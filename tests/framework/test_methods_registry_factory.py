# tests/framework/test_methods_registry_factory.py  (pure -- no setUpModule)
import unittest
from mpynode._common.methods.methods_registry import invoke_factory, _resolved_is_factory


class Dummy(object):
    NATIVE_TYPE = "Dummy"


class TestInvokeFactory(unittest.TestCase):
    def test_plain_clsfirst_binds_class(self):
        def setup(cls):
            return cls
        self.assertIs(invoke_factory(setup, Dummy), Dummy)

    def test_classmethod_binds_class(self):
        self.assertIs(invoke_factory(classmethod(lambda cls: cls), Dummy), Dummy)

    def test_staticmethod_no_binding(self):
        self.assertEqual(invoke_factory(staticmethod(lambda: "s"), Dummy), "s")

    def test_args_and_kwargs_forwarded(self):
        def setup(cls, a, b=0):
            return (cls, a, b)
        self.assertEqual(
            invoke_factory(setup, Dummy, args=(1,), kwargs={"b": 2}), (Dummy, 1, 2))


class TestResolvedIsFactory(unittest.TestCase):
    def test_classmethod_true(self):
        self.assertTrue(_resolved_is_factory(classmethod(lambda cls: cls)))

    def test_plain_clsfirst_true(self):
        self.assertTrue(_resolved_is_factory(lambda cls: cls))

    def test_selffirst_false(self):
        self.assertFalse(_resolved_is_factory(lambda self: self))

    def test_staticmethod_false(self):
        self.assertFalse(_resolved_is_factory(staticmethod(lambda: 1)))

    def test_none_false(self):
        self.assertFalse(_resolved_is_factory(None))


class TestResolvedIsInstanceSetup(unittest.TestCase):
    def _fn(self, src):
        from mpynode._common.methods.methods_registry import build_methods_namespace
        return build_methods_namespace(src).get("setup")

    def test_self_first_true(self):
        from mpynode._common.methods.methods_registry import _resolved_is_instance_setup
        self.assertTrue(_resolved_is_instance_setup(
            self._fn("def setup(self):\n    return self\n")))

    def test_cls_first_false(self):
        from mpynode._common.methods.methods_registry import _resolved_is_instance_setup
        self.assertFalse(_resolved_is_instance_setup(
            self._fn("def setup(cls):\n    return cls\n")))

    def test_classmethod_false(self):
        from mpynode._common.methods.methods_registry import _resolved_is_instance_setup
        self.assertFalse(_resolved_is_instance_setup(
            self._fn("@classmethod\ndef setup(cls):\n    return cls\n")))

    def test_staticmethod_false(self):
        from mpynode._common.methods.methods_registry import _resolved_is_instance_setup
        self.assertFalse(_resolved_is_instance_setup(
            self._fn("@staticmethod\ndef setup():\n    pass\n")))

    def test_none_false(self):
        from mpynode._common.methods.methods_registry import _resolved_is_instance_setup
        self.assertFalse(_resolved_is_instance_setup(None))


class TestRunNodeSetupHelper(unittest.TestCase):
    """run_node_setup: the single source of truth for self-first setup invocation."""

    class _FakeWrapper:
        def __init__(self, src):
            self._src = src
            self._calls = []

        def get_methods_source(self):
            return self._src

        def get_name(self):
            return "fakeNode1"

    def test_raises_setup_error_without_self_first_setup(self):
        from mpynode._common.methods.methods_registry import run_node_setup
        from mpynode._common.methods.setup_helpers import SetupError
        # methods source with NO setup at all
        w = self._FakeWrapper("def helper(self):\n    pass\n")
        with self.assertRaises(SetupError):
            run_node_setup(w, [])

    def test_raises_setup_error_on_cls_first_setup(self):
        from mpynode._common.methods.methods_registry import run_node_setup
        from mpynode._common.methods.setup_helpers import SetupError
        # cls-first setup is a factory, NOT a self-first setup -> rejected
        w = self._FakeWrapper("def setup(cls, selection=None):\n    return 'factory'\n")
        with self.assertRaises(SetupError):
            run_node_setup(w, [])

    def test_invokes_self_first_setup_with_selection_kwarg(self):
        from mpynode._common.methods.methods_registry import run_node_setup
        w = self._FakeWrapper(
            "def setup(self, selection=None):\n"
            "    self._calls.append(selection)\n"
            "    return selection\n")
        out = run_node_setup(w, ["a", "b"])
        self.assertEqual(out, ["a", "b"])
        self.assertEqual(w._calls, [["a", "b"]])


if __name__ == "__main__":
    unittest.main()
