"""mPyLocator deterministic draw lowering (nd_lower.try_lower_locator).

``self.draw`` is an ordered list of drawing objects, not a numeric expression,
so the transpiler cannot see it directly. ``desugar_draw`` rewrites each
authored item into a synthetic ``self.__nd_draw_<family>(...)`` call in
AUTHORING ORDER, and a blessed lowering turns each of those into the matching
``data.emit*()`` C++ statement. Everything the rewrite cannot prove is rejected
so the caller keeps the AI-porter PORT region.

Two of the assertions here pin bugs that a clean COMPILE did not catch and only
an interpreted-vs-compiled buffer comparison did (see
``tools/probe_locator_parity.py``): the rank-1 point-row rule and the ``filled``
default.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import nd_lower, py_to_cpp
from mpynode.native.compiler.kernels import locator_draw_cpp


def _spec(compute, inputs=None, init=""):
    return {"compute": compute, "inputs": inputs or {}, "outputs": {},
            "variables": {}, "init": init}


def _lower(compute, inputs=None, init=""):
    return "\n".join(
        nd_lower.try_lower_locator(_spec(compute, inputs, init)) or [])


class TestDesugarDraw(unittest.TestCase):
    """self.draw = <objects>  ->  ordered synthetic emit calls."""

    def test_single_item_becomes_one_emit_call(self):
        out = locator_draw_cpp.desugar_draw(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=2.0)\n")
        self.assertIn("self.__nd_draw_shape(", out)
        self.assertNotIn("DrawCircle(", out)

    def test_plus_composition_preserves_authoring_order(self):
        out = locator_draw_cpp.desugar_draw(
            "self.draw = DrawPoints(p) + DrawLines(a, b) + DrawMesh(p, c, i)\n")
        self.assertLess(out.index("__nd_draw_points"), out.index("__nd_draw_lines"))
        self.assertLess(out.index("__nd_draw_lines"), out.index("__nd_draw_mesh"))

    def test_list_preserves_authoring_order(self):
        out = locator_draw_cpp.desugar_draw(
            "self.draw = [DrawMesh(p, c, i), DrawPoints(p)]\n")
        self.assertLess(out.index("__nd_draw_mesh"), out.index("__nd_draw_points"))

    def test_local_alias_is_followed(self):
        out = locator_draw_cpp.desugar_draw(
            "plate = DrawMesh(p, c, i)\n"
            "self.draw = plate\n")
        self.assertIn("self.__nd_draw_mesh(", out)

    def test_consumed_binding_is_dropped(self):
        """The alias' original ctor call must not survive as dead code -- the
        transpiler would reject it as a call to an unknown function."""
        out = locator_draw_cpp.desugar_draw(
            "cube = DrawMesh(p, c, i)\n"
            "self.draw = cube\n")
        self.assertNotIn("DrawMesh(", out)

    def test_positional_and_keyword_desugar_identically(self):
        pos = locator_draw_cpp.desugar_draw("self.draw = DrawPoints(p, c, 4.0)\n")
        kwd = locator_draw_cpp.desugar_draw(
            "self.draw = DrawPoints(positions=p, color=c, size=4.0)\n")
        self.assertEqual(pos, kwd)


class TestLocatorLowers(unittest.TestCase):
    """Expressions with a proven compiled form."""

    def test_one_circle(self):
        out = _lower("self.draw = DrawCircle(center=(0.0, 0.0, 0.0), "
                     "radius=2.0, color=(1.0, 0.0, 0.0))\n")
        self.assertIn("data.emitShape(", out)

    def test_shape_chain_emits_each_kind(self):
        out = _lower(
            "self.draw = (DrawSphere(center=(0.0, 0.0, 0.0), radius=1.0)\n"
            "             + DrawBox(center=(2.0, 0.0, 0.0), radius=0.5)\n"
            "             + DrawCone(center=(4.0, 0.0, 0.0), radius=0.5))\n")
        for kind in (0, 2, 3):            # sphere, box, cone
            self.assertIn("data.emitShape(%d," % kind, out)

    def test_points_and_lines(self):
        out = _lower(
            "pts = np.zeros((8, 3))\n"
            "self.draw = [DrawPoints(pts, color=(0.2, 0.8, 1.0), size=6.0),\n"
            "             DrawLines(pts, pts + 1.0, color=(1.0, 1.0, 0.0))]\n")
        self.assertIn("data.emitPoint(", out)
        self.assertIn("data.emitLine(", out)
        self.assertLess(out.index("data.emitPoint("), out.index("data.emitLine("))

    def test_closed_curve(self):
        out = _lower(
            "t = np.linspace(0.0, 6.28318, 32)\n"
            "ring = np.stack([np.cos(t), np.sin(t), np.zeros(32)], axis=1)\n"
            "self.draw = DrawCurve(ring, closed=True, color=(1.0, 0.5, 0.0))\n")
        self.assertIn("data.emitLine(", out)

    def test_mesh(self):
        out = _lower(
            "pts = np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]])\n"
            "self.draw = DrawMesh(pts, np.array([4]), np.array([0,1,2,3]),\n"
            "                     color=(0.2, 0.4, 0.8), cull_backfaces=True)\n")
        self.assertIn("data.emitPoly()", out)
        self.assertIn(".cull = true;", out)

    def test_mesh_outlined(self):
        out = _lower(
            "pts = np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]])\n"
            "cube = DrawMesh(pts, np.array([4]), np.array([0,1,2,3]))\n"
            "self.draw = cube.outlined((0.04, 0.04, 0.06, 1.0), width=2.0)\n")
        self.assertIn("data.emitPoly()", out)
        self.assertIn(".hasWire = true;", out)

    def test_flags_and_draw_context(self):
        out = _lower(
            "self.auto_highlight = False\n"
            "self.auto_refresh = True\n"
            "self.precise_hover = True\n"
            "r = 1.0 + 0.5 * np.sin(self.time * 0.1)\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r,\n"
            "                       color=self.selection_color)\n")
        self.assertRegex(out, r"data\.autoHighlight = .*false")
        self.assertRegex(out, r"data\.autoRefresh = .*true")
        self.assertRegex(out, r"data\.preciseHover = .*true")
        self.assertIn("ndin_self_time", out)              # self.time bound
        self.assertIn("ndin_self_selection_color", out)   # self.selection_color

    def test_draw_none_lowers_to_an_empty_frame(self):
        """`self.draw = None` is a legal drawing -- nothing. It must lower, not
        fall back to the porter."""
        lines = nd_lower.try_lower_locator(_spec(
            "self.draw = None\nself.auto_refresh = False\n"))
        self.assertIsNotNone(lines)
        self.assertNotIn("data.emit", "\n".join(lines))

    def test_user_inputs_bind(self):
        out = _lower(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=self.radius,\n"
            "                       color=self.tint)\n",
            inputs={"radius": {"type": "float", "is_array": False,
                               "default_value": 1.0},
                    "tint": {"type": "color", "is_array": False,
                             "default_value": [0.2, 0.4, 0.8]}})
        self.assertIn("data.emitShape(", out)


class TestDrawAccumulator(unittest.TestCase):
    """`items = []` / `items.append(...)` / `self.draw = items`.

    The ordered command transport makes this lower exactly: emission order is
    execution order, so an append under an `if` is an emit under the same `if`.
    Verified against the interpreted buffers by tools/probe_locator_parity.py.
    """

    def test_appends_become_emits_in_order(self):
        out = _lower(
            "items = []\n"
            "items.append(DrawPoints(np.zeros((4, 3))))\n"
            "items.append(DrawLines(np.zeros((2, 3)), np.ones((2, 3))))\n"
            "self.draw = items\n")
        self.assertLess(out.index("data.emitPoint("), out.index("data.emitLine("))

    def test_append_under_if_stays_under_the_if(self):
        """An inactive branch must contribute nothing -- not a default drawing."""
        out = _lower(
            "items = []\n"
            "if self.flag > 0.5:\n"
            "    items.append(DrawCircle(center=(0.0, 0.0, 0.0)))\n"
            "self.draw = items\n",
            inputs={"flag": {"type": "float", "is_array": False,
                             "default_value": 1.0}})
        self.assertIn("if (", out)
        self.assertLess(out.index("if ("), out.index("data.emitShape("))

    def test_append_in_a_loop_emits_per_iteration(self):
        out = _lower(
            "items = []\n"
            "for i in range(3):\n"
            "    items.append(DrawCircle(center=(float(i), 0.0, 0.0)))\n"
            "self.draw = items\n")
        self.assertIn("data.emitShape(", out)
        self.assertLess(out.index("for (nl_i"), out.index("data.emitShape("))

    def test_empty_accumulator_draws_nothing(self):
        lines = nd_lower.try_lower_locator(_spec(
            "items = []\nself.draw = items\n"))
        self.assertIsNotNone(lines)
        self.assertNotIn("data.emit", "\n".join(lines))

    def test_reading_the_list_disqualifies_it(self):
        """`len(items)` means the list is more than an append-ordered
        accumulator, so it is no longer safe to erase."""
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "items = []\n"
            "items.append(DrawCircle(center=(0.0, 0.0, 0.0)))\n"
            "n = len(items)\n"
            "self.draw = items\n")))

    def test_indexing_the_list_disqualifies_it(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "items = []\n"
            "items.append(DrawCircle(center=(0.0, 0.0, 0.0)))\n"
            "first = items[0]\n"
            "self.draw = items\n")))

    def test_extend_is_not_an_append_accumulator(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "items = []\n"
            "items.extend([DrawCircle(center=(0.0, 0.0, 0.0))])\n"
            "self.draw = items\n")))

    def test_reseeded_list_disqualifies_it(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "items = []\n"
            "items.append(DrawCircle(center=(0.0, 0.0, 0.0)))\n"
            "items = []\n"
            "self.draw = items\n")))


class TestDrawTextConstantLabels(unittest.TestCase):
    """Labels known at COMPILE time need no runtime string type: the count is
    fixed, so each label becomes its own emitText call. Parity-verified in
    tools/probe_locator_parity.py (p_text1 / p_textn)."""

    def test_single_label_broadcasts_over_positions(self):
        out = _lower('self.draw = DrawText("tag", np.zeros((3, 3)))\n')
        self.assertIn('MString("tag")', out)
        self.assertIn("data.emitText(", out)
        self.assertEqual(1, out.count("data.emitText("))   # one loop, not three

    def test_label_list_unrolls_one_call_each(self):
        out = _lower('self.draw = DrawText(["a", "b"], np.zeros((2, 3)))\n')
        self.assertEqual(2, out.count("data.emitText("))
        self.assertIn('MString("a")', out)
        self.assertIn('MString("b")', out)

    def test_label_count_is_guarded_against_the_positions(self):
        """DrawText raises on a count mismatch; a compiled node cannot, so it
        must draw nothing rather than read past the array."""
        out = _lower('self.draw = DrawText(["a", "b"], np.zeros((2, 3)))\n')
        self.assertRegex(out, r"if \(_ndRows\(\w+\) == 2\)")

    def test_default_size_is_half_a_unit(self):
        """DrawText.__init__ defaults size=0.5."""
        out = _lower('self.draw = DrawText("x", (0.0, 0.0, 0.0))\n')
        self.assertIn("nd::scalar<double>(0.5)", out)

    def test_non_string_constants_are_str_ed(self):
        """draw_types._strings runs str() over non-string entries."""
        out = _lower('self.draw = DrawText([1, 2], np.zeros((2, 3)))\n')
        self.assertIn('MString("1")', out)
        self.assertIn('MString("2")', out)

    def test_quotes_and_backslashes_are_escaped(self):
        out = _lower('self.draw = DrawText(\'a"b\\\\c\', (0.0, 0.0, 0.0))\n')
        self.assertIn(r'MString("a\"b\\c")', out)


class TestStringPlugLabels(unittest.TestCase):
    """A string INPUT plug is a RUNTIME std::string, and draw_types._strings
    treats a bare string as exactly ONE label broadcast across every position --
    the same loop the single-constant case emits, so no string-array type is
    needed. Parity-verified in tools/probe_locator_parity.py (p_str_plug)."""

    _STR_IN = {"label": {"type": "string", "is_array": False,
                         "default_value": "hi"}}

    def test_string_plug_binds_as_a_std_string(self):
        out = _lower("self.draw = DrawText(self.label, np.zeros((2, 3)))\n",
                     inputs=self._STR_IN)
        self.assertIn("in_label.asChar()", out)

    def test_runtime_label_broadcasts_over_every_position(self):
        out = _lower("self.draw = DrawText(self.label, np.zeros((2, 3)))\n",
                     inputs=self._STR_IN)
        self.assertRegex(out, r"for \(int64_t \w+ = 0; \w+ < _ndRows\(")
        self.assertEqual(1, out.count("data.emitText("))   # one loop, not two
        self.assertIn(".c_str()", out)

    def test_concatenated_runtime_label_lowers(self):
        """str + str is already a lowered operation; the result is still ONE
        label."""
        out = _lower('self.draw = DrawText("f " + self.label, '
                     "np.zeros((2, 3)))\n", inputs=self._STR_IN)
        self.assertEqual(1, out.count("data.emitText("))
        self.assertIn("in_label.asChar()", out)

    def test_a_string_plug_the_draw_never_reads_is_not_bound(self):
        out = _lower("self.draw = DrawCircle(center=(0.0, 0.0, 0.0))\n",
                     inputs=self._STR_IN)
        self.assertNotIn("in_label", out)

    def test_string_array_plug_is_a_runtime_label_list(self):
        """A string ARRAY input now lifts to the same `strv` carrier that
        list(<str>) produces, so it reaches the RUNTIME label-list branch below
        instead of rejecting. Same carrier, same emitted shape -- the only thing
        that changed is that the labels can come from a plug."""
        spec = _spec("self.draw = DrawText(self.labels, np.zeros((2, 3)))\n",
                     inputs={"labels": {"type": "string", "is_array": True}})
        lines = nd_lower.try_lower_locator(spec)
        self.assertIsNotNone(lines)
        out = "\n".join(lines)
        self.assertIn("std::vector<std::string> ndin_self_labels", out)
        # The two _strings(value, n) cases, as a RUNTIME branch.
        self.assertIn(".size() == 1 &&", out)
        self.assertEqual(2, out.count("data.emitText("))

    def test_non_string_runtime_text_rejects(self):
        spec = _spec("self.draw = DrawText(np.zeros(3), np.zeros((3, 3)))\n")
        self.assertIsNone(nd_lower.try_lower_locator(spec))


class TestRuntimeLabelList(unittest.TestCase):
    """list(<str>) is a RUNTIME label list -- the count is known only at draw
    time, so both _strings(value, n) cases become a runtime branch. Parity-
    verified in tools/probe_locator_parity.py (p_str_chars / p_str_broadcast)."""

    _STR_IN = {"label": {"type": "string", "is_array": False,
                         "default_value": "hi"}}

    def _out(self):
        return _lower("chars = list(self.label)\n"
                      "n = len(chars)\n"
                      "pts = np.zeros((n, 3))\n"
                      "self.draw = DrawText(chars, pts)\n",
                      inputs=self._STR_IN)

    def test_labels_split_by_code_point(self):
        self.assertIn("nd::str_chars(", self._out())

    def test_length_drives_the_position_array(self):
        """n = len(chars) must be the vector size, not a compile-time guess."""
        self.assertRegex(self._out(), r"\(int64_t\)\w+\.size\(\)")

    def test_one_entry_list_broadcasts_and_equal_counts_pair_up(self):
        out = self._out()
        self.assertRegex(out, r"if \(\(int64_t\)\w+\.size\(\) == 1 && \w+ > 1\)")
        self.assertRegex(out, r"else if \(\(int64_t\)\w+\.size\(\) == \w+\)")
        self.assertEqual(2, out.count("data.emitText("))

    def test_mismatched_counts_draw_nothing(self):
        """DrawText raises on a mismatch; a compiled node cannot, so neither
        runtime branch may fire."""
        out = self._out()
        self.assertNotIn("} else {", out)


class TestWallClock(unittest.TestCase):
    """`time.time()` binds to the scaffold's per-frame wallClock -- system_clock
    epoch seconds since recipe 30, the same origin as the interpreted node, so
    the compiled gizmo runs the same motion at the same phase."""

    _INIT = "import time as _wall\n"

    def _spec_hover(self, compute, init=None, hover=True):
        spec = _spec(compute, init=self._INIT if init is None else init)
        spec["needs_hover"] = hover
        return spec

    def test_aliased_time_binds_the_wall_clock(self):
        out = "\n".join(nd_lower.try_lower_locator(self._spec_hover(
            "self.auto_refresh = True\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0),\n"
            "                       radius=1.0 + _wall.time())\n")) or [])
        self.assertIn("= wallClock;", out)

    def test_unaliased_import_time_also_binds(self):
        out = "\n".join(nd_lower.try_lower_locator(self._spec_hover(
            "self.auto_refresh = True\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0),\n"
            "                       radius=time.time())\n",
            init="import time\n")) or [])
        self.assertIn("= wallClock;", out)

    def test_without_needs_hover_it_rejects(self):
        """wallClock is pinned to 0.0 unless the node is needs_hover, which
        would freeze the compiled gizmo while the interpreted one animates."""
        self.assertIsNone(nd_lower.try_lower_locator(self._spec_hover(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0),\n"
            "                       radius=_wall.time())\n", hover=False)))

    def test_an_unimported_alias_is_not_a_clock(self):
        self.assertIsNone(nd_lower.try_lower_locator(self._spec_hover(
            "self.auto_refresh = True\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0),\n"
            "                       radius=_wall.time())\n", init="")))

    def test_other_time_module_calls_still_reject(self):
        """Only time.time() is bound; time.sleep() has no compiled form."""
        self.assertIsNone(nd_lower.try_lower_locator(self._spec_hover(
            "self.auto_refresh = True\n"
            "_wall.sleep(1)\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0)\n")))


class TestWallclockSlot(unittest.TestCase):
    """``self.wallclock`` is the framework's animation clock (epoch seconds,
    identical in both paths). It is a draw-context read bound to the same
    scaffold ``wallClock`` that ``time.time()`` lowers to, and -- like it --
    needs the live-clock service, which the extractor flags automatically."""

    def _spec_hover(self, compute, hover=True):
        spec = _spec(compute)
        spec["needs_hover"] = hover
        return spec

    def test_self_wallclock_binds_the_wall_clock(self):
        out = "\n".join(nd_lower.try_lower_locator(self._spec_hover(
            "self.auto_refresh = True\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0),\n"
            "                       radius=1.0 + self.wallclock)\n")) or [])
        self.assertIn("(double)(wallClock)", out)

    def test_without_needs_hover_it_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(self._spec_hover(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0),\n"
            "                       radius=self.wallclock)\n", hover=False)))

    def test_the_extractor_flags_it_as_needing_the_live_clock(self):
        from mpynode.native.spec.spec_extractor import detect_needs_hover
        self.assertTrue(detect_needs_hover(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=self.wallclock)\n"))
        self.assertFalse(detect_needs_hover(
            "# self.wallclock only in a comment\nself.draw = None\n"))


class TestCppStringLiteral(unittest.TestCase):
    """The escaper feeding MString(...)."""

    def test_plain_ascii(self):
        self.assertEqual('"hello"', locator_draw_cpp._cpp_string("hello"))

    def test_escapes(self):
        self.assertEqual(r'"a\"b\\c\nd"',
                         locator_draw_cpp._cpp_string('a"b\\c\nd'))

    def test_non_ascii_becomes_utf8_bytes(self):
        self.assertEqual(r'"\xc3\xa9"', locator_draw_cpp._cpp_string("é"))

    def test_hex_escape_does_not_swallow_the_next_digit(self):
        """A C++ hex escape is GREEDY -- "\\xc3\\xa9a" would parse the trailing
        'a' into the byte. The literal must split instead."""
        got = locator_draw_cpp._cpp_string("éa")
        self.assertEqual(r'"\xc3\xa9" "a"', got)
        self.assertNotEqual(r'"\xc3\xa9a"', got)


class TestLocatorRejects(unittest.TestCase):
    """No compiled form -> None, so the caller keeps the PORT region.

    A wrong lowering draws the wrong gizmo silently; an honest reject only
    costs the AI porter.
    """

    def test_undeclared_text_attr_rejects(self):
        """A runtime label is lowerable ONLY when it comes from a declared plug;
        an attr the node never declares cannot be bound at all."""
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "self.draw = DrawText(self.label, (0.0, 0.0, 0.0))\n"),
            ))

    def test_label_list_from_a_non_string_rejects(self):
        """list() lowers only over a string; the elements of a numeric array
        would need Python's repr to become labels."""
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "chars = list(np.zeros(3))\n"
            "self.draw = DrawText(chars, np.zeros((3, 3)))\n")))

    def test_screen_space_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0,\n"
            "                       screen_space=True)\n")))

    def test_non_local_space_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), space='world')\n")))

    def test_unknown_self_attr_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), "
            "radius=self.nope)\n")))

    def test_empty_compute_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec("")))
        self.assertIsNone(nd_lower.try_lower_locator(_spec("   \n")))


