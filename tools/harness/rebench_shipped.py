"""Re-measure every shipped AI-optimized node under the gated benchmark.

The 28 accepted speedups in the shipped ``rounds.json`` ledgers were measured
before the harness had a noise floor, before it moved every animated input
between ticks, and before it held a candidate to the baseline's outputs -- so
several of them time a cache hit (rbfWrap "6103x") or an early-out (spline
"3698x"). This re-measures each one honestly and writes the result BESIDE the
old number, never over it:

  for each build/stages/<Type>/rounds.json with ``accepted: true``
      compile 3_optimized/00_baseline.cpp   (the pre-optimization source)
      compile build/<Type>/<Type>.cpp       (the shipped final)
      calibrate the bench scene on the baseline, fingerprint its outputs
      time the final on the SAME scene, held to those outputs
      rounds.json["remeasured"] = {date, rung, baseline_ms, final_ms, speedup,
                                   fingerprint, perturbed, reason, diverged}
      regenerate the node's REPORT.md

Nothing is reverted: a final whose outputs diverge from its own baseline is
listed in the summary for a decision.

    mayapy tools/harness/rebench_shipped.py [--only a,b] [--dry-run]
                                            [--maya DIR] [--json PATH]
                                            [--scratch DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, ROOT)

TREES = ("templates",)


def plan(root=ROOT, only=None):
    """Every accepted node with both sources present, as work items.

    ``{type_name, template_dir, stage_dir, rounds_path, baseline_cpp,
    final_cpp, row, spec}``. A node missing either source is reported in
    ``skipped`` rather than silently dropped.
    """
    items, skipped = [], []
    want = set(only or [])
    for tree in TREES:
        pattern = os.path.join(root, tree, "*", "*", "build", "manifest.json")
        for mf in sorted(glob.glob(pattern)):
            build_dir    = os.path.dirname(mf)
            template_dir = os.path.dirname(build_dir)
            try:
                with open(mf, encoding="utf-8") as fh:
                    man = json.load(fh)
            except (OSError, ValueError):
                continue
            for row in man.get("nodes") or []:
                ty = row.get("type_name")
                if not ty or (want and ty not in want):
                    continue
                stage_dir   = os.path.join(build_dir, "stages", ty)
                rounds_path = os.path.join(stage_dir, "rounds.json")
                if not os.path.isfile(rounds_path):
                    continue
                try:
                    with open(rounds_path, encoding="utf-8") as fh:
                        rounds = json.load(fh)
                except (OSError, ValueError):
                    continue
                if not rounds.get("accepted"):
                    continue
                baseline_cpp = os.path.join(stage_dir, "3_optimized",
                                            "00_baseline.cpp")
                final_cpp = os.path.join(build_dir, ty, ty + ".cpp")
                missing = [p for p in (baseline_cpp, final_cpp)
                           if not os.path.isfile(p)]
                if missing:
                    skipped.append((ty, "missing %s" % ", ".join(
                        os.path.relpath(p, root) for p in missing)))
                    continue
                items.append({"type_name": ty, "template_dir": template_dir,
                              "stage_dir": stage_dir, "rounds_path": rounds_path,
                              "baseline_cpp": baseline_cpp, "final_cpp": final_cpp,
                              "row": row, "spec": row.get("spec") or {},
                              "old_speedup": rounds.get("speedup")})
    return items, skipped


def speedup_of(baseline_ms, final_ms):
    if not isinstance(baseline_ms, (int, float)) or not isinstance(final_ms, (int, float)):
        return None
    if final_ms <= 0:
        return None
    return baseline_ms / final_ms


def make_record(state, baseline_ms, final_ms, diverged, date=None):
    """The ``remeasured`` block. ``state`` is the adapters' ``bench_state_out``."""
    state = state or {}
    rec = {
        "date":        date or time.strftime("%Y-%m-%d"),
        "rung":        state.get("rung"),
        "floor_ms":    state.get("floor_ms"),
        "perturbed":   state.get("perturbed"),
        "fingerprint": state.get("fingerprint"),
        "baseline_ms": baseline_ms,
        "final_ms":    final_ms,
        "speedup":     speedup_of(baseline_ms, final_ms),
        "diverged":    diverged,
        "reason":      state.get("reason"),
    }
    return rec


