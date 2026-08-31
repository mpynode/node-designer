"""Unit coverage for the reserved ``def demo(self)`` hook machinery.

Self-contained (no Maya scene needed for the static-detection + dispatch parts);
mirrors the existing setup-hook tests. Detection must behave EXACTLY like
``find_setup`` but keyed on the name ``demo`` -- last self-first def wins, a later
``demo = ...`` rebind cancels, factory/static defs are rejected.
"""
import unittest

from mpynode._common import node_setups


class TestFindDemo(unittest.TestCase):
    def test_plain_self_first_demo_detected(self):
        src = "def demo(self):\n    return 1\n"
        self.assertIsNotNone(node_setups.find_demo(src))
        self.assertTrue(node_setups.has_demo_source(src))

    def test_no_demo_returns_none(self):
        src = "def setup(self):\n    return 1\n"
        self.assertIsNone(node_setups.find_demo(src))
        self.assertFalse(node_setups.has_demo_source(src))

    def test_factory_demo_rejected(self):
        src = "def demo(cls):\n    return 1\n"
        self.assertIsNone(node_setups.find_demo(src))

    def test_static_rebind_cancels(self):
        src = "def demo(self):\n    return 1\ndemo = staticmethod(demo)\n"
        self.assertIsNone(node_setups.find_demo(src))

    def test_last_def_wins(self):
        # first self-first, later factory rebinds -> rejected (matches exec).
        src = "def demo(self):\n    return 1\ndef demo(cls):\n    return 2\n"
        self.assertIsNone(node_setups.find_demo(src))

    def test_setup_and_demo_are_independent(self):
        src = ("def setup(self, selection=None):\n    return 1\n"
               "def demo(self):\n    return 2\n")
        self.assertIsNotNone(node_setups.find_setup(src))
        self.assertIsNotNone(node_setups.find_demo(src))

    def test_empty_source_is_safe(self):
        for bad in (None, "", "   ", "def (:\n"):
            self.assertIsNone(node_setups.find_demo(bad))
            self.assertFalse(node_setups.has_demo_source(bad))


class _FakeNode:
    """Minimal wrapper stand-in: pure-Python, no Maya. Records delegate calls."""
    def __init__(self, methods_source):
        self._src = methods_source
        self.setup_calls = []
        self.demo_calls = []

    def get_methods_source(self):
        return self._src

    def get_name(self):
        return "fakeNode1"

    # the mixin delegates to the module-level dispatchers, which call
    # invoke_command(fn, self). The authored bodies poke these lists so the
    # test can prove binding + delegation without Maya.
    def setup(self, selection=None):
        self.setup_calls.append(selection)
        return "setup-ran"

    def demo(self):
        self.demo_calls.append(True)
        return "demo-ran"


class TestRunNodeDemo(unittest.TestCase):
    def test_dispatches_self_first_demo(self):
        from mpynode._common.methods.methods_registry import run_node_demo
        node = _FakeNode("def demo(self):\n    return self.get_name()\n")
        self.assertEqual(run_node_demo(node), "fakeNode1")

    def test_no_demo_raises_setup_error(self):
        from mpynode._common.methods.methods_registry import run_node_demo
        from mpynode._common.methods import setup_helpers as node_setup
        node = _FakeNode("def setup(self, selection=None):\n    return 1\n")
        with self.assertRaises(node_setup.SetupError):
            run_node_demo(node)

    def test_factory_demo_rejected(self):
        from mpynode._common.methods.methods_registry import run_node_demo
        from mpynode._common.methods import setup_helpers as node_setup
        node = _FakeNode("def demo(cls):\n    return 1\n")
        with self.assertRaises(node_setup.SetupError):
            run_node_demo(node)

    def test_run_node_demo_exported(self):
        from mpynode._common.methods import methods_registry
        self.assertIn("run_node_demo", methods_registry.__all__)


class TestMixinConvenience(unittest.TestCase):
    """run_setup/run_demo on the mixin delegate to the module-level dispatchers,
    binding ``self`` -- this is how a demo body reaches a peer node's setup
    (``wrap_node(sh).run_setup([shape])``) despite the wrapper not exposing
    methods_source funcs as attributes."""

    def test_mixin_run_demo_delegates(self):
        from mpynode._common.methods.methods_registry import MethodsSourceMixin

        # _FakeNode first so its pure-Python get_methods_source/get_name win
        # the MRO over the mixin's Maya-backed ones; run_setup/run_demo still
        # come from the mixin, which is what we are exercising.
        class W(_FakeNode, MethodsSourceMixin):
            def __init__(self, src):
                _FakeNode.__init__(self, src)

        w = W("def demo(self):\n    return self.get_name()\n")
        self.assertEqual(w.run_demo(), "fakeNode1")

    def test_mixin_run_setup_delegates_selection(self):
        from mpynode._common.methods.methods_registry import MethodsSourceMixin

        # _FakeNode first so its pure-Python get_methods_source/get_name win
        # the MRO over the mixin's Maya-backed ones; run_setup/run_demo still
        # come from the mixin, which is what we are exercising.
        class W(_FakeNode, MethodsSourceMixin):
            def __init__(self, src):
                _FakeNode.__init__(self, src)

        w = W("def setup(self, selection=None):\n    return selection\n")
        self.assertEqual(w.run_setup(["a", "b"]), ["a", "b"])


