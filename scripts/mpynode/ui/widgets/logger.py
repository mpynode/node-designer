"""Log panel widget.

A read-only running log of mPy expression output and errors. Sits in
the right-hand tools tab strip alongside Profile and Watch.

Features:
 * Read-only QPlainTextEdit display
 * Right-click context menu: Clear / Copy All
 * Subscribed to ``mpynode._common.util.log_bus`` — any code calling
 ``log("...")`` posts to all live widgets, so non-UI bridge code
 can route expression output here without holding a widget
 reference
 * Capped buffer (5000 lines) so a runaway expression doesn't
 chew memory
 * Optional level coloring: ``info`` (default), ``warning`` (amber),
 ``error`` (red)

Usage from non-UI code (Qt-free path):

 from mpynode._common.util.log_bus import log
 log("compute() ran in 3.2ms")
 log(f"expression error: {exc}", level="error")

This module re-exports ``log`` and ``_SUBSCRIBERS`` from
``_common.log_bus`` for backwards-compat. Prefer the
``_common.log_bus`` import path for any non-UI producer.
"""

from __future__ import annotations

from mpynode._common.util.log_bus import (  # noqa: F401  (re-exported)
    _SUBSCRIBERS,
    log,
    subscribe as _subscribe,
    unsubscribe as _unregister,
)
from mpynode.ui.qt_wrapper import (
    QAction,
    QHBoxLayout,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    Qt,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


# ``None`` = let Qt pick the default text color, so the log follows the
# active Maya/Qt theme.
LEVEL_COLOR: dict[str, str | None] = {
    "info": None,
    "warning": "#d4a000",  # amber
    "error": "#d44444",  # red
}


def _format_error_maya_style(text: str) -> str:
    """Reformat an error message to mimic Maya's script editor output.

    Each line gets a ``# `` prefix (matches Maya), and the bridge's
    ``[mPyXxx] [<mpyxxx-exec>] expression error: Traceback...`` long
    one-liner is split out by inserting newlines around the marker
    fragments (``Traceback (most recent call last):``, ``  File...``
    indented frames, etc).

    The bridges already pass ``\\n``-delimited tracebacks, but that
    formatting can get squashed when the captured text comes back
    pre-joined. Re-injecting newlines around the well-known anchor
    strings ensures we always render readably.
    """
    # In case the upstream message smashed the traceback onto one line.
    s = text
    for marker in (
        "Traceback (most recent call last):",
        '  File "',
        "    ",  # indented frame body
    ):
        s = s.replace(marker, "\n" + marker)
    # Collapse the double-blanks the inject created.
    while "\n\n" in s:
        s = s.replace("\n\n", "\n")
    s = s.lstrip("\n")
    # Maya's `# ` line convention.
    return "\n".join(f"# {line}" for line in s.split("\n"))


def _preserve_indent_html(line: str) -> str:
    """Replace every space in ``line`` with ``&nbsp;`` so HTML
    doesn't collapse runs of whitespace.

    HTML renderers (Qt's QTextDocument included) collapse multi-space
    runs to a single space \u2014 which destroys the indentation on
    traceback frames like ``  File...`` and ``    exec(...)``, AND
    flattens the ``# `` prefix + indent that ``_format_error_maya_style``
    adds.

    Why blanket-replace every space (not just leading ones)? After the
    Maya-style ``# `` prefix is added, the indentation lives BETWEEN
    the ``#`` and the real content, not at the start of the line. A
    leading-only fix would miss it. Wrapping happens between lines
    via ``<br>`` (each frame is its own line) so we don't lose
    word-break opportunities by using non-breaking spaces here.
    """
    return line.replace(" ", "&nbsp;")


class NDLoggerWidget(QWidget):
    """Log tab \u2014 read-only running log + right-click Clear / Copy All.

    The widget is auto-subscribed to the module-level broadcast bus on
    construction; closing it (or its parent window) auto-unsubscribes.
    """

    # Past this many lines the oldest is dropped per append, so a runaway
    # loop can't eat memory.
    MAX_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Mirrors the right-click action, so the affordance is visible to
        # users who don't think to right-click. Same as Profile's Reset Stats.
        btn_row = QHBoxLayout()
        self._clear_btn = QPushButton("Clear", self)
        self._clear_btn.setToolTip("Clear all log messages.")
        self._clear_btn.clicked.connect(self.clear)
        btn_row.addWidget(self._clear_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Keeps the platform default font. QPlainTextEdit rather than
        # QTextEdit: the cheap choice for plain log output.
        self._editor = QPlainTextEdit(self)
        self._editor.setReadOnly(True)
        self._editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._editor.setMaximumBlockCount(self.MAX_LINES)
        # Our own Clear / Copy All menu instead of Qt's text-edit default.
        self._editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self._editor.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._editor)

        # Any ``log("...")`` call anywhere in the codebase pushes here. The
        # bus is Qt-free, so non-UI producers can import it without Qt.
        _subscribe(self)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_message(self, message: str, level: str = "info") -> None:
        """Append a single message line. ``level`` is one of
        ``info`` / ``warning`` / ``error`` (defaults to ``info``).

        error-level messages are reformatted Maya-style \u2014
        each line prefixed with ``# `` (matches the script editor),
        and newlines preserved so multi-line tracebacks read top-down
        instead of being smashed onto a single line.

        fix: HTML collapses runs of spaces, which destroyed
        the indentation on traceback frames (``  File...``,
        ``    exec(...)``). Convert leading spaces per line to
        ``&nbsp;`` so the indent survives the HTML render."""
        text = str(message).rstrip("\n")
        if not text:
            return
        color = LEVEL_COLOR.get(level)
        if level == "error":
            from html import escape as _escape

            display_text = _format_error_maya_style(text)
            lines_html = [
                _preserve_indent_html(_escape(line))
                for line in display_text.split("\n")
            ]
            html = (
                f'<span style="color: {color or "#d44444"};">'
                + "<br>".join(lines_html)
                + "</span>"
            )
            self._editor.appendHtml(html)
        elif color:
            from html import escape as _escape

            html = f'<span style="color: {color};">{_escape(text)}</span>'
            self._editor.appendHtml(html)
        else:
            # Info: insert with an EXPLICIT default char format. A prior
            # error/warning ``appendHtml`` can leave the document's current
            # char format coloured -- a Qt carry-over that bites
            # intermittently across builds -- which bleeds red/amber into
            # this line. Resetting the cursor's block + char formats to a
            # fresh QTextCharFormat guarantees the theme default.
            from mpynode.ui.qt_wrapper import QTextCharFormat

            try:
                from PySide6.QtGui import QTextCursor
            except Exception:
                from PySide2.QtGui import QTextCursor

            cursor = self._editor.textCursor()
            cursor.movePosition(QTextCursor.End)
            # New paragraph unless still empty -- characterCount() is 1 for
            # an empty QPlainTextEdit.
            if self._editor.document().characterCount() > 1:
                cursor.insertBlock()
            default_fmt = QTextCharFormat()
            cursor.setBlockCharFormat(default_fmt)
            cursor.setCharFormat(default_fmt)
            cursor.insertText(text)
        # Auto-scroll so the latest message is visible.
        sb = self._editor.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def clear(self) -> None:
        """Wipe the log buffer."""
        self._editor.clear()

    def text(self) -> str:
        """Return the current log content (handy for tests + Copy All)."""
        return self._editor.toPlainText()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos):
        menu = QMenu(self._editor)

        clear_action = QAction("Clear", menu)
        clear_action.triggered.connect(self.clear)
        menu.addAction(clear_action)

        copy_action = QAction("Copy All", menu)
        copy_action.triggered.connect(self._copy_all)
        menu.addAction(copy_action)

        menu.exec_(self._editor.mapToGlobal(pos))

    def _copy_all(self) -> None:
        """Push the entire log buffer to the clipboard.

        fix: ``qt_wrapper`` doesn't export ``QApplication``
        (lesson — importing it perturbs Qt platform init).
        Lazy-import ``QGuiApplication`` directly from the bound Qt
        binding instead. ``QGuiApplication.clipboard()`` is a static
        accessor available on both PySide2 and PySide6."""
        try:
            try:
                from PySide6.QtGui import QGuiApplication
            except ImportError:
                from PySide2.QtGui import QGuiApplication

            clipboard = QGuiApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(self.text())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Unsubscribe from the broadcast bus so dead widgets don't
        receive log calls."""
        _unregister(self)
        super().closeEvent(event)
