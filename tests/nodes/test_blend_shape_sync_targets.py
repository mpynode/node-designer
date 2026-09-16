"""Construction history for mPyBlendShape target meshes -- the LIVE path.

``rebuild()`` decodes the targets once into ``targetOffset`` /
``targetComponents`` / ``targetDeltas`` (names cannot be resolved on the EM
worker thread, so the deform cannot go looking for them). Nothing re-read a
target after that, so sculpting a connected target changed nothing: the deform
kept replaying the shape as it was when the node was built.

The deform now READS the connected target meshes instead, and the three
properties that has to satisfy are tested together on purpose, because the fix
must not buy one at the cost of the others:

  * a CONNECTED, dialled-in target that is sculpted reaches the deform on the
    very next evaluation -- no settling pull, no deferred pass;
  * a target with NO connection keeps driving it -- disconnect it, delete it,
    save and reopen, the shape stays; and
  * the deform WRITES NOTHING. That is the one that is easy to lose and
    expensive to lose: the first version of this re-baked from inside the
    deform, which meant marshalling a ``setAttr`` off the evaluation, which
    landed it in its own undo chunk on top of whatever the user was doing --
    so their vertex edit could no longer be undone at all.

A re-bake still exists, as ``resync_targets()``: an explicit, main-thread
authoring operation that makes a live sculpt permanent. Convert calls it.
"""
from __future__ import annotations

import unittest

import maya.api.OpenMaya as om2
from maya import cmds as mc

from tests import _setup
from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
from tests import _paths


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


class _Rig(unittest.TestCase):
    """A one-target blendShape whose target lifts vertex 0 by +1 in Y."""

    def setUp(self):
        mc.file(new=True, force=True)
        self.base = mc.polyPlane(w=2, h=2, sx=1, sy=1, name="bsBase",
                                 ch=False)[0]
        self.bs   = MPyBlendShape.create(mesh=self.base, name="bsSync")
        self.name = self.bs.get_name()
        self.bs.set_compute_expression(COMPUTE)
        self.shape = mc.listRelatives(self.base, shapes=True,
                                      noIntermediate=True, f=True)[0]

        self.tgt = mc.polyPlane(w=2, h=2, sx=1, sy=1, name="jawOpen",
                                ch=False)[0]
        mc.setAttr(self.tgt + ".translateX", 5)
        mc.move(0, 1, 0, self.tgt + ".vtx[0]", relative=True, objectSpace=True)
        self.tgt_shape = mc.listRelatives(self.tgt, shapes=True,
                                          noIntermediate=True, f=True)[0]

        self.bs.add_target(self.tgt)
        self.bs.rebuild()
        mc.setAttr(self.name + ".weight[0]", 1.0)

    def pull(self):
        mc.dgdirty(self.shape + ".outMesh")
        mc.getAttr(self.shape + ".outMesh")
        return _pts(self.shape)

    def sculpt(self, dy=-3):
        mc.move(0, dy, 0, self.tgt + ".vtx[0]", relative=True,
                objectSpace=True)


class TestConstructionHistory(_Rig):
    def test_the_rig_starts_matching_its_target(self):
        self.assertEqual(self.pull()[0], _pts(self.tgt_shape)[0])

    def test_a_sculpt_reaches_the_deform_on_the_NEXT_pull(self):
        """The live-feedback requirement. One pull, no settling: during a drag
        this is all Maya gives you before the next redraw."""
        self.sculpt()
        self.assertEqual(self.pull()[0], _pts(self.tgt_shape)[0])

    def test_the_deform_writes_no_plug(self):
        """The undo requirement. A setAttr from inside a deform has to be
        marshalled off the evaluation, and it lands in its OWN undo chunk on top
        of the user's -- which is what stopped their vertex edit undoing."""
        seen = []
        real = mc.setAttr

        def spy(*args, **kwargs):
            seen.append(args[0] if args else "?")
            return real(*args, **kwargs)

        self.sculpt()
        mc.setAttr = spy
        try:
            self.pull()
        finally:
            mc.setAttr = real
        self.assertEqual(seen, [], "the deform must not write ANY plug")

    def test_the_baked_table_is_left_alone(self):
        """Live means live: the tables are not quietly re-baked behind it.
        ``resync_targets`` is how a sculpt is made permanent, on purpose."""
        before = mc.getAttr(self.name + ".targetDeltas")
        self.sculpt()
        self.pull()
        self.assertEqual(mc.getAttr(self.name + ".targetDeltas"), before)

    def test_repeated_pulls_reach_a_fixed_point(self):
        self.sculpt()
        seq = [self.pull()[0] for _ in range(4)]
        self.assertEqual(len(set(seq)), 1, "deform should be at a fixed point")

    def test_an_unsculpted_live_target_matches_its_bake_exactly(self):
        """Parity. The live read and the bake measure against the SAME rest
        shape (``originalGeometry`` == what ``_base_points`` reads), so an
        untouched target must agree to the last bit -- not to a tolerance."""
        live = self.pull()
        mc.setAttr(self.name + ".liveTargets", 0)
        self.assertEqual(self.pull(), live)