class TestCommandsWiring(unittest.TestCase):
    """Source-level wiring checks (no Maya scene): the demo command exists and
    _TemplateCreateCommand grew a run_demo path. Full behavioural coverage of the
    demo path lives in the migrated integration tests (Task 11)."""

    def test_run_demo_command_exists(self):
        from mpynode._base import commands
        self.assertTrue(hasattr(commands, "_RunDemoCommand"))

    def test_template_create_accepts_run_demo(self):
        import inspect
        from mpynode._base.commands import _TemplateCreateCommand
        params = inspect.signature(_TemplateCreateCommand.__init__).parameters
        self.assertIn("run_demo", params)

    def test_run_demo_command_calls_run_node_demo(self):
        import inspect
        from mpynode._base.commands import _RunDemoCommand
        src = inspect.getsource(_RunDemoCommand.doIt)
        self.assertIn("run_node_demo", src)
        # A demo builds its OWN scene -> it must NOT snapshot/pass a selection.
        self.assertNotIn("cmds.ls(selection", src)


class TestFindDemos(unittest.TestCase):
    def test_reserved_instance_demo(self):
        src = "def demo(self):\n    return 1\n"
        specs = node_setups.find_demos(src)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].func_name, "demo")
        self.assertEqual(specs[0].label, "Run demo")
        self.assertTrue(specs[0].is_instance)
        self.assertFalse(specs[0].is_factory)

    def test_reserved_factory_demo_now_accepted(self):
        # a reserved `def demo(cls)` is a factory demo that find_demos accepts,
        # though the back-compat find_demo shim still rejects it.
        src = "def demo(cls):\n    return 1\n"
        specs = node_setups.find_demos(src)
        self.assertEqual(len(specs), 1)
        self.assertTrue(specs[0].is_factory)
        self.assertIsNone(node_setups.find_demo(src))  # shim unchanged

    def test_decorated_and_reserved_union(self):
        src = ("@maya_demo(label='Alt')\ndef alt(self):\n    return 1\n"
               "def demo(self):\n    return 2\n")
        specs = node_setups.find_demos(src)
        self.assertEqual({s.func_name for s in specs}, {"alt", "demo"})

    def test_decorated_demo_named_demo_not_double_counted(self):
        src = "@maya_demo\ndef demo(self):\n    return 1\n"
        specs = node_setups.find_demos(src)
        self.assertEqual(len(specs), 1)

    def test_multiple_decorated_demos(self):
        src = ("@maya_demo(label='One')\ndef one(self):\n    return 1\n"
               "@maya_demo(label='Two')\ndef two(self):\n    return 2\n")
        self.assertEqual(node_setups.demo_labels(src), ["One", "Two"])

    def test_has_demo_source_widened(self):
        self.assertTrue(node_setups.has_demo_source(
            "@maya_demo\ndef x(self):\n    return 1\n"))
        self.assertTrue(node_setups.has_demo_source("def demo(cls):\n    return 1\n"))
        self.assertFalse(node_setups.has_demo_source("def setup(self):\n    return 1\n"))

    def test_static_rebind_still_cancels_reserved(self):
        src = "def demo(self):\n    return 1\ndemo = staticmethod(demo)\n"
        self.assertEqual(node_setups.find_demos(src), [])

    def test_select_demo(self):
        src = ("@maya_demo(label='One')\ndef one(self):\n    return 1\n"
               "@maya_demo(label='Two')\ndef two(self):\n    return 2\n")
        specs = node_setups.find_demos(src)
        self.assertEqual(node_setups.select_demo(specs, "two").func_name, "two")
        self.assertEqual(node_setups.select_demo(specs, "One").func_name, "one")
        self.assertEqual(node_setups.select_demo(specs, None).func_name, "one")
        self.assertIsNone(node_setups.select_demo(specs, "nope"))
        self.assertIsNone(node_setups.select_demo([], None))


