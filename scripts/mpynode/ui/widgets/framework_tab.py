"""Framework tab -- read-only left pane describing the active node's WRAPPER.

TIER-SCOPED. ``self`` is not one object in this product: the expression tiers
(Init / Compute / Viewport) get a ``SelfProxy``, while the API tab -- setup,
demo and ``@maya_command`` bodies, the surface that absorbed the old Methods
pane -- gets the real WRAPPER. The two are DISJOINT, so a panel that lists both
while you edit one is advertising calls that raise ``AttributeError``. The
editor pushes the active tab in via :meth:`NDFrameworkWidget.setActiveTier`,
and ``plug_tree_walker.framework_scope_for`` decides which groups exist at all
(see ``tests/ui/test_framework_tier_scope`` for the measurements behind it).

Groups, all display-only:

  * **Methods** -- COMPUTE / VIEWPORT only. The wrapper's blessed
    ``INTERNAL_API_METHODS`` (each a ``MethodSpec``): entries carry
    ``runtime=`` / ``lower=Transpile(...)`` / ``reads=<plugs>`` and are
    validated against real plugs, because they lower to C++. Every method row
    stashes its spec on the item via ``setData(0, Qt.UserRole, spec)`` so the
    right-click menu can jump straight to the transpiled source
    (``resolve_method_source``) -- open it in the external editor, reveal it in
    the OS file manager, or copy its path.
  * **Properties** -- COMPUTE / VIEWPORT only. The non-plug
    ``INTERNAL_API_SLOTS`` surface (via ``variables.collect_internal_api_rows``):
    the wrapper's ``self.X`` read/write slots that are NOT backed by a Maya plug
    (so they don't show in Attributes) -- mPyIkSolver's joints / end_effector /
    pole_vector, mPyMesh's points / counts, mPyFile's time. The METHOD rows that
    helper appends at the end are SKIPPED: the Methods group already shows them.
    VP2-injected handles (``VIEWPORT_ONLY_SLOTS``) are dropped on every tier but
    Viewport, where alone they exist. Plug-only wrappers (mPySkinCluster,
    mPyNode, the deformer family) show a "(none)" placeholder -- their whole
    surface lives in the Attributes tab.
  * **Authoring Methods** (+ a second **Properties** group) -- API TAB ONLY.
    The scene-mutating Python API a setup or a command body calls
    (``self.load_target``, ``self.add_target``, ``self.rebuild``), plus the
    wrapper's ``@property`` surface, which likewise resolves on the wrapper.
    These do file IO and mutate the node, so they can never join the blessed
    tuple. CURATED per wrapper via ``AUTHORING_API``, not derived from
    ``dir()``: derivation could not tell a real authoring verb from internal
    table plumbing, so it listed methods the wrapper's own docstrings describe
    as automatic. ``tests/framework/test_authoring_api_allowlist`` is the drift guard
    curation costs. Rows carry no spec, so the jump-to-source menu correctly
    stays inert on them.
  * **Draw types** -- mPyLocator on the COMPUTE tab only: the ``Draw*`` classes
    ``self.draw`` accepts, with their constructor signatures. ``self.draw`` is
    a compute assignment, and nothing else in the UI names these.

Init and OSL reach none of it and render the scope's ``note`` instead -- an
empty tree with no message reads as a broken panel, not as an answer.

The widget is a thin, read-only view: no editing, no writes. All the data comes
from the Qt-free helpers in ``plug_tree_walker`` + ``variables`` so it stays in
lock-step with the Variables tab's Properties section.
"""

from __future__ import annotations

