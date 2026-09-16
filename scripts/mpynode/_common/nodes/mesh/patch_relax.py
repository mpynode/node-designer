"""Patch-based surface relaxation (de Goes et al., Pixar, SIGGRAPH '18 Talks).

Reference: https://doi.org/10.1145/3214745.3214768

Relaxes a DEFORMED mesh back toward the local edge layout of its REST mesh. Each
vertex builds a 2D "decal map" of its 1-ring (a geodesic-polar flattening),
derives span-aware edge weights from it, fits the rest-to-posed rotation of its
patch by SVD, and steps toward the rotated rest configuration -- optionally
sliding ON the surface rather than through it.

The result removes the pinching / bunching a skin or wrap leaves behind while
keeping the silhouette, because the target is the REST edge layout carried
through the patch's own rotation, not a Laplacian average (which shrinks).

Split in two, for one reason
----------------------------
``build_ring_adjacency`` depends ONLY on topology, so it runs once (in the
node's setup / a rebuild command) and its result is seeded into an int input.
``patch_relax`` runs every evaluation and is written in the deterministically
lowerable subset, so the whole compute becomes pure C++ with no AI porter:

  * no ``repeat`` / ``argsort`` / ``bincount`` -- all rejected by the
    transpiler. Prefix sums use ``np.cumsum``, shifted one column to make them
    exclusive (see ``_exclusive_prefix``).
  * no ``take_along_axis``. The valid slots of a ring are contiguous ``[0, val)``
    so "next neighbour around the ring" is ``roll(-1)`` with a ``where`` that
    wraps the last valid slot back to slot 0.
  * no ``arctan2``. See ``_rotate_scale_2d``.
  * gathers are ``np.take`` against a zero-padded row, the same ``-1``-padded
    idiom ``procrustes_clusters`` uses.

Boundary vertices are PINNED. The decal map normalizes a vertex's ring angles to
sum to 2*pi, which is only meaningful for a closed ring; applying it to an open
fan drags the border inward. ``build_ring_adjacency`` emits an all-``-1`` row for
any vertex whose ring does not close, and a vertex with no neighbours never
moves.

Fully vectorized numpy -- the only Python loop is over relaxation ITERATIONS,
which the transpiler lowers to a real C++ ``for``.

One numerical caveat, inherited from the reference and not introduced here: in
surface mode the 2D scale is ``(|vp2| + 1e-12) / (|vh2| + 1e-12)``, and on a
very regular rest ring the weighted decal sum ``vh2`` can cancel down to ~1e-16.
At those isolated vertices the epsilon dominates the ratio and ``vh2``'s
DIRECTION is rounding noise, so the term is amplified by ~1e10 and any two
summation orders disagree. Measured against a scalar transcription of the
reference, that shows up as ~1e-6 on a mesh whose vertices travel ~0.2 -- far
below anything visible, but it is why surface mode is not bit-exact across
implementations while ``surface_blend = 0`` is (1e-15).
"""

from __future__ import annotations

import numpy as np

# ---- Topology: CCW-ordered 1-ring adjacency (runs ONCE, not in the compute) ----


