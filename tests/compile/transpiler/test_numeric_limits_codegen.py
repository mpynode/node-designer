"""A recorded min_value / max_value reaches the compiled attr as setMin / setMax.

The interpreted node hands ``addAttr -min/-max`` for float / double / long /
doubleAngle / doubleLinear (``wrappers._mpy_node._apply_numeric_limits``), in
internal units for the unit types. Until 2026-10-02 no compiled node set
either, so a compiled slider ran past the range its interpreted twin clamps to
(Mesh Maze, Scanline, Circular Text, Voxelize ... 18 stage-1 files). Bool,
enum and time never take one, and a node that records none stays
byte-identical.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _spec(inputs, outputs=None, base="MPxNode", mpy_type="mPyNode",
          compute=""):
    """``inputs`` / ``outputs``: {plug: (type, is_array, extra meta)}."""
    def side(d):
        out = {}
        for k, (t, arr, extra) in (d or {}).items():
            out[k] = dict({"type": t, "is_array": arr}, **extra)
        return out

    return {
        "suggested": {"node_type_name": "limProbe", "class_name": "LimProbe",
                      "type_id": "0x0007FF41", "mpx_base": base},
        "mpy_type":    mpy_type,
        "source_node": "limProbeSrc",
        "inputs":      side(inputs),
        "outputs":     side(outputs),
        "portability": {"portable": True, "blockers": []},
        "compute":     compute,
        "init":        "",
        "variables":   {},
    }


def _cpp(spec):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(spec, for_port=True)


class TestPlainNode(unittest.TestCase):

    def test_every_limit_type_gets_both_bounds(self):
        # (type, min, max, create fn, create tail, emitted min, emitted max)
        rows = (
            ("float", 0.0, 1.0, "nAttr", "MFnNumericData::kFloat, 0.0);",
             "0.0", "1.0"),
            ("double", -2.5, 7, "nAttr", "MFnNumericData::kDouble, 0.0);",
             "-2.5", "7.0"),
            ("long", 1, 9.0, "nAttr", "MFnNumericData::kInt, 0);", "1", "9"),
            # unit types: internal units, as addAttr -min/-max
            ("doubleAngle", 0.0, 3.5, "uAttr", "MFnUnitAttribute::kAngle, 0.0);",
             "0.0", "3.5"),
            ("doubleLinear", 0.5, 250.0, "uAttr",
             "MFnUnitAttribute::kDistance, 0.0);", "0.5", "250.0"),
        )
        for t, lo, hi, fn, tail, elo, ehi in rows:
            with self.subTest(type=t):
                cpp = _cpp(_spec({"v": (t, False, {"min_value": lo, "max_value": hi})},
                                 {"o": ("float", False, {})}))
                self.assertIn('aV = %s.create("v", "v", %s\n'
                              "    %s.setMin(%s);\n"
                              "    %s.setMax(%s);\n"
                              "    %s.setStorable(true);"
                              % (fn, tail, fn, elo, fn, ehi, fn), cpp)

    def test_one_bound_alone(self):
        cpp = _cpp(_spec({"seed": ("long", False, {"min_value": 0})},
                         {"o": ("float", False, {})}))
        self.assertIn("    nAttr.setMin(0);\n    nAttr.setStorable(true);", cpp)
        self.assertNotIn("setMax", cpp)

    def test_no_limit_emits_nothing(self):
        cpp = _cpp(_spec({"a": ("float", False, {}), "b": ("doubleAngle", False, {})},
                         {"o": ("float", False, {})}))
        self.assertNotIn("setMin", cpp)
        self.assertNotIn("setMax", cpp)

    def test_bool_enum_time_never_take_one(self):
        # The interpreted node ignores min/max on these types, so a stray
        # value in the meta must not reach the compiled attr either.
        cpp = _cpp(_spec({"b": ("bool", False, {"min_value": 0, "max_value": 1}),
                          "e": ("enum", False, {"min_value": 0, "max_value": 1,
                                                "enum_names": ["A", "B"]}),
                          "t": ("time", False, {"min_value": 0, "max_value": 1})},
                         {"o": ("float", False, {})}))
        self.assertNotIn("setMin", cpp)
        self.assertNotIn("setMax", cpp)

    def test_outputs_take_limits_too(self):
        # add_output_attr applies _apply_numeric_limits as well
        cpp = _cpp(_spec({"a": ("float", False, {})},
                         {"o": ("double", False, {"min_value": -1.0, "max_value": 1.0})}))
        self.assertIn("    nAttr.setMin(-1.0);\n    nAttr.setMax(1.0);\n"
                      "    nAttr.setWritable(false);", cpp)

    def test_array_input_limits_every_element(self):
        cpp = _cpp(_spec({"w": ("float", True, {"min_value": 0.0, "max_value": 1.0})},
                         {"o": ("float", False, {})}))
        at = cpp.index('aW = nAttr.create("w"')
        self.assertLess(cpp.index("nAttr.setMin(0.0);", at),
                        cpp.index("nAttr.setArray(true);", at))

    def test_packed_array_takes_none(self):
        # addAttr rejects -min/-max on a dataType plug; so does the compiled one
        cpp = _cpp(_spec({"p": ("double", True, {"packed": True, "min_value": 0.0})},
                         {"o": ("float", False, {})}))
        self.assertNotIn("setMin", cpp)


class TestFindPlugFamilies(unittest.TestCase):
    """The locator and IK solver create their scalar inputs by hand; those
    paths take the limits too. A generic input rides emit_attr._create_lines."""

    def test_locator_scalars_and_generics(self):
        from mpynode.native.compiler.emit_locator import _LOCATOR_BASE

        cpp = _cpp(_spec({"alpha": ("float", False, {"min_value": 0.0, "max_value": 1.0}),
                          "count": ("long", False, {"min_value": 2}),
                          "flag":  ("bool", False, {"min_value": 0}),
                          "dist": ("doubleLinear", False, {"min_value": 1.0})},
                         base=_LOCATOR_BASE, mpy_type="mPyLocator"))
        self.assertIn("    nAttr.setStorable(true); nAttr.setKeyable(true);\n"
                      "    nAttr.setMin(0.0);\n    nAttr.setMax(1.0);\n"
                      "    nAttr.setAffectsAppearance(true);", cpp)
        self.assertIn("    nAttr.setStorable(true); nAttr.setKeyable(true);\n"
                      "    nAttr.setMin(2);\n"
                      "    nAttr.setAffectsAppearance(true);", cpp)
        self.assertIn("    uAttr.setMin(1.0);", cpp)
        flag = cpp.split('a_in_flag = nAttr.create("flag"', 1)[1].split("addAttribute", 1)[0]
        self.assertNotIn("setMin", flag)

    def test_iksolver_scalars(self):
        cpp = _cpp(_spec({"stiff": ("float", False, {"min_value": 0.0, "max_value": 1.0}),
                          "iters": ("long", False, {"min_value": 1})},
                         base="MPxIkSolverNode", mpy_type="mPyIkSolver",
                         compute="self.local_matrices = []\n"))
        self.assertIn("    nAttr.setStorable(true); nAttr.setKeyable(true);\n"
                      "    nAttr.setMin(0.0);\n    nAttr.setMax(1.0);\n"
                      "    addAttribute(a_stiff);", cpp)
        self.assertIn("    nAttr.setMin(1);\n    addAttribute(a_iters);", cpp)


if __name__ == "__main__":
    unittest.main()
