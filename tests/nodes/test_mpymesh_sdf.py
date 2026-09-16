"""Node-level test for the mPyMesh SDF dual-marching-cubes demo node.

Drives a LIVE Maya ``mPyMesh`` configured by
``mpynode._demos.build_mPyMesh_sdf_dmc.configure_node`` and verifies the
mesh it emits on ``outMesh``:

  * single sphere -- set ONLY ``shapeMatrix[0]`` (identity); every
    optional per-shape array is left unconnected so the compute must
    size them to the matrix count with the rl SDF defaults. The result
    must equal the shared module's single-sphere mesh exactly, proving
    (a) the optional-array defaulting rule, (b) an exact matrix plug
    round-trip, and (c) the node drives ``sdf_dmc.mesh_from_shapes``
    faithfully.

  * full igloo -- drive all ~40 primitives (matrices + parallel arrays)
    through the node's plugs at resolution 16 and assert the emitted mesh
    matches the saved ``TestSDFIgloo`` reference ``test_sdf.igloo.npz``.
    This is the "matches TestSDFIgloo through the live node" proof.
"""
from __future__ import annotations

import os
import unittest

import numpy as np
from tests import _paths


def setUpModule():
    import maya.standalone
    try:
        maya.standalone.initialize()
    except Exception:
        pass
    import maya.cmds as mc
    for plugin in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(plugin, q=True, loaded=True):
            mc.loadPlugin(plugin)


_REF_NPZ = os.path.join(_paths.ASSETS, "test_sdf.igloo.npz"
)


def _read_node_mesh(node):
    """Pull ``node.outMesh`` into (points, counts, indices) numpy arrays via
    a real mesh shape (the canonical render path -- forces DG eval)."""
    import maya.cmds as mc
    import maya.api.OpenMaya as om

    xfm   = mc.createNode("transform")
    shape = mc.createNode("mesh", parent=xfm)
    mc.connectAttr(node + ".outMesh", shape + ".inMesh", force=True)
    mc.polyEvaluate(shape, vertex=True)  # force the DG to evaluate inMesh

    sel = om.MSelectionList()
    sel.add(shape)
    dag     = sel.getDagPath(0)
    fn      = om.MFnMesh(dag)
    pts_arr = fn.getPoints(om.MSpace.kObject)
    points  = np.array([[p.x, p.y, p.z] for p in pts_arr], dtype=np.float64)
    counts, conn = fn.getVertices()
    return points, np.array(counts, dtype=np.int32), np.array(conn, dtype=np.int32)


def _set_arrays(node, arrays):
    """setAttr every per-shape array element onto ``node`` from the parallel
    arrays dict ``sdf_igloo.primitives_to_arrays`` produces."""
    import maya.cmds as mc

    mats = arrays["matrices"]
    n    = mats.shape[0]
    for i in range(n):
        mc.setAttr("%s.shapeMatrix[%d]" % (node, i),
                   *mats[i].flatten().tolist(), type="matrix")
        mc.setAttr("%s.shapeType[%d]" % (node, i), int(arrays["shape_types"][i]))
        mc.setAttr("%s.additive[%d]" % (node, i),  int(bool(arrays["additive"][i])))
        mc.setAttr("%s.smoothing[%d]" % (node, i), float(arrays["smoothing"][i]))
        mc.setAttr("%s.radius[%d]" % (node, i),    float(arrays["radius"][i]))
        mc.setAttr("%s.height[%d]" % (node, i),    float(arrays["height"][i]))
        mc.setAttr("%s.axis[%d]" % (node, i),      int(arrays["axis"][i]))
        mc.setAttr("%s.halfExtents[%d]" % (node, i),
                   *arrays["half_extents"][i].tolist(), type="double3")


