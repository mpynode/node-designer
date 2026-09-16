"""Blessed API methods for mPyBlendShape (the METHOD-kind registry entry).

Maya-free. Mirrors the skin_method_interface SSOT pattern. Read by the Variables
/ Framework tabs (via the wrapper class attr) and the native compiler / porter
(directly).

All three methods lower via the ``Transpile`` marker: their C++ comes from
transpiling the pure-numpy free functions in ``morph_blend`` -- the SAME
functions the interpreted adapters run -- so there is no hand-written blend-shape
kernel and no duplicated math. Deterministic parity-or-reject (never AI-ported).

Implicit reads
--------------
Unlike the skin methods (which pass every operand explicitly and declare
``reads=()``), these declare the baked tables as IMPLICIT reads. The tables are
bookkeeping -- ``targetOffset`` / ``targetComponents`` / ``targetDeltas`` and the
corrective four -- that a user should never have to name at a call site. That is
the entire readability win, so the implicit path is the point here.

``reads`` MUST be ordered to match the free fn's TRAILING parameters: the fn's
positional params are ``(*user_args, *reads)`` and ``blessed_transpile._make_emit``
binds them positionally. Get the order wrong and the compiled node silently reads
the wrong table, so the ordering is pinned by a test.

``lower_deform`` unions these into its used-attr set
(``blessed_transpile.called_method_reads``), which is what makes the codegen
materialise ``targetOffset`` et al even though the compute never spells them.
Every read must bind or the compile honest-rejects -- which is why
``MPyBlendShape.rebuild()`` always declares all eight tables, leaving the
corrective four empty when unused.
"""
from __future__ import annotations

from mpynode._common.interface.api_methods import (
    MethodSpec,
    PropertySpec,
    Transpile,
    validate,
    validate_properties,
)

# The aliased per-target weight multi. Maya-free SSOT for the name: the wrapper
# (``mpy_blend_shape.WEIGHT_ATTR``) and the codegen's ``self.morphs`` desugar
# (``nd_lower._rewrite_morph_reads``) both key off this, and a test pins them
# equal -- a drift here would rewrite ``self.morphs.weights`` to a plug that does
# not exist.
WEIGHT_PLUG = "weight"

# Per-rig name indirection: shapeSlot[k] is the weight[] index of the k-th NAME
# the Compute mentions, or -1 when this rig has no such target. The compiler
# bakes only k (an ordinal over the compute SOURCE, identical on every rig), so
# no target name ever reaches the generated C++ and one bundle still serves any
# rig. Filled by MPyBlendShape.rebuild(); ordering comes from
# nd_lower.morph_slot_names, which is the single source of it.
SLOT_PLUG = "shapeSlot"

# The eight baked tables, in the canonical order the kernels take them.
WEIGHT_READS = (WEIGHT_PLUG, "interBase", "interKnot", "comboOffset",
                "comboDriver")
DELTA_READS = ("targetOffset", "targetComponents", "targetDeltas")
SLOT_READS  = (WEIGHT_PLUG, SLOT_PLUG)

# The live-target tables: a target's offsets read off its CONNECTED mesh instead
# of the bake, in the same CSR layout, keyed by live ENTRY rather than by target
# (``liveSlot[k]`` says which target entry k belongs to). NOT plugs -- unlike
# every other read here, these are C++ locals emit_deformer builds in the deform
# prologue from targetGeometry + originalGeometry, and nd_lower binds them under
# these names. Declaring them as reads is what makes the compiled node ask for
# them at all; a name here that nothing binds honest-rejects the compile rather
# than shipping a node that quietly ignores its target meshes.
LIVE_READS = ("liveSlot", "liveOffset", "liveComponents", "liveDeltas")

# read name -> (nd dtype, the C++ std::vector carrying it). ``emit_deformer``
# DECLARES these in the deform prologue; ``nd_lower`` BINDS them under the
# LIVE_READS names. One table, so the emitting half and the binding half cannot
# drift into a node that declares a read nothing fills -- which does not fail
# loudly, it drops the whole deform to the AI porter.
LIVE_CPP_VARS = {
    "liveSlot":       ("int64", "mpyLiveSlot"),
    "liveOffset":     ("int64", "mpyLiveOfs"),
    "liveComponents": ("int64", "mpyLiveComp"),
    "liveDeltas":     ("double", "mpyLiveDlt"),
}

