"""Pure-numpy SDF dual-marching-cubes field builder.

A self-contained, de-numba'd reproduction of the dual-marching-cubes
isosurface extractor in ``rl.math.geometry.sdf`` (and its numba kernels
in ``rl.math.geometry.utils._numba._sdf``), brought into mpynode so the
``mPyMesh`` SDF example can build a mesh from a set of transformed SDF
primitives -- and so the native C++ compiler can port the math.

Design notes for the native port (``native/import_follower.py``):
  * Everything the node needs is a TOP-LEVEL ``def`` (import_follower
    follows absolute imports of top-level def/class transitively).
  * The dual-marching-cubes lookup tables are built INSIDE
    ``dual_marching_cubes`` as locals -- import_follower does NOT pull
    module-level constants, so a table referenced from a kernel must live
    in the kernel's own body.
  * numpy is left as-is (import_follower skips numpy; the porter's
    translation_knowledge converts numpy element-wise math to C++ loops).
  * The marching-cubes kernels are written as plain Python loops
    (the numba ``prange`` -> ``range`` conversion) so they translate
    directly to C++; only the embarrassingly-parallel field evaluation
    and cube classification stay vectorized for Python viability.

Convention: matrices are Maya row-vector form (a point row-vector ``p``
maps as ``p @ M[:3,:3] + M[3,:3]``; translation lives in row 3). A shape's
input matrix carries translate/rotate/scale as ``M3 = diag(scale) @ R``;
``sample_shape`` decomposes it to reproduce ``rl``'s ``SDFx.sample``
(rigid-inverse + per-axis ``/scale`` + ``* min(abs(scale))`` distance
correction). Non-uniform scale yields an approximate SDF -- matching the
source.
"""
from __future__ import annotations

import numpy as np

# Shape-type codes for the ``shape_types`` array (module-level for callers;
# the followed functions below use the literals 0/1/2 so the native port
# does not depend on these constants).
SPHERE = 0
BOX = 1
CYLINDER = 2


# ---- SDF primitive evaluators (verbatim from rl.math.geometry.sdf) ----


def eval_sphere(X, Y, Z, radius=1.0):
    return np.sqrt(X**2 + Y**2 + Z**2) - radius


def eval_box(X, Y, Z, half_extents):
    half_extents = np.asarray(half_extents, dtype=np.float64)
    dx = np.abs(X) - half_extents[0]
    dy = np.abs(Y) - half_extents[1]
    dz = np.abs(Z) - half_extents[2]
    outside = np.sqrt(
        np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2 + np.maximum(dz, 0) ** 2
    )
    inside = np.minimum(np.maximum(dx, np.maximum(dy, dz)), 0)
    return outside + inside


def eval_cylinder(X, Y, Z, radius=0.5, height=1.0, axis=1):
    # Explicit per-axis branch (no Python list / list-indexing) so the native
    # transpiler can lower it. Radial axes are the two coordinates != axis; the
    # height axis is the third. Behaviour is identical to the old
    # coords=[X,Y,Z]; radial_axes=[i for i in range(3) if i != axis] form.
    axis = int(axis)
    half_height = height / 2.0
    if axis == 0:
        r0 = Y
        r1 = Z
        ax = X
    elif axis == 2:
        r0 = X
        r1 = Y
        ax = Z
    else:
        r0 = X
        r1 = Z
        ax = Y
    d_radial = np.sqrt(r0 ** 2 + r1 ** 2) - radius
    d_height = np.abs(ax) - half_height
    return np.sqrt(
        np.maximum(d_radial, 0) ** 2 + np.maximum(d_height, 0) ** 2
    ) + np.minimum(np.maximum(d_radial, d_height), 0)


# ---- CSG ops (verbatim from rl.math.geometry.sdf) ----


def sdf_union(a, b):
    return np.minimum(a, b)


def sdf_intersection(a, b):
    return np.maximum(a, b)


def sdf_difference(a, b):
    return np.maximum(a, -b)


def sdf_smooth_union(a, b, k=0.1):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


# ---- Transform math ----
# Ports of the rl numba kernels (_euler_to_matrix, _matrix_inverse,
# _matrix_point_multiply). Row-vector / Maya convention.


