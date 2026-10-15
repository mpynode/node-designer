"""A compiled attribute is defined as the interpreted node defines it (v43).

The interpreted node decides. An attribute audit of all 37 templates
(interpreted node vs the All Templates Plugin, 2026-10-15) found the compiled
definitions apart in six ways:

  * short names: 186 differences. The compiled create reused every long name as
    the short name, so mPyFile's SSOT short names (``fn``, ``uv``, ``cs`` ...),
    ``outMesh``'s ``om``, ``tgeo`` / ``ltgt`` and every colour child (``colorR``
    there, createColor's ``colorr`` here) were missing: ``connectAttr
    place2d.outUV <node>.uv`` failed on all four compiled mPyFile types.
  * keyable: 22. ``add_input_attr`` makes every non-array input keyable, and the
    children of an array input too; the compiled mesh and matrix inputs and the
    array children were not.
  * usesArrayDataBuilder: 39. An ``addAttr -multi`` input uses the builder,
    children included; the compiled array inputs did not.
  * a packed (typed-array) input: ``addAttr -dt`` gives no default; the
    compiled one carried an empty data object.
  * missing plugs: 27. ``_timeIn`` on the mesh / curve / surface / transform
    generators (10 types) and mPyConstraint's 17 preset plugs, so their
    connections were dropped on Convert to C++.
  * Two Bone IK's ``_jointBindOffsets``: a string holding JSON rows
    interpreted, a hidden matrixArray compiled, so a convert lost the captured
    neutral. The compiled node now keeps the same JSON text in a string attr
    starting "" (the user's choice).

The first class pins the generator; the second compares the shipped compiled
sources with the interpreted types themselves; the third checks every shipped
lineage file that derives from the current stage 1.
"""
from __future__ import annotations

import glob
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.api.OpenMaya as om

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_TEMPLATES = os.path.join(_paths.ROOT, "templates")
_MEGA      = os.path.join(_TEMPLATES, "All Templates Plugin", "build")
_CREATE    = re.compile(r'\.create(?:Point)?\("(\w+)", "(\w+)"')
_STAMP     = re.compile(r"^// build: ([0-9a-f]{12})", re.M)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _builds(type_name):
    """Every build tree carrying ``type_name``: its template's and the mega."""
    pattern = os.path.join(_TEMPLATES, "*", "*", "build", "stages", type_name,
                           "1_transpiled.cpp")
    return [os.path.dirname(os.path.dirname(os.path.dirname(p)))
            for p in glob.glob(pattern)] + [_MEGA]


def _final(type_name):
    """The shipped final ``build/<t>/<t>.cpp`` of ``type_name``'s template."""
    hits = glob.glob(os.path.join(_TEMPLATES, "*", "*", "build", type_name,
                                  type_name + ".cpp"))
    assert len(hits) == 1, (type_name, hits)
    return _read(hits[0])


def _lineage(type_name):
    """Every shipped file derived from ``type_name``'s CURRENT stage 1: the
    stage 1 itself and each later stage, final and source carrying its stamp.
    A file with another stamp (an AI port of an older stage 1) is not one."""
    out = []
    for build in _builds(type_name):
        s1 = os.path.join(build, "stages", type_name, "1_transpiled.cpp")
        if not os.path.isfile(s1):
            continue
        stamp = _STAMP.search(_read(s1)).group(1)
        files = glob.glob(os.path.join(build, "stages", type_name, "**",
                                       "*.cpp"), recursive=True)
        files += [os.path.join(build, type_name, type_name + ".cpp"),
                  os.path.join(build, "source", type_name + ".cpp")]
        for path in files:
            if not os.path.isfile(path):
                continue
            m = _STAMP.search(_read(path))
            if m and m.group(1) == stamp:
                out.append(path)
    return out


def _shorts(cpp):
    """``{long: short}`` of every attribute the C++ creates."""
    return dict(_CREATE.findall(cpp))


