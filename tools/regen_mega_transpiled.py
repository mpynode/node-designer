"""Refresh templates/All Templates Plugin/build/stages/<type>/1_transpiled.cpp.

Stage 1 is TRANSPILER output -- ``codegen.generate_cpp(spec, for_port=True)``,
the exact call ``porter.port_node`` / ``compile_controller`` make for the
``1_transpiled`` artifact. No compiler is invoked, nothing is linked, no
``.bundle`` is produced: this is codegen only.

The mega build's ``manifest.json`` embeds the FULL spec every node was keyed
with, so the checked-in stage-1 artifacts can be re-derived from disk against
the current transpiler WITHOUT re-running the (expensive, AI-in-the-loop) mega
build. That is what keeps them honest after a transpiler / nd_runtime change --
e.g. the NaN-asymmetric ``nd::maximum_elem`` / ``minimum_elem`` fix, which the
older artifacts predate (they still show a bare ``a > b ? a : b``).

Only rewrites files that ALREADY exist -- a node the build dropped before
stage 1 (procrustesTags) stays absent.

    mayapy tools/regen_mega_transpiled.py --dry-run   # report, write nothing
    mayapy tools/regen_mega_transpiled.py             # rewrite in place
"""

import json
import os
import sys

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEGA     = os.path.join(ROOT, "templates", "All Templates Plugin", "build")
MANIFEST = os.path.join(MEGA, "manifest.json")
STAGES   = os.path.join(MEGA, "stages")


def _stage_path(type_name):
    return os.path.join(STAGES, type_name, "1_transpiled.cpp")


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    out_dir = None
    for i, a in enumerate(sys.argv[1:]):
        if a == "--out" and i + 2 <= len(sys.argv[1:]):
            out_dir = sys.argv[i + 2]

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import maya.standalone

    maya.standalone.initialize(name="python")
    import maya.cmds as mc

    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p)

    from mpynode.native import compiler as codegen

    with open(MANIFEST) as fh:
        man = json.load(fh)

    changed, same, missing, failed = [], [], [], []
    for row in man.get("nodes") or []:
        type_name = row.get("type_name")
        spec      = row.get("spec")
        if not type_name or not isinstance(spec, dict):
            continue
        dst = _stage_path(type_name)
        if not os.path.isfile(dst):
            missing.append(type_name)
            continue
        try:
            cpp = codegen.generate_cpp(spec, for_port=True)
        except Exception as exc:
            failed.append((type_name, "%s: %s" % (type(exc).__name__, exc)))
            continue
        with open(dst) as fh:
            old = fh.read()
        if old == cpp:
            same.append(type_name)
            continue
        changed.append(type_name)
        if dry_run:
            continue
        target = dst
        if out_dir:
            target = os.path.join(out_dir, type_name, "1_transpiled.cpp")
            os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as fh:
            fh.write(cpp)

    print("=" * 70)
    print("mega stage-1 regen   %s" % ("(DRY RUN)" if dry_run else "(WROTE)"))
    print("=" * 70)
    print("changed : %d  %s" % (len(changed), " ".join(sorted(changed))))
    print("same    : %d  %s" % (len(same), " ".join(sorted(same))))
    print("no stage-1 artifact on disk (skipped): %s" % (sorted(missing) or "-"))
    for tn, why in failed:
        print("FAILED  : %-24s %s" % (tn, why))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
