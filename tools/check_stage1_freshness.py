"""Diff every checked-in stage-1 C++ artifact against FRESH transpiler output.

Stage 1 is pure transpiler output -- ``codegen.generate_cpp(spec, for_port=True)``,
the exact call ``compile_controller`` makes for the ``1_transpiled`` artifact
(``compile_controller.py:783``). Every build directory's ``manifest.json`` embeds
the FULL spec each node was keyed with, so the artifacts can be re-derived from
disk against TODAY's transpiler without re-running a build: no compiler, no
linker, no bundle, no AI.

This is the measurement half of the T87 gate. The gate itself lives in
``tests.compile.freshness.test_stage1_codegen_freshness``, which runs this script in a
subprocess with ``PYTHONHASHSEED=0`` (see T69: codegen order is only reproducible
under a pinned seed) and compares the result against a checked-in baseline of
known-stale artifacts.

    mayapy tools/check_stage1_freshness.py                   # human report
    mayapy tools/check_stage1_freshness.py --json out.json   # machine readable
    mayapy tools/check_stage1_freshness.py --write-baseline  # re-record the list

Run it under ``PYTHONHASHSEED=0``; the gate does that for you.
"""

import difflib
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Every tree that ships stage-1 artifacts. `_snapshots` is deliberately absent:
# snapshots are frozen copies and must never be gated.
TREES      = ("templates",)
STAGE_FILE = "1_transpiled.cpp"
BASELINE   = os.path.join(ROOT, "tests", "data", "stage1_stale_baseline.json")


def _rel(path):
    """Repo-relative path in the canonical ``/`` form.

    These strings are the keys the checked-in baseline is compared against, and
    that baseline is shared across platforms -- so they must not carry
    ``os.sep``. A no-op on POSIX; on Windows it stops every path looking like a
    fresh artifact the baseline has never heard of.
    """
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def _manifests():
    """Every build ``manifest.json`` that carries per-node specs."""
    out = []
    for tree in TREES:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, tree)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if "manifest.json" not in filenames:
                continue
            path = os.path.join(dirpath, "manifest.json")
            try:
                with open(path, encoding="utf-8") as fh:
                    man = json.load(fh)
            except (OSError, ValueError):
                continue
            if isinstance(man.get("nodes"), list):
                out.append((path, man))
    out.sort()
    return out


def _diff_detail(old, new):
    """Bounded, human-usable summary of HOW the artifact drifted."""
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    first     = None
    for i, (a, b) in enumerate(zip(old_lines, new_lines)):
        if a != b:
            first = i + 1
            break
    if first is None and len(old_lines) != len(new_lines):
        first = min(len(old_lines), len(new_lines)) + 1
    excerpt = list(difflib.unified_diff(
        old_lines, new_lines, "shipped", "fresh", n=1, lineterm=""))
    return {"first_diff_line": first,
            "shipped_lines": len(old_lines),
            "fresh_lines":   len(new_lines),
            "excerpt": excerpt[:12]}


