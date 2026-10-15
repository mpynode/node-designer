"""An interpreted node recomputes once nodeState is back to Normal, as its
compiled twin does.

Measured 2026-10-15 on f84d9a4, interpreted vs compiled (All Templates
Plugin), every input changed while the node was suspended: the first read
after nodeState went back to Normal kept the value from before the suspension
on mPyNode, mPyConstraint, mPyMesh, mPyNurbsCurve and mPyNurbsSurface (26 of
60 reads of the round-2 nodeState probe; 285 of 360 with connected inputs and
nodeState 1-5), and on an mPyFile's user outputs. With a connected input the
node never recovered: later changes kept the stale value too. mPyFile's
outColor / outAlpha were right: its compute returns self, which leaves them
dirty.

Cause: while the node is suspended nothing dirties its outputs.
``dirty_affects.api2_dirty_gate`` drops every user-input change, and Maya
itself stops dirtying outMesh / outCurve / outSurface for a changed dynamic
input. A read in the meantime leaves the output clean, since the suspended
compute returns None. The connected input, never read, stays dirty, and a
dirty plug stops every later propagation.

The fix: a nodeState change that leaves a suspended state replays a
user-input change (``dirty_affects.declare_user_affects``), so the next read
computes. Entering a suspended state dirties nothing.

Under parallel evaluation the Evaluation Manager also has to know the user
affects: its graph keeps what ``setDependentsDirty`` declared when it was
built, and a nodeState change does not rebuild it. ``api2_dirty_gate`` lets
the affects through while the graph is being built, as the compiled twin's
``attributeAffects`` are there whatever its state.
"""
from __future__ import annotations

import inspect
import os
import shutil
import tempfile
import unittest

import maya.api.OpenMaya as om
import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_FAMILIES = ("mPyNode", "mPyConstraint", "mPyFile", "mPyMesh",
             "mPyNurbsCurve", "mPyNurbsSurface")
_STATES = (1, 2, 3, 4, 5)
_EXPR = ("self.outD = self.a * 3.0\n"
         "self.outV = (self.a, self.a + 1.0, self.a + 2.0)\n"
         "self.outA = [self.a * k for k in range(3)]\n")
# template, driven user input, geometry output
_GEO = (("MPyMesh/Game Of Life", "cellSize", "outMesh"),
        ("MPyNurbsCurve/NURBS Helix", "radius", "outCurve"),
        ("MPyNurbsSurface/NURBS Ripple", "amplitude", "outSurface"))


def _driver():
    return mc.createNode("transform", name="drv", skipSelect=True)


def _family_node(node_type, drv):
    """User input ``a`` fed by ``drv.tx``; user outputs ``outD`` = 3a,
    ``outV`` = (a, a + 1, a + 2) and the array ``outA`` = [0, a, 2a]."""
    import mpynode

    node = mc.createNode(node_type, name="n_" + node_type, skipSelect=True)
    w    = mpynode.wrap_node(node)
    w.add_input_attr("a", "double")
    w.add_output_attr("outD", "double")
    w.add_output_attr("outV", "double3")
    w.add_output_attr("outA", "double", is_array=True)
    w.set_compute_expression(_EXPR)
    mc.connectAttr(drv + ".tx", node + ".a")
    return node


def _template_node(rel):
    from mpynode._common.io import mpn_io

    path    = os.path.join(_paths.ROOT, "templates", rel, "template.mpn")
    payload = mpn_io.load_mpn(path, trusted=True)
    return mpn_io.deserialize_node(payload, skip_selection=True).get_name()


def _points(node, attr):
    obj = om.MSelectionList().add(node + "." + attr).getPlug(0).asMObject()
    if attr == "outMesh":
        pts = om.MFnMesh(obj).getPoints()
    elif attr == "outCurve":
        pts = om.MFnNurbsCurve(obj).cvPositions()
    else:
        pts = om.MFnNurbsSurface(obj).cvPositions()
    return [round(c, 6) for p in pts for c in (p.x, p.y, p.z)]


