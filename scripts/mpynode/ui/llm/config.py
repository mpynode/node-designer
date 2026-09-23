"""Provider-agnostic assistant config (provider selection, keys, models).

Keys and models are stored PER PROVIDER so switching providers doesn't clob-
ber the other's settings:
  * preference ``assistant_provider``            -> "anthropic" | "gemini"
  * preference ``assistant_api_key_<provider>``  -> API key (or env fallback)
  * preference ``assistant_model_<provider>``    -> model id (or default)
"""

from __future__ import annotations

import collections
import os
import re
import ssl
import time

PROVIDERS = ("anthropic", "gemini", "openai",
             "claude_cli", "gemini_cli", "codex_cli")

DEFAULT_PROVIDER = "anthropic"

# Defaults; editable in the panel because model ids drift. CLI providers have
# no default -- blank means "use the CLI's own".
DEFAULT_MODELS = {
    "anthropic":  "claude-sonnet-4-5",
    "gemini":     "gemini-2.5-flash",
    "openai":     "gpt-4o",
    "claude_cli": "",
    "gemini_cli": "",
    "codex_cli":  "",
}

# Environment-variable fallbacks for the key (checked in order). CLI providers
# need no key (they use the CLI's own machine login).
_ENV_KEYS = {
    "anthropic":  ("ANTHROPIC_API_KEY",),
    "gemini":     ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai":     ("OPENAI_API_KEY",),
    "claude_cli": (),
    "gemini_cli": (),
    "codex_cli":  (),
}

PROVIDER_LABELS = {
    "anthropic":  "Claude (Anthropic API)",
    "gemini":     "Gemini (Google API)",
    "openai":     "ChatGPT (OpenAI API)",
    "claude_cli": "Claude CLI",
    "gemini_cli": "Gemini CLI (experimental)",
    "codex_cli":  "Codex CLI (experimental)",
}

# Providers that use an API key + model in the panel (vs. the local CLIs).
API_PROVIDERS = ("anthropic", "gemini", "openai")
# CLI-backed providers (run a local agent binary; no API key).
CLI_PROVIDERS = ("claude_cli", "gemini_cli", "codex_cli")
# ---------------------------------------------------------------------------
# Gemini CLI headless invocation -- shared by the interactive assistant
# (ui.llm.gemini_cli_client) and the compile porter (native.ai.llm_client),
# because both hit the same two walls independently:
#
# * The prompt CANNOT ride in argv. A node payload or a port prompt runs to tens
#   of KB; Windows then refuses the spawn outright (CreateProcess -> WinError
#   206, "The filename or extension is too long") or, through npm's .cmd
#   launcher and cmd.exe, "The command line is too long." at ~8 KB. Gemini CLI
#   documents ``-p`` as "Appended to input on stdin (if any)", so the prompt
#   goes to STDIN and ``-p`` carries the tail below.
# * The tail must be NON-EMPTY: ``-p ""`` is falsy to the CLI's argument parser,
#   which drops it back into interactive mode -- and with no TTY that hangs.
#
# ``--skip-trust`` is what lets it start at all: the CLI refuses to run in a
# folder that was never trusted interactively (exit 55, "not running in a
# trusted directory"), and Maya's working directory never has been. Both callers
# pair it with a scratch working directory, so what gets trusted is a temp dir
# rather than the user's project.
GEMINI_PROMPT_TAIL = "Follow the instructions above."


def gemini_cli_argv(bin_path, model=None, stream_json=False, auto_approve=True):
    """argv for a headless Gemini CLI run. The PROMPT goes on stdin (above).

    ``auto_approve`` (``-y``) lets the agent run its own tools without a prompt
    it could never answer headlessly. The porter leaves it OFF -- it wants text
    back and nothing else, matching the tool deny-list it hands the Claude CLI.
    """
    cmd = [str(bin_path), "-p", GEMINI_PROMPT_TAIL]
    if stream_json:
        cmd += ["-o", "stream-json"]
    if auto_approve:
        cmd += ["-y"]
    cmd += ["--skip-trust"]
    if model:
        cmd += ["-m", str(model)]
    return cmd


# CLI providers that can answer "which models will you run?" LOCALLY, with no
# API key: `claude` is asked directly, and the Gemini CLI's own model table is
# read out of the installed bundle. Demanding the matching HTTP key instead was
# wrong twice over -- it is a different backend, and a CLI provider exists
# precisely so the user does not need a key.
SELF_LISTING_CLI_PROVIDERS = ("claude_cli", "gemini_cli")

# The Claude CLI list is NOT derived from the Anthropic HTTP API -- different
# backends, and a gateway build rejects ids /v1/models returns. It is asked of
# the CLI in claude_cli_client.list_models(); nothing here synthesises ids.


