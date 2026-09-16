"""Right-click "Rename Variable" for the Init / Compute / Viewport
expression editors.

Two flavours, both driven by the scope-aware engine in
``_common.refactor``:

* **Local variable** (``amplitude``) -- scope-aware rename within the
  clicked tab. If the binding lives at module scope it also propagates
  to the sibling tabs that share the Init namespace (Init defines a
  name -> Compute/Viewport read it), so the rename stays consistent
  across tabs.
* **``self.<attr>``** -- a plug / stored-var rename. The Maya DG
  attribute is renamed through the existing undoable
  ``_RenameAttrCommand`` (or ``rename_variable``), and every
  ``self.<attr>`` reference in all three tabs is rewritten.

Everything is preview-first: the dialog shows what will change (or why
it can't) and nothing is touched until the user confirms.
"""

from __future__ import annotations

from mpynode._common.util import refactor
from mpynode.ui.qt_wrapper import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    Qt,
    QVBoxLayout,
)


# Never touched by the local-variable renamer: framework-injected globals plus
# the proxy handle. Plug + INTERNAL_API_SLOTS names are added per-node at
# call time.
FRAMEWORK_NAMES = frozenset({
    "self", "np", "numpy", "cmds", "math", "time", "_wallclock",
    "build_default_output", "__builtins__",
})


# ---------------------------------------------------------------------------
# Editor / node plumbing
# ---------------------------------------------------------------------------


def _tab_content(editor):
    """Walk up from ``editor`` to the NDScriptTabContent that holds the
    Init / Compute / Viewport editors. Returns None if not found."""
    w = editor
    for _ in range(12):  # bounded climb; the tree is shallow
        try:
            w = w.parent()
        except Exception:
            return None
        if w is None:
            return None
        if any(hasattr(w, a) for a in
               ("_init_editor", "_expr_editor", "_viewport_editor")):
            return w
    return None


def sibling_editors(editor):
    """Return ``[(editor_widget, label), ...]`` for every expression
    editor in the same tab content (Init / Compute / Viewport). Falls
    back to just the clicked editor if the parent can't be found."""
    tc  = _tab_content(editor)
    out = []
    if tc is not None:
        for attr, label in (("_init_editor", "Init"),
                            ("_expr_editor", "Compute"),
                            ("_viewport_editor", "Viewport")):
            ed = getattr(tc, attr, None)
            if ed is not None:
                out.append((ed, label))
    if not out:
        out.append((editor, "this tab"))
    return out


def _node_of(editor):
    return getattr(editor, "_py_node", None)


def _editor_label(editor, siblings):
    for ed, label in siblings:
        if ed is editor:
            return label
    return "this tab"


def _blocked_local_names(node):
    blocked = set(FRAMEWORK_NAMES)
    if node is not None:
        for getter in ("get_input_attr_map", "get_output_attr_map"):
            fn = getattr(node, getter, None)
            if callable(fn):
                try:
                    blocked |= set(fn().keys())
                except Exception:
                    pass
        slots = getattr(type(node), "INTERNAL_API_SLOTS", ())
        for s in slots:
            blocked.add(s[0] if isinstance(s, (tuple, list)) else s)
    return frozenset(blocked)


def _set_editor_text(editor, text):
    """Replace an editor's text, marking it dirty (uses setText if the
    editor exposes the dirty-aware setter, else setPlainText)."""
    setter = getattr(editor, "setPlainText", None)
    # setText() suppresses the change signal on some editors, so use the
    # plain setter: textChanged fires and the Save button lights up.
    if setter is not None:
        editor.setPlainText(text)


# ---------------------------------------------------------------------------
# self.<attr> classification helpers
# ---------------------------------------------------------------------------


def _self_attr_kind(node, attr):
    """Classify a ``self.<attr>`` name against the node: returns
    "input" / "output" / "stored" / None (framework/unknown)."""
    if node is None:
        return None
    for getter, kind in (("get_input_attr_map", "input"),
                        ("get_output_attr_map", "output")):
        fn = getattr(node, getter, None)
        if callable(fn):
            try:
                if attr in (fn() or {}):
                    return kind
            except Exception:
                pass
    getnames = getattr(node, "get_variable_names", None)
    if callable(getnames):
        try:
            if attr in (getnames() or []):
                return "stored"
        except Exception:
            pass
    return None


