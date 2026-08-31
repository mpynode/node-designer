"""Parity says WHAT the compiled node computes; nothing said at WHAT COST.

A voxelize port substituted MFnMesh::getClosestPoint (unaccelerated, NULL
MMeshIsectAccelParams*) for MMeshIntersector (octree). Same answer, same
determinism, through every gate -- and 714 SECONDS per evaluation where the
accelerated form took 0.125 s. No stage of this pipeline measured speed, so no
stage could see it.

These tests pin the measurement primitive (:func:`verify._time_pair`) and the
classifier (:func:`verify._timing_verdict`) with fake pulls and a fake clock --
no Maya, no bundle. Two properties are load-bearing and asserted directly:

  * the perturb closures run OUTSIDE the timed window. Without perturbation a
    content-memoizing compute is timed as a cache hit (measured on the kd-tree:
    0.169 ms static vs 1.785 ms with one query point moved -- a 10.6x error);
    inside the window they would be timed as part of the node's work.
  * with warnings disabled NO ``warning`` key is produced at any ratio. The 5.0
    threshold is reasoned, not calibrated, so the guard records numbers and stays
    quiet until a calibration table exists.
"""

from __future__ import annotations

import os
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


class _FakeClock:
    """A monotonic stand-in for the ``time`` module that RECORDS every read, so a
    test can prove what did (and did not) happen between t0 and t1."""

    def __init__(self, events, start=0.0, step=1e-4):
        self.events = events
        self.t = start
        self.step = step

    def perf_counter(self):
        self.events.append("clock")
        self.t += self.step
        return self.t


def _sleeper(seconds):
    return lambda: time.sleep(seconds)


class TestTimePair(unittest.TestCase):
    def setUp(self):
        from mpynode.native.toolchain import verify

        self.v = verify

    def test_a_ten_fold_difference_is_measured_as_a_ten_fold_ratio(self):
        perturbs = [lambda: None, lambda: None]
        res = self.v._time_pair(None, "py", "cpp",
                                _sleeper(0.001), _sleeper(0.010),
                                perturbs, time.perf_counter() + 60.0)
        self.assertIsNotNone(res)
        self.assertEqual(res["n"], self.v._TIMING_SAMPLES)
        self.assertFalse(res["truncated"])
        ratio = res["cpp_ms"] / res["py_ms"]
        # Best-of-3 on both sides, so the bound can be tight-ish without being
        # flaky: only interruptions ADD time, and they add to both sides.
        self.assertGreater(ratio, 4.0)
        self.assertLess(ratio, 40.0)

    def test_a_spent_deadline_truncates_after_one_pair_and_says_so(self):
        perturbs = [lambda: None]
        res = self.v._time_pair(None, "py", "cpp",
                                lambda: None, lambda: None,
                                perturbs, time.perf_counter() - 1.0)
        self.assertIsNotNone(res)
        self.assertTrue(res["truncated"])
        self.assertLessEqual(res["n"], 1)

    def test_perturbs_run_once_per_tick_and_never_inside_the_timed_window(self):
        events = []
        clock = _FakeClock(events)
        orig_time = self.v.time
        self.v.time = clock
        try:
            perturbs = [lambda: events.append("perturb0"),
                        lambda: events.append("perturb1")]
            res = self.v._time_pair(None, "py", "cpp",
                                    lambda: events.append("py"),
                                    lambda: events.append("cpp"),
                                    perturbs, 1.0e9)
        finally:
            self.v.time = orig_time

        self.assertIsNotNone(res)
        # The warm-up is UNTIMED: no clock read anywhere around it.
        self.assertEqual(events[:4], ["perturb0", "perturb1", "py", "cpp"])
        # Every TIMED pull is bracketed by exactly one clock read on each side,
        # so nothing else -- least of all a perturb -- can be inside the window.
        timed = events[4:]
        pulls = [i for i, e in enumerate(timed) if e in ("py", "cpp")]
        self.assertEqual(len(pulls), 2 * self.v._TIMING_SAMPLES)
        for i in pulls:
            self.assertEqual(timed[i - 1], "clock")
            self.assertEqual(timed[i + 1], "clock")
        # One tick per sample, plus the single warm-up tick -- and the SAME count
        # for both closures, which is what keeps the two nodes at equal values.
        for nm in ("perturb0", "perturb1"):
            self.assertEqual(events.count(nm), self.v._TIMING_SAMPLES + 1)

    def test_a_missing_perturb_refuses_to_measure(self):
        """A node with no perturbable input would be timed as a cache hit."""
        res = self.v._time_pair(None, "py", "cpp", lambda: None, lambda: None,
                                [lambda: None, None],
                                time.perf_counter() + 60.0)
        self.assertIsNone(res)
        self.assertIsNone(self.v._time_pair(None, "py", "cpp", lambda: None,
                                            lambda: None, [],
                                            time.perf_counter() + 60.0))


