"""Compile every template in templates/, in place.

Each template.mpn is compiled into a build/ tree inside its own folder, so
    templates/MPyMesh/Voxelize/template.mpn
lands in
    templates/MPyMesh/Voxelize/build/

TWO PHASES, because they have opposite scheduling needs:

  PHASE A -- transpile + AI assist + compile, optimizer OFF. Nothing is timed, so
    nothing contends; it is CPU- and network-bound and fans out. ``--jobs``
    workers (default 8: 16 cores / 12 perf, and each worker is a mayapy).

  PHASE B -- the same compile with the AI optimizer ON (``MPYNODE_OPT_ROUNDS``
    rounds, intermediates kept). The port is served from the cache phase A
    warmed, so the expensive part is the agent rounds, which run ``--opt-jobs``
    wide. The BENCHMARKS inside serialise on the global bench lock
    (``MPYNODE_BENCH_LOCK``, owned elsewhere; a no-op when unset) -- two
    processes timing at once corrupt both sets of numbers.

Each template is built by tools/build_compiled_templates_worker.py in its OWN
mayapy process. That worker records evidence (did the AI write a 2_assisted
stage; did the optimizer write a FRESH rounds.json; each round's duration and
whether its .cpp is byte-identical to the baseline) and this orchestrator turns
that evidence into a verdict:

    ok        both phases ran and the optimizer really did work
    degraded  the phase "succeeded" but did NOT do what it claims (no agent
              session, a no-change accept, a stale ledger, rounds under a
              minute, optimizer skipped/errored)
    fail      the compile itself failed

A degraded row is NEVER counted as ok and is always re-run on resume, so the
77-minute "ok=43 fail=0" run that never called an LLM cannot happen silently.

RESUMABLE. A phase is skipped only when the manifest already holds an ``ok`` row
for it whose recorded MODE is at least as strong as the one being asked for --
which is what generalises the old "smoke" special case: a smoke row (no AI, no
optimizer) never satisfies a full request.

Usage (under mayapy, via tools/build_compiled_templates.sh):
    tools/build_compiled_templates.sh [--only SUBSTR] [--limit N]
                                      [--jobs 8] [--opt-jobs 8]
                                      [--phase both|a|b] [--smoke] [--force]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "templates")
# Each template's compiled tree lives inside the template folder it came from,
# so source and destination are the same root and `os.path.join(DST, rel)`
# below lands back on the directory the walk already visited.
DST = SRC
# The ledger is per-run machine state about the whole tree, not part of any one
# template, so it stays out of templates/.
MANIFEST = os.path.join(ROOT, "_build_state", "manifest.json")
WORKER = os.path.join(ROOT, "tools", "build_compiled_templates_worker.py")

MAYAPY = os.environ.get(
    "MPYNODE_MAYAPY",
    "/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy")

# A round that resolved this fast cannot have held an agent session (a real one
# is 350-1800 s). Measured against the run that produced ~10 s rounds.
FAST_ROUND_S = 60.0

# Benchmark noise, expressed as the smallest DELTA worth believing -- not as a
# minimum baseline. optimizer_live._BENCH_FLOOR_MS (15 ms) is a SCENE-SIZE
# target: the bench ladder grows the scene until the baseline clears it and
# settles for less when the ladder runs out. Read as a measurement uncertainty it
# called a real 8.685 -> 1.929 ms win (4.50x, parity pass, shipped) "noise"
# purely because the ladder had run out at 8.685 ms. What actually bounds
# resolution is what optimizer_live records: ~8% run-to-run noise on each median,
# over a ~0.4 ms fixed whole-evaluation cost no rewrite can remove. A speedup is
# noise when the time SAVED clears neither.
NOISE_FLOOR_MS = 0.4
NOISE_FRAC = 0.08

# Phase B is NOT one process per job. Each optimizer agent shells out to its own
# mayapy for every build / bench / parity check, and the CLI agent driving it is
# a third process -- a tree this orchestrator never counted. Measured on a 64 GB
# / 16-core machine: --opt-jobs 4 wedged it, 3 of the 4 workers dying at an
# identical 803.5 s with Maya's crash report reading "0.000 Mb Free Memory /
# 0.000 Mb Free Swap".
#
# Budget by MEMORY, because memory is what ran out: those 4 jobs did not fit in
# 67 GB (64 RAM + 3 swap), so one job's peak is north of 16 GB. Rounded up,
# because the two errors are not symmetric -- one slot fewer costs wall time on a
# run already measured in hours, while an OOM loses every in-flight slot and
# produces nothing.
OPT_JOB_GB = 24.0
# ...and the cores it occupies while doing it, so a small-RAM/many-core box
# cannot oversubscribe the CPU the same way.
OPT_JOB_CORES = 4

# Under this much free RAM AND free swap, at the moment Maya wrote its crash
# report, the MACHINE is what failed -- not the template.
OOM_FREE_MB = 64.0

_CRASH_RE = re.compile(r"Writing crash report in (\S.*?\.crash)")
_FREE_RE = re.compile(r"([0-9.]+)\s*Mb\s+Free (Memory|Swap)")


def opt_jobs_budget(mem_bytes=None, cores=None):
    """How many phase-B workers this machine can actually hold.

    Deliberately NOT ``--jobs``: phase A is one mayapy per job and fans out,
    phase B is a process tree per job (see OPT_JOB_GB) and does not.
    """
    if mem_bytes is None:
        try:
            mem_bytes = (os.sysconf("SC_PAGE_SIZE")
                         * os.sysconf("SC_PHYS_PAGES"))
        except (ValueError, OSError, AttributeError):
            mem_bytes = 16 * (1024 ** 3)
    if cores is None:
        cores = os.cpu_count() or 4
    by_mem = int(float(mem_bytes) / (OPT_JOB_GB * (1024 ** 3)))
    by_cpu = int(cores) // OPT_JOB_CORES
    return max(1, min(by_mem, by_cpu))


# ---------------------------------------------------------------------------
# discovery / manifest
# ---------------------------------------------------------------------------


def find_templates():
    out = []
    for dirpath, _dirnames, filenames in os.walk(SRC):
        if "template.mpn" in filenames:
            rel = os.path.relpath(dirpath, SRC)
            out.append((rel, os.path.join(dirpath, "template.mpn")))
    out.sort()
    return out


def load_manifest():
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST) as fh:
                man = json.load(fh)
            if isinstance(man, dict) and isinstance(man.get("rows"), dict):
                return _migrate(man)
        except (ValueError, OSError):
            pass
    return {"rows": {}}


def _migrate(man):
    """Park pre-two-phase rows under ``legacy``.

    The old shape was ``{ok, secs, smoke, result}`` -- a bare "ok" with no
    evidence of what ran, which is exactly what this rewrite exists to stop
    trusting. Keep it readable, but never let it satisfy a phase.
    """
    for rel, row in man["rows"].items():
        if not isinstance(row, dict):
            man["rows"][rel] = {"legacy": row}
        elif "phase_a" not in row and "phase_b" not in row and "legacy" not in row:
            man["rows"][rel] = {"legacy": row}
    return man


def save_manifest(man):
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    tmp = MANIFEST + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(man, fh, indent=2, sort_keys=True, default=str)
    # os.replace, NOT os.rename: POSIX rename overwrites, Windows raises
    # WinError 183 when the destination exists, so the SECOND save of a
    # run killed the orchestrator. Same call the toolchain's own atomic
    # writers use (port_cache, verify, typeid_registry).
    os.replace(tmp, MANIFEST)


def wanted_mode(phase, smoke):
    """The contract a phase is being asked to honour."""
    optimize = (phase == "b") and not smoke
    return {"optimize": optimize, "ai_assist": not smoke,
            "keep_intermediates": optimize}


def mode_satisfies(have, want):
    """Does a recorded phase mode cover the one now being asked for?

    Generalises the old ``smoke`` special case: every knob the request wants ON
    must have been ON in the recorded run. A weaker run never satisfies a
    stronger request; a stronger one always satisfies a weaker.
    """
    have = have or {}
    for key, need in (want or {}).items():
        if need and not have.get(key):
            return False
    return True


# ---------------------------------------------------------------------------
# evidence -> flags
# ---------------------------------------------------------------------------
# BLOCKING  the phase did not actually do its job -> never "ok", re-run on resume
# ADVISORY  the phase really ran, but the number it produced is not meaningful

BLOCKING = {
    "ai-preflight-fail", "no-ai-evidence",
    "optimizer-did-not-run", "optimizer-skipped", "optimizer-error",
    "stale-ledger", "no-agent-evidence", "no-change-accept",
    "all-rounds-fast", "zero-rounds", "ledger-missing",
    "worker-oom", "worker-killed",
    "port-incomplete",
}

# BLOCKING flags that a RE-RUN cannot clear. The port already succeeded and the
# bundle already built; what is missing is a feature the porter could not express,
# which only a codegen or authoring change fixes. So the row is never "clean", but
# resume must not burn another AI port on it every single run.
NO_RERUN = {"port-incomplete"}

FLAG_NOTES = {
    "port-incomplete":
        "a node recorded ND_PORT_INCOMPLETE -- it compiled, but a feature of "
        "the Python was NOT ported and does nothing at runtime; see the "
        "'incomplete' list in that template's phase_a.json. A re-run cannot "
        "clear this",
    "no-change-accept":
        "an 'accept' round's .cpp is BYTE-IDENTICAL to 00_baseline.cpp -- "
        "nothing was changed",
    "no-agent-evidence":
        "every round has an empty theme AND hypothesis -- no agent session ran",
    "all-rounds-fast":
        "every round resolved in under {fast_s}s; a real agent round is "
        "350-1800 s",
    "noise-floor-speedup":
        "claimed {spd:.2f}x, but the {saved} ms saved off a {base} ms baseline "
        "is inside the benchmark's own noise (max({noise_ms} ms, "
        "{noise_pct:.0f}% of the baseline))",
    "worker-oom":
        "the MACHINE ran out of memory and Maya was killed -- capacity, not "
        "this template; lower --opt-jobs and re-run",
    "worker-killed":
        "the worker was killed by a signal before it could report",
    "stale-ledger":
        "rounds.json predates this run -- left over from an earlier one",
    "optimizer-did-not-run":
        "no rounds.json was written at all",
    "optimizer-skipped":
        "the optimizer refused the whole plugin (see optimize_summary "
        "__status__) -- typically no reachable AI provider",
    "optimizer-error":
        "the optimizer raised; the un-optimized .cpp was shipped",
    "ledger-missing":
        "a node the optimizer reported on left no rounds.json",
    "zero-rounds":
        "a baseline was measured but not one round ran",
    "unmeasurable":
        "the node cannot be benchmarked at all -- permanent, not a bad run",
    "optimizer-skipped-by-gate":
        "every node is isolation-unsafe to optimize (mPyFile / shared helper)",
    "no-ai-evidence":
        "no 2_assisted stage, no cached assist, and no 'nothing needed the "
        "AI' -- assist unaccounted for",
    "ai-from-cache":
        "assist served from the port cache (the AI ran earlier, not now)",
    "ai-not-needed":
        "every compute lowered deterministically -- no LLM needed",
    "ai-preflight-fail":
        "the AI provider was not reachable",
}


def phase_a_flags(entry):
    flags = []
    # Checked BEFORE the state guard: an unreachable provider aborts the build,
    # so this is the one phase-A flag that only ever appears on a failed row --
    # and it is the reason a reader most needs to see.
    if any("AI provider" in e and "not reachable" in e
           for e in (entry.get("errors") or [])):
        flags.append("ai-preflight-fail")
    if entry.get("state") != "ok" or entry.get("smoke"):
        return flags
    # A node whose porter recorded ND_PORT_INCOMPLETE still builds, still links
    # and still reports build_status=compiled -- so without this it counted as
    # clean while shipping a feature that silently does nothing.
    if any((n or {}).get("incomplete") for n in (entry.get("nodes") or [])):
        flags.append("port-incomplete")
    ai = entry.get("ai") or {}
    fresh = ai.get("assisted_now") or []
    cached = ai.get("assisted_cached") or []
    if not fresh and not cached and not ai.get("no_node_needed_llm"):
        # Neither "the AI wrote this", nor "the cache had the AI's earlier
        # answer", nor "no node needed the AI". That combination means we cannot
        # say the assist step happened at all.
        flags.append("no-ai-evidence")
    elif ai.get("no_node_needed_llm"):
        flags.append("ai-not-needed")
    elif not fresh:
        flags.append("ai-from-cache")
    return flags


def _saved_ms(rec):
    """Wall time an accepted optimization actually removed, or ``None``.

    ``best_ms`` is what the ledger records; a ledger written before it existed is
    reconstructed from the speedup rather than dropped.
    """
    base = rec.get("baseline_ms")
    if base is None:
        return None
    base = float(base)
    best = rec.get("best_ms")
    if best is None:
        spd = float(rec.get("speedup") or 0.0)
        if spd <= 0.0:
            return None
        best = base / spd
    return base - float(best)


def _node_round_flags(rec, fast_s, noise_ms):
    """Flags for ONE node's optimizer ledger."""
    flags = []
    if not rec.get("fresh"):
        flags.append("stale-ledger")
    rounds = [r for r in (rec.get("rounds") or [])
              if r.get("outcome") != "baseline"]
    if not rounds:
        # No baseline ms means the node could not be benchmarked at all (the
        # optimizer's own "unmeasurable"). That is a permanent property of the
        # node, not a degraded run -- flag it, but never re-run it forever.
        flags.append("unmeasurable" if rec.get("baseline_ms") is None
                     else "zero-rounds")
        return flags
    if not any(r.get("has_theme") or r.get("has_hypothesis") for r in rounds):
        flags.append("no-agent-evidence")
    if any(r.get("outcome") == "accept" and r.get("cpp_same_as_baseline")
           for r in rounds):
        flags.append("no-change-accept")
    durs = [r.get("duration_s") for r in rounds]
    if durs and all(d is not None and d < fast_s for d in durs):
        flags.append("all-rounds-fast")
    # ADVISORY: is the win bigger than what this benchmark can resolve? That is a
    # question about the DELTA. Gating on the baseline instead called a real
    # 8.685 -> 1.929 ms win noise because the bench ladder had run out below the
    # 15 ms scene target -- see NOISE_FLOOR_MS.
    saved = _saved_ms(rec)
    if rec.get("accepted") and saved is not None:
        noise = max(noise_ms, NOISE_FRAC * float(rec.get("baseline_ms") or 0.0))
        if saved < noise:
            flags.append("noise-floor-speedup")
    return flags


