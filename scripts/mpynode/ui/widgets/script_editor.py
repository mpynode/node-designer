"""NDScriptEditor \u2014 the script editor widget.

Replaces the legacy NDScriptEditorPlaceholder. Same public API contract:
  * getMPyNode()
  * getText() / setText(text)
  * hasUnsavedChanges() / markSaved()
  * refresh()  (re-pull from node + reset baseline)
  * dirtyStateChanged(bool) signal

Adds line numbers + Python syntax highlighting + Ctrl+wheel font zoom
via the inherited QtPythonEditor.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import Signal
from mpynode.ui.widgets.editor_core import QtPythonEditor


def _hex_to_rgb(hex_color: str):
    """'#rrggbb' or '#rgb' \u2192 (r, g, b) tuple of ints. None on bad input."""
    if not hex_color or not isinstance(hex_color, str):
        return None
    s = hex_color.lstrip("#")
    try:
        if len(s) == 3:
            return tuple(int(c * 2, 16) for c in s)
        if len(s) == 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None
    return None


class NDScriptEditor(QtPythonEditor):
    """Per-tab Python script editor for an mPyNode-family node's expression."""

    # Lets the tab widget update the dirty marker in the tab title.
    dirtyStateChanged = Signal(bool)

    def __init__(self, py_node, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        self._last_saved_text: str = ""
        self._suppress_change_signal = False

        self.refresh()
        self.textChanged.connect(self._on_text_changed)

    # ------------------------------------------------------------------
    # Public API -- matches NDScriptEditorPlaceholder, so NDScriptTabWidget
    # can swap the two.
    # ------------------------------------------------------------------

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
        """Mark the editor's current text as the last-saved baseline."""
        self._last_saved_text = self.getText()
        self.dirtyStateChanged.emit(False)

    def refresh(self) -> None:
        """Re-pull the expression from the node + reset the dirty baseline.

        also push the per-attr-color map into the highlighter
        so var references render in the user's chosen color.

        also push the autocomplete vocabulary (plug tree +
        promoted-type methods + init bindings + stored vars +
        Python builtins) into the inherited completer.
        """
        try:
            text = self._py_node.get_compute_expression() or ""
        except Exception:
            text = ""
        # The api1 ``_computeSource`` plug defaults to the literal string
        # "None", a no-op expression, so normalize that sentinel to a BLANK
        # tab. The editor never re-inserts a header for an empty plug --
        # headers are seeded ONCE, at virgin create in "headers" mode -- so a
        # cleared expression stays cleared across save + reload.
        if not text or text.strip() == "None":
            text = ""
        self.setText(text)
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)
        # Rebuild the highlighter's var-color map from the node's per-attr
        # UI colors.
        self.refreshVarColors()
        self.refreshCompletionVocabulary()

    def refreshCompletionVocabulary(self) -> None:
        """Pull the latest plug-tree + binding + storage
        vocabulary from the bound node and push it into the inherited
        QtPythonEditor completer."""
        if self._py_node is None:
            self.setCompletionWords([])
            return
        try:
            from mpynode.ui.widgets.autocomplete import build_vocabulary

            try:
                node_name = self._py_node.get_name()
            except Exception:
                node_name = None
            vocab = build_vocabulary(node_name, scope="expression")
            self.setCompletionWords([c.text for c in vocab])
        except Exception:
            # Autocomplete is non-essential: never block the editor load.
            pass

    # ------------------------------------------------------------------
    # live refresh hook
    # ------------------------------------------------------------------

    def attachRefreshHub(self, hub) -> None:
        """Subscribe the editor's autocomplete vocabulary
        refresh to a shared RefreshHub. Called by the surrounding
        designer when the active node changes (the designer owns the
        hub lifetime; we just subscribe + unsubscribe).

        Re-attaching with a different hub auto-detaches the previous
        subscription."""
        prev = getattr(self, "_refresh_hub", None)
        if prev is not None and prev is not hub:
            try:
                prev.unsubscribe("script_editor")
            except Exception:
                pass
        self._refresh_hub = hub
        if hub is None:
            return
        from mpynode.ui.widgets.refresh_hub import (
            EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED,
        )

        hub.subscribe(
            "script_editor",
            lambda _event: self.refreshCompletionVocabulary(),
            events=(EVENT_ATTR_ADDED_OR_REMOVED, EVENT_NAME_CHANGED),
        )

    def refreshVarColors(self) -> None:
        """Push the active node's per-attr UI colors into the highlighter.

        Hex strings from the wrapper are converted to RGB tuples (the
        format ``QtPythonHighlighter.formatText`` expects). Called by
        ``refresh()`` and by MNodeMessage callback when
        ``_inputAttrs`` / ``_outputAttrs`` change.
        """
        if self._py_node is None:
            return
        get_colors = getattr(self._py_node, "get_all_attr_colors", None)
        if not callable(get_colors):
            return
        try:
            color_map = get_colors() or {}
        except Exception:
            color_map = {}

        # formatText wants RGB tuples, not hex.
        rgb_map = {}
        for name, hex_color in color_map.items():
            rgb = _hex_to_rgb(hex_color)
            if rgb is not None:
                rgb_map[name] = rgb

        highlighter = getattr(self, "_highlighter", None)
        if highlighter is None or not hasattr(highlighter, "setVarColorMap"):
            return
        try:
            highlighter.setVarColorMap(rgb_map)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_text_changed(self) -> None:
        if self._suppress_change_signal:
            return
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())
