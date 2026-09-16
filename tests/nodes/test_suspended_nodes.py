"""A suspended Python node (``nodeState`` Has No Effect / Blocking -- set by
Convert to C++, or by hand) must cost nothing per frame.

Two things kept costing after the outputs were moved off a converted
mPyBlendShape (Combo Correctives, 1306 verts, 167 targets; measured 2026-09-11):

* the Evaluation Manager evaluates a node whose inputs animate whether or not
  anything reads its outputs -- 8 deforms in 8 frames, 142 ms/frame, the same
  as before the convert. ``nodeState`` is what stops that, so the convert sets
  it (see ``node_swap._snapshot_state``);
* with the deform gone, ~100 ms/frame remained: the per-frame ``timeChanged``
  callback re-dirtied the node, and the Python ``setDependentsDirty`` override
  ran ~3,800 times a frame reading and decoding ``_inputAttrs`` each time;
* with the gate in, ~45 ms/frame remained in Parallel: ``auto_dirty``'s
  source-side callbacks dispatched ~42 ``dgdirty`` + envelope touches a frame
  at the suspended destination (~8,900 ``setDependentsDirty`` calls a frame).

These pin the callback half; ``test_dirty_recompute`` pins the dirty gate.
"""
from __future__ import annotations

import unittest
from unittest import mock

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestTimeChangeCallbacksSkipSuspendedNodes(unittest.TestCase):
    """Each deformer family's ``_on_time_change`` touches ``envelope`` on every
    node of its type so the deformer re-evaluates per frame. A suspended node
    has nothing to re-evaluate, so it is left alone -- touching it only
    re-dirties a node the Evaluation Manager would then evaluate for nothing."""

    _FAMILIES = (
        ("mpynode._api1.mpy_deformer", "mPyDeformer"),
        ("mpynode._api1.mpy_blend_shape", "mPyBlendShape"),
        ("mpynode._api1.mpy_skin_cluster", "mPySkinCluster"),
    )

    def setUp(self):
        mc.file(new=True, force=True)

    def _touched(self, module, node):
        """The ``.envelope`` writes the callback issued, as a set of plugs."""
        real_set_attr = mc.setAttr
        calls         = []

        def spy(*args, **kwargs):
            calls.append(args[0] if args else None)
            return real_set_attr(*args, **kwargs)

        with mock.patch("maya.cmds.setAttr", spy):
            module._on_time_change(None)
        return {c for c in calls if isinstance(c, str) and c.endswith(".envelope")}

    def test_every_family_skips_a_suspended_node_and_touches_a_live_one(self):
        import importlib

        for mod_name, node_type in self._FAMILIES:
            module = importlib.import_module(mod_name)
            sphere = mc.polySphere(sx=6, sy=6)[0]
            node   = mc.deformer(sphere, type=node_type)[0]
            with self.subTest(node_type=node_type):
                self.assertIn(node + ".envelope", self._touched(module, node),
                              "a live %s must be touched" % node_type)
                mc.setAttr(node + ".nodeState", 1)          # Has No Effect
                self.assertNotIn(node + ".envelope", self._touched(module, node),
                                 "a suspended %s must be left alone" % node_type)
                mc.setAttr(node + ".nodeState", 0)
                self.assertIn(node + ".envelope", self._touched(module, node),
                              "un-suspending resumes the touch")


