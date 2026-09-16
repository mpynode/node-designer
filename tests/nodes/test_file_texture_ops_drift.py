"""Drift guard: the INLINE math in ``_defaults/file_defaults.py``
``DEFAULT_INIT_SOURCE`` must stay behaviorally identical to the importable
``_common/methods/file_texture_ops`` module. The inline copy cannot import the
ops module (it is exec'd node source, preserved by one-way .py bake). Maya-free."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import types
import unittest

import numpy as np

from mpynode._common.methods import file_texture_ops as ops
from mpynode._defaults import file_defaults as fd


def _exec_inline_source():
    try:
        import maya.api.OpenMayaRender  # noqa: F401
    except Exception:
        for name in ("maya", "maya.api", "maya.api.OpenMayaRender"):
            sys.modules.setdefault(name, types.ModuleType(name))
    ns = {}
    exec(compile(fd.DEFAULT_INIT_SOURCE, "<DEFAULT_INIT_SOURCE>", "exec"), ns)
    return ns


class TestInitSourceMatchesOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns  = _exec_inline_source()
        rng     = np.random.default_rng(1234)
        cls.img = (rng.random((17, 19, 4)) * 255.0).astype(np.uint8)

    def test_linearize_all_25_color_spaces(self):
        inline = self.ns["_linearize"]
        for cs in range(25):
            self.assertTrue(np.array_equal(inline(self.img, cs),
                                           ops.linearize(self.img, cs)),
                            "linearize drift at colorSpace=%d" % cs)

    def test_kernels_match(self):
        pairs = [(self.ns["_gaussian_kernel"], ops.gaussian_kernel),
                 (self.ns["_box_kernel"], ops.box_kernel),
                 (self.ns["_quadratic_kernel"], ops.quadratic_kernel),
                 (self.ns["_quartic_kernel"], ops.quartic_kernel)]
        for r in (0.5, 1.0, 2.0, 3.7, 8.0):
            for inline, opf in pairs:
                self.assertTrue(np.array_equal(inline(r), opf(r)),
                                "kernel drift radius=%s (%s)" % (r, opf.__name__))

    def test_prefilter_all_kernels(self):
        inline = self.ns["_prefilter"]
        lin    = ops.linearize(self.img, 0)
        for kernel in (ops.kPreFilterBox, ops.kPreFilterQuadratic,
                       ops.kPreFilterQuartic, ops.kPreFilterGaussian):
            self.assertTrue(np.array_equal(inline(lin, True, kernel, 2.0),
                                           ops.prefilter(lin, True, kernel, 2.0)),
                            "prefilter drift at kernel=%d" % kernel)
        self.assertIs(inline(lin, False, ops.kPreFilterGaussian, 2.0), lin)
        self.assertIs(ops.prefilter(lin, False, ops.kPreFilterGaussian, 2.0), lin)

    def test_apply_wrap_matches(self):
        inline = self.ns["_apply_wrap"]
        for mode in (ops.kWrapWrap, ops.kWrapClamp, ops.kWrapMirror, ops.kWrapBorder):
            for coord in (-1.3, -0.2, 0.0, 0.37, 0.5, 1.0, 1.4, 2.9):
                self.assertEqual(inline(coord, mode), ops.apply_wrap(coord, mode),
                                 "apply_wrap drift coord=%s mode=%d" % (coord, mode))

    def test_sample_matches(self):
        inline = self.ns["_sample"]
        lin    = ops.linearize(self.img, 0)
        border = (0.1, 0.2, 0.3)
        for wu in (ops.kWrapWrap, ops.kWrapClamp, ops.kWrapMirror, ops.kWrapBorder):
            for (u, v) in [(0.0, 0.0), (0.25, 0.75), (0.5, 0.5), (1.3, -0.4), (0.99, 0.01)]:
                self.assertEqual(inline(lin, u, v, wu, wu, border),
                                 ops.sample(lin, u, v, wu, wu, border),
                                 "sample drift u=%s v=%s wrap=%d" % (u, v, wu))
        self.assertEqual(inline(None, 0.5, 0.5, 0, 0, border),
                         ops.sample(None, 0.5, 0.5, 0, 0, border))
        # The no-image substitute is a third lock-step copy (the C++ twin's
        # `miss` parameter is the fourth): drift here means the viewport and the
        # render disagree about what a broken layer looks like.
        for miss in (None, (0.0, 0.0, 0.0, 0.0), (0.2, 0.4, 0.6, 0.8)):
            self.assertEqual(inline(None, 0.5, 0.5, 0, 0, border, miss),
                             ops.sample(None, 0.5, 0.5, 0, 0, border, miss),
                             "missing-substitute drift: %r" % (miss,))
        # A substitute must not leak into the SUCCESS path.
        self.assertEqual(inline(lin, 0.5, 0.5, 0, 0, border, (9.0, 9.0, 9.0, 9.0)),
                         ops.sample(lin, 0.5, 0.5, 0, 0, border))

    def test_gamut_matrices_match(self):
        for name in ("_M_AdobeRGB_to_Rec709", "_M_P3D65_to_Rec709",
                     "_M_Rec2020_to_Rec709", "_M_AP0_to_Rec709", "_M_AP1_to_Rec709",
                     "_M_AlexaWide_to_Rec709", "_M_REDWide_to_Rec709",
                     "_M_SGamut3_to_Rec709"):
            self.assertTrue(np.array_equal(self.ns[name], getattr(ops, name)),
                            "gamut matrix drift: %s" % name)


if __name__ == "__main__":
    unittest.main()
