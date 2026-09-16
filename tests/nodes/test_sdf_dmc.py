"""Unit tests for the pure-numpy SDF dual-marching-cubes port
(``mpynode._common.nodes.mesh.sdf_dmc``).

Maya-free: every test here exercises only numpy. The port is a faithful
de-numba'd reproduction of ``rl.math.geometry.sdf`` (the SDF primitives,
CSG ops, transform math, and the 6 dual-marching-cubes kernels). The
igloo bit-parity test against the saved ``.npz`` lives in
``test_sdf_dmc_igloo.py``.
"""
from __future__ import annotations

import unittest

import numpy as np

from mpynode._common.nodes.mesh.sdf_dmc import (
    eval_sphere,
    eval_box,
    eval_cylinder,
    sdf_union,
    sdf_intersection,
    sdf_difference,
    sdf_smooth_union,
    euler_to_matrix,
    affine_inverse,
    matrix_point,
    decompose_matrix,
    sample_shape,
    shape_bounding_box,
    effective_bounds,
    make_grid,
    dual_marching_cubes,
    mesh_from_shapes,
    SPHERE,
    BOX,
    CYLINDER,
)


def _compose(translate, rotate_deg, scale, rotate_order=0):
    """Build a Maya-style row-vector worldMatrix: M3 = diag(scale) @ R3,
    last row = translate. Mirrors how the node's matrix input is built."""
    R         = euler_to_matrix(np.radians(np.asarray(rotate_deg, float)), rotate_order)
    M         = np.eye(4)
    M[:3, :3] = np.diag(np.asarray(scale, float)) @ R[:3, :3]
    M[3, :3]  = np.asarray(translate, float)
    return M


class TestEvaluators(unittest.TestCase):
    def test_sphere_known(self):
        z = np.array([0.0])
        self.assertAlmostEqual(float(eval_sphere(z, z, z, 1.0)), -1.0)
        self.assertAlmostEqual(
            float(eval_sphere(np.array([2.0]), z, z, 1.0)), 1.0
        )
        self.assertAlmostEqual(
            float(eval_sphere(np.array([1.0]), z, z, 1.0)), 0.0
        )

    def test_box_known(self):
        z    = np.array([0.0])
        half = np.array([1.0, 1.0, 1.0])
        # centre: inside distance = -1
        self.assertAlmostEqual(float(eval_box(z, z, z, half)), -1.0)
        # 2 units out on x: outside distance = 1
        self.assertAlmostEqual(
            float(eval_box(np.array([2.0]), z, z, half)), 1.0
        )
        # on the +x face
        self.assertAlmostEqual(
            float(eval_box(np.array([1.0]), z, z, half)), 0.0
        )

    def test_cylinder_known(self):
        z = np.array([0.0])
        # axis=1 (Y), r=0.5, h=1 -> centre interior = -0.5
        self.assertAlmostEqual(
            float(eval_cylinder(z, z, z, 0.5, 1.0, 1)), -0.5
        )
        # on the radial surface (x=0.5)
        self.assertAlmostEqual(
            float(eval_cylinder(np.array([0.5]), z, z, 0.5, 1.0, 1)), 0.0
        )
        # on the top cap (y=0.5)
        self.assertAlmostEqual(
            float(eval_cylinder(z, np.array([0.5]), z, 0.5, 1.0, 1)), 0.0
        )


class TestCSG(unittest.TestCase):
    def test_union_is_min(self):
        a = np.array([1.0, -2.0, 3.0])
        b = np.array([0.0, 5.0, -1.0])
        np.testing.assert_array_equal(sdf_union(a, b), np.minimum(a, b))

    def test_intersection_is_max(self):
        a = np.array([1.0, -2.0, 3.0])
        b = np.array([0.0, 5.0, -1.0])
        np.testing.assert_array_equal(sdf_intersection(a, b), np.maximum(a, b))

    def test_difference(self):
        a = np.array([1.0, -2.0, 3.0])
        b = np.array([0.0, 5.0, -1.0])
        np.testing.assert_array_equal(sdf_difference(a, b), np.maximum(a, -b))

    def test_smooth_union_reduces_to_min_when_far(self):
        # When |a-b| >> k the smooth union approaches the hard min.
        a = np.array([5.0])
        b = np.array([-5.0])
        k = 0.1
        self.assertAlmostEqual(
            float(sdf_smooth_union(a, b, k)), float(np.minimum(a, b)), places=4
        )

    def test_smooth_union_formula(self):
        a      = np.array([0.3])
        b      = np.array([0.1])
        k      = 0.2
        h      = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
        expect = b * (1 - h) + a * h - k * h * (1 - h)
        np.testing.assert_allclose(sdf_smooth_union(a, b, k), expect)


