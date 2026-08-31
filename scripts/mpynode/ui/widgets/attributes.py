"""Attribute panels (Inputs + Outputs) with right-click menus + inline rename.

Extracts the Attributes-tab widgets out of mpynode_designer.py
into their own module + adds:

  * Right-click context menu on Input + Output trees
    \u2192 Add New Input/Output
    \u2192 Delete (if selected)
    \u2192 Connect Attrs
    \u2192 Disconnect All
    \u2192 Select Node
  * Inline rename via Qt.ItemIsEditable on user attr items
  * NDAddAttrDialog wired to the Add action
  * NDConnectInputAttrDialog / NDConnectOutputAttrDialog wired to Connect

All write ops go through ``run_undoable`` for Ctrl+Z support.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode._base.commands import (
    _AddInputAttrCommand,
    _AddOutputAttrCommand,
    _ClobberMultiConnectCommand,
    _ConnectAttrCommand,
    _DeleteAttrCommand,
    _DisconnectAllCommand,
    _RenameAttrCommand,
    _ReorderAttrCommand,
    _SetAttrColorCommand,
    _SetSparseCommand,
    _timeline_is_playing,
    run_undoable,
)
from mpynode.ui.dialogs.add_attr import NDAddAttrDialog, validate_attr_name
from mpynode.ui.dialogs.confirm import confirm_delete_node
from mpynode.ui.dialogs.connect_attr import (
    NDConnectInputAttrDialog,
    NDConnectOutputAttrDialog,
)
from mpynode.ui.qt_wrapper import (
    QAction,
    QCheckBox,
    QColor,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    Signal,
)


# ===========================================================================
# Blank icon for guaranteed left padding
# ===========================================================================
# QSS alone (viewport margins + QTreeView::item) gave no visible indent in
# Maya: the bundled theme stylesheet wins on specificity. setIcon(0, ...)
# always reserves a pixel slot before the text, which is structural and not
# CSS-overridable. Lazy-created on first call.
_BLANK_ICON = None
_BLANK_ICON_WIDTH = 12  # px — just enough breathing room
_BLANK_ICON_HEIGHT = 16


def _blank_icon():
    """Return a cached transparent QIcon used purely as a left-padding
    placeholder in ``QTreeWidgetItem``\\s.

    Returns None if Qt isn't available (defensive — callers are
    Qt-only anyway).
    """
    global _BLANK_ICON
    if _BLANK_ICON is not None:
        return _BLANK_ICON
    try:
        from mpynode.ui.qt_wrapper import QIcon, QPixmap, Qt
    except Exception:
        return None
    pixmap = QPixmap(_BLANK_ICON_WIDTH, _BLANK_ICON_HEIGHT)
    pixmap.fill(Qt.transparent)
    _BLANK_ICON = QIcon(pixmap)
    return _BLANK_ICON


# ---------------------------------------------------------------------------
# Connection-state visuals (icon + muted unconnected text)
# ---------------------------------------------------------------------------
# Replaces a bold-on-connected font convention that didn't read at the tree's
# font size on dark themes. Connected -> filled dot icon in column 0 +
# default-brightness text; disconnected -> blank icon + muted-gray text.
# Rows with an explicit ``ui_color`` keep full-strength foreground either way
# (users opted into the color), so the icon is their only connection signal.
_CONNECTED_ICON = None
_CONNECTED_DOT_RGB = (130, 195, 255)  # light cyan-blue accent
_MUTED_BRUSH = None
_MUTED_BRUSH_RGBA = (180, 180, 180, 140)  # ~55% gray for unconnected text


def _connected_icon():
    """Return a cached QIcon containing a small filled dot used to
    flag rows whose plug has at least one connection.

    Same canvas dimensions as ``_blank_icon()`` so connected and
    disconnected rows stay vertically aligned in the tree. Falls
    back to the blank icon when Qt isn\'t available -- degrades to
    no visible indicator rather than crashing.
    """
    global _CONNECTED_ICON
    if _CONNECTED_ICON is not None:
        return _CONNECTED_ICON
    try:
        from mpynode.ui.qt_wrapper import (
            QBrush,
            QColor,
            QIcon,
            QPainter,
            QPixmap,
            Qt,
        )
    except Exception:
        return _blank_icon()
    pixmap = QPixmap(_BLANK_ICON_WIDTH, _BLANK_ICON_HEIGHT)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(*_CONNECTED_DOT_RGB)))
        cx = _BLANK_ICON_WIDTH // 2
        cy = _BLANK_ICON_HEIGHT // 2
        # 6 px dot centered on the 12 x 16 canvas.
        painter.drawEllipse(cx - 3, cy - 3, 6, 6)
    finally:
        painter.end()
    _CONNECTED_ICON = QIcon(pixmap)
    return _CONNECTED_ICON


def _muted_brush():
    """Return a cached QBrush used to dim the foreground of
    disconnected rows that don\'t carry a custom ``ui_color``."""
    global _MUTED_BRUSH
    if _MUTED_BRUSH is not None:
        return _MUTED_BRUSH
    try:
        from mpynode.ui.qt_wrapper import QBrush, QColor
    except Exception:
        return None
    _MUTED_BRUSH = QBrush(QColor(*_MUTED_BRUSH_RGBA))
    return _MUTED_BRUSH


# ===========================================================================
# Tree items
# ===========================================================================


class NDLockedAttrTreeItem(QTreeWidgetItem):
    """Read-only tree item for inherited / locked plugs.

    now constructed from a ``RowSpec`` returned by
    ``ui.widgets.plug_tree_walker.walk_plug_tree``. Backward-compat
    shim: the old dict-shape constructor argument is still accepted
    via ``locked_row``.
    """

    LOCKED_FLAGS = Qt.ItemIsEnabled  # not Selectable, not Editable

    def __init__(self, parent, locked_row=None, *, row_spec=None):
        super().__init__(parent)
        self.setFlags(self.LOCKED_FLAGS)
        # Transparent icon = left padding (see _blank_icon for why, not QSS).
        blank = _blank_icon()
        if blank is not None:
            self.setIcon(0, blank)
        # Prefer the RowSpec path; fall back to the old dict shape.
        if row_spec is not None:
            self.row_spec = row_spec
            self.setText(0, _locked_label_from_row(row_spec))
            tooltip = _locked_tooltip_from_row(row_spec)
            if tooltip:
                self.setToolTip(0, tooltip)
        else:
            self.row_spec = None
            row = locked_row or {}
            self.setText(0, row.get("display_text", ""))
            tooltip = row.get("tooltip", "")
            if tooltip:
                self.setToolTip(0, tooltip)

    def apply_connection_state(self, node_name: str, direction: str) -> None:
        """Apply the connection-state visual convention to an inherited
        row: column-0 icon swaps between the connected dot and the
        blank placeholder; foreground brush dims to muted-gray when
        the row is disconnected.

        ``direction`` is ``"input"`` or ``"output"`` (per the parent
        tree's ATTR_CATEGORY). Uses the full ``row_spec.plug_path``
        (e.g. ``originalGeometry[0]`` or ``input[0].inputGeometry``)
        so nested compound + array children get classified correctly.

        Caches the resolved state on ``self._is_connected`` for tests
        / introspection.
        """
        self._is_connected = False
        if self.row_spec is None:
            return
        try:
            plug_path = self.row_spec.plug_path
        except Exception:
            return
        if not plug_path:
            return
        try:
            connected = _is_attr_connected(node_name, plug_path, direction)
        except Exception:
            connected = False
        self._is_connected = bool(connected)
        # Same canvas size in both states keeps the label column aligned.
        icon = _connected_icon() if connected else _blank_icon()
        if icon is not None:
            self.setIcon(0, icon)
        # Inherited rows have no user ``ui_color``, so connection state owns
        # the brush outright.
        from mpynode.ui.qt_wrapper import Qt as _Qt
        if connected:
            # Restore theme-default brightness.
            self.setData(0, _Qt.ForegroundRole, None)
        else:
            brush = _muted_brush()
            if brush is not None:
                self.setForeground(0, brush)


