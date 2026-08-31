"""Compile dialog: no per-cell focus rectangle.

The node table is ``NoSelection``, but clicking a text cell still sets the
view's *current index*, and the platform style paints a focus square around
that ONE cell -- a highlight the user never asked for (inclusion is driven by
the Compile checkbox, not by a current cell). A ``_NoFocusDelegate`` strips
``QStyle.State_HasFocus`` so no per-cell highlight is ever painted.

Constructs the real ``CompileDialog`` (a QDialog), so a GUI QApplication must
exist at IMPORT time -- mirrors the other UI test modules.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest

_QAPP = None
QStyle = None
QStyleOptionViewItem = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
    from PySide6.QtWidgets import QStyle, QStyleOptionViewItem
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
        from PySide2.QtWidgets import QStyle, QStyleOptionViewItem
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-compile-cellfocus-test"])

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestCellFocusHighlight(unittest.TestCase):
    def setUp(self):
        import sys
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        sys.modules.pop("mpynode_user", None)

    def _dialog(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        return CompileDialog()

    def test_table_installs_no_focus_delegate(self):
        from mpynode.ui.dialogs.compile_dialog import _NoFocusDelegate

        dlg = self._dialog()
        # The table's item delegate strips the per-cell focus rectangle.
        self.assertIsInstance(dlg._table.itemDelegate(), _NoFocusDelegate)

    def test_delegate_strips_cell_focus_state(self):
        from mpynode import MPyNode

        MPyNode.create(name="focusNode")
        dlg = self._dialog()
        delegate = dlg._table.itemDelegate()
        index = dlg._table.model().index(0, 0)
        self.assertTrue(index.isValid(), "row 0 should be populated")
        opt = QStyleOptionViewItem()
        opt.state |= QStyle.State_HasFocus  # the view sets this on the current cell
        delegate.initStyleOption(opt, index)
        # After the delegate primes the option, the focus bit is gone -> the
        # style paints no per-cell focus square.
        self.assertFalse(bool(opt.state & QStyle.State_HasFocus),
                         "per-cell focus rectangle should be stripped")


if __name__ == "__main__":
    unittest.main()
