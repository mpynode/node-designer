"""Identity panel: a node's canonical Class + how it projects.

**Class** is the ONE editable field -- the single canonical identity. Everything
else is derived and read-only:

* the **node type** is the camelCase (lower-first) of the Class -- the SAME
  string used by BOTH ``<Class>.create(name=None)`` (Python API) and
  ``mc.createNode('<type>')`` (native C++), so a node created either way is
  auto-named ``<type>1`` by Maya's convention. The panel makes that equivalence
  explicit in two read-only projection lines.
* class-less is a valid first-class state: the field reads empty and naming is
  gated at Compile/Bake. Typing a PascalCase name + Enter synthesizes the
  in-memory ``mpynode_user.<Name>`` class, stamps the node, and emits
  ``classChanged`` so the rest of the UI (scene tree) re-renders.

Importing the module stays Qt-only (method-local maya/wrapper imports),
so it is safe to import headless / before standalone init.
"""
from __future__ import annotations

from mpynode.ui.qt_wrapper import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLineEdit, QLabel, QFont, Qt,
    Signal,
)


_ARROW = "  →  "  # create call -> resulting name

# Each read-only section sits in its own bordered card, so the three
# projections read as three areas instead of one continuous run of labels
# (they were separated by 4px of air and nothing else). Palette roles, NEVER
# hex: this panel is dark in Maya and light in a headless render, and either
# constant is invisible against the other.
_PANEL_STYLE = """
QFrame#ndIdCapsule {
    background: palette(alternate-base);
    border: 1px solid palette(mid);
    border-radius: 5px;
}
"""


def _bake_contract_text(native_type: str) -> str:
    """What a bake does and does not carry, re-flowed for a label.

    Source of truth is ``py_export.BAKE_CONTRACT``, which is the exporter's own
    statement of its semantics, so this panel cannot drift from what the bake
    actually does. It was the ``.py``'s first 16 lines until the top of the file
    became the user's to write; here it is read once, where the rest of the
    node's export facts already live, instead of skipped on every visit.

    Re-flowed rather than shown verbatim: the text is hard-wrapped to fit a
    source file, and a label that re-wraps pre-wrapped text reads as ragged.
    Each blank-line-separated paragraph becomes one line and the label wraps it
    to whatever width the panel has.
    """
    from mpynode._common.io.py_export import BAKE_CONTRACT

    body = BAKE_CONTRACT % {"native_type": native_type or "mPyNode"}
    paragraphs, current = [], []
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped:
            current.append(stripped)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