class TestTheWeightGate(_Rig):
    """A zero-weight target contributes exactly zero, so its mesh is never read.
    That skip is what keeps a 167-target rig affordable -- and being exact
    rather than approximate is what makes it safe."""

    def test_a_zero_weight_target_contributes_nothing(self):
        mc.setAttr(self.name + ".weight[0]", 0.0)
        self.sculpt()
        self.assertEqual(self.pull(), _pts(mc.listRelatives(
            self.base, shapes=True, ni=True, f=True)[0]))

    def test_dialling_it_back_up_picks_the_sculpt_straight_up(self):
        mc.setAttr(self.name + ".weight[0]", 0.0)
        self.sculpt()
        self.pull()
        mc.setAttr(self.name + ".weight[0]", 1.0)
        self.assertEqual(self.pull()[0], _pts(self.tgt_shape)[0])

    def test_a_partial_weight_scales_the_live_delta(self):
        mc.setAttr(self.name + ".weight[0]", 0.5)
        self.assertAlmostEqual(self.pull()[0][1], 0.5, places=4)


class TestTheGate(_Rig):
    def test_it_defaults_on(self):
        self.assertTrue(mc.getAttr(self.name + ".liveTargets"))

    def test_switching_it_off_pins_the_deform_to_the_bake(self):
        baked = self.pull()
        mc.setAttr(self.name + ".liveTargets", 0)
        self.sculpt()
        self.assertEqual(self.pull(), baked,
                         "liveTargets off -> the sculpt must NOT reach the "
                         "deform; the baked tables are authoritative")

    def test_switching_it_back_on_is_enough_to_see_the_sculpt(self):
        mc.setAttr(self.name + ".liveTargets", 0)
        self.sculpt()
        self.pull()
        mc.setAttr(self.name + ".liveTargets", 1)
        self.assertEqual(self.pull()[0], _pts(self.tgt_shape)[0])


class TestTheCacheStillSurvives(_Rig):
    """The half that must NOT regress: a target with no connection keeps driving
    the deform. targetGeometry is setCached(True), so a disconnected element goes
    on serving its last mesh -- only ``isDestination()`` can tell them apart."""

    def _sculpt_and_freeze(self):
        self.sculpt()
        self.bs.resync_targets()
        return _pts(self.tgt_shape)[0]

    def test_disconnecting_the_target_keeps_the_shape(self):
        want = self._sculpt_and_freeze()
        src = mc.listConnections("%s.targetGeometry[0]" % self.name,
                                 s=True, d=False, plugs=True)[0]
        mc.disconnectAttr(src, "%s.targetGeometry[0]" % self.name)
        self.assertEqual(self.pull()[0], want)

    def test_deleting_the_target_mesh_keeps_the_shape(self):
        want = self._sculpt_and_freeze()
        mc.delete(self.tgt)
        self.assertEqual(self.pull()[0], want)

    def test_a_disconnected_target_never_goes_live_again(self):
        """The cached-data trap, stated as a test. Disconnect, then sculpt the
        (now unrelated) mesh: nothing about the deform may change."""
        self._sculpt_and_freeze()
        src = mc.listConnections("%s.targetGeometry[0]" % self.name,
                                 s=True, d=False, plugs=True)[0]
        mc.disconnectAttr(src, "%s.targetGeometry[0]" % self.name)
        want = self.pull()
        self.sculpt(dy=7)
        self.assertEqual(self.pull(), want)


class TestResyncTargets(_Rig):
    def test_a_settled_node_writes_nothing(self):
        self.assertFalse(self.bs.resync_targets(),
                         "no sculpt -> no write")

    def test_a_sculpt_is_frozen_into_the_tables(self):
        self.sculpt()
        self.assertTrue(self.bs.resync_targets())
        self.assertAlmostEqual(
            mc.getAttr(self.name + ".targetDeltas")[1], -2.0, places=6)

    def test_it_leaves_the_shape_where_it_already_was(self):
        """Freezing is a no-op on APPEARANCE -- the live pass was already
        showing the sculpt. Only permanence changes."""
        self.sculpt()
        was = self.pull()
        self.bs.resync_targets()
        self.assertEqual(self.pull(), was)

    def test_a_node_with_no_connected_target_is_left_alone(self):
        """bake_deltas drops an unconnected slot that has no ALIAS, so a node
        whose deltas were written by hand (or loaded from a file before
        aliasing) must not be re-baked at all -- that would erase it."""
        mc.delete(self.tgt)
        before = mc.getAttr(self.name + ".targetDeltas")
        self.assertTrue(any(abs(v) > 1e-9 for v in before),
                        "fixture should have non-empty deltas to protect")
        self.assertFalse(self.bs.resync_targets())
        self.assertEqual(mc.getAttr(self.name + ".targetDeltas"), before)


