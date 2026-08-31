"""NDMethodsSourceEditor -- raw full-buffer round-trip over ``_methodsSource``.

Proves the single editor stores/loads the Methods source BYTE-IDENTICALLY (no
split/join), so an interleaved def / module-level source is never reordered.
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
    _QAPP = _QApplication.instance() or _QApplication(["methods-src-editor-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestMethodsSourceEditorRoundtrip(unittest.TestCase):
    def _loc(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        return MPyLocator.create(name="msEdit")

    def test_interleaved_roundtrip_byte_identical(self):
        from mpynode.ui.widgets.methods_source_editor import NDMethodsSourceEditor

        mc.file(new=True, force=True)
        loc = self._loc()
        src = "def helper(x):\n    return x\ndef m(self):\n    return helper(1)\nX = 5\n"
        loc.set_methods_source(src)

        editor = NDMethodsSourceEditor(loc)
        try:
            # Loaded verbatim (no split).
            self.assertEqual(editor.getText(), src)
            # markSaved with no edit is a no-op -> source unchanged bytes.
            editor.markSaved()
            self.assertEqual(loc.get_methods_source(), src)
            # Append a tail line, save -> stored byte-identical (NOT reordered:
            # the old class-body/module join would move helper/m/X around).
            editor.setText(src + "# tail\n")
            editor.markSaved()
            self.assertEqual(loc.get_methods_source(), src + "# tail\n")
        finally:
            editor.deleteLater()

    def test_empty_roundtrip(self):
        from mpynode.ui.widgets.methods_source_editor import NDMethodsSourceEditor

        mc.file(new=True, force=True)
        loc = self._loc()

        editor = NDMethodsSourceEditor(loc)
        try:
            self.assertEqual(editor.getText(), "")
            self.assertFalse(editor.hasUnsavedChanges())
            editor.markSaved()  # no-op
            self.assertEqual(loc.get_methods_source(), "")
        finally:
            editor.deleteLater()

    def test_store_on_syntax_error(self):
        from mpynode.ui.widgets.methods_source_editor import NDMethodsSourceEditor

        mc.file(new=True, force=True)
        loc = self._loc()

        editor = NDMethodsSourceEditor(loc)
        try:
            bad = "def broken(:\n"
            editor.setText(bad)
            editor.markSaved()
            # set_methods_source stores even invalid source (edits never lost).
            self.assertEqual(loc.get_methods_source(), bad)
        finally:
            editor.deleteLater()


if __name__ == "__main__":
    unittest.main()
