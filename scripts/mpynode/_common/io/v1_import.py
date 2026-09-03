"""Read a v1 (``node-designer``) ``mPyNode`` out of a ``.ma`` and convert it.

v2 registers ``mPyNode`` under a different ``MTypeId`` than v1
(``0x00135700`` vs ``0x001255C3``), so a v1 scene does not open here and the
two plug-ins cannot be loaded in one Maya session. This module is what keeps
that break from throwing away every node anyone ever wrote with v1 -- the same
role ``2to3`` played for Python 3.

**It reads the FILE, never a live node.** That is the decision that makes the
whole thing possible without renaming v2's node type: v1's plug-in never has to
be loaded, so the ``mPyNode`` name collision never arises. A ``.ma`` is text and
all five of v1's data plugs are string-valued.

What a v1 node stores (measured, not inferred -- see
``docs/notes/v1-import.md``):

===================  ==========================  ==================
plug                 content                     encoding
===================  ==========================  ==================
``expression``       the single compute source   plain, .ma-escaped
``_inputAttrs``      ``{name: [type]}``          base64 + pickle
``_outputAttrs``     ``{name: [type]}``          base64 + pickle
``_storedVarNames``  ``[name, ...]``             base64 + pickle
``_storedVarsData``  ``{name: value}``           base64 + pickle
===================  ==========================  ==================

Two facts a naive reader gets wrong. v1 never compresses -- its ``_dumpPickle``
is plain ``base64(pickle.dumps(..., HIGHEST_PROTOCOL))``. And a single node can
carry MIXED pickle protocols, because real files were written across the
Python 2 -> 3 migration: the shipped ``quaternionSpineNode.ma`` has
``_inputAttrs`` at protocol 2 and ``_outputAttrs`` at protocol 4.

The conversion itself is three problems:

1. **Attributes** -- free. v1's 15 types are a strict subset of v2's 19, so
   names and types carry over unchanged.
2. **The expression** -- v1 exposed plugs as BARE LOCALS (``pivot``,
   ``outputTranslate = ...``); v2 uses ``self.pivot``. Rewritten by AST, never
   by text substitution, which would corrupt strings, comments and any local
   that happens to share a plug's name.
3. **The tier split** -- v1 had one blob; v2 wants imports and helper ``def``s
   in Init (whose names are bare globals in Compute) and the per-frame body in
   Compute.
"""
from __future__ import annotations

import ast
import codecs
import io
import pickle

# v1's identity, for reference and for error messages.
V1_NODE_TYPE = "mPyNode"
V1_TYPE_ID = "0x001255C3"

_EXPR_PLUG = "expression"
_PICKLE_PLUGS = ("_inputAttrs", "_outputAttrs", "_storedVarNames",
                 "_storedVarsData")


class V1ImportError(Exception):
    """A v1 node could not be read or converted."""


class V1Node(object):
    """One v1 ``mPyNode`` as it was found in the file."""

    def __init__(self, name):
        self.name = name
        self.expression = ""
        self.inputs = {}        # {name: type}
        self.outputs = {}       # {name: type}
        self.stored_vars = {}   # {name: value}

    @property
    def attr_names(self):
        return set(self.inputs) | set(self.outputs)

    def __repr__(self):
        return "<V1Node %r %din %dout %dvar %dch>" % (
            self.name, len(self.inputs), len(self.outputs),
            len(self.stored_vars), len(self.expression))


# ---------------------------------------------------------------------------
# .ma parsing
# ---------------------------------------------------------------------------

def _quoted(line):
    """The quoted literal on a ``.ma`` line, decoded.

    Bounded by the first and last double quote, then handed to
    ``ast.literal_eval`` -- Maya's escapes are C-style and so are Python's, and
    literal_eval gets ``\\n`` / ``\\"`` / ``\\\\`` right where a chain of
    ``str.replace`` calls does not.
    """
    j = line.rfind('"')
    if j < 0:
        return None
    # Scan BACK to the matching opening quote. Taking the first quote on the
    # line is wrong for a setAttr: `setAttr "._inputAttrs" -type "string"
    # "<payload>"` would yield the plug name and everything after it. A quote
    # is an opener only if an even number of backslashes precedes it.
    i = j - 1
    while i >= 0:
        if line[i] == '"':
            k = i - 1
            slashes = 0
            while k >= 0 and line[k] == chr(92):
                slashes += 1
                k -= 1
            if slashes % 2 == 0:
                break
        i -= 1
    if i < 0:
        return None
    try:
        return ast.literal_eval(line[i:j + 1])
    except Exception:
        return line[i + 1:j]