def euler_to_matrix(euler_radians, rotate_order=0):
    """Single-euler (radians) -> 4x4 rotation matrix, Maya convention.

    Faithful port of Ken Shoemake's ``_euler_to_matrix`` numba kernel
    used by ``rl.math.transforms.euler.to_matrix``. ``rotate_order`` is
    the Maya index 0..5 (XYZ=0, YZX=1, ZXY=2, XZY=3, YXZ=4, ZYX=5).
    Used at build/test time to compose shape matrices; the node's compute
    path does not call this (it decomposes the live plug matrix).
    """
    euler_safe = [0, 1, 2, 0]
    euler_next = [1, 2, 0, 1]
    euler_order = [0, 8, 16, 4, 12, 20]
    maya_ea = [
        [0, 1, 2], [1, 2, 0], [2, 0, 1], [0, 2, 1], [1, 0, 2], [2, 1, 0],
    ]
    axis = int(rotate_order)

    # _get_euler_order
    o_ = euler_order[axis]
    f = o_ & 1
    o_ >>= 1
    s = o_ & 1
    o_ >>= 1
    n = o_ & 1
    o_ >>= 1
    i = euler_safe[o_ & 3]
    j = euler_next[i + n]
    k = euler_next[i + 1 - n]

    e = np.asarray(euler_radians, dtype=np.float64).reshape(3)
    ea = [e[maya_ea[axis][0]], e[maya_ea[axis][1]], e[maya_ea[axis][2]]]
    if f == 1:
        ea[0], ea[2] = ea[2], ea[0]
    if n == 1:
        ea[0], ea[1], ea[2] = -ea[0], -ea[1], -ea[2]

    ci = np.cos(ea[0]); cj = np.cos(ea[1]); ch = np.cos(ea[2])
    si = np.sin(ea[0]); sj = np.sin(ea[1]); sh = np.sin(ea[2])
    cc = ci * ch; cs = ci * sh; sc = si * ch; ss = si * sh

    m = np.zeros((4, 4), dtype=np.float64)
    if s:
        m[i, i] = cj
        m[j, i] = sj * si
        m[k, i] = sj * ci
        m[i, j] = sj * sh
        m[j, j] = -cj * ss + cc
        m[k, j] = -cj * cs - sc
        m[i, k] = -sj * ch
        m[j, k] = cj * sc + cs
        m[k, k] = cj * cc - ss
    else:
        m[i, i] = cj * ch
        m[j, i] = sj * sc - cs
        m[k, i] = sj * cc + ss
        m[i, j] = cj * sh
        m[j, j] = sj * ss + cc
        m[k, j] = sj * cs - sc
        m[i, k] = -sj
        m[j, k] = cj * si
        m[k, k] = cj * ci
    m[3, 3] = 1.0
    return m


def affine_inverse(M):
    """Affine TRS fast-inverse (port of ``_matrix_inverse``). Exact for a
    rigid matrix (rotation rows have unit norm); divides each transposed
    column by the source row's squared norm to handle scaled rows."""
    M = np.asarray(M, dtype=np.float64)
    sx = M[0, 0] ** 2 + M[0, 1] ** 2 + M[0, 2] ** 2
    sy = M[1, 0] ** 2 + M[1, 1] ** 2 + M[1, 2] ** 2
    sz = M[2, 0] ** 2 + M[2, 1] ** 2 + M[2, 2] ** 2
    inv = np.zeros((4, 4), dtype=np.float64)
    inv[0, 0] = M[0, 0] / sx; inv[0, 1] = M[1, 0] / sy; inv[0, 2] = M[2, 0] / sz
    inv[1, 0] = M[0, 1] / sx; inv[1, 1] = M[1, 1] / sy; inv[1, 2] = M[2, 1] / sz
    inv[2, 0] = M[0, 2] / sx; inv[2, 1] = M[1, 2] / sy; inv[2, 2] = M[2, 2] / sz
    inv[3, 0] = -(M[3, 0] * inv[0, 0] + M[3, 1] * inv[1, 0] + M[3, 2] * inv[2, 0])
    inv[3, 1] = -(M[3, 0] * inv[0, 1] + M[3, 1] * inv[1, 1] + M[3, 2] * inv[2, 1])
    inv[3, 2] = -(M[3, 0] * inv[0, 2] + M[3, 1] * inv[1, 2] + M[3, 2] * inv[2, 2])
    inv[3, 3] = 1.0
    return inv


def matrix_point(points, M):
    """Row-vector point transform: ``p' = p @ M[:3,:3] + M[3,:3]``
    (port of ``_matrix_point_multiply``)."""
    points = np.asarray(points, dtype=np.float64)
    M = np.asarray(M, dtype=np.float64)
    return points[:, :3] @ M[:3, :3] + M[3, :3]


def decompose_translate(M):
    """Translation row of a Maya row-vector matrix (row 3, xyz)."""
    M = np.asarray(M, dtype=np.float64)
    return M[3, :3].copy()


