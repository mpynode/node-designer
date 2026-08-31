"""OpenAI (ChatGPT) Chat-Completions tool-calling client (stdlib only).

Sibling of the Anthropic/Gemini clients -- identical Qt signal surface and
threading model (worker thread + tool calls marshaled to Maya's main thread),
sharing the same tools/system-prompt + SSL/retry infra. Wire format is OpenAI
Chat Completions: messages + ``tools`` (functions) + ``tool_calls``.

Config (read fresh per turn, via ``llm.config``):
  * API key   -- preference ``assistant_api_key_openai`` or env OPENAI_API_KEY
  * model     -- preference ``assistant_model_openai`` (default in config)
  * effort    -- maps to ``reasoning_effort`` (reasoning models only; auto
                 dropped if the model rejects it)

NOTE: Chat Completions hides the reasoning trace, so the ``thinking`` signal
stays silent for this provider. Prompt caching is automatic on OpenAI.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from mpynode.ui.qt_wrapper import QObject, Signal
from mpynode.ui.llm import config as _config
from mpynode.ui.llm import tools as _tools
from mpynode.ui.llm.system_prompt import build_system_prompt

PROVIDER = "openai"
_API_URL = "https://api.openai.com/v1/chat/completions"
_MODELS_URL = "https://api.openai.com/v1/models"
_MAX_TOKENS = 8192


def get_api_key() -> str:
    return _config.get_api_key(PROVIDER)


def get_model() -> str:
    return _config.get_model(PROVIDER)


def build_openai_tools():
    """TOOL_SCHEMAS -> OpenAI `tools` (function) form."""
    out = []
    for t in _tools.TOOL_SCHEMAS:
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
            },
        })
    return out


def _post(payload, api_key, on_retry=None, should_cancel=None, timeout=120.0):
    data = json.dumps(payload).encode("utf-8")

    def _once():
        req = urllib.request.Request(_API_URL, data=data, method="POST")
        req.add_header("content-type", "application/json")
        req.add_header("authorization", "Bearer %s" % api_key)
        with urllib.request.urlopen(
            req, timeout=timeout, context=_config.ssl_context()
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _config.request_with_retry(_once, on_retry=on_retry,
                                      should_cancel=should_cancel)


class OpenAIClient(QObject):
    assistantText = Signal(str)
    toolStarted = Signal(str)
    toolFinished = Signal(str)
    turnFinished = Signal()
    notice = Signal(str)
    thinking = Signal(str)  # interface compat (Chat Completions hides reasoning)
    retryScheduled = Signal(int, int, int, int, str)
    tokensUsed = Signal(int)
    errorOccurred = Signal(str)
    busyChanged = Signal(bool)

    def __init__(self, ctx_provider, parent=None):
        super().__init__(parent)
        self._ctx_provider = ctx_provider
        self._messages = []  # OpenAI chat history
        self._busy = False
        self._cancel = threading.Event()

    def reset(self):
        self._messages = []

    def is_busy(self) -> bool:
        return self._busy

    def cancel(self):
        if self._busy:
            self._cancel.set()
            self.notice.emit("Stopping\u2026")

    def send(self, user_text: str, images=None):
        if self._busy:
            self.errorOccurred.emit("AI Assistant is still working on the previous request.")
            return
        api_key = get_api_key()
        if not api_key:
            self.errorOccurred.emit(
                "No OpenAI API key. Set it in the \u2699 settings, or the "
                "OPENAI_API_KEY environment variable."
            )
            return
        self._cancel.clear()
        # Multimodal content if images are attached, else a plain string.
        if images:
            content = [{"type": "text", "text": user_text}]
            for im in images:
                if im.get("name"):  # label so an @imageN mention correlates
                    content.append({"type": "text", "text": "%s:" % im["name"]})
                url = "data:%s;base64,%s" % (im.get("media_type", "image/png"),
                                             im["data"])
                content.append({"type": "image_url", "image_url": {"url": url}})
            self._messages.append({"role": "user", "content": content})
        else:
            self._messages.append({"role": "user", "content": user_text})
        self._busy = True
        self.busyChanged.emit(True)
        t = threading.Thread(target=self._run_turn, args=(api_key, get_model()),
                             daemon=True)
        t.start()

    # -- worker thread ---------------------------------------------------

    def _run_turn(self, api_key, model):
        try:
            system = build_system_prompt()
            oa_tools = build_openai_tools()
            ctx = self._ctx_provider()
            effort = _config.get_effort(PROVIDER)        # off/low/medium/high
            use_effort = effort != "off"                 # -> reasoning_effort
            err_rounds = 0
            for _ in range(24):  # tool-call rounds cap (safety)
                if self._cancel.is_set():
                    self._finish_cancelled()
                    break
                payload = {
                    "model": model,
                    "max_completion_tokens": _MAX_TOKENS,
                    "messages": [{"role": "system", "content": system}] + self._messages,
                    "tools": oa_tools,
                }
                if use_effort:
                    payload["reasoning_effort"] = effort
                try:
                    resp = _post(payload, api_key, on_retry=self._on_retry,
                                 should_cancel=self._cancel.is_set)
                except _config.CancelledError:
                    self._finish_cancelled()
                    break
                except RuntimeError as exc:
                    # reasoning_effort is only valid on reasoning models; drop
                    # it and retry once if the model rejects it.
                    m = str(exc).lower()
                    if use_effort and "reasoning_effort" in m:
                        use_effort = False
                        continue
                    raise

                if "choices" not in resp:
                    self.errorOccurred.emit(
                        "API error: %s" % resp.get("error", {}).get("message", str(resp)))
                    break

                u = resp.get("usage") or {}
                if u.get("total_tokens"):
                    self.tokensUsed.emit(int(u["total_tokens"]))

                msg = (resp["choices"][0] or {}).get("message", {}) or {}
                # Record the assistant turn verbatim.
                self._messages.append(msg)

                txt = msg.get("content")
                if txt:
                    self.assistantText.emit(txt)

                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    self.turnFinished.emit()
                    break

                n_err = 0
                for tc in tool_calls:
                    fn = (tc.get("function") or {})
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = {}
                    display = _tools.resolve_tool_name(name) or name
                    self.toolStarted.emit(_tools.tool_summary(display, args))
                    result = self._run_tool_main_thread(name, args, ctx)
                    self.toolFinished.emit(_tools.compact_result(display, result))
                    if isinstance(result, dict) and "error" in result:
                        n_err += 1
                    self._messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": json.dumps(result, default=str),
                    })

                err_rounds = err_rounds + 1 if n_err == len(tool_calls) else 0
                if err_rounds >= 3:
                    self.errorOccurred.emit(
                        "Stopped: the model repeatedly called invalid tools. "
                        "Try rephrasing, or switch model in \u2699 settings.")
                    break
            else:
                self.errorOccurred.emit("Stopped: too many tool rounds.")
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                pass
            self.errorOccurred.emit("HTTP %s: %s" % (getattr(exc, "code", "?"), body[:500]))
        except Exception as exc:
            self.errorOccurred.emit("%s: %s" % (type(exc).__name__, exc))
        finally:
            self._busy = False
            self.busyChanged.emit(False)

    def _finish_cancelled(self):
        # History ends on a user/tool message; an assistant note keeps the
        # next turn valid.
        self._messages.append({"role": "assistant", "content": "(interrupted)"})
        self.notice.emit("Stopped.")
        self.turnFinished.emit()

    def _on_retry(self, code, delay, attempt, max_retries, detail=""):
        self.retryScheduled.emit(int(code or 0), int(round(delay)),
                                 int(attempt), int(max_retries), detail or "")

    def _run_tool_main_thread(self, name, args, ctx):
        try:
            import maya.utils as mu

            return mu.executeInMainThreadWithResult(
                lambda: _tools.dispatch(name, args, ctx)
            )
        except Exception as exc:
            return {"error": "main-thread dispatch failed: %s" % exc}


# ---------------------------------------------------------------------------
# Models (Refresh + Test)
# ---------------------------------------------------------------------------

# Keep chat/reasoning models; drop embeddings/audio/image/moderation, etc.
_MODEL_EXCLUDE = ("embedding", "tts", "whisper", "audio", "dall-e", "image",
                  "moderation", "realtime", "transcribe", "search", "codex")


def _get(url, api_key, timeout=20.0):
    req = urllib.request.Request(url, method="GET")
    req.add_header("authorization", "Bearer %s" % api_key)
    with urllib.request.urlopen(
        req, timeout=timeout, context=_config.ssl_context()
    ) as r:
        return json.loads(r.read().decode("utf-8"))


def list_models(api_key, timeout=20.0):
    """Chat-capable OpenAI model ids, sorted. [] on failure."""
    if not api_key:
        return []
    try:
        data = _get(_MODELS_URL, api_key, timeout)
    except Exception:
        return []
    out = []
    for m in (data.get("data") or []):
        mid = m.get("id", "")
        low = mid.lower()
        if not (low.startswith("gpt") or low.startswith("o1") or low.startswith("o3")
                or low.startswith("o4") or low.startswith("chatgpt")):
            continue
        if any(x in low for x in _MODEL_EXCLUDE):
            continue
        out.append(mid)
    return sorted(set(out), key=str.lower)


def describe_model(api_key, model, timeout=20.0):
    """Cheap read-only check: GET the model. Returns (ok, message)."""
    if not api_key:
        return False, "No OpenAI API key set."
    try:
        data = _get("%s/%s" % (_MODELS_URL, model), api_key, timeout)
        return True, "Connected \u2014 %s reachable" % (data.get("id") or model)
    except urllib.error.HTTPError as exc:
        msg = "request failed"
        try:
            body = json.loads(exc.read().decode("utf-8", "replace"))
            msg = body.get("error", {}).get("message", msg)
        except Exception:
            pass
        return False, "HTTP %s: %s" % (getattr(exc, "code", "?"), msg)
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)
