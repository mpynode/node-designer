"""User outputs are ``cachedInternally``: one evaluation serves every read.

``add_output_attr`` creates outputs with ``writable=False``, and ``cmds.addAttr``
defaults ``cachedInternally`` to FALSE for a non-writable attribute. A numeric
output keeps its value regardless, but a TYPED output (``dt=`` matrix / string /
python / hex / mesh / nurbsCurve / nurbsSurface) drops it after each read, so
every read re-ran the whole expression:

  * an array output wired element-by-element re-ran once per PULLED element --
    N worlds -> mPyNode -> N ``offsetParentMatrix`` ran N times a frame in DG;
  * a single output feeding K consumers re-ran K times.

Measured on Maya 2025 mayapy, 2026-09-23 (DG, runs/frame and pull time):

    N=30  matrix array -> offsetParentMatrix    30 runs 31.8 ms  ->  1 run 1.5 ms
    N=200 matrix array -> offsetParentMatrix   200 runs  832 ms  ->  1 run 8.5 ms
    mesh output -> 3 consumer meshes             3 runs          ->  1 run

EM Parallel already ran once a frame. Nothing on the compute side cleans a
non-cached typed element: ``setAllClean`` / ``setClean`` on the parent or on
every element leaves them dirty again by the next pull, with no
``setDependentsDirty`` in between.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

import maya.api.OpenMaya as om
import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init

# The expression bumps this counter on ``sys`` -- reachable from the exec
# namespace however this module was imported.
_COUNTER = "_mpynode_test_output_cached_runs"
_COUNT   = (
    "import sys\n"
    "sys.%s = getattr(sys, %r, 0) + 1\n" % (_COUNTER, _COUNTER)
)
N = 12


def setUpModule():
    standalone_init()


def _runs() -> int:
    return getattr(sys, _COUNTER, 0)


def _reset_runs() -> None:
    setattr(sys, _COUNTER, 0)


def _attr_fn(node: str, attr: str) -> om.MFnAttribute:
    obj = om.MSelectionList().add(node).getDependNode(0)
    return om.MFnAttribute(om.MFnDependencyNode(obj).attribute(attr))


class _DGCase(unittest.TestCase):
    """Fresh scene, plug-ins loaded, Evaluation Manager OFF (DG) for the test."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        self._em_mode = mc.evaluationManager(query=True, mode=True)[0]
        mc.evaluationManager(mode="off")
        _reset_runs()

    def tearDown(self):
        mc.evaluationManager(mode=self._em_mode)
        if hasattr(sys, _COUNTER):
            delattr(sys, _COUNTER)

    def _node(self):
        from mpynode.wrappers._mpy_node import MPyNode

        return MPyNode.create(name="probe")


class TestMatrixArrayRunsOncePerFrame(_DGCase):
    """The reported case: N driver worlds -> mPyNode -> N offsetParentMatrix."""

    def test_one_run_per_frame_for_every_connected_element(self):
        w = self._node()
        w.add_input_attr("inMats", "matrix", is_array=True)
        w.add_output_attr("outOpm", "matrix", is_array=True)
        w.set_compute_expression(_COUNT + "self.outOpm = self.inMats\n")

        drivers, targets = [], []
        for i in range(N):
            d = mc.spaceLocator(name="drv%d" % i)[0]
            mc.setKeyframe(d, attribute="tx", time=1, value=0.0)
            mc.setKeyframe(d, attribute="tx", time=10, value=10.0 + i)
            mc.connectAttr(d + ".worldMatrix[0]", "probe.inMats[%d]" % i)
            t = mc.createNode("transform", name="tgt%d" % i)
            mc.connectAttr("probe.outOpm[%d]" % i, t + ".offsetParentMatrix")
            drivers.append(d)
            targets.append(t)

        for frame in (2, 3, 4):
            _reset_runs()
            mc.currentTime(frame)
            got = [mc.getAttr(t + ".worldMatrix[0]")[12] for t in targets]
            self.assertEqual(_runs(), 1, "frame %d" % frame)
            want = [mc.getAttr(d + ".tx") for d in drivers]
            for i, (g, e) in enumerate(zip(got, want)):
                self.assertAlmostEqual(g, e, places=6,
                                       msg="frame %d element %d" % (frame, i))


