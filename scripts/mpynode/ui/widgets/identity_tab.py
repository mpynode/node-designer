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

        # The Python API / Native C++ projections and the "What the bake
        # carries" note used to render here. They were reference text nobody
        # re-read after the first time, and they cost more vertical space than
        # the whole rest of the panel. The panel now earns its place on one
        # thing only: Class is NOT editable anywhere else -- the Scene tree
        # shows it in a dimmed, read-only column 1, and that tree's editable
        # column 0 renames the Maya node, not the class.
        root.addStretch(1)

        self.setStyleSheet(_PANEL_STYLE)

        # Naming is one interaction: a PascalCase name + Enter.
        self._class_edit.editingFinished.connect(self._commit_class)

    # --- test / read accessors -----------------------------------------
    def class_name_text(self):
        return self._class_edit.text().strip()

    def node_type_text(self):
        """The derived camelCase node type (``""`` when class-less)."""
        return self._node_type

    # --- population ----------------------------------------------------
    def setPyNode(self, py_node):
        self._py_node = py_node
        self.refresh()


    def _render_empty(self):
        """Blank / neutral render -- used when there is no node AND as the
        graceful fallback when the backing node is gone (deleted / externally
        renamed) so a dead node can never crash the panel."""
        self._node_type = ""
        self._header.setText("IDENTITY")
        self._pill.setText("")
        self._class_edit.clear()

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
        try:
            pc = n.get_py_class() or ""
        except Exception:
            pc = ""
        short = pc.rpartition(".")[2] if pc else ""

        self._header.setText("IDENTITY — %s" % name)
        self._class_edit.setText(short)

        if short:
            self._pill.setText("selected")
            self._node_type = derive_class_identity(
                pc, native_type)["node_type_name"]
        else:
            self._pill.setText("class-less")
            self._node_type = ""

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
