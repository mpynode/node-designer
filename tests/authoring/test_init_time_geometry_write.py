"""Init-time (no DataBlock) geometry writes through ``plug_write``.

``_write_plug_init_time`` used to raise ``NotImplementedError`` for every
geometry typed attr. The blocker was never the marshalling -- ``_api2.geometry``
already builds ``MFn*Data`` objects -- it was the API BOUNDARY: ``plug_write``
holds an api1 ``MPlug`` and api1's ``setMObject`` rejects an api2 ``MObject``
outright, so the write has to be re-issued on the api2 side.

What is easy to get wrong, and is pinned here:

  * the api1 -> api2 hop is by NAME, and a DAG plug's ``name()`` uses the node's
    SHORT name. Two shapes called ``dup`` under different parents both resolve,
    so a naive hop can silently write to the WRONG node
    (``test_duplicate_dag_short_names_...``).
  * kSubdSurface / kLattice still have no marshaller on either path and must
    keep raising rather than half-writing.
"""
from __future__ import annotations

import unittest

import numpy as np

from tests import _setup


def setUpModule():
    _setup.standalone_init()
    _setup.ensure_plugins_loaded()


def _plug_and_attr(node_name, attr_name):
    """The api1 (MPlug, attribute MObject) pair ``_write_plug`` is handed."""
    import maya.OpenMaya as om1

    sel = om1.MSelectionList()
    sel.add(node_name)
    obj = om1.MObject()
    sel.getDependNode(0, obj)
    attr = om1.MFnDependencyNode(obj).attribute(attr_name)
    return om1.MPlug(obj, attr), attr


def _write(node_name, attr_name, value):
    """Init-time write: no datablock -> ``_write_plug_init_time``."""
    from mpynode._common.plugs.plug_write import _write_plug

    plug, attr = _plug_and_attr(node_name, attr_name)
    _write_plug(plug, attr, value)


def _read_back(node_name, attr_name):
    import maya.api.OpenMaya as om2

    sel = om2.MSelectionList()
    sel.add("%s.%s" % (node_name, attr_name))
    return sel.getPlug(0).asMObject()


def _vert_count(node_name, attr_name):
    """Vertices on the mesh sitting on a plug, or None when it carries none.

    An EMPTY geometry plug does not read back as a null MObject -- Maya raises
    "Unexpected Internal Failure" -- so the miss has to be caught."""
    from mpynode._api2.geometry import Mesh

    try:
        data = _read_back(node_name, attr_name)
    except Exception:
        return None
    if data.isNull():
        return None
    return int(Mesh._attach(data).points.shape[0])


def _mpy_node_with(attr_name, attr_type, direction="output"):
    import maya.cmds as mc
    import mpynode

    mc.file(new=True, force=True)
    n = mc.createNode("mPyNode", name="initGeoWrite")
    w = mpynode.wrap_node(n)
    if direction == "output":
        w.add_output_attr(attr_name, attr_type)
    else:
        w.add_input_attr(attr_name, attr_type)
    return n


