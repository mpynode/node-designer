"""A compiled mPyFile preset carries the flags MPyFile.initializer() gives it.

The interpreted initializer applies each ``FILE_TEXTURE_ATTRS`` entry's
``flags`` to an attr that otherwise keeps MFnAttribute's defaults. The compiled
create first applies emit_attr's generic flags, which make every input
keyable; a preset the spec carries then took no SSOT flag at all, and a base
plug took only the parent's. Measured on the shipped builds next to their
interpreted twins: colorSpace, preFilterKernel, uvCoord and uvFilterSize
(+ X / Y) keyable where the interpreted ones are not, and the spec-carried
fileName without usedAsFilename.

Each test replays the flag calls the generated initialize() makes on one plug
over Maya's defaults and compares the result with what the interpreted
initializer leaves.
"""
from __future__ import annotations

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

# MFnAttribute's defaults: what an attr reports when nothing sets the flag.
_MAYA_DEFAULTS = {"keyable": False, "storable": True, "hidden": False,
                  "writable": True, "readable": True, "connectable": True,
                  "usedAsColor": False, "usedAsFilename": False}
_SSOT_KEY = {"keyable": "keyable", "storable": "storable",
             "hidden": "hidden", "writable": "writable",
             "readable": "readable", "connectable": "connectable",
             "used_as_color": "usedAsColor",
             "used_as_filename": "usedAsFilename"}
_CALL_RE = re.compile(r"^    [a-z]Attr\.set(\w+)\((true|false)\);$")
_CHILD_RE = re.compile(r"^    \{ MFnNumericAttribute _cf\((\w+)\); "
                       r"_cf\.set(\w+)\((true|false)\); \}$")


# any create call: .create( / .createColor( / .createPoint(
_NEXT_CREATE = re.compile(r"\.create\w*\(")


def _spec(template):
    man = os.path.join(_paths.ROOT, "templates", "MPyFile", template, "build",
                       "manifest.json")
    with open(man, encoding="utf-8") as fh:
        return json.load(fh)["nodes"][0]["spec"]


def _flag_name(setter):
    return setter[:1].lower() + setter[1:]


def _created(cpp, plug):
    """``(member, lines)`` of ``plug``'s create statement through the next
    create (or the end of the create section)."""
    m = re.search(r'^ +(\w+) = [a-z]Attr\.create(?:Color)?\("%s", "%s"'
                  % (plug, plug), cpp, re.M)
    if m is None:
        return None, []
    rest  = cpp[m.end():].split("\n")[1:]
    block = []
    for line in rest:
        if _NEXT_CREATE.search(line) or "addAttribute(" in line or not line.strip():
            break
        block.append(line)
    return m.group(1), block


def _replay(block, member, color):
    """The parent's flags and each float2 child's, after the emitted calls."""
    parent   = dict(_MAYA_DEFAULTS, usedAsColor=color)
    children = {"X": dict(_MAYA_DEFAULTS), "Y": dict(_MAYA_DEFAULTS)}
    for line in block:
        m = _CALL_RE.match(line)
        if m:
            parent[_flag_name(m.group(1))] = m.group(2) == "true"
            continue
        m = _CHILD_RE.match(line)
        if m and m.group(1) in (member + "X", member + "Y"):
            children[m.group(1)[-1]][_flag_name(m.group(2))] = m.group(3) == "true"
    return parent, children


def _interpreted(flags):
    out = dict(_MAYA_DEFAULTS)
    for k, v in (flags or {}).items():
        out[_SSOT_KEY[k]] = bool(v)
    return out


class TestPresetFlags(unittest.TestCase):

    def test_every_preset_ends_with_the_interpreted_flags(self):
        from mpynode._common.interface import file_texture_interface as iface
        from mpynode.native import compiler as codegen

        for tpl in _TEMPLATES:
            spec    = _spec(tpl)
            cpp     = codegen.generate_cpp(spec, for_port=True)
            carried = set(spec["inputs"]) | set(spec["outputs"])
            for e in iface.FILE_TEXTURE_ATTRS:
                member, block = _created(cpp, e["long"])
                with self.subTest(template=tpl, plug=e["long"],
                                  carried=e["long"] in carried):
                    self.assertIsNotNone(member, "no create for the preset")
                    parent, kids = _replay(block, member,
                                           e["attr_type"] == "color")
                    self.assertEqual(parent, _interpreted(e.get("flags")))
                    if e["attr_type"] == "float2":
                        for c, axis in zip(e["children"], "XY"):
                            self.assertEqual(kids[axis],
                                             _interpreted(c.get("flags")),
                                             c["long"])

    def test_spec_carried_presets_measured_wrong(self):
        # The four the shipped File Simple build got wrong, spelled out.
        from mpynode.native import compiler as codegen

        spec = _spec("File Simple")
        for plug in ("fileName", "colorSpace", "preFilterKernel", "uvCoord"):
            self.assertIn(plug, spec["inputs"])
        cpp = codegen.generate_cpp(spec, for_port=True)
        _m, block = _created(cpp, "fileName")
        self.assertIn("    tAttr.setUsedAsFilename(true);", block)
        for plug in ("colorSpace", "preFilterKernel"):
            member, block = _created(cpp, plug)
            self.assertFalse(_replay(block, member, False)[0]["keyable"], plug)
        member, block = _created(cpp, "uvCoord")
        parent, kids = _replay(block, member, False)
        self.assertFalse(parent["keyable"])
        self.assertTrue(kids["X"]["keyable"] and kids["Y"]["keyable"])

    def test_base_uv_filter_size_is_not_keyable(self):
        from mpynode.native import compiler as codegen

        spec = _spec("File Simple")
        self.assertNotIn("uvFilterSize", spec["inputs"])
        member, block = _created(codegen.generate_cpp(spec, for_port=True),
                                 "uvFilterSize")
        parent, kids = _replay(block, member, False)
        self.assertEqual((parent["keyable"], parent["hidden"]), (False, True))
        self.assertFalse(kids["X"]["keyable"] or kids["Y"]["keyable"])

    def test_only_mpyfile_ssot_plugs_take_flags(self):
        from mpynode.native.compiler.kernels import file_texture_cpp as ftc

        m = [{"plug": "colorSpace", "kind": "inputs", "member": "aC",
              "meta": {"type": "enum", "is_array": False}}]
        self.assertEqual(ftc.with_preset_ssot({"mpy_type": "mPyNode"}, m), m)
        got = ftc.with_preset_ssot({"mpy_type": "mPyFile"}, m)
        self.assertEqual(got[0]["extra_flags"],
                         ["    eAttr.setKeyable(false);",
                          "    eAttr.setStorable(true);"])
        self.assertNotIn("extra_flags", m[0], "the member is copied")
        # a same-named plug of another type is not the preset
        other = [dict(m[0], meta={"type": "long"})]
        self.assertNotIn("extra_flags",
                         ftc.with_preset_ssot({"mpy_type": "mPyFile"}, other)[0])


if __name__ == "__main__":
    unittest.main()
