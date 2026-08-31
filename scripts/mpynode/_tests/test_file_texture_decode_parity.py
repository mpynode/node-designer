"""Guards for the two defects that made a compiled mPyFile disagree with its
interpreted twin, neither of which any existing test could see.

1. THE BAKE GRID. ``emit_vp2_override`` CPU-bakes the texture VP2 uploads. It
   had silently reverted to a 256x256 synthetic grid sampled at texel CENTRES
   with the node's wrap mode applied -- a 4x resolution drop and a WRAP fold at
   u == 1.0. Every one of the suite's tests passed throughout, because nothing
   asserted anything about the emitted bake at all.

2. THE DECODER. MImage returns ASSOCIATED (premultiplied) alpha quantised to 8
   bits; a PNG stores straight alpha. The tiers have to agree on which decoder
   ran, and the exact decoders have to agree byte-for-byte with each other.

Both are asserted on the REAL shipped template, not a hand-rolled spec, because
what regressed was the real template's output.
"""
from __future__ import annotations

import glob
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import struct
import unittest
import zlib

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


def _composite_cpp():
    """Generate the shipped File Composite node's finalized C++ (codegen +
    the VP2 override splice), the same way the build does."""
    from mpynode._common.io import mpn_io
    from mpynode.native.spec import mpn_spec_adapter
    from mpynode.native.compiler import node_scaffold
    from mpynode.native.compiler import emit_vp2_override as vp2

    p = os.path.join(_repo_root(), "templates", "MPyFile", "File Composite",
                     "template.mpn")
    payload = mpn_io.load_mpn(p, trusted=True)
    spec = mpn_spec_adapter.spec_from_mpn_payload(payload)
    return vp2.inject_vp2_override(
        node_scaffold.generate_cpp(spec, for_port=False), spec)


class TestBakeGrid(unittest.TestCase):
    """The VP2 bake must sample the same lattice the interpreted viewport
    uploads: full source resolution, CORNER convention, clamped."""

    @classmethod
    def setUpClass(cls):
        cls.cpp = _composite_cpp()

    def test_bake_uses_the_corner_grid(self):
        # The sampler does fx = u * (W - 1), so the texel-exact grid is
        # x / (W - 1) -- NOT the texel-centre (x + 0.5) / W.
        self.assertIn("(double)x / (double)(_w > 1 ? _w - 1 : 1)", self.cpp)
        self.assertIn("(double)py / (double)(_h > 1 ? _h - 1 : 1)", self.cpp)
        self.assertNotIn("((double)x + 0.5) / (double)_w", self.cpp)
        self.assertNotIn("((double)py + 0.5) / (double)_h", self.cpp)

    def test_bake_resolution_comes_from_the_layers(self):
        # A fixed 256x256 was the regression: it quarters a 1024 source.
        self.assertNotIn("const unsigned int _w = 256, _h = 256;", self.cpp)
        self.assertIn("for (size_t _li = 0; _li < _m_in_aLayers.size()", self.cpp)

    def test_bake_is_not_size_capped(self):
        # The interpreted tier uploads at the source's full resolution. Any cap
        # hands VP2 a differently-sized texture than the interpreted twin, and
        # its filtering then makes the two disagree everywhere -- a 1024 cap put
        # 26% of a 2048 source's texels wrong.
        self.assertNotIn("_kMaxBake", self.cpp)

    def test_bake_forces_clamp_but_compute_keeps_the_node_wrap(self):
        # fmod(1.0, 1.0) == 0, so a wrap-mode bake folds the last column back
        # onto the first. The BAKE clamps; compute() must still honour the
        # node's own wrap inputs -- the clamp must not leak out of the bake.
        self.assertIn("kTexClamp", self.cpp)
        self.assertNotIn("kTexWrap", self.cpp)
        self.assertIn("in_aWrapModeU, in_aWrapModeV", self.cpp)


