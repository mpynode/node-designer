"""Global middle-click -> select node in the Maya scene.

Middle-click used to be a per-widget action on ONLY the editor tab bar
(``NDEditorTabBar``) and the Scene tree (``NDSceneTree``). It is now a GLOBAL
Designer shortcut: an application-wide event filter on ``NDMainWindow`` catches
a middle-button press anywhere in the Designer, resolves the target mPyNode --
the row/tab under the cursor, else the active node -- and selects it with
``cmds.select(replace=True)``.

Coverage:
  * behavioral -- the per-widget node RESOLVERS (small widgets construct fine in
    mayapy) and the ancestor-walk helper;
  * inspect/structure -- the window-level event-filter WIRING (the full
    NDMainWindow is unreliable to instantiate in mayapy, per test_designer_window)
    and the removal of the old per-widget middle-click handlers.
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
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-middleclick-test"])

# QPoint isn't re-exported by qt_wrapper; pull it straight from the binding.
_QPoint = None
if _QApplication is not None:
    try:
        from PySide6.QtCore import QPoint as _QPoint
    except Exception:
        try:
            from PySide2.QtCore import QPoint as _QPoint
        except Exception:
            _QPoint = None

import inspect
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__middle_click():
    standalone_init()


def setUpModule():
    _setUpModule__middle_click()


def _qapp_available():
    return _QAPP is not None and _QPoint is not None


# ===========================================================================
# Behavioral: per-widget node resolvers (small widgets are safe in mayapy)
# ===========================================================================


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestTabWidgetResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="mcTabNode")
        self.name = self.node.get_name()
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    def _tab_widget(self):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        w = NDScriptTabWidget()
        self._widgets.append(w)
        w.addOrRaiseTab(self.node)
        return w

    def test_node_name_for_index_returns_tab_node(self):
        w = self._tab_widget()
        self.assertEqual(w.nodeNameForIndex(0), self.name)

    def test_node_name_for_index_out_of_range_is_none(self):
        w = self._tab_widget()
        self.assertIsNone(w.nodeNameForIndex(-1))
        self.assertIsNone(w.nodeNameForIndex(999))

    def test_tab_bar_middle_click_resolves_clicked_tab(self):
        """The tab bar maps a screen pos -> tab index -> the owner's
        nodeNameForIndex. tabAt is stubbed so the test is geometry-free."""
        w = self._tab_widget()
        bar = w.tabBar()
        bar.tabAt = lambda _pos: 0          # over the (only) tab
        self.assertEqual(bar.middleClickNodeName(_QPoint(5, 5)), self.name)

    def test_tab_bar_middle_click_off_any_tab_is_none(self):
        w = self._tab_widget()
        bar = w.tabBar()
        bar.tabAt = lambda _pos: -1         # empty tab-bar area
        self.assertIsNone(bar.middleClickNodeName(_QPoint(9999, 9999)))


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestSceneTreeResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="mcTreeNode")
        self.name = self.node.get_name()
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    def _tree(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        t = NDSceneTree()
        self._widgets.append(t)
        t.refresh()
        return t

    def test_middle_click_returns_row_node(self):
        """Over a real NDSceneTreeItem row -> that row's node name. itemAt is
        stubbed with the REAL item so the isinstance + node_name path is
        exercised without depending on offscreen pixel geometry."""
        from mpynode.ui.widgets.scene_tree import NDSceneTreeItem

        t = self._tree()
        item = t.topLevelItem(0)
        self.assertIsInstance(item, NDSceneTreeItem)
        t.itemAt = lambda _pos: item
        self.assertEqual(t.middleClickNodeName(_QPoint(5, 5)), self.name)

    def test_middle_click_off_row_is_none(self):
        t = self._tree()
        t.itemAt = lambda _pos: None
        self.assertIsNone(t.middleClickNodeName(_QPoint(9999, 9999)))

    def test_middle_click_non_scene_item_is_none(self):
        """A stray non-NDSceneTreeItem under the cursor must not resolve."""
        from mpynode.ui.qt_wrapper import QTreeWidgetItem

        t = self._tree()
        t.itemAt = lambda _pos: QTreeWidgetItem()
        self.assertIsNone(t.middleClickNodeName(_QPoint(5, 5)))


# ===========================================================================
# Behavioral: the ancestor-walk helper (pure, real small widgets)
# ===========================================================================


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestAncestorWalk(unittest.TestCase):
    def setUp(self):
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    def _resolver_cls(self):
        from mpynode.ui.qt_wrapper import QWidget

        class _ResolverWidget(QWidget):
            def __init__(self, name, parent=None):
                super().__init__(parent)
                self._name = name

            def middleClickNodeName(self, _gp):
                return self._name

        return _ResolverWidget

    def test_walk_finds_resolver_ancestor(self):
        from mpynode.ui.mpynode_designer import _middle_click_node_from_widget
        from mpynode.ui.qt_wrapper import QWidget

        Resolver = self._resolver_cls()
        stop = QWidget()
        parent = Resolver("nodeFoo", stop)
        child = QWidget(parent)          # plain, no resolver
        self._widgets += [stop, parent, child]

        self.assertEqual(
            _middle_click_node_from_widget(child, stop, _QPoint()), "nodeFoo")

    def test_walk_returns_none_when_no_resolver(self):
        from mpynode.ui.mpynode_designer import _middle_click_node_from_widget
        from mpynode.ui.qt_wrapper import QWidget

        stop = QWidget()
        parent = QWidget(stop)
        child = QWidget(parent)
        self._widgets += [stop, parent, child]

        self.assertIsNone(_middle_click_node_from_widget(child, stop, _QPoint()))

    def test_walk_falls_through_a_none_resolver_to_a_higher_one(self):
        """A resolver that returns None (e.g. click off a row) must NOT stop the
        walk: a higher resolver ancestor still resolves. A two-resolver chain is
        required -- with a single None resolver the result is None either way,
        so the test couldn't distinguish continue-vs-stop."""
        from mpynode.ui.mpynode_designer import _middle_click_node_from_widget
        from mpynode.ui.qt_wrapper import QWidget

        Resolver = self._resolver_cls()
        stop = QWidget()
        grandparent = Resolver("nodeFoo", stop)   # higher resolver: truthy
        parent = Resolver(None, grandparent)      # nearer resolver: None
        child = QWidget(parent)
        self._widgets += [stop, grandparent, parent, child]

        # only passes if the walk CONTINUES past the None resolver.
        self.assertEqual(
            _middle_click_node_from_widget(child, stop, _QPoint()), "nodeFoo")

    def test_walk_excludes_stop_widget(self):
        """The stop widget (the window) is NOT itself asked to resolve."""
        from mpynode.ui.mpynode_designer import _middle_click_node_from_widget

        Resolver = self._resolver_cls()
        stop = Resolver("shouldNotSee")   # stop IS a resolver, must be skipped
        self._widgets.append(stop)

        self.assertIsNone(_middle_click_node_from_widget(stop, stop, _QPoint()))


