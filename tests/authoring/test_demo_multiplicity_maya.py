"""End-to-end coverage for multiple demos + the factory demo path in a real
Maya scene. Proves: a node carrying two @maya_demo defs runs each by name; a
factory demo builds its OWN nodes via run_type_demo (bound to the wrapper class,
no instance); the command layer routes factory-vs-instance correctly.
"""
import unittest

from maya import cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import (
    _RunDemoCommand, _CreateNodeCommand, run_undoable)
from mpynode._node_registry import wrap_node


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_TWO_DEMOS = (
    "import maya.cmds as mc\n"
    "from mpynode._common.methods.maya_command import maya_demo\n"
    "\n"
    "@maya_demo(label='Make Cube')\n"
    "def make_cube(cls):\n"
    "    mc.polyCube(name='demoCube')\n"
    "    return 'demoCube'\n"
    "\n"
    "@maya_demo(label='Make Locator')\n"
    "def show_loc(self):\n"
    "    mc.spaceLocator(name='demoLoc')\n"
    "    return 'demoLoc'\n"
)


class TestDemoMultiplicity(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        cmd            = _CreateNodeCommand("mPyNode")
        self.node_name = run_undoable(cmd) or cmd.created_name
        node           = wrap_node(self.node_name, "mPyNode")
        node.set_methods_source(_TWO_DEMOS)

    def test_instance_demo_by_name(self):
        run_undoable(_RunDemoCommand(self.node_name, "mPyNode", "show_loc"))
        self.assertTrue(mc.objExists("demoLoc"))
        self.assertFalse(mc.objExists("demoCube"))

    def test_factory_demo_by_name_builds_own_nodes(self):
        run_undoable(_RunDemoCommand(self.node_name, "mPyNode", "make_cube"))
        self.assertTrue(mc.objExists("demoCube"))

    def test_factory_demo_single_undo(self):
        run_undoable(_RunDemoCommand(self.node_name, "mPyNode", "make_cube"))
        self.assertTrue(mc.objExists("demoCube"))
        mc.undo()
        self.assertFalse(mc.objExists("demoCube"))

    def test_reserved_def_demo_still_runs(self):
        node = wrap_node(self.node_name, "mPyNode")
        node.set_methods_source(
            "import maya.cmds as mc\n"
            "def demo(self):\n    mc.spaceLocator(name='resvLoc')\n"
            "    return 'resvLoc'\n")
        run_undoable(_RunDemoCommand(self.node_name, "mPyNode"))
        self.assertTrue(mc.objExists("resvLoc"))


if __name__ == "__main__":
    unittest.main()