class TestInterpretedParityRules(unittest.TestCase):
    """Rules the compiled draw MUST share with draw_types, each pinned because
    it diverged once. A clean compile does not catch either of these -- only
    comparing the interpreted buffers against the compiled ones does."""

    def test_bare_3_vector_is_one_point_not_three(self):
        """draw_types._points promotes a bare (3,) to (1,3). If the C++ row
        count uses shape[0] blindly, one circle draws as THREE."""
        self.assertIn("a.ndim() == 1 ? 1 : a.shape[0]",
                      locator_draw_cpp.DRAW_LOWER_HELPERS)

    def test_filled_defaults_to_false(self):
        """DrawPrimitive.__init__ defaults filled=False."""
        out = _lower("self.draw = DrawSphere(center=(0.0, 0.0, 0.0), "
                     "radius=1.0)\n")
        self.assertRegex(out, r"data\.emitShape\([^;]*,\s*false\);")

    def test_explicit_filled_is_honoured(self):
        out = _lower("self.draw = DrawSphere(center=(0.0, 0.0, 0.0), "
                     "radius=1.0, filled=True)\n")
        self.assertRegex(out, r"data\.emitShape\([^;]*,\s*true\);")

    def test_default_axis_matches_each_ctor(self):
        """DrawCircle defaults axis=+Z; the other primitives default +Y."""
        circle = _lower("self.draw = DrawCircle(center=(0.0, 0.0, 0.0))\n")
        sphere = _lower("self.draw = DrawSphere(center=(0.0, 0.0, 0.0))\n")
        self.assertIn("0.0, 0.0, 1.0", circle)
        self.assertIn("0.0, 1.0, 0.0", sphere)

    def test_uncoloured_mesh_is_white_not_the_struct_default(self):
        """_flush_polygons falls back to face_colors = normalize_color(None, n),
        i.e. WHITE. DrawPoly's own default is grey (0.5), which the AI-porter
        path relies on -- so the lowering must state white explicitly or an
        uncoloured mesh compiles grey and interprets white."""
        out = _lower(
            "pts = np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]])\n"
            "self.draw = DrawMesh(pts, np.array([4]), np.array([0,1,2,3]))\n")
        self.assertIn("colorMode = 0;", out)
        self.assertIn("_ndColor(nd::Array<double>(), false, 0)", out)

    def test_uniform_color_kwarg_is_one_setcolor(self):
        """color= is a per-FACE table; uniform_color= is the single-setColor
        fast path. They must not collapse into each other."""
        out = _lower(
            "pts = np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]])\n"
            "self.draw = DrawMesh(pts, np.array([4]), np.array([0,1,2,3]),\n"
            "                     uniform_color=(0.3, 0.6, 0.9, 0.5))\n")
        self.assertIn("colorMode = 0;", out)

    def test_per_face_colour_table_keeps_its_mode(self):
        out = _lower(
            "pts = np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]])\n"
            "fc = np.array([[1.,0.,0.,1.]])\n"
            "self.draw = DrawMesh(pts, np.array([4]), np.array([0,1,2,3]),\n"
            "                     color=fc)\n")
        self.assertIn("colorMode = 1;", out)
        self.assertIn("faceColors", out)

    def test_missing_colour_is_white(self):
        """normalize_color(None, n) is white, not black."""
        self.assertIn("if (!has) return MColor(1.0f, 1.0f, 1.0f, 1.0f);",
                      locator_draw_cpp.DRAW_LOWER_HELPERS)