def write_record(rounds_path, record):
    with open(rounds_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["remeasured"] = record
    with open(rounds_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")


def short(rec):
    """One phrase for the summary table."""
    if rec.get("diverged"):
        return "DIVERGED: %s" % rec["diverged"]
    if rec.get("baseline_ms") is None:
        return "unmeasurable: %s" % (rec.get("reason") or "?")
    if rec.get("final_ms") is None:
        return "final unmeasurable"
    return "%.3f -> %.3f ms = %.2fx" % (rec["baseline_ms"], rec["final_ms"],
                                       rec["speedup"] or 0.0)


def rebench_one(item, maya, scratch, log):
    """Compile both sources, measure both, return the ``remeasured`` record."""
    from mpynode.native.ai import optimizer_live, porter
    from mpynode.native.ai.optimizer import BenchmarkDiverged

    ty      = item["type_name"]
    spec    = item["spec"]
    work    = os.path.join(scratch, ty)
    plugins = {}
    for label, cpp in (("baseline", item["baseline_cpp"]),
                       ("final", item["final_cpp"])):
        out = os.path.join(work, label)
        os.makedirs(out, exist_ok=True)
        t0 = time.time()
        ok, clog, plugin = porter.compile_cpp(cpp, spec, out, maya=maya)
        log("[%s] compile %s: %s in %.0fs" % (ty, label, "ok" if ok else "FAILED",
                                            time.time() - t0))
        if not ok:
            tail = "\n".join((clog or "").strip().splitlines()[-8:])
            log(tail)
            state = {"reason": "%s source did not compile" % label}
            return make_record(state, None, None, None)
        plugins[label] = plugin

    state = {}
    ad = optimizer_live.make_adapters(
        spec, os.path.join(work, "bench"), maya=maya, node_type=ty,
        log_cb=log, bench_state_out=state)
    bench       = ad["benchmark_fn"]
    baseline_ms = bench(plugins["baseline"])       # calibrates + fingerprints
    if baseline_ms is None:
        return make_record(state, None, None, None)
    final_ms, diverged = None, None
    try:
        final_ms = bench(plugins["final"])
    except BenchmarkDiverged as exc:
        diverged = str(exc)
    return make_record(state, baseline_ms, final_ms, diverged)


def regen_report(item):
    from mpynode.native.toolchain import stage_report
    return stage_report.write_node_report(item["template_dir"], item["type_name"],
                                          row=item["row"], spec=item["spec"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only",    default="",          help="comma-separated type names")
    ap.add_argument("--dry-run", action="store_true", help="list the work, do nothing")
    ap.add_argument("--maya",    default=None,        help="Maya install root")
    ap.add_argument("--json",    default=None,        help="write the summary here")
    ap.add_argument("--scratch", default=None,
                    help="where plugins are built (default: a temp dir)")
    args = ap.parse_args(argv)

    only = [s for s in args.only.split(",") if s.strip()] or None
    items, skipped = plan(only=only)
    print("nodes to re-measure: %d%s" % (len(items), (
        "; skipped %d: %s" % (len(skipped), "; ".join("%s (%s)" % s for s in skipped))
        if skipped else "")))
    if args.dry_run:
        for it in items:
            print("  %-22s old %.2fx  %s" % (it["type_name"], it["old_speedup"] or 0,
                                             os.path.relpath(it["final_cpp"], ROOT)))
        return 0

    from mpynode.native.toolchain import toolchain
    maya    = args.maya or os.environ.get("MAYA_LOCATION") or toolchain.default_maya_dir()
    scratch = args.scratch or tempfile.mkdtemp(prefix="mpynode-rebench-")
    print("maya: %s\nscratch: %s" % (maya, scratch))

    def log(msg):
        print("  " + msg)
        sys.stdout.flush()

    summary = []
    for it in items:
        t0 = time.time()
        print("== %s (old %.2fx)" % (it["type_name"], it["old_speedup"] or 0))
        try:
            rec = rebench_one(it, maya, scratch, log)
        except Exception as exc:  # one node must not end the sweep
            rec = make_record({"reason": "rebench error: %r" % (exc,)}, None, None, None)
        write_record(it["rounds_path"], rec)
        try:
            regen_report(it)
        except Exception as exc:
            log("REPORT.md not regenerated: %r" % (exc,))
        rec_out = dict(rec, type_name=it["type_name"], old_speedup=it["old_speedup"],
                       seconds=round(time.time() - t0))
        summary.append(rec_out)
        print("   %s  (%ds)" % (short(rec), rec_out["seconds"]))
        sys.stdout.flush()

    print("\n%-22s %10s  %s" % ("node", "old", "re-measured"))
    for r in summary:
        print("%-22s %9.2fx  %s" % (r["type_name"], r["old_speedup"] or 0, short(r)))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"skipped": skipped, "nodes": summary}, fh, indent=2,
                      default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
