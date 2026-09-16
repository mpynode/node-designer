"""osl_convert -- deterministic mPyFile *Compute* -> OSL transpiler (v1).

This is the deterministic arm of the mPyFile->OSL conversion feature. It is a
BOUNDED, idiom-recognizing transpiler: it reads the Python Compute look-math and
emits Open Shading Language for the canonical mPyFile shading shape --

    sample an image at (u, v) with the top-down (1 - v) flip, modulate the
    sampled colour by a scalar, write self.outColor.

That is exactly the shape the scanline demo ships, and the hand-written
``scanline_defs.ARNOLD_OSL_SRC`` is its golden twin -- this module reproduces it
from ``COMPUTE_SRC`` by construction (see test_osl_convert.py).

Design notes
------------
* It is NOT a general Python->OSL compiler. Anything outside the recognized
  grammar raises :class:`UnsupportedComputeError`; the UI then offers the AI
  assistant (the hybrid feature's AI arm). Strictness here is SAFE -- a clear
  fallback beats silently emitting invalid OSL.
* The image-sample idiom (load PNG, read shape, index pixels) is a *semantic*
  re-expression, not a line transpile: those statements collapse to a single
  ``texture()`` call -- OSL does the sampling/filtering itself.
* Scalar arithmetic is transpiled via an AST transform + ``ast.unparse`` so the
  operator spacing/parenthesisation matches canonical OSL exactly (and stays
  numerically faithful to the Python). Constants come from the node's Init tier
  (resolved statically by :func:`extract_simple_consts`, no exec).
"""

from __future__ import annotations

import ast
import copy


class UnsupportedComputeError(Exception):
    """Raised when the Compute look-math is outside the v1 OSL grammar."""


_HINT = " -- use the AI assistant to translate this Compute look-math to OSL."

# math.<fn> / bare <fn> that exist in OSL with the same name + arity.
MATH_FUNCS = frozenset((
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "sqrt", "exp", "log", "pow", "floor", "ceil", "fabs", "hypot",
))
BUILTIN_FUNCS = frozenset(("abs", "min", "max", "pow"))  # kept verbatim in OSL
DROP_CASTS    = frozenset(("float", "int"))              # OSL is typed -- casts are noise


# ---- Static constant extraction from the Init tier (no exec) ----
def extract_simple_consts(src):
    """Return ``{name: number}`` for every top-level ``NAME = <number literal>``
    in *src* (preserving source order). Imports, functions, dict/list literals,
    and anything non-numeric are ignored. Safe: AST only, never executes."""
    consts = {}
    try:
        tree = ast.parse(src or "")
    except SyntaxError:
        return consts
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            val = _literal_number(node.value)
            if val is not None:
                consts[node.targets[0].id] = val
    return consts


def _literal_number(node):
    if (isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _literal_number(node.operand)
        if inner is not None:
            return -inner
    return None


def _fmt_num(v):
    if isinstance(v, bool):
        return "1.0" if v else "0.0"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, int):
        return str(v)
    raise UnsupportedComputeError("non-numeric constant %r%s" % (v, _HINT))


# ---- Conversion state ----
class _Ctx:
    def __init__(self, consts):
        self.consts            = consts or {}
        self.params            = []     # ordered [(otype, name, default)]
        self.param_names       = set()
        self.local_scalars     = set()  # python names that became float locals
        self.uv_map            = {}     # python uv name -> 'u' / 'v'
        self.color_var         = None   # python name of the sampled colour
        self.osl_color         = "grid"
        self.referenced_consts = set()

    def add_param(self, otype, name, default):
        if name not in self.param_names:
            self.param_names.add(name)
            self.params.append((otype, name, default))