def _existing_attr_names(node):
    names = set()
    if node is None:
        return names
    for getter in ("get_input_attr_map", "get_output_attr_map"):
        fn = getattr(node, getter, None)
        if callable(fn):
            try:
                names |= set(fn().keys())
            except Exception:
                pass
    getnames = getattr(node, "get_variable_names", None)
    if callable(getnames):
        try:
            names |= set(getnames() or [])
        except Exception:
            pass
    return names


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------


class NDRenameVariableDialog(QDialog):
    """Preview-first rename dialog.

    ``plan_fn(new_name)`` returns ``(ok, summary, warnings, apply_fn)``.
    The summary / warnings update live as the user types; OK is enabled
    only while ``ok`` is True and the new name differs from the old.
    """

    def __init__(self, parent, old_name, header, plan_fn):
        super().__init__(parent)
        self.setWindowTitle("Rename Variable")
        self.setModal(True)
        self._old_name = old_name
        self._plan_fn  = plan_fn
        self._apply_fn = None

        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(header, self))

        row = QHBoxLayout()
        row.addWidget(QLabel("New name:", self))
        self._field = QLineEdit(self)
        self._field.setText(old_name)
        self._field.selectAll()
        self._field.textChanged.connect(self._on_text_changed)
        row.addWidget(self._field)
        layout.addLayout(row)

        self._preview = QLabel("", self)
        self._preview.setWordWrap(True)
        self._preview.setMinimumWidth(440)
        layout.addWidget(self._preview)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._ok_btn = QPushButton("Rename", self)
        self._ok_btn.clicked.connect(self.accept)
        self._cancel_btn = QPushButton("Cancel", self)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addWidget(self._ok_btn)
        layout.addLayout(btn_row)

        self._on_text_changed(old_name)

    def _resize_to_fit(self):
        # Fit the current (wrapped) preview text.
        try:
            self.adjustSize()
        except Exception:
            pass

    def _on_text_changed(self, text):
        text = text.strip()
        if text == self._old_name:
            self._preview.setText("Enter a new name.")
            self._preview.setStyleSheet("")
            self._ok_btn.setEnabled(False)
            self._apply_fn = None
            self._resize_to_fit()
            return
        ok, summary, warnings, apply_fn = self._plan_fn(text)
        if not ok:
            self._preview.setText(summary)
            self._preview.setStyleSheet("color: #ff6b6b;")
            self._ok_btn.setEnabled(False)
            self._apply_fn = None
            self._resize_to_fit()
            return
        msg = summary
        if warnings:
            msg += "\n\nHeads up:\n  - " + "\n  - ".join(warnings)
            self._preview.setStyleSheet("color: #ffc04d;")
        else:
            self._preview.setStyleSheet("")
        self._preview.setText(msg)
        self._ok_btn.setEnabled(True)
        self._apply_fn = apply_fn
        self._resize_to_fit()

    def accept(self):
        if self._apply_fn is not None:
            try:
                self._apply_fn()
            except Exception as exc:  # never leave the editor half-edited
                QMessageBox.warning(
                    self, "Rename Failed", f"Could not apply rename:\n\n{exc}"
                )
                return
        super().accept()


# ---------------------------------------------------------------------------
# Entry point (called from the editor's context menu)
# ---------------------------------------------------------------------------


def run_rename(editor, lineno, col):
    """Classify the token at ``(lineno, col)`` and open the appropriate
    rename flow. No-op (silent) if the cursor isn't on a renameable
    token."""
    source = editor.toPlainText()
    kind, name = refactor.classify_at(source, lineno, col)
    if kind == "none" or not name:
        return
    node = _node_of(editor)
    if kind == "self_attr":
        _run_self_attr_rename(editor, name, node)
    elif kind == "name":
        _run_local_rename(editor, lineno, col, name, node)
    else:
        QMessageBox.information(
            editor, "Rename Variable",
            f"{name!r} can't be renamed here -- it isn't a local "
            "variable or a self.<attr> reference.",
        )


