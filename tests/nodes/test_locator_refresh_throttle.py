"""Interpreted locator side of the 2026-09 draw-cost pass: whole-pixel point
sizes (``draw_buffers.point_pixel_size``), the shared idle-refresh timer in
``draw_refresh`` throttled on the main thread's CPU clock, the
``self.wallclock`` draw-context slot, the ``self.time`` fix, and the in-memory
Watch snapshot.

Measured in a live session before the pass: ten interpreted Animated Text
locators dirtied themselves from ten 30 fps timers and held the main thread at
93% while Maya sat idle; a hundred compiled ones held it at 98% at 7.8 fps.
Three meters were tried: the timer's own lateness (misread Maya's ~47 ms tick
cadence), Maya's render messages and VP2's end-of-render notification (both
delivered on Maya's schedule, so the first "render finished" after a request
was the previous redraw's). The thread's CPU clock depends on none of that:
an idle main thread consumes none, so CPU since the last request is that
request's cost, and the next request waits twice it.
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
    """Pure state machine driven by two explicit clocks: wall (monotonic) and
    the main thread's CPU. Between ticks the thread is idle unless a redraw
    ran, so CPU only advances by the redraw's cost."""

    def _state(self):
        from mpynode._common.draw import draw_refresh

        return draw_refresh._fresh_throttle_state()

    def _step(self, st, now, cpu):
        from mpynode._common.draw import draw_refresh

        return draw_refresh.throttle_step(st, now, cpu)

    def test_first_tick_fires(self):
        st = self._state()
        self.assertTrue(self._step(st, 10.0, 100.0))
        self.assertEqual(st["last_dirty"], 10.0)
        self.assertEqual(st["cpu_at_dirty"], 100.0)

    def test_cheap_redraws_keep_the_full_tick_rate(self):
        # each request costs 9 ms of CPU; the tick after it sees 2 x 9 < period
        st = self._state()
        t, cpu, fired = 10.0, 100.0, 0
        for _ in range(30):
            if self._step(st, t, cpu):
                fired += 1
                cpu += 0.009
            t += P * 1.001
        self.assertEqual(fired, 30)

    def test_an_expensive_redraw_is_waited_out_twice(self):
        st = self._state()
        self.assertTrue(self._step(st, 0.0, 0.0))          # request; the redraw costs 125 ms CPU
        cpu = 0.125                                         # ...which the thread has spent by the next tick
        for t in (0.125, 0.158, 0.191, 0.224):
            self.assertFalse(self._step(st, t, cpu))        # wait = 0.25 since the request
        self.assertTrue(self._step(st, 0.257, cpu))
        self.assertAlmostEqual(st["last_cost"], 0.125)

    def test_user_work_on_the_main_thread_also_backs_off(self):
        # 200 ms of tumbling since the request reads as cost: wait 0.4 s
        st = self._state()
        self.assertTrue(self._step(st, 0.0, 0.0))
        self.assertFalse(self._step(st, 0.30, 0.20))
        self.assertTrue(self._step(st, 0.41, 0.20))

    def _duty(self, R, T=10.0):
        """Each request costs R CPU delivered while the thread is busy for R;
        the next tick comes right after; otherwise ticks come every P with no
        CPU spent. Returns the main-thread fraction spent on idle redraws."""
        st = self._state()
        t, cpu, redraws = 0.0, 0.0, 0
        while t < T:
            if self._step(st, t, cpu):
                redraws += 1
                t += R
                cpu += R
            else:
                t += P
        return redraws * R / T

    def test_duty_cycle_stays_near_half_for_heavy_scenes(self):
        # 65 ms: compiled N=100; 125 ms: compiled N=100 before the point fix;
        # 257 ms: interpreted N=100. Every earlier meter let one of these through.
        for R in (0.065, 0.125, 0.257):
            busy = self._duty(R)
            self.assertLess(busy, 0.55, "R=%.3f busy=%.2f" % (R, busy))
            self.assertGreater(busy, 0.4, "R=%.3f busy=%.2f" % (R, busy))

    def test_cost_is_forgotten_when_the_scene_gets_cheap(self):
        st = self._state()
        self.assertTrue(self._step(st, 0.0, 0.0))
        self.assertFalse(self._step(st, 0.125, 0.125))      # heavy: wait 0.25
        self.assertTrue(self._step(st, 0.26, 0.125))        # request; this one is cheap (2 ms)
        self.assertTrue(self._step(st, 0.26 + P * 1.01, 0.127))
        self.assertAlmostEqual(st["last_cost"], 0.002)

    def test_a_cpu_clock_that_goes_backwards_counts_as_zero(self):
        st = self._state()
        self.assertTrue(self._step(st, 0.0, 5.0))
        self.assertTrue(self._step(st, P * 1.01, 4.0))      # spent clamps to 0 -> full rate


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

    def test_the_tick_meters_the_threads_cpu_clock(self):
        import inspect

        from mpynode._common.draw import draw_refresh

        src = inspect.getsource(draw_refresh._shared_tick)
        self.assertIn("time.thread_time()", src)

    def test_module_stays_qt_free(self):
        import inspect

        from mpynode._common.draw import draw_refresh

        src = inspect.getsource(draw_refresh)
        self.assertNotIn("PySide", src)


