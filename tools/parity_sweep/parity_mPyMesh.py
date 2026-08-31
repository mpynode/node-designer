import os, sys, math

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(ROOT, "plug-ins"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds
import maya.api.OpenMaya as om

for p in ("mpynode_api1", "mpynode_api2"):
    if not cmds.pluginInfo(p, q=True, loaded=True):
        cmds.loadPlugin(p, quiet=True)

NATIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyMesh")
ORIGINAL_MA = os.path.join(NATIVE_DIR, "mPyMesh_gridMesh_original.ma")
BUNDLE = os.path.join(NATIVE_DIR, "gridMesh.bundle")
NODE_TYPE = "gridMesh"
SOURCE = "gridMeshSrc"
TOL = 1e-4


def get_mesh_points(node):
    """Read outMesh plug -> MObject -> MFnMesh.getPoints(kObject)."""
    sel = om.MSelectionList()
    sel.add(node)
    dep = om.MFnDependencyNode(sel.getDependNode(0))
    plug = dep.findPlug("outMesh", False)
    mesh_obj = plug.asMObject()  # forces eval
    fn = om.MFnMesh(mesh_obj)
    pts = fn.getPoints(om.MSpace.kObject)
    return fn.numVertices, fn.numPolygons, pts


def main():
    result = {"error": None}

    # 1) Load the original python scene (creates gridMeshSrc).
    if not os.path.isfile(ORIGINAL_MA):
        print("RESULT error original_ma_missing")
        return
    cmds.file(ORIGINAL_MA, open=True, force=True)

    if not cmds.objExists(SOURCE):
        print("RESULT error python_ref_missing", SOURCE)
        return
    print("PYREF built:", SOURCE, "type:", cmds.nodeType(SOURCE))

    # 2) Load the EXISTING bundle (do NOT rebuild).
    if not os.path.isfile(BUNDLE):
        print("RESULT error bundle_missing")
        return
    bname = os.path.basename(BUNDLE)
    if not cmds.pluginInfo(bname, q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    comp = cmds.createNode(NODE_TYPE)  # capture unique name
    print("NATIVE built:", comp, "type:", cmds.nodeType(comp))

    # 3) Sweep 8 phase values.
    phases = [i * 6.0 / 7.0 for i in range(8)]  # linspace 0..6, 8 pts
    maxerr = 0.0
    n_components = 0
    n_samples = 0
    py_nv = py_np = nat_nv = nat_np = None

    for ph in phases:
        cmds.setAttr(SOURCE + ".phase", ph)
        cmds.setAttr(comp + ".phase", ph)

        py_nv, py_np, py_pts = get_mesh_points(SOURCE)
        nat_nv, nat_np, nat_pts = get_mesh_points(comp)

        assert py_nv == nat_nv, "vertex count mismatch %d != %d at phase %f" % (py_nv, nat_nv, ph)
        assert py_np == nat_np, "polygon count mismatch %d != %d at phase %f" % (py_np, nat_np, ph)

        for k in range(py_nv):
            a = py_pts[k]
            b = nat_pts[k]
            for c in range(3):  # x,y,z
                err = abs(a[c] - b[c])
                if err > maxerr:
                    maxerr = err
                n_components += 1
        n_samples += 1

    ok = (maxerr <= TOL) and (n_components > 0)
    print("MESHINFO py_verts=%d py_polys=%d nat_verts=%d nat_polys=%d" % (py_nv, py_np, nat_nv, nat_np))
    print("RESULT pass=%s maxerr=%.6e samples=%d components=%d tol=%.1e" % (
        str(ok), maxerr, n_samples, n_components, TOL))


main()
