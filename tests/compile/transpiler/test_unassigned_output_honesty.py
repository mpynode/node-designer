"""An output the Python never assigns must not be invented, masked, or misnamed.

The kDTree case that motivated this: the compute writes one output but the node
declares three.

    pts = self.inMesh.points[:, :3]
    queries = self.queries
    if len(pts) and len(queries):
        d, idx = cKDTree(pts).query(queries, k=1)
        self.output = pts[idx]

``d`` and ``idx`` are computed and DISCARDED, yet ``distance`` and
``closestIndex`` are declared outputs. Three separate links then failed:

1. the PORT scaffold told the model to "populate std::vector out_aDistance"
   AND to "translate faithfully" -- contradictory instructions, which it
   resolved by harvesting the discarded locals. That is a scaffold defect, not
   a model failure;
2. the resulting length divergence (Python 0, compiled 4) was swallowed by the
   wired-geometry SKIP guard, whose stated cause -- "the interpreted reference
   could not evaluate the synthesized geometry headlessly" -- was true but not
   the whole truth. That guard would mask this class on EVERY run of a node
   shaped like this;
3. the hand-off then asked the assistant to "get it compiling" for a node whose
   build_status was already ``compiled``.
"""

from __future__ import annotations

import unittest

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


KDTREE_COMPUTE = (
    "pts = self.inMesh.points[:, :3]\n"
    "queries = self.queries\n"
    "\n"
    "if len(pts) and len(queries):\n"
    "    d, idx = cKDTree(pts).query(queries, k=1)\n"
    "    self.output = pts[idx]\n"
)


