"""CompileDialog "Fix with AI" concierge button (WS2).

Proves the dialog:
  * hides the AI button by default,
  * shows it after a finish that has a dropped/diverged node (via
    ``_update_ai_button``), and hides it when everything is clean,
  * emits ``handoffToAssistant`` with a compile_bridge hand-off when the button
    is clicked, carrying the flagged node(s).

The signal EMISSION is what's testable headlessly; the designer-side routing to
the assistant panel is verified separately (test_assistant_compile_seed).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

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
    _QAPP = _QApplication.instance() or _QApplication(["compile-ai-handoff-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _result(nodes, ok=True):
    return {
        "ok":          ok,
        "plugin_name": "myPlugin",
        "bundle_path": "/tmp/out/myPlugin.bundle" if ok else None,
        "nodes":       nodes,
        "errors":      [],
    }


def _row(type_name, build_status, verify=None):
    return {
        "source_node":  type_name + "1",
        "type_name":    type_name,
        "build_status": build_status,
        "build_reason": "",
        "verify": verify or {"ran": False, "pass": None, "maxerr": None,
                             "tol": None, "reason": ""},
        "spec": {"portability": {"blockers": []}},
    }


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestCompileDialogAIHandoff(unittest.TestCase):
    def _dialog(self):
        import maya.cmds as mc
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        mc.file(new=True, force=True)
        return CompileDialog()

    def test_ai_button_hidden_by_default(self):
        dlg = self._dialog()
        try:
            self.assertFalse(dlg._ai_btn.isVisible())
        finally:
            dlg.deleteLater()

    def test_update_shows_button_on_dropped_node(self):
        dlg = self._dialog()
        try:
            dlg.show()
            res = _result([_row("okNode", "compiled",
                                {"ran": True, "pass": True, "maxerr": 0.0,
                                 "tol": 1e-4, "reason": ""}),
                           _row("dropNode", "dropped")])
            dlg._update_ai_button(res, "/tmp/out")
            self.assertTrue(dlg._ai_btn.isVisible())
            self.assertIs(dlg._last_ai_result, res)
        finally:
            dlg.deleteLater()

    def test_update_hides_button_when_all_clean(self):
        dlg = self._dialog()
        try:
            dlg.show()
            res = _result([_row("okNode", "compiled",
                                {"ran": True, "pass": True, "maxerr": 0.0,
                                 "tol": 1e-4, "reason": ""})])
            dlg._update_ai_button(res, "/tmp/out")
            self.assertFalse(dlg._ai_btn.isVisible())
            self.assertIsNone(dlg._last_ai_result)
        finally:
            dlg.deleteLater()

    def test_click_emits_handoff_with_flagged_node(self):
        dlg = self._dialog()
        try:
            captured = []
            dlg.handoffToAssistant.connect(lambda h: captured.append(h))
            res = _result([_row("dropNode", "dropped")])
            dlg._update_ai_button(res, "/tmp/out")
            dlg._on_fix_with_ai()
            self.assertEqual(len(captured), 1)
            handoff = captured[0]
            self.assertEqual(handoff["kind"], "failure")
            names = {r["type_name"] for r in handoff["rows"]}
            self.assertIn("dropNode", names)
            self.assertEqual(handoff["out_dir"], "/tmp/out")
        finally:
            dlg.deleteLater()

    def test_click_without_result_is_noop(self):
        dlg = self._dialog()
        try:
            captured = []
            dlg.handoffToAssistant.connect(lambda h: captured.append(h))
            dlg._last_ai_result = None
            dlg._on_fix_with_ai()
            self.assertEqual(captured, [])
        finally:
            dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
