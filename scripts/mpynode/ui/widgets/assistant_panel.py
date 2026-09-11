"""NDAssistantPanel -- the embedded LLM chat panel (Shape A).

Docked to the right edge of the Node Designer (Cursor-style). Hosts a chat
transcript + input box and drives the selected assistant client (Anthropic or
Gemini, chosen in settings via ``llm.make_client``), whose tool calls
build/edit the working node live (inside undo). The working node is captured
from the host's active tab on the GUI thread at send time (the client's
worker thread must never touch Maya/Qt directly).
"""

from __future__ import annotations

import time

from mpynode.ui.qt_wrapper import (
    QColor,
    QComboBox,
    QFont,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
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
        self._turn_start         = None   # monotonic time the current turn began
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
        self._model_edit = QComboBox(self._settings)
        self._model_edit.setEditable(True)  # type-in always allowed
        self._model_edit.currentTextChanged.connect(self._save_model)
        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.addWidget(self._model_edit, 1)
        self._refresh_models_btn = QPushButton("\u21bb", self._settings)
        self._refresh_models_btn.setFixedWidth(28)
        self._refresh_models_btn.clicked.connect(self._on_refresh_models)
        model_row.addWidget(self._refresh_models_btn)
        slay.addLayout(model_row)

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
                '\u23f1 done in %s</div>' % _fmt_duration(elapsed))
        self._set_idle_status()

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
            "Fetch CLI model versions via your Anthropic API key (set it under "
            "the 'Claude (Anthropic API)' provider); or just type opus/sonnet")

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
        self._loading_settings = True
        try:
            self._model_edit.clear()
            cached = self._model_cache.get(provider)  # kept until Refresh
            if not cached:
                # CLI providers have no list endpoint, so restore the LAST
                # SUCCESSFUL live fetch from prefs. Empty on a machine that
                # never fetched; _maybe_autorefresh_models then tries a live
                # one, and the combo stays editable either way.
                cached = _llm_config.cli_model_candidates(provider)
            if cached:
                if provider == "claude_cli":
                    self._populate_cli_models(cached)
                else:
                    self._model_edit.addItems(cached)
            self._model_edit.setCurrentText(saved)
        finally:
            self._loading_settings = False
        try:
            if provider == "claude_cli":
                self._model_edit.lineEdit().setPlaceholderText(
                    "blank = claude's default; or a full model id")
            else:
                self._model_edit.lineEdit().setPlaceholderText(
                    "model (default: %s)" % _llm_config.DEFAULT_MODELS.get(provider, ""))
        except Exception:
            pass

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
        _llm_config.set_model(self._current_provider(), self._model_edit.currentText())

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

        Claude CLI has no list API of its own, but it runs Anthropic models --
        so we reuse the Anthropic key/list to surface versioned ids for it.
        """
        cli_src = {"claude_cli": "anthropic", "gemini_cli": "gemini",
                   "codex_cli": "openai"}.get(provider)
        if cli_src:
            return cli_src, _llm_config.get_api_key(cli_src)
        return provider, _llm_config.get_api_key(provider)

    def _maybe_autorefresh_models(self, provider):
        """Auto-fetch the model list once per session (so the dropdown isn't a
        single item until Refresh). Claude CLI always refreshes (it asks the CLI,
        which needs no key); the others fetch live when a key is available, and
        with no key restore the last successful fetch from prefs."""
        if provider in self._model_cache:
            return
        _src, key = self._list_source(provider)
        if (provider == "claude_cli" or key
                or _llm_config.cli_model_candidates(provider)):
            self._on_refresh_models()

    def _on_refresh_models(self):
        self._save_key()
        provider = self._current_provider()
        if provider == "claude_cli":
            # A CLI provider authenticates through the machine's own `claude`
            # login, so the list is asked OF THE CLI and no key is involved.
            # Checked BEFORE the key branch so no key can ever gate it.
            self._start_model_fetch(provider, self._fetch_claude_cli_models)
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

    def _fetch_claude_cli_models(self):
        """Model names from the local `claude` binary (no API key). Worker side.

        Full versioned ids are discovered + validated as well as the aliases, so
        a specific older version can be picked. An Anthropic key is NOT needed;
        if one happens to be set its ids ride along as extra CANDIDATES, still
        validated against this CLI (the HTTP list names models the CLI rejects).
        """
        from mpynode.ui.llm.claude_cli_client import list_models

        models, current, displays = list_models(
            extra_candidates=self._api_model_candidates())
        # Read back on the main thread in _on_models_fetched. Written BEFORE
        # the queued signal; the queue crossing is the barrier.
        self._cli_current_model  = current
        self._cli_model_displays = displays or {}
        return models

    def _populate_cli_models(self, models):
        """Fill the combo with the CLI list -- every entry an explicit versioned
        id, NEWEST FIRST per family. Display names ride along as tooltips
        because two ids can resolve to the same one (claude-opus-4 /
        claude-opus-4-20250514 are both "Opus 4").

        Order is re-derived here rather than trusted from the caller, so a list
        restored from the prefs cache renders exactly like a fresh fetch.
        """
        from mpynode.ui.llm.claude_cli_client import order_display

        displays = getattr(self, "_cli_model_displays", None) or {}
        for m in order_display(models):
            self._model_edit.addItem(m)
            label = displays.get(m)
            if label:
                try:
                    self._model_edit.setItemData(
                        self._model_edit.count() - 1, label, Qt.ToolTipRole)
                except Exception:
                    pass

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
        if not models:
            if provider == "claude_cli":
                self._append_error(
                    "Could not read the model list from the claude CLI. Check "
                    "that `claude` runs in a terminal -- or just type a model id.")
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
        # Naming what a blank box resolves to is the only way the user can
        # tell what it will actually run.
        suffix = ""
        if provider == "claude_cli" and getattr(self, "_cli_current_model", ""):
            suffix = " (current: %s)" % self._cli_current_model
        self._append('<div style="color:#6a6;font-size:11px;margin-left:8px;">'
                     '\u2713 %d models available%s</div>' % (len(models), suffix))
