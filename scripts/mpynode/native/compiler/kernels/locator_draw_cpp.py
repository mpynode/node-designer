"""Deterministic lowering of the ``self.draw`` surface to C++ draw emits.

``self.draw`` is an OBJECT surface -- ``DrawCircle(...) + DrawText(...)``, or a
(possibly nested) list of items -- and the numpy transpiler has no notion of
those objects. This kernel erases them at compile time, exactly like
``self.morphs``:

  1. :func:`desugar_draw` rewrites ``self.draw = <drawing>`` into an ORDERED
     sequence of bare ``self.__nd_draw_<kind>(...)`` statements -- one per
     authored item, in authoring order, carrying the original arguments.
  2. :func:`make_blessed_lowerings` supplies the transpiler a blessed lowering
     per statement, which emits the matching ``data.emit*`` call(s).

Authoring order therefore survives into the compiled node the same way it
survives ``draw_types.to_commands()``: one emit per item, front to back.

**Translate-or-reject.** Any drawing shape this cannot prove (a draw item built
in a loop, stored in a dict, returned from a helper, ...) raises
``UnsupportedSpec`` and the codegen keeps the AI-porter PORT region. A drawing
that lowered to something other than what the interpreted renderer does would be
a silent visual divergence, which is far worse than falling back.
"""
from __future__ import annotations

import ast

from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode.native.compiler.py_to_cpp import Val, scalar_t


# Draw type -> the emit family it desugars to. The five primitives share the
# `shape` family and differ only by their MUIDrawManager kind index (the same
# numbering emit_locator's addUIDrawables switches on).
_SHAPE_KINDS = {"DrawSphere": 0, "DrawCircle": 1, "DrawBox": 2,
                "DrawCone": 3, "DrawCylinder": 4}
_FAMILIES = {
    "DrawLines": "lines", "DrawCurve": "curve",
    "DrawPoints": "points", "DrawText": "text", "DrawMesh": "mesh",
}
_FAMILIES.update({k: "shape" for k in _SHAPE_KINDS})

_PREFIX = "__nd_draw_"

# Constructor signatures: positional parameter order, so a call written
# positionally and one written with keywords lower identically.
_POSITIONAL = {
    "DrawLines": ("starts", "ends", "color", "world_space", "space",
                  "screen_space"),
    "DrawCurve": ("points", "color", "closed", "world_space", "space",
                  "screen_space"),
    "DrawPoints": ("positions", "color", "size", "space", "screen_space"),
    "DrawText": ("text", "position", "color", "size", "space", "screen_space"),
    "DrawMesh": ("points", "counts", "indices", "color"),
}
for _k in _SHAPE_KINDS:
    _POSITIONAL[_k] = ("center", "radius", "axis", "color", "filled")


