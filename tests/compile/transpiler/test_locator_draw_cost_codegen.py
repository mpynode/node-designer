"""Locator draw-override codegen: what a live-session measurement of 100
compiled Animated Text locators (2026-09) pinned into the emitter.

Per redraw a node cost 1.22 ms, of which the 8 sparkle points were 0.68 ms:
VP2 caches its fat-point shader BY size value, so eight distinct float sizes
were eight shader instances per node per frame (85 us each). Whole-pixel
sizes recover 87% of that. One ``beginDrawable/endDrawable`` pair per ITEM
(80 per node) cost another 10%; the interpreted framework opens one per node.
Text sizes reached ``setFontSize`` as raw object-space heights (0.3-0.8 ->
unsigned 0), so every compiled glyph drew at Maya's fallback size instead of
the framework's pixels-per-object-unit scaling. And an auto_refresh locator
dirtied itself 30x/s regardless of what a redraw cost: 100 of them held the
main thread at 98%, 7.8 fps, at idle. These tests pin the four fixes in the
generated C++; the numbers themselves live in tools/harness/viewport_bench.py
and the idle probe.
"""
from __future__ import annotations

import unittest

from mpynode.native import compiler as codegen


def _spec(needs_hover):
    spec = {
        "schema_version": 1,
        "source_node": "gizmoCube",
        "mpy_type": "mPyLocator",
        "suggested": {
            "node_type_name": "gizmoCube", "class_name": "GizmoCube",
            "type_id": "0x00070123", "mpx_base": "MPxLocatorNode",
            "note": "viewport draw override", "heaviness": "hard",
        },
        "inputs": {
            "wire_width": {"type": "float", "is_array": False,
                           "default_value": 2.0, "portable": True},
        },
        "outputs": {},
        "variables": {},
        "compute": ("scale = 1.0 if self.hovered else 0.5\n"
                    "self.auto_refresh = True\n"
                    "self.polygons = None\n"),
        "init": "",
        "affects": "all",
    }
    if needs_hover:
        spec["needs_hover"] = True
    return spec


def _fn_body(cpp, signature):
    start = cpp.index(signature)
    end = cpp.index("\n}\n", start) + 3
    return cpp[start:end]


class TestWholePixelPointSizes(unittest.TestCase):
    def setUp(self):
        self.cpp = codegen._generate_locator_cpp(_spec(True))

    def test_point_size_goes_through_the_rounding_helper(self):
        self.assertIn("dm.setPointSize(_pointPx(d->pointSize[i]));", self.cpp)
        self.assertNotIn("dm.setPointSize(d->pointSize[i]);", self.cpp)

    def test_helper_rounds_and_never_goes_below_one_pixel(self):
        self.assertIn("static float _pointPx(float s)", self.cpp)
        self.assertIn("std::lround((double)s)", self.cpp)
        self.assertIn("p < 1 ? 1 : p", self.cpp)

    def test_helper_names_the_framework_twin(self):
        # both paths must round the same way or the two nodes draw differently
        self.assertIn("draw_buffers.point_pixel_size", self.cpp)


class TestOneDrawableBatchPerNode(unittest.TestCase):
    def setUp(self):
        self.cpp = codegen._generate_locator_cpp(_spec(True))
        self.body = _fn_body(self.cpp, "::addUIDrawables(const MDagPath& objPath,")

    def test_one_pair_around_the_replay_loop_plus_the_polygon_bracket(self):
        # begin before the loop + re-open after _drawPoly; end after the loop +
        # close before _drawPoly (which opens its own batches).
        self.assertEqual(self.body.count("dm.beginDrawable()"), 2)
        self.assertEqual(self.body.count("dm.endDrawable()"), 2)
        self.assertLess(self.body.index("dm.beginDrawable();"),
                        self.body.index("for (size_t ci = 0; ci < d->cmds.size(); ++ci)"))
        self.assertIn("dm.endDrawable(); _drawPoly(dm, *d, d->polys[i], wInv); dm.beginDrawable();",
                      self.body)

    def test_items_no_longer_open_their_own_batch(self):
        for item in ("dm.line(a, b); dm.endDrawable();",
                     "dm.text(d->textPos[i], d->textStr[i]); dm.endDrawable();"):
            self.assertNotIn(item, self.body)

    def test_polygon_soups_keep_their_own_batches(self):
        poly = _fn_body(self.cpp, "static void _drawPoly(")
        self.assertGreaterEqual(poly.count("dm.beginDrawable()"), 2)