from mpynode._common.methods.blessed_source import resolve_method_source
from mpynode.ui.editor_launch import (
    open_in_editor,
    reveal_in_file_manager,
    reveal_label,
)
from mpynode.ui.qt_wrapper import (
    QMenu,
    QMessageBox,
    QSize,
    QStyledItemDelegate,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from mpynode.ui.widgets.plug_tree_walker import (
    _internal_api_method_specs_for,
    _wrapper_class_for,
    authoring_method_rows_for,
    framework_scope_for,
    viewport_only_slots,
    wrapper_property_rows_for,
)
from mpynode.ui.widgets.variables import _dir_label, collect_internal_api_rows


# Rows sat at the exact glyph height, so a long Authoring Methods group read as
# a solid block of text. A DELEGATE rather than a per-item size hint: this tree
# builds rows at a dozen-odd sites (group headers, method / authoring /
# property / draw rows, three kinds of "(none)" placeholder), and one delegate
# covers all of them plus any added later.
_ROW_PAD = 2


class _RowPad(QStyledItemDelegate):
    """Adds :data:`_ROW_PAD` pixels of height to every row."""

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), size.height() + _ROW_PAD)


def _is_locator(node_name):
    cls = _wrapper_class_for(node_name)
    return getattr(cls, "__name__", "") == "MPyLocator"


def _draw_type_rows():
    """``(name, signature, doc)`` for every public Draw type.

    A locator's whole visual surface is ``self.draw = <these>``, and nothing
    else in the UI names them, so the tab lists them with their constructor
    signature."""
    import inspect

    from mpynode._common.draw import draw_types

    rows = []
    for name in getattr(draw_types, "__all__", ()):
        cls = getattr(draw_types, name, None)
        if not inspect.isclass(cls) or not name.startswith("Draw"):
            continue
        try:
            sig = str(inspect.signature(cls.__init__))
            sig = sig.replace("(self, ", "(", 1).replace("(self)", "()", 1)
        except (TypeError, ValueError):
            sig = "(...)"
        rows.append((name, sig, inspect.getdoc(cls) or ""))
    return rows


