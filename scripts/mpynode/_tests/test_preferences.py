"""Preferences module + dialog."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import maya.cmds as mc

from._setup import ensure_plugins_loaded, standalone_init

# A QApplication at IMPORT time so the dialog-building tests below can construct
# NDPreferencesDialog headlessly (mirrors the other UI test modules). Without
# one, building a QWidget under mayapy segfaults.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-prefs-test"])


def setUpModule():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# preferences module \u2014 pure Python, no Qt
# ===========================================================================


class TestPreferencesModule(unittest.TestCase):
    """Use a temp prefs file per test so tests don't clobber the user's
    real ~/.mpynode/preferences.json."""

    def setUp(self):
        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_test_")
        self._patch_dir = mock.patch.object(preferences, "PREFS_DIR", self._tmpdir)
        self._patch_path = mock.patch.object(
            preferences,
            "PREFS_PATH",
            os.path.join(self._tmpdir, "preferences.json"),
        )
        self._patch_dir.start()
        self._patch_path.start()
        preferences._reset_for_tests()

    def tearDown(self):
        from mpynode.ui import preferences

        self._patch_dir.stop()
        self._patch_path.stop()
        preferences._reset_for_tests()
        # Clean tmp dir.
        try:
            for f in os.listdir(self._tmpdir):
                os.remove(os.path.join(self._tmpdir, f))
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def test_get_pref_returns_default_when_no_file(self):
        from mpynode.ui import preferences

        self.assertEqual(preferences.get_pref("editor_font_family"), "Courier")
        self.assertEqual(preferences.get_pref("editor_font_size"), 10)
        self.assertTrue(preferences.get_pref("addattr_time_auto_connect"))
        self.assertFalse(preferences.get_pref("connect_dialog_show_all_default"))

        self.assertTrue(preferences.get_pref("connect_dialog_hide_pivots_default"))
        self.assertEqual(
            preferences.get_pref("connect_dialog_sort_mode_default"), "selection"
        )

    def test_set_pref_persists_and_get_pref_reads_back(self):
        from mpynode.ui import preferences

        preferences.set_pref("editor_font_size", 14)
        self.assertEqual(preferences.get_pref("editor_font_size"), 14)
        # Verify it actually wrote to disk.
        self.assertTrue(os.path.exists(preferences.PREFS_PATH))
        with open(preferences.PREFS_PATH) as f:
            data = json.load(f)
        self.assertEqual(data["editor_font_size"], 14)

    def test_round_trip_via_fresh_load(self):
        """Set, reset cache, get \u2014 should pick up the on-disk value."""
        from mpynode.ui import preferences

        preferences.set_pref("editor_font_family", "Menlo")
        preferences.set_pref("editor_font_size", 12)
        preferences.set_pref("addattr_time_auto_connect", False)

        # Simulate process restart \u2014 wipe cache.
        preferences._reset_for_tests()

        self.assertEqual(preferences.get_pref("editor_font_family"), "Menlo")
        self.assertEqual(preferences.get_pref("editor_font_size"), 12)
        self.assertFalse(preferences.get_pref("addattr_time_auto_connect"))

    def test_corrupt_json_falls_back_to_defaults(self):
        from mpynode.ui import preferences

        # Write garbage to the prefs file.
        os.makedirs(self._tmpdir, exist_ok=True)
        with open(preferences.PREFS_PATH, "w") as f:
            f.write("{not valid json")

        preferences._reset_for_tests()

        # Should NOT raise; should serve defaults.
        self.assertEqual(preferences.get_pref("editor_font_family"), "Courier")

    def test_missing_keys_in_file_filled_from_defaults(self):
        """Old prefs file missing newer keys \u2014 those keys should still
        return the default."""
        from mpynode.ui import preferences

        os.makedirs(self._tmpdir, exist_ok=True)
        with open(preferences.PREFS_PATH, "w") as f:
            json.dump({"editor_font_size": 16}, f)

        preferences._reset_for_tests()

        # Saved value comes back.
        self.assertEqual(preferences.get_pref("editor_font_size"), 16)
        # Missing key falls back to default.
        self.assertEqual(preferences.get_pref("editor_font_family"), "Courier")

    def test_reset_to_defaults(self):
        from mpynode.ui import preferences

        preferences.set_pref("editor_font_size", 99)
        preferences.set_pref("addattr_time_auto_connect", False)

        preferences.reset_to_defaults()

        self.assertEqual(preferences.get_pref("editor_font_size"), 10)
        self.assertTrue(preferences.get_pref("addattr_time_auto_connect"))

    def test_listeners_fire_on_set_pref(self):
        from mpynode.ui import preferences

        events = []

        def cb(key, value):
            events.append((key, value))

        preferences.register_change_listener(cb)
        preferences.set_pref("editor_font_size", 18)
        preferences.set_pref("editor_font_size", 18)  # no change \u2014 no fire
        preferences.set_pref("editor_font_family", "Menlo")

        self.assertEqual(
            events, [("editor_font_size", 18), ("editor_font_family", "Menlo")]
        )

        preferences.unregister_change_listener(cb)
        preferences.set_pref("editor_font_size", 20)
        # Should not have appended.
        self.assertEqual(len(events), 2)

    def test_listener_exceptions_are_swallowed(self):
        from mpynode.ui import preferences

        def bad_cb(key, value):
            raise RuntimeError("boom")

        preferences.register_change_listener(bad_cb)
        # Must not raise.
        preferences.set_pref("editor_font_size", 13)

    def test_unregister_listener_safe_on_unknown(self):
        from mpynode.ui import preferences

        def cb(k, v):
            pass

        # Never registered; should not raise.
        preferences.unregister_change_listener(cb)

    # -- AI-optimize timeout preference (#65) ---------------------------------
    def test_optimize_timeout_defaults(self):
        from mpynode.ui import preferences

        # Ships ENABLED at the generous optimizer budget so existing behaviour
        # is preserved; the user can disable it to remove the wall-clock cap.
        self.assertTrue(preferences.get_pref("optimize_timeout_enabled"))
        self.assertEqual(preferences.get_pref("optimize_timeout_seconds"), 2400)

    def test_resolve_optimize_timeout_enabled_returns_seconds(self):
        from mpynode.ui import preferences

        preferences.set_pref("optimize_timeout_enabled", True)
        preferences.set_pref("optimize_timeout_seconds", 900)
        self.assertEqual(preferences.resolve_optimize_timeout(), 900.0)

    def test_resolve_optimize_timeout_disabled_returns_inf(self):
        from mpynode.ui import preferences

        preferences.set_pref("optimize_timeout_enabled", False)
        self.assertEqual(preferences.resolve_optimize_timeout(), float("inf"))

    def test_optimize_max_tokens_default(self):
        from mpynode.ui import preferences

        # 4096 served only 9% of this repo's cached translation units; 64000
        # serves 72% and clears the kdtree that motivated the setting.
        self.assertEqual(preferences.get_pref("optimize_max_tokens"), 64000)
        self.assertEqual(preferences.resolve_optimize_max_tokens(), 64000)

    def test_resolve_optimize_max_tokens_bad_value_falls_back(self):
        from mpynode.ui import preferences

        preferences.set_pref("optimize_max_tokens", "nope")
        self.assertEqual(preferences.resolve_optimize_max_tokens(), 64000)

    def test_all_prefs_returns_full_dict(self):
        from mpynode.ui import preferences

        prefs = preferences.all_prefs()
        for key in preferences.DEFAULT_PREFS:
            self.assertIn(key, prefs)

    # -- new_node_mode (replaces the old init_show_header checkbox) ------

    def test_new_node_mode_default_is_headers(self):
        from mpynode.ui import preferences

        self.assertEqual(preferences.get_pref("new_node_mode"), "headers")
        self.assertEqual(preferences.new_node_mode(), "headers")
        self.assertTrue(preferences.show_new_node_header())

    def test_new_node_mode_none_hides_header(self):
        from mpynode.ui import preferences

        preferences.set_pref("new_node_mode", "none")
        self.assertEqual(preferences.new_node_mode(), "none")
        self.assertFalse(preferences.show_new_node_header())

    def test_new_node_mode_template_migrates_to_headers(self):
        """'template' is retired as a new_node_mode choice (it moved to the
        New-from-Template gallery). A prefs file that still stores 'template'
        must migrate to 'headers' on read so old prefs keep working."""
        from mpynode.ui import preferences

        preferences.set_pref("new_node_mode", "template")
        self.assertEqual(preferences.new_node_mode(), "headers")
        self.assertTrue(preferences.show_new_node_header())
        self.assertNotIn("template", preferences.VALID_NEW_NODE_MODES)

    def test_new_node_mode_invalid_falls_back_to_headers(self):
        from mpynode.ui import preferences

        preferences.set_pref("new_node_mode", "garbage")
        self.assertEqual(preferences.new_node_mode(), "headers")
        self.assertTrue(preferences.show_new_node_header())

    # -- script_tab_style (selected Expressions/Script tab emphasis) -----

    def test_script_tab_style_default_matches_the_declared_default(self):
        """Also pins the parity DEFAULT_SCRIPT_TAB_STYLE claims to keep with
        DEFAULT_PREFS -- asserted against the constant, not a literal, so
        changing the shipped look is a one-line change in preferences.py."""
        from mpynode.ui import preferences

        self.assertEqual(preferences.get_pref("script_tab_style"),
                         preferences.DEFAULT_SCRIPT_TAB_STYLE)
        self.assertEqual(preferences.script_tab_style(),
                         preferences.DEFAULT_SCRIPT_TAB_STYLE)

    def test_script_tab_style_valid_values_round_trip(self):
        from mpynode.ui import preferences

        for style in preferences.VALID_SCRIPT_TAB_STYLES:
            preferences.set_pref("script_tab_style", style)
            self.assertEqual(preferences.script_tab_style(), style)

    def test_script_tab_style_invalid_falls_back_to_the_default(self):
        from mpynode.ui import preferences

        preferences.set_pref("script_tab_style", "garbage")
        self.assertEqual(preferences.script_tab_style(),
                         preferences.DEFAULT_SCRIPT_TAB_STYLE)

    def test_auto_recompile_default_false(self):
        from mpynode.ui import preferences

        self.assertFalse(preferences.get_pref("auto_recompile"))

    def test_auto_recompile_round_trips(self):
        from mpynode.ui import preferences

        preferences.set_pref("auto_recompile", True)
        self.assertTrue(preferences.get_pref("auto_recompile"))
        preferences.set_pref("auto_recompile", False)
        self.assertFalse(preferences.get_pref("auto_recompile"))

    def test_script_tab_style_keys_match_stylesheet_map(self):
        """The validated pref values and the stylesheet map keys must agree, or
        a selectable style would resolve to no stylesheet."""
        from mpynode.ui import preferences
        from mpynode.ui.widgets.script_tab_content import _OUTER_BAR_STYLES

        self.assertEqual(
            set(preferences.VALID_SCRIPT_TAB_STYLES),
            set(_OUTER_BAR_STYLES.keys()),
        )

    def test_template_search_paths_default_and_getter(self):
        from mpynode.ui import preferences

        # Key exists in DEFAULT_PREFS and defaults to a non-empty list.
        self.assertIn("template_search_paths", preferences.DEFAULT_PREFS)
        default = preferences.DEFAULT_PREFS["template_search_paths"]
        self.assertIsInstance(default, list)
        self.assertTrue(default)
        self.assertTrue(all(isinstance(p, str) for p in default))
        # The default path ends in the repo 'templates' dir.
        self.assertTrue(default[0].replace("\\", "/").rstrip("/").endswith("templates"))

        # Getter returns a list of strings.
        paths = preferences.template_search_paths()
        self.assertIsInstance(paths, list)
        self.assertTrue(all(isinstance(p, str) for p in paths))

        # A round-trip set/get of a custom list survives.
        preferences.set_pref("template_search_paths", ["/tmp/a", "/tmp/b"])
        preferences._reset_for_tests()
        self.assertEqual(
            preferences.get_pref("template_search_paths"), ["/tmp/a", "/tmp/b"]
        )
        self.assertEqual(preferences.template_search_paths(), ["/tmp/a", "/tmp/b"])

        # Empty / non-list stored value falls back to the default.
        preferences.set_pref("template_search_paths", [])
        self.assertEqual(
            preferences.template_search_paths(),
            preferences.DEFAULT_PREFS["template_search_paths"],
        )
        preferences.set_pref("template_search_paths", "not-a-list")
        self.assertEqual(
            preferences.template_search_paths(),
            preferences.DEFAULT_PREFS["template_search_paths"],
        )

    def test_init_show_header_pref_removed(self):
        """The old init-only checkbox pref is gone; new_node_mode replaces it."""
        from mpynode.ui import preferences

        self.assertNotIn("init_show_header", preferences.DEFAULT_PREFS)
        self.assertIn("new_node_mode", preferences.DEFAULT_PREFS)
        self.assertEqual(preferences.DEFAULT_PREFS["new_node_mode"], "headers")


# ===========================================================================
# editor_font helper (lazy QFont construction)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestEditorFontHelper(unittest.TestCase):
    def setUp(self):
        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_efont_")
        self._patches = [
            mock.patch.object(preferences, "PREFS_DIR", self._tmpdir),
            mock.patch.object(
                preferences,
                "PREFS_PATH",
                os.path.join(self._tmpdir, "preferences.json"),
            ),
        ]
        for p in self._patches:
            p.start()
        preferences._reset_for_tests()

    def tearDown(self):
        from mpynode.ui import preferences

        for p in self._patches:
            p.stop()
        preferences._reset_for_tests()
        try:
            for f in os.listdir(self._tmpdir):
                os.remove(os.path.join(self._tmpdir, f))
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def test_editor_font_uses_saved_values(self):
        from mpynode.ui import preferences

        preferences.set_pref("editor_font_family", "Menlo")
        preferences.set_pref("editor_font_size", 14)

        font = preferences.editor_font()
        self.assertEqual(font.family(), "Menlo")
        self.assertEqual(font.pointSize(), 14)

    def test_editor_font_handles_bad_size_gracefully(self):
        from mpynode.ui import preferences

        # Bad value in cache (sneak past set_pref via direct cache mut).
        preferences._ensure_loaded()
        preferences._cache["editor_font_size"] = "not_a_number"

        font = preferences.editor_font()
        # Should fall back to 10 instead of raising.
        self.assertEqual(font.pointSize(), 10)


# ===========================================================================
# Preferences dialog shape (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestPreferencesDialogShape(unittest.TestCase):
    def test_dialog_class_exists(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        for method in (
            "_build_ui",
            "_load_into_widgets",
            "_wire_signals",
            "_on_save_clicked",
            "_on_reset_clicked",
        ):
            self.assertTrue(
                hasattr(NDPreferencesDialog, method),
                f"NDPreferencesDialog should have {method}",
            )

    def test_save_uses_set_pref_for_all_known_keys(self):
        import inspect

        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        src = inspect.getsource(NDPreferencesDialog._on_save_clicked)
        for key in (
            "editor_font_family",
            "editor_font_size",
            "new_node_mode",
            "addattr_time_auto_connect",
            "connect_dialog_show_all_default",

            "connect_dialog_hide_pivots_default",
            "connect_dialog_sort_mode_default",
        ):
            self.assertIn(key, src, f"_on_save_clicked must persist {key}")
        self.assertIn("set_pref", src)

    def test_save_drops_legacy_init_show_header(self):
        import inspect

        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        src = inspect.getsource(NDPreferencesDialog._on_save_clicked)
        self.assertNotIn("init_show_header", src)

    def test_build_ui_has_new_nodes_page_with_mode_combo(self):
        import inspect

        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        src = inspect.getsource(NDPreferencesDialog._build_ui)
        self.assertIn("New Nodes", src)
        self.assertIn("_new_node_mode_combo", src)
        # The old init-only page + checkbox must be gone.
        self.assertNotIn("Init Tab", src)
        self.assertNotIn("_init_show_header_check", src)

    def test_reset_calls_reset_to_defaults(self):
        import inspect

        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        src = inspect.getsource(NDPreferencesDialog._on_reset_clicked)
        self.assertIn("reset_to_defaults", src)


# ===========================================================================
# New Nodes combo: live index<->value round-trip (not just source inspection)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestNewNodesComboRoundTrip(unittest.TestCase):
    """Build the real dialog and verify the new_node_mode combo's
    index<->value mapping round-trips for every mode (guards against a
    reorder/off-by-one in _NEW_NODE_MODE_OPTIONS silently saving the wrong
    mode)."""

    def setUp(self):
        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_combo_")
        self._patches = [
            mock.patch.object(preferences, "PREFS_DIR", self._tmpdir),
            mock.patch.object(
                preferences, "PREFS_PATH",
                os.path.join(self._tmpdir, "preferences.json"),
            ),
        ]
        for p in self._patches:
            p.start()
        preferences._reset_for_tests()

    def tearDown(self):
        from mpynode.ui import preferences
        import shutil

        for p in self._patches:
            p.stop()
        preferences._reset_for_tests()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_load_reflects_each_saved_mode(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        self.assertNotIn(
            "template", [v for _l, v in dlg._NEW_NODE_MODE_OPTIONS],
            "Template choice must be retired from the New Nodes combo",
        )
        opts = dict((v, i) for i, (_l, v) in enumerate(dlg._NEW_NODE_MODE_OPTIONS))
        for mode in ("none", "headers"):
            preferences.set_pref("new_node_mode", mode)
            dlg._load_into_widgets()
            self.assertEqual(
                dlg._new_node_mode_combo.currentIndex(), opts[mode],
                f"loading mode {mode!r} selected the wrong combo row",
            )

    def test_save_persists_selected_mode(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._font_size_edit.setText("10")  # _on_save_clicked validates this
        for _label, value in dlg._NEW_NODE_MODE_OPTIONS:
            idx = next(i for i, (_l, v) in enumerate(dlg._NEW_NODE_MODE_OPTIONS)
                       if v == value)
            dlg._new_node_mode_combo.setCurrentIndex(idx)
            dlg._on_save_clicked()
            self.assertEqual(preferences.new_node_mode(), value)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestTemplatePathsEditor(unittest.TestCase):
    """The 'New Nodes' page has a QListWidget path editor bound to the
    template_search_paths pref, with Add.../Remove buttons."""

    def setUp(self):
        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_paths_")
        self._patches = [
            mock.patch.object(preferences, "PREFS_DIR", self._tmpdir),
            mock.patch.object(
                preferences, "PREFS_PATH",
                os.path.join(self._tmpdir, "preferences.json"),
            ),
        ]
        for p in self._patches:
            p.start()
        preferences._reset_for_tests()

    def tearDown(self):
        from mpynode.ui import preferences
        import shutil

        for p in self._patches:
            p.stop()
        preferences._reset_for_tests()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _paths_in_widget(self, dlg):
        lw = dlg._template_paths_list
        return [lw.item(i).text() for i in range(lw.count())]

    def test_load_populates_path_list_from_pref(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        preferences.set_pref("template_search_paths", ["/tmp/one", "/tmp/two"])
        dlg = NDPreferencesDialog()  # __init__ calls _load_into_widgets
        self.assertTrue(hasattr(dlg, "_template_paths_list"))
        self.assertEqual(self._paths_in_widget(dlg), ["/tmp/one", "/tmp/two"])

    def test_add_and_remove_buttons_exist(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        self.assertTrue(hasattr(dlg, "_template_paths_add_btn"))
        self.assertTrue(hasattr(dlg, "_template_paths_remove_btn"))

    def test_save_persists_path_list(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        preferences.set_pref("template_search_paths", ["/tmp/one"])
        dlg = NDPreferencesDialog()
        dlg._font_size_edit.setText("10")  # _on_save_clicked validates this
        # Simulate the user adding a row and removing the original.
        dlg._template_paths_list.addItem("/tmp/two")
        dlg._template_paths_list.takeItem(0)  # drop "/tmp/one"
        dlg._on_save_clicked()
        self.assertEqual(
            preferences.get_pref("template_search_paths"), ["/tmp/two"]
        )

    def test_add_handler_appends_picked_dir(self):
        from unittest import mock as _mock
        from mpynode.ui.dialogs import preferences as prefs_dlg
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._template_paths_list.clear()
        with _mock.patch.object(
            prefs_dlg.QFileDialog, "getExistingDirectory",
            return_value="/tmp/picked",
        ):
            dlg._on_add_template_path()
            # A second add of the SAME dir must not duplicate.
            dlg._on_add_template_path()
        self.assertEqual(self._paths_in_widget(dlg), ["/tmp/picked"])

    def test_add_handler_noop_on_cancel(self):
        from unittest import mock as _mock
        from mpynode.ui.dialogs import preferences as prefs_dlg
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._template_paths_list.clear()
        with _mock.patch.object(
            prefs_dlg.QFileDialog, "getExistingDirectory", return_value=""
        ):
            dlg._on_add_template_path()
        self.assertEqual(self._paths_in_widget(dlg), [])

    def test_remove_handler_drops_selected_rows(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._template_paths_list.clear()
        for p in ("/tmp/a", "/tmp/b", "/tmp/c"):
            dlg._template_paths_list.addItem(p)
        dlg._template_paths_list.item(1).setSelected(True)  # "/tmp/b"
        dlg._on_remove_template_path()
        self.assertEqual(self._paths_in_widget(dlg), ["/tmp/a", "/tmp/c"])


# ===========================================================================
# File menu wires the dialog (was placeholder)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestOptimizeTimeoutPrefUI(unittest.TestCase):
    """#65: the preferences dialog exposes the AI-optimize timeout as an
    'AI Optimization' page -- an enable checkbox + a numeric seconds field --
    and round-trips both through set_pref (disabling removes the wall-clock cap
    via resolve_optimize_timeout -> inf)."""

    def setUp(self):
        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_opt_")
        self._patches = [
            mock.patch.object(preferences, "PREFS_DIR", self._tmpdir),
            mock.patch.object(
                preferences, "PREFS_PATH",
                os.path.join(self._tmpdir, "preferences.json"),
            ),
        ]
        for p in self._patches:
            p.start()
        preferences._reset_for_tests()

    def tearDown(self):
        from mpynode.ui import preferences
        import shutil

        for p in self._patches:
            p.stop()
        preferences._reset_for_tests()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_ai_optimization_page_widgets_exist(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        self.assertTrue(hasattr(dlg, "_optimize_timeout_check"))
        self.assertTrue(hasattr(dlg, "_optimize_timeout_edit"))

    def test_load_reflects_saved_values(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        preferences.set_pref("optimize_timeout_enabled", False)
        preferences.set_pref("optimize_timeout_seconds", 1234)
        dlg = NDPreferencesDialog()  # __init__ loads
        self.assertFalse(dlg._optimize_timeout_check.isChecked())
        self.assertEqual(dlg._optimize_timeout_edit.text().strip(), "1234")

    def test_save_persists_values(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._font_size_edit.setText("10")  # _on_save_clicked validates this
        dlg._optimize_timeout_check.setChecked(True)
        dlg._optimize_timeout_edit.setText("999")
        dlg._on_save_clicked()
        self.assertTrue(preferences.get_pref("optimize_timeout_enabled"))
        self.assertEqual(preferences.get_pref("optimize_timeout_seconds"), 999)
        self.assertEqual(preferences.resolve_optimize_timeout(), 999.0)

    def test_save_disabled_resolves_to_inf(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._font_size_edit.setText("10")
        dlg._optimize_timeout_check.setChecked(False)
        dlg._on_save_clicked()
        self.assertFalse(preferences.get_pref("optimize_timeout_enabled"))
        self.assertEqual(preferences.resolve_optimize_timeout(), float("inf"))

    def test_save_clamps_and_defaults_bad_seconds(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._font_size_edit.setText("10")
        # Non-numeric -> default 2400.
        dlg._optimize_timeout_edit.setText("abc")
        dlg._on_save_clicked()
        self.assertEqual(preferences.get_pref("optimize_timeout_seconds"), 2400)
        # Below the floor -> clamped to the minimum (10s).
        dlg._optimize_timeout_edit.setText("0")
        dlg._on_save_clicked()
        self.assertEqual(preferences.get_pref("optimize_timeout_seconds"), 10)

    def test_edit_disabled_when_check_off_on_load(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        preferences.set_pref("optimize_timeout_enabled", False)
        dlg = NDPreferencesDialog()  # __init__ loads
        self.assertFalse(dlg._optimize_timeout_edit.isEnabled())

    def test_edit_enabled_when_check_on_on_load(self):
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        preferences.set_pref("optimize_timeout_enabled", True)
        dlg = NDPreferencesDialog()
        self.assertTrue(dlg._optimize_timeout_edit.isEnabled())

    def test_toggling_check_locks_and_unlocks_edit(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        dlg = NDPreferencesDialog()
        dlg._optimize_timeout_check.setChecked(True)
        self.assertTrue(dlg._optimize_timeout_edit.isEnabled())
        dlg._optimize_timeout_check.setChecked(False)
        self.assertFalse(dlg._optimize_timeout_edit.isEnabled())

    def test_label_greys_with_edit(self):
        # The "Per AI call timeout (seconds):" caption must grey out too, not
        # just the entry field, so the disabled state reads clearly.
        from mpynode.ui import preferences
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        preferences.set_pref("optimize_timeout_enabled", False)
        dlg = NDPreferencesDialog()
        self.assertFalse(dlg._optimize_timeout_label.isEnabled())
        dlg._optimize_timeout_check.setChecked(True)
        self.assertTrue(dlg._optimize_timeout_label.isEnabled())
        dlg._optimize_timeout_check.setChecked(False)
        self.assertFalse(dlg._optimize_timeout_label.isEnabled())


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestMenuWiring(unittest.TestCase):
    def test_menu_handler_opens_NDPreferencesDialog(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._show_preferences_placeholder)
        self.assertIn("NDPreferencesDialog", src)


# ===========================================================================
# Consumer call-sites pull from preferences (was hard-coded)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestConsumersUsePrefs(unittest.TestCase):
    def test_addattr_time_subframe_reads_pref(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._make_time_subframe)
        self.assertIn("get_pref", src)
        self.assertIn("addattr_time_auto_connect", src)

    def test_connect_dialog_show_all_reads_pref(self):
        """Surfaced the pref key in the dialog source. The dialog now reads
        the new ``connect_dialog_hide_pivots_default`` pref. The legacy
        ``connect_dialog_show_all_default`` key is still defined for
        back-compat but no longer drives behavior."""
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        src = inspect.getsource(_BaseConnectDialog._build_ui)
        self.assertIn("get_pref", src)
        self.assertIn("connect_dialog_hide_pivots_default", src)

    def test_connect_dialog_sort_mode_reads_pref(self):
        """default sort mode is pref-driven."""
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        src = inspect.getsource(_BaseConnectDialog._initial_sort_mode)
        self.assertIn("get_pref", src)
        self.assertIn("connect_dialog_sort_mode_default", src)

    def test_editor_core_reads_pref(self):
        import inspect

        from mpynode.ui.widgets.editor_core import QtPythonEditor

        src = inspect.getsource(QtPythonEditor._initTextAttrs)
        self.assertIn("from mpynode.ui.preferences import", src)
        self.assertIn("editor_font", src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestLocationsPage(unittest.TestCase):
    """The Locations page: a read-only map of every resolved path, plus the one
    overridable field. The table exists because the resolution is four levels
    deep and nothing else in the UI shows which level won."""

    def setUp(self):
        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_loc_")
        self._patches = [
            mock.patch.object(preferences, "PREFS_DIR", self._tmpdir),
            mock.patch.object(
                preferences, "PREFS_PATH",
                os.path.join(self._tmpdir, "preferences.json"),
            ),
        ]
        for p in self._patches:
            p.start()
        preferences._reset_for_tests()

    def tearDown(self):
        from mpynode.ui import preferences
        import shutil

        for p in self._patches:
            p.stop()
        preferences._reset_for_tests()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _dlg(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        return NDPreferencesDialog()

    def test_the_page_is_registered_in_the_sidebar(self):
        dlg = self._dlg()
        labels = [dlg._category_list.item(i).text()
                  for i in range(dlg._category_list.count())]
        self.assertIn("Locations", labels)

    def test_the_table_names_every_resolved_location(self):
        dlg = self._dlg()
        tree = dlg._locations_tree
        names = [tree.topLevelItem(i).text(0)
                 for i in range(tree.topLevelItemCount())]
        for want in ("Data home", "Preferences", "Trust store",
                     "Type-id pins", "Port cache", "Compiled output"):
            self.assertIn(want, names)

    def test_every_row_carries_a_real_resolved_path(self):
        from mpynode._common import home

        dlg = self._dlg()
        tree = dlg._locations_tree
        by_name = {tree.topLevelItem(i).text(0): tree.topLevelItem(i)
                   for i in range(tree.topLevelItemCount())}
        # Asked of _common.home, never recomputed by the page.
        self.assertEqual(by_name["Data home"].text(3), home.home_dir())
        self.assertEqual(by_name["Trust store"].text(3),
                         home.trust_store_path())

    def test_the_override_round_trips_through_save(self):
        from mpynode.ui import preferences

        dlg = self._dlg()
        dlg._font_size_edit.setText("10")   # _on_save_clicked validates this
        target = os.path.join(self._tmpdir, "cache")
        dlg._port_cache_edit.setText(target)
        dlg._on_save_clicked()
        self.assertEqual(preferences.get_pref("port_cache_dir"), target)
        self.assertEqual(preferences.port_cache_dir_pref(), target)

    def test_blank_saves_as_fall_through(self):
        from mpynode.ui import preferences

        preferences.set_pref("port_cache_dir", "/somewhere")
        dlg = self._dlg()
        dlg._font_size_edit.setText("10")
        dlg._on_reset_port_cache()
        dlg._on_save_clicked()
        self.assertEqual(preferences.get_pref("port_cache_dir"), "")

    def test_an_env_override_disables_the_field_and_says_so(self):
        """Silently accepting a value that is then ignored is the failure this
        page exists to prevent."""
        with mock.patch.dict(os.environ,
                             {"MPYNODE_PORT_CACHE": os.sep + "from_env"}):
            dlg = self._dlg()
            self.assertFalse(dlg._port_cache_edit.isEnabled())
            self.assertFalse(dlg._port_cache_browse_btn.isEnabled())
            note = dlg._port_cache_note.text()
            self.assertIn("MPYNODE_PORT_CACHE", note)
            self.assertIn(os.sep + "from_env", note)

    def test_a_foreign_os_path_warns_while_typing(self):
        dlg = self._dlg()
        with mock.patch.object(os, "name", "posix"):
            dlg._port_cache_edit.setText(r"C:\Users\bob\cache")
            self.assertIn("another operating system",
                          dlg._port_cache_note.text())

    def test_a_normal_path_shows_no_warning(self):
        dlg = self._dlg()
        dlg._port_cache_edit.setText(os.path.join(self._tmpdir, "cache"))
        self.assertEqual(dlg._port_cache_note.text(), "")

    def test_typing_does_not_rebuild_the_table(self):
        """The table runs a real WRITE PROBE per row (os.access lies under
        macOS App Management), so rebuilding it on textChanged would be six
        file writes per character typed."""
        from mpynode.ui.dialogs import preferences as dlg_mod

        dlg = self._dlg()
        with mock.patch.object(dlg_mod, "_writable_label",
                               return_value="yes") as probe:
            dlg._port_cache_edit.setText("/some/path/being/typed")
            self.assertEqual(
                probe.call_count, 0,
                "typing must refresh the note only, never the table")
        # ...but the note DID update.
        self.assertIsNotNone(dlg._port_cache_note.text())


class TestPortCacheDirPref(unittest.TestCase):
    """The port-cache override and its OS-sanity guard.

    ``preferences.json`` travels -- a studio network home mounted by both a Mac
    and a Windows box is ordinary -- and an absolute path is the one pref value
    that cannot survive the trip. A foreign-OS value must read as UNSET so the
    machine falls back to its own correct default, rather than being handed a
    path that can never exist.

    ``get_pref`` is patched directly rather than going through a temp prefs
    file: what is under test is the guard, not persistence.
    """

    def _with(self, value):
        from mpynode.ui import preferences

        return mock.patch.object(
            preferences, "get_pref",
            lambda k, d=None: value if k == "port_cache_dir" else d)

    # -- the guard itself ---------------------------------------------------

    def test_relative_paths_are_never_foreign(self):
        from mpynode.ui import preferences

        for p in ("cache", "./cache", "../cache", "a/b"):
            self.assertFalse(preferences.is_foreign_os_path(p), p)

    def test_blank_is_not_foreign(self):
        from mpynode.ui import preferences

        self.assertFalse(preferences.is_foreign_os_path(""))
        self.assertFalse(preferences.is_foreign_os_path("   "))

    def test_windows_paths_are_foreign_on_posix(self):
        from mpynode.ui import preferences

        with mock.patch.object(os, "name", "posix"):
            for p in (r"C:\Users\bob\cache", "C:/Users/bob/cache",
                      r"d:\cache", r"\\server\share\cache"):
                self.assertTrue(preferences.is_foreign_os_path(p), p)
            self.assertFalse(
                preferences.is_foreign_os_path("/Users/bob/cache"))

    def test_posix_paths_are_foreign_on_windows(self):
        from mpynode.ui import preferences

        with mock.patch.object(os, "name", "nt"):
            self.assertTrue(preferences.is_foreign_os_path("/Users/bob/cache"))
            self.assertTrue(preferences.is_foreign_os_path("/tmp/x"))
            # ...while real Windows paths, either slash style, are fine.
            for p in (r"C:\Users\bob\cache", "C:/Users/bob/cache",
                      r"\\server\share\cache"):
                self.assertFalse(preferences.is_foreign_os_path(p), p)

    # -- the accessor -------------------------------------------------------

    def test_default_is_blank_meaning_fall_through(self):
        from mpynode.ui import preferences

        self.assertEqual(preferences.DEFAULT_PREFS["port_cache_dir"], "")

    def test_blank_and_non_string_read_as_unset(self):
        from mpynode.ui import preferences

        for value in ("", "   ", None, 42, ["/tmp/x"]):
            with self._with(value):
                self.assertEqual(preferences.port_cache_dir_pref(), "")

    def test_a_usable_value_is_expanded(self):
        from mpynode.ui import preferences

        with self._with("~/somewhere/cache"):
            got = preferences.port_cache_dir_pref()
        self.assertTrue(got)
        self.assertNotIn("~", got)
        self.assertTrue(got.endswith(os.path.join("somewhere", "cache")))

    def test_a_foreign_value_reads_as_unset(self):
        from mpynode.ui import preferences

        with mock.patch.object(os, "name", "posix"):
            with self._with(r"C:\Users\bob\cache"):
                self.assertEqual(preferences.port_cache_dir_pref(), "")


if __name__ == "__main__":
    unittest.main()
