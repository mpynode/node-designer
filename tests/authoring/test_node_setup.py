"""Tests for the setup command infrastructure and selection helpers.

The right-click "Create + run setup" action drives :class:`_SetupNodeCommand`,
which runs the authored ``def setup(cls)`` from ``_common/node_setups/<Type>.py``
against the current Maya selection. The legacy ``SETUP_ROUTINES`` / ``run_setup``
/ ``has_setup`` dispatch has been retired (2026-06-24); the universal
``def setup(cls)`` hook supersedes it.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# LEGACY test classes TestSetupRegistry, TestDeformerSetup, TestSkinSetup,
# TestBlendSetup, TestIkSetup REMOVED (2026-06-24). Those exercised the retired
# `node_setup.has_setup` / `run_setup` API. The authored `def setup(cls)` bodies
# are tested via the command layer below and the per-type setup tests in
# test_setup_wiring_maya.py + test_setup_rollback_maya.py.


class TestSetupCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _run(self, native_type, mode="headers"):
        from mpynode._base.commands import _SetupNodeCommand, run_undoable

        cmd = _SetupNodeCommand(native_type, mode=mode)
        created = run_undoable(cmd)
        if created is None:
            created = getattr(cmd, "created_name", None)
        return cmd, created

    def test_attaches_and_is_undoable(self):
        plane = mc.polyPlane(name="cmdPlane")[0]
        mc.select(plane, replace=True)
        cmd, created = self._run("mPyDeformer", mode="headers")
        self.assertTrue(created and mc.objExists(created))
        self.assertEqual(mc.nodeType(created), "mPyDeformer")
        self.assertIn(created, mc.listHistory(plane) or [])
        mc.undo()
        self.assertFalse(mc.objExists(created))

    def test_template_create_seeds_expression(self):
        # The retired ``mode="template"`` path through _SetupNodeCommand no
        # longer applies a template; template creation now lives in the gallery
        # path (_base.commands._TemplateCreateCommand). This exercises the SAME
        # coverage -- creating from the bundled sine-ripple deformer template
        # seeds the compute expression -- against the migrated template payload.
        import os

        from mpynode._base.commands import _TemplateCreateCommand, run_undoable
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode._node_registry import wrap_node

        template_path = os.path.join(
            os.environ["MPYNODE_ROOT"],
            "templates", "MPyDeformer", "Sine Ripple", "template.mpn",
        )
        payload = load_mpn(template_path, trusted=True)

        plane = mc.polyPlane(name="tplPlane")[0]
        mc.select(plane, replace=True)
        cmd = _TemplateCreateCommand(payload, "mPyDeformer", run_setup=False)
        created = run_undoable(cmd) or cmd.created_name
        self.assertTrue(created and mc.objExists(created))

        expr = wrap_node(created, "mPyDeformer").get_compute_expression() or ""
        self.assertTrue(expr.strip(), "template compute expression must be seeded")
        # The bundled mPyDeformer template is a sine-ripple deformer.
        self.assertIn("sin", expr.lower())

    def test_falls_back_to_bare_when_selection_invalid(self):
        from mpynode._base.commands import _SetupNodeCommand, run_undoable

        mc.select(clear=True)  # no mesh -> setup can't run
        cmd = _SetupNodeCommand("mPyDeformer", mode="headers")
        created = run_undoable(cmd) or getattr(cmd, "created_name", None)
        # Safe degrade: a bare mPyDeformer is still created.
        self.assertTrue(created and mc.objExists(created))
        self.assertEqual(mc.nodeType(created), "mPyDeformer")


class TestCommandSelector(unittest.TestCase):
    def test_setup_command_when_pref_on_and_supported(self):
        from mpynode._base.commands import (
            _SetupNodeCommand,
            build_new_or_setup_command,
        )

        cmd = build_new_or_setup_command(
            "mPyDeformer", mode="headers", auto_setup=True
        )
        self.assertIsInstance(cmd, _SetupNodeCommand)

    def test_normal_create_when_pref_off(self):
        from mpynode._base.commands import (
            _SetupNodeCommand,
            build_new_or_setup_command,
        )

        cmd = build_new_or_setup_command(
            "mPyDeformer", mode="headers", auto_setup=False
        )
        self.assertNotIsInstance(cmd, _SetupNodeCommand)

    def test_normal_create_for_unsupported_type(self):
        from mpynode._base.commands import (
            _SetupNodeCommand,
            build_new_or_setup_command,
        )

        cmd = build_new_or_setup_command(
            "mPyNode", mode="headers", auto_setup=True
        )
        self.assertNotIsInstance(cmd, _SetupNodeCommand)


class TestSelectionHelper(unittest.TestCase):
    def test_override_wins_over_live(self):
        from mpynode._common.methods import setup_helpers as node_setup
        self.assertEqual(
            node_setup._selection(override=["a", "b"]), ["a", "b"])

    def test_exclude_removes_self(self):
        from mpynode._common.methods import setup_helpers as node_setup
        self.assertEqual(
            node_setup._selection(override=["a", "self1", "b"], exclude="self1"),
            ["a", "b"])

    def test_no_args_reads_live_selection(self):
        from mpynode._common.methods import setup_helpers as node_setup
        orig = node_setup.mc.ls
        node_setup.mc.ls = lambda *a, **k: ["live1", "live2"]
        try:
            self.assertEqual(node_setup._selection(), ["live1", "live2"])
        finally:
            node_setup.mc.ls = orig

    def test_exclude_with_live(self):
        from mpynode._common.methods import setup_helpers as node_setup
        orig = node_setup.mc.ls
        node_setup.mc.ls = lambda *a, **k: ["nodeX", "keep"]
        try:
            self.assertEqual(
                node_setup._selection(exclude="nodeX"), ["keep"])
        finally:
            node_setup.mc.ls = orig


class TestAutoSetupPref(unittest.TestCase):
    def test_pref_removed(self):
        from mpynode.ui import preferences

        self.assertNotIn("auto_setup_on_create", preferences.DEFAULT_PREFS)


class TestDesignerAutoSetupWiring(unittest.TestCase):
    def test_new_node_command_no_pref_but_uses_selector(self):
        import inspect

        from mpynode.ui import mpynode_designer as m

        src = inspect.getsource(m.NDMainWindow._new_node_command)
        self.assertNotIn("auto_setup_on_create", src)
        self.assertIn("build_new_or_setup_command", src)

    def test_pref_dialog_has_no_auto_setup_checkbox(self):
        import inspect

        from mpynode.ui.dialogs import preferences as pdlg

        src = inspect.getsource(pdlg)
        self.assertNotIn("_auto_setup_check", src)
        self.assertNotIn("auto_setup_on_create", src)


if __name__ == "__main__":
    unittest.main()
