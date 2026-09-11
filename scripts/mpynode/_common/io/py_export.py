"""Bake an mPyNode wrapper into a standalone ``.py`` rebuild script.

Unlike the ``.mpn`` format (which packs structure AND pickled stored data),
this emits a readable Python module that reconstructs the node's STRUCTURE +
expressions from scratch using the imperative wrapper API -- a subclass of the
node's ROOT wrapper with a generated ``build()`` classmethod (``ls`` / ``wrap``
and the rest of the API are inherited). It is meant to drop straight into a TA's
own toolkit.

This is a ONE-WAY bake: the node's Methods tab is emitted as REAL Python --
instance methods and classmethods on the generated class, and plain helper
functions (no ``self``/``cls``) hoisted to MODULE scope so they stay callable
exactly as written. The generated script does NOT re-store the Methods text via
``set_methods_source``, so re-importing it will not repopulate the Methods tab.
Compute/Init/Viewport/OSL expressions genuinely live as text on the node (there
is no class-method equivalent), so those stay as ``set_*_expression(...)``
strings.
Use the ``.mpn`` export for a full round-trip.

Stored variables are RE-DECLARED only (``add_variable(name, persistent=...)``);
their runtime values (NumPy arrays, dicts, images, ...) are not source code, so
they are intentionally NOT embedded -- use ``.mpn`` to carry data. This keeps
the script readable and free of the pickle/RCE surface.

Pure + Qt-free (mirrors ``mpn_io.serialize_node``), so it is unit-testable
headless and shared by the File-menu bake and the Copy-baked-script action.

ONE exception to "pure": the Node Info metadata banner at the top of the bake
falls back to the global defaults in the Node Designer preferences, the same
merge a compile does, so a node with a blank license does not compile WITH the
studio default and bake without it. That makes the bake depend on ambient prefs
-- tests that assert on the banner stub ``metadata_registry.prefs_defaults``.
"""

from __future__ import annotations

import ast
import inspect
import keyword
import re
from typing import Any

from mpynode._common.lifecycle import metadata_registry as md


def is_valid_class_name(name: Any) -> bool:
    """True if ``name`` is usable as a Python class name.

    A valid, non-keyword identifier. A leading-lowercase name (e.g. ``foo``)
    is still valid here -- callers may WARN on it, but it is not rejected.
    """
    return bool(name) and isinstance(name, str) and name.isidentifier() \
        and not keyword.iskeyword(name)


def is_pascal_class_name(name: Any) -> bool:
    """True if ``name`` is a valid PascalCase Python class name.

    Stricter than ``is_valid_class_name``: also requires a leading UPPERCASE
    letter. This is the gate for the canonical node Class name (the compiled
    type derives its lower-first form from it)."""
    return is_valid_class_name(name) and name[:1].isupper()


def resolve_bake_class_name(py_node, prompt_fn) -> str | None:
    """Determine the class name to bake for ``py_node``, or ``None`` to ABORT.

    The class name comes from IDENTITY, never from the node name:

    * If the node carries a ``_pyClass`` logical identity, reuse its short name
      (never prompt).
    * Otherwise call ``prompt_fn()`` -> ``str | None`` to obtain a name. A
      returned ``None`` (user cancelled) aborts the bake. A returned valid name
      also STAMPS the node (``set_py_class("__main__." + name)``) so subsequent
      bakes reuse it; an invalid / empty name aborts.
    """
    try:
        pc = py_node.get_py_class()
    except Exception:  # noqa: BLE001
        pc = None
    if pc:
        short = pc.rpartition(".")[2]
        if short:
            return short

    entered = prompt_fn()
    if not is_valid_class_name(entered):
        return None
    # Synthesize an importable in-memory class and stamp its canonical path so
    # later bakes reuse it -- never the un-importable ``__main__.<Name>``.
    try:
        from mpynode._common.io.user_classes import synthesize, dotted_path

        try:
            import maya.cmds as _mc

            native_type = _mc.nodeType(py_node.get_name())
        except Exception:  # noqa: BLE001
            native_type = getattr(type(py_node), "NATIVE_TYPE", "mPyNode")
        synthesize(entered, native_type)
        py_node.set_py_class(dotted_path(entered))
    except Exception:  # noqa: BLE001
        pass
    return entered

# What a bake does and does not carry. This is DOCUMENTATION, not a file
# header: it is no longer emitted into the script. It was 16 of the 33 lines of
# a plain node's bake -- half the file, above the user's own code, on every
# node, saying the same thing every time -- and the top of the script belongs
# to whoever is writing it. The Identity tab renders this instead (see
# ``ui/widgets/identity_tab.py``), which is where facts about the node's export
# live and where it can be read once rather than skipped forever.
BAKE_CONTRACT = (
    "Rebuilds this %(native_type)s node's structure + expressions from scratch.\n"
    "\n"
    "The generated class subclasses its root wrapper, inheriting the full\n"
    "wrapper API (ls / wrap / create / ...); only build() is regenerated.\n"
    "\n"
    "This is a ONE-WAY bake: the node's Methods are emitted as REAL Python\n"
    "(instance methods, classmethods, and module-level functions), NOT as the\n"
    "editable Methods-tab text. Re-importing this script into the Node Designer\n"
    "will NOT repopulate the Methods tab.\n"
    "\n"
    "Use the .mpn export for a full round-trip (and to carry stored variable\n"
    "DATA: persistent variables here are re-DECLARED with a neutral default\n"
    "only -- their runtime values, NumPy arrays/dicts/images/..., are not\n"
    "source code and are NOT included).\n"
)


