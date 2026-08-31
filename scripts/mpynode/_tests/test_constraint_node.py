"""MPyConstraint node: api1 MObject cache + rename hook

Consolidated from: test_phaseN_4_constraint_mobject_cache.py, test_phaseO_6_constraint_rename_hook.py.
"""

from __future__ import annotations

# ===================== from test_phaseN_4_constraint_mobject_cache.py =====================
import unittest

import maya.cmds as mc

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseN_4_constraint_mobject_cache():
    standalone_init()


class TestApi1MObjectHelperCorrectness(unittest.TestCase):
    """The _api1_mobject helper resolves correctly, caches the
    result, and re-resolves on stale-name input."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        self.node = mc.createNode("transform", name="cache_test_node")

    def _make_helper_instance(self):
        """Build a thin object that has the _api1_mobject method.
        We can't instantiate MPxNode subclasses from Python directly
        (they're Maya-instantiated), so we synthesize a host that
        re-uses the method via __get__."""
        from mpynode._api2.mpy_constraint import MPyConstraint

        class Host:
            _cached_api1_mobject = None
            _cached_api1_name = None
            _cached_api1_rename_token = None
            _api1_mobject = MPyConstraint._api1_mobject

        return Host()

    def test_helper_resolves_to_non_null_mobject(self):
        h = self._make_helper_instance()
        mob = h._api1_mobject(self.node)
        self.assertIsNotNone(mob)
        self.assertFalse(mob.isNull(),
            "first call should resolve to non-null api1 MObject")

    def test_second_call_reuses_cached(self):
        """The cache should hand back the same MObject reference on
        repeat calls with the same name."""
        h = self._make_helper_instance()
        first = h._api1_mobject(self.node)
        second = h._api1_mobject(self.node)
        # Same wrapper instance.
        self.assertIs(first, second,
            "second call with same name should return CACHED instance")

    def test_name_change_invalidates_cache(self):
        h = self._make_helper_instance()
        first = h._api1_mobject(self.node)
        # Simulate rename by passing a different name.
        other = mc.createNode("transform", name="cache_test_other")
        second = h._api1_mobject(other)
        self.assertIsNot(first, second,
            "rename should force a re-resolve, not return cached")

    def test_missing_node_returns_none(self):
        h = self._make_helper_instance()
        self.assertIsNone(h._api1_mobject("nosuch_xyz"))


class TestConstraintMObjectCacheSourceShape(unittest.TestCase):
    """Source-grep: confirm the N.4 cache helper exists and the
    compute path goes through it instead of re-resolving inline."""

    def test_api1_mobject_helper_exists(self):
        from mpynode._api2.mpy_constraint import MPyConstraint

        self.assertTrue(hasattr(MPyConstraint, "_api1_mobject"))

    def test_compute_uses_api1_mobject_helper(self):
        import inspect
        from mpynode._api2.mpy_constraint import MPyConstraint

        src = inspect.getsource(MPyConstraint.compute)
        self.assertIn("_api1_mobject", src,
            "compute() should route through _api1_mobject cache "
            "instead of re-resolving via MSelectionList every tick")
        # And the inline MSelectionList resolve should be gone.
        self.assertNotIn("MSelectionList()", src,
            "compute() should NOT contain an inline "
            "MSelectionList().add(name) resolve -- that path is "
            "now in the cached _api1_mobject helper.")

    def test_cache_helper_handles_null_and_stale(self):
        import inspect
        from mpynode._api2.mpy_constraint import MPyConstraint

        src = inspect.getsource(MPyConstraint._api1_mobject)
        self.assertIn("isNull", src)
        self.assertIn("_cached_api1_name", src)


# ===================== from test_phaseO_6_constraint_rename_hook.py =====================
import unittest

import maya.cmds as mc

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseO_6_constraint_rename_hook():
    standalone_init()


class TestCacheRenameHook(unittest.TestCase):
    """The cache helper registers a rename callback at first
    resolve. Renaming the node updates _cached_api1_name without
    requiring another compute() to re-resolve."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        self.node = mc.createNode("transform", name="o6_node")

    def _make_helper_instance(self):
        from mpynode._api2.mpy_constraint import MPyConstraint

        class Host:
            _cached_api1_mobject = None
            _cached_api1_name = None
            _cached_api1_rename_token = None
            _api1_mobject = MPyConstraint._api1_mobject

        return Host()

    def test_first_resolve_registers_callback(self):
        h = self._make_helper_instance()
        mob = h._api1_mobject(self.node)
        self.assertIsNotNone(mob)
        # Hook token should be set (best-effort -- may be None if
        # MNodeMessage subscription failed, but on Maya 2026 it
        # always works).
        self.assertIsNotNone(h._cached_api1_rename_token,
            "first resolve should register rename callback")

    def test_rename_updates_cached_name_proactively(self):
        h = self._make_helper_instance()
        h._api1_mobject(self.node)
        self.assertEqual(h._cached_api1_name, "o6_node")
        # Rename via cmds. Maya fires the addNameChangedCallback
        # synchronously in standalone.
        mc.rename(self.node, "o6_renamed")
        self.assertEqual(
            h._cached_api1_name, "o6_renamed",
            "rename callback should refresh _cached_api1_name "
            "PROACTIVELY (before next compute)",
        )

    def test_mobject_pointer_stable_across_rename(self):
        """Maya keeps MObject pointers stable across rename -- only
        the name field needs refreshing."""
        h = self._make_helper_instance()
        first_mob = h._api1_mobject(self.node)
        mc.rename(self.node, "o6_stable")
        # Calling helper again with the new name should hit the cache
        # (name was proactively updated) and return the SAME MObject.
        second_mob = h._api1_mobject("o6_stable")
        self.assertIs(first_mob, second_mob,
            "MObject pointer should stay stable across rename")


class TestCacheRenameHookSourceShape(unittest.TestCase):
    """Source-grep pins."""

    def test_helper_registers_rename_callback(self):
        import inspect
        from mpynode._api2.mpy_constraint import MPyConstraint

        src = inspect.getsource(MPyConstraint._api1_mobject)
        self.assertIn("addNameChangedCallback", src)
        self.assertIn("CALLBACK_MANAGER", src)
        self.assertIn("_cached_api1_rename_token", src)


def setUpModule():
    _setUpModule__phaseN_4_constraint_mobject_cache()
    _setUpModule__phaseO_6_constraint_rename_hook()


if __name__ == "__main__":
    import unittest
    unittest.main()
