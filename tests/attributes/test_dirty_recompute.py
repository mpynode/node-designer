"""Regression: editing the Compute expression on a CACHED node must re-evaluate.

Guards the API-1 ``attr_fn.name`` bound-method bug (P0-1 in the project
assessment): ``MFnAttribute.name`` is a *method* under maya.OpenMaya, so
reading it without parens yielded a bound method that is never in the trigger
set, so ``setDependentsDirty`` returned early and ``outputGeom`` was never
re-dirtied. Effect: after the output caches, changing the expression left the
node rendering the STALE result. User-INPUT changes still propagated (via the
separate auto_dirty callback), so this only bit expression / stored-var edits.

The fix is ``.name`` -> ``.name()`` in the API-1 deformer-family files
(mpy_deformer / mpy_blend_shape / mpy_transform);
mpy_skin_cluster already had it.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestExpressionEditReevaluatesDeformer(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import init_registry

        init_registry.clear_all_init_ns()

    def _vtx_y(self, plane, idx=12):
        return mc.xform("%s.vtx[%d]" % (plane, idx), q=True, ws=True, t=True)[1]

    def test_editing_expression_after_cache_reevaluates(self):
        """Cache an expression result, then edit the expression WITHOUT
        touching the input geometry, and assert the new value is produced.

        With the .name bound-method bug, setDependentsDirty early-returns on
        the _computeSource change, outputGeom stays clean, and the re-query
        returns the stale cached value (5.0 instead of 10.0).
        """
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", w=2, h=2, sx=4, sy=4)[0]
        d = MPyDeformer.create_on(plane)

        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += 5.0\n"
            "mesh.setPoints(pts)\n"
        )
        # Force evaluation -> caches the +5 result.
        self.assertAlmostEqual(self._vtx_y(plane), 5.0, places=3)

        # Edit the expression only; input geometry is untouched.
        d.set_compute_expression(
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += 10.0\n"
            "mesh.setPoints(pts)\n"
        )
        # Must re-evaluate to the new value, not the stale cached 5.0.
        self.assertAlmostEqual(self._vtx_y(plane), 10.0, places=3)


class TestDeclareUserAffectsDirtiesArrayElements(unittest.TestCase):
    """First test for _common/dirty_affects: an array OUTPUT must dirty each
    existing element plug, not only the array parent, or a downstream node
    wired to ``out[i]`` reads stale on the native (declare_user_affects) path.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import dirty_affects

        dirty_affects.invalidate_all()

    def test_array_output_elements_are_dirtied(self):
        import maya.api.OpenMaya as om
        from mpynode import MPyNode
        from mpynode._api2._mpy_node import MPyNode as ApiNode
        from mpynode._common.plugs import dirty_affects

        node = MPyNode.create(name="mpn_dua")
        node.add_input_attr("drv", "float")
        node.add_output_attr("outArr", "float", is_array=True)
        name = node.get_name()

        # Force two array-output elements to exist by connecting them.
        loc0 = mc.spaceLocator()[0]
        loc1 = mc.spaceLocator()[0]
        mc.connectAttr(name + ".outArr[0]", loc0 + ".tx")
        mc.connectAttr(name + ".outArr[1]", loc1 + ".tx")

        sel = om.MSelectionList()
        sel.add(name)
        mobj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(mobj)
        drv_plug = fn.findPlug("drv", False)

        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            drv_plug,
            affected,
            ApiNode._input_attrs_attr,
            ApiNode._output_attrs_attr,
        )
        names = [affected[i].partialName(useLongNames=True) for i in range(len(affected))]
        self.assertTrue(any(n == "outArr" for n in names), names)
        self.assertTrue(any("outArr[0]" in n for n in names), names)
        self.assertTrue(any("outArr[1]" in n for n in names), names)


