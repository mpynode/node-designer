"""Pick already-compiled nodes to put in a plug-in.

The Compile tab's "Add compiled nodes…" shows this as its compiled pane
(embedded; standalone it is a dialog). It lists every compiled node under
the places compiled nodes live -- the shipped templates, the user's
compiled-plug-ins folder, and any folder added here (remembered in the
``bundle_source_paths`` preference) -- plus single files added by hand. A multi-node build is listed member by
member, so part of one can be taken. Nothing is compiled or read beyond the
source text; ``bundle_plan.scan`` does the reading and says what each file
is.
"""
from __future__ import annotations

import os
from typing import List, Optional

from mpynode.ui.qt_wrapper import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    Signal,
)

_PREF_KEY = "bundle_source_paths"
_COLS     = ["", "Node", "Class", "Kind", "Type ID", "Commands", "Qt", "Recipe", "From"]
_COL_CHECK, _COL_NODE, _COL_CLASS, _COL_KIND, _COL_ID, _COL_CMDS, _COL_QT, \
    _COL_RECIPE, _COL_FROM = range(9)


def default_roots() -> List[str]:
    """Where compiled nodes are looked for, in order: the template search
    roots (the shipped ``templates/`` tree by default), the user's compiled
    output folder, and the folders added through this dialog."""
    roots: List[str] = []
    try:
        from mpynode._common.util.template_gallery import template_search_roots
        roots += list(template_search_roots() or [])
    except Exception:
        pass
    try:
        from mpynode._common import home
        roots.append(home.compiled_dir())
    except Exception:
        pass
    try:
        from mpynode.ui import preferences
        roots += [str(p) for p in (preferences.get_pref(_PREF_KEY, []) or [])]
    except Exception:
        pass
    out: List[str] = []
    seen = set()
    for r in roots:
        r = os.path.abspath(os.path.expanduser(os.path.expandvars(r)))
        if os.path.isdir(r) and os.path.normcase(r) not in seen:
            seen.add(os.path.normcase(r))
            out.append(r)
    return out


def _remember_root(path: str) -> None:
    try:
        from mpynode.ui import preferences
        cur = [str(p) for p in (preferences.get_pref(_PREF_KEY, []) or [])]
        if path not in cur:
            preferences.set_pref(_PREF_KEY, cur + [path])
    except Exception:
        pass


def _key(m) -> str:
    """The path a member is known by: its source."""
    return m.path


