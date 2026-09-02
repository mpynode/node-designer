"""MatrixView lowering: the 15 methods, the gate, and the Maya-free runtime.

A ``matrix`` input arrives in an expression as a ``MatrixView`` carrying the
whole ``MMatrix`` + ``MTransformationMatrix`` surface. ``py_to_cpp`` knew
exactly one of its 42 methods -- ``asNumpy()``, an identity passthrough -- so a
node that asked for a rotation fell through to the stage-2 AI porter, and the
assistant, told only that a MatrixView "behaves like numpy", wrote its own
matrix->euler instead.

These assertions are about ROUTING: that each spelling reaches the intended
``nd::`` kernel or ``ndx::`` bridge call at all, and that the bridge is dragged
in ONLY when it is needed. The arithmetic is Maya's own -- the whole point of
the bridge is that the decomposition is not re-derived -- so there is no
numeric oracle to pin here.

Design note: ``docs/notes/matrixview-lowering.md``.
"""

from __future__ import annotations

import io
import os
import unittest

from mpynode.native.compiler.kernels import nd_maya_cpp
from mpynode.native.compiler.py_to_cpp import (UnsupportedSpec, array_t,
                                               transpile_function)

from tests import _paths

_HEAD = "def f(m):\n    import numpy as np\n"

# A matrix input materialises as an nd (4,4): rank 2 is all the transpiler can
# prove statically, and it is what the receiver guard checks.
_ARGS = {"m": array_t("double", 2)}
_ARGS_VEC = {"m": array_t("double", 1)}


def _lower(body, args=None):
    res = transpile_function(_HEAD + body, args if args is not None else _ARGS)
    return "\n".join(list(res.decl_lines) + list(res.body_lines))


class TestTierAUsesExistingKernels(unittest.TestCase):
    """No Maya needed -- these route through kernels that already existed."""

    def test_translation_is_a_row_three_slice(self):
        # Maya's row-vector convention puts the translation in ROW 3.
        cpp = _lower("    return m.translation()\n")
        self.assertIn("nd::Sl::at(3)", cpp)
        self.assertIn("nd::Sl::to(3)", cpp)

    def test_inverse_routes_to_nd_inv(self):
        self.assertIn("nd::inv(", _lower("    return m.inverse()\n"))

    def test_det4x4_routes_to_nd_det(self):
        self.assertIn("nd::det(", _lower("    return m.det4x4()\n"))

    def test_det3x3_takes_the_upper_left_block(self):
        # NOT the whole matrix -- det3x3 is the rotation/scale block.
        cpp = _lower("    return m.det3x3()\n")
        self.assertIn("nd::det(", cpp)
        self.assertIn("nd::Sl::to(3)", cpp)

    def test_get_element_indexes_both_axes(self):
        cpp = _lower("    return m.getElement(1, 2)\n")
        # The index goes through _scalar_int_of, hence the cast.
        self.assertIn("nd::Sl::at((int64_t)1)", cpp)
        self.assertIn("nd::Sl::at((int64_t)2)", cpp)

    def test_tier_a_never_reaches_the_bridge(self):
        for body in ("    return m.translation()\n",
                     "    return m.inverse()\n",
                     "    return m.det4x4()\n"):
            self.assertNotIn("ndx::", _lower(body), body)


class TestTierCReachesTheBridge(unittest.TestCase):
    """Maya semantics -- delegated rather than re-derived."""

    CASES = (
        ("m.rotation()", "ndx::xf_rotation("),
        ("m.scale()", "ndx::xf_scale("),
        ("m.shear()", "ndx::xf_shear("),
        ("m.rotationOrder()", "ndx::xf_rotation_order("),
        ("m.isSingular()", "ndx::xf_is_singular("),
        ("m.asRotateMatrix()", "ndx::xf_as_rotate_matrix("),
        ("m.asScaleMatrix()", "ndx::xf_as_scale_matrix("),
        ("m.asMatrixInverse()", "ndx::xf_as_matrix_inverse("),
        ("m.adjoint()", "ndx::xf_adjoint("),
        ("m.homogenize()", "ndx::xf_homogenize("),
    )

    def test_each_method_reaches_its_bridge_call(self):
        for call, sym in self.CASES:
            self.assertIn(sym, _lower("    return %s\n" % call), call)

    def test_rotation_defaults_to_xyz(self):
        # axes omitted -> index 0, which euler_order maps to kXYZ.
        cpp = _lower("    return m.rotation()\n")
        self.assertIn("ndx::xf_rotation(", cpp)
        self.assertIn(", 0)", cpp)

    def test_rotation_takes_the_order_as_a_keyword(self):
        self.assertIn("ndx::xf_rotation(m, (int64_t)5)", _lower("    return m.rotation(axes=5)\n"))

    def test_rotation_takes_the_order_positionally(self):
        # Same lowering either way.
        self.assertIn("ndx::xf_rotation(m, (int64_t)3)", _lower("    return m.rotation(3)\n"))

    def test_rotation_rejects_a_second_argument(self):
        with self.assertRaises(UnsupportedSpec):
            _lower("    return m.rotation(1, 2)\n")