def decompose_scale(M):
    """Per-axis scale = row norm of the upper-left 3x3 (``M[:3,:3]``)."""
    M = np.asarray(M, dtype=np.float64)
    M3 = M[:3, :3]
    return np.sqrt((M3 ** 2).sum(axis=1))


def decompose_rotation(M):
    """Orthonormal rotation rows: each ``M[:3,:3]`` row divided by its norm
    (unit rows for a zero-scale axis are avoided via the ``safe`` guard)."""
    M = np.asarray(M, dtype=np.float64)
    M3 = M[:3, :3]
    scale = np.sqrt((M3 ** 2).sum(axis=1))
    safe = np.where(scale == 0.0, 1.0, scale)
    return M3 / safe[:, None]


def decompose_matrix(M):
    """Decompose a Maya row-vector matrix into (translate, R, scale) where
    ``M[:3,:3] = diag(scale) @ R`` and R has orthonormal rows. Recovers the
    exact translate/rotate/scale the source stored separately (positive
    scale only -- a baked matrix cannot carry a negative-scale sign).

    A thin wrapper over the three single-return ``decompose_*`` helpers (the
    native transpiler cannot lower a tuple return, so the transpilable code paths
    -- ``sample_shape`` / the ``_*_bbox`` helpers -- call those directly; this
    keeps the historical 3-tuple API for any Python caller)."""
    return decompose_translate(M), decompose_rotation(M), decompose_scale(M)


def sample_shape(M, shape_type, radius, height, axis, half_extents, points):
    """Evaluate a transformed SDF primitive at ``points`` (P,3) -> (P,).

    Faithful reproduction of ``rl``'s ``SDFx.sample``: build the rigid
    matrix from the decomposed (R, translate), inverse-transform the world
    points into the primitive's local frame, divide by the (separated)
    scale, evaluate the unit-convention primitive, and scale the returned
    distance by ``min(abs(scale))``."""
    translate = decompose_translate(M)
    R = decompose_rotation(M)
    scale = decompose_scale(M)
    min_scale = float(np.min(np.abs(scale)))

    rigid = np.eye(4, dtype=np.float64)
    rigid[:3, :3] = R
    rigid[3, :3] = translate
    rigid_inv = affine_inverse(rigid)

    local = matrix_point(points, rigid_inv)
    local = local / scale

    Xt = local[:, 0]; Yt = local[:, 1]; Zt = local[:, 2]
    st = int(shape_type)
    if st == 1:
        d = eval_box(Xt, Yt, Zt, half_extents)
    elif st == 2:
        d = eval_cylinder(Xt, Yt, Zt, float(radius), float(height), int(axis))
    else:
        d = eval_sphere(Xt, Yt, Zt, float(radius))
    return d * min_scale


def _shape_bbox(M, shape_type, radius, height, axis, half_extents):
    """World-space AABB as a (2,3) array ``[min; max]`` (transpiler-friendly
    single-return form of shape_bounding_box; identical math)."""
    R = decompose_rotation(M)
    scale = decompose_scale(M)
    translate = decompose_translate(M)
    st = int(shape_type)
    if st == 1:
        local_half = np.asarray(half_extents, dtype=np.float64) * scale
    elif st == 2:
        local_half = np.full(3, float(radius), dtype=np.float64)
        local_half[int(axis)] = float(height) / 2.0
        local_half = local_half * scale
    else:
        local_half = np.full(3, float(radius), dtype=np.float64) * scale
    Rb = R.T
    world_half = np.abs(Rb) @ local_half
    out = np.empty((2, 3), dtype=np.float64)
    out[0] = translate - world_half
    out[1] = translate + world_half
    return out


def shape_bounding_box(M, shape_type, radius, height, axis, half_extents):
    """World-space AABB of a transformed primitive (port of ``SDFx.bounding_box``).
    Thin (min, max) tuple wrapper over ``_shape_bbox`` for Python callers."""
    bb = _shape_bbox(M, shape_type, radius, height, axis, half_extents)
    return bb[0], bb[1]


