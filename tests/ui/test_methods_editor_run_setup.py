"""Source-inspection tests for the Methods-window right-click
"Run setup on selection" / "Run demo (new scene)" context items.

Both items must live on NDMethodsEditor (which holds ``self._py_node``) -- NOT on
the shared QtPythonEditor base in editor_core.py -- so they appear ONLY in the
Methods tab and never leak into Compute/Init/Viewport/OSL. "Run setup on
selection" is offered when the source defines a self-first ``def setup``; "Run
demo (new scene)" when it defines a self-first ``def demo`` (which fabricates its
OWN showcase scene, taking no selection).

Importing methods_editor pulls in Qt widgets, which need a QApplication at
import time under mayapy; mirror the guard used by the other UI test modules.
"""
import inspect
import unittest

# --- QApplication-at-import guard (mirrors test_methods_tier.py) ----------
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-runsetup-test"])


class TestMethodsRunSetup(unittest.TestCase):
    def test_context_menu_override_exists_on_methods_editor(self):
        from mpynode.ui.widgets.methods_editor import NDMethodsEditor
        # NDMethodsEditor must define its OWN contextMenuEvent (not just inherit
        # QtPythonEditor's), so the item appears only in the Methods tab.
        self.assertIn("contextMenuEvent", NDMethodsEditor.__dict__)

    def test_run_setup_item_text_present(self):
        from mpynode.ui.widgets import methods_editor
        src = inspect.getsource(methods_editor.NDMethodsEditor.contextMenuEvent)
        self.assertIn("Run setup on selection", src)

    def test_run_demo_item_text_present(self):
        from mpynode.ui.widgets import methods_editor
        src = inspect.getsource(methods_editor.NDMethodsEditor.contextMenuEvent)
        # "Run demo (new scene)" is offered when the source defines a self-first
        # ``def demo`` -- it fabricates its own showcase scene (no selection).
        self.assertIn("Run demo (new scene)", src)


if __name__ == "__main__":
    unittest.main()
