"""The mPyFile VP2 override reads every compute input off an MPlug (bug 6).

updateDG re-reads each input the texel body uses and folds it into the bake
key. Two holes, both measured on a scratch texture whose body used them: a
doubleAngle was read with ``asAngle()`` -- the data-handle spelling, which MPlug
does not have -- and every unit / vector / colour / float2 / quaternion / hex
MULTI was dropped from nd_texel because the multi parser only matched a bare
``eh.asX();`` and an argument-less gap fill. Either one fails to compile. The
shipped templates' injections are unchanged (none uses such an input).
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# The arrays the texel body below sums -- one per element family.
_EXTRA = (("ang", "doubleAngle", False), ("angArr", "doubleAngle", True),
          ("vecArr", "double3", True), ("linArr", "doubleLinear", True),
          ("posArr", "position", True), ("colArr", "color", True),
          ("uvArr", "float2", True))
_BODY = ("a = self.ang + np.sum(self.angArr)\n"
         "r = 0.5 + 0.5 * np.sin(a)\n"
         "g = np.sum(self.vecArr[:, 1]) * 0.1 + np.sum(self.posArr[:, 0]) * 0.05"
         " + np.sum(self.linArr) * 0.01\n"
         "b = np.sum(self.colArr[:, 2]) * 0.3 + np.sum(self.uvArr[:, 1]) * 0.2\n"
         "self.outColor = (r, g, b)\n"
         "self.outAlpha = 1.0\n")


def _scanline_spec():
    man = os.path.join(_paths.ROOT, "templates", "MPyFile", "File Scanline",
                       "build", "manifest.json")
    with open(man, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


class TestPlugReads(unittest.TestCase):

    def test_angle_reads_through_asMAngle(self):
        from mpynode.native.compiler import emit_vp2_override as vp2

        i = vp2._Input("double", "in_aA", "aA", "asAngle().asRadians()", "a")
        self.assertEqual(i.plug_read, "asMAngle().asRadians()")

    def test_every_multi_element_read_has_a_plug_twin(self):
        from mpynode.native.compiler import emit_vp2_override as vp2
        from mpynode.native.compiler.emit_attr import (_elem_plug_read_expr,
                                                       _elem_read_expr)

        for t in vp2._MULTI_ELEM_TYPES:
            with self.subTest(type=t):
                et = vp2._ELEM_TYPE_BY_READ[_elem_read_expr(t)]
                i = vp2._Input("std::vector<X>", "in_aV", "aV", _elem_read_expr(t),
                               "v", multi=True, elem_type=et)
                got = i.elem_plug_lines("_e", "_k")
                if t == "matrix":
                    self.assertIn("MFnMatrixData(_mo).matrix()", got[0])
                else:
                    self.assertEqual(got, ["_m_in_aV[_k] = %s;"
                                           % _elem_plug_read_expr(t, "_e")])
                self.assertFalse(i.is_time, "a multi is a vector, not a time")


class TestInjection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import emit_vp2_override as vp2
        from mpynode.native.spec.spec_extractor import normalize_attr

        spec = _scanline_spec()
        for name, t, arr in _EXTRA:
            spec["inputs"][name] = normalize_attr({"attr_type": t, "is_array": arr})
        spec["compute"] = _BODY
        cls.cpp         = codegen.generate_cpp(spec, for_port=True)
        cls.out         = vp2.inject_vp2_override(cls.cpp, spec)
        cls.vp2         = vp2

    def test_the_body_lowers_and_injects(self):
        from mpynode.native import compiler as codegen

        self.assertNotIn(codegen.PORT_BEGIN, self.cpp)
        self.assertEqual(self.vp2.skip_reason(self.cpp), "")
        self.assertNotEqual(self.out, self.cpp)

    def test_every_array_joins_nd_texel(self):
        texel = self.out.split("static void nd_texel(", 1)[1].split(") {", 1)[0]
        for name, t, arr in _EXTRA:
            if arr:
                self.assertIn("in_a%s%s" % (name[0].upper(), name[1:]), texel)
        self.assertIn("const std::vector<MVector>& in_aVecArr", texel)
        self.assertIn("const std::vector<MFloatVector>& in_aColArr", texel)

    def test_updatedg_reads_each_off_its_plug(self):
        for line in (
                "if (st) _m_in_aAng = p.asMAngle().asRadians();",
                "_m_in_aAngArr[_e.logicalIndex()] = _e.asMAngle().asRadians();",
                "_m_in_aVecArr[_e.logicalIndex()] = MVector(_e.child(0).asDouble(), "
                "_e.child(1).asDouble(), _e.child(2).asDouble());",
                "_m_in_aLinArr[_e.logicalIndex()] = _e.asMDistance().asCentimeters();",
                "_m_in_aColArr[_e.logicalIndex()] = MFloatVector(_e.child(0).asFloat(), "
                "_e.child(1).asFloat(), _e.child(2).asFloat());",
                "_m_in_aUvArr[_e.logicalIndex()] = MFloatVector(_e.child(0).asFloat(), "
                "_e.child(1).asFloat(), 0.0f);",
                "_m_in_aColArr.resize(_n, MFloatVector(0.0f, 0.0f, 0.0f));"):
            self.assertIn(line, self.out)
        self.assertNotIn("p.asAngle()", self.out)

    def test_bake_key_folds_vector_components(self):
        self.assertIn("for (size_t _i = 0; _i < _m_in_aVecArr.size(); ++_i) { "
                      'texName += (double)_m_in_aVecArr[_i].x; texName += MString(","); '
                      'texName += (double)_m_in_aVecArr[_i].y; texName += MString(","); '
                      'texName += (double)_m_in_aVecArr[_i].z; texName += MString(","); }',
                      self.out)
        self.assertNotIn("(double)_m_in_aVecArr[_i];", self.out)
        self.assertIn("for (size_t _i = 0; _i < _m_in_aAngArr.size(); ++_i) { "
                      'texName += (double)_m_in_aAngArr[_i]; texName += MString(","); }',
                      self.out)

    def test_matrix_multi_brings_its_header(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.spec.spec_extractor import normalize_attr

        spec                   = _scanline_spec()
        spec["inputs"]["mats"] = normalize_attr({"attr_type": "matrix", "is_array": True})
        spec["compute"] = ("t = np.sum(self.mats[:, 3, 0])\n"
                           "self.outColor = (t, t, t)\n"
                           "self.outAlpha = 1.0\n")
        cpp = codegen.generate_cpp(spec, for_port=True)
        if codegen.PORT_BEGIN in cpp:
            self.skipTest("matrix-array slicing does not lower")
        out = self.vp2.inject_vp2_override(cpp, spec)
        self.assertIn("#include <maya/MFnMatrixData.h>", out)
        self.assertIn("_m_in_aMats[_e.logicalIndex()] = MFnMatrixData(_mo).matrix();", out)
        self.assertIn("texName += (double)_m_in_aMats[_i](3, 0);", out)


if __name__ == "__main__":
    unittest.main()