def _static_attr(node_type, name):
    """The interpreted type's own (static) attribute, without making a node."""
    return om.MFnAttribute(om.MNodeClass(node_type).attribute(name))


def _member(m_plug, kind, meta, member=None):
    return {"plug": m_plug, "member": member or "a" + m_plug[:1].upper()
            + m_plug[1:], "kind": kind, "meta": meta}


class TestCreateLines(unittest.TestCase):
    """emit_attr._create_lines, one attribute at a time."""

    def _lines(self, plug, meta, kind="inputs"):
        from mpynode.native.compiler.emit_attr import _create_lines

        return _create_lines(_member(plug, kind, meta))

    def test_a_plug_takes_its_recorded_short_name(self):
        lines = self._lines("fileName", {"type": "string", "short": "fn"})
        self.assertIn('    aFileName = tAttr.create("fileName", "fn", '
                      'MFnData::kString);', lines)

    def test_a_user_attr_short_name_is_its_long_name(self):
        lines = self._lines("speed", {"type": "double"})
        self.assertIn('    aSpeed = nAttr.create("speed", "speed", '
                      'MFnNumericData::kDouble, 0.0);', lines)

    def test_colour_children_are_named_and_seeded(self):
        lines = self._lines("tint", {"type": "color",
                                     "default_value": [0.25, 0.5, 0.75]})
        self.assertEqual(lines[:5], [
            '    MObject aTintR = nAttr.create("tintR", "tintR", '
            'MFnNumericData::kFloat, 0.25);',
            '    MObject aTintG = nAttr.create("tintG", "tintG", '
            'MFnNumericData::kFloat, 0.5);',
            '    MObject aTintB = nAttr.create("tintB", "tintB", '
            'MFnNumericData::kFloat, 0.75);',
            '    aTint = nAttr.create("tint", "tint", aTintR, aTintG, aTintB);',
            "    nAttr.setUsedAsColor(true);",
        ])
        self.assertFalse(any("createColor" in ln for ln in lines))

    def test_ssot_colour_children_take_their_short_names(self):
        lines = self._lines("borderColor", {
            "type": "color", "short": "bcl",
            "children": ["borderColorR", "borderColorG", "borderColorB"],
            "child_shorts": ["bcr", "bcg", "bcb"]})
        self.assertIn('    MObject aBorderColorG = nAttr.create("borderColorG", '
                      '"bcg", MFnNumericData::kFloat, 0.0);', lines)
        self.assertIn('    aBorderColor = nAttr.create("borderColor", "bcl", '
                      'aBorderColorR, aBorderColorG, aBorderColorB);', lines)

    def test_an_output_colour_takes_no_default(self):
        lines = self._lines("tint", {"type": "color",
                                     "default_value": [1.0, 0.0, 0.0]},
                            kind="outputs")
        self.assertIn('    MObject aTintR = nAttr.create("tintR", "tintR", '
                      'MFnNumericData::kFloat, 0.0);', lines)

    def test_geometry_and_matrix_inputs_are_keyable_unless_arrays(self):
        for t, fn in (("mesh", "tAttr"), ("nurbsCurve", "tAttr"),
                      ("nurbsSurface", "tAttr"), ("matrix", "mAttr")):
            with self.subTest(type=t):
                one = self._lines("g", {"type": t})
                self.assertEqual(one[-1], "    %s.setKeyable(true);" % fn)
                many = self._lines("g", {"type": t, "is_array": True})
                self.assertNotIn("    %s.setKeyable(true);" % fn, many)
                self.assertIn("    %s.setKeyable(false);" % fn, many)

    def test_array_inputs_use_the_array_data_builder(self):
        lines = self._lines("weights", {"type": "double", "is_array": True})
        self.assertEqual(lines[-3:], ["    nAttr.setArray(true);",
                                      "    nAttr.setKeyable(false);",
                                      "    nAttr.setUsesArrayDataBuilder(true);"])

    def test_a_framework_array_can_opt_out(self):
        lines = self._lines("targetGeometry", {
            "type": "mesh", "is_array": True, "array_data_builder": False})
        self.assertFalse(any("UsesArrayDataBuilder" in ln for ln in lines))

    def test_compound_array_children(self):
        lines = self._lines("cv", {"type": "double3", "is_array": True})
        for ax in "XYZ":
            self.assertIn("    { MFnAttribute _ac(aCv%s); _ac.setKeyable(true); "
                          "_ac.setUsesArrayDataBuilder(true); }" % ax, lines)
        outs = self._lines("cv", {"type": "double3", "is_array": True},
                           kind="outputs")
        self.assertIn("    { MFnAttribute _ac(aCvX); "
                      "_ac.setUsesArrayDataBuilder(true); }", outs)

    def test_packed_input_has_no_default(self):
        lines = self._lines("deltas", {"type": "double", "is_array": True,
                                       "packed": True})
        self.assertEqual(lines[0], '    aDeltas = tAttr.create("deltas", '
                                   '"deltas", MFnData::kDoubleArray);')
        self.assertFalse(any("_pd" in ln for ln in lines))


