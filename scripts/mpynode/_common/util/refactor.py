"""Scope-aware variable rename for the expression editors.

Pure-Python (no Qt, no Maya) so it stays unit-testable. The engine
parses an expression tab's source with ``ast``, resolves the exact
binding under the cursor using Python's lexical scoping rules, and
rewrites only the occurrences that refer to that same binding.

Design promise: *always either do the correct thing or refuse and
change nothing.* When the engine can't prove a rename is safe
(global/nonlocal, class scope, name collision, dynamic access via
strings) it returns ``ok=False`` with a human-readable ``reason``
and leaves the source untouched. String-literal / ``getattr`` style
references are reported as ``warnings`` (the AST-safe code sites are
still renamed, but the user is told what wasn't touched).

Public entry points:

* ``plan_rename_at(source, lineno, col, new_name, blocked_names)`` --
  rename the binding whose occurrence sits at ``(lineno, col)``.
* ``plan_rename_free_name(source, old_name, new_name, blocked_names)``
  -- rename only module-scope (free/global) occurrences of
  ``old_name``. Used for cross-tab propagation: a name defined in the
  Init tab is injected into the Compute / Viewport namespaces, so a
  module-level rename in one tab must rewrite the free references in
  the siblings.
* ``is_valid_identifier(name)`` -- identifier + non-keyword check.
* ``word_at(source, lineno, col)`` -- the identifier under a cursor.
"""

from __future__ import annotations

import ast
import keyword
from typing import NamedTuple


class RenamePlan(NamedTuple):
    """Result of planning a rename against a single source string."""

    ok:              bool
    new_source:      str | None
    count:           int         # occurrences rewritten in this source
    reason:          str | None  # refusal reason (set iff not ok)
    warnings:        tuple       # non-fatal notes (e.g. string refs)
    old_name:        str
    scope_kind:      str         # module/function/lambda/comprehension/""
    is_module_level: bool        # True => cross-tab propagation candidate


# ---- Identifier helpers ----


def is_valid_identifier(name: str) -> bool:
    """True iff ``name`` is a usable Python identifier (and not a keyword)."""
    return bool(name) and name.isidentifier() and not keyword.iskeyword(name)


_IDENT_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)


def word_at(source: str, lineno: int, col: int) -> str:
    """Return the identifier spanning ``(lineno, col)`` (1-based line,
    0-based char column), or "" if the cursor isn't on an identifier.

    Char-based (not byte-based) so it matches how a Qt text cursor
    reports columns.
    """
    lines = source.splitlines()
    if lineno < 1 or lineno > len(lines):
        return ""
    line = lines[lineno - 1]
    n    = len(line)
    if n == 0:
        return ""
    if col > n:
        col = n
    start = col
    while start > 0 and line[start - 1] in _IDENT_CHARS:
        start -= 1
    end = col
    while end < n and line[end] in _IDENT_CHARS:
        end += 1
    word = line[start:end]
    if not word or word[0].isdigit():
        return ""
    return word


# ---- Scope model ----


class _Scope:
    __slots__ = ("kind", "parent", "bindings", "globals", "nonlocals", "is_class")

    def __init__(self, kind, parent):
        self.kind      = kind
        self.parent    = parent
        self.bindings  = set()
        self.globals   = set()
        self.nonlocals = set()
        self.is_class  = kind == "class"


def _iter_target_names(target):
    """Yield ``ast.Name`` nodes (Store ctx) bound by an assignment
    target. Tuple/List/Starred unpacking is recursed; Attribute /
    Subscript targets bind nothing local."""
    if isinstance(target, ast.Name):
        yield target
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            yield from _iter_target_names(elt)
    elif isinstance(target, ast.Starred):
        yield from _iter_target_names(target.value)


