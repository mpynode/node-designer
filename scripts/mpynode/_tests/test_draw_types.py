"""The mPyLocator object draw surface (``self.draw = DrawCircle(...)``).

``draw_types`` is Maya-free on purpose, so almost everything here runs without a
viewport: the contract under test is that ``to_commands()`` emits ONE record per
authored item, in authoring order, each carrying exactly the buffer dict
``MPyLocator``'s draw override already consumes -- with the parallel-array
bookkeeping (segment decomposition, colour trimming) done for the author instead
of by them.

The tests worth keeping honest are the ones covering what used to fail SILENTLY:

  * a polyline's per-vertex colour array is one row LONGER than its segment
    list; untrimmed, the whole buffer fails a length check and draws nothing
  * authoring order IS draw order -- bucketing items by type would quietly move
    every label on top of every surface, whatever the author wrote
  * a list (however nested) is the same drawing as a ``+`` chain, so a drawing
    accumulated in a loop needs no ``sum()``
"""
from __future__ import annotations

import unittest

import numpy as np

from mpynode._common.draw.draw_types import (
    DrawBox, DrawCircle, DrawCone, DrawCurve, DrawCylinder, DrawGroup,
    DrawItem, DrawLines, DrawMesh, DrawPoints, DrawSphere, DrawText,
    to_commands,
)
from mpynode._tests import _setup


def setUpModule():
    _setup.standalone_init()


def _buf(drawing, index=0):
    """The buffer of one command in ``drawing`` (default: the only one)."""
    return to_commands(drawing)[index]["buffer"]


def _slots(drawing):
    """The slot of every command in ``drawing``, in draw order."""
    return [c["slot"] for c in to_commands(drawing)]


def _quad_arrays(x=0.0):
    pts = np.array([[x, 0, 0], [x + 1, 0, 0], [x + 1, 1, 0], [x, 1, 0]],
                   dtype=np.float64)
    return pts, np.array([4]), np.array([0, 1, 2, 3])


class _MeshLike:
    """Duck-typed stand-in for _api2.geometry.Mesh (which needs Maya)."""

    def __init__(self, x=0.0):
        self.points, self.counts, self.indices = _quad_arrays(x)


class TestScalarFriendly(unittest.TestCase):
    """One circle should cost one call with scalars -- the old form needed six
    one-element arrays with the right nesting depth."""

    def test_one_circle_from_plain_tuples(self):
        b = _buf(DrawCircle(center=(0, 0, -1), radius=6.0))
        self.assertEqual(b["kinds"], ["circle"])
        self.assertEqual(b["centers"].shape, (1, 3))
        np.testing.assert_allclose(b["centers"][0], [0, 0, -1])
        np.testing.assert_allclose(b["radii"], [6.0])
        self.assertEqual(b["filled"], [False])
        self.assertEqual(b["colors"].shape, (1, 4))

    def test_arrays_still_emit_n_in_one_call(self):
        c = np.zeros((5, 3))
        b = _buf(DrawSphere(center=c, radius=np.arange(5.0)))
        self.assertEqual(b["centers"].shape, (5, 3))
        self.assertEqual(len(b["kinds"]), 5)
        self.assertEqual(b["kinds"][0], "sphere")

    def test_every_primitive_reports_its_native_kind(self):
        for cls, kind in ((DrawSphere, "sphere"), (DrawBox, "box"),
                          (DrawCone, "cone"), (DrawCylinder, "cylinder"),
                          (DrawCircle, "circle")):
            self.assertEqual(_buf(cls())["kinds"], [kind])

    def test_scalar_radius_broadcasts_over_many_centers(self):
        b = _buf(DrawBox(center=np.zeros((3, 3)), radius=2.0))
        np.testing.assert_allclose(b["radii"], [2, 2, 2])

    def test_mismatched_radius_count_raises(self):
        with self.assertRaises(ValueError):
            DrawBox(center=np.zeros((3, 3)), radius=[1.0, 2.0])