def _effective_bounds(matrices, shape_types, radius, height, axis, half_extents):
    """Union AABB as a (2,3) array ``[lo; hi]`` with 10% padding per side, over
    at least one shape (the node returns an empty mesh before this when n==0).
    Transpiler-friendly single-return form of effective_bounds (no ``position``
    offset -- the metaballs node never passes one); identical math otherwise."""
    n = matrices.shape[0]
    all_min = np.full(3, np.inf, dtype=np.float64)
    all_max = np.full(3, -np.inf, dtype=np.float64)
    for s in range(n):
        bb = _shape_bbox(
            matrices[s], shape_types[s], radius[s], height[s], axis[s],
            half_extents[s],
        )
        all_min = np.minimum(all_min, bb[0])
        all_max = np.maximum(all_max, bb[1])
    extent = all_max - all_min
    padding = extent * 0.1
    out = np.empty((2, 3), dtype=np.float64)
    out[0] = all_min - padding
    out[1] = all_max + padding
    return out


def effective_bounds(
    matrices, shape_types, radius, height, axis, half_extents, position=None
):
    """Union AABB of every shape (additive AND subtractive, matching the
    source) with 10% padding per side, offset by ``position``. (lo, hi) tuple
    wrapper over ``_effective_bounds`` for Python callers."""
    if position is None:
        position = np.zeros(3, dtype=np.float64)
    else:
        position = np.asarray(position, dtype=np.float64)

    n = matrices.shape[0]
    if n == 0:
        return (
            np.array([-1.0, -1.0, -1.0]) + position,
            np.array([1.0, 1.0, 1.0]) + position,
        )

    b = _effective_bounds(matrices, shape_types, radius, height, axis,
                          half_extents)
    return (b[0] + position, b[1] + position)


def make_grid(shape, bounds):
    """Build an ij-indexed sample grid (port of ``rl``'s ``make_grid``)."""
    min_bound = np.asarray(bounds[0], dtype=np.float64)
    max_bound = np.asarray(bounds[1], dtype=np.float64)
    x = np.linspace(min_bound[0], max_bound[0], shape[0])
    y = np.linspace(min_bound[1], max_bound[1], shape[1])
    z = np.linspace(min_bound[2], max_bound[2], shape[2])
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
    grid_origin = min_bound.copy()
    grid_spacing = (max_bound - min_bound) / (np.array(shape, dtype=np.float64) - 1)
    return X, Y, Z, grid_origin, grid_spacing


# ---- Dual marching cubes ----
# De-numba'd; all 6 kernels inlined as plain loops, lookup tables built as
# locals so the native porter carries them.