def build_ring_adjacency(counts, indices, n_verts):
    """CCW-ordered 1-ring neighbours per vertex, as an ``(N, K)`` int array.

    ``counts`` / ``indices`` are the polygon description a ``Mesh`` exposes:
    vertices-per-face and the flat face-vertex connectivity. ``K`` is the widest
    ring on the mesh; shorter rings are padded with ``-1``.

    A row is all ``-1`` when the vertex must not move: an open (boundary) ring,
    a valence below 3, or a non-manifold fan whose corners do not chain into a
    single cycle. See the module docstring for why boundaries are pinned.

    Uses whatever numpy is convenient -- this never reaches the transpiler.
    """
    counts  = np.asarray(counts, dtype=np.int64).ravel()
    indices = np.asarray(indices, dtype=np.int64).ravel()
    n_verts = int(n_verts)
    if n_verts <= 0 or counts.size == 0 or indices.size == 0:
        return np.zeros((max(n_verts, 0), 0), dtype=np.int64)

    # --- every face corner as (vertex, prev-in-face, next-in-face) ---
    n_faces    = counts.shape[0]
    face_start = np.zeros(n_faces, dtype=np.int64)
    np.cumsum(counts[:-1], out=face_start[1:])
    total = int(counts.sum())
    if total != indices.shape[0]:
        raise ValueError("indices length %d does not match counts sum %d"
                         % (indices.shape[0], total))

    corner_face = np.repeat(np.arange(n_faces, dtype=np.int64), counts)
    base        = face_start[corner_face]
    within      = np.arange(total, dtype=np.int64) - base
    face_len    = counts[corner_face]
    nxt         = indices[base + (within + 1) % face_len]
    prv         = indices[base + (within - 1) % face_len]
    vtx         = indices

    # A face with fewer than 3 corners describes no ring.
    keep = face_len >= 3
    vtx, nxt, prv = vtx[keep], nxt[keep], prv[keep]
    if vtx.size == 0:
        return np.zeros((n_verts, 0), dtype=np.int64)

    # --- bucket the corners by vertex into a dense (N, K) table ---
    valence = np.bincount(vtx, minlength=n_verts)[:n_verts].astype(np.int64)
    width   = int(valence.max())
    if width < 3:
        return np.zeros((n_verts, 0), dtype=np.int64)

    order = np.argsort(vtx, kind="stable")
    v_s, n_s, p_s = vtx[order], nxt[order], prv[order]
    offset = np.zeros(n_verts + 1, dtype=np.int64)
    np.cumsum(valence, out=offset[1:])
    slot = np.arange(v_s.shape[0], dtype=np.int64) - offset[v_s]

    nxt_tab            = np.full((n_verts, width), -1, dtype=np.int64)
    prv_tab            = np.full((n_verts, width), -1, dtype=np.int64)
    nxt_tab[v_s, slot] = n_s
    prv_tab[v_s, slot] = p_s

    # --- chain the corners: corner t follows corner s when prv[t] == nxt[s] ---
    valid = np.arange(width)[None, :] < valence[:, None]  # (N, K)
    link  = (prv_tab[:, None, :] == nxt_tab[:, :, None])  # (N, s, t)
    link &= valid[:, :, None] & valid[:, None, :]
    has_succ = link.sum(axis=2) > 0  # (N, s)
    has_pred = link.sum(axis=1) > 0  # (N, t)
    succ     = np.where(has_succ, link.argmax(axis=2), 0)

    # A ring is closed iff every corner has both a predecessor and a successor.
    closed = ((has_succ | ~valid).all(axis=1)
              & (has_pred | ~valid).all(axis=1)
              & (valence >= 3))

    # --- walk the cycle from corner 0: [prev0, next0, then one per step] ---
    rows       = np.arange(n_verts, dtype=np.int64)
    ring       = np.full((n_verts, width), -1, dtype=np.int64)
    ring[:, 0] = prv_tab[:, 0]
    ring[:, 1] = nxt_tab[:, 0]
    cur        = np.zeros(n_verts, dtype=np.int64)
    for k in range(2, width):
        cur        = succ[rows, cur]
        ring[:, k] = np.where(k < valence, nxt_tab[rows, cur], -1)

    ring = np.where(valid, ring, -1)
    return np.where(closed[:, None], ring, -1)


# ---- Per-evaluation relaxation (the deterministically lowerable half) ----


def _exclusive_prefix(a):
    """``(N, K)`` EXCLUSIVE prefix sum along axis 1: ``out[i, k] = a[i, :k].sum()``.

    numpy's ``cumsum`` is INCLUSIVE, so it is shifted right one column with a
    zero in front. The shift is pure data movement, which is what makes this
    bit-identical to the strictly-upper matmul (``a @ M``) it replaces -- that
    matmul added an exact ``+0.0`` for every k >= i. Note ``cumsum(a) - a`` is
    NOT equivalent: the subtraction rounds a second time (measured off by 16.0
    on adversarial input).
    """
    zeros = np.zeros((a.shape[0], 1), dtype=np.float64)
    return np.concatenate([zeros, np.cumsum(a, axis=1)[:, :-1]], axis=1)


def _gather_ring(values, index, mask):
    """``(N, K, 3)`` neighbour values. ``-1`` padding reads an appended zero row
    and is then zeroed by ``mask``, so padding contributes nothing downstream."""
    padded = np.concatenate([values, np.zeros((1, 3), dtype=np.float64)], axis=0)
    return np.take(padded, index, axis=0) * mask[:, :, None]


def _ring_next(a, wrap):
    """The next entry around the ring, for a ``(N, K, C)`` per-slot array.

    Valid slots are contiguous ``[0, val)``, so the successor of slot k is slot
    k+1 -- except the last valid slot, which wraps to slot 0. That is exactly a
    ``roll`` with the wrap positions replaced by slot 0, and it avoids
    ``take_along_axis`` (unsupported by the transpiler)."""
    return np.where(wrap[:, :, None], a[:, :1, :], np.roll(a, -1, axis=1))


