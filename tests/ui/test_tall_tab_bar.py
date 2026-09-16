"""Horizontal (North) tab strips are 1.5x taller.

The Node Designer's horizontal tab bars — Scene | Attributes | Variables
(``_panel_tab_widget``), Log | Watch | Profile (``_tools_tab_widget``), the
per-node editor document tabs (``NDEditorTabBar``), and the Init | Compute | ...
inner tier tabs (``script_tab_content._inner_tabs``) — are made ~1.5x taller via
``ui.widgets.tall_tab_bar``. This mirrors the West mode tabs' 1.5x *width* bump.

The vertical West ``_mode_tabs`` must stay on ``_WideTabBar`` (width scaling),
NOT the tall bar — this file guards that too.
"""

import inspect
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:  # QApplication must exist before importing UI modules that build widgets.
    from mpynode.ui.qt_wrapper import Qt  # noqa: F401
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        from PySide2.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    _QT  = True
except Exception:  # pragma: no cover - Qt missing
    _QT = False


def setUpModule():
    try:
        from tests._setup import standalone_init
        standalone_init()
    except Exception:
        pass


@unittest.skipUnless(_QT, "Qt unavailable")
class TestTallTabBarUnit(unittest.TestCase):
    def test_scale_constant_is_1_5(self):
        from mpynode.ui.widgets.tall_tab_bar import TAB_HEIGHT_SCALE
        self.assertEqual(TAB_HEIGHT_SCALE, 1.5)

    def test_taller_scales_height_only(self):
        from mpynode.ui.qt_wrapper import QSize
        from mpynode.ui.widgets.tall_tab_bar import taller
        out = taller(QSize(80, 20))
        self.assertEqual(out.width(), 80)   # width untouched
        self.assertEqual(out.height(), 30)  # 20 * 1.5

    def test_make_tabs_tall_installs_and_preserves_tabs(self):
        # Installed BEFORE addTab -> the custom bar is a TallTabBar AND the
        # tabs survive (setTabBar wipes tabs added earlier; this proves the
        # call site ordering contract).
        from mpynode.ui.qt_wrapper import QTabWidget, QWidget
        from mpynode.ui.widgets.tall_tab_bar import make_tabs_tall, TallTabBar

        tw  = QTabWidget()
        bar = make_tabs_tall(tw)
        tw.addTab(QWidget(), "A")
        tw.addTab(QWidget(), "B")
        self.assertIs(bar, tw.tabBar())
        self.assertIsInstance(tw.tabBar(), TallTabBar)
        self.assertEqual(tw.count(), 2)


