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

PROVIDER    = "claude_cli"
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


def main_model(usage):
    """The model that did most of the work in a result's ``modelUsage``. Pure.

    ``modelUsage`` maps model id -> token counts, and can name a small helper
    model beside the main one, so the one with the most output wins. ``''`` for
    anything that is not such a mapping.
    """
    if not isinstance(usage, dict):
        return ""
    best, most = "", -1
    for mid, u in usage.items():
        out = (u or {}).get("outputTokens", 0) if isinstance(u, dict) else 0
        if mid and isinstance(out, (int, float)) and out > most:
            best, most = str(mid), out
    return best


# ---------------------------------------------------------------------------
# Model listing -- ask the CLI, NEVER an API key.
# ---------------------------------------------------------------------------
# `claude -p /model` is answered LOCALLY (no network, no key) with:
#
#   Current model: `Opus 5 (1M context) (default)` (effort: xhigh)
#   Usage: /model <name>. Available: sonnet, opus, ..., or a full model ID.
#
# (2.1.273 wraps the name in backticks and tags it "(default)"; earlier builds
# printed it bare. clean_label() takes either.)
#
# This is the ONLY list guaranteed to match what THIS install will run. The
# Anthropic HTTP list describes a different backend: a gateway build rejects ids
# it returns (`claude-opus-4-1-20250805` is in /v1/models, the CLI refuses it).
_AVAIL_RE   = re.compile(r"Available:\s*(.+)", re.IGNORECASE)
_CURRENT_RE = re.compile(r"Current model:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
# Prose escape hatch closing the sentence -- not a model name.
_TRAILER_RE = re.compile(r",?\s*or a full model ID\.?\s*$", re.IGNORECASE)
_TOKEN_RE   = re.compile(r"[A-Za-z0-9._\-\[\]]+")
# Decorations the CLI puts around a display name -- none of them name the model.
_TAG_RE = re.compile(r"\s*\((?:effort:[^)]*|default|disabled)\)", re.IGNORECASE)


def clean_label(text):
    """A model's display name without the CLI's decorations. Pure.

    ``\\`Opus 5 (1M context) (default)\\` (effort: xhigh)`` -> ``Opus 5 (1M
    context)``. The effort tag reports settings.json, not what a turn sends (the
    panel passes its own ``--effort``), and ``(default)`` describes the session
    rather than the model -- left in, either one mislabels a row.
    """
    return " ".join(_TAG_RE.sub("", str(text or "").replace("`", "")).split())


def parse_model_listing(text):
    """``(model_names, current_label)`` from a ``/model`` reply. Pure.

    Deliberately tolerant: the launcher prints banners around the answer and the
    wording can drift between CLI versions. Anything unrecognised yields
    ``([], "")`` so the caller falls back rather than offering junk.
    """
    current = ""
    m       = _CURRENT_RE.search(text or "")
    if m:
        current = clean_label(m.group(1))
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
#   2. VALIDATION -- `claude -p "/model <id>"`. No API key and no agent turn, but
#      NOT free for a full id: the CLI checks it by sending that model a
#      one-output-token request ("Hi", max_tokens 1) with the machine's login.
#      An alias resolves locally. Only the first outcome is a pickable row:
#        "Set model to `Opus 5` for this session only"  -> valid (+ display name)
#        "... version 2.1.280 or newer is required"     -> too_old (greyed row)
#        "Model 'claude-opus' not found"                -> unknown id
#        "API error: 403 Access to Fable is restricted" -> real id, NO ACCESS
#        "Model 'x' is not available. Your organization restricts ..."
#                                                       -> restricted, by policy
#        "Unable to validate model: <why>"              -> error, reason kept
#
# Nothing unvalidated reaches the dropdown, so a stale or reorganised binary
# costs coverage, never correctness -- worst case, aliases alone.
#
# What the dropdown says about a fallback alias. The panel renders `displays` as
# each row's tooltip, so this is where a floating entry declares itself.
_ALIAS_DISPLAY = ("floating alias -- NOT version-pinned; re-points to a new "
                  "model on release day")
_SET_RE        = re.compile(r"Set model to\s+(.+?)\s+for this session", re.IGNORECASE)
_NOTFOUND_RE   = re.compile(r"Model\s+'.*?'\s+not found", re.IGNORECASE)
_RESTRICTED_RE = re.compile(r"API error:\s*(?:403|401)\b", re.IGNORECASE)
_POLICY_RE     = re.compile(r"Model\s+'.*?'\s+is not available", re.IGNORECASE)
_UNABLE_RE     = re.compile(r"Unable to validate model:\s*([^\r\n]+)", re.IGNORECASE)
_NOAUTH_RE     = re.compile(r"Could not resolve authentication method", re.IGNORECASE)
_BADFLAG_RE    = re.compile(r"unknown option", re.IGNORECASE)
# "This CLI is too old for that model": the server's machine-readable code, and
# the sentence carrying the version (a real turn only has the sentence).
_TOO_OLD_CODE = "claude_code_version_too_old"
_TOO_OLD_RE = re.compile(r"version\s+(\d+(?:\.\d+)+)\s+or newer is required",
                         re.IGNORECASE)
# Flag sets a probe tries, in order. `--bare` is fast and is all a third-party
# backend needs (Bedrock/Vertex/gateway credentials come from the environment),
# but it never reads the OAuth login: on a claude.ai login EVERY full id answers
# "Could not resolve authentication method", which emptied the list down to the
# alias fallback. The next set keeps the login while still switching off project
# hooks, MCP servers and transcripts; the last drops --safe-mode for a CLI that
# predates it ("unknown option").
_PROBE_FLAG_SETS = (
    ("--bare",),
    ("--safe-mode", "--strict-mcp-config", "--no-session-persistence"),
    ("--strict-mcp-config", "--no-session-persistence"),
)
# Per binary, the first flag set that got a real answer -- later probes start
# there instead of paying for the sets that cannot work on this login.
_PROBE_START = {}
# Model ids the CLI could know about. Anchored on the vendor prefix + a digit so
# doc/filename noise ("claude-fable-5.md") drops. The family is NOT listed: a
# family that ships tomorrow must be found with no code change, and whatever
# else matches is weeded out by validation. _CAND_REV is a Bedrock revision
# suffix (claude-opus-4-6-v1): the same model under a cloud's naming, which the
# Claude CLI does not take.
_CAND_RE        = re.compile(rb"claude-[a-z]+-[0-9][A-Za-z0-9._-]*")
_CAND_OK        = re.compile(r"^claude-[a-z]+-[0-9][A-Za-z0-9-]*$")
_CAND_REV       = re.compile(r"-v[0-9]+$")
_FAMILY_RE      = re.compile(r"^claude-([a-z]+)-[0-9]")
_VERSION_RE     = re.compile(r"(\d+\.\d+\.\d+)")
_SCAN_CHUNK     = 8 << 20
_MIN_BIN        = 2 << 20
_MAX_SCAN_FILES = 6


def _is_candidate(mid):
    return bool(_CAND_OK.match(mid or "")) and not _CAND_REV.search(mid)


def family_of(model_id):
    """``'opus'`` for ``claude-opus-5[1m]``; ``''`` for anything else. Pure.

    Read from the id itself, so a new family groups correctly with no table.
    """
    m = _FAMILY_RE.match(model_id or "")
    return m.group(1) if m else ""


def version_too_old(text):
    """The Claude Code version a model needs, when ``text`` says the installed CLI
    is too old for it. ``None`` otherwise; ``''`` when it says so without a
    number. Pure.
    """
    s = str(text or "")
    m = _TOO_OLD_RE.search(s)
    if m:
        return m.group(1)
    if _TOO_OLD_CODE in s:
        return ""
    return None


def too_old_hint(version):
    """What to do about a model the installed CLI is too old to run."""
    need = ("Claude Code %s or newer" % version) if version else "a newer Claude Code"
    return ("This model needs %s. Run `claude update` in a terminal (or update "
            "the Claude desktop app), then press ↻ next to Model." % need)


def _unable_reason(out):
    m = _UNABLE_RE.search(out or "")
    return m.group(1).strip()[:200] if m else ""


def classify_probe(out):
    """``(status, detail)`` for one ``/model <id>`` reply. Pure.

    Status is 'valid' | 'too_old' | 'unknown' | 'restricted' | 'error'. Detail is
    the clean display name when valid, the minimum Claude Code version when
    too_old ('' if the reply gave none), the CLI's own reason when it explains
    an error, else ''.
    """
    m = _SET_RE.search(out or "")
    if m:
        return "valid", clean_label(m.group(1))
    if _NOTFOUND_RE.search(out or ""):
        return "unknown", ""
    ver = version_too_old(out)
    if ver is not None:
        return "too_old", ver
    if _RESTRICTED_RE.search(out or "") or _POLICY_RE.search(out or ""):
        return "restricted", ""
    return "error", _unable_reason(out)


def _resolve(bin_path=None):
    try:
        return toolchain.resolve_executable(bin_path or _CLAUDE_BIN)
    except Exception:
        return None


def _run_cli(binp, args, extra=(), timeout=90.0, feed=None):
    """Combined stdout+stderr of a one-shot CLI call, or None if it failed.

    stdin is /dev/null unless ``feed`` is given: with an idle pipe the CLI waits
    3s for input it will never get (observed as a spurious "no stdin data
    received" instead of the answer).
    """
    stdin = {"input": feed} if feed is not None else {"stdin": subprocess.DEVNULL}
    try:
        proc = subprocess.run(
            [binp] + list(extra) + list(args),
            capture_output=True, timeout=timeout,
            **stdin,
            **toolchain.cli_subprocess_kwargs())
    except Exception:
        return None
    return (proc.stdout or "") + "\n" + (proc.stderr or "")


def probe_model(model_id, bin_path=None, timeout=90.0):
    """``(status, detail)`` for one id -- see ``classify_probe``.

    No API key and no agent turn; a full id costs the CLI's one-token check
    (see VALIDATION above). Tries each of ``_PROBE_FLAG_SETS`` until one gets a
    real answer, so a login that ``--bare`` cannot read still validates. No
    answer at all (a timeout, a binary that will not start) ends it there:
    another flag set would only wait as long again.
    """
    binp = _resolve(bin_path)
    if not binp:
        return "error", ""
    result = ("error", "")
    for i in range(_PROBE_START.get(binp, 0), len(_PROBE_FLAG_SETS)):
        out = _run_cli(binp, ["-p", "/model %s" % model_id],
                       list(_PROBE_FLAG_SETS[i]) + ["--model", _GUARD_MODEL],
                       timeout)
        if out is None:
            return "error", _NO_ANSWER
        if _NOAUTH_RE.search(out) or _BADFLAG_RE.search(out):
            result = ("error", _unable_reason(out) or out.strip()[:200])
            continue
        _PROBE_START[binp] = i
        return classify_probe(out)
    return result


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
        real  = os.path.realpath(binp)
        d     = os.path.dirname(real)
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
    return sorted(m for m in found if _is_candidate(m))


_NUM_RE   = re.compile(r"(\d+)")
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
    wide  = set(wide or ())
    ids   = [m for m in (ids or ()) if m]
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

    out  = []
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


# Batched probing: ``-p --input-format stream-json`` reads a stream of user
# messages and runs each slash command LOCALLY, one ``result`` event per
# message, in order. One process then answers each further ``/model <id>`` in
# ~0.5 s, where separate processes serialise on the login at ~1.2 s apiece --
# 16 in parallel took as long as 16 in a row (both measured on 2.1.273).
#
# The session model is an id no backend has. /model runs locally whatever it
# is, but a message some CLI version mistook for a PROMPT would run a real,
# billed turn on it; on this model that turn fails at no cost (verified: cost
# 0, "There's an issue with the selected model").
_GUARD_MODEL = "claude-probe-guard-0"
_FEED_ARGS = ("-p", "--input-format", "stream-json", "--output-format",
              "stream-json", "--verbose")
_NO_ANSWER = "no answer from claude (it timed out or would not start)"
# Batches run side by side, about this many ids each. The login step still
# serialises across processes, so more, smaller batches stop paying off: 32 ids
# took 18.9 s in 1 process, 10.0 s in 4 and 11.1 s in 8.
_BATCH_PROCS = 4
_BATCH_SIZE  = 8


def _feed(commands):
    return "".join(json.dumps({"type": "user",
                               "message": {"role": "user", "content": c}}) + "\n"
                   for c in commands)


def _batch_replies(out):
    """The ``result`` text of each ``result`` event in a stream-json log, in order."""
    replies = []
    for line in (out or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            replies.append(str(ev.get("result") or ""))
    return replies


def _probe_batch(ids, binp, timeout):
    """``{id: (status, detail)}`` from ONE process fed every ``/model <id>``.

    Holds only the ids that got an answer; the caller probes the rest one
    process each. Walks ``_PROBE_FLAG_SETS`` like ``probe_model``, judging auth
    PER REPLY: a policy refusal is answered locally before any credential is
    read, so one id can answer under ``--bare`` while the rest cannot log in.
    Only the ids that could not log in move on to the next set.
    """
    done = {}
    todo = [m for m in (ids or ()) if m]
    for i in range(_PROBE_START.get(binp, 0), len(_PROBE_FLAG_SETS)):
        if not todo:
            break
        out = _run_cli(binp, _FEED_ARGS,
                       list(_PROBE_FLAG_SETS[i]) + ["--model", _GUARD_MODEL],
                       timeout + 2.0 * len(todo),
                       feed=_feed(["/model %s" % m for m in todo]))
        if out is None:
            break  # no answer in time; another set would only wait as long
        if _BADFLAG_RE.search(out):
            continue
        replies = _batch_replies(out)
        if len(replies) != len(todo):
            break  # replies cannot be paired with ids; each is probed alone
        noauth = []
        for mid, reply in zip(todo, replies):
            if _NOAUTH_RE.search(reply):
                noauth.append(mid)
            else:
                done[mid] = classify_probe(reply)
        if not noauth:
            _PROBE_START[binp] = i
        todo = noauth
    return done


def _probe_batches(ids, binp, timeout):
    """``_probe_batch`` split over up to ``_BATCH_PROCS`` concurrent processes."""
    ids = [m for m in (ids or ()) if m]
    k   = max(1, min(_BATCH_PROCS, -(-len(ids) // _BATCH_SIZE)))
    if k == 1:
        return _probe_batch(ids, binp, timeout)
    import concurrent.futures as _cf

    out = {}
    with _cf.ThreadPoolExecutor(max_workers=k) as ex:
        for part in ex.map(lambda chunk: _probe_batch(chunk, binp, timeout),
                           [ids[i::k] for i in range(k)]):
            out.update(part)
    return out


def _probe_many(cands, binp, timeout, max_workers):
    """``{id: (status, detail)}`` for every id in ``cands``, in input order.

    Batched processes first (``_probe_batches``). Whatever they leave unanswered
    is probed one process per id, the first ALONE: that settles which flag set
    this login needs (``_PROBE_START``), and when it cannot authenticate at all
    -- logged out, offline -- or gets no answer in time, the rest would fail the
    same way, so they are never spawned.
    """
    cands = [c for c in (cands or ()) if c]
    if not cands:
        return {}
    done = _probe_batches(cands, binp, timeout)
    todo = [c for c in cands if c not in done]
    if not todo:
        return {m: done[m] for m in cands}
    first = probe_model(todo[0], binp, timeout)
    if first[0] == "error" and (first[1] == _NO_ANSWER
                                or _NOAUTH_RE.search(first[1] or "")):
        done.update({m: first for m in todo})
        return {m: done[m] for m in cands}
    out          = dict(done)
    out[todo[0]] = first
    rest         = todo[1:]
    if rest:
        import concurrent.futures as _cf

        with _cf.ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
            for mid, res in zip(rest, ex.map(
                    lambda m: probe_model(m, binp, timeout), rest)):
                out[mid] = res
    return {m: out[m] for m in cands}


def _discover(binp, timeout, extra_candidates=(), max_workers=16, hints=()):
    """``(probes, wide)``: each candidate's probe, then its ``[1m]`` twin's.

    Candidates are the binary's own ids plus ``extra_candidates`` (the panel
    passes the Anthropic API's ids when a key happens to exist) plus the ids the
    CLI's picker hints name. All of them are guesses and all are validated: the
    HTTP API describes a different backend and lists ids this CLI rejects. Twins
    are probed only for ids that validated.
    """
    cands = [c for c in candidate_model_ids(binp) if c]
    extra = list(extra_candidates or ())
    extra += [h.get("value", "").replace("[1m]", "") for h in (hints or ())
              if not h.get("disabled")]
    for c in extra:
        c = str(c or "").strip()
        if c and _is_candidate(c) and c not in cands:
            cands.append(c)
    probes = _probe_many(cands, binp, timeout, max_workers)
    valid  = [m for m in cands if probes.get(m, ("",))[0] == "valid"]
    wide   = _probe_many(["%s[1m]" % m for m in valid], binp, timeout, max_workers)
    return probes, wide


def _with_wide(probes, wide=None):
    """``{id: label}`` for the valid ids, plus each ``[1m]`` twin whose label differs.

    ``[1m]`` is not a universal suffix -- ``claude-haiku-4-5[1m]`` is a 400 (the
    1M beta header is rejected) and ``claude-sonnet-5[1m]`` is accepted but
    resolves to plain "Sonnet 5", so offering it would just duplicate the base
    id. Comparing display names lets the CLI decide, with no table of which
    models support 1M.
    """
    displays = {m: d for m, (s, d) in (probes or {}).items() if s == "valid"}
    for twin, (status, label) in (wide or {}).items():
        base = twin[:-len("[1m]")]
        if status == "valid" and label and label != displays.get(base):
            displays[twin] = label
    return displays


def list_models(bin_path=None, timeout=90.0, extra_candidates=(),
                max_workers=16):
    """``(names, current_label, displays)`` -- the FLAT form of the listing.

    ``list_model_rows`` is what the panel renders; this keeps the older flat
    contract. Every entry is an EXPLICIT versioned id -- no floating aliases --
    EXCEPT on the last-resort fallback below, which labels what it offers.
    Discovery and validation are ``_discover``'s; twins follow ``_with_wide``.
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

    try:
        probes, wide = _discover(binp, timeout, extra_candidates, max_workers)
    except Exception:
        return _alias_fallback()
    displays = _with_wide(probes, wide)
    if not displays:
        return _alias_fallback()
    keep_wide = [m for m in displays if m.endswith("[1m]")]
    bases     = [m for m in displays if not m.endswith("[1m]")]
    return order_models(bases, keep_wide), current, displays


# ---------------------------------------------------------------------------
# Rows -- what the dropdown shows, and what each entry means.
# ---------------------------------------------------------------------------
# An id alone says too little ("claude-opus-5[1m]"), and an alias says nothing
# about which model runs ("opus" is Opus 5 on 2.1.273 and Opus 5.5 once the CLI
# updates). So every pickable row is a PINNED id carrying its display name, and
# each alias rides as a chip on the row it resolves to today. Nothing below
# names a model or a family: all of it is read from the installed CLI.
_HINT_VER_RE = re.compile(r"(\d+(?:\.\d+)+)\+")


def resolve_aliases(aliases, bin_path=None, timeout=60.0, max_workers=16):
    """``{alias: display_name}`` for the aliases the CLI resolves. Local, keyless.

    ``/model opus`` answers "Set model to `Opus 5` ..." from the CLI's own table
    under ``--bare`` in about a second, no login needed; the name is what places
    the alias's chip. An alias that names no single model ("opusplan": Opus in
    plan mode, else Sonnet) still resolves -- it just matches no row.
    """
    binp    = _resolve(bin_path)
    aliases = [a for a in (aliases or ()) if a]
    if not binp or not aliases:
        return {}

    def _label(reply):
        m = _SET_RE.search(reply or "")
        return clean_label(m.group(1)) if m else ""

    # One batched process (see _GUARD_MODEL), else one process per alias. Both
    # retried without --bare for a CLI that predates it, as alias_listing is.
    feed = _feed(["/model %s" % a for a in aliases])
    for bare in (["--bare"], []):
        flags = bare + ["--model", _GUARD_MODEL]
        out = _run_cli(binp, _FEED_ARGS, flags, timeout + 2.0 * len(aliases),
                       feed=feed)
        if bare and re.search(r"unknown option\W+--bare", out or ""):
            continue  # per alias would refuse the same flag, once each
        replies = _batch_replies(out)
        if len(replies) == len(aliases):
            return {a: lab for a, lab in zip(aliases, map(_label, replies)) if lab}
        import concurrent.futures as _cf

        with _cf.ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as ex:
            outs = list(ex.map(lambda a: _run_cli(
                binp, ["-p", "/model %s" % a], flags, timeout), aliases))
        if all(o and _BADFLAG_RE.search(o) for o in outs):
            continue
        return {a: lab for a, lab in zip(aliases, map(_label, outs)) if lab}
    return {}


def cli_version(bin_path=None, timeout=30.0):
    """``'2.1.273'`` from ``claude --version``; ``''`` when it cannot be read.

    Keys the saved rows: a newer CLI runs models the old one could not (Opus 5.5
    needs 2.1.280), so an update must force a full re-check.
    """
    binp = _resolve(bin_path)
    if not binp:
        return ""
    m = _VERSION_RE.search(_run_cli(binp, ["--version"], (), timeout) or "")
    return m.group(1) if m else ""


def _claude_json_paths():
    out     = []
    cfg_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg_dir:
        out.append(os.path.join(cfg_dir, ".claude.json"))
    out.append(os.path.join(os.path.expanduser("~"), ".claude.json"))
    return out


def read_server_hints(path=None):
    """The CLI's own cached model-picker extras -- ``[]`` whenever unavailable.

    ``claude`` keeps the extra entries its /model picker shows in
    ``additionalModelOptionsCache`` inside ``.claude.json``. On 2.1.273 that is
    an enabled ``claude-fable-5-1[1m]`` and a DISABLED "Opus 5.5 (disabled)" /
    "Update to 2.1.280+ to use Opus 5.5" -- the only place a model NEWER than
    the installed CLI is named at all, since its binary has never heard of it.
    Internal and undocumented, so READ-ONLY and advisory: any surprise yields
    ``[]`` and the dropdown simply shows no greyed row.
    """
    for p in ([path] if path else _claude_json_paths()):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        raw = data.get("additionalModelOptionsCache") if isinstance(data, dict) else None
        out = []
        for h in (raw if isinstance(raw, list) else ()):
            if isinstance(h, dict) and (h.get("value") or h.get("label")):
                out.append({"value": str(h.get("value") or ""),
                            "label":       str(h.get("label") or ""),
                            "description": str(h.get("description") or ""),
                            "disabled": bool(h.get("disabled"))})
        return out
    return []


def _row(mid, label, status="valid", note="", min_version="", family=None):
    return {"id": mid, "label": label,
            "family": family_of(mid) if family is None else family,
            "aliases": [], "status": status, "note": note,
            "min_version": min_version}


def _version_key(text):
    return tuple(int(p) for p in re.findall(r"\d+", text or ""))


def link_rows(rows, alias_labels=None, current="", aliases=(), hints=(),
              cli_version="", error="", also_valid=None, refused=None,
              partial=False):
    """Chips, the default row, greyed hint rows and family order over ``rows``. Pure.

    Split from ``build_rows`` because these facts are LOCAL (1-3 s, no login)
    and change without a CLI update -- settings.json moves the default, the
    server refreshes its hints -- so the panel re-links saved rows at launch
    instead of re-validating every id. Returns the payload ``build_rows``
    documents.
    """
    alias_labels = dict(alias_labels or {})
    current      = clean_label(current)
    rows         = [dict(r, aliases=[]) for r in (rows or ()) if r.get("status") != "hint"]
    valid_labels = {r["label"] for r in rows if r.get("status") == "valid"}

    # The CLI's "update to use X" notices. One that matches a too_old row (same
    # family, same minimum version) names that row; the rest become rows of
    # their own, since the id they would run is unknown to this CLI. A notice
    # this CLI already satisfies is stale -- the CLI rewrites its cache only
    # later -- and is dropped.
    for h in hints or ():
        if not h.get("disabled"):
            continue
        label  = clean_label(h.get("label"))
        family = (label.split() or [""])[0].lower()
        m      = _HINT_VER_RE.search(h.get("description") or "")
        need   = m.group(1) if m else ""
        if label in valid_labels or (
                need and cli_version
                and _version_key(need) <= _version_key(cli_version)):
            continue
        twin = next((r for r in rows if r["status"] == "too_old"
                     and r["family"] == family and r["min_version"] == need), None)
        if twin is not None:
            twin["label"] = label
        else:
            rows.append(_row("", label, "hint", h.get("description") or "", need,
                             family))

    by_label = {}
    for r in rows:
        if r["status"] == "valid":
            by_label.setdefault(r["label"], r)
    # What a blank box runs is the "Current model:" line, which already carries
    # any settings.json / ANTHROPIC_MODEL override; "/model default" names the
    # built-in default and ignores them. "default" is never pinned: it is the
    # blank row, so its chip marks whatever the blank box runs.
    # Only an UNKNOWN current falls back to it: a current naming no row (an
    # "opusplan" setting, an unlisted gateway id) means the blank box runs
    # something that is not a row, so no row is the default.
    default = (by_label.get(current) if current
               else by_label.get(alias_labels.get("default", "")))
    alias_map = {}
    for a in aliases or list(alias_labels):
        r = default if a == "default" else by_label.get(alias_labels.get(a, ""))
        if r is not None:
            r["aliases"].append(a)
            if a != "default":
                alias_map[a] = r["id"]

    # Family blocks: the default's first, then the order /model lists them in,
    # then any family it does not name (a new one sorts in, not out).
    families = [default["family"]] if default else []
    for f in [a.replace("[1m]", "") for a in (aliases or ())] + [r["family"] for r in rows]:
        if f not in families and any(r["family"] == f for r in rows):
            families.append(f)
    ordered = []
    for f in families:
        block = [r for r in rows if r["family"] == f]
        ordered += [r for r in block if r["status"] != "valid"]
        ordered += [r for r in block if r["status"] == "valid"]
    return {
        "rows":         ordered,
        "current":      current,
        "default_id":   default["id"] if default else "",
        "alias_map":    alias_map,
        "alias_labels": alias_labels,
        "cli_version":  cli_version or "",
        "error":        error or "",
        "fallback":     not any(r["status"] == "valid" for r in ordered),
        "also_valid":   dict(also_valid or {}),
        "refused":      dict(refused or {}),
        "aliases":      [a for a in (aliases or ()) if a],
        "partial":      bool(partial),
    }


def build_rows(probes, wide=None, alias_labels=None, current="", aliases=(),
               hints=(), cli_version="", error=""):
    """The Claude CLI dropdown as data -- every row it shows and why. Pure.

    ``probes``/``wide`` come from ``_discover``, ``alias_labels`` from
    ``resolve_aliases``, ``hints`` from ``read_server_hints``. Returns a
    JSON-safe dict (the panel saves it to prefs as is):

    rows
        ``{"id", "label", "family", "aliases", "status", "note",
        "min_version"}`` in display order: family blocks (the default's family
        first, then the order ``/model`` lists them), newest first in each.
        ``status`` is 'valid' (pickable), 'too_old' (greyed: a real id this CLI
        is too old to run) or 'hint' (greyed: the CLI's own "update to use X"
        notice, which names no id). ``aliases`` are the chips.
    default_id
        The row a blank box runs ('' when none matches).
    alias_map
        ``{alias: id}`` for every alias that lands on a row, except "default",
        which is the blank row itself.
    also_valid
        ``{id: label}`` for ids that validated but are not listed -- a build
        stamp or a ``[1m]`` twin naming the same model as a listed row. Typed,
        they still run what their label says.
    refused
        ``{id: why}`` for candidates this CLI answered but will not run: 'not
        found', 'no access', or the CLI's reason.
    aliases
        The alias names ``/model`` listed, resolved or not.
    partial
        True when the check did not finish -- a probe got no answer or could
        not log in, or a listed alias did not resolve. Rows from a partial
        check are shown but not trusted for a week.
    current, alias_labels, cli_version, error
        What a blank box runs (clean name), the resolved aliases, the CLI
        version, and why nothing validated (when nothing did).
    fallback
        True when no row is pickable.
    """
    labels = _with_wide(probes, wide)
    also_valid = {t: d for t, (s, d) in (wide or {}).items()
                  if s == "valid" and d and t not in labels}
    # A build stamp naming the same model as its root offers no real choice:
    # claude-haiku-4-5-20251001 IS "Haiku 4.5", listed once as claude-haiku-4-5.
    for mid in list(labels):
        m = _DATED_RE.match(mid)
        if m and labels.get(m.group(1)) == labels[mid]:
            also_valid[mid] = labels.pop(mid)
    order = order_models([m for m in labels if not m.endswith("[1m]")],
                         [m for m in labels if m.endswith("[1m]")])
    # order_models seats a twin only after a listed root; the twin of a parked
    # build stamp has no seat but still runs.
    listed = set(order)
    also_valid.update({m: d for m, d in labels.items() if m not in listed})
    rows     = [_row(m, labels[m]) for m in order]
    answered = list((probes or {}).items()) + list((wide or {}).items())
    partial = any(s == "error" and (d == _NO_ANSWER or _NOAUTH_RE.search(d or ""))
                  for _m, (s, d) in answered)
    partial = partial or any(a not in (alias_labels or {}) for a in aliases or ())
    refused = {m: {"unknown": "not found", "restricted": "no access"}.get(s, d or "rejected")
               for m, (s, d) in (probes or {}).items()
               if s in ("unknown", "restricted")
               or (s == "error" and d != _NO_ANSWER and not _NOAUTH_RE.search(d or ""))}
    too_old = sorted(((m, d) for m, (s, d) in (probes or {}).items()
                      if s == "too_old"),
                     key=lambda kv: _nat_key(kv[0]), reverse=True)
    for mid, need in too_old:
        note = ("needs Claude Code %s+" % need) if need else "needs a newer Claude Code"
        rows.append(_row(mid, mid, "too_old", note, need))
    return link_rows(rows, alias_labels, current, aliases, hints, cli_version,
                     error, also_valid, refused, partial)


def list_model_rows(bin_path=None, timeout=90.0, extra_candidates=(),
                    max_workers=16):
    """The full Claude CLI listing as ``build_rows`` data. Worker thread only.

    Local and free: the /model listing, the CLI version, the picker hints and
    the alias names (1-3 s). Then the one networked step: every candidate id
    and ``[1m]`` twin gets the CLI's one-token check with the login (~50 on
    2.1.273, 25-40 s; see ``_discover``).
    """
    binp = _resolve(bin_path)
    if not binp:
        return build_rows({}, error="`claude` was not found on PATH")
    aliases, current = alias_listing(binp, timeout)
    hints = read_server_hints()
    try:
        probes, wide = _discover(binp, timeout, extra_candidates, max_workers,
                                 hints)
        error = ""
    except Exception as exc:
        probes, wide, error = {}, {}, "%s: %s" % (type(exc).__name__, exc)
    if not error and not any(s == "valid" for s, _d in probes.values()):
        error = next((d for s, d in probes.values() if s == "error" and d),
                     "no model id validated" if probes else
                     "no model ids found in the installed CLI")
    return build_rows(probes, wide,
                      resolve_aliases(aliases, binp, timeout, max_workers),
                      current, aliases, hints, cli_version(binp), error)


def relink_saved_rows(saved, bin_path=None, timeout=60.0, max_workers=16):
    """Saved rows with their LOCAL facts refreshed; no id is re-validated.

    What a blank box runs, where each alias points and the picker hints can
    all change without a CLI update, and all three answer locally in 1-3 s. The
    pinned rows only change with the CLI itself, which the caller checks first
    (``config.rows_need_full_check``).
    """
    saved = dict(saved or {})
    binp  = _resolve(bin_path)
    if not binp:
        return saved
    aliases, current = alias_listing(binp, timeout)
    labels = resolve_aliases(aliases, binp, timeout, max_workers)
    if not labels:
        # A slow or failed lookup this time: keep the last good chips rather
        # than save a payload that has none.
        labels  = saved.get("alias_labels") or {}
        aliases = aliases or list(labels)
    out = link_rows(saved.get("rows"), labels, current or saved.get("current", ""),
                    aliases, read_server_hints(), saved.get("cli_version", ""),
                    "", saved.get("also_valid"), saved.get("refused"),
                    saved.get("partial", False))
    out["fetched"] = saved.get("fetched", 0)
    return out


class ClaudeCliClient(QObject):
    assistantText  = Signal(str)
    toolStarted    = Signal(str)
    toolFinished   = Signal(str)
    turnFinished   = Signal()
    notice         = Signal(str)
    thinking       = Signal(str)                      # thinking trace (when effort > off)
    retryScheduled = Signal(int, int, int, int, str)  # interface compat (unused)
    tokensUsed     = Signal(int)
    errorOccurred  = Signal(str)
    busyChanged    = Signal(bool)
    modelRan       = Signal(str)                      # model id that answered the turn

    def __init__(self, ctx_provider=None, parent=None):
        super().__init__(parent)
        self._ctx_provider = ctx_provider
        self._busy         = False
        self._cancel       = threading.Event()
        self._proc         = None
        self._session_id   = str(uuid.uuid4())
        self._started      = False  # session created? -> use --resume next time
        self._emitted_text = False
        self._answer_text  = ""     # accumulated reply -> payload extraction
        self._ctx          = None   # ToolContext captured per turn (GUI thread)
        self._node_name    = None   # active node captured per turn (GUI thread)
        self._auth_failed  = False  # set from the stream; reset every turn
        self._ran_model    = ""     # model that answered, from the stream
        self._too_old      = None   # min CLI version the model needs, if refused

    def reset(self):
        self._session_id = str(uuid.uuid4())
        self._started    = False

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
        self._ctx       = self._ctx_provider() if callable(self._ctx_provider) else None
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
        self._answer_text  = ""
        self._auth_failed  = False
        self._ran_model    = ""
        self._too_old      = None
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
                elif self._too_old is not None:
                    # The CLI's own sentence is already in chat; the stderr
                    # tag ("[claude-code:unrecognized_model] {...}") says less.
                    self.errorOccurred.emit(too_old_hint(self._too_old))
                else:
                    self.errorOccurred.emit(
                        "claude exited %s%s" % (self._proc.returncode,
                                                (": " + err) if err else ""))
            else:
                if self._ran_model:
                    self.modelRan.emit(self._ran_model)
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
        et  = ev.get("type")
        msg = (ev.get("message", {}) or {}) if et == "assistant" else {}
        # A refusal arrives as a synthetic assistant message plus an error
        # result; either may carry the "version X or newer" sentence.
        if ev.get("error") or ev.get("is_error") or msg.get("model") == "<synthetic>":
            ver = version_too_old(line)
            if ver is not None:
                self._too_old = ver
        if et == "assistant":
            # Output nested under a tool use (parent_tool_use_id) is interim
            # text, NOT the main answer: only the top-level agent emits the
            # payload. Kept although sub-agents are denied -- it is what makes
            # any nested chatter harmless.
            is_sub = ev.get("parent_tool_use_id") is not None
            # The model that ANSWERED. Not the init event's "model": for a
            # full id that echoes the request unchecked, even one that never
            # runs. A refusal is tagged "<synthetic>".
            ran = msg.get("model")
            if not is_sub and ran and ran != "<synthetic>":
                self._ran_model = str(ran)
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
            u   = msg.get("usage") or {}
            tot = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
            if tot:
                self.tokensUsed.emit(int(tot))
        elif et == "result":
            # Only surface the aggregated result if no streamed text appeared.
            r = ev.get("result")
            if not self._emitted_text and isinstance(r, str) and r.strip():
                self._append_answer(r)
            if not self._ran_model and not ev.get("is_error"):
                self._ran_model = main_model(ev.get("modelUsage"))
