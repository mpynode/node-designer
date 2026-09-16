"""Stage-1 recipe parity: extracted stock weights on an mPySkinCluster == stock.

The LBS template's demo imports the bundled ``arm.ma`` (a mesh deformed by a
stock ``skinCluster``), extracts that skinCluster's weights / influences /
bindPreMatrix, detaches it, and re-skins the SAME mesh with an ``mPySkinCluster``
running the shipped vectorized LBS default. This test pins the recipe: the
rebuilt mPySkinCluster must reproduce the stock deform to floating-point parity
at multiple elbow poses (the whole point of "use the existing weights").

Recipe proven interactively (see project memory
``skincluster-lbs-dqs-template-program-2026-07-22``): ``mc.skinCluster(sc,
e=True, unbind=True)`` reverts the mesh to its exact rest geometry, so feeding
that rest + the stock bindPreMatrix + the live joint world matrices to the
mPySkinCluster reproduces the stock deform exactly (no duplicate / point copy).
"""

from __future__ import annotations

import os
import unittest

import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _arm_path():
    from mpynode._common.util.template_gallery import _bundled_templates_root
    root = _bundled_templates_root()
    return os.path.join(root or "", "MPyNode", "Ouch", "arm.ma")


def _mobj1(name):
    import maya.OpenMaya as om1
    sl = om1.MSelectionList()
    sl.add(name)
    o = om1.MObject()
    sl.getDependNode(0, o)
    return o


def _dag1(name):
    import maya.OpenMaya as om1
    sl = om1.MSelectionList()
    sl.add(name)
    dp = om1.MDagPath()
    sl.getDagPath(0, dp)
    return dp


def _mesh_pts(shape):
    sl = om.MSelectionList()
    sl.add(shape)
    fn = om.MFnMesh(sl.getDagPath(0))
    return np.array([[p.x, p.y, p.z] for p in fn.getPoints(om.MSpace.kObject)])


def _extract_stock_skin(sc, mesh_shape):
    """Return (influence_names, weights (nv, ninf), {col: bindPreMatrix})."""
    import maya.OpenMaya as om1
    import maya.OpenMayaAnim as oma1

    mfn_sc = oma1.MFnSkinCluster(_mobj1(sc))
    infl   = om1.MDagPathArray()
    mfn_sc.influenceObjects(infl)
    infl_names = [infl[i].partialPathName() for i in range(infl.length())]

    comp_fn = om1.MFnSingleIndexedComponent()
    comp    = comp_fn.create(om1.MFn.kMeshVertComponent)
    nv      = mc.polyEvaluate(mesh_shape, vertex=True)
    comp_fn.setCompleteData(nv)
    wts = om1.MDoubleArray()
    su  = om1.MScriptUtil()
    su.createFromInt(0)
    p_uint = su.asUintPtr()
    mfn_sc.getWeights(_dag1(mesh_shape), comp, wts, p_uint)
    ninf = om1.MScriptUtil.getUint(p_uint)
    W    = np.array([wts[i] for i in range(wts.length())]).reshape(nv, ninf)

    bind_vals = {}
    for c in (mc.getAttr(sc + ".bindPreMatrix", multiIndices=True) or []):
        bind_vals[c] = mc.getAttr(sc + ".bindPreMatrix[%d]" % c)
    return infl_names, W, bind_vals


