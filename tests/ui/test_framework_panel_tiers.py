"""What the Framework PANEL actually renders, tab by tab.

``test_framework_tier_scope`` measures the reachability and locks the scope
TABLE; this locks the WIDGET that consumes it -- the groups a user sees when the
editor is on Init / Compute / Viewport / OSL / API.

The panel used to render the same four groups on every tab. On an mPyFile that
meant 13 authoring methods that AttributeError in a compute, and four VP2-only
handles that AttributeError anywhere but the Viewport. Both surfaces are still
reachable -- just from the one tab that can call them.
"""

from __future__ import annotations

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
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-tierpanel-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _qapp_available():
    return _QAPP is not None


def _group_labels(tree):
    """Top-level group names, in render order."""
    return [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]


def _group(tree, label):
    for i in range(tree.topLevelItemCount()):
        it = tree.topLevelItem(i)
        if it.text(0) == label:
            return it
    return None


def _rows(tree, label):
    """Col-0 texts under group ``label``; [] when the group is absent."""
    top = _group(tree, label)
    if top is None:
        return []
    return [top.child(i).text(0) for i in range(top.childCount())]


class _PanelCase(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    def _panel(self, py_node, tier=None):
        from mpynode.ui.widgets.framework_tab import NDFrameworkWidget

        w = NDFrameworkWidget()
        self._widgets.append(w)
        w.setPyNode(py_node)
        if tier is not None:
            w.setActiveTier(tier)
        return w

    def _file(self):
        from mpynode.wrappers.mpy_file import MPyFile

        return MPyFile.create(name="tierPanelFile#")

    def _locator(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        return MPyLocator.create(name="tierPanelLoc#")


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestFilePanelPerTier(_PanelCase):
    """mPyFile is the wrapper the redesign started from: 2 blessed methods,
    5 slots (1 general + 4 VP2-only), 13 authoring methods."""

    def test_init_renders_nothing_and_explains_itself(self):
        w = self._panel(self._file(), "Init")
        self.assertEqual(_group_labels(w._tree).__len__(), 1,
                         "Init must render no GROUPS, only the note")
        note = w._tree.topLevelItem(0).text(0)
        self.assertIn("PLUGS only", note)
        self.assertNotIn("Methods", _group_labels(w._tree))

    def test_compute_shows_the_expression_surface_only(self):
        w = self._panel(self._file(), "Compute")
        self.assertEqual(_group_labels(w._tree), ["Methods", "Properties"])
        self.assertEqual(_rows(w._tree, "Methods"),
                         ["read_texture", "sample_texture", "composite_layers",
                          "write_texture"])

    def test_compute_hides_the_vp2_only_handles(self):
        """shader / mappings / texture_manager / state_manager are injected by
        the VP2 draw override; in a compute they raise."""
        w = self._panel(self._file(), "Compute")
        rows = _rows(w._tree, "Properties")
        self.assertEqual(rows, ["time"])
        for name in ("shader", "mappings", "texture_manager", "state_manager"):
            self.assertNotIn(name, rows)

    def test_viewport_adds_the_vp2_handles_back(self):
        w = self._panel(self._file(), "Viewport")
        rows = _rows(w._tree, "Properties")
        for name in ("time", "shader", "mappings", "texture_manager",
                     "state_manager"):
            self.assertIn(name, rows, "%s must be listed on the Viewport tab"
                                      % name)

    def test_osl_renders_nothing_and_explains_itself(self):
        w = self._panel(self._file(), "OSL")
        self.assertEqual(len(_group_labels(w._tree)), 1)
        self.assertIn("shader language", w._tree.topLevelItem(0).text(0))

    def test_api_shows_authoring_and_nothing_from_the_expression_side(self):
        w = self._panel(self._file(), "API")
        labels = _group_labels(w._tree)
        self.assertIn("Authoring Methods", labels)
        self.assertNotIn("Methods", labels,
                         "read_texture does not resolve on the wrapper")
        self.assertNotIn("Properties", labels,
                         "mPyFile has no wrapper @property surface")
        self.assertEqual(len(_rows(w._tree, "Authoring Methods")), 13)

    def test_authoring_never_appears_on_an_expression_tab(self):
        node = self._file()
        for tier in ("Init", "Compute", "Viewport", "OSL"):
            w = self._panel(node, tier)
            self.assertNotIn("Authoring Methods", _group_labels(w._tree),
                             "Authoring Methods leaked onto %s" % tier)


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestDrawTypesAreComputeOnly(_PanelCase):
    """``self.draw = Draw*(...)`` is a COMPUTE assignment, so the type list is
    only useful on that one tab."""

    def test_compute_lists_the_draw_types(self):
        w = self._panel(self._locator(), "Compute")
        self.assertIn("Draw types", _group_labels(w._tree))
        self.assertIn("DrawSphere", _rows(w._tree, "Draw types"))

    def test_other_tiers_do_not(self):
        node = self._locator()
        for tier in ("Init", "Viewport", "OSL", "API"):
            w = self._panel(node, tier)
            self.assertNotIn("Draw types", _group_labels(w._tree),
                             "Draw types leaked onto %s" % tier)


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestTierWiringBehaviour(_PanelCase):

    def test_unset_tier_renders_the_compute_panel(self):
        """The panel is constructed before the editor reports a tab. It must
        show a USEFUL surface meanwhile, not an empty one."""
        node = self._file()
        default = self._panel(node)
        compute = self._panel(node, "Compute")
        self.assertIsNone(default.activeTier())
        self.assertEqual(_group_labels(default._tree),
                         _group_labels(compute._tree))
        self.assertEqual(_rows(default._tree, "Properties"),
                         _rows(compute._tree, "Properties"))

    def test_switching_tabs_rebuilds_live(self):
        """Round-trip: the API tab's groups must not persist back onto Compute,
        and Compute's must come back."""
        w = self._panel(self._file(), "Compute")
        before = _group_labels(w._tree)
        w.setActiveTier("API")
        self.assertEqual(_group_labels(w._tree), ["Authoring Methods"])
        w.setActiveTier("Compute")
        self.assertEqual(_group_labels(w._tree), before)

    def test_repeating_a_tier_is_a_no_op(self):
        w = self._panel(self._file(), "Compute")
        before = _group_labels(w._tree)
        w.setActiveTier("Compute")
        self.assertEqual(_group_labels(w._tree), before)
        self.assertEqual(w.activeTier(), "Compute")


if __name__ == "__main__":
    unittest.main()