def _decal_map(pos, index, mask, valence, wrap):
    """Geodesic-polar flattening of every 1-ring into 2D -- Section 2.

    Ring angles are scaled so they total 2*pi, which makes the flattening
    independent of how cone-like the vertex is, then each neighbour is placed at
    its true edge LENGTH and its accumulated angle.
    """
    edge   = _gather_ring(pos, index, mask) - pos[:, None, :] * mask[:, :, None]
    length = np.sqrt((edge * edge).sum(axis=2)) + 1e-12
    unit   = edge / length[:, :, None]

    cos_between = (unit * _ring_next(unit, wrap)).sum(axis=2)
    angle       = np.arccos(np.clip(cos_between, -1.0, 1.0)) * mask

    # Literal rather than a module constant: only the FUNCTIONS get carried
    # across when the transpiler inlines this helper, so a module global would
    # be "used before assignment" in the lowered C++.
    two_pi = 6.283185307179586
    total  = angle.sum(axis=1)
    scale  = np.where(total > 1e-8, two_pi / np.maximum(total, 1e-30), 1.0)
    swept  = _exclusive_prefix(angle) * scale[:, None]
    return np.stack([length * np.cos(swept), length * np.sin(swept)],
                    axis=2) * mask[:, :, None]


def _span_weights(decal, mask, valence, width):
    """Span-aware edge weights -- Section 3.

    Each edge is weighted by how much of the ring it actually spans: the extent
    of the OTHER neighbours measured along the edge (``c_neg``) and across it
    (``f_pos - f_neg``). A neighbour crowded in among others gets little weight;
    one that spans a wide empty span gets a lot. Rows are normalized to sum to 1.
    """
    n      = decal.shape[0]
    length = np.sqrt((decal * decal).sum(axis=2)) + 1e-12
    tang   = decal / length[:, :, None]
    norm   = np.stack([-tang[:, :, 1], tang[:, :, 0]], axis=2)

    # (N, K, K): component of every OTHER ring edge along / across edge k.
    decal_t = np.transpose(decal, (0, 2, 1))
    along   = tang @ decal_t
    across  = norm @ decal_t

    off_diagonal = 1.0 - np.eye(width, dtype=np.float64)
    other        = mask[:, :, None] * mask[:, None, :] * off_diagonal[None, :, :]
    is_other     = other > 0.0
    big          = 1e30

    c_neg = np.min(np.where(is_other, along, big), axis=2)
    f_pos = np.max(np.where(is_other, across, -big), axis=2)
    f_neg = np.min(np.where(is_other, across, big), axis=2)

    # A ring of one has no "other" -- fall through to the uniform branch below.
    lone    = (other.sum(axis=2) > 0.0)
    c_neg   = np.where(lone, c_neg, 0.0)
    f_pos   = np.where(lone, f_pos, 0.0)
    f_neg   = np.where(lone, f_neg, 0.0)

    w       = np.abs(c_neg) * np.maximum(f_pos - f_neg, 1e-8) * mask
    total   = w.sum(axis=1)
    uniform = mask / np.maximum(valence, 1.0)[:, None]
    return np.where((total > 1e-12)[:, None],
                    w / np.maximum(total, 1e-30)[:, None], uniform)


def _fit_rotations(rest_edge, posed_edge, w, n):
    """Per-vertex best-fit rotation rest -> posed, by SVD -- Section 4.

    The weighted cross-covariance of the two edge sets, then the Kabsch
    reflection guard so the result is a proper rotation. Same batched form as
    ``procrustes_clusters``; ``np.linalg.svd`` must be tuple-unpacked for the
    transpiler to map it onto the deterministic Jacobi ``nd::svd``.
    """
    cov = np.transpose(rest_edge * w[:, :, None], (0, 2, 1)) @ posed_edge
    u, _s, vt = np.linalg.svd(cov)
    v              = np.transpose(vt, (0, 2, 1))
    ut             = np.transpose(u, (0, 2, 1))
    flip           = np.sign(np.linalg.det(v @ ut))
    guard          = np.tile(np.eye(3, dtype=np.float64), (n, 1, 1))
    guard[:, 2, 2] = flip
    return v @ guard @ ut


