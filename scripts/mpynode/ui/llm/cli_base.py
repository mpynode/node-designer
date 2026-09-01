"""Shared scaffolding for CLI-backed providers (Gemini CLI, Codex CLI).

A CLI provider drives a local agent binary (`gemini`, `codex`, ...) that CANNOT
call back into the live Maya session. Instead of a tool bridge, we inject the
active node + the node cheat-sheet into the prompt (``llm.payload.build_prompt``),
let the agent reply with ONE JSON node payload, and apply it through the tested
``define_node`` spine on Maya's main thread (``llm.payload.finalize_turn``).

This base handles the common machinery -- composing the payload prompt, spawning
the subprocess, streaming its output, accumulating the reply, applying the
payload at end of turn, cancel, and the Qt signal surface. Subclasses supply the
CLI-specific bits:

  * ``_bin()``                       -- binary name (with env override)
  * ``_build_cmd(prompt, images)``   -- the argv
  * ``_stdin_payload(prompt, images)`` -- str to write to stdin, or None
  * ``_handle_event(line)``          -- map one stdout line -> signals
  * ``_cleanup()``                   -- optional post-run cleanup (temp files)

(The Claude CLI client predates this and stays standalone.)
"""

from __future__ import annotations

import os
import subprocess
import threading

from mpynode.ui.qt_wrapper import QObject, Signal
from mpynode.native.toolchain import toolchain


# Set MPYNODE_CLI_DEBUG=1 to echo every raw CLI output line into the chat, so
# the exact JSON event schema (and any errors) can be inspected/pasted.
def _debug():
    return bool(os.environ.get("MPYNODE_CLI_DEBUG"))


class BaseCliClient(QObject):
    assistantText = Signal(str)
    toolStarted = Signal(str)
    toolFinished = Signal(str)
    turnFinished = Signal()
    notice = Signal(str)
    thinking = Signal(str)
    retryScheduled = Signal(int, int, int, int, str)  # interface compat (unused)
    tokensUsed = Signal(int)
    errorOccurred = Signal(str)
    busyChanged = Signal(bool)

    PROVIDER = "cli"
    LABEL = "CLI"

    def __init__(self, ctx_provider=None, parent=None):
        super().__init__(parent)
        self._ctx_provider = ctx_provider
        self._busy = False
        self._cancel = threading.Event()
        self._proc = None
        self._emitted_text = False
        self._answer_text = ""   # accumulated reply -> payload extraction
        self._ctx = None         # ToolContext captured per turn (GUI thread)
        self._node_name = None   # active node captured per turn (GUI thread)

    # -- public interface ------------------------------------------------

    def reset(self):
        pass  # CLI keeps its own session; nothing to clear here

    def is_busy(self):
        return self._busy

    def cancel(self):
        if not self._busy:
            return
        self._cancel.set()
        p = self._proc
        if p is not None:
            try:
                p.terminate()
            except Exception:
                pass
        self.notice.emit("Stopping…")

    def _emit_answer(self, text):
        """Emit assistant text to the panel AND accumulate it for end-of-turn
        payload extraction."""
        if not text:
            return
        self._answer_text += text
        self.assistantText.emit(text)
        self._emitted_text = True

    def send(self, user_text, images=None):
        if self._busy:
            self.errorOccurred.emit("AI Assistant is still working on the previous request.")
            return
        binexe = self._bin()
        if toolchain.find_executable(binexe) is None:
            self.errorOccurred.emit(
                "`%s` CLI not found on PATH. Install it or set its *_BIN env var."
                % binexe)
            return
        # Capture the active node + a ToolContext on the GUI thread (Maya-safe),
        # then compose the full payload-mode prompt (serializes the active node).
        self._ctx = self._ctx_provider() if callable(self._ctx_provider) else None
        self._node_name = getattr(self._ctx, "working_node", None)
        try:
            from mpynode.ui.llm import payload as _payload

            prompt = _payload.build_prompt(user_text, self._node_name)
        except Exception as exc:
            self.errorOccurred.emit("Could not build the prompt: %s" % exc)
            return

        self._cancel.clear()
        self._busy = True
        self.busyChanged.emit(True)
        t = threading.Thread(target=self._run, args=(prompt, images or []),
                             daemon=True)
        t.start()

    # -- worker thread ---------------------------------------------------

    def _run(self, prompt, images):
        self._emitted_text = False
        self._answer_text = ""
        try:
            from mpynode.native.toolchain import toolchain

            cmd = self._build_cmd(prompt, images)
            # Resolve the launcher to a full path so Windows can exec a .cmd/.exe
            # shim by full path (CreateProcess can't run a bare .cmd name).
            if cmd:
                cmd[0] = toolchain.resolve_executable(cmd[0])
            stdin_data = self._stdin_payload(prompt, images)
            # DEVNULL, not None: None INHERITS our stdin, and a GUI Maya has no
            # console, so the agent waits on a handle that never delivers. The
            # Claude CLI charges 3s for that on every request before giving up
            # ("no stdin data received in 3s"). DEVNULL is an immediate EOF.
            self._proc = subprocess.Popen(
                cmd,
                stdin=(subprocess.PIPE if stdin_data is not None
                       else subprocess.DEVNULL),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=1, **toolchain.cli_subprocess_kwargs())
            if stdin_data is not None:
                try:
                    self._proc.stdin.write(stdin_data)
                    self._proc.stdin.flush()
                    self._proc.stdin.close()
                except Exception:
                    pass
            dbg = _debug()
            if dbg:
                self.notice.emit("[debug] cmd: %s" % " ".join(cmd))
            for line in self._proc.stdout:
                if self._cancel.is_set():
                    break
                line = line.strip()
                if not line:
                    continue
                if dbg:
                    self.notice.emit("[raw] %s" % line[:800])
                try:
                    self._handle_event(line)
                except Exception:
                    pass
            self._proc.wait()
            if self._cancel.is_set():
                self.notice.emit("Stopped.")
            elif self._proc.returncode not in (0, None):
                err = ""
                try:
                    err = (self._proc.stderr.read() or "")[:600]
                except Exception:
                    pass
                self.errorOccurred.emit(
                    "%s exited %s%s" % (self._bin(), self._proc.returncode,
                                        (": " + err) if err else ""))
            else:
                # Apply the node payload the agent emitted (main thread).
                self._finalize()
            self.turnFinished.emit()
        except Exception as exc:
            self.errorOccurred.emit("%s: %s" % (type(exc).__name__, exc))
        finally:
            self._proc = None
            try:
                self._cleanup()
            except Exception:
                pass
            self._busy = False
            self.busyChanged.emit(False)

    def _finalize(self):
        """Extract + apply the node payload from the accumulated reply."""
        if self._cancel.is_set():
            return
        try:
            from mpynode.ui.llm import payload as _payload

            _payload.finalize_turn(self, self._node_name, self._ctx,
                                   self._answer_text)
        except Exception:
            pass

    # -- subclass hooks --------------------------------------------------

    def _bin(self):
        raise NotImplementedError

    def _build_cmd(self, prompt, images):
        raise NotImplementedError

    def _stdin_payload(self, prompt, images):
        return None

    def _handle_event(self, line):
        raise NotImplementedError

    def _cleanup(self):
        pass