def phase_b_flags(entry, fast_s, noise_ms):
    flags = []
    # Checked BEFORE the state guard, like phase A's ai-preflight-fail: a worker
    # the machine killed never got to record a state, and how it died is the one
    # thing a reader of a failed row most needs -- the remedy for an OOM is
    # --opt-jobs, not the template.
    killed = entry.get("killed")
    if killed == "oom":
        flags.append("worker-oom")
    elif killed:
        flags.append("worker-killed")
    if entry.get("state") != "ok":
        return flags
    summary = entry.get("optimize_summary") or {}
    if summary.get("__status__"):
        flags.append("optimizer-skipped")
    if summary.get("__error__"):
        flags.append("optimizer-error")
    # Per-node rows, minus the __status__/__error__/__fallback__ sentinels.
    per_node = {k: (v or {}) for k, v in summary.items()
                if not k.startswith("__")}
    # The controller REFUSES to optimize an mPyFile or a shared-helper node (it
    # cannot be validated in isolation). That is the gate working, not a
    # degraded run, and it writes no ledger at all.
    gate_skipped = {k for k, v in per_node.items()
                    if str(v.get("reason") or "").startswith("skipped:")}
    rounds = entry.get("rounds") or {}
    if not rounds:
        if per_node and len(gate_skipped) == len(per_node):
            flags.append("optimizer-skipped-by-gate")
        else:
            flags.append("optimizer-did-not-run")
        return flags
    for tn in sorted(per_node):
        if tn not in rounds and tn not in gate_skipped:
            flags.append("ledger-missing")
            break
    for rec in rounds.values():
        for f in _node_round_flags(rec, fast_s, noise_ms):
            if f not in flags:
                flags.append(f)
    return flags