class TestDeclareUserAffectsExpressionTrigger(unittest.TestCase):
    """``expression_attr`` param: passing the expression MObject makes a change
    to that plug dirty every user output. This is the base ``MPyNode``
    expression trigger, expressed through the shared helper instead of inline.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import dirty_affects

        dirty_affects.invalidate_all()

    def _make_node(self):
        import maya.api.OpenMaya as om
        from mpynode import MPyNode

        node = MPyNode.create(name="mpn_expr")
        node.add_input_attr("drv", "float")
        node.add_output_attr("outLen", "float")
        sel = om.MSelectionList()
        sel.add(node.get_name())
        mobj = sel.getDependNode(0)
        return om.MFnDependencyNode(mobj), mobj

    def test_expression_plug_dirties_user_outputs(self):
        import maya.api.OpenMaya as om
        from mpynode._api2._mpy_node import MPyNode as ApiNode
        from mpynode._common.plugs import dirty_affects

        fn, mobj = self._make_node()
        expr_plug = fn.findPlug(ApiNode._expression_attr, False)
        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            expr_plug,
            affected,
            ApiNode._input_attrs_attr,
            ApiNode._output_attrs_attr,
            expression_attr=ApiNode._expression_attr,
        )
        names = [
            affected[i].partialName(useLongNames=True) for i in range(len(affected))
        ]
        self.assertIn("outLen", names)

    def test_expression_plug_without_param_does_not_trigger(self):
        """Default behavior (no ``expression_attr``) must NOT fire on the
        expression plug -- the geometry/file callers rely on that."""
        import maya.api.OpenMaya as om
        from mpynode._api2._mpy_node import MPyNode as ApiNode
        from mpynode._common.plugs import dirty_affects

        fn, mobj = self._make_node()
        expr_plug = fn.findPlug(ApiNode._expression_attr, False)
        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            expr_plug,
            affected,
            ApiNode._input_attrs_attr,
            ApiNode._output_attrs_attr,
        )
        names = [
            affected[i].partialName(useLongNames=True) for i in range(len(affected))
        ]
        self.assertNotIn("outLen", names)


class TestDeclareUserAffectsExtraTriggers(unittest.TestCase):
    """``extra_trigger_names`` param: a named NON-input plug (e.g. a constraint
    preset input) fires the helper. This is MPyConstraint's preset trigger,
    expressed through the shared helper instead of inline."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import dirty_affects

        dirty_affects.invalidate_all()

    def _make_constraint(self):
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        c = MPyConstraint.create(name="cstr_xt")
        c.add_output_attr("out", "vector")
        sel = om.MSelectionList()
        sel.add(c.get_name())
        mobj = sel.getDependNode(0)
        return om.MFnDependencyNode(mobj), mobj

    def test_extra_trigger_name_dirties_user_outputs(self):
        import maya.api.OpenMaya as om
        from mpynode._api2.mpy_constraint import MPyConstraint as ApiC
        from mpynode._common.plugs import dirty_affects

        fn, mobj = self._make_constraint()
        tt_plug = fn.findPlug(ApiC._targetTranslate_attr, False)
        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            tt_plug,
            affected,
            ApiC._input_attrs_attr,
            ApiC._output_attrs_attr,
            extra_trigger_names={"targetTranslate"},
        )
        names = [
            affected[i].partialName(useLongNames=True) for i in range(len(affected))
        ]
        self.assertIn("out", names)

    def test_extra_trigger_absent_does_not_dirty(self):
        """Without ``extra_trigger_names`` a preset (non-user-input) plug does
        NOT fire -- proves the param is what triggers it."""
        import maya.api.OpenMaya as om
        from mpynode._api2.mpy_constraint import MPyConstraint as ApiC
        from mpynode._common.plugs import dirty_affects

        fn, mobj = self._make_constraint()
        tt_plug = fn.findPlug(ApiC._targetTranslate_attr, False)
        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            tt_plug,
            affected,
            ApiC._input_attrs_attr,
            ApiC._output_attrs_attr,
        )
        names = [
            affected[i].partialName(useLongNames=True) for i in range(len(affected))
        ]
        self.assertNotIn("out", names)


