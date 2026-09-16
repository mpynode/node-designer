"""Bit-parity test: the mpynode SDF dual-marching-cubes port must reproduce
``rl.math.geometry.tests.test_sdf.TestSDFIgloo`` -- the saved reference mesh
``test_assets/test_sdf.igloo.npz`` -- when fed the same primitives in the
same order at resolution 16.

This is the "matches TestSDFIgloo" proof for the port. It mirrors the
source test's assertions exactly: point_count, points allclose
(rtol=1e-5, atol=1e-7), face_count, indices array_equal, and validity.
"""
from __future__ import annotations

import os
import unittest

import numpy as np

from mpynode._common.nodes.mesh import sdf_dmc
from mpynode._demos import sdf_igloo
from tests import _paths


_REF_NPZ = os.path.join(_paths.ASSETS, "test_sdf.igloo.npz"
)


def _mesh_valid(points, counts, indices):
    """Mirror of rl MeshData.valid: indices contiguous 0..V-1, all used,
    sum(counts) == len(indices)."""
    uniq = np.unique(indices)
    if uniq.size == 0:
        return False
    return bool(
        uniq[0] == 0
        and uniq[-1] == points.shape[0] - 1
        and uniq.size == points.shape[0]
        and int(counts.sum()) == indices.shape[0]
    )


class TestSDFIglooParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with np.load(_REF_NPZ, allow_pickle=True) as data:
            cls.ref_points  = np.asarray(data["points"],  dtype=np.float64)
            cls.ref_counts  = np.asarray(data["counts"],  dtype=np.int32)
            cls.ref_indices = np.asarray(data["indices"], dtype=np.int32)

        prims  = sdf_igloo.igloo_primitives()
        arrays = sdf_igloo.primitives_to_arrays(prims)
        points, counts, indices = sdf_dmc.mesh_from_shapes(
            resolution=16, iso_value=0.0, **arrays
        )
        cls.points  = points
        cls.counts  = counts
        cls.indices = indices

    def test_point_count(self):
        self.assertEqual(self.points.shape[0], self.ref_points.shape[0])

    def test_points_allclose(self):
        np.testing.assert_allclose(
            self.points, self.ref_points, rtol=1e-5, atol=1e-7
        )

    def test_face_count(self):
        self.assertEqual(self.counts.size, self.ref_counts.size)

    def test_indices_equal(self):
        np.testing.assert_array_equal(self.indices, self.ref_indices)

    def test_valid(self):
        self.assertTrue(_mesh_valid(self.points, self.counts, self.indices))


if __name__ == "__main__":
    unittest.main()