class TestResolveAndRunDemos(unittest.TestCase):
    def test_run_node_demo_by_name(self):
        from mpynode._common.methods.methods_registry import run_node_demo
        src = ("@maya_demo(label='A')\ndef a(self):\n    return 'A' + self.get_name()\n"
               "@maya_demo(label='B')\ndef b(self):\n    return 'B' + self.get_name()\n")
        node = _FakeNode(src)
        self.assertEqual(run_node_demo(node, "b"), "BfakeNode1")
        self.assertEqual(run_node_demo(node, "A"), "AfakeNode1")  # by label

    def test_run_node_demo_default_is_first(self):
        from mpynode._common.methods.methods_registry import run_node_demo
        src = ("@maya_demo\ndef first(self):\n    return 1\n"
               "@maya_demo\ndef second(self):\n    return 2\n")
        self.assertEqual(run_node_demo(_FakeNode(src)), 1)

    def test_run_node_demo_unknown_name_raises(self):
        from mpynode._common.methods.methods_registry import run_node_demo
        from mpynode._common.methods import setup_helpers as node_setup
        node = _FakeNode("@maya_demo\ndef a(self):\n    return 1\n")
        with self.assertRaises(node_setup.SetupError):
            run_node_demo(node, "nope")

    def test_run_node_demo_factory_raises_use_run_type(self):
        # run_node_demo is the INSTANCE path, so a factory demo is rejected
        # here and goes through run_type_demo instead.
        from mpynode._common.methods.methods_registry import run_node_demo
        from mpynode._common.methods import setup_helpers as node_setup
        node = _FakeNode("@maya_demo\ndef make(cls):\n    return 1\n")
        with self.assertRaises(node_setup.SetupError):
            run_node_demo(node)

    def test_resolve_demo_classifies(self):
        from mpynode._common.methods.methods_registry import resolve_demo
        fn, is_factory = resolve_demo(
            "@maya_demo\ndef make(cls):\n    return 1\n")
        self.assertTrue(is_factory)
        fn2, is_factory2 = resolve_demo(
            "@maya_demo\ndef show(self):\n    return 1\n")
        self.assertFalse(is_factory2)

    def test_run_type_demo_exported(self):
        from mpynode._common.methods import methods_registry
        self.assertIn("run_type_demo", methods_registry.__all__)

    def test_maya_demo_seeded_in_namespace(self):
        from mpynode._common.methods.methods_registry import build_methods_namespace
        ns = build_methods_namespace("x = 1\n")
        self.assertIn("maya_demo", ns)
        self.assertIn("maya_command", ns)


class TestCommandFactoryRouting(unittest.TestCase):
    def test_run_demo_command_accepts_demo_name(self):
        import inspect
        from mpynode._base.commands import _RunDemoCommand
        params = inspect.signature(_RunDemoCommand.__init__).parameters
        self.assertIn("demo_name", params)

    def test_run_demo_command_routes_factory(self):
        import inspect
        from mpynode._base.commands import _RunDemoCommand
        src = inspect.getsource(_RunDemoCommand.doIt)
        self.assertIn("run_type_demo", src)
        self.assertIn("run_node_demo", src)
        self.assertIn("is_factory", src)
        # A demo builds its OWN scene -> still no selection snapshot.
        self.assertNotIn("cmds.ls(selection", src)

    def test_template_create_accepts_demo_name(self):
        import inspect
        from mpynode._base.commands import _TemplateCreateCommand
        params = inspect.signature(_TemplateCreateCommand.__init__).parameters
        self.assertIn("demo_name", params)

    def test_template_create_routes_factory(self):
        import inspect
        from mpynode._base.commands import _TemplateCreateCommand
        src = inspect.getsource(_TemplateCreateCommand.doIt)
        self.assertIn("run_type_demo", src)
        self.assertIn("is_factory", src)


class TestSceneTreeDemoWiring(unittest.TestCase):
    def test_run_demo_signal_has_demo_name_arg(self):
        # runDemoRequested must carry (node_name, native_type, demo_name).
        import inspect
        from mpynode.ui.widgets import scene_tree
        src = inspect.getsource(scene_tree)
        self.assertIn("runDemoRequested = Signal(str, str, str)", src)

    def test_scene_tree_menu_uses_find_demos(self):
        import inspect
        from mpynode.ui.widgets import scene_tree
        src = inspect.getsource(scene_tree)
        self.assertIn("find_demos", src)

    def test_designer_run_demo_handler_accepts_demo_name(self):
        import inspect
        from mpynode.ui import mpynode_designer
        src = inspect.getsource(mpynode_designer.NDMainWindow._on_run_demo_requested)
        self.assertIn("demo_name", src)


class TestMethodsEditorDemoWiring(unittest.TestCase):
    def test_methods_editor_uses_find_demos(self):
        import inspect
        from mpynode.ui.widgets import methods_editor
        src = inspect.getsource(methods_editor.NDMethodsEditor.contextMenuEvent)
        self.assertIn("find_demos", src)

    def test_run_demo_passes_demo_name(self):
        import inspect
        from mpynode.ui.widgets import methods_editor
        src = inspect.getsource(methods_editor.NDMethodsEditor)
        self.assertIn("demo_name", src)


class TestGalleryDemoWiring(unittest.TestCase):
    def test_do_create_accepts_demo_name(self):
        import inspect
        from mpynode.ui.widgets import template_gallery_panel as tgp
        params = inspect.signature(
            tgp.NDTemplateGalleryPanel._do_create).parameters
        self.assertIn("demo_name", params)

    def test_gallery_uses_template_demos(self):
        import inspect
        from mpynode.ui.widgets import template_gallery_panel as tgp
        src = inspect.getsource(tgp.NDTemplateGalleryPanel)
        self.assertIn("_template_demos", src)

    def test_create_from_template_forwards_demo_name(self):
        import inspect
        from mpynode.ui import mpynode_designer
        src = inspect.getsource(
            mpynode_designer.NDMainWindow._create_from_template)
        self.assertIn("demo_name", src)


if __name__ == "__main__":
    unittest.main()