class TestBakeDeltasIsIdempotent(_Rig):
    def test_an_unchanged_rebake_writes_nothing(self):
        seen = []
        real = mc.setAttr

        def spy(*args, **kwargs):
            if args and str(args[0]).endswith(".targetDeltas"):
                seen.append(args[0])
            return real(*args, **kwargs)

        mc.setAttr = spy
        try:
            self.bs.bake_deltas()
        finally:
            mc.setAttr = real
        self.assertEqual(seen, [],
                         "an identical re-bake must not write the plug")

    def test_a_changed_rebake_does_write(self):
        self.sculpt()
        self.bs.bake_deltas()
        self.assertAlmostEqual(
            mc.getAttr(self.name + ".targetDeltas")[1], -2.0, places=6)


class TestTheShippedTemplate(unittest.TestCase):
    def test_it_no_longer_calls_a_rebake_side_effect(self):
        import json
        import os

        here = os.path.dirname(os.path.abspath(__file__))
        root = _paths.ROOT
        path = os.path.join(root, "templates", "MPyBlendShape",
                            "Combo Correctives", "template.mpn")
        if not os.path.isfile(path):
            self.skipTest("shipped Combo Correctives template not found")
        with open(path, encoding="utf-8") as fh:
            expr = json.load(fh)["data"]["expression"]
        self.assertNotIn("sync_targets", expr,
                         "the deform must not re-bake -- that is what broke "
                         "undo")


class TestTheRestReferenceIsWired(_Rig):
    """``originalGeometry`` is the deform's rest reference, and it is only there
    if something CONNECTS it.

    Maya 2026 wires it for an MPxDeformerNode by itself; Maya 2024 does not --
    ``mc.deformer`` leaves it with no elements at all, so ``_orig_points``
    returns None and every live read degrades to the baked tables without saying
    so. The failure is invisible on 2026, which is why it is pinned here.
    """

    def _incoming(self, idx=0):
        return mc.listConnections("%s.originalGeometry[%d]" % (self.name, idx),
                                  source=True, destination=False, plugs=True)

    def test_create_wires_the_orig_shape(self):
        self.assertTrue(self._incoming(),
                        "originalGeometry[0] must be connected, or the deform "
                        "has no rest reference")

    def test_it_is_the_INTERMEDIATE_shape(self):
        """Not the deformed shape -- that would fold the current deformation
        into every live delta."""
        src = self._incoming()[0].split(".")[0]
        self.assertTrue(mc.getAttr(src + ".intermediateObject"),
                        "%s is not an intermediate (ORIG) shape" % src)

    def test_rebuild_repairs_an_unwired_node(self):
        """The path every scene authored on 2024 takes."""
        mc.disconnectAttr(self._incoming()[0],
                          "%s.originalGeometry[0]" % self.name)
        self.assertFalse(self._incoming())
        self.bs.rebuild()
        self.assertTrue(self._incoming(), "rebuild() must re-wire it")

    def test_wiring_twice_makes_no_second_connection(self):
        """Idempotent -- it runs on every rebuild()."""
        before = self._incoming()
        self.bs._ensure_original_geometry()
        self.assertEqual(self._incoming(), before)

    def test_the_live_path_actually_reaches_the_deform(self):
        """The property the wiring exists for. Fails on 2024 without it."""
        self.sculpt()
        self.assertEqual(self.pull()[0], _pts(self.tgt_shape)[0])


RESOLVED_COMPUTE = (
    "mesh = self.outputGeometry[0]\n"
    "base = mesh.getPoints()\n"
    "mesh.setPoints(base + self.envelope * self.morphs.deltas("
    "base, self.morphs.resolved))\n"
)


