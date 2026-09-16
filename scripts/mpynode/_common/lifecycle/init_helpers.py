"""Init_helpers -- opt-in conversion utilities for the Init tab.

locked the user-facing ``self.X`` contract:

 Numerical plug -> numpy (scalar / 1D / (N, 3))
 Non-numerical plug -> native Maya API object
 (MFnMesh, MatrixView, str, etc.)

That means when the user reads e.g. ``self.input[0].inputGeometry``
they get an ``MFnMesh`` directly, and when they read ``self.worldMatrix[0]``
they get an ``MatrixView``. These ARE native Maya
types -- the user can call the standard MFn / MTransformationMatrix
accessors on them. But the common case is "convert to numpy once,
then do the real math against numpy buffers".

This module ships the small set of converters that wraps the most
common conversions in a one-liner, so user expressions in the Init
tab can do::

 from mpynode._common.lifecycle import init_helpers as ih

 self.cage = ih.mfnmesh_to_numpy_points(self.input[0].inputGeometry)
 self.basis_inv = np.linalg.inv(ih.mtm_to_numpy(self.baseLatticeMatrix))

instead of writing the conversion loop by hand.

Nothing in this module is mandatory. Wrappers stop pre-caching
plug reads; the Init tab uses these helpers when the
numpy form is the natural one.

Public surface::

 mtm_to_numpy(mtm) -> (4, 4) float64
 mtm_translation_numpy(mtm) -> (3,) float64
 mtm_rotation_numpy(mtm) -> (3,) float64 (radians)
 mtm_scale_numpy(mtm) -> (3,) float64
 mfnmesh_to_numpy_points(fn_mesh) -> (N, 3) float64
 mfncurve_to_numpy_cvs(fn_curve) -> (N, 3) float64
 mfnsurface_to_numpy_cvs(fn_srf) -> ((U*V, 3), (U, V))
 mfnlattice_to_numpy_points(fn_lat) -> (S*T*U, 3) float64
 (None when HAS_LATTICE_DATA is False)
 joint_chain_walk(handle) -> list[MFnIkJoint]
 (best-effort; empty list on failure)

Re-export::

 MatrixView (so user code can isinstance-check
 without knowing which submodule it lives in).
"""

from __future__ import annotations

import numpy as np

from mpynode._common.plugs import array_convert as array_io
from mpynode._common.plugs.promoted_types import (
    MatrixView,
)


__all__ = [
    "MatrixView",
    "mtm_to_numpy",
    "mtm_translation_numpy",
    "mtm_rotation_numpy",
    "mtm_scale_numpy",
    "mfnmesh_to_numpy_points",
    "mfncurve_to_numpy_cvs",
    "mfnsurface_to_numpy_cvs",
    "mfnlattice_to_numpy_points",
    "joint_chain_walk",
]


# ---- Matrix helpers ----


def mtm_to_numpy(mtm):
    """Convert an MatrixView (or anything matrix-like)
    to a fresh ``(4, 4) float64`` numpy.

    Accepts ``MatrixView``, ``MMatrix``,
    ``MTransformationMatrix``, ``(4, 4)`` numpy, or a list of 16 floats.
    Returns an independent copy; the caller owns it.
    """
    if mtm is None:
        return np.eye(4, dtype=np.float64)
    if isinstance(mtm, MatrixView):
        return mtm.asNumpy()
    # Wrap and convert.
    return MatrixView(mtm).asNumpy()


def mtm_translation_numpy(mtm):
    """Return the translation component of ``mtm`` as a ``(3,)`` numpy.

    Equivalent to ``mtm.translation()`` then unpacking to numpy --
    saves the user a 3-line conversion.
    """
    if not isinstance(mtm, MatrixView):
        mtm = MatrixView(mtm)
    return np.asarray(mtm.translation(), dtype=np.float64)


def mtm_rotation_numpy(mtm):
    """Return the Euler rotation (radians) of ``mtm`` as a ``(3,)`` numpy.

    Order is taken from the underlying ``MEulerRotation.order``; if the
    user needs a specific rotation order, reorder before/after.
    """
    if not isinstance(mtm, MatrixView):
        mtm = MatrixView(mtm)
    return np.asarray(mtm.rotation(), dtype=np.float64)


def mtm_scale_numpy(mtm):
    """Return the scale component of ``mtm`` as a ``(3,)`` numpy."""
    if not isinstance(mtm, MatrixView):
        mtm = MatrixView(mtm)
    sx, sy, sz = mtm.scale()
    return np.array([sx, sy, sz], dtype=np.float64)


# ---- Mesh / curve / surface helpers ----


def mfnmesh_to_numpy_points(fn_mesh):
    """Read mesh points as ``(N, 3) float64`` numpy.

    Works on:
      * the read-only ``MFnMesh`` returned by an input geometry plug
        (API 1.0 ``getPoints(MPointArray, MSpace)`` out-arg style),
      * the writable ``MFnMeshHandle`` returned by an output geometry
        plug (``getPoints()`` already returns numpy),
      * a raw ``MFnMesh`` from API 2.0 that returns an MPointArray.
    """
    if fn_mesh is None:
        return np.empty((0, 3), dtype=np.float64)
    import maya.OpenMaya as om

    pts = None
    # Try API 2.0 / Phase-F-handle style first: 0-arg or 1-arg call
    # that returns either a numpy array (MFnMeshHandle) or an
    # MPointArray (raw API 2.0).
    try:
        pts = fn_mesh.getPoints(om.MSpace.kObject)
    except TypeError:
        try:
            pa = om.MPointArray()
            fn_mesh.getPoints(pa, om.MSpace.kObject)
            pts = pa
        except Exception:
            return np.empty((0, 3), dtype=np.float64)
    except Exception:
        return np.empty((0, 3), dtype=np.float64)
    if pts is None:
        return np.empty((0, 3), dtype=np.float64)
    # MFnMeshHandle.setPoints accepts numpy directly; getPoints may
    # already have returned one.
    if isinstance(pts, np.ndarray):
        return pts
    return array_io.points_array_to_numpy(pts)


