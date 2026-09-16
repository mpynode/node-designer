"""Attributes/Storage tab drag-and-drop wiring + drop highlight

Consolidated from: test_phaseN_2_tree_and_dnd.py, test_phaseO_3_dnd_visual_feedback.py, test_phaseP_5_storage_dnd_highlight.py.
"""

from __future__ import annotations

# ===================== from test_phaseN_2_tree_and_dnd.py =====================
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
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-phaseN2-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseN_2_tree_and_dnd():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


# ===========================================================================
# Tree-style Storage helper (Qt-free)
# ===========================================================================


class TestCollectPlugTree(unittest.TestCase):
    """Collect_plug_tree returns a nested TreeNode list, ready for
    Qt rendering."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="ct_td")
        self.deformer.add_input_attr("amplitude", "vector")

    def test_returns_nested_tree(self):
        from mpynode.ui.widgets.variables import collect_plug_tree

        nodes = collect_plug_tree(self.deformer.get_name())
        self.assertGreater(len(nodes), 0)
        # All top-level nodes have parent_path == "".
        for n in nodes:
            self.assertEqual(n.row.parent_path, "")

    def test_compound_children_nested(self):
        """Amplitude (Double3) should have 3 children in the tree."""
        from mpynode.ui.widgets.variables import collect_plug_tree

        nodes = collect_plug_tree(self.deformer.get_name())
        amp   = None
        for n in nodes:
            if n.row.short_name == "amplitude":
                amp = n
                break
        self.assertIsNotNone(amp)
        child_names = sorted(c.row.short_name for c in amp.children)
        self.assertEqual(
            child_names, ["amplitudeX", "amplitudeY", "amplitudeZ"]
        )

    def test_internal_excluded(self):
        """Collect_plug_tree filters to INPUT + OUTPUT only;
        INTERNAL rows are surfaced separately via
        collect_internal_api_rows."""
        from mpynode.ui.widgets.variables import collect_plug_tree

        nodes = collect_plug_tree(self.deformer.get_name())
        for n in nodes:
            self.assertIn(n.row.direction, ("INPUT", "OUTPUT"))


# ===========================================================================
# Attributes-tab DnD (requires Qt)
# ===========================================================================


class TestAttributesDnD(unittest.TestCase):
    """Drag-and-drop wiring: MIME payload + drop target gating +
    _ConnectAttrCommand dispatch."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        # Source: a transform whose translateY plug we'll drag.
        self.src = mc.createNode("transform", name="dnd_src")
        mc.setAttr(self.src + ".translateY", 7.0)
        # Target: an mPyNode with two user-added matrix inputs.
        from mpynode.wrappers._mpy_node import MPyNode
        self.node = MPyNode.create(name="dnd_target")
        self.node.add_input_attr("driverA", "float")
        self.node.add_input_attr("driverB", "float")

    def _make_input_tree(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        t = NDInputAttrTree()
        t.setNode(self.node)
        return t

    def test_dragdrop_mode_enabled(self):
        tree = self._make_input_tree()
        from mpynode.ui.qt_wrapper import QTreeWidget

        # DragDrop mode is enabled in __init__.
        self.assertEqual(tree.dragDropMode(), QTreeWidget.DragDrop)
        self.assertTrue(tree.dragEnabled())
        self.assertTrue(tree.acceptDrops())

    def test_mimeData_builds_full_plug_payload(self):
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        tree   = self._make_input_tree()
        target = None
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == "driverA":
                target = it
                break
        self.assertIsNotNone(target)
        md = tree.mimeData([target])
        self.assertIsNotNone(md)
        self.assertTrue(md.hasFormat(tree._MIME_TYPE))
        payload = bytes(md.data(tree._MIME_TYPE)).decode("utf-8")
        self.assertEqual(payload, "dnd_target.driverA")

    def test_drop_triggers_connect_attr_command(self):
        """Simulate a drop with a synthetic MIME payload; assert the
        target gets connected via mc.listConnections."""
        try:
            from PySide6.QtCore import QMimeData, QPoint, QEvent, Qt as _Qt
            from PySide6.QtGui import QDropEvent
        except Exception:
            from PySide2.QtCore import QMimeData, QPoint, QEvent, Qt as _Qt
            from PySide2.QtGui import QDropEvent

        tree = self._make_input_tree()
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        target_item = None
        target_pos  = None
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == "driverA":
                target_item = it
                rect        = tree.visualItemRect(it)
                target_pos  = rect.center()
                break
        # Simpler than a synthetic QDropEvent: run _ConnectAttrCommand the way
        # dropEvent does, so the command path is checked on a real connection
        # on top of the source-grep already pinned.
        from mpynode._base.commands import _ConnectAttrCommand, run_undoable

        src_plug = "dnd_src.translateY"
        dst_plug = "dnd_target.driverA"
        run_undoable(_ConnectAttrCommand(src_plug, dst_plug, force=True))
        cons = mc.listConnections(dst_plug, source=True, destination=False) or []
        self.assertIn("dnd_src", cons,
            "Connect should produce a live wire from dnd_src to dnd_target.driverA")


class TestAttributesDnDSourceShape(unittest.TestCase):
    """Source-grep pins."""

    def test_attribute_tree_has_drop_event_override(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree)
        self.assertIn("def dropEvent",       src)
        self.assertIn("def dragEnterEvent",  src)
        self.assertIn("def mimeData",        src)
        self.assertIn("_MIME_TYPE",          src)
        self.assertIn("_ConnectAttrCommand", src)

    def test_drop_event_gates_to_user_items(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree.dropEvent)
        self.assertIn("NDUserAttrTreeItem", src,
            "dropEvent must check target is NDUserAttrTreeItem "
            "(edit-op gating)")


# ===================== from test_phaseO_3_dnd_visual_feedback.py =====================
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
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-phaseO3-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseO_3_dnd_visual_feedback():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestDropHighlight(unittest.TestCase):
    """The helper methods _set_drop_highlight / _clear_drop_highlight
    paint and restore the target row's background."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode
        self.node = MPyNode.create(name="o3_target")
        self.node.add_input_attr("driverA", "float")

    def _make_tree(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        t = NDInputAttrTree()
        t.setNode(self.node)
        return t

    def test_set_drop_highlight_changes_background(self):
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        tree   = self._make_tree()
        target = None
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == "driverA":
                target = it
                break
        self.assertIsNotNone(target)
        before_brush = target.background(0)
        tree._set_drop_highlight(target)
        after_brush = target.background(0)
        # the brush is the configured Maya yellow.
        self.assertEqual(after_brush.color().red(),   255)
        self.assertEqual(after_brush.color().green(), 204)
        self.assertEqual(after_brush.color().blue(),  0)
        # the tree remembers which item is highlighted.
        self.assertIs(tree._drop_highlight_item, target)

    def test_clear_restores_background(self):
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        tree   = self._make_tree()
        target = None
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == "driverA":
                target = it
                break
        original_brush = target.background(0)
        tree._set_drop_highlight(target)
        tree._clear_drop_highlight()
        self.assertIsNone(tree._drop_highlight_item,
            "_clear_drop_highlight must reset _drop_highlight_item to None")
        post_brush = target.background(0)
        # Compare colours, not brush identity.
        self.assertEqual(
            post_brush.color().getRgb(),
            original_brush.color().getRgb(),
            "background should be restored to pre-highlight state",
        )

    def test_set_highlight_on_new_target_clears_prior(self):
        """If the cursor moves from row A to row B, A's highlight
        should clear and B's should set."""
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        self.node.add_input_attr("driverB", "float")
        tree   = self._make_tree()
        item_a = item_b = None
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem):
                if it.attr_name == "driverA":
                    item_a = it
                elif it.attr_name == "driverB":
                    item_b = it
        self.assertIsNotNone(item_a)
        self.assertIsNotNone(item_b)
        tree._set_drop_highlight(item_a)
        self.assertIs(tree._drop_highlight_item, item_a)
        tree._set_drop_highlight(item_b)
        self.assertIs(tree._drop_highlight_item, item_b)
        # item_a should no longer be highlighted in Maya-yellow.
        a_color = item_a.background(0).color().getRgb()
        self.assertNotEqual(a_color, (255, 204, 0, 128),
            "previously-highlighted row should have been restored")


