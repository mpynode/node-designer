"""NDOslEditor OSL -> assistant hand-off (WS2).

Proves that when OSL conversion hits a HARD, structural limit (a compute OSL
cannot express -- e.g. compositeTexture's string-array input), the editor emits
``handoffToAssistant`` with an ``osl`` hand-off (built by compile_bridge) so a
host can turn the dead end into an assistant conversation. The inline
``convertFailed`` message still fires for hosts that don't wire the new signal.

We force the intractable branch by patching ``assess_osl_tractability`` rather
than authoring a genuinely-intractable node, so the test is fast and precise.
"""

from __future__ import annotations

import os
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
    _QAPP = _QApplication.instance() or _QApplication(["osl-handoff-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestOslEditorHandoff(unittest.TestCase):
    def _editor(self):
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.ui.widgets.osl_editor import NDOslEditor

        mc.file(new=True, force=True)
        node = MPyFile.create(name="compositeTex")
        return node, NDOslEditor(node)

    def test_intractable_emits_osl_handoff_and_failure(self):
        node, ed = self._editor()
        try:
            handoffs = []
            failures = []
            ed.handoffToAssistant.connect(lambda h: handoffs.append(h))
            ed.convertFailed.connect(lambda m: failures.append(m))

            with mock.patch(
                "mpynode._common.osl.osl_convert.assess_osl_tractability",
                return_value=(False, "string-array input unsupported"),
            ):
                started = ed._convert_via_ai(Exception("deterministic failed"))

            self.assertFalse(started)  # worker never launched
            self.assertEqual(len(handoffs), 1)
            h = handoffs[0]
            self.assertEqual(h["kind"], "osl")
            self.assertIn("string-array input unsupported", h["reason"])
            self.assertTrue(h["suggestions"])
            # the inline failure message still fires
            self.assertEqual(len(failures), 1)
        finally:
            ed.deleteLater()

    def test_signal_exists(self):
        node, ed = self._editor()
        try:
            self.assertTrue(hasattr(ed, "handoffToAssistant"))
        finally:
            ed.deleteLater()


if __name__ == "__main__":
    unittest.main()