class TestShippedSourcesMatchTheInterpretedTypes(unittest.TestCase):
    """The shipped compiled sources, read next to the interpreted types."""

    def test_mpyfile_short_names(self):
        from mpynode._common.interface import file_texture_interface as iface

        for ty in ("fileTexture", "compositeTexture", "scanlineTex",
                   "gameOfLifeTex"):
            shorts = _shorts(_final(ty))
            for e in iface.FILE_TEXTURE_ATTRS:
                for long_name in [e["long"]] + [c["long"] for c
                                                in e.get("children", [])]:
                    with self.subTest(type=ty, plug=long_name):
                        self.assertEqual(
                            shorts.get(long_name),
                            _static_attr("mPyFile", long_name).shortName)
            with self.subTest(type=ty, plug="_timeIn"):
                self.assertEqual(shorts.get("_timeIn"),
                                 _static_attr("mPyFile", "_timeIn").shortName)

    def test_generators_have_the_interpreted_time_input(self):
        for ty, native, out in (("metaballs", "mPyMesh", "outMesh"),
                                ("meshMaze", "mPyMesh", "outMesh"),
                                ("helixCurve", "mPyNurbsCurve", "outCurve"),
                                ("rippleSurf", "mPyNurbsSurface", "outSurface"),
                                ("aimTransform", "mPyTransform", None)):
            cpp, ref = _final(ty), _static_attr(native, "_timeIn")
            with self.subTest(type=ty):
                self.assertEqual(_shorts(cpp).get("_timeIn"), ref.shortName)
                self.assertEqual((ref.storable, ref.keyable, ref.readable,
                                  ref.writable, ref.hidden),
                                 (True, False, False, True, True))
                self.assertIn("uAttr.setStorable(true); uAttr.setKeyable(false);",
                              cpp)
                self.assertIn("uAttr.setReadable(false); uAttr.setWritable(true);",
                              cpp)
                if out:
                    self.assertEqual(_shorts(cpp).get(out),
                                     _static_attr(native, out).shortName)
                    self.assertIn("attributeAffects(a_timeIn, a%s%s);"
                                  % (out[0].upper(), out[1:]), cpp)
                else:
                    self.assertIn("attributeAffects(a_timeIn, aOutLocalFlat);",
                                  cpp)

    def test_constraint_preset_plugs(self):
        from mpynode._api2.mpy_constraint import _PRESET_INPUT_NAMES

        shorts = _shorts(_final("procrustesTags"))
        self.assertEqual(len(_PRESET_INPUT_NAMES), 5)
        for plug in _PRESET_INPUT_NAMES:
            ref = _static_attr("mPyConstraint", plug)
            with self.subTest(plug=plug):
                self.assertEqual(shorts.get(plug), ref.shortName)
                self.assertTrue(ref.keyable and ref.storable)

    def test_blend_shape_framework_short_names(self):
        shorts = _shorts(_final("comboCorrectives"))
        for plug in ("targetGeometry", "liveTargets"):
            with self.subTest(plug=plug):
                self.assertEqual(shorts.get(plug),
                                 _static_attr("mPyBlendShape", plug).shortName)
        self.assertFalse(_static_attr("mPyBlendShape",
                                      "targetGeometry").usesArrayDataBuilder)

    def test_ik_bind_offsets_are_the_interpreted_string(self):
        ref = om.MFnTypedAttribute(
            om.MNodeClass("mPyIkSolver").attribute("_jointBindOffsets"))
        self.assertEqual(ref.attrType(), om.MFnData.kString)
        self.assertEqual((ref.readable, ref.storable, ref.hidden, ref.keyable,
                          ref.connectable, ref.internal),
                         (False, True, True, False, False, True))
        cpp = _final("twoBoneIK")
        self.assertIn('MObject bDefObj = bDef.create("");', cpp)
        self.assertIn('a_jointBindOffsets = bAttr.create("_jointBindOffsets", '
                      '"_jointBindOffsets", MFnData::kString, bDefObj);', cpp)
        self.assertIn("bAttr.setConnectable(false); bAttr.setReadable(false); "
                      "bAttr.setWritable(true);", cpp)
        self.assertIn("bAttr.setStorable(true); bAttr.setInternal(true); "
                      "bAttr.setKeyable(false); bAttr.setHidden(true);", cpp)
        self.assertNotIn("kMatrixArray", cpp)
        # written in the interpreted node's JSON spelling: json.dumps rows
        self.assertIn('cmd += "\\" -type \\"string\\" \\"";', cpp)


