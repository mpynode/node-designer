"""Array_io -- numpy <-> Maya array converters.

introduces numpy as the default interchange currency for
geometry point data. This module collects the small, focused
conversion helpers used by the writable MFn handle wrappers and by
the per-plug type promotion pass.

Public surface (kept tight to keep the import cost low):

 points_array_to_numpy(MPointArray) -> (N, 3) float64
 numpy_to_points_array((N, 3)) -> MPointArray

 float_vector_array_to_numpy(MFloatVectorArray) -> (N, 3) float32
 vector_array_to_numpy(MVectorArray) -> (N, 3) float64

 int_array_to_numpy(MIntArray) -> (N,) int32
 double_array_to_numpy(MDoubleArray) -> (N,) float64
 float_array_to_numpy(MFloatArray) -> (N,) float32

 coerce_to_point_array(value) -> MPointArray
 # Accepts numpy (N, 3) / (N, 4), MPointArray, or list of triples.

The module is API 1.0 only. The few API 2.0 callers (mPyMesh,
mPyLocator) wrap the same data through their own bridge and don't
share the helpers here.
"""

from __future__ import annotations

from typing import Any

import maya.OpenMaya as om
import numpy as np


# ---- Point arrays ----


def points_array_to_numpy(pa):
    """Copy an MPointArray to a fresh (N, 3) float64 numpy array.

    Maya's MPoint is internally 4-wide (x, y, z, w). We slice off
    the w here so callers always get the canonical (N, 3) shape type promotion table (Section 4).
    """
    n = pa.length()
    out = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        p = pa[i]
        out[i, 0] = p.x
        out[i, 1] = p.y
        out[i, 2] = p.z
    return out


def numpy_to_points_array(arr, out=None):
    """Build (or refill) an MPointArray from a (N, 3) or (N, 4) numpy.

    Accepts any 2D array whose second dim is 3 or 4. w defaults
    to 1.0 when not present (matches MPoint defaults).

    when ``out`` is an existing ``MPointArray`` of length
    ``N``, the values are written in place via ``.set(MPoint, i)``
    and ``out`` is returned. This avoids re-allocating the underlying
    buffer on every compute tick for deformer-family nodes that
    push the same vertex count every frame. When ``out`` is None or
    its length doesn't match, a fresh ``MPointArray`` is allocated.
    """
    if arr.ndim!= 2 or arr.shape[1] not in (3, 4):
        raise ValueError(
            "numpy_to_points_array: expected (N, 3) or (N, 4) array, "
            "got shape {!r}".format(arr.shape)
        )
    n = int(arr.shape[0])
    if out is None or not isinstance(out, om.MPointArray) or out.length()!= n:
        pa = om.MPointArray(n)
    else:
        pa = out
    if arr.shape[1] == 4:
        for i in range(n):
            pa.set(
                om.MPoint(
                    float(arr[i, 0]), float(arr[i, 1]),
                    float(arr[i, 2]), float(arr[i, 3]),
                ),
                i,
            )
    else:
        for i in range(n):
            pa.set(
                om.MPoint(
                    float(arr[i, 0]), float(arr[i, 1]), float(arr[i, 2])
                ),
                i,
            )
    return pa


def coerce_to_point_array(value, out=None):
    """Normalize value to an MPointArray.

    Accepts:
      * MPointArray -- returned as-is.
      * (N, 3) or (N, 4) numpy array -- vectorized convert (may
        reuse ``out`` when its length matches).
      * Iterable of (x, y, z) triples -- per-element fallback.

    Raises ValueError for anything else.
    """
    if isinstance(value, om.MPointArray):
        return value
    if isinstance(value, np.ndarray):
        return numpy_to_points_array(value, out=out)
    pa = om.MPointArray()
    for v in value:
        try:
            x, y, z = float(v[0]), float(v[1]), float(v[2])
        except Exception as exc:
            raise ValueError(
                "coerce_to_point_array: element {!r} is not a 3-tuple "
                "({})".format(v, exc)
            )
        pa.append(om.MPoint(x, y, z))
    return pa


# ---- Vector + float arrays ----


def float_vector_array_to_numpy(va):
    """Copy an MFloatVectorArray to (N, 3) float32."""
    n = va.length()
    out = np.empty((n, 3), dtype=np.float32)
    for i in range(n):
        v = va[i]
        out[i, 0] = v.x
        out[i, 1] = v.y
        out[i, 2] = v.z
    return out


def vector_array_to_numpy(va):
    """Copy an MVectorArray to (N, 3) float64."""
    n = va.length()
    out = np.empty((n, 3), dtype=np.float64)
    for i in range(n):
        v = va[i]
        out[i, 0] = v.x
        out[i, 1] = v.y
        out[i, 2] = v.z
    return out


def int_array_to_numpy(ia):
    """Copy an MIntArray to (N,) int32."""
    n = ia.length()
    out = np.empty(n, dtype=np.int32)
    for i in range(n):
        out[i] = ia[i]
    return out


def double_array_to_numpy(da):
    """Copy an MDoubleArray to (N,) float64."""
    n = da.length()
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        out[i] = da[i]
    return out


def float_array_to_numpy(fa):
    """Copy an MFloatArray to (N,) float32."""
    n = fa.length()
    out = np.empty(n, dtype=np.float32)
    for i in range(n):
        out[i] = fa[i]
    return out
