"""NDAssistantPanel -- the embedded LLM chat panel (Shape A).

Docked to the right edge of the Node Designer (Cursor-style). Hosts a chat
transcript + input box and drives the selected assistant client (Anthropic or
Gemini, chosen in settings via ``llm.make_client``), whose tool calls
build/edit the working node live (inside undo). The working node is captured
from the host's active tab on the GUI thread at send time (the client's
worker thread must never touch Maya/Qt directly).
"""

from __future__ import annotations

import re
import time

from mpynode.ui.qt_wrapper import (
    QColor,
    QComboBox,
    QFont,
    QFontMetrics,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRect,
    QSize,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    Qt,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextEdit,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)
from mpynode.ui.llm import config as _llm_config


# Provider -> the panel method that lists its models LOCALLY, with no API key.
# Kept beside config.SELF_LISTING_CLI_PROVIDERS (a test holds the two equal): a
# CLI listed there but missing here silently falls back to the API-key path,
# which is the bug that made the Gemini CLI demand a Gemini API key.
_CLI_MODEL_FETCHERS = {
    "claude_cli": "_fetch_claude_cli_models",
    "gemini_cli": "_fetch_gemini_cli_models",
}

# What the Refresh button does, per provider.
_REFRESH_TIPS = {
    "claude_cli": "Re-check which models this `claude` install can run. Uses "
                  "its own login, no API key; each model gets a one-token check "
                  "and the whole pass takes about half a minute",
    "gemini_cli": "Re-read the models the local `gemini` CLI knows",
    "codex_cli":  "Fetch model ids with the OpenAI API key (set it under the "
                  "'ChatGPT (OpenAI API)' provider); or type a model id",
}

# Data roles on the Claude CLI rows, drawn by _ModelRowDelegate. That box is a
# pure dropdown: the item TEXT is the human label the closed box shows, and what
# picking the row saves rides in _ROW_VALUE -- "" on the default row, which
# sends no --model and so follows Claude Code's default, else the exact id.
# Rows that cannot be picked carry no value.
_ROW_VALUE = Qt.UserRole      # what picking the row saves
_ROW_KIND  = Qt.UserRole + 1  # "default" | "header" | "model" | "greyed"
_ROW_LABEL = Qt.UserRole + 2  # display name, or the family on a header
_ROW_CHIPS = Qt.UserRole + 3  # aliases resolving to this row, space-separated
_ROW_RIGHT = Qt.UserRole + 4  # the id, or why the row is greyed

_PICKABLE_KINDS = ("default", "model")

_DATE_STAMP_RE  = re.compile(r"-20\d{6}$")


def _model_root(mid):
    """``claude-haiku-4-5`` for ``claude-haiku-4-5-20251001[1m]``: the part two
    names of one model share. ``[1m]`` picks a context size, not a model, and a
    build stamp is the same model."""
    return _DATE_STAMP_RE.sub("", (mid or "").replace("[1m]", ""))


def _rows_with_also_valid(rows, also_valid, family_of):
    """``rows`` with a pickable row for every ``also_valid`` id. Pure.

    Those ids validated but are not listed (a build stamp, a ``[1m]`` twin);
    they were reachable only by typing, and the box takes no typing. Each goes
    under its family, just after the rows of the same model, so the order stays
    one block per family; a family with no block gets one at the end.
    """
    out = [dict(r) for r in rows or ()]
    for mid in sorted(also_valid or {},
                      key=lambda m: (_model_root(m), m.endswith("[1m]"), m)):
        if any(r.get("id") == mid for r in out):
            continue
        # The CLI names a twin like its listed model ("Sonnet 5" for
        # claude-sonnet-5[1m]); say what differs, as the listed rows do.
        label = also_valid[mid] or mid
        if mid.endswith("[1m]") and "1M" not in label:
            label += " (1M context)"
        stamp = _DATE_STAMP_RE.search(mid.replace("[1m]", ""))
        if stamp and stamp.group(0)[1:] not in label:
            label += " (%s)" % stamp.group(0)[1:]
        row = {"id": mid, "label": label, "family": family_of(mid),
               "aliases": [], "status": "valid", "note": "", "min_version": ""}
        same = [i for i, r in enumerate(out) if r.get("family") == row["family"]]
        root = [i for i in same if _model_root(out[i].get("id")) == _model_root(mid)]
        out.insert((root or same or [len(out) - 1])[-1] + 1, row)
    return out


def _fmt_day(ts):
    try:
        return time.strftime("%Y-%m-%d", time.localtime(float(ts))) if ts else "?"
    except (TypeError, ValueError, OverflowError, OSError):
        return "?"


class _ModelRowDelegate(QStyledItemDelegate):
    """Draws a Claude CLI model row as ``name  [chips]  id``.

    The style paints the background with the text blanked, so hover and
    selection look native, and the three parts are drawn over it: the display
    name, one small chip per alias that resolves to the row today, and the exact
    id right-aligned. A header is its family name with a rule; a greyed row is
    dim throughout. Rows without ``_ROW_KIND`` (the API providers) paint as
    plain items.
    """

    _DIM  = QColor(0x80, 0x80, 0x80)
    _CHIP = QColor(0x93, 0xC3, 0xCD)
    _RULE = QColor(0x50, 0x50, 0x50)
    _PAD  = 6
    _GAP  = 12

    @staticmethod
    def _chip_font(font):
        f  = QFont(font)
        pt = font.pointSize()
        if pt > 0:
            f.setPointSize(max(6, int(round(pt * 0.8))))
        else:
            f.setPixelSize(max(7, int(round(font.pixelSize() * 0.8))))
        return f

    def _parts(self, index):
        label = index.data(_ROW_LABEL) or ""
        right = index.data(_ROW_RIGHT) or ""
        chips = (index.data(_ROW_CHIPS) or "").split()
        return label, chips, ("" if right == label else right)

    def paint(self, painter, option, index):
        kind = index.data(_ROW_KIND)
        if not kind:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget   = getattr(option, "widget", None)
        style    = widget.style() if widget is not None else None
        if style is not None:
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)
        label, chips, right = self._parts(index)
        rect     = QRect(option.rect).adjusted(self._PAD, 0, -self._PAD, 0)
        fm       = QFontMetrics(option.font)
        selected = bool(option.state & QStyle.State_Selected)
        fg = (option.palette.highlightedText() if selected
                    else option.palette.text()).color()
        painter.save()
        try:
            if kind == "header":
                f = QFont(option.font)
                f.setBold(True)
                painter.setFont(f)
                painter.setPen(self._DIM)
                painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, label)
                x = rect.left() + QFontMetrics(f).horizontalAdvance(label) + self._PAD
                y = rect.center().y()
                painter.setPen(self._RULE)
                painter.drawLine(x, y, rect.right(), y)
                return
            dim = kind == "greyed"
            # On the highlight, grey would vanish into it: use its text colour.
            side    = fg if selected else self._DIM
            chip_fg = fg if selected else self._CHIP
            painter.setFont(option.font)
            painter.setPen(side)
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignRight, right)
            room = max(0, rect.width() - fm.horizontalAdvance(right) - self._GAP)
            painter.setPen(self._DIM if dim else fg)
            name = fm.elidedText(label, Qt.ElideRight, room)
            painter.drawText(QRect(rect.left(), rect.top(), room, rect.height()),
                             Qt.AlignVCenter | Qt.AlignLeft, name)
            x     = rect.left() + fm.horizontalAdvance(name) + self._GAP
            limit = rect.left() + room
            cf    = self._chip_font(option.font)
            cfm   = QFontMetrics(cf)
            painter.setFont(cf)
            for chip in chips:
                w = cfm.horizontalAdvance(chip) + 8
                if x + w > limit:
                    break
                h   = cfm.height() + 2
                box = QRect(x, rect.top() + (rect.height() - h) // 2, w, h)
                painter.setPen(chip_fg)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(box, 3, 3)
                painter.drawText(box, Qt.AlignCenter, chip)
                x += w + 4
        finally:
            painter.restore()

    def sizeHint(self, option, index):
        s    = super().sizeHint(option, index)
        kind = index.data(_ROW_KIND)
        if not kind or kind == "header":
            return s
        label, chips, right = self._parts(index)
        fm  = QFontMetrics(option.font)
        cfm = QFontMetrics(self._chip_font(option.font))
        width = (2 * self._PAD + fm.horizontalAdvance(label) + self._GAP
                 + sum(cfm.horizontalAdvance(c) + 12 for c in chips)
                 + (self._GAP + fm.horizontalAdvance(right) if right else 0))
        return QSize(max(s.width(), width), s.height())


def _esc(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )


# Bubble backgrounds: user a touch lighter/bluer than the assistant.
_USER_BG = "#3a4147"
_ASST_BG = "#2b2b2b"

_IMG_MAX_EDGE = 1568  # long-edge downscale cap before sending; saves tokens


def _encode_qimage(img, max_edge=_IMG_MAX_EDGE):
    """QImage -> {"media_type","data"} (downscaled PNG, base64). None on fail."""
    import base64

    try:
        try:
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        except ImportError:
            from PySide2.QtCore import QBuffer, QByteArray, QIODevice

        if img is None or img.isNull():
            return None
        w, h = img.width(), img.height()
        if max(w, h) > max_edge:
            if w >= h:
                img = img.scaledToWidth(max_edge, Qt.SmoothTransformation)
            else:
                img = img.scaledToHeight(max_edge, Qt.SmoothTransformation)
        ba   = QByteArray()
        buf  = QBuffer(ba)
        mode = getattr(QIODevice, "WriteOnly", None)
        if mode is None:  # PySide6 scoped enums
            mode = QIODevice.OpenModeFlag.WriteOnly
        buf.open(mode)
        img.save(buf, "PNG")
        buf.close()
        data = base64.b64encode(bytes(ba.data())).decode("ascii")
        return {"media_type": "image/png", "data": data}
    except Exception:
        return None


import re as _re
import re

from mpynode.ui.widgets.font_prefs import wire_area_font

_MENTION_RE    = _re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)")
_IMAGE_NAME_RE = _re.compile(r"^image\d+$")


def _fmt_duration(secs):
    """Subtle human duration: '4.2s' under a minute, else '1m 05s'."""
    secs = max(0.0, float(secs))
    if secs < 60:
        return "%.1fs" % secs
    m, s = divmod(int(round(secs)), 60)
    return "%dm %02ds" % (m, s)