class TestTypedArraysRunOncePerChange(_DGCase):
    """Every typed array kind, pulled element by element with getAttr."""

    def _pull_each(self, attr_type, expr):
        w = self._node()
        w.add_input_attr("a", "float")
        w.add_output_attr("out", attr_type, is_array=True)
        w.set_compute_expression(_COUNT + "self.out = " + expr + "\n")
        mc.getAttr("probe.out[0]")  # first write materialises all N elements
        self.assertEqual(len(mc.getAttr("probe.out", multiIndices=True)), N)
        pulls = []
        for value in (1.0, 2.0, 3.0):
            mc.setAttr("probe.a", value)
            _reset_runs()
            got = [mc.getAttr("probe.out[%d]" % i) for i in range(N)]
            self.assertEqual(_runs(), 1, "%s, a=%s" % (attr_type, value))
            pulls.append((value, got))
        return pulls

    def test_string_array(self):
        pulls = self._pull_each(
            "string", "[str(self.a + i) for i in range(%d)]" % N)
        for value, got in pulls:
            self.assertEqual(got, [str(value + i) for i in range(N)])

    def test_python_array(self):
        self._pull_each("python", "[{'v': self.a + i} for i in range(%d)]" % N)


class TestMeshOutputRunsOnceForManyConsumers(_DGCase):
    """A single typed output feeding K consumers ran K times."""

    def test_three_consumers_one_run(self):
        w = self._node()
        w.add_input_attr("inMesh", "mesh")
        w.add_input_attr("a", "float")
        w.add_output_attr("outMesh", "mesh")
        w.set_compute_expression(_COUNT + "self.outMesh = self.inMesh\n")
        src   = mc.polySphere(subdivisionsX=20, subdivisionsY=20)[0]
        shape = mc.listRelatives(src, shapes=True)[0]
        mc.connectAttr(shape + ".worldMesh[0]", "probe.inMesh")
        consumers = []
        for _ in range(3):
            m = mc.createNode("mesh")
            mc.connectAttr("probe.outMesh", m + ".inMesh")
            consumers.append(m)

        for value in (1.0, 2.0, 3.0):
            mc.setAttr("probe.a", value)
            _reset_runs()
            counts = [mc.polyEvaluate(m, vertex=True) for m in consumers]
            self.assertEqual(_runs(), 1, "a=%s" % value)
            self.assertEqual(counts, [382] * 3)


class TestOutputAttrsAreCached(_DGCase):
    """The flag itself: set for every output kind, and saved with the scene."""

    def test_every_output_kind_is_cached(self):
        from mpynode.wrappers._mpy_node import VALID_OUTPUT_TYPES

        w = self._node()
        for kind in VALID_OUTPUT_TYPES:
            name = "o" + kind[0].upper() + kind[1:]
            w.add_output_attr(name, kind)
            w.add_output_attr(name + "Arr", kind, is_array=True)
            with self.subTest(kind=kind):
                self.assertTrue(_attr_fn("probe", name).cached)
                self.assertTrue(_attr_fn("probe", name + "Arr").cached)

    def test_cached_survives_ma_round_trip(self):
        w = self._node()
        w.add_output_attr("outOpm", "matrix", is_array=True)
        w.add_output_attr("outStr", "string")
        w.add_output_attr("outMesh", "mesh")
        tmp = tempfile.mkdtemp(prefix="mpynode-output-cached-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "cached.ma")
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(path, open=True, force=True)
        for attr in ("outOpm", "outStr", "outMesh"):
            with self.subTest(attr=attr):
                self.assertTrue(_attr_fn("probe", attr).cached)


if __name__ == "__main__":
    unittest.main()
