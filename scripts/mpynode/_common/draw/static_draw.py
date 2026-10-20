"""What an mPyLocator drawing depends on, read off its sources.

A drawing is STATIC when the draw expression's result depends only on the
node's input attributes, on stored vars it reads but never writes, and on its
Init and Methods code. A static drawing is built once per change instead of on
every viewport refresh:

  * the interpreted node reuses its last draw commands while those values stay
    the same (``mpynode._api2.mpy_locator``);
  * the compiled node keeps its draw override clean until an input changes
    (``spec["draw_mode"] == "static"``, ``native.compiler.emit_locator``).

A drawing is VIEW-DEPENDENT when the override needs the camera to draw it: text
sized in pixels, back-face culling, screen-space items. The interpreted node
does that work after the expression, so its expression can still be reused;
the compiled node keeps rebuilding such a drawing on every refresh.

The analysis is conservative: a read it cannot place (a ``self.<name>`` that is
not an input, a stored var, an Init name or a method) makes the drawing
dynamic, and so does any source that does not parse. ``force_dynamic`` (the
node's ``dynamic_draw`` metadata, Node Info > Always redraw) overrides it.

Maya-free: the interpreted node, ``spec_extractor`` and ``mpn_spec_adapter``
share this one analysis.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Iterable, Optional

# self.<name> values that change without any input attribute changing
CONTEXT_READS = frozenset(("time", "wallclock", "hovered", "selected", "is_lead", "selection_color"))

# write-only draw outputs the framework harvests after the expression
WRITE_SINKS = frozenset(("draw", "auto_highlight", "auto_refresh", "precise_hover"))

# the passive hover / idle-refresh service serves these (and auto_refresh set on)
_HOVER_NAMES = frozenset(("hovered", "wallclock", "precise_hover"))

# modules whose calls can answer differently from one refresh to the next
_VOLATILE_ROOTS = frozenset(("time", "datetime", "random", "secrets", "uuid", "cmds", "mc", "pm", "pymel",
                             "MGlobal", "MAnimControl", "oma"))

# keywords that make the compiled override need the camera when they are on
_VIEW_KEYWORDS = ("cull_backfaces", "screen_space")


@dataclass(frozen=True)
class DrawAnalysis:
    """What one locator's sources say about its drawing."""

    static:         bool
    view_dependent: bool
    needs_hover:    bool
    reasons:        tuple = ()  # why the drawing is not static
    view_reasons:   tuple = ()  # why the compiled override needs the camera
    parsed:         bool = True

    @property
    def draw_mode(self) -> str:
        """``"static"`` when the compiled override can stay clean until an input changes"""
        return "static" if self.static and not self.view_dependent else "dynamic"


def _is_self(node) -> bool:
    return isinstance(node, ast.Name) and node.id == "self"


def _falsy(node) -> bool:
    """a literal False / None / 0 / empty string"""
    return isinstance(node, ast.Constant) and not node.value


def _root_and_path(node):
    """the leftmost name of ``a.b.c`` and the dotted path, or (None, "")"""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return node.id, ".".join(reversed(parts))
    return None, ""


