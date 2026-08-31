"""Gemini CLI provider -- drive the local `gemini` binary.

Runs `gemini -p` non-interactively and streams `-o stream-json`. The agent can't
call back into Maya, so it replies with ONE JSON node payload (the prompt carries
the active node + cheat-sheet via ``llm.payload.build_prompt``) which the base
client applies through the tested define_node spine. Uses the machine's Gemini
login (no API key).

Notes vs other providers: Gemini CLI's headless mode has no image or effort flag,
so images + Reasoning don't apply here.
"""

from __future__ import annotations

import json
import os

from mpynode.ui.llm.cli_base import BaseCliClient

_BIN = os.environ.get("GEMINI_BIN", "gemini")


def _model():
    from mpynode.ui.llm import config as _config

    return _config.get_model("gemini_cli")


def build_cmd(bin_path, prompt, model=None, resume=None):
    """argv for a non-interactive Gemini CLI run (pure -- unit-testable)."""
    cmd = [bin_path, "-p", prompt, "-o", "stream-json", "-y"]
    if model:
        cmd += ["-m", model]
    if resume:
        cmd += ["-r", resume]
    return cmd


class GeminiCliClient(BaseCliClient):
    PROVIDER = "gemini_cli"
    LABEL = "Gemini CLI"

    def _bin(self):
        return _BIN

    def _build_cmd(self, prompt, images):
        if images:
            self.notice.emit("(images aren't supported by the Gemini CLI provider)")
        return build_cmd(_BIN, prompt, model=_model())

    def _handle_event(self, line):
        # Gemini CLI -o stream-json NDJSON. Observed event types: init,
        # message{role,content}, result{stats}.
        try:
            ev = json.loads(line)
        except Exception:
            return
        if not isinstance(ev, dict):
            return
        typ = str(ev.get("type", "")).lower()

        if typ == "init":
            return

        if typ == "message":
            if str(ev.get("role", "")).lower() in ("user", "system"):
                return  # don't echo our own prompt back
            content = ev.get("content")
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content
                                  if isinstance(p, dict))
            if isinstance(content, str) and content.strip():
                self._emit_answer(content)
            return

        if "thought" in typ or "reasoning" in typ:
            t = ev.get("content") or ev.get("text")
            if isinstance(t, str) and t.strip():
                self.thinking.emit(t)
            return

        if typ == "result":
            stats = ev.get("stats") or {}
            if stats.get("total_tokens"):
                self.tokensUsed.emit(int(stats["total_tokens"]))
            if not self._emitted_text:
                self.errorOccurred.emit(
                    "Gemini CLI returned no output (0 tokens) -- the model "
                    "didn't run. Verify `gemini -p \"hello\" -o stream-json` "
                    "responds in a terminal, and that the model is valid.")
            return
