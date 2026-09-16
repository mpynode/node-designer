"""Foundation \u2014 undoable commands + scene tree wiring + tab shell."""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# runUndoableAPICommand (hosted by mpynode_api2) + _BaseCommand + run_undoable
# ===========================================================================


class TestUndoablePluginAndBase(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_undoable_command_hosted_by_api2(self):
        """runUndoableAPICommand ships inside the mpynode_api2 plug-in (folded
        in from the former standalone undoable_api_command plug-in so the
        toolkit is exactly two plug-ins). load_plugin is idempotent and api2
        registers the command itself -- no separate plug-in needed."""
        from mpynode._base.plugins import load_plugin

        # after the context the plug-in is loaded; re-entering is a no-op.
        with load_plugin("mpynode_api2"):
            self.assertTrue(mc.pluginInfo("mpynode_api2", q=True, loaded=True))
        with load_plugin("mpynode_api2"):
            self.assertTrue(mc.pluginInfo("mpynode_api2", q=True, loaded=True))
        # api2 registers the dispatcher command in its own initializePlugin.
        registered = mc.pluginInfo("mpynode_api2", q=True, command=True) or []
        self.assertIn("runUndoableAPICommand", registered)

    def test_run_undoable_with_no_op_command(self):
        """A simple _BaseCommand with side-effect doIt + reversible undoIt."""
        from mpynode._base.commands import _BaseCommand, run_undoable

        history: list[str] = []

        class _MyCmd(_BaseCommand):
            def doIt(self):
                history.append("do")
                return "ok"

            def undoIt(self):
                history.append("undo")

            def redoIt(self):
                history.append("redo")

        result = run_undoable(_MyCmd())
        self.assertEqual(result, "ok")
        self.assertEqual(history, ["do"])

        mc.undo()
        self.assertEqual(history[-1], "undo")
        mc.redo()
        self.assertEqual(history[-1], "redo")

    def test_create_node_command_is_undoable(self):
        """_CreateNodeCommand creates an mPyNode that Ctrl+Z removes."""
        from mpynode._base.commands import _CreateNodeCommand, run_undoable

        cmd     = _CreateNodeCommand("mPyNode", name="cmdTestNode")
        created = run_undoable(cmd)
        self.assertEqual(created, "cmdTestNode")
        self.assertTrue(mc.objExists("cmdTestNode"))

        mc.undo()
        self.assertFalse(mc.objExists("cmdTestNode"))

        mc.redo()
        self.assertTrue(mc.objExists("cmdTestNode"))

    def test_set_expression_command_round_trip(self):
        """Ctrl+Z restores the previous expression after _SetExpressionCommand."""
        from mpynode._base.commands import _SetExpressionCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="exprUndo")
        n.set_compute_expression("# original")

        run_undoable(_SetExpressionCommand(n, "# new value"))
        self.assertEqual(n.get_compute_expression(), "# new value")

        mc.undo()
        self.assertEqual(n.get_compute_expression(), "# original")

        mc.redo()
        self.assertEqual(n.get_compute_expression(), "# new value")


# ===========================================================================
# Node registry
# ===========================================================================


