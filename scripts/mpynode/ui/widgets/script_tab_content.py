"""NDScriptTabContent — the Script area's single tab strip.

ONE strip, whose segments are everything this node has:

    Init | Compute | [Viewport] | [OSL] | API

The tiers come first in runtime order (Init runs once, Compute per dirty cycle,
Viewport in VP2), then the API view. Both the half-width [Expressions | Script]
selector and the Methods segment are GONE.

"API" is the node as ``File > Bake Node to .py`` would emit it: expression
bodies folded, generated lines marked, and the Methods source EDITABLE in place
— see :mod:`mpynode.ui.widgets.api_view`. That is where the Methods pane went.
It rendered methods and free functions flat at column 0, so nothing on screen
distinguished a class member from a module function; here they sit indented
inside ``class X:`` exactly where they bake.

SELECTION IS ONE KEY, WITH TWO RENDERERS
:meth:`select` is the only navigation implementation. The tab strip, the
navigator table and the API view's managed zones all call it, so there is no
"now also update the other widget" line to forget — which is precisely the line
that, missing, left the navigator pointing elsewhere whenever a tab was clicked.

Implements the existing tab-widget contract used by
NDScriptTabWidget (getMPyNode / getText / setText /
hasUnsavedChanges / markSaved / refresh / dirtyStateChanged signal)
by delegating to the COMPUTE editor (still backed by the ``_computeSource``
plug for save / load). The Init editor participates in the dirty/save
flow via markSaved() (which also persists the init source) and
hasUnsavedChanges (True if any editor is dirty). The Viewport editor
follows the same pattern for nodes that opt in via
``set_viewport_expression``.

Which TIER segments appear is decided by ``hasattr`` on the wrapper, so the
strip states what this node can actually do. For wrappers with no
``set_init_expression`` (legacy / non-JIT-capable types) Compute is the only
tier. For wrappers with no ``set_viewport_expression`` (every node except
mPyFile in v1.0) there is no Viewport segment. API always appears; whether it
has any EDITABLE region depends on the wrapper exposing ``set_methods_source``.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import (
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    Qt,
    Signal,
)
from mpynode.ui.widgets.api_view import NDApiView
from mpynode.ui.widgets.script_navigator import NDScriptNavigator
from mpynode.ui.widgets.init_editor import NDInitEditor
from mpynode.ui.widgets.osl_activity_strip import NDOslActivityStrip
from mpynode.ui.widgets.osl_editor import NDOslEditor
from mpynode.ui.widgets.viewport_editor import NDViewportEditor
from mpynode.ui.widgets.script_editor import NDScriptEditor
from mpynode.ui.widgets.tall_tab_bar import make_tabs_uniform


# Stylesheets for the Script tab's own strip ONLY, applied per-instance to
# self._inner_tabs' bar and never to the shared tab-bar class. Each emphasises
# the SELECTED tab differently; the user picks one in Preferences. All colours
# are Maya palette(...) roles so they track the active theme. Keys MUST match
# preferences.VALID_SCRIPT_TAB_STYLES (a test enforces parity).
#
# The name is historical: these dressed the deleted [Expressions | Script]
# selector. They now dress the single [Init | Compute | ... | Methods | API]
# strip that replaced it, and the pref key is unchanged, so a user's saved
# choice still applies.

# underline (default, shipped): base fill + bold + 3px highlight underline.
_TAB_STYLE_UNDERLINE = """
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    padding: 5px 14px;
    border: 0px;
    border-bottom: 3px solid transparent;
    background: palette(window);
    color: palette(mid);
}
QTabBar::tab:hover:!selected { color: palette(text); }
QTabBar::tab:selected {
    background: palette(base);
    color: palette(text);
    font-weight: bold;
    border-bottom: 3px solid palette(highlight);
}
"""

# gray: inactive recedes to a dim grey; selected brightens + bold, no accent.
_TAB_STYLE_GRAY = """
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    padding: 6px 14px;
    border: 0px;
    background: palette(dark);
    color: palette(mid);
}
QTabBar::tab:hover:!selected { color: palette(text); }
QTabBar::tab:selected {
    background: palette(window);
    color: palette(text);
    font-weight: bold;
}
"""

# top_accent: same idea as underline but the accent sits on the TOP edge.
_TAB_STYLE_TOP_ACCENT = """
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    padding: 5px 14px;
    border: 0px;
    border-top: 3px solid transparent;
    background: palette(window);
    color: palette(mid);
}
QTabBar::tab:hover:!selected { color: palette(text); }
QTabBar::tab:selected {
    background: palette(base);
    color: palette(text);
    font-weight: bold;
    border-top: 3px solid palette(highlight);
}
"""

# fill: selected tab filled with the theme highlight colour.
_TAB_STYLE_FILL = """
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    padding: 6px 14px;
    border: 0px;
    background: palette(window);
    color: palette(mid);
}
QTabBar::tab:hover:!selected { color: palette(text); }
QTabBar::tab:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
    font-weight: bold;
}
"""

# classic: the ORIGINAL solid dark fill, kept selectable for comparison.
_TAB_STYLE_CLASSIC = """
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    padding: 6px 14px;
    border-right: 1px solid palette(dark);
    background: palette(button);
    color: palette(text);
}
QTabBar::tab:selected {
    background: #000000;
    color: #ffffff;
}
"""

# boxed (default, shipped): each tab is a discrete cell -- 1px border on every
# side and a 2px gap -- so the strip reads as five tabs rather than one band.
# Every other style here draws the tabs borderless on a shared background,
# which emphasises the SELECTED tab well but leaves the inactive ones fused
# into a single dark strip. The selected tab keeps the highlight fill, so
# "you are here" stays as loud as it is under `fill`.
_TAB_STYLE_BOXED = """
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab {
    padding: 6px 14px;
    margin-right: 2px;
    border: 1px solid palette(dark);
    background: palette(button);
    color: palette(text);
}
QTabBar::tab:hover:!selected { background: palette(midlight); }
QTabBar::tab:selected {
    background: palette(highlight);
    color: palette(highlighted-text);
    font-weight: bold;
    border: 1px solid palette(shadow);
}
"""

_OUTER_BAR_STYLES = {
    "underline":  _TAB_STYLE_UNDERLINE,
    "gray":       _TAB_STYLE_GRAY,
    "top_accent": _TAB_STYLE_TOP_ACCENT,
    "fill":       _TAB_STYLE_FILL,
    "classic":    _TAB_STYLE_CLASSIC,
    "boxed":      _TAB_STYLE_BOXED,
}


class NDScriptTabContent(QWidget):
    """Per-node container — main expression + (optional) JIT sister."""

    dirtyStateChanged = Signal(bool)
    # Forwarded up from the OSL editor when conversion hits a hard limit;
    # carries a compile_bridge hand-off dict for the assistant panel.
    handoffToAssistant = Signal(object)
    # Forwarded up from the API view when a persistent-variable declaration is
    # clicked; carries the variable name for the designer to reveal on the
    # left-hand Variables tab, where the DATA lives.
    revealVariableRequested = Signal(str)
    # Forwarded up from the API view when a generated attribute block is
    # clicked; carries "Inputs" / "Outputs" for the designer to raise the
    # left-hand Attributes tab, where those attrs are actually authored.
    revealAttributesRequested = Signal(str)
    # The active tier's NAME ("Init" / "Compute" / "Viewport" / "OSL" / "API"),
    # emitted whenever the strip changes. The Framework panel lists only the
    # surface the active tier can actually reach -- the expression tiers get a
    # SelfProxy, the API tab gets the wrapper -- so it has to be told which one
    # is on screen. Emitted for PROGRAMMATIC switches too (unlike the shared-
    # tier write below): the panel must track what is visible, not who caused it.
    tierChanged = Signal(str)

    # The tier tab shown across ALL node editors. Class-level, so switching
    # document tabs keeps the SAME tier visible instead of each node
    # remembering its own (which made jumping between nodes disorienting).
    # Synced by NAME, not index, because tab sets differ per node type; a node
    # lacking the shared tier falls back to Compute, which is always present.
    _shared_tier = "Compute"

    # Nodes this session has already shown an editor for. A node being opened
    # for the FIRST time lands on Compute regardless of the shared tier: that
    # is the tier you almost always want when meeting a node, and inheriting
    # (say) API from whatever you were last doing on a different node makes a
    # freshly opened node look empty and broken -- which is exactly how a
    # converted v1 node presented itself.
    #
    # Session-scoped, and reopening a closed tab counts as already-seen: if
    # you deliberately closed an API tab and reopened it, snapping to Compute
    # would fight you. Keyed off the node UUID, so a rename does not read as
    # a new node -- see _node_key for why not the MObjectHandle hash.
    _seen_nodes = set()

    def __init__(self, py_node, parent=None):
        super().__init__(parent)
        self._py_node = py_node

        # NAME-INDEPENDENT handle to the backing Maya node, used by
        # NDScriptTabWidget.pruneStaleTabs to close tabs whose node a
        # File>New / File>Open destroyed. A NAME check is fooled by a
        # same-named replacement node and leaves a "ghost" tab; an
        # MObjectHandle tracks the exact object and goes invalid with it.
        # None when unresolvable -- isBackingNodeAlive() then reports
        # "unknown" so a tab is never pruned on a guess.
        self._node_handle = self._resolve_node_handle(py_node)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._inner_tabs = QTabWidget(self)
        # Taller inner tier tabs, to match the other horizontal tab strips, and
        # all the same WIDTH: Init | Compute | Viewport | OSL | API otherwise
        # renders as five ragged buttons. Install BEFORE the addTab calls below
        # -- setTabBar wipes existing tabs -- and keep the ref, or PySide GC
        # drops the tabSizeHint override.
        self._inner_tab_bar = make_tabs_uniform(self._inner_tabs)

        # ONE strip, no [Expressions | Script] switch above it. The tiers, the
        # Methods module and the baked API view are peers: they are the things
        # you alternate between, and a single bar is the clearest statement of
        # WHERE YOU ARE. The old outer QTabBar/QStackedWidget pair is gone --
        # its two states were "the tier editors" and "the Methods pane", both of
        # which are now segments here.
        #
        # The emphasis style still comes from the script_tab_style pref; it just
        # dresses this strip instead of the deleted one. Applied per-instance,
        # never to the shared tab-bar class other strips reuse, and re-applied
        # live on pref change (_wire_pref_listener).
        self._apply_tab_style()
        self._wire_pref_listener()

        # The strip and its editor on the left, the navigator on the right.
        # A splitter, not a fixed column, because the navigator holds LABELS --
        # its width is set by the longest symbol name, not by 87 columns of
        # code -- and on a narrow window the user can rail it away to give the
        # editor every pixel.
        self._nav_split = QSplitter(Qt.Horizontal, self)
        self._nav_split.addWidget(self._inner_tabs)
        # Built empty; populated from the API view's bake once that exists, so
        # opening a node bakes it once rather than once per surface.
        self._navigator = NDScriptNavigator(parent=self._nav_split)
        self._nav_split.addWidget(self._navigator)
        self._nav_split.setStretchFactor(0, 1)
        self._nav_split.setStretchFactor(1, 0)
        self._nav_split.setCollapsible(0, False)  # the code never disappears
        self._nav_split.setCollapsible(1, True)   # the navigator may
        # J3's budget: 236 preferred, 208 floor. It had to be cut to 180 while
        # the strip still carried a Methods segment -- at the shipped 580px
        # centre pane, mPyFile's SIX segments needed 393px and a wider
        # navigator made the strip elide its own labels. Deleting that segment
        # is what bought the width back. The navigator holds labels and can
        # elide; the strip is the where-am-I widget and cannot, so the strip
        # still wins any tie. Pinned by
        # test_script_area_wiring.test_widest_strip_still_fits_without_scrolling
        self._navigator.setMinimumWidth(208)
        # Outline starts COLLAPSED: it is a jump-to aid, not something to
        # read continuously, and at rest it was taking a fifth of the code
        # width. Drag the handle (or widen the pane) to bring it back --
        # setCollapsible(1, True) above is what makes 0 mean collapsed
        # rather than clamped to the 208 minimum.
        self._nav_split.setSizes([816, 0])
        layout.addWidget(self._nav_split, 1)

        self._navigator.selectRequested.connect(self.select)
        self._navigator.variableActivated.connect(
            self.revealVariableRequested)
        self._navigator.runRequested.connect(self._on_run_requested)
        self._navigator.insertTemplateRequested.connect(
            self._on_insert_template)

        # The API view is built LAST, so initialise its handle FIRST: an inner
        # editor can emit dirtyStateChanged during its own construction, and
        # the dirty/save/refresh aggregates must already be safe.
        self._api_view              = None
        self._output_builder_editor = None  # back-compat aggregate hook

        # Guard so a PROGRAMMATIC tier switch isn't mistaken for a user click
        # and doesn't clobber the shared choice.
        self._applying_shared_tier = False

        # Only for wrappers exposing set_init_expression. FIRST in the strip:
        # Init runs once per file open, before the per-frame Compute work.
        self._init_editor = None
        if hasattr(py_node, "set_init_expression"):
            self._init_editor = NDInitEditor(py_node, parent=self._inner_tabs)
            self._inner_tabs.addTab(self._init_editor, "Init")
            self._init_editor.dirtyStateChanged.connect(self._on_inner_dirty_changed)

        # Always present. SECOND, so left-to-right matches the runtime order:
        # Init (once) -> Compute (per dirty cycle) -> Viewport (VP2).
        self._expr_editor = NDScriptEditor(py_node, parent=self._inner_tabs)
        self._inner_tabs.addTab(self._expr_editor, "Compute")

        # Only for wrappers exposing set_viewport_expression (e.g. mPyFile).
        # Runs in parallel with Compute for VP2 shader-class nodes.
        self._viewport_editor = None
        if hasattr(py_node, "set_viewport_expression"):
            self._viewport_editor = NDViewportEditor(
                py_node, parent=self._inner_tabs
            )
            self._inner_tabs.addTab(self._viewport_editor, "Viewport")
            self._viewport_editor.dirtyStateChanged.connect(
                self._on_inner_dirty_changed
            )

        # Only for wrappers exposing set_osl_expression. LAST, because it is
        # not an execution tier but a renderer-target string output (the
        # node's connectable .osl).
        self._osl_editor = None
        if hasattr(py_node, "set_osl_expression"):
            self._osl_editor = NDOslEditor(py_node, parent=self._inner_tabs)
            self._osl_editor.dirtyStateChanged.connect(
                self._on_inner_dirty_changed
            )
            # Host the editor under a "Translate Compute -> OSL" action: the
            # deterministic converter, falling back to the AI assistant on
            # unsupported look-math. self._osl_editor stays the editor object,
            # so the dirty/save/refresh aggregate is unchanged.
            osl_tab = self._osl_editor
            if hasattr(py_node, "convert_compute_to_osl"):
                osl_tab    = QWidget(self._inner_tabs)
                osl_layout = QVBoxLayout(osl_tab)
                osl_layout.setContentsMargins(0, 0, 0, 0)
                osl_layout.setSpacing(2)
                self._osl_convert_btn = QPushButton(
                    "Translate Compute → OSL", osl_tab
                )
                self._osl_convert_btn.setToolTip(
                    "Transpile this node's Compute look-math into OSL. Falls back "
                    "to the AI assistant automatically for look-math the "
                    "deterministic converter can't handle."
                )
                self._osl_convert_btn.clicked.connect(
                    self._on_osl_translate_clicked
                )
                # Disable + relabel while the AI fallback runs on its worker
                # thread, so a second translation can't be launched.
                self._osl_editor.convertBusyChanged.connect(
                    self._on_osl_convert_busy
                )
                # Spinner + timer + streamed feed + Stop + inline error, driven
                # by the editor's convert signals. Hidden until a translation
                # runs or a failure needs reporting.
                self._osl_activity = NDOslActivityStrip(osl_tab)
                self._osl_activity.stopRequested.connect(self._osl_editor.cancel)
                self._osl_editor.convertProgress.connect(
                    self._on_osl_convert_progress
                )
                self._osl_editor.convertSucceeded.connect(
                    self._on_osl_convert_ok
                )
                self._osl_editor.convertFailed.connect(
                    self._on_osl_convert_failed
                )
                self._osl_editor.convertCancelled.connect(
                    self._on_osl_convert_cancelled
                )
                # Forward a hand-off up, so a hard "can't convert" becomes an
                # assistant conversation.
                self._osl_editor.handoffToAssistant.connect(
                    self.handoffToAssistant
                )
                osl_layout.addWidget(self._osl_convert_btn)
                osl_layout.addWidget(self._osl_activity)
                osl_layout.addWidget(self._osl_editor)
            self._inner_tabs.addTab(osl_tab, "OSL")

        # There is NO Methods segment. It showed your methods and free functions
        # flat at column 0 -- the one thing Python uses to express scope was
        # missing, so a method and a module function looked identical. They are
        # edited in the API view now, indented inside ``class X:`` where they
        # really land, and reached from the navigator's MODULE / member rows.
        # Its outline duplicated the navigator; its Run and its command
        # templates moved there.

        # LAST: the node as ``File > Bake Node to .py`` would emit it, with the
        # expression bodies folded and every generated line marked. Editable in
        # the Methods regions, refused everywhere else.
        self._api_view = NDApiView(py_node, parent=self._inner_tabs)
        self._inner_tabs.addTab(self._api_view, "API")
        # Right-click > "Go to <tier>" raises that tab. A LEFT click does not:
        # it used to, and was retracted -- the tier is already on screen where
        # you clicked, so being thrown to another tab cost the place you were
        # reading. The navigator highlight (regionActivated, below) answers
        # the click; the menu answers "take me there".
        self._api_view.tierActivated.connect(
            lambda label: self.select("tier.%s" % str(label).lower()))
        self._api_view.variableActivated.connect(self.revealVariableRequested)
        self._api_view.attributesActivated.connect(
            self.revealAttributesRequested)
        self._api_view.dirtyStateChanged.connect(self._on_inner_dirty_changed)
        self._api_view.regionActivated.connect(self._on_region_activated)
        self._navigator.setPyNode(py_node, self._api_view.regions())
        # AFTER the last addTab: an empty QTabBar has no meaningful height, so
        # asking earlier would align the navigator to nothing.
        self._navigator.setTitleHeight(
            self._inner_tabs.tabBar().sizeHint().height())

        # The Output Builder tab is GONE: geometry generators now write their
        # output straight from Compute via the ``build_default_output``
        # marshaller auto-seeded into Init. One tab, one execution path, no
        # preview-vs-live drift. ``self._output_builder_editor`` stays None as
        # a back-compat aggregate hook.

        self._expr_editor.dirtyStateChanged.connect(self._on_inner_dirty_changed)

        # Before connecting the listener, so this initial programmatic set
        # doesn't feed back. After it, a tier click updates every node.
        self._apply_shared_tier()
        self._inner_tabs.currentChanged.connect(self._on_inner_tab_changed)

    # ------------------------------------------------------------------
    # Tab-widget contract (delegated to expression editor for
    # backwards compatibility with NDScriptTabWidget save logic)
    # ------------------------------------------------------------------

    def getMPyNode(self):
        return self._py_node

    # -- selected-tab emphasis style (pref-driven, live) ------------------

    def _apply_tab_style(self) -> None:
        """Apply the user's chosen emphasis stylesheet to the Expressions/Script
        selector. Reads ``preferences.script_tab_style()`` (validated to a known
        key) and falls back to the shipped ``underline`` look if anything is off
        (e.g. preferences module unavailable headless)."""
        style = _OUTER_BAR_STYLES["underline"]
        try:
            from mpynode.ui import preferences

            style = _OUTER_BAR_STYLES.get(
                preferences.script_tab_style(), _OUTER_BAR_STYLES["underline"])
        except Exception:
            pass
        self._inner_tab_bar.setStyleSheet(style)

    def _wire_pref_listener(self) -> None:
        """Subscribe to live pref changes so switching the tab style in
        Preferences re-styles open editors with no restart. Best-effort."""
        try:
            from mpynode.ui.preferences import register_change_listener

            register_change_listener(self._on_pref_changed)
        except Exception:
            pass

    def _on_pref_changed(self, key, value) -> None:
        """Re-apply the tab style when ``script_tab_style`` changes. Self-
        unregisters if the C++ side has been deleted (the codebase's standard
        listener-lifecycle pattern -- no closeEvent hook)."""
        if key != "script_tab_style":
            return
        try:
            self._apply_tab_style()
        except RuntimeError:
            try:
                from mpynode.ui.preferences import unregister_change_listener

                unregister_change_listener(self._on_pref_changed)
            except Exception:
                pass

    @staticmethod
    def _resolve_node_handle(py_node):
        """Return an ``MObjectHandle`` for ``py_node``'s Maya node, or None if it
        can't be resolved (headless edge / node already gone / no api2)."""
        try:
            import maya.api.OpenMaya as om

            name = py_node.get_name()
            if not name:
                return None
            sel = om.MSelectionList()
            sel.add(name)
            return om.MObjectHandle(sel.getDependNode(0))
        except Exception:
            return None

    def isBackingNodeAlive(self):
        """Tri-state liveness of the backing Maya node:

          * ``True``  -- the node still exists in the scene,
          * ``False`` -- the node was definitively removed (its MObject is no
            longer valid, e.g. after a File>New / File>Open),
          * ``None``  -- unknown (no handle was captured); callers MUST NOT
            prune a tab on ``None``.

        Decided from the ``MObjectHandle`` captured at construction, so a
        same-named node in a freshly opened scene never masquerades as this
        tab's node.
        """
        handle = self._node_handle
        if handle is None:
            return None
        try:
            return bool(handle.isValid() and handle.isAlive())
        except Exception:
            return None

    def getText(self) -> str:
        # The save flow persists this via set_compute_expression; JIT source
        # goes separately through markSaved().
        return self._expr_editor.getText()

    def setText(self, text: str) -> None:
        self._expr_editor.setText(text)

    def hasUnsavedChanges(self) -> bool:
        if self._expr_editor.hasUnsavedChanges():
            return True
        if self._init_editor is not None and self._init_editor.hasUnsavedChanges():
            return True
        if (
            self._viewport_editor is not None
            and self._viewport_editor.hasUnsavedChanges()
        ):
            return True
        if self._osl_editor is not None and self._osl_editor.hasUnsavedChanges():
            return True
        if (
            self._output_builder_editor is not None
            and self._output_builder_editor.hasUnsavedChanges()
        ):
            return True
        if self._api_view is not None and self._api_view.hasUnsavedChanges():
            return True
        return False

    def markSaved(self) -> None:
        """Mark every inner editor as saved. The compute (expression)
        save already ran through ``_SetExpressionCommand`` upstream;
        here we also persist the Init source via the init editor's
        markSaved() (which calls ``node.set_init_expression(text)``) and,
        when present, the Viewport source via the viewport editor's
        markSaved() (``node.set_viewport_expression(text)``) and the
        Output Builder source via the output-builder editor's
        markSaved() (``node.set_output_builder_source(text)`` +
        ``set_output_builder_enabled(bool)``)."""
        self._expr_editor.markSaved()
        if self._init_editor is not None:
            self._init_editor.markSaved()
        if self._viewport_editor is not None:
            self._viewport_editor.markSaved()
        if self._osl_editor is not None:
            self._osl_editor.markSaved()
        if self._output_builder_editor is not None:
            self._output_builder_editor.markSaved()
        # LAST, and it re-reads _methodsSource before splicing, so whatever the
        # Methods pane just wrote is the base its regions are spliced into
        # rather than being overwritten wholesale.
        if self._api_view is not None:
            self._api_view.markSaved()

    def refresh(self) -> None:
        self._expr_editor.refresh()
        if self._init_editor is not None:
            self._init_editor.refresh()
        if self._viewport_editor is not None:
            self._viewport_editor.refresh()
        if self._osl_editor is not None:
            self._osl_editor.refresh()
        if self._output_builder_editor is not None:
            self._output_builder_editor.refresh()
        if self._api_view is not None:
            self._api_view.refresh()
            # Hand the navigator the API view's OWN region list rather than
            # letting it bake a second time: two equal-but-separate bakes are
            # two things that can drift.
            if self._navigator is not None:
                self._navigator.refresh(self._api_view.regions())

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def refreshIdentityViews(self) -> None:
        """Re-bake the two views that print the Class -- the API view and the
        Outline -- and nothing else. ``refresh()`` also re-pulls every
        expression editor, which resets their dirty baselines and would throw
        away typed-but-unsaved code; a Class change must not cost that. (The
        API view keeps unsaved Methods edits across its own refresh.)"""
        if self._api_view is None:
            return
        self._api_view.refresh()
        if self._navigator is not None:
            self._navigator.refresh(self._api_view.regions())

    def _on_inner_dirty_changed(self, _is_dirty_inner: bool) -> None:
        # Aggregate dirty state across the inner editors.
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())

    # ------------------------------------------------------------------
    # Shared tier (Init / Compute / ...) across ALL node editors
    # ------------------------------------------------------------------

    def _index_for_tier(self, name: str) -> int:
        """Inner-tab index whose label == ``name``, or -1 if this node lacks it."""
        for i in range(self._inner_tabs.count()):
            if self._inner_tabs.tabText(i) == name:
                return i
        return -1

    def _node_key(self):
        """Session-stable identity for the backing node, for ``_seen_nodes``.

        Prefers the node's UUID, so a rename is still the same node. NOT the
        MObjectHandle hash that ``__init__`` already resolved, tempting as it
        is: Maya recycles hash codes once an object is destroyed, so after a
        File>New a brand new node can inherit a dead one's entry and be
        treated as already-seen. A UUID is never reused.

        Falls back to the name and then to object identity -- being wrong here
        only costs one tier choice.
        """
        try:
            from maya import cmds as mc

            uuid = mc.ls(self._py_node.get_name(), uuid=True)
            if uuid:
                return ("uuid", str(uuid[0]))
        except Exception:
            pass
        try:
            name = self._py_node.get_name()
            if name:
                return ("name", str(name))
        except Exception:
            pass
        return ("id", id(self._py_node))

    def _apply_shared_tier(self) -> None:
        """Show the session-wide shared tier tab if this node has it; otherwise
        fall back to Compute (always present). Programmatic, so it does not
        update the shared choice (guarded).

        A node being seen for the first time this session ignores the shared
        tier and opens on Compute -- see ``_seen_nodes``. The check lives here
        rather than at the two call sites (``__init__`` and the show event)
        because those are source-pinned by tests, and because every path that
        reveals a node's editor for the first time necessarily comes through
        here.
        """
        first_open = self._node_key() not in NDScriptTabContent._seen_nodes
        NDScriptTabContent._seen_nodes.add(self._node_key())
        tier   = "Compute" if first_open else NDScriptTabContent._shared_tier
        target = self._index_for_tier(tier)
        if target < 0:
            target = self._index_for_tier("Compute")
        if target < 0 or target == self._inner_tabs.currentIndex():
            return
        self._applying_shared_tier = True
        try:
            self._inner_tabs.setCurrentIndex(target)
        finally:
            self._applying_shared_tier = False

    def _on_inner_tab_changed(self, index: int) -> None:
        """A USER-driven tier click becomes the shared choice for every node --
        and lights the navigator row that names the same target. This is the
        return leg: before it, the navigator drove the tabs but the tabs never
        drove the navigator, so selecting Compute in the strip left the table
        pointing somewhere else."""
        if index < 0:
            return
        if not self._applying_shared_tier:
            NDScriptTabContent._shared_tier = self._inner_tabs.tabText(index)
        # The API view is a projection of the node, not a buffer, so it can go
        # stale while you edit a tier. Re-bake when it comes forward.
        if (self._api_view is not None
                and self._inner_tabs.widget(index) is self._api_view):
            self._api_view.refresh()
            if self._navigator is not None:
                self._navigator.refresh(self._api_view.regions())
        if self._navigator is not None:
            self._navigator.setCurrentKey(
                self._key_for_tab(self._inner_tabs.tabText(index)))
        self.tierChanged.emit(self._inner_tabs.tabText(index))

    def currentTier(self) -> str:
        """The tier name currently shown in the strip ("" if none)."""
        idx = self._inner_tabs.currentIndex()
        return self._inner_tabs.tabText(idx) if idx >= 0 else ""

    def _on_region_activated(self, region) -> None:
        """Clicking a line in the API view lights up the navigator row that
        names it.

        NOT ``select()``: that would scroll the caret to the region's first
        line, and the user is already looking at the line they just clicked.
        Highlight only.
        """
        if self._navigator is None:
            return
        key = self._navigator.keyForRegion(region)
        if key:
            self._navigator.setCurrentKey(key)

    @staticmethod
    def _key_for_tab(label: str) -> str:
        """Tab label -> selection key. ``API`` is its own target; every other
        segment is a tier."""
        if label == "API":
            return "api"
        return "tier.%s" % str(label).lower()

    def _tab_for_key(self, key: str) -> int:
        """Selection key -> tab index, matching on the LOWERCASED label rather
        than title-casing the key: ``tier.osl`` must find the ``OSL`` tab, and
        ``"osl".capitalize()`` is ``"Osl"``."""
        want = key.split(".", 1)[1] if "." in key else key
        for i in range(self._inner_tabs.count()):
            if self._inner_tabs.tabText(i).lower() == want:
                return i
        return -1

    def select(self, key: str) -> bool:
        """Show ``key``. THE navigation entry point -- the tab strip, the
        navigator table and the API view's managed zones all route here, so
        there is no 'now also update the other widget' line to forget.

        Keys: ``api``, ``tier.<name>``, and ``module.*`` / ``member.*`` /
        ``class.*``, which live only in the baked file and therefore resolve to
        the API view scrolled to their region.
        """
        if not key:
            return False
        if key.startswith("tier."):
            index = self._tab_for_key(key)
            if index < 0:
                return False
            self._inner_tabs.setCurrentIndex(index)
            return True
        index = self._index_for_tier("API")
        if index < 0 or self._api_view is None:
            return False
        self._inner_tabs.setCurrentIndex(index)
        if key == "api":
            return True
        region = None
        if self._navigator is not None:
            region = self._navigator.regionForKey(key)
        if isinstance(region, dict):
            self._api_view.goToLine(int(region["start"]))
        return True

    def _on_run_requested(self, run_kind: str, name: str) -> None:
        """Run a member from the navigator. Delegates to the SAME undoable
        commands the Methods outline used, so a run behaves identically to the
        one the Script pane offered."""
        from mpynode._base.commands import (
            run_undoable,
            _RunCommandCommand,
            _RunDemoCommand,
            _RunSetupCommand,
            _RunTestCommand,
        )

        node_name = self._py_node.get_name()
        ntype     = self._py_node.NATIVE_TYPE
        if run_kind == "command":
            # A parameterised command still asks for its arguments, exactly as
            # the Methods outline's Run did.
            kwargs = {}
            params = self._run_params(name)
            if params:
                from mpynode.ui.widgets.command_args import prompt_command_args

                kwargs = prompt_command_args(name, params, self)
                if kwargs is None:
                    return
            cmd = _RunCommandCommand(node_name, ntype, name, (), kwargs)
        elif run_kind == "demo":
            cmd = _RunDemoCommand(node_name, ntype, name)
        elif run_kind == "setup":
            cmd = _RunSetupCommand(node_name, ntype)
        elif run_kind == "test":
            cmd = _RunTestCommand(node_name, ntype, name)
        else:
            return
        try:
            run_undoable(cmd)
        except Exception as exc:  # noqa: BLE001
            from mpynode.ui.qt_wrapper import QMessageBox

            QMessageBox.warning(
                self, "Run failed", "%s could not run:\n%s" % (name, exc))

    def _run_params(self, run_name: str):
        """The parameter names of the command whose run_name is ``run_name``,
        read off the region map so there is no second detector."""
        if self._api_view is None:
            return ()
        for region in self._api_view.regions():
            if region.get("run_name") == run_name:
                return tuple(region.get("run_params") or ())
        return ()

    def _on_insert_template(self, source: str) -> None:
        """Append a blessed command's source to the node's Methods source, then
        re-bake so the new def appears in the API view and the navigator.

        Writes the plug directly now that there is no Methods editor to type
        into. The insert is therefore SAVED rather than left dirty -- the old
        pane deliberately left it unsaved so the pasted ``name=`` had to be
        changed before committing, and the equivalent guard here is that the
        def lands in the API view with the caret on it, ready to rename.
        """
        if not source or not hasattr(self._py_node, "set_methods_source"):
            return
        # Flush any in-progress edit FIRST, or the read below misses it and the
        # write clobbers it.
        if self._api_view is not None:
            self._api_view.markSaved()
        try:
            current = self._py_node.get_methods_source() or ""
        except Exception:  # noqa: BLE001
            current = ""
        chunk = source if not current.strip() else current.rstrip(
            "\n") + "\n\n\n" + source
        try:
            self._py_node.set_methods_source(chunk)
        except Exception as exc:  # noqa: BLE001
            from mpynode.ui.qt_wrapper import QMessageBox

            QMessageBox.warning(
                self, "Insert template", "Could not insert:\n%s" % exc)
            return
        if self._api_view is not None:
            self._api_view.refresh(force=True)
            if self._navigator is not None:
                self._navigator.refresh(self._api_view.regions())
            self.select("api")

    def showEvent(self, event):
        # This document tab just became active; snap it to the shared tier so
        # switching nodes never jumps tiers.
        self._apply_shared_tier()
        super().showEvent(event)

    def _on_osl_translate_clicked(self) -> None:
        """Clear any stale strip state from a prior run, then translate. The AI
        fallback re-shows the strip via convertBusyChanged; a deterministic
        success leaves it cleared/hidden."""
        strip = getattr(self, "_osl_activity", None)
        if strip is not None:
            strip.reset()
        self._osl_editor.convertFromCompute()

    def _on_osl_convert_busy(self, busy: bool) -> None:
        """Reflect the AI-fallback translation (worker thread) on the button and
        start the activity strip. The strip's terminal state (ok/cancel/error) is
        set by the outcome handlers below, NOT here."""
        btn = getattr(self, "_osl_convert_btn", None)
        if btn is not None:
            btn.setEnabled(not busy)
            btn.setText(
                "Translating with AI…" if busy else "Translate Compute → OSL"
            )
        strip = getattr(self, "_osl_activity", None)
        if strip is not None and busy:
            strip.start()

    def _on_osl_convert_progress(self, line) -> None:
        """Stream one raw chain-of-thought / tool line into the strip's log and
        bump the curated headline when a recognizable stage line goes by."""
        strip = getattr(self, "_osl_activity", None)
        if strip is None:
            return
        strip.add_log_line(line)
        low = str(line).lower()
        if "compil" in low or "validat" in low:
            strip.set_stage("Validating OSL compile…")
        elif "repair" in low or "attempt" in low or "fix" in low:
            strip.set_stage("Repairing…")

    def _on_osl_convert_ok(self) -> None:
        strip = getattr(self, "_osl_activity", None)
        if strip is not None:
            strip.finish_ok()

    def _on_osl_convert_failed(self, message) -> None:
        strip = getattr(self, "_osl_activity", None)
        if strip is not None:
            strip.finish_error(str(message))

    def _on_osl_convert_cancelled(self) -> None:
        strip = getattr(self, "_osl_activity", None)
        if strip is not None:
            strip.finish_cancelled()