def _allowlist_with_ancestors(rows, allowlist):
    """Filter walker ``rows`` to ``allowlist`` (by short name) while KEEPING the
    structural ancestors (array-index element rows and compound parents) of every
    kept row, so ``treeify`` can still nest them.

    An allowlist that keeps rows purely by ``short_name`` drops the intermediate
    element / compound rows whose own short name isn't listed -- e.g. the
    ``input[0]`` element row that sits between the ``input`` multi and its
    allowlisted ``inputGeometry`` child. Dropping an ancestor orphans its kept
    descendants to the tree root (they render flat instead of nested). Re-adding
    ancestors of kept rows preserves nesting; it is NOT an allowlist leak -- a
    row surfaces only because an allowlisted (or user-added) descendant needs it
    as a container. Preserves the input depth-first row order.
    """
    row_by_path = {r.plug_path: r for r in rows}
    keep = set()
    for r in rows:
        if not (r.is_user_added or r.short_name in allowlist):
            continue
        keep.add(r.plug_path)
        p = r.parent_path
        while p and p not in keep:
            keep.add(p)
            anc = row_by_path.get(p)
            p = anc.parent_path if anc is not None else ""
    return [r for r in rows if r.plug_path in keep]


def _locked_label_from_row(row_spec) -> str:
    """Render a ``RowSpec`` into the label shown in the
    Attributes tab. For top-level rows we show the short name plus
    a short type marker; for compound children we show the short
    name only (the parent's type carries the family info)."""
    short = row_spec.short_name
    # Tidy the apiTypeStr: "kNumericAttribute" -> "Numeric".
    type_label = row_spec.attr_type or ""
    if type_label.startswith("k"):
        type_label = type_label[1:]
    if type_label.endswith("Attribute"):
        type_label = type_label[: -len("Attribute")]
    if row_spec.is_array:
        suffix = "[]"
    else:
        suffix = ""
    if type_label:
        return "{}{}: {}".format(short, suffix, type_label)
    return "{}{}".format(short, suffix)


def _locked_tooltip_from_row(row_spec) -> str:
    """Tooltip surfaces the full plug path + connection
    annotation so the artist can sanity-check what's wired."""
    parts = [row_spec.plug_path]
    if row_spec.value_text:
        parts.append(row_spec.value_text)
    return "\n".join(parts)


class NDUserAttrTreeItem(QTreeWidgetItem):
    """Editable tree item for USER-added input/output attrs."""

    # setFlags() REPLACES the default flag set, and Qt only starts a drag when
    # the pressed item carries ItemIsDragEnabled -- so the drag/drop flags are
    # required for connection-wiring AND drag-to-reorder.
    USER_FLAGS = (
        Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
    )

    def __init__(self, parent, attr_name: str, meta: dict, direction: str = "input"):
        super().__init__(parent)
        self.attr_name = attr_name
        self.attr_meta = meta
        # Direction picks the ``mc.listConnections`` flavour in refresh().
        self.direction = direction
        self.setFlags(self.USER_FLAGS)
        # Transparent icon = left padding (see _blank_icon for why, not QSS).
        blank = _blank_icon()
        if blank is not None:
            self.setIcon(0, blank)
        self.setText(0, self._format_label(attr_name, meta))
        # Array read-mode tooltip (explains the optional "sparse" marker).
        if meta.get("is_array"):
            if meta.get("sparse"):
                self.setToolTip(
                    0,
                    "Sparse array — the expression reads only the connected/"
                    "set elements, compactly (by physical position).",
                )
            else:
                self.setToolTip(
                    0,
                    "Dense array — the expression reads a contiguous array of "
                    "length max_logical+1; gaps are filled with the attribute "
                    "default.",
                )
        self._apply_color(meta)
        self._apply_connection_state()

    def _apply_connection_state(self) -> None:
        """Apply the connection-state visual convention to this row.

        Connected rows get a small dot icon in column 0; disconnected
        rows get the transparent placeholder. The foreground brush
        dims to muted-gray when disconnected AND no ``ui_color`` was
        set in meta -- user-customised colors always win, so a
        deliberately-tagged attr keeps its hue regardless of wiring
        state (the icon remains the sole signal for those rows).

        Caches the resolved state on ``self._is_connected`` for tests
        / introspection.
        """
        # Look up the wrapper on the parent tree (we may be detached).
        tree = self.treeWidget()
        py_node = getattr(tree, "_py_node", None) if tree is not None else None
        connected = False
        if py_node is not None:
            try:
                connected = _is_attr_connected(
                    py_node.get_name(), self.attr_name, self.direction
                )
            except Exception:
                connected = False
        self._is_connected = bool(connected)
        # Always set an icon; the transparent one keeps the label aligned.
        icon = _connected_icon() if connected else _blank_icon()
        if icon is not None:
            self.setIcon(0, icon)
        # ui_color is sacred: if the user set one, _apply_color already won.
        ui_color_set = bool((self.attr_meta or {}).get("ui_color"))
        if ui_color_set:
            return
        from mpynode.ui.qt_wrapper import Qt as _Qt
        if connected:
            self.setData(0, _Qt.ForegroundRole, None)
        else:
            brush = _muted_brush()
            if brush is not None:
                self.setForeground(0, brush)

    def _apply_color(self, meta: dict) -> None:
        """Apply per-attr UI color, if set.

        only apply CUSTOM ``ui_color`` from meta. If no custom
        color is set, leave the foreground at the theme default
        (light-gray on Maya's dark theme). per-attr-TYPE
        color defaults were removed so the tree doesn't look "painted"
        when the user hasn't explicitly chosen colors. The type-color
        palette still exists in ``widgets/icons.py`` (used by node-type
        pills + future opt-in features).
        """
        # Local import to keep top-level Qt overhead low.
        from mpynode.ui.qt_wrapper import QBrush, QColor

        try:
            ui_color = (meta or {}).get("ui_color")
            if ui_color:
                self.setForeground(0, QBrush(QColor(ui_color)))
            # else: leave the default theme color.
        except Exception:
            pass

    # Backwards-compat shim — older tests inspect this method by name.
    def _apply_type_color(self, attr_type: str) -> None:
        # attr_type alone no longer drives a color, so this is a no-op unless
        # meta carries a custom one.
        self._apply_color({"attr_type": attr_type})

    @staticmethod
    def _format_label(name: str, meta: dict) -> str:
        attr_type = meta.get("attr_type", "?")
        is_array = meta.get("is_array", False)
        suffix = "[]" if is_array else ""
        # Dense is the default, so only sparse arrays get a marker.
        type_part = attr_type
        if is_array and meta.get("sparse"):
            type_part = f"{attr_type} (sparse)"
        return f"{name}{suffix}: {type_part}"

    def getCurrentName(self) -> str:
        return self.attr_name


# ===========================================================================
# Rename delegate: hides the ":type" suffix and aligns the editor
# pixel-flush with the painted item text.
# ===========================================================================