def collect():
    """{'artifacts': {relpath: row}, 'absent': [...], 'manifests': [...]}."""
    from mpynode.native import compiler as codegen

    artifacts = {}
    absent    = []
    manifests = []
    for man_path, man in _manifests():
        man_rel = _rel(man_path)
        manifests.append(man_rel)
        stages = os.path.join(os.path.dirname(man_path), "stages")
        for row in man.get("nodes") or []:
            type_name = row.get("type_name")
            spec      = row.get("spec")
            if not type_name or not isinstance(spec, dict):
                continue
            art     = os.path.join(stages, type_name, STAGE_FILE)
            art_rel = _rel(art)
            if not os.path.isfile(art):
                # A node the build dropped before stage 1 never wrote one.
                absent.append(art_rel)
                continue
            entry = {"type_name": type_name, "manifest": man_rel}
            try:
                fresh = codegen.generate_cpp(spec, for_port=True)
            except Exception as exc:
                entry["state"]     = "error"
                entry["detail"]    = "%s: %s" % (type(exc).__name__, exc)
                artifacts[art_rel] = entry
                continue
            entry["fresh_sha"] = hashlib.sha256(
                fresh.encode("utf-8")).hexdigest()[:16]
            with open(art, encoding="utf-8") as fh:
                shipped = fh.read()
            if shipped == fresh:
                entry["state"] = "fresh"
            else:
                entry["state"]  = "stale"
                entry["detail"] = _diff_detail(shipped, fresh)
            artifacts[art_rel] = entry
    # Artifacts on disk that no manifest row claims. They are UNGATED: nothing
    # can re-derive them, so drift in one is invisible. Reported, not ignored.
    # Walked from the TREES, never from `manifests` (T109): deriving the search
    # from the manifests that PARSED made a build tree whose manifest.json is
    # missing, unreadable or nodes-less contribute no artifacts to compare AND
    # no artifacts here -- a clean "0 ungated" over exactly the hole this looks
    # for.
    unmatched = []
    for tree in TREES:
        pattern = os.path.join(ROOT, tree, "**", "stages", "*", STAGE_FILE)
        for art in glob.glob(pattern, recursive=True):
            art_rel = _rel(art)
            if art_rel not in artifacts:
                unmatched.append(art_rel)
    return {"root": ROOT,
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
            "manifests":      manifests,
            "unmatched":      sorted(unmatched),
            "absent":         sorted(absent),
            "artifacts": artifacts}


def _report(result):
    by_state = {}
    for rel, row in sorted(result["artifacts"].items()):
        by_state.setdefault(row["state"], []).append(rel)
    print("=" * 70)
    print("stage-1 artifact freshness   PYTHONHASHSEED=%s"
          % (result["pythonhashseed"],))
    print("=" * 70)
    print("manifests : %d" % len(result["manifests"]))
    print("checked   : %d" % len(result["artifacts"]))
    for state in ("fresh", "stale", "error"):
        names = by_state.get(state) or []
        print("%-9s : %d" % (state, len(names)))
        for rel in names:
            if state == "fresh":
                continue
            row    = result["artifacts"][rel]
            detail = row.get("detail")
            if isinstance(detail, dict):
                detail = "first diff at line %s (%s -> %s lines)" % (
                    detail["first_diff_line"], detail["shipped_lines"],
                    detail["fresh_lines"])
            print("    %-70s %s" % (rel, detail))
    print("no stage-1 artifact on disk (skipped): %d" % len(result["absent"]))
    print("UNGATED (artifact on disk, no manifest row): %d" % len(result["unmatched"]))
    for rel in result["unmatched"]:
        print("    %s" % rel)


def _write_baseline(result):
    """Re-record the known-stale set, keeping the file's own explainer.

    The ONLY sanctioned way to widen the gate's exemption list, and it leaves a
    reviewable diff naming every artifact that newly rotted. The test never
    calls this -- a gate that repairs its own baseline is not a gate.
    """
    with open(BASELINE, encoding="utf-8") as fh:
        doc = json.load(fh)
    was = set(doc.get("stale") or [])
    now = sorted(rel for rel, row in result["artifacts"].items()
                 if row["state"] == "stale")
    doc["stale"] = now
    with open(BASELINE, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    print("baseline: %d -> %d  (+%d newly stale, -%d refreshed)"
          % (len(was), len(now), len(set(now) - was), len(was - set(now))))
    for rel in sorted(set(now) - was):
        print("    + %s" % rel)
    for rel in sorted(was - set(now)):
        print("    - %s" % rel)


def main():
    argv     = sys.argv[1:]
    json_out = None
    if "--json" in argv:
        json_out = argv[argv.index("--json") + 1]

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import maya.standalone

    maya.standalone.initialize(name="python")
    import maya.cmds as mc

    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p)

    result = collect()
    if json_out:
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, sort_keys=True)
    else:
        _report(result)
    if "--write-baseline" in argv:
        _write_baseline(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