class TestTimingVerdict(unittest.TestCase):
    """Table-driven: one measurement in, one named classification out."""

    def setUp(self):
        from mpynode.native.toolchain import verify

        self.v = verify

    def _verdict(self, py_ms, cpp_ms, floor=1.0, n=3, truncated=False,
                 scene="geo 40 / array 512", mesh_query=False, warn=True):
        return self.v._timing_verdict(py_ms, cpp_ms, floor, n, truncated, scene,
                                      mesh_query=mesh_query, warn=warn)

    def test_an_unmeasured_side_is_not_a_measurement(self):
        for py, cpp in ((None, 1.0), (1.0, None), (None, None)):
            row = self._verdict(py, cpp)
            self.assertFalse(row["measured"])
            self.assertIn("reason", row)

    def test_below_the_floor_is_recorded_and_silent(self):
        # Ratio 9x, but BOTH sides are sub-floor -- noise, not a finding.
        row = self._verdict(1.0, 9.0, floor=15.0)
        self.assertEqual(row["verdict"], "below-floor")
        self.assertNotIn("warning", row)
        self.assertEqual(row["py_ms"], 1.0)
        self.assertEqual(row["cpp_ms"], 9.0)

    def test_the_floor_is_on_the_max_not_on_the_interpreted_side(self):
        """A floor on py_ms alone would make the guard permanently silent on the
        asymptotic case: density grows the COMPILED side while the interpreted
        side stays flat."""
        row = self._verdict(0.5, 500.0, floor=15.0)
        self.assertNotEqual(row["verdict"], "below-floor")
        self.assertIn("warning", row)

    def test_just_under_the_warn_ratio_is_silent(self):
        row = self._verdict(10.0, 10.0 * (self.v._TIMING_WARN_RATIO - 0.1))
        self.assertEqual(row["verdict"], "ok")
        self.assertNotIn("warning", row)

    def test_just_over_the_warn_ratio_warns(self):
        row = self._verdict(10.0, 10.0 * (self.v._TIMING_WARN_RATIO + 0.1))
        self.assertEqual(row["verdict"], "slower")
        self.assertIn("SLOWER", row["warning"])
        self.assertNotIn("ORDERS OF MAGNITUDE", row["warning"])

    def test_an_order_of_magnitude_escalates_the_wording(self):
        row = self._verdict(10.0, 120.0)
        self.assertEqual(row["verdict"], "much-slower")
        self.assertIn("ORDERS OF MAGNITUDE", row["warning"])
        self.assertIn("algorithmic regression", row["warning"])

    def test_a_truncated_measurement_is_labelled_a_lower_bound(self):
        row = self._verdict(10.0, 120.0, truncated=True)
        self.assertIn("lower bound", row["warning"])
        self.assertNotIn("lower bound", self._verdict(10.0, 120.0)["warning"])

    def test_the_mesh_query_clause_needs_the_spec_flag(self):
        with_flag = self._verdict(10.0, 120.0, mesh_query=True)["warning"]
        without = self._verdict(10.0, 120.0, mesh_query=False)["warning"]
        self.assertIn("MMeshIntersector", with_flag)
        self.assertNotIn("MMeshIntersector", without)

    def test_with_warnings_disabled_no_ratio_produces_a_warning(self):
        """The default. Numbers still land in the row; the sentence does not."""
        for cpp in (9.0, 51.0, 120.0, 1.0e5):
            row = self._verdict(10.0, cpp, warn=False)
            self.assertNotIn("warning", row)
            self.assertTrue(row["measured"])
            self.assertIn("ratio", row)

    def test_warnings_are_off_unless_the_env_gate_is_set(self):
        orig = os.environ.get("MPYNODE_TIMING_WARN")
        try:
            os.environ.pop("MPYNODE_TIMING_WARN", None)
            self.assertFalse(self.v._timing_warn_enabled())
            self.assertNotIn("warning", self._verdict(10.0, 120.0, warn=None))
            os.environ["MPYNODE_TIMING_WARN"] = "1"
            self.assertTrue(self.v._timing_warn_enabled())
            self.assertIn("warning", self._verdict(10.0, 120.0, warn=None))
        finally:
            os.environ.pop("MPYNODE_TIMING_WARN", None)
            if orig is not None:
                os.environ["MPYNODE_TIMING_WARN"] = orig