class TestNodeRegistry(unittest.TestCase):
    def test_core_types_registered(self):
        from mpynode._node_registry import all_native_types

        types = set(all_native_types())
        for nt in (
            "mPyNode",
            "mPyLocator",
            "mPyConstraint",
            "mPyIkSolver",
        ):
            self.assertIn(nt, types)
        # Deleted node types must NOT be registered.
        for nt in ("mPyObjectSet", "mPyField", "mPyEmitter", "mPyLattice"):
            self.assertNotIn(nt, types)

    def test_get_spec_returns_wrapper_class(self):
        from mpynode._node_registry import get_spec

        spec = get_spec("mPyIkSolver")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.native_type, "mPyIkSolver")
        cls = spec.get_wrapper_class()
        self.assertEqual(cls.__name__, "MPyIkSolver")

    def test_wrap_node(self):
        from mpynode._node_registry import wrap_node

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        MPyIkSolver.create(name="wrapTest")
        wrapped = wrap_node("wrapTest", "mPyIkSolver")
        self.assertIsNotNone(wrapped)
        self.assertEqual(wrapped.get_name(), "wrapTest")
        self.assertIsInstance(wrapped, MPyIkSolver)

    def test_wrap_node_unknown_returns_none(self):
        from mpynode._node_registry import wrap_node

        self.assertIsNone(wrap_node("foo", "notARealType"))

    def test_wrap_node_auto_detects_when_the_type_is_omitted(self):
        """The one-arg form is what replaced the old bare ``wrap``. It must
        agree with the two-arg form on the same node, or the merge changed
        behaviour for one set of callers."""
        from mpynode._node_registry import wrap_node

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        MPyIkSolver.create(name="autoWrap")
        auto = wrap_node("autoWrap")
        told = wrap_node("autoWrap", "mPyIkSolver")
        self.assertIsInstance(auto, MPyIkSolver)
        self.assertEqual(type(auto), type(told))
        self.assertEqual(auto.get_name(), told.get_name())

    def test_wrap_node_one_arg_returns_none_off_the_registry(self):
        """Silently, for both misses -- the UI and LLM callers probe arbitrary
        name strings and must not have to catch."""
        from mpynode._node_registry import wrap_node

        mc.file(new=True, force=True)
        self.assertIsNone(wrap_node("noSuchNode__xyz"))           # does not exist
        self.assertIsNone(wrap_node(mc.createNode("transform")))  # not an mPy

    def test_the_bare_wrap_name_is_retired(self):
        """Removed, not aliased: leaving it would keep the word occupied, and
        freeing it for a geometry factory was the point of the rename."""
        import mpynode
        from mpynode import _node_registry

        self.assertFalse(hasattr(_node_registry, "wrap"))
        self.assertTrue(hasattr(_node_registry, "wrap_node"))
        with self.assertRaises(AttributeError):
            mpynode.wrap
        self.assertIn("wrap_node", dir(mpynode))
        self.assertNotIn("wrap", dir(mpynode))


