import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
import importlib
import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestUserClasses(unittest.TestCase):
    def setUp(self):
        from mpynode._common.io import user_classes
        # Start each test from a clean synthetic module.
        sys.modules.pop(user_classes.PACKAGE, None)

    def test_ensure_module_registers_in_sys_modules(self):
        from mpynode._common.io import user_classes
        mod = user_classes.ensure_module()
        self.assertIs(sys.modules.get("mpynode_user"), mod)
        # Idempotent: second call returns the same object.
        self.assertIs(user_classes.ensure_module(), mod)

    def test_synthesize_returns_importable_subclass(self):
        from mpynode._common.io import user_classes
        from mpynode.wrappers._mpy_node import MPyNode
        cls = user_classes.synthesize("Procrustes", "mPyNode")
        self.assertTrue(issubclass(cls, MPyNode))
        self.assertEqual(cls.__module__, "mpynode_user")
        self.assertEqual(cls.__qualname__, "Procrustes")

    def test_import_resolves_from_sys_modules_no_disk(self):
        from mpynode._common.io import user_classes
        from mpynode.wrappers._mpy_node import _import_py_class
        user_classes.synthesize("Procrustes", "mPyNode")
        mod = importlib.import_module("mpynode_user")
        self.assertTrue(hasattr(mod, "Procrustes"))
        self.assertIs(_import_py_class("mpynode_user.Procrustes"),
                      getattr(mod, "Procrustes"))

    def test_from_import_works(self):
        from mpynode._common.io import user_classes
        user_classes.synthesize("Widget", "mPyNode")
        ns = {}
        exec("from mpynode_user import Widget", ns)
        self.assertTrue(isinstance(ns["Widget"], type))

    def test_synthesize_idempotent_same_base(self):
        from mpynode._common.io import user_classes
        a = user_classes.synthesize("Foo", "mPyNode")
        b = user_classes.synthesize("Foo", "mPyNode")
        self.assertIs(a, b)

    def test_synthesize_different_base_raises(self):
        from mpynode._common.io import user_classes
        user_classes.synthesize("Foo", "mPyNode")
        with self.assertRaises(ValueError):
            user_classes.synthesize("Foo", "mPyMesh")

    def test_stamp_path_is_canonical(self):
        from mpynode._common.io import user_classes
        cls = user_classes.synthesize("Bar", "mPyNode")
        self.assertEqual(cls.__module__ + "." + cls.__qualname__,
                         "mpynode_user.Bar")

    def test_dotted_path_helper(self):
        from mpynode._common.io import user_classes
        self.assertEqual(user_classes.dotted_path("Bar"), "mpynode_user.Bar")


class TestStampClass(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_stamp_class_synthesizes_and_stamps(self):
        from mpynode._common.io import user_classes
        from mpynode.wrappers._mpy_node import MPyNode, _read_py_class
        n = MPyNode.create(name="stampA#")
        path = user_classes.stamp_class(n.get_name(), "mPyNode", "Gadget")
        self.assertEqual(path, "mpynode_user.Gadget")
        self.assertEqual(_read_py_class(n.get_name()), "mpynode_user.Gadget")
        # The class is importable afterwards.
        self.assertTrue(hasattr(user_classes.ensure_module(), "Gadget"))

    def test_stamp_class_bad_name_raises(self):
        from mpynode._common.io import user_classes
        from mpynode.wrappers._mpy_node import MPyNode
        n = MPyNode.create(name="stampB#")
        with self.assertRaises(ValueError):
            user_classes.stamp_class(n.get_name(), "mPyNode", "")

    def test_stamp_class_missing_node_returns_none(self):
        from mpynode._common.io import user_classes
        self.assertIsNone(
            user_classes.stamp_class("nope_no_such_node", "mPyNode", "Ghost"))


class TestClassPathPlug(unittest.TestCase):
    def test_plug_attr_is_class_path(self):
        from mpynode.wrappers import _mpy_node
        self.assertEqual(_mpy_node._PY_CLASS_PLUG, "class_path")

    def test_set_get_roundtrip_on_new_attr(self):
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        n = MPyNode.create(name="clsPathRT#")
        n.set_py_class("mpynode_user.Thing")
        self.assertEqual(n.get_py_class(), "mpynode_user.Thing")
        self.assertTrue(mc.attributeQuery("class_path",
                                          node=n.get_name(), exists=True))
