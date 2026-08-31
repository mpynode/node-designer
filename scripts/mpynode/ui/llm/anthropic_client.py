"""Anthropic Messages-API tool-calling client (stdlib only).

No third-party SDK -- talks to the API over ``urllib`` so it works in a
vanilla Maya Python with no pip install. Runs the request/tool loop on a
background ``threading.Thread`` so Maya's UI never blocks; tool calls are
marshaled back onto the main thread (Maya is not thread-safe) via
``maya.utils.executeInMainThreadWithResult``. Progress is reported through
Qt signals (queued to the GUI thread).

Config (read fresh per turn, via ``llm.config``):
  * API key   -- preference ``assistant_api_key_anthropic`` or env ANTHROPIC_API_KEY
  * model     -- preference ``assistant_model_anthropic`` (default in config)
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

PROVIDER = "anthropic"
_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
# Generous so a big define_node (full compute+init+viewport source) isn't
# truncated mid tool-call -- truncation used to leave a dangling tool_use.
_MAX_TOKENS = 8192


def get_api_key() -> str:
    return _config.get_api_key(PROVIDER)


def get_model() -> str:
    return _config.get_model(PROVIDER)


def _post(payload, api_key, on_retry=None, should_cancel=None, timeout=120.0):
    data = json.dumps(payload).encode("utf-8")

    def _once():
        req = urllib.request.Request(_API_URL, data=data, method="POST")
        req.add_header("content-type", "application/json")
        req.add_header("anthropic-version", _API_VERSION)
        req.add_header("x-api-key", api_key)
        with urllib.request.urlopen(
            req, timeout=timeout, context=_config.ssl_context()
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _config.request_with_retry(
        _once, on_retry=on_retry, should_cancel=should_cancel
    )


def describe_model(api_key, model, timeout=20.0):
    """Cheap read-only check: GET the model via the Models API (no tokens).

    Returns ``(ok, message)`` -- validates key, model id, network + TLS.
    ``401`` => bad key; ``404`` => bad/unavailable model.
    """
    if not api_key:
        return False, "No Anthropic API key set."
    url = "https://api.anthropic.com/v1/models/%s" % model
    req = urllib.request.Request(url, method="GET")
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", _API_VERSION)
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=_config.ssl_context()
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = data.get("id") or model
        return True, "Connected \u2014 %s reachable" % name
    except urllib.error.HTTPError as exc:
        return False, "HTTP %s: %s" % (getattr(exc, "code", "?"), _http_error_msg(exc))
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def _http_error_msg(exc):
    try:
        data = json.loads(exc.read().decode("utf-8", "replace"))
        err = data.get("error", {})
        return err.get("message") if isinstance(err, dict) else str(err)
    except Exception:
        return getattr(exc, "reason", "request failed")


def list_models_detailed(api_key, timeout=20.0):
    """Full model rows from the Anthropic Models API. [] on failure.

    Callers need more than the id: ``max_input_tokens`` is what lets the Claude
    CLI list derive its 1M-context "[1m]" variants (the HTTP list never returns
    those, but the CLI accepts them), and ``created_at`` gives a real
    newest-first order instead of an alphabetical one.
    """
    if not api_key:
        return []
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/models?limit=100", method="GET")
    req.add_header("x-api-key", api_key)
    req.add_header("anthropic-version", _API_VERSION)
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=_config.ssl_context()
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []
    # Keep every model the key returns (Anthropic's list is all chat models) so
    # new / non-"claude-" ids (e.g. internal aliases) appear too.
    return [m for m in (data.get("data") or []) if m.get("id")]


def list_models(api_key, timeout=20.0):
    """Model ids available to this key (Anthropic Models API). [] on failure."""
    ids = [m["id"] for m in list_models_detailed(api_key, timeout)]
    return sorted(set(ids), key=str.lower)


class AssistantClient(QObject):
    """Drives a multi-turn tool-calling conversation. One instance per panel.

    Signals (all delivered on the GUI thread):
      * ``assistantText(str)``   -- a chunk of the model's prose.
      * ``toolStarted(str)``     -- human-readable tool summary.
      * ``toolFinished(str)``    -- compact tool result line.
      * ``turnFinished()``       -- the model finished (stop_reason end_turn).
      * ``notice(str)``          -- transient status (e.g. rate-limit retry).
      * ``errorOccurred(str)``   -- network / API / config error.
      * ``busyChanged(bool)``    -- True while a turn is in flight.
    """

    assistantText = Signal(str)
    toolStarted = Signal(str)
    toolFinished = Signal(str)
    turnFinished = Signal()
    notice = Signal(str)
    thinking = Signal(str)  # extended-thinking trace (when effort > off)
    retryScheduled = Signal(int, int, int, int, str)  # code, secs, attempt, max, detail
    tokensUsed = Signal(int)  # tokens consumed by one response
    errorOccurred = Signal(str)
    busyChanged = Signal(bool)

    def __init__(self, ctx_provider, parent=None):
        super().__init__(parent)
        # ctx_provider() -> a fresh ToolContext for each turn (so the working
        # node tracks the host UI's active tab).
        self._ctx_provider = ctx_provider
        self._messages: list[dict] = []
        self._busy = False
        self._cancel = threading.Event()

    def reset(self):
        self._messages = []

    def is_busy(self) -> bool:
        return self._busy

    def cancel(self):
        """Request the in-flight turn to stop ASAP (safe to call any time)."""
        if self._busy:
            self._cancel.set()
            self.notice.emit("Stopping\u2026")

    def _repair_tail(self):
        """Strip a trailing assistant ``tool_use`` that has no ``tool_result``.

        The Messages API rejects a request whose history contains a tool_use
        not immediately followed by a tool_result. Such a tail can only arise
        from an interrupted/truncated turn; drop the orphan tool_use blocks
        (keeping any prose) so the next message is valid.
        """
        while self._messages:
            last = self._messages[-1]
            if last.get("role") != "assistant":
                break
            content = last.get("content")
            if not isinstance(content, list):
                break
            if not any(b.get("type") == "tool_use" for b in content):
                break
            safe = [b for b in content if b.get("type") != "tool_use"]
            if safe:
                last["content"] = safe
                break
            self._messages.pop()  # nothing but tool_use -> drop, re-check

    def send(self, user_text: str, images=None):
        if self._busy:
            self.errorOccurred.emit("AI Assistant is still working on the previous request.")
            return
        api_key = get_api_key()
        if not api_key:
            self.errorOccurred.emit(
                "No Anthropic API key. Set it in the \u2699 settings, or the "
                "ANTHROPIC_API_KEY environment variable."
            )
            return
        self._cancel.clear()
        self._repair_tail()
        # Multimodal content when images are attached (base64 PNGs); else a
        # plain string keeps the common path identical.
        if images:
            content = [{"type": "text", "text": user_text}]
            for im in images:
                if im.get("name"):  # label so an @imageN mention correlates
                    content.append({"type": "text", "text": "%s:" % im["name"]})
                content.append({
                    "type": "image",
                    "source": {"type": "base64",
                               "media_type": im.get("media_type", "image/png"),
                               "data": im["data"]},
                })
            self._messages.append({"role": "user", "content": content})
        else:
            self._messages.append({"role": "user", "content": user_text})
        self._busy = True
        self.busyChanged.emit(True)
        t = threading.Thread(
            target=self._run_turn, args=(api_key, get_model()), daemon=True
        )
        t.start()

    # -- worker thread ---------------------------------------------------

    def _run_turn(self, api_key: str, model: str):
        try:
            system = build_system_prompt()
            ctx = self._ctx_provider()
            # Extended thinking. Newer models want the "adaptive" form +
            # output_config.effort, older ones "enabled" + budget_tokens.
            # Adaptive first, fall back to budget on a thinking-related 400.
            effort = _config.get_effort(PROVIDER)        # off/low/medium/high
            think_on = effort != "off"
            budget = _config.effort_budget(effort)
            think_mode = "adaptive" if think_on else None
            think_tried = set()
            err_rounds = 0
            for _ in range(24):  # tool-call rounds cap (safety)
                if self._cancel.is_set():
                    self._finish_cancelled()
                    break
                max_tokens = _MAX_TOKENS
                payload = {
                    "model": model,
                    "max_tokens": max_tokens,
                    # Prompt caching: one breakpoint at the end of the system
                    # block caches the static prefix (tools + system) that is
                    # re-sent every round. Cache reads cost ~10% of normal.
                    # Ignored if the prefix is below the model's cache minimum,
                    # so it is always safe to send.
                    "system": [{
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    "tools": _tools.TOOL_SCHEMAS,
                    "messages": self._messages,
                }
                if think_on:
                    if think_mode == "adaptive":
                        payload["thinking"] = {"type": "adaptive"}
                        payload["output_config"] = {"effort": effort}
                    else:  # budget form (older models); needs max_tokens > budget
                        payload["max_tokens"] = max(_MAX_TOKENS, budget + 4096)
                        payload["thinking"] = {"type": "enabled",
                                               "budget_tokens": budget}
                try:
                    resp = _post(payload, api_key, on_retry=self._on_retry,
                                 should_cancel=self._cancel.is_set)
                except _config.CancelledError:
                    self._finish_cancelled()
                    break
                except RuntimeError as exc:
                    # If the model rejects this thinking form, switch to the
                    # other one and retry the round (once).
                    if think_on and "thinking" in str(exc).lower():
                        think_tried.add(think_mode)
                        alt = "budget" if think_mode == "adaptive" else "adaptive"
                        if alt not in think_tried:
                            think_mode = alt
                            continue
                    raise
                if resp.get("type") == "error" or "content" not in resp:
                    msg = resp.get("error", {}).get("message", str(resp))
                    self.errorOccurred.emit("API error: %s" % msg)
                    break

                u = resp.get("usage") or {}
                tot = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
                if tot:
                    self.tokensUsed.emit(int(tot))

                content = resp.get("content", [])
                stop = resp.get("stop_reason")

                tool_uses = []
                for block in content:
                    bt = block.get("type")
                    if bt == "text":
                        txt = block.get("text", "")
                        if txt:
                            self.assistantText.emit(txt)
                    elif bt == "thinking":
                        th = block.get("thinking", "")
                        if th:
                            self.thinking.emit(th)
                    elif bt == "tool_use":
                        tool_uses.append(block)

                if not (stop == "tool_use" and tool_uses):
                    # Final turn (end_turn) or truncated (max_tokens). The API
                    # rejects a tool_use not followed by tool_result, so drop
                    # partial tool_use blocks and keep only the prose.
                    safe = [b for b in content if b.get("type") != "tool_use"]
                    if safe:
                        self._messages.append({"role": "assistant", "content": safe})
                    if stop == "max_tokens":
                        self.errorOccurred.emit(
                            "The reply was cut off (hit the output limit). Try "
                            "again, or split the request (e.g. create the node "
                            "first, then set the expression in a follow-up)."
                        )
                    self.turnFinished.emit()
                    break

                # Tool round: record the assistant turn verbatim, then run tools.
                self._messages.append({"role": "assistant", "content": content})

                # Execute each tool on the MAIN thread, collect tool_result.
                results = []
                n_err = 0
                for tu in tool_uses:
                    name = tu.get("name", "")
                    args = tu.get("input", {}) or {}
                    display = _tools.resolve_tool_name(name) or name
                    self.toolStarted.emit(_tools.tool_summary(display, args))
                    result = self._run_tool_main_thread(name, args, ctx)
                    self.toolFinished.emit(_tools.compact_result(display, result))
                    if isinstance(result, dict) and "error" in result:
                        n_err += 1
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.get("id"),
                        "content": json.dumps(result, default=str),
                    })
                self._messages.append({"role": "user", "content": results})

                # Runaway guard: model keeps calling tools that all fail.
                err_rounds = err_rounds + 1 if n_err == len(tool_uses) else 0
                if err_rounds >= 3:
                    self.errorOccurred.emit(
                        "Stopped: the model repeatedly called invalid tools. "
                        "Try rephrasing, or switch model in \u2699 settings."
                    )
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
        """Close out a cancelled turn with valid, resumable history.

        We only break at round boundaries, where ``_messages`` ends on a
        user-role message (the initial prompt or a tool_result batch). Append a
        short assistant message so role alternation holds for the next send.
        """
        self._messages.append({"role": "assistant", "content": "(interrupted)"})
        self.notice.emit("Stopped.")
        self.turnFinished.emit()

    def _on_retry(self, code, delay, attempt, max_retries, detail=""):
        # Structured so the UI can run a live countdown.
        self.retryScheduled.emit(int(code or 0), int(round(delay)),
                                 int(attempt), int(max_retries), detail or "")

    def _run_tool_main_thread(self, name: str, args: dict, ctx) -> dict:
        """Marshal a tool call onto Maya's main thread and return its result."""
        try:
            import maya.utils as mu

            return mu.executeInMainThreadWithResult(
                lambda: _tools.dispatch(name, args, ctx)
            )
        except Exception as exc:
            return {"error": "main-thread dispatch failed: %s" % exc}
