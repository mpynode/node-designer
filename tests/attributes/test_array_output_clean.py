"""A written array output is clean at the ATTRIBUTE, not only per element.

``_api2/helpers.write_multi_plug_value`` ended with
``array_handle.setAllClean()``, which cleans the ELEMENTS. The array attribute
itself stayed dirty, so the Evaluation Manager -- which schedules every
connected output of a node -- called compute again for each array output still
dirty: a Python node with K connected array outputs ran its expression K times
a frame under EM parallel / serial (Spine 2.0: 5 runs, 7.6 ms -> 1 run, 2.4 ms),
a DG read of a whole array paid one compute per array too, and a stateful
expression advanced K steps a frame (DNET drifted away from DG).

The helper now also calls ``data_block.setClean(attr)``. Its C++ twin is
``native/compiler/emit_attr._array_write_lines``; the compiled side is covered
by ``tests/compile/nodes/test_native_array_output_clean.py``.

Every family that writes user arrays through the helper is covered: mPyNode
and mPyConstraint directly, mPyMesh through ``write_user_outputs``.
"""

from __future__ import annotations

import sys
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init

# The expression bumps this counter on ``sys`` -- reachable from the exec
# namespace however this module was imported.
_COUNTER = "_mpynode_test_array_output_clean_runs"
_EXPR = (
    "import sys\n"
    "sys.%s = getattr(sys, %r, 0) + 1\n"
    "k = float(self.k)\n"
    "self.a = [[k + i, 0.0, 0.0] for i in range(4)]\n"
    "self.b = [k + 10.0 * i for i in range(4)]\n"
    "self.c = [k * i for i in range(4)]\n"
    "self.s = k\n" % (_COUNTER, _COUNTER)
)


def setUpModule():
    standalone_init()


def _runs() -> int:
    return getattr(sys, _COUNTER, 0)


def _reset_runs() -> None:
    setattr(sys, _COUNTER, 0)


def _create(family):
    if family == "mPyConstraint":
        from mpynode.wrappers.mpy_constraint import MPyConstraint as cls
    elif family == "mPyMesh":
        from mpynode.wrappers.mpy_mesh import MPyMesh as cls
    else:
        from mpynode.wrappers._mpy_node import MPyNode as cls
    return cls.create(name="probe")


class _Case(unittest.TestCase):
    """Fresh scene, plug-ins loaded, the EM mode restored afterwards."""

    FAMILIES = ("mPyNode", "mPyConstraint", "mPyMesh")

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        self._em_mode = mc.evaluationManager(query=True, mode=True)[0]
        _reset_runs()

    def tearDown(self):
        mc.evaluationManager(mode=self._em_mode)
        if hasattr(sys, _COUNTER):
            delattr(sys, _COUNTER)

    def _build(self, family, keyed):
        """probe: two CONNECTED array outputs (a: vector[], b: float[]), one
        array left unconnected (c) and a connected scalar (s)."""
        mc.file(new=True, force=True)
        w    = _create(family)
        name = w.get_name()
        w.add_input_attr("k", "float")
        w.add_output_attr("a", "vector", is_array=True)
        w.add_output_attr("b", "float",  is_array=True)
        w.add_output_attr("c", "float",  is_array=True)
        w.add_output_attr("s", "float")
        w.set_compute_expression(_EXPR)
        a_out, b_out = [], []
        for i in range(4):
            t = mc.createNode("transform", name="aOut%d" % i)
            mc.connectAttr("%s.a[%d]" % (name, i), t + ".translate")
            a_out.append(t)
            t = mc.createNode("transform", name="bOut%d" % i)
            mc.connectAttr("%s.b[%d]" % (name, i), t + ".translateY")
            b_out.append(t)
        s_out = mc.createNode("transform", name="sOut")
        mc.connectAttr(name + ".s", s_out + ".translateZ")
        if keyed:
            mc.setKeyframe(name, attribute="k", time=1, value=0.0,
                           inTangentType="linear", outTangentType="linear")
            mc.setKeyframe(name, attribute="k", time=50, value=49.0,
                           inTangentType="linear", outTangentType="linear")
        return name, a_out, b_out, s_out

    def _check_values(self, a_out, b_out, s_out, k, msg):
        for i in range(4):
            self.assertAlmostEqual(mc.getAttr(a_out[i] + ".translateX"), k + i,
                                   places=5, msg=msg)
            self.assertAlmostEqual(mc.getAttr(b_out[i] + ".translateY"), k + 10.0 * i,
                                   places=5, msg=msg)
        self.assertAlmostEqual(mc.getAttr(s_out + ".translateZ"), k, places=5, msg=msg)


class TestArrayOutputsRunOncePerFrameUnderEM(_Case):
    """The reported cost: one expression run per connected array output per
    frame under the Evaluation Manager."""

    def test_one_run_per_frame(self):
        for family in self.FAMILIES:
            for mode in ("parallel", "serial"):
                with self.subTest(family=family, mode=mode):
                    name, a_out, b_out, s_out = self._build(family, keyed=True)
                    mc.evaluationManager(mode=mode)
                    mc.currentTime(1)
                    mc.currentTime(2)  # warm-up: the EM graph is built
                    for frame in (3, 4, 5, 6):
                        _reset_runs()
                        mc.currentTime(frame)
                        self.assertEqual(_runs(), 1, "frame %d" % frame)
                        self._check_values(a_out, b_out, s_out, frame - 1.0,
                                           "%s %s frame %d" % (family, mode, frame))
                        self.assertEqual(_runs(), 1, "reads after frame %d" % frame)


class TestSiblingArraysCleanAfterOnePull(_Case):
    """DG: one evaluation publishes every array output, so reading a second
    array neither finds it dirty nor re-runs the expression."""

    def test_second_array_is_clean(self):
        mc.evaluationManager(mode="off")
        for family in self.FAMILIES:
            with self.subTest(family=family):
                name, a_out, b_out, s_out = self._build(family, keyed=False)
                mc.setAttr(name + ".k", 5.0)
                _reset_runs()
                self.assertEqual(mc.getAttr(name + ".b")[0], (5.0, 15.0, 25.0, 35.0))
                self.assertEqual(_runs(), 1)
                self.assertFalse(mc.isDirty(name + ".b", datablock=True), "b")
                self.assertFalse(mc.isDirty(name + ".a", datablock=True), "a")
                self.assertEqual(mc.getAttr(name + ".a[2]")[0], (7.0, 0.0, 0.0))
                self.assertEqual(_runs(), 1, "reading a re-ran the expression")


if __name__ == "__main__":
    unittest.main()
