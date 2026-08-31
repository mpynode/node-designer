"""Variables panel widget.

The Variables panel renders the per-instance USER stored vars as TWO
stacked sections inside one tree:

* **Persistent** -- ``self.X`` vars saved with the scene (registered in
  ``_storedVarNames``).
* **Temporary** -- ``self.X`` vars that live this session only (in the
  store but not registered); re-initialised on the next file load /
  import.

Both are editable in place: + / - / Refresh + double-click rename /
value edit; right-click promotes a var between the two tiers. All write
ops route through ``_BaseCommand`` subclasses for Ctrl+Z support. Both
sections start expanded.

The Properties / State surface (a wrapper's ``INTERNAL_API_SLOTS`` --
non-plug API state marshalled into the user-expression namespace) is no
longer rendered here; it moved to the Framework tab, which reuses this
module's data collectors (``collect_internal_api_rows`` / ``_dir_label``
/ ``NDPlugRowItem``).
"""

from __future__ import annotations

import ast
import keyword

from mpynode._base.commands import (
    _AddStoredVarCommand,
    _AddTemporaryVarCommand,
    _RemoveStoredVarCommand,
    _RenameStoredVarCommand,
    _SetPersistentCommand,
    _SetStoredVarCommand,
    run_undoable,
)
from mpynode._common.interface.reserved_names import check_reserved_name
from mpynode._common.storedvars.internal_vars_helper import (
    get_internal_vars_schema,
    get_solver_context_snapshot_dict,
)
from mpynode.ui.dialogs.confirm import confirm_delete_node
from mpynode.ui.widgets.watch import _format_value as _fmt_value
from mpynode.ui.widgets.image_preview import (
    ImagePreviewDelegate,
    WaveformPlayer,
    attach_value,
    cleanup_media_widgets,
    is_audio_item,
    is_previewable_item,
    is_showing_image,
    is_showing_waveform,
    refresh_media_widget,
    render_waveform_pref_on,
    set_image_view,
    set_waveform_view,
    toggle_value_mode,
    toggle_waveform_view,
)
from mpynode.ui.qt_wrapper import (
    QBrush,
    QCheckBox,
    QColor,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Warn before embedding a media blob larger than this into a PERSISTENT var:
# persistent vars are base64-embedded into the scene file on every save, so a
# large one bloats the .ma/.mb. Temporary vars (session-only) skip the warning.
_MEDIA_PERSIST_WARN_BYTES = 5 * 1024 * 1024


# Reserved names users can't pick (clash with Python or our compute glue).
_PY_BUILTINS = frozenset(
    dir(__builtins__)
    if isinstance(__builtins__, type(__builtins__))
    else __builtins__.__dict__
)
_RESERVED = frozenset(keyword.kwlist) | _PY_BUILTINS | {"self"}

# Section header labels, pinned by tests. The INTERNAL_API_SLOTS surface was
# renamed "Internal" -> "API" -> "Properties"; the constant NAME stays
# SECTION_INTERNAL for continuity.
SECTION_INTERNAL = "Properties"
# self.X vars saved with the scene (registered in ``_storedVarNames``).
SECTION_PERSISTENT = "Persistent"
# self.X vars in the store but NOT registered: they live for this session
# only and are re-initialised on the next file load / import.
SECTION_TEMPORARY = "Temporary"

# A Unicode glyph keeps us off the Qt-version-specific standardIcon paths --
# no built-in lock icon is portable across PySide2 + PySide6 + Maya themes.
_LOCK_BADGE = "\U0001f512 "  # 🔒


def validate_var_name(
    name: str, existing: set[str], node_name: str | None = None
) -> tuple[bool, str]:
    """Return (is_valid, error_message). Empty error means valid.

    ``node_name`` is optional: pass it and the framework reserved-name
    resolver is consulted too, so the panel refuses a colliding name up
    front with the SAME sentence the store's guard would raise later.
    """
    if not name:
        return False, "Name is required"
    if name in existing:
        return False, f"A stored variable named {name!r} already exists"
    if name[0].isdigit():
        return False, "Name cannot start with a digit"
    if not all(ch.isalnum() or ch == "_" for ch in name):
        return False, "Name must be alphanumeric (with optional underscores)"
    if name in _RESERVED:
        return False, f"{name!r} is a reserved Python keyword/builtin"
    if node_name is not None:
        reason = check_reserved_name(name, node_name=node_name)
        if reason:
            return False, reason
    return True, ""


def parse_value_text(text: str):
    """Parse a Python-literal string into a value.

    Uses ``ast.literal_eval`` for safety \u2014 supports numbers, strings,
    lists, tuples, dicts, sets, bool, None. Raises ValueError on bad
    input. Empty string \u2192 None.
    """
    text = (text or "").strip()
    if not text:
        return None
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"{text!r} is not a valid Python literal: {exc}")


_VALUE_FONT = None


def _value_font():
    """Lazily-built monospace font for the Value column so multi-dim
    numpy arrays column-align (mirrors the Watch tab)."""
    global _VALUE_FONT
    if _VALUE_FONT is None:
        try:
            from mpynode.ui.qt_wrapper import QFont

            f = QFont("Courier")
            f.setStyleHint(QFont.Monospace)
            _VALUE_FONT = f
        except Exception:
            _VALUE_FONT = False
    return _VALUE_FONT or None


