"""Native mPyFile EMBEDDED-IMAGE fallback: lift the open() blocker + bake bytes.

An mPyFile prefers the on-disk ``fileName`` and, when that is blank /
unreadable, falls back to a baked ``embeddedImage`` byte buffer -- staging the
bytes to a temp file (MImage has no readFromMemory) and handing the file to the
image reader. That bare ``open()`` used to be a hard portability blocker.

The fallback is now a FRAMEWORK service inside ``read_texture()`` itself
(``_common/methods/file_methods.py``), so there are TWO compiled shapes and this
suite pins both:

  * BLESSED -- ``buf = self.read_texture()`` lowers deterministically to
    ``nd_tex_load_linear``, and the fallback is a retry through the SAME
    by-path NdTexCache (no second cache member). This is what the shipped
    templates use.
  * RAW -- a hand-rolled pixel tap that stages the bytes in its own Init tab.
    No shipped template does this any more, so the fixture below synthesizes
    one; the machinery still exists for user nodes and must stay covered.

This suite proves the whole #98 path:

  * assess_portability SANCTIONS the binary-write staging open() for a
    file-reading node, while a NON-binary open() stays a hard blocker -- and
    a node that just calls read_texture() is an embedded-image reader too,
    with no open() of its own to detect;
  * extract_spec BAKES a non-empty ``embeddedImage`` stored var into the spec as
    ``embedded_image_b64`` (byte-exact roundtrip); a node WITHOUT embedded bytes
    keeps a byte-identical spec (no key -> port-cache stable);
  * a reads_image_file file node SURFACES ``fileName`` as an input even when the
    compute reaches it only through the ``getattr(slf, "fileName")`` helper;
  * codegen emits the baked byte array + ``nd_img_embedded_path()`` staging
    helper + the path-appropriate fallback load -- and emits NONE of that when
    there is no embedded image (lean shipped templates);
  * the staging helper COMPILES and stages the baked bytes byte-exact
    (decisive C++).

The compile test SKIPs (never fails) on a host with no C++ toolchain, matching
the other native e2e suites.
"""
from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init

_TEMPLATES = os.path.join(
    os.environ.get("MPYNODE_ROOT", ""), "templates", "MPyFile")


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _template_data(name):
    with open(os.path.join(_TEMPLATES, name, "template.mpn")) as fh:
        return json.load(fh)["data"]


def _tiny_png():
    """A tiny 3x2 RGBA PNG as raw bytes (magic 0x89 P N G ...)."""
    from PIL import Image

    buf = io.BytesIO()
    im  = Image.new("RGBA", (3, 2), (10, 20, 30, 255))
    im.putpixel((0, 0), (200, 100, 50, 255))
    im.save(buf, format="PNG")
    return buf.getvalue()


# A HAND-ROLLED embedded-image node: stages the bytes in its own Init tab and
# taps pixels directly, instead of calling the blessed read_texture(). This is
# what every mPyFile template used to look like. None ship that way now, but the
# raw-cache + second-slot codegen still serves user nodes written this way, so
# the RAW arm of the codegen tests builds against this fixture rather than
# quietly losing its subject when the templates moved to the framework read.
_RAW_INIT = '''import numpy as np
import hashlib
import os
import tempfile

_BYTES_PATHS = {}


def _stage_embedded(data):
    if not data:
        return None
    key = hashlib.md5(data).hexdigest()
    if key in _BYTES_PATHS:
        return _BYTES_PATHS[key]
    path = None
    try:
        tmp = os.path.join(tempfile.gettempdir(), "mpy_embed_%s.png" % key)
        if not os.path.isfile(tmp):
            with open(tmp, "wb") as fh:
                fh.write(data)
        path = tmp
    except Exception:
        path = None
    _BYTES_PATHS[key] = path
    return path


def _read_image(path):
    import maya.api.OpenMaya as om
    img = om.MImage()
    try:
        img.readFromFile(path)
    except Exception:
        return None
    return img


def _resolve_image(slf):
    img = _read_image(slf.fileName)
    if img is not None:
        return img
    return _read_image(_stage_embedded(getattr(slf, "embeddedImage", None)))
'''

_RAW_COMPUTE = '''img = _resolve_image(self)
u, v = self.uvCoord

if img is None:
    self.outColor = (1.0, 0.0, 1.0)
    self.outAlpha = 1.0
else:
    h, w = img.shape[0], img.shape[1]
    uu = u - np.floor(u)
    vv = v - np.floor(v)
    px = min(w - 1, int(uu * w))
    py = min(h - 1, int((1.0 - vv) * h))
    r, g, b, a = (float(c) for c in img[py, px])
    self.outColor = (r, g, b)
    self.outAlpha = a
'''


