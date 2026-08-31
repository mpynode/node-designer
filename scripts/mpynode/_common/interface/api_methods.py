"""Maya-free SSOT for blessed node API methods (the `METHOD` kind).

A blessed method is a *paired* artifact: an interpreted adapter (``runtime``)
plus a C++ lowering (``lower``), curated per node type. The Variables tab
surfaces it; SelfProxy binds it as ``self.<name>``; the porter lowers a
``self.<name>(...)`` call via ``lower``. Pure Python so the headless porter and
the .mpn path can read it.
"""
from __future__ import annotations

from typing import NamedTuple, Union


class CppKernel(NamedTuple):
    """Lower a blessed call to an existing hand-written C++ kernel."""
    kernel: str


class Transpile(NamedTuple):
    """Lower a blessed call by following+transpiling a pure-numpy free fn.
    Defined for future procrustes-style methods; NOT exercised in v1."""
    free_fn: str


class NativeSideEffect(NamedTuple):
    """Lower a SIDE-EFFECTING blessed method -- one that mutates a plug or
    marshals a Maya command (e.g. copying a persistent weight buffer into the
    weightList paint scratchpad) rather than returning a numeric result.

    There is no pure numeric kernel to transpile and the side effect is
    INTERACTIVE-ONLY (it stages a Maya plug for the paint UI; a compiled node
    running headless has no paint session), so a BARE ``self.<name>(...)``
    expression STATEMENT lowers to NOTHING -- the compiled node simply omits it.
    This is faithful ONLY because the deform's numeric output does not depend on
    the side effect: the parity-gated compiled path reads its own per-node input
    plugs, never the scratchpad the method would stage. The interpreted adapter
    (``runtime``) still performs the side effect when the node runs interpreted.

    A NativeSideEffect method used in VALUE position (``x = self.<name>(...)``)
    still honest-rejects -- there is no numeric Val to produce, and dropping a
    value-producing call would silently corrupt the surrounding math (never
    AI-port). Carries a human-readable note only."""
    note: str


class MethodSpec(NamedTuple):
    name: str                       # e.g. "read_texture"
    sig: str                        # display signature, e.g. "read_texture() -> ..."
    doc: str                        # one-line docstring (tooltip)
    runtime: str                    # "module.path:function" interpreted adapter
    lower: Union[CppKernel, Transpile, NativeSideEffect]
    reads: tuple = ()               # node PRESET attr names the interpreted
                                    # adapter reads (e.g. colorSpace/borderColor).
                                    # The extractor unions these into the compiled
                                    # spec when a compute CALLS this method -- the
                                    # presets are read INSIDE the adapter, never
                                    # textually as self.<preset> in the compute.
                                    # LAST field w/ a default so existing 5-arg
                                    # constructions stay valid.


class PropertySpec(NamedTuple):
    """A blessed non-plug READ property bound onto ``self`` (the PROPERTY kind).

    The value-returning sibling of :class:`MethodSpec`. SelfProxy resolves it in
    its own tier ABOVE the plug tree, so ``self.morphs`` hands back a live object
    built from the node's plugs rather than a bound callable.

    There is no ``lower`` field on purpose. A property has no call node for the
    transpiler to hang a lowering off, so the compiled path never sees the
    property at all -- the codegen rewrites the recognised ``self.<prop>.<member>``
    forms into blessed METHOD calls before lowering (see
    ``nd_lower._rewrite_morph_reads``), and a bare or unrecognised use
    honest-rejects. The property is therefore an INTERPRETED + authoring surface
    whose compiled equivalent is always a method.
    """
    name: str                       # e.g. "morphs"
    sig: str                        # display signature, e.g. "morphs -> MorphStack"
    doc: str                        # one-line docstring (tooltip)
    runtime: str                    # "module.path:function" -- fn(self) -> value


def validate_properties(props, plug_names, method_names=()) -> None:
    """Fail loudly if a blessed PROPERTY would shadow something.

    A property resolves above the plug tree, so a name equal to a plug would
    silently hide it on read -- the same trap :func:`validate` guards for
    methods. A property colliding with a METHOD name is also fatal: which tier
    wins would then depend on lookup order rather than on intent.
    """
    seen = set()
    for p in props:
        if not isinstance(p, PropertySpec):
            raise ValueError("not a PropertySpec: %r" % (p,))
        if p.name in seen:
            raise ValueError("duplicate blessed property name %r" % p.name)
        seen.add(p.name)
        if p.name in plug_names:
            raise ValueError(
                "blessed property %r collides with a plug of the same name; "
                "rename the property" % p.name)
        if p.name in set(method_names):
            raise ValueError(
                "blessed property %r collides with a blessed method of the "
                "same name" % p.name)


def validate(specs, plug_names) -> None:
    """Fail loudly if the registry violates an invariant the tiers rely on:
    no method name may equal a plug name (SelfProxy method tier wins on read,
    so a collision would silently shadow a plug), and names must be unique."""
    seen = set()
    for m in specs:
        if not isinstance(m, MethodSpec):
            raise ValueError("not a MethodSpec: %r" % (m,))
        if m.name in seen:
            raise ValueError("duplicate blessed method name %r" % m.name)
        seen.add(m.name)
        if m.name in plug_names:
            raise ValueError(
                "blessed method %r collides with a plug of the same name; "
                "rename the method" % m.name)