class TestInitTabConstants(unittest.TestCase):
    """A compute may read an Init-tab module constant as a bare name.

    Folded LAZILY at each use by py_to_cpp.ex_Name, so a constant the
    transpiler cannot express costs nothing until something reads it.
    Parity-verified in tools/probe_locator_parity.py (p_init_*).
    """

    def test_scalar_constant_folds(self):
        out = _lower(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=TWO_PI)\n",
            init="TWO_PI = 6.283185307179586\n")
        self.assertIn("6.28318", out)

    def test_numeric_tuple_constant_folds(self):
        out = _lower(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), color=WIRE)\n",
            init="WIRE = (0.04, 0.05, 0.06, 1.0)\n")
        self.assertIn("0.04", out)

    def test_np_array_literal_constant_folds(self):
        out = _lower(
            "self.draw = DrawMesh(PTS, CNT, IDX)\n",
            init="import numpy as np\n"
                 "PTS = np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]])\n"
                 "CNT = np.array([4])\n"
                 "IDX = np.array([0, 1, 2, 3])\n")
        self.assertIn("nd::from_data", out)
        self.assertIn("data.emitPoly()", out)

    def test_constant_may_reference_another_constant(self):
        out = _lower(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=OUTER)\n",
            init="BASE = 2.0\nOUTER = BASE * 3.0\n")
        self.assertIn("data.emitShape(", out)

    def test_init_def_may_read_an_init_constant(self):
        """Helper bodies share the same _HelperCtx, so they see consts too."""
        out = _lower(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=scaled(1.5))\n",
            init="GAIN = 2.5\n\n\ndef scaled(x):\n    return x * GAIN\n")
        self.assertIn("data.emitShape(", out)

    def test_drawtext_labels_from_an_init_constant(self):
        out = _lower(
            "self.draw = DrawText(LABELS, np.zeros((2, 3)))\n",
            init='LABELS = ["a", "b"]\n')
        self.assertIn('MString("a")', out)
        self.assertIn('MString("b")', out)

    def test_compute_local_shadows_the_constant(self):
        """env is consulted before the const fold, so a compute-local rebind
        wins -- and a node that lowers today cannot start rejecting because an
        Init name happens to collide."""
        out = _lower(
            "TWO_PI = 1.0\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=TWO_PI)\n",
            init="TWO_PI = 6.283185307179586\n")
        self.assertIn("data.emitShape(", out)
        self.assertNotIn("6.28318", out)

    def test_unreferenced_untranspilable_constant_costs_nothing(self):
        """The fold is LAZY: an Init constant the transpiler cannot express
        must not sink a node that never reads it."""
        out = _lower(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0)\n",
            init="import numpy as np\nCACHE = {}\nGRID = np.meshgrid([1], [2])\n")
        self.assertIn("data.emitShape(", out)

    def test_referencing_an_untranspilable_constant_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=CACHE)\n",
            init="CACHE = {}\n")))

    def test_twice_assigned_constant_is_not_folded(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=R)\n",
            init="R = 1.0\nR = 2.0\n")))

    def test_self_referential_constant_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=R)\n",
            init="R = R + 1.0\n")))