# ---- C++ support emitted once into the generated file ----------------------
# ``normalize_color`` in C++: the SAME broadcast rules the interpreted flush
# uses (None -> white, (3,)/(4,) uniform, (n,3)/(n,4) per element, missing
# alpha 1.0), so a compiled gizmo tints identically.
DRAW_LOWER_HELPERS = r'''
// ---- self.draw lowering helpers (nd::Array -> Maya draw types) ------------
// Mirrors mpynode/_common/draw/draw_buffers.normalize_color + the per-item
// flush rules, so the compiled draw matches the interpreted one element for
// element.
// Row count of a POINT-LIKE array, mirroring draw_types._points: a bare (3,)
// is promoted to a single row, so one circle is one point -- not three.
static inline int64_t _ndRows(const nd::Array<double>& a) {
    if (a.ndim() == 0) return 0;
    return a.ndim() == 1 ? 1 : a.shape[0];
}
static inline double _ndAt2(const nd::Array<double>& a, int64_t i, int64_t j) {
    nd::Shape idx; idx.push_back(i); idx.push_back(j);
    return a.flat_ref(a.off_of(idx));
}
static inline double _ndAt1(const nd::Array<double>& a, int64_t i) {
    if (a.ndim() == 0) return a.item();
    nd::Shape idx; idx.push_back(i < a.shape[0] ? i : a.shape[0] - 1);
    return a.flat_ref(a.off_of(idx));
}
// Row i of an (n,3) / (n,4) point array (a 1-D (3,) array broadcasts).
static inline MPoint _ndPoint(const nd::Array<double>& a, int64_t i) {
    if (a.ndim() <= 1) return MPoint(_ndAt1(a, 0), _ndAt1(a, 1), _ndAt1(a, 2));
    return MPoint(_ndAt2(a, i, 0), _ndAt2(a, i, 1), _ndAt2(a, i, 2));
}
static inline MVector _ndVector(const nd::Array<double>& a, int64_t i) {
    MPoint p = _ndPoint(a, i);
    return MVector(p.x, p.y, p.z);
}
// normalize_color(colors, n)[i]. `has` is false for a colour the expression
// never passed (Python None) -> the white default.
static inline MColor _ndColor(const nd::Array<double>& c, bool has, int64_t i) {
    if (!has) return MColor(1.0f, 1.0f, 1.0f, 1.0f);
    if (c.ndim() <= 1) {                       // uniform (3,) or (4,)
        const int64_t w = c.ndim() == 0 ? 1 : c.shape[0];
        return MColor((float)_ndAt1(c, 0), (float)_ndAt1(c, 1),
                      (float)_ndAt1(c, 2), w >= 4 ? (float)_ndAt1(c, 3) : 1.0f);
    }
    const int64_t rows = c.shape[0], w = c.shape[1];
    const int64_t r = (i < rows) ? i : rows - 1;   // shorter arrays clamp
    return MColor((float)_ndAt2(c, r, 0), (float)_ndAt2(c, r, 1),
                  (float)_ndAt2(c, r, 2),
                  w >= 4 ? (float)_ndAt2(c, r, 3) : 1.0f);
}
// Copy an nd (n,3) point array into a DrawPoly's MPoint vector.
static inline void _ndFillPts(std::vector<MPoint>& out,
                              const nd::Array<double>& a) {
    const int64_t n = _ndRows(a);
    out.clear(); out.reserve((size_t)n);
    for (int64_t i = 0; i < n; ++i) out.push_back(_ndPoint(a, i));
}
static inline void _ndFillInts(std::vector<int>& out,
                               const nd::Array<int64_t>& a) {
    const int64_t n = a.ndim() == 0 ? 0 : a.shape[0];
    out.clear(); out.reserve((size_t)n);
    for (int64_t i = 0; i < n; ++i) {
        nd::Shape idx; idx.push_back(i);
        out.push_back((int)a.flat_ref(a.off_of(idx)));
    }
}
static inline void _ndFillCols(std::vector<MColor>& out,
                               const nd::Array<double>& c, int64_t n) {
    out.clear(); out.reserve((size_t)n);
    for (int64_t i = 0; i < n; ++i) out.push_back(_ndColor(c, true, i));
}
'''


# ---- desugar: the drawing expression -> ordered emit statements ------------
def _is_draw_ctor(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in _FAMILIES)


def _emit_name(ctor):
    return _PREFIX + _FAMILIES[ctor]


def _as_emit_call(call, alias):
    """One draw constructor -> the bare ``self.__nd_draw_<family>(...)`` stmt.

    Arguments are normalized to KEYWORDS (using the constructor's positional
    order) so the blessed lowering reads one shape only. The concrete type is
    carried as a ``_kind`` keyword for the shape family, and as ``_ctor`` for
    everything else, so the lowering never has to re-derive it."""
    ctor = call.func.id
    names = _POSITIONAL[ctor]
    kw = {}
    for i, arg in enumerate(call.args):
        if i >= len(names):
            raise UnsupportedSpec(
                "nd_lower locator: %s() got %d positional arguments (max %d)"
                % (ctor, len(call.args), len(names)))
        kw[names[i]] = arg
    for k in call.keywords:
        if k.arg is None:
            raise UnsupportedSpec(
                "nd_lower locator: %s(**kwargs) has no compiled form -- pass "
                "the arguments explicitly" % ctor)
        if k.arg in kw:
            raise UnsupportedSpec(
                "nd_lower locator: %s() got a duplicate value for %r"
                % (ctor, k.arg))
        kw[k.arg] = k.value
    kw["_ctor"] = ast.Constant(value=ctor)
    if ctor in _SHAPE_KINDS:
        kw["_kind"] = ast.Constant(value=_SHAPE_KINDS[ctor])
    for k, v in (alias or {}).items():       # .outlined(...) restyle
        kw.setdefault(k, v)
    node = ast.Expr(value=ast.Call(
        func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                           attr=_emit_name(ctor), ctx=ast.Load()),
        args=[],
        keywords=[ast.keyword(arg=k, value=v) for k, v in sorted(kw.items())]))
    return ast.fix_missing_locations(ast.copy_location(node, call))


