"""Provider transport for the AI porter -- HTTP + local-CLI completions.

Qt-free one-shot text completion (no tools): HTTP for API providers
(anthropic / gemini) and subprocess for local CLI providers
(claude_cli / gemini_cli / codex_cli), plus a cancel-aware killable variant.
Reuses ``ui.llm.config`` for provider / key / model / TLS / retry.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

from mpynode.native.toolchain import toolchain
from mpynode.ui.llm import config as _config

_MAX_TOKENS = 4096

# Grace period (seconds) between proc.terminate() and proc.kill() when a port
# is cancelled mid-flight -- give the CLI a moment to exit cleanly, then SIGKILL.
_CANCEL_GRACE = 2.0

# Wall-clock budget (seconds) for a SINGLE one-shot CLI completion (the initial
# port and each fix-loop round). At ``--effort max`` the largest computes can take
# >10 min just to emit, so a too-small ceiling drops otherwise-portable nodes.
# Override with ``MPYNODE_PORT_TIMEOUT``; the default stays at the historical 600.
def _cli_timeout() -> float:
    try:
        return float(os.environ.get("MPYNODE_PORT_TIMEOUT", "600"))
    except (TypeError, ValueError):
        return 600.0


# Typographic Unicode the model sometimes emits into C++ (em/en dashes, a real
# MINUS SIGN in arithmetic, arrows, smart quotes, ellipsis, NBSP). clang cannot
# lex these outside a string literal, so they are hard errors the bounded fix loop
# struggles to scrub. ONLY this fixed set is transliterated to ASCII; every other
# non-ASCII byte is left untouched, so real strings are never corrupted.
_TYPO_ASCII = {
    "—": "-",    # — em dash
    "–": "-",    # – en dash
    "−": "-",    # − minus sign
    "→": "->",   # → rightwards arrow
    "“": '"',    # “ left double quote
    "”": '"',    # ” right double quote
    "‘": "'",    # ‘ left single quote
    "’": "'",    # ’ right single quote
    "…": "...",  # … horizontal ellipsis
    " ": " ",    # non-breaking space
    "‑": "-",    # ‑ non-breaking hyphen
    "⁄": "/",    # ⁄ fraction slash
    "×": "*",    # × multiplication sign
}


def _ascii_typography(text: str) -> str:
    """Force the completion to 7-bit ASCII.

    A no-op for pure-ASCII output (fast path). Otherwise: first transliterate the
    known typographic offenders in ``_TYPO_ASCII`` to their sensible ASCII
    equivalent (em-dash -> '-', unicode minus -> '-', etc.), then HARD-DROP any
    non-ASCII that survives (stray emoji like U+2713, other symbols the model
    slips into comments/prose). clang cannot lex non-ASCII outside a string
    literal and generated compute C++ never legitimately needs it, so this is the
    guaranteed-ASCII backstop the system prompt's ASCII rule only asks for. (A
    non-ASCII char inside a genuine string literal would be dropped too -- an
    accepted trade per the "emit nothing but valid ASCII" directive.)
    """
    if text is None or text.isascii():
        return text
    for bad, good in _TYPO_ASCII.items():
        if bad in text:
            text = text.replace(bad, good)
    if not text.isascii():
        text = text.encode("ascii", "ignore").decode("ascii")
    return text


class PortCancelled(Exception):
    """Raised by a cancel-aware ``complete_fn`` when its ``cancel_event`` fires.

    The CLI subprocess is terminated (then killed after a short grace) before
    this propagates, so an in-flight port can be abandoned mid-run. Qt-free:
    the controller wires a ``threading.Event`` in; this module never imports Qt.
    """


class AgentUnavailable(RuntimeError):
    """The tool-using agent could not START -- NO work was attempted.

    Distinct from a generic failure mid-run (where the agent may already have
    edited and measured real files, which callers keep). A caller that sees this
    knows the round produced literally nothing, so it can report "the AI never
    ran" instead of silently gating the unchanged source and calling the
    resulting benchmark noise a speedup. Subclasses ``RuntimeError`` so every
    existing ``except Exception`` / ``except RuntimeError`` path is unchanged.
    """


# ---------------------------------------------------------------------------
# LLM one-shot completion (Qt-free, no tools)
# ---------------------------------------------------------------------------


def _http_json(url, payload, headers, timeout=120.0, cancel_event=None):
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)

    def _once():
        with urllib.request.urlopen(req, timeout=timeout, context=_config.ssl_context()) as r:
            return json.loads(r.read().decode("utf-8"))

    # ``request_with_retry`` polls ``should_cancel`` before every attempt AND every
    # 0.2s of a 429/5xx backoff -- the hook was simply never passed, so Cancel
    # could not interrupt a rate-limit wait. A response already being READ is still
    # not interruptible (that needs SSE). ``cancel_event=None`` (the porter and OSL
    # converter, which bind ``_complete`` bare) keeps should_cancel None.
    try:
        return _config.request_with_retry(
            _once, should_cancel=(None if cancel_event is None
                                  else cancel_event.is_set))
    except _config.CancelledError:
        raise PortCancelled()


# Built-in Claude Code tools to deny so the porter stays a pure text
# completion (no codebase spelunking / shell). MCP is NOT configured here.
_CLI_DENY = ("Bash,Read,Edit,Write,Glob,Grep,WebFetch,WebSearch,Task,"
             "TodoWrite,NotebookEdit,ToolSearch,Skill,AskUserQuestion")

# Permission posture for EVERY claude_cli launch -- the porter's one-shot
# completion and the tool-using optimizer agent alike. Said once so the two
# cannot drift: the porter left it unstated and inherited whatever default the
# installed CLI happened to have, which is not something a compile should
# depend on. The porter denies every editing tool anyway, so this changes
# nothing it can do -- it only stops the default from being the CLI's to pick.
_CLI_PERMISSION_MODE = "acceptEdits"

_CLI_BINS = {
    "claude_cli": ("CLAUDE_BIN", "claude"),
    "gemini_cli": ("GEMINI_BIN", "gemini"),
    "codex_cli":  ("CODEX_BIN", "codex"),
}

# ---------------------------------------------------------------------------
# Porter "ultracode" (multi-agent) posture
# ---------------------------------------------------------------------------
# The compile porter emits C++ ONLY and has NO mpynode MCP tools wired, so
# "ultracode" here buys max-reasoning + optional Task decomposition of a hard
# self-contained math port, with a directive that the FINAL message is the C++
# body and nothing else. The literal 'ultracode' keyword (a Claude Code session
# keyword) goes in the prompt BODY, behaviour rides --append-system-prompt, and
# Task + ToolSearch are the only built-ins un-denied. Experimental and env-gated
# (see _porter_orchestrate); the interactive assistant has no multi-agent mode.
_PORT_ULTRACODE_PREFIX = "ultracode\n\nTASK:\n"
_PORT_ORCHESTRATE_KEEP = ("Task", "ToolSearch")
_PORT_ORCHESTRATE_DIRECTIVE = (
    "You are porting ONE Maya node's Python compute into C++. This is a hard, "
    "self-contained math task -- you MAY use the Task tool to reason about "
    "independent parts in parallel, but you have NO file, shell, scene, or MCP "
    "access. Your FINAL message MUST be ONLY the C++ statements that go between "
    "the PORT markers: no prose, no explanation, no markdown fences, not even a "
    "leading or trailing sentence. Put ALL reasoning in your thinking, never in "
    "the answer. Emit strictly 7-bit ASCII in code AND comments."
)


def _port_orchestrate_disallowed() -> str:
    """The porter deny list with Task + ToolSearch REMOVED (multi-agent mode).

    Every other built-in in ``_CLI_DENY`` stays denied, so un-denying Task can
    never also open Bash/Read/Write/etc -- the porter stays a pure text task with
    no codebase/scene access."""
    out = []
    for t in _CLI_DENY.split(","):
        t = t.strip()
        if t and t not in _PORT_ORCHESTRATE_KEEP and t not in out:
            out.append(t)
    return ",".join(out)


def _porter_orchestrate() -> bool:
    """Should the porter run in "ultracode" multi-agent mode? (claude_cli only.)

    Controlled EXPLICITLY by the ``MPYNODE_PORT_ULTRACODE`` env var (default OFF);
    there is no preference or UI for it. A 2026-07-16 e2e showed the Task fan-out
    at effort=max is impractically slow for a hard port (procrustes_single TIMED
    OUT at the 1800s ceiling in ONE round -- a net regression vs the
    non-orchestrate path, which completes its fix rounds); that measurement is
    also why the interactive assistant's multi-agent toggle was removed
    (2026-09). The always-on wins (stream-json CoT capture + effort + the prose
    guard) apply regardless of this flag; orchestrate is the experimental,
    opt-in extra. Never raises."""
    env = os.environ.get("MPYNODE_PORT_ULTRACODE", "")
    return env.strip().lower() not in ("", "0", "false", "no", "off")


def _build_cli(provider, binp, model, effort, prompt,
               orchestrate=False, stream_json=False):
    """Return (argv, stdin_text) for a one-shot CLI completion.

    ``stdin_text`` is None when the prompt is passed in argv. Claude takes the
    (potentially large) prompt on stdin to dodge argv size limits.
    ``stream_json`` switches Claude to ``--output-format stream-json --verbose``
    (JSONL: thinking + tool-use + text events, parsed by ``_extract_cli_output``)
    so the porter's chain-of-thought can be captured to the durable compile log.
    ``orchestrate`` prefixes the 'ultracode' keyword, un-denies Task + ToolSearch,
    and appends the porter orchestration directive (multi-agent mode).
    """
    if provider == "claude_cli":
        fmt = (["--output-format", "stream-json", "--verbose"] if stream_json
               else ["--output-format", "text"])
        deny = _port_orchestrate_disallowed() if orchestrate else _CLI_DENY
        # --strict-mcp-config makes the CLI use ONLY the servers passed via
        # --mcp-config; we pass NONE, so it loads ZERO. Without it the CLI
        # auto-loads the user's MCP config and the agent can spend minutes calling
        # mcp__..._search_files, which --disallowedTools (built-ins only) cannot
        # deny -- the flail that produced no OSL and a log full of tool calls.
        cmd = [binp, "-p"] + fmt + ["--disallowedTools", deny,
                                    "--permission-mode", _CLI_PERMISSION_MODE,
                                    "--strict-mcp-config"]
        if orchestrate:
            cmd += ["--append-system-prompt", _PORT_ORCHESTRATE_DIRECTIVE]
            prompt = _PORT_ULTRACODE_PREFIX + prompt
        if model:
            cmd += ["--model", model]
        if effort and effort != "off":
            cmd += ["--effort", effort]
        return cmd, prompt
    if provider == "gemini_cli":
        cmd = [binp, "-p", prompt]
        if model:
            cmd += ["-m", model]
        return cmd, None
    # codex_cli (best-effort; output may carry banner noise)
    cmd = [binp, "exec", "--skip-git-repo-check"]
    if model:
        cmd += ["-m", model]
    cmd += [prompt]
    return cmd, None


# How the Claude CLI is told a response ceiling. There is no flag for it, and it
# is a Claude Code concept, so no other provider gets it.
_CLAUDE_MAX_OUTPUT_ENV = "CLAUDE_CODE_MAX_OUTPUT_TOKENS"


def _cli_env(provider, max_tokens):
    """The child's environment, or None to INHERIT (the shipped behaviour).

    The optimizer's one-shot fallback asks for a WHOLE translation unit back in
    one reply and passes the configured ceiling as ``max_tokens``. That reached
    the anthropic/gemini payloads and was dropped for CLI providers, so the CLI's
    own default decided instead -- measured on the 2026-08-13 arm-1 run, eight
    rounds across four nodes all stopped between ~29k and ~38k estimated output
    tokens while the files they were asked to re-emit needed 49k-131k, and every
    one was rejected as truncated. The stop point tracked the ceiling, not the
    input, which is what makes it the ceiling and not a timeout (the budget was
    2400 s; the longest round was 1781.7 s).

    Returns None whenever the caller named no ceiling -- the porter and the OSL
    converter bind this with ``max_tokens=None``, so their child is spawned with
    exactly the environment it was spawned with before.
    """
    if provider != "claude_cli" or not max_tokens:
        return None
    env                         = dict(os.environ)
    env[_CLAUDE_MAX_OUTPUT_ENV] = str(int(max_tokens))
    return env


def _resolve_cli_bin(provider: str) -> str:
    """Resolve a CLI provider's binary (env override -> PATH). Raises if absent.

    Factored out of ``_complete_cli`` so the cancel-aware factory resolves the
    binary identically.
    """
    env, default = _CLI_BINS[provider]
    binp = os.environ.get(env, default)
    if os.path.isabs(binp):
        return binp
    # Resolve to a full path so Windows can exec a .cmd/.exe shim (CreateProcess
    # can't launch a bare .cmd name); also the existence check. find_executable
    # adds common off-PATH install dirs, so a dock-launched Maya (minimal launchd
    # PATH) still finds a `claude` that works in a terminal.
    resolved = toolchain.find_executable(binp)
    if resolved is None:
        raise RuntimeError("%r CLI not found on PATH (set %s)" % (binp, env))
    return resolved


def _tool_input_summary(inp) -> str:
    """A compact ``" {...}"`` suffix describing a tool call's input for the log
    (e.g. the search query / file path), or ``""`` when there's nothing useful.
    Bounded so a huge input can't flood the activity strip."""
    if not isinstance(inp, dict) or not inp:
        return ""
    try:
        s = json.dumps(inp, ensure_ascii=False, sort_keys=True)
    except Exception:
        return ""
    return " " + (s if len(s) <= 200 else s[:197] + "...")


