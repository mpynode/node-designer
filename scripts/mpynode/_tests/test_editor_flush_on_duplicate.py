"""T54: a NATIVE Maya duplicate must not lose typed-but-unsaved editor text.

The per-tier code editors commit to a node's DG plugs only on an explicit Save.
The Node Designer's own Duplicate / Convert / Export-to-.mpn handlers already
call ``NDScriptTabWidget.saveTabsForNode`` first, but Maya's own duplicate
(Ctrl+D, ``cmds.duplicate``) goes straight to the plugs and copies whatever was
last SAVED -- so a node the user has been typing in duplicates with a stale or
empty expression.

The fix is an ``MModelMessage`` before-duplicate interception owned by the tab
widget: it flushes dirty tabs to their plugs just before Maya reads them.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["editor-flush-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _wrap(name):
    import mpynode

    return mpynode.wrap_node(name)


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestFlushOnNativeDuplicate(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.src = MPyNode.create(name="typedNode")
        self.src.add_input_attr("alpha", "float", default_value=2.0)
        self.src.add_output_attr("out", "float")
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            # Unhook deterministically: deleteLater alone leaves the Maya
            # callback live until the deferred delete is processed, and a
            # leftover widget would flush into the NEXT test's duplicate.
            try:
                w.detachSceneCallbacks()
            except Exception:
                pass
            try:
                w.deleteLater()
            except Exception:
                pass
        if _QAPP is not None:
            _QAPP.processEvents()

    def _widget_with_tab(self, node):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        w = NDScriptTabWidget()
        self._widgets.append(w)
        w.addOrRaiseTab(node)
        return w

    def _compute_plug(self, name):
        return mc.getAttr(name + "._computeSource") or ""

    def test_native_duplicate_carries_typed_but_unsaved_compute(self):
        """The headline defect: Ctrl+D on a node being typed in."""
        name = self.src.get_name()
        w = self._widget_with_tab(self.src)
        tab = w.getAllTabs()[0]
        typed = "out = alpha * 3.0  # typed, never saved"
        tab.setText(typed)
        self.assertTrue(tab.hasUnsavedChanges())
        self.assertNotIn(typed, self._compute_plug(name))

        mc.select(name, replace=True)
        dups = mc.duplicate() or []
        self.assertEqual(len(dups), 1)
        self.assertEqual(_wrap(dups[0]).get_compute_expression(), typed)

    def test_flush_is_load_bearing(self):
        """Neutralise the flush and the SAME duplicate loses the text -- proof
        the interception, not something else, is what carries it."""
        from mpynode.ui.widgets import script_tab as st

        name = self.src.get_name()
        w = self._widget_with_tab(self.src)
        tab = w.getAllTabs()[0]
        typed = "out = alpha * 4.0"
        tab.setText(typed)

        original = st.NDScriptTabWidget.flushDirtyTabsBeforeDuplicate
        st.NDScriptTabWidget.flushDirtyTabsBeforeDuplicate = lambda self: 0
        try:
            mc.select(name, replace=True)
            dups = mc.duplicate() or []
            self.assertNotEqual(
                _wrap(dups[0]).get_compute_expression(), typed)
        finally:
            st.NDScriptTabWidget.flushDirtyTabsBeforeDuplicate = original

        mc.select(name, replace=True)
        dups = mc.duplicate() or []
        self.assertEqual(_wrap(dups[0]).get_compute_expression(), typed)

    def test_flush_marks_the_tab_saved(self):
        """After the flush the tab is no longer dirty -- otherwise the very next
        Save would re-run and re-log a save with nothing to do."""
        name = self.src.get_name()
        w = self._widget_with_tab(self.src)
        tab = w.getAllTabs()[0]
        tab.setText("out = alpha * 5.0")
        mc.select(name, replace=True)
        mc.duplicate()
        self.assertFalse(tab.hasUnsavedChanges())

    def test_clean_tabs_are_not_resaved(self):
        """No dirty tab -> nothing is written, so a duplicate of an untouched
        node costs no extra undo entry and logs no phantom save."""
        name = self.src.get_name()
        w = self._widget_with_tab(self.src)
        self.assertFalse(w.getAllTabs()[0].hasUnsavedChanges())
        self.assertEqual(w.flushDirtyTabsBeforeDuplicate(), 0)

    def test_syntax_error_flush_never_opens_a_modal(self):
        """A half-typed expression is the NORMAL state at duplicate time. The
        explicit-Save popup must not fire here: a modal inside Maya's
        before-duplicate callback blocks the operation it is nested in."""
        from mpynode.ui import qt_wrapper

        name = self.src.get_name()
        w = self._widget_with_tab(self.src)
        tab = w.getAllTabs()[0]
        broken = "out = alpha *"
        tab.setText(broken)

        calls = []
        original = qt_wrapper.QMessageBox.warning
        qt_wrapper.QMessageBox.warning = staticmethod(
            lambda *a, **k: calls.append(a))
        try:
            mc.select(name, replace=True)
            mc.duplicate()
        finally:
            qt_wrapper.QMessageBox.warning = original
        self.assertEqual(calls, [])
        # The text still reached the plug -- quiet, not skipped.
        self.assertEqual(self._compute_plug(name), broken)

    def test_callback_is_removed_when_the_widget_goes_away(self):
        """A dangling Maya callback into a deleted QWidget is a crash. Closing
        the editor must unhook it."""
        name = self.src.get_name()
        w = self._widget_with_tab(self.src)
        tab = w.getAllTabs()[0]
        tab.setText("out = alpha * 6.0")
        w.detachSceneCallbacks()
        mc.select(name, replace=True)
        mc.duplicate()
        # Unhooked -> the stale plug is what got copied (no flush, no crash).
        self.assertEqual(self._compute_plug(name), "")

    def test_detach_is_idempotent(self):
        w = self._widget_with_tab(self.src)
        w.detachSceneCallbacks()
        w.detachSceneCallbacks()

    def test_undo_after_a_flushed_duplicate_is_sane(self):
        """The flush runs an MPxCommand from inside Maya's own before-duplicate
        callback, i.e. nested in the duplicate it precedes. Undo must still drop
        the copy and leave the source alone, and redo must bring it back."""
        name = self.src.get_name()
        mc.undoInfo(state=True, infinity=True)
        w = self._widget_with_tab(self.src)
        tab = w.getAllTabs()[0]
        typed = "self.out = self.alpha * 7.0"
        tab.setText(typed)

        mc.select(name, replace=True)
        dups = mc.duplicate() or []
        self.assertTrue(mc.objExists(dups[0]))

        mc.undo()
        self.assertFalse(mc.objExists(dups[0]),
                         "undo must remove the duplicate")
        self.assertTrue(mc.objExists(name), "the source must survive")
        mc.redo()
        self.assertTrue(mc.objExists(dups[0]), "redo must bring it back")
        self.assertEqual(self._compute_plug(dups[0]), typed)


if __name__ == "__main__":
    unittest.main()