def row_verdict(row, phases, fast_s, noise_ms):
    """(state, flags) for a template from its recorded phase entries."""
    flags = []
    failed = False
    missing = False
    for phase in phases:
        entry = row.get("phase_" + phase)
        if not entry:
            # Keep going: a FAILED phase A must not read as merely "missing"
            # because phase B never got to run after it.
            missing = True
            continue
        if entry.get("state") != "ok":
            failed = True
        f = (phase_a_flags(entry) if phase == "a"
             else phase_b_flags(entry, fast_s, noise_ms))
        flags.extend(phase + ":" + x for x in f)
    if failed:
        return "fail", flags
    if missing:
        return "missing", flags
    if any(x.split(":", 1)[1] in BLOCKING for x in flags):
        return "degraded", flags
    return "ok", flags


def phase_is_done(row, phase, want, fast_s, noise_ms):
    """Can this phase be skipped on resume?

    Only when it is recorded ``ok``, was run under a mode at least as strong as
    the one requested, and carries no BLOCKING flag. An advisory flag (a
    noise-floor baseline) is a fact about the node, not a reason to burn another
    hour on it.
    """
    entry = row.get("phase_" + phase)
    if not entry or entry.get("state") != "ok":
        return False
    if not mode_satisfies(entry.get("mode"), want):
        return False
    f = (phase_a_flags(entry) if phase == "a"
         else phase_b_flags(entry, fast_s, noise_ms))
    return not any(x in BLOCKING and x not in NO_RERUN for x in f)