class _Analyzer:
    """Builds the scope tree + a flat map of every Name/arg node to its
    owning scope. Single pass, explicit recursion."""

    def __init__(self):
        self.module      = _Scope("module", None)
        self.node_scope  = {}
        self.occurrences = []
        self.has_class   = False

    def _bind(self, scope, name):
        scope.bindings.add(name)

    def _record_name(self, node, scope):
        self.node_scope[id(node)] = scope
        self.occurrences.append((node, scope))

    def visit(self, node, scope):
        method = getattr(self, "_v_" + type(node).__name__, None)
        if method is not None:
            method(node, scope)
        else:
            self._generic(node, scope)

    def _generic(self, node, scope):
        for child in ast.iter_child_nodes(node):
            self.visit(child, scope)

    def _v_Name(self, node, scope):
        if isinstance(node.ctx, ast.Store):
            self._bind(scope, node.id)
        self._record_name(node, scope)

    def _v_arg(self, node, scope):
        self._bind(scope, node.arg)
        self._record_name(node, scope)

    def _v_Assign(self, node, scope):
        self.visit(node.value, scope)
        for t in node.targets:
            self.visit(t, scope)

    def _v_AnnAssign(self, node, scope):
        if node.value is not None:
            self.visit(node.value, scope)
        if node.annotation is not None:
            self.visit(node.annotation, scope)
        self.visit(node.target, scope)

    def _v_AugAssign(self, node, scope):
        self.visit(node.value, scope)
        self.visit(node.target, scope)

    def _v_NamedExpr(self, node, scope):  # walrus :=
        self.visit(node.value, scope)
        target = node.target
        if isinstance(target, ast.Name):
            bind_scope = scope
            while bind_scope.kind == "comprehension" and bind_scope.parent is not None:
                bind_scope = bind_scope.parent
            self._bind(bind_scope, target.id)
            self.node_scope[id(target)] = bind_scope
            self.occurrences.append((target, bind_scope))
        else:
            self.visit(target, scope)

    def _v_Global(self, node, scope):
        for n in node.names:
            scope.globals.add(n)

    def _v_Nonlocal(self, node, scope):
        for n in node.names:
            scope.nonlocals.add(n)

    def _v_Import(self, node, scope):
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self._bind(scope, bound)

    def _v_ImportFrom(self, node, scope):
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name
            self._bind(scope, bound)

    def _v_For(self, node, scope):
        self.visit(node.iter, scope)
        self.visit(node.target, scope)
        for n in node.body:
            self.visit(n, scope)
        for n in node.orelse:
            self.visit(n, scope)

    _v_AsyncFor = _v_For

    def _v_withitem(self, node, scope):
        self.visit(node.context_expr, scope)
        if node.optional_vars is not None:
            self.visit(node.optional_vars, scope)

    def _v_ExceptHandler(self, node, scope):
        if node.type is not None:
            self.visit(node.type, scope)
        if node.name:
            self._bind(scope, node.name)
        for n in node.body:
            self.visit(n, scope)

    def _function_like(self, node, scope, kind):
        for dec in getattr(node, "decorator_list", []):
            self.visit(dec, scope)
        args = node.args
        for default in list(args.defaults) + [d for d in args.kw_defaults if d]:
            self.visit(default, scope)
        for a in _all_args(args):
            if a.annotation is not None:
                self.visit(a.annotation, scope)
        if getattr(node, "returns", None) is not None:
            self.visit(node.returns, scope)
        if kind == "function":
            self._bind(scope, node.name)
        inner = _Scope(kind, scope)
        for a in _all_args(args):
            self._bind(inner, a.arg)
            self.node_scope[id(a)] = inner
            self.occurrences.append((a, inner))
        body = node.body
        if isinstance(body, list):
            for n in body:
                self.visit(n, inner)
        else:
            self.visit(body, inner)

    def _v_FunctionDef(self, node, scope):
        self._function_like(node, scope, "function")

    _v_AsyncFunctionDef = _v_FunctionDef

    def _v_Lambda(self, node, scope):
        self._function_like(node, scope, "lambda")

    def _v_ClassDef(self, node, scope):
        self.has_class = True
        for dec in node.decorator_list:
            self.visit(dec, scope)
        for base in node.bases:
            self.visit(base, scope)
        for kw in node.keywords:
            self.visit(kw.value, scope)
        self._bind(scope, node.name)
        inner = _Scope("class", scope)
        for n in node.body:
            self.visit(n, inner)

    def _comprehension(self, node, scope):
        inner = _Scope("comprehension", scope)
        gens  = node.generators
        for i, gen in enumerate(gens):
            if i == 0:
                self.visit(gen.iter, scope)
            else:
                self.visit(gen.iter, inner)
            self.visit(gen.target, inner)
            for cond in gen.ifs:
                self.visit(cond, inner)
        if isinstance(node, ast.DictComp):
            self.visit(node.key, inner)
            self.visit(node.value, inner)
        else:
            self.visit(node.elt, inner)

    _v_ListComp     = _comprehension
    _v_SetComp      = _comprehension
    _v_GeneratorExp = _comprehension
    _v_DictComp     = _comprehension


