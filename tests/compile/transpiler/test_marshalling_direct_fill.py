"""Codegen rule 2: marshalling moves data once.

Three shapes the AI optimizer kept removing by hand (8 "direct-fill" plus 3
"bulk constructor" accepted rounds in the shipped ledgers) are now what the
transpiler emits:

* ``nd::from_data`` has an rvalue overload that ADOPTS the vector; every
  marshalling temporary (``_tmp`` / ``_gt`` / ``_tgt`` / ``_tmpn`` / ``_uv`` /
  ``skinW``) is handed over with ``std::move`` instead of being copied a
  second time.
* geometry output buffers are filled by index into a resized vector, not
  ``push_back`` one element at a time.
* the mesh / curve / surface GENERATORS (emit_geo) and the typed geo I/O
  helpers (emit_geo_io: ``nd_build_mesh`` / ``nd_read_mesh``) hand Maya their
  point / count / index / normal / colour / knot / UV arrays through the bulk
  constructors, not one ``append()`` per element; ``nd_read_mesh`` copies
  topology with ``MIntArray::get``.

Pure data movement: the values, their order and their casts are unchanged.
"""

from __future__ import annotations

import os
import re
import unittest

from mpynode.native import compiler as codegen
from tests import _paths

_RUNTIME_H = os.path.join(_paths.ROOT, "scripts", "mpynode", "native", "compiler",
                          "nd_runtime.h")


def _spec(compute, *, base="MPxNode", mpy_type="mPyNode", inputs=None, outputs=None):
    return {
        "suggested": {"node_type_name": "marshalTest", "class_name": "MarshalTest",
                      "type_id": "0x000701a6", "mpx_base": base},
        "mpy_type":    mpy_type,
        "compute":     compute,
        "init":        "",
        "inputs":      dict(inputs or {}),
        "outputs":     dict(outputs or {}),
        "portability": {"portable": True, "blockers": [], "warnings": []},
    }


def _no_appends(block):
    """Every ``.append(`` left in ``block`` -- the bulk-constructor rule says none."""
    return [ln.strip() for ln in block.splitlines() if ".append(" in ln]


class TestRuntimeOverload(unittest.TestCase):
    def test_from_data_adopts_an_rvalue_vector(self):
        with open(_RUNTIME_H, encoding="utf-8") as fh:
            h = fh.read()
        self.assertIn("inline Array<T> from_data(std::vector<T>&& flat, const Shape& sh)", h)
        self.assertIn("std::make_shared<std::vector<T>>(std::move(flat))", h)
        # the copying overload stays for callers that keep their vector
        self.assertIn("inline Array<T> from_data(const std::vector<T>& flat, const Shape& sh)", h)


class TestInputsAreMoved(unittest.TestCase):
    def test_vector_array_input_moves_its_temporary(self):
        spec = _spec("mesh = self.outputGeometry[0]\n"
                     "rest = mesh.getPoints()\n"
                     "mesh.setPoints(rest + self.offsets)\n",
                     base="MPxDeformerNode", mpy_type="mPyDeformer",
                     inputs={"offsets": {"type": "vector", "is_array": True}})
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("lowered deform (no port)", cpp)
        self.assertIn("nd::from_data<double>(std::move(_tmp), {(int64_t)in_aOffsets.size(), 3});", cpp)
        # the harvest temporary too
        self.assertIn("nd::from_data<double>(std::move(_tmp), {(int64_t)n, 3});", cpp)

    def test_no_marshalling_temporary_is_copied(self):
        spec = _spec("mesh = self.outputGeometry[0]\n"
                     "rest = mesh.getPoints()\n"
                     "mesh.setPoints(rest * self.gain)\n",
                     base="MPxDeformerNode", mpy_type="mPyDeformer",
                     inputs={"gain": {"type": "double", "is_array": False}})
        cpp   = codegen.generate_cpp(spec, for_port=True)
        stale = re.findall(r"nd::from_data<[a-z0-9_]+>\((_tmp|_gt|_tgt|_tmpn|_uv|skinW),", cpp)
        self.assertEqual(stale, [])


