"""Maya-FREE: QW1 -- the `x ** 2` squaring lowering in the numpy->C++ transpiler.

numpy's ``**`` operator special-cases an integer exponent of 2 as a plain
element-wise multiply (``x * x``), byte-for-byte. The transpiler used to lower
``x ** 2`` to ``nd::power`` / ``nd::apply_binop<..>(nd::BinOp::Pow, ..)`` which
call libm ``pow`` -- correct to ~1 ULP but NOT byte-identical to numpy and much
slower. QW1 lowers ``x ** 2`` to a multiply so the compiled node matches numpy's
``**`` exactly and skips libm.

Scope (safety): only when the exponent is the integer literal ``2`` AND the base
is an ``ast.Name`` / ``ast.Constant`` -- an operand that can be referenced twice
without re-evaluating a side-effecting or expensive subexpression. A non-trivial
base (``(a - b) ** 2``) and any other exponent (``x ** 3``, where float repeated
multiply is NOT byte-exact with numpy) keep the libm ``pow`` path. ``np.power``
is unaffected -- only the ``**`` OPERATOR special-cases squaring in numpy."""

from __future__ import annotations

import unittest

from mpynode.native.compiler.py_to_cpp import (
    transpile_compute_block, scalar_t, array_t)


def _transpile(compute, env):
    writers = {"self.out": lambda val: ["OUT = %s;" % val.code]}
    res, _written, _helpers = transpile_compute_block(compute, dict(env), writers)
    return "\n".join(res.all_lines())


class TestSquaringLowered(unittest.TestCase):
    def test_scalar_name_squared_uses_multiply(self):
        # x ** 2 (scalar Name) -> (x * x), not libm pow.
        cpp = _transpile("self.out = x ** 2\n", {"x": scalar_t("double")})
        self.assertIn("nl_x * nl_x", cpp)
        self.assertNotIn("nd::BinOp::Pow", cpp)
        self.assertNotIn("nd::power(", cpp)

    def test_array_name_squared_uses_nd_mul(self):
        # X ** 2 (array Name) -> nd::mul(X, X), not nd::power(X, 2).
        cpp = _transpile("self.out = X ** 2\n", {"X": array_t("double", 1)})
        self.assertIn("nd::mul(nl_X, nl_X)", cpp)
        self.assertNotIn("nd::power(", cpp)


class TestSquaringGates(unittest.TestCase):
    def test_nontrivial_base_keeps_pow(self):
        # (a - b) ** 2 : base is not a Name/Constant -> keep libm pow so the
        # subexpression is not evaluated twice.
        cpp = _transpile("self.out = (a - b) ** 2\n",
                         {"a": array_t("double", 1), "b": array_t("double", 1)})
        self.assertIn("nd::power(", cpp)
        self.assertNotIn("nd::mul(nd::sub", cpp)

    def test_cube_keeps_pow(self):
        # x ** 3 : float repeated multiply is NOT byte-exact with numpy's ** for
        # exponents >= 3 -> keep libm pow.
        cpp = _transpile("self.out = x ** 3\n", {"x": scalar_t("double")})
        self.assertIn("nd::BinOp::Pow", cpp)


if __name__ == "__main__":
    unittest.main()