def _parse_stream_json(text: str, log_cb=None):
    """Parse a Claude ``--output-format stream-json`` transcript.

    Returns the model's FINAL answer text (top-level ``assistant`` text blocks,
    or the aggregated ``result`` as fallback), or ``None`` if ``text`` is not a
    stream-json transcript (first non-empty line is not a JSON object with a
    ``type`` -- e.g. plain ``--output-format text`` output). Mirrors the event
    handling in ``ui.llm.claude_cli_client._handle_event``: reasoning
    (``thinking``), tool use, and sub-agent activity are streamed to ``log_cb``
    (the durable compile log) but NEVER folded into the returned answer.
    """
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        first = json.loads(lines[0])
    except Exception:
        return None
    if not (isinstance(first, dict) and "type" in first):
        return None  # not stream-json; caller keeps the raw text

    def _log(msg):
        if log_cb is not None and msg:
            try:
                log_cb(msg)
            except Exception:
                pass

    answer_parts    = []
    result_fallback = None
    for ln in lines:
        try:
            ev = json.loads(ln)
        except Exception:
            continue
        et = ev.get("type")
        if et == "assistant":
            is_sub = ev.get("parent_tool_use_id") is not None
            for b in ((ev.get("message", {}) or {}).get("content") or []):
                bt = b.get("type")
                if bt == "text" and b.get("text"):
                    if is_sub:
                        _log("[sub-agent text] " + b["text"][:400])
                    else:
                        answer_parts.append(b["text"])
                        # ALSO tee the top-level answer to the log so the strip
                        # shows the C++ as it arrives; teeing a copy never
                        # changes the returned answer (answer_parts above).
                        _log("[answer] " + b["text"][:2000])
                elif bt == "thinking":
                    th = b.get("thinking") or b.get("text")
                    if th:
                        _log(("[thinking] " if not is_sub
                              else "[sub-agent thinking] ") + th)
                elif bt == "tool_use":
                    nm = (b.get("name") or "tool").split("__")[-1]
                    _log(("[tool] " if not is_sub else "[sub-agent tool] ")
                         + nm + _tool_input_summary(b.get("input")))
        elif et == "system":
            sub = ev.get("subtype")
            if sub == "task_started":
                _log("[sub-agent started] %s" % (ev.get("description") or "task"))
            elif sub == "task_notification" and ev.get("status") == "completed":
                _log("[sub-agent done] %s" % (ev.get("summary") or "done"))
        elif et == "result":
            r = ev.get("result")
            if isinstance(r, str) and r.strip():
                result_fallback = r
    if answer_parts:
        return "".join(answer_parts)
    return result_fallback


