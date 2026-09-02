"""py_to_cpp -- deterministic numpy-subset AST -> C++ transpiler (nd:: runtime).

This is the mechanical lowering half of the general-purpose port pipeline. It
walks a Python compute function's AST and emits C++ that operates on the
``nd::`` header-only runtime (nd_runtime.h). Every construct is either lowered
to a proven ``nd::`` call or HARD-REJECTED with a precise ``UnsupportedSpec`` --
there is no "best effort" path. Rejection is a feature: codegen catches it and
falls back to the AI porter for that node, so coverage grows deliberately and a
partial/incorrect port is never emitted.

Design (SP-2):
  * A small type/shape lattice (``CppType``: scalar|array x double|int64|bool,
    plus an optional static rank) is threaded through expression evaluation so
    the transpiler can pick ``Array<T>`` template params, insert ``astype<>``
    casts for numpy dtype promotion, and honour true-division float promotion.
  * A single forward pass infers types AND emits code. Variable declarations are
    HOISTED to the function top with explicit types (arrays default-construct
    empty, scalars zero) and every assignment is a plain assign -- this makes
    Python's function-scoped variables (assigned in one branch, read after)
    lower correctly to C++ block scoping.
  * ``self.<attr>`` reads resolve against a caller-supplied environment so the
    codegen integration (SP-4) can bind inputs to pre-materialised nd::Array
    locals.

Supported surface:
  * P0 -- scalar arithmetic + control flow (for-range / while / if-elif-else /
    break / continue / return / aug-assign); numpy constructors
    (zeros/ones/full/eye/arange/linspace/array/*_like/expand_dims); elementwise
    (+ - * / // % ** unary-neg, maximum/minimum/clip); ufuncs (sin..sign);
    reductions (sum/mean/max/min, linalg.norm); linalg (dot/cross/matmul/@);
    shape manip (reshape/ravel/flatten/transpose/.T/newaxis/astype/copy);
    slicing + slice-assign; np.random.RandomState(seed).random(...) via
    nd::MT19937.
  * P1 (SP-5) -- boolean masks + array comparisons; np.where; fancy/gather
    indexing (integer-array index + np.take); nonzero (tuple-unpacked);
    concatenate/stack/hstack/vstack/column_stack; tile/roll; stencil neighbour
    reads; plus recursion-free inline-INIT helper recovery and persistent
    node-state locals.
  * P2 (SP-6) -- linalg on stacked 3x3 (and batched leading dims): np.diag
    (1-D<->2-D), np.linalg.det, np.einsum (explicit 'in,in->out' subscripts,
    incl. diagonal + batched Procrustes/Kabsch forms), np.transpose(a, axes),
    and np.linalg.svd via tuple-unpack ``U, S, Vt = np.linalg.svd(a)`` mapped to
    the deterministic Jacobi ``nd::svd`` (no BLAS/LAPACK).

Still HARD-REJECTED to the AI porter (which also emits pure C++, so the
translate-or-reject HARD RULE holds): np.argwhere, and np.linalg.pinv (which
needs a GENERAL svd -- nd::svd is 3x3-only, so there is nothing deterministic to
build it on). A BATCHED (...,N,N) np.linalg.solve also rejects; the single (N,N)
form is lowered. Rejection is a feature -- codegen catches UnsupportedSpec and
routes the node to the porter; a partial/incorrect deterministic port is never
emitted.

This list is easy to leave stale: np.linalg.inv, np.outer and the reductions
argsort/sort/prod/diff/pad/unique/repeat were all named here long after they had
in fact been lowered.
"""

from __future__ import annotations

import ast
import re

from mpynode.native.compiler.errors import UnsupportedSpec

# CANONICAL module origins. Dispatch is on the origin a name RESOLVES to, never
# on how it is spelled -- see _parse_import_bindings / canonical_dotted.
_CANON_NUMPY = "numpy"
_CANON_MATH = "math"
# `from mpynode import ndio` -- named ARRAY file IO. The Python half is
# mpynode/ndio.py; the C++ half is compiler/kernels/nd_io_cpp.py. Both must
# agree, including the degrade-to-EMPTY rule for a missing/malformed file.
_CANON_NDIO = "mpynode.ndio"

# Fallback for a name with NO import in view. The mpynode Init header seeds
# `np`, and computes rely on that ambient binding, so an absent import must
# behave exactly as it always has. Only an import that actually rebinds the name
# overrides this -- which is what makes `import mylib as np` stop meaning numpy.
_AMBIENT_MODULES = {"np": _CANON_NUMPY, "numpy": _CANON_NUMPY,
                    "math": _CANON_MATH, "ndio": _CANON_NDIO}

# A name whose origin cannot be trusted: rebound at module level, or imported
# relatively (no resolvable absolute origin). It must never match a module.
_SHADOWED_ORIGIN = "?shadowed"

# Builtins that none of the supported modules export, so `from numpy import *`
# leaves them as builtins. numpy DOES export abs/min/max/round/sum/any/all --
# those are deliberately absent here, because after a star import they really do
# mean np.<name> and must keep resolving that way (measured against numpy 1.26,
# not assumed). An explicit `from numpy import float64 as float` still wins: the
# check is skipped when the name is bound by an import or by a local.
_NEVER_MODULE_BUILTINS = ("len", "int", "float", "bool", "str", "list",
                          "getattr", "hasattr", "isinstance")

# Classes `isinstance(<statically-None value>, ...)` may name (plus np.ndarray,
# matched through the canonical resolver). Every entry answers False for None,
# which is what makes the fold decidable; `object` and `type(None)` are
# deliberately absent -- they are the two spellings that would answer True.
_ISINSTANCE_TYPES = ("bool", "bytes", "complex", "dict", "float", "frozenset",
                     "int", "list", "set", "str", "tuple")


def _parse_import_bindings(sources):
    """``{bound_name: canonical dotted origin}`` for the imports in SOURCES.

    Python binds a module -- or a name out of one -- in several shapes, and a
    transpiler that dispatches on the SPELLING mishandles every shape but the
    conventional ``np.``: it rejects valid code, or worse, treats the NAME ``np``
    as numpy when the source aliased something else to it.

        import numpy                   ->  numpy : numpy            (root name)
        import numpy as np             ->  np    : numpy
        import numpy.linalg            ->  numpy : numpy            (root name!)
        import numpy.linalg as la      ->  la    : numpy.linalg
        from numpy import sin          ->  sin   : numpy.sin
        from numpy import sin as s     ->  s     : numpy.sin
        from numpy import linalg as la ->  la    : numpy.linalg
        from numpy.linalg import norm  ->  norm  : numpy.linalg.norm

    Imports are collected from ANY depth (a ``def`` may import too), but
    REBINDING is only honoured at module level -- that is the scope an import
    binds, and a function-local of the same name is handled precisely by the
    ``env`` check in ``Transpiler._canon`` instead of being guessed at here.

    Returns ``(bindings, star_modules)``. ``star_modules`` are the absolute
    modules of any ``from X import *``, whose members resolve as ``X.<name>``.
    """
    srcs = [sources] if isinstance(sources, str) else list(sources or [])
    bindings, stars, rebound = {}, [], set()
    for src in srcs:
        if not src or not src.strip():
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.asname:
                        bindings[a.asname] = a.name
                    else:
                        # `import a.b.c` binds the ROOT name `a`, not `a.b.c`.
                        root = a.name.split(".", 1)[0]
                        bindings[root] = root
            elif isinstance(n, ast.ImportFrom):
                if n.level:            # relative: no resolvable absolute origin
                    for a in n.names:
                        if a.name != "*":
                            bindings[a.asname or a.name] = _SHADOWED_ORIGIN
                    continue
                mod = n.module or ""
                for a in n.names:
                    if a.name == "*":
                        # de-duped: the same source is often handed in twice
                        # (as the helper source AND the const source), and a
                        # repeat must not read as a second, ambiguous star.
                        if mod not in stars:
                            stars.append(mod)
                    else:
                        bindings[a.asname or a.name] = "%s.%s" % (mod, a.name)
        for stmt in tree.body:         # module-level rebinding only
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                rebound.add(stmt.name)
            elif isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    for sub in ast.walk(t):
                        # ctx=Store only: `a.b = x` and `a[i] = x` MUTATE a,
                        # they do not rebind the name, so `a` is still whatever
                        # it was imported as.
                        if isinstance(sub, ast.Name) \
                                and isinstance(sub.ctx, ast.Store):
                            rebound.add(sub.id)
            elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign, ast.For)):
                if isinstance(getattr(stmt, "target", None), ast.Name):
                    rebound.add(stmt.target.id)
    for name in rebound:
        bindings[name] = _SHADOWED_ORIGIN
    return bindings, stars