def get_cached_models(provider: str) -> list:
    """The last model list successfully fetched for ``provider`` ([] if never)."""
    val = _pref("assistant_models_%s" % provider, None)
    if isinstance(val, (list, tuple)):
        return [str(x) for x in val if x]
    return []


def set_cached_models(provider: str, models) -> None:
    """Persist a successful fetch so the dropdown survives a restart / offline."""
    _set_pref("assistant_models_%s" % provider, [str(m) for m in (models or [])])


# The Claude CLI dropdown's full rows (display names, alias chips, greyed
# "needs update" entries) as claude_cli_client.build_rows returns them, stamped
# with the CLI version they were checked against and when. The flat
# ``assistant_models_<provider>`` list above is still written beside it: an
# older MPyNode sharing this preferences file reads only that one.
ROWS_MAX_AGE = 7 * 24 * 3600


def get_cached_rows(provider: str) -> dict:
    """The last validated row payload for ``provider`` ({} if never)."""
    val = _pref("assistant_model_rows_%s" % provider, None)
    if isinstance(val, dict) and isinstance(val.get("rows"), list):
        return dict(val)
    return {}


def set_cached_rows(provider: str, payload) -> None:
    _set_pref("assistant_model_rows_%s" % provider, dict(payload or {}))


def rows_need_full_check(cached, cli_version, now=None, max_age=ROWS_MAX_AGE) -> bool:
    """True when saved rows must be re-validated against the CLI. Pure.

    Validation is the slow, login-backed step (25-40 s), so it runs only when its
    answer can have changed: never checked, the last check did not finish,
    the CLI version moved (a new CLI runs models the old one refused), or the
    check is older than ``max_age`` (the server can grant or withdraw access).
    Anything unreadable counts as stale.
    """
    if (not cached or not cached.get("rows") or cached.get("fallback")
            or cached.get("partial")):
        return True
    if not cli_version or cached.get("cli_version") != cli_version:
        return True
    try:
        fetched = float(cached.get("fetched") or 0)
    except (TypeError, ValueError):
        return True
    now = time.time() if now is None else now
    return not (0 < fetched <= now + 60) or now - fetched > max_age


def cli_model_candidates(provider: str) -> list:
    """Model ids to OFFER for a CLI provider that has no list endpoint.

    Returns the LAST SUCCESSFUL fetch (persisted in prefs), so the dropdown keeps
    working with no key and offline -- and ``[]`` on a machine that has never
    fetched one. This is deliberately NOT a hardcoded roster: a baked-in list
    silently goes stale every time a model family ships (it stranded users on
    4.8 after Opus 5 shipped). The panel surfaces the empty case with guidance,
    and the combo is editable, so a model id can always be typed.

    Served for the CLI providers that list themselves (see
    SELF_LISTING_CLI_PROVIDERS); codex_cli still fetches via its source
    provider's key, and API providers use their own list endpoints.
    """
    if provider in SELF_LISTING_CLI_PROVIDERS:
        return get_cached_models(provider)
    return []


def model_selection_after_fetch(provider: str, current: str, models) -> str:
    """Which model id the dropdown should show after a list refresh.

    Preserve the user's current choice. When it's blank, API providers surface
    the first concrete id (cosmetic -- their blank already maps to a real
    ``DEFAULT_MODELS`` entry), but CLI providers KEEP blank: for them blank means
    "use the CLI's own default", so showing ``models[0]`` would display one
    version while the CLI runs whatever its default is.
    """
    if current:
        return current
    if provider in CLI_PROVIDERS:
        return ""
    return models[0] if models else ""

# Reasoning / thinking effort. "off" = no extended thinking.
EFFORT_LEVELS = ("off", "low", "medium", "high")  # API providers (budget presets)
# Claude CLI exposes its own richer --effort enum (off = omit the flag). These
# MUST match exactly what `claude --effort` accepts; an unknown value makes the
# CLI exit 1 ("Unknown --effort value …"), which aborts the native porter.
EFFORT_LEVELS_CLI = ("off", "low", "medium", "high", "xhigh", "max")
# Effort prefs that were never valid `claude --effort` members (`ultracode` is a
# Claude Code *session* keyword, not an effort tier; `auto` was never a CLI
# value). Migrated to the closest real value so the CLI can't reject it.
_EFFORT_ALIASES = {"ultracode": "max", "auto": "off"}
# Thinking-token budgets for the API providers (Claude CLI uses --effort names).
EFFORT_BUDGETS = {"low": 2048, "medium": 8192, "high": 16384}


def effort_levels(provider: str) -> tuple:
    """The effort choices valid for a provider."""
    if provider == "claude_cli":
        return EFFORT_LEVELS_CLI            # rich --effort enum
    if provider == "gemini_cli":
        return ("off",)                     # Gemini CLI has no effort flag
    return EFFORT_LEVELS                     # APIs + codex_cli (reasoning_effort)


