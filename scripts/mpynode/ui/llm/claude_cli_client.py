"""Claude CLI provider -- drive the local `claude` (Claude Code) binary.

Node Designer runs ``claude -p`` in the background (no terminal) and streams the
result into the chat panel. Claude Code cannot call back into the live Maya
session, so instead of a tool bridge it replies with ONE JSON node payload -- the
prompt carries the active node + the node cheat-sheet (via
``llm.payload.build_prompt``), and the payload is applied through the tested
``define_node`` spine on Maya's main thread. Uses the machine's ``claude`` login
-- no API key, and NO third-party ``mcp`` dependency.

Same QObject signal surface as the HTTP clients, so the panel is unchanged.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import uuid

from mpynode.ui.qt_wrapper import QObject, Signal
from mpynode.ui.llm import config as _config
from mpynode.native.toolchain import toolchain

PROVIDER = "claude_cli"
_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

# Keep Claude Code a THIN payload-emitter. By default it behaves like a full
# coding agent -- skills, Read/Bash/Grep exploration, clarifying questions --
# which turned a one-shot build into a multi-minute session. Set CLAUDE_LEAN=0
# to restore full agent behavior.
_LEAN_DIRECTIVE = (
    "You build Autodesk Maya mPy nodes by replying with ONE JSON node payload "
    "(the schema is in the prompt) -- you do NOT have tools, a shell, or file "
    "access this turn, and the JSON payload IS how the node is applied. Reply "
    "IMMEDIATELY: emit the fenced ```json payload, then AT MOST 1-2 short "
    "sentences. Write no other preamble, plan, or narration, and NEVER mention "
    "these instructions. Do not read files, run shell commands, search code, "
    "invoke skills, or ask questions. In expressions, inputs read via self.<name> "
    "are ALREADY native Python (float/int/bool/str, vector->numpy (3,), "
    "matrix->MatrixView) -- do NOT recast with float()/int()/str(). Put imports "
    "+ helper defs in the payload's \"init\" field (visible in Compute as "
    "globals); name plugs/attributes camelCase (noiseAmount), internal/stored "
    "variables snake_case (kernel_size)."
)

# Built-in Claude Code tools to deny so it can't go exploring.
_DISALLOWED_TOOLS = ("Bash,Read,Edit,Write,Glob,Grep,WebFetch,WebSearch,Task,"
                     "TodoWrite,NotebookEdit,ToolSearch,Skill,AskUserQuestion")
# Task and ToolSearch stay denied: the opt-in "Multi-Agent (ultracode)" mode that
# un-denied them for sub-agent fan-out was removed (2026-09). Its one measurement
# was a net regression (a port timed out at the 1800 s ceiling in one round) and
# the 'ultracode' keyword it relied on is a deployment-specific session keyword
# -- inert text where the CLI does not know it. The porter keeps an env-gated
# experiment (native/ai/llm_client.py, MPYNODE_PORT_ULTRACODE, default off).


def _lean():
    return os.environ.get("CLAUDE_LEAN", "1") != "0"


def _bare_flags():
    flags = []
    if os.environ.get("CLAUDE_BARE", "0") == "1":
        flags.append("--bare")
    if os.environ.get("CLAUDE_NO_SKILLS", "0") == "1":
        flags.append("--disable-slash-commands")
    return flags


def _lean_flags():
    if not _lean():
        return []
    disallowed = os.environ.get("CLAUDE_DISALLOWED_TOOLS", _DISALLOWED_TOOLS)
    return (["--disallowedTools", disallowed,
             "--append-system-prompt", _LEAN_DIRECTIVE] + _bare_flags())


def build_cmd(bin_path, prompt, session_id, resume, stream_input=False,
              effort=None, model=None):
    """Construct the `claude` argv (pure -- unit-testable).

    ``stream_input=True`` omits the positional prompt and reads a stream-json
    user message from stdin instead -- the way to attach images to ``-p``.
    ``effort`` (low/medium/high...) maps to ``--effort``; ``model`` maps to
    ``--model``. No MCP flags -- the node payload is parsed from the reply.
    """
    cmd = [bin_path, "-p"]
    if stream_input:
        cmd += ["--input-format", "stream-json"]
    else:
        cmd += [prompt]
    cmd += ["--output-format", "stream-json", "--verbose"] + _lean_flags()
    if model:
        cmd += ["--model", model]
    if effort and effort != "off":
        cmd += ["--effort", effort]
    cmd += (["--resume", session_id] if resume else ["--session-id", session_id])
    return cmd


def build_user_message(prompt, images):
    """Stream-json user message (Anthropic-style content blocks incl. images)."""
    content = [{"type": "text", "text": prompt}]
    for im in (images or []):
        if im.get("name"):
            content.append({"type": "text", "text": "%s:" % im["name"]})
        content.append({
            "type": "image",
            "source": {"type": "base64",
                       "media_type": im.get("media_type", "image/png"),
                       "data": im["data"]},
        })
    return {"type": "user", "message": {"role": "user", "content": content}}


# ---------------------------------------------------------------------------
# Authentication failure -- name the fix instead of the exit code.
# ---------------------------------------------------------------------------
# A logged-out CLI still exits 1 with an EMPTY stderr: the whole story is on
# stdout, in the stream-json events. Reporting only the return code turned
# "you are not logged in" into "claude exited 1", which names neither the
# cause nor the cure.
_AUTH_ERROR_CODES = ("authentication_failed", "oauth_token_expired")

# Both routes are real and both were verified: `claude auth login` writes
# ~/.claude/.credentials.json, while `claude setup-token` only PRINTS a token --
# storing it is the caller's job. The os.environ line works mid-session because
# neither client passes env= to Popen, so the child snapshots this process's
# environment at spawn time; a Maya restart is not needed.
_AUTH_HINT = (
    "Claude CLI is not authenticated -- `claude auth status` will say "
    '"loggedIn": false. Fix it in a terminal, then send again:'
    "\n    claude auth login"
    "\nOr mint a long-lived token and hand it to this Maya session (no "
    "restart needed -- the CLI inherits Maya's environment):"
    "\n    claude setup-token"
    "\nthen, in the Script Editor:"
    '\n    import os; os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "<the token>"'
)


def auth_failure(event):
    """True if one parsed stream-json event reports an auth failure. Pure.

    Keys off the CLI's machine-readable ``error`` code, not its prose: the
    sentence the user sees depends on WHY auth failed ("OAuth session expired
    and could not be refreshed" with no token on disk, "401 OAuth access token
    is invalid" with a bad one), while the code is stable across both. The
    terminal ``result`` event drops the code, so that one is matched on
    ``is_error`` plus the one word every variant shares.
    """
    if not isinstance(event, dict):
        return False
    if event.get("error") in _AUTH_ERROR_CODES:
        return True
    if event.get("is_error"):
        return "authenticate" in str(event.get("result") or "").lower()
    return False


# ---------------------------------------------------------------------------
# Model listing -- ask the CLI, NEVER an API key.
# ---------------------------------------------------------------------------
# `claude -p /model` is answered LOCALLY (no network, no key) with:
#
#   Current model: Opus 5 (1M context) (effort: xhigh)
#   Usage: /model <name>. Available: sonnet, opus, ..., or a full model ID.
#
# This is the ONLY list guaranteed to match what THIS install will run. The
# Anthropic HTTP list describes a different backend: a gateway build rejects ids
# it returns (`claude-opus-4-1-20250805` is in /v1/models, the CLI refuses it).
_AVAIL_RE = re.compile(r"Available:\s*(.+)", re.IGNORECASE)
_CURRENT_RE = re.compile(r"Current model:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
# Prose escape hatch closing the sentence -- not a model name.
_TRAILER_RE = re.compile(r",?\s*or a full model ID\.?\s*$", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z0-9._\-\[\]]+")


def parse_model_listing(text):
    """``(model_names, current_label)`` from a ``/model`` reply. Pure.

    Deliberately tolerant: the launcher prints banners around the answer and the
    wording can drift between CLI versions. Anything unrecognised yields
    ``([], "")`` so the caller falls back rather than offering junk.
    """
    current = ""
    m = _CURRENT_RE.search(text or "")
    if m:
        current = m.group(1).strip()
    names = []
    for line in (text or "").splitlines():
        m = _AVAIL_RE.search(line)
        if not m:
            continue
        body = _TRAILER_RE.sub("", m.group(1).strip()).rstrip(".")
        for tok in body.split(","):
            tok = tok.strip()
            if tok and _TOKEN_RE.fullmatch(tok) and tok not in names:
                names.append(tok)
        break
    return names, current


def alias_listing(bin_path=None, timeout=60.0):
    """``(alias_names, current_label)`` the LOCAL ``claude`` accepts.

    Asked OF THE CLI -- no API key. A CLI provider authenticates through the
    machine's own ``claude`` login (personal or IT-managed), so demanding an
    Anthropic key just to populate the dropdown was wrong. Returns ``([], "")``
    when the binary is absent or the reply doesn't parse.

    ``--bare`` skips hooks/LSP/plugin sync and takes the round trip from ~20s to
    ~4s; it is retried WITHOUT the flag for older CLIs that lack it.
    """
    binp = _resolve(bin_path)
    if not binp:
        return [], ""
    for extra in (["--bare"], []):
        out = _run_cli(binp, ["-p", "/model"], extra, timeout)
        if out is None:
            continue
        names, current = parse_model_listing(out)
        if names:
            return names, current
    return [], ""


# ---------------------------------------------------------------------------
# Full versioned ids -- discovered, then VALIDATED against the CLI itself.
# ---------------------------------------------------------------------------
# `/model` reports only ALIASES (opus, opus[1m], ...). Full ids like
# `claude-opus-4-8` are equally valid but never enumerated, so a user cannot
# pick a specific older version. Recovered in two steps:
#
#   1. CANDIDATES -- scraped from the installed CLI's OWN binary (its model
#      table). Build-specific and therefore untrusted: treated as guesses only.
#   2. VALIDATION -- `claude -p "/model <id>"`, answered locally with no LLM
#      turn and no key. Three outcomes, and only the first is offered:
#        "Set model to Opus 5 for this session only"   -> valid (+ display name)
#        "Model 'claude-opus' not found"               -> unknown id
#        "API error: 403 Access to Fable is restricted" -> real id, NO ACCESS
#
# Nothing unvalidated reaches the dropdown, so a stale or reorganised binary
# costs coverage, never correctness -- worst case, aliases alone.
#
# What the dropdown says about a fallback alias. The panel renders `displays` as
# each row's tooltip, so this is where a floating entry declares itself.
_ALIAS_DISPLAY = ("floating alias -- NOT version-pinned; re-points to a new "
                  "model on release day")
_SET_RE = re.compile(r"Set model to\s+(.+?)\s+for this session", re.IGNORECASE)
_NOTFOUND_RE = re.compile(r"Model\s+'.*?'\s+not found", re.IGNORECASE)
_RESTRICTED_RE = re.compile(r"API error:\s*(?:403|401)\b", re.IGNORECASE)
# Model ids the CLI could know about. Anchored on the vendor prefix + a digit so
# doc/filename noise ("claude-fable-5.md") and internal suffixes ("-v1") drop.
_CAND_RE = re.compile(rb"claude-(?:opus|sonnet|haiku|fable)-[0-9][A-Za-z0-9._-]*")
_CAND_OK = re.compile(r"^claude-[a-z]+-[0-9][A-Za-z0-9-]*$")
_SCAN_CHUNK = 8 << 20
_MIN_BIN = 2 << 20
_MAX_SCAN_FILES = 6


def _resolve(bin_path=None):
    try:
        return toolchain.resolve_executable(bin_path or _CLAUDE_BIN)
    except Exception:
        return None


def _run_cli(binp, args, extra=(), timeout=90.0):
    """Combined stdout+stderr of a one-shot CLI call, or None if it failed.

    stdin is /dev/null: with a pipe the CLI waits 3s for input it will never get
    (observed as a spurious "no stdin data received" instead of the answer).
    """
    try:
        proc = subprocess.run(
            [binp] + list(extra) + list(args),
            capture_output=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
            **toolchain.cli_subprocess_kwargs())
    except Exception:
        return None
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def probe_model(model_id, bin_path=None, timeout=90.0):
    """``(status, label)`` for one id -- 'valid' | 'unknown' | 'restricted' | 'error'.

    Local and keyless; ``/model <id>`` resolves without running a turn.
    """
    binp = _resolve(bin_path)
    if not binp:
        return "error", ""
    out = _run_cli(binp, ["-p", "/model %s" % model_id], ["--bare"], timeout)
    if out is None:
        return "error", ""
    m = _SET_RE.search(out)
    if m:
        return "valid", m.group(1).strip()
    if _NOTFOUND_RE.search(out):
        return "unknown", ""
    if _RESTRICTED_RE.search(out):
        return "restricted", ""
    return "error", ""


def _claude_related(path):
    """True when a PATH COMPONENT actually names Claude.

    Without this the scan is "biggest neighbour wins". That is right only when
    the launcher is a SYMLINK into Claude's own tree (macOS: /usr/local/bin/claude
    -> claude_code/os/claude, so every neighbour is Claude's). Where the launcher
    is a REAL file in a SHARED bin dir -- a 392 KB chocolatey claude.exe --
    resolution stays put and the neighbours are unrelated 74 MB binaries
    (gslides.exe, gmail.exe, gmux.exe), which yield no model ids at all.
    """
    parts = os.path.normpath(path).lower().replace("\\", "/").split("/")
    return any("claude" in p for p in parts)


def _scan_files(binp):
    """Files plausibly holding the CLI's model table, largest first.

    The launcher on PATH is often a small shim (a shell script here), with the
    real multi-MB binary a directory or two away -- so search the resolved
    file's own directory, its parent, and the parent's immediate subdirs, and
    keep only those that are Claude's (see ``_claude_related``).
    """
    out = []
    try:
        real = os.path.realpath(binp)
        d = os.path.dirname(real)
        roots = [d, os.path.dirname(d)]
        roots += [os.path.join(roots[1], n) for n in sorted(os.listdir(roots[1]))
                  if os.path.isdir(os.path.join(roots[1], n))]
        seen = set()
        for r in roots:
            try:
                entries = sorted(os.listdir(r))
            except OSError:
                continue
            for n in entries:
                p = os.path.join(r, n)
                if p in seen or not os.path.isfile(p) or os.path.islink(p):
                    continue
                seen.add(p)
                if not _claude_related(p):
                    continue
                try:
                    sz = os.path.getsize(p)
                except OSError:
                    continue
                if sz >= _MIN_BIN:
                    out.append((sz, p))
    except Exception:
        return []
    out.sort(reverse=True)
    return [p for _sz, p in out[:_MAX_SCAN_FILES]]


def candidate_model_ids(bin_path=None):
    """Full model ids the installed CLI mentions. GUESSES -- always validate.

    Read in bounded chunks (the binary can be ~170 MB) with a small overlap so
    an id straddling a chunk boundary is not lost.
    """
    binp = _resolve(bin_path)
    if not binp:
        return []
    found = set()
    for path in _scan_files(binp):
        try:
            with open(path, "rb") as fh:
                tail = b""
                while True:
                    chunk = fh.read(_SCAN_CHUNK)
                    if not chunk:
                        break
                    for m in _CAND_RE.finditer(tail + chunk):
                        found.add(m.group(0).decode("ascii", "replace"))
                    tail = chunk[-64:]
        except Exception:
            continue
        if found:
            break  # the biggest file that knows any model is the right one
    return sorted(m for m in found if _CAND_OK.match(m))


_NUM_RE = re.compile(r"(\d+)")
_DATED_RE = re.compile(r"^(.*)-(20\d{6})$")


def _nat_key(mid):
    """Natural-sort key: digit runs compare NUMERICALLY, not as text.

    Plain string order puts ``claude-opus-4-10`` *before* ``claude-opus-4-8``
    ("1" < "8"), which would bury the newest build the day a two-digit minor
    ships. Every element is a 3-tuple so a digit run and a literal are always
    comparable -- a TypeError here would empty the dropdown.
    """
    out = []
    for p in _NUM_RE.split(mid or ""):
        out.append((1, int(p), "") if p.isdigit() else (0, 0, p))
    return out


def order_models(ids, wide=()):
    """EXPLICIT ids, NEWEST FIRST within each family, each followed by its twin.

    Reverse natural order, so ``claude-opus-5`` sits above ``claude-opus-4-8``
    and the family blocks stay contiguous (the family name is the leading text
    run of the key). A ``[1m]`` variant sits next to its base because it IS that
    model, just with the 1M-token context.

    This does NOT filter: it is a pure sorter and passes through whatever it is
    given, aliases included. Floating aliases ("opus", "opus[1m]") are kept out
    by ``list_models``, which feeds this only ids it VALIDATED -- they hide which
    model actually runs and silently re-point on every release, so ``opus`` is
    Opus 5 today and becomes Opus 6 the day that ships, changing a saved node's
    behaviour with no edit. The one exception is ``list_models``' last-resort
    alias fallback, whose entries do come through here and are labelled there.

    Sorting is purely lexical/numeric -- there is no capability table, so an
    install we have never seen still orders sanely. Pure.
    """
    wide = set(wide or ())
    ids = [m for m in (ids or ()) if m]
    known = set(ids)
    # A trailing YYYYMMDD is a BUILD STAMP of the id in front of it, not a
    # version component: claude-sonnet-4-20250514 *is* "Sonnet 4", so letting
    # 20250514 outrank the 6 in claude-sonnet-4-6 would hoist the oldest entry
    # in the family to the top. Park it under its own root instead.
    dated = {}
    roots = []
    for mid in ids:
        m = _DATED_RE.match(mid)
        if m and m.group(1) in known:
            dated.setdefault(m.group(1), []).append(mid)
        else:
            roots.append(mid)

    out = []
    seen = set()
    for mid in sorted(roots, key=_nat_key, reverse=True):
        if mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
        twin = "%s[1m]" % mid
        if twin in wide and twin not in seen:
            seen.add(twin)
            out.append(twin)
        for d in sorted(dated.get(mid, ()), key=_nat_key, reverse=True):
            if d not in seen:
                seen.add(d)
                out.append(d)
    return out


def order_display(names):
    """Re-derive display order from a FLAT list, e.g. one restored from prefs.

    Keeps a cached list rendering identically to a fresh fetch, so changing the
    sort takes effect at launch instead of only after a Refresh. Pure.
    """
    names = [m for m in (names or ()) if m]
    return order_models([m for m in names if not m.endswith("[1m]")],
                        [m for m in names if m.endswith("[1m]")])


def _validate_many(cands, binp, timeout, max_workers):
    """``{id: display_name}`` for those of ``cands`` this CLI will actually run.

    Order-preserving (``Executor.map`` yields in input order), so the caller's
    discovery order carries through to the dropdown.
    """
    out = {}
    if not cands:
        return out
    import concurrent.futures as _cf

    with _cf.ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
        for mid, (status, label) in zip(
            cands, ex.map(lambda m: probe_model(m, binp, timeout), cands)
        ):
            if status == "valid":
                out[mid] = label
    return out


def list_models(bin_path=None, timeout=90.0, extra_candidates=(),
                max_workers=16):
    """``(names, current_label, displays)`` for the Claude CLI dropdown.

    Every entry is an EXPLICIT versioned id -- no floating aliases -- EXCEPT on
    the last-resort fallback below, which labels what it offers. Two probe
    passes, both keyless and local:

    1. validate each discovered candidate (``claude-opus-5``, ...);
    2. for each survivor, validate its ``[1m]`` twin and keep it ONLY if the
       display name actually changes. ``[1m]`` is not a universal suffix --
       ``claude-haiku-4-5[1m]`` is a 400 (the 1M beta header is rejected) and
       ``claude-sonnet-5[1m]`` is accepted but resolves to plain "Sonnet 5", so
       offering it would just duplicate the base id. Comparing display names
       lets the CLI decide, with no table of which models support 1M.

    ``extra_candidates`` are merged in; the panel passes the Anthropic API's ids
    when a key happens to exist. They are candidates ONLY -- every one is still
    validated here, because the HTTP API describes a different backend and lists
    ids this CLI rejects.
    """
    binp = _resolve(bin_path)
    if not binp:
        return [], "", {}
    # Aliases are NOT offered on the normal path; this call is for the
    # "Current model:" label -- and for the fallback below.
    aliases, current = alias_listing(binp, timeout)

    def _alias_fallback():
        """LAST RESORT: offer the aliases the CLI itself just listed.

        Discovery found nothing this build will run. An EMPTY dropdown means no
        agent can be selected at all (observed on Windows, where the launcher is
        a shim in a shared bin dir), which is strictly worse than a labelled
        floating alias. The alias POLICY is untouched: the normal path above
        still offers only validated pinned ids. ``order_models`` is a pure
        sorter and would pass an alias straight through, so the exclusion lives
        HERE -- and so every entry on this path says what it is in ``displays``.
        """
        names = [a for a in (aliases or ()) if a]
        return names, current, {a: _ALIAS_DISPLAY for a in names}

    cands = [c for c in candidate_model_ids(binp) if c]
    for c in (extra_candidates or ()):
        c = str(c).strip()
        if c and _CAND_OK.match(c) and c not in cands:
            cands.append(c)
    if not cands:
        return _alias_fallback()

    try:
        displays = _validate_many(cands, binp, timeout, max_workers)
        wide = _validate_many(["%s[1m]" % m for m in displays], binp, timeout,
                              max_workers)
    except Exception:
        return _alias_fallback()
    if not displays:
        return _alias_fallback()

    for twin, label in wide.items():
        base = twin[:-len("[1m]")]
        if label and label != displays.get(base):
            displays[twin] = label
    keep_wide = [m for m in displays if m.endswith("[1m]")]
    bases = [m for m in displays if not m.endswith("[1m]")]
    return order_models(bases, keep_wide), current, displays


class ClaudeCliClient(QObject):
    assistantText = Signal(str)
    toolStarted = Signal(str)
    toolFinished = Signal(str)
    turnFinished = Signal()
    notice = Signal(str)
    thinking = Signal(str)  # thinking trace (when effort > off)
    retryScheduled = Signal(int, int, int, int, str)  # interface compat (unused)
    tokensUsed = Signal(int)
    errorOccurred = Signal(str)
    busyChanged = Signal(bool)

    def __init__(self, ctx_provider=None, parent=None):
        super().__init__(parent)
        self._ctx_provider = ctx_provider
        self._busy = False
        self._cancel = threading.Event()
        self._proc = None
        self._session_id = str(uuid.uuid4())
        self._started = False  # session created? -> use --resume next time
        self._emitted_text = False
        self._answer_text = ""   # accumulated reply -> payload extraction
        self._ctx = None         # ToolContext captured per turn (GUI thread)
        self._node_name = None   # active node captured per turn (GUI thread)
        self._auth_failed = False  # set from the stream; reset every turn

    def reset(self):
        self._session_id = str(uuid.uuid4())
        self._started = False

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

    def _append_answer(self, text):
        if not text:
            return
        self._answer_text += text
        self.assistantText.emit(text)
        self._emitted_text = True

    def send(self, user_text, images=None):
        if self._busy:
            self.errorOccurred.emit("AI Assistant is still working on the previous request.")
            return
        if toolchain.find_executable(_CLAUDE_BIN) is None:
            self.errorOccurred.emit(
                "`claude` CLI not found on PATH. Install Claude Code (or set the "
                "CLAUDE_BIN env var).")
            return
        # Capture the active node + a ToolContext on the GUI thread (Maya-safe),
        # then compose the payload-mode prompt (serializes the active node).
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
        t = threading.Thread(
            target=self._run, args=(prompt, images or []), daemon=True)
        t.start()

    # -- worker thread ---------------------------------------------------

    def _run(self, prompt, images):
        self._emitted_text = False
        self._answer_text = ""
        self._auth_failed = False
        try:
            from mpynode.native.toolchain import toolchain

            stream_input = bool(images)
            cmd = build_cmd(_CLAUDE_BIN, prompt, self._session_id,
                            self._started, stream_input=stream_input,
                            effort=_config.get_effort("claude_cli"),
                            model=_config.get_model("claude_cli"))
            # Resolve the launcher (Windows .cmd/.exe shims need a full path).
            if cmd:
                cmd[0] = toolchain.resolve_executable(cmd[0])
            # DEVNULL, not None: None INHERITS our stdin, and a GUI Maya has
            # no console, so claude waits on a handle that never delivers and
            # charges 3s per request ("no stdin data received in 3s") before
            # proceeding. DEVNULL is an immediate EOF. Only the image path,
            # which really does feed a stream-json message, gets a PIPE.
            self._proc = subprocess.Popen(
                cmd,
                stdin=(subprocess.PIPE if stream_input
                       else subprocess.DEVNULL),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=1, **toolchain.cli_subprocess_kwargs())
            self._started = True
            if stream_input:
                # Feed the user message (text + base64 images) on stdin, then
                # close it so claude processes the single -p turn and exits.
                try:
                    msg = build_user_message(prompt, images)
                    self._proc.stdin.write(json.dumps(msg) + "\n")
                    self._proc.stdin.flush()
                    self._proc.stdin.close()
                except Exception:
                    pass
            for line in self._proc.stdout:
                if self._cancel.is_set():
                    break
                line = line.strip()
                if line:
                    self._handle_event(line)
            self._proc.wait()
            if self._cancel.is_set():
                self.notice.emit("Stopped.")
            elif self._proc.returncode not in (0, None):
                err = ""
                try:
                    err = (self._proc.stderr.read() or "")[:600]
                except Exception:
                    pass
                if self._auth_failed:
                    self.errorOccurred.emit(_AUTH_HINT)
                else:
                    self.errorOccurred.emit(
                        "claude exited %s%s" % (self._proc.returncode,
                                                (": " + err) if err else ""))
            else:
                # Apply the node payload the agent emitted (main thread).
                self._finalize()
            self.turnFinished.emit()
        except Exception as exc:
            self.errorOccurred.emit("%s: %s" % (type(exc).__name__, exc))
        finally:
            self._proc = None
            self._busy = False
            self.busyChanged.emit(False)

    def _finalize(self):
        if self._cancel.is_set():
            return
        try:
            from mpynode.ui.llm import payload as _payload

            _payload.finalize_turn(self, self._node_name, self._ctx,
                                   self._answer_text)
        except Exception:
            pass

    def _handle_event(self, line):
        try:
            ev = json.loads(line)
        except Exception:
            return
        if auth_failure(ev):
            self._auth_failed = True
        et = ev.get("type")
        if et == "assistant":
            # Output nested under a tool use (parent_tool_use_id) is interim
            # text, NOT the main answer: only the top-level agent emits the
            # payload. Kept although sub-agents are denied -- it is what makes
            # any nested chatter harmless.
            is_sub = ev.get("parent_tool_use_id") is not None
            msg = ev.get("message", {}) or {}
            for b in (msg.get("content") or []):
                bt = b.get("type")
                if bt == "text" and b.get("text"):
                    if is_sub:
                        continue
                    self._append_answer(b["text"])
                elif bt == "thinking":
                    if is_sub:
                        continue
                    th = b.get("thinking") or b.get("text")
                    if th:
                        self.thinking.emit(th)
            u = msg.get("usage") or {}
            tot = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
            if tot:
                self.tokensUsed.emit(int(tot))
        elif et == "result":
            # Only surface the aggregated result if no streamed text appeared.
            r = ev.get("result")
            if not self._emitted_text and isinstance(r, str) and r.strip():
                self._append_answer(r)
