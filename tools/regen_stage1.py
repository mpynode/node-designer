"""Refresh EVERY checked-in ``build/stages/<type>/1_transpiled.cpp`` from the
current transpiler -- all template trees, not only the mega build.

Stage 1 is transpiler output -- ``codegen.generate_cpp(spec, for_port=True)``,
the exact call ``compile_controller`` makes for the ``1_transpiled`` artifact.
Every build's ``manifest.json`` embeds the FULL spec each node was keyed with,
so the artifacts can be re-derived from disk against today's transpiler with no
compiler, no linker, no bundle and no AI. ``tools/regen_mega_transpiled.py``
does this for the mega tree alone; a codegen change moves the per-template trees
too, and ``tests/compile/freshness/test_stage1_codegen_freshness`` gates all of
them byte for byte.

Only rewrites files that ALREADY exist. Refreshing stage 1 after a codegen
change also moves its emitter stamp away from the node's ``00_baseline`` --
``test_shipped_artifact_freshness`` then names the nodes whose shipped final
must be rebuilt (bump PORTER_RECIPE_VERSION, ``tools/build_compiled_templates``).

    mayapy tools/regen_stage1.py --dry-run      # report, write nothing
    mayapy tools/regen_stage1.py                # rewrite in place
    mayapy tools/regen_stage1.py --only sineRipple,nurbsWave

Run under ``PYTHONHASHSEED=0`` (see ``check_stage1_freshness``).
"""

import argparse
import json
import os
import sys

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREES      = ("templates",)
STAGE_FILE = "1_transpiled.cpp"


def manifests():
    out = []
    for tree in TREES:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, tree)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if "manifest.json" in filenames:
                out.append(os.path.join(dirpath, "manifest.json"))
    return sorted(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="comma-separated type names")
    args = ap.parse_args(argv)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import maya.standalone

    maya.standalone.initialize(name="python")
    import maya.cmds as mc

    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p)

    from mpynode.native import compiler as codegen

    changed, same, missing, failed = [], [], [], []
    for mf in manifests():
        try:
            with open(mf, encoding="utf-8") as fh:
                man = json.load(fh)
        except (OSError, ValueError) as exc:
            failed.append((mf, "manifest: %s" % exc))
            continue
        build = os.path.dirname(mf)
        label = os.path.relpath(build, ROOT).replace(os.sep, "/")
        for row in man.get("nodes") or []:
            ty   = row.get("type_name")
            spec = row.get("spec")
            if not ty or not isinstance(spec, dict) or (only and ty not in only):
                continue
            dst = os.path.join(build, "stages", ty, STAGE_FILE)
            tag = "%s:%s" % (label, ty)
            if not os.path.isfile(dst):
                missing.append(tag)
                continue
            try:
                cpp = codegen.generate_cpp(spec, for_port=True)
            except Exception as exc:
                failed.append((tag, "%s: %s" % (type(exc).__name__, exc)))
                continue
            with open(dst, encoding="utf-8", newline="") as fh:
                old = fh.read()
            if old == cpp:
                same.append(tag)
                continue
            changed.append(tag)
            if not args.dry_run:
                with open(dst, "w", encoding="utf-8", newline="") as fh:
                    fh.write(cpp)

    print("=" * 70)
    print("stage-1 regen, all trees   %s" % ("(DRY RUN)" if args.dry_run else "(WROTE)"))
    print("=" * 70)
    print("changed : %d" % len(changed))
    for t in changed:
        print("    " + t)
    print("same    : %d" % len(same))
    print("no stage-1 artifact on disk (skipped): %d" % len(missing))
    for tn, why in failed:
        print("FAILED  : %-40s %s" % (tn, why))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
