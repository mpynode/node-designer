"""Scene-tab right-click "Compile…": a per-node context-menu action that opens
the native compile dialog with THAT node preselected (checked), so the user
lands one click from compiling just it instead of hunting the full scene list.

  * ``NDSceneTree`` exposes a ``compileNodeRequested(str, str)`` signal and a
    "Compile…" menu action that emits it;
  * ``NDMainWindow`` wires the signal to a handler that opens the dialog with
    ``preselect=<node>``;
  * ``CompileDialog.preselect_node`` checks exactly that node (a known scene
    node), ignoring unknown/stale names and no-op'ing mid-compile.

Importing the widget pulls Qt, so create a QApplication at IMPORT time (mirrors
the other UI test modules)."""

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
    _QAPP = _QApp.instance() or _QApp(["nd-compile-menu-test"])

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


class TestCompileMenuSignalAndAction(unittest.TestCase):
    def test_signal_exists(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree
        self.assertTrue(hasattr(NDSceneTree, "compileNodeRequested"))

    def test_menu_source_has_compile_action(self):
        from mpynode.ui.widgets import scene_tree

        src = inspect.getsource(scene_tree.NDSceneTree._build_context_menu)
        self.assertIn("Compile", src)
        self.assertIn("compileNodeRequested", src)


class TestCompileMenuWiring(unittest.TestCase):
    def test_signal_wired(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(mpynode_designer.NDMainWindow._wire_signals)
        self.assertIn("compileNodeRequested.connect", src)

    def test_handler_exists(self):
        from mpynode.ui import mpynode_designer
        self.assertTrue(hasattr(
            mpynode_designer.NDMainWindow, "_on_compile_node_requested"))

    def test_open_compile_dialog_accepts_preselect(self):
        from mpynode.ui import mpynode_designer

        sig = inspect.signature(
            mpynode_designer.NDMainWindow._open_compile_dialog)
        self.assertIn("preselect", sig.parameters)

    def test_handler_opens_dialog_with_preselect(self):
        from mpynode.ui import mpynode_designer

        src = inspect.getsource(
            mpynode_designer.NDMainWindow._on_compile_node_requested)
        self.assertIn("_open_compile_dialog", src)
        self.assertIn("preselect", src)


class _PreselFake:
    """Duck-typed CompileDialog for preselect_node (only what it touches)."""

    def __init__(self, nodes, busy=False):
        self._busy        = busy
        self._scene_nodes = list(nodes)
        self._checked     = set()
        self._refreshed   = 0

    def _refresh_table(self):
        self._refreshed += 1


class TestPreselectNode(unittest.TestCase):
    def test_checks_exactly_the_named_scene_node(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        fake = _PreselFake([("metaClay1", "mPyMesh"), ("other1", "mPyMesh")])
        CompileDialog.preselect_node(fake, "metaClay1")
        self.assertEqual(fake._checked, {"metaClay1"})
        self.assertEqual(fake._refreshed, 1)

    def test_ignores_unknown_node(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        fake = _PreselFake([("metaClay1", "mPyMesh")])
        CompileDialog.preselect_node(fake, "ghost99")
        self.assertEqual(fake._checked, set())
        self.assertEqual(fake._refreshed, 0)

    def test_noop_while_busy(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        fake = _PreselFake([("metaClay1", "mPyMesh")], busy=True)
        CompileDialog.preselect_node(fake, "metaClay1")
        self.assertEqual(fake._checked, set())
        self.assertEqual(fake._refreshed, 0)


@unittest.skipUnless(_QAPP is not None, "requires Qt")
class TestConvertCompileMenuStates(unittest.TestCase):
    """#69: the right-click menu must show BOTH "Compile to C++…" and "Convert
    Node to C++" for EVERY node (Convert was previously HIDDEN unless the node
    was a classed REGISTRY type), with a MUTUALLY-EXCLUSIVE enable: when the
    node is convertible (its Class's compiled type is loaded) Convert is enabled
    and Compile is disabled; otherwise Compile is enabled and Convert is
    disabled. A CONVERTED node shows an enabled "Revert Node to Python" instead
    of Convert and still disables Compile.

    The two are named apart on purpose -- "Compile to C++" builds the .bundle /
    C++ TYPE, "Convert Node to C++" swaps THIS node instance onto it -- and
    Compile is listed FIRST because that is the order the flow runs in."""

    def _build(self, convertible, converted):
        from mpynode._base import commands
        from mpynode.ui.widgets.scene_tree import NDSceneTree, NDSceneTreeItem

        orig_conv                      = commands.is_convertible_to_cpp
        orig_isc                       = commands.is_converted
        commands.is_convertible_to_cpp = lambda n, t: convertible
        commands.is_converted          = lambda n: converted
        self.addCleanup(setattr, commands, "is_convertible_to_cpp", orig_conv)
        self.addCleanup(setattr, commands, "is_converted", orig_isc)

        tree = NDSceneTree(None)
        self.addCleanup(tree.deleteLater)
        item = NDSceneTreeItem(tree, "fakeNode1", "mPyMesh")
        tree.setCurrentItem(item)
        menu   = tree._build_context_menu()
        states = {}
        order  = []
        for a in menu.actions():
            txt = a.text()
            if txt:
                states[txt] = a.isEnabled()
                order.append(txt)
        self._order = order
        return states

    @staticmethod
    def _find(states, prefix):
        for txt, enabled in states.items():
            if txt.startswith(prefix):
                return enabled
        return None

    def _index(self, prefix):
        for i, txt in enumerate(self._order):
            if txt.startswith(prefix):
                return i
        return -1

    def test_both_actions_always_present_when_not_convertible(self):
        states = self._build(convertible=False, converted=False)
        self.assertIsNotNone(self._find(states, "Compile to C++"),
                             "Compile to C++ action must always be present")
        self.assertIsNotNone(
            self._find(states, "Convert Node to C++"),
            "Convert Node to C++ must be present even when disabled")

    def test_convertible_enables_convert_disables_compile(self):
        states = self._build(convertible=True, converted=False)
        self.assertTrue(self._find(states, "Convert Node to C++"))
        self.assertFalse(self._find(states, "Compile to C++"))

    def test_not_convertible_enables_compile_disables_convert(self):
        states = self._build(convertible=False, converted=False)
        self.assertTrue(self._find(states, "Compile to C++"))
        self.assertFalse(self._find(states, "Convert Node to C++"))

    def test_converted_shows_revert_and_disables_compile(self):
        states = self._build(convertible=False, converted=True)
        self.assertTrue(self._find(states, "Revert Node to Python"))
        self.assertFalse(self._find(states, "Compile to C++"))
        self.assertIsNone(self._find(states, "Convert Node to C++"),
                          "a converted node shows Revert, not Convert")

    def test_compile_is_listed_before_convert(self):
        """Compile FIRST, then Convert -- the order the flow actually runs in."""
        self._build(convertible=False, converted=False)
        c_i = self._index("Compile to C++")
        v_i = self._index("Convert Node to C++")
        self.assertNotEqual(c_i, -1)
        self.assertNotEqual(v_i, -1)
        self.assertLess(c_i, v_i,
                        "Compile to C++ must precede Convert Node to C++")

    def test_compile_is_listed_before_revert(self):
        self._build(convertible=False, converted=True)
        c_i = self._index("Compile to C++")
        r_i = self._index("Revert Node to Python")
        self.assertNotEqual(c_i, -1)
        self.assertNotEqual(r_i, -1)
        self.assertLess(c_i, r_i,
                        "Compile to C++ must precede Revert Node to Python")

    def test_load_compiled_plugin_always_offered_and_enabled(self):
        """A compiled type is SESSION-scoped, so the way to make an
        already-built bundle resident must be reachable in every state --
        including the one where Convert is greyed out, which is exactly when
        the user needs it."""
        for convertible, converted in ((False, False), (True, False),
                                       (False, True)):
            states = self._build(convertible=convertible, converted=converted)
            self.assertTrue(
                self._find(states, "Load Compiled Plug-in"),
                "Load Compiled Plug-in must be present and ENABLED "
                "(convertible=%s converted=%s)" % (convertible, converted))

    def test_load_compiled_plugin_signal_exists(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree
        self.assertTrue(hasattr(NDSceneTree, "loadCompiledPluginRequested"))

    def test_designer_wires_load_compiled_plugin(self):
        """The signal is useless unless NDMainWindow has the slot it names."""
        from mpynode.ui import mpynode_designer
        self.assertTrue(
            hasattr(mpynode_designer.NDMainWindow,
                    "_on_load_compiled_plugin_requested"))


if __name__ == "__main__":
    unittest.main()