class TestMPyMeshSDFSingleSphere(unittest.TestCase):
    def test_optional_arrays_default_to_unit_sphere(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_mesh import MPyMesh
        from mpynode._demos import build_mPyMesh_sdf_dmc as bld
        from mpynode._common.nodes.mesh import sdf_dmc

        mc.file(new=True, force=True)
        wrapper = MPyMesh.create(name="sdfSphere")
        bld.configure_node(wrapper)
        node = wrapper.get_name()

        # Set ONLY the matrix (identity) + resolution. Leave every optional
        # per-shape array unconnected -> the compute must default them.
        mc.setAttr("%s.shapeMatrix[0]" % node,
                   *np.eye(4).flatten().tolist(), type="matrix")
        mc.setAttr("%s.resolution" % node, 12)

        pts, counts, idx = _read_node_mesh(node)

        # Reference: the shared module fed the SAME single sphere with the
        # SAME defaults the node should synthesize.
        ref_pts, ref_counts, ref_idx = sdf_dmc.mesh_from_shapes(
            matrices     = np.eye(4)[None],
            shape_types  = np.zeros(1, dtype=np.int64),
            additive     = np.ones(1, dtype=bool),
            smoothing    = np.zeros(1, dtype=np.float64),
            radius       = np.ones(1, dtype=np.float64),
            height       = np.ones(1, dtype=np.float64),
            axis         = np.ones(1, dtype=np.int64),
            half_extents = np.tile([0.5, 0.5, 0.5], (1, 1)),
            resolution   = 12,
            iso_value    = 0.0,
        )

        self.assertEqual(pts.shape[0], ref_pts.shape[0])
        self.assertGreater(pts.shape[0], 0)
        np.testing.assert_allclose(pts, ref_pts, rtol=1e-5, atol=1e-7)
        np.testing.assert_array_equal(counts, ref_counts)
        np.testing.assert_array_equal(idx, ref_idx)


class TestMPyMeshSDFIgloo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with np.load(_REF_NPZ, allow_pickle=True) as data:
            cls.ref_points  = np.asarray(data["points"],  dtype=np.float64)
            cls.ref_counts  = np.asarray(data["counts"],  dtype=np.int32)
            cls.ref_indices = np.asarray(data["indices"], dtype=np.int32)

    def _build_igloo_node(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_mesh import MPyMesh
        from mpynode._demos import build_mPyMesh_sdf_dmc as bld
        from mpynode._demos import sdf_igloo

        mc.file(new=True, force=True)
        wrapper = MPyMesh.create(name="sdfIgloo")
        bld.configure_node(wrapper)
        node   = wrapper.get_name()

        arrays = sdf_igloo.primitives_to_arrays(sdf_igloo.igloo_primitives())
        _set_arrays(node, arrays)
        mc.setAttr("%s.resolution" % node, 16)
        return node

    def test_igloo_mesh_matches_reference(self):
        node = self._build_igloo_node()
        pts, counts, idx = _read_node_mesh(node)

        self.assertEqual(pts.shape[0], self.ref_points.shape[0])
        np.testing.assert_allclose(pts, self.ref_points, rtol=1e-5, atol=1e-7)
        self.assertEqual(counts.size, self.ref_counts.size)
        np.testing.assert_array_equal(idx, self.ref_indices)


_EXAMPLE_MA = os.path.join(_paths.ASSETS, "mPyMesh_sdf_dmc.ma")


class TestMPyMeshSDFExampleScene(unittest.TestCase):
    """Open the SHIPPED example scene (live transforms igloo) and confirm the
    mesh it produces matches the TestSDFIgloo reference -- the end-to-end
    proof that the example faithfully recreates the unittest in Maya."""

    @classmethod
    def setUpClass(cls):
        with np.load(_REF_NPZ, allow_pickle=True) as data:
            cls.ref_points  = np.asarray(data["points"],  dtype=np.float64)
            cls.ref_counts  = np.asarray(data["counts"],  dtype=np.int32)
            cls.ref_indices = np.asarray(data["indices"], dtype=np.int32)

    @unittest.skipUnless(os.path.exists(_EXAMPLE_MA),
                         "example scene not built yet")
    def test_example_scene_mesh_matches_reference(self):
        import maya.cmds as mc

        mc.file(_EXAMPLE_MA, open=True, force=True)
        # The render shape the setup() hook created.
        shapes = mc.ls("*RenderShape", type="mesh", long=True)
        self.assertTrue(shapes, "no *RenderShape mesh in the example scene")
        shape = shapes[0]
        mc.polyEvaluate(shape, vertex=True)  # force eval through inMesh

        import maya.api.OpenMaya as om
        sel = om.MSelectionList()
        sel.add(shape)
        fn = om.MFnMesh(sel.getDagPath(0))
        pts = np.array([[p.x, p.y, p.z]
                        for p in fn.getPoints(om.MSpace.kObject)], dtype=np.float64)
        counts, conn = fn.getVertices()
        idx = np.array(conn, dtype=np.int32)

        self.assertEqual(pts.shape[0], self.ref_points.shape[0])
        np.testing.assert_allclose(pts, self.ref_points, rtol=1e-5, atol=1e-7)
        self.assertEqual(np.array(counts).size, self.ref_counts.size)
        np.testing.assert_array_equal(idx, self.ref_indices)


class TestMPyMeshSDFCommands(unittest.TestCase):
    def _new_node(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_mesh import MPyMesh
        from mpynode._demos import build_mPyMesh_sdf_dmc as bld

        mc.file(new=True, force=True)
        wrapper = MPyMesh.create(name="sdfCmd")
        bld.configure_node(wrapper)
        return wrapper

    def test_commands_detected(self):
        wrapper = self._new_node()
        names   = {c["name"] for c in wrapper.list_commands()}
        self.assertEqual({"addSphere", "addBox", "addCylinder"} & names,
                         {"addSphere", "addBox", "addCylinder"})
        # All three are instance (self-first) commands, not factories/statics.
        for c in wrapper.list_commands():
            if c["name"] in ("addSphere", "addBox", "addCylinder"):
                self.assertFalse(c["is_factory"])
                self.assertFalse(c["is_static"])

    def test_addSphere_wires_and_builds_unit_sphere(self):
        import maya.cmds as mc
        from mpynode._common.nodes.mesh import sdf_dmc

        wrapper = self._new_node()
        node    = wrapper.get_name()
        xf      = mc.createNode("transform", name="sphereXf")

        out = wrapper.call_command("addSphere", transform=xf, radius=1.0)
        self.assertEqual(out, xf)

        # Wiring: worldMatrix + radius connected; shapeType stamped sphere.
        self.assertTrue(mc.isConnected(xf + ".worldMatrix[0]",
                                       node + ".shapeMatrix[0]"))
        self.assertTrue(mc.isConnected(xf + ".radius", node + ".radius[0]"))
        self.assertEqual(mc.getAttr(node + ".shapeType[0]"), 0)
        self.assertTrue(mc.attributeQuery("radius", node=xf, exists=True))
        self.assertAlmostEqual(mc.getAttr(xf + ".radius"), 1.0)

        mc.setAttr(node + ".resolution", 12)
        pts, counts, idx = _read_node_mesh(node)
        ref_pts, ref_counts, ref_idx = sdf_dmc.mesh_from_shapes(
            matrices     = np.eye(4)[None],
            shape_types  = np.zeros(1, dtype=np.int64),
            additive     = np.ones(1, dtype=bool),
            smoothing    = np.zeros(1, dtype=np.float64),
            radius       = np.ones(1, dtype=np.float64),
            height       = np.ones(1, dtype=np.float64),
            axis         = np.ones(1, dtype=np.int64),
            half_extents = np.tile([0.5, 0.5, 0.5], (1, 1)),
            resolution=12, iso_value=0.0,
        )
        self.assertEqual(pts.shape[0], ref_pts.shape[0])
        np.testing.assert_allclose(pts, ref_pts, rtol=1e-5, atol=1e-7)
        np.testing.assert_array_equal(idx, ref_idx)

    def test_sphere_minus_box_matches_module(self):
        import maya.cmds as mc
        from mpynode._common.nodes.mesh import sdf_dmc

        wrapper   = self._new_node()
        node      = wrapper.get_name()

        sphere_xf = mc.createNode("transform", name="domeXf")
        box_xf    = mc.createNode("transform", name="cutXf")
        mc.setAttr(box_xf + ".translateY", -1.0)

        wrapper.call_command("addSphere", transform=sphere_xf, radius=1.5,
                             additive=True)
        wrapper.call_command("addBox", transform=box_xf, half=(2.0, 1.0, 2.0),
                             additive=False)
        mc.setAttr(node + ".resolution", 12)

        self.assertEqual(mc.getAttr(node + ".shapeType[0]"), 0)
        self.assertEqual(mc.getAttr(node + ".shapeType[1]"), 1)
        self.assertEqual(mc.getAttr(node + ".additive[1]"),  0)

        pts, counts, idx = _read_node_mesh(node)

        box_M        = np.eye(4)
        box_M[3, :3] = [0.0, -1.0, 0.0]
        ref_pts, ref_counts, ref_idx = sdf_dmc.mesh_from_shapes(
            matrices     = np.array([np.eye(4), box_M]),
            shape_types  = np.array([0, 1], dtype=np.int64),
            additive     = np.array([True, False]),
            smoothing    = np.zeros(2, dtype=np.float64),
            radius       = np.array([1.5, 1.0], dtype=np.float64),
            height       = np.ones(2, dtype=np.float64),
            axis         = np.ones(2, dtype=np.int64),
            half_extents = np.array([[0.5, 0.5, 0.5], [2.0, 1.0, 2.0]]),
            resolution=12, iso_value=0.0,
        )
        self.assertEqual(pts.shape[0], ref_pts.shape[0])
        self.assertGreater(pts.shape[0], 0)
        np.testing.assert_allclose(pts, ref_pts, rtol=1e-5, atol=1e-7)
        np.testing.assert_array_equal(idx, ref_idx)

    def test_addCylinder_wires_radius_height_axis(self):
        import maya.cmds as mc

        wrapper = self._new_node()
        node    = wrapper.get_name()
        xf      = mc.createNode("transform", name="cylXf")

        wrapper.call_command("addCylinder", transform=xf, radius=0.5,
                             height=1.2, axis=2)
        self.assertTrue(mc.isConnected(xf + ".radius", node + ".radius[0]"))
        self.assertTrue(mc.isConnected(xf + ".height", node + ".height[0]"))
        self.assertEqual(mc.getAttr(node + ".shapeType[0]"), 2)
        self.assertEqual(mc.getAttr(node + ".axis[0]"), 2)

    def test_setup_creates_render_mesh(self):
        import maya.cmds as mc
        from mpynode._common.methods.methods_registry import run_node_setup

        wrapper = self._new_node()
        node    = wrapper.get_name()
        run_node_setup(wrapper, selection=[])

        shape = node + "RenderShape"
        self.assertTrue(mc.objExists(shape))
        self.assertEqual(mc.nodeType(shape), "mesh")
        self.assertTrue(mc.isConnected(node + ".outMesh", shape + ".inMesh"))


if __name__ == "__main__":
    unittest.main()
