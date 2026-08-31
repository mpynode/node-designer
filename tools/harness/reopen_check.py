"""Clean-reopen verification: open a saved compiled-demo .ma in a FRESH mayapy
(with the demo folder on MAYA_PLUG_IN_PATH) and confirm the compiled node type
loads and the scene evaluates.

It also COMPARES the reopened compiled scene's mesh vertex count against the
INTERPRETED demo's. ``mesh_verts`` on its own was a number with nothing to
measure it against: a compiled node that reopened cleanly and produced the WRONG
amount of geometry -- or none -- read exactly like one that produced the right
amount. The interpreted reference is rebuilt here, in this same process, from the
template .mpn that ``templates.json`` maps this out_dir's folder to, running the
same demo the .ma was built from (``deserialize_node`` + ``run_node_demo``, the
same two calls build_demo_compiled.py uses before it swaps in the compiled node).

The comparison DEGRADES rather than lies: if the reference cannot be rebuilt the
result says ``verts_compared: false`` with a reason, and the pass/fail verdict is
unchanged from before. Only a comparison that actually RAN can fail the check.
Set MPYNODE_REOPEN_INTERP=0 to skip it -- the rebuild re-runs the demo, and
run_all.py caps this step at 600s.

Usage (under mayapy, with MAYA_PLUG_IN_PATH including <out_dir>):
    reopen_check.py <out_dir> <ma_path>

Prints a single 'REOPEN_JSON:' line.
"""
import os
import sys
import json
import time
import traceback

OUT = sys.argv[1]
MA = sys.argv[2]

HARNESS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.dirname(
    os.path.dirname(HARNESS))
WANT_INTERP = os.environ.get("MPYNODE_REOPEN_INTERP", "1").strip().lower() \
    not in ("", "0", "false", "no", "off")

res = {"ma": MA, "reopened": False, "compiled_type": None,
       "compiled_nodes": 0, "mesh_verts": 0, "unknown_nodes": 0,
       "interp_mesh_verts": None, "verts_compared": False,
       "verts_match": None, "verts_delta": None, "interp_reason": None,
       "interp_seconds": None, "errors": []}


def _mesh_verts(mc, om):
    """Total vertices across every evaluated mesh in the CURRENT scene."""
    tot = 0
    for s in (mc.ls(type="mesh") or []):
        try:
            mc.dgeval(s + ".outMesh")
            sl = om.MSelectionList()
            sl.add(s)
            tot += om.MFnMesh(sl.getDagPath(0)).numVertices
        except Exception:
            pass
    return tot


def _template_for(out_dir):
    """(mpn_path, folder) for this out_dir, from the harness manifest."""
    folder = os.path.basename(os.path.normpath(out_dir))
    with open(os.path.join(HARNESS, "templates.json")) as fh:
        rows = json.load(fh)
    for row in rows:
        if row.get("folder") == folder:
            return os.path.join(ROOT, row["mpn"]), folder
    raise KeyError("no templates.json row for folder %r" % folder)


def _demo_for(ma_path, folder):
    """The demo the .ma was built from.

    build_demo_compiled.py names a multi-demo scene ``<folder>__<func_name>``
    and a single-demo one just ``<folder>``; None selects the first demo, which
    is exactly what the single-demo case means.
    """
    base = os.path.splitext(os.path.basename(ma_path))[0]
    prefix = folder + "__"
    return base[len(prefix):] if base.startswith(prefix) else None


def _interpreted_verts(mc, om):
    """Rebuild the demo INTERPRETED and count its vertices."""
    from mpynode._common.io import mpn_io
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.methods.methods_registry import run_node_demo

    mpn, folder = _template_for(OUT)
    demo = _demo_for(MA, folder)
    mc.file(new=True, force=True)
    node = deserialize_node(mpn_io.load_mpn(mpn, trusted=True),
                            restore_persistent=False)
    run_node_demo(node, demo)
    return _mesh_verts(mc, om)


try:
    manifest = json.load(open(os.path.join(OUT, "build", "manifest.json")))
    nodes = manifest.get("nodes") or []
    ctype = nodes[0].get("type_name") if nodes else None
    res["compiled_type"] = ctype

    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc
    for p in ("mpynode_api1", "mpynode_api2"):
        try:
            mc.loadPlugin(p, quiet=True)
        except Exception:
            pass

    import maya.api.OpenMaya as om

    # INTERPRETED reference FIRST: opening the compiled .ma replaces the scene.
    # Never allowed to fail the check -- a reference we could not build is a gap
    # in the evidence, not a defect in the node.
    if not WANT_INTERP:
        res["interp_reason"] = "disabled by MPYNODE_REOPEN_INTERP=0"
    else:
        _t0 = time.time()
        try:
            res["interp_mesh_verts"] = _interpreted_verts(mc, om)
        except Exception as exc:
            res["interp_reason"] = "interpreted rebuild failed: %r" % exc
        finally:
            res["interp_seconds"] = round(time.time() - _t0, 1)

    mc.file(MA, open=True, force=True)
    res["reopened"] = True

    if ctype:
        res["compiled_nodes"] = len(mc.ls(type=ctype) or [])
    # unknown nodes = a plugin failed to load on open
    res["unknown_nodes"] = len(mc.ls(type="unknown") or [])

    res["mesh_verts"] = _mesh_verts(mc, om)

    if res["interp_mesh_verts"] is not None:
        res["verts_compared"] = True
        res["verts_delta"] = res["mesh_verts"] - res["interp_mesh_verts"]
        res["verts_match"] = (res["verts_delta"] == 0)
        if not res["verts_match"]:
            res["errors"].append(
                "VERTEX COUNT MISMATCH: compiled %d vs interpreted %d "
                "(delta %+d) -- the compiled node reopened cleanly and built "
                "different geometry"
                % (res["mesh_verts"], res["interp_mesh_verts"],
                   res["verts_delta"]))

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
        (res["compiled_nodes"] > 0) and res["verts_match"] is not False
    sys.exit(0 if ok else 1)
