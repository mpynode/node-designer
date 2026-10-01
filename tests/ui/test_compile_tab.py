"""The Compile tab: the Designer's third mode page hosts the CompileDialog as
a plain child widget, every entry point lands on it, and the compiled pane is
the picker embedded over the node table.

Design: ``docs/notes/native-source-design.md`` §5 (embed, don't extract: the
dialog's methods stay where the other test modules pin them). Constructs the
real ``CompileDialog``, so a GUI QApplication must exist at IMPORT time --
mirrors the other compile-dialog test modules.
"""

from __future__ import annotations

import inspect
import json
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-compile-tab-test"])

from tests._setup import standalone_init
from tests.compile.pipeline.test_native_bundle import _src, _write


def setUpModule():
    standalone_init()


def _plugin_tree(root, plugin, node, cls, tid):
    _write(root, "%s/build/manifest.json" % plugin, json.dumps({
        "plugin_name": plugin, "porter_recipe_version": "36",
        "nodes": [{"type_name": node, "type_id": tid, "build_status": "compiled"}]}))
    return _write(root, "%s/build/source/%s.cpp" % (plugin, node), _src(node, cls, tid))


# ---------------------------------------------------------------------------
# The Designer: a third mode page, and the launcher that lands on it
# ---------------------------------------------------------------------------

class TestDesignerHasACompileTab(unittest.TestCase):

    def test_the_mode_switcher_has_three_pages(self):
        from mpynode.ui import node_designer

        src = inspect.getsource(node_designer.NDMainWindow._build_ui)
        self.assertIn('addTab(workspace, "Workspace")', src)
        self.assertIn('addTab(self._gallery_panel, "Templates")', src)
        self.assertIn('addTab(self._compile_page, "Compile")', src)

    def test_the_launcher_switches_to_the_page_and_never_execs(self):
        from mpynode.ui import node_designer

        src = inspect.getsource(node_designer.NDMainWindow._open_compile_dialog)
        self.assertIn("_show_compile_mode", src)
        self.assertIn("refresh_nodes", src)
        self.assertNotIn("exec_", src)
        # Built once, by _ensure_compile_dialog -- never a second window.
        self.assertNotIn("CompileDialog(", src)

    def test_the_dialog_is_built_embedded(self):
        from mpynode.ui import node_designer

        src = inspect.getsource(node_designer.NDMainWindow._ensure_compile_dialog)
        self.assertIn("embedded=True", src)
        self.assertIn("handoffToAssistant", src)
        self.assertIn("classesStamped", src)

    def test_closing_the_window_closes_the_embedded_dialog(self):
        from mpynode.ui import node_designer

        src = inspect.getsource(node_designer.NDMainWindow.closeEvent)
        self.assertIn("_compile_dialog.close()", src)


class _FakeDialog:
    def __init__(self):
        self.calls = []

    def refresh_nodes(self):
        self.calls.append("refresh")

    def preselect_node(self, name):
        self.calls.append(("preselect", name))

    def add_compiled_sources(self, paths):
        self.calls.append(("compiled", list(paths)))
        return list(paths), []

    def rescan_scene(self):
        self.calls.append("rescan")


class _FakeWindow:
    """Only what _open_compile_dialog / _on_compile_tab_shown touch."""

    def __init__(self):
        self.dlg   = _FakeDialog()
        self.shown = 0
        self._compile_tab_switching = False

    def _ensure_compile_dialog(self):
        return self.dlg

    def _show_compile_mode(self):
        self.shown += 1


class TestEntryPoints(unittest.TestCase):

    def _open(self, **kw):
        from mpynode.ui.node_designer import NDMainWindow

        w = _FakeWindow()
        NDMainWindow._open_compile_dialog(w, **kw)
        return w

    def test_a_plain_open_is_a_fresh_open(self):
        w = self._open()
        self.assertEqual(w.dlg.calls, ["refresh"])
        self.assertEqual(w.shown, 1)

    def test_the_scene_tree_preselects_after_the_refresh(self):
        w = self._open(preselect="bubbleSort1")
        self.assertEqual(w.dlg.calls, ["refresh", ("preselect", "bubbleSort1")])
        self.assertEqual(w.shown, 1)

    def test_add_to_bundle_adds_to_what_the_page_holds(self):
        # The gallery's action is additive: no reset between two templates.
        w = self._open(compiled=["/x/a.mpn"])
        self.assertEqual(w.dlg.calls, [("compiled", ["/x/a.mpn"])])
        self.assertEqual(w.shown, 1)

    def test_a_users_return_to_the_tab_rescans_and_keeps_the_session(self):
        from mpynode.ui.node_designer import NDMainWindow

        w = _FakeWindow()
        NDMainWindow._on_compile_tab_shown(w)
        self.assertEqual(w.dlg.calls, ["rescan"])
        # ...but a switch made by the launcher is not a user's return.
        w.dlg.calls.clear()
        w._compile_tab_switching = True
        NDMainWindow._on_compile_tab_shown(w)
        self.assertEqual(w.dlg.calls, [])


