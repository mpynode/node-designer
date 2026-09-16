"""``NDVariablesWidget.revealVariable`` -- the click-through from the Script
tab's API view.

The API view lists persistent variables by NAME with their data abstracted (a
board of points, an animated GIF, a waveform never gets expanded inline), so
the value itself is only ever shown on the Variables tab. Clicking a variable
there raises this tab and reveals the row.

The contract that matters is the negative one: revealing is a VIEW operation.
It must report honestly when there is no row, and it must never create one --
a click that declared a variable as a side effect would silently change what
the node saves.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-varreveal-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _qapp_available():
    return _QAPP is not None


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestRevealVariable(unittest.TestCase):
    def _node(self, name="varReveal"):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        return MPyNode.create(name=name)

    def _widget(self, py_node):
        from mpynode.ui.widgets.variables import NDVariablesWidget

        w = NDVariablesWidget()
        w.setPyNode(py_node)
        return w

    def test_reveals_a_persistent_variable(self):
        n = self._node()
        n.add_variable("board", persistent=True)
        w = self._widget(n)
        try:
            self.assertTrue(w.revealVariable("board"))
            cur = w._tree.currentItem()
            self.assertIsNotNone(cur)
            self.assertEqual(getattr(cur, "var_name", None), "board")
        finally:
            w.deleteLater()

    def test_reveals_a_temporary_variable(self):
        n = self._node()
        n.add_variable("scratch", persistent=False)
        w = self._widget(n)
        try:
            self.assertTrue(w.revealVariable("scratch"))
            self.assertEqual(
                getattr(w._tree.currentItem(), "var_name", None), "scratch")
        finally:
            w.deleteLater()

    def test_absent_name_reports_false_and_creates_nothing(self):
        n = self._node()
        w = self._widget(n)
        try:
            before = set(n.get_variable_names() or [])
            self.assertFalse(w.revealVariable("neverDeclared"))
            self.assertEqual(set(n.get_variable_names() or []), before)
            self.assertNotIn("neverDeclared",
                             (n.get_variables() or {}))
        finally:
            w.deleteLater()

    def test_no_node_reports_false_and_does_not_raise(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget

        w = NDVariablesWidget()
        try:
            self.assertFalse(w.revealVariable("anything"))
        finally:
            w.deleteLater()

    def test_reveal_expands_a_collapsed_section(self):
        # scrollToItem is a no-op on a child of a collapsed section, so the
        # reveal has to expand it or the row is "selected" off-screen.
        n = self._node()
        n.add_variable("board", persistent=True)
        w = self._widget(n)
        try:
            sec = w._persistent_section
            self.assertIsNotNone(sec)
            sec.setExpanded(False)
            self.assertTrue(w.revealVariable("board"))
            self.assertTrue(sec.isExpanded())
        finally:
            w.deleteLater()

    def test_signal_relays_from_the_api_view_to_the_tab_widget(self):
        # The click has to travel NDApiView -> NDScriptTabContent ->
        # NDScriptTabWidget -> designer.revealVariable. Each hop is a separate
        # connect, so test the chain rather than the endpoints.
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        n = self._node()
        n.add_variable("board", persistent=True)
        content = NDScriptTabContent(n)
        seen    = []
        content.revealVariableRequested.connect(seen.append)
        try:
            content._api_view.variableActivated.emit("board")
            self.assertEqual(seen, ["board"])
        finally:
            content.deleteLater()

    def test_designer_wires_the_relay_to_reveal(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        self.assertTrue(hasattr(NDScriptTabWidget, "revealVariableRequested"))
        src = inspect.getsource(NDMainWindow._wire_signals)
        self.assertIn("revealVariableRequested.connect", src)
        self.assertIn("self.revealVariable", src)
        self.assertTrue(callable(NDMainWindow.revealVariable))

    def test_select_user_item_reports_the_match(self):
        # revealVariable needs to know WHETHER a row matched; the helper used
        # to always return None, and its one other caller ignores the result.
        n = self._node()
        n.add_variable("board", persistent=True)
        w = self._widget(n)
        try:
            self.assertIsNotNone(w._select_user_item("board"))
            self.assertIsNone(w._select_user_item("nope"))
        finally:
            w.deleteLater()


if __name__ == "__main__":
    unittest.main()
