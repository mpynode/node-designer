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
from mpynode._common.interface.reserved_names import check_reserved_name
from mpynode.ui.qt_wrapper import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedLayout,
    Qt,
    QVBoxLayout,
    QWidget,
)


# Attr types the dialog offers, grouped into families (common-first). Per-type
# subframe key = the type name; ALL_ATTR_TYPES is the flattened tuple and the
# single source of truth for both order and membership.
# "double" is deliberately absent: it is redundant with "float" (both come back
# from read_plug_value as a Python float). The wrapper's _ADD_ATTR_KIND still
# accepts it, so existing scenes and .mpn templates keep loading.
_ATTR_TYPE_GROUPS = (
    ("float", "int", "bool", "angle"),
    ("vector", "euler", "matrix", "quaternion", "color"),
    ("string", "enum", "hex", "python"),
    ("mesh", "nurbsCurve", "nurbsSurface"),
    ("time",),
)
ALL_ATTR_TYPES = tuple(t for _group in _ATTR_TYPE_GROUPS for t in _group)

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
        self._type_combo = QComboBox(self)
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
        Falls back to the first item otherwise.
        """
        # Snapshot the user's current selection so we can try to
        # restore it after re-populating the list.
        prev_selection = self._type_combo.currentText() or ""
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
        # Render in family-group order (no separators or colour). Every group
        # member is in ALL_ATTR_TYPES, so a type in ``allowed`` that isn't in a
        # group (e.g. legacy "double") is correctly dropped.
        allowed_set = set(allowed)
        for group in _ATTR_TYPE_GROUPS:
            for t in group:
                if t in allowed_set:
                    self._type_combo.addItem(t)
        # Attempt to restore the previous selection, falling back to the last
        # type selected this session. If neither is valid for the new
        # direction, the combo just stays at its default (index 0).
        if not prev_selection:
            prev_selection = _LAST_SELECTED_TYPE or ""
        if prev_selection:
            idx = self._type_combo.findText(prev_selection)
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)
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
        if attr_type == "int":
            return self._make_numeric_subframe(attr_type, is_int=True)
        if attr_type == "angle":
            # angle uses numeric subframe (radians).
            return self._make_numeric_subframe(attr_type, is_int=False)
        if attr_type == "bool":
            return self._make_bool_subframe()
        if attr_type == "enum":
            return self._make_enum_subframe()
        if attr_type == "time":
            # time has its own subframe with auto-connect option.
            return self._make_time_subframe()
        # vector / matrix / string / euler / python /
        # mesh / nurbsCurve / nurbsSurface — blank
        w      = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(f"({attr_type} — no extra configuration)", w))
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
        grid.addWidget(QLabel("Min:", w),     0, 0)
        grid.addWidget(QLabel("Max:", w),     1, 0)
        grid.addWidget(QLabel("Default:", w), 2, 0)
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

        w._min_edit     = min_edit
        w._max_edit     = max_edit
        w._default_edit = default_edit
        w._is_int       = is_int
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

    def _on_type_changed(self, index: int) -> None:
        # Defensive: _populate_type_combo can fire this during early
        # init before _stack exists. Safe no-op in that case.
        if not hasattr(self, "_stack"):
            return
        type_name = self._type_combo.itemText(index) if index >= 0 else ""
        for i, t in enumerate(ALL_ATTR_TYPES):
            if t == type_name:
                self._stack.setCurrentIndex(i)
                break
        if type_name in ALL_ATTR_TYPES:
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

        attr_type = self._type_combo.currentText()
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
            # numeric subframe (float / int / angle): read min / max / default.
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
