"""NDAssistantPanel.seed_compile_context -- the "Compile with AI" concierge seam.

Proves the assistant panel exposes a PUBLIC entry point that turns a native
compile hand-off (from ui.llm.compile_bridge) into a pre-filled starter prompt in
the input box, WITHOUT sending it (the first compile always requires a human
press).

Follows the QApplication-first ordering the other Qt tests use: the app must
exist before maya.standalone.initialize, else QWidget construction crashes.
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
    _QAPP = _QApplication.instance() or _QApplication(["assistant-seed-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestSeedCompileContext(unittest.TestCase):
    def _panel(self):
        from mpynode.ui.widgets.assistant_panel import NDAssistantPanel

        return NDAssistantPanel()

    def _handoff(self, kind="failure"):
        from mpynode.ui.llm import compile_bridge

        result = {
            "ok": True,
            "plugin_name": "myPlugin",
            "nodes": [{
                "source_node": "dropNode1",
                "type_name": "dropNode",
                "build_status": "dropped",
                "build_reason": "port: needs <map>",
                "verify": {"ran": False, "pass": None, "maxerr": None,
                           "tol": None, "reason": ""},
                "spec": {"portability": {"blockers": ["dict keyed by tuple"]}},
            }],
            "errors": [],
        }
        return compile_bridge.build_handoff(result, {"out_dir": "/tmp/out"},
                                            kind=kind)

    def test_seed_fills_input_without_sending(self):
        from mpynode.ui.llm import compile_bridge

        p = self._panel()
        try:
            h = self._handoff()
            expected = compile_bridge.starter_prompt(h)
            returned = p.seed_compile_context(h)
            self.assertEqual(returned, expected)
            self.assertEqual(p._input.toPlainText(), expected)
            # nothing was sent: the report block is embedded in the draft
            self.assertIn("[Compile report]", p._input.toPlainText())
            self.assertIn("dropNode", p._input.toPlainText())
        finally:
            p.deleteLater()

    def test_seed_is_public(self):
        p = self._panel()
        try:
            self.assertTrue(hasattr(p, "seed_compile_context"))
            self.assertFalse(
                "seed_compile_context".startswith("_"),
                "concierge entry point must be public")
        finally:
            p.deleteLater()

    def test_optimize_kind_produces_different_seed(self):
        p = self._panel()
        try:
            fail_text = p.seed_compile_context(self._handoff("failure"))
            opt_text = p.seed_compile_context(self._handoff("optimize"))
            self.assertNotEqual(fail_text, opt_text)
        finally:
            p.deleteLater()


if __name__ == "__main__":
    unittest.main()