class TestWallclockSlot(unittest.TestCase):
    """``self.wallclock``: the framework's animation clock (``time.time()``),
    injectable through ``evaluate_draw_commands(..., wallclock=)``."""

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def _loc(self, compute):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="wallclockShape")
        loc.set_init_expression("from mpynode._common.draw.draw_types import DrawText\n")
        loc.set_compute_expression(compute)
        return loc

    @staticmethod
    def _text_x(out):
        for cmd in out["commands"]:
            if cmd["slot"] == "text":
                return float(cmd["buffer"]["positions"][0][0])
        raise AssertionError("no text drawn: %r" % (out,))

    def test_a_pinned_clock_reaches_the_expression(self):
        loc = self._loc("self.auto_refresh = True\n"
                        "self.draw = DrawText('t', position=(float(self.wallclock), 0.0, 0.0))\n")
        for wc in (5.0, 7.5):
            self.assertAlmostEqual(
                self._text_x(loc.evaluate_draw_commands(0.0, wallclock=wc)), wc, places=3)

    def test_the_default_is_the_real_clock(self):
        import time

        loc = self._loc("self.auto_refresh = True\n"
                        "self.draw = DrawText('t', position=(float(self.wallclock), 0.0, 0.0))\n")
        x = self._text_x(loc.evaluate_draw_commands(0.0))
        # buffers are float32: ~1.7e9 has a 128 s spacing, so a wide tolerance
        self.assertLess(abs(x - time.time()), 600.0)

    def test_self_time_is_the_frame_passed_in(self):
        loc = self._loc("self.draw = DrawText('t', position=(float(self.time), 0.0, 0.0))\n")
        self.assertAlmostEqual(self._text_x(loc.evaluate_draw_commands(30.0)), 30.0, places=3)

    def test_prepare_for_draw_reads_the_frame_from_openmayaanim(self):
        # MAnimControl lives in OpenMayaAnim; read through OpenMaya it raised into
        # a swallowing except and self.time was ALWAYS 0.0 in the interpreted node.
        import inspect

        from mpynode._api2.mpy_locator import MPyLocatorDrawOverride

        src = inspect.getsource(MPyLocatorDrawOverride.prepareForDraw)
        self.assertIn("oma.MAnimControl.currentTime()", src)
        self.assertNotIn("om.MAnimControl", src)


class TestWatchSnapshotInMemory(unittest.TestCase):
    """A locator's expression runs inside VP2's prepareForDraw, where the
    snapshot plug write is refused; the Watch tab reads the in-memory copy."""

    def test_locals_survive_a_refused_plug_write(self):
        import maya.api.OpenMaya as om
        from maya import cmds
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode._common.instrumentation import snapshot_io

        cmds.file(new=True, force=True)
        loc = MPyLocator.create(name="watchMemShape")
        sel = om.MSelectionList()
        sel.add(loc.get_name())
        node_obj = sel.getDependNode(0)
        real = cmds.setAttr

        def _refuse(*_a, **_k):
            raise RuntimeError("cannot set attributes during draw")

        cmds.setAttr = _refuse
        try:
            snapshot_io.write_watch_vars(node_obj, {"ang": 1.5, "__framework__": {"wallclock": 2.0}})
        finally:
            cmds.setAttr = real
        snap = snapshot_io.read_watch_vars(loc.get_name())
        self.assertIsNotNone(snap, "the in-memory snapshot must serve the read")
        self.assertEqual(snap["ang"], 1.5)
        self.assertEqual(snap["__framework__"]["wallclock"], 2.0)

    def test_framework_block_is_sanitised_per_key(self):
        import base64
        import json
        import pickle

        from mpynode._common.instrumentation.watch import encode_watch_vars

        class _Unpicklable:
            def __reduce__(self):
                raise TypeError("nope")

        text = encode_watch_vars({"__framework__": {"draw": _Unpicklable(), "wallclock": 2.0}})
        data = pickle.loads(base64.b64decode(json.loads(text)["data_b64"]))
        fw = data["__framework__"]
        self.assertIsInstance(fw, dict, "one unpicklable slot must not collapse the block to a repr")
        self.assertEqual(fw["wallclock"], 2.0)
        self.assertIsInstance(fw["draw"], str)


if __name__ == "__main__":
    unittest.main()