def _run_local_rename(editor, lineno, col, name, node):
    blocked      = _blocked_local_names(node)
    siblings     = sibling_editors(editor)
    active_label = _editor_label(editor, siblings)
    source       = editor.toPlainText()

    def plan_fn(new_name):
        primary = refactor.plan_rename_at(
            source, lineno, col, new_name, blocked_names=blocked
        )
        if not primary.ok:
            return (False, primary.reason, (), None)
        # Cross-tab propagation is module-level bindings only.
        sib_plans = []  # (editor, label, plan)
        if primary.is_module_level:
            for ed, label in siblings:
                if ed is editor:
                    continue
                p = refactor.plan_rename_free_name(
                    ed.toPlainText(), name, new_name, blocked_names=blocked
                )
                if p.ok and p.count > 0:
                    sib_plans.append((ed, label, p))
        parts = [f"{primary.count} occurrence(s) in {active_label}"]
        for _ed, label, p in sib_plans:
            parts.append(f"{p.count} in {label}")
        summary = (
            f"Rename local variable '{name}' -> '{new_name}'\n"
            + ", ".join(parts) + "."
        )
        warnings = list(primary.warnings)

        def apply_fn():
            _set_editor_text(editor, primary.new_source)
            for ed, _label, p in sib_plans:
                _set_editor_text(ed, p.new_source)

        return (True, summary, tuple(warnings), apply_fn)

    header = f"Rename local variable: {name}"
    dlg    = NDRenameVariableDialog(editor, name, header, plan_fn)
    dlg.show()
    dlg.raise_()


def _run_self_attr_rename(editor, attr, node):
    if node is None:
        QMessageBox.information(
            editor, "Rename Variable",
            f"self.{attr} can't be renamed (no node bound to this editor).",
        )
        return
    attr_kind = _self_attr_kind(node, attr)
    if attr_kind is None:
        QMessageBox.information(
            editor, "Rename Variable",
            f"self.{attr} is a framework-managed attribute and can't be "
            "renamed here.",
        )
        return

    siblings = sibling_editors(editor)
    existing = _existing_attr_names(node)

    def plan_fn(new_name):
        if not refactor.is_valid_identifier(new_name):
            return (False, f"{new_name!r} is not a valid attribute name", (), None)
        if new_name in existing:
            return (
                False,
                f"{new_name!r} already exists as an attribute / variable",
                (), None,
            )
        # Rewrite plans for every tab (text side).
        tab_plans = []  # (editor, label, plan)
        total     = 0
        for ed, label in siblings:
            p = refactor.plan_rename_self_attr(ed.toPlainText(), attr, new_name)
            if not p.ok:
                return (False, p.reason, (), None)
            tab_plans.append((ed, label, p))
            total += p.count
        kind_label = {"input": "input plug", "output": "output plug",
                    "stored": "stored variable"}[attr_kind]
        summary = (
            f"Rename {kind_label} 'self.{attr}' -> 'self.{new_name}'\n"
            f"Updates the node attribute + {total} reference(s) across "
            "the expression tabs."
        )

        def apply_fn():
            node_name = node.get_name()
            # DG-side rename first (undoable for plugs).
            if attr_kind in ("input", "output"):
                from mpynode._base.commands import (
                    _RenameAttrCommand, run_undoable,
                )
                run_undoable(
                    _RenameAttrCommand(node, attr, new_name, attr_kind)
                )
            else:  # stored var
                from mpynode._common.storedvars.stored_vars_api import rename_variable

                rename_variable(node_name, attr, new_name)
            # Then the text references in every tab.
            for ed, _label, p in tab_plans:
                if p.count > 0:
                    _set_editor_text(ed, p.new_source)

        return (True, summary, (), apply_fn)

    header = f"Rename self.{attr} (node attribute)"
    dlg    = NDRenameVariableDialog(editor, attr, header, plan_fn)
    dlg.show()
    dlg.raise_()


# ---------------------------------------------------------------------------
# "Make Persistent Variable" / "Promote to Persistent Variable"
# ---------------------------------------------------------------------------
#
# Both turn an expression variable into a node stored variable (Variables ->
# User), which saves with the scene and repopulates on load:
#
#   * Make -- on a ``self.X`` that is not yet a plug / stored var / internal
#     slot. Registers X seeded None, so it shows in the Variables tab at once
#     and ``self.X`` resolves before the first assignment. The value
#     auto-populates on the next evaluation.
#   * Promote -- on a bare top-level local. Rewrites ``var`` -> ``self.var``
#     so it routes through storage, then registers it. The rewrite lands in
#     the editor; Save commits the expression.


def _internal_slot_names(node):
    slots = getattr(type(node), "INTERNAL_API_SLOTS", ()) if node else ()
    out   = set()
    for s in slots:
        out.add(s[0] if isinstance(s, (tuple, list)) else s)
    return out


