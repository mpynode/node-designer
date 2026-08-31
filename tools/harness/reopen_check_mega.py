"""Clean-reopen verification for MEGA-built demos: open a saved .ma in a FRESH
mayapy and confirm the compiled node type loads from the mega bundle and the
scene evaluates.

Same as ``reopen_check.py`` except the compiled type is passed in (there is no
per-template manifest -- every type lives in the one mega bundle).

Usage (under mayapy, with MAYA_PLUG_IN_PATH including the mega dir):
    reopen_check_mega.py <ma_path> <compiled_type>

Prints a single 'REOPEN_JSON:' line.
"""
import sys
import json
import traceback

MA = sys.argv[1]
CTYPE = sys.argv[2]

res = {"ma": MA, "reopened": False, "compiled_type": CTYPE,
       "compiled_nodes": 0, "mesh_verts": 0, "unknown_nodes": 0,
       "unknown_plugins": [], "errors": []}

try:
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc
    for p in ("mpynode_api1", "mpynode_api2"):
        try:
            mc.loadPlugin(p, quiet=True)
        except Exception:
            pass

    mc.file(MA, open=True, force=True)
    res["reopened"] = True

    if CTYPE:
        res["compiled_nodes"] = len(mc.ls(type=CTYPE) or [])
    res["unknown_nodes"] = len(mc.ls(type="unknown") or [])
    try:
        res["unknown_plugins"] = list(mc.unknownPlugin(q=True, list=True) or [])
    except Exception:
        pass

    import maya.api.OpenMaya as om
    tot = 0
    for s in (mc.ls(type="mesh") or []):
        try:
            mc.dgeval(s + ".outMesh")
            sl = om.MSelectionList()
            sl.add(s)
            tot += om.MFnMesh(sl.getDagPath(0)).numVertices
        except Exception:
            pass
    res["mesh_verts"] = tot

except Exception as exc:
    res["errors"].append("REOPEN EXCEPTION: %r" % exc)
    sys.stderr.write(traceback.format_exc())
finally:
    print("REOPEN_JSON:" + json.dumps(res))
    try:
        import maya.standalone
        maya.standalone.uninitialize()
    except Exception:
        pass
    ok = res["reopened"] and res["unknown_nodes"] == 0 and \
        (res["compiled_nodes"] > 0)
    sys.exit(0 if ok else 1)
