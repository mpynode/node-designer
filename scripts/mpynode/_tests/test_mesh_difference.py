"""``Mesh - Mesh`` -- tolerance-based overlap removal (NOT a boolean).

Mirrors the reference ``rl/math/geometry/mesh.py`` ``MeshData.difference``: match
our vertices against the other side's with a nearest-neighbour-within-tolerance
query, drop every face whose corners are ALL matched, then compact + renumber.

The parts that would fail silently if they regressed:

  * the match is a fixed-RADIUS query, so the scipy-free spatial hash must find
    every pair a ``cKDTree`` would -- a missed pair silently keeps a face that
    should have gone. ``test_hash_matches_brute_force`` and
    ``test_hash_matches_scipy`` (skipped without scipy) pin that down.
  * ``contained=True``: a face only PARTLY overlapping the other mesh must
    SURVIVE. Dropping it would eat geometry the user never asked to remove.
  * ``(a + b) - b == a`` -- subtraction is the inverse of the union ``+``.
"""
from __future__ import annotations

import unittest

import numpy as np

from mpynode._tests import _setup


def setUpModule():
    _setup.standalone_init()


def _quad(x=0.0, y=0.0):
    """A single 4-gon on the unit square, offset to (x, y)."""
    from mpynode._api2.geometry import Mesh
    pts = np.array([[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]],
                   dtype=np.float64)
    return Mesh(points=pts, counts=np.array([4]),
                indices=np.array([0, 1, 2, 3]))


def _brute_force(points, other, tol):
    """The O(N*M) oracle: indices of ``points`` within ``tol`` of any ``other``."""
    d = np.sqrt(((points[:, None, :] - other[None, :, :]) ** 2).sum(axis=2))
    return np.flatnonzero((d <= tol).any(axis=1)).astype(np.int64)


class TestPointsWithin(unittest.TestCase):
    """The vertex matcher underneath -- the only genuinely new algorithm."""

    def test_hash_matches_brute_force(self):
        from mpynode._api2.geometry import _points_within
        rng = np.random.default_rng(20260813)
        for trial in range(20):
            a = rng.normal(scale=3.0, size=(120, 3))
            # half of b is a jittered copy of a, so real matches exist
            b = np.concatenate([
                a[:40] + rng.normal(scale=2e-3, size=(40, 3)),
                rng.normal(scale=3.0, size=(60, 3))])
            for tol in (1e-6, 1e-3, 5e-3, 0.5):
                with self.subTest(trial=trial, tol=tol):
                    np.testing.assert_array_equal(
                        _points_within(a, b, tol), _brute_force(a, b, tol))

    def test_hash_matches_scipy(self):
        """Parity with the reference's own cKDTree query, where scipy exists."""
        try:
            from scipy.spatial import cKDTree
        except Exception:
            self.skipTest("scipy not available")
        from mpynode._api2.geometry import _points_within
        rng = np.random.default_rng(7)
        a = rng.normal(scale=2.0, size=(400, 3))
        b = np.concatenate([a[:150] + rng.normal(scale=1e-4, size=(150, 3)),
                            rng.normal(scale=2.0, size=(250, 3))])
        for tol in (1e-6, 1e-4, 1e-3, 0.25):
            with self.subTest(tol=tol):
                distances, _ = cKDTree(b).query(a)
                np.testing.assert_array_equal(
                    _points_within(a, b, tol),
                    np.flatnonzero(distances <= tol).astype(np.int64))

    def test_zero_tolerance_is_exact_coincidence(self):
        from mpynode._api2.geometry import _points_within
        a = np.array([[0.0, 0, 0], [1.0, 0, 0], [2.0, 0, 0]])
        b = np.array([[1.0, 0, 0], [2.0, 1e-15, 0]])
        np.testing.assert_array_equal(_points_within(a, b, 0.0), [1])

    def test_empty_sides_match_nothing(self):
        from mpynode._api2.geometry import _points_within
        a = np.zeros((3, 3))
        empty = np.zeros((0, 3))
        self.assertEqual(_points_within(a, empty, 1.0).size, 0)
        self.assertEqual(_points_within(empty, a, 1.0).size, 0)


