"""Interpreted adapters for mPyBlendShape's blessed blend-shape methods.

Bound onto ``self`` by the SelfProxy blessed-method tier. Each one reads the
node's baked tables off ``self`` and delegates to the canonical Maya-free math in
``morph_blend`` -- the SAME functions the native compiler's blessed ``Transpile``
lowering transpiles, so interpreted == compiled by construction.

Live targets
------------
The one place interpreted goes BEYOND the shared math is construction history:
``_live_deltas`` reads the offsets for a target straight off its connected mesh
rather than off the bake, so sculpting a target reaches the deform immediately.
It is a pure READ -- no plug write, no dirty, nothing on the undo stack -- which
is what separates it from re-baking mid-deform: a ``setAttr`` from inside an
evaluation has to be marshalled off it, and lands in its own undo chunk on top
of whatever the user was doing, so their vertex edit can no longer be undone.

That divergence rides the ``MethodSpec`` ``runtime=`` / ``lower=`` seam: the
adapters here gain it, the transpiled kernels do not, and a compiled node keeps
reading the baked tables exactly as before.

Unlike the skinCluster methods (which take every operand explicitly), these
declare the tables as implicit ``MethodSpec.reads``: they are bookkeeping the
user never wants to name at a call site. ``lower_deform`` unions those reads into
its used-attr set so the codegen materialises them even though the compute never
spells ``self.targetOffset``.

Missing-table policy. A node whose corrective tables were never declared (an old
scene, or a hand-built node) reads them as EMPTY here, so ``resolve_weights``
degrades to the raw weights and the deform still runs. The COMPILED path instead
honest-rejects at compile time, because ``MethodSpec.reads`` requires every
declared read to bind. Loud compiled, soft interpreted -- deliberate: an
interpreted node should keep working, and a compiled one should never silently
read a table that is not there.
"""
from __future__ import annotations

import numpy as np

from mpynode._common.methods import morph_blend


def _rebake_if_stale(name):
    """Re-bake ``name``'s delta tables when a CONNECTED target's points no
    longer match what is baked. Returns True when something was written.

    A MAIN-THREAD authoring operation, never reached from a deform: the live
    pass below gives the deform its construction history without writing a
    single plug. Shared by ``MPyBlendShape.resync_targets`` and by Convert (which
    has to freeze the live state into the tables the compiled sibling reads), so
    both apply the IDENTICAL guards: a node with no connected target is left
    alone, a slot that is neither connected nor aliased is never silently erased,
    and a settled node performs no plug write at all.
    """
    from maya import cmds as mc
    from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

    bs    = MPyBlendShape(name)
    names = bs.target_names
    live = [bool(mc.listConnections("%s.targetGeometry[%d]" % (name, i),
                                    s=True, d=False))
            for i in range(len(names))]
    # Nothing connected -> nothing to follow. A node whose deltas came from a
    # file (or were written by hand) has no target meshes at all, and re-baking
    # it would be pure loss.
    if not any(live):
        return False
    # bake_deltas only KEEPS an unconnected slot's deltas when the slot still
    # has an ALIAS -- an empty name is how remove_target marks a slot as gone.
    # So a slot that is neither connected nor aliased would be dropped by the
    # re-bake. Never trade a live refresh for silently erasing a target: leave
    # the whole node alone instead.
    if not all(c or nm for c, nm in zip(live, names)):
        return False

    was = mc.getAttr(name + ".targetDeltas")
    now = bs.bake_deltas().get("targetDeltas")
    if list(was or []) == list(now or []):
        return False                        # settled: nothing was written

    # Publish. Safe against a recompute loop precisely because it is reached
    # ONLY when the bake actually changed something -- the next pass compares
    # equal and returns above.
    mc.dgdirty(name)
    return True


# The gate. A node predating it has no such plug and reads LIVE, which is the
# behaviour the attribute exists to expose rather than to withhold.
LIVE_GATE  = "liveTargets"
TARGET_GEO = "targetGeometry"
ORIG_GEO   = "originalGeometry"


def _pts_fast(mfn):
    """(N, 3) float64 points from an api1 ``MFnMesh``, via its RAW buffer.

    Maya stores polygon points as float32 internally, so this is BIT-EXACT
    against ``MFnMesh.getPoints`` -- not a precision trade. It is the whole
    difference between a usable live path and an unusable one: measured at
    212,521 verts, 0.11 ms here against 74.51 ms for the framework's
    ``points_array_to_numpy`` (both exact, maxerr 0.0).

    ``from_address`` gives a VIEW of Maya's own buffer; ``astype`` copies out of
    it before it can be invalidated.
    """
    import ctypes

    n = mfn.numVertices()
    buf = (ctypes.c_float * (n * 3)).from_address(
        int(mfn.getRawPoints().__int__()))
    return np.frombuffer(buf, dtype=np.float32,
                         count=n * 3).reshape(n, 3).astype(np.float64)