_OUTLINED_KW = ("color", "width", "boundary_only")


def _flatten_drawing(node, assigns, seen=None, consumed=None):
    """The drawing expression -> the ordered list of (ctor_call, restyle) pairs.

    Recognised: a constructor call, a ``+`` chain, a list/tuple display, a
    ``.outlined(...)`` restyle, ``None``, and a NAME bound exactly once to any
    of those. Everything else rejects.

    ``consumed`` collects every local name resolved through ``assigns``; its
    binding statement becomes dead once the drawing is desugared into emits and
    MUST be dropped -- the transpiler has no lowering for a bare
    ``cube = DrawMesh(...)``."""
    seen = seen or set()
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return []
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (_flatten_drawing(node.left, assigns, seen, consumed)
                + _flatten_drawing(node.right, assigns, seen, consumed))
    if isinstance(node, (ast.List, ast.Tuple)):
        out = []
        for el in node.elts:
            out += _flatten_drawing(el, assigns, seen, consumed)
        return out
    if _is_draw_ctor(node):
        return [(node, {})]
    # mesh.outlined(color, width=..., boundary_only=...)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "outlined"):
        inner = _flatten_drawing(node.func.value, assigns, seen, consumed)
        if len(inner) != 1 or inner[0][0].func.id != "DrawMesh":
            raise UnsupportedSpec(
                "nd_lower locator: .outlined(...) lowers only on a single "
                "DrawMesh")
        style = {}
        for i, a in enumerate(node.args):
            if i >= len(_OUTLINED_KW):
                raise UnsupportedSpec(
                    "nd_lower locator: .outlined() takes at most 3 arguments")
            style["outline" if i == 0 else "outline_" + _OUTLINED_KW[i]] = a
        for k in node.keywords:
            if k.arg not in _OUTLINED_KW:
                raise UnsupportedSpec(
                    "nd_lower locator: .outlined(%s=...) is not a recognised "
                    "option" % k.arg)
            style["outline" if k.arg == "color"
                  else "outline_" + k.arg] = k.value
        call, prev = inner[0]
        merged = dict(prev)
        merged.update(style)
        return [(call, merged)]
    if isinstance(node, ast.Name):
        if node.id in seen:
            raise UnsupportedSpec(
                "nd_lower locator: %r is defined in terms of itself" % node.id)
        bound = assigns.get(node.id)
        if bound is None:
            raise UnsupportedSpec(
                "nd_lower locator: %r is not a drawing this can prove -- it is "
                "unassigned, reassigned, or built conditionally" % node.id)
        if consumed is not None:
            consumed.add(node.id)
        return _flatten_drawing(bound, assigns, seen | {node.id}, consumed)
    raise UnsupportedSpec(
        "nd_lower locator: self.draw takes draw items composed with '+' or a "
        "list of them; %s has no compiled form" % type(node).__name__)


def _single_assignments(tree):
    """``{name: value_node}`` for every module-level name bound EXACTLY once.

    A name assigned twice (or mutated with ``.append``, or bound in a branch)
    is deliberately absent -- resolving it would mean guessing which drawing
    ran, and guessing wrong is a silent visual divergence."""
    counts, values = {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    counts[t.id] = counts.get(t.id, 0) + 1
                    values[t.id] = node.value
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            t = node.target
            if isinstance(t, ast.Name):
                counts[t.id] = counts.get(t.id, 0) + 2      # never single
        elif isinstance(node, ast.For):
            t = node.target
            if isinstance(t, ast.Name):
                counts[t.id] = counts.get(t.id, 0) + 2
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and isinstance(node.func.value, ast.Name)
              and node.func.attr in ("append", "extend", "insert")):
            nm = node.func.value.id
            counts[nm] = counts.get(nm, 0) + 2              # mutated -> opaque
    return {k: v for k, v in values.items() if counts.get(k) == 1}


