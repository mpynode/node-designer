"""Maya-FREE: Item 11 -- CSE non-trivial operands duplicated by abs/min/max.

Python ``abs(x)`` lowers to a C++ ternary ``((x) < 0 ? -(x) : (x))`` that names
the operand THREE times; ``min``/``max`` name each operand TWICE. When the
operand is a bare name / literal / cast (trivial), that duplication is free --
the compiler folds it -- and it stays inline. But when the operand contains a
real call (nd::matmul, .item(), a helper) the source expression would be EMITTED
and re-evaluated 2-3x. This binds such an operand to ONE ``const auto`` local so
it is computed exactly once, then referenced by the ternary. A pure expression
evaluated once yields the same value as evaluated three times, so the produced
value (and every downstream bit) is UNCHANGED -- a pure common-subexpression
rewrite, byte-for-byte faithful.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c


def _emit(compute, env):
    res, _w, _h = p2c.transpile_compute_block(
        compute, dict(env), {"self.r": lambda v: ["out = %s;" % v.code]})
    return "\n".join(res.all_lines())


def _A(dt="double", r=1):
    return p2c.CppType("array", dt, r)


def _S(dt="double"):
    return p2c.CppType("scalar", dt, 0)


class TestCseNonTrivialOperand(unittest.TestCase):
    def test_abs_of_matmul_scalar_binds_matmul_once(self):
        # abs(float(a @ b)): a@b is a rank-0 array, float() -> scalar via .item();
        # abs then triplicates the operand. The nd::matmul must be emitted ONCE,
        # bound to a const, and the ternary must reference the bound temp.
        text = _emit("self.r = abs(float(self.a @ self.b))\n",
                     {"self.a": _A(), "self.b": _A()})
        self.assertEqual(text.count("nd::matmul("), 1)   # bound once, not 3x
        self.assertIn("const auto", text)                # a cse temp was emitted

    def test_abs_of_scalar_name_stays_inline(self):
        # abs(x) where x is a scalar Name -> trivial operand -> NO const temp; the
        # ternary inlines the name (free to duplicate; the compiler folds it).
        text = _emit("self.r = abs(self.x)\n", {"self.x": _S()})
        self.assertNotIn("const auto", text)
        self.assertIn("< 0 ? -", text)                   # still the abs ternary

    def test_max_of_matmul_scalar_binds_operand_once(self):
        # max(float(a @ b), c): the non-trivial matmul operand is named twice by
        # the max ternary -> bound once; the trivial c stays inline.
        text = _emit("self.r = max(float(self.a @ self.b), self.c)\n",
                     {"self.a": _A(), "self.b": _A(), "self.c": _S()})
        self.assertEqual(text.count("nd::matmul("), 1)   # bound once, not 2x
        self.assertIn("const auto", text)


if __name__ == "__main__":
    unittest.main()
