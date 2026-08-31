"""Mfn_handles -- writable MFn* handles returned for output geometry plugs.

introduces the writable ``self.outputGeometry[i]`` surface
described in. The bridge eagerly allocates
a fresh MObject + MFn wrapper at compute start (deep-copied from the
input geometry, see Section 3.1) and the user expression mutates it
in place via the standard MFn API.

For F.0 only ``MFnMeshHandle`` is needed (the spike target is
mPyDeformer). F.2 generalizes to NurbsCurve / NurbsSurface / Lattice.

The handles wrap the underlying ``MFn*`` instance via composition
(``__getattr__`` delegation) rather than subclassing -- many MFn*
methods are SWIG'd C++ slots that don't accept Python overrides
cleanly. The wrapper also adds:

 * Numpy-friendly ``getPoints()`` / ``setPoints()`` that accept and
 return ``(N, 3)`` numpy arrays by default (still accept
 ``MPointArray`` / list-of-triples on input for advanced users).
 * ``_mpyn_mobject`` -- the fresh MObject the handle owns.
 * ``_mpyn_plug_name`` / ``_mpyn_plug_index`` -- plug coordinates.
 * ``_mpyn_touched`` -- defaults False; commit is currently always
 issued (skip-if-untouched is reserved for future use).
"""

from __future__ import annotations

from typing import Any

import maya.OpenMaya as om
import numpy as np

from mpynode._common.plugs.array_convert import (
    coerce_to_point_array,
    points_array_to_numpy,
)


# ---- Mesh ----


