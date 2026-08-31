"""Arithmetic dunders + sub-mesh extraction on the geometry value objects.

Modelled on ``rl/math/geometry/mesh.py``'s ``MeshData``: ``__add__`` is
``copy()`` + ``__iadd__`` so the merge logic exists once, and the morph branch
is DUCK-TYPED (``.indices`` / ``.offsets``) so geometry.py never imports
morph.py.

The tests that matter most are the ones pinning down behaviour that fails
SILENTLY if it regresses:

  * ``__iadd__`` must ``_cow_detach`` first -- mutating an attached mesh's cached
    points leaves ``_attached`` True, so ``to_mobject()`` returns the ORIGINAL
    data MObject and the edit vanishes.
  * the morph branch must use ``np.add.at``, not ``points[idx] += off``, which
    keeps only the LAST write on duplicate indices.
  * ``from_tag`` must dispatch on the tag's own component type -- ``region()``
    returns POINTS for a vertex tag and INDICES for a face tag, so
    ``from_faces(region(tag))`` produces garbage on a vertex tag.
"""
from __future__ import annotations

import unittest

import numpy as np

from tests import _setup


def setUpModule():
    _setup.standalone_init()


def _quad(x=0.0):
    """A single 4-gon whose verts sit at x, x+1 on the unit square."""
    from mpynode._api2.geometry import Mesh
    pts = np.array([[x, 0, 0], [x + 1, 0, 0], [x + 1, 1, 0], [x, 1, 0]],
                   dtype=np.float64)
    return Mesh(points=pts, counts=np.array([4]),
                indices=np.array([0, 1, 2, 3]))


def _grid2():
    """Two quads sharing no verts: faces 0 and 1, 8 points."""
    from mpynode._api2.geometry import Mesh
    pts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                    [2, 0, 0], [3, 0, 0], [3, 1, 0], [2, 1, 0]],
                   dtype=np.float64)
    return Mesh(points=pts, counts=np.array([4, 4]),
                indices=np.array([0, 1, 2, 3, 4, 5, 6, 7]))


class _FakeMorph:
    """Anything with .indices/.offsets is a morph to the duck-type branch."""

    def __init__(self, indices, offsets):
        self.indices = np.asarray(indices, dtype=np.int64)
        self.offsets = np.asarray(offsets, dtype=np.float64)


class TestMeshUnion(unittest.TestCase):

    def test_add_rebases_the_other_sides_indices(self):
        a, b = _quad(0.0), _quad(5.0)
        c = a + b
        self.assertEqual(c.points.shape, (8, 3))
        np.testing.assert_array_equal(c.counts, [4, 4])
        # the whole point: b's indices are shifted past a's vertex count
        np.testing.assert_array_equal(c.indices, [0, 1, 2, 3, 4, 5, 6, 7])
        np.testing.assert_allclose(c.points[4], [5, 0, 0])

    def test_add_does_not_mutate_either_operand(self):
        a, b = _quad(0.0), _quad(5.0)
        _ = a + b
        self.assertEqual(a.points.shape, (4, 3))
        self.assertEqual(b.points.shape, (4, 3))

    def test_iadd_does_mutate_the_left_operand(self):
        a, b = _quad(0.0), _quad(5.0)
        a += b
        self.assertEqual(a.points.shape, (8, 3))

    def test_union_onto_an_empty_mesh_adopts_the_other(self):
        from mpynode._api2.geometry import Mesh
        c = Mesh() + _quad(2.0)
        self.assertEqual(c.points.shape, (4, 3))
        np.testing.assert_array_equal(c.counts, [4])

    def test_sum_works_via_radd(self):
        total = sum([_quad(0.0), _quad(2.0), _quad(4.0)])
        self.assertEqual(total.points.shape, (12, 3))
        np.testing.assert_array_equal(total.counts, [4, 4, 4])
        np.testing.assert_array_equal(total.indices[-4:], [8, 9, 10, 11])

    def test_union_drops_derived_channels(self):
        a, b = _quad(0.0), _quad(5.0)
        a.normals = np.tile([0.0, 0.0, 1.0], (4, 1))
        c = a + b
        self.assertIsNone(c.normals)


