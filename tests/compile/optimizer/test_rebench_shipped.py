"""tools/harness/rebench_shipped.py re-measures every shipped AI-optimized node
under the gated benchmark and writes the honest number BESIDE the old one
(``rounds.json["remeasured"]``); REPORT.md renders it. These tests pin the
work-planning, the record shape, and the rendering -- without compiling or
booting Maya."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest

from tests import _paths

_TOOL = os.path.join(_paths.ROOT, "tools", "harness", "rebench_shipped.py")


def _tool():
    spec = importlib.util.spec_from_file_location("rebench_shipped", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_tree(root, *, accepted=True, with_final=True, with_baseline=True):
    """templates/Fam/Tpl/build/{manifest.json, stages/ty/rounds.json,
    stages/ty/3_optimized/00_baseline.cpp, ty/ty.cpp}"""
    build = os.path.join(root, "templates", "Fam", "Tpl", "build")
    stage = os.path.join(build, "stages", "thing")
    os.makedirs(os.path.join(stage, "3_optimized"), exist_ok=True)
    os.makedirs(os.path.join(build, "thing"), exist_ok=True)
    with open(os.path.join(build, "manifest.json"), "w") as fh:
        json.dump({"nodes": [{"type_name": "thing", "spec": {"inputs": {}}}]}, fh)
    with open(os.path.join(stage, "rounds.json"), "w") as fh:
        json.dump({"type_name": "thing", "accepted": accepted, "speedup": 12.5,
                   "ledger": []}, fh)
    if with_baseline:
        open(os.path.join(stage, "3_optimized", "00_baseline.cpp"), "w").write("b")
    if with_final:
        open(os.path.join(build, "thing", "thing.cpp"), "w").write("f")
    return build, stage


class TestPlan(unittest.TestCase):
    def test_accepted_node_with_both_sources_is_planned(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            build, stage = _fake_tree(tmp)
            items, skipped = t.plan(root=tmp)
            self.assertEqual(skipped, [])
            self.assertEqual([i["type_name"] for i in items], ["thing"])
            it = items[0]
            self.assertEqual(it["old_speedup"], 12.5)
            self.assertEqual(it["template_dir"], os.path.dirname(build))
            self.assertTrue(it["baseline_cpp"].endswith("00_baseline.cpp"))
            self.assertTrue(it["final_cpp"].endswith(os.path.join("thing", "thing.cpp")))

    def test_unaccepted_nodes_are_not_work(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            _fake_tree(tmp, accepted=False)
            items, skipped = t.plan(root=tmp)
        self.assertEqual((items, skipped), ([], []))

    def test_missing_source_is_reported_not_dropped(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            _fake_tree(tmp, with_final=False)
            items, skipped = t.plan(root=tmp)
        self.assertEqual(items, [])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0][0], "thing")
        self.assertIn("thing.cpp", skipped[0][1])

    def test_only_filters_by_type_name(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            _fake_tree(tmp)
            self.assertEqual(t.plan(root=tmp, only=["other"])[0], [])
            self.assertEqual(len(t.plan(root=tmp, only=["thing"])[0]), 1)


class TestRecord(unittest.TestCase):
    def test_record_shape_and_speedup(self):
        t = _tool()
        state = {"rung": [40, 512], "floor_ms": 15.0,
                 "perturbed": ["deformCage <- cageShape.vtx[0]"],
                 "fingerprint": "checked (1 plug(s))"}
        rec = t.make_record(state, 2103.7, 59.7, None, date="2026-09-08")
        self.assertEqual(rec["rung"], [40, 512])
        self.assertAlmostEqual(rec["speedup"], 2103.7 / 59.7)
        self.assertIsNone(rec["diverged"])
        self.assertEqual(rec["date"], "2026-09-08")
        self.assertIn("59.7", t.short(rec))
        self.assertIn("35.", t.short(rec))

    def test_divergence_and_unmeasurable_are_kept_apart(self):
        t = _tool()
        div = t.make_record({}, 10.0, 0.1, "out: maxerr 1 at element 0")
        self.assertIsNone(div["speedup"] is None or None)  # speedup still computed
        self.assertTrue(t.short(div).startswith("DIVERGED"))
        un = t.make_record({"reason": "below the noise floor"}, None, None, None)
        self.assertIsNone(un["speedup"])
        self.assertIn("unmeasurable", t.short(un))
        self.assertIn("noise floor", t.short(un))

    def test_write_record_adds_beside_never_over(self):
        t = _tool()
        with tempfile.TemporaryDirectory() as tmp:
            _build, stage = _fake_tree(tmp)
            p = os.path.join(stage, "rounds.json")
            t.write_record(p, t.make_record({}, 10.0, 5.0, None, date="d"))
            with open(p) as fh:
                doc = json.load(fh)
        self.assertEqual(doc["speedup"], 12.5)              # old number intact
        self.assertEqual(doc["remeasured"]["speedup"], 2.0)


class TestReportRendersTheRemeasurement(unittest.TestCase):
    def _md(self, remeasured):
        from mpynode.native.toolchain import stage_report
        from tests.compile.freshness.test_stage_report import _ledger, _rounds

        doc = {"accepted": True, "speedup": 6103.0, "baseline_ms": 2103.7,
               "best_ms": 0.34, "parity_gate": "authored-only",
               "reason": "accepted (6103.00x)", "ledger": _ledger(),
               "remeasured": remeasured}
        with tempfile.TemporaryDirectory() as tmp:
            _rounds(tmp, "kDTree", doc)
            return stage_report.node_report_text(tmp, "kDTree")

    def test_match_prints_the_honest_number_beside_the_old(self):
        md = self._md({"date": "2026-09-08", "rung": [40, 512],
                       "baseline_ms": 2103.7, "final_ms": 59.7,
                       "speedup": 35.2, "diverged": None,
                       "perturbed": ["deformCage <- cageShape.vtx[0]"]})
        self.assertIn("6103.00x", md)                       # old, still there
        self.assertIn("Re-measured 2026-09-08", md)
        self.assertIn("2103.700 ms -> shipped 59.700 ms (**35.20x**)", md)
        self.assertIn("outputs match", md)
        self.assertIn("geo density 40 / array length 512", md)
        self.assertIn("`deformCage <- cageShape.vtx[0]`", md)
        self.assertIn("re-measured: **35.20x** (outputs match)", md)

    def test_divergence_is_called_out(self):
        md = self._md({"date": "2026-09-08", "rung": [200, 10000],
                       "baseline_ms": 4.4, "final_ms": 0.001, "speedup": 4400.0,
                       "diverged": "samples: 1 values vs 30000", "perturbed": []})
        self.assertIn("DIVERGE", md)
        self.assertIn("samples: 1 values vs 30000", md)
        self.assertIn("revert decision pending", md)
        self.assertIn("re-measured: outputs DIVERGE", md)

    def test_unmeasurable_says_why(self):
        md = self._md({"date": "2026-09-08", "rung": [400, 20000],
                       "baseline_ms": None, "final_ms": None, "speedup": None,
                       "diverged": None, "perturbed": None,
                       "reason": "baseline 0.021 ms is below the 15 ms noise floor"})
        self.assertIn("**unmeasurable**", md)
        self.assertIn("noise floor", md)
        self.assertIn("re-measured: unmeasurable under the gate", md)

    def test_absent_block_renders_nothing_new(self):
        md = self._md(None)
        self.assertNotIn("Re-measured", md)


if __name__ == "__main__":
    unittest.main()
