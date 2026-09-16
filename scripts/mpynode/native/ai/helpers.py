"""Followed-import helper translation + shareability analysis + translate-once memo.

A pure-Python helper several nodes call is translated ONCE into a named C++
free function and emitted as a marked file-scope block; the bundler hoists the
unique set into one shared_helpers.cpp so it compiles ONCE instead of being
embedded per node. SCALAR helpers get a fixed ``double f(double, ...)`` proto
derived statically; NON-scalar helpers (vector/array/matrix in or out) let the
LLM CHOOSE a typed proto (reported on a PROTO: line, parsed + memoized so every
node shares the identical signature). A helper that can't be either (class,
*args/**kwargs/defaults, dict/set, a param called as a function) disqualifies
the node, which then keeps the robust INLINE path -- so this is purely additive.
"""

from __future__ import annotations

import ast
import hashlib
import re

from .prompt import _SYSTEM_HELPER, _strip_fences


# Process-level translate-once cache: deterministic helper name -> result dict.
# Spans one compile run's port_node calls, so a helper shared by N nodes is
# translated once and every node embeds the SAME text (which lets the bundler
# dedup it). Keyed by the source-derived name, so identical helpers hit.
_HELPER_MEMO: dict = {}


def reset_helper_memo() -> None:
    """Clear the translate-once cache (tests; or to force re-translation)."""
    _HELPER_MEMO.clear()


class _HelperProtoError(Exception):
    """A non-scalar helper translation produced no usable signature.

    Raised when the LLM omits the ``PROTO:`` line or chooses a prototype that
    doesn't use the required (content-hashed) name. ``port_node`` catches it and
    drops the whole node to the robust INLINE path -- so a bad typed translation
    never emits a marked block whose proto we can't trust."""


def _helper_symbol(module: str, name: str, source: str) -> str:
    digest = hashlib.sha1(
        ("%s\0%s\0%s" % (module, name, source)).encode("utf-8")).hexdigest()
    return "mpyh_" + digest[:12]


# C++ reserved words: a Python param named like one of these can't become a
# `double <name>` parameter -> such a helper keeps the inline path.
_CPP_KEYWORDS = frozenset((
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char "
    "char8_t char16_t char32_t class compl concept const consteval constexpr "
    "constinit const_cast continue co_await co_return co_yield decltype default "
    "delete do double dynamic_cast else enum explicit export extern false float "
    "for friend goto if inline int long mutable namespace new noexcept not not_eq "
    "nullptr operator or or_eq private protected public register reinterpret_cast "
    "requires return short signed sizeof static static_assert static_cast struct "
    "switch template this thread_local throw true try typedef typeid typename "
    "union unsigned using virtual void volatile wchar_t while xor xor_eq").split())

# Builtins that consume an ITERABLE -- a param passed to one of these is not a
# scalar, so the helper can't be a scalar-double free function.
_NON_SCALAR_BUILTINS = frozenset((
    "len sum sorted any all enumerate zip reversed iter list tuple set dict "
    "frozenset map filter").split())