class MFnMeshHandle(object):
    """Wrap an ``MFnMesh`` so writes to its points return numpy + flag
    the handle as touched.

    Constructed by ``compute.allocate_output_handles(...)`` and dropped
    into the per-compute ``output_handles`` dict so ``self.outputGeometry[i]``
    can return it directly.
    """

    def __init__(self, mfn_mesh, mobject, plug_name="", plug_index=0):
        # __dict__ writes via object.__setattr__ to avoid recursion --
        # see __setattr__ below for the user-facing forwarding rule.
        object.__setattr__(self, "_mfn", mfn_mesh)
        object.__setattr__(self, "_mpyn_mobject", mobject)
        object.__setattr__(self, "_mpyn_plug_name", plug_name)
        object.__setattr__(self, "_mpyn_plug_index", int(plug_index))
        object.__setattr__(self, "_mpyn_touched", False)

    # ---- Numpy-friendly geometry I/O ----

    def getPoints(self, space=None):
        """Return points as ``(N, 3) float64`` numpy.

        ``space`` accepts the MFnMesh space constants (``om.MSpace.kObject``
        is the default and matches the deformer pipeline's local-space
        convention).
        """
        if space is None:
            space = om.MSpace.kObject
        pa = om.MPointArray()
        self._mfn.getPoints(pa, space)
        return points_array_to_numpy(pa)

    def setPoints(self, value, space=None):
        """Push points to the underlying mesh.

        Accepts:
          * ``(N, 3)`` or ``(N, 4)`` numpy array
          * ``MPointArray``
          * Iterable of ``(x, y, z)`` triples

        the handle caches a single ``MPointArray`` it can
        refill in place when the per-tick vertex count is stable
        (which is the common case for deformer-family nodes). The
        cached buffer is dropped + reallocated automatically when
        the count changes.
        """
        if space is None:
            space = om.MSpace.kObject
        cached = object.__getattribute__(self, "__dict__").get("_mpyn_point_buf")
        pa = coerce_to_point_array(value, out=cached)
        if pa is not cached:
            object.__setattr__(self, "_mpyn_point_buf", pa)
        self._mfn.setPoints(pa, space)
        object.__setattr__(self, "_mpyn_touched", True)

    def setPoint(self, idx, value, space=None):
        """Single-vertex setter -- accepts ``MPoint`` or ``(x, y, z)``."""
        if space is None:
            space = om.MSpace.kObject
        if isinstance(value, om.MPoint):
            self._mfn.setPoint(int(idx), value, space)
        else:
            self._mfn.setPoint(
                int(idx),
                om.MPoint(float(value[0]), float(value[1]), float(value[2])),
                space,
            )
        object.__setattr__(self, "_mpyn_touched", True)

    def numVertices(self):
        return int(self._mfn.numVertices())

    # ---- Unified geometry surface: same names as the api2 ``Mesh`` wrapper, so
    # a deformer expression uses the SAME API as an api2 node. ``points`` is
    # read/write (writes route to in-place ``setPoints`` -> deformer commit);
    # ``counts`` / ``indices`` are read-only, since a deformer can't change
    # topology. Component tags are read off a geometry INPUT (which arrives as
    # the full ``Mesh``) -- the deformed handle shares that topology, so tag
    # indices apply directly. ----

    def _topo(self):
        """Cached ``(counts, indices)`` int64 numpy arrays from the mesh."""
        cached = object.__getattribute__(self, "__dict__").get("_mpyn_topo")
        if cached is None:
            counts = om.MIntArray()
            conn = om.MIntArray()
            self._mfn.getVertices(counts, conn)
            c = np.fromiter((counts[i] for i in range(counts.length())),
                            dtype=np.int64, count=counts.length())
            idx = np.fromiter((conn[i] for i in range(conn.length())),
                              dtype=np.int64, count=conn.length())
            cached = (c, idx)
            object.__setattr__(self, "_mpyn_topo", cached)
        return cached

    @property
    def points(self):
        return self.getPoints()

    @property
    def counts(self):
        return self._topo()[0]

    @property
    def indices(self):
        return self._topo()[1]

    def region(self, tag):
        """Not available on the deformed handle (api1 tag enumeration is
        build-fragile). Read component tags off a geometry INPUT instead --
        it arrives as the full ``Mesh`` wrapper with ``.component_tags`` /
        ``.region()``, and shares this handle's topology so indices apply."""
        return None

    def copy(self):
        """A DETACHED api2 ``Mesh`` value copy of the current deformed state
        (points + topology). Send it to an output / hand it off with the SAME
        API as an api2 node."""
        from mpynode._api2 import geometry as _geo
        c, idx = self._topo()
        return _geo.Mesh(points=self.getPoints(), counts=c, indices=idx)

    # ---- Generic MFn* method delegation ----

    def __getattr__(self, name):
        # Forward to the underlying MFnMesh for anything we don't
        # explicitly override. This keeps the entire MFnMesh surface
        # available (numEdges, getVertexNormals, etc.).
        try:
            return getattr(object.__getattribute__(self, "_mfn"), name)
        except AttributeError:
            raise AttributeError(
                "MFnMeshHandle has no attribute {!r}".format(name)
            )

    def __setattr__(self, name, value):
        # Unified surface: ``self.<mesh>.points = ...`` routes to the in-place
        # setter (deformer commit); topology is read-only.
        if name == "points":
            self.setPoints(value)
            return
        if name in ("counts", "indices"):
            raise AttributeError(
                "{!r} is read-only on a deformer-bound mesh (a deformer cannot "
                "change topology; only positions).".format(name)
            )
        # Internal bookkeeping (object.__setattr__ from __init__) goes
        # through __dict__ before we ever see it. Anything else is a
        # user-side write to a method-style attribute -- forward it
        # to the underlying MFnMesh and let it complain if it's not
        # supported (most MFnMesh methods are not assignable, only
        # callable, so this should be a rare path).
        try:
            setattr(object.__getattribute__(self, "_mfn"), name, value)
        except (AttributeError, TypeError):
            object.__setattr__(self, name, value)

    def __repr__(self):
        try:
            n = self._mfn.numVertices()
        except Exception:
            n = "?"
        return (
            "<MFnMeshHandle plug={!r} index={} verts={} touched={}>".format(
                self._mpyn_plug_name,
                self._mpyn_plug_index,
                n,
                self._mpyn_touched,
            )
        )


# ---- Allocation helpers ----


