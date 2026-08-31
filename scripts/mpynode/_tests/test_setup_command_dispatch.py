import os
import tempfile
import unittest

from maya import cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import (
    _SetupNodeCommand, build_new_or_setup_command, run_undoable)
from mpynode._node_registry import wrap_node


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestSetupDispatch(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_seed_methods_source_on_create_with_setup(self):
        # mPyMesh has no .mpn template -> proves the seed is set_methods_source.
        cmd = build_new_or_setup_command("mPyMesh", mode=None, auto_setup=True)
        self.assertIsInstance(cmd, _SetupNodeCommand)
        run_undoable(cmd)
        self.assertTrue(mc.objExists(cmd.created_name))
        src = wrap_node(cmd.created_name, "mPyMesh").get_methods_source()
        self.assertIn("def setup(self", src)

    def test_seed_round_trips_through_ma(self):
        cmd = build_new_or_setup_command("mPyMesh", mode=None, auto_setup=True)
        run_undoable(cmd)
        name = cmd.created_name
        path = os.path.join(tempfile.mkdtemp(), "seed_rt.ma")
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)
        mc.file(path, open=True, force=True)
        self.assertIn("def setup(self",
                      wrap_node(name, "mPyMesh").get_methods_source())

    def test_built_but_unwired_on_setup_error(self):
        # deformer needs geo selected; with nothing selected the setup raises
        # SetupError -- build() swallows it, so the node is BUILT but UNWIRED
        # (and still seeded with its setup source). Creation never fails.
        mc.select(clear=True)
        cmd = build_new_or_setup_command("mPyDeformer", mode="headers", auto_setup=True)
        run_undoable(cmd)
        name = cmd.created_name
        self.assertTrue(name and mc.objExists(name))
        self.assertIn("def setup(self",
                      wrap_node(name, "mPyDeformer").get_methods_source())

    def test_built_but_unwired_on_runtime_error(self):
        import mpynode._common.node_setups as nsmod
        orig = nsmod.setup_source_for_type
        nsmod.setup_source_for_type = lambda t, *a, **k: (
            "def setup(self):\n    raise RuntimeError('boom')\n"
            if t == "mPyMesh" else orig(t, *a, **k))
        try:
            cmd = build_new_or_setup_command("mPyMesh", mode=None, auto_setup=True)
            run_undoable(cmd)
            # build() runs the (injected) setup, which raises at runtime; the
            # exception is swallowed -> node exists, just unwired.
            self.assertTrue(cmd.created_name and mc.objExists(cmd.created_name))
        finally:
            nsmod.setup_source_for_type = orig

    def test_single_undo_removes_node_and_seed(self):
        cmd = build_new_or_setup_command("mPyMesh", mode=None, auto_setup=True)
        run_undoable(cmd)
        name = cmd.created_name
        self.assertTrue(mc.objExists(name))
        mc.undo()
        self.assertFalse(mc.objExists(name))

    def test_setup_command_has_no_template_seed_branch(self):
        # The §6.1 deviation (build(setup=True) THEN _seed_template) is retired;
        # the correct order now lives only in _TemplateCreateCommand.
        self.assertFalse(hasattr(_SetupNodeCommand, "_seed_template"))

    def test_setup_command_template_mode_still_creates(self):
        # mode="template" no longer special-cases anything: a wiring type still
        # creates (built-but-unwired with nothing selected), no template seeding.
        mc.select(clear=True)
        cmd = _SetupNodeCommand("mPyDeformer", mode="template")
        run_undoable(cmd)
        self.assertTrue(cmd.created_name and mc.objExists(cmd.created_name))


if __name__ == "__main__":
    unittest.main()
