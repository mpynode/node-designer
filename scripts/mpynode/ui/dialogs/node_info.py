"""NDNodeInfoDialog — per-node metadata editor (right-click ▸ Info…).

Edits a node's ``authors`` / ``version`` / ``license`` / ``description`` /
``type_id`` (the ``MetadataMixin`` surface). Empty fields show the GLOBAL default
(from Node Designer preferences) as a greyed placeholder hint -- a hint only, NOT
saved -- so the studio can set license/author once globally and a node left blank
falls back to the live default at compile time (the merge runs in
``compile_controller``). The compiled node embeds this metadata in a banner + the
``MFnPlugin`` vendor/version + a build hash.

``License`` is one free-form block covering the whole legal surface: a copyright
line, a copyleft notice, a Creative Commons deed, an SPDX id, or full terms.
There is no separate Copyright field -- a CC0 or public-domain node has no
copyright holder to name, so that label invited the wrong content.

``Type ID`` is the exception to the defaults rule: an MTypeId is unique per node,
so it never inherits a global default. Left empty (the normal case) the compiled
id is DERIVED from the node's Class and the placeholder previews exactly what
that will be. Filling it in PINS the id -- the escape hatch for the one case a
derived id can't fix itself, a clash with a third-party plugin, which is
otherwise permanent precisely because derivation is stable.

``metadata_from_fields()`` returns the editable state as a dict (used by Save and
unit-tested without a running Maya UI); ``save()`` persists via
``py_node.set_metadata`` and accepts the dialog.
"""
from __future__ import annotations

