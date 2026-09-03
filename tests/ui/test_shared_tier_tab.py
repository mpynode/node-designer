"""The inner tier tab (Init / Compute / Viewport / Methods / ...) is SHARED
across all node editors instead of per-node-remembered.

Switching between node document tabs used to jump between whatever tier each
node last had open, which was disorienting. Now every node shows the same tier
(by NAME); a node that lacks the shared tier falls back to Compute (always
present). See ``NDScriptTabContent._shared_tier`` / ``_apply_shared_tier``.
"""

from __future__ import annotations

import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-sharedtier-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestSharedTierWiring(unittest.TestCase):
    """Source assertions — the wiring exists and syncs by NAME, not index."""

    def _src(self, fn):
        from mpynode.ui.widgets import script_tab_content as stc
        return inspect.getsource(getattr(stc.NDScriptTabContent, fn))

    def test_shared_tier_is_class_level_default_compute(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent
        # Class attribute (shared across instances), defaulting to Compute.
        self.assertEqual(
            NDScriptTabContent.__dict__.get("_shared_tier"), "Compute"
        )

    def test_init_applies_shared_and_connects_listener(self):
        src = self._src("__init__")
        self.assertIn("_apply_shared_tier()", src)
        self.assertIn(
            "currentChanged.connect(self._on_inner_tab_changed)", src
        )
        # Apply must precede the connect so the initial programmatic set does
        # not feed back into the shared choice.
        self.assertLess(
            src.index("_apply_shared_tier()"),
            src.index("currentChanged.connect(self._on_inner_tab_changed)"),
        )

    def test_show_event_applies_shared_tier(self):
        src = self._src("showEvent")
        self.assertIn("_apply_shared_tier()", src)

    def test_sync_is_by_name_not_index(self):
        # user-change handler stores the tab TEXT (name), not the raw index.
        chg = self._src("_on_inner_tab_changed")
        self.assertIn("tabText(index)", chg)
        self.assertIn("NDScriptTabContent._shared_tier", chg)
        # apply resolves by name and falls back to Compute.
        apply_src = self._src("_apply_shared_tier")
        self.assertIn("_index_for_tier", apply_src)
        self.assertIn('"Compute"', apply_src)


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestSharedTierBehavioral(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        # Global shared state — snapshot + reset so tests are isolated and do
        # not leak the shared tier into the rest of the suite.
        self._saved_tier = NDScriptTabContent._shared_tier
        NDScriptTabContent._shared_tier = "Compute"
        mc.file(new=True, force=True)
        self._widgets = []

    def tearDown(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass
        NDScriptTabContent._shared_tier = self._saved_tier

    def _locator_content(self, name):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        loc = MPyLocator.create(name=name)
        w = NDScriptTabContent(loc)
        self._widgets.append(w)
        return w

    @staticmethod
    def _current_tier(w):
        tabs = w._inner_tabs
        return tabs.tabText(tabs.currentIndex())

    def test_new_nodes_start_on_shared_default_compute(self):
        a = self._locator_content("sharedA")
        self.assertEqual(self._current_tier(a), "Compute")

    def test_user_switch_propagates_to_other_nodes(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        a = self._locator_content("sharedU1")
        b = self._locator_content("sharedU2")
        self.assertEqual(self._current_tier(a), "Compute")

        # Simulate a USER clicking node A's "Init" tab (fires currentChanged,
        # which is NOT guarded here → updates the shared choice).
        init_idx = a._index_for_tier("Init")
        self.assertGreaterEqual(init_idx, 0)
        a._inner_tabs.setCurrentIndex(init_idx)
        self.assertEqual(NDScriptTabContent._shared_tier, "Init")

        # Switching to node B (its document tab becoming active == showEvent ->
        # _apply_shared_tier) snaps B to the same tier.
        b._apply_shared_tier()
        self.assertEqual(self._current_tier(b), "Init")

    def test_fallback_to_compute_when_tier_absent_without_clobber(self):
        # Red-green guard test: shared tier is one this node lacks (mPyLocator
        # has no "Viewport"). Applying it must show Compute (fallback) AND must
        # NOT overwrite the shared choice — otherwise a node that DOES have the
        # tier would stop showing it.
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        a = self._locator_content("sharedF1")
        self.assertLess(a._index_for_tier("Viewport"), 0)  # locator has none

        NDScriptTabContent._shared_tier = "Viewport"
        a._apply_shared_tier()
        self.assertEqual(self._current_tier(a), "Compute")   # fell back
        self.assertEqual(
            NDScriptTabContent._shared_tier, "Viewport"
        )  # guard preserved the shared choice


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestFirstOpenPrefersCompute(unittest.TestCase):
    """A node opened for the FIRST time this session lands on Compute, whatever
    the shared tier is.

    Inheriting the shared tier on a node you have never opened is what made a
    freshly converted v1 node look broken: the Designer came up on API, which
    showed a generated ``build()`` stub, while Init and Compute -- the tabs
    that would have shown the real state -- went unlooked-at. Compute is the
    tier you want when meeting a node.

    Already-seen nodes keep the old behaviour, so switching tier and then
    flipping between nodes still works; that is what
    ``TestSharedTierBehavioral`` covers.
    """

    def setUp(self):
        import maya.cmds as mc
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        self._saved_tier = NDScriptTabContent._shared_tier
        self._saved_seen = set(NDScriptTabContent._seen_nodes)
        NDScriptTabContent._shared_tier = "Compute"
        NDScriptTabContent._seen_nodes.clear()
        mc.file(new=True, force=True)
        self._widgets = []

    def tearDown(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass
        NDScriptTabContent._shared_tier = self._saved_tier
        NDScriptTabContent._seen_nodes.clear()
        NDScriptTabContent._seen_nodes.update(self._saved_seen)

    def _content(self, name):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent
        from mpynode.wrappers.mpy_locator import MPyLocator

        w = NDScriptTabContent(MPyLocator.create(name=name))
        self._widgets.append(w)
        return w

    @staticmethod
    def _tier(w):
        tabs = w._inner_tabs
        return tabs.tabText(tabs.currentIndex())

    def test_a_never_seen_node_ignores_the_shared_tier(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        NDScriptTabContent._shared_tier = "Init"
        self.assertEqual(self._tier(self._content("firstOpenA")), "Compute")

    def test_the_shared_tier_survives_a_first_open(self):
        # First-open must not clobber the shared choice, or opening one new
        # node would reset the tier for every node after it.
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        NDScriptTabContent._shared_tier = "Init"
        self._content("firstOpenB")
        self.assertEqual(NDScriptTabContent._shared_tier, "Init")

    def test_a_second_apply_on_the_same_node_uses_the_shared_tier(self):
        # Construction marks the node seen, so a later re-sync (switching
        # document tabs back to it) honours the shared tier again.
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        w = self._content("firstOpenC")
        self.assertEqual(self._tier(w), "Compute")
        NDScriptTabContent._shared_tier = "Init"
        w._apply_shared_tier()
        self.assertEqual(self._tier(w), "Init")

    def test_the_node_is_recorded_as_seen(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        w = self._content("firstOpenD")
        self.assertIn(w._node_key(), NDScriptTabContent._seen_nodes)

    def test_the_key_is_a_uuid_and_survives_a_rename(self):
        import maya.cmds as mc

        w = self._content("firstOpenE")
        before = w._node_key()
        self.assertEqual(before[0], "uuid")
        mc.rename("firstOpenE", "firstOpenE_renamed")
        self.assertEqual(w._node_key(), before)