_ENUM_IN = {"shapeMode": {"type": "enum", "is_array": False,
                          "default_value": 1,
                          "enum_names": ["sphere", "box", "circle"]}}


class TestEnumNameDispatch(unittest.TestCase):
    """`self.<enum>.name()` -> the scaffold's own in_<plug>_name std::string.

    Rewritten to a synthetic self-attr rather than taught to the type system:
    the transpiler still has no notion of enum-ness. Parity-verified in
    tools/probe_locator_parity.py (p_enum_name).
    """

    def test_enum_name_binds_the_scaffold_local(self):
        out = _lower(
            'mode = self.shapeMode.name()\n'
            'if mode == "box":\n'
            "    self.draw = DrawBox(center=(0.0, 0.0, 0.0))\n"
            "else:\n"
            "    self.draw = DrawCircle(center=(0.0, 0.0, 0.0))\n",
            inputs=_ENUM_IN)
        self.assertIn("in_shapeMode_name", out)
        self.assertIn("data.emitShape(2,", out)   # box
        self.assertIn("data.emitShape(1,", out)   # circle

    def test_enum_name_compares_as_a_string(self):
        out = _lower(
            'self.auto_refresh = self.shapeMode.name() == "box"\n'
            "self.draw = None\n",
            inputs=_ENUM_IN)
        self.assertIn("in_shapeMode_name", out)

    def test_name_on_a_non_enum_input_still_rejects(self):
        """The rewrite is keyed on the plug being a declared ENUM -- it must not
        swallow .name() on anything else."""
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            'm = self.radius.name()\n'
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=1.0)\n",
            inputs={"radius": {"type": "float", "is_array": False,
                               "default_value": 1.0}})))

    def test_node_without_enum_inputs_is_untouched(self):
        """No enum plugs -> the rewrite returns the source verbatim."""
        src = "self.draw = DrawCircle(center=(0.0, 0.0, 0.0))\n"
        out, used = nd_lower._rewrite_loc_enum_names(src, set())
        self.assertEqual(src, out)
        self.assertEqual(set(), used)

    def test_rewrite_reports_the_plugs_it_used(self):
        out, used = nd_lower._rewrite_loc_enum_names(
            "m = self.shapeMode.name()\n", {"shapeMode"})
        self.assertEqual({"shapeMode"}, used)
        self.assertIn("self.__nd_enumname_shapeMode", out)
        self.assertNotIn(".name()", out)


