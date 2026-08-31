"""MPyLocator draw buffers, draw-state, refresh timer, A/B contract, basics, cull-backfaces

Consolidated from: test_phase29.py, test_phase29_2.py, test_phase30.py, test_phaseR_0_locator_ab.py, test_phase05.py, test_cull_backfaces.py.
"""

from __future__ import annotations

# ===================== from test_phase29.py =====================
import unittest

import numpy as np

from._setup import standalone_init


def _setUpModule__phase29():
    standalone_init()


# ===========================================================================
# 1. Schema shape
# ===========================================================================


class TestNormalizeColor(unittest.TestCase):
    def test_none_returns_default_tiled(self):
        from mpynode._common.draw.draw_buffers import normalize_color

        out = normalize_color(None, 3, default=(0.5, 0.5, 0.5, 1.0))
        self.assertEqual(out.shape, (3, 4))
        np.testing.assert_allclose(out[0], [0.5, 0.5, 0.5, 1.0])
        np.testing.assert_allclose(out[2], [0.5, 0.5, 0.5, 1.0])

    def test_uniform_rgb_gets_alpha_1(self):
        from mpynode._common.draw.draw_buffers import normalize_color

        out = normalize_color((1.0, 0.0, 0.0), 4)
        self.assertEqual(out.shape, (4, 4))
        for i in range(4):
            np.testing.assert_allclose(out[i], [1.0, 0.0, 0.0, 1.0])

    def test_uniform_rgba_passes_through(self):
        from mpynode._common.draw.draw_buffers import normalize_color

        out = normalize_color((1.0, 0.0, 0.0, 0.5), 2)
        np.testing.assert_allclose(out[0], [1.0, 0.0, 0.0, 0.5])
        np.testing.assert_allclose(out[1], [1.0, 0.0, 0.0, 0.5])

    def test_per_element_rgb_gets_alpha(self):
        from mpynode._common.draw.draw_buffers import normalize_color

        src = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
        out = normalize_color(src, 3)
        self.assertEqual(out.shape, (3, 4))
        np.testing.assert_allclose(out[1], [0.0, 1.0, 0.0, 1.0])

    def test_per_element_rgba_passes_through(self):
        from mpynode._common.draw.draw_buffers import normalize_color

        src = np.array([[1, 0, 0, 0.2], [0, 1, 0, 0.8]], dtype=np.float32)
        out = normalize_color(src, 2)
        np.testing.assert_allclose(out, src)

    def test_uint8_promotes_to_float(self):
        from mpynode._common.draw.draw_buffers import normalize_color

        src = np.array([[255, 0, 0]], dtype=np.uint8)
        out = normalize_color(src, 1)
        np.testing.assert_allclose(out[0], [1.0, 0.0, 0.0, 1.0])

    def test_shape_mismatch_raises(self):
        from mpynode._common.draw.draw_buffers import normalize_color

        with self.assertRaises(ValueError):
            normalize_color(np.zeros((3, 3)), 5)


class TestFanTriangulate(unittest.TestCase):
    def test_single_triangle_passthrough(self):
        from mpynode._common.draw.draw_buffers import fan_triangulate

        pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        out = fan_triangulate(pts, [0, 1, 2], [3])
        self.assertEqual(out.shape, (3, 3))

    def test_quad_to_two_triangles(self):
        from mpynode._common.draw.draw_buffers import fan_triangulate

        pts = np.array(
            [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            dtype=np.float32,
        )
        out = fan_triangulate(pts, [0, 1, 2, 3], [4])
        # 4 verts -> 2 triangles = 6 vertex outputs.
        self.assertEqual(out.shape, (6, 3))
        # Both triangles share vertex[0] (fan anchor).
        np.testing.assert_allclose(out[0], pts[0])
        np.testing.assert_allclose(out[3], pts[0])

    def test_ngon_5verts_gives_3_triangles(self):
        from mpynode._common.draw.draw_buffers import fan_triangulate

        pts = np.array(
            [[0, 0, 0], [1, 0, 0], [1.5, 0.5, 0], [1, 1, 0], [0, 1, 0]],
            dtype=np.float32,
        )
        out = fan_triangulate(pts, list(range(5)), [5])
        # 5 verts -> 3 triangles = 9 vertex outputs.
        self.assertEqual(out.shape, (9, 3))

    def test_two_faces_concatenate(self):
        from mpynode._common.draw.draw_buffers import fan_triangulate

        pts = np.array(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 0, 0], [2, 1, 0]],
            dtype=np.float32,
        )
        # Face 0: tri [0, 1, 2]; Face 1: tri [3, 4, 0]
        out = fan_triangulate(pts, [0, 1, 2, 3, 4, 0], [3, 3])
        self.assertEqual(out.shape, (6, 3))

    def test_face_with_2_verts_silently_skipped(self):
        from mpynode._common.draw.draw_buffers import fan_triangulate

        pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        out = fan_triangulate(pts, [0, 1, 0, 1, 2], [2, 3])
        # First face skipped (2 verts), second emits 1 triangle.
        self.assertEqual(out.shape, (3, 3))


class TestExpandFaceColorsToTriangles(unittest.TestCase):
    def test_quad_expands_to_6_colors(self):
        from mpynode._common.draw.draw_buffers import expand_face_colors_to_triangles

        face_colors = np.array([[1, 0, 0, 1]], dtype=np.float32)
        counts = np.array([4], dtype=np.int64)
        out = expand_face_colors_to_triangles(face_colors, counts)
        # quad = 2 tris = 6 vertex colors, all = (1,0,0,1)
        self.assertEqual(out.shape, (6, 4))
        for i in range(6):
            np.testing.assert_allclose(out[i], [1.0, 0.0, 0.0, 1.0])

    def test_mixed_face_sizes(self):
        from mpynode._common.draw.draw_buffers import expand_face_colors_to_triangles

        face_colors = np.array(
            [[1, 0, 0, 1], [0, 1, 0, 1], [0, 0, 1, 1]],
            dtype=np.float32,
        )
        counts = np.array([3, 4, 5], dtype=np.int64)
        # tri=3, quad=6, pentagon=9 -> 18 total vertex colors
        out = expand_face_colors_to_triangles(face_colors, counts)
        self.assertEqual(out.shape, (18, 4))
        # First 3 are red, next 6 green, last 9 blue.
        np.testing.assert_allclose(out[0], [1, 0, 0, 1])
        np.testing.assert_allclose(out[3], [0, 1, 0, 1])
        np.testing.assert_allclose(out[9], [0, 0, 1, 1])


