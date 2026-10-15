"""The compiled default mPyFile shows its texture in Viewport 2.0 (v45).

A node with no custom template code compiles through the full-parity glue
(``file_texture_cpp.compute_glue_lines``). ``emit_vp2_override`` recognised
only an AI PORT region or a lowered guard, so the glue node shipped with no
MPxShadingNodeOverride and Viewport 2.0 shaded it one flat colour, while the
interpreted default node shows its texture. The override now takes the glue
region too, and the glue's sample point is ``_su``/``_sv`` so the body drops
into ``nd_texel`` (whose own parameters are ``_u``/``_v``) unchanged.

Measured on a Maya 2025 build of this code (ogsRender, unlit surfaceShader):
the compiled default node's mean RGB equals the interpreted node's for a valid
file, a missing file and an empty path. No shipped template uses the glue.
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _default_spec():
    """The spec the compile pipeline reads off a fresh default mPyFile."""
    from mpynode._common.io import mpn_io
    from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload
    from mpynode.wrappers.mpy_file import MPyFile

    mc.file(new=True, force=True)
    w                    = MPyFile.create(name="defaultVp2")
    spec                 = spec_from_mpn_payload(mpn_io.serialize_node(w))
    sg                   = spec["suggested"]
    sg["node_type_name"] = "defaultVp2Tex"
    sg["class_name"]     = "DefaultVp2Tex"
    sg["type_id"]        = "0x0007fd02"
    return spec


def _scanline_spec():
    from mpynode._defaults.file_defaults import DEFAULT_INIT_SOURCE
    from mpynode.native.compiler.kernels import file_texture_cpp as ftc
    from mpynode.native.spec import spec_extractor as se

    spec            = _default_spec()
    spec["compute"] = ftc.make_scanline_compute(spec["compute"])
    spec["init"] = DEFAULT_INIT_SOURCE + (
        "\nimport math\nNUM_BANDS = 12.0\nSPEED = 0.1\n"
        "TWO_PI = 6.283185307179586\n")
    spec["inputs"]["tIn"] = se.normalize_attr({"attr_type": "float"})
    return spec


def _texel(cpp):
    """The nd_texel definition, signature to closing brace. With no override
    injected there is none: a test failure, not a ValueError."""
    start = cpp.find("static void nd_texel(")
    if start < 0:
        raise AssertionError("no nd_texel: the VP2 override was not injected")
    return cpp[start:cpp.index("\n}\n", start) + 2]


def _compute(cpp):
    m = re.search(r"MStatus \w+::compute\(const MPlug& \w+, "
                  r"MDataBlock& data\) \{", cpp)
    start = m.start()
    return cpp[start:cpp.index("\n}\n", start) + 2]


class TestDefaultGlueOverride(unittest.TestCase):

    def setUp(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        self.spec = _default_spec()
        self.assertTrue(ftc.use_full_parity_glue(self.spec))
        self.s1 = codegen.generate_cpp(self.spec, for_port=True)

    def test_the_glue_takes_the_override(self):
        from mpynode.native.compiler import emit_vp2_override as vp2

        self.assertEqual(vp2.skip_reason(self.s1), "")
        out = vp2.inject_vp2_override(self.s1, self.spec)
        self.assertIn("MPxShadingNodeOverride", out)
        self.assertIn("registerShadingNodeOverrideCreator", out)

    def test_compute_samples_through_the_shared_texel(self):
        from mpynode.native.compiler import emit_vp2_override as vp2

        out  = vp2.inject_vp2_override(self.s1, self.spec)
        body = _compute(out)
        self.assertIn("nd_texel(", body)
        self.assertNotIn("verified file-texture pipeline", body)
        self.assertNotIn("nd_tex_sample(", body)
        texel = _texel(out)
        self.assertIn("nd_tex_load_linear(_texCache, _texMutex, in_aFileName,",
                      texel)
        self.assertIn("nd_tex_sample(_lin, _linW, _linH, _su, _sv,", texel)

    def test_the_texel_does_not_redeclare_its_parameters(self):
        from mpynode.native.compiler import emit_vp2_override as vp2

        texel = _texel(vp2.inject_vp2_override(self.s1, self.spec))
        self.assertIn("double _u", texel)
        self.assertIn("double _v", texel)
        self.assertIsNone(re.search(r"\bfloat _u\b|\b_v = in_", texel))

    def test_the_glue_reads_the_sample_point_into_its_own_names(self):
        self.assertIn("    float _su = in_aUvCoord[0], _sv = in_aUvCoord[1];",
                      self.s1)


class TestScanlineGlueOverride(unittest.TestCase):

    def test_the_scanline_glue_takes_the_override(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import emit_vp2_override as vp2
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        spec = _scanline_spec()
        self.assertTrue(ftc.use_full_parity_glue(spec))
        s1 = codegen.generate_cpp(spec, for_port=True)
        self.assertEqual(vp2.skip_reason(s1), "")
        texel = _texel(vp2.inject_vp2_override(s1, spec))
        self.assertIn("std::sin((_sv * ", texel)


if __name__ == "__main__":
    unittest.main()