def dotted_name(node):
    """Resolve a (possibly dotted) name expression to 'a.b.c' or None."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def canonical_dotted(dotted, bindings, stars=()):
    """``la.norm`` -> ``numpy.linalg.norm``: resolve the HEAD through BINDINGS.

    A head with no binding is returned unchanged, so a caller that seeds
    ``bindings`` with the ambient defaults keeps its existing behaviour and one
    that does not (the locator's wall clock) resolves only explicit imports."""
    if not dotted:
        return dotted
    head, _, rest = dotted.partition(".")
    origin = bindings.get(head)
    if origin is None and len(stars) == 1 and not rest:
        # `from numpy import *` makes an unbound BARE name a member of that
        # module. It cannot introduce a dotted path, so `self.v.copy` must stay
        # unresolved -- claiming it would route a method call into np.<...>.
        # Two star imports leave even a bare name ambiguous, so nothing resolves.
        origin = "%s.%s" % (stars[0], head)
    if origin is None:
        return dotted
    if origin == _SHADOWED_ORIGIN:
        return _SHADOWED_ORIGIN
    return origin + ("." + rest if rest else "")

# nd_io dtype descriptor (kind, itemsize) per AUTHORED dtype spelling -- the pair
# the raw reader needs to interpret a headerless buffer.
#
# Keyed on what the AUTHOR wrote, never on the promoted transpiler dtype. np.float32
# promotes to the 'double' lattice entry for arithmetic, but the FILE still holds
# 4-byte floats: descriptor ('f', 8) walks it in 8-byte strides and pairs adjacent
# elements into garbage -- an 8-element float32 file read back as 4 nonsense values.
# The destination C++ type stays the promoted one; only the SOURCE layout is
# described here, and nd_io_get converts elementwise via nd_io_elem_f
# (kernels/nd_io_cpp.py:132), which handles every (kind, size) pair below.
_NDIO_RAW = {
    "float": ("f", 8), "float64": ("f", 8), "double": ("f", 8),
    "float32": ("f", 4),
    "int": ("i", 8), "int64": ("i", 8), "intp": ("i", 8), "int_": ("i", 8),
    "int32": ("i", 4), "int16": ("i", 2), "int8": ("i", 1),
    "uint": ("u", 8), "uint64": ("u", 8), "uint32": ("u", 4),
    "uint16": ("u", 2), "uint8": ("u", 1),
    # np.bool_.itemsize is 1, so a numpy bool file is one BYTE per element.
    "bool": ("i", 1), "bool_": ("i", 1),
}


def env_cpp_name(dotted):
    """C++ local identifier that a compute-block read of a bound (dotted) env
    name -- e.g. ``self.pointsIn`` -- lowers to.

    The transpiler emits this name for every ``self.<attr>`` read; the codegen
    integration (nd_lower) declares a materialised nd:: local under exactly this
    name. The ``ndin_`` prefix keeps it distinct from codegen's ``in_``/``out_``/
    ``h_`` handles and from user-declared block locals.
    """
    return "ndin_" + re.sub(r"[^0-9A-Za-z_]", "_", dotted)

# dtype lattice: higher wins in numeric promotion.
_DTYPE_RANK = {"bool": 0, "int64": 1, "double": 2}
_CTYPE = {"bool": "bool", "int64": "int64_t", "double": "double"}

# A generated C++ operand string is "trivial" -- free to duplicate inline -- when
# it holds no function/method call: a bare name, literal, cast, member access, or
# plain arithmetic thereof. `[A-Za-z_]\w*\s*\(` matches `matmul(`, `foo.item(`,
# a helper call `_h(`, etc.; it does NOT match a cast `(double)(x)` (no identifier
# precedes that `(`). Non-trivial operands that abs/min/max would name 2-3x get
# bound to one const first (see Transpiler._cse_bind) so real work runs once.
_CALL_RE = re.compile(r"[A-Za-z_]\w*\s*\(")


def _is_trivial_operand(code):
    return _CALL_RE.search(code) is None


# Trailing argument of an outermost ``nd::newaxis(<expr>, <int literal>)``.
_TRAILING_NEWAXIS_RE = re.compile(r"^nd::newaxis\(.*,\s*(-?\d+)\)$", re.S)


def _is_trailing_newaxis_view(v):
    """True if ``v`` is a bare ``x[..., None]`` view inserting the length-1 axis
    at its LAST axis -- a value that can NEVER be C-contiguous.

    ``nd::newaxis`` inserts a stride of 0 at the new axis while ``nd::c_strides``
    always leaves its LAST entry at 1, so ``Array::is_contiguous()`` is false for
    every shape such a view can have, the empty ones included. (At a non-last
    axis the matching c_stride is ``prod(shape[pos+1:])``, which IS 0 when a
    later dim is 0 -- so only the trailing case is unconditional.)

    Matched on ``v.code`` rather than on a flag threaded through the type
    lattice because ``code`` is verbatim what initialises the bound C++ leaf
    whose ``is_contiguous()`` the fused guard tests -- the two cannot drift.
    A nested/wrapped newaxis (``nd::astype<>(nd::newaxis(...))`` materialises a
    contiguous copy) is deliberately NOT matched.
    """
    rank = v.type.rank
    if rank is None or not v.code.startswith("nd::newaxis("):
        return False
    m = _TRAILING_NEWAXIS_RE.match(v.code)
    if m is None:
        return False
    # The leading `nd::newaxis(` must be the OUTERMOST call: its paren may not
    # close before the end of the text.
    depth = 0
    for i, ch in enumerate(v.code):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                if i != len(v.code) - 1:
                    return False
                break
    pos = int(m.group(1))
    if pos < 0:
        pos += rank
    return pos == rank - 1


def _promote(d1, d2):
    # Defensive: a non-numeric dtype (e.g. the 'str' carrier) must NEVER reach
    # numeric promotion -- reject cleanly (UnsupportedSpec is caught by
    # try_lower_compute) instead of KeyError-crashing the whole codegen. The str
    # entry points (concat/equality) are handled before any _promote call; this
    # only fires for an unsupported string use, which then falls back to the porter.
    if d1 not in _DTYPE_RANK or d2 not in _DTYPE_RANK:
        raise UnsupportedSpec("py_to_cpp: non-numeric dtype in numeric promotion "
                              "(%r, %r)" % (d1, d2))
    return d1 if _DTYPE_RANK[d1] >= _DTYPE_RANK[d2] else d2


class CppType:
    """A lowered value's static type: kind + element dtype + optional rank.

    kind  : 'scalar' | 'array' | 'shape' | 'rng' | 'texbuf' | 'str'
    dtype : 'double' | 'int64' | 'bool'   (element type; irrelevant for shape/rng);
            'str' for the 'str' kind (a std::string carrier -- pass-through /
            concatenation / equality only; any numeric use is rejected).
    rank  : int for arrays when statically known, else None. 0 == 0-d array.
    code  : for the 'shape' pseudo-kind, the C++ expression yielding the nd::Shape.
    handle: for the opaque 'texbuf' pseudo-kind (a blessed read_texture() result),
            a (ptr_var, w_var, h_var) tuple of C++ local names. Neither scalar nor
            array -- carried between a blessed load and a blessed sample.
    """

    __slots__ = ("kind", "dtype", "rank", "code", "handle")

    def __init__(self, kind, dtype="double", rank=None, code=None, handle=None):
        self.kind = kind
        self.dtype = dtype
        self.rank = rank
        self.code = code
        self.handle = handle

    def is_scalar(self):
        return self.kind == "scalar"

    def is_array(self):
        return self.kind == "array"

    def __repr__(self):
        return "CppType(%s,%s,rank=%r)" % (self.kind, self.dtype, self.rank)


def scalar_t(dtype):
    return CppType("scalar", dtype)


def array_t(dtype, rank=None):
    return CppType("array", dtype, rank)


def _scalarish(t):
    """True for a value ``_cast_scalar`` can consume as a plain scalar.

    A rank-0 array -- ``a[i]`` with a full integer index, or a whole-array
    reduction -- holds ONE number and already lowers through ``.item()`` / the
    raw ``nd::atN`` form, which is why the ``float(...)``-wrapped spelling
    works. Guards that mean "not a real (rank>=1) array" must test THIS, not
    ``is_scalar()``, or they reject the unwrapped spelling of an expression they
    would happily accept one ``float()`` call later. Rank ``None`` (an
    unknown-rank result) is accepted for exactly the same reason
    ``_cast_scalar`` accepts it.
    """
    return t.is_scalar() or (t.is_array() and t.rank in (0, None))


def str_t():
    # A std::string value carrier: only pass-through, concatenation (+) and
    # equality (==/!=) are lowered; every numeric consumer rejects it (see the
    # str guards in ex_BinOp/ex_Compare/_as_bool/_cast_scalar + defensive _promote).
    return CppType("str", "str")


def strv_t():
    # A std::vector<std::string> carrier produced by list(<str>): only
    # pass-through and len() are lowered. It shares dtype 'str' with str_t so the
    # same guards catch both -- _CTYPE has no 'str' entry, so an unguarded
    # numeric path would KeyError rather than reject cleanly.
    return CppType("strv", "str")


def kdtree_t():
    # An nd::KDTree bound to a local by `tree = cKDTree(pts)`, consumed only by
    # its query methods -- the same stateful-object shape as 'rng'. Every numeric
    # guard below lists it alongside 'rng' so an arithmetic use rejects cleanly
    # rather than reaching _CTYPE (which has no entry for it).
    return CppType("kdtree", "kdtree")


# Pseudo-kinds that carry no numeric value. Arithmetic, comparison, casting and
# truthiness must all reject them. Collected here because they used to be spelled
# out at 13 call sites -- some as denylists, one (the subscript guard) as an
# INVERTED allowlist -- so adding a kind to some and missing others failed OPEN,
# silently lowering nonsense. Each constant mirrors ONE pre-existing spelling
# exactly, plus 'kdtree'; kept as three so this stays strictly additive.
_VALUELESS_KINDS = ("shape", "rng", "kdtree")
_OPAQUE_KINDS = ("shape", "rng", "texbuf", "kdtree")
_NON_NUMERIC_KINDS = _OPAQUE_KINDS + ("str", "strv")


class Val:
    """An evaluated expression: its C++ code string and its CppType.

    ``raw`` (optional) is an ALTERNATIVE C++ expression that yields this value as
    a raw scalar WITHOUT allocating an nd:: view -- set only for a fully
    integer-indexed subscript (``nd::atN(base, i, j, ...)``). Scalar consumers
    (_cast_scalar / _scalar_int_of) use it instead of ``code.item()`` to avoid a
    per-access heap allocation; array-context consumers keep using ``code`` (the
    nd::slice). None when there is no raw form.

    ``fuse`` (optional) is a FuseNode describing this value as an ELEMENTWISE
    expression tree (Phase-2 fusion). When set, an assignment sink may emit ONE
    scalar loop composing the whole tree instead of the nested ``nd::`` calls in
    ``code`` -- ``code`` is always kept as the (byte-identical) fallback. None
    when the value is not a fusable elementwise result.
    """

    __slots__ = ("code", "type", "raw", "fuse")

    def __init__(self, code, typ, raw=None, fuse=None):
        self.code = code
        self.type = typ
        self.raw = raw
        self.fuse = fuse


class FuseNode:
    """A node in a Phase-2 ELEMENTWISE fusion tree.

    ``kind`` is one of:
      - "arr": a leaf read PER ELEMENT from an array ``val`` (rank >= 1).
      - "scl": a leaf read ONCE from a scalar ``val`` (hoisted before the loop).
      - "op":  combines child FuseNodes via ``emit`` -- a callable taking the
               children's per-element scalar Vals and returning ONE scalar Val
               built by the transpiler's EXISTING scalar lowering. Reusing that
               lowering is what makes the fused loop body byte-identical to the
               nested nd:: element computation it replaces.
    """
    __slots__ = ("kind", "val", "emit", "children")

    def __init__(self, kind, val=None, emit=None, children=None):
        self.kind = kind
        self.val = val
        self.emit = emit
        self.children = children if children is not None else []


class TranspileResult:
    def __init__(self, arg_names, decl_lines, body_lines, returns):
        self.arg_names = arg_names
        self.decl_lines = decl_lines      # hoisted declarations (indent 1)
        self.body_lines = body_lines      # statement body (indent 1)
        self.returns = returns            # list[CppType] observed at `return`
        self.state_members = {}           # persistent self-var name -> CppType

    def all_lines(self):
        return list(self.decl_lines) + list(self.body_lines)


def _static_int(node):
    """The compile-time int value of `node`, or None if it is not one.

    `-1` is NOT an ast.Constant -- it parses as UnaryOp(USub, Constant(1)) -- so
    a plain isinstance check silently misses every negative literal. That matters
    wherever a negative axis has to be normalised before it reaches a kernel that
    indexes with it.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _static_int(node.operand)
        if inner is not None:
            return -inner if isinstance(node.op, ast.USub) else inner
    return None


# ==== the ndarray operation surface -- ONE table behind BOTH spellings =====
# `a.prod()` and `np.prod(a)` are the same operation written two ways, so they
# resolve to the SAME handler here and cannot drift apart. Two if-chains (one in
# _call_method, one in _call_numpy) is how the gaps got in: np.take/np.cumsum
# were wired free-only, .copy() method-only.
#
# Each handler has the signature `handler(self, recv, args, node) -> Val`, where
# `recv` is the receiver for the method spelling and the FIRST ARGUMENT for the
# free spelling -- `a.sum(axis=0)` and `np.sum(a, axis=0)` therefore arrive
# identically. `spell` records which spellings numpy itself provides:
#
#   "both"   -- a.f(...)  and  np.f(a, ...)
#   "method" -- method only (numpy has no such free function: .flatten, .astype)
#   "free"   -- free only (np.amax, np.resize-as-repeat)
#
# A few names mean DIFFERENT things in the two spellings and so get separate
# entries rather than a shared one: np.sort copies where a.sort() mutates, and
# np.resize repeats where a.resize() zero-fills.
_ARRAY_OPS = {
    "all":          ("_op_all", "both"),
    "amax":         ("_op_max", "free"),
    "amin":         ("_op_min", "free"),
    "any":          ("_op_any", "both"),
    "argmax":       ("_op_argmax", "both"),
    "argmin":       ("_op_argmin", "both"),
    "argsort":      ("_op_argsort", "both"),
    "asNumpy":      ("_op_asnumpy", "method"),
    # ---- MatrixView methods (docs/notes/matrixview-lowering.md) --------
    # "method" only: numpy has no free spelling of any of these, and a matrix
    # input is the only thing that produces the MatrixView they live on.
    # `transpose` is deliberately absent -- the existing numpy handler already
    # does the right thing on a (4,4).
    "translation":  ("_op_mv_translation", "method"),
    "inverse":      ("_op_mv_inverse", "method"),
    "getElement":   ("_op_mv_get_element", "method"),
    "det3x3":       ("_op_mv_det3", "method"),
    "det4x4":       ("_op_mv_det4", "method"),
    "rotation":     ("_op_mv_rotation", "method"),
    "scale":        ("_op_mv_scale", "method"),
    "shear":        ("_op_mv_shear", "method"),
    "rotationOrder": ("_op_mv_rotation_order", "method"),
    "isSingular":   ("_op_mv_is_singular", "method"),
    "asRotateMatrix": ("_op_mv_as_rotate_matrix", "method"),
    "asScaleMatrix": ("_op_mv_as_scale_matrix", "method"),
    "asMatrixInverse": ("_op_mv_as_matrix_inverse", "method"),
    "adjoint":      ("_op_mv_adjoint", "method"),
    "homogenize":   ("_op_mv_homogenize", "method"),
    # numpy 1.x has no np.astype; numpy 2 added it. Wiring "both" costs nothing
    # and keeps the free spelling from becoming a gap on an upgrade.
    "astype":       ("_op_astype", "both"),
    "byteswap":     ("_op_byteswap", "method"),
    "choose":       ("_op_choose", "both"),
    "clip":         ("_op_clip", "both"),
    "conj":         ("_op_conj", "both"),
    "conjugate":    ("_op_conj", "both"),
    "copy":         ("_op_copy", "both"),
    "cumprod":      ("_op_cumprod", "both"),
    "cumsum":       ("_op_cumsum", "both"),
    "diagonal":     ("_op_diagonal", "both"),
    "dot":          ("_op_dot", "both"),
    "flatten":      ("_op_ravel", "method"),
    "item":         ("_op_item", "method"),
    "max":          ("_op_max", "both"),
    "mean":         ("_op_mean", "both"),
    "min":          ("_op_min", "both"),
    "nonzero":      ("_op_nonzero", "both"),
    "prod":         ("_op_prod", "both"),
    "ptp":          ("_op_ptp", "both"),
    "ravel":        ("_op_ravel", "both"),
    "repeat":       ("_op_repeat", "both"),
    "reshape":      ("_op_reshape", "both"),
    "resize":       ("_op_resize_repeat", "free"),
    "round":        ("_op_round", "both"),
    "searchsorted": ("_op_searchsorted", "both"),
    "sort":         ("_op_sort", "free"),
    "squeeze":      ("_op_squeeze", "both"),
    "std":          ("_op_std", "both"),
    "sum":          ("_op_sum", "both"),
    "swapaxes":     ("_op_swapaxes", "both"),
    "take":         ("_op_take", "both"),
    "tofile":       ("_op_tofile", "method"),
    "trace":        ("_op_trace", "both"),
    "transpose":    ("_op_transpose", "both"),
    "var":          ("_op_var", "both"),
}

# The one operation whose two spellings take their arguments in a DIFFERENT
# ORDER: np.compress(condition, a) leads with the mask, a.compress(condition)
# with the array. Looked up before _ARRAY_OPS, so the shared handler below still
# sees (cond, src) whichever way it was written.
_ARRAY_OPS_BY_SPELLING = {
    ("compress", "free"):   "_op_compress_free",
    ("compress", "method"): "_op_compress_method",
}

# Methods whose whole point is the SIDE EFFECT: they return None, so they appear
# as bare expression statements (`b.sort()`), not as expressions. Handled by
# _array_stmt_method, which is why they are not in _ARRAY_OPS.
#   name -> (handler, needs_lvalue)
# `needs_lvalue` marks the ones that REBIND the name (resize changes the shape)
# rather than mutating the existing buffer through a reference.
_ARRAY_STMT_OPS = {
    "fill":     ("_stmt_fill", False),
    "itemset":  ("_stmt_itemset", False),
    "put":      ("_stmt_put", False),
    "resize":   ("_stmt_resize", True),
    "setflags": ("_stmt_setflags", False),
    "sort":     ("_stmt_sort", False),
}

# The methods that CANNOT be lowered, each with the reason. Kept as data so both
# spellings give the identical message, and so the reasoning is reviewable
# instead of buried in an if-chain.
_ARRAY_OP_REJECTS = {
    "partition": "numpy leaves the order of every non-kth element unspecified, "
                 "so a C++ selection would disagree with the interpreted result "
                 "on the same input (this is a parity impossibility, not a gap)",
    "argpartition": "numpy leaves the order of every non-kth index unspecified, "
                    "so a C++ selection would disagree with the interpreted "
                    "result on the same input",
    "view": "a view ALIASES its base (v = a.view(); v[0] = 1 changes a), and the "
            "runtime has no aliasing view type -- returning a copy would "
            "silently drop the write-through",
    "newbyteorder": "it reinterprets the buffer in a NON-native byte order, and "
                    "the runtime has only native-order arrays, so the values "
                    "themselves would differ",
    "dump": "it pickles to a file; there is no Python object model in C++",
    "dumps": "it pickles to bytes; there is no Python object model in C++",
    "tobytes": "there is no bytes carrier, and its consumers (struct.unpack, "
               "slicing) are outside the subset -- use a.tofile(path)",
    "tostring": "there is no bytes carrier -- use a.tofile(path)",
    "getfield": "structured/record dtypes; the runtime dtype set is scalar-only",
    "setfield": "structured/record dtypes; the runtime dtype set is scalar-only",
    "tolist": "it returns a Python list, where + CONCATENATES and * REPEATS; "
              "lowering it to the array would silently turn "
              "a.tolist() + b.tolist() into elementwise addition",
}


class Transpiler:
    def __init__(self, env, return_handler=None, output_writers=None,
                 helper_ctx=None, state_vars=None, blessed=None,
                 blessed_unpack=None, side_effect_methods=None,
                 imports=None, import_stars=()):
        # env: name -> CppType for pre-bound values (args, self.<attr>).
        self.env = dict(env)
        # imports: {bound name -> canonical module origin} from the node's own
        # source, over the ambient defaults. Every module dispatch goes through
        # _canon so it keys off where a name CAME FROM, not how it is spelled.
        self.imports = dict(_AMBIENT_MODULES)
        self.imports.update(imports or {})
        self.import_stars = tuple(import_stars or ())
        # blessed: {method_name: callable(tp, call_node) -> Val} -- a blessed
        # `self.<name>(...)` used in EXPRESSION position (read_texture). The
        # callable MAY emit statement lines via tp.emit(...).
        self.blessed = dict(blessed or {})
        # blessed_unpack: {method_name: callable(tp, call_node) -> list[Val]} --
        # a blessed `a, b, ... = self.<name>(...)` in UNPACK position
        # (sample_texture). The callable emits its own statements and returns one
        # Val per target. Supplied by codegen, so py_to_cpp stays kernel-agnostic.
        self.blessed_unpack = dict(blessed_unpack or {})
        # side_effect_methods: names of blessed `NativeSideEffect` methods. A BARE
        # `self.<name>(...)` STATEMENT lowers to nothing -- these perform an
        # interactive-only plug side effect (e.g. writing the paint `weightList`
        # scratchpad) with NO numeric kernel. Statement context ONLY: used in
        # VALUE position it still fails (no Val), and a bare call to any OTHER
        # method still honest-rejects.
        self.side_effect_methods = set(side_effect_methods or [])
        self.return_handler = return_handler or self._default_return
        # output_writers: dotted-name ('self.<attr>') -> callable(Val)->list[str]
        # used by the compute-BLOCK path to lower `self.<out> = expr` writes.
        self.output_writers = dict(output_writers or {})
        self.written_outputs = set()
        # Persistent stateful self-vars: undeclared self.<name> ASSIGNED in the
        # compute/init that must SURVIVE between compute() calls (a latched rest
        # length, a simulation buffer, a solver carry-over). They map to per-node
        # members `st.<name>` in a state registry the caller emits, and
        # `hasattr(self,'<name>')` to `st.<name>_isset`. state_members is
        # discovered here (from the first assignment) so the caller can declare
        # the struct with the right member types.
        self.state_vars = set(state_vars or [])
        self.state_members = {}
        # helper_ctx: shared _HelperCtx for lowering inline INIT-tier `def`
        # helpers into C++ lambdas (None -> a bare-name call is unknown -> reject).
        self.helpers = helper_ctx
        # INIT-tier constants currently being folded, so `A = A + 1` at module
        # level cannot recurse forever (see _init_const).
        self._const_stack = []
        # Locals statically known to hold None (`x = None`, or a
        # `getattr(self, '<absent>', None)` that folds to its default). None has
        # no C++ value, so these bind no variable and only an `is None` /
        # `is not None` test can read them; any other use rejects.
        self._none_names = set()
        # arg names of the current function (helper path) -- declared in the
        # lambda signature, so they must be excluded from hoisted _decl_lines
        # even when reassigned in the body (else the decl would shadow the param).
        self._param_names = set()
        self.decls = {}          # name -> CppType (hoisted, first-seen order)
        self.body = []
        self.returns = []
        self.indent = 1
        self._tmp = 0
        # Set by any lowering that emits an nd_io call, so the caller knows the
        # generated body needs the nd_io kernel + its per-instance cache members.
        self.uses_ndio = False
        # Set when a MatrixView method that needs Maya semantics lowers.
        # The EMITTERS gate on the spec (nd_maya_cpp.spec_uses_maya_xform)
        # because includes are decided before lowering; this flag is the
        # transpiler-side record, used by tests to prove the two agree.
        self.uses_maya_xform = False
        # In the compute-BLOCK path the emitted C++ shares a scope with the node's
        # frame, which reserves names like `env`, `pts`, `n`, `iter`, `block`,
        # `adjStart`. A user local named the same (e.g. the canonical
        # `env = float(self.envelope)`) would clash, so every user local gets an
        # `nl_` prefix. Off for the helper path (`run`): its locals are scoped.
        self.prefix_locals = False

    # ---- emission helpers ---------------------------------------------------
    def emit(self, line):
        self.body.append("    " * self.indent + line)

    def _cpp_local(self, name):
        """C++ identifier for a user Python local. Prefixed in the block path so
        it can never collide with a codegen frame-reserved name."""
        return ("nl_" + name) if self.prefix_locals else name

    def _default_return(self, val):
        self.returns.append(val.type)
        return ["return %s;" % val.code]

    def fail(self, node, msg):
        ln = getattr(node, "lineno", "?")
        raise UnsupportedSpec("py_to_cpp: %s (line %s, node %s)"
                              % (msg, ln, type(node).__name__))

    # ---- public entry -------------------------------------------------------
    def run(self, func_def):
        arg_names = [a.arg for a in func_def.args.args]
        self._param_names = set(arg_names)
        # Seed decls with each param's declared type so a reassignment (e.g.
        # `h = max(1, int(h))`) type-checks against it. _decl_lines skips params,
        # so this never emits a shadowing declaration -- the param already lives
        # in the (caller-emitted) function/lambda signature.
        for nm in arg_names:
            if nm in self.env:
                self.decls[nm] = self.env[nm]
        for st in func_def.body:
            self.stmt(st)
        return TranspileResult(arg_names, self._decl_lines(), self.body,
                               self.returns)

    def run_block(self, stmts):
        """Transpile a bare statement block (the mpynode compute body).

        Reads bind to env entries ('self.<in>'); writes to declared outputs go
        through output_writers. Returns a TranspileResult (no arg_names)."""
        self.prefix_locals = True
        for st in stmts:
            self.stmt(st)
        return TranspileResult([], self._decl_lines(), self.body, self.returns)

    def _decl_lines(self):
        decl_lines = []
        for name, t in self.decls.items():
            if name in self._param_names:
                continue                      # declared in the signature
            cname = self._cpp_local(name)
            if t.kind == "rng":
                decl_lines.append("    nd::MT19937 %s;" % cname)
            elif t.kind == "kdtree":
                decl_lines.append("    nd::KDTree %s;" % cname)
            elif t.kind == "array":
                # Defensive, same argument as _promote: a non-numeric element
                # dtype (the 'str' carrier) has no _CTYPE entry, so declaring it
                # would KeyError-crash codegen instead of rejecting cleanly.
                # Unreachable today (_promote rejects 'str' first).
                if t.dtype not in _CTYPE:
                    raise UnsupportedSpec("py_to_cpp: local %r is an array of "
                                          "non-numeric dtype %r" % (name, t.dtype))
                decl_lines.append("    nd::Array<%s> %s;" % (_CTYPE[t.dtype], cname))
            elif t.kind == "str":
                decl_lines.append("    std::string %s;" % cname)
            elif t.kind == "strv":
                decl_lines.append("    std::vector<std::string> %s;" % cname)
            else:  # scalar
                decl_lines.append("    %s %s = 0;" % (_CTYPE[t.dtype], cname))
        return decl_lines

    # ==== statements =====================================================
    def stmt(self, node):
        m = getattr(self, "st_" + type(node).__name__, None)
        if m is None:
            self.fail(node, "unsupported statement")
        m(node)

    def _block(self, stmts):
        self.indent += 1
        for s in stmts:
            self.stmt(s)
        self.indent -= 1

    def st_Expr(self, node):
        # docstrings and bare literals are no-ops; bare calls are rejected...
        if isinstance(node.value, ast.Constant):
            return
        # ...EXCEPT a bare call to a blessed NativeSideEffect method, which lowers
        # to nothing (interactive-only plug side effect, no numeric kernel). The
        # arguments are NOT evaluated -- the call has no compiled meaning at all.
        v = node.value
        if (isinstance(v, ast.Call)
                and isinstance(v.func, ast.Attribute)
                and isinstance(v.func.value, ast.Name)
                and v.func.value.id == "self"
                and v.func.attr in self.side_effect_methods):
            return
        # ...and EXCEPT a file WRITE, whose whole point is the side effect. The
        # value (a success bool) is discarded, but the call itself must still be
        # emitted -- `(void)(...)` keeps it as a statement without an
        # unused-result warning.
        if isinstance(v, ast.Call) and self._is_io_stmt(v):
            self.emit("(void)(%s);" % self.expr(v).code)
            return
        # ...and EXCEPT a blessed `self.<name>(...)`, whose codegen-supplied
        # lowering does the work by emitting statements (e.g. a locator draw
        # emit). Its returned value has no use in statement position, so it is
        # dropped -- the emitted lines are the effect.
        if (isinstance(v, ast.Call)
                and isinstance(v.func, ast.Attribute)
                and isinstance(v.func.value, ast.Name)
                and v.func.value.id == "self"
                and v.func.attr in self.blessed):
            self.blessed[v.func.attr](self, v)
            return
        # ...and EXCEPT the ndarray methods whose whole point is the MUTATION.
        # `b.sort()` / `b.fill(0.0)` return None, so they only ever appear in
        # statement position -- see _ARRAY_STMT_OPS.
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                and v.func.attr in _ARRAY_STMT_OPS
                and self._canon(v.func) != "%s.put" % _CANON_NUMPY):
            self._array_stmt_method(v)
            return
        # ...and the FREE spelling of the same mutation: np.put(a, ind, vals).
        # It is the one in-place numpy free function in the surface, and it must
        # reach the same lowering as a.put(ind, vals).
        if isinstance(v, ast.Call) and self._canon(v.func) == "%s.put" % _CANON_NUMPY:
            fargs = self._pos_args(v)
            self._need(v, fargs, 3)
            if not isinstance(fargs[0], ast.Name) or fargs[0].id not in self.env:
                self.fail(v, "np.put mutates in place, so its target must be a "
                             "local array variable")
            self._stmt_put(self.expr(fargs[0]), fargs[1:], v)
            return
        # ...and the two other in-place numpy free functions (SP-7). Both return
        # None, so like np.put they can ONLY appear in statement position.
        if isinstance(v, ast.Call) and self._canon(v.func) == \
                "%s.fill_diagonal" % _CANON_NUMPY:
            self._stmt_fill_diagonal(v)
            return
        if isinstance(v, ast.Call) and self._canon(v.func) == \
                "%s.add.at" % _CANON_NUMPY:
            self._stmt_add_at(v)
            return
        self.fail(node, "bare expression statement has no supported effect")

    def _stmt_mutable_target(self, call, fargs, what):
        """The shared 'first arg must be a writable local array' check.

        np.put already had this inline; fill_diagonal and add.at need the exact
        same rule, so it lives in one place rather than being restated twice.
        """
        if not isinstance(fargs[0], ast.Name) or fargs[0].id not in self.env:
            self.fail(call, "%s mutates in place, so its target must be a local "
                            "array variable" % what)
        recv = self.expr(fargs[0])
        if not recv.type.is_array():
            self.fail(call, "%s on a non-array" % what)
        return recv

    def _stmt_fill_diagonal(self, call):
        fargs = self._pos_args(call)
        self._need(call, fargs, 2)
        if self._kw(call, "wrap") is not None:
            self.fail(call, "np.fill_diagonal(wrap=True) is not lowered")
        recv = self._stmt_mutable_target(call, fargs, "np.fill_diagonal")
        if recv.type.rank is not None and recv.type.rank < 2:
            self.fail(call, "np.fill_diagonal needs a 2-D (or higher) array")
        val = self._cast_scalar(self.expr(fargs[1]), recv.type.dtype)
        self.emit("nd::fill_diagonal(%s, (%s)(%s));"
                  % (recv.code, _CTYPE[recv.type.dtype], val))

    def _stmt_add_at(self, call):
        fargs = self._pos_args(call)
        self._need(call, fargs, 3)
        recv = self._stmt_mutable_target(call, fargs, "np.add.at")
        idx = self.expr(fargs[1])
        if not idx.type.is_array():
            self.fail(call, "np.add.at needs an index ARRAY")
        self.emit("nd::add_at(%s, %s, %s);"
                  % (recv.code, self._to_array_dtype(idx, "int64"),
                     self._to_array_dtype(self.expr(fargs[2]),
                                          recv.type.dtype)))

    def _array_stmt_method(self, call):
        """Lower an IN-PLACE ndarray method used as a statement.

        These mutate through the receiver, so the receiver has to be a name this
        function can write to -- an expression like `(a + b).sort()` sorts a
        temporary and is dead code in Python too.
        """
        name = call.func.attr
        handler, needs_lvalue = _ARRAY_STMT_OPS[name]
        target = call.func.value
        if not isinstance(target, ast.Name) or target.id not in self.env:
            self.fail(call, "a.%s(...) mutates in place, so its receiver must be "
                            "a local array variable" % name)
        recv = self.expr(target)
        if not recv.type.is_array():
            self.fail(call, "a.%s(...) on a non-array" % name)
        if needs_lvalue and not recv.code.isidentifier():
            self.fail(call, "a.%s(...) rebinds the name, so its receiver must be "
                            "a plain local variable" % name)
        getattr(self, handler)(recv, self._pos_args(call), call)

    def _stmt_sort(self, recv, args, node):
        # In-place, through the buffer: `c = a; a.sort()` must leave BOTH sorted,
        # which `a = nd::sort(a)` would not do (it rebinds only this name).
        axis = self._kw(node, "axis")
        if axis is None and args:
            axis = args[0]
        if axis is not None and isinstance(axis, ast.Constant) \
                and axis.value is None:
            self.fail(node, "a.sort(axis=None) is not an in-place sort in numpy "
                            "either; use a = np.sort(a, axis=None)")
        axc = "-1" if axis is None else self._int_arg(axis)
        self.emit("nd::sort_inplace(%s, %s);" % (recv.code, axc))

    def _stmt_fill(self, recv, args, node):
        self._need(node, args, 1)
        v = self.expr(args[0])
        self.emit("nd::fill_inplace(%s, (%s)(%s));"
                  % (recv.code, _CTYPE[recv.type.dtype],
                     self._cast_scalar(v, recv.type.dtype)))

    def _stmt_put(self, recv, args, node):
        self._need(node, args, 2)
        ind = self.expr(args[0])
        vals = self.expr(args[1])
        self.emit("nd::put_inplace(%s, %s, %s);"
                  % (recv.code, self._to_array_dtype(ind, "int64"),
                     self._to_array_dtype(vals, recv.type.dtype)))

    def _stmt_itemset(self, recv, args, node):
        # a.itemset(i, v) is a.flat[i] = v -- a one-element put.
        self._need(node, args, 2)
        if len(args) != 2:
            self.fail(node, "a.itemset(flat_index, value) is the only lowered form")
        ind = self.expr(args[0])
        vals = self.expr(args[1])
        self.emit("nd::put_inplace(%s, %s, %s);"
                  % (recv.code, self._to_array_dtype(ind, "int64"),
                     self._to_array_dtype(vals, recv.type.dtype)))

    def _stmt_resize(self, recv, args, node):
        # a.resize(n) ZERO-fills the tail (np.resize repeats instead). numpy
        # raises when anything else references the buffer, so a program that RUNS
        # has no aliases -- which makes rebinding the name exactly equivalent.
        shp = self._shape_from_args(args, node)
        self.emit("%s = nd::resize_zero(%s, %s);"
                  % (recv.code, recv.code, shp[0]))
        # resize can change the RANK, and the C++ type (nd::Array<T>) does not
        # carry it -- so the lattice entry has to be updated or later ops would
        # reason about the old shape.
        name = node.func.value.id
        if name in self.env:
            self.env[name].rank = shp[1]

    def _stmt_setflags(self, recv, args, node):
        # No observable effect on a compiled array: they are always writeable,
        # aligned and owned. A program that RUNS never writes through a
        # write=False array, so doing nothing is exact rather than approximate.
        pass

    def _is_io_stmt(self, call):
        """True for the file-write calls that are legal as bare statements."""
        canon = self._canon(call.func)
        if canon:
            if canon in ("%s.write" % _CANON_NDIO, "%s.write_raw" % _CANON_NDIO):
                return True
            if canon == "%s.save" % _CANON_NUMPY:
                return True
        return (isinstance(call.func, ast.Attribute)
                and call.func.attr == "tofile")

    def st_Pass(self, node):
        pass

    def st_Assert(self, node):
        # asserts are runtime checks with no output effect -> drop faithfully.
        pass

    def st_Import(self, node):
        # `import numpy as np` / `import math` etc. -> no-op. numpy (`np.`) and
        # math are handled specially in the expression visitor; any OTHER
        # imported name that is actually used lands in an unknown-call/name
        # failure downstream (-> UnsupportedSpec -> fallback), so dropping the
        # import here never lets an unsupported dependency through silently.
        pass

    def st_ImportFrom(self, node):
        # `from mpynode._api2.mpy_mesh import build_default_output` and similar
        # helper imports -> no-op (same safety argument as st_Import). The geo
        # bridge strips the build_default_output(...) call itself; any other
        # imported symbol used in a lowerable way fails downstream if unknown.
        pass

    def st_Return(self, node):
        if node.value is None:
            self.fail(node, "bare `return` (no value)")
        if isinstance(node.value, (ast.Tuple, ast.List)):
            # A tuple/list return would lower (via ex_Tuple) to `return <nd::Array>;`
            # -- valid as an assignment-RHS pack (``self.outColor = (r, g, b)``) but
            # NOT as a return: the compute() body returns MStatus and lowered
            # helpers return a single value, so this emits non-compiling C++.
            # Reject (-> AI porter), matching the behaviour before tuple packing
            # existed. Multi-value return is not modeled.
            self.fail(node, "tuple/list `return` (multi-value return not "
                            "supported; a tuple literal only lowers as an "
                            "assignment pack)")
        val = self.expr(node.value)
        # expose the source return node so a custom return_handler (the recursive
        # helper's return-type recorder) can classify base-case vs recursive
        # returns; harmless for the default/output-writer handlers.
        self._cur_ret_id = id(node)
        # Phase-2: fuse an elementwise return into a temp, then return it. Only
        # for the DEFAULT handler; the recursive return-type recorder only ever
        # sees scalar returns (non-fusable) and must observe the plain form.
        if self.return_handler == self._default_return:
            cpp = self._fuse_into_temp(val, node, "ret")
            if cpp is not None:
                self.returns.append(val.type)
                self.emit("return %s;" % cpp)
                return
        for line in self.return_handler(val):
            self.emit(line)

    def st_AnnAssign(self, node):
        if node.value is None:
            self.fail(node, "annotation without assignment")
        self._assign(node.target, node.value, node)

    def st_Assign(self, node):
        if len(node.targets) != 1:
            self.fail(node, "chained assignment `a = b = ...`")
        self._assign(node.targets[0], node.value, node)

    def st_AugAssign(self, node):
        # x op= y  ->  x = x op y  (desugar via a synthetic BinOp)
        binop = ast.BinOp(left=self._target_load(node.target), op=node.op,
                          right=node.value)
        ast.copy_location(binop, node)
        self._assign(node.target, binop, node)

    def _init_const(self, node):
        """An INIT-tier module constant, transpiled LAZILY at its first use.

        Returns None when the name is not a known constant, so the caller still
        raises its normal unknown-name error. Re-transpiled at EVERY use rather
        than bound once: the value is a pure literal expression, and emitting it
        in place is correct in any scope, where a cached binding declared inside
        a loop body would not be visible outside it."""
        ctx = self.helpers
        if ctx is None or node.id not in ctx.consts:
            return None
        if node.id in self._const_stack:
            self.fail(node, "init constant %r is defined in terms of itself"
                      % node.id)
        self._const_stack.append(node.id)
        try:
            return self.expr(ctx.consts[node.id])
        finally:
            self._const_stack.pop()

    def _reject_const_write(self, name, node, what):
        """An INIT-tier constant folds to an rvalue, so writing THROUGH it would
        either not compile or -- worse -- silently write into a temporary that
        is discarded at the end of the statement, while the interpreted node
        mutates the real module-level object and keeps it. Reject instead."""
        if (name not in self.env and self.helpers is not None
                and name in self.helpers.consts):
            self.fail(node, "%s the init-tab constant %r -- copy it into a "
                            "local first" % (what, name))

    def _target_load(self, target):
        """Build a load-expression AST mirroring an assignment target."""
        if isinstance(target, ast.Name):
            self._reject_const_write(target.id, target, "aug-assign to")
            return ast.copy_location(ast.Name(id=target.id, ctx=ast.Load()), target)
        if isinstance(target, ast.Subscript):
            return ast.copy_location(
                ast.Subscript(value=target.value, slice=target.slice,
                              ctx=ast.Load()), target)
        if isinstance(target, ast.Attribute):
            # self.<state> += x  ->  reads self.<state> (a persistent member);
            # only lowers if the attr is a readable state var, else ex_Attribute
            # rejects it and the caller falls back to the porter.
            return ast.copy_location(
                ast.Attribute(value=target.value, attr=target.attr,
                              ctx=ast.Load()), target)
        self.fail(target, "aug-assign target")

    def _is_none_expr(self, node):
        """True when this expression is statically None.

        Two spellings: the literal, and the `getattr(self, '<name>', None)`
        optional-input idiom whose DEFAULT is the branch _call_getattr folds to
        (the attribute is not declared on this node). A state var is excluded --
        its presence is a runtime fact, so its getattr lowers to a conditional
        that cannot have a None arm."""
        if isinstance(node, ast.Constant) and node.value is None:
            return True
        if not (isinstance(node, ast.Call) and len(node.args) == 3
                and not node.keywords
                and self._dotted(node.func) == "getattr"
                and "getattr" not in self.imports and "getattr" not in self.env
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "self"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and isinstance(node.args[2], ast.Constant)
                and node.args[2].value is None):
            return False
        nm = node.args[1].value
        return (nm not in self.state_vars
                and ("self." + nm) not in self.env
                and ("self." + nm) not in self.output_writers)

    def _assign(self, target, value_node, node):
        # tuple unpack from x.shape: `h, w = arr.shape`
        if isinstance(target, (ast.Tuple, ast.List)):
            return self._assign_unpack(target, value_node, node)
        if isinstance(target, ast.Subscript):
            return self._assign_subscript(target, value_node, node)
        # compute-block output write: `self.<out> = expr`
        if isinstance(target, ast.Attribute):
            return self._assign_output(target, value_node, node)
        if not isinstance(target, ast.Name):
            self.fail(node, "unsupported assignment target")
        name = target.id

        # RandomState construction -> declare an nd::MT19937 and seed it.
        rng_seed = self._as_randomstate(value_node)
        if rng_seed is not None:
            self._declare(name, CppType("rng"), node)
            self.emit(rng_seed % self._cpp_local(name))
            return

        # cKDTree construction -> build an nd::KDTree once, bound to this local.
        kd = self._as_kdtree(value_node)
        if kd is not None:
            self._declare(name, kdtree_t(), node)
            self.emit("%s = %s;" % (self._cpp_local(name), kd))
            return

        # `x = None` (directly, or via a getattr default that is selected):
        # bind the NAME as None without declaring anything. Rebinding a typed
        # local to None -- or a None local to a value -- would need one C++
        # variable to be two things, so both reject.
        if self._is_none_expr(value_node):
            if name in self.decls or name in self.env:
                self.fail(node, "variable %r reassigned to None; not supported"
                          % name)
            self._none_names.add(name)
            return
        if name in self._none_names:
            self.fail(node, "variable %r was bound to None and is reassigned to "
                            "a value; not supported" % name)

        val = self.expr(value_node)
        if val.type.kind in _OPAQUE_KINDS:
            # bind the pseudo-type in env without emitting a C++ variable
            # (texbuf: an opaque blessed read_texture() handle carrying .handle).
            self.env[name] = val.type
            return
        self._declare(name, val.type, node)
        cpp = self._cpp_local(name)
        # Phase-2 fusion: if the RHS is a fusable elementwise tree, emit ONE
        # runtime-guarded scalar loop (with the nested nd:: expression kept as a
        # fallback) instead of the allocating nd:: chain. Never changes results.
        if val.fuse is not None and self._emit_fused(cpp, val, node):
            return
        self.emit("%s = %s;" % (cpp, val.code))

    def _assign_output(self, target, value_node, node):
        dotted = self._dotted(target)
        # persistent stateful self-var write (self.<name> = expr): latch into the
        # per-node member `st.<name>` and flag it set. The member type is recorded
        # on the first write so the caller can declare the registry struct.
        if dotted is not None and dotted.startswith("self.") \
                and dotted[5:] in self.state_vars:
            nm = dotted[5:]
            # A LIST seed stays non-liftable even though a list literal now packs
            # to a rank-1 array in value position (ex_List). Persistent list state
            # means Python list semantics -- it grows (append) and concatenates
            # (+) -- and a fixed-size nd::Array would silently freeze the size and
            # turn `+` into an elementwise add. A TUPLE seed is unaffected: it has
            # always lowered here, and a tuple cannot grow.
            if isinstance(value_node, ast.List):
                self.fail(node, "persistent state %r cannot hold a list (a list "
                          "literal only packs a fixed-size vector in value "
                          "position)" % nm)
            val = self.expr(value_node)
            if val.type.dtype == "str":        # the str AND strv carriers
                self.fail(node, "persistent state %r cannot hold a string value "
                          "(not supported)" % nm)
            if val.type.kind in _VALUELESS_KINDS:
                self.fail(node, "persistent state %r cannot hold a %s pseudo-value"
                          % (nm, val.type.kind))
            prev = self.state_members.get(nm)
            if prev is None:
                self.state_members[nm] = val.type
            elif prev.kind != val.type.kind or prev.dtype != val.type.dtype:
                self.fail(node, "persistent state %r reassigned to a different "
                          "C++ type (%r -> %r)" % (nm, prev, val.type))
            elif prev.rank is None and val.type.rank is not None:
                self.state_members[nm].rank = val.type.rank
            self.emit("st.%s = %s;" % (nm, val.code))
            self.emit("st.%s_isset = true;" % nm)
            return
        if dotted is None or dotted not in self.output_writers:
            self.fail(node, "assignment to attribute %r that is not a declared "
                            "output" % dotted)
        val = self.expr(value_node)
        # Phase-2: fuse a direct `self.<out> = <elementwise tree>` into a temp,
        # then hand the writer a Val referencing it (writers only read `.code`).
        cpp = self._fuse_into_temp(val, node, "out")
        if cpp is not None:
            val = Val(cpp, val.type)
        for line in self.output_writers[dotted](val):
            self.emit(line)
        self.written_outputs.add(dotted)

    def _declare(self, name, typ, node):
        prev = self.decls.get(name)
        if prev is None:
            self.decls[name] = typ
            self.env[name] = typ
            return
        if prev.kind != typ.kind or prev.dtype != typ.dtype:
            self.fail(node, "variable %r reassigned to a different C++ type "
                            "(%r -> %r); not supported" % (name, prev, typ))
        # keep the widest known rank
        if prev.rank is None and typ.rank is not None:
            self.decls[name].rank = typ.rank
            self.env[name].rank = typ.rank

    def _assign_unpack(self, target, value_node, node):
        for elt in target.elts:
            if not isinstance(elt, ast.Name):
                self.fail(node, "tuple-unpack target must be plain names")
        # blessed `a, b, ... = self.<name>(...)` in unpack position -> the
        # codegen-supplied callable (e.g. sample_texture -> nd_tex_sample). It
        # emits its own statements and returns one Val per unpack target.
        if (isinstance(value_node, ast.Call)
                and isinstance(value_node.func, ast.Attribute)
                and isinstance(value_node.func.value, ast.Name)
                and value_node.func.value.id == "self"
                and self.blessed_unpack
                and value_node.func.attr in self.blessed_unpack):
            vals = self.blessed_unpack[value_node.func.attr](self, value_node)
            if len(vals) != len(target.elts):
                self.fail(node, "blessed %r returned %d values for %d targets"
                          % (value_node.func.attr, len(vals), len(target.elts)))
            for elt, val in zip(target.elts, vals):
                if not isinstance(elt, ast.Name):
                    self.fail(node, "blessed unpack target must be a plain name")
                self._declare(elt.id, val.type, node)
                self.emit("%s = %s;" % (self._cpp_local(elt.id), val.code))
            return
        # ys, xs = np.nonzero(arr)  -> per-axis int64 index arrays
        if self._is_nonzero_call(value_node):
            return self._assign_nonzero(target, value_node, node)
        # U, S, Vt = np.linalg.svd(a)  -> nd::SVD3 destructure (SP-6)
        if self._is_svd_call(value_node):
            return self._assign_svd(target, value_node, node)
        # X, Y = np.meshgrid(x, y)  -> two stretched grids (SP-7)
        if isinstance(value_node, ast.Call) and self._canon(value_node.func) \
                == "%s.meshgrid" % _CANON_NUMPY:
            return self._assign_meshgrid(target, value_node, node)
        # u, i = np.unique(a, return_index=True)  -> one stable sort, two arrays
        if isinstance(value_node, ast.Call) and self._canon(value_node.func) \
                == "%s.unique" % _CANON_NUMPY:
            return self._assign_unique(target, value_node, node)
        # d, i = tree.query(x[, k])  -> one nd::kd_query, two fields
        if self._is_kdtree_query(value_node, "query"):
            return self._assign_kdtree_query(target, value_node, node)
        # starts, items = tree.query_ball_point(x, r)  -> a CSR pair
        if self._is_kdtree_query(value_node, "query_ball_point"):
            return self._assign_kdtree_ball(target, value_node, node)
        # a, b, c = e1, e2, e3  -- bind EVERY right-hand side to a temp before
        # assigning any target, so a simultaneous assignment (`a, b = b, a`)
        # keeps Python's semantics instead of clobbering through.
        if isinstance(value_node, (ast.Tuple, ast.List)):
            if len(value_node.elts) != len(target.elts):
                self.fail(node, "tuple-unpack arity mismatch (%d target(s), "
                                "%d value(s))"
                          % (len(target.elts), len(value_node.elts)))
            tmps = []
            for elt_node in value_node.elts:
                v = self.expr(elt_node)
                if v.type.kind in _OPAQUE_KINDS:
                    self.fail(node, "tuple-unpack of a %s pseudo-value"
                              % v.type.kind)
                tmp = self._new_tmp("ndunp")
                self.emit("const auto %s = %s;" % (tmp, v.code))
                tmps.append(Val(tmp, v.type))
            for elt, v in zip(target.elts, tmps):
                self._declare(elt.id, v.type, node)
                self.emit("%s = %s;" % (self._cpp_local(elt.id), v.code))
            return
        val = self.expr(value_node)
        if val.type.kind != "shape":
            self.fail(node, "tuple unpacking only supported for `= x.shape`, "
                            "`= np.nonzero(arr)` or an explicit value tuple")
        for i, elt in enumerate(target.elts):
            self._declare(elt.id, scalar_t("int64"), node)
            self.emit("%s = (int64_t)%s[%d];"
                      % (self._cpp_local(elt.id), val.type.code, i))

    def _is_nonzero_call(self, node):
        """True for BOTH spellings: np.nonzero(a) and a.nonzero()."""
        if not isinstance(node, ast.Call):
            return False
        if self._canon(node.func) == "%s.nonzero" % _CANON_NUMPY:
            return True
        return (isinstance(node.func, ast.Attribute)
                and node.func.attr == "nonzero")

    def _new_tmp(self, prefix="ndtmp"):
        self._tmp += 1
        return "%s_%d" % (prefix, self._tmp)

    def _cse_bind(self, code):
        """Bind a NON-trivial operand to one ``const auto`` local so a caller that
        must name it 2-3x (the abs/min/max ternaries) evaluates it exactly once.
        Trivial operands (name / literal / cast / arithmetic -- no call) are
        returned unchanged: duplicating them is free and the C++ optimizer folds
        them. Byte-identical: the operand is a pure expression, so one evaluation
        yields the same value as three. The decl lands in the append-only body
        stream just before the enclosing statement (same as _assign_svd), so the
        temp is always in scope where the returned name is used."""
        if _is_trivial_operand(code):
            return code
        name = self._new_tmp("cse")
        self.emit("const auto %s = %s;" % (name, code))
        return name

    def _assign_nonzero(self, target, call, node):
        args = self._pos_args(call)
        if self._canon(call.func) == "%s.nonzero" % _CANON_NUMPY:
            self._need(call, args, 1)
            src = self.expr(args[0])
        else:                                # a.nonzero() -- the method spelling
            if args:
                self.fail(node, "a.nonzero() takes no arguments")
            src = self.expr(call.func.value)
        if not src.type.is_array():
            self.fail(node, "np.nonzero of a non-array")
        if src.type.rank is None:
            self.fail(node, "np.nonzero needs a statically known rank")
        if len(target.elts) != src.type.rank:
            self.fail(node, "np.nonzero unpack count (%d) != array ndim (%d)"
                      % (len(target.elts), src.type.rank))
        tmp = self._new_tmp("nz")
        self.emit("std::vector<nd::Array<int64_t>> %s = nd::nonzero(%s);"
                  % (tmp, src.code))
        for i, elt in enumerate(target.elts):
            self._declare(elt.id, array_t("int64", 1), node)
            self.emit("%s = %s[%d];" % (self._cpp_local(elt.id), tmp, i))

    def _assign_meshgrid(self, target, call, node):
        """X, Y[, Z] = np.meshgrid(x, y[, z], indexing='xy'|'ij').

        'ij' is not 'xy' with the axes renamed -- it TRANSPOSES the leading two
        axes of every output -- so each indexing gets its own explicit mapping
        rather than a shared one with a flag. For two inputs that mapping is
        exactly "swap the arguments and swap which grid you ask for", so it
        reuses the existing meshgrid_x/meshgrid_y with no new runtime. Three
        inputs need a rank-3 builder (nd::meshgrid3), which takes the output
        shape and the source axis per output, so both indexings are one call.
        """
        args = self._pos_args(call)
        if len(args) not in (2, 3):
            self.fail(node, "np.meshgrid lowers the 2- and 3-input forms only")
        if len(target.elts) != len(args):
            self.fail(node, "np.meshgrid unpacks to exactly one grid per input "
                            "(%d input(s), %d target(s))"
                      % (len(args), len(target.elts)))
        idx = self._kw(call, "indexing")
        if idx is not None and not (isinstance(idx, ast.Constant)
                                    and idx.value in ("xy", "ij")):
            self.fail(node, "np.meshgrid(indexing=...) must be the literal "
                            "'xy' or 'ij'")
        ij = idx is not None and idx.value == "ij"
        if self._kw(call, "sparse") is not None:
            self.fail(node, "np.meshgrid(sparse=True) is not lowered")
        vals = [self.expr(a) for a in args]
        for v in vals:
            if not v.type.is_array():
                self.fail(node, "np.meshgrid needs 1-D arrays")
            if v.type.rank is not None and v.type.rank != 1:
                self.fail(node, "np.meshgrid needs 1-D arrays")
        dt = vals[0].type.dtype
        for v in vals[1:]:
            dt = _promote(dt, v.type.dtype)
        cs = [self._cse_bind(self._to_array_dtype(v, dt)) for v in vals]
        if len(cs) == 2:
            rank = 2
            if ij:
                calls = ["nd::meshgrid_y(%s, %s)" % (cs[1], cs[0]),
                         "nd::meshgrid_x(%s, %s)" % (cs[1], cs[0])]
            else:
                calls = ["nd::meshgrid_x(%s, %s)" % (cs[0], cs[1]),
                         "nd::meshgrid_y(%s, %s)" % (cs[0], cs[1])]
        else:
            rank = 3
            n = ["(%s).size()" % c for c in cs]
            # 'xy' swaps the FIRST TWO axes only; the third is untouched.
            dims = (n[0], n[1], n[2]) if ij else (n[1], n[0], n[2])
            axes = (0, 1, 2) if ij else (1, 0, 2)
            calls = ["nd::meshgrid3(%s, %d, %s, %s, %s)"
                     % (cs[i], axes[i], dims[0], dims[1], dims[2])
                     for i in range(3)]
        for elt, cexpr in zip(target.elts, calls):
            self._declare(elt.id, array_t(dt, rank), node)
            self.emit("%s = %s;" % (self._cpp_local(elt.id), cexpr))

    def _assign_unique(self, target, call, node):
        """u, i = np.unique(a, return_index=True).

        The index contract is the whole reason this is separate from the plain
        np.unique lowering: numpy reports the FIRST occurrence of each value in
        the original (flattened) order, which nd::unique_index reproduces with a
        stable sort. The other return_* flags each need their own array and are
        still rejected."""
        args = self._pos_args(call)
        self._need(call, args, 1)
        for bad in ("return_inverse", "return_counts", "axis"):
            if self._kw(call, bad) is not None:
                self.fail(node, "np.unique(%s=...) is not lowered" % bad)
        ri = self._kw(call, "return_index")
        if not (isinstance(ri, ast.Constant) and ri.value is True):
            self.fail(node, "np.unique unpacks only with a literal "
                            "return_index=True")
        if len(target.elts) != 2:
            self.fail(node, "np.unique(return_index=True) unpacks to exactly "
                            "values, indices")
        a = self.expr(args[0])
        if not a.type.is_array():
            self.fail(node, "np.unique of a non-array")
        tmp = self._new_tmp("uq")
        self.emit("auto %s = nd::unique_index(%s);" % (tmp, a.code))
        vt, it = target.elts
        self._declare(vt.id, array_t(a.type.dtype, 1), node)
        self.emit("%s = %s.first;" % (self._cpp_local(vt.id), tmp))
        self._declare(it.id, array_t("int64", 1), node)
        self.emit("%s = %s.second;" % (self._cpp_local(it.id), tmp))

    def _is_svd_call(self, node):
        return (isinstance(node, ast.Call)
                and self._canon(node.func) == "%s.linalg.svd" % _CANON_NUMPY)

    def _assign_svd(self, target, call, node):
        args = self._pos_args(call)
        self._need(call, args, 1)
        if self._kw(call, "full_matrices") is not None:
            self.fail(node, "np.linalg.svd(full_matrices=...) not supported "
                            "(only the default full_matrices=True for 3x3)")
        src = self.expr(args[0])
        if (not src.type.is_array() or src.type.rank is None
                or src.type.rank < 2):
            self.fail(node, "np.linalg.svd needs a (...,3,3) array")
        if len(target.elts) != 3:
            self.fail(node, "np.linalg.svd unpack needs exactly U, S, Vt")
        tmp = self._new_tmp("svd")
        self.emit("nd::SVD3 %s = nd::svd(%s);"
                  % (tmp, self._to_array_dtype(src, "double")))
        u, s, vt = target.elts
        self._declare(u.id, array_t("double", src.type.rank), node)
        self.emit("%s = %s.U;" % (self._cpp_local(u.id), tmp))
        self._declare(s.id, array_t("double", src.type.rank - 1), node)
        self.emit("%s = %s.S;" % (self._cpp_local(s.id), tmp))
        self._declare(vt.id, array_t("double", src.type.rank), node)
        self.emit("%s = %s.Vt;" % (self._cpp_local(vt.id), tmp))

    def _assign_subscript(self, target, value_node, node):
        if isinstance(target.value, ast.Name):
            self._reject_const_write(target.value.id, node, "cannot write into")
        base = self.expr(target.value)
        if not base.type.is_array():
            self.fail(node, "slice-assign target is not an array")
        rhs = self.expr(value_node)
        dt = base.type.dtype
        # Raw ref-write fast path: a FULL all-integer index into a plain array
        # local yields an lvalue element -- write straight through nd::atN_ref
        # (no per-access view allocation), bit-identical to nd::assign on the
        # scalar view. Restricted to a Name base so the reference points into
        # the real buffer, not a temporary. See ex_Subscript / nd_runtime.h.
        idxs = self._all_integer_index_exprs(target, base.type)
        if (idxs is not None and isinstance(target.value, ast.Name)
                and (rhs.type.is_scalar()
                     or (rhs.type.is_array() and rhs.type.rank in (0, None)))):
            ref = "nd::at%d_ref(%s, %s)" % (len(idxs), base.code,
                                            ", ".join(idxs))
            self.emit("%s = %s;" % (ref, self._cast_scalar(rhs, dt)))
            return
        specs, _rank, newaxis_pos = self._build_slice(target, base.type)
        if newaxis_pos:
            self.fail(node, "newaxis on a slice-assign target")
        view = "nd::slice(%s, {%s})" % (base.code, ", ".join(specs))
        if rhs.type.is_scalar():
            self.emit("nd::assign(%s, (%s)(%s));"
                      % (view, _CTYPE[dt], rhs.code))
        elif rhs.type.is_array():
            self.emit("nd::assign(%s, %s);"
                      % (view, self._to_array_dtype(rhs, dt)))
        else:
            self.fail(node, "slice-assign rhs must be scalar or array")

    def st_For(self, node):
        if node.orelse:
            self.fail(node, "for/else")
        if not (isinstance(node.iter, ast.Call)
                and self._dotted(node.iter.func) == "range"):
            self.fail(node, "only `for i in range(...)` is supported")
        if not isinstance(node.target, ast.Name):
            self.fail(node, "for-loop target must be a plain name")
        args = node.iter.args
        if node.iter.keywords or not (1 <= len(args) <= 3):
            self.fail(node, "range() takes 1-3 positional args")
        if len(args) == 1:
            start, stop, step = self._scalar_int("0"), self._int_arg(args[0]), None
        elif len(args) == 2:
            start, stop, step = self._int_arg(args[0]), self._int_arg(args[1]), None
        else:
            start, stop, step = (self._int_arg(args[0]), self._int_arg(args[1]),
                                 args[2])
        var = node.target.id
        self._declare(var, scalar_t("int64"), node)
        cvar = self._cpp_local(var)
        if step is None:
            self.emit("for (%s = %s; %s < %s; ++%s) {"
                      % (cvar, start, cvar, stop, cvar))
        else:
            if not (isinstance(step, ast.Constant) and isinstance(step.value, int)):
                self.fail(node, "range() step must be an integer literal")
            sv = step.value
            if sv == 0:
                self.fail(node, "range() step == 0")
            cmp = "<" if sv > 0 else ">"
            self.emit("for (%s = %s; %s %s %s; %s += %d) {"
                      % (cvar, start, cvar, cmp, stop, cvar, sv))
        self._block(node.body)
        self.emit("}")

    def _int_arg(self, node):
        v = self.expr(node)
        return self._scalar_int_of(v, node)

    def _scalar_int(self, lit):
        return lit

    def st_While(self, node):
        if node.orelse:
            self.fail(node, "while/else")
        cond = self._as_bool(self.expr(node.test), node)
        self.emit("while (%s) {" % cond)
        self._block(node.body)
        self.emit("}")

    def st_If(self, node):
        cond = self._as_bool(self.expr(node.test), node)
        self.emit("if (%s) {" % cond)
        self._block(node.body)
        if node.orelse:
            self.emit("} else {")
            self._block(node.orelse)
        self.emit("}")

    def st_Break(self, node):
        self.emit("break;")

    def st_Continue(self, node):
        self.emit("continue;")

    def st_Raise(self, node):
        """`raise <Exception>('<literal>')` -> the runtime's OWN error channel.

        A compiled compute has no Python exception, but it does already have one
        way to abandon a malformed evaluation: nd_runtime throws
        std::runtime_error for every bad shape/index it meets, and that throw is
        what a compiled node already does today. Lowering a guard raise to the
        same throw keeps both sides doing the same thing -- stop, write no
        output -- instead of inventing a value numpy never produced.

        Only the literal-message form lowers. A computed message (an f-string, a
        formatted value) or a bare re-raise has no compiled form and rejects, so
        the node routes to the porter rather than losing the diagnostic."""
        if node.cause is not None:
            self.fail(node, "`raise ... from ...` is not lowered")
        exc = node.exc
        if exc is None:
            self.fail(node, "bare `raise` (re-raise) has no compiled form")
        exc_name, exc_args = None, []
        if isinstance(exc, ast.Name):
            exc_name = exc.id
        elif (isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name)
                and not exc.keywords):
            exc_name, exc_args = exc.func.id, list(exc.args)
        # An exception class is never a lowered VALUE, so a name that is one
        # (`raise a`, with `a` an input) is not the guard idiom at all.
        if (exc_name is None or exc_name in self.env
                or exc_name in self._none_names
                or (self.helpers is not None and exc_name in self.helpers.consts)):
            self.fail(node, "only `raise <Exception>('<literal message>')` is "
                            "lowered")
        if len(exc_args) > 1:
            self.fail(node, "raise with more than one argument is not lowered")
        msg = exc_name
        if exc_args:
            a = exc_args[0]
            if not (isinstance(a, ast.Constant) and isinstance(a.value, str)):
                self.fail(node, "raise message must be a literal string (a "
                                "formatted message has no compiled form)")
            msg = "%s: %s" % (exc_name, a.value)
        self.emit("throw std::runtime_error(%s);" % self._cpp_str_lit(msg, node))

    # ==== expressions -> Val =============================================
    def expr(self, node):
        m = getattr(self, "ex_" + type(node).__name__, None)
        if m is None:
            self.fail(node, "unsupported expression")
        return m(node)

    def ex_Constant(self, node):
        v = node.value
        if isinstance(v, bool):
            return Val("true" if v else "false", scalar_t("bool"))
        if isinstance(v, int):
            return Val("(int64_t)%d" % v, scalar_t("int64"))
        if isinstance(v, float):
            return Val(self._float_lit(v), scalar_t("double"))
        if isinstance(v, str):
            return Val("std::string(%s)" % self._cpp_str_lit(v, node), str_t())
        self.fail(node, "unsupported constant %r" % (v,))

    def _cpp_str_lit(self, s, node):
        # A C++ double-quoted literal for a Python str. Only printable-ASCII (plus
        # the common escapes) is lowered deterministically; any control/non-ASCII
        # char rejects (-> the whole node ports) so no ambiguous \\x escape can
        # silently corrupt the compiled string.
        out = ['"']
        for ch in s:
            o = ord(ch)
            if ch == "\\":
                out.append("\\\\")
            elif ch == '"':
                out.append('\\"')
            elif ch == "\n":
                out.append("\\n")
            elif ch == "\t":
                out.append("\\t")
            elif ch == "\r":
                out.append("\\r")
            elif 32 <= o < 127:
                out.append(ch)
            else:
                self.fail(node, "string literal with non-ASCII/control character "
                                "(deterministic lowering supports printable ASCII)")
        out.append('"')
        return "".join(out)

    def _float_lit(self, v):
        import math as _m
        if _m.isinf(v):
            return "(-INFINITY)" if v < 0 else "INFINITY"
        if _m.isnan(v):
            return "NAN"
        r = repr(v)
        if ("." not in r) and ("e" not in r) and ("E" not in r):
            r += ".0"
        return "(%s)" % r

    def ex_Tuple(self, node):
        return self._sequence_literal(node)

    def ex_List(self, node):
        return self._sequence_literal(node)

    def _sequence_literal(self, node):
        """A tuple/list literal of SCALAR elements -> a rank-1 nd::Array (PACK a
        small vector, e.g. ``self.outColor = (r, g, b)`` or ``[r, g, b]``).
        Elements are dtype-promoted like numpy; the consuming output writer
        (color -> set3Float, vector -> set3Double) casts to its Maya element
        type. Nested / array / empty literals reject."""
        elts = node.elts
        if not elts:
            self.fail(node, "empty tuple/list literal")
        vals = [self.expr(e) for e in elts]
        dt = "bool"
        for v in vals:
            if v.type.kind in _OPAQUE_KINDS:
                self.fail(node, "tuple/list element is a %s pseudo-value"
                          % v.type.kind)
            if v.type.is_array() and v.type.rank not in (0, None):
                self.fail(node, "nested/array element in a tuple/list literal "
                                "(use np.array / np.stack)")
            dt = _promote(dt, v.type.dtype)
        items = ", ".join(self._cast_scalar(v, dt) for v in vals)
        return Val("nd::from_data<%s>({%s}, {%d})"
                   % (_CTYPE[dt], items, len(vals)), array_t(dt, 1))

    def ex_Name(self, node):
        if node.id in self._none_names:
            self.fail(node, "local %r holds None, which has no compiled value; "
                            "only `is None` / `is not None` can read it"
                      % node.id)
        t = self.env.get(node.id)
        if t is None:
            # `from math import pi` binds pi as a BARE name; resolve it to the
            # same constant `math.pi` lowers to.
            konst = self._named_constant(self._canon(node))
            if konst is not None:
                return konst
            folded = self._init_const(node)
            if folded is not None:
                return folded
            self.fail(node, "name %r used before assignment / not an input"
                      % node.id)
        if t.kind == "texbuf":
            # A blessed read_texture() handle bound to a name may ONLY be passed
            # as sample_texture()'s first arg (which reads it from env directly).
            # Any other reuse (arithmetic, condition, np.*) would lower to a stray
            # pointer / an undeclared identifier -> reject (parity-or-reject).
            self.fail(node, "texture handle %r from read_texture() may only be "
                            "passed to sample_texture()" % node.id)
        return Val(self._cpp_local(node.id), t)

    def ex_UnaryOp(self, node):
        if isinstance(node.op, ast.UAdd):
            return self.expr(node.operand)
        if isinstance(node.op, ast.USub):
            v = self.expr(node.operand)
            if v.type.is_scalar():
                return Val("(-(%s))" % v.code, v.type)
            if v.type.is_array():
                r = Val("nd::negate(%s)" % v.code, v.type)
                fv = self._fuse_operand(v)
                if fv is not None and v.type.dtype != "bool" \
                        and v.type.rank is not None:
                    r.fuse = FuseNode(
                        "op",
                        emit=lambda vs: Val("(-(%s))" % vs[0].code,
                                            scalar_t(vs[0].type.dtype)),
                        children=[fv])
                return r
            self.fail(node, "negate of non-numeric")
        if isinstance(node.op, ast.Not):
            v = self._as_bool(self.expr(node.operand), node)
            return Val("(!(%s))" % v, scalar_t("bool"))
        if isinstance(node.op, ast.Invert):
            v = self.expr(node.operand)
            if v.type.kind in ("shape", "rng", "kdtree", "str", "strv") \
                    or v.type.dtype == "double":
                self.fail(node, "~ requires an integral/bool operand")
            if v.type.is_array():
                return Val("nd::invert(%s)" % v.code, v.type)
            if v.type.dtype == "bool":   # ~bool scalar == logical not (numpy)
                return Val("(!(%s))" % v.code, scalar_t("bool"))
            return Val("(~(%s))" % v.code, v.type)
        self.fail(node, "unary operator")

    def ex_BoolOp(self, node):
        op = "&&" if isinstance(node.op, ast.And) else "||"
        parts = [self._as_bool(self.expr(v), node) for v in node.values]
        return Val("(" + (" %s " % op).join(parts) + ")", scalar_t("bool"))

    _CMP_MAP = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=",
                ast.Eq: "==", ast.NotEq: "!="}
    _CMP_FN = {ast.Lt: "cmp_lt", ast.LtE: "cmp_le", ast.Gt: "cmp_gt",
               ast.GtE: "cmp_ge", ast.Eq: "cmp_eq", ast.NotEq: "cmp_ne"}

    def ex_Compare(self, node):
        if len(node.ops) != len(node.comparators):
            self.fail(node, "malformed compare")
        folded = self._compare_to_none(node)
        if folded is not None:
            return folded
        operands = [self.expr(node.left)] + [self.expr(c) for c in node.comparators]
        for op in node.ops:
            if type(op) not in self._CMP_MAP:
                self.fail(node, "comparison operator %s" % type(op).__name__)
        # string equality: a single == / != between two std::string carriers ->
        # bool. Ordered (< <= > >=) and chained/mixed string comparisons reject.
        if any(o.type.dtype == "str" for o in operands):
            if (len(node.ops) != 1
                    or not all(o.type.kind == "str" for o in operands)):
                self.fail(node, "string comparison must be a single == / != "
                                "between two strings")
            if type(node.ops[0]) not in (ast.Eq, ast.NotEq):
                self.fail(node, "strings support only == and != comparison")
            op = "==" if isinstance(node.ops[0], ast.Eq) else "!="
            return Val("(%s %s %s)" % (operands[0].code, op, operands[1].code),
                       scalar_t("bool"))
        if any(o.type.is_array() for o in operands):
            # numpy forbids chained comparison of arrays (ambiguous truth value).
            if len(node.ops) != 1:
                self.fail(node, "chained comparison involving arrays")
            l, r = operands[0], operands[1]
            if l.type.kind in _VALUELESS_KINDS or r.type.kind in _VALUELESS_KINDS:
                self.fail(node, "comparison on shape/rng object")
            dt = _promote(l.type.dtype, r.type.dtype)
            rank = self._binop_rank(l, r)
            return self._cmp_array(self._CMP_FN[type(node.ops[0])], l, r, dt, rank)
        # all-scalar: fold into a single boolean && chain.
        terms = []
        for op, cur, rhs in zip(node.ops, operands[:-1], operands[1:]):
            dt = _promote(cur.type.dtype, rhs.type.dtype)
            terms.append("(%s %s %s)"
                         % (self._cast_scalar(cur, dt), self._CMP_MAP[type(op)],
                            self._cast_scalar(rhs, dt)))
        return Val("(" + " && ".join(terms) + ")", scalar_t("bool"))

    def _compare_to_none(self, node):
        """Fold `x is None` / `x is not None` to a compile-time bool, or None.

        None is not representable in the lowered type system, so a value that
        transpiles at all can never BE None at runtime and a value bound by
        `x = None` always is: the test is decided here, not emitted. `== None`
        is deliberately left alone -- it is an equality, not an identity test.
        The other operand is still evaluated, exactly as Python evaluates it."""
        if len(node.ops) != 1 or type(node.ops[0]) not in (ast.Is, ast.IsNot):
            return None
        left, right = node.left, node.comparators[0]
        other = None
        if isinstance(right, ast.Constant) and right.value is None:
            other = left
        elif isinstance(left, ast.Constant) and left.value is None:
            other = right
        if other is None:
            return None
        if isinstance(other, ast.Name) and other.id in self._none_names:
            is_none = True
        else:
            is_none = self._is_none_expr(other)
            if not is_none:
                self.expr(other)
        same = isinstance(node.ops[0], ast.Is)
        return Val("true" if (is_none == same) else "false", scalar_t("bool"))

    def _cmp_array(self, fn, l, r, dt, rank):
        """Emit a broadcasting array comparison -> Array<bool>."""
        if l.type.is_array() and r.type.is_array():
            return Val("nd::%s(%s, %s)" % (fn, self._to_array_dtype(l, dt),
                                           self._to_array_dtype(r, dt)),
                       array_t("bool", rank))
        if l.type.is_array():
            return Val("nd::%s(%s, (%s)(%s))"
                       % (fn, self._to_array_dtype(l, dt), _CTYPE[dt],
                          self._cast_scalar(r, dt)), array_t("bool", rank))
        return Val("nd::%s((%s)(%s), %s)"
                   % (fn, _CTYPE[dt], self._cast_scalar(l, dt),
                      self._to_array_dtype(r, dt)), array_t("bool", rank))

    def ex_IfExp(self, node):
        # _as_bool rejects an array test, so `cond` is always a C++ scalar bool
        # and a plain ternary SELECTS one branch -- it never needs np.where's
        # elementwise blend.
        cond = self._as_bool(self.expr(node.test), node)
        a = self.expr(node.body)
        b = self.expr(node.orelse)
        if a.type.kind == "str" and b.type.kind == "str":
            # Both branches are std::string, so the ternary is well-typed and
            # selects one whole string -- no promotion involved.
            return Val("(%s ? %s : %s)" % (cond, a.code, b.code), str_t())
        if a.type.is_array() and b.type.is_array():
            # Same-rank arrays share one static C++ type (nd::Array<T>), so the
            # ternary is well-typed and the lattice rank stays exact. Differing
            # ranks have no single lattice entry -- numpy returns the branch
            # object unchanged rather than broadcasting -- so they still reject.
            if a.type.rank != b.type.rank:
                self.fail(node, "conditional expression mixes array ranks "
                                "(%s vs %s)" % (a.type.rank, b.type.rank))
            dt = _promote(a.type.dtype, b.type.dtype)
            return Val("(%s ? %s : %s)"
                       % (cond, self._to_array_dtype(a, dt),
                          self._to_array_dtype(b, dt)),
                       array_t(dt, a.type.rank))
        if not (a.type.is_scalar() and b.type.is_scalar()):
            self.fail(node, "conditional expression on arrays (use np.where)")
        dt = _promote(a.type.dtype, b.type.dtype)
        return Val("(%s ? %s : %s)"
                   % (cond, self._cast_scalar(a, dt), self._cast_scalar(b, dt)),
                   scalar_t(dt))

    _BINOP = {
        ast.Add: "Add", ast.Sub: "Sub", ast.Mult: "Mul", ast.Div: "Div",
        ast.FloorDiv: "FloorDiv", ast.Mod: "Mod", ast.Pow: "Pow",
    }

    @staticmethod
    def _is_int_literal(node, val):
        # True only for a plain int literal equal to val. `type(...) is int`
        # excludes bool (a subclass of int) and float, so 2.0 / True never match.
        return (isinstance(node, ast.Constant)
                and type(node.value) is int and node.value == val)
    # bitwise operators (integral / bool operands only, like numpy)
    _BITOP = {ast.BitAnd: ("and", "&"), ast.BitOr: ("or", "|"),
              ast.BitXor: ("xor", "^")}

    def ex_BinOp(self, node):
        if isinstance(node.op, ast.MatMult):
            return self._matmul(self.expr(node.left), self.expr(node.right), node)
        if type(node.op) in self._BITOP:
            return self._bitop(node)
        kind = self._BINOP.get(type(node.op))
        if kind is None:
            self.fail(node, "binary operator %s" % type(node.op).__name__)
        # QW1: x ** 2 with an integer-literal exponent lowers to a multiply.
        # numpy's ** operator special-cases squaring as an element-wise x*x
        # (byte-exact), whereas nd::power / apply_binop<..>(Pow) call libm pow
        # (~1 ULP off numpy, and slower). Restricted to a Name/Constant base so
        # the operand is safe to reference twice without re-evaluating a
        # side-effecting or expensive subexpression. np.power is untouched (only
        # the ** operator special-cases squaring in numpy).
        if kind == "Pow" and self._is_int_literal(node.right, 2) \
                and isinstance(node.left, (ast.Name, ast.Constant)):
            b = self.expr(node.left)
            # INVERTED sense: everything not listed takes the fast path, so a
            # kind missing here fails OPEN into _array_binop rather than
            # rejecting. _NON_NUMERIC_KINDS is the same set plus 'kdtree'.
            if b.type.kind not in _NON_NUMERIC_KINDS:
                if b.type.is_scalar():
                    return self._scalar_binop("Mul", b, b)
                return self._array_binop("Mul", b, b, node)
        l = self.expr(node.left)
        r = self.expr(node.right)
        # string concatenation: str + str -> str. Any other operator, or a mix of
        # a string with a non-string operand, rejects (-> the porter).
        if l.type.dtype == "str" or r.type.dtype == "str":
            if (kind == "Add" and l.type.kind == "str"
                    and r.type.kind == "str"):
                return Val("(%s + %s)" % (l.code, r.code), str_t())
            self.fail(node, "string operand supports only + (concatenation) "
                            "with another string")
        if l.type.kind in _VALUELESS_KINDS or r.type.kind in _VALUELESS_KINDS:
            self.fail(node, "arithmetic on shape/rng object")
        if l.type.is_scalar() and r.type.is_scalar():
            return self._scalar_binop(kind, l, r)
        return self._array_binop(kind, l, r, node)

    # ---- scalar arithmetic --------------------------------------------------
    def _scalar_binop(self, kind, l, r):
        if kind == "Div":
            return Val("(((double)(%s)) / ((double)(%s)))" % (l.code, r.code),
                       scalar_t("double"))
        if kind in ("Add", "Sub", "Mul"):
            dt = _promote(l.type.dtype, r.type.dtype)
            op = {"Add": "+", "Sub": "-", "Mul": "*"}[kind]
            return Val("(%s %s %s)"
                       % (self._cast_scalar(l, dt), op, self._cast_scalar(r, dt)),
                       scalar_t(dt))
        if kind in ("FloorDiv", "Mod"):
            dt = _promote(l.type.dtype, r.type.dtype)
            return Val("nd::apply_binop<%s>(nd::BinOp::%s, %s, %s)"
                       % (_CTYPE[dt], kind, self._cast_scalar(l, dt),
                          self._cast_scalar(r, dt)), scalar_t(dt))
        if kind == "Pow":
            dt = "double" if "double" in (l.type.dtype, r.type.dtype) else "int64"
            return Val("nd::apply_binop<%s>(nd::BinOp::Pow, %s, %s)"
                       % (_CTYPE[dt], self._cast_scalar(l, dt),
                          self._cast_scalar(r, dt)), scalar_t(dt))
        self.fail_generic("scalar binop %s" % kind)

    def _scalar_maxmin(self, kind, l, r):
        # Byte-exact match to nd:: binary Max/Min by CONSTRUCTION: call the SAME
        # nd::maximum_elem/minimum_elem the nd:: side uses (nd_runtime.h -- one
        # definition shared by apply_binop, binary() and the reduce() fast path).
        # Those are NaN-ASYMMETRIC, `(a > b || isnan(a)) ? a : b`, so a bare
        # `a > b ? a : b` here drops a NaN LEFT operand and makes this fast path
        # disagree with its own nd:: fallback arm for the same expression. They
        # are inline templates that fold back to that ternary (to a bare one for
        # integral T), so the loop body compiles the same with each operand named
        # ONCE rather than twice -- which also stops nesting (np.clip is Min then
        # Max) from squaring the operand text. No outer cast: the helper returns
        # the selected operand at the promoted dtype. Fusion-only (the scalar
        # binop path never sees Max/Min); used to build a fused loop body for
        # np.maximum / np.minimum / np.clip.
        dt = _promote(l.type.dtype, r.type.dtype)
        fn = "maximum_elem" if kind == "Max" else "minimum_elem"
        return Val("nd::%s<%s>(%s, %s)"
                   % (fn, _CTYPE[dt], self._cast_scalar(l, dt),
                      self._cast_scalar(r, dt)), scalar_t(dt))

    def fail_generic(self, msg):
        raise UnsupportedSpec("py_to_cpp: " + msg)

    # ---- bitwise / logical ops ---------------------------------------------
    def _bitop(self, node):
        name, cop = self._BITOP[type(node.op)]
        fn = {"and": "bit_and", "or": "bit_or", "xor": "bit_xor"}[name]
        l = self.expr(node.left)
        r = self.expr(node.right)
        if l.type.kind in _VALUELESS_KINDS or r.type.kind in _VALUELESS_KINDS:
            self.fail(node, "bitwise op on shape/rng object")
        dt = _promote(l.type.dtype, r.type.dtype)
        if dt == "double":
            self.fail(node, "bitwise %s on floating-point operand(s)" % cop)
        if l.type.is_scalar() and r.type.is_scalar():
            return Val("(%s %s %s)"
                       % (self._cast_scalar(l, dt), cop, self._cast_scalar(r, dt)),
                       scalar_t(dt))
        rank = self._binop_rank(l, r)
        if l.type.is_array() and r.type.is_array():
            return Val("nd::%s(%s, %s)" % (fn, self._to_array_dtype(l, dt),
                                           self._to_array_dtype(r, dt)),
                       array_t(dt, rank))
        if l.type.is_array():
            return Val("nd::%s(%s, (%s)(%s))"
                       % (fn, self._to_array_dtype(l, dt), _CTYPE[dt],
                          self._cast_scalar(r, dt)), array_t(dt, rank))
        return Val("nd::%s((%s)(%s), %s)"
                   % (fn, _CTYPE[dt], self._cast_scalar(l, dt),
                      self._to_array_dtype(r, dt)), array_t(dt, rank))

    # ---- array arithmetic ---------------------------------------------------
    _NDFN = {"Add": "add", "Sub": "sub", "Mul": "mul",
             "Max": "maximum", "Min": "minimum", "Mod": "mod",
             "FloorDiv": "floordiv", "Pow": "power"}
    # ops with (Array,T)/(T,Array) scalar overloads in nd_runtime.h
    _SCALAR_OVERLOAD = {"add", "sub", "mul"}          # both sides
    _SCALAR_OVERLOAD_R = {"power"}                     # (Array, T) only

    def _array_binop(self, kind, l, r, node):
        # Emit the nd:: array op, then (Phase-2) attach a fusion tree when both
        # operands are fusable. ``.fuse`` is inert metadata: only assignment
        # sinks read it; every other consumer uses ``.code`` unchanged.
        v = self._array_binop_impl(kind, l, r, node)
        fz = self._binop_fuse(kind, l, r, v)
        if fz is not None:
            v.fuse = fz
        return v

    def _array_binop_impl(self, kind, l, r, node):
        # A texbuf handle has no array/scalar lowering. The Div branch (and any
        # future kind) can slip a non-array texbuf past the _cast_scalar /
        # _to_array_dtype guards, so reject centrally here (covers +,-,*,/,//,%,
        # **, maximum/minimum/clip on a stray read_texture() handle).
        if l.type.kind == "texbuf" or r.type.kind == "texbuf":
            self.fail(node, "texture handle from read_texture() may only be "
                            "passed to sample_texture()")
        if kind == "Div":
            ld = self._to_array_dtype(l, "double") if l.type.is_array() else None
            rd = self._to_array_dtype(r, "double") if r.type.is_array() else None
            rank = self._binop_rank(l, r)
            if l.type.is_array() and r.type.is_array():
                return Val("nd::divide(%s, %s)" % (ld, rd), array_t("double", rank))
            if l.type.is_array():  # array / scalar
                return Val("nd::divide(%s, (double)(%s))" % (ld, r.code),
                           array_t("double", rank))
            return Val("nd::divide((double)(%s), %s)" % (l.code, rd),
                       array_t("double", rank))

        dt = _promote(l.type.dtype, r.type.dtype)
        if kind == "Pow" and dt not in ("double", "int64"):
            dt = "int64"
        fn = self._NDFN[kind]
        rank = self._binop_rank(l, r)
        both_arr = l.type.is_array() and r.type.is_array()
        if both_arr:
            return Val("nd::%s(%s, %s)"
                       % (fn, self._to_array_dtype(l, dt),
                          self._to_array_dtype(r, dt)), array_t(dt, rank))
        # one operand is scalar
        if l.type.is_array():
            arr, sc, sc_left = l, r, False
        else:
            arr, sc, sc_left = r, l, True
        A = self._to_array_dtype(arr, dt)
        S = self._cast_scalar(sc, dt)
        if fn in self._SCALAR_OVERLOAD:
            if sc_left:
                return Val("nd::%s((%s)(%s), %s)" % (fn, _CTYPE[dt], sc.code, A),
                           array_t(dt, rank))
            return Val("nd::%s(%s, (%s)(%s))" % (fn, A, _CTYPE[dt], sc.code),
                       array_t(dt, rank))
        if fn in self._SCALAR_OVERLOAD_R and not sc_left:
            return Val("nd::%s(%s, (%s)(%s))" % (fn, A, _CTYPE[dt], sc.code),
                       array_t(dt, rank))
        # no matching scalar overload -> wrap the scalar as a 0-d array
        SA = "nd::scalar<%s>(%s)" % (_CTYPE[dt], S)
        if sc_left:
            return Val("nd::%s(%s, %s)" % (fn, SA, A), array_t(dt, rank))
        return Val("nd::%s(%s, %s)" % (fn, A, SA), array_t(dt, rank))

    # ---- Phase-2 elementwise fusion ----------------------------------------
    # Kinds whose per-element compute is reproduced by _scalar_binop /
    # _scalar_maxmin (byte-exact vs the nd:: array op).
    _FUSE_BINOPS = frozenset(["Add", "Sub", "Mul", "Div", "FloorDiv", "Mod",
                              "Pow", "Max", "Min"])

    def _fuse_operand(self, v):
        """Map an operand Val to a FuseNode leaf/subtree, or None if not fusable.

        A value that ALREADY carries a ``.fuse`` (an in-RHS elementwise subtree)
        is spliced whole, so a chain like ``a + b*c`` fuses into one tree. A bare
        scalar becomes a hoisted "scl" leaf; a bare array (known rank, non-bool)
        becomes a per-element "arr" leaf. bool arrays (bit-packed, no data()) and
        unknown-rank arrays are NOT fusable (return None -> caller falls back)."""
        if v.fuse is not None:
            return v.fuse
        if v.type.kind in _OPAQUE_KINDS:
            return None
        if v.type.is_scalar():
            # A bool-LABELED scalar may hold an int outside {0,1} (numpy/C++
            # `bool + bool` promotes to int -> can be 2; `bool - bool` -> -1).
            # Hoisting it into `const bool __s` would truncate the value, whereas
            # the nd:: fallback casts the expression straight to the consumer
            # dtype (int64/double). Not fusable -> fall back.
            if v.type.dtype == "bool":
                return None
            return FuseNode("scl", val=v)
        if v.type.is_array():
            if v.type.dtype == "bool" or v.type.rank is None:
                return None
            if v.type.rank == 0:
                # 0-d array: read once as a scalar (raw nd::atN form if present).
                base = v.raw if v.raw is not None else "(%s).item()" % v.code
                return FuseNode("scl", val=Val(base, scalar_t(v.type.dtype)))
            return FuseNode("arr", val=v)
        return None

    def _fuse_operand_for(self, v, result_rank):
        """Like _fuse_operand, but a bare rank-1 array feeding a rank-2 result is
        a numpy trailing-dim ROW broadcast (out[i,j] = ... c[j]) -- represent it
        as a "bcast" leaf read by column index, not a same-shape "arr" leaf. Only
        a plain (no in-RHS subtree) non-bool rank-1 array qualifies; a rank-1
        SUBTREE into a rank-2 result is not modelled per-column, so it disables
        fusion (return None -> caller falls back to the nd:: expression)."""
        if result_rank == 2 and v.type.is_array() and v.type.rank == 1 \
                and v.type.dtype != "bool":
            if v.fuse is not None:
                return None
            return FuseNode("bcast", val=v)
        return self._fuse_operand(v)

    def _binop_fuse(self, kind, l, r, result):
        """Build a FuseNode for an elementwise array binop, or None. ``result``
        is the nd:: Val just produced; its dtype/rank gate fusion."""
        if kind not in self._FUSE_BINOPS:
            return None
        if not result.type.is_array() or result.type.rank is None \
                or result.type.dtype == "bool":
            return None
        fl = self._fuse_operand_for(l, result.type.rank)
        fr = self._fuse_operand_for(r, result.type.rank)
        if fl is None or fr is None:
            return None
        if kind in ("Max", "Min"):
            emit = lambda vs, _k=kind: self._scalar_maxmin(_k, vs[0], vs[1])
        else:
            emit = lambda vs, _k=kind: self._scalar_binop(_k, vs[0], vs[1])
        fz = FuseNode("op", emit=emit, children=[fl, fr])
        # Record an ARRAY*ARRAY product's two coerced operands so a reduction
        # consuming it can emit nd::sum_mul and skip the a*b temporary (see
        # _reduce_op). `val` is inert on an "op" node -- collect() recurses into
        # children and build() calls emit(), neither reads it. The operand code
        # is re-derived with the SAME _to_array_dtype call _array_binop_impl
        # made, which is pure (returns a string, emits nothing), so this is the
        # identical text, not a second evaluation.
        if kind == "Mul" and l.type.is_array() and r.type.is_array():
            dt = result.type.dtype
            fz.val = ("Mul", self._to_array_dtype(l, dt),
                      self._to_array_dtype(r, dt))
        return fz

    @staticmethod
    def _fallback_expr(code, binds):
        """``code`` with already-bound leaves replaced by their bind names.

        Every leaf is bound BY VALUE above the guard, so the else branch's
        verbatim nd:: expression re-computes each operand a SECOND time -- a
        guard miss costs double the operand work, and the discarded first
        evaluation is not something the C++ compiler can eliminate (the nd::
        calls allocate). A bind is a shallow handle onto exactly the buffer the
        re-evaluation would produce, so substituting is byte-identical.

        Only CALL expressions are substituted (``"(" in code``). A bare
        identifier or literal is free to re-read, and rewriting those by text
        would be unsafe -- a leaf named ``k`` is a substring of ``mask``.
        Longest-first, so a leaf nested inside another leaf's text is rewritten
        as part of its container rather than orphaning it.
        """
        for src in sorted((c for c in binds if "(" in c),
                          key=len, reverse=True):
            code = code.replace(src, binds[src])
        return code

    def _emit_no_fma(self):
        """Pin FP contraction off for the fused scalar loop that follows.

        A fused arm evaluates ``a - b*c`` as ONE expression, which clang (whose
        default is ``-ffp-contract=on``) may emit as a single FMA -- one rounding
        where the nd:: fallback, materialising ``b*c`` into a temporary first,
        rounds twice. That is a ~1 ULP divergence between two arms of the SAME
        block. The toolchain already passes ``-ffp-contract=off``, but the
        lowering harnesses compare with ``np.allclose(rtol=1e-12)``, so a 1 ULP
        drift would not be caught if a build flag ever regressed. Pinning it in
        the source is the only guard that travels with the generated code.

        Must be the first thing in the compound statement -- that is where clang
        accepts the pragma.
        """
        self.emit("#if defined(__clang__)")
        self.emit("#pragma clang fp contract(off)")
        self.emit("#endif")

    def _emit_fused(self, cname, val, node):
        """Emit a runtime-guarded scalar loop assigning ``cname`` from the fusion
        tree on ``val`` (nested nd:: ``val.code`` kept as the else-branch
        fallback). Returns True if it emitted the loop, else False (the caller
        then emits the plain nd:: assignment). Worst case: the guard is false at
        runtime and the byte-identical nd:: expression runs -- never wrong."""
        root = val.fuse
        if root is None or root.kind != "op":
            return False
        if not val.type.is_array() or val.type.rank is None \
                or val.type.dtype == "bool":
            return False
        # Collect distinct array/scalar leaves (dedup by code text so a repeated
        # leaf like a*a binds/hoists once).
        arr_names, arr_order = {}, []
        scl_names, scl_order = {}, []
        mm_names, mm_order = {}, []      # matmul producers: (Acode,Bcode) -> index
        bc_names, bc_order = {}, []      # row-broadcast leaves: Ccode -> name

        def collect(fn):
            if fn.kind == "arr":
                if fn.val.code not in arr_names:
                    arr_names[fn.val.code] = "__L%d" % len(arr_order)
                    arr_order.append(fn.val)
            elif fn.kind == "scl":
                if fn.val.code not in scl_names:
                    scl_names[fn.val.code] = "__s%d" % len(scl_order)
                    scl_order.append(fn.val)
            elif fn.kind == "matmul":
                key = (fn.val[0].code, fn.val[1].code)
                if key not in mm_names:
                    mm_names[key] = len(mm_order)
                    mm_order.append(fn.val)
            elif fn.kind == "bcast":
                if fn.val.code not in bc_names:
                    bc_names[fn.val.code] = "__bc%d" % len(bc_order)
                    bc_order.append(fn.val)
            else:
                for ch in fn.children:
                    collect(ch)
        collect(root)
        # Every rank>=2 arr leaf gets an `is_contiguous()` term in the guard
        # below (and in the producer's guard). A bare `x[..., None]` leaf can
        # never satisfy it -- see _is_trailing_newaxis_view -- so the guard is
        # false for EVERY input and the loop it protects is unreachable. Decline
        # and let the caller emit the plain nd:: expression: byte-identical, it
        # is the arm that already runs, minus the dead code.
        for v in arr_order:
            if v.type.rank is not None and v.type.rank >= 2 \
                    and _is_trailing_newaxis_view(v):
                return False
        # Producer mode (Inc2): a 2-D matmul and/or a row-broadcast leaf. The
        # output is (m, N) and each element is (i=__i/__N, j=__i%__N) -- a
        # different loop shape than the plain-elementwise flat loop below.
        if mm_order or bc_order:
            return self._emit_fused_producer(
                cname, val, root, arr_names, arr_order, scl_names, scl_order,
                mm_names, mm_order, bc_names, bc_order)
        if not arr_order:
            return False    # no array leaf -> nothing to size/iterate the loop

        def read_of(v):
            bind = arr_names[v.code]
            if v.type.rank == 1:
                # rank-1 leaves may be strided views (e.g. a column of (N,3)).
                code = ("(*%s.data)[(size_t)(%s.offset + __i * %s.strides[0])]"
                        % (bind, bind, bind))
            else:  # rank >= 2: guaranteed C-contiguous (offset 0) by the guard.
                code = "(*%s.data)[(size_t)__i]" % bind
            return Val(code, scalar_t(v.type.dtype))

        def build(fn):
            if fn.kind == "arr":
                return read_of(fn.val)
            if fn.kind == "scl":
                return Val(scl_names[fn.val.code], scalar_t(fn.val.type.dtype))
            return fn.emit([build(ch) for ch in fn.children])
        body = build(root)

        To = _CTYPE[val.type.dtype]
        L0 = arr_names[arr_order[0].code]
        self.emit("{")
        self.indent += 1
        for v in arr_order:
            # Bind leaves BY VALUE, not by reference: the fused output may BE one
            # of these leaves (`a = a / d`), and `cname = ::alloc(...)` below
            # reassigns it. A reference would then alias the fresh (zeroed)
            # buffer; a value copy is a shallow handle that snapshots the old
            # buffer via shared_ptr -- exactly what the nd:: fallback captures.
            self.emit("const nd::Array<%s> %s = %s;"
                      % (_CTYPE[v.type.dtype], arr_names[v.code], v.code))
        # Hoist scalar leaves BEFORE the realloc too: a scalar leaf may read the
        # destination (`side = side / norm(side)`), so it must be captured while
        # cname still holds the old buffer -- same reasoning as the by-value
        # array binds above.
        for v in scl_order:
            self.emit("const %s %s = %s;"
                      % (_CTYPE[v.type.dtype], scl_names[v.code], v.code))
        terms = ["%s.shape == %s.shape" % (arr_names[v.code], L0)
                 for v in arr_order[1:]]
        terms += ["%s.is_contiguous()" % arr_names[v.code]
                  for v in arr_order if v.type.rank >= 2]
        guard = " && ".join(terms) if terms else "true"
        self.emit("if ( %s ) {" % guard)
        self.indent += 1
        self._emit_no_fma()
        self.emit("%s = nd::Array<%s>::alloc(%s.shape);" % (cname, To, L0))
        self.emit("%s* __o = %s.data->data();" % (To, cname))
        self.emit("const int64_t __n = %s.size();" % cname)
        self.emit("for (int64_t __i = 0; __i < __n; ++__i) {")
        self.indent += 1
        self.emit("__o[(size_t)__i] = (%s)( %s );" % (To, body.code))
        self.indent -= 1
        self.emit("}")
        self.indent -= 1
        self.emit("} else {")
        self.indent += 1
        binds = dict(arr_names)
        binds.update(scl_names)
        self.emit("%s = %s;" % (cname, self._fallback_expr(val.code, binds)))
        self.indent -= 1
        self.emit("}")
        self.indent -= 1
        self.emit("}")
        return True

    def _emit_fused_producer(self, cname, val, root, arr_names, arr_order,
                             scl_names, scl_order, mm_names, mm_order,
                             bc_names, bc_order):
        """Producer-mode fused loop (Inc2): the tree contains a 2-D matmul and/or
        a row-broadcast leaf, so the output is (m, N) and each element is indexed
        (i = __i/__N, j = __i%__N). A matmul leaf becomes an inline acc-loop
        (byte-identical to nd::matmul2d: acc=(T)0; ascending-l acc += A[i,l]*B[l,j]);
        a bcast leaf reads column j; rank-2 arr leaves read flat (guarded
        contiguous). The nested nd:: expression stays as the else-branch fallback,
        so a guard miss (or any rank-1 arr leaf) is never wrong."""
        # Plain arr leaves are read FLAT (__i over m*N); a rank-1 arr leaf would
        # be out of bounds. Bail to the nd:: fallback if one appears.
        for v in arr_order:
            if v.type.rank != 2:
                return False
        if val.type.dtype == "bool":
            return False
        To = _CTYPE[val.type.dtype]
        self.emit("{")
        self.indent += 1
        # Bind every leaf BY VALUE before the realloc (same aliasing reasoning as
        # the elementwise path: the fused output may BE one of the inputs).
        for i, (A, B) in enumerate(mm_order):
            self.emit("const nd::Array<%s> __mmA%d = %s;"
                      % (_CTYPE[A.type.dtype], i, A.code))
            self.emit("const nd::Array<%s> __mmB%d = %s;"
                      % (_CTYPE[B.type.dtype], i, B.code))
        for v in arr_order:
            self.emit("const nd::Array<%s> %s = %s;"
                      % (_CTYPE[v.type.dtype], arr_names[v.code], v.code))
        for v in bc_order:
            self.emit("const nd::Array<%s> %s = %s;"
                      % (_CTYPE[v.type.dtype], bc_names[v.code], v.code))
        for v in scl_order:
            self.emit("const %s %s = %s;"
                      % (_CTYPE[v.type.dtype], scl_names[v.code], v.code))
        # Sizing source: a matmul gives (A.rows, B.cols); else a rank-2 arr leaf.
        if mm_order:
            alloc_shape = "{ __mmA0.shape[0], __mmB0.shape[1] }"
            size_N = "__mmB0.shape[1]"
        else:
            L0 = arr_names[arr_order[0].code]
            alloc_shape = "%s.shape" % L0
            size_N = "%s.shape[1]" % L0
        # Guard (fall back if any is false at runtime).
        terms = []
        for i in range(len(mm_order)):
            t = ("__mmA%d.ndim() == 2 && __mmB%d.ndim() == 2 "
                 "&& __mmA%d.shape[1] == __mmB%d.shape[0]" % (i, i, i, i))
            if i > 0:   # every matmul must yield the same (m, N) output.
                t += (" && __mmA%d.shape[0] == __mmA0.shape[0]"
                      " && __mmB%d.shape[1] == __mmB0.shape[1]" % (i, i))
            terms.append(t)
        for v in bc_order:
            terms.append("%s.size() == %s" % (bc_names[v.code], size_N))
        if mm_order:
            for v in arr_order:
                n = arr_names[v.code]
                terms.append("%s.ndim() == 2 && %s.shape[0] == __mmA0.shape[0] "
                             "&& %s.shape[1] == __mmB0.shape[1] "
                             "&& %s.is_contiguous()" % (n, n, n, n))
        else:
            L0 = arr_names[arr_order[0].code]
            terms.append("%s.is_contiguous()" % L0)
            for v in arr_order[1:]:
                n = arr_names[v.code]
                terms.append("%s.shape == %s.shape && %s.is_contiguous()"
                             % (n, L0, n))
        guard = " && ".join(terms) if terms else "true"
        self.emit("if ( %s ) {" % guard)
        self.indent += 1
        self._emit_no_fma()
        self.emit("%s = nd::Array<%s>::alloc(%s);" % (cname, To, alloc_shape))
        self.emit("%s* __o = %s.data->data();" % (To, cname))
        self.emit("const int64_t __n = %s.size();" % cname)
        self.emit("const int64_t __N = %s;" % size_N)
        self.emit("for (int64_t __i = 0; __i < __n; ++__i) {")
        self.indent += 1
        self.emit("const int64_t __ii = __i / __N;")
        self.emit("const int64_t __jj = __i % __N;")
        # Inline matmul accumulators (byte-identical to nd::matmul2d: acc=(T)0,
        # ascending l, C-order, stride reads).
        for i, (A, B) in enumerate(mm_order):
            tm = _CTYPE[A.type.dtype]
            self.emit("%s __mm%d = (%s)0;" % (tm, i, tm))
            self.emit("for (int64_t __l = 0; __l < __mmA%d.shape[1]; ++__l) {" % i)
            self.indent += 1
            self.emit("__mm%d += (*__mmA%d.data)[(size_t)(__mmA%d.offset "
                      "+ __ii * __mmA%d.strides[0] + __l * __mmA%d.strides[1])] "
                      "* (*__mmB%d.data)[(size_t)(__mmB%d.offset "
                      "+ __l * __mmB%d.strides[0] + __jj * __mmB%d.strides[1])];"
                      % (i, i, i, i, i, i, i, i, i))
            self.indent -= 1
            self.emit("}")

        def build(fn):
            if fn.kind == "arr":
                return Val("(*%s.data)[(size_t)__i]" % arr_names[fn.val.code],
                           scalar_t(fn.val.type.dtype))
            if fn.kind == "scl":
                return Val(scl_names[fn.val.code], scalar_t(fn.val.type.dtype))
            if fn.kind == "matmul":
                key = (fn.val[0].code, fn.val[1].code)
                return Val("__mm%d" % mm_names[key],
                           scalar_t(fn.val[0].type.dtype))
            if fn.kind == "bcast":
                c = bc_names[fn.val.code]
                return Val("(*%s.data)[(size_t)(%s.offset + __jj * %s.strides[0])]"
                           % (c, c, c), scalar_t(fn.val.type.dtype))
            return fn.emit([build(ch) for ch in fn.children])
        body = build(root)
        self.emit("__o[(size_t)__i] = (%s)( %s );" % (To, body.code))
        self.indent -= 1
        self.emit("}")
        self.indent -= 1
        self.emit("} else {")
        self.indent += 1
        # Same leaf reuse as the elementwise path, plus this mode's matmul and
        # row-broadcast binds. A matmul operand is the most expensive thing in
        # the block, so re-evaluating it on a guard miss is the worst case.
        binds = dict(arr_names)
        binds.update(bc_names)
        binds.update(scl_names)
        for i, (A, B) in enumerate(mm_order):
            binds[A.code] = "__mmA%d" % i
            binds[B.code] = "__mmB%d" % i
        self.emit("%s = %s;" % (cname, self._fallback_expr(val.code, binds)))
        self.indent -= 1
        self.emit("}")
        self.indent -= 1
        self.emit("}")
        return True

    def _fuse_into_temp(self, val, node, prefix):
        """If ``val`` carries a fusable elementwise tree, hoist a temp, emit the
        guarded fused loop into it, and return the temp's C++ name; else None.
        Used by sinks that cannot fuse in place (return, output write)."""
        if val.fuse is None or not val.type.is_array() \
                or val.type.rank is None or val.type.dtype == "bool":
            return None
        tmpkey = self._new_tmp(prefix)
        self.decls[tmpkey] = val.type
        cpp = self._cpp_local(tmpkey)
        if self._emit_fused(cpp, val, node):
            return cpp
        self.decls.pop(tmpkey, None)   # declined -> drop the unused declaration
        return None

    def _binop_rank(self, l, r):
        ra = l.type.rank if l.type.is_array() else 0
        rb = r.type.rank if r.type.is_array() else 0
        if ra is None or rb is None:
            return None
        return max(ra, rb)

    def _matmul(self, l, r, node):
        if not (l.type.is_array() and r.type.is_array()):
            self.fail(node, "matmul requires two arrays")
        dt = _promote(l.type.dtype, r.type.dtype)
        rank = None
        if l.type.rank is not None and r.type.rank is not None:
            if l.type.rank == 1 and r.type.rank == 1:
                rank = 0
            elif l.type.rank == 2 and r.type.rank == 2:
                rank = 2
            elif {l.type.rank, r.type.rank} == {1, 2}:
                rank = 1
            else:
                rank = max(l.type.rank, r.type.rank)
        la = self._to_array_dtype(l, dt)
        ra = self._to_array_dtype(r, dt)
        v = Val("nd::matmul(%s, %s)" % (la, ra), array_t(dt, rank))
        # Phase-2 (Inc2): a 2-D @ 2-D matmul is a fusion PRODUCER. When it feeds
        # an elementwise op, _emit_fused expands each output element as an inline
        # dot product inside the consumer loop -- erasing the (m,N) temp. `.code`
        # stays nd::matmul (the byte-identical fallback). Operands are captured at
        # the PROMOTED dtype (exactly what nd::matmul reads), so the fused
        # accumulation matches nd::matmul2d bit-for-bit. Matvecs / bool excluded.
        if l.type.rank == 2 and r.type.rank == 2 and dt != "bool":
            v.fuse = FuseNode("matmul", val=(Val(la, array_t(dt, 2)),
                                             Val(ra, array_t(dt, 2))))
        return v

    # ==== coercions ======================================================
    def _cast_scalar(self, v, dt):
        if v.type.dtype == "str":          # the str AND strv carriers
            self.fail_generic("string value used where a numeric scalar is required")
        if v.type.kind == "texbuf":
            self.fail_generic("texture handle from read_texture() may only be "
                              "passed to sample_texture()")
        if v.type.is_array():
            if v.type.rank not in (0, None):
                self.fail_generic("array used where a scalar is required")
            # A fully integer-indexed subscript carries a raw scalar form
            # (nd::atN) -- use it to avoid allocating a per-access nd:: view.
            base = v.raw if v.raw is not None else "(%s).item()" % v.code
            src = v.type.dtype
        else:
            base, src = v.code, v.type.dtype
        if src == dt:
            return base
        return "(%s)(%s)" % (_CTYPE[dt], base)

    def _to_array_dtype(self, v, dt):
        if v.type.dtype == "str":          # the str AND strv carriers
            self.fail_generic("string value used where a numeric array is required")
        if v.type.kind == "texbuf":
            self.fail_generic("texture handle from read_texture() may only be "
                              "passed to sample_texture()")
        if v.type.is_scalar():
            return "nd::scalar<%s>(%s)" % (_CTYPE[dt], self._cast_scalar(v, dt))
        if v.type.dtype == dt:
            return v.code
        return "nd::astype<%s>(%s)" % (_CTYPE[dt], v.code)

    def _as_bool(self, v, node):
        if v.type.kind in ("str", "strv"):
            # Python: a str / list is falsey ONLY when empty -- .empty() is the
            # same test on both carriers, so this is exact, not an approximation.
            return "(!(%s).empty())" % v.code
        if v.type.kind == "texbuf":
            self.fail(node, "texture handle from read_texture() may only be "
                            "passed to sample_texture()")
        if v.type.is_array():
            self.fail(node, "array used as a boolean condition (ambiguous)")
        if v.type.dtype == "bool":
            return v.code
        return "((%s) != 0)" % v.code

    def _scalar_int_of(self, v, node):
        if v.type.kind == "str":
            # Without this the fall-through emitted
            # `(int64_t)(std::string("browUp"))` -- not a valid conversion, so a
            # name-keyed subscript passed the transpiler and then died in the C++
            # compiler with an unrelated-looking error. Reject here, where the
            # message names the real cause. (``_as_bool`` guards `str` the same.)
            self.fail(node, "string used where an integer index is required -- "
                            "a name key has no runtime form. Index by position.")
        if v.type.is_array():
            if v.type.rank not in (0, None):
                self.fail(node, "array where an integer scalar is required")
            if v.raw is not None:
                return "(int64_t)(%s)" % v.raw
            return "(int64_t)(%s).item()" % v.code
        if v.type.dtype == "int64":
            return v.code
        return "(int64_t)(%s)" % v.code

    # ==== subscript / slicing ============================================
    def ex_Subscript(self, node):
        base = self.expr(node.value)
        if base.type.kind == "shape":
            idx = self._const_or_scalar_index(node.slice)
            return Val("(int64_t)%s[%s]" % (base.type.code, idx),
                       scalar_t("int64"))
        if base.type.kind == "strv":
            # v[i] on a string vector -> one std::string. Positional only: a
            # slice would need a runtime-sized sub-vector (a second carrier this
            # kind does not have), so it rejects rather than lowering a
            # near-miss. nd::strv_at applies the same negative wrap as nd::at1.
            elts = self._index_elts(node.slice)
            if len(elts) != 1 or isinstance(elts[0], ast.Slice):
                self.fail(node, "a string list supports a single positional "
                                "index, not a slice or a tuple index")
            idx = self._scalar_int_of(self.expr(elts[0]), node)
            return Val("nd::strv_at(%s, %s)" % (base.code, idx), str_t())
        if not base.type.is_array():
            self.fail(node, "indexing a non-array value")
        # Raw-access fast path: a FULL all-integer index yields a scalar; emit an
        # nd::atN(base, i, ...) raw read (no per-access view allocation) as the
        # Val's ``raw`` form, keeping the nd::slice as ``code`` for any array
        # context. See _all_integer_index_exprs / nd_runtime.h at1..at4.
        idxs = self._all_integer_index_exprs(node, base.type)
        if idxs is not None:
            specs = ", ".join("nd::Sl::at(%s)" % x for x in idxs)
            code = "nd::slice(%s, {%s})" % (base.code, specs)
            raw = "nd::at%d(%s, %s)" % (len(idxs), base.code, ", ".join(idxs))
            return Val(code, array_t(base.type.dtype, 0), raw=raw)
        # a[idx] where idx is an integer ARRAY -- numpy fancy indexing on axis 0,
        # and the single most common way to spell a gather (`pts[indices]` after
        # a KD-tree query). Without it the index reaches _one_slice, which needs
        # an integer SCALAR, and the whole node is rejected.
        gather = self._as_gather_index(node, base)
        if gather is not None:
            return gather
        specs, rank, newaxis_pos = self._build_slice(node, base.type)
        code = "nd::slice(%s, {%s})" % (base.code, ", ".join(specs))
        for p in newaxis_pos:
            code = "nd::newaxis(%s, %d)" % (code, p)
        return Val(code, array_t(base.type.dtype, rank))

    def _as_gather_index(self, node, base):
        """`a[idx]` with an integer-array ``idx`` -> ``nd::take(a, idx, 0)``.

        Exact, not an approximation: nd::take's axis form produces
        ``idx.shape + a.shape[1:]`` and wraps negative indices, which is what
        numpy's fancy indexing on axis 0 does. Only the SINGLE-index form is
        lowered -- a mixed tuple (``a[idx, 1]``) follows advanced-indexing
        broadcasting rules this does not implement, so it keeps falling through
        to the slice path and its existing rejection.
        """
        elts = self._index_elts(node.slice)
        if len(elts) != 1:
            return None
        e = elts[0]
        if isinstance(e, ast.Slice) or self._is_newaxis(e):
            return None
        if isinstance(e, ast.Constant) and e.value is Ellipsis:
            return None
        idx = self.expr(e)
        if not idx.type.is_array() or idx.type.rank in (0, None):
            return None
        if idx.type.dtype == "bool":
            # A mask SELECTS a runtime-sized subset -- a different operation
            # from a gather, and one whose result length is not known here.
            self.fail(node, "boolean mask indexing a[mask] is not lowered (the "
                            "result length is not known at compile time); use "
                            "np.where / np.nonzero + np.take")
        if base.type.rank is None:
            self.fail(node, "a[idx] with an array index needs a statically "
                            "known rank on the indexed array")
        idxc = (idx.code if idx.type.dtype == "int64"
                else "nd::astype<int64_t>(%s)" % idx.code)
        return Val("nd::take(%s, %s, 0)" % (base.code, idxc),
                   array_t(base.type.dtype, base.type.rank - 1 + idx.type.rank))

    def _all_integer_index_exprs(self, subscript, base_type):
        """If ``subscript`` is a FULL all-integer index of ``base_type`` (every
        axis indexed by an integer -- no slice / np.newaxis / Ellipsis -- so the
        result is a scalar), return the list of C++ integer-index expressions;
        else None.

        Gates the raw-pointer element-access recipe: rank must be statically
        known and 1..4 (the arities nd::atN provides), the index count must equal
        the rank (a partial index is a VIEW, not a scalar), and ``bool`` arrays
        are excluded (std::vector<bool> is bit-packed -- keep the nd:: path)."""
        rank = base_type.rank
        if rank is None or not (1 <= rank <= 4):
            return None
        if base_type.dtype == "bool":
            return None
        elts = self._index_elts(subscript.slice)
        if len(elts) != rank:
            return None
        idxs = []
        for e in elts:
            if isinstance(e, ast.Slice) or self._is_newaxis(e):
                return None
            if isinstance(e, ast.Constant) and e.value is Ellipsis:
                return None
            v = self.expr(e)
            if v.type.is_array() and v.type.rank not in (0, None):
                return None   # a rank>0 index (fancy indexing) -- not integer
            idxs.append(self._scalar_int_of(v, e))
        return idxs

    def _const_or_scalar_index(self, sl):
        node = sl.value if isinstance(sl, ast.Index) else sl
        v = self.expr(node)
        return self._scalar_int_of(v, node)

    def _index_elts(self, sl):
        node = sl.value if isinstance(sl, ast.Index) else sl
        if isinstance(node, ast.Tuple):
            return list(node.elts)
        return [node]

    def _build_slice(self, subscript, base_type):
        """Return (list-of-Sl-C++-exprs, result_rank, newaxis_positions).

        newaxis_positions is a list of OUTPUT-axis indices (source order) at
        which an ``np.newaxis``/``None`` inserts a length-1 axis; empty == none.
        The Sl specs cover only the non-newaxis index entries, in source order;
        ``nd::slice`` pads any unmentioned trailing axes with full slices, and
        callers insert ``nd::newaxis`` at each returned position in order (each
        position already accounts for axes inserted to its left)."""
        elts = self._index_elts(subscript.slice)
        if any(isinstance(e, ast.Constant) and e.value is Ellipsis for e in elts):
            if any(self._is_newaxis(e) for e in elts):
                self.fail(subscript, "Ellipsis mixed with np.newaxis (SP-5)")
            specs, rank, _ = self._build_slice_ellipsis(subscript, elts, base_type)
            return specs, rank, []
        specs = []
        newaxis_pos = []
        out_pos = 0
        n_index = 0
        for e in elts:
            if self._is_newaxis(e):
                newaxis_pos.append(out_pos)
                out_pos += 1
                continue
            s, is_index = self._one_slice(e, subscript)
            specs.append(s)
            if is_index:
                n_index += 1
            else:
                out_pos += 1
        rank = None
        if base_type.rank is not None:
            rank = base_type.rank - n_index + len(newaxis_pos)
        return specs, rank, newaxis_pos

    def _build_slice_ellipsis(self, subscript, elts, base_type):
        if base_type.rank is None:
            self.fail(subscript, "Ellipsis index needs a statically known rank")
        n_ell = sum(1 for e in elts
                    if isinstance(e, ast.Constant) and e.value is Ellipsis)
        if n_ell != 1:
            self.fail(subscript, "multiple Ellipsis")
        explicit = [e for e in elts
                    if not (isinstance(e, ast.Constant) and e.value is Ellipsis)]
        if any(self._is_newaxis(e) for e in explicit):
            self.fail(subscript, "Ellipsis mixed with np.newaxis (SP-5)")
        fill = base_type.rank - len(explicit)
        if fill < 0:
            self.fail(subscript, "too many indices for array")
        specs, dropped = [], 0
        for e in elts:
            if isinstance(e, ast.Constant) and e.value is Ellipsis:
                specs.extend([self._sl_full()] * fill)
                continue
            s, is_index = self._one_slice(e, subscript)
            specs.append(s)
            if is_index:
                dropped += 1
        return specs, base_type.rank - dropped, False

    def _is_newaxis(self, e):
        if isinstance(e, ast.Constant) and e.value is None:
            return True
        return self._canon(e) == "%s.newaxis" % _CANON_NUMPY

    def _is_full_slice(self, e):
        return (isinstance(e, ast.Slice) and e.lower is None
                and e.upper is None and e.step is None)

    def _sl_full(self):
        return "nd::Sl::full()"

    def _one_slice(self, e, ctx):
        """-> (C++ Sl expr, is_integer_index)."""
        if isinstance(e, ast.Slice):
            hs = e.lower is not None
            he = e.upper is not None
            start = self._int_arg(e.lower) if hs else "0"
            stop = self._int_arg(e.upper) if he else "0"
            step = self._int_arg(e.step) if e.step is not None else "1"
            return ("nd::Sl::mk(%s, %s, %s, %s, %s)"
                    % ("true" if hs else "false", start,
                       "true" if he else "false", stop, step), False)
        if self._is_newaxis(e):
            self.fail(ctx, "np.newaxis in this position (SP-5)")
        # integer index -> drops the axis
        return ("nd::Sl::at(%s)" % self._int_arg(e), True)

    # ==== attributes (x.T / x.shape / x.ndim / x.size) and dotted names ===
    def ex_Attribute(self, node):
        dotted = self._dotted(node)
        if dotted is not None:
            # persistent stateful self-var read (self.<name> latched across
            # compute() calls) -> the per-node member `st.<name>`. Checked BEFORE
            # the env lookup so state vars never collide with declared IO. Its
            # type is discovered at the first assignment; reading before the first
            # write (non-idiomatic) fails -> the caller falls back to the porter.
            if dotted.startswith("self.") and dotted[5:] in self.state_vars:
                nm = dotted[5:]
                if nm not in self.state_members:
                    self.fail(node,
                              "persistent state %r read before initialization"
                              % nm)
                return Val("st.%s" % nm, self.state_members[nm])
            # bound environment entry (e.g. self.<attr>) or a np/math constant.
            # A dotted env entry lowers to its materialised C++ local name so the
            # emitted code is a valid identifier (self.foo -> ndin_self_foo).
            if dotted in self.env:
                return Val(env_cpp_name(dotted), self.env[dotted])
            konst = self._named_constant(self._canon(node))
            if konst is not None:
                return konst
        base = self.expr(node.value)
        attr = node.attr
        if base.type.is_array():
            if attr == "T":
                return Val("nd::transpose(%s)" % base.code,
                           array_t(base.type.dtype, base.type.rank))
            if attr == "shape":
                return Val(base.code, CppType("shape", code="%s.shape" % base.code))
            if attr == "ndim":
                return Val("(int64_t)%s.ndim()" % base.code, scalar_t("int64"))
            if attr == "size":
                return Val("(int64_t)%s.size()" % base.code, scalar_t("int64"))
        self.fail(node, "attribute .%s" % attr)

    def _named_constant(self, canon):
        """np.pi / math.e / `from numpy import pi` -- keyed on the ORIGIN."""
        head, _, tail = (canon or "").partition(".")
        if head in (_CANON_NUMPY, _CANON_MATH):
            table = {"pi": "3.141592653589793", "e": "2.718281828459045",
                     "inf": "INFINITY", "nan": "NAN"}
            if tail in table:
                return Val("(%s)" % table[tail], scalar_t("double"))
        return None

    def _canon(self, node):
        """The CANONICAL origin of a dotted name expression, or None.

        ``la.norm`` -> ``numpy.linalg.norm``, ``s(...)`` (from ``from numpy
        import sin as s``) -> ``numpy.sin``. Every module dispatch compares
        against a canonical name, so all the import spellings that reach one
        function reach one lowering."""
        dotted = self._dotted(node)
        if dotted is None:
            return None
        # A bound VALUE of that name shadows any module: a local `np` is the
        # local, whatever the module table says. `self` is the node instance and
        # can never be a module -- and it needs naming explicitly because a
        # compute block's env is keyed by the FULL dotted name ("self.v"), so the
        # head "self" is never itself in env.
        head = dotted.partition(".")[0]
        if head == "self" or head in self.env:
            return dotted
        return canonical_dotted(dotted, self.imports, self.import_stars)

    def _dotted(self, node):
        """Resolve a (possibly dotted) name expression to 'a.b.c' or None."""
        return dotted_name(node)

    # ==== calls ==========================================================
    def ex_Call(self, node):
        dotted = self._dotted(node.func)
        if dotted is not None:
            # Builtins that NO supported module exports stay builtins even under
            # `from numpy import *`. Checked FIRST or the star resolver would
            # claim them -- see _NEVER_MODULE_BUILTINS for why abs/min/max/round/
            # sum/any/all are deliberately NOT in that set.
            if (dotted in _NEVER_MODULE_BUILTINS
                    and dotted not in self.imports and dotted not in self.env):
                if dotted == "hasattr":
                    return self._call_hasattr(node)
                if dotted == "getattr":
                    return self._call_getattr(node)
                if dotted == "isinstance":
                    return self._call_isinstance(node)
                return self._call_builtin(dotted, node)
            # Module dispatch keys off the RESOLVED ORIGIN, never the spelling,
            # so every import shape that reaches one function -- np.sin,
            # onp.sin, `from numpy import sin as s` -- reaches one lowering.
            canon = self._canon(node.func)
            for mod, handler in ((_CANON_NUMPY, self._call_numpy),
                                 (_CANON_MATH, self._call_math),
                                 (_CANON_NDIO, self._call_ndio)):
                if canon.startswith(mod + "."):
                    return handler(canon[len(mod) + 1:], node)
            if dotted == "hasattr":
                return self._call_hasattr(node)
            if dotted == "getattr":
                return self._call_getattr(node)
            if dotted in ("len", "int", "float", "bool", "abs", "min", "max",
                          "str", "list"):
                return self._call_builtin(dotted, node)
            if "." not in dotted:
                if self.helpers is not None and dotted in self.helpers.defs:
                    return self._call_helper(dotted, node)
                self._reject_unbound_kdtree(node)
                self.fail(node, "call to unknown function %r" % dotted)
        # blessed `self.<name>(...)` in expression position -> the codegen-supplied
        # lowering callable (e.g. read_texture -> nd_tex_load_linear). Checked
        # BEFORE the generic method-call fallback so it never reaches _call_method
        # (which would reject `self.<name>()`).
        if (self.blessed and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.func.attr in self.blessed):
            return self.blessed[node.func.attr](self, node)
        # method call on an expression value: x.method(...)
        if isinstance(node.func, ast.Attribute):
            return self._call_method(node)
        self.fail(node, "unsupported call")

    # ---- hasattr(self, '<name>') -------------------------------------------
    def _call_hasattr(self, node):
        """Lower `hasattr(self, '<name>')` (the persistent-state first-run test).

        A persistent state var -> `st.<name>_isset` (false until first written,
        true after). A declared IO attr is always present -> `true`. Anything
        else is rejected so the caller falls back to the porter."""
        if (len(node.args) == 2 and not node.keywords
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "self"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            nm = node.args[1].value
            if nm in self.state_vars:
                return Val("st.%s_isset" % nm, scalar_t("bool"))
            if ("self." + nm) in self.env or ("self." + nm) in self.output_writers:
                return Val("true", scalar_t("bool"))
        self.fail(node, "hasattr on a non-state/non-declared attribute")

    # ---- getattr(self, '<name>', <default>) ---------------------------------
    def _call_getattr(self, node):
        """Lower `getattr(self, '<name>', <default>)` -- the "use it if this
        node declares it" idiom for optional inputs and for animation state
        that needs no seeding.

        Presence is a COMPILE-TIME fact for a declared attr, so the call folds
        to the plain read; an undeclared name folds to the default. A
        persistent state var is the one runtime case -- it is absent until its
        first write -- and reuses the `hasattr` test through an equivalent
        conditional, so branch typing and its rejects stay in one place.

        The 2-arg form is deliberately NOT lowered: it raises in Python when
        the attribute is missing, and a compiled node cannot raise."""
        if not (len(node.args) == 3 and not node.keywords
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "self"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            self.fail(node, "only getattr(self, '<name>', <default>) is "
                            "supported")
        nm = node.args[1].value
        read = ast.copy_location(
            ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                          attr=nm, ctx=ast.Load()), node)
        if nm in self.state_vars:
            probe = ast.copy_location(ast.Call(
                func=ast.Name(id="hasattr", ctx=ast.Load()),
                args=[ast.Name(id="self", ctx=ast.Load()),
                      ast.Constant(value=nm)], keywords=[]), node)
            return self.expr(ast.fix_missing_locations(ast.copy_location(
                ast.IfExp(test=probe, body=read, orelse=node.args[2]), node)))
        if ("self." + nm) in self.env or ("self." + nm) in self.output_writers:
            return self.expr(read)
        return self.expr(node.args[2])

    # ---- isinstance(<statically-None value>, <type>) ------------------------
    def _call_isinstance(self, node):
        """Fold `isinstance(x, T)` -- ONLY when `x` is statically None.

        That is the "this node does not declare the optional attribute" idiom:
        `cfg = getattr(self, 'cfg', None)` followed by `if not isinstance(cfg,
        dict)`. A None binding carries no C++ value at all (see `_is_none_expr` /
        `_compare_to_none`), so its Python class IS a compile-time fact and every
        class in `_ISINSTANCE_TYPES` answers False.

        Any other operand rejects, deliberately. A lowered value keeps no record
        of the Python class it came from: dtype 'double' covers a Python float
        AND a np.float32 element, and `isinstance(np.float32(1.0), float)` is
        False while `isinstance(np.float64(1.0), float)` is True -- one lowered
        type, two Python answers. dtype 'int64' has the same split (np.int64 is
        not an int) and so does 'bool' (np.bool_ is not a bool). Folding those
        would silently disagree with the interpreted node."""
        if len(node.args) != 2 or node.keywords:
            self.fail(node, "only isinstance(<value>, <type>) is lowered")
        obj, cls = node.args
        for e in (cls.elts if isinstance(cls, (ast.Tuple, ast.List)) else [cls]):
            nm = self._dotted(e)
            if (nm in _ISINSTANCE_TYPES and nm not in self.imports
                    and nm not in self.env):
                continue
            if self._canon(e) == _CANON_NUMPY + ".ndarray":
                continue
            self.fail(node, "isinstance() against %r, which is not a class this "
                            "can decide" % (nm or type(e).__name__))
        if not ((isinstance(obj, ast.Name) and obj.id in self._none_names)
                or self._is_none_expr(obj)):
            self.fail(node, "isinstance() on a value that is not statically None "
                            "-- a lowered value's Python class (float vs "
                            "np.float32, int vs np.int64) is not a compile-time "
                            "fact")
        return Val("false", scalar_t("bool"))

    # ---- inline helper calls (INIT-tier `def`s -> C++ lambdas) --------------
    def _call_helper(self, name, node):
        """Lower a call to an inline INIT-tier helper to a C++ lambda call.

        The helper is monomorphized on its argument TYPES (a distinct lambda per
        (name, arg-type-signature)); the lambda is emitted once into the shared
        _HelperCtx in callee-before-caller order and captured by reference so
        nested helpers resolve. Recursion / mutual recursion / *args / **kwargs /
        keyword-only / positional-only / decorated helpers are rejected."""
        ctx = self.helpers
        fdef = ctx.defs[name]
        a = fdef.args
        if (a.vararg or a.kwarg or a.kwonlyargs
                or getattr(a, "posonlyargs", None)):
            self.fail(node, "helper %r uses *args/**kwargs/kw-only/pos-only "
                            "parameters" % name)
        if fdef.decorator_list:
            self.fail(node, "helper %r is decorated" % name)

        params = [p.arg for p in a.args]
        # defaults align to the TAIL of params; only literals are allowed.
        default_nodes = {}
        if a.defaults:
            for p, dflt in zip(params[len(params) - len(a.defaults):],
                               a.defaults):
                if not isinstance(dflt, ast.Constant):
                    self.fail(node, "helper %r default for %r is not a literal"
                              % (name, p))
                default_nodes[p] = dflt

        # bind call-site arguments: positional, then keyword, then defaults.
        pos = self._pos_args(node)
        if len(pos) > len(params):
            self.fail(node, "helper %r called with too many positional args"
                      % name)
        bound = {}
        for p, arg in zip(params, pos):
            bound[p] = self.expr(arg)
        for kw in node.keywords:
            if kw.arg is None:
                self.fail(node, "helper %r called with **kwargs" % name)
            if kw.arg not in params:
                self.fail(node, "helper %r called with unknown keyword %r"
                          % (name, kw.arg))
            if kw.arg in bound:
                self.fail(node, "helper %r got multiple values for %r"
                          % (name, kw.arg))
            bound[kw.arg] = self.expr(kw.value)
        for p in params:
            if p not in bound:
                if p in default_nodes:
                    bound[p] = self.expr(default_nodes[p])
                else:
                    self.fail(node, "helper %r missing argument %r" % (name, p))

        return self.emit_helper_call(name, fdef, [bound[p] for p in params],
                                     node)

    def emit_helper_call(self, name, fdef, arg_vals, node=None):
        """Emit (dedup) a monomorphised C++ lambda for ``fdef`` given the
        argument Vals ALREADY evaluated (one per positional param, in order) and
        return a Val that calls it.

        Shared by ``_call_helper`` (args bound from the call site) and blessed
        ``Transpile`` lowerings (some args sourced from the env rather than the
        call site, so the AST call node has fewer args than the free fn has
        params). Requires a live helper context (``self.helpers``)."""
        ref = node if node is not None else fdef
        ctx = self.helpers
        if ctx is None:
            self.fail(ref, "helper %r cannot be lowered without a helper context"
                      % name)
        a = fdef.args
        if (a.vararg or a.kwarg or a.kwonlyargs
                or getattr(a, "posonlyargs", None)):
            self.fail(ref, "helper %r uses *args/**kwargs/kw-only/pos-only "
                           "parameters" % name)
        if fdef.decorator_list:
            self.fail(ref, "helper %r is decorated" % name)
        params = [p.arg for p in a.args]
        if len(arg_vals) != len(params):
            self.fail(ref, "helper %r expected %d argument(s), got %d"
                      % (name, len(params), len(arg_vals)))
        arg_types = [v.type for v in arg_vals]
        # rank is only meaningful for arrays; a scalar's incidental rank marker
        # (0 from an env binding vs None from arithmetic) must NOT split the
        # monomorphisation, or a self-call whose arg came from arithmetic would
        # miss the in-progress key and be misread as polymorphic recursion.
        sig = tuple((t.kind, t.dtype, t.rank if t.kind == "array" else None)
                    for t in arg_types)
        key = (name, sig)
        argcodes = ", ".join(v.code for v in arg_vals)
        if key in ctx.in_progress:
            # A call to a helper whose body is still being transpiled. Only a
            # DIRECT self-call of the exact monomorphisation on top of the emit
            # stack is supported (a std::function recursive lambda); anything
            # else is a cross-helper cycle (mutual recursion) -> reject.
            if ctx.emit_stack and ctx.emit_stack[-1] == key and key in ctx.rec:
                mono_name, ret_type = ctx.rec[key]
                return Val("%s(%s)" % (mono_name, argcodes), ret_type)
            self.fail(ref, "helper %r is (mutually) recursive" % name)
        if any(k[0] == name for k in ctx.in_progress):
            # Same helper re-entered with a DIFFERENT argument-type signature
            # while an emission is in flight -> polymorphic recursion (unbounded
            # monomorphisation) -> reject.
            self.fail(ref, "helper %r is polymorphically recursive" % name)
        memo = ctx.generated.get(key)
        if memo is None:
            if _is_self_recursive(fdef):
                memo = self._emit_recursive_helper(name, fdef, params,
                                                   arg_types, key)
            else:
                memo = self._emit_helper(name, fdef, params, arg_types, key)
        mono_name, ret_type = memo
        return Val("%s(%s)" % (mono_name, argcodes), ret_type)

    def _emit_helper(self, name, fdef, params, arg_types, key):
        """Transpile helper `fdef` under the given argument types into a C++
        lambda, append it to the shared ctx (callee-first), and memoise."""
        ctx = self.helpers
        ctx.in_progress.add(key)
        ctx.emit_stack.append(key)
        try:
            sub_env = {p: CppType(t.kind, t.dtype, t.rank, t.code)
                       for p, t in zip(params, arg_types)}
            sub = Transpiler(sub_env, helper_ctx=ctx, imports=self.imports,
                             import_stars=self.import_stars)
            res = sub.run(fdef)
        finally:
            ctx.emit_stack.pop()
            ctx.in_progress.discard(key)
        ret_type = self._unify_returns(fdef, res.returns)
        mono_name = ctx.fresh(name)
        # read-only array params -> const& (calling convention only; byte-exact).
        written = _written_names(fdef)
        sigparts = ", ".join(
            "%s %s" % (_param_ctype(t, fdef, by_ref=(p not in written)), p)
            for p, t in zip(params, arg_types))
        ret_ctype = _param_ctype(ret_type, fdef)
        block = ["    auto %s = [&](%s) -> %s {"
                 % (mono_name, sigparts, ret_ctype)]
        block += ["    " + ln for ln in res.decl_lines]
        block += ["    " + ln for ln in res.body_lines]
        block.append("    };")
        ctx.lines += block
        memo = (mono_name, ret_type)
        ctx.generated[key] = memo
        return memo

    def _emit_recursive_helper(self, name, fdef, params, arg_types, key):
        """Transpile a DIRECTLY self-recursive helper into a named
        ``std::function`` lambda (a plain ``auto`` lambda cannot reference
        itself, and its return type cannot be deduced through the recursive
        call). Only SCALAR-returning recursion is supported.

        The return dtype is the least fixed point of the dtype lattice: seed the
        self-call at the bottom (bool) and re-transpile, promoting the return
        dtype until it stops growing (at most bool->int64->double, so it
        converges in <=3 steps). This keeps a pure-int recurrence (factorial) at
        int64 while promoting a mixed int/float recurrence to double."""
        ctx = self.helpers
        mono_name = ctx.fresh(name)
        # statically split base-case returns (no self-call) from recursive ones.
        ret_nodes = [n for n in ast.walk(fdef) if isinstance(n, ast.Return)]
        base_ret_nodes = set(id(n) for n in ret_nodes
                             if n.value is not None
                             and not _contains_call_to(n.value, name))

        seed = CppType("scalar", "bool", 0)   # lattice bottom
        ret_type = None
        res = None
        for _ in range(4):
            recorded = []       # (return-node-id, CppType) in emission order
            sub_env = {p: CppType(t.kind, t.dtype, t.rank, t.code)
                       for p, t in zip(params, arg_types)}

            def _record(val, _rec=recorded):
                _rec.append((getattr(sub, "_cur_ret_id", None), val.type))
                return ["return %s;" % val.code]

            sub = Transpiler(sub_env, return_handler=_record, helper_ctx=ctx,
                             imports=self.imports,
                             import_stars=self.import_stars)
            ctx.rec[key] = (mono_name, seed)
            ctx.in_progress.add(key)
            ctx.emit_stack.append(key)
            try:
                res = sub.run(fdef)
            finally:
                ctx.emit_stack.pop()
                ctx.in_progress.discard(key)
                ctx.rec.pop(key, None)

            all_types = [t for (_id, t) in recorded]
            if not all_types:
                self.fail(fdef, "recursive helper %r has no value-returning "
                                "`return`" % name)
            if any(t.kind != "scalar" for t in all_types):
                self.fail(fdef, "recursive helper %r must return a scalar" % name)
            base_types = [t for (rid, t) in recorded if rid in base_ret_nodes]
            if not base_types:
                self.fail(fdef, "recursive helper %r has no base case "
                                "(would not terminate)" % name)
            new_dtype = "bool"
            for t in all_types:
                new_dtype = _promote(new_dtype, t.dtype)
            if ret_type is not None and new_dtype == ret_type.dtype:
                break
            ret_type = CppType("scalar", new_dtype, 0)
            seed = ret_type
        else:
            self.fail(fdef, "recursive helper %r return type did not converge"
                      % name)

        # read-only array params -> const& in BOTH the lambda param list and the
        # std::function<...> signature (they must match). Byte-exact: values read
        # are identical, only the calling convention changes.
        written = _written_names(fdef)
        sigparts = ", ".join(
            "%s %s" % (_param_ctype(t, fdef, by_ref=(p not in written)), p)
            for p, t in zip(params, arg_types))
        sigtypes = ", ".join(
            _param_ctype(t, fdef, by_ref=(p not in written))
            for p, t in zip(params, arg_types))
        ret_ctype = _param_ctype(ret_type, fdef)
        block = ["    std::function<%s(%s)> %s;" % (ret_ctype, sigtypes,
                                                    mono_name),
                 "    %s = [&](%s) -> %s {" % (mono_name, sigparts, ret_ctype)]
        block += ["    " + ln for ln in res.decl_lines]
        block += ["    " + ln for ln in res.body_lines]
        block.append("    };")
        ctx.lines += block
        memo = (mono_name, ret_type)
        ctx.generated[key] = memo
        return memo

    def _unify_returns(self, fdef, returns):
        """Single CppType for a helper's return, unifying every observed
        `return`. Kinds must match; scalar dtypes promote (C++ converts); array
        returns of differing dtype/rank are rejected (fail-closed)."""
        if not returns:
            self.fail(fdef, "helper %r has no value-returning `return`"
                      % fdef.name)
        kind = returns[0].kind
        dtype = returns[0].dtype
        rank = returns[0].rank
        for t in returns[1:]:
            if t.kind != kind:
                self.fail(fdef, "helper %r returns mixed kinds (%s vs %s)"
                          % (fdef.name, kind, t.kind))
            if kind == "array" and t.dtype != dtype:
                self.fail(fdef, "helper %r returns arrays of differing dtype"
                          % fdef.name)
            dtype = _promote(dtype, t.dtype)
            if t.rank != rank:
                rank = None
        return CppType(kind, dtype, rank)

    def _pos_args(self, node):
        if any(isinstance(a, ast.Starred) for a in node.args):
            self.fail(node, "*args unpacking")
        return node.args

    def _kw(self, node, name):
        for k in node.keywords:
            if k.arg == name:
                return k.value
        return None

    def _kw_dtype(self, node):
        d = self._kw(node, "dtype")
        if d is None:
            return None
        return self._dtype_of(d, node)

    def _dtype_of(self, node, ctx):
        # Keyed on the CANONICAL origin, so np.float64 / numpy.float64 /
        # `from numpy import float64` are one entry rather than three spellings.
        name = self._canon(node)
        _np = _CANON_NUMPY + "."
        table = {
            "int": "int64", "int64": "int64", "int32": "int64",
            _np + "intp": "int64", _np + "int_": "int64",
            "float": "double", _np + "float64": "double",
            _np + "float32": "double",
            _np + "double": "double", "float64": "double",
            "bool": "bool", _np + "bool_": "bool",
        }
        # Integer subtypes (signed + unsigned, all widths) collapse to int64.
        #
        # This is a DELIBERATE, MEASURED deviation from numpy, not a faithful
        # mapping: numpy wraps at the authored width and nd:: does not. uint8
        # 200+200 is 144 in numpy and 400 here; int32 2e9+2e9 is -294967296 in
        # numpy and 4000000000 here. Nothing downstream detects it -- the parity
        # gate is tolerance-based and a wrapped value is not a small error.
        # test_dtype_width_deviation pins both cases so the divergence stays a
        # known deviation rather than a discovery. Narrowing the lattice to fix
        # it was measured and REJECTED: it makes parity worse elsewhere (float32
        # nd::matmul at K=100 goes from exactly 0.0 to 7.391e-04, outside the
        # 1e-4 gate) for a whole-node payoff of ~1.0x-1.1x.
        for _w in ("8", "16", "32", "64"):
            for _p in (_np, ""):
                table[_p + "uint" + _w] = "int64"
                table[_p + "int" + _w] = "int64"
        table[_np + "uint"] = "int64"
        # dtype="int32": ndio.py's own docstring advertises the STRING spelling
        # (ndio.py:28), but _canon returns None for a string constant -- it is
        # not a dotted name -- so this used to hard-reject and drop the whole
        # node to the AI porter. Resolve it to the key np.int32 already uses.
        if name is None and isinstance(node, ast.Constant) \
                and isinstance(node.value, str):
            name = node.value if node.value in table else _np + node.value
        if name in table:
            return table[name]
        self.fail(ctx, "unsupported dtype %r" % (self._dotted(node) or name,))

    def _ndio_raw_desc(self, node, ctx):
        """(kind, itemsize) describing how the FILE's bytes are laid out.

        Separate from _dtype_of on purpose: that returns the PROMOTED lattice
        entry, which has already thrown away the authored width. A headerless
        buffer carries no type, so the width has to come from the spelling the
        author wrote. See _NDIO_RAW."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            name = node.value
        else:
            name = self._canon(node)
            _np = _CANON_NUMPY + "."
            if name is not None and name.startswith(_np):
                name = name[len(_np):]
        if name in _NDIO_RAW:
            return _NDIO_RAW[name]
        self.fail(ctx, "no raw byte layout for dtype %r"
                       % (self._dotted(node) or name,))

    # ---- numpy free functions ----------------------------------------------
    # ---- ndio.* (named array file IO) --------------------------------------
    def _str_arg(self, node, ctx, what):
        """An argument that must lower to a C++ ``std::string`` -- a literal or a
        string-typed value (a string INPUT plug, or a concatenation of them)."""
        v = self.expr(node)
        if v.type.kind != "str":
            self.fail(ctx, "%s must be a string" % what)
        return v.code

    def _call_ndio(self, fn, node):
        args = self._pos_args(node)
        self.uses_ndio = True
        if fn == "read":
            self._need(node, args, 1)
            if len(args) > 2:
                self.fail(node, "ndio.read(path[, name], dtype=...)")
            path = self._str_arg(args[0], node, "ndio.read path")
            name = (self._str_arg(args[1], node, "ndio.read name")
                    if len(args) == 2 else 'std::string("")')
            dt = self._kw_dtype(node) or "double"
            return Val("nd_io_read_named<%s>(_ndioCache, _ndioMutex, %s, %s)"
                       % (_CTYPE[dt], path, name), array_t(dt, None))
        if fn == "read_raw":
            self._need(node, args, 1)
            if len(args) > 2:
                self.fail(node, "ndio.read_raw(path, dtype=...)")
            path = self._str_arg(args[0], node, "ndio.read_raw path")
            # dtype may be positional (arg 1) or keyword; a raw buffer has no
            # header, so it is REQUIRED -- defaulting would silently pick an
            # interpretation and hand back plausible garbage.
            dnode = self._kw(node, "dtype")
            if dnode is None and len(args) == 2:
                dnode = args[1]
            if dnode is None:
                self.fail(node, "ndio.read_raw needs an explicit dtype")
            dt = self._dtype_of(dnode, node)
            kind, size = self._ndio_raw_desc(dnode, node)
            return Val("nd_io_read_raw<%s>(_ndioCache, _ndioMutex, %s, '%s', %d)"
                       % (_CTYPE[dt], path, kind, size), array_t(dt, 1))
        if fn == "write_raw":
            self._need(node, args, 2)
            path = self._str_arg(args[0], node, "ndio.write_raw path")
            src = self.expr(args[1])
            if not src.type.is_array():
                self.fail(node, "ndio.write_raw of a non-array")
            return Val("nd_io_write_raw(%s, %s)" % (path, src.code),
                       scalar_t("bool"))
        if fn == "write":
            self._need(node, args, 1)
            if len(args) > 1:
                self.fail(node, "ndio.write(path, name=array, ...) -- the arrays "
                                "are keyword arguments")
            if not node.keywords:
                self.fail(node, "ndio.write with no arrays to write")
            path = self._str_arg(args[0], node, "ndio.write path")
            # Evaluate every array BEFORE opening the writer block so any nested
            # temp decl lands outside it and stays in scope.
            packed = []
            for kw in node.keywords:
                if not kw.arg:
                    self.fail(node, "ndio.write(**kwargs) unpacking")
                v = self.expr(kw.value)
                if not v.type.is_array():
                    self.fail(node, "ndio.write %r is not an array" % kw.arg)
                packed.append((kw.arg, v.code))
            out = self._new_tmp("ndio_ok")
            wr = self._new_tmp("ndio_w")
            self.emit("bool %s = false;" % out)
            self.emit("{")
            self.emit("    NdIoWriter %s;" % wr)
            for name, code in packed:
                self.emit('    nd_io_writer_add(%s, std::string(%s), %s);'
                          % (wr, self._cpp_str_lit(name, node), code))
            self.emit("    %s = nd_io_writer_finish(%s, %s);" % (out, wr, path))
            self.emit("}")
            return Val(out, scalar_t("bool"))
        if fn == "frame_path":
            # ('mesh.####.json', frame) -> 'mesh.0007.json'. The ONE string
            # operation a compiled compute needs and cannot otherwise express:
            # str()/%/f-strings are all outside the lowerable surface, so a
            # file-per-frame sequence would be interpreted-only without it.
            self._need(node, args, 2)
            if len(args) > 2:
                self.fail(node, "ndio.frame_path(template, frame)")
            tmpl = self._str_arg(args[0], node, "ndio.frame_path template")
            fr = self.expr(args[1])
            if not fr.type.is_scalar():
                self.fail(node, "ndio.frame_path frame must be a number")
            return Val("nd_io_frame_path(%s, (double)(%s))" % (tmpl, fr.code),
                       str_t())
        if fn == "keys":
            # Returns a LIST of strings; the type lattice has no list kind.
            self.fail(node, "ndio.keys() returns a list (no compiled equivalent) "
                            "-- read each array by name instead")
        self.fail(node, "unsupported ndio.%s()" % fn)

    def _call_numpy(self, fn, node):
        args = self._pos_args(node)
        # file IO -----------------------------------------------------------
        # np.load is NOT here on purpose: it has no dtype argument, so the
        # element type is whatever the file happens to hold, while nd::Array<T>
        # must fix T at compile time. Guessing would silently reinterpret an
        # int32 asset as double. spec_extractor blocks it and points at
        # ndio.read(path), which names the dtype explicitly.
        if fn == "fromfile":
            self._need(node, args, 1)
            for bad in ("count", "sep", "offset"):
                if self._kw(node, bad) is not None:
                    self.fail(node, "np.fromfile(%s=...) is not lowered" % bad)
            if len(args) > 2:
                self.fail(node, "np.fromfile(path, dtype=...)")
            path = self._str_arg(args[0], node, "np.fromfile path")
            dnode = self._kw(node, "dtype")
            if dnode is None and len(args) == 2:
                dnode = args[1]
            if dnode is None:
                self.fail(node, "np.fromfile needs an explicit dtype (a raw "
                                "buffer carries no type)")
            dt = self._dtype_of(dnode, node)
            kind, size = self._ndio_raw_desc(dnode, node)
            self.uses_ndio = True
            return Val("nd_io_read_raw<%s>(_ndioCache, _ndioMutex, %s, '%s', %d)"
                       % (_CTYPE[dt], path, kind, size), array_t(dt, 1))
        if fn == "save":
            self._need(node, args, 2)
            path = self._str_arg(args[0], node, "np.save path")
            src = self.expr(args[1])
            if not src.type.is_array():
                self.fail(node, "np.save of a non-array")
            self.uses_ndio = True
            return Val("nd_io_write_npy(nd_io_npy_path(%s), %s)"
                       % (path, src.code), scalar_t("bool"))
        # constructors ------------------------------------------------------
        if fn in ("zeros", "ones", "empty"):
            self._need(node, args, 1)
            dt = self._kw_dtype(node) or "double"
            shp = self._shape_arg(args[0])
            maker = {"zeros": "zeros", "ones": "ones", "empty": "zeros"}[fn]
            return Val("nd::%s<%s>(%s)" % (maker, _CTYPE[dt], shp),
                       array_t(dt, self._shape_rank(args[0])))
        if fn == "full":
            self._need(node, args, 2)
            fill = self.expr(args[1])
            dt = self._kw_dtype(node) or fill.type.dtype
            return Val("nd::full<%s>(%s, (%s)(%s))"
                       % (_CTYPE[dt], self._shape_arg(args[0]), _CTYPE[dt],
                          self._cast_scalar(fill, dt)),
                       array_t(dt, self._shape_rank(args[0])))
        if fn in ("zeros_like", "ones_like", "empty_like"):
            self._need(node, args, 1)
            src = self.expr(args[0])
            if not src.type.is_array():
                self.fail(node, "%s of a non-array" % fn)
            dt = self._kw_dtype(node) or src.type.dtype
            maker = {"zeros_like": "zeros", "ones_like": "ones",
                     "empty_like": "zeros"}[fn]
            return Val("nd::%s<%s>(%s.shape)" % (maker, _CTYPE[dt], src.code),
                       array_t(dt, src.type.rank))
        if fn == "full_like":
            self._need(node, args, 2)
            src = self.expr(args[0])
            fill = self.expr(args[1])
            dt = self._kw_dtype(node) or src.type.dtype
            return Val("nd::full<%s>(%s.shape, (%s)(%s))"
                       % (_CTYPE[dt], src.code, _CTYPE[dt],
                          self._cast_scalar(fill, dt)), array_t(dt, src.type.rank))
        if fn in ("eye", "identity"):
            self._need(node, args, 1)
            return Val("nd::eye(%s)" % self._int_arg(args[0]), array_t("double", 2))
        if fn == "arange":
            return self._np_arange(args, node)
        if fn == "linspace":
            if not (2 <= len(args) <= 3):
                self.fail(node, "linspace(start, stop[, num])")
            num = self._int_arg(args[2]) if len(args) == 3 else "50"
            ep = self._kw(node, "endpoint")
            eps = "true"
            if ep is not None:
                eps = self._as_bool(self.expr(ep), node)
            return Val("nd::linspace((double)(%s), (double)(%s), %s, %s)"
                       % (self._scalar_dbl(args[0]), self._scalar_dbl(args[1]),
                          num, eps), array_t("double", 1))
        # asanyarray differs from asarray only in how it treats ndarray
        # SUBCLASSES, which the lowered form has none of -- so it is the same op.
        if fn in ("array", "asarray", "asanyarray"):
            return self._np_array(args, node, fn)
        if fn == "expand_dims":
            self._need(node, args, 1)
            ax = self._kw(node, "axis") or (args[1] if len(args) > 1 else None)
            if ax is None:
                self.fail(node, "expand_dims needs axis")
            src = self.expr(args[0])
            rank = None if src.type.rank is None else src.type.rank + 1
            return Val("nd::newaxis(%s, %s)"
                       % (self._to_any_array(src, node), self._int_arg(ax)),
                       array_t(src.type.dtype, rank))
        # ndarray operations -------------------------------------------------
        # Routed through the SHARED table so np.f(a, ...) and a.f(...) reach ONE
        # lowering and cannot drift apart (see _ARRAY_OPS). Membership is tested
        # before args[0] is evaluated so a non-ndarray name falls through to the
        # free-only chain below untouched.
        if fn in _ARRAY_OP_REJECTS:
            self._array_op(fn, None, args, node, "free")     # always raises
        if fn in _ARRAY_OPS or (fn, "free") in _ARRAY_OPS_BY_SPELLING:
            self._need(node, args, 1)
            val = self._array_op(fn, self.expr(args[0]), args[1:], node, "free")
            if val is not None:
                return val
        # ufuncs ------------------------------------------------------------
        uf = {"sin": "sin", "cos": "cos", "tan": "tan", "arcsin": "asin",
              "arccos": "acos", "arctan": "atan", "exp": "exp", "log": "log",
              "sqrt": "sqrt", "abs": "fabs", "absolute": "fabs", "fabs": "fabs",
              "floor": "floor", "ceil": "ceil", "sign": "sign",
              "tanh": "tanh", "radians": "radians", "degrees": "degrees",
              "deg2rad": "radians", "rad2deg": "degrees"}
        if fn in uf:
            self._need(node, args, 1)
            a = self.expr(args[0])
            if a.type.is_scalar():
                return self._scalar_ufunc(uf[fn], a)
            v = Val("nd::%s(%s)" % (uf[fn], a.code),
                    array_t("double", a.type.rank))
            if a.type.rank is not None:
                fa = self._fuse_operand(a)
                if fa is not None:
                    v.fuse = FuseNode(
                        "op",
                        emit=lambda vs, _nd=uf[fn]: self._scalar_ufunc(_nd, vs[0]),
                        children=[fa])
            return v
        if fn == "cross":
            self._need(node, args, 2)
            a, b = self.expr(args[0]), self.expr(args[1])
            dt = _promote(a.type.dtype, b.type.dtype)
            return Val("nd::cross(%s, %s)" % (self._to_array_dtype(a, dt),
                                              self._to_array_dtype(b, dt)),
                       array_t(dt, 1))
        if fn == "matmul":
            self._need(node, args, 2)
            return self._matmul(self.expr(args[0]), self.expr(args[1]), node)
        if fn == "diag":
            self._need(node, args, 1)
            a = self.expr(args[0])
            if not a.type.is_array() or a.type.rank is None:
                self.fail(node, "np.diag needs an array of statically known rank")
            if a.type.rank == 1:
                orank = 2
            elif a.type.rank == 2:
                orank = 1
            else:
                self.fail(node, "np.diag needs a 1-D or 2-D array")
            return Val("nd::diag(%s)" % a.code, array_t(a.type.dtype, orank))
        if fn == "linalg.det":
            self._need(node, args, 1)
            a = self.expr(args[0])
            if not a.type.is_array() or a.type.rank is None:
                self.fail(node, "np.linalg.det needs an array of statically "
                                "known rank")
            if a.type.rank < 2:
                self.fail(node, "np.linalg.det needs a (...,N,N) array")
            return Val("nd::det(%s)" % self._to_array_dtype(a, "double"),
                       array_t("double", a.type.rank - 2))
        if fn == "linalg.inv":
            self._need(node, args, 1)
            a = self.expr(args[0])
            if not a.type.is_array() or a.type.rank is None:
                self.fail(node, "np.linalg.inv needs an array of statically "
                                "known rank")
            if a.type.rank < 2:
                self.fail(node, "np.linalg.inv needs a (...,N,N) array")
            return Val("nd::inv(%s)" % self._to_array_dtype(a, "double"),
                       array_t("double", a.type.rank))
        if fn == "linalg.solve":
            self._need(node, args, 2)
            a = self.expr(args[0])
            b = self.expr(args[1])
            if not a.type.is_array() or a.type.rank is None \
                    or not b.type.is_array() or b.type.rank is None:
                self.fail(node, "np.linalg.solve needs arrays of statically "
                                "known rank")
            if a.type.rank != 2:
                self.fail(node, "np.linalg.solve is lowered for a single (N,N) "
                                "matrix; a BATCHED (...,N,N) solve is not")
            if b.type.rank not in (1, 2):
                self.fail(node, "np.linalg.solve right-hand side must be (N,) "
                                "or (N,K)")
            return Val("nd::solve(%s, %s)"
                       % (self._to_array_dtype(a, "double"),
                          self._to_array_dtype(b, "double")),
                       array_t("double", b.type.rank))
        if fn == "einsum":
            return self._np_einsum(args, node)
        if fn == "linalg.svd":
            self.fail(node, "np.linalg.svd must be tuple-unpacked: "
                            "U, S, Vt = np.linalg.svd(a)")
        if fn in ("maximum", "minimum"):
            self._need(node, args, 2)
            kind = "Max" if fn == "maximum" else "Min"
            return self._array_binop(kind, self.expr(args[0]),
                                     self.expr(args[1]), node)
        if fn == "linalg.norm":
            return self._linalg_norm(args, node)
        if fn.startswith("random."):
            self.fail(node, "np.random.%s (use RandomState(seed).random(...))"
                      % fn.split(".", 1)[1])
        # ---- P1 selection / join / gather (SP-5) --------------------------
        if fn == "where":
            return self._np_where(args, node)
        if fn == "select":
            return self._np_select(args, node)
        if fn == "concatenate":
            axis = self._kw(node, "axis")
            if axis is None and len(args) > 1:
                axis = args[1]
            axcode = self._int_arg(axis) if axis is not None else "0"
            dt, vec, rank = self._join_vec(args, node, fn)
            return Val("nd::concatenate(%s, %s)" % (vec, axcode), array_t(dt, rank))
        if fn == "stack":
            axis = self._kw(node, "axis")
            if axis is None and len(args) > 1:
                axis = args[1]
            axcode = self._int_arg(axis) if axis is not None else "0"
            dt, vec, rank = self._join_vec(args, node, fn)
            orank = None if rank is None else rank + 1
            return Val("nd::stack(%s, %s)" % (vec, axcode), array_t(dt, orank))
        if fn == "hstack":
            dt, vec, rank = self._join_vec(args, node, fn)
            return Val("nd::hstack(%s)" % vec, array_t(dt, rank))
        if fn == "vstack":
            dt, vec, rank = self._join_vec(args, node, fn)
            orank = None if rank is None else max(2, rank)
            return Val("nd::vstack(%s)" % vec, array_t(dt, orank))
        if fn == "column_stack":
            dt, vec, _rank = self._join_vec(args, node, fn)
            return Val("nd::column_stack(%s)" % vec, array_t(dt, 2))
        if fn == "tile":
            return self._np_tile(args, node)
        if fn == "roll":
            return self._np_roll(args, node)
        # ---- SP-7 gap-fill ------------------------------------------------
        # Spellings that are pure ALIASES of an operator get rewritten to the
        # operator instead of a new kernel: that preserves numpy's dtype rules
        # (np.negative on an int array stays int) and inherits the existing
        # broadcast + fusion paths for free.
        if fn == "negative":
            self._need(node, args, 1)
            # Rewritten to the AST for `-x` (same idiom as np.select below) so
            # it reuses ex_UnaryOp's dtype rules and fusion rather than forking.
            return self.expr(ast.copy_location(
                ast.UnaryOp(op=ast.USub(), operand=args[0]), node))
        if fn in ("add", "subtract", "multiply", "divide", "true_divide"):
            self._need(node, args, 2)
            kind = {"add": "Add", "subtract": "Sub", "multiply": "Mul",
                    "divide": "Div", "true_divide": "Div"}[fn]
            return self._array_binop(kind, self.expr(args[0]),
                                     self.expr(args[1]), node)
        # elementwise -> bool
        if fn in ("isnan", "isinf", "isfinite"):
            self._need(node, args, 1)
            a = self.expr(args[0])
            return Val("nd::%s(%s)" % (fn, self._to_array_dtype(a, "double")),
                       array_t("bool", a.type.rank if a.type.is_array() else 0))
        if fn == "isclose":
            self._need(node, args, 2)
            a, b = self.expr(args[0]), self.expr(args[1])
            ra = a.type.rank if a.type.is_array() else 0
            rb = b.type.rank if b.type.is_array() else 0
            rank = None if (ra is None or rb is None) else max(ra, rb)
            return Val("nd::isclose(%s, %s, %s, %s)"
                       % (self._to_array_dtype(a, "double"),
                          self._to_array_dtype(b, "double"),
                          self._tol_kw(node, "rtol", "1e-5"),
                          self._tol_kw(node, "atol", "1e-8")),
                       array_t("bool", rank))
        if fn == "allclose":
            self._need(node, args, 2)
            return Val("nd::allclose(%s, %s, %s, %s)"
                       % (self._to_array_dtype(self.expr(args[0]), "double"),
                          self._to_array_dtype(self.expr(args[1]), "double"),
                          self._tol_kw(node, "rtol", "1e-5"),
                          self._tol_kw(node, "atol", "1e-8")),
                       scalar_t("bool"))
        if fn == "array_equal":
            self._need(node, args, 2)
            return Val("nd::array_equal(%s, %s)"
                       % (self._to_array_dtype(self.expr(args[0]), "double"),
                          self._to_array_dtype(self.expr(args[1]), "double")),
                       scalar_t("bool"))
        if fn == "nan_to_num":
            self._need(node, args, 1)
            a = self.expr(args[0])
            if self._kw(node, "copy") is not None:
                self.fail(node, "np.nan_to_num(copy=...) is not lowered "
                                "(the lowered form is always a copy)")
            parts = [self._to_array_dtype(a, "double")]
            big = "1.7976931348623157e308"
            for kw, dflt in (("nan", "0.0"), ("posinf", big),
                             ("neginf", "-" + big)):
                k = self._kw(node, kw)
                parts.append(self._scalar_dbl(k) if k is not None else dflt)
            return Val("nd::nan_to_num(%s)" % ", ".join(parts),
                       array_t("double", a.type.rank if a.type.is_array() else 0))
        # set-like
        if fn in ("unique", "setdiff1d", "isin", "in1d"):
            for bad in ("return_index", "return_inverse", "return_counts",
                        "assume_unique", "invert"):
                if self._kw(node, bad) is not None:
                    self.fail(node, "np.%s(%s=...) is not lowered" % (fn, bad))
            if fn == "unique":
                self._need(node, args, 1)
                a = self.expr(args[0])
                if not a.type.is_array():
                    self.fail(node, "np.unique of a non-array")
                # Always 1-D: unique flattens whatever the input rank.
                return Val("nd::unique(%s)" % a.code, array_t(a.type.dtype, 1))
            self._need(node, args, 2)
            a, b = self.expr(args[0]), self.expr(args[1])
            if not (a.type.is_array() and b.type.is_array()):
                self.fail(node, "np.%s needs two arrays" % fn)
            dt = _promote(a.type.dtype, b.type.dtype)
            ac = self._to_array_dtype(a, dt)
            bc = self._to_array_dtype(b, dt)
            if fn == "setdiff1d":
                return Val("nd::setdiff1d(%s, %s)" % (ac, bc), array_t(dt, 1))
            # np.isin keeps a's shape; np.in1d is the FLATTENED spelling, so it
            # is 1-D even when a is not -- they are not interchangeable.
            rank = a.type.rank if fn == "isin" else 1
            src = ac if fn == "isin" else "nd::ravel(%s)" % ac
            return Val("nd::isin(%s, %s)" % (src, bc), array_t("bool", rank))
        if fn == "bincount":
            self._need(node, args, 1)
            a = self.expr(args[0])
            if self._kw(node, "weights") is not None:
                self.fail(node, "np.bincount(weights=...) is not lowered")
            ml = self._kw(node, "minlength")
            if ml is None and len(args) > 1:
                ml = args[1]
            return Val("nd::bincount(%s, %s)"
                       % (self._to_array_dtype(a, "int64"),
                          self._int_arg(ml) if ml is not None else "0"),
                       array_t("int64", 1))
        # layout
        if fn == "ascontiguousarray":
            self._need(node, args, 1)
            a = self.expr(args[0])
            if not a.type.is_array():
                self.fail(node, "np.ascontiguousarray of a non-array")
            dt = self._kw_dtype(node) or a.type.dtype
            rank = a.type.rank if a.type.rank else 1
            return Val("nd::ascontiguousarray(%s)" % self._to_array_dtype(a, dt),
                       array_t(dt, rank))
        if fn == "atleast_1d":
            self._need(node, args, 1)
            a = self.expr(args[0])
            rank = (1 if not a.type.is_array()
                    else (None if a.type.rank is None else max(1, a.type.rank)))
            return Val("nd::atleast_1d(%s)"
                       % self._to_array_dtype(a, a.type.dtype),
                       array_t(a.type.dtype, rank))
        if fn == "broadcast_to":
            self._need(node, args, 2)
            a = self.expr(args[0])
            return Val("nd::broadcast_to(%s, %s)"
                       % (self._to_array_dtype(a, a.type.dtype),
                          self._shape_arg(args[1])),
                       array_t(a.type.dtype, self._shape_rank(args[1])))
        if fn in ("flip", "flipud", "fliplr"):
            self._need(node, args, 1)
            a = self.expr(args[0])
            if not a.type.is_array():
                self.fail(node, "np.%s of a non-array" % fn)
            if fn == "flip":
                ax = self._kw(node, "axis")
                if ax is None and len(args) > 1:
                    ax = args[1]
                if ax is None:
                    # np.flip with no axis reverses EVERY axis, which is a
                    # different operation than a single-axis flip.
                    self.fail(node, "np.flip needs an explicit axis (the "
                                    "all-axes form is not lowered)")
                axc = self._int_arg(ax)
            else:
                axc = "0" if fn == "flipud" else "1"
                if a.type.rank is not None and a.type.rank < (
                        1 if fn == "flipud" else 2):
                    self.fail(node, "np.%s needs a %d-D array"
                              % (fn, 1 if fn == "flipud" else 2))
            return Val("nd::flip(%s, %s)" % (a.code, axc),
                       array_t(a.type.dtype, a.type.rank))
        if fn == "diff":
            self._need(node, args, 1)
            a = self.expr(args[0])
            if not a.type.is_array():
                self.fail(node, "np.diff of a non-array")
            for bad in ("prepend", "append"):
                if self._kw(node, bad) is not None:
                    self.fail(node, "np.diff(%s=...) is not lowered" % bad)
            n = self._kw(node, "n")
            if n is None and len(args) > 1:
                n = args[1]
            ax = self._kw(node, "axis")
            if ax is None and len(args) > 2:
                ax = args[2]
            return Val("nd::diff(%s, %s, %s)"
                       % (a.code, self._int_arg(n) if n is not None else "1",
                          self._int_arg(ax) if ax is not None else "-1"),
                       array_t(a.type.dtype, a.type.rank))
        if fn == "pad":
            return self._np_pad(args, node)
        # numeric
        if fn == "outer":
            self._need(node, args, 2)
            a, b = self.expr(args[0]), self.expr(args[1])
            return Val("nd::outer(%s, %s)"
                       % (self._to_array_dtype(a, "double"),
                          self._to_array_dtype(b, "double")),
                       array_t("double", 2))
        if fn == "interp":
            self._need(node, args, 3)
            for bad in ("left", "right", "period"):
                if self._kw(node, bad) is not None:
                    self.fail(node, "np.interp(%s=...) is not lowered" % bad)
            x = self.expr(args[0])
            return Val("nd::interp(%s, %s, %s)"
                       % (self._to_array_dtype(x, "double"),
                          self._to_array_dtype(self.expr(args[1]), "double"),
                          self._to_array_dtype(self.expr(args[2]), "double")),
                       array_t("double", x.type.rank if x.type.is_array() else 0))
        if fn in ("nanmax", "nanmin"):
            self._need(node, args, 1)
            a = self.expr(args[0])
            if self._kw(node, "axis") is not None:
                self.fail(node, "np.%s(axis=...) is not lowered (whole-array "
                                "only)" % fn)
            return Val("nd::%s(%s)" % (fn, self._to_array_dtype(a, "double")),
                       scalar_t("double"))
        if fn in ("append", "delete", "insert"):
            return self._np_edit(fn, args, node)
        if fn == "block":
            # np.block([[A, B], [C, D]]) IS vstack-of-hstacks, so it reuses
            # _join_vec and the existing nd::hstack/nd::vstack rather than
            # getting a kernel (and a second set of shape rules) of its own.
            self._need(node, args, 1)
            rows = args[0]
            if not isinstance(rows, (ast.List, ast.Tuple)) or not rows.elts:
                self.fail(node, "np.block needs a literal non-empty list")
            nested = [isinstance(r, (ast.List, ast.Tuple)) for r in rows.elts]
            if not any(nested):
                dt, vec, rank = self._join_vec([rows], node, "block")
                return Val("nd::hstack(%s)" % vec, array_t(dt, rank))
            if not all(nested):
                self.fail(node, "np.block rows must be uniformly nested")
            rvals = []
            for r in rows.elts:
                rdt, rvec, rrank = self._join_vec([r], node, "block")
                rvals.append(Val("nd::hstack(%s)" % rvec, array_t(rdt, rrank)))
            dt = rvals[0].type.dtype
            for v in rvals[1:]:
                dt = _promote(dt, v.type.dtype)
            ranks = [v.type.rank for v in rvals]
            rank = None if any(x is None for x in ranks) else max(2, max(ranks))
            vec = "std::vector<nd::Array<%s>>{%s}" % (
                _CTYPE[dt], ", ".join(self._to_array_dtype(v, dt) for v in rvals))
            return Val("nd::vstack(%s)" % vec, array_t(dt, rank))
        if fn == "ix_":
            self.fail(node, "np.ix_ builds an open mesh for ADVANCED indexing, "
                            "which is not lowered (use explicit np.take or a "
                            "meshgrid + flat index instead)")
        if fn == "meshgrid":
            self.fail(node, "np.meshgrid must be tuple-unpacked: "
                            "X, Y = np.meshgrid(x, y)")
        if fn == "fill_diagonal":
            self.fail(node, "np.fill_diagonal mutates in place, so it is only "
                            "valid as a statement, not as an expression")
        # explicit P1/P2 rejects with a helpful pointer
        deferred = {
            "argwhere": "SP-5",
            "linalg.pinv": "the AI porter (nd::svd is 3x3-only, so there is no "
                           "general pseudo-inverse to build on)",
        }
        if fn in deferred:
            self.fail(node, "np.%s is deferred to %s" % (fn, deferred[fn]))
        self.fail(node, "np.%s not supported" % fn)

    def _np_edit(self, fn, args, node):
        """np.append / np.delete / np.insert.

        All three share one rule that is easy to miss: with axis omitted numpy
        FLATTENS first and returns 1-D, which is a different shape than the
        same call with axis=0. That branch is explicit here rather than
        defaulted, because silently treating them alike would change the rank.

        np.append needs no kernel -- it IS a concatenate -- so it routes to the
        existing nd::concatenate instead of getting its own.
        """
        self._need(node, args, 2 if fn != "insert" else 3)
        a = self.expr(args[0])
        if not a.type.is_array():
            self.fail(node, "np.%s of a non-array" % fn)
        ax = self._kw(node, "axis")
        if ax is None and fn == "append" and len(args) > 2:
            ax = args[2]
        if ax is None and fn == "delete" and len(args) > 2:
            ax = args[2]
        if ax is None and fn == "insert" and len(args) > 3:
            ax = args[3]
        flat = ax is None
        if not flat and a.type.rank is None:
            self.fail(node, "np.%s with an axis needs a statically known rank"
                      % fn)
        rank = 1 if flat else a.type.rank
        axc = "0" if flat else self._int_arg(ax)
        src = "nd::ravel(%s)" % a.code if flat else a.code

        if fn == "append":
            b = self.expr(args[1])
            if not b.type.is_array():
                self.fail(node, "np.append values must be an array")
            dt = _promote(a.type.dtype, b.type.dtype)
            ac = "nd::ravel(%s)" % self._to_array_dtype(a, dt) if flat \
                else self._to_array_dtype(a, dt)
            bc = "nd::ravel(%s)" % self._to_array_dtype(b, dt) if flat \
                else self._to_array_dtype(b, dt)
            vec = "std::vector<nd::Array<%s>>{%s, %s}" % (_CTYPE[dt], ac, bc)
            return Val("nd::concatenate(%s, %s)" % (vec, axc),
                       array_t(dt, rank))

        obj = self.expr(args[1])
        objc = self._to_array_dtype(obj, "int64")
        if fn == "delete":
            return Val("nd::delete_axis(%s, %s, %s)" % (src, objc, axc),
                       array_t(a.type.dtype, rank))
        vals = self.expr(args[2])
        vc = self._to_array_dtype(vals, a.type.dtype)
        if flat and vals.type.is_array():
            vc = "nd::ravel(%s)" % vc
        return Val("nd::insert_axis(%s, %s, %s, %s)" % (src, objc, vc, axc),
                   array_t(a.type.dtype, rank))

    def _tol_kw(self, node, name, default):
        """rtol/atol as a C++ double expression, or numpy's documented default."""
        k = self._kw(node, name)
        return default if k is None else self._scalar_dbl(k)

    def _np_pad(self, args, node):
        """np.pad(a, pad_width, mode='constant', constant_values=0).

        Only mode='constant' is lowered. The other modes ('edge', 'reflect',
        'wrap', ...) are genuinely different algorithms, not options on this one,
        so they reject rather than silently padding with zeros.

        pad_width's NESTING has to be literal because it encodes how many axes
        are padded, but the individual widths may be live int expressions.
        """
        self._need(node, args, 2)
        a = self.expr(args[0])
        if not a.type.is_array() or a.type.rank is None:
            self.fail(node, "np.pad needs an array of statically known rank")
        mode = self._kw(node, "mode")
        if mode is None and len(args) > 2:
            mode = args[2]
        if mode is not None:
            if not (isinstance(mode, ast.Constant) and mode.value == "constant"):
                self.fail(node, "np.pad only lowers mode='constant'")
        rank = a.type.rank
        pw = args[1]

        def _pair(el):
            if isinstance(el, (ast.Tuple, ast.List)):
                if len(el.elts) != 2:
                    self.fail(node, "np.pad width pairs must be (before, after)")
                return self._int_arg(el.elts[0]), self._int_arg(el.elts[1])
            w = self._int_arg(el)
            return w, w

        if isinstance(pw, (ast.Tuple, ast.List)) and pw.elts \
                and all(isinstance(e, (ast.Tuple, ast.List)) for e in pw.elts):
            if len(pw.elts) != rank:
                self.fail(node, "np.pad got %d width pairs for a %d-D array"
                          % (len(pw.elts), rank))
            pairs = [_pair(e) for e in pw.elts]
        else:
            pairs = [_pair(pw)] * rank
        cv = self._kw(node, "constant_values")
        if cv is None and len(args) > 3:
            cv = args[3]
        if cv is not None and isinstance(cv, (ast.Tuple, ast.List)):
            self.fail(node, "np.pad(constant_values=...) must be a single value")
        val = (self._cast_scalar(self.expr(cv), a.type.dtype)
               if cv is not None else "0")
        return Val("nd::pad_constant(%s, {%s}, {%s}, (%s)(%s))"
                   % (a.code,
                      ", ".join(p[0] for p in pairs),
                      ", ".join(p[1] for p in pairs),
                      _CTYPE[a.type.dtype], val),
                   array_t(a.type.dtype, rank))

    def _np_select(self, args, node):
        """np.select(condlist, choicelist, default=0) -> nested np.where.

        numpy takes the FIRST true condition, so the equivalent nesting is built
        from the BACK: where(c0, v0, where(c1, v1, ... default)). Rewriting to
        np.where AST nodes (rather than emitting nd:: here) reuses where's dtype
        promotion, rank inference and elementwise fusion unchanged.

        The nesting depth IS the list length, so both lists must be literal --
        an opaque sequence has no compile-time length."""
        self._need(node, args, 2)
        conds, choices = args[0], args[1]
        for seq, what in ((conds, "condlist"), (choices, "choicelist")):
            if not isinstance(seq, (ast.List, ast.Tuple)):
                self.fail(node, "np.select %s must be a literal list/tuple "
                                "(its length must be known at compile time)"
                          % what)
        if len(conds.elts) != len(choices.elts):
            self.fail(node, "np.select got %d conditions but %d choices"
                      % (len(conds.elts), len(choices.elts)))
        if not conds.elts:
            self.fail(node, "np.select got no conditions")
        default = self._kw(node, "default")
        if default is None and len(args) > 2:
            default = args[2]
        # numpy's default= is 0 when omitted.
        expr = default if default is not None else ast.Constant(value=0)
        for cond, choice in zip(reversed(conds.elts), reversed(choices.elts)):
            expr = ast.Call(
                func=ast.Attribute(value=ast.Name(id="np", ctx=ast.Load()),
                                   attr="where", ctx=ast.Load()),
                args=[cond, choice, expr], keywords=[])
            ast.copy_location(expr, node)
        ast.fix_missing_locations(expr)
        return self.expr(expr)

    def _np_where(self, args, node):
        if len(args) == 1:
            self.fail(node, "np.where(cond) single-arg form (use np.nonzero)")
        self._need(node, args, 3)
        cond = self.expr(args[0])
        if not cond.type.is_array():
            self.fail(node, "np.where condition must be an array")
        condc = (cond.code if cond.type.dtype == "bool"
                 else "nd::astype<bool>(%s)" % cond.code)
        a = self.expr(args[1])
        b = self.expr(args[2])
        if a.type.kind in _VALUELESS_KINDS or b.type.kind in _VALUELESS_KINDS:
            self.fail(node, "np.where on shape/rng object")
        dt = _promote(a.type.dtype, b.type.dtype)
        ranks = [cond.type.rank]
        if a.type.is_array():
            ranks.append(a.type.rank)
        if b.type.is_array():
            ranks.append(b.type.rank)
        rank = None if any(x is None for x in ranks) else max(ranks)

        def side(v):
            if v.type.is_array():
                return self._to_array_dtype(v, dt)
            return "(%s)(%s)" % (_CTYPE[dt], self._cast_scalar(v, dt))

        v = Val("nd::where(%s, %s, %s)" % (condc, side(a), side(b)),
                array_t(dt, rank))
        fz = self._where_fuse(args[0], a, b, dt, rank)
        if fz is not None:
            v.fuse = fz
        return v

    # Compare operands safe to RE-READ (pure env/const lookups; no self.emit),
    # so building the fused per-element compare never double-emits statements.
    _SAFE_CMP_OPERAND = (ast.Name, ast.Constant)

    def _where_fuse(self, cond_ast, a, b, dt, rank):
        """Phase-2 fusion for np.where(x <cmp> c, <true>, <false>): build a
        FuseNode that emits a per-element ternary `(x <cmp> c) ? <true> : <false>`.
        Byte-identical to the eager nd::where -- C++ `?:` evaluates only the taken
        branch, but each branch is a pure elementwise function of the element, so
        the SELECTED value is unchanged. Returns None (caller keeps plain
        nd::where) unless the condition is a single elementwise comparison whose
        operands re-read without side effects and every branch/operand is a
        fusable leaf."""
        if rank is None or dt == "bool":
            return None
        if not isinstance(cond_ast, ast.Compare):
            return None
        if len(cond_ast.ops) != 1 or type(cond_ast.ops[0]) not in self._CMP_MAP:
            return None
        cleft, cright = cond_ast.left, cond_ast.comparators[0]
        if not (isinstance(cleft, self._SAFE_CMP_OPERAND)
                and isinstance(cright, self._SAFE_CMP_OPERAND)):
            return None
        cl = self.expr(cleft)
        cr = self.expr(cright)
        if cl.type.kind in _OPAQUE_KINDS \
                or cr.type.kind in _OPAQUE_KINDS:
            return None
        fcl = self._fuse_operand_for(cl, rank)
        fcr = self._fuse_operand_for(cr, rank)
        fa = self._fuse_operand_for(a, rank)
        fb = self._fuse_operand_for(b, rank)
        if None in (fcl, fcr, fa, fb):
            return None
        cmp_op = self._CMP_MAP[type(cond_ast.ops[0])]
        cdt = _promote(cl.type.dtype, cr.type.dtype)

        def emit(vs, _op=cmp_op, _cdt=cdt, _dt=dt):
            c_l, c_r, v_a, v_b = vs
            cond_s = "(%s %s %s)" % (self._cast_scalar(c_l, _cdt), _op,
                                     self._cast_scalar(c_r, _cdt))
            return Val("(%s ? %s : %s)"
                       % (cond_s, self._cast_scalar(v_a, _dt),
                          self._cast_scalar(v_b, _dt)), scalar_t(_dt))

        return FuseNode("op", emit=emit, children=[fcl, fcr, fa, fb])

    def _join_vec(self, args, node, fn):
        """Evaluate a literal list/tuple of arrays -> (dtype, C++ vector expr,
        max input rank). Shared by concatenate/stack/hstack/vstack/column_stack."""
        self._need(node, args, 1)
        listnode = args[0]
        if not isinstance(listnode, (ast.List, ast.Tuple)):
            self.fail(node, "np.%s requires a literal list/tuple of arrays" % fn)
        vals = [self.expr(e) for e in listnode.elts]
        if not vals:
            self.fail(node, "np.%s of an empty sequence" % fn)
        for v in vals:
            if not v.type.is_array():
                self.fail(node, "np.%s element is not an array" % fn)
        dt = vals[0].type.dtype
        for v in vals[1:]:
            dt = _promote(dt, v.type.dtype)
        ranks = [v.type.rank for v in vals]
        rank = None if any(x is None for x in ranks) else max(ranks)
        elems = ", ".join(self._to_array_dtype(v, dt) for v in vals)
        vec = "std::vector<nd::Array<%s>>{%s}" % (_CTYPE[dt], elems)
        return dt, vec, rank

    def _np_tile(self, args, node):
        self._need(node, args, 2)
        src = self.expr(args[0])
        if not src.type.is_array():
            self.fail(node, "np.tile of a non-array")
        reps = args[1]
        if isinstance(reps, (ast.Tuple, ast.List)):
            repcode = "nd::Shape{%s}" % ", ".join(self._int_arg(e)
                                                  for e in reps.elts)
            nreps = len(reps.elts)
        else:
            repcode = "nd::Shape{%s}" % self._int_arg(reps)
            nreps = 1
        rank = (None if src.type.rank is None
                else max(src.type.rank, nreps))
        return Val("nd::tile(%s, %s)" % (src.code, repcode),
                   array_t(src.type.dtype, rank))

    def _np_roll(self, args, node):
        self._need(node, args, 2)
        src = self.expr(args[0])
        if not src.type.is_array():
            self.fail(node, "np.roll of a non-array")
        shift = self._int_arg(args[1])
        axis = self._kw(node, "axis")
        if axis is None and len(args) > 2:
            axis = args[2]
        if axis is None or (isinstance(axis, ast.Constant) and axis.value is None):
            return Val("nd::roll(%s, %s)" % (src.code, shift),
                       array_t(src.type.dtype, src.type.rank))
        return Val("nd::roll(%s, %s, %s)" % (src.code, shift, self._int_arg(axis)),
                   array_t(src.type.dtype, src.type.rank))

    def _to_any_array(self, v, node):
        if v.type.is_array():
            return v.code
        self.fail(node, "expected an array operand")

    def _scalar_dbl(self, node):
        v = self.expr(node)
        return self._cast_scalar(v, "double")

    def _np_arange(self, args, node):
        dt = self._kw_dtype(node)
        vals = [self.expr(a) for a in args]
        if not vals or len(vals) > 3:
            self.fail(node, "arange(stop) / arange(start, stop[, step])")
        if dt is None:
            dt = "double" if any(v.type.dtype == "double" for v in vals) else "int64"
        cast = [self._cast_scalar(v, dt) for v in vals]
        return Val("nd::arange<%s>(%s)" % (_CTYPE[dt], ", ".join(cast)),
                   array_t(dt, 1))

    def _np_array(self, args, node, fn):
        self._need(node, args, 1)
        # np.asarray(existing_array) is a no-op passthrough (optional dtype).
        inner = args[0]
        if not isinstance(inner, (ast.List, ast.Tuple)):
            src = self.expr(inner)
            if src.type.is_array():
                dt = self._kw_dtype(node)
                if dt is None or dt == src.type.dtype:
                    return src
                return Val("nd::astype<%s>(%s)" % (_CTYPE[dt], src.code),
                           array_t(dt, src.type.rank))
            self.fail(node, "np.%s of a non-list scalar" % fn)
        if not self._is_const_literal(inner):
            # A literal built from live SCALARS (e.g. the cross-product matrix
            # `np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])`). Same
            # nd::from_data emission as the all-constant path -- only the
            # element expressions differ -- so an all-constant literal keeps
            # its byte-identical output above.
            flat, shape = self._literal_nested_vals(inner, node)
            dt = self._kw_dtype(node)
            if dt is None:
                dt = "bool"
                for v in flat:
                    dt = _promote(dt, v.type.dtype)
            items = ", ".join(self._cast_scalar(v, dt) for v in flat)
            dims = ", ".join(str(d) for d in shape)
            return Val("nd::from_data<%s>({%s}, {%s})"
                       % (_CTYPE[dt], items, dims), array_t(dt, len(shape)))
        flat, shape = self._literal_nested(inner, node)
        dt = self._kw_dtype(node) or self._literal_dtype(flat)
        items = ", ".join(self._literal_item(x, dt) for x in flat)
        dims = ", ".join(str(d) for d in shape)
        return Val("nd::from_data<%s>({%s}, {%s})" % (_CTYPE[dt], items, dims),
                   array_t(dt, len(shape)))

    def _is_const_literal(self, node):
        """True when every leaf of a nested list/tuple literal is a numeric
        constant -- i.e. the original all-constant _literal_nested path applies."""
        if isinstance(node, (ast.List, ast.Tuple)):
            return all(self._is_const_literal(e) for e in node.elts)
        if isinstance(node, ast.Constant):
            return isinstance(node.value, (int, float, bool))
        return (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
                and isinstance(node.operand, ast.Constant)
                and isinstance(node.operand.value, (int, float, bool)))

    def _literal_nested_vals(self, node, ctx):
        """Flatten a nested list/tuple literal -> (flat Vals, shape), where each
        leaf is an arbitrary SCALAR expression rather than a constant."""
        if isinstance(node, (ast.List, ast.Tuple)):
            rows = [self._literal_nested_vals(e, ctx) for e in node.elts]
            if not rows:
                return [], [0]
            first_shape = rows[0][1]
            for _, sh in rows:
                if sh != first_shape:
                    self.fail(ctx, "ragged array literal")
            flat = []
            for f, _ in rows:
                flat.extend(f)
            return flat, [len(node.elts)] + first_shape
        v = self.expr(node)
        if v.type.is_array() and v.type.rank in (0, None):
            v = Val("(%s).item()" % v.code, scalar_t(v.type.dtype))
        if not v.type.is_scalar():
            self.fail(ctx, "array literal element must be a scalar (got an "
                           "array); build it with np.stack / np.concatenate")
        return [v], []

    def _literal_nested(self, node, ctx):
        """Flatten a (possibly nested) list/tuple literal -> (flat_consts, shape)."""
        if isinstance(node, (ast.List, ast.Tuple)):
            rows = [self._literal_nested(e, ctx) for e in node.elts]
            if not rows:
                return [], [0]
            first_shape = rows[0][1]
            for _, sh in rows:
                if sh != first_shape:
                    self.fail(ctx, "ragged array literal")
            flat = []
            for f, _ in rows:
                flat.extend(f)
            return flat, [len(node.elts)] + first_shape
        v = self._const_number(node, ctx)
        return [v], []

    def _const_number(self, node, ctx):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)):
            return node.value
        if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
                and isinstance(node.operand, ast.Constant)):
            return -node.operand.value
        self.fail(ctx, "array literal element must be a numeric constant")

    def _literal_dtype(self, flat):
        if any(isinstance(x, float) for x in flat):
            return "double"
        if any(isinstance(x, bool) for x in flat) and all(isinstance(x, bool) for x in flat):
            return "bool"
        return "int64"

    def _literal_item(self, x, dt):
        if dt == "double":
            return self._float_lit(float(x))
        if dt == "bool":
            return "true" if x else "false"
        return "%d" % int(x)

    def _linalg_norm(self, args, node):
        self._need(node, args, 1)
        src = self.expr(args[0])
        if self._kw(node, "ord") is not None:
            self.fail(node, "np.linalg.norm with ord (only L2 supported)")
        axis = self._kw(node, "axis")
        axes_code, n_axes = self._axes_arg(axis, node)
        # keepdims must be threaded to nd::norm faithfully: keepdims=True keeps a
        # length-1 axis (numpy (N,1)), so a silent drop would misalign every
        # downstream broadcast. Mirrors _reduction: rank is unknown when keepdims
        # is present (True keeps rank, False drops n_axes).
        keep = self._kw(node, "keepdims")
        keeps = "false"
        if keep is not None:
            keeps = self._as_bool(self.expr(keep), node)
        rank = None
        if src.type.rank is not None and keep is None:
            rank = 0 if n_axes is None else max(0, src.type.rank - n_axes)
        return Val("nd::norm(%s, {%s}, %s)" % (src.code, axes_code, keeps),
                   array_t("double", rank))

    def _np_einsum(self, args, node):
        if len(args) < 2:
            self.fail(node, "np.einsum(subscripts, *operands)")
        sub = args[0]
        if not (isinstance(sub, ast.Constant) and isinstance(sub.value, str)):
            self.fail(node, "np.einsum subscripts must be a string literal")
        subs = sub.value
        if "->" not in subs:
            self.fail(node, "np.einsum requires explicit '->' output "
                            "(implicit mode is not supported)")
        # subscripts are restricted to letters / ',' / '->' / spaces so the
        # string embeds safely into a C++ literal with no escaping needed.
        body = subs.replace("->", "").replace(",", "").replace(" ", "")
        if not body.isalpha():
            self.fail(node, "np.einsum subscripts may only use letters, commas "
                            "and '->'")
        ops = [self.expr(a) for a in args[1:]]
        for o in ops:
            if not o.type.is_array():
                self.fail(node, "np.einsum operands must be arrays")
        dt = ops[0].type.dtype
        for o in ops[1:]:
            dt = _promote(dt, o.type.dtype)
        lhs, rhs = subs.split("->", 1)
        out_labels = rhs.replace(" ", "")
        terms = [term.replace(" ", "") for term in lhs.split(",")]
        # Specialized per-subscript contraction loop -- byte-identical to
        # nd::einsum (same output/sum odometer nesting, operand order, and real
        # offset+stride reads via atN) -- when every term is a plain index list
        # of rank 1..4 matching its operand and the output is non-scalar. Anything
        # else (diagonal, rank>4, scalar output) falls back to the nd::einsum
        # runtime, which stays byte-exact.
        spec = self._einsum_specialized(terms, out_labels, ops, dt)
        if spec is not None:
            return spec
        opvec = ", ".join(self._to_array_dtype(o, dt) for o in ops)
        return Val('nd::einsum(std::string("%s"), std::vector<nd::Array<%s>>{%s})'
                   % (subs, _CTYPE[dt], opvec),
                   array_t(dt, len(out_labels)))

    def _einsum_specialized(self, terms, out_labels, ops, dt):
        """Emit a specialized scalar contraction loop for a fixed einsum
        subscript, byte-identical to nd::einsum, or return None to fall back.

        Modelled: each term is a plain (non-diagonal) index list whose length
        equals its operand's rank (1..4), and the output has >=1 label. The nest
        loops output labels outermost (C-contiguous store order) and sum labels
        (first-seen order) innermost; per output element acc=(T)0, then over the
        sum odometer prodv=(T)1, prodv*=at{rank}(op_t, ...) in OPERAND order,
        acc+=prodv -- exactly nd::einsum's accumulation. Operand elements are read
        through atN, whose offset math (offset + sum idx*strides[p]) is identical
        to nd::einsum's and whose negative-index guard is dead here (all indices
        >=0). Each operand is bound to one const local first (single eval; a view
        operand stays alive and is read via its real strides)."""
        if len(terms) != len(ops) or not out_labels:
            return None
        first_occ = {}
        order = []
        for t, term in enumerate(terms):
            if len(set(term)) != len(term):          # diagonal (repeated label)
                return None
            r = ops[t].type.rank
            if r is None or r != len(term) or not (1 <= len(term) <= 4):
                return None
            for p, lab in enumerate(term):
                if lab not in first_occ:
                    first_occ[lab] = (t, p)
                    order.append(lab)
        if any(lab not in first_occ for lab in out_labels):
            return None
        sum_labels = [lab for lab in order if lab not in out_labels]
        T = _CTYPE[dt]
        uid = self._new_tmp("es")
        op_names = ["%s_op%d" % (uid, t) for t in range(len(ops))]

        def var(lab):
            return "%s_%s" % (uid, lab)

        def extent(lab):
            t, p = first_occ[lab]
            return "%s.shape[%d]" % (op_names[t], p)

        for t, o in enumerate(ops):
            self.emit("const nd::Array<%s> %s = %s;"
                      % (T, op_names[t], self._to_array_dtype(o, dt)))
        osh = ", ".join(extent(lab) for lab in out_labels)
        self.emit("nd::Array<%s> %s = nd::Array<%s>::alloc(nd::Shape{%s});"
                  % (T, uid, T, osh))
        self.emit("%s* %s_dst = %s.data->data();" % (T, uid, uid))
        self.emit("int64_t %s_pos = 0;" % uid)
        for lab in out_labels:
            self.emit("for (int64_t %s = 0; %s < %s; ++%s) {"
                      % (var(lab), var(lab), extent(lab), var(lab)))
            self.indent += 1
        self.emit("%s %s_acc = (%s)0;" % (T, uid, T))
        for lab in sum_labels:
            self.emit("for (int64_t %s = 0; %s < %s; ++%s) {"
                      % (var(lab), var(lab), extent(lab), var(lab)))
            self.indent += 1
        self.emit("%s %s_prod = (%s)1;" % (T, uid, T))
        for t, term in enumerate(terms):
            idxs = ", ".join(var(lab) for lab in term)
            self.emit("%s_prod *= nd::at%d(%s, %s);"
                      % (uid, len(term), op_names[t], idxs))
        self.emit("%s_acc += %s_prod;" % (uid, uid))
        for _lab in sum_labels:
            self.indent -= 1
            self.emit("}")
        self.emit("%s_dst[%s_pos++] = %s_acc;" % (uid, uid, uid))
        for _lab in out_labels:
            self.indent -= 1
            self.emit("}")
        return Val(uid, array_t(dt, len(out_labels)))

    def _axes_arg(self, axis_node, node):
        """-> (comma-separated axis exprs, count) ; count None == reduce-all."""
        if axis_node is None or (isinstance(axis_node, ast.Constant)
                                 and axis_node.value is None):
            return "", None
        if isinstance(axis_node, (ast.Tuple, ast.List)):
            parts = [self._int_arg(e) for e in axis_node.elts]
            return ", ".join(parts), len(parts)
        return self._int_arg(axis_node), 1

    def _scalar_ufunc(self, ndname, a):
        std = {"sin": "std::sin", "cos": "std::cos", "tan": "std::tan",
               "asin": "std::asin", "acos": "std::acos", "atan": "std::atan",
               "exp": "std::exp", "log": "std::log", "sqrt": "std::sqrt",
               "fabs": "std::fabs", "floor": "std::floor", "ceil": "std::ceil",
               "tanh": "std::tanh"}
        if ndname == "sign":
            x = self._cast_scalar(a, "double")
            return Val("(double)(((%s)>0)-((%s)<0))" % (x, x), scalar_t("double"))
        # numpy's deg/rad conversions are a plain multiply by a rounded literal,
        # so the scalar form has to use the SAME constant as nd::radians to stay
        # bit-identical with the array form (and with the fused form).
        if ndname in ("radians", "degrees"):
            k = ("0.017453292519943295" if ndname == "radians"
                 else "57.29577951308232")
            return Val("((double)(%s) * %s)"
                       % (self._cast_scalar(a, "double"), k), scalar_t("double"))
        return Val("%s((double)(%s))" % (std[ndname], self._cast_scalar(a, "double")),
                   scalar_t("double"))

    # ---- RandomState detection ---------------------------------------------
    def _as_randomstate(self, node):
        """If node is `np.random.RandomState(seed)`, return a C++ seed stmt
        template with a single %s slot for the target variable name; else None."""
        if not (isinstance(node, ast.Call)
                and self._canon(node.func)
                == "%s.random.RandomState" % _CANON_NUMPY):
            return None
        args = self._pos_args(node)
        if len(args) != 1:
            self.fail(node, "RandomState(seed) takes one seed")
        seed = self.expr(args[0])
        if not seed.type.is_scalar():
            self.fail(node, "RandomState array seed (only scalar int supported)")
        return "%%s.seed((uint32_t)(%s));" % self._cast_scalar(seed, "int64")

    # ---- scipy.spatial.cKDTree ---------------------------------------------
    #
    # The tie rule is nd_runtime's, not scipy's: a neighbour is ordered by
    # (distance, index), so equidistant candidates resolve to the LOWEST index --
    # the same convention nd::argmin uses. scipy's own answer on a tie falls out
    # of its tree layout, is undefined by its API, and moves with the scipy
    # version (three are reachable on this machine), so it is not a target worth
    # matching. See the KDTree block in nd_runtime.h.

    _KDTREE_ORIGINS = ("scipy.spatial.cKDTree", "scipy.spatial.KDTree",
                       "scipy.spatial.kdtree.KDTree",
                       "scipy.spatial.ckdtree.cKDTree")

    def _reject_unbound_kdtree(self, node):
        """A cKDTree(...) in a position that is neither `name = cKDTree(...)`
        nor the receiver of a query (`cKDTree(pts).query(x)`).

        The tree has no value semantics, so it cannot be passed around, stored,
        or returned -- it can only be built and queried. Without this the
        generic path reports "unknown function 'cKDTree'", which points at the
        import rather than at the real problem.
        """
        if (isinstance(node, ast.Call)
                and self._canon(node.func) in self._KDTREE_ORIGINS):
            self.fail(node, "cKDTree(...) may only be built and queried: bind "
                            "it (`tree = cKDTree(pts)`) or query it inline "
                            "(`d, i = cKDTree(pts).query(x)`)")

    def _kdtree_recv(self, node):
        """Evaluate a `.query*` receiver that may be an inline `cKDTree(...)`.

        `tree = cKDTree(pts)` binds a named local, but the chained spelling
        `cKDTree(pts).query(x)` -- the one scipy's own docs use -- has no name
        to bind, so the tree is materialised into a temporary. The temporary is
        emitted as a statement of the ENCLOSING block, which is exactly the
        lifetime the Python temporary has: built on entry, dropped on exit.

        Everything that is not a cKDTree call falls through to the normal
        expression path unchanged.
        """
        kd = self._as_kdtree(node)
        if kd is None:
            return self.expr(node)
        tmp = self._new_tmp("kdt")
        self.emit("nd::KDTree %s = %s;" % (tmp, kd))
        return Val(tmp, kdtree_t())

    def _as_kdtree(self, node):
        """`cKDTree(pts)` -> the C++ build expression, else None."""
        if not isinstance(node, ast.Call):
            return None
        if self._canon(node.func) not in self._KDTREE_ORIGINS:
            return None
        args = self._pos_args(node)
        self._need(node, args, 1)
        for bad in ("boxsize", "compact_nodes", "balanced_tree", "copy_data"):
            if self._kw(node, bad) is not None:
                self.fail(node, "cKDTree(%s=...) is not lowered" % bad)
        pts = self.expr(args[0])
        if not pts.type.is_array() or pts.type.rank not in (2, None):
            self.fail(node, "cKDTree needs an (M, D) array")
        leaf = self._kw(node, "leafsize")
        if leaf is None and len(args) > 1:
            leaf = args[1]
        # leafsize changes only the tree SHAPE. The result is defined by the
        # (distance, index) rule, so it cannot change the answer -- it is
        # accepted and honoured purely so a port reads the same as its source.
        leaf_c = self._int_arg(leaf) if leaf is not None else "16"
        return "nd::kdtree(%s, %s)" % (self._to_array_dtype(pts, "double"),
                                       leaf_c)

    def _kdtree_method(self, attr, recv, args, node):
        if attr == "query":
            self.fail(node, "tree.query() returns (distances, indices) and must "
                            "be tuple-unpacked: d, i = tree.query(x)")
        if attr == "query_ball_point":
            self.fail(node, "tree.query_ball_point() returns ragged lists and "
                            "must be unpacked as starts, items = "
                            "tree.query_ball_point(x, r) -- a CSR pair")
        if attr == "query_pairs":
            self._need(node, args, 1)
            for bad in ("eps", "p"):
                if self._kw(node, bad) is not None:
                    self.fail(node, "query_pairs(%s=...) is not lowered" % bad)
            # scipy DEFAULTS output_type to 'set' -- a Python set of tuples,
            # which has no lowered carrier. Requiring the ndarray form
            # explicitly is what keeps the compiled result the same OBJECT as
            # the interpreted one; defaulting it silently would make the two
            # sides return different types.
            ot = self._kw(node, "output_type")
            if ot is None:
                self.fail(node, "query_pairs() defaults to a Python set, which "
                                "has no lowered form -- pass "
                                "output_type='ndarray'")
            # Compared on the AST, not on the lowered code: _str_arg returns a
            # C++ expression, so a literal never equals the bare word.
            if not (isinstance(ot, ast.Constant) and ot.value == "ndarray"):
                self.fail(node, "query_pairs(output_type=...) must be the "
                                "literal 'ndarray'")
            return Val("nd::kd_query_pairs(%s, %s)"
                       % (recv.code, self._scalar_dbl(args[0])),
                       array_t("int64", 2))
        self.fail(node, "cKDTree method .%s is not lowered (query / "
                        "query_ball_point / query_pairs only)" % attr)

    def _is_kdtree_query(self, node, which):
        """`<tree>.<which>(...)`, where <tree> is a bound local OR an inline
        `cKDTree(...)`.

        Matched off the ENV / the AST rather than by evaluating the receiver,
        because this runs during assignment dispatch -- before the unpack is
        lowered -- and evaluating twice would emit the build expression twice.
        """
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == which):
            return False
        recv = node.func.value
        if isinstance(recv, ast.Call):
            return self._canon(recv.func) in self._KDTREE_ORIGINS
        if not isinstance(recv, ast.Name):
            return False
        t = self.env.get(recv.id)
        return t is not None and t.kind == "kdtree"

    def _assign_kdtree_query(self, target, call, node):
        """`d, i = tree.query(x[, k])` -> one nd::kd_query, two fields."""
        recv = self._kdtree_recv(call.func.value)
        args = self._pos_args(call)
        self._need(call, args, 1)
        for bad in ("distance_upper_bound", "eps", "p", "workers", "n_jobs"):
            if self._kw(call, bad) is not None:
                self.fail(node, "tree.query(%s=...) is not lowered" % bad)
        if len(target.elts) != 2:
            self.fail(node, "tree.query unpack needs exactly (distances, indices)")
        x = self.expr(args[0])
        if not x.type.is_array() or x.type.rank is None:
            self.fail(node, "tree.query needs a query array of known rank")
        knode = self._kw(call, "k")
        if knode is None and len(args) > 1:
            knode = args[1]
        # k drives the OUTPUT RANK, so it has to be a literal: k=1 collapses the
        # trailing axis (scipy's own shape rule) and k>1 keeps it. A runtime k
        # would leave the rank unknowable at lowering time.
        k = 1
        if knode is not None:
            kv = _static_int(knode)
            if kv is None:
                self.fail(node, "tree.query(k=...) must be a literal int -- k "
                                "decides the result RANK, which is fixed at "
                                "compile time")
            if kv < 1:
                self.fail(node, "tree.query needs k >= 1")
            k = kv
        base = x.type.rank - 1          # (N, D) -> N rows; (D,) -> single point
        orank = base if k == 1 else base + 1
        tmp = self._new_tmp("kdq")
        fn = "nd::kd_query1(%s, %s)" if k == 1 else \
             "nd::kd_query(%s, %s, " + str(k) + ")"
        self.emit("nd::KDQuery %s = %s;"
                  % (tmp, fn % (recv.code, self._to_array_dtype(x, "double"))))
        d, i = target.elts
        self._declare(d.id, array_t("double", orank), node)
        self.emit("%s = %s.dist;" % (self._cpp_local(d.id), tmp))
        self._declare(i.id, array_t("int64", orank), node)
        self.emit("%s = %s.idx;" % (self._cpp_local(i.id), tmp))

    def _assign_kdtree_ball(self, target, call, node):
        """`starts, items = tree.query_ball_point(x, r)` -> a CSR pair.

        A list-of-lists has no dense carrier, so the ragged result is returned
        as CSR: row i is items[starts[i]:starts[i+1]], ascending. That is the
        shape the one real consumer already wants -- it reads the first entry of
        each row as the smallest neighbour index.
        """
        recv = self._kdtree_recv(call.func.value)
        args = self._pos_args(call)
        self._need(call, args, 2)
        for bad in ("p", "eps", "workers", "return_sorted", "return_length"):
            if self._kw(call, bad) is not None:
                self.fail(node, "query_ball_point(%s=...) is not lowered" % bad)
        if len(target.elts) != 2:
            self.fail(node, "tree.query_ball_point unpack needs exactly "
                            "(starts, items) -- a CSR pair")
        x = self.expr(args[0])
        if not x.type.is_array():
            self.fail(node, "tree.query_ball_point needs a query array")
        tmp = self._new_tmp("kdb")
        self.emit("nd::KDBall %s = nd::kd_query_ball_point(%s, %s, %s);"
                  % (tmp, recv.code, self._to_array_dtype(x, "double"),
                     self._scalar_dbl(args[1])))
        s, it = target.elts
        self._declare(s.id, array_t("int64", 1), node)
        self.emit("%s = %s.starts;" % (self._cpp_local(s.id), tmp))
        self._declare(it.id, array_t("int64", 1), node)
        self.emit("%s = %s.items;" % (self._cpp_local(it.id), tmp))

    # ---- method calls: x.method(...) ---------------------------------------
    def _call_method(self, node):
        attr = node.func.attr
        # _kdtree_recv is self.expr for everything that is not an inline
        # cKDTree(...), so this also reaches `cKDTree(p).query_pairs(r)`.
        recv = self._kdtree_recv(node.func.value)
        args = self._pos_args(node)
        # RandomState instance methods
        if recv.type.kind == "rng":
            return self._rng_method(attr, recv, args, node)
        if recv.type.kind == "kdtree":
            return self._kdtree_method(attr, recv, args, node)
        if recv.type.kind == "str":
            if attr != "strip":
                self.fail(node, "string method .%s is not lowered" % attr)
            if args:
                # .strip(chars) strips a SET of characters, not a prefix -- a
                # different operation, and not the one animated labels need.
                self.fail(node, ".strip(chars) is not lowered; only the bare "
                                ".strip()")
            return Val("nd::str_strip(%s)" % recv.code, str_t())
        if not recv.type.is_array():
            self.fail(node, "method .%s on a non-array" % attr)
        val = self._array_op(attr, recv, args, node, "method")
        if val is None:
            self.fail(node, "array method .%s" % attr)
        return val

    # ==== the ndarray operation funnel (see _ARRAY_OPS) ==================
    def _array_op(self, name, recv, args, node, spelling):
        """Lower one ndarray operation, whichever way it was spelled.

        `recv` is the receiver for `a.f(...)` and the first argument for
        `np.f(a, ...)`, so a handler never has to know which spelling it came
        from -- which is exactly what keeps the two from drifting apart.
        Returns None when the name is not an ndarray operation at all, so the
        free-function caller can carry on down its own chain.
        """
        reason = _ARRAY_OP_REJECTS.get(name)
        if reason is not None:
            how = ("a.%s(...)" % name) if spelling == "method" else "np.%s(...)" % name
            self.fail(node, "%s is not lowered: %s" % (how, reason))
        byspell = _ARRAY_OPS_BY_SPELLING.get((name, spelling))
        if byspell is not None:
            return getattr(self, byspell)(recv, args, node)
        spec = _ARRAY_OPS.get(name)
        if spec is not None and spec[1] in ("both", spelling):
            return getattr(self, spec[0])(recv, args, node)
        if spelling == "method" and name in _ARRAY_STMT_OPS:
            self.fail(node, "a.%s(...) mutates IN PLACE and returns None -- use "
                            "it as a statement, not as a value" % name)
        if spec is not None:
            exists = ("np.%s(a, ...)" % name if spec[1] == "free"
                      else "a.%s(...)" % name)
            self.fail(node, "numpy has no %s spelling of %s; the form that "
                            "exists is %s" % (spelling, name, exists))
        return None

    # ---- shape ---------------------------------------------------------
    def _op_reshape(self, recv, args, node):
        shp = self._shape_from_args(args, node)
        return Val("nd::reshape(%s, %s)" % (recv.code, shp[0]),
                   array_t(recv.type.dtype, shp[1]))

    def _op_ravel(self, recv, args, node):
        return Val("nd::ravel(%s)" % self._to_any_array(recv, node),
                   array_t(recv.type.dtype, 1))

    def _op_transpose(self, recv, args, node):
        axnode = self._kw(node, "axes")
        if axnode is None and len(args) == 1 and isinstance(args[0],
                                                            (ast.Tuple, ast.List)):
            axnode = args[0]
        if axnode is not None:
            if not isinstance(axnode, (ast.Tuple, ast.List)):
                self.fail(node, "transpose axes must be a tuple/list literal")
            elts = list(axnode.elts)
        else:
            elts = list(args)
        if not elts:
            return Val("nd::transpose(%s)" % recv.code,
                       array_t(recv.type.dtype, recv.type.rank))
        axvals = []
        for el in elts:
            ax = _static_int(el)
            if ax is not None:
                if ax < 0:
                    # nd::transpose indexes axes[i] directly, so a negative axis
                    # would read out of bounds -- normalise it here.
                    if recv.type.rank is None:
                        self.fail(node, "transpose negative axis needs a "
                                        "statically known rank")
                    ax += recv.type.rank
                axvals.append(str(ax))
            else:
                axvals.append(self._int_arg(el))
        return Val("nd::transpose(%s, {%s})" % (recv.code, ", ".join(axvals)),
                   array_t(recv.type.dtype, recv.type.rank))

    def _op_squeeze(self, recv, args, node):
        ax = self._kw(node, "axis") or (args[0] if args else None)
        if ax is None:
            # Which axes vanish depends on the RUNTIME shape, so the output rank
            # is not statically known (rank=None) unless an axis is named.
            return Val("nd::squeeze(%s)" % recv.code,
                       array_t(recv.type.dtype, None))
        rank = None if recv.type.rank is None else max(0, recv.type.rank - 1)
        return Val("nd::squeeze(%s, %s)" % (recv.code, self._int_arg(ax)),
                   array_t(recv.type.dtype, rank))

    def _op_swapaxes(self, recv, args, node):
        self._need(node, args, 2)
        return Val("nd::swapaxes(%s, %s, %s)"
                   % (recv.code, self._int_arg(args[0]), self._int_arg(args[1])),
                   array_t(recv.type.dtype, recv.type.rank))

    def _op_diagonal(self, recv, args, node):
        off = self._kw(node, "offset") or (args[0] if args else None)
        offs = "0" if off is None else self._int_arg(off)
        return Val("nd::diagonal(%s, %s)" % (recv.code, offs),
                   array_t(recv.type.dtype, 1))

    def _op_trace(self, recv, args, node):
        off = self._kw(node, "offset") or (args[0] if args else None)
        offs = "0" if off is None else self._int_arg(off)
        return Val("nd::trace(%s, %s)" % (recv.code, offs),
                   array_t(recv.type.dtype, 0))

    # ---- copy / cast / export -------------------------------------------
    def _op_copy(self, recv, args, node):
        return Val("%s.copy()" % recv.code,
                   array_t(recv.type.dtype, recv.type.rank))

    def _op_astype(self, recv, args, node):
        self._need(node, args, 1)
        dt = self._dtype_of(args[0], node)
        return Val("nd::astype<%s>(%s)" % (_CTYPE[dt], recv.code),
                   array_t(dt, recv.type.rank))

    def _op_item(self, recv, args, node):
        return Val("(%s).item()" % recv.code, scalar_t(recv.type.dtype))

    # ==== MatrixView =====================================================
    # A matrix input arrives as a MatrixView, which carries the whole MMatrix +
    # MTransformationMatrix surface. Tier A below is pure nd::; the rest route
    # to the ndx:: bridge, which calls Maya so the compiled node matches the
    # interpreted one EXACTLY rather than to a tolerance. Design note and the
    # excluded methods (in-place setters, pivots): docs/notes/.

    def _mv_recv(self, recv, node, what):
        """C++ for a receiver that must be a (4,4) matrix.

        Rank is all that can be proven statically -- the exact 4x4 is checked at
        runtime by ndx::nd_to_mmatrix and nd::det, the same way nd::inv already
        reports a bad shape. Rejecting a wrong RANK here is still worth doing:
        it turns `self.someVector.rotation()` into a precise UnsupportedSpec at
        codegen time instead of a throw inside compute.
        """
        t = recv.type
        if not t.is_array() or (t.rank is not None and t.rank != 2):
            self.fail(node, ".%s() is a MatrixView method and needs a (4,4) "
                            "receiver; this value is %s" % (
                                what,
                                "a rank-%s array" % (t.rank,) if t.is_array()
                                else "a %s" % t.kind))
        return recv.code

    def _mv_bridge(self, fn, recv, args, node, what, rtype):
        self._need(node, args, 0)
        code = "ndx::%s(%s)" % (fn, self._mv_recv(recv, node, what))
        self.uses_maya_xform = True
        return Val(code, rtype)

    # ---- Tier A: existing nd::, no Maya ---------------------------------
    def _op_mv_translation(self, recv, args, node):
        self._need(node, args, 0)
        # Row 3, first three columns -- Maya's row-vector convention puts the
        # translation in ROW 3, not column 3.
        return Val("nd::slice(%s, {nd::Sl::at(3), nd::Sl::to(3)})"
                   % self._mv_recv(recv, node, "translation"),
                   array_t("double", 1))

    def _op_mv_inverse(self, recv, args, node):
        self._need(node, args, 0)
        return Val("nd::inv(%s)" % self._mv_recv(recv, node, "inverse"),
                   array_t("double", 2))

    def _op_mv_get_element(self, recv, args, node):
        self._need(node, args, 2)
        base = self._mv_recv(recv, node, "getElement")
        r = self._scalar_int_of(self.expr(args[0]), node)
        c = self._scalar_int_of(self.expr(args[1]), node)
        return Val("nd::slice(%s, {nd::Sl::at(%s), nd::Sl::at(%s)})"
                   % (base, r, c), array_t("double", 0))

    # ---- Tier C: Maya semantics via the ndx:: bridge ---------------------
    def _op_mv_rotation(self, recv, args, node):
        base = self._mv_recv(recv, node, "rotation")
        axnode = self._kw(node, "axes")
        if axnode is None and len(args) == 1:
            axnode = args[0]
        elif len(args) > 1:
            self.fail(node, ".rotation() takes at most one argument (axes)")
        # 0-based Maya rotate-order index (0=xyz .. 5=zyx) -- the same numbering
        # a rotateOrder enum plug uses, and NOT the 1-based enum rotationOrder()
        # returns. Both are mirrored as-is; see the design note.
        axes = ("0" if axnode is None
                else self._scalar_int_of(self.expr(axnode), node))
        self.uses_maya_xform = True
        return Val("ndx::xf_rotation(%s, %s)" % (base, axes),
                   array_t("double", 1))

    def _op_mv_det3(self, recv, args, node):
        # MMatrix::det3x3 -- the UPPER-LEFT block, not the whole matrix. Via
        # Maya rather than nd::det so nd_runtime.h stays untouched; see
        # kernels/nd_maya_cpp.py for why that matters.
        return self._mv_bridge("xf_det3x3", recv, args, node, "det3x3",
                               scalar_t("double"))

    def _op_mv_det4(self, recv, args, node):
        return self._mv_bridge("xf_det4x4", recv, args, node, "det4x4",
                               scalar_t("double"))

    def _op_mv_scale(self, recv, args, node):
        return self._mv_bridge("xf_scale", recv, args, node, "scale",
                               array_t("double", 1))

    def _op_mv_shear(self, recv, args, node):
        return self._mv_bridge("xf_shear", recv, args, node, "shear",
                               array_t("double", 1))

    def _op_mv_rotation_order(self, recv, args, node):
        return self._mv_bridge("xf_rotation_order", recv, args, node,
                               "rotationOrder", scalar_t("int64"))

    def _op_mv_is_singular(self, recv, args, node):
        return self._mv_bridge("xf_is_singular", recv, args, node,
                               "isSingular", scalar_t("bool"))

    def _op_mv_as_rotate_matrix(self, recv, args, node):
        return self._mv_bridge("xf_as_rotate_matrix", recv, args, node,
                               "asRotateMatrix", array_t("double", 2))

    def _op_mv_as_scale_matrix(self, recv, args, node):
        return self._mv_bridge("xf_as_scale_matrix", recv, args, node,
                               "asScaleMatrix", array_t("double", 2))

    def _op_mv_as_matrix_inverse(self, recv, args, node):
        return self._mv_bridge("xf_as_matrix_inverse", recv, args, node,
                               "asMatrixInverse", array_t("double", 2))

    def _op_mv_adjoint(self, recv, args, node):
        return self._mv_bridge("xf_adjoint", recv, args, node, "adjoint",
                               array_t("double", 2))

    def _op_mv_homogenize(self, recv, args, node):
        return self._mv_bridge("xf_homogenize", recv, args, node, "homogenize",
                               array_t("double", 2))

    def _op_asnumpy(self, recv, args, node):
        # MatrixView.asNumpy() -- the interpreted matrix-input idiom
        # (self.matrix0.asNumpy()). The receiver is already the materialised
        # nd (4,4) array, so this is an identity passthrough.
        if args:
            self.fail(node, ".asNumpy() takes no arguments")
        return recv

    def _op_tofile(self, recv, args, node):
        # arr.tofile(path) -- headerless little-endian dump, path verbatim
        # (unlike np.save, numpy adds no suffix here).
        self._need(node, args, 1)
        for bad in ("sep", "format"):
            if self._kw(node, bad) is not None:
                self.fail(node, ".tofile(%s=...) is not lowered" % bad)
        path = self._str_arg(args[0], node, ".tofile path")
        self.uses_ndio = True
        return Val("nd_io_write_raw(%s, %s)" % (path, recv.code),
                   scalar_t("bool"))

    def _op_byteswap(self, recv, args, node):
        return Val("nd::byteswap(%s)" % recv.code,
                   array_t(recv.type.dtype, recv.type.rank))

    def _op_conj(self, recv, args, node):
        # The runtime has no complex dtype, so on a real array conj is exactly
        # the identity -- and a complex one never gets this far.
        return recv

    # ---- reductions ------------------------------------------------------
    def _reduce_op(self, ndfn, pyname, recv, args, node, out_dtype=None,
                   extra=None):
        """The one reduction lowering. `a.sum(axis=0)` and `np.sum(a, axis=0)`
        both arrive here with the array in `recv` and `axis` first in `args`.
        `extra` appends a trailing kernel argument (var/std's ddof)."""
        if recv.type.is_scalar():
            self.fail(node, "%s of a scalar" % pyname)
        axis = self._kw(node, "axis")
        if axis is None and args:
            axis = args[0]
        axes_code, n_axes = self._axes_arg(axis, node)
        keep = self._kw(node, "keepdims")
        keeps = "false" if keep is None else self._as_bool(self.expr(keep), node)
        out_dt = out_dtype or recv.type.dtype
        recv_code = recv.code
        if ndfn in ("sum", "reduce_prod") and recv.type.dtype == "bool":
            # numpy promotes bool.sum()/bool.prod() -> int64. Accumulate in the
            # promoted type: summing in bool saturates at 1 (true + true == true),
            # so a boolean mask's count would collapse to 1.
            out_dt = "int64"
            recv_code = "nd::astype<int64_t>(%s)" % recv.code
        rank = None
        if recv.type.rank is not None and keep is None:
            rank = 0 if n_axes is None else max(0, recv.type.rank - n_axes)
        tail = "" if extra is None else ", %s" % extra
        # `(a * b).sum(axis=...)` -> nd::sum_mul(a, b, ...), which accumulates
        # the product instead of materialising it. Only for a plain sum of an
        # ARRAY*ARRAY product with no dtype promotion in the way; sum_mul falls
        # back to the literal sum(mul(...)) whenever its own runtime
        # preconditions miss, so a wrong guess here costs nothing but is still
        # kept narrow.
        if ndfn == "sum" and extra is None:
            fz = recv.fuse
            if fz is not None and fz.kind == "op" \
                    and isinstance(fz.val, tuple) and len(fz.val) == 3 \
                    and fz.val[0] == "Mul" and out_dt == recv.type.dtype \
                    and out_dt != "bool":
                return Val("nd::sum_mul(%s, %s, {%s}, %s)"
                           % (fz.val[1], fz.val[2], axes_code, keeps),
                           array_t(out_dt, rank))
        return Val("nd::%s(%s, {%s}, %s%s)"
                   % (ndfn, recv_code, axes_code, keeps, tail),
                   array_t(out_dt, rank))

    def _op_sum(self, recv, args, node):
        return self._reduce_op("sum", "sum", recv, args, node)

    def _op_max(self, recv, args, node):
        return self._reduce_op("reduce_max", "max", recv, args, node)

    def _op_min(self, recv, args, node):
        return self._reduce_op("reduce_min", "min", recv, args, node)

    def _op_mean(self, recv, args, node):
        return self._reduce_op("mean", "mean", recv, args, node, "double")

    def _op_prod(self, recv, args, node):
        return self._reduce_op("reduce_prod", "prod", recv, args, node)

    def _op_all(self, recv, args, node):
        return self._reduce_op("reduce_all", "all", recv, args, node, "bool")

    def _op_any(self, recv, args, node):
        return self._reduce_op("reduce_any", "any", recv, args, node, "bool")

    def _op_ptp(self, recv, args, node):
        return self._reduce_op("ptp", "ptp", recv, args, node)

    def _op_var(self, recv, args, node):
        return self._var_op("var", recv, args, node)

    def _op_std(self, recv, args, node):
        return self._var_op("stddev", recv, args, node)

    def _var_op(self, ndfn, recv, args, node):
        """var/std -- a reduction with the extra ddof argument. ddof defaults to
        0 (the POPULATION form); ddof=1 is the sample form.

        ddof is KEYWORD-only here on purpose: numpy's positional order is
        (axis, dtype, out, ddof), so reading args[1] as ddof would actually be
        reading `dtype`."""
        if len(args) > 1:
            self.fail(node, "pass ddof as a keyword (numpy's positional order "
                            "is axis, dtype, out, ddof)")
        dd = self._kw(node, "ddof")
        ddof = "0" if dd is None else self._int_arg(dd)
        return self._reduce_op(ndfn, ndfn, recv, args, node, "double", ddof)

    def _arg_reduce(self, ndfn, pyname, recv, args, node):
        """argmax/argmin: numpy takes ONE axis or None, never a tuple."""
        axis = self._kw(node, "axis")
        if axis is None and args:
            axis = args[0]
        axes_code, n_axes = self._axes_arg(axis, node)
        if n_axes is not None and n_axes != 1:
            self.fail(node, "np.%s takes a single axis or None" % pyname)
        rank = None
        if recv.type.rank is not None:
            rank = 0 if n_axes is None else max(0, recv.type.rank - 1)
        return Val("nd::%s(%s, {%s}, false)" % (ndfn, recv.code, axes_code),
                   array_t("int64", rank))

    def _op_argmax(self, recv, args, node):
        return self._arg_reduce("argmax", "argmax", recv, args, node)

    def _op_argmin(self, recv, args, node):
        return self._arg_reduce("argmin", "argmin", recv, args, node)

    # ---- scans -----------------------------------------------------------
    def _scan_op(self, ndfn, pyname, recv, args, node):
        """cumsum/cumprod -- the INCLUSIVE running sum/product.

        numpy's DEFAULT here is axis=None, which FLATTENS to 1-D whatever the
        input rank; note np.sort defaults the other way (axis=-1), so the two
        cannot share a default. An EXCLUSIVE prefix sum is not ``cumsum(a) - a``
        -- that subtraction rounds a second time. Shift instead:
        ``concatenate([zeros, cumsum(a)[..., :-1]])``.
        """
        if not recv.type.is_array() or recv.type.rank is None:
            self.fail(node, "np.%s needs an array of statically known rank"
                      % pyname)
        axis = self._kw(node, "axis")
        if axis is None and args:
            axis = args[0]
        dt, code = recv.type.dtype, recv.code
        if dt == "bool":
            # numpy promotes a bool scan to int64; accumulating in bool would
            # saturate at 1 the same way np.sum(bool) does.
            dt = "int64"
            code = "nd::astype<int64_t>(%s)" % recv.code
        if axis is None:
            return Val("nd::%s(%s, (int64_t)0, true)" % (ndfn, code),
                       array_t(dt, 1))
        if recv.type.rank < 1:
            self.fail(node, "np.%s with axis needs a rank>=1 array" % pyname)
        return Val("nd::%s(%s, (int64_t)(%s), false)"
                   % (ndfn, code, self._int_arg(axis)), array_t(dt, recv.type.rank))

    def _op_cumsum(self, recv, args, node):
        return self._scan_op("cumsum", "cumsum", recv, args, node)

    def _op_cumprod(self, recv, args, node):
        return self._scan_op("cumprod", "cumprod", recv, args, node)

    # ---- sort / search ---------------------------------------------------
    def _sort_axis(self, args, node, argno=0):
        """The axis argument shared by sort/argsort. numpy's default is -1 (the
        LAST axis), and axis=None is the opt-in flatten -- the opposite default
        from cumsum, which is why this is spelled out rather than assumed."""
        axis = self._kw(node, "axis")
        if axis is None and len(args) > argno:
            axis = args[argno]
        if axis is None:
            return "-1", False
        if isinstance(axis, ast.Constant) and axis.value is None:
            return "0", True
        return self._int_arg(axis), False

    def _op_sort(self, recv, args, node):
        axis, flat = self._sort_axis(args, node)
        rank = 1 if flat else recv.type.rank
        return Val("nd::sort(%s, %s, %s)"
                   % (recv.code, axis, "true" if flat else "false"),
                   array_t(recv.type.dtype, rank))

    def _op_argsort(self, recv, args, node):
        axis, flat = self._sort_axis(args, node)
        rank = 1 if flat else recv.type.rank
        return Val("nd::argsort(%s, %s, %s)"
                   % (recv.code, axis, "true" if flat else "false"),
                   array_t("int64", rank))

    def _op_searchsorted(self, recv, args, node):
        self._need(node, args, 1)
        v = self.expr(args[0])
        side = self._kw(node, "side")
        if side is None and len(args) > 1:
            side = args[1]
        right = "false"
        if side is not None:
            if not (isinstance(side, ast.Constant)
                    and side.value in ("left", "right")):
                self.fail(node, "searchsorted side must be the literal 'left' "
                                "or 'right'")
            right = "true" if side.value == "right" else "false"
        rank = 0 if v.type.is_scalar() else v.type.rank
        return Val("nd::searchsorted(%s, %s, %s)"
                   % (recv.code, self._to_array_dtype(v, recv.type.dtype), right),
                   array_t("int64", rank))

    # ---- gather / select --------------------------------------------------
    def _op_take(self, recv, args, node):
        self._need(node, args, 1)
        idx = self.expr(args[0])
        if not recv.type.is_array():
            self.fail(node, "take of a non-array")
        if not idx.type.is_array():
            self.fail(node, "take indices must be an array")
        idxc = (idx.code if idx.type.dtype == "int64"
                else "nd::astype<int64_t>(%s)" % idx.code)
        axis = self._kw(node, "axis")
        if axis is None and len(args) > 1:
            axis = args[1]
        if axis is None or (isinstance(axis, ast.Constant) and axis.value is None):
            return Val("nd::take(%s, %s)" % (recv.code, idxc),
                       array_t(recv.type.dtype, idx.type.rank))
        # result rank = src.rank - 1 (axis dropped) + idx.rank (index block).
        return Val("nd::take(%s, %s, %s)" % (recv.code, idxc, self._int_arg(axis)),
                   array_t(recv.type.dtype, recv.type.rank - 1 + idx.type.rank))

    def _op_repeat(self, recv, args, node):
        self._need(node, args, 1)
        n = self._int_arg(args[0])
        axis = self._kw(node, "axis")
        if axis is None and len(args) > 1:
            axis = args[1]
        if axis is None:
            # numpy FLATTENS when axis is None: a (2,2) repeated twice is an
            # 8-vector, not a (4,2).
            return Val("nd::repeat(%s, %s)" % (recv.code, n),
                       array_t(recv.type.dtype, 1))
        return Val("nd::repeat(%s, %s, %s)"
                   % (recv.code, n, self._int_arg(axis)),
                   array_t(recv.type.dtype, recv.type.rank))

    def _op_compress_free(self, recv, args, node):
        """np.compress(condition, a[, axis])."""
        self._need(node, args, 1)
        return self._compress(recv, self.expr(args[0]), args[1:], node)

    def _op_compress_method(self, recv, args, node):
        """a.compress(condition[, axis]) -- the same op, mask and array swapped."""
        self._need(node, args, 1)
        return self._compress(self.expr(args[0]), recv, args[1:], node)

    def _compress(self, cond, src, rest, node):
        axis = self._kw(node, "axis")
        if axis is None and rest:
            axis = rest[0]
        condc = self._to_array_dtype(cond, "bool")
        if axis is None:
            return Val("nd::compress(%s, %s)" % (condc, src.code),
                       array_t(src.type.dtype, 1))
        return Val("nd::compress(%s, %s, %s)"
                   % (condc, src.code, self._int_arg(axis)),
                   array_t(src.type.dtype, src.type.rank))

    def _op_choose(self, recv, args, node):
        self._need(node, args, 1)
        if not isinstance(args[0], (ast.Tuple, ast.List)):
            # numpy also accepts ONE array whose first axis selects.
            ch = self.expr(args[0])
            if not ch.type.is_array():
                self.fail(node, "choose() needs a tuple/list of choices or an "
                                "array whose first axis selects")
            return Val("nd::choose(%s, %s)"
                       % (self._to_array_dtype(recv, "int64"), ch.code),
                       array_t(ch.type.dtype, recv.type.rank))
        vals = [self.expr(e) for e in args[0].elts]
        if not vals:
            self.fail(node, "choose() with no choices")
        dt = vals[0].type.dtype
        for v in vals[1:]:
            dt = _promote(dt, v.type.dtype)
        # Spelled out rather than braced: a bare {a, b} cannot deduce T.
        vec = "std::vector<nd::Array<%s>>{%s}" % (
            _CTYPE[dt], ", ".join(self._to_array_dtype(v, dt) for v in vals))
        return Val("nd::choose(%s, %s)"
                   % (self._to_array_dtype(recv, "int64"), vec),
                   array_t(dt, recv.type.rank))

    def _op_clip(self, recv, args, node):
        self._need(node, args, 2)
        inner = self._array_binop("Min", recv, self.expr(args[1]), node)
        return self._array_binop("Max", inner, self.expr(args[0]), node)

    def _op_dot(self, recv, args, node):
        self._need(node, args, 1)
        return self._matmul(recv, self.expr(args[0]), node)

    def _op_nonzero(self, recv, args, node):
        # nonzero returns a TUPLE of per-axis index arrays, which has no single
        # value form here -- both spellings get the same pointer.
        self.fail(node, "nonzero must be tuple-unpacked: "
                        "`ys, xs = np.nonzero(a)` (or `a.nonzero()`)")

    def _op_round(self, recv, args, node):
        dec = self._kw(node, "decimals") or (args[0] if args else None)
        decs = "0" if dec is None else self._int_arg(dec)
        return Val("nd::round(%s, %s)" % (recv.code, decs),
                   array_t(recv.type.dtype, recv.type.rank))

    def _op_resize_repeat(self, recv, args, node):
        # np.resize REPEATS the source to fill the new shape; the a.resize()
        # METHOD zero-fills instead (see _stmt_resize).
        self._need(node, args, 1)
        shp = self._shape_from_args(args, node)
        return Val("nd::resize_repeat(%s, %s)" % (recv.code, shp[0]),
                   array_t(recv.type.dtype, shp[1]))

    def _rng_method(self, attr, recv, args, node):
        if attr in ("random", "random_sample", "ranf", "sample"):
            if len(args) == 1:
                shp = self._shape_arg(args[0])
                rank = self._shape_rank(args[0])
            elif len(args) == 0:
                shp, rank = "nd::Shape{}", 0
            else:
                self.fail(node, "%s takes a single shape argument" % attr)
            return Val("%s.random(%s)" % (recv.code, shp), array_t("double", rank))
        if attr == "rand":
            # legacy rand(d0, d1, ...) -> shape from separate int args
            dims = ", ".join(self._int_arg(a) for a in args)
            return Val("%s.random({%s})" % (recv.code, dims),
                       array_t("double", len(args) if args else 0))
        self.fail(node, "RandomState.%s (deferred)" % attr)

    def _shape_from_args(self, args, node):
        """reshape(*dims) or reshape((dims,)) -> (C++ shape expr, rank)."""
        if len(args) == 1 and isinstance(args[0], (ast.Tuple, ast.List)):
            return self._shape_arg(args[0]), self._shape_rank(args[0])
        if len(args) == 1:
            v = self.expr(args[0])
            if v.type.kind == "shape":
                return v.type.code, None
            return "{%s}" % self._int_arg(args[0]), 1
        dims = ", ".join(self._int_arg(a) for a in args)
        return "{%s}" % dims, len(args)

    # ---- math.* scalar functions -------------------------------------------
    def _call_math(self, fn, node):
        args = self._pos_args(node)
        smap = {"sin": "sin", "cos": "cos", "tan": "tan", "asin": "asin",
                "acos": "acos", "atan": "atan", "exp": "exp", "log": "log",
                "sqrt": "sqrt", "fabs": "fabs"}
        if fn in smap:
            self._need(node, args, 1)
            a = self.expr(args[0])
            if not _scalarish(a.type):
                self.fail(node, "math.%s of an array (use np.%s)" % (fn, fn))
            return self._scalar_ufunc(smap[fn], a)
        if fn == "pow":
            self._need(node, args, 2)
            return self._scalar_binop("Pow", self.expr(args[0]), self.expr(args[1]))
        self.fail(node, "math.%s not supported" % fn)

    # ---- python builtins ----------------------------------------------------
    def _call_builtin(self, fn, node):
        args = self._pos_args(node)
        if fn == "len":
            self._need(node, args, 1)
            v = self.expr(args[0])
            if v.type.is_array():
                return Val("(int64_t)%s.shape[0]" % v.code, scalar_t("int64"))
            if v.type.kind == "shape":
                return Val("(int64_t)%s.size()" % v.type.code, scalar_t("int64"))
            if v.type.kind == "strv":
                return Val("(int64_t)%s.size()" % v.code, scalar_t("int64"))
            self.fail(node, "len() of a scalar")
        if fn == "str":
            self._need(node, args, 1)
            v = self.expr(args[0])
            if v.type.kind != "str":
                # str() of a NUMBER is Python's repr ("3.0", "3", "1e-05"), which
                # no C++ formatter reproduces exactly -- a near-miss would draw
                # the wrong text, so reject rather than approximate.
                self.fail(node, "str() lowers only for a value that is already "
                                "a string")
            return v
        if fn == "list":
            self._need(node, args, 1)
            v = self.expr(args[0])
            if v.type.kind != "str":
                self.fail(node, "list() lowers only for a string (one entry per "
                                "character)")
            return Val("nd::str_chars(%s)" % v.code, strv_t())
        if fn == "int":
            self._need(node, args, 1)
            return Val("(int64_t)(%s)" % self._scalar_dbl_or_int(args[0], node),
                       scalar_t("int64"))
        if fn == "float":
            self._need(node, args, 1)
            return Val("(double)(%s)" % self._scalar_dbl(args[0]), scalar_t("double"))
        if fn == "bool":
            self._need(node, args, 1)
            return Val(self._as_bool(self.expr(args[0]), node), scalar_t("bool"))
        if fn == "abs":
            self._need(node, args, 1)
            v = self.expr(args[0])
            if v.type.is_array():
                return Val("nd::fabs(%s)" % v.code, array_t("double", v.type.rank))
            c = self._cse_bind(v.code)   # bind non-trivial once (named 3x below)
            return Val("((%s) < 0 ? -(%s) : (%s))" % (c, c, c), v.type)
        if fn in ("min", "max"):
            self._need(node, args, 2)
            a, b = self.expr(args[0]), self.expr(args[1])
            if not (_scalarish(a.type) and _scalarish(b.type)):
                self.fail(node, "%s() of arrays (use np.%simum)" % (fn, fn))
            dt = _promote(a.type.dtype, b.type.dtype)
            op = ">" if fn == "max" else "<"
            ca, cb = self._cast_scalar(a, dt), self._cast_scalar(b, dt)
            ca = self._cse_bind(ca)      # bind non-trivial once (each named 2x)
            cb = self._cse_bind(cb)
            # CPython's two-arg max(a, b) is `b if b > a else a` (min is the
            # mirror): the SECOND operand wins only when it compares strictly
            # greater/less, so a NaN loses in either slot -- max(nan, 1.0) is
            # nan, max(1.0, nan) is 1.0. Testing `a > b` inverts BOTH of those.
            # Deliberately NOT nd::maximum_elem: that is np.maximum, which
            # propagates NaN from either side. These are the PYTHON builtins.
            # The bind ORDER above stays a-then-b, so left-to-right argument
            # evaluation is unchanged; only the ternary's operands swap.
            return Val("(%s %s %s ? %s : %s)" % (cb, op, ca, cb, ca), scalar_t(dt))
        self.fail(node, "builtin %s" % fn)

    def _scalar_dbl_or_int(self, node, ctx):
        v = self.expr(node)
        if v.type.is_array():
            if v.type.rank not in (0, None):
                self.fail(ctx, "int() of a non-scalar array")
            # A fully integer-indexed subscript carries a raw scalar form
            # (nd::atN) -- use it to avoid allocating a per-access nd:: view.
            return v.raw if v.raw is not None else "(%s).item()" % v.code
        return v.code

    # ---- shape argument helpers --------------------------------------------
    def _need(self, node, args, n):
        if len(args) < n:
            self.fail(node, "expected at least %d positional argument(s)" % n)

    def _shape_arg(self, node):
        """A shape argument (tuple/list of ints, a single int, or x.shape)."""
        if isinstance(node, (ast.Tuple, ast.List)):
            dims = ", ".join(self._int_arg(e) for e in node.elts)
            return "nd::Shape{%s}" % dims
        v = self.expr(node)
        if v.type.kind == "shape":
            return v.type.code
        if v.type.is_scalar():
            return "nd::Shape{%s}" % self._scalar_int_of(v, node)
        self.fail(node, "invalid shape argument")

    def _shape_rank(self, node):
        if isinstance(node, (ast.Tuple, ast.List)):
            return len(node.elts)
        v = self.expr(node)
        if v.type.kind == "shape":
            return None
        return 1