class TestEveryShippedLineageFile(unittest.TestCase):
    """Each change reached every shipped file derived from the current stage 1
    (spliced, as section 3 of the parity plan prescribes)."""

    _EXPECT = {
        "fileTexture":      ['"uvCoord", "uv", aUvCoordX, aUvCoordY'],
        "compositeTexture": ['"uvCoord", "uv", aUvCoordX, aUvCoordY'],
        "scanlineTex":      ['"uvCoord", "uv", aUvCoordX, aUvCoordY'],
        "gameOfLifeTex":    ['"outColor", "oc", aOutColorR'],
        "metaballs": ['"outMesh", "om"', '"_timeIn", "_tin"',
                      "{ MFnAttribute _ac(aHalfExtentsX); "
                      "_ac.setKeyable(true); "
                      "_ac.setUsesArrayDataBuilder(true); }"],
        "helixCurve":     ['"_timeIn", "_tin"'],
        "aimTransform":   ['"_timeIn", "_tin"', "mAttr.setKeyable(true);"],
        "procrustesTags": ['createPoint("targetTranslate", "ttr")'],
        "comboCorrectives": ['"targetGeometry", "tgeo"',
                             'tAttr.create("targetDeltas", "targetDeltas", '
                             'MFnData::kDoubleArray);'],
        "twoBoneIK": ["MFnData::kString, bDefObj",
                      "bAttr.setInternal(true);"],
        "meshRegionLocator": ['"defaultColorR", "defaultColorR"'],
    }

    def test_every_derived_file(self):
        for ty, needles in self._EXPECT.items():
            files = _lineage(ty)
            with self.subTest(type=ty):
                # stage 1 + 00_baseline + final + source in the template, and
                # the mega's stage 1 + source at least
                self.assertGreaterEqual(len(files), 5)
            for path in files:
                text = _read(path)
                for needle in needles:
                    with self.subTest(file=os.path.relpath(path, _paths.ROOT),
                                      needle=needle):
                        self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