def allocate_writable_mesh_from_source(src_mobject):
    """Deep-copy a source mesh MObject into a fresh MFnMeshData/MObject.

    Returns ``(handle_mfn_mesh, fresh_mobject)``. The MFnMesh wraps the
    fresh MObject so callers can mutate it safely without aliasing
    the input geometry.
    """
    fresh_data = om.MFnMeshData().create()
    fresh_mfn = om.MFnMesh()
    if src_mobject is not None and not src_mobject.isNull():
        fresh_mfn.copy(src_mobject, fresh_data)
    else:
        # Source unavailable (e.g. no upstream connection yet).
        # Build an empty mesh; the user can populate via.create().
        empty_pts = om.MPointArray()
        empty_cnt = om.MIntArray()
        empty_idx = om.MIntArray()
        fresh_mfn.create(0, 0, empty_pts, empty_cnt, empty_idx, fresh_data)
    return fresh_mfn, fresh_data


def allocate_empty_mesh():
    """Allocate a fresh, empty MFnMesh on a new MObject. For generators
    (mPyMesh) where the user builds topology from scratch."""
    fresh_data = om.MFnMeshData().create()
    fresh_mfn = om.MFnMesh()
    empty_pts = om.MPointArray()
    empty_cnt = om.MIntArray()
    empty_idx = om.MIntArray()
    fresh_mfn.create(0, 0, empty_pts, empty_cnt, empty_idx, fresh_data)
    return fresh_mfn, fresh_data


# ---- NURBS curve handle ----


class MFnNurbsCurveHandle(object):
    """Wrap an ``MFnNurbsCurve`` so writes to its CV positions return
    numpy + flag the handle as touched.
    """

    def __init__(self, mfn_curve, mobject, plug_name="", plug_index=0):
        object.__setattr__(self, "_mfn", mfn_curve)
        object.__setattr__(self, "_mpyn_mobject", mobject)
        object.__setattr__(self, "_mpyn_plug_name", plug_name)
        object.__setattr__(self, "_mpyn_plug_index", int(plug_index))
        object.__setattr__(self, "_mpyn_touched", False)

    def cvPositions(self, space=None):
        """Return CV positions as ``(N, 3) float64`` numpy."""
        if space is None:
            space = om.MSpace.kObject
        pa = om.MPointArray()
        self._mfn.getCVs(pa, space)
        return points_array_to_numpy(pa)

    def setCVPositions(self, value, space=None):
        """Push CVs to the underlying curve. Accepts numpy / MPointArray /
        list of triples."""
        if space is None:
            space = om.MSpace.kObject
        pa = coerce_to_point_array(value)
        self._mfn.setCVs(pa, space)
        # Some MFnNurbsCurve operations require an updateCurve call to
        # rebuild the geometry cache after CV mutation.
        try:
            self._mfn.updateCurve()
        except Exception:
            pass
        object.__setattr__(self, "_mpyn_touched", True)

    def numCVs(self):
        return int(self._mfn.numCVs())

    # Unified surface: ``points`` / ``cvs`` (read = flat (N,3) CV positions;
    # write routes to the in-place setter -> deformer commit).
    @property
    def points(self):
        return self.cvPositions()

    @property
    def cvs(self):
        return self.cvPositions()

    def copy(self):
        """A DETACHED api2 ``NurbsCurve`` value copy (CVs + degree)."""
        from mpynode._api2 import geometry as _geo
        try:
            degree = int(self._mfn.degree())
        except Exception:
            degree = 3
        return _geo.NurbsCurve(points=self.cvPositions(), degree=degree)

    def __getattr__(self, name):
        try:
            return getattr(object.__getattribute__(self, "_mfn"), name)
        except AttributeError:
            raise AttributeError("MFnNurbsCurveHandle has no attribute {!r}".format(name))

    def __setattr__(self, name, value):
        if name in ("points", "cvs"):
            self.setCVPositions(value)
            return
        try:
            setattr(object.__getattribute__(self, "_mfn"), name, value)
        except (AttributeError, TypeError):
            object.__setattr__(self, name, value)

    def __repr__(self):
        try:
            n = self._mfn.numCVs()
        except Exception:
            n = "?"
        return "<MFnNurbsCurveHandle plug={!r} index={} cvs={} touched={}>".format(
            self._mpyn_plug_name, self._mpyn_plug_index, n, self._mpyn_touched,
        )


# ---- NURBS surface handle ----


