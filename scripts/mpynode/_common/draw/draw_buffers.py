"""Qt-free helpers for the vectorized draw buffers.

The MPyLocator's MPxDrawOverride consumes typed buffers (lines /
points / polygons / shapes / text) instead of the old list-of-dicts
draw_items shape. The buffers are numpy arrays whose dispatch + draw
glue lives in ``_api2/mpy_locator.py`` (Qt-bound). Anything that
can be expressed without Qt lives here so it stays unit-testable
without instantiating widgets.

What's in this module:

* ``normalize_color(colors, n, default)`` -- accept None / 3-tuple /
 4-tuple / (N, 3) / (N, 4) and return a uniform ``(N, 4)`` float
 array in [0, 1]. Auto-promotes uint8 [0, 255] -> float [0, 1].
* ``fan_triangulate(points, indices, counts)`` -- convex-fan
 triangulation of an OBJ-style polygon mesh. Returns the flat
 ``(T*3, 3)`` triangle-list point array suitable for
 ``MUIDrawManager.mesh(kTriangles,...)``.
* ``expand_face_colors_to_triangles(face_colors, counts)`` -- given a
 ``(F, 4)`` per-face color array and per-face vertex counts, produce
 the ``(T*3, 4)`` per-vertex color array that parallels the
 triangulated point array.
* ``build_edge_list_from_polygons(indices, counts)`` -- emit a flat
 ``(E*2,)`` index array of edges (each face's perimeter) suitable
 for ``MUIDrawManager.mesh(kLines, point_array_indexed)``. Used by
 the wireframe path.

All functions accept array-like inputs (lists, tuples, np.ndarray)
and coerce via ``np.asarray``. None inputs are handled explicitly.
"""

from __future__ import annotations

import numpy as np


# ---- Color normalization ----


def normalize_color(colors, n: int, default=(1.0, 1.0, 1.0, 1.0)):
    """Return a ``(n, 4)`` float32 RGBA array in [0, 1].

    ``colors`` may be:

    * ``None``                -> uniform ``default`` color
    * ``(3,)`` or ``(4,)``    -> uniform color (promoted to RGBA;
                                  missing alpha defaults to 1.0)
    * ``(n, 3)`` or ``(n, 4)`` -> per-element color (one row per
                                   item; missing alpha = 1.0)

    uint8 inputs in [0, 255] are auto-promoted to float [0, 1]. Any
    other shape raises ValueError with a clear message.

    Returns ``np.ndarray(shape=(n, 4), dtype=np.float32)``.
    """
    if n <= 0:
        return np.zeros((0, 4), dtype=np.float32)
    if colors is None:
        arr = np.array(default, dtype=np.float32)
        if arr.shape == (3,):
            arr = np.concatenate([arr, [1.0]]).astype(np.float32)
        return np.tile(arr, (n, 1))

    src = np.asarray(colors)
    # uint8 -> float [0, 1]
    if src.dtype == np.uint8 or src.dtype == np.int32 or src.dtype == np.int64:
        if src.max(initial=0) > 1:
            src = src.astype(np.float32) / 255.0
    src = src.astype(np.float32)

    if src.ndim == 1:
        # Uniform color across all n.
        if src.shape == (3,):
            src = np.concatenate([src, [1.0]]).astype(np.float32)
        elif src.shape == (4,):
            pass
        else:
            raise ValueError(
                f"normalize_color: uniform color must be (3,) or (4,), got {src.shape}"
            )
        return np.tile(src, (n, 1))

    if src.ndim == 2:
        if src.shape[0]!= n:
            raise ValueError(
                f"normalize_color: per-element color count {src.shape[0]} "
                f"does not match expected {n}"
            )
        if src.shape[1] == 3:
            alpha = np.ones((n, 1), dtype=np.float32)
            return np.concatenate([src, alpha], axis=1)
        if src.shape[1] == 4:
            return src
        raise ValueError(
            f"normalize_color: per-element color must be (N, 3) or (N, 4), "
            f"got {src.shape}"
        )

    raise ValueError(f"normalize_color: ndim must be 1 or 2, got {src.ndim}")