# ---------------------------------------------------------------------------
# parallel driver
# ---------------------------------------------------------------------------


def _runner_dir(rel):
    d = os.path.join(DST, rel, "_runner")
    if not os.path.isdir(d):
        os.makedirs(d)
    return d


def spawn(rel, mpn_path, phase, smoke, force=False):
    """Start one worker. Returns (proc, result_json, log_path, t0)."""
    rdir = _runner_dir(rel)
    result_json = os.path.join(rdir, "phase_%s.json" % phase)
    log_path = os.path.join(rdir, "phase_%s.log" % phase)
    if os.path.exists(result_json):
        # Stale result from a previous attempt must not be read as this one's.
        os.remove(result_json)
    cmd = [MAYAPY, WORKER, "--rel", rel, "--mpn", mpn_path,
           "--out", os.path.join(DST, rel), "--phase", phase,
           "--result-json", result_json]
    if smoke:
        cmd.append("--smoke")
    # --force means "re-run this phase", so it must also start from an empty
    # 3_optimized/: leave the last run's NN_<slug>.cpp there and one directory
    # holds two runs, which is how a round gets attributed to the wrong file.
    if force and phase == "b" and not smoke:
        cmd.append("--clear-stages")
    log = open(log_path, "w")
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    proc._log_fh = log
    return proc, result_json, log_path, time.time()


