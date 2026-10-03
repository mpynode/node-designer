"""A compiled mPyFile creates every preset at the SSOT default, like the interpreted one.

MPyFile.initializer() creates each preset at its ``FILE_TEXTURE_ATTRS`` default.
A base plug (one the spec does not carry) took it through ``_ssot_meta``; a
preset the SPEC carries arrives through ``build_porter_meta_table`` with its
type only, so the compiled node created it at 0. Measured on the shipped
builds: preFilterRadius registered 0 instead of 2 (fileTexture, scanlineTex,
compositeTexture) and outAlpha 0 instead of 1 (all four).
"""
from __future__ import annotations

import copy
import json
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_TEMPLATES = ("File Simple", "File Composite", "File Scanline",
              "Game Of Life Texture", "File Brightness Contrast")


def _spec(template="File Simple"):
    man = os.path.join(_paths.ROOT, "templates", "MPyFile", template, "build",
                       "manifest.json")
    with open(man, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


def _defaulted():
    """The SSOT entries whose create call takes a default (scalar / enum)."""
    from mpynode._common.interface import file_texture_interface as iface

    return [e for e in iface.FILE_TEXTURE_ATTRS
            if e["attr_type"] in ("float", "long", "bool", "enum")]


def _created_default(cpp, plug):
    """The default argument of ``plug``'s create call, as text."""
    m = re.search(r'[ne]Attr\.create\("%s", "%s", (?:MFnNumericData::k\w+, )?'
                  r'([^)]+)\);' % (plug, plug), cpp)
    return m.group(1) if m else None


def _literal(e):
    v = e["default"]
    if e["attr_type"] == "bool":
        return "true" if v else "false"
    return repr(float(v)) if e["attr_type"] == "float" else repr(int(v))


class TestPresetDefaults(unittest.TestCase):

    def test_spec_carried_presets_take_the_ssot_default(self):
        # File Simple carries preFilterRadius and outAlpha in its spec.
        from mpynode.native import compiler as codegen

        spec = _spec()
        self.assertIn("preFilterRadius", spec["inputs"])
        self.assertIn("outAlpha", spec["outputs"])
        self.assertNotIn("default_value", spec["inputs"]["preFilterRadius"])
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertEqual(_created_default(cpp, "preFilterRadius"), "2.0")
        self.assertEqual(_created_default(cpp, "outAlpha"), "1.0")

    def test_base_presets_take_the_ssot_default(self):
        # Game Of Life Texture carries none of these: all base plugs.
        from mpynode.native import compiler as codegen

        spec = _spec("Game Of Life Texture")
        cpp  = codegen.generate_cpp(spec, for_port=True)
        for plug, want in (("preFilterRadius", "2.0"), ("maxAnisotropy", "16"),
                           ("maxLOD", "16"), ("filterMode", "2")):
            with self.subTest(plug=plug):
                self.assertNotIn(plug, spec["inputs"])
                self.assertEqual(_created_default(cpp, plug), want)

    def test_every_shipped_preset_default_matches_the_ssot(self):
        from mpynode.native import compiler as codegen

        for tpl in _TEMPLATES:
            spec    = _spec(tpl)
            cpp     = codegen.generate_cpp(spec, for_port=True)
            carried = set(spec["inputs"]) | set(spec["outputs"])
            for e in _defaulted():
                with self.subTest(template=tpl, plug=e["long"],
                                  carried=e["long"] in carried):
                    self.assertEqual(_created_default(cpp, e["long"]), _literal(e))

    def test_ssot_defaults_need_no_unit_conversion(self):
        # _ssot_default writes the value as is: right only while no preset is
        # a unit type (doubleAngle / doubleLinear take internal units).
        from mpynode._common.interface import file_texture_interface as iface

        self.assertEqual(
            [e["long"] for e in iface.FILE_TEXTURE_ATTRS
             if e["attr_type"] in ("doubleAngle", "doubleLinear", "time")], [])

    def test_a_recorded_default_wins(self):
        from mpynode.native import compiler as codegen

        spec                                               = _spec()
        spec["inputs"]["preFilterRadius"]["default_value"] = 3.5
        cpp                                                = codegen.generate_cpp(spec, for_port=True)
        self.assertEqual(_created_default(cpp, "preFilterRadius"), "3.5")
        # the range still comes from the SSOT
        block = cpp.split('nAttr.create("preFilterRadius"', 1)[1]
        block = block.split(".create(", 1)[0]
        self.assertIn("nAttr.setMin(0.0);", block)
        self.assertIn("nAttr.setMax(8.0);", block)

    def test_a_none_is_not_a_record(self):
        # emit_attr reads a None default / min / max as absent, so a None key
        # must take the SSOT value, not a create at 0 with no range.
        from mpynode.native import compiler as codegen

        spec = _spec()
        meta = spec["inputs"]["preFilterRadius"]
        meta.update(default_value=None, min_value=None, max_value=None)
        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertEqual(_created_default(cpp, "preFilterRadius"), "2.0")
        block = cpp.split('nAttr.create("preFilterRadius"', 1)[1]
        block = block.split(".create(", 1)[0]
        self.assertIn("nAttr.setMin(0.0);", block)
        self.assertIn("nAttr.setMax(8.0);", block)

    def test_the_spec_is_not_touched(self):
        from mpynode.native import compiler as codegen

        spec   = _spec()
        before = copy.deepcopy(spec)
        codegen.generate_cpp(spec, for_port=True)
        self.assertEqual(spec, before)

    def test_only_mpyfile_presets(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        m = [{"plug": "preFilterRadius", "kind": "inputs", "member": "aP",
              "meta": {"type": "float", "is_array": False}},
             {"plug": "outAlpha", "kind": "outputs", "member": "aA",
              "meta": {"type": "float", "is_array": False}}]
        self.assertEqual(ftc.with_preset_ssot({"mpy_type": "mPyNode"}, m), m)
        got = ftc.with_preset_ssot({"mpy_type": "mPyFile"}, m)
        self.assertEqual([g["meta"].get("default_value") for g in got], [2.0, 1.0])
        self.assertNotIn("default_value", m[0]["meta"], "the member is copied")
        # a same-named plug of another type or direction is not the preset
        other = [dict(m[0], meta={"type": "double"}), dict(m[1], kind="inputs")]
        for g in ftc.with_preset_ssot({"mpy_type": "mPyFile"}, other):
            self.assertNotIn("default_value", g["meta"])


if __name__ == "__main__":
    unittest.main()