# ---- Convex-fan triangulation (OBJ-style polygons) ----


def fan_triangulate(points, indices, counts):
    """Triangulate an OBJ-style polygon mesh as fans from each face's
    first vertex. Returns a flat triangle-list of points.

    Inputs:

    * ``points``  -- ``(P, 3)`` array of unique vertex positions
    * ``indices`` -- ``(sum(counts),)`` int array of indices into points
    * ``counts``  -- ``(F,)`` int array of vertex counts per face
                     (3 = tri, 4 = quad, 5+ = N-gon)

    Returns:

    * triangle-list points, ``(T*3, 3)`` float array where each
      consecutive triple is one triangle. T = sum(c - 2 for c in counts).

    Note this is fan-from-vert[0] per face, which is exact for convex
    faces and produces visually-wrong fills for concave faces. The
    contract: filled polygons are assumed convex. Use
    wireframe (colors=None) for concave shapes, or upgrade to
    ear-clipping in a future phase.

    Faces with < 3 verts are skipped silently.
    """
    points = np.asarray(points, dtype=np.float32)
    indices = np.asarray(indices, dtype=np.int64)
    counts = np.asarray(counts, dtype=np.int64)
    if counts.size == 0:
        return np.zeros((0, 3), dtype=np.float32)

    # Fully vectorized fan triangulation (no per-face Python loop).
    # Face f of size c contributes (c-2) triangles: (0, j+1, j+2) for
    # j in 0..c-3, indexing into that face's slice of ``indices``.
    face_off = np.cumsum(counts) - counts          # start offset into indices/face
    tpf = np.maximum(counts - 2, 0)                 # triangles per face (0 if c < 3)
    total = int(tpf.sum())
    if total == 0:
        return np.zeros((0, 3), dtype=np.float32)

    face_of_tri = np.repeat(np.arange(counts.size), tpf)        # (T,)
    tri_start = np.cumsum(tpf) - tpf                            # global tri start/face
    j = np.arange(total) - tri_start[face_of_tri]              # 0-based tri within face
    base = face_off[face_of_tri]                               # anchor offset into indices

    a = indices[base]            # anchor (corner 0) of each triangle's face
    b = indices[base + j + 1]
    c = indices[base + j + 2]

    # Interleave [a, b, c] per triangle to match the (T*3, 3) flat layout.
    out = np.empty((total * 3, 3), dtype=np.float32)
    out[0::3] = points[a]
    out[1::3] = points[b]
    out[2::3] = points[c]
    return out


def expand_face_colors_to_triangles(face_colors, counts):
    """Given a ``(F, 4)`` per-face color and per-face vertex counts,
    return a ``(T*3, 4)`` per-vertex color array that parallels the
    triangle-list output of ``fan_triangulate``.

    Each face contributes ``(face_size - 2)`` triangles, and each
    triangle gets 3 copies of the face's color.
    """
    face_colors = np.asarray(face_colors, dtype=np.float32)
    counts = np.asarray(counts, dtype=np.int64)
    if face_colors.shape[0]!= counts.shape[0]:
        raise ValueError(
            f"expand_face_colors_to_triangles: face_colors has "
            f"{face_colors.shape[0]} rows but counts has "
            f"{counts.shape[0]} faces"
        )
    out = []
    for face_idx, face_size in enumerate(counts):
        face_size = int(face_size)
        if face_size < 3:
            continue
        n_tris = face_size - 2
        # Each triangle gets 3 copies of this face's color.
        for _ in range(n_tris * 3):
            out.append(face_colors[face_idx])
    if not out:
        return np.zeros((0, 4), dtype=np.float32)
    return np.asarray(out, dtype=np.float32)


# ---- Wireframe edge extraction ----


