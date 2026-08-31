"""OSL hand-off propagation: OSL editor -> NDScriptTabContent -> NDScriptTabWidget.

Proves the signal chain that turns an OSL intractability into an assistant
conversation actually forwards end-to-end (mirroring how tabSaved aggregates).
The designer's final hop (tab widget -> _route_compile_handoff -> panel) is a
plain Signal.connect verified by the designer/seed tests; here we prove the
per-tab OSL editor's hand-off reaches the aggregated tab-widget signal.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["osl-prop-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestOslHandoffPropagation(unittest.TestCase):
    def test_editor_handoff_reaches_tab_widget(self):
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget
        from mpynode.ui.llm import compile_bridge

        mc.file(new=True, force=True)
        node = MPyFile.create(name="compositeTex")

        tabw = NDScriptTabWidget()
        try:
            tabw.addOrRaiseTab(node)
            content = tabw.currentWidget()
            self.assertTrue(hasattr(content, "handoffToAssistant"))
            osl_ed = getattr(content, "_osl_editor", None)
            self.assertIsNotNone(osl_ed, "mPyFile tab should have an OSL editor")

            received = []
            tabw.handoffToAssistant.connect(lambda h: received.append(h))

            # Simulate the editor emitting an OSL hand-off; it must bubble up
            # through the tab content to the aggregated tab-widget signal.
            handoff = compile_bridge.build_osl_handoff(
                "string-array input unsupported", node_name="compositeTex")
            osl_ed.handoffToAssistant.emit(handoff)

            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["kind"], "osl")
        finally:
            tabw.deleteLater()

    def test_designer_has_route_handler(self):
        # The final hop connects the tab widget's aggregated signal to this
        # handler (also used by the compile dialog's "Fix with AI").
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "_route_compile_handoff"))


if __name__ == "__main__":
    unittest.main()