def _all_args(args):
    out = list(getattr(args, "posonlyargs", []))
    out += list(args.args)
    if args.vararg:
        out.append(args.vararg)
    out += list(args.kwonlyargs)
    if args.kwarg:
        out.append(args.kwarg)
    return out


# ---- Resolution ----


def _resolve(name, scope, module):
    """Return the scope that owns ``name`` as seen from ``scope`` (LEGB).
    Module scope for free/global/builtin names; None for malformed
    nonlocal so callers can refuse."""
    s     = scope
    first = True
    while s is not None:
        if name in s.globals:
            return module
        if name in s.nonlocals:
            t = s.parent
            while t is not None:
                if t.kind in ("function", "lambda") and name in t.bindings:
                    return t
                t = t.parent
            return None
        if name in s.bindings:
            if s.is_class and not first:
                pass
            else:
                return s
        first = False
        s     = s.parent
    return module


# ---- Rewriting ----


def _node_span(node):
    return (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)


def _rewrite(source, nodes, new_name):
    """Replace each node's source span with ``new_name`` (per-line, on
    the UTF-8 byte representation since ast col offsets are byte-based;
    right-to-left within a line so spans don't shift)."""
    lines   = source.splitlines(keepends=True)
    by_line = {}
    for node in nodes:
        lineno, col, end_lineno, end_col = _node_span(node)
        if end_lineno != lineno:
            continue
        by_line.setdefault(lineno, []).append((col, end_col))
    new_bytes = new_name.encode("utf-8")
    for lineno, spans in by_line.items():
        if lineno < 1 or lineno > len(lines):
            continue
        raw = lines[lineno - 1].encode("utf-8")
        for col, end_col in sorted(spans, reverse=True):
            raw = raw[:col] + new_bytes + raw[end_col:]
        lines[lineno - 1] = raw.decode("utf-8")
    return "".join(lines)


# ---- Dynamic-reference scan (warnings only) ----


