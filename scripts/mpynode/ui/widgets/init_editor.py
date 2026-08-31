"""NDInitEditor — sister editor for the per-node ``_initSource`` plug.

Same Python editor (line numbers, syntax highlighting, font zoom) as
NDScriptEditor but pulls/pushes the Init source instead of the main
expression.

Lives alongside NDScriptEditor inside an NDScriptTabContent widget
that the NDScriptTabWidget instantiates instead of NDScriptEditor
directly.

when the Init attr is empty, prefills with an auto-generated
header that documents the bridge bindings for this node's type
(read/write self.X surface).
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import Signal
from mpynode.ui.widgets.editor_core import QtPythonEditor


class NDInitEditor(QtPythonEditor):
    """Per-tab editor bound to a node's ``_initSource`` string attr."""

    dirtyStateChanged = Signal(bool)

    def __init__(self, py_node, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        self._last_saved_text: str = ""
        self._suppress_change_signal = False
        self.refresh()
        self.textChanged.connect(self._on_text_changed)

    def getMPyNode(self):
        return self._py_node

    def getText(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self._suppress_change_signal = True
        try:
            self.setPlainText(text)
        finally:
            self._suppress_change_signal = False

    def hasUnsavedChanges(self) -> bool:
        return self.getText()!= self._last_saved_text

    def markSaved(self) -> None:
        """Persist the Init source to the node + reset baseline."""
        text = self.getText()
        try:
            self._py_node.set_init_expression(text)
        except Exception as exc:
            import sys

            sys.stderr.write(f"[NDInitEditor] set_init_expression failed: {exc}\n")
            return
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    def refresh(self) -> None:
        """Re-pull from the node's ``_initSource`` attr + reset baseline.

        A blank attr renders as a BLANK tab -- the editor never re-inserts a
        header for an empty plug. Headers are seeded into the plug ONCE, at
        Node-Designer virgin create in ``"headers"`` mode
        (:func:`mpynode._base.commands.build_new_node_command`); a deleted
        expression therefore stays deleted across save + reload, and an
        API-/``.mpn``-created node with a blank plug is left blank.

        also push the autocomplete vocabulary into the inherited completer.
        Init scope is narrower than Expression scope (no plug-tree completions
        -- InitProxy doesn't resolve plugs; reads happen in Expression).
        """
        try:
            text = self._py_node.get_init_expression() or ""
        except Exception:
            text = ""
        self.setText(text)
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)
        self.refreshCompletionVocabulary()

    def refreshCompletionVocabulary(self) -> None:
        """Pull the Init-scope vocabulary (Python builtins
        + init helpers + node's own init-binding extraction) and push
        it into the inherited QtPythonEditor completer."""
        if self._py_node is None:
            self.setCompletionWords([])
            return
        try:
            from mpynode.ui.widgets.autocomplete import build_vocabulary

            try:
                node_name = self._py_node.get_name()
            except Exception:
                node_name = None
            vocab = build_vocabulary(node_name, scope="init")
            self.setCompletionWords([c.text for c in vocab])
        except Exception:
            pass

    def attachRefreshHub(self, hub) -> None:
        """Subscribe the init-tab autocomplete vocabulary
        refresh to a shared RefreshHub."""
        prev = getattr(self, "_refresh_hub", None)
        if prev is not None and prev is not hub:
            try:
                prev.unsubscribe("init_editor")
            except Exception:
                pass
        self._refresh_hub = hub
        if hub is None:
            return
        from mpynode.ui.widgets.refresh_hub import (
            EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED,
        )

        hub.subscribe(
            "init_editor",
            lambda _event: self.refreshCompletionVocabulary(),
            events=(EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED),
        )

    def _on_text_changed(self) -> None:
        if self._suppress_change_signal:
            return
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())