class _UserAttrRenameDelegate:
    """Delegate built lazily so qt_wrapper import stays at module level.

    Symptom that motivated this delegate:
      * User double-clicks ``test: float`` to rename it.
      * Qt's default editor opens with the WHOLE label (``test: float``)
        and the QLineEdit's native ~2px padding/border pushes the
        editor text right past where the painted text was, leaving the
        original 't' of 'test' visible behind the editor.

    Fix:
      * ``setEditorData`` reads ``attr_name`` only (not the full label).
      * ``setModelData`` writes the new name back and lets the existing
        ``_on_item_changed`` handler split out the ``": type"`` suffix
        in the simple displayed-text path.
      * ``createEditor`` zeroes out the QLineEdit's frame + text
        margins so the editor sits flush with the painted text rect.
      * ``updateEditorGeometry`` uses the item's visualRect verbatim
        so there's no horizontal jitter when the editor pops open.
    """

    @staticmethod
    def install_on(tree):
        from mpynode.ui.qt_wrapper import QStyledItemDelegate, QLineEdit

        class _Delegate(QStyledItemDelegate):
            def createEditor(self, parent, option, index):
                editor = QLineEdit(parent)
                # Maya's dark style adds ~2px of internal left-padding, so
                # kill the frame, padding and text margins to sit flush.
                try:
                    editor.setFrame(False)
                    editor.setTextMargins(0, 0, 0, 0)
                    editor.setStyleSheet(
                        "padding: 0px; margin: 0px; border: 0px;"
                    )
                except Exception:
                    pass
                return editor

            def setEditorData(self, editor, index):
                # Edit the bare attr_name, not the "name: type" label.
                item = tree.itemFromIndex(index)
                name = getattr(item, "attr_name", None)
                if name is None:
                    name = index.data() or ""
                editor.setText(name)
                editor.selectAll()

            def setModelData(self, editor, model, index):
                # Write via DisplayRole so itemChanged fires and
                # _on_item_changed takes the rename path.
                new_name = editor.text().strip()
                model.setData(index, new_name)

            def updateEditorGeometry(self, editor, option, index):
                # The cell rect already includes the icon padding, so this
                # covers the full text region with no horizontal jitter.
                editor.setGeometry(option.rect)

        delegate = _Delegate(tree)
        tree.setItemDelegateForColumn(0, delegate)
        # Keep a ref on the tree so the delegate isn't GC'd.
        tree._user_attr_rename_delegate = delegate
        return delegate


# ===========================================================================
# connection-state helper
# ===========================================================================


def _is_attr_connected(node_name: str, attr_name: str, direction: str) -> bool:
    """Return True if ``node_name.attr_name`` has a connection on the
    relevant side.

    Direction semantics:
      * ``"input"``  — something plugs INTO this attr (source-side)
      * ``"output"`` — this attr plugs INTO something else (destination-side)

    Multi attrs (arrays) flag the row as connected if ANY index is wired —
    ``mc.listConnections`` on the parent plug returns that union, which
    is the right semantic ("the user wired SOMETHING into this attr at
    all").

    Best-effort: silent False on any failure (node
    missing, attr deleted out-from-under us, etc).
    """
    try:
        full = f"{node_name}.{attr_name}"
        if direction == "input":
            cons = mc.listConnections(full, source=True, destination=False, plugs=False)
        else:
            cons = mc.listConnections(full, source=False, destination=True, plugs=False)
        return bool(cons)
    except Exception:
        return False


# ===========================================================================
# Attribute trees
# ===========================================================================