class TestTransforms(unittest.TestCase):
    def test_euler_identity(self):
        M = euler_to_matrix(np.array([0.0, 0.0, 0.0]), 0)
        np.testing.assert_allclose(M, np.eye(4), atol=1e-12)

    def test_euler_90x_rowvector(self):
        # +90 deg about X in Maya row-vector convention: Y row -> +Z, Z row -> -Y
        M = euler_to_matrix(np.radians(np.array([90.0, 0.0, 0.0])), 0)
        expect = np.array(
            [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
        )
        np.testing.assert_allclose(M[:3, :3], expect, atol=1e-12)

    def test_euler_orthonormal_det1(self):
        M = euler_to_matrix(np.radians(np.array([23.0, -47.0, 88.0])), 0)
        R = M[:3, :3]
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-12)
        self.assertAlmostEqual(float(np.linalg.det(R)), 1.0, places=10)

    def test_affine_inverse_rigid(self):
        R            = euler_to_matrix(np.radians(np.array([10.0, 20.0, 30.0])), 0)
        rigid        = R.copy()
        rigid[3, :3] = [1.0, -2.0, 3.0]
        inv          = affine_inverse(rigid)
        np.testing.assert_allclose(rigid @ inv, np.eye(4), atol=1e-10)

    def test_matrix_point_rowvector(self):
        M         = np.eye(4)
        M[:3, :3] = np.diag([2.0, 3.0, 4.0])
        M[3, :3]  = [1.0, 1.0, 1.0]
        pts       = np.array([[1.0, 1.0, 1.0]])
        out       = matrix_point(pts, M)
        np.testing.assert_allclose(out, np.array([[3.0, 4.0, 5.0]]))

    def test_decompose_roundtrip(self):
        t   = np.array([1.2, -0.15, 0.8])
        rot = [8.0, -37.0, 0.0]
        s   = np.array([1.0, 0.3, 1.2])
        M   = _compose(t, rot, s)
        translate, R3, scale = decompose_matrix(M)
        np.testing.assert_allclose(translate, t, atol=1e-12)
        np.testing.assert_allclose(scale, s, atol=1e-12)
        # R3 should be orthonormal
        np.testing.assert_allclose(R3 @ R3.T, np.eye(3), atol=1e-10)