class TestDeclareUserAffectsExtraOutputs(unittest.TestCase):
    """``extra_outputs`` param: native output MObjects (e.g. MPyFile's
    outColor/outAlpha) are appended on trigger, EVEN when the node has zero
    user outputs (exercises the relaxed control flow)."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import dirty_affects

        dirty_affects.invalidate_all()

    def test_extra_outputs_appended_with_no_user_outputs(self):
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_file import MPyFile as WrapFile
        from mpynode._api2.mpy_file import MPyFile as ApiFile
        from mpynode._common.plugs import dirty_affects

        f = WrapFile.create(name="file_xo", seed_defaults=False, as_texture=False)
        f.add_input_attr("drv", "float")
        # Deliberately NO user output attr -- only the native extra_outputs.
        sel = om.MSelectionList()
        sel.add(f.get_name())
        mobj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(mobj)
        drv_plug = fn.findPlug("drv", False)

        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            drv_plug,
            affected,
            ApiFile._input_attrs_attr,
            ApiFile._output_attrs_attr,
            extra_outputs=(ApiFile.aOutColor, ApiFile.aOutAlpha),
        )
        names = [
            affected[i].partialName(useLongNames=True) for i in range(len(affected))
        ]
        self.assertTrue(any("outColor" in n for n in names), names)
        self.assertTrue(any("outAlpha" in n for n in names), names)


class TestDeclareUserAffectsCompoundChildTriggers(unittest.TestCase):
    """Regression guard: editing a compound INPUT CHILD plug (e.g. ``vecX`` of
    a vector user input, or ``targetTranslateX`` of a constraint preset) must
    still dirty the user outputs. Maya delivers the child plug to
    ``setDependentsDirty`` whose long name carries the axis suffix and has NO
    parent prefix -- the helper must map it back to the parent key (the
    pre-helper code did this via ``MFnAttribute.name`` + ``rstrip('XYZ')``)."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.plugs import dirty_affects

        dirty_affects.invalidate_all()

    def test_vector_input_child_dirties_user_outputs(self):
        import maya.api.OpenMaya as om
        from mpynode import MPyNode
        from mpynode._api2._mpy_node import MPyNode as ApiNode
        from mpynode._common.plugs import dirty_affects

        node = MPyNode.create(name="mpn_vec")
        node.add_input_attr("vec", "vector")
        node.add_output_attr("outLen", "float")
        sel = om.MSelectionList()
        sel.add(node.get_name())
        mobj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(mobj)
        # The X child of the "vec" compound input (robust to exact naming).
        child_plug = fn.findPlug("vec", False).child(0)

        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            child_plug,
            affected,
            ApiNode._input_attrs_attr,
            ApiNode._output_attrs_attr,
            expression_attr=ApiNode._expression_attr,
        )
        names = [
            affected[i].partialName(useLongNames=True) for i in range(len(affected))
        ]
        self.assertIn("outLen", names)

    def test_preset_vector_child_dirties_user_outputs(self):
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_constraint import MPyConstraint
        from mpynode._api2.mpy_constraint import (
            MPyConstraint as ApiC,
            _PRESET_INPUT_NAMES,
        )
        from mpynode._common.plugs import dirty_affects

        c = MPyConstraint.create(name="cstr_child")
        c.add_output_attr("out", "vector")
        sel = om.MSelectionList()
        sel.add(c.get_name())
        mobj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(mobj)
        child_plug = fn.findPlug(ApiC._targetTranslate_attr, False).child(0)

        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj,
            child_plug,
            affected,
            ApiC._input_attrs_attr,
            ApiC._output_attrs_attr,
            expression_attr=ApiC._expression_attr,
            extra_trigger_names=_PRESET_INPUT_NAMES,
        )
        names = [
            affected[i].partialName(useLongNames=True) for i in range(len(affected))
        ]
        self.assertIn("out", names)

    def test_vector_child_setattr_recomputes_output_end_to_end(self):
        """The faithful repro: cache an output, edit ONLY a vector child, and
        assert the output recomputes (not stale)."""
        from mpynode import MPyNode

        node = MPyNode.create(name="mpn_vec_e2e")
        node.add_input_attr("vec", "vector")
        node.add_output_attr("s", "float")
        node.set_compute_expression("self.s = self.vec[0] + self.vec[1] + self.vec[2]")
        name = node.get_name()

        loc = mc.spaceLocator()[0]
        mc.connectAttr(name + ".s", loc + ".tx", force=True)

        mc.setAttr(name + ".vec", 1.0, 0.0, 0.0, type="double3")
        # Force evaluation -> caches s = 1.0
        self.assertAlmostEqual(mc.getAttr(loc + ".tx"), 1.0, places=4)

        # Edit ONLY the Y child. With the regression, s stays stale at 1.0.
        mc.setAttr(name + ".vecY", 5.0)
        self.assertAlmostEqual(mc.getAttr(loc + ".tx"), 6.0, places=4)


if __name__ == "__main__":
    unittest.main()