class TestGetattrFold(unittest.TestCase):
    """getattr(self, '<name>', <default>): presence is a COMPILE-TIME fact.

    Parity-verified in tools/probe_locator_parity.py (p_getattr_has /
    p_getattr_missing).
    """

    _RADIUS_IN = {"radius": {"type": "float", "is_array": False,
                             "default_value": 3.0}}

    def test_declared_attr_folds_to_the_read_not_the_default(self):
        """The bug this pins: getattr does not syntactically read self.radius,
        so unless the name is collected the plug is never materialised and the
        call folds to the DEFAULT -- compiles clean, draws the wrong size."""
        out = _lower(
            'r = getattr(self, "radius", 0.25)\n'
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r)\n",
            inputs=self._RADIUS_IN)
        self.assertIn("in_radius", out)
        self.assertNotIn("0.25", out)

    def test_undeclared_name_folds_to_the_default(self):
        out = _lower(
            'r = getattr(self, "notDeclared", 0.25)\n'
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r)\n")
        self.assertIn("0.25", out)
        self.assertIn("data.emitShape(", out)

    def test_two_arg_getattr_rejects(self):
        """Python's 2-arg form RAISES when the attribute is missing, and a
        compiled node cannot raise."""
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            'r = getattr(self, "radius")\n'
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r)\n",
            inputs=self._RADIUS_IN)))

    def test_non_constant_name_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            'nm = "radius"\n'
            'r = getattr(self, nm, 0.25)\n'
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=r)\n",
            inputs=self._RADIUS_IN)))

    def test_declared_string_array_plug_is_bound_not_folded_to_the_default(self):
        """A locator declares a string ARRAY input and reads it via getattr.

        This used to REJECT, because a string array had no liftable kind. It now
        lifts to `strv`, so the invariant flips from "reject" to "bind": what
        must never happen is getattr treating a DECLARED plug as absent and
        folding to the default, which would silently ignore a plug the user
        wired up and always draw the fallback. Assert the plug is read."""
        lines = nd_lower.try_lower_locator(_spec(
            'raw = getattr(self, "displayText", "")\n'
            "self.draw = DrawText(raw, (0.0, 0.0, 0.0))\n",
            inputs={"displayText": {"type": "string", "is_array": True,
                                    "default_value": ""}}))
        self.assertIsNotNone(lines)
        out = "\n".join(lines)
        self.assertIn("ndin_self_displayText", out)
        self.assertIn("in_a_displayText", out)

    def test_context_read_through_getattr(self):
        out = _lower(
            'f = getattr(self, "time", 0.0)\n'
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=f)\n")
        self.assertIn("ndin_self_time", out)