class _V1Object(object):
    """Stand-in for a v1 class found inside a pickled stored variable.

    Real files carry them: ``unitSphereCollisionNode.ma`` stores a list of
    ``mpylib._mpynode._openmaya.MPoint``. Unpickling those normally needs v1
    on sys.path, which is the one thing this importer refuses to require.

    Captures whatever the pickle hands it and demotes to a plain list of
    numbers, which is what v2 wants anyway -- its plug reads are numpy and
    Python natives, never Maya API objects.
    """

    def __init__(self, *args):
        self._args = list(args)

    def __setstate__(self, state):
        if isinstance(state, dict):
            self._args = list(state.values())
        elif isinstance(state, (list, tuple)):
            self._args = list(state)
        else:
            self._args = [state]

    def demote(self):
        flat = []
        for a in self._args:
            if isinstance(a, (list, tuple)):
                flat.extend(a)
            else:
                flat.append(a)
        return [x for x in flat if isinstance(x, (int, float))] or flat


def _demote(obj):
    """Recursively replace :class:`_V1Object` with plain data."""
    if isinstance(obj, _V1Object):
        return obj.demote()
    if isinstance(obj, dict):
        return {k: _demote(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        out = [_demote(v) for v in obj]
        return out if isinstance(obj, list) else tuple(out)
    return obj


class _V1Unpickler(pickle.Unpickler):
    """Unpickler that tolerates v1's own classes and refuses surprises.

    Doubles as a safety measure: v1 data is untrusted input, and allowing an
    explicit set of modules is far better than letting ``pickle.loads`` import
    anything it is told to.
    """

    _ALLOWED = {"builtins", "copyreg", "collections", "numpy",
                "numpy.core.multiarray", "numpy._core.multiarray"}

    def find_class(self, module, name):
        if module.split(".")[0] == "mpylib":
            return _V1Object
        root = module.split(".")[0]
        if module in self._ALLOWED or root in ("numpy", "builtins"):
            return super().find_class(module, name)
        raise V1ImportError(
            "v1 data references %s.%s, which this importer will not import"
            % (module, name))


def _unpickle_b64(payload):
    """Decode one of v1's base64+pickle plugs. Protocol-agnostic."""
    if not payload:
        return None
    clean = "".join(payload.split())
    try:
        raw = codecs.decode(clean.encode(), "base64")
        return _demote(_V1Unpickler(io.BytesIO(raw)).load())
    except V1ImportError:
        raise
    except Exception as exc:
        raise V1ImportError("could not decode a v1 payload: %s" % exc)


def _store(node, plug, payload):
    """Assign one decoded plug payload onto ``node``."""
    if plug == _EXPR_PLUG:
        node.expression = payload or ""
        return
    obj = _unpickle_b64(payload)
    if plug == "_inputAttrs" and isinstance(obj, dict):
        node.inputs = {k: (v[0] if isinstance(v, (list, tuple)) and v else v)
                       for k, v in obj.items()}
    elif plug == "_outputAttrs" and isinstance(obj, dict):
        node.outputs = {k: (v[0] if isinstance(v, (list, tuple)) and v else v)
                        for k, v in obj.items()}
    elif plug == "_storedVarsData" and isinstance(obj, dict):
        node.stored_vars = dict(obj)


def read_v1_ma(path):
    """Every v1 ``mPyNode`` in ``path``, as :class:`V1Node` objects.

    Line-oriented rather than regex: a ``.ma`` is a MEL script and its string
    literals routinely contain quotes, brackets and backslashes that make
    pattern matching fragile.

    ANY of the five string plugs may be written on one line or split across
    many. Maya wraps a long value as ``setAttr ".x" -type "string" (`` followed
    by quoted fragments joined by ``+``. It does NOT emit a reliable closing
    ``);`` line -- the final fragment and the paren share a line and the next
    ``setAttr`` follows immediately -- so a continuation run ends at the first
    line that is not a fragment, and that line still has to be processed.
    """
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    nodes, cur, pending = [], None, None
    plugs = (_EXPR_PLUG,) + _PICKLE_PLUGS

    for line in lines:
        s = line.strip()

        if pending is not None:
            if s.startswith('"') or s.startswith("+"):
                frag = _quoted(s)
                if frag is not None:
                    pending[1].append(frag)
                continue
            _store(cur, pending[0], "".join(pending[1]))
            pending = None
            # fall through -- this line is real content

        if s.startswith("createNode "):
            parts = s.split()
            cur = None
            if len(parts) > 1 and parts[1] == V1_NODE_TYPE:
                cur = V1Node((s.split('"')[1] if '"' in s else "") or "mPyNode1")
                nodes.append(cur)
            continue

        if cur is None or not s.startswith("setAttr "):
            continue

        for plug in plugs:
            if not s.startswith('setAttr ".%s"' % plug):
                continue
            if s.rstrip().endswith("("):
                pending = (plug, [])
            else:
                _store(cur, plug, _quoted(s))
            break

    if pending is not None and cur is not None:
        _store(cur, pending[0], "".join(pending[1]))

    # v1's _loadPickle ends in a bare `except: pass`, so a corrupt payload
    # reads as empty rather than as an error. An expression with no attributes
    # is far more likely to be that than a genuinely attribute-less node.
    for n in nodes:
        if n.expression.strip() and not n.attr_names:
            raise V1ImportError(
                "%r has a %d-character expression but no attributes; its "
                "attr payloads are probably corrupt (v1 fails silently here)"
                % (n.name, len(n.expression)))
    return nodes


# ---------------------------------------------------------------------------
# Expression conversion
# ---------------------------------------------------------------------------

class _ScopeBinds(ast.NodeVisitor):
    """Names bound locally in ONE scope -- assignment targets, loop and with
    targets, comprehension targets, parameters, imports, def/class names.

    Used to spot a plug name the expression shadows. v1's semantics are that
    assigning to an input name makes a plain local and does NOT write the plug,
    so a shadowed name must be left alone rather than rewritten.
    """

    def __init__(self):
        self.bound = set()

    def _targets(self, node):
        for t in ast.walk(node):
            if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
                self.bound.add(t.id)

    def visit_Assign(self, node):
        for t in node.targets:
            self._targets(t)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._targets(node.target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._targets(node.target)
        self.generic_visit(node)

    def visit_For(self, node):
        self._targets(node.target)
        self.generic_visit(node)

    def visit_withitem(self, node):
        if node.optional_vars is not None:
            self._targets(node.optional_vars)
        self.generic_visit(node)

    def _alias(self, node):
        for a in node.names:
            self.bound.add((a.asname or a.name).split(".")[0])

    visit_Import = _alias
    visit_ImportFrom = _alias

    def visit_FunctionDef(self, node):
        self.bound.add(node.name)      # the name, not the body's scope

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.bound.add(node.name)


class _Selfify(ast.NodeTransformer):
    """Rewrite bare plug names to ``self.<name>``.

    ``outputs`` are rewritten even when assigned -- that assignment IS the plug
    write, and it is the whole point. ``inputs`` are rewritten only when the
    module scope does not also bind the name, because in v1 assigning to an
    input shadowed it locally rather than writing the plug.
    """

    def __init__(self, rewrite, skipped):
        self.rewrite = rewrite
        self.skipped = skipped
        self.hits = 0

    def visit_Name(self, node):
        if node.id not in self.rewrite:
            return node
        self.hits += 1
        return ast.copy_location(
            ast.Attribute(value=ast.copy_location(
                ast.Name(id="self", ctx=ast.Load()), node),
                attr=node.id, ctx=node.ctx), node)


def _globals_used_in_defs(tree, names):
    """Plug names a top-level ``def`` reads as a global.

    A v1 helper could see plug values because they were module-level locals in
    the exec namespace. In v2 helpers live in Init, which cannot see ``self``,
    so every one of these is a conversion the user has to finish by hand.
    """
    out = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = _ScopeBinds()
        for st in node.body:
            local.visit(st)
        params = {a.arg for a in node.args.args + node.args.kwonlyargs}
        if node.args.vararg:
            params.add(node.args.vararg.arg)
        if node.args.kwarg:
            params.add(node.args.kwarg.arg)
        for sub in ast.walk(node):
            if (isinstance(sub, ast.Name) and sub.id in names
                    and sub.id not in local.bound and sub.id not in params):
                out.add(sub.id)
    return out


# ---------------------------------------------------------------------------
# v1 -> v2 type mismatches the converter can fix outright
# ---------------------------------------------------------------------------
#
# Two of these show up in nearly every non-trivial v1 node, and both are
# invisible until the node evaluates. Measured on quaternionSpineNode: fixing
# the first merely reveals the second, and the node runs clean once both are
# done -- four edit sites in 52 lines.
#
#   1. A matrix plug read used to be an ``MMatrix``. In v2 it is a
#      ``MatrixView``, so ``om.MTransformationMatrix(self.someMatrix)`` raises
#      ``ValueError: MTransformationMatrix : no matching constructor found``.
#      MatrixView carries the conversion itself.
#
#   2. An ``MPoint`` has FOUR components. v1 accepted one for a 3-component
#      plug and quietly used x/y/z; v2 hands numpy, which refuses with
#      ``could not broadcast input array from shape (4,) into shape (3,)``.

_MATRIX_CTORS = {"MMatrix": "asMatrix",
                 "MTransformationMatrix": "asTransformationMatrix"}

# Plug types that take exactly three components.
_VEC3_TYPES = ("vector", "color", "euler")

# Plug types v1 handed back WRAPPED in a unit object rather than as a number:
# DEFAULT_ANGLE = MAngle and DEFAULT_TIME = MTime in v1's node module. Both
# expose the number as `.value`. v2 hands the number directly, so the extra
# hop raises `AttributeError: 'float' object has no attribute 'value'`.
_UNIT_WRAPPED_TYPES = ("time", "angle")

_VEC3_SHIM = "_v1_vec3"

# Built line-by-line rather than as one literal so the docstring inside it
# needs no quote gymnastics.
_VEC3_SHIM_SRC = chr(10).join([
    "def _v1_vec3(v):",
    '    """Added by the v1 importer; safe to delete once the maths is tidied.',
    "",
    "    v1 accepted a 4-component MPoint where a 3-component plug was",
    "    expected and quietly used x/y/z. v2 hands numpy, which refuses the",
    "    shape. Anything already 3 long (or not a sequence at all) passes",
    '    through untouched."""',
    "    try:",
    "        seq = list(v)",
    "    except TypeError:",
    "        return v",
    "    return seq[:3] if len(seq) > 3 else v",
])


def _plug_of(node):
    """The plug name a ``self.``-rooted expression refers to, or None.

    Accepts ``self.<n>`` and ``self.<n>[...]`` alike: an element of a matrix
    ARRAY plug is a MatrixView exactly as a single matrix plug is, and an
    element of a vector array takes three components exactly as a single
    vector plug does.
    """
    if isinstance(node, ast.Subscript):
        node = node.value
    if (isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"):
        return node.attr
    return None


class _ApiTypeFix(ast.NodeTransformer):
    """Rewrites the two mismatches above. Runs AFTER :class:`_Selfify`,
    because it recognises plug access by the ``self.`` prefix that pass
    installs.

    Both rules are driven by the DECLARED attribute type rather than by
    inferring what an expression evaluates to -- the declared type is ground
    truth from ``_inputAttrs`` / ``_outputAttrs``, so neither rule can fire on
    something that merely looks like a plug.
    """

    def __init__(self, types):
        self.types = types
        self.matrix_fixes = []
        self.vec3_fixes = []
        self.vec_ctor_fixes = []
        self.eval_fixes = []
        self.time_fixes = []

    def _is_matrix_plug(self, node):
        name = _plug_of(node)
        return name is not None and self.types.get(name) == "matrix"

    def visit_Call(self, node):
        self.generic_visit(node)
        # Both the qualified `om.MMatrix(...)` and the bare `MMatrix(...)`
        # form, because v1 made those names ambient in the expression
        # namespace and real v1 nodes use both.
        if (isinstance(node.func, ast.Name)
                and node.func.id in ("eval", "exec")
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            # gameOfLifeNode really does `getattr(self, 'boardX') ==
            # eval('boardX')`. Under v1 the bare name resolved because plugs
            # were locals in the exec namespace; under v2 it is a NameError
            # that _Selfify cannot reach, the name being inside a string
            # literal. Rewriting the STRING is exact, and only done when the
            # whole thing is a declared plug name -- never for arbitrary
            # expressions, where `self.` might not be the right prefix.
            want = node.args[0].value.strip()
            if want in self.types:
                self.eval_fixes.append(want)
                return ast.Call(
                    func=node.func,
                    args=[ast.Constant(value="self." + want)],
                    keywords=node.keywords)
            return node

        if isinstance(node.func, ast.Name):
            ctor = node.func.id
            # Bare == v1-ambient == undefined under v2. `om.MVector(...)` is
            # a real api2 call and falls through untouched.
            if ctor in _V1_VEC_CTORS:
                self.vec_ctor_fixes.append(ctor)
                return ast.Call(
                    func=ast.Name(id=_V1_VEC, ctx=ast.Load()),
                    args=node.args, keywords=node.keywords)
        elif isinstance(node.func, ast.Attribute):
            ctor = node.func.attr
        else:
            return node
        method = _MATRIX_CTORS.get(ctor)
        if (method is None or len(node.args) != 1 or node.keywords
                or not self._is_matrix_plug(node.args[0])):
            return node
        self.matrix_fixes.append("%s(%s) -> .%s()"
                                 % (ctor, _plug_of(node.args[0]), method))
        return ast.Call(
            func=ast.Attribute(value=node.args[0], attr=method,
                               ctx=ast.Load()),
            args=[], keywords=[])

    def visit_Attribute(self, node):
        """``self.<time plug>.value`` -> ``self.<time plug>``.

        v1 handed a ``time`` plug back as an ``MTime`` and an ``angle`` plug
        as an ``MAngle``, both of which expose the number as ``.value``. v2
        hands the number directly, so the extra hop raises
        ``AttributeError: 'float' object has no attribute 'value'`` --
        gameOfLifeNode hit it on a time plug, ouchNode on an angle plug, and
        the message is completely opaque until you know v1 wrapped the value.
        """
        self.generic_visit(node)
        if node.attr != "value":
            return node
        name = _plug_of(node.value)
        if name is None or self.types.get(name) not in _UNIT_WRAPPED_TYPES:
            return node
        self.time_fixes.append(name)
        return node.value

    def visit_Assign(self, node):
        self.generic_visit(node)
        if len(node.targets) != 1:
            return node
        name = _plug_of(node.targets[0])
        if name is None or self.types.get(name) not in _VEC3_TYPES:
            return node
        # A 3-element display is already the right shape and is the common
        # case; wrapping it would be pure noise.
        if (isinstance(node.value, (ast.List, ast.Tuple))
                and len(node.value.elts) == 3):
            return node
        if (isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id in (_VEC3_SHIM, _V1_VEC)):
            return node
        self.vec3_fixes.append(name)
        node.value = ast.Call(func=ast.Name(id=_VEC3_SHIM, ctx=ast.Load()),
                              args=[node.value], keywords=[])
        return node


# v1's own library. It cannot be satisfied under v2 -- and deliberately so:
# v2 does not make api objects ambient, which was an explicit design decision
# rather than an omission. Four of the nine upstream examples do
# ``from mpylib import MVector`` or ``MPoint``.
#
# Leaving such an import in place is much worse than dropping it, because Init
# is ALL-OR-NOTHING: the ModuleNotFoundError aborts the whole Init exec, so
# every other Init name -- imports, helper defs, the _v1_vec3 shim -- vanishes
# too, and the error Compute reports is whichever of those names it happens to
# reach first. That trail points nowhere near the real cause. Dropping the
# import localises the failure to the actual use of MVector, which the report
# already explains.
_V1_LIB_ROOTS = ("mpylib",)

# Third-party extensions a v1 expression may import that v2 does not require
# and cannot assume. NOT dropped -- unlike mpylib these can legitimately be
# installed -- but reported, with the v2 route named, because the failure is
# otherwise a bare ModuleNotFoundError with no hint that an answer exists.
_V1_THIRD_PARTY = {
    "pyaudio": "v1_compat.play_pcm plays raw PCM through Qt without it, "
               "asynchronously, so the background thread goes too",
}


def _v1_lib_module(stmt):
    """The v1-library module a statement imports from, or None."""
    if isinstance(stmt, ast.ImportFrom):
        mod = stmt.module or ""
        return mod if mod.split(".")[0] in _V1_LIB_ROOTS else None
    if isinstance(stmt, ast.Import):
        for alias in stmt.names:
            if alias.name.split(".")[0] in _V1_LIB_ROOTS:
                return alias.name
    return None


def _strip_v1_lib_import(stmt):
    """``(kept_stmt_or_None, description)`` for one import statement.

    ``import mpylib, math`` keeps the ``math`` half rather than throwing the
    line away, so an unrelated import is never collateral damage.
    """
    mod = _v1_lib_module(stmt)
    if mod is None:
        return stmt, None
    bound = ", ".join(a.asname or a.name for a in stmt.names)
    if isinstance(stmt, ast.ImportFrom):
        return None, "from %s import %s" % (mod, bound)
    survivors = [a for a in stmt.names
                 if a.name.split(".")[0] not in _V1_LIB_ROOTS]
    dead = ", ".join(a.asname or a.name for a in stmt.names
                     if a.name.split(".")[0] in _V1_LIB_ROOTS)
    if survivors:
        stmt.names = survivors
        return stmt, "import %s" % dead
    return None, "import %s" % dead


def _nested_v1_lib_imports(tree):
    """v1-library imports inside a def/class, reported but NOT removed.

    One of these fails when its function is CALLED, not during Init, so it
    does not take the namespace down with it -- and removing it could leave an
    empty function body. Reporting is enough.
    """
    top = set(id(s) for s in tree.body)
    out = []
    for node in ast.walk(tree):
        if id(node) in top:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = _v1_lib_module(node)
            if mod:
                out.append(mod)
    return sorted(set(out))


# v1's ambient vector/point constructors. Every BARE (unqualified) call to
# one of these in the whole upstream corpus takes scalar arguments --
# MVector(0, 0, 0), MVector(1, 1, 1), MVector(p[0], p[1], 0),
# MPoint(0, 0, 0, 1), MPoint(x, 0, z, 1) -- so they are plain 3- and
# 4-component holders, and a numpy array does the same arithmetic.
#
# Only the bare form is rewritten. `om.MVector(...)` is a real api2 call that
# works fine under v2 and is left exactly as written.
#
# This does NOT resurrect v1's ambient api objects, which v2 deliberately does
# not seed: the shim is a visible, deletable function in Init that returns
# numpy, not a re-export of MVector.
_V1_VEC_CTORS = ("MVector", "MPoint")

_V1_VEC = "_v1_vec"

# One explicit import, not ~90 lines of injected class source. The type
# has to live in a real module because stored variables are PICKLED: v1
# nodes keep buffers of vectors (springChain velocity/position,
# unitSphereCollision a point grid), and a class defined by exec-ing Init
# source has no importable path, so its instances cannot round-trip.
_V1_VEC_SHIM_SRC = (
    "from mpynode._common.io.v1_compat import v1_vec as _v1_vec"
)


def split_and_selfify(expression, inputs, outputs):
    """``(init_src, compute_src, report)`` for one v1 expression.

    Imports and top-level ``def``/``class`` go to Init -- whose names are bare
    globals in Compute -- and everything else stays in Compute, in order.
    Anything ambiguous stays in Compute: that only costs per-evaluation work,
    where guessing the other way breaks the node.
    """
    report = {"shadowed": [], "globals_in_defs": [], "rewrites": 0,
              "init_stmts": 0, "compute_stmts": 0,
              "matrix_view_fixes": [], "vec3_fixes": [],
              "vec_ctor_fixes": [], "eval_fixes": [], "time_fixes": [],
              "dead_imports": [], "third_party_imports": []}
    try:
        tree = ast.parse(expression)
    except SyntaxError as exc:
        raise V1ImportError("v1 expression does not parse: %s" % exc)

    names = set(inputs) | set(outputs)

    top = _ScopeBinds()
    for st in tree.body:
        top.visit(st)
    # An input the module also binds was a local shadow in v1; leave it bare.
    shadowed = (set(inputs) & top.bound) - set(outputs)
    report["shadowed"] = sorted(shadowed)
    report["globals_in_defs"] = sorted(_globals_used_in_defs(tree, names))

    dead = list(_nested_v1_lib_imports(tree))

    init_body, compute_body = [], []
    for st in tree.body:
        if isinstance(st, (ast.Import, ast.ImportFrom)):
            kept, dropped = _strip_v1_lib_import(st)
            if dropped:
                dead.append(dropped)
            if kept is not None:
                init_body.append(kept)
            continue
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef)):
            init_body.append(st)
        else:
            compute_body.append(st)
    report["dead_imports"] = sorted(set(dead))
    report["third_party_imports"] = sorted(
        {a.name.split(".")[0] for st in tree.body
         if isinstance(st, (ast.Import, ast.ImportFrom))
         for a in st.names
         if a.name.split(".")[0] in _V1_THIRD_PARTY}
        | {(st.module or "").split(".")[0] for st in tree.body
           if isinstance(st, ast.ImportFrom)
           and (st.module or "").split(".")[0] in _V1_THIRD_PARTY})

    xf = _Selfify(names - shadowed, shadowed)
    body = [xf.visit(s) for s in compute_body]

    # Now that plug access wears a `self.` prefix, the declared types can be
    # used to repair the two v1/v2 type mismatches outright. Ordering is not
    # optional: _ApiTypeFix recognises a plug by that prefix.
    types = dict(inputs)
    types.update(outputs)
    fix = _ApiTypeFix(types)
    body = [fix.visit(s) for s in body]

    # Init too. A top-level def is partitioned into Init before any rewriting
    # happens, so a helper that builds its own MVector -- springChainNode's
    # `spring()` does, twice -- kept a name that does not exist under v2.
    # Deliberately AFTER the compute pass and with the SAME instance, so the
    # counters cover both halves.
    init_body = [fix.visit(s) for s in init_body]
    report["matrix_view_fixes"] = list(fix.matrix_fixes)
    report["vec3_fixes"] = sorted(set(fix.vec3_fixes))
    report["vec_ctor_fixes"] = sorted(set(fix.vec_ctor_fixes))
    report["eval_fixes"] = sorted(set(fix.eval_fixes))
    report["time_fixes"] = sorted(set(fix.time_fixes))

    # The shim goes in Init, whose names are bare globals in Compute -- and
    # only when something actually needs it, so a node that does not gets no
    # mystery function to wonder about.
    if fix.vec_ctor_fixes:
        init_body = list(ast.parse(_V1_VEC_SHIM_SRC).body) + init_body
    if fix.vec3_fixes:
        init_body = list(ast.parse(_VEC3_SHIM_SRC).body) + init_body

    # A shadowed input is left bare -- but it still has to START as the plug
    # value, because v1 pre-populated the namespace and the expression may read
    # the name BEFORE it assigns to it. Leaving it bare alone raises NameError
    # (splineNode's `degree` did exactly that). Prepending `name = self.name`
    # reproduces v1 precisely: the plug value up front, and any later
    # assignment shadows it locally from that point on.
    for nm in sorted(shadowed):
        alias = ast.Assign(
            targets=[ast.Name(id=nm, ctx=ast.Store())],
            value=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                                attr=nm, ctx=ast.Load()))
        body.insert(0, alias)

    compute_mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(compute_mod)
    report["rewrites"] = xf.hits
    report["init_stmts"] = len(init_body)
    report["compute_stmts"] = len(compute_body)

    init_mod = ast.Module(body=init_body, type_ignores=[])
    ast.fix_missing_locations(init_mod)

    return ast.unparse(init_mod), ast.unparse(compute_mod), report


# ---------------------------------------------------------------------------
# Enum field names
# ---------------------------------------------------------------------------

def synth_enum_names(attr, expression, minimum=2):
    """Field labels for a v1 enum, which stored none.

    v1 wrote ``['enum']`` and nothing else, so the labels are simply not in the
    file -- and v2 rejects an enum with no ``enum_names``. Recover the COUNT
    from the expression by looking at what the attribute is compared against
    (``if scaleMethod == 2``), and label them by index. Wrong names are
    obvious and one rename away; a wrong COUNT silently clamps the plug, so
    err high.
    """
    highest = minimum - 1
    try:
        tree = ast.parse(expression)
    except SyntaxError:
        return [str(i) for i in range(minimum)]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left] + list(node.comparators)
        mentions = any(isinstance(s, ast.Name) and s.id == attr
                       or isinstance(s, ast.Attribute) and s.attr == attr
                       for s in sides)
        if not mentions:
            continue
        for s in sides:
            if isinstance(s, ast.Constant) and isinstance(s.value, int):
                highest = max(highest, s.value)
    return [str(i) for i in range(max(minimum, highest + 1))]


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

# Names v1 made ambient in the expression namespace, and which also carry a
# value model v2 does not share. v1 handed plug values as its own MPoint /
# MVector / MMatrix shims, so expressions do arithmetic ON them; v2 hands numpy
# and MatrixView. `MPoint * MatrixView` and `MVector(numpy_row)` therefore stop
# type-checking. That is not something a converter can guess its way through --
# it is a rewrite of the maths -- so it is reported instead.
_V1_AMBIENT = ("MPoint", "MVector", "MMatrix", "MQuaternion", "MEulerRotation")


def _api_object_use(src):
    """v1 API-shim names used in converted source. Sorted, deduped."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    hits = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _V1_AMBIENT:
            hits.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in _V1_AMBIENT:
            hits.add(node.attr)
    return sorted(hits)


def convert(v1):
    """A v1 node -> the pieces v2 needs, plus a report of what was inexact."""
    from mpynode._common.io import v1_compat
    init_src, compute_src, report = split_and_selfify(
        v1.expression, v1.inputs, v1.outputs)

    enums = {}
    for name, typ in list(v1.inputs.items()) + list(v1.outputs.items()):
        if typ == "enum":
            enums[name] = synth_enum_names(name, v1.expression)

    api_use = _api_object_use(init_src + chr(10) + compute_src)

    report.update({
        "api_objects": api_use,
        "needs_hand_finish": bool(api_use),
        "name": v1.name,
        "inputs": dict(v1.inputs),
        "outputs": dict(v1.outputs),
        # Demoted v1 vectors become V1Vec so they can be computed with.
        # The restricted unpickler maps v1's classes to plain lists, which is
        # right for reading a file without v1 installed and wrong for
        # arithmetic: `float * [0.0, 0.0, 0.0]` raises, and a list has no
        # distanceTo and no matrix multiply. springChainNode and
        # unitSphereCollisionNode failed on exactly that, from their SAVED
        # buffers rather than from anything in the expression.
        "stored_vars": v1_compat.coerce_stored(dict(v1.stored_vars)),
        "synthesized_enums": enums,
        "init": init_src,
        "compute": compute_src,
    })
    return report


def build_node(spec, name=None):
    """Create the v2 node described by :func:`convert`'s output. Maya only."""
    from mpynode import MPyNode

    node = MPyNode.create(name=name or spec["name"] or "importedV1Node")
    for attr, typ in spec["inputs"].items():
        kw = {}
        if typ == "enum":
            kw["enum_names"] = spec["synthesized_enums"].get(attr) or ["0", "1"]
        node.add_input_attr(attr, typ, **kw)
    for attr, typ in spec["outputs"].items():
        kw = {}
        if typ == "enum":
            kw["enum_names"] = spec["synthesized_enums"].get(attr) or ["0", "1"]
        node.add_output_attr(attr, typ, **kw)
    for var, value in spec["stored_vars"].items():
        node.set_variable(var, value, persistent=True)
    if spec["init"].strip():
        node.set_init_expression(spec["init"])
    node.set_compute_expression(spec["compute"])
    return node


def import_v1_ma(path, build=True):
    """Read every v1 node in ``path`` and (optionally) build the v2 equivalent.

    Returns one report per node. The report is the deliverable as much as the
    node is: a silent 90% conversion is worse than a noisy one, because the
    10% is exactly what the user has to go and finish.
    """
    out = []
    for v1 in read_v1_ma(path):
        spec = convert(v1)
        if build:
            spec["built"] = build_node(spec).get_name()
        out.append(spec)
    return out
