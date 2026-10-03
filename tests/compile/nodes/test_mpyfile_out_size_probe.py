"""A compiled mPyFile reports the size of its own fileName, whatever its compute reads.

The interpreted node derives ``outSize`` through its own ``read_texture()``:
the dimensions of ``fileName`` at the node's presets, read on every node. The
compiled tail only probed when the spec carried all five presets, so a node
whose compute reads no fileName -- the composite (string-array layers) and the
Game of Life bake -- reported (0, 0). Measured 2026-10-03 on the shipped
builds with test_grid.png in fileName: interpreted 1024 x 1024, compiled 0 x 0,
on valid, valid -> empty -> valid and valid -> missing -> valid alike.

read_texture() also falls back to the node's baked ``embeddedImage`` bytes when
fileName does not load. The compiled tail took no such fallback, and neither
did the full-parity glue a default mPyFile compiles to: measured 2026-10-03 on
scratch builds of specs carrying a 5 x 3 PNG, a blank or missing fileName read
(5, 3) and the embedded colours interpreted, (0, 0) compiled -- and magenta on
the default node. ``TestEmbeddedFallback`` pins the retry.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _spec(template):
    man = os.path.join(_paths.ROOT, "templates", "MPyFile", template, "build",
                       "manifest.json")
    with open(man, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


def _tail(cpp):
    """The derived outSize block at the end of compute()."""
    return cpp.split("float _ndW = 0.0f, _ndH = 0.0f;", 1)[1].split(
        "_hOS.setClean();", 1)[0]


_BASE_READS = [
    "const MString _ndPFn = data.inputValue(aFileName).asString();",
    "const short _ndPCs = data.inputValue(aColorSpace).asShort();",
    "const bool _ndPPf = data.inputValue(aPreFilter).asBool();",
    "const short _ndPKn = data.inputValue(aPreFilterKernel).asShort();",
    "const float _ndPRd = data.inputValue(aPreFilterRadius).asFloat();",
]


class TestOutSizeProbe(unittest.TestCase):

    def test_game_of_life_loads_its_base_file_name(self):
        from mpynode.native import compiler as codegen

        spec = _spec("Game Of Life Texture")
        self.assertNotIn("fileName", spec["inputs"])
        cpp  = codegen.generate_cpp(spec, for_port=True)
        tail = _tail(cpp)
        for line in _BASE_READS:
            self.assertIn(line, tail)
        self.assertIn("nd_tex_load_linear(_texCache, _texMutex, _ndPFn, "
                      "(int)_ndPCs, _ndPPf != 0, (int)_ndPKn, (float)_ndPRd, "
                      "_ndPW, _ndPH)", tail)
        # the cache it loads through comes with it -- the node bakes, it
        # never samples, so nothing else declared one
        self.assertIn("    NdTexCache _texCache;", cpp)
        self.assertIn("static const float* nd_tex_load_linear(", cpp)

    def test_composite_mixes_spec_locals_and_base_reads(self):
        from mpynode.native import compiler as codegen

        spec = _spec("File Composite")
        self.assertNotIn("fileName", spec["inputs"])
        self.assertIn("colorSpace", spec["inputs"])
        tail = _tail(codegen.generate_cpp(spec, for_port=True))
        self.assertIn(_BASE_READS[0], tail)
        self.assertIn("nd_tex_load_linear(_texCache, _texMutex, _ndPFn, "
                      "(int)in_aColorSpace, in_aPreFilter != 0, "
                      "(int)in_aPreFilterKernel, (float)in_aPreFilterRadius, "
                      "_ndPW, _ndPH)", tail)

    def test_a_node_carrying_all_five_is_unchanged(self):
        from mpynode.native import compiler as codegen

        tail = _tail(codegen.generate_cpp(_spec("File Simple"), for_port=True))
        self.assertNotIn("data.inputValue", tail)
        self.assertIn("nd_tex_load_linear(_texCache, _texMutex, in_aFileName, "
                      "(int)in_aColorSpace, in_aPreFilter != 0, "
                      "(int)in_aPreFilterKernel, (float)in_aPreFilterRadius, "
                      "_ndPW, _ndPH)", tail)

    def test_every_shipped_texture_path_mpyfile_probes(self):
        from mpynode.native import compiler as codegen

        for tpl in ("File Simple", "File Composite", "File Scanline",
                    "Game Of Life Texture"):
            with self.subTest(template=tpl):
                cpp = codegen.generate_cpp(_spec(tpl), for_port=True)
                self.assertIn("nd_tex_load_linear(_texCache, _texMutex, ",
                              _tail(cpp))
                self.assertEqual(cpp.count("    NdTexCache _texCache;"), 1)

    def test_a_raw_image_port_reads_its_own_decode_back(self):
        # Brightness Contrast is a hand-ported pixel tap: its raw cache already
        # holds fileName, so outSize reads that decode back -- no texture cache.
        from mpynode.native import compiler as codegen

        spec = _spec("File Brightness Contrast")
        self.assertIn("fileName", spec["inputs"])
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn("nd_img_load_raw(_imgRawCache, _imgRawMutex, in_aFileName, "
                      "_ndPW, _ndPH, _ndPPx)", _tail(cpp))
        self.assertNotIn("nd_tex_load_linear", cpp)
        self.assertEqual(cpp.count(".readFromFile("), 1)

    def test_no_out_size_no_load(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        self.assertIsNone(ftc.out_size_loader([], [], True, False))
        self.assertIsNone(ftc.derived_output_lines([], [], [], {}, "tex") or None)

    def test_the_viewport_texel_does_not_take_a_cache_it_never_uses(self):
        # The Game of Life body never samples: the outSize load after it must
        # not thread the cache into nd_texel.
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import emit_vp2_override as vp2

        spec = _spec("Game Of Life Texture")
        inj = vp2.inject_vp2_override(codegen.generate_cpp(spec, for_port=True),
                                      spec)
        sig = inj.split("static void nd_texel(", 1)[1].split(")", 1)[0]
        self.assertNotIn("_texCache", sig)
        # a body that samples still gets the pair
        spec = _spec("File Simple")
        inj = vp2.inject_vp2_override(codegen.generate_cpp(spec, for_port=True),
                                      spec)
        sig = inj.split("static void nd_texel(", 1)[1].split(")", 1)[0]
        self.assertIn("NdTexCache& _texCache", sig)


def _tiny_png():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (5, 3), (10, 20, 30, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _with_bytes(spec):
    spec = copy.deepcopy(spec)
    spec["suggested"]["embedded_image_b64"] = base64.b64encode(
        _tiny_png()).decode("ascii")
    return spec


def _body(cpp):
    """compute() up to the derived outputs (the tail is checked apart)."""
    return cpp.split("::compute(", 1)[1].split(
        "// --- mPyFile derived outputs", 1)[0]


_TEX_RETRY = "nd_tex_load_linear(_texCache, _texMutex, _ndPEmb, "
_RAW_RETRY = ("nd_img_load_raw(_imgEmbedCache, _imgEmbedMutex, _ndPEmb, "
              "_ndPW, _ndPH, _ndPPx)")


class TestEmbeddedFallback(unittest.TestCase):
    """A fileName that does not load falls back to the baked bytes, as the
    interpreted read_texture() does, in the outSize tail and the glue."""

    def _cpp(self, spec):
        from mpynode.native import compiler as codegen

        return codegen.generate_cpp(spec, for_port=True)

    def test_the_blessed_tail_retries_the_embedded_image(self):
        cpp  = self._cpp(_with_bytes(_spec("File Simple")))
        tail = _tail(cpp)
        self.assertIn("MString _ndPEmb = nd_img_embedded_path();", tail)
        self.assertIn(_TEX_RETRY + "(int)in_aColorSpace, in_aPreFilter != 0, "
                      "(int)in_aPreFilterKernel, (float)in_aPreFilterRadius, "
                      "_ndPW, _ndPH)", tail)

    def test_the_composite_tail_retries_and_its_layers_do_not(self):
        # A layer path is an explicit read_texture(path): "read THIS file", so
        # a blank layer drops out instead of painting the embedded image. The
        # node's own fileName, which outSize reports, still falls back.
        cpp = self._cpp(_with_bytes(_spec("File Composite")))
        self.assertIn("static MString nd_img_embedded_path()", cpp)
        self.assertIn(_TEX_RETRY + "(int)in_aColorSpace, ", _tail(cpp))
        self.assertNotIn("nd_img_embedded_path()", _body(cpp))

    def test_the_raw_tail_retries_through_the_second_slot(self):
        cpp = self._cpp(_with_bytes(_spec("File Brightness Contrast")))
        self.assertIn("NdImgRawCache _imgEmbedCache;", cpp)
        self.assertIn(_RAW_RETRY, _tail(cpp))

    def test_the_full_parity_glue_retries_the_embedded_image(self):
        import maya.cmds as cmds
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc
        from mpynode.native.spec import spec_extractor
        from mpynode.wrappers.mpy_file import MPyFile

        cmds.file(new=True, force=True)
        w = MPyFile.create(name="embGlue#")
        w.set_variable("embeddedImage", _tiny_png())
        spec = spec_extractor.extract_spec(w.get_name())
        self.assertTrue(ftc.use_full_parity_glue(spec))
        cpp  = self._cpp(spec)
        body = _body(cpp)
        self.assertIn("verified file-texture pipeline",            body)
        self.assertIn("static MString nd_img_embedded_path()",     cpp)
        self.assertIn("MString _linEmb = nd_img_embedded_path();", body)
        self.assertIn("_lin = nd_tex_load_linear(_texCache, _texMutex, _linEmb,",
                      body)
        self.assertIn(_TEX_RETRY, _tail(cpp))

    def test_no_bytes_no_retry(self):
        for tpl in ("File Simple", "File Composite",
                    "File Brightness Contrast", "Game Of Life Texture"):
            with self.subTest(template=tpl):
                cpp = self._cpp(_spec(tpl))
                self.assertNotIn("nd_img_embedded_path", cpp)
                self.assertNotIn("_ndPEmb", cpp)


if __name__ == "__main__":
    unittest.main()
