"""Blessed ``Transpile``-marker lowering builder (kernel-agnostic).

A blessed method whose ``lower`` is a :class:`Transpile` marker is lowered by
FOLLOWING and transpiling its pure-numpy free function -- the SAME function the
interpreted adapter runs (see ``_common/methods/skin_blend.py``) -- so the
interpreted node and the compiled ``deform()`` share one algorithm and no
skinning math is hand-written in C++. This is the deterministic parity-or-reject
path (never an AI port).

Contract between a ``Transpile`` MethodSpec and its free fn:

  * the free fn's positional parameters are ``(*user_args, *reads)`` -- the
    leading ``user_args`` are the values the compute passes at the call site;
    the trailing ``reads`` are bound, IN ORDER, to ``self.<name>`` for each
    ``name`` in ``MethodSpec.reads``. So ``reads`` MUST be ordered to match the
    free fn's trailing parameters.
  * the number of user args = ``len(params) - len(reads)``; the call site must
    supply exactly that many positional args (no keywords).

The shipped skin methods declare ``reads=()`` -- every operand is an explicit
call-site arg, e.g. ``self.linear_blend(rest, self.weightList, self.matrix,
self.bindPreMatrix)`` -- so the trailing-read binding is exercised only as the
degenerate empty case here; it remains for any method that opts into implicit
node reads.

The blessed callable evaluates the user args from the call node, pulls each read
from the transpiler env (materialised by the codegen because ``lower_deform``
unions the called method's ``reads`` into the used-attr set), and emits the free
fn as a monomorphised C++ helper lambda via ``Transpiler.emit_helper_call``.
Requiring every read to be present in the env is fail-closed: a missing binding
raises ``UnsupportedSpec`` (honest-reject) rather than silently diverging.
"""
from __future__ import annotations

import ast
import importlib
import inspect

from mpynode._common.interface import method_registry
from mpynode._common.interface.api_methods import NativeSideEffect, Transpile
from mpynode.native.compiler.errors import UnsupportedSpec
from mpynode.native.compiler.py_to_cpp import Val, env_cpp_name

# free-fn ref ("module:qualname") -> parsed ast.FunctionDef (parsed once).
_FDEF_CACHE: dict = {}


def _load_free_fn(ref):
    """Load + parse the ``module:qualname`` free fn into its ast.FunctionDef."""
    fdef = _FDEF_CACHE.get(ref)
    if fdef is not None:
        return fdef
    mod_name, _, qual = ref.partition(":")
    if not mod_name or not qual or "." in qual:
        raise UnsupportedSpec(
            "blessed Transpile: bad free-fn ref %r (want 'module:function')"
            % ref)
    try:
        mod = importlib.import_module(mod_name)
        fn  = getattr(mod, qual)
        src = inspect.getsource(fn)
    except (ImportError, AttributeError, OSError, TypeError) as e:
        raise UnsupportedSpec(
            "blessed Transpile: cannot follow free fn %r (%s)" % (ref, e))
    src = _dedent(src)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        raise UnsupportedSpec(
            "blessed Transpile: free fn %r did not parse (%s)" % (ref, e))
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == qual:
            _FDEF_CACHE[ref] = n
            return n
    raise UnsupportedSpec(
        "blessed Transpile: free fn %r not found in its module source" % ref)


def _dedent(src):
    """Left-strip common leading whitespace so a nested/def source parses."""
    lines   = src.splitlines()
    indents = [len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()]
    cut     = min(indents) if indents else 0
    return "\n".join(ln[cut:] if len(ln) >= cut else ln for ln in lines) + "\n"


def _called_self_methods(compute, names):
    """Subset of ``names`` invoked as ``self.<name>(...)`` in ``compute``."""
    called = set()
    try:
        tree = ast.parse(compute)
    except SyntaxError:
        return called
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "self" and n.func.attr in names):
            called.add(n.func.attr)
    return called


def _make_emit(spec):
    """Build the ``callable(tp, node) -> Val`` that lowers one blessed call."""
    ref   = spec.lower.free_fn
    reads = tuple(spec.reads)

    def _emit(tp, node):
        fdef     = _load_free_fn(ref)
        n_params = len(fdef.args.args)
        n_user   = n_params - len(reads)
        if n_user < 0:
            raise UnsupportedSpec(
                "blessed %r: free fn has fewer params than declared reads"
                % spec.name)
        args = tp._pos_args(node)
        if len(args) != n_user or node.keywords:
            raise UnsupportedSpec(
                "blessed %r: expected %d positional argument(s), got %d"
                % (spec.name, n_user, len(args) + len(node.keywords)))
        arg_vals = [tp.expr(a) for a in args]
        for name in reads:
            key = "self." + name
            typ = tp.env.get(key)
            if typ is None:
                raise UnsupportedSpec(
                    "blessed %r: read %r not bound in the compiled env"
                    % (spec.name, name))
            arg_vals.append(Val(env_cpp_name(key), typ))
        return tp.emit_helper_call(fdef.name, fdef, arg_vals, node)

    return _emit


