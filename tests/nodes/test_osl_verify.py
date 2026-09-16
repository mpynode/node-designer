"""OSL increment 3 -- the render-compare verifier (osl_verify).

Two tiers, mirroring how increment 2 is tested:

* PURE CORE (no Maya, no renderer): the PFM readback, the image-diff metric and
  the compare harness driven by FAKE ``render_fn``s. These are the honesty
  tests -- above all that a MISSING renderer reports ``ran=False`` and never
  reads as a pass.
* REAL ARNOLD: the shipped ``render_osl_via_arnold`` backend driven against the
  actual ``oslc``/``kick``/``oiiotool`` on this machine. ``skipTest`` when they
  are absent (a skip is VISIBLE in the run; a silent pass would not be).
"""

from __future__ import annotations

import os
import struct
import tempfile
import unittest


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _pfm_bytes(width, height, pixels, little_endian=True):
    """Serialize a bottom-row-first RGB float list into PFM bytes."""
    scale  = -1.0 if little_endian else 1.0
    header = ("PF\n%d %d\n%f\n" % (width, height, scale)).encode("ascii")
    fmt    = ("<" if little_endian else ">") + "%df" % len(pixels)
    return header + struct.pack(fmt, *pixels)


def _ramp(width, height, scale=1.0, offset=0.0):
    """RGB image where R=u, G=v, B=0.25 (the probe shader's look)."""
    px = []
    for row in range(height):
        for col in range(width):
            u = (col + 0.5) / width
            v = (row + 0.5) / height
            px += [u * scale + offset, v * scale + offset, 0.25]
    return px


def _flat(width, height, value=0.0):
    return [value] * (width * height * 3)


def _worst_uv_error(img):
    """Largest deviation of a rendered frame from the analytic
    ``color(u, v, 0.25)``, over EVERY pixel."""
    from mpynode._common.osl.osl_verify import pixel_at
    worst = 0.0
    for row in range(img.height):
        for col in range(img.width):
            red, green, blue = pixel_at(img, col, row)[:3]
            worst = max(worst,
                        abs(red - (col + 0.5) / img.width),
                        abs(green - (row + 0.5) / img.height),
                        abs(blue - 0.25))
    return worst


_PROBE_OSL = (
    "shader mpy_probe(output color outColor = color(0))\n"
    "{\n"
    "    outColor = color(u, v, 0.25);\n"
    "}\n"
)

# Same look, different spelling -- must COMPARE EQUAL.
_PROBE_OSL_EQUIVALENT = (
    "shader mpy_probe_twin(output color outColor = color(0))\n"
    "{\n"
    "    float uu = u;\n"
    "    float vv = v;\n"
    "    outColor = color(uu, vv, 0.5 * 0.5);\n"
    "}\n"
)

# u and v swapped -- must COMPARE DIFFERENT (anti-vacuousness).
_PROBE_OSL_DIFFERENT = (
    "shader mpy_probe_swapped(output color outColor = color(0))\n"
    "{\n"
    "    outColor = color(v, u, 0.25);\n"
    "}\n"
)


