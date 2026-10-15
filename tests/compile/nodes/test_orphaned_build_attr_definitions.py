"""The orphaned Brightness Contrast build creates its attributes the way its
stage 1 does.

``templates/MPyFile/File Brightness Contrast`` has a build tree but no
template.mpn, so nothing regenerates it and no splice reaches its shipped
files: they keep their own stamp, 2de0f50e3ee6. Its stage 1 moved with the
compiled attribute definitions (port_cache v43: SSOT short names, keyable
compound children, the "" fileName default), while the final, the shipped
source and 2_assisted kept the old ones. ``connectAttr place2dTexture.outUV
<node>.uv`` failed on it, as on every compiled mPyFile type before v43
(parity pass 2026-10-15, round 2).

The orphan creates six attributes. Stage 1 creates the same six first, then
the mPyFile base plugs the orphan predates. Each shipped file's create section
must equal stage 1's up to the first base plug. When a generator change moves
these definitions again, hand-edit the three files to the new stage 1; never
an AI re-port.
"""
from __future__ import annotations

import difflib
import os
import re
import unittest

from tests import _paths

_BUILD = os.path.join(_paths.ROOT, "templates", "MPyFile",
                      "File Brightness Contrast", "build")
_STAGES   = os.path.join(_BUILD, "stages", "brightContrastTex")
_STAGE1   = os.path.join(_STAGES, "1_transpiled.cpp")
_FINAL    = os.path.join(_BUILD, "brightContrastTex", "brightContrastTex.cpp")
_SOURCE   = os.path.join(_BUILD, "source", "brightContrastTex.cpp")
_ASSISTED = os.path.join(_STAGES, "2_assisted.cpp")
_SHIPPED  = {"final": _FINAL, "source": _SOURCE, "2_assisted": _ASSISTED}
_STAMP    = "2de0f50e3ee6"


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def _members(cpp):
    """The static MObject attribute members, in declaration order."""
    return re.findall(r"^    static MObject (a\w+);$", cpp, re.M)


def _create_section(cpp):
    """The lines of initialize() that create the attributes: after the MFn
    declarations, up to the first addAttribute()."""
    lines = cpp.split("\n")
    start = lines.index("MStatus BrightContrastTex::initialize() {") + 1
    while re.match(r"^    MFn\w+ +\w+;$", lines[start]):
        start += 1
    while lines[start] == "":
        start += 1
    end = next(i for i in range(start, len(lines))
               if lines[i].startswith("    addAttribute("))
    while lines[end - 1] == "":
        end -= 1
    return lines[start:end]


def _referenced(line, members):
    """The attribute members ``line`` names, a compound's children (aUvCoordX,
    aOutColorR) counted as their parent."""
    found = set()
    for ident in re.findall(r"\ba[A-Z_]\w*", line):
        if ident in members:
            found.add(ident)
        elif ident[:-1] in members and ident[-1] in "XYZRGB":
            found.add(ident[:-1])
    return found


def _stage1_prefix(stage1, orphan_members):
    """Stage 1's create section up to the first line of the first attribute
    the orphan does not have."""
    section = _create_section(stage1)
    members = set(_members(stage1))
    extra   = members - set(orphan_members)
    cut = next((i for i, line in enumerate(section)
                if _referenced(line, members) & extra), len(section))
    # A string attribute opens a scope for its default before its create line.
    while cut and (section[cut - 1] == "    {"
                   or section[cut - 1].startswith("        ")):
        cut -= 1
    return section[:cut]


class TestOrphanedBuildAttributeDefinitions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.stage1  = _read(_STAGE1)
        cls.shipped = {name: _read(path) for name, path in _SHIPPED.items()}

    def test_the_orphan_creates_stage_1_first_attributes(self):
        """The six attributes are still the first stage 1 creates, so the
        comparison below covers every attribute the orphan has."""
        stage1 = _members(self.stage1)
        for name, cpp in self.shipped.items():
            with self.subTest(file=name):
                own = _members(cpp)
                self.assertEqual(len(own), 6)
                self.assertEqual(stage1[:len(own)], own)

    def test_each_attribute_is_created_as_stage_1_creates_it(self):
        for name, cpp in self.shipped.items():
            with self.subTest(file=name):
                want = _stage1_prefix(self.stage1, _members(cpp))
                got  = _create_section(cpp)
                self.assertEqual(
                    got, want,
                    "%s creates its attributes differently from stage 1; "
                    "hand-edit it to stage 1's definitions:\n%s" % (
                        name, "\n".join(difflib.unified_diff(
                            want, got, "stage 1", name, lineterm=""))))

    def test_every_attribute_function_set_is_included(self):
        """The definitions use MFnStringData for the "" fileName default;
        each function set they use has its header."""
        for name, cpp in self.shipped.items():
            used = set(re.findall(r"\b(MFn\w+)\b",
                                  "\n".join(_create_section(cpp))))
            for fn in sorted(used):
                with self.subTest(file=name, header=fn):
                    self.assertIn("#include <maya/%s.h>" % fn, cpp)

    def test_the_orphan_keeps_its_stamp(self):
        for name, cpp in self.shipped.items():
            with self.subTest(file=name):
                self.assertIn("// build: %s\n" % _STAMP, cpp)
        self.assertIn('"1.0+%s"' % _STAMP, self.shipped["2_assisted"])

    def test_the_source_is_the_final_plus_its_type_id(self):
        final  = self.shipped["final"].split("\n")
        source = self.shipped["source"].split("\n")
        self.assertEqual(len(final), len(source))
        differ = [(a, b) for a, b in zip(final, source) if a != b]
        self.assertEqual(len(differ), 1, differ)
        for line in differ[0]:
            self.assertTrue(line.startswith("MTypeId BrightContrastTex::id("),
                            line)


if __name__ == "__main__":
    unittest.main()