def _extract_cli_output(binp: str, stdout: str, stderr: str, returncode,
                        log_cb=None) -> str:
    """Turn a finished CLI run into its text output (or raise).

    Handles both ``--output-format text`` (returned verbatim) and Claude's
    ``--output-format stream-json`` (auto-detected and parsed to the final answer
    via ``_parse_stream_json``, streaming any chain-of-thought / tool activity to
    ``log_cb``). Nonzero-exit and empty-output handling is unchanged so both the
    blocking and the killable paths report identical errors.
    """
    out = (stdout or "").strip()
    if returncode not in (0, None):
        raise RuntimeError("%s exited %s: %s"
                           % (binp, returncode, (stderr or "")[:600]))
    if not out:
        tail = (": " + (stderr or "")[:300]) if stderr else ""
        raise RuntimeError("%s produced no output%s" % (binp, tail))
    parsed = _parse_stream_json(out, log_cb=log_cb)
    if parsed is not None:
        out = parsed.strip()
        if not out:
            raise RuntimeError("%s produced no assistant text (stream-json)"
                               % binp)
    return _ascii_typography(out)


def _run_cli_proc(cmd, stdin_text, binp, cancel_event=None, log_cb=None,
                  timeout=None, cwd=None, env=None) -> str:
    """Run a one-shot CLI ``cmd`` and return its extracted text output.

    The killable core shared by ``_complete_cli`` (cancel_event=None) and
    ``make_cli_complete_fn``'s closure.

    * ``cancel_event is None`` -> byte-identical to the original blocking path:
      ``subprocess.run(cmd, input=stdin_text, capture_output=True, text=True,
      timeout=600)`` then the shared extraction.
    * ``cancel_event`` given -> ``subprocess.Popen`` (same captured pipes) with a
      daemon ``communicate`` pump draining both pipes CONCURRENTLY (so a child
      that writes >64KB can't deadlock on a full pipe), while we poll the event
      ~every 0.1s; on set, ``terminate()`` then ``kill()`` after a short grace
      and raise ``PortCancelled``. The 600s timeout is enforced by that poll.

    ``env`` (default None) is the child's environment; None means INHERIT, which
    is what every caller but the optimizer wants.

    Patterned on ``ui/llm/claude_cli_client._run`` (Popen + ``_cancel`` Event +
    ``proc.terminate()``); kept Qt-free.
    """
    if cancel_event is None:
        _tmo = timeout if timeout is not None else _cli_timeout()
        # timeout=inf (the optimize-timeout preference turned OFF) => unbounded:
        # subprocess.run(timeout=None) blocks until the child exits. None keeps
        # the shipped default (_cli_timeout, 600s) so the porter is unchanged.
        proc = subprocess.run(cmd, input=stdin_text, capture_output=True,
                              timeout=(None if _tmo == float("inf") else _tmo),
                              cwd=cwd, env=env,
                              **toolchain.cli_subprocess_kwargs())
        return _extract_cli_output(binp, proc.stdout, proc.stderr,
                                   proc.returncode, log_cb=log_cb)

    # Cancel-aware path: Popen + a pump thread that drains stdout/stderr
    # CONCURRENTLY while the main thread polls for cancellation. Concurrent
    # draining is mandatory: a real CLI port emits well over the ~64KB OS pipe
    # buffer, so a poll loop that never reads the pipes would fill it and BLOCK the
    # child forever. ``communicate`` does the same concurrent feed + drain as
    # ``subprocess.run``; running it in a daemon thread keeps cancel + timeout
    # responsive (poll ~every 0.1s; terminate()/kill() unblocks the pump).
    proc = subprocess.Popen(
        cmd,
        stdin=(subprocess.PIPE if stdin_text is not None else None),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env,
        **toolchain.cli_subprocess_kwargs())
    pump = {}

    def _pump():
        # communicate() feeds stdin and drains BOTH pipes concurrently, so the
        # child can never block on a full pipe. Stash the result for the caller.
        try:
            pump["out"], pump["err"] = proc.communicate(input=stdin_text)
            pump["rc"] = proc.returncode
        except Exception as exc:  # pragma: no cover - defensive
            pump["exc"] = exc

    worker = threading.Thread(target=_pump, daemon=True)
    worker.start()
    _tmo = timeout if timeout is not None else _cli_timeout()
    # timeout=inf (the optimize-timeout preference turned OFF) => no wall-clock
    # kill; only cancel_event stops the call. None keeps the shipped 600s cap so
    # the porter path is unchanged.
    deadline = None if _tmo == float("inf") else time.time() + _tmo
    try:
        # Poll cancel / timeout ~every 0.1s while the pump keeps the pipes drained.
        while worker.is_alive():
            if cancel_event.is_set():
                _terminate_proc(proc)  # unblocks communicate() in the pump
                raise PortCancelled()
            if deadline is not None and time.time() >= deadline:
                _terminate_proc(proc)
                raise subprocess.TimeoutExpired(cmd, _tmo)
            worker.join(0.1)
        # Pump finished on its own -- but a cancel may have raced in just now.
        if cancel_event.is_set():
            _terminate_proc(proc)
            raise PortCancelled()
        if "exc" in pump:
            raise pump["exc"]
    finally:
        # Never leak the child or the pump thread.
        if proc.poll() is None:
            _terminate_proc(proc)
        worker.join(_CANCEL_GRACE)
    return _extract_cli_output(binp, pump.get("out"), pump.get("err"),
                               pump.get("rc"), log_cb=log_cb)


