"""Construction history SURVIVES a coexist convert.

A compiled mPyBlendShape reads the BAKED tables -- it has no live-target path --
so Convert has to freeze the interpreted node's live state into those tables and
land them on the sibling that actually deforms. Two things broke that, and both
failed as no-ops rather than as errors:

  1. ``_base_points`` answers from ``deformer -q -geometry``, which reads the
     output edge ``move_outputs`` took away. A converted node therefore reports
     NO base, and ``bake_deltas`` guards on ``base.shape[0]`` -- so every target
     silently took the "keep the previous deltas" path and the re-bake reported
     that nothing had changed. The quiet killer.
  2. Every table write goes to ``self._name``. Even a successful re-bake landed
     only on the interpreted node, never on the sibling that deforms.

These are tested against a linked pair of INTERPRETED nodes rather than a real
compiled sibling: the link is a plain ``mpyCompiledLink`` message connection, so
the mirror, the base fallback and the freeze can all be exercised without the
mega bundle. The end-to-end path over the real C++ node is covered by the
convert parity probes.
"""
from __future__ import annotations

import unittest

import maya.api.OpenMaya as om2
from maya import cmds as mc

from mpynode._base.node_swap import _ensure_link
from mpynode._common.methods import morph_methods as MM
from tests import _setup
from mpynode.wrappers.mpy_blend_shape import MPyBlendShape


def setUpModule():
    _setup.standalone_init()
    _setup.ensure_plugins_loaded()


COMPUTE = (
    "mesh = self.outputGeometry[0]\n"
    "base = mesh.getPoints()\n"
    "mesh.setPoints(base + self.envelope * self.morphs.deltas("
    "base, self.weight))\n"
)


def _pts(shape):
    sel = om2.MSelectionList()
    sel.add(shape)
    fn = om2.MFnMesh(sel.getDagPath(0))
    return [(round(p.x, 4), round(p.y, 4), round(p.z, 4))
            for p in fn.getPoints(om2.MSpace.kObject)]


