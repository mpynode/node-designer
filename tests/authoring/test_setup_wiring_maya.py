"""Integration tests for universal setup hook wiring (§9.4 per-family wiring).

Tests that each authored `_common/node_setups/<Type>.py` setup body wires the
Maya scene correctly when executed end-to-end. This is the FIRST real exercise
of the setup bodies — they have only been AST/exec-smoke-tested before this.
"""

import unittest

from maya import cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import build_new_or_setup_command, run_undoable


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestSetupWiringMaya(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _run_setup(self, native_type):
        """Run setup and return the created node name."""
        cmd = build_new_or_setup_command(native_type, mode=None, auto_setup=True)
        run_undoable(cmd)
        self.assertTrue(cmd.created_name, "setup must create a node")
        self.assertTrue(mc.objExists(cmd.created_name))
        return cmd.created_name

    # 7a: mPyMesh — produces mesh shape with outMesh→inMesh
    def test_mpymesh_wires_mesh_shape(self):
        name = self._run_setup("mPyMesh")
        # Must create a render transform + mesh shape.
        render_xform = name + "Render"
        render_shape = name + "RenderShape"
        self.assertTrue(mc.objExists(render_xform))
        self.assertTrue(mc.objExists(render_shape))
        self.assertEqual(mc.nodeType(render_shape), "mesh")
        # outMesh → inMesh.
        self.assertTrue(mc.isConnected(name + ".outMesh", render_shape + ".inMesh"))
        # Shape in initialShadingGroup.
        sg_members = mc.sets("initialShadingGroup", query=True) or []
        self.assertIn(render_shape, sg_members)

    # 7b: mPyNurbsCurve, mPyNurbsSurface — outCurve/outSurface → shape.create
    def test_mpynurbscurve_wires_curve_shape(self):
        name         = self._run_setup("mPyNurbsCurve")
        render_xform = name + "Render"
        render_shape = name + "RenderShape"
        self.assertTrue(mc.objExists(render_xform))
        self.assertTrue(mc.objExists(render_shape))
        self.assertEqual(mc.nodeType(render_shape), "nurbsCurve")
        # outCurve → create.
        self.assertTrue(mc.isConnected(name + ".outCurve", render_shape + ".create"))

    def test_mpynurbssurface_wires_surface_shape(self):
        name         = self._run_setup("mPyNurbsSurface")
        render_xform = name + "Render"
        render_shape = name + "RenderShape"
        self.assertTrue(mc.objExists(render_xform))
        self.assertTrue(mc.objExists(render_shape))
        self.assertEqual(mc.nodeType(render_shape), "nurbsSurface")
        # outSurface → create.
        self.assertTrue(mc.isConnected(name + ".outSurface", render_shape + ".create"))

    # 7c: mPyFile — in defaultTextureList1; color wiring to shader
    def test_mpyfile_in_texture_list(self):
        name = self._run_setup("mPyFile")
        # Node must be in defaultTextureList1.textures.
        textures = mc.listConnections("defaultTextureList1.textures", source=True) or []
        self.assertIn(name, textures)

    def test_mpyfile_wires_to_lambert_color(self):
        # Create a lambert, select it, then create mPyFile → outColor→color.
        shader = mc.shadingNode("lambert", asShader=True, name="testLambert")
        mc.select(shader, replace=True)
        name = self._run_setup("mPyFile")
        self.assertTrue(mc.isConnected(name + ".outColor", shader + ".color"))

    def test_mpyfile_wires_to_aiStandardSurface_baseColor(self):
        # Skip if MtoA/aiStandardSurface unavailable.
        if "aiStandardSurface" not in mc.allNodeTypes():
            self.skipTest("aiStandardSurface (MtoA) not available")
        shader = mc.shadingNode("aiStandardSurface", asShader=True, name="testAi")
        mc.select(shader, replace=True)
        name = self._run_setup("mPyFile")
        self.assertTrue(mc.isConnected(name + ".outColor", shader + ".baseColor"))

    def test_mpyfile_no_wiring_to_non_shader(self):
        # Select a pointLight → no color wiring.
        light = mc.createNode("pointLight", name="testLight")
        mc.select(light, replace=True)
        name = self._run_setup("mPyFile")
        # No outColor connections to the light.
        conns = mc.listConnections(name + ".outColor", destination=True) or []
        self.assertNotIn(light, conns)

    # 7d: mPyDeformer — in mesh deform chain
    def test_mpydeformer_in_deform_chain(self):
        mesh = mc.polyPlane(name="deformPlane")[0]
        mc.select(mesh, replace=True)
        name = self._run_setup("mPyDeformer")
        self.assertEqual(mc.nodeType(name), "mPyDeformer")
        # Must be in the mesh's history.
        history = mc.listHistory(mesh) or []
        self.assertIn(name, history)

    # 7e: mPyDeformer — in deform chain for mesh AND nurbs
    def test_mpydeformer_deforms_mesh_and_nurbs(self):
        mesh = mc.polyPlane(name="gfPlane")[0]
        surf = mc.nurbsPlane(name="gfSurf")[0]
        mc.select([mesh, surf], replace=True)
        name = self._run_setup("mPyDeformer")
        self.assertEqual(mc.nodeType(name), "mPyDeformer")
        # In both histories.
        mesh_hist = mc.listHistory(mesh) or []
        surf_hist = mc.listHistory(surf) or []
        self.assertIn(name, mesh_hist)
        self.assertIn(name, surf_hist)

    # 7f: mPySkinCluster — matrix[i]/bindPreMatrix[i] from joints
    def test_mpyskincluster_wires_joints(self):
        mc.select(clear=True)
        j1   = mc.joint(p=(0, 0, 0), name="skinJ1")
        j2   = mc.joint(p=(0, 2, 0), name="skinJ2")
        mesh = mc.polyPlane(name="skinPlane")[0]
        mc.select([j1, j2, mesh], replace=True)
        name = self._run_setup("mPySkinCluster")
        self.assertEqual(mc.nodeType(name), "mPySkinCluster")
        # Each joint's worldMatrix wired to matrix[i].
        matrix_drivers = mc.listConnections(name + ".matrix", source=True) or []
        self.assertIn(j1, matrix_drivers)
        self.assertIn(j2, matrix_drivers)
        # bindPreMatrix[i] is SET (not connected) with bind-pose inverse matrices.
        bind_indices = mc.getAttr(name + ".bindPreMatrix", multiIndices=True) or []
        self.assertGreaterEqual(len(bind_indices), 2, "bindPreMatrix must be set for both joints")

    # 7g: mPyBlendShape — targetGeometry[i] from targets
    def test_mpyblendshape_wires_targets(self):
        tgt  = mc.polyPlane(name="blendTarget")[0]
        base = mc.polyPlane(name="blendBase")[0]
        mc.select([tgt, base], replace=True)
        name = self._run_setup("mPyBlendShape")
        self.assertEqual(mc.nodeType(name), "mPyBlendShape")
        # targetGeometry[i] wired from target mesh (may be transform or shape).
        tgt_drivers = mc.listConnections(name + ".targetGeometry", source=True) or []
        self.assertTrue(tgt_drivers, "at least one target must be wired")
        # The target transform or its shape must be among the drivers.
        tgt_shape = mc.listRelatives(tgt, shapes=True, noIntermediate=True)[0]
        self.assertTrue(
            tgt in tgt_drivers or tgt_shape in tgt_drivers,
            f"target {tgt} or {tgt_shape} must be in {tgt_drivers}"
        )

    # 7h: mPyIkSolver — ikHandle references solver node name
    def test_mpyiksolver_creates_handle(self):
        mc.select(clear=True)
        root = mc.joint(p=(0, 5, 0),  name="ikRoot")
        mid  = mc.joint(p=(0, 0, 0),  name="ikMid")
        tip  = mc.joint(p=(0, -5, 0), name="ikTip")
        mc.select([root, tip], replace=True)
        name = self._run_setup("mPyIkSolver")
        self.assertEqual(mc.nodeType(name), "mPyIkSolver")
        # An ikHandle must exist using this solver NODE NAME.
        handles = mc.ls(type="ikHandle") or []
        self.assertTrue(handles, "an ikHandle should have been created")
        # Find solver connections.
        used = []
        for h in handles:
            used += mc.listConnections(h + ".ikSolver", source=True) or []
        self.assertIn(name, used)


if __name__ == "__main__":
    unittest.main()
