"""Build ONE template for tools/build_compiled_templates.py, in one mayapy process.

Phase A (``--phase a``): transpile + AI assist + compile, optimizer OFF. Nothing
is timed, so nothing contends -- this is what the orchestrator fans out ~8 wide.

Phase B (``--phase b``): the SAME compile with the AI optimizer ON. The port is
served from the port cache that phase A warmed, so the only expensive work left
is the optimizer's agent rounds. Benchmarks inside the optimizer serialise on the
global bench lock (``MPYNODE_BENCH_LOCK``, owned elsewhere; a no-op if unset).

This worker records EVIDENCE and draws no conclusions from it:
  * did the AI actually write a ``2_assisted`` stage for a node, or was it served
    from cache, or did no node need the LLM at all;
  * did the optimizer write a FRESH ``rounds.json`` (created after this phase
    started), or is the one on disk left over from an earlier run;
  * each round's duration, outcome, ms, and whether its ``.cpp`` is
    BYTE-IDENTICAL to ``00_baseline.cpp`` (a "no-change accept").
The orchestrator turns that evidence into ok / degraded / fail.

Usage (spawned by the orchestrator; not meant to be run by hand):
    mayapy tools/build_compiled_templates_worker.py --rel REL --mpn PATH \
        --out DIR --phase a|b --result-json PATH [--smoke] [--clear-stages]
"""
import argparse
import collections
import hashlib
import json
import os
import shutil
import time
import traceback

# Non-log progress events kept verbatim in the evidence file.
MAX_EVENTS = 400
# Optimizer narration kept (tail): baseline ms, per-round ACCEPT/reject.
MAX_OPT_EVENTS = 400


def _md5(path):
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _stage_roots(out_dir):
    """Every directory a ``build/stages/<Type>/`` tree can land in.

    ``compile_controller`` hands the optimizer ``bundler.build_dir_for(out_dir)``
    (``<out>/build``) and ``optimizer_live`` re-applies ``bundler.stage_dir_for``,
    which prepends its OWN ``build/`` -- so the optimizer's stages land under
    ``<out>/build/build/stages`` while the porter's land under
    ``<out>/build/stages``. That doubling lives in scripts/, not here; look in
    BOTH so this keeps working whichever way it is resolved upstream.
    """
    build = os.path.join(out_dir, "build")
    return [os.path.join(build, "stages"),
            os.path.join(build, "build", "stages")]


def clear_round_cpps(out_dir):
    """Delete every ``3_optimized/`` under ``out_dir``, both stage roots.

    ``make_version_writer`` only ever ADDS files, and the filename carries the
    round's THEME -- so a re-run writes ``01_<other_slug>.cpp`` beside the last
    run's ``01_<old_slug>.cpp`` and two runs end up sharing one directory. The
    orchestrator calls this for ``--force``, which means "re-run this phase" and
    should therefore start from an empty stage. The ledger is left alone: it is
    rewritten wholesale each run and its ``created`` stamp already tells a reader
    whether it is this run's.
    """
    for root in _stage_roots(out_dir):
        if not os.path.isdir(root):
            continue
        for type_name in sorted(os.listdir(root)):
            d = os.path.join(root, type_name, "3_optimized")
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)


