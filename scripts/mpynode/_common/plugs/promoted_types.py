"""Promoted_types -- type-promotion helpers for plug reads.

A few non-obvious return types
that need a tiny class wrapper so the user gets sensible methods:

 * kMatrix -> MTransformationMatrix wrapper with.asMatrix()
 +.asNumpy() (a 4x4 float64 numpy view).
 * kTime -> float subclass whose value is the current FRAME and
 which carries the scene fps (.fps,.asSeconds(),
 .asFrame()).
 * kEnum -> int subclass exposing.name() (looks up the
 field name from the attribute's enum table).

Everything else in the table maps to a plain Python / numpy type
and lives directly in the plug_proxy reader.
"""

from __future__ import annotations

import maya.OpenMaya as om
import maya.api.OpenMaya as om2
import numpy as np


# ---- Euler-order helpers (shared by the single + array matrix views) ----
#
# Maya's rotate-order indices (matches the ``rotateOrder`` enum and
# ``MEulerRotation`` constants): 0=xyz 1=yzx 2=zxy 3=xzy 4=yxz 5=zyx.
_EULER_ORDERS = (
    om.MEulerRotation.kXYZ,
    om.MEulerRotation.kYZX,
    om.MEulerRotation.kZXY,
    om.MEulerRotation.kXZY,
    om.MEulerRotation.kYXZ,
    om.MEulerRotation.kZYX,
)


def _euler_order(idx) -> int:
    """Map a Maya rotate-order index (0..5) to an ``MEulerRotation``
    constant. Out-of-range / bad values fall back to XYZ (0)."""
    try:
        return _EULER_ORDERS[int(idx)]
    except Exception:
        return _EULER_ORDERS[0]


def _euler_from_mmatrix(mmatrix, order_idx=0) -> np.ndarray:
    """Decompose an ``MMatrix`` into an euler ``(3,)`` (radians) in the
    requested Maya rotate-order index (default XYZ)."""
    tm = om.MTransformationMatrix(mmatrix)
    e  = tm.eulerRotation()  # kXYZ representation
    try:
        e.reorderIt(_euler_order(order_idx))
    except Exception:
        pass
    return np.array([e.x, e.y, e.z], dtype=np.float64)


# api2 mirror of ``_EULER_ORDERS`` (used by the api2-backed ``MatrixView``).
_EULER_ORDERS2 = (
    om2.MEulerRotation.kXYZ,
    om2.MEulerRotation.kYZX,
    om2.MEulerRotation.kZXY,
    om2.MEulerRotation.kXZY,
    om2.MEulerRotation.kYXZ,
    om2.MEulerRotation.kZYX,
)


def _euler_order2(idx) -> int:
    """api2 analog of :func:`_euler_order`."""
    try:
        return _EULER_ORDERS2[int(idx)]
    except Exception:
        return _EULER_ORDERS2[0]


def _normalize_axes(axes, n: int) -> np.ndarray:
    """Normalize an ``axes`` argument into an ``(n,)`` int array of
    rotate-order indices. A scalar broadcasts to all ``n``; an iterable
    is used per-element and PADDED with 0 (XYZ) when shorter than ``n``
    (and truncated when longer)."""
    if np.isscalar(axes):
        return np.full((n,), int(axes), dtype=np.int64)
    arr = np.asarray(list(axes), dtype=np.int64).ravel()
    if arr.shape[0] < n:
        arr = np.concatenate([arr, np.zeros((n - arr.shape[0],), dtype=np.int64)])
    return arr[:n]


# ---- Matrix wrapper ----