def _scalar_safe(fn: ast.FunctionDef) -> bool:
    """True iff every parameter is used only as a scalar and the function returns
    a scalar -- a conservative static check. Anything non-scalar (subscript,
    attribute, iteration, len/sum/..., container return, calling a param, np.*)
    disqualifies, routing the helper to the inline path. Erring toward False is
    safe (inline still works); a false True would emit mis-typed C++."""
    params = set()
    a      = fn.args
    for p in list(getattr(a, "posonlyargs", [])) + list(a.args):
        params.add(p.arg)

    def _is_param(node):
        return isinstance(node, ast.Name) and node.id in params

    for node in ast.walk(fn):
        # p[...]  /  p.attr  /  *p  -> p is not a scalar
        if isinstance(node, ast.Subscript) and _is_param(node.value):
            return False
        if isinstance(node, ast.Attribute) and _is_param(node.value):
            return False
        if isinstance(node, ast.Starred) and _is_param(node.value):
            return False
        # for v in p:  /  [.. for v in p]
        if isinstance(node, ast.For) and _is_param(node.iter):
            return False
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                             ast.GeneratorExp)):
            for gen in node.generators:
                if _is_param(gen.iter):
                    return False
        if isinstance(node, ast.Call):
            # calling a parameter as a function
            if _is_param(node.func):
                return False
            fname = (node.func.id if isinstance(node.func, ast.Name)
                     else node.func.attr if isinstance(node.func, ast.Attribute)
                     else None)
            # np.<anything>(param) / param.method() -> non-scalar
            if isinstance(node.func, ast.Attribute) and _is_param(node.func.value):
                return False
            arg_is_param = any(_is_param(arg) for arg in node.args)
            if fname in _NON_SCALAR_BUILTINS and arg_is_param:
                return False
            # min(p)/max(p) with a single param arg == reduce over an iterable
            # (min(a, b) with two scalar args is fine).
            if fname in ("min", "max") and len(node.args) == 1 \
                    and _is_param(node.args[0]):
                return False
        # returning a container is a non-scalar return
        if isinstance(node, ast.Return) and isinstance(
                node.value, (ast.List, ast.Tuple, ast.Dict, ast.Set,
                             ast.ListComp, ast.SetComp, ast.DictComp)):
            return False
    return True


def _parse_unit_fn(unit: dict):
    """The top-level ``FunctionDef`` named ``unit['name']`` in its source, or None
    (a class, a syntax error, or a def not found under that name)."""
    try:
        tree = ast.parse(unit.get("source") or "")
    except Exception:
        return None
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == unit.get("name"):
            return n
    return None


def _structurally_shareable(fn: ast.FunctionDef) -> bool:
    """Disqualifiers shared by BOTH the scalar and non-scalar paths: a variadic /
    keyword / default-bearing signature, or a parameter named like a C++ keyword.
    These can't become a fixed C++ free-function parameter list either way."""
    a = fn.args
    if (a.vararg or a.kwarg or a.kwonlyargs or a.defaults or a.kw_defaults):
        return False
    pos = list(getattr(a, "posonlyargs", [])) + list(a.args)
    if any(p.arg in _CPP_KEYWORDS for p in pos):
        return False
    return True


def _derive_scalar_proto(unit: dict):
    """``(c_name, c_proto)`` for a scalar-``double`` free function mirroring this
    helper, or None if it can't be one. None means "not scalar-shareable" -> the
    caller tries the non-scalar path, else keeps the inline path.

    Disqualifiers: not a plain top-level def (class); *args/**kwargs/kwonly/
    defaults; a parameter named like a C++ keyword; or any non-scalar use of a
    parameter / non-scalar return (see :func:`_scalar_safe`)."""
    fn = _parse_unit_fn(unit)
    if fn is None:
        return None  # a class, or the def isn't top-level under this name
    if not _structurally_shareable(fn):
        return None
    if not _scalar_safe(fn):
        return None
    pos    = list(getattr(fn.args, "posonlyargs", [])) + list(fn.args.args)
    c_name = _helper_symbol(unit["module"], unit["name"], unit["source"])
    params = ", ".join("double %s" % p.arg for p in pos)
    return c_name, "double %s(%s)" % (c_name, params)


