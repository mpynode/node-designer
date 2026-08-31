"""Compile dialog: per-Class divergence warn + fork (must-fix #1 UX).

Instances of one Class compile to ONE native type but carry code per instance,
so Duplicate-then-edit can make siblings diverge. Before extracting specs the
dialog detects this and offers: Fork (each variant its own Class), Compile first
variant only (drop the rest, acknowledged), or Cancel. Identical instances of a
Class are NOT flagged -- they collapse silently (normal per-Class compile).

Constructs the real ``CompileDialog`` (a QDialog), so a GUI QApplication must
exist at IMPORT time. The single modal seam ``_prompt_divergence_choice`` is
stubbed so each branch is driven headlessly.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-compile-divergence-test"])

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestCompileDialogDivergence(unittest.TestCase):
    def setUp(self):
        import sys
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        # the synthetic mpynode_user module persists across tests, and across
        # scene opens in the app; reset it so fork naming starts clean.
        sys.modules.pop("mpynode_user", None)

    def _mk(self, name, cls, expr):
        from mpynode import MPyNode
        from mpynode._common.io.user_classes import synthesize, dotted_path

        synthesize(cls, "mPyNode")
        n = MPyNode.create(name=name)
        n.set_compute_expression(expr)
        n.set_py_class(dotted_path(cls))
        return n

    def _dialog(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        return CompileDialog()

    # --- content-aware dedup -------------------------------------------

    def test_dedup_is_content_aware(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        def spec(tn, compute):
            return {"suggested": {"node_type_name": tn}, "compute": compute,
                    "inputs": {}, "outputs": {}}

        # Two identical instances -> collapse silently (no diverged drop).
        u, ident, div = CompileDialog._dedup_specs_by_type(
            [spec("w", "out=1"), spec("w", "out=1")])
        self.assertEqual(len(u), 1)
        self.assertEqual(ident, ["w"])
        self.assertEqual(div, [])
        # Two divergent instances: the second is a LOSSY drop, returned whole
        # so the caller can key an acknowledgment by source_node.
        u, ident, div = CompileDialog._dedup_specs_by_type(
            [spec("w", "out=1"), spec("w", "out=2")])
        self.assertEqual(len(u), 1)
        self.assertEqual(ident, [])
        self.assertEqual([s["suggested"]["node_type_name"] for s in div], ["w"])
        self.assertEqual(div[0]["compute"], "out=2")

    # --- pre-flight branches -------------------------------------------

    def test_identical_instances_proceed_without_prompt(self):
        a = self._mk("dlgIdA", "Widget", "out = x + 1")
        b = self._mk("dlgIdB", "Widget", "out = x + 1")
        dlg = self._dialog()
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        # If the prompt is reached it's a bug -> make it fail loudly.
        dlg._prompt_divergence_choice = lambda d: self.fail(
            "prompt shown for identical instances")
        self.assertTrue(dlg._resolve_divergence(checked))
        self.assertEqual(dlg._acknowledged_diverged_nodes, set())

    def test_fork_choice_forks_the_divergent_sibling(self):
        a = self._mk("dlgForkA", "Widget", "out = x + 1")
        b = self._mk("dlgForkB", "Widget", "out = x + 2")
        dlg = self._dialog()
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        dlg._prompt_divergence_choice = lambda d: "fork"
        self.assertTrue(dlg._resolve_divergence(checked))
        # First instance keeps the Class; the diverged one is forked to Widget2.
        self.assertEqual(a.get_py_class(), "mpynode_user.Widget")
        self.assertEqual(b.get_py_class(), "mpynode_user.Widget2")
        # And the scene is now divergence-free.
        self.assertEqual(dlg._divergence_report(checked), {})

    def test_fork_skips_existing_class_names(self):
        # Widget2 already taken by an unrelated node -> fork lands on Widget3.
        self._mk("dlgTaken", "Widget2", "out = 7")
        a = self._mk("dlgFA", "Widget", "out = x + 1")
        b = self._mk("dlgFB", "Widget", "out = x + 2")
        dlg = self._dialog()
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        dlg._prompt_divergence_choice = lambda d: "fork"
        self.assertTrue(dlg._resolve_divergence(checked))
        self.assertEqual(b.get_py_class(), "mpynode_user.Widget3")

    def test_fork_skips_orphan_in_memory_class_name(self):
        # a Widget2 synthesized in memory with no scene node still counts as
        # taken, so the fork skips to Widget3; otherwise stamp_class can clash
        # on a different base and silently fail.
        from mpynode._common.io.user_classes import synthesize
        synthesize("Widget2", "mPyNode")  # orphan: no node carries it
        a = self._mk("dlgOrphA", "Widget", "out = x + 1")
        b = self._mk("dlgOrphB", "Widget", "out = x + 2")
        dlg = self._dialog()
        self.assertIn("Widget2", dlg._scene_class_names())  # union catches orphan
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        dlg._prompt_divergence_choice = lambda d: "fork"
        self.assertTrue(dlg._resolve_divergence(checked))
        self.assertEqual(b.get_py_class(), "mpynode_user.Widget3")

    def test_fork_incomplete_cancels_rather_than_lossy_compile(self):
        # a fork that can't be fully applied aborts (returns False) instead of
        # falling through to a lossy compile.
        a = self._mk("dlgIncA", "Widget", "out = x + 1")
        b = self._mk("dlgIncB", "Widget", "out = x + 2")
        dlg = self._dialog()
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        dlg._prompt_divergence_choice = lambda d: "fork"
        dlg._apply_fork_plan = lambda plan, nt: 0  # simulate a total fork failure
        dlg._warn = lambda *a, **k: None           # don't block on the modal
        self.assertFalse(dlg._resolve_divergence(checked))

    def test_representative_choice_acknowledges_loss(self):
        a = self._mk("dlgRepA", "Widget", "out = x + 1")
        b = self._mk("dlgRepB", "Widget", "out = x + 2")
        dlg = self._dialog()
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        dlg._prompt_divergence_choice = lambda d: "representative"
        self.assertTrue(dlg._resolve_divergence(checked))
        # acknowledged per node, not globally, so an unrelated type's lossy
        # drop is still warned about later.
        self.assertEqual(dlg._acknowledged_diverged_nodes,
                         {a.get_name(), b.get_name()})
        # Classes are unchanged (still one shared, diverged Class).
        self.assertEqual(a.get_py_class(), "mpynode_user.Widget")
        self.assertEqual(b.get_py_class(), "mpynode_user.Widget")

    def test_cancel_choice_aborts_without_mutation(self):
        a = self._mk("dlgCanA", "Widget", "out = x + 1")
        b = self._mk("dlgCanB", "Widget", "out = x + 2")
        dlg = self._dialog()
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        dlg._prompt_divergence_choice = lambda d: "cancel"
        self.assertFalse(dlg._resolve_divergence(checked))
        # Nothing forked.
        self.assertEqual(a.get_py_class(), "mpynode_user.Widget")
        self.assertEqual(b.get_py_class(), "mpynode_user.Widget")

    def test_classless_instances_never_flagged(self):
        # class-less nodes compile as per-instance types with no shared Class
        # to diverge within, so no prompt whatever the code says.
        from mpynode import MPyNode

        a = MPyNode.create(name="dlgLessA")
        a.set_compute_expression("out = 1")
        b = MPyNode.create(name="dlgLessB")
        b.set_compute_expression("out = 2")
        dlg = self._dialog()
        checked = [(a.get_name(), "mPyNode"), (b.get_name(), "mPyNode")]
        dlg._prompt_divergence_choice = lambda d: self.fail(
            "prompt shown for class-less nodes")
        self.assertTrue(dlg._resolve_divergence(checked))


if __name__ == "__main__":
    unittest.main()