# ---- Expression transpiler (AST transform -> ast.unparse) ----
class _OslExprTransform(ast.NodeTransformer):
    """Rewrites a Python expression AST into an OSL-valid one, validating that
    every name/call is in the v1 grammar (raising otherwise)."""

    def __init__(self, ctx):
        self.ctx = ctx

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            pname = node.attr
            # A scalar read of an input -> a float param (the image input is
            # handled by the texture idiom, not here).
            self.ctx.add_param("float", pname, "0.0")
            return ast.copy_location(ast.Name(id=pname, ctx=ast.Load()), node)
        raise UnsupportedComputeError(
            "unsupported attribute access '%s'%s" % (_safe_unparse(node), _HINT))

    def visit_Call(self, node):
        func = node.func
        if (isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name) and func.value.id == "math"):
            fn = func.attr
            if fn not in MATH_FUNCS:
                raise UnsupportedComputeError(
                    "math.%s is not available in OSL%s" % (fn, _HINT))
            args = [self.visit(a) for a in node.args]
            return ast.copy_location(
                ast.Call(func=ast.Name(id=fn, ctx=ast.Load()),
                         args=args, keywords=[]), node)
        if isinstance(func, ast.Name):
            fid = func.id
            if fid in DROP_CASTS and len(node.args) == 1 and not node.keywords:
                return self.visit(node.args[0])
            if fid in MATH_FUNCS or fid in BUILTIN_FUNCS:
                args = [self.visit(a) for a in node.args]
                return ast.copy_location(
                    ast.Call(func=ast.Name(id=fid, ctx=ast.Load()),
                             args=args, keywords=[]), node)
        raise UnsupportedComputeError(
            "unsupported call '%s'%s" % (_safe_unparse(node), _HINT))

    def visit_Name(self, node):
        nid = node.id
        if nid in self.ctx.uv_map:
            return ast.copy_location(
                ast.Name(id=self.ctx.uv_map[nid], ctx=ast.Load()), node)
        if self.ctx.color_var and nid == self.ctx.color_var:
            return ast.copy_location(
                ast.Name(id=self.ctx.osl_color, ctx=ast.Load()), node)
        if nid in self.ctx.consts:
            self.ctx.referenced_consts.add(nid)
            return node
        if (nid in self.ctx.local_scalars or nid in self.ctx.param_names
                or nid in ("u", "v")):
            return node
        raise UnsupportedComputeError(
            "unknown name '%s' in Compute look-math%s" % (nid, _HINT))

    # OSL floats support only + - * /; everything else (//, **, %, ^, &, |, <<,
    # >>, @) unparses to INVALID OSL ('//' is even a line comment), so reject and
    # defer to the AI. Children are still visited, so a nested bad name/cast is
    # still caught.
    _OSL_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)

    def visit_BinOp(self, node):
        if not isinstance(node.op, self._OSL_BINOPS):
            raise UnsupportedComputeError(
                "operator '%s' is not supported in OSL v1%s"
                % (_safe_unparse(node), _HINT))
        node.left  = self.visit(node.left)
        node.right = self.visit(node.right)
        return node

    # Only unary +/- are valid on OSL floats; reject ~ (Invert) and `not`.
    _OSL_UNARYOPS = (ast.UAdd, ast.USub)

    def visit_UnaryOp(self, node):
        if not isinstance(node.op, self._OSL_UNARYOPS):
            raise UnsupportedComputeError(
                "unary operator '%s' is not supported in OSL v1%s"
                % (_safe_unparse(node), _HINT))
        node.operand = self.visit(node.operand)
        return node

    def visit_Constant(self, node):
        v = node.value
        # No None/bool/str literals in this OSL grammar -> defer to AI.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise UnsupportedComputeError(
                "non-numeric literal %r is not supported in OSL v1%s"
                % (v, _HINT))
        # Python's 1/2 is 0.5, OSL's is 0 (integer division on int operands).
        # Emit every numeric literal as a float to keep the math faithful.
        if isinstance(v, int):
            return ast.copy_location(ast.Constant(value=float(v)), node)
        return node

    # Constructs that ast.unparse would render as INVALID OSL -> defer to AI.
    def visit_Subscript(self, node):
        raise UnsupportedComputeError(
            "array indexing is not supported in OSL v1%s" % _HINT)

    def visit_IfExp(self, node):
        raise UnsupportedComputeError(
            "conditional expressions are not supported in OSL v1%s" % _HINT)

    def visit_Compare(self, node):
        raise UnsupportedComputeError(
            "comparisons are not supported in OSL v1%s" % _HINT)

    def visit_BoolOp(self, node):
        raise UnsupportedComputeError(
            "boolean operators are not supported in OSL v1%s" % _HINT)

    def _reject(self, node):
        raise UnsupportedComputeError(
            "unsupported expression '%s'%s" % (_safe_unparse(node), _HINT))

    visit_JoinedStr      = _reject       # f-strings
    visit_FormattedValue = _reject
    visit_Tuple          = _reject
    visit_List           = _reject
    visit_Dict           = _reject
    visit_Set            = _reject
    visit_Lambda         = _reject
    visit_ListComp       = _reject
    visit_SetComp        = _reject
    visit_DictComp       = _reject
    visit_GeneratorExp   = _reject
    visit_Starred        = _reject