class TestBuildEdgePointPairs(unittest.TestCase):
    def test_triangle_emits_3_edges(self):
        from mpynode._common.draw.draw_buffers import build_edge_point_pairs

        pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
        starts, ends = build_edge_point_pairs(pts, [0, 1, 2], [3])
        self.assertEqual(starts.shape, (3, 3))
        self.assertEqual(ends.shape, (3, 3))
        # Last edge closes back to vert[0].
        np.testing.assert_allclose(ends[2], pts[0])

    def test_quad_emits_4_edges(self):
        from mpynode._common.draw.draw_buffers import build_edge_point_pairs

        pts = np.array(
            [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            dtype=np.float32,
        )
        starts, ends = build_edge_point_pairs(pts, [0, 1, 2, 3], [4])
        self.assertEqual(starts.shape, (4, 3))


# ===========================================================================
# 2b. Per-slot draw-space helpers (local vs screen)
# ===========================================================================


class TestNormalizeSpace(unittest.TestCase):
    def test_default_is_local(self):
        from mpynode._common.draw.draw_buffers import normalize_space

        self.assertEqual(normalize_space(None), "local")

    def test_local_and_screen_pass_through(self):
        from mpynode._common.draw.draw_buffers import normalize_space

        self.assertEqual(normalize_space("local"), "local")
        self.assertEqual(normalize_space("screen"), "screen")

    def test_case_insensitive(self):
        from mpynode._common.draw.draw_buffers import normalize_space

        self.assertEqual(normalize_space("SCREEN"), "screen")
        self.assertEqual(normalize_space(" Screen "), "screen")

    def test_unknown_falls_back_to_local(self):
        from mpynode._common.draw.draw_buffers import normalize_space

        self.assertEqual(normalize_space("world"), "local")
        self.assertEqual(normalize_space(42), "local")


class TestMatrixUniformScale(unittest.TestCase):
    def test_identity_is_one(self):
        from mpynode._common.draw.draw_buffers import matrix_uniform_scale

        ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        self.assertAlmostEqual(matrix_uniform_scale(ident), 1.0, places=6)

    def test_uniform_scale_3(self):
        from mpynode._common.draw.draw_buffers import matrix_uniform_scale

        # basis rows scaled by 3 (row-major, row-vector convention).
        m = [3, 0, 0, 0, 0, 3, 0, 0, 0, 0, 3, 0, 5, 6, 7, 1]
        self.assertAlmostEqual(matrix_uniform_scale(m), 3.0, places=6)

    def test_non_uniform_geometric_mean(self):
        from mpynode._common.draw.draw_buffers import matrix_uniform_scale

        # scales 2, 4, 8 -> geometric mean = (2*4*8)**(1/3) = 4.
        m = [2, 0, 0, 0, 0, 4, 0, 0, 0, 0, 8, 0, 0, 0, 0, 1]
        self.assertAlmostEqual(matrix_uniform_scale(m), 4.0, places=6)


class TestPixelsPerWorldUnit(unittest.TestCase):
    def _ortho_view_proj(self, half_h, vp_h):
        """Build a trivial world->clip matrix for an orthographic view
        where world-Y maps linearly to clip-Y with NDC = y / half_h
        (w == 1). Row-major, row-vector convention (clip = p_row @ M)."""
        sy = 1.0 / half_h
        # M[i*4+j]; row-vector: clip_y = y * M[1*4+1]; clip_w = M[3*4+3]=1
        m = [0.0] * 16
        m[0] = 1.0            # x -> clip x (unused)
        m[5] = sy             # y -> clip y
        m[10] = 1.0           # z -> clip z (unused)
        m[15] = 1.0           # w = 1 (ortho)
        return m

    def test_ortho_pixels_per_unit(self):
        from mpynode._common.draw.draw_buffers import pixels_per_world_unit

        # half_h world units span half the viewport height in NDC (0->1),
        # i.e. vp_h/2 pixels. So 1 world unit = (vp_h/2)/half_h pixels.
        half_h, vp_h = 5.0, 800.0
        m = self._ortho_view_proj(half_h, vp_h)
        ppw = pixels_per_world_unit(
            m, vp_h, anchor_world=(0.0, 0.0, 0.0), up_world=(0.0, 1.0, 0.0)
        )
        self.assertAlmostEqual(ppw, (vp_h / 2.0) / half_h, places=4)

    def test_behind_camera_returns_none(self):
        from mpynode._common.draw.draw_buffers import pixels_per_world_unit

        # Perspective-ish matrix that maps to negative w -> behind camera.
        m = [0.0] * 16
        m[5] = 1.0
        m[11] = -1.0   # w = -z
        m[15] = 0.0
        ppw = pixels_per_world_unit(
            m, 800.0, anchor_world=(0.0, 0.0, 1.0), up_world=(0.0, 1.0, 0.0)
        )
        self.assertIsNone(ppw)


class TestLocalTextPixelSize(unittest.TestCase):
    def test_scales_with_object_pixels(self):
        from mpynode._common.draw.draw_buffers import local_text_pixel_size

        # size 0.5 obj-units at 40 px/obj-unit = 20 px.
        self.assertEqual(local_text_pixel_size(0.5, 40.0), 20)

    def test_clamps_min_and_max(self):
        from mpynode._common.draw.draw_buffers import local_text_pixel_size

        self.assertEqual(local_text_pixel_size(0.001, 40.0, min_px=6), 6)
        self.assertEqual(local_text_pixel_size(100.0, 40.0, max_px=200), 200)

    def test_zoom_out_shrinks_font(self):
        from mpynode._common.draw.draw_buffers import local_text_pixel_size

        near = local_text_pixel_size(1.0, 60.0)
        far = local_text_pixel_size(1.0, 15.0)
        self.assertGreater(near, far)


class TestProjectObjectPointsToPixels(unittest.TestCase):
    def _ortho_full(self, half_w, half_h, vp_w, vp_h):
        """world->clip ortho: NDC_x = x/half_w, NDC_y = y/half_h, w=1."""
        m = [0.0] * 16
        m[0] = 1.0 / half_w
        m[5] = 1.0 / half_h
        m[10] = 1.0
        m[15] = 1.0
        return m

    def test_origin_maps_to_viewport_center(self):
        from mpynode._common.draw.draw_buffers import project_object_points_to_pixels

        ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        vp = self._ortho_full(5.0, 5.0, 800.0, 600.0)
        px, valid = project_object_points_to_pixels(
            [[0.0, 0.0, 0.0]], ident, vp, 800.0, 600.0
        )
        self.assertTrue(bool(valid[0]))
        # NDC (0,0) -> pixel center (400, 300).
        self.assertAlmostEqual(px[0, 0], 400.0, places=3)
        self.assertAlmostEqual(px[0, 1], 300.0, places=3)

    def test_object_matrix_applied_before_projection(self):
        from mpynode._common.draw.draw_buffers import project_object_points_to_pixels

        # object matrix translates +half_w in X -> lands at right edge.
        obj = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 5.0, 0.0, 0.0, 1]
        vp = self._ortho_full(5.0, 5.0, 800.0, 600.0)
        px, valid = project_object_points_to_pixels(
            [[0.0, 0.0, 0.0]], obj, vp, 800.0, 600.0
        )
        self.assertTrue(bool(valid[0]))
        # NDC_x = 5/5 = 1 -> right edge pixel = 800.
        self.assertAlmostEqual(px[0, 0], 800.0, places=3)
        self.assertAlmostEqual(px[0, 1], 300.0, places=3)


# ===========================================================================
# 3. Round-trip through a real locator
# ===========================================================================