class _Scan(ast.NodeVisitor):
    """``self`` reads and writes, volatile calls and view-dependent draw arguments"""

    def __init__(self):
        self.reads    = set()
        self.optional = set()  # getattr(self, "x", default) / hasattr: the stored-var idiom
        self.names    = set()  # bare names loaded (calls into Init helpers)
        self.writes   = {}     # name -> [value node or None]
        self.volatile = []
        self.view     = []
        self.world    = False

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)

    # ---- self.<name> ----
    def visit_Attribute(self, node):
        if _is_self(node.value) and isinstance(node.ctx, ast.Load):
            self.reads.add(node.attr)
        self.generic_visit(node)

    def _target(self, target, value):
        if isinstance(target, ast.Attribute) and _is_self(target.value):
            self.writes.setdefault(target.attr, []).append(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._target(element, None)
        elif isinstance(target, ast.Starred):
            self._target(target.value, None)

    def visit_Assign(self, node):
        for target in node.targets:
            self._target(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._target(node.target, node.value)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._target(node.target, None)
        if isinstance(node.target, ast.Attribute) and _is_self(node.target.value):
            self.reads.add(node.target.attr)
        self.generic_visit(node)

    def visit_Delete(self, node):
        for target in node.targets:
            self._target(target, None)
        self.generic_visit(node)

    # ---- calls ----
    def visit_Call(self, node):
        func = node.func
        if (isinstance(func, ast.Name) and func.id in ("getattr", "hasattr", "setattr")
                and len(node.args) >= 2 and _is_self(node.args[0])
                and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)):
            name = node.args[1].value
            if func.id == "setattr":
                self.writes.setdefault(name, []).append(node.args[2] if len(node.args) > 2 else None)
            elif name in CONTEXT_READS or (func.id == "getattr" and len(node.args) < 3):
                self.reads.add(name)
            else:
                self.optional.add(name)
        if isinstance(func, ast.Attribute) and _is_self(func.value) and func.attr in ("set_variable", "delete_variable"):
            self.writes.setdefault("<stored var via %s>" % func.attr, []).append(None)

        root, path = _root_and_path(func)
        if root in _VOLATILE_ROOTS or ".random." in "." + path + ".":
            self.volatile.append(path)
        callee = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if callee == "DrawText":
            self.view.append("DrawText (glyphs are sized from the camera)")
        if callee == "in_space" and node.args and not (
                isinstance(node.args[0], ast.Constant) and node.args[0].value == "local"):
            self.view.append("in_space(...) away from local space")
        for kw in node.keywords:
            if kw.arg in _VIEW_KEYWORDS and not _falsy(kw.value):
                self.view.append("%s=..." % kw.arg)
            elif kw.arg == "space" and not (isinstance(kw.value, ast.Constant) and kw.value.value == "local"):
                self.view.append("space=...")
            elif kw.arg == "world_space" and not _falsy(kw.value):
                self.world = True
        self.generic_visit(node)

    # ---- imports of volatile modules inside the per-draw code ----
    def visit_ImportFrom(self, node):
        if node.module and node.module.split(".")[0] in ("time", "datetime", "random"):
            for alias in node.names:
                self.volatile.append("%s.%s" % (node.module, alias.name))
        self.generic_visit(node)


def _top_level_names(tree) -> set:
    """names an Init / Methods source binds at module level"""
    names = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for sub in ast.walk(target):
                    if isinstance(sub, ast.Name):
                        names.add(sub.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
    return names


def _parse(source: str):
    try:
        return ast.parse(source or "")
    except (SyntaxError, ValueError):
        return None


def analyse(
    compute:       str,
    init:          str                     = "",
    methods:       str                     = "",
    inputs:        Iterable[str]           = (),
    stored_vars:   Optional[Iterable[str]] = (),
    force_dynamic: bool                    = False,
) -> DrawAnalysis:
    """What ``compute`` (the draw expression) reads, given the node's other sources.

    ``inputs`` are the user input attribute names and ``stored_vars`` the stored
    var names (None when unknown: then any unplaced ``self.<name>`` read makes
    the drawing dynamic, as it does anyway).
    """
    trees = [_parse(compute), _parse(init), _parse(methods)]
    if any(tree is None for tree in trees):
        return DrawAnalysis(static=False, view_dependent=True, needs_hover=False,
                            reasons=("a source does not parse",), parsed=False)
    expr_tree, init_tree, methods_tree = trees

    scan = _Scan()
    scan.visit(expr_tree)

    # Init / Methods code the drawing reaches: the functions (and classes) the
    # expression names, and what those name in turn. Top-level Init code runs
    # once, and a Methods command or test the drawing never calls cannot change it.
    defs = {}
    for tree in (init_tree, methods_tree):
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defs[node.name] = node
    helper = _Scan()
    reached, todo = set(), list((scan.reads | scan.optional | scan.names) & set(defs))
    while todo:
        name = todo.pop()
        if name in reached:
            continue
        reached.add(name)
        local = _Scan()
        local.visit(defs[name])
        helper.reads    |= local.reads
        helper.volatile += local.volatile
        helper.view     += local.view
        helper.world    |= local.world
        for key, values in local.writes.items():
            helper.writes.setdefault(key, []).extend(values)
        todo.extend((local.reads | local.optional | local.names) & set(defs))

    known = set(inputs) | set(stored_vars or ()) | WRITE_SINKS
    known |= _top_level_names(init_tree) | _top_level_names(methods_tree)

    reasons = []
    for name in sorted(scan.reads & CONTEXT_READS):
        reasons.append("reads self.%s" % name)
    auto_refresh_on = False
    for name in sorted(scan.writes):
        values = scan.writes[name]
        if name == "auto_refresh":
            if any(value is None or not _falsy(value) for value in values):
                auto_refresh_on = True
                reasons.append("sets self.auto_refresh")
        elif name not in WRITE_SINKS:
            reasons.append("writes self.%s (state kept between draws)" % name)
    for name in sorted(scan.reads - known - CONTEXT_READS):
        reasons.append("reads self.%s, which is not an input, a stored var, an Init name or a method" % name)
    # Init / Methods functions that take the node as ``self``
    for name in sorted(helper.reads & CONTEXT_READS):
        reasons.append("an Init or Methods function reads self.%s" % name)
    for name in sorted(set(helper.writes) - WRITE_SINKS):
        reasons.append("an Init or Methods function writes self.%s" % name)
    for path in scan.volatile + helper.volatile:
        reasons.append("calls %s" % path)
    if scan.world or helper.world:
        reasons.append("draws world_space items, placed from the node's world matrix on every refresh")
    if force_dynamic:
        reasons.append("Always redraw is on (dynamic_draw metadata)")

    hover_scan = _Scan()
    hover_scan.visit(init_tree)
    hover_refs = scan.reads | hover_scan.reads | set(scan.writes) | set(hover_scan.writes)
    needs_hover = bool(hover_refs & _HOVER_NAMES) or auto_refresh_on or any(
        value is None or not _falsy(value) for value in hover_scan.writes.get("auto_refresh", ()))

    view_reasons = tuple(dict.fromkeys(scan.view + helper.view))
    return DrawAnalysis(
        static         = not reasons,
        view_dependent = bool(view_reasons),
        needs_hover    = needs_hover,
        reasons        = tuple(dict.fromkeys(reasons)),
        view_reasons   = view_reasons,
    )