class MFnNurbsSurfaceHandle(object):
    """Wrap an ``MFnNurbsSurface`` so writes to its CV positions return
    numpy + flag the handle as touched.

    NURBS surfaces are 2D (u, v); ``cvPositions()`` flattens to ``(N, 3)``
    in row-major (u-fastest) order to match the MPointArray returned by
    MFnNurbsSurface.getCVs.
    """

    def __init__(self, mfn_surface, mobject, plug_name="", plug_index=0):
        object.__setattr__(self, "_mfn", mfn_surface)
        object.__setattr__(self, "_mpyn_mobject", mobject)
        object.__setattr__(self, "_mpyn_plug_name", plug_name)
        object.__setattr__(self, "_mpyn_plug_index", int(plug_index))
        object.__setattr__(self, "_mpyn_touched", False)

    def cvPositions(self, space=None):
        if space is None:
            space = om.MSpace.kObject
        pa = om.MPointArray()
        self._mfn.getCVs(pa, space)
        return points_array_to_numpy(pa)

    def setCVPositions(self, value, space=None):
        if space is None:
            space = om.MSpace.kObject
        pa = coerce_to_point_array(value)
        self._mfn.setCVs(pa, space)
        try:
            self._mfn.updateSurface()
        except Exception:
            pass
        object.__setattr__(self, "_mpyn_touched", True)

    def numCVsInU(self):
        return int(self._mfn.numCVsInU())

    def numCVsInV(self):
        return int(self._mfn.numCVsInV())

    # Unified surface: ``points`` / ``cvs`` (read = FLAT (N,3) CV positions in
    # getCVs order; write routes to the in-place setter -> deformer commit). A
    # deformer edits positions in place, so flat is the natural form here (the
    # api2 NurbsSurface INPUT wrapper exposes the structured (nu,nv,3) grid).
    @property
    def points(self):
        return self.cvPositions()

    @property
    def cvs(self):
        return self.cvPositions()

    def copy(self):
        """A DETACHED api2 ``NurbsSurface`` value copy (flat CVs + counts +
        degrees). Uses ``num_u`` / ``num_v`` so the flat CVs re-grid on build."""
        from mpynode._api2 import geometry as _geo
        try:
            nu, nv = int(self._mfn.numCVsInU()), int(self._mfn.numCVsInV())
            du, dv = int(self._mfn.degreeU()), int(self._mfn.degreeV())
        except Exception:
            nu = nv = 0
            du = dv = 3
        return _geo.NurbsSurface(points=self.cvPositions(), num_u=nu, num_v=nv,
                                 degree_u=du, degree_v=dv)

    def __getattr__(self, name):
        try:
            return getattr(object.__getattribute__(self, "_mfn"), name)
        except AttributeError:
            raise AttributeError("MFnNurbsSurfaceHandle has no attribute {!r}".format(name))

    def __setattr__(self, name, value):
        if name in ("points", "cvs"):
            self.setCVPositions(value)
            return
        try:
            setattr(object.__getattribute__(self, "_mfn"), name, value)
        except (AttributeError, TypeError):
            object.__setattr__(self, name, value)

    def __repr__(self):
        try:
            u = self._mfn.numCVsInU()
            v = self._mfn.numCVsInV()
        except Exception:
            u = v = "?"
        return "<MFnNurbsSurfaceHandle plug={!r} index={} cvs={}x{} touched={}>".format(
            self._mpyn_plug_name, self._mpyn_plug_index, u, v, self._mpyn_touched,
        )


# ---- Lattice handle ----


