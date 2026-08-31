"""Blessed API methods for mPySkinCluster (the METHOD-kind registry entry).

Maya-free. Mirrors the file_method_interface SSOT pattern. Read by the Variables
tab (via the wrapper class attr) and the native compiler / porter (directly).

Both methods lower via the ``Transpile`` marker: their C++ comes from transpiling
the pure-numpy free functions in ``skin_blend`` -- the SAME functions the
interpreted adapters run -- so there is no hand-written skinning kernel and no
duplicated math. Deterministic parity-or-reject (never AI-ported).

Every operand is an EXPLICIT argument -- ``f(rest, weights, joint, bind)`` -- so
``reads=()``: the method reads nothing off ``self``. The Compute expression
passes the node's own plugs at the call site, e.g. ``self.linear_blend(rest,
self.weightList, self.matrix, self.bindPreMatrix)``. The compiler lowers each
call arg in place; because the compute literally spells ``self.weightList`` /
``self.matrix`` / ``self.bindPreMatrix``, ``lower_deform``'s used-attr scan
materialises the dense skin locals without any implicit-``reads`` injection.
"""
from __future__ import annotations

from mpynode._common.interface.api_methods import (
    MethodSpec,
    NativeSideEffect,
    Transpile,
    validate,
)

INTERNAL_API_METHODS = (
    MethodSpec(
        name="linear_blend",
        sig="linear_blend(rest, weights, joint, bind) -> ndarray(N, 3)",
        doc=("Linear blend skinning of the rest points using the weights / joint "
             "matrices / bind-pre matrices you pass (typically self.weightList, "
             "self.matrix, self.bindPreMatrix). Returns deformed points (apply "
             "the envelope in your Compute)."),
        runtime="mpynode._common.methods.skin_methods:linear_blend",
        lower=Transpile("mpynode._common.methods.skin_blend:linear_blend"),
    ),
    MethodSpec(
        name="dual_quaternion",
        sig="dual_quaternion(rest, weights, joint, bind) -> ndarray(N, 3)",
        doc=("Dual quaternion skinning of the rest points using the weights / "
             "joint matrices / bind-pre matrices you pass (typically "
             "self.weightList, self.matrix, self.bindPreMatrix). Volume-preserving "
             "under bends. Returns deformed points (apply the envelope in your "
             "Compute)."),
        runtime="mpynode._common.methods.skin_methods:dual_quaternion",
        lower=Transpile("mpynode._common.methods.skin_blend:dual_quaternion"),
    ),
    MethodSpec(
        name="twist_swing",
        sig="twist_swing(rest, weights, joint, bind, twist_axis) -> ndarray(N, 3)",
        doc=("Twist/swing skinning: dual quaternion for the TWIST about a "
             "selectable bone-local axis (twist_axis: 0=X default, 1=Y, 2=Z), "
             "linear blend for the remaining SWING (bend). Pass the same operands "
             "as the other skin methods (typically self.weightList, self.matrix, "
             "self.bindPreMatrix) plus the axis (typically int(self.twistAxis)). "
             "Volume-preserving twist without the LBS \"candy-wrapper\", "
             "clean/cheap LBS bend. Returns deformed points (apply the envelope "
             "in your Compute)."),
        runtime="mpynode._common.methods.skin_methods:twist_swing",
        lower=Transpile("mpynode._common.methods.skin_blend:twist_swing"),
    ),
    MethodSpec(
        name="twist_swing_dual",
        sig=("twist_swing_dual(rest, twist_weights, swing_weights, joint, bind, "
             "twist_axis) -> ndarray(N, 3)"),
        doc=("Twist/swing skinning with SEPARATE weight sets: dual quaternion for "
             "the TWIST (about a selectable bone-local axis -- twist_axis: 0=X "
             "default, 1=Y, 2=Z) driven by ``twist_weights``, linear blend for "
             "the SWING (bend) driven by ``swing_weights`` (both dense N x J). "
             "Pass the same array for both to match twist_swing. Lets one node "
             "carry independently-painted twist vs bend weights (see the "
             "twist_swing_skin template). Returns deformed points "
             "(apply the envelope in your Compute)."),
        runtime="mpynode._common.methods.skin_methods:twist_swing_dual",
        lower=Transpile("mpynode._common.methods.skin_blend:twist_swing_dual"),
    ),
    MethodSpec(
        name="update_weights",
        sig="update_weights(weights) -> None",
        doc=("Write a dense (N, J) weight array INTO this skinCluster's "
             "weightList plug so Maya's Paint Skin Weights / Component Editor "
             "shows + edits it. Generic + side-effecting: pass ANY weight buffer "
             "-- nothing about which set / how many sets is baked in. The plug "
             "write is marshalled to the main thread (deferred in interactive "
             "Maya). Typically called from Compute to load a persistent weight "
             "buffer into the paint scratchpad; the deform reads the buffers "
             "directly, so weightList is only the scratchpad."),
        runtime="mpynode._common.methods.skin_methods:update_weights",
        # No numeric kernel to transpile: writing the weightList paint
        # scratchpad is an INTERACTIVE-ONLY side effect. A bare
        # ``self.update_weights(...)`` STATEMENT lowers to nothing in the
        # compiled node (it runs headless -- no paint session), which is faithful
        # because the deform reads its per-node weight plugs directly, never the
        # scratchpad this stages. The interpreted adapter still performs the
        # write. A value-position use would still honest-reject.
        lower=NativeSideEffect(
            "weightList paint-scratchpad write; interactive-only, compiled no-op"),
        reads=(),
    ),
    MethodSpec(
        name="sync_paint",
        sig="sync_paint(mode) -> None",
        doc=("Interactive paint machinery for the two-weight-set twist/swing skin: "
             "on entering a paint mode (skinMode 0/1) load that set's plug into "
             "weightList so Paint Skin Weights shows it; on a settled paint eval "
             "bank the painted weightList back into that set's plug (guarded, so an "
             "unpainted eval writes nothing). Interactive-only -- the compiled node "
             "reads the weight plugs directly, so a bare call lowers to nothing."),
        runtime="mpynode._common.methods.skin_methods:sync_paint",
        # Interactive-only plug staging; no numeric kernel. A bare
        # self.sync_paint(mode) STATEMENT lowers to nothing in the compiled node
        # (headless -- no paint session); the deform reads the weight plugs
        # directly so omitting the scratchpad staging is faithful.
        lower=NativeSideEffect(
            "twist/swing paint load+bank; interactive-only, compiled no-op"),
        reads=(),
    ),
)


# The self.<attr> surface an mPySkinCluster Compute reaches (inherited
# MPxSkinCluster / MPxGeometryFilter plugs). A blessed method resolves BEFORE the
# plug tree in SelfProxy.__getattr__, so a method name equal to one of these would
# silently shadow the plug on read -- validate() fails loudly at import if so.
_SKIN_PLUG_NAMES = frozenset({
    "outputGeometry", "outputGeom", "input", "inputGeometry", "inputGeom",
    "envelope", "weightList", "weights", "matrix", "bindPreMatrix",
    "geomMatrix", "blendWeights",
})

validate(INTERNAL_API_METHODS, _SKIN_PLUG_NAMES)