class TestScaffoldNamesTheUnassignedOutputs(unittest.TestCase):
    """Fix 1 -- the scaffold must stop asking for values the Python never
    produces."""

    def test_an_output_the_compute_never_assigns_is_reported(self):
        from mpynode.native.compiler import emit_compute

        unassigned = emit_compute.unassigned_output_plugs(
            ["output", "distance", "closestIndex"], KDTREE_COMPUTE)

        self.assertEqual(unassigned, {"distance", "closestIndex"})

    def test_a_subscript_or_augmented_write_counts_as_assigned(self):
        from mpynode.native.compiler import emit_compute

        src = ("self.a[0] = 1.0\n"
               "self.b += 2.0\n"
               "for self.c in range(3):\n"
               "    pass\n")
        unassigned = emit_compute.unassigned_output_plugs(
            ["a", "b", "c", "d"], src)

        self.assertEqual(unassigned, {"d"})

    def test_an_unparseable_compute_claims_nothing(self):
        """Guessing wrong in THIS direction tells the model to leave a real
        output untouched, which is worse than the bug being fixed."""
        from mpynode.native.compiler import emit_compute

        unassigned = emit_compute.unassigned_output_plugs(
            ["output"], "this is ( not python")

        self.assertEqual(unassigned, set())

    def test_tuple_unpacking_counts_as_assigned(self):
        """``self.a, self.b = f()`` is the single most likely way to write two
        outputs at once -- and missing it points the model at a REAL output and
        tells it to leave that one empty, which is the opposite of the fix."""
        from mpynode.native.compiler import emit_compute

        src = ("self.output, self.distance = solve()\n"
               "[self.extra], = [[1.0]]\n")
        unassigned = emit_compute.unassigned_output_plugs(
            ["output", "distance", "extra", "other"], src)

        self.assertEqual(unassigned, {"other"})

    def test_a_starred_target_counts_as_assigned(self):
        from mpynode.native.compiler import emit_compute

        unassigned = emit_compute.unassigned_output_plugs(
            ["head", "rest"], "self.head, *self.rest = values\n")

        self.assertEqual(unassigned, set())

    def test_a_setattr_on_self_makes_the_answer_untrustworthy(self):
        """The name is computed, so no static scan can see it. Claiming nothing
        is the safe direction."""
        from mpynode.native.compiler import emit_compute

        unassigned = emit_compute.unassigned_output_plugs(
            ["output", "distance"],
            "setattr(self, 'dist' + 'ance', 1.0)\n"
            "self.output = 2.0\n")

        self.assertEqual(unassigned, set())

    def test_a_setattr_on_something_else_is_not_a_reason_to_give_up(self):
        from mpynode.native.compiler import emit_compute

        unassigned = emit_compute.unassigned_output_plugs(
            ["output", "distance"],
            "setattr(cfg, 'mode', 1)\n"
            "self.output = 2.0\n")

        self.assertEqual(unassigned, {"distance"})

    def test_self_escaping_into_a_call_makes_the_answer_untrustworthy(self):
        """``solve(self)`` can write any output from a helper we cannot see, and
        neither can ``self.helper()``. Both must silence the scan rather than
        report every output as unassigned."""
        from mpynode.native.compiler import emit_compute

        for src in ("solve(self)\n",
                    "self.helper()\n",
                    "out = compute(self, 3)\n"):
            self.assertEqual(
                emit_compute.unassigned_output_plugs(["output"], src), set(),
                "self escaped into a call in %r" % src)

    def test_reading_through_self_is_not_an_escape(self):
        """``self.inMesh.getPoints()`` is a call on an ATTRIBUTE, not on self --
        treating it as an escape would silence the scan for almost every node."""
        from mpynode.native.compiler import emit_compute

        unassigned = emit_compute.unassigned_output_plugs(
            ["output", "distance"],
            "pts = self.inMesh.points[:, :3]\n"
            "self.output = len(pts)\n")

        self.assertEqual(unassigned, {"distance"})

    def test_an_empty_compute_claims_nothing(self):
        """Parses fine and assigns nothing -- but a node with no compute is not
        a node that 'refuses to write its outputs'."""
        from mpynode.native.compiler import emit_compute

        self.assertEqual(
            emit_compute.unassigned_output_plugs(["output"], ""), set())

    def _region(self, name, compute):
        """The PORT region of a 2-array-output node built from ``compute``."""
        from mpynode.native import compiler as codegen
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name=name + "#")
        w.add_input_attr("queries", "vector", is_array=True)
        w.add_output_attr("output", "vector", is_array=True)
        w.add_output_attr("distance", "float", is_array=True)
        w.set_compute_expression(compute)
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = name + "Probe"

        cpp = codegen.generate_cpp(spec, for_port=True)
        self.assertIn(codegen.PORT_BEGIN, cpp,
                      "this probe must reach the AI porter to be meaningful")
        return cpp.split(codegen.PORT_BEGIN, 1)[1].split(codegen.PORT_END, 1)[0]

    PARTIAL = ("if len(self.queries):\n"
               "    self.output = [[0.0, 0.0, 0.0] for _ in self.queries]\n")
    FULL = ("if len(self.queries):\n"
            "    self.output = [[0.0, 0.0, 0.0] for _ in self.queries]\n"
            "    self.distance = [0.0 for _ in self.queries]\n")

    def test_the_port_scaffold_says_leave_it_untouched(self):
        region = self._region("kdScaffold", self.PARTIAL)

        populate = [l for l in region.splitlines() if "populate" in l]
        self.assertTrue(any("out_aOutput" in l for l in populate))
        self.assertFalse(any("out_aDistance" in l for l in populate),
                         "asking for it and forbidding it is the contradiction "
                         "that produced the invented values")
        self.assertIn("untouched", region.lower(),
                      "the model must be TOLD not to invent the missing one")
        self.assertIn("out_aDistance", region,
                      "and told WHICH one, by buffer name")

    def test_a_skipped_SCALAR_output_is_named_by_the_symbol_that_exists(self):
        """Arrays get ``out_<member>``; a plain scalar output has no such buffer
        -- its write target is the handle ``h_<member>``. Naming a symbol that
        is not in the file sends the model looking for it (a shipped template,
        spine, has exactly this shape)."""
        from mpynode.native import compiler as codegen
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="kdScalarSrc#")
        w.add_input_attr("queries", "vector", is_array=True)
        w.add_output_attr("output", "vector", is_array=True)
        w.add_output_attr("total", "float")
        w.set_compute_expression(
            "if len(self.queries):\n"
            "    self.output = [[0.0, 0.0, 0.0] for _ in self.queries]\n")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "kdScalarProbe"

        cpp = codegen.generate_cpp(spec, for_port=True)
        region = cpp.split(codegen.PORT_BEGIN, 1)[1].split(codegen.PORT_END, 1)[0]
        skip = region.split("UNTOUCHED", 1)[1]

        self.assertIn("h_aTotal", skip)
        self.assertNotIn("out_aTotal", skip,
                         "no such buffer is declared for a scalar output")

    def test_a_node_that_assigns_everything_is_unchanged(self):
        region = self._region("kdAll", self.FULL)

        populate = [l for l in region.splitlines() if "populate" in l]
        self.assertTrue(any("out_aOutput" in l for l in populate))
        self.assertTrue(any("out_aDistance" in l for l in populate))
        self.assertNotIn("untouched", region.lower(),
                         "no unassigned outputs -> no extra instruction")