def _orig_points(self, fn, nverts):
    """(N, 3) REST points -- ``originalGeometry`` for the geometry this deform
    pass is running on -- or None when they cannot be had.

    This, not the ``base`` arriving in the compute, is the reference a live delta
    must be measured against: ``base`` already carries any UPSTREAM deformation,
    which would be folded into every delta with the wrong sign. It is also
    exactly what ``bake_deltas`` measures against (``_base_points`` reads the
    same ORIG intermediate shape), which is what makes a live slot and a baked
    slot agree to the last bit.
    """
    import maya.OpenMaya as om1

    try:
        arr = self._psp_datablock.inputArrayValue(fn.attribute(ORIG_GEO))
        # LOGICAL index: deform() runs once per output geometry and the compute
        # context carries which one, so a deformer driving two meshes reads the
        # rest shape of the one it is deforming rather than always the first.
        arr.jumpToElement(
            int((self._psp_compute_ctx or {}).get("multi_index") or 0))
        data = arr.inputValue().data()
        if data.isNull():
            return None
        mfn = om1.MFnMesh(data)
        if mfn.numVertices() != nverts:
            return None
        return _pts_fast(mfn)
    except Exception:
        return None


def _live_deltas(self, base, w):
    """``(lslot, lofs, lcomp, ldlt)`` read from the CONNECTED target meshes, or
    ``None`` when the live pass cannot -- or must not -- run.

    Construction history without construction: the deform READS the target
    meshes instead of re-baking them, so it writes no plug, dirties nothing, and
    pushes nothing onto the undo stack. A re-bake from inside the deform cannot
    do that -- its ``setAttr`` has to be marshalled off the evaluation, which
    lands it in its own undo chunk on top of whatever the user was doing.

    The result is the CSR ``morph_blend.accumulate_deltas_live`` takes, keyed by
    live ENTRY: ``lslot[k]`` is the target entry k belongs to. UNWEIGHTED -- the
    kernel applies ``w[lslot[k]]``, which is what lets the compiled prologue
    build the identical tables without needing the effective weights (it has
    only the raw ``weight`` plug at that point).

    Every path out of here degrades to the BAKED tables, which is precisely the
    behaviour this node had before live targets existed.
    """
    import maya.OpenMaya as om1

    try:
        if not bool(getattr(self, LIVE_GATE)):
            return None
    except AttributeError:
        pass                    # no gate on this node -> live (see LIVE_GATE)

    try:
        mobj  = self._psp_mobject
        block = self._psp_datablock
    except AttributeError:
        return None
    if block is None:
        return None
    fn = om1.MFnDependencyNode(mobj)

    # Which slots are live. BOTH conditions are load-bearing.
    #
    # isDestination(): targetGeometry is setStorable(False) + setCached(True), so
    # a DISCONNECTED element keeps serving its last cached mesh -- the data alone
    # cannot tell you the connection is gone, and trusting it would resurrect a
    # deleted target that the baked deltas are supposed to keep driving. The plug
    # tree is the only honest discriminator, and it is a topology query with no DG
    # pull, so it is safe from the EM worker thread this runs on.
    #
    # w[li] != 0: a zero-weight target contributes exactly zero, so skipping its
    # read is EXACT, not an approximation -- and that skip is what makes a
    # 167-target rig affordable, since almost none of a face are dialled in at once.
    try:
        gplug = om1.MPlug(mobj, fn.attribute(TARGET_GEO))
        want  = set()
        for k in range(gplug.numElements()):
            e  = gplug.elementByPhysicalIndex(k)
            li = int(e.logicalIndex())
            if li < w.shape[0] and w[li] != 0.0 and e.isDestination():
                want.add(li)
    except Exception:
        return None
    if not want:
        return None

    nv   = base.shape[0]
    orig = _orig_points(self, fn, nv)
    if orig is None:
        # No rest reference -> no live pass. Falling back to ``base`` would be
        # wrong under an upstream deformer, and silently so.
        return None

    slots = []
    offs  = [0]
    comps = []
    dlts  = []
    try:
        arr = block.inputArrayValue(fn.attribute(TARGET_GEO))
        for k in range(arr.elementCount()):
            arr.jumpToArrayElement(k)
            li = int(arr.elementIndex())
            if li not in want:
                continue        # never PULL a slot whose read we would discard
            data = arr.inputValue().data()
            if data.isNull():
                continue
            mfn = om1.MFnMesh(data)
            if mfn.numVertices() != nv:
                continue        # topology drift -> keep that slot's bake
            d = _pts_fast(mfn) - orig
            # Sparse, exactly as the bake is: only the vertices this target
            # actually moves. An UNMOVED vertex contributes 0.0 either way, so
            # the threshold decides the table's SIZE and never its result --
            # which is why an exact comparison is safe on both sides.
            hit = np.nonzero(np.abs(d).max(axis=1) != 0.0)[0]
            slots.append(li)
            comps.append(hit.astype(np.int64))
            dlts.append(d[hit].reshape(-1))
            offs.append(offs[-1] + int(hit.shape[0]))
    except Exception:
        return None
    if not slots:
        return None
    return (np.asarray(slots, dtype=np.int64),
            np.asarray(offs, dtype=np.int64),
            np.concatenate(comps) if comps else np.zeros(0, dtype=np.int64),
            np.concatenate(dlts) if dlts else np.zeros(0, dtype=np.float64))