class TestSampleAndBounds(unittest.TestCase):
    def test_sample_identity_sphere(self):
        M   = np.eye(4)
        pts = np.array([[2.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        d   = sample_shape(M, SPHERE, 1.0, 1.0, 1, np.array([0.5, 0.5, 0.5]), pts)
        np.testing.assert_allclose(d, np.array([1.0, -1.0, 0.0]), atol=1e-12)

    def test_sample_translated_sphere(self):
        M        = np.eye(4)
        M[3, :3] = [5.0, 0.0, 0.0]
        pts      = np.array([[5.0, 0.0, 0.0]])
        d        = sample_shape(M, SPHERE, 2.0, 1.0, 1, np.array([0.5, 0.5, 0.5]), pts)
        self.assertAlmostEqual(float(d[0]), -2.0, places=10)

    def test_sample_uniform_scaled_sphere(self):
        # uniform scale 2 on a unit sphere => radius-2 sphere, exact
        M         = np.eye(4)
        M[:3, :3] = np.diag([2.0, 2.0, 2.0])
        pts       = np.array([[2.0, 0.0, 0.0]])
        d         = sample_shape(M, SPHERE, 1.0, 1.0, 1, np.array([0.5, 0.5, 0.5]), pts)
        self.assertAlmostEqual(float(d[0]), 0.0, places=10)

    def test_bbox_axis_aligned_box(self):
        M = _compose([0.0, -1.5, 0.0], [0, 0, 0], [1, 1, 1])
        lo, hi = shape_bounding_box(
            M, BOX, 1.0, 1.0, 1, np.array([3.0, 1.5, 3.0])
        )
        np.testing.assert_allclose(lo, [-3.0, -3.0, -3.0], atol=1e-12)
        np.testing.assert_allclose(hi, [3.0, 0.0, 3.0], atol=1e-12)

    def test_effective_bounds_padding(self):
        # single unit sphere at origin -> bbox [-1,1]^3, +10% per side
        M = np.eye(4)
        lo, hi = effective_bounds(
            M[None], np.array([SPHERE]), np.array([1.0]), np.array([1.0]),
            np.array([1]), np.array([[0.5, 0.5, 0.5]]),
        )
        np.testing.assert_allclose(lo, [-1.2, -1.2, -1.2], atol=1e-12)
        np.testing.assert_allclose(hi, [1.2, 1.2, 1.2], atol=1e-12)

    def test_make_grid_ij(self):
        X, Y, Z, origin, spacing = make_grid(
            (3, 3, 3), (np.array([-1.0, -1.0, -1.0]), np.array([1.0, 1.0, 1.0]))
        )
        self.assertEqual(X.shape, (3, 3, 3))
        np.testing.assert_allclose(origin, [-1, -1, -1])
        np.testing.assert_allclose(spacing, [1, 1, 1])
        # indexing='ij' -> X varies along axis 0
        self.assertAlmostEqual(float(X[0, 0, 0]), -1.0)
        self.assertAlmostEqual(float(X[2, 0, 0]), 1.0)
        self.assertAlmostEqual(float(Y[0, 2, 0]), 1.0)


class TestDualMarchingCubes(unittest.TestCase):
    def _sphere_field(self, r, n, half):
        bounds = (np.full(3, -half), np.full(3, half))
        X, Y, Z, origin, spacing = make_grid((n, n, n), bounds)
        field = np.sqrt(X**2 + Y**2 + Z**2) - r
        return field, origin, spacing

    def test_dmc_sphere_is_valid_closed_quadmesh(self):
        field, origin, spacing = self._sphere_field(1.0, 24, 1.6)
        points, counts, indices = dual_marching_cubes(field, 0.0, origin, spacing)
        self.assertGreater(points.shape[0], 0)
        # all quads
        self.assertTrue(np.all(counts == 4))
        self.assertEqual(int(counts.sum()), indices.shape[0])
        # validity: indices contiguous 0..P-1, all used
        uniq = np.unique(indices)
        self.assertEqual(uniq[0],   0)
        self.assertEqual(uniq[-1],  points.shape[0] - 1)
        self.assertEqual(uniq.size, points.shape[0])
        # every dual vertex sits near the unit sphere
        radii = np.linalg.norm(points, axis=1)
        self.assertLess(float(np.max(np.abs(radii - 1.0))), 0.2)

    def test_dmc_empty_field(self):
        # field entirely outside -> no surface
        field = np.full((5, 5, 5), 1.0)
        points, counts, indices = dual_marching_cubes(
            field, 0.0, np.zeros(3), np.ones(3)
        )
        self.assertEqual(points.shape[0], 0)


class TestMeshFromShapes(unittest.TestCase):
    def test_single_sphere(self):
        M = np.eye(4)[None]
        points, counts, indices = mesh_from_shapes(
            M, np.array([SPHERE]), np.array([True]), np.array([0.0]),
            np.array([1.0]), np.array([1.0]), np.array([1]),
            np.array([[0.5, 0.5, 0.5]]), resolution=12, iso_value=0.0,
        )
        self.assertGreater(points.shape[0], 0)
        self.assertTrue(np.all(counts == 4))
        radii = np.linalg.norm(points, axis=1)
        self.assertLess(float(np.max(np.abs(radii - 1.0))), 0.25)

    def test_hollow_sphere_subtract(self):
        # outer r=1 sphere minus inner r=0.8 sphere -> a shell (more verts
        # than a solid sphere, and inner-surface verts present)
        M = np.stack([np.eye(4), np.eye(4)])
        points, counts, indices = mesh_from_shapes(
            M, np.array([SPHERE, SPHERE]), np.array([True, False]),
            np.array([0.0, 0.0]), np.array([1.0, 0.8]), np.array([1.0, 1.0]),
            np.array([1, 1]), np.tile([0.5, 0.5, 0.5], (2, 1)),
            resolution=16, iso_value=0.0,
        )
        self.assertGreater(points.shape[0], 0)
        radii = np.linalg.norm(points, axis=1)
        # shell has vertices near both r=1 (outer) and r=0.8 (inner)
        self.assertTrue(np.any(np.abs(radii - 1.0) < 0.15))
        self.assertTrue(np.any(np.abs(radii - 0.8) < 0.15))

    def test_empty_input(self):
        points, counts, indices = mesh_from_shapes(
            np.zeros((0, 4, 4)), np.zeros(0, int), np.zeros(0, bool),
            np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0, int),
            np.zeros((0, 3)), resolution=8,
        )
        self.assertEqual(points.shape[0], 0)


if __name__ == "__main__":
    unittest.main()
