"""Compile dialog: 7-column layout + persistent-data bake confirm.

Columns are now **Compile · Node Name · Class · Source · Data · Node Type ·
Status**:
 * **Class** = Option-A notation (``Class(Parent)`` classed, ``Parent()``
   class-less) -- the same the scene tree shows.
 * **Node Type** = the DERIVED compiled type the bundle registers
   (``derive_class_identity(class_path or name)['node_type_name']`` = camelCase
   of the Class when classed; the instance-derived type when class-less), NOT the
   base native type.

When a checked node carries persistent stored data (its Data box auto-checks),
compiling asks the user to confirm the bake.

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
    _QAPP = _QApp.instance() or _QApp(["nd-compile-columns-test"])

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestColumnLayout(unittest.TestCase):
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

    def _row_of(self, dlg, node_name):
        for i, (nm, _t) in enumerate(dlg._scene_nodes):
            if nm == node_name:
                return i
        raise AssertionError("row not found for %r" % node_name)

    def test_seven_columns_in_order(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self.assertEqual(
            (cd._COL_CHECK, cd._COL_NODE, cd._COL_CLASS, cd._COL_SOURCE,
             cd._COL_PERSIST, cd._COL_TYPE, cd._COL_STATUS),
            (0, 1, 2, 3, 4, 5, 6))
        dlg = self._dialog()
        self.assertEqual(dlg._table.columnCount(), 7)
        labels = [dlg._table.horizontalHeaderItem(i).text() for i in range(7)]
        self.assertEqual(
            labels,
            ["Compile", "Node Name", "Class", "Source", "Data", "Node Type",
             "Status"])

    def test_classed_row_class_and_node_type(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        n = self._classed("dlgColA", "Widget")
        dlg = self._dialog()
        row = self._row_of(dlg, n.get_name())
        self.assertEqual(dlg._table.item(row, cd._COL_CLASS).text(),
                         "Widget(MPyNode)")
        self.assertEqual(dlg._table.item(row, cd._COL_TYPE).text(), "widget")

    def test_node_type_is_derived_not_native(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        n = self._classed("dlgColB", "ProcrustesConstraint")
        dlg = self._dialog()
        row = self._row_of(dlg, n.get_name())
        # Node Type = the derived compiled type, NOT the base native type.
        self.assertEqual(dlg._table.item(row, cd._COL_TYPE).text(),
                         "procrustesConstraint")
        self.assertNotEqual(dlg._table.item(row, cd._COL_TYPE).text(), "mPyNode")

    def test_classless_row_shows_parent_and_instance_type(self):
        from mpynode import MPyNode
        from mpynode.ui.dialogs import compile_dialog as cd

        n = MPyNode.create(name="lonely")  # class-less
        dlg = self._dialog()
        row = self._row_of(dlg, n.get_name())
        self.assertEqual(dlg._table.item(row, cd._COL_CLASS).text(), "MPyNode()")
        # class-less: the registered type comes from the instance name, per
        # spec_extractor's class_path-or-name fallback.
        self.assertEqual(dlg._table.item(row, cd._COL_TYPE).text(), "lonely")

    def test_classless_file_row_shows_parent_only(self):
        # A class-less .mpn (no class_path) renders "Parent()" like a
        # class-less scene node, not a "Class(Parent)" reverse-engineered
        # from the instance-derived node type.
        dlg = self._dialog()
        dlg._file_rows = {
            "myLoc": ("/x/myLoc.mpn", "mPyLocator", False, "myLoc", "")}
        self.assertEqual(dlg._row_class_label("myLoc", "mPyLocator"),
                         "MPyLocator()")

    def test_classed_file_row_shows_class_and_type(self):
        # A classed .mpn carries its Class short name -> "Class(Parent)", and
        # Node Type still shows the stored compiled type.
        dlg = self._dialog()
        dlg._file_rows = {
            "rig": ("/x/rig.mpn", "mPyNode", False, "wheel", "Wheel")}
        self.assertEqual(dlg._row_class_label("rig", "mPyNode"), "Wheel(MPyNode)")
        self.assertEqual(dlg._row_node_type("rig", "mPyNode"), "wheel")


class TestPersistentBakeConfirm(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _dialog(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        return CompileDialog()

    def _classify(self, n, cls="BakeCls"):
        # Give the node a Class so the class-less naming gate is a no-op:
        # these tests exercise the bake confirm.
        from mpynode._common.io.user_classes import synthesize, dotted_path

        synthesize(cls, "mPyNode")
        n.set_py_class(dotted_path(cls))

    def test_nodes_baking_persistent_lists_only_data_nodes(self):
        dlg = self._dialog()
        dlg._scene_nodes = [("hasData", "mPyNode"), ("noData", "mPyNode")]
        dlg._checked = {"hasData", "noData"}
        dlg._node_has_persistent = lambda name: name == "hasData"
        self.assertEqual(
            dlg._nodes_baking_persistent(dlg._checked_nodes()), ["hasData"])

    def test_nodes_baking_respects_uncheck_and_global_ignore(self):
        dlg = self._dialog()
        dlg._scene_nodes = [("hasData", "mPyNode")]
        dlg._checked = {"hasData"}
        dlg._node_has_persistent = lambda name: True
        # An explicit per-node uncheck -> not baking.
        dlg._persistent_unchecked = {"hasData"}
        self.assertEqual(dlg._nodes_baking_persistent(dlg._checked_nodes()), [])
        # The global "Ignore persistent data" -> nothing bakes.
        dlg._persistent_unchecked = set()
        dlg._ignore_persistent_check.setChecked(True)
        self.assertEqual(dlg._nodes_baking_persistent(dlg._checked_nodes()), [])

    def test_compile_aborts_when_bake_not_confirmed(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="bakeCancel")
        self._classify(n)
        dlg = self._dialog()
        dlg._checked = {n.get_name()}
        dlg._node_has_persistent = lambda name: True  # force "has data"
        seen = {}
        dlg._confirm_bake_persistent = (
            lambda names: (seen.__setitem__("names", list(names)) or False))
        dlg._on_compile()
        # the confirm named exactly the baking node, and the compile aborted
        # before any controller started.
        self.assertEqual(seen.get("names"), [n.get_name()])
        self.assertIsNone(dlg._controller)
        self.assertFalse(dlg._busy)

    def test_bake_confirm_runs_before_divergence(self):
        # the bake confirm runs BEFORE _resolve_divergence: divergence's
        # "Fork" mutates the scene, so an abortable step after it would leave
        # a forked-but-nothing-compiled scene.
        from mpynode import MPyNode

        n = MPyNode.create(name="orderNode")
        self._classify(n)
        dlg = self._dialog()
        dlg._checked = {n.get_name()}
        dlg._node_has_persistent = lambda name: True
        order = []
        dlg._confirm_bake_persistent = (
            lambda names: (order.append("bake"), False)[1])
        dlg._resolve_divergence = (
            lambda checked: (order.append("divergence"), True)[1])
        dlg._on_compile()
        self.assertEqual(order, ["bake"])  # divergence never reached

    def test_compile_clears_stale_persistent_cache_before_confirm(self):
        # A node can gain persistent data while the non-modal dialog stays
        # open, so _on_compile clears the render-time _has_persistent cache
        # and re-reads live, or the bake confirm never fires.
        from mpynode import MPyNode

        n = MPyNode.create(name="staleCache")
        n.set_variable("v", 1, persistent=True)  # really carries data
        self._classify(n)
        dlg = self._dialog()
        dlg._checked = {n.get_name()}
        dlg._has_persistent = {n.get_name(): False}  # STALE: says "no data"
        seen = {}
        dlg._confirm_bake_persistent = (
            lambda names: (seen.__setitem__("names", list(names)) or False))
        dlg._on_compile()
        # The stale cache was cleared -> live re-read sees the var -> confirm fired.
        self.assertEqual(seen.get("names"), [n.get_name()])
        self.assertIsNone(dlg._controller)


if __name__ == "__main__":
    unittest.main()