def build_edge_point_pairs(points, indices, counts):
    """Build (start, end) point pairs for the wireframe (closed-line)
    rendering of every face's perimeter.

    Returns ``(starts, ends)`` where each is ``(E, 3)`` float arrays.
    Per face of size N, contributes N edges (closing back to vert 0).

    This is the wireframe path used when ``polygons["colors"]`` is None.
    """
    points = np.asarray(points, dtype=np.float32)
    indices = np.asarray(indices, dtype=np.int64)
    counts = np.asarray(counts, dtype=np.int64)

    starts = []
    ends = []
    cursor = 0
    for face_size in counts:
        face_size = int(face_size)
        if face_size < 2:
            cursor += face_size
            continue
        face_indices = indices[cursor: cursor + face_size]
        cursor += face_size
        for i in range(face_size):
            a_idx = int(face_indices[i])
            b_idx = int(face_indices[(i + 1) % face_size])
            starts.append(points[a_idx])
            ends.append(points[b_idx])

    if not starts:
        empty = np.zeros((0, 3), dtype=np.float32)
        return empty, empty
    return (
        np.asarray(starts, dtype=np.float32),
        np.asarray(ends, dtype=np.float32),
    )


# ---- Backface culling (view-dependent face filter) ----


def cull_backfaces_by_view(points, indices, counts, view_pos):
    """Return ``(filtered_indices, filtered_counts)`` containing only
    faces whose normal points toward ``view_pos``.

    Backface = a face whose outward normal points away from the
    viewer. Useful when rendering a transparent polygon mesh on the
    custom-locator UI overlay -- without culling, the back half of a
    closed mesh layers on top of the front half through alpha blend
    and visually inflates the apparent opacity.

    Inputs:

    * ``points``  -- ``(P, 3)`` array of unique vertex positions
      (same space as ``view_pos``).
    * ``indices`` -- ``(sum(counts),)`` int array of indices into points
      (one per face vertex, polygon-flat).
    * ``counts``  -- ``(F,)`` int array of vertex counts per face
      (3 = tri, 4 = quad, 5+ = N-gon).
    * ``view_pos`` -- ``(3,)`` viewer position in the same coordinate
      frame as ``points``. Typically the camera position transformed
      into the locator's local space.

    Convention: a face is FRONT-facing iff
    ``dot(normal, view_pos - centroid) > 0``. ``normal`` is computed
    from the first two edges of the face (``(v1-v0) x (v2-v0)``);
    callers are responsible for using consistent winding (CCW outward).
    Degenerate or zero-area faces are kept (they emit no triangles
    after fan-triangulation anyway).

    Returns:

    * ``filtered_indices`` -- ``(sum(filtered_counts),)`` int array.
    * ``filtered_counts``  -- ``(F_keep,)`` int array of vertex counts
      for the kept faces, preserving relative order.

    Coerces array-like inputs via ``np.asarray``. Empty input returns
    empty arrays. Never raises -- a fully-culled mesh returns
    zero-length arrays (caller short-circuits on ``counts.shape[0]``).
    """
    pts = np.asarray(points, dtype=np.float64)
    idxs = np.asarray(indices, dtype=np.int64)
    cnts = np.asarray(counts, dtype=np.int64)
    view = np.asarray(view_pos, dtype=np.float64).reshape(3)

    if pts.ndim != 2 or pts.shape[1] != 3:
        return (
            np.zeros((0,), dtype=np.int64),
            np.zeros((0,), dtype=np.int64),
        )
    if idxs.ndim != 1 or cnts.ndim != 1 or cnts.shape[0] == 0:
        return (
            np.zeros((0,), dtype=np.int64),
            np.zeros((0,), dtype=np.int64),
        )

    # Walk faces, compute centroid + normal, classify.
    keep_face = np.zeros((cnts.shape[0],), dtype=bool)
    cursor = 0
    for fi, c in enumerate(cnts):
        c_int = int(c)
        if c_int < 3:
            keep_face[fi] = True  # degenerate kept (no harm)
            cursor += c_int
            continue
        face = idxs[cursor:cursor + c_int]
        cursor += c_int
        if face.shape[0] < 3:
            keep_face[fi] = True
            continue
        v0 = pts[face[0]]
        v1 = pts[face[1]]
        v2 = pts[face[2]]
        normal = np.cross(v1 - v0, v2 - v0)
        # Centroid = mean of face verts (better than v0 for accuracy
        # on long/narrow N-gons).
        centroid = pts[face].mean(axis=0)
        if np.dot(normal, view - centroid) > 0.0:
            keep_face[fi] = True

    if not keep_face.any():
        return (
            np.zeros((0,), dtype=np.int64),
            np.zeros((0,), dtype=np.int64),
        )

    # Reassemble the kept faces' index ranges.
    starts = np.concatenate([[0], np.cumsum(cnts[:-1])])
    kept_indices_chunks = []
    kept_counts = []
    for fi in range(cnts.shape[0]):
        if not keep_face[fi]:
            continue
        s = int(starts[fi])
        c = int(cnts[fi])
        kept_indices_chunks.append(idxs[s:s + c])
        kept_counts.append(c)
    return (
        np.concatenate(kept_indices_chunks).astype(np.int64),
        np.asarray(kept_counts, dtype=np.int64),
    )