# ===========================================================================
# Structure: global event-filter wiring on NDMainWindow. The full window is
# unreliable in mayapy, so verify by inspect like test_designer_window.py.
# ===========================================================================


class TestGlobalFilterWiring(unittest.TestCase):
    def _m(self):
        from mpynode.ui import mpynode_designer as m

        return m

    def test_window_has_filter_api(self):
        m = self._m()
        for attr in (
            "eventFilter",
            "_install_global_middle_click_filter",
            "_remove_global_middle_click_filter",
            "_on_global_middle_click",
        ):
            self.assertTrue(
                hasattr(m.NDMainWindow, attr),
                f"NDMainWindow must define {attr}")

    def test_init_installs_filter(self):
        m = self._m()
        src = inspect.getsource(m.NDMainWindow.__init__)
        self.assertIn("_install_global_middle_click_filter", src)

    def test_close_removes_filter(self):
        m = self._m()
        src = inspect.getsource(m.NDMainWindow.closeEvent)
        self.assertIn("_remove_global_middle_click_filter", src)

    def test_reopen_reinstalls_filter(self):
        """closeEvent removes the filter but the X-button keeps the singleton
        alive; _handle_reopen MUST re-install it or the feature dies for the
        session after the first close/reopen."""
        m = self._m()
        src = inspect.getsource(m.NDMainWindow._handle_reopen)
        self.assertIn("_install_global_middle_click_filter", src)

    def test_handler_dedupes_by_timestamp(self):
        """An app-level filter is re-invoked once per ancestor for one physical
        press; the handler must act only on the first (under-cursor) delivery,
        keyed by event timestamp, so a later ancestor can't overwrite it."""
        m = self._m()
        src = inspect.getsource(m.NDMainWindow._on_global_middle_click)
        self.assertIn("timestamp", src)
        self.assertIn("_last_middle_click_ts", src)

    def test_install_uses_app_level_event_filter(self):
        m = self._m()
        src = inspect.getsource(m.NDMainWindow._install_global_middle_click_filter)
        self.assertIn("installEventFilter", src)

    def test_event_filter_is_middle_press_and_non_consuming(self):
        m = self._m()
        src = inspect.getsource(m.NDMainWindow.eventFilter)
        self.assertIn("MouseButtonPress", src)
        self.assertIn("MiddleButton", src)
        # NON-consuming: must return False so widgets' own MMB handling stands.
        self.assertIn("return False", src)

    def test_handler_scopes_and_falls_back_to_active_node(self):
        m = self._m()
        src = inspect.getsource(m.NDMainWindow._on_global_middle_click)
        self.assertIn("isAncestorOf", src)          # scoped to Designer subtree
        self.assertIn("_current_node", src)          # active-node fallback
        self.assertIn("replace=True", src)           # selects in the scene


