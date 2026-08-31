"""``composite_layers`` is the SSOT for stacking image layers. Three things
implement it and they must not drift:

  1. ``file_methods.composite_layers``      -- blessed scalar runtime (the SSOT)
  2. ``nd_tex_composite_layers``            -- the C++ kernel it lowers to
  3. the File Composite template's ``_composite_layers`` -- the VECTORIZED twin
     the Python viewport tier needs, because a per-texel Python call over a
     1024x1024 canvas is not usable

(1) and (2) are pinned by construction -- the compiled node calls the kernel and
nothing else. (1) and (3) cannot be one function (scalar vs whole-image), so
they are pinned HERE, the same way ``DEFAULT_INIT_SOURCE`` and
``file_texture_ops`` are pinned by ``test_file_texture_ops_drift``.

This is the test that would have caught the original defect: the viewport twin
carried an ``if op > 0.0`` filter the compute expression never had, so a layer
with zero/negative/NaN opacity previewed differently from how it rendered.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import standalone_init, ensure_plugins_loaded

try:
    import numpy as np
except ImportError:                                          # pragma: no cover
    np = None


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


_LDIR = os.path.join(_repo_root(), "templates", "MPyFile", "File Composite")
_NAMES = ("grid_bg.png", "red_square.png", "green_circle.png",
          "blue_triangle.png")


def _template():
    from mpynode._common.io import mpn_io
    return mpn_io.load_mpn(os.path.join(_LDIR, "template.mpn"), trusted=True)


class _Stub(object):
    """Enough of a node for the blessed runtime and the template helper.

    wrapMode is CLAMP because that is what the VP2 bake forces. On [0,1] clamp
    and wrap agree everywhere except at exactly 1.0, where wrap's fmod folds the
    last row/column onto the opposite edge -- comparing under wrap would just
    re-measure that fold instead of the compositing math.
    """
    fileName = ""
    colorSpace = 0
    preFilter = False
    preFilterKernel = 3
    preFilterRadius = 2.0
    wrapModeU = 1
    wrapModeV = 1
    borderColor = (0.0, 0.0, 0.0)

    def __init__(self, layers, opacities):
        self.layers = list(layers)
        self.opacities = list(opacities)

    def get_init_helper(self, name):
        # Force the framework helpers; this stub has no Init tab of its own.
        raise AttributeError(name)

    def read_texture(self, path=None):
        from mpynode._common.methods import file_methods
        return file_methods.read_texture(self, path)

    def sample_texture(self, buf, u, v, missing=None):
        from mpynode._common.methods import file_methods
        return file_methods.sample_texture(self, buf, u, v, missing=missing)


@unittest.skipIf(np is None, "numpy required")
class TestScalarAndImageFormsAgree(unittest.TestCase):
    """The whole-image viewport twin must equal the blessed scalar SSOT sampled
    on the bake's CORNER grid."""

    @classmethod
    def setUpClass(cls):
        for n in _NAMES:
            if not os.path.isfile(os.path.join(_LDIR, n)):
                raise unittest.SkipTest("shipped composite textures missing")
        ns = {"__name__": "tpl_init"}
        exec(compile(_template()["init_source"], "<init>", "exec"), ns)
        cls.image_fn = staticmethod(ns["_composite_layers"])
        cls.paths = [os.path.join(_LDIR, n) for n in _NAMES]

    # (y, x) probes: all four corners (where the grid convention bites) plus
    # interior points.
    GRID = ((0, 0), (0, 1023), (1023, 0), (1023, 1023), (1, 1), (512, 512),
            (37, 900), (900, 37), (255, 256))

    def _compare(self, opacities, layers=None):
        from mpynode._common.methods import file_methods
        stub = _Stub(layers if layers is not None else self.paths, opacities)
        img = type(self).image_fn(stub)
        self.assertIsNotNone(
            img, "the whole-image form returned None; the compiled tier always "
                 "uploads a canvas, so returning nothing is a divergence")
        h, w = img.shape[0], img.shape[1]
        worst = 0.0
        for (y, x) in self.GRID:
            if y >= h or x >= w:
                continue
            u = x / float(w - 1)
            v = 1.0 - y / float(h - 1)
            sc = np.asarray(file_methods.composite_layers(
                stub, stub.layers, stub.opacities, u, v), dtype=np.float64)
            im = img[y, x].astype(np.float64)
            # NaN in the same slot on both sides is agreement, not a diff.
            d = np.where(np.isnan(sc) & np.isnan(im), 0.0, np.abs(sc - im))
            worst = max(worst, float(np.nanmax(d)))
        # Measured worst over these cases is 3.3e-08 -- the scalar form
        # accumulates in Python float64, the image form in float32.
        self.assertLess(worst, 1e-6,
                        "scalar and whole-image composite disagree by %.3e "
                        "for opacities=%r" % (worst, opacities))
        return img

    def test_default_and_unit_weights(self):
        self._compare([])
        self._compare([1.0, 1.0, 1.0, 1.0])

    def test_fractional_weights(self):
        self._compare([1.0, 0.5, 0.25, 0.75])

    def test_zero_opacity_on_the_largest_layer(self):
        """Was D2: the viewport skipped zero-weight layers and sized its canvas
        over the survivors, so zeroing the biggest layer shrank the upload."""
        img = self._compare([0.0, 1.0, 1.0, 1.0])
        self.assertEqual(img.shape[:2], (1024, 1024),
                         "a zero-weight layer must still count toward the "
                         "canvas size -- compute never dropped it")

    def test_negative_opacity_subtracts_rather_than_skipping(self):
        """Was D3. `op` is a WEIGHT: skipping a layer and weighting it by a
        negative number are different results, and compute weights."""
        self._compare([1.0, -0.5, 1.0, 1.0])

    def test_nan_opacity_agrees(self):
        """Was D4. NaN must propagate the SAME way in both forms; what matters
        is that neither silently drops the layer while the other poisons it."""
        img = self._compare([1.0, float("nan"), 1.0, 1.0])
        self.assertTrue(np.isnan(img).any(),
                        "a NaN weight must reach the canvas, as it does in "
                        "compute")

    def test_all_layers_off_still_uploads_a_canvas(self):
        """Was D5: the viewport returned None (uploading nothing) while the
        compiled tier uploaded a transparent canvas."""
        img = self._compare([0.0, 0.0, 0.0, 0.0])
        self.assertEqual(img.shape[:2], (1024, 1024))
        self.assertAlmostEqual(float(np.abs(img).max()), 0.0, places=6)

    def test_unresolvable_layer_drops_out(self):
        self._compare([1.0, 1.0, 1.0],
                      layers=[self.paths[0], os.path.join(_LDIR, "nope.png"),
                              self.paths[2]])

    def test_short_opacities_default_to_one(self):
        self._compare([0.25])


