"""Per-wrapper Attributes-tab allowlist (USEFUL_INHERITED_PLUGS).

When "Show framework attrs" is OFF the Attributes tab shows only user-added attrs
+ each wrapper's curated USEFUL_INHERITED_PLUGS. These tests pin every wrapper's
allowlist content, prove the names are REAL inherited attrs on a live node (typo
guard), and enforce the cross-cutting invariants (every registered type declares
its own set; EXPOSED_INPUT_PLUGS is a subset).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import maya.standalone
maya.standalone.initialize()
import maya.cmds as mc


def setUpModule():
    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p)


def _leaves(node):
    out = set()
    for a in (mc.listAttr(node) or []):
        out.add(a.split(".")[-1].split("[")[0])
    return out


class TestBaseDefaultAndResolver(unittest.TestCase):
    def test_base_mpynode_default_is_empty_frozenset(self):
        from mpynode.wrappers._mpy_node import MPyNode
        self.assertEqual(MPyNode.USEFUL_INHERITED_PLUGS, frozenset())

    def test_resolver_returns_none_for_unregistered_type(self):
        from mpynode.ui.widgets.plug_tree_walker import _useful_inherited_plugs_for
        mc.file(new=True, force=True)
        loc = mc.spaceLocator(name="stockLoc")[0]  # stock Maya node, not mpy
        shp = mc.listRelatives(loc, shapes=True)[0]
        self.assertIsNone(_useful_inherited_plugs_for(shp))

    def test_resolver_returns_frozenset_for_registered_type(self):
        from mpynode.ui.widgets.plug_tree_walker import _useful_inherited_plugs_for
        mc.file(new=True, force=True)
        n = mc.createNode("mPyNode")
        self.assertEqual(_useful_inherited_plugs_for(n), frozenset())


class TestDeformerFamilyAllowlists(unittest.TestCase):
    def test_skin_allowlist(self):
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        from mpynode._common.plugs.plug_filter import DEFORMER_USEFUL
        expect = DEFORMER_USEFUL | {
            "skinningMethod", "normalizeWeights", "maxInfluences",
            "maintainMaxInfluences", "dropoff", "blendWeights",
            "bindPreMatrix", "geomMatrix",
        }
        self.assertEqual(MPySkinCluster.USEFUL_INHERITED_PLUGS, frozenset(expect))
        mc.file(new=True, force=True)
        j1 = mc.joint(p=(0, 0, 0)); mc.select(cl=True)
        j2 = mc.joint(p=(0, 2, 0)); mc.select(cl=True)
        pl      = mc.polyPlane(w=2, h=2, sx=1, sy=1)[0]
        sc      = MPySkinCluster.create(pl, joints=[j1, j2], name="wlSkin")
        leaves  = _leaves(sc.get_name())
        missing = MPySkinCluster.USEFUL_INHERITED_PLUGS - leaves
        self.assertFalse(missing, "allowlist names not on node: %r" % missing)

    def test_blendshape_allowlist(self):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
        from mpynode._common.plugs.plug_filter import DEFORMER_USEFUL
        # `weight` is not listed: it is a USER attr, so it shows in the
        # Attributes tab without needing an inherited-plug allowlist entry.
        self.assertEqual(
            MPyBlendShape.USEFUL_INHERITED_PLUGS,
            DEFORMER_USEFUL | {"targetGeometry"})
        mc.file(new=True, force=True)
        pl      = mc.polyPlane(w=2, h=2, sx=1, sy=1)[0]
        tgt     = mc.polyPlane(w=2, h=2, sx=1, sy=1)[0]
        bs      = MPyBlendShape.create(pl, targets=[tgt], name="wlBS")
        leaves  = _leaves(bs.get_name())
        missing = MPyBlendShape.USEFUL_INHERITED_PLUGS - leaves
        self.assertFalse(missing, "allowlist names not on node: %r" % missing)

    def test_deformer_allowlist(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        from mpynode._common.plugs.plug_filter import DEFORMER_USEFUL
        self.assertEqual(MPyDeformer.USEFUL_INHERITED_PLUGS, DEFORMER_USEFUL)


class TestDagGeometryAllowlists(unittest.TestCase):
    def test_transform_allowlist_equals_exposed_inputs(self):
        from mpynode.wrappers.mpy_transform import MPyTransform
        self.assertEqual(MPyTransform.USEFUL_INHERITED_PLUGS,
                         frozenset(MPyTransform.EXPOSED_INPUT_PLUGS))

    def test_locator_allowlist_empty(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        self.assertEqual(MPyLocator.USEFUL_INHERITED_PLUGS, frozenset())

    def test_geometry_output_allowlists(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface
        self.assertEqual(MPyMesh.USEFUL_INHERITED_PLUGS, frozenset({"outMesh"}))
        self.assertEqual(MPyNurbsCurve.USEFUL_INHERITED_PLUGS,
                         frozenset({"outCurve"}))
        self.assertEqual(MPyNurbsSurface.USEFUL_INHERITED_PLUGS,
                         frozenset({"outSurface"}))
        # typo guard: outputs are real attrs
        mc.file(new=True, force=True)
        for t, want in (("mPyMesh", "outMesh"), ("mPyNurbsCurve", "outCurve"),
                        ("mPyNurbsSurface", "outSurface")):
            n = mc.createNode(t)
            self.assertIn(want, _leaves(n))


class TestFileConstraintIkAllowlists(unittest.TestCase):
    def test_file_allowlist_essentials(self):
        from mpynode.wrappers.mpy_file import MPyFile
        expect = frozenset({
            "fileName", "uvCoord", "uCoord", "vCoord", "colorSpace",
            "wrapModeU", "wrapModeV", "outColor", "outColorR", "outColorG",
            "outColorB", "outAlpha", "outTransparency", "outSize", "osl",
        })
        self.assertEqual(MPyFile.USEFUL_INHERITED_PLUGS, expect)
        for noise in ("preFilter", "mipmapMode", "maxAnisotropy", "borderColor"):
            self.assertNotIn(noise, MPyFile.USEFUL_INHERITED_PLUGS)
        mc.file(new=True, force=True)
        n       = mc.createNode("mPyFile")
        missing = expect - _leaves(n)
        self.assertFalse(missing, "allowlist names not on node: %r" % missing)

    def test_constraint_allowlist(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint
        expect = frozenset({
            "targetTranslate", "targetTranslateX", "targetTranslateY",
            "targetTranslateZ", "targetRotate", "targetRotateX",
            "targetRotateY", "targetRotateZ", "targetWeight",
            "restTranslate", "restTranslateX", "restTranslateY",
            "restTranslateZ", "restRotate", "restRotateX", "restRotateY",
            "restRotateZ",
        })
        self.assertEqual(MPyConstraint.USEFUL_INHERITED_PLUGS, expect)

    def test_iksolver_allowlist(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver
        self.assertEqual(MPyIkSolver.USEFUL_INHERITED_PLUGS,
                         frozenset({"maxIterations", "tolerance"}))


class TestAllowlistInvariants(unittest.TestCase):
    def _wrapper_classes(self):
        from mpynode.ui.widgets.plug_tree_walker import _TYPE_TO_WRAPPER
        out = {}
        for typ, (mod, cls) in _TYPE_TO_WRAPPER.items():
            m        = __import__(mod, fromlist=[cls])
            out[typ] = getattr(m, cls)
        return out

    def test_every_registered_type_declares_its_own_allowlist(self):
        for typ, cls in self._wrapper_classes().items():
            self.assertIn("USEFUL_INHERITED_PLUGS", cls.__dict__,
                          "%s (%s) must declare its OWN USEFUL_INHERITED_PLUGS"
                          % (typ, cls.__name__))
            self.assertIsInstance(cls.__dict__["USEFUL_INHERITED_PLUGS"],
                                  frozenset)

    def test_exposed_inputs_subset_of_useful(self):
        for typ, cls in self._wrapper_classes().items():
            exposed = frozenset(getattr(cls, "EXPOSED_INPUT_PLUGS", ()) or ())
            useful  = getattr(cls, "USEFUL_INHERITED_PLUGS", frozenset())
            self.assertTrue(exposed <= useful,
                            "%s: EXPOSED_INPUT_PLUGS not subset of USEFUL: %r"
                            % (typ, exposed - useful))


if __name__ == "__main__":
    unittest.main()
