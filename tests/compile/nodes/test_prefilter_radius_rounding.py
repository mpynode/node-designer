"""Compiled preFilterRadius quantises as the interpreted mPyFile does (v45).

The interpreted node quantises the radius in
``file_texture_ops.load_linear_pixels``: ``round(float(radius), 1)``, on the
float plug's value, in double. Until v45 the compiled kernel quantised in
float -- ``nearbyintf(radius * 10.0f) / 10.0f`` -- which rounds the product to
an exact 0.5 first and then half to even, so 0.05 went to 0 where the
interpreted node takes 0.1. 29 of 801 radii (0..8, step 0.01) differed on File
Simple, worst output error 0.162.

The kernel now quantises through ``nd_tex_radius_q``: ``radius * 10.0`` is
exact in double for any float, and ``nearbyint`` rounds that exact tenth, half
to even only on a true tie -- which is what Python's ``round`` does. These
tests pin the generator, every shipped file that carries the texture cache,
and the interpreted reference.
"""
from __future__ import annotations

import glob
import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests import _paths
from tests._setup import standalone_init


def setUpModule():
    standalone_init()


_RADIUS_Q = ("static inline double nd_tex_radius_q(float radius) {\n"
             "    return (radius != 0.0f) ? nearbyint((double)radius * 10.0)"
             " / 10.0 : 0.0;\n"
             "}\n")
# the float statement (the kernel comment still names it, so match the code)
_OLD = "? (nearbyintf(radius * 10.0f) / 10.0f) : 0.0f"


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read().replace("\r\n", "\n")


def _python_round(r):
    """The interpreted quantisation, on a float32 plug value."""
    r = float(r)
    return round(r, 1) if r else 0.0


class TestKernel(unittest.TestCase):
    """The emitted texture kernel."""

    def test_radius_q_is_the_double_formula(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        self.assertIn(_RADIUS_Q, ftc.MATH_CPP)

    def test_the_cache_quantises_through_radius_q(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        # the cache key / prefilter and the per-thread memo in front of it
        self.assertEqual(ftc.CACHE_CPP.count("nd_tex_radius_q(radius)"), 2)
        self.assertFalse(_OLD in ftc.CACHE_CPP)
        self.assertIn("double             rq = -1.0;", ftc.CACHE_CPP)


class TestFormula(unittest.TestCase):
    """The double formula equals Python's round on every float radius."""

    def test_double_formula_equals_python_round(self):
        import numpy as np

        sweep = [np.float32(i * 0.01) for i in range(801)]
        rng   = np.random.RandomState(45)
        rand  = list(rng.uniform(0.0, 8.0, 20000).astype(np.float32))
        for r in sweep + rand:
            # nearbyint under the default rounding mode is np.rint: half to
            # even. radius * 10.0 is exact in double for any float32.
            got = float(np.rint(np.float64(r) * 10.0) / 10.0) if r != 0 else 0.0
            self.assertEqual(got, _python_round(r), repr(r))

    def test_the_float_formula_was_wrong_at_a_half_tenth(self):
        import numpy as np

        r   = np.float32(0.05)
        old = float(np.rint(r * np.float32(10.0)) / np.float32(10.0))
        self.assertEqual(old, 0.0)
        self.assertEqual(_python_round(r), 0.1)


class TestShippedFiles(unittest.TestCase):
    """Every shipped file with the texture cache quantises in double."""

    def test_every_shipped_texture_cache(self):
        seen = 0
        for path in sorted(glob.glob(os.path.join(_paths.ROOT, "templates",
                                                  "**", "*.cpp"),
                                     recursive=True)):
            text = _read(path)
            if "nd_tex_load_linear_uncached(" not in text:
                continue
            with self.subTest(file=os.path.relpath(path, _paths.ROOT)):
                self.assertTrue(_RADIUS_Q in text)
                self.assertEqual(text.count("nd_tex_radius_q(radius)"), 2)
                self.assertFalse(_OLD in text)
            seen += 1
        # 4 mPyFile types: template lineage (stage 1, rounds, final, source)
        # and the All Templates stage 1 + source
        self.assertEqual(seen, 34)


class TestInterpretedReference(unittest.TestCase):
    """What the compiled side copies."""

    def test_interpreted_rounds_the_double_radius(self):
        from mpynode._common.methods import file_texture_ops

        src = inspect.getsource(file_texture_ops.load_linear_pixels)
        self.assertIn("radius_q = round(float(radius), 1) if radius else 0.0",
                      src)


if __name__ == "__main__":
    unittest.main()
