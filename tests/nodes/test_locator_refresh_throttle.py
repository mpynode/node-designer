"""Interpreted locator side of the 2026-09 draw-cost pass: whole-pixel point
sizes (``draw_buffers.point_pixel_size``) and the shared, throttled
idle-refresh timer in ``draw_refresh``.

Measured in a live session before the change: ten interpreted Animated Text
locators dirtied themselves from ten 30 fps timers and held the main thread at
93% while Maya sat idle; a hundred compiled ones held it at 98% at 7.8 fps.
The throttle reads the redraw's cost off the first tick after its own request
(the timer fires only once the main thread is free again) and waits twice
that before the next request.
"""
from __future__ import annotations

import unittest

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


P = 1.0 / 30.0


class TestPointPixelSize(unittest.TestCase):
    def test_rounds_to_whole_pixels(self):
        from mpynode._common.draw.draw_buffers import point_pixel_size

        self.assertEqual(point_pixel_size(7.4), 7.0)
        self.assertEqual(point_pixel_size(7.6), 8.0)
        self.assertEqual(point_pixel_size(5), 5.0)
        self.assertIsInstance(point_pixel_size(5), float)

    def test_never_below_one_pixel(self):
        from mpynode._common.draw.draw_buffers import point_pixel_size

        self.assertEqual(point_pixel_size(0.2), 1.0)
        self.assertEqual(point_pixel_size(-3.0), 1.0)
        self.assertEqual(point_pixel_size("not a size"), 1.0)

    def test_draw_points_uses_it_in_both_spaces(self):
        import inspect

        from mpynode._api2.mpy_locator import MPyLocatorDrawOverride

        src = inspect.getsource(MPyLocatorDrawOverride._draw_points)
        self.assertEqual(src.count("dm.setPointSize(point_pixel_size(sizes_arr[i]))"), 2)
        self.assertNotIn("dm.setPointSize(float(sizes_arr[i]))", src)


class TestThrottleStep(unittest.TestCase):
    """Pure state machine; ticks are simulated with explicit clocks."""

    def _state(self):
        from mpynode._common.draw import draw_refresh

        return draw_refresh._fresh_throttle_state()

    def _step(self, st, now):
        from mpynode._common.draw import draw_refresh

        return draw_refresh.throttle_step(st, now)

    def test_first_tick_fires_and_arms(self):
        st = self._state()
        self.assertTrue(self._step(st, 10.0))
        self.assertTrue(st["armed"])
        self.assertEqual(st["last_dirty"], 10.0)

    def test_cheap_redraws_keep_the_full_tick_rate(self):
        # redraw cheaper than a tick: every tick arrives on time -> every tick fires
        st = self._state()
        fired = [self._step(st, 10.0 + i * P * 1.001) for i in range(30)]
        self.assertTrue(all(fired))
        self.assertEqual(st["last_redraw"], 0.0)

    def test_expensive_redraw_is_measured_once_and_waited_out_twice(self):
        st = self._state()
        self.assertTrue(self._step(st, 0.0))              # request; redraw takes 125 ms
        self.assertFalse(self._step(st, 0.125))            # first tick after it: late -> measured
        self.assertAlmostEqual(st["last_redraw"], 0.125)
        self.assertFalse(st["armed"])
        # idle cadence resumes; the cheap gaps must NOT forget the cost
        for t in (0.158, 0.191, 0.224):
            self.assertFalse(self._step(st, t))
            self.assertAlmostEqual(st["last_redraw"], 0.125)
        self.assertTrue(self._step(st, 0.257))             # >= 2 x 0.125 since the request
        self.assertTrue(st["armed"])

    def test_duty_cycle_stays_near_half_for_a_heavy_scene(self):
        # simulate: each request costs R on the main thread; the timer can fire
        # again only once the redraw is done; otherwise ticks come every P.
        R = 0.125
        st = self._state()
        t, requests, t_end = 0.0, 0, 10.0
        while t < t_end:
            if self._step(st, t):
                requests += 1
                t += R                     # the tick after the redraw
            else:
                t += P
        busy = requests * R / t_end
        self.assertLess(busy, 0.55)
        self.assertGreater(busy, 0.35)

    def test_cost_is_forgotten_when_the_scene_gets_cheap_again(self):
        st = self._state()
        self.assertTrue(self._step(st, 0.0))
        self.assertFalse(self._step(st, 0.125))            # heavy
        self.assertTrue(self._step(st, 0.26))              # next request
        self.assertTrue(self._step(st, 0.26 + P * 1.001))  # on time -> cheap now -> fires
        self.assertEqual(st["last_redraw"], 0.0)


class TestSharedTimer(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        from mpynode._common.draw import draw_refresh

        draw_refresh._reset_all_for_tests()

    def _node(self, name):
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name=name)
        sel = om.MSelectionList()
        sel.add(loc.get_name())
        return sel.getDependNode(0)

    def test_n_nodes_share_one_timer_and_it_stops_with_the_last(self):
        from mpynode._common.draw import draw_refresh

        a, b = self._node("sharedA"), self._node("sharedB")
        draw_refresh.enable(a)
        tid = draw_refresh._SHARED["timer_id"]
        self.assertIsNotNone(tid)
        draw_refresh.enable(b)
        self.assertEqual(draw_refresh._SHARED["timer_id"], tid, "second node must reuse the timer")
        self.assertEqual(draw_refresh.active_count(), 2)
        draw_refresh.disable(a)
        self.assertEqual(draw_refresh._SHARED["timer_id"], tid, "timer lives while one node is enabled")
        draw_refresh.disable(b)
        self.assertIsNone(draw_refresh._SHARED["timer_id"])
        self.assertEqual(draw_refresh.active_count(), 0)

    def test_shared_tick_dirties_every_enabled_node_when_the_gate_opens(self):
        from mpynode._common.draw import draw_refresh

        a, b = self._node("tickA"), self._node("tickB")
        draw_refresh.enable(a)
        draw_refresh.enable(b)
        seen = []

        class _FakeRenderer:
            @staticmethod
            def setGeometryDrawDirty(obj):
                seen.append(obj)

        class _FakeOmr:
            MRenderer = _FakeRenderer

        real = draw_refresh.omr
        draw_refresh.omr = _FakeOmr
        try:
            draw_refresh._shared_tick()
        finally:
            draw_refresh.omr = real
            draw_refresh._reset_all_for_tests()
        self.assertEqual(len(seen), 2)

    def test_module_stays_qt_free(self):
        import inspect

        from mpynode._common.draw import draw_refresh

        src = inspect.getsource(draw_refresh)
        self.assertNotIn("PySide", src)


if __name__ == "__main__":
    unittest.main()
