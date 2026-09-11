"""QtPythonEditor \u2014 QPlainTextEdit subclass with line numbers + Ctrl+wheel zoom.

Notes:
  * The legacy eventFilter approach for Ctrl+wheel never actually
    fired (the editor never calls installEventFilter on itself); we
    override ``wheelEvent`` directly which always works.
  * Falls back to baked-in font defaults if the preferences module
    is unavailable.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import (
    QCheckBox,
    QColor,
    QDesktopServices,
    QEvent,
    QFont,
    QFontMetrics,
    QHBoxLayout,
    QKeySequence,
    QLabel,
    QLineEdit,
    QPainter,
    QPlainTextEdit,
    QPushButton,
    QRect,
    QShortcut,
    QSize,
    Qt,
    QTextEdit,
    QTextFormat,
    QToolTip,
    QUrl,
    QWidget,
)
import re as _re
import sys as _sys
from mpynode.ui.widgets.highlighter import URL_PATTERN, QtPythonHighlighter


def _qt_gui_textdoc():
    """Lazy QTextDocument / QTextCursor import (QtGui), PySide6/2 safe."""
    try:
        from PySide6.QtGui import QTextCursor, QTextDocument
    except Exception:
        from PySide2.QtGui import QTextCursor, QTextDocument
    return QTextDocument, QTextCursor


class _FindLineEdit(QLineEdit):
    """QLineEdit for the editor find bar.

    Routes Return / Shift+Return / Escape to the owning find bar so
    the field behaves like a standard find box (Enter = next,
    Shift+Enter = previous, Esc = close) instead of inserting newlines
    or losing focus.
    """

    def __init__(self, find_bar):
        super().__init__(find_bar)
        self._find_bar = find_bar

    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if mods & Qt.ShiftModifier:
                self._find_bar.find_prev()
            else:
                self._find_bar.find_next()
            event.accept()
            return
        if key == Qt.Key_Escape:
            self._find_bar.close_bar()
            event.accept()
            return
        super().keyPressEvent(event)


class _EditorFindBar(QWidget):
    """Inline find bar overlaid on the top-right of a QtPythonEditor.

    Mirrors the familiar Ctrl/Cmd+F experience: a text field, a live
    match counter (``current/total``), previous / next buttons, a
    case-sensitivity toggle, and a close button. All matches are
    highlighted in the editor; the active match keeps the native
    selection so it's visually distinct.
    """

    _MATCH_BG = QColor(255, 213, 79, 110)   # soft amber, semi-transparent

    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        self.setAutoFillBackground(True)

        row = QHBoxLayout(self)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(3)

        self._line = _FindLineEdit(self)
        self._line.setPlaceholderText("Find")
        self._line.setClearButtonEnabled(True)
        self._line.setMinimumWidth(160)
        self._line.textChanged.connect(self._on_text_changed)
        row.addWidget(self._line)

        self._count_label = QLabel("", self)
        self._count_label.setMinimumWidth(64)
        row.addWidget(self._count_label)

        self._case_cb = QCheckBox("Aa", self)
        self._case_cb.setToolTip("Match case")
        self._case_cb.toggled.connect(self._on_text_changed)
        row.addWidget(self._case_cb)

        self._prev_btn = QPushButton("\u25b2", self)  # up triangle
        self._prev_btn.setToolTip("Previous match (Shift+Enter)")
        self._prev_btn.setFixedWidth(26)
        self._prev_btn.clicked.connect(self.find_prev)
        row.addWidget(self._prev_btn)

        self._next_btn = QPushButton("\u25bc", self)  # down triangle
        self._next_btn.setToolTip("Next match (Enter)")
        self._next_btn.setFixedWidth(26)
        self._next_btn.clicked.connect(self.find_next)
        row.addWidget(self._next_btn)

        self._close_btn = QPushButton("\u2715", self)  # x
        self._close_btn.setToolTip("Close (Esc)")
        self._close_btn.setFixedWidth(26)
        self._close_btn.clicked.connect(self.close_bar)
        row.addWidget(self._close_btn)

        self.adjustSize()
        self.hide()

    # -- public API ----------------------------------------------------

    def open_bar(self, seed_text: str = "") -> None:
        """Show the bar, seed the field (e.g. with the editor's current
        selection), select-all so the user can immediately retype, and
        focus the field."""
        if seed_text:
            self._line.setText(seed_text)
        self.show()
        self.raise_()
        self.reposition()
        self._line.setFocus()
        self._line.selectAll()
        # Refresh highlights for whatever text is in the field.
        self._on_text_changed()

    def close_bar(self) -> None:
        self.hide()
        self._editor.clear_find_highlights()
        self._editor.setFocus()

    def case_sensitive(self) -> bool:
        return self._case_cb.isChecked()

    def search_text(self) -> str:
        return self._line.text()

    def find_next(self) -> None:
        self._editor.find_step(self.search_text(), backward=False,
                               case=self.case_sensitive())
        self._refresh_count()

    def find_prev(self) -> None:
        self._editor.find_step(self.search_text(), backward=True,
                               case=self.case_sensitive())
        self._refresh_count()

    def reposition(self) -> None:
        """Anchor the bar at the top-right corner of the editor's
        content area, clear of the vertical scroll bar."""
        if not self.isVisible():
            return
        self.adjustSize()
        cr     = self._editor.contentsRect()
        margin = 4
        sb     = self._editor.verticalScrollBar()
        sb_w   = sb.width() if (sb is not None and sb.isVisible()) else 0
        x      = cr.right() - self.width() - sb_w - margin
        y      = cr.top() + margin
        self.move(max(cr.left(), x), y)

    # -- internal ------------------------------------------------------

    def _on_text_changed(self, *_args) -> None:
        text = self.search_text()
        # (Re)highlight every occurrence + jump to the first match at
        # or after the current cursor so typing feels live.
        self._editor.update_find_highlights(
            text, self._MATCH_BG, case=self.case_sensitive()
        )
        if text:
            self._editor.find_step(
                text, backward=False, case=self.case_sensitive(),
                from_cursor_start=True,
            )
        self._refresh_count()

    def _refresh_count(self) -> None:
        text = self.search_text()
        total, index = self._editor.find_match_stats(
            text, case=self.case_sensitive()
        )
        if not text:
            self._count_label.setText("")
            self._set_no_results(False)
            return
        if total == 0:
            self._count_label.setText("No results")
            self._set_no_results(True)
            return
        self._set_no_results(False)
        if index > 0:
            self._count_label.setText(f"{index}/{total}")
        else:
            self._count_label.setText(f"{total} found")

    def _set_no_results(self, on: bool) -> None:
        # Tint the field text red when there are no matches.
        self._line.setStyleSheet(
            "color: #ff6b6b;" if on else ""
        )



class QtLineNumberArea(QWidget):
    """The narrow gutter widget that shows line numbers down the editor's left edge."""

    def __init__(self, editor):
        super().__init__(editor)
        self._txt_editor = editor

    def sizeHint(self):
        return QSize(self._txt_editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self._txt_editor.lineNumberAreaPaintEvent(event)


def _default_font_family() -> str:
    """The platform's shipped monospace (Consolas / Monaco / DejaVu Sans Mono),
    through the preferences module so the editor's last-resort font is the one
    the Preferences dialog defaults to. Best-effort, like every other
    preferences import in this module."""
    try:
        from mpynode.ui.preferences import default_editor_font_family

        return default_editor_font_family()
    except Exception:
        return "Courier New"


class QtPythonEditor(QPlainTextEdit):
    """QPlainTextEdit + line numbers + syntax highlighting + Ctrl+wheel font zoom."""

    HIGHLIGHT_COLOR   = Qt.lightGray
    HIGHLIGHTER_CLASS = QtPythonHighlighter

    DEFAULT_FONT_FAMILY    = _default_font_family()
    DEFAULT_FONT_SIZE      = 10
    MIN_FONT_SIZE          = 6
    MAX_FONT_SIZE          = 72
    DEFAULT_LINE_WRAP_MODE = QPlainTextEdit.NoWrap

    TAB_STOP = 4

    def __init__(self, parent=None):
        super().__init__(parent)

        self._highlighter        = self.HIGHLIGHTER_CLASS(self.document())
        self._line_number_widget = QtLineNumberArea(self)
        self.setLineWrapMode(self.DEFAULT_LINE_WRAP_MODE)

        self._font_size = self.DEFAULT_FONT_SIZE
        self._font      = self._build_default_font()

        # Lazy-built on the first completion, so editor construction stays
        # cheap and Qt-free where QCompleter isn't importable.
        self._completer        = None
        self._completion_words = []

        self._initTextAttrs()
        self._initEvents()
        self._wire_pref_listener()

        # Ctrl/Cmd+F find bar (lazily constructed on first use).
        self._find_bar              = None
        self._find_extra_selections = []
        self._install_find_shortcuts()
        self._install_comment_shortcut()

        # Mouse tracking lets the pointing-hand cursor show while the
        # modifier is held over a URL (see the clickable-URL block below).
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    # Clickable URLs (modifier + click opens the link in the browser)
    # ------------------------------------------------------------------

    # Shared with highlighter.py's link styling, so the blue+underline
    # rendering and this click detection agree on what a URL is.
    _URL_RE = _re.compile(URL_PATTERN)

    # ControlModifier maps to Cmd on macOS, so name the key the user presses.
    _URL_HINT = (
        "\u2318+click to open" if _sys.platform == "darwin" else "Ctrl+click to open"
    )

    @staticmethod
    def _url_modifier_held(modifiers) -> bool:
        # Cmd on macOS, Ctrl elsewhere: the standard "follow link" chord.
        return bool(modifiers & Qt.ControlModifier)

    def _url_at_pos(self, pos):
        """Return the URL under the given viewport position, or None."""
        try:
            cursor = self.cursorForPosition(pos)
            line   = cursor.block().text()
            col    = cursor.positionInBlock()
        except Exception:
            return None
        for m in self._URL_RE.finditer(line):
            if m.start() <= col <= m.end():
                return m.group(0)
        return None

    def mouseMoveEvent(self, event):
        try:
            over = self._url_modifier_held(event.modifiers()) and self._url_at_pos(
                event.pos()
            )
            self.viewport().setCursor(
                Qt.PointingHandCursor if over else Qt.IBeamCursor
            )
        except Exception:
            pass
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton and self._url_modifier_held(
                event.modifiers()
            ):
                url = self._url_at_pos(event.pos())
                if url:
                    QDesktopServices.openUrl(QUrl(url))
                    event.accept()
                    return
        except Exception:
            pass
        super().mousePressEvent(event)

    def viewportEvent(self, event):
        # A plain hover (no modifier) shows the "<chord>+click to open" hint,
        # which is what makes the gesture discoverable. QPlainTextEdit mouse
        # events go to the viewport, so the ToolTip help-event lands here.
        try:
            if event.type() == QEvent.ToolTip:
                url = self._url_at_pos(event.pos())
                if url:
                    QToolTip.showText(
                        event.globalPos(), f"{self._URL_HINT}\n{url}", self
                    )
                else:
                    QToolTip.hideText()
                    event.ignore()
                return True
        except Exception:
            pass
        return super().viewportEvent(event)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _build_default_font(self) -> QFont:
        # A fallback only: _initTextAttrs prefers preferences.editor_font().
        font = QFont()
        font.setFamily(self.DEFAULT_FONT_FAMILY)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(self._font_size)
        return font

    def _initTextAttrs(self):
        try:
            from mpynode.ui.preferences import editor_font, get_pref

            self._font      = editor_font()
            self._font_size = int(get_pref("editor_font_size"))
        except Exception:
            # No preferences module: keep the default font built above.
            pass
        self.setFont(self._font)
        self._apply_tab_stop()

    def _apply_tab_stop(self):
        try:
            self.setTabStopDistance(
                self.TAB_STOP * QFontMetrics(self._font).horizontalAdvance(" ")
            )
        except AttributeError:
            # Older Qt fallback
            self.setTabStopWidth(self.TAB_STOP * QFontMetrics(self._font).width(" "))

    def _initEvents(self):
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth()

    def applyPrefsFont(self):
        """Re-apply font from user preferences."""
        try:
            from mpynode.ui.preferences import editor_font, get_pref

            self._font      = editor_font()
            self._font_size = int(get_pref("editor_font_size"))
            self.setFont(self._font)
            self._apply_tab_stop()
        except Exception:
            pass

    def _wire_pref_listener(self):
        """Subscribe to preferences.set_pref notifications so the editor
        font updates live when the user changes ``editor_font_family`` /
        ``editor_font_size`` in the Preferences dialog (no Maya restart
        required). Best-effort -- if the preferences module isn't
        importable we silently skip and fall back to the start-up font.
        """
        try:
            from mpynode.ui.preferences import register_change_listener
            register_change_listener(self._on_pref_changed)
        except Exception:
            pass

    def _on_pref_changed(self, key, value):
        """Re-apply font when a font-related pref is written. Other keys
        are ignored. The handler self-unregisters when the widget has
        been destroyed (the bound method otherwise keeps the dead widget
        alive in the listener registry)."""
        if key not in ("editor_font_family", "editor_font_size"):
            return
        try:
            self.applyPrefsFont()
        except RuntimeError:
            # Widget's C++ side has been deleted; unsubscribe silently.
            try:
                from mpynode.ui.preferences import unregister_change_listener
                unregister_change_listener(self._on_pref_changed)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Layout / line numbers
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_widget.setGeometry(
            QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height())
        )
        if getattr(self, "_find_bar", None) is not None:
            self._find_bar.reposition()

    def lineNumberAreaWidth(self):
        digits = 1
        count  = max(1, self.blockCount())
        while count >= 10:
            count  //= 10
            digits += 1
        try:
            char_width = self.fontMetrics().horizontalAdvance("9")
        except AttributeError:
            char_width = self.fontMetrics().width("9")
        return 3 + char_width * digits

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self._line_number_widget.scroll(0, dy)
        else:
            self._line_number_widget.update(
                0, rect.y(), self._line_number_widget.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth()

    def updateLineNumberAreaWidth(self):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self._line_number_widget)
        painter.fillRect(event.rect(), Qt.lightGray)

        block        = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top          = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom       = top + self.blockBoundingRect(block).height()
        height       = self.fontMetrics().height()

        while block.isValid() and (top <= event.rect().bottom()):
            if block.isVisible() and (bottom >= event.rect().top()):
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                painter.drawText(
                    0,
                    int(top),
                    self._line_number_widget.width(),
                    height,
                    int(Qt.AlignRight),
                    number,
                )
            block  = block.next()
            top    = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    # ------------------------------------------------------------------
    # Ctrl+wheel font zoom (fix: override wheelEvent directly)
    # ------------------------------------------------------------------

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            try:
                delta = event.angleDelta().y()
            except AttributeError:
                delta = event.delta()
            if delta > 0:
                new_size = min(self._font_size + 1, self.MAX_FONT_SIZE)
            else:
                new_size = max(self._font_size - 1, self.MIN_FONT_SIZE)
            if new_size!= self._font_size:
                self.setFontSize(new_size)
            event.accept()
            return
        super().wheelEvent(event)

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def highlightCurrentLine(self):
        extra_selections = []
        if not self.isReadOnly():
            selection  = QTextEdit.ExtraSelection()
            line_color = QColor(self.HIGHLIGHT_COLOR).lighter(160)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def getHighlighter(self):
        return self._highlighter

    def setFontSize(self, size: int):
        self._font_size = int(size)
        self._font.setPointSize(self._font_size)
        self.setFont(self._font)
        self._apply_tab_stop()

    def getFontSize(self) -> int:
        return self._font_size

    # ------------------------------------------------------------------
    # Find bar (Ctrl/Cmd+F)
    # ------------------------------------------------------------------

    def _install_find_shortcuts(self) -> None:
        """Bind the standard Find / FindNext / FindPrevious sequences.

        ``QKeySequence.Find`` maps to Ctrl+F on Windows/Linux and
        Cmd+F on macOS automatically. FindNext/Previous cover F3 /
        Shift+F3 (and Cmd+G / Cmd+Shift+G on macOS). All are scoped to
        this editor + its children so they don\'t collide with the
        rest of the Designer.
        """
        try:
            find_sc = QShortcut(QKeySequence(QKeySequence.Find), self)
            find_sc.setContext(Qt.WidgetWithChildrenShortcut)
            find_sc.activated.connect(self.showFindBar)
            self._find_shortcut = find_sc

            next_sc = QShortcut(QKeySequence(QKeySequence.FindNext), self)
            next_sc.setContext(Qt.WidgetWithChildrenShortcut)
            next_sc.activated.connect(self._find_next_shortcut)
            self._find_next_sc = next_sc

            prev_sc = QShortcut(QKeySequence(QKeySequence.FindPrevious), self)
            prev_sc.setContext(Qt.WidgetWithChildrenShortcut)
            prev_sc.activated.connect(self._find_prev_shortcut)
            self._find_prev_sc = prev_sc
        except Exception:
            # Best-effort: the editor still works without the shortcut
            # (e.g. a Qt build missing QShortcut).
            pass

    def _ensure_find_bar(self) -> "_EditorFindBar":
        if self._find_bar is None:
            self._find_bar = _EditorFindBar(self)
        return self._find_bar

    def showFindBar(self) -> None:
        """Open the find bar, seeding it with the current single-line
        selection (if any) so "select word -> Cmd+F" pre-fills."""
        bar  = self._ensure_find_bar()
        seed = self.textCursor().selectedText()
        # QTextCursor.selectedText() uses U+2029 as the line separator;
        # only seed for single-line selections.
        if "\u2029" in seed:
            seed = ""
        bar.open_bar(seed)

    def _find_next_shortcut(self) -> None:
        if self._find_bar is not None and self._find_bar.isVisible():
            self._find_bar.find_next()
        else:
            self.showFindBar()

    def _find_prev_shortcut(self) -> None:
        if self._find_bar is not None and self._find_bar.isVisible():
            self._find_bar.find_prev()
        else:
            self.showFindBar()

    def _find_flags(self, backward: bool, case: bool):
        """Build a QTextDocument.FindFlags value for the given options."""
        QTextDocument, _QTextCursor = _qt_gui_textdoc()
        flags = QTextDocument.FindFlags()
        if backward:
            flags |= QTextDocument.FindBackward
        if case:
            flags |= QTextDocument.FindCaseSensitively
        return flags

    def find_step(
        self,
        text:     str,
        backward: bool = False,
        case: bool = False,
        from_cursor_start: bool = False,
    ) -> bool:
        """Move to the next/previous match of ``text``, wrapping around
        the document end. Returns True if a match was found.

        ``from_cursor_start`` collapses the cursor to the start of its
        current selection before searching forward -- used while the
        user is typing so the first match at/after the cursor stays
        stable instead of skipping ahead on every keystroke.
        """
        if not text:
            return False
        _QTextDocument, QTextCursor = _qt_gui_textdoc()
        flags = self._find_flags(backward, case)
        if from_cursor_start:
            cursor = self.textCursor()
            cursor.setPosition(cursor.selectionStart())
            self.setTextCursor(cursor)
        found = self.find(text, flags)
        if not found:
            # Wrap to the opposite end + retry once.
            cursor = self.textCursor()
            cursor.movePosition(
                QTextCursor.End if backward else QTextCursor.Start
            )
            self.setTextCursor(cursor)
            found = self.find(text, flags)
        return bool(found)

    def update_find_highlights(self, text: str, color, case: bool = False) -> None:
        """Highlight every occurrence of ``text`` via extra selections.

        Owns the editor\'s extra-selection list while the find bar is
        open (the current-line highlighter is not wired up, so there\'s
        no conflict).
        """
        _QTextDocument, QTextCursor = _qt_gui_textdoc()
        selections = []
        if text:
            flags  = self._find_flags(False, case)
            doc    = self.document()
            cursor = QTextCursor(doc)
            while True:
                cursor = doc.find(text, cursor, flags)
                if cursor.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.format.setBackground(color)
                sel.cursor = cursor
                selections.append(sel)
        self._find_extra_selections = selections
        self.setExtraSelections(selections)

    def clear_find_highlights(self) -> None:
        self._find_extra_selections = []
        self.setExtraSelections([])

    def find_match_stats(self, text: str, case: bool = False):
        """Return ``(total_matches, current_index)``. ``current_index``
        is the 1-based position of the match currently selected, or 0
        if the selection isn\'t exactly on a match."""
        if not text:
            return (0, 0)
        _QTextDocument, QTextCursor = _qt_gui_textdoc()
        flags     = self._find_flags(False, case)
        doc       = self.document()
        sel_start = self.textCursor().selectionStart()
        sel_end   = self.textCursor().selectionEnd()
        total     = 0
        index     = 0
        cursor    = QTextCursor(doc)
        while True:
            cursor = doc.find(text, cursor, flags)
            if cursor.isNull():
                break
            total += 1
            if (cursor.selectionStart() == sel_start
                    and cursor.selectionEnd() == sel_end):
                index = total
        return (total, index)

    # ------------------------------------------------------------------
    # Block indent / comment toggle
    # ------------------------------------------------------------------

    def _install_comment_shortcut(self) -> None:
        """Bind Ctrl+/ (Cmd+/ on macOS) to the comment toggle."""
        try:
            sc = QShortcut(QKeySequence("Ctrl+/"), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(self._toggle_comment_lines)
            self._comment_shortcut = sc
        except Exception:
            pass

    def _apply_text_transform(self, transform) -> None:
        """Apply a pure ``(text, sel_start, sel_end) -> (new_text, ns,
        ne)`` transform to the document in a single undo step, then
        restore the (possibly grown) selection."""
        try:
            from PySide6.QtGui import QTextCursor
        except Exception:
            from PySide2.QtGui import QTextCursor

        cursor    = self.textCursor()
        text      = self.toPlainText()
        sel_start = cursor.selectionStart()
        sel_end   = cursor.selectionEnd()
        new_text, ns, ne = transform(text, sel_start, sel_end)
        if new_text == text:
            return
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()
        restored = self.textCursor()
        restored.setPosition(min(ns, len(new_text)))
        restored.setPosition(min(ne, len(new_text)), QTextCursor.KeepAnchor)
        self.setTextCursor(restored)

    def _indent_selection(self, add: bool = True) -> None:
        """Indent (add=True) / unindent the selected lines (or the
        current line if there\'s no selection)."""
        self._apply_text_transform(
            lambda t, s, e: indent_block(t, s, e, add=add)
        )

    def _toggle_comment_lines(self) -> None:
        """Comment / uncomment the selected lines (or current line)."""
        self._apply_text_transform(toggle_comment)

    # ------------------------------------------------------------------
    # autocomplete
    # ------------------------------------------------------------------

    def setCompletionWords(self, words):
        """Update the editor's autocomplete vocabulary.

        ``words`` is a list[str]. Builds the QCompleter lazily on
        first call. Subsequent calls just replace the wordlist on
        the existing completer.

        Safe to call with an empty list (disables completion until
        the next non-empty call).
        """
        self._completion_words = list(words or [])
        if self._completer is None and self._completion_words:
            from mpynode.ui.widgets.autocomplete import make_completer

            self._completer = make_completer(self, self._completion_words)
            if self._completer is not None:
                self._completer.activated.connect(self._insertCompletion)
        else:
            from mpynode.ui.widgets.autocomplete import update_completer_words

            update_completer_words(self._completer, self._completion_words)

    def getCompletionWords(self):
        """Return the active completion wordlist (used by
        tests + headless probes)."""
        return list(self._completion_words)

    def _currentCompletionPrefix(self) -> str:
        """Extract the word fragment under the cursor that
        the QCompleter should match against. Walks back from the
        cursor through ``[A-Za-z0-9_.]`` characters (dot is included
        so ``self.driverMatrixA`` matches as a single prefix). The
        dot inclusion lets users do prefix-search against the full
        ``self.X.Y`` paths the autocomplete module emits."""
        try:
            from PySide6.QtGui import QTextCursor
        except Exception:
            try:
                from PySide2.QtGui import QTextCursor
            except Exception:
                return ""
        cursor     = self.textCursor()
        block_text = cursor.block().text()
        pos        = cursor.positionInBlock()
        if pos <= 0:
            return ""
        start = pos
        while start > 0:
            ch = block_text[start - 1]
            if ch.isalnum() or ch == "_" or ch == ".":
                start -= 1
            else:
                break
        return block_text[start:pos]

    def _insertCompletion(self, completion_text: str) -> None:
        """Replace the prefix under the cursor with the
        chosen completion. Selects backwards by the prefix length
        and overwrites."""
        if self._completer is None:
            return
        prefix = self._currentCompletionPrefix()
        cursor = self.textCursor()
        # Drop the typed prefix, then insert the full completion.
        for _ in range(len(prefix)):
            cursor.deletePreviousChar()
        cursor.insertText(completion_text)
        self.setTextCursor(cursor)

    # ------------------------------------------------------------------
    # Load / Save context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        """Extend Qt's standard right-click menu with Load
        / Save items so the artist can ferry script source to and
        from disk for sharing / version control / backup.

        Qt's default actions (Undo / Redo / Cut / Copy / Paste /
        Select All) are kept intact -- the new entries appear at
        the bottom under a separator."""
        try:
            menu = self.createStandardContextMenu()

            # From the CLICK point, not the text cursor, so it works with no
            # prior click.
            lineno = col = None
            try:
                tc     = self.cursorForPosition(event.pos())
                lineno = tc.blockNumber() + 1
                col    = tc.columnNumber()
            except Exception:
                lineno = col = None

            # Actions that depend on the token under the cursor: Rename, and
            # Make / Promote to Persistent Variable.
            rename_act  = None
            persist_act = None
            if lineno is not None:
                try:
                    from mpynode._common.util import refactor as _rf

                    kind, word = _rf.classify_at(
                        self.toPlainText(), lineno, col
                    )
                    if kind in ("name", "self_attr") and word:
                        label = (
                            "Rename Variable '{}'...".format(word)
                            if kind == "name"
                            else "Rename 'self.{}'...".format(word)
                        )
                        rename_act         = menu.addAction(label)
                        self._rename_click = (lineno, col)
                except Exception:
                    rename_act = None
                try:
                    from mpynode.ui.widgets.rename_var import (
                        classify_persistable,
                    )

                    pmode, pword = classify_persistable(self, lineno, col)
                    if pmode == "make":
                        persist_act = menu.addAction("Make Persistent Variable")
                    elif pmode == "promote":
                        persist_act = menu.addAction(
                            "Promote to Persistent Variable"
                        )
                    if persist_act is not None:
                        self._persist_click = (lineno, col, pmode, pword)
                except Exception:
                    persist_act = None

            # Hoist above Qt's standard Undo / Cut / Copy entries.
            top_acts = [a for a in (rename_act, persist_act) if a is not None]
            if top_acts:
                first = menu.actions()[0] if menu.actions() else None
                for act in top_acts:
                    menu.insertAction(first, act)
                menu.insertSeparator(first)

            menu.addSeparator()
            comment_act = menu.addAction("Comment / Uncomment Lines")
            menu.addSeparator()
            load_act = None
            if self._offers_file_load():
                load_act = menu.addAction("Load From File...")
            save_act = menu.addAction("Save To File...")
            chosen   = menu.exec_(event.globalPos())
            if rename_act is not None and chosen is rename_act:
                try:
                    from mpynode.ui.widgets.rename_var import run_rename

                    ln, cl = self._rename_click
                    run_rename(self, ln, cl)
                except Exception:
                    pass
            elif persist_act is not None and chosen is persist_act:
                try:
                    from mpynode.ui.widgets.rename_var import run_persist

                    ln, cl, mode, word = self._persist_click
                    run_persist(self, ln, cl, mode, word)
                except Exception:
                    pass
            elif chosen is comment_act:
                self._toggle_comment_lines()
            elif load_act is not None and chosen is load_act:
                # ``is not None`` FIRST: a dismissed menu returns None, which
                # would otherwise match a suppressed (None) load action and pop
                # the file dialog on every cancel.
                self._load_from_file()
            elif chosen is save_act:
                self._save_to_file()
        except Exception:
            super().contextMenuEvent(event)

    def _offers_file_load(self) -> bool:
        """Whether "Load From File..." belongs on this editor's menu.

        False for a surface whose text is a PROJECTION rather than a buffer:
        replacing the document wholesale there desynchronises it from whatever
        it is projecting. Saving out is always fine.
        """
        return True

    def _load_from_file(self) -> None:
        """Prompt for a.py file and REPLACE the editor's
        contents. setPlainText fires textChanged -> the parent
        editor's dirty tracking activates the Save button so the
        artist can commit the loaded text to the node."""
        try:
            from mpynode.ui.qt_wrapper import QFileDialog
        except Exception:
            return
        path, _filter = QFileDialog.getOpenFileName(
            self, "Load script", "",
            "Python files (*.py);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fp:
                text = fp.read()
        except Exception as exc:
            try:
                from mpynode.ui.qt_wrapper import QMessageBox

                QMessageBox.warning(
                    self, "Load Failed",
                    f"Could not read {path}:\n\n{exc}",
                )
            except Exception:
                pass
            return
        self.setPlainText(text)

    def _save_to_file(self) -> None:
        """Prompt for a.py file path and write the
        editor's current contents (utf-8). Note: this is a
        FILE-SYSTEM save, NOT a commit to the Maya node. The
        artist still needs to hit the Save toolbar button to
        push edits into the node's expression/_initSource plug."""
        try:
            from mpynode.ui.qt_wrapper import QFileDialog
        except Exception:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, "Save script", "",
            "Python files (*.py);;All files (*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fp:
                fp.write(self.toPlainText())
        except Exception as exc:
            try:
                from mpynode.ui.qt_wrapper import QMessageBox

                QMessageBox.warning(
                    self, "Save Failed",
                    f"Could not write {path}:\n\n{exc}",
                )
            except Exception:
                pass

    def keyPressEvent(self, event):
        """Route Enter/Tab through the completer popup
        when it's visible (consume the keypress to accept the
        highlighted completion). Otherwise default behavior, then
        on identifier-character keystrokes refresh the popup with
        the current prefix.

        The completer is OPT-IN: until ``setCompletionWords`` has
        been called with a non-empty list, this override is a thin
        passthrough and no popup ever appears.
        """
        # Lazy Qt import, matching the rest of this module.
        try:
            from PySide6.QtCore import Qt as _Qt
        except Exception:
            try:
                from PySide2.QtCore import Qt as _Qt
            except Exception:
                super().keyPressEvent(event)
                return

        completer = self._completer
        popup_visible = (
            completer is not None
            and completer.popup() is not None
            and completer.popup().isVisible()
        )

        if popup_visible:
            # Forward to the popup without inserting into the document.
            if event.key() in (
                _Qt.Key_Enter, _Qt.Key_Return, _Qt.Key_Tab,
                _Qt.Key_Escape, _Qt.Key_Backtab,
            ):
                event.ignore()
                return

        # Shift+Tab arrives as Key_Backtab, or as Tab+Shift on some
        # platforms, and ALWAYS dedents -- the current line when there is no
        # selection. Tab indents only with a selection; a bare Tab falls
        # through to the normal insert.
        if not popup_visible:
            shift = bool(event.modifiers() & _Qt.ShiftModifier)
            if event.key() == _Qt.Key_Backtab or (
                event.key() == _Qt.Key_Tab and shift
            ):
                self._indent_selection(add=False)
                event.accept()
                return
            if event.key() == _Qt.Key_Tab and self.textCursor().hasSelection():
                self._indent_selection(add=True)
                event.accept()
                return
            if event.key() == _Qt.Key_Tab:
                # SPACES to the next tab stop, never a literal tab: mixing
                # the two trips Python's "inconsistent use of tabs" error
                # even though the code looks aligned.
                cursor = self.textCursor()
                col    = cursor.positionInBlock()
                n      = self.TAB_STOP - (col % self.TAB_STOP)
                cursor.insertText(" " * n)
                event.accept()
                return

        super().keyPressEvent(event)

        if completer is None:
            return

        # Refresh the popup with the new prefix now the keypress is in the
        # document. Cheap: filterMode is just a string match on the model.
        prefix = self._currentCompletionPrefix()
        if not prefix or len(prefix) < 2:
            completer.popup().hide() if completer.popup() else None
            return
        if prefix!= completer.completionPrefix():
            completer.setCompletionPrefix(prefix)
            completer.popup().setCurrentIndex(
                completer.completionModel().index(0, 0)
            )
        # Anchor the popup at the cursor position.
        rect = self.cursorRect()
        rect.setWidth(
            completer.popup().sizeHintForColumn(0)
            + completer.popup().verticalScrollBar().sizeHint().width()
        )
        completer.complete(rect)


