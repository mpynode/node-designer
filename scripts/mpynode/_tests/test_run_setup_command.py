"""Integration tests for on-demand "Run setup" on an EXISTING node.

Exercises ``_RunSetupCommand``: take an already-created (unwired) node and run
its own ``_methodsSource`` ``def setup(self)`` against the live selection,
instance-bound, inside one undo chunk. Distinct from ``_SetupNodeCommand``,
which CREATES and wires in one shot.
"""

import unittest

import maya.cmds as mc
from maya import cmds

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestRunSetupCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_run_setup_on_existing_node_wires(self):
        from mpynode._node_registry import get_spec
        from mpynode._base.commands import _RunSetupCommand, run_undoable
        mesh = mc.polyCube()[0]
        cls = get_spec("mPyDeformer").get_wrapper_class()
        node = cls.build()                                   # unwired
        mc.select(mesh)
        run_undoable(_RunSetupCommand(node.get_name(), "mPyDeformer"))
        self.assertTrue(cmds.deformer(node.get_name(), q=True, g=True))

    def test_run_setup_excludes_self(self):
        from mpynode._node_registry import get_spec
        from mpynode._base.commands import _RunSetupCommand, run_undoable
        mesh = mc.polyCube()[0]
        cls = get_spec("mPyDeformer").get_wrapper_class()
        node = cls.build()
        mc.select(mesh, node.get_name())                     # self also selected
        run_undoable(_RunSetupCommand(node.get_name(), "mPyDeformer"))
        geo = cmds.deformer(node.get_name(), q=True, g=True) or []
        self.assertNotIn(node.get_name(), geo)

    def test_run_setup_undo_reverses(self):
        from mpynode._node_registry import get_spec
        from mpynode._base.commands import _RunSetupCommand, run_undoable
        mesh = mc.polyCube()[0]
        cls = get_spec("mPyDeformer").get_wrapper_class()
        node = cls.build()
        mc.select(mesh)
        run_undoable(_RunSetupCommand(node.get_name(), "mPyDeformer"))
        self.assertTrue(cmds.deformer(node.get_name(), q=True, g=True))
        mc.undo()
        self.assertFalse(cmds.deformer(node.get_name(), q=True, g=True) or [])


class TestNodeHasRunnableSetup(unittest.TestCase):
    """The gate behind the Scene-tab right-click "Run setup": offered when the
    node's TYPE ships a built-in setup OR the node's OWN Methods source defines a
    self-first ``def setup(self)`` (e.g. a template node like bubble_sort, which
    is a plain mPyNode whose setup lives in its Methods tab)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_type_level_setup_true(self):
        from mpynode._common.methods.methods_registry import node_has_runnable_setup
        from mpynode._node_registry import get_spec
        node = get_spec("mPyDeformer").get_wrapper_class().create()
        self.assertTrue(
            node_has_runnable_setup(node.get_name(), "mPyDeformer"))

    def test_bare_mpynode_false(self):
        from mpynode._common.methods.methods_registry import node_has_runnable_setup
        from mpynode._node_registry import get_spec
        node = get_spec("mPyNode").get_wrapper_class().create()
        self.assertFalse(
            node_has_runnable_setup(node.get_name(), "mPyNode"))

    def test_instance_setup_on_mpynode_true(self):
        from mpynode._common.methods.methods_registry import node_has_runnable_setup
        from mpynode._node_registry import get_spec
        node = get_spec("mPyNode").get_wrapper_class().create()
        node.set_methods_source(
            "def setup(self, *a, **k):\n    return self.get_name()\n")
        self.assertTrue(
            node_has_runnable_setup(node.get_name(), "mPyNode"))

    def test_missing_node_does_not_raise(self):
        # The Scene-tab menu gate must tolerate a stale / non-existent node name
        # (attributeQuery raises on an unknown node) and degrade to False.
        from mpynode._common.methods.methods_registry import (
            node_has_runnable_setup, methods_source_of)
        self.assertEqual(methods_source_of("nonExistentNode#"), "")
        self.assertFalse(
            node_has_runnable_setup("nonExistentNode#", "mPyNode"))


if __name__ == "__main__":
    unittest.main()
