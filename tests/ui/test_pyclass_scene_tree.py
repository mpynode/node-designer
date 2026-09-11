"""Scene-tree Class display + Name/Rename/Reclassify actions (Task 8 / 6.2).

The scene tree's column 1 shows the node's canonical Class in Option A notation
(``Class(Parent)`` when classed, ``Parent()`` when class-less) rather than a
bracketed tag, and the right-click menu offers "Name Class…" (class-less) or
"Rename Class" + "Reclassify (Fork to New Class)" (classed), emitting
``nameClassRequested`` / ``reclassifyRequested``.

Importing the widget pulls Qt, so create a QApplication at IMPORT time (before
maya.standalone installs a non-GUI QCoreApplication). Mirrors the other UI test
modules.
"""

from __future__ import annotations

import inspect
import unittest

import maya.cmds as mc

# QApplication at IMPORT time -- mirrors the other UI test modules.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-pyclass-tree-test"])

from tests._setup import (
    ensure_plugins_loaded, ensure_stub_compiled_plugin, standalone_init)


def setUpModule():
    standalone_init()


class TestSceneTreeHeadersAndTag(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _tree(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        t = NDSceneTree()
        t.refresh()
        return t

    def test_headers_are_name_and_class(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        t   = NDSceneTree()
        hdr = t.headerItem()
        self.assertEqual(hdr.text(0), "Name")
        self.assertEqual(hdr.text(1), "Class")

    def test_plain_node_shows_native_type_tag(self):
        from mpynode import MPyNode

        MPyNode.create(name="treePlain1")
        t    = self._tree()
        item = t.findItem("treePlain1")
        self.assertIsNotNone(item)
        # Option A: a class-less node reads ``Parent()``.
        self.assertEqual(item.text(1), "MPyNode()")

    def test_tagged_node_shows_logical_class_tag(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="treeSub1")
        n.set_py_class("mpynode_user.BlackWhiteFile")
        t    = self._tree()
        item = t.findItem("treeSub1")
        self.assertIsNotNone(item)
        # Option A: a classed node reads ``Class(Parent)``.
        self.assertEqual(item.text(1), "BlackWhiteFile(MPyNode)")


class TestPausedChip(unittest.TestCase):
    """A node that does not evaluate (nodeState Has No Effect / Blocking --
    Convert to C++ sets it, a user may too) carries the pause chip; both chips
    are laid out against the viewport so neither can be clipped."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _item(self, name):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        t = NDSceneTree()
        t.refresh()
        item = t.findItem(name)
        self.assertIsNotNone(item)
        return item

    def test_a_hand_suspended_node_is_marked_paused_with_the_reason(self):
        from mpynode import MPyNode
        from mpynode.ui.widgets.scene_tree import _PAUSED_ROLE

        n = MPyNode.create(name="pausedProbe1")
        self.assertFalse(self._item("pausedProbe1").data(1, _PAUSED_ROLE))
        mc.setAttr(n.get_name() + ".nodeState", 2)
        item = self._item("pausedProbe1")
        self.assertTrue(item.data(1, _PAUSED_ROLE))
        self.assertIn("Not evaluating", item.toolTip(1))
        self.assertIn("Blocking", item.toolTip(1))
        mc.setAttr(n.get_name() + ".nodeState", 0)
        item = self._item("pausedProbe1")
        self.assertFalse(item.data(1, _PAUSED_ROLE))
        self.assertEqual(item.toolTip(1), "")

    def test_a_converted_node_is_paused_and_says_so(self):
        from mpynode import MPyNode
        from mpynode._base.commands import (
            build_convert_to_cpp_command, build_revert_to_py_command, run_undoable)
        from mpynode.ui.widgets.scene_tree import (
            _CPP_BADGE_ROLE, _CPP_CONVERTED, _PAUSED_ROLE)

        ensure_stub_compiled_plugin()
        n = MPyNode.create(name="pausedCvt")
        n.set_py_class("mpynode_user.StubCompiled")
        run_undoable(build_convert_to_cpp_command("pausedCvt", "mPyNode"))
        item = self._item("pausedCvt")
        self.assertEqual(item.data(1, _CPP_BADGE_ROLE), _CPP_CONVERTED)
        self.assertTrue(item.data(1, _PAUSED_ROLE))
        self.assertIn("paused (nodeState Blocking)", item.toolTip(1))
        run_undoable(build_revert_to_py_command("pausedCvt", "mPyNode"))
        item = self._item("pausedCvt")
        self.assertFalse(item.data(1, _PAUSED_ROLE))
        self.assertNotIn("paused", item.toolTip(1))

    def test_chips_are_laid_out_inside_the_viewport(self):
        from mpynode.ui.qt_wrapper import QRect
        from mpynode.ui.widgets.scene_tree import _CppChipDelegate as D

        # The item rect runs 40 px past the visible viewport (a stretched last
        # section under a frame / scrollbar): every chip must still end left
        # of the viewport edge, with the margin kept clear.
        rect  = QRect(300, 0, 540, 20)          # right() == 839
        rects = D.chip_rects(rect, 800, chipped=True, paused=True)
        self.assertEqual(rects["cpp"].right(), 800 - 1 - D.MARGIN)
        self.assertEqual(rects["cpp"].width(), D.CHIP_W)
        self.assertEqual(rects["cpp"].left() - rects["pause"].right() - 1, D.GUTTER)
        self.assertEqual(rects["pause"].width(), D.PAUSE_W)
        # No viewport known: bounded by the item rect itself.
        only_cpp = D.chip_rects(rect, 0, chipped=True, paused=False)
        self.assertEqual(only_cpp["cpp"].right(), rect.right() - D.MARGIN)
        self.assertIsNone(only_cpp["pause"])
        # A paused, unconverted node: the pause chip takes the C++ chip's slot.
        only_pause = D.chip_rects(rect, 800, chipped=False, paused=True)
        self.assertIsNone(only_pause["cpp"])
        self.assertEqual(only_pause["pause"].right(), 800 - 1 - D.MARGIN)
        # Every row keeps the C++ chip's room clear; a paused row also its own.
        self.assertEqual(D.RESERVED,            D.CHIP_W + D.GUTTER + D.MARGIN)
        self.assertEqual(D.reserved_for(False), D.RESERVED)
        self.assertEqual(D.reserved_for(True),  D.RESERVED + D.PAUSE_W + D.GUTTER)


class TestNameColumnSpacing(unittest.TestCase):
    """The Name column carries a small trailing gutter so the widest node name
    keeps a readable gap from the Class column (the column is
    ``ResizeToContents``, which otherwise hugs the text exactly)."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_name_delegate_adds_padding(self):
        try:
            from PySide6.QtWidgets import (
                QStyledItemDelegate, QStyleOptionViewItem)
        except Exception:
            from PySide2.QtWidgets import (
                QStyledItemDelegate, QStyleOptionViewItem)
        from mpynode import MPyNode
        from mpynode.ui.widgets.scene_tree import NDSceneTree, _NamePadDelegate

        MPyNode.create(name="paddingProbe1")
        t = NDSceneTree()
        t.refresh()
        item = t.findItem("paddingProbe1")
        self.assertIsNotNone(item)
        d = t.itemDelegateForColumn(0)
        self.assertIsInstance(d, _NamePadDelegate)
        idx  = t.indexFromItem(item, 0)
        opt  = QStyleOptionViewItem()
        base = QStyledItemDelegate(t)
        # Same option + same index -> the only difference is the added gutter.
        self.assertEqual(
            d.sizeHint(opt, idx).width(),
            base.sizeHint(opt, idx).width() + _NamePadDelegate.PAD,
        )


class TestSubclassActionsAndSignals(unittest.TestCase):
    def test_signals_exist(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        self.assertTrue(hasattr(NDSceneTree, "nameClassRequested"))
        self.assertTrue(hasattr(NDSceneTree, "reclassifyRequested"))

    def test_menu_has_class_actions(self):
        from mpynode.ui.widgets import scene_tree

        src = inspect.getsource(scene_tree.NDSceneTree._build_context_menu)
        # Option A relabel: class-less "Name Class…", classed "Rename Class" +
        # "Reclassify (Fork to New Class)"; no more "Clear Subclass".
        self.assertIn("Name Class", src)
        self.assertIn("Rename Class", src)
        self.assertIn("Reclassify (Fork to New Class)", src)
        self.assertNotIn("Clear Subclass", src)
        self.assertIn("nameClassRequested", src)
        self.assertIn("reclassifyRequested", src)


class TestDesignerBakeWiring(unittest.TestCase):
    """The designer wires the class-identity signals to handlers, exposes a
    class-name prompt, and both bake paths resolve the class name (identity,
    never node name) before generating the script (Task 9). Verified by
    source-inspection (constructing NDMainWindow headless is heavyweight;
    mirrors the other designer wiring tests)."""

    def test_class_signals_wired(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._wire_signals)
        self.assertIn("nameClassRequested.connect", src)
        self.assertIn("reclassifyRequested.connect", src)

    def test_class_handlers_exist(self):
        from mpynode.ui import mpynode_designer

        self.assertTrue(
            hasattr(mpynode_designer.NDMainWindow, "_on_name_class_requested"))
        self.assertTrue(
            hasattr(mpynode_designer.NDMainWindow, "_on_reclassify_requested"))

    def test_class_name_prompt_helper_exists(self):
        from mpynode.ui import mpynode_designer

        self.assertTrue(
            hasattr(mpynode_designer.NDMainWindow, "_prompt_for_class_name"))

    def test_bake_paths_resolve_class_name(self):
        from mpynode.ui import mpynode_designer

        for meth in ("_export_node_as_py", "_copy_node_as_py"):
            src = inspect.getsource(getattr(mpynode_designer.NDMainWindow, meth))
            self.assertIn("resolve_bake_class_name", src)
            self.assertIn("class_name=", src)


class TestNameRenameForkHandlers(unittest.TestCase):
    """The Name / Rename (cascade) / Fork handlers stamp the canonical Class on
    the correct set of instances. Constructs NDMainWindow (headless-safe, per
    the identity-panel smoke) and stubs the modal class-name prompt."""

    @classmethod
    def setUpClass(cls):
        from mpynode.ui.mpynode_designer import NDMainWindow

        cls._window = NDMainWindow()

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _win(self, answer):
        w                        = type(self)._window
        w._prompt_for_class_name = lambda *a, **k: answer
        return w

    def test_name_classless_stamps_only_self(self):
        from mpynode import MPyNode

        a = MPyNode.create(name="nrA#")
        b = MPyNode.create(name="nrB#")
        self._win("Foo")._on_name_class_requested(a.get_name(), "mPyNode")
        self.assertEqual(a.get_py_class(), "mpynode_user.Foo")
        self.assertEqual(b.get_py_class() or "", "")  # untouched

    def test_rename_cascades_to_all_instances_of_that_class(self):
        from mpynode import MPyNode

        a = MPyNode.create(name="nrcA#")
        b = MPyNode.create(name="nrcB#")
        a.set_py_class("mpynode_user.Foo")
        b.set_py_class("mpynode_user.Foo")
        c = MPyNode.create(name="nrcC#")
        c.set_py_class("mpynode_user.Other")
        # a is classed -> "Rename Class" cascades to every Foo instance.
        self._win("Bar")._on_name_class_requested(a.get_name(), "mPyNode")
        self.assertEqual(a.get_py_class(), "mpynode_user.Bar")
        self.assertEqual(b.get_py_class(), "mpynode_user.Bar")    # cascaded
        self.assertEqual(c.get_py_class(), "mpynode_user.Other")  # untouched

    def test_fork_stamps_only_self(self):
        from mpynode import MPyNode

        a = MPyNode.create(name="fkA#")
        b = MPyNode.create(name="fkB#")
        a.set_py_class("mpynode_user.Foo")
        b.set_py_class("mpynode_user.Foo")
        self._win("Forked")._on_reclassify_requested(a.get_name(), "mPyNode")
        self.assertEqual(a.get_py_class(), "mpynode_user.Forked")  # forked away
        self.assertEqual(b.get_py_class(), "mpynode_user.Foo")     # sibling kept

    def test_blank_rename_clears_only_this_instance(self):
        # The prompt returns "" for a classed node confirmed blank; the handler
        # clears THIS node (the Reclassify scope), never the cascade.
        from mpynode import MPyNode

        a = MPyNode.create(name="clrA#")
        b = MPyNode.create(name="clrB#")
        a.set_py_class("mpynode_user.Foo")
        b.set_py_class("mpynode_user.Foo")
        self._win("")._on_name_class_requested(a.get_name(), "mPyNode")
        self.assertFalse(a.get_py_class())
        self.assertEqual(b.get_py_class(), "mpynode_user.Foo")

    def test_cancel_is_still_a_no_op(self):
        from mpynode import MPyNode

        a = MPyNode.create(name="cancA#")
        a.set_py_class("mpynode_user.Foo")
        self._win(None)._on_name_class_requested(a.get_name(), "mPyNode")
        self.assertEqual(a.get_py_class(), "mpynode_user.Foo")

    def test_every_class_change_refreshes_the_open_views(self):
        # Name, cascade rename and clear all route through _refresh_class_views,
        # which re-bakes the open Outline / API view for each affected node.
        from unittest import mock

        from mpynode import MPyNode

        a = MPyNode.create(name="rvA#")
        b = MPyNode.create(name="rvB#")
        w = type(self)._window
        with mock.patch.object(w._script_tab_widget, "refreshIdentityViewsForNode",
                               return_value=0) as refreshed:
            self._win("Foo")._on_name_class_requested(a.get_name(), "mPyNode")
            b.set_py_class("mpynode_user.Foo")
            self._win("Bar")._on_name_class_requested(a.get_name(), "mPyNode")
            self._win("")._on_name_class_requested(a.get_name(), "mPyNode")
        seen = [c.args[0] for c in refreshed.call_args_list]
        self.assertEqual(seen.count(a.get_name()), 3)  # name, rename, clear
        self.assertIn(b.get_name(), seen)              # cascaded rename


class TestConvertToCppMenu(unittest.TestCase):
    """The scene tree exposes a convertToCppRequested signal and a "Convert Node
    to C++" action gated by commands.is_convertible_to_cpp."""

    def test_signal_exists(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree
        self.assertTrue(hasattr(NDSceneTree, "convertToCppRequested"))

    def test_menu_source_has_convert_action(self):
        from mpynode.ui.widgets import scene_tree

        src = inspect.getsource(scene_tree.NDSceneTree._build_context_menu)
        self.assertIn("Convert Node to C++",   src)
        self.assertIn("convertToCppRequested", src)
        self.assertIn("is_convertible_to_cpp", src)

    def test_revert_signal_exists(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree
        self.assertTrue(hasattr(NDSceneTree, "revertToPyRequested"))

    def test_menu_source_has_stateful_revert_action(self):
        from mpynode.ui.widgets import scene_tree

        src = inspect.getsource(scene_tree.NDSceneTree._build_context_menu)
        # A converted node offers "Revert Node to Python" (gated on is_converted).
        self.assertIn("Revert Node to Python", src)
        self.assertIn("revertToPyRequested",   src)
        self.assertIn("is_converted",          src)


class TestConvertToCppWiring(unittest.TestCase):
    def test_signal_wired(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._wire_signals)
        self.assertIn("convertToCppRequested.connect", src)

    def test_revert_signal_wired(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._wire_signals)
        self.assertIn("revertToPyRequested.connect", src)

    def test_handler_exists(self):
        from mpynode.ui import mpynode_designer
        self.assertTrue(hasattr(
            mpynode_designer.NDMainWindow, "_on_convert_to_cpp_requested"))

    def test_revert_handler_exists(self):
        from mpynode.ui import mpynode_designer
        self.assertTrue(hasattr(
            mpynode_designer.NDMainWindow, "_on_revert_to_py_requested"))


class TestConvertToCppHandler(unittest.TestCase):
    """The handler runs the undoable swap end to end. Constructs NDMainWindow
    (headless-safe) and stubs the modal QMessageBox so no dialog blocks."""

    @classmethod
    def setUpClass(cls):
        from mpynode.ui.mpynode_designer import NDMainWindow
        cls._window = NDMainWindow()

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        ensure_stub_compiled_plugin()

    def test_handler_converts_classed_node_to_coexisting_cpp(self):
        from mpynode import MPyNode
        from mpynode.ui import qt_wrapper
        from mpynode._base.commands import is_converted, linked_compiled_node

        n = MPyNode.create(name="hcvt")
        n.set_py_class("mpynode_user.StubCompiled")  # -> "stubCompiled" (plugin)
        # Stub the informational dialog so a dropped-connection / cycle report
        # can never block the headless run.
        orig                               = qt_wrapper.QMessageBox.information
        qt_wrapper.QMessageBox.information = staticmethod(lambda *a, **k: None)
        try:
            self._window._on_convert_to_cpp_requested("hcvt", "mPyNode")
        finally:
            qt_wrapper.QMessageBox.information = orig
        # Coexist: the Python node stays; a hidden compiled sibling is linked.
        self.assertTrue(mc.objExists("hcvt"))
        self.assertEqual(mc.nodeType("hcvt"), "mPyNode")
        self.assertTrue(is_converted("hcvt"))
        self.assertEqual(mc.nodeType(linked_compiled_node("hcvt")), "stubCompiled")

    def test_handler_keeps_editor_tab_open(self):
        """Coexist keeps the Python node as source of truth, so its editor tab
        must NOT be closed (a delete-swap leftover that lost the tab on a convert
        failure)."""
        from mpynode import MPyNode
        from mpynode.ui import qt_wrapper

        n = MPyNode.create(name="htab")
        n.set_py_class("mpynode_user.StubCompiled")
        calls = []
        stw   = self._window._script_tab_widget
        stw.closeTabForNode = lambda *a, **k: calls.append(a)
        orig = qt_wrapper.QMessageBox.information
        qt_wrapper.QMessageBox.information = staticmethod(lambda *a, **k: None)
        try:
            self._window._on_convert_to_cpp_requested("htab", "mPyNode")
        finally:
            del stw.closeTabForNode
            qt_wrapper.QMessageBox.information = orig
        self.assertEqual(calls, [])  # tab never closed in the coexist model

    def test_handler_stateful_warn_cancel_aborts(self):
        from mpynode import MPyNode
        from mpynode.ui import qt_wrapper
        from mpynode._base.commands import is_converted

        n = MPyNode.create(name="hstate")
        n.set_py_class("mpynode_user.StubCompiled")
        n.add_variable("counter", 3)  # -> get_variables() non-empty
        orig = qt_wrapper.QMessageBox.warning
        qt_wrapper.QMessageBox.warning = staticmethod(
            lambda *a, **k: qt_wrapper.QMessageBox.No)
        try:
            self._window._on_convert_to_cpp_requested("hstate", "mPyNode")
        finally:
            qt_wrapper.QMessageBox.warning = orig
        self.assertEqual(mc.nodeType("hstate"), "mPyNode")
        self.assertFalse(is_converted("hstate"))

    def _convert(self, name):
        from mpynode import MPyNode
        from mpynode.ui import qt_wrapper

        n = MPyNode.create(name=name)
        n.set_py_class("mpynode_user.StubCompiled")
        orig                               = qt_wrapper.QMessageBox.information
        qt_wrapper.QMessageBox.information = staticmethod(lambda *a, **k: None)
        try:
            self._window._on_convert_to_cpp_requested(name, "mPyNode")
        finally:
            qt_wrapper.QMessageBox.information = orig

    def test_unrewired_warn_is_silent_when_outputs_do_move(self):
        """Every type whose outputs ARE moved must not gain a new dialog."""
        from mpynode.ui import qt_wrapper

        mc.createNode("network", name="plainDG")
        calls = []
        orig  = qt_wrapper.QMessageBox.warning
        qt_wrapper.QMessageBox.warning = staticmethod(
            lambda *a, **k: calls.append(a) or qt_wrapper.QMessageBox.Yes)
        try:
            proceed = self._window._confirm_unrewired_dependents("plainDG")
        finally:
            qt_wrapper.QMessageBox.warning = orig
        self.assertTrue(proceed)
        self.assertEqual(calls, [], "no prompt for a full convert")

    def test_unrewired_warn_is_silent_for_a_transform_with_no_dependents(self):
        from mpynode.ui import qt_wrapper

        mc.createNode("transform", name="lonely")
        calls = []
        orig  = qt_wrapper.QMessageBox.warning
        qt_wrapper.QMessageBox.warning = staticmethod(
            lambda *a, **k: calls.append(a) or qt_wrapper.QMessageBox.Yes)
        try:
            proceed = self._window._confirm_unrewired_dependents("lonely")
        finally:
            qt_wrapper.QMessageBox.warning = orig
        self.assertTrue(proceed)
        self.assertEqual(calls, [], "nothing stays behind -- nothing to warn about")

    def _transform_with_dependents(self):
        xf = mc.createNode("transform", name="warnXf")
        mc.createNode("transform", name="warnKid", parent=xf)
        sink = mc.createNode("network")
        mc.addAttr(sink, ln="m", at="matrix")
        mc.connectAttr(xf + ".worldMatrix[0]", sink + ".m", force=True)
        return xf

    def test_unrewired_warn_lists_the_edge_and_the_child(self):
        from mpynode.ui import qt_wrapper

        self._transform_with_dependents()
        seen = []
        orig = qt_wrapper.QMessageBox.warning
        qt_wrapper.QMessageBox.warning = staticmethod(
            lambda *a, **k: seen.append(a[2]) or qt_wrapper.QMessageBox.Yes)
        try:
            proceed = self._window._confirm_unrewired_dependents("warnXf")
        finally:
            qt_wrapper.QMessageBox.warning = orig
        self.assertTrue(proceed)
        self.assertEqual(len(seen), 1, "the user must be told before converting")
        self.assertIn("worldMatrix", seen[0])
        self.assertIn("warnKid", seen[0])

    def test_unrewired_warn_cancel_aborts_the_convert(self):
        from mpynode.ui import qt_wrapper

        self._transform_with_dependents()
        orig = qt_wrapper.QMessageBox.warning
        qt_wrapper.QMessageBox.warning = staticmethod(
            lambda *a, **k: qt_wrapper.QMessageBox.No)
        try:
            proceed = self._window._confirm_unrewired_dependents("warnXf")
        finally:
            qt_wrapper.QMessageBox.warning = orig
        self.assertFalse(proceed)

    def test_revert_handler_unconverts(self):
        from mpynode.ui import qt_wrapper
        from mpynode._base.commands import is_converted, linked_compiled_node

        self._convert("hrev")
        cpp = linked_compiled_node("hrev")
        self.assertTrue(mc.objExists(cpp))
        orig                               = qt_wrapper.QMessageBox.information
        qt_wrapper.QMessageBox.information = staticmethod(lambda *a, **k: None)
        try:
            self._window._on_revert_to_py_requested("hrev", "mPyNode")
        finally:
            qt_wrapper.QMessageBox.information = orig
        self.assertFalse(is_converted("hrev"))
        self.assertFalse(mc.objExists(cpp))
        self.assertTrue(mc.objExists("hrev"))

    def test_delete_converted_node_cascades_to_cpp(self):
        from mpynode.ui import qt_wrapper
        from mpynode._base.commands import linked_compiled_node

        self._convert("hdel")
        cpp = linked_compiled_node("hdel")
        self.assertTrue(mc.objExists(cpp))
        orig_q = qt_wrapper.QMessageBox.question
        qt_wrapper.QMessageBox.question = staticmethod(
            lambda *a, **k: qt_wrapper.QMessageBox.Yes)
        try:
            self._window._on_delete_node_requested("hdel", "mPyNode")
        finally:
            qt_wrapper.QMessageBox.question = orig_q
        # Deleting the converted Python node also deletes its hidden sibling.
        self.assertFalse(mc.objExists("hdel"))
        self.assertFalse(mc.objExists(cpp))


if __name__ == "__main__":
    unittest.main()