def _death_kind(returncode, log_tail):
    """Why a worker that wrote no result died: ``'oom'``, ``'signal-N'``, None.

    Maya names the ``.crash`` file it is writing on stderr and records the memory
    it had at that moment inside it; "0.000 Mb Free Memory / 0.000 Mb Free Swap"
    is the machine exhausted by the phase-B fan-out, which is a CAPACITY problem
    with a different remedy than a broken template. Best-effort -- the next crash
    overwrites that file, and a missing one simply is not evidence of an OOM.
    """
    m = _CRASH_RE.search(log_tail or "")
    if m:
        free = {}
        try:
            with open(m.group(1).strip()) as fh:
                free = dict((k, float(v))
                            for v, k in _FREE_RE.findall(fh.read()))
        except (OSError, ValueError):
            free = {}
        if (free.get("Memory", 1e9) < OOM_FREE_MB
                and free.get("Swap", 1e9) < OOM_FREE_MB):
            return "oom"
    if returncode is not None and returncode < 0:
        return "signal-%d" % -returncode
    return None


def harvest(rel, phase, proc, result_json, log_path, t0):
    """Turn a finished worker into a phase entry.

    The worker's EXIT CODE is not trusted: after maya.standalone.initialize()
    mayapy's teardown forces 0. The result json is the signal -- no file means
    the process died before it could report.
    """
    try:
        proc._log_fh.close()
    except Exception:
        pass
    entry = None
    if os.path.exists(result_json):
        try:
            with open(result_json) as fh:
                entry = json.load(fh)
        except (ValueError, OSError):
            entry = None
    if entry is None:
        tail = ""
        try:
            with open(log_path) as fh:
                tail = fh.read()[-1500:]
        except OSError:
            pass
        killed = _death_kind(proc.returncode, tail)
        if killed == "oom":
            err = ("worker was KILLED: the machine ran out of memory (no free "
                   "RAM and no free swap when Maya wrote its crash report). "
                   "Capacity, not this template -- lower --opt-jobs and re-run")
        elif killed:
            err = "worker was killed by %s (rc=%s)" % (killed, proc.returncode)
        else:
            err = "worker wrote no result (rc=%s)" % proc.returncode
        entry = {"rel": rel, "phase": phase, "state": "fail", "mode": {},
                 "errors": [err], "killed": killed,
                 "log_tail": tail, "nodes": [], "ai": {},
                 "optimize_summary": {}, "rounds": {}}
    entry["wall_secs"] = round(time.time() - t0, 1)
    entry["log"] = log_path
    return entry