def _dmc_packed(scalar_field, iso_value, grid_origin, grid_spacing):
    """Two-pass, fixed-shape dual-marching-cubes returning a SINGLE packed 1-D
    float64 array (transpiler-friendly: no argwhere / fancy scatter / growable
    list / bit-shift / tuple return). Layout::

        [ V, F, <points: 3*V floats>, <indices: 4*F floats> ]

    V = vertex count, F = quad-face count (every face is a quad, so ``counts`` is
    reconstructed by the caller as F copies of 4). Faithful to the original
    ``dual_marching_cubes``: same corner-bit classification, same lexicographic
    ``(i,j,k)`` vertex numbering, same owned-edge ``(0,3,8)`` face order and
    winding, so ``mesh_from_shapes`` (which unpacks this) stays bit-identical to
    the historical output. Bit tests use a doubling accumulator instead of a left
    shift, and the owned edges/masks are small local arrays instead of a tuple
    loop -- both purely to stay inside the transpiler's supported subset."""
    scalar_field = np.asarray(scalar_field, dtype=np.float64)
    grid_origin = np.asarray(grid_origin, dtype=np.float64)
    grid_spacing = np.asarray(grid_spacing, dtype=np.float64)

    # --- lookup tables (locals so import_follower carries them to C++) ---
    edge_table = np.array([
        0x000, 0x109, 0x203, 0x30a, 0x406, 0x50f, 0x605, 0x70c,
        0x80c, 0x905, 0xa0f, 0xb06, 0xc0a, 0xd03, 0xe09, 0xf00,
        0x190, 0x099, 0x393, 0x29a, 0x596, 0x49f, 0x795, 0x69c,
        0x99c, 0x895, 0xb9f, 0xa96, 0xd9a, 0xc93, 0xf99, 0xe90,
        0x230, 0x339, 0x033, 0x13a, 0x636, 0x73f, 0x435, 0x53c,
        0xa3c, 0xb35, 0x83f, 0x936, 0xe3a, 0xf33, 0xc39, 0xd30,
        0x3a0, 0x2a9, 0x1a3, 0x0aa, 0x7a6, 0x6af, 0x5a5, 0x4ac,
        0xbac, 0xaa5, 0x9af, 0x8a6, 0xfaa, 0xea3, 0xda9, 0xca0,
        0x460, 0x569, 0x663, 0x76a, 0x066, 0x16f, 0x265, 0x36c,
        0xc6c, 0xd65, 0xe6f, 0xf66, 0x86a, 0x963, 0xa69, 0xb60,
        0x5f0, 0x4f9, 0x7f3, 0x6fa, 0x1f6, 0x0ff, 0x3f5, 0x2fc,
        0xdfc, 0xcf5, 0xfff, 0xef6, 0x9fa, 0x8f3, 0xbf9, 0xaf0,
        0x650, 0x759, 0x453, 0x55a, 0x256, 0x35f, 0x055, 0x15c,
        0xe5c, 0xf55, 0xc5f, 0xd56, 0xa5a, 0xb53, 0x859, 0x950,
        0x7c0, 0x6c9, 0x5c3, 0x4ca, 0x3c6, 0x2cf, 0x1c5, 0x0cc,
        0xfcc, 0xec5, 0xdcf, 0xcc6, 0xbca, 0xac3, 0x9c9, 0x8c0,
        0x8c0, 0x9c9, 0xac3, 0xbca, 0xcc6, 0xdcf, 0xec5, 0xfcc,
        0x0cc, 0x1c5, 0x2cf, 0x3c6, 0x4ca, 0x5c3, 0x6c9, 0x7c0,
        0x950, 0x859, 0xb53, 0xa5a, 0xd56, 0xc5f, 0xf55, 0xe5c,
        0x15c, 0x055, 0x35f, 0x256, 0x55a, 0x453, 0x759, 0x650,
        0xaf0, 0xbf9, 0x8f3, 0x9fa, 0xef6, 0xfff, 0xcf5, 0xdfc,
        0x2fc, 0x3f5, 0x0ff, 0x1f6, 0x6fa, 0x7f3, 0x4f9, 0x5f0,
        0xb60, 0xa69, 0x963, 0x86a, 0xf66, 0xe6f, 0xd65, 0xc6c,
        0x36c, 0x265, 0x16f, 0x066, 0x76a, 0x663, 0x569, 0x460,
        0xca0, 0xda9, 0xea3, 0xfaa, 0x8a6, 0x9af, 0xaa5, 0xbac,
        0x4ac, 0x5a5, 0x6af, 0x7a6, 0x0aa, 0x1a3, 0x2a9, 0x3a0,
        0xd30, 0xc39, 0xf33, 0xe3a, 0x936, 0x83f, 0xb35, 0xa3c,
        0x53c, 0x435, 0x73f, 0x636, 0x13a, 0x033, 0x339, 0x230,
        0xe90, 0xf99, 0xc93, 0xd9a, 0xa96, 0xb9f, 0x895, 0x99c,
        0x69c, 0x795, 0x49f, 0x596, 0x29a, 0x393, 0x099, 0x190,
        0xf00, 0xe09, 0xd03, 0xc0a, 0xb06, 0xa0f, 0x905, 0x80c,
        0x70c, 0x605, 0x50f, 0x406, 0x30a, 0x203, 0x109, 0x000,
    ], dtype=np.int64)
    edge_vertices = np.array([
        [0, 1], [1, 2], [2, 3], [3, 0],
        [4, 5], [5, 6], [6, 7], [7, 4],
        [0, 4], [1, 5], [2, 6], [3, 7],
    ], dtype=np.int32)
    corner_offsets = np.array([
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
    ], dtype=np.int32)
    edge_axis = np.array([0, 1, 0, 1, 0, 1, 0, 1, 2, 2, 2, 2], dtype=np.int32)
    face_offsets_x = np.array(
        [[0, 0, 0], [0, -1, 0], [0, -1, -1], [0, 0, -1]], dtype=np.int32
    )
    face_offsets_y = np.array(
        [[0, 0, 0], [-1, 0, 0], [-1, 0, -1], [0, 0, -1]], dtype=np.int32
    )
    face_offsets_z = np.array(
        [[0, 0, 0], [-1, 0, 0], [-1, -1, 0], [0, -1, 0]], dtype=np.int32
    )
    owned = np.array([0, 3, 8], dtype=np.int64)
    owned_masks = np.array([1, 8, 256], dtype=np.int64)

    nx, ny, nz = scalar_field.shape
    cx = nx - 1
    cy = ny - 1
    cz = nz - 1
    if cx <= 0 or cy <= 0 or cz <= 0:
        empty = np.empty(2, dtype=np.float64)
        empty[0] = 0.0
        empty[1] = 0.0
        return empty

    ox = float(grid_origin[0]); oy = float(grid_origin[1]); oz = float(grid_origin[2])
    hx = float(grid_spacing[0]); hy = float(grid_spacing[1]); hz = float(grid_spacing[2])

    # --- pass 1: per-cube corner-bit config + lexicographic vertex numbering.
    # Visiting (i,j,k) in C-order and numbering active cubes 0,1,2,... reproduces
    # argwhere(active).astype + arange scatter EXACTLY. ---
    cfg_grid = np.full((cx, cy, cz), 0, dtype=np.int64)
    cube_to_vertex = np.full((cx, cy, cz), -1, dtype=np.int64)
    vc = 0
    for i in range(cx):
        for j in range(cy):
            for k in range(cz):
                cfg = 0
                bit = 1
                for c in range(8):
                    cox = int(corner_offsets[c, 0])
                    coy = int(corner_offsets[c, 1])
                    coz = int(corner_offsets[c, 2])
                    if float(scalar_field[i + cox, j + coy, k + coz]) >= iso_value:
                        cfg = cfg + bit
                    bit = bit * 2
                cfg_grid[i, j, k] = cfg
                if cfg > 0 and cfg < 255:
                    cube_to_vertex[i, j, k] = vc
                    vc = vc + 1

    if vc == 0:
        empty = np.empty(2, dtype=np.float64)
        empty[0] = 0.0
        empty[1] = 0.0
        return empty

    # --- pass 2: dual vertex per active cube (mean of active-edge crossings) ---
    points = np.empty((vc, 3), dtype=np.float64)
    for i in range(cx):
        for j in range(cy):
            for k in range(cz):
                cfg = int(cfg_grid[i, j, k])
                if cfg <= 0 or cfg >= 255:
                    continue
                v = int(cube_to_vertex[i, j, k])
                edge_bits = int(edge_table[cfg])
                sx = 0.0
                sy = 0.0
                sz = 0.0
                count = 0
                ebit = 1
                for e in range(12):
                    if (edge_bits & ebit) != 0:
                        c0 = int(edge_vertices[e, 0])
                        c1 = int(edge_vertices[e, 1])
                        o0x = int(corner_offsets[c0, 0])
                        o0y = int(corner_offsets[c0, 1])
                        o0z = int(corner_offsets[c0, 2])
                        o1x = int(corner_offsets[c1, 0])
                        o1y = int(corner_offsets[c1, 1])
                        o1z = int(corner_offsets[c1, 2])
                        v0 = float(scalar_field[i + o0x, j + o0y, k + o0z])
                        v1 = float(scalar_field[i + o1x, j + o1y, k + o1z])
                        dv = v1 - v0
                        if abs(dv) < 1e-10:
                            t = 0.5
                        else:
                            t = (iso_value - v0) / dv
                        p0x = ox + (i + o0x) * hx
                        p1x = ox + (i + o1x) * hx
                        p0y = oy + (j + o0y) * hy
                        p1y = oy + (j + o1y) * hy
                        p0z = oz + (k + o0z) * hz
                        p1z = oz + (k + o1z) * hz
                        sx = sx + p0x + t * (p1x - p0x)
                        sy = sy + p0y + t * (p1y - p0y)
                        sz = sz + p0z + t * (p1z - p0z)
                        count = count + 1
                    ebit = ebit * 2
                if count > 0:
                    inv = 1.0 / count
                    points[v, 0] = sx * inv
                    points[v, 1] = sy * inv
                    points[v, 2] = sz * inv
                else:
                    points[v, 0] = ox + (i + 0.5) * hx
                    points[v, 1] = oy + (j + 0.5) * hy
                    points[v, 2] = oz + (k + 0.5) * hz

    # --- pass 3: quad faces on owned edges (0,3,8), gradient winding. Same
    # lexicographic cube order + owned-edge order as the vertex pass. ---
    idxbuf = np.empty(3 * vc * 4, dtype=np.int64)
    nf = 0
    for i in range(cx):
        for j in range(cy):
            for k in range(cz):
                cfg = int(cfg_grid[i, j, k])
                if cfg <= 0 or cfg >= 255:
                    continue
                edge_bits = int(edge_table[cfg])
                for eo in range(3):
                    e = int(owned[eo])
                    emask = int(owned_masks[eo])
                    if (edge_bits & emask) == 0:
                        continue
                    ax = int(edge_axis[e])
                    if ax == 0:
                        offs = face_offsets_x
                    elif ax == 1:
                        offs = face_offsets_y
                    else:
                        offs = face_offsets_z
                    quad = np.full(4, -1, dtype=np.int64)
                    valid = 1
                    for nidx in range(4):
                        ci = i + int(offs[nidx, 0])
                        cj = j + int(offs[nidx, 1])
                        ck = k + int(offs[nidx, 2])
                        if ci < 0 or ci >= cx or cj < 0 or cj >= cy or ck < 0 or ck >= cz:
                            valid = 0
                            break
                        vmap = int(cube_to_vertex[ci, cj, ck])
                        if vmap < 0:
                            valid = 0
                            break
                        quad[nidx] = vmap
                    if valid == 0:
                        continue
                    c0 = int(edge_vertices[e, 0])
                    c1 = int(edge_vertices[e, 1])
                    o0x = int(corner_offsets[c0, 0])
                    o0y = int(corner_offsets[c0, 1])
                    o0z = int(corner_offsets[c0, 2])
                    o1x = int(corner_offsets[c1, 0])
                    o1y = int(corner_offsets[c1, 1])
                    o1z = int(corner_offsets[c1, 2])
                    v0 = float(scalar_field[i + o0x, j + o0y, k + o0z])
                    v1 = float(scalar_field[i + o1x, j + o1y, k + o1z])
                    base = nf * 4
                    if v0 < v1:
                        idxbuf[base + 0] = int(quad[0])
                        idxbuf[base + 1] = int(quad[1])
                        idxbuf[base + 2] = int(quad[2])
                        idxbuf[base + 3] = int(quad[3])
                    else:
                        idxbuf[base + 0] = int(quad[3])
                        idxbuf[base + 1] = int(quad[2])
                        idxbuf[base + 2] = int(quad[1])
                        idxbuf[base + 3] = int(quad[0])
                    nf = nf + 1

    total = 2 + 3 * vc + 4 * nf
    packed = np.empty(total, dtype=np.float64)
    packed[0] = float(vc)
    packed[1] = float(nf)
    packed[2:2 + 3 * vc] = points.ravel()
    if nf > 0:
        packed[2 + 3 * vc:2 + 3 * vc + 4 * nf] = idxbuf[0:4 * nf].astype(np.float64)
    return packed