def classify_persistable(editor, lineno, col):
    """Decide which persistent-variable action (if any) applies at
    ``(lineno, col)``. Returns ``("make", attr)`` / ``("promote", name)``
    / ``(None, "")``."""
    source = editor.toPlainText()
    kind, word = refactor.classify_at(source, lineno, col)
    node = _node_of(editor)
    if node is None or not word:
        return (None, "")
    if word in FRAMEWORK_NAMES:
        return (None, "")
    if kind == "self_attr":
        # "make" only when X isn't already persisted / managed.
        if _self_attr_kind(node, word) is not None:
            return (None, "")  # already a plug or stored var
        if word in _internal_slot_names(node):
            return (None, "")
        return ("make", word)
    if kind == "name":
        # "promote" only when self.<word> wouldn't collide.
        if word in _existing_attr_names(node):
            return (None, "")
        if word in _internal_slot_names(node):
            return (None, "")
        return ("promote", word)
    return (None, "")


def _log(msg):
    try:
        from mpynode._common.util.log_bus import log as _log_bus

        _log_bus(msg, level="info")
    except Exception:
        pass


def make_persistent_variable(editor, attr):
    """Register ``self.attr`` as a persistent (stored) variable, seeded
    to None. Idempotent guards: refuse if it's already a plug / stored
    var / internal slot."""
    node = _node_of(editor)
    if node is None:
        QMessageBox.information(
            editor, "Make Persistent Variable",
            f"self.{attr} can't be made persistent (no node bound).",
        )
        return
    kind = _self_attr_kind(node, attr)
    if kind == "stored":
        QMessageBox.information(
            editor, "Make Persistent Variable",
            f"self.{attr} is already a persistent variable.",
        )
        return
    if kind in ("input", "output"):
        QMessageBox.information(
            editor, "Make Persistent Variable",
            f"self.{attr} is a {kind} attribute -- it already persists "
            "with the scene.",
        )
        return
    if attr in _internal_slot_names(node):
        QMessageBox.information(
            editor, "Make Persistent Variable",
            f"self.{attr} is a framework-managed internal -- can't be "
            "made a user variable.",
        )
        return
    try:
        from mpynode._base.commands import _AddStoredVarCommand, run_undoable

        run_undoable(_AddStoredVarCommand(node, attr, None))
    except Exception as exc:
        QMessageBox.warning(
            editor, "Make Persistent Variable",
            f"Could not register {attr!r}:\n\n{exc}",
        )
        return
    _log(
        f"Made 'self.{attr}' a persistent variable on "
        f"{node.get_name()!r} (populates on next evaluation)."
    )


def promote_to_persistent_variable(editor, lineno, col):
    """Rewrite a bare local ``var`` -> ``self.var`` and register it as a
    persistent (stored) variable."""
    node = _node_of(editor)
    if node is None:
        QMessageBox.information(
            editor, "Promote to Persistent Variable",
            "Can't promote (no node bound to this editor).",
        )
        return
    blocked = _blocked_local_names(node) | _existing_attr_names(node)         | _internal_slot_names(node)
    plan = refactor.plan_promote_local(
        editor.toPlainText(), lineno, col, blocked_names=blocked
    )
    if not plan.ok:
        QMessageBox.information(
            editor, "Promote to Persistent Variable", plan.reason
        )
        return
    name = plan.old_name
    # Marks the editor dirty; Save commits the expression.
    _set_editor_text(editor, plan.new_source)
    # Seeded None, so it shows in Variables now.
    try:
        from mpynode._base.commands import _AddStoredVarCommand, run_undoable

        run_undoable(_AddStoredVarCommand(node, name, None))
    except Exception as exc:
        QMessageBox.warning(
            editor, "Promote to Persistent Variable",
            f"Rewrote the references, but could not register {name!r}:"
            f"\n\n{exc}",
        )
        return
    _log(
        f"Promoted '{name}' to a persistent variable 'self.{name}' on "
        f"{node.get_name()!r} ({plan.count} reference(s) rewritten; Save "
        "to commit)."
    )


def run_persist(editor, lineno, col, mode, word):
    """Context-menu entry point: dispatch the chosen persistent-var
    action."""
    if mode == "make":
        make_persistent_variable(editor, word)
    elif mode == "promote":
        promote_to_persistent_variable(editor, lineno, col)
