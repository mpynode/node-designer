"""Maya-FREE: the dtype lattice collapses narrow widths, and that is DELIBERATE.

``_dtype_of`` maps every integer subtype to ``int64`` and every float subtype to
``double``. Where the authored dtype is a PRECISION choice that is harmless (the
compiled answer is closer to exact than the authored one, and the three real
sinks -- Maya mesh points, VP2 textures, draw buffers -- are float32 anyway).
Where it is a WIDTH choice it is a real divergence: numpy wraps at the authored
width and nd:: does not.

Narrowing the lattice to remove the divergence was measured and REJECTED. It
makes parity WORSE, not better: float32 ``nd::matmul`` at K=100 with cancellation
goes from exactly 0.0 today to 7.391e-04, which is OUTSIDE the 1e-4 gate, because
nd accumulates serially while numpy float32 matmul is blocked BLAS sgemm. The
whole-node payoff would have been ~1.0x-1.1x against threading's measured
14x-110x, and on a realistic deformer the authored discipline (f64 positions /
f32 weights / i32 indices) measured 0.895x-1.004x -- a SLOWDOWN in three of four
configurations.

So this file does not assert the divergence away. It PINS it, so that it stays a
known deviation rather than something a future reader discovers by shipping
wrapping image arithmetic on the strength of a comment that used to claim the
mapping was faithful.
"""

from __future__ import annotations

import unittest

import numpy as np

from mpynode.native.compiler import py_to_cpp as p2c


def _emit(compute, env):
    res, _w, _h = p2c.transpile_compute_block(
        compute, dict(env), {"self.r": lambda v: ["out = %s;" % v.code]})
    return "\n".join(res.all_lines())


class TestNarrowIntWidthDeviation(unittest.TestCase):
    """numpy wraps at the authored width; the lowered C++ does not."""

    def test_uint8_addition_wraps_in_numpy_and_does_not_in_cpp(self):
        # numpy: 200 + 200 over uint8 wraps to 144. nd:: keeps int64, so the
        # compiled node computes 400. Both are "correct" for their own type;
        # they are not the same answer, and no gate downstream detects it.
        got = np.uint8(200) + np.uint8(200)
        self.assertEqual(int(got), 144)
        self.assertEqual(200 + 200, 400)
        self.assertNotEqual(int(got), 400)

    def test_int32_addition_wraps_in_numpy_and_does_not_in_cpp(self):
        got = np.int32(2000000000) + np.int32(2000000000)
        self.assertEqual(int(got), -294967296)
        self.assertEqual(2000000000 + 2000000000, 4000000000)
        self.assertNotEqual(int(got), 4000000000)

    def test_every_integer_width_still_collapses_to_int64(self):
        # The collapse itself is the documented behaviour. If someone widens the
        # lattice later, this test is the tripwire that says the deviation above
        # has changed and the comment at _dtype_of must be revisited with it.
        for spelling in ("np.int8", "np.int16", "np.int32", "np.int64",
                         "np.uint8", "np.uint16", "np.uint32", "np.uint64"):
            text = _emit("self.r = np.zeros(4, dtype=%s)\n" % spelling, {})
            self.assertIn("int64_t", text, spelling)
            self.assertNotIn("int32_t", text, spelling)


class TestNarrowFloatIsPrecisionNotWidth(unittest.TestCase):
    def test_float32_collapses_to_double_and_that_is_the_safer_direction(self):
        # float32 -> double means the compiled node is MORE accurate than the
        # authored numpy, bounded by the rounding the author already accepted.
        # Recorded here so the asymmetry with the integer case is explicit.
        a = np.float32(0.1) + np.float32(0.2)
        b = np.float64(0.1) + np.float64(0.2)
        self.assertNotEqual(float(a), float(b))
        self.assertLess(abs(float(b) - 0.3), abs(float(a) - 0.3))


if __name__ == "__main__":
    unittest.main()