def dual_marching_cubes(scalar_field, iso_value, grid_origin, grid_spacing):
    """Extract a quad-dominant dual-marching-cubes isosurface from a scalar
    field. Returns ``(points (V,3) float64, counts (F,) int32 all-4,
    indices (4F,) int32)``. Thin wrapper that unpacks the packed 1-D array from
    ``_dmc_packed`` (the transpiler-friendly single-return core), preserving the
    historical (points, counts, indices) tuple API and dtypes."""
    packed = _dmc_packed(scalar_field, iso_value, grid_origin, grid_spacing)
    v_count = int(packed[0])
    f_count = int(packed[1])
    if v_count == 0:
        return (
            np.zeros((0, 3), dtype=np.float64),
            np.zeros(0, dtype=np.int32),
            np.zeros(0, dtype=np.int32),
        )
    points = packed[2:2 + 3 * v_count].reshape((v_count, 3)).copy()
    if f_count == 0:
        return (
            points,
            np.zeros(0, dtype=np.int32),
            np.zeros(0, dtype=np.int32),
        )
    indices = packed[2 + 3 * v_count:2 + 3 * v_count + 4 * f_count].astype(np.int32)
    counts = np.full(f_count, 4, dtype=np.int32)
    return points, counts, indices


# ---- Top-level driver: ordered shape stream -> mesh ----