def _read(node):
    return (mc.getAttr(node + ".outD"), mc.getAttr(node + ".outVY"),
            mc.getAttr(node + ".outA[1]"))


def _expected(a):
    return (a * 3.0, a + 1.0, a)


class _Case(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        self.addCleanup(mc.file, new=True, force=True)


class TestUserOutputsAfterResume(_Case):
    """Hand-built node per family; the input comes through a connection."""

    def _run(self, read_while_suspended):
        for node_type in _FAMILIES:
            for state in _STATES:
                mc.file(new=True, force=True)
                drv  = _driver()
                node = _family_node(node_type, drv)
                mc.setAttr(drv + ".tx", 1.0)
                self.assertEqual(_read(node), _expected(1.0))
                mc.setAttr(node + ".nodeState", state)
                mc.setAttr(drv + ".tx", 2.0)
                with self.subTest(family=node_type, state=state):
                    if read_while_suspended:
                        # not evaluated: the last value, the array element too
                        self.assertEqual(_read(node), _expected(1.0))
                    mc.setAttr(node + ".nodeState", 0)
                    self.assertEqual(_read(node), _expected(2.0))
                    mc.setAttr(drv + ".tx", 4.0)
                    self.assertEqual(_read(node), _expected(4.0))

    def test_input_changed_while_suspended_and_read(self):
        self._run(read_while_suspended=True)

    def test_input_changed_while_suspended_not_read(self):
        self._run(read_while_suspended=False)

    def test_suspended_before_any_read(self):
        for node_type in _FAMILIES:
            mc.file(new=True, force=True)
            drv  = _driver()
            node = _family_node(node_type, drv)
            mc.setAttr(node + ".nodeState", 1)
            mc.setAttr(drv + ".tx", 2.0)
            mc.getAttr(node + ".outA[1]")
            mc.setAttr(node + ".nodeState", 0)
            with self.subTest(family=node_type):
                self.assertEqual(_read(node), _expected(2.0))

    def test_left_by_undo_and_by_redo(self):
        mc.undoInfo(state=True, infinity=True)
        for node_type in _FAMILIES:
            mc.file(new=True, force=True)
            drv  = _driver()
            node = _family_node(node_type, drv)
            mc.setAttr(drv + ".tx", 1.0)
            _read(node)
            mc.setAttr(node + ".nodeState", 2)
            # the input changes outside the undo queue, so undo / redo move
            # nodeState alone
            mc.undoInfo(stateWithoutFlush=False)
            mc.setAttr(drv + ".tx", 2.0)
            mc.undoInfo(stateWithoutFlush=True)
            _read(node)
            mc.undo()
            with self.subTest(family=node_type, left_by="undo"):
                self.assertEqual(mc.getAttr(node + ".nodeState"), 0)
                self.assertEqual(_read(node), _expected(2.0))
            mc.setAttr(node + ".nodeState", 2)
            mc.setAttr(node + ".nodeState", 0)
            mc.undo()
            mc.undoInfo(stateWithoutFlush=False)
            mc.setAttr(drv + ".tx", 5.0)
            mc.undoInfo(stateWithoutFlush=True)
            _read(node)
            mc.redo()
            with self.subTest(family=node_type, left_by="redo"):
                self.assertEqual(mc.getAttr(node + ".nodeState"), 0)
                self.assertEqual(_read(node), _expected(5.0))


class TestGeometryOutputAfterResume(_Case):
    """outMesh / outCurve / outSurface: a user input reaches them through
    Maya, which stops while the node is suspended. The reference is a twin
    node fed by the same driver and never suspended."""

    def test_geometry_output(self):
        for rel, attr, out in _GEO:
            for state in _STATES:
                mc.file(new=True, force=True)
                drv  = _driver()
                node = _template_node(rel)
                twin = _template_node(rel)
                for n in (node, twin):
                    mc.connectAttr(drv + ".tx", n + "." + attr, force=True)
                mc.setAttr(drv + ".tx", 1.0)
                before = _points(node, out)
                self.assertEqual(before, _points(twin, out))
                mc.setAttr(node + ".nodeState", state)
                mc.setAttr(drv + ".tx", 2.0)
                _points(node, out)
                mc.setAttr(node + ".nodeState", 0)
                with self.subTest(template=rel, state=state):
                    want = _points(twin, out)
                    self.assertNotEqual(want, before)
                    self.assertEqual(_points(node, out), want)


class TestReopenedWhileSuspended(_Case):
    """The after-read sweep (``dirty_affects.dirty_file_read_outputs``) skips
    a suspended node; returning it to Normal is what computes it."""

    def test_user_outputs(self):
        tmp = tempfile.mkdtemp(prefix="mpynode-resume-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "suspended.ma")
        for node_type in _FAMILIES:
            mc.file(new=True, force=True)
            node = _family_node(node_type, _driver())
            mc.setAttr("drv.tx", 2.0)
            self.assertEqual(_read(node), _expected(2.0))
            mc.setAttr(node + ".nodeState", 1)
            mc.file(rename=path)
            mc.file(save=True, type="mayaAscii", force=True)
            mc.file(new=True, force=True)
            mc.file(path, open=True, force=True)
            mc.setAttr(node + ".nodeState", 0)
            with self.subTest(family=node_type):
                self.assertEqual(_read(node), _expected(2.0))


class TestOnlyLeavingDirties(_Case):
    """``declare_user_affects`` runs inside setDependentsDirty, where the
    nodeState plug still holds the state being left."""

    def _affected(self, node, state, connect=False):
        from mpynode._api2._mpy_node import MPyNode
        from mpynode._common.plugs import dirty_affects

        mc.setAttr(node + ".nodeState", state)
        if connect:
            src = mc.createNode("transform", skipSelect=True)
            mc.addAttr(src, ln="st", at="short")
            mc.setAttr(src + ".st", state)
            mc.connectAttr(src + ".st", node + ".nodeState")
        sel   = om.MSelectionList().add(node)
        mobj  = sel.getDependNode(0)
        plug  = om.MFnDependencyNode(mobj).findPlug("nodeState", False)
        plugs = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj, plug, plugs, MPyNode._input_attrs_attr,
            MPyNode._output_attrs_attr,
            expression_attr=MPyNode._expression_attr)
        return sorted({plugs[i].partialName(useLongNames=True)
                       for i in range(len(plugs))})

    def test_leaving_a_suspended_state_dirties_every_output(self):
        for state in _STATES:
            mc.file(new=True, force=True)
            node = _family_node("mPyNode", _driver())
            _read(node)
            with self.subTest(state=state):
                # every element and compound child, as a user-input change
                self.assertEqual(self._affected(node, state),
                                 ["outA", "outA[0]", "outA[1]", "outA[2]",
                                  "outD", "outV", "outVX", "outVY", "outVZ"])

    def test_entering_a_suspended_state_dirties_nothing(self):
        node = _family_node("mPyNode", _driver())
        _read(node)
        self.assertEqual(self._affected(node, 0), [])

    def test_a_connected_node_state_is_not_read(self):
        node = _family_node("mPyNode", _driver())
        _read(node)
        self.assertIn("outD", self._affected(node, 0, connect=True))

    def test_every_family_passes_its_geometry_output(self):
        from mpynode._api2 import mpy_mesh, mpy_nurbs_curve, mpy_nurbs_surface

        for mod, cls, attr in (
                (mpy_mesh, "MPyMesh", "_out_mesh_attr"),
                (mpy_nurbs_curve, "MPyNurbsCurve", "_out_curve_attr"),
                (mpy_nurbs_surface, "MPyNurbsSurface", "_out_surface_attr")):
            src = inspect.getsource(getattr(mod, cls).setDependentsDirty)
            with self.subTest(family=cls):
                self.assertIn("state_outputs=(type(self).%s,)" % attr, src)


class TestKeyedInputUnderParallelEvaluation(_Case):
    """A keyed input under parallel evaluation, the Evaluation Manager graph
    built while the node is suspended. ``dirty_affects.api2_dirty_gate``
    dropped the user affects during that build, and a nodeState change does
    not rebuild the graph: after nodeState went back to Normal the first frame
    computed and every later frame kept its value (mPyNode, mPyConstraint;
    measured 2026-10-15), while the compiled twin, whose attributeAffects do
    not depend on its state, kept tracking. The reference is a twin fed by the
    same driver and never suspended."""

    _FRAMES = (60, 110, 130, 150, 61, 62)

    def setUp(self):
        super().setUp()
        mode = (mc.evaluationManager(q=True, mode=True) or ["off"])[0]
        if mode not in ("off", "serial", "parallel"):
            mode = "off"
        self.addCleanup(mc.evaluationManager, mode=mode)

    @staticmethod
    def _scene(lo, hi):
        """A new scene at frame 30 under parallel evaluation, and a driver
        whose translateX is keyed linearly from ``lo`` at 1 to ``hi`` at 200."""
        mc.file(new=True, force=True)
        mc.evaluationManager(mode="parallel")
        mc.currentTime(30)
        drv = _driver()
        mc.setKeyframe(drv, at="translateX", t=1, v=lo)
        mc.setKeyframe(drv, at="translateX", t=200, v=hi)
        mc.keyTangent(drv, itt="linear", ott="linear")
        return drv

    @staticmethod
    def _rounded(values):
        return tuple(round(v, 6) for v in values)

    def _suspend_rebuild_resume(self, node, state):
        mc.setAttr(node + ".nodeState", state)
        mc.evaluationManager(invalidate=True)
        mc.currentTime(40)
        mc.setAttr(node + ".nodeState", 0)

    def test_user_outputs(self):
        for node_type in _FAMILIES:
            for state in (1, 2):
                drv  = self._scene(0.0, 199.0)
                node = _family_node(node_type, drv)
                twin = _family_node(node_type, drv)
                self._suspend_rebuild_resume(node, state)
                for frame in self._FRAMES:
                    mc.currentTime(frame)
                    with self.subTest(family=node_type, state=state, frame=frame):
                        want = self._rounded(_expected(frame - 1.0))
                        self.assertEqual(self._rounded(_read(twin)), want)
                        self.assertEqual(self._rounded(_read(node)), want)

    def test_user_outputs_reopened_while_suspended(self):
        tmp = tempfile.mkdtemp(prefix="mpynode-resume-keyed-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = os.path.join(tmp, "keyed.ma")
        for node_type in _FAMILIES:
            drv  = self._scene(0.0, 199.0)
            node = _family_node(node_type, drv)
            twin = _family_node(node_type, drv)
            mc.setAttr(node + ".nodeState", 1)
            mc.file(rename=path)
            mc.file(save=True, type="mayaAscii", force=True)
            mc.file(new=True, force=True)
            mc.file(path, open=True, force=True)
            mc.evaluationManager(mode="parallel")
            mc.currentTime(40)
            mc.setAttr(node + ".nodeState", 0)
            for frame in self._FRAMES:
                mc.currentTime(frame)
                with self.subTest(family=node_type, frame=frame):
                    want = self._rounded(_expected(frame - 1.0))
                    self.assertEqual(self._rounded(_read(twin)), want)
                    self.assertEqual(self._rounded(_read(node)), want)

    def test_geometry_output(self):
        for rel, attr, out in _GEO:
            for state in (1, 2):
                drv  = self._scene(1.0, 5.0)
                node = _template_node(rel)
                twin = _template_node(rel)
                for n in (node, twin):
                    mc.connectAttr(drv + ".tx", n + "." + attr, force=True)
                self._suspend_rebuild_resume(node, state)
                seen = set()
                for frame in self._FRAMES:
                    mc.currentTime(frame)
                    with self.subTest(template=rel, state=state, frame=frame):
                        want = _points(twin, out)
                        seen.add(tuple(want))
                        self.assertEqual(_points(node, out), want)
                self.assertEqual(len(seen), len(self._FRAMES), rel)


if __name__ == "__main__":
    unittest.main()