# ==========================================================================
# PURE CORE -- PFM readback
# ==========================================================================
class TestReadPfm(unittest.TestCase):
    def _write(self, data):
        fd, path = tempfile.mkstemp(suffix=".pfm")
        os.close(fd)
        with open(path, "wb") as fh:
            fh.write(data)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_reads_shape_and_pixels(self):
        from mpynode._common.osl.osl_verify import read_pfm
        px  = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1]
        img = read_pfm(self._write(_pfm_bytes(2, 2, px)))
        self.assertEqual((img.width, img.height, img.channels), (2, 2, 3))
        for got, want in zip(img.pixels, px):
            self.assertAlmostEqual(got, want, places=5)

    def test_row_zero_is_the_bottom_row(self):
        """PFM stores bottom-up; the verifier's contract is row 0 == v LOW."""
        from mpynode._common.osl.osl_verify import read_pfm, pixel_at
        # bottom row green=0, top row green=1
        px = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
              0.0, 1.0, 0.0, 0.0, 1.0, 0.0]
        img = read_pfm(self._write(_pfm_bytes(2, 2, px)))
        self.assertEqual(pixel_at(img, 0, 0)[1], 0.0)
        self.assertEqual(pixel_at(img, 0, 1)[1], 1.0)

    def test_big_endian_scale_is_honoured(self):
        from mpynode._common.osl.osl_verify import read_pfm
        px  = [1.0, 2.0, 3.0]
        img = read_pfm(self._write(_pfm_bytes(1, 1, px, little_endian=False)))
        self.assertEqual([round(p, 4) for p in img.pixels], [1.0, 2.0, 3.0])

    def test_truncated_file_is_rejected(self):
        from mpynode._common.osl.osl_verify import read_pfm
        data = _pfm_bytes(4, 4, _flat(4, 4))[:-20]
        with self.assertRaises(ValueError):
            read_pfm(self._write(data))


# ==========================================================================
# PURE CORE -- the image-diff metric
# ==========================================================================
class TestDiffImages(unittest.TestCase):
    def _img(self, w, h, px):
        from mpynode._common.osl.osl_verify import OslImage
        return OslImage(w, h, 3, px)

    def test_identical_images_diff_to_zero(self):
        from mpynode._common.osl.osl_verify import diff_images
        a = self._img(4, 4, _ramp(4, 4))
        d = diff_images(a, self._img(4, 4, _ramp(4, 4)))
        self.assertEqual(d.max_abs,        0.0)
        self.assertEqual(d.mean_abs,       0.0)
        self.assertEqual(d.rms,            0.0)
        self.assertEqual(d.over_tolerance, 0)

    def test_uniform_offset_reports_that_offset(self):
        from mpynode._common.osl.osl_verify import diff_images
        a = self._img(4, 4, _flat(4, 4, 0.25))
        b = self._img(4, 4, _flat(4, 4, 0.30))
        d = diff_images(a, b)
        self.assertAlmostEqual(d.max_abs,  0.05, places=6)
        self.assertAlmostEqual(d.mean_abs, 0.05, places=6)
        self.assertAlmostEqual(d.rms,      0.05, places=6)

    def test_over_tolerance_counts_samples_not_pixels(self):
        from mpynode._common.osl.osl_verify import diff_images
        px_a    = _flat(2, 1, 0.0)
        px_b    = list(px_a)
        px_b[0] = 1.0          # one channel of one pixel blows the tolerance
        d = diff_images(self._img(2, 1, px_a), self._img(2, 1, px_b),
                        tolerance=1e-3)
        self.assertEqual(d.over_tolerance, 1)
        self.assertAlmostEqual(d.over_fraction, 1.0 / 6.0, places=6)

    def test_shape_mismatch_raises(self):
        from mpynode._common.osl.osl_verify import diff_images
        with self.assertRaises(ValueError):
            diff_images(self._img(4, 4, _flat(4, 4)),
                        self._img(2, 2, _flat(2, 2)))


class TestImageIsConstant(unittest.TestCase):
    def _img(self, w, h, px):
        from mpynode._common.osl.osl_verify import OslImage
        return OslImage(w, h, 3, px)

    def test_flat_image_is_constant(self):
        from mpynode._common.osl.osl_verify import image_is_constant
        self.assertTrue(image_is_constant(self._img(4, 4, _flat(4, 4, 0.7))))

    def test_ramp_is_not_constant(self):
        from mpynode._common.osl.osl_verify import image_is_constant
        self.assertFalse(image_is_constant(self._img(4, 4, _ramp(4, 4))))

    def test_variation_under_tolerance_counts_as_constant(self):
        from mpynode._common.osl.osl_verify import image_is_constant
        img = self._img(4, 4, _ramp(4, 4, scale=1e-9))
        self.assertTrue(image_is_constant(img, tolerance=1e-3))


