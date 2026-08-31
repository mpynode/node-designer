"""Codex CLI provider -- drive the local `codex` binary.

Runs `codex exec --json` non-interactively. The agent can't call back into Maya,
so it replies with ONE JSON node payload (the prompt carries the active node +
cheat-sheet via ``llm.payload.build_prompt``) which the base client applies
through the tested define_node spine. Uses the machine's Codex / ChatGPT login
(no API key).

Supports effort (`-c model_reasoning_effort=...`) and images (`-i <tempfile>`).
"""

from __future__ import annotations

import json
import os
import subprocess  # noqa: F401  (used via base; kept for parity)
import tempfile

from mpynode.ui.llm.cli_base import BaseCliClient

_BIN = os.environ.get("CODEX_BIN", "codex")


def _model():
    from mpynode.ui.llm import config as _config

    return _config.get_model("codex_cli")


def _effort():
    from mpynode.ui.llm import config as _config

    return _config.get_effort("codex_cli")


def build_cmd(bin_path, prompt, model=None, effort=None, image_paths=None):
    """argv for a non-interactive Codex run (pure -- unit-testable)."""
    cmd = [bin_path, "exec", "--json",
           "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check"]
    if model:
        cmd += ["-m", model]
    if effort and effort != "off":
        cmd += ["-c", 'model_reasoning_effort="%s"' % effort]
    for p in (image_paths or []):
        cmd += ["-i", p]
    cmd += [prompt]
    return cmd


class CodexCliClient(BaseCliClient):
    PROVIDER = "codex_cli"
    LABEL = "Codex CLI"

    def __init__(self, ctx_provider=None, parent=None):
        super().__init__(ctx_provider, parent)
        self._tmp_images = []

    def _bin(self):
        return _BIN

    def _build_cmd(self, prompt, images):
        self._tmp_images = []
        for im in (images or []):
            try:
                import base64

                fd, path = tempfile.mkstemp(suffix=".png", prefix="mpynode_img_")
                with os.fdopen(fd, "wb") as f:
                    f.write(base64.b64decode(im["data"]))
                self._tmp_images.append(path)
            except Exception:
                pass
        return build_cmd(_BIN, prompt, model=_model(), effort=_effort(),
                         image_paths=self._tmp_images)

    def _cleanup(self):
        for p in self._tmp_images:
            try:
                os.remove(p)
            except Exception:
                pass
        self._tmp_images = []

    def _handle_event(self, line):
        # `codex exec --json` emits JSONL events; schema varies by version, so
        # parse defensively across the item/msg shapes.
        try:
            ev = json.loads(line)
        except Exception:
            return
        if not isinstance(ev, dict):
            return
        outer = str(ev.get("type", "")).lower()
        item = ev.get("item") or ev.get("msg") or ev
        typ = str(item.get("type", "") or outer).lower()
        text = (item.get("text") or item.get("message")
                or item.get("content") or item.get("delta"))
        if isinstance(text, dict):
            text = text.get("text")

        if "reasoning" in typ or "thinking" in typ:
            if isinstance(text, str) and text.strip():
                self.thinking.emit(text)
            return
        if ("agent_message" in typ or "assistant" in typ
                or ("message" in typ and text)):
            if isinstance(text, str) and text.strip():
                self._emit_answer(text)