def run_phase(phase, jobs, todo, man, smoke, fast_s, noise_ms, force=False):
    """Run ``todo`` [(rel, mpn)] through ``jobs`` concurrent workers."""
    if not todo:
        print("PHASE %s: nothing to do" % phase.upper())
        return
    print("PHASE %s: %d template(s), %d worker(s)"
          % (phase.upper(), len(todo), jobs))
    sys.stdout.flush()
    pending = list(todo)
    running = []
    done = 0
    while pending or running:
        while pending and len(running) < jobs:
            rel, mpn_path = pending.pop(0)
            print("  start  %s" % rel)
            sys.stdout.flush()
            running.append((rel,) + spawn(rel, mpn_path, phase, smoke, force))
        time.sleep(2.0)
        still = []
        for rel, proc, result_json, log_path, t0 in running:
            if proc.poll() is None:
                still.append((rel, proc, result_json, log_path, t0))
                continue
            entry = harvest(rel, phase, proc, result_json, log_path, t0)
            row = man["rows"].setdefault(rel, {})
            row["phase_" + phase] = entry
            save_manifest(man)
            done += 1
            f = (phase_a_flags(entry) if phase == "a"
                 else phase_b_flags(entry, fast_s, noise_ms))
            print("  [%d/%d] %-7s %s  %ss%s"
                  % (done, len(todo), entry.get("state"), rel,
                     entry.get("wall_secs"),
                     ("  flags=" + ",".join(f)) if f else ""))
            sys.stdout.flush()
        running = still


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


def _best(entry):
    """(speedup, baseline_ms, saved_ms) of the best accepted node in a phase-B
    entry."""
    best_s, base, saved = 1.0, None, None
    for rec in (entry.get("rounds") or {}).values():
        if not rec.get("accepted"):
            continue
        s = float(rec.get("speedup") or 1.0)
        if s > best_s:
            best_s, base, saved = s, rec.get("baseline_ms"), _saved_ms(rec)
    return best_s, base, saved


