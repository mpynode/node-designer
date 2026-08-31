"""Node Designer (v1) \u2014 the legacy expression editor.

Layout:
  Splitter:
    LEFT: QTabWidget [Scene | Identity | Attributes | Variables | Framework]
    RIGHT: NDScriptTabWidget (one tab per opened mPy* node)

Selection cascade:
  Scene tree row click
   \u2192 NDSceneTree.nodeSelected emitted
   \u2192 NDMainWindow._on_scene_node_selected wraps name+native_type \u2192 py_node
   \u2192 _script_tab_widget.addOrRaiseTab(py_node)
   \u2192 NDScriptTabWidget.activeNodeChanged emitted
   \u2192 NDMainWindow._on_active_tab_changed
   \u2192 setCurrentNode(py_node) populates Attributes / Framework / Variables

Maya scene callbacks:
  MDGMessage.addNodeAddedCallback per known type \u2192 refresh scene tree
  MDGMessage.addNodeRemovedCallback per known type \u2192 close affected tabs +
    deferred-refresh tree
  MSceneMessage.addCallback(kAfterOpen / kAfterNew) \u2192 reset everything
  All callback IDs torn down in closeEvent().
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode._base.commands import _CreateNodeCommand, run_undoable
from mpynode._node_registry import (
    all_native_types,
    iter_new_node_menu_entries,
    REGISTRY,
    wrap_node,
)
from mpynode.ui.dialogs.about import show_about_dialog
from mpynode.ui.qt_wrapper import (
    maya_main_window,
    QAction,
    QEvent,
    QHeaderView,
    QIcon,
    QKeySequence,
    QLabel,
    QMainWindow,
    QMenu,
    QShortcut,
    QSplitter,
    Qt,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mpynode.ui.widgets.attributes import (
    NDAttributesWidget,
    NDInputAttrTree,
    NDLockedAttrTreeItem,
    NDOutputAttrTree,
    NDUserAttrTreeItem,
)

from mpynode.ui.widgets.framework_tab import NDFrameworkWidget
from mpynode.ui.widgets.profile import NDProfileWidget
from mpynode.ui.widgets.scene_tree import NDSceneTree
from mpynode.ui.widgets.script_tab import NDScriptTabWidget
from mpynode.ui.widgets.tall_tab_bar import make_tabs_tall
from mpynode.ui.widgets.toolbar import NDToolBar
from mpynode.ui.widgets.wide_tab_bar import WideTabBar
from mpynode.ui.widgets.variables import NDVariablesWidget
from mpynode.ui.widgets.watch import NDWatchWidget


# Plug-in names that the designer needs loaded to enumerate scene nodes.
_REQUIRED_PLUGINS = ("mpynode_api1", "mpynode_api2")


def _ensure_plugins_loaded() -> None:
    """Load both mpynode plug-ins if they aren't already.

    The designer queries scene nodes by type. Without the plug-ins
    loaded, those types are unknown and Maya warns "Unknown object
    type: mPyNode" for each.
    """
    for plug in _REQUIRED_PLUGINS:
        try:
            if not mc.pluginInfo(plug, q=True, loaded=True):
                mc.loadPlugin(plug)
        except Exception:
            pass


# ===========================================================================
# Tree items + attribute trees + NDAttributesWidget live in
# widgets/attributes.py. Re-imported at the top of this module for
# backward-compat with ``from mpynode.ui.mpynode_designer import ...``.
# ===========================================================================


# ===========================================================================
# The Solver Context tree is gone: it folded into the Storage panel's Internal
# section, which surfaces both ``INTERNAL_VARS`` schema entries and live
# ``_solverContextSnapshot`` values inline. See
# widgets/variables.py::NDInternalVarItem + _common/internal_vars_helper.py.
# ===========================================================================


# ===========================================================================
# Composite widgets
# ===========================================================================


class NDVariablesWidget(QWidget):  # noqa: F811
    """DEPRECATED placeholder kept for backwards-compat with anything that
    imported NDVariablesWidget from mpynode.ui.mpynode_designer.

    moved the real implementation to widgets/variables.py with
    full +/-/refresh/inline-edit support. This class is just here so old
    imports don't break; the import at the top of this module already
    rebinds the name to the new implementation.
    """

    pass


# Rebind: the stub class def above is evaluated AFTER the top-of-file import,
# so without this, downstream uses would get the empty placeholder.
from mpynode.ui.widgets.variables import NDVariablesWidget  # noqa: F401, E402


# ===========================================================================
# Main window
# ===========================================================================


def _coerce_int_list(value, n):
    """Return ``value`` as a list of exactly ``n`` ints, or None if it is not a
    valid persisted layout value (wrong type / length / non-int element)."""
    if not isinstance(value, (list, tuple)) or len(value) != n:
        return None
    try:
        return [int(x) for x in value]
    except (TypeError, ValueError):
        return None


# The West (vertical) mode-tab bar is the shared WideTabBar -- single source of
# truth with the per-node editor's Expressions | Script switch. Aliased so the
# existing call site (``_WideTabBar(self._mode_tabs)``) and tests keep the name.
_WideTabBar = WideTabBar


def _event_global_pos(event):
    """Global (screen) position of a mouse ``event``, across Qt5 and Qt6.

    Qt6's ``QMouseEvent.globalPosition()`` returns a QPointF (needs
    ``.toPoint()``); Qt5 exposes ``globalPos()`` directly.
    """
    try:
        return event.globalPosition().toPoint()
    except AttributeError:
        return event.globalPos()


def _middle_click_node_from_widget(widget, stop_widget, global_pos):
    """Resolve the mPyNode name for a middle-click at ``global_pos``.

    Walks ``widget`` up its parent chain to (but excluding) ``stop_widget``,
    asking each ancestor that implements ``middleClickNodeName(global_pos)``
    for the node under the cursor. The Scene tree resolves the clicked row; the
    editor tab bar resolves the clicked tab. Any other widget lacks the method,
    so the walk falls through and the caller defaults to the active node.
    Returns the first resolved name, or None.
    """
    w = widget
    while w is not None and w is not stop_widget:
        fn = getattr(w, "middleClickNodeName", None)
        if callable(fn):
            try:
                name = fn(global_pos)
            except Exception:
                name = None
            if name:
                return name
        try:
            w = w.parentWidget()
        except Exception:
            return None
    return None


def _dropped_summary(dropped, limit=15):
    """Body text for the convert/revert 'these edges did not transfer' notice.

    The full list goes to stderr and only the first ``limit`` entries reach the
    dialog. A compiled sibling declares just the attributes its compute uses, so
    an input the compiled node has no use for drops every edge feeding it: a
    167-target blendShape produced a 167-line modal taller than the screen, with
    no way to read or dismiss it comfortably. Truncating the DISPLAY keeps the
    report honest -- the count is exact and nothing is discarded -- while leaving
    the dialog usable.
    """
    import sys

    for d in dropped:
        sys.stderr.write("[NDMainWindow] dropped connection: %s\n" % d)
    shown = dropped[:limit]
    text = "\n".join(shown)
    if len(dropped) > limit:
        text += ("\n... and %d more (full list in the Script Editor)"
                 % (len(dropped) - limit))
    return text


class NDMainWindow(QMainWindow):
    """Node Designer.

    Owns the layout + delegates work to widgets + wires the
    scene-tree-\u2192-tab-raise-\u2192-panel-populate cascade.
    Registers Maya scene callbacks for live refresh.
    """

    WINDOW_TITLE = "Node Designer 2.0"
    WINDOW_OBJECT_NAME = "NodeDesigner2MainWindow"

    def __init__(self, parent=None):
        # Plugins must be loaded BEFORE the scene tree's first refresh.
        _ensure_plugins_loaded()

        # Ensure the per-user data home exists, migrating a legacy hidden
        # ~/.mpynode into the visible ~/mpynode ONCE (no-op when MPYNODE_HOME is
        # set). Here, the canonical entry point, before prefs / compiles read it.
        try:
            from mpynode._common import home

            home.ensure_home()
        except Exception:
            pass

        # Hard singleton: reject construction if another instance exists. Catches
        # a direct ``NDMainWindow()`` that would skip ``show_designer()``'s
        # findChild check. No parent -> look up the Maya main window instead.
        check_parent = parent if parent is not None else maya_main_window()
        if check_parent is not None:
            try:
                existing = check_parent.findChild(QMainWindow, self.WINDOW_OBJECT_NAME)
            except Exception:
                existing = None
            if existing is not None and existing is not self:
                raise RuntimeError(
                    "Node Designer is already open; use "
                    "mpynode.ui.mpynode_designer.show_designer() to focus it."
                )

        super().__init__(parent)
        self.setObjectName(self.WINDOW_OBJECT_NAME)
        self.setWindowTitle(self.WINDOW_TITLE)
        # Window/taskbar icon (512x512 source -> Qt downscales per context).
        # Guarded so a missing file never blocks window construction.
        try:
            import os

            from mpynode.ui.widgets.icons import icon_path

            _win_icon = icon_path("mpynode_hr.png")
            if os.path.exists(_win_icon):
                self.setWindowIcon(QIcon(_win_icon))
        except Exception:
            pass
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.resize(1200, 700)

        # Maya scene callback IDs (torn down in closeEvent).
        self._scene_callback_ids: list = []

        # Per-node MNodeMessage callbacks, node_name → id. Reconciled against
        # the open-tabs set whenever NDScriptTabWidget.tabsChanged fires.
        self._node_attr_callbacks: dict[str, int] = {}
        # Parallel registry for connection-state callbacks (kConnectionMade /
        # kConnectionBroken) so the Attributes panel's connected-dot refreshes
        # when wiring changes OUTSIDE the Designer.
        self._node_connection_callbacks: dict[str, int] = {}

        # track the active node for menu actions.
        self._current_node = None
        # De-dupe key for the global middle-click filter: Qt re-delivers an
        # un-accepted middle press up the parent chain, so act only on the FIRST
        # (deepest = under the cursor) delivery, keyed by event timestamp.
        self._last_middle_click_ts = None
        # Set in _build_ui; defaulted here so early/failed construction is safe.
        self._mode_tabs = None
        self._gallery_panel = None
        self._assistant_panel = None
        # Assistant pane width, remembered for re-showing it after the user has
        # dragged it closed in the Workspace splitter.
        self._last_side_panel_width = 340
        # cache for the persistent Add Attribute dialog.
        self._menu_add_attr_dlg = None
        # Stored-var change listener plumbing. The store fires its notify on an
        # EM WORKER thread; we accumulate the changed node hashes under a lock
        # and keep at most one deferred (main-thread) Storage refresh in flight.
        import threading as _threading

        self._stored_vars_lock = _threading.Lock()
        self._stored_vars_changed_hashes: set = set()
        self._stored_vars_refresh_pending = False
        # Kept so closeEvent can unregister the exact same callable object.
        self._stored_vars_listener = None

        self._build_menu_bar()
        self._build_toolbar()
        self._build_ui()
        self._wire_signals()
        self._install_shortcuts()
        self._register_scene_callbacks()
        self._register_stored_var_listener()
        # Global middle-click -> select the node under the cursor (else the
        # active node) in the Maya scene, anywhere in the Designer.
        self._install_global_middle_click_filter()
        self._scene_tree.refresh()
        # If mPy* nodes already exist when the designer first opens, auto-select
        # the first so the expression tabs come up populated instead of blank.
        self._auto_select_first_node()

    def _auto_select_first_node(self) -> None:
        """Pick the first mPy* node in the scene tree (if any) and
        emit its ``nodeSelected`` signal to populate the editor tabs.

        Idempotent + safe to call on both fresh launches AND reopens.
        Bails out if any script tab is already open (so the user's
        prior tabs survive a reopen when the scene didn't change);
        when the prior scene's tabs were all stale and pruned by
        ``_handle_reopen``, ``count()`` is 0 and we auto-select the
        first node of the freshly-loaded scene.
        """
        try:
            if self._script_tab_widget.count() > 0:
                return
        except Exception:
            return
        try:
            top = self._scene_tree.topLevelItem(0)
        except Exception:
            top = None
        if top is None:
            return
        from mpynode.ui.widgets.scene_tree import NDSceneTreeItem

        if not isinstance(top, NDSceneTreeItem):
            return
        try:
            self._scene_tree.selectNode(top.node_name)
            # selectNode only updates the visual selection, and nodeSelected
            # fires only on user-driven changes -- so emit it explicitly.
            self._scene_tree.nodeSelected.emit(top.node_name, top.native_type)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        # Align the toolbar's New button with the central content's left
        # edge (File menu / tabs panel) instead of the bare window border.
        try:
            self._toolbar.set_left_inset(outer.contentsMargins().left())
        except Exception:
            pass

        # Top-level mode switcher: Workspace (tree | editor | Assistant) and
        # Templates (full-width gallery). Two big tabs that swap the entire
        # content region; both pages stay alive so editor and gallery state
        # survive. Tradeoff: gallery + editor are never visible at once.
        self._mode_tabs = QTabWidget(central)
        # 1.5x-wider tab bar so the vertical mode switch is a more noticeable
        # target. Install BEFORE addTab/setMovable so those apply to the custom
        # bar; keep a Python ref so PySide can't GC the wrapper (that would
        # drop the tabSizeHint override and revert the width).
        self._mode_tab_bar = _WideTabBar(self._mode_tabs)
        self._mode_tabs.setTabBar(self._mode_tab_bar)
        self._mode_tabs.setMovable(False)
        self._mode_tabs.setTabsClosable(False)
        # Vertical tabs down the LEFT edge (West). As a horizontal bar this mode
        # switch stacked right above the Scene | Attributes | Variables panel
        # tabs, and the two rows of tabs were hard to tell apart.
        self._mode_tabs.setTabPosition(QTabWidget.West)

        # Templates gallery = the full-width Templates mode page. Built up front
        # (cheap/pure-Qt) and OUTSIDE the assistant's try/except below so the
        # Templates mode is always available even if the assistant fails.
        from mpynode.ui.widgets.template_gallery_panel import (
            NDTemplateGalleryPanel,
        )

        self._gallery_panel = NDTemplateGalleryPanel(
            self._mode_tabs, on_create=self._create_from_template
        )

        # Workspace mode page: tree | editor+tools | Assistant, in one splitter.
        workspace = QWidget(self._mode_tabs)
        ws_layout = QVBoxLayout(workspace)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal, workspace)

        # LEFT: tab widget with the 4 panels.
        self._panel_tab_widget = QTabWidget(splitter)
        # 1.5x taller horizontal tabs (Scene | Attributes | Variables) — the
        # North-bar analog of the West mode tabs' widen. Install the tall bar
        # BEFORE addTab (setTabBar wipes existing tabs); keep the ref (GC).
        self._panel_tab_bar = make_tabs_tall(self._panel_tab_widget)
        self._panel_tab_widget.setMovable(False)
        self._panel_tab_widget.setTabsClosable(False)

        # Scene tab: scene tree (top) over the Identity panel (bottom), split by
        # a draggable splitter, so editing a node's Class keeps the tree and the
        # node's siblings in view (Identity used to be its own left-hand tab).
        # Refresh lives on the tree's right-click context menu.
        from mpynode.ui.widgets.identity_tab import NDIdentityWidget

        self._scene_split = QSplitter(Qt.Vertical, self._panel_tab_widget)
        self._scene_tree = NDSceneTree(self._scene_split)
        self._identity_widget = NDIdentityWidget(self._scene_split)
        self._scene_split.addWidget(self._scene_tree)
        self._scene_split.addWidget(self._identity_widget)
        # The tree is the primary surface and never collapses; the identity
        # panel MAY be dragged shut by users who never rename Classes.
        self._scene_split.setStretchFactor(0, 3)
        self._scene_split.setStretchFactor(1, 1)
        self._scene_split.setCollapsible(0, False)
        self._scene_split.setCollapsible(1, True)
        self._scene_split.setSizes([340, 150])
        self._panel_tab_widget.addTab(self._scene_split, "Scene")

        self._attributes_widget = NDAttributesWidget(self._panel_tab_widget)
        self._panel_tab_widget.addTab(self._attributes_widget, "Attributes")

        self._variables_widget = NDVariablesWidget(self._panel_tab_widget)
        self._panel_tab_widget.addTab(self._variables_widget, "Variables")

        # Framework is the rightmost tab: read-only per-type surface (blessed
        # methods + non-plug State slots), least-frequently touched.
        self._framework_widget = NDFrameworkWidget(self._panel_tab_widget)
        self._panel_tab_widget.addTab(self._framework_widget, "Framework")

        # RIGHT: vertical split between editor (top) and tools (bottom).
        right_split = QSplitter(Qt.Vertical, splitter)
        self._right_split = right_split

        self._script_tab_widget = NDScriptTabWidget(right_split)

        from mpynode.ui.qt_wrapper import QTabWidget as _QTabWidget

        self._tools_tab_widget = _QTabWidget(right_split)
        # 1.5x taller horizontal tabs (Log | Watch | Profile) — same tall bar
        # as the panel strip. Install BEFORE addTab; keep the ref (GC).
        self._tools_tab_bar = make_tabs_tall(self._tools_tab_widget)
        self._tools_tab_widget.setMovable(False)
        self._tools_tab_widget.setTabsClosable(False)

        # Order is [Log, Watch, Profile]: Log is the most-used (errors /
        # expression output), Watch second (live values), Profile last.
        # The Log tab is a read-only running log with right-click Clear /
        # Copy All, subscribed to the module-level broadcast bus so any
        # ``ui.widgets.logger.log("...")`` call in the codebase posts here.
        from mpynode.ui.widgets.logger import NDLoggerWidget

        self._logger_widget = NDLoggerWidget(self._tools_tab_widget)
        self._tools_tab_widget.addTab(self._logger_widget, "Log")

        self._watch_widget = NDWatchWidget(self._tools_tab_widget)
        self._tools_tab_widget.addTab(self._watch_widget, "Watch")

        self._profile_widget = NDProfileWidget(self._tools_tab_widget)
        self._tools_tab_widget.addTab(self._profile_widget, "Profile")

        right_split.addWidget(self._script_tab_widget)
        right_split.addWidget(self._tools_tab_widget)
        # The tools panel must NEVER fully collapse, or it is easy to forget
        # the Profile / Watch panel exists.
        right_split.setCollapsible(0, False)
        right_split.setCollapsible(1, False)
        # Minimum height EXACTLY the tab bar, no margin for body content: at the
        # splitter's lowest position only the tab labels show, and body toolbars
        # (Log's Clear, Profile's Reset Stats) clip fully. 40 left ~10px and the
        # Clear button peeked through. DERIVED from the live tall bar, not a
        # constant, so it tracks the 1.5x-taller tabs and per-binding bar height
        # -- a hard-coded 30 clipped the taller labels themselves.
        self._tools_tab_widget.setMinimumHeight(
            self._tools_tab_bar.sizeHint().height()
        )
        # Tall enough for the Profile tab's toolbar + 5 stat rows + the deep-
        # profile tree header and first row without dragging (~260px of body);
        # the editor still keeps the lion's share.
        right_split.setSizes([610, 260])

        splitter.addWidget(self._panel_tab_widget)
        splitter.addWidget(right_split)

        # RIGHT: AI Assistant pane beside the editor. Wrapped so an
        # import/construct failure degrades to a Workspace without the
        # Assistant rather than blocking the window.
        self._assistant_panel = None
        try:
            from mpynode.ui.widgets.assistant_panel import NDAssistantPanel

            self._assistant_panel = NDAssistantPanel(
                splitter,
                get_current_node=self._current_node_name,
                on_nodes_changed=self._on_assistant_changed,
            )
            splitter.addWidget(self._assistant_panel)
        except Exception as _exc:
            import sys as _sys

            _sys.stderr.write(
                "[node designer] assistant panel unavailable: %s\n" % _exc
            )

        # The editor never collapses. The left panel and the Assistant pane may
        # both be dragged shut -- the handle stays put, so either comes back.
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, False)
        if self._assistant_panel is not None:
            splitter.setCollapsible(2, True)
            splitter.setSizes([280, 580, 340])
        else:
            splitter.setSizes([280, 900])
        self._main_splitter = splitter
        ws_layout.addWidget(splitter)

        # Assemble the two modes. Workspace is tab 0 (default); Templates is the
        # full-width gallery page.
        self._mode_tabs.addTab(workspace, "Workspace")
        self._mode_tabs.addTab(self._gallery_panel, "Templates")
        self._mode_tabs.setCurrentIndex(0)  # Workspace default
        outer.addWidget(self._mode_tabs)

        # Stop a template video preview whenever the active mode is not
        # Templates (a QMediaPlayer must never play under a hidden page).
        self._mode_tabs.currentChanged.connect(self._on_mode_tab_changed)

        # Restore persisted layout (splitters + geometry + active mode); a
        # first run keeps the hard-coded defaults set above.
        self._restore_layout()

    # ------------------------------------------------------------------
    # Assistant panel host hooks
    # ------------------------------------------------------------------

    def _current_node_name(self):
        """Active node name for the assistant's working context (or None)."""
        try:
            return self._current_node.get_name() if self._current_node else None
        except Exception:
            return None

    def _on_assistant_changed(self, name):
        """Called (on the main thread) after the assistant mutates a node.
        Refresh the scene tree + open/raise the node's editor + refresh
        Attributes / Variables so the user immediately sees the result."""
        try:
            self._scene_tree.refresh()
        except Exception:
            pass
        if not name:
            return
        # Select the node in the Scene tab so it becomes the "current" node and
        # the rest of the UI follows what the agent just created/edited.
        try:
            if mc.objExists(name):
                self._scene_tree.selectNode(name)
        except Exception:
            pass
        try:
            if mc.objExists(name):
                py = wrap_node(name, mc.nodeType(name))
                if py is not None:
                    self._script_tab_widget.addOrRaiseTab(py)
        except Exception:
            pass
        for fn in (self._refresh_editor_for_node, self._refresh_attributes_for_node):
            try:
                fn(name)
            except Exception:
                pass
        try:
            self._variables_widget.refresh()
        except Exception:
            pass

    def toggle_assistant_panel(self):
        """Show/hide the Assistant pane in the Workspace, switching to Workspace
        mode first (the Assistant only lives there). Orphan today (no menu item
        calls it) — the splitter handle already covers show/hide — but kept
        correct for a future caller."""
        if self._assistant_panel is None:
            return
        self._show_workspace_mode()
        showing = not self._assistant_panel.isVisible()
        self._assistant_panel.setVisible(showing)
        if showing:
            try:
                sizes = self._main_splitter.sizes()
                if len(sizes) >= 3 and sizes[2] < 10:
                    sizes[2] = self._last_side_panel_width
                    self._main_splitter.setSizes(sizes)
            except Exception:
                pass

    def _on_mode_tab_changed(self, index):
        """Persist the active mode and stop the gallery's video preview whenever
        the active mode is not Templates."""
        from mpynode.ui.preferences import set_pref

        try:
            set_pref("layout_mode_tab", int(index))
        except Exception:
            pass
        try:
            if self._mode_tabs.tabText(index) != "Templates":
                self._gallery_panel.stop_video()
        except Exception:
            pass

    def _restore_layout(self):
        """Best-effort restore of the persisted window layout. Malformed values
        are ignored and the hard-coded defaults set in _build_ui stand."""
        from mpynode.ui.preferences import get_pref

        geo = _coerce_int_list(get_pref("layout_window_geometry"), 4)
        if geo is not None:
            try:
                self.setGeometry(*geo)
            except Exception:
                pass
        # The Workspace splitter has 3 panes (tree, editor, Assistant) or 2 if
        # the Assistant failed to construct; coerce to the actual pane count.
        try:
            n_main = self._main_splitter.count()
        except Exception:
            n_main = 3
        main = _coerce_int_list(get_pref("layout_main_splitter"), n_main)
        if main is not None:
            try:
                self._main_splitter.setSizes(main)
            except Exception:
                pass
        # Remember the (restored or default) Assistant-pane width.
        try:
            sizes = self._main_splitter.sizes()
            if len(sizes) >= 3 and sizes[2] > 10:
                self._last_side_panel_width = sizes[2]
        except Exception:
            pass
        right = _coerce_int_list(get_pref("layout_right_splitter"), 2)
        if right is not None:
            try:
                self._right_split.setSizes(right)
            except Exception:
                pass
        try:
            mode = int(get_pref("layout_mode_tab", 0))
        except Exception:
            mode = 0
        try:
            if 0 <= mode < self._mode_tabs.count():
                self._mode_tabs.setCurrentIndex(mode)
        except Exception:
            pass

    def _wire_signals(self) -> None:
        # No Refresh connection here: it is a right-click action on the scene
        # tree, whose contextMenuEvent invokes self._scene_tree.refresh direct.
        self._scene_tree.nodeSelected.connect(self._on_scene_node_selected)
        # Export-from-scene-tree right-click → file dialog.
        self._scene_tree.exportNodeRequested.connect(self._on_export_node_requested)
        self._scene_tree.exportNodeScriptRequested.connect(
            self._on_export_node_script_requested
        )
        self._scene_tree.copyNodeScriptRequested.connect(
            self._on_copy_node_script_requested
        )
        self._scene_tree.deleteNodeRequested.connect(self._on_delete_node_requested)
        self._scene_tree.nodeInfoRequested.connect(self._on_node_info_requested)
        self._scene_tree.duplicateNodeRequested.connect(
            self._on_duplicate_node_requested
        )
        self._scene_tree.duplicateWithInputsRequested.connect(
            self._on_duplicate_with_inputs_requested
        )
        self._scene_tree.runSetupRequested.connect(self._on_run_setup_requested)
        self._scene_tree.runDemoRequested.connect(self._on_run_demo_requested)
        self._scene_tree.nameClassRequested.connect(
            self._on_name_class_requested
        )
        self._scene_tree.reclassifyRequested.connect(
            self._on_reclassify_requested
        )
        self._scene_tree.convertToCppRequested.connect(
            self._on_convert_to_cpp_requested
        )
        self._scene_tree.revertToPyRequested.connect(
            self._on_revert_to_py_requested
        )
        self._scene_tree.compileNodeRequested.connect(
            self._on_compile_node_requested
        )
        self._scene_tree.loadCompiledPluginRequested.connect(
            self._on_load_compiled_plugin_requested
        )
        self._scene_tree.nodeRenamed.connect(self._on_node_renamed)
        self._script_tab_widget.activeNodeChanged.connect(self._on_active_tab_changed)
        # Reconcile per-node MNodeMessage callbacks when the open tabs change.
        self._script_tab_widget.tabsChanged.connect(self._reconcile_node_attr_callbacks)
        # Refresh Profile + Watch right after an expression Save; they used to
        # stay stale until the user toggled the tab.
        self._script_tab_widget.tabSaved.connect(self._on_tab_saved)
        # WS2 concierge: an OSL intractability hand-off from any tab's OSL editor
        # routes to the assistant panel (same handler as the compile dialog's
        # "Fix with AI"). A hard "can't convert to OSL" becomes a conversation.
        self._script_tab_widget.handoffToAssistant.connect(
            self._route_compile_handoff)
        # The API view abstracts persistent-variable DATA down to a name;
        # clicking one raises the Variables tab, where the value is shown.
        self._script_tab_widget.revealVariableRequested.connect(
            self.revealVariable)
        # Same rule for the generated attribute blocks: the baked
        # add_input_attr / add_output_attr calls are a read-only rendering, so a
        # click goes to the Attributes tab where they are actually authored.
        self._script_tab_widget.revealAttributesRequested.connect(
            self.revealAttributes)
        # The Framework panel is tier-scoped: an expression tier's `self` is a
        # SelfProxy, the API tab's is the wrapper, and the two surfaces are
        # disjoint. Follow the strip so the panel never lists a method the
        # visible tab would raise AttributeError on.
        self._script_tab_widget.tierChanged.connect(
            self._framework_widget.setActiveTier)
        # When the artist sets/clears a user-attr colour, push the new map into
        # the script editor's highlighter so `self.driverMatrixA` renders in the
        # chosen colour immediately, with no node reload.
        try:
            self._attributes_widget.attrColorChanged.connect(
                self._on_attr_color_changed
            )
        except Exception:
            pass
        # An attr rename rewrites the node's stored expression sources, so
        # reload the open editor tab to match.
        try:
            self._attributes_widget.attrRenamed.connect(
                self._on_attr_renamed
            )
        except Exception:
            pass
        # An Identity-tab (re)name must re-render the scene-tree Option A label.
        try:
            self._identity_widget.classChanged.connect(
                lambda _name: self._scene_tree.refresh_node_class_tag(
                    self._current_node.get_name()
                    if self._current_node else None))
        except Exception:
            pass

    def _on_attr_color_changed(self, node_name: str) -> None:
        """Walk the open script tabs + refresh the
        highlighter var-color map for any tab whose node matches
        ``node_name``. The map is rebuilt from the wrapper's
        get_all_attr_colors() so adds / clears / updates all
        propagate uniformly."""
        try:
            n = self._script_tab_widget.count()
        except Exception:
            return
        for i in range(n):
            try:
                tab = self._script_tab_widget.widget(i)
                py = tab.getMPyNode() if hasattr(tab, "getMPyNode") else None
                if py is None:
                    continue
                try:
                    if py.get_name()!= node_name:
                        continue
                except Exception:
                    continue
                # NDScriptTabContent exposes the expression editor
                # as ``_expr_editor`` (see script_tab_content.py).
                editor = getattr(tab, "_expr_editor", None)
                if editor is not None and hasattr(editor, "refreshVarColors"):
                    editor.refreshVarColors()
            except Exception:
                continue

    def _on_tab_saved(self, py_node) -> None:
        """NDScriptTabWidget.tabSaved handler. Re-refresh
        the right-side Profile + Watch widgets if they're currently
        bound to the just-saved node."""
        try:
            cur_pw = self._profile_widget._py_node
        except Exception:
            cur_pw = None
        if (
            cur_pw is not None
            and py_node is not None
            and (cur_pw.get_name() == py_node.get_name())
        ):
            try:
                self._profile_widget.refresh()
            except Exception:
                pass
        try:
            cur_ww = self._watch_widget._py_node
        except Exception:
            cur_ww = None
        if (
            cur_ww is not None
            and py_node is not None
            and (cur_ww.get_name() == py_node.get_name())
        ):
            try:
                self._watch_widget.refresh()
            except Exception:
                pass

        try:
            cur_vw = self._variables_widget._py_node
        except Exception:
            cur_vw = None
        if (
            cur_vw is not None
            and py_node is not None
            and (cur_vw.get_name() == py_node.get_name())
        ):
            # _saveTab force-evaluated the node before emitting tabSaved,
            # so any newly-written self.X vars are already in the store.
            try:
                self._variables_widget.refresh()
            except Exception:
                pass

        # #68: keep the Identity panel's Class in sync when the saved tab
        # belongs to the node it is showing -- a save may have stamped/changed
        # the canonical Class. Mirrors the Variables re-sync above.
        try:
            cur_iw = self._identity_widget._py_node
        except Exception:
            cur_iw = None
        if (
            cur_iw is not None
            and py_node is not None
            and (cur_iw.get_name() == py_node.get_name())
        ):
            try:
                self._identity_widget.setPyNode(py_node)
            except Exception:
                pass

    def _on_export_node_requested(self, node_name: str, native_type: str) -> None:
        """Handler for the Scene tree's Export-to-.mpn right-click."""
        from mpynode._node_registry import wrap_node

        try:
            py_node = wrap_node(node_name, native_type)
        except Exception:
            return
        self._export_node_as_mpn(py_node)

    def _on_node_info_requested(self, node_name: str, native_type: str) -> None:
        """Handler for the Scene tree's Info… right-click -- open the per-node
        metadata (authors/version/license/description) editor."""
        from mpynode._node_registry import wrap_node

        try:
            py_node = wrap_node(node_name, native_type)
        except Exception:
            return
        if py_node is None:
            return
        from mpynode.ui.dialogs.node_info import NDNodeInfoDialog

        dlg = NDNodeInfoDialog(py_node, parent=self)
        dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()

    def _on_export_node_script_requested(
        self, node_name: str, native_type: str
    ) -> None:
        """Handler for the Scene tree's Bake-to-.py-Script right-click."""
        from mpynode._node_registry import wrap_node

        try:
            py_node = wrap_node(node_name, native_type)
        except Exception:
            return
        self._export_node_as_py(py_node)

    def _on_copy_node_script_requested(
        self, node_name: str, native_type: str
    ) -> None:
        """Handler for the Scene tree's Copy-Baked-.py-Script right-click."""
        from mpynode._node_registry import wrap_node

        try:
            py_node = wrap_node(node_name, native_type)
        except Exception:
            return
        self._copy_node_as_py(py_node)

    def _on_compile_toolbar(self) -> None:
        """Toolbar / Node-menu "Compile…" launcher. Opens the compile dialog,
        which lists every mPy* node in the scene with checkboxes."""
        self._open_compile_dialog()

    def _on_compile_node_requested(self, node_name, native_type) -> None:
        """Scene-tab right-click "Compile…": open the compile dialog with this
        node preselected (checked), so the user is one click from compiling just
        it."""
        self._open_compile_dialog(preselect=node_name)

    def _on_load_compiled_plugin_requested(self) -> None:
        """Scene-tab right-click "Load Compiled Plug-in…": browse for an
        already-built ``.bundle`` and make it resident in THIS session.

        A compiled node type only exists while its plug-in is loaded, and nothing
        puts ``~/mpynode/compiled`` on ``MAYA_PLUG_IN_PATH`` -- so after a Maya
        restart, or after declining the post-compile "Load it into Maya now?"
        prompt, the type is simply gone and "Convert Node to C++" is greyed out.
        Without this entry the only way back is to compile the node again.

        Goes through the SAME ``load_or_reload_native_plugin`` the compile dialog
        uses (unload-first so a stale build cannot linger, never ``file(new)``),
        then refreshes the Scene tab so the tri-state C++ badge and the Convert
        action re-evaluate against the now-registered type.
        """
        import os

        from mpynode._base.plugins import load_or_reload_native_plugin
        from mpynode._common import home
        from mpynode.ui.qt_wrapper import QFileDialog, QMessageBox

        start = home.compiled_dir()
        if not os.path.isdir(start):
            start = home.home_dir()
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Load Compiled Plug-in",
            start,
            "Compiled plug-in (*.bundle *.so *.mll);;All files (*)",
        )
        if not path:
            return

        res = load_or_reload_native_plugin(path)
        if res.get("error"):
            QMessageBox.critical(self, "Load Compiled Plug-in",
                                 res["error"])
            return

        # Report what the plug-in actually brought in: the node TYPE is the thing
        # that ungreys Convert, so naming it is the confirmation the user needs.
        base = res.get("base") or os.path.basename(path)
        try:
            types = mc.pluginInfo(base, q=True, dependNode=True) or []
            cmds_ = mc.pluginInfo(base, q=True, command=True) or []
        except Exception:
            types, cmds_ = [], []
        try:
            self._scene_tree.refresh()
        except Exception:
            pass
        QMessageBox.information(
            self, "Load Compiled Plug-in",
            "%s %s.\n\nNode type(s): %s\nCommand(s): %s"
            % (base,
               "reloaded" if res.get("reloaded") else "loaded",
               ", ".join(types) or "(none)",
               ", ".join(cmds_) or "(none)"))

    def _open_compile_dialog(self, preselect=None) -> None:
        """Open (or raise) the single non-modal CompileDialog.

        The dialog lists every mPy* node in the CURRENT scene; ``refresh_nodes``
        re-queries the live scene on every open so it never shows nodes from a
        previous scene. Non-modal so the user can keep working while a compile
        runs (it never touches the scene); a single reused instance avoids a
        pile of duplicate windows.

        ``preselect`` (a scene node name) checks exactly that node after the
        refresh, so the scene-tab right-click "Compile…" lands on it directly.
        """
        # Local import to avoid a top-level cycle (the dialog pulls in the
        # native compile stack, which need not load until first used).
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        dlg = getattr(self, "_compile_dialog", None)
        if dlg is not None:
            try:
                dlg.refresh_nodes()
                if preselect:
                    dlg.preselect_node(preselect)
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
                return
            except Exception:
                # The previous dialog was destroyed; fall through and remake it.
                self._compile_dialog = None

        dlg = CompileDialog(parent=self)
        # WS2 concierge: route the dialog's "Fix with AI" hand-off to the
        # assistant panel (the dialog stays decoupled from the panel).
        try:
            dlg.handoffToAssistant.connect(self._route_compile_handoff)
        except Exception:
            pass
        # #68: after the dialog's class-less gate STAMPS a canonical Class on a
        # freshly-compiled node, refresh the Identity panel / Scene tree so the
        # new Class shows immediately (mirrors the Reclassify re-sync).
        try:
            dlg.classesStamped.connect(self._on_compile_dialog_classes_stamped)
        except Exception:
            pass
        self._compile_dialog = dlg
        if preselect:
            dlg.preselect_node(preselect)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _route_compile_handoff(self, handoff) -> None:
        """Seed the assistant panel with a compile hand-off from the compile
        dialog's "Fix with AI" button. Reveals the panel and pre-fills the
        starter prompt; whether it sends immediately follows the
        ``auto_recompile`` preference (else the user reviews and presses send --
        the first compile always requires a human press)."""
        panel = getattr(self, "_assistant_panel", None)
        if panel is None:
            return
        try:
            from mpynode.ui import preferences

            autosend = bool(preferences.get_pref("auto_recompile", False))
        except Exception:
            autosend = False
        try:
            panel.setVisible(True)
            panel.raise_()
        except Exception:
            pass
        try:
            panel.seed_compile_context(handoff, autosend=autosend)
        except Exception as exc:  # never let a hand-off crash the designer
            import sys

            sys.stderr.write("[node designer] compile hand-off failed: %s\n"
                             % exc)

    def _on_delete_node_requested(self, node_name: str, native_type: str) -> None:
        """Handler for the Scene tree's Delete-Node right-click.

        Confirms, closes any open tab for the node, deletes it from the
        scene (undoable via Maya's normal undo queue), then refreshes the
        tree.
        """
        from mpynode.ui.qt_wrapper import QMessageBox

        if not mc.objExists(node_name):
            self._scene_tree.refresh()
            return
        resp = QMessageBox.question(
            self,
            "Delete Node",
            "Delete '{0}' from the scene?".format(node_name),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        # Close the node's tab first so no panel holds a stale wrapper when
        # the node disappears.
        try:
            self._script_tab_widget.closeTabForNode(node_name)
        except Exception:
            pass
        # If this node is coexist-converted, delete its hidden compiled sibling
        # too (it is locked + load-bearing -- leaving it would orphan downstream
        # with no way to reach it from the tree). Both deletes ride ONE undo
        # chunk so a single Ctrl+Z restores the pair.
        from mpynode._base.commands import is_converted, linked_compiled_node

        cpp = linked_compiled_node(node_name) if is_converted(node_name) else None
        try:
            mc.undoInfo(openChunk=True)
            try:
                if cpp and mc.objExists(cpp):
                    try:
                        mc.lockNode(cpp, lock=False)
                    except Exception:
                        pass
                    # Break the message link FIRST: it makes the two nodes delete
                    # together, so deleting the sibling with the link intact
                    # would destroy this node too and error on the delete below.
                    if mc.attributeQuery(
                            "mpyCompiledLink", node=node_name, exists=True):
                        try:
                            mc.deleteAttr(node_name + ".mpyCompiledLink")
                        except Exception:
                            pass
                    if mc.objExists(cpp):
                        mc.delete(cpp)
                if mc.objExists(node_name):
                    mc.delete(node_name)
            finally:
                mc.undoInfo(closeChunk=True)
        except Exception as exc:
            import sys

            sys.stderr.write(
                f"[NDMainWindow] delete node {node_name!r} failed: {exc}\n"
            )
        self._scene_tree.refresh()

    def _on_node_renamed(self, old_name: str, new_name: str) -> None:
        """Scene tree inline-rename applied -> retitle the open editor tab."""
        try:
            self._script_tab_widget.renameTabForNode(old_name, new_name)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Duplicate (Scene-tree right-click + Node menu)
    # ------------------------------------------------------------------

    def _on_duplicate_node_requested(self, node_name: str, native_type: str) -> None:
        """Scene-tree "Duplicate": deep-copy the node (incl. independent
        persistent data), NO input connections."""
        self._duplicate_node(node_name, native_type, with_inputs=False)

    def _on_duplicate_with_inputs_requested(
        self, node_name: str, native_type: str
    ) -> None:
        """Scene-tree "Duplicate + Inputs": deep-copy + re-wire input
        connections from the source's upstream onto the copy."""
        self._duplicate_node(node_name, native_type, with_inputs=True)

    def _on_run_setup_requested(self, node_name: str, native_type: str) -> None:
        """Scene-tree "Run setup": run the node's own setup() on the current
        selection, in one undo chunk."""
        from mpynode._base.commands import _RunSetupCommand

        run_undoable(_RunSetupCommand(node_name, native_type))
        self._scene_tree.refresh()

    def _on_run_demo_requested(
        self, node_name: str, native_type: str, demo_name: str = ""
    ) -> None:
        """Scene-tree "Run demo": run the node's own demo() (fabricates its own
        showcase scene, NO selection), in one undo chunk. ``demo_name`` selects
        among multiple demos (empty string -> the sole/first demo)."""
        from mpynode._base.commands import _RunDemoCommand

        run_undoable(_RunDemoCommand(node_name, native_type, demo_name or None))
        self._scene_tree.refresh()

    # ------------------------------------------------------------------
    # Canonical Class identity (Name / Rename / Reclassify + bake name prompt)
    # ------------------------------------------------------------------

    def _prompt_for_class_name(self, py_node, *, default: str = "") -> str | None:
        """Ask the user for a Class name (PascalCase). Loops on an invalid
        identifier; WARNS (but allows) a leading-lowercase name. Returns the
        name, or ``None`` if the user cancelled.

        Used as the bake ``prompt_fn`` and by "Name Class…" / "Rename Class" /
        "Reclassify". The class name is an IDENTITY choice -- it is never
        derived from the node name."""
        from mpynode._common.io.py_export import is_valid_class_name
        from mpynode.ui.qt_wrapper import QInputDialog, QMessageBox

        text = default
        while True:
            entered, ok = QInputDialog.getText(
                self,
                "Class Name",
                "Class name for this node (PascalCase, e.g. BlackWhiteFile):",
                text=text,
            )
            if not ok:
                return None
            entered = (entered or "").strip()
            if not is_valid_class_name(entered):
                QMessageBox.warning(
                    self,
                    "Invalid Class Name",
                    "%r is not a valid Python class name. Use a letter/underscore "
                    "start and letters, digits or underscores only (no spaces, "
                    "not a keyword)." % entered,
                )
                text = entered
                continue
            if entered[:1].islower():
                resp = QMessageBox.question(
                    self,
                    "Lowercase Class Name",
                    "Class names are conventionally PascalCase. Use %r anyway?"
                    % entered,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if resp != QMessageBox.Yes:
                    text = entered
                    continue
            return entered

    def _instances_of_class(self, class_path: str, native_type: str):
        """Every scene node of ``native_type`` currently stamped with exactly
        ``class_path``. Used by the Rename Class cascade so renaming a Class
        re-stamps all of its instances, not just the selected one."""
        from mpynode.wrappers._mpy_node import _read_py_class

        if not class_path:
            return []
        try:
            nodes = mc.ls(type=native_type) or []
        except Exception:
            return []
        return [n for n in nodes if _read_py_class(n) == class_path]

    def _apply_class_name(
        self, node_name: str, native_type: str, new_name: str, *, cascade: bool
    ) -> None:
        """Synthesize ``mpynode_user.<new_name>`` and stamp it as ``class_path``.

        When ``cascade`` (a Rename), re-stamp EVERY scene instance of the
        selected node's current Class -- as one Maya undo chunk -- and refresh
        each row. Otherwise (Name a class-less node, or Fork one instance),
        stamp only the selected node. Renaming the derived NODE names is out of
        scope until a ``node_name_pinned`` plug + name-from-class derivation
        exist (see the design's rename-cascade section)."""
        from mpynode._node_registry import wrap_node
        from mpynode._common.io.user_classes import synthesize, dotted_path
        from mpynode.wrappers._mpy_node import _read_py_class

        try:
            py_node = wrap_node(node_name, native_type)
        except Exception:
            py_node = None
        if py_node is None:
            return
        old_path = ""
        try:
            old_path = py_node.get_py_class() or ""
        except Exception:
            old_path = ""
        new_path = dotted_path(new_name)
        try:
            synthesize(new_name, native_type)
        except Exception:
            return
        targets = (self._instances_of_class(old_path, native_type)
                   if (cascade and old_path) else [node_name])
        if node_name not in targets:
            targets.append(node_name)
        opened = False
        try:
            if len(targets) > 1:
                mc.undoInfo(openChunk=True)
                opened = True
            for n in targets:
                try:
                    wn = wrap_node(n, native_type)
                    if wn is not None:
                        wn.set_py_class(new_path)
                except Exception:
                    pass
        finally:
            if opened:
                mc.undoInfo(closeChunk=True)
        for n in targets:
            self._scene_tree.refresh_node_class_tag(n)
        # Keep the Identity panel in sync if it is showing an affected node.
        try:
            if (self._current_node is not None
                    and self._current_node.get_name() in targets):
                self._identity_widget.setPyNode(self._current_node)
        except Exception:
            pass

    def _on_compile_dialog_classes_stamped(self, names) -> None:
        """#68: the compile dialog's class-less gate stamped a canonical Class
        on one or more nodes (verified-stamped only). Refresh the Scene tree
        class tag and the Identity panel so the new Class shows immediately --
        mirrors the Reclassify re-sync above."""
        try:
            names = list(names or [])
        except Exception:
            names = []
        if not names:
            return
        for n in names:
            try:
                self._scene_tree.refresh_node_class_tag(n)
            except Exception:
                pass
        try:
            if (self._current_node is not None
                    and self._current_node.get_name() in names):
                self._identity_widget.setPyNode(self._current_node)
        except Exception:
            pass

    def _on_name_class_requested(
        self, node_name: str, native_type: str
    ) -> None:
        """Scene-tree "Name Class…" (class-less) / "Rename Class" (classed):
        prompt for a Class name and apply it. A class-less node is simply named
        (this node only); a classed node's rename cascades to every scene
        instance of the Class. Synthesizes the in-memory ``mpynode_user.<Name>``
        class and stamps the canonical ``class_path``; refreshes the tags."""
        from mpynode._node_registry import wrap_node

        try:
            py_node = wrap_node(node_name, native_type)
        except Exception:
            return
        if py_node is None:
            return
        current = ""
        try:
            pc = py_node.get_py_class()
            if pc:
                current = pc.rpartition(".")[2]
        except Exception:
            current = ""
        name = self._prompt_for_class_name(py_node, default=current)
        if not name:
            return
        # A classed node -> Rename (cascade); a class-less node -> Name (self).
        self._apply_class_name(
            node_name, native_type, name, cascade=bool(current))

    def _on_reclassify_requested(
        self, node_name: str, native_type: str
    ) -> None:
        """Scene-tree "Reclassify (Fork to New Class)": prompt for a NEW Class
        name and re-stamp ONLY this instance, forking it away from the other
        instances that share its current Class (they keep the old Class)."""
        from mpynode._node_registry import wrap_node

        try:
            py_node = wrap_node(node_name, native_type)
        except Exception:
            return
        if py_node is None:
            return
        name = self._prompt_for_class_name(py_node, default="")
        if not name:
            return
        self._apply_class_name(node_name, native_type, name, cascade=False)

    def _on_convert_to_cpp_requested(self, node_name: str,
                                     native_type: str) -> None:
        """Scene-tree "Convert to C++": create a hidden compiled C++ sibling
        alongside this interpreted node and reroute its outputs, in one undo
        chunk. The Python node is KEPT as the source of truth (coexist); it is
        never deleted.

        Warns first if the node carries live stateful variables (they will NOT
        transfer -- the compiled node cold-starts). Flushes the node's editor
        tab, runs the undoable convert, refreshes the tree, re-selects the
        (retained) Python node, and surfaces any dropped connections / introduced
        cycle. Deliberately does NOT open an editor tab for the compiled node
        (its authoring lives in C++, not editable plugs)."""
        from mpynode.ui.qt_wrapper import QMessageBox
        from mpynode._base.commands import (
            build_convert_to_cpp_command, compiled_type_for, run_undoable,
        )

        if not node_name or not mc.objExists(node_name):
            self._scene_tree.refresh()
            return
        if not compiled_type_for(node_name, native_type):
            QMessageBox.information(
                self, "Convert Node to C++",
                "No compiled C++ type is loaded for this node's Class. "
                "Compile it first, then try again.")
            return
        # Inputs-only warn: a DAG transform's sibling fans off the same inputs
        # but does NOT take over the outputs -- its DAG children follow
        # PARENTAGE and there is no edge to reroute. Name what keeps reading
        # the Python node and let the user decide.
        if not self._confirm_unrewired_dependents(node_name):
            return
        # Stateful warn: live in-memory vars do NOT transfer to the compiled node.
        try:
            node = wrap_node(node_name, native_type)
            stateful = bool(node.get_variables()) if node is not None else False
        except Exception:
            stateful = False
        if stateful:
            resp = QMessageBox.warning(
                self, "Convert Node to C++",
                "'%s' has live stateful variables that will NOT transfer to the "
                "compiled node (it cold-starts). Continue?" % node_name,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if resp != QMessageBox.Yes:
                return
        # Flush the editor so just-typed authoring is committed. The Python node
        # is KEPT as the source of truth (coexist), so do NOT close its tab.
        try:
            self._script_tab_widget.saveTabsForNode(node_name)
        except Exception:
            pass
        try:
            cmd = build_convert_to_cpp_command(node_name, native_type)
            created_name = run_undoable(cmd)
        except Exception as exc:
            import sys

            sys.stderr.write(
                "[NDMainWindow] convert %r to C++ failed: %s\n"
                % (node_name, exc))
            self._scene_tree.refresh()
            return
        if created_name is None:
            created_name = getattr(cmd, "created_name", None)
        self._scene_tree.refresh()
        # Report anything the swap could not carry.
        dropped = getattr(cmd, "dropped", None) or []
        if dropped:
            QMessageBox.information(
                self, "Convert Node to C++",
                "Converted. %d connection(s) have no matching attribute on the "
                "compiled node, which declares only the attributes its compute "
                "reads.\n\nNothing was lost: the Python node keeps these "
                "connections and stays the source of truth, and reverting "
                "restores them.\n\n%s"
                % (len(dropped), _dropped_summary(dropped)))
        if getattr(cmd, "cycle_introduced", False):
            QMessageBox.warning(
                self, "Convert Node to C++",
                "The compiled node introduced a dependency cycle. Undo (Ctrl+Z) "
                "to revert if this is not intended.")
        # Coexist: convert returns the PYTHON node name -- keep it selected, it
        # is the source of truth. Direct, not evalDeferred, so this works
        # headless too.
        if created_name:
            try:
                self._scene_tree.selectNode(created_name)
            except Exception:
                pass

    _UNREWIRED_PREVIEW = 12

    def _confirm_unrewired_dependents(self, node_name: str) -> bool:
        """For a convert that duplicates INPUTS ONLY, list what keeps reading the
        interpreted node and ask whether to go ahead. Returns True to proceed.

        A no-op (True, silently) for every node type whose outputs DO get moved,
        and for an inputs-only node that has no dependents yet."""
        from mpynode.ui.qt_wrapper import QMessageBox
        from mpynode._base import node_swap

        try:
            if node_swap.moves_outputs(node_name):
                return True
            edges, children = node_swap.downstream_dependents(node_name)
        except Exception:
            return True
        if not edges and not children:
            return True
        lines = ["  %s  ->  %s" % (lp, rp) for lp, rp in edges]
        lines += ["  child:  %s" % c.split("|")[-1] for c in children]
        total = len(lines)
        shown = lines[:self._UNREWIRED_PREVIEW]
        if total > len(shown):
            shown.append("  ... and %d more" % (total - len(shown)))
        resp = QMessageBox.warning(
            self, "Convert Node to C++",
            "'%s' is a DAG transform. The compiled sibling is created beside it "
            "and fed the same inputs, but it does NOT take over the outputs: DAG "
            "children follow parentage, which cannot be rerouted onto a "
            "sibling.\n\n"
            "%d dependent(s) will keep reading the Python node:\n\n%s\n\n"
            "Convert anyway?" % (node_name, total, "\n".join(shown)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return resp == QMessageBox.Yes

    def _on_revert_to_py_requested(self, node_name: str,
                                   native_type: str) -> None:
        """Scene-tree "Revert to Python": delete this node's hidden compiled
        sibling and move its output wiring back onto the Python node, in one undo
        chunk. Surfaces any dropped connections (schema drift)."""
        from mpynode.ui.qt_wrapper import QMessageBox
        from mpynode._base.commands import (
            build_revert_to_py_command, is_converted, run_undoable)

        if not node_name or not mc.objExists(node_name):
            self._scene_tree.refresh()
            return
        if not is_converted(node_name):
            self._scene_tree.refresh()
            return
        try:
            cmd = build_revert_to_py_command(node_name, native_type)
            run_undoable(cmd)
        except Exception as exc:
            import sys

            sys.stderr.write(
                "[NDMainWindow] revert %r to Python failed: %s\n"
                % (node_name, exc))
            self._scene_tree.refresh()
            return
        self._scene_tree.refresh()
        dropped = getattr(cmd, "dropped", None) or []
        if dropped:
            QMessageBox.information(
                self, "Revert Node to Python",
                "Reverted, but %d connection(s) had no matching attribute on "
                "the Python node and were dropped:\n\n%s"
                % (len(dropped), _dropped_summary(dropped)))
        try:
            self._scene_tree.selectNode(node_name)
        except Exception:
            pass

    def _duplicate_node(
        self, node_name: str, native_type: str, with_inputs: bool
    ) -> None:
        """Shared duplicate path for the right-click + Node-menu commands.

        Runs the undoable duplicate command, refreshes the scene tree, then
        opens + selects the new node's tab (mirrors ``addNewNodeEvent``)."""
        from mpynode._base.commands import (
            build_duplicate_node_command,
            run_undoable,
        )

        if not node_name or not mc.objExists(node_name):
            self._scene_tree.refresh()
            return
        if not native_type:
            try:
                native_type = mc.nodeType(node_name)
            except Exception:
                return
        # P0: flush the source node's open editor BEFORE serializing. The code
        # editors only commit to the DG plugs on an explicit Save, so a typed-
        # but-unsaved expression (any tier) would otherwise be lost on the copy.
        try:
            self._script_tab_widget.saveTabsForNode(node_name)
        except Exception:
            pass
        try:
            cmd = build_duplicate_node_command(
                node_name, native_type, with_inputs=with_inputs
            )
            created_name = run_undoable(cmd)
        except Exception as exc:
            import sys

            sys.stderr.write(
                f"[NDMainWindow] duplicate {node_name!r} failed: {exc}\n"
            )
            return
        if created_name is None:
            created_name = getattr(cmd, "created_name", None)
        self._scene_tree.refresh()
        if not created_name:
            return
        py_node = wrap_node(created_name, native_type)
        if py_node is not None:
            self._script_tab_widget.addOrRaiseTab(py_node)
        try:
            mc.evalDeferred(lambda n=created_name: self._scene_tree.selectNode(n))
        except Exception:
            pass

    def duplicateCurrentNode(self, with_inputs: bool = False) -> None:
        """Node-menu "Duplicate" / "Duplicate + Inputs": operate on the active
        tab's node (no-op when no node is current)."""
        if self._current_node is None:
            return
        try:
            name = self._current_node.get_name()
            native_type = mc.nodeType(name)
        except Exception:
            return
        self._duplicate_node(name, native_type, with_inputs=with_inputs)

    # ------------------------------------------------------------------
    # The cascade
    # ------------------------------------------------------------------

    def _on_scene_node_selected(self, name: str, native_type: str) -> None:
        """Scene tree row clicked \u2014 raise or create the node's tab."""
        py_node = wrap_node(name, native_type)
        if py_node is None:
            return
        self._script_tab_widget.addOrRaiseTab(py_node)
        # The above raises currentChanged \u2192 _on_active_tab_changed which
        # populates the panels. No need to call setCurrentNode directly.

    def _on_active_tab_changed(self, py_node) -> None:
        """Active tab changed — populate Attributes / Storage."""
        self.setCurrentNode(py_node)

    def setCurrentNode(self, py_node) -> None:
        """Populate every panel for the given py_node (or clear if None)."""
        # track the active node so the Node menu actions
        # (Select Node, Add Attribute) know what to operate on.
        self._current_node = py_node
        self._identity_widget.setPyNode(py_node)
        self._attributes_widget.refresh(py_node)
        self._framework_widget.setPyNode(py_node)
        # Switching DOCUMENT tabs does not re-emit tierChanged (the strip did
        # not move), so read the tier off the now-current editor. Without this
        # the panel keeps the previous node's tier scope.
        self._sync_framework_tier()
        # Variables tab now displays solver-context snapshot
        # inline (Internal section). One refresh covers both the user
        # storage AND the bridge-injected internals.
        self._variables_widget.setPyNode(py_node)

        self._profile_widget.setPyNode(py_node)
        self._watch_widget.setPyNode(py_node)

    def _sync_framework_tier(self) -> None:
        """Push the visible editor's tier name into the Framework panel.

        Best-effort: during construction, or with no document open, there is no
        editor to ask and the panel keeps its default scope."""
        try:
            editor = self._script_tab_widget.currentWidget()
            tier = editor.currentTier() if editor is not None else ""
        except Exception:
            return
        if tier:
            self._framework_widget.setActiveTier(tier)

    # ------------------------------------------------------------------
    # Left-panel reveal (called from the Script tab)
    # ------------------------------------------------------------------

    def revealVariable(self, name: str) -> bool:
        """Raise the Variables tab and show the row for ``name``.

        The Script tab's API view abstracts persistent-variable DATA (a board
        of points, an animated GIF, a waveform) down to a name and a shape, so
        the value itself is only ever shown here. Returns True iff a row was
        found; the tab is raised either way, because landing on an empty
        Variables tab still answers "where would this live".
        """
        self._panel_tab_widget.setCurrentWidget(self._variables_widget)
        return self._variables_widget.revealVariable(name)

    def revealAttributes(self, which: str = "") -> bool:
        """Raise the Attributes tab, where input/output attrs are authored.

        ``which`` is "Inputs" or "Outputs" -- carried for symmetry with
        :meth:`revealVariable` and for the caller's intent to stay legible, but
        not used to scroll: the panel lists inputs and outputs together and
        both blocks are short, so raising the tab already puts the user in
        front of what they clicked.
        """
        self._panel_tab_widget.setCurrentWidget(self._attributes_widget)
        return True

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        prefs_action = QAction("Preferences…", self)
        prefs_action.triggered.connect(
            lambda checked=False: self._show_preferences_placeholder()
        )
        file_menu.addAction(prefs_action)
        # Import / Export .mpn
        file_menu.addSeparator()
        import_action = QAction("Import .mpn…", self)
        import_action.triggered.connect(lambda checked=False: self.importMpnDialog())
        file_menu.addAction(import_action)
        export_action = QAction("Export Current Node as .mpn…", self)
        export_action.triggered.connect(
            lambda checked=False: self.exportCurrentNodeAsMpn()
        )
        file_menu.addAction(export_action)
        # Bake into a standalone .py rebuild script (structure + expressions;
        # Methods become real Python). One-way -- stored DATA is not packed and
        # the Methods tab won't repopulate; use .mpn for round-trip.
        export_py_action = QAction("Bake Node to .py File…", self)
        export_py_action.triggered.connect(
            lambda checked=False: self.exportCurrentNodeAsPy()
        )
        file_menu.addAction(export_py_action)
        copy_py_action = QAction("Bake Node to Clipboard", self)
        copy_py_action.triggered.connect(
            lambda checked=False: self.copyCurrentNodeAsPy()
        )
        file_menu.addAction(copy_py_action)

        # Node menu
        node_menu = menubar.addMenu("Node")
        # Submenu: New Node ▸ -- StayOpenMenu keeps it open after a pick so
        # several nodes can be created in a row (close via click-away / Esc).
        from mpynode.ui.widgets.menus import StayOpenMenu, show_new_node_options

        # LEFT-click creates with the default new_node_mode pref; RIGHT-click
        # pops up the per-type create-mode options (vanilla/header/template).
        new_node_menu = StayOpenMenu(
            "New Node",
            node_menu,
            right_click_handler=lambda act, pos: show_new_node_options(
                new_node_menu, act, self.addNewNodeEvent, pos
            ),
        )
        from mpynode.ui.widgets.icons import get_node_type_icon

        # Pinned-first order (mPyNode, separator, then the rest) is shared
        # with the toolbar New ▾ menu via iter_new_node_menu_entries().
        for native_type in iter_new_node_menu_entries():
            if native_type is None:
                new_node_menu.addSeparator()
                continue
            spec = REGISTRY[native_type]
            act = QAction(native_type, new_node_menu)
            act.setIcon(get_node_type_icon(native_type))
            act.setToolTip(spec.description or native_type)
            # Carry the node type for the right-click options handler.
            act.setData(native_type)
            act.triggered.connect(
                lambda checked=False, nt=native_type: self.addNewNodeEvent(nt)
            )
            new_node_menu.addAction(act)
        node_menu.addMenu(new_node_menu)
        # Opens the disk-driven template gallery. Supersedes the per-type
        # right-click "From template".
        new_from_tmpl_action = QAction("New from Template…", self)
        new_from_tmpl_action.setToolTip(
            "Browse the template gallery and create a node from a template"
        )
        new_from_tmpl_action.triggered.connect(
            lambda checked=False: self._on_new_from_template()
        )
        node_menu.addAction(new_from_tmpl_action)
        node_menu.addSeparator()
        select_node_action = QAction("Select Node in Scene", self)
        select_node_action.triggered.connect(
            lambda checked=False: self.selectCurrentNodeInScene()
        )
        node_menu.addAction(select_node_action)
        add_attr_action = QAction("Add Attribute…", self)
        add_attr_action.triggered.connect(
            lambda checked=False: self.showAddAttributeDialog()
        )
        node_menu.addAction(add_attr_action)
        # Duplicate = deep copy incl. independent persistent data;
        # Duplicate + Inputs also re-wires the input connections.
        node_menu.addSeparator()
        dup_action = QAction("Duplicate", self)
        dup_action.triggered.connect(
            lambda checked=False: self.duplicateCurrentNode(with_inputs=False)
        )
        node_menu.addAction(dup_action)
        dup_inputs_action = QAction("Duplicate + Inputs", self)
        dup_inputs_action.setToolTip(
            "Duplicate the active node AND re-create its input connections"
        )
        dup_inputs_action.triggered.connect(
            lambda checked=False: self.duplicateCurrentNode(with_inputs=True)
        )
        node_menu.addAction(dup_inputs_action)
        node_menu.addSeparator()
        save_node_action = QAction("Save Node\tF5", self)
        save_node_action.triggered.connect(lambda checked=False: self.saveCurrentNode())
        node_menu.addAction(save_node_action)
        save_all_action = QAction("Save All", self)
        save_all_action.triggered.connect(lambda checked=False: self.saveAllNodes())
        node_menu.addAction(save_all_action)
        node_menu.addSeparator()
        compile_action = QAction("Compile to Native Plugin…", self)
        compile_action.triggered.connect(
            lambda checked=False: self._on_compile_toolbar()
        )
        node_menu.addAction(compile_action)

        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About Node Designer…", self)
        about_action.triggered.connect(lambda checked=False: show_about_dialog(self))
        help_menu.addAction(about_action)

        # Markdown doc viewer: "Documentation…" (docs/index.md) + a "Node Types"
        # submenu auto-listing docs/node_types/*.md. See dialogs/doc_viewer.py.
        from mpynode.ui.dialogs.doc_viewer import add_documentation_menu

        add_documentation_menu(help_menu, self)

    def _show_preferences_placeholder(self) -> None:
        """File \u2192 Preferences\u2026 \u2014 opens NDPreferencesDialog."""
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog(self)
        dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        self._toolbar = NDToolBar(
            self,
            on_new_node=self.addNewNodeEvent,
            on_save_node=self.saveCurrentNode,
            on_save_all=self.saveAllNodes,
            on_compile=self._on_compile_toolbar,
            on_new_from_template=self._on_new_from_template,
        )
        self.addToolBar(Qt.TopToolBarArea, self._toolbar)

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _install_shortcuts(self) -> None:
        # F5 → Save Current Node
        self._save_shortcut = QShortcut(QKeySequence("F5"), self)
        self._save_shortcut.setContext(Qt.WindowShortcut)
        self._save_shortcut.activated.connect(self.saveCurrentNode)

    # ------------------------------------------------------------------
    # Node creation + Save
    # ------------------------------------------------------------------

    def _new_node_command(
        self, native_type: str, mode: str | None = None,
        autoconnect: bool | None = None,
    ):
        """Pick the undoable command for creating ``native_type``, honoring the
        ``new_node_mode`` preference. Delegates to the Qt-free
        :func:`mpynode._base.commands.build_new_or_setup_command`: with
        ``autoconnect`` True a wiring type (deformer/skin/blend/IK) is created +
        attached to the live selection (seeding its template); otherwise a
        template-aware/bare create. Both paths are fail-safe.

        ``mode`` overrides the ``new_node_mode`` preference for this one create
        (used by the right-click create-mode options menu, which lets the user
        pick vanilla/header/template explicitly). A plain left-click create
        never auto-runs setup (``autoconnect`` defaults to False); the
        right-click "Create + run setup" context passes ``autoconnect`` True
        explicitly. When ``mode`` is ``None`` the pref is used (the normal
        left-click path)."""
        from mpynode._base.commands import build_new_or_setup_command

        try:
            from mpynode.ui import preferences

            if mode is None:
                mode = preferences.new_node_mode()
            if autoconnect is None:
                autoconnect = False
        except Exception:
            if mode is None:
                mode = "headers"
            if autoconnect is None:
                autoconnect = False
        return build_new_or_setup_command(
            native_type, mode, auto_setup=bool(autoconnect)
        )

    def addNewNodeEvent(
        self, native_type: str, mode: str | None = None,
        autoconnect: bool | None = None,
    ) -> None:
        """Create a new node of the given type via undoable command.

        Honors the ``new_node_mode`` preference by default. Pass an explicit
        ``mode`` (``"none"`` / ``"headers"`` / ``"template"``) and/or
        ``autoconnect`` to override it for this one create -- the right-click
        create-mode options menu sets ``mode``, and its "Create + run setup"
        context sets ``autoconnect`` True so the node is wired to the current
        selection on purpose. In ``"template"`` mode a type with a bundled
        template is seeded from it.

        After creation: the MDGMessage callback refreshes the scene tree
        AND the node's tab is added + raised in the script tab widget.
        """
        cmd = self._new_node_command(native_type, mode, autoconnect)
        try:
            created_name = run_undoable(cmd)
        except Exception as exc:
            import sys

            sys.stderr.write(
                f"[NDMainWindow] addNewNodeEvent({native_type!r}) failed: {exc}\n"
            )
            return
        # _CreateNodeCommand returns the name; _ImportNodeCommand sets it on
        # the command (doIt returns None).
        if created_name is None:
            created_name = getattr(cmd, "created_name", None)
        if not created_name:
            return
        self._post_create(created_name)

    def _post_create(self, name: str) -> None:
        """Shared post-create tail: open + raise the node's script tab and
        select it in the scene tree. Used by both addNewNodeEvent (plain New)
        and _create_from_template (the gallery). Best-effort throughout.

        ``mc.nodeType(name)`` recovers the native type so the gallery path
        (which doesn't know the type up front) can reuse this unchanged.
        """
        if not name:
            return
        # Any create lands the user back in the Workspace with the new node's
        # editor open — e.g. Create from the full-width Templates mode returns
        # here automatically.
        self._show_workspace_mode()
        # No hand-rolled type probe: wrap_node(name) IS the auto-detect,
        # and it already returns None for a node that has gone away.
        py_node = wrap_node(name)
        if py_node is not None:
            self._script_tab_widget.addOrRaiseTab(py_node)
            try:
                mc.evalDeferred(lambda n=name: self._scene_tree.selectNode(n))
            except Exception:
                pass

    def _on_new_from_template(self) -> None:
        """Switch to the full-width Templates mode and rescan so newly-added
        templates appear. (Formerly opened a modal dialog, then a side-tab.)"""
        self._show_templates_mode()
        try:
            self._gallery_panel.reload()
        except Exception:
            pass

    def _show_workspace_mode(self) -> None:
        """Switch the top-level mode switcher back to the Workspace page (0)."""
        if self._mode_tabs is None:
            return
        try:
            self._mode_tabs.setCurrentIndex(0)
        except Exception:
            pass

    def _show_templates_mode(self) -> None:
        """Switch the top-level mode switcher to the full-width Templates page
        and pop it into view."""
        if self._mode_tabs is None or self._gallery_panel is None:
            return
        try:
            idx = self._mode_tabs.indexOf(self._gallery_panel)
            if idx >= 0:
                self._mode_tabs.setCurrentIndex(idx)
            self._mode_tabs.raise_()
        except Exception:
            pass

    def _create_from_template(
        self, payload, native_type: str, run_setup: bool,
        run_demo: bool = False, demo_name=None
    ) -> None:
        """Create a node from a chosen template payload (gallery callback).

        run_demo True -> import THEN run the template's self-contained demo
        (fabricates a showcase scene, NO selection) via
        _TemplateCreateCommand(run_demo=True); wins over run_setup. demo_name
        selects which demo when the template declares several (else the first).
        run_setup True (and not run_demo) -> import THEN run the template's
        setup against the current selection in one undo step via
        _TemplateCreateCommand. Neither -> seed-only import (config + setup/demo
        code seeded, node left unwired) via
        _ImportNodeCommand(restore_persistent=False, seed_setup=True). Reuses
        _post_create's select+open-tabs tail.
        """
        from mpynode._base.commands import (
            _ImportNodeCommand,
            _TemplateCreateCommand,
            run_undoable,
        )

        if run_demo:
            cmd = _TemplateCreateCommand(
                payload, native_type, run_setup=False, run_demo=True,
                demo_name=demo_name)
        elif run_setup:
            cmd = _TemplateCreateCommand(payload, native_type, run_setup=True)
        else:
            cmd = _ImportNodeCommand(
                payload, restore_persistent=False, seed_setup=True
            )
        try:
            created_name = run_undoable(cmd)
        except Exception as exc:
            import sys

            sys.stderr.write(
                f"[NDMainWindow] _create_from_template failed: {exc}\n"
            )
            return
        if created_name is None:
            created_name = getattr(cmd, "created_name", None)
        # Surface any tier-restore / setup failures so a template that creates
        # but doesn't fully apply is not silently accepted (P0-6).
        failures = getattr(cmd, "tier_failures", None)
        if failures:
            import sys

            detail = "\n".join(
                "- %s: %s" % (k, v) for k, v in failures.items())
            sys.stderr.write(
                "[NDMainWindow] template created with issues:\n%s\n" % detail)
            try:
                from mpynode.ui.qt_wrapper import QMessageBox

                QMessageBox.warning(
                    self, "Template Created With Issues",
                    "The node was created, but some parts did not apply "
                    "cleanly:\n\n%s" % detail)
            except Exception:
                pass
        self._post_create(created_name)

    def _suspend_watch_live(self) -> None:
        """Pause the Watch live poll around a save (see NDWatchWidget.
        suspend_live): keeps timer ticks from forcing extra computes while the
        save transiently re-dirties the node. Best-effort."""
        try:
            self._watch_widget.suspend_live()
        except Exception:
            pass

    def _resume_watch_live(self) -> None:
        try:
            self._watch_widget.resume_live()
        except Exception:
            pass

    def saveCurrentNode(self) -> None:
        """F5 / toolbar Save — write the active tab's editor text to the
        node's ``_computeSource`` plug via _SetExpressionCommand (undoable).

        The Watch live poll is suspended for the duration so timer ticks
        don't force extra (and non-deterministic) computes during the save's
        transient dirty windows -- the cause of "Save fires the expression
        4-8x when the Designer is open"."""
        self._suspend_watch_live()
        try:
            self._script_tab_widget.saveCurrentTab()
        finally:
            self._resume_watch_live()

    def saveAllNodes(self) -> None:
        """Save every dirty tab (Watch live poll suspended for the duration)."""
        self._suspend_watch_live()
        try:
            self._script_tab_widget.saveAllTabs()
        finally:
            self._resume_watch_live()

    # ------------------------------------------------------------------
    #.mpn import / export
    # ------------------------------------------------------------------

    def importMpnDialog(self) -> None:
        """File → Import .mpn… — pick a file, recreate the node,
        open its tab."""
        from mpynode._base.commands import _ImportNodeCommand, run_undoable
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode.ui.qt_wrapper import QFileDialog, QMessageBox

        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Import .mpn",
            "",
            "Node Designer template (*.mpn);;All files (*)",
        )
        if not path:
            return
        # A .mpn can carry pickled stored vars; gate the (RCE-capable) pickle
        # decode behind a per-file trust prompt, exactly like a scene file.
        from mpynode._common.lifecycle import make_trust_prompt

        try:
            payload, sv_failures = load_mpn(
                path,
                return_failures=True,
                prompt_fn=make_trust_prompt(allow_always=True, subject=".mpn template"),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            return
        cmd = _ImportNodeCommand(payload)
        try:
            run_undoable(cmd)
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            return
        # Open a tab for the new node.
        new_name = cmd.created_name
        if new_name and mc.objExists(new_name):
            from mpynode._node_registry import wrap_node

            try:
                native_type = mc.nodeType(new_name)
                py_node = wrap_node(new_name, native_type)
                self._script_tab_widget.addOrRaiseTab(py_node)
            except Exception:
                pass

        # Graceful partial load: tell the user which stored vars couldn't
        # be restored (e.g. a class instance whose class isn't importable
        # here). The rest were loaded.
        if sv_failures:
            lines = "\n".join(
                f"  \u2022 {name}: {reason}" for name, reason in sv_failures.items()
            )
            QMessageBox.warning(
                self,
                "Some stored variables were skipped",
                "These stored variables couldn't be restored and were "
                "skipped (everything else loaded):\n\n" + lines,
            )

    def exportCurrentNodeAsMpn(self) -> None:
        """File → Export Current Node as .mpn… — serialize the active
        node to disk."""
        from mpynode.ui.qt_wrapper import QFileDialog, QMessageBox

        if self._current_node is None:
            QMessageBox.information(self, "Export .mpn", "No node selected to export.")
            return
        self._export_node_as_mpn(self._current_node)

    def _export_node_as_mpn(self, py_node) -> None:
        """Shared export helper used by File menu + scene-tree right-click.

        Uses the OS-native save dialog. Compression is chosen by the
        ``mpn_export_max_compression`` preference: OFF -> zlib (fast
        default), ON -> lzma (smaller file, slower).
        """
        from mpynode._common.io.mpn_io import save_mpn, serialize_node
        from mpynode.ui import preferences
        from mpynode.ui.qt_wrapper import QFileDialog, QMessageBox

        try:
            default_name = py_node.get_name() + ".mpn"
        except Exception:
            default_name = "node.mpn"
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export .mpn",
            default_name,
            "Node Designer template (*.mpn);;All files (*)",
        )
        if not path:
            return
        compression = (
            "lzma"
            if preferences.get_pref("mpn_export_max_compression", False)
            else "zlib"
        )
        # Flush the node's open editor first (same stale-plug issue as Duplicate):
        # the editors commit to the DG plugs only on Save, so serialize_node would
        # otherwise read typed-but-unsaved expressions as empty.
        try:
            self._script_tab_widget.saveTabsForNode(py_node.get_name())
        except Exception:
            pass
        try:
            payload = serialize_node(py_node)
            save_mpn(payload, path, compression=compression)
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    # ------------------------------------------------------------------
    # .py rebuild-script bake (structure + expressions; Methods become real
    # Python). One-way -- stored DATA is not packed; use .mpn for round-trip.
    # ------------------------------------------------------------------

    def exportCurrentNodeAsPy(self) -> None:
        """File → Bake Node to .py File… — write a standalone Python module
        that rebuilds the active node from scratch. One-way: Methods bake to
        real Python, the Methods tab won't repopulate."""
        from mpynode.ui.qt_wrapper import QMessageBox

        if self._current_node is None:
            QMessageBox.information(
                self, "Bake Node to .py File", "No node selected to bake."
            )
            return
        self._export_node_as_py(self._current_node)

    def _export_node_as_py(self, py_node) -> None:
        """Shared helper: write a node's rebuild script to a chosen .py file.
        Used by the File menu + the scene-tree right-click. The baked class name
        comes from the node's logical identity; an untagged node is PROMPTED for
        one first (cancelling aborts the bake)."""
        from mpynode._common.io import py_export
        from mpynode.ui.qt_wrapper import QFileDialog, QMessageBox

        class_name = py_export.resolve_bake_class_name(
            py_node, lambda: self._prompt_for_class_name(py_node)
        )
        if class_name is None:
            return  # untagged + cancelled -> abort the bake
        default_name = class_name[:1].lower() + class_name[1:] + ".py"
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Bake Node to .py File",
            default_name,
            "Python script (*.py);;All files (*)",
        )
        if not path:
            return
        try:
            src = py_export.generate_node_script(py_node, class_name=class_name)
            with open(path, "w") as f:
                f.write(src)
        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))

    def copyCurrentNodeAsPy(self) -> None:
        """File → Bake Node to Clipboard — put the baked rebuild script on the
        clipboard for pasting straight into a TA's own module. One-way:
        Methods bake to real Python, the Methods tab won't repopulate."""
        from mpynode.ui.qt_wrapper import QMessageBox

        if self._current_node is None:
            QMessageBox.information(
                self, "Bake Node to Clipboard", "No node selected to bake."
            )
            return
        self._copy_node_as_py(self._current_node)

    def _copy_node_as_py(self, py_node) -> None:
        """Shared helper: put a node's rebuild script on the clipboard.
        Used by the File menu + the scene-tree right-click. The baked class name
        comes from the node's logical identity; an untagged node is PROMPTED for
        one first (cancelling aborts the copy)."""
        from mpynode._common.io import py_export
        from mpynode.ui.qt_wrapper import QMessageBox

        class_name = py_export.resolve_bake_class_name(
            py_node, lambda: self._prompt_for_class_name(py_node)
        )
        if class_name is None:
            return  # untagged + cancelled -> abort
        try:
            src = py_export.generate_node_script(py_node, class_name=class_name)
        except Exception as exc:
            QMessageBox.warning(self, "Copy Failed", str(exc))
            return
        # qt_wrapper doesn't export QApplication (importing it perturbs Qt
        # platform init); lazy-import QGuiApplication from the bound binding --
        # ``clipboard()`` is a static accessor on both PySide2 and PySide6.
        try:
            try:
                from PySide6.QtGui import QGuiApplication
            except ImportError:
                from PySide2.QtGui import QGuiApplication

            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(src)
        except Exception as exc:
            QMessageBox.warning(self, "Copy Failed", str(exc))
            return
        try:
            self.statusBar().showMessage(
                "Baked .py script copied to clipboard.", 4000
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Node menu actions \u2014 Select Node + Add Attribute
    # ------------------------------------------------------------------

    def selectCurrentNodeInScene(self) -> None:
        """Select the active mPyNode in the Maya scene (cmds.select)."""
        if self._current_node is None:
            return
        try:
            mc.select(self._current_node.get_name(), replace=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Global middle-click -> select node in scene
    # ------------------------------------------------------------------

    def _install_global_middle_click_filter(self) -> None:
        """Install an application-wide event filter so a middle-click ANYWHERE
        in the Designer selects the relevant mPyNode in the Maya scene.

        Middle-click used to be handled per-widget (only the Scene tree and the
        editor tab bar). It is now global: one filter catches the press on any
        Designer descendant, resolves the target node -- the row/tab under the
        cursor, else the active node -- and selects it. Removed in
        :meth:`closeEvent`. An app-level filter is required because child
        widgets consume their own mouse events, so a window-level filter would
        never see them.
        """
        try:
            try:
                from PySide6.QtGui import QGuiApplication
            except Exception:
                from PySide2.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if app is not None:
                app.installEventFilter(self)
        except Exception:
            pass

    def _remove_global_middle_click_filter(self) -> None:
        """Uninstall the app-wide middle-click filter (called on close so it
        does not outlive the window)."""
        try:
            try:
                from PySide6.QtGui import QGuiApplication
            except Exception:
                from PySide2.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        """Global middle-click -> select the target mPyNode in the Maya scene.

        NON-consuming: always returns False so a widget's own middle-button
        handling (e.g. text paste) is untouched -- we only ADD the
        select-in-scene side effect. Scoped to this window's widget subtree.
        """
        try:
            if (
                event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.MiddleButton
            ):
                self._on_global_middle_click(obj, event)
        except Exception:
            pass
        return False

    def _on_global_middle_click(self, obj, event) -> None:
        # The filter is application-wide, so act only on Designer widgets.
        if not isinstance(obj, QWidget):
            return
        if obj is not self and not self.isAncestorOf(obj):
            return
        # Qt re-delivers an un-accepted middle press up the parent chain, so this
        # app-level filter fires once PER ANCESTOR. Act only on the FIRST (obj =
        # the deepest widget = the one under the cursor); a later ancestor with
        # no resolver would fall through to the active-node branch and OVERWRITE
        # the correct selection (background tab: NDEditorTabBar resolves it, then
        # NDScriptTabWidget re-fires with the active node). The dedup also
        # collapses the redundant selects into one undo entry.
        try:
            ts = event.timestamp()
        except Exception:
            ts = None
        if ts is not None and ts == self._last_middle_click_ts:
            return
        self._last_middle_click_ts = ts
        gp = _event_global_pos(event)
        name = _middle_click_node_from_widget(obj, self, gp)
        if not name and self._current_node is not None:
            try:
                name = self._current_node.get_name()
            except Exception:
                name = None
        if name:
            try:
                mc.select(name, replace=True)
            except Exception:
                pass

    def showAddAttributeDialog(self) -> None:
        """Open the persistent NDAddAttrDialog for the active mPyNode.

        Reuses the same dialog instance the right-click menus open, so
        the user can keep adding attrs across multiple invocations.
        """
        if self._current_node is None:
            return
        # Local import to avoid a top-level cycle.
        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        # If a previous dialog is still alive, just bring it back.
        try:
            if self._menu_add_attr_dlg is not None:
                self._menu_add_attr_dlg.objectName()  # throws if C++ destroyed
                self._menu_add_attr_dlg.show()
                self._menu_add_attr_dlg.raise_()
                self._menu_add_attr_dlg.activateWindow()
                return
        except (RuntimeError, AttributeError):
            self._menu_add_attr_dlg = None

        def _on_attr_added(name, attr_type, is_array, direction):
            # Refresh both attribute trees + the storage panel.
            try:
                self._attributes_widget.refresh(self._current_node)
            except Exception:
                pass

        self._menu_add_attr_dlg = NDAddAttrDialog(
            self,
            self._current_node,
            initial_direction="input",
            on_attr_added=_on_attr_added,
        )
        self._menu_add_attr_dlg.show()
        self._menu_add_attr_dlg.raise_()
        self._menu_add_attr_dlg.activateWindow()

    # ------------------------------------------------------------------
    # Maya scene callbacks (live refresh)
    # ------------------------------------------------------------------

    def _register_scene_callbacks(self) -> None:
        """Hook MDGMessage + MSceneMessage so the UI auto-refreshes."""
        try:
            import maya.api.OpenMaya as om
        except ImportError:
            return

        # Per-known-type: when a node of that type is added/removed.
        for nt in all_native_types():
            try:
                cb_id = om.MDGMessage.addNodeAddedCallback(self._on_node_added_cb, nt)
                self._scene_callback_ids.append(cb_id)
            except Exception:
                pass
            try:
                cb_id = om.MDGMessage.addNodeRemovedCallback(
                    self._on_node_removed_cb, nt
                )
                self._scene_callback_ids.append(cb_id)
            except Exception:
                pass

        # Scene-level: after-open / after-new \u2192 wipe and rebuild.
        try:
            cb_id = om.MSceneMessage.addCallback(
                om.MSceneMessage.kAfterOpen, self._on_scene_changed_cb
            )
            self._scene_callback_ids.append(cb_id)
        except Exception:
            pass
        try:
            cb_id = om.MSceneMessage.addCallback(
                om.MSceneMessage.kAfterNew, self._on_scene_changed_cb
            )
            self._scene_callback_ids.append(cb_id)
        except Exception:
            pass

    def _remove_scene_callbacks(self) -> None:
        try:
            import maya.api.OpenMaya as om
        except ImportError:
            return
        for cb_id in self._scene_callback_ids:
            try:
                om.MMessage.removeCallback(cb_id)
            except Exception:
                pass
        self._scene_callback_ids = []

    # ------------------------------------------------------------------
    # Per-node MNodeMessage callbacks (live attr updates)
    # ------------------------------------------------------------------

    def _reconcile_node_attr_callbacks(self, open_node_names) -> None:
        """Install/remove per-node attr callbacks to match the set of
        currently open tabs.

        Called by NDScriptTabWidget.tabsChanged on every tab add/remove.
        Idempotent: safe to call repeatedly with the same input.
        """
        from mpynode._base.node_callbacks import (
            install_node_attr_callback,
            install_node_connection_callback,
            remove_callback,
        )

        target_names = set(open_node_names or [])
        current_names = set(self._node_attr_callbacks.keys())

        # Drop callbacks for tabs that closed (attr + connection).
        for stale in current_names - target_names:
            remove_callback(self._node_attr_callbacks.pop(stale, None))
            remove_callback(self._node_connection_callbacks.pop(stale, None))

        # Install callbacks for tabs that just opened.
        for new_name in target_names - current_names:
            try:
                cb_id = install_node_attr_callback(new_name, self._on_node_attr_changed)
            except Exception:
                continue
            self._node_attr_callbacks[new_name] = cb_id
            # Connection-state listener (separate registry); failure to
            # install must not abort the attr-callback bookkeeping above.
            try:
                conn_id = install_node_connection_callback(
                    new_name, self._on_node_connection_changed
                )
                self._node_connection_callbacks[new_name] = conn_id
            except Exception:
                pass

    def _unregister_all_node_attr_callbacks(self) -> None:
        from mpynode._base.node_callbacks import remove_callback

        for cb_id in list(self._node_attr_callbacks.values()):
            remove_callback(cb_id)
        self._node_attr_callbacks.clear()
        for cb_id in list(self._node_connection_callbacks.values()):
            remove_callback(cb_id)
        self._node_connection_callbacks.clear()

    def _on_node_connection_changed(self, plug) -> None:
        """Maya callback (kConnectionMade / kConnectionBroken). A connection
        on this node changed -- possibly OUTSIDE the Designer (Node Editor /
        Channel Box) -- so rebuild the Attributes panel for that node to
        update the per-row connected dot. Connection events don't carry a
        usable changed-attr short name, so we refresh the whole node's
        attrs rather than routing by plug. Best-effort: never raise out of
        a Maya callback."""
        try:
            node_name = plug.name().partition(".")[0]
            if node_name:
                self._refresh_attributes_for_node(node_name)
        except Exception:
            pass

    def _on_node_attr_changed(self, plug) -> None:
        """Maya callback (kAttributeSet). Dispatch to the right panel.

        Runs on Maya's main thread (callbacks always do), so we can
        safely touch Qt widgets directly. Best-effort \u2014 every branch
        is wrapped to avoid crashing Maya from a callback.
        """
        try:
            full_name = plug.name()  # e.g. "myNode._computeSource"
            node_name, _, plug_path = full_name.partition(".")
            if not node_name or not plug_path:
                return
            # Use the LAST segment (after final '.') so vector children
            # like ``foo.translateX`` route based on ``translateX``.
            short_attr = plug_path.split(".")[-1]
        except Exception:
            return

        try:
            if short_attr == "_computeSource":
                self._refresh_editor_for_node(node_name)
            elif short_attr in ("_inputAttrs", "_outputAttrs"):
                self._refresh_attributes_for_node(node_name)
            elif short_attr in ("_storedVarsData", "_storedVarNames"):
                self._refresh_storage_for_node(node_name)
            elif short_attr == "_solverContextSnapshot":
                self._refresh_solver_context_for_node(node_name)

            elif short_attr in (
                "_profileSnapshotData",
                "profile_enabled",
                "deep_profile_enabled",
            ):
                self._refresh_profile_for_node(node_name)
            elif short_attr in ("_watchVarsData", "watch_enabled"):
                self._refresh_watch_for_node(node_name)
        except Exception:
            pass

    def _on_attr_renamed(self, node_name: str) -> None:
        """A user attr was renamed in the Attributes tab. The rename
        command already rewrote the node's stored expression sources;
        reload the open editor tab(s) so the displayed text tracks the
        new name (skips tabs with unsaved edits, per
        ``_refresh_editor_for_node``)."""
        try:
            self._refresh_editor_for_node(node_name)
        except Exception:
            pass

    def _refresh_editor_for_node(self, node_name: str) -> None:
        """Find the tab for node_name + refresh its editor (if not dirty).

        Conflict resolution: if the user has unsaved edits in this
        tab's editor, SKIP the auto-refresh \u2014 their next Save will
        overwrite. (A future iteration could surface a "Reload?" banner
        for that case.)
        """
        for i in range(self._script_tab_widget.count()):
            tab = self._script_tab_widget.widget(i)
            if not hasattr(tab, "getMPyNode"):
                continue
            py_node = tab.getMPyNode()
            try:
                if py_node is None or py_node.get_name()!= node_name:
                    continue
            except Exception:
                continue
            if hasattr(tab, "hasUnsavedChanges") and tab.hasUnsavedChanges():
                continue  # don't clobber dirty edits
            if hasattr(tab, "refresh"):
                try:
                    tab.refresh()
                except Exception:
                    pass
            return

    def _refresh_attributes_for_node(self, node_name: str) -> None:
        if self._current_node is None:
            return
        try:
            if self._current_node.get_name()!= node_name:
                return
        except Exception:
            return
        try:
            self._attributes_widget.refresh(self._current_node)
        except Exception:
            pass
        # per-attr UI colors live on the same _inputAttrs/
        # _outputAttrs JSON map. When attrs change, push the updated
        # color map into the editor's highlighter.
        try:
            for i in range(self._script_tab_widget.count()):
                tab = self._script_tab_widget.widget(i)
                if not hasattr(tab, "getMPyNode"):
                    continue
                pn = tab.getMPyNode()
                if pn is None or pn.get_name()!= node_name:
                    continue
                if hasattr(tab, "refreshVarColors"):
                    tab.refreshVarColors()
                break
        except Exception:
            pass

    def _refresh_storage_for_node(self, node_name: str) -> None:
        if self._current_node is None:
            return
        try:
            if self._current_node.get_name()!= node_name:
                return
        except Exception:
            return
        try:
            self._variables_widget.refresh()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Stored-var change listener (compute() -> Storage panel auto-refresh)
    # ------------------------------------------------------------------

    def _register_stored_var_listener(self) -> None:
        """Subscribe to the stored-var store so the Storage and Watch panels
        auto-refresh when a node's stored vars change -- whether a compute()
        rewrote them (e.g. re-pointing an audio path recomputes a persistent
        buffer) or a script did via ``MPyNode.set_variable``. Unlike
        ``_storedVarsData`` plug callbacks -- which never fire in a session
        because the plug is kept empty until save -- this fires from the
        in-memory store's write paths: ``set_for_compute`` plus the name-based
        ``set_var`` / ``set_data`` / ``remove_var``."""
        try:
            from mpynode._common.storedvars import stored_var_store as _svstore
        except Exception:
            return
        self._stored_vars_listener = self._on_stored_vars_changed
        try:
            _svstore.add_change_listener(self._stored_vars_listener)
        except Exception:
            self._stored_vars_listener = None

    def _on_stored_vars_changed(self, node_hash) -> None:
        """Stored-var store listener. Runs on the EM WORKER THREAD with the
        changed node's thread-safe hash, so it must NOT touch the DG / Qt here.
        Record the hash and (coalesced) marshal a Storage refresh to the main
        thread via ``maya.utils.executeDeferred`` (safe to call cross-thread),
        where resolving the active node's identity + re-reading the store is
        safe."""
        try:
            with self._stored_vars_lock:
                self._stored_vars_changed_hashes.add(node_hash)
                if self._stored_vars_refresh_pending:
                    return
                self._stored_vars_refresh_pending = True
        except Exception:
            return
        try:
            import maya.utils as _mu

            _mu.executeDeferred(self._drain_stored_var_changes)
        except Exception:
            # No deferral available (headless): drop the latch so a later
            # change can still schedule. No UI is up to refresh anyway.
            with self._stored_vars_lock:
                self._stored_vars_refresh_pending = False

    def _drain_stored_var_changes(self) -> None:
        """Main-thread tail of the stored-var listener: if the ACTIVE node is
        among those whose stored vars changed, refresh the Storage panel. That
        refresh re-reads the in-memory store only (no output-plug read), so it
        cannot trigger a re-entrant compute the way the Watch refresh could."""
        try:
            with self._stored_vars_lock:
                changed = self._stored_vars_changed_hashes
                self._stored_vars_changed_hashes = set()
                self._stored_vars_refresh_pending = False
        except Exception:
            return
        if not changed or self._current_node is None:
            return
        try:
            if not self.isVisible():
                return
        except Exception:
            pass
        try:
            from mpynode._common.storedvars import stored_var_store as _svstore

            cur = _svstore._hash_for_name(self._current_node.get_name())
        except Exception:
            cur = None
        if cur is None or cur not in changed:
            return
        try:
            self._variables_widget.refresh()
        except Exception:
            pass
        # Watch renders the SAME stored vars from its own snapshot, so a change
        # that refreshed only Storage left the two panels disagreeing until
        # Watch happened to rebuild for another reason. Store-only refresh --
        # the full one reads output plugs and could re-enter compute, which is
        # why this widget was skipped here before.
        try:
            self._watch_widget.refresh_stored_only()
        except Exception:
            pass

    def _refresh_solver_context_for_node(self, node_name: str) -> None:
        """Solver-context snapshot now renders inside the
        Storage tab's Internal section. When the snapshot plug changes,
        refresh the Storage panel — the dedicated Solver Context tab is
        gone."""
        if self._current_node is None:
            return
        try:
            if self._current_node.get_name()!= node_name:
                return
        except Exception:
            return
        try:
            self._variables_widget.refresh()
        except Exception:
            pass

    def _refresh_profile_for_node(self, node_name: str) -> None:
        """Refresh the Profile panel when the snapshot or
        toggle plug changes for the active node."""
        if self._current_node is None:
            return
        try:
            if self._current_node.get_name()!= node_name:
                return
        except Exception:
            return
        try:
            self._profile_widget.refresh()
        except Exception:
            pass

    def _refresh_watch_for_node(self, node_name: str) -> None:
        """Refresh the Watch panel when the snapshot or
        toggle plug changes for the active node.

        DEFERRED: the _watchVarsData change that triggers this fires from
        a cmds.setAttr INSIDE the node's compute(). Refreshing synchronously
        would re-read the output plugs (forcing a re-entrant compute) -- a
        feedback loop that froze Maya. evalDeferred runs it after compute
        unwinds; the Watch's re-entrancy guard is the backstop."""
        if self._current_node is None:
            return
        try:
            if self._current_node.get_name()!= node_name:
                return
        except Exception:
            return

        def _do():
            try:
                self._watch_widget.refresh()
            except Exception:
                pass

        try:
            mc.evalDeferred(_do)
        except Exception:
            _do()

    # Callback signatures match what Maya expects (variadic args).
    def _on_node_added_cb(self, *_args, **_kwargs) -> None:
        # Refresh on next event-loop tick to let Maya finish the add op.
        try:
            mc.evalDeferred(self._scene_tree.refresh)
        except Exception:
            self._scene_tree.refresh()

    def _on_node_removed_cb(self, mobject, *_args, **_kwargs) -> None:
        # Capture the name BEFORE the node is fully removed so we can
        # close the matching tab.
        removed_name = ""
        try:
            import maya.api.OpenMaya as om

            removed_name = om.MFnDependencyNode(mobject).name()
        except Exception:
            pass

        def _do_close_and_refresh():
            if removed_name:
                self._script_tab_widget.closeTabForNode(removed_name)
            self._scene_tree.refresh()

        try:
            mc.evalDeferred(_do_close_and_refresh)
        except Exception:
            _do_close_and_refresh()

    def _on_scene_changed_cb(self, *_args, **_kwargs) -> None:
        # New / opened scene \u2014 close all tabs and rebuild the tree.
        try:
            mc.evalDeferred(self._handle_scene_change)
        except Exception:
            self._handle_scene_change()

    def _handle_scene_change(self) -> None:
        # Route through closeAllTabs() (not a raw removeTab loop) so tabsChanged
        # fires -> per-node attr callbacks are reconciled to empty. A scene swap
        # replaces every node, so every tab is a stale document view whatever
        # its node is named -- leaving one behind is the "ghost tab" bug.
        self._script_tab_widget.closeAllTabs()
        self.setCurrentNode(None)
        self._scene_tree.refresh()

    def _handle_reopen(self) -> None:
        """refresh stale state when the window is
        re-shown after being closed.

        Background: when the user clicks the X button, ``closeEvent``
        tears down all scene + per-node attribute callbacks but the
        widget itself stays alive in Maya's main-window child list (so
        that ``show_designer()``'s findChild path can re-raise it). If
        the user then changes the Maya scene (file new, file open) WHILE
        the window is hidden, no callbacks fire — our internal state
        (open tabs, current node, scene tree) goes stale.

        This handler is invoked by ``show_designer()`` whenever an
        EXISTING instance is being re-shown. It:
          1. Re-registers the scene + per-node attribute callbacks if
             they were torn down.
          2. Closes any tab whose backing node no longer exists.
          3. Clears ``_current_node`` (and its panel content) if that
             node is gone.
          4. Re-queries the Maya scene to rebuild the Scene tree.
        """
        # 1. Re-register scene callbacks if torn down.
        if not self._scene_callback_ids:
            try:
                self._register_scene_callbacks()
            except Exception:
                pass
        # closeEvent also drops the stored-var listener; without re-subscribing,
        # the Storage panel stops auto-refreshing for the rest of the session.
        if self._stored_vars_listener is None:
            try:
                self._register_stored_var_listener()
            except Exception:
                pass
        # closeEvent removes the app-wide middle-click filter, but the X-button
        # keeps this widget alive (singleton reopen), so a reopen must restore
        # the filter or middle-click-to-select dies for the rest of the session.
        # Idempotent: Qt de-dupes re-installing the same filter object.
        self._install_global_middle_click_filter()

        # 2. Close tabs whose backing node was destroyed while hidden. Uses each
        #    tab's MObjectHandle (pruneStaleTabs), NOT objExists(name): a fresh
        #    scene can hold a DIFFERENT node with the same name, which the name
        #    check mistook for the original and left as a ghost tab.
        try:
            self._script_tab_widget.pruneStaleTabs()
        except Exception:
            pass

        # 3. Clear current node if it's gone.
        if self._current_node is not None:
            try:
                cur_name = self._current_node.get_name()
            except Exception:
                cur_name = None
            if not cur_name or not mc.objExists(cur_name):
                try:
                    self.setCurrentNode(None)
                except Exception:
                    pass

        # 4. Re-reconcile per-node MNodeMessage callbacks against the
        #    surviving open tabs (some may have just been closed).
        try:
            open_names = self._script_tab_widget.getOpenNodeNames()
        except Exception:
            open_names = []
        try:
            self._reconcile_node_attr_callbacks(open_names)
        except Exception:
            pass

        # 5. Always refresh the Scene tree: the user must see the current
        #    scene's nodes, not the snapshot from when the window closed.
        try:
            self._scene_tree.refresh()
        except Exception:
            pass

        # 6. If step 2 pruned EVERY tab (scene swap while hidden) and the fresh
        #    scene has mPy* nodes, auto-select the first, as at launch. The
        #    helper bails out if any tab survived, so a reopen on the same
        #    scene keeps its prior tabs.
        try:
            self._auto_select_first_node()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Qt close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        # Turn off ALL instrumentation toggles scene-wide so closing the UI
        # leaves no background profile/watch DG work running. They are
        # storable=False, so this only zeroes the still-loaded session's cost.
        try:
            from mpynode._common.instrumentation import (
                disable_all_instrumentation_toggles_in_scene,
            )

            disable_all_instrumentation_toggles_in_scene()
        except Exception:
            # Never block close on a scrub error.
            pass
        # Drop the app-wide middle-click filter so it doesn't outlive the window.
        self._remove_global_middle_click_filter()
        self._remove_scene_callbacks()
        self._unregister_all_node_attr_callbacks()
        # Drop the stored-var store listener, else it outlives the window.
        if self._stored_vars_listener is not None:
            try:
                from mpynode._common.storedvars import stored_var_store as _svstore

                _svstore.remove_change_listener(self._stored_vars_listener)
            except Exception:
                pass
            self._stored_vars_listener = None
        # Persist the layout for the next Maya session. Saved ONLY here, not on
        # every drag, to avoid thrashing the JSON file. Never blocks close.
        try:
            from mpynode.ui.preferences import set_pref

            set_pref("layout_main_splitter", list(self._main_splitter.sizes()))
            set_pref("layout_right_splitter", list(self._right_split.sizes()))
            set_pref("layout_mode_tab", int(self._mode_tabs.currentIndex()))
            geo = self.geometry()
            set_pref(
                "layout_window_geometry",
                [geo.x(), geo.y(), geo.width(), geo.height()],
            )
        except Exception:
            pass
        # Gallery owns its own two splitters (tree|preview and preview|desc);
        # let it persist them the same way (own try so it can't skip the above).
        try:
            self._gallery_panel.save_layout()
        except Exception:
            pass
        super().closeEvent(event)


# ===========================================================================
# Module-level singleton + convenience launcher
# ===========================================================================

_designer_instance: NDMainWindow | None = None


def show_designer() -> NDMainWindow:
    """Launch (or raise) the Node Designer window. See README for details.

    bulletproof singleton: looks up any existing instance via
    ``QMainWindow.findChild(QMainWindow, NDMainWindow.WINDOW_OBJECT_NAME)``
    on the Maya main window, NOT just the module-level cache. This catches:
      * stale cache after window closed (X button)
      * direct ``NDMainWindow()`` construction bypass
      * module reload (cache reset to None)
      * any other path that could leave a live widget the cache doesn't know about

    If an existing window is found, just raise + return it (no re-init,
    no second window).
    """
    global _designer_instance

    parent = maya_main_window()

    # Source of truth: walk Maya's main window children for one named
    # NDMainWindow.WINDOW_OBJECT_NAME. Always preferred over the cache.
    if parent is not None:
        try:
            existing = parent.findChild(QMainWindow, NDMainWindow.WINDOW_OBJECT_NAME)
        except Exception:
            existing = None
        if existing is not None:
            try:
                _designer_instance = existing
                existing.show()
                existing.raise_()
                existing.activateWindow()
                # A re-shown widget may be stale: the scene can change while
                # the window is hidden, with all callbacks torn down.
                if hasattr(existing, "_handle_reopen"):
                    try:
                        existing._handle_reopen()
                    except Exception:
                        pass
                return existing
            except (RuntimeError, AttributeError):
                # Underlying Qt object died between findChild and call.
                # Fall through to fresh-construction path.
                _designer_instance = None

    # No live instance found anywhere — construct, cache, show.
    _designer_instance = NDMainWindow(parent=parent)
    _designer_instance.show()
    _designer_instance.raise_()
    _designer_instance.activateWindow()
    return _designer_instance