@unittest.skipUnless(_QT, "Qt unavailable")
class TestTallTabBarBehavioral(unittest.TestCase):
    def _north(self, bar=None):
        from mpynode.ui.qt_wrapper import QTabWidget, QWidget
        tw = QTabWidget()
        if bar is not None:
            tw.setTabBar(bar)
        tw.addTab(QWidget(), "Scene")
        tw.addTab(QWidget(), "Attributes")
        tw.resize(400, 400)
        tw.show()
        _app.processEvents()
        return tw

    def test_tall_bar_is_1_5x_taller(self):
        from mpynode.ui.widgets.tall_tab_bar import TallTabBar
        plain = self._north()
        tall  = self._north(TallTabBar())
        ph    = plain.tabBar().tabRect(0).height()
        th    = tall.tabBar().tabRect(0).height()
        self.assertGreater(ph, 0)
        self.assertGreater(th, ph)  # taller
        self.assertAlmostEqual(th / float(ph), 1.5, delta=0.2)
        # width (length along the North bar) must be unchanged
        self.assertEqual(
            plain.tabBar().tabRect(0).width(),
            tall.tabBar().tabRect(0).width(),
        )
        plain.deleteLater()
        tall.deleteLater()

    def test_editor_tab_bar_is_1_5x_taller(self):
        # The editor document tabs use their own bespoke NDEditorTabBar (for the
        # reliable close button); it must be taller by the same factor.
        from mpynode.ui.widgets.script_tab import NDEditorTabBar
        plain = self._north()
        ed    = self._north(NDEditorTabBar())
        ph    = plain.tabBar().tabRect(0).height()
        eh    = ed.tabBar().tabRect(0).height()
        self.assertGreater(eh, ph)
        self.assertAlmostEqual(eh / float(ph), 1.5, delta=0.2)
        plain.deleteLater()
        ed.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestEqualWidthTabBar(unittest.TestCase):
    """The Expressions | Script switch uses an equal-width North bar: each tab
    claims bar-width / count (two tabs => halves), still 1.5x taller."""

    def test_tab_size_hint_splits_width_evenly(self):
        from mpynode.ui.widgets.tall_tab_bar import EqualWidthTabBar

        bar = EqualWidthTabBar()
        bar.addTab("Expressions")
        bar.addTab("Script")
        bar.resize(400, 40)
        # Each of the two tabs claims exactly half of the 400px bar.
        self.assertEqual(bar.tabSizeHint(0).width(), 200)
        self.assertEqual(bar.tabSizeHint(1).width(), 200)

    def test_tab_size_hint_falls_back_before_layout(self):
        # width() <= 0 (never laid out) -> natural non-zero width, not a 0-wide
        # tab that would vanish.
        from mpynode.ui.widgets.tall_tab_bar import EqualWidthTabBar

        bar = EqualWidthTabBar()
        bar.addTab("Expressions")
        bar.resize(0, 40)
        self.assertGreater(bar.tabSizeHint(0).width(), 0)

    def test_still_1_5x_taller(self):
        from mpynode.ui.qt_wrapper import QTabBar
        from mpynode.ui.widgets.tall_tab_bar import EqualWidthTabBar

        plain = QTabBar()
        plain.addTab("Expressions")
        bar = EqualWidthTabBar()
        bar.addTab("Expressions")
        bar.resize(400, 40)
        self.assertGreater(
            bar.tabSizeHint(0).height(), plain.tabSizeHint(0).height()
        )

    def test_rendered_tabs_are_equal_halves(self):
        # STANDALONE bar in a plain layout (NOT QTabWidget.setTabBar): it
        # stretches to the full container width, so the two tabs come out as
        # equal halves that fill the bar.
        from mpynode.ui.qt_wrapper import QVBoxLayout, QWidget
        from mpynode.ui.widgets.tall_tab_bar import EqualWidthTabBar

        host = QWidget()
        lay  = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        bar = EqualWidthTabBar()
        bar.addTab("Expressions")
        bar.addTab("Script")
        lay.addWidget(bar)
        host.resize(400, 120)
        host.show()
        _app.processEvents()
        w0 = bar.tabRect(0).width()
        w1 = bar.tabRect(1).width()
        self.assertGreater(w0, 0)
        self.assertAlmostEqual(w0, w1, delta=2)                 # equal halves
        self.assertAlmostEqual(w0, bar.width() / 2.0, delta=6)  # ~half the bar
        self.assertGreater(w0, 150)                             # fills width, not text-hugging
        host.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestTallTabBarWiredIn(unittest.TestCase):
    """Source assertions: every horizontal strip installs the tall bar, and the
    West mode tabs stay on the WIDE bar (not the tall one)."""

    def test_script_strip_is_the_tall_bar(self):
        # The Script area is now ONE strip -- the tiers, Methods and API as
        # peers -- so it uses the shared tall North bar like every other
        # horizontal strip. The old half-width EqualWidthTabBar over a
        # QStackedWidget is gone with the selector it split.
        #
        # UniformWidthTabBar, not TallTabBar: it SUBCLASSES the tall bar (so
        # the height is unchanged and this strip still matches the others) and
        # adds the equal-width pass this strip alone wants.
        from mpynode.ui.widgets import script_tab_content
        src = inspect.getsource(
            script_tab_content.NDScriptTabContent.__init__)
        self.assertIn("make_tabs_uniform(self._inner_tabs)", src)
        self.assertIn("self._inner_tab_bar =", src)  # ref kept vs PySide GC
        self.assertNotIn("EqualWidthTabBar",  src)
        self.assertNotIn("self._outer_bar",   src)
        self.assertNotIn("self._outer_stack", src)

    def test_designer_panel_and_tools_are_tall(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("make_tabs_tall(self._panel_tab_widget)", src)
        self.assertIn("make_tabs_tall(self._tools_tab_widget)", src)
        # Refs kept on self so PySide does not GC the wrappers.
        self.assertIn("self._panel_tab_bar =", src)
        self.assertIn("self._tools_tab_bar =", src)

    def test_tools_floor_derived_from_tall_bar_not_stale_30(self):
        # The tools panel's minimum height (its splitter floor, so "only the
        # tab labels show" when collapsed) must be DERIVED from the now-taller
        # bar, not the old hard-coded 30 (calibrated to the ~31/36px bar)
        # which would clip the taller labels.
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("self._tools_tab_bar.sizeHint().height()", src)
        self.assertNotIn("setMinimumHeight(30)", src)

    def test_designer_imports_make_tabs_tall(self):
        import inspect as _i
        from mpynode.ui import mpynode_designer
        src = _i.getsource(mpynode_designer)
        self.assertIn(
            "from mpynode.ui.widgets.tall_tab_bar import make_tabs_tall", src
        )

    def test_mode_tabs_stay_wide_not_tall(self):
        # The vertical West Workspace | Templates switch keeps the WIDTH-scaling
        # _WideTabBar; the tall (height) bar must NOT be applied to it.
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("_WideTabBar(self._mode_tabs)", src)
        self.assertNotIn("make_tabs_tall(self._mode_tabs)", src)

    def test_editor_tab_bar_overrides_tab_size_hint(self):
        from mpynode.ui.widgets.script_tab import NDEditorTabBar
        src = inspect.getsource(NDEditorTabBar.tabSizeHint)
        self.assertIn("taller", src)

    def test_inner_tier_tabs_are_tall(self):
        # make_tabs_uniform installs UniformWidthTabBar, a TallTabBar subclass,
        # so the tier strip keeps the shared 1.5x height.
        from mpynode.ui.widgets.tall_tab_bar import (
            TallTabBar,
            UniformWidthTabBar,
        )
        from mpynode.ui.widgets import script_tab_content
        src = inspect.getsource(script_tab_content.NDScriptTabContent.__init__)
        self.assertIn("make_tabs_uniform(self._inner_tabs)", src)
        self.assertIn("self._inner_tab_bar =", src)
        self.assertTrue(issubclass(UniformWidthTabBar, TallTabBar))


if __name__ == "__main__":
    unittest.main()
