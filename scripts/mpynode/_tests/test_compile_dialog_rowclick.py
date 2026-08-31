"""Compile dialog: clicking anywhere on a row toggles its Compile checkbox.

The Compile checkbox is a small centered widget that is fiddly to hit, so a
click anywhere on a row's TEXT cells now toggles it (and thus the whole-row
highlight). Clicks on the two checkbox-widget columns (Compile, Data) are left
to those checkboxes' own handlers so they are never double-toggled.

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
    _QAPP = _QApp.instance() or _QApp(["nd-compile-rowclick-test"])

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestRowClickTogglesCompile(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_click_text_cell_toggles_compile_and_membership(self):
        from mpynode import MPyNode
        from mpynode.ui.dialogs.compile_dialog import CompileDialog, _COL_NODE

        MPyNode.create(name="rowClick1")
        dlg = CompileDialog()
        row = 0
        name = dlg._scene_nodes[row][0]  # _scene_nodes holds (name, type) tuples
        cb = dlg._compile_checkbox(row)
        self.assertIsNotNone(cb)
        # Unchecked by default -> not in the bundle set.
        self.assertFalse(cb.isChecked())
        self.assertNotIn(name, dlg._checked)
        # A click on a TEXT cell turns the checkbox on + adds the node.
        dlg._on_row_cell_clicked(row, _COL_NODE)
        self.assertTrue(cb.isChecked())
        self.assertIn(name, dlg._checked)
        # A second click turns it back off (toggle) + removes the node.
        dlg._on_row_cell_clicked(row, _COL_NODE)
        self.assertFalse(cb.isChecked())
        self.assertNotIn(name, dlg._checked)

    def test_click_on_checkbox_columns_not_double_toggled(self):
        from mpynode import MPyNode
        from mpynode.ui.dialogs.compile_dialog import (
            CompileDialog, _COL_CHECK, _COL_PERSIST)

        MPyNode.create(name="rowClick2")
        dlg = CompileDialog()
        cb = dlg._compile_checkbox(0)
        before = cb.isChecked()
        # The row handler ignores the two checkbox-widget columns (those clicks
        # are handled by the checkboxes themselves -> no double toggle).
        dlg._on_row_cell_clicked(0, _COL_CHECK)
        dlg._on_row_cell_clicked(0, _COL_PERSIST)
        self.assertEqual(cb.isChecked(), before)


if __name__ == "__main__":
    unittest.main()
