"""skip_selection=False on every node create method.

Contract: passing ``skip_selection=True`` creates the node WITHOUT touching the
active selection. For ``cmds.createNode`` that is ``skipSelect=True``; for
``cmds.shadingNode`` (mPyFile as a texture) the wrapper snapshots the selection
before and restores it after. ``cmds.deformer`` (mPyDeformer / mPySkinCluster /
mPyBlendShape) is SELECTION-NEUTRAL in practice (verified empirically: it never
selects the new deformer and never disturbs the active selection), but the
wrapper still snapshots+restores so the contract is uniform and stays robust if
that ever changes.

Default (False) reproduces today's behavior EXACTLY: the createNode-family and
the shadingNode-family select the new node; the cmds.deformer-family leaves the
selection untouched (it never selected the new node to begin with). The returned
wrapper / name is correct either way.

The gallery "Create + Run setup" commands (_TemplateCreateCommand /
_SetupNodeCommand) ADOPT skip_selection=True so the user's pre-create selection
survives creation (the created node is no longer auto-selected).
"""

import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _marker():
    """A node to select so we can prove the selection is (un)changed."""
    m = mc.createNode("transform", name="SEL_MARKER")
    mc.select(m, replace=True)
    return m


class CreateNodeFamilyTest(unittest.TestCase):
    """Wrappers whose create() is a plain cmds.createNode."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _check(self, make):
        # skip_selection=True -> selection untouched, node still created
        m = _marker()
        node = make(True)
        self.assertEqual(mc.ls(selection=True), [m],
                         "skip_selection=True must not change the selection")
        self.assertTrue(mc.objExists(node.get_name()))
        # default -> the new node (or its transform) is selected, as today
        mc.file(new=True, force=True)
        m = _marker()
        node = make(False)
        self.assertNotEqual(mc.ls(selection=True), [m],
                            "default create must still select the new node")
        self.assertTrue(mc.objExists(node.get_name()))

    def test_base_mpynode(self):
        from mpynode.wrappers._mpy_node import MPyNode
        self._check(lambda ss: MPyNode.create(skip_selection=ss))

    def test_transform(self):
        from mpynode.wrappers.mpy_transform import MPyTransform
        self._check(lambda ss: MPyTransform.create(skip_selection=ss))

    def test_constraint(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint
        self._check(lambda ss: MPyConstraint.create(skip_selection=ss))

    def test_locator(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        self._check(lambda ss: MPyLocator.create(skip_selection=ss))

    def test_mesh(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh
        self._check(lambda ss: MPyMesh.create(skip_selection=ss))

    def test_nurbs_curve(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
        self._check(lambda ss: MPyNurbsCurve.create(skip_selection=ss))

    def test_nurbs_surface(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface
        self._check(lambda ss: MPyNurbsSurface.create(skip_selection=ss))

    def test_iksolver(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver
        self._check(lambda ss: MPyIkSolver.create(skip_selection=ss))

    def test_deformer_bare(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        self._check(lambda ss: MPyDeformer.create(skip_selection=ss))

    def test_skin_cluster_bare(self):
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        self._check(lambda ss: MPySkinCluster.create(skip_selection=ss))

    def test_blend_shape_bare(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
        self._check(lambda ss: MPyBlendShape.create(skip_selection=ss))

    def test_file_bare(self):
        from mpynode.wrappers.mpy_file import MPyFile
        self._check(lambda ss: MPyFile.create(as_texture=False, skip_selection=ss))


class DeformerAttachFamilyTest(unittest.TestCase):
    """Attach creators that use cmds.deformer (mPyDeformer / mPySkinCluster /
    mPyBlendShape). cmds.deformer is SELECTION-NEUTRAL (empirically verified on
    Maya 2024 + 2026: it neither selects the new deformer nor disturbs the active
    selection), so for this family BOTH default and skip_selection=True leave the
    selection that was live at the moment of the call untouched. skip_selection
    additionally snapshots+restores it explicitly, so the uniform contract holds
    and stays robust if a future wrapper change ever starts moving the selection.

    The helper geometry is created BEFORE the marker so the marker is the genuine
    live selection when create() is called -- otherwise the helper-geo creation
    (which DOES move the selection) would be what's preserved, not the marker.
    (The skip-restore MECHANISM is genuinely exercised by the bare createNode
    variants in CreateNodeFamilyTest, where createNode selects the new node.)"""

    def setUp(self):
        mc.file(new=True, force=True)

    def _assert_selection_neutral(self, build, make):
        # skip_selection=True -> marker (live at call time) preserved
        geo = build()
        m = _marker()
        node = make(geo, True)
        self.assertEqual(mc.ls(selection=True), [m],
                         "skip_selection=True must leave the live selection intact")
        self.assertTrue(mc.objExists(node.get_name()))
        # default -> cmds.deformer is selection-neutral, so STILL the marker
        mc.file(new=True, force=True)
        geo = build()
        m = _marker()
        node = make(geo, False)
        self.assertTrue(mc.objExists(node.get_name()))
        self.assertEqual(mc.ls(selection=True), [m],
                         "cmds.deformer default path is selection-neutral")

    def test_deformer_create_on(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        self._assert_selection_neutral(
            build=lambda: mc.polyPlane()[0],
            make=lambda geo, ss: MPyDeformer.create_on(geo, skip_selection=ss))

    def test_skin_cluster_attach(self):
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        self._assert_selection_neutral(
            build=lambda: (mc.polyPlane()[0], mc.createNode("joint")),
            make=lambda geo, ss: MPySkinCluster.create(
                mesh=geo[0], joints=[geo[1]], skip_selection=ss))

    def test_blend_shape_attach(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
        self._assert_selection_neutral(
            build=lambda: (mc.polyPlane()[0], mc.polyPlane()[0]),
            make=lambda geo, ss: MPyBlendShape.create(
                mesh=geo[0], targets=[geo[1]], skip_selection=ss))


class ShadingNodeAttachFamilyTest(unittest.TestCase):
    """mPyFile as a texture uses cmds.shadingNode, which DOES select the new
    node -> default selects it; skip_selection=True restores the prior."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_file_as_texture(self):
        from mpynode.wrappers.mpy_file import MPyFile
        m = _marker()
        node = MPyFile.create(as_texture=True, skip_selection=True)
        self.assertEqual(mc.ls(selection=True), [m],
                         "skip_selection=True must restore the prior selection")
        self.assertTrue(mc.objExists(node.get_name()))
        mc.file(new=True, force=True)
        m = _marker()
        node = MPyFile.create(as_texture=True, skip_selection=False)
        self.assertNotEqual(mc.ls(selection=True), [m],
                            "shadingNode default selects the new node")
        self.assertTrue(mc.objExists(node.get_name()))