class _FakePanel:
    def __init__(self):
        self.seen = []

    def setVisible(self, on):
        pass

    def raise_(self):
        pass

    def seed_compile_context(self, handoff):
        self.seen.append(handoff)


class TestFixWithAiHandOff(unittest.TestCase):

    def test_a_hand_off_from_the_compile_tab_shows_the_workspace(self):
        # The assistant lives on the Workspace page: seeding it while the
        # Compile page is up fills a panel nobody can see.
        from mpynode.ui.node_designer import NDMainWindow

        w                   = mock.Mock()
        w._assistant_panel  = _FakePanel()
        w._reveal_assistant = lambda: NDMainWindow._reveal_assistant(w)
        NDMainWindow._route_compile_handoff(w, {"node": "x"})
        w._show_workspace_mode.assert_called_once_with()
        self.assertEqual(w._assistant_panel.seen, [{"node": "x"}])


# ---------------------------------------------------------------------------
# The dialog, embedded
# ---------------------------------------------------------------------------

@unittest.skipIf(_QApp is None, "no Qt")
class TestEmbeddedDialog(unittest.TestCase):

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        self.d = tempfile.mkdtemp(prefix="tab_dlg_")
        self.a = _plugin_tree(self.d, "plugA", "aNode", "ANode", "0x00081000")

    def test_embedded_is_a_child_widget_with_no_close_button(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog
        from mpynode.ui.qt_wrapper import QWidget

        host = QWidget()
        self.addCleanup(host.deleteLater)
        dlg = CompileDialog(parent=host, embedded=True)
        self.assertFalse(dlg.isWindow())
        self.assertTrue(dlg._close_btn.isHidden())

    def test_standalone_stays_a_window_with_a_close_button(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        dlg = CompileDialog()
        self.addCleanup(dlg.close)
        self.assertTrue(dlg.isWindow())
        self.assertFalse(dlg._close_btn.isHidden())

    def test_rescan_keeps_the_session_where_a_fresh_open_resets_it(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        dlg = CompileDialog()
        self.addCleanup(dlg.close)
        dlg.add_compiled_sources([self.a])
        dlg.rescan_scene()
        self.assertIn("aNode", dlg._compiled_rows)
        self.assertIn("aNode", dlg._checked)
        dlg.refresh_nodes()
        self.assertEqual(dlg._compiled_rows, {})


    def test_the_compiled_pane_is_the_picker_embedded_over_the_table(self):
        from mpynode.ui.dialogs import compiled_node_picker
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        dlg = CompileDialog()
        self.addCleanup(dlg.close)
        self.assertIsNone(dlg._compiled_pane)
        self.assertTrue(dlg._compiled_pane_host.isHidden())
        with mock.patch.object(compiled_node_picker, "default_roots",
                               return_value=[self.d]):
            dlg._add_compiled_btn.setChecked(True)
            dlg._on_add_compiled()
        pane = dlg._compiled_pane
        self.assertIsNotNone(pane)
        self.assertFalse(pane.isWindow())
        self.assertIsNone(pane._buttons)
        self.assertFalse(dlg._compiled_pane_host.isHidden())
        self.assertEqual([m.node for m in pane._members], ["aNode"])
        # "Add Selected" puts the checked ones in the table, then clears.
        pane._set_all(True)
        self.assertTrue(pane._add_btn.isEnabled())
        pane._add_btn.click()
        self.assertIn("aNode", dlg._compiled_rows)
        self.assertEqual(pane.selected_paths(), [])
        # The same button hides the pane again.
        dlg._add_compiled_btn.setChecked(False)
        dlg._on_add_compiled()
        self.assertTrue(dlg._compiled_pane_host.isHidden())

    def test_nothing_is_added_while_a_compile_runs(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        dlg = CompileDialog()
        self.addCleanup(dlg.close)
        dlg._busy = True
        added, problems = dlg.add_compiled_sources([self.a])
        self.assertEqual(added, [])
        self.assertEqual(len(problems), 1)
        self.assertEqual(dlg._compiled_rows, {})


if __name__ == "__main__":
    unittest.main()