class NDVariableTreeItem(QTreeWidgetItem):
    """Tree item for a single USER stored var. Editable in name + value columns.

    v3: now a 3-column shape (Variable | Dir | Value).
    User vars don't have an IN/OUT direction — col 1 is left empty.
    The inline-edit handler ignores edits to col 1 so the empty cell
    stays empty.
    """

    EDITABLE_FLAGS = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def __init__(self, parent, var_name: str, value):
        super().__init__(parent)
        self.var_name = var_name
        self.var_value = value
        self.is_internal = False
        # Session-only rows (store key not in the persistent registry) are
        # display-only + muted; editing would otherwise auto-register them.
        self.is_session = False
        # Mirrors the persistent checkbox state (for toggle detection).
        self._persistent = False
        self.setFlags(self.EDITABLE_FLAGS)
        self.setText(0, var_name)
        # Dir is empty for user vars -- they're inherently writeable.
        self.setText(1, "")
        # Image-previewable values get an inline thumbnail + a right-click
        # source<->image toggle; everything else uses the Watch tab's
        # numpy-aware text formatter. Monospace regardless, so the source
        # view column-aligns multi-dim arrays.
        attach_value(self, 2, value, _fmt_value(value))
        _f = _value_font()
        if _f is not None:
            try:
                self.setFont(2, _f)
            except Exception:
                pass
        # Top-align so the name lines up with the FIRST line of a
        # multi-line value instead of being centered.
        for _c in range(3):
            self.setTextAlignment(_c, Qt.AlignLeft | Qt.AlignTop)


# The plug-tree walking helpers now live in ``ui.widgets.plug_tree_walker``.
# Re-exported here so existing callers keep working unmodified.
from mpynode.ui.widgets.plug_tree_walker import (  # noqa: F401, E402
    PLUG_BROWSER_BLACKLIST,
    collect_plug_rows,
    collect_plug_tree,
    read_plug_value_text,
)


def _format_slot_value(value, max_len: int = 80) -> str:
    """Render an INTERNAL_API_SLOTS value as a short text string
    suitable for a single tree-row cell.

    Handles common shapes encountered across wrappers:
      * ``None``                 -> "None"
      * ``numpy.ndarray``        -> "ndarray(shape) dtype" (no element dump)
      * ``OpenMaya.MMatrix``     -> "MMatrix(<row0>...)" truncated
      * ``OpenMaya.MVector/MPoint`` -> "MVector(x, y, z)"
      * ``list`` / ``tuple``     -> "list[N]" / "tuple[N]" with first 3 items
      * everything else          -> ``repr(value)`` truncated to ``max_len``

    Truncation always preserves the leading characters so the row
    column stays scannable.
    """
    if value is None:
        return "None"
    # Shape + dtype, NOT contents (may be huge).
    try:
        import numpy as _np
        if isinstance(value, _np.ndarray):
            return f"ndarray{tuple(value.shape)} {value.dtype}"
    except Exception:
        pass
    # OpenMaya matrix / vector: compact summaries.
    try:
        import maya.api.OpenMaya as _om2
        if isinstance(value, _om2.MMatrix):
            row0 = ", ".join(f"{value[i]:.3g}" for i in range(4))
            return f"MMatrix(row0=[{row0}]...)"
        if isinstance(value, (_om2.MVector, _om2.MPoint)):
            return f"{type(value).__name__}({value.x:.3g}, {value.y:.3g}, {value.z:.3g})"
    except Exception:
        pass
    # list / tuple: show length + first 3 items.
    if isinstance(value, (list, tuple)):
        n = len(value)
        cls = type(value).__name__
        if n == 0:
            return f"{cls}[0]"
        head = ", ".join(repr(x) for x in value[:3])
        suffix = ",..." if n > 3 else ""
        text = f"{cls}[{n}]: {head}{suffix}"
        if len(text) > max_len:
            text = text[: max_len - 3] + "..."
        return text
    # Fallback: repr + truncate.
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__} repr() raised>"
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text


def collect_internal_api_rows(node_name):
    """Return ``[(slot_name, direction, value_text),...]`` for the
    per-wrapper ``INTERNAL_API_SLOTS`` declaration -- with LIVE values +
    the extended schema (direction tag + type hint).

    ``direction`` is the slot's raw ``"read"`` / ``"write"`` string (or
    ``""`` for legacy flat-string slots that declare none). The widget
    renders it in the 'Dir' column via:func:`_dir_label`; it is NO LONGER
    baked into ``value_text`` as a ``"READ |"`` / ``"WRITE |"`` prefix.

    upgrade: rather than the static ``<api>`` placeholder we
    Resolves the wrapper instance for
    the node and reads each slot via ``getattr(wrapper, slot)``.

    upgrade: when the wrapper declares ``INTERNAL_API_SLOTS``
    as ``(("name", "read"|"write", "type hint"),...)`` the value
    column carries both the live value AND the type-hint annotation
    so the Variables-API panel reflects the full I/O contract.
    Legacy flat-string declarations (``("name",...)``) still work
    -- they render with direction/type_hint omitted.

    Failure modes are non-fatal:
      * Wrapper class not registered   -> ``"<wrapper unavailable>"``.
      * ``getattr`` raises (non-Attr)  -> ``"<error: ExceptionRepr>"``.
      * Slot has no matching wrapper property (a write-only compute
        target, or a read slot the wrapper doesn't surface) -> the
        type-hint schema alone (empty cell if it declares none). NOT an
        error and NOT a redundant "(write-only)"/"no wrapper property"
        tag -- the 'Dir' column already conveys read/write.
    """
    try:
        from mpynode.ui.widgets.plug_tree_walker import (
            _internal_api_slot_specs_for,
            _wrapper_instance_for,
        )
        specs = _internal_api_slot_specs_for(node_name)
    except Exception:
        return []
    # Do NOT early-return on empty specs. The blessed API-method rows appended
    # below are INDEPENDENT of slots and must render for slot-less wrappers --
    # e.g. mPySkinCluster (INTERNAL_API_SLOTS == ()) whose blessed skin methods
    # still belong here. A prior `if not specs: return []` swallowed them.
    rows = []
    # Only needed to read live slot values, so skip it when there are none.
    wrapper = _wrapper_instance_for(node_name) if specs else None

    # Declaration order, not alphabetical: schemas read top-down.
    for name, direction, type_hint in specs:
        if wrapper is None:
            rows.append((name, direction,
                         _annotate_row("<wrapper unavailable>", type_hint)))
            continue
        try:
            raw = getattr(wrapper, name)
        except AttributeError:
            # No Python property for this slot is the expected I/O contract,
            # NOT an error: write slots are COMPUTE-tab targets. The 'Dir'
            # column already conveys read/write, so show the type-hint schema
            # alone rather than a redundant "(write-only)" tag.
            rows.append((name, direction, _annotate_row("", type_hint)))
            continue
        except Exception as exc:
            rows.append((name, direction, _annotate_row(
                f"<error: {type(exc).__name__}: {exc}>", type_hint)))
            continue
        rows.append((name, direction,
                     _annotate_row(_format_slot_value(raw), type_hint)))
    # Blessed API methods: the signature goes in the value cell (no live
    # value) and the docstring rides along for the tooltip.
    try:
        from mpynode.ui.widgets.plug_tree_walker import (
            _internal_api_method_specs_for,
        )
        for _spec in _internal_api_method_specs_for(node_name):
            rows.append((_spec.name, "method",
                         _annotate_row("", "%s -- %s" % (_spec.sig, _spec.doc))))
    except Exception:
        pass
    return rows


