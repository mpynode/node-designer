"""Maya-free blend-shape math -- the single source of truth for the blessed API
methods on ``mPyBlendShape``.

Three pure numpy functions over the node's baked tables:

  resolve_weights(w, ibase, iknot, cofs, cdrv)      -> (T,)   effective weights
  accumulate_deltas(base, w, ofs, comp, dlt)        -> (N, 3) delta field
  blend_targets(base, ...)                          -> (N, 3) deformed points

Each delta form has a ``_live`` twin taking four extra tables, which lets a
target's offsets come from its CONNECTED mesh instead of the bake -- see
``accumulate_deltas_live``. Both halves are the same scatter kernel, so live and
baked cannot drift.

Both the interpreted adapters (``morph_methods.py``) and the native compiler's
blessed ``Transpile`` lowering read THESE functions, so the interpreted node and
the compiled ``deform()`` run one shared algorithm -- no blend-shape math is
written twice, and there is no hand-written C++ kernel. Deterministic
parity-or-reject (never AI-ported).

Written in the loop dialect the compiler lowers to pure C++: ``for i in
range(...)``, integer indexing, ``float()`` / ``int()`` casts, ``np.zeros``,
``reshape``. Verified to emit a monomorphised ``nd::`` helper lambda.

The table layout
----------------
CSR (compressed sparse row), flat because a multi-of-arrays is not expressible
as a Maya attribute::

    ofs[t] .. ofs[t+1]        the slice of target t
    comp[j]                   vertex id
    dlt[3j], [3j+1], [3j+2]   xyz offset

Correctives ride alongside, one entry per target::

    ibase[t]   in-between -> the MAIN target it rides on, else -1
    iknot[t]   the in-between's position on that main (0..1)
    cofs[t] .. cofs[t+1]      slice of cdrv -- the combo's driver targets
    cdrv[j]                   a driver target index

EVERY table read is bounds-clamped. This is load-bearing, not defensive noise:
``nd::at1_ref`` performs NO bounds checking, so a stale table would be a silent
out-of-bounds heap write compiled while interpreted it would raise ``IndexError``.
Clamping makes both sides degrade identically.
"""
import numpy as np


def resolve_weights(w, ibase, iknot, cofs, cdrv):
    """Effective per-target weights: raw weights with in-between hats and combo
    products ADDED on top.

    A MAIN target keeps its own weight. An IN-BETWEEN target ADDS a triangular
    hat on its main target's weight -- peaking at 1.0 when the main sits exactly
    on the knot, falling to 0 at both ends. A COMBO target ADDS the PRODUCT of
    its drivers' weights.

    Correctives are ADDITIVE: a target keeps whatever is keyed on its OWN
    channel and the driven amount is added to it, so a corrective can be dialled
    by hand as well as derived. That is what makes every aliased channel a real,
    settable rig channel rather than a field whose value is silently discarded.

    Empty corrective tables (a node with no in-betweens or combos) leave every
    weight untouched, so this is a safe no-op on a plain blendShape.
    """
    nt = w.shape[0]
    nib = ibase.shape[0]
    nkn = iknot.shape[0]
    nco = cofs.shape[0]
    ncd = cdrv.shape[0]

    eff = np.zeros(nt)
    for t in range(nt):
        e = float(w[t])

        # in-between: a triangular hat on the main target's weight, ADDED to
        # whatever this target's own channel already carries.
        if t < nib and t < nkn:
            m = int(ibase[t])
            if m >= 0 and m < nt:
                k = float(iknot[t])
                dv = float(w[m])
                h = 0.0
                if dv <= k:
                    if k > 0.0:
                        h = dv / k
                else:
                    if k < 1.0:
                        h = (1.0 - dv) / (1.0 - k)
                e = e + h

        # combo: the product of every driver's weight, ADDED to this target's
        # own channel on the same rule as the in-between above.
        if t + 1 < nco:
            lo = int(cofs[t])
            hi = int(cofs[t + 1])
            if lo < 0:
                lo = 0
            if hi > ncd:
                hi = ncd
            if hi > lo:
                p = 1.0
                for j in range(lo, hi):
                    dr = int(cdrv[j])
                    if dr >= 0 and dr < nt:
                        p = p * float(w[dr])
                e = e + p

        eff[t] = e
    return eff


def accumulate_deltas(base, w, ofs, comp, dlt):
    """The weighted sum of every target's sparse deltas -- an ``(N, 3)`` OFFSET
    field, not deformed points.

    ``base`` supplies the vertex count (and nothing else); the result is what to
    ADD to it. Returning the offset rather than absolute points keeps the caller
    composable (scale it, mask it, add another field) and avoids the
    ``(base + d) - base`` cancellation the envelope lerp would otherwise need.
    """
    nv = base.shape[0]
    nt = w.shape[0]
    no = ofs.shape[0]
    nk = comp.shape[0]
    nd = dlt.shape[0]

    out = np.zeros(nv * 3)
    for t in range(nt):
        wt = float(w[t])
        if wt != 0.0 and t + 1 < no:
            lo = int(ofs[t])
            hi = int(ofs[t + 1])
            if lo < 0:
                lo = 0
            if hi > nk:
                hi = nk
            for j in range(lo, hi):
                v = int(comp[j])
                d = 3 * j
                if v >= 0 and v < nv and d + 2 < nd:
                    b = 3 * v
                    out[b] = out[b] + wt * float(dlt[d])
                    out[b + 1] = out[b + 1] + wt * float(dlt[d + 1])
                    out[b + 2] = out[b + 2] + wt * float(dlt[d + 2])
    return out.reshape(-1, 3)