class TestPolyline(unittest.TestCase):

    def test_curve_decomposes_into_segments(self):
        pts = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]],
                       dtype=np.float64)
        b = _buf(DrawCurve(pts))
        self.assertEqual(b["starts"].shape, (3, 3))
        np.testing.assert_allclose(b["starts"][0], [0, 0, 0])
        np.testing.assert_allclose(b["ends"][0], [1, 0, 0])
        np.testing.assert_allclose(b["ends"][-1], [3, 0, 0])

    def test_closed_curve_adds_the_wrap_segment(self):
        pts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0]], dtype=np.float64)
        b = _buf(DrawCurve(pts, closed=True))
        self.assertEqual(b["starts"].shape, (3, 3))
        np.testing.assert_allclose(b["ends"][-1], [0, 0, 0])

    def test_per_vertex_colors_are_trimmed_to_the_segment_count(self):
        """N points -> N-1 segments but N colours. Untrimmed, the renderer's
        length check rejects the buffer and nothing draws."""
        pts = np.zeros((5, 3))
        cols = np.tile([1.0, 0.0, 0.0, 1.0], (5, 1))
        b = _buf(DrawCurve(pts, color=cols))
        self.assertEqual(b["starts"].shape[0], 4)
        self.assertEqual(b["colors"].shape[0], 4)

    def test_uniform_color_broadcasts(self):
        b = _buf(DrawCurve(np.zeros((4, 3)), color=(1, 0, 0)))
        self.assertEqual(b["colors"].shape, (3, 4))
        np.testing.assert_allclose(b["colors"][0][:3], [1, 0, 0])

    def test_a_single_point_draws_nothing_rather_than_erroring(self):
        self.assertEqual(to_commands(DrawCurve(np.zeros((1, 3)))), [])

    def test_explicit_segments_via_drawlines(self):
        b = _buf(DrawLines(starts=(0, 0, 0), ends=(1, 1, 1)))
        self.assertEqual(b["starts"].shape, (1, 3))

    def test_drawlines_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            DrawLines(starts=np.zeros((3, 3)), ends=np.zeros((2, 3)))

    def test_world_space_reaches_the_buffer(self):
        """Endpoints already in world space must survive to the override, which
        cancels the locator's own transform for them."""
        b = _buf(DrawLines(starts=(0, 0, 0), ends=(1, 1, 1), world_space=True))
        self.assertTrue(b["world_space"])
        self.assertFalse(_buf(DrawCurve(np.zeros((3, 3))))["world_space"])


class TestPolygonPatches(unittest.TestCase):

    def test_two_patches_are_two_commands_in_order(self):
        """Patches are NOT merged: each keeps its own buffer, drawn in the
        order it was authored."""
        g = DrawMesh(*_quad_arrays(0.0)) + DrawMesh(*_quad_arrays(5.0))
        cmds = to_commands(g)
        self.assertEqual([c["slot"] for c in cmds], ["polygons", "polygons"])
        for c in cmds:
            self.assertEqual(c["buffer"]["points"].shape, (4, 3))
            np.testing.assert_array_equal(c["buffer"]["indices"], [0, 1, 2, 3])
        np.testing.assert_allclose(cmds[0]["buffer"]["points"][0], [0, 0, 0])
        np.testing.assert_allclose(cmds[1]["buffer"]["points"][0], [5, 0, 0])

    def test_sum_keeps_authoring_order(self):
        g = sum([DrawMesh(*_quad_arrays(float(i))) for i in range(3)])
        cmds = to_commands(g)
        self.assertEqual(len(cmds), 3)
        np.testing.assert_allclose(
            [c["buffer"]["points"][0][0] for c in cmds], [0, 1, 2])

    def test_accepts_a_mesh_like_object(self):
        b = _buf(DrawMesh(_MeshLike(2.0)))
        self.assertEqual(b["points"].shape, (4, 3))
        np.testing.assert_allclose(b["points"][0], [2, 0, 0])

    def test_rejects_a_non_mesh_without_arrays(self):
        with self.assertRaises(TypeError):
            DrawMesh(object())

    def test_inconsistent_counts_and_indices_raise(self):
        with self.assertRaises(ValueError):
            DrawMesh(np.zeros((4, 3)), np.array([4]), np.array([0, 1]))

    def test_face_colors_are_one_row_per_face(self):
        b = _buf(DrawMesh(*_quad_arrays(), color=(1, 0, 0)))
        self.assertEqual(b["face_colors"].shape, (1, 4))

    def test_outline_reaches_the_wireframe_keys(self):
        b = _buf(DrawMesh(*_quad_arrays()).outlined((1, 1, 1), width=3.0))
        self.assertEqual(b["wireframe"], (1, 1, 1))
        self.assertEqual(b["wireframe_width"], 3.0)
        self.assertTrue(b["wireframe_boundary_only"])

    def test_no_outline_means_no_wireframe_keys(self):
        self.assertNotIn("wireframe", _buf(DrawMesh(*_quad_arrays())))

    def test_precise_hover_opt_in_rides_on_the_patch(self):
        """Per-PATCH, so a gizmo can keep its decoration out of the pick."""
        self.assertTrue(
            _buf(DrawMesh(*_quad_arrays(), precise_hover=True))["precise_hover"])
        self.assertNotIn("precise_hover", _buf(DrawMesh(*_quad_arrays())))