def _nonscalar_shareable(fn: ast.FunctionDef) -> bool:
    """True iff this helper CAN be shared with an LLM-chosen typed (non-scalar)
    signature -- a relaxed twin of :func:`_scalar_safe`. Subscript / attribute /
    iteration / len/sum / np.* / comprehensions over a parameter and list/tuple
    returns are ALLOWED (they map to MVector / std::vector). Still rejected:
    a variadic/keyword/default signature or C++-keyword param
    (:func:`_structurally_shareable`), calling a parameter as a function, and a
    dict/set return (an untyped container we won't map). Erring toward False is
    safe -- the node then keeps the (correct) inline path."""
    if not _structurally_shareable(fn):
        return False
    params = {p.arg for p in
              list(getattr(fn.args, "posonlyargs", [])) + list(fn.args.args)}

    def _is_param(node):
        return isinstance(node, ast.Name) and node.id in params

    for node in ast.walk(fn):
        # calling a parameter as a function -> can't give it a C++ type.
        if isinstance(node, ast.Call) and _is_param(node.func):
            return False
        # returning a dict/set (or a dict/set comprehension) -> not mappable.
        if isinstance(node, ast.Return) and isinstance(
                node.value, (ast.Dict, ast.Set, ast.DictComp, ast.SetComp)):
            return False
    return True


def _shareable_helper_units(spec: dict) -> list:
    """Followed helpers that can be shared, as
    ``[{module, sym, source, name, proto, kind}]``. Empty if there are none OR if
    ANY helper isn't shareable at all (the node then keeps the inline path -- no
    partial sharing, which keeps the shared/inline decision per-node and simple).

    Each unit is tagged ``kind``: ``'scalar'`` keeps a statically-derived
    ``double f(double, ...)`` proto (byte-identical to before); ``'nonscalar'``
    leaves ``proto=None`` for the LLM to choose a typed signature at translate
    time. Genuinely unshareable helpers (class, *args/**kwargs/defaults, a param
    called as a function, dict/set in/out) force the whole node inline.

    Units come from ``spec['external_helper_units']`` (set by spec_extractor);
    for specs that predate that field we recompute statically via import_follower
    (best-effort -- any failure -> inline path)."""
    units = spec.get("external_helper_units")
    if units is None:
        # No structured units on the spec. A node with no followed helpers has
        # neither key (spec_extractor omits both when empty), so short-circuit
        # WITHOUT re-running the follower -- keeps the no-helper port path cheap.
        if not spec.get("external_helpers"):
            return []
        try:  # an older spec that predates external_helper_units: recompute.
            from mpynode.native.ai import import_follower
            res = import_follower.collect_helper_sources(
                spec.get("compute") or "", spec.get("init") or "")
            units = res.get("sources") or []
        except Exception:
            return []
    out = []
    for u in units or []:
        scalar = _derive_scalar_proto(u)
        if scalar is not None:
            out.append({"module": u["module"], "sym": u["name"],
                        "source": u["source"], "name": scalar[0],
                        "proto": scalar[1], "kind": "scalar"})
            continue
        fn = _parse_unit_fn(u)
        if fn is not None and _nonscalar_shareable(fn):
            out.append({"module": u["module"], "sym": u["name"],
                        "source": u["source"],
                        "name": _helper_symbol(u["module"], u["name"],
                                               u["source"]),
                        "proto": None, "kind": "nonscalar"})
            continue
        return []  # any genuinely-unshareable helper -> whole node uses inline
    return out


def _marked_block(name: str, proto: str, code: str) -> str:
    """Wrap a translated helper definition in the bundler's hoist markers."""
    return (
        "// === MPYNODE SHARED HELPER BEGIN name=%s proto=%s ===\n"
        "%s\n"
        "// === MPYNODE SHARED HELPER END name=%s ===\n" % (name, proto, code, name)
    )


def _signature_of(code: str) -> str:
    """The function signature (everything up to the first ``{``) of a C++
    definition, whitespace-normalized. This is the AUTHORITATIVE prototype: using
    the definition's own signature (rather than a separately-stated PROTO line)
    guarantees the forward declaration the bundler emits can never disagree with
    the definition (a mismatch would be a hard link/compile failure)."""
    i   = code.find("{")
    sig = code[:i] if i >= 0 else code
    return " ".join(sig.split())