# ==========================================================================
# PURE CORE -- the compare harness (fake render_fn)
# ==========================================================================
def _fake_render(mapping, calls=None):
    """render_fn returning a canned (image|None, error) per OSL source."""
    from mpynode._common.osl.osl_verify import OslImage

    def render_fn(osl_src, width, height):
        if calls is not None:
            calls.append((osl_src, width, height))
        entry = mapping[osl_src]
        if entry is None:
            return None, "fake renderer says no"
        return OslImage(width, height, 3, entry(width, height)), ""
    return render_fn


class TestCompareRenders(unittest.TestCase):
    def test_matching_renders_pass(self):
        from mpynode._common.osl.osl_verify import compare_renders
        fn  = _fake_render({"A": _ramp, "B": _ramp})
        res = compare_renders("A", "B", fn, width=4, height=4)
        self.assertTrue(res.ran)
        self.assertTrue(res.passed)
        self.assertEqual(res.diff.max_abs, 0.0)

    def test_diverging_renders_fail_with_stats(self):
        from mpynode._common.osl.osl_verify import compare_renders
        fn = _fake_render({
            "A": _ramp,
            "B": lambda w, h: _ramp(w, h, offset=0.5),
        })
        res = compare_renders("A", "B", fn, width=4, height=4)
        self.assertTrue(res.ran, "it DID run -- it just did not match")
        self.assertFalse(res.passed)
        self.assertAlmostEqual(res.diff.max_abs, 0.5, places=6)

    def test_tolerance_is_the_pass_criterion(self):
        from mpynode._common.osl.osl_verify import compare_renders
        fn = _fake_render({
            "A": _ramp,
            "B": lambda w, h: _ramp(w, h, offset=1e-4),
        })
        self.assertFalse(
            compare_renders("A", "B", fn, width=4, height=4,
                            tolerance=1e-6).passed)
        self.assertTrue(
            compare_renders("A", "B", fn, width=4, height=4,
                            tolerance=1e-3).passed)

    def test_requested_size_reaches_the_renderer(self):
        from mpynode._common.osl.osl_verify import compare_renders
        calls = []
        fn    = _fake_render({"A": _ramp, "B": _ramp}, calls=calls)
        compare_renders("A", "B", fn, width=7, height=5)
        self.assertEqual(calls, [("A", 7, 5), ("B", 7, 5)])


class TestNoRendererIsNotAPass(unittest.TestCase):
    """The T25 ``verify_ran=false`` defect class: absence of a renderer must
    NEVER be reportable as a pass."""

    def test_first_render_unavailable_reports_not_ran(self):
        from mpynode._common.osl.osl_verify import compare_renders
        fn  = _fake_render({"A": None, "B": _ramp})
        res = compare_renders("A", "B", fn, width=4, height=4)
        self.assertFalse(res.ran)
        self.assertFalse(res.passed)
        self.assertIn("fake renderer says no", res.reason)

    def test_second_render_unavailable_reports_not_ran(self):
        from mpynode._common.osl.osl_verify import compare_renders
        fn  = _fake_render({"A": _ramp, "B": None})
        res = compare_renders("A", "B", fn, width=4, height=4)
        self.assertFalse(res.ran)
        self.assertFalse(res.passed)

    def test_result_is_falsey_when_it_did_not_run(self):
        """``if result:`` must not read a non-run as success."""
        from mpynode._common.osl.osl_verify import compare_renders
        not_run = compare_renders("A", "B", _fake_render({"A": None}),
                                  width=4, height=4)
        ok = compare_renders("A", "B", _fake_render({"A": _ramp, "B": _ramp}),
                             width=4, height=4)
        self.assertFalse(bool(not_run))
        self.assertTrue(bool(ok))

    def test_render_fn_raising_is_reported_not_swallowed(self):
        from mpynode._common.osl.osl_verify import compare_renders

        def boom(osl_src, width, height):
            raise RuntimeError("renderer exploded")

        res = compare_renders("A", "B", boom, width=4, height=4)
        self.assertFalse(res.ran)
        self.assertFalse(res.passed)
        self.assertIn("renderer exploded", res.reason)