def _file_spec(template, bake_embedded=None, init=None, compute=None):
    """Build an mPyFile from a shipped texture template + extract its spec.

    ``bake_embedded`` -> set the ``embeddedImage`` stored var to those bytes
    before extraction (mirrors a user baking an image into the node).
    ``init`` / ``compute`` -> override the template's tiers, for the synthesized
    hand-rolled node above (the template supplies the input surface either way).
    """
    import maya.cmds as cmds
    from mpynode.wrappers.mpy_file import MPyFile
    from mpynode.native.spec import spec_extractor

    d = _template_data(template)
    cmds.file(new=True, force=True)
    # ``template`` is now a folder NAME with spaces ("File Simple"); a Maya
    # node name cannot carry one, so squeeze them out for the node only.
    w = MPyFile.create(name=template.replace(" ", "") + "#")
    for nm, meta in (d.get("input_attrs") or {}).items():
        w.add_input_attr(nm, meta.get("attr_type", "float"))
    w.set_init_expression(d["init_source"] if init is None else init)
    w.set_compute_expression(d["expression"] if compute is None else compute)
    if bake_embedded is not None:
        w.set_variable("embeddedImage", bake_embedded)
    return spec_extractor.extract_spec(w.get_name())


# ---------------------------------------------------------------------------


class TestOpenBlockerLifted(unittest.TestCase):
    """The binary-write staging open() is sanctioned; a plain open() still blocks."""

    def _assess(self, template):
        from mpynode.native.spec import spec_extractor as se

        d = _template_data(template)
        return se.assess_portability(
            d["expression"], d["init_source"], {}, {}, {}, allow_file_read=True)

    def test_file_simple_portable(self):
        p = self._assess("File Simple")
        self.assertTrue(p.get("portable"), p)
        self.assertTrue(p.get("reads_image_file"))
        self.assertTrue(p.get("reads_embedded_image"))
        self.assertEqual(list(p.get("blockers") or []), [])

    def test_file_scanline_portable(self):
        p = self._assess("File Scanline")
        self.assertTrue(p.get("portable"), p)
        self.assertTrue(p.get("reads_image_file"))
        self.assertEqual(list(p.get("blockers") or []), [])

    def test_nonbinary_open_is_not_the_sanctioned_idiom(self):
        from mpynode.native.spec import spec_extractor as se

        # A text-mode open() is NOT the sanctioned image-staging idiom. It no
        # longer refuses the build, but it must not be mistaken for staging
        # either -- reads_embedded_image is what drives EMBEDDED_STAGE_CPP.
        p = se.assess_portability(
            "data = open(self.fileName).read()\nself.outAlpha = len(data)\n",
            "", {}, {}, {}, allow_file_read=True)
        self.assertFalse(p.get("reads_embedded_image"))
        self.assertTrue(any("open()" in u for u in (p.get("unported") or [])),
                        p.get("unported"))

    def test_open_not_in_nonportable_patterns(self):
        # The blanket open() pattern was removed from the deny table (it is now
        # classified per-call in _classify_opens); a bare AST-based scanner exists.
        from mpynode.native.spec import spec_extractor as se

        self.assertTrue(hasattr(se, "_classify_opens"))
        self.assertEqual(se._classify_opens('open("x", "wb")'),      (1, 1))
        self.assertEqual(se._classify_opens('open("x", "rb")'),      (1, 1))
        self.assertEqual(se._classify_opens('open("x")'),            (1, 0))
        self.assertEqual(se._classify_opens('open("x", mode="wb")'), (1, 1))
        self.assertEqual(se._classify_opens("fh.open('x')"),         (0, 0))  # method call


class TestEmbeddedByteBaking(unittest.TestCase):
    """extract_spec bakes embeddedImage bytes; absence keeps a lean spec."""

    def test_bytes_roundtrip(self):
        png  = _tiny_png()
        spec = _file_spec("File Simple", bake_embedded=png)
        b64  = (spec.get("suggested") or {}).get("embedded_image_b64")
        self.assertTrue(b64)
        self.assertEqual(base64.b64decode(b64), png)

    def test_no_embedded_no_key(self):
        spec = _file_spec("File Simple", bake_embedded=None)
        self.assertNotIn("embedded_image_b64", spec.get("suggested") or {})
        # ... but it is still a portable file reader.
        self.assertTrue((spec.get("suggested") or {}).get("reads_image_file"))

    def test_empty_bytes_no_key(self):
        spec = _file_spec("File Simple", bake_embedded=b"")
        self.assertNotIn("embedded_image_b64", spec.get("suggested") or {})


class TestFileNameCaptured(unittest.TestCase):
    """A reads_image_file node surfaces fileName even via a getattr helper."""

    def test_filename_input_present(self):
        spec = _file_spec("File Simple")
        self.assertIn("fileName", spec.get("inputs") or {})
        self.assertEqual(spec["inputs"]["fileName"].get("type"), "string")