def mfncurve_to_numpy_cvs(fn_curve):
    """Read CV positions from an MFnNurbsCurve, return ``(N, 3)`` numpy."""
    if fn_curve is None:
        return np.empty((0, 3), dtype=np.float64)
    # API 1.0 MFnNurbsCurve exposes ``getCVs(MPointArray, MSpace.kObject)``.
    import maya.OpenMaya as om

    pa = om.MPointArray()
    try:
        fn_curve.getCVs(pa, om.MSpace.kObject)
    except Exception:
        # API 2.0 path: ``cvPositions(MSpace.kObject)`` returns an MPointArray.
        try:
            pa = fn_curve.cvPositions(om.MSpace.kObject)
        except Exception:
            return np.empty((0, 3), dtype=np.float64)
    return array_io.points_array_to_numpy(pa)


def mfnsurface_to_numpy_cvs(fn_surface):
    """Read CV positions from an MFnNurbsSurface.

    Returns a tuple ``(numpy_array, (num_u, num_v))`` where the array
    is row-major ``(num_u * num_v, 3)`` with u-fastest (matches the
    mPyNurbsSurface ``compute_locals`` convention).
    """
    if fn_surface is None:
        return np.empty((0, 3), dtype=np.float64), (0, 0)
    import maya.OpenMaya as om

    pa = om.MPointArray()
    try:
        fn_surface.getCVs(pa, om.MSpace.kObject)
    except Exception:
        try:
            pa = fn_surface.cvPositions(om.MSpace.kObject)
        except Exception:
            return np.empty((0, 3), dtype=np.float64), (0, 0)
    try:
        num_u = int(fn_surface.numCVsInU())
        num_v = int(fn_surface.numCVsInV())
    except Exception:
        num_u, num_v = 0, 0
    return array_io.points_array_to_numpy(pa), (num_u, num_v)


def mfnlattice_to_numpy_points(fn_lattice):
    """Read lattice points from an MFnLattice.

    Returns ``(S*T*U, 3) float64`` numpy in row-major order
    (s-fastest, then t, then u). Returns ``None`` when MFnLattice is
    not available in the current Maya distribution (see the
    HAS_LATTICE_DATA probe in ``_api2/lattice_node.py``).
    """
    if fn_lattice is None:
        return None
    # MFnLattice is loaded conditionally; if the import fails the user
    # gets ``None`` and can branch on it.
    try:
        import maya.OpenMayaAnim as oma  # noqa: F401
    except Exception:
        return None
    try:
        s_div = int(fn_lattice.getSDivisionCount())
        t_div = int(fn_lattice.getTDivisionCount())
        u_div = int(fn_lattice.getUDivisionCount())
    except Exception:
        return None
    n = s_div * t_div * u_div
    if n <= 0:
        return np.empty((0, 3), dtype=np.float64)
    out = np.empty((n, 3), dtype=np.float64)
    idx = 0
    try:
        for u in range(u_div):
            for t in range(t_div):
                for s in range(s_div):
                    p           = fn_lattice.point(s, t, u)
                    out[idx, 0] = p.x
                    out[idx, 1] = p.y
                    out[idx, 2] = p.z
                    idx += 1
    except Exception:
        return None
    return out


# ---- IK helpers ----


def joint_chain_walk(handle):
    """Best-effort walk of an IK handle's joint chain.

    Accepts an ``MFnIkHandle`` (or an ``MObject`` that one can be built
    from). Returns a list of ``MFnIkJoint`` instances ordered from
    start joint to end effector parent. Returns an empty list on
    failure -- the user expression should branch on len() == 0.

    Used by mPyIkSolver Init code that wants the live joint chain as
    native MFnIkJoint instances rather than the curated joint
    dictionaries fed by ``compute_locals["joints"]``.
    """
    try:
        import maya.OpenMaya as om
        import maya.OpenMayaAnim as oma
    except Exception:
        return []
    fn_handle = None
    try:
        if isinstance(handle, oma.MFnIkHandle):
            fn_handle = handle
        else:
            fn_handle = oma.MFnIkHandle(handle)
    except Exception:
        return []
    try:
        start_path = om.MDagPath()
        fn_handle.getStartJoint(start_path)
    except Exception:
        return []
    chain = []
    try:
        current_path = om.MDagPath(start_path)
        while True:
            joint_obj = current_path.node()
            try:
                chain.append(oma.MFnIkJoint(joint_obj))
            except Exception:
                break
            # Walk to first joint child.
            child_count = current_path.childCount()
            next_path   = None
            for i in range(child_count):
                child_obj = current_path.child(i)
                if child_obj.hasFn(om.MFn.kJoint):
                    nxt = om.MDagPath(current_path)
                    nxt.push(child_obj)
                    next_path = nxt
                    break
            if next_path is None:
                break
            current_path = next_path
    except Exception:
        pass
    return chain