class NDIdentityWidget(QWidget):
    """The Identity panel. Class is the one editable field; the node type and its
    Python-API / native-C++ projections are derived and read-only."""

    classChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._py_node = None
        self._node_type = ""  # derived camelCase type

        self.setObjectName("ndIdentityPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 11, 12, 13)
        root.setSpacing(8)

        # "IDENTITY -- <NODE>" plus a state pill.
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        self._header = QLabel("IDENTITY", self)
        self._header.setObjectName("ndIdHeader")
        hf = QFont(self._header.font())
        hf.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        self._header.setFont(hf)
        self._pill = QLabel("", self)
        self._pill.setObjectName("ndIdPill")
        header_row.addWidget(self._header)
        header_row.addWidget(self._pill)
        header_row.addStretch(1)
        root.addLayout(header_row)

        # The one editable field.
        class_row = QHBoxLayout()
        class_row.setSpacing(8)
        class_lbl = QLabel("Class", self)
        class_lbl.setObjectName("ndIdClassLbl")
        class_lbl.setFixedWidth(64)
        self._class_edit = QLineEdit(self)
        self._class_edit.setObjectName("ndIdClassEdit")
        self._class_edit.setPlaceholderText(
            "Type a Class name (PascalCase) + Enter to name this node")
        class_row.addWidget(class_lbl)
        class_row.addWidget(self._class_edit)
        root.addLayout(class_row)

        root.addSpacing(4)

        # Python API projection.
        self._py_header = QLabel("Python API", self)
        self._py_header.setObjectName("ndIdSection")
        self._py_code = QLabel("", self)
        self._py_code.setObjectName("ndIdCode")
        self._py_code.setContentsMargins(10, 0, 0, 0)
        self._py_code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self._capsule(self._py_header, self._py_code))

        root.addSpacing(4)

        # Native C++ projection.
        self._cpp_header = QLabel("Native C++", self)
        self._cpp_header.setObjectName("ndIdSection")
        self._cpp_code = QLabel("", self)
        self._cpp_code.setObjectName("ndIdCode")
        self._cpp_code.setContentsMargins(10, 0, 0, 0)
        self._cpp_code.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self._capsule(self._cpp_header, self._cpp_code))

        root.addSpacing(4)

        # What a bake does and does not carry. Lives here rather than as 16
        # folded lines at the top of the API view: it is a fact about the node's
        # export, which is what this panel is for, and it answers the question
        # ("where did my stored audio go?") that the folded version hid.
        self._bake_header = QLabel("What the bake carries", self)
        self._bake_header.setObjectName("ndIdSection")
        self._bake_body = QLabel("", self)
        self._bake_body.setObjectName("ndIdNote")
        self._bake_body.setContentsMargins(10, 0, 0, 0)
        self._bake_body.setWordWrap(True)
        self._bake_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self._capsule(self._bake_header, self._bake_body))

        root.addStretch(1)

        self.setStyleSheet(_PANEL_STYLE)

        # Naming is one interaction: a PascalCase name + Enter.
        self._class_edit.editingFinished.connect(self._commit_class)

    def _capsule(self, header, body):
        """Box a section's header + body so it owns a visible area."""
        box = QFrame(self)
        box.setObjectName("ndIdCapsule")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(9, 7, 9, 8)
        lay.setSpacing(3)
        lay.addWidget(header)
        lay.addWidget(body)
        return box

    # --- test / read accessors -----------------------------------------
    def class_name_text(self):
        return self._class_edit.text().strip()

    def node_type_text(self):
        """The derived camelCase node type (``""`` when class-less)."""
        return self._node_type

    def python_api_text(self):
        return self._py_code.text()

    def native_cpp_text(self):
        return self._cpp_code.text()

    def bake_contract_text(self):
        return self._bake_body.text()

    # --- population ----------------------------------------------------
    def setPyNode(self, py_node):
        self._py_node = py_node
        self.refresh()

    def _parent_name(self, native_type):
        """Root wrapper class name for ``native_type`` (mPyNode -> MPyNode)."""
        from mpynode._node_registry import get_spec

        try:
            spec = get_spec(native_type)
            if spec is not None:
                root = spec.get_wrapper_class()
                if isinstance(root, type):
                    return root.__name__
        except Exception:
            pass
        return native_type

    def _set_code(self, label, text, classless):
        """Set a projection line's text + toggle the class-less (dim/italic)
        look via a dynamic property + style repolish."""
        label.setText(text)
        label.setProperty("classless", "true" if classless else "false")
        label.style().unpolish(label)
        label.style().polish(label)

    def _render_empty(self):
        """Blank / neutral render -- used when there is no node AND as the
        graceful fallback when the backing node is gone (deleted / externally
        renamed) so a dead node can never crash the panel."""
        self._node_type = ""
        self._header.setText("IDENTITY")
        self._pill.setText("")
        self._class_edit.clear()
        self._set_code(self._py_code, "", True)
        self._set_code(self._cpp_code, "", True)
        self._py_header.setText("Python API")
        self._cpp_header.setText("Native C++")
        # Hidden rather than blanked: a lone section heading over empty space
        # reads as a panel that failed to populate.
        self._bake_body.setText("")
        self._bake_header.setVisible(False)
        self._bake_body.setVisible(False)

    def refresh(self):
        n = self._py_node
        if n is None:
            self._render_empty()
            return
        # The node may have been deleted or externally renamed since we were
        # populated -- get_name() returns a cached, possibly-stale string, so
        # mc.nodeType() can raise. Degrade to the empty render instead of
        # letting that propagate through setCurrentNode and abort the sibling
        # panels' population. Every sibling panel is hardened the same way.
        try:
            self._refresh_live(n)
        except Exception:
            self._render_empty()

    def _refresh_live(self, n):
        import maya.cmds as mc
        from mpynode.native.spec.identity import derive_class_identity

        name = n.get_name()
        native_type = mc.nodeType(name)
        parent = self._parent_name(native_type)
        try:
            pc = n.get_py_class() or ""
        except Exception:
            pc = ""
        short = pc.rpartition(".")[2] if pc else ""

        self._header.setText("IDENTITY — %s" % name)
        self._class_edit.setText(short)
        # Independent of whether a Class is stamped: the export contract is the
        # same either way, and it is exactly when a node is unfinished that the
        # user is likeliest to ask what a bake would keep.
        self._bake_body.setText(_bake_contract_text(native_type))
        self._bake_header.setVisible(True)
        self._bake_body.setVisible(True)

        if short:
            self._pill.setText("selected")
            ntype = derive_class_identity(pc, native_type)["node_type_name"]
            self._node_type = ntype
            self._py_header.setText("Python API — class %s(%s)"
                                    % (short, parent))
            self._set_code(
                self._py_code,
                "%s.create()%s%s1" % (short, _ARROW, ntype), False)
            self._cpp_header.setText("Native C++")
            self._set_code(
                self._cpp_code,
                "mc.createNode('%s')%s%s1" % (ntype, _ARROW, ntype), False)
        else:
            self._pill.setText("class-less")
            self._node_type = ""
            self._py_header.setText("Python API")
            self._set_code(
                self._py_code,
                "Name a Class to get an importable Python API.", True)
            self._cpp_header.setText("Native C++")
            self._set_code(
                self._cpp_code,
                "Compiles to a native type once a Class is named.", True)

    def _commit_class(self):
        n = self._py_node
        if n is None:
            return
        new = self._class_edit.text().strip()
        if not new:
            return
        # editingFinished ALSO fires on focus-out, so short-circuit an
        # unchanged name: clicking through the field must not re-synthesize,
        # re-stamp and re-emit classChanged for a redundant tree re-render.
        try:
            cur = (n.get_py_class() or "").rpartition(".")[2]
        except Exception:
            cur = ""
        if new == cur:
            return
        from mpynode._common.io.py_export import is_pascal_class_name

        if not is_pascal_class_name(new):
            self.refresh()
            return
        import maya.cmds as mc
        from mpynode._common.io.user_classes import synthesize, dotted_path

        native_type = mc.nodeType(n.get_name())
        try:
            synthesize(new, native_type)
            n.set_py_class(dotted_path(new))
        except Exception:
            self.refresh()
            return
        self.refresh()
        self.classChanged.emit(new)
