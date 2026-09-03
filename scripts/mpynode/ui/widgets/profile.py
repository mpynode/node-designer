"""Profile panel widget.

Renders timing stats + optional cProfile drill-down for a selected
mPy* node. Reads the snapshot from the node's ``_profileSnapshotData``
plug; the actual collection happens inside ``exec_with_profile_watch``.

Layout:
 [ Profile: <Off|Profile|Deep Profile> ] [ Reset Stats ] [ Evaluate Node ] [ Unit: <combo> ]

 Last (us):...
 Avg (us):...
 Min (us):...
 Max (us):...
 Count:...

 [ Function | Calls | Cumulative ms | Total ms | Per-call ms ]... cProfile rows when deep profile is on...

The Profile mode combo writes the node's two bool toggles
(``profile_enabled`` / ``deep_profile_enabled``) via cmds.setAttr:

  * "Off"          -> both False
  * "Profile"      -> profile_enabled=True, deep_profile_enabled=False
  * "Deep Profile" -> both True (deep is only meaningful with profile on)

The Evaluate Node button forces a one-shot evaluation of the node
so the stats populate immediately (this evaluates downstream graph
too, by design). The panel itself does not gate behavior -- flipping the
mode on is the only thing that starts collection.
"""

from __future__ import annotations

import maya.cmds as mc
from mpynode.ui.qt_wrapper import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from mpynode.ui.widgets.font_prefs import wire_area_font


_STAT_KEYS = ("last", "avg", "min", "max", "count")

# unit-label -> (multiplier-from-seconds, precision). Snapshot timings are
# microseconds in the plug, cProfile rows milliseconds; both convert to
# seconds first, then to the selected unit.
_TIME_UNITS = (
    ("ns", 1e9, 0),  # nanoseconds: integer precision
    ("\u00b5s", 1e6, 2),
    ("ms", 1e3, 3),
    ("s", 1.0, 6),
)
_TIME_UNIT_MAP = {label: (mult, prec) for (label, mult, prec) in _TIME_UNITS}
_DEFAULT_UNIT = "\u00b5s"

# Combo index maps directly onto the node's (profile_enabled,
# deep_profile_enabled) pair.
_MODE_OFF = 0
_MODE_PROFILE = 1
_MODE_DEEP = 2
_PROFILE_MODES = ("Off", "Profile", "Deep Profile")

# Base unit for each data source -> seconds divisor.
_SNAP_BASE_TO_SECONDS = 1e6  # last_us / avg_us / min_us / max_us are microseconds
_DEEP_BASE_TO_SECONDS = 1e3  # cumtime_ms / tottime_ms / percall_ms are milliseconds


def _convert(value: float, from_divisor: float, to_unit: str) -> float:
    """Convert ``value`` (in base unit, where base/sec = from_divisor)
    into ``to_unit``."""
    seconds = float(value) / from_divisor
    mult, _prec = _TIME_UNIT_MAP[to_unit]
    return seconds * mult


def _fmt(value: float, unit: str) -> str:
    """Format a converted value with the precision appropriate for unit."""
    _mult, prec = _TIME_UNIT_MAP[unit]
    if prec == 0:
        return str(int(round(value)))
    return f"{value:.{prec}f}"