def _dynamic_warnings(tree, name):
    """Flag string-literal references a static rename can't follow
    (getattr/setattr/globals/eval/exec). Returns warning strings."""
    warns     = []
    dyn_funcs = {"getattr", "setattr", "hasattr", "delattr"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn      = node.func
            fn_name = None
            if isinstance(fn, ast.Name):
                fn_name = fn.id
            elif isinstance(fn, ast.Attribute):
                fn_name = fn.attr
            if fn_name in dyn_funcs:
                for a in node.args:
                    if isinstance(a, ast.Constant) and a.value == name:
                        warns.append(
                            f"dynamic {fn_name}(..., {name!r}) at line "
                            f"{getattr(node, 'lineno', '?')} not renamed"
                        )
            if fn_name in ("eval", "exec"):
                warns.append(
                    f"{fn_name}() at line {getattr(node, 'lineno', '?')} "
                    "may reference the name dynamically"
                )
    return warns


# ---- Public planning entry points ----


def _plan(source, new_name, *, target_pos=None, target_name=None,
          module_only=False, blocked_names=frozenset()):
    if not is_valid_identifier(new_name):
        return RenamePlan(
            False, None, 0,
            f"{new_name!r} is not a valid Python identifier",
            (), target_name or "", "", False,
        )

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return RenamePlan(
            False, None, 0,
            f"cannot rename: source has a syntax error ({exc.msg})",
            (), target_name or "", "", False,
        )

    analyzer = _Analyzer()
    analyzer.visit(tree, analyzer.module)
    module = analyzer.module

    if target_pos is not None:
        # Locate the Name/arg occurrence at (lineno, byte_col) within
        # THIS analyzer's tree (same parse -> id() lookups are valid).
        lineno, byte_col, name_hint = target_pos
        target_node = None
        for node, _sc in analyzer.occurrences:
            nm = node.id if isinstance(node, ast.Name) else node.arg
            if nm != name_hint or node.lineno != lineno:
                continue
            if node.col_offset <= byte_col <= node.end_col_offset:
                target_node = node
                break
        if target_node is None:
            return RenamePlan(
                False, None, 0,
                f"{name_hint!r} under the cursor isn't a variable "
                "reference (it may be an attribute, string, or keyword)",
                (), name_hint, "", False,
            )
        old_name = (
            target_node.id if isinstance(target_node, ast.Name)
            else target_node.arg
        )
        start_scope = analyzer.node_scope.get(id(target_node))
        defining    = _resolve(old_name, start_scope, module)
    else:
        target_node = None
        old_name    = target_name
        defining    = module
        start_scope = module

    if old_name in blocked_names:
        return RenamePlan(
            False, None, 0,
            f"{old_name!r} is a framework/built-in name and can't be renamed",
            (), old_name, "", False,
        )
    if not is_valid_identifier(old_name):
        return RenamePlan(
            False, None, 0,
            f"{old_name!r} is not a renameable identifier",
            (), old_name, "", False,
        )
    if defining is None:
        return RenamePlan(
            False, None, 0,
            f"{old_name!r} uses global/nonlocal in a way the renamer "
            "can't resolve safely",
            (), old_name, "", False,
        )
    if defining.is_class or (target_node is not None and start_scope.is_class):
        return RenamePlan(
            False, None, 0,
            "renaming inside a class body isn't supported",
            (), old_name, defining.kind, False,
        )

    def _declared_special(name):
        for _node, sc in analyzer.occurrences:
            s = sc
            while s is not None:
                if name in s.globals or name in s.nonlocals:
                    return True
                s = s.parent
        return False

    if _declared_special(old_name):
        return RenamePlan(
            False, None, 0,
            f"{old_name!r} is declared global/nonlocal somewhere; "
            "rename isn't supported for those",
            (), old_name, defining.kind, defining is module,
        )

    targets = []
    for node, sc in analyzer.occurrences:
        nm = node.id if isinstance(node, ast.Name) else node.arg
        if nm != old_name:
            continue
        if module_only:
            if _resolve(nm, sc, module) is module:
                targets.append(node)
        else:
            if _resolve(nm, sc, module) is defining:
                targets.append(node)

    if not targets:
        return RenamePlan(
            False, None, 0,
            f"no renameable occurrences of {old_name!r} found",
            (), old_name, defining.kind, defining is module,
        )

    collide_scope = module if module_only else defining
    if new_name in collide_scope.bindings:
        return RenamePlan(
            False, None, 0,
            f"{new_name!r} already exists in this scope; renaming would "
            "merge two different variables",
            (), old_name, defining.kind, defining is module,
        )

    warnings   = tuple(_dynamic_warnings(tree, old_name))
    new_source = _rewrite(source, targets, new_name)

    try:
        ast.parse(new_source)
    except SyntaxError:
        return RenamePlan(
            False, None, 0,
            "internal error: rewrite produced invalid source (aborted)",
            (), old_name, defining.kind, defining is module,
        )

    return RenamePlan(
        True, new_source, len(targets), None, warnings,
        old_name, defining.kind, defining is module,
    )


def plan_rename_at(source, lineno, col, new_name, *, blocked_names=frozenset()):
    """Plan a rename for the variable whose occurrence sits at
    ``(lineno, col)`` (1-based line, 0-based char column)."""
    old_name = word_at(source, lineno, col)
    if not old_name:
        return RenamePlan(
            False, None, 0, "no identifier under the cursor",
            (), "", "", False,
        )
    # Convert the char column to a UTF-8 byte column (ast offsets are
    # byte-based). The node lookup happens inside _plan against its own
    # parse so id() comparisons stay valid.
    lines    = source.splitlines()
    line_txt = lines[lineno - 1] if 1 <= lineno <= len(lines) else ""
    byte_col = len(line_txt[:col].encode("utf-8"))
    return _plan(
        source, new_name,
        target_pos    = (lineno, byte_col, old_name),
        blocked_names = blocked_names,
    )


def plan_rename_free_name(source, old_name, new_name, *, blocked_names=frozenset()):
    """Plan a rename of only the module-scope (free/global) occurrences
    of ``old_name`` -- used to propagate an Init-tab rename into the
    Compute / Viewport tabs that share its namespace."""
    return _plan(
        source, new_name,
        target_name=old_name, module_only=True,
        blocked_names=blocked_names,
    )


# ---- self.X attribute classification + rename ----


def classify_at(source: str, lineno: int, col: int):
    """Classify the token at ``(lineno, col)`` (1-based line, 0-based
    char col). Returns a ``(kind, name)`` tuple:

      * ``("self_attr", attr)`` -- the ``.attr`` of a ``self.attr``
        access (Case B: a plug / stored-var rename).
      * ``("name", ident)``     -- a plain local-variable reference
        (Case A).
      * ``("none", "")``        -- not on an identifier.
      * ``("other", word)``     -- an identifier the engine won\'t
        treat as a local (e.g. a non-self attribute, or unparseable).
    """
    word = word_at(source, lineno, col)
    if not word:
        return ("none", "")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Best-effort heuristic when the buffer doesn\'t parse.
        lines = source.splitlines()
        line  = lines[lineno - 1] if 1 <= lineno <= len(lines) else ""
        start = col
        while start > 0 and line[start - 1] in _IDENT_CHARS:
            start -= 1
        if line[:start].endswith("self."):
            return ("self_attr", word)
        return ("name", word)

    lines    = source.splitlines()
    line_txt = lines[lineno - 1] if 1 <= lineno <= len(lines) else ""
    byte_col = len(line_txt[:col].encode("utf-8"))

    # self.attr access?
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == word:
            if not isinstance(node.value, ast.Name) or node.value.id != "self":
                continue
            # The attr identifier occupies the tail of the node span.
            if node.end_lineno != lineno:
                continue
            attr_start = node.end_col_offset - len(word.encode("utf-8"))
            if attr_start <= byte_col <= node.end_col_offset:
                return ("self_attr", word)

    # plain Name?
    decorator_spans = _decorator_name_spans(tree)
    for node in ast.walk(tree):
        nm = None
        if isinstance(node, ast.Name):
            nm = node.id
        elif isinstance(node, ast.arg):
            nm = node.arg
        if nm != word or node.lineno != lineno:
            continue
        if node.col_offset <= byte_col <= node.end_col_offset:
            # ``@maya_command(...)`` parses to Call(func=Name('maya_command')),
            # so a decorator reads as a plain local and gets offered Rename /
            # Promote to Persistent Variable. It is neither: it names a
            # framework function, and rewriting it to ``self.maya_command``
            # would break the member it decorates.
            if (lineno, node.col_offset) in decorator_spans:
                return ("other", word)
            return ("name", word)

    return ("other", word)


def _decorator_name_spans(tree):
    """``(lineno, col_offset)`` of every Name written in a decorator."""
    spans = set()
    for node in ast.walk(tree):
        for deco in getattr(node, "decorator_list", None) or ():
            for sub in ast.walk(deco):
                if isinstance(sub, ast.Name):
                    spans.add((sub.lineno, sub.col_offset))
    return spans


def plan_rename_self_attr(source: str, old_attr: str, new_attr: str):
    """Rewrite every ``self.<old_attr>`` access to ``self.<new_attr>``.

    Attribute access on ``self`` is unambiguous, so this is always
    safe (no scope analysis needed). Returns a RenamePlan; ``count``
    is the number of ``self.<old_attr>`` sites rewritten in this
    source (may be 0 for a sibling tab that doesn\'t use the attr).
    """
    if not is_valid_identifier(new_attr):
        return RenamePlan(
            False, None, 0,
            f"{new_attr!r} is not a valid attribute name",
            (), old_attr, "self_attr", False,
        )
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return RenamePlan(
            False, None, 0,
            f"cannot rename: source has a syntax error ({exc.msg})",
            (), old_attr, "self_attr", False,
        )
    # Collect synthetic span nodes for each self.<old_attr> attr token.
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == old_attr:
            if not isinstance(node.value, ast.Name) or node.value.id != "self":
                continue
            attr_start = node.end_col_offset - len(old_attr.encode("utf-8"))
            spans.append(
                _SpanNode(node.end_lineno, attr_start, node.end_col_offset)
            )
    new_source = _rewrite_spans(source, spans, new_attr)
    try:
        ast.parse(new_source)
    except SyntaxError:
        return RenamePlan(
            False, None, 0,
            "internal error: rewrite produced invalid source (aborted)",
            (), old_attr, "self_attr", False,
        )
    return RenamePlan(
        True, new_source, len(spans), None, (),
        old_attr, "self_attr", False,
    )


class _SpanNode:
    """Minimal span carrier so _rewrite_spans can reuse the per-line
    byte-edit logic for synthetic (non-ast) spans."""

    __slots__ = ("lineno", "col_offset", "end_lineno", "end_col_offset")

    def __init__(self, lineno, col, end_col):
        self.lineno         = lineno
        self.col_offset     = col
        self.end_lineno     = lineno
        self.end_col_offset = end_col


def _rewrite_spans(source, span_nodes, new_name):
    return _rewrite(source, span_nodes, new_name)


# ---- Promote a bare local variable to a ``self.<name>`` (persistent) reference ----


def plan_promote_local(source, lineno, col, *, blocked_names=frozenset()):
    """Rewrite a top-level (module-scope) local variable into a
    ``self.<name>`` attribute reference, so it becomes a persistent
    stored variable.

    Every occurrence of the binding under ``(lineno, col)`` that
    resolves to module scope is rewritten ``name`` -> ``self.name``.
    Returns a RenamePlan (``new_source`` carries the rewritten text).

    Refuses (ok=False) when:
      * the cursor isn\'t on a plain local name;
      * the name is a framework/built-in or collides with an existing
        plug / stored var / internal slot (passed in ``blocked_names``);
      * the binding lives in a function / comprehension scope (only
        top-level compute locals are promotable);
      * the source doesn\'t parse.
    """
    old_name = word_at(source, lineno, col)
    if not old_name:
        return RenamePlan(
            False, None, 0, "no identifier under the cursor",
            (), "", "", False,
        )
    if old_name in blocked_names:
        return RenamePlan(
            False, None, 0,
            f"{old_name!r} is a framework name or already exists as a "
            "plug / persistent variable",
            (), old_name, "", False,
        )
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return RenamePlan(
            False, None, 0,
            f"cannot promote: source has a syntax error ({exc.msg})",
            (), old_name, "", False,
        )

    analyzer = _Analyzer()
    analyzer.visit(tree, analyzer.module)
    module   = analyzer.module

    lines    = source.splitlines()
    line_txt = lines[lineno - 1] if 1 <= lineno <= len(lines) else ""
    byte_col = len(line_txt[:col].encode("utf-8"))

    target       = None
    target_scope = None
    for node, sc in analyzer.occurrences:
        nm = node.id if isinstance(node, ast.Name) else node.arg
        if nm != old_name or node.lineno != lineno:
            continue
        if node.col_offset <= byte_col <= node.end_col_offset:
            target       = node
            target_scope = sc
            break
    if target is None:
        return RenamePlan(
            False, None, 0,
            f"{old_name!r} under the cursor isn't a local variable "
            "reference (it may be an attribute, string, or keyword)",
            (), old_name, "", False,
        )

    defining = _resolve(old_name, target_scope, module)
    if defining is None or defining is not module:
        return RenamePlan(
            False, None, 0,
            "only top-level (module-scope) local variables can be "
            "promoted to a persistent variable",
            (), old_name, defining.kind if defining else "", False,
        )

    targets = []
    for node, sc in analyzer.occurrences:
        nm = node.id if isinstance(node, ast.Name) else node.arg
        if nm != old_name:
            continue
        if _resolve(nm, sc, module) is module:
            targets.append(node)
    if not targets:
        return RenamePlan(
            False, None, 0,
            f"no occurrences of {old_name!r} found",
            (), old_name, "module", True,
        )

    new_source = _rewrite(source, targets, "self." + old_name)
    try:
        ast.parse(new_source)
    except SyntaxError:
        return RenamePlan(
            False, None, 0,
            "internal error: promote produced invalid source (aborted)",
            (), old_name, "module", True,
        )
    return RenamePlan(
        True, new_source, len(targets), None, (),
        old_name, "module", True,
    )
