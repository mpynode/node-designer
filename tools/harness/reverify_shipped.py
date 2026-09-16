"""Re-verify every shipped compiled node and make its manifest say what is true.

The shipped ``manifest.json`` files record the parity verdict of the build that
produced them. On 2026-09-08, 13 of 38 said "verify could not run" -- the
build-time verify process could not create its interpreted reference -- and a
re-run in a working environment passed 14 of them outright. The verdict was a
property of the environment, not of the node. This tool re-runs the SAME verify
the build runs (generic parity + authored ``@maya_test``, in a throwaway mayapy
via ``verify.subprocess_verify_fn``) against a fresh compile of each node's
shipped final ``.cpp``, and rewrites only the node's ``verify`` block (plus a
``reverified`` date), then regenerates its REPORT.md.

    mayapy tools/harness/reverify_shipped.py [--only a,b] [--dry-run]
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
    """Every shipped node with a final ``build/<Type>/<Type>.cpp``, as work
    items ``{type_name, template_dir, manifest_path, row_index, final_cpp,
    spec, row, old_verify}``; nodes missing the source go to ``skipped``."""
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
            for idx, row in enumerate(man.get("nodes") or []):
                ty = row.get("type_name")
                if not ty or (want and ty not in want):
                    continue
                final_cpp = os.path.join(build_dir, ty, ty + ".cpp")
                if not os.path.isfile(final_cpp):
                    skipped.append((ty, "missing %s" % os.path.relpath(final_cpp, root)))
                    continue
                items.append({"type_name": ty, "template_dir": template_dir,
                              "manifest_path": mf, "row_index": idx,
                              "final_cpp": final_cpp, "spec": row.get("spec") or {},
                              "row": row, "old_verify": dict(row.get("verify") or {})})
    return items, skipped


def dump_manifest(path, doc):
    """Write the manifest the way the build wrote it: 2-space indent, insertion
    order, trailing newline, LF -- so the only diff is the block that changed."""
    text = json.dumps(doc, indent=2) + "\n"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def finish_block(block, ran_generic=None, date=None):
    """Make a verify block self-describing: ``generic_ran`` (what the merge
    records when an authored test ran; otherwise the generic run itself) and a
    ``reverified`` date."""
    block = dict(block or {})
    if "generic_ran" not in block:
        block["generic_ran"] = bool(block.get("ran")) if ran_generic is None \
            else bool(ran_generic)
    block["reverified"] = date or time.strftime("%Y-%m-%d")
    return block


def write_block(item, block):
    with open(item["manifest_path"], encoding="utf-8") as fh:
        doc = json.load(fh)
    doc["nodes"][item["row_index"]]["verify"] = block
    dump_manifest(item["manifest_path"], doc)


def regen_report(item, block):
    from mpynode.native.toolchain import stage_report

    row = dict(item["row"], verify=block)
    return stage_report.write_node_report(item["template_dir"], item["type_name"],
                                          row=row, spec=item["spec"])


def gate_of(block):
    from mpynode.native.ai.optimizer_live import parity_gate_label

    return parity_gate_label(block)


def short(block):
    if not block.get("ran"):
        return "SKIP  %s" % (block.get("reason") or "")[:90]
    me = block.get("maxerr")
    me = ("%.2e" % me) if isinstance(me, (int, float)) else "-"
    return "%s  maxerr=%s tol=%s  %s" % ("PASS" if block.get("pass") else "FAIL",
                                         me, block.get("tol"),
                                         (block.get("reason") or "")[:70])


def reverify_one(item, maya, scratch, verify_fn, log):
    """Compile the shipped final, run the pipeline's verify on it, return the
    finished ``verify`` block. Never raises."""
    from mpynode.native.ai import porter

    ty  = item["type_name"]
    out = os.path.join(scratch, ty)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    try:
        ok, clog, plugin = porter.compile_cpp(item["final_cpp"], item["spec"], out,
                                              maya=maya)
    except Exception as exc:
        ok, clog, plugin = False, "compile raised: %r" % (exc,), None
    log("[%s] compile: %s in %.0fs" % (ty, "ok" if ok else "FAILED", time.time() - t0))
    if not ok:
        tail = "\n".join((clog or "").strip().splitlines()[-4:])
        return finish_block({"ran": False, "pass": None, "maxerr": None, "tol": None,
                             "reason": "shipped final did not compile: %s" % tail})
    t0 = time.time()
    try:
        res = verify_fn(plugin, [{"type_name": ty, "spec": item["spec"]}]) or {}
    except Exception as exc:
        res = {}
        log("[%s] verify raised: %r" % (ty, exc))
    block = res.get(ty) or {"ran": False, "pass": None, "maxerr": None, "tol": None,
                            "reason": "subprocess verify produced no result"}
    log("[%s] verify in %.0fs: %s" % (ty, time.time() - t0, short(block)))
    return finish_block(block)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", default="", help="comma-separated type names")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--maya",    default=None)
    ap.add_argument("--json",    default=None)
    ap.add_argument("--scratch", default=None)
    args = ap.parse_args(argv)

    only = [s for s in args.only.split(",") if s.strip()] or None
    items, skipped = plan(only=only)
    print("nodes to re-verify: %d%s" % (len(items), (
        "; skipped %d: %s" % (len(skipped), "; ".join("%s (%s)" % s for s in skipped))
        if skipped else "")))
    if args.dry_run:
        for it in items:
            ov = it["old_verify"]
            print("  %-22s old: ran=%-5s pass=%-5s %s" % (
                it["type_name"], ov.get("ran"), ov.get("pass"),
                (ov.get("reason") or "")[:70]))
        return 0

    from mpynode.native.toolchain import toolchain, verify
    maya      = args.maya or os.environ.get("MAYA_LOCATION") or toolchain.default_maya_dir()
    scratch   = args.scratch or tempfile.mkdtemp(prefix="mpynode-reverify-")
    verify_fn = verify.subprocess_verify_fn(maya=maya, timeout=900)
    print("maya: %s\nscratch: %s" % (maya, scratch))

    def log(msg):
        print("  " + msg)
        sys.stdout.flush()

    summary = []
    for it in items:
        t0 = time.time()
        print("== %s" % it["type_name"])
        block = reverify_one(it, maya, scratch, verify_fn, log)
        write_block(it, block)
        try:
            regen_report(it, block)
        except Exception as exc:
            log("REPORT.md not regenerated: %r" % (exc,))
        summary.append({"type_name": it["type_name"], "old": it["old_verify"],
                        "new": block, "gate": gate_of(block),
                        "seconds": round(time.time() - t0)})
        sys.stdout.flush()

    print("\n%-22s %-6s %-20s %s" % ("node", "old", "gate", "re-verified"))
    for r in summary:
        o   = r["old"]
        old = ("PASS" if o.get("pass") else "FAIL") if o.get("ran") else "SKIP"
        if "could not run" in (o.get("reason") or ""):
            old = "ERR"
        print("%-22s %-6s %-20s %s" % (r["type_name"], old, r["gate"], short(r["new"])))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"skipped": skipped, "nodes": summary}, fh, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