def _mesh_packed(
    matrices, shape_types, additive, smoothing, radius, height, axis,
    half_extents, resolution, iso_value=0.0,
):
    """Transpiler-friendly single-return core of ``mesh_from_shapes``: fold the
    ordered SDF stream into a scalar field and dual-march it, returning the
    ``_dmc_packed`` packed 1-D float64 array (``[V, F, points..., indices...]``).

    ``resolution`` is a SCALAR (the metaballs node's ``resolution`` plug); the
    grid is built from ``np.linspace`` + gathered indices (``np.take``) instead
    of ``np.meshgrid`` so the native transpiler can lower it -- the gathered
    values are bit-identical to ``meshgrid(...).ravel()``. Every construct here
    is inside the deterministic transpiler's supported subset; ``mesh_from_shapes``
    unpacks this into the historical (points, counts, indices) tuple, so the
    parity harness (which exercises ``mesh_from_shapes``) gates this code."""
    matrices = np.asarray(matrices, dtype=np.float64)
    n = matrices.shape[0]
    if n == 0:
        empty = np.empty(2, dtype=np.float64)
        empty[0] = 0.0
        empty[1] = 0.0
        return empty

    shape_types = np.asarray(shape_types)
    additive = np.asarray(additive)
    smoothing = np.asarray(smoothing, dtype=np.float64)
    radius = np.asarray(radius, dtype=np.float64)
    height = np.asarray(height, dtype=np.float64)
    axis = np.asarray(axis)
    half_extents = np.asarray(half_extents, dtype=np.float64)

    rr = float(int(resolution))

    bounds = _effective_bounds(
        matrices, shape_types, radius, height, axis, half_extents
    )
    lo = bounds[0]
    hi = bounds[1]
    lo0 = float(lo[0]); lo1 = float(lo[1]); lo2 = float(lo[2])
    hi0 = float(hi[0]); hi1 = float(hi[1]); hi2 = float(hi[2])

    nx = max(2, int(np.ceil((hi0 - lo0) * rr)))
    ny = max(2, int(np.ceil((hi1 - lo1) * rr)))
    nz = max(2, int(np.ceil((hi2 - lo2) * rr)))

    # --- sample grid: linspace per axis, gathered by C-order flat index (an
    # exact stand-in for meshgrid(x,y,z,indexing="ij").ravel()) ---
    x = np.linspace(lo0, hi0, nx)
    y = np.linspace(lo1, hi1, ny)
    z = np.linspace(lo2, hi2, nz)
    npts = nx * ny * nz
    fidx = np.arange(npts)
    ii = fidx // (ny * nz)
    jj = (fidx // nz) % ny
    kk = fidx % nz
    gx = np.take(x, ii)
    gy = np.take(y, jj)
    gz = np.take(z, kk)
    grid_points = np.stack([gx, gy, gz], axis=-1)

    # --- CSG fold (base shape, then union / smooth-union / difference) ---
    combined = sample_shape(
        matrices[0], shape_types[0], radius[0], height[0], axis[0],
        half_extents[0], grid_points,
    ).reshape((nx, ny, nz))

    for s in range(1, n):
        sdf = sample_shape(
            matrices[s], shape_types[s], radius[s], height[s], axis[s],
            half_extents[s], grid_points,
        ).reshape((nx, ny, nz))
        if int(additive[s]) != 0:
            if float(smoothing[s]) > 0.0:
                combined = sdf_smooth_union(combined, sdf, float(smoothing[s]))
            else:
                combined = sdf_union(combined, sdf)
        else:
            combined = sdf_difference(combined, sdf)

    origin = lo
    spacing = np.empty(3, dtype=np.float64)
    spacing[0] = (hi0 - lo0) / (nx - 1)
    spacing[1] = (hi1 - lo1) / (ny - 1)
    spacing[2] = (hi2 - lo2) / (nz - 1)

    return _dmc_packed(combined, iso_value, origin, spacing)


def mesh_from_shapes(
    matrices, shape_types, additive, smoothing, radius, height, axis,
    half_extents, resolution, iso_value=0.0,
):
    """Build a dual-marching-cubes mesh from an ORDERED stream of SDF
    primitives. Each shape ``s`` carries a row-vector world matrix, a type
    code (0 sphere / 1 box / 2 cylinder), an additive flag, a smoothing k,
    and its dimensions. Shapes are folded left-to-right: shape 0 is the
    base; each later shape is unioned (or smooth-unioned when smoothing>0)
    if additive, else subtracted (difference). Returns
    ``(points, counts, indices)`` ready for ``MFnMesh.create``.

    Thin tuple wrapper over the transpiler-friendly ``_mesh_packed`` core (which
    the native compiler lowers directly). ``resolution`` may be a scalar or, for
    backward compatibility, a 0-d array."""
    packed = _mesh_packed(
        matrices, shape_types, additive, smoothing, radius, height, axis,
        half_extents, resolution, iso_value,
    )
    v_count = int(packed[0])
    f_count = int(packed[1])
    if v_count == 0:
        return (
            np.zeros((0, 3), dtype=np.float64),
            np.zeros(0, dtype=np.int32),
            np.zeros(0, dtype=np.int32),
        )
    points = packed[2:2 + 3 * v_count].reshape((v_count, 3)).copy()
    if f_count == 0:
        return (
            points,
            np.zeros(0, dtype=np.int32),
            np.zeros(0, dtype=np.int32),
        )
    indices = packed[2 + 3 * v_count:2 + 3 * v_count + 4 * f_count].astype(np.int32)
    counts = np.full(f_count, 4, dtype=np.int32)
    return points, counts, indices
