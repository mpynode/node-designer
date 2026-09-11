"""A Class change re-bakes the Outline and the API view at once.

Both views print the Class (``class Foo(MPyLocator):`` / ``CLASS · Foo``) and
both used to re-bake only when the API tab came forward, so a rename showed
there one tab-click late and a clear not at all. ``refreshIdentityViews`` does
exactly those two views -- NOT the expression editors, whose refresh resets the
dirty baseline and would discard typed-but-unsaved code.

Importing the widgets pulls Qt, so create a QApplication at IMPORT time (before
maya.standalone installs a non-GUI QCoreApplication). Mirrors the other UI test
modules.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-class-views-test"])

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _section_titles(navigator):
    tree = navigator._tree
    return [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())]


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestRefreshIdentityViews(unittest.TestCase):
    def _content(self, name, cls):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name=name)
        loc.set_py_class("mpynode_user.%s" % cls)
        return loc, NDScriptTabContent(loc)

    def test_rename_reaches_both_views_without_a_tab_switch(self):
        loc, w = self._content("cvRename", "OldName")
        try:
            self.assertIn("class OldName(", w._api_view.source())
            self.assertTrue(any("OldName" in t for t in _section_titles(w._navigator)))
            loc.set_py_class("mpynode_user.NewName")
            w.refreshIdentityViews()
            self.assertIn("class NewName(", w._api_view.source())
            self.assertNotIn("class OldName(", w._api_view.source())
            self.assertTrue(any("NewName" in t for t in _section_titles(w._navigator)))
        finally:
            w.deleteLater()

    def test_clear_reaches_both_views(self):
        loc, w = self._content("cvClear", "Gone")
        try:
            loc.clear_py_class()
            w.refreshIdentityViews()
            # Class-less bakes under the root wrapper's own name.
            self.assertIn("class MPyLocator(MPyLocator):", w._api_view.source())
            self.assertFalse(any("Gone" in t for t in _section_titles(w._navigator)))
        finally:
            w.deleteLater()

    def test_unsaved_expression_edits_survive(self):
        loc, w = self._content("cvDirty", "Keep")
        try:
            w._expr_editor.setText("self.x = 1  # not saved yet\n")
            self.assertTrue(w.hasUnsavedChanges())
            loc.set_py_class("mpynode_user.Kept")
            w.refreshIdentityViews()
            self.assertTrue(w.hasUnsavedChanges(),
                            "a Class change must not reset the editors")
            self.assertIn("not saved yet", w._expr_editor.getText())
        finally:
            w.deleteLater()


@unittest.skipIf(_QAPP is None, "no Qt available")
class TestTabWidgetRoutesByNode(unittest.TestCase):
    def test_only_the_named_nodes_tabs_are_refreshed(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        mc.file(new=True, force=True)
        a = MPyLocator.create(name="cvTabA")
        b = MPyLocator.create(name="cvTabB")
        a.set_py_class("mpynode_user.Alpha")
        tabs = NDScriptTabWidget()
        try:
            tabs.addOrRaiseTab(a)
            tabs.addOrRaiseTab(b)
            a.set_py_class("mpynode_user.Beta")
            self.assertEqual(tabs.refreshIdentityViewsForNode(a.get_name()), 1)
            self.assertEqual(tabs.refreshIdentityViewsForNode("noSuchNode"), 0)
            content = tabs.widget(tabs.getIndexOfNode(a))
            self.assertIn("class Beta(", content._api_view.source())
        finally:
            tabs.deleteLater()


if __name__ == "__main__":
    unittest.main()
