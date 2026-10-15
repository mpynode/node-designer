"""nodeState dirties a compiled node's array outputs (v46), so an array element
read while the node was suspended recomputes once nodeState is back to Normal,
as the interpreted node's does.

The interpreted node dirties its outputs when nodeState leaves a suspended
state (``dirty_affects.declare_user_affects``, see
tests/nodes/test_node_state_resume.py). A compiled plain or compound output
needs nothing for that: the suspended compute leaves it dirty. An array
ELEMENT read while suspended is left clean, though, and kept its old value
after nodeState went back to Normal -- for good when its input came through a
connection. Measured 2026-10-15, interpreted (fixed) vs compiled, nodeState
1-5, DG and parallel evaluation: De Boor Spline samples[1] differed on 10 of
30 resumed reads and 15 of 30 later ones, Procrustes Tags outMatrix[1] on 10
of 30 resumed reads; 0 of both with the edge.

The compiled node now declares ``attributeAffects(MPxNode::state, <array>)``
for each array output, at the end of initialize(). Pinned here: the generator
for every shipped row, and every shipped lineage file stamped from the current
stage 1.
"""
from __future__ import annotations

import glob
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


_EDGE    = "    attributeAffects(MPxNode::state, %s);\n"
_EDGE_RE = re.compile(r"attributeAffects\(MPxNode::state, (\w+)\);")
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


def _initialize(cpp):
    """The text of ``<cls>::initialize()``, braces included."""
    m     = re.search(r"^MStatus \w+::initialize\(\) \{\n", cpp, re.M)
    depth = 0
    for j in range(m.end() - 2, len(cpp)):
        if cpp[j] == "{":
            depth += 1
        elif cpp[j] == "}":
            depth -= 1
            if depth == 0:
                return cpp[m.start():j + 1]
    raise AssertionError("initialize() is not closed")


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

    def test_each_array_output_takes_the_edge_last(self):
        from mpynode.native import compiler as codegen

        with_arrays = []
        for build, ty, spec in _rows(_SCAFFOLD):
            arrays = _array_outputs(spec)
            init   = _initialize(codegen.generate_cpp(spec, for_port=True))
            with self.subTest(type=ty):
                self.assertEqual(_EDGE_RE.findall(init), arrays)
                tail = "".join(_EDGE % a for a in arrays)
                self.assertTrue(init.endswith(tail + "    return MS::kSuccess;\n}"))
            if arrays:
                with_arrays.append(ty)
        self.assertEqual(sorted(with_arrays),
                         ["bubbleSort", "mPyDnet", "procrustesTags", "spine",
                          "spline", "springChain"])

    def test_the_other_families_get_no_edge(self):
        from mpynode.native import compiler as codegen

        rows = _rows(_OTHERS)
        self.assertGreater(len(rows), 15)
        for build, ty, spec in rows:
            with self.subTest(type=ty):
                self.assertNotIn("attributeAffects(MPxNode::state",
                                 codegen.generate_cpp(spec, for_port=True))


class TestShippedLineage(unittest.TestCase):
    """Every lineage file of a row with array outputs, in its template and in
    the All Templates Plugin, carries the stage-1 initialize() unchanged."""

    def test_every_current_lineage_file_has_the_edge(self):
        allt = os.path.join(_paths.ROOT, "templates", "All Templates Plugin",
                            "build")
        seen, foreign = 0, set()
        for build, ty, spec in _rows(_SCAFFOLD):
            arrays = _array_outputs(spec)
            if not arrays:
                continue
            for b in (build, allt):
                s1   = _read(os.path.join(b, "stages", ty, "1_transpiled.cpp"))
                init = _initialize(s1)
                self.assertEqual(_EDGE_RE.findall(init), arrays)
                for p in _lineage(b, ty):
                    text = _read(p)
                    if _stamp(text) != _stamp(s1):
                        foreign.add(_rel(p))
                        continue
                    seen += 1
                    with self.subTest(file=_rel(p)):
                        self.assertEqual(_initialize(text), init)
        self.assertEqual(foreign, _FOREIGN)
        # 6 rows x (template + All Templates copy): 40 current lineage files
        self.assertEqual(seen, 40)


if __name__ == "__main__":
    unittest.main()
