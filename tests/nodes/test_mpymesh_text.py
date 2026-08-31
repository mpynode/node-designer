"""mPyMesh SDF "MPyNode" text demo.

Pure-module checks on the stroke font + field, plus a reopen check on the
shipped example scene (live-transform glyph boxes -> one watertight mesh).
"""
from __future__ import annotations

import os
import unittest

import numpy as np

from mpynode._demos import sdf_text
from mpynode._common.nodes.mesh import sdf_dmc
from tests import _paths


_EXAMPLE_MA = os.path.join(_paths.ASSETS, "mPyMesh_text.ma")

# Deterministic vertex count of the "MPyNode" field at resolution 12.
_EXPECTED_POINTS = 5524


def setUpModule():
    import maya.standalone
    try:
        maya.standalone.initialize()
    except Exception:
        pass
    import maya.cmds as mc
    for plugin in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(plugin, q=True, loaded=True):
            mc.loadPlugin(plugin)


class TestSDFTextField(unittest.TestCase):
    def test_word_strokes_cover_all_letters(self):
        boxes = sdf_text.word_strokes("MPyNode")
        # 4+4+2+3+4+4+5 strokes for M,P,y,N,o,d,e.
        self.assertEqual(len(boxes), 26)

    def test_arrays_are_all_boxes(self):
        arr = sdf_text.strokes_to_arrays(sdf_text.word_strokes("MPyNode"))
        self.assertEqual(arr["matrices"].shape, (26, 4, 4))
        self.assertTrue(np.all(arr["shape_types"] == 1))   # all boxes
        self.assertTrue(np.all(arr["additive"]))

    def test_mesh_is_valid_watertight(self):
        arr = sdf_text.strokes_to_arrays(sdf_text.word_strokes("MPyNode"))
        pts, counts, idx = sdf_dmc.mesh_from_shapes(
            resolution=12, iso_value=0.0, **arr)
        self.assertEqual(pts.shape[0], _EXPECTED_POINTS)
        uniq = np.unique(idx)
        self.assertEqual(uniq.size, pts.shape[0])
        self.assertEqual(uniq[0], 0)
        self.assertEqual(uniq[-1], pts.shape[0] - 1)
        self.assertEqual(int(counts.sum()), idx.shape[0])
        # Spans the expected centred width (~9 units across 7 letters).
        width = pts[:, 0].max() - pts[:, 0].min()
        self.assertGreater(width, 8.5)
        self.assertLess(width, 9.8)


class TestSDFTextScene(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(_EXAMPLE_MA),
                         "text example scene not built yet")
    def test_example_scene_matches_reference(self):
        import maya.cmds as mc
        import maya.api.OpenMaya as om

        mc.file(_EXAMPLE_MA, open=True, force=True)
        shapes = mc.ls("*RenderShape", type="mesh", long=True)
        self.assertTrue(shapes, "no render shape in text scene")
        mc.polyEvaluate(shapes[0], vertex=True)
        sel = om.MSelectionList()
        sel.add(shapes[0])
        fn = om.MFnMesh(sel.getDagPath(0))
        pts = np.array([[p.x, p.y, p.z]
                        for p in fn.getPoints(om.MSpace.kObject)], np.float64)
        counts, conn = fn.getVertices()

        arr = sdf_text.strokes_to_arrays(sdf_text.word_strokes("MPyNode"))
        rp, rc, ri = sdf_dmc.mesh_from_shapes(resolution=12, iso_value=0.0, **arr)

        self.assertEqual(pts.shape[0], rp.shape[0])
        np.testing.assert_allclose(pts, rp, rtol=1e-5, atol=1e-6)
        np.testing.assert_array_equal(np.array(conn, np.int32), ri)


if __name__ == "__main__":
    unittest.main()
