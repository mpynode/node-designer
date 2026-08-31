"""NDViewportEditor -- sister editor for the per-node ``_viewportSource``
plug.

Same Python editor (line numbers, syntax highlighting, font zoom) as
NDScriptEditor and NDInitEditor but pulls/pushes the Viewport source
instead of the main expression or init source.

The Viewport tab runs in PARALLEL with the Compute tab for nodes that
also bridge into systems outside the regular DG compute() path. The
canonical example is mPyFile, whose Viewport source is exec'd inside
``MPxShadingNodeOverride.updateShader`` to push the texture + sampler
state into VP2.

Lives alongside NDScriptEditor + NDInitEditor inside an
NDScriptTabContent widget that the NDScriptTabWidget instantiates
instead of NDScriptEditor directly.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import Signal
from mpynode.ui.widgets.editor_core import QtPythonEditor


class NDViewportEditor(QtPythonEditor):
    """Per-tab editor bound to a node's ``_viewportSource`` string attr."""

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
        """Persist the Viewport source to the node + reset baseline."""
        text = self.getText()
        try:
            self._py_node.set_viewport_expression(text)
        except Exception as exc:
            import sys

            sys.stderr.write(
                f"[NDViewportEditor] set_viewport_expression failed: {exc}\n"
            )
            return
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    def refresh(self) -> None:
        """Re-pull from the node's ``_viewportSource`` attr + reset baseline.

        A blank attr renders as a BLANK tab -- the editor never re-inserts a
        header for an empty plug. Headers are seeded into the plug ONCE, at
        Node-Designer virgin create in "headers" mode (build_new_node_command);
        a cleared expression therefore stays cleared across save + reload.
        """
        try:
            text = self._py_node.get_viewport_expression() or ""
        except Exception:
            text = ""
        self.setText(text)
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)
        self.refreshCompletionVocabulary()

    def refreshCompletionVocabulary(self) -> None:
        """Pull the Viewport-scope vocabulary (Python builtins + init
        helpers + plug tree + node-specific extras) and push it into
        the inherited QtPythonEditor completer."""
        if self._py_node is None:
            self.setCompletionWords([])
            return
        try:
            from mpynode.ui.widgets.autocomplete import build_vocabulary

            try:
                node_name = self._py_node.get_name()
            except Exception:
                node_name = None
            vocab = build_vocabulary(node_name, scope="viewport")
            self.setCompletionWords([c.text for c in vocab])
        except Exception:
            pass

    def attachRefreshHub(self, hub) -> None:
        """Subscribe the viewport-tab autocomplete vocabulary refresh
        to a shared RefreshHub."""
        prev = getattr(self, "_refresh_hub", None)
        if prev is not None and prev is not hub:
            try:
                prev.unsubscribe("viewport_editor")
            except Exception:
                pass
        self._refresh_hub = hub
        if hub is None:
            return
        from mpynode.ui.widgets.refresh_hub import (
            EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED,
        )

        hub.subscribe(
            "viewport_editor",
            lambda _event: self.refreshCompletionVocabulary(),
            events=(EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED),
        )

    def _on_text_changed(self) -> None:
        if self._suppress_change_signal:
            return
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())
