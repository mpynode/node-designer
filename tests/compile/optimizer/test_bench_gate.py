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
    def test_below_floor_at_the_largest_rung_is_measured_under_confirmation(self):
        """Refusing outright threw away every real win on the nodes that live
        under the floor (the skins at 5.9-8.2 ms). Now: measure at the largest
        rung, say so, and widen the engine's noise band to the whole node so
        each accept needs 1.15x on two independent timings."""
        seen, logged, state = [], [], {}

        def runner(script, args, prefix, timeout):
            seen.append(_geo_of(args))
            return ({"ok": True, "median_ms": 0.5}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner, log_cb=logged.append,
                           bench_state_out=state)
            self.assertIsNone(ad["resolution_fn"]())        # not calibrated yet
            self.assertEqual(ad["benchmark_fn"]("/b"), 0.5)
            self.assertEqual(ad["resolution_fn"](), float("inf"))
        # It climbed the whole ladder first -- a small rung is not a verdict.
        self.assertEqual(seen[-1], optimizer_live._BENCH_LADDER[-1][0])
        self.assertTrue(state.get("below_floor"))
        self.assertIn("two independent timings", state.get("reason", ""))
        self.assertEqual(state.get("rung"), list(optimizer_live._BENCH_LADDER[-1]))
        self.assertTrue(any("noise floor" in m for m in logged), logged)

    def test_above_the_floor_the_band_is_left_to_the_engine(self):
        def runner(script, args, prefix, timeout):
            return ({"ok": True, "median_ms": 40.0}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner)
            ad["benchmark_fn"]("/b")
            self.assertIsNone(ad["resolution_fn"]())

    def test_the_report_says_the_node_was_under_the_floor(self):
        from mpynode.native.toolchain import stage_report
        line = stage_report._bench_sentence(
            {"rung": [400, 20000], "floor_ms": 15.0, "perturbed": ["a (double)"],
             "fingerprint": "checked (1 plug(s))", "below_floor": True})
        self.assertIn("under the noise floor", line)
        self.assertIn("two independent timings", line)

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

    def test_how_the_adaptive_loop_ended_is_written(self):
        from mpynode.native.ai.optimizer import OptimizeResult

        res = OptimizeResult(True, "x", 20.0, 5.0, 4.0, 3, [], "accepted (4.00x)",
                             max_rounds=6,
                             stop_reason="round 3 gained 1.08x, below the "
                                         "1.15x needed to continue")
        with tempfile.TemporaryDirectory() as tmp:
            p = optimizer_live.write_rounds_json(tmp, "mPyThing", res)
            with open(p, encoding="utf-8") as fh:
                doc = json.load(fh)
        self.assertEqual(doc["rounds"], 3)
        self.assertEqual(doc["max_rounds"], 6)
        self.assertIn("1.08x", doc["stop_reason"])


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


