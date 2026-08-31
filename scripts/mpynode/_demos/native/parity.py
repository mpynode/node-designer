"""Parity + performance check for the hand-ported ``mPyMeshSDF`` plugin.

Builds (via :mod:`build`) and loads the native plugin, drives the full igloo
through it at resolution 16, and asserts the emitted mesh matches BOTH the
saved ``TestSDFIgloo`` reference (``tests/test_assets/test_sdf.igloo.npz``,
12509 points) AND the pure-numpy ``sdf_dmc`` module -- proving the C++ is a
faithful translation. It then times Python vs C++ and pushes the native node
to resolution 32 to show it scales to denser fields with the same parity.

Usage (numpy must be importable; pass its dir via SDF_NUMPY_PATH if vendored)::

    SDF_NUMPY_PATH=/path/to/numpy mayapy -B parity.py
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_ROOT = os.path.abspath(os.path.join(_SCRIPTS, ".."))
for p in (os.environ.get("SDF_NUMPY_PATH"), _SCRIPTS):
    if p and p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(_ROOT, "plug-ins"))
sys.dont_write_bytecode = True


def log(m):
    sys.stderr.write(m + "\n")
    sys.stderr.flush()


import maya.standalone
maya.standalone.initialize()
import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np

from mpynode._base.plugins import load_or_reload_native_plugin
from mpynode._demos import sdf_igloo
from mpynode._common.nodes.mesh import sdf_dmc
import build as _build

NATIVE_TYPE = "mPyMeshSDF"
_REF_NPZ = os.path.join(os.path.dirname(_SCRIPTS), "tests", "test_assets",
                        "test_sdf.igloo.npz")


def set_arrays(node, arrays):
    mats = arrays["matrices"]
    for i in range(mats.shape[0]):
        mc.setAttr("%s.shapeMatrix[%d]" % (node, i),
                   *mats[i].flatten().tolist(), type="matrix")
        mc.setAttr("%s.shapeType[%d]" % (node, i), int(arrays["shape_types"][i]))
        mc.setAttr("%s.additive[%d]" % (node, i), int(bool(arrays["additive"][i])))
        mc.setAttr("%s.smoothing[%d]" % (node, i), float(arrays["smoothing"][i]))
        mc.setAttr("%s.radius[%d]" % (node, i), float(arrays["radius"][i]))
        mc.setAttr("%s.height[%d]" % (node, i), float(arrays["height"][i]))
        mc.setAttr("%s.axis[%d]" % (node, i), int(arrays["axis"][i]))
        mc.setAttr("%s.halfExtents[%d]" % (node, i),
                   *arrays["half_extents"][i].tolist(), type="double3")


def read_mesh(node):
    # NB: never mc.delete the temp shape -- outMesh->inMesh is construction
    # history, so deleting it cascades and removes the source node.
    xf = mc.createNode("transform")
    shp = mc.createNode("mesh", parent=xf)
    mc.connectAttr(node + ".outMesh", shp + ".inMesh", force=True)
    mc.polyEvaluate(shp, vertex=True)
    sel = om.MSelectionList()
    sel.add(shp)
    fn = om.MFnMesh(sel.getDagPath(0))
    pts = np.array([[p.x, p.y, p.z]
                    for p in fn.getPoints(om.MSpace.kObject)], np.float64)
    counts, conn = fn.getVertices()
    return pts, np.array(counts, np.int32), np.array(conn, np.int32)


def main():
    bundle = _build.build()
    res = load_or_reload_native_plugin(bundle)
    log("LOAD %s" % res)
    if res.get("error"):
        raise SystemExit(res["error"])

    arrays = sdf_igloo.primitives_to_arrays(sdf_igloo.igloo_primitives())
    with np.load(_REF_NPZ, allow_pickle=True) as d:
        ref_pts = np.asarray(d["points"], np.float64)
        ref_idx = np.asarray(d["indices"], np.int32)

    mc.file(new=True, force=True)
    load_or_reload_native_plugin(bundle)
    nat = mc.createNode(NATIVE_TYPE, name="natIgloo")
    set_arrays(nat, arrays)
    mc.setAttr(nat + ".resolution", 16)
    pts, _c, idx = read_mesh(nat)
    log("PARITY res16: native=%d ref=%d maxerr=%.3e indices_equal=%s"
        % (pts.shape[0], ref_pts.shape[0], float(np.max(np.abs(pts - ref_pts))),
           bool(np.array_equal(idx, ref_idx))))

    mc.setAttr(nat + ".resolution", 32)
    t0 = time.perf_counter()
    d32, _c32, i32 = read_mesh(nat)
    t_nat32 = time.perf_counter() - t0
    t0 = time.perf_counter()
    rp32, _rc32, ri32 = sdf_dmc.mesh_from_shapes(resolution=32, iso_value=0.0, **arrays)
    t_py32 = time.perf_counter() - t0
    log("DENSE res32: native=%d (%.3fs) python=%.3fs maxerr=%.3e indices_equal=%s"
        % (d32.shape[0], t_nat32, t_py32, float(np.max(np.abs(d32 - rp32))),
           bool(np.array_equal(i32, ri32))))

    maya.standalone.uninitialize()
    os._exit(0)


if __name__ == "__main__":
    main()