class NDInputAttrTree(QTreeWidget):
    """Input-attr tree for a single mPyNode.

    + right-click menu + inline rename.
    + drag-and-drop connection wiring (gated to
    user-added rows; uses _ConnectAttrCommand for undoable connects).
    """

    ATTR_CATEGORY = "input"
    LIST_ATTR_FUNC_NAME = "get_input_attr_map"
    # Blue header pairs with the amber Output header.
    HEADER_LABEL = "Input"
    HEADER_COLOR = "#5aa9e6"  # blue -- input

    # After _SetAttrColorCommand: NDAttributesWidget re-emits and the designer
    # routes to the script editor, so the highlighter picks up the new color
    # without a node refresh.
    attrColorChanged = Signal(str)  # node name
    # After a user-attr rename. The rename command also rewrites the node's
    # stored expression sources, so the designer reloads the open editor tab.
    attrRenamed = Signal(str)  # node name

    # Plug drag payload: "<node>.<plug_path>" UTF-8 bytes.
    _MIME_TYPE = "application/x-mpynode-plug"

    # Maya's theme stylesheet scopes its item rule on ``QTreeView::item``
    # (the parent class), which beat our ``QTreeWidget::item`` on specificity
    # and left it with zero visible effect -- so match Maya's own selector.
    # Paired with viewport().setContentsMargins(6, 0, 0, 0) below, which
    # indents before any item is drawn regardless of theme.
    _ITEM_STYLESHEET = "QTreeView::item { padding: 2px 6px; }"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._py_node = None
        # Suppress itemChanged events while we're rebuilding the tree
        # programmatically (otherwise refresh() triggers spurious renames).
        self._refreshing = False
        self.setHeaderLabel(self.HEADER_LABEL)
        # Nested compounds show under their parents (input[0].inputGeometry
        # under input[0] under input); the arrows need root decoration.
        self.setRootIsDecorated(True)
        # See _ITEM_STYLESHEET. Tint the header text with HEADER_COLOR
        # (absent -> no tint).
        _ss = self._ITEM_STYLESHEET
        _hc = getattr(self, "HEADER_COLOR", None)
        if _hc:
            _ss += " QHeaderView::section { color: %s; }" % _hc
        self.setStyleSheet(_ss)
        self.viewport().setContentsMargins(6, 0, 0, 0)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.itemChanged.connect(self._on_item_changed)
        # Delegate edits the bare attr_name and sits pixel-flush with the
        # painted text, so the original first letter stops peeking out.
        try:
            _UserAttrRenameDelegate.install_on(self)
        except Exception:
            # Best-effort polish; default Qt editor still works.
            pass
        # Drops are accepted onto user-added rows; sources are dragged plug
        # names (full node.plug_path).
        try:
            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.setDropIndicatorShown(True)
            self.setDragDropMode(QTreeWidget.DragDrop)
        except Exception:
            pass
        # Tracks the highlighted item so its prior background brush can be
        # restored on drag-leave / drop.
        self._drop_highlight_item = None
        self._drop_highlight_prev_brush = None

    # ------------------------------------------------------------------
    # drag & drop
    # ------------------------------------------------------------------

    def _dragged_plug_full(self, item):
        """Return the full ``node.plug_path`` for the dragged item,
        or None if the item isn't draggable (e.g. a header)."""
        if self._py_node is None or item is None:
            return None
        node_name = self._py_node.get_name()
        if isinstance(item, NDUserAttrTreeItem):
            return f"{node_name}.{item.attr_name}"
        if isinstance(item, NDLockedAttrTreeItem):
            rs = getattr(item, "row_spec", None)
            if rs is not None:
                # An array without an index is an ambiguous target.
                path = rs.plug_path
                if rs.is_array and "[" not in path:
                    path = path + "[0]"
                return f"{node_name}.{path}"
        return None

    def mimeData(self, items):
        """Build a QMimeData payload containing the full
        plug name of the (single) dragged item."""
        try:
            try:
                from PySide6.QtCore import QMimeData
            except Exception:
                from PySide2.QtCore import QMimeData
        except Exception:
            return None
        md = QMimeData()
        if items:
            full = self._dragged_plug_full(items[0])
            if full is not None:
                md.setData(self._MIME_TYPE, full.encode("utf-8"))
                # setText lets external sinks (channel box, Node Editor)
                # read the plug name too.
                md.setText(full)
        return md

    def dragEnterEvent(self, event):
        """Accept any drag whose source carries our MIME
        type. Other MIME types pass through to the default impl."""
        try:
            if event.mimeData().hasFormat(self._MIME_TYPE):
                event.acceptProposedAction()
                return
        except Exception:
            pass
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        """Accept the drop ONLY when hovering over a
        user-added row (edit-op gating mirrors the right-click
        menu rules).

        also highlight the valid drop-target row in
        Maya-Node-Editor-yellow so the artist has clear visual
        feedback. The highlight is cleared on dragLeaveEvent /
        dropEvent."""
        try:
            md = event.mimeData()
            if md is None or not md.hasFormat(self._MIME_TYPE):
                super().dragMoveEvent(event)
                return
            # A same-tree drag of a user attr is a REORDER (you cannot connect
            # two same-direction plugs), so let Qt draw the move indicator --
            # the per-row connect highlight would be misleading.
            if self._is_internal_reorder(event):
                self._clear_drop_highlight()
                event.acceptProposedAction()
                return
            target_item = self.itemAt(event.pos())
            if isinstance(target_item, NDUserAttrTreeItem):
                self._set_drop_highlight(target_item)
                event.acceptProposedAction()
                return
            self._clear_drop_highlight()
            event.ignore()
        except Exception:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        """Clear the drop-target highlight when the drag
        cursor leaves the widget."""
        self._clear_drop_highlight()
        try:
            super().dragLeaveEvent(event)
        except Exception:
            pass

    # Maya-yellow, semi-transparent so item text stays readable.
    _DROP_HIGHLIGHT_RGBA = (255, 204, 0, 128)

    def _set_drop_highlight(self, item):
        """Paint ``item`` with the Maya-yellow highlight.
        Restores the prior background on the previously-highlighted
        item (if any) so the highlight tracks the cursor."""
        if item is self._drop_highlight_item:
            return
        self._clear_drop_highlight()
        try:
            from mpynode.ui.qt_wrapper import QBrush, QColor

            r, g, b, a = self._DROP_HIGHLIGHT_RGBA
            self._drop_highlight_prev_brush = item.background(0)
            item.setBackground(0, QBrush(QColor(r, g, b, a)))
            self._drop_highlight_item = item
        except Exception:
            self._drop_highlight_item = None

    def _clear_drop_highlight(self):
        """Restore the previously-highlighted item's
        background brush. Idempotent."""
        item = self._drop_highlight_item
        if item is None:
            return
        try:
            from mpynode.ui.qt_wrapper import QBrush

            prev = self._drop_highlight_prev_brush
            if prev is not None:
                item.setBackground(0, prev)
            else:
                # No prior brush captured -> reset to default.
                item.setBackground(0, QBrush())
        except Exception:
            pass
        self._drop_highlight_item = None
        self._drop_highlight_prev_brush = None

    def dropEvent(self, event):
        """On drop onto a user-added target, build a
        ``(src_plug, dst_plug)`` pair + apply via
        ``_ConnectAttrCommand`` (preserves undo). clears
        the drop-target highlight before applying."""
        self._clear_drop_highlight()
        try:
            md = event.mimeData()
            if md is None or not md.hasFormat(self._MIME_TYPE):
                super().dropEvent(event)
                return
            # Same-tree drag of a user attr = REORDER, handled separately from
            # the connect path below.
            if self._is_internal_reorder(event):
                self._handle_reorder_drop(event)
                return
            target_item = self.itemAt(event.pos())
            if not isinstance(target_item, NDUserAttrTreeItem):
                event.ignore()
                return
            src_bytes = bytes(md.data(self._MIME_TYPE))
            src_plug = src_bytes.decode("utf-8", errors="replace")
            if not src_plug:
                event.ignore()
                return
            dst_plug = "{}.{}".format(
                self._py_node.get_name(), target_item.attr_name
            )
            if src_plug == dst_plug:
                event.ignore()
                return
            try:
                run_undoable(_ConnectAttrCommand(src_plug, dst_plug, force=True))
                event.acceptProposedAction()
                # Rebuild so the dropped-onto row's connected dot appears.
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(
                    self, "Connect Failed",
                    f"{src_plug} \u2192 {dst_plug}\n\n{exc}",
                )
                event.ignore()
        except Exception:
            super().dropEvent(event)

    # ------------------------------------------------------------------
    # drag-to-reorder (plug-level; user attrs only)
    # ------------------------------------------------------------------

    def _is_internal_reorder(self, event) -> bool:
        """True when ``event`` is a drag that STARTED in this same tree and
        carries one of this node's USER attrs -- the reorder gesture. A
        same-direction drag can't be a connection (you can't wire input->input
        or output->output), so this is unambiguous and steals nothing from the
        connect path."""
        try:
            if event.source() is not self or self._py_node is None:
                return False
            return self._dragged_user_attr_name(event) is not None
        except Exception:
            return False

    def _dragged_user_attr_name(self, event):
        """The dragged plug's bare attr name if it is a USER attr of this node
        (this tree's direction), else None. Compound child / array-element plugs
        are rejected -- reorder operates on parent attrs only."""
        md = event.mimeData()
        if md is None or not md.hasFormat(self._MIME_TYPE):
            return None
        src = bytes(md.data(self._MIME_TYPE)).decode("utf-8", errors="replace")
        prefix = self._py_node.get_name() + "."
        if not src.startswith(prefix):
            return None
        name = src[len(prefix):]
        if "." in name or "[" in name:
            return None
        return name if name in self._current_attr_map() else None

    def _current_attr_map(self) -> dict:
        list_func = getattr(self._py_node, self.LIST_ATTR_FUNC_NAME, None)
        if list_func is None:
            return {}
        try:
            return list_func() or {}
        except Exception:
            return {}

    def _handle_reorder_drop(self, event) -> None:
        """Drop end of a reorder drag: compute the new order from the drop row
        (insert before/after it based on the cursor) and apply it."""
        moved = self._dragged_user_attr_name(event)
        if not moved:
            event.ignore()
            return
        target_item = self.itemAt(event.pos())
        target_name = (target_item.attr_name
                       if isinstance(target_item, NDUserAttrTreeItem) else None)
        place_after = False
        if target_item is not None:
            try:
                rect = self.visualItemRect(target_item)
                place_after = event.pos().y() > rect.center().y()
            except Exception:
                place_after = False
        if self._reorder_to(moved, target_name, place_after):
            event.acceptProposedAction()
            self.refresh()
        else:
            event.ignore()

    def _reorder_to(self, moved_name, target_name, place_after: bool = False) -> bool:
        """Move ``moved_name`` before/after ``target_name`` (or to the end when
        ``target_name`` is None) and apply via ``_ReorderAttrCommand``. Returns
        True iff a reorder was performed."""
        if self._py_node is None:
            return False
        cur = list(self._current_attr_map().keys())
        if moved_name not in cur:
            return False
        order = [n for n in cur if n != moved_name]
        if (target_name is None or target_name == moved_name
                or target_name not in order):
            order.append(moved_name)
        else:
            idx = order.index(target_name)
            if place_after:
                idx += 1
            order.insert(idx, moved_name)
        return self._apply_reorder_order(order)

    def _apply_reorder_order(self, new_order) -> bool:
        """Apply a full new attr order via ``_ReorderAttrCommand`` (undoable).
        Returns True iff applied. REFUSED (returns False, warns) while the
        timeline is playing -- the user chose 'only when the timeline is idle'.
        No-op (False) when the order is unchanged or not a permutation."""
        if self._py_node is None:
            return False
        cur = list(self._current_attr_map().keys())
        if sorted(new_order) != sorted(cur) or list(new_order) == cur:
            return False
        if _timeline_is_playing():
            try:
                mc.warning(
                    "Reorder attributes is disabled during playback -- stop the "
                    "timeline and try again."
                )
            except Exception:
                pass
            return False
        run_undoable(
            _ReorderAttrCommand(self._py_node, list(new_order), self.ATTR_CATEGORY)
        )
        return True

    # ------------------------------------------------------------------
    # keyboard reorder: Shift+Up / Shift+Down on the selected user attr
    # (a trackpad-friendly alternative to drag).
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        try:
            mods = event.modifiers()
            key = event.key()
            if (mods & Qt.ShiftModifier) and key in (Qt.Key_Up, Qt.Key_Down):
                if self._move_selected(-1 if key == Qt.Key_Up else 1):
                    event.accept()
                    return
        except Exception:
            pass
        super().keyPressEvent(event)

    def _move_selected(self, delta: int) -> bool:
        """Move the currently-selected user attr by ``delta`` rows (-1 up,
        +1 down). Reselects the moved attr so repeated presses keep moving it.
        Returns True iff it moved."""
        item = self.currentItem()
        if not isinstance(item, NDUserAttrTreeItem):
            return False
        name = item.attr_name
        cur = list(self._current_attr_map().keys())
        if name not in cur:
            return False
        i = cur.index(name)
        j = i + delta
        if j < 0 or j >= len(cur):
            return False  # already at the edge
        new = list(cur)
        new.insert(j, new.pop(i))
        if not self._apply_reorder_order(new):
            return False
        self.refresh()
        self._select_user_attr(name)
        return True

    def _select_user_attr(self, name) -> None:
        """Select the top-level user-attr row whose attr_name is ``name``."""
        for idx in range(self.topLevelItemCount()):
            it = self.topLevelItem(idx)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == name:
                self.setCurrentItem(it)
                return

    def setNode(self, py_node):
        # The Add-Attr dialog captures ``py_node`` at construction and reuses
        # it forever, so a stale one routes the add to the OLD wrapper and
        # errors with "node 'X' no longer exists in the scene".
        if self._py_node is not py_node:
            self._invalidate_add_dialog()
        self._py_node = py_node
        self.refresh()

    def attachRefreshHub(self, hub) -> None:
        """Subscribe the attribute tree's refresh to a
        shared RefreshHub so addAttr/removeAttr/connectionMade events
        from the channel box or the Node Editor reflect immediately."""
        prev = getattr(self, "_refresh_hub", None)
        view_id = "attr_tree_{}".format(id(self))
        if prev is not None and prev is not hub:
            try:
                prev.unsubscribe(view_id)
            except Exception:
                pass
        self._refresh_hub = hub
        self._refresh_hub_view_id = view_id
        if hub is None:
            return
        from mpynode.ui.widgets.refresh_hub import (
            EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED,
        )

        hub.subscribe(
            view_id,
            lambda _event: self.refresh(),
            events=(EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED),
        )

    def _invalidate_add_dialog(self):
        """Close + drop the cached Add-Attr dialog so the next
        ``_show_add_attr_dlg`` rebuilds it bound to the current
        ``self._py_node``."""
        dlg = getattr(self, "_add_dlg", None)
        if dlg is not None:
            try:
                dlg.close()
            except Exception:
                pass
            try:
                dlg.deleteLater()
            except Exception:
                pass
            self._add_dlg = None

    def refresh(self):
        # Without this, any color set/clear or connection collapses every
        # expanded compound + array row back to its top level.
        expanded_locked = self._capture_expanded_locked_paths()
        expanded_user = self._capture_expanded_user_names()
        self._refreshing = True
        try:
            self.clear()
            # Walk the live plug tree: inherited base-class plugs, nested
            # compound children and array elements, matching what self.X
            # resolves to in the expression AND what the Node Editor shows.
            # User-added attrs are SKIPPED here -- the NDUserAttrTreeItem path
            # below surfaces them and preserves the right-click edit ops.
            self._buildLockedTreeFromWalker()

            # User-added attrs (legacy path): flat rows at the bottom.
            if self._py_node is not None:
                list_func = getattr(self._py_node, self.LIST_ATTR_FUNC_NAME, None)
                if list_func is not None:
                    # Already in authored add-order (each meta's ``order``
                    # field). Do NOT re-sort alphabetically -- that was the bug.
                    attr_map = list_func() or {}
                    for attr_name, meta in attr_map.items():
                        NDUserAttrTreeItem(
                            self, attr_name, meta, direction=self.ATTR_CATEGORY
                        )
        finally:
            self._refreshing = False
        self._restore_expanded_locked_paths(expanded_locked)
        self._restore_expanded_user_names(expanded_user)

    def _capture_expanded_locked_paths(self) -> set:
        """Snapshot the plug_path of every expanded
        NDLockedAttrTreeItem so:meth:`refresh` can restore them."""
        expanded = set()

        def _walk(item):
            for i in range(item.childCount()):
                _walk(item.child(i))
            if (
                isinstance(item, NDLockedAttrTreeItem)
                and item.row_spec is not None
                and item.isExpanded()
            ):
                try:
                    expanded.add(item.row_spec.plug_path)
                except Exception:
                    pass

        for i in range(self.topLevelItemCount()):
            _walk(self.topLevelItem(i))
        return expanded

    def _capture_expanded_user_names(self) -> set:
        """Snapshot expanded NDUserAttrTreeItem attr_names."""
        expanded = set()
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if isinstance(item, NDUserAttrTreeItem) and item.isExpanded():
                expanded.add(item.attr_name)
        return expanded

    def _restore_expanded_locked_paths(self, paths: set) -> None:
        if not paths:
            return

        def _walk(item):
            for i in range(item.childCount()):
                _walk(item.child(i))
            if (
                isinstance(item, NDLockedAttrTreeItem)
                and item.row_spec is not None
            ):
                try:
                    if item.row_spec.plug_path in paths:
                        item.setExpanded(True)
                except Exception:
                    pass

        for i in range(self.topLevelItemCount()):
            _walk(self.topLevelItem(i))

    def _restore_expanded_user_names(self, names: set) -> None:
        if not names:
            return
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if isinstance(item, NDUserAttrTreeItem) and item.attr_name in names:
                item.setExpanded(True)

    def _buildLockedTreeFromWalker(self) -> None:
        """Populate the tree with inherited plugs from
        ``walk_plug_tree``, filtered to this widget's direction
        (INPUT or OUTPUT), with compound + array nesting preserved.

        Walker returns rows in depth-first order with explicit
        ``parent_path`` fields; ``treeify`` builds the nested
        ``TreeNode`` structure that we render one-to-one as
        ``NDLockedAttrTreeItem`` QTreeWidgetItems.
        """
        if self._py_node is None:
            return
        try:
            from mpynode.ui.widgets.plug_tree_walker import (
                walk_plug_tree, filter_by_direction, treeify,
            )
        except Exception:
            return
        try:
            node_name = self._py_node.get_name()
        except Exception:
            return
        try:
            all_rows = walk_plug_tree(node_name)
        except Exception:
            return

        # Walker says "INPUT"/"OUTPUT"/"INTERNAL"; ATTR_CATEGORY is lowercase.
        direction_filter = self.ATTR_CATEGORY.upper()
        scoped_rows = filter_by_direction(all_rows, direction_filter)

        # Skip user-added rows; the NDUserAttrTreeItem path below gives them
        # editable items. Also skip CHILDREN of user-added compounds (e.g.
        # amplitudeX/Y/Z under a user-added "amplitude" Double3) -- otherwise
        # treeify orphans them into confusing top-level inherited rows.
        user_added_paths = {
            r.plug_path for r in scoped_rows if r.is_user_added
        }

        def _under_user_added(plug_path: str) -> bool:
            for ua in user_added_paths:
                if plug_path == ua:
                    return True
                if plug_path.startswith(ua + ".") or plug_path.startswith(ua + "["):
                    return True
            return False

        scoped_rows = [r for r in scoped_rows if not _under_user_added(r.plug_path)]

        # Hide framework / Maya-base plugs (``caching``, ``frozen``,
        # ``nodeState``...) unless the artist ticked "Show framework attrs".
        # Mirrors the Node Editor's curation. User-added rows are exempt --
        # already stripped above.
        if not self._show_framework_attrs():
            try:
                from mpynode.ui.widgets.plug_tree_walker import (
                    _useful_inherited_plugs_for,
                )

                allowlist = _useful_inherited_plugs_for(node_name)
                if allowlist is not None:
                    # ALLOWLIST model: an inherited attr shows only if listed,
                    # so it cannot leak.
                    scoped_rows = _allowlist_with_ancestors(scoped_rows, allowlist)
                else:
                    # No wrapper class (unregistered / non-mpy node): fall back
                    # to the denylist so we don't hide everything.
                    from mpynode._common.plugs.plug_filter import (
                        is_hidden_input_row,
                    )

                    scoped_rows = [
                        r for r in scoped_rows
                        if not is_hidden_input_row(r.short_name)
                    ]
            except Exception:
                # Best-effort polish; show all rows if resolution fails.
                pass

        # Children are appended via QTreeWidgetItem's parent-child ctor.
        for top in treeify(scoped_rows):
            self._addLockedSubtree(top, parent_item=None)

    def _show_framework_attrs(self) -> bool:
        """Read the artist's preference from optionVar.

        Default OFF (filter ON) -> matches Node Editor curation.
        Toggle persisted by the parent ``NDAttributesWidget``
        checkbox. ``cmds.optionVar`` is the cross-restart vehicle
        Maya itself uses for similar prefs."""
        try:
            from maya import cmds

            if cmds.optionVar(exists="mpynodeShowFrameworkAttrs"):
                return bool(cmds.optionVar(q="mpynodeShowFrameworkAttrs"))
        except Exception:
            pass
        return False

    def _addLockedSubtree(self, tree_node, parent_item):
        """Recursively render a ``TreeNode`` (and its children) as
        ``NDLockedAttrTreeItem`` QTreeWidgetItems. ``parent_item``
        is None at top level (-> addTopLevelItem) or another
        QTreeWidgetItem (-> nested child).

        also applies the connection-state visual convention
        to each inherited row (used to be user-added-only)."""
        if parent_item is None:
            item = NDLockedAttrTreeItem(None, row_spec=tree_node.row)
            self.addTopLevelItem(item)
        else:
            item = NDLockedAttrTreeItem(parent_item, row_spec=tree_node.row)
        # The item must already be in the tree, so this runs after add*Item.
        try:
            node_name = self._py_node.get_name() if self._py_node is not None else ""
            if node_name:
                item.apply_connection_state(node_name, self.ATTR_CATEGORY)
        except Exception:
            pass
        for child in tree_node.children:
            self._addLockedSubtree(child, parent_item=item)

    def _buildLockedItems(self) -> list:
        """Backward-compat shim: no longer calls this
        directly (the walker-driven path in ``refresh()`` replaces
        it), but the method is kept as part of the public surface
        for any external introspection that referenced it.
        Returns an empty list now."""
        return []

    # ------------------------------------------------------------------
    # Right-click context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        if self._py_node is None:
            return
        menu = QMenu(self)

        # Always-shown actions
        add_act = QAction(f"Add New {self.ATTR_CATEGORY.capitalize()}", menu)
        add_act.triggered.connect(lambda checked=False: self._show_add_attr_dlg())
        menu.addAction(add_act)

        selected = self._selected_user_items()
        if selected:
            del_act = QAction(
                f"Delete {self.ATTR_CATEGORY.capitalize()}{'s' if len(selected) > 1 else ''}",
                menu,
            )
            del_act.triggered.connect(lambda checked=False: self._delete_selected())
            menu.addAction(del_act)

            menu.addSeparator()
            connect_label = (
                f"Connect Attrs to {self.ATTR_CATEGORY.capitalize()}"
                if self.ATTR_CATEGORY == "input"
                else f"Connect {self.ATTR_CATEGORY.capitalize()} to Attrs"
            )
            connect_act = QAction(connect_label, menu)
            connect_act.triggered.connect(
                lambda checked=False: self._show_connect_dlg()
            )
            menu.addAction(connect_act)

            disconnect_act = QAction(
                f"Disconnect All {self.ATTR_CATEGORY.capitalize()}s", menu
            )
            disconnect_act.triggered.connect(
                lambda checked=False: self._disconnect_selected()
            )
            menu.addAction(disconnect_act)

            menu.addSeparator()
            set_color_act = QAction("Set Color\u2026", menu)
            set_color_act.triggered.connect(
                lambda checked=False: self._show_set_color_dlg()
            )
            menu.addAction(set_color_act)
            # Only show Clear if at least one selected has a custom color.
            if any((it.attr_meta or {}).get("ui_color") for it in selected):
                clear_color_act = QAction("Clear Color", menu)
                clear_color_act.triggered.connect(
                    lambda checked=False: self._clear_selected_colors()
                )
                menu.addAction(clear_color_act)

            # Sparse toggle (input ARRAY attrs only). OFF (default) = the
            # expression reads a dense gap-filled array; ON = only the
            # connected/set elements, compactly. Pure metadata edit -- plug,
            # connections and values are untouched.
            if self.ATTR_CATEGORY == "input":
                array_items = [
                    it for it in selected
                    if (it.attr_meta or {}).get("is_array")
                ]
                if array_items:
                    menu.addSeparator()
                    cur = bool(
                        (array_items[0].attr_meta or {}).get("sparse", False)
                    )
                    sp_act = QAction("Sparse", menu)
                    sp_act.setCheckable(True)
                    sp_act.setChecked(cur)
                    sp_act.toggled.connect(
                        lambda checked: self._toggle_sparse(checked)
                    )
                    menu.addAction(sp_act)

        menu.addSeparator()
        select_act = QAction("Select Node", menu)
        select_act.triggered.connect(lambda checked=False: self._select_node())
        menu.addAction(select_act)

        # Plugs wired outside the Designer don't auto-refresh, so offer a
        # one-click re-walk instead of close + re-pick the node.
        menu.addSeparator()
        refresh_act = QAction("Refresh Inputs + Outputs", menu)
        refresh_act.triggered.connect(
            lambda checked=False: self._refresh_both_trees()
        )
        menu.addAction(refresh_act)

        menu.exec_(event.globalPos()) if hasattr(menu, "exec_") else menu.exec(
            event.globalPos()
        )

    def _refresh_both_trees(self) -> None:
        """Rebuild this tree AND the sibling Input/Output
        tree. The parent NDAttributesWidget holds both via
        ``_input_tree`` / ``_output_tree``; we walk up to find it
        rather than carrying back-references on each tree."""
        try:
            self.refresh()
        except Exception:
            pass
        # Walk up the parent chain to find the NDAttributesWidget.
        parent = self.parent()
        while parent is not None:
            input_tree = getattr(parent, "_input_tree", None)
            output_tree = getattr(parent, "_output_tree", None)
            if input_tree is not None or output_tree is not None:
                for other in (input_tree, output_tree):
                    if other is None or other is self:
                        continue
                    try:
                        other.refresh()
                    except Exception:
                        pass
                return
            parent = parent.parent() if hasattr(parent, "parent") else None

    def _selected_user_items(self) -> list:
        return [it for it in self.selectedItems() if isinstance(it, NDUserAttrTreeItem)]

    # ------------------------------------------------------------------
    # Add / Delete / Connect / Disconnect
    # ------------------------------------------------------------------

    def _show_add_attr_dlg(self) -> None:
        if self._py_node is None:
            return
        # Persistent non-modal dialog: stays open between Adds and manages its
        # own undoable Add commands; we just refresh on each success. Cached
        # on self so it isn't GC'd.
        if not hasattr(self, "_add_dlg") or self._add_dlg is None:
            self._add_dlg = None
        # If a previous dialog is still alive, just bring it back.
        try:
            if self._add_dlg is not None:
                # Will throw if the underlying C++ widget was destroyed.
                self._add_dlg.objectName()
                self._add_dlg.show()
                self._add_dlg.raise_()
                self._add_dlg.activateWindow()
                return
        except (RuntimeError, AttributeError):
            self._add_dlg = None

        def _on_attr_added(name, attr_type, is_array, direction):
            # Refresh BOTH trees so the sibling sees a cross-direction add.
            parent = self.parent()
            if parent is not None and hasattr(parent, "refreshInputs"):
                parent.refreshInputs()
                parent.refreshOutputs()
            else:
                self.refresh()

        self._add_dlg = NDAddAttrDialog(
            self,
            self._py_node,
            initial_direction=self.ATTR_CATEGORY,
            on_attr_added=_on_attr_added,
        )
        self._add_dlg.show()
        self._add_dlg.raise_()
        self._add_dlg.activateWindow()

    def _delete_selected(self) -> None:
        items = self._selected_user_items()
        if not items:
            return
        names = [it.getCurrentName() for it in items]
        if not confirm_delete_node(self, names, entity="attribute"):
            return
        for name in names:
            try:
                run_undoable(
                    _DeleteAttrCommand(self._py_node, name, self.ATTR_CATEGORY)
                )
            except Exception as exc:
                QMessageBox.warning(self, "Delete Failed", f"{name}: {exc}")
        self.refresh()

    def _show_connect_dlg(self) -> None:
        items = self._selected_user_items()
        if not items or self._py_node is None:
            return
        # Operate on the FIRST selected item.
        item = items[0]
        attr_name = item.getCurrentName()
        target_plug = f"{self._py_node.get_name()}.{attr_name}"
        # Multi lets the dialog auto-distribute sources to next-available
        # indices.
        target_is_multi = bool(item.attr_meta.get("is_array", False))
        DialogClass = (
            NDConnectInputAttrDialog
            if self.ATTR_CATEGORY == "input"
            else NDConnectOutputAttrDialog
        )
        dlg = DialogClass(self, target_plug, target_is_multi=target_is_multi)
        accepted = dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()
        if not accepted:
            return
        chosen_plugs = dlg.getChosenPlugs()
        if not chosen_plugs:
            return

        # Multi-side index policy + target-array range (guarded so a duck-typed
        # fake dialog without the new getters still works).
        clobber = dlg.getClobber() if hasattr(dlg, "getClobber") else False
        range_text = dlg.getRangeText() if hasattr(dlg, "getRangeText") else ""

        # Compute (src, dst) pairs (handles multi index distribution).
        from mpynode.ui.dialogs.connect_attr import compute_connection_pairs

        if self.ATTR_CATEGORY == "input":
            # Sources -> our input. A SOURCE under a multi ancestor (e.g.
            # driver.worldMatrix) is expanded to concrete indexed plugs here,
            # then distributed over our input indices; a scalar takes the first.
            from mpynode.ui.dialogs.connect_attr import expand_source_plugs

            src_plugs, warnings = expand_source_plugs(chosen_plugs, range_text)
            if warnings:
                QMessageBox.warning(self, "Connect", "\n".join(warnings))
            if not src_plugs:
                return
            pairs = compute_connection_pairs(
                target_plug, target_is_multi, src_plugs, clobber=clobber
            )
        else:
            # Our output -> destinations. A destination under a multi ancestor
            # (polyColorPerVertex.vertexColor[i].vertexColorRGB) is auto-indexed
            # here: a scalar output fans across the target's elements, an array
            # output maps element-wise.
            from mpynode.ui.dialogs.connect_attr import (
                compute_output_connection_pairs,
                expand_dest_plugs,
            )

            dest_plugs, warnings = expand_dest_plugs(chosen_plugs, range_text)
            if warnings:
                QMessageBox.warning(
                    self, "Connect", "\n".join(warnings)
                )
            if not dest_plugs:
                return
            # MULTI output: allocate element indices from 0 when clobbering,
            # else skip only indices ALREADY wired as a source -- indices that
            # merely hold cached compute data are reusable.
            pairs = compute_output_connection_pairs(
                target_plug, target_is_multi, dest_plugs, clobber=clobber
            )

        force = dlg.getExtraFlag()
        # Clobber on a MULTI attr rebuilds from index 0: trim every existing
        # element (Maya won't shrink it on a plain disconnect) then wire the
        # new pairs, all in one undoable command.
        if clobber and target_is_multi and pairs:
            try:
                run_undoable(_ClobberMultiConnectCommand(target_plug, pairs))
            except Exception as exc:
                QMessageBox.warning(
                    self, "Connect Failed", f"{target_plug}\n\n{exc}"
                )
            self.refresh()
            return

        for src, dst in pairs:
            try:
                run_undoable(_ConnectAttrCommand(src, dst, force=force))
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Connect Failed",
                    f"{src} \u2192 {dst}\n\n{exc}",
                )
                self.refresh()  # reflect any partial connects before bailing
                return  # stop on first failure
        # _apply_connection_state only runs at construction, so rebuild to
        # update the per-row connected dot.
        self.refresh()

    def _disconnect_selected(self) -> None:
        items = self._selected_user_items()
        if not items or self._py_node is None:
            return
        for item in items:
            plug = f"{self._py_node.get_name()}.{item.getCurrentName()}"
            try:
                run_undoable(_DisconnectAllCommand(plug, self.ATTR_CATEGORY))
            except Exception as exc:
                QMessageBox.warning(self, "Disconnect Failed", str(exc))
        # Rebuild so the per-row connected dot clears.
        self.refresh()

    def _select_node(self) -> None:
        if self._py_node is None:
            return
        try:
            mc.select(self._py_node.get_name(), replace=True)
        except Exception:
            pass

    def _toggle_sparse(self, value: bool) -> None:
        """Flip the ``sparse`` read flag on the selected user ARRAY input attr(s).

        Routed through ``_SetSparseCommand`` (undoable; a pure metadata edit --
        the plug, connections, and values are untouched). Input arrays only."""
        if self._py_node is None or self.ATTR_CATEGORY != "input":
            return
        items = [
            it for it in self._selected_user_items()
            if (it.attr_meta or {}).get("is_array")
        ]
        if not items:
            return
        for it in items:
            try:
                run_undoable(
                    _SetSparseCommand(self._py_node, it.attr_name, value)
                )
            except Exception as exc:
                QMessageBox.warning(
                    self, "Set Sparse Failed", f"{it.attr_name}: {exc}"
                )
        self.refresh()

    # ------------------------------------------------------------------
    # Per-attr UI color
    # ------------------------------------------------------------------

    def _show_set_color_dlg(self) -> None:
        """Open QColorDialog and apply the picked color to selected attrs."""
        items = self._selected_user_items()
        if not items or self._py_node is None:
            return
        # Seed from the FIRST selected item's color, else a default.
        seed = (items[0].attr_meta or {}).get("ui_color") or "#80e650"
        try:
            initial = QColor(seed)
        except Exception:
            initial = QColor("#80e650")
        chosen = QColorDialog.getColor(initial, self, "Pick Attr Color")
        if not chosen.isValid():
            return
        hex_color = chosen.name()  # "#rrggbb"
        for it in items:
            try:
                run_undoable(
                    _SetAttrColorCommand(
                        self._py_node, it.attr_name, hex_color, self.ATTR_CATEGORY
                    )
                )
            except Exception as exc:
                QMessageBox.warning(self, "Set Color Failed", f"{it.attr_name}: {exc}")
        self.refresh()
        # Notify the script-editor highlighter.
        try:
            self.attrColorChanged.emit(self._py_node.get_name())
        except Exception:
            pass

    def _clear_selected_colors(self) -> None:
        items = self._selected_user_items()
        if not items or self._py_node is None:
            return
        for it in items:
            try:
                run_undoable(
                    _SetAttrColorCommand(
                        self._py_node, it.attr_name, None, self.ATTR_CATEGORY
                    )
                )
            except Exception as exc:
                QMessageBox.warning(
                    self, "Clear Color Failed", f"{it.attr_name}: {exc}"
                )
        self.refresh()
        # Same notification on clear.
        try:
            self.attrColorChanged.emit(self._py_node.get_name())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Inline rename (itemChanged)
    # ------------------------------------------------------------------

    def _on_item_changed(self, item, column: int) -> None:
        if self._refreshing or self._py_node is None:
            return
        if not isinstance(item, NDUserAttrTreeItem):
            return
        # The label format is "name: type" (scalar) / "name[]: type" /
        # "name[]: type (sparse)" (array). Extract the new name part.
        new_label = item.text(0).strip()
        if ": " in new_label:
            new_label = new_label.split(": ", 1)[0]
        # Strip the array marker suffix ("[]"). A validated attr name never
        # contains "[", so splitting on it yields the bare name.
        new_name = new_label.split("[", 1)[0].strip()

        old_name = item.attr_name
        if not new_name or new_name == old_name:
            self._restore_label(item)
            return

        existing = set(
            (getattr(self._py_node, self.LIST_ATTR_FUNC_NAME)() or {}).keys()
        )
        existing.discard(old_name)  # ok to "rename" to its current name
        ok, err = validate_attr_name(
            new_name, existing, node_name=self._py_node.get_name()
        )
        if not ok:
            QMessageBox.warning(self, "Invalid Name", err)
            self._restore_label(item)
            return

        try:
            run_undoable(
                _RenameAttrCommand(
                    self._py_node, old_name, new_name, self.ATTR_CATEGORY
                )
            )
        except Exception as exc:
            QMessageBox.warning(self, "Rename Failed", str(exc))
            self._restore_label(item)
            return

        # Rebuild so the label reformats and attr_name is current.
        self.refresh()
        # The rename command rewrote the node's expression sources
        # (self.<old> -> self.<new>), so a non-dirty editor must re-pull.
        try:
            self.attrRenamed.emit(self._py_node.get_name())
        except Exception:
            pass

    def _restore_label(self, item) -> None:
        self._refreshing = True
        try:
            item.setText(0, item._format_label(item.attr_name, item.attr_meta))
        finally:
            self._refreshing = False