class TestParityReadsEveryOutputKind(unittest.TestCase):
    """Generic parity used to die on two output kinds -- a string (hexAttribute:
    float('44 52 ...')) and a declared mesh (rbfWrap: float(None)) -- and to
    call an mPyTransform 'no scalar outputs to compare'."""

    def test_string_components_equal_iff_identical(self):
        from mpynode.native.toolchain.verify import _attr_components as ac

        self.assertEqual(ac("abc"), [3.0, 97.0, 98.0, 99.0])
        self.assertEqual(ac(["ab", 1.5]), [2.0, 97.0, 98.0, 1.5])
        self.assertNotEqual(ac("abc"), ac("abd"))
        self.assertNotEqual(ac("ab")[0], ac("abc")[0])   # length leads
        self.assertEqual(ac([(1, 2.0), 3]), [1.0, 2.0, 3.0])  # numerics unchanged

    def test_declared_geo_output_is_read_through_the_api(self):
        from mpynode.native.toolchain import verify

        calls = []

        class Cmds:
            def getAttr(self, plug, **kw):
                calls.append(plug)
                return 1.0

        with mock.patch.object(verify, "_geo_output_components",
                               return_value=[8.0, 1.0, 2.0]) as geo:
            out = verify._read_outputs(Cmds(), "n", {"outGeo": {"type": "mesh"},
                                                    "k": {"type": "double"}})
        geo.assert_called_once_with("n", "outGeo", "mesh")
        self.assertEqual(out["outGeo"], ([8.0, 1.0, 2.0], None))
        self.assertEqual(calls, ["n.k"])   # getAttr never asked for the mesh

    def test_geo_components_of_an_empty_plug_is_a_count_of_zero(self):
        from mpynode.native.toolchain import verify

        with mock.patch.object(verify, "_read_geo_components", return_value=None):
            self.assertEqual(verify._geo_output_components("n", "outGeo", "mesh"),
                             [0.0])
        geo = {"pts": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "topo": ((4, 4), (0, 1, 2, 3), ()),
               "attrs": [0.5]}
        with mock.patch.object(verify, "_read_geo_components", return_value=geo):
            comps = verify._geo_output_components("n", "outGeo", "mesh")
        self.assertEqual(comps[0], 2.0)                  # two points
        self.assertEqual(comps[1:5], [2.0, 8.0, 4.0, 6.0])  # counts / connects sigs
        self.assertEqual(comps[-1], 0.5)                 # attrs ride along

    def test_transform_family_compares_its_native_matrix(self):
        from mpynode.native.toolchain.verify import _native_family_outputs as nfo

        self.assertEqual(nfo({"mpy_type": "mPyTransform"}),
                         {"matrix": {"type": "matrix", "native": True}})
        self.assertEqual(nfo({"mpy_type": "mPyNode"}), {})
        self.assertEqual(nfo({}), {})

    def test_scalar_path_sizes_outputs_on_both_nodes(self):
        import inspect
        from mpynode.native.toolchain import verify

        src = inspect.getsource(verify)
        i = src.index("# An array OUTPUT has no elements until something consumes them")
        self.assertIn("for _nd in (orig, comp):", src[i:i + 600])
        self.assertIn("bench_size_output_multis(cmds, _nd, spec, K_ARR)", src[i:i + 700])


class TestReferenceErrorsAreNotParitySignals(unittest.TestCase):
    """spline read as FAIL 1.99: the random drive handed it a negative degree,
    the interpreted reference raised and kept stale outputs, and the compare
    measured that against the compiled node's answer."""

    def test_tap_counts_expression_errors_and_passes_the_rest_through(self):
        import io
        import sys
        from mpynode.native.toolchain.verify import _ExpressionErrorTap

        real = sys.stderr
        buf = io.StringIO()
        sys.stderr = buf
        try:
            with _ExpressionErrorTap() as tap:
                sys.stderr.write("[mPyNode expression error] boom\n")
                sys.stderr.write("plain warning\n")
                sys.stderr.flush()
            self.assertEqual(tap.hits, 1)
            self.assertIs(sys.stderr, buf)              # restored
        finally:
            sys.stderr = real
        self.assertIn("plain warning", buf.getvalue())   # nothing swallowed

    def test_reference_raised_reads_the_node_under_the_tap(self):
        import sys
        from mpynode.native.toolchain import verify

        class Cmds:
            def getAttr(self, plug, **kw):
                sys.stderr.write("[mPyNode expression error] negative dimensions\n")
                return 1.0

        class Quiet:
            def getAttr(self, plug, **kw):
                return 1.0

        self.assertTrue(verify._reference_raised(Cmds(), "n", {"o": {"type": "double"}}))
        self.assertFalse(verify._reference_raised(Quiet(), "n", {"o": {"type": "double"}}))


