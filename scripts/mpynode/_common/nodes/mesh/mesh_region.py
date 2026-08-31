"""Vectorized helpers to turn a live mesh into draw-buffer arrays and to
extract a face-region sub-buffer -- the building block for mesh-region
gizmos (e.g. a control that highlights the patch of a deforming character
mesh it is bound to).

Everything is fully vectorized numpy (no per-face Python loops), so it
stays cheap even on dense meshes and large regions.

Reads a live ``MFnMesh`` (what an mpynode ``"mesh"`` input delivers). Feed
a node's ``worldMesh[0]`` so the geometry comes in WORLD space; then a
gizmo locator left at the origin draws + hover-tests it directly.
"""

from __future__ import annotations

import numpy as np
import maya.api.OpenMaya as om


def _is_api2(mesh) -> bool:
    """True for an API-2.0 function set, False for a legacy API-1.0 one.
    Both classes are named ``MFnMesh``, so we distinguish by module:
    API 1.0 is ``maya.OpenMaya``; API 2.0 reports ``OpenMaya``."""
    return type(mesh).__module__ != "maya.OpenMaya"


def _arrays_api1(mesh, space):
    """Legacy API-1.0 read path. API 1.0 has no vectorized point accessor,
    so points go through a small per-vertex loop; connectivity uses the
    scalar-iterable MIntArray (np.fromiter)."""
    import maya.OpenMaya as om1

    space1 = om1.MSpace.kObject if space is None else int(space)
    pa = om1.MPointArray()
    mesh.getPoints(pa, space1)
    n = pa.length()
    pts = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        p = pa[i]
        pts[i, 0] = p.x
        pts[i, 1] = p.y
        pts[i, 2] = p.z
    counts1 = om1.MIntArray()
    connects1 = om1.MIntArray()
    mesh.getVertices(counts1, connects1)
    counts = np.fromiter(counts1, dtype=np.int64, count=counts1.length())
    connects = np.fromiter(connects1, dtype=np.int64, count=connects1.length())
    return pts, counts, connects


def mesh_arrays(mesh, space=None):
    """Return ``(points (V,3) float64, counts (F,) int64, connects (C,) int64)``
    for an ``MFnMesh`` (API 2.0 preferred, API 1.0 supported).

    ``points`` are the vertex positions, ``counts`` the per-face vertex
    count, ``connects`` the flat polygon-vertex connectivity (OBJ-style).
    ``space`` defaults to the mesh's own coordinates (``kObject``) -- for a
    ``worldMesh``-fed input that already IS world space.

    The fast path expects an API-2.0 ``MFnMesh`` (what a locator's bare
    ``"mesh"`` input name delivers) and is fully vectorized. An API-1.0
    ``MFnMesh`` (e.g. ``self.<meshInput>`` via the plug proxy) is handled
    via a legacy fallback.
    """
    if not _is_api2(mesh):
        return _arrays_api1(mesh, space)
    if space is None:
        space = om.MSpace.kObject
    # getPoints -> MPointArray; np.array gives (V, 4) [x,y,z,w] -> drop w.
    pts = np.asarray(mesh.getPoints(space))[:, :3].astype(np.float64)
    counts_arr, connects_arr = mesh.getVertices()
    counts = np.asarray(counts_arr, dtype=np.int64)
    connects = np.asarray(connects_arr, dtype=np.int64)
    return pts, counts, connects


def _normals_api1(mesh, space):
    """Legacy API-1.0 per-vertex normal read (out-param + small loop)."""
    import maya.OpenMaya as om1

    space1 = om1.MSpace.kObject if space is None else int(space)
    nrm = om1.MFloatVectorArray()
    mesh.getVertexNormals(False, nrm, space1)
    n = nrm.length()
    out = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        v = nrm[i]
        out[i, 0] = v.x
        out[i, 1] = v.y
        out[i, 2] = v.z
    return out