class TestAComboDrivenCorrectiveGoesLive(unittest.TestCase):
    """A corrective whose OWN channel sits at 0 but whose combo drives it.

    This is what separates 'live' from 'live enough', and it is why the compiled
    prologue cannot decide liveness from the RAW ``weight`` plug.
    ``resolve_weights`` ADDS the combo product on top of a target's own channel,
    so a corrective at rest on its own weight can still be fully dialled in by
    its drivers. Skipping it because its raw weight is 0 would mean sculpting a
    corrective did nothing while its drivers were posed -- which is the entire
    workflow of the Combo Correctives template.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        self.base = mc.polyPlane(w=2, h=2, sx=1, sy=1, name="ccBase",
                                 ch=False)[0]
        self.bs   = MPyBlendShape.create(mesh=self.base, name="ccRig")
        self.name = self.bs.get_name()
        self.bs.set_compute_expression(RESOLVED_COMPUTE)
        self.shape = mc.listRelatives(self.base, shapes=True,
                                      noIntermediate=True, f=True)[0]

        # aUp / bUp are mains; aUp_bUp is the COMBO of the two, by the alias
        # naming convention rebuild() decodes.
        self.tgt = {}
        for i, nm in enumerate(("aUp", "bUp", "aUp_bUp")):
            t = mc.polyPlane(w=2, h=2, sx=1, sy=1, name=nm, ch=False)[0]
            mc.setAttr(t + ".translateX", 5 * (i + 1))
            mc.move(0, 1, 0, "%s.vtx[%d]" % (t, i), relative=True,
                    objectSpace=True)
            self.bs.add_target(t)
            self.tgt[nm] = t
        self.bs.rebuild()

        self.idx = {n: i for i, n in enumerate(self.bs.target_names)}
        # drivers fully on; the corrective's OWN channel left at rest
        for nm, v in (("aUp", 1.0), ("bUp", 1.0), ("aUp_bUp", 0.0)):
            mc.setAttr("%s.weight[%d]" % (self.name, self.idx[nm]), v)

    def pull(self):
        mc.dgdirty(self.shape + ".outMesh")
        mc.getAttr(self.shape + ".outMesh")
        return _pts(self.shape)

    def _resolved(self):
        """Effective weights, from the node's own decoded tables."""
        import numpy as np
        from mpynode._common.methods import morph_blend

        def tbl(attr, dt):
            return np.asarray(mc.getAttr(self.name + "." + attr) or [],
                              dtype=dt).reshape(-1)

        w = np.array([mc.getAttr("%s.weight[%d]" % (self.name, i))
                      for i in range(len(self.idx))], dtype=np.float64)
        return morph_blend.resolve_weights(
            w, tbl("interBase", np.int64), tbl("interKnot", np.float64),
            tbl("comboOffset", np.int64), tbl("comboDriver", np.int64))

    def test_rebuild_actually_decoded_it_as_a_combo(self):
        """Guards the premise. If the alias never decoded, every other
        assertion here would pass for the wrong reason."""
        ci   = self.idx["aUp_bUp"]
        cofs = mc.getAttr(self.name + ".comboOffset") or []
        cdrv = mc.getAttr(self.name + ".comboDriver") or []
        self.assertGreater(len(cofs), ci + 1, "no combo table was written")
        drivers = sorted(cdrv[int(cofs[ci]):int(cofs[ci + 1])])
        self.assertEqual(drivers,
                         sorted([self.idx["aUp"], self.idx["bUp"]]))

    def test_its_raw_weight_is_zero_but_its_effective_weight_is_not(self):
        """The premise the live pass has to cope with."""
        ci = self.idx["aUp_bUp"]
        self.assertEqual(mc.getAttr("%s.weight[%d]" % (self.name, ci)), 0.0)
        self.assertAlmostEqual(float(self._resolved()[ci]), 1.0, places=6)

    def test_sculpting_it_reaches_the_deform(self):
        """The requirement. A raw-weight-0 corrective is still LIVE."""
        before = self.pull()
        mc.move(0, -3, 0, "%s.vtx[2]" % self.tgt["aUp_bUp"], relative=True,
                objectSpace=True)
        after = self.pull()
        dy    = [round(a[1] - b[1], 4) for a, b in zip(after, before)]
        self.assertAlmostEqual(dy[2], -3.0, places=3,
                               msg="the corrective's sculpt did not reach the "
                                   "deform -- it was skipped as zero-weight")
        self.assertEqual([v for i, v in enumerate(dy) if i != 2],
                         [0.0] * (len(dy) - 1),
                         "only the sculpted vertex may move")

    def test_the_gate_still_switches_it_off(self):
        before = self.pull()
        mc.setAttr(self.name + ".liveTargets", 0)
        mc.move(0, -3, 0, "%s.vtx[2]" % self.tgt["aUp_bUp"], relative=True,
                objectSpace=True)
        self.assertEqual(self.pull(), before,
                         "liveTargets off must pin the deform to the bake")


if __name__ == "__main__":
    unittest.main()