class TestParityFixtures(unittest.TestCase):
    """File-reading nodes were driven with an EMPTY path (or skipped). Both
    sides can read the same generated file instead."""

    def test_png_writer_emits_a_valid_8bit_rgb_png(self):
        import struct
        import zlib
        from mpynode.native.toolchain.verify import _write_png_rgb

        with tempfile.TemporaryDirectory() as d:
            p = _write_png_rgb(os.path.join(d, "g.png"), 5, 3,
                               lambda u, v: (u, v, 0.5))
            data = open(p, "rb").read()
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        w, h, depth, ctype = struct.unpack(">IIBB", data[16:26])
        self.assertEqual((w, h, depth, ctype), (5, 3, 8, 2))
        idat_len = struct.unpack(">I", data[33:37])[0]
        raw = zlib.decompress(data[41:41 + idat_len])
        self.assertEqual(len(raw), 3 * (1 + 5 * 3))     # h * (filter + w*3)

    def test_texture_inputs_get_gradients_arrays_get_k(self):
        from mpynode.native.toolchain.verify import parity_fixtures

        spec = {"mpy_type": "mPyFile", "compute": "buf = self.read_texture()",
                "inputs": {"fileName": {"type": "string"},
                           "layers": {"type": "string", "is_array": True},
                           "uvCoord": {"type": "float2"}}}
        with tempfile.TemporaryDirectory() as d:
            fx = parity_fixtures(spec, k=3, dirpath=d)
            self.assertEqual(sorted(fx), ["fileName", "layers"])
            self.assertTrue(fx["fileName"].endswith(".png"))
            self.assertEqual(len(fx["layers"]), 3)
            self.assertTrue(all(os.path.isfile(p) for p in fx["layers"]))
            # layers differ from each other (distinct phase)
            self.assertNotEqual(open(fx["layers"][0], "rb").read(),
                                open(fx["layers"][1], "rb").read())

    def test_json_reader_gets_a_frame_sequence_template(self):
        import json
        from mpynode import ndio
        from mpynode.native.toolchain.verify import (parity_fixtures,
                                                     _FIXTURE_FRAMES)

        spec = {"mpy_type": "mPyMesh",
                "compute": "resolved = ndio.frame_path(self.path, self.frame)",
                "inputs": {"path": {"type": "string"}, "frame": {"type": "time"}}}
        with tempfile.TemporaryDirectory() as d:
            fx = parity_fixtures(spec, dirpath=d)
            self.assertIn("####", fx["path"])
            f7 = ndio.frame_path(fx["path"], 7)
            doc = json.load(open(f7))
            self.assertEqual(len(doc["points"]), 8)
            self.assertEqual(sum(doc["counts"]), len(doc["indices"]))
            self.assertTrue(os.path.isfile(ndio.frame_path(fx["path"], _FIXTURE_FRAMES)))

    def test_disk_cache_gets_an_ndio_container(self):
        from mpynode import ndio
        from mpynode.native.toolchain.verify import parity_fixtures

        spec = {"mpy_type": "mPyMesh",
                "compute": 'frames = ndio.read(self.cachePath, "points")',
                "inputs": {"cachePath": {"type": "string"}, "frame": {"type": "time"}}}
        with tempfile.TemporaryDirectory() as d:
            fx = parity_fixtures(spec, dirpath=d)
            pts = ndio.read(fx["cachePath"], "points")
            self.assertEqual(tuple(pts.shape), (2, 8, 3))
            self.assertEqual(len(ndio.read(fx["cachePath"], "counts")), 6)

    def test_an_output_path_is_not_given_an_image_to_read(self):
        from mpynode.native.toolchain.verify import parity_fixtures

        spec = {"mpy_type": "mPyFile", "compute": "buf = self.read_texture()",
                "inputs": {"fileName": {"type": "string"},
                           "bakePath": {"type": "string"},
                           "outputDir": {"type": "string"}}}
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sorted(parity_fixtures(spec, dirpath=d)), ["fileName"])

    def test_plain_node_gets_nothing(self):
        from mpynode.native.toolchain.verify import parity_fixtures

        self.assertEqual(parity_fixtures({"inputs": {"a": {"type": "double"}}}), {})
        self.assertEqual(parity_fixtures({"inputs": {"s": {"type": "string"}},
                                          "compute": "self.o = len(self.s)"}), {})

    def test_apply_fixtures_sets_strings_on_every_node(self):
        from mpynode.native.toolchain.verify import apply_fixtures

        calls = []

        class Cmds:
            def setAttr(self, plug, *vals, **kw):
                calls.append((plug, vals, kw.get("type")))

        apply_fixtures(Cmds(), ("a", "b"), {"fileName": "x.png", "layers": ["l0", "l1"]})
        self.assertIn(("a.fileName", ("x.png",), "string"), calls)
        self.assertIn(("b.layers[1]", ("l1",), "string"), calls)
        self.assertEqual(len(calls), 6)