# ---- Per-corner / per-edge index maps (for per-vertex + face-varying colors) ----


def cull_backfaces_mask(points, indices, counts, view_pos):
    """Boolean ``(F,)`` keep-mask -- True for front-facing (kept) faces.

    Same convention as :func:`cull_backfaces_by_view` (a face is kept iff
    ``dot(normal, view_pos - centroid) > 0``); degenerate faces (<3 verts)
    are kept. Exposing the mask lets callers subset per-face / face-corner
    color data so it stays aligned with the culled mesh. Robust: returns
    an all-True mask on malformed input (so nothing is wrongly dropped).
    """
    pts = np.asarray(points, dtype=np.float64)
    idxs = np.asarray(indices, dtype=np.int64)
    cnts = np.asarray(counts, dtype=np.int64)
    if cnts.ndim != 1:
        return np.zeros((0,), dtype=bool)
    if pts.ndim != 2 or pts.shape[1] != 3 or idxs.ndim != 1:
        return np.ones((cnts.shape[0],), dtype=bool)
    try:
        view = np.asarray(view_pos, dtype=np.float64).reshape(3)
    except Exception:
        return np.ones((cnts.shape[0],), dtype=bool)

    keep = np.zeros((cnts.shape[0],), dtype=bool)
    cursor = 0
    for fi, c in enumerate(cnts):
        c_int = int(c)
        if c_int < 3:
            keep[fi] = True
            cursor += c_int
            continue
        face = idxs[cursor:cursor + c_int]
        cursor += c_int
        if face.shape[0] < 3:
            keep[fi] = True
            continue
        v0 = pts[face[0]]
        v1 = pts[face[1]]
        v2 = pts[face[2]]
        normal = np.cross(v1 - v0, v2 - v0)
        centroid = pts[face].mean(axis=0)
        if np.dot(normal, view - centroid) > 0.0:
            keep[fi] = True
    return keep


def apply_face_mask(indices, counts, keep_mask):
    """Subset a polygon mesh to the faces selected by ``keep_mask``.

    Returns ``(kept_indices, kept_counts, kept_corner_idx)`` where
    ``kept_corner_idx`` indexes into the ORIGINAL flattened face-corner
    list (``indices``). Use it to subset face-varying per-corner data
    (e.g. ``face_vertex_colors``) so it stays aligned with the culled
    mesh; subset per-face data directly with ``keep_mask``.
    """
    indices = np.asarray(indices, dtype=np.int64)
    counts = np.asarray(counts, dtype=np.int64)
    keep_mask = np.asarray(keep_mask, dtype=bool)
    z = np.zeros((0,), dtype=np.int64)
    if counts.shape[0] == 0 or not keep_mask.any():
        return z, z, z
    starts = np.concatenate([[0], np.cumsum(counts[:-1])]).astype(np.int64)
    corner_chunks = []
    kept_counts = []
    for fi in range(counts.shape[0]):
        if not keep_mask[fi]:
            continue
        s = int(starts[fi])
        c = int(counts[fi])
        corner_chunks.append(np.arange(s, s + c, dtype=np.int64))
        kept_counts.append(c)
    kept_corner_idx = np.concatenate(corner_chunks).astype(np.int64)
    return (
        indices[kept_corner_idx],
        np.asarray(kept_counts, dtype=np.int64),
        kept_corner_idx,
    )


