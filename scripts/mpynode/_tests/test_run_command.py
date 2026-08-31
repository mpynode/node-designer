"""End-to-end coverage for the undoable ``_RunCommandCommand``: running a
node's ``@maya_command`` in the interpreted node, in one undo chunk.

Mirrors ``test_demo_multiplicity_maya`` -- a real Maya scene, the node carries
a Methods source defining a single ``@maya_command``, and the command is
dispatched via ``run_undoable``. Proves the command is callable by BOTH its
``@maya_command`` name and its python def name, with args/kwargs forwarded.
"""
import unittest

from maya import cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_ECHO_SRC = (
    "from mpynode._common.methods.maya_command import maya_command\n"
    "@maya_command(name='echoVal')\n"
    "def echo_val(self, v=None):\n"
    "    return v\n"
)


class TestRunCommandCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers.mpy_locator import MPyLocator

        self.loc = MPyLocator.create(name="runCmd")
        self.loc.set_methods_source(_ECHO_SRC)

    def test_run_by_command_name(self):
        from mpynode._base.commands import _RunCommandCommand, run_undoable

        res = run_undoable(
            _RunCommandCommand(
                self.loc.get_name(), self.loc.NATIVE_TYPE,
                'echoVal', (), {'v': 42}))
        self.assertEqual(res, 42)

    def test_run_by_python_def_name(self):
        from mpynode._base.commands import _RunCommandCommand, run_undoable

        res2 = run_undoable(
            _RunCommandCommand(
                self.loc.get_name(), self.loc.NATIVE_TYPE,
                'echo_val', (), {'v': 7}))
        self.assertEqual(res2, 7)


if __name__ == "__main__":
    unittest.main()