class NDFrameworkWidget(QWidget):
    """Read-only Framework tab: blessed Methods + non-plug Properties."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._py_node = None
        # Which script tier the editor is showing. The panel lists only the
        # surface THAT tier can reach, so it must be told; None means "not
        # wired yet" and falls back to the Compute scope.
        self._tier = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._tree = QTreeWidget(self)
        # Shift-click any section header to expand/collapse THAT subtree.
        from mpynode.ui.widgets.tree_expand import (
            install_shift_click_expand_all,
        )
        install_shift_click_expand_all(self._tree)
        # Kept on self: PySide GCs a delegate held only by the view.
        self._row_pad = _RowPad(self._tree)
        self._tree.setItemDelegate(self._row_pad)
        self._tree.setHeaderLabels(["Name", "Detail"])
        self._tree.setRootIsDecorated(True)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_menu)
        layout.addWidget(self._tree)

    def getMPyNode(self):
        return self._py_node

    def setPyNode(self, py_node):
        self._py_node = py_node
        self.refresh()

    def setActiveTier(self, tier):
        """Tell the panel which script tab the user is editing.

        The Framework surface is NOT uniform across tiers -- the expression
        tiers get a SelfProxy, the API tab gets the wrapper, and the two are
        disjoint -- so the tier decides which groups exist at all. No-op when
        the tier is unchanged, because a tab click must not cost a rebuild."""
        if tier == self._tier:
            return
        self._tier = tier
        self.refresh()

    def activeTier(self):
        return self._tier

    def refresh(self):
        self._tree.clear()
        if self._py_node is None:
            self._add_placeholder("(no active node)")
            return
        try:
            node_name = self._py_node.get_name()
        except Exception:
            node_name = None
        if not node_name:
            self._add_placeholder("(no active node)")
            return

        # What the ACTIVE TIER can reach. Everything below is gated on this:
        # offering a row the current tab cannot call is noise at best and a
        # silent AttributeError at worst.
        scope = framework_scope_for(self._tier)

        # --- Methods group: blessed INTERNAL_API_METHODS -------------------
        if scope["methods"]:
            methods_top = QTreeWidgetItem(self._tree, ["Methods", ""])
            methods_top.setFlags(Qt.ItemIsEnabled)
            methods_top.setFirstColumnSpanned(True)
            try:
                specs = _internal_api_method_specs_for(node_name)
            except Exception:
                specs = []
            if specs:
                for spec in specs:
                    child = QTreeWidgetItem(methods_top, [spec.name, spec.sig])
                    if spec.doc:
                        child.setToolTip(0, spec.doc)
                        child.setToolTip(1, spec.doc)
                    # _on_menu reads this to resolve + jump to source.
                    child.setData(0, Qt.UserRole, spec)
            else:
                none_row = QTreeWidgetItem(methods_top, ["(none)", ""])
                none_row.setFlags(Qt.ItemIsEnabled)

        # --- Authoring Methods group: the scene-mutating wrapper API -------
        # The wrapper's own API -- what a setup / demo / @maya_command body in
        # the API tab calls (self.load_target, self.add_target, self.rebuild).
        # API TAB ONLY: these resolve on the WRAPPER, and an expression tier's
        # `self` is a SelfProxy that raises AttributeError for every one of
        # them. Curated via each wrapper's AUTHORING_API tuple.
        if scope["authoring"]:
            auth_top = QTreeWidgetItem(self._tree, ["Authoring Methods", ""])
            auth_top.setFlags(Qt.ItemIsEnabled)
            auth_top.setFirstColumnSpanned(True)
            try:
                auth_rows = authoring_method_rows_for(node_name)
            except Exception:
                auth_rows = []
            if auth_rows:
                for name, sig, doc in auth_rows:
                    child = QTreeWidgetItem(auth_top, [name, sig])
                    child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if doc:
                        child.setToolTip(0, doc)
                        child.setToolTip(1, doc)
            else:
                none_row = QTreeWidgetItem(auth_top, ["(none)", ""])
                none_row.setFlags(Qt.ItemIsEnabled)

            # Wrapper @property surface -- ALSO wrapper-side, so it belongs on
            # the API tab and nowhere else. Empty on most wrappers; mPyBlendShape
            # carries aliases / target_count / alias_fingerprint / morphs.
            self._add_api_properties(node_name)

        # --- Properties group: non-plug INTERNAL_API_SLOTS -----------------
        if not scope["slots"]:
            self._finish(scope)
            return
        state_top = QTreeWidgetItem(self._tree, ["Properties", ""])
        state_top.setFlags(Qt.ItemIsEnabled)
        state_top.setFirstColumnSpanned(True)
        try:
            rows = collect_internal_api_rows(node_name)
        except Exception:
            rows = []
        # collect_internal_api_rows appends the blessed methods, direction
        # "method", at the end. Skip them: the Methods group already shows
        # them, and Properties is strictly the slot surface.
        slot_rows = [
            (name, direction, value_text)
            for (name, direction, value_text) in rows
            if direction != "method"
        ]
        # VP2-injected handles (shader / mappings / texture_manager /
        # state_manager) exist ONLY while the Viewport tier runs; in Compute
        # they raise AttributeError. Drop them on every other tier rather than
        # advertise four rows the tab cannot call.
        if self._tier != "Viewport":
            try:
                vp_only = viewport_only_slots(node_name)
            except Exception:
                vp_only = frozenset()
            if vp_only:
                slot_rows = [r for r in slot_rows if r[0] not in vp_only]
        # A wrapper @property is NOT part of the SelfProxy slot surface -- it
        # resolves on the WRAPPER (mPyBlendShape.aliases is explicitly
        # "never bound into SelfProxy", reserved_names._AUTHORING_ONLY_SLOTS).
        # It is listed under the API tab instead of being appended here, where
        # it would claim to be callable from an expression.
        if slot_rows:
            for name, direction, value_text in slot_rows:
                detail = "%s  %s" % (_dir_label(direction), value_text)
                child = QTreeWidgetItem(state_top, [name, detail])
                child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        else:
            none_row = QTreeWidgetItem(
                state_top, ["(none -- plug-only node)", ""]
            )
            none_row.setFlags(Qt.ItemIsEnabled)

        # --- Draw types group: the self.draw surface (locators only) -------
        # Compute-tier only: self.draw is assigned there, so a Draw* type is
        # only nameable from that tab.
        try:
            wants_draw = scope["draw"] and _is_locator(node_name)
        except Exception:
            wants_draw = False
        if wants_draw:
            draw_top = QTreeWidgetItem(self._tree, ["Draw types", ""])
            draw_top.setFlags(Qt.ItemIsEnabled)
            draw_top.setFirstColumnSpanned(True)
            try:
                draw_rows = _draw_type_rows()
            except Exception:
                draw_rows = []
            for name, sig, doc in draw_rows:
                child = QTreeWidgetItem(draw_top, [name, sig])
                child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if doc:
                    child.setToolTip(0, doc)
                    child.setToolTip(1, doc)
            if not draw_rows:
                none_row = QTreeWidgetItem(draw_top, ["(none)", ""])
                none_row.setFlags(Qt.ItemIsEnabled)

        self._finish(scope)

    def _finish(self, scope):
        """Expand, and explain an empty panel.

        A tier that reaches nothing (Init, OSL) must say WHY -- an empty tree
        with no message reads as a broken panel, not as an answer."""
        if self._tree.topLevelItemCount() == 0:
            self._add_placeholder(scope.get("note") or "(nothing available "
                                                       "on this tab)")
        self._tree.expandAll()

    def _add_api_properties(self, node_name):
        """The wrapper's ``@property`` surface, as an API-tab group.

        These read as ``self.X`` on the WRAPPER -- so they belong beside the
        authoring methods, not beside the SelfProxy slots. Emitted only when
        the wrapper actually has some (mPyFile has none, which is why its API
        tab shows authoring methods alone)."""
        try:
            prop_rows = wrapper_property_rows_for(node_name)
        except Exception:
            prop_rows = []
        if not prop_rows:
            return
        top = QTreeWidgetItem(self._tree, ["Properties", ""])
        top.setFlags(Qt.ItemIsEnabled)
        top.setFirstColumnSpanned(True)
        for name, kind, doc in prop_rows:
            detail = doc.splitlines()[0] if doc else kind
            child = QTreeWidgetItem(top, [name, detail])
            child.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if doc:
                child.setToolTip(0, doc)
                child.setToolTip(1, doc)

    def _add_placeholder(self, text):
        item = QTreeWidgetItem(self._tree, [text, ""])
        item.setFlags(Qt.NoItemFlags)
        item.setFirstColumnSpanned(True)

    def _on_menu(self, pos):
        item = self._tree.itemAt(pos)
        spec = item.data(0, Qt.UserRole) if item is not None else None
        # Only blessed method rows carry a spec.
        if spec is None:
            return

        menu = QMenu(self._tree)
        resolved = resolve_method_source(spec)
        open_act = reveal_act = copy_act = None
        if resolved is not None:
            open_act = menu.addAction("Open in Editor")
            reveal_act = menu.addAction(reveal_label())
            copy_act = menu.addAction("Copy Path")
        else:
            menu.addAction("(source not on disk)").setEnabled(False)

        run = getattr(menu, "exec_", None) or menu.exec
        chosen = run(self._tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen is open_act:
            path, line = resolved
            ok, err = open_in_editor(path, line)
            if not ok:
                QMessageBox.warning(self, "Open in Editor", err or "failed")
        elif chosen is reveal_act:
            reveal_in_file_manager(resolved[0])
        elif chosen is copy_act:
            # qt_wrapper deliberately does NOT export QApplication -- importing
            # it perturbs Qt platform init -- so lazy-import QGuiApplication
            # from the bound binding. clipboard() is static on PySide2/6.
            try:
                try:
                    from PySide6.QtGui import QGuiApplication
                except ImportError:
                    from PySide2.QtGui import QGuiApplication
                clip = QGuiApplication.clipboard()
                if clip is not None:
                    clip.setText(resolved[0])
            except Exception as exc:
                QMessageBox.warning(self, "Copy Path", str(exc))
