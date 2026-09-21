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
import re

from mpynode.ui.llm import config as _cfg
from mpynode.ui.llm.cli_base import BaseCliClient

_BIN = os.environ.get("GEMINI_BIN", "gemini")


def _model():
    return _cfg.get_model("gemini_cli")


# ---------------------------------------------------------------------------
# Model listing -- local, keyless, and WITHOUT an API call.
#
# The Gemini CLI has no `models list` command and `-m` takes a free string: the
# binary validates it against a table compiled into its own bundle. So the table
# is read where it lives instead of being baked in here (a hardcoded roster goes
# stale the day a family ships) and instead of demanding a Gemini API key, which
# is a DIFFERENT backend -- the CLI signs in with the machine's own Google login
# and its accepted ids are its own.

#: ``var DEFAULT_GEMINI_MODEL = "<family>-<version>";`` -- the CLI's own model
#: constants. No id is spelled out anywhere in this module, deliberately: the
#: roster comes from the installed CLI, so there is nothing here to go stale.
_CONST_RE = re.compile(
    r'var\s+([A-Za-z_$][\w$]*)\s*=\s*"((?:gemini|gemma)-[A-Za-z0-9._-]+)"')
#: the membership table those constants feed, e.g.
#: ``var VALID_GEMINI_MODELS = /* @__PURE__ */ new Set([ ... ]);``
_VALID_SET_RE = re.compile(
    r"VALID_[A-Z_]*MODELS\s*=\s*(?:/\*.*?\*/\s*)?new\s+Set\(\s*\[(.*?)\]",
    re.DOTALL)
#: entries inside that table: a constant name, or a quoted id.
_MEMBER_RE = re.compile(r'"([^"]+)"|([A-Za-z_$][\w$]*)')
#: ``var GEMINI_MODEL_ALIAS_AUTO = "auto";`` -- the CLI's own shorthands. These
#: ARE offered (unlike the Claude CLI's, which are suppressed in favour of
#: pinned ids): "auto" is the CLI's headline behaviour -- it picks the model per
#: task, including the thinking-capable one -- and there is no id that means it.
_ALIAS_RE = re.compile(
    r'var\s+[A-Za-z_$][\w$]*ALIAS[\w$]*\s*=\s*"([a-z][a-z0-9-]{0,24})"')
#: an id worth offering: a family and a version, not a sentinel ("none") and not
#: an embedding model (it cannot answer a prompt).
_ID_OK = re.compile(r"^(?:gemini|gemma)-\d[A-Za-z0-9._-]*$")

_SCAN_CHUNK = 8 << 20
#: the table spans a few hundred bytes; this overlap keeps it whole across reads.
_SCAN_OVERLAP   = 64 << 10
_MAX_SCAN_FILES = 6


def _resolve(bin_path=None):
    from mpynode.native.toolchain import toolchain

    try:
        return toolchain.find_executable(bin_path or _BIN)
    except Exception:
        return None


def _package_roots(binp):
    """Directories that may hold the CLI's bundled JS, best guess first.

    npm installs the launcher as a SHIM, so the bundle is never beside it: on
    Windows ``gemini.cmd`` names its entry point in plain text, and on
    unix-likes the launcher is a symlink into the package (realpath lands
    inside it). Both are followed here, plus the two standard global layouts,
    because a wrong guess costs nothing and a missed one empties the dropdown.
    """
    if not binp:
        return []
    out, seen = [], set()

    def _add(path):
        if path and os.path.isdir(path) and path not in seen:
            seen.add(path)
            out.append(path)

    real = os.path.realpath(binp)
    here = os.path.dirname(real)
    _add(here)                                  # symlinked unix install
    # The shim text names the real entry: "...\@google\gemini-cli\bundle\gemini.js"
    try:
        if os.path.getsize(real) <= (256 << 10):
            with open(real, "r", encoding="utf-8", errors="replace") as fh:
                shim = fh.read()
            for m in re.finditer(r"[^\"'\s]*gemini-cli[^\"'\s]*\.[cm]?js", shim):
                frag = m.group(0).replace("%dp0%", here).replace("$basedir", here)
                _add(os.path.dirname(os.path.normpath(frag)))
    except Exception:
        pass
    pkg = os.path.join("node_modules", "@google", "gemini-cli")
    for base in (here, os.path.dirname(here)):
        _add(os.path.join(base, pkg))         # npm prefix (Windows)
        _add(os.path.join(base, "lib", pkg))  # npm prefix (unix)
    return out


def bundle_files(binp):
    """JS files from the installed CLI that may carry the model table.

    Largest first: the table lives in the big bundled chunk, and reading that
    one first usually means reading exactly one file.
    """
    found, seen = [], set()
    for root in _package_roots(binp):
        for d in (root, os.path.join(root, "bundle"), os.path.join(root, "dist")):
            try:
                names = os.listdir(d)
            except Exception:
                continue
            for n in names:
                p = os.path.join(d, n)
                if not n.endswith((".js", ".mjs", ".cjs")) or p in seen:
                    continue
                if not os.path.isfile(p):
                    continue
                seen.add(p)
                try:
                    found.append((os.path.getsize(p), p))
                except Exception:
                    continue
    # Every root pooled, then size order -- stopping at the first root that held
    # ANY .js would hand a stray shim script priority over the real bundle.
    found.sort(key=lambda sp: -sp[0])
    return [p for _, p in found[:_MAX_SCAN_FILES]]