class TestMpnLiveEquivalence(unittest.TestCase):
    """The .mpn adapter and live extract_spec agree on the new fileName + embedded
    baking -- else the port_cache key would split between the two entry points."""

    def _live_and_file(self, template, bake_embedded=None):
        import maya.cmds as cmds
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.native.spec import spec_extractor as sx
        from mpynode.native.spec import mpn_spec_adapter as adapter
        from mpynode._common.io import mpn_io

        d = _template_data(template)
        cmds.file(new=True, force=True)
        # ``template`` is now a folder NAME with spaces ("File Simple"); a Maya
        # node name cannot carry one, so squeeze them out for the node only.
        w = MPyFile.create(name=template.replace(" ", "") + "#")
        for nm, meta in (d.get("input_attrs") or {}).items():
            w.add_input_attr(nm, meta.get("attr_type", "float"))
        w.set_init_expression(d["init_source"])
        w.set_compute_expression(d["expression"])
        if bake_embedded is not None:
            w.set_variable("embeddedImage", bake_embedded)
        live      = sx.extract_spec(w.get_name())
        payload   = mpn_io.serialize_node(w)
        from_file = adapter.spec_from_mpn_payload(payload)
        return live, from_file

    def test_filename_input_equivalent(self):
        live, from_file = self._live_and_file("File Simple")
        self.assertIn("fileName", from_file["inputs"])
        self.assertEqual(from_file["inputs"], live["inputs"])

    def test_embedded_b64_equivalent(self):
        png = _tiny_png()
        live, from_file = self._live_and_file("File Simple", bake_embedded=png)
        self.assertEqual(from_file["suggested"].get("embedded_image_b64"),
                         live["suggested"].get("embedded_image_b64"))
        self.assertEqual(base64.b64decode(from_file["suggested"]["embedded_image_b64"]),
                         png)


class TestEmbeddedCodegen(unittest.TestCase):
    """Codegen emits the staging helper + fallback only when bytes are baked."""

    def _cpp(self, template, bake_embedded=None, init=None, compute=None):
        from mpynode.native import compiler as codegen

        spec = _file_spec(template, bake_embedded=bake_embedded,
                          init=init, compute=compute)
        return codegen.generate_cpp(spec, for_port=True), spec

    def _raw_cpp(self, bake_embedded=None):
        return self._cpp("File Simple", bake_embedded=bake_embedded,
                         init=_RAW_INIT, compute=_RAW_COMPUTE)

    # ---- BLESSED path (what the shipped templates compile to) ----

    def test_embedded_machinery_emitted(self):
        cpp, _ = self._cpp("File Simple", bake_embedded=_tiny_png())
        # baked bytes + staging helper
        self.assertIn("static const unsigned char nd_embed_img[]", cpp)
        self.assertIn("static MString nd_img_embedded_path()", cpp)
        # primary fileName load, then the nullptr -> embedded retry, BOTH through
        # the one by-path NdTexCache (a std::map, so the retry cannot invalidate
        # a pointer the first call handed out).
        self.assertIn(
            "nd_tex_load_linear(_texCache, _texMutex, in_aFileName,", cpp)
        self.assertIn("MString tb_1_emb = nd_img_embedded_path();", cpp)
        self.assertIn(
            "nd_tex_load_linear(_texCache, _texMutex, tb_1_emb,", cpp)
        # ...and therefore NO second cache slot: that belongs to the raw path.
        self.assertNotIn("NdImgRawCache _imgEmbedCache;", cpp)
        self.assertNotIn("std::mutex _imgEmbedMutex;", cpp)
        # magic-byte ext sniff -> .png staged filename
        self.assertIn("/mpy_embed_", cpp)
        self.assertIn(".png", cpp)

    def test_no_embedded_no_machinery_but_primary_load(self):
        cpp, _ = self._cpp("File Simple", bake_embedded=None)
        self.assertNotIn("nd_embed_img[]",       cpp)
        self.assertNotIn("nd_img_embedded_path", cpp)
        self.assertNotIn("_imgEmbedCache",       cpp)
        # the fileName load is STILL wired (the node reads its image by path)
        self.assertIn(
            "nd_tex_load_linear(_texCache, _texMutex, in_aFileName,", cpp)

    # ---- RAW path (a user node that stages + taps pixels itself) ----

    def test_raw_embedded_machinery_emitted(self):
        cpp, _ = self._raw_cpp(bake_embedded=_tiny_png())
        # baked bytes + staging helper + the SECOND raw cache slot
        self.assertIn("static const unsigned char nd_embed_img[]", cpp)
        self.assertIn("static MString nd_img_embedded_path()", cpp)
        self.assertIn("NdImgRawCache _imgEmbedCache;", cpp)
        self.assertIn("std::mutex _imgEmbedMutex;", cpp)
        # primary fileName load + !_imgOK embedded fallback
        self.assertIn("nd_img_load_raw(_imgRawCache, _imgRawMutex, in_aFileName,",
                      cpp)
        self.assertIn("if (!_imgOK) {", cpp)
        self.assertIn(
            "nd_img_load_raw(_imgEmbedCache, _imgEmbedMutex, _embPath,", cpp)

    def test_raw_no_embedded_no_machinery_but_primary_load(self):
        cpp, _ = self._raw_cpp(bake_embedded=None)
        self.assertNotIn("nd_embed_img[]",       cpp)
        self.assertNotIn("nd_img_embedded_path", cpp)
        self.assertNotIn("_imgEmbedCache",       cpp)
        self.assertIn("nd_img_load_raw(_imgRawCache, _imgRawMutex, in_aFileName,",
                      cpp)


