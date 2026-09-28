"""One connection callback for the whole module, not one per node type.

Maya cannot filter a connection callback. ``addNodeAddedCallback`` takes a type
name and is filtered in C++, but EVERY connection made anywhere in the scene
enters EVERY registered connection callback. ``auto_dirty`` registered one per
covered type, and each asked ``cmds.nodeType(fn.name())`` -- the slowest way to
ask -- before discovering the destination was not one of ours.

MEASURED on Windows 2026-09-28, 5,000 ``connectAttr`` between stock
multiplyDivide nodes, 9 types covered:

    baseline                        40.6 us
    + ONE no-op python callback     56.7 us   (the irreducible dispatch floor)
    + MPyNode, one per type        478.0 us   <- before
    + MPyNode, shared dispatch      63.2 us   <- after

Every tool in the session paid that, not just MPyNode: the ``rig`` DSL's
rail_spine example built in 3.9 s with the plug-ins loaded and 2.1 s without.

So these tests guard the two properties that made it fast, and the four that
keep it correct across plug-in load, unload and reload.
"""

from __future__ import annotations

import unittest
from unittest import mock

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestExactlyOneCallbackServesEveryType(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import auto_dirty

        self.ad = auto_dirty

    def test_one_shared_callback_is_registered(self):
        self.assertIsNotNone(self.ad._shared_connection_cb)

    def test_every_covered_type_dispatches_through_it(self):
        """The registry carries a row per covered type; the CALLBACK count
        stays at one. That ratio is the whole optimisation."""
        covered = set(self.ad._connection_callbacks_installed)
        self.assertGreaterEqual(len(covered), 5, "expected the api2 types at least")
        rows = {e["type_name"] for e in self.ad._connection_types.values()}
        rows |= set(self.ad._pending_connection_types)
        self.assertEqual(rows, covered)

    def test_registering_another_type_adds_no_callback(self):
        cb_before = self.ad._shared_connection_cb
        self.ad._register_connection_type("multiplyDivide", "user", "test-owner")
        self.addCleanup(self.ad._forget_connection_types, "test-owner")
        self.assertIs(self.ad._shared_connection_cb, cb_before)

    def test_the_registry_is_keyed_by_type_id(self):
        """Not by name: asking a node its name to compare strings is what cost
        8.9 us per callback."""
        import maya.OpenMaya as om

        want = om.MNodeClass("mPyLocator").typeId().id()
        self.assertIn(want, self.ad._connection_types)
        self.assertEqual(self.ad._connection_types[want]["type_name"], "mPyLocator")


class TestStrangersAreRejectedWithoutWork(unittest.TestCase):
    """The common case by far: a connection between two nodes that are not
    ours. It must not reach either handler."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import auto_dirty

        self.ad = auto_dirty

    def test_a_stock_to_stock_connection_reaches_no_handler(self):
        a = mc.createNode("multiplyDivide")
        b = mc.createNode("multiplyDivide")
        with mock.patch.object(self.ad, "_on_user_input_connection") as user, \
             mock.patch.object(self.ad, "_on_native_geo_connection") as native:
            mc.connectAttr(a + ".outputX", b + ".input1X", force=True)
        self.assertEqual(user.call_count, 0)
        self.assertEqual(native.call_count, 0)

    def test_a_broken_connection_does_no_work_either(self):
        a = mc.createNode("multiplyDivide")
        b = mc.createNode("multiplyDivide")
        mc.connectAttr(a + ".outputX", b + ".input1X", force=True)
        with mock.patch.object(self.ad, "_on_user_input_connection") as user:
            mc.disconnectAttr(a + ".outputX", b + ".input1X")
        self.assertEqual(user.call_count, 0)


class TestOurOwnNodesStillGetCovered(unittest.TestCase):
    """The behaviour the callback exists for, unchanged by the refactor: a
    connection into a USER input installs the source-side dirty callback."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import auto_dirty

        self.ad = auto_dirty

    def _locator_with_input(self, name, attr="amount"):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name=name)
        loc.add_input_attr(attr, "float")
        return loc

    def test_a_connection_into_a_user_input_is_dispatched(self):
        w   = self._locator_with_input("covProbe")
        src = mc.spaceLocator(name="covDriver")[0]
        with mock.patch.object(self.ad, "_on_user_input_connection") as user:
            mc.connectAttr(src + ".translateX", w.get_name() + ".amount")
        self.assertEqual(user.call_count, 1)

    def test_it_installs_a_source_side_callback(self):
        w   = self._locator_with_input("srcProbe")
        src = mc.spaceLocator(name="srcDriver")[0]
        before = len(self.ad._source_callbacks)
        mc.connectAttr(src + ".translateX", w.get_name() + ".amount")
        self.assertGreater(len(self.ad._source_callbacks), before,
                           "no source-side dirty callback was installed")

    def test_a_connection_to_a_non_user_attr_installs_nothing(self):
        """Dispatch reaching our node is not enough -- the ``_inputAttrs``
        filter still has to reject a connection into a BUILT-IN plug, which
        ``localScaleX`` is and ``amount`` is not."""
        w   = self._locator_with_input("filtProbe")
        src = mc.spaceLocator(name="filtDriver")[0]
        before = len(self.ad._source_callbacks)
        with mock.patch.object(
            self.ad, "_on_user_input_connection",
            side_effect=self.ad._on_user_input_connection
        ) as user:
            mc.connectAttr(src + ".translateX", w.get_name() + ".localScaleX")
        self.assertEqual(user.call_count, 1, "dispatch should reach our node")
        self.assertEqual(len(self.ad._source_callbacks), before,
                         "a built-in plug is not a user input")