# ===========================================================================
# Behavioral: eventFilter + _on_global_middle_click. NDMainWindow is
# unreliable in mayapy, but these are plain methods, so call them UNBOUND
# against a real-QWidget stand-in carrying a _current_node stub, with
# mc.select spied.
# ===========================================================================


def _node_stub(name):
    class _Node:
        def get_name(self):
            return name

    return _Node()


def _fake_event(ts, pos, button=None, etype=None):
    """Duck-typed QMouseEvent: exposes only what the dispatch reads."""
    from mpynode.ui.qt_wrapper import QEvent, Qt

    class _Pt:
        def toPoint(self):
            return pos

    class _E:
        def type(self):
            return etype if etype is not None else QEvent.MouseButtonPress

        def button(self):
            return button if button is not None else Qt.MiddleButton

        def timestamp(self):
            return ts

        def globalPosition(self):
            return _Pt()

    return _E()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestGlobalDispatch(unittest.TestCase):
    def setUp(self):
        import types

        from mpynode.ui.mpynode_designer import NDMainWindow
        from mpynode.ui.qt_wrapper import QWidget

        self._widgets = []
        self.root = QWidget()                     # NDMainWindow stand-in ("self")
        self.root._current_node = _node_stub("activeNode")
        self.root._last_middle_click_ts = None
        # eventFilter dispatches to self._on_global_middle_click, so the
        # stand-in carries it bound like the real window.
        self.root._on_global_middle_click = types.MethodType(
            NDMainWindow._on_global_middle_click, self.root)
        self._widgets.append(self.root)

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    def _resolver_child(self, name, parent):
        from mpynode.ui.qt_wrapper import QWidget

        class _Resolver(QWidget):
            def middleClickNodeName(self, _gp):
                return name

        w = _Resolver(parent)
        self._widgets.append(w)
        return w

    def _plain_child(self, parent):
        from mpynode.ui.qt_wrapper import QWidget

        w = QWidget(parent)
        self._widgets.append(w)
        return w

    def _dispatch(self, obj, event):
        """Call the unbound handler with mc.select spied; return recorded calls."""
        from mpynode.ui.mpynode_designer import NDMainWindow

        calls = []
        import maya.cmds as _mc

        orig = _mc.select
        _mc.select = lambda *a, **k: calls.append((a, k))
        try:
            NDMainWindow._on_global_middle_click(self.root, obj, event)
        finally:
            _mc.select = orig
        return calls

    def test_fallback_selects_active_node(self):
        obj = self._plain_child(self.root)        # no resolver in chain
        calls = self._dispatch(obj, _fake_event(1, _QPoint(2, 2)))
        self.assertEqual(calls, [(("activeNode",), {"replace": True})])

    def test_out_of_scope_is_ignored(self):
        from mpynode.ui.qt_wrapper import QWidget

        outside = QWidget()                        # NOT a descendant of root
        self._widgets.append(outside)
        calls = self._dispatch(outside, _fake_event(1, _QPoint(2, 2)))
        self.assertEqual(calls, [], "must not select for widgets outside the window")

    def test_under_cursor_resolver_wins_over_active(self):
        obj = self._resolver_child("clickedNode", self.root)
        calls = self._dispatch(obj, _fake_event(1, _QPoint(2, 2)))
        self.assertEqual(calls, [(("clickedNode",), {"replace": True})])

    def test_no_active_node_and_no_resolver_is_noop(self):
        self.root._current_node = None
        obj = self._plain_child(self.root)
        calls = self._dispatch(obj, _fake_event(1, _QPoint(2, 2)))
        self.assertEqual(calls, [], "no target -> no select, no raise")

    def test_same_press_dedup_keeps_under_cursor_node(self):
        """THE regression guard: Qt re-fires one physical press per ancestor.
        Fire A (obj = tab-bar-like resolver) selects the clicked node; fire B
        (obj = its parent, no resolver, SAME timestamp) must be deduped so it
        does NOT fall back and overwrite with the active node."""
        tab_widget = self._plain_child(self.root)             # NDScriptTabWidget-like
        tab_bar = self._resolver_child("tabNode", tab_widget)  # NDEditorTabBar-like

        from mpynode.ui.mpynode_designer import NDMainWindow
        import maya.cmds as _mc

        calls = []
        orig = _mc.select
        _mc.select = lambda *a, **k: calls.append((a, k))
        try:
            NDMainWindow._on_global_middle_click(
                self.root, tab_bar, _fake_event(42, _QPoint(2, 2)))       # fire A
            NDMainWindow._on_global_middle_click(
                self.root, tab_widget, _fake_event(42, _QPoint(2, 2)))    # fire B (same ts)
        finally:
            _mc.select = orig

        self.assertEqual(
            calls, [(("tabNode",), {"replace": True})],
            "the clicked tab's node must win; the parent re-fire must not "
            "overwrite it with the active node")

    def test_distinct_presses_are_not_over_suppressed(self):
        """Dedup keys on timestamp: two DISTINCT presses (different ts) must
        both act."""
        a = self._resolver_child("nodeA", self.root)
        b = self._plain_child(self.root)

        from mpynode.ui.mpynode_designer import NDMainWindow
        import maya.cmds as _mc

        calls = []
        orig = _mc.select
        _mc.select = lambda *args, **k: calls.append((args, k))
        try:
            NDMainWindow._on_global_middle_click(self.root, a, _fake_event(1, _QPoint()))
            NDMainWindow._on_global_middle_click(self.root, b, _fake_event(2, _QPoint()))
        finally:
            _mc.select = orig

        self.assertEqual(
            calls,
            [(("nodeA",), {"replace": True}), (("activeNode",), {"replace": True})])

    def test_event_filter_is_non_consuming_and_gates_button(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        from mpynode.ui.qt_wrapper import QEvent, Qt
        import maya.cmds as _mc

        obj = self._resolver_child("clickedNode", self.root)
        calls = []
        orig = _mc.select
        _mc.select = lambda *a, **k: calls.append((a, k))
        try:
            # Middle press -> selects, and NEVER consumes (returns False).
            ret = NDMainWindow.eventFilter(
                self.root, obj, _fake_event(7, _QPoint(1, 1)))
            self.assertFalse(ret, "eventFilter must be non-consuming")
            self.assertEqual(calls, [(("clickedNode",), {"replace": True})])
            # A left-button press must NOT trigger a select.
            calls.clear()
            self.root._last_middle_click_ts = None
            ret2 = NDMainWindow.eventFilter(
                self.root, obj, _fake_event(8, _QPoint(1, 1), button=Qt.LeftButton))
            self.assertFalse(ret2)
            self.assertEqual(calls, [], "left-button must not select")
            # A non-press event (e.g. MouseMove) must NOT trigger a select.
            calls.clear()
            ret3 = NDMainWindow.eventFilter(
                self.root, obj, _fake_event(9, _QPoint(1, 1), etype=QEvent.MouseMove))
            self.assertFalse(ret3)
            self.assertEqual(calls, [], "non-press must not select")
        finally:
            _mc.select = orig


# ===========================================================================
# Regression: the per-widget middle-click handlers are gone from the tabs and
# scene tab; handling is global.
# ===========================================================================


class TestOldHandlersRemoved(unittest.TestCase):
    def test_tab_bar_mousepress_has_no_middle_button(self):
        from mpynode.ui.widgets import script_tab

        src = inspect.getsource(script_tab.NDEditorTabBar.mousePressEvent)
        self.assertNotIn(
            "MiddleButton", src,
            "the tab bar must no longer special-case middle-click")

    def test_scene_tree_has_no_mousepress_override(self):
        from mpynode.ui.widgets import scene_tree

        self.assertNotIn(
            "mousePressEvent", scene_tree.NDSceneTree.__dict__,
            "the Scene tree's middle-click mousePressEvent override must be gone")

    def test_resolvers_present_on_both_widgets(self):
        from mpynode.ui.widgets import scene_tree, script_tab

        self.assertIn("middleClickNodeName", scene_tree.NDSceneTree.__dict__)
        self.assertIn("middleClickNodeName", script_tab.NDEditorTabBar.__dict__)

    def test_select_action_replaced_by_accessor(self):
        from mpynode.ui.widgets import script_tab

        self.assertFalse(
            hasattr(script_tab.NDScriptTabWidget, "selectNodeInSceneForIndex"),
            "the old per-tab select action must be removed")
        self.assertTrue(
            hasattr(script_tab.NDScriptTabWidget, "nodeNameForIndex"))

    def test_middle_button_centralized_to_designer(self):
        """``MiddleButton`` must appear ONLY in the designer module now, not in
        the two widget modules -- i.e. the action is fully global."""
        from mpynode.ui import mpynode_designer
        from mpynode.ui.widgets import scene_tree, script_tab

        self.assertNotIn("MiddleButton", inspect.getsource(script_tab))
        self.assertNotIn("MiddleButton", inspect.getsource(scene_tree))
        self.assertIn("MiddleButton", inspect.getsource(mpynode_designer))


if __name__ == "__main__":
    unittest.main()