def _parse_mentions(text):
    """Return (image_names, node_names) referenced via @token in `text`."""
    imgs, nodes = [], []
    for tok in _MENTION_RE.findall(text or ""):
        (imgs if _IMAGE_NAME_RE.match(tok) else nodes).append(tok)
    return imgs, nodes


def _make_thumb_popup(image, max_px=320):
    """A frameless QLabel popup showing `image` (downscaled). None on failure."""
    try:
        try:
            from PySide6.QtWidgets import QLabel
            from PySide6.QtGui import QPixmap
        except ImportError:
            from PySide2.QtWidgets import QLabel
            from PySide2.QtGui import QPixmap
        pm = QPixmap.fromImage(image)
        if pm.isNull():
            return None
        if pm.width() > max_px or pm.height() > max_px:
            pm = pm.scaled(max_px, max_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        lbl = QLabel(None, Qt.ToolTip)  # frameless popup window
        lbl.setPixmap(pm)
        lbl.setStyleSheet("border: 1px solid #555; background: #222;")
        lbl.adjustSize()
        return lbl
    except Exception:
        return None


class _MentionHighlighter(QSyntaxHighlighter):
    """Colors @mentions in the input so they pop out."""

    def __init__(self, document):
        super().__init__(document)
        self._fmt = QTextCharFormat()
        self._fmt.setForeground(QColor("#7fd1ff"))
        try:
            self._fmt.setFontWeight(QFont.Bold)
        except Exception:
            pass

    def highlightBlock(self, text):
        for m in _MENTION_RE.finditer(text or ""):
            self.setFormat(m.start(), m.end() - m.start(), self._fmt)


class _ImageChip(QPushButton):
    """Attachment chip that shows a thumbnail preview on hover."""

    def __init__(self, text, image, parent=None):
        super().__init__(text, parent)
        self._image   = image
        self._preview = None
        self.setToolTip("Hover to preview \u00b7 click to remove")

    def enterEvent(self, event):
        self._preview = _make_thumb_popup(self._image)
        if self._preview is not None:
            gp = self.mapToGlobal(self.rect().topRight())
            self._preview.move(gp.x() + 6, gp.y() - self._preview.height() - 6)
            self._preview.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._preview is not None:
            self._preview.close()
            self._preview = None
        super().leaveEvent(event)


class _ChatInput(QPlainTextEdit):
    """Chat input box that recalls prompt history with Up/Down at the edges.

    Up on the first line walks back through previously sent prompts; Down on
    the last line walks forward (and past the newest back to an empty draft).
    """

    def __init__(self, panel):
        super().__init__(panel)
        self._panel         = panel
        self._completer     = None
        self._hl            = _MentionHighlighter(self.document())  # color @mentions
        self._hover_preview = None
        self._hover_name    = None
        self.setMouseTracking(True)  # for @image hover previews

    def _mention_at_pos(self, pos):
        text = self.toPlainText()
        for m in _MENTION_RE.finditer(text):
            if m.start() <= pos <= m.end():
                return m.group(1)
        return None

    def _hide_hover(self):
        if self._hover_preview is not None:
            self._hover_preview.close()
            self._hover_preview = None
        self._hover_name = None

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        try:
            name = self._mention_at_pos(self.cursorForPosition(event.pos()).position())
            img  = self._panel._image_by_name(name) if name else None
            if img is None:
                self._hide_hover()
            elif name != self._hover_name:
                self._hide_hover()
                popup = _make_thumb_popup(img)
                if popup is not None:
                    gp = self.mapToGlobal(event.pos())
                    popup.move(gp.x() + 12, gp.y() - popup.height() - 10)
                    popup.show()
                    self._hover_preview = popup
                    self._hover_name    = name
        except Exception:
            self._hide_hover()

    def leaveEvent(self, event):
        self._hide_hover()
        super().leaveEvent(event)

    def _ensure_completer(self):
        if self._completer is not None:
            return self._completer
        try:
            try:
                from PySide6.QtWidgets import QCompleter
                from PySide6.QtCore import QStringListModel
            except ImportError:
                from PySide2.QtWidgets import QCompleter
                from PySide2.QtCore import QStringListModel
            comp = QCompleter(self)
            comp.setWidget(self)
            comp.setCompletionMode(QCompleter.PopupCompletion)
            comp.setCaseSensitivity(Qt.CaseInsensitive)
            comp.setModel(QStringListModel([], comp))
            comp.activated.connect(self._insert_completion)
            self._completer = comp
        except Exception:
            self._completer = None
        return self._completer

    def _at_token(self):
        """The @-token under the cursor: (partial, at_pos, cursor_pos) or Nones."""
        pos  = self.textCursor().position()
        text = self.toPlainText()
        i    = pos - 1
        while i >= 0 and (text[i].isalnum() or text[i] == "_"):
            i -= 1
        if i >= 0 and text[i] == "@":
            return text[i + 1:pos], i, pos
        return None, None, None

    def _insert_completion(self, completion):
        partial, at_pos, cur_pos = self._at_token()
        if at_pos is None:
            return
        try:
            try:
                from PySide6.QtGui import QTextCursor
            except ImportError:
                from PySide2.QtGui import QTextCursor
            tc = self.textCursor()
            tc.setPosition(at_pos)
            tc.setPosition(cur_pos, QTextCursor.KeepAnchor)
            tc.insertText("@" + completion + " ")
            self.setTextCursor(tc)
        except Exception:
            pass

    def _update_completer(self):
        comp = self._ensure_completer()
        if comp is None:
            return
        partial, at_pos, _ = self._at_token()
        if at_pos is None:
            comp.popup().hide()
            return
        comp.model().setStringList(self._panel._mention_candidates())
        comp.setCompletionPrefix(partial)
        if comp.completionCount() == 0:
            comp.popup().hide()
            return
        popup = comp.popup()
        popup.setCurrentIndex(comp.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(popup.sizeHintForColumn(0)
                      + popup.verticalScrollBar().sizeHint().width())
        comp.complete(rect)

    def keyPressEvent(self, event):
        comp = self._completer
        if comp is not None and comp.popup().isVisible():
            # Let the popup consume selection/navigation keys.
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape,
                               Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return
        popup_visible = comp is not None and comp.popup().isVisible()
        key           = event.key()
        cur           = self.textCursor()
        if not popup_visible and key == Qt.Key_Up and cur.blockNumber() == 0:
            if self._panel._history_prev():
                return
        elif (not popup_visible and key == Qt.Key_Down
              and cur.blockNumber() == self.blockCount() - 1):
            if self._panel._history_next():
                return
        super().keyPressEvent(event)
        self._update_completer()

    def insertFromMimeData(self, source):
        # Intercept a pasted image (Ctrl+V) -> attachment chip, not raw paste.
        if source is not None and source.hasImage():
            if self._panel._add_image_from_mime(source):
                return
        super().insertFromMimeData(source)


class NDAssistantPanel(QWidget):
    """Right-edge assistant chat panel.

    ``get_current_node`` -> callable returning the active node name (or None).
    ``on_nodes_changed``  -> callable(name) the panel invokes (on the main
                             thread) after the assistant mutates a node, so the
                             host can refresh Attributes / Variables / tabs.
    """

    # Emitted from worker threads (queued to the GUI thread).
    _testFinished  = Signal(bool, str)
    _modelsFetched = Signal(list, str)  # models, provider
    _cliRecheck    = Signal()           # the saved Claude CLI rows are due a full check

    def __init__(self, parent=None, get_current_node=None, on_nodes_changed=None):
        super().__init__(parent)
        self._get_current_node   = get_current_node
        self._host_on_changed    = on_nodes_changed
        self._working_node_name  = None   # captured on GUI thread per send
        self._history            = []     # sent prompts, oldest first
        self._hist_idx           = 0      # cursor into _history (== len => fresh draft)
        self._pending_images     = []     # QImages pasted, awaiting send
        self._session_tokens     = 0      # cumulative tokens this session
        self._loading_settings   = False  # guard combo edits while populating
        self._model_cache        = {}     # provider -> fetched model list (kept until refresh)
        self._cli_current_model  = ""     # claude CLI's active model, from /model
        self._cli_model_displays = {}     # model id -> display name, from /model <id>
        self._cli_rows           = {}     # claude CLI rows payload on screen (build_rows)
        self._cli_rows_fetched   = None   # payload a worker fetched, read on the GUI thread
        self._cli_quick_fetch    = False  # next claude CLI fetch may just re-link saved rows
        self._cli_checking       = False  # a full check may overturn the saved "current"
        self._cli_current_stale  = False  # a re-check began: "current" may be an older CLI's
        self._cli_typed_id       = ""     # explicit id in the box, checked with the rest
        self._turn_ran           = ""     # model id the CLI reported for this turn
        self._turn_want          = ""     # model id this turn asked for, at send
        self._turn_start         = None   # monotonic time the current turn began
        # The saved Claude CLI model as the panel opened: only THAT value is a
        # candidate for the one-time alias pin, never text typed since.
        self._model_at_launch = _llm_config.saved_model("claude_cli")
        # The reply streams in chunks and, for the CLI providers, carries a
        # fenced .mpn payload we must NOT show in chat. Buffer the turn's
        # chunks and re-render ONE bubble with the payload stripped. The
        # bubble is finalized (anchor cleared) whenever other content is
        # appended, so the next chunk starts a fresh one.
        self._asst_buf    = ""    # accumulated raw assistant text for this bubble
        self._asst_anchor = None  # doc position where the live bubble starts

        self._build_ui()
        self._build_client()
        self._testFinished.connect(self._on_test_finished)
        self._modelsFetched.connect(self._on_models_fetched)
        self._cliRecheck.connect(self._on_cli_recheck)
        # Populate the model dropdown on launch (no need to press Refresh).
        self._maybe_autorefresh_models(self._current_provider())

    # -- construction ----------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        header = QHBoxLayout()
        title  = QLabel("<b>AI Assistant</b>", self)
        header.addWidget(title)
        header.addStretch(1)
        self._settings_btn = QPushButton("\u2699", self)  # gear
        self._settings_btn.setFixedWidth(28)
        self._settings_btn.setToolTip("API key / model settings")
        self._settings_btn.clicked.connect(self._toggle_settings)
        header.addWidget(self._settings_btn)
        self._clear_btn = QPushButton("Clear", self)
        self._clear_btn.setToolTip("Clear the conversation")
        self._clear_btn.clicked.connect(self._on_clear)
        header.addWidget(self._clear_btn)
        root.addLayout(header)

        # Settings (hidden by default): provider + API key + model, per-provider.
        self._settings = QWidget(self)
        slay           = QVBoxLayout(self._settings)
        slay.setContentsMargins(0, 0, 0, 0)
        slay.addWidget(QLabel("Provider:", self._settings))
        self._provider_combo = QComboBox(self._settings)
        for prov in _llm_config.PROVIDERS:
            self._provider_combo.addItem(
                _llm_config.PROVIDER_LABELS.get(prov, prov), prov
            )
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        slay.addWidget(self._provider_combo)

        # Reasoning effort (all providers; per-provider). Off = fastest.
        slay.addWidget(QLabel("Reasoning:", self._settings))
        self._effort_combo = QComboBox(self._settings)
        for lv in _llm_config.EFFORT_LEVELS:
            self._effort_combo.addItem("Off" if lv == "off" else lv.capitalize(), lv)
        self._effort_combo.setToolTip("Extended thinking effort -- more careful "
                                      "but slower/costlier. Off is fastest.")
        self._effort_combo.currentIndexChanged.connect(self._on_effort_changed)
        slay.addWidget(self._effort_combo)

        # Shown for ALL providers -- Claude CLI takes --model too. Between
        # Reasoning and the key section, so an API provider reads
        # Provider -> Reasoning -> Model -> API key.
        slay.addWidget(QLabel("Model:", self._settings))
        # Typeable for every provider but the Claude CLI, whose box is a pure
        # dropdown: _load_model switches it per provider (_set_model_editable).
        self._model_edit = QComboBox(self._settings)
        # Enter must not append what was typed as a new row.
        self._model_edit.setInsertPolicy(QComboBox.NoInsert)
        self._model_row_delegate = _ModelRowDelegate(self._model_edit)
        self._model_edit.setItemDelegate(self._model_row_delegate)
        # Text for a typed id; index for a Claude CLI row, whose text is only
        # its label -- what it saves rides in _ROW_VALUE.
        self._model_edit.currentTextChanged.connect(self._save_model)
        self._model_edit.currentTextChanged.connect(self._update_runs_line)
        self._model_edit.currentIndexChanged.connect(self._save_model)
        self._model_edit.currentIndexChanged.connect(self._update_runs_line)
        self._model_edit.activated.connect(self._on_model_picked)
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.addWidget(self._model_edit, 1)
        self._refresh_models_btn = QPushButton("\u21bb", self._settings)
        self._refresh_models_btn.setFixedWidth(28)
        self._refresh_models_btn.clicked.connect(self._on_refresh_models)
        model_row.addWidget(self._refresh_models_btn)
        slay.addLayout(model_row)

        # Claude CLI only: what the box will actually run, and anything the
        # installed CLI is too old for.
        self._runs_label = QLabel("", self._settings)
        self._runs_label.setWordWrap(True)
        self._runs_label.setTextFormat(Qt.RichText)
        self._runs_label.setStyleSheet("color: #888;")  # size via QFont
        wire_area_font(self._runs_label, "assistant", rel=0.85)
        self._runs_label.setVisible(False)
        slay.addWidget(self._runs_label)

        # API key + Test connection -- HTTP providers only (hidden for Claude CLI).
        self._api_section = QWidget(self._settings)
        alay              = QVBoxLayout(self._api_section)
        alay.setContentsMargins(0, 0, 0, 0)
        alay.addWidget(QLabel("API key:", self._api_section))
        self._key_edit = QLineEdit(self._api_section)
        self._key_edit.setEchoMode(QLineEdit.Password)
        self._key_edit.editingFinished.connect(self._save_key)
        alay.addWidget(self._key_edit)
        self._test_btn = QPushButton("Test connection", self._api_section)
        self._test_btn.setToolTip("Verify the API key + model with a free "
                                  "read-only request (no tokens used)")
        self._test_btn.clicked.connect(self._on_test)
        alay.addWidget(self._test_btn)
        slay.addWidget(self._api_section)

        # Claude CLI note (shown only when that provider is selected).
        self._cli_note = QLabel(
            "Uses your machine's `claude` login \u2014 no API key needed. "
            "Node Designer runs claude in the background; it replies with a node "
            "definition that is applied to the active node (no extra packages).",
            self._settings)
        self._cli_note.setWordWrap(True)
        # Size deliberately NOT in the stylesheet: a stylesheet font-size
        # beats setFont(), so it would pin this label while the rest of
        # the panel scaled. Colour only here, size via QFont below.
        self._cli_note.setStyleSheet("color: #888;")
        wire_area_font(self._cli_note, "assistant", rel=0.85)
        slay.addWidget(self._cli_note)

        self._settings.setVisible(False)
        root.addWidget(self._settings)
        self._load_settings_fields()

        # Draggable vertical splitter so the input box can be given more room.
        # Neither pane may collapse to nothing (setChildrenCollapsible(False)
        # plus per-pane minimum heights).
        self._splitter = QSplitter(Qt.Vertical, self)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(6)

        self._transcript = QTextEdit(self)
        wire_area_font(self._transcript, "assistant",
                       on_change=self._on_assistant_font)
        self._asst_pt_applied = self._asst_pt()
        self._transcript.setReadOnly(True)
        self._transcript.setMinimumWidth(280)
        self._transcript.setMinimumHeight(120)  # transcript can't collapse
        self._splitter.addWidget(self._transcript)

        # Animated "working" indicator (self-contained; no QProgressBar dep).
        self._spin_frames = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"
        self._spin_i      = 0
        self._status_msg  = ""
        self._spin_timer  = QTimer(self)
        self._spin_timer.setInterval(110)
        self._spin_timer.timeout.connect(self._tick_spinner)

        # Live rate-limit countdown (updates the status text once per second).
        self._retry_left  = 0
        self._retry_label = "Rate limited"
        self._retry_info  = ""
        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(1000)
        self._retry_timer.timeout.connect(self._tick_retry)

        bottom = QWidget(self._splitter)
        blay   = QVBoxLayout(bottom)
        blay.setContentsMargins(0, 0, 0, 0)
        blay.setSpacing(4)
        self._status = QLabel("", bottom)
        self._status.setStyleSheet("color: #888;")
        blay.addWidget(self._status)

        # Local requests/60s (Google has no live-quota API) + session tokens.
        self._usage_label = QLabel("", bottom)
        self._usage_label.setStyleSheet("color: #666;")  # size via QFont
        wire_area_font(self._usage_label, "assistant", rel=0.85)
        blay.addWidget(self._usage_label)
        self._usage_timer = QTimer(self)
        self._usage_timer.setInterval(1000)
        self._usage_timer.timeout.connect(self._update_usage)
        self._usage_timer.start()

        # Attachments strip (chips for pasted images); hidden when empty.
        self._attach_box    = QWidget(bottom)
        self._attach_layout = QHBoxLayout(self._attach_box)
        self._attach_layout.setContentsMargins(0, 0, 0, 0)
        self._attach_layout.setSpacing(4)
        self._attach_layout.addStretch(1)
        self._attach_box.setVisible(False)
        blay.addWidget(self._attach_box)

        in_row      = QHBoxLayout()
        self._input = _ChatInput(self)  # panel ref kept for history recall
        wire_area_font(self._input, "assistant")
        self._input.setPlaceholderText(
            "Ask the assistant to build or edit a node\u2026  "
            "paste an image, then Ctrl+Enter to send"
        )
        # Roughly four lines at the default size. Was 48 -- two lines --
        # which read as an afterthought next to the Send button.
        self._input.setMinimumHeight(72)
        in_row.addWidget(self._input, 1)
        # One toggle button: "Send" when idle, "Stop" while working. Fills the
        # input height via a vertical Expanding size policy.
        self._action_btn = QPushButton("Send", bottom)
        self._action_btn.setToolTip("Send the prompt (becomes Stop while working)")
        self._action_btn.setMinimumWidth(64)
        try:
            try:
                from PySide6.QtWidgets import QSizePolicy
            except ImportError:
                from PySide2.QtWidgets import QSizePolicy
            self._action_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        except Exception:
            pass
        self._action_btn.clicked.connect(self._on_action)
        in_row.addWidget(self._action_btn)
        blay.addLayout(in_row)
        # Floor for the input area, so the divider can't collapse it.
        bottom.setMinimumHeight(96)
        self._splitter.addWidget(bottom)

        # The transcript soaks up extra window height; the input keeps its
        # size unless the user drags the divider.
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        # 260 is the tools pane default (Log | Watch | Profile, set in
        # mpynode_designer as right_split [610, 260]), so the prompt box
        # comes up the same height as the panel across from it instead of
        # the crushed two-line strip 110 gave.
        self._splitter.setSizes([1000, 260])
        root.addWidget(self._splitter, 1)

        # Ctrl+Enter to send.
        from mpynode.ui.qt_wrapper import QShortcut, QKeySequence

        self._send_sc = QShortcut(QKeySequence("Ctrl+Return"), self._input)
        self._send_sc.activated.connect(self._on_send)

        self._append_system(
            "Hi! Tell me what node to build \u2014 e.g. \u201cmake a locator that "
            "draws my name waving over time\u201d or \u201cadd a float 'blend' "
            "input and use it in the expression\u201d. I edit the node live."
        )
        self._set_idle_status()

    def _build_client(self):
        from mpynode.ui.llm import make_client

        self._client = make_client(self._make_ctx, parent=self)
        self._client.assistantText.connect(self._append_assistant)
        self._client.toolStarted.connect(self._append_tool_start)
        self._client.toolFinished.connect(self._append_tool_done)
        self._client.notice.connect(self._append_notice)
        self._client.thinking.connect(self._append_thinking)
        self._client.retryScheduled.connect(self._on_retry_scheduled)
        self._client.tokensUsed.connect(self._on_tokens_used)
        self._client.errorOccurred.connect(self._append_error)
        self._client.busyChanged.connect(self._on_busy)
        self._client.turnFinished.connect(self._on_turn_finished)
        if hasattr(self._client, "modelRan"):  # Claude CLI only
            self._client.modelRan.connect(self._on_model_ran)

    # -- ToolContext provider (runs on worker thread: NO Maya/Qt calls) --

    def _make_ctx(self):
        from mpynode.ui.llm.tools import ToolContext

        return ToolContext(
            working_node     = self._working_node_name,
            on_nodes_changed = self._notify_changed,
        )

    def _capture_working_node(self):
        """Capture the Designer's active node (GUI thread) for this turn. Both
        provider paths read it through the per-turn ``ToolContext`` (``_make_ctx``):
        the API providers seed it as the tool ``working_node``, and the CLI
        providers serialize it into the payload prompt so the agent edits the node
        the user is on instead of building a fresh orphan."""
        self._working_node_name = None
        if callable(self._get_current_node):
            try:
                self._working_node_name = self._get_current_node()
            except Exception:
                self._working_node_name = None

    def _notify_changed(self, name):
        # Called from a tool on the main thread, so touching Qt / the host is
        # safe. Refreshes the host UI so new attrs/expressions show.
        if callable(self._host_on_changed):
            try:
                self._host_on_changed(name)
            except Exception:
                pass

    # -- send ------------------------------------------------------------

    def _on_send(self):
        if self._client and self._client.is_busy():
            return
        text = self._input.toPlainText().strip()
        # Encode pasted images on the GUI thread into base64 PNGs named
        # image1.., so an @imageN mention can correlate.
        images = []
        for i, img in enumerate(self._pending_images):
            enc = _encode_qimage(img)
            if enc:
                enc["name"] = "image%d" % (i + 1)
                images.append(enc)
        if not text and not images:
            return
        # What this turn asks for, for the footer to compare against.
        self._turn_want = (_llm_config.get_model("claude_cli")
                           or (self._cli_rows or {}).get("default_id", ""))
        # HERE, on the GUI thread, so the worker never queries Maya. Seeds
        # BOTH provider paths.
        self._capture_working_node()
        if text and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self._hist_idx = len(self._history)
        self._append_user(text, n_images=len(images))
        # The provider is locked while busy, so this matches who actually
        # replies even if the user switches later.
        self._append_agent_header()
        self._input.clear()
        self._pending_images = []
        self._refresh_attach_strip()
        # Transcript shows the original text; the model receives @node context.
        sent_text = self._resolve_mentions(text) if text else text
        self._client.send(sent_text, images=images)

    # -- image attachments ----------------------------------------------

    def _add_image_from_mime(self, source) -> bool:
        try:
            try:
                from PySide6.QtGui import QImage
            except ImportError:
                from PySide2.QtGui import QImage

            data = source.imageData()
            img  = data if isinstance(data, QImage) else QImage(data)
            if img is None or img.isNull():
                return False
            self._pending_images.append(img)
            self._refresh_attach_strip()
            return True
        except Exception:
            return False

    def _remove_image(self, index):
        if 0 <= index < len(self._pending_images):
            del self._pending_images[index]
            self._refresh_attach_strip()

    def _refresh_attach_strip(self):
        # Clear existing chip widgets (keep the trailing stretch).
        while self._attach_layout.count() > 1:
            item = self._attach_layout.takeAt(0)
            w    = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        for i, img in enumerate(self._pending_images):
            chip = _ImageChip("\U0001f5bc image%d \u2715" % (i + 1), img, self._attach_box)
            chip.clicked.connect(lambda _=False, idx=i: self._remove_image(idx))
            self._attach_layout.insertWidget(self._attach_layout.count() - 1, chip)
        self._attach_box.setVisible(bool(self._pending_images))

    # -- @-mentions (images + scene nodes) ------------------------------

    def _scene_mpy_nodes(self):
        try:
            import maya.cmds as mc
            from mpynode._node_registry import REGISTRY

            nodes = mc.ls(type=list(REGISTRY.keys())) or []
            return sorted(set(nodes))
        except Exception:
            return []

    def _mention_candidates(self):
        """Names offered by the @-completer: attached images + scene nodes."""
        names = ["image%d" % (i + 1) for i in range(len(self._pending_images))]
        return names + self._scene_mpy_nodes()

    def _image_by_name(self, name):
        """The pending QImage for an @imageN name (or None)."""
        if not name or not _IMAGE_NAME_RE.match(name):
            return None
        try:
            idx = int(name[len("image"):]) - 1
        except Exception:
            return None
        if 0 <= idx < len(self._pending_images):
            return self._pending_images[idx]
        return None

    def _node_context(self, name, cap=4000):
        """Compact, read-only context for an @referenced node (or '')."""
        try:
            import maya.cmds as mc
            import mpynode

            if not mc.objExists(name):
                return ""
            w = mpynode.wrap_node(name)
            if w is None:
                return ""

            def _fmt(m):
                return ", ".join("%s:%s" % (k, (v or {}).get("attr_type"))
                                 for k, v in (m or {}).items()) or "(none)"

            try:
                ins = w.get_input_attr_map()
            except Exception:
                ins = {}
            try:
                outs = w.get_output_attr_map()
            except Exception:
                outs = {}
            try:
                compute = (w.get_compute_expression() or "")[:cap]
            except Exception:
                compute = ""
            try:
                init = (w.get_init_expression() or "")[:cap]
            except Exception:
                init = ""
            lines = ["@%s (%s):" % (name, mc.nodeType(name)),
                     "  inputs: %s" % _fmt(ins),
                     "  outputs: %s" % _fmt(outs)]
            if init.strip():
                lines.append("  init:\n    " + init.replace("\n", "\n    "))
            if compute.strip():
                lines.append("  compute:\n    " + compute.replace("\n", "\n    "))
            return "\n".join(lines)
        except Exception:
            return ""

    def _resolve_mentions(self, text):
        """Prefix the prompt with context for any @nodeName it references."""
        _imgs, nodes = _parse_mentions(text)
        ctxs = []
        seen = set()
        for n in nodes:
            if n in seen:
                continue
            seen.add(n)
            c = self._node_context(n)
            if c:
                ctxs.append(c)
        if not ctxs:
            return text
        return ("[Referenced nodes]\n" + "\n\n".join(ctxs)
                + "\n[/Referenced nodes]\n\n" + text)

    # -- prompt history (Up/Down in the input) --------------------------

    def _history_prev(self) -> bool:
        if not self._history:
            return False
        if self._hist_idx > 0:
            self._hist_idx -= 1
            self._set_input(self._history[self._hist_idx])
        return True  # consume Up so the cursor doesn't jump

    def _history_next(self) -> bool:
        if not self._history or self._hist_idx >= len(self._history):
            return False
        self._hist_idx += 1
        if self._hist_idx >= len(self._history):
            self._set_input("")  # past newest -> empty draft
        else:
            self._set_input(self._history[self._hist_idx])
        return True

    def _set_input(self, text):
        self._input.setPlainText(text)
        try:
            try:
                from PySide6.QtGui import QTextCursor
            except ImportError:
                from PySide2.QtGui import QTextCursor
            self._input.moveCursor(QTextCursor.End)
        except Exception:
            pass

    def seed_compile_context(self, handoff):
        """Public entry point for the "Compile with AI" concierge (WS2).

        Pre-fill the input with a starter prompt built from a native-compile
        hand-off (see ``ui.llm.compile_bridge.build_handoff``) so the user can
        review/edit before pressing send. Returns the text placed in the input.
        Never raises on a malformed hand-off: it degrades to whatever text
        ``compile_bridge`` produces. It only SEEDS the conversation: nothing is
        sent, and nothing recompiles, without a human press."""
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(handoff)
        self._set_input(text)
        return text

    def _on_clear(self):
        self._client.reset()
        self._transcript.clear()
        self._append_system("Conversation cleared.")

    # -- font scaling ---------------------------------------------------
    # The transcript is ONE QTextEdit fed HTML, and eleven call sites author an
    # inline font-size. Inline CSS becomes an explicit char format on the
    # inserted characters, which outranks both setFont() and
    # document().setDefaultFont() -- so without the two helpers below, raising
    # the assistant font would resize the message bubbles and silently leave
    # every grey progress line ("apply mPyNode ... compute", "done in 1m 06s")
    # at its old size.
    #
    # Rather than rewrite eleven differently-shaped format strings, the authored
    # px literals are kept AS RELATIVE INTENT and converted here, in the two
    # funnels every insertion passes through. Qt's rich-text CSS subset only
    # honours pt and px for font-size -- em and % silently do nothing -- so the
    # number is computed in Python.
    _AUTHORED_BASE_PX = 12      # what the px literals were authored against
    _SIZE_PX_RE       = re.compile(r"font-size:\s*(\d+)px")
    _SIZE_PT_RE       = re.compile(r"font-size:\s*([0-9.]+)pt")

    def _asst_pt(self) -> int:
        try:
            from mpynode.ui.preferences import resolve_font_size

            return resolve_font_size("assistant")
        except Exception:
            return 10

    def _scale_html(self, html: str) -> str:
        """Convert authored ``font-size:Npx`` to a pt size relative to the
        configured assistant size. Floored at 6pt so a small setting cannot
        make the progress lines illegible."""
        base = self._asst_pt()

        def _sub(m):
            rel = int(m.group(1)) / float(self._AUTHORED_BASE_PX)
            return "font-size:%dpt" % max(6, int(round(base * rel)))

        return self._SIZE_PX_RE.sub(_sub, html)

    def _rescale_existing(self, ratio: float) -> bool:
        """Multiply every explicit pt size already in the document by ``ratio``.

        Text already inserted keeps its char formats, so a live change has to
        touch the existing document too. Done proportionally off toHtml() --
        which round-trips streamed bubbles as well as appended ones -- rather
        than by replaying a recorded history, which would lose anything the
        streaming path inserted by cursor.

        Returns False if it declined (mid-stream, or nothing to do).
        """
        if self._asst_anchor is not None:
            return False        # a live bubble is being rewritten; don't fight it
        if not ratio or abs(ratio - 1.0) < 1e-6:
            return False
        try:
            html = self._transcript.toHtml()
        except RuntimeError:
            return False

        def _sub(m):
            return "font-size:%dpt" % max(6, int(round(float(m.group(1)) * ratio)))

        sb     = self._transcript.verticalScrollBar()
        at_end = sb.value() >= sb.maximum() - 2
        self._transcript.setHtml(self._SIZE_PT_RE.sub(_sub, html))
        if at_end:
            sb.setValue(sb.maximum())
        return True

    def _on_assistant_font(self) -> None:
        """assistant_font_size changed: rescale what is already on screen."""
        new                   = self._asst_pt()
        old                   = getattr(self, "_asst_pt_applied", None)
        self._asst_pt_applied = new
        if old:
            self._rescale_existing(float(new) / float(old))

    # -- transcript helpers ---------------------------------------------

    def _append(self, html: str):
        # Non-assistant content ends the live bubble, so the next chunk starts
        # a new one and its payload strip is scoped to that bubble's text.
        self._finalize_asst_stream()
        self._transcript.append(self._scale_html(html))
        sb = self._transcript.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _finalize_asst_stream(self) -> None:
        """Close the current live assistant bubble (leave it in place); the next
        assistant chunk begins a fresh bubble."""
        self._asst_anchor = None
        self._asst_buf    = ""

    def _cursor(self):
        try:
            from PySide6.QtGui import QTextCursor
        except Exception:
            from PySide2.QtGui import QTextCursor
        return QTextCursor

    def _asst_bubble_html(self, body_html: str) -> str:
        return ('<table width="100%%" cellspacing="0" cellpadding="7"><tr>'
                '<td bgcolor="%s"><span style="color:%s;">%s</span></td>'
                '</tr></table>' % (_ASST_BG, "#e6e6e6", body_html))

    def _render_asst_bubble(self, body_html: str) -> None:
        """Insert or replace the current live assistant bubble in place."""
        QTextCursor = self._cursor()
        html        = self._scale_html(self._asst_bubble_html(body_html))
        cur         = self._transcript.textCursor()
        if self._asst_anchor is None:
            cur.movePosition(QTextCursor.End)
            self._asst_anchor = cur.position()
            cur.insertHtml(html)
        else:
            cur.setPosition(self._asst_anchor)
            cur.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            cur.removeSelectedText()
            cur.insertHtml(html)
        sb = self._transcript.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _spacer(self):
        self._append('<div style="font-size:7px;line-height:7px;">&nbsp;</div>')

    def _bubble(self, body_html, bg, color):
        self._append(
            '<table width="100%%" cellspacing="0" cellpadding="7"><tr>'
            '<td bgcolor="%s"><span style="color:%s;">%s</span></td>'
            '</tr></table>' % (bg, color, body_html)
        )

    def _append_user(self, text, n_images=0):
        self._spacer()
        body = "<b>You</b><br>%s" % _esc(text)
        if n_images:
            chips = " ".join("\U0001f5bc [image]" for _ in range(n_images))
            body += '<br><span style="color:#9cc;font-size:11px;">%s</span>' % chips
        self._bubble(body, _USER_BG, "#eaf2f7")
        self._spacer()  # same gap below, before the agent's reply

    def _append_agent_header(self):
        provider = self._current_provider()
        try:
            model = _llm_config.get_model(provider)
        except Exception:
            model = ""
        # Drop the dropdown's "(no key)" hint, and the model suffix when the
        # provider has no model.
        label = ("Claude CLI" if provider == "claude_cli"
                 else _llm_config.PROVIDER_LABELS.get(provider, provider))
        if provider == "claude_cli":
            # A name, not an id -- and a blank box says what it resolves to.
            current = (self._cli_rows or {}).get("current", "")
            model = (self._cli_model_displays.get(model, model) if model
                       else "default \u2192 %s" % current if current else "")
        suffix = (" \u00b7 %s" % _esc(model)) if model else ""
        self._append(
            '<div style="color:#9cc;font-size:11px;margin-top:6px;margin-left:2px;">'
            '<b>%s</b>%s</div>' % (_esc(label), suffix)
        )

    def _append_assistant(self, text):
        # Re-render ONE bubble with the fenced .mpn payload stripped; it is
        # applied via the tool spine, not shown in chat. While only the payload
        # has streamed the prose is empty, so show a placeholder that
        # _on_turn_finished resolves to a "definition applied" note.
        from mpynode.ui.llm import payload as _payload

        self._asst_buf += text
        disp = _payload.strip_payload_for_display(self._asst_buf)
        if disp:
            body = _esc(disp).replace("\n", "<br>")
        else:
            body = ('<span style="color:#8a8;font-style:italic;">'
                    'building node…</span>')
        self._render_asst_bubble(body)

    def _finalize_asst_bubble_if_empty(self) -> None:
        """At turn end, if the live bubble's stripped prose is empty, resolve the
        transient placeholder: a payload-only reply becomes a short applied note;
        a truly empty reply is removed."""
        if self._asst_anchor is None:
            return
        from mpynode.ui.llm import payload as _payload

        if _payload.strip_payload_for_display(self._asst_buf).strip():
            return  # real prose already shown
        had_payload = _payload.extract_payload(self._asst_buf) is not None
        QTextCursor = self._cursor()
        cur         = self._transcript.textCursor()
        cur.setPosition(self._asst_anchor)
        cur.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        cur.removeSelectedText()
        if had_payload:
            cur.insertHtml(
                '<table width="100%%" cellspacing="0" cellpadding="7"><tr>'
                '<td bgcolor="%s"><span style="color:#9c9;font-style:italic;">'
                '✓ Node definition applied.</span></td></tr></table>'
                % _ASST_BG)
        self._finalize_asst_stream()

    def _append_tool_start(self, summary):
        self._append('<div style="color:#7aa;font-size:11px;margin-left:8px;">'
                     '\u2699 %s\u2026</div>' % _esc(summary))

    def _append_tool_done(self, line):
        self._append('<div style="color:#6a6;font-size:11px;margin-left:8px;">'
                     '\u2713 %s</div>' % _esc(line))

    def _append_thinking(self, text):
        t = (text or "").strip()
        if not t:
            return
        if len(t) > 240:  # keep the trace subtle/compact
            t = t[:240] + "\u2026"
        self._append('<div style="color:#777;font-style:italic;font-size:10px;'
                     'margin-left:8px;">\U0001f9e0 %s</div>' % _esc(t))

    def _append_notice(self, text):
        self._status_msg = text
        self._status.setText(text)
        self._append('<div style="color:#dca54c;font-size:11px;">\u23f3 %s</div>'
                     % _esc(text))

    def _append_error(self, text):
        self._append('<div style="color:#e77;margin-top:4px;"><b>Error:</b> %s</div>'
                     % _esc(text))

    def _append_system(self, text):
        self._append('<div style="color:#888;font-style:italic;">%s</div>' % _esc(text))

    # -- state -----------------------------------------------------------

    def _on_busy(self, busy):
        self._action_btn.setText("Stop" if busy else "Send")
        self._input.setReadOnly(busy)
        # Settings can't change mid-request. Stop lives outside this.
        self._settings.setEnabled(not busy)
        if busy:
            self._turn_start = time.monotonic()
            self._turn_ran   = ""
            self._status_msg = "Working\u2026"
            self._spin_i     = 0
            self._spin_timer.start()
            self._tick_spinner()
        else:
            self._set_idle_status()

    def _on_action(self):
        """Single button: cancel if a turn is running, else send."""
        if self._client and self._client.is_busy():
            try:
                self._client.cancel()
            except Exception:
                pass
        else:
            self._on_send()

    def _tick_spinner(self):
        frame = self._spin_frames[self._spin_i % len(self._spin_frames)]
        self._spin_i += 1
        self._status.setText("%s %s" % (frame, self._status_msg or "Working\u2026"))

    def _on_turn_finished(self):
        # Resolve the live bubble BEFORE the marker below appends and clears
        # the anchor.
        self._finalize_asst_bubble_if_empty()
        # How long the work took; also signals the agent is waiting.
        if self._turn_start is not None:
            elapsed          = time.monotonic() - self._turn_start
            self._turn_start = None
            self._append(
                '<div style="color:#666;font-size:10px;margin-left:8px;">'
                '\u23f1 done in %s%s</div>' % (_fmt_duration(elapsed),
                                               self._turn_ran_html()))
        self._set_idle_status()

    def _on_model_ran(self, model_id):
        self._turn_ran = str(model_id or "")

    def _turn_ran_html(self):
        """`` \u00b7 ran <id>`` for the turn that just ended -- amber when it is not
        the model the box asked for (a retired id the CLI silently remaps)."""
        ran, self._turn_ran = self._turn_ran, ""
        want, self._turn_want = self._turn_want, ""
        if not ran:
            return ""
        if want and _model_root(want) != _model_root(ran):
            return (' \u00b7 <span style="color:#dca54c;">ran %s (asked for %s)'
                    '</span>' % (_esc(ran), _esc(want)))
        return " \u00b7 ran %s" % _esc(ran)

    def _set_idle_status(self):
        """Green 'Ready' indicator so it's clear nothing is running."""
        self._spin_timer.stop()
        self._retry_timer.stop()
        self._status_msg = ""
        self._status.setText('<span style="color:#6a6;">\u25cf Ready</span>')

    # -- live rate-limit countdown --------------------------------------

    def _on_retry_scheduled(self, code, seconds, attempt, max_retries, detail=""):
        self._retry_left  = max(0, int(seconds))
        base              = "Rate limited" if code == 429 else "Service busy"
        self._retry_label = base + ((" \u00b7 %s" % detail) if detail else "")
        self._retry_info  = "(%d/%d)" % (attempt, max_retries)
        # One transcript record per retry, then start the countdown.
        self._append('<div style="color:#dca54c;font-size:11px;">'
                     '\u23f3 %s \u2014 retrying in %ds %s</div>'
                     % (_esc(self._retry_label), self._retry_left,
                        _esc(self._retry_info)))
        self._update_retry_status()
        self._retry_timer.start()

    def _tick_retry(self):
        self._retry_left -= 1
        if self._retry_left <= 0:
            self._retry_timer.stop()
            self._status_msg = "Working\u2026"
            return
        self._update_retry_status()

    def _update_retry_status(self):
        self._status_msg = "%s \u2014 retrying in %ds %s" % (
            self._retry_label, self._retry_left, self._retry_info)

    # -- settings --------------------------------------------------------

    def _toggle_settings(self):
        self._settings.setVisible(not self._settings.isVisible())

    def _current_provider(self) -> str:
        data = self._provider_combo.currentData()
        return data or _llm_config.DEFAULT_PROVIDER

    def _load_settings_fields(self):
        """Reflect the stored provider + its key/model into the fields."""
        provider = _llm_config.get_provider()
        # Select the combo without re-triggering a rebuild.
        self._provider_combo.blockSignals(True)
        idx = self._provider_combo.findData(provider)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)
        self._provider_combo.blockSignals(False)
        self._refresh_provider_fields(provider)

    def _apply_provider_visibility(self, provider: str):
        """Key/Test are API-only; Model shows for all; note for Claude CLI."""
        is_api = provider in _llm_config.API_PROVIDERS
        self._api_section.setVisible(is_api)
        self._cli_note.setVisible(not is_api)
        self._refresh_models_btn.setEnabled(True)
        self._refresh_models_btn.setToolTip(
            "Fetch the models available to this API key" if is_api else
            _REFRESH_TIPS.get(provider, "Refresh the model list"))

    def _load_effort(self, provider: str):
        # Repopulate per provider (Claude CLI exposes xhigh/max), then select.
        self._loading_settings = True
        try:
            self._effort_combo.clear()
            for lv in _llm_config.effort_levels(provider):
                self._effort_combo.addItem(
                    "Off" if lv == "off" else lv.capitalize(), lv)
            i = self._effort_combo.findData(_llm_config.get_effort(provider))
            if i >= 0:
                self._effort_combo.setCurrentIndex(i)
        finally:
            self._loading_settings = False

    def _on_effort_changed(self, *_):
        if self._loading_settings:
            return
        _llm_config.set_effort(self._current_provider(),
                               self._effort_combo.currentData())

    def _refresh_provider_fields(self, provider: str):
        self._apply_provider_visibility(provider)
        self._load_effort(provider)  # all providers
        self._load_model(provider)   # all providers (CLI uses --model too)
        if provider in _llm_config.API_PROVIDERS:
            self._load_key(provider)

    def _load_key(self, provider: str):
        try:
            from mpynode.ui import preferences

            key = preferences.get_pref("assistant_api_key_%s" % provider, "") or ""
        except Exception:
            key = ""
        self._key_edit.setText(key)
        if provider == "gemini":
            self._key_edit.setPlaceholderText("Gemini API key (or set GEMINI_API_KEY)")
        else:
            self._key_edit.setPlaceholderText(
                "Anthropic API key (or set ANTHROPIC_API_KEY)")

    def _load_model(self, provider: str):
        saved                  = _llm_config.get_model(provider)  # saved, or default ('' for CLI)
        is_claude_cli          = provider == "claude_cli"
        self._loading_settings = True
        try:
            self._set_model_editable(not is_claude_cli)
            self._model_edit.clear()
            cached = self._model_cache.get(provider)  # kept until Refresh
            if not cached:
                # CLI providers have no list endpoint, so restore the LAST
                # SUCCESSFUL live fetch from prefs. Empty on a machine that
                # never fetched; _maybe_autorefresh_models then tries a live
                # one. A typeable box takes an id meanwhile; the Claude CLI
                # box still has its default row.
                cached = _llm_config.cli_model_candidates(provider)
            self._model_edit.view().setMinimumWidth(0)
            if is_claude_cli:
                # Saved rows carry names, chips and greyed rows; a flat list
                # (an older MPyNode wrote only that) still renders.
                rows = self._cli_rows or _llm_config.get_cached_rows(provider)
                if rows or not cached:
                    self._populate_cli_rows(rows)
                else:
                    self._populate_cli_models(cached)
                self._select_cli_value(saved)
            else:
                if cached:
                    self._model_edit.addItems(cached)
                self._model_edit.setCurrentText(saved)
        finally:
            self._loading_settings = False
        line_edit = self._model_edit.lineEdit()  # None on the Claude CLI box
        if line_edit is not None:
            if provider in _llm_config.CLI_PROVIDERS:
                line_edit.setPlaceholderText(
                    "blank = the CLI's own default; or a full model id")
            else:
                line_edit.setPlaceholderText(
                    "model (default: %s)" % _llm_config.DEFAULT_MODELS.get(provider, ""))
        self._update_runs_line()

    def _set_model_editable(self, editable):
        """Typeable box, or (Claude CLI) a pure dropdown.

        setEditable creates a NEW line edit each time it turns typing on and
        destroys it when it turns typing off -- lineEdit() is None then -- so
        the line edit's signal is connected here, every time one is made.
        """
        combo = self._model_edit
        # Sized by its longest row, the dropdown would widen the whole panel:
        # its rows are names, some with an id or "what Claude Code runs" on.
        # It clips instead, and the list is widened on its own
        # (_fit_model_popup). A typeable box keeps Qt's defaults.
        combo.setSizeAdjustPolicy(
            QComboBox.AdjustToContentsOnFirstShow if editable
            else QComboBox.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(0 if editable else 20)
        if combo.isEditable() == bool(editable):
            return
        combo.setEditable(bool(editable))
        line_edit = combo.lineEdit()
        if line_edit is not None:
            # Typing is a choice too: it cancels the one-time alias pin.
            line_edit.textEdited.connect(self._on_model_picked)

    def _on_provider_changed(self, *_):
        provider = self._current_provider()
        _llm_config.set_provider(provider)
        self._refresh_provider_fields(provider)
        # Rebuild for the new backend and reset history -- the wire formats
        # are not interchangeable mid-conversation.
        self._build_client()
        self._client.reset()
        self._append_system(
            "Switched to %s." % _llm_config.PROVIDER_LABELS.get(provider, provider)
        )
        self._maybe_autorefresh_models(provider)

    def _save_key(self):
        _llm_config.set_api_key(self._current_provider(), self._key_edit.text())

    def _save_model(self):
        if self._loading_settings:
            return
        provider = self._current_provider()
        if provider == "claude_cli":
            # Its text is a label; the value is the row's data.
            value = self._cli_box_value()
            if value is not None:
                _llm_config.set_model(provider, value)
            return
        _llm_config.set_model(provider, self._model_edit.currentText())

    # -- connection test (cheap read-only describe-model) ---------------

    def _on_test(self):
        # Persist what's typed, then resolve the effective key/model (incl.
        # env-var fallback) on the GUI thread before the worker starts.
        self._save_key()
        self._save_model()
        provider = self._current_provider()
        key      = _llm_config.get_api_key(provider)
        model    = _llm_config.get_model(provider)
        if not key:
            self._append_error(
                "No API key for %s \u2014 enter one above (or set the env var)."
                % _llm_config.PROVIDER_LABELS.get(provider, provider)
            )
            return
        self._test_btn.setEnabled(False)
        self._status.setText("Testing connection\u2026")
        self._append_system("Testing %s / %s\u2026" % (provider, model))

        import threading

        def _work():
            try:
                if provider == "gemini":
                    from mpynode.ui.llm.gemini_client import describe_model
                elif provider == "openai":
                    from mpynode.ui.llm.openai_client import describe_model
                else:
                    from mpynode.ui.llm.anthropic_client import describe_model
                ok, msg = describe_model(key, model)
            except Exception as exc:
                ok, msg = False, "%s: %s" % (type(exc).__name__, exc)
            self._testFinished.emit(bool(ok), str(msg))

        threading.Thread(target=_work, daemon=True).start()

    def _on_test_finished(self, ok, msg):
        self._test_btn.setEnabled(True)
        self._status.setText("")
        if ok:
            self._append('<div style="color:#6a6;font-size:11px;margin-left:8px;">'
                         '\u2713 %s</div>' % _esc(msg))
        else:
            self._append_error(msg)

    # -- usage meter ----------------------------------------------------

    def _on_tokens_used(self, n):
        self._session_tokens += int(n or 0)

    def _update_usage(self):
        try:
            n = _llm_config.requests_in_last(60)
        except Exception:
            n = 0
        txt = "%d req/60s" % n
        if self._session_tokens:
            txt += " \u00b7 %s tok this session" % format(self._session_tokens, ",")
        self._usage_label.setText(txt)

    # -- model list (Refresh) -------------------------------------------

    def _list_source(self, provider):
        """Where to fetch a model list for a provider: (source_provider, key).

        Only for providers that have no local lister of their own -- a CLI that
        can answer for itself never reaches here (see _cli_model_fetcher). What
        is left is codex_cli, which borrows the OpenAI key, plus the API
        providers, which use their own key.
        """
        cli_src = {"claude_cli": "anthropic", "gemini_cli": "gemini",
                   "codex_cli": "openai"}.get(provider)
        if cli_src:
            return cli_src, _llm_config.get_api_key(cli_src)
        return provider, _llm_config.get_api_key(provider)

    def _cli_model_fetcher(self, provider):
        """The local, keyless model lister for a CLI provider -- or None.

        A CLI provider signs in with the machine's own login, so its list is
        asked of the CLI itself. Table-driven because the alternative (an `if
        provider == "claude_cli"`) silently sent every OTHER CLI down the
        API-key path, which demanded a Gemini key to list a CLI that never uses
        one.
        """
        name = _CLI_MODEL_FETCHERS.get(provider)
        return getattr(self, name) if name else None

    def _maybe_autorefresh_models(self, provider):
        """Auto-fetch the model list once per session (so the dropdown isn't a
        single item until Refresh). A self-listing CLI always refreshes (it asks
        the CLI, which needs no key); the others fetch live when a key is
        available, and with no key restore the last successful fetch from
        prefs."""
        if provider in self._model_cache:
            return
        _src, key = self._list_source(provider)
        if (self._cli_model_fetcher(provider) or key
                or _llm_config.cli_model_candidates(provider)):
            # At launch the saved Claude CLI rows only need re-linking unless
            # the CLI changed; the Refresh button always re-checks in full.
            self._cli_quick_fetch = True
            self._on_refresh_models()

    def _on_refresh_models(self):
        quick, self._cli_quick_fetch = self._cli_quick_fetch, False
        self._save_key()
        provider  = self._current_provider()
        cli_fetch = self._cli_model_fetcher(provider)
        if cli_fetch is not None:
            # A CLI provider authenticates through the machine's own login, so
            # the list is asked OF THE CLI and no key is involved. Checked
            # BEFORE the key branch so no key can ever gate it.
            if provider == "claude_cli":
                # Cleared HERE, on the GUI thread: a worker that dies before
                # writing it must read as a failed fetch, not the last one.
                self._cli_rows_fetched = None
                # A saved id the list does not show is checked too, so the
                # Runs line's "press ↻" is kept.
                typed = self._cli_box_value() or ""
                self._cli_typed_id = (
                    typed if _llm_config.is_explicit_cli_id(typed) else "")
                if quick:
                    cli_fetch = lambda: self._fetch_claude_cli_models(quick=True)
            self._start_model_fetch(provider, cli_fetch)
            return
        src, key = self._list_source(provider)
        if not key:
            # Fall back to the LAST SUCCESSFUL fetch, never a hardcoded roster
            # -- a baked-in list goes stale every time a family ships.
            cached = _llm_config.cli_model_candidates(provider)
            if cached:
                self._modelsFetched.emit(cached, provider)
                return
            if provider in _llm_config.CLI_PROVIDERS:
                self._append_error(
                    "To list %s model versions, set the %s API key under that "
                    "provider -- or just type a model id."
                    % (_llm_config.PROVIDER_LABELS.get(provider, provider),
                       _llm_config.PROVIDER_LABELS.get(src, src)))
            else:
                self._append_error("Set an API key first to fetch models.")
            return

        def _fetch_api_models():
            if src == "gemini":
                from mpynode.ui.llm.gemini_client import list_models
                return list_models(key)
            if src == "openai":
                from mpynode.ui.llm.openai_client import list_models
                return list_models(key)
            from mpynode.ui.llm.anthropic_client import list_models
            return list_models(key)

        self._start_model_fetch(provider, _fetch_api_models)

    def _fetch_claude_cli_models(self, quick=False):
        """Pickable ids from the local `claude` binary (no API key). Worker side.

        Full versioned ids are discovered + validated, so a specific older
        version can be picked, and the aliases are resolved into chips. With
        ``quick`` and saved rows still good for this CLI version (see
        config.rows_need_full_check), only the local facts are re-linked (~4 s)
        instead of re-validating every id with the login (25-40 s).

        An Anthropic key is NOT needed; if one happens to be set its ids ride
        along as extra CANDIDATES, still validated against this CLI (the HTTP
        list names models the CLI rejects).
        """
        from mpynode.ui.llm import claude_cli_client as cli

        payload = None
        saved   = _llm_config.get_cached_rows("claude_cli") if quick else {}
        if saved and _llm_config.rows_need_full_check(saved, cli.cli_version()):
            # After a CLI update, say: the model the saved rows name may no
            # longer be what Claude Code runs (_on_cli_recheck).
            self._cliRecheck.emit()
        elif saved:
            payload = cli.relink_saved_rows(saved)
        if payload is None:
            extra = list(self._api_model_candidates())
            if self._cli_typed_id:
                extra.append(self._cli_typed_id)
            payload            = cli.list_model_rows(extra_candidates=extra)
            payload["fetched"] = time.time()
        # Read back on the main thread in _on_models_fetched, which derives
        # everything else from it -- a failed check must not touch what is on
        # screen. Written BEFORE the queued signal; the queue is the barrier.
        self._cli_rows_fetched = payload
        return [r["id"] for r in payload.get("rows") or [] if r.get("status") == "valid"]

    def _fetch_gemini_cli_models(self):
        """Model ids from the local `gemini` binary (no API key). Worker side.

        The Gemini CLI has no list command, so its own model table is read out
        of the installed bundle -- local, keyless, and free of an API round
        trip. See gemini_cli_client.list_models.
        """
        from mpynode.ui.llm.gemini_cli_client import list_models

        return list_models()

    def _populate_cli_models(self, models):
        """Fill the combo from a FLAT id list -- what an older MPyNode saved, or
        a fallback. Rendered through the same rows as a fresh fetch, NEWEST
        FIRST per family, with whatever display names are known.

        A name that is not an explicit id (a floating alias from the old
        fallback) is shown greyed, never pickable: ``get_model`` would drop it,
        so offering it would show a model the box never sends.
        """
        from mpynode.ui.llm import claude_cli_client as cli

        displays = getattr(self, "_cli_model_displays", None) or {}
        rows     = []
        for m in cli.order_display(models):
            if _llm_config.is_explicit_cli_id(m):
                rows.append({"id": m, "label": displays.get(m) or m,
                             "family": cli.family_of(m), "aliases": [],
                             "status": "valid", "note": "", "min_version": ""})
            else:
                rows.append({"id": "", "label": m, "family": "", "aliases": [],
                             "status": "alias", "note": "alias · not sent",
                             "min_version": ""})
        self._populate_cli_rows(cli.link_rows(rows, current=self._cli_current_model))

    def _populate_cli_rows(self, payload):
        """Fill the combo from a ``claude_cli_client.build_rows`` payload.

        Order: the default row, then one block per family under a header,
        greyed "needs update" rows first. The default row names the model
        Claude Code runs and saves "", so nothing is sent and it keeps
        following that default; every other enabled row pins its id, and the
        ``also_valid`` ids get rows too. Item text is the label the closed box
        shows -- plus the id where an earlier row has the same label -- and the
        value, name, chips and notes ride in data roles (_ROW_VALUE, and
        _ModelRowDelegate's). The name is also the tooltip.
        """
        from mpynode.ui.llm import claude_cli_client as cli

        payload = dict(payload or {})
        rows    = payload.get("rows") or []
        current = payload.get("current") or ""
        self._cli_rows           = payload
        self._cli_current_model  = current
        self._cli_model_displays = dict(payload.get("also_valid") or {})
        self._cli_model_displays.update(
            {r["id"]: r["label"] for r in rows if r.get("id")})
        self._add_model_row(
            "", "default", self._follow_row_text(current),
            right   = "follows Claude Code's default",
            tooltip = "Sends no model id, so this runs whatever Claude Code runs "
                    "by default -- and follows that default when it moves.")
        family = None
        seen   = set()
        for r in _rows_with_also_valid(rows, payload.get("also_valid"), cli.family_of):
            if r.get("family") != family:
                family = r.get("family")
                if family:
                    self._add_model_row("", "header", family.capitalize())
            if r.get("status") == "valid":
                label = r.get("label") or r["id"]
                # Two ids can share a name ("Sonnet 5" and its [1m] twin): the
                # closed box names the id too, so it never hides which is pinned.
                text = label if label not in seen else "%s · %s" % (label, r["id"])
                seen.add(label)
                self._add_model_row(r["id"], "model", label,
                                    r.get("aliases") or (), r["id"],
                                    r.get("label"), text=text)
            else:
                self._add_model_row("", "greyed", r.get("label") or r.get("id", ""),
                                    right=r.get("note", ""), tooltip=r.get("note"))
        if payload.get("fallback"):
            # Nothing validated: say where each alias points today, greyed.
            labels = payload.get("alias_labels") or {}
            for alias, label in labels.items():
                self._add_model_row("", "greyed", "%s → %s" % (alias, label),
                                    right="alias · not sent")
        self._fit_model_popup()

    def _follow_row_text(self, current):
        """The default row's label: the model Claude Code runs, once known."""
        if self._cli_checking:
            return "Checking what Claude Code runs…"  # the saved name may be stale
        if current and not self._cli_current_stale:
            return "%s — what Claude Code runs" % current
        if "claude_cli" not in self._model_cache:
            return "Checking what Claude Code runs…"  # no check has finished yet
        return "Claude Code's default"

    def _relabel_follow_row(self):
        """Re-name the default row in place -- for a check that started, or
        ended without replacing the rows on screen.

        Guarded like every rewrite of the box: renaming the current row emits
        currentTextChanged, which must not save "" over a saved legacy alias
        still waiting for its one-time pin.
        """
        combo = self._model_edit
        if combo.count() and combo.itemData(0, _ROW_KIND) == "default":
            text = self._follow_row_text(
                (self._cli_rows or {}).get("current") or "")
            self._loading_settings = True
            try:
                combo.setItemText(0, text)
                combo.setItemData(0, text, _ROW_LABEL)
            finally:
                self._loading_settings = False
        self._update_runs_line()

    def _on_cli_recheck(self):
        """A full check started over saved rows it may overturn -- after a
        Claude Code update, say -- so the model they name is no longer known
        to be what Claude Code runs: the top row reads "Checking what Claude
        Code runs…" until that check lands (_apply_cli_rows_fetch)."""
        self._cli_checking      = True
        self._cli_current_stale = True
        self._relabel_follow_row()

    def _add_model_row(self, value, kind, label, chips=(), right="", tooltip=None,
                       text=None, at=None):
        """One Claude CLI row. ``value`` is what picking it saves -- "" on the
        default row -- and only the default and model rows carry one. ``text``
        is what the closed box shows (``label`` when omitted; blank on a row
        that cannot be picked). ``at`` inserts instead of appending."""
        combo = self._model_edit
        pick  = kind in _PICKABLE_KINDS
        i     = combo.count() if at is None else at
        combo.insertItem(i, (label if text is None else text) if pick else "")
        if pick:
            combo.setItemData(i, value or "", _ROW_VALUE)
        combo.setItemData(i, kind,            _ROW_KIND)
        combo.setItemData(i, label,           _ROW_LABEL)
        combo.setItemData(i, " ".join(chips), _ROW_CHIPS)
        combo.setItemData(i, right,           _ROW_RIGHT)
        if tooltip:
            combo.setItemData(i, tooltip, Qt.ToolTipRole)
        if not pick:
            try:
                item = combo.model().item(i)
                item.setEnabled(False)
                item.setSelectable(False)
            except Exception:
                pass

    def _cli_row_index(self, value):
        """The Claude CLI row that saves ``value``, or -1."""
        combo = self._model_edit
        for i in range(combo.count()):
            if (combo.itemData(i, _ROW_KIND) in _PICKABLE_KINDS
                    and (combo.itemData(i, _ROW_VALUE) or "") == value):
                return i
        return -1

    def _cli_box_value(self):
        """What the Claude CLI box's current row saves: "" (follow Claude
        Code's default) or an id -- None when no pickable row is current."""
        combo = self._model_edit
        i     = combo.currentIndex()
        if i < 0 or combo.itemData(i, _ROW_KIND) not in _PICKABLE_KINDS:
            return None
        return combo.itemData(i, _ROW_VALUE) or ""

    def _select_cli_value(self, value):
        """Show the Claude CLI row that saves ``value``.

        Anything ``get_model`` would not send (blank, a legacy alias) is the
        default row: that is what runs. A saved id no row holds -- refused
        since, or never checked -- gets a row under its family, so the closed
        box never shows a model other than the one sent; the line under the box
        says why it is not listed.
        """
        from mpynode.ui.llm import claude_cli_client as cli

        value = value if _llm_config.is_explicit_cli_id(value) else ""
        i     = self._cli_row_index(value)
        if i < 0:
            family = cli.family_of(value)
            head   = family.capitalize()
            combo  = self._model_edit
            starts = [j for j in range(combo.count())
                      if combo.itemData(j, _ROW_KIND) == "header"
                      and combo.itemData(j, _ROW_LABEL) == head]
            if starts:
                i = starts[0] + 1
                while (i < combo.count()
                       and combo.itemData(i, _ROW_KIND) != "header"):
                    i += 1
            else:
                if head:
                    self._add_model_row("", "header", head)
                i = combo.count()
            label = self._cli_model_displays.get(value) or value
            self._add_model_row(value, "model", label, right=value,
                                tooltip="Saved, but not in this list", at=i)
        self._model_edit.setCurrentIndex(i)

    def _model_box_busy(self):
        """True while the user is choosing: typing in a typeable box, or the
        list is open. lineEdit() is None on the Claude CLI's pure dropdown."""
        line_edit = self._model_edit.lineEdit()
        if line_edit is not None and line_edit.hasFocus():
            return True
        try:
            return bool(self._model_edit.view().isVisible())
        except Exception:
            return False

    def _fit_model_popup(self):
        """Widen the popup to the widest row: the panel is narrow, and a row
        carries a name, chips AND an id."""
        view = self._model_edit.view()
        try:
            opt      = QStyleOptionViewItem()
            opt.font = view.font()
            model    = self._model_edit.model()
            width = max((self._model_row_delegate.sizeHint(
                opt, model.index(i, 0)).width() for i in range(model.rowCount())),
                default=0)
            view.setMinimumWidth(min(width + 24, 720))
        except Exception:
            pass

    def _on_model_picked(self, *_):
        """The user chose: picked a row, or typed. That cancels the one-time
        alias pin (see _pin_saved_alias), and the choice is saved even when the
        row did not change -- while a legacy alias is saved the Claude CLI box
        already shows the default row, so picking it fires no change signal."""
        if self._loading_settings:
            return
        self._model_at_launch = ""
        self._save_model()

    def _update_runs_line(self, *_):
        """The line under the Claude CLI box: what it will run, and anything
        the installed CLI is too old for."""
        if self._current_provider() != "claude_cli":
            self._runs_label.setVisible(False)
            return
        p    = self._cli_rows or {}
        rows = p.get("rows") or []
        ver  = p.get("cli_version") or ""
        cur  = "" if self._cli_current_stale else (p.get("current") or "")
        by_id = {mid: {"label": lab, "status": "valid"}
                 for mid, lab in (p.get("also_valid") or {}).items()}
        by_id.update({r["id"]: r for r in rows if r.get("id")})
        # "" (the default row) or an id: _select_cli_value never shows an alias.
        text = self._cli_box_value() or ""
        tail = (" · Claude Code %s" % ver) if ver else ""
        row  = by_id.get(text)
        if not text and self._cli_checking:
            line = "Runs: Claude Code's default · checking which model that is"
        elif not text:
            line = ("Runs: %s · follows Claude Code's default%s" % (cur, tail) if cur
                    else "Runs: Claude Code's default, whichever model that is%s" % tail)
        elif row is not None and row.get("status") == "valid":
            line = ("Runs: %s · pinned, won't change on its own%s"
                    % (row.get("label") or text, tail))
        elif row is not None:
            line = "Runs: nothing — %s %s" % (text, row.get("note") or "")
        elif text in (p.get("refused") or {}):
            line = ("Runs: nothing — Claude Code%s does not take %s (%s)"
                    % ((" " + ver) if ver else "", text, p["refused"][text]))
        else:
            line = "Runs: %s · not checked yet — press ↻" % text
        html = _esc(line)
        for r in rows:
            if r.get("status") not in ("hint", "too_old") or not r.get("min_version"):
                continue
            html += ('<br><span style="color:#dca54c;">⚠ %s needs Claude Code '
                     '%s+%s — run <code>claude update</code>, then ↻</span>'
                     % (_esc(r.get("label") or r.get("id")), _esc(r["min_version"]),
                        (" (installed %s)" % _esc(ver)) if ver else ""))
        if p.get("fallback") and p.get("error"):
            html += ('<br><span style="color:#e77;">Could not check model ids: %s'
                     '</span>' % _esc(p["error"]))
        self._runs_label.setText(html)
        self._runs_label.setVisible(True)

    def _api_model_candidates(self):
        """Anthropic ids to offer the validator as extra guesses ([] with no key)."""
        try:
            key = _llm_config.get_api_key("anthropic")
            if not key:
                return []
            from mpynode.ui.llm.anthropic_client import list_models as _api_list

            return _api_list(key)
        except Exception:
            return []

    def _start_model_fetch(self, provider, fetch_fn):
        """Run ``fetch_fn`` off the UI thread and emit its list. Shared by the
        API-key providers and the Claude CLI so both get the same button/status
        handling."""
        self._refresh_models_btn.setEnabled(False)
        self._status.setText("Fetching models\u2026")

        import threading

        def _work():
            try:
                models = fetch_fn()
            except Exception:
                models = []
            self._modelsFetched.emit(list(models or []), provider)

        threading.Thread(target=_work, daemon=True).start()

    def _on_models_fetched(self, models, provider):
        self._refresh_models_btn.setEnabled(True)
        self._status.setText("")
        if provider != self._current_provider():
            return  # user switched provider while fetching
        if provider == "claude_cli":
            payload = self._cli_rows_fetched
            if not isinstance(payload, dict):
                from mpynode.ui.llm.claude_cli_client import build_rows

                payload = build_rows({}, error="the model check stopped early")
            self._apply_cli_rows_fetch(payload)
            return
        if not models:
            if self._cli_model_fetcher(provider) is not None:
                binary = {"claude_cli": "claude", "gemini_cli": "gemini"}.get(
                    provider, provider)
                self._append_error(
                    "Could not read the model list from the %s CLI. Check that "
                    "`%s` runs in a terminal -- or just type a model id."
                    % (binary, binary))
            else:
                self._append_error("No models returned (check the API key).")
            return
        self._model_cache[provider] = list(models)  # keep until next refresh
        # Persist so the next launch still lists real, live-fetched ids, even
        # with no key or offline.
        _llm_config.set_cached_models(provider, models)
        current                = self._model_edit.currentText()
        self._loading_settings = True
        try:
            self._model_edit.clear()
            if provider == "claude_cli":
                self._populate_cli_models(models)
            else:
                self._model_edit.addItems(models)
            # Blank for CLI providers means the CLI's own default, so the box
            # never shows a version the tool won't actually run.
            self._model_edit.setCurrentText(
                _llm_config.model_selection_after_fetch(provider, current, models))
        finally:
            self._loading_settings = False
        self._append('<div style="color:#6a6;font-size:11px;margin-left:8px;">'
                     '\u2713 %d models available</div>' % len(models))

    def _apply_cli_rows_fetch(self, payload):
        """GUI-thread side of a Claude CLI fetch (``_fetch_claude_cli_models``).

        A fetch where nothing validated -- logged out, offline, a CLI this
        cannot read -- never replaces a good saved list, and neither does one
        that did not finish (``partial``): that list is kept and the reason
        reported. Otherwise the rows are shown and saved (with the flat id list
        an older MPyNode reads), and a saved alias is pinned once.
        """
        provider = "claude_cli"
        saved    = _llm_config.get_cached_rows(provider)
        ids      = [r["id"] for r in payload.get("rows") or [] if r.get("status") == "valid"]
        fallback = bool(payload.get("fallback"))
        keep = (saved and not saved.get("fallback")
                    and (fallback or not saved.get("partial")))
        self._model_cache[provider] = ids    # once per session, success or not
        self._cli_checking          = False  # the check is over, known or not
        if (fallback or payload.get("partial")) and keep:
            reason = payload.get("error") or "the check did not finish"
            self._append_error(
                "Could not re-check the Claude CLI models (%s). Keeping the "
                "list checked %s with Claude Code %s."
                % (reason, _fmt_day(saved.get("fetched")),
                   saved.get("cli_version") or "?"))
            self._relabel_follow_row()  # the check is over, known or not
            return
        if fallback:
            reason = payload.get("error") or "no model id validated"
            self._append_error(
                "Could not check the claude CLI's model ids (%s). Check that "
                "`claude` runs in a terminal, then press ↻." % reason)
        else:
            _llm_config.set_cached_rows(provider, payload)
            _llm_config.set_cached_models(provider, ids)
            self._cli_current_stale = False  # this check named the current model
        # The box holds no unsaved text (it takes no typing), so what is saved
        # is what it shows.
        current                = _llm_config.get_model(provider)
        self._loading_settings = True
        try:
            self._model_edit.clear()
            self._populate_cli_rows(payload)
            self._select_cli_value(
                _llm_config.model_selection_after_fetch(provider, current, ids))
        finally:
            self._loading_settings = False
        self._update_runs_line()
        if payload.get("fallback"):
            return
        self._pin_saved_alias(payload)
        needs = sum(1 for r in payload.get("rows") or []
                    if r.get("status") in ("hint", "too_old"))
        parts = ["\u2713 %d models" % len(ids)]
        if payload.get("cli_version"):
            parts.append("Claude Code %s" % payload["cli_version"])
        if payload.get("current"):
            parts.append("default %s" % payload["current"])
        if needs:
            parts.append("%d need%s a Claude Code update" % (needs, "" if needs > 1 else "s"))
        if payload.get("fetched"):
            parts.append("checked %s" % _fmt_day(payload["fetched"]))
        if payload.get("partial"):
            parts.append("check incomplete, re-checked next launch")
        self._append('<div style="color:#6a6;font-size:11px;margin-left:8px;">'
                     '%s</div>' % _esc(" \u00b7 ".join(parts)))

    def _pin_saved_alias(self, payload):
        """Pin a saved alias to the id it names today (see
        config.migrate_saved_alias), and say so once.

        Only the value saved when the panel opened is a candidate -- never a
        choice made since, never while the list is open -- and only once this
        fetch resolved the aliases, so a slow lookup cannot clear a real one.
        """
        launch = self._model_at_launch
        labels = payload.get("alias_labels") or {}
        if (not launch or not labels
                or _llm_config.saved_model("claude_cli") != launch
                or self._model_box_busy()):
            return
        # Not resolved THIS time -- the check did not finish, or this alias did
        # not answer -- so the next fetch decides rather than clearing it.
        if launch != "default" and launch not in (payload.get("alias_map") or {}):
            if payload.get("partial") or (
                    launch in (payload.get("aliases") or ()) and launch not in labels):
                return
        res                   = _llm_config.migrate_saved_alias("claude_cli", payload.get("alias_map"))
        self._model_at_launch = ""
        if not res:
            return
        old, new = res
        cur                    = payload.get("current") or "Claude Code's default"
        self._loading_settings = True
        try:
            self._select_cli_value(new)
        finally:
            self._loading_settings = False
        self._update_runs_line()
        if old == "default":
            self._append_system(
                "Saved model “default” is now the top row, which "
                "follows Claude Code's default (%s)." % cur)
            return
        if not new and old in labels:
            self._append_system(
                "Saved model \u201c%s\u201d names no single model (%s), so it "
                "was never sent and every turn ran %s. Cleared."
                % (old, labels[old], cur))
            return
        if not new:
            self._append_system(
                "Saved model \u201c%s\u201d is not a model id, so it was never "
                "sent and every turn ran %s. Cleared." % (old, cur))
            return
        same = new == payload.get("default_id")
        self._append_system(
            "Saved model \u201c%s\u201d was never sent (an alias is not a pinned "
            "id), so every turn ran %s. It is now pinned to %s (%s)%s." % (
                old, cur, new, self._cli_model_displays.get(new, new),
                " \u2014 the same model, and it won't change on its own"
                if same else ""))