class TestBuiltinSceneIsShared(unittest.TestCase):
    def test_key_and_ops(self):
        from mpynode.native.toolchain import verify

        self.assertEqual(verify.builtin_scene_key("metaballsSw"), "metaballs")
        self.assertIsNone(verify.builtin_scene_key("kDTree"))
        ops = verify.builtin_scene_ops("metaballsCmp", 6)
        self.assertIn({"plug": "resolution", "value": 6}, ops)
        self.assertTrue(any(o["plug"] == "shapeMatrix[2]" and o["kind"] == "matrix"
                            for o in ops))
        self.assertIsNone(verify.builtin_scene_ops("patchRelax", 6))

    def test_apply_scene_ops_types_each_kind(self):
        from mpynode.native.toolchain import verify

        calls = []

        class Cmds:
            def setAttr(self, plug, *vals, **kw):
                calls.append((plug, len(vals), kw.get("type")))

        verify.apply_scene_ops(Cmds(), "m", [
            {"plug": "shapeMatrix[0]", "kind": "matrix", "value": [1.0] * 16},
            {"plug": "halfExtents[0]", "kind": "double3", "value": [1, 2, 3]},
            {"plug": "resolution", "value": 6}])
        self.assertEqual(calls, [("m.shapeMatrix[0]", 16, "matrix"),
                                 ("m.halfExtents[0]", 3, "double3"),
                                 ("m.resolution", 1, None)])

    def test_benchmark_harness_imports_the_shared_table(self):
        from tests.compile.optimizer.test_benchmark_harness_scene import _source

        src = _source()
        self.assertIn("BUILTIN_SCENES as _BUILTIN", src)
        self.assertNotIn("def _metaclay_scene", src)

    def test_geo_drive_uses_the_fixture_for_a_string_input(self):
        from mpynode.native.toolchain import verify

        calls = []

        class Cmds:
            def setAttr(self, plug, *vals, **kw):
                calls.append((plug, vals, kw.get("type")))

            def currentTime(self, *a, **k):
                pass

            def listConnections(self, *a, **k):
                return []

        inputs = {"path": {"type": "string"}}
        verify._drive_geo_inputs(Cmds(), ("i", "c"), inputs, {}, 1,
                                 __import__("random").Random(1),
                                 fixtures={"path": "/tmp/mesh.####.json"})
        self.assertIn(("i.path", ("/tmp/mesh.####.json",), "string"), calls)
        self.assertIn(("c.path", ("/tmp/mesh.####.json",), "string"), calls)