class TestMeshDifference(unittest.TestCase):
    """``Mesh - Mesh`` is tolerance-based OVERLAP REMOVAL, not a boolean. It
    drops every face of ours whose corners ALL coincide -- within ``tolerance``,
    default 1e-6 -- with a vertex of the other mesh, then compacts the points
    and renumbers. It is the inverse of the union ``+``."""

    def _union(self):
        return _quad(0.0) + _quad(5.0)

    def _quad_shifted(self, eps):
        """The x=5 quad nudged ``eps`` along +x, so every corner sits exactly
        ``eps`` from its partner in the union."""
        q = _quad(5.0)
        q.points = q.points + np.array([eps, 0.0, 0.0])
        return q

    def test_mesh_minus_mesh_removes_the_coincident_faces(self):
        a, b = _quad(0.0), _quad(5.0)
        c = (a + b) - b
        np.testing.assert_array_equal(c.counts, [4])
        np.testing.assert_allclose(c.points, a.points)

    def test_surviving_points_are_compacted_and_indices_renumbered(self):
        # the survivor is verts 4..7 of the union and must come back as 0..3
        c = (_quad(5.0) + _quad(0.0)) - _quad(5.0)
        self.assertEqual(c.points.shape, (4, 3))
        np.testing.assert_array_equal(c.indices, [0, 1, 2, 3])
        np.testing.assert_allclose(c.points[0], [0, 0, 0])

    def test_a_face_survives_unless_EVERY_corner_coincides(self):
        """``contained=True``. The x=4 quad shares exactly two corners with the
        x=5 quad; dropping that face would be the silent wrong answer."""
        c = self._union() - _quad(4.0)
        np.testing.assert_array_equal(c.counts, [4, 4])
        self.assertEqual(c.points.shape, (8, 3))

    def test_the_default_tolerance_is_1e_6(self):
        # 9e-7 off -> still the same vertex, the face goes
        np.testing.assert_array_equal(
            (self._union() - self._quad_shifted(9e-7)).counts, [4])
        # 1.1e-6 off -> a different vertex, nothing matches, nothing goes
        np.testing.assert_array_equal(
            (self._union() - self._quad_shifted(1.1e-6)).counts, [4, 4])

    def test_no_coincident_vertex_leaves_the_mesh_untouched(self):
        m = self._union()
        m.normals = np.tile([0.0, 0.0, 1.0], (8, 1))
        c = m - _quad(50.0)
        np.testing.assert_array_equal(c.counts, [4, 4])
        self.assertEqual(c.points.shape, (8, 3))
        # no face was removed, so the derived channels still describe the mesh
        self.assertIsNotNone(c.normals)

    def test_removing_a_face_drops_the_derived_channels(self):
        m = self._union()
        m.normals = np.tile([0.0, 0.0, 1.0], (8, 1))
        m._tags = {"all": {"type": "face", "indices": np.array([0, 1])}}
        c = m - _quad(5.0)
        self.assertIsNone(c.normals)
        self.assertEqual(c.component_tags, {})

    def test_subtracting_itself_yields_an_empty_mesh(self):
        c = _quad(0.0) - _quad(0.0)
        self.assertEqual(c.points.shape, (0, 3))
        self.assertEqual(c.counts.size, 0)
        self.assertEqual(c.indices.size, 0)

    def test_sub_does_not_mutate_either_operand(self):
        a, b = self._union(), _quad(5.0)
        _ = a - b
        self.assertEqual(a.points.shape, (8, 3))
        self.assertEqual(b.points.shape, (4, 3))

    def test_isub_does_mutate_the_left_operand(self):
        a = self._union()
        a -= _quad(5.0)
        self.assertEqual(a.points.shape, (4, 3))

    def test_subtracting_a_non_numeric_operand_is_still_an_error(self):
        """The Mesh branch is what got added; anything that is neither a Mesh,
        a morph, nor array-like still has to fail loudly rather than reach the
        point field."""
        with self.assertRaises(TypeError):
            _ = _quad(0.0) - object()
        with self.assertRaises(ValueError):
            _ = _quad(0.0) - "not a mesh"