def _terminate_proc(proc) -> None:
    """terminate() a CLI subprocess, then kill() it after a short grace."""
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=_CANCEL_GRACE)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=_CANCEL_GRACE)
        except Exception:
            pass


def _complete_cli(provider: str, model: str, system: str, user: str,
                  log_cb=None) -> str:
    """One-shot text completion via a local CLI (no API key, no MCP).

    For claude_cli this streams ``--output-format stream-json`` so the porter's
    chain-of-thought / tool activity is teed to ``log_cb`` (the durable compile
    log) while only the final answer is returned; multi-agent "ultracode" mode is
    enabled when ``_porter_orchestrate()`` says so.
    """
    binp   = _resolve_cli_bin(provider)
    prompt = system + "\n\n" + user
    cmd, stdin_text = _build_cli(
        provider, binp, model, _config.get_effort(provider), prompt,
        orchestrate=(provider == "claude_cli" and _porter_orchestrate()),
        stream_json=(provider == "claude_cli"))
    return _run_cli_proc(cmd, stdin_text, binp, cancel_event=None, log_cb=log_cb)


def _complete(system: str, user: str, max_tokens=None, timeout=None,
              cancel_event=None) -> str:
    """One-shot completion. ``max_tokens`` / ``timeout`` override the shipped
    defaults for THIS call only.

    Both default to None so the porter and the OSL converter, which bind this
    as a bare two-argument ``complete_fn``, are byte-for-byte unchanged. Only
    the optimizer overrides them: it has to get a whole translation unit back,
    which neither 4096 tokens nor a 120s read can deliver.

    ``cancel_event`` (also None by default) reaches the API path's retry loop, so
    Cancel interrupts a 429/5xx backoff instead of waiting it out. It does not
    reach the CLI branch: a CLI provider never gets here from the cancel-aware
    ``make_cli_complete_fn``, which runs the killable ``_run_cli_proc`` itself.
    """
    provider = _config.get_provider()
    model    = _config.get_model(provider)
    if provider in _config.CLI_PROVIDERS:
        return _complete_cli(provider, model, system, user)
    key = _config.get_api_key(provider)
    if not key:
        raise RuntimeError("no API key for provider %r" % provider)
    # openai is offered in the panel but has no request shape here. Falling
    # through sent an OpenAI key to api.anthropic.com in an anthropic payload,
    # so refuse by name instead of leaking the credential.
    if provider == "openai":
        raise RuntimeError(
            "provider 'openai' is not supported for compiling; use anthropic, "
            "gemini, or a CLI provider")

    cap = max_tokens or _MAX_TOKENS
    # Two different "no timeout" meanings, so pass the argument only when the
    # caller actually set one: timeout=None means UNSPECIFIED (keep _http_json's
    # shipped 120s), while timeout=inf -- the optimize-timeout preference turned
    # OFF -- means UNBOUNDED and maps to urlopen(timeout=None). inf itself
    # cannot be passed: socket.settimeout(inf) raises OverflowError.
    tmo = {} if timeout is None else {
        "timeout": (None if timeout == float("inf") else timeout)}
    if provider == "gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents":          [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig":  {"maxOutputTokens": cap},
        }
        resp = _http_json(url, payload, {"content-type": "application/json",
                                         "x-goog-api-key": key},
                          cancel_event=cancel_event, **tmo)
        parts = (resp.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
        return _ascii_typography("".join(p.get("text", "") for p in parts))

    # anthropic
    payload = {
        "model": model, "max_tokens": cap,
        "system":   system,
        "messages": [{"role": "user", "content": user}],
    }
    resp = _http_json("https://api.anthropic.com/v1/messages", payload,
                      {"content-type": "application/json",
                       "anthropic-version": "2023-06-01", "x-api-key": key},
                      cancel_event=cancel_event, **tmo)
    return _ascii_typography("".join(b.get("text", "") for b in resp.get("content", [])
                             if b.get("type") == "text"))


# Tools the OPTIMIZER agent needs. The porter's _CLI_DENY blocks all of these,
# which is right for a pure text task and wrong here: optimizing means edit ->
# build -> measure -> keep-or-revert, repeatedly. Denied its tools the optimizer
# could only be handed the whole .cpp and asked to retype it faster in one shot,
# which truncated on any real node. Web/Task/MCP stay off: this job never leaves
# the build directory.
# "ultracode" for the OPTIMIZER cannot share the porter's directive
# (_PORT_ORCHESTRATE_DIRECTIVE): that says the model has NO file or shell access,
# that its FINAL MESSAGE is the deliverable, and that it may use Task -- all three
# false here. Pointing a tool-using optimizer at it steers it back into
# blindfolded one-shot retyping, the exact failure the agent rebuild removed.
_OPT_ULTRACODE_DIRECTIVE = (
    "You are making ONE already-working Maya plug-in node FASTER. You have real "
    "file and shell access and a build+measure loop: your deliverable is the "
    "EDITED FILE on disk, not your reply -- nobody reads your reply. Spend the "
    "extra reasoning on finding a better ALGORITHM or data layout, then prove it "
    "with ./bench.sh; never guess that an edit is faster. Prefer one large, "
    "well-reasoned structural change you can measure over a long tail of "
    "micro-tweaks. Keep the file compiling and benchmarked at every step."
)

_OPT_AGENT_ALLOW = "Read Edit Write Glob Grep Bash"
_OPT_AGENT_DENY = ("WebFetch,WebSearch,Task,ToolSearch,Skill,AskUserQuestion,"
                   "NotebookEdit")

# Marker the CLI prints when it cannot install its own shell sandbox.
_SANDBOX_NEST_ERR = "sandbox_apply"

# Said in ONE place: the runtime failure and the pre-flight below must give the
# same remedy, or a headless runner is told two different things about one cause.
_NO_SANDBOX_HINT = (
    "the Claude CLI cannot install its shell sandbox here (%s: Operation not "
    "permitted). Sandboxes do not nest, so the tool-using optimizer agent dies "
    "at startup whenever the compile is itself launched from inside one. Set "
    "MPYNODE_OPT_AGENT_NO_SANDBOX=1 to run the agent with the CLI's OS sandbox "
    "disabled." % _SANDBOX_NEST_ERR)

# What the CLI shells out to for its own sandbox; running it on /usr/bin/true
# exercises the SAME sandbox_apply that fails, in milliseconds and no tokens.
_SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def _truthy(v):
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _sandbox_nests():
    """Can a child of THIS process install a macOS sandbox? ``None`` = unknown.

    The tool-using agent needs one (it is granted Bash) and gets no second
    chance: the CLI exits ~2s in, having done nothing. Probing costs one
    ``/usr/bin/true`` under ``sandbox-exec``, so the answer is free compared with
    discovering it 40 nodes into a batch. Unknown (not macOS, binary absent,
    probe raised) is deliberately NOT "broken" -- an inference must never be the
    thing that blocks a run that would have worked.
    """
    if sys.platform != "darwin" or not os.path.exists(_SANDBOX_EXEC):
        return None
    try:
        p = subprocess.run([_SANDBOX_EXEC, "-p", "(version 1)(allow default)",
                            "/usr/bin/true"],
                           capture_output=True, timeout=20,
                           **toolchain.cli_subprocess_kwargs())
    except Exception:
        return None
    if p.returncode == 0:
        return True
    return False if _SANDBOX_NEST_ERR in (p.stderr or "") else None


def check_agent(provider: str = None) -> dict:
    """Pre-flight the TOOL-USING optimizer agent (``{"ok", "problems", ...}``).

    Stricter than :func:`check_provider`, and deliberately separate from it: the
    one-shot text path needs only a binary on PATH, while the agent additionally
    needs a working OS sandbox for its Bash tool. Folding this into
    ``check_provider`` would block the porter -- which never shells out -- on a
    constraint that does not apply to it. NEVER raises.
    """
    chk      = check_provider(provider)
    provider = chk.get("provider")
    problems = list(chk.get("problems") or [])
    if chk.get("ok") and provider != "claude_cli":
        problems.append(
            "provider %r has no headless tool-using mode; only claude_cli does"
            % provider)
    if (chk.get("ok") and provider == "claude_cli"
            and not _truthy(os.environ.get("MPYNODE_OPT_AGENT_NO_SANDBOX"))
            and _sandbox_nests() is False):
        problems.append(_NO_SANDBOX_HINT)
    return {"ok": not problems, "problems": problems,
            "provider": provider, "kind": chk.get("kind")}


def make_cli_agent_fn(cwd, cancel_event=None, log_cb=None, timeout=None):
    """Build ``agent_fn(prompt) -> transcript`` that runs the CLI AS AN AGENT
    inside ``cwd``, with file + shell tools, iterating on real files.

    Unlike :func:`make_cli_complete_fn` (text in, text out) nothing of value is
    returned through the response: the agent's WORK is the edited files on disk.
    The caller reads those back. The transcript is returned only for logging.

    claude_cli only -- it is the provider with a tool-using headless mode. Other
    providers have no equivalent, so callers keep the one-shot path for them.
    """

    def _cancelled():
        return bool(cancel_event is not None and cancel_event.is_set())

    def agent_fn(prompt: str) -> str:
        if _cancelled():
            raise PortCancelled()
        binp   = _resolve_cli_bin("claude_cli")
        model  = _config.get_model("claude_cli")
        effort = _config.get_effort("claude_cli")
        cmd = [binp, "-p", "--output-format", "stream-json", "--verbose",
               "--allowedTools", _OPT_AGENT_ALLOW,
               "--disallowedTools", _OPT_AGENT_DENY,
               "--permission-mode", _CLI_PERMISSION_MODE,
               "--add-dir", cwd,
               "--strict-mcp-config"]
        # Granting Bash makes the CLI sandbox its own shell execution, which
        # FAILS ("sandbox_apply: Operation not permitted") when the compile is
        # already inside another sandbox -- sandboxes do not nest. Opt-in escape
        # hatch, default OFF: Node Designer launched from Maya is not nested.
        if _truthy(os.environ.get("MPYNODE_OPT_AGENT_NO_SANDBOX")):
            cmd.append("--dangerously-disable-osx-sandbox")
        if _porter_orchestrate():
            # The optimizer's OWN directive -- see _OPT_ULTRACODE_DIRECTIVE for
            # why the porter's is actively wrong here. The literal "ultracode"
            # keyword still leads the prompt body and carries the behaviour.
            cmd += ["--append-system-prompt", _OPT_ULTRACODE_DIRECTIVE]
            prompt = _PORT_ULTRACODE_PREFIX + prompt
        if model:
            cmd += ["--model", model]
        if effort and effort != "off":
            cmd += ["--effort", effort]
        try:
            return _run_cli_proc(cmd, prompt, binp, cancel_event=cancel_event,
                                 log_cb=log_cb, timeout=timeout, cwd=cwd)
        except Exception as exc:
            if _SANDBOX_NEST_ERR in str(exc):
                raise AgentUnavailable(_NO_SANDBOX_HINT)
            # The CLI exited without ever emitting a session: no tool ran, no
            # file was touched, so this round produced literally nothing. Typed
            # so the caller reports "the AI never ran" rather than gating the
            # untouched source (see AgentUnavailable).
            if "produced no output" in str(exc):
                raise AgentUnavailable(
                    "the Claude CLI exited without starting a session: %s"
                    % exc)
            raise

    return agent_fn


def make_cli_complete_fn(cancel_event=None, log_cb=None, timeout=None,
                         max_tokens=None):
    """Build a ``complete_fn(system, user) -> str`` that a slow port can cancel.

    Pass the result as ``port_node(..., complete_fn=make_cli_complete_fn(ev))``.
    ``cancel_event`` is any object with ``.is_set()`` (a ``threading.Event``);
    ``None`` makes a plain completion that never cancels -- behaviourally the
    same as the default ``_complete``. ``log_cb(line)`` (optional) receives the
    porter's streamed chain-of-thought / tool activity (claude_cli stream-json)
    so it can be written to the durable per-node compile log.

    Provider + model are resolved per call exactly as ``_complete`` does
    (``_config.get_provider`` / ``get_model``), so a provider switch between
    the port and its fix-loop rounds is honoured. For a CLI provider
    (claude_cli/gemini_cli/codex_cli) the closure reuses ``_build_cli`` to get
    the argv + stdin, then runs the killable ``_run_cli_proc`` (Popen + ~0.1s
    poll of ``cancel_event`` + terminate/kill, raising ``PortCancelled``). For
    non-CLI/API providers it falls back to ``_complete`` -- checking
    ``cancel_event`` first, and handing it down to the retry loop so a cancel
    also lands during a 429/5xx backoff and between retries. A response already
    being read is still not killable on the API path (that needs streaming).

    Qt-free: ``cancel_event`` is a plain ``threading.Event``; no Qt import.
    """

    def _cancelled():
        return bool(cancel_event is not None and cancel_event.is_set())

    def complete_fn(system: str, user: str) -> str:
        if _cancelled():
            raise PortCancelled()
        provider = _config.get_provider()
        model    = _config.get_model(provider)
        if provider in _config.CLI_PROVIDERS:
            binp   = _resolve_cli_bin(provider)
            prompt = system + "\n\n" + user
            cmd, stdin_text = _build_cli(
                provider, binp, model, _config.get_effort(provider), prompt,
                orchestrate=(provider == "claude_cli" and _porter_orchestrate()),
                stream_json=(provider == "claude_cli"))
            return _run_cli_proc(cmd, stdin_text, binp,
                                 cancel_event=cancel_event, log_cb=log_cb,
                                 timeout=timeout,
                                 env=_cli_env(provider, max_tokens))
        # API providers: no mid-flight kill of a response being read, but the
        # event reaches the retry loop, so a cancel lands before the next attempt
        # and DURING a rate-limit backoff. The caller's budget used to be dropped
        # here, capping every API call at _http_json's 120s however long a budget
        # the optimizer had been given.
        return _complete(system, user, max_tokens=max_tokens, timeout=timeout,
                         cancel_event=cancel_event)

    return complete_fn


def check_provider(provider: str = None, model: str = None) -> dict:
    """Pre-flight: is the configured AI provider reachable WITHOUT spending any
    tokens? Returns ``{"ok": bool, "problems": [str], "provider": str,
    "kind": "cli"|"api"}``; NEVER raises.

    For a CLI provider it resolves the binary on PATH (the exact same resolution
    the real port uses, ``_resolve_cli_bin``). For an API provider it confirms a
    key is configured (preference or env var). It does NOT make any network call
    or launch the model -- the goal is to fail fast and clearly BEFORE the porter
    sends the first prompt, not to validate the key against the service.
    """
    problems = []
    kind     = "api"
    try:
        if provider is None:
            provider = _config.get_provider()
        if provider in _config.CLI_PROVIDERS:
            kind = "cli"
            try:
                _resolve_cli_bin(provider)
            except Exception as exc:
                problems.append(str(exc))
        else:
            kind = "api"
            key  = ""
            try:
                key = _config.get_api_key(provider)
            except Exception as exc:
                problems.append(
                    "Could not read the API key for provider %r: %s"
                    % (provider, exc))
            if not key:
                problems.append(
                    "No API key configured for AI provider %r. Set it in the "
                    "Node Designer's AI Assistant settings (or the provider's "
                    "API-key environment variable), or switch to a CLI provider "
                    "(e.g. claude_cli)." % provider)
    except Exception as exc:
        problems.append("Could not check the AI provider: %s" % exc)
    return {"ok": not problems, "problems": problems,
            "provider": provider, "kind": kind}