class TestVerifySeparatesInventedFromUnverifiable(unittest.TestCase):
    """Fix 2 -- the wired-geometry SKIP must not absorb a divergence we can
    explain statically."""

    def test_an_unassigned_output_is_its_own_reason(self):
        from mpynode.native.toolchain import verify

        reason = verify._count_mismatch_reason(
            "distance", 0, 4, geo_wired_any=True, unassigned={"distance"})

        self.assertIsNotNone(reason)
        ran, passed, text = reason
        self.assertTrue(ran, "we can explain this one, so it is a real verdict")
        self.assertFalse(passed)
        self.assertIn("never assigns", text)
        self.assertIn("distance", text)
        self.assertNotIn("headlessly", text,
                         "blaming the harness here is the masking that hid it")

    def test_the_geometry_skip_still_applies_to_an_assigned_output(self):
        from mpynode.native.toolchain import verify

        ran, passed, text = verify._count_mismatch_reason(
            "output", 0, 4, geo_wired_any=True, unassigned={"distance"})

        self.assertFalse(ran, "genuinely inconclusive -- the reference bailed")
        self.assertIsNone(passed)
        self.assertIn("headlessly", text)

    def test_no_geometry_wired_is_still_a_hard_fail(self):
        from mpynode.native.toolchain import verify

        ran, passed, text = verify._count_mismatch_reason(
            "output", 0, 4, geo_wired_any=False, unassigned=set())

        self.assertTrue(ran)
        self.assertFalse(passed)
        self.assertIn("element count differs", text)

    def test_both_sides_non_empty_is_still_a_hard_fail(self):
        from mpynode.native.toolchain import verify

        ran, passed, _text = verify._count_mismatch_reason(
            "output", 3, 4, geo_wired_any=True, unassigned=set())

        self.assertTrue(ran)
        self.assertFalse(passed)

    def test_an_empty_COMPILED_side_is_never_excused_by_the_geometry_clause(self):
        """Python 4 vs compiled 0 is the classic broken-port signature. The old
        ``min(na, nb) == 0`` was symmetric, so it skipped this direction AND
        narrated it as "the interpreted reference could not evaluate" -- the
        exact opposite of what happened."""
        from mpynode.native.toolchain import verify

        ran, passed, text = verify._count_mismatch_reason(
            "output", 4, 0, geo_wired_any=True, unassigned=set())

        self.assertTrue(ran, "the compiled node produced nothing -- that is a "
                             "result, not an inconclusive")
        self.assertFalse(passed)
        self.assertNotIn("interpreted reference could not", text)

    def test_the_verdict_is_wired_into_verify_one(self):
        import inspect

        from mpynode.native.toolchain import verify

        src = inspect.getsource(verify)
        self.assertIn("_count_mismatch_reason(", src)
        self.assertEqual(src.count("def _count_mismatch_reason"), 1)
        # The executable form, not the docstring that explains why it went.
        self.assertNotIn("and min(na, nb) == 0:", src,
                         "the symmetric test excused a broken port")

    def test_a_real_verdict_outranks_an_inconclusive_one(self):
        """``count_mismatch`` was a single slot overwritten on every hit across
        30 sweep iterations, so whichever output diverged LAST decided the
        verdict -- a benign geo-driven skip could bury a genuine failure."""
        from mpynode.native.toolchain import verify

        picked = verify._pick_count_verdict(
            {"output": (0, 4), "distance": (0, 4)},
            geo_wired_any=True, unassigned={"distance"})

        ran, passed, text = picked
        self.assertTrue(ran)
        self.assertFalse(passed)
        self.assertIn("distance", text)
        self.assertIn("never assigns", text)

    def test_picking_is_deterministic_when_every_mismatch_is_inconclusive(self):
        from mpynode.native.toolchain import verify

        a = verify._pick_count_verdict({"b": (0, 4), "a": (0, 2)},
                                       geo_wired_any=True, unassigned=set())
        b = verify._pick_count_verdict({"a": (0, 2), "b": (0, 4)},
                                       geo_wired_any=True, unassigned=set())

        self.assertEqual(a, b)
        self.assertFalse(a[0])