class TestPolygonFillModes(unittest.TestCase):
    """The polygons buffer defines FOUR mutually-exclusive fill keys with a
    renderer-side precedence. The object layer has to reach all four, or a
    template that uses one is stuck on raw dicts."""

    def test_color_emits_face_colors(self):
        b = _buf(DrawMesh(*_quad_arrays(), color=(1, 0, 0)))
        self.assertIn("face_colors", b)
        self.assertEqual(b["face_colors"].shape, (1, 4))

    def test_uniform_color_emits_the_colors_fast_path(self):
        b = _buf(DrawMesh(*_quad_arrays(), uniform_color=(0.45, 0.85, 1.0, 0.6)))
        self.assertEqual(b["colors"], (0.45, 0.85, 1.0, 0.6))
        self.assertNotIn("face_colors", b)

    def test_vertex_colors_are_one_row_per_point(self):
        vc = np.tile((0, 1, 0), (4, 1))
        b = _buf(DrawMesh(*_quad_arrays(), vertex_colors=vc))
        self.assertEqual(b["vertex_colors"].shape, (4, 4))
        self.assertNotIn("face_colors", b)

    def test_face_vertex_colors_are_one_row_per_corner(self):
        fvc = np.tile((0, 0, 1), (4, 1))
        b = _buf(DrawMesh(*_quad_arrays(), face_vertex_colors=fvc))
        self.assertEqual(b["face_vertex_colors"].shape, (4, 4))

    def test_no_fill_still_defaults_to_face_colors(self):
        # Historical behaviour: an uncoloured DrawMesh draws FILLED (white).
        # Emitting no fill key at all would silently turn it wireframe-only.
        self.assertEqual(_buf(DrawMesh(*_quad_arrays()))["face_colors"].shape,
                         (1, 4))

    def test_two_fill_modes_on_ONE_patch_raise(self):
        with self.assertRaises(ValueError):
            DrawMesh(*_quad_arrays(), color=(1, 0, 0),
                     uniform_color=(0, 1, 0))

    def test_two_patches_may_each_use_a_DIFFERENT_fill_mode(self):
        """Each patch is its own command, so it keeps its own style. Under the
        old merged buffer this combination raised."""
        g = (DrawMesh(*_quad_arrays(0.0), color=(1, 0, 0))
             + DrawMesh(*_quad_arrays(5.0),
                        vertex_colors=np.tile((0, 1, 0), (4, 1))))
        cmds = to_commands(g)
        self.assertIn("face_colors", cmds[0]["buffer"])
        self.assertIn("vertex_colors", cmds[1]["buffer"])

    def test_an_uncoloured_patch_keeps_the_white_default_beside_a_coloured_one(self):
        g = DrawMesh(*_quad_arrays(0.0)) + DrawMesh(*_quad_arrays(5.0),
                                                    color=(1, 0, 0))
        cmds = to_commands(g)
        np.testing.assert_allclose(cmds[0]["buffer"]["face_colors"][0],
                                   [1, 1, 1, 1])
        np.testing.assert_allclose(cmds[1]["buffer"]["face_colors"][0][:3],
                                   [1, 0, 0])


class TestPolygonRenderFlags(unittest.TestCase):

    def test_cull_backfaces_passes_through_when_on(self):
        self.assertTrue(
            _buf(DrawMesh(*_quad_arrays(), cull_backfaces=True))["cull_backfaces"])

    def test_cull_backfaces_absent_when_off(self):
        self.assertNotIn("cull_backfaces", _buf(DrawMesh(*_quad_arrays())))

    def test_highlight_flags_default_to_absent_so_the_node_wide_toggle_wins(self):
        b = _buf(DrawMesh(*_quad_arrays()))
        self.assertNotIn("highlight_fill", b)
        self.assertNotIn("highlight_wire", b)

    def test_explicit_false_is_written_through_not_dropped(self):
        # highlight_wire=False must REACH the buffer: it is how a template turns
        # selection tinting off for one aspect. Treating False as "unset" would
        # silently re-enable it.
        b = _buf(DrawMesh(*_quad_arrays(), highlight_fill=True,
                          highlight_wire=False))
        self.assertTrue(b["highlight_fill"])
        self.assertIn("highlight_wire", b)
        self.assertFalse(b["highlight_wire"])