class TestMeshDifference(unittest.TestCase):

    def test_union_then_difference_round_trips(self):
        a, b = _quad(0.0), _quad(5.0)
        out = (a + b) - b
        np.testing.assert_allclose(out.points, a.points)
        np.testing.assert_array_equal(out.counts, a.counts)
        np.testing.assert_array_equal(out.indices, a.indices)

    def test_disjoint_meshes_subtract_to_a_no_op(self):
        a, b = _quad(0.0), _quad(5.0)
        out = a - b
        np.testing.assert_allclose(out.points, a.points)
        np.testing.assert_array_equal(out.counts, [4])

    def test_identical_meshes_subtract_to_empty(self):
        a = _quad(0.0)
        out = a - _quad(0.0)
        self.assertEqual(out.counts.size, 0)
        self.assertEqual(out.points.shape[0], 0)

    def test_a_partly_overlapping_face_SURVIVES(self):
        """``contained=True``: every corner must match before a face goes."""
        from mpynode._api2.geometry import Mesh
        a = _quad(0.0)
        # only two of the quad's four corners exist in b
        b = Mesh(points=np.array([[0.0, 0, 0], [1.0, 0, 0], [0.5, 9.0, 0]]),
                 counts=np.array([3]), indices=np.array([0, 1, 2]))
        out = a - b
        np.testing.assert_array_equal(out.counts, [4])

    def test_only_the_fully_matched_face_is_removed(self):
        a = _quad(0.0) + _quad(5.0)
        out = a - _quad(5.0)
        np.testing.assert_array_equal(out.counts, [4])
        np.testing.assert_allclose(out.points, _quad(0.0).points)

    def test_tolerance_is_fuzzy_within_1e6_and_exact_beyond_it(self):
        near = _quad(0.0)
        near._points = near.points + 4e-7           # inside the 1e-6 default
        self.assertEqual((_quad(0.0) - near).counts.size, 0)
        far = _quad(0.0)
        far._points = far.points + 4e-5             # outside it
        np.testing.assert_array_equal((_quad(0.0) - far).counts, [4])

    def test_sub_does_not_mutate_either_operand(self):
        a, b = _quad(0.0), _quad(0.0)
        _ = a - b
        np.testing.assert_array_equal(a.counts, [4])
        np.testing.assert_array_equal(b.counts, [4])

    def test_isub_mutates_in_place(self):
        a = _quad(0.0)
        a -= _quad(0.0)
        self.assertEqual(a.counts.size, 0)

    def test_difference_drops_derived_channels(self):
        a = _quad(0.0) + _quad(5.0)
        a.normals = np.tile([0.0, 0.0, 1.0], (8, 1))
        out = a - _quad(5.0)
        self.assertIsNone(out.normals)
        self.assertEqual(out.component_tags, {})

    def test_a_points_only_mesh_is_left_alone(self):
        """No topology -> no faces to remove; the point bucket must survive."""
        from mpynode._api2.geometry import Mesh
        a = Mesh(points=np.zeros((4, 3)))
        out = a - _quad(0.0)
        self.assertEqual(out.points.shape, (4, 3))

    def test_morph_and_vector_branches_still_work(self):
        """The Mesh branch must not have shadowed the other two."""
        class _FakeMorph:
            indices = np.array([1])
            offsets = np.array([[0.0, 0.0, 5.0]])

        m = _quad(0.0)
        np.testing.assert_allclose((m - _FakeMorph()).points[1], [1, 0, -5.0])
        np.testing.assert_allclose((m - np.array([1.0, 0, 0])).points[0],
                                   [-1.0, 0, 0])


if __name__ == "__main__":
    unittest.main()