class TestHandoffNamesTheRealProblem(unittest.TestCase):
    """Fix 3 -- "get it compiling" is wrong for a node that compiled."""

    def _row(self, **kw):
        row = {"type_name": "kDTree", "source_node": "mPyNode1",
               "build_status": "compiled", "ported": True,
               "verify": {"ran": False, "reason": "inconclusive"}}
        row.update(kw)
        return row

    def _handoff(self, rows):
        from mpynode.ui.llm import compile_bridge

        return compile_bridge.build_handoff(
            {"nodes": rows, "plugin_name": "asses", "ok": True},
            options={"out_dir": "/tmp/asses"})

    def test_an_unverified_but_compiled_node_is_not_asked_to_compile(self):
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([self._row()]))

        self.assertNotIn("get it compiling", text.lower())
        self.assertIn("compiled", text)
        self.assertIn("could not be verified", text.lower())

    def test_a_node_that_did_not_build_still_asks_for_a_compile(self):
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([
            self._row(build_status="dropped", verify=None)]))

        self.assertIn("compil", text.lower())

    def test_a_measured_divergence_asks_for_parity_not_a_compile(self):
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([
            self._row(verify={"ran": True, "pass": False, "maxerr": 0.5})]))

        self.assertNotIn("get it compiling", text.lower())
        self.assertIn("diverge", text.lower())

    def test_the_worst_row_decides_when_a_run_has_several(self):
        """One node that did not build outranks another that merely went
        unverified -- the compile is the blocking problem."""
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([
            self._row(),
            self._row(type_name="other", build_status="dropped", verify=None)]))

        self.assertIn("compil", text.lower())

    def test_the_ask_talks_about_the_node_whose_failure_it_describes(self):
        """``primary_source_node`` is the FIRST flagged row; the shape is the
        WORST one. Mixing them asserts a measured divergence against a node that
        does not have one."""
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([
            self._row(),                                       # unverified
            self._row(type_name="other", source_node="mPyNode2",
                      verify={"ran": True, "pass": False, "maxerr": 0.5})]))

        self.assertIn("diverge", text.lower())
        head = text.split("[Compile report]", 1)[0]
        self.assertIn("mPyNode2", head)
        self.assertNotIn("`mPyNode1`", head,
                         "mPyNode1 has no measured divergence")

    def test_the_closing_goal_agrees_with_the_ask(self):
        """The block ended with a hardcoded "produce valid, compiling C++"
        paragraph, which contradicts an ask that says the node already compiles
        and must not be rewritten."""
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([self._row()]))
        goal = text.split("Goal:", 1)[1]

        self.assertNotIn("produce valid, compiling C++", goal)
        self.assertIn("verif", goal.lower())

    def test_the_closing_goal_for_an_unbuilt_node_is_unchanged(self):
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([
            self._row(build_status="dropped", verify=None)]))

        self.assertIn("produce valid, compiling C++", text)

    def test_the_unverified_ask_does_not_invite_a_rewrite_of_working_code(self):
        """With no measured divergence to chase, the likely failure mode is the
        assistant rewriting correct C++ against a phantom."""
        from mpynode.ui.llm import compile_bridge

        text = compile_bridge.starter_prompt(self._handoff([self._row()]))

        low = text.lower()
        self.assertTrue("why" in low or "before changing" in low
                        or "do not rewrite" in low,
                        "the ask must point at diagnosis first: %r" % text)


if __name__ == "__main__":
    unittest.main()
