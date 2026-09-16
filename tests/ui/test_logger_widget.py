"""Log color must reset after an error.

Regression: an error message (red, via appendHtml) could leave the
QPlainTextEdit's current char format colored, so the next info line
("Saved expression on ...") rendered red instead of the theme default.
The info path now inserts with an explicit default QTextCharFormat so
it can't inherit a leaked color.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
    from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
        from PySide2.QtGui import QColor, QTextCharFormat, QTextCursor
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["logger-color-test"])

import unittest


def _qt():
    return _QAPP is not None


def _last_color(ed):
    b  = ed.document().lastBlock()
    it = b.begin()
    if it.atEnd():
        return None
    c = it.fragment().charFormat().foreground().color()
    return (c.red(), c.green(), c.blue())


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestLoggerColorReset(unittest.TestCase):
    def _widget(self):
        from mpynode.ui.widgets.logger import NDLoggerWidget

        return NDLoggerWidget()

    def test_info_default_after_error(self):
        w = self._widget()
        w.append_message(
            "Traceback...\nNameError: name 'x' not defined", level="error"
        )
        w.append_message("Saved expression on 'gizmo'", level="info")
        self.assertEqual(_last_color(w._editor), (0, 0, 0))

    def test_info_default_even_from_polluted_state(self):
        """Simulate the intermittent Qt carry-over: force the editor's
        current + trailing char format to red, then log info. It must
        still come out theme-default."""
        w   = self._widget()
        red = QTextCharFormat()
        red.setForeground(QColor("#d44444"))
        w._editor.setCurrentCharFormat(red)
        cur = w._editor.textCursor()
        cur.movePosition(QTextCursor.End)
        cur.setCharFormat(red)
        w._editor.setTextCursor(cur)

        w.append_message("Saved expression on 'gizmo'", level="info")
        self.assertEqual(_last_color(w._editor), (0, 0, 0))

    def test_error_still_red(self):
        w = self._widget()
        w.append_message("boom", level="error")
        r, g, b = _last_color(w._editor)
        self.assertGreater(r, 150)
        self.assertLess(g, 120)

    def test_warning_still_amber(self):
        w = self._widget()
        w.append_message("careful", level="warning")
        r, g, b = _last_color(w._editor)
        # amber #d4a000 -> high red, mid green, ~no blue.
        self.assertGreater(r, 150)
        self.assertLess(b, 80)

    def test_info_path_uses_explicit_format(self):
        import inspect

        from mpynode.ui.widgets.logger import NDLoggerWidget

        src = inspect.getsource(NDLoggerWidget.append_message)
        self.assertIn("QTextCharFormat", src)
        self.assertIn("setCharFormat", src)


if __name__ == "__main__":
    unittest.main()