def _rotate_scale_2d(vh2, vp2):
    """Carry ``vh2`` onto ``vp2``'s frame: scale by ``|vp2|/|vh2|`` and rotate by
    the angle between them -- the 2D half of Section 5.

    The reference builds this from ``atan2(vp2) - atan2(vh2)``, but a rotation
    only ever needs ``cos`` and ``sin`` of that angle, and both fall straight out
    of the 2D dot and cross products. That skips ``arctan2`` (which the
    transpiler has no mapping for) and the branch cut with it.

    Where the epsilons go MATTERS, and not by a rounding-error margin. On a
    regular rest ring the weighted sum of decal positions very nearly cancels,
    so ``|vh2|`` lands around 1e-17 and the reference's ``+1e-12`` completely
    dominates the SCALE -- it is the epsilon, not the geometry, that sets how
    much of the rest layout survives here. The ANGLE has no such epsilon in the
    reference (``atan2`` needs none), so folding one into the cos/sin
    denominator would rescale the whole term by ``|vh2| / (|vh2| + 1e-12)``,
    which is a factor of ~1e-5, not a rounding difference. Hence: exact norms
    for the angle, epsilon'd norms for the scale.
    """
    len_h = np.sqrt((vh2 * vh2).sum(axis=1))
    len_p = np.sqrt((vp2 * vp2).sum(axis=1))
    dot   = vh2[:, 0] * vp2[:, 0] + vh2[:, 1] * vp2[:, 1]
    crs   = vh2[:, 0] * vp2[:, 1] - vh2[:, 1] * vp2[:, 0]
    # Only bites when a vector is EXACTLY zero, where atan2(0, 0) is 0 and the
    # rotated result is zero anyway -- so the choice of angle cannot show up.
    unit  = np.maximum(len_h * len_p, 1e-300)
    scale = (len_p + 1e-12) / (len_h + 1e-12)
    cos_t = (dot / unit) * scale
    sin_t = (crs / unit) * scale
    return np.stack([cos_t * vh2[:, 0] - sin_t * vh2[:, 1],
                     sin_t * vh2[:, 0] + cos_t * vh2[:, 1]], axis=1)


def _lift_to_surface(target, decal, center, nbr_pos, mask, wrap):
    """Lift a 2D decal-space target back onto the 3D surface -- Section 5.

    The ring is a triangle fan in decal space; the target is expressed in
    barycentric coordinates of whichever fan triangle reproduces it most closely
    (clamped, so a target outside the fan lands on its border) and those same
    coordinates are applied to the 3D triangle. This keeps the vertex ON the
    surface instead of stepping off it through the chord.
    """
    b   = decal
    c   = _ring_next(decal, wrap)
    tgt = target[:, None, :]

    d00 = (c * c).sum(axis=2)
    d01 = (c * b).sum(axis=2)
    d02 = (c * tgt).sum(axis=2)
    d11 = (b * b).sum(axis=2)
    d12 = (b * tgt).sum(axis=2)

    denom  = d00 * d11 - d01 * d01
    usable = (np.abs(denom) >= 1e-15) & (mask > 0.0)
    safe   = np.where(usable, denom, 1.0)

    bu  = np.clip((d11 * d02 - d01 * d12) / safe, 0.0, 1.0)
    bv  = np.clip((d00 * d12 - d01 * d02) / safe, 0.0, 1.0)
    bw  = np.clip(1.0 - bu - bv, 0.0, 1.0)
    tot = bu + bv + bw
    tot = np.where(tot > 1e-12, tot, 1.0)
    # One assignment per name: a tuple literal holding ARRAYS has no lowered
    # form ("use np.array / np.stack"), and stacking here just to unpack again
    # would be worse than three lines.
    bu = bu / tot
    bv = bv / tot
    bw = bw / tot

    nbr_next = _ring_next(nbr_pos, wrap)
    pos = (bw[:, :, None] * center[:, None, :]
           + bv[:, :, None] * nbr_pos
           + bu[:, :, None] * nbr_next)

    # Distance is measured in 2D; the fan's apex sits at the origin there, so
    # the bw term drops out of pt2d entirely.
    pt2d  = bv[:, :, None] * b + bu[:, :, None] * c
    delta = pt2d - tgt
    dist  = np.where(usable, np.sqrt((delta * delta).sum(axis=2)), 1e30)

    # Pick the FIRST closest triangle, matching the reference's strict "<".
    # argmin is unsupported, so select by mask and break ties with the same
    # prefix-count trick used for the ring angles.
    chosen   = (dist <= dist.min(axis=1)[:, None]) & usable
    chosen_f = chosen.astype(np.float64)
    first    = chosen_f * (1.0 - np.minimum(_exclusive_prefix(chosen_f), 1.0))
    found    = first.sum(axis=1)
    best     = (pos * first[:, :, None]).sum(axis=1)
    return np.where((found > 0.0)[:, None], best, center)