# ==== public API ==========================================================
def _extract_func(source):
    tree = ast.parse(source)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len(funcs) != 1:
        raise UnsupportedSpec("py_to_cpp: expected exactly one top-level "
                              "function, found %d" % len(funcs))
    return funcs[0]


def transpile_function(source, arg_types, return_handler=None):
    """Transpile a single Python function to C++ nd:: statements.

    source        : text with exactly one top-level `def`.
    arg_types     : dict argname -> CppType (and/or 'self.<attr>' -> CppType).
    return_handler: optional callable(Val) -> list[str] of C++ lines; default
                    emits `return <expr>;`.
    Returns a TranspileResult (arg_names, decl_lines, body_lines, returns).
    """
    fdef = _extract_func(source)
    imports, import_stars = _parse_import_bindings(source)
    t = Transpiler(arg_types, return_handler, imports=imports,
                   import_stars=import_stars)
    return t.run(fdef)


class _HelperCtx:
    """Shared state for lowering a node's inline INIT-tier ``def`` helpers into
    C++ lambdas emitted ahead of the compute body.

    defs        : name -> ast.FunctionDef for every top-level helper in the init
                  source.
    generated   : (name, arg-type-sig) -> (mono_name, ret CppType) -- a helper
                  called with the same argument types is emitted once.
    lines       : accumulated ``auto <mono> = [&](...) -> R { ... };`` blocks in
                  callee-before-caller order (ready to prepend to the body).
    in_progress : keys currently being generated -> recursion/cycle guard.
    """

    def __init__(self, defs, consts=None):
        self.defs = defs
        # {name: value AST node} for INIT-tier module constants (see
        # _parse_module_consts). Empty unless the caller opted in.
        self.consts = consts or {}
        self.generated = {}
        self.lines = []
        self.in_progress = set()
        # emit_stack: keys whose bodies are currently being transpiled, in order.
        # Direct self-recursion is valid only when the recursive call's key is
        # the TOP of the stack (the helper calling itself); any other in-progress
        # key means a cross-helper cycle (mutual recursion) -> reject.
        self.emit_stack = []
        # rec: key -> (mono_name, seed_ret CppType) for a self-recursive helper
        # currently being emitted, so its own self-calls resolve to a typed call
        # of the std::function lambda before the lambda is fully written.
        self.rec = {}
        self._counter = 0

    def fresh(self, name):
        self._counter += 1
        return "_h_%s_%d" % (re.sub(r"[^0-9A-Za-z_]", "_", name),
                             self._counter)