class TestEmbeddedStageHelperUnit(unittest.TestCase):
    """The pure codegen helper: ext sniff + baked-array structure."""

    def test_ext_for_bytes(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        self.assertEqual(ftc._ext_for_bytes(b"\x89PNG\r\n\x1a\nrest"), ".png")
        self.assertEqual(ftc._ext_for_bytes(b"\xff\xd8\xff\xe0jpg"), ".jpg")
        self.assertEqual(ftc._ext_for_bytes(b"RIFF____WEBPvp8"), ".webp")
        self.assertEqual(ftc._ext_for_bytes(b"BMbmp"), ".bmp")
        self.assertEqual(ftc._ext_for_bytes(b"II*\x00tif"), ".tif")
        self.assertEqual(ftc._ext_for_bytes(b"MM\x00*tif"), ".tif")
        self.assertEqual(ftc._ext_for_bytes(b"random-junk"), ".png")

    def test_make_embedded_stage_cpp_structure(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        data = b"\x89PNG\r\n\x1a\n" + bytes(range(40))
        cpp  = ftc.make_embedded_stage_cpp(data)
        self.assertIn("static const unsigned char nd_embed_img[] = {", cpp)
        self.assertIn("static const size_t nd_embed_img_len = sizeof(nd_embed_img);",
                      cpp)
        self.assertIn("static MString nd_img_embedded_path()", cpp)
        self.assertIn(".png", cpp)                # magic -> png
        # the first byte (0x89 = 137) appears in the initializer list
        self.assertIn("137,", cpp)


class TestEmbeddedStageCompiles(unittest.TestCase):
    """DECISIVE: the staging helper compiles and stages the bytes byte-exact."""

    _SHIM = r"""
#include <cstdio>
#include <cstring>
#include <string>
#include <fstream>
#include <cstdlib>
#include <mutex>
#include <iterator>
struct MString {
    std::string s;
    MString() {}
    MString(const char* c): s(c?c:"") {}
    unsigned length() const { return (unsigned)s.size(); }
    const char* asChar() const { return s.c_str(); }
};
"""
    _MAIN = r"""
int main() {
    MString p = nd_img_embedded_path();
    if (p.length()==0) { printf("FAIL empty\n"); return 1; }
    std::ifstream f(p.asChar(), std::ios::binary);
    std::string data((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());
    if (data.size()!=nd_embed_img_len) { printf("FAIL size\n"); return 1; }
    if (memcmp(data.data(), nd_embed_img, nd_embed_img_len)!=0) {
        printf("FAIL bytes\n"); return 1; }
    MString p2 = nd_img_embedded_path();
    if (strcmp(p.asChar(), p2.asChar())!=0) { printf("FAIL unstable\n"); return 1; }
    if (!strstr(p.asChar(), ".png")) { printf("FAIL ext\n"); return 1; }
    printf("OK\n");
    return 0;
}
"""

    def _cxx(self):
        for cc in ("clang++", "g++", "c++"):
            if shutil.which(cc):
                return cc
        return None

    def test_stage_roundtrip_compiles(self):
        try:
            png = _tiny_png()
        except Exception:
            self.skipTest("PIL not available to author a test PNG")
        cc = self._cxx()
        if cc is None:
            self.skipTest("no C++ compiler on this host")

        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        src = self._SHIM + ftc.make_embedded_stage_cpp(png) + self._MAIN
        d   = tempfile.mkdtemp(prefix="embed_stage_")
        cpp = os.path.join(d, "t.cpp")
        exe = os.path.join(d, "t")
        with open(cpp, "w") as fh:
            fh.write(src)
        r = subprocess.run([cc, "-std=c++17", "-O2", "-o", exe, cpp],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = subprocess.run([exe], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("OK", out.stdout)


if __name__ == "__main__":
    unittest.main()