class TestGeneratorOutputIsDirectFill(unittest.TestCase):
    """A mesh GENERATOR (mPyMesh) goes through emit_geo: nd buffers -> vectors
    -> MFnMesh::create."""

    def setUp(self):
        self.cpp = codegen.generate_cpp(_spec(
            "import numpy as np\n"
            "self.points = np.zeros((4, 3), dtype=float) + self.size\n"
            "self.counts = np.array([4], dtype=int)\n"
            "self.indices = np.array([0, 1, 2, 3], dtype=int)\n",
            mpy_type="mPyMesh",
            inputs={"size": {"type": "double", "is_array": False}}), for_port=True)

    def test_point_and_index_buffers_are_resized_then_indexed(self):
        c = self.cpp
        self.assertIn(".resize((size_t)_n);", c)
        self.assertRegex(c, r"\w+\[\(size_t\)_i\] = MPoint\(\(\*_o\.data\)\[_i\*3\+0\]")
        self.assertRegex(c, r"\w+\[\(size_t\)_i\] = \(int\)\(\*_o\.data\)\[_i\];")
        self.assertNotIn("push_back(MPoint((*_o.data)", c)

    def test_create_uses_bulk_constructors(self):
        c = self.cpp
        self.assertIn("if (!points.empty()) _pa = MPointArray(points.data(), (unsigned)points.size());", c)
        self.assertIn("if (!counts.empty()) _pc = MIntArray(counts.data(), (unsigned)counts.size());", c)
        self.assertIn("if (!indices.empty()) _ic = MIntArray(indices.data(), (unsigned)indices.size());", c)
        self.assertIn("MVectorArray _nrm(normals.data(), (unsigned)normals.size());", c)
        self.assertIn("MColorArray _col(colors.data(), (unsigned)colors.size());", c)
        body = c.split("MObject newData = dataCreator.create(&gstat);")[1].split("setMObject")[0]
        self.assertEqual(_no_appends(body), [])


class TestGeoIoHelpersAreBulk(unittest.TestCase):
    """A typed mesh INPUT/OUTPUT on a plain MPxNode goes through emit_geo_io's
    nd_read_mesh / nd_build_mesh."""

    def setUp(self):
        self.cpp = codegen.generate_cpp(_spec(
            "self.aOut = Mesh(points=self.aIn.points, counts=self.aIn.counts, "
            "indices=self.aIn.indices)\n",
            inputs={"aIn": {"type": "mesh", "is_array": False}},
            outputs={"aOut": {"type": "mesh", "is_array": False}}), for_port=True)
        self.assertIn("nd_build_mesh", self.cpp)          # the premise

    def test_build_mesh_uses_bulk_constructors(self):
        c = self.cpp
        self.assertIn("_pa = MPointArray(g.points.data(), (unsigned)g.points.size());", c)
        self.assertIn("_pc = MIntArray(g.counts.data(), (unsigned)g.counts.size());", c)
        self.assertIn("_ic = MIntArray(g.indices.data(), (unsigned)g.indices.size());", c)
        self.assertIn("MVectorArray _nr(g.normals.data(), (unsigned)g.normals.size());", c)
        self.assertIn("MColorArray _co(g.colors.data(), (unsigned)g.colors.size());", c)
        self.assertIn("_su = MFloatArray(_ud.data(), (unsigned)_nuv);", c)
        body = c.split("static MObject nd_build_mesh")[1].split("return _data;")[0]
        self.assertEqual(_no_appends(body), [])

    def test_read_mesh_copies_topology_in_bulk(self):
        c = self.cpp
        self.assertIn("if (_gc.length()) _gc.get(g.counts.data());",  c)
        self.assertIn("if (_gv.length()) _gv.get(g.indices.data());", c)
        self.assertIn("g.points[i] = MPoint((double)_rp[3 * i]",      c)
        self.assertNotIn("g.counts.push_back(", c)


if __name__ == "__main__":
    unittest.main()