class TestDrivesRespectDeclaredRanges(unittest.TestCase):
    """mPyFile's preset preFilterRadius has min 0; the random drive handed it
    -3.2 and setAttr raised, so every texture node read 'verify could not run'."""

    def _cmds(self, ranges):
        class Cmds:
            def attributeQuery(self, attr, node=None, **kw):
                lo, hi = ranges.get((node, attr), (None, None))
                if kw.get("minExists"):
                    return lo is not None
                if kw.get("maxExists"):
                    return hi is not None
                if kw.get("minimum"):
                    return [lo]
                if kw.get("maximum"):
                    return [hi]
                raise RuntimeError("unexpected query %r" % kw)
        return Cmds()

    def test_clamps_to_the_first_node_that_declares_a_range(self):
        from mpynode.native.toolchain.verify import _clamp_drive

        cmds = self._cmds({("orig", "radius"): (0.0, 2.0)})
        self.assertEqual(_clamp_drive(cmds, ("orig", "comp"), "radius", "float", -3.2), 0.0)
        self.assertEqual(_clamp_drive(cmds, ("orig", "comp"), "radius", "float", 7.0), 2.0)
        self.assertEqual(_clamp_drive(cmds, ("orig", "comp"), "radius", "float", 1.5), 1.5)
        # the compiled node may carry the range too, or not: same answer
        self.assertEqual(_clamp_drive(cmds, ("comp", "orig"), "radius", "float", -1.0), 0.0)

    def test_unranged_and_non_scalar_pass_through(self):
        from mpynode.native.toolchain.verify import _clamp_drive

        cmds = self._cmds({})
        self.assertEqual(_clamp_drive(cmds, ("orig",), "gain", "double", -3.2), -3.2)
        self.assertEqual(_clamp_drive(cmds, ("orig",), "v", "vector", [-9, 0, 0]), [-9, 0, 0])
        self.assertEqual(_clamp_drive(cmds, ("orig",), "s", "string", "x"), "x")

    def test_unregistered_type_is_a_named_skip(self):
        from mpynode.native.toolchain.verify import _unregistered_type

        class Cmds:
            def nodeType(self, n):
                return "unknown"

        row = _unregistered_type(Cmds(), "unknown1", "brightContrastTex", 1e-4)
        self.assertFalse(row["ran"])
        self.assertIn("does not register node type 'brightContrastTex'", row["reason"])

        class Ok:
            def nodeType(self, n):
                return "brightContrastTex"

        self.assertIsNone(_unregistered_type(Ok(), "b1", "brightContrastTex", 1e-4))


class TestSkinParityHasARig(unittest.TestCase):
    """A skinCluster attached with a bare deformer() has no joints and no
    weights; the three skin templates were never compared pointwise."""

    def test_bind_wires_every_joint_and_paints_nonzero_weights(self):
        from mpynode.native.toolchain.verify import _bind_skin_node

        conns, sets = [], []

        class Cmds:
            def connectAttr(self, s, d, **kw):
                conns.append((s, d))

            def setAttr(self, plug, *vals, **kw):
                sets.append((plug, vals, kw.get("type")))

        ident = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
        _bind_skin_node(Cmds(), "sk", ["j0", "j1"], [ident, ident],
                        [[1.0, 0.0], [0.25, 0.75]])
        self.assertEqual(conns, [("j0.worldMatrix[0]", "sk.matrix[0]"),
                                 ("j1.worldMatrix[0]", "sk.matrix[1]")])
        self.assertIn(("sk.bindPreMatrix[1]", tuple(ident), "matrix"), sets)
        self.assertIn(("sk.weightList[1].weights[0]", (0.25,), None), sets)
        self.assertIn(("sk.weightList[1].weights[1]", (0.75,), None), sets)
        self.assertNotIn("sk.weightList[0].weights[1]", [s[0] for s in sets])  # zero: skipped

    def test_weight_values_flatten_and_roll(self):
        from mpynode.native.toolchain.verify import _skin_weight_values

        W = [[1.0, 0.0, 0.0], [0.5, 0.5, 0.0]]
        self.assertEqual(_skin_weight_values(W), [1.0, 0.0, 0.0, 0.5, 0.5, 0.0])
        rolled = _skin_weight_values(W, roll=1)
        self.assertEqual(rolled[:3], [0.0, 1.0, 0.0])
        self.assertAlmostEqual(sum(rolled[3:]), 1.0)

    def test_skin_branch_no_longer_skips(self):
        import inspect
        from mpynode.native.toolchain import verify

        src = inspect.getsource(verify)
        self.assertNotIn("skinCluster needs a bound rig", src)
        self.assertIn("_skin_rig(cmds, name)", src)
        self.assertIn("_pose_skin_rig(cmds, elbow, random)", src)