class TestTimingWiring(unittest.TestCase):
    """The call sites need Maya + a compiled bundle, so pin them by SOURCE."""

    def _src(self, fn):
        import inspect

        from mpynode.native.toolchain import verify

        return inspect.getsource(getattr(verify, fn))

    def test_timing_runs_only_after_a_passing_parity_verdict(self):
        for fn in ("_verify_one", "_verify_geo"):
            src = self._src(fn)
            self.assertIn("if passed and _timing_enabled():", src,
                          "%s must gate timing on the GENERIC pass verdict" % fn)
            self.assertLess(src.index("passed = maxerr <= tol"),
                            src.index("if passed and _timing_enabled():"),
                            "%s times before it knows parity passed" % fn)

    def test_the_geo_timing_pull_does_not_extract_components(self):
        """_read_geo_components' MFn extraction inside the timed region would be
        a large constant common to both sides and drag the ratio toward 1.0."""
        import ast
        import textwrap

        tree = ast.parse(textwrap.dedent(self._src("_pull_geo_plug")))
        fn = tree.body[0]
        if ast.get_docstring(fn):
            fn.body = fn.body[1:]        # judge the CODE, not the prose
        src = ast.unparse(fn)
        self.assertNotIn("_read_geo_components", src)
        for banned in ("getPoints", "getVertices", "getVertexNormals",
                       "getFaceVertexColors"):
            self.assertNotIn(banned, src)
        self.assertIn("asMObject()", src)

    def test_geo_configs_rewire_a_fresh_upstream_shape(self):
        src = self._src("_drive_geo_inputs")
        self.assertIn("rewire=True", src,
                      "_drive_geo_inputs must replace the upstream shape per cfg")

    def test_wire_geo_input_exposes_the_rewire_switch_and_defaults_off(self):
        import inspect

        from mpynode.native.toolchain import verify

        sig = inspect.signature(verify._wire_geo_input)
        self.assertIn("rewire", sig.parameters)
        self.assertIs(sig.parameters["rewire"].default, False)

    def test_the_bundle_budget_is_computed_once_outside_the_row_loop(self):
        src = self._src("_default_verify")
        self.assertIn("deadline = time.perf_counter() + _TIMING_BUDGET_S", src)
        self.assertLess(src.index("deadline = time.perf_counter()"),
                        src.index("for r in rows:\n        tn ="),
                        "the timing budget must be GLOBAL across the bundle")


if __name__ == "__main__":
    unittest.main()