def _transpile(node, ctx):
    new = _OslExprTransform(ctx).visit(copy.deepcopy(node))
    ast.fix_missing_locations(new)
    return ast.unparse(new)


def _safe_unparse(node):
    try:
        return ast.unparse(node)
    except Exception:
        return "<expr>"


def _unparse(node):
    try:
        return ast.unparse(node)
    except Exception:
        return ""


# ---- Statement / idiom matchers ----
def _is_self_attr(node):
    return (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "self")


def _is_assign_to(st, name):
    return (isinstance(st, ast.Assign) and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Name)
            and st.targets[0].id == name)


def _assign_self_target(st):
    if isinstance(st, ast.Assign) and len(st.targets) == 1 and _is_self_attr(st.targets[0]):
        return st.targets[0].attr
    return None


def _subscript_indices(sub):
    s = sub.slice
    if isinstance(s, ast.Index):  # py<3.9 compatibility
        s = s.value
    if isinstance(s, ast.Tuple):
        return s.elts
    return [s]


def _match_image_load(st):
    """``X = f(self.A)`` -> (X, A). Any single-arg call on a self attr."""
    if (isinstance(st, ast.Assign) and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Name)):
        v = st.value
        if (isinstance(v, ast.Call) and len(v.args) == 1 and not v.keywords
                and _is_self_attr(v.args[0])):
            return (st.targets[0].id, v.args[0].attr)
    return None


def _match_shape_read(st, img_vars):
    """``X = IMG.shape[k]`` -> True (consumed)."""
    if (isinstance(st, ast.Assign) and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Name)):
        v = st.value
        if (isinstance(v, ast.Subscript) and isinstance(v.value, ast.Attribute)
                and v.value.attr == "shape"
                and isinstance(v.value.value, ast.Name)
                and v.value.value.id in img_vars):
            return True
    return False


def _match_uv_unpack(st):
    """``P, Q = self.uvCoord`` -> (P, Q)."""
    if (isinstance(st, ast.Assign) and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Tuple)):
        tgt = st.targets[0]
        if (len(tgt.elts) == 2 and all(isinstance(e, ast.Name) for e in tgt.elts)
                and _is_self_attr(st.value) and st.value.attr == "uvCoord"):
            return (tgt.elts[0].id, tgt.elts[1].id)
    return None


def _match_sample(st, img_vars):
    """``R = IMG[I, J]`` -> (R, IMG, [I, J])."""
    if (isinstance(st, ast.Assign) and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Name)):
        v = st.value
        if (isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name)
                and v.value.id in img_vars):
            idx = _subscript_indices(v)
            if len(idx) == 2 and all(isinstance(x, ast.Name) for x in idx):
                return (st.targets[0].id, v.value.id, [idx[0].id, idx[1].id])
    return None


def _detect_texture_idiom(stmts, ctx):
    """Recognize the canonical image-sample idiom. Registers the ``filename``
    param + the colour var, returns idiom info (with consumed stmt indices) or
    None if the shape isn't present."""
    img_files = {}
    for st in stmts:
        info = _match_image_load(st)
        if info:
            img_files[info[0]] = info[1]
    if not img_files:
        return None

    sample = sample_index = None
    for i, st in enumerate(stmts):
        m = _match_sample(st, img_files)
        if m:
            sample, sample_index = m, i
            break
    if not sample:
        return None
    color_var, img_var, idx_names = sample
    row_idx, col_idx = idx_names[0], idx_names[1]   # arr[row, col]

    uv = None
    for st in stmts:
        u = _match_uv_unpack(st)
        if u:
            uv = u
            break
    if not uv:
        return None
    col_axis, row_axis = uv[0], uv[1]   # "u, v = self.uvCoord" -> u=col, v=row

    consumed = set()
    flip     = False
    for i, st in enumerate(stmts):
        if _match_image_load(st):
            consumed.add(i)
        elif _match_shape_read(st, img_files):
            consumed.add(i)
        elif _match_uv_unpack(st):
            consumed.add(i)
        elif _is_assign_to(st, row_idx) or _is_assign_to(st, col_idx):
            consumed.add(i)
            if _is_assign_to(st, row_idx):
                src = _unparse(st.value)
                if ("1.0 - %s" % row_axis) in src or ("1 - %s" % row_axis) in src:
                    flip = True
        elif i == sample_index:
            consumed.add(i)

    ctx.add_param("string", "filename", '""')
    ctx.color_var        = color_var
    ctx.uv_map[col_axis] = "u"
    ctx.uv_map[row_axis] = "v"
    return {
        "consumed":     consumed,
        "sample_index": sample_index,
        "file_param":   "filename",
        "u_expr":       "u",
        "flip_expr":    "1.0 - v" if flip else "v",
    }