def _quad():
    from mpynode._api2.geometry import Mesh
    return Mesh(points=np.array([[0., 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]),
                counts=np.array([4]), indices=np.array([0, 1, 2, 3]))


class TestInitTimeGeometryWrite(unittest.TestCase):

    def test_mesh_object_lands_on_the_plug(self):
        from mpynode._api2.geometry import Mesh

        n = _mpy_node_with("outGeo", "mesh")
        _write(n, "outGeo", _quad())
        data = _read_back(n, "outGeo")
        self.assertFalse(data.isNull())
        back = Mesh._attach(data)
        np.testing.assert_allclose(back.points, _quad().points)
        np.testing.assert_array_equal(back.counts, [4])

    def test_mesh_input_attr_too(self):
        from mpynode._api2.geometry import Mesh

        n = _mpy_node_with("inGeo", "mesh", direction="input")
        _write(n, "inGeo", _quad())
        self.assertEqual(Mesh._attach(_read_back(n, "inGeo")).points.shape,
                         (4, 3))

    def test_curve_object_lands_on_the_plug(self):
        import maya.api.OpenMaya as om2
        from mpynode._api2.geometry import NurbsCurve

        n = _mpy_node_with("outCrv", "nurbsCurve")
        cvs = np.array([[0., 0, 0], [1, 1, 0], [2, 0, 0], [3, 1, 0]])
        _write(n, "outCrv", NurbsCurve(points=cvs, degree=3))
        data = _read_back(n, "outCrv")
        self.assertFalse(data.isNull())
        self.assertEqual(om2.MFnNurbsCurve(data).numCVs, 4)

    def test_surface_object_lands_on_the_plug(self):
        import maya.api.OpenMaya as om2
        from mpynode._api2.geometry import NurbsSurface

        n = _mpy_node_with("outSrf", "nurbsSurface")
        grid = np.zeros((4, 4, 3))
        for i in range(4):
            for j in range(4):
                grid[i, j] = (float(i), float(j), 0.0)
        _write(n, "outSrf", NurbsSurface(points=grid, degree_u=3, degree_v=3))
        data = _read_back(n, "outSrf")
        self.assertFalse(data.isNull())
        self.assertEqual(om2.MFnNurbsSurface(data).numCVsInU, 4)

    def test_a_duck_typed_value_bucket_marshals(self):
        from types import SimpleNamespace
        from mpynode._api2.geometry import Mesh

        n = _mpy_node_with("outGeo", "mesh")
        _write(n, "outGeo", SimpleNamespace(
            points=np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]]),
            counts=np.array([3]), indices=np.array([0, 1, 2])))
        self.assertEqual(Mesh._attach(_read_back(n, "outGeo")).points.shape,
                         (3, 3))

    def test_a_finished_data_mobject_passes_through(self):
        from mpynode._api2.geometry import Mesh

        n = _mpy_node_with("outGeo", "mesh")
        _write(n, "outGeo", _quad().to_mobject())
        self.assertEqual(Mesh._attach(_read_back(n, "outGeo")).points.shape,
                         (4, 3))

    def test_a_non_geometry_value_is_a_clear_error(self):
        n = _mpy_node_with("outGeo", "mesh")
        with self.assertRaises(AttributeError) as cm:
            _write(n, "outGeo", "not a mesh")
        self.assertIn("mesh plug", str(cm.exception))

    def test_duplicate_dag_short_names_write_to_the_RIGHT_node(self):
        """A DAG plug's name() is the SHORT name; two shapes can share it.

        Both writes land on ONE node if the api1 -> api2 hop resolves by short
        name, so each shape is given a DIFFERENT vertex count and both are read
        back."""
        import maya.cmds as mc
        from mpynode._api2.geometry import Mesh

        mc.file(new=True, force=True)
        mc.createNode("transform", name="grpA")
        mc.createNode("transform", name="grpB")
        mc.createNode("mesh", name="dup", parent="grpA")
        mc.createNode("mesh", name="dup", parent="grpB")
        tri = Mesh(points=np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0]]),
                   counts=np.array([3]), indices=np.array([0, 1, 2]))
        _write("|grpA|dup", "inMesh", tri)
        _write("|grpB|dup", "inMesh", _quad())
        self.assertEqual(_vert_count("|grpA|dup", "inMesh"), 3)
        self.assertEqual(_vert_count("|grpB|dup", "inMesh"), 4)

    def test_subd_and_lattice_still_raise(self):
        """No marshaller exists on either path -- these must not half-write."""
        import maya.cmds as mc

        for node_type, attr in (("subdiv", "create"),
                                ("lattice", "latticeInput")):
            with self.subTest(node_type=node_type):
                mc.file(new=True, force=True)
                n = mc.createNode(node_type)
                with self.assertRaises(NotImplementedError):
                    _write(n, attr, _quad())


if __name__ == "__main__":
    unittest.main()
