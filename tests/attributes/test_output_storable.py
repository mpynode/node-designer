"""User outputs are not storable, and their compound children are cached.

The interpreted node decides, and the compiled node matches it. Before
2026-10-15 the two disagreed in both directions, measured with an attribute
audit of all 37 templates (interpreted node vs the All Templates Plugin):

  * ``add_output_attr`` never set ``storable``, so every interpreted user
    output was storable; every compiled output is ``setStorable(false)``, as
    are the interpreted static outputs (mPyMesh outMesh, mPyFile outColor ...).
    40 differences. (Maya writes no value for a non-writable attr either way;
    the flag is what a scene file and the Attribute Editor carry.)
  * the compound children of an interpreted output (double3 X/Y/Z, color
    R/G/B ...) were created without ``cachedInternally``, which ``addAttr``
    defaults to False for a non-writable attr; the parent alone was cached.
    21 differences.
  * the compiled meshRegionLocator created its ``inMesh`` input
    ``setStorable(false)``. The interpreted ``add_input_attr`` makes every input
    storable, and so does the generic compiled mesh input, so the locator
    emitter now does too (port_cache v42).
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import tempfile
import unittest

import maya.api.OpenMaya as om
import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _attr_fn(node: str, attr: str) -> om.MFnAttribute:
    obj = om.MSelectionList().add(node).getDependNode(0)
    return om.MFnAttribute(om.MFnDependencyNode(obj).attribute(attr))


class _Case(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _node(self):
        from mpynode.wrappers._mpy_node import MPyNode

        return MPyNode.create(name="probe")


class TestOutputsAreNotStorable(_Case):

    def test_every_output_kind_and_its_children(self):
        from mpynode.wrappers._mpy_node import (
            _COMPOUND_CHILD_AXES,
            VALID_OUTPUT_TYPES,
        )

        w = self._node()
        for kind in VALID_OUTPUT_TYPES:
            for suffix, is_array in (("", False), ("Arr", True)):
                name = "o" + kind[0].upper() + kind[1:] + suffix
                w.add_output_attr(name, kind, is_array=is_array)
                attrs = [name] + [name + axis for axis
                                  in _COMPOUND_CHILD_AXES.get(kind, ())]
                for attr in attrs:
                    with self.subTest(kind=kind, attr=attr):
                        fn = _attr_fn("probe", attr)
                        self.assertFalse(fn.storable)
                        self.assertTrue(fn.cached)

    def test_inputs_stay_storable(self):
        w = self._node()
        w.add_input_attr("inV", "double3")
        w.add_input_attr("inMesh", "mesh")
        for attr in ("inV", "inVX", "inMesh"):
            with self.subTest(attr=attr):
                self.assertTrue(_attr_fn("probe", attr).storable)

    def test_flags_survive_ma_round_trip(self):
        w = self._node()
        w.add_input_attr("a", "double")
        w.add_output_attr("outV",    "double3")
        w.add_output_attr("outD",    "double")
        w.add_output_attr("outMesh", "mesh")
        w.set_compute_expression(
            "self.outV = (self.a, self.a + 1.0, self.a + 2.0)\n"
            "self.outD = self.a * 3.0\n")
        mc.setAttr("probe.a", 5.0)
        self.assertEqual(mc.getAttr("probe.outD"), 15.0)

        tmp = tempfile.mkdtemp(prefix="mpynode-output-storable-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "storable.ma")
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        # Every output's addAttr line says so, children included.
        lines = re.findall(r'addAttr [^\n]*-ln "(out\w*)"', text)
        self.assertEqual(sorted(lines), ["outD", "outMesh", "outV", "outVX",
                                         "outVY", "outVZ"])
        for name in lines:
            line = re.search(r'addAttr ([^\n]*)-ln "%s"' % name, text).group(1)
            with self.subTest(attr=name):
                self.assertIn("-s false", line)
                self.assertIn("-ci true", line)
        self.assertEqual(re.findall(r'setAttr[^\n"]*"\.(out\w*)"', text), [])

        mc.file(path, open=True, force=True)
        for attr in ("outV", "outVX", "outD", "outMesh"):
            with self.subTest(attr=attr):
                fn = _attr_fn("probe", attr)
                self.assertFalse(fn.storable)
                self.assertTrue(fn.cached)


class TestLocatorMeshInputIsStorable(_Case):
    """meshRegionLocator ``inMesh``: storable on both sides."""

    _CREATE = re.compile(r'(\w+) = tAttr\.create\("inMesh", "inMesh", '
                         r'MFnData::kMesh\);\s*\n\s*tAttr\.setStorable\((\w+)\)')

    def test_interpreted_locator_mesh_input(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        w = MPyLocator.create(name="probeLoc")
        w.add_input_attr("inMesh", "mesh")
        self.assertTrue(_attr_fn(w.get_name(), "inMesh").storable)

    def test_every_shipped_mesh_regions_source(self):
        files = []
        for build in (
            os.path.join(_paths.ROOT, "templates", "MPyLocator",
                         "Mesh Regions", "build"),
            os.path.join(_paths.ROOT, "templates", "All Templates Plugin",
                         "build"),
        ):
            files += glob.glob(os.path.join(build, "stages",
                                            "meshRegionLocator", "**", "*.cpp"),
                               recursive=True)
            files += glob.glob(os.path.join(build, "source",
                                            "meshRegionLocator.cpp"))
            files += glob.glob(os.path.join(build, "meshRegionLocator",
                                            "meshRegionLocator.cpp"))
        # 1_transpiled, 2_assisted, 00_baseline, the final and its source in
        # the template; 1_transpiled, 2_assisted and source in the mega.
        self.assertEqual(len(files), 8)
        for path in files:
            with open(path, encoding="utf-8") as fh:
                found = self._CREATE.findall(fh.read())
            with self.subTest(path=os.path.relpath(path, _paths.ROOT)):
                self.assertEqual(found, [("a_inMesh", "true")])


if __name__ == "__main__":
    unittest.main()
