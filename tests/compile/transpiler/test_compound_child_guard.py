"""compute() resolves a compound output's CHILD to its parent (bug 7).

A pull on ``outColorR`` / ``outX`` arrives as that child plug, and MPlug's
``!=`` against an MObject compares attributes -- so the guard turned the child
away and it read its default until the parent itself was pulled. The compiled
compute now renames its parameter and rebinds ``plug`` to the parent, leaving
the guard line (and every ``plug`` a ported body tests) byte for byte. A node
with no compound OUTPUT keeps the old signature, so it stays byte-identical.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init

_NORM = ("    const MPlug plug = plugIn.isChild() ? plugIn.parent() : plugIn;")


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _spec(inputs, outputs, mpy_type="mPyNode"):
    def side(d):
        return {k: {"type": t, "is_array": arr} for k, (t, arr) in d.items()}

    return {
        "suggested": {"node_type_name": "kidProbe", "class_name": "KidProbe",
                      "type_id": "0x0007FF42", "mpx_base": "MPxNode"},
        "mpy_type":    mpy_type,
        "source_node": "kidProbeSrc",
        "inputs":      side(inputs),
        "outputs":     side(outputs),
        "portability": {"portable": True, "blockers": []},
        "compute":     "",
        "init":        "",
        "variables":   {},
    }


def _cpp(spec):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(spec, for_port=True)


class TestPlainNode(unittest.TestCase):

    def test_each_compound_output_type_normalises(self):
        for t in ("double3", "euler", "position", "color", "float2", "quaternion"):
            for arr in (False, True):
                with self.subTest(type=t, array=arr):
                    cpp = _cpp(_spec({"k": ("float", False)},
                                     {"s": ("float", False), "c": (t, arr)}))
                    self.assertIn(
                        "MStatus KidProbe::compute(const MPlug& plugIn, MDataBlock& data) {\n"
                        + _NORM + "\n"
                        "    if (plug != aS && plug != aC)\n"
                        "        return MS::kUnknownParameter;", cpp)

    def test_scalar_outputs_keep_the_old_signature(self):
        cpp = _cpp(_spec({"v": ("double3", False)},  # compound INPUT only
                         {"s": ("float", False), "m": ("matrix", False),
                          "a": ("double", True)}))
        self.assertIn("MStatus KidProbe::compute(const MPlug& plug, MDataBlock& data) {\n"
                      "    if (plug != aS && plug != aM && plug != aA)", cpp)
        self.assertNotIn("plugIn", cpp)

    def test_helper(self):
        from mpynode.native.compiler.emit_attr import compute_open_lines

        self.assertEqual(
            compute_open_lines("N", [{"meta": {"type": "float"}}]),
            ["MStatus N::compute(const MPlug& plug, MDataBlock& data) {"])
        self.assertEqual(
            compute_open_lines("N", [{"meta": {"type": "float"}},
                                     {"meta": {"type": "euler", "is_array": True}}]),
            ["MStatus N::compute(const MPlug& plugIn, MDataBlock& data) {", _NORM])


class TestTextureAndGeometry(unittest.TestCase):

    def test_mpyfile_base_outputs_are_compound(self):
        # outColor / outTransparency / outSize ride every mPyFile, so the guard
        # normalises even with no user compound -- and the base-surface pins
        # (`plug != aOutTransparency` inside the guard) still read the same.
        from mpynode.native import compiler as codegen

        man = os.path.join(_paths.ROOT, "templates", "MPyFile", "File Simple",
                           "build", "manifest.json")
        with open(man, encoding="utf-8") as fh:
            spec = json.load(fh)["nodes"][0]["spec"]
        cpp   = codegen.generate_cpp(spec, for_port=True)
        guard = cpp.split("::compute(const MPlug& plug", 1)[1]
        guard = guard.split("return MS::kUnknownParameter;", 1)[0]
        self.assertTrue(guard.startswith("In, MDataBlock& data) {\n" + _NORM))
        self.assertIn("plug != aOutTransparency", guard)
        self.assertIn("plug != aOutColor", guard)

    def test_generator_with_scalar_outputs_is_unchanged(self):
        # emit_geo shares the opening, but a generator may not declare a
        # compound output (_GEO_SCALAR_OUT_TYPES), so it never normalises.
        cpp = _cpp(_spec({"n": ("long", False)},
                         {"steps": ("long", False), "when": ("time", False)},
                         mpy_type="mPyMesh"))
        self.assertIn("compute(const MPlug& plug, MDataBlock& data) {\n"
                      "    if (plug != aOutMesh && plug != aSteps && plug != aWhen)",
                      cpp)
        self.assertNotIn("plugIn", cpp)


if __name__ == "__main__":
    unittest.main()
