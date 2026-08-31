"""Phase B: drag-to-reorder user attributes (plug-level).

Reordering is DESTRUCTIVE -- it physically deletes and re-adds the Maya dynamic
attrs so the Channel Box / Node Editor order follows -- but it must preserve
every connection and unconnected value, all inside ONE undo chunk (single
Ctrl+Z reverts it), and it is refused while the timeline is playing.

These tests pin the wrapper engine (``reorder_input_attrs`` /
``reorder_output_attrs``) and the undoable ``_ReorderAttrCommand`` headless.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QApplication must exist BEFORE standalone.initialize for the widget tests.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-reorder-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _qt_available() -> bool:
    return _QAPP is not None


def _node(name="reordNode#"):
    from mpynode.wrappers._mpy_node import MPyNode

    n = MPyNode.create(name=name)
    for nm in ("alpha", "beta", "gamma", "delta"):
        n.add_input_attr(nm, "float")
    return n


def _user_attr_order(node_name):
    """The Channel Box / DG creation order of user attrs (parents only)."""
    attrs = mc.listAttr(node_name, userDefined=True) or []
    # keep only our four (skip any compound children / built-ins).
    return [a for a in attrs if a in ("alpha", "beta", "gamma", "delta")]


class TestWrapperReorder(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_reorder_moves_plugs_in_channel_box(self):
        n = _node()
        new = ["delta", "alpha", "gamma", "beta"]
        n.reorder_input_attrs(new)
        # Both the JSON map order AND Maya's true creation order follow.
        self.assertEqual(list(n.get_input_attr_map().keys()), new)
        self.assertEqual(_user_attr_order(n.get_name()), new)

    def test_reorder_preserves_incoming_connection(self):
        n = _node()
        name = n.get_name()
        drv = mc.createNode("transform", name="drv#")
        mc.connectAttr(drv + ".translateX", name + ".gamma")
        n.reorder_input_attrs(["gamma", "delta", "alpha", "beta"])
        srcs = mc.listConnections(name + ".gamma", source=True, destination=False,
                                  plugs=True) or []
        self.assertEqual(srcs, [drv + ".translateX"])

    def test_reorder_preserves_compound_child_connection(self):
        # a vector input wired at the CHILD level (vecX <- translateX) must
        # survive the rebuild; a parent-only snapshot would drop it.
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="vecReord#")
        n.add_input_attr("a", "float")
        n.add_input_attr("vec", "vector")
        n.add_input_attr("z", "float")
        name = n.get_name()
        drv = mc.createNode("transform", name="vdrv#")
        mc.connectAttr(drv + ".translateX", name + ".vecX")
        n.reorder_input_attrs(["vec", "z", "a"])
        self.assertEqual(list(n.get_input_attr_map().keys()), ["vec", "z", "a"])
        srcs = mc.listConnections(name + ".vecX", source=True, destination=False,
                                  plugs=True) or []
        self.assertEqual(srcs, [drv + ".translateX"])

    def test_reorder_preserves_unconnected_value(self):
        n = _node()
        name = n.get_name()
        mc.setAttr(name + ".beta", 7.5)
        n.reorder_input_attrs(["beta", "alpha", "gamma", "delta"])
        self.assertAlmostEqual(mc.getAttr(name + ".beta"), 7.5, places=4)

    def test_reorder_preserves_outgoing_connection(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="outReord#")
        for nm in ("outA", "outB", "outC"):
            n.add_output_attr(nm, "float")
        name = n.get_name()
        sink = mc.createNode("transform", name="sink#")
        mc.connectAttr(name + ".outB", sink + ".translateY")
        n.reorder_output_attrs(["outC", "outB", "outA"])
        self.assertEqual(list(n.get_output_attr_map().keys()),
                         ["outC", "outB", "outA"])
        dsts = mc.listConnections(name + ".outB", source=False, destination=True,
                                  plugs=True) or []
        self.assertEqual(dsts, [sink + ".translateY"])

    def test_reorder_rejects_non_permutation(self):
        n = _node()
        with self.assertRaises(ValueError):
            n.reorder_input_attrs(["alpha", "beta"])          # missing some
        with self.assertRaises(ValueError):
            n.reorder_input_attrs(["alpha", "beta", "gamma", "zzz"])  # unknown

    def test_reorder_noop_when_order_unchanged(self):
        n = _node()
        n.reorder_input_attrs(["alpha", "beta", "gamma", "delta"])
        self.assertEqual(list(n.get_input_attr_map().keys()),
                         ["alpha", "beta", "gamma", "delta"])


class TestReorderSuppressesTransientEval(unittest.TestCase):
    """Root cause of the quatSpring.ma reorder error: the destructive rebuild
    momentarily DELETES every user attr and writes an EMPTY schema map, so when
    the GUI Evaluation Manager / viewport eager-pulls a still-live output mid-
    edit, the user expression raises 'self has no plug named X'. The consumer
    (_api2/_mpy_node.compute) suppresses that benign transient only when the
    missing name is still in the (now-empty) schema map OR
    scene_io.should_defer_transient() is True. With the map empty, ONLY
    should_defer_transient() can save it.

    The GUI EM eager-pull cannot be reproduced in headless DG mode (getAttr on
    an output returns the clean default WITHOUT re-running the expression -- see
    investigation), so we test the precise, reproducible contract that fixes the
    bug: throughout the delete window the schema map is empty (vulnerable) AND
    should_defer_transient() is True (protected). That is exactly the predicate
    the consumer's `_spurious` branch evaluates.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode._common.lifecycle import scene_state as scene_io
        scene_io._last_surgery_monotonic = -1.0e9
        scene_io._attr_surgery_depth = 0

    def _build(self):
        from mpynode.wrappers._mpy_node import MPyNode
        n = MPyNode.create(name="transNode#")
        n.add_input_attr("a", "float")
        n.add_input_attr("b", "float")
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = self.a + self.b")
        return n

    def test_transient_deferred_throughout_reorder(self):
        import mpynode.wrappers._mpy_node as W
        from mpynode._common.lifecycle import scene_state as scene_io

        n = self._build()
        name = n.get_name()

        # Sample (schema-map, should_defer?) before every deleteAttr and
        # addAttr, the instants a GUI EM pull could land. The map is empty
        # between write({}) and the first re-add's addAttr, and add_input_attr
        # calls mc.addAttr first, so sampling before orig catches that window.
        samples = []
        orig_del, orig_add = W.mc.deleteAttr, W.mc.addAttr

        def sampling_delete(*a, **k):
            samples.append((dict(n._read_input_map()),
                            scene_io.should_defer_transient()))
            return orig_del(*a, **k)

        def sampling_add(*a, **k):
            samples.append((dict(n._read_input_map()),
                            scene_io.should_defer_transient()))
            return orig_add(*a, **k)

        W.mc.deleteAttr, W.mc.addAttr = sampling_delete, sampling_add
        try:
            n.reorder_input_attrs(["b", "a"])
        finally:
            W.mc.deleteAttr, W.mc.addAttr = orig_del, orig_add

        self.assertTrue(samples, "reorder issued no deleteAttr/addAttr")
        # At least one sample must catch the emptied map, or the test proves
        # nothing.
        empties = [s for s in samples if "a" not in s[0] and "b" not in s[0]]
        self.assertTrue(empties,
                        "expected an empty-schema-map moment during reorder")
        for _m, deferred in samples:
            self.assertTrue(
                deferred,
                "should_defer_transient() was False during the reorder window "
                "-- a mid-edit EM pull would log the benign missing-plug error "
                "(this is the quatSpring.ma bug)")

        # And the reorder still happened + the node recomputes cleanly after,
        # and the surgery window has closed (depth back to zero).
        self.assertEqual(list(n.get_input_attr_map().keys()), ["b", "a"])
        self.assertEqual(scene_io._attr_surgery_depth, 0)
        mc.setAttr(name + ".a", 2.0)
        mc.setAttr(name + ".b", 3.0)
        mc.dgdirty(name + ".out")
        self.assertAlmostEqual(mc.getAttr(name + ".out"), 5.0, places=4)

    def test_consumer_suppresses_missing_plug_when_deferring(self):
        """The consumer predicate: with an EMPTY schema map, a missing-plug
        message is suppressed iff should_defer_transient() is True. Mirrors
        _api2/_mpy_node.compute so a regression in either side is caught."""
        from mpynode._common.lifecycle import scene_state as scene_io

        msg = ("'self' has no plug, init binding, or stored var named "
               "'quatIn'. ...")
        input_map, output_map = {}, {}

        def spurious():
            miss = scene_io.extract_missing_name(msg)
            return scene_io.is_missing_plug_error(msg) and (
                (miss is not None
                 and (miss in input_map or miss in output_map))
                or scene_io.should_defer_transient()
            )

        scene_io._last_surgery_monotonic = -1.0e9
        scene_io._attr_surgery_depth = 0
        self.assertFalse(spurious(), "outside surgery the error must surface")
        scene_io.begin_attr_surgery()
        try:
            self.assertTrue(spurious(), "during surgery the error is deferred")
        finally:
            scene_io.end_attr_surgery()