class CompiledNodePicker(QDialog):
    """A checklist of compiled nodes; ``selected_paths()`` after ``Accepted``.
    Embedded (``embedded=True``) it is a pane, not a window: no OK / Cancel,
    an "Add Selected" button that emits ``addSelected`` with the paths."""

    addSelected = Signal(object)

    def __init__(self, parent=None, roots: Optional[List[str]] = None,
                 maya: Optional[str] = None, embedded: bool = False):
        super().__init__(parent)
        self._embedded = bool(embedded)
        if self._embedded:
            self.setWindowFlags(Qt.Widget)
        self.setWindowTitle("Add Compiled Nodes")
        if not self._embedded:
            self.resize(820, 440)
        self._roots   = list(roots) if roots is not None else default_roots()
        self._maya    = maya
        self._members = []          # bundle_plan.Member, table order
        self._build_ui()
        self.rescan()

    # ---- UI -------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        top   = QHBoxLayout()
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Filter by node, class or folder…")
        self._search.textChanged.connect(self._apply_filter)
        top.addWidget(QLabel("Compiled nodes found:", self))
        top.addWidget(self._search, 1)
        outer.addLayout(top)

        self._table = QTableWidget(0, len(_COLS), self)
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        try:
            header.setSectionResizeMode(QHeaderView.ResizeToContents)
            header.setSectionResizeMode(_COL_FROM, QHeaderView.Stretch)
        except Exception:
            pass
        outer.addWidget(self._table, 1)

        row = QHBoxLayout()
        self._all_btn    = QPushButton("Select All", self)
        self._none_btn   = QPushButton("Select None", self)
        self._folder_btn = QPushButton("Add Folder…", self)
        self._folder_btn.setToolTip("Scan another folder for compiled nodes "
                                    "(remembered for next time)")
        self._file_btn   = QPushButton("Add .cpp…", self)
        self._file_btn.setToolTip("Add compiled node sources by file")
        self._rescan_btn = QPushButton("Rescan", self)
        for b in (self._all_btn, self._none_btn, self._folder_btn, self._file_btn,
                  self._rescan_btn):
            row.addWidget(b)
        row.addStretch(1)
        # Embedded: "Add Selected" is a button on this row, and the pane stays.
        self._add_btn = None
        if self._embedded:
            self._add_btn = QPushButton("Add Selected", self)
            self._add_btn.setEnabled(False)
            self._add_btn.clicked.connect(
                lambda checked=False: self.addSelected.emit(self.selected_paths()))
            row.addWidget(self._add_btn)
        outer.addLayout(row)

        self._summary = QLabel("", self)
        outer.addWidget(self._summary)

        # Standalone: OK adds and closes, as a dialog does.
        self._buttons = None
        if not self._embedded:
            self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
            self._buttons.button(QDialogButtonBox.Ok).setText("Add Selected")
            self._buttons.accepted.connect(self.accept)
            self._buttons.rejected.connect(self.reject)
            outer.addWidget(self._buttons)

        self._all_btn.clicked.connect(lambda checked=False: self._set_all(True))
        self._none_btn.clicked.connect(lambda checked=False: self._set_all(False))
        self._folder_btn.clicked.connect(lambda checked=False: self._on_add_folder())
        self._file_btn.clicked.connect(lambda checked=False: self._on_add_file())
        self._rescan_btn.clicked.connect(lambda checked=False: self.rescan())
        self._table.itemChanged.connect(lambda _item: self._update_summary())

    # ---- data -----------------------------------------------------------

    def rescan(self) -> None:
        from mpynode.native.toolchain import bundle_plan

        keep = set(self.selected_paths())
        self._members = bundle_plan.list_candidates(self._roots)
        self._fill(checked=keep)

    def clear_selection(self) -> None:
        """Uncheck every row, hidden ones too (after an add went through)."""
        self._table.blockSignals(True)
        for row in range(self._table.rowCount()):
            it = self._table.item(row, _COL_CHECK)
            if it is not None:
                it.setCheckState(Qt.Unchecked)
        self._table.blockSignals(False)
        self._update_summary()

    def add_sources(self, paths) -> List[str]:
        """Add sources by file; returns the reasons for any that were refused."""
        from mpynode.native.toolchain import bundle_plan

        keep     = set(self.selected_paths())
        have     = {os.path.normcase(_key(m)) for m in self._members}
        problems = []
        for p in paths or []:
            p = os.path.abspath(p)
            if os.path.normcase(p) in have:
                continue
            m = bundle_plan.scan(p)
            self._members.append(m)
            have.add(os.path.normcase(_key(m)))
            if m.kind == "refused":
                problems.append("%s: %s" % (os.path.basename(p), m.reason))
            else:
                keep.add(_key(m))
        self._fill(checked=keep)
        return problems

    def _fill(self, checked=()) -> None:
        checked = set(checked)
        self._table.blockSignals(True)
        self._table.setRowCount(len(self._members))
        for row, m in enumerate(self._members):
            ok   = m.kind != "refused"
            tick = QTableWidgetItem("")
            tick.setFlags((Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                          if ok else Qt.ItemIsSelectable)
            tick.setCheckState(Qt.Checked if (ok and _key(m) in checked) else Qt.Unchecked)
            self._table.setItem(row, _COL_CHECK, tick)
            main = m.resolved.get(m.node) or m.ids.get(m.node) or ""
            kind = m.kind if ok else "refused"
            if m.kind == "fragment":
                kind += " v%d" % m.fragment_version
            cells = {
                _COL_NODE:   m.node or os.path.basename(_key(m)),
                _COL_CLASS:  m.cls,
                _COL_KIND:   kind,
                _COL_ID:     main,
                _COL_CMDS:   ", ".join(m.commands),
                _COL_QT:     "Qt" if m.needs_qt else "",
                _COL_RECIPE: m.recipe,
                _COL_FROM:   os.path.dirname(_key(m)),
            }
            for col, text in cells.items():
                it = QTableWidgetItem(str(text))
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable if ok
                            else Qt.ItemIsSelectable)
                if not ok:
                    it.setToolTip(m.reason)
                self._table.setItem(row, col, it)
        self._table.blockSignals(False)
        self._apply_filter(self._search.text())
        self._update_summary()

    def _apply_filter(self, text) -> None:
        needle = (text or "").strip().lower()
        for row, m in enumerate(self._members):
            hay = " ".join((m.node, m.cls, _key(m))).lower()
            self._table.setRowHidden(row, bool(needle) and needle not in hay)

    def _set_all(self, on: bool) -> None:
        self._table.blockSignals(True)
        for row, m in enumerate(self._members):
            it = self._table.item(row, _COL_CHECK)
            if it is not None and m.kind != "refused" and not self._table.isRowHidden(row):
                it.setCheckState(Qt.Checked if on else Qt.Unchecked)
        self._table.blockSignals(False)
        self._update_summary()

    def _update_summary(self) -> None:
        n_sel = len(self.selected_paths())
        n_bad = sum(1 for m in self._members if m.kind == "refused")
        text  = "%d of %d selected" % (n_sel, len(self._members) - n_bad)
        if n_bad:
            text += "  (%d not usable -- hover for the reason)" % n_bad
        self._summary.setText(text)
        try:
            if self._buttons is not None:
                self._buttons.button(QDialogButtonBox.Ok).setEnabled(n_sel > 0)
            if self._add_btn is not None:
                self._add_btn.setEnabled(n_sel > 0)
        except Exception:
            pass

    # ---- results --------------------------------------------------------

    def selected_members(self):
        out = []
        for row, m in enumerate(self._members):
            it = self._table.item(row, _COL_CHECK)
            if it is not None and it.checkState() == Qt.Checked and m.kind != "refused":
                out.append(m)
        return out

    def selected_paths(self) -> List[str]:
        return [_key(m) for m in self.selected_members()]

    # ---- actions --------------------------------------------------------

    def _on_add_folder(self) -> None:
        start = self._roots[-1] if self._roots else os.path.expanduser("~")
        path  = QFileDialog.getExistingDirectory(self, "Scan a folder for compiled nodes", start)
        if not path:
            return
        path = os.path.abspath(path)
        if path not in self._roots:
            self._roots.append(path)
            _remember_root(path)
        self.rescan()

    def _on_add_file(self) -> None:
        start  = self._roots[-1] if self._roots else os.path.expanduser("~")
        chosen = QFileDialog.getOpenFileNames(self, "Add compiled node sources", start,
                                              "Compiled node sources (*.cpp *.mpn)")
        paths = chosen[0] if isinstance(chosen, tuple) else chosen
        problems = self.add_sources(paths)
        if problems:
            self._summary.setText("; ".join(problems))
