"""Orthogonal Procrustes: the best rigid (rotation + translation, optional
uniform scale) transform that maps one ordered point set onto another,
solved in closed form via SVD.

Use it to rigidly "attach" something to a cluster of mesh vertices: feed
the REST positions of the tracked verts and their CURRENT (deformed)
positions, and you get the rigid frame the cluster has moved through. That
frame drives a constraint (a Procrustes / "vertex cluster" constraint),
robust to deformation because it fits the whole cluster, not a single tri.

Conventions
-----------
``procrustes_rigid`` works in the standard math (column-vector) convention:
``Q ~= s * (R @ P.T).T + t``.

``procrustes_matrix`` returns a **Maya-layout** (row-vector) 4x4 so it drops
straight onto a Maya matrix plug: ``p_row @ M == q_row`` (rotation in the
top-left 3x3 transposed, translation in row 3). That's the same layout
``mpynode`` reads/writes for matrix attrs.

Fully vectorized numpy -- no per-point loops.
"""

from __future__ import annotations

import numpy as np


def procrustes_rigid(P, Q, with_scale: bool = False):
    """Best rigid transform mapping ``P`` (N,3) onto ``Q`` (N,3).

    Returns ``(R, t, s)`` with ``R`` a proper rotation (3,3, det +1 -- no
    reflection), ``t`` the translation (3,), and ``s`` the uniform scale
    (1.0 unless ``with_scale``). In column convention: ``q = s * R @ p + t``.
    """
    P = np.asarray(P, dtype=np.float64)
    Q = np.asarray(Q, dtype=np.float64)
    if P.shape != Q.shape or P.ndim != 2 or P.shape[1] != 3 or P.shape[0] == 0:
        # Degenerate input -> identity (caller gets a no-op attachment).
        return np.eye(3), np.zeros(3), 1.0

    cP = P.mean(axis=0)
    cQ = Q.mean(axis=0)
    P0 = P - cP
    Q0 = Q - cQ

    # Cross-covariance + SVD.
    H = P0.T @ Q0
    U, S, Vt = np.linalg.svd(H)
    # Reflection guard: force a proper rotation (det +1).
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T

    if with_scale:
        var_p = float((P0 ** 2).sum())
        s = float((S * np.array([1.0, 1.0, d])).sum() / var_p) if var_p > 1e-12 else 1.0
    else:
        s = 1.0

    t = cQ - s * (R @ cP)
    return R, t, s


def procrustes_matrix(P, Q, with_scale: bool = False):
    """Maya-layout (row-vector) 4x4 attachment matrix mapping the rest world
    points ``P`` to the deformed world points ``Q`` (``p_row @ M == q_row``).

    Drop straight onto a Maya matrix plug (e.g. an mpynode matrix output).
    """
    R, t, s = procrustes_rigid(P, Q, with_scale=with_scale)
    M = np.eye(4, dtype=np.float64)
    M[:3, :3] = (s * R).T          # row-vector convention
    M[3, :3] = t
    return M


# ---- Vectorized multi-cluster attachment (orient MANY transforms in one call) ----


