"""A compile report must be honest about what it does NOT know.

Three properties are load-bearing, each because its absence already cost
something on a real run:

* the report states WHICH gate judged the optimize rounds -- a node whose
  pointwise parity SKIPs is checked only by its authored ``@maya_test``, and a
  bare "12.41x" reads as verified when it is not;
* rejected rounds appear, with their themes. The attempt that measured SLOWER is
  the transferable result;
* a prediction is printed next to its measurement, so the two can disagree in
  public.

Everything is derived from ``rounds.json`` + the manifest row, so these tests
build those inputs directly and never run a compile.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


def _rounds(tmp, type_name, doc):
    from mpynode.native.compiler import bundler

    d = bundler.stage_dir_for(tmp, type_name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "rounds.json"), "w") as fh:
        json.dump(doc, fh)
    return d


def _ledger():
    return [
        {"index": 0, "outcome": "baseline", "ms": 100.0, "compiled": True},
        {"index": 1, "outcome": "accept", "slug": "hoist_invariant",
         "theme": "peel the p==0 test out of the argmin",
         "hypothesis": "the invariant disjunct blocks NEON packing",
         "predicted_speedup": 2.0, "speedup": 2.01, "ms": 49.8,
         "duration_s": 41.0, "parity": "pass", "compiled": True},
        {"index": 2, "outcome": "not-faster", "slug": "soa_split",
         "theme": "three double streams instead of MVector",
         "hypothesis": "SoA is always faster",
         "predicted_speedup": 3.0, "ms": 101.0, "duration_s": 55.0,
         "parity": "pass", "compiled": True,
         "note": "0.98x -- the 24-byte stride let LLVM pack x,y"},
        {"index": 3, "outcome": "parity-fail", "slug": "f32_lanes",
         "theme": "float32 distance accumulation",
         "predicted_speedup": 1.3, "compiled": True, "parity": "fail",
         "note": "11/20000 closestIndex differ"},
    ]


class TestGateStrengthIsStated(unittest.TestCase):
    def test_the_gate_name_appears_in_the_report(self):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            _rounds(tmp, "kDTree", {"accepted": True, "speedup": 2.01,
                                    "baseline_ms": 100.0, "best_ms": 49.8,
                                    "parity_gate": "authored+pointwise",
                                    "reason": "accepted", "ledger": _ledger()})
            md = stage_report.node_report_text(tmp, "kDTree")

        self.assertIn("authored+pointwise", md)
        self.assertIn("Parity gate", md)
        # And the caveat a reader needs in order to weigh it.
        self.assertIn("@maya_test", md)

    def test_no_gate_is_called_out_loudly(self):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            _rounds(tmp, "kDTree", {"accepted": False, "speedup": 1.0,
                                    "parity_gate": "none", "reason": "no gain",
                                    "ledger": []})
            md = stage_report.node_report_text(tmp, "kDTree")

        self.assertIn("No parity gate ran", md)


class TestRejectedRoundsSurvive(unittest.TestCase):
    def setUp(self):
        from mpynode.native.toolchain import stage_report

        self.tmp = tempfile.mkdtemp(prefix="mpynode-report-")
        _rounds(self.tmp, "kDTree",
                {"accepted": True, "speedup": 2.01, "baseline_ms": 100.0,
                 "best_ms": 49.8, "parity_gate": "authored+pointwise",
                 "reason": "accepted (2.01x)", "ledger": _ledger()})
        self.md = stage_report.node_report_text(self.tmp, "kDTree")

    def test_every_round_has_a_row(self):
        for slug in ("hoist_invariant", "soa_split", "f32_lanes"):
            self.assertIn(slug, self.md, slug)

    def test_rejections_say_why(self):
        self.assertIn("Rejected rounds", self.md)
        self.assertIn("not faster", self.md)
        self.assertIn("parity fail", self.md)
        self.assertIn("11/20000 closestIndex differ", self.md)

    def test_predicted_and_measured_are_both_printed(self):
        self.assertIn("Predicted vs measured", self.md)
        # 3.00x predicted for a round that turned out slower.
        self.assertIn("3.00x", self.md)
        self.assertIn("| 2.00x |", self.md)

    def test_a_landed_prediction_is_not_noise_in_the_divergence_list(self):
        """01 predicted 2.0 and measured 2.01 -- not worth a bullet."""
        section = self.md.split("### Predicted vs measured", 1)[1]
        section = section.split("###", 1)[0]
        self.assertNotIn("hoist_invariant", section)
        self.assertIn("soa_split", section)


class TestANoChangeRoundReadsLikeItsSiblings(unittest.TestCase):
    """``no-change`` had no ``_OUTCOME_MARK`` entry, so both the rounds table
    and the rejected list rendered the bare enum through the ``return outcome``
    fallback -- "no-change" sitting in a column next to "rejected: not faster".
    """

    def _md(self):
        from mpynode.native.toolchain import stage_report

        ledger = _ledger() + [
            {"index": 4, "outcome": "no-change", "slug": "simd_lanes",
             "theme": "widen the inner loop to four lanes", "duration_s": 12.0,
             "note": "candidate is identical to the current best"}]
        with tempfile.TemporaryDirectory() as tmp:
            _rounds(tmp, "kDTree",
                    {"accepted": True, "speedup": 2.01, "baseline_ms": 100.0,
                     "best_ms": 49.8, "parity_gate": "authored+pointwise",
                     "reason": "accepted (2.01x)", "ledger": ledger})
            return stage_report.node_report_text(tmp, "kDTree")

    def test_the_outcome_is_spelled_out(self):
        from mpynode.native.toolchain import stage_report

        self.assertEqual(stage_report._outcome_text("no-change"),
                         "rejected: no change to the source")

    def test_the_report_never_prints_the_bare_enum(self):
        md = self._md()
        self.assertIn("rejected: no change to the source", md)
        self.assertNotIn("| no-change |", md)
        self.assertNotIn("-- no-change.", md)


class TestDegradesWithoutData(unittest.TestCase):
    def test_a_node_that_never_optimized_still_reports(self):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            md = stage_report.node_report_text(
                tmp, "plainNode",
                row={"source_node": "plainNode", "build_status": "compiled",
                     "ported": False, "verify": {"ran": True, "pass": True,
                                                 "maxerr": 0.0, "tol": 1e-9}})

        self.assertIn("plainNode", md)
        self.assertIn("3 AI optimize | not run", md)
        self.assertIn("parity: **pass**", md)

    def test_unresolved_regions_are_surfaced(self):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            md = stage_report.node_report_text(
                tmp, "gappy",
                row={"ported": True,
                     "incomplete": ["pandas DataFrame groupby has no C++ form"],
                     "invented_io": ["file read"]})

        self.assertIn("Unfinished work", md)
        self.assertIn("pandas DataFrame groupby", md)
        self.assertIn("invented I/O", md)


class TestTimingIsRecorded(unittest.TestCase):
    """A port that is correct but slower than the Python it replaced is a
    PASSING row. The measurement is worth writing down either way -- that record
    is what a later calibration pass reads."""

    def _md(self, timing):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            return stage_report.node_report_text(
                tmp, "slowNode",
                row={"source_node": "slowNode", "build_status": "compiled",
                     "verify": {"ran": True, "pass": True, "maxerr": 0.0,
                                "tol": 1e-9, "timing": timing}})

    def test_a_slower_port_gets_its_warning_and_its_numbers(self):
        md = self._md({"measured": True, "py_ms": 5.5, "cpp_ms": 124.7,
                       "n": 3, "truncated": False, "verdict": "much-slower",
                       "warning": "TIMING: compiled is 22.7x SLOWER",
                       "scene": "geo 140/array 5000"})
        self.assertIn("parity: **pass**", md)           # still a pass
        self.assertIn("TIMING: compiled is 22.7x SLOWER", md)
        self.assertIn("* speed: compiled 124.700 ms vs interpreted 5.500 ms", md)
        self.assertIn("best of 3", md)
        self.assertIn("geo 140/array 5000", md)

    def test_a_clean_measurement_is_still_written_down(self):
        md = self._md({"measured": True, "py_ms": 5.5, "cpp_ms": 0.9, "n": 3,
                       "truncated": False, "verdict": "ok",
                       "scene": "geo 140/array 5000"})
        self.assertIn("* speed: compiled 0.900 ms vs interpreted 5.500 ms", md)
        self.assertNotIn("TIMING", md)

    def test_an_unmeasured_row_prints_no_speed_line(self):
        md = self._md({"measured": False, "reason": "no benchable plugs"})
        self.assertNotIn("* speed:", md)

    def test_a_row_with_no_timing_at_all_is_safe(self):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            md = stage_report.node_report_text(
                tmp, "plainNode",
                row={"verify": {"ran": True, "pass": True, "maxerr": 0.0,
                                "tol": 1e-9}})
        self.assertIn("parity: **pass**", md)
        self.assertNotIn("* speed:", md)


class TestIndexReport(unittest.TestCase):
    def test_index_lists_every_node_and_links_to_written_reports(self):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            _rounds(tmp, "kDTree",
                    {"accepted": True, "speedup": 12.41, "parity_gate": "x",
                     "baseline_ms": 100.0, "best_ms": 8.0, "ledger": _ledger()})
            rows = [{"type_name": "kDTree", "build_status": "compiled",
                     "ported": True, "incomplete": []},
                    {"type_name": "plainNode", "build_status": "compiled",
                     "ported": False, "incomplete": []}]
            written = stage_report.write_reports(tmp, "myPlugin", rows)
            with open(os.path.join(tmp, "REPORT.md")) as fh:
                idx = fh.read()

        self.assertEqual(len(written), 3, written)  # 2 nodes + index
        self.assertIn("kDTree", idx)
        self.assertIn("plainNode", idx)
        self.assertIn("12.41x", idx)
        self.assertIn("build/stages/kDTree/REPORT.md", idx)
        # The layout legend is the thing that makes the folder self-explaining.
        self.assertIn("3_optimized/NN_<slug>.cpp", idx)

    def test_writing_reports_never_raises_on_a_junk_row(self):
        from mpynode.native.toolchain import stage_report

        with tempfile.TemporaryDirectory() as tmp:
            written = stage_report.write_reports(
                tmp, "myPlugin", [{}, {"type_name": None}, None])

        self.assertEqual(len(written), 1)  # index only


if __name__ == "__main__":
    unittest.main()