def triangle_corner_indices(indices, counts):
    """Parallel to :func:`fan_triangulate`: for each triangle corner (in
    the same order as the returned ``(T*3, 3)`` points), return the index
    into ``points`` (for per-vertex colors) and the index into the
    flattened face-corner list / ``indices`` (for face-varying colors).

    Returns ``(point_idx, facecorner_idx)``, each ``(T*3,)`` int64.
    """
    indices = np.asarray(indices, dtype=np.int64)
    counts = np.asarray(counts, dtype=np.int64)
    pt_idx = []
    fc_idx = []
    cursor = 0
    for face_size in counts:
        face_size = int(face_size)
        if face_size < 3:
            cursor += face_size
            continue
        for i in range(1, face_size - 1):
            for local in (0, i, i + 1):
                pt_idx.append(int(indices[cursor + local]))
                fc_idx.append(cursor + local)
        cursor += face_size
    if not pt_idx:
        z = np.zeros((0,), dtype=np.int64)
        return z, z
    return (
        np.asarray(pt_idx, dtype=np.int64),
        np.asarray(fc_idx, dtype=np.int64),
    )


def edge_face_indices(counts):
    """Parallel to :func:`build_edge_point_pairs`: for each emitted edge,
    the index of the face it belongs to. Returns ``(E,)`` int64."""
    counts = np.asarray(counts, dtype=np.int64)
    out = []
    for f, face_size in enumerate(counts):
        face_size = int(face_size)
        if face_size < 2:
            continue
        out.extend([f] * face_size)
    if not out:
        return np.zeros((0,), dtype=np.int64)
    return np.asarray(out, dtype=np.int64)


def region_boundary_edges(indices, counts):
    """Find the BOUNDARY (outline) edges of an OBJ-style polygon buffer:
    the edges used by exactly ONE face. Interior edges (shared by two
    faces) are dropped, leaving only the silhouette of the patch.

    Returns ``(boundary_edges, boundary_faces)`` where:

    * ``boundary_edges`` -- ``(E, 2)`` int64 vertex-index pairs (into the
      same ``points`` the ``indices`` reference). Index ``points[edges]``
      to get ``(E, 2, 3)`` line segments.
    * ``boundary_faces`` -- ``(E,)`` int64, the owning face index of each
      boundary edge (each boundary edge belongs to exactly one face), so
      per-face wireframe colors stay aligned.

    Fully vectorized -- no per-face loops. Purely topological, so it works
    on any (remapped) connectivity and is winding-independent.
    """
    indices = np.asarray(indices, dtype=np.int64)
    counts = np.asarray(counts, dtype=np.int64)
    empty = (np.zeros((0, 2), dtype=np.int64), np.zeros((0,), dtype=np.int64))
    if indices.size == 0 or counts.size == 0:
        return empty

    starts = np.cumsum(counts) - counts                 # per-face start in indices
    total = int(counts.sum())
    face_of = np.repeat(np.arange(counts.shape[0]), counts)   # (total,) owning face
    within = np.arange(total) - starts[face_of]         # corner index within its face
    nxt = within + 1
    wrap = nxt >= counts[face_of]                        # last corner wraps to first
    nxt_pos = np.where(wrap, starts[face_of], starts[face_of] + nxt)

    a = indices
    b = indices[nxt_pos]
    # Canonicalize each edge as (min, max) so shared edges match regardless
    # of the two faces' winding; drop degenerate (a == b) edges.
    edges = np.sort(np.stack([a, b], axis=1), axis=1)
    keep = edges[:, 0] != edges[:, 1]
    edges = edges[keep]
    edge_face = face_of[keep]
    if edges.shape[0] == 0:
        return empty

    uniq, first_idx, cnt = np.unique(
        edges, axis=0, return_index=True, return_counts=True
    )
    boundary_mask = cnt == 1
    return uniq[boundary_mask], edge_face[first_idx[boundary_mask]]