class TestAutoDirtyLeavesSuspendedNodesAlone(unittest.TestCase):
    """``auto_dirty`` is what re-dirties a deformer per frame in practice: a
    source-side dirty callback ``dgdirty``-s the destination and touches its
    envelope. A suspended destination is left alone (un-suspending resumes),
    and a destination that no longer exists is ignored rather than dereferenced
    -- mayapy crashed in ``MFnDependencyNode::name`` on the first source dirty
    after a covered deformer was deleted with undo off."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _calls_on(self, node, fn):
        """(command, first arg) pairs aimed at ``node`` while ``fn`` runs."""
        real_dg, real_set = mc.dgdirty, mc.setAttr
        hits = []

        def spy_dg(*a, **k):
            hits.append(("dgdirty", a[0] if a else None))
            return real_dg(*a, **k)

        def spy_set(*a, **k):
            hits.append(("setAttr", a[0] if a else None))
            return real_set(*a, **k)

        with mock.patch("maya.cmds.dgdirty", spy_dg), \
             mock.patch("maya.cmds.setAttr", spy_set):
            fn()
        return [h for h in hits
                if isinstance(h[1], str) and h[1].split(".")[0] == node]

    def test_dispatch_skips_a_suspended_destination(self):
        from mpynode._common.plugs import auto_dirty

        plane = mc.polySphere(sx=6, sy=6)[0]
        node  = mc.deformer(plane, type="mPyDeformer")[0]
        live  = self._calls_on(node, lambda: auto_dirty._dispatch_dirty_now(node))
        self.assertTrue(any(k == "dgdirty" for k, _ in live), live)
        self.assertTrue(any(k == "setAttr" for k, _ in live),
                        "a live deformer gets its envelope touched")
        mc.setAttr(node + ".nodeState", 1)                  # Has No Effect
        self.assertEqual(
            self._calls_on(node, lambda: auto_dirty._dispatch_dirty_now(node)), [],
            "a suspended destination is neither dirtied nor touched")
        mc.setAttr(node + ".nodeState", 0)
        self.assertTrue(
            self._calls_on(node, lambda: auto_dirty._dispatch_dirty_now(node)),
            "un-suspending resumes the dispatch")

    def test_a_source_dirty_after_the_destination_is_deleted_is_ignored(self):
        from mpynode._common.plugs import auto_dirty
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polySphere(sx=6, sy=6)[0]
        w     = MPyDeformer.create_on(plane, name="goneProbe")
        w.add_input_attr("amount", "float")
        loc = mc.spaceLocator(name="goneDriver")[0]
        mc.connectAttr(loc + ".translateX", "goneProbe.amount")
        dispatched = []
        real       = auto_dirty._dispatch_dirty_now

        def spy(name):
            dispatched.append(name)
            return real(name)

        with mock.patch.object(auto_dirty, "_dispatch_dirty_now", spy):
            mc.setAttr(loc + ".translateX", 1.0)
        self.assertIn("goneProbe", dispatched,
                      "the source callback is installed and dispatches while live")
        undo_was = mc.undoInfo(q=True, state=True)
        mc.undoInfo(state=False)
        try:
            mc.delete("goneProbe")                    # gone for real: no undo record
            dispatched.clear()
            with mock.patch.object(auto_dirty, "_dispatch_dirty_now", spy):
                mc.setAttr(loc + ".translateX", 2.0)  # used to crash mayapy here
        finally:
            mc.undoInfo(state=undo_was)
        self.assertEqual(dispatched, [])


class TestApi2SuspendedNodesDoNotRunTheirExpression(unittest.TestCase):
    """Convert to C++ suspends the Python node (``nodeState`` Blocking) and
    moves its outputs, but under the Evaluation Manager a USER OUTPUT that an
    animated input dirties is evaluated whether or not anything reads it. Mesh
    Maze's int ``solutionSteps`` kept its converted Python node running the
    whole expression every frame until BOTH animated inputs were unplugged,
    while Voxelize -- no user output -- idled at once (2026-09-14). The api2
    gate closes that for every maya.api family: a suspended node forwards no
    dirtiness and its ``compute()`` returns before the expression, and lifting
    the suspension resumes at once."""

    _FAMILIES = (
        ("mpynode.wrappers._mpy_node", "MPyNode"),
        ("mpynode.wrappers.mpy_mesh", "MPyMesh"),
    )
    _EXPR = chr(10).join((
        "import builtins as _b",
        "_b._mpyTestRuns = getattr(_b, '_mpyTestRuns', 0) + 1",
        "self.n = int(self.k) + 1",
    ))

    def setUp(self):
        mc.file(new=True, force=True)
        self._mode = (mc.evaluationManager(q=True, mode=True) or ["off"])[0]
        mc.evaluationManager(mode="parallel")

    def tearDown(self):
        mc.evaluationManager(
            mode=self._mode if self._mode in ("off", "serial", "parallel") else "off")

    @staticmethod
    def _runs():
        import builtins
        return getattr(builtins, "_mpyTestRuns", 0)

    def _build(self, module, cls_name, name):
        import importlib
        w = getattr(importlib.import_module(module), cls_name).create(name=name)
        w.add_input_attr("k", "int")
        w.add_output_attr("n", "int")
        w.set_compute_expression(self._EXPR)
        node = w.get_name()
        mc.setKeyframe(node + ".k", t=1, v=0)
        mc.setKeyframe(node + ".k", t=10, v=9)
        return node

    def _step(self, lo, hi):
        for t in range(lo, hi + 1):
            mc.currentTime(t, update=True)

    def test_a_suspended_node_stops_running_and_resumes_when_lifted(self):
        for module, cls_name in self._FAMILIES:
            with self.subTest(family=cls_name):
                mc.file(new=True, force=True)
                node   = self._build(module, cls_name, "susp" + cls_name)
                before = self._runs()
                self._step(1, 5)
                self.assertGreater(self._runs(), before,
                                   "%s: the live node must run its expression" % cls_name)
                self.assertEqual(mc.getAttr(node + ".n"), 5)

                mc.setAttr(node + ".nodeState", 2)           # Blocking, as the convert sets
                mid = self._runs()
                self._step(6, 10)
                self.assertEqual(self._runs(), mid,
                                 "%s: a suspended node must not run its expression "
                                 "under the Evaluation Manager" % cls_name)
                self.assertEqual(mc.getAttr(node + ".n"), 5,
                                 "%s: a suspended node leaves its output as it was" % cls_name)

                mc.setAttr(node + ".nodeState", 0)
                self._step(1, 10)
                self.assertGreater(self._runs(), mid,
                                   "%s: lifting the suspension resumes evaluation" % cls_name)
                self.assertEqual(mc.getAttr(node + ".n"), 10)

    def test_the_gate_caches_and_drops_on_the_nodestate_plug(self):
        import maya.api.OpenMaya as om
        from mpynode._common.plugs import dirty_affects

        node = self._build(*self._FAMILIES[1], name="gateProbe")
        sel  = om.MSelectionList()
        sel.add(node)
        mobj = sel.getDependNode(0)

        class _Node(object):
            def thisMObject(self):
                return mobj

        class _Plug(object):
            def __init__(self, name):
                self._n = name

            def partialName(self, useLongNames=False):
                return self._n

        n = _Node()
        self.assertFalse(dirty_affects.api2_dirty_gate(n, _Plug("k")))
        mc.setAttr(node + ".nodeState", 2)
        # Cached: the hot path reads no plug until nodeState passes through.
        self.assertFalse(dirty_affects.api2_dirty_gate(n, _Plug("k")))
        self.assertFalse(dirty_affects.api2_dirty_gate(n, _Plug("nodeState")))
        self.assertTrue(dirty_affects.api2_dirty_gate(n, _Plug("k")))
        mc.setAttr(node + ".nodeState", 0)
        dirty_affects.api2_dirty_gate(n, _Plug("nodeState"))
        self.assertFalse(dirty_affects.api2_dirty_gate(n, _Plug("k")))
        self.assertTrue(dirty_affects.api2_node_suspended(mobj) is False)


if __name__ == "__main__":
    unittest.main()