# Blank lines the exporter has ALWAYS emitted before each generated block.
# The user can override any of them (see gap_spacing_registry): the API view
# lets Return push a block down and Backspace pull it back up, and the result
# is stored on the node. This table is the fallback, so a node with no stored
# spacing bakes byte-for-byte what it baked before the feature existed.
_DEFAULT_GAP = {
    "metadata": 0,         # the very top of the file, above the user's header
    "header": 0,           # the top of the file
    "imports": 0,          # the header carries its own trailing blank
    "imports_hoisted": 0,  # runs straight on from the imports above it
    "module_segment": 2,
    "class_decl": 2,
    "build_signature": 1,
    "attrs_in": 1,
    "attrs_out": 1,
    "expr_header": 1,
    "expr_init": 0,        # the tiers pack tight under their own header
    "expr_compute": 0,
    "expr_viewport": 0,
    "expr_osl": 0,
    "vars": 1,
    "return": 1,
    "method_member": 1,
    "method_warning": 1,
}

# Kinds that appear MORE THAN ONCE in a bake. Keying their spacing on the kind
# alone would move every one of them at once, so they key on their label (the
# def / segment name) too. A rename or a reorder just misses the key and falls
# back to the default, which is always a valid answer.
_REPEATED_GAP_KINDS = ("module_segment", "method_member", "method_warning")


def gap_key(kind: str, label=None) -> str:
    """The spacing-map key for a block. Public: the API view derives the same
    key from a region when it writes the map back, and two spellings of one
    boundary would silently stop round-tripping."""
    if kind in _REPEATED_GAP_KINDS and label:
        return "%s:%s" % (kind, label)
    return kind


def _leading_header_block(methods_src: str):
    """``(text, n_lines)`` for the header the user wrote at the top of their
    Methods source, or ``("", 0)``.

    The header is everything before the first real top-level statement --
    comment lines and blanks -- plus a leading module docstring if there is
    one. Emitted verbatim as the FIRST thing in the bake, above the imports,
    which is the only place a file header can be.

    Both halves fixed a defect. A leading COMMENT block was dropped from the
    bake outright (it is not an AST node, so the module-segment walker never
    saw it), so a header typed in the Methods tab silently did not exist in the
    baked file. A leading DOCSTRING did survive, but was emitted after the
    imports as an ordinary string expression -- not ``__doc__``, and not a
    header.

    Returned as a LINE COUNT as well as text so the caller can mark the region
    as the slice ``1..n_lines`` of the Methods source and splice edits straight
    back into it.
    """
    if not (methods_src or "").strip():
        return "", 0
    lines = methods_src.split("\n")
    try:
        tree = ast.parse(methods_src)
    except (SyntaxError, ValueError):
        return "", 0
    # 1-based line of the first statement, counting from its decorators so a
    # decorated def does not leave its @ lines looking like header comments.
    first = len(lines) + 1
    if tree.body:
        stmt = tree.body[0]
        first = _stmt_line(stmt)
    end = 0
    for i in range(min(first - 1, len(lines))):
        text = lines[i].strip()
        if text and not text.startswith("#"):
            break
        end = i + 1
    # A leading docstring is a statement, so it sits at `first` rather than in
    # the comment run above; take it too and let it land where Python actually
    # reads it.
    if tree.body and _is_docstring(tree.body[0]) and end >= first - 1:
        last = getattr(tree.body[0], "end_lineno", None)
        if last:
            end = last
    if not end:
        return "", 0
    # Absorb the blank lines between the header and the first real statement,
    # rather than trimming them and letting the exporter append a separator of
    # its own. The emitted bytes are identical either way; what changes is that
    # the REGION now spans those blanks, so a line of room the user opens up at
    # the top of the file splices back into the Methods source and survives the
    # next bake. A trimmed header cannot express "leave me some space here".
    rest = tree.body[1:] if _is_docstring(tree.body[0]) else tree.body
    code_line = _stmt_line(rest[0]) if rest else len(lines) + 1
    limit = min(code_line - 1, len(lines))
    while end < limit and not lines[end].strip():
        end += 1
    return "\n".join(lines[:end]), end


def _is_docstring(stmt) -> bool:
    return (isinstance(stmt, ast.Expr)
            and isinstance(getattr(stmt, "value", None), ast.Constant)
            and isinstance(stmt.value.value, str))


def _class_name_from_node_name(name: str) -> str:
    """Derive a valid PascalCase Python class name from a Maya node name."""
    parts = [p for p in re.sub(r"[^0-9A-Za-z_]", " ", name or "").split() if p]
    if not parts:
        return "ExportedMPyNode"
    cc = "".join(p[:1].upper() + p[1:] for p in parts)
    if not cc[:1].isalpha() and cc[:1] != "_":
        cc = "Node" + cc
    return cc


def _triple_quote_safe(s: str, quote: str) -> bool:
    """True if ``s`` fits losslessly in a (possibly raw) triple-``quote`` block.

    ``quote`` is ``'"'`` or ``"'"``. A triple-quoted block CANNOT safely hold
    ``s`` when:

      * the triple-``quote`` delimiter occurs in ``s`` (closes the block early);
      * ``s`` ends with ``quote`` (merges with the closing delimiter);
      * ``s`` ends with a backslash (escapes the closing delimiter, and a raw
        string can't end with one either);
      * ``s`` contains a carriage return -- Python's source tokenizer rewrites
        ``\\r`` -> ``\\n`` (universal newlines) regardless of delimiter or raw
        prefix, silently corrupting the round trip.

    The first two are quote-specific (so swapping ``\"\"\"`` <-> ``'''`` can
    dodge them); the last two doom every triple-quoted form -> accumulator.
    """
    if "\r" in s or s.endswith("\\"):
        return False
    return (quote * 3) not in s and not s.endswith(quote)