class TestArmWeightExtractionParity(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_rebuilt_skin_reproduces_stock_deform(self):
        arm = _arm_path()
        self.assertTrue(os.path.isfile(arm), "bundled arm.ma missing: %s" % arm)

        new    = mc.file(arm, i=True, ignoreVersion=True, returnNewNodes=True) or []
        skins  = mc.ls(new, type="skinCluster") or []
        joints = mc.ls(new, type="joint", long=True) or []
        meshes = [m for m in (mc.ls(new, type="mesh", long=True) or [])
                  if not mc.getAttr(m + ".intermediateObject")]
        self.assertTrue(skins and meshes, "arm.ma missing skinCluster/mesh")

        sc         = skins[0]
        mesh_shape = meshes[0]
        mesh_xform = mc.listRelatives(mesh_shape, parent=True, fullPath=True)[0]
        elbow = (next((j for j in joints
                       if j.rsplit("|", 1)[-1] == "loarm_r_JNT"), None)
                 or next((j for j in joints if "loarm" in j), None))
        self.assertIsNotNone(elbow, "elbow joint not found")

        infl_names, W, bind_vals = _extract_stock_skin(sc, mesh_shape)
        nv, ninf = W.shape
        self.assertEqual(ninf, 2, "expected 2 influences")
        self.assertTrue(np.allclose(W.sum(axis=1), 1.0, atol=1e-6),
                        "extracted weights are not partition-of-unity")

        # Deterministic posing: clear anim + unlock the elbow rotate.
        for ax in ("rotateX", "rotateY", "rotateZ"):
            for src in (mc.listConnections(elbow + "." + ax, s=True, d=False,
                                           plugs=True) or []):
                mc.disconnectAttr(src, elbow + "." + ax)
            mc.setAttr(elbow + "." + ax, lock=False)

        # Capture the stock deform at two elbow poses.
        mc.setAttr(elbow + ".rotate", 0, 0, 0)
        mc.dgeval(mesh_shape + ".outMesh")
        stock_straight = _mesh_pts(mesh_shape)
        mc.setAttr(elbow + ".rotateY", 50.0)   # arm hinges on Y
        mc.dgeval(mesh_shape + ".outMesh")
        stock_bent = _mesh_pts(mesh_shape)
        mc.setAttr(elbow + ".rotateY", 0.0)

        # Detach the stock skin -> the mesh reverts to its exact rest geometry.
        mc.skinCluster(sc, e=True, unbind=True)

        # Re-skin the SAME mesh with an mPySkinCluster (shipped LBS default).
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        from mpynode._defaults import skin_cluster_defaults as scd

        wrapper = MPySkinCluster.create(mesh=mesh_xform, joints=infl_names,
                                        name="lbsSkin")
        node = wrapper.get_name()
        # Weights BEFORE first eval (kSkinCluster 0.5/0.5 lock-in gotcha).
        for v in range(nv):
            for c in range(ninf):
                wrapper.set_vertex_weight(v, c, float(W[v, c]))
        # Byte-exact bind from the stock bindPreMatrix (live influence columns).
        for c in range(ninf):
            if c in bind_vals:
                mc.setAttr(node + ".bindPreMatrix[%d]" % c, bind_vals[c],
                           type="matrix")
        wrapper.set_init_expression(scd.DEFAULT_INIT_SOURCE)
        wrapper.set_compute_expression(scd.DEFAULT_COMPUTE_SOURCE)

        mc.setAttr(elbow + ".rotate", 0, 0, 0)
        mc.dgeval(mesh_shape + ".outMesh")
        mpy_straight = _mesh_pts(mesh_shape)
        mc.setAttr(elbow + ".rotateY", 50.0)   # arm hinges on Y
        mc.dgeval(mesh_shape + ".outMesh")
        mpy_bent   = _mesh_pts(mesh_shape)

        d_straight = float(np.abs(mpy_straight - stock_straight).max())
        d_bent     = float(np.abs(mpy_bent - stock_bent).max())
        # The bent pose must be a non-trivial deform (else parity is vacuous).
        self.assertGreater(float(np.abs(stock_bent - stock_straight).max()), 1.0,
                           "elbow pose did not move the stock mesh")
        self.assertLess(d_straight, 1e-4,
                        "mPySkinCluster deviates from stock (straight): %r"
                        % d_straight)
        self.assertLess(d_bent, 1e-4,
                        "mPySkinCluster deviates from stock (bent): %r" % d_bent)


if __name__ == "__main__":
    unittest.main()