def _deltas(self, base, w):
    """The offset field: live where a target mesh is connected and dialled in,
    baked everywhere else. The single implementation behind all three delta
    methods, so the live half cannot drift between them.

    Always routes through ``accumulate_deltas_live`` -- an EMPTY live table is
    the no-live case -- so interpreted and compiled run one kernel down one path
    rather than two that merely agree today.
    """
    live = _live_deltas(self, base, w)
    if live is None:
        live = (np.zeros(0, dtype=np.int64), np.zeros(1, dtype=np.int64),
                np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float64))
    return morph_blend.accumulate_deltas_live(
        base, w,
        _table(self, "targetOffset", np.int64),
        _table(self, "targetComponents", np.int64),
        _table(self, "targetDeltas", np.float64),
        live[0], live[1], live[2], live[3],
    )


def _table(self, name, dtype):
    """A 1-D array for table ``name``, or an EMPTY array when the node does not
    declare it (see the missing-table policy in the module docstring)."""
    try:
        v = getattr(self, name)
    except AttributeError:
        return np.zeros(0, dtype=dtype)
    if v is None:
        return np.zeros(0, dtype=dtype)
    return np.asarray(v, dtype=dtype).reshape(-1)


def _weights(self):
    return _table(self, "weight", np.float64)


def morphs(self):
    """self.morphs -> MorphStack. The blessed PROPERTY adapter.

    A view over the node's baked tables, rebuilt per access (a few array slices).
    ALIASES are absent -- they return empty on the EM worker thread -- so a name
    key resolves through the compile-time slot table instead (``shapeSlot``),
    which is the same route the compiled node takes. See MorphStack's module
    docstring.
    """
    from mpynode._api2.morph import MorphStack
    return MorphStack.from_proxy(self)


def morph_weights(self):
    """self.morph_weights() -> (T,) effective weights.

    Raw ``weight[]`` with in-between hats and combo products ADDED on top of
    each target's own channel, so a corrective can be dialled by hand as well as
    driven. A node with no correctives gets its raw weights back unchanged.
    """
    return morph_blend.resolve_weights(
        _weights(self),
        _table(self, "interBase", np.int64),
        _table(self, "interKnot", np.float64),
        _table(self, "comboOffset", np.int64),
        _table(self, "comboDriver", np.int64),
    )


def morph_deltas(self, base, w):
    """self.morph_deltas(base, w) -> (N, 3) accumulated OFFSET field.

    What to ADD to ``base``, given the per-target weight vector ``w`` (typically
    ``self.morph_weights()``). ``base`` supplies the vertex count.
    """
    return _deltas(self,
                   np.asarray(base, dtype=np.float64),
                   np.asarray(w, dtype=np.float64).reshape(-1))


def morph_apply(self, base, envelope=1.0):
    """self.morph_apply(base, envelope) -> (N, 3) points, envelope applied.

    The whole deform in one call. This is what ``self.morphs.apply(base,
    envelope)`` desugars to in a compiled compute -- a single call, so the
    ``base`` argument expression is evaluated exactly once.

    Composed from the same two kernels ``morph_blend.apply_morphs`` composes it
    from, in the same order -- identical by construction when nothing is live,
    and able to route through the live pass when something is.
    """
    base = np.asarray(base, dtype=np.float64)
    return base + float(envelope) * _deltas(self, base, morph_weights(self))


def morph_weight_at(self, slot):
    """self.morph_weight_at(slot) -> float, one target's RAW weight by slot.

    The interpreted half of the name-key path: ``self.morphs["browUp"].weight``
    desugars to this compiled, and MorphStack resolves the same name through the
    same ``shapeSlot`` table interpreted, so both sides read one mapping.
    """
    return morph_blend.weight_at_slot(
        int(slot),
        _weights(self),
        _table(self, "shapeSlot", np.int64),
    )


def blend_targets(self, base):
    """self.blend_targets(base) -> (N, 3) fully-blended POINTS.

    Resolve the weights, accumulate the deltas, add to ``base``. Apply the
    envelope in your Compute:
    ``base + envelope * (self.blend_targets(base) - base)``.
    """
    base = np.asarray(base, dtype=np.float64)
    return base + _deltas(self, base, morph_weights(self))