# Raw-direction token -> 'Dir'-column word. Plain uppercase text; short
# letter badges were tried and read poorly.
_DIR_WORD = {
    "read": "READ", "write": "WRITE", "readwrite": "READWRITE",
    "method": "METHOD",
}


def _dir_label(direction) -> str:
    """Map a slot's raw direction to its 'Dir'-column word (plain uppercase
    text rendered directly in the column):

      "read"      -> "READ"
      "write"     -> "WRITE"
      "readwrite" -> "READWRITE"
      "method"    -> "METHOD"
      "" / None   -> ""   (legacy directionless slot -> neutral, blank)
    """
    if not direction:
        return ""
    return _DIR_WORD.get(direction, direction.upper())


def _annotate_row(value_text: str, type_hint: str) -> str:
    """Compose the Variables-API value-column text from the live-value
    string + type-hint annotation. The read/write direction is rendered
    separately in the 'Dir' column (see:func:`_dir_label`), NOT prefixed
    into the value text.

    Either part may be empty (a slot with no live value shows the type-hint
    schema alone; a slot with no type hint shows the value alone) -- the
    join never leaves a dangling ' -- '.

    Format examples:
      "4.0 -- float -- scene time in frames"
      "ndarray(48, 3) float64 -- np.ndarray(N, 3)..."
      "np.ndarray(N, 3)..."           (no live value -- schema only)
      "None"                          (no type hint -- legacy schema)
    """
    if value_text and type_hint:
        return f"{value_text} -- {type_hint}"
    return value_text or type_hint


def _wrap_tooltip(text: str) -> str:
    """Wrap arbitrary value/description text as a RICH-TEXT tooltip so Qt
    word-wraps long lines. A plain-text tooltip renders a long API
    description (e.g. mPyTransform's ``local_matrix`` hint) as one giant
    unwrapped line that runs off-screen; wrapping in ``<qt>...</qt>`` marks
    it rich text, which Qt auto-word-wraps to a sensible width.

    HTML metacharacters are escaped so ``<``/``>``/``&`` in the text (e.g.
    ``world @ inv(parent)`` is fine, but ``<connected>`` would otherwise be
    eaten as a tag) render literally. Returns ``""`` for empty text so the
    caller can skip setting a tooltip.
    """
    if not text:
        return ""
    esc = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"<qt>{esc}</qt>"


class NDPlugRowItem(QTreeWidgetItem):
    """Tree item for a single plug-tree entry surfaced in
    the variables widget API section.

    Display-only; reads the live plug value at populate time. Uses the
    3-column (name / dir / value) layout so existing column widths still
    apply. Now consumed by the Framework tab (the Variables tab no longer
    renders a Properties section)."""

    DISPLAY_FLAGS = Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def __init__(self, parent, plug_name: str, direction: str, value_text: str):
        super().__init__(parent)
        self.plug_name = plug_name
        self.direction = direction
        self.value_text = value_text
        self.is_internal = True  # treated as read-only by the widget
        self.setFlags(self.DISPLAY_FLAGS)
        self.setText(0, plug_name)
        self.setText(1, direction)
        self.setTextAlignment(1, Qt.AlignCenter)
        self.setText(2, value_text)
        # Long API descriptions overflow the Value column, so give the whole
        # row a word-wrapped rich-text tooltip of the full value.
        tip = _wrap_tooltip(value_text)
        if tip:
            for _c in range(3):
                self.setToolTip(_c, tip)