def get_effort(provider: str) -> str:
    lv = (_pref("assistant_effort_%s" % provider, "off") or "off").strip().lower()
    lv = _EFFORT_ALIASES.get(lv, lv)        # migrate legacy/invalid prefs
    return lv if lv in effort_levels(provider) else "off"


def set_effort(provider: str, level: str) -> None:
    level = (level or "off").strip().lower()
    if level in effort_levels(provider):
        _set_pref("assistant_effort_%s" % provider, level)


def effort_budget(level: str) -> int:
    """Thinking-token budget for an effort level (0 = off/unknown)."""
    return EFFORT_BUDGETS.get((level or "").lower(), 0)


class CancelledError(Exception):
    """Raised inside ``request_with_retry`` when the caller asks to stop."""


# --- local request-rate meter (Google exposes no live-quota endpoint) ------
_REQ_TIMES = collections.deque(maxlen=512)


def record_request():
    """Note that an API request was just sent (for the local RPM meter)."""
    _REQ_TIMES.append(time.time())


def requests_in_last(window=60.0):
    """How many API requests we've sent in the last `window` seconds."""
    cutoff = time.time() - window
    while _REQ_TIMES and _REQ_TIMES[0] < cutoff:
        _REQ_TIMES.popleft()
    return len(_REQ_TIMES)


def _quota_detail(body):
    """Pull a short 'limit N/min' string out of a 429 body, or '' if unknown."""
    import re

    try:
        data = __import__("json").loads(body or "{}")
        err  = data.get("error", {}) if isinstance(data, dict) else {}
        msg  = err.get("message", "") if isinstance(err, dict) else ""
        for d in (err.get("details") or []):
            if "QuotaFailure" in str(d.get("@type", "")):
                for v in (d.get("violations") or []):
                    metric = str(v.get("quotaMetric", "") or v.get("quotaId", ""))
                    val    = v.get("quotaValue")
                    per_min = any(k in metric for k in
                                 ("PerMinute", "per_minute", "free_tier_requests"))
                    if val:
                        return "limit %s%s" % (val, "/min" if per_min else "")
        m = re.search(r"limit:\s*(\d+)", msg)
        if m:
            per_min = "free_tier_requests" in msg or "PerMinute" in msg
            return "limit %s%s" % (m.group(1), "/min" if per_min else "")
    except Exception:
        pass
    return ""


# HTTP status codes worth retrying: rate-limit + transient server / overload.
_RETRYABLE = {429, 500, 502, 503, 529}


def _parse_seconds(val):
    """Parse '4.39s' / '4.39' / an http-date-less number into float seconds."""
    if val is None:
        return None
    try:
        s = str(val).strip()
        if s.endswith("s"):
            s = s[:-1]
        return float(s)
    except Exception:
        return None


def _retry_after_seconds(exc, body, attempt):
    """How long to wait before retry: server hint if any, else backoff."""
    hdrs = getattr(exc, "headers", None)
    if hdrs is not None:
        sec = _parse_seconds(hdrs.get("Retry-After"))
        if sec is not None:
            return min(sec + 0.5, 60.0)
    # Gemini puts a RetryInfo.retryDelay in error.details.
    try:
        import json

        data = json.loads(body or "{}")
        for d in (data.get("error", {}).get("details") or []):
            if "RetryInfo" in str(d.get("@type", "")):
                sec = _parse_seconds(d.get("retryDelay"))
                if sec is not None:
                    return min(sec + 0.5, 60.0)
    except Exception:
        pass
    import random

    return min((2.0 ** attempt) + random.uniform(0.0, 0.5), 30.0)


def request_with_retry(do_request, on_retry=None, max_retries=5, should_cancel=None):
    """Run ``do_request()`` (one HTTPS call returning a dict), auto-retrying
    transient failures (429 rate-limit, 5xx) with the server's suggested delay
    or exponential backoff.

    Runs on the client's worker thread, so the ``time.sleep`` never blocks
    Maya. ``on_retry(code, delay, attempt, max_retries)`` is called before each
    wait so the UI can show a notice. ``should_cancel()`` (if given) is polled
    frequently -- including DURING the backoff sleep, so an interrupt takes
    effect even mid rate-limit wait -- and raises ``CancelledError`` when True.
    On give-up (non-retryable, or retries exhausted) raises ``RuntimeError``
    with the HTTP code + body snippet.
    """
    import time
    import urllib.error

    def _cancelled():
        return bool(should_cancel and should_cancel())

    attempt = 0
    while True:
        if _cancelled():
            raise CancelledError()
        try:
            record_request()  # local RPM meter
            return do_request()
        except urllib.error.HTTPError as exc:
            code = getattr(exc, "code", 0)
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            if code not in _RETRYABLE or attempt >= max_retries:
                raise RuntimeError("HTTP %s: %s" % (code, body[:500]))
            delay  = _retry_after_seconds(exc, body, attempt)
            detail = _quota_detail(body) if code == 429 else ""
            attempt += 1
            if callable(on_retry):
                try:
                    on_retry(code, delay, attempt, max_retries, detail)
                except Exception:
                    pass
            slept = 0.0
            while slept < delay:
                if _cancelled():
                    raise CancelledError()
                step = min(0.2, delay - slept)
                time.sleep(step)
                slept += step


