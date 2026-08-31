"""NDScriptTabContent Script-area wiring.

The centre editor now has ONE tab strip, not two. The old half-width
[Expressions | Script] selector (a standalone QTabBar over a QStackedWidget)
is GONE: its two states were "the tier editors" and "the Methods pane", and
both are segments of the single strip now, alongside the new read-only API
view:

    Init | Compute | [Viewport] | [OSL] | Methods | API

Which tier segments appear is still decided by ``hasattr`` on the wrapper, so
the strip states what the node can actually do. The Methods pane kept its
widget and its plug and only changed label ("Script" -> "Methods"), because
the segment beside it is now the one that shows the whole script.

The per-instance emphasis stylesheet (the ``script_tab_style`` pref) survived
the deletion -- it just dresses the merged strip instead of the removed one, so
a user's saved choice still applies. An edit in the Methods pane still flags
the tab dirty and persists to ``_methodsSource`` on markSaved, and the
dirty/save/refresh aggregates still reference ``_script_pane``.
"""

from __future__ import annotations

import inspect
import os
import tempfile
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

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
    _QAPP = _QApplication.instance() or _QApplication(["script-area-wiring-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestScriptAreaWiring(unittest.TestCase):
    def setUp(self):
        # Isolate preferences to a temp file so tab-style set_pref calls never
        # touch the real ~/.mpynode/preferences.json (see the prefs isolation
        # gotcha), and clear cache + listeners between tests.
        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndscriptarea_test_")
        self._patch_dir = mock.patch.object(
            preferences, "PREFS_DIR", self._tmpdir)
        self._patch_path = mock.patch.object(
            preferences, "PREFS_PATH",
            os.path.join(self._tmpdir, "preferences.json"))
        self._patch_dir.start()
        self._patch_path.start()
        preferences._reset_for_tests()

        # _shared_tier is a MUTABLE CLASS attribute -- selecting a tab writes
        # it for every node in the session. Tests here change tabs, so restore
        # it or a later test asserting the class default sees our leftovers.
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        self._saved_tier = NDScriptTabContent.__dict__.get("_shared_tier")

    def tearDown(self):
        from mpynode.ui import preferences
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        NDScriptTabContent._shared_tier = self._saved_tier
        self._patch_dir.stop()
        self._patch_path.stop()
        preferences._reset_for_tests()
        try:
            for f in os.listdir(self._tmpdir):
                os.remove(os.path.join(self._tmpdir, f))
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def _build(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="scArea")
        return loc, NDScriptTabContent(loc)

    def _labels(self, w):
        return [w._inner_tabs.tabText(i)
                for i in range(w._inner_tabs.count())]

    def test_the_strip_is_tiers_then_api(self):
        loc, w = self._build()
        try:
            self.assertFalse(hasattr(w, "_script_pane"))
            labels = self._labels(w)
            self.assertIn("Init", labels)
            self.assertIn("Compute", labels)
            # The Methods segment is deleted; its editing moved INTO the API
            # view, where the defs sit inside the baked `class X:`.
            self.assertNotIn("Methods", labels)
            self.assertIs(w._inner_tabs.widget(labels.index("API")),
                          w._api_view)
        finally:
            w.deleteLater()

    def test_the_outer_selector_is_gone(self):
        loc, w = self._build()
        try:
            self.assertFalse(hasattr(w, "_outer_bar"),
                             "the [Expressions | Script] bar was removed")
            self.assertFalse(hasattr(w, "_outer_stack"))
            labels = self._labels(w)
            self.assertNotIn("Expressions", labels)
            self.assertNotIn("Script", labels)
        finally:
            w.deleteLater()

    def test_strip_order_is_runtime_order_then_api(self):
        loc, w = self._build()
        try:
            labels = self._labels(w)
            self.assertLess(labels.index("Init"), labels.index("Compute"))
            self.assertLess(labels.index("Compute"), labels.index("API"))
            # API is last, always present.
            self.assertEqual(labels[-1], "API")
        finally:
            w.deleteLater()

    def test_api_segment_shows_the_bake(self):
        from mpynode._common.io import py_export
        from mpynode.ui.widgets.api_view import NDApiView

        loc, w = self._build()
        try:
            labels = self._labels(w)
            api = w._inner_tabs.widget(labels.index("API"))
            self.assertIsInstance(api, NDApiView)
            self.assertIs(api, w._api_view)
            self.assertEqual(api.toPlainText(),
                             py_export.generate_node_script(loc))
            self.assertFalse(api.hasUnsavedChanges())
        finally:
            w.deleteLater()

    def test_clicking_a_zone_in_api_raises_the_owning_tier(self):
        loc, w = self._build()
        try:
            labels = self._labels(w)
            w._inner_tabs.setCurrentIndex(labels.index("API"))
            w.select("tier.compute")
            self.assertEqual(w._inner_tabs.tabText(
                w._inner_tabs.currentIndex()), "Compute")
            w.select("tier.init")
            self.assertEqual(w._inner_tabs.tabText(
                w._inner_tabs.currentIndex()), "Init")
            # A tier this node does not have must not move the selection.
            self.assertFalse(w.select("tier.osl"))
            self.assertEqual(w._inner_tabs.tabText(
                w._inner_tabs.currentIndex()), "Init")
        finally:
            w.deleteLater()

    def test_horizontal_bar(self):
        # One strip: a QTabWidget whose bar is the tall North bar shared by the
        # designer's other horizontal strips.
        from mpynode.ui.qt_wrapper import QTabBar, QTabWidget

        loc, w = self._build()
        try:
            self.assertIsInstance(w._inner_tabs, QTabWidget)
            self.assertIsInstance(w._inner_tab_bar, QTabBar)
            self.assertEqual(w._inner_tab_bar.shape(), QTabBar.RoundedNorth)
        finally:
            w.deleteLater()

    def test_strip_has_selected_emphasis_style(self):
        """The strip carries a stylesheet that emphasises the SELECTED tab (bold
        + accent underline) and dims the rest, so the active editor is obvious.
        It survived the deletion of the [Expressions | Script] selector it was
        written for. (The visual result must still be eyeballed in Maya; this
        only guards that the styling hook stays wired.)"""
        loc, w = self._build()
        try:
            ss = w._inner_tab_bar.styleSheet()
            self.assertTrue(ss.strip(), "the strip should carry a stylesheet")
            self.assertIn("QTabBar::tab", ss)
            self.assertIn("selected", ss)
        finally:
            w.deleteLater()

    def test_all_tab_styles_present_and_nonempty(self):
        """Every selectable style has a real stylesheet, so no pref value can
        resolve to an empty/absent style."""
        from mpynode.ui import preferences
        from mpynode.ui.widgets.script_tab_content import _OUTER_BAR_STYLES

        for name in preferences.VALID_SCRIPT_TAB_STYLES:
            self.assertIn(name, _OUTER_BAR_STYLES)
            ss = _OUTER_BAR_STYLES[name]
            self.assertTrue(ss.strip(), "style %r must be non-empty" % name)
            self.assertIn("QTabBar::tab", ss)

    def test_tab_style_reflects_pref_at_build(self):
        """A non-default pref value is honoured when the editor is built."""
        from mpynode.ui import preferences
        from mpynode.ui.widgets.script_tab_content import _OUTER_BAR_STYLES

        preferences.set_pref("script_tab_style", "fill")
        loc, w = self._build()
        try:
            self.assertEqual(w._inner_tab_bar.styleSheet(), _OUTER_BAR_STYLES["fill"])
        finally:
            w.deleteLater()

    def test_tab_style_updates_live_on_pref_change(self):
        """Changing the pref re-styles an already-open editor with no restart."""
        from mpynode.ui import preferences
        from mpynode.ui.widgets.script_tab_content import _OUTER_BAR_STYLES

        loc, w = self._build()
        try:
            # fresh (no saved pref) -> the shipped default style ("boxed")
            self.assertEqual(
                w._inner_tab_bar.styleSheet(), _OUTER_BAR_STYLES["boxed"])
            preferences.set_pref("script_tab_style", "top_accent")
            self.assertEqual(
                w._inner_tab_bar.styleSheet(), _OUTER_BAR_STYLES["top_accent"])
        finally:
            w.deleteLater()

    def test_preferences_dialog_tab_style_round_trip(self):
        """The Preferences ▸ Node Designer combo lists every style, loads the
        current pref, and writes the chosen one back on save."""
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        try:
            combo = dlg._script_tab_style_combo
            self.assertEqual(
                combo.count(), len(preferences.VALID_SCRIPT_TAB_STYLES))
            # load reflects the current pref
            preferences.set_pref("script_tab_style", "gray")
            dlg._load_into_widgets()
            idx = combo.currentIndex()
            self.assertEqual(dlg._SCRIPT_TAB_STYLE_OPTIONS[idx][1], "gray")
            # choosing another option + save writes it back
            for i, (_l, v) in enumerate(dlg._SCRIPT_TAB_STYLE_OPTIONS):
                if v == "classic":
                    combo.setCurrentIndex(i)
                    break
            dlg._on_save_clicked()
            self.assertEqual(preferences.get_pref("script_tab_style"), "classic")

            # auto-recompile checkbox loads + saves too
            preferences.set_pref("auto_recompile", True)
            dlg._load_into_widgets()
            self.assertTrue(dlg._auto_recompile_check.isChecked())
            dlg._auto_recompile_check.setChecked(False)
            dlg._on_save_clicked()
            self.assertFalse(preferences.get_pref("auto_recompile"))
        finally:
            dlg.deleteLater()

    def test_widest_strip_still_fits_without_scrolling(self):
        # The design review docked the one-strip approach for a measured
        # elision ceiling: if the segments overflow, the one widget whose job
        # is saying where you are starts truncating its own labels. mPyFile is
        # the worst case -- four tiers. Dropping the Methods segment took it
        # from six to five, which is what paid for the wider navigator.
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        node = MPyFile.create(name="scAreaWide")
        w = NDScriptTabContent(node)
        try:
            w.resize(580, 400)          # the shipped default centre width
            w.show()
            _QAPP.processEvents()
            labels = self._labels(w)
            self.assertEqual(
                labels, ["Init", "Compute", "Viewport", "OSL", "API"])
            bar = w._inner_tab_bar
            total = sum(bar.tabRect(i).width() for i in range(bar.count()))
            self.assertGreater(total, 0)
            self.assertLessEqual(
                total, bar.width(),
                "the segments overflow the shipped 580px centre pane "
                "(%dpx of tabs in %dpx of bar) -- the strip would scroll or "
                "elide its labels" % (total, bar.width()))
        finally:
            w.deleteLater()

    def test_strip_equalises_its_tabs_once_the_pane_can_afford_it(self):
        # The other half of UniformWidthTabBar's budget: five ragged buttons
        # read as an accident, so the tabs take the widest tab's width -- but
        # only where that fits. mPyFile's natural widths total 314px and the
        # equal ones 425px, so the switch happens around a 700px pane; at the
        # shipped 580px default the test above wins instead.
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        node = MPyFile.create(name="scAreaEqual")
        w = NDScriptTabContent(node)
        try:
            w.resize(900, 400)
            w.show()
            _QAPP.processEvents()
            bar = w._inner_tab_bar
            widths = [bar.tabRect(i).width() for i in range(bar.count())]
            self.assertEqual(len(widths), 5)
            self.assertEqual(
                len(set(widths)), 1,
                "tabs are still ragged at a 900px pane: %r" % (widths,))
            self.assertLessEqual(sum(widths), bar.width())
        finally:
            w.deleteLater()

    def test_methods_edit_dirties_and_marksaved_persists(self):
        # The same guarantee the Methods pane gave, now through the API view:
        # edit -> tab is dirty -> markSaved writes _methodsSource.
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="scEdit")
        loc.set_methods_source("def m(self):\n    return 1\n")
        w = NDScriptTabContent(loc)
        try:
            member = [r for r in w._api_view.regions()
                      if r["kind"] == "method_member"][0]
            block = w._api_view.document().findBlockByNumber(member["end"])
            cursor = w._api_view.textCursor()
            cursor.setPosition(block.position() + len(block.text()))
            w._api_view.setTextCursor(cursor)
            self._type(w._api_view, "  # touched")
            self.assertTrue(w.hasUnsavedChanges())
            w.markSaved()
            self.assertIn("# touched", loc.get_methods_source())
            self.assertFalse(w.hasUnsavedChanges())
        finally:
            w.deleteLater()

    @staticmethod
    def _type(view, text):
        try:
            from PySide6.QtGui import QKeyEvent
            from PySide6.QtCore import QEvent, Qt as _Qt
        except Exception:
            from PySide2.QtGui import QKeyEvent
            from PySide2.QtCore import QEvent, Qt as _Qt
        for ch in text:
            view.keyPressEvent(QKeyEvent(
                QEvent.KeyPress, _Qt.Key_A, _Qt.NoModifier, ch))

    def test_marksaved_source_references_the_api_view(self):
        loc, w = self._build()
        try:
            self.assertIn("_api_view", inspect.getsource(type(w).markSaved))
            self.assertIn("_api_view", inspect.getsource(type(w).refresh))
            self.assertIn(
                "_api_view", inspect.getsource(type(w).hasUnsavedChanges))
        finally:
            w.deleteLater()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestAGeneratedBlockRoutesToItsAuthoringSurface(unittest.TestCase):
    """Each generated block is a read-only rendering of something edited
    elsewhere, and clicking it goes there. Tiers reach their own tab inside
    the Script area; variables and attributes reach the LEFT panel, so those
    two travel up as requests the designer fulfils."""

    def setUp(self):
        # _shared_tier is a MUTABLE CLASS attribute and select() writes it for
        # the whole session. The tier test below raises Init, which without
        # this leaks into test_shared_tier_tab's "the default is Compute"
        # hundreds of tests later -- passing per-module and failing in the
        # full suite.
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        self._saved_tier = NDScriptTabContent.__dict__.get("_shared_tier")

    def tearDown(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        NDScriptTabContent._shared_tier = self._saved_tier

    def _build(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="scRoute")
        loc.add_input_attr("inFloat", "float")
        loc.add_output_attr("outFloat", "float")
        return loc, NDScriptTabContent(loc)

    def test_an_attribute_block_relays_up_to_the_designer(self):
        _loc, w = self._build()
        seen = []
        w.revealAttributesRequested.connect(seen.append)
        try:
            w._api_view.attributesActivated.emit("Outputs")
            self.assertEqual(seen, ["Outputs"])
        finally:
            w.deleteLater()

    def test_a_tier_click_lights_the_row_without_leaving_the_tab(self):
        # It used to raise the Init tab. Retracted: clicking a folded rail now
        # behaves like clicking any other managed block -- the navigator row
        # lights up and the reader keeps their place.
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        # NOT self._build(): that node has no expression set, so the bake
        # carries no expr_* region and there is no rail to click.
        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="scTier")
        loc.set_init_expression("self.seed = 1\n")
        w = NDScriptTabContent(loc)
        try:
            w.select("api")
            _QAPP.processEvents()
            before = w._inner_tabs.currentIndex()
            init = [r for r in w._api_view.regions()
                    if r["kind"] == "expr_init"][0]
            w._api_view.regionActivated.emit(init)
            _QAPP.processEvents()
            self.assertEqual(w._inner_tabs.currentIndex(), before)
            self.assertEqual(w._navigator.currentKey(), "tier.init")
        finally:
            w.deleteLater()

    def test_the_navigator_title_matches_the_tab_strip(self):
        # So "Symbol | Kind | Detail" lands level with the first line of code
        # rather than with the tabs above it.
        _loc, w = self._build()
        try:
            want = w._inner_tabs.tabBar().sizeHint().height()
            self.assertGreater(want, 0)
            self.assertEqual(w._navigator._title_bar.height(), want)
        finally:
            w.deleteLater()

    def test_the_column_header_lands_level_with_the_code(self):
        # The POINT of sizing the title bar off the tab strip, measured in
        # global coordinates rather than trusted to the layout maths: the two
        # panes are siblings in a splitter, so equal heights above them is only
        # the same thing as equal tops if nothing else intrudes.
        _loc, w = self._build()
        try:
            w.resize(940, 640)
            w.show()
            _QAPP.processEvents()
            w.select("api")
            _QAPP.processEvents()

            def top(widget):
                return widget.mapToGlobal(widget.rect().topLeft()).y()

            code = top(w._api_view.viewport())
            header = top(w._navigator._tree.header())
            self.assertLessEqual(
                abs(header - code), 2,
                "column header at %d, code at %d" % (header, code))
        finally:
            w.deleteLater()

    def test_the_designer_raises_the_attributes_tab(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "revealAttributes"))
        src = inspect.getsource(NDMainWindow.revealAttributes)
        self.assertIn("_attributes_widget", src)
        self.assertIn("setCurrentWidget", src)
        wired = inspect.getsource(NDMainWindow._wire_signals)
        self.assertIn("revealAttributesRequested", wired)

    def test_the_signal_survives_the_hop_through_the_tab_widget(self):
        # NDScriptTabWidget aggregates per-document editors; a signal that is
        # declared but never connected there dies silently at the boundary.
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        self.assertTrue(hasattr(NDScriptTabWidget, "revealAttributesRequested"))
        joined = "".join(
            inspect.getsource(getattr(NDScriptTabWidget, name))
            for name in dir(NDScriptTabWidget)
            if callable(getattr(NDScriptTabWidget, name, None))
            and getattr(getattr(NDScriptTabWidget, name), "__module__", "")
            == NDScriptTabWidget.__module__)
        self.assertIn(
            "editor.revealAttributesRequested.connect", joined,
            "the aggregate signal is declared but never connected")


if __name__ == "__main__":
    unittest.main()