_CPP_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _cpp_string(text):
    """A C++ string literal for ``text``.

    Non-ASCII goes out as UTF-8 ``\\xNN`` bytes (MString reads UTF-8). A hex
    escape in C++ is GREEDY, so a following hex digit would be swallowed into
    the previous byte -- the literal is split in two at that point instead
    (adjacent literals concatenate)."""
    out, prev_hex = [], False
    for ch in text:
        if ch in _CPP_ESCAPES:
            out.append(_CPP_ESCAPES[ch])
            prev_hex = False
        elif 32 <= ord(ch) < 127:
            if prev_hex and ch in "0123456789abcdefABCDEF":
                out.append('" "')
            out.append(ch)
            prev_hex = False
        else:
            out.extend("\\x%02x" % b for b in ch.encode("utf-8"))
            prev_hex = True
    return '"%s"' % "".join(out)


def _const_strings(tp, node):
    """The labels of a ``DrawText``, resolved at COMPILE time.

    Mirrors ``draw_types._strings``: a bare string is ONE label (not a list of
    characters) and any other constant is ``str()``-ed. Anything whose value is
    only known at runtime rejects -- the transpiler carries no string-array
    type, so guessing a label would draw the wrong text.

    A bare NAME resolves through the INIT-tier constants, which is how the
    usual ``LABELS = ["a", "b"]`` in the Init tab reaches the draw. This reads
    the AST directly rather than going through the expression transpiler, so it
    needs no string-list value type."""
    if node is None:
        raise UnsupportedSpec("nd_lower locator: DrawText() needs text")
    if isinstance(node, ast.Name):
        consts = getattr(tp.helpers, "consts", None) or {}
        if node.id not in consts:
            raise UnsupportedSpec(
                "nd_lower locator: DrawText(text=%s) is not a compile-time "
                "constant -- only a literal, or an Init-tab constant bound "
                "exactly once, has a compiled form" % node.id)
        return _const_strings(tp, consts[node.id])
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return [node.value]
        return [str(node.value)]
    if isinstance(node, (ast.List, ast.Tuple)):
        out = []
        for el in node.elts:
            if not isinstance(el, ast.Constant):
                raise UnsupportedSpec(
                    "nd_lower locator: DrawText() lowers only literal labels; "
                    "%s has no compiled form" % type(el).__name__)
            out.append(el.value if isinstance(el.value, str) else str(el.value))
        if not out:
            raise UnsupportedSpec("nd_lower locator: DrawText() got no labels")
        return out
    raise UnsupportedSpec(
        "nd_lower locator: DrawText(text=...) must be a literal string or a "
        "literal list of them -- a runtime string has no compiled form")


def _is_self_draw(node):
    return (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "self" and node.attr == "draw")


def _draw_accumulators(tree):
    """Names built as ``N = []``, filled only by ``N.append(<drawing>)``, and
    handed to ``self.draw``.

    This is the idiom the templates teach, and the ordered command transport
    makes it lower EXACTLY: emission order is execution order, so an append
    under an ``if`` is just an emit under the same ``if`` and an inactive branch
    contributes nothing -- the same drawing the interpreted node produces.

    Conservative by construction: the name is collected only if every single
    mention of it is one of those three roles. Any other read (``len(items)``,
    ``items[0]``, passing it to a call, a second assignment) disqualifies it,
    because then the list is no longer a pure append-ordered accumulator."""
    seeds, sinks, accounted = {}, set(), set()
    for node in ast.walk(tree):
        # N = []
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.List) and not node.value.elts):
            nm = node.targets[0].id
            seeds[nm] = seeds.get(nm, 0) + 1
            accounted.add(id(node.targets[0]))
        # N.append(<one positional drawing>) as a bare statement
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "append"
                and isinstance(node.value.func.value, ast.Name)
                and len(node.value.args) == 1 and not node.value.keywords):
            accounted.add(id(node.value.func.value))
        # self.draw = N
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                and _is_self_draw(node.targets[0])
                and isinstance(node.value, ast.Name)):
            sinks.add(node.value.id)
            accounted.add(id(node.value))

    elsewhere = {n.id for n in ast.walk(tree)
                 if isinstance(n, ast.Name) and id(n) not in accounted}
    return {nm for nm, count in seeds.items()
            if count == 1 and nm in sinks and nm not in elsewhere}


