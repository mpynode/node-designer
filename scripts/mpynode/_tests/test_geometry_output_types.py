"""Typed geometry output dataclasses (``mpynode._api2.geometry``).

Covers the Phase-1 surface the three geo generators expose to a user's
``compute``:

* :class:`Mesh` / :class:`NurbsCurve` / :class:`NurbsSurface` construction +
  ``to_mobject`` marshalling (round-trip read-back via ``MFn*``).
* mesh normals + colors, both per-vertex and per-face-vertex INDEXED, incl.
  RGB->RGBA alpha default.
* fail-soft validation (missing/mismatched required attrs -> EMPTY geometry,
  never raises; a bad optional channel is skipped, the geometry still builds).
* structural (duck) typing: any object exposing the required attrs marshals;
  a missing required attr is rejected.
* the ``build_default_output`` back-compat shims on each node module.

Maya api2 lifetime note: a data ``MObject`` returned by ``to_mobject`` /
``build_*_data`` must stay referenced for as long as any ``MFn*`` attached to
it is used -- attaching an ``MFn*`` to an *unretained temporary* is a
use-after-free (hard crash). Product code is safe (compute binds
``self.outX = ...``); these tests bind the data object to a local ``dm`` first,
then attach the function set.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import numpy as np
import maya.api.OpenMaya as om

from._setup import ensure_plugins_loaded, standalone_init
from mpynode._api2 import geometry


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# ---------------------------------------------------------------------------
# read-back helpers. Each holds the data MObject for the whole extraction and
# returns plain data, so no caller keeps an MFn past the MObject's lifetime.
# ---------------------------------------------------------------------------
def _mesh_vert_count(dm):
    """Vertex count, or 0 for an empty/invalid data object (the fail-soft
    marshaller returns an empty MFnMeshData on rejection)."""
    try:
        return om.MFnMesh(dm).numVertices
    except Exception:
        return 0


def _curve_cv_count(dm):
    try:
        return om.MFnNurbsCurve(dm).numCVs
    except Exception:
        return 0


def _surface_cv_count(dm):
    try:
        m = om.MFnNurbsSurface(dm)
        return m.numCVsInU * m.numCVsInV
    except Exception:
        return 0


def _flat_points(pt_array):
    out = []
    for p in pt_array:
        out.extend((p.x, p.y, p.z))
    return out


_QUAD_PTS = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                      [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)
_QUAD_COUNTS = np.array([4], dtype=np.int32)
_QUAD_INDICES = np.array([0, 1, 2, 3], dtype=np.int32)


# ===========================================================================
# Mesh
# ===========================================================================
class TestMeshDataclass(unittest.TestCase):
    def test_basic_quad_roundtrip(self):
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=_QUAD_INDICES).to_mobject()
        fn = om.MFnMesh(dm)
        self.assertEqual(fn.numVertices, 4)
        self.assertEqual(fn.numPolygons, 1)
        got = _flat_points(fn.getPoints(om.MSpace.kObject))
        self.assertEqual(len(got), 12)
        for a, b in zip(got, _QUAD_PTS.ravel().tolist()):
            self.assertAlmostEqual(a, b, places=6)

    def test_per_vertex_normals(self):
        nrm = np.array([[0.0, 0.0, 1.0]] * 4, dtype=np.float64)
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=_QUAD_INDICES, normals=nrm).to_mobject()
        fn = om.MFnMesh(dm)
        read = fn.getVertexNormals(False, om.MSpace.kObject)
        self.assertEqual(len(read), 4)
        for v in read:
            self.assertAlmostEqual(v.x, 0.0, places=5)
            self.assertAlmostEqual(v.y, 0.0, places=5)
            self.assertAlmostEqual(v.z, 1.0, places=5)

    def test_indexed_normals(self):
        # two distinct normals, one per pair of the quad's corners.
        ndir = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0]], dtype=np.float64)
        nidx = np.array([0, 0, 1, 1], dtype=np.int32)
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=_QUAD_INDICES, normals=ndir,
                           normal_indices=nidx).to_mobject()
        fn = om.MFnMesh(dm)
        # face-vertex readback: getVertexNormals would return the planar
        # quad's smooth per-vertex normal and hide the channel.
        fvn = fn.getFaceVertexNormals(0, om.MSpace.kObject)
        # face 0 corners v0,v1 -> ndir[0]=(0,0,1); v2,v3 -> ndir[1]=(1,0,0)
        self.assertAlmostEqual(fvn[0].z, 1.0, places=5)
        self.assertAlmostEqual(fvn[1].z, 1.0, places=5)
        self.assertAlmostEqual(fvn[2].x, 1.0, places=5)
        self.assertAlmostEqual(fvn[3].x, 1.0, places=5)

    def test_per_vertex_colors_rgb_alpha_default(self):
        col = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0], [1.0, 1.0, 0.0]], dtype=np.float64)
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=_QUAD_INDICES, colors=col).to_mobject()
        fn = om.MFnMesh(dm)
        self.assertTrue(fn.getColorSetNames())
        fvc = fn.getFaceVertexColors(fn.getColorSetNames()[0])
        self.assertEqual(len(fvc), 4)          # one quad, 4 face-vertices
        self.assertAlmostEqual(fvc[0].r, 1.0, places=5)
        self.assertAlmostEqual(fvc[1].g, 1.0, places=5)
        self.assertAlmostEqual(fvc[2].b, 1.0, places=5)
        for c in fvc:                           # RGB input -> alpha 1.0
            self.assertAlmostEqual(c.a, 1.0, places=5)

    def test_per_vertex_colors_rgba(self):
        col = np.array([[1.0, 0.0, 0.0, 0.25], [0.0, 1.0, 0.0, 0.5],
                        [0.0, 0.0, 1.0, 0.75], [1.0, 1.0, 0.0, 1.0]],
                       dtype=np.float64)
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=_QUAD_INDICES, colors=col).to_mobject()
        fn = om.MFnMesh(dm)
        fvc = fn.getFaceVertexColors(fn.getColorSetNames()[0])
        self.assertAlmostEqual(fvc[0].a, 0.25, places=5)
        self.assertAlmostEqual(fvc[3].a, 1.0, places=5)

    def test_indexed_colors(self):
        pal = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)
        cidx = np.array([0, 1, 0, 1], dtype=np.int32)
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=_QUAD_INDICES, colors=pal,
                           color_indices=cidx).to_mobject()
        fn = om.MFnMesh(dm)
        fvc = fn.getFaceVertexColors(fn.getColorSetNames()[0])
        self.assertAlmostEqual(fvc[0].r, 1.0, places=5)  # pal[0] red
        self.assertAlmostEqual(fvc[1].g, 1.0, places=5)  # pal[1] green
        self.assertAlmostEqual(fvc[2].r, 1.0, places=5)  # pal[0] red
        self.assertAlmostEqual(fvc[3].g, 1.0, places=5)  # pal[1] green

    # ---- fail-soft validation (empty geometry, never raises) ------------
    def test_missing_required_counts_empty(self):
        obj = SimpleNamespace(points=_QUAD_PTS, indices=_QUAD_INDICES)
        dm = geometry.build_mesh_data(obj)
        self.assertEqual(_mesh_vert_count(dm), 0)

    def test_indices_len_mismatch_empty(self):
        dm = geometry.Mesh(points=_QUAD_PTS, counts=np.array([4], np.int32),
                           indices=np.array([0, 1, 2], np.int32)).to_mobject()
        self.assertEqual(_mesh_vert_count(dm), 0)

    def test_degenerate_face_count_empty(self):
        dm = geometry.Mesh(points=_QUAD_PTS, counts=np.array([2, 2], np.int32),
                           indices=np.array([0, 1, 2, 3], np.int32)).to_mobject()
        self.assertEqual(_mesh_vert_count(dm), 0)

    def test_index_out_of_range_empty(self):
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=np.array([0, 1, 2, 99], np.int32)).to_mobject()
        self.assertEqual(_mesh_vert_count(dm), 0)

    def test_bad_optional_channel_skipped_geometry_still_builds(self):
        # per-vertex normals of the wrong length: skip the channel, keep mesh.
        dm = geometry.Mesh(points=_QUAD_PTS, counts=_QUAD_COUNTS,
                           indices=_QUAD_INDICES,
                           normals=np.array([[0.0, 0.0, 1.0]], np.float64)
                           ).to_mobject()
        fn = om.MFnMesh(dm)
        self.assertEqual(fn.numVertices, 4)     # mesh survived

    # ---- duck typing -----------------------------------------------------
    def test_duck_typed_foo_accepted(self):
        class Foo:
            pass
        foo = Foo()
        foo.points = _QUAD_PTS
        foo.counts = _QUAD_COUNTS
        foo.indices = _QUAD_INDICES
        foo.colors = np.array([[1.0, 0.0, 0.0]] * 4, np.float64)
        self.assertTrue(geometry.is_mesh_like(foo))
        dm = geometry.build_mesh_data(foo)
        fn = om.MFnMesh(dm)
        self.assertEqual(fn.numVertices, 4)
        self.assertTrue(fn.getColorSetNames())   # optional read honored


# ===========================================================================
# NURBS curve
# ===========================================================================
class TestCurveDataclass(unittest.TestCase):
    def _open_cvs(self, n=6):
        return np.array([[float(i), 0.0, 0.0] for i in range(n)],
                        dtype=np.float64)

    def _periodic_cvs(self):
        # 8 unique circle CVs + first degree(3) wrapped = 11 CVs.
        base = np.array([[1.0, 0.0, 0.0], [0.7, 0.7, 0.0], [0.0, 1.0, 0.0],
                         [-0.7, 0.7, 0.0], [-1.0, 0.0, 0.0], [-0.7, -0.7, 0.0],
                         [0.0, -1.0, 0.0], [0.7, -0.7, 0.0]], dtype=np.float64)
        return np.vstack([base, base[:3]])

    def test_open_curve_defaults(self):
        dm = geometry.NurbsCurve(points=self._open_cvs(6)).to_mobject()
        fn = om.MFnNurbsCurve(dm)
        self.assertEqual(fn.numCVs, 6)
        self.assertEqual(fn.degree, 3)
        self.assertEqual(int(fn.form), int(om.MFnNurbsCurve.kOpen))
        # auto knot count = numCVs + degree - 1
        self.assertEqual(len(fn.knots()), 6 + 3 - 1)

    def test_periodic_curve(self):
        dm = geometry.NurbsCurve(points=self._periodic_cvs(), degree=3,
                                 periodic=True).to_mobject()
        fn = om.MFnNurbsCurve(dm)
        self.assertEqual(fn.numCVs, 11)
        self.assertEqual(int(fn.form), int(om.MFnNurbsCurve.kPeriodic))

    def test_kv_override_used(self):
        cvs = self._open_cvs(5)
        kv = geometry._curve_uniform_knots(5, 3, False)   # length 7, valid
        dm = geometry.NurbsCurve(points=cvs, degree=3, kv=kv).to_mobject()
        fn = om.MFnNurbsCurve(dm)
        self.assertEqual(len(fn.knots()), len(kv))

    def test_kv_wrong_length_rebuilds_uniform(self):
        cvs = self._open_cvs(6)
        dm = geometry.NurbsCurve(points=cvs, degree=3,
                                 kv=[0.0, 1.0]).to_mobject()  # too few
        fn = om.MFnNurbsCurve(dm)
        self.assertEqual(fn.numCVs, 6)                    # still built
        self.assertEqual(len(fn.knots()), 6 + 3 - 1)

    def test_too_few_cvs_empty(self):
        dm = geometry.NurbsCurve(points=self._open_cvs(2), degree=3).to_mobject()
        self.assertEqual(_curve_cv_count(dm), 0)

    def test_invalid_degree_defaults_to_three(self):
        dm = geometry.NurbsCurve(points=self._open_cvs(6), degree=4).to_mobject()
        fn = om.MFnNurbsCurve(dm)
        self.assertEqual(fn.degree, 3)

    def test_legacy_form_closed_via_shim_object(self):
        obj = SimpleNamespace(points=self._open_cvs(6), degree=3,
                              form="closed")
        dm = geometry.build_curve_data(obj)
        fn = om.MFnNurbsCurve(dm)
        self.assertEqual(int(fn.form), int(om.MFnNurbsCurve.kClosed))

    def test_duck_typed_curve_accepted(self):
        obj = SimpleNamespace(points=self._open_cvs(6))
        self.assertTrue(geometry.is_curve_like(obj))
        self.assertEqual(_curve_cv_count(geometry.build_curve_data(obj)), 6)


# ===========================================================================
# NURBS surface
# ===========================================================================
class TestSurfaceDataclass(unittest.TestCase):
    def _grid(self, nu=4, nv=4):
        return np.array([[[float(u), float(v), 0.0] for v in range(nv)]
                         for u in range(nu)], dtype=np.float64)

    def _periodic_u_flat(self):
        # 11 x 4 periodic-U (wrapped) x open-V grid, U-major flat.
        rx = [1.0, 0.7, 0.0, -0.7, -1.0, -0.7, 0.0, 0.7, 1.0, 0.7, 0.0]
        ry = [0.0, 0.7, 1.0, 0.7, 0.0, -0.7, -1.0, -0.7, 0.0, 0.7, 1.0]
        heights = [0.0, 1.0, 2.0, 3.0]
        rows = []
        for u in range(11):
            for v in range(4):
                rows.append([rx[u], heights[v], ry[u]])
        return np.array(rows, dtype=np.float64), 11, 4

    def test_grid_roundtrip(self):
        dm = geometry.NurbsSurface(points=self._grid(4, 5)).to_mobject()
        fn = om.MFnNurbsSurface(dm)
        self.assertEqual(fn.numCVsInU, 4)
        self.assertEqual(fn.numCVsInV, 5)
        self.assertEqual(fn.degreeInU, 3)
        self.assertEqual(fn.degreeInV, 3)

    def test_flat_with_num_uv(self):
        grid = self._grid(4, 4).reshape(16, 3)
        dm = geometry.NurbsSurface(points=grid, num_u=4, num_v=4).to_mobject()
        self.assertEqual(_surface_cv_count(dm), 16)

    def test_flat_without_num_uv_empty(self):
        grid = self._grid(4, 4).reshape(16, 3)
        dm = geometry.NurbsSurface(points=grid).to_mobject()  # no num_u/num_v
        self.assertEqual(_surface_cv_count(dm), 0)

    def test_num_uv_mismatch_empty(self):
        grid = self._grid(4, 4).reshape(16, 3)
        dm = geometry.NurbsSurface(points=grid, num_u=3,
                                   num_v=4).to_mobject()  # 12 != 16
        self.assertEqual(_surface_cv_count(dm), 0)

    def test_periodic_u(self):
        grid, nu, nv = self._periodic_u_flat()
        dm = geometry.NurbsSurface(points=grid, num_u=nu, num_v=nv,
                                   degree_u=3, degree_v=3,
                                   periodic_u=True,
                                   periodic_v=False).to_mobject()
        fn = om.MFnNurbsSurface(dm)
        self.assertEqual(fn.numCVsInU, 11)
        self.assertEqual(int(fn.formInU), int(om.MFnNurbsSurface.kPeriodic))
        self.assertEqual(int(fn.formInV), int(om.MFnNurbsSurface.kOpen))

    def test_too_few_cvs_each_direction_empty(self):
        dm = geometry.NurbsSurface(points=self._grid(2, 2), degree_u=3,
                                   degree_v=3).to_mobject()
        self.assertEqual(_surface_cv_count(dm), 0)


# ===========================================================================
# structural gates
# ===========================================================================
class TestStructuralGates(unittest.TestCase):
    def test_mesh_like(self):
        self.assertTrue(geometry.is_mesh_like(
            geometry.Mesh(points=1, counts=1, indices=1)))
        self.assertFalse(geometry.is_mesh_like(
            SimpleNamespace(points=1, counts=1)))   # no indices
        self.assertFalse(geometry.is_mesh_like(None))

    def test_curve_like(self):
        self.assertTrue(geometry.is_curve_like(geometry.NurbsCurve(points=1)))
        self.assertTrue(geometry.is_curve_like(SimpleNamespace(points=1)))
        self.assertFalse(geometry.is_curve_like(SimpleNamespace(degree=3)))

    def test_surface_like(self):
        self.assertTrue(geometry.is_surface_like(
            geometry.NurbsSurface(points=1)))
        self.assertFalse(geometry.is_surface_like(object()))


# ===========================================================================
# build_default_output back-compat shims
# ===========================================================================
class TestBuildDefaultOutputShims(unittest.TestCase):
    def test_mesh_shim(self):
        from mpynode._api2.mpy_mesh import build_default_output
        dm = build_default_output(_QUAD_PTS, _QUAD_COUNTS, _QUAD_INDICES)
        self.assertEqual(_mesh_vert_count(dm), 4)

    def test_mesh_shim_with_colors(self):
        from mpynode._api2.mpy_mesh import build_default_output
        col = np.array([[1.0, 0.0, 0.0]] * 4, np.float64)
        dm = build_default_output(_QUAD_PTS, _QUAD_COUNTS, _QUAD_INDICES,
                                  colors=col)
        fn = om.MFnMesh(dm)
        self.assertEqual(fn.numVertices, 4)
        self.assertTrue(fn.getColorSetNames())

    def test_curve_shim(self):
        # legacy positional signature: (cvs, knots, degree, form)
        from mpynode._api2.mpy_nurbs_curve import build_default_output
        cvs = np.array([[float(i), 0.0, 0.0] for i in range(6)], np.float64)
        dm = build_default_output(cvs, None, 3, "open")
        self.assertEqual(_curve_cv_count(dm), 6)

    def test_curve_shim_closed_form_passthrough(self):
        from mpynode._api2.mpy_nurbs_curve import build_default_output
        cvs = np.array([[float(i), 0.0, 0.0] for i in range(6)], np.float64)
        dm = build_default_output(cvs, None, 3, "closed")
        fn = om.MFnNurbsCurve(dm)
        self.assertEqual(int(fn.form), int(om.MFnNurbsCurve.kClosed))

    def test_surface_shim(self):
        from mpynode._api2.mpy_nurbs_surface import build_default_output
        grid = np.array([[[float(u), float(v), 0.0] for v in range(4)]
                         for u in range(4)], np.float64).reshape(16, 3)
        dm = build_default_output(grid, 4, 4)
        self.assertEqual(_surface_cv_count(dm), 16)


if __name__ == "__main__":
    unittest.main()