INTERNAL_API_METHODS = (
    MethodSpec(
        name = "morph_weights",
        sig  = "morph_weights() -> ndarray(T,)",
        doc=("Effective per-target weights: the raw weight[] channels with "
             "in-between hats and combo products ADDED on top. An in-between "
             "target adds a triangular hat on its main target's weight; a combo "
             "target adds the product of its drivers. Both keep whatever is "
             "keyed on their own channel, so a corrective can be dialled by "
             "hand as well as driven. A node with no correctives gets its raw "
             "weights back unchanged."),
        runtime = "mpynode._common.methods.morph_methods:morph_weights",
        lower   = Transpile("mpynode._common.methods.morph_blend:resolve_weights"),
        reads   = WEIGHT_READS,
    ),
    MethodSpec(
        name = "morph_deltas",
        sig  = "morph_deltas(base, w) -> ndarray(N, 3)",
        doc=("The weighted sum of every target's sparse deltas as an OFFSET "
             "field -- what to ADD to base -- for the per-target weight vector "
             "w (typically self.morph_weights()). base supplies the vertex "
             "count. Returns offsets rather than points so you can scale, mask "
             "or combine the field before applying it."),
        runtime="mpynode._common.methods.morph_methods:morph_deltas",
        lower=Transpile(
            "mpynode._common.methods.morph_blend:accumulate_deltas_live"),
        reads=DELTA_READS + LIVE_READS,
    ),
    MethodSpec(
        name = "morph_apply",
        sig  = "morph_apply(base, envelope) -> ndarray(N, 3)",
        doc=("The whole deform in one call: base + envelope * deltas, with "
             "in-betweens and combos resolved. This is what "
             "self.morphs.apply(base, envelope) desugars to in a compiled "
             "compute -- a single call, so the base expression is evaluated "
             "exactly once."),
        runtime = "mpynode._common.methods.morph_methods:morph_apply",
        lower   = Transpile("mpynode._common.methods.morph_blend:apply_morphs_live"),
        reads   = WEIGHT_READS + DELTA_READS + LIVE_READS,
    ),
    MethodSpec(
        name = "blend_targets",
        sig  = "blend_targets(base) -> ndarray(N, 3)",
        doc=("Fully-blended points: resolve the weights, accumulate the deltas, "
             "add to base. The one-call convenience form. Apply the envelope in "
             "your Compute -- base + envelope * (blend_targets(base) - base) -- "
             "exactly as the skinCluster methods do."),
        runtime="mpynode._common.methods.morph_methods:blend_targets",
        lower=Transpile(
            "mpynode._common.methods.morph_blend:blend_targets_live"),
        reads=WEIGHT_READS + DELTA_READS + LIVE_READS,
    ),
    MethodSpec(
        name = "morph_weight_at",
        sig  = "morph_weight_at(slot) -> float",
        doc=("One target's RAW weight, reached by compile-time slot. This is "
             "what self.morphs[\"browUp\"].weight desugars to: the compiler "
             "turns the name into an ordinal and shapeSlot maps that ordinal to "
             "this rig's weight[] index, so the name itself never reaches the "
             "generated C++. A slot this rig has no target for reads 0.0."),
        runtime = "mpynode._common.methods.morph_methods:morph_weight_at",
        lower   = Transpile("mpynode._common.methods.morph_blend:weight_at_slot"),
        reads   = SLOT_READS,
    ),
)


# The self.<attr> surface an mPyBlendShape Compute reaches: inherited
# MPxDeformerNode plugs plus the node's own target surface and baked tables. A
# blessed method resolves BEFORE the plug tree in SelfProxy.__getattr__, so a
# method name equal to one of these would silently shadow the plug on read --
# validate() fails loudly at import if so.
_BS_PLUG_NAMES = frozenset({
    "outputGeometry", "outputGeom", "input", "inputGeometry", "inputGeom",
    "envelope", "weightList", "weights",
    "targetGeometry", "weight", "liveTargets", "originalGeometry",
    "targetOffset", "targetComponents", "targetDeltas",
    "interBase", "interKnot", "comboOffset", "comboDriver",
    SLOT_PLUG,
})

INTERNAL_API_PROPERTIES = (
    PropertySpec(
        name = "morphs",
        sig  = "morphs -> MorphStack",
        doc=("The target stack as an object: list-like (len / [i] / iterate) "
             "and, in authoring code, dict-like ([\"browUp\"], .find(\"brow*\")). "
             "A VIEW over the node's baked tables -- no plugs of its own. In a "
             "Compute only .weights / .resolved / .deltas(base, w) / "
             ".apply(base, envelope) / [int].weight / len() are recognised; each "
             "rewrites to the matching blessed method so it lowers to pure C++."),
        runtime="mpynode._common.methods.morph_methods:morphs",
    ),
)

validate(INTERNAL_API_METHODS, _BS_PLUG_NAMES)
validate_properties(INTERNAL_API_PROPERTIES, _BS_PLUG_NAMES,
                    tuple(m.name for m in INTERNAL_API_METHODS))