class TestPassedIsClampedToRan(unittest.TestCase):
    """T108. Every other case reaches ``RenderCompareResult`` through
    ``compare_renders``, which never asks for ``passed=True`` on a comparison
    that did not happen -- so the ``and self.ran`` clamp in ``__init__`` was
    never aimed at, and deleting it left the whole module green. Constructing
    the result DIRECTLY is the only way to exercise the clamp that the class
    docstring's honesty contract ("NEVER True when ``ran`` is False") rests on.
    """

    def _res(self, ran, passed):
        from mpynode._common.osl.osl_verify import RenderCompareResult
        return RenderCompareResult(ran, passed, "")

    def test_a_pass_claimed_without_a_run_is_forced_false(self):
        res = self._res(False, True)
        self.assertFalse(res.passed)
        self.assertFalse(bool(res))

    def test_the_clamp_leaves_a_real_pass_alone(self):
        res = self._res(True, True)
        self.assertTrue(res.passed)
        self.assertTrue(bool(res))


class TestVacuousComparisonIsNotAPass(unittest.TestCase):
    """Two featureless renders 'match' but prove nothing -- the trap when a
    texture-sampling shader renders black because its ``filename`` parameter
    was never set."""

    def test_two_constant_images_do_not_pass(self):
        from mpynode._common.osl.osl_verify import compare_renders
        fn  = _fake_render({"A": _flat, "B": _flat})
        res = compare_renders("A", "B", fn, width=4, height=4)
        self.assertTrue(res.ran)
        self.assertFalse(res.passed)
        self.assertIn("vacuous", res.reason.lower())

    def test_one_constant_one_varying_still_compares(self):
        from mpynode._common.osl.osl_verify import compare_renders
        fn  = _fake_render({"A": _flat, "B": _ramp})
        res = compare_renders("A", "B", fn, width=4, height=4)
        self.assertTrue(res.ran)
        self.assertFalse(res.passed)
        self.assertNotIn("vacuous", res.reason.lower())


class TestCompareRenderToReference(unittest.TestCase):
    def _img(self, w, h, px):
        from mpynode._common.osl.osl_verify import OslImage
        return OslImage(w, h, 3, px)

    def test_matches_reference(self):
        from mpynode._common.osl.osl_verify import compare_render_to_reference
        ref = self._img(4, 4, _ramp(4, 4))
        res = compare_render_to_reference("A", ref, _fake_render({"A": _ramp}))
        self.assertTrue(res.ran)
        self.assertTrue(res.passed)

    def test_render_size_follows_the_reference(self):
        from mpynode._common.osl.osl_verify import compare_render_to_reference
        calls = []
        ref   = self._img(7, 5, _ramp(7, 5))
        compare_render_to_reference("A", ref,
                                    _fake_render({"A": _ramp}, calls=calls))
        self.assertEqual(calls, [("A", 7, 5)])

    def test_missing_renderer_is_not_a_pass(self):
        from mpynode._common.osl.osl_verify import compare_render_to_reference
        ref = self._img(4, 4, _ramp(4, 4))
        res = compare_render_to_reference("A", ref, _fake_render({"A": None}))
        self.assertFalse(res.ran)
        self.assertFalse(res.passed)


# ==========================================================================
# REAL ARNOLD -- the shipped standalone backend
# ==========================================================================
class _ArnoldCase(unittest.TestCase):
    def setUp(self):
        from mpynode._common.osl.osl_verify import find_arnold_tools
        self.tools = find_arnold_tools()
        if self.tools is None:
            self.skipTest("Arnold standalone tools (oslc/kick/oiiotool) "
                          "not found on this machine")