class TestLocatorRoundTrip(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    _IMPORT = ("from mpynode._common.draw.draw_types import (\n"
               "    DrawBox, DrawCurve, DrawLines, DrawMesh, DrawPoints,\n"
               "    DrawSphere, DrawText)\n")

    def _cmds(self, name, body):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name=name)
        loc.set_compute_expression("import numpy as np\n" + self._IMPORT + body)
        return loc.evaluate_draw_commands()["commands"]

    def test_lines_buffer_round_trip(self):
        cmds = self._cmds(
            "rtLines",
            "self.draw = DrawLines(\n"
            "    np.array([[0,0,0],[1,1,1]], dtype=np.float32),\n"
            "    np.array([[1,0,0],[0,1,0]], dtype=np.float32),\n"
            "    color=np.array([[1,0,0],[0,1,0]], dtype=np.float32))\n")
        self.assertEqual([c["slot"] for c in cmds], ["lines"])
        self.assertEqual(cmds[0]["buffer"]["starts"].shape, (2, 3))
        self.assertEqual(cmds[0]["buffer"]["ends"].shape, (2, 3))

    def test_polygons_obj_style_round_trip(self):
        cmds = self._cmds(
            "rtPoly",
            "self.draw = DrawMesh(\n"
            "    np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], np.float32),\n"
            "    np.array([4], np.int32), np.array([0,1,2,3], np.int32),\n"
            "    color=(1, 0, 0))\n")
        self.assertEqual([c["slot"] for c in cmds], ["polygons"])
        p = cmds[0]["buffer"]
        self.assertEqual(p["points"].shape, (4, 3))
        self.assertEqual(p["counts"].tolist(), [4])

    def test_shapes_buffer_round_trip(self):
        """Two different primitives are two commands -- they draw in the order
        written rather than being merged into one shapes buffer."""
        cmds = self._cmds(
            "rtShapes",
            "self.draw = (DrawSphere(center=(0, 0, 0), radius=0.5,\n"
            "                        color=(1, 0, 0))\n"
            "             + DrawBox(center=(2, 0, 0), radius=1.0,\n"
            "                       color=(0, 1, 0)))\n")
        self.assertEqual([c["buffer"]["kinds"][0] for c in cmds],
                         ["sphere", "box"])
        self.assertEqual(cmds[0]["buffer"]["centers"].shape, (1, 3))

    def test_text_buffer_round_trip(self):
        cmds = self._cmds(
            "rtText",
            "self.draw = DrawText(['A', 'B'],\n"
            "                     np.array([[0,0,0],[1,0,0]], np.float32))\n")
        self.assertEqual(cmds[0]["buffer"]["strings"], ["A", "B"])

    def test_points_buffer_round_trip(self):
        cmds = self._cmds(
            "rtPoints",
            "self.draw = DrawPoints(\n"
            "    np.array([[0,0,0],[1,1,1],[2,2,2]], np.float32),\n"
            "    color=(1, 1, 0), size=6.0)\n")
        b = cmds[0]["buffer"]
        self.assertEqual(b["positions"].shape, (3, 3))
        self.assertEqual(float(b["sizes"][0]), 6.0)

    def test_only_what_was_drawn_is_emitted(self):
        """No empty per-type slots to skip: a drawing of one line is one
        command, full stop."""
        cmds = self._cmds(
            "rtPartial",
            "self.draw = DrawLines(np.zeros((1, 3)), np.zeros((1, 3)))\n")
        self.assertEqual([c["slot"] for c in cmds], ["lines"])

    def test_space_survives_round_trip_per_item(self):
        """``space`` is per ITEM, so a screen-space line and a local label
        coexist without either being reinterpreted."""
        cmds = self._cmds(
            "rtSpace",
            "self.draw = (DrawLines(np.zeros((1, 3)), np.ones((1, 3)),\n"
            "                       screen_space=True)\n"
            "             + DrawText('x', size=0.5))\n")
        self.assertEqual(cmds[0]["buffer"]["space"], "screen")
        self.assertEqual(cmds[1]["buffer"]["space"], "local")


# ===========================================================================
# 4. Recipe shape
# ===========================================================================


class TestLocatorRecipe(unittest.TestCase):
    def test_recipe_has_one_synthetic_draw_output(self):
        from mpynode._common.util.recipes import get_recipe

        recipe = get_recipe("mPyLocator")
        self.assertEqual({e.name for e in recipe.outputs}, {"draw"})

    def test_the_draw_output_is_synthetic(self):
        from mpynode._common.util.recipes import get_recipe

        recipe = get_recipe("mPyLocator")
        for entry in recipe.outputs:
            self.assertEqual(
                entry.target_plug,
                "",
                f"{entry.name} should be synthetic (target_plug='')",
            )

    def test_the_per_type_buffer_outputs_are_gone(self):
        """One transport. Keeping the five dict slots beside ``self.draw`` is
        what let the interpreted and compiled renderers disagree on order."""
        from mpynode._common.util.recipes import get_recipe

        recipe = get_recipe("mPyLocator")
        names = {e.name for e in recipe.outputs}
        self.assertNotIn("draw_items", names)
        for slot in ("lines", "points", "polygons", "shapes", "text"):
            self.assertNotIn(slot, names)


# ===========================================================================
# 5. Save event broadcasts to the Log tab
# ===========================================================================


class TestSaveLogsToBus(unittest.TestCase):
    def test_save_tab_emits_log_bus_event(self):
        """F5 / Save button should produce a visible log entry so the
        user gets feedback that the action did something. Source-pin
        the log_bus call inside NDScriptTabWidget._saveTab."""
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget._saveTab)
        # A lazy import, like the other bridge log_bus call sites.
        self.assertIn("from mpynode._common.util.log_bus import log", src)
        self.assertIn("Saved expression on", src)
        # info, not error, so it does not compete with expression errors.
        self.assertIn('level="info"', src)


# ===================== from test_phase29_2.py =====================
import unittest

import numpy as np

from._setup import standalone_init


def _setUpModule__phase29_2():
    standalone_init()


# ===========================================================================
# 1. INTERNAL_VARS schema additions
# ===========================================================================


class TestEvaluateDrawItemsSignature(unittest.TestCase):
    def test_signature_accepts_3_state_kwargs(self):
        import inspect

        from mpynode._api2.mpy_locator import MPyLocator

        sig = inspect.signature(MPyLocator.evaluateDrawItems)
        for kwarg in ("selected", "is_lead", "selection_color"):
            self.assertIn(kwarg, sig.parameters)
        # Defaults keep back-compat with callers passing only time_value.
        self.assertEqual(sig.parameters["selected"].default, False)
        self.assertEqual(sig.parameters["is_lead"].default, False)
        self.assertEqual(
            sig.parameters["selection_color"].default,
            (1.0, 1.0, 1.0, 1.0),
        )

    def test_signature_has_hovered_kwarg(self):
        import inspect

        from mpynode._api2.mpy_locator import MPyLocator

        sig = inspect.signature(MPyLocator.evaluateDrawItems)
        self.assertIn("hovered", sig.parameters)
        self.assertEqual(sig.parameters["hovered"].default, False)


# ===========================================================================
# 3. Return dict includes auto_highlight
# ===========================================================================