class TestMeshMorph(unittest.TestCase):

    def test_add_morph_applies_offsets_at_indices(self):
        m = _quad(0.0)
        out = m + _FakeMorph([1, 3], [[0, 0, 2.0], [0, 0, -1.0]])
        np.testing.assert_allclose(out.points[1], [1, 0, 2.0])
        np.testing.assert_allclose(out.points[3], [0, 1, -1.0])
        np.testing.assert_allclose(out.points[0], [0, 0, 0])   # untouched

    def test_duplicate_indices_ACCUMULATE(self):
        """``points[idx] += off`` would keep only the last write. np.add.at
        accumulates -- this is the whole reason for using it."""
        m = _quad(0.0)
        out = m + _FakeMorph([2, 2, 2], [[0, 0, 1.0]] * 3)
        np.testing.assert_allclose(out.points[2][2], 3.0)

    def test_subtract_morph_is_the_mirror(self):
        m = _quad(0.0)
        mo = _FakeMorph([1], [[0, 0, 5.0]])
        np.testing.assert_allclose((m + mo - mo).points, m.points)

    def test_scaled_morph_composes(self):
        """The mPyBlendShape shape: mesh + morph * weight."""
        from mpynode._api2.morph import Morph
        m = _quad(0.0)
        smile = Morph("smile", offsets=np.array([[0.0, 0.0, 4.0]]),
                      indices=np.array([2]))
        out = m + smile * 0.5
        np.testing.assert_allclose(out.points[2][2], 2.0)

    def test_a_real_Morph_hits_the_duck_type_branch(self):
        from mpynode._api2.morph import Morph
        from mpynode._api2.geometry import _looks_like_morph
        self.assertTrue(_looks_like_morph(
            Morph("x", offsets=np.zeros((1, 3)), indices=np.array([0]))))

    def test_a_mesh_is_not_mistaken_for_a_morph(self):
        from mpynode._api2.geometry import _looks_like_morph
        self.assertFalse(_looks_like_morph(_quad(0.0)))

    def test_out_of_range_morph_index_raises(self):
        m = _quad(0.0)
        with self.assertRaises(ValueError):
            _ = m + _FakeMorph([99], [[0, 0, 1.0]])

    def test_mismatched_index_offset_lengths_raise(self):
        m = _quad(0.0)
        with self.assertRaises(ValueError):
            _ = m + _FakeMorph([0, 1], [[0, 0, 1.0]])


class TestMeshScalarOps(unittest.TestCase):

    def test_add_a_vector_offsets_every_point(self):
        out = _quad(0.0) + np.array([0.0, 0.0, 3.0])
        np.testing.assert_allclose(out.points[:, 2], 3.0)

    def test_multiply_scales_the_point_field(self):
        np.testing.assert_allclose((_quad(0.0) * 2.0).points[1], [2, 0, 0])

    def test_rmul_from_the_left(self):
        np.testing.assert_allclose((2.0 * _quad(0.0)).points[1], [2, 0, 0])

    def test_numpy_scalar_defers_to_our_operator(self):
        """__array_ufunc__ = None -- otherwise numpy iterates the Mesh."""
        out = np.float64(2.0) * _quad(0.0)
        np.testing.assert_allclose(out.points[1], [2, 0, 0])

    def test_mesh_times_mesh_is_an_explicit_error(self):
        with self.assertRaises(TypeError):
            _ = _quad(0.0) * _quad(1.0)


