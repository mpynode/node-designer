"""Refresh the embedded @maya_command payload in every shipped C++ artifact,
without rebuilding the node.

A compiled node's commands run as Python embedded in its C++: the
``kPayloadB64`` array (``command_dispatch.python_module_source``). A change that
moves only that module -- its prelude, its runtime, or which Methods code it
carries -- leaves every other byte of the generated C++ alone, but the pipeline
can only ship it through a rebuild, which re-ports and re-optimizes the node
(nondeterministic, and hours across the tree). This does the payload alone.

For each manifest row whose stage 1 carries a payload, it generates stage 1
fresh (``codegen.generate_cpp(spec, for_port=True)``, the pipeline's own call)
and REFUSES the row unless the fresh text equals the shipped one outside the
payload array and the build hash -- a node with any other pending codegen
change needs a real rebuild. Otherwise it writes the fresh stage 1, and puts the
fresh array into every other file of that node in that build tree:
``stages/<type>/**/*.cpp`` (``00_baseline``, optimizer rounds, a
``2_assisted``), ``<type>/<type>.cpp`` and ``source/<type>.cpp``. A file that
carried stage 1's old hash gets the new one; a file stamped from some OTHER
stage 1 keeps its stamp and is reported, since the code around its payload
came from that older stage 1 and restamping it would hide exactly what
``test_shipped_artifact_freshness`` looks for. Each written file is decoded
back and checked. A payload array it cannot read (a CRLF working copy) is
refused, never skipped.

    PYTHONHASHSEED=0 mayapy tools/swap_command_payload.py            # report
    PYTHONHASHSEED=0 mayapy tools/swap_command_payload.py --apply
    PYTHONHASHSEED=0 mayapy tools/swap_command_payload.py --only spine,mPyDnet
"""

import argparse
import base64
import glob
import json
import os
import re
import sys

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREES = ("templates",)

ARRAY = re.compile(r"(static const char kPayloadB64\[\] = \{\n)(.*?)(\n\s*0\n\};)", re.S)
STAMP = re.compile(r"// build: ([0-9a-f]{12})|\+([0-9a-f]{12})\"")


def _payload(text):
    """``(match, decoded module)`` of the one payload array, or (None, None)."""
    found = list(ARRAY.finditer(text))
    if len(found) != 1:
        return None, None
    m = found[0]
    return m, base64.b64decode(
        "".join(re.findall(r"'([A-Za-z0-9+/=])'", m.group(2)))).decode("utf-8")


def _stamps(text):
    return {a or b for a, b in STAMP.findall(text)}


def _lineage(build, ty):
    """Every .cpp of ``ty`` in one build tree, stage 1 excluded."""
    out = glob.glob(os.path.join(build, "stages", ty, "**", "*.cpp"), recursive=True)
    out = [p for p in out if os.path.basename(p) != "1_transpiled.cpp"]
    for p in (os.path.join(build, ty, ty + ".cpp"),
              os.path.join(build, "source", ty + ".cpp")):
        if os.path.isfile(p):
            out.append(p)
    return sorted(out)


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true")
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

    swapped, refused, files, skipped, foreign = [], [], 0, [], []
    for tree in TREES:
        for man_path in sorted(glob.glob(os.path.join(ROOT, tree, "**", "manifest.json"),
                                         recursive=True)):
            build = os.path.dirname(man_path)
            label = os.path.relpath(build, ROOT).replace(os.sep, "/")
            with open(man_path, encoding="utf-8") as fh:
                rows = json.load(fh).get("nodes") or []
            for row in rows:
                ty, spec = row.get("type_name"), row.get("spec")
                if not ty or not isinstance(spec, dict) or (only and ty not in only):
                    continue
                stage1 = os.path.join(build, "stages", ty, "1_transpiled.cpp")
                if not os.path.isfile(stage1):
                    continue
                shipped = _read(stage1)
                ms, _smod = _payload(shipped)
                tag = "%s:%s" % (label, ty)
                if ms is None:
                    if "kPayloadB64" in shipped:
                        refused.append((tag, "payload array unreadable (CRLF?)"))
                    continue
                fresh = codegen.generate_cpp(spec, for_port=True)
                mf, fmod = _payload(fresh)
                old_h, new_h = _stamps(shipped), _stamps(fresh)
                if mf is None or len(old_h) != 1 or len(new_h) != 1:
                    refused.append((tag, "no single payload / stamp in stage 1"))
                    continue
                old_h, new_h = old_h.pop(), new_h.pop()
                if (ARRAY.sub("<P>", shipped).replace(old_h, "<H>")
                        != ARRAY.sub("<P>", fresh).replace(new_h, "<H>")):
                    refused.append((tag, "stage 1 moves outside the payload: rebuild"))
                    continue
                body       = mf.group(2)
                plan       = [(stage1, fresh)]
                unreadable = []
                for path in _lineage(build, ty):
                    text = _read(path)
                    m, _mod = _payload(text)
                    if m is None:
                        (unreadable if "kPayloadB64" in text else skipped).append(
                            os.path.relpath(path, ROOT))
                        continue
                    out = text[:m.start(2)] + body + text[m.end(2):]
                    out = out.replace(old_h, new_h)
                    for h in sorted(_stamps(text) - {old_h, new_h}):
                        foreign.append("%s keeps %s (stage 1 was %s)"
                                       % (os.path.relpath(path, ROOT), h, old_h))
                    plan.append((path, out))
                if unreadable:
                    refused.append((tag, "payload array unreadable (CRLF?) in "
                                    + ", ".join(unreadable)))
                    continue
                for path, out in plan:
                    _m, mod = _payload(out)
                    if mod != fmod or (old_h != new_h and old_h in _stamps(out)):
                        raise SystemExit("self-check failed on %s" % path)
                changed = [p for p, out in plan if _read(p) != out]
                files += len(changed)
                swapped.append((tag, old_h, new_h, len(changed), len(plan)))
                if args.apply:
                    for path, out in plan:
                        if _read(path) != out:
                            _write(path, out)

    print("=" * 70)
    print("command payload swap   %s" % ("(WROTE)" if args.apply else "(DRY RUN)"))
    print("=" * 70)
    for tag, old_h, new_h, n, total in swapped:
        print("  %-52s %s -> %s  %d/%d file(s)" % (tag, old_h, new_h, n, total))
    print("nodes: %d | files changed: %d" % (len(swapped), files))
    for p in skipped:
        print("  no payload, left alone: %s" % p)
    for line in foreign:
        print("  stamped from another stage 1, stamp kept: %s" % line)
    for tag, why in refused:
        print("REFUSED %-50s %s" % (tag, why))
    return 1 if refused else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        import maya.standalone

        maya.standalone.uninitialize()
    except Exception:
        pass
    os._exit(code)
