"""A locator must report the extent it actually DRAWS.

MPxLocatorNode's stock bounding box is the unit cube scaled by ``localScale``,
which describes the little cross Maya draws for a plain locator -- not what an
mPyLocator expression puts on screen. Left at that, a gizmo drawing a radius-10
ring answered "unbounded" (±1e30), so framing the selection (`F`) zoomed to the
whole scene instead of to the ring, and a bbox pick had nothing useful to test
against. A stock `spaceLocator` does the right thing here, which is the
comparison that surfaced it.

The extent is measured off the buffers the draw already produced -- never by
evaluating the user expression a second time, since Maya asks for the box during
selection and framing.
"""
from __future__ import annotations

import unittest

import numpy as np

from mpynode._common.draw.draw_buffers import command_bounds
from tests._setup import standalone_init


def setUpModule():
    standalone_init()


def _cmd(slot, **buf):
    return {"slot": slot, "buffer": buf}


class TestCommandBounds(unittest.TestCase):
    """The pure measurement, one slot at a time."""

    def test_nothing_drawn_is_no_extent(self):
        # None, not a zero box: the caller falls back to the locator default
        # rather than reporting a point at the origin.
        self.assertIsNone(command_bounds([]))
        self.assertIsNone(command_bounds(None))

    def test_lines_span_both_endpoints(self):
        lo, hi = command_bounds([_cmd(
            "lines",
            starts=np.array([[-2.0, 0.0, 0.0], [0.0, 0.0, 0.0]]),
            ends=np.array([[0.0, 3.0, 0.0], [0.0, 0.0, 5.0]]))])
        self.assertEqual(lo, (-2.0, 0.0, 0.0))
        self.assertEqual(hi, (0.0, 3.0, 5.0))

    def test_polygons_points_count(self):
        lo, hi = command_bounds([_cmd(
            "polygons", points=np.array([[1.0, 1.0, 1.0], [4.0, 2.0, 3.0]]))])
        self.assertEqual((lo, hi), ((1.0, 1.0, 1.0), (4.0, 2.0, 3.0)))

    def test_shapes_grow_by_their_radius(self):
        # A sphere whose CENTRE is in frame is not the same as a sphere that is
        # in frame -- the radius has to count.
        lo, hi = command_bounds([_cmd(
            "shapes",
            centers=np.array([[0.0, 0.0, 0.0]]),
            radii=np.array([2.5]))])
        self.assertEqual((lo, hi), ((-2.5, -2.5, -2.5), (2.5, 2.5, 2.5)))

    def test_text_contributes_only_its_anchor(self):
        # Glyphs are sized in PIXELS; their on-screen extent is not an
        # object-space quantity and would move the box with the camera.
        lo, hi = command_bounds([_cmd(
            "text", positions=np.array([[0.0, 7.0, 0.0]]),
            sizes=np.array([48.0]))])
        self.assertEqual((lo, hi), ((0.0, 7.0, 0.0), (0.0, 7.0, 0.0)))

    def test_world_space_buffers_are_skipped(self):
        # Their points are already in WORLD space while the box is reported in
        # object space -- unioning the two puts the box where the drawing isn't.
        cmds = [_cmd("polygons", points=np.array([[1.0, 0.0, 0.0]])),
                _cmd("polygons", points=np.array([[500.0, 0.0, 0.0]]),
                     world_space=True)]
        lo, hi = command_bounds(cmds)
        self.assertEqual(hi, (1.0, 0.0, 0.0))
        self.assertEqual(command_bounds(cmds, include_world=True)[1],
                         (500.0, 0.0, 0.0))

    def test_several_slots_union(self):
        lo, hi = command_bounds([
            _cmd("points", positions=np.array([[-1.0, -1.0, -1.0]])),
            _cmd("lines", starts=np.array([[0.0, 0.0, 0.0]]),
                 ends=np.array([[2.0, 0.0, 0.0]])),
        ])
        self.assertEqual((lo, hi), ((-1.0, -1.0, -1.0), (2.0, 0.0, 0.0)))

    def test_non_finite_points_do_not_poison_the_box(self):
        # One NaN from a divide in an expression would otherwise make the whole
        # box NaN, and framing would go somewhere undefined.
        lo, hi = command_bounds([_cmd(
            "points",
            positions=np.array([[1.0, 1.0, 1.0], [np.nan, 0.0, 0.0]]))])
        self.assertEqual((lo, hi), ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0)))

    def test_a_malformed_buffer_is_ignored_not_raised(self):
        # boundingBox() runs during selection; it must never throw.
        self.assertIsNone(command_bounds([_cmd("points", positions="nonsense")]))
        self.assertIsNone(command_bounds([{"slot": "points"}]))