class NDProfileWidget(QWidget):
    """Profile tab \u2014 read-only timing + cProfile drill-down view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._py_node = None
        # Suppresses signal recursion while rebuilding from a refresh.
        self._refreshing = False
        # Display unit for timing columns; persists across refreshes.
        self._unit: str = _DEFAULT_UNIT

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._header = QLabel("(no node selected)", self)
        layout.addWidget(self._header)

        # Grouped at the left; a trailing stretch stops them spreading across
        # the full width.
        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("Profile:", self))
        # 0 = Off (default), 1 = Profile, 2 = Deep Profile (cProfile
        # drill-down, which implies Profile on).
        self._mode_combo = QComboBox(self)
        for label in _PROFILE_MODES:
            self._mode_combo.addItem(label)
        self._mode_combo.setCurrentIndex(_MODE_OFF)
        self._mode_combo.setToolTip(
            "Off: no profiling.\n"
            "Profile: cheap per-compute timing stats "
            "(last/avg/min/max/count).\n"
            "Deep Profile: also run cProfile every compute for "
            "per-function stats (heavyweight)."
        )
        self._reset_btn = QPushButton("Reset Stats", self)
        self._reset_btn.setToolTip(
            "Clear the running stats so the next compute starts at count=0."
        )
        self._refresh_btn = QPushButton("Evaluate Node", self)
        self._refresh_btn.setToolTip(
            "Force a one-shot evaluation of this node so the profiler "
            "updates now. This also evaluates downstream graph nodes "
            "(by design) -- the only way to pull a fresh compute."
        )
        self._unit_combo = QComboBox(self)
        for label, _mult, _prec in _TIME_UNITS:
            self._unit_combo.addItem(label)
        self._unit_combo.setCurrentText(self._unit)
        self._unit_combo.setToolTip(
            "Time unit for the timing columns + cProfile drill-down. "
            "Sort order is preserved across unit switches."
        )
        btn_row.addWidget(self._mode_combo)
        btn_row.addWidget(self._reset_btn)
        btn_row.addWidget(self._refresh_btn)
        btn_row.addSpacing(12)
        btn_row.addWidget(QLabel("Unit:", self))
        btn_row.addWidget(self._unit_combo)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # 5 rows of label/value pairs. The label text is rebuilt each refresh
        # so it tracks the selected unit.
        self._stat_value_labels: dict[str, QLabel] = {}
        self._stat_label_widgets: dict[str, QLabel] = {}
        for key in _STAT_KEYS:
            row = QHBoxLayout()
            label = QLabel("", self)  # text populated in refresh()
            label.setMinimumWidth(80)
            value = QLabel("\u2014", self)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.addWidget(label)
            row.addWidget(value)
            row.addStretch(1)
            layout.addLayout(row)
            self._stat_value_labels[key] = value
            self._stat_label_widgets[key] = label

        # cProfile drill-down. Header text is rebuilt each refresh.
        self._tree = QTreeWidget(self)
        wire_area_font(self._tree, "panel")
        self._tree.setColumnCount(5)
        self._tree.setRootIsDecorated(False)
        self._tree.setSortingEnabled(True)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree)

        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        self._unit_combo.currentTextChanged.connect(self._on_unit_changed)

        self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    # Public API (mirrors NDVariablesWidget)
    # ------------------------------------------------------------------

    def setPyNode(self, py_node):
        self._py_node = py_node
        self.refresh()

    def refresh(self):
        """Rebuild the panel from the node's plug values."""
        self._refreshing = True
        try:
            self._tree.clear()
            # Rebuilt on EVERY refresh with the current unit, so
            # _on_unit_changed just calls refresh().
            unit = self._unit
            self._stat_label_widgets["last"].setText(f"Last ({unit}):")
            self._stat_label_widgets["avg"].setText(f"Avg ({unit}):")
            self._stat_label_widgets["min"].setText(f"Min ({unit}):")
            self._stat_label_widgets["max"].setText(f"Max ({unit}):")
            self._stat_label_widgets["count"].setText("Count:")
            self._tree.setHeaderLabels(
                [
                    "Function",
                    "Calls",
                    f"Cumulative ({unit})",
                    f"Total ({unit})",
                    f"Per-call ({unit})",
                ]
            )

            if self._py_node is None:
                self._header.setText("(no node selected)")
                for value in self._stat_value_labels.values():
                    value.setText("\u2014")
                # UNCHECK too, not just grey out, or the toggles look like
                # they're still on. Safe because ``_refreshing`` is True, so
                # the mode handler no-ops.
                self._mode_combo.setCurrentIndex(_MODE_OFF)
                self._set_controls_enabled(False)
                return
            self._header.setText(f"Profile: {self._py_node.get_name()}")

            # Only ``MPyNode`` declares the profile methods -- ``MPyIkSolver``,
            # ``MPyField`` etc. don't inherit them -- so detect via hasattr and
            # disable the controls instead of crashing in setPyNode.
            supports_profile = hasattr(self._py_node, "is_profile_enabled")
            if not supports_profile:
                self._header.setText(
                    f"Profile: {self._py_node.get_name()} (not supported "
                    "for this node type)"
                )
                self._mode_combo.setCurrentIndex(_MODE_OFF)
                self._set_controls_enabled(False)
                for value in self._stat_value_labels.values():
                    value.setText("\u2014")
                return

            self._set_controls_enabled(True)

            # Deep implies profile-on, so check deep first.
            if bool(self._py_node.is_deep_profile_enabled()):
                self._mode_combo.setCurrentIndex(_MODE_DEEP)
            elif bool(self._py_node.is_profile_enabled()):
                self._mode_combo.setCurrentIndex(_MODE_PROFILE)
            else:
                self._mode_combo.setCurrentIndex(_MODE_OFF)

            snap = None
            try:
                snap = self._py_node.get_profile_snapshot()
            except Exception:
                snap = None

            if snap is None:
                for value in self._stat_value_labels.values():
                    value.setText("\u2014")
                return

            # Microseconds (base) -> selected unit.
            for key in ("last", "avg", "min", "max"):
                raw_us = snap.get(key + "_us")
                value_widget = self._stat_value_labels[key]
                if raw_us is None:
                    value_widget.setText("\u2014")
                    continue
                converted = _convert(raw_us, _SNAP_BASE_TO_SECONDS, unit)
                value_widget.setText(_fmt(converted, unit))
            count_raw = snap.get("count")
            if count_raw is None:
                self._stat_value_labels["count"].setText("\u2014")
            else:
                self._stat_value_labels["count"].setText(str(int(count_raw)))

            deep_table = snap.get("deep_table") or []
            for row in deep_table:
                # _SortableTreeWidgetItem.__lt__ consults UserRole (canonical
                # seconds) instead of display text, so numeric columns sort
                # numerically.
                item = _SortableTreeWidgetItem(self._tree)
                item.setText(0, str(row.get("function", "")))
                # Qt.UserRole sort values are always SECONDS, so the order
                # survives a unit switch.
                _set_int_col(item, 1, int(row.get("calls", 0)))
                _set_float_col(
                    item,
                    2,
                    _convert(
                        float(row.get("cumtime_ms", 0.0)), _DEEP_BASE_TO_SECONDS, unit
                    ),
                    sort_seconds=float(row.get("cumtime_ms", 0.0))
                    / _DEEP_BASE_TO_SECONDS,
                    unit=unit,
                )
                _set_float_col(
                    item,
                    3,
                    _convert(
                        float(row.get("tottime_ms", 0.0)), _DEEP_BASE_TO_SECONDS, unit
                    ),
                    sort_seconds=float(row.get("tottime_ms", 0.0))
                    / _DEEP_BASE_TO_SECONDS,
                    unit=unit,
                )
                _set_float_col(
                    item,
                    4,
                    _convert(
                        float(row.get("percall_ms", 0.0)), _DEEP_BASE_TO_SECONDS, unit
                    ),
                    sort_seconds=float(row.get("percall_ms", 0.0))
                    / _DEEP_BASE_TO_SECONDS,
                    unit=unit,
                )
        finally:
            self._refreshing = False

    # ------------------------------------------------------------------
    # Toggle handlers (write to plug; refresh comes via attr-change cb)
    # ------------------------------------------------------------------

    def _set_controls_enabled(self, on: bool) -> None:
        self._mode_combo.setEnabled(on)
        self._reset_btn.setEnabled(on)
        self._refresh_btn.setEnabled(on)

    def _on_mode_changed(self, index: int) -> None:
        """Profile-mode combo changed.

        Maps the combo index onto the node's two bool toggles:

          * Off          -> profile=False, deep=False
          * Profile      -> profile=True,  deep=False
          * Deep Profile -> profile=True,  deep=True

        Turning profiling ON (Profile or Deep) forces a one-shot
        compute so the panel shows count=1 / the first sample
        immediately. Switching to Off clears the snapshot plug + the
        stat labels so stale numbers don't linger pretending profile
        is still on.
        """
        if self._refreshing or self._py_node is None:
            return
        profile_on = index >= _MODE_PROFILE
        deep_on = index >= _MODE_DEEP
        name = self._py_node.get_name()
        try:
            mc.setAttr(name + ".profile_enabled", bool(profile_on))
        except Exception:
            pass
        try:
            mc.setAttr(name + ".deep_profile_enabled", bool(deep_on))
        except Exception:
            pass

        if profile_on:
            # Force a one-shot compute so stats populate now.
            try:
                from mpynode._base.eval_helpers import force_one_eval

                force_one_eval(self._py_node)
            except Exception:
                pass
        else:
            # Off: clear stat values + the snapshot plug, so stale numbers
            # don't linger pretending profile is on.
            try:
                mc.setAttr(
                    name + "._profileSnapshotData",
                    "",
                    type="string",
                )
            except Exception:
                pass
            for value in self._stat_value_labels.values():
                value.setText("\u2014")
            try:
                self._tree.clear()
            except Exception:
                pass

    def _on_refresh_clicked(self) -> None:
        """Force a one-shot evaluation of the node + repaint the panel.

        This pulls a fresh compute (and, by design, evaluates the
        downstream graph) so the profiler reflects the current state
        without the user having to scrub the timeline or nudge an
        upstream input.
        """
        if self._py_node is None:
            return
        try:
            from mpynode._base.eval_helpers import force_one_eval

            force_one_eval(self._py_node)
        except Exception:
            pass
        self.refresh()

    def _on_unit_changed(self, _new_unit: str) -> None:
        if self._refreshing:
            return
        # The combo text IS the unit label, and refresh() rebuilds every
        # timing label + the tree.
        self._unit = self._unit_combo.currentText()
        self.refresh()

    def _on_reset_clicked(self) -> None:
        """Reset on-instance stats AND clear the snapshot plug."""
        if self._py_node is None:
            return
        try:
            import maya.api.OpenMaya as om
            from mpynode._common import instrumentation as _instr

            sel = om.MSelectionList()
            sel.add(self._py_node.get_name())
            node_obj = sel.getDependNode(0)
            _instr.reset_stats(node_obj)
        except Exception:
            pass
        # Panel shows "no data" until the next compute.
        try:
            mc.setAttr(
                self._py_node.get_name() + "._profileSnapshotData",
                "",
                type="string",
            )
        except Exception:
            pass
        self.refresh()


