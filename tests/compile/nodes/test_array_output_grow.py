"""A compiled array output is sized as the interpreted node sizes it (v47).

The interpreted node sizes every ARRAY output to its highest existing logical
index + 1 (``max(getExistingArrayAttributeIndices()) + 1``, inline in
``_api2/_mpy_node.py`` and ``mpy_constraint.py``, and in
``output_defaults.seed_user_output_defaults_api2``) and writes every index
below it. The compiled compute counted the output's data-block elements
(``elementCount()``), and reading an element that does not exist yet adds that
one element only. Measured 2026-10-15 on a fresh pair, nothing connected:
De Boor Spline ``samples[3]`` read (0, 0, 0) on every read, input changes
included, where the interpreted node computed 4 samples and read the last CV;
Bubble Sort ``sort[3]`` read 0 where the interpreted node read minVal; Spring
Chain ``driven[3]`` stayed (0, 0, 0) after the driver moved. Outputs connected
at [0] and [3] did the same to [3].

Right after the nodeState gate the compiled compute now fills the gaps below
the highest index (``emit_compute.array_grow_lines``), so every count it takes
-- a lowered body, a port, an optimizer round -- is the interpreted count.
Pinned here: the generator for every shipped row, every shipped lineage file
stamped from the current stage 1, and the interpreted reference.
"""
from __future__ import annotations

import glob
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


_GATE = ("    if (data.inputValue(MPxNode::state).asShort() != 0)\n"
         "        return MS::kSuccess;\n")
_LIST_RE = re.compile(r"const MObject\* _growAttrs\[\] = \{([^}]*)\};")
# template folder families compiled through the generic MPxNode compute path
_SCAFFOLD = ("MPyNode", "MPyConstraint", "MPyFile")
_OTHERS = ("MPyMesh", "MPyNurbsCurve", "MPyNurbsSurface", "MPyDeformer",
           "MPySkinCluster", "MPyBlendShape", "MPyIkSolver", "MPyTransform",
           "MPyLocator")
# Optimizer rounds stamped from an older stage 1 (an optimizer pass of their
# own), left untouched by every splice.
_FOREIGN = {
    "templates/MPyNode/Spine/build/stages/spine/3_optimized/01_scalar_arc_table.cpp",
    "templates/MPyNode/Spine/build/stages/spine/3_optimized/02_weights_ref_write.cpp",
    "templates/MPyNode/Spine/build/stages/spine/3_optimized/03_fuse_sparse_weights.cpp",
}


def _read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read().replace("\r\n", "\n")


def _rel(path):
    return os.path.relpath(path, _paths.ROOT).replace(os.sep, "/")


def _stamp(text):
    m = re.search(r"^// build: ([0-9a-f]{12})", text, re.M)
    return m.group(1) if m else None


def _rows(families):
    """(template build dir, type name, spec) for every shipped row."""
    out = []
    for fam in families:
        for man in sorted(glob.glob(os.path.join(_paths.ROOT, "templates", fam,
                                                 "**", "build",
                                                 "manifest.json"),
                                    recursive=True)):
            with open(man, encoding="utf-8") as fh:
                for row in json.load(fh)["nodes"]:
                    out.append((os.path.dirname(man), row["type_name"],
                                row["spec"]))
    return out


def _array_outputs(spec):
    from mpynode.native.compiler.emit_attr import _members

    return [m["member"] for m in _members(spec)
            if m["kind"] == "outputs" and m["meta"].get("is_array")]


def _block(arrays):
    """The block the generator emits for these array members."""
    from mpynode.native.compiler.emit_compute import array_grow_lines

    outs = [{"member": a, "meta": {"is_array": True}} for a in arrays]
    return "".join(ln + "\n" for ln in array_grow_lines(outs))


def _after_gate(cpp):
    """The text right after compute()'s nodeState gate."""
    m = re.search(r"^MStatus \w+::compute\(const MPlug& \w+, MDataBlock& data\) "
                  r"\{\n", cpp, re.M)
    g = cpp.index(_GATE, m.end())
    return cpp[g + len(_GATE):]


def _lineage(build, node_type):
    out = glob.glob(os.path.join(build, "stages", node_type, "**", "*.cpp"),
                    recursive=True)
    out = [p for p in out if os.path.basename(p) != "1_transpiled.cpp"]
    for p in (os.path.join(build, node_type, node_type + ".cpp"),
              os.path.join(build, "source", node_type + ".cpp")):
        if os.path.isfile(p):
            out.append(p)
    return sorted(out)