class TestFindArnoldTools(unittest.TestCase):
    def test_bogus_override_finds_nothing(self):
        from mpynode._common.osl.osl_verify import find_arnold_tools
        self.assertIsNone(find_arnold_tools(search_dirs=["/nonexistent/bin"],
                                            use_defaults=False))

    def test_override_dir_is_searched(self):
        from mpynode._common.osl.osl_verify import find_arnold_tools
        real = find_arnold_tools()
        if real is None:
            self.skipTest("no Arnold on this machine")
        found = find_arnold_tools(
            search_dirs=[os.path.dirname(real.kick)], use_defaults=False)
        self.assertIsNotNone(found)
        self.assertEqual(found.kick, real.kick)


class TestRenderOslViaArnold(_ArnoldCase):
    def test_renders_the_uv_grid_the_contract_promises(self):
        """row 0 == v low, col 0 == u low, pixel centres -- EVERY pixel."""
        from mpynode._common.osl.osl_verify import render_osl_via_arnold
        img, err = render_osl_via_arnold(_PROBE_OSL, 32, 32, tools=self.tools)
        self.assertIsNotNone(img, "render failed: %s" % err)
        self.assertEqual((img.width, img.height), (32, 32))
        self.assertLess(_worst_uv_error(img), 1e-5)

    def test_uncompilable_osl_returns_the_oslc_diagnostic(self):
        from mpynode._common.osl.osl_verify import render_osl_via_arnold
        img, err = render_osl_via_arnold(
            "shader broken(output color outColor = color(0)) { this is not osl }",
            16, 16, tools=self.tools)
        self.assertIsNone(img)
        self.assertTrue(err.strip(), "a compile failure must carry a reason")
        self.assertIn("error", err.lower())

    def test_watermarked_render_above_the_safe_size_is_refused(self):
        """Unlicensed Arnold stamps watermarks over larger frames, which would
        silently corrupt every pixel metric. Either we are licensed (clean
        image) or the backend REFUSES rather than returning junk."""
        from mpynode._common.osl.osl_verify import (
            render_osl_via_arnold, WATERMARK_SAFE_MAX)
        size = WATERMARK_SAFE_MAX * 2
        img, err = render_osl_via_arnold(_PROBE_OSL, size, size,
                                         tools=self.tools)
        if img is None:
            self.assertIn("watermark", err.lower())
            return
        # Licensed Arnold: the frame has to be clean EVERYWHERE. Spot-checking
        # a few pixels is NOT enough -- the watermark is a localized stamp, so
        # a 3-pixel sample passes straight through a contaminated frame.
        self.assertLess(
            _worst_uv_error(img), 1e-3,
            "a %dpx frame came back contaminated -- the watermark guard did "
            "not fire and every pixel metric downstream is now junk" % size)


class TestRenderCompareWithRealArnold(_ArnoldCase):
    def _fn(self):
        from mpynode._common.osl.osl_verify import make_arnold_render_fn
        return make_arnold_render_fn(tools=self.tools)

    def test_equivalent_shaders_compare_equal(self):
        from mpynode._common.osl.osl_verify import compare_renders
        res = compare_renders(_PROBE_OSL, _PROBE_OSL_EQUIVALENT, self._fn(),
                              width=32, height=32)
        self.assertTrue(res.ran, res.reason)
        self.assertTrue(res.passed, res.reason)

    def test_swapped_uv_shaders_are_caught(self):
        from mpynode._common.osl.osl_verify import compare_renders
        res = compare_renders(_PROBE_OSL, _PROBE_OSL_DIFFERENT, self._fn(),
                              width=32, height=32)
        self.assertTrue(res.ran, res.reason)
        self.assertFalse(res.passed,
                         "u/v swap must NOT read as a match: %s" % res.reason)
        self.assertGreater(res.diff.max_abs, 0.5)

    def test_uncompilable_arm_is_not_a_pass(self):
        from mpynode._common.osl.osl_verify import compare_renders
        res = compare_renders(_PROBE_OSL, "not an osl shader at all",
                              self._fn(), width=16, height=16)
        self.assertFalse(res.ran)
        self.assertFalse(res.passed)


if __name__ == "__main__":
    unittest.main()