def desugar_draw(source):
    """Rewrite ``self.draw = <drawing>`` into ordered emit statements.

    Returns the rewritten source. Raises ``UnsupportedSpec`` when the drawing
    cannot be proven -- the caller then keeps the PORT region."""
    tree = ast.parse(source)
    assigns = _single_assignments(tree)
    accums = _draw_accumulators(tree)
    consumed = set()

    def _emits(value, at):
        stmts = [_as_emit_call(call, style)
                 for call, style in _flatten_drawing(value, assigns,
                                                     consumed=consumed)]
        # A drawing that resolves to nothing (self.draw = None) emits nothing --
        # the C++ command list simply stays empty, matching to_commands(None).
        return stmts or [ast.copy_location(ast.Pass(), at)]

    class _T(ast.NodeTransformer):
        def visit_Expr(self, node):
            """`items.append(<drawing>)` -> the emit statements, IN PLACE, so
            the surrounding if/for control flow keeps driving them."""
            v = node.value
            if (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                    and v.func.attr == "append"
                    and isinstance(v.func.value, ast.Name)
                    and v.func.value.id in accums):
                return _emits(v.args[0], node)
            return node

        def visit_Assign(self, node):
            # the `N = []` seed carries no drawing of its own
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in accums):
                return ast.copy_location(ast.Pass(), node)
            targets = [t for t in node.targets if _is_self_draw(t)]
            if not targets:
                return node
            if len(node.targets) != 1:
                raise UnsupportedSpec(
                    "nd_lower locator: chained assignment to self.draw")
            # `self.draw = items` already emitted at each append site
            if isinstance(node.value, ast.Name) and node.value.id in accums:
                return ast.copy_location(ast.Pass(), node)
            return _emits(node.value, node)

    tree = _T().visit(tree)

    # `cube = DrawMesh(...)` is DEAD once its use desugared into an emit: the
    # constructor was inlined at the use site, and the transpiler has no
    # lowering for a bare draw-object binding. Drop it (the same move nd_lower
    # makes for a consumed geo alias).
    class _DropConsumed(ast.NodeTransformer):
        def visit_Assign(self, node):
            if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in consumed):
                return None
            return node

    if consumed:
        tree = _DropConsumed().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ---- blessed lowerings: one emit statement -> C++ --------------------------
def _kwmap(node):
    return {k.arg: k.value for k in node.keywords}


def _const(node, default=None):
    if node is None:
        return default
    if isinstance(node, ast.Constant):
        return node.value
    raise UnsupportedSpec(
        "nd_lower locator: expected a literal, got %s" % type(node).__name__)


