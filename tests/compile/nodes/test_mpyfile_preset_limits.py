"""A compiled mPyFile clamps its sampler presets where the interpreted one does.

MPyFile.initializer() hands setMin / setMax the SSOT range of preFilterRadius,
maxAnisotropy, mipLODBias, minLOD and maxLOD. The compiled node created them
unclamped: ``_ssot_meta`` dropped min / max for a base plug, and a preset the
spec carries (preFilterRadius, through ``build_porter_meta_table``) arrived
with its type only. Measured on the shipped File Simple build: all five
attributeQuery -min/-max differed from the interpreted node.
"""
from __future__ import annotations

import copy
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _ranged():
    from mpynode._common.interface import file_texture_interface as iface

    return [e for e in iface.FILE_TEXTURE_ATTRS
            if e["direction"] == "input" and ("min" in e or "max" in e)]


def _spec(template="File Simple"):
    man = os.path.join(_paths.ROOT, "templates", "MPyFile", template, "build",
                       "manifest.json")
    with open(man, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


def _create_block(cpp, plug):
    """initialize()'s lines for ``plug``, from its create to the next create."""
    head = 'nAttr.create("%s"' % plug
    return cpp.split(head, 1)[1].split(".create(", 1)[0]


class TestPresetRanges(unittest.TestCase):

    def test_the_five_ranged_presets(self):
        self.assertEqual(sorted(e["long"] for e in _ranged()),
                         ["maxAnisotropy", "maxLOD", "minLOD", "mipLODBias",
                          "preFilterRadius"])

    def test_spec_and_base_presets_both_clamp(self):
        # File Simple carries preFilterRadius in its spec; the other four
        # are base plugs. Each gets the SSOT's own bounds.
        from mpynode.native import compiler as codegen

        spec = _spec()
        self.assertIn("preFilterRadius", spec["inputs"])
        cpp = codegen.generate_cpp(spec, for_port=True)
        for e in _ranged():
            with self.subTest(plug=e["long"]):
                cast  = int if e["attr_type"] == "long" else float
                block = _create_block(cpp, e["long"])
                self.assertIn("    nAttr.setMin(%r);\n    nAttr.setMax(%r);\n"
                              % (cast(e["min"]), cast(e["max"])), block)

    def test_the_spec_is_not_touched(self):
        from mpynode.native import compiler as codegen

        spec   = _spec("File Scanline")
        before = copy.deepcopy(spec)
        codegen.generate_cpp(spec, for_port=True)
        self.assertEqual(spec, before)

    def test_a_recorded_range_wins(self):
        from mpynode.native import compiler as codegen

        spec                                           = _spec()
        spec["inputs"]["preFilterRadius"]["min_value"] = 1.0
        block = _create_block(codegen.generate_cpp(spec, for_port=True),
                              "preFilterRadius")
        self.assertIn("nAttr.setMin(1.0);", block)
        self.assertNotIn("setMax", block)

    def test_only_mpyfile_presets(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        m = [{"plug": "preFilterRadius", "kind": "inputs", "member": "aP",
              "meta": {"type": "float", "is_array": False}}]
        self.assertEqual(ftc.with_preset_limits({"mpy_type": "mPyNode"}, m), m)
        got = ftc.with_preset_limits({"mpy_type": "mPyFile"}, m)
        self.assertEqual((got[0]["meta"]["min_value"], got[0]["meta"]["max_value"]),
                         (0.0, 8.0))
        self.assertNotIn("min_value", m[0]["meta"], "the member is copied")
        # a same-named attr of another type is not the preset
        m[0]["meta"]["type"] = "double"
        self.assertNotIn("min_value",
                         ftc.with_preset_limits({"mpy_type": "mPyFile"}, m)[0]["meta"])


if __name__ == "__main__":
    unittest.main()