def patch_relax(points, rest_points, ring, iterations=30, alpha=1.0,
                surface_blend=0.8):
    """Relax ``points`` toward the rest edge layout of ``rest_points``.

    Parameters
    ----------
    points, rest_points : ``(N, 3)`` current (deformed) and rest positions.
    ring : ``(N, K)`` CCW 1-ring neighbour ids from ``build_ring_adjacency``,
        ``-1`` padded. An all-``-1`` row pins that vertex.
    iterations : Jacobi sweeps. Each reads the previous sweep's positions and
        writes a fresh buffer -- never in place, which would be Gauss-Seidel and
        would make the result depend on vertex order.
    alpha : how strongly the rest layout is enforced. 0 leaves the input alone.
    surface_blend : 0 relaxes through 3D space; 1 slides along the surface.
        Has NO EFFECT at ``alpha = 1`` -- see the note below.

    Returns the relaxed ``(N, 3)``.

    Note on ``surface_blend``
    ------------------------
    The reference builds the surface target as
    ``step * (vp2 - alpha * Rvh2)``, where ``Rvh2`` is ``vh2`` scaled by
    ``|vp2|/|vh2|`` and rotated by ``arg(vp2) - arg(vh2)``. That construction is
    ``vp2`` -- it maps ``vh2`` onto ``vp2`` exactly, by definition -- so the
    target collapses to ``step * (1 - alpha) * vp2`` and the surface branch does
    NOTHING when ``alpha`` is 1. Measured on a bunched torus: through-space
    leaves 59% of the input edge error after 20 sweeps, ``surface_blend = 0.8``
    leaves 87%, and ``surface_blend = 1.0`` leaves 100% -- the mesh does not move
    at all. This is faithful to the reference, not an artifact of vectorizing it.
    Raising ``surface_blend`` therefore only WEAKENS the relaxation unless
    ``alpha < 1``, which is why the shipped template defaults it to 0.
    """
    x     = np.asarray(points,      dtype=np.float64)
    x_hat = np.asarray(rest_points, dtype=np.float64)
    ring  = np.asarray(ring,        dtype=np.int64)
    n     = x.shape[0]
    width = ring.shape[1]
    if n == 0 or width == 0 or iterations <= 0:
        return x

    mask    = (ring >= 0).astype(np.float64)              # (N, K)
    index   = np.where(ring >= 0, ring, n)                # -1 -> the zero row
    valence = mask.sum(axis=1)                            # (N,)
    slots   = np.arange(width, dtype=np.float64)
    wrap    = (slots[None, :] + 1.0) >= valence[:, None]  # last valid slot

    # --- rest-invariant precomputation ---
    rest_decal = _decal_map(x_hat, index, mask, valence, wrap)
    w          = _span_weights(rest_decal, mask, valence, width)
    rest_edge  = _gather_ring(x_hat, index, mask) - x_hat[:, None, :] * mask[:, :, None]
    v_hat      = (w[:, :, None] * rest_edge).sum(axis=1)   # (N, 3)
    rest_2d    = (w[:, :, None] * rest_decal).sum(axis=1)  # (N, 2)

    # Damped Jacobi step -- a full step oscillates on exactly the
    # high-frequency modes this is meant to remove. Matches the reference.
    # A local, not a module constant, for the same reason as two_pi above.
    step_size   = 0.5
    use_surface = surface_blend > 1e-6

    for _sweep in range(iterations):
        posed_edge = _gather_ring(x, index, mask) - x[:, None, :] * mask[:, :, None]
        v_pose     = (w[:, :, None] * posed_edge).sum(axis=1)

        rot     = _fit_rotations(rest_edge, posed_edge, w, n)
        rotated = (rot @ v_hat[:, :, None])[:, :, 0]
        through = x + step_size * (v_pose - alpha * rotated)

        if use_surface:
            posed_decal = _decal_map(x, index, mask, valence, wrap)
            posed_2d    = (w[:, :, None] * posed_decal).sum(axis=1)
            target = step_size * (posed_2d
                                  - alpha * _rotate_scale_2d(rest_2d,
                                                             posed_2d))
            on_surface = _lift_to_surface(target, posed_decal, x,
                                          _gather_ring(x, index, mask),
                                          mask, wrap)
            step = (1.0 - surface_blend) * through + surface_blend * on_surface
        else:
            step = through

        # Pinned vertices (empty ring) never move.
        moves = (valence > 0.0)[:, None]
        x     = np.where(moves, step, x)

    return x
