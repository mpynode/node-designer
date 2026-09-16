"""Compile dialog: class-less nodes are refused a silent compile.

A node with no Class would derive its compiled type from its (renameable)
instance name -- the original identity footgun. Before extracting specs,
``_on_compile`` runs ``_resolve_classless``: every checked class-less SCENE node
is either NAMED a Class (prompt -> synthesize + stamp) or EXCLUDED from this
compile. So a class-less node never silently compiles to an instance-name type.

Constructs the real ``CompileDialog`` (a QDialog), so a GUI QApplication must
exist at IMPORT time -- mirrors the other UI test modules.
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
    _QAPP = _QApp.instance() or _QApp(["nd-classless-gate-test"])

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _class_of(name):
    from mpynode.wrappers._mpy_node import _read_py_class

    return _read_py_class(name) or ""


class TestClasslessCompileGate(unittest.TestCase):
    def setUp(self):
        import sys
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        sys.modules.pop("mpynode_user", None)

    def _dialog(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        return CompileDialog()

    def _classed(self, name, cls):
        from mpynode import MPyNode
        from mpynode._common.io.user_classes import synthesize, dotted_path

        synthesize(cls, "mPyNode")
        n = MPyNode.create(name=name)
        n.set_py_class(dotted_path(cls))
        return n

    # ---- _resolve_classless unit behavior --------------------------------

    def test_classless_node_named_and_stamped(self):
        from mpynode import MPyNode

        n   = MPyNode.create(name="lonely")  # class-less
        dlg = self._dialog()
        dlg._checked               = {n.get_name()}
        dlg._prompt_class_name_for = lambda name: "Widget"
        proceed = dlg._resolve_classless(dlg._checked_nodes())
        self.assertTrue(proceed)
        # Stamped its canonical importable Class; still checked.
        self.assertEqual(_class_of(n.get_name()), "mpynode_user.Widget")
        self.assertIn(n.get_name(), dlg._checked)

    def test_classless_cancel_excludes_node(self):
        from mpynode import MPyNode

        n                          = MPyNode.create(name="lonely2")
        dlg                        = self._dialog()
        dlg._checked               = {n.get_name()}
        dlg._prompt_class_name_for = lambda name: None  # user cancelled
        dlg._resolve_classless(dlg._checked_nodes())
        # Excluded from this compile; still class-less (untouched).
        self.assertNotIn(n.get_name(), dlg._checked)
        self.assertEqual(_class_of(n.get_name()), "")

    def test_classed_node_is_not_prompted(self):
        n   = self._classed("clsNode", "Gizmo")
        dlg = self._dialog()
        dlg._checked = {n.get_name()}
        calls = []
        dlg._prompt_class_name_for = lambda name: calls.append(name) or "X"
        dlg._resolve_classless(dlg._checked_nodes())
        self.assertEqual(calls, [])  # never prompted
        self.assertEqual(_class_of(n.get_name()), "mpynode_user.Gizmo")
        self.assertIn(n.get_name(), dlg._checked)

    def test_invalid_name_excludes_node(self):
        from mpynode import MPyNode

        n   = MPyNode.create(name="lonely3")
        dlg = self._dialog()
        dlg._checked               = {n.get_name()}
        dlg._prompt_class_name_for = lambda name: "notPascal"  # lower-first
        warned = {}
        dlg._warn = lambda title, text: warned.setdefault("t", title)
        dlg._resolve_classless(dlg._checked_nodes())
        self.assertNotIn(n.get_name(), dlg._checked)
        self.assertEqual(_class_of(n.get_name()), "")
        self.assertTrue(warned)  # user was told why it was skipped

    # ---- _on_compile integration -----------------------------------------

    def test_compile_aborts_when_only_classless_declined(self):
        from mpynode import MPyNode

        n                          = MPyNode.create(name="onlyClassless")
        dlg                        = self._dialog()
        dlg._checked               = {n.get_name()}
        dlg._prompt_class_name_for = lambda name: None         # decline
        dlg._warn                  = lambda title, text: None  # swallow the "Nothing to Compile"
        dlg._on_compile()
        # Nothing left checked -> aborted before a controller ever started.
        self.assertIsNone(dlg._controller)
        self.assertFalse(dlg._busy)
        self.assertEqual(_class_of(n.get_name()), "")  # untouched

    def test_compile_stops_after_naming_class_awaiting_second_click(self):
        from mpynode import MPyNode

        n   = MPyNode.create(name="willName")
        dlg = self._dialog()
        dlg._checked               = {n.get_name()}
        dlg._prompt_class_name_for = lambda name: "Widget"
        order = []
        # Would run AFTER the naming gate; must NOT be reached this click.
        dlg._resolve_divergence = lambda checked: (order.append("div"), False)[1]
        warned                  = {}
        dlg._warn               = lambda title, text: warned.setdefault("title", title)
        dlg._on_compile()
        # Naming a Class must NOT auto-compile: the name is stamped, the run
        # stops before divergence, the node stays checked, and the user is
        # told to press Compile again.
        self.assertEqual(order, [])                # never reached divergence
        self.assertEqual(_class_of(n.get_name()), "mpynode_user.Widget")
        self.assertIsNone(dlg._controller)         # no compile started
        self.assertIn(n.get_name(), dlg._checked)  # still checked for round 2
        self.assertTrue(warned)                    # told to click again

    def test_compile_with_all_classed_proceeds_to_divergence(self):
        # the second-click rule applies only when a Class was just named. With
        # everything already classed the gate names nothing, so the compile
        # flows straight to the divergence pre-flight.
        n   = self._classed("alreadyClassed", "Gizmo")
        dlg = self._dialog()
        dlg._checked = {n.get_name()}
        order = []
        dlg._resolve_divergence = lambda checked: (order.append("div"), False)[1]
        dlg._on_compile()
        self.assertEqual(order, ["div"])                 # proceeded as before
        self.assertIsNone(dlg._controller)


if __name__ == "__main__":
    unittest.main()