class MatrixView(object):
    """KMatrix return type. Wraps an api2 ``MMatrix`` (+ a parallel
    ``MTransformationMatrix``) and exposes the full ``MMatrix`` +
    ``MTransformationMatrix`` method surface.

    Return conventions:
      * numerical results are numpy -- ``(N,)`` arrays for vectors, a fresh
        ``(4, 4)`` array via :meth:`asNumpy`, and numpy scalars for
        ``det*`` / ``getElement``.
      * matrix-valued results (``inverse`` / ``transpose`` / ``adjoint`` /
        ``homogenize``) return a NEW ``MatrixView`` so calls chain, e.g.
        ``m.inverse().translation()``.
      * mutators (``setElement`` / ``setToIdentity`` / ``setToProduct`` /
        ``setTranslation`` / ``setScale`` / ...) act IN PLACE and return
        ``self`` for chaining.

    The constructor accepts an api1 ``MMatrix`` (so the api1 plug-read path
    and :class:`MatrixArrayView` keep working), an api2 ``MMatrix``, an
    api1/api2 ``MTransformationMatrix``, a ``(4, 4)`` numpy array, a 16-float
    or 4x4-nested list, another ``MatrixView``, or ``None`` (identity).
    """

    def __init__(self, matrix=None):
        self._m  = self._to_mmatrix(matrix)
        self._tm = om2.MTransformationMatrix(self._m)

    # ---- Coercion helpers ----

    @staticmethod
    def _flatten(value):
        if isinstance(value, np.ndarray) and value.shape == (4, 4):
            return [float(v) for v in value.flatten()]
        try:
            flat = list(value)
            if len(flat) == 16:
                return [float(v) for v in flat]
            if len(flat) == 4 and all(len(row) == 4 for row in flat):
                return [float(flat[i][j]) for i in range(4) for j in range(4)]
        except Exception:
            pass
        return None

    @classmethod
    def _to_mmatrix(cls, value):
        """Coerce anything matrix-like into an OWNED api2 ``MMatrix``."""
        if value is None:
            return om2.MMatrix()
        if isinstance(value, MatrixView):
            return om2.MMatrix(value._m)
        if isinstance(value, om2.MMatrix):
            return om2.MMatrix(value)
        if isinstance(value, om2.MTransformationMatrix):
            return value.asMatrix()
        # api1 MMatrix / MTransformationMatrix -- read 16 elements via the
        # api1 ``operator()`` accessor and rebuild as an api2 matrix.
        if isinstance(value, om.MMatrix):
            return om2.MMatrix([value(i, j) for i in range(4) for j in range(4)])
        if isinstance(value, om.MTransformationMatrix):
            mm = value.asMatrix()
            return om2.MMatrix([mm(i, j) for i in range(4) for j in range(4)])
        flat = cls._flatten(value)
        if flat is not None:
            return om2.MMatrix(flat)
        return om2.MMatrix()

    @staticmethod
    def _seq3(value):
        """Coerce an MVector / MPoint / array / list into ``[x, y, z]``."""
        if isinstance(value, (om2.MVector, om2.MPoint)):
            return [value.x, value.y, value.z]
        arr = np.asarray(value, dtype=np.float64).ravel()
        return [float(arr[0]), float(arr[1]), float(arr[2])]

    def _sync_from_m(self):
        """Rebuild the transformation matrix after a raw-matrix mutation."""
        self._tm = om2.MTransformationMatrix(self._m)
        return self

    def _sync_from_tm(self):
        """Rebuild the raw matrix after a transformation mutation."""
        self._m = self._tm.asMatrix()
        return self

    # ---- Raw accessors ----

    def asMatrix(self):
        """Return the underlying api2 ``MMatrix`` (4x4)."""
        return self._m

    def asTransformationMatrix(self):
        """Return the underlying api2 ``MTransformationMatrix``."""
        return self._tm

    def asNumpy(self):
        """Return a fresh ``(4, 4) float64`` numpy array."""
        out = np.empty((4, 4), dtype=np.float64)
        for i in range(4):
            for j in range(4):
                out[i, j] = self._m.getElement(i, j)
        return out

    # ---- MMatrix surface: numerical -> numpy, matrix -> MatrixView,
    # mutators -> self ----

    def adjoint(self):
        """Return the adjoint as a new ``MatrixView``."""
        return MatrixView(self._m.adjoint())

    def homogenize(self):
        """Return the homogenized matrix as a new ``MatrixView``."""
        return MatrixView(self._m.homogenize())

    def inverse(self):
        """Return the inverse as a new ``MatrixView``."""
        return MatrixView(self._m.inverse())

    def transpose(self):
        """Return the transpose as a new ``MatrixView``."""
        return MatrixView(self._m.transpose())

    def det3x3(self):
        """Return the upper-left 3x3 determinant as a numpy scalar."""
        return np.float64(self._m.det3x3())

    def det4x4(self):
        """Return the 4x4 determinant as a numpy scalar."""
        return np.float64(self._m.det4x4())

    def getElement(self, row, col):
        """Return element ``(row, col)`` as a numpy scalar."""
        return np.float64(self._m.getElement(int(row), int(col)))

    def isSingular(self):
        """Return ``True`` if the matrix is singular."""
        return bool(self._m.isSingular())

    def isEquivalent(self, other, tolerance=None):
        """Return ``True`` if ``other`` is within ``tolerance`` of self."""
        if tolerance is None:
            tolerance = om2.MMatrix.kTolerance
        return bool(self._m.isEquivalent(self._to_mmatrix(other), tolerance))

    def setElement(self, row, col, value):
        """Set element ``(row, col)`` in place; return self."""
        self._m.setElement(int(row), int(col), float(value))
        return self._sync_from_m()

    def setToIdentity(self):
        """Reset to identity in place; return self."""
        self._m.setToIdentity()
        return self._sync_from_m()

    def setToProduct(self, left, right):
        """Set self to ``left * right`` in place; return self."""
        self._m.setToProduct(self._to_mmatrix(left), self._to_mmatrix(right))
        return self._sync_from_m()

    # ---- MTransformationMatrix surface (numerical -> numpy, mutators -> self) ----

    def translation(self, space=None):
        """Return the translation as a ``(3,)`` float64 numpy array."""
        if space is None:
            space = om2.MSpace.kTransform
        v = self._tm.translation(space)
        return np.array([v.x, v.y, v.z], dtype=np.float64)

    def setTranslation(self, value, space=None):
        """Set the translation in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        x, y, z = self._seq3(value)
        self._tm.setTranslation(om2.MVector(x, y, z), space)
        return self._sync_from_tm()

    def translateBy(self, value, space=None):
        """Translate by ``value`` in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        x, y, z = self._seq3(value)
        self._tm.translateBy(om2.MVector(x, y, z), space)
        return self._sync_from_tm()

    def rotation(self, axes=0):
        """Return the euler rotation as a ``(3,)`` float64 numpy array
        (radians), in the given Maya rotate-order index (``axes``):
        0=xyz 1=yzx 2=zxy 3=xzy 4=yxz 5=zyx (default XYZ)."""
        e = self._tm.rotation()
        try:
            e.reorderIt(_euler_order2(axes))
        except Exception:
            pass
        return np.array([e.x, e.y, e.z], dtype=np.float64)

    def setRotation(self, value, axes=0):
        """Set the euler rotation (radians, rotate-order ``axes``) in place;
        return self."""
        x, y, z = self._seq3(value)
        self._tm.setRotation(om2.MEulerRotation(x, y, z, _euler_order2(axes)))
        return self._sync_from_tm()

    def rotateBy(self, value, axes=0, space=None):
        """Rotate by an euler (radians, rotate-order ``axes``) in place;
        return self."""
        if space is None:
            space = om2.MSpace.kTransform
        x, y, z = self._seq3(value)
        self._tm.rotateBy(om2.MEulerRotation(x, y, z, _euler_order2(axes)), space)
        return self._sync_from_tm()

    def reorderRotation(self, axes):
        """Reorder the rotation to rotate-order ``axes`` in place; return self."""
        self._tm.reorderRotation(_euler_order2(axes))
        return self._sync_from_tm()

    def rotationOrder(self):
        """Return the rotation order as a plain int (Maya rotate-order index)."""
        return int(self._tm.rotationOrder())

    def scale(self, space=None):
        """Return the scale as a ``(3,)`` float64 numpy array."""
        if space is None:
            space = om2.MSpace.kTransform
        return np.array(self._tm.scale(space), dtype=np.float64)

    def setScale(self, value, space=None):
        """Set the scale in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        self._tm.setScale(self._seq3(value), space)
        return self._sync_from_tm()

    def scaleBy(self, value, space=None):
        """Scale by ``value`` in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        self._tm.scaleBy(self._seq3(value), space)
        return self._sync_from_tm()

    def shear(self, space=None):
        """Return the shear as a ``(3,)`` float64 numpy array."""
        if space is None:
            space = om2.MSpace.kTransform
        return np.array(self._tm.shear(space), dtype=np.float64)

    def setShear(self, value, space=None):
        """Set the shear in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        self._tm.setShear(self._seq3(value), space)
        return self._sync_from_tm()

    def shearBy(self, value, space=None):
        """Shear by ``value`` in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        self._tm.shearBy(self._seq3(value), space)
        return self._sync_from_tm()

    def rotatePivot(self, space=None):
        """Return the rotate pivot as a ``(3,)`` float64 numpy array."""
        if space is None:
            space = om2.MSpace.kTransform
        p = self._tm.rotatePivot(space)
        return np.array([p.x, p.y, p.z], dtype=np.float64)

    def setRotatePivot(self, value, space=None, balance=True):
        """Set the rotate pivot in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        x, y, z = self._seq3(value)
        self._tm.setRotatePivot(om2.MPoint(x, y, z), space, balance)
        return self._sync_from_tm()

    def rotatePivotTranslation(self, space=None):
        """Return the rotate-pivot translation as a ``(3,)`` numpy array."""
        if space is None:
            space = om2.MSpace.kTransform
        v = self._tm.rotatePivotTranslation(space)
        return np.array([v.x, v.y, v.z], dtype=np.float64)

    def setRotatePivotTranslation(self, value, space=None):
        """Set the rotate-pivot translation in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        x, y, z = self._seq3(value)
        self._tm.setRotatePivotTranslation(om2.MVector(x, y, z), space)
        return self._sync_from_tm()

    def scalePivot(self, space=None):
        """Return the scale pivot as a ``(3,)`` float64 numpy array."""
        if space is None:
            space = om2.MSpace.kTransform
        p = self._tm.scalePivot(space)
        return np.array([p.x, p.y, p.z], dtype=np.float64)

    def setScalePivot(self, value, space=None, balance=True):
        """Set the scale pivot in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        x, y, z = self._seq3(value)
        self._tm.setScalePivot(om2.MPoint(x, y, z), space, balance)
        return self._sync_from_tm()

    def scalePivotTranslation(self, space=None):
        """Return the scale-pivot translation as a ``(3,)`` numpy array."""
        if space is None:
            space = om2.MSpace.kTransform
        v = self._tm.scalePivotTranslation(space)
        return np.array([v.x, v.y, v.z], dtype=np.float64)

    def setScalePivotTranslation(self, value, space=None):
        """Set the scale-pivot translation in place; return self."""
        if space is None:
            space = om2.MSpace.kTransform
        x, y, z = self._seq3(value)
        self._tm.setScalePivotTranslation(om2.MVector(x, y, z), space)
        return self._sync_from_tm()

    def asMatrixInverse(self):
        """Return the inverse matrix (raw api2 ``MMatrix``)."""
        return self._tm.asMatrixInverse()

    def asRotateMatrix(self):
        """Return the rotate-only matrix (raw api2 ``MMatrix``)."""
        return self._tm.asRotateMatrix()

    def asScaleMatrix(self):
        """Return the scale-only matrix (raw api2 ``MMatrix``)."""
        return self._tm.asScaleMatrix()

    # ---- Numpy transparency: ``np.asarray(M)`` -> (4, 4); indexing / .shape /
    # .copy() behave like the ndarray and ``@`` does matrix math. Keeps user code
    # that treats a matrix plug as a numpy array working unchanged. ----

    @property
    def shape(self):
        return (4, 4)

    def __array__(self, dtype=None):
        arr = self.asNumpy()
        return arr.astype(dtype) if dtype is not None else arr

    def __getitem__(self, idx):
        return self.asNumpy()[idx]

    def copy(self):
        return self.asNumpy().copy()

    def __reduce__(self):
        # Pickle as the (4, 4) numpy array (the underlying ``MMatrix``
        # isn't picklable). Reconstructs a numpy-backed ``MatrixView`` --
        # so e.g. the Watch-tab snapshot keeps the real type instead of
        # falling back to ``repr()``.
        return (MatrixView, (self.asNumpy(),))

    def __matmul__(self, other):
        return self.asNumpy() @ np.asarray(other)

    def __rmatmul__(self, other):
        return np.asarray(other) @ self.asNumpy()

    # ---- Operators for ergonomic chaining (MMatrix-level, keep view type) ----

    def __mul__(self, other):
        if isinstance(other, MatrixView):
            return MatrixView(self._m * other._m)
        if isinstance(other, (om2.MMatrix, om.MMatrix)):
            return MatrixView(self._m * self._to_mmatrix(other))
        return NotImplemented

    def __rmul__(self, other):
        if isinstance(other, (om2.MMatrix, om.MMatrix)):
            return MatrixView(self._to_mmatrix(other) * self._m)
        return NotImplemented

    def __repr__(self):
        try:
            t = self.translation()
            return (
                "<MatrixView translate=({:.3f}, {:.3f}, "
                "{:.3f})>".format(t[0], t[1], t[2])
            )
        except Exception:
            return "<MatrixView>"


# ---- Matrix-array view (array of transforms) ----


class MatrixArrayView(object):
    """Return type for a *matrix array* plug -- the SINGLE type both API
    layers hand back for a multi matrix. It offers BOTH access styles:

      * structure-of-arrays (vectorized): ``M.translation()`` -> ``(N,3)``,
        ``M.rotation(axes=...)`` -> ``(N,3)``, ``M.scale()`` / ``M.shear()``.
      * array-of-structs (per element): ``M[i]`` (plain int) -> a single
        ``MatrixView`` (with ``.translation()`` etc.).

    It is numpy-transparent: ``np.asarray(M)`` -> ``(N,4,4)``, ``M @ X`` does
    batched matrix math, ``M.shape`` / slicing / fancy-index behave like
    the underlying ndarray (only a *plain int* index returns the
    per-element view; a non-int/non-slice index raises ``TypeError``).

    Dual-backed so one class serves both layers WITHOUT a perf cost:

      * api2 (eager): constructed from an ``(N, 4, 4)`` numpy array that
        the datablock reader already produced.
      * api1 (lazy): constructed from a *plug provider* (supplied by
        ``plug_proxy``) that resolves elements on demand. This keeps the
        ``worldMatrix[0]`` idiom working (an output multi resolves element
        0 even with no allocated elements yet) and avoids reading a big
        multi in full unless the vectorized form is actually requested.
        The provider duck-types ``count()`` / ``get_matrix(i)`` /
        ``set_matrix(i, v)`` / ``stack() -> (N,4,4)``.

    The hot paths are identical either way: ``M[i]`` resolves/copies one
    matrix; the vectorized accessors stack once.
    """

    def __init__(self, source):
        # A plug provider (api1, lazy) vs. a raw (N,4,4) array (api2).
        if hasattr(source, "get_matrix") and hasattr(source, "stack"):
            self._provider = source
            self._a        = None
        else:
            arr = np.asarray(source, dtype=np.float64)
            if arr.size == 0:
                arr = np.zeros((0, 4, 4), dtype=np.float64)
            else:
                arr = arr.reshape(-1, 4, 4)
            self._a        = arr
            self._provider = None

    # -- backing -------------------------------------------------------
    def asNumpy(self):
        """Return the matrices as a single ``(N, 4, 4)`` float64 array
        (eager copy if this view is plug-backed)."""
        return self._a if self._provider is None else self._provider.stack()

    def __reduce__(self):
        # Pickle as the eager ``(N, 4, 4)`` array -- this resolves a lazy
        # plug-backed view (whose ``_MatrixPlugProvider`` holds an
        # unpicklable live MPlug) and reconstructs an eager view. Keeps
        # the real type in the Watch-tab snapshot instead of repr() str.
        return (MatrixArrayView, (self.asNumpy(),))

    def _row_view(self, row):
        mm = om.MMatrix()
        om.MScriptUtil.createMatrixFromList([float(v) for v in row.ravel()], mm)
        return MatrixView(mm)

    # -- numpy transparency --------------------------------------------
    @property
    def shape(self):
        return self._a.shape if self._a is not None else self.asNumpy().shape

    def __len__(self):
        return self._provider.count() if self._provider is not None else self._a.shape[0]

    def __array__(self, dtype=None):
        a = self.asNumpy()
        return a.astype(dtype) if dtype is not None else a

    def __matmul__(self, other):
        return self.asNumpy() @ np.asarray(other)

    def __rmatmul__(self, other):
        return np.asarray(other) @ self.asNumpy()

    def __getitem__(self, idx):
        # Plain int -> a single MatrixView (array-of-structs, lazy when
        # plug-backed); slice / tuple / array -> raw numpy view; anything
        # else (e.g. a string) -> TypeError (matches the prior multi-plug
        # contract).
        if isinstance(idx, (int, np.integer)):
            if self._provider is not None:
                return self._provider.get_matrix(int(idx))
            return self._row_view(self._a[idx])
        if isinstance(idx, (slice, tuple, list, np.ndarray)):
            return self.asNumpy()[idx]
        raise TypeError(
            "matrix array indices must be int or slice, got %s"
            % type(idx).__name__
        )

    def __setitem__(self, idx, value):
        if self._provider is not None:
            self._provider.set_matrix(int(idx), value)
        else:
            self._a[idx] = np.asarray(value, dtype=np.float64)

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    # -- structure-of-arrays decompose (vectorized) --------------------
    def translation(self):
        """``(N, 3)`` translations (row 3 of each matrix)."""
        a = self.asNumpy()
        if a.shape[0] == 0:
            return np.zeros((0, 3), dtype=np.float64)
        return a[:, 3, :3].copy()

    def rotation(self, axes=0):
        """``(N, 3)`` euler rotations (radians) per matrix.

        ``axes`` is a Maya rotate-order index (0=xyz..5=zyx). A scalar
        applies to all; an iterable applies per-element and is padded
        with 0 (XYZ) when shorter than ``N``.
        """
        a = self.asNumpy()
        n = a.shape[0]
        if n == 0:
            return np.zeros((0, 3), dtype=np.float64)
        orders = _normalize_axes(axes, n)
        out    = np.empty((n, 3), dtype=np.float64)
        for i in range(n):
            mm = om.MMatrix()
            om.MScriptUtil.createMatrixFromList(
                [float(v) for v in a[i].ravel()], mm
            )
            out[i] = _euler_from_mmatrix(mm, int(orders[i]))
        return out

    def scale(self):
        """``(N, 3)`` scales per matrix."""
        a   = self.asNumpy()
        out = np.empty((a.shape[0], 3), dtype=np.float64)
        for i in range(a.shape[0]):
            out[i] = self._row_view(a[i]).scale()
        return out

    def shear(self):
        """``(N, 3)`` shears per matrix."""
        a   = self.asNumpy()
        out = np.empty((a.shape[0], 3), dtype=np.float64)
        for i in range(a.shape[0]):
            out[i] = self._row_view(a[i]).shear()
        return out

    def __repr__(self):
        try:
            n = len(self)
        except Exception:
            n = "?"
        mode = "lazy" if self._provider is not None else "eager"
        return "<MatrixArrayView (N={}, 4, 4) {}>".format(n, mode)


# ---- Time + Enum sub-classed scalars ----


class TimeFloat(float):
    """Scene-time return type for kTime plugs and built-in ``self.time``.

    A ``float`` whose value is the current **frame** (scene time in the
    current UI time unit). It also carries the scene frame rate, so the
    user can ask for other flavors without a separate ``self.fps``:

      * ``float(t)`` / arithmetic -> frame number (the default)
      * ``t.fps``                 -> frames per second (current unit)
      * ``t.asSeconds()``         -> seconds (``frame / fps``)
      * ``t.asFrame()``           -> frame number (identity; kept for
                                     symmetry / back-compat)

    ``fps`` is snapshotted at construction so the object stays
    self-consistent for the frame it captured; a scene time-unit change
    yields a fresh ``TimeFloat`` on the next evaluation.
    """

    def __new__(cls, frame_value, fps=None):
        inst = float.__new__(cls, float(frame_value))
        if fps is None:
            from mpynode._common.lifecycle.time_utils import current_fps
            fps = current_fps()
        inst._fps = float(fps)
        return inst

    @property
    def fps(self):
        return self._fps

    def asSeconds(self):
        try:
            return float(self) / self._fps if self._fps else 0.0
        except Exception:
            return float(self)

    def asFrame(self):
        return float(self)


class EnumInt(int):
    """KEnum return type. Plain ``int`` with a ``.name()``
    helper that looks up the named field via the attribute's enum
    table.

    The attribute MObject is captured at construction time so the
    instance can self-describe.
    """

    def __new__(cls, value, attr_mobject=None):
        inst               = int.__new__(cls, int(value))
        inst._attr_mobject = attr_mobject
        return inst

    def name(self):
        attr = getattr(self, "_attr_mobject", None)
        if attr is None or attr.isNull():
            return str(int(self))
        # The stored MObject may be an API1 (``maya.OpenMaya``) OR an API2
        # (``maya.api.OpenMaya``) handle depending on the read path: the plug
        # proxy resolves via API1, while the dense input-seed reader
        # (``_api2.helpers.read_plug_value`` / ``_read_handle_value``) uses
        # API2. ``MFnEnumAttribute`` from one API cleanly rejects the other
        # API's MObject, so try API2 first (the modern dense-seed default),
        # then fall back to API1.
        for _mfn_enum in (om2.MFnEnumAttribute, om.MFnEnumAttribute):
            try:
                return _mfn_enum(attr).fieldName(int(self))
            except Exception:
                continue
        return str(int(self))