def _parse_helpers(helper_source):
    """Parse helper source(s) into {name: FunctionDef} for their top-level
    ``def``s. Non-def statements (imports, module constants) are ignored -- a
    helper that references such a name lands in an unknown-name failure at
    lowering time, so nothing unsupported slips through.

    ``helper_source`` is EITHER a single source string (the node's INIT-tier
    source) OR an iterable of source strings (INIT-tier + each followed external
    helper unit's source; see import_follower). Every source is parsed
    INDEPENDENTLY, so a leading ``from __future__`` in one unit can never break a
    sibling, and later sources override earlier ones on a name collision (callers
    put the node-local INIT source LAST so a node-local ``def`` shadows an
    identically named followed helper). A source that fails to parse is skipped
    (best-effort: a genuinely needed helper that won't parse simply is not found,
    so the compute that calls it fails to lower -> AI-porter fallback, never a
    crash)."""
    sources = [helper_source] if isinstance(helper_source, str) else list(
        helper_source or [])
    defs = {}
    for src in sources:
        if not src or not src.strip():
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for n in tree.body:
            if isinstance(n, ast.FunctionDef):
                defs[n.name] = n
    return defs


def _parse_module_consts(source):
    """``{name: value_node}`` for MODULE-LEVEL constants in an INIT-tier source.

    Companion to :func:`_parse_helpers`, which keeps the ``def``s and drops
    everything else. A compute expression may read an Init-tab constant
    (``TWO_PI``, ``CUBE_PTS``); this collects the candidates and ``ex_Name``
    transpiles one LAZILY at its first use, so a constant the transpiler cannot
    express costs nothing until something actually reads it.

    Collection is from ``tree.body`` ONLY -- a name assigned inside a ``def`` is
    that function's local, not a module constant -- but DISQUALIFICATION is
    counted over the whole tree: a name that is also bound anywhere else (in a
    function body, a loop, a branch, or a second module-level assignment) is
    dropped rather than guessed at. Same rule, and the same reason, as
    ``locator_draw_cpp._single_assignments``: resolving an ambiguous binding
    means guessing, and guessing wrong is a silent wrong answer.

    ``source`` is a single source string or an iterable of them. A source that
    will not parse is skipped (best-effort, never a crash)."""
    sources = [source] if isinstance(source, str) else list(source or [])
    counts, values = {}, {}
    for src in sources:
        if not src or not src.strip():
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for stmt in tree.body:
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)):
                values[stmt.targets[0].id] = stmt.value
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    for sub in ast.walk(t):
                        if isinstance(sub, ast.Name):
                            counts[sub.id] = counts.get(sub.id, 0) + 1
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign, ast.For)):
                t = getattr(n, "target", None)
                if isinstance(t, ast.Name):
                    counts[t.id] = counts.get(t.id, 0) + 2   # never single
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                ast.ClassDef)):
                counts[n.name] = counts.get(n.name, 0) + 2
                for a in list(getattr(n, "args", None).args
                              if getattr(n, "args", None) else []):
                    counts[a.arg] = counts.get(a.arg, 0) + 2
    return {k: v for k, v in values.items() if counts.get(k) == 1}