def _expr_literal(s: str):
    """A readable source literal for expression ``s`` -- or ``None`` if no
    triple-quoted block is safe (caller must use the line-by-line accumulator).

    Prefers a triple-DOUBLE-quote block; falls back to triple-SINGLE-quote only
    when the text embeds or ends with ``\"\"\"`` (so a ``\"\"\"`` docstring inside
    the expression, or a trailing ``\"``, becomes a clean ``'''...'''`` block
    instead of the verbose accumulator). A raw (``r``) prefix is added whenever
    ``s`` contains a backslash so regex escapes survive verbatim. Returns
    ``None`` only when BOTH delimiters collide, or the text ends with a
    backslash, or contains a carriage return.
    """
    prefix = "r" if "\\" in s else ""
    if _triple_quote_safe(s, '"'):
        return '%s"""%s"""' % (prefix, s)
    if _triple_quote_safe(s, "'"):
        return "%s'''%s'''" % (prefix, s)
    return None


def _accumulator_lines(var: str, s: str, indent: str) -> list:
    """Build expression ``s`` line-by-line into ``var`` -- readable + exact.

    Each physical line of ``s`` becomes one ``var = "...\\n"`` / ``var +=
    "...\\n"`` statement, e.g.::

        exp = "import x\\n"
        exp += "x.start()\\n"
        exp += "\\n"
        exp += "x.stop()\\n"

    The per-line literal is produced with ``repr()``, which always round-trips
    exactly and auto-picks a safe quote style -- so even an embedded docstring,
    a trailing quote, or a trailing backslash (the cases a triple-quoted block
    can't hold) survive verbatim. ``s`` is rebuilt as ``"\\n".join(parts)``: each
    part but the last carries a trailing ``\\n``; a final empty part (i.e. ``s``
    ended in a newline) is already covered by the previous line's ``\\n``.
    """
    s = s or ""
    parts = s.split("\n")
    segs = []
    for i, p in enumerate(parts):
        if i == len(parts) - 1:
            if p == "":
                continue  # trailing newline already carried by the prior segment
            segs.append(p)
        else:
            segs.append(p + "\n")
    if not segs:  # s was "" -> assign an empty string
        return ['%s%s = ""' % (indent, var)]
    out = []
    for j, seg in enumerate(segs):
        op = "=" if j == 0 else "+="
        out.append("%s%s %s %r" % (indent, var, op, seg))
    return out


def _body_line_count(src: str) -> int:
    """How many lines the user's expression has -- what the API view prints as
    ``‹ N lines ›``. The EDITOR's count, not the literal's: a trailing newline
    closes the last line rather than opening an empty one, and the closing
    delimiter's own line is nobody's."""
    s = src or ""
    if not s:
        return 0
    parts = s.split("\n")
    if parts[-1] == "":
        parts.pop()
    return max(1, len(parts))


def _emit_set_expression(lines: list, method: str, src: str, indent: str = "        "):
    """Append the source that calls ``node.<method>(<src>)``.

    Normal expressions go inline as a readable triple-quoted block, switching
    the delimiter (``\"\"\"`` <-> ``'''``) to dodge a quote collision. Only when
    BOTH triple-quote styles collide -- or the text ends with a backslash or
    contains a carriage return, which no triple-quoted block can hold -- do we
    build it up line-by-line into ``exp`` (each line a ``repr()``, always exact).

    Returns a small dict describing what was emitted, for
    :func:`generate_node_script_with_regions`. ``body_col`` is the column on the
    FIRST emitted line at which the user's own text starts: the opening
    delimiter and the user's first body line share one physical line, so a
    viewer that marks whole lines as generated cannot be honest here without it.
    ``call_offset`` is which emitted line carries the CALL (0 inline; after the
    accumulator statements in the escaped form) and ``body_lines`` the user's
    own line count -- together they are what the API view paints as
    ``node.<method>(‹ N lines ›)`` over the call line.
    """
    lit = _expr_literal(src)
    body_lines = _body_line_count(src)
    if lit is None:
        acc = _accumulator_lines("exp", src, indent)
        lines.extend(acc)
        lines.append("%snode.%s(exp)" % (indent, method))
        # No rail shared with the body: the CALL is the last line, after the
        # accumulator statements, and ``open_col`` is where its argument starts.
        return {"inline": False, "body_col": None,
                "open_col": len(indent) + len("node.%s(" % method),
                "call_offset": len(acc), "body_lines": body_lines}
    lines.append("%snode.%s(%s)" % (indent, method, lit))
    # ``lit`` is <prefix><q3><src><q3>, and the prefix is an ``r`` whenever the
    # text holds a backslash -- so measure the opener off the literal rather
    # than assuming three delimiter characters.
    open_col = len(indent) + len("node.%s(" % method)
    return {
        "inline": True,
        # Where the CALL's argument begins -- the opening delimiter itself.
        # A folded rail covers from HERE rather than from body_col, so the
        # reader is not left looking at a bare ''' and the first
        # character of a body that is not being displayed.
        "open_col": open_col,
        "body_col": open_col + (len(lit) - len(src) - 3),
        "call_offset": 0,
        "body_lines": body_lines,
    }


_NUMERIC_LIMIT_KEYS = ("min_value", "max_value", "default_value")


def _attr_call(method: str, attr_name: str, meta: dict) -> str:
    """One ``node.add_input_attr(...)`` / ``add_output_attr(...)`` line."""
    parts = [repr(attr_name), repr(meta.get("attr_type", "float"))]
    if meta.get("is_array"):
        parts.append("is_array=True")
        # sparse is INPUT-array-only (default False = dense), so emit only the
        # deviation and gate on the method -- add_output_attr has no such param.
        if method == "add_input_attr" and meta.get("sparse"):
            parts.append("sparse=True")
        # packed is likewise INPUT-array-only and must round-trip: it selects a
        # typed-array plug rather than a multi.
        if method == "add_input_attr" and meta.get("packed"):
            parts.append("packed=True")
    if meta.get("enum_names"):
        parts.append("enum_names=%r" % (list(meta["enum_names"]),))
    for k in _NUMERIC_LIMIT_KEYS:
        v = meta.get(k)
        if v is not None:
            parts.append("%s=%r" % (k, v))
    return "        node.%s(%s)" % (method, ", ".join(parts))


