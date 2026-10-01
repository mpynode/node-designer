"""A compiled instance command acts on a node of its own type, and says so
when it is given anything else.

A compiled @maya_command has no implicit ``self``: its target is the object
named on the command line, else the selection. Aimed at a node of another
type it used to run and fail partway -- ``spineBuildSystem`` with a locator
selected died on ``setAttr: No object matches name: locator4.curveAimAxis``.
The dispatcher the bundle embeds now checks the target first. These run the
generated module against real Maya nodes.
"""

from __future__ import annotations

import unittest

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


_SRC = "@maya_command\ndef poke(self):\n    return self.get_name()\n"


def _dispatcher(node_type):
    """The module a bundle of ``node_type`` embeds, executed."""
    from mpynode._common.methods.maya_command import detect_commands
    from mpynode.native.compiler.kernels import command_dispatch as cd

    src = cd.python_module_source(node_type, _SRC, detect_commands(_SRC))
    ns  = {"__name__": "mpynode_cmd_test"}
    exec(compile(src, "<mpynode_cmd_test>", "exec"), ns)
    return ns


class TestTheTargetIsANodeOfItsType(unittest.TestCase):

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def test_a_named_node_of_its_type_is_the_target(self):
        import maya.cmds as mc

        node = mc.createNode("transform", name="grp1")
        self.assertEqual(_dispatcher("transform")["_resolve_target"](node, "poke"), node)

    def test_a_node_of_another_type_is_refused_by_name(self):
        import maya.cmds as mc

        loc = mc.spaceLocator(name="locator4")[0]
        with self.assertRaises(RuntimeError) as ctx:
            _dispatcher("spine")["_resolve_target"](loc, "spineBuildSystem")
        msg = str(ctx.exception)
        self.assertIn("'locator4' is a transform, not a spine", msg)
        self.assertIn("first argument", msg)

    def test_the_selection_is_checked_the_same_way(self):
        import maya.cmds as mc

        mc.select(mc.spaceLocator(name="locator4")[0])
        with self.assertRaises(RuntimeError) as ctx:
            _dispatcher("spine")["_resolve_target"]("", "spineBuildSystem")
        self.assertIn("not a spine", str(ctx.exception))

    def test_a_transform_over_a_shape_of_its_type_is_accepted(self):
        import maya.cmds as mc

        loc = mc.spaceLocator(name="loc1")[0]
        self.assertEqual(_dispatcher("locator")["_resolve_target"](loc, "poke"), loc)

    def test_a_missing_node_is_named(self):
        with self.assertRaises(RuntimeError) as ctx:
            _dispatcher("transform")["_resolve_target"]("nope", "poke")
        self.assertIn("no node named 'nope'", str(ctx.exception))

    def test_nothing_named_or_selected_keeps_its_message(self):
        import maya.cmds as mc

        mc.select(clear=True)
        with self.assertRaises(RuntimeError) as ctx:
            _dispatcher("transform")["_resolve_target"]("", "poke")
        self.assertIn("select (or name) the target node", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