class MFnLatticeHandle(object):
    """Wrap an ``MFnLattice`` so writes to its lattice points return
    numpy + flag the handle as touched.

    Lattice geometry is 3D (s, t, u); the wrapper exposes a flat
    ``getPoints()`` that returns ``(S*T*U, 3)`` and a ``setPoints()``
    that accepts the same shape.
    """

    def __init__(self, mfn_lattice, mobject, plug_name="", plug_index=0):
        object.__setattr__(self, "_mfn", mfn_lattice)
        object.__setattr__(self, "_mpyn_mobject", mobject)
        object.__setattr__(self, "_mpyn_plug_name", plug_name)
        object.__setattr__(self, "_mpyn_plug_index", int(plug_index))
        object.__setattr__(self, "_mpyn_touched", False)

    def getPoints(self):
        """Return all lattice points as ``(S*T*U, 3) float64`` numpy."""
        try:
            s_int = self._mfn.getDivisions()
            # MFnLattice.getDivisions returns 3 ints via ptr; many
            # OpenMaya API revisions expose getDivisions(s, t, u)
            # that takes uint refs. Fall back to MItGeometry-style
            # iteration.
        except Exception:
            pass
        # Use a simple per-point loop -- API 1.0 MFnLattice surface is
        # idiosyncratic across versions.
        # numLatticePoints is N; getPoint(i) returns MPoint.
        try:
            n = int(self._mfn.numLatticePoints())
        except Exception:
            try:
                n = int(self._mfn.numPoints())
            except Exception:
                n = 0
        out = np.empty((n, 3), dtype=np.float64)
        for i in range(n):
            try:
                p = self._mfn.point(i)
            except Exception:
                try:
                    p = self._mfn.getPoint(i)
                except Exception:
                    p = om.MPoint()
            out[i, 0] = p.x
            out[i, 1] = p.y
            out[i, 2] = p.z
        return out

    def setPoints(self, value):
        """Push lattice points back. Accepts ``(N, 3)`` numpy."""
        if isinstance(value, np.ndarray):
            n = int(value.shape[0])
            for i in range(n):
                pt = om.MPoint(
                    float(value[i, 0]),
                    float(value[i, 1]),
                    float(value[i, 2]),
                )
                try:
                    self._mfn.setPoint(i, pt)
                except Exception:
                    pass
        else:
            for i, triple in enumerate(value):
                pt = om.MPoint(float(triple[0]), float(triple[1]), float(triple[2]))
                try:
                    self._mfn.setPoint(i, pt)
                except Exception:
                    pass
        object.__setattr__(self, "_mpyn_touched", True)

    def __getattr__(self, name):
        try:
            return getattr(object.__getattribute__(self, "_mfn"), name)
        except AttributeError:
            raise AttributeError("MFnLatticeHandle has no attribute {!r}".format(name))

    def __setattr__(self, name, value):
        try:
            setattr(object.__getattribute__(self, "_mfn"), name, value)
        except (AttributeError, TypeError):
            object.__setattr__(self, name, value)

    def __repr__(self):
        return "<MFnLatticeHandle plug={!r} index={} touched={}>".format(
            self._mpyn_plug_name, self._mpyn_plug_index, self._mpyn_touched,
        )


# ---- Allocation helpers for non-mesh geometry ----


def allocate_writable_curve_from_source(src_mobject):
    """Deep-copy a source NURBS curve MObject into a fresh
    MFnNurbsCurveData / MObject. Returns ``(MFnNurbsCurve, fresh_mobject)``."""
    fresh_data = om.MFnNurbsCurveData().create()
    fresh_mfn = om.MFnNurbsCurve()
    if src_mobject is not None and not src_mobject.isNull():
        fresh_mfn.copy(src_mobject, fresh_data)
    return fresh_mfn, fresh_data


def allocate_writable_surface_from_source(src_mobject):
    """Deep-copy a source NURBS surface MObject into a fresh
    MFnNurbsSurfaceData / MObject."""
    fresh_data = om.MFnNurbsSurfaceData().create()
    fresh_mfn = om.MFnNurbsSurface()
    if src_mobject is not None and not src_mobject.isNull():
        fresh_mfn.copy(src_mobject, fresh_data)
    return fresh_mfn, fresh_data


def allocate_writable_lattice_from_source(src_mobject):
    """Deep-copy a source Lattice MObject into a fresh
    ``MFnLatticeData`` / MObject if available.

    API 1.0 in some Maya versions ships ``MFnLatticeDeformer`` /
    ``MFnLattice`` only -- not ``MFnLatticeData``. In that case this
    helper returns ``(None, None)`` so the compute path can fall back
    to a no-op handle. The deformer pipeline then routes the input
    lattice through to the output unchanged.
    """
    try:
        import maya.OpenMayaAnim as oma
    except Exception:
        return None, None
    if not hasattr(oma, "MFnLatticeData"):
        return None, None
    fresh_data = oma.MFnLatticeData().create()
    fresh_mfn = oma.MFnLattice()
    if src_mobject is not None and not src_mobject.isNull():
        try:
            fresh_mfn.copy(src_mobject, fresh_data)
        except Exception:
            pass
    return fresh_mfn, fresh_data
