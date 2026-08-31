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