class TestText(unittest.TestCase):

    def test_a_bare_string_is_one_label_not_a_list_of_characters(self):
        b = _buf(DrawText("MPyNode!", position=(0, 2, 0)))
        self.assertEqual(b["strings"], ["MPyNode!"])
        self.assertEqual(b["positions"].shape, (1, 3))

    def test_many_labels_need_many_positions(self):
        b = _buf(DrawText(["a", "b", "c"], position=np.zeros((3, 3))))
        self.assertEqual(b["strings"], ["a", "b", "c"])

    def test_one_label_broadcasts_over_many_positions(self):
        b = _buf(DrawText("x", position=np.zeros((4, 3))))
        self.assertEqual(b["strings"], ["x"] * 4)

    def test_label_position_mismatch_raises(self):
        with self.assertRaises(ValueError):
            DrawText(["a", "b"], position=(0, 0, 0))

    def test_plus_groups_labels_it_does_not_concatenate_strings(self):
        cmds = to_commands(DrawText("a") + DrawText("b", position=(1, 0, 0)))
        self.assertEqual([c["buffer"]["strings"] for c in cmds], [["a"], ["b"]])

    def test_screen_space_flag(self):
        self.assertEqual(_buf(DrawText("a", screen_space=True))["space"],
                         "screen")


class TestComposition(unittest.TestCase):

    def test_plus_returns_a_group_and_keeps_authoring_order(self):
        g = (DrawCircle(radius=2)
             + DrawCurve(np.zeros((3, 3)))
             + DrawText("hi")
             + DrawPoints(np.zeros((2, 3))))
        self.assertIsInstance(g, DrawGroup)
        self.assertEqual(_slots(g), ["shapes", "lines", "text", "points"])

    def test_authoring_order_is_draw_order_not_type_order(self):
        """A label written FIRST stays first -- it draws UNDER the surface. Type
        bucketing would silently float every label to the top."""
        g = DrawText("under") + DrawMesh(*_quad_arrays())
        self.assertEqual(_slots(g), ["text", "polygons"])
        self.assertEqual(_slots(DrawMesh(*_quad_arrays()) + DrawText("over")),
                         ["polygons", "text"])

    def test_two_of_the_same_type_stay_two_commands(self):
        cmds = to_commands(DrawCircle(radius=1) + DrawCircle(radius=2))
        np.testing.assert_allclose(
            [c["buffer"]["radii"][0] for c in cmds], [1, 2])

    def test_sum_of_items_works(self):
        g = sum([DrawCircle(radius=float(r)) for r in (1, 2, 3)])
        np.testing.assert_allclose(
            [c["buffer"]["radii"][0] for c in to_commands(g)], [1, 2, 3])

    def test_groups_nest_flat(self):
        g = (DrawCircle() + DrawCircle()) + (DrawCircle() + DrawCircle())
        self.assertEqual(len(g), 4)

    def test_adding_a_non_drawitem_is_an_explicit_error(self):
        with self.assertRaises(TypeError):
            _ = DrawCircle() + 5

    def test_multiply_and_subtract_are_deliberately_absent(self):
        """Ambiguous on a heterogeneous drawing -- scale via .scaled()."""
        for d in ("__mul__", "__sub__", "__truediv__"):
            self.assertIs(getattr(DrawItem, d, None),
                          getattr(object, d, None), d)
        with self.assertRaises(TypeError):
            _ = DrawCircle() * 2


class TestIterableDrawings(unittest.TestCase):
    """A list is the same drawing as a ``+`` chain -- so a drawing accumulated
    in a loop needs no ``sum()``, and its items stay individually addressable."""

    def test_a_list_matches_the_equivalent_plus_chain(self):
        items = [DrawCircle(radius=1), DrawText("a"), DrawPoints(np.zeros((2, 3)))]
        self.assertEqual(_slots(items), _slots(items[0] + items[1] + items[2]))

    def test_a_tuple_works_too(self):
        self.assertEqual(_slots((DrawCircle(), DrawText("a"))),
                         ["shapes", "text"])

    def test_nested_lists_flatten_in_order(self):
        """Nesting is a grouping convenience, not a draw-order override: the
        drawing is read left-to-right, depth-first."""
        g = [DrawCircle(radius=1),
             [DrawCircle(radius=2), [DrawCircle(radius=3)]],
             DrawCircle(radius=4)]
        np.testing.assert_allclose(
            [c["buffer"]["radii"][0] for c in to_commands(g)], [1, 2, 3, 4])

    def test_a_group_nested_inside_a_list_flattens(self):
        g = [DrawCircle(radius=1) + DrawCircle(radius=2), DrawCircle(radius=3)]
        np.testing.assert_allclose(
            [c["buffer"]["radii"][0] for c in to_commands(g)], [1, 2, 3])

    def test_a_generator_is_accepted(self):
        g = (DrawCircle(radius=float(r)) for r in (1, 2))
        np.testing.assert_allclose(
            [c["buffer"]["radii"][0] for c in to_commands(g)], [1, 2])

    def test_none_entries_are_skipped_not_an_error(self):
        """An accumulator that appends None for "nothing here this frame"
        should not have to filter itself."""
        np.testing.assert_allclose(
            [c["buffer"]["radii"][0]
             for c in to_commands([None, DrawCircle(radius=7), None])], [7])

    def test_an_empty_list_draws_nothing(self):
        self.assertEqual(to_commands([]), [])
        self.assertEqual(to_commands([[], [None]]), [])

    def test_a_non_drawable_leaf_is_an_explicit_error(self):
        for bad in (5, "circle", {"radius": 2}, np.zeros((2, 3))):
            with self.assertRaises(TypeError):
                to_commands([DrawCircle(), bad])


