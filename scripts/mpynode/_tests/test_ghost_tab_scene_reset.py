"""Ghost editor-tab after a scene reset must not survive.

Reported bug: a Python spine node was open in the Node Designer; a File>Open
then reset the scene (the Scene tab -- left, ``NDSceneTree`` -- self-healed to
EMPTY) but a right-side editor tab stayed open showing the old node's expression
code, which no live scene node backed. Root cause: the right editor tabs
(``NDScriptTabContent``) identified their node only by a cached NAME string, and
the reopen prune used ``mc.objExists(name)`` -- fooled by a same-named node in a
freshly loaded scene -- while the scene-change handler used a raw ``removeTab``
loop that never fired ``tabsChanged``.

Fix under test:
  * ``NDScriptTabContent`` captures an ``MObjectHandle`` at construction and
    exposes ``isBackingNodeAlive()`` (tri-state True / False / None).
  * ``NDScriptTabWidget.closeAllTabs()`` (scene reset) and
    ``pruneStaleTabs()`` (reopen) close tabs by that handle, not by name, and
    each fires ``tabsChanged`` once.
  * ``NDMainWindow._handle_scene_change`` -> ``closeAllTabs``;
    ``_handle_reopen`` -> ``pruneStaleTabs``.

Coverage:
  * behavioral -- the tab widget + content widget construct fine in mayapy
    (per test_middle_click_select), so the prune/close/liveness paths run
    against real nodes and a real File>New;
  * structure -- the window-level WIRING (the full NDMainWindow is unreliable to
    instantiate in mayapy) via inspect.getsource, same as the sibling tests.
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
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-ghosttab-test"])

import inspect
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


# ===========================================================================
# Behavioral: real tab widget + real nodes + a real File>New
# ===========================================================================


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestPruneAndCloseTabs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    def _new_node(self, name):
        from mpynode.wrappers._mpy_node import MPyNode

        return MPyNode.create(name=name)

    def _tab_widget(self, *nodes):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        w = NDScriptTabWidget()
        self._widgets.append(w)
        for n in nodes:
            w.addOrRaiseTab(n)
        return w

    # -- isBackingNodeAlive tri-state -----------------------------------

    def test_backing_node_alive_true_then_false_after_file_new(self):
        node = self._new_node("ghostAlive")
        w = self._tab_widget(node)
        content = w.widget(0)
        self.assertTrue(
            content.isBackingNodeAlive(),
            "a freshly opened node's tab must report alive")
        mc.file(new=True, force=True)
        self.assertFalse(
            content.isBackingNodeAlive(),
            "after File>New the node is gone -> tab must report NOT alive")

    def test_backing_node_alive_none_when_no_handle(self):
        node = self._new_node("ghostNoHandle")
        w = self._tab_widget(node)
        content = w.widget(0)
        content._node_handle = None  # simulate an unresolvable handle
        self.assertIsNone(
            content.isBackingNodeAlive(),
            "no handle -> UNKNOWN (None), never a hard True/False guess")

    # -- pruneStaleTabs -------------------------------------------------

    def test_prune_removes_tab_after_file_new(self):
        node = self._new_node("ghostPrune")
        w = self._tab_widget(node)
        self.assertEqual(w.count(), 1)
        mc.file(new=True, force=True)
        pruned = w.pruneStaleTabs()
        self.assertEqual(w.count(), 0, "stale tab must be pruned")
        self.assertEqual(pruned, ["ghostPrune"])

    def test_prune_keeps_live_tab_on_unchanged_scene(self):
        """Reopen on the SAME scene: the node still exists -> tab survives, and
        no tabsChanged is emitted (nothing changed)."""
        node = self._new_node("liveKeep")
        w = self._tab_widget(node)
        emitted = []
        w.tabsChanged.connect(emitted.append)
        pruned = w.pruneStaleTabs()
        self.assertEqual(w.count(), 1, "a live node's tab must be kept")
        self.assertEqual(pruned, [])
        self.assertEqual(emitted, [], "no prune -> no tabsChanged")

    def test_prune_survives_same_named_replacement_node(self):
        """THE regression guard. A File>New wipes the scene, then a DIFFERENT
        node is created with the SAME name. The old objExists(name) check saw
        the name exist and left a ghost tab; the MObjectHandle check prunes it
        because the ORIGINAL object is gone."""
        node = self._new_node("collideName")
        w = self._tab_widget(node)
        mc.file(new=True, force=True)
        # A brand-new, unrelated node that happens to reuse the name.
        replacement = self._new_node("collideName")
        self.assertEqual(replacement.get_name(), "collideName")
        pruned = w.pruneStaleTabs()
        self.assertEqual(
            w.count(), 0,
            "a same-named replacement must NOT rescue the stale tab")
        self.assertEqual(pruned, ["collideName"])

    def test_prune_emits_tabschanged_once(self):
        n1 = self._new_node("pruneEmitA")
        n2 = self._new_node("pruneEmitB")
        w = self._tab_widget(n1, n2)
        emitted = []
        w.tabsChanged.connect(emitted.append)
        mc.file(new=True, force=True)
        w.pruneStaleTabs()
        self.assertEqual(
            len(emitted), 1,
            "pruning any number of tabs must fire tabsChanged exactly once")
        self.assertEqual(emitted[0], [], "no tabs remain after a full prune")

    # -- closeAllTabs ---------------------------------------------------

    def test_close_all_tabs_closes_everything_and_emits_once(self):
        n1 = self._new_node("closeAllA")
        n2 = self._new_node("closeAllB")
        w = self._tab_widget(n1, n2)
        self.assertEqual(w.count(), 2)
        emitted = []
        w.tabsChanged.connect(emitted.append)
        closed = w.closeAllTabs()
        self.assertEqual(closed, 2)
        self.assertEqual(w.count(), 0)
        self.assertEqual(
            len(emitted), 1, "closeAllTabs must fire tabsChanged exactly once")
        self.assertEqual(emitted[0], [])

    def test_close_all_tabs_noop_when_empty(self):
        w = self._tab_widget()
        emitted = []
        w.tabsChanged.connect(emitted.append)
        closed = w.closeAllTabs()
        self.assertEqual(closed, 0)
        self.assertEqual(emitted, [], "no tabs -> no tabsChanged")


# ===========================================================================
# Structure: the window-level wiring (inspect-based -- the full NDMainWindow is
# unreliable to instantiate in mayapy, per test_designer_window).
# ===========================================================================


class TestSceneResetWiring(unittest.TestCase):
    def _m(self):
        from mpynode.ui import mpynode_designer as m

        return m

    def test_tab_widget_has_new_api(self):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        for attr in ("closeAllTabs", "pruneStaleTabs"):
            self.assertTrue(
                hasattr(NDScriptTabWidget, attr),
                f"NDScriptTabWidget must define {attr}")

    def test_content_has_liveness_api(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        self.assertTrue(hasattr(NDScriptTabContent, "isBackingNodeAlive"))

    def test_scene_change_uses_close_all_tabs(self):
        m = self._m()
        src = inspect.getsource(m.NDMainWindow._handle_scene_change)
        self.assertIn("closeAllTabs", src)
        # the fragile raw removeTab loop is gone (the widget owns removal now).
        self.assertNotIn(".removeTab(", src)

    def test_reopen_uses_prune_stale_tabs(self):
        m = self._m()
        src = inspect.getsource(m.NDMainWindow._handle_reopen)
        self.assertIn("pruneStaleTabs", src)
        # the name-based objExists prune is gone from the tab-pruning path.
        self.assertNotIn("objExists(node_name)", src)


if __name__ == "__main__":
    unittest.main()
