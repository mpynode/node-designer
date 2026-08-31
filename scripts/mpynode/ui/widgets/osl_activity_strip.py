"""NDOslActivityStrip -- a compact activity indicator for the OSL tab's
"Translate Compute → OSL" AI fallback.

Shows an animated braille spinner + a live MM:SS elapsed timer + a curated stage
headline while the (worker-thread) AI translation runs, a Stop button to cancel
it, a collapsible log of the raw streamed chain-of-thought / tool lines, and a
PERSISTENT inline error state on failure (there is no modal). Purely visual: it
knows nothing about the LLM -- the host drives it from NDOslEditor's
convertBusyChanged / convertProgress / convertSucceeded / convertFailed /
convertCancelled signals, and its Stop button emits ``stopRequested``.

The spinner is the same pure-text idiom used by the AI assistant panel and the
compile dialog (a QTimer cycling braille frames into a QLabel); factored here so
it isn't pasted a fourth time.
"""

from __future__ import annotations

import time

from mpynode.ui.qt_wrapper import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)

# Braille spinner; matches assistant_panel / compile_dialog.
_SPIN_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPIN_INTERVAL_MS = 110

_LOG_COLLAPSED = "Log ▸"
_LOG_EXPANDED = "Log ▾"


def _fmt(seconds: float) -> str:
    s = int(seconds)
    return "%d:%02d" % (s // 60, s % 60)


class NDOslActivityStrip(QWidget):
    """Spinner + timer + live feed + Stop + collapsible log + inline error."""

    stopRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._spin_i = 0
        self._t0 = 0.0
        self._stage = ""

        self._timer = QTimer(self)
        self._timer.setInterval(_SPIN_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self._status = QLabel("", self)
        self._log_toggle = QPushButton(_LOG_COLLAPSED, self)
        self._log_toggle.setCheckable(True)
        self._log_toggle.setFlat(True)
        self._log_toggle.toggled.connect(self._on_log_toggled)
        self._stop_btn = QPushButton("Stop", self)
        self._stop_btn.clicked.connect(self.request_stop)
        row.addWidget(self._status, 1)
        row.addWidget(self._log_toggle, 0)
        row.addWidget(self._stop_btn, 0)

        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)  # bound memory on a chatty stream
        try:
            self._log.setLineWrapMode(QPlainTextEdit.NoWrap)
        except Exception:
            pass

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        outer.addLayout(row)
        outer.addWidget(self._log)

        self.reset()

    # ------------------------------------------------------------------
    # Public API (driven by the host from NDOslEditor's signals)
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Idle state: no spinner, no error, log collapsed, whole strip hidden."""
        self._running = False
        self._timer.stop()
        self._t0 = 0.0  # so a finish with no preceding start() reports 0:00
        self._stage = ""
        self._status.setText("")
        self._set_error_style(False)
        self._log.clear()
        self._log_toggle.setChecked(False)
        self._log.setVisible(False)
        self._stop_btn.setVisible(False)
        self._stop_btn.setText("Stop")  # clear any leftover "Stopping…"
        self._stop_btn.setEnabled(True)
        self._log_toggle.setVisible(False)
        self.setVisible(False)

    def start(self, stage: str = "Translating with AI…") -> None:
        """Begin: show the strip, start the spinner + elapsed timer, reveal Stop."""
        self._running = True
        self._spin_i = 0
        self._t0 = time.monotonic()
        self._stage = stage
        self._set_error_style(False)
        self._log.clear()
        self._stop_btn.setVisible(True)
        self._stop_btn.setEnabled(True)
        self._stop_btn.setText("Stop")  # a prior run may have left "Stopping…"
        self._log_toggle.setVisible(True)
        self.setVisible(True)
        self._render()
        self._timer.start()

    def set_stage(self, stage: str) -> None:
        """Update the curated headline (e.g. 'Validating OSL compile…')."""
        self._stage = stage or self._stage
        if self._running:
            self._render()

    def add_log_line(self, line: str) -> None:
        """Append one raw streamed line to the (collapsible) log."""
        self._log.appendPlainText(str(line))

    def finish_ok(self) -> None:
        self._finish("✓ OSL generated in %s" % self._elapsed(), error=False)

    def finish_cancelled(self) -> None:
        self._finish("Cancelled after %s" % self._elapsed(), error=False)

    def finish_error(self, message: str) -> None:
        first = (str(message) or "translation failed").splitlines()[0]
        self._finish("✕ Failed after %s: %s" % (self._elapsed(), first),
                     error=True)
        # Surface the streamed detail on failure, but ONLY when there IS
        # detail: a synchronous failure (e.g. no AI provider) arrives with no
        # preceding start(), so the toggle is hidden and the log empty, and
        # force-expanding would reveal an empty, uncollapsible panel. The
        # toggle is revealed too, so the log can be collapsed again.
        if self.log_text().strip():
            self._log_toggle.setVisible(True)
            self._log_toggle.setChecked(True)

    def request_stop(self) -> None:
        """Emit stopRequested (also the Stop button's slot). Disables the button
        so a second press can't double-fire while the cancel unwinds."""
        self._stop_btn.setEnabled(False)
        self._stop_btn.setText("Stopping…")
        self.stopRequested.emit()

    # Read-accessors, for tests + inspectors.
    def status_text(self) -> str:
        return self._status.text()

    def log_text(self) -> str:
        return self._log.toPlainText()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _finish(self, message: str, error: bool) -> None:
        self._running = False
        self._timer.stop()
        self._stop_btn.setVisible(False)
        self._set_error_style(error)
        self._status.setText(message)
        self.setVisible(True)

    def _tick(self) -> None:
        self._spin_i = (self._spin_i + 1) % len(_SPIN_FRAMES)
        self._render()

    def _render(self) -> None:
        frame = _SPIN_FRAMES[self._spin_i % len(_SPIN_FRAMES)]
        self._status.setText("%s %s   %s"
                             % (frame, self._stage or "Working…", self._elapsed()))

    def _elapsed(self) -> str:
        return _fmt(time.monotonic() - self._t0) if self._t0 else "0:00"

    def _set_error_style(self, on: bool) -> None:
        # Muted red for the persistent failure state.
        self._status.setStyleSheet("color: #d05a5a;" if on else "")

    def _on_log_toggled(self, checked: bool) -> None:
        self._log_toggle.setText(_LOG_EXPANDED if checked else _LOG_COLLAPSED)
        self._log.setVisible(checked)