class TestBridgeReturnsAutoHighlight(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def test_empty_expression_returns_auto_highlight_true(self):
        """Casual gizmo (no expression code) defaults to True so the
        framework will auto-tint when selected."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="defaultAuto")
        out = loc.evaluate_draw_commands()
        self.assertIn("auto_highlight", out)
        self.assertTrue(out["auto_highlight"])

    def test_expression_can_opt_out(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="optOutAuto")
        loc.set_compute_expression("self.auto_highlight = False\n")
        bufs = loc.evaluate_draw_commands()
        self.assertFalse(bufs["auto_highlight"])

    def test_expression_explicit_true_still_true(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="explicitTrue")
        loc.set_compute_expression("self.auto_highlight = True\n")
        bufs = loc.evaluate_draw_commands()
        self.assertTrue(bufs["auto_highlight"])


# ===========================================================================
# 4. Expression can read selection state
# ===========================================================================


class TestExpressionReadsState(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    _SELECTED_EXPR = (
        "import numpy as np\n"
        "from mpynode._common.draw.draw_types import DrawPoints\n"
        "n = 1 if self.selected else 2\n"
        "self.draw = DrawPoints(np.zeros((n, 3)), color=(1, 1, 1))\n"
    )

    def test_expression_sees_selected_default_false(self):
        """Wrapper.evaluate_draw_commands does not pass selection state,
        so the bridge defaults all flags to False/identity."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="stateRead")
        loc.set_compute_expression(self._SELECTED_EXPR)
        cmds = loc.evaluate_draw_commands()["commands"]
        # Default selected=False -> n=2.
        self.assertEqual(cmds[0]["buffer"]["positions"].shape, (2, 3))

    def test_expression_sees_selected_true_when_passed(self):
        """Call evaluateDrawItems directly via the MPx node with the
        selected kwarg, verify the expression branches accordingly."""
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="stateTrue")
        loc.set_compute_expression(self._SELECTED_EXPR)
        sel = om.MSelectionList()
        sel.add(loc.get_name())
        node_obj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(node_obj)
        mpx = fn.userNode()
        out = mpx.evaluateDrawItems(time_value=0.0, selected=True)
        # selected=True -> n=1.
        self.assertEqual(out["commands"][0]["buffer"]["positions"].shape,
                         (1, 3))

    def test_expression_sees_selection_color(self):
        """Pass a known selection_color tuple, verify the expression
        receives the same tuple."""
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="colorRead")
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawLines\n"
            "# Forward the selection_color into the drawing so we can\n"
            "# introspect it after evaluate.\n"
            "c = self.selection_color\n"
            "self.draw = DrawLines((0, 0, 0), (1, 0, 0), color=c[:3])\n"
        )
        sel = om.MSelectionList()
        sel.add(loc.get_name())
        node_obj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(node_obj)
        mpx = fn.userNode()
        out = mpx.evaluateDrawItems(
            time_value=0.0,
            selected=True,
            selection_color=(0.5, 0.8, 0.2, 1.0),
        )
        np.testing.assert_allclose(
            out["commands"][0]["buffer"]["colors"][0][:3],
            [0.5, 0.8, 0.2],
            atol=1e-5,
        )


# ===========================================================================
# 5. draw_override pipes selection state correctly
# ===========================================================================


class TestDrawOverrideWiresUpState(unittest.TestCase):
    def test_prepare_for_draw_queries_display_status(self):
        import inspect

        from mpynode._api2.mpy_locator import MPyLocatorDrawOverride

        src = inspect.getsource(MPyLocatorDrawOverride.prepareForDraw)
        self.assertIn("MGeometryUtilities.displayStatus", src)
        self.assertIn("MGeometryUtilities.wireframeColor", src)
        # Active selection states are still queried.
        self.assertIn("kLead", src)
        self.assertIn("kActive", src)
        # displayStatus has no hover value, so hover comes from the
        # cursor-ray hover_tracker.
        self.assertIn("hover_tracker", src)
        self.assertIn("hover_tracker.is_hovered", src)

    def test_prepare_for_draw_passes_state_to_evaluateDrawItems(self):
        import inspect

        from mpynode._api2.mpy_locator import MPyLocatorDrawOverride

        src = inspect.getsource(MPyLocatorDrawOverride.prepareForDraw)
        # 4 state kwargs forwarded (selection + hover).
        self.assertIn("selected=is_selected", src)
        self.assertIn("is_lead=is_lead", src)
        self.assertIn("selection_color=sel_color_tuple", src)
        self.assertIn("hovered=is_hovered", src)

    def test_add_ui_drawables_only_overrides_when_selected_and_auto(self):
        import inspect

        from mpynode._api2.mpy_locator import MPyLocatorDrawOverride

        src = inspect.getsource(MPyLocatorDrawOverride.addUIDrawables)
        # The override condition is the AND of is_selected + auto_highlight.
        self.assertIn(
            "data.is_selected and data.auto_highlight",
            src,
        )
        # And the override color comes from data.sel_color.
        self.assertIn("data.sel_color", src)

    def test_user_data_class_has_29_2_fields(self):
        from mpynode._api2.mpy_locator import MPyLocatorDrawData

        # Constructing populates the new fields.
        d = MPyLocatorDrawData()
        self.assertEqual(d.commands, [])
        self.assertFalse(d.is_selected)
        self.assertTrue(d.auto_highlight)
        self.assertIsNone(d.sel_color)

    def test_add_ui_drawables_replays_the_commands_in_order(self):
        """A dispatch LOOP, not five typed branches: reordering here would
        silently override what the author wrote."""
        import inspect

        from mpynode._api2.mpy_locator import MPyLocatorDrawOverride

        src = inspect.getsource(MPyLocatorDrawOverride.addUIDrawables)
        self.assertIn("for cmd in commands:", src)


# ===================== from test_phase30.py =====================
import unittest

from._setup import standalone_init


def _setUpModule__phase30():
    standalone_init()


# ===========================================================================
# 1. Helper module shape
# ===========================================================================


class TestDrawRefreshModule(unittest.TestCase):
    def test_module_exports_public_api(self):
        from mpynode._common.draw import draw_refresh

        for name in ("enable", "disable", "is_enabled", "active_count"):
            self.assertTrue(
                hasattr(draw_refresh, name),
                f"draw_refresh missing {name!r}",
            )

    def test_refresh_interval_is_30fps(self):
        from mpynode._common.draw import draw_refresh

        # 30 fps == 1/30 sec per tick.
        self.assertAlmostEqual(
            draw_refresh._REFRESH_INTERVAL_SEC,
            1.0 / 30.0,
            places=5,
        )

    def test_module_is_qt_free(self):
        import inspect

        from mpynode._common.draw import draw_refresh

        src = inspect.getsource(draw_refresh)
        self.assertNotIn("PySide", src)
        self.assertNotIn("qt_wrapper", src)


