"""node_swap SSOT primitives: value / multi-array / connection transfer + the
swap_node orchestration. Uses stock Maya `network` nodes (no mPy plugin needed)
so it exercises the pure Maya-cmds mechanics in isolation."""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


def _net(attrs_scalar=False, attrs_multi=False, attrs_io=False):
    n = mc.createNode("network")
    if attrs_scalar:
        mc.addAttr(n, ln="k", at="double")
        mc.addAttr(n, ln="v3", at="double3")
        for c in "XYZ":
            mc.addAttr(n, ln="v3" + c, at="double", parent="v3")
        mc.addAttr(n, ln="s", dt="string")
    if attrs_multi:
        mc.addAttr(n, ln="arr", at="double", multi=True)
    if attrs_io:
        mc.addAttr(n, ln="inp", at="double")
        mc.addAttr(n, ln="out", at="double")
    return n


class TestCopyValues(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_copies_scalar_compound_string(self):
        from mpynode._base.node_swap import copy_values

        src = _net(attrs_scalar=True)
        dst = _net(attrs_scalar=True)
        mc.setAttr(src + ".k", 7.5)
        mc.setAttr(src + ".v3", 1.0, 2.0, 3.0, type="double3")
        mc.setAttr(src + ".s", "hi", type="string")
        copy_values(src, dst)
        self.assertAlmostEqual(mc.getAttr(dst + ".k"), 7.5)
        self.assertEqual(mc.getAttr(dst + ".v3"), [(1.0, 2.0, 3.0)])
        self.assertEqual(mc.getAttr(dst + ".s"), "hi")

    def test_skips_attr_absent_on_dst(self):
        from mpynode._base.node_swap import copy_values

        src = _net(attrs_scalar=True)
        dst = _net()  # no dynamic attrs
        mc.setAttr(src + ".k", 9.0)
        copy_values(src, dst)  # must not raise
        self.assertFalse(mc.attributeQuery("k", node=dst, exists=True))


def _arr():
    """A node carrying one attr of every typed-array data type."""
    n = mc.createNode("network")
    for ln, dt in (("ia", "Int32Array"), ("da", "doubleArray"),
                   ("va", "vectorArray"), ("pa", "pointArray"),
                   ("sa", "stringArray"), ("ma", "matrixArray")):
        mc.addAttr(n, ln=ln, dt=dt)
    return n


class TestCopyArrayValues(unittest.TestCase):
    """Typed ARRAY data attrs are neither scalars nor multis, so they fell
    through BOTH copy paths and reached the compiled sibling EMPTY. On a
    blendShape the baked tables ARE the deform, so a convert silently produced
    the wrong shape while reporting only the dropped target connections
    (measured: targetDeltas 319044 -> 0, all 1306 verts wrong)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_copies_flat_numeric_arrays(self):
        from mpynode._base.node_swap import copy_values

        src, dst = _arr(), _arr()
        mc.setAttr(src + ".ia", [1, 2, 3, 4], type="Int32Array")
        mc.setAttr(src + ".da", [1.5, -2.25, 3.0], type="doubleArray")
        copy_values(src, dst)
        self.assertEqual(list(mc.getAttr(dst + ".ia")), [1, 2, 3, 4])
        self.assertEqual(list(mc.getAttr(dst + ".da")), [1.5, -2.25, 3.0])

    def test_copies_counted_arrays(self):
        from mpynode._base.node_swap import copy_values

        src, dst = _arr(), _arr()
        vec = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        mc.setAttr(src + ".va", len(vec), *vec, type="vectorArray")
        pts = [(1.0, 2.0, 3.0, 1.0)]
        mc.setAttr(src + ".pa", len(pts), *pts, type="pointArray")
        strs = ["alpha", "beta"]
        mc.setAttr(src + ".sa", len(strs), *strs, type="stringArray")
        copy_values(src, dst)
        self.assertEqual(list(mc.getAttr(dst + ".va")), vec)
        self.assertEqual(list(mc.getAttr(dst + ".pa")), pts)
        self.assertEqual(list(mc.getAttr(dst + ".sa")), strs)

    def test_copies_matrix_array(self):
        """``cmds.getAttr`` returns None for matrixArray however it is set, so
        both sides go through ``_array_value`` -- which is also the only reader
        that works (``asMObject()`` reports 0 for a plug holding 2)."""
        from mpynode._base.node_swap import _array_value, copy_values

        src, dst = _arr(), _arr()
        ident        = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
        shift        = list(ident)
        shift[12:15] = [7.0, 8.0, 9.0]
        mats         = [ident, shift]
        mc.setAttr(src + ".ma", len(mats), *mats, type="matrixArray")
        copy_values(src, dst)

        got = _array_value(dst + ".ma", "matrixArray")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[1][12:15], [7.0, 8.0, 9.0])

    def test_the_helpers_round_trip_every_array_type(self):
        """The real guard. ``copy_values`` calls ``copyAttr(values=True)``
        first, and that DOES carry a DYNAMIC array on a stock node -- so the
        end-to-end tests above would pass even with the read/write helpers
        broken. The plug-in-declared tables that actually failed are static, and
        these are the helpers that rescue them, so exercise them directly."""
        from mpynode._base.node_swap import _array_value, _set_array_value

        ident = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
        cases = (
            ("ia", "Int32Array", [3, 1, 4, 1, 5]),
            ("da", "doubleArray", [2.5, -0.25]),
            ("va", "vectorArray", [(1.0, 2.0, 3.0)]),
            ("pa", "pointArray", [(1.0, 2.0, 3.0, 1.0)]),
            ("sa", "stringArray", ["x", "y"]),
            ("ma", "matrixArray", [ident]),
        )
        src, dst = _arr(), _arr()
        for attr, typ, val in cases:
            sp, dp = "%s.%s" % (src, attr), "%s.%s" % (dst, attr)
            if typ in ("Int32Array", "doubleArray"):
                mc.setAttr(sp, val, type=typ)
            else:
                mc.setAttr(sp, len(val), *val, type=typ)
            got = _array_value(sp, typ)
            self.assertEqual(len(got), len(val),
                             "%s: read back %r" % (typ, got))
            _set_array_value(dp, typ, got)
            self.assertEqual(_array_value(dp, typ), got, "%s round-trip" % typ)

    def test_an_empty_source_array_does_not_raise(self):
        from mpynode._base.node_swap import _set_array_value

        dst = _arr()
        _set_array_value(dst + ".da", "doubleArray", [])
        _set_array_value(dst + ".va", "vectorArray", None)
        self.assertIsNone(mc.getAttr(dst + ".da"))

    def test_array_absent_on_dst_is_skipped(self):
        from mpynode._base.node_swap import copy_values

        src, dst = _arr(), mc.createNode("network")
        mc.setAttr(src + ".da", [1.0], type="doubleArray")
        copy_values(src, dst)          # must not raise
        self.assertFalse(mc.attributeQuery("da", node=dst, exists=True))


class TestCopyMultiValues(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_copies_multi_elements_by_index(self):
        from mpynode._base.node_swap import copy_multi_values

        src = _net(attrs_multi=True)
        dst = _net(attrs_multi=True)
        mc.setAttr(src + ".arr[0]", 1.0)
        mc.setAttr(src + ".arr[2]", 3.0)
        copy_multi_values(src, dst)
        self.assertAlmostEqual(mc.getAttr(dst + ".arr[0]"), 1.0)
        self.assertAlmostEqual(mc.getAttr(dst + ".arr[2]"), 3.0)
        self.assertEqual(
            sorted(mc.getAttr(dst + ".arr", multiIndices=True) or []), [0, 2])

    def _add_weightlist(self, n):
        # multi-of-compound with a nested multi child, mirroring skinCluster
        # weightList[i].weights[j] (the canonical silent-loss case).
        mc.addAttr(n, ln="wl", at="compound", nc=1, multi=True)
        mc.addAttr(n, ln="wts", at="double", multi=True, parent="wl")

    def test_copies_nested_multi_of_compound(self):
        from mpynode._base.node_swap import copy_multi_values

        src = mc.createNode("network"); self._add_weightlist(src)
        dst = mc.createNode("network"); self._add_weightlist(dst)
        mc.setAttr(src + ".wl[0].wts[2]", 0.25)
        mc.setAttr(src + ".wl[1].wts[0]", 0.75)
        copy_multi_values(src, dst)
        self.assertAlmostEqual(mc.getAttr(dst + ".wl[0].wts[2]"), 0.25)
        self.assertAlmostEqual(mc.getAttr(dst + ".wl[1].wts[0]"), 0.75)

    def test_copies_nested_multi_when_children_report_dotted_names(self):
        """`attributeQuery(listChildren=True)` returns a DOTTED path on some
        types and a BARE name on others -- stock `cluster`/`blendShape`/`softMod`
        report `weightList.weights`, while `skinCluster` and addAttr-built
        compounds report `weights`. `se`/`de` already carry the ancestors, so
        appending the dotted form re-adds the parent and yields
        `cluster1.weightList[0].weightList.weights`, which does not resolve."""
        from mpynode._base.node_swap import copy_multi_values

        src = mc.createNode("cluster")
        dst = mc.createNode("cluster")
        self.assertIn(
            "weightList.weights",
            mc.attributeQuery("weightList", node=src, listChildren=True) or [],
            "fixture must exercise the DOTTED form or the test is vacuous")
        mc.setAttr(src + ".weightList[0].weights[2]", 0.25)
        mc.setAttr(src + ".weightList[0].weights[5]", 0.75)
        copy_multi_values(src, dst)
        self.assertAlmostEqual(
            mc.getAttr(dst + ".weightList[0].weights[2]"), 0.25)
        self.assertAlmostEqual(
            mc.getAttr(dst + ".weightList[0].weights[5]"), 0.75)


class TestCopyAliases(unittest.TestCase):
    """Aliases are the blendShape's user-facing surface: `browUp` IS
    `weight[0]`. copyAttr never carries them, so the swap has to."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_reapplies_alias_and_keyable_state(self):
        from mpynode._base.node_swap import copy_aliases, copy_multi_values

        src = _net(attrs_multi=True)
        dst = _net(attrs_multi=True)
        mc.setAttr(src + ".arr[0]", 0.5)
        mc.setAttr(src + ".arr[0]", keyable=True)
        mc.aliasAttr("browUp", src + ".arr[0]")

        copy_multi_values(src, dst)
        self.assertEqual(copy_aliases(src, dst), [])

        self.assertAlmostEqual(mc.getAttr(dst + ".browUp"), 0.5)
        self.assertTrue(
            mc.getAttr(dst + ".arr[0]", keyable=True),
            "an aliased element is a named rig channel -- it must stay keyable",
        )
        self.assertIn("browUp", mc.listAttr(dst, multi=True, keyable=True) or [])

    def test_non_keyable_alias_is_not_forced_keyable(self):
        """The flag is COPIED, not forced -- the array-inputs-are-not-keyable
        rule stays intact for anything the source did not opt in."""
        from mpynode._base.node_swap import copy_aliases, copy_multi_values

        src = _net(attrs_multi=True)
        dst = _net(attrs_multi=True)
        mc.setAttr(src + ".arr[0]", 0.5)
        mc.setAttr(src + ".arr[0]", keyable=False)
        mc.aliasAttr("quiet", src + ".arr[0]")

        copy_multi_values(src, dst)
        copy_aliases(src, dst)
        self.assertFalse(mc.getAttr(dst + ".arr[0]", keyable=True))

    def test_reports_alias_whose_attr_is_missing_on_dst(self):
        from mpynode._base.node_swap import copy_aliases

        src = _net(attrs_multi=True)
        dst = _net()  # no `arr` at all -- schema drift
        mc.setAttr(src + ".arr[0]", 1.0)
        mc.aliasAttr("browUp", src + ".arr[0]")

        dropped = copy_aliases(src, dst)
        self.assertEqual(len(dropped), 1, dropped)
        self.assertIn("browUp", dropped[0])

    def test_no_aliases_is_a_clean_no_op(self):
        from mpynode._base.node_swap import copy_aliases

        self.assertEqual(copy_aliases(_net(attrs_multi=True), _net(attrs_multi=True)), [])

    def test_swap_node_reports_an_alias_it_cannot_carry(self):
        """`swap_node` builds a bare node of the target TYPE. A real compiled
        type declares the same attrs, so the alias lands -- but when the
        destination type has no such attribute the alias must be REPORTED in
        `dropped`, never silently lost."""
        from mpynode._base.node_swap import swap_node

        src = _net(attrs_multi=True)
        mc.setAttr(src + ".arr[1]", 0.25)
        mc.aliasAttr("mouthOpen", src + ".arr[1]")
        # stock `network` has no `arr`, standing in for schema drift
        dst, dropped = swap_node(src, "network")
        self.assertFalse(mc.objExists(dst + ".mouthOpen"))
        self.assertTrue(any("mouthOpen" in d for d in dropped), dropped)

    def test_alias_survives_the_delete_and_rename_swap_node_performs(self):
        """The alias is applied while `src` is still alive, then `src` is
        deleted and `dst` is renamed into its place. Neither step may drop it."""
        from mpynode._base.node_swap import copy_aliases, copy_multi_values

        src = _net(attrs_multi=True)
        dst = _net(attrs_multi=True)
        mc.setAttr(src + ".arr[1]", 0.25)
        mc.aliasAttr("mouthOpen", src + ".arr[1]")
        copy_multi_values(src, dst)
        copy_aliases(src, dst)

        short = src.split("|")[-1]
        mc.delete(src)
        dst = mc.rename(dst, short)
        self.assertAlmostEqual(mc.getAttr(dst + ".mouthOpen"), 0.25)


class TestRewire(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_moves_in_and_out_connections(self):
        from mpynode._base.node_swap import rewire

        src = _net(attrs_io=True)
        dst = _net(attrs_io=True)
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", src + ".inp")
        mc.connectAttr(src + ".out", down + ".i")
        dropped = rewire(src, dst)
        self.assertTrue(mc.isConnected(up + ".o", dst + ".inp"))
        self.assertTrue(mc.isConnected(dst + ".out", down + ".i"))
        self.assertEqual(dropped, [])

    def test_reports_dropped_when_attr_absent(self):
        from mpynode._base.node_swap import rewire

        src = _net(attrs_io=True)
        dst = _net()  # no inp/out
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        mc.connectAttr(up + ".o", src + ".inp")
        dropped = rewire(src, dst)
        self.assertTrue(any("inp" in d for d in dropped))

    def test_moves_dual_role_passthrough_connection(self):
        """A plug that is BOTH driven and driving (up.o -> src.pt -> down.i) must
        have BOTH edges moved onto dst in the CORRECT direction. Per-plug
        connectionInfo(isSource) misclassifies the incoming edge (regression
        guard for the rewire direction bug)."""
        from mpynode._base.node_swap import rewire

        src = mc.createNode("network"); mc.addAttr(src, ln="pt", at="double")
        dst = mc.createNode("network"); mc.addAttr(dst, ln="pt", at="double")
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", src + ".pt")    # incoming
        mc.connectAttr(src + ".pt", down + ".i")  # outgoing
        dropped = rewire(src, dst)
        self.assertTrue(mc.isConnected(up + ".o", dst + ".pt"),
                        "incoming edge must be preserved, correctly directed")
        self.assertTrue(mc.isConnected(dst + ".pt", down + ".i"),
                        "outgoing edge must be preserved, correctly directed")
        self.assertEqual(dropped, [])

    def test_dual_role_incoming_survives_unstealable_outgoing(self):
        """Deterministic dual-role regression. When the outgoing edge cannot be
        force-stolen (locked destination), src.pt stays a source for the whole
        loop, so per-plug connectionInfo(isSource) mislabels the INCOMING edge
        as outgoing and reverses it (up.o -> dst.pt lost, dst.pt -> up.o
        spuriously created). Per-EDGE classification must keep it correct."""
        from mpynode._base.node_swap import rewire

        src = mc.createNode("network"); mc.addAttr(src, ln="pt", at="double")
        dst = mc.createNode("network"); mc.addAttr(dst, ln="pt", at="double")
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", src + ".pt")    # incoming
        mc.connectAttr(src + ".pt", down + ".i")  # outgoing
        mc.setAttr(down + ".i", lock=True)        # unstealable outgoing
        rewire(src, dst)
        self.assertTrue(mc.isConnected(up + ".o", dst + ".pt"),
                        "incoming edge must move onto dst in the correct direction")
        self.assertFalse(mc.isConnected(dst + ".pt", up + ".o"),
                         "must NOT create a reversed dst -> up edge")


class TestIsInfra(unittest.TestCase):
    def test_classifies_infra_vs_compute_plugs(self):
        from mpynode._base.node_swap import _is_infra

        self.assertTrue(_is_infra("x.instObjGroups[0].objectGroups[0]"))
        self.assertTrue(_is_infra("x.hyperLayout"))
        self.assertTrue(_is_infra("x.mpyCompiledLink"))
        self.assertTrue(_is_infra("x.mpyInterpretedLink"))
        self.assertFalse(_is_infra("x.inp"))
        self.assertFalse(_is_infra("x.out[3]"))

    def test_message_is_classified_by_destination_not_by_name(self):
        """`message` is deliberately NOT a blanket infra plug: it carries BOTH
        registry membership and genuine functional references (an ikHandle names
        its solver through it). Classifying it by the LOCAL name would deny both,
        leaving a converted solver inert."""
        from mpynode._base.node_swap import _is_infra

        self.assertFalse(_is_infra("x.message"))


class TestMessageDestinationPolicy(unittest.TestCase):
    """A `.message` edge is registry PLUMBING or a FUNCTIONAL reference, and the
    two are told apart by the DESTINATION, not the source attr name.

    Every registry Maya ships accumulates members in a MULTI (`shaders[]`,
    `textures[]`, `utilities[]`, `postProcesses[]`, `dnSetMembers[]`,
    `hyperPosition[].dependNode`, `ikSystem.ikSolver[]`), while a functional
    reference names exactly ONE node in a SINGLE plug (`ikHandle.ikSolver`,
    `ikHandle.startJoint`). Note `ikSystem.ikSolver[1]` vs `ikHandle.ikSolver`:
    same attr NAME, opposite meaning -- so an attr-name denylist cannot work, and
    an isAType denylist cannot either (ikHandle isAType containerBase)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_indexed_destination_is_a_registry_slot(self):
        from mpynode._base.node_swap import _is_message_registry_slot

        self.assertTrue(_is_message_registry_slot("defaultShaderList1.shaders[6]"))
        self.assertTrue(_is_message_registry_slot("probeSet.dnSetMembers[0]"))
        self.assertTrue(_is_message_registry_slot("ikSystem.ikSolver[1]"))
        self.assertTrue(
            _is_message_registry_slot("hyperLayout1.hyperPosition[0].dependNode"),
            "the INDEX may sit on an ancestor, not the leaf")

    def test_single_destination_is_a_functional_reference(self):
        from mpynode._base.node_swap import _is_message_registry_slot

        self.assertFalse(_is_message_registry_slot("ikHandle1.ikSolver"))
        self.assertFalse(_is_message_registry_slot("ikHandle1.startJoint"))

    def test_move_outputs_moves_a_functional_message_reference(self):
        from mpynode._base.node_swap import move_outputs

        src = _net(); dst = _net()
        down = mc.createNode("network"); mc.addAttr(down, ln="ref", at="message")
        mc.connectAttr(src + ".message", down + ".ref")
        self.assertEqual(move_outputs(src, dst), [])
        self.assertTrue(mc.isConnected(dst + ".message", down + ".ref"))
        self.assertFalse(mc.isConnected(src + ".message", down + ".ref"))

    def test_move_outputs_leaves_a_registry_membership_slot_alone(self):
        from mpynode._base.node_swap import move_outputs

        src = _net(); dst = _net()
        reg = mc.createNode("network")
        mc.addAttr(reg, ln="members", at="message", multi=True)
        mc.connectAttr(src + ".message", reg + ".members[0]")
        move_outputs(src, dst)
        self.assertTrue(mc.isConnected(src + ".message", reg + ".members[0]"),
                        "membership must stay with the node that is a member")
        self.assertFalse(mc.isConnected(dst + ".message", reg + ".members[0]"))

    def test_real_set_membership_survives_a_move(self):
        """The measured case: every mPy type's only `.message` edges in a normal
        scene are `objectSet.dnSetMembers[]` and `hyperLayout.hyperPosition[]`."""
        from mpynode._base.node_swap import move_outputs

        src = _net(); dst = _net()
        st = mc.sets(name="memberSet", empty=True)
        mc.sets(src, add=st)
        move_outputs(src, dst)
        self.assertIn(src, mc.sets(st, query=True) or [],
                      "a convert must not silently remove the node from its set")

    def test_ik_handle_solver_reference_is_moved(self):
        """The motivating case. An ikSolver has NO non-message output plugs; the
        handle names it through a SINGLE `.message` destination, so denying
        message by name left a converted solver completely inert."""
        from mpynode._base.node_swap import move_outputs

        j1 = mc.joint(p=(0, 0, 0)); mc.joint(p=(0, 2, 0)); j3 = mc.joint(p=(0, 4, 0))
        handle = mc.ikHandle(sj=j1, ee=j3, solver="ikRPsolver")[0]
        py     = (mc.ls(type="ikRPsolver") or [None])[0]
        cpp    = mc.createNode("ikRPsolver")

        move_outputs(py, cpp)

        self.assertEqual(
            mc.listConnections(handle + ".ikSolver", source=True,
                               destination=False) or [], [cpp],
            "the handle must now resolve its solver to the sibling")
        self.assertIn(
            py, mc.listConnections("ikSystem.ikSolver", source=True,
                                   destination=False) or [],
            "but the solver REGISTRY (a multi) must keep the original")


class TestMovesOutputs(unittest.TestCase):
    """Whether a coexist convert MOVES the output edges or duplicates inputs
    only. A DAG transform's consumers include its CHILDREN, and parentage is not
    an edge -- moving `worldMatrix` while the children keep following the
    interpreted node would silently HALF-convert the scene, so a transform gets
    an inputs-only convert and the user is told what stayed behind."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_dg_node_moves_outputs(self):
        from mpynode._base.node_swap import moves_outputs
        self.assertTrue(moves_outputs(mc.createNode("network")))

    def test_locator_shape_moves_outputs(self):
        from mpynode._base.node_swap import moves_outputs
        self.assertTrue(moves_outputs(mc.createNode("locator")))

    def test_transform_does_not_move_outputs(self):
        from mpynode._base.node_swap import moves_outputs
        self.assertFalse(moves_outputs(mc.createNode("transform")))


class TestOpmRelayCompanion(unittest.TestCase):
    """`mPyTransform` auto-builds a stock `fourByFourMatrix` that takes its flat
    matrix output and drives its OWN `offsetParentMatrix`. That relay is private
    wiring, not user downstream: it must stay out of the "what will not be
    rewired" report and be deleted with the sibling, or every convert/revert
    cycle leaks one.

    It is found the same way `ensure_opm_relay` tests for it -- the driver of
    `offsetParentMatrix` -- and then CONFIRMED exclusive to the node, so nothing
    the user owns is ever deleted."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _owner_with_relay(self):
        owner = mc.createNode("transform")
        mc.addAttr(owner, ln="flat", at="double", multi=True)
        relay = mc.createNode("fourByFourMatrix")
        mc.connectAttr(owner + ".flat[0]", relay + ".in00")
        mc.connectAttr(relay + ".output", owner + ".offsetParentMatrix")
        return owner, relay

    def test_detects_the_nodes_own_relay(self):
        from mpynode._base.node_swap import _opm_relay

        owner, relay = self._owner_with_relay()
        self.assertEqual(_opm_relay(owner), relay)

    def test_a_relay_shared_with_a_third_party_is_not_private(self):
        from mpynode._base.node_swap import _opm_relay

        owner, relay = self._owner_with_relay()
        outsider = mc.createNode("network")
        mc.addAttr(outsider, ln="m", at="matrix")
        mc.connectAttr(relay + ".output", outsider + ".m")
        self.assertIsNone(_opm_relay(owner),
                          "shared with a third party -- never delete it")

    def test_a_user_driven_offset_parent_matrix_is_not_a_relay(self):
        """The user wiring their own node into `offsetParentMatrix` is an ORDINARY
        input (duplicate_inputs carries it). It only drives the transform, never
        reads back from it, so it must not be mistaken for the private relay."""
        from mpynode._base.node_swap import _opm_relay

        owner = mc.createNode("transform")
        drv   = mc.createNode("fourByFourMatrix")
        mc.connectAttr(drv + ".output", owner + ".offsetParentMatrix")
        self.assertIsNone(_opm_relay(owner))

    def test_no_relay_is_a_clean_none(self):
        from mpynode._base.node_swap import _opm_relay

        self.assertIsNone(_opm_relay(mc.createNode("transform")))
        self.assertIsNone(_opm_relay(mc.createNode("network")))


class TestDownstreamDependents(unittest.TestCase):
    """What an inputs-only convert leaves behind, for the pre-convert warning.
    Reports exactly the edges `move_outputs` WOULD have moved, plus DAG children
    (which are not edges at all)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_reports_output_edges_and_dag_children(self):
        from mpynode._base.node_swap import downstream_dependents

        xf  = mc.createNode("transform", name="drv")
        kid = mc.createNode("transform", name="kid", parent=xf)
        sink = mc.createNode("network"); mc.addAttr(sink, ln="m", at="matrix")
        mc.connectAttr(xf + ".worldMatrix[0]", sink + ".m")

        edges, children = downstream_dependents(xf)
        self.assertTrue(any(r == sink + ".m" for _l, r in edges), edges)
        self.assertEqual([c.split("|")[-1] for c in children], [kid.split("|")[-1]])

    def test_excludes_infra_and_private_companion_wiring(self):
        from mpynode._base.node_swap import downstream_dependents

        xf = mc.createNode("transform")
        mc.addAttr(xf, ln="flat", at="double", multi=True)
        relay = mc.createNode("fourByFourMatrix")
        mc.connectAttr(xf + ".flat[0]", relay + ".in00")
        mc.connectAttr(relay + ".output", xf + ".offsetParentMatrix")
        st = mc.sets(name="s", empty=True); mc.sets(xf, add=st)

        edges, _children = downstream_dependents(xf)
        remotes = [r for _l, r in edges]
        self.assertFalse([r for r in remotes if r.startswith(relay + ".")],
                         "the node's own relay is private wiring, not downstream")
        self.assertFalse([r for r in remotes if "dnSetMembers" in r],
                         "set membership is not downstream either")


class TestDuplicateInputs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_fans_off_same_upstream_keeping_src(self):
        from mpynode._base.node_swap import duplicate_inputs

        src = _net(attrs_io=True)
        dst = _net(attrs_io=True)
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        mc.connectAttr(up + ".o", src + ".inp")
        dropped = duplicate_inputs(src, dst)
        # dst's input now fans off the SAME upstream ...
        self.assertTrue(mc.isConnected(up + ".o", dst + ".inp"))
        # ... and src KEEPS its input (not moved).
        self.assertTrue(mc.isConnected(up + ".o", src + ".inp"))
        self.assertEqual(dropped, [])

    def test_reports_dropped_when_attr_absent(self):
        from mpynode._base.node_swap import duplicate_inputs

        src = _net(attrs_io=True)
        dst = _net()  # no inp
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        mc.connectAttr(up + ".o", src + ".inp")
        dropped = duplicate_inputs(src, dst)
        self.assertTrue(any("inp" in d for d in dropped))


class TestMoveOutputs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_moves_outgoing_edge(self):
        from mpynode._base.node_swap import move_outputs

        src = _net(attrs_io=True)
        dst = _net(attrs_io=True)
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(src + ".out", down + ".i")
        dropped = move_outputs(src, dst)
        self.assertTrue(mc.isConnected(dst + ".out", down + ".i"))
        self.assertFalse(mc.isConnected(src + ".out", down + ".i"))
        self.assertEqual(dropped, [])

    def test_skips_infra_link_plug(self):
        """The convert's OWN link attr must never be rerouted -- moving it would
        point the new sibling's link at itself. (`.message` is no longer judged
        by name; see TestMessageDestinationPolicy.)"""
        from mpynode._base.node_swap import move_outputs

        src = _net(attrs_io=True)
        dst = _net(attrs_io=True)
        mc.addAttr(src, ln="mpyCompiledLink", at="message")
        mc.addAttr(dst, ln="mpyCompiledLink", at="message")
        down = mc.createNode("network"); mc.addAttr(down, ln="mdst", at="message")
        mc.connectAttr(src + ".mpyCompiledLink", down + ".mdst")
        move_outputs(src, dst)
        self.assertTrue(mc.isConnected(src + ".mpyCompiledLink", down + ".mdst"))
        self.assertFalse(mc.isConnected(dst + ".mpyCompiledLink", down + ".mdst"))

    def test_moves_multi_element_edge_allocating_index(self):
        from mpynode._base.node_swap import move_outputs

        src = mc.createNode("network"); mc.addAttr(src, ln="mo", at="double", multi=True)
        dst = mc.createNode("network"); mc.addAttr(dst, ln="mo", at="double", multi=True)
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(src + ".mo[2]", down + ".i")
        move_outputs(src, dst)
        # force-connect ALLOCATES dst.mo[2] (must NOT pre-skip on objExists).
        self.assertTrue(mc.isConnected(dst + ".mo[2]", down + ".i"))
        self.assertFalse(mc.isConnected(src + ".mo[2]", down + ".i"))

    def test_dual_role_passthrough_split_correctly(self):
        """A passthrough plug (up.o -> src.pt -> down.i): duplicate_inputs carries
        the INCOMING edge, move_outputs carries the OUTGOING edge, each correctly
        directed (per-edge classification -- the D1 lesson)."""
        from mpynode._base.node_swap import duplicate_inputs, move_outputs

        src = mc.createNode("network"); mc.addAttr(src, ln="pt", at="double")
        dst = mc.createNode("network"); mc.addAttr(dst, ln="pt", at="double")
        up = mc.createNode("network"); mc.addAttr(up, ln="o", at="double")
        down = mc.createNode("network"); mc.addAttr(down, ln="i", at="double")
        mc.connectAttr(up + ".o", src + ".pt")    # incoming
        mc.connectAttr(src + ".pt", down + ".i")  # outgoing
        duplicate_inputs(src, dst)
        move_outputs(src, dst)
        self.assertTrue(mc.isConnected(up + ".o", dst + ".pt"))
        self.assertTrue(mc.isConnected(dst + ".pt", down + ".i"))
        self.assertFalse(mc.isConnected(dst + ".pt", up + ".o"))


class TestSwapNode(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_creates_deletes_renames_and_returns_tuple(self):
        from mpynode._base.node_swap import swap_node

        src      = mc.createNode("network", name="swapSrc")
        old_uuid = mc.ls(src, uuid=True)[0]
        mc.addAttr(src, ln="k", at="double"); mc.setAttr(src + ".k", 4.0)
        new_name, dropped = swap_node(src, "network")
        # The new node takes the old short name ...
        self.assertTrue(mc.objExists(new_name))
        self.assertEqual(new_name.split("|")[-1], "swapSrc")
        # ... but it is a genuinely NEW node (the old one was deleted): a fresh
        # createNode has a different UUID, so the same-name check can't be used.
        self.assertNotEqual(mc.ls(new_name, uuid=True)[0], old_uuid)
        self.assertIsInstance(dropped, list)

    def test_reparents_dag_children(self):
        """A DAG transform's child subtree must survive the swap (reparented
        onto the new node), not be destroyed with delete(src)."""
        from mpynode._base.node_swap import swap_node

        grp = mc.createNode("transform", name="swapParent")
        src = mc.createNode("transform", name="swapDagSrc", parent=grp)
        mc.createNode("transform", name="swapChild", parent=src)
        new_name, _dropped = swap_node(src, "transform")
        kids = mc.listRelatives(new_name, children=True) or []
        self.assertTrue(
            any(k.split("|")[-1] == "swapChild" for k in kids),
            "child subtree must be preserved under the swapped node")


if __name__ == "__main__":
    unittest.main()