class TestSceneIoAttrSurgery(unittest.TestCase):
    def setUp(self):
        # Clear any grace window left by an earlier reorder test so the
        # depth assertions are deterministic; it auto-expires in 2s, but
        # sleeping is worse.
        from mpynode._common.lifecycle import scene_state as scene_io
        scene_io._last_surgery_monotonic = -1.0e9
        scene_io._attr_surgery_depth = 0

    def test_surgery_window_defers_transient(self):
        from mpynode._common.lifecycle import scene_state as scene_io
        self.assertFalse(scene_io.in_attr_surgery())
        scene_io.begin_attr_surgery()
        try:
            self.assertTrue(scene_io.in_attr_surgery())
            self.assertTrue(scene_io.should_defer_transient())
        finally:
            scene_io.end_attr_surgery()
        # Re-entrant safe: nested begin/end tracks depth correctly while nested
        # (grace may keep it briefly true after the OUTER close).
        scene_io._last_surgery_monotonic = -1.0e9
        scene_io.begin_attr_surgery()
        scene_io.begin_attr_surgery()
        scene_io.end_attr_surgery()
        self.assertTrue(scene_io.in_attr_surgery())   # one still open (depth=1)
        scene_io.end_attr_surgery()


class TestReorderCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_command_reorders_and_single_undo_restores(self):
        from mpynode._base.commands import _ReorderAttrCommand, run_undoable

        n = _node()
        name = n.get_name()
        drv = mc.createNode("transform", name="drvU#")
        mc.connectAttr(drv + ".translateX", name + ".alpha")
        run_undoable(_ReorderAttrCommand(n, ["delta", "gamma", "beta", "alpha"],
                                         "input"))
        self.assertEqual(_user_attr_order(name),
                         ["delta", "gamma", "beta", "alpha"])
        # ONE undo reverts the whole reorder...
        mc.undo()
        self.assertEqual(_user_attr_order(name),
                         ["alpha", "beta", "gamma", "delta"])
        # ...connections intact after undo.
        srcs = mc.listConnections(name + ".alpha", source=True, destination=False,
                                  plugs=True) or []
        self.assertEqual(srcs, [drv + ".translateX"])

    def test_command_redo_reapplies_new_order(self):
        from mpynode._base.commands import _ReorderAttrCommand, run_undoable

        n = _node()
        name = n.get_name()
        new = ["gamma", "alpha", "delta", "beta"]
        run_undoable(_ReorderAttrCommand(n, new, "input"))
        mc.undo()
        self.assertEqual(_user_attr_order(name),
                         ["alpha", "beta", "gamma", "delta"])
        mc.redo()
        self.assertEqual(_user_attr_order(name), new)

    def test_command_refused_during_playback(self):
        from mpynode._base import commands as cmdmod
        from mpynode._base.commands import _ReorderAttrCommand, run_undoable

        n = _node()
        name = n.get_name()
        orig = cmdmod.cmds.play
        cmdmod.cmds.play = lambda *a, **k: True       # pretend the timeline is playing
        try:
            cmd = _ReorderAttrCommand(n, ["delta", "alpha", "gamma", "beta"],
                                      "input")
            run_undoable(cmd)
        finally:
            cmdmod.cmds.play = orig
        # No reorder happened.
        self.assertEqual(_user_attr_order(name),
                         ["alpha", "beta", "gamma", "delta"])
        self.assertTrue(getattr(cmd, "refused_playback", False))


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestReorderDropSeam(unittest.TestCase):
    """The Attributes-panel drop seam (``_reorder_to``) that the drag wiring
    funnels into -- exercised directly so it needs no synthetic QDropEvent."""

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        self.tree = NDInputAttrTree()
        self.node = _node()
        self.tree.setNode(self.node)

    def tearDown(self):
        try:
            self.tree.deleteLater()
        except Exception:
            pass

    def test_drop_before_target_reorders(self):
        ok = self.tree._reorder_to("delta", "alpha", place_after=False)
        self.assertTrue(ok)
        self.assertEqual(list(self.node.get_input_attr_map().keys()),
                         ["delta", "alpha", "beta", "gamma"])

    def test_drop_after_target_reorders(self):
        ok = self.tree._reorder_to("alpha", "gamma", place_after=True)
        self.assertTrue(ok)
        self.assertEqual(list(self.node.get_input_attr_map().keys()),
                         ["beta", "gamma", "alpha", "delta"])

    def test_drop_none_target_moves_to_end(self):
        ok = self.tree._reorder_to("alpha", None)
        self.assertTrue(ok)
        self.assertEqual(list(self.node.get_input_attr_map().keys()),
                         ["beta", "gamma", "delta", "alpha"])

    def test_seam_refused_during_playback(self):
        import mpynode.ui.widgets.attributes as attrmod
        orig = attrmod._timeline_is_playing
        attrmod._timeline_is_playing = lambda: True
        try:
            ok = self.tree._reorder_to("delta", "alpha", place_after=False)
        finally:
            attrmod._timeline_is_playing = orig
        self.assertFalse(ok)
        self.assertEqual(list(self.node.get_input_attr_map().keys()),
                         ["alpha", "beta", "gamma", "delta"])


class TestReorderWiring(unittest.TestCase):
    """Source-level guards that the drop path actually routes reorder."""

    def test_drop_event_routes_internal_reorder(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        src = inspect.getsource(NDInputAttrTree.dropEvent)
        self.assertIn("_is_internal_reorder", src)
        self.assertIn("_handle_reorder_drop", src)

    def test_output_tree_inherits_reorder(self):
        from mpynode.ui.widgets.attributes import NDOutputAttrTree
        self.assertTrue(hasattr(NDOutputAttrTree, "_reorder_to"))
        self.assertEqual(NDOutputAttrTree.ATTR_CATEGORY, "output")


if __name__ == "__main__":
    unittest.main()
