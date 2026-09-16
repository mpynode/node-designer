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
class TestModeTabs(unittest.TestCase):
    """Option B — a top-level mode switcher (Workspace | Templates) swaps the
    whole content region so the gallery gets the full window width, instead of
    sharing the cramped 340px right panel with the Assistant."""

    def test_build_ui_creates_mode_tabs(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("self._mode_tabs", src)
        self.assertIn("NDTemplateGalleryPanel", src)
        self.assertIn('addTab(workspace, "Workspace")', src)
        self.assertIn('addTab(self._gallery_panel, "Templates")', src)
        self.assertIn("setCurrentIndex(0)", src)
        # The Assistant lives beside the editor in the Workspace splitter now,
        # not in a right-edge tab widget.
        self.assertIn("splitter.addWidget(self._assistant_panel)", src)
        # The old shared side-tab panel must be gone entirely.
        self.assertNotIn("self._side_tabs", src)

    def test_gallery_built_before_assistant(self):
        # The gallery (Templates mode page) is built OUTSIDE the assistant's
        # try/except so Templates mode is always available; the assistant
        # degrades to a Workspace-without-Assistant on failure.
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("self._assistant_panel = None", src)
        self.assertLess(
            src.find("NDTemplateGalleryPanel"), src.find("NDAssistantPanel")
        )

    def test_mode_tab_change_stops_video(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        self.assertTrue(hasattr(NDMainWindow, "_on_mode_tab_changed"))
        chg = inspect.getsource(NDMainWindow._on_mode_tab_changed)
        self.assertIn("stop_video", chg)
        build = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn(
            "currentChanged.connect(self._on_mode_tab_changed)", build
        )

    def test_mode_tabs_are_vertical_west(self):
        # The Workspace | Templates mode switch is a vertical tab bar down the
        # LEFT edge so it reads distinctly from the horizontal Scene |
        # Attributes | Variables panel tabs it would otherwise stack above.
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("setTabPosition(QTabWidget.West)", src)

    def test_qtabwidget_west_enum_available(self):
        # West must resolve in whichever binding is active (PySide2 in Maya
        # 2024, PySide6 in Maya 2026) or _build_ui would raise on construction.
        from mpynode.ui.qt_wrapper import QTabWidget
        self.assertTrue(hasattr(QTabWidget, "West"))

    def test_mode_tab_bar_is_widened(self):
        # _build_ui installs the custom wide bar before adding tabs.
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("_WideTabBar(self._mode_tabs)", src)
        self.assertIn("setTabBar(self._mode_tab_bar)", src)

    def test_wide_tab_bar_is_1_5x_thicker(self):
        # Behavioral: a West bar built from _WideTabBar juts out ~1.5x further
        # than a plain West bar (its tabs are wider / more noticeable).
        from mpynode.ui.mpynode_designer import _WideTabBar
        from mpynode.ui.qt_wrapper import QTabWidget, QWidget

        def _west(bar=None):
            tw = QTabWidget()
            if bar is not None:
                tw.setTabBar(bar)
            tw.setTabPosition(QTabWidget.West)
            tw.addTab(QWidget(), "Workspace")
            tw.addTab(QWidget(), "Templates")
            tw.resize(400, 400)
            tw.show()
            _app.processEvents()
            return tw

        plain = _west()
        wide  = _west(_WideTabBar())
        self.assertIs(wide.tabBar().__class__, _WideTabBar)
        pw = plain.tabBar().tabRect(0).width()
        ww = wide.tabBar().tabRect(0).width()
        self.assertGreater(pw, 0)
        self.assertGreater(ww, pw)  # wider
        self.assertAlmostEqual(ww / float(pw), 1.5, delta=0.2)
        plain.deleteLater()
        wide.deleteLater()


@unittest.skipUnless(_QT, "Qt unavailable")
class TestModeSwitching(unittest.TestCase):
    def test_on_new_from_template_switches_and_reloads(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._on_new_from_template)
        self.assertIn("_show_templates_mode", src)
        self.assertIn("reload", src)
        self.assertNotIn("open_template_gallery", src)

    def test_show_templates_mode_switches_page(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        self.assertTrue(hasattr(NDMainWindow, "_show_templates_mode"))
        src = inspect.getsource(NDMainWindow._show_templates_mode)
        self.assertIn("setCurrentIndex", src)

    def test_create_returns_to_workspace(self):
        # Any create (plain New or from a template) lands the user back in the
        # Workspace with the new node's editor open.
        from mpynode.ui.mpynode_designer import NDMainWindow
        self.assertTrue(hasattr(NDMainWindow, "_show_workspace_mode"))
        src = inspect.getsource(NDMainWindow._post_create)
        self.assertIn("_show_workspace_mode", src)

    def test_toggle_uses_assistant_pane(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow.toggle_assistant_panel)
        self.assertIn("_assistant_panel", src)

    def test_dialog_module_deleted(self):
        import importlib
        with self.assertRaises(ImportError):
            importlib.import_module(
                "mpynode.ui.dialogs.template_gallery_dialog"
            )


@unittest.skipUnless(_QT, "Qt unavailable")
class TestLayoutPersistence(unittest.TestCase):
    def test_layout_default_prefs_exist(self):
        from mpynode.ui import preferences
        self.assertIn("layout_main_splitter", preferences.DEFAULT_PREFS)
        self.assertIsNone(preferences.DEFAULT_PREFS["layout_main_splitter"])
        self.assertIsNone(preferences.DEFAULT_PREFS["layout_right_splitter"])
        self.assertIsNone(preferences.DEFAULT_PREFS["layout_window_geometry"])
        self.assertEqual(preferences.DEFAULT_PREFS["layout_mode_tab"], 0)

    def test_coerce_int_list(self):
        from mpynode.ui.mpynode_designer import _coerce_int_list
        self.assertEqual(_coerce_int_list([1, 2, 3], 3), [1, 2, 3])
        self.assertEqual(_coerce_int_list((10, 20), 2), [10, 20])
        self.assertIsNone(_coerce_int_list([1, 2], 3))           # wrong length
        self.assertIsNone(_coerce_int_list("nope", 3))           # wrong type
        self.assertIsNone(_coerce_int_list(None, 3))             # None
        self.assertIsNone(_coerce_int_list(["a", "b", "c"], 3))  # non-int elems

    def test_restore_layout_wired_in_build_ui(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        self.assertTrue(hasattr(NDMainWindow, "_restore_layout"))
        build = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("self._restore_layout()", build)
        src = inspect.getsource(NDMainWindow._restore_layout)
        for key in ("layout_window_geometry", "layout_main_splitter",
                    "layout_right_splitter", "layout_mode_tab"):
            self.assertIn(key, src)

    def test_close_event_saves_layout(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow.closeEvent)
        self.assertIn("layout_main_splitter", src)
        self.assertIn("layout_right_splitter", src)
        self.assertIn("layout_window_geometry", src)
        self.assertIn("set_pref", src)

    def test_mode_tab_change_saves_active_tab(self):
        from mpynode.ui.mpynode_designer import NDMainWindow
        src = inspect.getsource(NDMainWindow._on_mode_tab_changed)
        self.assertIn("layout_mode_tab", src)
        self.assertIn("set_pref", src)


if __name__ == "__main__":
    unittest.main()
