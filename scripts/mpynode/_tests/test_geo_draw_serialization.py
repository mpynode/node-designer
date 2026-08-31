"""Geometry + draw objects are interchangeable OUTSIDE Maya.

Two formats, one payload:

  * **pickle** -- ``__reduce__`` on the geometry wrappers. An ATTACHED wrapper
    (what an input plug hands you) holds a live geometry DATA MObject and an
    ``MFn*`` function set, neither of which is picklable; it must materialize
    its channels and come back DETACHED but data-identical, still marshallable
    to an output plug. Draw items are plain objects over numpy, so they pickle
    natively -- pinned here so a future field can't silently break it.
  * **JSON** -- ``to_json()`` / ``from_json()``: no numpy, no Maya types, so a
    drawing or a mesh can be written to a file and read in a plain interpreter.

The draw JSON codec is generic (it walks ``__dict__``), so these tests cover
EVERY Draw type by construction rather than by enumeration.
"""
from __future__ import annotations

import json
import pickle
import unittest

from ._setup import standalone_init

standalone_init()

import maya.cmds as mc
import maya.api.OpenMaya as om
import numpy as np

from mpynode._api2.geometry import (
    Mesh, NurbsCurve, NurbsSurface, UVSet, build_mesh_data, geometry_from_json)
from mpynode._common.draw.draw_types import (
    DrawBox, DrawCircle, DrawCone, DrawCurve, DrawCylinder, DrawLines,
    DrawMesh, DrawPoints, DrawSphere, DrawText, draw_from_json, to_commands)


def _plug_data(node, attr):
    sel = om.MSelectionList()
    sel.add(node + "." + attr)
    return sel.getPlug(0).asMObject(), sel.getPlug(0)


def _value_mesh():
    m = Mesh(points=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
             counts=[4], indices=[0, 1, 2, 3],
             normals=[[0, 0, 1]] * 4)
    m._tags = {"lid": {"type": "vertex", "indices": np.array([0, 2])}}
    m._uv_sets = [UVSet("map1", [[0, 0], [1, 0], [1, 1], [0, 1]], [4],
                        [0, 1, 2, 3])]
    return m