class TestUsedSelfAttrCollection(unittest.TestCase):
    """nd_lower._used_self_attrs -- the string-named forms are opt-in."""

    def test_dot_access_always_collected(self):
        self.assertEqual({"radius"},
                         nd_lower._used_self_attrs("x = self.radius\n"))

    def test_string_named_ignored_without_a_declared_set(self):
        """Callers that have not opted in must be byte-identical to before."""
        self.assertEqual(
            set(), nd_lower._used_self_attrs('x = getattr(self, "r", 1.0)\n'))

    def test_string_named_collected_when_declared(self):
        self.assertEqual(
            {"r"},
            nd_lower._used_self_attrs('x = getattr(self, "r", 1.0)\n', {"r"}))

    def test_undeclared_string_name_stays_out(self):
        """Otherwise it would fail the allowlist instead of folding to the
        default."""
        self.assertEqual(
            set(),
            nd_lower._used_self_attrs('x = getattr(self, "nope", 1.0)\n', {"r"}))

    def test_hasattr_is_collected_too(self):
        self.assertEqual(
            {"r"}, nd_lower._used_self_attrs('x = hasattr(self, "r")\n', {"r"}))


class TestInitConstantWriteGuards(unittest.TestCase):
    """A folded constant is an RVALUE. Writing through it would either not
    compile or -- worse -- write into a temporary that is discarded at the end
    of the statement, while the interpreted node mutates the real module-level
    object and KEEPS it across compute calls. Both must reject."""

    def test_subscript_store_into_a_constant_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "PTS[0] = 5.0\n"
            "self.draw = DrawMesh(PTS, CNT, IDX)\n",
            init="import numpy as np\n"
                 "PTS = np.array([[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.]])\n"
                 "CNT = np.array([4])\n"
                 "IDX = np.array([0, 1, 2, 3])\n")))

    def test_aug_assign_to_a_constant_rejects(self):
        self.assertIsNone(nd_lower.try_lower_locator(_spec(
            "TWO_PI += 1.0\n"
            "self.draw = DrawCircle(center=(0.0, 0.0, 0.0), radius=TWO_PI)\n",
            init="TWO_PI = 6.283185307179586\n")))