def transpile_method_specs(type_name):
    """Every ``Transpile``-marker MethodSpec registered for ``type_name``."""
    return tuple(m for m in method_registry.methods_for_type(type_name)
                 if isinstance(m.lower, Transpile))


def called_method_reads(spec_dict):
    """Ordered-union of ``reads`` for the ``Transpile`` methods that
    ``spec_dict['compute']`` actually calls (empty for a non-blessed type).

    ``lower_deform`` unions these into its used-attr set so the codegen
    materialises the node reads the followed free fn needs -- the reads are
    consumed INSIDE the method, never spelled ``self.<read>`` in the compute."""
    type_name = spec_dict.get("mpy_type")
    specs     = transpile_method_specs(type_name)
    if not specs:
        return ()
    called = _called_self_methods(spec_dict.get("compute") or "",
                                  {m.name for m in specs})
    reads = []
    for m in specs:
        if m.name in called:
            for r in m.reads:
                if r not in reads:
                    reads.append(r)
    return tuple(reads)


def transpile_helper_sources(spec_dict):
    """Module source(s) of the followed free fns, so a free fn's SIBLING
    module-level helpers resolve as transpiler helper ``def``s.

    A ``Transpile`` free fn may call other top-level functions in its own module
    (e.g. ``twist_swing`` calls ``_twist_matrix`` / ``dual_quaternion`` /
    ``linear_blend`` in ``skin_blend.py``). ``emit_helper_call`` transpiles the
    followed fn's body, and any bare-name call inside it is resolved against the
    transpiler's helper pool (``_parse_helpers``). Feeding each followed fn's WHOLE
    module source in registers every sibling ``def`` in that pool. Deduped by
    module; empty for a non-blessed type / a compute that calls no blessed method,
    so every other node is unaffected. A self-contained free fn (LBS / DQS) simply
    calls none of the registered siblings, so nothing extra is emitted."""
    type_name = spec_dict.get("mpy_type")
    specs     = transpile_method_specs(type_name)
    if not specs:
        return []
    called = _called_self_methods(spec_dict.get("compute") or "",
                                  {m.name for m in specs})
    sources = []
    seen    = set()
    for m in specs:
        if m.name not in called:
            continue
        mod_name = m.lower.free_fn.partition(":")[0]
        if not mod_name or mod_name in seen:
            continue
        seen.add(mod_name)
        try:
            mod = importlib.import_module(mod_name)
            src = inspect.getsource(mod)
        except (ImportError, OSError, TypeError):
            continue
        if src and src.strip():
            sources.append(src)
    return sources


def side_effect_method_names(spec_dict):
    """Names of the ``NativeSideEffect`` blessed methods ``spec_dict['compute']``
    actually calls (empty for a non-blessed type / a compute that calls none).

    ``lower_deform`` passes these to ``transpile_compute_block`` so a bare
    ``self.<name>(...)`` statement lowers to nothing (the side effect is
    interactive-only; the compiled node omits it). A value-position use is NOT
    covered here -- py_to_cpp still rejects it, because there is no Val to make."""
    type_name = spec_dict.get("mpy_type")
    specs = tuple(m for m in method_registry.methods_for_type(type_name)
                  if isinstance(m.lower, NativeSideEffect))
    if not specs:
        return frozenset()
    called = _called_self_methods(spec_dict.get("compute") or "",
                                  {m.name for m in specs})
    return frozenset(called)


def make_transpile_lowerings(spec_dict):
    """Build ``(blessed, blessed_unpack)`` transpiler-callable dicts for the
    ``Transpile`` blessed methods ``spec_dict['compute']`` calls.

    Returns ``({}, {})`` for a non-blessed type / a compute that calls none, so
    every other node lowers exactly as before. ``blessed_unpack`` is always empty
    here: a ``Transpile`` method returns a single value used in expression
    position (tuple-unpack lowering is the CppKernel path's concern)."""
    type_name = spec_dict.get("mpy_type")
    specs     = transpile_method_specs(type_name)
    if not specs:
        return {}, {}
    called = _called_self_methods(spec_dict.get("compute") or "",
                                  {m.name for m in specs})
    blessed = {m.name: _make_emit(m) for m in specs if m.name in called}
    return blessed, {}