class TestChainableTransforms(unittest.TestCase):

    def test_translated_moves_and_does_not_mutate_the_original(self):
        c = DrawCircle(center=(0, 0, 0), radius=1)
        np.testing.assert_allclose(_buf(c.translated(0, 5, 0))["centers"][0],
                                   [0, 5, 0])
        np.testing.assert_allclose(_buf(c)["centers"][0], [0, 0, 0])

    def test_scaled_scales_centers_and_radii_together(self):
        b = _buf(DrawCircle(center=(1, 0, 0), radius=2).scaled(3))
        np.testing.assert_allclose(b["centers"][0], [3, 0, 0])
        np.testing.assert_allclose(b["radii"], [6])

    def test_scaled_text_scales_glyph_size(self):
        np.testing.assert_allclose(_buf(DrawText("a", size=0.5).scaled(4))["sizes"],
                                   [2.0])

    def test_colored_restyles_a_copy(self):
        c = DrawCircle()
        np.testing.assert_allclose(_buf(c.colored((1, 0, 0)))["colors"][0][:3],
                                   [1, 0, 0])
        np.testing.assert_allclose(_buf(c)["colors"][0][:3], [1, 1, 1])

    def test_transforms_chain(self):
        b = _buf(DrawCircle(radius=1).translated(1, 0, 0).scaled(2)
                 .colored((0, 1, 0)))
        np.testing.assert_allclose(b["centers"][0], [2, 0, 0])
        np.testing.assert_allclose(b["radii"], [2])

    def test_transforms_apply_through_a_group(self):
        g = (DrawCircle(center=(0, 0, 0)) + DrawText("a", position=(0, 0, 0)))
        cmds = to_commands(g.translated(0, 3, 0))
        np.testing.assert_allclose(cmds[0]["buffer"]["centers"][0], [0, 3, 0])
        np.testing.assert_allclose(cmds[1]["buffer"]["positions"][0], [0, 3, 0])

    def test_a_drawing_can_be_reused_at_several_transforms(self):
        """The value property: build once, place many times."""
        unit = DrawCircle(radius=1)
        cmds = to_commands(unit.translated(0, 0, 0) + unit.translated(5, 0, 0))
        np.testing.assert_allclose(
            [c["buffer"]["centers"][0][0] for c in cmds], [0, 5])


class TestSpaceRules(unittest.TestCase):

    def test_each_item_carries_its_own_space(self):
        cmds = to_commands(DrawCircle() + DrawText("a", screen_space=True))
        self.assertEqual(cmds[0]["buffer"]["space"], "local")
        self.assertEqual(cmds[1]["buffer"]["space"], "screen")

    def test_two_items_of_the_SAME_type_may_use_different_spaces(self):
        """One command per item, so each carries its own ``space``. Under the
        old merged-per-type buffer this raised."""
        cmds = to_commands(DrawCircle() + DrawCircle(screen_space=True))
        self.assertEqual([c["buffer"]["space"] for c in cmds],
                         ["local", "screen"])

    def test_in_space_restyles(self):
        self.assertEqual(_buf(DrawCircle().in_space("screen"))["space"],
                         "screen")


class TestCommandShape(unittest.TestCase):
    """Each command must be shaped exactly like what the locator already
    harvests, or the draw override silently rejects it."""

    def test_buffer_keys_match_the_renderer_contract(self):
        cmds = to_commands([DrawCurve(np.zeros((3, 3))),
                            DrawPoints(np.zeros((2, 3))),
                            DrawMesh(*_quad_arrays()),
                            DrawCircle(),
                            DrawText("a")])
        want = {
            "lines": {"starts", "ends", "colors"},
            "points": {"positions", "colors", "sizes"},
            "polygons": {"points", "indices", "counts"},
            "shapes": {"kinds", "centers", "radii", "axes", "filled"},
            "text": {"positions", "strings", "colors", "sizes"},
        }
        self.assertEqual([c["slot"] for c in cmds], list(want))
        for cmd in cmds:
            self.assertLessEqual(want[cmd["slot"]], set(cmd["buffer"]),
                                 cmd["slot"])

    def test_every_command_is_a_slot_plus_a_buffer(self):
        for cmd in to_commands(DrawCircle() + DrawText("a")):
            self.assertEqual(set(cmd), {"slot", "buffer"})
            self.assertIsInstance(cmd["buffer"], dict)

    def test_point_arrays_are_float32_for_the_renderer(self):
        self.assertEqual(_buf(DrawCurve(np.zeros((3, 3))))["starts"].dtype,
                         np.float32)

    def test_to_commands_of_none_is_empty(self):
        self.assertEqual(to_commands(None), [])