class TestExactDecodeIsEmitted(unittest.TestCase):
    """The compiled tier must carry the exact decoder and reach for it first."""

    @classmethod
    def setUpClass(cls):
        cls.cpp = _composite_cpp()

    def test_decoder_is_present_and_tried_before_mimage(self):
        self.assertIn("static bool nd_png_supported(", self.cpp)
        self.assertIn("static bool nd_png_decode(", self.cpp)
        self.assertIn("nd_png_decode_file(path.asChar()", self.cpp)
        # The exact path decodes STRAIGHT alpha, so it must not un-premultiply;
        # the MImage fallback must.
        self.assertIn("nd_tex_linearize(&px8[0], W, H, cs, lin, /*unpremult=*/false)",
                      self.cpp)
        self.assertIn("nd_tex_linearize(px, W, H, cs, lin, /*unpremult=*/true)",
                      self.cpp)

    def test_emitted_predicate_matches_the_python_one(self):
        """The two predicates decide WHICH decoder runs. If they could ever
        disagree, one tier would read straight alpha and the other associated
        alpha from the same file -- so the accept/decline rules are pinned on
        both sides and compared here."""
        from mpynode._common.methods import file_texture_ops as ops

        # (depth, colour) -> supported? Built as real PNG headers so the actual
        # Python predicate runs, not a paraphrase of it.
        expect = {
            (1, 0): True, (2, 0): True, (4, 0): True, (8, 0): True, (16, 0): False,
            (8, 2): True, (16, 2): True, (1, 2): False, (4, 2): False,
            (1, 3): True, (2, 3): True, (4, 3): True, (8, 3): True, (16, 3): False,
            (8, 4): True, (16, 4): True, (1, 4): False,
            (8, 6): True, (16, 6): True, (2, 6): False,
            (8, 1): False, (8, 5): False, (8, 7): False,
        }
        for (depth, colour), want in sorted(expect.items()):
            hdr = ((4).to_bytes(4, "big") + (4).to_bytes(4, "big") +
                   bytes([depth, colour, 0, 0, 0]))
            data = (b"\x89PNG\r\n\x1a\n" +
                    len(hdr).to_bytes(4, "big") + b"IHDR" + hdr +
                    zlib.crc32(b"IHDR" + hdr).to_bytes(4, "big") +
                    (0).to_bytes(4, "big") + b"IDAT" +
                    zlib.crc32(b"IDAT").to_bytes(4, "big"))
            self.assertEqual(
                ops.png_supported(data), want,
                "depth=%d colour=%d: predicate disagrees with the C++ rules"
                % (depth, colour))

        # And the C++ source carries those same rules.
        self.assertIn("if (comp != 0 || filt != 0 || interlace != 0) return false;",
                      self.cpp)
        self.assertIn("if (bitDepth != 8 && bitDepth != 16) return false;", self.cpp)

    def test_interlaced_and_odd_pngs_are_declined_by_both(self):
        from mpynode._common.methods import file_texture_ops as ops

        def _png(depth, colour, interlace=0, extra=b""):
            hdr = ((4).to_bytes(4, "big") + (4).to_bytes(4, "big") +
                   bytes([depth, colour, 0, 0, interlace]))
            def ch(t, d):
                return (len(d).to_bytes(4, "big") + t + d +
                        zlib.crc32(t + d).to_bytes(4, "big"))
            return (b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", hdr) + extra +
                    ch(b"IDAT", b"") + ch(b"IEND", b""))

        self.assertFalse(ops.png_supported(_png(8, 6, interlace=1)),
                         "Adam7 must be declined -- it is not decoded here")
        self.assertFalse(ops.png_supported(_png(16, 0)),
                         "16-bit greyscale must be declined: PIL clips it")
        # tRNS is honoured on palette only; on grey/truecolour it is declined.
        trns = (struct.pack(">I", 6) + b"tRNS" + struct.pack(">HHH", 1, 2, 3) +
                zlib.crc32(b"tRNS" + struct.pack(">HHH", 1, 2, 3)).to_bytes(4, "big"))
        self.assertFalse(ops.png_supported(_png(8, 2, extra=trns)))
        self.assertFalse(ops.png_supported(b"not a png at all"))
        self.assertFalse(ops.png_supported(b""))


@unittest.skipIf(np is None, "numpy required")
class TestDecodersAgree(unittest.TestCase):
    """Every decoder the interpreted tier may reach must return the same bytes,
    or the node's output would depend on which libraries the host happens to
    have -- Maya 2024 ships no PIL, so this is a real configuration, not a
    hypothetical one."""

    def _pngs(self):
        root = _repo_root()
        out = []
        for sub in ("templates", os.path.join("scripts", "mpynode", "_demos")):
            out += sorted(glob.glob(os.path.join(root, sub, "**", "*.png"),
                                    recursive=True))
        return out

    def test_pure_python_matches_pil_on_every_shipped_texture(self):
        from mpynode._common.methods import file_texture_ops as ops
        if ops._PILImage is None:
            self.skipTest("PIL not available on this host")
        n = 0
        for p in self._pngs():
            with open(p, "rb") as fh:
                data = fh.read()
            if not ops.png_supported(data):
                continue
            got = ops.png_decode(data)
            self.assertIsNotNone(got, "supported but failed to decode: %s" % p)
            ref = np.asarray(ops._PILImage.open(p).convert("RGBA"), np.uint8)
            self.assertTrue(np.array_equal(got, ref),
                            "pure-Python decode != PIL for %s" % p)
            n += 1
        self.assertGreater(n, 0, "no shipped PNG was exercised")

    def test_decode_rgba8_reports_straight_alpha_for_png(self):
        """The premultiplied flag drives whether linearize un-associates. An
        exact PNG decode is straight, so the flag MUST be False -- reporting
        True would apply the correction twice."""
        from mpynode._common.methods import file_texture_ops as ops
        p = os.path.join(_repo_root(), "templates", "MPyFile", "File Composite",
                         "green_circle.png")
        if not os.path.isfile(p):
            self.skipTest("shipped texture missing")
        px, premultiplied = ops.decode_rgba8(p)
        self.assertFalse(premultiplied)
        self.assertEqual(px.shape[2], 4)
        self.assertEqual(px.dtype, np.uint8)

    def test_qt_path_matches_pure_python(self):
        from mpynode._common.methods import file_texture_ops as ops
        p = os.path.join(_repo_root(), "templates", "MPyFile", "File Composite",
                         "grid_bg.png")
        if not os.path.isfile(p):
            self.skipTest("shipped texture missing")
        with open(p, "rb") as fh:
            data = fh.read()
        qt = ops._qimage_rgba8(p, data[24])
        if qt is None:
            self.skipTest("no Qt binding on this host")
        self.assertTrue(np.array_equal(qt, ops.png_decode(data)),
                        "Qt decode != pure-Python decode")


if __name__ == "__main__":
    unittest.main()