# ---- Output-write recognition ----
def _is_color_comp(node, color_var, i):
    """``rgb[i]`` or ``float(rgb[i])`` for the sampled colour."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in DROP_CASTS and len(node.args) == 1):
        node = node.args[0]
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
            and node.value.id == color_var):
        idxs = _subscript_indices(node)
        if (len(idxs) == 1 and isinstance(idxs[0], ast.Constant)
                and idxs[0].value == i):
            return True
    return False


def _match_color_times_scalar(value, color_var):
    """``(rgb[0]*k, rgb[1]*k, rgb[2]*k)`` -> the scalar name ``k`` (else None)."""
    scalar = None
    for i, e in enumerate(value.elts):
        if not (isinstance(e, ast.BinOp) and isinstance(e.op, ast.Mult)):
            return None
        comp = other = None
        for side in (e.left, e.right):
            if _is_color_comp(side, color_var, i):
                comp = side
            else:
                other = side
        if comp is None or not isinstance(other, ast.Name):
            return None
        if scalar is None:
            scalar = other.id
        elif scalar != other.id:
            return None
    return scalar


def _emit_output_expr(value, ctx):
    if isinstance(value, ast.Tuple) and len(value.elts) == 3 and ctx.color_var:
        scalar = _match_color_times_scalar(value, ctx.color_var)
        if scalar is not None:
            return "%s * %s" % (
                ctx.osl_color,
                _transpile(ast.Name(id=scalar, ctx=ast.Load()), ctx),
            )
    if isinstance(value, ast.Tuple) and len(value.elts) == 3:
        return "color(%s)" % ", ".join(_transpile(e, ctx) for e in value.elts)
    return _transpile(value, ctx)


def _emit_statement(st, ctx):
    self_attr = _assign_self_target(st)
    if self_attr == "outAlpha":
        return None                      # colour output drops alpha
    if self_attr == "outColor":
        return "    outColor = %s;" % _emit_output_expr(st.value, ctx)
    if self_attr is not None:
        raise UnsupportedComputeError(
            "writing self.%s is not supported in OSL v1%s" % (self_attr, _HINT))
    if (isinstance(st, ast.Assign) and len(st.targets) == 1
            and isinstance(st.targets[0], ast.Name)):
        name = st.targets[0].id
        expr = _transpile(st.value, ctx)
        ctx.local_scalars.add(name)
        return "    float %s = %s;" % (name, expr)
    raise UnsupportedComputeError(
        "unsupported statement: %s%s" % (type(st).__name__, _HINT))


# ---- Public entry point ----
def convert_compute_to_osl(compute_src, consts=None, shader_name="mpyfile_shader"):
    """Transpile an mPyFile Compute look-math string into an OSL shader string.

    *consts* maps look-constant names (from the Init tier; see
    :func:`extract_simple_consts`) to numbers. Raises
    :class:`UnsupportedComputeError` for anything outside the v1 grammar.
    """
    try:
        tree = ast.parse(compute_src or "")
    except SyntaxError as exc:
        raise UnsupportedComputeError(
            "Compute source is not valid Python (%s)%s" % (exc, _HINT))

    ctx      = _Ctx(consts)
    stmts    = list(tree.body)
    idiom    = _detect_texture_idiom(stmts, ctx)
    consumed = idiom["consumed"] if idiom else set()

    body_lines      = []
    emitted_texture = False
    for i, st in enumerate(stmts):
        if i in consumed:
            if idiom and i == idiom["sample_index"] and not emitted_texture:
                body_lines.append(
                    "    // grid: same top-down (1 - v) flip the Compute tab samples with.")
                body_lines.append(
                    "    color %s = texture(%s, %s, %s);" % (
                        ctx.osl_color, idiom["file_param"],
                        idiom["u_expr"], idiom["flip_expr"]))
                emitted_texture = True
            continue
        emitted = _emit_statement(st, ctx)
        if emitted is not None:
            body_lines.append(emitted)

    const_lines = [
        "    float %s = %s;" % (name, _fmt_num(ctx.consts[name]))
        for name in ctx.consts if name in ctx.referenced_consts
    ]

    header = ["shader %s(" % shader_name]
    for otype, name, default in ctx.params:
        header.append("    %s %s = %s," % (otype, name, default))
    header.append("    output color outColor = color(0))")
    header.append("{")

    lines = header + const_lines + body_lines + ["}"]
    return "\n".join(lines) + "\n"


# ---- Tractability gate -- is an OSL translation even POSSIBLE? ----
# self.<attr> targets inside the OSL colour-shader contract. A write to any
# OTHER self attr has no OSL equivalent: a texture shader produces a colour,
# not arbitrary typed outputs.
_OSL_OUTPUT_ATTRS = frozenset(("outColor", "outAlpha"))


def _extra_output_reason(names):
    return (
        "the Compute writes non-colour output(s) (%s); an OSL texture shader "
        "produces only a colour (outColor / outAlpha), so these outputs have "
        "no OSL equivalent and the look cannot be translated to a single OSL "
        "shader." % ", ".join("self.%s" % n for n in names))


def assess_osl_tractability(compute_src, init_src=None,
                            input_attrs=None, output_attrs=None):
    """Return ``(tractable, reason)`` for translating this Compute to OSL.

    ``tractable=True`` (reason ``""``) means the look-math is at least PLAUSIBLY
    expressible in OSL -- either the deterministic transpiler handles it, or (if
    it raises :class:`UnsupportedComputeError`) the AI arm has a real chance.
    This is NOT a promise the AI will succeed; it is a fast, cheap veto for the
    cases that are STRUCTURALLY IMPOSSIBLE in OSL, so the UI refuses them
    immediately with an actionable reason instead of burning minutes on a doomed
    AI round (the compositeTexture failure that motivated this gate).

    ``tractable=False`` (with a human-readable ``reason``) is returned for:

    * an ARRAY-valued input attribute (``input_attrs[name]['is_array']``) -- an
      OSL shader parameter is a single scalar / string / colour, not a runtime
      array of textures (compositeTexture's ``filePaths``);
    * a non-colour typed OUTPUT -- either an ``output_attrs`` entry beyond
      ``outColor`` / ``outAlpha`` (compositeTexture's int ``maxWidth`` /
      ``maxHeight``), or a Compute assignment to ``self.<x>`` for such an ``x``
      detected statically from ``compute_src``.

    Maya-free + AST-only (never executes the source); safe on unparseable input
    (returns tractable -- the deterministic arm reports the syntax error).
    ``input_attrs`` / ``output_attrs`` are the ``{name: {"attr_type",
    "is_array"}}`` maps from the node (``get_input_attr_map`` /
    ``get_output_attr_map``); both optional -- the source scan alone catches the
    multi-output shape.
    """
    # (1) Array-valued input -> no OSL shader-parameter idiom.
    for name, meta in (input_attrs or {}).items():
        if isinstance(meta, dict) and meta.get("is_array"):
            return False, (
                "input '%s' is an array; an OSL shader parameter is a single "
                "scalar/string/colour, not a runtime array of textures, so "
                "this node cannot be expressed as a single OSL shader." % name)

    # (2) Extra typed outputs (from the attr map) -> not a colour shader.
    extra_out = [n for n in (output_attrs or {}) if n not in _OSL_OUTPUT_ATTRS]
    if extra_out:
        return False, _extra_output_reason(sorted(extra_out))

    # (3) Extra self.<x> writes detected statically in the Compute source.
    try:
        tree = ast.parse(compute_src or "")
    except SyntaxError:
        return True, ""  # a syntax error is the deterministic arm's to report
    written = []
    seen    = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (_is_self_attr(tgt) and tgt.attr not in _OSL_OUTPUT_ATTRS
                        and tgt.attr not in seen):
                    seen.add(tgt.attr)
                    written.append(tgt.attr)
    if written:
        return False, _extra_output_reason(written)
    return True, ""