class BuildAndCommandTest(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_build_threads_skip_selection(self):
        from mpynode.wrappers._mpy_node import MPyNode
        m = _marker()
        node = MPyNode.build(skip_selection=True)
        self.assertEqual(mc.ls(selection=True), [m])
        self.assertTrue(mc.objExists(node.get_name()))

    def test_create_node_command(self):
        from mpynode._base.commands import _CreateNodeCommand, run_undoable
        m = _marker()
        cmd = _CreateNodeCommand("mPyNode", skip_selection=True)
        name = run_undoable(cmd) or cmd.created_name
        self.assertEqual(mc.ls(selection=True), [m])
        self.assertTrue(mc.objExists(name))

    def test_deserialize_node(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io.mpn_io import serialize_node, deserialize_node
        src = MPyNode.create()
        payload = serialize_node(src, include_persistent=False)
        mc.delete(src.get_name())
        m = _marker()
        node = deserialize_node(payload, skip_selection=True)
        self.assertEqual(mc.ls(selection=True), [m])
        self.assertTrue(mc.objExists(node.get_name()))


class GalleryCommandsAdoptSkipSelectionTest(unittest.TestCase):
    """_TemplateCreateCommand / _SetupNodeCommand create with skipSelect=True so
    the user's pre-create selection survives (created node not auto-selected)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _deformer_payload(self):
        from mpynode._node_registry import get_spec
        from mpynode._common.io.mpn_io import serialize_node
        n = get_spec("mPyDeformer").get_wrapper_class().build()
        payload = serialize_node(n, include_persistent=False)
        mc.delete(n.get_name())
        return payload

    def test_template_create_command_preserves_selection(self):
        from mpynode._base.commands import _TemplateCreateCommand, run_undoable
        payload = self._deformer_payload()
        plane = mc.polyCube()[0]
        mc.select(plane, replace=True)
        cmd = _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        self.assertTrue(mc.objExists(name))
        self.assertNotIn(name, mc.ls(selection=True) or [],
                         "gallery create must not auto-select the new node")

    def test_setup_node_command_preserves_selection(self):
        from mpynode._base.commands import _SetupNodeCommand, run_undoable
        plane = mc.polyCube()[0]
        mc.select(plane, replace=True)
        cmd = _SetupNodeCommand("mPyDeformer", mode="headers")
        run_undoable(cmd)
        self.assertTrue(cmd.created_name and mc.objExists(cmd.created_name))
        self.assertNotIn(cmd.created_name, mc.ls(selection=True) or [],
                         "auto-setup create must not auto-select the new node")


if __name__ == "__main__":
    unittest.main()
