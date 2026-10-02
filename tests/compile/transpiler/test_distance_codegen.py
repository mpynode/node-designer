"""Native codegen for the distance types: ``doubleLinear`` and ``position``.

``doubleLinear`` mirrors ``doubleAngle``: one MFnUnitAttribute, here kDistance,
read with ``asDistance().asCentimeters()`` and written with ``setMDistance``.
``position`` mirrors ``euler``: a numeric double3 parent over three
MFnUnitAttribute kDistance children, read with ``asDouble3()``. Both carry
internal centimetres, as the interpreted node does, so the two builds agree.
MDistance is only forward-declared by the Maya headers, so its header is
included exactly when a doubleLinear is present.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _spec(inputs, outputs, compute="", base="MPxNode", mpy_type="mPyNode"):
    def side(d):
        return {k: {"type": t, "is_array": arr} for k, (t, arr) in d.items()}

    return {
        "suggested": {"node_type_name": "distProbe", "class_name": "DistProbe",
                      "type_id": "0x0007FF31", "mpx_base": base},
        "mpy_type":    mpy_type,
        "source_node": "distProbeSrc",
        "inputs":      side(inputs),
        "outputs":     side(outputs),
        "portability": {"portable": True, "blockers": []},
        "compute":     compute,
        "init":        "",
        "variables":   {},
    }


class TestTables(unittest.TestCase):

    def test_supported_and_array_ok(self):
        from mpynode.native import compiler as codegen

        for t in ("doubleLinear", "position"):
            self.assertIn(t, codegen._SUPPORTED)
            self.assertIn(t, codegen._ARRAY_OK)
        self.assertEqual(codegen._CPP["doubleLinear"], "double")
        self.assertEqual(codegen._CPP["position"], "MVector")

    def test_norm_type_rows(self):
        from mpynode.native.spec import spec_extractor as se

        dl, pos = se._NORM_TYPE["doubleLinear"], se._NORM_TYPE["position"]
        self.assertEqual((dl["cat"], dl["fn"], dl["data"]),
                         ("unit", "MFnUnitAttribute", "kDistance"))
        self.assertEqual((pos["cat"], pos["fn"], pos["data"], pos["read"]),
                         ("vector", "MFnUnitAttribute*3", "kDistance*3",
                          "asDouble3"))
        # Maya's own doubleLinear now maps to doubleLinear, not double.
        self.assertEqual(se._MAYA_ATTR_TO_SPEC["doubleLinear"], "doubleLinear")

    def test_normalize_attr_is_portable(self):
        from mpynode.native.spec.spec_extractor import normalize_attr

        for t in ("doubleLinear", "position"):
            out = normalize_attr({"attr_type": t})
            self.assertTrue(out["portable"], t)
            self.assertNotIn("note", out)


class TestScalarCodegen(unittest.TestCase):

    def setUp(self):
        from mpynode.native import compiler as codegen

        spec = _spec({"pIn": ("position", False),
                      "dIn": ("doubleLinear", False)},
                     {"pOut": ("position", False),
                      "dOut": ("doubleLinear", False)})
        self.cpp = codegen.generate_cpp(spec, for_port=True)

    def test_position_is_three_distance_children(self):
        for plug in ("pIn", "pOut"):
            for ax in "XYZ":
                self.assertIn('uAttr.create("%s%s", "%s%s", '
                              'MFnUnitAttribute::kDistance, 0.0);'
                              % (plug, ax, plug, ax), self.cpp)
        self.assertIn('aPIn = nAttr.create("pIn", "pIn", aPInX, aPInY, '
                      'aPInZ);', self.cpp)
        self.assertIn("in_aPIn = data.inputValue(aPIn).asDouble3();", self.cpp)
        self.assertIn("h_aPOut.set3Double(0.0, 0.0, 0.0);", self.cpp)
        self.assertNotIn("kAngle", self.cpp)

    def test_doubleLinear_is_a_distance_unit_attr(self):
        self.assertIn('aDIn = uAttr.create("dIn", "dIn", '
                      'MFnUnitAttribute::kDistance, 0.0);', self.cpp)
        self.assertIn("in_aDIn = data.inputValue(aDIn).asDistance()"
                      ".asCentimeters();", self.cpp)
        self.assertIn("h_aDOut.setMDistance(MDistance(0.0));", self.cpp)
        self.assertIn("#include <maya/MDistance.h>", self.cpp)

    def test_default_is_centimetres(self):
        from mpynode.native import compiler as codegen

        spec                                   = _spec({"dIn": ("doubleLinear", False)}, {})
        spec["inputs"]["dIn"]["default_value"] = 150.0
        cpp                                    = codegen.generate_cpp(spec, for_port=True)
        self.assertIn('uAttr.create("dIn", "dIn", '
                      'MFnUnitAttribute::kDistance, 150.0);', cpp)

    def test_mdistance_header_only_with_a_doubleLinear(self):
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(
            _spec({"pIn": ("position", False)}, {"pOut": ("position", False)}),
            for_port=True)
        self.assertNotIn("MDistance", cpp)


class TestArrayCodegen(unittest.TestCase):

    def test_array_reads_and_writes(self):
        from mpynode.native import compiler as codegen

        spec = _spec({"pArr": ("position", True),
                      "dArr": ("doubleLinear", True)},
                     {"pArrOut": ("position", True),
                      "dArrOut": ("doubleLinear", True)})
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("std::vector<MVector> in_aPArr;", cpp)
        self.assertIn("in_aPArr[_li] = MVector(eh.asDouble3());", cpp)
        self.assertIn("std::vector<double> in_aDArr;", cpp)
        self.assertIn("in_aDArr[_li] = eh.asDistance().asCentimeters();", cpp)
        self.assertIn('uAttr.create("pArrX", "pArrX", '
                      'MFnUnitAttribute::kDistance, 0.0);', cpp)
        self.assertIn("nAttr.setArray(true);", cpp)
        self.assertIn("uAttr.setArray(true);", cpp)

    def test_element_writers(self):
        from mpynode.native import compiler as codegen

        self.assertEqual(codegen._elem_set_stmt("position", "v"),
                         "eh.set3Double((v).x, (v).y, (v).z);")
        self.assertEqual(codegen._elem_set_stmt("doubleLinear", "v"),
                         "eh.setMDistance(MDistance(v));")
        self.assertEqual(codegen._array_gap_default_cpp({"type": "position"}),
                         "MVector()")
        self.assertEqual(codegen._array_gap_default_cpp(
            {"type": "doubleLinear", "default_value": 25.0}), "25.0")


class TestDeterministicLowering(unittest.TestCase):
    """``self.out = self.in`` lowers to C++ with no AI porter."""

    def test_lowers_without_a_port_region(self):
        from mpynode.native import compiler as codegen

        spec = _spec(
            {"pIn": ("position", False), "dIn": ("doubleLinear", False),
             "pArr": ("position", True), "dArr": ("doubleLinear", True)},
            {"pOut": ("position", False), "pTwice": ("position", False),
             "dOut": ("doubleLinear", False), "pArrOut": ("position", True),
             "dArrOut": ("doubleLinear", True)},
            compute=("self.pOut = self.pIn\n"
                     "self.pTwice = self.pIn * 2\n"
                     "self.dOut = self.dIn\n"
                     "self.pArrOut = self.pArr\n"
                     "self.dArrOut = self.dArr\n"))
        cpp = codegen.generate_cpp(spec, for_port=False)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)
        self.assertIn("h_aDOut.setMDistance(MDistance((double)(", cpp)
        self.assertIn("#include <maya/MDistance.h>", cpp)


class TestFindPlugFamilies(unittest.TestCase):
    """transform / locator read generic inputs off plugs (no datablock)."""

    def test_transform_and_locator_read_cm(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler.emit_locator import _LOCATOR_BASE
        from mpynode.native.compiler.emit_transform import _TRANSFORM_BASE

        for base, mpy_type in ((_TRANSFORM_BASE, "mPyTransform"),
                               (_LOCATOR_BASE, "mPyLocator")):
            with self.subTest(base=base):
                spec = _spec({"pIn": ("position", False),
                              "dIn": ("doubleLinear", False),
                              "dArr": ("doubleLinear", True)}, {},
                             base=base, mpy_type=mpy_type)
                cpp = codegen.generate_cpp(spec, for_port=True)
                self.assertIn(".asMDistance().asCentimeters();", cpp)
                self.assertIn("MFnUnitAttribute::kDistance",     cpp)
                self.assertIn("#include <maya/MDistance.h>",     cpp)
                self.assertIn("double[3], CENTIMETRES",          cpp)

    def test_other_families_include_mdistance(self):
        # Each family adds the header through its own code: the IK solver
        # through findplug_family_extras, the mesh generator through
        # emit_geo's include list, the deformer through node_scaffold. No
        # devkit header includes MDistance.h, so a miss is a compile error.
        import maya.cmds as cmds

        from mpynode.native import compiler as codegen
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver
        from mpynode.wrappers.mpy_mesh import MPyMesh

        cmds.file(new=True, force=True)
        cases = (
            (MPyIkSolver, "ikDist#", "asMDistance().asCentimeters()"),
            (MPyMesh, "meshDist#", "asDistance().asCentimeters()"),
            (MPyDeformer, "dfmDist#", "asDistance().asCentimeters()"),
        )
        for wrapper, name, read in cases:
            with self.subTest(family=wrapper.__name__):
                w = wrapper.create(name=name)
                w.add_input_attr("pIn", "position")
                w.add_input_attr("dIn", "doubleLinear", default_value=12.5)
                w.add_input_attr("dArr", "doubleLinear", is_array=True)
                if wrapper is MPyMesh:
                    w.add_output_attr("dOut", "doubleLinear")
                spec = spec_extractor.extract_spec(w.get_name())
                cpp  = codegen.generate_cpp(spec, for_port=True)
                self.assertIn("#include <maya/MDistance.h>", cpp)
                self.assertIn('uAttr.create("dIn", "dIn", '
                              'MFnUnitAttribute::kDistance, 12.5);', cpp)
                self.assertIn('uAttr.create("pInX", "pInX", '
                              'MFnUnitAttribute::kDistance, 0.0);', cpp)
                self.assertIn(read, cpp)
                if wrapper is MPyMesh:
                    self.assertIn("setMDistance(MDistance(", cpp)


class TestVp2Override(unittest.TestCase):
    """The mPyFile VP2 override re-reads each compute input off an MPlug in
    updateDG. The data handle's asDistance() is asMDistance() on a plug."""

    def test_plug_read_renames_the_distance_accessor(self):
        from mpynode.native.compiler import emit_vp2_override as vp2

        i = vp2._Input("double", "in_aD", "aD", "asDistance().asCentimeters()",
                       "d")
        self.assertEqual(i.plug_read, "asMDistance().asCentimeters()")
        i = vp2._Input("double", "in_aE", "aE", "asDouble()", "e")
        self.assertEqual(i.plug_read, "asDouble()")

    def test_scanline_with_distance_inputs(self):
        import os

        from mpynode._common.io import mpn_io
        from mpynode._common.util.template_gallery import \
            _bundled_templates_root
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import emit_vp2_override as vp2
        from mpynode.native.spec import mpn_spec_adapter
        from mpynode.native.spec.spec_extractor import normalize_attr

        path = os.path.join(_bundled_templates_root(), "MPyFile",
                            "File Scanline", "template.mpn")
        spec = mpn_spec_adapter.spec_from_mpn_payload(
            mpn_io.load_mpn(path, trusted=True))
        spec["inputs"]["distX"] = normalize_attr({"attr_type": "doubleLinear"})
        spec["inputs"]["posP"]  = normalize_attr({"attr_type": "position"})
        cpp                     = codegen.generate_cpp(spec, for_port=False)
        out                     = vp2.inject_vp2_override(cpp, spec)
        self.assertTrue(out != cpp, "injection was a no-op")
        # updateDG's plug reads (the members are also hashed and baked later).
        reads = [line.strip() for line in out.splitlines()
                 if "_m_in_aDistX = p." in line
                 or ("_m_in_aPosP[" in line and "= p.child(" in line)]
        self.assertEqual(reads, [
            'p = fn.findPlug("distX", false, &st); if (st) '
            '_m_in_aDistX = p.asMDistance().asCentimeters();',
            "_m_in_aPosP[0] = p.child(0).asDouble();",
            "_m_in_aPosP[1] = p.child(1).asDouble();",
            "_m_in_aPosP[2] = p.child(2).asDouble();",
        ])
        self.assertFalse("p.asDistance()" in out)


class TestLiveNodeSpec(unittest.TestCase):
    """A live interpreted node's spec carries the new names unchanged."""

    def test_extract_spec(self):
        import maya.cmds as cmds

        from mpynode import MPyNode
        from mpynode.native.spec import spec_extractor

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="distSrc#")
        w.add_input_attr("pIn", "position")
        w.add_input_attr("dIn", "doubleLinear", default_value=150.0)
        w.add_output_attr("pOut", "position")
        w.set_compute_expression("self.pOut = self.pIn")
        spec = spec_extractor.extract_spec(w.get_name())
        self.assertEqual(spec["inputs"]["pIn"]["type"],          "position")
        self.assertEqual(spec["inputs"]["dIn"]["type"],          "doubleLinear")
        self.assertEqual(spec["inputs"]["dIn"]["default_value"], 150.0)
        self.assertEqual(spec["outputs"]["pOut"]["cpp"]["data"], "kDistance*3")


if __name__ == "__main__":
    unittest.main()
