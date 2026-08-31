"""Scene-tree right-click "Run setup" / "Run demo" actions.

Pure source-inspection / signal-existence test (no Maya scene needed):
  * ``NDSceneTree`` exposes a ``runSetupRequested(name, native_type)`` signal.
  * ``_build_context_menu`` adds a "Run setup" action GATED on
    ``node_has_runnable_setup(name, native_type)`` (the node's TYPE has a
    ``setup()`` hook OR the node's own Methods source defines ``def setup(self)``
    -- e.g. the unitSphereCollision gallery deformer).
  * ``NDSceneTree`` ALSO exposes a ``runDemoRequested(name, native_type, demo)``
    signal and one or more "Run demo" actions GATED on
    ``node_setups.find_demos(methods_source_of(name))``. Unlike setup, demo has NO
    type default: it is gated PURELY on the node's own Methods source carrying at
    least one demo (``@maya_demo`` decorated OR the reserved ``def demo``; instance
    or factory) which fabricates its own showcase scene. One demo -> a single flat
    "Run demo" action; two or more -> a "Run demo" submenu of labeled entries.

Importing the widget pulls Qt, so create a QApplication at IMPORT time (before
maya.standalone installs a non-GUI QCoreApplication, which would make QWidget
creation fail). Mirrors the other UI test modules.
"""

from __future__ import annotations

import inspect
import unittest

# QApplication at IMPORT time -- mirrors the other UI test modules.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-run-setup-test"])


class TestRunSetupAction(unittest.TestCase):
    def test_signal_exists(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree
        self.assertTrue(hasattr(NDSceneTree, "runSetupRequested"))

    def test_menu_builds_run_setup_gated_on_instance_or_type(self):
        from mpynode.ui.widgets import scene_tree
        src = inspect.getsource(scene_tree.NDSceneTree._build_context_menu)
        self.assertIn("Run setup", src)
        # instance-aware gate (covers template mPyNodes, not just setup types)
        self.assertIn("node_has_runnable_setup", src)


class TestRunDemoAction(unittest.TestCase):
    def test_demo_signal_exists(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree
        self.assertTrue(hasattr(NDSceneTree, "runDemoRequested"))

    def test_menu_builds_run_demo_gated_on_instance_demo(self):
        from mpynode.ui.widgets import scene_tree
        src = inspect.getsource(scene_tree.NDSceneTree._build_context_menu)
        self.assertIn("Run demo", src)
        # demo has NO type default -> gated purely on the node's own Methods
        # source carrying at least one demo, discovered via find_demos over the
        # node's methods_source_of(...). Adaptive: 1 demo -> flat action,
        # 2+ -> a "Run demo" submenu.
        self.assertIn("find_demos", src)
        self.assertIn("methods_source_of", src)


if __name__ == "__main__":
    unittest.main()
