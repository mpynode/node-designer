"""Selecting a translucent gizmo must not make it solid.

Maya's wireframe colour is opaque, and the framework's auto-highlight used to
hand that colour straight to ``setColor`` for every element -- so a drawing that
deliberately fades out (a shaded band, a ghosted guide, anything carrying alpha)
snapped to fully opaque the moment the node was selected, which reads as the
gizmo changing SHAPE rather than changing state.

The rule under test is the one ``MPyLocatorDrawOverride._tinted`` encodes: the
selection highlight replaces hue, never opacity. These tests drive the draw
helpers with a recording draw manager, because the colour is decided in the
draw call itself -- nothing upstream in the buffers shows whether it survived.
"""
from __future__ import annotations

import unittest

import numpy as np

import maya.api.OpenMaya as om

from mpynode._api2.mpy_locator import MPyLocatorDrawOverride as DO
from tests import _setup


def setUpModule():
    _setup.standalone_init()


SEL = om.MColor((0.0, 1.0, 0.4, 1.0))       # opaque, the way Maya hands it over


class _FakeDrawManager:
    """Records the colours the override asks for; no-ops every draw call."""

    def __init__(self):
        self.colors = []  # every setColor, in order
        self.meshes = []  # (points, colors-or-None) per mesh call

    def setColor(self, color):
        self.colors.append((float(color.r), float(color.g), float(color.b),
                            float(color.a)))

    def mesh(self, prim, points, normals=None, colors=None):
        self.meshes.append((points, colors))

    mesh2d = mesh

    def __getattr__(self, name):            # line, point, text, setLineWidth...
        return lambda *a, **kw: None


class TestSelectionTintKeepsAlpha(unittest.TestCase):

    def test_lines_keep_their_own_alpha(self):
        """Per-segment alpha survives; only the hue becomes the selection's."""
        buf = {
            "starts": np.zeros((3, 3), dtype=np.float32),
            "ends":   np.ones((3, 3), dtype=np.float32),
            "colors": np.array([[1.0, 0.85, 0.2, 0.0],
                                [1.0, 0.85, 0.2, 0.5],
                                [1.0, 0.85, 0.2, 1.0]], dtype=np.float32),
        }
        dm = _FakeDrawManager()
        DO._draw_lines(dm, buf, override=SEL)
        self.assertEqual([round(c[3], 3) for c in dm.colors], [0.0, 0.5, 1.0])
        for c in dm.colors:
            self.assertEqual((round(c[0], 3), round(c[1], 3), round(c[2], 3)),
                             (0.0, 1.0, 0.4))

    def test_uniform_fill_keeps_its_alpha(self):
        """The one-setColor fast path tints without going opaque."""
        buf = {"colors": np.array([0.2, 0.4, 1.0, 0.35], dtype=np.float32)}
        pts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                       dtype=np.float64)
        idx = np.array([0, 1, 2], dtype=np.int64)
        cnt = np.array([3], dtype=np.int64)
        dm  = _FakeDrawManager()
        DO._draw_poly_fill(dm, buf, pts, idx, cnt, cnt, None, None, SEL)
        self.assertEqual(len(dm.colors), 1)
        self.assertAlmostEqual(dm.colors[0][3], 0.35, places=5)
        self.assertEqual((round(dm.colors[0][0], 3), round(dm.colors[0][1], 3)),
                         (0.0, 1.0))

    def test_vertex_colors_keep_their_ramp(self):
        """A faded patch selected: per-corner alphas intact, hue replaced.

        The tint has to move to a per-corner colour ARRAY here -- one flat
        setColor cannot carry a ramp -- which is exactly what used to be lost.
        """
        pts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                        [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float64)
        idx = np.array([0, 1, 2, 3], dtype=np.int64)
        cnt = np.array([4], dtype=np.int64)
        buf = {"vertex_colors": np.array([[1.0, 0.85, 0.2, 0.0],
                                          [1.0, 0.85, 0.2, 0.25],
                                          [1.0, 0.85, 0.2, 0.75],
                                          [1.0, 0.85, 0.2, 1.0]],
                                         dtype=np.float32)}
        dm = _FakeDrawManager()
        DO._draw_poly_fill(dm, buf, pts, idx, cnt, cnt, None, None, SEL)
        self.assertEqual(len(dm.meshes), 1)
        colors = dm.meshes[0][1]
        self.assertIsNotNone(colors, "a tinted ramp must still draw per-corner")
        got = sorted({round(float(colors[i].a), 3) for i in range(len(colors))})
        self.assertEqual(got, [0.0, 0.25, 0.75, 1.0])
        self.assertEqual((round(float(colors[0].r), 3),
                          round(float(colors[0].g), 3),
                          round(float(colors[0].b), 3)), (0.0, 1.0, 0.4))

    def test_wireframe_keeps_its_alpha(self):
        pts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                       dtype=np.float64)
        idx = np.array([0, 1, 2], dtype=np.int64)
        cnt = np.array([3], dtype=np.int64)
        buf = {"wireframe": (1.0, 1.0, 1.0, 0.2), "wireframe_width": 2.0}
        dm  = _FakeDrawManager()
        DO._draw_poly_wire(dm, buf, pts, idx, cnt, None, SEL, SEL)
        self.assertTrue(dm.colors)
        self.assertAlmostEqual(dm.colors[0][3], 0.2, places=5)
        self.assertEqual((round(dm.colors[0][0], 3), round(dm.colors[0][1], 3)),
                         (0.0, 1.0))

    def test_unselected_drawing_is_untouched(self):
        """No override -> the buffer's own colours, alpha and all."""
        buf = {
            "starts": np.zeros((2, 3), dtype=np.float32),
            "ends":   np.ones((2, 3), dtype=np.float32),
            "colors": np.array([[1.0, 0.85, 0.2, 0.3],
                                [0.1, 0.2, 0.3, 0.9]], dtype=np.float32),
        }
        dm = _FakeDrawManager()
        DO._draw_lines(dm, buf, override=None)
        self.assertEqual([round(c[3], 3) for c in dm.colors], [0.3, 0.9])
        self.assertEqual(round(dm.colors[1][0], 3), 0.1)

    def test_opaque_drawing_still_reads_as_selected(self):
        """The common case is unchanged: opaque in, selection colour out."""
        buf = {
            "starts": np.zeros((1, 3), dtype=np.float32),
            "ends":   np.ones((1, 3), dtype=np.float32),
            "colors": np.array([[1.0, 0.85, 0.2, 1.0]], dtype=np.float32),
        }
        dm = _FakeDrawManager()
        DO._draw_lines(dm, buf, override=SEL)
        self.assertEqual([round(c, 3) for c in dm.colors[0]],
                         [0.0, 1.0, 0.4, 1.0])


if __name__ == "__main__":
    unittest.main()