def _indent_block(src: str, indent: str = "    ") -> str:
    """Re-indent ``src`` by ``indent`` (blank lines stay blank). Used to drop a
    top-level Methods ``def`` into a class body as a real member."""
    out = []
    for line in (src or "").splitlines():
        out.append(indent + line if line.strip() else line)
    return "\n".join(out)


def _top_level_import_lines(methods_src: str):
    """Verbatim source of every top-level ``import`` / ``from ... import`` in
    ``methods_src`` (source order, de-duplicated by exact segment).

    The Methods defs are baked as real members (methods on the class, free
    functions at module scope), so any module-level symbols those bodies refer
    to (``cmds``, ``np``, ...) need their imports hoisted to the generated
    module too, or the rebuilt node NameErrors when the member is called.

    Two skips: the ``maya_command`` marker import (already emitted explicitly
    by ``generate_node_script``) and ``import maya.cmds as mc`` (also already
    emitted as the script's own helper). Never raises -- a SyntaxError or
    failure to slice yields ``[]`` so the bake still succeeds.
    """
    try:
        tree = ast.parse(methods_src or "")
    except (SyntaxError, ValueError):
        return []
    seen = set()
    out = []
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        try:
            seg = ast.get_source_segment(methods_src, stmt)
        except Exception:
            seg = None
        if not seg:
            continue
        # Skip the marker import -- generate_node_script emits it explicitly.
        if ("maya_command" in seg
                and "mpynode._common.methods.maya_command" in seg):
            continue
        # Skip `import maya.cmds as mc` (already emitted as the script helper).
        if seg.strip() == "import maya.cmds as mc":
            continue
        if seg in seen:
            continue
        seen.add(seg)
        out.append(seg)
    return out


# Names already produced by ``generate_node_script`` -- a Methods def carrying
# any of these would shadow the generated classmethod and break the rebuild.
_RESERVED_MEMBER_NAMES = frozenset({"build", "ls", "create", "create_on"})

# The two AUTHORING HOOKS, resolved by name out of the Methods namespace rather
# than off the wrapper (``methods_registry`` exposes run_setup / run_demo, never
# bare setup / demo). Neither resolves on ANY of the 12 wrappers today, so this
# is future-proofing: should a wrapper ever grow either name, the base-shadow
# guard below must NOT start stripping the hooks out of every bake -- ``demo``
# appears in 43/43 shipped template sources and ``setup`` in 34/43.
_BASE_SHADOW_EXEMPT = frozenset({"setup", "demo"})


def _has_maya_demo(decs) -> bool:
    """True if any decorator in ``decs`` is the ``maya_demo`` marker (bare,
    parameterized, or attribute form). A marked def belongs in the class body
    regardless of its first parameter."""
    for d in decs:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Name) and target.id == "maya_demo":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "maya_demo":
            return True
    return False


def _classify_funcdef(fn) -> tuple:
    """Classify an ``ast.FunctionDef`` for the one-way bake.

    Returns ``("class", add_classmethod)`` when the def is a METHOD (belongs in
    the class body) or ``("module", False)`` when it is a plain free function
    (belongs at MODULE scope). A def is a method when it carries
    ``@classmethod``/``@staticmethod`` or its first parameter is ``self``/``cls``.
    ``add_classmethod`` is True only for a ``cls``-first def that lacks an
    explicit ``@classmethod`` -- adding it keeps the baked class valid Python
    (``Foo.setup()`` binds ``cls`` correctly). Everything else (first param not
    ``self``/``cls``, or no params) is a free function hoisted to module scope,
    so it stays callable exactly as written.
    """
    decs = fn.decorator_list
    has_classmethod = any(
        isinstance(d, ast.Name) and d.id == "classmethod" for d in decs
    )
    has_staticmethod = any(
        isinstance(d, ast.Name) and d.id == "staticmethod" for d in decs
    )
    first = fn.args.args[0].arg if fn.args.args else None
    if has_classmethod or has_staticmethod:
        return ("class", False)
    if _has_maya_demo(decs):
        # Class member; a cls-first factory still needs @classmethod added.
        return ("class", first == "cls")
    if first == "self":
        return ("class", False)
    if first == "cls":
        return ("class", True)
    return ("module", False)


def _method_kind(body_src: str) -> tuple:
    """``_classify_funcdef`` for the first top-level def in ``body_src`` (a slice
    from ``_all_method_defs``). A parse failure or a slice with no def keeps it
    as a plain class member (``("class", False)``) -- the conservative default.
    """
    try:
        tree = ast.parse(body_src or "")
    except (SyntaxError, ValueError):
        return ("class", False)
    for stmt in tree.body:
        if isinstance(stmt, ast.FunctionDef):
            return _classify_funcdef(stmt)
    return ("class", False)


def _stmt_line(stmt) -> int:
    """1-based line in the Methods source where ``stmt``'s emitted text starts.

    Decorators are part of the slice ``_node_source`` returns, so a decorated
    def starts at its FIRST decorator, not at ``stmt.lineno`` -- otherwise a
    navigator jump lands one line below ``@maya_command`` and the badge that
    makes the def a command scrolls off the top.
    """
    first = getattr(stmt, "lineno", 1)
    for deco in getattr(stmt, "decorator_list", None) or ():
        first = min(first, getattr(deco, "lineno", first))
    return int(first)


def _stmt_kind(stmt) -> str:
    """Coarse label for a module-scope statement, for the navigator's Kind
    column. Only the shapes the hoist actually emits are named; anything else
    falls back to the node's own class name lowercased."""
    if isinstance(stmt, ast.ClassDef):
        return "class"
    if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return "constant"
    return type(stmt).__name__.lower()


def _stmt_name(stmt):
    """Bound name of a module-scope statement, or None when it has no single
    one (a tuple unpack, an expression statement)."""
    if isinstance(stmt, ast.ClassDef):
        return stmt.name
    target = None
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        target = stmt.targets[0]
    elif isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
        target = stmt.target
    if isinstance(target, ast.Name):
        return target.id
    return None