class TestSideEffectSelectorsStayAtDefault(unittest.TestCase):
    """twistSwingSkin's skinMode feeds sync_paint, an interpreted-only blessed
    side effect that rewrites weightList on a paint-mode switch; randomising it
    read as FAIL 1.18 on a node that matches at 0.0 in Live mode."""

    _SPEC = {"mpy_type": "mPySkinCluster",
             "inputs": {"skinMode": {"type": "enum", "default_value": 2,
                                     "enum_names": ["Paint LBS", "Paint DQS", "Live"]},
                        "twistAxis": {"type": "enum", "default_value": 0,
                                      "enum_names": ["X", "Y", "Z"]}},
             "compute": ("mode = int(self.skinMode)\n"
                         "self.sync_paint(mode)\n"
                         "axis = int(self.twistAxis)\n")}

    def test_only_the_selector_of_the_side_effect_is_held(self):
        from mpynode.native.toolchain import verify

        with mock.patch("mpynode.native.compiler.kernels.blessed_transpile."
                        "side_effect_method_names", return_value=frozenset({"sync_paint"})):
            self.assertEqual(verify._side_effect_gated_enums(self._SPEC), {"skinMode"})

    def test_direct_argument_form_and_no_side_effect(self):
        from mpynode.native.toolchain import verify

        direct = dict(self._SPEC, compute="self.sync_paint(self.skinMode)\n")
        with mock.patch("mpynode.native.compiler.kernels.blessed_transpile."
                        "side_effect_method_names", return_value=frozenset({"sync_paint"})):
            self.assertEqual(verify._side_effect_gated_enums(direct), {"skinMode"})
        with mock.patch("mpynode.native.compiler.kernels.blessed_transpile."
                        "side_effect_method_names", return_value=frozenset()):
            self.assertEqual(verify._side_effect_gated_enums(self._SPEC), frozenset())

    def test_enum_default_and_note(self):
        from mpynode.native.toolchain.verify import _enum_default, _held_enum_note

        self.assertEqual(_enum_default({"default_value": 2}, ["a", "b", "c"]), 2)
        self.assertEqual(_enum_default({"default_value": "b"}, ["a", "b", "c"]), 1)
        self.assertEqual(_enum_default({}, ["a"]), 0)
        self.assertIn("skinMode", _held_enum_note({"skinMode"}, ""))
        self.assertEqual(_held_enum_note(set(), "x"), "x")
        self.assertTrue(_held_enum_note({"m"}, "x").startswith("x -- "))


class TestVerifyWorkerEnvironment(unittest.TestCase):
    """`mayapy -c` puts the cwd on sys.path; at the repo root Maya then runs
    ./userSetup.py, which died on __file__ and aborted the startup chain, so the
    worker's environment differed from the caller's (fileTexture parity 0.023
    in the worker, 3e-7 in-process)."""

    def test_worker_runs_in_the_payload_directory(self):
        import subprocess
        from mpynode.native.toolchain import verify

        with tempfile.TemporaryDirectory() as d:
            payload = os.path.join(d, "payload.json")
            open(payload, "w").write("{}")
            env = {"MPYNODE_VERIFY_PAYLOAD": payload}
            self.assertEqual(verify._worker_cwd(env), d)
            seen = {}

            def fake_run(argv, **kw):
                seen.update(kw)
                return mock.Mock(returncode=0)

            with mock.patch.object(subprocess, "run", fake_run):
                verify._default_verify_runner(["mayapy", "-c", "x"], env, 10)
            self.assertEqual(seen.get("cwd"), d)
        self.assertIsNone(verify._worker_cwd({}))

    def test_repo_usersetup_survives_exec_without___file__(self):
        from tests import _paths

        path = os.path.join(_paths.ROOT, "userSetup.py")
        if not os.path.isfile(path):
            # /userSetup.py is gitignored: a per-machine copy (INSTALL.md), so
            # this only checks the copy on a machine that has one.
            self.skipTest("no local userSetup.py at the repo root")
        src = open(path, encoding="utf-8").read()
        g = {"__name__": "userSetup_probe"}          # no __file__, like Maya's exec
        with mock.patch.dict(os.environ, {"MPYNODE_USE_STUDIO": "1"}):
            exec(compile(src, "./userSetup.py", "exec"), g)
        self.assertTrue(os.path.isdir(g["PROJECT_DIR"]))


