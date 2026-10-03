"""NDAddAttrDialog \u2014 modal dialog for adding new input/output attrs.

UX refinements:
  * Persistent dialog \u2014 ``Add`` keeps the dialog open + clears the name
    + refocuses the name field, so users can add many attrs in one session.
    ``Done`` (or window-close) closes the dialog.
  * Direction selector at the top: Input / Output radio buttons. The user
    can switch direction without reopening the dialog. Allowed types
    update automatically.
  * Tighter vertical spacing between fields.
  * On each successful Add, signals ``attrAdded(name, attr_type, is_array,
    direction, extra_meta_dict)`` so the parent widget refreshes its tree.

The dialog now manages its OWN ``_AddInputAttrCommand`` / ``_AddOutputAttrCommand``
dispatch (was: caller dispatched). Each Add op is undoable on its own.

Validation rules:
  * Name required, no empty
  * No dashes (use underscore)
  * Not in existing attrs of the chosen direction
  * No leading digit
  * Alphanumeric + underscore only
  * Not a Python keyword/builtin/`self`
"""

from __future__ import annotations

import keyword

from mpynode._base.commands import (
    _AddInputAttrCommand,
    _AddOutputAttrCommand,
    run_undoable,
)
from mpynode._common import attr_types as _attr_types
from mpynode._common.interface.reserved_names import check_reserved_name
from mpynode.ui.qt_wrapper import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFontMetrics,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPalette,
    QPushButton,
    QRadioButton,
    QRect,
    QSize,
    QStackedLayout,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    Qt,
    QVBoxLayout,
    QWidget,
)


# Attr types the dialog offers, grouped into families, from the one type table
# (``_common/attr_types.py``). Per-type subframe key = the STORED name, also
# each combo item's data; ALL_ATTR_TYPES is the flattened tuple: the dialog's
# order and membership. A separator line sits between families.
# "double" (float64: a 64-bit real, what Maya's own Add Attribute calls
# "Float") leads and is pre-selected; "float" (float32) is the 32-bit plug, a
# different storage, not a synonym. A type the API accepts but the table keeps
# out of the dialog (``in_dialog=False``) is absent here.
_ATTR_TYPE_GROUPS = _attr_types.DIALOG_GROUPS
ALL_ATTR_TYPES    = _attr_types.DIALOG_NAMES

# The open dropdown's gap between the artist-name column and the description
# column, in em of the font the rows are painted in (the combo's).
_COLUMN_GAP_EM = 2.5

# The unit the numeric subframe's Min / Max / Default are typed in, for the
# unit types: Maya's INTERNAL unit, which is what addAttr -min/-max/-dv take
# and what the code reads, whatever the scene's UI units. Plain numbers have
# no unit.
_NUMERIC_UNIT = {"doubleAngle": "radians", "doubleLinear": "cm"}

# Last attr type selected in the dialog this session (module-global; resets on
# Maya restart). Used as the default type when the dialog re-opens.
_LAST_SELECTED_TYPE = None


# Python identifier validators.
_PY_BUILTINS = frozenset(
    dir(__builtins__)
    if isinstance(__builtins__, type(__builtins__))
    else __builtins__.__dict__
)
_RESERVED = frozenset(keyword.kwlist) | _PY_BUILTINS | {"self"}


def validate_attr_name(
    name: str, existing: set[str], node_name: str | None = None
) -> tuple[bool, str]:
    """Return (is_valid, error_message). Empty error means valid.

    ``node_name`` is optional: pass it and the framework reserved-name
    resolver is consulted too, so the dialog refuses a colliding name up
    front with the SAME sentence the wrapper's guard would raise later.
    """
    if not name:
        return False, "Name is required"
    if "-" in name:
        return False, "Name cannot contain '-' (use '_' instead)"
    if name in existing:
        return False, f"An attribute named {name!r} already exists"
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


def _is_separator(index) -> bool:
    """True for a separator row (``QComboBox.insertSeparator`` marks it so)."""
    return index.data(Qt.AccessibleDescriptionRole) == "separator"


