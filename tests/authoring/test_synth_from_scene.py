import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import importlib
import unittest
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestSynthFromScene(unittest.TestCase):
    def test_rebuilds_class_from_scene(self):
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io import user_classes

        mc.file(new=True, force=True)
        n = MPyNode.create(name="synthFromScene#")
        n.set_py_class("mpynode_user.SceneBorn")
        # Simulate a fresh process: forget the synthetic class.
        sys.modules.pop(user_classes.PACKAGE, None)

        count = user_classes.synthesize_from_scene()
        self.assertGreaterEqual(count, 1)
        mod = importlib.import_module("mpynode_user")
        self.assertTrue(hasattr(mod, "SceneBorn"))
        self.assertTrue(issubclass(mod.SceneBorn, MPyNode))

    def test_ignores_external_module_class_paths(self):
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io import user_classes

        mc.file(new=True, force=True)
        n = MPyNode.create(name="extPath#")
        n.set_py_class("some.external.Thing")  # not mpynode_user.*
        sys.modules.pop(user_classes.PACKAGE, None)
        user_classes.synthesize_from_scene()
        mod = importlib.import_module("mpynode_user")
        self.assertFalse(hasattr(mod, "Thing"))