class NDVariablesWidget(QWidget):
    """Variables tab -- Persistent + Temporary user-var sections
    (both editable). The Properties/State surface moved to the
    Framework tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._py_node = None
        # Suppress itemChanged events while we're rebuilding the tree
        # programmatically (otherwise refresh() triggers spurious renames).
        self._refreshing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._header = QLabel("(no node selected)", self)
        layout.addWidget(self._header)

        # + / - only act on User entries; Internal entries are schema-only.
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+", self)
        self._add_btn.setFixedWidth(32)
        self._add_btn.setToolTip("Add a stored variable (User)")
        self._del_btn = QPushButton("\u2212", self)
        self._del_btn.setFixedWidth(32)
        self._del_btn.setToolTip("Remove the selected User variable(s)")
        self._refresh_btn = QPushButton("Refresh", self)
        self._refresh_btn.setToolTip("Re-read variables from the node")
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._del_btn)
        btn_row.addWidget(self._refresh_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self._tree = QTreeWidget(self)
        # Shift-click a section header (Persistent / Temporary) to
        # recursively expand or collapse that section's subtree.
        from mpynode.ui.widgets.tree_expand import (
            install_shift_click_expand_all,
        )
        install_shift_click_expand_all(self._tree)
        # Drops land on User section rows only; read-only API rows reject
        # them. The highlight is painted from an event filter (see below).
        try:
            self._tree.setAcceptDrops(True)
            self._tree.setDropIndicatorShown(True)
        except Exception:
            pass
        # Drop-highlight state (mirrors NDInputAttrTree).
        self._drop_highlight_item = None
        self._drop_highlight_prev_brush = None
        # New-var flash: the self.X var set + node from the last refresh, so
        # a var that just appeared can be selected, scrolled to and flashed.
        self._known_node_name = None
        self._known_var_names = set()
        # Per-variable "show as image" choices from the right-click toggle.
        # Survive refreshes; cleared when the active node changes.
        self._image_view_modes: dict = {}
        # Same, for the "show as waveform" choice on audio (WAV/PCM) vars.
        self._waveform_view_modes: dict = {}
        # Shared audio player for waveform cells (lazy; created on first play).
        self._waveform_player = None
        # Event filter, so the drop target can be painted without
        # subclassing QTreeWidget.
        try:
            self._tree.installEventFilter(self)
        except Exception:
            pass
        # Dir carries each Internal slot's direction word (see _dir_label);
        # blank for user vars and for legacy directionless slots. Native
        # column text stays readable at any DPI / theme, with no sprite-icon
        # downscaling, and var names auto-align in col 0.
        self._tree.setHeaderLabels(["Variable", "Dir", "Value"])
        self._tree.setColumnCount(3)
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        # Variable column auto-fits; Value stretches.
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        # Fixed, not ResizeToContents, which hugs ``WRITE`` exactly and reads
        # cramped. 82 px on the default Maya font fits ``READWRITE`` with
        # padding to spare, and stops the Variable column wobbling when the
        # longest var name changes width.
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self._tree.setColumnWidth(1, 82)
        layout.addWidget(self._tree)

        # Dir is a read-only tag, but Persistent rows carry ItemIsEditable,
        # which would make the cell editable -- so open no editor.
        from mpynode.ui.qt_wrapper import QStyledItemDelegate as _QSID

        class _NoEditDelegate(_QSID):
            def createEditor(self, parent, option, index):
                return None

        self._dir_noedit_delegate = _NoEditDelegate(self._tree)
        self._tree.setItemDelegateForColumn(1, self._dir_noedit_delegate)

        # Frameless + flush so the editor OVERLAPS the existing name, and
        # pinned to the TOP of a possibly tall multi-line row so it lines up
        # with the top-aligned name instead of dropping to the center.
        from mpynode.ui.qt_wrapper import QLineEdit as _QLE

        class _RenameDelegate(_QSID):
            def createEditor(self, parent, option, index):
                ed = _QLE(parent)
                try:
                    ed.setFrame(False)
                    ed.setTextMargins(0, 0, 0, 0)
                except Exception:
                    pass
                return ed

            def updateEditorGeometry(self, editor, option, index):
                r = option.rect
                try:
                    h = editor.sizeHint().height()
                    if h <= 0 or h > r.height():
                        h = r.height()
                    editor.setGeometry(r.x(), r.y(), r.width(), h)
                except Exception:
                    editor.setGeometry(r)

        self._rename_delegate = _RenameDelegate(self._tree)
        self._tree.setItemDelegateForColumn(0, self._rename_delegate)

        # PIL-image vars render as scaled square thumbnails; other rows fall
        # through to default text. The delegate tracks the column width on
        # resize (relayout only -- it never writes widths).
        self._img_delegate = ImagePreviewDelegate(self._tree, value_col=2)
        self._tree.setItemDelegateForColumn(2, self._img_delegate)

        # Reused across refreshes: children are cleared but the headers stay,
        # so expanded state survives.
        self._internal_section: QTreeWidgetItem | None = None
        self._persistent_section: QTreeWidgetItem | None = None
        self._temporary_section: QTreeWidgetItem | None = None

        self._add_btn.clicked.connect(self._on_add_clicked)
        self._del_btn.clicked.connect(self._on_remove_clicked)
        self._refresh_btn.clicked.connect(self.refresh)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        # Live-update values when a display pref changes (rounding digits,
        # scientific notation, full arrays).
        try:
            from mpynode.ui.preferences import register_change_listener

            register_change_listener(self._on_pref_changed)
        except Exception:
            pass

    def setPyNode(self, py_node):
        # New node -> remembered per-variable image choices no longer apply.
        if py_node is not self._py_node:
            self._image_view_modes = {}
            self._waveform_view_modes = {}
            # Release the player + temp .wav but KEEP the wrapper object --
            # dispose() leaves it reusable, and any surviving reused cell
            # still points at it.
            if self._waveform_player is not None:
                try:
                    self._waveform_player.dispose()
                except Exception:
                    pass
        self._py_node = py_node
        self.refresh()

    def _apply_image_view_modes(self) -> None:
        """Re-apply the user's remembered source<->image choices to the
        freshly-rebuilt rows (keyed by var name). Walks all section rows."""
        if not self._image_view_modes:
            return

        def _walk(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                vn = getattr(child, "var_name", None)
                if (
                    vn is not None
                    and vn in self._image_view_modes
                    and is_previewable_item(child, 2)
                ):
                    set_image_view(child, 2, self._image_view_modes[vn])
                    try:
                        idx = self._tree.indexFromItem(child, 2)
                        self._img_delegate.sizeHintChanged.emit(idx)
                    except Exception:
                        pass
                _walk(child)

        try:
            _walk(self._tree.invisibleRootItem())
            self._tree.viewport().update()
        except Exception:
            pass

    def _ensure_waveform_player(self):
        """Lazily create the shared audio player for waveform cells."""
        if self._waveform_player is None:
            self._waveform_player = WaveformPlayer(self)
        return self._waveform_player

    def _apply_media_views(self) -> None:
        """Re-apply remembered 'show as waveform' choices and (re)install the
        per-row media widgets (animated GIF / interactive waveform) on the
        freshly-built rows. Walks all section rows. Pure-cosmetic + guarded so
        it can never break the build."""
        wave_pref = render_waveform_pref_on()
        player = self._ensure_waveform_player() if wave_pref else None

        def _walk(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                vn = getattr(child, "var_name", None)
                if (wave_pref and vn is not None
                        and self._waveform_view_modes.get(vn)
                        and is_audio_item(child, 2)):
                    set_waveform_view(child, 2, True)
                try:
                    refresh_media_widget(self._tree, child, 2, player)
                except Exception:
                    pass
                _walk(child)

        try:
            _walk(self._tree.invisibleRootItem())
            self._tree.viewport().update()
        except Exception:
            pass

    _DISPLAY_PREF_KEYS = (
        "display_round_enabled",
        "display_round_digits",
        "watch_suppress_scientific",
        "watch_threshold_inf",
        "variables_image_preview_px",
        "variables_animate_gif",
        "variables_render_waveform",
    )

    def _on_pref_changed(self, key, value):
        """Re-render values when a display pref changes. Self-unregisters
        once the widget's C++ side has been destroyed."""
        if key not in self._DISPLAY_PREF_KEYS:
            return
        try:
            self.refresh()
        except RuntimeError:
            try:
                from mpynode.ui.preferences import unregister_change_listener

                unregister_change_listener(self._on_pref_changed)
            except Exception:
                pass

    def refresh(self):
        prev_node = self._known_node_name
        prev_names = self._known_var_names
        new_names = set()
        self._refreshing = True
        try:
            # clear() leaves item widgets alive on the viewport with their
            # timers running, so stop animated-GIF movies first.
            cleanup_media_widgets(self._tree)
            self._tree.clear()
            self._internal_section = None
            self._persistent_section = None
            self._temporary_section = None
            if self._py_node is None:
                self._header.setText("(no node selected)")
                self._set_buttons_enabled(False)
                self._known_node_name = None
                self._known_var_names = set()
                return
            cur_node = self._py_node.get_name()
            self._header.setText(f"Variables: {cur_node}")
            self._set_buttons_enabled(True)

            # Always present, even when empty. Only the two USER-var tiers
            # render here; Properties moved to the Framework tab.
            self._persistent_section = self._make_section_header(
                SECTION_PERSISTENT
            )
            self._temporary_section = self._make_section_header(
                SECTION_TEMPORARY
            )

            # Right-click a row to move it between the two tiers.
            self._populate_persistent_section(self._persistent_section)
            self._populate_temporary_section(self._temporary_section)

            # Both sections expanded by default.
            self._tree.expandItem(self._persistent_section)
            self._tree.expandItem(self._temporary_section)

            # Fresh rows default to source view, so without this a chosen
            # image would revert to its byte/array repr on every refresh.
            self._apply_image_view_modes()
            # Same for waveform choices + the per-row media widgets.
            self._apply_media_views()

            # Snapshot the var set to detect what's NEW next refresh. Only
            # flash within the SAME node -- a switch shouldn't flash all.
            data, _reg = self._stored_data_and_registry()
            cur_names = set((data or {}).keys())
            if cur_node == prev_node:
                new_names = cur_names - prev_names
            self._known_node_name = cur_node
            self._known_var_names = cur_names
        finally:
            self._refreshing = False

        if new_names:
            self._flash_new_vars(new_names)

    # The drop-highlight yellow, more transparent so it reads as transient.
    _FLASH_RGBA = (255, 204, 0, 110)

    def _flash_new_vars(self, new_names) -> None:
        """Select + scroll to + briefly highlight rows whose var appeared
        since the last refresh (e.g. a self.X written by the expression
        and surfaced on Save). Purely cosmetic discoverability."""
        from mpynode.ui.qt_wrapper import QBrush, QColor, QTimer

        items = []
        for sec in (self._persistent_section, self._temporary_section):
            if sec is None:
                continue
            for i in range(sec.childCount()):
                ch = sec.child(i)
                if (
                    isinstance(ch, NDVariableTreeItem)
                    and ch.var_name in new_names
                ):
                    items.append(ch)
        if not items:
            return
        first = items[0]
        try:
            self._tree.setCurrentItem(first)
            self._tree.scrollToItem(first)
        except Exception:
            pass
        r, g, b, a = self._FLASH_RGBA
        brush = QBrush(QColor(r, g, b, a))
        # setBackground emits itemChanged, so block signals or the inline
        # edit handler misfires on a purely-cosmetic paint.
        self._tree.blockSignals(True)
        try:
            for it in items:
                for col in range(3):
                    it.setBackground(col, brush)
        finally:
            self._tree.blockSignals(False)

        def _clear():
            try:
                self._tree.blockSignals(True)
            except Exception:
                return
            try:
                for it in items:
                    try:
                        for col in range(3):
                            it.setBackground(col, QBrush())
                    except Exception:
                        pass
            finally:
                try:
                    self._tree.blockSignals(False)
                except Exception:
                    pass

        try:
            QTimer.singleShot(1400, _clear)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Section building
    # ------------------------------------------------------------------

    def _make_section_header(self, label: str) -> QTreeWidgetItem:
        """Create a non-editable, non-selectable section header row."""
        item = QTreeWidgetItem(self._tree)
        item.setText(0, label)
        item.setFlags(Qt.ItemIsEnabled)
        # Span all columns so the header text doesn't drive col-0 sizing.
        item.setFirstColumnSpanned(True)
        return item

    # ------------------------------------------------------------------
    # helpers (delegate to module-level implementations)
    # ------------------------------------------------------------------

    def _collect_node_name(self):
        try:
            return self._py_node.get_name()
        except Exception:
            return ""

    def _stored_data_and_registry(self):
        """Return ``(data, registered)`` for the active node: the live
        store dict + the set of names declared persistent."""
        get_stored = getattr(self._py_node, "get_variables", None)
        if get_stored is None:
            return None, set()
        try:
            data = get_stored() or {}
        except Exception:
            data = {}
        try:
            from mpynode._common.storedvars.stored_vars_api import get_variable_names

            registered = set(get_variable_names(self._collect_node_name()))
        except Exception:
            registered = set()
        return data, registered

    def _populate_persistent_section(self, parent: QTreeWidgetItem) -> None:
        """Persistent ``self.X`` vars -- saved with the scene (registered
        in ``_storedVarNames``). Editable; a registered name shows even
        before it has a value."""
        data, registered = self._stored_data_and_registry()
        if data is None:
            placeholder = QTreeWidgetItem(parent)
            placeholder.setText(0, "(node has no stored-var support)")
            placeholder.setFlags(Qt.ItemIsEnabled)
            placeholder.setFirstColumnSpanned(True)
            return
        names = sorted(registered)
        if not names:
            placeholder = QTreeWidgetItem(parent)
            placeholder.setText(
                0, "(none -- right-click a Temporary var to promote)"
            )
            placeholder.setFlags(Qt.ItemIsEnabled)
            placeholder.setFirstColumnSpanned(True)
            return
        for name in names:
            item = NDVariableTreeItem(parent, name, data.get(name))
            item.is_session = False
            item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
            )
            item.setToolTip(0, "Persistent \u2014 saved with the scene")

    def _populate_temporary_section(self, parent: QTreeWidgetItem) -> None:
        """Temporary ``self.X`` vars -- live this session only (in the
        store but not registered), re-initialised on the next load.
        Display-only + muted; right-click to make one persistent."""
        data, registered = self._stored_data_and_registry()
        if data is None:
            return
        names = sorted(
            k for k in data.keys()
            if k not in registered and not k.startswith("_")
        )
        if not names:
            placeholder = QTreeWidgetItem(parent)
            placeholder.setText(0, "(none yet -- written on compute)")
            placeholder.setFlags(Qt.ItemIsEnabled)
            placeholder.setFirstColumnSpanned(True)
            return
        muted = QBrush(QColor(150, 150, 150, 150))
        for name in names:
            item = NDVariableTreeItem(parent, name, data[name])
            item.is_session = True
            # A temporary var's value is owned by the expression, and an
            # inline edit would auto-register it.
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setToolTip(
                0,
                "Session-only \u2014 not saved; right-click to make persistent",
            )
            for col in range(3):
                item.setForeground(col, muted)

    def _set_buttons_enabled(self, on: bool) -> None:
        self._add_btn.setEnabled(on)
        self._del_btn.setEnabled(on)
        self._refresh_btn.setEnabled(on)

    # ------------------------------------------------------------------
    # Drag-and-drop highlight (mirrors NDInputAttrTree). This QTreeWidget
    # isn't a custom subclass, so ``self`` is installed as its event filter
    # and intercepts DragEnter/DragMove/DragLeave/Drop to paint the row.
    # ------------------------------------------------------------------

    # Same RGBA as NDInputAttrTree._DROP_HIGHLIGHT_RGBA.
    _DROP_HIGHLIGHT_RGBA = (255, 204, 0, 128)

    def eventFilter(self, obj, event):
        try:
            if obj is self._tree:
                etype = event.type()
                # QEvent.DragEnter=60, DragMove=61, DragLeave=62, Drop=63
                if etype in (60, 61):
                    self._on_drag_move(event)
                    return False  # let default handling continue
                elif etype == 62:
                    self._clear_drop_highlight()
                    return False
                elif etype == 63:
                    self._clear_drop_highlight()
                    return False
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def _on_drag_move(self, event):
        try:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        except Exception:
            self._clear_drop_highlight()
            return
        target_item = self._tree.itemAt(pos)
        if target_item is None or not isinstance(target_item, NDVariableTreeItem):
            # Read-only Internal-section rows reject the highlight.
            self._clear_drop_highlight()
            return
        self._set_drop_highlight(target_item)

    def _set_drop_highlight(self, item):
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
        item = self._drop_highlight_item
        if item is None:
            return
        try:
            from mpynode.ui.qt_wrapper import QBrush

            prev = self._drop_highlight_prev_brush
            if prev is not None:
                item.setBackground(0, prev)
            else:
                item.setBackground(0, QBrush())
        except Exception:
            pass
        self._drop_highlight_item = None
        self._drop_highlight_prev_brush = None

    # ------------------------------------------------------------------
    # + button (User section only)
    # ------------------------------------------------------------------

    def _on_add_clicked(self) -> None:
        if self._py_node is None:
            return
        existing = set(self._current_var_names())
        result = self._prompt_new_var()
        if result is None:
            return
        name, persistent = result
        name = (name or "").strip()
        valid, err = validate_var_name(
            name, existing, node_name=self._py_node.get_name()
        )
        if not valid:
            QMessageBox.warning(self, "Invalid Name", err)
            return
        try:
            if persistent:
                run_undoable(_AddStoredVarCommand(self._py_node, name, None))
            else:
                run_undoable(
                    _AddTemporaryVarCommand(self._py_node, name, None)
                )
        except Exception as exc:
            QMessageBox.warning(self, "Add Failed", str(exc))
            return
        self.refresh()
        # Select the new var so its value cell is one double-click away.
        self._select_user_item(name)

    def _prompt_new_var(self):
        """Modal: variable name + a 'Persistent' checkbox (on by default).
        Returns ``(name, persistent_bool)`` or ``None`` if cancelled.
        Unchecked -> create a session-only (Temporary) variable."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Variable")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Name:", dlg))
        name_edit = QLineEdit(dlg)
        lay.addWidget(name_edit)
        persist_check = QCheckBox("Persistent", dlg)
        persist_check.setChecked(True)
        persist_check.setToolTip(
            "On = saved with the scene (Persistent). "
            "Off = session-only (Temporary)."
        )
        lay.addWidget(persist_check)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        ok_btn = QPushButton("OK", dlg)
        cancel_btn = QPushButton("Cancel", dlg)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        name_edit.setFocus()
        run = getattr(dlg, "exec_", None) or dlg.exec
        if run() != QDialog.Accepted:
            return None
        return name_edit.text(), persist_check.isChecked()

    # ------------------------------------------------------------------
    # Remove button (User section only)
    # ------------------------------------------------------------------

    def _on_remove_clicked(self) -> None:
        items = self._tree.selectedItems()
        if not items or self._py_node is None:
            return
        # Internal entries cannot be removed.
        names = [
            it.var_name
            for it in items
            if isinstance(it, NDVariableTreeItem) and not it.is_internal
        ]
        self._delete_vars(names)

    def _delete_vars(self, names) -> None:
        """Delete one or more stored vars (Persistent or Temporary) -- the
        shared path for the (-) button and the right-click Delete action.
        Undoable. Note: a Temporary var whose ``self.X = ...`` assignment
        still runs will simply be re-created on the next compute."""
        if not names or self._py_node is None:
            return
        if not confirm_delete_node(self, names, entity="variable"):
            return
        for name in names:
            try:
                run_undoable(_RemoveStoredVarCommand(self._py_node, name))
            except Exception as exc:
                QMessageBox.warning(self, "Remove Failed", f"{name}: {exc}")
        self.refresh()

    # ------------------------------------------------------------------
    # Inline edit (itemChanged)
    # ------------------------------------------------------------------

    def _on_item_changed(self, item, column: int) -> None:
        if self._refreshing or self._py_node is None:
            return
        # Internal items are non-editable, so this should never fire for
        # them; guard anyway.
        if not isinstance(item, NDVariableTreeItem):
            return
        if column == 0:
            self._handle_inline_rename(item)
        elif column == 1:
            # Col 1 is the Dir tag, empty for user vars: if the user types
            # into it, restore the empty cell (no-op on the model side).
            if item.text(1)!= "":
                self._refreshing = True
                try:
                    item.setText(1, "")
                finally:
                    self._refreshing = False
        elif column == 2:
            self._handle_inline_value_edit(item)

    def _handle_inline_rename(self, item) -> None:
        new_name = item.text(0).strip()
        old_name = item.var_name
        if not new_name or new_name == old_name:
            self._restore_name(item)
            return
        existing = set(self._current_var_names())
        existing.discard(old_name)
        valid, err = validate_var_name(
            new_name,
            existing,
            node_name=(
                self._py_node.get_name() if self._py_node is not None else None
            ),
        )
        if not valid:
            QMessageBox.warning(self, "Invalid Name", err)
            self._restore_name(item)
            return
        try:
            run_undoable(_RenameStoredVarCommand(self._py_node, old_name, new_name))
        except Exception as exc:
            QMessageBox.warning(self, "Rename Failed", str(exc))
            self._restore_name(item)
            return
        self.refresh()

    def _handle_inline_value_edit(self, item) -> None:
        text = item.text(2)
        try:
            new_value = parse_value_text(text)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Value", str(exc))
            self._restore_value(item)
            return
        # Skip if the parsed value matches what's already stored.
        if repr(new_value) == repr(item.var_value):
            return
        try:
            run_undoable(_SetStoredVarCommand(self._py_node, item.var_name, new_value))
        except Exception as exc:
            QMessageBox.warning(self, "Set Value Failed", str(exc))
            self._restore_value(item)
            return
        self.refresh()

    def _toggle_persistent(self, item, persistent: bool) -> None:
        """Promote (persistent=True) or demote (False) a stored var by
        toggling its ``_storedVarNames`` membership. The value stays live
        in the store either way."""
        try:
            run_undoable(
                _SetPersistentCommand(self._py_node, item.var_name, persistent)
            )
        except Exception as exc:
            QMessageBox.warning(self, "Persistence Change Failed", str(exc))
        self.refresh()

    def _on_context_menu(self, pos) -> None:
        """Right-click a self.X row to move it between Persistent and
        Temporary, or delete it. API (read-only) rows have no menu."""
        if self._py_node is None:
            return
        item = self._tree.itemAt(pos)
        if not isinstance(item, NDVariableTreeItem) or item.is_internal:
            return

        # Operate on the full selection when the clicked row is part of a
        # multi-selection; otherwise just the clicked row.
        selected = [
            it
            for it in self._tree.selectedItems()
            if isinstance(it, NDVariableTreeItem) and not it.is_internal
        ]
        if item in selected and len(selected) > 1:
            targets = [it.var_name for it in selected]
        else:
            targets = [item.var_name]

        menu = QMenu(self._tree)
        # Toggle the Value cell between source repr and thumbnail.
        img_act = None
        if is_previewable_item(item, 2):
            img_lbl = (
                "Show as Source" if is_showing_image(item, 2) else "Show as Image"
            )
            img_act = menu.addAction(img_lbl)
            menu.addSeparator()
        # WAV / raw PCM rows: a waveform render, mutually exclusive with the
        # image view -- the same row is never both.
        wave_act = None
        if is_audio_item(item, 2) and render_waveform_pref_on():
            wave_lbl = (
                "Show as Source" if is_showing_waveform(item, 2)
                else "Show as Waveform"
            )
            wave_act = menu.addAction(wave_lbl)
            menu.addSeparator()
        # Load a media file into THIS row as raw bytes -- the most versatile
        # serialize-safe container; the preview sniffs the magic bytes. The
        # row's Persistent/Temporary status is preserved.
        load_act = menu.addAction("Load media…")
        menu.addSeparator()
        if item.is_session:
            toggle_act = menu.addAction("Make Persistent (save with scene)")
            toggle_target = True
        else:
            toggle_act = menu.addAction(
                "Make Temporary (don't save with scene)"
            )
            toggle_target = False
        menu.addSeparator()
        delete_act = menu.addAction(
            "Delete Variable" + ("s" if len(targets) > 1 else "")
        )

        gpos = self._tree.viewport().mapToGlobal(pos)
        run = getattr(menu, "exec_", None) or menu.exec
        chosen = run(gpos)
        if chosen is img_act and img_act is not None:
            # toggle_value_mode writes data/tooltip on col 2 and each write
            # emits itemChanged, which would literal_eval the source text.
            self._refreshing = True
            try:
                new_mode = toggle_value_mode(item, 2)
            finally:
                self._refreshing = False
            if new_mode is not None:
                # Remember by var name so a rebuild keeps the choice.
                self._image_view_modes[item.var_name] = bool(new_mode)
                refresh_media_widget(
                    self._tree, item, 2, self._ensure_waveform_player()
                )
                idx = self._tree.indexFromItem(item, 2)
                self._img_delegate.sizeHintChanged.emit(idx)
                self._tree.viewport().update()
        elif chosen is wave_act and wave_act is not None:
            # Suppressed for the same reason as the image toggle.
            self._refreshing = True
            try:
                new_mode = toggle_waveform_view(item, 2)
            finally:
                self._refreshing = False
            if new_mode is not None:
                self._waveform_view_modes[item.var_name] = bool(new_mode)
                refresh_media_widget(
                    self._tree, item, 2, self._ensure_waveform_player()
                )
                idx = self._tree.indexFromItem(item, 2)
                self._img_delegate.sizeHintChanged.emit(idx)
                self._tree.viewport().update()
        elif chosen is load_act:
            self._load_media_into(item)
        elif chosen is toggle_act:
            self._toggle_persistent(item, toggle_target)
        elif chosen is delete_act:
            self._delete_vars(targets)

    def _load_media_into(self, item) -> None:
        """Right-click "Load media": pick a file and load its raw bytes into
        ``item``'s variable, PRESERVING the row's Persistent/Temporary status.

        Raw ``bytes`` is stored deliberately -- it is the most versatile
        container that round-trips through the scene without a pickle-trust
        prompt, and the media preview sniffs the format (png/jpg/gif/wav/mp3/
        ...) from the leading magic bytes. A size warning guards embedding a
        large blob into a persistent (scene-saved) var."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load media into %s" % item.var_name,
            "",
            "Media files (*.png *.jpg *.jpeg *.gif *.bmp *.tif *.tiff *.webp "
            "*.wav *.mp3 *.ogg *.flac *.m4a *.aif *.aiff *.mp4 *.mov *.webm);;"
            "All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except Exception as exc:
            QMessageBox.warning(self, "Load Media Failed", str(exc))
            return
        if not data:
            QMessageBox.warning(self, "Load Media Failed", "File is empty.")
            return

        # ``is_session`` == Temporary; anything else is Persistent (scene-saved).
        persistent = not item.is_session
        if persistent and len(data) > _MEDIA_PERSIST_WARN_BYTES:
            name = path.replace("\\", "/").rsplit("/", 1)[-1]
            mb = len(data) / (1024.0 * 1024.0)
            ret = QMessageBox.question(
                self,
                "Large persistent media",
                "%s is %.1f MB. '%s' is a persistent variable, so it is "
                "embedded in the scene file on every save -- this will bloat "
                "the .ma/.mb.\n\nLoad it anyway? (Tip: make the variable "
                "Temporary first to keep it out of the saved file.)"
                % (name, mb, item.var_name),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
        try:
            run_undoable(
                _SetStoredVarCommand(
                    self._py_node, item.var_name, data, persistent
                )
            )
        except Exception as exc:
            QMessageBox.warning(self, "Load Media Failed", str(exc))
            return
        self.refresh()

    def _restore_name(self, item) -> None:
        self._refreshing = True
        try:
            item.setText(0, item.var_name)
        finally:
            self._refreshing = False

    def _restore_value(self, item) -> None:
        self._refreshing = True
        try:
            item.setText(2, _fmt_value(item.var_value))
        finally:
            self._refreshing = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_var_names(self) -> list[str]:
        if self._py_node is None:
            return []
        try:
            return list((self._py_node.get_variables() or {}).keys())
        except Exception:
            return []

    def _select_user_item(self, name: str):
        """Select the row (Persistent or Temporary) whose var_name matches, and
        return it -- or None when this node has no such row."""
        for sec in (self._persistent_section, self._temporary_section):
            if sec is None:
                continue
            for i in range(sec.childCount()):
                child = sec.child(i)
                if (
                    isinstance(child, NDVariableTreeItem)
                    and child.var_name == name
                ):
                    self._tree.setCurrentItem(child)
                    return child
        return None

    def revealVariable(self, name: str) -> bool:
        """Expand, select, scroll to and flash the row for ``name``.

        The Script tab's API view lists persistent variables by name with their
        data abstracted; clicking one raises this tab and calls here to show the
        actual value. Returns True iff a row was found -- a caller must not
        assume one exists, because a name can be declared on the node yet absent
        from the live store, and because a node may declare none at all.

        Never creates a row: revealing is a view operation, and a click that
        declared a variable as a side effect would change what the node saves.
        """
        if self._py_node is None:
            return False
        item = self._select_user_item(name)
        if item is None:
            return False
        # scrollToItem is a no-op on a child of a collapsed section, and the
        # user can collapse either one.
        parent = item.parent()
        if parent is not None:
            self._tree.expandItem(parent)
        # Reuses the existing select + scroll + timed-tint helper rather than
        # repeating its blockSignals discipline.
        self._flash_new_vars({name})
        return True
