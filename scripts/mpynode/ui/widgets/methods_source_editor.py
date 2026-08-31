"""NDMethodsSourceEditor -- single full-buffer editor over ``_methodsSource``.

Sister to :class:`NDInitEditor`, but bound to the node's Methods source plug
via :meth:`MethodsSourceMixin.get_methods_source` /
:meth:`~MethodsSourceMixin.set_methods_source`.

RAW PASSTHROUGH: the full buffer round-trips byte-for-byte. Unlike the older
two-pane Methods view (class body + Module strip), this editor does NOT split
or join the source, so interleaved defs / module-level statements keep their
authored order.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import Signal
from mpynode.ui.widgets.editor_core import QtPythonEditor


class NDMethodsSourceEditor(QtPythonEditor):
    """Per-node editor bound to a node's ``_methodsSource`` string attr."""

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
        return self.getText() != self._last_saved_text

    def markSaved(self) -> None:
        """Persist the FULL Methods buffer to the node + reset baseline.

        RAW -- the buffer is stored verbatim (no split/join), so interleaved
        defs / module-level statements keep their authored order."""
        if not self.hasUnsavedChanges():
            return
        text = self.getText()
        try:
            self._py_node.set_methods_source(text)
        except Exception as exc:
            import sys

            sys.stderr.write(
                f"[NDMethodsSourceEditor] set_methods_source failed: {exc}\n")
            return
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    def refresh(self) -> None:
        """Re-pull the FULL buffer from ``_methodsSource`` + reset baseline.

        RAW -- the plug text is loaded verbatim (no split); a blank plug renders
        as a blank tab."""
        try:
            text = self._py_node.get_methods_source() or ""
        except Exception:
            text = ""
        self.setText(text)
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    def _on_text_changed(self) -> None:
        if self._suppress_change_signal:
            return
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())