def _parse_helper_proto(text: str) -> tuple:
    """Pull a non-scalar helper translation into ``(proto, code)``.

    Requires the LLM's ``PROTO: <prototype>`` line (the prompt contract) -- its
    absence means the output isn't the agreed shape, so we raise and the node
    falls back to inline. The returned ``proto`` is DERIVED FROM THE DEFINITION
    (:func:`_signature_of`), not the PROTO line, so proto and code can never
    disagree; the PROTO line just focuses the model on choosing types."""
    lines = _strip_fences(text).splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().upper().startswith("PROTO:"):
            code = "\n".join(lines[i + 1:]).strip("\n")
            if "{" not in code:
                raise _HelperProtoError("no function body after PROTO: line")
            return _signature_of(code), code
    raise _HelperProtoError("no PROTO: line in helper translation")


def _translate_helper(unit: dict, complete_fn, sibling_protos: list) -> dict:
    """Translate one helper to C++ (memoized). Returns ``{name, proto, code}``.

    Scalar (or legacy, no ``kind``) units use the FIXED ``unit['proto']`` and the
    "use EXACTLY this signature" contract -- byte-identical to before. Non-scalar
    units ask the LLM to CHOOSE a typed signature and report it on a ``PROTO:``
    line, which is parsed + validated (must use the fixed name); a bad/missing
    proto raises :class:`_HelperProtoError` so the node falls back to inline."""
    name   = unit["name"]
    cached = _HELPER_MEMO.get(name)
    if cached is not None:
        return cached
    others       = [p for p in sibling_protos if p and p != unit.get("proto")]
    others_block = ""
    if others:
        others_block = ("Other helpers you MAY call (already declared elsewhere "
                        "-- do NOT redefine them):\n%s\n\n"
                        % "\n".join("%s;" % p for p in others))
    if unit.get("kind") == "nonscalar":
        user = (
            "Translate this pure-Python helper into ONE C++ free function.\n"
            "Use EXACTLY this function NAME: %s\n"
            "CHOOSE the C++ parameter and return types per the TYPE MAPPING "
            "(pass vectors/arrays/matrices by const reference; return by value).\n"
            "FIRST output a line `PROTO: <full C++ prototype, no trailing "
            "semicolon>`, THEN the matching function definition.\n\n"
            "%s"
            "Original Python (was %s.%s):\n```python\n%s\n```\n"
            % (name, others_block, unit["module"], unit["sym"], unit["source"])
        )
        proto, code = _parse_helper_proto(complete_fn(_SYSTEM_HELPER, user))
        # The proto must declare a function literally NAMED `name` (word-boundary
        # + "(" so a substring or a comment mention can't false-accept).
        if not re.search(r"\b%s\s*\(" % re.escape(name), proto):
            raise _HelperProtoError(
                "chosen proto %r does not declare the required name %r"
                % (proto, name))
        result = {"name": name, "proto": proto, "code": code}
    else:
        user = (
            "Translate this pure-Python helper into ONE C++ free function with "
            "EXACTLY this name and signature:\n  %s\n\n"
            "%s"
            "Original Python (was %s.%s):\n```python\n%s\n```\n"
            % (unit["proto"], others_block, unit["module"], unit["sym"],
               unit["source"])
        )
        code   = _strip_fences(complete_fn(_SYSTEM_HELPER, user)).strip()
        result = {"name": name, "proto": unit["proto"], "code": code}
    _HELPER_MEMO[name] = result
    return result


def _inject_helper_blocks(skeleton: str, blocks: list) -> str:
    """Insert marked helper blocks at file scope -- after the last ``#include``
    (so they precede the node class/namespace), or at the top if none."""
    if not blocks:
        return skeleton
    lines   = skeleton.splitlines()
    inc_idx = [i for i, l in enumerate(lines) if l.lstrip().startswith("#")]
    at      = (max(inc_idx) + 1) if inc_idx else 0
    chunk   = "\n\n" + "\n".join(b.rstrip("\n") for b in blocks)
    head    = "\n".join(lines[:at])
    tail    = "\n".join(lines[at:])
    return head + chunk + "\n" + tail