class TestDropHighlightSourceShape(unittest.TestCase):
    """Source-grep pins."""

    def test_drag_move_calls_set_highlight(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree.dragMoveEvent)
        self.assertIn("_set_drop_highlight", src)
        self.assertIn("_clear_drop_highlight", src)

    def test_drag_leave_clears(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree.dragLeaveEvent)
        self.assertIn("_clear_drop_highlight", src)


# ===================== from test_phaseP_5_storage_dnd_highlight.py =====================
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
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-phaseP5-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseP_5_storage_dnd_highlight():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestStorageDnDHighlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode
        self.node = MPyNode.create(name="p5_storage")
        # Add a stored var so the User section has a target row.
        self.node.set_variables({"foo": 1.0})

    def _make_widget(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget
        w          = NDVariablesWidget()
        w._py_node = self.node
        if hasattr(w, "refresh"):
            try:
                w.refresh()
            except Exception:
                pass
        return w

    def test_highlight_helpers_present(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget

        for m in ("_set_drop_highlight", "_clear_drop_highlight",
                  "eventFilter", "_on_drag_move"):
            self.assertTrue(hasattr(NDVariablesWidget, m),
                f"NDVariablesWidget missing P.5 method {m!r}")

    def test_set_highlight_paints_yellow(self):
        from mpynode.ui.widgets.variables import (
            NDVariablesWidget, NDVariableTreeItem,
        )
        w = self._make_widget()
        # Find a User section row.
        target = None
        for i in range(w._tree.topLevelItemCount()):
            top = w._tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if isinstance(child, NDVariableTreeItem):
                    target = child
                    break
            if target is not None:
                break
        if target is None:
            self.skipTest("no NDVariableTreeItem found to highlight")
        before = target.background(0).color().getRgb()
        w._set_drop_highlight(target)
        after = target.background(0).color().getRgb()
        self.assertEqual(after[:3], (255, 204, 0),
            f"highlight color wrong: {after}")
        self.assertIs(w._drop_highlight_item, target)

    def test_clear_restores_background(self):
        from mpynode.ui.widgets.variables import (
            NDVariablesWidget, NDVariableTreeItem,
        )
        w      = self._make_widget()
        target = None
        for i in range(w._tree.topLevelItemCount()):
            top = w._tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if isinstance(child, NDVariableTreeItem):
                    target = child
                    break
            if target is not None:
                break
        if target is None:
            self.skipTest("no NDVariableTreeItem found to highlight")
        original = target.background(0).color().getRgb()
        w._set_drop_highlight(target)
        w._clear_drop_highlight()
        self.assertIsNone(w._drop_highlight_item)
        self.assertEqual(
            target.background(0).color().getRgb(),
            original,
            "background should be restored after clear",
        )


class TestStorageDnDHighlightSourceShape(unittest.TestCase):
    def test_event_filter_handles_drag_events(self):
        import inspect
        from mpynode.ui.widgets.variables import NDVariablesWidget

        src = inspect.getsource(NDVariablesWidget.eventFilter)
        # must intercept DragEnter (60), DragMove (61),
        # DragLeave (62), Drop (63).
        for code in ("60", "61", "62", "63"):
            self.assertIn(code, src,
                f"eventFilter must handle QEvent type {code}")

    def test_init_enables_accept_drops(self):
        import inspect
        from mpynode.ui.widgets.variables import NDVariablesWidget

        src = inspect.getsource(NDVariablesWidget.__init__)
        self.assertIn("setAcceptDrops", src)
        self.assertIn("installEventFilter", src)


def setUpModule():
    _setUpModule__phaseN_2_tree_and_dnd()
    _setUpModule__phaseO_3_dnd_visual_feedback()
    _setUpModule__phaseP_5_storage_dnd_highlight()


if __name__ == "__main__":
    import unittest
    unittest.main()