class TestReceiverGuard(unittest.TestCase):
    """A MatrixView method on something that is not a (4,4) must be a codegen
    rejection, not a runtime throw buried inside compute."""

    def test_rank_one_receiver_is_rejected(self):
        for call in ("m.rotation()", "m.translation()", "m.det4x4()"):
            with self.assertRaises(UnsupportedSpec, msg=call):
                _lower("    return %s\n" % call, args=_ARGS_VEC)

    def test_the_message_names_the_method(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _lower("    return m.rotation()\n", args=_ARGS_VEC)
        self.assertIn("rotation", str(cm.exception))


class TestTheGate(unittest.TestCase):
    """spec_uses_maya_xform decides whether the bridge and its Maya headers are
    emitted at all. It matches on SOURCE plus the input table, because the
    include list is built before compute lowering."""

    def _spec(self, compute="", init="", itype="matrix"):
        return {"inputs": {"m": {"type": itype}},
                "compute": compute, "init": init}

    def test_matrix_input_plus_method(self):
        self.assertTrue(nd_maya_cpp.spec_uses_maya_xform(
            self._spec(compute="e = self.m.rotation()")))

    def test_init_tier_counts_too(self):
        self.assertTrue(nd_maya_cpp.spec_uses_maya_xform(
            self._spec(init="def g(m): return m.shear()")))

    def test_tier_a_only_does_not_pull_maya_in(self):
        # The discriminating case: a matrix node that never needs the bridge
        # must keep its generated file byte-identical to before.
        self.assertFalse(nd_maya_cpp.spec_uses_maya_xform(
            self._spec(compute="t = self.m.translation()")))

    def test_method_name_without_a_matrix_input_is_not_enough(self):
        # `.scale(` is a common spelling on unrelated objects.
        self.assertFalse(nd_maya_cpp.spec_uses_maya_xform(
            self._spec(compute="x = someObject.scale()", itype="vector")))

    def test_empty_spec(self):
        self.assertFalse(nd_maya_cpp.spec_uses_maya_xform({}))


class TestTheTwoHalvesAgree(unittest.TestCase):
    """py_to_cpp emits ndx:: calls; nd_maya_cpp defines them. Nothing else
    checks that the two lists match, and a typo would only surface as a C++
    compile error at the far end of a multi-hour rebuild."""

    def test_every_emitted_symbol_is_defined(self):
        src = io.open(os.path.join(_paths.ROOT, "scripts", "mpynode", "native",
                                   "compiler", "py_to_cpp.py"),
                      encoding="utf-8").read()
        import re

        emitted = set(re.findall(r'ndx::(\w+)\(', src))
        self.assertTrue(emitted, "no ndx:: calls found in py_to_cpp")
        for sym in sorted(emitted):
            self.assertIn("%s(" % sym, nd_maya_cpp.MAYA_XFORM_CPP,
                          "py_to_cpp emits ndx::%s but the bridge does not "
                          "define it" % sym)

    def test_the_bridge_guards_its_include(self):
        # Bundling several nodes into one translation unit must stay idempotent.
        self.assertIn("#ifndef ND_MAYA_XFORM_H", nd_maya_cpp.MAYA_XFORM_CPP)
        self.assertIn("#define ND_MAYA_XFORM_H", nd_maya_cpp.MAYA_XFORM_CPP)


class TestRuntimeStaysMayaFree(unittest.TestCase):
    """The eleven oracle harnesses under tests/compile/native/ compile
    nd_runtime.h with NO Maya include path, carrying their own MVector/MPoint
    shims. One maya/ include in the runtime turns all eleven red -- which is
    the whole reason the bridge is a separate block."""

    def _runtime(self):
        return io.open(os.path.join(_paths.ROOT, "scripts", "mpynode", "native",
                                    "compiler", "nd_runtime.h"),
                       encoding="utf-8").read()

    def test_no_maya_include(self):
        self.assertNotIn("maya/", self._runtime())

    def test_no_maya_types(self):
        rt = self._runtime()
        for sym in ("MMatrix", "MTransformationMatrix", "MEulerRotation",
                    "MSpace"):
            self.assertNotIn(sym, rt,
                             "%s reached nd_runtime.h -- the oracle harnesses "
                             "compile it without Maya" % sym)

    def test_the_det_arm_that_backs_det4x4_is_present(self):
        self.assertIn("nd::det only 1x1..4x4", self._runtime())
