"""Interpreted ``WeightListView`` -- the dense weightList parity contract.

``np.asarray(self.weightList)`` on a genuine ``mPySkinCluster`` returns a dense
``(N, J)`` float64 matrix, LOGICAL-indexed (row v == vertex logical index, col j
== influence logical index), zero gap-fill, sized ``N = max painted vertex + 1``,
``J = max painted influence + 1``. This is the SAME dense contract the compiled
``deform()`` reader implements, so the two stay byte-parity. Per-element access
(``self.weightList[v].weights[j]``) must keep working (view subclasses the plain
multi proxy).
"""

from __future__ import annotations

import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import numpy as np

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _node_mobject(name):
    sel = om.MSelectionList()
    sel.add(name)
    mo = om.MObject()
    sel.getDependNode(0, mo)
    return mo


def _proxy_for(name):
    from mpynode._common.plugs.plug_proxy import PlugProxy
    return PlugProxy(_node_mobject(name))


class TestWeightListView(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _bare_skin(self, sx=2, sy=2):
        """A mPySkinCluster on a plane with NO joints -- lets us drive the
        weightList plug directly with setAttr to exercise exact logical layouts
        (gaps included) without Maya's binding heuristics."""
        plane = mc.polyPlane(name="wlP", w=2, h=2, sx=sx, sy=sy)[0]
        sc = mc.deformer(plane, type="mPySkinCluster")[0]
        return plane, sc

    def test_view_type_and_detection(self):
        from mpynode._common.plugs.plug_proxy import WeightListView
        _plane, sc = self._bare_skin()
        mc.setAttr(sc + ".weightList[0].weights[0]", 0.7)
        mc.setAttr(sc + ".weightList[0].weights[1]", 0.3)
        wl = _proxy_for(sc).weightList
        self.assertIsInstance(wl, WeightListView)

    def test_dense_shape_and_values(self):
        _plane, sc = self._bare_skin()
        mc.setAttr(sc + ".weightList[0].weights[0]", 0.7)
        mc.setAttr(sc + ".weightList[0].weights[1]", 0.3)
        W = np.asarray(_proxy_for(sc).weightList)
        self.assertEqual(W.shape, (1, 2))
        self.assertTrue(np.allclose(W, [[0.7, 0.3]]), W)
        self.assertEqual(W.dtype, np.float64)

    def test_influence_gap_zero_filled(self):
        # Paint logical influences {0, 2} (skip 1): J = max+1 = 3, gap col = 0.
        _plane, sc = self._bare_skin()
        mc.setAttr(sc + ".weightList[0].weights[0]", 1.0)
        mc.setAttr(sc + ".weightList[0].weights[2]", 0.5)
        W = np.asarray(_proxy_for(sc).weightList)
        self.assertEqual(W.shape, (1, 3))
        self.assertTrue(np.allclose(W, [[1.0, 0.0, 0.5]]), W)

    def test_vertex_gap_zero_filled(self):
        # Paint vertices {0, 2} (skip 1): N = max+1 = 3, missing row all-zero.
        _plane, sc = self._bare_skin()
        mc.setAttr(sc + ".weightList[0].weights[0]", 0.9)
        mc.setAttr(sc + ".weightList[0].weights[1]", 0.1)
        mc.setAttr(sc + ".weightList[2].weights[0]", 0.4)
        mc.setAttr(sc + ".weightList[2].weights[1]", 0.6)
        W = np.asarray(_proxy_for(sc).weightList)
        self.assertEqual(W.shape, (3, 2))
        self.assertTrue(np.allclose(W[0], [0.9, 0.1]), W)
        self.assertTrue(np.allclose(W[1], [0.0, 0.0]), W)
        self.assertTrue(np.allclose(W[2], [0.4, 0.6]), W)

    def test_per_element_access_preserved(self):
        _plane, sc = self._bare_skin()
        mc.setAttr(sc + ".weightList[0].weights[0]", 0.7)
        mc.setAttr(sc + ".weightList[0].weights[1]", 0.3)
        wl = _proxy_for(sc).weightList
        # subclass keeps the plain multi proxy iteration + indexing.
        pairs = {int(j): float(w) for j, w in wl[0].weights}
        self.assertAlmostEqual(pairs[0], 0.7, places=6)
        self.assertAlmostEqual(pairs[1], 0.3, places=6)
        by_v = {int(v): vp for v, vp in wl}
        self.assertIn(0, by_v)

    def test_empty_weightlist_is_empty_2d(self):
        _plane, sc = self._bare_skin()
        W = np.asarray(_proxy_for(sc).weightList)
        self.assertEqual(W.ndim, 2)
        self.assertEqual(W.shape, (0, 0))


if __name__ == "__main__":
    unittest.main()