class TestOwnershipAcrossUnloadAndReload(unittest.TestCase):
    """``forget_owner`` runs on EVERY single-plug-in unload. It must drop that
    plug-in's types without taking the shared callback the sibling still needs.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import auto_dirty

        self.ad = auto_dirty

    def test_forget_owner_drops_only_that_owners_rows(self):
        self.ad._register_connection_type("multiplyDivide", "user", "ownerA")
        self.ad._register_connection_type("condition", "user", "ownerB")
        self.addCleanup(self.ad._forget_connection_types, "ownerB")

        self.ad._forget_connection_types("ownerA")
        names = {e["type_name"] for e in self.ad._connection_types.values()}
        self.assertNotIn("multiplyDivide", names)
        self.assertIn("condition", names)

    def test_the_shared_callback_survives_one_owner_leaving(self):
        """If it did not, unloading api1 would silently stop api2 covering
        anything -- the sibling-unload bug the old per-type latch guarded."""
        cb = self.ad._shared_connection_cb
        self.ad._register_connection_type("multiplyDivide", "user", "ownerC")
        self.ad._forget_connection_types("ownerC")
        self.assertIs(self.ad._shared_connection_cb, cb)
        self.assertIsNotNone(self.ad._shared_connection_cb)

    def test_the_real_plugin_types_survive_a_foreign_forget(self):
        self.ad._forget_connection_types("not-a-real-owner")
        names = {e["type_name"] for e in self.ad._connection_types.values()}
        self.assertIn("mPyLocator", names)


class TestATypeIdThatIsNotResolvableYet(unittest.TestCase):
    """``install_for_type`` runs on evalDeferred and compiled types register
    later, so a name can arrive before Maya knows it. ``MNodeClass`` answers 0
    for an unknown type rather than raising, so 0 must read as "not yet"."""

    def setUp(self):
        from mpynode._common.plugs import auto_dirty

        self.ad = auto_dirty

    def test_an_unknown_type_id_is_none_not_zero(self):
        self.assertIsNone(self.ad._type_id("noSuchNodeTypeXyz"))

    def test_an_unresolvable_name_waits_in_pending(self):
        self.ad._register_connection_type("noSuchNodeTypeXyz", "user", "ownerP")
        self.addCleanup(self.ad._forget_connection_types, "ownerP")
        self.assertIn("noSuchNodeTypeXyz", self.ad._pending_connection_types)

    def test_it_is_folded_in_once_the_id_resolves(self):
        self.ad._pending_connection_types["multiplyDivide"] = ("user", "ownerQ")
        self.addCleanup(self.ad._forget_connection_types, "ownerQ")
        self.ad._resolve_pending_connection_types()
        self.assertNotIn("multiplyDivide", self.ad._pending_connection_types)
        names = {e["type_name"] for e in self.ad._connection_types.values()}
        self.assertIn("multiplyDivide", names)

    def test_a_still_unresolvable_name_stays_put(self):
        self.ad._register_connection_type("noSuchNodeTypeXyz", "user", "ownerR")
        self.addCleanup(self.ad._forget_connection_types, "ownerR")
        self.ad._resolve_pending_connection_types()
        self.assertIn("noSuchNodeTypeXyz", self.ad._pending_connection_types)


if __name__ == "__main__":
    unittest.main()