# ===========================================================================
# Scene tree widget (Qt-guarded structural)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestSceneTreeStructure(unittest.TestCase):
    def test_class_signals_and_methods(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree, NDSceneTreeItem

        for method in ("refresh", "findItem", "selectNode", "_on_selection_changed"):
            self.assertTrue(hasattr(NDSceneTree, method))
        self.assertTrue(hasattr(NDSceneTree, "nodeSelected"))
        for method in ("setNodeName", "_refresh_label"):
            self.assertTrue(hasattr(NDSceneTreeItem, method))

    def test_scene_tree_module_uses_registry(self):
        """Scene tree refresh should iterate the node registry, not a hardcoded list."""
        import inspect

        from mpynode.ui.widgets.scene_tree import NDSceneTree

        src = inspect.getsource(NDSceneTree.refresh)
        self.assertIn("all_native_types", src)


# ===========================================================================
# Script tab widget (Qt-guarded structural)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestScriptTabWidgetStructure(unittest.TestCase):
    def test_class_methods(self):
        from mpynode.ui.widgets.script_tab import (
            NDScriptEditorPlaceholder,
            NDScriptTabWidget,
        )

        for method in (
            "addOrRaiseTab",
            "getIndexOfNode",
            "getCurrentNode",
            "closeTabForNode",
            "renameTabForNode",
        ):
            self.assertTrue(hasattr(NDScriptTabWidget, method))
        self.assertTrue(hasattr(NDScriptEditorPlaceholder, "getMPyNode"))
        self.assertTrue(hasattr(NDScriptEditorPlaceholder, "refresh"))

    def test_active_node_changed_signal(self):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        self.assertTrue(hasattr(NDScriptTabWidget, "activeNodeChanged"))


# ===========================================================================
# Designer integration (Qt-guarded structural)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDesignerWiring(unittest.TestCase):
    def test_main_window_uses_scene_tree_and_tab_widget(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("NDSceneTree",       src)
        self.assertIn("NDScriptTabWidget", src)
        self.assertIn("Refresh",           src)  # refresh button

    def test_wire_signals_connects_scene_tree_to_tab(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._wire_signals)
        self.assertIn("nodeSelected", src)
        self.assertIn("activeNodeChanged", src)
        self.assertIn("_on_scene_node_selected", src)
        self.assertIn("_on_active_tab_changed", src)
        self.assertIn(".refresh", src)  # refresh button connected

    def test_cascade_method_present(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        for m in (
            "_on_scene_node_selected",
            "_on_active_tab_changed",
            "setCurrentNode",
            "_register_scene_callbacks",
            "_remove_scene_callbacks",
            "_on_node_added_cb",
            "_on_node_removed_cb",
            "_on_scene_changed_cb",
            "closeEvent",
        ):
            self.assertTrue(hasattr(NDMainWindow, m), f"missing {m}")

    def test_close_event_removes_callbacks(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.closeEvent)
        self.assertIn("_remove_scene_callbacks", src)


# ===========================================================================
# Regression: inherited-attr collisions (caught the mPyField applyPerVertex bug)
# ===========================================================================


class TestNoBaseAttrCollisions(unittest.TestCase):
    """Regression for the ``mPyField applyPerVertex`` inherited-attr collision.

    For each Maya base type our MPx subclasses inherit from (or via
    intermediate proxy types like ``THdynField``), assert that NO
    attribute name we explicitly add via ``node_initializer`` already
    exists on a stock concrete instance of that base type.

    A collision means the parent C++ class auto-provides the attribute
    via inheritance \u2014 calling ``cls.addAttribute(...)`` for the same
    name will raise ``(kInvalidParameter): Object already exists`` on
    plugin load (silently swallowed in mayapy; warning + traceback in
    interactive Maya).

    Probes use STOCK Maya types (``gravityField``, ``pointEmitter``,
    ``locator``, ``objectSet``, ``transform``) so we don't need our
    own plug-in loaded \u2014 the test catches collisions BEFORE we
    register our nodes.
    """

    # Every name added via build_internal_attrs, plus per-node extras. Add a
    # new addAttribute in any node_initializer -> ADD ITS NAME HERE, or the
    # regression stops catching collisions.
    OUR_ADDED_NAMES = frozenset({
        # Standard internal attrs (build_internal_attrs)
        "_computeSource", "_inputAttrs", "_outputAttrs",
        "_storedVarNames", "_storedVarsData", "debug_mode",
        # mPyIkSolver extras
        "_solverContextSnapshot",
        # mPyConstraint preset inputs
        "targetTranslate", "targetRotate", "targetWeight",
        "restTranslate", "restRotate",
    })

    # (stock_concrete_type, base_type_label_for_error_messages)
    PROBE_NODES = (
        ("gravityField",  "field"),         # MPxFieldNode parent
        ("pointEmitter",  "pointEmitter"),  # MPxEmitterNode parent
        ("locator",       "locator"),       # MPxLocatorNode parent
        ("objectSet",     "objectSet"),     # MPxObjectSet parent
        ("transform",     "transform"),     # MPxNode parent (closest non-abstract)
    )

    def setUp(self):
        # Deliberately no ensure_plugins_loaded(), so the probe sees
        # pre-plugin attribute state. Even if a sibling test loaded the
        # plugins, createNode("gravityField") still gives a STOCK Maya field
        # node, so the inherited set is unaffected.
        mc.file(new=True, force=True)

    def test_no_collisions_with_stock_base_types(self):
        for stock_type, label in self.PROBE_NODES:
            try:
                node = mc.createNode(stock_type, name=f"_probe_{stock_type}")
            except Exception:
                # Type unavailable in this Maya install; skip silently.
                continue
            try:
                collisions = {
                    name
                    for name in self.OUR_ADDED_NAMES
                    if mc.attributeQuery(name, node=node, exists=True)
                }
                self.assertFalse(
                    collisions,
                    (
                        f"Stock Maya {label!r} type already provides these "
                        f"attribute names via inheritance: {sorted(collisions)}. "
                        f"Calling addAttribute() with any of these in a "
                        f"node_initializer will raise '(kInvalidParameter): "
                        f"Object already exists' on plugin load. "
                        f"Either rename our attr OR rely on the inherited one "
                        f"(remove the addAttribute call)."
                    ),
                )
            finally:
                try:
                    mc.delete(node)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