def procrustes_clusters(rest_pts, deformed_pts, clusters, bind_matrices,
                        with_scale: bool = False):
    """Vectorized Procrustes attachment for MANY transforms at once.

    Each transform owns its own vertex cluster. Returns the WORLD matrices
    (Maya layout, row-vector) the transforms should have so each rides the
    rigid motion of its cluster while preserving its bind offset:

        ``world_i = bind_matrices_i @ M_attach_i``

    where ``M_attach_i`` carries the cluster's REST verts onto its DEFORMED
    verts. At the bind frame (deformed == rest) ``M_attach_i`` is identity, so
    ``world_i == bind_matrices_i`` -- the offset is exactly preserved.

    Parameters
    ----------
    rest_pts, deformed_pts : (V, 3) -- rest + current world vertex positions.
    clusters : (N, L) int -- per-transform vertex ids, RAGGED clusters padded
        with ``-1`` (so all rows share width L).
    bind_matrices : (N, 4, 4) -- each transform's bind world matrix.
    with_scale : include uniform cluster scale in the attachment.

    Fully vectorized: one batched SVD solves all N clusters -- no Python loop
    over transforms.
    """
    rest_pts = np.asarray(rest_pts, dtype=np.float64)
    deformed_pts = np.asarray(deformed_pts, dtype=np.float64)
    clusters = np.asarray(clusters, dtype=np.int64)
    bind_matrices = np.asarray(bind_matrices, dtype=np.float64).reshape(-1, 4, 4)
    n = clusters.shape[0]
    if n == 0:
        return np.zeros((0, 4, 4), dtype=np.float64)

    # Gather cluster points; -1 padding indexes an appended zero row, then is
    # masked out of the centroid + covariance so it contributes nothing.
    rp = np.vstack([rest_pts, np.zeros((1, 3))])
    dp = np.vstack([deformed_pts, np.zeros((1, 3))])
    # np.take(..., axis=0) is byte-identical to ``rp[clusters]`` for an integer
    # index array and lowers deterministically to C++ (nd::take); the plain
    # advanced-index subscript does not.
    P = np.take(rp, clusters, axis=0)                  # (N, L, 3)
    Q = np.take(dp, clusters, axis=0)
    mask = clusters >= 0                               # (N, L)
    counts = np.maximum(mask.sum(axis=1), 1)           # (N,)

    cP = P.sum(axis=1) / counts[:, None]               # (N, 3)
    cQ = Q.sum(axis=1) / counts[:, None]
    P0 = (P - cP[:, None]) * mask[:, :, None]
    Q0 = (Q - cQ[:, None]) * mask[:, :, None]

    # Batched cross-covariance + SVD + reflection guard -> proper rotations.
    H = np.einsum("nli,nlj->nij", P0, Q0)              # (N, 3, 3)
    U, S, Vt = np.linalg.svd(H)
    Vt_t = np.transpose(Vt, (0, 2, 1))
    U_t = np.transpose(U, (0, 2, 1))
    d = np.sign(np.linalg.det(np.einsum("nij,njk->nik", Vt_t, U_t)))
    D = np.tile(np.eye(3), (n, 1, 1))
    D[:, 2, 2] = d
    R = np.einsum("nij,njk,nkl->nil", Vt_t, D, U_t)    # (N, 3, 3) col-conv

    if with_scale:
        var_p = (P0 ** 2).sum(axis=(1, 2))
        s = (S * np.stack([np.ones(n), np.ones(n), d], axis=1)).sum(axis=1)
        s = s / np.where(var_p > 1e-12, var_p, 1.0)
    else:
        s = np.ones(n)

    t = cQ - s[:, None] * np.einsum("nij,nj->ni", R, cP)   # (N, 3)

    # Maya-layout attachment matrices (row-vector): rest-world -> deformed-world
    M = np.tile(np.eye(4), (n, 1, 1))
    M[:, :3, :3] = np.transpose(s[:, None, None] * R, (0, 2, 1))
    M[:, 3, :3] = t

    # Compose with each transform's bind world to preserve its offset.
    return bind_matrices @ M


# ---- Vectorized matrix <-> Maya euler (Shoemake), all 6 rotate orders ----
# Ported from the user's reference: matrix_to_euler / matrix_inverse.

_EULER_SAFE = np.array([0, 1, 2, 0], dtype=np.intp)
_EULER_NEXT = np.array([1, 2, 0, 1], dtype=np.intp)
_EULER_ORDER = np.array([0, 8, 16, 4, 12, 20], dtype=np.intp)
_MAYA_EA = np.array(
    [[0, 1, 2], [1, 2, 0], [2, 0, 1], [0, 2, 1], [1, 0, 2], [2, 1, 0]],
    dtype=np.intp,
)
_EPS = 1e-9


