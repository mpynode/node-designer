"""Node Designer window/toolbar/scaffold: reopen-autoselect, toolbar+commands, icons+singleton, scaffold, solver/storage tab removal, scene-tree single-select

Consolidated from: test_designer_reopen_autoselect.py, test_phase16.py, test_phase20.py, test_phase04.py, test_phase10.py, test_scene_tree_single_select.py.
"""

from __future__ import annotations

# ===================== from test_designer_reopen_autoselect.py =====================
import ast
import inspect
import unittest


class TestReopenAutoSelect(unittest.TestCase):
    def _designer_source(self) -> str:
        from mpynode.ui import mpynode_designer

        return inspect.getsource(mpynode_designer)

    def test_handle_reopen_calls_auto_select_first_node(self):
        """``_handle_reopen`` must include a call to
        ``self._auto_select_first_node()`` so the new scene\'s first
        node populates the editor tabs after a reopen-with-scene-swap.
        """
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._handle_reopen)
        self.assertIn(
            "_auto_select_first_node",
            src,
            "_handle_reopen must call _auto_select_first_node so a "
            "reopen onto a different scene picks up the new scene\'s "
            "first node (same UX as fresh launch).",
        )

    def test_handle_reopen_calls_after_stale_tab_prune(self):
        """``_auto_select_first_node`` must be invoked AFTER the
        stale-tab prune (step 2) -- otherwise the auto-select helper\'s
        ``count() > 0`` guard would see the not-yet-pruned stale tabs
        and bail out, leaving the editor blank."""
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._handle_reopen)
        # The stale-tab prune delegates to the tab widget's pruneStaleTabs()
        # (MObjectHandle liveness), not an inline removeTab(i) loop. What
        # matters here is the ordering: auto-select AFTER the prune.
        prune_marker = "pruneStaleTabs()"
        autoselect_marker = "_auto_select_first_node()"
        prune_idx = src.find(prune_marker)
        auto_idx = src.find(autoselect_marker)
        self.assertGreaterEqual(
            prune_idx,
            0,
            "_handle_reopen must still prune stale tabs",
        )
        self.assertGreaterEqual(
            auto_idx,
            0,
            "_handle_reopen must call _auto_select_first_node",
        )
        self.assertGreater(
            auto_idx,
            prune_idx,
            "_auto_select_first_node must run AFTER the stale-tab "
            "prune so the helper\'s count()==0 guard sees the freshly-"
            "cleaned tab widget.",
        )

    def test_handle_reopen_calls_after_scene_tree_refresh(self):
        """Auto-select reads ``topLevelItem(0)`` from the Scene tree,
        so the tree must be refreshed BEFORE the auto-select fires --
        otherwise the helper picks the first node from the previous
        scene\'s stale tree snapshot."""
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._handle_reopen)
        refresh_idx = src.find("self._scene_tree.refresh()")
        auto_idx = src.find("_auto_select_first_node()")
        self.assertGreaterEqual(
            refresh_idx,
            0,
            "_handle_reopen must refresh the Scene tree",
        )
        self.assertGreater(
            auto_idx,
            refresh_idx,
            "_auto_select_first_node must run AFTER scene_tree.refresh()",
        )

    def test_handle_reopen_autoselect_guarded_by_try_except(self):
        """The auto-select call in ``_handle_reopen`` must be wrapped
        in try/except so a transient lookup failure (e.g. a callback
        ordering hiccup) can\'t leak into the rest of the reopen
        flow."""
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._handle_reopen)
        # Find the auto-select call + verify a try/except surrounds it.
        tree = ast.parse(inspect.getsource(
            mpynode_designer.NDMainWindow._handle_reopen
        ).lstrip())
        wrapped = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Walk the try body for a Call that hits the helper.
                for sub in ast.walk(node):
                    if (
                        isinstance(sub, ast.Attribute)
                        and sub.attr == "_auto_select_first_node"
                    ):
                        wrapped = True
                        break
                if wrapped:
                    break
        self.assertTrue(
            wrapped,
            "_auto_select_first_node call in _handle_reopen must "
            "live inside a try/except block",
        )

    def test_auto_select_helper_still_guards_on_open_tabs(self):
        """The reopen wiring relies on the helper\'s existing
        ``count() > 0`` guard to skip auto-select when the user reopens
        on the SAME scene (so prior tabs stay intact). Pin that guard
        so a future refactor doesn\'t silently drop it."""
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(
            mpynode_designer.NDMainWindow._auto_select_first_node
        )
        self.assertIn(
            "_script_tab_widget.count()",
            src,
            "_auto_select_first_node must keep its open-tabs guard so "
            "reopens on the same scene don\'t clobber the user\'s tabs",
        )


# ===================== from test_phase16.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase16():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Underlying command behavior (no QWidget needed)
# ===========================================================================