# Every Draw type, each with a non-default option set so the round trip has
# something to lose.
def _draw_items():
    return [
        DrawCircle(center=(1, 2, 3), radius=2.0, color=(1, 0, 0), filled=True),
        DrawSphere(center=(0, 1, 0), radius=0.5),
        DrawBox(center=(0, 0, 0), radius=1.5, filled=False),
        DrawCone(center=(2, 0, 0), radius=1.0),
        DrawCylinder(center=(3, 0, 0), radius=1.0),
        DrawLines([[0, 0, 0], [1, 1, 1]], [[1, 0, 0], [2, 1, 1]],
                  color=(0, 1, 0), world_space=True),
        DrawCurve([[0, 0, 0], [1, 1, 0], [2, 0, 0]], closed=True,
                  color=(0, 0, 1)),
        DrawPoints([[0, 0, 0], [1, 1, 1]], size=6.0),
        DrawText("hello", (1, 1, 1), size=14.0, screen_space=True),
        DrawMesh([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
                 counts=[4], indices=[0, 1, 2, 3], color=(0.2, 0.4, 0.8),
                 precise_hover=True, cull_backfaces=True),
    ]


class _DrawRoundTripMixin:
    def assertSameDrawing(self, a, b, msg=""):
        """Two drawings are equal iff they produce the same ordered commands --
        the only thing the renderer ever sees."""
        ca, cb = to_commands(a), to_commands(b)
        self.assertEqual([c["slot"] for c in ca], [c["slot"] for c in cb],
                         "slot order changed %s" % msg)
        for x, y in zip(ca, cb):
            self.assertEqual(sorted(x["buffer"]), sorted(y["buffer"]),
                             "buffer keys changed %s" % msg)
            for k in x["buffer"]:
                u, v = x["buffer"][k], y["buffer"][k]
                if isinstance(u, np.ndarray) or isinstance(v, np.ndarray):
                    np.testing.assert_allclose(
                        np.asarray(u, dtype=float), np.asarray(v, dtype=float),
                        err_msg="%r changed %s" % (k, msg))
                else:
                    self.assertEqual(u, v, "%r changed %s" % (k, msg))


class TestValueGeometryPickle(unittest.TestCase):
    """A detached (value) wrapper round-trips every channel."""

    def test_mesh_pickle_keeps_every_channel(self):
        m = _value_mesh()
        r = pickle.loads(pickle.dumps(m))
        np.testing.assert_allclose(r.points, m.points)
        np.testing.assert_array_equal(r.counts, m.counts)
        np.testing.assert_array_equal(r.indices, m.indices)
        np.testing.assert_allclose(r.normals, m.normals)
        np.testing.assert_array_equal(r.component_tags["lid"]["indices"], [0, 2])
        self.assertEqual(len(r.uv_sets), 1)
        np.testing.assert_allclose(r.uv_sets[0].points, m.uv_sets[0].points)

    def test_curve_pickle_keeps_every_channel(self):
        c = NurbsCurve(points=[[0, 0, 0], [1, 2, 0], [3, 1, 0], [4, 0, 0]],
                       degree=3, periodic=False)
        r = pickle.loads(pickle.dumps(c))
        np.testing.assert_allclose(r.points, c.points)
        self.assertEqual(r.degree, c.degree)
        self.assertEqual(r.periodic, c.periodic)

    def test_surface_pickle_keeps_every_channel(self):
        s = NurbsSurface(points=[[float(i), float(j), 0.0]
                                 for i in range(4) for j in range(4)],
                         num_u=4, num_v=4, degree_u=3, degree_v=3)
        r = pickle.loads(pickle.dumps(s))
        np.testing.assert_allclose(r.points, s.points)
        self.assertEqual((r.num_u, r.num_v), (s.num_u, s.num_v))
        self.assertEqual((r.degree_u, r.degree_v), (s.degree_u, s.degree_v))


class TestAttachedGeometryPickle(unittest.TestCase):
    """The case the plain-arrays path does NOT cover: a wrapper holding a live
    Maya DATA MObject + MFn. Pickling must materialize and sever, never raise."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _attached_cube(self):
        cube = mc.polyCube(name="pickleCube", constructionHistory=False)[0]
        shape = mc.listRelatives(cube, shapes=True, fullPath=True)[0]
        data, plug = _plug_data(shape, "outMesh")
        return Mesh._attach(data, plug)

    def test_attached_mesh_pickles_as_a_detached_value(self):
        m = self._attached_cube()
        self.assertTrue(m.__dict__.get("_attached"), "fixture is not attached")
        self.assertIsNotNone(m.fn, "fixture has no live function set")

        r = pickle.loads(pickle.dumps(m))
        self.assertFalse(r.__dict__.get("_attached"),
                         "an unpickled mesh must be a detached value")
        self.assertIsNone(r.__dict__.get("_data"),
                          "the Maya DATA MObject must not survive a pickle")
        np.testing.assert_allclose(r.points, m.points)
        np.testing.assert_array_equal(r.counts, m.counts)
        np.testing.assert_array_equal(r.indices, m.indices)
        np.testing.assert_allclose(r.normals, m.normals)

    def test_attached_mesh_uv_sets_survive(self):
        # copy() drops UV sets (they are not marshalled to a plug); losing them
        # on a serialization round trip would be silent data loss.
        m = self._attached_cube()
        self.assertTrue(m.uv_sets, "fixture cube has no UVs")
        r = pickle.loads(pickle.dumps(m))
        self.assertEqual(len(r.uv_sets), len(m.uv_sets))
        np.testing.assert_allclose(r.uv_sets[0].points, m.uv_sets[0].points)

    def test_unpickled_mesh_still_marshals_to_an_output(self):
        m = self._attached_cube()
        n = m.points.shape[0]
        r = pickle.loads(pickle.dumps(m))
        out = build_mesh_data(r)
        self.assertFalse(out.isNull())
        self.assertEqual(om.MFnMesh(out).numVertices, n)

    def test_pickle_stream_carries_no_maya_types(self):
        blob = pickle.dumps(self._attached_cube())
        self.assertNotIn(b"OpenMaya", blob)
        self.assertNotIn(b"MObject", blob)

    def test_attached_curve_pickles_as_a_detached_value(self):
        crv = mc.curve(p=[(0, 0, 0), (1, 2, 0), (3, 1, 0), (4, 0, 0)], degree=3)
        shape = mc.listRelatives(crv, shapes=True, fullPath=True)[0]
        data, plug = _plug_data(shape, "local")
        c = NurbsCurve._attach(data, plug)
        r = pickle.loads(pickle.dumps(c))
        self.assertFalse(r.__dict__.get("_attached"))
        np.testing.assert_allclose(r.points, c.points)
        self.assertEqual(r.degree, c.degree)
        np.testing.assert_allclose(r.knots, c.knots)


class TestGeometryJson(unittest.TestCase):
    """JSON is the portable form: text in, text out, no numpy, no Maya."""

    def test_mesh_json_round_trip(self):
        m = _value_mesh()
        r = geometry_from_json(json.dumps(m.to_json()))
        np.testing.assert_allclose(r.points, m.points)
        np.testing.assert_array_equal(r.indices, m.indices)
        np.testing.assert_array_equal(r.component_tags["lid"]["indices"], [0, 2])
        np.testing.assert_allclose(r.uv_sets[0].points, m.uv_sets[0].points)

    def test_curve_json_round_trip(self):
        c = NurbsCurve(points=[[0, 0, 0], [1, 2, 0], [3, 1, 0], [4, 0, 0]])
        r = geometry_from_json(json.dumps(c.to_json()))
        np.testing.assert_allclose(r.points, c.points)
        self.assertEqual(r.degree, c.degree)

    def test_surface_json_round_trip(self):
        s = NurbsSurface(points=[[float(i), float(j), 0.0]
                                 for i in range(4) for j in range(4)],
                         num_u=4, num_v=4)
        r = geometry_from_json(json.dumps(s.to_json()))
        np.testing.assert_allclose(r.points, s.points)
        self.assertEqual((r.num_u, r.num_v), (s.num_u, s.num_v))

    def test_uv_set_json_round_trip(self):
        u = _value_mesh().uv_sets[0]
        r = geometry_from_json(json.dumps(u.to_json()))
        self.assertEqual(r.name, u.name)
        np.testing.assert_allclose(r.points, u.points)

    def test_to_json_is_json_serializable(self):
        # the whole point: no numpy scalars/arrays leak into the payload
        for obj in (_value_mesh(),
                    NurbsCurve(points=[[0, 0, 0], [1, 1, 1]], degree=1),
                    NurbsSurface(points=[[0., 0., 0.]] * 16, num_u=4, num_v=4)):
            json.dumps(obj.to_json())      # must not raise

    def test_unknown_type_is_rejected(self):
        with self.assertRaises(ValueError):
            geometry_from_json({"type": "Lattice"})


class TestDrawPickle(unittest.TestCase, _DrawRoundTripMixin):
    def test_every_draw_type_pickles(self):
        for item in _draw_items():
            with self.subTest(item=type(item).__name__):
                self.assertSameDrawing(item, pickle.loads(pickle.dumps(item)))

    def test_group_pickle_preserves_authoring_order(self):
        items = _draw_items()
        group = items[0] + items[8] + items[9]
        self.assertSameDrawing(group, pickle.loads(pickle.dumps(group)))


class TestDrawJson(unittest.TestCase, _DrawRoundTripMixin):
    def test_every_draw_type_round_trips_through_json(self):
        for item in _draw_items():
            with self.subTest(item=type(item).__name__):
                self.assertSameDrawing(
                    item, draw_from_json(json.dumps(item.to_json())))

    def test_group_json_preserves_authoring_order(self):
        items = _draw_items()
        group = items[9] + items[0] + items[8]
        self.assertSameDrawing(group, draw_from_json(json.dumps(group.to_json())))

    def test_a_list_of_items_round_trips_as_a_list(self):
        items = [_draw_items()[9], _draw_items()[8], _draw_items()[0]]
        back = draw_from_json(json.dumps([i.to_json() for i in items]))
        self.assertIsInstance(back, list)
        self.assertSameDrawing(items, back)

    def test_numpy_dtype_survives(self):
        # a float32 point array must not silently come back as float64 (or as
        # a Python list, which would break the flush)
        item = DrawPoints(np.array([[0, 0, 0], [1, 1, 1]], dtype=np.float32))
        back = draw_from_json(json.dumps(item.to_json()))
        for k, v in item.__dict__.items():
            if isinstance(v, np.ndarray):
                self.assertEqual(back.__dict__[k].dtype, v.dtype,
                                 "dtype of %s changed" % k)

    def test_unknown_type_is_rejected(self):
        with self.assertRaises(ValueError):
            draw_from_json({"type": "DrawHologram", "state": {}})


if __name__ == "__main__":
    unittest.main()