class TestTextSizedInPixels(unittest.TestCase):
    def setUp(self):
        self.cpp = codegen._generate_locator_cpp(_spec(True))

    def test_font_size_is_object_height_times_pixels_per_unit(self):
        self.assertIn("dm.setFontSize(_textPx(d->textSize[i], d->localPpu));", self.cpp)
        self.assertNotIn("dm.setFontSize((unsigned)d->textSize[i]);", self.cpp)

    def test_helper_clamps_like_local_text_pixel_size(self):
        self.assertIn("static unsigned _textPx(double size, double ppu)", self.cpp)
        self.assertIn("px < 6.0", self.cpp)
        self.assertIn("px > 256.0", self.cpp)
        # no view scale (headless) -> the size is taken as pixels, as the framework
        self.assertIn("if (ppu <= 0.0) return (unsigned)(size < 0.0 ? 0.0 : size);", self.cpp)

    def test_prepare_for_draw_measures_pixels_per_object_unit(self):
        prep = _fn_body(self.cpp, "::prepareForDraw(const MDagPath& objPath,")
        for tok in ("MHWRender::MFrameContext::kViewProjMtx",
                    "frameContext.getViewportDimensions(_vx, _vy, _vw, _vh);",
                    "data->localPpu = _ppw * ((_prod > 0.0) ? std::cbrt(_prod) : 1.0);",
                    "data->localPpu = 0.0;"):
            self.assertIn(tok, prep)
        # camera up axis is row 1 of the camera matrix, as the framework's
        # pixels_per_world_unit(view_proj, vp_h, anchor_world, up_world)
        self.assertIn("MVector _up(_camW(1,0), _camW(1,1), _camW(1,2));", prep)

    def test_data_carries_the_scale(self):
        self.assertIn("double localPpu = 0.0;", self.cpp)


class TestThrottledIdleRefresh(unittest.TestCase):
    def setUp(self):
        self.cpp = codegen._generate_locator_cpp(_spec(True))
        self.poll = _fn_body(self.cpp, "static void _poll(float, float, void*) {")

    def test_poll_measures_the_redraw_on_the_armed_tick(self):
        self.assertIn("if (g_armed) { g_lastRedraw = (_gap > 1.25 * _period) ? _gap : 0.0; g_armed = false; }",
                      self.poll)

    def test_poll_waits_twice_the_measured_redraw_never_less_than_a_period(self):
        self.assertIn("const double _wait = std::max(_period, 2.0 * g_lastRedraw);", self.poll)
        self.assertIn("(_now - g_lastDirtyT) >= _wait", self.poll)
        self.assertIn("g_lastDirtyT = _now; g_armed = true;", self.poll)

    def test_dirtying_is_inside_the_gate(self):
        gate = self.poll.index("(_now - g_lastDirtyT) >= _wait")
        dirty = self.poll.index("setGeometryDrawDirty(h->second.object())")
        self.assertLess(gate, dirty)

    def test_hover_ray_cast_is_not_throttled(self):
        # only the idle-redraw request is gated; the cursor ray still runs each tick
        self.assertIn("_cursorRay(o, d)", self.poll)
        self.assertLess(self.poll.index("setGeometryDrawDirty"), self.poll.index("_cursorRay(o, d)"))


class TestNonHoverLocatorSharesTheDrawPath(unittest.TestCase):
    def setUp(self):
        self.cpp = codegen._generate_locator_cpp(_spec(False))

    def test_draw_fixes_apply_without_the_hover_service(self):
        for tok in ("_pointPx(d->pointSize[i])", "_textPx(d->textSize[i], d->localPpu)",
                    "double localPpu = 0.0;", "MHWRender::MFrameContext::kViewProjMtx"):
            self.assertIn(tok, self.cpp)

    def test_no_poll_no_throttle_state(self):
        for tok in ("g_lastDirtyT", "g_lastRedraw", "g_armed", "static void _poll("):
            self.assertNotIn(tok, self.cpp)

    def test_helpers_stay_plugin_only(self):
        self.assertLess(self.cpp.index("#ifndef MPYNODE_PROBE"),
                        self.cpp.index("static float _pointPx(float s)"))


if __name__ == "__main__":
    unittest.main()