def make_blessed_lowerings():
    """``{method: callable(tp, call_node) -> Val}`` for the draw emit family."""

    def _arr(tp, node):
        """One argument as an nd::Array<double> C++ local (name, present)."""
        if node is None:
            return None
        v = tp.expr(node)
        if v.type.kind == "scalar":
            t = tp._new_tmp("dsc")
            tp.emit("const nd::Array<double> %s = nd::scalar<double>((double)(%s));"
                    % (t, v.code))
            return t
        if v.type.kind != "array":
            raise UnsupportedSpec(
                "nd_lower locator: a draw argument must be numeric, got %r"
                % v.type.kind)
        t = tp._new_tmp("darr")
        tp.emit("const nd::Array<double> %s = nd::astype<double>(%s);"
                % (t, v.code))
        return t

    def _iarr(tp, node):
        v = tp.expr(node)
        t = tp._new_tmp("dint")
        tp.emit("const nd::Array<int64_t> %s = nd::astype<int64_t>(%s);"
                % (t, v.code))
        return t

    def _scalar(tp, node, default):
        if node is None:
            return default
        v = tp.expr(node)
        if v.type.kind != "scalar":
            raise UnsupportedSpec(
                "nd_lower locator: expected a scalar draw argument")
        return "(double)(%s)" % (v.raw or (v.code + ".item()")
                                 if v.type.kind == "array" else v.code)

    def _flag(tp, node, default="false"):
        if node is None:
            return default
        val = _const(node, None)
        if isinstance(val, bool):
            return "true" if val else "false"
        v = tp.expr(node)
        return "(bool)(%s)" % v.code

    def _color(tp, node):
        """(cpp_array_name_or_placeholder, has_flag)."""
        if node is None:
            return "nd::Array<double>()", "false"
        return _arr(tp, node), "true"

    def _space_guard(tp, kw, what):
        sp = kw.get("space")
        scr = kw.get("screen_space")
        if scr is not None and _const(scr, False):
            raise UnsupportedSpec(
                "nd_lower locator: %s(screen_space=True) has no compiled form "
                "yet (the C++ renderer draws in local space)" % what)
        if sp is not None and _const(sp, "local") not in ("local", None):
            raise UnsupportedSpec(
                "nd_lower locator: %s(space=%r) has no compiled form yet"
                % (what, _const(sp, "local")))

    def _emit_shape(tp, node):
        kw = _kwmap(node)
        kind = _const(kw.get("_kind"), 1)
        ctor = _const(kw.get("_ctor"), "DrawCircle")
        _space_guard(tp, kw, ctor)
        centers = _arr(tp, kw.get("center"))
        if centers is None:
            raise UnsupportedSpec("nd_lower locator: %s() needs a center" % ctor)
        radii = _arr(tp, kw.get("radius")) or "nd::scalar<double>(1.0)"
        default_axis = "0.0, 0.0, 1.0" if ctor == "DrawCircle" else "0.0, 1.0, 0.0"
        axes = _arr(tp, kw.get("axis"))
        if axes is None:
            axes = tp._new_tmp("dax")
            tp.emit("const nd::Array<double> %s = nd::from_data<double>("
                    "std::vector<double>{%s}, nd::Shape{3});" % (axes, default_axis))
        col, has = _color(tp, kw.get("color"))
        filled = _flag(tp, kw.get("filled"))   # DrawPrimitive defaults filled=False
        i = tp._new_tmp("di")
        tp.emit("for (int64_t %s = 0; %s < std::max<int64_t>(_ndRows(%s), 1); ++%s)"
                % (i, i, centers, i))
        tp.emit("    data.emitShape(%d, _ndPoint(%s, %s), _ndAt1(%s, %s), "
                "_ndVector(%s, %s), _ndColor(%s, %s, %s), %s);"
                % (kind, centers, i, radii, i, axes, i, col, has, i, filled))
        return Val("0", scalar_t("int64"))

    def _emit_points(tp, node):
        kw = _kwmap(node)
        _space_guard(tp, kw, "DrawPoints")
        pos = _arr(tp, kw.get("positions"))
        if pos is None:
            raise UnsupportedSpec("nd_lower locator: DrawPoints() needs positions")
        col, has = _color(tp, kw.get("color"))
        size = _arr(tp, kw.get("size")) or "nd::scalar<double>(4.0)"
        i = tp._new_tmp("di")
        tp.emit("for (int64_t %s = 0; %s < _ndRows(%s); ++%s)" % (i, i, pos, i))
        tp.emit("    data.emitPoint(_ndPoint(%s, %s), _ndColor(%s, %s, %s), "
                "(float)_ndAt1(%s, %s));" % (pos, i, col, has, i, size, i))
        return Val("0", scalar_t("int64"))

    def _emit_lines(tp, node):
        kw = _kwmap(node)
        _space_guard(tp, kw, "DrawLines")
        starts = _arr(tp, kw.get("starts"))
        ends = _arr(tp, kw.get("ends"))
        if starts is None or ends is None:
            raise UnsupportedSpec(
                "nd_lower locator: DrawLines() needs starts and ends")
        col, has = _color(tp, kw.get("color"))
        world = _flag(tp, kw.get("world_space"))
        i = tp._new_tmp("di")
        tp.emit("for (int64_t %s = 0; %s < _ndRows(%s); ++%s)" % (i, i, starts, i))
        tp.emit("    data.emitLine(_ndPoint(%s, %s), _ndPoint(%s, %s), "
                "_ndColor(%s, %s, %s), %s);"
                % (starts, i, ends, i, col, has, i, world))
        return Val("0", scalar_t("int64"))

    def _emit_curve(tp, node):
        """A polyline: the SAME pts[:-1]/pts[1:] split DrawCurve._segments does
        (plus the wrap segment when closed)."""
        kw = _kwmap(node)
        _space_guard(tp, kw, "DrawCurve")
        pts = _arr(tp, kw.get("points"))
        if pts is None:
            raise UnsupportedSpec("nd_lower locator: DrawCurve() needs points")
        col, has = _color(tp, kw.get("color"))
        closed = _flag(tp, kw.get("closed"))
        world = _flag(tp, kw.get("world_space"))
        n, i = tp._new_tmp("dn"), tp._new_tmp("di")
        tp.emit("const int64_t %s = _ndRows(%s);" % (n, pts))
        tp.emit("for (int64_t %s = 0; %s + 1 < %s + (%s ? 1 : 0); ++%s)"
                % (i, i, n, closed, i))
        tp.emit("    if (%s >= 2) data.emitLine(_ndPoint(%s, %s), "
                "_ndPoint(%s, (%s + 1) %% %s), _ndColor(%s, %s, %s), %s);"
                % (n, pts, i, pts, i, n, col, has, i, world))
        return Val("0", scalar_t("int64"))

    def _emit_text(tp, node):
        """Labels known at COMPILE time need no runtime string type at all --
        the count is fixed, so each label becomes its own emitText call.

        A RUNTIME std::string (a string INPUT plug, or a concatenation of one)
        is still exactly ONE label, which _strings() broadcasts across every
        position -- the same single-label loop, so this needs no string-array
        type either."""
        kw = _kwmap(node)
        _space_guard(tp, kw, "DrawText")
        if kw.get("text") is None:
            raise UnsupportedSpec("nd_lower locator: DrawText() needs text")
        try:
            strings, runtime = _const_strings(tp, kw["text"]), None
        except UnsupportedSpec:
            # Not a compile-time label. A str-kind value is one label; anything
            # else (an array, a number) has no compiled form -- re-raise the
            # constant-folder's message, which names what it could not resolve.
            runtime = tp.expr(kw["text"])
            if runtime.type.kind not in ("str", "strv"):
                raise
            strings = None
        pos = _arr(tp, kw.get("position"))
        if pos is None:
            raise UnsupportedSpec("nd_lower locator: DrawText() needs a position")
        col, has = _color(tp, kw.get("color"))
        size = _arr(tp, kw.get("size")) or "nd::scalar<double>(0.5)"
        if runtime is not None and runtime.type.kind == "strv":
            # A RUNTIME label list (list(<str>)): the count is known only at draw
            # time, so the two _strings(value, n) cases become a runtime branch --
            # a ONE-entry list broadcasts across every position, otherwise the
            # counts must match exactly. The interpreted DrawText raises on a
            # mismatch; a compiled node cannot, so it draws nothing.
            v = tp._new_tmp("dtv")
            n = tp._new_tmp("dtn")
            b = tp._new_tmp("di")
            i = tp._new_tmp("di")
            tp.emit("const std::vector<std::string>& %s = %s;"
                    % (v, runtime.code))
            tp.emit("const int64_t %s = _ndRows(%s);" % (n, pos))
            tp.emit("if ((int64_t)%s.size() == 1 && %s > 1) {" % (v, n))
            tp.emit("    for (int64_t %s = 0; %s < %s; ++%s)" % (b, b, n, b))
            tp.emit("        data.emitText(_ndPoint(%s, %s), MString(%s[0].c_str()), "
                    "_ndColor(%s, %s, %s), _ndAt1(%s, %s));"
                    % (pos, b, v, col, has, b, size, b))
            tp.emit("} else if ((int64_t)%s.size() == %s) {" % (v, n))
            tp.emit("    for (int64_t %s = 0; %s < %s; ++%s)" % (i, i, n, i))
            tp.emit("        data.emitText(_ndPoint(%s, %s), MString(%s[%s].c_str()), "
                    "_ndColor(%s, %s, %s), _ndAt1(%s, %s));"
                    % (pos, i, v, i, col, has, i, size, i))
            tp.emit("}")
            return Val("0", scalar_t("int64"))
        if runtime is not None or len(strings) == 1:
            # _strings(text, n) broadcasts ONE label across every position.
            if runtime is not None:
                lbl = tp._new_tmp("dtx")
                tp.emit("const MString %s(%s.c_str());" % (lbl, runtime.code))
            else:
                lbl = "MString(%s)" % _cpp_string(strings[0])
            i = tp._new_tmp("di")
            tp.emit("for (int64_t %s = 0; %s < _ndRows(%s); ++%s)"
                    % (i, i, pos, i))
            tp.emit("    data.emitText(_ndPoint(%s, %s), %s, "
                    "_ndColor(%s, %s, %s), _ndAt1(%s, %s));"
                    % (pos, i, lbl, col, has, i, size, i))
            return Val("0", scalar_t("int64"))
        # N labels require exactly N positions. The interpreted DrawText raises
        # on a mismatch and a compiled node cannot, so draw nothing rather than
        # read past the array.
        tp.emit("if (_ndRows(%s) == %d) {" % (pos, len(strings)))
        for k, text in enumerate(strings):
            tp.emit("    data.emitText(_ndPoint(%s, %d), MString(%s), "
                    "_ndColor(%s, %s, %d), _ndAt1(%s, %d));"
                    % (pos, k, _cpp_string(text), col, has, k, size, k))
        tp.emit("}")
        return Val("0", scalar_t("int64"))

    def _emit_mesh(tp, node):
        kw = _kwmap(node)
        pts = _arr(tp, kw.get("points"))
        counts = kw.get("counts")
        indices = kw.get("indices")
        if pts is None or counts is None or indices is None:
            raise UnsupportedSpec(
                "nd_lower locator: DrawMesh() needs points, counts and indices")
        cnt = _iarr(tp, counts)
        idx = _iarr(tp, indices)
        pg = tp._new_tmp("dpg")
        tp.emit("DrawPoly& %s = data.emitPoly();" % pg)
        tp.emit("_ndFillPts(%s.pts, %s);" % (pg, pts))
        tp.emit("_ndFillInts(%s.cnt, %s);" % (pg, cnt))
        tp.emit("_ndFillInts(%s.idx, %s);" % (pg, idx))
        # exactly one fill mode -- the same mutual exclusion DrawMesh enforces
        modes = [("color", 1, "faceColors"), ("uniform_color", 0, None),
                 ("vertex_colors", 2, "vertexColors"),
                 ("face_vertex_colors", 3, "faceVertexColors")]
        chosen = [m for m in modes if kw.get(m[0]) is not None]
        if len(chosen) > 1:
            raise UnsupportedSpec(
                "nd_lower locator: DrawMesh() got several fill modes (%s)"
                % ", ".join(m[0] for m in chosen))
        if not chosen:
            # An uncoloured DrawMesh is flat WHITE: _flush_polygons falls back
            # to face_colors = normalize_color(None, n). Say so explicitly --
            # DrawPoly's own default is grey, which the porter path relies on.
            tp.emit("%s.colorMode = 0;" % pg)
            tp.emit("%s.uniform = _ndColor(nd::Array<double>(), false, 0);" % pg)
        if chosen:
            key, mode, vec = chosen[0]
            carr = _arr(tp, kw[key])
            if vec is None or mode == 0:
                tp.emit("%s.colorMode = 0;" % pg)
                tp.emit("%s.uniform = _ndColor(%s, true, 0);" % (pg, carr))
            else:
                # A (3,)/(4,) `color=` is a UNIFORM tint, not a per-face table.
                tp.emit("if (%s.ndim() <= 1) { %s.colorMode = 0; "
                        "%s.uniform = _ndColor(%s, true, 0); }"
                        % (carr, pg, pg, carr))
                tp.emit("else { %s.colorMode = %d; _ndFillCols(%s.%s, %s, "
                        "_ndRows(%s)); }" % (pg, mode, pg, vec, carr, carr))
        for key, member in (("cull_backfaces", "cull"),
                            ("world_space", "worldSpace"),
                            ("highlight_fill", "highlightFill"),
                            ("highlight_wire", "highlightWire"),
                            ("precise_hover", "preciseHover")):
            if kw.get(key) is not None:
                tp.emit("%s.%s = %s;" % (pg, member, _flag(tp, kw[key])))
        if kw.get("outline") is not None:
            oc = _arr(tp, kw["outline"])
            tp.emit("%s.hasWire = true;" % pg)
            tp.emit("%s.wireColor = _ndColor(%s, true, 0);" % (pg, oc))
        if kw.get("outline_width") is not None:
            tp.emit("%s.wireWidth = %s;" % (pg, _scalar(tp, kw["outline_width"],
                                                        "1.0")))
        if kw.get("outline_boundary_only") is not None:
            tp.emit("%s.wireBoundaryOnly = %s;"
                    % (pg, _flag(tp, kw["outline_boundary_only"])))
        return Val("0", scalar_t("int64"))

    return {
        _PREFIX + "shape": _emit_shape,
        _PREFIX + "points": _emit_points,
        _PREFIX + "lines": _emit_lines,
        _PREFIX + "curve": _emit_curve,
        _PREFIX + "text": _emit_text,
        _PREFIX + "mesh": _emit_mesh,
    }
