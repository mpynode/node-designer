"""RefreshHub event bus + per-plug filter

Consolidated from: test_phaseN_0_refresh_hub.py, test_phaseO_2_refresh_hub_filter.py.
"""

from __future__ import annotations

# ===================== from test_phaseN_0_refresh_hub.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-phaseN-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseN_0_refresh_hub():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestRefreshHubBasic(unittest.TestCase):
    """Hub lifecycle + subscribe/unsubscribe + manual fire path."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyNode", name="hub_test")

    def test_make_hub_attaches(self):
        from mpynode.ui.widgets.refresh_hub import make_hub

        hub = make_hub(self.node)
        self.assertIsNotNone(hub)
        self.assertTrue(hub.is_attached())
        self.assertEqual(hub.node_name(), self.node)
        hub.detach()

    def test_make_hub_returns_none_for_missing_node(self):
        from mpynode.ui.widgets.refresh_hub import make_hub

        self.assertIsNone(make_hub("nosuch_xyz"))

    def test_subscribe_unsubscribe(self):
        from mpynode.ui.widgets.refresh_hub import make_hub

        hub   = make_hub(self.node)
        calls = []
        hub.subscribe("v1", lambda ev: calls.append(("v1", ev)))
        self.assertTrue(hub.has_subscriber("v1"))
        self.assertEqual(hub.subscriber_count(), 1)
        hub.unsubscribe("v1")
        self.assertFalse(hub.has_subscriber("v1"))
        hub.detach()

    def test_fire_dispatches_to_subscribers(self):
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_ADDED_OR_REMOVED,
        )

        hub   = make_hub(self.node)
        calls = []
        hub.subscribe("v1", lambda ev: calls.append(ev))
        hub.fire(EVENT_ATTR_ADDED_OR_REMOVED)
        # Headless: flush manually (Qt timer may not be running).
        hub._dispatch_pending()
        self.assertEqual(calls, [EVENT_ATTR_ADDED_OR_REMOVED])
        hub.detach()

    def test_debounce_collapses_burst(self):
        """Multiple fire() calls of the same event before dispatch
        collapse into a single callback invocation."""
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_ADDED_OR_REMOVED,
        )

        hub   = make_hub(self.node)
        calls = []
        hub.subscribe("v1", lambda ev: calls.append(ev))
        for _ in range(5):
            hub.fire(EVENT_ATTR_ADDED_OR_REMOVED)
        hub._dispatch_pending()
        self.assertEqual(len(calls), 1,
            "burst of 5 identical fires should debounce to 1 callback")
        hub.detach()

    def test_event_mask_filters_subscribers(self):
        """A subscriber that only registers for ATTR_SET shouldn't
        see NAME_CHANGED fires."""
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_SET, EVENT_NAME_CHANGED,
        )

        hub        = make_hub(self.node)
        attr_calls = []
        name_calls = []
        hub.subscribe("attr_only", lambda ev: attr_calls.append(ev),
                      events=(EVENT_ATTR_SET,))
        hub.subscribe("name_only", lambda ev: name_calls.append(ev),
                      events=(EVENT_NAME_CHANGED,))
        hub.fire(EVENT_ATTR_SET)
        hub.fire(EVENT_NAME_CHANGED)
        hub._dispatch_pending()
        self.assertEqual(attr_calls, [EVENT_ATTR_SET])
        self.assertEqual(name_calls, [EVENT_NAME_CHANGED])
        hub.detach()

    def test_detach_idempotent(self):
        from mpynode.ui.widgets.refresh_hub import make_hub

        hub = make_hub(self.node)
        hub.detach()
        hub.detach()  # second call must be safe
        self.assertFalse(hub.is_attached())


class TestRefreshHubMayaCallbacks(unittest.TestCase):
    """Live MNodeMessage path: register a subscriber, perform a
    Maya operation (addAttr / rename), assert the hub fired."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyNode", name="hub_live")

    def test_addAttr_fires_attribute_added(self):
        """Cmds.addAttr on the bound node should trigger the
        addAttributeAddedOrRemoved callback, which fires the hub's
        ATTR_ADDED_OR_REMOVED event."""
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_ADDED_OR_REMOVED,
        )

        hub    = make_hub(self.node)
        events = []
        hub.subscribe("v1", lambda ev: events.append(ev))
        # Trigger
        mc.addAttr(self.node, longName="liveAttr", attributeType="float")
        # MNodeMessage callbacks fire on the main thread; in mayapy
        # there's no Qt event loop running so we drain the pending
        # queue manually.
        hub._dispatch_pending()
        self.assertIn(EVENT_ATTR_ADDED_OR_REMOVED, events,
            f"addAttr did not propagate; events={events}")
        hub.detach()

    def test_about_to_delete_fires_and_detaches(self):
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_NODE_ABOUT_TO_DELETE,
        )

        hub    = make_hub(self.node)
        events = []
        hub.subscribe("v1", lambda ev: events.append(ev))
        # Delete the node
        mc.delete(self.node)
        hub._dispatch_pending()
        # The hub should have auto-detached after firing.
        self.assertFalse(hub.is_attached(),
            "hub should detach after node_about_to_delete fires")