def _contains_call_to(node, name):
    """True if the AST subtree `node` contains a direct call ``name(...)``."""
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == name:
            return True
    return False


def _is_self_recursive(fdef):
    """True if `fdef` calls itself directly by name (ignoring nested defs, which
    the helper surface already forbids)."""
    return _contains_call_to(fdef, fdef.name)


def _written_names(fdef):
    """Set of local names WRITTEN anywhere in helper ``fdef``'s body -- targets
    of assignment (plain or through a subscript store ``p[i] = v``), augmented /
    annotated assignment, ``for`` / ``with`` / comprehension binding, and walrus.
    A helper array parameter NOT in this set is only read, so it can be passed by
    ``const&``; a written one MUST stay by value (a const& would fail to compile
    on reassignment, or silently alias the caller on an in-place element store).
    Conservative by construction: any name that appears as a store target counts
    as written, and the default (by value) is always correct."""
    written = set()

    def add_target(tgt):
        if isinstance(tgt, ast.Name):
            written.add(tgt.id)
        elif isinstance(tgt, ast.Starred):
            add_target(tgt.value)
        elif isinstance(tgt, (ast.Tuple, ast.List)):
            for e in tgt.elts:
                add_target(e)
        elif isinstance(tgt, ast.Subscript):
            # p[i] = v mutates p's (shared) buffer -> p is written.
            if isinstance(tgt.value, ast.Name):
                written.add(tgt.value.id)
        # ast.Attribute (self.x) is not a local param name -> ignore.

    for n in ast.walk(fdef):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                add_target(t)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            add_target(n.target)
        elif isinstance(n, ast.For):
            add_target(n.target)
        elif isinstance(n, ast.comprehension):
            add_target(n.target)
        elif isinstance(n, ast.NamedExpr):
            add_target(n.target)
        elif isinstance(n, ast.withitem):
            if n.optional_vars is not None:
                add_target(n.optional_vars)
    return written