_SSL_CTX = None


def ssl_context() -> "ssl.SSLContext":
    """A verified TLS context for the assistant's HTTPS calls.

    Maya's bundled OpenSSL points its default CA path at a Python.org location
    that doesn't exist inside Maya, so ``ssl.create_default_context()`` finds
    no root certs and every request fails with CERTIFICATE_VERIFY_FAILED. We
    prefer the ``certifi`` CA bundle that ships with Maya; if it's missing we
    honour the ``SSL_CERT_FILE`` env var, then fall back to the OS default.
    Built once and cached.
    """
    global _SSL_CTX
    if _SSL_CTX is not None:
        return _SSL_CTX
    cafile = None
    try:
        import certifi

        cafile = certifi.where()
    except Exception:
        cafile = os.environ.get("SSL_CERT_FILE") or None
    try:
        _SSL_CTX = ssl.create_default_context(cafile=cafile)
    except Exception:
        _SSL_CTX = ssl.create_default_context()
    return _SSL_CTX


def _pref(key, default=None):
    try:
        from mpynode.ui import preferences

        return preferences.get_pref(key, default)
    except Exception:
        return default


def _set_pref(key, value):
    try:
        from mpynode.ui import preferences

        preferences.set_pref(key, value)
    except Exception:
        pass


def get_provider() -> str:
    p = (_pref("assistant_provider", DEFAULT_PROVIDER) or DEFAULT_PROVIDER).strip()
    return p if p in PROVIDERS else DEFAULT_PROVIDER


def set_provider(provider: str) -> None:
    if provider in PROVIDERS:
        _set_pref("assistant_provider", provider)


def get_api_key(provider: str) -> str:
    key = (_pref("assistant_api_key_%s" % provider, "") or "").strip()
    if key:
        return key
    for env in _ENV_KEYS.get(provider, ()):
        val = (os.environ.get(env, "") or "").strip()
        if val:
            return val
    return ""


def set_api_key(provider: str, key: str) -> None:
    _set_pref("assistant_api_key_%s" % provider, (key or "").strip())


# A floating alias ("opus", "opus[1m]") saved back when the dropdown offered
# them must not survive: it hides WHICH model runs and re-points every release.
# Blank is the honest fallback. Filtered HERE, the one chokepoint every reader
# goes through, so the box and the --model flag can never disagree.
_EXPLICIT_CLI_ID = re.compile(r"^claude-[a-z]+-[0-9][A-Za-z0-9.\-]*(\[1m\])?$")


def is_explicit_cli_id(model) -> bool:
    """True for a pinned Claude id (``claude-opus-5``, ``claude-opus-5[1m]``)."""
    return bool(_EXPLICIT_CLI_ID.match((model or "").strip()))


def get_model(provider: str) -> str:
    m = saved_model(provider)
    if provider == "claude_cli" and m and not is_explicit_cli_id(m):
        return ""
    return m or DEFAULT_MODELS.get(provider, "")


def saved_model(provider: str) -> str:
    """The stored model string as typed -- unlike ``get_model``, NOT filtered."""
    return (_pref("assistant_model_%s" % provider, "") or "").strip()


def set_model(provider: str, model: str) -> None:
    _set_pref("assistant_model_%s" % provider, (model or "").strip())


def migrate_saved_alias(provider: str, alias_map):
    """Pin a saved Claude CLI alias to the id it names today: ``(old, new)``, or None.

    The dropdown once offered aliases, and ``get_model`` has always dropped
    them, so a saved "opus[1m]" was never sent: every turn ran Claude Code's
    default. Rather than keep a value that does nothing, it is pinned to the
    model it names on THIS machine -- ``alias_map`` is resolved live by the
    caller, never hardcoded. Anything else non-explicit becomes blank, which is
    what already ran.
    """
    if provider != "claude_cli":
        return None
    old = saved_model(provider)
    if not old or is_explicit_cli_id(old):
        return None
    new = (alias_map or {}).get(old, "")
    set_model(provider, new)
    return old, new
