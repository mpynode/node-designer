"""Node duplication: ``build_duplicate_node_command`` (Scene-tree right-click +
Node menu "Duplicate" / "Duplicate + Inputs").

Two commands:
  * Duplicate          -- deep copy of the node INCLUDING all persistent stored
                          data, with NO input connections. The copied stored
                          data must be INDEPENDENT (not a shared reference) so
                          mutating one node's data never touches the other.
  * Duplicate + Inputs -- same, but ALSO re-wires every incoming (input)
                          connection from the source's upstream onto the copy,
                          so a TA can swap nodes without redoing connections.
"""

from __future__ import annotations

import inspect
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init

# QApplication at IMPORT time (before maya.standalone installs a non-GUI
# QCoreApplication, which would make QWidget creation fail). Mirrors the other
# UI test modules.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-dup-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _wrap(name, native_type="mPyNode"):
    from mpynode._node_registry import wrap_node

    return wrap_node(name, native_type)


class TestDuplicateNodeCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.src = MPyNode.create(name="srcNode")
        self.src.add_input_attr("alpha", "float", default_value=2.0)
        self.src.add_output_attr("out", "float")
        self.src.set_compute_expression("out = alpha * 2.0")

    def _duplicate(self, with_inputs=False, source=None):
        from mpynode._base.commands import (
            build_duplicate_node_command,
            run_undoable,
        )

        source = source or self.src.get_name()
        cmd = build_duplicate_node_command(
            source, "mPyNode", with_inputs=with_inputs
        )
        created = run_undoable(cmd)
        if created is None:
            created = getattr(cmd, "created_name", None)
        return created

    # ---- structure / definition copy -------------------------------------
    def test_duplicate_creates_distinct_node(self):
        dup = self._duplicate()
        self.assertTrue(dup and mc.objExists(dup))
        self.assertNotEqual(dup, self.src.get_name())
        self.assertEqual(mc.nodeType(dup), "mPyNode")

    def test_duplicate_copies_definition(self):
        dup = self._duplicate()
        d   = _wrap(dup)
        self.assertEqual(d.get_compute_expression(), "out = alpha * 2.0")
        self.assertIn("alpha", d.get_input_attr_map())
        self.assertIn("out", d.get_output_attr_map())

    # ---- persistent data: copied AND independent --------------------------
    def test_duplicate_copies_persistent_data(self):
        self.src.set_variable("counter", 7, persistent=True)
        self.src.set_variable("config", {"a": 1, "b": [1, 2, 3]}, persistent=True)
        d = _wrap(self._duplicate())
        self.assertEqual(d.get_variables().get("counter"), 7)
        self.assertEqual(d.get_variables().get("config"), {"a": 1, "b": [1, 2, 3]})

    def test_persistent_data_is_independent_not_referenced(self):
        """The user's explicit requirement: stored data is COPIED, not shared.
        Mutating the source's stored value must NOT change the duplicate's."""
        self.src.set_variable("w", [1, 2, 3], persistent=True)
        d = _wrap(self._duplicate())
        self.assertEqual(d.get_variables()["w"], [1, 2, 3])
        # Mutate the SOURCE's cached list in place.
        self.src.get_variables()["w"].append(999)
        self.assertEqual(self.src.get_variables()["w"], [1, 2, 3, 999])
        # The duplicate must be unaffected (deep, independent copy).
        self.assertEqual(d.get_variables()["w"], [1, 2, 3])

    def test_persistent_numpy_is_independent(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy unavailable")
        self.src.set_variable("arr", np.array([1.0, 2.0, 3.0]), persistent=True)
        d = _wrap(self._duplicate())
        # Mutate the source array in place.
        self.src.get_variables()["arr"] += 100.0
        dup_arr = d.get_variables()["arr"]
        self.assertAlmostEqual(float(dup_arr[0]), 1.0)
        self.assertAlmostEqual(float(dup_arr[2]), 3.0)

    def test_session_only_var_not_promoted_to_persistent(self):
        """Duplicate copies ONLY persistent data. ``get_variables()`` returns the
        FULL in-memory store -- including session-only scratch vars (un-registered
        ``self.X`` writes / ``persistent=False``). Those must NOT be promoted to
        persistent on the copy (which would diverge from the source and bloat the
        saved scene); the genuinely persistent var must survive."""
        from mpynode._common.storedvars import stored_vars_api

        self.src.set_variable("keep", 5, persistent=True)
        self.src.set_variable("scratch", 999, persistent=False)
        dup = self._duplicate()
        # The genuinely persistent var is copied AND stays persistent.
        self.assertTrue(stored_vars_api.is_variable_persistent(dup, "keep"))
        self.assertEqual(_wrap(dup).get_variables().get("keep"), 5)
        # The session-only var must NOT be promoted to persistent on the copy.
        self.assertFalse(
            stored_vars_api.is_variable_persistent(dup, "scratch"),
            "session-only 'scratch' was wrongly promoted to persistent on the "
            "duplicate",
        )

    # ---- input connections ------------------------------------------------
    def _make_upstream_driving_alpha(self):
        from mpynode.wrappers._mpy_node import MPyNode

        up = MPyNode.create(name="upstreamNode")
        up.add_output_attr("drv", "float")
        mc.connectAttr(up.get_name() + ".drv", self.src.get_name() + ".alpha")
        return up

    def test_duplicate_without_inputs_has_no_input_connections(self):
        up = self._make_upstream_driving_alpha()
        d  = _wrap(self._duplicate(with_inputs=False))
        conns = mc.listConnections(
            d.get_name() + ".alpha", source=True, destination=False
        ) or []
        self.assertEqual(conns, [])

    def test_duplicate_with_inputs_rewires_input_connection(self):
        up = self._make_upstream_driving_alpha()
        d  = _wrap(self._duplicate(with_inputs=True))
        srcs = mc.listConnections(
            d.get_name() + ".alpha", source=True, destination=False, plugs=True
        ) or []
        # The duplicate's alpha must be driven by the SAME upstream plug.
        self.assertEqual(srcs, [up.get_name() + ".drv"])

    def test_duplicate_with_inputs_does_not_rewire_outputs(self):
        """Only INPUT connections are preserved -- the copy's outputs stay free
        so it can be wired to a fresh destination."""
        # Wire the source's OUTPUT to a downstream consumer.
        from mpynode.wrappers._mpy_node import MPyNode

        down = MPyNode.create(name="downNode")
        down.add_input_attr("sink", "float")
        mc.connectAttr(self.src.get_name() + ".out", down.get_name() + ".sink")
        d = _wrap(self._duplicate(with_inputs=True))
        out_conns = mc.listConnections(
            d.get_name() + ".out", source=False, destination=True
        ) or []
        self.assertEqual(out_conns, [])

    # ---- undo -------------------------------------------------------------
    def test_duplicate_is_undoable(self):
        dup = self._duplicate()
        self.assertTrue(mc.objExists(dup))
        mc.undo()
        self.assertFalse(mc.objExists(dup))
        self.assertTrue(mc.objExists(self.src.get_name()))


# ===========================================================================
# Scene-tree right-click context menu (Duplicate / Duplicate + Inputs)
# ===========================================================================
@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestSceneTreeDuplicateMenu(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _tree_with_selected_item(self):
        from mpynode.ui.widgets.scene_tree import NDSceneTree, NDSceneTreeItem

        tree = NDSceneTree()
        NDSceneTreeItem(tree, "fooNode", "mPyNode").setSelected(True)
        return tree

    def test_context_menu_has_both_duplicate_actions(self):
        tree   = self._tree_with_selected_item()
        labels = [a.text() for a in tree._build_context_menu().actions()]
        self.assertIn("Duplicate", labels)
        self.assertIn("Duplicate + Inputs", labels)

    def test_duplicate_action_emits_signal(self):
        tree = self._tree_with_selected_item()
        got  = {}
        tree.duplicateNodeRequested.connect(
            lambda n, t: got.update(name=n, type=t)
        )
        act = next(
            a for a in tree._build_context_menu().actions() if a.text() == "Duplicate"
        )
        act.trigger()
        self.assertEqual(got, {"name": "fooNode", "type": "mPyNode"})

    def test_duplicate_with_inputs_action_emits_signal(self):
        tree = self._tree_with_selected_item()
        got  = {}
        tree.duplicateWithInputsRequested.connect(
            lambda n, t: got.update(name=n, type=t)
        )
        act = next(
            a for a in tree._build_context_menu().actions()
            if a.text() == "Duplicate + Inputs"
        )
        act.trigger()
        self.assertEqual(got, {"name": "fooNode", "type": "mPyNode"})


# ===========================================================================
# Designer wiring (source-inspection -- no full window build needed)
# ===========================================================================
class TestDesignerDuplicateWiring(unittest.TestCase):
    def test_signals_are_wired(self):
        from mpynode.ui import mpynode_designer as m

        src = inspect.getsource(m.NDMainWindow._wire_signals)
        self.assertIn("duplicateNodeRequested", src)
        self.assertIn("duplicateWithInputsRequested", src)

    def test_node_menu_exposes_duplicate_actions(self):
        from mpynode.ui import mpynode_designer as m

        src = inspect.getsource(m.NDMainWindow._build_menu_bar)
        self.assertIn("Duplicate", src)
        self.assertIn("Duplicate + Inputs", src)

    def test_handlers_exist(self):
        from mpynode.ui import mpynode_designer as m

        self.assertTrue(hasattr(m.NDMainWindow, "_on_duplicate_node_requested"))
        self.assertTrue(
            hasattr(m.NDMainWindow, "_on_duplicate_with_inputs_requested")
        )

    def test_duplicate_handler_flushes_unsaved_editor(self):
        """P0: the duplicate handler must FLUSH the source node's open editor to
        its plugs BEFORE serializing -- the editors only commit to the DG plugs
        on explicit Save, so an unsaved-but-typed expression would otherwise be
        lost on the copy. The flush must come BEFORE build_duplicate_node_command."""
        from mpynode.ui import mpynode_designer as m

        src = inspect.getsource(m.NDMainWindow._duplicate_node)
        self.assertIn("saveTabsForNode", src)
        # Compare against the CALL (`name(`) -- the bare name also appears in the
        # method's import line, which would precede the flush spuriously.
        self.assertLess(
            src.index("saveTabsForNode"),
            src.index("build_duplicate_node_command("),
            "must flush the editor BEFORE serializing the node",
        )

    def test_export_handler_flushes_unsaved_editor(self):
        """The .mpn export path shares the same stale-plug bug -- it must also
        flush the node's editor before serialize_node."""
        from mpynode.ui import mpynode_designer as m

        src = inspect.getsource(m.NDMainWindow._export_node_as_mpn)
        self.assertIn("saveTabsForNode", src)
        self.assertLess(
            src.index("saveTabsForNode"), src.index("serialize_node(")
        )


# ===========================================================================
# P0 regression: right-click Duplicate must copy TYPED-but-unsaved expressions.
# The per-tier code editors write their DG plug ONLY on an explicit Save, so
# duplicating read the stale plug. Fix = NDScriptTabWidget.saveTabsForNode()
# flushes the dirty tab before serialize.
# ===========================================================================
@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestDuplicateFlushesUnsavedEditor(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.src = MPyNode.create(name="typedNode")
        self.src.add_input_attr("alpha", "float", default_value=2.0)
        self.src.add_output_attr("out", "float")
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    def _widget_with_tab(self, node):
        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        w = NDScriptTabWidget()
        self._widgets.append(w)
        w.addOrRaiseTab(node)
        return w

    def _compute_plug(self, name):
        return mc.getAttr(name + "._computeSource") or ""

    def test_save_tabs_for_node_flushes_compute_to_plug(self):
        name  = self.src.get_name()
        w     = self._widget_with_tab(self.src)
        tab   = w.getAllTabs()[0]
        typed = "out = alpha * 3.0  # typed, not saved"
        tab.setText(typed)
        # Pre-condition: editor dirty, plug STALE (reproduces the user's bug).
        self.assertTrue(tab.hasUnsavedChanges())
        self.assertNotIn(typed, self._compute_plug(name))
        # The fix: flush the node's tab.
        w.saveTabsForNode(name)
        self.assertEqual(self._compute_plug(name), typed)

    def test_save_tabs_for_node_flushes_all_tiers(self):
        """P0: ALL expressions, not just Compute. Init must flush too."""
        name    = self.src.get_name()
        w       = self._widget_with_tab(self.src)
        tab     = w.getAllTabs()[0]
        compute = "out = alpha * 4.0"
        init    = "import math\nTAU = math.pi * 2"
        tab.setText(compute)
        # Init lives in the sister editor.
        self.assertIsNotNone(getattr(tab, "_init_editor", None))
        tab._init_editor.setText(init)
        self.assertTrue(tab.hasUnsavedChanges())
        w.saveTabsForNode(name)
        self.assertEqual(self._compute_plug(name), compute)
        self.assertEqual(self.src.get_init_expression(), init)

    def test_save_tabs_for_node_is_surgical(self):
        """Flushing one node must NOT commit a DIFFERENT node's unsaved tab."""
        from mpynode.wrappers._mpy_node import MPyNode

        other = MPyNode.create(name="otherNode")
        other.add_output_attr("out", "float")
        w = self._widget_with_tab(self.src)
        w.addOrRaiseTab(other)
        tabs = {t.getMPyNode().get_name(): t for t in w.getAllTabs()}
        tabs[self.src.get_name()].setText("out = alpha * 5.0")
        tabs[other.get_name()].setText("out = 99.0")
        w.saveTabsForNode(self.src.get_name())
        self.assertEqual(self._compute_plug(self.src.get_name()), "out = alpha * 5.0")
        # The other node's tab was NOT the target -> its plug stays stale.
        self.assertNotIn("99.0", self._compute_plug(other.get_name()))

    def test_flush_is_load_bearing_for_duplicate(self):
        """End-to-end: without the flush the copy loses the typed expression;
        with the flush the copy carries it."""
        from mpynode._base.commands import (
            build_duplicate_node_command,
            run_undoable,
        )

        name  = self.src.get_name()
        w     = self._widget_with_tab(self.src)
        tab   = w.getAllTabs()[0]
        typed = "out = alpha * 6.0"
        tab.setText(typed)

        # Duplicate WITHOUT flushing -> copy does NOT have the typed expression.
        cmd0 = build_duplicate_node_command(name, "mPyNode")
        dup0 = run_undoable(cmd0) or getattr(cmd0, "created_name", None)
        self.assertNotEqual(_wrap(dup0).get_compute_expression(), typed)

        # Flush, then duplicate -> copy carries the typed expression.
        w.saveTabsForNode(name)
        cmd1 = build_duplicate_node_command(name, "mPyNode")
        dup1 = run_undoable(cmd1) or getattr(cmd1, "created_name", None)
        self.assertEqual(_wrap(dup1).get_compute_expression(), typed)


if __name__ == "__main__":
    unittest.main()