def _round_cpps(stage_dir, since=None):
    """``{round_index: path}`` for ``<stage_dir>/3_optimized/NN_<slug>.cpp``.

    ONE index can have several files (see :func:`clear_round_cpps`). Picking the
    last name alphabetically hands round 1 whichever slug sorts last, which may
    be a PREVIOUS run's -- and then ``cpp_same_as_baseline`` compares the wrong
    pair. A stale ``01_zzz.cpp`` that differs from the baseline, sitting beside a
    real ``01_accept.cpp`` that does not, hides a no-change accept: the exact
    thing this evidence exists to catch.

    Attribute by mtime instead, and when ``since`` (this phase's start) is given,
    a file written since then beats any older one whatever its slug. Without
    ``since`` the newest file wins, which is still never worse than alphabetical.
    """
    d   = os.path.join(stage_dir, "3_optimized")
    out = {}
    if not os.path.isdir(d):
        return out
    best = {}
    for name in sorted(os.listdir(d)):
        if not name.endswith(".cpp"):
            continue
        head = name.split("_", 1)[0]
        if not head.isdigit():
            continue
        path = os.path.join(d, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        rank = (since is not None and mtime >= since, mtime)
        idx  = int(head)
        if idx not in best or rank > best[idx][0]:
            best[idx] = (rank, path)
    for idx in best:
        out[idx] = best[idx][1]
    return out


def _collect_rounds(out_dir, since):
    """Read every optimizer ledger under ``out_dir``, newest per type name.

    ``since`` is this phase's start time: a ledger created before it is recorded
    with ``fresh: False`` so a leftover from an earlier run can never be read as
    proof that the optimizer ran now.
    """
    found = {}
    for root in _stage_roots(out_dir):
        if not os.path.isdir(root):
            continue
        for type_name in sorted(os.listdir(root)):
            stage_dir = os.path.join(root, type_name)
            path      = os.path.join(stage_dir, "rounds.json")
            if not os.path.isfile(path):
                continue
            try:
                with open(path) as fh:
                    doc = json.load(fh)
            except (ValueError, OSError):
                continue
            created = float(doc.get("created") or 0.0)
            prev    = found.get(type_name)
            if prev is not None and prev["created"] >= created:
                continue
            cpps     = _round_cpps(stage_dir, since)
            base_md5 = _md5(cpps.get(0))
            rounds   = []
            for r in (doc.get("ledger") or []):
                idx = r.get("index")
                cpp = cpps.get(idx)
                rounds.append({
                    "index":      idx,
                    "outcome":    r.get("outcome"),
                    "duration_s": r.get("duration_s"),
                    "ms":         r.get("ms"),
                    "speedup":    r.get("speedup"),
                    "parity":     r.get("parity"),
                    "slug":       r.get("slug"),
                    "note":       r.get("note"),
                    # An agent session that ran fills these in. Empty across
                    # every round is what "no agent ran" looks like on disk.
                    "has_theme":      bool((r.get("theme") or "").strip()),
                    "has_hypothesis": bool((r.get("hypothesis") or "").strip()),
                    # The decisive one: a round whose .cpp is byte-identical to
                    # the baseline changed NOTHING, whatever it claims.
                    "cpp_same_as_baseline": (
                        None if (cpp is None or base_md5 is None)
                        else _md5(cpp) == base_md5),
                })
            found[type_name] = {
                "created":     created,
                "fresh":       created >= since,
                "path":        path,
                "accepted":    bool(doc.get("accepted")),
                "baseline_ms": doc.get("baseline_ms"),
                "best_ms":     doc.get("best_ms"),
                "speedup":     doc.get("speedup"),
                "reason":      doc.get("reason"),
                "parity_gate": doc.get("parity_gate"),
                "n_rounds":    doc.get("rounds"),
                "rounds":      rounds,
            }
    return found


class _Facts(object):
    """A ``progress_cb`` that keeps only what the manifest has to prove."""

    def __init__(self):
        self.assisted_now       = []
        self.assisted_cached    = []
        self.cache_hit          = []
        self.cache_miss         = []
        self.no_node_needed_llm = False
        self.events             = []
        self.n_log_lines        = 0
        self.opt_events         = collections.deque(maxlen=MAX_OPT_EVENTS)
        self.n_opt_events       = 0

    def __call__(self, ev):
        stage  = ev.get("stage")
        status = ev.get("status")
        node   = ev.get("node")
        detail = str(ev.get("detail") or "")
        if stage == "log":
            self.n_log_lines += 1
            return
        if stage == "stage" and node:
            if detail == "2_assisted":
                self.assisted_now.append(node)
            elif detail == "2_assisted_cached":
                self.assisted_cached.append(node)
        elif stage == "cache" and node:
            if status == "hit":
                self.cache_hit.append(node)
            elif status == "miss":
                self.cache_miss.append(node)
        elif (stage == "port" and status == "skip"
                and "no node needed AI assist" in detail):
            self.no_node_needed_llm = True
        if stage == "optimize":
            self.n_opt_events += 1
            self.opt_events.append("%s %s: %s"
                                   % (node or "-", status, detail[:300]))
            return
        if len(self.events) < MAX_EVENTS:
            self.events.append("%s %s %s: %s"
                               % (stage, node or "-", status, detail[:300]))

    def as_dict(self):
        return {
            "assisted_now": sorted(set(self.assisted_now)),
            "assisted_cached": sorted(set(self.assisted_cached)),
            "cache_hit": sorted(set(self.cache_hit)),
            "cache_miss": sorted(set(self.cache_miss)),
            "no_node_needed_llm": self.no_node_needed_llm,
            "n_log_lines": self.n_log_lines,
            "n_optimize_events": self.n_opt_events,
            "optimize_events_tail": list(self.opt_events),
            "events": self.events,
        }


def _slim_nodes(result):
    out = []
    for row in (result.get("nodes") or []):
        out.append({
            "type_name":    row.get("type_name"),
            "cache":        row.get("cache"),
            "build_status": row.get("build_status"),
            "build_reason": str(row.get("build_reason") or "")[:400],
            "ported":       row.get("ported"),
            "incomplete":   row.get("incomplete") or [],
            "verify":       row.get("verify") or {},
        })
    return out


def run(rel, mpn_path, out_dir, phase, smoke, clear_stages=False):
    from mpynode.native.toolchain import compile_controller as cc

    optimize  = (phase == "b") and not smoke
    ai_assist = not smoke
    mode = {"optimize": optimize, "ai_assist": ai_assist,
            "keep_intermediates": optimize}

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    if clear_stages:
        clear_round_cpps(out_dir)

    facts = _Facts()
    t0    = time.time()
    result = cc.compile_from_mpn_paths(
        # Flatten BOTH separators, not os.sep: callers hand `rel` over in POSIX
        # form (run_qt_verify.py passes rel.replace(os.sep, "/")), so on Windows
        # os.sep is "\\" and this replace was a NO-OP -- the "/" survived into
        # plugin_name and the linker was asked to write
        # <out>/MPyLocator/Animated Selection.mll into a directory nobody
        # created ("LNK1104: cannot open file"). MEASURED on Windows 2026-08-14.
        # On macOS/Linux os.sep is already "/" so the result is unchanged.
        # SPACE folds for exactly the same reason: template leaf folders are now
        # "Mesh Regions" / "Two Bone IK", and plugin_name becomes the .bundle /
        # .mll filename handed to the linker -- an unquoted space there is the
        # same class of failure as the surviving "/" above.
        [mpn_path], (rel.replace("\\", "_").replace("/", "_")
                     .replace("-", "_").replace(" ", "_")),
        out_dir,
        trusted            = True,
        optimize           = optimize,
        ai_assist          = ai_assist,
        keep_intermediates = optimize,
        strict             = False,
        verify             = True,
        clean_scratch      = False,
        progress_cb        = facts,
    )
    secs = round(time.time() - t0, 1)

    row = {
        "rel":         rel,
        "phase":       phase,
        "smoke":       bool(smoke),
        "mode":        mode,
        "state":       "ok" if result.get("ok") else "fail",
        "secs":        secs,
        "started":     t0,
        "ended":       time.time(),
        "errors":      [str(e)[:600] for e in (result.get("errors") or [])],
        "bundle_path": result.get("bundle_path"),
        "bundle_exists": bool(result.get("bundle_path")
                              and os.path.exists(result["bundle_path"])),
        "nodes": _slim_nodes(result),
        "ai":    facts.as_dict(),
        # {} when the optimizer never ran; may carry __status__/__error__.
        "optimize_summary": result.get("optimize") or {},
        # Only ledgers written during THIS phase count as proof.
        "rounds": _collect_rounds(out_dir, t0) if optimize else {},
    }
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rel", required=True)
    ap.add_argument("--mpn", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--phase", required=True, choices=("a", "b"))
    ap.add_argument("--result-json", required=True)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--clear-stages", action="store_true",
                    help="delete 3_optimized/ first; the orchestrator passes "
                         "this for --force")
    args = ap.parse_args()

    import maya.standalone
    maya.standalone.initialize(name="python")

    try:
        row = run(args.rel, args.mpn, args.out, args.phase, args.smoke,
                  clear_stages=args.clear_stages)
    except Exception as exc:
        row = {
            "rel": args.rel, "phase": args.phase, "smoke": bool(args.smoke),
            "state": "fail", "secs": None,
            "mode": {"optimize": args.phase == "b" and not args.smoke,
                     "ai_assist": not args.smoke,
                     "keep_intermediates": args.phase == "b" and not args.smoke},
            "errors": ["%s: %s" % (type(exc).__name__, exc)],
            "trace":  traceback.format_exc()[-4000:],
            "nodes": [], "ai": {}, "optimize_summary": {}, "rounds": {},
        }

    tmp = args.result_json + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(row, fh, indent=2, sort_keys=True, default=str)
    # os.replace, NOT os.rename: POSIX rename overwrites, Windows raises
    # WinError 183 when the destination exists, so the SECOND save of a
    # run killed the orchestrator. Same call the toolchain's own atomic
    # writers use (port_cache, verify, typeid_registry).
    os.replace(tmp, args.result_json)
    print("[worker] %s phase=%s state=%s secs=%s"
          % (args.rel, args.phase, row.get("state"), row.get("secs")))


if __name__ == "__main__":
    main()