class TestLocatorReportsItsDrawnExtent(unittest.TestCase):

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def _locator(self, name, body):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name=name)
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawCurve, DrawSphere\n"
            + body)
        return loc

    def _mpx(self, loc):
        import maya.api.OpenMaya as om

        sel = om.MSelectionList()
        sel.add(loc.get_name())
        return om.MFnDependencyNode(sel.getDependNode(0)).userNode()

    _RING = ("t = np.linspace(0.0, 2.0 * np.pi, 33)\n"
             "pts = np.stack([np.cos(t) * 10.0, np.zeros(33),\n"
             "                np.sin(t) * 10.0], axis=1)\n"
             "self.draw = DrawCurve(pts, closed=True)\n")

    def test_the_box_matches_what_was_drawn(self):
        import maya.cmds as mc

        loc = self._locator("boundsRing", self._RING)
        loc.evaluate_draw_commands()
        bb = mc.exactWorldBoundingBox(loc.get_name())
        self.assertAlmostEqual(bb[0], -10.0, places=2)   # xmin
        self.assertAlmostEqual(bb[3],  10.0, places=2)   # xmax
        self.assertAlmostEqual(bb[5],  10.0, places=2)   # zmax
        self.assertTrue(self._mpx(loc).isBounded())

    def test_the_box_follows_the_drawing(self):
        import maya.cmds as mc

        loc = self._locator("boundsGrow", self._RING)
        loc.evaluate_draw_commands()
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawCurve, DrawSphere\n"
            "self.draw = DrawSphere(center=(0, 0, 0), radius=40.0)\n")
        loc.evaluate_draw_commands()
        bb = mc.exactWorldBoundingBox(loc.get_name())
        self.assertAlmostEqual(bb[3], 40.0, places=2)

    def test_an_undrawn_locator_keeps_the_stock_answer(self):
        # The bounds are a by-product of drawing. Before the first draw the node
        # defers to MPxLocatorNode, which reports unbounded -- so nothing is
        # ever culled on the strength of a box we have not measured yet.
        loc = self._locator("boundsUndrawn", "self.draw = None\n")
        mpx = self._mpx(loc)
        self.assertIsNone(getattr(mpx, "_draw_bounds", "missing"))
        self.assertGreater(float(mpx.boundingBox().width), 1e29)

    def test_a_drawing_that_stops_drawing_releases_its_box(self):
        loc = self._locator("boundsCleared", self._RING)
        loc.evaluate_draw_commands()
        self.assertIsNotNone(self._mpx(loc)._draw_bounds)
        loc.set_compute_expression("self.draw = None\n")
        loc.evaluate_draw_commands()
        self.assertIsNone(self._mpx(loc)._draw_bounds)

    def test_the_box_is_not_a_second_expression_run(self):
        # Maya asks for the box during selection and framing; running user code
        # there would be a surprise (and re-entrant).
        loc = self._locator(
            "boundsNoRerun",
            "self.count = float(getattr(self, 'count', 0.0)) + 1.0\n" + self._RING)
        loc.evaluate_draw_commands()
        mpx = self._mpx(loc)
        before = mpx._draw_bounds
        for _ in range(5):
            mpx.boundingBox()
        self.assertEqual(mpx._draw_bounds, before)


if __name__ == "__main__":
    unittest.main()