from mpynode.ui import preferences
from mpynode.ui.qt_wrapper import (
    Qt,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


# prefs key -> canonical metadata field for the placeholder hints.
_DEFAULT_KEYS = {
    "authors": "metadata_default_authors",
    "version": "metadata_default_version",
    "license": "metadata_default_license",
}


def _derived_type_id(py_node) -> str:
    """The MTypeId this node WOULD compile to with no pin -- shown as the Type
    ID placeholder. Mirrors the compile path exactly: the ``node_type_name`` from
    ``derive_class_identity`` is the key the allocator hashes. Best-effort: any
    failure just yields an empty hint."""
    try:
        from maya import cmds

        from mpynode.native.spec.identity import derive_class_identity
        from mpynode.native.toolchain import typeid_registry
        from mpynode.wrappers._mpy_node import _read_py_class

        name       = py_node.get_name()
        class_path = _read_py_class(name) or ""
        type_name = derive_class_identity(
            class_path or name, cmds.nodeType(name))["node_type_name"]
        return "0x%08x" % typeid_registry.deterministic_id(type_name)
    except Exception:
        return ""


def _type_id_is_valid(text: str) -> bool:
    """Blank (= derive it) or a hex value inside Maya's id range."""
    s = (text or "").strip()
    if not s:
        return True
    try:
        val = int(s, 16)
    except Exception:
        return False
    return 0 <= val <= 0x0007FFFF


def _authors_to_text(authors) -> str:
    return "\n".join(authors or [])


def _text_to_authors(text: str):
    out = []
    for line in (text or "").replace(";", "\n").splitlines():
        line = line.strip()
        if line:
            out.append(line)
    return out


class NDNodeInfoDialog(QDialog):
    """Modal metadata editor for a single node wrapper (``py_node``)."""

    def __init__(self, py_node, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        try:
            name = py_node.get_name()
        except Exception:
            name = "<node>"
        self.setWindowTitle("Node Info — %s" % name)
        self.setModal(True)
        self.resize(480, 520)
        # Never shrink below the open size; it can still grow.
        self.setMinimumSize(480, 520)

        self._build_ui(name)
        self._load()

    # ------------------------------------------------------------------
    def _build_ui(self, name: str) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        header = QLabel("Metadata for <b>%s</b>" % name, self)
        outer.addWidget(header)

        # Field labels share one fixed width so every row lines up.
        labels = []

        def _row(text, field):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            lab = QLabel(text, self)
            labels.append(lab)
            row.addWidget(lab)
            row.addWidget(field, 1)
            return row

        def _pane(text, field):
            pane = QWidget(self)
            lay  = QHBoxLayout(pane)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(6)
            lab = QLabel(text, pane)
            labels.append(lab)
            lay.addWidget(lab)
            lay.addWidget(field, 1)
            return pane

        # Author(s) — short multi-line box.
        self._authors_edit = QPlainTextEdit(self)
        self._authors_edit.setToolTip(
            "One \"Name <email>\" per line (also split on ';').")
        self._authors_edit.setFixedHeight(64)
        # NoWrap: see the license/description note below. AsNeeded rather than
        # AlwaysOn only because this box is a fixed 64px -- a permanent bar
        # would cost it a third of its height, and an author line is short
        # enough that it almost never overflows in the first place.
        self._authors_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._authors_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addLayout(_row("Author(s):", self._authors_edit))

        # Version — single line.
        self._version_edit = QLineEdit(self)
        outer.addLayout(_row("Version:", self._version_edit))

        # Type ID — normally empty (derived); the placeholder previews the
        # derived value so the user can see it without compiling first.
        self._type_id_edit = QLineEdit(self)
        self._type_id_edit.setToolTip(
            "Pin this node's compiled MTypeId (hex, e.g. 0x0001a2b3).\n"
            "Leave EMPTY to derive it from the node's Class — stable across\n"
            "rebuilds and machines. Pin one only to resolve a clash with a\n"
            "third-party plugin.")
        self._type_id_edit.textChanged.connect(self._refresh_type_id_state)
        outer.addLayout(_row("Type ID:", self._type_id_edit))

        # License + Description share a draggable splitter (equal by default).
        # Scrollbars are ALWAYS-ON: macOS overlay bars fade out, so
        # ScrollBarAsNeeded leaves nothing to grab on a long license.
        #
        # NO WORD WRAP, and a horizontal bar instead. Soft wrap inserts no
        # newline, so a long line LOOKED formatted here and came out as one
        # unbroken run in the baked header -- the dialog was showing a layout
        # the file could not reproduce. With NoWrap the break you see is a
        # break you typed, which is what lets the banner mirror this box
        # exactly. Same AlwaysOn reasoning as the vertical bars.
        self._license_edit = QPlainTextEdit(self)
        self._license_edit.setMinimumHeight(120)
        self._license_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._license_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._license_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._license_edit.setToolTip(
            "The whole legal block, verbatim: a copyright line, a copyleft or\n"
            "Creative Commons notice, an SPDX id (e.g. MIT), or full terms.\n"
            "Emitted into the baked header exactly as typed, unlabelled.")
        self._description_edit = QPlainTextEdit(self)
        self._description_edit.setMinimumHeight(120)
        self._description_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._description_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._description_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self._split = QSplitter(Qt.Vertical, self)
        self._split.setChildrenCollapsible(False)
        self._split.addWidget(_pane("License:", self._license_edit))
        self._split.addWidget(_pane("Description:", self._description_edit))
        self._split.setStretchFactor(0, 1)
        self._split.setStretchFactor(1, 1)
        # Equal default apportionment; the user can drag the handle.
        self._split.setSizes([10000, 10000])
        outer.addWidget(self._split, 1)

        # Pin a uniform label-column width so all rows align.
        if labels:
            label_w = max(lab.sizeHint().width() for lab in labels)
            for lab in labels:
                lab.setFixedWidth(label_w)

        hint = QLabel(
            "Empty fields fall back to the global defaults "
            "(Preferences ▸ Metadata) at compile time — except Type ID, which "
            "is derived from the Class when left empty.", self)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        outer.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._save_btn = QPushButton("Save", self)
        self._save_btn.clicked.connect(self.save)
        self._cancel_btn = QPushButton("Cancel", self)
        self._cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self._save_btn)
        buttons.addWidget(self._cancel_btn)
        outer.addLayout(buttons)

    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Populate fields from the node's metadata; show the matching global
        default as a greyed PLACEHOLDER (hint only, not saved) on empty fields."""
        try:
            meta = self._py_node.get_metadata() or {}
        except Exception:
            meta = {}

        self._authors_edit.setPlainText(_authors_to_text(meta.get("authors")))
        self._version_edit.setText(str(meta.get("version") or ""))
        self._license_edit.setPlainText(str(meta.get("license") or ""))
        self._description_edit.setPlainText(str(meta.get("description") or ""))
        self._type_id_edit.setText(str(meta.get("type_id") or ""))

        # placeholder hints from global defaults
        self._authors_edit.setPlaceholderText(self._default("authors"))
        self._version_edit.setPlaceholderText(self._default("version"))
        self._license_edit.setPlaceholderText(self._default("license"))
        # Type ID's hint is NOT a global default (an id is unique per node) --
        # it is the value this node derives to when the field is left empty.
        derived = _derived_type_id(self._py_node)
        self._type_id_edit.setPlaceholderText(
            ("%s  (derived)" % derived) if derived else "derived from the Class")
        self._refresh_type_id_state()

    def _refresh_type_id_state(self) -> None:
        """Tint the Type ID field when the text isn't a usable hex id. The
        compile ignores an unusable pin and falls back to the derived id, so
        this is a warning, not a block."""
        ok = _type_id_is_valid(self._type_id_edit.text())
        self._type_id_edit.setStyleSheet(
            "" if ok else "border: 1px solid #a33; color: #d66;")

    def _default(self, field: str) -> str:
        key = _DEFAULT_KEYS.get(field)
        if not key:
            return ""
        try:
            return str(preferences.get_pref(key, "") or "")
        except Exception:
            return ""

    # ------------------------------------------------------------------
    def metadata_from_fields(self) -> dict:
        """The editable state as a metadata dict (empty fields stay empty so the
        compile-time merge can fall back to the live global default)."""
        return {
            "authors":     _text_to_authors(self._authors_edit.toPlainText()),
            "version":     self._version_edit.text().strip(),
            "license":     self._license_edit.toPlainText().strip(),
            "description": self._description_edit.toPlainText().strip(),
            "type_id":     self._type_id_edit.text().strip(),
        }

    def save(self) -> None:
        """Persist via ``set_metadata`` and accept. Best-effort: a write failure
        is swallowed (the wrapper logs it) so the dialog still closes cleanly."""
        try:
            self._py_node.set_metadata(self.metadata_from_fields())
        except Exception:
            pass
        self.accept()
