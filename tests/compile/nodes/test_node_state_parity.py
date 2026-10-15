"""A suspended compiled node is not evaluated, as the interpreted node is not (v45).

The interpreted MPxNode families -- MPyNode, MPyConstraint, MPyFile, MPyMesh,
MPyNurbsCurve, MPyNurbsSurface -- return at once from compute while nodeState
is not Normal (``dirty_affects.api2_suspended_in_block``, read off the data
block): Has No Effect, Blocking and the Waiting states alike. The outputs are
not written, so they keep their last value, or their default before any
evaluation. Until v45 no compiled compute read nodeState: a suspended compiled
node went on computing (all 4 mPyFile types, measured; worst outSize error 9).

The compiled compute now returns kSuccess right after its plug guard while
nodeState is not Normal. The deformer, skin, IK-solver and transform families
already behaved as their twins (Maya handles them the same on both sides,
measured), and the locator's gate is v44's setDependentsDirty override, so
none of them gets this compute gate.

Pinned here: the generator, every shipped lineage file stamped from the
current stage 1, the files still waiting (optimizer rewrites at the insertion
point, an open question), and the interpreted reference.
"""
from __future__ import annotations

import glob
import inspect
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


_GATE = ("    // Suspended (nodeState not Normal): not evaluated, as the interpreted\n"
         "    // compute returns (dirty_affects.api2_suspended_in_block). The outputs\n"
         "    // are not written: they keep their last value.\n"
         "    if (data.inputValue(MPxNode::state).asShort() != 0)\n"
         "        return MS::kSuccess;\n")
_GUARD_END = "return MS::kUnknownParameter;\n"

# template folder families whose compiled node is a plain MPxNode with compute()
_GATED = ("MPyNode", "MPyConstraint", "MPyFile", "MPyMesh", "MPyNurbsCurve",
          "MPyNurbsSurface")
_UNGATED = ("MPyDeformer", "MPySkinCluster", "MPyBlendShape", "MPyIkSolver",
            "MPyTransform", "MPyLocator")

