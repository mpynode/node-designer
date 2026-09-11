"""The editor font preference: platform default + installed families only.

The shipped family is the platform's own monospace -- Consolas on Windows,
Monaco on macOS, DejaVu Sans Mono elsewhere -- never "Courier", which Windows
only has as a raster alias. The Preferences list offers installed fixed-pitch
families only (it used to be eight hard-coded names in an editable combo), and
a saved family this machine lacks resolves to the default.

Qt's OFFSCREEN platform carries no system fonts (its FreeType database scans
only QT_QPA_FONTDIR), so under mayapy the real database is empty and the code
degrades to "Qt cannot tell". The filtering and resolution rules are therefore
pinned against a FAKE database; one live test checks the degrade itself.

Importing the dialog pulls Qt, so create a QApplication at IMPORT time (before
maya.standalone installs a non-GUI QCoreApplication). Mirrors the other UI test
modules.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest import mock

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-editor-font-test"])

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


_FAKE_FAMILIES = ["Zebra Sans", "Consolas", "Arial", "Courier New", "Monaco"]
_FAKE_MONO     = {"Consolas", "Courier New", "Monaco"}


def _fake_db():
    return (lambda: list(_FAKE_FAMILIES)), (lambda f: f in _FAKE_MONO)


class _FakeFontDatabase:
    """Swap the Qt font database for a known one and clear the session cache
    on both sides, so the lists are rebuilt from the fake and the real one is
    rebuilt afterwards."""

    def __init__(self, db=_fake_db):
        self._db = db

    def __enter__(self):
        from mpynode.ui import preferences

        preferences._FAMILY_CACHE.clear()
        self._patch = mock.patch.object(preferences, "_font_db", self._db)
        self._patch.start()
        return preferences

    def __exit__(self, *exc):
        from mpynode.ui import preferences

        self._patch.stop()
        preferences._FAMILY_CACHE.clear()
        return False


class TestPlatformDefault(unittest.TestCase):
    def test_one_family_per_platform(self):
        from mpynode.ui import preferences

        self.assertEqual(preferences.default_editor_font_family("win32"), "Consolas")
        self.assertEqual(preferences.default_editor_font_family("darwin"), "Monaco")
        self.assertEqual(preferences.default_editor_font_family("linux"),
                         "DejaVu Sans Mono")

    def test_the_shipped_default_and_the_editor_fallback_agree(self):
        from mpynode.ui import preferences
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        want = preferences.default_editor_font_family()
        self.assertEqual(preferences.DEFAULT_PREFS["editor_font_family"], want)
        self.assertEqual(QtPythonEditor.DEFAULT_FONT_FAMILY, want)
        self.assertNotEqual(want, "Courier")


class TestInstalledFamilies(unittest.TestCase):
    def test_monospace_list_is_the_installed_fixed_pitch_subset_sorted(self):
        with _FakeFontDatabase() as p:
            self.assertEqual(p.installed_font_families(),
                             sorted(_FAKE_FAMILIES))
            self.assertEqual(p.installed_monospace_families(),
                             ["Consolas", "Courier New", "Monaco"])

    def test_no_fixed_pitch_classification_offers_every_installed_family(self):
        with _FakeFontDatabase(lambda: ((lambda: list(_FAKE_FAMILIES)),
                                        (lambda f: False))) as p:
            self.assertEqual(p.installed_monospace_families(),
                             sorted(_FAKE_FAMILIES))

    def test_a_saved_family_the_machine_lacks_resolves_to_the_default(self):
        with _FakeFontDatabase() as p:
            self.assertEqual(p.resolve_editor_font_family("No Such Font 123"),
                             p.default_editor_font_family())
            self.assertEqual(p.resolve_editor_font_family(""),
                             p.default_editor_font_family())
            # Installed stays, fixed pitch or not: the user chose it.
            self.assertEqual(p.resolve_editor_font_family("Arial"), "Arial")
            self.assertEqual(p.resolve_editor_font_family("Consolas"), "Consolas")

    def test_without_a_font_database_the_saved_family_is_kept(self):
        # "Qt cannot tell" must never override a choice -- the offscreen
        # platform and a headless mayapy both land here.
        with _FakeFontDatabase(lambda: None) as p:
            self.assertEqual(p.installed_font_families(),           [])
            self.assertEqual(p.installed_monospace_families(),      [])
            self.assertEqual(p.resolve_editor_font_family("Menlo"), "Menlo")
            self.assertEqual(p.resolve_editor_font_family(""),
                             p.default_editor_font_family())

    def test_live_database_lists_are_consistent(self):
        # Whatever THIS Qt reports (nothing, offscreen): the monospace list is a
        # subset of the installed list and both are sorted.
        from mpynode.ui import preferences

        preferences._FAMILY_CACHE.clear()
        try:
            installed = preferences.installed_font_families()
            mono      = preferences.installed_monospace_families()
            self.assertTrue(set(mono) <= set(installed))
            self.assertEqual(installed, sorted(installed))
            self.assertEqual(mono, sorted(mono))
        finally:
            preferences._FAMILY_CACHE.clear()


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestDialogFontList(unittest.TestCase):
    def _dialog(self):
        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        return NDPreferencesDialog()

    def _offered(self, combo):
        return [combo.itemText(i) for i in range(combo.count())]

    def test_maya_default_saves_the_empty_family_and_reads_back(self):
        # Index 0 is the empty preference: the platform's own monospace
        # (Consolas / Monaco), which stays the shipped default. An explicit
        # pick still saves the family itself.
        with _FakeFontDatabase() as p:
            dlg = self._dialog()
            try:
                dlg._load_into_widgets()
                dlg._font_family_combo.setCurrentIndex(0)
                dlg._on_save_clicked()
                self.assertEqual(p.get_pref("editor_font_family"), "")
                self.assertEqual(p.resolve_editor_font_family(""),
                                 p.default_editor_font_family())
                self.assertEqual(p.editor_font().family(),
                                 p.default_editor_font_family())
                dlg._load_into_widgets()
                self.assertEqual(dlg._font_family_combo.currentIndex(), 0)
                self.assertEqual(dlg._font_family_combo.currentText(),
                                 p.UI_FONT_DEFAULT_LABEL)
                dlg._font_family_combo.setCurrentIndex(
                    dlg._font_family_combo.findText("Courier New"))
                dlg._on_save_clicked()
                self.assertEqual(p.get_pref("editor_font_family"), "Courier New")
                dlg._load_into_widgets()
                self.assertEqual(dlg._font_family_combo.currentText(), "Courier New")
            finally:
                dlg.deleteLater()

    def test_offers_installed_fixed_pitch_fonts_only_and_is_not_editable(self):
        with _FakeFontDatabase() as p:
            dlg = self._dialog()
            try:
                combo = dlg._font_family_combo
                self.assertFalse(combo.isEditable())
                self.assertEqual(self._offered(combo),
                                 [p.UI_FONT_DEFAULT_LABEL,
                                  "Consolas", "Courier New", "Monaco"])
            finally:
                dlg.deleteLater()
            del p

    def test_a_saved_family_the_machine_lacks_loads_as_the_default(self):
        with _FakeFontDatabase() as p:
            saved = p.get_pref("editor_font_family")
            dlg   = self._dialog()
            try:
                p.set_pref("editor_font_family", "No Such Font 123")
                dlg._load_into_widgets()
                self.assertEqual(dlg._font_family_combo.currentText(),
                                 p.default_editor_font_family())
            finally:
                p.set_pref("editor_font_family", saved)
                dlg.deleteLater()

    def test_an_installed_proportional_choice_is_offered_and_selected(self):
        # Installed but not fixed pitch: not in the list by default, yet the
        # user's own saved choice must show as what it is, not as a substitute.
        with _FakeFontDatabase() as p:
            saved = p.get_pref("editor_font_family")
            dlg   = self._dialog()
            try:
                p.set_pref("editor_font_family", "Arial")
                dlg._load_into_widgets()
                self.assertEqual(dlg._font_family_combo.currentText(), "Arial")
                self.assertIn("Arial", self._offered(dlg._font_family_combo))
            finally:
                p.set_pref("editor_font_family", saved)
                dlg.deleteLater()

    def test_without_a_font_database_the_default_is_offered(self):
        with _FakeFontDatabase(lambda: None) as p:
            dlg = self._dialog()
            try:
                self.assertIn(p.default_editor_font_family(),
                              self._offered(dlg._font_family_combo))
            finally:
                dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