def _module_level_nonimport_segments(methods_src: str):
    """Verbatim source of every top-level statement in ``methods_src`` that must
    live at MODULE scope in the bake -- EXCLUDING imports (handled separately by
    ``_top_level_import_lines``).

    This covers plain free functions (no ``self``/``cls``, not
    ``@classmethod``/``@staticmethod``) AND any non-``def`` statement: module
    constants, assignments, helper classes. A baked method that references such
    a symbol resolves it as a module global at call time, so without this hoist
    the rebuilt node would NameError (the old exporter hoisted imports only).

    Source order is preserved so a constant that references an earlier one (or
    an import) still evaluates. ``AsyncFunctionDef`` is skipped (mirrors
    ``_all_method_defs``). Never raises -- yields ``[]`` on failure so the bake
    still succeeds.

    Each entry is ``{"src", "kind", "name", "lineno"}``; ``lineno`` is 1-based
    in ``methods_src`` and lets the region map point a navigator row back at the
    line the user actually edits.
    """
    try:
        tree = ast.parse(methods_src or "")
    except (SyntaxError, ValueError):
        return []
    try:
        from mpynode._common.methods.maya_command import _node_source
    except Exception:  # pragma: no cover - defensive
        return []
    out = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue  # hoisted by _top_level_import_lines
        if isinstance(stmt, ast.AsyncFunctionDef):
            continue
        if isinstance(stmt, ast.FunctionDef):
            kind, _add_cm = _classify_funcdef(stmt)
            if kind != "module":
                continue  # a method -> emitted in the class body
            seg = _node_source(methods_src, stmt)
            if seg:
                out.append({"src": seg, "kind": "function",
                            "name": stmt.name, "lineno": _stmt_line(stmt)})
            continue
        # Any other top-level statement (constant / assignment / helper class).
        try:
            seg = ast.get_source_segment(methods_src, stmt)
        except Exception:
            seg = None
        if seg:
            out.append({"src": seg, "kind": _stmt_kind(stmt),
                        "name": _stmt_name(stmt) or seg.split("\n", 1)[0].strip(),
                        "lineno": _stmt_line(stmt)})
    return out


def _all_method_defs(methods_src: str):
    """All top-level ``def``s in ``methods_src``, in source order.

    Each entry is ``{"func_name": str, "body_src": str, "lineno": int}``;
    decorators are preserved verbatim (so a ``@maya_command`` def emits as-is
    when re-inserted into the class) and ``lineno`` is 1-based in
    ``methods_src``, counting from the first decorator so it addresses the same
    slice ``body_src`` holds. ``AsyncFunctionDef`` is intentionally excluded --
    it cannot be a Maya command (and the static detector warns about it
    separately). Never raises.
    """
    try:
        tree = ast.parse(methods_src or "")
    except (SyntaxError, ValueError):
        return []
    # Reuse maya_command._node_source so the decorator slice matches what
    # detect_commands returns -- one source of truth for "def source + decos".
    try:
        from mpynode._common.methods.maya_command import _node_source
    except Exception:  # pragma: no cover - defensive
        return []
    out = []
    for stmt in tree.body:
        if not isinstance(stmt, ast.FunctionDef):
            continue
        body = _node_source(methods_src, stmt)
        if not body:
            continue
        out.append({"func_name": stmt.name, "body_src": body,
                    "lineno": _stmt_line(stmt)})
    return out