def _euler_order_params(axes):
    """Decode Maya rotate-order indices (0=xyz .. 5=zyx) into Shoemake
    (i, j, k, h, n, s, f) parameters, each (N,)."""
    o = _EULER_ORDER[axes].copy()
    f = o & 1
    o >>= 1
    s = o & 1
    o >>= 1
    nn = o & 1
    o >>= 1
    i = _EULER_SAFE[o & 3]
    j = _EULER_NEXT[i + nn]
    k = _EULER_NEXT[i + 1 - nn]
    h = np.where(s.astype(bool), k, i)
    return i, j, k, h, nn, s, f


def matrix_to_euler(matrix, axes):
    """Vectorized batch of (N,4,4) Maya-layout matrices -> Maya euler angles
    in RADIANS, (N,3) in (rx, ry, rz) storage order.

    ``axes`` is an (N,) int array of Maya rotation orders (0=xyz .. 5=zyx).
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    axes = np.asarray(axes, dtype=np.intp)
    n_mat = matrix.shape[0]
    ar = np.arange(n_mat)

    i, j, k, h, nn, s, f = _euler_order_params(axes)

    # Strip scale: normalize each row of the 3x3, then transpose.
    scale = np.sqrt(np.sum(matrix[:, :3, :3] ** 2, axis=2))
    scale = np.where(scale > _EPS, scale, 1.0)
    m = np.transpose(matrix[:, :3, :3] / scale[:, :, None], (0, 2, 1))

    m_ii = m[ar, i, i]; m_ij = m[ar, i, j]; m_ik = m[ar, i, k]
    m_ji = m[ar, j, i]; m_jj = m[ar, j, j]; m_jk = m[ar, j, k]
    m_ki = m[ar, k, i]; m_kj = m[ar, k, j]; m_kk = m[ar, k, k]

    # Non-repeated axis solution (s == 0).
    yy_n = np.sqrt(m_ii ** 2 + m_ji ** 2)
    safe_n = yy_n > _EPS
    e0_n = np.where(safe_n, np.arctan2(m_kj, m_kk), np.arctan2(-m_jk, m_jj))
    e1_n = np.arctan2(-m_ki, yy_n)
    e2_n = np.where(safe_n, np.arctan2(m_ji, m_ii), 0.0)

    # Repeated axis solution (s == 1).
    yy_s = np.sqrt(m_ij ** 2 + m_ik ** 2)
    safe_s = yy_s > _EPS
    e0_s = np.where(safe_s, np.arctan2(m_ij, m_ik), np.arctan2(-m_jk, m_jj))
    e1_s = np.arctan2(yy_s, m_ii)
    e2_s = np.where(safe_s, np.arctan2(m_ji, -m_ki), 0.0)

    sb = s.astype(bool)
    e0 = np.where(sb, e0_s, e0_n)
    e1 = np.where(sb, e1_s, e1_n)
    e2 = np.where(sb, e2_s, e2_n)

    nb = nn.astype(bool)
    e0 = np.where(nb, -e0, e0)
    e1 = np.where(nb, -e1, e1)
    e2 = np.where(nb, -e2, e2)

    fb = f.astype(bool)
    e0, e2 = np.where(fb, e2, e0), np.where(fb, e0, e2)

    euler = np.stack((e0, e1, e2), axis=1)
    # Reorder the triple into Maya's (rx, ry, rz) storage order.
    return np.take_along_axis(euler, _MAYA_EA[axes], axis=1)


def matrix_inverse(matrix):
    """Vectorized inverse of (N,4,4) Maya-style TRS matrices (row-vector,
    orthogonal-rows 3x3 + translation in row 3). Matches Maya inverseMatrix."""
    matrix = np.asarray(matrix, dtype=np.float64)
    out = np.zeros(matrix.shape, dtype=matrix.dtype)
    sq = np.sum(matrix[:, :3, :3] ** 2, axis=2)
    sq = np.where(sq > _EPS, sq, 1.0)
    out[:, :3, :3] = np.transpose(matrix[:, :3, :3], (0, 2, 1)) / sq[:, None, :]
    out[:, 3, :3] = -np.einsum("ni,nij->nj", matrix[:, 3, :3], out[:, :3, :3])
    out[:, 3, 3] = 1.0
    return out