# ---- Per-slot draw space (local vs screen) ----
#
# Every draw slot (lines / points / polygons / shapes / text) may carry a
# ``"space"`` key selecting how it is drawn:
#
# * ``"local"`` (default) -- coordinates are in the locator's OBJECT space;
#   Maya's world matrix brings them to world, so they translate/rotate/scale
#   with the transform and shrink with camera distance. For TEXT this ALSO
#   auto-scales the bitmap font size (via ``local_text_pixel_size`` below) so
#   glyphs track the object instead of collapsing when zoomed out. lines /
#   points / polygons / shapes keep their existing object-space drawing.
# * ``"screen"`` -- the slot's object-space points are projected to viewport
#   PIXELS here (object -> world -> clip -> pixel) and drawn with the 2D
#   MUIDrawManager primitives (line2d / point2d / mesh2d / circle2d / text2d)
#   at a CONSTANT pixel size, so they are zoom/distance independent (a HUD-like
#   overlay anchored to the object). This generalizes what ``dm.text()``
#   already did for text to every mechanism. 3D solid shapes (sphere / box /
#   cone / cylinder) have no 2D analog and fall back to local (the ``circle``
#   shape maps to ``circle2d``).
#
# The projection math is kept here (pure, numpy/scalar only) so it is
# unit-testable without a viewport; the Qt/VP2 glue in ``_api2/mpy_locator.py``
# feeds it the frame's matrices and calls the 2D draw primitives.

_VALID_SPACES = ("local", "screen")


def normalize_space(value):
    """Coerce a slot's ``"space"`` value to ``"local"`` or ``"screen"``.

    ``None`` / missing / unknown -> ``"local"`` (the safe default that
    preserves existing object-space behavior). Case- and whitespace-
    insensitive for strings; non-strings fall back to ``"local"``.
    """
    if isinstance(value, str):
        v = value.strip().lower()
        if v in _VALID_SPACES:
            return v
    return "local"


def matrix_uniform_scale(m16):
    """Representative uniform scale of a 4x4 row-major transform.

    Given a flat 16-element row-major matrix (Maya's ``MMatrix`` order,
    row-vector convention), returns the geometric mean of the three basis
    row lengths -- a single scalar that behaves well for both uniform and
    non-uniform scale when sizing a billboarded (screen-aligned) glyph.
    Returns 1.0 on degenerate/zero input.
    """
    m = [float(x) for x in m16]
    sx = (m[0] * m[0] + m[1] * m[1] + m[2] * m[2]) ** 0.5
    sy = (m[4] * m[4] + m[5] * m[5] + m[6] * m[6]) ** 0.5
    sz = (m[8] * m[8] + m[9] * m[9] + m[10] * m[10]) ** 0.5
    prod = sx * sy * sz
    if prod <= 0.0:
        return 1.0
    return prod ** (1.0 / 3.0)


def _clip_yw(point, m16):
    """Row-vector world->clip transform; return only (clip_y, clip_w)."""
    x, y, z = float(point[0]), float(point[1]), float(point[2])
    cy = x * m16[1] + y * m16[5] + z * m16[9] + m16[13]
    cw = x * m16[3] + y * m16[7] + z * m16[11] + m16[15]
    return cy, cw