class TestGenerator(unittest.TestCase):
    """The stage-1 codegen of every shipped row."""

    def test_each_array_output_is_filled_right_after_the_gate(self):
        from mpynode.native import compiler as codegen

        with_arrays = []
        for build, ty, spec in _rows(_SCAFFOLD):
            arrays = _array_outputs(spec)
            cpp    = codegen.generate_cpp(spec, for_port=True)
            with self.subTest(type=ty):
                if arrays:
                    self.assertTrue(_after_gate(cpp).startswith(_block(arrays)))
                    self.assertEqual(
                        _LIST_RE.findall(cpp),
                        [", ".join("&" + a for a in arrays)])
                else:
                    self.assertNotIn("_growAttrs", cpp)
            if arrays:
                with_arrays.append(ty)
        self.assertEqual(sorted(with_arrays),
                         ["bubbleSort", "mPyDnet", "procrustesTags", "spine",
                          "spline", "springChain"])

    def test_the_other_families_get_no_block(self):
        from mpynode.native import compiler as codegen

        rows = _rows(_OTHERS)
        self.assertGreater(len(rows), 15)
        for build, ty, spec in rows:
            with self.subTest(type=ty):
                self.assertNotIn("_growAttrs",
                                 codegen.generate_cpp(spec, for_port=True))

    def test_no_array_output_emits_nothing(self):
        from mpynode.native.compiler.emit_compute import array_grow_lines

        self.assertEqual(array_grow_lines([]), [])
        self.assertEqual(
            array_grow_lines([{"member": "aOut", "meta": {"type": "double"}}]),
            [])


class TestShippedLineage(unittest.TestCase):
    """Every lineage file of a row with array outputs, in its template and in
    the All Templates Plugin, carries stage 1's block right after the gate."""

    def test_every_current_lineage_file_has_the_block(self):
        allt = os.path.join(_paths.ROOT, "templates", "All Templates Plugin",
                            "build")
        seen, foreign = 0, set()
        for build, ty, spec in _rows(_SCAFFOLD):
            arrays = _array_outputs(spec)
            if not arrays:
                continue
            block = _block(arrays)
            for b in (build, allt):
                s1 = _read(os.path.join(b, "stages", ty, "1_transpiled.cpp"))
                self.assertTrue(_after_gate(s1).startswith(block))
                for p in _lineage(b, ty):
                    text = _read(p)
                    if _stamp(text) != _stamp(s1):
                        foreign.add(_rel(p))
                        continue
                    seen += 1
                    with self.subTest(file=_rel(p)):
                        self.assertTrue(_after_gate(text).startswith(block))
                        self.assertEqual(text.count("_growAttrs[]"), 1)
        self.assertEqual(foreign, _FOREIGN)
        # 6 rows x (template + All Templates copy): 40 current lineage files
        self.assertEqual(seen, 40)


class TestInterpretedReference(unittest.TestCase):
    """What the compiled side copies, read off the interpreted node."""

    _CVS = [(0, 0, 0), (1, 2, 0), (3, -1, 1), (4, 0, 2), (6, 1, 0)]

    def setUp(self):
        mc.file(new=True, force=True)

    def _spline(self):
        from mpynode._common.io import mpn_io

        payload = mpn_io.load_mpn(
            os.path.join(_paths.ROOT, "templates", "MPyNode", "De Boor Spline",
                         "template.mpn"),
            trusted=True)
        node = mpn_io.deserialize_node(payload, skip_selection=True).get_name()
        for k, v in enumerate(self._CVS):
            mc.setAttr("%s.cv[%d]" % (node, k), *v)
        return node

    def _assert_vec(self, got, want, places=6):
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=places)

    def test_a_first_read_of_a_missing_element_computes_up_to_it(self):
        node = self._spline()
        # samples[3] does not exist yet: N = 3 + 1, so it is the last sample,
        # the last CV, and samples[1] is the second of 4.
        self._assert_vec(mc.getAttr(node + ".samples[3]")[0], self._CVS[-1])
        self._assert_vec(mc.getAttr(node + ".samples[1]")[0],
                         (1.9259, 0.6667, 0.5185), places=4)
        self.assertEqual(mc.getAttr(node + ".samples", multiIndices=True),
                         [0, 1, 2, 3])

    def test_a_sparse_connection_counts_up_to_its_index(self):
        node  = self._spline()
        sinks = []
        for k in (0, 3):
            t = mc.createNode("transform", skipSelect=True)
            mc.connectAttr("%s.samples[%d]" % (node, k), t + ".translate")
            sinks.append(t)
        self._assert_vec(mc.getAttr(sinks[1] + ".translate")[0], self._CVS[-1])
        self._assert_vec(mc.getAttr(node + ".samples[1]")[0],
                         (1.9259, 0.6667, 0.5185), places=4)


if __name__ == "__main__":
    unittest.main()
