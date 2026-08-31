# scripts/mpynode/_tests/test_node_setups.py  (pure AST -- no setUpModule needed)
import unittest
from mpynode._common import node_setups as ns
from mpynode._common.methods.methods_registry import build_methods_namespace


class TestFindSetup(unittest.TestCase):
    def _name(self, src):
        node = ns.find_setup(src)
        return None if node is None else node.name

    def test_selffirst_def_accepted(self):
        self.assertEqual(self._name("def setup(self):\n    return self\n"), "setup")

    def test_selffirst_varargs_accepted(self):
        self.assertEqual(
            self._name("def setup(self, *a, **k):\n    return self\n"), "setup")

    def test_clsfirst_def_rejected(self):
        self.assertIsNone(ns.find_setup("def setup(cls):\n    return cls\n"))

    def test_classmethod_def_rejected(self):
        self.assertIsNone(ns.find_setup(
            "@classmethod\ndef setup(self):\n    return self\n"))

    def test_staticmethod_rejected(self):
        self.assertIsNone(ns.find_setup("@staticmethod\ndef setup():\n    pass\n"))
        self.assertIsNone(ns.find_setup(
            "@staticmethod\ndef setup(self):\n    pass\n"))

    def test_no_params_rejected(self):
        self.assertIsNone(ns.find_setup("def setup():\n    pass\n"))

    def test_non_setup_instance_ignored(self):
        self.assertIsNone(ns.find_setup("def wire(self):\n    return self\n"))

    def test_empty_and_whitespace(self):
        self.assertIsNone(ns.find_setup(""))
        self.assertIsNone(ns.find_setup("   \n\t"))
        self.assertIsNone(ns.find_setup(None))

    def test_syntax_error_returns_none(self):
        self.assertIsNone(ns.find_setup("def setup(self)\n  oops"))

    def test_nested_def_ignored(self):
        self.assertIsNone(ns.find_setup(
            "def outer():\n    def setup(self):\n        return self\n"))

    def _exec_kind(self, src):
        obj = build_methods_namespace(src).get("setup")
        if isinstance(obj, (classmethod, staticmethod)) or obj is None:
            return "non-instance"
        import inspect
        params = list(inspect.signature(obj).parameters)
        return "self" if (params and params[0] == "self") else "non-instance"

    def test_order_a_self_then_cls(self):
        src = "def setup(self):\n    return self\ndef setup(cls):\n    return cls\n"
        self.assertIsNone(ns.find_setup(src))
        self.assertEqual(self._exec_kind(src), "non-instance")

    def test_order_b_cls_then_self(self):
        src = "def setup(cls):\n    return cls\ndef setup(self):\n    return self\n"
        self.assertEqual(self._name(src), "setup")
        self.assertEqual(self._exec_kind(src), "self")

    def test_order_c_assign_rebind(self):
        for tail in ("setup = staticmethod(setup)\n", "setup = None\n",
                     "setup: object = None\n"):
            src = "def setup(self):\n    return self\n" + tail
            self.assertIsNone(ns.find_setup(src), tail)
            self.assertEqual(self._exec_kind(src), "non-instance", tail)


class TestLocator(unittest.TestCase):
    """LOCK: the eight real setup sources resolve via the exact-stem locator."""

    SETUP_TYPES = ["mPyMesh", "mPyNurbsCurve", "mPyNurbsSurface", "mPyFile",
                   "mPyDeformer", "mPySkinCluster", "mPyBlendShape", "mPyIkSolver"]

    def test_unknown_type_none(self):
        self.assertIsNone(ns.setup_source_for_type("mPyNope"))
        self.assertIsNone(ns.setup_source_for_type(""))
        self.assertIsNone(ns.setup_source_for_type(None))

    def test_exact_stem_case_sensitive(self):
        self.assertIsNotNone(ns.setup_source_for_type("mPyIkSolver"))
        self.assertIsNone(ns.setup_source_for_type("mPyIksolver"))  # wrong case

    def test_all_setup_types_resolve(self):
        for t in self.SETUP_TYPES:
            self.assertIsNotNone(ns.setup_source_for_type(t), t)

    def test_type_has_setup_true_for_setup_types_false_for_base(self):
        for t in self.SETUP_TYPES:
            self.assertTrue(ns.type_has_setup(t), t)
        self.assertFalse(ns.type_has_setup("mPyNode"))

    def test_type_has_setup_stable(self):
        self.assertEqual(ns.type_has_setup("mPyMesh"), ns.type_has_setup("mPyMesh"))


if __name__ == "__main__":
    unittest.main()
