"""Google Gemini ``generateContent`` tool-calling client (stdlib only).

Mirrors ``anthropic_client.AssistantClient`` exactly -- same Qt signal
surface, same threading model (background worker thread + tool calls
marshaled onto Maya's main thread), same shared tools/system-prompt. Only the
wire format differs (Gemini ``contents`` / ``functionCall`` / ``functionResponse``
vs Anthropic ``messages`` / ``tool_use`` / ``tool_result``), so the two are
interchangeable behind ``llm.make_client``.

No third-party SDK -- talks to the REST API over ``urllib``.

Config (read fresh per turn, via ``llm.config``):
  * API key   -- preference ``assistant_api_key_gemini`` or env GEMINI_API_KEY / GOOGLE_API_KEY
  * model     -- preference ``assistant_model_gemini`` (default in config)
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

PROVIDER  = "gemini"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
# Generous so a big define_node payload isn't truncated mid-call.
_MAX_TOKENS = 8192

# JSON-schema type -> Gemini Schema type (the proto enum is upper-case).
_TYPE_MAP = {
    "object":  "OBJECT",
    "string":  "STRING",
    "number":  "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "array":   "ARRAY",
}


def get_api_key() -> str:
    return _config.get_api_key(PROVIDER)


def get_model() -> str:
    return _config.get_model(PROVIDER)


# ---------------------------------------------------------------------------
# Tool-schema translation: Anthropic input_schema -> Gemini functionDeclarations
# ---------------------------------------------------------------------------


def _to_gemini_schema(s: dict) -> dict:
    """Convert one JSON-schema node to a Gemini ``Schema``.

    Gemini requires every property to be typed; our untyped ``value`` (any
    JSON) becomes a STRING carrying JSON text (``tools._coerce_value`` parses
    it back on dispatch).
    """
    s     = s if isinstance(s, dict) else {}
    typed = "type" in s
    t     = s.get("type") or "string"
    out: dict = {"type": _TYPE_MAP.get(t, "STRING")}

    desc = s.get("description")
    if not typed and out["type"] == "STRING":
        hint = 'Pass as JSON text (e.g. "[1, 2, 3]" or "3.14" or "hello").'
        desc = (desc + " " + hint) if desc else hint
    if desc:
        out["description"] = desc
    if "enum" in s:
        out["enum"] = list(s["enum"])

    if out["type"] == "OBJECT":
        props             = s.get("properties") or {}
        out["properties"] = {k: _to_gemini_schema(v) for k, v in props.items()}
        if s.get("required"):
            out["required"] = list(s["required"])
    elif out["type"] == "ARRAY":
        out["items"] = _to_gemini_schema(s.get("items") or {"type": "string"})
    return out


def build_gemini_tools() -> list[dict]:
    """Translate ``tools.TOOL_SCHEMAS`` into Gemini ``tools`` form."""
    decls = []
    for t in _tools.TOOL_SCHEMAS:
        decl   = {"name": t["name"], "description": t.get("description", "")}
        params = _to_gemini_schema(t.get("input_schema") or {})
        # A function with no parameters must omit ``parameters`` entirely.
        if params.get("properties"):
            decl["parameters"] = params
        decls.append(decl)
    return [{"functionDeclarations": decls}]


def _post(payload, api_key, model, on_retry=None, should_cancel=None, timeout=120.0):
    url  = "%s/%s:generateContent" % (_API_BASE, model)
    data = json.dumps(payload).encode("utf-8")

    def _once():
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("content-type", "application/json")
        req.add_header("x-goog-api-key", api_key)  # key in header, not URL
        with urllib.request.urlopen(
            req, timeout=timeout, context=_config.ssl_context()
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _config.request_with_retry(
        _once, on_retry=on_retry, should_cancel=should_cancel
    )


def describe_model(api_key, model, timeout=20.0):
    """Cheap read-only check: GET the model resource (no tokens spent).

    Returns ``(ok, message)`` -- validates key, model id, network + TLS in one
    shot. ``404`` => bad model id; ``400/403`` => bad/again key.
    """
    if not api_key:
        return False, "No Gemini API key set."
    url = "%s/%s" % (_API_BASE, model)
    req = urllib.request.Request(url, method="GET")
    req.add_header("x-goog-api-key", api_key)
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=_config.ssl_context()
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = data.get("name") or model
        return True, "Connected \u2014 %s reachable" % name
    except urllib.error.HTTPError as exc:
        return False, "HTTP %s: %s" % (getattr(exc, "code", "?"), _http_error_msg(exc))
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, exc)


def _http_error_msg(exc):
    try:
        data = json.loads(exc.read().decode("utf-8", "replace"))
        err  = data.get("error", {})
        return err.get("message") if isinstance(err, dict) else str(err)
    except Exception:
        return getattr(exc, "reason", "request failed")


# Substrings that mark a model as NOT a general text/tool chat model for our
# use case (image-gen "nano-banana", embeddings, TTS, vision-only, etc.).
_GEM_EXCLUDE = (
    "embedding", "aqa", "tts", "image", "imagen", "vision", "nano",
    "gemma", "learnlm", "live", "audio", "veo", "robotics",
)


def list_models(api_key, timeout=20.0):
    """Chat/tool-capable Gemini model ids for this key, sorted. [] on failure."""
    if not api_key:
        return []
    req = urllib.request.Request(_API_BASE, method="GET")
    req.add_header("x-goog-api-key", api_key)
    try:
        with urllib.request.urlopen(
            req, timeout=timeout, context=_config.ssl_context()
        ) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []
    out = []
    for m in (data.get("models") or []):
        if "generateContent" not in (m.get("supportedGenerationMethods") or []):
            continue
        name = m.get("name", "")
        if name.startswith("models/"):
            name = name[len("models/"):]
        low = name.lower()
        if not low.startswith("gemini"):
            continue  # keep the main chat family only
        if any(x in low for x in _GEM_EXCLUDE):
            continue
        out.append(name)
    return sorted(set(out), key=str.lower)


def _json_safe(obj):
    """Force a value through JSON so it is safe inside a functionResponse."""
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"value": str(obj)}


class GeminiClient(QObject):
    """Gemini sibling of ``AssistantClient`` -- identical public surface.

    Signals (all delivered on the GUI thread):
      * ``assistantText(str)``   -- a chunk of the model's prose.
      * ``toolStarted(str)``     -- human-readable tool summary.
      * ``toolFinished(str)``    -- compact tool result line.
      * ``turnFinished()``       -- the model finished (no function calls).
      * ``notice(str)``          -- transient status (e.g. rate-limit retry).
      * ``errorOccurred(str)``   -- network / API / config error.
      * ``busyChanged(bool)``    -- True while a turn is in flight.
    """

    assistantText  = Signal(str)
    toolStarted    = Signal(str)
    toolFinished   = Signal(str)
    turnFinished   = Signal()
    notice         = Signal(str)
    thinking       = Signal(str)                      # thinking trace (when effort > off)
    retryScheduled = Signal(int, int, int, int, str)  # code, secs, attempt, max, detail
    tokensUsed     = Signal(int)                      # tokens consumed by one response
    errorOccurred  = Signal(str)
    busyChanged    = Signal(bool)

    def __init__(self, ctx_provider, parent=None):
        super().__init__(parent)
        self._ctx_provider = ctx_provider
        self._contents: list[dict] = []  # Gemini conversation history
        self._busy   = False
        self._cancel = threading.Event()

    def reset(self):
        self._contents = []

    def is_busy(self) -> bool:
        return self._busy

    def cancel(self):
        """Request the in-flight turn to stop ASAP (safe to call any time)."""
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
                "No Gemini API key. Set it in the \u2699 settings, or the "
                "GEMINI_API_KEY environment variable."
            )
            return
        self._cancel.clear()
        parts = [{"text": user_text}]
        for im in (images or []):
            if im.get("name"):  # label so an @imageN mention correlates
                parts.append({"text": "%s:" % im["name"]})
            parts.append({"inlineData": {"mimeType": im.get("media_type", "image/png"),
                                         "data": im["data"]}})
        self._contents.append({"role": "user", "parts": parts})
        self._busy = True
        self.busyChanged.emit(True)
        t = threading.Thread(
            target=self._run_turn, args=(api_key, get_model()), daemon=True
        )
        t.start()

    # -- worker thread ---------------------------------------------------

    def _run_turn(self, api_key: str, model: str):
        try:
            system_text = build_system_prompt()
            gem_tools   = build_gemini_tools()
            ctx         = self._ctx_provider()
            # Thinking budget from the per-provider effort setting. Off = omit
            # (use the model's default) to avoid erroring on models that can't
            # disable thinking.
            gen_config = {"maxOutputTokens": _MAX_TOKENS}
            budget     = _config.effort_budget(_config.get_effort(PROVIDER))
            if budget > 0:
                gen_config["thinkingConfig"] = {"thinkingBudget": budget,
                                                "includeThoughts": True}
            err_rounds = 0
            for _ in range(24):  # tool-call rounds cap (safety)
                if self._cancel.is_set():
                    self._finish_cancelled()
                    break
                payload = {
                    "systemInstruction": {"parts": [{"text": system_text}]},
                    "contents":          self._contents,
                    "tools":             gem_tools,
                    "generationConfig":  gen_config,
                }
                try:
                    resp = _post(payload, api_key, model, on_retry=self._on_retry,
                                 should_cancel=self._cancel.is_set)
                except _config.CancelledError:
                    self._finish_cancelled()
                    break
                if "error" in resp:
                    msg = resp.get("error", {})
                    self.errorOccurred.emit(
                        "API error: %s" % (msg.get("message") if isinstance(msg, dict) else msg)
                    )
                    break

                um = resp.get("usageMetadata") or {}
                if um.get("totalTokenCount"):
                    self.tokensUsed.emit(int(um["totalTokenCount"]))

                cands = resp.get("candidates") or []
                if not cands:
                    pf      = resp.get("promptFeedback") or {}
                    blocked = pf.get("blockReason")
                    self.errorOccurred.emit(
                        "Empty response%s." % (" (blocked: %s)" % blocked if blocked else "")
                    )
                    break

                cand  = cands[0]
                parts = (cand.get("content") or {}).get("parts") or []
                # Record the model turn verbatim so tool context is preserved.
                self._contents.append({"role": "model", "parts": parts})

                func_calls   = []
                emitted_text = False
                for p in parts:
                    txt = p.get("text")
                    if p.get("thought"):  # thinking trace, not the answer
                        if txt:
                            self.thinking.emit(txt)
                        continue
                    if txt:
                        self.assistantText.emit(txt)
                        emitted_text = True
                    fc = p.get("functionCall")
                    if fc:
                        func_calls.append(fc)

                if not func_calls:
                    reason = cand.get("finishReason")
                    if not emitted_text:
                        # Candidate came back empty -- don't fail silently. Most
                        # often a SAFETY/RECITATION block (e.g. a flagged image)
                        # or MAX_TOKENS; surface the reason so it's actionable.
                        sr      = (cand.get("safetyRatings") or [])
                        blocked = [r.get("category") for r in sr if r.get("blocked")]
                        detail  = "finishReason=%s" % (reason or "unspecified")
                        if blocked:
                            detail += ", blocked: %s" % ", ".join(blocked)
                        self.errorOccurred.emit(
                            "Gemini returned no content (%s). If an image is "
                            "attached it may have been blocked or the model "
                            "couldn't read it \u2014 try a different/clearer image, "
                            "rephrase, or use Claude for this one." % detail
                        )
                    elif reason == "MAX_TOKENS":
                        self.errorOccurred.emit(
                            "The reply was cut off (hit the output limit). Try "
                            "again, or split the request into smaller steps."
                        )
                    self.turnFinished.emit()
                    break

                # Execute each call on the MAIN thread, return functionResponses.
                resp_parts = []
                n_err      = 0
                for fc in func_calls:
                    name    = fc.get("name", "")
                    args    = fc.get("args") or {}
                    display = _tools.resolve_tool_name(name) or name
                    self.toolStarted.emit(_tools.tool_summary(display, args))
                    result = self._run_tool_main_thread(name, args, ctx)
                    self.toolFinished.emit(_tools.compact_result(display, result))
                    if isinstance(result, dict) and "error" in result:
                        n_err += 1
                    resp_obj = result if isinstance(result, dict) else {"result": result}
                    resp_parts.append({
                        "functionResponse": {
                            "name":     name,
                            "response": _json_safe(resp_obj),
                        }
                    })
                self._contents.append({"role": "user", "parts": resp_parts})

                # Runaway guard: bail if the model keeps calling tools that all
                # fail (e.g. hallucinated names) instead of hitting the rate limit.
                err_rounds = err_rounds + 1 if n_err == len(func_calls) else 0
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
        """Close out a cancelled turn with valid, resumable history."""
        # History ends on a user-role message here; add a model placeholder so
        # the next user message keeps the required user/model alternation.
        self._contents.append({"role": "model", "parts": [{"text": "(interrupted)"}]})
        self.notice.emit("Stopped.")
        self.turnFinished.emit()

    def _on_retry(self, code, delay, attempt, max_retries, detail=""):
        # Structured so the UI can run a live countdown.
        self.retryScheduled.emit(int(code or 0), int(round(delay)),
                                 int(attempt), int(max_retries), detail or "")

    def _run_tool_main_thread(self, name: str, args: dict, ctx) -> dict:
        try:
            import maya.utils as mu

            return mu.executeInMainThreadWithResult(
                lambda: _tools.dispatch(name, args, ctx)
            )
        except Exception as exc:
            return {"error": "main-thread dispatch failed: %s" % exc}