class TestModuleConstCollector(unittest.TestCase):
    """py_to_cpp._parse_module_consts -- what counts as a module constant."""

    def _consts(self, src):
        return set(py_to_cpp._parse_module_consts(src))

    def test_top_level_single_assignment(self):
        self.assertEqual({"A"}, self._consts("A = 1.0\n"))

    def test_function_local_is_not_a_module_constant(self):
        """The distinction that makes this its own collector: a name bound
        inside a def is that function's local, and folding it into a compute
        would substitute an unrelated value."""
        self.assertEqual(set(), self._consts("def f():\n    x = 5\n    return x\n"))

    def test_twice_assigned_is_dropped(self):
        self.assertEqual(set(), self._consts("A = 1.0\nA = 2.0\n"))

    def test_name_also_bound_inside_a_def_is_dropped(self):
        self.assertEqual(set(), self._consts(
            "A = 1.0\n\n\ndef f():\n    A = 2.0\n    return A\n"))

    def test_loop_target_is_dropped(self):
        self.assertEqual(set(), self._consts("for A in range(3):\n    pass\n"))

    def test_def_and_arg_names_are_dropped(self):
        got = self._consts("def f(x):\n    return x\n")
        self.assertNotIn("f", got)
        self.assertNotIn("x", got)

    def test_unparsable_source_is_skipped(self):
        self.assertEqual(set(), self._consts("this is not python!!\n"))

    def test_accepts_a_list_of_sources(self):
        self.assertEqual({"A", "B"}, self._consts(["A = 1.0\n", "B = 2.0\n"]))