# Lineage files the splice refused: an optimizer round rewrote the lines right
# after the plug guard, where the gate goes. Left untouched pending the
# user's call (no hand edit of optimizer-rewritten code).
_PENDING = {
    "templates/MPyMesh/Mesh Maze/build/meshMaze/meshMaze.cpp",
    "templates/MPyMesh/Mesh Maze/build/source/meshMaze.cpp",
    "templates/MPyMesh/Mesh Maze/build/stages/meshMaze/3_optimized/"
    "03_palette_threads_overlap_carve.cpp",
    "templates/MPyMesh/Mesh Maze/build/stages/meshMaze/3_optimized/04_accept.cpp",
    "templates/MPyMesh/Voxelize/build/voxelizeMesh/voxelizeMesh.cpp",
    "templates/MPyMesh/Voxelize/build/source/voxelizeMesh.cpp",
    "templates/MPyMesh/Voxelize/build/stages/voxelizeMesh/3_optimized/"
    "01_reuse_outmesh_percube_colors.cpp",
    "templates/All Templates Plugin/build/source/meshMaze.cpp",
    "templates/All Templates Plugin/build/source/voxelizeMesh.cpp",
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
    """(template build dir, family, type name, spec) for every shipped row."""
    out = []
    for fam in families:
        for man in sorted(glob.glob(os.path.join(_paths.ROOT, "templates", fam,
                                                 "**", "build",
                                                 "manifest.json"),
                                    recursive=True)):
            with open(man, encoding="utf-8") as fh:
                for row in json.load(fh)["nodes"]:
                    out.append((os.path.dirname(man), fam, row["type_name"],
                                row["spec"]))
    return out


_COMPUTE_RE = re.compile(r"MStatus \w+::compute\(const MPlug& \w+, "
                         r"MDataBlock& data\) \{")


def _gated(cpp):
    """True when compute() runs the nodeState gate right after its guard."""
    c = _COMPUTE_RE.search(cpp).start()
    g = cpp.index(_GUARD_END, c) + len(_GUARD_END)
    return cpp.startswith(_GATE, g)


def _lineage(build, node_type):
    out = glob.glob(os.path.join(build, "stages", node_type, "**", "*.cpp"),
                    recursive=True)
    for p in (os.path.join(build, node_type, node_type + ".cpp"),
              os.path.join(build, "source", node_type + ".cpp")):
        if os.path.isfile(p):
            out.append(p)
    return sorted(out)


class TestGenerator(unittest.TestCase):
    """The stage-1 codegen of every shipped row."""

    def test_every_mpxnode_family_compute_is_gated(self):
        from mpynode.native import compiler as codegen

        rows = _rows(_GATED)
        for build, fam, ty, spec in rows:
            with self.subTest(type=ty):
                self.assertTrue(_gated(codegen.generate_cpp(spec, for_port=True)))
        # 21 templates
        self.assertEqual(len(rows), 21)

    def test_the_other_families_get_no_compute_gate(self):
        from mpynode.native import compiler as codegen

        rows = _rows(_UNGATED)
        for build, fam, ty, spec in rows:
            with self.subTest(type=ty):
                cpp = codegen.generate_cpp(spec, for_port=True)
                self.assertNotIn("data.inputValue(MPxNode::state)", cpp)
        self.assertEqual(len(rows), 17)


class TestShippedLineage(unittest.TestCase):
    """Every lineage file stamped from the current stage 1 carries the gate."""

    def test_every_current_lineage_file_is_gated(self):
        seen, missing = 0, set()
        allt = os.path.join(_paths.ROOT, "templates", "All Templates Plugin",
                            "build")
        for build, fam, ty, _spec in _rows(_GATED):
            builds = [build]
            if os.path.isfile(os.path.join(allt, "stages", ty,
                                           "1_transpiled.cpp")):
                builds.append(allt)
            for b in builds:
                stamp = _stamp(_read(os.path.join(b, "stages", ty,
                                                  "1_transpiled.cpp")))
                for path in _lineage(b, ty):
                    text = _read(path)
                    if _stamp(text) != stamp:
                        if _rel(path) in _PENDING:
                            missing.add(_rel(path))
                        continue  # a foreign stamp: never spliced
                    with self.subTest(file=_rel(path)):
                        self.assertTrue(_gated(text))
                    seen += 1
        # 42 moved stage-1 files (21 templates and their 21 All Templates
        # copies) and the 128 lineage files spliced from them
        self.assertEqual(seen, 170)
        self.assertEqual(missing, _PENDING)

    def test_the_pending_files_are_not_gated(self):
        for rel in sorted(_PENDING):
            with self.subTest(file=rel):
                text = _read(os.path.join(_paths.ROOT, rel))
                self.assertNotIn("data.inputValue(MPxNode::state)", text)


class TestInterpretedReference(unittest.TestCase):
    """What the compiled side copies, read off the interpreted node."""

    def test_every_interpreted_compute_returns_while_suspended(self):
        from mpynode._api2._mpy_node import MPyNode
        from mpynode._api2.mpy_constraint import MPyConstraint
        from mpynode._api2.mpy_file import MPyFile
        from mpynode._api2.mpy_mesh import MPyMesh
        from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve
        from mpynode._api2.mpy_nurbs_surface import MPyNurbsSurface

        for cls in (MPyNode, MPyConstraint, MPyFile, MPyMesh, MPyNurbsCurve,
                    MPyNurbsSurface):
            with self.subTest(cls=cls.__name__):
                src = inspect.getsource(cls.compute)
                self.assertIn("api2_suspended_in_block(self, data_block)", src)

    def test_every_state_but_normal_skips(self):
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        w = MPyNode.create(name="stateRef")
        n = w.get_name()
        w.add_input_attr("x", "double")
        w.add_output_attr("y", "double")
        w.set_compute_expression("self.y = self.x * 2.0\n")
        mc.setAttr(n + ".x", 1.0)
        last = 2.0
        self.assertEqual(mc.getAttr(n + ".y"), last)
        for state in range(1, 6):
            with self.subTest(nodeState=state):
                # suspended: the output keeps its last value
                mc.setAttr(n + ".nodeState", state)
                mc.setAttr(n + ".x", 100.0 + state)
                self.assertEqual(mc.getAttr(n + ".y"), last)
                # Normal again: the next input change evaluates
                mc.setAttr(n + ".nodeState", 0)
                mc.setAttr(n + ".x", float(state))
                last = 2.0 * state
                self.assertEqual(mc.getAttr(n + ".y"), last)


if __name__ == "__main__":
    unittest.main()