def accumulate_deltas_live(base, w, ofs, comp, dlt, lslot, lofs, lcomp, ldlt):
    """``accumulate_deltas`` with a LIVE override: any target listed in ``lslot``
    takes its offsets from the live CSR instead of the baked one.

    Construction history without construction. The caller has already read the
    connected target meshes and diffed them against ``originalGeometry``; what
    arrives here is the result, in the SAME CSR layout as the bake::

        lslot[k]                  the target index live entry k belongs to
        lofs[k] .. lofs[k+1]      that entry's slice of lcomp / ldlt
        lcomp[j]                  vertex id
        ldlt[3j], [3j+1], [3j+2]  xyz offset

    Note the live table is keyed by ENTRY k, not by target -- which is what lets
    both halves be the same kernel. The baked half runs with the live targets'
    weights switched off (zero weight is exactly how ``accumulate_deltas`` skips
    a target, so this costs nothing), and the live half runs with a weight vector
    of one entry per live ENTRY. Two calls, one implementation, no second copy of
    the scatter loop.

    A target that is live contributes from the live table ONLY -- never both, or
    it would count twice. An empty ``lslot`` degrades to plain
    ``accumulate_deltas``, which is the behaviour of a node with nothing
    connected.
    """
    nt = w.shape[0]
    nlv = lslot.shape[0]

    # baked half: every target EXCEPT the ones being read live.
    wb = np.zeros(nt)
    for t in range(nt):
        wb[t] = float(w[t])
    for k in range(nlv):
        t = int(lslot[k])
        if t >= 0 and t < nt:
            wb[t] = 0.0
    baked = accumulate_deltas(base, wb, ofs, comp, dlt)

    # live half: per-ENTRY weights, so the same kernel walks the live CSR.
    wl = np.zeros(nlv)
    for k in range(nlv):
        t = int(lslot[k])
        if t >= 0 and t < nt:
            wl[k] = float(w[t])
    live = accumulate_deltas(base, wl, lofs, lcomp, ldlt)

    return baked + live


def blend_targets(base, w, ibase, iknot, cofs, cdrv, ofs, comp, dlt):
    """Fully-blended ``(N, 3)`` points: resolve the weights, then accumulate.

    Returns POINTS (not the offset field) so the call site reads exactly like the
    skinCluster methods -- ``base + envelope * (blend_targets(base) - base)``.
    """
    eff = resolve_weights(w, ibase, iknot, cofs, cdrv)
    return base + accumulate_deltas(base, eff, ofs, comp, dlt)


def blend_targets_live(base, w, ibase, iknot, cofs, cdrv, ofs, comp, dlt,
                       lslot, lofs, lcomp, ldlt):
    """``blend_targets`` with the live-target override -- see
    ``accumulate_deltas_live``.

    Exists alongside the baked form rather than replacing it because
    ``MorphStack`` and the authoring path call ``blend_targets`` directly, with
    no live tables to hand.
    """
    eff = resolve_weights(w, ibase, iknot, cofs, cdrv)
    return base + accumulate_deltas_live(base, eff, ofs, comp, dlt,
                                         lslot, lofs, lcomp, ldlt)


def apply_morphs(base, envelope, w, ibase, iknot, cofs, cdrv, ofs, comp, dlt):
    """Fully-blended ``(N, 3)`` points WITH the envelope already applied.

    The whole deform in one call: ``base + envelope * deltas``. Exists as its own
    kernel (rather than being composed at the call site) so ``MorphStack.apply``
    can desugar to a SINGLE blessed call. Composing it in the rewriter would mean
    emitting ``base`` twice, and ``base`` is typically the expression
    ``mesh.getPoints()`` -- which would then be evaluated twice per deform.
    """
    eff = resolve_weights(w, ibase, iknot, cofs, cdrv)
    return base + envelope * accumulate_deltas(base, eff, ofs, comp, dlt)


def apply_morphs_live(base, envelope, w, ibase, iknot, cofs, cdrv, ofs, comp,
                      dlt, lslot, lofs, lcomp, ldlt):
    """``apply_morphs`` with the live-target override -- see
    ``accumulate_deltas_live``. Kept separate from the baked form for the same
    reason ``blend_targets_live`` is.
    """
    eff = resolve_weights(w, ibase, iknot, cofs, cdrv)
    return base + envelope * accumulate_deltas_live(base, eff, ofs, comp, dlt,
                                                    lslot, lofs, lcomp, ldlt)


def weight_at_slot(slot, w, islot):
    """One target's raw weight, reached by compile-time SLOT.

    This is how a NAME key compiles. The compiler collects the name literals a
    compute mentions, assigns each an ordinal ``slot`` (a property of the CODE,
    identical on every rig), and bakes only that integer. ``islot`` is the node's
    ``shapeSlot`` table, which the wrapper fills per rig: ``islot[slot]`` is that
    name's actual ``weight[]`` index HERE, or -1 when this rig has no such
    target. So the C++ holds pure integer indirection and one bundle still serves
    any rig -- no name ever reaches the generated code.

    Returns the RAW channel, matching ``MorphStack[...].weight`` interpreted. Use
    ``resolve_weights`` when you want in-betweens and combos applied.

    An unmapped slot reads 0.0 rather than raising, so a rig missing a target
    behaves like that target sitting at rest -- the same degrade-don't-explode
    rule the table clamps follow.
    """
    n = islot.shape[0]
    nw = w.shape[0]
    out = 0.0
    if slot >= 0 and slot < n:
        j = int(islot[slot])
        if j >= 0 and j < nw:
            out = float(w[j])
    return out