class TestTimerTickFlushOrder(unittest.TestCase):
    """The per-tick order matters for interactive latency.

    ``_timer_tick`` both (a) raises the VP2 draw-dirty flag via
    ``setGeometryDrawDirty`` -- which schedules the redraw that will call
    prepareForDraw -- and (b) flushes the parent aim's stale worldMatrix
    cache. If the draw-dirty flag is raised BEFORE the flush, the redraw
    triggered by this tick samples the still-stale world matrix and the
    freshly-flushed value is only picked up on the NEXT tick's redraw -- a
    systematic one-tick (~33ms) latency penalty on the DNET link gizmos.
    Flushing FIRST lets the redraw this tick triggers pick up the fresh
    matrix immediately."""

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        from mpynode._common.draw import draw_refresh

        draw_refresh._reset_all_for_tests()

    def test_timer_tick_flushes_parent_before_marking_draw_dirty(self):
        import maya.api.OpenMaya as om
        from mpynode._common.draw import draw_refresh
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="tickOrderShape")
        sel = om.MSelectionList()
        sel.add(loc.get_name())
        node_obj = sel.getDependNode(0)
        handle = om.MObjectHandle(node_obj)
        # Any valid handle: the flush itself is stubbed to just record order.
        parent_handle = om.MObjectHandle(node_obj)

        calls = []

        class _FakeRenderer:
            @staticmethod
            def setGeometryDrawDirty(_obj):
                calls.append("draw_dirty")

        class _FakeOmr:
            MRenderer = _FakeRenderer

        def _fake_flush(_ph):
            calls.append("flush")
            return True

        real_omr = draw_refresh.omr
        real_flush = draw_refresh._flush_parent_transform
        draw_refresh.omr = _FakeOmr
        draw_refresh._flush_parent_transform = _fake_flush
        try:
            draw_refresh._timer_tick(handle, parent_handle)
        finally:
            draw_refresh.omr = real_omr
            draw_refresh._flush_parent_transform = real_flush

        self.assertEqual(
            calls,
            ["flush", "draw_dirty"],
            "the parent worldMatrix flush must precede setGeometryDrawDirty so "
            "the redraw THIS tick triggers samples the fresh matrix, not the "
            "stale one (which would add a ~33ms one-tick latency)",
        )


# ===========================================================================
# 2. enable/disable round-trip on a real locator
# ===========================================================================


class TestEnableDisableRoundTrip(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        # Tear down any leaked timers from previous tests.
        from mpynode._common.draw import draw_refresh

        draw_refresh._reset_all_for_tests()

    def _create_locator_node(self):
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="refreshTestShape")
        sel = om.MSelectionList()
        sel.add(loc.get_name())
        return sel.getDependNode(0)

    def test_enable_then_is_enabled_then_disable(self):
        from mpynode._common.draw import draw_refresh

        node_obj = self._create_locator_node()
        self.assertFalse(draw_refresh.is_enabled(node_obj))
        draw_refresh.enable(node_obj)
        self.assertTrue(draw_refresh.is_enabled(node_obj))
        self.assertEqual(draw_refresh.active_count(), 1)
        draw_refresh.disable(node_obj)
        self.assertFalse(draw_refresh.is_enabled(node_obj))
        self.assertEqual(draw_refresh.active_count(), 0)

    def test_enable_is_idempotent(self):
        from mpynode._common.draw import draw_refresh

        node_obj = self._create_locator_node()
        draw_refresh.enable(node_obj)
        draw_refresh.enable(node_obj)  # second call should be a no-op
        self.assertEqual(draw_refresh.active_count(), 1)
        draw_refresh.disable(node_obj)

    def test_disable_unknown_node_is_safe(self):
        from mpynode._common.draw import draw_refresh

        node_obj = self._create_locator_node()
        # Never enabled -- disable should be a no-op, not raise.
        draw_refresh.disable(node_obj)
        self.assertEqual(draw_refresh.active_count(), 0)


# ===========================================================================
# 3-4. Schema + bridge surface
# ===========================================================================


class TestDrawOverrideWiresTimer(unittest.TestCase):
    def test_prepare_for_draw_calls_enable_when_auto_refresh_true(self):
        import inspect

        from mpynode._api2.mpy_locator import MPyLocatorDrawOverride

        src = inspect.getsource(MPyLocatorDrawOverride.prepareForDraw)
        self.assertIn('auto_refresh = bool(harvest.get("auto_refresh"', src)
        self.assertIn("_dr.enable(node_obj)", src)
        self.assertIn("_dr.disable(node_obj)", src)


# ===========================================================================
# 6. Crash safety: scene-event teardown
# ===========================================================================


class TestCrashSafety(unittest.TestCase):
    """The user-reported crash: timer keeps firing on dangling MObject
    after file->new. Our V3 strategy registers a kBeforeNew callback
    that tears down ALL timers BEFORE the scene wipe invalidates
    MObjects. This test verifies that mechanism end-to-end."""

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)
        from mpynode._common.draw import draw_refresh

        draw_refresh._reset_all_for_tests()

    def test_file_new_tears_down_all_timers(self):
        import maya.api.OpenMaya as om
        import maya.cmds as mc
        from mpynode._common.draw import draw_refresh
        from mpynode.wrappers.mpy_locator import MPyLocator

        # Create 3 locators, enable all of them.
        node_objs = []
        for i in range(3):
            loc = MPyLocator.create(name=f"crashTest{i}")
            sel = om.MSelectionList()
            sel.add(loc.get_name())
            node_objs.append(sel.getDependNode(0))
            draw_refresh.enable(node_objs[-1])
        self.assertEqual(draw_refresh.active_count(), 3)

        # File->new fires kBeforeNew, which wipes ALL timer state.
        mc.file(new=True, force=True)
        self.assertEqual(
            draw_refresh.active_count(),
            0,
            "scene event must reap all timers before file-new invalidates the MObjects",
        )

    def test_scene_callbacks_registered_once(self):
        """The helper should only register kBeforeNew etc. once even
        if enable() is called many times across many nodes."""
        import maya.api.OpenMaya as om
        from mpynode._common.draw import draw_refresh
        from mpynode.wrappers.mpy_locator import MPyLocator

        for i in range(5):
            loc = MPyLocator.create(name=f"sceneCbTest{i}")
            sel = om.MSelectionList()
            sel.add(loc.get_name())
            node_obj = sel.getDependNode(0)
            draw_refresh.enable(node_obj)

        # 3 scene events (kBeforeNew, kBeforeOpen, kMayaExiting), all from the
        # first enable() call. No extras.
        self.assertEqual(len(draw_refresh._SCENE_CB_IDS), 3)

    def test_module_has_object_handle_isvalid_guard(self):
        """Defense layer 1: even if scene+node callbacks failed, the
        timer callback itself must check MObjectHandle.isValid()."""
        import inspect

        from mpynode._common.draw import draw_refresh

        src = inspect.getsource(draw_refresh._timer_tick)
        self.assertIn("handle.isValid()", src)


# ===================== from test_phaseR_0_locator_ab.py =====================
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseR_0_locator_ab():
    standalone_init()


_DRAW_SRC = (
    "import numpy as np\n"
    "from mpynode._common.draw.draw_types import DrawLines\n"
    "self.draw = DrawLines(np.zeros((1, 3)),\n"
    "                      np.array([[1, 0, 0]], dtype=float),\n"
    "                      color=(1, 0, 0))\n"
)