# ---------------------------------------------------------------------------
# Block indent / comment text transforms (pure, Qt-free, unit-testable)
# ---------------------------------------------------------------------------

INDENT_UNIT = "    "  # 4 spaces (matches QtPythonEditor.TAB_STOP)


def _selected_line_range(text, sel_start, sel_end):
    """Return ``(first_idx, last_idx, lines, starts)`` for the lines the
    selection ``[sel_start, sel_end]`` touches.

    ``lines`` is ``text.split("\n")``; ``starts`` are each line\'s char
    offset. A selection that ends exactly at a line start excludes that
    trailing line (so selecting through the newline of line N doesn\'t
    drag in line N+1) -- unless the selection is a zero-width caret.
    """
    lines  = text.split("\n")
    starts = []
    pos    = 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln) + 1  # + newline

    def line_of(offset):
        idx = 0
        for i, s in enumerate(starts):
            if s <= offset:
                idx = i
            else:
                break
        return idx

    first = line_of(sel_start)
    last  = line_of(sel_end)
    if sel_end > sel_start and last > first and sel_end == starts[last]:
        last -= 1
    return first, last, lines, starts


def _span_after(lines, first, last):
    """Recompute the (start, end) selection covering the full affected
    lines after an edit."""
    starts = []
    pos    = 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln) + 1
    new_start = starts[first]
    new_end   = starts[last] + len(lines[last])
    return new_start, new_end