class TestSubMesh(unittest.TestCase):

    def test_from_faces_compacts_points_and_renumbers(self):
        sub = _grid2().from_faces([1])
        self.assertEqual(sub.points.shape, (4, 3))
        np.testing.assert_array_equal(sub.counts, [4])
        np.testing.assert_array_equal(sub.indices, [0, 1, 2, 3])
        np.testing.assert_allclose(sub.points[0], [2, 0, 0])

    def test_from_faces_exclude_keeps_the_complement(self):
        sub = _grid2().from_faces([1], exclude=True)
        np.testing.assert_allclose(sub.points[0], [0, 0, 0])
        np.testing.assert_array_equal(sub.counts, [4])

    def test_from_faces_out_of_range_is_ignored_not_fatal(self):
        sub = _grid2().from_faces([0, 99])
        np.testing.assert_array_equal(sub.counts, [4])

    def test_from_faces_empty_selection_yields_an_empty_mesh(self):
        sub = _grid2().from_faces([])
        self.assertEqual(sub.points.shape, (0, 3))
        self.assertEqual(sub.indices.size, 0)

    def test_from_vertices_contained_requires_every_corner(self):
        # verts 0..3 are exactly face 0; face 1 has none of them
        sub = _grid2().from_vertices([0, 1, 2, 3], contained=True)
        np.testing.assert_array_equal(sub.counts, [4])
        np.testing.assert_allclose(sub.points[0], [0, 0, 0])

    def test_from_vertices_contained_false_matches_any_corner(self):
        # one corner of each face -> both faces come back
        sub = _grid2().from_vertices([0, 4], contained=False)
        np.testing.assert_array_equal(sub.counts, [4, 4])

    def test_partial_containment_excludes_the_face(self):
        sub = _grid2().from_vertices([0, 1], contained=True)
        self.assertEqual(sub.counts.size, 0)


class TestFromTag(unittest.TestCase):

    def _tagged(self):
        m = _grid2()
        m._tags = {
            "rightHalf": {"type": "face", "indices": np.array([1])},
            "leftVerts": {"type": "vertex", "indices": np.array([0, 1, 2, 3])},
            "someEdges": {"type": "edge", "indices": np.array([0])},
        }
        return m

    def test_face_tag_routes_through_from_faces(self):
        sub = self._tagged().from_tag("rightHalf")
        np.testing.assert_array_equal(sub.counts, [4])
        np.testing.assert_allclose(sub.points[0], [2, 0, 0])

    def test_vertex_tag_routes_through_from_vertices(self):
        sub = self._tagged().from_tag("leftVerts")
        np.testing.assert_array_equal(sub.counts, [4])
        np.testing.assert_allclose(sub.points[0], [0, 0, 0])

    def test_region_is_polymorphic_which_is_why_from_tag_exists(self):
        """region() gives INDICES for a face tag but POINTS for a vertex tag.
        Feeding a vertex tag's region() to from_faces is the silent-garbage
        path from_tag was added to close."""
        m = self._tagged()
        np.testing.assert_array_equal(m.region("rightHalf"), [1])
        self.assertEqual(np.asarray(m.region("leftVerts")).shape, (4, 3))

    def test_missing_tag_raises_and_names_what_is_available(self):
        with self.assertRaises(KeyError) as cm:
            self._tagged().from_tag("nope")
        self.assertIn("leftVerts", str(cm.exception))

    def test_unsupported_tag_type_raises(self):
        with self.assertRaises(ValueError):
            self._tagged().from_tag("someEdges")


class TestNurbsCurveConcat(unittest.TestCase):

    def _curve(self, x=0.0, degree=3, periodic=False):
        from mpynode._api2.geometry import NurbsCurve
        pts = np.array([[x, 0, 0], [x + 1, 1, 0], [x + 2, 1, 0], [x + 3, 0, 0]],
                       dtype=np.float64)
        return NurbsCurve(points=pts, degree=degree, periodic=periodic)

    def test_concatenates_control_points(self):
        c = self._curve(0.0) + self._curve(10.0)
        self.assertEqual(c.points.shape, (8, 3))
        np.testing.assert_allclose(c.points[4], [10, 0, 0])

    def test_knots_are_dropped_for_rebuild(self):
        a = self._curve(0.0)
        a.knots = np.linspace(0.0, 1.0, 6)
        self.assertIsNone((a + self._curve(10.0)).knots)

    def test_add_does_not_mutate_the_left_operand(self):
        a = self._curve(0.0)
        _ = a + self._curve(10.0)
        self.assertEqual(a.points.shape, (4, 3))

    def test_degree_mismatch_raises(self):
        with self.assertRaises(ValueError):
            _ = self._curve(degree=3) + self._curve(degree=1)

    def test_periodic_mismatch_raises(self):
        with self.assertRaises(ValueError):
            _ = self._curve(periodic=False) + self._curve(periodic=True)

    def test_adding_a_non_curve_raises(self):
        with self.assertRaises(TypeError):
            _ = self._curve() + _quad(0.0)

    def test_sum_works(self):
        total = sum([self._curve(0.0), self._curve(10.0), self._curve(20.0)])
        self.assertEqual(total.points.shape, (12, 3))