def generate_node_script_with_regions(py_node, *, class_name: str | None = None):
    """Return ``(source, regions)``.

    ``source`` is exactly what :func:`generate_node_script` returns. ``regions``
    is a REGION MAP describing which physical lines this generator owns and
    which carry the user's own text -- what the Script tab's API view needs to
    fold bodies, mark generated lines and route a click back to the tier that
    owns it.

    Each region is a dict:

    ``kind``      one of the block names below (``header``, ``expr_init``, ...)
    ``start`` /
    ``end``       0-based PHYSICAL line indices into ``source``, inclusive
    ``editable``  True when the lines carry user text that round-trips
    ``owner``     the setter the text round-trips through, or None
    ``label``     a display name (tier, member, segment), or None

    Expression regions additionally carry ``body_col`` / ``open_col`` /
    ``call_offset`` / ``body_lines`` -- see :func:`_emit_set_expression`.

    The map is built by the SAME pass that builds the text, so the two cannot
    disagree. A parallel walker would have to duplicate the emission ORDER,
    which is the one thing the helpers in this module do not encapsulate.
    """
    wrapper_cls = type(py_node)
    native_type = getattr(wrapper_cls, "NATIVE_TYPE", "mPyNode")
    uses_mesh = hasattr(wrapper_cls, "create_on")  # deformer-family creator

    # ALWAYS the registry ROOT wrapper, never the live logical subclass: a user
    # subclass isn't exported at ``mpynode`` top level so ``from mpynode import
    # <Sub>`` would break. All 13 root wrappers ARE exported there.
    # ``base_cls`` shadows ``base_name``'s lifecycle exactly, so the shadow guard
    # below always probes the class the baked ``class X(<base_name>)`` inherits.
    base_name = wrapper_cls.__name__
    base_cls = wrapper_cls
    try:
        from mpynode._node_registry import get_spec

        spec = get_spec(native_type)
        if spec is not None:
            root_cls = spec.get_wrapper_class()
            if isinstance(root_cls, type):
                base_name = root_cls.__name__
                base_cls = root_cls
    except Exception:
        pass

    # Class name comes from IDENTITY, never the node name: caller-supplied wins,
    # else the stamped ``_pyClass`` short name, else the root wrapper name.
    if not class_name:
        pc = None
        try:
            pc = py_node.get_py_class()
        except Exception:
            pc = None
        if pc:
            class_name = pc.rpartition(".")[2]
        if not class_name:
            class_name = base_name
    default_name = class_name[:1].lower() + class_name[1:] + "#"

    def _safe(getter, default):
        try:
            return getter() or default
        except Exception:
            return default

    input_attrs: dict = _safe(py_node.get_input_attr_map, {})
    output_attrs: dict = _safe(py_node.get_output_attr_map, {})
    init_src: str = _safe(py_node.get_init_expression, "")
    compute_src: str = _safe(py_node.get_compute_expression, "")
    # Viewport exists only on some types (e.g. mPyFile, via ViewportSourceMixin).
    # Emit only when supported, else the rebuild AttributeErrors on a mPyNode.
    viewport_src: str = ""
    if hasattr(py_node, "get_viewport_expression"):
        viewport_src = _safe(py_node.get_viewport_expression, "")
    # OSL is opt-in the same way (OslSourceMixin), and .mpn already round-trips
    # it via osl_source -- so omitting it here silently DROPPED the tier on bake.
    osl_src: str = ""
    if hasattr(py_node, "get_osl_expression"):
        osl_src = _safe(py_node.get_osl_expression, "")
    var_names = _safe(py_node.get_variable_names, [])
    # Methods tier -- only on wrappers exposing get_methods_source.
    methods_src: str = ""
    if hasattr(py_node, "get_methods_source"):
        methods_src = _safe(py_node.get_methods_source, "")
    command_defs = []
    if methods_src:
        try:
            from mpynode._common.methods.maya_command import detect_commands

            command_defs = detect_commands(methods_src)
        except Exception:
            command_defs = []
    demo_defs = []
    if methods_src:
        try:
            from mpynode._common.methods.maya_command import detect_demos

            demo_defs = detect_demos(methods_src)
        except Exception:
            demo_defs = []
    test_defs = []
    if methods_src:
        try:
            from mpynode._common.methods.maya_command import detect_tests

            test_defs = detect_tests(methods_src)
        except Exception:
            test_defs = []

    # Per-node blank-line overrides. Empty for every node that has never had a
    # boundary moved by hand, which is what keeps the default bake unchanged.
    gap_spacing = {}
    _get_gaps = getattr(py_node, "get_api_gap_spacing", None)
    if _get_gaps is not None:
        try:
            gap_spacing = _get_gaps() or {}
        except Exception:  # noqa: BLE001
            gap_spacing = {}

    L: list[str] = []
    # Region marks, recorded as L INDICES while emitting and converted to
    # physical line numbers in one pass at the end -- L entries are multi-line
    # (the header, a module segment, a whole triple-quoted expression), so a
    # line number is not knowable until every entry exists.
    marks: list = []

    def mark(kind, i0, editable=False, owner=None, label=None, **extra):
        marks.append((kind, i0, len(L), editable, owner, label, extra or None))

    def gap(kind, label=None):
        """Emit the blank lines that precede a block: the node's stored
        override if it has one, otherwise the spacing this exporter has always
        used. Called where the literal ``L.append("")`` runs used to be, so the
        default path appends exactly the same lines in the same order."""
        for _ in range(gap_spacing.get(gap_key(kind, label),
                                       _DEFAULT_GAP.get(kind, 0))):
            L.append("")

    # The Node Info metadata as a generated banner, above everything. Merged
    # over the global prefs defaults exactly as a compile merges them, so the
    # baked .py and the compiled node carry the SAME license rather than the
    # bake silently dropping a studio default the compile picked up.
    #
    # Skipped entirely when there is nothing to say. There is no build line here
    # (nothing stamps one -- a bake does not compile), so empty metadata would
    # leave two bars and a "Generated by": per-node boilerplate above the user's
    # own code, which is precisely what BAKE_CONTRACT was deleted for.
    # The whole thing is behind one preference (default ON). The merge has to
    # sit inside that gate too: with it off but the merge still running, a
    # studio-wide default license would keep producing a banner on every node
    # and the switch would look broken.
    meta = {}
    if md.bake_header_enabled():
        _get_meta = getattr(py_node, "get_metadata", None)
        if _get_meta is not None:
            try:
                meta = _get_meta() or {}
            except Exception:  # noqa: BLE001
                meta = {}
        meta = md.merge_metadata(meta, md.prefs_defaults())
    # generator: NOT the DEFAULT_VENDOR "mpynode-native" -- that is the compiled
    # tier's vendor, and this file is not compiled. Same name the rest of the
    # bake surface uses for the authoring tool.
    _banner = md.banner_lines(meta, generator="Node Designer", prefix="#",
                              build=False)
    # NOT is_empty(): that counts `type_id`, which pins the compiled MTypeId,
    # renders no banner line and means nothing in a .py -- so a node carrying
    # only a pinned id would bake two bars around a lone "Generated by".
    # Comparing against the genuinely-empty banner asks the real question ("did
    # any field render?") without restating which fields banner_lines emits.
    if len(_banner) > len(md.banner_lines({}, prefix="#", build=False)):
        gap("metadata")
        _i = len(L)
        L.append("\n".join(_banner))
        # The separator below the banner is INSIDE the region, like the header's
        # keep_blanks trailing blank. Left outside it would be an unmarked blank
        # above the `header` block, and NDApiView._spacing_from_document counts
        # those as a user override -- so `header` (default 0) would come back as
        # 1, and the next bake would emit that blank a second time. Same defect
        # its `imports` branch already sidesteps. Owning it costs nothing: the
        # region is generated, so nothing writes back.
        L.append("")
        mark("metadata", _i)

    # The user's own file header, if they wrote one, ABOVE the imports -- the
    # only place a header can be. There is no generated preamble any more; see
    # BAKE_CONTRACT. The metadata banner above is not one: it is per-node, and
    # it is what the user typed into Node Info.
    header_src, header_lines = _leading_header_block(methods_src)
    if header_src:
        gap("header")
        _i = len(L)
        L.append(header_src)
        # keep_blanks: the header's own trailing blank line is the separator
        # above the imports and is part of the user's slice, so the write-back
        # must not strip it the way it strips a member's trailing blanks.
        mark("header", _i, editable=True, owner="set_methods_source",
             label="header", symbol_kind="header", keep_blanks=True,
             src_line=1, src_lines=header_lines)
    gap("imports")
    _i = len(L)
    L.append("from mpynode import %s" % base_name)
    L.append("import maya.cmds as mc")
    if command_defs:
        # so the @maya_command decorators below resolve on import.
        L.append("from mpynode._common.methods.maya_command import maya_command")
    if demo_defs:
        # so the @maya_demo decorators below resolve on import.
        L.append("from mpynode._common.methods.maya_command import maya_demo")
    if test_defs:
        # so the @maya_test decorators below resolve on import. Omitting this
        # still COMPILES -- the name only resolves when the class body runs --
        # so every shipped template baked a .py that NameError'd on import.
        L.append("from mpynode._common.methods.maya_command import maya_test")
    mark("imports", _i)
    # Hoist the Methods source's module-level context so baked members resolve
    # their globals: imports first, then free functions + module constants.
    if methods_src:
        gap("imports_hoisted")
        _i = len(L)
        for line in _top_level_import_lines(methods_src):
            L.append(line)
        # NOT editable in place: the hoist DE-DUPLICATES by exact segment and
        # re-orders imports ahead of everything else, so the emitted block is
        # not a contiguous slice of the Methods source and cannot be spliced
        # back. It is a navigable row, not an editable one.
        mark("imports_hoisted", _i, editable=False, owner="set_methods_source",
             label="imports", src_line=1, symbol_kind="import")
        for seg in _module_level_nonimport_segments(methods_src):
            # A leading docstring is already emitted as the file header above.
            # Without this it lands TWICE -- once at the top and once here,
            # where the second copy is a dead string expression and the two
            # editable regions would both splice back to Methods line 1.
            if seg["lineno"] <= header_lines:
                continue
            gap("module_segment", seg["name"])
            _i = len(L)
            L.append(seg["src"])
            mark("module_segment", _i, editable=True,
                 owner="set_methods_source",
                 label=seg["name"],
                 symbol_kind=seg["kind"],
                 src_line=seg["lineno"],
                 src_lines=seg["src"].count("\n") + 1)
    gap("class_decl")
    _i = len(L)
    L.append("class %s(%s):" % (class_name, base_name))
    mark("class_decl", _i, label=class_name, base=base_name)
    gap("build_signature")
    _i = len(L)
    L.append("    @classmethod")
    if uses_mesh:
        L.append('    def build(cls, mesh, name="%s"):' % default_name)
        L.append("        node = cls.create_on(mesh, name=name)")
    else:
        L.append('    def build(cls, name="%s"):' % default_name)
        L.append("        node = cls.create(name=name)")
    mark("build_signature", _i)

    # --- inputs ---
    if input_attrs:
        gap("attrs_in")
        _i = len(L)
        L.append("        # --- inputs ---")
        for nm, meta in input_attrs.items():
            L.append(_attr_call("add_input_attr", nm, meta))
            color = (meta or {}).get("ui_color")
            if color:
                L.append(
                    "        node.set_input_attr_color(%r, %r)" % (nm, color)
                )
        mark("attrs_in", _i, label="Inputs", count=len(input_attrs))

    # --- outputs ---
    if output_attrs:
        gap("attrs_out")
        _i = len(L)
        L.append("        # --- outputs ---")
        for nm, meta in output_attrs.items():
            L.append(_attr_call("add_output_attr", nm, meta))
            color = (meta or {}).get("ui_color")
            if color:
                L.append(
                    "        node.set_output_attr_color(%r, %r)" % (nm, color)
                )
        mark("attrs_out", _i, label="Outputs", count=len(output_attrs))

    # --- expressions ---
    if init_src or compute_src or viewport_src or osl_src:
        gap("expr_header")
        _i = len(L)
        L.append("        # --- expressions ---")
        mark("expr_header", _i)
        # One region per emitted tier, in the same order as before. Looped
        # rather than repeated four times so the mark and the emit can never
        # drift apart.
        for tier, setter, src in (
            ("Init", "set_init_expression", init_src),
            ("Compute", "set_compute_expression", compute_src),
            ("Viewport", "set_viewport_expression", viewport_src),
            ("OSL", "set_osl_expression", osl_src),
        ):
            if not src:
                continue
            gap("expr_%s" % tier.lower())
            _i = len(L)
            info = _emit_set_expression(L, setter, src)
            # The escaped (accumulator) form is repr'd line-by-line, so it is
            # NOT editable in place the way an inline triple-quoted body is.
            mark("expr_%s" % tier.lower(), _i, editable=info["inline"],
                 owner=setter, label=tier,
                 body_col=info["body_col"], open_col=info.get("open_col"),
                 inline=info["inline"],
                 call_offset=info.get("call_offset", 0),
                 body_lines=info.get("body_lines"))

    # --- persistent variables (declarations only) ---
    if var_names:
        gap("vars")
        _i = len(L)
        L.append(
            "        # --- persistent variables (declarations only; "
            "data not included) ---"
        )
        for vn in var_names:
            L.append("        node.add_variable(%r, persistent=True)" % vn)
        mark("vars", _i, label="Variables", count=len(var_names))

    # One-way bake: set_methods_source is deliberately NOT called -- the defs go
    # out as real Python instead (see the module docstring).

    gap("return")
    _i = len(L)
    L.append("        return node")
    mark("return", _i)
    # No ``ls`` classmethod: the class inherits its root wrapper's scoped ls().

    # --- Methods defs baked as REAL class members. Only methods land here
    #     (self-first, @classmethod, @staticmethod); free functions were hoisted
    #     to module scope above. Decorators stay verbatim. Three guards:
    #       * reserved names (build/ls/create/create_on) would shadow the
    #         generated classmethods -- skip + warn;
    #       * a name that resolves on the ROOT WRAPPER would shadow the very
    #         method the body forwards to -- ``def load_target`` returning
    #         ``self.load_target(...)`` is fine interpreted (the Methods func is
    #         never bound to the wrapper) but is REAL recursion once baked into
    #         ``class X(MPyBlendShape)``. Shadowing a PROPERTY is worse: no
    #         error at all, just a bound method where a value was expected.
    #         skip + warn, which leaves the inherited method in place;
    #       * duplicate defs -- keep the FIRST (safer than Python's last-wins
    #         when re-exec'd) and warn on the rest.
    # Authoring role per def name, for the region map only -- it changes no
    # emitted byte. Derived from the SAME detect_* results this function already
    # ran, so a surface reading the regions classifies a def exactly as the bake
    # does; deriving it a second time from outline_model would be the two
    # resolvers that produced the find_demos / detect_demos divergence.
    _roles = {}
    for _d in test_defs:
        _roles[_d["func_name"]] = (
            "test", _d.get("label") or _d["func_name"], ())
    for _d in demo_defs:
        _roles[_d["func_name"]] = (
            "demo", _d.get("label") or _d["func_name"], ())
    for _d in command_defs:
        # ``params`` rides along so a Run can prompt for the command's
        # arguments; without it the navigator could only call it bare.
        _roles[_d["func_name"]] = (
            "command", _d.get("name") or _d["func_name"],
            tuple(_d.get("params") or ()))

    emitted = set()
    for d in _all_method_defs(methods_src):
        kind, add_classmethod = _method_kind(d["body_src"])
        if kind == "module":
            continue  # a plain free function -- emitted at module scope above
        func_name = d["func_name"]
        if func_name in _RESERVED_MEMBER_NAMES:
            gap("method_warning", func_name)
            _i = len(L)
            L.append(
                "    # WARNING: Methods def %r shadows the generated %r "
                "classmethod; skipped." % (func_name, func_name)
            )
            mark("method_warning", _i, label=func_name)
            continue
        # Reserved FIRST: ``build`` is in both sets, and it keeps the message
        # written for it. ``getattr_static`` on the CLASS never runs a
        # descriptor -- ``hasattr`` on an INSTANCE raises out of a property that
        # reads an unconnected plug. Dunders are excluded: every one of them
        # resolves via ``object``.
        if (base_cls is not None
                and func_name not in _BASE_SHADOW_EXEMPT
                and not (func_name.startswith("__")
                         and func_name.endswith("__"))
                and inspect.getattr_static(base_cls, func_name, None) is not None):
            gap("method_warning", func_name)
            _i = len(L)
            L.append(
                "    # WARNING: Methods def %r shadows %s.%s; skipped (the "
                "inherited one is used)." % (func_name, base_name, func_name)
            )
            mark("method_warning", _i, label=func_name)
            continue
        if func_name in emitted:
            gap("method_warning", func_name)
            _i = len(L)
            L.append(
                "    # WARNING: duplicate Methods def %r; later definition "
                "skipped." % func_name
            )
            mark("method_warning", _i, label=func_name)
            continue
        body = (d.get("body_src") or "").strip("\n")
        if not body:
            continue
        emitted.add(func_name)
        gap("method_member", func_name)
        _i = len(L)
        # A cls-first factory must surface as a real @classmethod for the baked
        # class to be valid Python; add it when the author omitted it. A
        # self-first `def setup(self)` correctly gets none. Do NOT add a
        # name-based guard -- it would suppress the @classmethod that
        # test_cls_first_surfaces_as_classmethod asserts for `def setup(cls)`.
        if add_classmethod:
            L.append("    @classmethod")
        L.append(_indent_block(body, "    "))
        # ``setup`` is a role by NAME, not by decorator -- it is the reserved
        # hook _RunSetupCommand runs -- so it is resolved after the decorator
        # roles and never overrides one.
        role, run_name, run_params = _roles.get(func_name, (None, None, ()))
        if role is None and func_name == "setup":
            role, run_name = "setup", func_name
        # ``_classify_funcdef``'s vocabulary is binary -- "class" means "is a
        # method", not "is a class statement" -- so an undecorated member would
        # read as ``class`` beside a real ``class SetupError``. Name it for what
        # it is; the classifier keeps its own vocabulary for the bake.
        mark("method_member", _i, editable=True, owner="set_methods_source",
             label=func_name,
             symbol_kind=role or ("method" if kind == "class" else kind),
             run_kind=role, run_name=run_name, run_params=run_params,
             src_line=d.get("lineno"),
             src_lines=body.count("\n") + 1,
             indent=4,
             # The region mark is taken BEFORE this line is appended, so a
             # synthesized @classmethod is INSIDE the region but has no
             # counterpart in the Methods source. An edit spliced back without
             # dropping it would grow one decorator per save.
             synth_classmethod=bool(add_classmethod))

    L.append("")

    # Entry index -> first physical line. Done in ONE pass here rather than
    # while emitting, because L entries are multi-line and a line number is
    # not knowable until every entry exists.
    offs = []
    pos = 0
    for chunk in L:
        offs.append(pos)
        pos += chunk.count("\n") + 1

    regions = []
    for kind, i0, i1, editable, owner, label, extra in marks:
        if i1 <= i0:
            continue
        region = {
            "kind": kind,
            "start": offs[i0],
            "end": offs[i1 - 1] + L[i1 - 1].count("\n"),
            "editable": editable,
            "owner": owner,
            "label": label,
        }
        if extra:
            region.update(extra)
        regions.append(region)

    return "\n".join(L), regions


def generate_node_script(py_node, *, class_name: str | None = None) -> str:
    """Return a standalone ``.py`` module string that rebuilds ``py_node``."""
    return generate_node_script_with_regions(py_node, class_name=class_name)[0]