# ------------------------------------------------------- small-scene hold
class TestSmallSceneHold(unittest.TestCase):
    """When calibration climbs past the ladder's first rung, an accepted
    candidate is re-timed there against the incumbent and rejected if it is
    clearly slower. rbfWrapDeformer (2026-09-09): the design accepted at geo 90
    dropped the H cache -- right at 8k vertices, 2x slower at 1.5k."""

    def _runner(self, table, fps=None):
        """median_ms by (geo, bundle); a fingerprint per bundle at the small
        rung (default: identical) so the divergence check has data."""
        calls = []

        def runner(script, args, prefix, timeout):
            geo, bundle = _geo_of(args), args[0]
            calls.append((geo, bundle))
            fp = (fps or {}).get(bundle) or {"out": {"kind": "double",
                                                     "count": 1,
                                                     "values": [1.0]}}
            with open(_fp_path(args), "w") as fh:
                json.dump(fp, fh)
            ms = table.get((geo, bundle), table.get(geo))
            return ({"ok": True, "median_ms": ms, "moved": ["a (double)"]},
                    True, "")

        runner.calls = calls
        return runner

    def _climbed(self, tmp, runner, state):
        # geo 40 is under the floor for every bundle -> the gate froze at 90.
        # Returns the adapters and how many timings calibration itself spent
        # (its first rung IS geo 40), so the checks below count only their own.
        ad = _adapters(tmp, runner, bench_state_out=state)
        self.assertEqual(ad["benchmark_fn"]("/base"), 40.0)
        self.assertEqual(state["rung"], [90, 2000])
        return ad, len(runner.calls)

    def test_nothing_to_check_when_the_scene_did_not_climb(self):
        runner = self._runner({40: 40.0})
        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner)
            ad["benchmark_fn"]("/base")
            n = len(runner.calls)
            self.assertIsNone(ad["accept_check_fn"]("/cand", "/base"))
        self.assertEqual(len(runner.calls), n)            # no extra timing

    def test_a_candidate_clearly_slower_on_the_small_scene_is_rejected(self):
        runner = self._runner({(40, "/base"): 5.0, (40, "/cand"): 8.0,
                               90: 40.0})
        state = {}
        with tempfile.TemporaryDirectory() as tmp:
            ad, n0 = self._climbed(tmp, runner, state)
            why = ad["accept_check_fn"]("/cand", "/base")
        self.assertIn("slower on the small scene", why)
        self.assertIn("geo 40", why)
        self.assertIn("8.000 ms", why)
        self.assertEqual(state["small_rung"], [40, 512])
        # Both were timed at the small rung, incumbent then candidate.
        self.assertEqual(runner.calls[n0:], [(40, "/base"), (40, "/cand")])

    def test_within_the_band_holds(self):
        runner = self._runner({(40, "/base"): 5.0, (40, "/cand"): 5.3,
                               90: 40.0})
        with tempfile.TemporaryDirectory() as tmp:
            ad, _n0 = self._climbed(tmp, runner, {})
            self.assertIsNone(ad["accept_check_fn"]("/cand", "/base"))

    def test_the_incumbent_is_timed_once_per_bundle(self):
        runner = self._runner({(40, "/base"): 5.0, (40, "/c1"): 5.0,
                               (40, "/c2"): 5.0, 90: 40.0})
        with tempfile.TemporaryDirectory() as tmp:
            ad, n0 = self._climbed(tmp, runner, {})
            ad["accept_check_fn"]("/c1", "/base")
            ad["accept_check_fn"]("/c2", "/base")
        self.assertEqual(runner.calls[n0:],
                         [(40, "/base"), (40, "/c1"), (40, "/c2")])

    def test_a_divergence_on_the_small_scene_raises(self):
        fps = {"/cand": {"out": {"kind": "double", "count": 1, "values": [2.0]}}}
        runner = self._runner({(40, "/base"): 5.0, (40, "/cand"): 5.0,
                               90: 40.0}, fps=fps)
        with tempfile.TemporaryDirectory() as tmp:
            ad, _n0 = self._climbed(tmp, runner, {})
            with self.assertRaises(BenchmarkDiverged) as cm:
                ad["accept_check_fn"]("/cand", "/base")
        self.assertIn("small scene", str(cm.exception))

    def test_the_report_names_the_small_rung(self):
        from mpynode.native.toolchain import stage_report
        line = stage_report._bench_sentence(
            {"rung": [90, 2000], "floor_ms": 15.0, "perturbed": [],
             "fingerprint": "checked (1 plug(s))", "small_rung": [40, 512]})
        self.assertIn("re-timed against the incumbent on the smallest scene "
                      "(geo density 40 / array length 512)", line)
        self.assertEqual(stage_report._outcome_text("regressed"),
                         "rejected: slower on the small scene")