class _TypeItemDelegate(QStyledItemDelegate):
    """Paints the open type dropdown as two columns.

    The artist name sits at the left and the description at ONE x for every
    row, :attr:`column_x`: the widest artist name in :meth:`item_font` plus
    :data:`_COLUMN_GAP_EM` em. The style draws each row's background,
    selection and hover as for any item view; a separator row is a plain line.
    :meth:`refresh` re-measures the column and widens the view so the longest
    row shows unclipped.
    """

    def __init__(self, combo):
        super().__init__(combo.view())
        self._combo    = combo
        self._view     = combo.view()
        self.column_x  = 0
        self.row_width = 0

    def item_font(self):
        """The one font the rows are measured AND painted in: the combo's,
        which is what Qt's own combo popup paints its items in. The view's
        font can differ (a stylesheet font set on QComboBox alone does not
        reach the popup's view), so it is never used for the text."""
        return self._combo.font()

    def text_margin(self) -> int:
        """Qt's own left margin for an item's text, so the first column sits
        where a plain item's text would."""
        style = self._view.style()
        return style.pixelMetric(QStyle.PM_FocusFrameHMargin, None,
                                 self._view) + 1

    def refresh(self) -> None:
        """Measure the columns for the view's items in :meth:`item_font`, and
        set the view's minimum width to the longest row (plus frame and scroll
        bar)."""
        model = self._view.model()
        types = []
        for row in range(model.rowCount()):
            t = _attr_types.BY_NAME.get(model.index(row, 0).data(Qt.UserRole))
            if t is not None:
                types.append(t)
        fm     = QFontMetrics(self.item_font())
        margin = self.text_margin()
        gap    = int(round(_COLUMN_GAP_EM * fm.horizontalAdvance("M")))
        widest_artist = max((fm.horizontalAdvance(t.artist) for t in types),
                            default=0)
        widest_text = max((fm.horizontalAdvance(t.description)
                             for t in types), default=0)
        self.column_x  = margin + widest_artist + gap
        self.row_width = self.column_x + widest_text + margin
        style          = self._view.style()
        extra = (2 * self._view.frameWidth()
                 + style.pixelMetric(QStyle.PM_ScrollBarExtent, None,
                                     self._view))
        self._view.setMinimumWidth(self.row_width + extra)

    def column_rects(self, rect):
        """``(artist_rect, description_rect)`` for a row painted in ``rect``;
        the description always starts at ``rect.left() + column_x``."""
        margin = self.text_margin()
        artist = QRect(rect.left() + margin, rect.top(),
                       max(0, self.column_x - margin), rect.height())
        text = QRect(rect.left() + self.column_x, rect.top(),
                     max(0, rect.width() - self.column_x), rect.height())
        return artist, text

    def paint(self, painter, option, index):
        if _is_separator(index):
            rect   = option.rect
            margin = self.text_margin()
            y      = rect.center().y()
            # The text colour, part-transparent: Mid sits too close to the
            # popup's background on Maya's dark palette to read as a line.
            pen = option.palette.color(QPalette.Text)
            pen.setAlphaF(0.45)
            painter.save()
            painter.setPen(pen)
            painter.drawLine(rect.left() + margin, y, rect.right() - margin, y)
            painter.restore()
            return
        t = _attr_types.BY_NAME.get(index.data(Qt.UserRole))
        if t is None:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # The style paints the background, selection and hover; no text.
        opt.text = ""
        widget   = opt.widget if opt.widget is not None else self._view
        widget.style().drawControl(QStyle.CE_ItemViewItem, opt, painter,
                                   widget)
        if opt.state & QStyle.State_Enabled:
            group = QPalette.Normal
        else:
            group = QPalette.Disabled
        if opt.state & QStyle.State_Selected:
            role = QPalette.HighlightedText
        else:
            role = QPalette.Text
        artist_rect, text_rect = self.column_rects(opt.rect)
        painter.save()
        # The font the columns were measured in, so they cannot overlap.
        painter.setFont(self.item_font())
        painter.setPen(opt.palette.color(group, role))
        self._draw_text(painter, artist_rect, t.artist)
        self._draw_text(painter, text_rect, t.description)
        painter.restore()

    def _draw_text(self, painter, rect, text) -> None:
        """One column's text, left-aligned and centred vertically."""
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)

    def sizeHint(self, option, index):
        if _is_separator(index):
            return QSize(1, max(5, option.fontMetrics.height() // 2))
        size = super().sizeHint(option, index)
        size.setWidth(max(size.width(), self.row_width))
        return size


class _TypeComboBox(QComboBox):
    """The type combo. Closed, it shows the item text ``"<artist> -
    <description>"``; open, :class:`_TypeItemDelegate` draws two columns,
    re-measured each time the popup opens."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.type_delegate = _TypeItemDelegate(self)
        self.setItemDelegate(self.type_delegate)

    def showPopup(self):
        self.type_delegate.refresh()
        super().showPopup()


class NDAddAttrDialog(QDialog):
    """Persistent modal dialog for adding attrs to an mPyNode.

    Construct with the wrapper instance + the initial direction; the
    dialog handles its own undoable Add commands and stays open until
    the user clicks Done.

    The parent widget should pass an ``on_attr_added`` callback that
    refreshes the tree after each successful Add.
    """

    def __init__(
        self,
        parent,
        py_node,
        initial_direction: str = "input",
        on_attr_added          = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Add Attribute: {py_node.get_name()}")
        # NOT modal \u2014 user can interact with the rest of the designer
        # while this dialog is open.
        self.setModal(False)
        self.resize(420, 360)

        self._py_node       = py_node
        self._direction     = initial_direction
        self._on_attr_added = on_attr_added

        self._build_ui()
        self._wire_signals()
        # Focus the name field for fast typing.
        self._name_edit.setFocus()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(6)
        outer.setContentsMargins(10, 10, 10, 10)

        # Build the stack + sub-frames FIRST so _populate_type_combo can call
        # _on_type_changed during setup. The container is added to the outer
        # layout further down, so visual order is unchanged.
        self._stack = QStackedLayout()
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._sub_frames: dict[str, QWidget] = {}
        for t in ALL_ATTR_TYPES:
            frame               = self._make_subframe(t)
            self._sub_frames[t] = frame
            self._stack.addWidget(frame)

        # Exclusive QButtonGroup so clicking the active radio is a no-op AND
        # both radios can never end up unchecked together.
        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel("Direction:", self))
        self._input_radio     = QRadioButton("Input", self)
        self._output_radio    = QRadioButton("Output", self)
        self._direction_group = QButtonGroup(self)
        self._direction_group.setExclusive(True)
        self._direction_group.addButton(self._input_radio)
        self._direction_group.addButton(self._output_radio)
        if self._direction == "output":
            self._output_radio.setChecked(True)
        else:
            self._input_radio.setChecked(True)
        direction_row.addWidget(self._input_radio)
        direction_row.addWidget(self._output_radio)
        direction_row.addStretch(1)
        outer.addLayout(direction_row)

        # Name + type + array
        top = QGridLayout()
        top.setVerticalSpacing(4)
        top.setHorizontalSpacing(6)
        top.addWidget(QLabel("Name:", self), 0, 0)
        self._name_edit = QLineEdit(self)
        top.addWidget(self._name_edit, 0, 1)

        top.addWidget(QLabel("Type:", self), 1, 0)
        self._type_combo = _TypeComboBox(self)
        # Safe to call now: _stack exists.
        self._populate_type_combo()
        top.addWidget(self._type_combo, 1, 1)

        self._array_check = QCheckBox("Array (multi)", self)
        top.addWidget(self._array_check, 2, 1)

        outer.addLayout(top)

        # Now add the pre-built stack container to the outer layout.
        stack_container = QWidget(self)
        stack_container.setLayout(self._stack)
        outer.addWidget(stack_container, stretch=1)

        # Buttons row \u2014 has Add (persistent) + Done.
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._add_btn = QPushButton("Add", self)
        self._add_btn.setDefault(True)
        self._done_btn = QPushButton("Done", self)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._done_btn)
        outer.addLayout(btn_row)

    def _populate_type_combo(self) -> None:
        """Populate the type combo with the types valid for the current
        direction. Preserves the current selection across input/output
        switches when the chosen type is valid for the new direction.
        Falls back to ``double`` (float64) otherwise.

        Each item's text is ``"<artist> - <description>"`` (the open list draws
        it as two columns); the STORED type name is the item data, so every
        lookup goes through ``findData`` / ``currentData``. A separator row,
        which carries no data and cannot be selected, sits between families.
        """
        # Snapshot the user's current selection so we can try to
        # restore it after re-populating the list.
        prev_selection = self._type_combo.currentData() or ""
        # Block signals so re-population doesn't fire currentIndexChanged.
        self._type_combo.blockSignals(True)
        self._type_combo.clear()

        list_method = (
            "list_valid_input_types"
            if self._direction == "input"
            else "list_valid_output_types"
        )
        list_func = getattr(self._py_node, list_method, None)
        allowed   = None
        if callable(list_func):
            try:
                allowed = list_func()
            except Exception:
                allowed = None
        if not allowed:
            allowed = list(ALL_ATTR_TYPES)
        # Render in family-group order, a separator line between families.
        # Every group member is in ALL_ATTR_TYPES, so a type in ``allowed``
        # that isn't in a group (one the table keeps out of the dialog) is
        # correctly dropped.
        allowed_set = set(allowed)
        for group in _ATTR_TYPE_GROUPS:
            members = [t for t in group if t in allowed_set]
            if not members:
                continue
            if self._type_combo.count():
                self._type_combo.insertSeparator(self._type_combo.count())
            for t in members:
                self._type_combo.addItem(_attr_types.dialog_label(t), t)
        self._type_combo.type_delegate.refresh()
        # Restore the previous selection, else the last type selected this
        # session, else ``double``. If none is valid for the new direction,
        # the combo stays at index 0.
        if not prev_selection:
            prev_selection = _LAST_SELECTED_TYPE or ""
        for wanted in (prev_selection, _attr_types.DIALOG_DEFAULT):
            idx = self._type_combo.findData(wanted) if wanted else -1
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)
                break
        self._type_combo.blockSignals(False)
        # Refresh the stack frame for the now-current type.
        self._on_type_changed(self._type_combo.currentIndex())

    def _wire_signals(self) -> None:
        # Subscribe to the GROUP's exclusive buttonClicked (fires once per
        # change, on the newly-selected button), NOT each radio's `toggled`,
        # which fires twice per change.
        self._direction_group.buttonClicked.connect(self._on_direction_changed)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._add_btn.clicked.connect(self._on_add_clicked)
        self._done_btn.clicked.connect(self.close)

    def _on_direction_changed(self, _btn) -> None:
        new_dir = "input" if self._input_radio.isChecked() else "output"
        if new_dir == self._direction:
            return  # No-op: same direction selected, nothing to refresh.
        self._direction = new_dir
        self._populate_type_combo()

    # ------------------------------------------------------------------
    # Sub-frames
    # ------------------------------------------------------------------

    def _make_subframe(self, attr_type: str) -> QWidget:
        if attr_type in ("float", "double"):
            return self._make_numeric_subframe(attr_type, is_int=False)
        if attr_type == "long":
            return self._make_numeric_subframe(attr_type, is_int=True)
        if attr_type in ("doubleAngle", "doubleLinear"):
            # doubleAngle / doubleLinear use the numeric subframe, values in
            # internal units (radians / cm) -- see _NUMERIC_UNIT.
            return self._make_numeric_subframe(attr_type, is_int=False)
        if attr_type == "bool":
            return self._make_bool_subframe()
        if attr_type == "enum":
            return self._make_enum_subframe()
        if attr_type == "time":
            # time has its own subframe with auto-connect option.
            return self._make_time_subframe()
        # double3 / matrix / string / euler / position / pickle /
        # mesh / nurbsCurve / nurbsSurface — blank, named as the dropdown does
        w      = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        artist = _attr_types.artist_name(attr_type)
        layout.addWidget(QLabel(f"({artist} — no extra configuration)", w))
        layout.addStretch(1)
        return w

    def _make_time_subframe(self) -> QWidget:
        """Time subframe with auto-connect checkbox.

        Default ON since 99.9% of use cases want the time1.outTime
        connection. User can opt out by unchecking.
        """
        w     = QWidget(self)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        auto_connect = QCheckBox("Auto-connect to time1.outTime", w)
        # default pulled from preferences (was hard-coded True).
        try:
            from mpynode.ui.preferences import get_pref

            auto_connect.setChecked(bool(get_pref("addattr_time_auto_connect", True)))
        except Exception:
            auto_connect.setChecked(True)
        auto_connect.setToolTip(
            "When enabled, the new time input is automatically connected\n"
            "to Maya's default time1 node so your expression sees the\n"
            "current frame without manual wiring. (Output attrs ignore\n"
            "this option.)"
        )
        outer.addWidget(auto_connect)
        outer.addWidget(
            QLabel(
                "(time — value in current Maya time units, typically frames)",
                w,
            )
        )
        outer.addStretch(1)
        w._auto_connect_check = auto_connect
        return w

    def _make_numeric_subframe(self, attr_type: str, is_int: bool) -> QWidget:
        # A trailing stretch packs the rows at the top with the same tight
        # spacing as the Direction/Name/Type grid. Without it the QStackedLayout
        # fills the container and the grid spreads slack over its 3 rows.
        w     = QWidget(self)
        outer = QVBoxLayout(w)
        outer.setSpacing(0)
        outer.setContentsMargins(0, 0, 0, 0)

        grid = QGridLayout()
        grid.setVerticalSpacing(4)
        grid.setHorizontalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        # "Min (cm):" for a unit type, "Min:" for a plain number.
        unit          = _NUMERIC_UNIT.get(attr_type)
        tail          = " (%s):" % unit if unit else ":"
        min_label     = QLabel("Min" + tail,     w)
        max_label     = QLabel("Max" + tail,     w)
        default_label = QLabel("Default" + tail, w)
        grid.addWidget(min_label,     0, 0)
        grid.addWidget(max_label,     1, 0)
        grid.addWidget(default_label, 2, 0)
        min_edit     = QLineEdit(w)
        max_edit     = QLineEdit(w)
        default_edit = QLineEdit(w)
        if is_int:
            default_edit.setText("0")
        else:
            default_edit.setText("0.0")
        grid.addWidget(min_edit,     0, 1)
        grid.addWidget(max_edit,     1, 1)
        grid.addWidget(default_edit, 2, 1)

        outer.addLayout(grid)
        outer.addStretch(1)  # absorb extra vertical space

        w._min_edit      = min_edit
        w._max_edit      = max_edit
        w._default_edit  = default_edit
        w._is_int        = is_int
        w._min_label     = min_label
        w._max_label     = max_label
        w._default_label = default_label
        return w

    def _make_bool_subframe(self) -> QWidget:
        w      = QWidget(self)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Default:", w))
        true_radio  = QRadioButton("True", w)
        false_radio = QRadioButton("False", w)
        false_radio.setChecked(True)
        layout.addWidget(true_radio)
        layout.addWidget(false_radio)
        layout.addStretch(1)
        w._true_radio  = true_radio
        w._false_radio = false_radio
        return w

    def _make_enum_subframe(self) -> QWidget:
        # +/- list editor pre-populated with False/True; items edit inline.
        w     = QWidget(self)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        outer.addWidget(QLabel("Enum values (one per row, edit inline):", w))
        list_widget = QListWidget(w)
        for default in ("False", "True"):
            item = QListWidgetItem(default)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            list_widget.addItem(item)
        outer.addWidget(list_widget, stretch=1)
        btn_row  = QHBoxLayout()
        plus_btn = QPushButton("+", w)
        plus_btn.setFixedWidth(32)
        plus_btn.setToolTip("Add a new enum value")
        minus_btn = QPushButton("−", w)
        minus_btn.setFixedWidth(32)
        minus_btn.setToolTip("Remove the selected value(s)")
        btn_row.addWidget(plus_btn)
        btn_row.addWidget(minus_btn)
        btn_row.addStretch(1)
        outer.addLayout(btn_row)
        plus_btn.clicked.connect(lambda: self._enum_add_blank(list_widget))
        minus_btn.clicked.connect(lambda: self._enum_remove_selected(list_widget))
        w._list_widget = list_widget
        return w

    @staticmethod
    def _enum_add_blank(list_widget) -> None:
        item = QListWidgetItem(f"value{list_widget.count()}")
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
        list_widget.addItem(item)
        list_widget.setCurrentItem(item)
        list_widget.editItem(item)

    @staticmethod
    def _enum_remove_selected(list_widget) -> None:
        for item in list(list_widget.selectedItems()):
            list_widget.takeItem(list_widget.row(item))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def _on_type_changed(self, _index: int = -1) -> None:
        # Defensive: _populate_type_combo can fire this during early
        # init before _stack exists. Safe no-op in that case.
        if not hasattr(self, "_stack"):
            return
        # By item data, never by row: the separators shift every row, and
        # the sub-frames are keyed by the stored name. A separator row has no
        # data and leaves the frame as it is.
        type_name = self._type_combo.currentData() or ""
        frame     = self._sub_frames.get(type_name)
        if frame is not None:
            self._stack.setCurrentWidget(frame)
            global _LAST_SELECTED_TYPE
            _LAST_SELECTED_TYPE = type_name
        # EVERY attr type can be multi: Maya handles ``matrix[]`` fine and the
        # wrapper round-trips it as ``list[np.ndarray(4,4)]``.
        if hasattr(self, "_array_check"):
            self._array_check.setEnabled(True)

    def _on_add_clicked(self) -> None:
        """Validate, add via undoable command, then RESET the form.

        dialog stays open after each Add. The user closes
        via Done (or window close).

        enum_names captured from the enum subframe and
        forwarded to the Add command (cmds.addAttr enumName=...).
        """
        name = self._name_edit.text().strip()
        # Re-pull the existing attrs (they may have changed from a prior Add).
        existing = self._collect_existing()
        ok, err = validate_attr_name(
            name, existing, node_name=self._py_node.get_name()
        )
        if not ok:
            QMessageBox.warning(self, "Invalid Name", err)
            return

        attr_type = self._type_combo.currentData() or ""
        is_array  = self._array_check.isChecked()

        # Per-type extras (enum gets enum_names; time gets auto_connect_time;
        # numeric gets min/max/default; others stay default).
        enum_names        = None
        auto_connect_time = True  # default — only consulted for time inputs
        min_value         = max_value = default_value = None
        sub               = self._sub_frames.get(attr_type)
        if sub is not None and hasattr(sub, "_list_widget"):
            entries = [
                sub._list_widget.item(i).text().strip()
                for i in range(sub._list_widget.count())
            ]
            entries = [e for e in entries if e]  # drop blanks
            if not entries:
                QMessageBox.warning(
                    self,
                    "No Enum Entries",
                    "Add at least one enum entry.",
                )
                return
            enum_names = entries
        elif sub is not None and hasattr(sub, "_auto_connect_check"):
            # time subframe.
            auto_connect_time = sub._auto_connect_check.isChecked()
        elif sub is not None and hasattr(sub, "_min_edit"):
            # numeric subframe (double / float / long / doubleAngle /
            # doubleLinear): read min / max / default.
            is_int = bool(getattr(sub, "_is_int", False))

            def _parse(text, field):
                text = text.strip()
                if not text:
                    return None
                try:
                    return int(text) if is_int else float(text)
                except ValueError:
                    raise ValueError(f"{field} must be a number (got {text!r}).")

            try:
                min_value     = _parse(sub._min_edit.text(),     "Min")
                max_value     = _parse(sub._max_edit.text(),     "Max")
                default_value = _parse(sub._default_edit.text(), "Default")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid Value", str(exc))
                return
            if (
                min_value is not None
                and max_value is not None
                and min_value > max_value
            ):
                QMessageBox.warning(
                    self, "Invalid Range", "Min must be less than or equal to Max."
                )
                return

        # Dispatch via undoable command.
        cmd_cls = (
            _AddInputAttrCommand
            if self._direction == "input"
            else _AddOutputAttrCommand
        )
        try:
            if self._direction == "input":
                run_undoable(
                    cmd_cls(
                        self._py_node,
                        name,
                        attr_type,
                        is_array,
                        enum_names        = enum_names,
                        auto_connect_time = auto_connect_time,
                        min_value         = min_value,
                        max_value         = max_value,
                        default_value     = default_value,
                    )
                )
            else:
                # Output command doesn't have auto_connect_time —
                # outputs can't be driven by time1.
                run_undoable(
                    cmd_cls(
                        self._py_node,
                        name,
                        attr_type,
                        is_array,
                        enum_names    = enum_names,
                        min_value     = min_value,
                        max_value     = max_value,
                        default_value = default_value,
                    )
                )
        except Exception as exc:
            QMessageBox.warning(self, "Add Failed", str(exc))
            return

        # Notify parent so the tree refreshes.
        if callable(self._on_attr_added):
            try:
                self._on_attr_added(name, attr_type, is_array, self._direction)
            except Exception:
                pass

        # Reset the form for the next Add.
        self._name_edit.clear()
        self._name_edit.setFocus()

    def _collect_existing(self) -> set[str]:
        """Return the set of attr names currently on the node in the
        chosen direction (so validation catches just-added names too)."""
        list_method = (
            "get_input_attr_map" if self._direction == "input" else "get_output_attr_map"
        )
        list_func = getattr(self._py_node, list_method, None)
        if not callable(list_func):
            return set()
        try:
            return set((list_func() or {}).keys())
        except Exception:
            return set()