class NDOutputAttrTree(NDInputAttrTree):
    """Output-attr tree (same as input but other direction)."""

    ATTR_CATEGORY = "output"
    LIST_ATTR_FUNC_NAME = "get_output_attr_map"
    HEADER_LABEL = "Output"
    HEADER_COLOR = "#e0a34e"  # amber -- output


# ===========================================================================
# Composite widget
# ===========================================================================


class NDAttributesWidget(QWidget):
    """Attributes tab content: header label + Input tree + Output tree."""

    # Bubbled up so the designer can live-refresh the script editor's
    # syntax-highlighter var-color map.
    attrColorChanged = Signal(str)  # node name
    # Bubbled up so the designer can reload the open editor tab after a
    # user-attr rename.
    attrRenamed = Signal(str)  # node name

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        header_row = QHBoxLayout()
        self._header = QLabel("(no node selected)", self)
        header_row.addWidget(self._header, 1)
        self._show_framework_chk = QCheckBox("Show framework attrs", self)
        self._show_framework_chk.setToolTip(
            "When OFF (default), hide framework / Maya-base attrs "
            "(matches the Node Editor's curated view). When ON, "
            "show every plug (raw walk_plug_tree dump). State "
            "persists across Maya restarts."
        )
        try:
            from maya import cmds

            current = bool(cmds.optionVar(q="mpynodeShowFrameworkAttrs")) \
                if cmds.optionVar(exists="mpynodeShowFrameworkAttrs") \
                else False
        except Exception:
            current = False
        self._show_framework_chk.setChecked(current)
        self._show_framework_chk.toggled.connect(
            self._on_show_framework_toggled
        )
        header_row.addWidget(self._show_framework_chk, 0)
        layout.addLayout(header_row)
        self._input_tree = NDInputAttrTree(self)
        self._output_tree = NDOutputAttrTree(self)
        layout.addWidget(self._input_tree)
        layout.addWidget(self._output_tree)
        # Forwarded so the designer can refresh the highlighter without a
        # full node-load round-trip.
        try:
            self._input_tree.attrColorChanged.connect(self.attrColorChanged)
            self._output_tree.attrColorChanged.connect(self.attrColorChanged)
            self._input_tree.attrRenamed.connect(self.attrRenamed)
            self._output_tree.attrRenamed.connect(self.attrRenamed)
        except Exception:
            pass

    def _on_show_framework_toggled(self, on: bool) -> None:
        """Persist the toggle via optionVar + refresh
        both trees so the filtered view updates immediately."""
        try:
            from maya import cmds

            cmds.optionVar(iv=("mpynodeShowFrameworkAttrs", 1 if on else 0))
        except Exception:
            pass
        try:
            self._input_tree.refresh()
        except Exception:
            pass
        try:
            self._output_tree.refresh()
        except Exception:
            pass

    def refresh(self, py_node):
        if py_node is None:
            self._header.setText("(no node selected)")
        else:
            self._header.setText(py_node.get_name())
        self._input_tree.setNode(py_node)
        self._output_tree.setNode(py_node)

    def refreshInputs(self):
        self._input_tree.refresh()

    def refreshOutputs(self):
        self._output_tree.refresh()