class TestSetExpressionCommandFromUI(unittest.TestCase):
    """The Save flow uses _SetExpressionCommand. Verify it works
    end-to-end including undo / redo."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_save_writes_to_node(self):
        from mpynode._base.commands import _SetExpressionCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="saveOne")
        n.set_compute_expression("# original")

        run_undoable(_SetExpressionCommand(n, "# saved via UI"))
        self.assertEqual(n.get_compute_expression(), "# saved via UI")

    def test_save_is_undoable_redoable(self):
        from mpynode._base.commands import _SetExpressionCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="undoSave")
        n.set_compute_expression("# baseline")

        run_undoable(_SetExpressionCommand(n, "# modified"))
        self.assertEqual(n.get_compute_expression(), "# modified")

        mc.undo()
        self.assertEqual(n.get_compute_expression(), "# baseline")
        mc.redo()
        self.assertEqual(n.get_compute_expression(), "# modified")


class TestAddNewNodeEvent(unittest.TestCase):
    """AddNewNodeEvent uses _CreateNodeCommand. Test the underlying flow
    without instantiating the QWidget."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_create_node_command_via_designer_path(self):
        from mpynode._base.commands import _CreateNodeCommand, run_undoable

        # Mirrors what addNewNodeEvent does internally.
        created = run_undoable(_CreateNodeCommand("mPyNode"))
        self.assertTrue(mc.objExists(created))
        self.assertEqual(mc.nodeType(created), "mPyNode")

        mc.undo()
        self.assertFalse(mc.objExists(created))

        mc.redo()
        self.assertTrue(mc.objExists(created))

    def test_each_registered_type_can_be_created(self):
        """Every node type in REGISTRY can be created via the
        _CreateNodeCommand path (with the iksolver requiring a name)."""
        from mpynode._base.commands import _CreateNodeCommand, run_undoable
        from mpynode._node_registry import REGISTRY

        # mPyIkSolver must exist before mc.ikHandle can use it as a solver, but
        # plain createNode works for all 7 types.
        for native_type in REGISTRY.keys():
            mc.file(new=True, force=True)
            created = run_undoable(_CreateNodeCommand(native_type))
            self.assertTrue(
                mc.objExists(created),
                f"_CreateNodeCommand failed for {native_type!r}",
            )