class _LinkedPair(unittest.TestCase):
    """``self.bs`` (drives a mesh, one target) linked to ``self.sib``.

    ``sib`` stands in for the compiled sibling. It is a second interpreted
    mPyBlendShape purely so it carries the same table attrs -- nothing here
    depends on it being compiled.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        self.base = mc.polyPlane(w=2, h=2, sx=1, sy=1, name="cvBase",
                                 ch=False)[0]
        self.bs = MPyBlendShape.create(mesh=self.base, name="cvSrc")
        self.name = self.bs.get_name()
        self.bs.set_compute_expression(COMPUTE)
        self.shape = mc.listRelatives(self.base, shapes=True,
                                      noIntermediate=True, f=True)[0]

        self.tgt = mc.polyPlane(w=2, h=2, sx=1, sy=1, name="cvTgt", ch=False)[0]
        mc.setAttr(self.tgt + ".translateX", 5)
        mc.move(0, 1, 0, self.tgt + ".vtx[0]", relative=True, objectSpace=True)
        self.bs.add_target(self.tgt)
        self.bs.rebuild()
        mc.setAttr(self.name + ".weight[0]", 1.0)

        # The stand-in sibling, on its own mesh so it has a base of its own.
        self.sib_mesh = mc.polyPlane(w=2, h=2, sx=1, sy=1, name="cvSibBase",
                                     ch=False)[0]
        self.sib = MPyBlendShape.create(mesh=self.sib_mesh, name="cvCpp")
        self.sib_name = self.sib.get_name()
        # A real compiled sibling declares the tables in its C++; this stand-in
        # only grows them on demand, so create them up front.
        self.sib.ensure_delta_attrs()

    def orphan(self, name):
        """A blendShape with NO reachable geometry -- what convert leaves the
        interpreted node as once move_outputs has taken its output edge."""
        mesh = mc.polyPlane(w=2, h=2, sx=1, sy=1, name=name + "Mesh",
                            ch=False)[0]
        node = MPyBlendShape.create(mesh=mesh, name=name)
        for c in (mc.listConnections(node.get_name() + ".outputGeometry[0]",
                                     s=False, d=True, plugs=True) or []):
            mc.disconnectAttr(node.get_name() + ".outputGeometry[0]", c)
        return node

    def link(self):
        _ensure_link(self.name, self.sib_name)


class TestTheMirror(_LinkedPair):
    def test_a_table_write_reaches_the_sibling(self):
        self.link()
        self.bs._write_multi("targetDeltas", [1.0, 2.0, 3.0])
        self.assertEqual(
            list(self.bs._read_multi("targetDeltas")), [1.0, 2.0, 3.0])
        self.assertEqual(
            list(self.sib._read_multi("targetDeltas")), [1.0, 2.0, 3.0],
            "the compiled sibling is what deforms -- a table written only on "
            "the authoring node reaches nothing")

    def test_an_unconverted_node_writes_only_itself(self):
        self.bs._write_multi("targetDeltas", [4.0, 5.0])
        self.assertEqual(list(self.bs._read_multi("targetDeltas")), [4.0, 5.0])
        self.assertEqual(list(self.sib._read_multi("targetDeltas")), [],
                         "no link -> no mirror")

    def test_the_mirror_is_dropped_when_the_link_goes(self):
        self.link()
        mc.disconnectAttr(self.name + ".mpyCompiledLink",
                          self.sib_name + ".mpyInterpretedLink")
        self.bs._write_multi("targetDeltas", [7.0])
        self.assertEqual(list(self.sib._read_multi("targetDeltas")), [],
                         "revert is undoable, so the sibling must be resolved "
                         "per write and not cached")

    def test_an_attr_the_sibling_lacks_is_skipped(self):
        """A compiled node declares only the attrs its compute reads, so the
        mirror must tolerate a table that has no counterpart."""
        self.link()
        mc.deleteAttr(self.sib_name + ".targetDeltas")
        self.bs._write_multi("targetDeltas", [9.0])       # must not raise
        self.assertEqual(list(self.bs._read_multi("targetDeltas")), [9.0])

    def test_compiled_sibling_is_none_when_unconverted(self):
        self.assertIsNone(self.bs._compiled_sibling())
        self.link()
        self.assertEqual(self.bs._compiled_sibling(), self.sib_name)


class TestTheBaseFallback(_LinkedPair):
    def test_a_node_with_no_geometry_asks_its_sibling(self):
        """The quiet killer: `deformer -q -geometry` answers from the output
        edge that convert MOVED, so a converted node reports no base at all."""
        orphan = self.orphan("cvOrphan")
        self.assertEqual(orphan._base_points().shape[0], 0,
                         "precondition: no geometry reachable")

        # `self.bs` still drives cvBase, so it stands in for the sibling that
        # took the geometry over.
        _ensure_link(orphan.get_name(), self.name)
        self.assertGreater(
            orphan._base_points().shape[0], 0,
            "a converted node must find its base through the sibling that is "
            "now driving the geometry")

    def test_an_unconverted_node_with_no_geometry_still_reports_empty(self):
        self.assertEqual(self.orphan("cvOrphan2")._base_points().shape[0], 0)


class TestTheFreeze(_LinkedPair):
    """Convert must BAKE before it copies. The interpreted node follows a
    connected target live, so a sculpt is visible without ever touching
    ``targetDeltas`` -- and a compiled sibling reading those stale tables would
    snap straight back to the pre-sculpt shape."""

    def test_a_live_sculpt_is_frozen_into_the_tables(self):
        before = list(self.bs._read_multi("targetDeltas"))
        mc.move(0, -3, 0, self.tgt + ".vtx[0]", relative=True,
                objectSpace=True)
        self.assertEqual(list(self.bs._read_multi("targetDeltas")), before,
                         "precondition: the live path writes no plug, so the "
                         "tables are stale until something freezes them")

        from mpynode._base.node_swap import _freeze_live_state
        _freeze_live_state(self.name)
        after = list(self.bs._read_multi("targetDeltas"))
        self.assertNotEqual(before, after)
        self.assertAlmostEqual(after[1], -2.0, places=6)

    def test_the_freeze_reaches_the_sibling(self):
        self.link()
        mc.move(0, -3, 0, self.tgt + ".vtx[0]", relative=True,
                objectSpace=True)
        from mpynode._base.node_swap import _freeze_live_state
        _freeze_live_state(self.name)
        self.assertEqual(list(self.sib._read_multi("targetDeltas")),
                         list(self.bs._read_multi("targetDeltas")),
                         "the compiled sibling is what deforms")

    def test_it_is_a_no_op_on_another_node_type(self):
        from mpynode._base.node_swap import _freeze_live_state
        _freeze_live_state(mc.polyCube(ch=False)[0])       # must not raise


class TestTheSharedRebake(_LinkedPair):
    def test_a_settled_node_writes_nothing(self):
        self.assertFalse(MM._rebake_if_stale(self.name),
                         "no sculpt -> no write, or the node spins a "
                         "dirty/recompute loop")

    def test_a_sculpt_is_detected(self):
        mc.move(0, -3, 0, self.tgt + ".vtx[0]", relative=True,
                objectSpace=True)
        self.assertTrue(MM._rebake_if_stale(self.name))

    def test_a_node_with_no_connected_target_is_left_alone(self):
        mc.disconnectAttr(
            mc.listConnections(self.name + ".targetGeometry[0]", s=True,
                               d=False, plugs=True)[0],
            self.name + ".targetGeometry[0]")
        self.assertFalse(MM._rebake_if_stale(self.name),
                         "deltas loaded from a file have no mesh to follow and "
                         "re-baking them would be pure loss")


if __name__ == "__main__":
    unittest.main()
