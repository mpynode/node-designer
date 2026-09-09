"""The stage-3 benchmark must time a node doing the SAME real work twice.

Four holes let 28 accepted "speedups" ship without that being true (audited
2026-09-08 from the shipped rounds.json ledgers):

  * ``_calibrate`` froze the scene at the largest rung even when the baseline
    was still under the 15 ms noise floor, and the engine then accepted
    microsecond deltas -- 12 of 28 accepted nodes, one at "95x" on 0.209 ms.
  * ``bench_perturb_fn`` moved ONE numeric scalar; rbfWrap has only mesh inputs,
    so nothing moved and a candidate caching the whole solve was accepted at
    2103 ms -> 0.34 ms ("6103x") -- a cache hit, timed.
  * vacuity was checked for geometry outputs only; a candidate that early-outs
    to nothing on a numeric output (spline: 1.2 us, "3698x") was a valid timing.
  * every ledger said ``parity_gate: authored+pointwise``; pointwise had run for
    3 of 37 nodes.

These tests pin the four fixes: the floor gate, perturb coverage + refusal, the
bench-scene fingerprint (``BenchmarkDiverged``), and the honest ledger/labels.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

from mpynode.native.ai import optimizer_live
from mpynode.native.ai.optimizer import (BenchmarkDiverged, PARITY_PASS,
                                         optimize_cpp)
from tests.compile.optimizer.test_optimizer import _bench, _compile_ok, _parity

_SPEC = {"suggested": {"node_type_name": "mPyThing", "mpx_base": "MPxNode"},
         "compute": "self.out = self.a ** 2", "init": "import numpy as np",
         "inputs": {"a": {"type": "double"}},
         "outputs": {"out": {"type": "double"}}}


def _adapters(tmp, runner, **over):
    kw = dict(complete_fn=lambda system, user: "```cpp\nCANDIDATE_BODY;\n```",
              run_step=runner)
    kw.update(over)
    return optimizer_live.make_adapters(_SPEC, tmp, **kw)


def _geo_of(args):
    return int(args[args.index("--bench-geo") + 1])


def _fp_path(args):
    return args[args.index("--fingerprint-out") + 1]


# --------------------------------------------------------------------- engine
class TestEngineRecordsDivergence(unittest.TestCase):
    def test_bench_diverged_is_its_own_outcome_and_never_accepts(self):
        def bench(bundle):
            if bundle.endswith("CAND"):
                raise BenchmarkDiverged("out: maxerr 1 at element 0")
            return 100.0

        res = optimize_cpp("BASE", optimize_fn=lambda cpp: "CAND",
                           fix_fn=lambda cpp, errs: cpp, compile_fn=_compile_ok,
                           parity_fn=_parity(PARITY_PASS), benchmark_fn=bench,
                           rounds=1)
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")
        self.assertEqual(res.ledger[-1].outcome, "bench-diverged")
        self.assertIn("maxerr", res.ledger[-1].note)
        # It is NOT filed as unmeasurable: the difference matters to a reader.
        self.assertNotEqual(res.ledger[-1].outcome, "unmeasurable")


# ----------------------------------------------------------------- floor gate
class TestNoiseFloorGate(unittest.TestCase):
    def test_below_floor_at_the_largest_rung_is_unmeasurable(self):
        seen, logged, state = [], [], {}

        def runner(script, args, prefix, timeout):
            seen.append(_geo_of(args))
            return ({"ok": True, "median_ms": 0.5}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner, log_cb=logged.append,
                           bench_state_out=state)
            self.assertIsNone(ad["benchmark_fn"]("/b"))
        # It climbed the whole ladder first -- a small rung is not a verdict.
        self.assertEqual(seen[-1], optimizer_live._BENCH_LADDER[-1][0])
        self.assertIn("noise floor", state.get("reason", ""))
        self.assertEqual(state.get("rung"), list(optimizer_live._BENCH_LADDER[-1]))
        self.assertTrue(any("noise floor" in m for m in logged), logged)

    def test_clearing_the_floor_is_still_a_measurement(self):
        state = {}

        def runner(script, args, prefix, timeout):
            return ({"ok": True, "median_ms": 40.0}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner, bench_state_out=state)
            self.assertEqual(ad["benchmark_fn"]("/b"), 40.0)
        self.assertEqual(state.get("rung"), [40, 512])
        self.assertEqual(state.get("floor_ms"), optimizer_live._BENCH_FLOOR_MS)


# ------------------------------------------------------------ perturb refusal
class TestUnperturbedIsRefusedNotGrown(unittest.TestCase):
    def test_nothing_to_move_is_unmeasurable_and_does_not_climb(self):
        seen, state = [], {}

        def runner(script, args, prefix, timeout):
            seen.append(_geo_of(args))
            return ({"ok": False, "median_ms": None, "unperturbed": True},
                    False, "nothing to perturb")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner, bench_state_out=state)
            self.assertIsNone(ad["benchmark_fn"]("/b"))
        self.assertEqual(seen, [40], "not a size problem; must not climb")
        self.assertIn("perturb", state.get("reason", ""))


# ---------------------------------------------------------------- fingerprint
class TestFingerprintsDiffer(unittest.TestCase):
    def _fp(self, values, kind="numeric", count=None, text=None):
        e = {"kind": kind, "count": len(values) if count is None else count,
             "values": list(values)}
        if text is not None:
            e["text"] = text
        return {"out": e}

    def test_equal_and_within_tolerance_agree(self):
        d = optimizer_live.fingerprints_differ
        self.assertIsNone(d(self._fp([1.0, 2.0, 3.0]), self._fp([1.0, 2.0, 3.0])))
        self.assertIsNone(d(self._fp([1.0, 1e6]), self._fp([1.0 + 5e-7, 1e6 + 0.5])))

    def test_value_count_kind_and_text_differences_are_named(self):
        d = optimizer_live.fingerprints_differ
        why = d(self._fp([1.0, 2.0, 3.0]), self._fp([1.0, 2.0, 9.0]))
        self.assertIn("out", why)
        self.assertIn("maxerr", why)
        self.assertIn("element 2", why)
        self.assertIn("[2] vs numeric[1]", d(self._fp([1.0, 2.0]), self._fp([1.0])))
        two = {"out": {"kind": "numeric", "count": 2, "values": [1.0, 2.0]}}
        short = {"out": {"kind": "numeric", "count": 2, "values": [1.0]}}
        self.assertIn("values", d(two, short))
        self.assertIn("mesh", d(self._fp([1.0], kind="mesh"), self._fp([1.0])))
        self.assertIn("string", d(self._fp([], text=["a"]), self._fp([], text=["b"])))
        self.assertIn("one side only", d(self._fp([1.0]), {}))

    def test_non_dicts_never_diverge(self):
        self.assertIsNone(optimizer_live.fingerprints_differ(None, {"x": {}}))


class TestCandidateIsHeldToTheBaselineOutputs(unittest.TestCase):
    def _runner(self, fps):
        calls = {"n": 0}

        def runner(script, args, prefix, timeout):
            fp = fps[min(calls["n"], len(fps) - 1)]
            calls["n"] += 1
            with open(_fp_path(args), "w") as fh:
                json.dump(fp, fh)
            return ({"ok": True, "median_ms": 99.0, "moved": ["a (double)"]},
                    True, "")

        return runner

    def test_diverging_candidate_raises_matching_candidate_measures(self):
        base = {"out": {"kind": "numeric", "count": 1, "values": [4.0]}}
        bad = {"out": {"kind": "numeric", "count": 1, "values": [0.0]}}
        state = {}
        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, self._runner([base, bad, base]),
                           bench_state_out=state)
            self.assertEqual(ad["benchmark_fn"]("/baseline"), 99.0)   # calibrate
            with self.assertRaises(BenchmarkDiverged) as cm:
                ad["benchmark_fn"]("/cand1")
            self.assertIn("out", str(cm.exception))
            self.assertEqual(ad["benchmark_fn"]("/cand2"), 99.0)
        self.assertEqual(state.get("perturbed"), ["a (double)"])
        self.assertTrue(str(state.get("fingerprint", "")).startswith("checked"),
                        state)

    def test_rng_nodes_are_not_compared(self):
        base = {"out": {"kind": "numeric", "count": 1, "values": [4.0]}}
        bad = {"out": {"kind": "numeric", "count": 1, "values": [0.0]}}
        state = {}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(optimizer_live, "_spec_uses_rng",
                               return_value=True):
            ad = _adapters(tmp, self._runner([base, bad]), bench_state_out=state)
            ad["benchmark_fn"]("/baseline")
            self.assertEqual(ad["benchmark_fn"]("/cand"), 99.0)
        self.assertIn("skipped", state.get("fingerprint", ""))

    def test_harness_without_fingerprint_is_not_a_divergence(self):
        def runner(script, args, prefix, timeout):
            return ({"ok": True, "median_ms": 99.0}, True, "")

        state = {}
        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner, bench_state_out=state)
            ad["benchmark_fn"]("/baseline")
            self.assertEqual(ad["benchmark_fn"]("/cand"), 99.0)
        self.assertIn("unavailable", state.get("fingerprint", ""))


# ---------------------------------------------------------- ledger + labels
class TestParityGateLabel(unittest.TestCase):
    def test_labels_follow_what_actually_ran(self):
        lab = optimizer_live.parity_gate_label
        at = {"ran": True, "passed": True}
        self.assertEqual(lab({"ran": True, "generic_ran": True,
                              "authored_test": at}), "authored+pointwise")
        self.assertEqual(lab({"ran": True, "generic_ran": False,
                              "authored_test": at}), "authored-only")
        self.assertEqual(lab({"ran": True, "generic_ran": True}), "pointwise")
        self.assertEqual(lab({"ran": False}), "none")
        # Legacy result without the marker: `ran` is the generic run.
        self.assertEqual(lab({"ran": True, "pass": True}), "pointwise")
        self.assertEqual(lab(None), "none")

    def test_parity_fn_reports_the_gate_through_the_sink(self):
        seen = []

        def verify_fn(bundle, rows):
            return {"mPyThing": {"ran": True, "pass": True, "generic_ran": False,
                                 "authored_test": {"ran": True, "passed": True}}}

        pf = optimizer_live.parity_fn_from_verify(verify_fn, "mPyThing", _SPEC,
                                                  gate_sink=seen.append)
        self.assertEqual(pf("/b").status, PARITY_PASS)
        self.assertEqual(seen, ["authored-only"])


class TestRoundsJsonCarriesTheScene(unittest.TestCase):
    def test_bench_block_is_written(self):
        from mpynode.native.ai.optimizer import OptimizeResult
        from mpynode.native.compiler import bundler

        res = OptimizeResult(False, "x", 20.0, 20.0, 1.0, 0, [], "nothing")
        with tempfile.TemporaryDirectory() as tmp:
            p = optimizer_live.write_rounds_json(
                tmp, "mPyThing", res, parity_gate="authored-only",
                bench={"rung": [200, 10000], "floor_ms": 15.0,
                       "perturbed": ["deformCage <- cageShape.vtx[0]"],
                       "fingerprint": "checked (1 plug(s))"})
            with open(p, encoding="utf-8") as fh:
                doc = json.load(fh)
            self.assertEqual(os.path.dirname(p),
                             bundler.stage_dir_for(tmp, "mPyThing"))
        self.assertEqual(doc["parity_gate"], "authored-only")
        self.assertEqual(doc["bench"]["rung"], [200, 10000])
        self.assertEqual(doc["bench"]["perturbed"],
                         ["deformCage <- cageShape.vtx[0]"])

    def test_bench_defaults_to_an_empty_record(self):
        from mpynode.native.ai.optimizer import OptimizeResult

        res = OptimizeResult(False, "x", None, None, 1.0, 0, [], "n/a")
        with tempfile.TemporaryDirectory() as tmp:
            p = optimizer_live.write_rounds_json(tmp, "mPyThing", res)
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["bench"], {})


class TestReportSaysWhatTheNumbersAreWorth(unittest.TestCase):
    def _md(self, doc):
        from mpynode.native.toolchain import stage_report
        from tests.compile.freshness.test_stage_report import _ledger, _rounds

        base = {"accepted": True, "speedup": 2.0, "baseline_ms": 40.0,
                "best_ms": 20.0, "reason": "accepted (2.00x)",
                "ledger": _ledger()}
        base.update(doc)
        with tempfile.TemporaryDirectory() as tmp:
            _rounds(tmp, "kDTree", base)
            return stage_report.node_report_text(tmp, "kDTree")

    def test_authored_only_is_said_bluntly(self):
        md = self._md({"parity_gate": "authored-only"})
        self.assertIn("authored `@maya_test` only", md)
        self.assertIn("behavioural check", md)

    def test_bench_scene_is_printed_or_its_absence_is(self):
        md = self._md({"parity_gate": "authored+pointwise",
                       "bench": {"rung": [200, 10000], "floor_ms": 15.0,
                                 "perturbed": ["weight[0] (float)"],
                                 "fingerprint": "checked (2 plug(s))"}})
        self.assertIn("geo density 200 / array length 10000", md)
        self.assertIn("noise floor 15 ms", md)
        self.assertIn("`weight[0] (float)`", md)
        self.assertIn("outputs checked (2 plug(s))", md)
        old = self._md({"parity_gate": "authored+pointwise"})
        self.assertIn("Bench scene: not recorded", old)

    def test_not_exercised_and_diverged_have_words(self):
        from mpynode.native.toolchain import stage_report

        self.assertIn("not exercised",
                      stage_report._gate_sentence("not exercised"))
        self.assertIn("diverge", stage_report._outcome_text("bench-diverged"))


class TestMergeRecordsWhetherGenericRan(unittest.TestCase):
    def test_generic_ran_marker(self):
        from mpynode.native.toolchain.verify import _merge_authored_test

        good = {"ran": True, "passed": True, "count": 1, "passes": 1, "reason": ""}
        m = _merge_authored_test({"ran": False, "pass": None, "maxerr": None,
                                  "tol": None, "reason": "skipped"}, good)
        self.assertTrue(m["ran"])
        self.assertFalse(m["generic_ran"])
        m = _merge_authored_test({"ran": True, "pass": True, "maxerr": 0.0,
                                  "tol": 1e-4, "reason": ""}, good)
        self.assertTrue(m["generic_ran"])


# ------------------------------------------------------------ the harness
class TestHarnessFingerprintHelpers(unittest.TestCase):
    def test_flatten_values(self):
        from tests.compile.optimizer.test_benchmark_harness_scene import _load_func

        fn = _load_func("_flatten_values", {"_FP_CAP": 400000})
        self.assertEqual(fn(3), [3.0])
        self.assertEqual(fn([(1, 2.5), [True, None, "x"], 4]), [1.0, 2.5, 1.0, 4.0])
        self.assertEqual(fn("text"), [])
        self.assertEqual(len(fn(list(range(10)), cap=4)), 4)

    def test_source_carries_the_two_new_switches(self):
        from tests.compile.optimizer.test_benchmark_harness_scene import _source

        src = _source()
        for needle in ("--fingerprint-out", "--allow-unperturbed",
                       'result["unperturbed"] = True', "_fingerprint_outputs("):
            self.assertIn(needle, src, needle)


# ------------------------------------------------------------ perturbation
class _FakeCmds:
    """Just enough of maya.cmds for bench_perturb_fn: numeric plugs in
    ``attrs``, geometry inputs in ``conn`` (plug -> source plug), component
    positions in ``points``."""

    def __init__(self, attrs=None, conn=None, points=None):
        self.attrs = dict(attrs or {})
        self.conn = dict(conn or {})
        self.points = {k: list(v) for k, v in (points or {}).items()}
        self.moves, self.evals = [], []

    def objExists(self, p):
        return p in self.attrs or p in self.conn

    def listConnections(self, plug, **kw):
        src = self.conn.get(plug)
        if src is None:
            return []
        return [src] if kw.get("p") or kw.get("plugs") else [src.split(".")[0]]

    def getAttr(self, p, **kw):
        return self.attrs[p]

    def setAttr(self, p, *vals, **kw):
        self.attrs[p] = vals[0] if len(vals) == 1 else tuple(vals)

    def pointPosition(self, comp, **kw):
        return list(self.points[comp])

    def move(self, x, y, z, comp, **kw):
        self.moves.append(comp)
        self.points[comp][0] += x

    def dgeval(self, plug):
        self.evals.append(plug)

    # --- output sizing (bench_size_output_multis) ---
    def createNode(self, t, **kw):
        self.created = getattr(self, "created", [])
        name = "%s%d" % (t, len(self.created) + 1)
        self.created.append((t, name))
        return name

    def connectAttr(self, src, dst, **kw):
        self.connections = getattr(self, "connections", [])
        if getattr(self, "refuse_dst", None) and dst.startswith(self.refuse_dst):
            raise RuntimeError("cannot connect")
        self.connections.append((src, dst))


class TestPerturbCoversAnimatedInputs(unittest.TestCase):
    def test_static_names(self):
        from mpynode.native.toolchain.verify import _is_static_input_name as st

        for name in ("restCage", "bindMatrices", "base_mesh", "origPoints",
                     "interBase", "refFrame", "initialPose"):
            self.assertTrue(st(name), name)
        for name in ("deformCage", "weight", "restore", "geoToDeform",
                     "cv", "degree", "time"):
            self.assertFalse(st(name), name)

    def test_mesh_only_node_moves_a_vertex_of_each_animated_cage(self):
        from mpynode.native.toolchain import verify

        spec = {"inputs": {"deformCage": {"type": "mesh"},
                           "restCage": {"type": "mesh"},
                           "geoToDeform": {"type": "mesh"}}}
        cmds = _FakeCmds(
            conn={"n.deformCage": "cageShape.worldMesh[0]",
                  "n.restCage": "restShape.worldMesh[0]",
                  "n.geoToDeform": "bodyShape.worldMesh[0]"},
            points={"cageShape.vtx[0]": [0, 0, 0], "restShape.vtx[0]": [0, 0, 0],
                    "bodyShape.vtx[0]": [1, 1, 1]})
        fn = verify.bench_perturb_fn(cmds, "n", spec)
        self.assertIsNotNone(fn, "rbfWrap used to get None here: nothing moved")
        self.assertEqual(sorted(fn.moved),
                         ["deformCage <- cageShape.vtx[0]",
                          "geoToDeform <- bodyShape.vtx[0]"])
        self.assertNotIn("restShape.vtx[0]", cmds.moves)
        n0 = len(cmds.moves)
        fn()
        self.assertEqual(len(cmds.moves), n0 + 2)
        # upstream re-evaluated OUTSIDE the timed region
        self.assertIn("cageShape.worldMesh[0]", cmds.evals)

    def test_every_free_animated_numeric_moves_static_ones_stay(self):
        from mpynode.native.toolchain import verify

        spec = {"inputs": {"weight": {"type": "float", "is_array": True},
                           "gain": {"type": "double"},
                           "restLength": {"type": "double"},
                           "driven": {"type": "double"}}}
        cmds = _FakeCmds(attrs={"n.weight[0]": 0.5, "n.gain": 1.0,
                                "n.restLength": 2.0, "n.driven": 3.0},
                         conn={"n.driven": "anim.output"})
        fn = verify.bench_perturb_fn(cmds, "n", spec)
        self.assertEqual(sorted(fn.moved), ["gain (double)", "weight[0] (float)"])
        self.assertEqual(cmds.attrs["n.restLength"], 2.0)   # static: untouched
        self.assertEqual(cmds.attrs["n.driven"], 3.0)       # upstream-driven
        before = cmds.attrs["n.gain"]
        fn()
        self.assertNotEqual(cmds.attrs["n.gain"], before)

    def test_matrix_time_and_uv_inputs_move_too(self):
        from mpynode.native.toolchain import verify

        spec = {"inputs": {"matrix0": {"type": "matrix"},
                           "time": {"type": "time"},
                           "uvCoord": {"type": "float2"},
                           "mode": {"type": "enum"}}}
        ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        cmds = _FakeCmds(attrs={"n.matrix0": ident, "n.time": 0.0,
                                "n.uvCoord": [(0.0, 0.0)], "n.mode": 0})
        fn = verify.bench_perturb_fn(cmds, "n", spec)
        self.assertEqual(sorted(fn.moved),
                         ["matrix0 (matrix)", "time (time)", "uvCoord (float2)"])
        self.assertEqual(cmds.attrs["n.mode"], 0)   # enums change behaviour: left
        self.assertEqual(cmds.attrs["n.time"], 1.0)  # one frame per tick
        fn()
        self.assertEqual(cmds.attrs["n.time"], 2.0)

    def test_deformer_native_input_is_moved_too(self):
        from mpynode.native.toolchain import verify

        cmds = _FakeCmds(conn={"d.input[0].inputGeometry": "bodyShapeOrig.worldMesh[0]"},
                         points={"bodyShapeOrig.vtx[0]": [0, 0, 0]})
        fn = verify.bench_perturb_fn(cmds, "d", {"inputs": {}})
        self.assertEqual(fn.moved, ["input[0].inputGeometry <- bodyShapeOrig.vtx[0]"])

    def test_nothing_movable_is_none(self):
        from mpynode.native.toolchain import verify

        spec = {"inputs": {"path": {"type": "string"},
                           "restCage": {"type": "mesh"}}}
        cmds = _FakeCmds(conn={"n.restCage": "restShape.worldMesh[0]"},
                         points={"restShape.vtx[0]": [0, 0, 0]})
        self.assertIsNone(verify.bench_perturb_fn(cmds, "n", spec))


class TestOutputMultisAreSized(unittest.TestCase):
    """An output array with no consumer has no elements, so the compute writes
    nothing: spline computed ONE sample on 20 000 CVs. The bench scene now gives
    every array output k consumers through a stock sink node."""

    def test_each_array_output_gets_k_typed_consumers(self):
        from mpynode.native.toolchain import verify

        spec = {"outputs": {"samples": {"type": "vector", "is_array": True},
                            "lengths": {"type": "float", "is_array": True},
                            "outMatrix": {"type": "matrix", "is_array": True},
                            "total": {"type": "double"},
                            "names": {"type": "string", "is_array": True}}}
        cmds = _FakeCmds()
        rep = verify.bench_size_output_multis(cmds, "n", spec, 4)
        self.assertEqual(sorted(rep["sized"]),
                         [("lengths", 4, "plusMinusAverage.input1D"),
                          ("outMatrix", 4, "multMatrix.matrixIn"),
                          ("samples", 4, "plusMinusAverage.input3D")])
        self.assertEqual([s[0] for s in rep["skipped"]], ["names"])
        # one sink per output, k connections each, element i -> element i
        self.assertEqual(sorted(t for t, _ in cmds.created),
                         ["multMatrix", "plusMinusAverage", "plusMinusAverage"])
        self.assertEqual(len(cmds.connections), 12)
        dst = dict(cmds.connections)["n.samples[3]"]
        self.assertTrue(dst.endswith(".input3D[3]"), dst)
        # a scalar output is not an array: untouched
        self.assertFalse(any("n.total" in s for s, _ in cmds.connections))

    def test_a_refusing_plug_is_recorded_not_fatal(self):
        from mpynode.native.toolchain import verify

        spec = {"outputs": {"samples": {"type": "vector", "is_array": True}}}
        cmds = _FakeCmds()
        cmds.refuse_dst = "plusMinusAverage1.input3D[2]"
        rep = verify.bench_size_output_multis(cmds, "n", spec, 5)
        self.assertEqual(rep["sized"], [("samples", 2, "plusMinusAverage.input3D")])
        self.assertEqual(len(rep["skipped"]), 1)
        self.assertIn("stopped at 2", rep["skipped"][0][2])

    def test_seed_bench_scene_reports_the_sized_outputs(self):
        from mpynode.native.toolchain import verify

        spec = {"inputs": {}, "outputs": {"samples": {"type": "vector",
                                                      "is_array": True}}}
        cmds = _FakeCmds()
        rep = verify.seed_bench_scene(cmds, "n", spec, k_array=3)
        self.assertEqual(rep["outputs"], [("samples", 3, "plusMinusAverage.input3D")])

    def test_harness_records_them(self):
        from tests.compile.optimizer.test_benchmark_harness_scene import _source

        src = _source()
        self.assertIn('result["sized_outputs"]', src)
        self.assertIn("multi(s) sized", src)


if __name__ == "__main__":
    unittest.main()
