"""Coexist Py<->C++ convert/revert at the COMMAND layer: the gate predicate
(``is_convertible_to_cpp`` / ``_coexist_eligible``), ``_ConvertToCppCommand``
(attach, no delete), ``_RevertToPyCommand`` (detach), chunk-undo of both, and
the not-already-converted refusal.

Uses the plugin-provided ``stubCompiled`` compiled type (a genuine PLUGIN node
type, which the gate must accept -- unlike a stock built-in, which it must
reject). Reroute mechanics are covered by ``test_node_swap`` / ``test_coexist``;
here we assert orchestration, the gate, and undo fidelity."""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import (
    ensure_plugins_loaded, ensure_stub_compiled_plugin, standalone_init)


def setUpModule():
    standalone_init()


class TestCoexistEligible(unittest.TestCase):
    """``_coexist_eligible``: DG + locator + deformer + DAG transform + solver
    in; a non-locator DAG SHAPE stays out. Unit-level (stock nodes) so no mPy
    wiring is needed."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_dg_node_eligible(self):
        from mpynode._base.commands import _coexist_eligible
        n = mc.createNode("network")
        self.assertTrue(_coexist_eligible(n, "network"))

    def test_locator_eligible(self):
        from mpynode._base.commands import _coexist_eligible
        loc = mc.createNode("locator")
        self.assertTrue(_coexist_eligible(loc, "locator"))

    def test_transform_eligible_via_inputs_only_convert(self):
        """A transform's children follow PARENTAGE, not an edge, so its outputs
        are deliberately left in place and the user is warned about what did not
        get rewired (see ``node_swap.moves_outputs``). That makes it eligible --
        the convert is an interactive development step, not a production swap."""
        from mpynode._base.commands import _coexist_eligible
        t = mc.createNode("transform")
        self.assertTrue(_coexist_eligible(t, "transform"))

    def test_non_locator_dag_shape_excluded(self):
        """The one surviving type-shape exclusion: a DAG shape that is not a
        locator has no co-located-sibling story."""
        from mpynode._base.commands import _coexist_eligible
        shp = mc.listRelatives(mc.polySphere()[0], shapes=True, fullPath=True)[0]
        self.assertFalse(_coexist_eligible(shp, "mesh"))

    def test_deformer_eligible(self):
        """A geometryFilter's downstream hangs off ``outputGeometry[]``, which
        ``move_outputs`` relocates like any other output plug -- the type shape
        is no bar to a coexist convert."""
        from mpynode._base.commands import _coexist_eligible
        twk = mc.createNode("tweak")  # inherits geometryFilter
        self.assertTrue(_coexist_eligible(twk, "tweak"))

    def test_deformer_still_fails_the_full_gate_without_a_compiled_type(self):
        """Type-shape eligibility is only ONE gate. A stock deformer has no
        REGISTRY native type and no compiled sibling, so the user-facing
        predicate still refuses it -- widening ``_coexist_eligible`` does not
        make arbitrary deformers convertible."""
        from mpynode._base.commands import is_convertible_to_cpp
        twk = mc.createNode("tweak")
        self.assertFalse(is_convertible_to_cpp(twk, "tweak"))

    def test_solver_eligible(self):
        """A solver has no non-message output plugs, but an ikHandle names it
        through a SINGLE ``.message`` destination, which the destination-based
        message policy now moves -- so the sibling is no longer inert."""
        from mpynode._base.commands import _coexist_eligible
        slv = mc.createNode("ikRPsolver")
        self.assertTrue(_coexist_eligible(slv, "ikRPsolver"))


class TestConvertGate(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        ensure_stub_compiled_plugin()

    def test_classless_not_convertible(self):
        from mpynode import MPyNode
        from mpynode._base.commands import (
            is_convertible_to_cpp, compiled_type_for)

        n = MPyNode.create(name="gateClassless")
        self.assertIsNone(compiled_type_for(n.get_name(), "mPyNode"))
        self.assertFalse(is_convertible_to_cpp(n.get_name(), "mPyNode"))

    def test_classed_but_type_not_loaded_not_convertible(self):
        from mpynode import MPyNode
        from mpynode._base.commands import is_convertible_to_cpp

        n = MPyNode.create(name="gateNoType")
        n.set_py_class("mpynode_user.TotallyMadeUpType12345")
        self.assertFalse(is_convertible_to_cpp(n.get_name(), "mPyNode"))

    def test_classed_deriving_stock_type_not_convertible(self):
        # A Class whose derived type collides with a STOCK Maya built-in (e.g.
        # "Network" -> "network") must NOT be convertible: that type is not the
        # node's compiled C++ type. The gate requires a PLUGIN-provided type.
        from mpynode import MPyNode
        from mpynode._base.commands import (
            is_convertible_to_cpp, compiled_type_for)

        n = MPyNode.create(name="gateStock")
        n.set_py_class("mpynode_user.Network")  # -> "network" (STOCK built-in)
        self.assertIsNone(compiled_type_for(n.get_name(), "mPyNode"))
        self.assertFalse(is_convertible_to_cpp(n.get_name(), "mPyNode"))

    def test_classed_with_plugin_type_is_convertible(self):
        from mpynode import MPyNode
        from mpynode._base.commands import (
            is_convertible_to_cpp, compiled_type_for)

        n = MPyNode.create(name="gateOk")
        n.set_py_class("mpynode_user.StubCompiled")  # -> "stubCompiled" (plugin)
        self.assertEqual(
            compiled_type_for(n.get_name(), "mPyNode"), "stubCompiled")
        self.assertTrue(is_convertible_to_cpp(n.get_name(), "mPyNode"))

    def test_already_converted_not_convertible(self):
        # A converted node offers "Revert to Python", not another convert.
        from mpynode import MPyNode
        from mpynode._base.node_swap import attach_compiled
        from mpynode._base.commands import is_convertible_to_cpp

        n = MPyNode.create(name="gateConverted")
        n.set_py_class("mpynode_user.StubCompiled")
        attach_compiled(n.get_name(), "stubCompiled")
        self.assertFalse(is_convertible_to_cpp(n.get_name(), "mPyNode"))


class TestConvertCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        ensure_stub_compiled_plugin()
        try:
            mc.flushUndo()
        except Exception:
            pass

    def _make_src(self):
        from mpynode import MPyNode
        n = MPyNode.create(name="cvt")
        n.add_input_attr("inA", "float")   # connection-driven input
        n.add_input_attr("inB", "float")   # plain-value input
        n.add_output_attr("outC", "float")
        mc.setAttr("cvt.inB", 5.0)
        n.set_py_class("mpynode_user.StubCompiled")  # -> "stubCompiled"
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", "cvt.inA")
        mc.connectAttr("cvt.outC", down + ".i")
        return n, up, down

    def test_convert_coexists_without_deleting_python(self):
        from mpynode._base.commands import (
            build_convert_to_cpp_command, run_undoable, is_converted,
            linked_compiled_node)

        _, up, down = self._make_src()
        result = run_undoable(build_convert_to_cpp_command("cvt", "mPyNode"))
        # Convert returns the PYTHON node name (it stays; nothing is deleted).
        self.assertEqual(result, "cvt")
        self.assertTrue(mc.objExists("cvt"))
        self.assertEqual(mc.nodeType("cvt"), "mPyNode")
        # A hidden compiled sibling now exists + is linked.
        self.assertTrue(is_converted("cvt"))
        cpp = linked_compiled_node("cvt")
        self.assertEqual(mc.nodeType(cpp), "stubCompiled")
        # Output MOVED to cpp; input DUPLICATED (both fan off up.o); static copied.
        self.assertTrue(mc.isConnected(cpp + ".outC", down + ".i"))
        self.assertFalse(mc.isConnected("cvt.outC", down + ".i"))
        self.assertTrue(mc.isConnected(up + ".o", cpp + ".inA"))
        self.assertTrue(mc.isConnected(up + ".o", "cvt.inA"))
        self.assertAlmostEqual(mc.getAttr(cpp + ".inB"), 5.0)

    def test_double_convert_refused(self):
        from mpynode._base.commands import (
            build_convert_to_cpp_command, run_undoable)

        self._make_src()
        run_undoable(build_convert_to_cpp_command("cvt", "mPyNode"))
        with self.assertRaises(Exception):
            run_undoable(build_convert_to_cpp_command("cvt", "mPyNode"))

    def test_classless_command_raises(self):
        from mpynode import MPyNode
        from mpynode._base.commands import (
            build_convert_to_cpp_command, run_undoable)

        MPyNode.create(name="noClass")
        with self.assertRaises(Exception):
            run_undoable(build_convert_to_cpp_command("noClass", "mPyNode"))


class TestRevertCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        ensure_stub_compiled_plugin()
        try:
            mc.flushUndo()
        except Exception:
            pass

    def _make_and_convert(self):
        from mpynode import MPyNode
        from mpynode._base.commands import (
            build_convert_to_cpp_command, run_undoable)

        n = MPyNode.create(name="rv")
        n.add_input_attr("inA", "float")
        n.add_output_attr("outC", "float")
        n.set_py_class("mpynode_user.StubCompiled")
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", "rv.inA")
        mc.connectAttr("rv.outC", down + ".i")
        run_undoable(build_convert_to_cpp_command("rv", "mPyNode"))
        return up, down

    def test_revert_restores_python_and_deletes_cpp(self):
        from mpynode._base.commands import (
            build_revert_to_py_command, run_undoable, is_converted,
            linked_compiled_node)

        up, down = self._make_and_convert()
        cpp = linked_compiled_node("rv")
        self.assertTrue(mc.objExists(cpp))

        result = run_undoable(build_revert_to_py_command("rv", "mPyNode"))
        self.assertEqual(result, "rv")
        self.assertFalse(mc.objExists(cpp))           # cpp deleted
        self.assertFalse(is_converted("rv"))          # link gone
        self.assertFalse(
            mc.attributeQuery("mpyCompiledLink", node="rv", exists=True))
        self.assertTrue(mc.isConnected("rv.outC", down + ".i"))  # output back
        self.assertTrue(mc.isConnected(up + ".o", "rv.inA"))     # input intact

    def test_revert_unconverted_raises(self):
        from mpynode import MPyNode
        from mpynode._base.commands import (
            build_revert_to_py_command, run_undoable)

        MPyNode.create(name="plain")
        with self.assertRaises(Exception):
            run_undoable(build_revert_to_py_command("plain", "mPyNode"))


class TestNoteCycleBaseline(unittest.TestCase):
    """``cycle_introduced`` must reflect a cycle NEWLY introduced by the convert,
    not one that already existed through the node. cycleCheck is patched (a real
    persisting DG cycle can't be built from the attr-less-ish stub, and
    interpreted mPy nodes have selective affects by design)."""

    def test_preexisting_cycle_not_reported_as_introduced(self):
        from unittest import mock
        from mpynode._base import commands

        cmd = commands._ConvertToCppCommand("n", "mPyNode")
        cmd._pre_cycle = True  # a cycle already ran through the node pre-convert
        with mock.patch.object(commands.cmds, "cycleCheck",
                               return_value=["n.x"]):
            cmd._note_cycle("n")
        self.assertFalse(cmd.cycle_introduced)

    def test_newly_introduced_cycle_is_reported(self):
        from unittest import mock
        from mpynode._base import commands

        cmd = commands._ConvertToCppCommand("n", "mPyNode")
        cmd._pre_cycle = False  # no cycle before the convert
        with mock.patch.object(commands.cmds, "cycleCheck",
                               return_value=["n.x"]):
            cmd._note_cycle("n")
        self.assertTrue(cmd.cycle_introduced)


class TestHiddenContract(unittest.TestCase):
    """The compiled C++ sibling is HIDDEN from the Node Designer: its type is not
    registered, so it never appears in the scene tree (``all_native_types`` /
    ``MPyNode.ls``) and can't be wrapped. The Python node stays visible."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        ensure_stub_compiled_plugin()

    def test_cpp_sibling_is_hidden_python_is_visible(self):
        from mpynode import MPyNode
        from mpynode._base.commands import (
            build_convert_to_cpp_command, run_undoable, linked_compiled_node)
        from mpynode._node_registry import get_spec, wrap_node

        n = MPyNode.create(name="hc")
        n.set_py_class("mpynode_user.StubCompiled")
        run_undoable(build_convert_to_cpp_command("hc", "mPyNode"))
        cpp = linked_compiled_node("hc")
        cpp_type = mc.nodeType(cpp)

        # The compiled type is not registered -> not resolvable / wrappable.
        self.assertIsNone(get_spec(cpp_type))
        self.assertIsNone(wrap_node(cpp, cpp_type))
        # The tree lists Python nodes but not the hidden sibling.
        listed = [w.get_name() for w in MPyNode.ls()]
        self.assertIn("hc", listed)
        self.assertNotIn(cpp, listed)