def indent_block(text, sel_start, sel_end, add=True, unit=INDENT_UNIT):
    """Indent (``add=True``) or unindent the selected lines.

    Returns ``(new_text, new_sel_start, new_sel_end)``. On indent,
    completely-empty lines are left untouched (no trailing whitespace).
    On unindent, a leading ``unit`` (or a tab, or up to ``len(unit)``
    leading spaces) is stripped per line. The resulting selection spans
    the full affected lines so repeated Tab/Shift+Tab keeps working.
    """
    first, last, lines, _starts = _selected_line_range(text, sel_start, sel_end)
    n = len(unit)
    for i in range(first, last + 1):
        ln = lines[i]
        if add:
            if ln != "":
                lines[i] = unit + ln
        else:
            if ln.startswith(unit):
                lines[i] = ln[n:]
            elif ln.startswith("\t"):
                lines[i] = ln[1:]
            else:
                j = 0
                while j < n and j < len(ln) and ln[j] == " ":
                    j += 1
                lines[i] = ln[j:]
    new_text = "\n".join(lines)
    ns, ne = _span_after(lines, first, last)
    return new_text, ns, ne


def toggle_comment(text, sel_start, sel_end, token="#"):
    """Toggle line comments on the selected lines.

    If every non-blank selected line is already commented, uncomment
    them (strip the leading ``token`` + one optional following space);
    otherwise comment them by inserting ``token + " "`` at the minimum
    common indentation column. Blank lines are skipped. Returns
    ``(new_text, new_sel_start, new_sel_end)``.
    """
    first, last, lines, _starts = _selected_line_range(text, sel_start, sel_end)
    idxs     = list(range(first, last + 1))
    nonblank = [i for i in idxs if lines[i].strip() != ""]
    if not nonblank:
        return text, sel_start, sel_end

    def leading_ws(ln):
        return len(ln) - len(ln.lstrip(" \t"))

    all_commented = all(lines[i].lstrip().startswith(token) for i in nonblank)
    if all_commented:
        for i in nonblank:
            ln   = lines[i]
            w    = leading_ws(ln)
            rest = ln[w:]
            if rest.startswith(token):
                rest = rest[len(token):]
                if rest.startswith(" "):
                    rest = rest[1:]
                lines[i] = ln[:w] + rest
    else:
        min_indent = min(leading_ws(lines[i]) for i in nonblank)
        prefix     = token + " "
        for i in nonblank:
            ln       = lines[i]
            lines[i] = ln[:min_indent] + prefix + ln[min_indent:]
    new_text = "\n".join(lines)
    ns, ne = _span_after(lines, first, last)
    return new_text, ns, ne
