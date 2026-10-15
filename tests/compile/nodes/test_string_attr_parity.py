"""A compiled string attribute matches the interpreted one: default and keyable.

Measured on the interpreted nodes of all ten families (2026-10-03):

* mPyFile's ``fileName`` and ``osl`` are created at "" through MFnStringData,
  so an unset one reads "". The compiled ones were created bare and read None.
* a USER string / hex input is an ``addAttr -dt string``, which takes no
  default: it reads None interpreted, so the compiled one stays bare too.
* every non-array user input is ``addAttr -keyable``; a string array is not.
  The compiled string inputs were created non-keyable (gameOfLifeTex's
  bakePath, the locators' displayText).
"""
from __future__ import annotations

import json
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# any create call: .create( / .createColor( / .createPoint(
_NEXT_CREATE = re.compile(r"\.create\w*\(")


def _spec(family, template):
    man = os.path.join(_paths.ROOT, "templates", family, template, "build",
                       "manifest.json")
    with open(man, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


def _cpp(family, template):
    from mpynode.native import compiler as codegen

    return codegen.generate_cpp(_spec(family, template), for_port=True)


def _block(cpp, plug):
    """``plug``'s create line and the lines after it, to the next create.
    The short name is whatever the plug is created with: its long name for a
    user attr, the SSOT's for an mPyFile plug (fileName -> fn, v43)."""
    m = re.search(r'^ +\w+ = tAttr\.create\("%s", "[^"]+"[^\n]*\n' % plug,
                  cpp, re.M)
    if m is None:
        return None
    rest = cpp[m.end():].split("\n")
    out  = [m.group(0).rstrip("\n").strip()]
    for line in rest:
        if _NEXT_CREATE.search(line) or "addAttribute(" in line or not line.strip():
            break
        out.append(line.strip())
    return out


_EMPTY_DEFAULT = ['MFnStringData _sd;', 'MObject _sdo = _sd.create("");']


class TestFrameworkStringsStartEmpty(unittest.TestCase):

    def test_file_name_and_osl_are_created_at_empty(self):
        # File Simple carries fileName in its spec; Game Of Life does not, so
        # there it is a base plug. osl is a base plug on both.
        for tpl in ("File Simple", "Game Of Life Texture"):
            cpp = _cpp("MPyFile", tpl)
            self.assertIn("#include <maya/MFnStringData.h>", cpp)
            for plug, mem, short in (("fileName", "aFileName", "fn"),
                                     ("osl", "aOsl", "osl")):
                with self.subTest(template=tpl, plug=plug):
                    head = cpp.split('%s = tAttr.create("%s"' % (mem, plug), 1)[0]
                    self.assertEqual(
                        [l.strip() for l in head.rstrip().split("\n")[-2:]],
                        _EMPTY_DEFAULT)
                    self.assertIn('%s = tAttr.create("%s", "%s", '
                                  'MFnData::kString, _sdo);' % (mem, plug, short),
                                  cpp)

    def test_a_node_without_one_is_byte_identical(self):
        # Ouch's only string is a user input: created bare, no new header.
        cpp = _cpp("MPyNode", "Ouch")
        self.assertNotIn("MFnStringData", cpp)
        self.assertIn('aAudioFile = tAttr.create("audioFile", "audioFile", '
                      'MFnData::kString);', cpp)

    def test_only_a_text_default_counts(self):
        from mpynode.native.compiler.emit_attr import string_default

        def m(t, **kw):
            return {"meta": dict(type=t, **kw)}

        self.assertEqual(string_default(m("string", string_default="")), "")
        self.assertIsNone(string_default(m("string")))
        self.assertIsNone(string_default(m("string", string_default=None)))
        self.assertIsNone(string_default(m("hex", string_default="")))
        # a recorded default_value is a user attr's: the interpreted node
        # ignores it, so it is not a create default (test_native_codegen_
        # check_gate.TestDefaultValueContract pins the emitted side)
        self.assertIsNone(string_default(m("string", default_value="x")))

    def test_a_recorded_file_name_default_does_not_win(self):
        # MPyFile.initializer() creates fileName at "" whatever a spec records.
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        m = [{"plug": "fileName", "kind": "inputs", "member": "aFileName",
              "meta": {"type": "string", "is_array": False,
                       "default_value": "x.png"}}]
        got = ftc.with_preset_ssot({"mpy_type": "mPyFile"}, m)[0]["meta"]
        self.assertEqual(got["string_default"], "")


class TestStringInputsAreKeyable(unittest.TestCase):

    def test_bake_path_is_keyable(self):
        block = _block(_cpp("MPyFile", "Game Of Life Texture"), "bakePath")
        self.assertEqual(block, ['aBakePath = tAttr.create("bakePath", '
                                 '"bakePath", MFnData::kString);',
                                 "tAttr.setStorable(true);",
                                 "tAttr.setKeyable(true);"])

    def test_every_single_user_string_input_is_keyable(self):
        for family, tpl, plug in (("MPyMesh", "Disk Mesh Cache", "cachePath"),
                                  ("MPyMesh", "JSON Mesh Reader", "path"),
                                  ("MPyMesh", "UV Layout", "uvSetName"),
                                  ("MPyMesh", "Voxelize", "textureFile"),
                                  ("MPyNode", "Ouch", "audioFile")):
            with self.subTest(template=tpl, plug=plug):
                self.assertIn("tAttr.setKeyable(true);",
                              _block(_cpp(family, tpl), plug))

    def test_locator_display_text_is_keyable(self):
        for tpl in ("Animated Text", "Circular Text"):
            with self.subTest(template=tpl):
                block = _block(_cpp("MPyLocator", tpl), "displayText")
                self.assertIn("tAttr.setKeyable(true); "
                              "tAttr.setAffectsAppearance(true);", block)
                self.assertNotIn("tAttr.setKeyable(false); "
                                 "tAttr.setAffectsAppearance(true);", block)

    def test_a_string_array_stays_unkeyable(self):
        block = _block(_cpp("MPyFile", "File Composite"), "layers")
        self.assertNotIn("tAttr.setKeyable(true);", block)
        # ...and uses the array data builder, as an addAttr -multi does (v43)
        self.assertEqual(block[-3:], ["tAttr.setArray(true);",
                                      "tAttr.setKeyable(false);",
                                      "tAttr.setUsesArrayDataBuilder(true);"])


class TestInterpretedReference(unittest.TestCase):
    """What the compiled side copies, read off the interpreted nodes."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_a_user_string_input_reads_none_and_is_keyable(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.wrappers.mpy_locator import MPyLocator

        for cls in (MPyNode, MPyLocator):
            with self.subTest(family=cls.__name__):
                w = cls.create(name="strRef")
                n = w.get_name()
                w.add_input_attr("sIn", "string")
                w.add_input_attr("sArr", "string", is_array=True)
                self.assertIsNone(mc.getAttr(n + ".sIn"))
                self.assertTrue(mc.attributeQuery("sIn", node=n, keyable=True))
                self.assertFalse(mc.attributeQuery("sArr", node=n, keyable=True))

    def test_mpyfile_file_name_and_osl_read_empty(self):
        n = mc.createNode("mPyFile")
        self.assertEqual(mc.getAttr(n + ".fileName"), "")
        self.assertEqual(mc.getAttr(n + ".osl"), "")
        self.assertTrue(mc.attributeQuery("fileName", node=n, usedAsFilename=True))
        self.assertFalse(mc.attributeQuery("fileName", node=n, keyable=True))


if __name__ == "__main__":
    unittest.main()