def mesh_vertex_normals(mesh, space=None):
    """Return ``(V, 3)`` unit per-vertex normals (Maya's averaged vertex
    normals) for an ``MFnMesh``, aligned with ``mesh_arrays`` point order.

    Use these to push a region off the surface along its own normals (kills
    Z-fighting) or to drive a normal-aligned pop animation. API 2.0 is
    vectorized; API 1.0 falls back to a small loop.
    """
    if not _is_api2(mesh):
        n = _normals_api1(mesh, space)
    else:
        if space is None:
            space = om.MSpace.kObject
        n = np.asarray(mesh.getVertexNormals(False, space))[:, :3].astype(np.float64)
    # Defensive renormalize (Maya returns unit normals, but guard zeros).
    mag = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(mag > 1e-12, mag, 1.0)


def extract_region(mesh, face_ids, space=None, with_normals=False):
    """Build a compact polygon buffer for the faces in ``face_ids`` from a
    live ``MFnMesh``.

    Returns ``(points, indices, counts)`` -- or, when ``with_normals`` is
    True, ``(points, indices, counts, normals)`` where ``normals`` are the
    unit per-vertex normals aligned with ``points`` (handy for offsetting
    the region off the surface).

    The region's vertices are compacted + remapped, so ``indices`` refer
    only to the returned ``points``. The result drops straight into
    ``self.polygons``.

    Fully vectorized -- no per-face loops, so a large region on a deforming
    mesh stays cheap.
    """
    def _empty():
        z3 = np.zeros((0, 3), dtype=np.float64)
        zi = np.zeros((0,), dtype=np.int64)
        return (z3, zi, zi.copy(), z3.copy()) if with_normals else (z3, zi, zi.copy())

    if mesh is None:
        return _empty()
    pts, counts, connects = mesh_arrays(mesh, space)
    face_ids = np.asarray(face_ids, dtype=np.int64).ravel()
    if face_ids.size == 0 or counts.shape[0] == 0:
        return _empty()
    # Keep only valid face ids.
    face_ids = face_ids[(face_ids >= 0) & (face_ids < counts.shape[0])]
    if face_ids.size == 0:
        return _empty()

    face_off = np.cumsum(counts) - counts          # start offset into connects/face
    sel_counts = counts[face_ids]                  # (M,)
    starts = face_off[face_ids]                    # (M,)
    total = int(sel_counts.sum())
    if total == 0:
        return _empty()

    # Flatten the selected faces' connectivity positions (vectorized).
    face_of = np.repeat(np.arange(face_ids.size), sel_counts)            # (total,)
    within = np.arange(total) - (np.cumsum(sel_counts) - sel_counts)[face_of]
    connect_pos = starts[face_of] + within                              # (total,)
    region_verts = connects[connect_pos]                                # global vertex ids

    # Compact the used vertices + remap the connectivity to 0..U-1.
    uniq, inverse = np.unique(region_verts, return_inverse=True)
    region_points = pts[uniq]
    region_indices = inverse.astype(np.int64)
    region_counts = sel_counts.astype(np.int64)
    if not with_normals:
        return region_points, region_indices, region_counts
    region_normals = mesh_vertex_normals(mesh, space)[uniq]
    return region_points, region_indices, region_counts, region_normals


def face_centers(mesh, space=None):
    """Return ``(F, 3)`` per-face centroids (vertex average) for an
    ``MFnMesh``. Vectorized -- useful for picking a region by proximity
    (e.g. all faces within a radius of a point)."""
    pts, counts, connects = mesh_arrays(mesh, space)
    if counts.shape[0] == 0:
        return np.zeros((0, 3), dtype=np.float64)
    # Sum each face's vertex positions via add.reduceat, then divide.
    starts = (np.cumsum(counts) - counts).astype(np.int64)
    sums = np.add.reduceat(pts[connects], starts, axis=0)
    return sums / counts[:, None]