def _param_ctype(t, ctx_node, by_ref=False):
    """C++ type for a helper parameter/return CppType. Rejects rng/shape (a
    helper may not take or return a RandomState or a shape tuple). ``by_ref``
    (parameter position only, never a return) emits an ARRAY param as
    ``const nd::Array<T>&`` so a read-only param is not copied per call -- a
    pure calling-convention change (the values read are identical, so the
    compiled output stays byte-for-byte the same). Scalars ignore ``by_ref``."""
    if t.kind == "array":
        base = "nd::Array<%s>" % _CTYPE[t.dtype]
        return ("const %s&" % base) if by_ref else base
    if t.kind == "scalar":
        return _CTYPE[t.dtype]
    raise UnsupportedSpec("py_to_cpp: helper param/return kind %r (line %s) not "
                          "supported" % (t.kind, getattr(ctx_node, "lineno", "?")))


def transpile_compute_block(source, env, output_writers, helper_source=None,
                            state_vars=None, blessed=None, blessed_unpack=None,
                            side_effect_methods=None, const_source=None):
    """Transpile an mpynode compute BODY (bare statements) to C++.

    source         : the compute source (statements; reads self.<in>, writes
                     self.<out>). A leading module docstring is tolerated.
    env            : dict 'self.<in>' -> CppType for every readable input, plus
                     any other pre-bound names.
    output_writers : dict 'self.<out>' -> callable(Val) -> list[str] that emits
                     the C++ storing the produced value into the node output.
    helper_source  : optional helper source whose top-level ``def``s the compute
                     may call; each used helper is lowered to a C++ lambda
                     returned in ``helper_lines`` (callee-first order). EITHER a
                     single source string (the INIT-tier source) OR a list of
                     source strings (INIT-tier + followed external helper units,
                     see _parse_helpers / import_follower).
    blessed        : optional {method: callable(tp, node)->Val} lowering a blessed
                     ``self.<method>(...)`` in expression position.
    blessed_unpack : optional {method: callable(tp, node)->list[Val]} lowering a
                     blessed ``a, b, ... = self.<method>(...)`` unpack. Both are
                     codegen-supplied so py_to_cpp stays kernel-agnostic.
    side_effect_methods : optional set of blessed ``NativeSideEffect`` method
                     names whose bare ``self.<name>(...)`` statement lowers to
                     nothing (interactive-only plug side effect, no kernel).
    const_source   : optional INIT-tier source whose MODULE-LEVEL constants the
                     compute may read as bare names (see _parse_module_consts).
                     Opt-in and separate from ``helper_source``: that argument
                     also carries whole FOLLOWED module sources, whose module
                     constants are not the node author's to reference.
    Returns (TranspileResult, written_outputs_set, helper_lines). Raises
    UnsupportedSpec on any unsupported construct."""
    tree = ast.parse(source)
    if any(isinstance(n, ast.FunctionDef) for n in tree.body):
        raise UnsupportedSpec("py_to_cpp: compute block must be bare statements, "
                              "not a def")
    # A live _HelperCtx is required whenever a helper lambda might be emitted --
    # both for INIT-tier ``def``s (helper_source) AND for blessed ``Transpile``
    # lowerings (which emit the followed free fn as a helper lambda even when the
    # node has no INIT-tier helpers). An empty ctx is harmless (emits nothing).
    helper_ctx = (_HelperCtx(_parse_helpers(helper_source),
                             _parse_module_consts(const_source))
                  if (helper_source or blessed or blessed_unpack or const_source)
                  else None)
    # Resolve module aliases from every source in view -- the compute itself, the
    # INIT-tier source (which `helper_source` already carries for all six
    # lowerers) and any followed helper unit.
    _import_srcs = [source]
    _import_srcs += ([helper_source] if isinstance(helper_source, str)
                     else list(helper_source or []))
    if isinstance(const_source, str):
        _import_srcs.append(const_source)
    imports, import_stars = _parse_import_bindings(_import_srcs)
    t = Transpiler(env, output_writers=output_writers, helper_ctx=helper_ctx,
                   state_vars=state_vars, blessed=blessed,
                   blessed_unpack=blessed_unpack,
                   side_effect_methods=side_effect_methods,
                   imports=imports, import_stars=import_stars)
    res = t.run_block(tree.body)
    helper_lines = list(helper_ctx.lines) if helper_ctx else []
    # expose the per-node persistent state members discovered during transpile
    # (name -> CppType) so the caller can declare the state-registry struct.
    res.state_members = dict(t.state_members)
    return res, t.written_outputs, helper_lines
