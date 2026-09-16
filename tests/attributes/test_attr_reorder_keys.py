"""Phase B follow-up: rows must be draggable, and a keyboard reorder
(Shift+Up / Shift+Down on the selected user attr) as a trackpad-friendly
alternative that confirms the reorder mechanism without a mouse drag.
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
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-reorder-keys"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _qt() -> bool:
    return _QAPP is not None


def _node(name="keyReord#"):
    from mpynode.wrappers._mpy_node import MPyNode

    n = MPyNode.create(name=name)
    for nm in ("alpha", "beta", "gamma", "delta"):
        n.add_input_attr(nm, "float")
    return n


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestUserRowDraggable(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_user_attr_item_has_drag_flag(self):
        from mpynode.ui.qt_wrapper import Qt
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDUserAttrTreeItem,
        )
        tree = NDInputAttrTree()
        tree.setNode(_node())
        items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        users = [it for it in items if isinstance(it, NDUserAttrTreeItem)]
        self.assertTrue(users, "no user-attr rows built")
        for it in users:
            # bool(flags & flag) is the cross-version idiom (PySide6 ItemFlag is
            # not int()-able; PySide2 ItemFlags is).
            self.assertTrue(bool(it.flags() & Qt.ItemIsDragEnabled),
                            "user attr row %r is not draggable" % it.attr_name)
        tree.deleteLater()


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestKeyboardReorder(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        self.tree = NDInputAttrTree()
        self.node = _node()
        self.tree.setNode(self.node)

    def tearDown(self):
        try:
            self.tree.deleteLater()
        except Exception:
            pass

    def _select(self, name):
        self.tree._select_user_attr(name)

    def _order(self):
        return list(self.node.get_input_attr_map().keys())

    def test_move_down_swaps_with_next(self):
        self._select("beta")
        self.assertTrue(self.tree._move_selected(1))
        self.assertEqual(self._order(), ["alpha", "gamma", "beta", "delta"])
        # selection follows the moved attr (so repeated presses keep moving it).
        self.assertEqual(self.tree.currentItem().attr_name, "beta")

    def test_move_up_swaps_with_prev(self):
        self._select("gamma")
        self.assertTrue(self.tree._move_selected(-1))
        self.assertEqual(self._order(), ["alpha", "gamma", "beta", "delta"])

    def test_move_up_at_top_is_noop(self):
        self._select("alpha")
        self.assertFalse(self.tree._move_selected(-1))
        self.assertEqual(self._order(), ["alpha", "beta", "gamma", "delta"])

    def test_move_down_at_bottom_is_noop(self):
        self._select("delta")
        self.assertFalse(self.tree._move_selected(1))
        self.assertEqual(self._order(), ["alpha", "beta", "gamma", "delta"])

    def test_move_refused_during_playback(self):
        import mpynode.ui.widgets.attributes as attrmod
        self._select("beta")
        orig                         = attrmod._timeline_is_playing
        attrmod._timeline_is_playing = lambda: True
        try:
            self.assertFalse(self.tree._move_selected(1))
        finally:
            attrmod._timeline_is_playing = orig
        self.assertEqual(self._order(), ["alpha", "beta", "gamma", "delta"])

    def test_keypress_shift_down_moves(self):
        from mpynode.ui.qt_wrapper import Qt
        try:
            from PySide6.QtGui import QKeyEvent
            from PySide6.QtCore import QEvent
        except Exception:
            from PySide2.QtGui import QKeyEvent
            from PySide2.QtCore import QEvent
        self._select("alpha")
        ev = QKeyEvent(QEvent.KeyPress, Qt.Key_Down, Qt.ShiftModifier)
        self.tree.keyPressEvent(ev)
        self.assertEqual(self._order(), ["beta", "alpha", "gamma", "delta"])


class TestKeyboardWiring(unittest.TestCase):
    def test_keypressevent_routes_to_move_selected(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        src = inspect.getsource(NDInputAttrTree.keyPressEvent)
        self.assertIn("_move_selected", src)
        self.assertIn("ShiftModifier", src)


if __name__ == "__main__":
    unittest.main()