# ===========================================================================
# Inspect-based UI structural tests (no widget instantiation)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestScriptTabModuleShape(unittest.TestCase):
    def test_placeholder_editor_is_editable_in_phase16(self):
        """Changed the placeholder from read-only to editable."""
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptEditorPlaceholder

        src = inspect.getsource(NDScriptEditorPlaceholder.__init__)
        self.assertIn("setReadOnly(False)", src)

    def test_placeholder_has_dirty_api(self):
        from mpynode.ui.widgets.script_tab import NDScriptEditorPlaceholder

        for method in (
            "getText",
            "setText",
            "hasUnsavedChanges",
            "markSaved",
            "refresh",
        ):
            self.assertTrue(
                hasattr(NDScriptEditorPlaceholder, method),
                f"NDScriptEditorPlaceholder should have {method!r}",
            )
        self.assertTrue(hasattr(NDScriptEditorPlaceholder, "dirtyStateChanged"))

    def test_script_tab_widget_has_save_methods(self):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        for method in (
            "saveCurrentTab",
            "saveAllTabs",
            "_saveTab",
            "hasAnyDirtyTab",
            "_showSaveConfirmDialog",
            "_update_tab_dirty_marker",
        ):
            self.assertTrue(
                hasattr(NDScriptTabWidget, method),
                f"NDScriptTabWidget should have {method!r}",
            )

    def test_save_uses_set_expression_command(self):
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget._saveTab)
        self.assertIn("_SetExpressionCommand", src)
        self.assertIn("run_undoable", src)
        self.assertIn("markSaved", src)

    def test_close_request_checks_dirty(self):
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget._on_tab_close_requested)
        self.assertIn("hasUnsavedChanges", src)
        self.assertIn("_showSaveConfirmDialog", src)
        self.assertIn("_saveTab", src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestToolbarModuleShape(unittest.TestCase):
    def test_toolbar_class_present(self):
        from mpynode.ui.widgets.toolbar import NDToolBar

        for method in ("_build_buttons", "contextMenuEvent"):
            self.assertTrue(hasattr(NDToolBar, method))

    def test_toolbar_iterates_registry_for_new_menu(self):
        import inspect

        from mpynode.ui.widgets.toolbar import NDToolBar

        src = inspect.getsource(NDToolBar._build_buttons)
        self.assertIn("REGISTRY", src)
        self.assertIn("New", src)
        self.assertIn("Save", src)
        self.assertIn("Save All", src)

    def test_toolbar_context_menu_is_noop(self):
        """Suppress Maya's default right-click on the toolbar area."""
        import inspect

        from mpynode.ui.widgets.toolbar import NDToolBar

        src = inspect.getsource(NDToolBar.contextMenuEvent)
        self.assertIn("event.accept", src)
        # Should NOT call super (which would show the default menu).
        self.assertNotIn("super().contextMenuEvent", src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDesignerPhase16Wiring(unittest.TestCase):
    def test_main_window_has_phase16_methods(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        for m in (
            "_build_menu_bar",
            "_build_toolbar",
            "_install_shortcuts",
            "addNewNodeEvent",
            "saveCurrentNode",
            "saveAllNodes",
        ):
            self.assertTrue(hasattr(NDMainWindow, m), f"missing {m}")

    def test_addNewNodeEvent_uses_create_node_command(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        # Phase F moved the post-create tab-open tail into _post_create and
        # routed command building through _new_node_command. Intent unchanged:
        # the create is undoable and ends by opening the node's tab.
        src = inspect.getsource(NDMainWindow.addNewNodeEvent)
        self.assertIn("_new_node_command", src)
        self.assertIn("run_undoable", src)
        self.assertIn("_post_create", src)

        # The tab gets opened + raised in the factored-out tail.
        post_src = inspect.getsource(NDMainWindow._post_create)
        self.assertIn("addOrRaiseTab", post_src)

    def test_install_shortcuts_binds_F5(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._install_shortcuts)
        self.assertIn("F5", src)
        self.assertIn("saveCurrentNode", src)

    def test_menu_bar_includes_required_menus(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_menu_bar)
        for menu in ('"File"', '"Node"', '"Help"', '"New Node"'):
            self.assertIn(menu, src)

    def test_toolbar_built_with_callbacks(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_toolbar)
        self.assertIn("NDToolBar", src)
        self.assertIn("on_new_node", src)
        self.assertIn("on_save_node", src)
        self.assertIn("on_save_all", src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDialogs(unittest.TestCase):
    def test_about_dialog_module_present(self):
        from mpynode.ui.dialogs.about import show_about_dialog

        self.assertTrue(callable(show_about_dialog))

    def test_confirm_delete_module_present(self):
        from mpynode.ui.dialogs.confirm import confirm_delete_node

        self.assertTrue(callable(confirm_delete_node))


# ===================== from test_phase20.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase20():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Icon registry shape
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestIconRegistries(unittest.TestCase):
    def test_letters_for_all_registered_node_types(self):
        from mpynode._node_registry import REGISTRY
        from mpynode.ui.widgets.icons import NODE_TYPE_LETTERS

        for native_type in REGISTRY.keys():
            self.assertIn(
                native_type,
                NODE_TYPE_LETTERS,
                f"NODE_TYPE_LETTERS missing entry for {native_type!r}",
            )

    def test_colors_for_all_registered_node_types(self):
        from mpynode._node_registry import REGISTRY
        from mpynode.ui.widgets.icons import NODE_TYPE_COLORS

        for native_type in REGISTRY.keys():
            self.assertIn(
                native_type,
                NODE_TYPE_COLORS,
                f"NODE_TYPE_COLORS missing entry for {native_type!r}",
            )
            rgb = NODE_TYPE_COLORS[native_type]
            self.assertEqual(len(rgb), 3)
            for ch in rgb:
                self.assertGreaterEqual(ch, 0)
                self.assertLessEqual(ch, 255)

    def test_letters_are_single_chars(self):
        from mpynode.ui.widgets.icons import NODE_TYPE_LETTERS

        for native_type, letter in NODE_TYPE_LETTERS.items():
            self.assertEqual(
                len(letter),
                1,
                f"{native_type!r} letter {letter!r} should be 1 char",
            )

    def test_letters_are_unique(self):
        from mpynode.ui.widgets.icons import NODE_TYPE_LETTERS

        letters = list(NODE_TYPE_LETTERS.values())
        self.assertEqual(
            len(letters),
            len(set(letters)),
            "letter pills must be unique across node types",
        )


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestAttrColorRegistry(unittest.TestCase):
    def test_attr_colors_cover_all_supported_types(self):
        from mpynode.wrappers._mpy_node import _ADD_ATTR_KIND
        from mpynode.ui.widgets.icons import ATTR_TYPE_COLORS

        for attr_type in _ADD_ATTR_KIND.keys():
            self.assertIn(
                attr_type,
                ATTR_TYPE_COLORS,
                f"ATTR_TYPE_COLORS missing entry for {attr_type!r}",
            )

    def test_attr_colors_match_phase29_for_known_types(self):
        """RGB values for the original types (verified against the
        original mpynode_designer.py)."""
        from mpynode.ui.widgets.icons import ATTR_TYPE_COLORS

        self.assertEqual(ATTR_TYPE_COLORS["int"], (0, 128, 1))
        self.assertEqual(ATTR_TYPE_COLORS["float"], (80, 230, 80))
        self.assertEqual(ATTR_TYPE_COLORS["vector"], (80, 230, 80))
        self.assertEqual(ATTR_TYPE_COLORS["angle"], (128, 230, 230))
        self.assertEqual(ATTR_TYPE_COLORS["bool"], (221, 135, 36))
        self.assertEqual(ATTR_TYPE_COLORS["matrix"], (128, 170, 170))
        self.assertEqual(ATTR_TYPE_COLORS["mesh"], (230, 1, 230))
        self.assertEqual(ATTR_TYPE_COLORS["nurbsCurve"], (128, 230, 230))
        self.assertEqual(ATTR_TYPE_COLORS["nurbsSurface"], (128, 128, 128))
        self.assertEqual(ATTR_TYPE_COLORS["string"], (255, 218, 76))
        self.assertEqual(ATTR_TYPE_COLORS["python"], (255, 218, 76))
        self.assertEqual(ATTR_TYPE_COLORS["enum"], (146, 101, 49))


# ===========================================================================
# Pill rendering smoke test (uses QPixmap directly \u2014 safe in mayapy)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestLetterPillRender(unittest.TestCase):
    def test_pill_pixmap_has_correct_size(self):
        # Create a QApplication so QPixmap can render.
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PySide2.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication([])

        from mpynode.ui.widgets.icons import _make_letter_pill_pixmap

        pm = _make_letter_pill_pixmap("X", (200, 100, 50), size=24)
        self.assertEqual(pm.width(), 24)
        self.assertEqual(pm.height(), 24)
        self.assertFalse(pm.isNull())

    def test_get_node_type_icon_caches(self):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PySide2.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication([])

        from mpynode.ui.widgets.icons import _NODE_ICON_CACHE, get_node_type_icon

        _NODE_ICON_CACHE.clear()
        icon1 = get_node_type_icon("mPyNode", size=16)
        icon2 = get_node_type_icon("mPyNode", size=16)
        self.assertIs(icon1, icon2, "icon should be cached + identity-equal")

    def test_unknown_node_type_falls_back(self):
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PySide2.QtWidgets import QApplication
        _ = QApplication.instance() or QApplication([])

        from mpynode.ui.widgets.icons import get_node_type_icon

        icon = get_node_type_icon("notARealType", size=16)
        # Doesn't crash, returns SOMETHING.
        self.assertFalse(icon.isNull())


# ===========================================================================
# Wiring (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestWiring(unittest.TestCase):
    def test_scene_tree_item_sets_icon(self):
        import inspect

        from mpynode.ui.widgets.scene_tree import NDSceneTreeItem

        # Scoped to the CLASS, not __init__: the icon is assigned in
        # _refresh_compiled_state (via _refresh_label) so a rename or a
        # convert/revert re-reads it instead of stranding the pill built at
        # construction.
        src = inspect.getsource(NDSceneTreeItem)
        self.assertIn("get_node_type_icon", src)
        self.assertIn("setIcon(0,", src)

    def test_toolbar_new_menu_sets_icon(self):
        import inspect

        from mpynode.ui.widgets.toolbar import NDToolBar

        src = inspect.getsource(NDToolBar._build_buttons)
        self.assertIn("get_node_type_icon", src)
        self.assertIn("action.setIcon", src)

    def test_node_menu_sets_icon(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_menu_bar)
        self.assertIn("get_node_type_icon", src)
        self.assertIn("act.setIcon", src)

    def test_user_attr_item_applies_type_color(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        # Type-default colouring was REMOVED: the theme default stands unless
        # ui_color is set. `_apply_type_color` remains as an API-compat shim.
        self.assertTrue(hasattr(NDUserAttrTreeItem, "_apply_type_color"))
        self.assertTrue(hasattr(NDUserAttrTreeItem, "_apply_color"))
        # __init__ still calls one of them.
        init_src = inspect.getsource(NDUserAttrTreeItem.__init__)
        self.assertTrue(
            "_apply_color" in init_src or "_apply_type_color" in init_src,
            "__init__ should call _apply_color or _apply_type_color",
        )
        # The helper applies setForeground when a color IS set.
        helper_src = inspect.getsource(NDUserAttrTreeItem._apply_color)
        self.assertIn("setForeground", helper_src)
        self.assertIn("ui_color", helper_src)


# ===========================================================================
# Bug fix: direction radio buttons must be in an exclusive QButtonGroup
# (prevents both-unchecked when user clicks the active radio)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDirectionRadioBugFix(unittest.TestCase):
    def test_build_ui_uses_qbuttongroup(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._build_ui)
        self.assertIn("QButtonGroup(self)", src)
        self.assertIn("setExclusive(True)", src)
        self.assertIn("addButton(self._input_radio)", src)
        self.assertIn("addButton(self._output_radio)", src)

    def test_signal_handler_uses_buttongroup_signal(self):
        """Subscribe to the GROUP's buttonClicked signal,
        NOT the individual radio's `toggled` signal (which fires twice
        per change and used to leave both radios unchecked when the
        active one was re-clicked)."""
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._wire_signals)
        self.assertIn("_direction_group.buttonClicked.connect", src)
        # The OLD per-radio signal subscription should be gone.
        self.assertNotIn("_input_radio.toggled.connect", src)

    def test_direction_change_handler_no_ops_on_same_direction(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._on_direction_changed)
        # Should early-out when new_dir == self._direction.
        self.assertIn("== self._direction", src)
        self.assertIn("return", src)


# ===========================================================================
class TestShowDesignerRestoresAMinimizedWindow(unittest.TestCase):
    """The shelf button calls show_designer(). A minimized Node Designer is a
    title-bar stub at the bottom of Maya that nobody finds, and re-calling
    show() on it changed nothing -- the button looked dead. The existing
    window is now un-minimized (Qt restores its pre-minimize geometry), moved
    on screen if no screen shows it, raised and activated; a new one is built
    only when none exists."""

    def test_second_call_unminimizes_the_same_window(self):
        from unittest import mock

        from mpynode.ui import mpynode_designer as dm
        from mpynode.ui.qt_wrapper import QMainWindow

        try:
            from PySide6.QtGui import QGuiApplication
        except ImportError:
            from PySide2.QtGui import QGuiApplication

        parent = QMainWindow()
        self.addCleanup(parent.deleteLater)
        with mock.patch.object(dm, "maya_main_window", lambda: parent):
            win = dm.show_designer()
            try:
                self.assertIs(win.parent(), parent)
                win.showMinimized()
                self.assertTrue(win.isMinimized())
                again = dm.show_designer()
                self.assertIs(again, win, "a second window was built")
                self.assertFalse(win.isMinimized())
                self.assertTrue(win.isVisible())
                # Parked off every screen: brought back onto the primary one,
                # size untouched.
                size = win.size()
                win.move(20000, 20000)
                dm.show_designer()
                avail = QGuiApplication.primaryScreen().availableGeometry()
                self.assertTrue(avail.intersects(win.frameGeometry()),
                                win.frameGeometry())
                self.assertEqual(win.size(), size)
            finally:
                win.close()
                win.deleteLater()
                dm._designer_instance = None


# Bulletproof singleton: show_designer must use findChild as the source
# of truth (catches stale cache, direct-construction bypass, module reload).
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestShowDesignerSingleton(unittest.TestCase):
    def test_show_designer_uses_findChild_as_source_of_truth(self):
        """Source of truth is parent.findChild(QMainWindow,
        WINDOW_OBJECT_NAME), NOT just the module-level _designer_instance
        cache. This catches stale cache after window-X-close + direct
        NDMainWindow() bypass + module-reload races."""
        import inspect

        from mpynode.ui import mpynode_designer as dm

        src = inspect.getsource(dm.show_designer)
        self.assertIn("findChild", src)
        self.assertIn("WINDOW_OBJECT_NAME", src)

    def test_show_designer_only_constructs_when_no_existing(self):
        """If findChild returns an instance, show_designer should NOT
        construct a new NDMainWindow."""
        import inspect

        from mpynode.ui import mpynode_designer as dm

        src = inspect.getsource(dm.show_designer)
        # NDMainWindow must be constructed AFTER the findChild lookup and its
        # early-return on hit.
        find_idx = src.find("findChild")
        return_idx = src.find("return existing")
        ctor_idx = src.find("NDMainWindow(parent=parent)")
        self.assertGreater(find_idx, -1)
        self.assertGreater(return_idx, -1)
        self.assertGreater(ctor_idx, -1)
        self.assertLess(find_idx, return_idx)
        self.assertLess(return_idx, ctor_idx)

    def test_main_window_object_name_set_in_init(self):
        """The findChild lookup only works because __init__ calls
        setObjectName(WINDOW_OBJECT_NAME). Make sure that didn't get
        accidentally removed."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.__init__)
        self.assertIn("setObjectName(self.WINDOW_OBJECT_NAME)", src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestNDMainWindowHardSingleton(unittest.TestCase):
    def test_init_has_singleton_guard(self):
        """Hard singleton: NDMainWindow.__init__ rejects
        construction when another instance already exists in the same
        Qt main-window subtree."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.__init__)
        # Must call findChild before super().__init__ to catch the bypass.
        find_idx = src.find("findChild")
        super_idx = src.find("super().__init__")
        self.assertGreater(find_idx, -1, "must use findChild for singleton check")
        self.assertGreater(super_idx, -1)
        self.assertLess(
            find_idx, super_idx, "findChild check must run BEFORE super().__init__"
        )
        # Must raise RuntimeError on collision.
        self.assertIn("raise RuntimeError", src)
        self.assertIn("show_designer", src)

    def test_init_falls_back_to_maya_main_when_parent_none(self):
        """If user calls NDMainWindow() (no parent), the check should
        still work by looking up Maya's main window."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.__init__)
        self.assertIn("maya_main_window()", src)


# ===========================================================================
# stale-state on reopen after file new
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestReopenAfterSceneChange(unittest.TestCase):
    """Bug: when the user closes the Designer (X button) THEN does
    file→new, the underlying Qt widget stays alive (so show_designer's
    findChild path can re-raise it) but its scene callbacks were torn
    down in closeEvent — so the wipe was missed. On reopen the user
    saw stale tabs / panels from the old scene.

    Fix: ``NDMainWindow._handle_reopen`` is invoked by show_designer
    whenever an existing instance is being re-shown. It re-registers
    callbacks, closes tabs whose nodes are gone, clears _current_node
    if it's gone, and refreshes the Scene tree.

    Tests use a stand-in object instead of instantiating ``NDMainWindow``
    directly because mayapy + headless Qt can't reliably build a
    ``QMainWindow`` after ``maya.standalone.initialize``. Same pattern
    as ``TestE2EIntegration``.
    """

    def test_handle_reopen_method_exists(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(callable(getattr(NDMainWindow, "_handle_reopen", None)))

    def test_handle_reopen_source_does_the_4_things(self):
        """Source inspection: the handler must (1) re-register scene
        callbacks if torn down, (2) close stale tabs by objExists check,
        (3) clear _current_node if gone, (4) refresh the scene tree."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._handle_reopen)
        # 1. Re-register
        self.assertIn("_register_scene_callbacks", src)
        self.assertIn("_scene_callback_ids", src)
        # 2. Close stale tabs via mc.objExists
        self.assertIn("objExists", src)
        self.assertIn("_script_tab_widget", src)
        # 3. Clear current_node if gone
        self.assertIn("_current_node", src)
        self.assertIn("setCurrentNode(None)", src)
        # 4. Refresh scene tree
        self.assertIn("_scene_tree.refresh", src)

    def test_show_designer_calls_handle_reopen_on_existing(self):
        import inspect

        import mpynode.ui.mpynode_designer as dm

        src = inspect.getsource(dm.show_designer)
        self.assertIn("_handle_reopen", src)
        # The call belongs in the existing-widget branch (after findChild), not
        # the fresh-construction path, which does not need it.
        self.assertGreater(src.find("_handle_reopen"), src.find("findChild"))

    # ------------------------------------------------------------------
    # Stand-in tests: exercise _handle_reopen on a duck-typed object, with
    # no real QMainWindow.
    # ------------------------------------------------------------------

    def _make_stand_in(self):
        """Build a minimal object with the attrs _handle_reopen touches."""
        from mpynode.ui.mpynode_designer import NDMainWindow

        class _FakeTabWidget:
            def __init__(self):
                self._tabs = []  # list of (py_node, fake_tab)

            def count(self):
                return len(self._tabs)

            def widget(self, i):
                return self._tabs[i][1]

            def removeTab(self, i):
                self._tabs.pop(i)

            def addOrRaiseTab(self, py_node):
                self._tabs.append((py_node, _FakeTab(py_node)))

            def pruneStaleTabs(self):
                # Mirror NDScriptTabWidget.pruneStaleTabs: close tabs whose
                # node is definitively gone (False); keep True and unknown
                # (None). Reversed so pop indices stay valid.
                pruned = []
                for i in reversed(range(self.count())):
                    tab = self._tabs[i][1]
                    checker = getattr(tab, "isBackingNodeAlive", None)
                    alive = checker() if callable(checker) else None
                    if alive is not False:
                        continue
                    try:
                        node = tab.getMPyNode()
                        name = node.get_name() if node is not None else None
                    except Exception:
                        name = None
                    self.removeTab(i)
                    tab.deleteLater()
                    pruned.append(name)
                return pruned

            def getOpenNodeNames(self):
                names = []
                for _, t in self._tabs:
                    pn = t.getMPyNode()
                    if pn is not None:
                        try:
                            names.append(pn.get_name())
                        except Exception:
                            pass
                return names

        class _FakeTab:
            def __init__(self, py_node):
                self._py_node = py_node
                # Mirror NDScriptTabContent: an MObjectHandle tracks the exact
                # object (invalid on delete / File>New), NOT the node name.
                self._node_handle = None
                try:
                    import maya.api.OpenMaya as om

                    name = py_node.get_name()
                    if name:
                        sel = om.MSelectionList()
                        sel.add(name)
                        self._node_handle = om.MObjectHandle(
                            sel.getDependNode(0))
                except Exception:
                    self._node_handle = None

            def getMPyNode(self):
                return self._py_node

            def isBackingNodeAlive(self):
                # Tri-state, mirroring NDScriptTabContent.isBackingNodeAlive:
                # True (exists) / False (definitively gone) / None (unknown).
                h = self._node_handle
                if h is None:
                    return None
                try:
                    return bool(h.isValid() and h.isAlive())
                except Exception:
                    return None

            def deleteLater(self):
                pass

        class _FakeSceneTree:
            def __init__(self):
                self.refresh_count = 0

            def refresh(self):
                self.refresh_count += 1

        class _StandIn:
            pass

        s = _StandIn()
        s._scene_callback_ids = []
        s._node_attr_callbacks = {}
        s._node_connection_callbacks = {}
        s._current_node = None
        s._script_tab_widget = _FakeTabWidget()
        s._scene_tree = _FakeSceneTree()

        s._registered = 0
        s._set_current_calls = []

        def _fake_register():
            s._registered += 1
            # Mimic the side-effect of populating callback IDs.
            s._scene_callback_ids.extend([1, 2, 3])

        s._register_scene_callbacks = _fake_register

        # Reopen must also re-install the global middle-click filter that
        # closeEvent removed (else the feature dies after the first reopen).
        s._filter_installs = 0

        def _fake_install_filter():
            s._filter_installs += 1

        s._install_global_middle_click_filter = _fake_install_filter

        # Reopen must also re-subscribe the stored-var listener that closeEvent
        # dropped (guarded on the listener being None, like the scene callbacks).
        s._stored_vars_listener = None
        s._stored_var_registers = 0

        def _fake_register_stored():
            s._stored_var_registers += 1
            s._stored_vars_listener = object()  # mimic "now subscribed"

        s._register_stored_var_listener = _fake_register_stored

        def _fake_set_current(py_node):
            s._set_current_calls.append(py_node)
            s._current_node = py_node

        s.setCurrentNode = _fake_set_current

        # Bind the real _reconcile + _handle_reopen.
        s._reconcile_node_attr_callbacks = (
            NDMainWindow._reconcile_node_attr_callbacks.__get__(s)
        )
        s._handle_reopen = NDMainWindow._handle_reopen.__get__(s)
        return s

    def test_reopen_re_registers_scene_callbacks_when_torn_down(self):
        """If callbacks were torn down (closeEvent), reopen registers them."""
        s = self._make_stand_in()
        s._scene_callback_ids = []  # simulate torn-down state
        s._handle_reopen()
        self.assertEqual(s._registered, 1)
        self.assertGreater(len(s._scene_callback_ids), 0)

    def test_reopen_reinstalls_global_middle_click_filter(self):
        """closeEvent removes the app-wide middle-click filter but keeps the
        singleton alive, so reopen MUST re-install it or middle-click-to-select
        silently dies for the rest of the session."""
        s = self._make_stand_in()
        s._handle_reopen()
        self.assertEqual(
            s._filter_installs, 1,
            "_handle_reopen must re-install the global middle-click filter")

    def test_reopen_resubscribes_stored_var_listener_when_torn_down(self):
        """closeEvent drops the stored-var store listener; reopen must
        re-subscribe it or the Storage panel stops auto-refreshing on stored-var
        changes for the rest of the session."""
        s = self._make_stand_in()
        s._stored_vars_listener = None  # simulate closeEvent teardown
        s._handle_reopen()
        self.assertEqual(
            s._stored_var_registers, 1,
            "_handle_reopen must re-subscribe the stored-var listener")

    def test_reopen_skips_stored_var_resubscribe_when_alive(self):
        """If the listener is still alive (no close happened), don't re-subscribe
        (the add is idempotent, but the guard keeps intent clear + avoids churn)."""
        s = self._make_stand_in()
        s._stored_vars_listener = object()  # still subscribed
        s._handle_reopen()
        self.assertEqual(s._stored_var_registers, 0)

    def test_reopen_skips_re_register_when_callbacks_alive(self):
        """If callbacks are still alive (no close happened), don't double-register."""
        s = self._make_stand_in()
        s._scene_callback_ids = [99]  # already registered
        s._handle_reopen()
        self.assertEqual(s._registered, 0)

    def test_reopen_closes_tabs_for_deleted_nodes(self):
        """Tab whose backing node no longer exists \u2192 closed."""
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

        s = self._make_stand_in()
        # Create a node + add tab, then delete the node.
        n = MPyNode.create(name="reopen_doomed")
        s._script_tab_widget.addOrRaiseTab(n)
        s._current_node = n
        mc.delete("reopen_doomed")
        self.assertFalse(mc.objExists("reopen_doomed"))

        s._handle_reopen()

        # Tab whose node vanished should be closed.
        self.assertEqual(s._script_tab_widget.count(), 0)
        # _current_node should be cleared (setCurrentNode(None) called).
        self.assertIn(None, s._set_current_calls)

    def test_reopen_preserves_tabs_for_alive_nodes(self):
        """Tab whose backing node still exists \u2192 preserved."""
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

        s = self._make_stand_in()
        n = MPyNode.create(name="reopen_alive")
        s._script_tab_widget.addOrRaiseTab(n)
        s._current_node = n

        s._handle_reopen()

        # Tab is preserved.
        self.assertEqual(s._script_tab_widget.count(), 1)
        # setCurrentNode(None) should NOT have been called.
        self.assertNotIn(None, s._set_current_calls)

    def test_reopen_always_refreshes_scene_tree(self):
        """Reopen should always re-query the Scene tree."""
        s = self._make_stand_in()
        before = s._scene_tree.refresh_count
        s._handle_reopen()
        self.assertEqual(s._scene_tree.refresh_count, before + 1)


# ===================== from test_phase04.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase04():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Qt-guarded tests \u2014 UI class structure
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestUIClassesPresent(unittest.TestCase):
    """Inspect-based smoke tests that do NOT instantiate any Qt widgets.
    QApplication construction in mayapy is unreliable (Maya 2024 crashes;
    Maya 2026 needs special offscreen platform). We verify class
    structure via inspect instead."""

    def test_main_window_class(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "_build_ui"))
        self.assertTrue(hasattr(NDMainWindow, "setCurrentNode"))
        # _setSolverContextTabVisible went with the Solver Context tab fold.
        self.assertFalse(hasattr(NDMainWindow, "_setSolverContextTabVisible"))
        self.assertEqual(NDMainWindow.WINDOW_TITLE, "Node Designer 2.0")

    def test_main_window_builds_3_left_tabs(self):
        """3 LEFT tabs (Scene / Attributes / Storage).
        The dedicated Solver Context tab folded into the Storage tab's
        Internal section."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_ui)
        for label in ("Scene", "Attributes", "Variables"):
            self.assertIn(
                f'"{label}"',
                src,
                f"NDMainWindow._build_ui should add {label!r} tab",
            )
        # Solver Context tab is gone.
        self.assertNotIn('"Solver Context"', src)

    def test_attribute_widget_class(self):
        from mpynode.ui.mpynode_designer import NDAttributesWidget

        self.assertTrue(hasattr(NDAttributesWidget, "refresh"))
        self.assertTrue(hasattr(NDAttributesWidget, "refreshInputs"))
        self.assertTrue(hasattr(NDAttributesWidget, "refreshOutputs"))

    def test_input_tree_class(self):
        from mpynode.ui.mpynode_designer import NDInputAttrTree

        self.assertEqual(NDInputAttrTree.ATTR_CATEGORY, "input")
        self.assertEqual(NDInputAttrTree.LIST_ATTR_FUNC_NAME, "get_input_attr_map")
        self.assertTrue(hasattr(NDInputAttrTree, "_buildLockedItems"))

    def test_output_tree_class(self):
        from mpynode.ui.mpynode_designer import NDOutputAttrTree

        self.assertEqual(NDOutputAttrTree.ATTR_CATEGORY, "output")
        self.assertEqual(NDOutputAttrTree.LIST_ATTR_FUNC_NAME, "get_output_attr_map")

    def test_input_tree_uses_walk_plug_tree(self):
        """The input tree's locked-row build path uses the
        unified ``walk_plug_tree`` walker (replaces the legacy
        ``build_locked_rows`` + ``get_recipe`` hand-curated path)."""
        import inspect

        from mpynode.ui.mpynode_designer import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._buildLockedTreeFromWalker)
        self.assertIn("walk_plug_tree", src)
        self.assertIn("treeify", src)

    def test_locked_item_class(self):
        from mpynode.ui.mpynode_designer import NDLockedAttrTreeItem
        from mpynode.ui.qt_wrapper import Qt

        # Must NOT be selectable (LOCKED_FLAGS == ItemIsEnabled only).
        self.assertEqual(NDLockedAttrTreeItem.LOCKED_FLAGS, Qt.ItemIsEnabled)

    def test_solver_context_tree_removed(self):
        """NDSolverContextTree class removed; Storage tab's
        Internal section now surfaces snapshot data inline."""
        from mpynode.ui import mpynode_designer

        self.assertFalse(
            hasattr(mpynode_designer, "NDSolverContextTree"),
            "NDSolverContextTree should be removed.5",
        )


# ===================== from test_phase10.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase10():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Qt-guarded structural tests
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestNDSolverContextTreeWiring(unittest.TestCase):
    """NDSolverContextTree was REMOVED \u2014 the snapshot now
    renders inline in the Storage tab's Internal section. These tests
    were rewritten to pin the post-fold surface."""

    def test_solver_context_class_removed(self):
        """The pre-27.5 NDSolverContextTree class is gone."""
        from mpynode.ui import mpynode_designer

        self.assertFalse(hasattr(mpynode_designer, "NDSolverContextTree"))

    def test_setCurrentNode_does_not_call_solver_context_tab_logic(self):
        """The pre-27.5 has_solver_context / _setSolverContextTabVisible
        wiring is gone from setCurrentNode \u2014 the storage widget owns
        the snapshot now."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.setCurrentNode)
        self.assertNotIn("has_solver_context", src)
        self.assertNotIn("_setSolverContextTabVisible", src)
        # And it still kicks off the storage widget refresh.
        self.assertIn("self._variables_widget.setPyNode", src)


# ===================== from test_scene_tree_single_select.py =====================
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__scene_tree_single_select():
    standalone_init()


class TestSceneTreeSingleSelect(unittest.TestCase):
    def test_init_is_single_select(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        src = inspect.getsource(NDSceneTree.__init__)
        self.assertIn("SingleSelection", src)
        self.assertNotIn("ExtendedSelection", src)

    def test_compile_signal_removed(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        self.assertFalse(hasattr(NDSceneTree, "compileNodesRequested"))

    def test_context_menu_has_no_multiselect_compile_action(self):
        # The OLD multi-select "compile these N nodes" action and its
        # compileNodesRequested signal were removed (the tree is single-select).
        # The single-node compileNodeRequested is a DIFFERENT, wanted feature
        # covered by test_scene_tree_compile_menu, so guard only the PLURAL one.
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        src = inspect.getsource(NDSceneTree._build_context_menu)
        self.assertNotIn("compileNodesRequested", src)   # old plural signal gone
        self.assertNotIn("native plugin", src)           # old action label gone

    def test_other_signals_and_menu_actions_intact(self):
        """Guard against over-deletion: every NON-compile feature stays."""
        from mpynode.ui.widgets.scene_tree import NDSceneTree

        for sig in ("nodeSelected", "exportNodeRequested",
                    "deleteNodeRequested", "nodeRenamed"):
            self.assertTrue(hasattr(NDSceneTree, sig),
                            "scene-tree signal %s must survive" % sig)
        src = inspect.getsource(NDSceneTree._build_context_menu)
        self.assertIn("Rename Node", src)
        self.assertIn("Select Node in Scene", src)
        self.assertIn("Export to", src)
        self.assertIn("Delete Node", src)


class TestDesignerCompileWiring(unittest.TestCase):
    def test_no_right_click_compile_handler(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertFalse(hasattr(NDMainWindow, "_on_compile_nodes_requested"))

    def test_compile_toolbar_entrypoint_intact(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "_on_compile_toolbar"))
        self.assertTrue(hasattr(NDMainWindow, "_open_compile_dialog"))

    def test_designer_does_not_connect_compile_signal(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        # No method on the window may still reference the removed scene-tree
        # compile signal: a dangling .connect() AttributeErrors at construction.
        src = inspect.getsource(NDMainWindow)
        self.assertNotIn("compileNodesRequested", src)


def setUpModule():
    _setUpModule__phase16()
    _setUpModule__phase20()
    _setUpModule__phase04()
    _setUpModule__phase10()
    _setUpModule__scene_tree_single_select()


if __name__ == "__main__":
    import unittest
    unittest.main()
