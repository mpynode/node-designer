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

    def test_first_tick_fires(self):
        st = self._state()
        self.assertTrue(self._step(st, 10.0))
        self.assertEqual(st["last_dirty"], 10.0)
        self.assertEqual(st["last_redraw"], 0.0)

    def test_mayas_47ms_cadence_is_not_read_as_a_redraw(self):
        # under any redraw load Maya fires the 33 ms timer every ~47 ms (measured:
        # 21 ticks/s with ten cheap locators); that must keep the full rate.
        st = self._state()
        fired = [self._step(st, 10.0 + i * 0.047) for i in range(30)]
        self.assertTrue(all(fired))
        self.assertEqual(st["last_redraw"], 0.0)

    def test_heavy_redraw_when_the_tick_runs_after_it(self):
        # compiled path ordering: request, redraw (125 ms), then the tick
        st = self._state()
        self.assertTrue(self._step(st, 0.0))
        # the late tick carries the cost; it may fire once more back-to-back,
        # but from here on the wait is 2 x 0.125
        self.assertTrue(self._step(st, 0.125))
        self.assertAlmostEqual(st["last_redraw"], 0.125)
        for t in (0.25, 0.283, 0.316, 0.349):
            self.assertFalse(self._step(st, t))
        self.assertTrue(self._step(st, 0.382))              # 0.257 >= 0.25 since the request

    def test_heavy_redraw_when_the_tick_runs_before_it(self):
        # interpreted path ordering: request, the due tick fires ON TIME (the
        # redraw has not run yet), THEN the 257 ms redraw delays the next tick.
        # v28 measured only the first tick and read the scene as cheap (92%).
        st = self._state()
        self.assertTrue(self._step(st, 0.0))
        t1 = P * 1.01
        self.assertTrue(self._step(st, t1))                 # on time -> coalesced request
        self.assertTrue(self._step(st, t1 + 0.257))         # late 0.257 -> becomes the cost
        self.assertAlmostEqual(st["last_redraw"], 0.257)
        t2 = t1 + 0.257
        for dt in (0.26, 0.293, 0.326, 0.46):
            self.assertFalse(self._step(st, t2 + dt))       # wait = 0.514 since the request
        self.assertTrue(self._step(st, t2 + 0.52))

    def _duty(self, R, tick_before_redraw):
        """Simulate: a request costs R on the main thread; ticks otherwise come
        every P. ``tick_before_redraw`` models Maya running the due tick before
        the redraw it triggered."""
        st = self._state()
        t, redraws, t_end = 0.0, 0, 10.0
        while t < t_end:
            if self._step(st, t):
                redraws += 1
                if tick_before_redraw:
                    t += P
                    self._step(st, t)                       # on-time tick; a fire here coalesces
                t += R                                      # redraw runs; next tick after it
            else:
                t += P
        return redraws * R / t_end

    def test_duty_cycle_stays_near_half_for_a_heavy_scene_either_ordering(self):
        for order in (False, True):
            busy = self._duty(0.125, order)
            self.assertLess(busy, 0.6, "ordering tick_before=%s busy=%.2f" % (order, busy))
            self.assertGreater(busy, 0.35, "ordering tick_before=%s busy=%.2f" % (order, busy))
        busy = self._duty(0.257, True)                      # Python N=100
        self.assertLess(busy, 0.6, "busy=%.2f" % busy)

    def test_cost_is_forgotten_when_the_scene_gets_cheap_again(self):
        st = self._state()
        self.assertTrue(self._step(st, 0.0))
        self.assertTrue(self._step(st, 0.125))              # late -> cost 0.125, wait 0.25
        # the scene got cheap: from here every tick is on cadence (no late gap)
        for t in (0.16, 0.20, 0.235, 0.27, 0.305, 0.34):
            self.assertFalse(self._step(st, t))
        self.assertTrue(self._step(st, 0.38))               # 0.255 >= 0.25; no late tick seen
        self.assertEqual(st["last_redraw"], 0.0)            # -> cost reset
        self.assertTrue(self._step(st, 0.38 + P * 1.01))    # full rate again


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