class TestBlessedWiring(unittest.TestCase):
    """The method must be registered, lower to the kernel, and actually be what
    the shipped template calls."""

    def test_registered_and_lowers_to_the_kernel(self):
        from mpynode._common.interface import method_registry
        from mpynode._common.interface.api_methods import CppKernel
        specs = {m.name: m for m in method_registry.methods_for_type("mPyFile")}
        self.assertIn("composite_layers", specs)
        low = specs["composite_layers"].lower
        self.assertIsInstance(low, CppKernel)
        self.assertEqual(low.kernel, "nd_tex_composite_layers")

    def test_template_calls_the_blessed_method(self):
        expr = _template()["expression"]
        self.assertIn("self.composite_layers(", expr)
        # The hand-rolled stack it replaced must be gone, or there would be two
        # implementations again -- which is the whole defect.
        self.assertNotIn("cr = r * a + cr * (1.0 - a)", expr)

    def test_viewport_twin_has_no_opacity_gate(self):
        """The regression guard. This filter is what made the preview disagree
        with the render."""
        init = _template()["init_source"]
        self.assertIn("_composite_layers", init)
        self.assertNotIn("if op > 0.0", init)

    def test_scanline_viewport_does_not_clip(self):
        """Compute writes `r * scan` unclamped; clipping only in the viewport
        made the two disagree for colour spaces whose linear range exceeds 1."""
        from mpynode._common.io import mpn_io
        p = os.path.join(_repo_root(), "templates", "MPyFile", "File Scanline",
                         "template.mpn")
        vp = mpn_io.load_mpn(p, trusted=True)["viewport_source"]
        self.assertNotIn("np.clip(processed", vp)

    def test_emitted_cpp_carries_the_kernel_and_calls_it(self):
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter
        from mpynode.native.compiler import node_scaffold
        from mpynode.native.compiler import emit_vp2_override as vp2

        payload = mpn_io.load_mpn(os.path.join(_LDIR, "template.mpn"),
                                  trusted=True)
        spec = mpn_spec_adapter.spec_from_mpn_payload(payload)
        cpp = vp2.inject_vp2_override(
            node_scaffold.generate_cpp(spec, for_port=False), spec)
        self.assertIn("static void nd_tex_composite_layers(", cpp)
        self.assertIn("nd_tex_composite_layers(ndin_self_layers", cpp)
        # Lowered, not AI-ported.
        self.assertNotIn("AI PORT", cpp)
        # And the bake still probes every layer for the canvas size -- the
        # composite kernel hides the per-layer load, so the probe has to key off
        # the kernel rather than off an nd_tex_load_linear that is no longer
        # there.
        self.assertIn("for (size_t _li = 0; _li < _m_in_aLayers.size()", cpp)


if __name__ == "__main__":
    unittest.main()
