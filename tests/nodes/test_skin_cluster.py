"""mPySkinCluster: weightList as the live source of truth.

Covers the fixes that make Maya's native skinning UX work end to end on a
custom mPySkinCluster (which is registered under kSkinCluster):

  * weightList edits re-deform live (Option A) -- editing a
    ``weightList[v].weights[j]`` plug (what the Component Editor / Paint
    Skin Weights write) re-evaluates the deformer WITHOUT an explicit
    ``cmds.dgdirty``. This works because the node is a genuine skinCluster,
    so the C++ base class propagates ``weightList -> outputGeometry``
    dirtiness natively -- NOT because of the Python ``setDependentsDirty``
    override.

  * ``_computeSource`` edits re-deform live (Option D) -- changing ONLY the
    Compute expression at runtime must re-evaluate the output. Nothing else
    covers this trigger (no static ``attributeAffects``; the base class
    doesn't know ``_computeSource``; auto-dirty only covers user inputs), so
    it relies on the ``setDependentsDirty`` fix (call ``attr_fn.name()`` and
    keep ``_computeSource``/``weights`` in the trigger set).

  * Option C -- the customLBS demo populates ``weightList`` and its
    Compute densifies the weights from ``self.weightList`` (instead of the
    fragile ``vertex_weights`` stored var), so the shipped scene shows
    real, editable skin weights in the Component Editor.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import maya.OpenMayaAnim as oma
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class TestSkinClusterDirtyPropagation(unittest.TestCase):
    """Option D: weightList plug edits drive a live re-deform."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _build_weight_driven_skin(self):
        """A skinCluster whose Compute pushes each vertex's Y by its
        ``weights[0]`` value -- so a weight edit maps directly to a
        visible position change."""
        plane = mc.polyPlane(name="sP", w=2, h=2, sx=4, sy=4)[0]
        sc = mc.deformer(plane, type="mPySkinCluster")[0]
        mc.setAttr(sc + ".weightList[0].weights[0]", 0.0)
        mc.setAttr(
            sc + "._computeSource",
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "for v, vplug in self.weightList:\n"
            "    for j, w in vplug.weights:\n"
            "        if j == 0:\n"
            "            pts[int(v), 1] += float(w)\n"
            "mesh.setPoints(pts)\n",
            type="string",
        )
        return plane, sc

    def test_weightlist_edit_redeforms_without_dgdirty(self):
        plane, sc = self._build_weight_driven_skin()

        # First eval: weight is 0 -> vtx[0] stays at rest Y.
        y0 = mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(y0, 0.0, places=4)

        # Edit the weight plug exactly like the Component Editor / Paint
        # tools do -- and DO NOT call dgdirty.
        mc.setAttr(sc + ".weightList[0].weights[0]", 1.0)

        y1 = mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(
            y1, 1.0, places=4,
            msg="editing weightList[0].weights[0] must re-evaluate the "
                "deformer without an explicit dgdirty (got y=%r)" % y1,
        )

    def test_computesource_only_edit_redeforms_without_dgdirty(self):
        """Editing ONLY the Compute expression at runtime must re-evaluate
        the output. Nothing but setDependentsDirty covers _computeSource, so
        this fails if the override is a no-op (the bound-method bug)."""
        plane = mc.polyPlane(name="cP", w=2, h=2, sx=4, sy=4)[0]
        sc = mc.deformer(plane, type="mPySkinCluster")[0]

        # First eval with a no-op expression -> output == input (rest).
        mc.setAttr(sc + "._computeSource", "pass", type="string")
        y0 = mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(y0, 0.0, places=4)

        # Change ONLY the expression -- no weight/joint/envelope edit, no dgdirty.
        mc.setAttr(
            sc + "._computeSource",
            "mesh = self.outputGeometry[0]\n"
            "pts = mesh.getPoints()\n"
            "pts[:, 1] += 3.0\n"
            "mesh.setPoints(pts)\n",
            type="string",
        )
        y1 = mc.xform(plane + ".vtx[0]", q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(
            y1, 3.0, places=4,
            msg="editing only _computeSource must re-evaluate the deformer "
                "without an explicit dgdirty (got y=%r)" % y1,
        )


class TestCustomLBSDemoWeightList(unittest.TestCase):
    """Option C: the customLBS demo is weightList-driven."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _build_demo_no_save(self):
        import mpynode._demos.build_mPySkinCluster_customLBS as builder

        self._saved = builder.save_demo
        builder.save_demo = lambda *a, **k: None  # don't overwrite the shipped .ma
        try:
            builder.build()
        finally:
            builder.save_demo = self._saved
        return builder

    def test_compute_source_reads_weightlist_not_storedvar(self):
        import mpynode._demos.build_mPySkinCluster_customLBS as builder

        self.assertIn("self.weightList", builder.COMPUTE_SOURCE)
        self.assertNotIn(
            "vertex_weights", builder.COMPUTE_SOURCE,
            "Compute must densify from self.weightList, not the "
            "vertex_weights stored var",
        )

    def test_demo_populates_weightlist_and_deforms(self):
        self._build_demo_no_save()
        node = mc.ls(type="mPySkinCluster")[0]

        # weightList plug actually has per-vertex entries.
        idx = mc.getAttr(node + ".weightList", multiIndices=True)
        self.assertTrue(idx, "demo must populate the weightList plug")
        # Each populated vertex carries BOTH influences (base + mid), incl. zeros.
        w0 = mc.getAttr(node + ".weightList[0].weights", multiIndices=True)
        self.assertEqual(
            sorted(w0 or []), [0, 1],
            "every vertex should carry both influences (base + mid)",
        )
        # Weights read back as written (guards the kSkinCluster 0.5/0.5
        # first-eval lock-in: vtx[0] is at the bottom -> fully the base joint).
        self.assertAlmostEqual(mc.getAttr(node + ".weightList[0].weights[0]"), 1.0, places=4)
        self.assertAlmostEqual(mc.getAttr(node + ".weightList[0].weights[1]"), 0.0, places=4)

        shape = mc.listRelatives("skinnedCylinder", shapes=True, fullPath=True)[0]
        n = mc.polyEvaluate(shape, vertex=True)

        def top_centroid_x():
            # Mean x of the top ring: ~0 at rest (ring is centered on the Y
            # axis), large when the mid joint rotates it off-axis. (max|x| is
            # ~radius even at rest, so it would be a vacuous metric.)
            mc.dgdirty(node + ".outputGeometry")
            pts = np.asarray([
                mc.xform("%s.vtx[%d]" % (shape, v), q=True, ws=True, t=True)
                for v in range(n)
            ])
            top = pts[pts[:, 1] > 1.5]
            self.assertTrue(top.size, "expected vertices above y=1.5")
            return float(top[:, 0].mean())

        # build() posed skinMid to rotateZ 60 -> top ring swings off-axis.
        bent_x = top_centroid_x()
        mc.setAttr("skinMid.rotateZ", 0.0)            # un-pose -> rest
        rest_x = top_centroid_x()
        self.assertLess(abs(rest_x), 0.2, "rest top ring is centered on the Y axis")
        self.assertGreater(
            abs(bent_x - rest_x), 1.0,
            "posing the mid joint must swing the weightList-weighted top half "
            "off-axis (rest_x=%.3f bent_x=%.3f)" % (rest_x, bent_x),
        )


class TestSkinClusterIsRealSkinCluster(unittest.TestCase):
    """Option A headline: the node is a genuine skinCluster by type, so
    Maya's native skin tools recognise it. Guards against a regression back
    to the kDeformerNode fallback."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_lineage_is_real_skincluster(self):
        plane = mc.polyPlane(name="rP")[0]
        sc = mc.deformer(plane, type="mPySkinCluster")[0]
        inherited = mc.nodeType(sc, inherited=True)
        self.assertIn("skinCluster", inherited)
        self.assertIn("geometryFilter", inherited)

    def test_mfnskincluster_and_skinpercent_roundtrip(self):
        j1 = mc.joint(p=(0, 0, 0), n="rj1")
        mc.select(clear=True)
        j2 = mc.joint(p=(2, 0, 0), n="rj2")
        mc.select(clear=True)
        plane = mc.polyPlane(name="rP", w=2, h=2, sx=4, sy=4)[0]

        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        sc = MPySkinCluster.create(plane, joints=[j1, j2], name="realSkin")
        node = sc.get_name()

        # MFnSkinCluster recognises it + lists the influences.
        sel = om.MSelectionList()
        sel.add(node)
        mobj = om.MObject()
        sel.getDependNode(0, mobj)
        fn = oma.MFnSkinCluster(mobj)
        infs = om.MDagPathArray()
        fn.influenceObjects(infs)
        names = sorted(infs[i].partialPathName() for i in range(infs.length()))
        self.assertEqual(names, ["rj1", "rj2"])

        # The skinCluster command query works.
        self.assertEqual(sorted(mc.skinCluster(node, q=True, inf=True)), ["rj1", "rj2"])

        # skinPercent round-trips through the weightList plug (the path the
        # Component Editor / Paint Skin Weights use).
        mc.skinPercent(node, plane + ".vtx[0]", transformValue=[(j1, 0.7), (j2, 0.3)])
        self.assertAlmostEqual(
            mc.getAttr(node + ".weightList[0].weights[0]"), 0.7, places=4)
        self.assertEqual(
            mc.skinPercent(node, plane + ".vtx[0]", q=True, value=True), [0.7, 0.3])


if __name__ == "__main__":
    unittest.main()