class TestAttachedMeshEdits(unittest.TestCase):
    """The silent-failure path. An ATTACHED mesh holds a live data MObject and
    ``to_mobject()`` passes it straight through -- so an in-place edit that
    forgets to ``_cow_detach`` first mutates a cache that is then thrown away,
    and the node quietly outputs the UNMODIFIED input."""

    def _attached_cube(self):
        import maya.cmds as mc
        import maya.api.OpenMaya as om
        from mpynode._api2.geometry import Mesh
        mc.file(new=True, force=True)
        cube = mc.polyCube(constructionHistory=False)[0]
        sel = om.MSelectionList()
        sel.add(cube)
        dag = sel.getDagPath(0)
        dag.extendToShape()
        plug = om.MFnDependencyNode(dag.node()).findPlug("outMesh", False)
        return Mesh._attach(plug.asMObject())

    # these assert on _attached + the numpy channels instead of round-tripping
    # through to_mobject(). build_mesh_data returns a data MObject owned by a
    # function set that goes out of scope inside it: fine in production, where
    # the result goes straight into a datablock handle, but holding it across
    # statements and re-wrapping it in an MFnMesh reads freed memory (wrong
    # values, then a hard crash). `_attached is False` IS the property under
    # test: to_mobject() passes the original data through only while attached.

    def test_attached_mesh_reads_its_points(self):
        self.assertEqual(self._attached_cube().points.shape, (8, 3))

    def test_iadd_morph_on_an_attached_mesh_detaches(self):
        m = self._attached_cube()
        before = float(m.points[0][1])
        m += _FakeMorph([0], [[0.0, 10.0, 0.0]])
        self.assertFalse(m.__dict__.get("_attached"),
                         "in-place edit must detach or to_mobject() discards it")
        self.assertIsNone(m.__dict__.get("_data"))
        self.assertAlmostEqual(float(m.points[0][1]), before + 10.0, places=5)

    def test_union_on_an_attached_mesh_detaches_and_grows(self):
        m = self._attached_cube()
        m += _quad(20.0)
        self.assertFalse(m.__dict__.get("_attached"))
        self.assertEqual(m.points.shape, (12, 3))
        self.assertEqual(int(m.counts.size), 7)      # 6 cube faces + 1 quad
        self.assertEqual(int(m.indices.max()), 11)   # quad rebased past vert 7

    def test_isub_mesh_on_an_attached_mesh_detaches(self):
        from mpynode._api2.geometry import Mesh
        m = self._attached_cube()
        face0 = m.points[m.indices[:4]]                 # one cube face
        m -= Mesh(points=face0, counts=np.array([4]),
                  indices=np.arange(4))
        self.assertFalse(m.__dict__.get("_attached"),
                         "in-place edit must detach or to_mobject() discards it")
        self.assertIsNone(m.__dict__.get("_data"))
        self.assertEqual(int(m.counts.size), 5)         # 6 cube faces - 1

    def test_from_tag_and_arithmetic_leave_the_source_attached(self):
        m = self._attached_cube()
        _ = m + _quad(0.0)                      # pure form copies first
        self.assertTrue(m.__dict__.get("_attached"))


