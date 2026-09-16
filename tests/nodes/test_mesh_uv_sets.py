"""Mesh.uv_sets -- expose a mesh input's UV set(s) as standalone 2D "meshes".

A mesh INPUT read hands the compute a ``geometry.Mesh`` whose ``points`` /
``counts`` / ``indices`` describe the 3D topology. ``uv_sets`` mirrors that
convention in the independent 2D UV index space: one :class:`UVSet` per named UV
set, each with ``name`` + 2D ``points`` (u, v) + per-face ``counts`` + ``indices``
(uvIds). Proven here on a deterministic ``polyCube`` (6 quad faces; default set
``map1``; more UVs than vertices because seam corners are unshared).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import numpy as np
import maya.cmds as mc
import maya.api.OpenMaya as om

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _attached_mesh(shape_name):
    """Wrap a mesh SHAPE as an ATTACHED geometry.Mesh (the same object an input
    plug hands a compute)."""
    from mpynode._api2.geometry import Mesh

    sel = om.MSelectionList()
    sel.add(shape_name)
    return Mesh._attach(sel.getDependNode(0))


class TestMeshUVSets(unittest.TestCase):
    def _cube(self):
        mc.file(new=True, force=True)
        xform = mc.polyCube(constructionHistory=False)[0]
        shape = mc.listRelatives(xform, shapes=True, fullPath=True)[0]
        return shape

    def test_uv_sets_returns_list_of_uvset(self):
        from mpynode._api2.geometry import UVSet

        m    = _attached_mesh(self._cube())
        sets = m.uv_sets
        self.assertIsInstance(sets, list)
        self.assertGreaterEqual(len(sets), 1)
        self.assertIsInstance(sets[0], UVSet)

    def test_default_set_named_map1(self):
        m     = _attached_mesh(self._cube())
        names = [s.name for s in m.uv_sets]
        self.assertIn("map1", names)

    def test_points_are_2d_and_invariants_hold(self):
        s = _attached_mesh(self._cube()).uv_sets[0]
        # points are (M, 2) float UV coords
        self.assertEqual(s.points.ndim,     2)
        self.assertEqual(s.points.shape[1], 2)
        self.assertEqual(s.points.dtype,    np.float64)
        # counts/indices reconstruct the per-face UV layout (same invariant as
        # the mesh's counts/indices): sum(counts) == len(indices)
        self.assertEqual(int(s.counts.sum()), int(s.indices.shape[0]))
        # a cube is 6 quads -> 6 counts of 4, 24 uvIds
        self.assertEqual(int(s.counts.shape[0]), 6)
        self.assertTrue((s.counts == 4).all())
        self.assertEqual(int(s.indices.shape[0]), 24)
        # every uvId indexes a real UV point
        self.assertEqual(s.num_uvs, int(s.points.shape[0]))
        self.assertLess(int(s.indices.max()), s.num_uvs)
        self.assertGreaterEqual(int(s.indices.min()), 0)

    def test_uv_index_space_independent_of_vertices(self):
        # UVs are per-face-vertex: a cube's seam corners are unshared, so there
        # are MORE UVs than the 8 vertices -- the UV point array is its own space.
        m       = _attached_mesh(self._cube())
        n_verts = m.fn.numVertices
        self.assertNotEqual(m.uv_sets[0].num_uvs, n_verts)

    def test_as_mesh_builds_valid_2d_mesh(self):
        from mpynode._api2.geometry import Mesh, build_mesh_data

        s    = _attached_mesh(self._cube()).uv_sets[0]
        flat = s.as_mesh()
        self.assertIsInstance(flat, Mesh)
        # padded to (M, 3) with z == 0
        self.assertEqual(flat.points.shape[1], 3)
        self.assertTrue(np.allclose(flat.points[:, 2], 0.0))
        # all faces kept (cube is fully mapped, no <3 counts)
        self.assertEqual(int(flat.counts.sum()), int(flat.indices.shape[0]))
        self.assertEqual(int(flat.counts.shape[0]), 6)
        # and it marshals into a real DG mesh (no exception, non-null data)
        data = build_mesh_data(flat)
        self.assertFalse(data.isNull())

    def test_value_mesh_has_no_uv_sets(self):
        from mpynode._api2.geometry import Mesh

        # A detached / value mesh (no live fn) reports no UV sets, never raises.
        m = Mesh(points=[[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                 counts=[3], indices=[0, 1, 2])
        self.assertEqual(m.uv_sets, [])


class TestMeshGracefulCtor(unittest.TestCase):
    """Mesh(...) gracefully accepts a UVSet or 2D points, so you can build the
    output mesh straight from a UV set: ``self.outMesh = Mesh(uv_set)``."""

    def test_mesh_from_uvset_equals_as_mesh(self):
        from mpynode._api2.geometry import Mesh

        mc.file(new=True, force=True)
        xform = mc.polyCube(constructionHistory=False)[0]
        shape = mc.listRelatives(xform, shapes=True, fullPath=True)[0]
        uv    = _attached_mesh(shape).uv_sets[0]

        direct    = Mesh(uv)      # graceful: build straight from the UVSet
        reference = uv.as_mesh()  # the explicit projection
        self.assertTrue(np.array_equal(direct.points, reference.points))
        self.assertTrue(np.array_equal(direct.counts, reference.counts))
        self.assertTrue(np.array_equal(direct.indices, reference.indices))
        # points are the padded 3D form (z == 0)
        self.assertEqual(direct.points.shape[1], 3)
        self.assertTrue(np.allclose(direct.points[:, 2], 0.0))

    def test_2d_points_are_padded_to_3d(self):
        from mpynode._api2.geometry import Mesh

        m = Mesh(points=[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
                 counts=[3], indices=[0, 1, 2])
        self.assertEqual(m.points.shape, (3, 3))
        self.assertTrue(np.allclose(m.points[:, 2], 0.0))
        self.assertTrue(np.allclose(m.points[:, :2],
                                    [[0, 0], [1, 0], [0, 1]]))

    def test_3d_points_unchanged(self):
        from mpynode._api2.geometry import Mesh

        pts = [[0, 0, 5], [1, 0, 5], [0, 1, 5]]
        m   = Mesh(points=pts, counts=[3], indices=[0, 1, 2])
        self.assertEqual(m.points.shape, (3, 3))
        self.assertTrue(np.allclose(m.points, pts))  # z preserved, no padding

    def test_empty_mesh_still_valid(self):
        from mpynode._api2.geometry import Mesh

        m = Mesh()
        self.assertIsNone(m._points)

    def test_uvset_from_value_mesh_builds_dg_data(self):
        from mpynode._api2.geometry import Mesh, build_mesh_data

        mc.file(new=True, force=True)
        xform = mc.polyCube(constructionHistory=False)[0]
        shape = mc.listRelatives(xform, shapes=True, fullPath=True)[0]
        uv    = _attached_mesh(shape).uv_sets[0]
        data  = build_mesh_data(Mesh(uv))
        self.assertFalse(data.isNull())


if __name__ == "__main__":
    unittest.main()