def parse_model_table(text):
    """Model ids from one chunk of the CLI's bundled JS (pure -- unit-testable).

    Two structural reads, never a blind sweep for anything id-shaped: the bundle
    also carries test fixtures and truncated prefixes, and offering those would
    put ids in the dropdown that the CLI rejects.

    1. the membership table (``VALID_GEMINI_MODELS``), whose entries are the
       constant names below or literal ids -- this IS the CLI's own answer to
       "will you run this";
    2. failing that, the model constants themselves.
    """
    consts = {name: mid for name, mid in _CONST_RE.findall(text)}
    ids, seen = [], set()

    def _keep(mid):
        if mid and _ID_OK.match(mid) and "embedding" not in mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)

    m = _VALID_SET_RE.search(text)
    if m:
        for lit, name in _MEMBER_RE.findall(m.group(1)):
            _keep(lit or consts.get(name, ""))
    if not ids:
        for mid in consts.values():
            _keep(mid)
    return ids


def parse_model_aliases(text):
    """The CLI's shorthand model names (``auto``, ``pro``, ...), in source order.

    Read the same structural way as the ids, so a renamed or added alias is
    picked up from the installed CLI rather than from a list here.
    """
    out, seen = [], set()
    for alias in _ALIAS_RE.findall(text):
        if alias not in seen:
            seen.add(alias)
            out.append(alias)
    return out


_SERIES_RE = re.compile(r"^(?:gemini|gemma)-(\d+)(?:\.(\d+))?")
#: pro before flash before flash-lite, the order the CLI's own help presents.
_FAMILY_ORDER = ("pro", "flash-lite", "flash")


def order_models(ids):
    """Newest first, pro before flash -- the order the dropdown shows.

    Sorted rather than left in bundle order so a restored prefs cache renders
    exactly like a fresh read (the Claude CLI list does the same).
    """
    def key(mid):
        m     = _SERIES_RE.match(mid)
        major = int(m.group(1)) if m else 0
        minor = int(m.group(2)) if (m and m.group(2)) else 0
        fam   = next((i for i, f in enumerate(_FAMILY_ORDER) if f in mid),
                     len(_FAMILY_ORDER))
        # gemma is a local side-branch: keep it under the gemini families.
        return (mid.startswith("gemma"), -major, -minor, fam, mid)

    return sorted(dict.fromkeys(ids), key=key)


def list_models(bin_path=None):
    """Model ids the INSTALLED Gemini CLI accepts. ``[]`` if it can't be read.

    No API key and no network: the answer comes from the binary on this machine,
    so it matches what ``gemini -m <id>`` will actually run.
    """
    for path in bundle_files(_resolve(bin_path)):
        ids, aliases = [], []
        try:
            with open(path, "rb") as fh:
                tail = b""
                while True:
                    chunk = fh.read(_SCAN_CHUNK)
                    if not chunk:
                        break
                    text     = (tail + chunk).decode("utf-8", "replace")
                    ids     += parse_model_table(text)
                    aliases += parse_model_aliases(text)
                    tail     = chunk[-_SCAN_OVERLAP:]
        except Exception:
            continue
        if ids:
            # Aliases lead: `auto` is how the CLI is meant to be driven (it
            # picks per task), and a pinned id is the deliberate override
            # underneath it.
            picked = order_models(ids)
            return list(dict.fromkeys(aliases)) + [m for m in picked
                                                   if m not in set(aliases)]
    return []


#: The prompt travels on STDIN, never in argv, and the tail rides `-p`. Both
#: live in llm.config because the compile porter builds the same command for
#: the same reasons -- see GEMINI_PROMPT_TAIL there for the full why.
PROMPT_TAIL = _cfg.GEMINI_PROMPT_TAIL


def build_cmd(bin_path, prompt=None, model=None, resume=None):
    """argv for a non-interactive Gemini CLI run (pure -- unit-testable).

    ``prompt`` is the SHORT tail only (default PROMPT_TAIL); the payload goes to
    ``GeminiCliClient._stdin_payload``. ``--skip-trust`` is paired with
    ``_cwd()`` below, which points the agent at a scratch directory instead of
    the user's project, so trusting the workspace grants it a sandbox rather
    than their files.
    """
    cmd = _cfg.gemini_cli_argv(bin_path, model=model, stream_json=True)
    if prompt is not None and prompt != PROMPT_TAIL:
        cmd[cmd.index("-p") + 1] = prompt
    if resume:
        cmd += ["-r", resume]
    return cmd


class GeminiCliClient(BaseCliClient):
    PROVIDER = "gemini_cli"
    LABEL    = "Gemini CLI"

    #: scratch working directory for the agent (see _cwd), made on first use.
    _workdir = None

    def _bin(self):
        return _BIN

    def _build_cmd(self, prompt, images):
        if images:
            self.notice.emit("(images aren't supported by the Gemini CLI provider)")
        # argv carries only the tail -- see PROMPT_TAIL / _stdin_payload.
        return build_cmd(_BIN, model=_model())

    def _stdin_payload(self, prompt, images):
        """The prompt itself, written to the CLI's stdin.

        The CLI concatenates stdin with ``-p``, so the payload arrives first and
        the tail reads as the instruction that follows it. Keeping it out of
        argv is what stops a long node payload hitting the Windows command-line
        limit (see PROMPT_TAIL).
        """
        return (prompt or "") + "\n"

    def _cwd(self):
        """A scratch directory for the agent to run in.

        The answer we want is a JSON node payload, not file work -- but the run
        is launched with tools auto-approved and the workspace trusted (see
        build_cmd), so WHERE it starts matters: inheriting Maya's working
        directory would point an auto-approving agent at the user's project.
        A per-session temp dir gives it somewhere harmless to look instead, and
        keeps any GEMINI.md / settings it picks up out of the picture.
        """
        if self._workdir is None or not os.path.isdir(self._workdir):
            import tempfile

            self._workdir = tempfile.mkdtemp(prefix="mpynode_gemini_")
        return self._workdir

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