class TestOtherNodeTypesUnaffected(unittest.TestCase):
    """const_source is opt-in. Every lowerer except the locator passes none, so
    _HelperCtx.consts stays empty and the fold + write guards no-op."""

    def test_helper_ctx_defaults_to_no_consts(self):
        ctx = py_to_cpp._HelperCtx({})
        self.assertEqual({}, ctx.consts)

    def test_helper_source_alone_does_not_expose_constants(self):
        """The Init source reaches EVERY lowerer as helper_source. Only the
        separate const_source opt-in may fold it -- otherwise this change would
        silently alter deformer / mesh / transform / iksolver lowering."""
        from mpynode.native.compiler.errors import UnsupportedSpec

        env = {"self.inValue": py_to_cpp.scalar_t("double")}
        writers = {"self.outValue": lambda v: ["    out = %s;" % v.code]}
        src = "self.outValue = self.inValue * TWO_PI\n"
        init = "TWO_PI = 6.28\n"

        with self.assertRaises(UnsupportedSpec):
            py_to_cpp.transpile_compute_block(src, env, writers, init)

        res, _written, _helpers = py_to_cpp.transpile_compute_block(
            src, env, writers, init, const_source=init)
        self.assertIn("6.28", "\n".join(res.all_lines()))


class TestGeneratedLocatorCpp(unittest.TestCase):
    """End of the pipe: does the emitted node actually drop the PORT region?"""

    def _cpp(self, compute, inputs=None):
        from mpynode.native import compiler as codegen
        return codegen._generate_locator_cpp({
            "schema_version": 1, "source_node": "loc1", "mpy_type": "mPyLocator",
            "suggested": {"node_type_name": "lowerTest", "class_name": "LowerTest",
                          "type_id": "0x00070c01", "mpx_base": "MPxLocatorNode",
                          "note": "", "heaviness": "hard"},
            "inputs": inputs or {}, "outputs": {}, "variables": {},
            "compute": compute, "init": "", "affects": "all",
            "portability": {"portable": True, "blockers": []}, "commands": [],
        }, for_port=True)

    def test_lowered_locator_has_no_port_region(self):
        from mpynode.native.compiler.spec_model import PORT_BEGIN
        cpp = self._cpp("self.draw = DrawCircle(center=(0.0, 0.0, 0.0), "
                        "radius=2.0)\n")
        self.assertNotIn(PORT_BEGIN, cpp)
        self.assertIn("data.emitShape(", cpp)

    def test_rejected_locator_keeps_the_port_region(self):
        from mpynode.native.compiler.spec_model import PORT_BEGIN, PORT_END
        cpp = self._cpp("self.draw = DrawCircle(center=(0.0, 0.0, 0.0), "
                        "screen_space=True)\n")
        self.assertIn(PORT_BEGIN, cpp)
        self.assertIn(PORT_END, cpp)

    def test_string_input_default_is_baked_into_the_inputs_pod(self):
        """Every other input type seeds the POD with the plug DEFAULT; a string
        left it empty, so a failed findPlug (and the standalone parity probe)
        saw "" instead of the authored default."""
        cpp = self._cpp("self.draw = DrawText(self.label, np.zeros((2, 3)))\n",
                        inputs={"label": {"type": "string", "is_array": False,
                                          "default_value": "hi"}})
        self.assertIn('MString in_label = "hi";', cpp)

    def test_lowered_locator_carries_the_draw_helpers(self):
        cpp = self._cpp("self.draw = DrawCircle(center=(0.0, 0.0, 0.0))\n")
        self.assertIn("static inline int64_t _ndRows(", cpp)
        self.assertIn("namespace nd", cpp)

    def test_lowered_guard_header_is_visible_to_the_probe(self):
        """lowered_guard's handler calls MGlobal::displayError from
        computeBuffers, which the -DMPYNODE_PROBE translation unit compiles
        too, so maya/MGlobal.h cannot stay behind the plugin-only guard."""
        cpp = self._cpp("self.draw = DrawCircle(center=(0.0, 0.0, 0.0))\n")
        self.assertIn("MGlobal::displayError", cpp)
        self.assertLess(cpp.index("#include <maya/MGlobal.h>"),
                        cpp.index("#ifndef MPYNODE_PROBE"),
                        "the probe compiles computeBuffers -- MGlobal.h must "
                        "not be plugin-only")
        self.assertEqual(1, cpp.count("#include <maya/MGlobal.h>"),
                         "moved, not duplicated")

    def test_an_ai_ported_locator_keeps_MGlobal_plugin_only(self):
        """Nothing outside the plugin scaffold calls MGlobal when the draw did
        NOT lower, so that frag must stay byte-identical."""
        cpp = self._cpp("self.draw = DrawCircle(center=(0.0, 0.0, 0.0), "
                        "screen_space=True)\n")
        self.assertLess(cpp.index("#ifndef MPYNODE_PROBE"),
                        cpp.index("#include <maya/MGlobal.h>"))


if __name__ == "__main__":
    unittest.main()