class TestNurbsSurfaceHasNoDunders(unittest.TestCase):
    """Deliberately none -- a surface is a (u,v) CV grid and concatenating CVs
    has no meaning that preserves the grid. Pinned so nobody adds one by
    reflex."""

    def test_no_arithmetic_dunders(self):
        from mpynode._api2.geometry import NurbsSurface
        for d in ("__add__", "__iadd__", "__sub__", "__mul__"):
            self.assertIs(getattr(NurbsSurface, d, None),
                          getattr(object, d, None), d)


class TestGeometryDisplayName(unittest.TestCase):
    """``Mesh("pCubeShape1")`` -- the identity a geometry object shows when
    something prints it (the Watch tab, a bare ``print``).

    The object holds datablock DATA, which has no identity of its own, so the
    name has to come from the plug it was decoded off. What is worth pinning:

      * it resolves LAZILY and is cached -- a repr on the watch path runs every
        compute, so re-walking the DG each time would be a real cost;
      * an object with no source keeps its STRUCTURAL repr rather than
        inventing a name (a value mesh you built has no shape behind it);
      * ``name`` must win over the ``MFnMesh.name`` that ``__getattr__`` would
        otherwise delegate to -- that one is built from geometry DATA, so
        calling it raises "Object does not exist".
    """

    def _connected_mesh(self):
        import maya.cmds as mc
        import maya.api.OpenMaya as om
        from mpynode._api2 import helpers as H

        mc.file(new=True, force=True)
        cube = mc.polyCube(constructionHistory=False)[0]
        shape = mc.listRelatives(cube, shapes=True)[0]
        dst = mc.createNode("transform", name="probe")
        mc.addAttr(dst, longName="inGeo", dataType="mesh")
        mc.connectAttr(shape + ".outMesh", dst + ".inGeo", force=True)

        sel = om.MSelectionList()
        sel.add(dst + ".inGeo")
        return H.read_plug_value(sel.getPlug(0), "mesh"), shape

    def test_a_connected_mesh_reprs_with_its_source_shape_name(self):
        mesh, shape = self._connected_mesh()
        self.assertEqual(mesh.name, shape)
        self.assertEqual(repr(mesh), 'Mesh("%s")' % shape)

    def test_the_name_is_resolved_once_and_cached(self):
        import maya.api.OpenMaya as om
        import mpynode._api2.geometry as G

        mesh, _shape = self._connected_mesh()
        calls = []
        orig = G.om.MFnDependencyNode

        class Counting(orig):
            def __init__(self, *a, **k):
                calls.append(1)
                super().__init__(*a, **k)

        G.om.MFnDependencyNode = Counting
        try:
            for _ in range(5):
                repr(mesh)
        finally:
            G.om.MFnDependencyNode = orig
        self.assertEqual(len(calls), 1, "name must resolve once, then cache")

    def test_a_value_mesh_keeps_its_structural_repr(self):
        from mpynode._api2.geometry import Mesh
        m = Mesh(points=np.zeros((4, 3)), counts=np.array([4]),
                 indices=np.arange(4))
        self.assertIsNone(m.name)
        self.assertEqual(repr(m), "<Mesh value verts=4>")

    def test_name_shadows_the_broken_mfn_delegation(self):
        # before this property, mesh.name handed back MFnMesh.name, a bound
        # method built from DATA that raised when called. None is better than
        # an attribute that only ever explodes.
        m = self._attached_no_source()
        self.assertIsNone(m.name)
        self.assertNotIn("verts", 'Mesh("x")')      # guard the format itself

    def _attached_no_source(self):
        import maya.cmds as mc
        import maya.api.OpenMaya as om
        from mpynode._api2.geometry import Mesh

        mc.file(new=True, force=True)
        cube = mc.polyCube(constructionHistory=False)[0]
        sel = om.MSelectionList()
        sel.add(cube)
        dag = sel.getDagPath(0)
        dag.extendToShape()
        plug = om.MFnDependencyNode(dag.node()).findPlug("outMesh", False)
        return Mesh._attach(plug.asMObject())      # no source_plug


if __name__ == "__main__":
    unittest.main()