class TestLocatorDraw(unittest.TestCase):
    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_expression_drives_draw(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="drawA")
        loc.set_compute_expression(_DRAW_SRC)
        cmds = loc.evaluate_draw_commands(0.0)["commands"]
        self.assertEqual([c["slot"] for c in cmds], ["lines"])

    def test_user_input_feeds_draw(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="drawB")
        loc.add_input_attr("scale", "float")
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawLines\n"
            "self.draw = DrawLines(\n"
            "    np.zeros((1, 3)),\n"
            "    np.array([[self.scale, 0, 0]], dtype=float),\n"
            "    color=(1, 0, 0))\n"
        )
        mc.setAttr(loc.get_name() + ".scale", 4.0)
        cmds = loc.evaluate_draw_commands(0.0)["commands"]
        self.assertAlmostEqual(float(cmds[0]["buffer"]["ends"][0][0]), 4.0)


class TestLocatorOutputLimitation(unittest.TestCase):
    """Pin the known limitation: DG user outputs don't compute on a locator."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_user_output_does_not_compute(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="limA")
        loc.add_input_attr("foo", "float")
        loc.add_output_attr("bar", "float")
        loc.set_compute_expression("self.bar = self.foo * 2.0")
        mc.setAttr(loc.get_name() + ".foo", 5.0)
        # MPxLocatorNode never calls compute() for the dynamic output, so
        # bar stays at its default rather than computing to 10.0.
        self.assertEqual(mc.getAttr(loc.get_name() + ".bar"), 0.0)


class TestLocatorInputDirtyRedraw(unittest.TestCase):
    """The directive: when an INPUT plug is dirtied (setAttr OR an incoming
    connection updating its value), the node MUST re-evaluate -- no exception,
    any node type. A draw-only locator has no DG output to dirty, so it honours
    this by forcing a viewport redraw (re-run of the draw expression) from
    ``setDependentsDirty`` -- see ``MPyLocator._is_draw_dirty_trigger`` /
    ``setDependentsDirty``. This replaces the opt-in 30fps ``auto_refresh`` poll
    as the correctness mechanism for input-driven gizmos (e.g. the DNET knot,
    whose evaluated position arrives as the ``positionMatrix`` input)."""

    def setUp(self):
        import maya.cmds as mc

        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_is_draw_dirty_trigger_gates_inputs(self):
        # Red-green guard: user inputs + the internal Compute plug are triggers,
        # an unrelated built-in (message) is not. RED before the fix, where the
        # method did not exist -> AttributeError.
        import maya.api.OpenMaya as om
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="ddGate", skip_selection=True)
        loc.add_input_attr("positionMatrix", "matrix")
        loc.add_input_attr("radius", "float")

        sel = om.MSelectionList()
        sel.add(loc.get_name())
        mobj = sel.getDependNode(0)
        fn = om.MFnDependencyNode(mobj)
        mpx = fn.userNode()

        self.assertTrue(mpx._is_draw_dirty_trigger(fn.findPlug("positionMatrix", True)),
                        "a user matrix INPUT must be a redraw trigger")
        self.assertTrue(mpx._is_draw_dirty_trigger(fn.findPlug("radius", True)),
                        "a user float INPUT must be a redraw trigger")
        self.assertTrue(mpx._is_draw_dirty_trigger(fn.findPlug("_computeSource", True)),
                        "the Compute-source plug must be a redraw trigger")
        self.assertFalse(mpx._is_draw_dirty_trigger(fn.findPlug("message", True)),
                         "an unrelated built-in plug must NOT be a redraw trigger")

    def test_input_dirty_path_is_crash_safe_and_reads_fresh(self):
        # Dirtying a connected input via the source's TRS must (1) NOT crash --
        # the real setDependentsDirty -> setGeometryDrawDirty path runs here,
        # and the old cmds.dgdirty callback SIGSEGV'd under EM in exactly this
        # situation -- and (2) leave the draw expression reading the FRESH
        # matrix. The VP2 repaint is not observable headless.
        import maya.api.OpenMaya as om
        import maya.cmds as mc
        from mpynode.wrappers.mpy_locator import MPyLocator

        src = mc.createNode("transform", name="ddSrc")
        loc = MPyLocator.create(name="ddRedraw", skip_selection=True)
        loc.add_input_attr("positionMatrix", "matrix")
        loc.set_init_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawSphere\n")
        loc.set_compute_expression(
            "c = self.positionMatrix.asNumpy()[3, :3]\n"
            "self.draw = DrawSphere(center=c, radius=1.0,\n"
            "                       color=(1, 1, 1, 1), filled=True)\n"
        )
        mc.connectAttr(src + ".matrix", loc.get_name() + ".positionMatrix",
                       force=True)

        mc.setAttr(src + ".translateX", 7.0)
        # Force dirty propagation to the locator input -> real setDependentsDirty.
        mc.dgdirty(loc.get_name() + ".positionMatrix")

        db = loc.evaluate_draw_commands(0.0)
        buf = db["commands"][0]["buffer"]
        center = np.asarray(buf["centers"], dtype=float).reshape(-1, 3)[0]
        self.assertAlmostEqual(float(center[0]), 7.0, places=5,
                               msg="draw expression did not read the fresh input")
        # Knot-style contract: an input-driven gizmo needs no auto_refresh poll,
        # the redraw comes from setDependentsDirty.
        self.assertFalse(bool(db.get("auto_refresh")),
                         "input-driven gizmo should not rely on the auto_refresh poll")


# ===================== from test_phase05.py =====================
import os
import unittest

import maya.cmds as mc

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase05():
    standalone_init()


class TestMPyLocatorBasics(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_node_type_registered(self):
        self.assertIn("mPyLocator", mc.allNodeTypes() or [])

    def test_create_returns_wrapper_with_transform(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="myGizmoShape")
        self.assertTrue(mc.objExists("myGizmoShape"))
        self.assertEqual(mc.nodeType("myGizmoShape"), "mPyLocator")
        # The locator must have a parent transform.
        parent = loc.get_transform()
        self.assertTrue(mc.objExists(parent))
        self.assertEqual(mc.nodeType(parent), "transform")

    def test_locator_inherits_from_locator(self):
        chain = mc.nodeType("mPyLocator", inherited=True, isTypeName=True)
        self.assertIn("locator", chain)
        self.assertIn("mPyLocator", chain)

    def test_set_get_expression(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="exprGizmo")
        loc.set_compute_expression("self.draw = DrawPoints([[0, 0, 0]])")
        self.assertIn("self.draw", loc.get_compute_expression())


class TestMPyLocatorDrawBuffers(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_evaluate_draw_commands_empty_default(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="emptyGizmo")
        # Default expression "None" -> an empty command list plus the default
        # auto_highlight (True), auto_refresh (False), precise_hover (False).
        out = loc.evaluate_draw_commands()
        self.assertEqual(
            set(out.keys()),
            {"commands", "auto_highlight", "auto_refresh", "precise_hover"},
        )
        self.assertEqual(out["commands"], [])
        self.assertTrue(out["auto_highlight"])
        self.assertFalse(out["auto_refresh"])
        self.assertFalse(out["precise_hover"])

    def test_evaluate_draw_commands_simple_line(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="lineGizmo")
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawLines\n"
            "self.draw = DrawLines(np.array([[0,0,0]], np.float32),\n"
            "                      np.array([[1,0,0]], np.float32),\n"
            "                      color=(1, 0, 0))\n"
        )
        cmds = loc.evaluate_draw_commands()["commands"]
        self.assertEqual([c["slot"] for c in cmds], ["lines"])
        self.assertEqual(cmds[0]["buffer"]["starts"].shape, (1, 3))
        self.assertEqual(cmds[0]["buffer"]["ends"].shape, (1, 3))

    def test_evaluate_draw_commands_with_time(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="timedGizmo")
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawPoints\n"
            "self.draw = DrawPoints(\n"
            "    np.array([[self.time, 0, 0]], np.float32), color=(1, 1, 1))\n"
        )
        cmds = loc.evaluate_draw_commands(time_value=5.0)["commands"]
        self.assertAlmostEqual(
            float(cmds[0]["buffer"]["positions"][0, 0]), 5.0)


class TestMPyLocatorRecipe(unittest.TestCase):
    def test_recipe_registered(self):
        from mpynode._common.util.recipes import get_recipe

        recipe = get_recipe("mPyLocator")
        self.assertIsNotNone(recipe)
        # Real input plugs (localPosition, localScale)
        names_in = {e.name for e in recipe.inputs}
        self.assertIn("localPosition", names_in)
        self.assertIn("localScale", names_in)
        # ONE synthetic output -- the ordered drawing.
        names_out = {e.name for e in recipe.outputs}
        self.assertEqual(names_out, {"draw"})
        entry = next(e for e in recipe.outputs if e.name == "draw")
        self.assertEqual(entry.target_plug, "")   # synthetic (no real plug)


# ===================== from test_cull_backfaces.py =====================
import unittest

import numpy as np

from mpynode._common.draw.draw_buffers import cull_backfaces_by_view


def _unit_cube():
    """Return (points, indices, counts) for a unit cube centered at
    the origin with CCW-outward winding."""
    points = np.array(
        [
            [-1.0, -1.0, -1.0],   # 0
            [ 1.0, -1.0, -1.0],   # 1
            [ 1.0,  1.0, -1.0],   # 2
            [-1.0,  1.0, -1.0],   # 3
            [-1.0, -1.0,  1.0],   # 4
            [ 1.0, -1.0,  1.0],   # 5
            [ 1.0,  1.0,  1.0],   # 6
            [-1.0,  1.0,  1.0],   # 7
        ],
        dtype=np.float64,
    )
    # CCW-outward face winding (when looking from outside the cube).
    indices = np.array(
        [
            0, 3, 2, 1,   # -Z face
            4, 5, 6, 7,   # +Z face
            0, 1, 5, 4,   # -Y face
            2, 3, 7, 6,   # +Y face
            0, 4, 7, 3,   # -X face
            1, 2, 6, 5,   # +X face
        ],
        dtype=np.int64,
    )
    counts = np.array([4, 4, 4, 4, 4, 4], dtype=np.int64)
    return points, indices, counts


class TestCullBackfacesByView(unittest.TestCase):
    """Verify that a unit-cube\'s back faces are dropped relative to
    the camera position. The cube has 6 faces; from any axis-aligned
    viewing direction exactly 1 face is fully front-facing, 1 is
    fully back-facing, and the remaining 4 lie edge-on (their
    centroids are coplanar with the camera). The dot-product test
    classifies edge-on faces as back-facing (dot == 0 -> rejected),
    so the expected keep count is 1 for an axis-aligned far camera
    and 3 for a corner camera.
    """

    def test_camera_along_plus_z_keeps_only_plus_z_face(self):
        points, indices, counts = _unit_cube()
        # Camera way out on +Z -> only the +Z face is front-facing.
        view_pos = (0.0, 0.0, 100.0)
        new_idx, new_cnt = cull_backfaces_by_view(
            points, indices, counts, view_pos,
        )
        self.assertEqual(
            new_cnt.shape[0], 1,
            f"expected 1 front face from +Z, got {new_cnt.shape[0]}",
        )
        # The +Z face is indices [4, 5, 6, 7] -- all z=+1.
        kept = list(new_idx)
        self.assertEqual(sorted(kept), [4, 5, 6, 7])

    def test_camera_along_minus_x_keeps_only_minus_x_face(self):
        points, indices, counts = _unit_cube()
        view_pos = (-100.0, 0.0, 0.0)
        new_idx, new_cnt = cull_backfaces_by_view(
            points, indices, counts, view_pos,
        )
        self.assertEqual(new_cnt.shape[0], 1)
        # -X face: indices [0, 4, 7, 3] -- all x=-1.
        kept = list(new_idx)
        self.assertEqual(sorted(kept), [0, 3, 4, 7])

    def test_camera_at_corner_keeps_three_front_faces(self):
        """Camera at (+R, +R, +R) sees +X / +Y / +Z faces."""
        points, indices, counts = _unit_cube()
        view_pos = (10.0, 10.0, 10.0)
        new_idx, new_cnt = cull_backfaces_by_view(
            points, indices, counts, view_pos,
        )
        self.assertEqual(new_cnt.shape[0], 3)
        # the three kept faces must be the +X / +Y / +Z ones.
        kept_face_verts = []
        cursor = 0
        for c in new_cnt:
            kept_face_verts.append(set(new_idx[cursor:cursor + c].tolist()))
            cursor += int(c)
        # +Z face = {4,5,6,7}; +Y face = {2,3,6,7}; +X face = {1,2,5,6}.
        expected_sets = [
            frozenset([4, 5, 6, 7]),  # +Z
            frozenset([2, 3, 6, 7]),  # +Y
            frozenset([1, 2, 5, 6]),  # +X
        ]
        kept_sets = sorted(frozenset(s) for s in kept_face_verts)
        self.assertEqual(kept_sets, sorted(expected_sets))

    def test_camera_at_corner_drops_three_back_faces(self):
        """Mirror of the above: the -X / -Y / -Z faces must all be
        culled when the camera is at the +++ corner."""
        points, indices, counts = _unit_cube()
        view_pos = (10.0, 10.0, 10.0)
        new_idx, new_cnt = cull_backfaces_by_view(
            points, indices, counts, view_pos,
        )
        # Total kept verts: 3 faces * 4 verts.
        self.assertEqual(new_idx.shape[0], 12)
        # Most verts are shared and survive, but vertex 0 sits only on the
        # back faces (-X / -Y / -Z), so it must not be kept.
        self.assertNotIn(0, new_idx.tolist())

    def test_fully_culled_returns_empty_arrays(self):
        """A camera placed exactly at the centroid of a single
        triangle sees nothing (every face\'s view vector is
        perpendicular to its normal -> classified as back)."""
        # A single triangle on z=0 with CCW winding viewed from +Z.
        points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
        indices = np.array([0, 1, 2], dtype=np.int64)
        counts = np.array([3], dtype=np.int64)
        # Camera below the plane -> the +Z-winding triangle is
        # back-facing.
        view_pos = (0.0, 0.0, -5.0)
        new_idx, new_cnt = cull_backfaces_by_view(
            points, indices, counts, view_pos,
        )
        self.assertEqual(new_cnt.shape[0], 0)
        self.assertEqual(new_idx.shape[0], 0)

    def test_empty_input(self):
        """Zero faces in -> zero faces out, no exception."""
        new_idx, new_cnt = cull_backfaces_by_view(
            np.zeros((0, 3)),
            np.zeros((0,), dtype=np.int64),
            np.zeros((0,), dtype=np.int64),
            (0.0, 0.0, 1.0),
        )
        self.assertEqual(new_idx.shape[0], 0)
        self.assertEqual(new_cnt.shape[0], 0)

    def test_preserves_winding_order(self):
        """Kept faces must retain their original vertex ordering --
        the downstream fan-triangulator depends on it."""
        points, indices, counts = _unit_cube()
        view_pos = (0.0, 0.0, 100.0)
        new_idx, new_cnt = cull_backfaces_by_view(
            points, indices, counts, view_pos,
        )
        # +Z face original ordering is [4, 5, 6, 7].
        self.assertEqual(list(new_idx), [4, 5, 6, 7])


# ===========================================================================
# Duplicate-with-colliding-short-name (standalone animated gizmo)
# ===========================================================================


class TestLocatorDuplicateNameCollision(unittest.TestCase):
    """Duplicating a transform whose shape is an mPyLocator keeps the shape's
    SHORT name identical (two shapes named e.g. "gizShape" under transform1 and
    transform2). Every name-based re-resolution then becomes ambiguous, which
    used to leave the duplicate with (a) no api1 MObject -> dynamic input attrs
    invisible and (b) no Init namespace. The two draw expressions on the
    duplicate then failed with ``AttributeError`` (dynamic attr) and
    ``NameError`` (Init global), and the gizmo drew nothing.

    The fix resolves DAG nodes by their UNIQUE full DAG path in
    ``SelfProxy._ensure_api1_mobject`` and
    ``init_registry.ensure_init_namespace_for_mobject``.

    User requirement: standalone animated gizmos with no external plug deps
    must always duplicate and render like their predecessor.
    """

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def _draw(self, shape_path):
        """Evaluate the api2 draw path for a shape addressed by full DAG path
        (short names are ambiguous once a colliding duplicate exists)."""
        import maya.api.OpenMaya as om

        sel = om.MSelectionList()
        sel.add(shape_path)
        node_obj = sel.getDependNode(0)
        mpx = om.MFnDependencyNode(node_obj).userNode()
        return mpx.evaluateDrawItems(time_value=0.0)

    def _active(self, out):
        return {c["slot"] for c in out["commands"]}

    def _rename_arbitrary(self, loc, base):
        """Give the created locator an ARBITRARY shape name that is NOT the
        ``<transform>Shape`` convention. Maya only auto-renames a duplicated
        shape when its name matches ``parentShape``; an arbitrary name is
        preserved verbatim, so the duplicate collides on the short name -- the
        exact condition that triggered the reported bug (the real templates
        collide the same way, their shapes being named e.g. "asTest").

        Sources/attrs are set on the wrapper BEFORE this rename (the wrapper
        addresses the node by name); the Init namespace is keyed by MObject
        hashCode, so it survives the rename.
        """
        orig_shape = loc.get_name()
        xform = mc.listRelatives(orig_shape, parent=True, fullPath=True)[0]
        mc.rename(xform, base + "Rig")
        xform = mc.ls(base + "Rig", long=True)[0]
        shape = mc.listRelatives(xform, shapes=True, fullPath=True)[0]
        mc.rename(shape, base + "Giz")  # base+"Giz" != (base+"Rig")+"Shape"
        return mc.listRelatives(xform, shapes=True, fullPath=True)[0]

    def _duplicate_and_assert_collision(self, orig_shape):
        transform = mc.listRelatives(orig_shape, parent=True, fullPath=True)[0]
        dup_tf = mc.duplicate(transform)[0]
        dup_shape = mc.listRelatives(dup_tf, shapes=True, fullPath=True)[0]
        # Precondition: the duplicate shares the original's short name, which
        # is what makes name-based resolution ambiguous.
        self.assertEqual(
            dup_shape.split("|")[-1],
            orig_shape.split("|")[-1],
            "duplicate shape should share the original's short name",
        )
        return dup_shape

    def test_duplicate_resolves_init_namespace_global(self):
        """Init-namespace path: the duplicate's Compute reads a global defined
        in its Init source. Regressed as ``NameError: name '_wallclock' is not
        defined`` before the full-DAG-path fix."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="dupInit")
        loc.set_init_expression(
            "_wallclock = 42.0\n"
            "from mpynode._common.draw.draw_types import DrawPoints\n")
        loc.set_compute_expression(
            "import numpy as np\n"
            "w = _wallclock  # resolved from the per-node Init namespace\n"
            "self.draw = DrawPoints(np.array([[w, 0, 0]], np.float32),\n"
            "                       color=(1, 1, 1))\n"
        )
        orig_shape = self._rename_arbitrary(loc, "dupInit")
        # Original draws (unique short name at this point).
        self.assertIn("points", self._active(self._draw(orig_shape)))

        dup_shape = self._duplicate_and_assert_collision(orig_shape)
        cmds = self._draw(dup_shape)["commands"]
        self.assertEqual(
            [c["slot"] for c in cmds], ["points"],
            "duplicated locator must resolve its Init-namespace global "
            "(_wallclock) despite the colliding short name",
        )
        self.assertAlmostEqual(
            float(cmds[0]["buffer"]["positions"][0, 0]), 42.0)

    def test_duplicate_resolves_dynamic_input_attr(self):
        """api1-bridge path: the duplicate's Compute reads a dynamic input attr
        via ``self.<name>``. Regressed as ``AttributeError: 'self' has no plug
        ... named 'popDuration'`` before the full-DAG-path fix."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="dupAttr")
        loc.add_input_attr("popDuration", "float")
        mc.setAttr(loc.get_name() + ".popDuration", 0.6)
        loc.set_compute_expression(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawPoints\n"
            "d = self.popDuration  # dynamic input attr via the api1 bridge\n"
            "self.draw = DrawPoints(np.array([[d, 0, 0]], np.float32),\n"
            "                       color=(1, 1, 1))\n"
        )
        orig_shape = self._rename_arbitrary(loc, "dupAttr")
        self.assertIn("points", self._active(self._draw(orig_shape)))

        dup_shape = self._duplicate_and_assert_collision(orig_shape)
        # duplicate copies the dynamic attr's value (0.6), not a connection.
        cmds = self._draw(dup_shape)["commands"]
        self.assertEqual(
            [c["slot"] for c in cmds], ["points"],
            "duplicated locator must resolve its dynamic input attr "
            "(popDuration) through the api1 bridge despite the colliding "
            "short name",
        )
        self.assertAlmostEqual(
            float(cmds[0]["buffer"]["positions"][0, 0]), 0.6, places=5
        )


def setUpModule():
    _setUpModule__phase29()
    _setUpModule__phase29_2()
    _setUpModule__phase30()
    _setUpModule__phaseR_0_locator_ab()
    _setUpModule__phase05()


if __name__ == "__main__":
    import unittest
    unittest.main()