def pixels_per_world_unit(view_proj_m16, viewport_h, anchor_world, up_world,
                          ref_len=1.0):
    """Screen pixels spanned by one WORLD unit along ``up_world`` at
    ``anchor_world``, measured through the world->clip ``view_proj``.

    Handles perspective and orthographic uniformly (it measures the actual
    projected delta rather than assuming a projection model). Returns
    ``None`` when the anchor (or the offset point) is at/behind the camera
    (clip w <= 0), so callers can fall back gracefully.

    * ``view_proj_m16`` -- flat 16-element row-major world->clip matrix.
    * ``viewport_h``    -- viewport height in pixels.
    * ``anchor_world``  -- (x, y, z) world position to measure at.
    * ``up_world``      -- world-space direction to measure along (typically
                           the camera's up axis); need not be unit length.
    * ``ref_len``       -- world length of the probe segment.
    """
    m = [float(x) for x in view_proj_m16]
    ux, uy, uz = float(up_world[0]), float(up_world[1]), float(up_world[2])
    nrm = (ux * ux + uy * uy + uz * uz) ** 0.5
    if nrm <= 1e-12 or ref_len <= 0.0:
        return None
    ux, uy, uz = ux / nrm, uy / nrm, uz / nrm
    ax, ay, az = float(anchor_world[0]), float(anchor_world[1]), float(anchor_world[2])
    b = (ax + ux * ref_len, ay + uy * ref_len, az + uz * ref_len)
    cyA, cwA = _clip_yw(anchor_world, m)
    cyB, cwB = _clip_yw(b, m)
    if cwA <= 1e-9 or cwB <= 1e-9:
        return None
    ndc_a = cyA / cwA
    ndc_b = cyB / cwB
    return abs(ndc_b - ndc_a) * 0.5 * float(viewport_h) / float(ref_len)


def local_text_pixel_size(size_obj, pixels_per_object_unit, min_px=6,
                          max_px=256):
    """Bitmap font size (pixels) for a glyph of object-space height
    ``size_obj`` drawn at ``pixels_per_object_unit`` on-screen density.

    ``pixels_per_object_unit`` is ``pixels_per_world_unit * world_scale`` --
    i.e. how many screen pixels one object-space unit spans at the glyph's
    depth. Multiplying by ``size_obj`` yields the pixel height that tracks
    the object (shrinks as it recedes, grows with the transform's scale).
    Clamped to ``[min_px, max_px]`` and rounded to an int.
    """
    px = float(size_obj) * float(pixels_per_object_unit)
    px = max(float(min_px), min(float(max_px), px))
    return int(round(px))


def project_object_points_to_pixels(points_obj, obj_world_m16, view_proj_m16,
                                    vp_w, vp_h):
    """Project OBJECT-space points to viewport PIXEL coordinates.

    Full transform ``object -> world -> clip -> NDC -> pixel``:

    * ``points_obj``    -- ``(N, 3)`` array-like of object-space points.
    * ``obj_world_m16`` -- flat 16 row-major object->world matrix.
    * ``view_proj_m16`` -- flat 16 row-major world->clip matrix.
    * ``vp_w`` / ``vp_h`` -- viewport size in pixels.

    Returns ``(pixels, valid)`` where ``pixels`` is ``(N, 2)`` float
    (x right, y up -- Maya's lower-left pixel origin) and ``valid`` is a
    ``(N,)`` bool mask (False where the point is at/behind the camera).
    Pixel rows for invalid points are 0 and must be skipped by the caller.
    """
    pts = np.asarray(points_obj, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 3 or pts.shape[0] == 0:
        return (
            np.zeros((0, 2), dtype=np.float64),
            np.zeros((0,), dtype=bool),
        )
    n = pts.shape[0]
    obj = np.asarray(obj_world_m16, dtype=np.float64).reshape(4, 4)
    vp = np.asarray(view_proj_m16, dtype=np.float64).reshape(4, 4)
    # object -> clip as one row-vector matrix (v_row @ obj @ vp).
    mvp = obj @ vp
    homog = np.empty((n, 4), dtype=np.float64)
    homog[:, :3] = pts
    homog[:, 3] = 1.0
    clip = homog @ mvp
    w = clip[:, 3]
    valid = w > 1e-9
    safe_w = np.where(valid, w, 1.0)
    ndc_x = clip[:, 0] / safe_w
    ndc_y = clip[:, 1] / safe_w
    pixels = np.empty((n, 2), dtype=np.float64)
    pixels[:, 0] = (ndc_x * 0.5 + 0.5) * float(vp_w)
    pixels[:, 1] = (ndc_y * 0.5 + 0.5) * float(vp_h)
    pixels[~valid] = 0.0
    return pixels, valid
