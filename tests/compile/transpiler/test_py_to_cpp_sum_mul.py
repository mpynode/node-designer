"""Maya-FREE: `(a * b).sum(axis=...)` lowers to nd::sum_mul, and nothing else does.

The authored idiom ``np.sqrt((edge * edge).sum(axis=2))`` is far more common in
the shipped nodes than ``np.linalg.norm`` -- it appears 7 times against norm's
1 -- and the two-step it used to lower to writes and re-reads an ``a*b``
temporary three times the size of its own output purely to sum it away.

The peephole is only ever a SPEED change: nd::sum_mul falls back to the literal
``sum(mul(a, b), ...)`` whenever its runtime preconditions miss (unequal shapes
from a broadcast, a non-trailing or unpacked reduced axis), so emitting it for a
case that cannot fuse is harmless. What is NOT harmless is emitting it for a
reduction that is not a plain sum, or for a product that promotes dtype -- those
would change the answer, so they are pinned here as MUST-NOT-fuse.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c
from mpynode.native.compiler.py_to_cpp import array_t


def _emit(compute, env):
    res, _w, _h = p2c.transpile_compute_block(
        compute, dict(env), {"self.r": lambda v: ["out = %s;" % v.code]})
    return "\n".join(res.all_lines())


ENV = {
    "a":  array_t("double", 3),
    "b":  array_t("double", 3),
    "m":  array_t("double", 2),
    "n":  array_t("double", 2),
    "ib": array_t("bool", 2),
    "ii": array_t("int64", 2),
}


class TestSumMulFires(unittest.TestCase):
    def _fused(self, src):
        return "nd::sum_mul(" in _emit(src, ENV)

    def test_both_spellings_fuse(self):
        # a.sum(...) and np.sum(a, ...) share one lowering; if they ever drift,
        # only one of these two fails.
        self.assertTrue(self._fused("self.r = (a * b).sum(axis=2)"))
        self.assertTrue(self._fused("self.r = np.sum(a * b, axis=2)"))

    def test_self_product_fuses(self):
        # (x * x) is the sum-of-squares shape behind the sqrt(...) idiom.
        self.assertTrue(self._fused("self.r = (a * a).sum(axis=2)"))
        self.assertTrue(self._fused("self.r = np.sqrt((a * a).sum(axis=2))"))

    def test_axis_forms_all_fuse(self):
        for src in ("self.r = (a * b).sum(axis=2)",
                    "self.r = (a * b).sum(axis=-1)",
                    "self.r = (a * b).sum()",
                    "self.r = (a * b).sum(axis=2, keepdims=True)",
                    "self.r = (m * n).sum(axis=1)"):
            self.assertTrue(self._fused(src), src)

    def test_int64_product_fuses(self):
        self.assertTrue(self._fused("self.r = (ii * ii).sum(axis=1)"))

    def test_non_trailing_axis_still_emits_sum_mul(self):
        # Deliberate: the transpiler does not know the runtime layout, so it
        # emits sum_mul and lets the RUNTIME decide. axis=0 cannot fuse and
        # falls back internally -- byte-identically. Pinned so that a future
        # reader does not "fix" this into a transpile-time axis check and
        # assume the runtime guard is therefore dead.
        self.assertTrue(self._fused("self.r = (a * b).sum(axis=0)"))

    def test_emission_passes_the_two_operands_not_the_product(self):
        text = _emit("self.r = (a * b).sum(axis=2)", ENV)
        self.assertIn("nd::sum_mul(", text)
        self.assertNotIn("nd::mul(", text)   # the temporary is gone entirely


class TestSumMulStaysOutOfTheWay(unittest.TestCase):
    def _clean(self, src):
        return "nd::sum_mul(" not in _emit(src, ENV)

    def test_plain_sum_is_untouched(self):
        self.assertTrue(self._clean("self.r = a.sum(axis=2)"))

    def test_sum_of_a_non_product_is_untouched(self):
        self.assertTrue(self._clean("self.r = (a + b).sum(axis=2)"))
        self.assertTrue(self._clean("self.r = (a - b).sum(axis=2)"))

    def test_other_reductions_of_a_product_are_untouched(self):
        # sum_mul seeds acc at 0 and combines with +. mean/prod/max/std would
        # each be a DIFFERENT reduction; fusing them would be silently wrong.
        for op in ("mean", "prod", "max", "min", "std", "var"):
            self.assertTrue(self._clean("self.r = (a * b).%s(axis=2)" % op), op)

    def test_bool_product_is_untouched(self):
        # bool arrays are bit-packed (no .data()) and bool.sum() promotes to
        # int64 -- the promotion path rewrites the receiver, so the peephole
        # must not see through it.
        self.assertTrue(self._clean("self.r = (ib * ib).sum(axis=1)"))

    def test_scalar_operand_is_untouched(self):
        # sum_mul takes two ARRAYS. `a * 2.0` lowers to a scalar overload with
        # no second array to hand it.
        self.assertTrue(self._clean("self.r = (a * 2.0).sum(axis=2)"))
        self.assertTrue(self._clean("self.r = (2.0 * a).sum(axis=2)"))


if __name__ == "__main__":
    unittest.main()