def summarise(man, rels, phases, fast_s, noise_ms):
    print("\n" + "=" * 96)
    print("SUMMARY   phases=%s   fast-round<%ss   "
          "resolvable-delta>max(%sms, %.0f%% of baseline)"
          % (",".join(phases), fast_s, noise_ms, NOISE_FRAC * 100))
    print("=" * 96)
    print("%-46s %-9s %7s %8s %8s  %s"
          % ("template", "state", "A secs", "B secs", "speedup", "flags"))
    counts = {}
    suspect = []
    for rel in rels:
        row = man["rows"].get(rel) or {}
        state, flags = row_verdict(row, phases, fast_s, noise_ms)
        counts[state] = counts.get(state, 0) + 1
        a = row.get("phase_a") or {}
        b = row.get("phase_b") or {}
        spd, base, saved = _best(b)
        print("%-46s %-9s %7s %8s %8s  %s"
              % (rel[:46], state, a.get("wall_secs", "-"),
                 b.get("wall_secs", "-"),
                 ("%.2fx" % spd) if spd > 1.0 else "-",
                 ",".join(flags)))
        if flags:
            suspect.append((rel, state, flags, spd, base, saved))
    print("-" * 96)
    print("  ".join("%s=%d" % (k, counts[k]) for k in sorted(counts)))

    n_oom = 0
    if suspect:
        print("\nFLAGGED ROWS  (BLOCKING = the phase did not do its job)")
        print("-" * 96)
        for rel, state, flags, spd, base, saved in suspect:
            print("  %s  [%s]" % (rel, state))
            ctx = {"fast_s": fast_s, "noise_ms": noise_ms, "spd": spd,
                   "base": base, "noise_pct": NOISE_FRAC * 100,
                   "saved": "?" if saved is None else "%.3f" % saved}
            for f in flags:
                key = f.split(":", 1)[1]
                if key == "worker-oom":
                    n_oom += 1
                print("      %-28s %s%s"
                      % (f, "BLOCKING " if key in BLOCKING else "advisory ",
                         FLAG_NOTES.get(key, "").format(**ctx)))

    if n_oom:
        # Said once, loudly: these rows say nothing about their templates. The
        # fan-out was too wide for the machine and the next run must be narrower.
        print("\n%d worker(s) were killed by the MACHINE running out of memory."
              % n_oom)
        print("  Those rows are not verdicts on their templates -- re-run them "
              "with --opt-jobs %d or fewer." % opt_jobs_budget())

    bad = counts.get("degraded", 0) + counts.get("fail", 0) \
        + counts.get("missing", 0)
    print("\nDONE. clean=%d  not-clean=%d  of %d"
          % (counts.get("ok", 0), bad, len(rels)))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="",
                    help="comma-separated substrings; keep matching templates")
    ap.add_argument("--rounds", type=int, default=2,
                    help="optimize rounds per node (MPYNODE_OPT_ROUNDS)")
    ap.add_argument("--jobs", type=int, default=8,
                    help="phase A concurrency (each worker is a mayapy)")
    ap.add_argument("--opt-jobs", type=int, default=0,
                    help="phase B concurrency (default: what this machine can "
                         "hold -- each job is a TREE of Maya processes, not one)")
    ap.add_argument("--phase", default="both", choices=("both", "a", "b"))
    ap.add_argument("--smoke", action="store_true",
                    help="plumbing check: phase A only, no LLM, no optimizer")
    ap.add_argument("--force", action="store_true",
                    help="re-run every phase, even ones recorded ok")
    ap.add_argument("--fast-round-s", type=float, default=FAST_ROUND_S)
    ap.add_argument("--noise-floor-ms", type=float, default=NOISE_FLOOR_MS)
    ap.add_argument("--summary-only", action="store_true",
                    help="re-print the summary from the manifest; build nothing")
    args = ap.parse_args()

    os.environ["MPYNODE_OPT_ROUNDS"] = str(args.rounds)
    # NOT args.jobs: phase A is one mayapy per job, phase B is a process tree per
    # job. Inheriting --jobs is what put 8 optimizer agents on a machine that
    # could not hold 4 (see OPT_JOB_GB).
    budget = opt_jobs_budget()
    opt_jobs = args.opt_jobs or budget
    if opt_jobs > budget:
        print("WARNING: --opt-jobs %d is over this machine's phase-B budget of "
              "%d. Each phase-B job is a worker mayapy PLUS the optimizer "
              "agent PLUS the mayapy children that agent spawns to build, "
              "bench and parity-check; --opt-jobs 4 on a 64 GB box killed 3 of "
              "4 workers with no free memory and no free swap."
              % (opt_jobs, budget))
    phases = ["a"] if args.smoke else (["a", "b"] if args.phase == "both"
                                       else [args.phase])

    templates = find_templates()
    if args.only:
        pats = [p.strip() for p in args.only.split(",") if p.strip()]
        templates = [t for t in templates if any(p in t[0] for p in pats)]
    if args.limit:
        templates = templates[:args.limit]
    rels = [rel for rel, _ in templates]

    man = load_manifest()
    if args.summary_only:
        summarise(man, rels, phases, args.fast_round_s, args.noise_floor_ms)
        return

    print("templates: %d   phases=%s   rounds=%d   jobs=%d/%d (phase-B budget "
          "%d)   bench_lock=%s"
          % (len(templates), ",".join(phases), args.rounds, args.jobs, opt_jobs,
             budget,
             os.environ.get("MPYNODE_BENCH_LOCK") or "(unset -- no-op)"))
    sys.stdout.flush()

    t0 = time.time()
    for phase in phases:
        want = wanted_mode(phase, args.smoke)
        todo = []
        for rel, mpn_path in templates:
            row = man["rows"].get(rel) or {}
            if not args.force and phase_is_done(row, phase, want,
                                                args.fast_round_s,
                                                args.noise_floor_ms):
                print("  skip (done) %s" % rel)
                continue
            # Never spend an optimizer session on a template that cannot even
            # compile -- phase B would just re-run phase A's failure, slowly.
            if phase == "b" and (row.get("phase_a") or {}).get("state") == "fail":
                print("  skip (phase A failed) %s" % rel)
                continue
            todo.append((rel, mpn_path))
        jobs = args.jobs if phase == "a" else opt_jobs
        run_phase(phase, max(1, jobs), todo, man, args.smoke,
                  args.fast_round_s, args.noise_floor_ms, args.force)

    print("\nwall %.1f min" % ((time.time() - t0) / 60.0))
    summarise(man, rels, phases, args.fast_round_s, args.noise_floor_ms)


if __name__ == "__main__":
    main()