class TestChunkUndo(unittest.TestCase):
    """Convert + revert must round-trip through Maya's chunk-undo -- the whole
    point of the no-op undoIt/redoIt contract. Verifies lockNode + addAttr +
    delete all ride the chunk cleanly (the delete-of-a-locked-node hazard)."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        ensure_stub_compiled_plugin()
        try:
            mc.flushUndo()
        except Exception:
            pass

    def _make(self):
        from mpynode import MPyNode
        n = MPyNode.create(name="cu")
        n.add_input_attr("inA", "float")
        n.add_output_attr("outC", "float")
        n.set_py_class("mpynode_user.StubCompiled")
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", "cu.inA")
        mc.connectAttr("cu.outC", down + ".i")
        return up, down

    def test_convert_undo_restores_exact_pre_convert(self):
        from mpynode._base.commands import (
            build_convert_to_cpp_command, run_undoable, is_converted,
            linked_compiled_node)

        up, down = self._make()
        run_undoable(build_convert_to_cpp_command("cu", "mPyNode"))
        cpp = linked_compiled_node("cu")
        mc.undo()
        # cpp gone, link gone, outputs BACK on the Python node.
        self.assertFalse(mc.objExists(cpp))
        self.assertFalse(is_converted("cu"))
        self.assertFalse(
            mc.attributeQuery("mpyCompiledLink", node="cu", exists=True))
        self.assertTrue(mc.isConnected("cu.outC", down + ".i"))
        self.assertTrue(mc.isConnected(up + ".o", "cu.inA"))

    def test_revert_undo_restores_converted(self):
        from mpynode._base.commands import (
            build_convert_to_cpp_command, build_revert_to_py_command,
            run_undoable, is_converted, linked_compiled_node)

        up, down = self._make()
        run_undoable(build_convert_to_cpp_command("cu", "mPyNode"))
        run_undoable(build_revert_to_py_command("cu", "mPyNode"))
        self.assertFalse(is_converted("cu"))
        mc.undo()  # undo the revert -> converted state returns
        self.assertTrue(is_converted("cu"))
        cpp = linked_compiled_node("cu")
        self.assertTrue(mc.objExists(cpp))
        self.assertTrue(mc.isConnected(cpp + ".outC", down + ".i"))

    def test_convert_revert_convert_idempotent_link(self):
        from mpynode._base.commands import (
            build_convert_to_cpp_command, build_revert_to_py_command,
            run_undoable, is_converted)

        self._make()
        run_undoable(build_convert_to_cpp_command("cu", "mPyNode"))
        run_undoable(build_revert_to_py_command("cu", "mPyNode"))
        # Re-convert must NOT raise on a duplicate addAttr of the link.
        run_undoable(build_convert_to_cpp_command("cu", "mPyNode"))
        self.assertTrue(is_converted("cu"))


if __name__ == "__main__":
    unittest.main()
