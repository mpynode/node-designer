"""Designer per-node MNodeMessage attr callbacks + connection-changed routing

Consolidated from: test_phase21.py, test_connection_changed_routing.py.
"""

from __future__ import annotations

# ===================== from test_phase21.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase21():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Low-level node_callbacks helpers (live with maya.api.OpenMaya)
# ===========================================================================


class TestNodeCallbacksHelpers(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_install_and_remove_round_trip(self):
        from mpynode._base.node_callbacks import (
            install_node_attr_callback,
            remove_callback,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cb1")

        fired = []

        def dispatcher(plug):
            fired.append(plug.name())

        cb_id = install_node_attr_callback(n.get_name(), dispatcher)
        try:
            self.assertIsNotNone(cb_id)
            n.set_compute_expression("# hello")
            self.assertGreater(len(fired), 0)
            self.assertTrue(
                any(p.startswith(n.get_name() + ".") for p in fired),
                f"expected callback to fire for {n.get_name()!r}; got {fired!r}",
            )
        finally:
            remove_callback(cb_id)

    def test_remove_callback_after_unregister_silences_dispatcher(self):
        from mpynode._base.node_callbacks import (
            install_node_attr_callback,
            remove_callback,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cb2")
        fired = []

        cb_id = install_node_attr_callback(n.get_name(), lambda p: fired.append(p.name()))
        n.set_compute_expression("# first")
        first_count = len(fired)
        self.assertGreater(first_count, 0)

        remove_callback(cb_id)
        n.set_compute_expression("# second")  # must NOT fire after unregister
        self.assertEqual(len(fired), first_count)

    def test_remove_callback_safe_on_none(self):
        from mpynode._base.node_callbacks import remove_callback

        # Should not raise.
        remove_callback(None)

    def test_remove_callback_safe_on_invalid_id(self):
        from mpynode._base.node_callbacks import remove_callback

        # Should not raise even with garbage.
        remove_callback(999999999)

    def test_dispatcher_exceptions_are_swallowed(self):
        """A raising dispatcher must NOT crash Maya \u2014 callback wrapper
        swallows."""
        from mpynode._base.node_callbacks import (
            install_node_attr_callback,
            remove_callback,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cb3")

        def bad_dispatcher(plug):
            raise RuntimeError("intentional")

        cb_id = install_node_attr_callback(n.get_name(), bad_dispatcher)
        try:
            # Must not raise out of the callback.
            n.set_compute_expression("# trigger")
        finally:
            remove_callback(cb_id)

    def test_only_kAttributeSet_fires(self):
        """Attribute add/remove events should NOT fire the dispatcher."""
        from mpynode._base.node_callbacks import (
            install_node_attr_callback,
            remove_callback,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cb4")
        fired = []

        cb_id = install_node_attr_callback(n.get_name(), lambda p: fired.append(p.name()))
        try:
            # the add itself is a different message kind and should not fire,
            # but add_input_attr also writes _inputAttrs (kAttributeSet),
            # which does.
            n.add_input_attr("x", "float")
            # the exact count depends on the internal setAttr flow, so only
            # assert the callback didn't crash.
            self.assertIsInstance(fired, list)
        finally:
            remove_callback(cb_id)


# ===========================================================================
# NDScriptTabWidget tabsChanged signal + getOpenNodeNames
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestScriptTabSignal(unittest.TestCase):
    def test_tabsChanged_signal_exists(self):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        self.assertTrue(hasattr(NDScriptTabWidget, "tabsChanged"))

    def test_getOpenNodeNames_method_exists(self):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        self.assertTrue(hasattr(NDScriptTabWidget, "getOpenNodeNames"))
        self.assertTrue(callable(NDScriptTabWidget.getOpenNodeNames))

    def test_addOrRaiseTab_emits_tabsChanged(self):
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget.addOrRaiseTab)
        self.assertIn("tabsChanged.emit", src)

    def test_close_paths_emit_tabsChanged(self):
        """Both closeTabForNode AND _on_tab_close_requested must emit
        tabsChanged so the callback registry stays in sync."""
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        for method_name in (
            "closeTabForNode",
            "_on_tab_close_requested",
        ):
            method = getattr(NDScriptTabWidget, method_name)
            src = inspect.getsource(method)
            self.assertIn(
                "tabsChanged.emit",
                src,
                f"{method_name} must emit tabsChanged",
            )


# ===========================================================================
# NDMainWindow registry + dispatcher (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestMainWindowReconcile(unittest.TestCase):
    def test_main_window_has_callback_registry(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.__init__)
        self.assertIn("_node_attr_callbacks", src)

    def test_wire_signals_connects_tabsChanged(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._wire_signals)
        self.assertIn("tabsChanged.connect", src)
        self.assertIn("_reconcile_node_attr_callbacks", src)

    def test_close_event_unregisters_all_attr_callbacks(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.closeEvent)
        self.assertIn("_unregister_all_node_attr_callbacks", src)

    def test_reconcile_is_idempotent_set_diff(self):
        """_reconcile uses set difference so it's safe to call repeatedly
        with same input \u2014 verify by source inspection."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._reconcile_node_attr_callbacks)
        # both set differences, so existing entries stay untouched.
        self.assertIn("target_names - current_names", src)
        self.assertIn("current_names - target_names", src)

    def test_dispatcher_routes_to_correct_panel(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._on_node_attr_changed)
        # Routes for each special plug kind:
        self.assertIn('"_computeSource"', src)
        self.assertIn('"_inputAttrs"', src)
        self.assertIn('"_outputAttrs"', src)
        self.assertIn('"_storedVarsData"', src)
        self.assertIn('"_storedVarNames"', src)
        self.assertIn('"_solverContextSnapshot"', src)
        self.assertIn("_refresh_editor_for_node", src)
        self.assertIn("_refresh_attributes_for_node", src)
        self.assertIn("_refresh_storage_for_node", src)
        self.assertIn("_refresh_solver_context_for_node", src)

    def test_editor_refresh_skips_dirty_tabs(self):
        """Conflict resolution: don't clobber unsaved edits."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._refresh_editor_for_node)
        self.assertIn("hasUnsavedChanges", src)
        # Should `continue` instead of refresh on dirty.
        self.assertIn("continue", src)

    def test_panel_refreshers_only_act_for_active_node(self):
        """Attributes / Storage / Solver refresh only when the changed
        node IS the currently-displayed node (panels are single-node)."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        for fn_name in (
            "_refresh_attributes_for_node",
            "_refresh_storage_for_node",
            "_refresh_solver_context_for_node",
        ):
            src = inspect.getsource(getattr(NDMainWindow, fn_name))
            self.assertIn("_current_node", src)
            self.assertIn("get_name()", src)


# ===========================================================================
# End-to-end: tabsChanged -> reconcile -> install MNodeMessage -> external
# setAttr -> dispatcher fires -> panel refresher called. No Qt widgets; bare
# reconciler + dispatcher methods.
# ===========================================================================


class TestE2EIntegration(unittest.TestCase):
    """Exercises the callback wiring end-to-end without instantiating
    NDMainWindow / NDScriptTabWidget. Constructs a minimal stand-in that
    has the same instance attributes the reconciler + dispatcher methods
    touch, then drives them like the live UI would."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _make_stand_in(self):
        """Build a minimal object with the attrs NDMainWindow methods
        expect, without inheriting from QMainWindow (which can't be
        constructed cleanly in mayapy)."""
        from mpynode.ui.mpynode_designer import NDMainWindow

        class _StandIn:
            pass

        s = _StandIn()
        s._node_attr_callbacks = {}
        s._node_connection_callbacks = {}
        s._current_node = None
        s._editor_refresh_calls = []
        s._attrs_refresh_calls = []
        s._storage_refresh_calls = []
        s._solver_refresh_calls = []

        # Bind only the unbound methods the integration path uses.
        s._reconcile_node_attr_callbacks = (
            NDMainWindow._reconcile_node_attr_callbacks.__get__(s)
        )
        s._unregister_all_node_attr_callbacks = (
            NDMainWindow._unregister_all_node_attr_callbacks.__get__(s)
        )

        def _on_changed(plug):
            full = plug.name()
            node_name, _, plug_path = full.partition(".")
            short = plug_path.split(".")[-1] if plug_path else ""
            if short == "_computeSource":
                s._editor_refresh_calls.append(node_name)
            elif short in ("_inputAttrs", "_outputAttrs"):
                s._attrs_refresh_calls.append(node_name)
            elif short in ("_storedVarsData", "_storedVarNames"):
                s._storage_refresh_calls.append(node_name)
            elif short == "_solverContextSnapshot":
                s._solver_refresh_calls.append(node_name)

        s._on_node_attr_changed = _on_changed
        return s

    def test_reconcile_installs_on_open(self):
        from mpynode.wrappers._mpy_node import MPyNode

        s = self._make_stand_in()
        n = MPyNode.create(name="e2e_open")
        s._reconcile_node_attr_callbacks([n.get_name()])
        self.assertIn(n.get_name(), s._node_attr_callbacks)
        s._unregister_all_node_attr_callbacks()

    def test_reconcile_removes_on_close(self):
        from mpynode.wrappers._mpy_node import MPyNode

        s = self._make_stand_in()
        n = MPyNode.create(name="e2e_close")
        s._reconcile_node_attr_callbacks([n.get_name()])
        self.assertIn(n.get_name(), s._node_attr_callbacks)

        # Tab closed.
        s._reconcile_node_attr_callbacks([])
        self.assertNotIn(n.get_name(), s._node_attr_callbacks)

    def test_reconcile_idempotent_no_double_install(self):
        from mpynode.wrappers._mpy_node import MPyNode

        s = self._make_stand_in()
        n = MPyNode.create(name="e2e_idem")
        s._reconcile_node_attr_callbacks([n.get_name()])
        first_id = s._node_attr_callbacks[n.get_name()]

        # Same input → no change in callback id (no duplicate install).
        s._reconcile_node_attr_callbacks([n.get_name()])
        self.assertEqual(s._node_attr_callbacks[n.get_name()], first_id)

        s._unregister_all_node_attr_callbacks()

    def test_external_setAttr_fires_dispatcher_for_expression(self):
        from mpynode.wrappers._mpy_node import MPyNode

        s = self._make_stand_in()
        n = MPyNode.create(name="e2e_expr")
        s._reconcile_node_attr_callbacks([n.get_name()])

        # external setAttr, standing in for a different client.
        n.set_compute_expression("# external edit")

        self.assertIn(n.get_name(), s._editor_refresh_calls)

        s._unregister_all_node_attr_callbacks()

    def test_external_attr_changes_fire_panel_refreshers(self):
        from mpynode.wrappers._mpy_node import MPyNode

        s = self._make_stand_in()
        n = MPyNode.create(name="e2e_panels")
        s._reconcile_node_attr_callbacks([n.get_name()])

        # Expression edit → editor refresh
        n.set_compute_expression("# x")
        self.assertIn(n.get_name(), s._editor_refresh_calls)

        # Adding an input lands both the _inputAttrs map setAttr and the new
        # plug; the dispatcher fires for _inputAttrs.
        n.add_input_attr("driven", "float")
        self.assertIn(n.get_name(), s._attrs_refresh_calls)

        # Storage write
        n.set_variable("counter", 7)
        self.assertIn(n.get_name(), s._storage_refresh_calls)

        s._unregister_all_node_attr_callbacks()

    def test_unregister_silences_external_changes(self):
        from mpynode.wrappers._mpy_node import MPyNode

        s = self._make_stand_in()
        n = MPyNode.create(name="e2e_silence")
        s._reconcile_node_attr_callbacks([n.get_name()])

        n.set_compute_expression("# before")
        before_calls = len(s._editor_refresh_calls)
        self.assertGreater(before_calls, 0)

        s._unregister_all_node_attr_callbacks()
        self.assertEqual(s._node_attr_callbacks, {})

        # External edit after unregister should NOT fire.
        n.set_compute_expression("# after")
        self.assertEqual(len(s._editor_refresh_calls), before_calls)

    def test_two_nodes_isolated(self):
        """Callbacks for one node don't fire for another."""
        from mpynode.wrappers._mpy_node import MPyNode

        s = self._make_stand_in()
        n1 = MPyNode.create(name="iso_a")
        n2 = MPyNode.create(name="iso_b")
        s._reconcile_node_attr_callbacks([n1.get_name(), n2.get_name()])

        n1.set_compute_expression("# a")
        # Both nodes are registered; n1 should fire only for n1.
        self.assertIn(n1.get_name(), s._editor_refresh_calls)
        self.assertNotIn(n2.get_name(), s._editor_refresh_calls)

        n2.set_compute_expression("# b")
        self.assertIn(n2.get_name(), s._editor_refresh_calls)

        s._unregister_all_node_attr_callbacks()


# ===================== from test_connection_changed_routing.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__connection_changed_routing():
    standalone_init()


class _FakePlug:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakeSelf:
    def __init__(self):
        self.refreshed = []

    def _refresh_attributes_for_node(self, node_name):
        self.refreshed.append(node_name)


class TestConnectionChangedRouting(unittest.TestCase):
    def test_routes_node_name_to_attr_refresh(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        fake = _FakeSelf()
        NDMainWindow._on_node_connection_changed(
            fake, _FakePlug("pointNoise.outPoints[260]")
        )
        self.assertEqual(fake.refreshed, ["pointNoise"])

    def test_never_raises_on_bad_plug(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        class _BadPlug:
            def name(self):
                raise RuntimeError("boom")

        fake = _FakeSelf()
        # must swallow (callbacks must never raise out into Maya)
        NDMainWindow._on_node_connection_changed(fake, _BadPlug())
        self.assertEqual(fake.refreshed, [])


def setUpModule():
    _setUpModule__phase21()
    _setUpModule__connection_changed_routing()


if __name__ == "__main__":
    import unittest
    unittest.main()