# ------------------------------------------------------------ texture bake
class TestTextureNodesAreTimedOnABake(unittest.TestCase):
    """Compute mode times one texel of a texture node (4-8 us -- every mPyFile
    template shipped as a noise-floor accept and came back unmeasurable in every
    sweep). A texture-classified spec (mpy_type mPyFile) is calibrated on the
    bake ladder instead: an ogsRender of the node on a plane, source image
    grown 1024 -> 2048 -> 4096 until the frame clears the floor."""

    _TEX = dict(_SPEC, mpy_type="mPyFile")

    def _tex_adapters(self, tmp, runner, **over):
        kw = dict(complete_fn=lambda system, user: "x", run_step=runner)
        kw.update(over)
        return optimizer_live.make_adapters(self._TEX, tmp, **kw)

    def test_a_texture_node_is_measured_in_bake_mode(self):
        seen, state = [], {}

        def runner(script, args, prefix, timeout):
            seen.append(list(args))
            return ({"ok": True, "median_ms": 40.0}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = self._tex_adapters(tmp, runner, bench_state_out=state)
            self.assertEqual(ad["benchmark_fn"]("/b"), 40.0)
        a = seen[0]
        self.assertIn("--mode", a)
        self.assertEqual(a[a.index("--mode") + 1], "bake")
        self.assertEqual(int(a[a.index("--bake-source") + 1]), 1024)
        self.assertEqual(state["rung"], ["bake", 1024])

    def test_the_bake_ladder_grows_the_source_until_the_floor(self):
        sizes, state = [], {}

        def runner(script, args, prefix, timeout):
            px = int(args[args.index("--bake-source") + 1])
            sizes.append(px)
            return ({"ok": True, "median_ms": 5.0 if px < 4096 else 22.0}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = self._tex_adapters(tmp, runner, bench_state_out=state)
            self.assertEqual(ad["benchmark_fn"]("/b"), 22.0)
            # the small-scene guard re-times on the ladder's first rung
            n0 = len(sizes)
            ad["accept_check_fn"]("/cand", "/b")
        self.assertEqual(sizes[:3], [1024, 2048, 4096])
        self.assertEqual(state["rung"], ["bake", 4096])
        self.assertEqual(sizes[n0:], [1024, 1024])
        self.assertEqual(state["small_rung"], ["bake", 1024])

    def test_a_compute_node_never_sees_bake_mode(self):
        seen = []

        def runner(script, args, prefix, timeout):
            seen.append(list(args))
            return ({"ok": True, "median_ms": 40.0}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, runner)
            ad["benchmark_fn"]("/b")
        self.assertNotIn("--mode", seen[0])

    def test_the_report_names_the_bake(self):
        from mpynode.native.toolchain import stage_report
        line = stage_report._bench_sentence(
            {"rung": ["bake", 2048], "floor_ms": 15.0, "perturbed": ["gain (float)"],
             "fingerprint": "checked (1 plug(s))", "small_rung": ["bake", 1024]})
        self.assertIn("VP2 bake of a 2048px source image", line)
        self.assertIn("smallest scene (VP2 bake of a 1024px source image)", line)
        self.assertEqual(stage_report._rung_text([90, 2000]),
                         "geo density 90 / array length 2000")


if __name__ == "__main__":
    unittest.main()
