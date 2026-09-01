"""Assemble ported single-node MPyNode .cpp file(s) into ONE compiled plugin,
laid out as a CLEAN, self-documenting, re-buildable folder.

Folder shape: ONLY the importable ``<plugin>.bundle`` sits at the top of
``out_dir`` (the controller adds any ``*_commands.py`` companion plugins beside
it); everything the compiler produced to MAKE it lives under ``out_dir/build/``
-- ``build.sh`` / ``build.bat`` / ``README.txt`` directly in ``build/``, and all
C++ source (``<node>.cpp`` / ``plugin_main.cpp`` / ``shared_helpers.cpp``) nested
in ``build/source/``. The build scripts read their inputs from ``$HERE/source/``
and write the rebuilt bundle back up to ``$HERE/../`` so a hand rebuild lands it
exactly where the programmatic build did. See :func:`build_dir_for` /
:func:`source_dir_for`.

Output source (what a compile produces, under ``build/source/``):
  * **Single-node plugin (the common case).** ONE self-contained ``<node>.cpp``
    -- the node's own ported, parity-verified source with the registry MTypeId
    baked in and its own ``initializePlugin``/``uninitializePlugin`` kept intact.
    No namespace wrap, no register hooks, no ``plugin_main.cpp``: this is "THE
    file you edit". It links directly into ``<plugin>.bundle``.
  * **Multi-node plugin.** ``<node>.cpp`` per node (each namespaced so symbols
    can't collide + its register hook) PLUS a generated ``plugin_main.cpp`` that
    registers them all, optionally ``shared_helpers.cpp``; all link into one
    ``<plugin>.bundle``.
  * **Always:** ``build.sh`` AND ``build.bat`` (rebuild on macOS/Linux OR
    Windows by re-running the script) and a ``README.txt`` explaining what to
    edit and how to rebuild. Object files are removed after a successful link so
    only source + scripts + the bundle remain.

Transforms:
  * **Global per-user MTypeIds** via :mod:`typeid_registry` -- collision-free,
    stable, multi-plugin-safe (fixes the audit's id-collision bugs too).
  * The multi-node fragment transform re-homes class references via
    ``using namespace`` and swaps plugin entry points for ``register_*`` hooks;
    it is general across every MPx base (compute / deformer / iksolver / locator
    / transform / geo) because it reuses each file's own registration body.
  * **Strict by default, opt-in best-effort.** A node that fails to compile
    aborts the bundle (strict) or is dropped with a loud report
    (best-effort). A per-node status report is always returned.

The transform operates on POST-PORT source text (the AI-filled .cpp), so it is
deliberately text-level surgery.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from mpynode.native.toolchain import toolchain
from mpynode.native.toolchain import typeid_registry
from .errors import UnsupportedSpec


_MAYA_DEFAULT = toolchain.preferred_maya_dir()

# Output-folder layout (SINGLE SOURCE OF TRUTH -- compile_controller and the UI
# import these). A compile leaves ONLY the importable ``<plugin>.bundle`` (and
# any ``*_commands.py`` companions) at the TOP of ``out_dir``; build scripts,
# README and manifest live in ``out_dir/build/``, C++ source one level deeper in
# ``out_dir/build/source/``. "Here is the plugin, here is how it was made".
BUILD_DIRNAME = "build"
SOURCE_DIRNAME = "source"
STAGES_DIRNAME = "stages"


def build_dir_for(out_dir: str) -> str:
    """``out_dir/build`` -- holds build scripts, README, manifest, and source/."""
    return os.path.join(out_dir, BUILD_DIRNAME)


def source_dir_for(out_dir: str) -> str:
    """``out_dir/build/source`` -- holds every ``.cpp`` (node fragments,
    plugin_main, shared_helpers)."""
    return os.path.join(out_dir, BUILD_DIRNAME, SOURCE_DIRNAME)


def stages_dir_for(out_dir: str) -> str:
    """``out_dir/build/stages`` -- the DURABLE per-node pipeline history."""
    return os.path.join(out_dir, BUILD_DIRNAME, STAGES_DIRNAME)


def stage_dir_for(out_dir: str, type_name: str) -> str:
    """``out_dir/build/stages/<Type>`` -- one node's whole story.

    Holds ``1_transpiled.cpp`` / ``2_assisted.cpp`` / ``3_optimized/NN_<slug>.cpp``
    plus that node's ``rounds.json`` and ``REPORT.md``. The digit prefixes exist
    so the stages sort in pipeline order ("assisted" would otherwise sort before
    "transpiled").

    Distinct from ``build/<Type>/`` (per-node port SCRATCH: object files, an
    intermediate .bundle, verify_in_maya.py) which is swept after a successful
    build. Nothing here is ever swept: it is source and reports, which is the
    only thing worth keeping once the lint is gone.
    """
    return os.path.join(stages_dir_for(out_dir), type_name)

# Superset of Maya libs any generated node might need; linking unused ones is
# harmless and avoids per-node link-flag bookkeeping.
_LINK_LIBS = [
    "OpenMaya", "OpenMayaAnim", "OpenMayaUI", "OpenMayaRender", "Foundation",
]
_CXXFLAGS = [
    # -ffp-contract=off is MANDATORY for byte-parity (clang defaults contract=on
    # -> FMA -> ~1 ULP drift vs numpy); -O3 is measured faster and IEEE-correct
    # with contraction off. Never -ffast-math.
    "-std=c++17", "-O3", "-ffp-contract=off", "-arch", "arm64",
    "-D", "OSMac_", "-D", "REQUIRE_IOSTREAM", "-D", "_BOOL",
    "-Wno-nontrivial-memcall",
]

# MFnPlugin.h (via MApiVersion.h) emits the exported plugin-version symbols
# ``MApiVersion[]`` / ``ADSK_PLUGIN_SIGNATURE[]`` in EVERY translation unit that
# includes it -- they must appear exactly ONCE per plugin. The node fragments
# include MFnPlugin.h (their register hooks take ``MFnPlugin&``), so they
# suppress these symbols; only ``plugin_main.cpp`` emits them.
_FRAG_DEFINES = ["-D", "MNoVersionString", "-D", "MNoPluginEntry"]

# Linux has no build-script generator: the emitted build.sh is the macOS recipe
# (clang++ / -D OSMac_ / -bundle / lipo), which cannot link a .so. Reported as a
# clear reason rather than letting the compiler fail cryptically.
_LINUX_UNSUPPORTED = (
    "native compile is not supported on Linux: the generated build script is "
    "the macOS recipe and nothing drives a g++/.so link (toolchain.py carries "
    "the flags; no caller reaches them). See docs/PORTING.md. Compile on "
    "macOS or Windows.")


# ---- C++ source surgery ---------------------------------------------------


def _extract_fn(text: str, fname: str) -> Optional[Tuple[int, int, str]]:
    """Find a top-level ``MStatus <fname>(MObject <x>) { ... }`` and return
    ``(start, end, body)`` where body is the text BETWEEN the outer braces.
    Brace-matched so nested ``{}`` are handled."""
    m = re.search(
        r"MStatus\s+%s\s*\(\s*MObject\s+\w+\s*\)\s*\{" % re.escape(fname), text
    )
    if not m:
        return None
    open_brace = m.end() - 1
    depth = 0
    for j in range(open_brace, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return (m.start(), j + 1, text[m.end():j])
    return None


# Scan ``registerCommand("name", ...)`` calls only in CODE context: the same
# substring inside a comment or a string literal is a false positive that would
# falsely fail strict assemble. A word-boundary check also keeps
# ``deregisterCommand`` uncounted (every command emits BOTH lines).
#
# regex-finditer-with-post-filter is unsafe here: a literal containing bare
# ``registerCommand(`` text matches as a "name" that consumes into the following
# real call. Hence a left-to-right scanner tracking comment/string/code state.
def _raw_string_span(text: str, i: int, n: int):
    """If a C++11 raw string literal starts at ``i`` -- ``R"delim( ... )delim"``,
    optionally with a ``u8``/``u``/``U``/``L`` encoding prefix -- return the
    index just past its closing quote; else ``None``.

    Raw strings carry unescaped ``"`` in the body, so they MUST be treated as
    one opaque token or the ``"..."`` scanner desyncs (leaking a ghost
    ``registerCommand`` from the body, or swallowing a following real call).
    The introducer must sit on a word boundary so an identifier ending in
    ``R``/``L``/``u``/``U`` (e.g. ``fooR"x"``) is NOT misread as a raw string.
    Unterminated -> consume to EOF (caller never raises)."""
    start = i
    for pre in ("u8", "u", "U", "L"):  # u8 before u (longest prefix first)
        if text.startswith(pre + 'R"', i):
            i += len(pre)
            break
    if not text.startswith('R"', i):
        return None
    prev = text[start - 1] if start > 0 else ""
    if prev.isalnum() or prev == "_":  # part of a longer identifier, not raw
        return None
    j = i + 2  # past the R"
    dstart = j
    while j < n and text[j] != '(':  # delimiter: no (, ), backslash, whitespace
        if text[j] in '() \t\r\n\\':
            return None  # not a valid raw-string delimiter -> not a raw string
        j += 1
    if j >= n:
        return None
    closer = ')' + text[dstart:j] + '"'
    end = text.find(closer, j + 1)
    return n if end == -1 else end + len(closer)


def command_names_in(text: str) -> List[str]:
    """Every command name passed to ``registerCommand("name", ...)`` in CODE
    context (not inside ``//`` ``/* */`` comments, ``"..."``/``'...'`` literals,
    or ``R"(...)"`` raw-string literals; and not the ``registerCommand``
    substring of ``deregisterCommand``), in source order. Single left-to-right
    scan; consumes-to-EOF on any unterminated comment/literal so it never raises
    on a malformed fragment."""
    text = text or ""
    names: List[str] = []
    i, n = 0, len(text)
    _ws = " \t\r\n"
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '/':
            i += 2
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            i += 2
            while i < n and not (text[i] == '*' and i + 1 < n and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        if c in 'RLuU':  # possible C++11 raw string introducer (before plain ")
            raw_end = _raw_string_span(text, i, n)
            if raw_end is not None:
                i = raw_end
                continue
        if c == "'" or c == '"':
            q = c
            i += 1
            while i < n and text[i] != q:
                i += 2 if text[i] == '\\' else 1
            i += 1
            continue
        if c == 'r' and text.startswith("registerCommand", i):
            prev = text[i - 1] if i > 0 else ""
            if not (prev.isalnum() or prev == "_"):  # word boundary -> not deregisterCommand
                j = i + len("registerCommand")
                while j < n and text[j] in _ws:
                    j += 1
                if j < n and text[j] == '(':
                    j += 1
                    while j < n and text[j] in _ws:
                        j += 1
                    if j < n and text[j] == '"':
                        j += 1
                        start = j
                        while j < n and text[j] != '"':
                            j += 2 if text[j] == '\\' else 1
                        names.append(text[start:min(j, n)])
                        i = j + 1
                        continue
        i += 1
    return names


def find_command_clashes(named_sources) -> Dict[str, List[str]]:
    """Detect companion-command NAME collisions across a plugin's nodes.

    ``named_sources`` is ``[(type_name, cpp_text), ...]``. Returns
    ``{command_name: [type_name, ...]}`` for every command registered more than
    once total (across nodes OR twice within one node). Maya's command namespace
    is a single global string space, so any such duplicate fails the 2nd
    ``registerCommand`` at LOAD -- the bundler rejects it before link instead."""
    owners: Dict[str, List[str]] = {}
    counts: Dict[str, int] = {}
    for type_name, text in named_sources:
        for cmd in command_names_in(text):
            counts[cmd] = counts.get(cmd, 0) + 1
            owners.setdefault(cmd, []).append(type_name)
    return {c: owners[c] for c, k in counts.items() if k > 1}


def _make_hook(body: str, new_name: str, ns: str) -> str:
    """Turn an ``initializePlugin``/``uninitializePlugin`` body into a
    ``register_*``/``deregister_*`` hook taking ``MFnPlugin&``. Drops the
    in-body ``MFnPlugin <var>(...)`` construction (the plugin is now a param)
    and re-homes class references with ``using namespace <ns>;``."""
    var = "plugin"
    kept: List[str] = []
    for ln in body.splitlines():
        mm = re.search(r"MFnPlugin\s+(\w+)\s*\(", ln)
        if mm:
            var = mm.group(1)
            continue  # drop the construction line
        kept.append(ln)
    inner = "\n".join(kept).strip("\n")
    return (
        "MStatus %s(MFnPlugin& %s) {\n"
        "    using namespace %s;\n"
        "%s\n"
        "}" % (new_name, var, ns, inner)
    )


def _ns_for(node_name: str) -> str:
    return "nd_" + re.sub(r"\W", "_", node_name)


def _node_cpp_name(node_name: str) -> str:
    """The clean per-node source filename ``<node>.cpp`` (sanitized). Same base as
    the old ``frag_<ns>.cpp`` (``_ns_for(x)[3:]``) but without the ``frag_``
    prefix, so the file reads as "the source for node <node>"."""
    return re.sub(r"\W", "_", node_name) + ".cpp"


# Match a shared-helper marker COMMENT line (+ its newline) so a single-node
# self-contained .cpp can drop the markers while keeping the inline definition.
_SHARED_MARKER_LINE_RE = re.compile(
    r"^[ \t]*//[ \t]*=== MPYNODE SHARED HELPER (?:BEGIN|END)\b.*\n", re.M)


def _rewrite_typeids(text: str, type_name: str, id_for, main_cls: str) -> str:
    """Override every ``MTypeId <Class>::id(0x...)`` placeholder with a
    registry-assigned id (main class keyed by ``type_name``; a companion class --
    e.g. a transform's matrix -- keyed ``"<type_name>#<Class>"``)."""
    def _repl(m: "re.Match") -> str:
        cls = m.group(1)
        key = type_name if cls == main_cls else "%s#%s" % (type_name, cls)
        return "MTypeId %s::id(%s);" % (cls, id_for(key))
    return re.sub(r"MTypeId\s+(\w+)::id\(0x[0-9a-fA-F]+\);", _repl, text)


# A followed-import helper that codegen decides to share is emitted at file scope
# wrapped in these markers, so the bundler can hoist the body into ONE shared
# compilation unit and leave each node fragment with only a prototype + call:
#   // === MPYNODE SHARED HELPER BEGIN name=<sym> proto=<C++ prototype> ===
#   <full free-function definition>
#   // === MPYNODE SHARED HELPER END name=<sym> ===
_SHARED_BEGIN_RE = re.compile(
    r"//[ \t]*=== MPYNODE SHARED HELPER BEGIN name=(?P<name>\S+) "
    r"proto=(?P<proto>.+?) ===[ \t]*\n"
)
_SHARED_END_TMPL = "// === MPYNODE SHARED HELPER END name=%s ==="


def _extract_shared_helpers(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Pull every marked shared-helper block out of ``text``.

    Returns ``(text_without_blocks, blocks)`` where each block is
    ``{"name", "proto", "code"}`` (``code`` = the bare function definition, no
    markers). The blocks are removed from ``text`` so the per-node fragment keeps
    only the call site; the caller injects ``proto;`` declarations at global
    scope and hands ``blocks`` to :func:`assemble` for the shared unit. A node
    .cpp with no markers is returned unchanged with ``blocks == []`` (additive:
    the whole feature is inert unless codegen emitted a block)."""
    blocks: List[Dict[str, str]] = []
    out = []
    pos = 0
    while True:
        m = _SHARED_BEGIN_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        name = m.group("name")
        end_marker = _SHARED_END_TMPL % name
        end_at = text.find(end_marker, m.end())
        if end_at < 0:
            # Unterminated marker -- leave the rest untouched (defensive: never
            # corrupt a fragment over a malformed block).
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        code = text[m.end():end_at].strip("\n")
        blocks.append({"name": name, "proto": m.group("proto").strip(),
                       "code": code})
        pos = end_at + len(end_marker)
        if pos < len(text) and text[pos] == "\n":
            pos += 1  # swallow the newline after the END marker
    return "".join(out), blocks


_PP_IF_RE = re.compile(r"^\s*#\s*if(?:def|ndef)?\b")
_PP_ENDIF_RE = re.compile(r"^\s*#\s*endif\b")
_PROBE_IFDEF_RE = re.compile(r"^\s*#\s*ifdef\s+MPYNODE_PROBE\b")
_PROBE_IFNDEF_RE = re.compile(r"^\s*#\s*ifndef\s+MPYNODE_PROBE\b")


def _flatten_probe_guards(text: str) -> str:
    """Flatten the ``MPYNODE_PROBE`` conditionals for a bundle build.

    A native locator .cpp is the only node skeleton with these directives:
    ``#ifndef MPYNODE_PROBE … #endif`` around the plugin scaffold (+ a small
    headers guard) and a trailing ``#ifdef MPYNODE_PROBE … #endif`` standalone
    parity probe. A bundle NEVER defines ``MPYNODE_PROBE``, and
    :func:`transform_node_cpp` drops everything after ``uninitializePlugin``
    (where the locator's closing ``#endif`` + the probe block live), which left
    the fragment with an unterminated ``#ifndef`` -> clang
    "unterminated conditional directive". So before the head/hook split we:

      * drop every ``#ifdef MPYNODE_PROBE`` block whole (probe-only code), and
      * strip the ``#ifndef MPYNODE_PROBE`` guard lines while KEEPING their
        content (always-compiled plugin code, since the symbol is never defined).

    Nesting is handled by depth-counting all ``#if*``/``#endif`` so an inner
    non-probe conditional inside a guarded region is matched correctly. Codegen
    never emits ``#else`` for these guards, so no else-branch handling is needed.
    A .cpp with no ``MPYNODE_PROBE`` guard (every other node type) is returned
    byte-for-byte unchanged -- zero blast radius."""
    if "MPYNODE_PROBE" not in text:
        return text
    lines = text.splitlines()
    out: List[str] = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if _PROBE_IFDEF_RE.match(ln):
            # Drop the whole probe-only block, including its matching #endif.
            depth, i = 1, i + 1
            while i < n and depth > 0:
                if _PP_IF_RE.match(lines[i]):
                    depth += 1
                elif _PP_ENDIF_RE.match(lines[i]):
                    depth -= 1
                i += 1
            continue
        if _PROBE_IFNDEF_RE.match(ln):
            # Keep the guarded plugin code; drop only the #ifndef/#endif lines.
            depth, i = 1, i + 1
            while i < n and depth > 0:
                cur = lines[i]
                if _PP_IF_RE.match(cur):
                    depth += 1
                    out.append(cur)
                elif _PP_ENDIF_RE.match(cur):
                    depth -= 1
                    if depth == 0:
                        i += 1  # consume + drop the matching #endif
                        break
                    out.append(cur)
                else:
                    out.append(cur)
                i += 1
            continue
        out.append(ln)
        i += 1
    flattened = "\n".join(out)
    if text.endswith("\n") and not flattened.endswith("\n"):
        flattened += "\n"
    return flattened


def _toplevel_directive_lines(text: str) -> List[int]:
    """Indices of the lines holding a column-0 preprocessor directive that sits
    at brace depth 0 -- i.e. genuinely in the preamble, not inside a function.

    Column-0-ness alone is no longer sufficient. The AI optimizer emits column-0
    conditionals INSIDE function bodies: an ``#if NDPROF`` profiling block
    (comboCorrectives, patchRelax) and an ``#if defined(__APPLE__)`` sincos guard
    (helixCurve). Anchoring on the last column-0 ``#`` then lands mid-function
    and the node namespace opens there ("namespaces can only be defined in
    global or namespace scope"), dropping those nodes from the merged build --
    the same symptom the indented-pragma fix addressed, from the other side.

    Depth is counted in CODE context only, with the comment / literal / raw-string
    state machine :func:`command_names_in` uses, so a brace inside a comment or a
    string cannot skew it. Directive lines are consumed whole (honouring
    backslash continuations) so a ``#define FOO { }`` cannot move the depth.
    """
    out: List[int] = []
    i, n = 0, len(text)
    line, depth = 0, 0
    col0 = True
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            col0 = True
            continue
        at_col0, col0 = col0, False
        if c == "#" and at_col0:
            if depth == 0:
                out.append(line)
            while i < n:
                j = text.find("\n", i)
                if j < 0:
                    i = n
                    break
                seg = text[i:j].rstrip()
                i, line = j + 1, line + 1
                if not seg.endswith("\\"):
                    break
            col0 = True
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            end = n if j < 0 else j + 2
            line += text.count("\n", i, end)
            i = end
            continue
        if c in "RLuU":
            raw_end = _raw_string_span(text, i, n)
            if raw_end is not None:
                line += text.count("\n", i, raw_end)
                i = raw_end
                continue
        if c == "'" or c == '"':
            q = c
            i += 1
            while i < n and text[i] != q and text[i] != "\n":
                i += 2 if text[i] == "\\" else 1
            if i < n and text[i] == q:
                i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return out


def transform_node_cpp(
    text: str, type_name: str, id_for
) -> Tuple[str, Dict[str, str]]:
    """Transform a ported single-node .cpp into a link-ready fragment.

    ``id_for(key) -> hex`` supplies MTypeIds (main class keyed by
    ``type_name``; any companion class -- e.g. a transform's matrix -- keyed
    ``"<type_name>#<ClassName>"``). Returns ``(fragment_text, info)`` where
    info carries ``node_name / class / ns / register / deregister``.
    """
    reg = re.search(
        r"register(?:Node|Transform)\s*\(\s*\"([^\"]+)\"\s*,\s*(\w+)::id", text
    )
    node_name = reg.group(1) if reg else type_name
    main_cls = reg.group(2) if reg else re.sub(r"\W", "", type_name.title())
    ns = _ns_for(node_name)

    # (c) override every MTypeId definition with a registry-assigned id.
    text = _rewrite_typeids(text, type_name, id_for, main_cls)

    # Hoist any marked shared-helper blocks OUT of this node before we wrap the
    # body in the per-node namespace -- their definitions live once in the shared
    # unit; here we keep only a global-scope prototype so the call (inside the
    # namespace) still resolves. No markers -> text unchanged, shared == [].
    text, shared = _extract_shared_helpers(text)

    # Flatten a locator's MPYNODE_PROBE conditionals (drop the probe block, strip
    # the plugin-scaffold guard lines) so the head/hook split below can't orphan
    # the scaffold's closing #endif. No-op for every non-locator node.
    text = _flatten_probe_guards(text)

    init = _extract_fn(text, "initializePlugin")
    uninit = _extract_fn(text, "uninitializePlugin")
    if not init or not uninit:
        raise ValueError(
            "could not locate initializePlugin/uninitializePlugin in %r" % node_name
        )

    # Head = everything before the plugin functions. Wrap its code body in the
    # per-node namespace (keeping #include / # directives outside it).
    head = text[: init[0]].rstrip()
    lines = head.splitlines()
    # ONLY column-0 directives at BRACE DEPTH 0 delimit the preamble. py_to_cpp
    # emits the fp-contract fusion guard (#if/#pragma clang fp contract/#endif)
    # INDENTED, as the first statement INSIDE a compound statement -- counting
    # those made last_inc land mid-function and opened the node namespace there
    # ("error: namespaces can only be defined in global or namespace scope"),
    # dropping the node from every merged build. Every real preamble directive
    # (#include, "#  define", the nd_runtime header's closing #endif) starts at
    # column 0; no generated source ever indents an #include.
    #
    # Column 0 alone stopped being sufficient once the AI optimizer joined the
    # pipeline: it emits column-0 #if blocks inside function bodies (an NDPROF
    # profiling block, an __APPLE__ sincos guard), which reproduced the exact
    # same mid-function anchor from the other direction. The depth test covers
    # both -- see :func:`_toplevel_directive_lines`.
    inc_idx = _toplevel_directive_lines(head)
    last_inc = max(inc_idx) if inc_idx else -1
    pre = lines[: last_inc + 1]
    body = lines[last_inc + 1:]

    reg_hook = "register_%s" % main_cls
    dereg_hook = "deregister_%s" % main_cls

    # Prototypes for the hoisted helpers, at GLOBAL scope (between the includes
    # and the node namespace) so unqualified calls inside the namespace resolve
    # to the shared definitions linked from shared_helpers.cpp.
    proto_block = ""
    if shared:
        proto_block = ("\n\n// shared helper prototypes (defined in "
                       "shared_helpers.cpp)\n"
                       + "\n".join("%s;" % b["proto"] for b in shared))

    frag = (
        "\n".join(pre)
        + proto_block
        + "\n\nnamespace %s {\n" % ns
        + "\n".join(body).strip("\n")
        + "\n}  // namespace %s\n\n" % ns
        + _make_hook(init[2], reg_hook, ns)
        + "\n\n"
        + _make_hook(uninit[2], dereg_hook, ns)
        + "\n"
    )
    info = {
        "node_name": node_name,
        "class": main_cls,
        "ns": ns,
        "register": reg_hook,
        "deregister": dereg_hook,
        "shared_helpers": shared,
    }
    return frag, info


def make_single_node_cpp(
    text: str, type_name: str, id_for
) -> Tuple[str, Dict[str, str]]:
    """Turn a ported single-node .cpp into a SELF-CONTAINED, link-ready plugin
    source -- the clean "one .cpp you edit" for a single-node plugin.

    Unlike :func:`transform_node_cpp` (multi-node), this does the MINIMUM: bake
    the registry MTypeId(s) in and drop the shared-helper marker COMMENTS (their
    definitions stay inline -- a lone node has nothing to dedup). It does NOT wrap
    the body in a namespace, does NOT swap ``initializePlugin``/
    ``uninitializePlugin`` for register hooks, and does NOT flatten the
    ``MPYNODE_PROBE`` guards (they resolve correctly with the symbol undefined, and
    keeping them preserves the standalone parity probe). The result is
    byte-for-byte the node's own verified source except the ids -- so if it
    compiled as a standalone port it compiles here. Returns ``(cpp_text, info)``
    with ``node_name`` / ``class``.
    """
    reg = re.search(
        r"register(?:Node|Transform)\s*\(\s*\"([^\"]+)\"\s*,\s*(\w+)::id", text
    )
    node_name = reg.group(1) if reg else type_name
    main_cls = reg.group(2) if reg else re.sub(r"\W", "", type_name.title())
    text = _rewrite_typeids(text, type_name, id_for, main_cls)
    text = _SHARED_MARKER_LINE_RE.sub("", text)
    return text, {"node_name": node_name, "class": main_cls}


def make_plugin_main(infos: List[Dict[str, str]], plugin_name: str,
                     vendor: str = "mpynode-native", version: str = "1.0") -> str:
    """Generate the single plugin entry point that registers all nodes.

    Registration is strict at LOAD time (a failed registerNode aborts the
    load) -- compile/link-time partial-failure is handled by the assembler,
    so this only ever sees nodes that compiled."""
    decls = "\n".join(
        "MStatus %s(MFnPlugin&); MStatus %s(MFnPlugin&);"
        % (i["register"], i["deregister"]) for i in infos
    )
    regs = "\n".join(
        "    st = %s(plugin);\n"
        "    if (!st) { st.perror(\"register %s\"); return st; }"
        % (i["register"], i["node_name"]) for i in infos
    )
    # Deregister in reverse order, best-effort (never abort an unload).
    deregs = "\n".join(
        "    %s(plugin);" % i["deregister"] for i in reversed(infos)
    )
    return (
        "// %s -- combined MPyNode plugin entry (generated by bundler.py).\n"
        "// Registers %d node(s): %s\n"
        "#include <maya/MFnPlugin.h>\n"
        "#include <maya/MObject.h>\n"
        "#include <maya/MStatus.h>\n"
        "\n"
        "%s\n"
        "\n"
        "MStatus initializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj, \"%s\", \"%s\", \"Any\");\n"
        "    MStatus st;\n"
        "%s\n"
        "    return MS::kSuccess;\n"
        "}\n"
        "\n"
        "MStatus uninitializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj);\n"
        "%s\n"
        "    return MS::kSuccess;\n"
        "}\n"
        % (plugin_name, len(infos), ", ".join(i["node_name"] for i in infos),
           decls, vendor, version, regs, deregs)
    )


# Standard headers every shared helper unit gets (scalar math). A scalar-only
# shared unit stays byte-identical to before (no Maya headers -> compiles with a
# bare compiler, no Maya include path).
_SHARED_HELPER_INCLUDES = ["<cmath>", "<vector>", "<algorithm>", "<cstdint>"]

# When ANY block uses a Maya type, the shared unit gets the FULL Maya math header
# superset -- the union of what every node skeleton (codegen._INCLUDES + the
# deformer/iksolver/locator/geo include sets) provides. This guarantees the key
# invariant: if a helper definition compiled in its node's single-node port (the
# inline-fallback gate), it ALSO compiles here -- so a typed mistranslation can
# only fail the single-node compile (which degrades to inline), never hard-abort
# the multi-node link. Adding only a needed subset reintroduced that abort path
# for MEulerRotation/MQuaternion/MPoint/MColor helpers (they compiled standalone
# under the broad skeleton includes but not in a narrow shared unit).
_MAYA_TYPE_TOKENS = (
    "MVector", "MMatrix", "MPoint", "MEulerRotation", "MQuaternion",
    "MColor", "MString", "MAngle", "MTime", "MQuaternion", "MVectorArray",
    "MPointArray", "MMatrixArray", "MFloatVector", "MFloatPoint",
    "MFloatMatrix")
_SHARED_HELPER_MAYA_BUNDLE = [
    "<maya/MVector.h>", "<maya/MMatrix.h>", "<maya/MPoint.h>",
    "<maya/MEulerRotation.h>", "<maya/MQuaternion.h>", "<maya/MColor.h>",
    "<maya/MString.h>", "<maya/MAngle.h>", "<maya/MTime.h>"]
SHARED_HELPERS_FILE = "shared_helpers.cpp"


def _collect_shared_helpers(infos: List[Dict[str, str]]):
    """Dedup the shared-helper blocks across node fragments by symbol name.

    First definition of a name wins; a later block with the SAME name but
    DIFFERENT code is recorded as a conflict (never silently merged). Returns
    ``(unique_blocks, conflicts)``."""
    by_name: Dict[str, Dict[str, str]] = {}
    order: List[str] = []
    conflicts: List[str] = []
    for info in infos:
        for b in info.get("shared_helpers") or []:
            nm = b["name"]
            if nm not in by_name:
                by_name[nm] = b
                order.append(nm)
            elif by_name[nm]["code"] != b["code"]:
                conflicts.append(nm)
    return [by_name[n] for n in order], conflicts


def _maya_includes_for(blocks: List[Dict[str, str]]) -> List[str]:
    """The Maya header superset if ANY block uses a Maya type, else ``[]``.

    Word-boundary matched against a known type-token list so an ordinary
    identifier (e.g. a local named ``MAX``) never drags a scalar-only unit onto
    the Maya headers (which would break its bare-compiler build). All-or-nothing
    (the full bundle) so a typed helper that compiled in any node skeleton also
    compiles here -- see :data:`_SHARED_HELPER_MAYA_BUNDLE`."""
    text = " ".join((b.get("proto") or "") + " " + (b.get("code") or "")
                    for b in blocks)
    if any(re.search(r"\b%s\b" % tok, text) for tok in _MAYA_TYPE_TOKENS):
        return list(_SHARED_HELPER_MAYA_BUNDLE)
    return []


def make_shared_helpers_cpp(blocks: List[Dict[str, str]]) -> str:
    """Emit the single shared compilation unit holding every unique helper
    definition once (global scope).

    Every helper is forward-declared BEFORE any definition so a helper whose body
    calls a sibling helper compiles regardless of emission order (otherwise an
    A-calls-B with A emitted first is a 'use of undeclared identifier' error).
    Maya vector/matrix headers are included only when a block uses those types."""
    incs = "\n".join("#include %s" % h
                     for h in _SHARED_HELPER_INCLUDES + _maya_includes_for(blocks))
    protos = "\n".join("%s;" % b["proto"] for b in blocks)
    defs = "\n\n".join(b["code"] for b in blocks)
    return (
        "// shared_helpers.cpp -- followed-import helpers shared across nodes,\n"
        "// hoisted here so each compiles ONCE (generated by bundler.py).\n"
        "%s\n\n"
        "// forward declarations (order-independent sibling calls)\n"
        "%s\n\n%s\n" % (incs, protos, defs)
    )


def make_build_sh(plugin_name: str, frag_files: List[str],
                  needs_qt: bool = False) -> str:
    """Generate a combined build.sh: compile each fragment + plugin_main to
    .o, then link all into one .bundle.

    ``needs_qt=True`` (a bundle containing a hover locator) adds Maya's Qt
    framework search to the compile and the Qt frameworks + an rpath to the link
    (mirrors ``toolchain.qt_compile_flags`` / ``qt_link_flags``). Defaults False
    so a Qt-free bundle's script is byte-for-byte unchanged.
    """
    cxx = " ".join(_CXXFLAGS)
    frag_def = " ".join(_FRAG_DEFINES)
    libs = " ".join("-l" + l for l in _LINK_LIBS)
    fw = '"$MAYA/Maya.app/Contents/Frameworks"'
    qt_cxx = (" -F%s" % fw) if needs_qt else ""
    qt_link = ((" -framework QtCore -framework QtGui -framework QtWidgets "
                "-F%s -Wl,-rpath,%s" % (fw, fw)) if needs_qt else "")
    lines = [
        "#!/usr/bin/env bash",
        "# Generated combined build for native plugin '%s' (%d nodes)."
        % (plugin_name, len(frag_files)),
        "#",
        "# Usage:  ./build.sh [maya-version]      e.g. ./build.sh 2026",
        "# With no argument the newest installed Maya is used; MAYA=<path>",
        "# overrides discovery.",
        "set -euo pipefail",
    ] + toolchain.maya_resolver_sh("darwin") + [
        'HERE="$(cd "$(dirname "$0")" && pwd)"',
        'CXX=(clang++ %s -I"$MAYA/include"%s)' % (cxx, qt_cxx),
        "OBJS=()",
        "# Node fragments suppress the plugin-version symbols (%s);" % frag_def,
        "# only plugin_main.cpp emits them (exactly one per plugin).",
    ]
    # Sources live in build/source/ (this script sits in build/); the rebuilt
    # bundle is written UP to the top level ($HERE/../) beside nothing else.
    for f in frag_files:
        o = os.path.splitext(f)[0] + ".o"
        lines.append('"${CXX[@]}" %s -c "$HERE/source/%s" -o "$HERE/source/%s"'
                     % (frag_def, f, o))
        lines.append('OBJS+=("$HERE/source/%s")' % o)
    # plugin_main.cpp: compiled WITHOUT the suppress defines so it carries the
    # single copy of the plugin-version symbols.
    lines.append('"${CXX[@]}" -c "$HERE/source/plugin_main.cpp" '
                 '-o "$HERE/source/plugin_main.o"')
    lines.append('OBJS+=("$HERE/source/plugin_main.o")')
    lines.append(
        'clang++ -std=c++17 -arch arm64 -bundle '
        '-L"$MAYA/Maya.app/Contents/MacOS" %s "${OBJS[@]}"%s '
        '-o "$HERE/../%s.bundle"' % (libs, qt_link, plugin_name)
    )
    # Drop the object files so a hand-rebuild leaves the folder as clean as the
    # compiler did (bundle at top; source + scripts under build/).
    lines.append('rm -f "${OBJS[@]}"')
    lines.append('echo "Built: $HERE/../%s.bundle"' % plugin_name)
    lines.append('lipo -info "$HERE/../%s.bundle"' % plugin_name)
    return "\n".join(lines) + "\n"


def make_build_bat(plugin_name: str, frag_files: List[str],
                   needs_qt: bool = False) -> str:
    """Windows ``cl.exe`` equivalent of :func:`make_build_sh` (reference/debug).

    Compiles each fragment + ``plugin_main.cpp`` to ``.obj`` then links one
    ``.mll``. Run from an *x64 Native Tools Command Prompt for VS*. The actual
    programmatic build (:func:`assemble`) drives ``cl`` directly via
    ``native.toolchain``; this is the hand-runnable mirror. ``needs_qt=True``
    links Maya's Qt import libs AND emits ``toolchain.qt_resolver_bat``, which
    finds the Qt headers at RUN time.

    There is deliberately no ``qt_include`` parameter. It used to take the
    host-RESOLVED ``toolchain.qt_include_dir``, which meant the emitted script
    only worked when the generating machine was the running machine: this
    project is developed on macOS, where that resolver returns ``None``, so
    every hover node shipped a build.bat with no Qt include path and no MSVC Qt
    flags and died on Windows at ``C1083``. Resolving in the SCRIPT instead is
    both host-independent and honest about a path that cannot be known until
    the user runs it -- exactly what ``maya_resolver_bat`` already does for
    ``%MAYA%``.
    """
    libs = " ".join("%s.lib" % l for l in _LINK_LIBS)
    if needs_qt:
        libs = libs + " Qt6Core.lib Qt6Gui.lib Qt6Widgets.lib"
    cxx = ("cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 "
           "/D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS "
           "/D _CRT_SECURE_NO_WARNINGS")
    if needs_qt:
        # The MSVC-only flags Qt 6 requires ride along with the include dir, or
        # this hand-runnable mirror dies at C1189/C2338 while the programmatic
        # build (toolchain.qt_compile_flags) succeeds.
        cxx = cxx + ' %s /I "%%QTINC%%"' % " ".join(toolchain.qt_msvc_flags())
    lines = [
        "@echo off",
        "REM Generated combined build for native plugin '%s' (%d nodes)."
        % (plugin_name, len(frag_files)),
        "REM Run from an 'x64 Native Tools Command Prompt for VS'.",
        "REM",
        "REM Usage:  build.bat [maya-version]      e.g. build.bat 2026",
        "REM With no argument the newest installed Maya is used; set MAYA to",
        "REM override discovery.",
    ] + toolchain.maya_resolver_bat("win32") + (
        # Must follow the Maya resolver: the Qt probe reads %MAYA%\include.
        toolchain.qt_resolver_bat() if needs_qt else []) + [
        'set "HERE=%~dp0"',
        'set "OBJS="',
    ]
    # Sources live in build\source\ (this script sits in build\); the rebuilt
    # .mll is written UP to the top level (%HERE%..\).
    for f in frag_files:
        o = os.path.splitext(f)[0] + ".obj"
        lines.append(
            '%s /D MNoVersionString /D MNoPluginEntry /c "%%HERE%%source\\%s" '
            '/Fo"%%HERE%%source\\%s" /I "%%MAYA%%\\include"' % (cxx, f, o))
        lines.append("if errorlevel 1 exit /b 1")
        lines.append('set "OBJS=%%OBJS%% "%%HERE%%source\\%s""' % o)
    lines.append(
        '%s /c "%%HERE%%source\\plugin_main.cpp" '
        '/Fo"%%HERE%%source\\plugin_main.obj" /I "%%MAYA%%\\include"' % cxx)
    lines.append("if errorlevel 1 exit /b 1")
    lines.append('set "OBJS=%OBJS% "%HERE%source\\plugin_main.obj""')
    lines.append(
        'cl /nologo /LD %%OBJS%% /link /LIBPATH:"%%MAYA%%\\lib" %s '
        '/OUT:"%%HERE%%..\\%s.mll" '
        '/EXPORT:initializePlugin /EXPORT:uninitializePlugin'
        % (libs, plugin_name))
    lines.append("if errorlevel 1 exit /b 1")
    # Drop the object files so a hand-rebuild leaves a clean folder.
    lines.append("del %OBJS% 2>nul")
    # The link above writes UP to %HERE%..\ (the plugin lives beside build/),
    # so name that exact path -- not %HERE%.
    lines.append('echo Built: %%HERE%%..\\%s.mll' % plugin_name)
    # `del` above reports errorlevel 1 when an object file is already gone, and
    # `echo` does NOT reset it -- so a FULLY SUCCESSFUL build exited 1 and every
    # caller believed it had failed. MEASURED on Windows 2026-09-01: mPyMega.mll
    # linked (2.7 MB on disk), then the wrapper's `if errorlevel 1` skipped the
    # install copy and printed BUILD FAILED. Cleanup is best-effort and must not
    # decide the exit status. build.sh cannot have this bug: a shell script's
    # status is its last command, which is the echo.
    lines.append("exit /b 0")
    return "\r\n".join(lines) + "\r\n"


def make_single_build_sh(plugin_name: str, node_file: str, libs: List[str],
                         *, needs_qt: bool = False, maya: str = None) -> str:
    """Bash rebuild for a SELF-CONTAINED single-node plugin: one-shot compile +
    link of ``node_file`` into ``<plugin_name>.bundle``. Mirrors the verified
    single-node recipe (build_scripts.generate_build_sh); ``needs_qt`` links
    Maya's Qt frameworks for a hover locator.

    ``maya`` is recorded as provenance only -- which install the shipped
    artifact was compiled against. It is NOT baked into the script: the Maya
    root is resolved at RUN time from the optional version argument, so one
    script serves every installed version.
    """
    libflags = " ".join("-l%s" % l for l in libs)
    lines = [
        "#!/usr/bin/env bash",
        "# Rebuild native plugin '%s' from its single source 'source/%s'."
        % (plugin_name, node_file),
        "# Edit source/%s, then run ./build.sh to produce %s.bundle (one level up)."
        % (node_file, plugin_name),
        "#",
        "# Usage:  ./build.sh [maya-version]      e.g. ./build.sh 2026",
        "# With no argument the newest installed Maya is used; MAYA=<path>",
        "# overrides discovery.",
    ] + toolchain.build_provenance(maya) + [
        "set -euo pipefail",
    ] + toolchain.maya_resolver_sh("darwin") + [
        'HERE="$(cd "$(dirname "$0")" && pwd)"',
        "clang++ -std=c++17 -O3 -ffp-contract=off -arch arm64 -bundle \\",
        "  -D OSMac_ -D REQUIRE_IOSTREAM -D _BOOL \\",
        "  -Wno-nontrivial-memcall \\",
        '  -I"$MAYA/include" \\',
        '  -L"$MAYA/Maya.app/Contents/MacOS" \\',
        "  %s \\" % libflags,
    ]
    if needs_qt:
        fw = '"$MAYA/Maya.app/Contents/Frameworks"'
        lines += [
            "  -F%s \\" % fw,
            "  -framework QtCore -framework QtGui -framework QtWidgets \\",
            "  -Wl,-rpath,%s \\" % fw,
        ]
    lines += [
        '  -o "$HERE/../%s.bundle" "$HERE/source/%s"' % (plugin_name, node_file),
        'echo "Built: $HERE/../%s.bundle"' % plugin_name,
        'lipo -info "$HERE/../%s.bundle"' % plugin_name,
        "",
    ]
    return "\n".join(lines)


def make_single_build_bat(plugin_name: str, node_file: str, libs: List[str],
                          *, needs_qt: bool = False, maya: str = None) -> str:
    """Windows ``cl.exe`` rebuild for a self-contained single-node plugin
    (one-shot compile + link into ``<plugin_name>.mll``). Run from an *x64 Native
    Tools Command Prompt for VS*. ``needs_qt=True`` emits
    ``toolchain.qt_resolver_bat`` so a hover locator's Qt header search path is
    found at RUN time -- see :func:`make_build_bat` for why there is no
    ``qt_include`` parameter.

    ``maya`` is provenance only -- see :func:`make_single_build_sh`. The Maya
    root is resolved at RUN time from the optional version argument.
    """
    libx = list(libs)
    if needs_qt:
        libx += ["Qt6Core", "Qt6Gui", "Qt6Widgets"]
    libstr = " ".join("%s.lib" % l for l in libx)
    # The MSVC-only flags Qt 6 requires ride along with the include dir, or this
    # hand-runnable mirror dies at C1189/C2338 while the programmatic build
    # (toolchain.qt_compile_flags) succeeds.
    qt_inc = (' %s /I "%%QTINC%%"' % " ".join(toolchain.qt_msvc_flags())
              ) if needs_qt else ""
    return "\r\n".join([
        "@echo off",
        "REM Rebuild native plugin '%s' from its single source 'source\\%s'."
        % (plugin_name, node_file),
        "REM Edit source\\%s, then run build.bat from an 'x64 Native Tools "
        "Command Prompt for VS'." % node_file,
        "REM",
        "REM Usage:  build.bat [maya-version]      e.g. build.bat 2026",
        "REM With no argument the newest installed Maya is used; set MAYA to",
        "REM override discovery.",
    ] + toolchain.build_provenance(maya, "REM")
      + toolchain.maya_resolver_bat("win32")
      + (  # Must follow the Maya resolver: the Qt probe reads %MAYA%\include.
        toolchain.qt_resolver_bat() if needs_qt else []) + [
        'set "HERE=%~dp0"',
        ('cl /nologo /LD /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 '
         '/D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS '
         '/D _CRT_SECURE_NO_WARNINGS '
         '/I "%%MAYA%%\\include"%s "%%HERE%%source\\%s" '
         '/link /LIBPATH:"%%MAYA%%\\lib" %s '
         '/OUT:"%%HERE%%..\\%s.mll" '
         '/EXPORT:initializePlugin /EXPORT:uninitializePlugin'
         % (qt_inc, node_file, libstr, plugin_name)),
        'if errorlevel 1 exit /b 1',
        'echo Built: %%HERE%%..\\%s.mll' % plugin_name,
        "",
    ])


def make_readme(plugin_name: str, node_files: List[str], *, single: bool,
                bundle_name: str) -> str:
    """A human/AI-readable ``README.txt`` describing what to edit and how to
    rebuild the plugin in place."""
    title = "MPyNode compiled plugin: %s" % plugin_name
    lines = [
        title, "=" * len(title), "",
        "This 'build/' folder holds everything the compiler produced EXCEPT the",
        "plugin itself: the C++ source (under source/) plus the scripts to rebuild",
        "it. The importable plugin lives ONE LEVEL UP, beside this folder, so you",
        "(or an AI agent) can read/tweak the source here and recompile in place.",
        "",
        "What you'll see",
        "---------------",
        "  ../%s   <- the plugin you load into Maya (one level up)." % bundle_name,
        "  ../<type>_commands.py   <- companion command plugin(s), if any (also",
        "                             one level up, beside the bundle).",
        "  source/       <- the C++ source for every node that LINKED.",
        "  build.sh, build.bat   <- rebuild scripts (see Rebuild below).",
        "  README.txt    <- this file.",
        "  manifest.json <- build receipt: every node, its id, and -- for any that",
        "                   dropped -- the reason.",
        "  <node>/       <- ONLY appears when a node FAILED (see 'Failed nodes'",
        "                   below); a clean, all-linked build has none.",
        "",
        "Source (in source/)",
        "-------------------",
    ]
    if single:
        lines.append(
            "  source/%s   <- the node. Edit this file to change the plugin's "
            "behaviour." % node_files[0])
    else:
        for f in node_files:
            lines.append("  source/%s" % f)
        lines.append(
            "  source/plugin_main.cpp   <- registers every node above.")
        lines.append(
            "  source/shared_helpers.cpp (if present) <- helpers shared across "
            "nodes.")
    lines += [
        "",
        "Rebuild",
        "-------",
        "  macOS / Linux:  ./build.sh",
        "  Windows:        build.bat   (from an 'x64 Native Tools Command "
        "Prompt for VS')",
        "",
        "Both scripts read $MAYA / %MAYA% for the Maya install (defaulting to the",
        "standard location). The rebuilt plugin is written to the PARENT folder",
        "(one level up from here) as:",
        "  ../%s" % bundle_name,
        "",
        "Failed nodes leave breadcrumbs",
        "------------------------------",
        "  In a multi-node build, a node that FAILS to port or compile is DROPPED",
        "  from the bundle (the others still link) and leaves a folder here so you",
        "  can see WHY:",
        "    <node>/<node>.cpp     the generated C++ that would not compile, and/or",
        "    <node>/compile.log    the port / compile transcript.",
        "  A node rejected earlier, at the portability gate, never got that far, so",
        "  it leaves NO folder -- only a reason in manifest.json. Nodes that built",
        "  successfully leave no folder either, so ANY <node>/ folder in here marks",
        "  a failure worth investigating (the one-line reason is in manifest.json).",
        "",
        "Notes",
        "-----",
        "  * MTypeId values come from your per-user id registry and are already",
        "    baked into the source -- do not hand-edit them (two plugins could",
        "    otherwise collide).",
        "  * To load in Maya: loadPlugin this bundle (.bundle on macOS, .mll on",
        "    Windows).",
        "",
    ]
    return "\n".join(lines)


# ---- Orchestration --------------------------------------------------------


class _FailedLaunch:
    """A stand-in compile result for "the compiler could not be launched".

    Mirrors the ``subprocess.CompletedProcess`` attributes the assemble path
    reads (``returncode``/``stdout``/``stderr``) so a failed launch flows through
    the existing nonzero-exit handling as an actionable message instead of
    propagating a bare ``[WinError 2]`` -- the same decode ``porter.compile_cpp``
    already does for the single-node path.
    """

    def __init__(self, message: str):
        self.returncode = 9009  # cmd.exe "command not found" rc; distinctive
        self.stdout = ""
        self.stderr = message


class _CompileResult:
    """A CompletedProcess-like result from a STREAMED compile/link run.

    ``toolchain.run_streaming`` merges stdout+stderr, so both attributes carry
    the same full text -- enough for the assemble path, which only reads
    ``returncode`` and ``stderr`` (for ``report['stderr']`` and the failure line).
    """

    def __init__(self, returncode, text):
        self.returncode = returncode
        self.stdout = text
        self.stderr = text


def _run_compile(cmd, env, compiler, log_cb=None):
    """Run a compile/link ``cmd``, streaming output to ``log_cb`` (if given);
    never raise on a missing executable.

    On ``FileNotFoundError`` (the compiler binary could not be launched at all)
    return a :class:`_FailedLaunch` carrying ``toolchain.compiler_missing_message``
    so the caller reports a clear cause rather than crashing with ``[WinError 2]``.
    """
    try:
        rc, text = toolchain.run_streaming(cmd, env=env, log_cb=log_cb)
    except FileNotFoundError:
        return _FailedLaunch(toolchain.compiler_missing_message(compiler))
    return _CompileResult(rc, text)


def _detect_qt(nodes) -> bool:
    """True if the bundle needs Maya's Qt frameworks -- i.e. any node source
    includes the hover locator's ``QtGui/QCursor`` header."""
    for _tn, cp in nodes:
        try:
            with open(cp) as fh:
                if "QtGui/QCursor" in fh.read():
                    return True
        except Exception:
            pass
    return False


def _prepare_compiler(report: dict, compile_now: bool):
    """Resolve the platform compiler + build env, running the MSVC vcvars /
    resolve / toolset-mismatch pre-flight both assemble paths need.

    Returns ``{exe, obj_env, compiler}`` or ``None`` (with ``report['reason']``
    set) when the toolchain can't compile. ``compile_now=False`` never fails.
    """
    compiler = toolchain.default_compiler()
    obj_env = toolchain.build_env(compiler)
    # MSVC: refuse a stray PATH cl when the vcvars env couldn't be captured -- it
    # may be an older toolset than the installed headers (STL1001). Allowed inside
    # an x64 Native Tools prompt (ambient toolset already consistent).
    if (compile_now and toolchain.compiler_family(compiler) == "msvc"
            and obj_env is None and not toolchain.in_developer_shell()):
        report["reason"] = toolchain.vcvars_unavailable_message(compiler)
        return None
    # Resolve the compiler to a full path (THE WINDOWS FIX: a bare "cl" raises
    # [WinError 2] because cl.exe is only on the captured vcvars PATH). Unix
    # compilers pass through unchanged.
    resolved = toolchain.resolve_compiler(compiler, obj_env)
    if compile_now and resolved is None:
        report["reason"] = toolchain.compiler_missing_message(compiler)
        return None
    exe = resolved or compiler
    # MSVC toolset-consistency PRE-FLIGHT (guards the cache-hit path where the
    # per-node compile_cpp guard was skipped): refuse if the resolved cl differs
    # from the INCLUDE headers' toolset (the STL1001 cause).
    if compile_now and toolchain.compiler_family(compiler) == "msvc":
        include = (obj_env or os.environ).get("INCLUDE")
        mismatch = toolchain.diagnose_toolset_mismatch(exe, include)
        if mismatch:
            report["reason"] = mismatch
            return None
    return {"exe": exe, "obj_env": obj_env, "compiler": compiler}


def _remove_objects(directory: str) -> None:
    """Delete object files left by a link (in ``directory`` = build/source) so a
    successful build leaves only source + scripts (best-effort)."""
    for pat in ("*.o", "*.obj"):
        for p in glob.glob(os.path.join(directory, pat)):
            try:
                os.remove(p)
            except OSError:
                pass


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _clean_stale_intermediates(out_dir: str, keep=()) -> None:
    """Remove leftovers from a PRIOR compile into the same folder so a re-compile
    yields the clean nested layout.

    Two jobs: (1) MIGRATE -- a pre-reorg compile wrote source / build scripts /
    README / manifest FLAT at the top of ``out_dir``; sweep those so the top
    level ends up holding only the bundle (+ ``*_commands.py`` companions, which
    are left untouched). (2) drop any stale ``frag_*.cpp`` / object files inside
    the build tree. Current-layout sources are overwritten in place.

    ``keep`` is a set of ABSOLUTE paths never to delete -- the input node .cpp
    files being assembled. They are usually elsewhere, but a caller may point
    ``out_dir`` at the very folder holding the inputs (some tests do), and the
    ``*.cpp`` migration sweep must not eat them."""
    keep = {os.path.abspath(p) for p in keep}
    # (1) migration: flat-layout files an OLD compile left at the top level.
    for name in ("build.sh", "build.bat", "README.txt", "manifest.json"):
        p = os.path.join(out_dir, name)
        if os.path.abspath(p) not in keep:
            _rm(p)
    for pat in ("*.cpp", "*.o", "*.obj"):  # *.cpp covers frag_*/plugin_main/etc.
        for p in glob.glob(os.path.join(out_dir, pat)):
            if os.path.abspath(p) not in keep:
                _rm(p)
    # (2) stale intermediates inside the build tree.
    for d in (build_dir_for(out_dir), source_dir_for(out_dir)):
        for pat in ("frag_*.cpp", "*.o", "*.obj"):
            for p in glob.glob(os.path.join(d, pat)):
                if os.path.abspath(p) not in keep:
                    _rm(p)


def _clash_reason(clashes: Dict[str, List[str]]) -> str:
    return ("companion-command name clash(es): "
            + "; ".join("%s (from %s)" % (cmd, ", ".join(sorted(set(owners))))
                        for cmd, owners in sorted(clashes.items())))


def assemble(
    nodes: List[Tuple[str, str]],
    plugin_name: str,
    out_dir: str,
    *,
    strict: bool = True,
    registry: Optional[typeid_registry.TypeIdRegistry] = None,
    maya: str = _MAYA_DEFAULT,
    compile_now: bool = True,
    log_cb=None,
    needs_qt: Optional[bool] = None,
) -> dict:
    """Assemble ``nodes`` (list of ``(type_name, cpp_path)``) into ONE plugin,
    laid out as a clean, re-buildable source folder (see the module docstring).

    A **single-node** plugin becomes a self-contained ``<node>.cpp`` (no
    ``plugin_main.cpp``); a **multi-node** plugin becomes ``<node>.cpp`` per node
    + ``plugin_main.cpp`` (+ optional ``shared_helpers.cpp``). Either way the
    folder also gets ``build.sh`` AND ``build.bat`` + a ``README.txt``, and object
    files are removed after a successful link.

    Returns a report dict: ``{plugin, bundle, nodes:[{name,status,id,reason}],
    ok, dropped}``. With ``strict=True`` any per-node compile failure aborts and
    no bundle is produced; with ``strict=False`` failing nodes are dropped
    (loudly, in the report) and the rest are bundled.

    ``needs_qt`` makes the bundle link Maya's Qt frameworks (a hover-capable
    locator's self-contained C++ hover service includes QCursor/QWidget). Default
    ``None`` -> auto-detect by scanning the node sources for the Qt include; pass
    an explicit bool to override.
    """
    reg = registry or typeid_registry.TypeIdRegistry()
    if needs_qt is None:
        needs_qt = _detect_qt(nodes)
    # GENERATION-TIME Qt gate. Both assemble paths (single + multi) funnel
    # through here, and it runs FIRST -- before out_dir is even created, let
    # alone swept -- so a refusal touches nothing: it is not worth deleting a
    # working plugin folder's build scripts to tell someone their Qt headers
    # are unextracted. Failing here gives one actionable message instead of a
    # build.bat whose first hover TU dies at C1083 and takes the whole serial
    # ``if errorlevel 1 exit /b 1`` chain -- and every other node -- with it.
    # No-op off Windows (qt_include_problem returns None there).
    if needs_qt:
        qt_problem = toolchain.qt_include_problem(maya)
        if qt_problem:
            raise UnsupportedSpec(qt_problem)
    os.makedirs(out_dir, exist_ok=True)
    # Protect the input node .cpp files from the migration sweep in case a caller
    # points out_dir at the folder that holds them.
    _clean_stale_intermediates(out_dir, keep=[cp for _tn, cp in nodes])
    # Nested layout: source under build/source, scripts under build/, bundle at
    # the top of out_dir. Create build/source (also makes build/) for both the
    # single- and multi-node paths below.
    src_dir = source_dir_for(out_dir)
    build_dir = build_dir_for(out_dir)
    os.makedirs(src_dir, exist_ok=True)
    report = {"plugin": plugin_name, "bundle": None, "nodes": [], "ok": False,
              "dropped": []}

    # Single-node plugin -> one clean, self-contained <node>.cpp (the common
    # case: one node per plugin). No namespace/hook surgery, no plugin_main.
    if len(nodes) == 1:
        return _assemble_single(
            nodes[0], plugin_name, out_dir, reg, report, strict=strict,
            maya=maya, compile_now=compile_now, log_cb=log_cb, needs_qt=needs_qt)

    # ---- multi-node: <node>.cpp fragments + plugin_main.cpp ----
    # 1) read + transform each node, collecting ids from the registry.
    fragments: List[Tuple[str, Dict[str, str], str]] = []  # (cpp_path, info, type_name)
    cmd_sources: List[Tuple[str, str]] = []  # (type_name, src) for clash detection
    for type_name, cpp_path in nodes:
        rec = {"name": type_name, "status": "pending", "id": None, "reason": ""}
        try:
            with open(cpp_path) as fh:
                src = fh.read()
            cmd_sources.append((type_name, src))
            # Pre-allocate ids for every MTypeId this file defines so id_for is
            # a pure lookup during transform.
            cls_defs = re.findall(r"MTypeId\s+(\w+)::id\(0x[0-9a-fA-F]+\);", src)
            reg_m = re.search(r"register(?:Node|Transform)\s*\(\s*\"[^\"]+\"\s*,\s*(\w+)::id", src)
            main_cls = reg_m.group(1) if reg_m else None
            keys = []
            for c in cls_defs:
                keys.append(type_name if c == main_cls else "%s#%s" % (type_name, c))
            id_map = reg.allocate_many(keys)

            def id_for(key, _m=id_map):
                return _m[key]

            frag, info = transform_node_cpp(src, type_name, id_for)
            frag_path = os.path.join(src_dir, _node_cpp_name(info["node_name"]))
            with open(frag_path, "w") as fh:
                fh.write(frag)
            rec["id"] = id_map.get(type_name)
            rec["status"] = "transformed"
            fragments.append((frag_path, info, type_name))
            report["nodes"].append(rec)
        except Exception as exc:
            rec["status"] = "error"
            rec["reason"] = "transform: %s" % exc
            report["nodes"].append(rec)
            if strict:
                return report

    if not fragments:
        return report

    # 1b) reject companion-command NAME clashes BEFORE link: Maya's command
    #     namespace is one global string space, so a duplicate name fails the 2nd
    #     registerCommand at LOAD. Fatal REGARDLESS of `strict` -- there is no safe
    #     auto-resolution, and falling through emits a bundle whose
    #     initializePlugin aborts for the WHOLE plugin, which reads as ok.
    clashes = find_command_clashes(cmd_sources)
    if clashes:
        report["reason"] = _clash_reason(clashes)
        return report  # ok stays False; no bundle produced

    # 2) compile each fragment to an object file (per-node isolation ->
    #    drop-or-abort). The compile/link recipe is platform-chosen by toolchain.
    tc = _prepare_compiler(report, compile_now)
    if tc is None:
        return report
    exe, obj_env, compiler = tc["exe"], tc["obj_env"], tc["compiler"]
    arch = toolchain.mac_arch()
    frag_files = []
    frag_objs = []           # needed for the Windows direct-link path
    compiled_infos = []
    inc = toolchain.maya_include_dir(maya)
    for frag_path, info, type_name in fragments:
        rec = next(r for r in report["nodes"] if r["name"] == type_name)
        obj = os.path.splitext(frag_path)[0] + toolchain.object_ext()
        cmd = toolchain.compile_object_cmd(
            exe, frag_path, obj, include_dir=inc, frag=True, arch=arch,
            qt=needs_qt, maya=maya)
        if compile_now:
            proc = _run_compile(cmd, obj_env, compiler, log_cb=log_cb)
            if proc.returncode != 0:
                rec["status"] = "compile-failed"
                rec["reason"] = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "compile error"
                report["dropped"].append(type_name)
                if strict:
                    report["stderr"] = proc.stderr
                    return report
                # Best-effort: this node is DROPPED from the bundle, so its
                # transformed fragment must not linger in source/ (which is the
                # bundle's source -- build.sh never compiles it). The debug
                # breadcrumb is the per-node scratch dir the controller keeps.
                _rm(frag_path)
                continue
        rec["status"] = "compiled"
        frag_files.append(os.path.basename(frag_path))
        frag_objs.append(obj)
        compiled_infos.append(info)

    if not compiled_infos:
        return report

    # 2b) collect + dedup shared-helper blocks across the nodes that ACTUALLY
    #     compiled (so a dropped node never orphans its helper into the unit),
    #     emit the one shared unit, compile it, and add it to the link set. No
    #     node carried a block -> shared_path stays None and NOTHING below
    #     changes. A broken shared helper is a hard build failure.
    shared_blocks, shared_conflicts = _collect_shared_helpers(compiled_infos)
    if shared_conflicts:
        report["shared_helper_conflicts"] = shared_conflicts
    shared_path = None
    if shared_blocks:
        shared_path = os.path.join(src_dir, SHARED_HELPERS_FILE)
        with open(shared_path, "w") as fh:
            fh.write(make_shared_helpers_cpp(shared_blocks))
        report["shared_helpers"] = [b["name"] for b in shared_blocks]
    if shared_path is not None:
        shared_obj = os.path.splitext(shared_path)[0] + toolchain.object_ext()
        if compile_now:
            sh_cmd = toolchain.compile_object_cmd(
                exe, shared_path, shared_obj, include_dir=inc, frag=True,
                arch=arch, qt=needs_qt, maya=maya)
            proc = _run_compile(sh_cmd, obj_env, compiler, log_cb=log_cb)
            if proc.returncode != 0:
                report["reason"] = "shared helpers compile failed"
                report["stderr"] = proc.stderr
                return report
        frag_files.append(os.path.basename(shared_path))
        frag_objs.append(shared_obj)

    # 3) plugin_main (into build/source) + BOTH build scripts + README (into
    #    build/), then link the bundle at the TOP of out_dir.
    with open(os.path.join(src_dir, "plugin_main.cpp"), "w") as fh:
        fh.write(make_plugin_main(compiled_infos, plugin_name))
    node_cpp_files = [_node_cpp_name(i["node_name"]) for i in compiled_infos]
    build_sh = os.path.join(build_dir, "build.sh")
    # newline="" on BOTH: the generators already emit their own line endings
    # (LF for .sh, CRLF for .bat). Without it a Windows host translates them
    # again -- the .sh becomes CRLF and dies with "$'\r': command not found",
    # the .bat becomes \r\r\n. No-op on macOS (os.linesep is already "\n").
    with open(build_sh, "w", newline="") as fh:
        fh.write(make_build_sh(plugin_name, frag_files, needs_qt=needs_qt))
    if not toolchain.is_windows():
        os.chmod(build_sh, 0o755)
    with open(os.path.join(build_dir, "build.bat"), "w", newline="") as fh:
        fh.write(make_build_bat(plugin_name, frag_files, needs_qt=needs_qt))
    out_plugin = os.path.join(out_dir, plugin_name + toolchain.plugin_ext())
    with open(os.path.join(build_dir, "README.txt"), "w") as fh:
        fh.write(make_readme(plugin_name, node_cpp_files, single=False,
                             bundle_name=os.path.basename(out_plugin)))

    # Remove any stale bundle from a PRIOR compile up-front so the post-link
    # existence check below means "THIS run produced it", not a leftover an
    # aborted/failed link never overwrote (#67).
    if compile_now:
        _rm(out_plugin)

    if toolchain.is_windows():
        # Direct cl compile+link (the build-verified path); build.bat above is the
        # hand-runnable mirror.
        if compile_now:
            pm_obj = os.path.join(src_dir, "plugin_main" + toolchain.object_ext())
            pm_cmd = toolchain.compile_object_cmd(
                exe, os.path.join(src_dir, "plugin_main.cpp"), pm_obj,
                include_dir=inc, frag=False, arch=arch, qt=needs_qt, maya=maya)
            proc = _run_compile(pm_cmd, obj_env, compiler, log_cb=log_cb)
            if proc.returncode != 0:
                report["reason"] = "plugin_main compile failed"
                report["stderr"] = proc.stderr
                return report
            link_cmd = toolchain.link_plugin_cmd(
                exe, frag_objs + [pm_obj], out_plugin,
                lib_dir=toolchain.maya_lib_dir(maya), libs=_LINK_LIBS,
                qt=needs_qt, maya=maya)
            proc = _run_compile(link_cmd, obj_env, compiler, log_cb=log_cb)
            if proc.returncode != 0:
                report["reason"] = "link failed"
                report["stderr"] = proc.stderr
                return report
            report["bundle"] = out_plugin
    elif toolchain.is_linux():
        # No Linux generator exists -- build.sh above is the macOS recipe. Fail
        # with a readable reason instead of a confusing clang error. See the
        # note on the single-node path and docs/PORTING.md.
        if compile_now:
            report["reason"] = _LINUX_UNSUPPORTED
            return report
    else:
        if compile_now:
            env = dict(os.environ, MAYA=maya)
            proc = _run_compile(["bash", build_sh], env, compiler, log_cb=log_cb)
            if proc.returncode != 0:
                report["reason"] = "link failed"
                report["stderr"] = proc.stderr
                return report
            report["bundle"] = out_plugin

    if report.get("bundle"):
        # The linker returned 0 but must have actually produced the artifact --
        # never report a phantom bundle as ok (#62). Handles file OR dir bundles.
        if not os.path.exists(report["bundle"]):
            report["reason"] = ("linker reported success but no bundle was "
                                "produced at %s" % report["bundle"])
            report["bundle"] = None
            return report
        _remove_objects(src_dir)
    report["ok"] = True
    return report


def _assemble_single(node, plugin_name, out_dir, reg, report, *, strict, maya,
                     compile_now, log_cb, needs_qt) -> dict:
    """Emit a clean, SELF-CONTAINED single-node plugin folder.

    One ``<node>.cpp`` (registry ids baked in, its own initializePlugin), a
    ``build.sh`` + ``build.bat`` + ``README.txt``, and -- when ``compile_now`` --
    the linked ``<plugin>.bundle``. Any ``plugin_main.cpp`` / ``shared_helpers.cpp``
    left by a prior multi-node compile into this folder is removed. Mirrors the
    ``assemble`` report shape.
    """
    type_name, cpp_path = node
    rec = {"name": type_name, "status": "pending", "id": None, "reason": ""}
    report["nodes"].append(rec)
    try:
        with open(cpp_path) as fh:
            src = fh.read()
    except Exception as exc:
        rec["status"] = "error"
        rec["reason"] = "read: %s" % exc
        return report

    # A single node can still register a companion command twice (name clash).
    clashes = find_command_clashes([(type_name, src)])
    if clashes:
        report["reason"] = _clash_reason(clashes)
        return report

    # Pre-allocate registry ids for every MTypeId this file defines.
    cls_defs = re.findall(r"MTypeId\s+(\w+)::id\(0x[0-9a-fA-F]+\);", src)
    reg_m = re.search(r"register(?:Node|Transform)\s*\(\s*\"[^\"]+\"\s*,\s*(\w+)::id", src)
    main_cls = reg_m.group(1) if reg_m else None
    keys = [type_name if c == main_cls else "%s#%s" % (type_name, c)
            for c in cls_defs]
    id_map = reg.allocate_many(keys)

    def id_for(key, _m=id_map):
        return _m[key]

    try:
        cpp_text, info = make_single_node_cpp(src, type_name, id_for)
    except Exception as exc:
        rec["status"] = "error"
        rec["reason"] = "transform: %s" % exc
        return report

    node_file = _node_cpp_name(info["node_name"])
    src_dir = source_dir_for(out_dir)
    build_dir = build_dir_for(out_dir)
    os.makedirs(src_dir, exist_ok=True)
    with open(os.path.join(src_dir, node_file), "w") as fh:
        fh.write(cpp_text)
    rec["id"] = id_map.get(type_name)
    rec["status"] = "transformed"

    # A single-node plugin has no plugin_main / shared unit -- drop any left by a
    # prior multi-node compile into the source dir.
    for stale in ("plugin_main.cpp", SHARED_HELPERS_FILE):
        _rm(os.path.join(src_dir, stale))

    libs = list(_LINK_LIBS)
    # The build scripts are cross-platform artifacts, so each gets its OWN
    # platform's default $MAYA. Only the HOST-platform script gets this compile's
    # actual maya -- we can't know the user's install on the other OS.
    is_win = toolchain.is_windows()
    build_sh = os.path.join(build_dir, "build.sh")
    # newline="" -- see the note in assemble(): the generators own their line
    # endings, a second translation on a Windows host breaks both scripts.
    with open(build_sh, "w", newline="") as fh:
        fh.write(make_single_build_sh(plugin_name, node_file, libs, needs_qt=needs_qt,
                                      maya=(None if is_win else maya)))
    if not is_win:
        os.chmod(build_sh, 0o755)
    with open(os.path.join(build_dir, "build.bat"), "w", newline="") as fh:
        fh.write(make_single_build_bat(plugin_name, node_file, libs,
                                       needs_qt=needs_qt,
                                       maya=(maya if is_win else None)))
    out_plugin = os.path.join(out_dir, plugin_name + toolchain.plugin_ext())
    with open(os.path.join(build_dir, "README.txt"), "w") as fh:
        fh.write(make_readme(plugin_name, [node_file], single=True,
                             bundle_name=os.path.basename(out_plugin)))

    if not compile_now:
        report["ok"] = True
        return report

    tc = _prepare_compiler(report, compile_now)
    if tc is None:
        rec["status"] = "compile-failed"
        rec["reason"] = report.get("reason", "toolchain unavailable")
        report["dropped"].append(type_name)
        return report

    # Remove any stale bundle from a PRIOR compile so the post-link existence
    # check below means "THIS run produced it" (#67). Done only AFTER the compiler
    # is confirmed available (as in the multi-node path), so a recompile that
    # can't find a toolchain never destroys the last-good bundle.
    _rm(out_plugin)

    if toolchain.is_windows():
        cmd = toolchain.compile_to_plugin_cmd(
            tc["exe"], os.path.join(src_dir, node_file), out_plugin,
            include_dir=toolchain.maya_include_dir(maya),
            lib_dir=toolchain.maya_lib_dir(maya), libs=libs,
            arch=toolchain.mac_arch(), qt=needs_qt, maya=maya)
        proc = _run_compile(cmd, tc["obj_env"], tc["compiler"], log_cb=log_cb)
    elif toolchain.is_linux():
        # There is no Linux build-script generator: make_single_build_sh emits
        # the macOS recipe (clang++/-D OSMac_/-bundle/lipo). Running it here
        # would fail deep in the compiler with a confusing message, so say so
        # up front. See docs/PORTING.md -- the g++/.so column is unimplemented.
        rec["status"] = "compile-failed"
        rec["reason"] = _LINUX_UNSUPPORTED
        report["reason"] = _LINUX_UNSUPPORTED
        report["dropped"].append(type_name)
        return report
    else:
        # Dogfood the shipped build.sh: the script the user re-runs is the one
        # that built the bundle.
        env = dict(os.environ, MAYA=maya)
        proc = _run_compile(["bash", build_sh], env, tc["compiler"], log_cb=log_cb)

    if proc.returncode != 0:
        rec["status"] = "compile-failed"
        rec["reason"] = (proc.stderr.strip().splitlines()[-1]
                         if proc.stderr.strip() else "compile error")
        report["reason"] = "build failed"
        report["stderr"] = proc.stderr
        report["dropped"].append(type_name)
        return report

    rec["status"] = "compiled"
    # The linker returned 0 but must have actually produced the artifact --
    # never report a phantom bundle as ok (#62).
    if not os.path.exists(out_plugin):
        rec["status"] = "compile-failed"
        rec["reason"] = "linker reported success but produced no bundle"
        report["reason"] = ("linker reported success but no bundle was "
                            "produced at %s" % out_plugin)
        report["dropped"].append(type_name)
        return report
    report["bundle"] = out_plugin
    _remove_objects(src_dir)
    report["ok"] = True
    return report