def _set_float_col(
    item: QTreeWidgetItem,
    col: int,
    value: float,
    *,
    sort_seconds: float | None = None,
    unit: str | None = None,
) -> None:
    """Set a float value with Qt.UserRole sort key for numeric sorting.

    when called with sort_seconds + unit, formats using
    the unit's precision and stores the canonical seconds value as
    the sort key (so sort order is stable across unit switches).
    """
    if unit is not None:
        item.setText(col, _fmt(value, unit))
    else:
        item.setText(col, f"{value:.3f}")
    item.setData(
        col,
        Qt.UserRole,
        float(sort_seconds if sort_seconds is not None else value),
    )


def _set_int_col(item: QTreeWidgetItem, col: int, value: int) -> None:
    """Set an int value with Qt.UserRole sort key."""
    item.setText(col, str(value))
    item.setData(col, Qt.UserRole, int(value))


class _SortableTreeWidgetItem(QTreeWidgetItem):
    """QTreeWidgetItem subclass that sorts numerically by Qt.UserRole
    when both rows have UserRole data set, falling back to direct
    text comparison otherwise.

    fix: the default QTreeWidgetItem.__lt__ compares the
    displayed text as strings, which produces lexicographic ordering
    on numeric columns. The pre-fix bug showed up as e.g. cumulative
    sort returning ``[84, 666, 541, 3959,...]`` (with '208' wedged
    between '250' and '1501' because '208' < '250' < '1501'
    lexicographically). We always stored the canonical seconds value
    in UserRole; this subclass actually consults it.

    fix: never call ``super().__lt__()``. In PySide
    (both 2 and 6) ``QTreeWidgetItem`` exposes ``operator<`` as a
    virtual function that re-dispatches through Python's MRO -- so
    ``super().__lt__(other)`` ends up calling self.__lt__ again,
    producing infinite recursion. The bug surfaced with deep
    profile enabled (multiple cProfile rows in the tree means Qt
    actually invokes the sort comparator). Fix: implement the text
    fallback directly via self.text(col) < other.text(col).
    """

    def __lt__(self, other):
        # Qt guarantees another QTreeWidgetItem for items in the same tree,
        # but be defensive.
        if not isinstance(other, QTreeWidgetItem):
            return NotImplemented
        tree = self.treeWidget()
        if tree is None:
            # No tree context: direct text compare on column 0 for SOME
            # stable ordering. Never call super.
            return self.text(0) < other.text(0)
        col = tree.sortColumn()
        a = self.data(col, Qt.UserRole)
        b = other.data(col, Qt.UserRole)
        if a is not None and b is not None:
            try:
                return float(a) < float(b)
            except (TypeError, ValueError):
                pass
        # Text fallback, e.g. column 0 = Function name. CRITICAL: do NOT call
        # super().__lt__ -- it virtual-dispatches back through Python's MRO
        # and re-enters this method -> recursion.
        return self.text(col) < other.text(col)