class TestEditorRefreshHubAttach(unittest.TestCase):
    """NDScriptEditor / NDInitEditor / NDInputAttrTree accept an
    attachRefreshHub(hub) and propagate fired events through their
    refresh callbacks."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest(
                "Qt unavailable in this mayapy build; widget tests skipped"
            )

    def setUp(self):
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="ed_n0")

    def test_script_editor_refreshes_vocabulary_on_hub_fire(self):
        from mpynode.ui.widgets.script_editor import NDScriptEditor
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_ADDED_OR_REMOVED,
        )

        ed  = NDScriptEditor(self.deformer)
        hub = make_hub(self.deformer.get_name())
        ed.attachRefreshHub(hub)
        before = set(ed.getCompletionWords())
        # Add a new attr; live MNodeMessage fires the hub.
        self.deformer.add_input_attr("brandNewAttr", "float")
        hub._dispatch_pending()
        after = set(ed.getCompletionWords())
        self.assertIn("self.brandNewAttr", after,
            "editor completion vocab should pick up the new attr "
            "after the hub fired")
        self.assertNotIn("self.brandNewAttr", before)
        hub.detach()

    def test_attribute_tree_refreshes_on_hub_fire(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        from mpynode.ui.widgets.refresh_hub import make_hub

        tree = NDInputAttrTree()
        tree.setNode(self.deformer)
        hub = make_hub(self.deformer.get_name())
        tree.attachRefreshHub(hub)
        # Count user-added items before.
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem
        before_user = sum(
            1
            for i in range(tree.topLevelItemCount())
            if isinstance(tree.topLevelItem(i), NDUserAttrTreeItem)
        )
        self.deformer.add_input_attr("freshAttr", "float")
        hub._dispatch_pending()
        after_user = sum(
            1
            for i in range(tree.topLevelItemCount())
            if isinstance(tree.topLevelItem(i), NDUserAttrTreeItem)
        )
        self.assertEqual(after_user, before_user + 1,
            "attribute tree should grow by 1 user-added row")
        hub.detach()


# ===================== from test_phaseO_2_refresh_hub_filter.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseO_2_refresh_hub_filter():
    standalone_init()


class TestRefreshHubPlugFilter(unittest.TestCase):
    """Manual fire_plug_set + filtered dispatch."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyNode", name="o2_node")

    def test_unfiltered_subscriber_still_fires(self):
        """Backward compat: subscribers that don't pass plug_filter
        get ATTR_SET for any plug change."""
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_SET,
        )

        hub    = make_hub(self.node)
        events = []
        hub.subscribe("v1", lambda ev: events.append(ev),
                      events=(EVENT_ATTR_SET,))
        hub.fire_plug_set("envelope")
        hub._dispatch_pending()
        self.assertEqual(events, [EVENT_ATTR_SET])
        hub.detach()

    def test_filtered_subscriber_skips_unrelated(self):
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_SET,
        )

        hub    = make_hub(self.node)
        events = []
        hub.subscribe(
            "v1",
            lambda ev: events.append(ev),
            events      = (EVENT_ATTR_SET,),
            plug_filter = ("driverMatrixA", "amplitude"),
        )
        hub.fire_plug_set("envelope")  # not in filter
        hub._dispatch_pending()
        self.assertEqual(events, [],
            "ATTR_SET on 'envelope' must NOT fire filtered subscriber")
        hub.detach()

    def test_filtered_subscriber_fires_on_match(self):
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_SET,
        )

        hub    = make_hub(self.node)
        events = []
        hub.subscribe(
            "v1",
            lambda ev: events.append(ev),
            events      = (EVENT_ATTR_SET,),
            plug_filter = ("driverMatrixA",),
        )
        hub.fire_plug_set("driverMatrixA")
        hub._dispatch_pending()
        self.assertEqual(events, [EVENT_ATTR_SET])
        hub.detach()

    def test_mixed_burst_filtered_correctly(self):
        """A burst of fire_plug_set('A') + fire_plug_set('B') should
        fire a subscriber filtered for {'B'} exactly once."""
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_SET,
        )

        hub    = make_hub(self.node)
        events = []
        hub.subscribe(
            "v1",
            lambda ev: events.append(ev),
            events      = (EVENT_ATTR_SET,),
            plug_filter = ("amplitude",),
        )
        hub.fire_plug_set("envelope")
        hub.fire_plug_set("amplitude")
        hub.fire_plug_set("envelope")
        hub._dispatch_pending()
        self.assertEqual(events, [EVENT_ATTR_SET],
            "filter matches 'amplitude' in the burst -> 1 fire")
        hub.detach()

    def test_plain_fire_still_works(self):
        """Fire(EVENT_ATTR_SET) without a plug name acts like
        pre-O.2 (no plug name -> all unfiltered subscribers fire;
        filtered subscribers don't see it)."""
        from mpynode.ui.widgets.refresh_hub import (
            make_hub, EVENT_ATTR_SET,
        )

        hub               = make_hub(self.node)
        unfiltered_events = []
        filtered_events   = []
        hub.subscribe(
            "uf", lambda ev: unfiltered_events.append(ev),
            events=(EVENT_ATTR_SET,),
        )
        hub.subscribe(
            "f", lambda ev: filtered_events.append(ev),
            events      = (EVENT_ATTR_SET,),
            plug_filter = ("X",),
        )
        hub.fire(EVENT_ATTR_SET)
        hub._dispatch_pending()
        self.assertEqual(unfiltered_events, [EVENT_ATTR_SET])
        self.assertEqual(filtered_events, [])
        hub.detach()


class TestRefreshHubFilterSourceShape(unittest.TestCase):
    """Source-grep pins."""

    def test_subscribe_has_plug_filter_kwarg(self):
        import inspect
        from mpynode.ui.widgets.refresh_hub import RefreshHub

        sig = inspect.signature(RefreshHub.subscribe)
        self.assertIn("plug_filter", sig.parameters)

    def test_fire_plug_set_exists(self):
        from mpynode.ui.widgets.refresh_hub import RefreshHub

        self.assertTrue(hasattr(RefreshHub, "fire_plug_set"))


def setUpModule():
    _setUpModule__phaseN_0_refresh_hub()
    _setUpModule__phaseO_2_refresh_hub_filter()


if __name__ == "__main__":
    import unittest
    unittest.main()