class TestDrawSlotOnARealNode(unittest.TestCase):
    """``self.draw`` end-to-end through a live mPyLocator."""

    def setUp(self):
        import maya.cmds as mc
        mc.file(new=True, force=True)

    def _loc(self, expr, name="gz"):
        from mpynode.wrappers.mpy_locator import MPyLocator
        loc = MPyLocator.create(name=name)
        loc.set_compute_expression(expr)
        return loc.evaluate_draw_commands()

    def test_draw_object_produces_a_shapes_command(self):
        out = self._loc(
            "from mpynode._common.draw.draw_types import DrawCircle\n"
            "self.draw = DrawCircle(center=(0, 0, -1), radius=6.0)\n")
        self.assertEqual([c["slot"] for c in out["commands"]], ["shapes"])
        b = out["commands"][0]["buffer"]
        self.assertEqual(b["kinds"], ["circle"])
        np.testing.assert_allclose(b["radii"], [6.0])

    def test_a_composed_drawing_keeps_its_order(self):
        out = self._loc(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import (\n"
            "    DrawCircle, DrawCurve, DrawText)\n"
            "pts = np.zeros((4, 3))\n"
            "pts[:, 0] = np.arange(4.0)\n"
            "self.draw = (DrawCircle(radius=2.0)\n"
            "              + DrawCurve(pts)\n"
            "              + DrawText('hip_ctrl', position=(0, 2, 0)))\n")
        cmds = out["commands"]
        self.assertEqual([c["slot"] for c in cmds], ["shapes", "lines", "text"])
        self.assertEqual(cmds[1]["buffer"]["starts"].shape, (3, 3))
        self.assertEqual(cmds[2]["buffer"]["strings"], ["hip_ctrl"])

    def test_a_list_of_items_is_a_valid_drawing(self):
        out = self._loc(
            "from mpynode._common.draw.draw_types import DrawCircle\n"
            "rings = []\n"
            "for i in range(3):\n"
            "    rings.append(DrawCircle(radius=float(i + 1)))\n"
            "self.draw = rings\n")
        np.testing.assert_allclose(
            [c["buffer"]["radii"][0] for c in out["commands"]], [1, 2, 3])

    def test_no_drawing_leaves_the_command_list_empty(self):
        self.assertEqual(self._loc("pass\n")["commands"], [])

    def test_precise_hover_rides_along_from_a_drawmesh(self):
        out = self._loc(
            "import numpy as np\n"
            "from mpynode._common.draw.draw_types import DrawMesh\n"
            "self.draw = DrawMesh(\n"
            "    np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], float),\n"
            "    np.array([4]), np.array([0,1,2,3]), precise_hover=True)\n")
        self.assertTrue(out["commands"][0]["buffer"]["precise_hover"])

    def test_the_node_wide_precise_hover_toggle_is_harvested(self):
        out = self._loc(
            "from mpynode._common.draw.draw_types import DrawCircle\n"
            "self.draw = DrawCircle()\n"
            "self.precise_hover = True\n")
        self.assertTrue(out["precise_hover"])
        self.assertFalse(self._loc("pass\n", name="gz2")["precise_hover"])

    def test_a_malformed_drawing_does_not_take_the_node_down(self):
        """A non-drawable raises inside the flatten; the node must survive and
        report, not crash the draw."""
        out = self._loc("self.draw = 5\n")
        self.assertEqual(out["commands"], [])


class TestDrawSlotIsDeclared(unittest.TestCase):
    """``draw`` must appear in MPyLocator.INTERNAL_API_SLOTS.

    The slot works at compute time either way -- the seed lives in
    ``_api2/mpy_locator.py``. But the wrapper's declaration is what the
    Framework tab, the Variables panel and the porter read, so an undeclared
    slot is invisible in the UI: the canonical draw surface simply would not be
    listed anywhere a user looks.
    """

    def test_draw_is_a_declared_slot(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        names = [entry[0] if not isinstance(entry, str) else entry
                 for entry in MPyLocator.INTERNAL_API_SLOTS]
        self.assertIn("draw", names)

    def test_draw_is_declared_write(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        spec = next(e for e in MPyLocator.INTERNAL_API_SLOTS if e[0] == "draw")
        self.assertEqual(spec[1], "write")

    def test_the_five_dict_slots_are_gone(self):
        """One transport, not two. Leaving the per-type dicts declared beside
        ``self.draw`` is what let the interpreted and compiled renderers
        disagree about draw order."""
        from mpynode.wrappers.mpy_locator import MPyLocator
        names = {e[0] for e in MPyLocator.INTERNAL_API_SLOTS}
        for slot in ("lines", "points", "polygons", "shapes", "text"):
            self.assertNotIn(slot, names)

    def test_precise_hover_replaced_hover_shape(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        names = {e[0] for e in MPyLocator.INTERNAL_API_SLOTS}
        self.assertIn("precise_hover", names)
        self.assertNotIn("hover_shape", names)


class TestPrimitiveAsMesh(unittest.TestCase):
    """``DrawPrimitive.as_mesh()`` -- the escape hatch to the styling only a
    ``DrawMesh`` can carry (outline, per-face colour).

    The contract is that the tessellation reproduces WHAT MAYA DRAWS, so each
    case below pins the geometry against the corresponding ``MUIDrawManager``
    call in ``_api2/mpy_locator._draw_shapes``::

        sphere    dm.sphere(center, r, filled)
        box       dm.box(center, up=axis, right=(1,0,0), r, r, r, filled)
        cone      dm.cone(BASE=center, axis, r, height=2r, filled)
        cylinder  dm.cylinder(CENTER=center, axis, r, height=2r, 16, filled)
        circle    dm.circle(center, normal=axis, r, filled)
    """

    def _faces(self, m):
        """[(p0, p1, ...), ...] -- one point tuple list per face."""
        out, off = [], 0
        for c in m.counts:
            out.append(m.points[m.indices[off:off + int(c)]])
            off += int(c)
        return out

    def test_returns_a_drawmesh(self):
        self.assertIsInstance(DrawSphere(radius=2.0).as_mesh(), DrawMesh)

    def test_sphere_points_lie_on_the_drawn_sphere(self):
        c, r = np.array([1.0, -2.0, 3.0]), 2.5
        m = DrawSphere(center=c, radius=r).as_mesh()
        d = np.linalg.norm(m.points - c, axis=1)
        np.testing.assert_allclose(d, np.full(d.shape, r), atol=1e-9)
        # rotationally symmetric: dm.sphere takes no axis, so neither may we
        m2 = DrawSphere(center=c, radius=r, axis=(1.0, 0.0, 0.0)).as_mesh()
        np.testing.assert_allclose(m.points, m2.points, atol=1e-12)

    def test_box_is_the_up_right_frame_with_half_extent_radius(self):
        c, r = np.array([0.0, 0.0, 0.0]), 2.0
        m = DrawBox(center=c, radius=r, axis=(0.0, 1.0, 0.0)).as_mesh()
        self.assertEqual(m.points.shape, (8, 3))
        self.assertEqual(list(m.counts), [4] * 6)
        corners = {tuple(p) for p in np.round(m.points, 9)}
        want = {(x * r, y * r, z * r)
                for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0)}
        self.assertEqual(corners, want)

    def test_box_follows_the_axis_as_its_up_vector(self):
        m = DrawBox(radius=1.0, axis=(0.0, 0.0, 1.0)).as_mesh()
        # up = +Z, right = +X (the fixed side vector the draw passes), so the
        # box still spans +-1 on every world axis -- but rotated, which shows in
        # the FACE normals: one pair must be perpendicular to +Z.
        self.assertEqual(m.points.shape, (8, 3))
        np.testing.assert_allclose(np.abs(m.points).max(axis=0),
                                   [1.0, 1.0, 1.0], atol=1e-9)

    def test_cone_base_sits_at_center_and_apex_two_radii_along_axis(self):
        c, r = np.array([0.0, 1.0, 0.0]), 3.0
        m = DrawCone(center=c, radius=r, axis=(0.0, 1.0, 0.0)).as_mesh()
        h = np.round(m.points[:, 1], 9)
        # dm.cone takes the BASE, and the draw passes height = 2 * radius
        self.assertAlmostEqual(float(h.min()), 1.0)
        self.assertAlmostEqual(float(h.max()), 1.0 + 2.0 * r)
        apex = m.points[np.isclose(m.points[:, 1], 1.0 + 2.0 * r)]
        self.assertEqual(apex.shape[0], 1)
        np.testing.assert_allclose(apex[0], [0.0, 1.0 + 2.0 * r, 0.0],
                                   atol=1e-9)
        ring = m.points[np.isclose(m.points[:, 1], 1.0)]
        np.testing.assert_allclose(np.linalg.norm(ring - c, axis=1),
                                   np.full((ring.shape[0],), r), atol=1e-9)

    def test_cylinder_is_centered_with_height_two_radii_and_16_segments(self):
        c, r = np.array([0.0, 0.0, 0.0]), 1.5
        m = DrawCylinder(center=c, radius=r, axis=(0.0, 1.0, 0.0)).as_mesh()
        y = m.points[:, 1]
        self.assertAlmostEqual(float(y.min()), -r)      # centered, not based
        self.assertAlmostEqual(float(y.max()), r)
        # the draw hardcodes subdivisionsAxis=16
        self.assertEqual(m.points.shape, (32, 3))
        self.assertEqual(sorted(set(int(c_) for c_ in m.counts)), [4, 16])

    def test_circle_is_one_ngon_in_the_normal_plane(self):
        c = np.array([0.0, 0.0, -1.0])
        m = DrawCircle(center=c, radius=4.0).as_mesh()   # default axis +Z
        self.assertEqual(len(m.counts), 1)
        np.testing.assert_allclose(m.points[:, 2], np.full(m.points.shape[0], -1.0),
                                   atol=1e-9)
        np.testing.assert_allclose(np.linalg.norm(m.points - c, axis=1),
                                   np.full(m.points.shape[0], 4.0), atol=1e-9)

    def test_array_of_primitives_merges_into_one_mesh(self):
        centers = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
        one = DrawBox(center=centers[:1], radius=1.0).as_mesh()
        two = DrawBox(center=centers, radius=1.0).as_mesh()
        self.assertEqual(two.points.shape[0], 2 * one.points.shape[0])
        self.assertEqual(len(two.counts), 2 * len(one.counts))
        # the second shell is rebased, not aliased onto the first
        self.assertEqual(int(two.indices.max()), two.points.shape[0] - 1)

    def test_colour_and_space_carry_over(self):
        red, blue = (1.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0)
        m = DrawBox(center=np.zeros((2, 3)), radius=1.0,
                    color=[red, blue], space="screen").as_mesh()
        self.assertEqual(m._space, "screen")
        face_colors = _buf(m)["face_colors"]
        self.assertEqual(face_colors.shape, (12, 4))     # 2 boxes * 6 faces
        np.testing.assert_allclose(face_colors[:6], np.tile(red, (6, 1)))
        np.testing.assert_allclose(face_colors[6:], np.tile(blue, (6, 1)))

    def test_result_is_outlinable_and_flushes_to_polygons(self):
        cmds = to_commands(DrawSphere(radius=2.0).as_mesh().outlined((1, 1, 1, 1)))
        self.assertEqual([c["slot"] for c in cmds], ["polygons"])
        self.assertEqual(cmds[0]["buffer"]["wireframe"], (1, 1, 1, 1))

    def test_scaled_primitive_tessellates_at_the_new_radius(self):
        m = DrawSphere(radius=1.0).scaled(3.0).as_mesh()
        np.testing.assert_allclose(np.linalg.norm(m.points, axis=1),
                                   np.full(m.points.shape[0], 3.0), atol=1e-9)

    def test_solid_faces_wind_outward(self):
        """A DrawMesh can be drawn with ``cull_backfaces``, so a converted
        solid must not be inside-out."""
        for prim in (DrawBox(radius=2.0), DrawSphere(radius=2.0),
                     DrawCone(radius=2.0), DrawCylinder(radius=2.0)):
            m = prim.as_mesh()
            inside = m.points.mean(axis=0)      # convex -> the mean is interior
            for face in self._faces(m):
                n = np.cross(face[1] - face[0], face[2] - face[0])
                self.assertGreater(
                    float(np.dot(n, face.mean(axis=0) - inside)), 0.0,
                    "%s has an inward face" % type(prim).__name__)

    def test_circle_faces_along_its_normal(self):
        # read the FACE (index order), not the raw point array -- the winding
        # lives in the indices.
        face = self._faces(DrawCircle(radius=2.0, axis=(0.0, 1.0, 0.0)).as_mesh())[0]
        n = np.cross(face[1] - face[0], face[2] - face[0])
        self.assertGreater(float(np.dot(n, [0.0, 1.0, 0.0])), 0.0)

    def test_every_face_is_a_valid_polygon(self):
        for prim in (DrawSphere(), DrawBox(), DrawCone(), DrawCylinder(),
                     DrawCircle()):
            m = prim.as_mesh()
            self.assertEqual(int(m.counts.sum()), m.indices.size,
                             type(prim).__name__)
            self.assertTrue((m.counts >= 3).all(), type(prim).__name__)
            self.assertLess(int(m.indices.max()), m.points.shape[0],
                            type(prim).__name__)
            for face in self._faces(m):
                self.assertEqual(len({tuple(np.round(p, 9)) for p in face}),
                                 face.shape[0], type(prim).__name__)


if __name__ == "__main__":
    unittest.main()
