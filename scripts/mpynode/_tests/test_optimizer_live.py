"""The live adapters bind the pure optimizer engine to the real porter / LLM /
benchmark / parity infrastructure. To keep this suite Maya- and LLM-free, both
side channels are injectable: ``complete_fn`` (the model call) and ``run_step``
(the mayapy subprocess runner). We assert the adapters wire those correctly --
whole-file prompt hygiene, -ffp-contract=off enforced on compile, PARITY_JSON /
BENCH_JSON parsing, and the safe SKIP when no parity harness is available.
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest

from mpynode.native.ai import optimizer_live
from mpynode.native.ai import porter
from mpynode.native.ai.optimizer import PARITY_PASS, PARITY_FAIL, PARITY_SKIP
from unittest import mock


_SPEC = {"suggested": {"node_type_name": "mPyThing", "mpx_base": "MPxNode"},
         "compute": "self.out = self.a ** 2", "init": "import numpy as np"}

# Candidates are screened by optimizer_knowledge.implausible_reason before the
# engine spends a compile on them, so a stub's answer still has to look like a
# translation unit: braces, balanced, and at least a quarter of this length.
_BASELINE_CPP = "void f(){ return; }"


def _adapters(tmp, **over):
    kw = dict(complete_fn=lambda system, user: "```cpp\nCANDIDATE_BODY;\n```",
              run_step=lambda script, args, prefix, timeout: (None, False, ""))
    kw.update(over)
    return optimizer_live.make_adapters(_SPEC, tmp, **kw)


class TestMakeAdaptersShape(unittest.TestCase):
    def test_returns_the_five_engine_callables(self):
        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp)
            for k in ("optimize_fn", "fix_fn", "compile_fn", "parity_fn",
                      "benchmark_fn"):
                self.assertIn(k, ad)
                self.assertTrue(callable(ad[k]))


class TestTheEntryBaselineFollowsTheAcceptedBest(unittest.TestCase):
    """What TASK.md states as "Baseline on entry" must be the ms of the file the
    round is actually handed. ``_benchmark`` records it only while CALIBRATING,
    so every round after an accept was told the FIRST measurement -- and then
    spent itself re-measuring to discover the figure was stale."""

    def _drive(self, tmp, measurements, rounds=2):
        from mpynode.native.ai import optimizer_agent
        from mpynode.native.ai.optimizer import optimize_cpp, ParityVerdict

        told = []
        step = {"i": 0}

        def fake_owa(spec, ws_dir, cpp_text, agent_fn, **kw):
            told.append(kw.get("baseline_ms"))
            step["i"] += 1
            return "void g%d(){ return; }" % step["i"]

        def run_step(script, args, prefix, timeout):
            return ({"median_ms": measurements.pop(0)}, True, "")

        spec = {"suggested": {"node_type_name": "kdProbe"},
                "compute": "pass", "init": ""}
        with mock.patch.object(optimizer_agent, "optimize_with_agent", fake_owa):
            ad = optimizer_live.make_adapters(
                spec, tmp, node_type="kdProbe", agent_fn=lambda prompt: "",
                parity_fn=lambda b: ParityVerdict(PARITY_PASS),
                run_step=run_step)
            # A real compile is the one thing this wiring does not need.
            ad["compile_fn"] = lambda cpp: (True, "", "b:" + cpp)
            res = optimize_cpp(_BASELINE_CPP, rounds=rounds, **ad)
        return told, res, ad

    def test_round_two_is_told_the_accepted_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            told, res, _ad = self._drive(tmp, [20.0, 5.0, 4.99])
        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "accept", "not-faster"])
        self.assertEqual(told, [20.0, 5.0])

    def test_a_rejected_round_leaves_the_baseline_alone(self):
        """Keyed on the engine's ACCEPT, not on "measured faster": a candidate
        that missed min_speedup is not what the next round is handed."""
        with tempfile.TemporaryDirectory() as tmp:
            told, res, _ad = self._drive(tmp, [20.0, 19.5, 19.4])
        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "not-faster", "not-faster"])
        self.assertEqual(told, [20.0, 20.0])

    def test_the_adapters_stay_splat_safe(self):
        """optimize_node.py and test_optimizer_round_history.py splat this dict
        straight into optimize_cpp, which has no **kwargs -- one foreign key is
        a TypeError there, swallowed by the driver's blanket except."""
        import inspect
        from mpynode.native.ai.optimizer import optimize_cpp
        with tempfile.TemporaryDirectory() as tmp:
            _told, _res, ad = self._drive(tmp, [20.0, 5.0, 4.99])
        self.assertEqual(
            sorted(set(ad) - set(inspect.signature(optimize_cpp).parameters)),
            [])


class TestOptimizeAndFixHygiene(unittest.TestCase):
    def test_optimize_fn_strips_fence_to_whole_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp)
            out = ad["optimize_fn"]("int OLD = 1;")
            self.assertEqual(out.strip(), "CANDIDATE_BODY;")   # fence peeled

    def test_fix_fn_uses_complete_and_strips(self):
        seen = {}

        def complete(system, user):
            seen["user"] = user
            return "```cpp\nFIXED_BODY;\n```"

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, complete_fn=complete)
            out = ad["fix_fn"]("int BAD = ;", "error: expected expression")
            self.assertEqual(out.strip(), "FIXED_BODY;")
            self.assertIn("expected expression", seen["user"])  # errors embedded


class TestCompileFnEnforcesFpContract(unittest.TestCase):
    def test_writes_cpp_and_compiles_with_optimize_true(self):
        captured = {}

        def fake_compile_cpp(cpp_path, spec, out_dir, **kw):
            captured["cpp_path"] = cpp_path
            captured["optimize"] = kw.get("optimize")
            with open(cpp_path) as fh:
                captured["text"] = fh.read()
            return (True, "ok", os.path.join(out_dir, "mPyThing.bundle"))

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp)
            with mock.patch.object(porter, "compile_cpp", fake_compile_cpp):
                ok, log, bundle = ad["compile_fn"]("int CODE = 42;")
            self.assertTrue(ok)
            self.assertTrue(captured["optimize"])            # -ffp-contract=off
            self.assertEqual(captured["text"], "int CODE = 42;")
            self.assertTrue(bundle.endswith("mPyThing.bundle"))


class TestParityFn(unittest.TestCase):
    def test_skip_when_no_harness(self):
        # No parity harness -> cannot prove correctness -> SKIP (engine refuses).
        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp)   # parity_harness defaults None
            v = ad["parity_fn"]("/some/bundle")
            self.assertEqual(v.status, PARITY_SKIP)

    def test_pass_and_fail_from_parity_json(self):
        def runner_ok(script, args, prefix, timeout):
            return ({"ok": True, "scenes": [{"maxerr": 1e-9}]}, True, "")

        def runner_bad(script, args, prefix, timeout):
            return ({"ok": False, "errors": ["boom"]}, False, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, parity_harness="/h/parity.py", run_step=runner_ok)
            self.assertEqual(ad["parity_fn"]("/b").status, PARITY_PASS)
            ad2 = _adapters(tmp, parity_harness="/h/parity.py", run_step=runner_bad)
            self.assertEqual(ad2["parity_fn"]("/b").status, PARITY_FAIL)

    def test_skip_when_harness_yields_no_json(self):
        def runner_crash(script, args, prefix, timeout):
            return (None, False, "traceback...")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, parity_harness="/h/parity.py",
                           run_step=runner_crash)
            self.assertEqual(ad["parity_fn"]("/b").status, PARITY_SKIP)


class TestBenchmarkFn(unittest.TestCase):
    def test_parses_median_ms(self):
        def runner(script, args, prefix, timeout):
            return ({"ok": True, "median_ms": 12.5}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, run_step=runner)
            self.assertAlmostEqual(ad["benchmark_fn"]("/b"), 12.5)

    def test_none_when_unmeasurable(self):
        def runner(script, args, prefix, timeout):
            return (None, False, "crash")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, run_step=runner)
            self.assertIsNone(ad["benchmark_fn"]("/b"))

    def test_unmeasurable_says_why(self):
        # A candidate whose benchmark CRASHED and one that was benignly
        # unmeasurable both surfaced as a bare "round N: unmeasurable", and the
        # round was dropped. That silently discarded a real 18x win once.
        seen = []

        def runner(script, args, prefix, timeout):
            return (None, False, "Segmentation fault: 11")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, run_step=runner, log_cb=seen.append)
            self.assertIsNone(ad["benchmark_fn"]("/b"))
        self.assertTrue(any("Segmentation fault" in m for m in seen),
                        "the failure tail was never surfaced: %r" % (seen,))


class TestEmptyOutputGrowsTheLadder(unittest.TestCase):
    """An EMPTY output is a reason to GROW the bench scene, not to give up.

    The harness now refuses to report a timing for a compute that produced
    nothing (a 95x "win" measured on an empty isosurface is how a candidate with
    an inverted shape dispatch got accepted). But `_calibrate` bailed on the
    first rung that yielded no median, so that refusal would abort optimization
    outright for any node that is empty at geo=40 and fine at geo=200. Empty and
    crashed must be distinguishable.
    """

    @staticmethod
    def _geo_of(args):
        return int(args[args.index("--bench-geo") + 1])

    def test_empty_first_rung_grows_instead_of_aborting(self):
        seen = []

        def runner(script, args, prefix, timeout):
            geo = self._geo_of(args)
            seen.append(geo)
            if geo == 40:
                return ({"ok": False, "median_ms": None,
                         "empty_output": True}, False, "output EMPTY")
            return ({"ok": True, "median_ms": 99.0}, True, "")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, run_step=runner)
            ms = ad["benchmark_fn"]("/b")
        self.assertEqual(ms, 99.0,
                         "an empty first rung must grow, not abort (got %r)" % ms)
        self.assertIn(90, seen, "the ladder never grew past geo=40: %r" % seen)

    def test_all_rungs_empty_is_unmeasurable(self):
        def runner(script, args, prefix, timeout):
            return ({"ok": False, "median_ms": None, "empty_output": True},
                    False, "output EMPTY")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, run_step=runner)
            self.assertIsNone(ad["benchmark_fn"]("/b"))

    def test_a_crash_still_aborts_immediately(self):
        # Only EMPTY output grows the ladder. A crashed benchmark is not a
        # too-small scene, and retrying it up the whole ladder would burn six
        # mayapy launches per measurement.
        seen = []

        def runner(script, args, prefix, timeout):
            seen.append(self._geo_of(args))
            return (None, False, "Segmentation fault: 11")

        with tempfile.TemporaryDirectory() as tmp:
            ad = _adapters(tmp, run_step=runner)
            self.assertIsNone(ad["benchmark_fn"]("/b"))
        self.assertEqual(seen, [40],
                         "a crash must not climb the ladder: %r" % seen)


class TestBenchNodeFactory(unittest.TestCase):
    """A deformer's geometry arrives through the NATIVE input[0].inputGeometry,
    not through any declared spec input. `createNode` makes an ORPHAN deformer
    with no mesh, so pulling outputGeometry computes nothing -- patch_relax
    benchmarked at 0.11 ms, which is empty, not fast. The parity harness already
    knows to use cmds.deformer(); the benchmark must use the same knowledge.
    """

    def test_deformer_family_is_attached_to_geometry(self):
        from mpynode.native.toolchain import verify as _verify
        calls = []

        class FakeCmds:
            def polySphere(self, **kw):
                calls.append(("polySphere", kw))
                return ["sphereXf"]

            def deformer(self, geo, **kw):
                calls.append(("deformer", geo, kw))
                return ["theDeformer"]

            def createNode(self, t, **kw):
                calls.append(("createNode", t))
                return "theNode"

        spec = {"mpy_type": "mPyDeformer",
                "suggested": {"mpx_base": "MPxDeformerNode"}}
        node = _verify.bench_make_node(FakeCmds(), spec, "patchRelaxSw",
                                       density=140)
        self.assertEqual(node, "theDeformer")
        self.assertTrue(any(c[0] == "deformer" for c in calls),
                        "deformer never attached: %r" % (calls,))
        self.assertFalse(any(c[0] == "createNode" for c in calls))

    def test_density_reaches_the_deformed_mesh(self):
        from mpynode.native.toolchain import verify as _verify
        seen = {}

        class FakeCmds:
            def polySphere(self, **kw):
                seen.update(kw)
                return ["sphereXf"]

            def deformer(self, geo, **kw):
                return ["theDeformer"]

        _verify.bench_make_node(FakeCmds(), {"mpy_type": "mPyDeformer"},
                                "patchRelaxSw", density=200)
        self.assertEqual(int(seen.get("sx")), 200)

    def test_non_deformer_still_uses_createnode(self):
        from mpynode.native.toolchain import verify as _verify
        calls = []

        class FakeCmds:
            def createNode(self, t, **kw):
                calls.append(t)
                return "plainNode"

        node = _verify.bench_make_node(FakeCmds(), {"mpy_type": "mPyNode"},
                                       "kDTree", density=200)
        self.assertEqual(node, "plainNode")
        self.assertEqual(calls, ["kDTree"])


class TestRoundsOverride(unittest.TestCase):
    """One agentic round is a full 40-minute build+measure session, so the round
    count is the difference between a tractable sweep and days of compute. It was
    hardcoded to 2 with no way to lower it from outside the process."""

    def setUp(self):
        self._saved = os.environ.get("MPYNODE_OPT_ROUNDS")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MPYNODE_OPT_ROUNDS", None)
        else:
            os.environ["MPYNODE_OPT_ROUNDS"] = self._saved

    def test_default_is_still_two(self):
        os.environ.pop("MPYNODE_OPT_ROUNDS", None)
        self.assertEqual(optimizer_live._optimize_rounds(2), 2)

    def test_env_overrides(self):
        os.environ["MPYNODE_OPT_ROUNDS"] = "1"
        self.assertEqual(optimizer_live._optimize_rounds(2), 1)

    def test_garbage_falls_back_to_the_caller_value(self):
        os.environ["MPYNODE_OPT_ROUNDS"] = "not-a-number"
        self.assertEqual(optimizer_live._optimize_rounds(2), 2)

    def test_zero_is_honoured_so_a_sweep_can_measure_baseline_only(self):
        os.environ["MPYNODE_OPT_ROUNDS"] = "0"
        self.assertEqual(optimizer_live._optimize_rounds(2), 0)


class TestParityFromVerify(unittest.TestCase):
    """The compile-time hook reuses the pipeline's OWN subprocess parity verify
    as the optimizer's gate, so 'correct' means the same thing the build already
    means. Map its per-node row -> ParityVerdict, treating a non-ran verify as
    SKIP (never a pass)."""

    def _pf(self, row):
        vfn = lambda bundle, rows: {"myNode": row}
        return optimizer_live.parity_fn_from_verify(vfn, "myNode", {})

    def test_pass(self):
        v = self._pf({"ran": True, "pass": True, "maxerr": 1e-9})("/b")
        self.assertEqual(v.status, PARITY_PASS)

    def test_fail(self):
        v = self._pf({"ran": True, "pass": False, "reason": "drift"})("/b")
        self.assertEqual(v.status, PARITY_FAIL)

    def test_skip_when_not_ran(self):
        v = self._pf({"ran": False, "pass": None, "reason": "no ref"})("/b")
        self.assertEqual(v.status, PARITY_SKIP)

    def test_skip_when_node_missing(self):
        vfn = lambda bundle, rows: {}   # verify reported nothing for the node
        pf = optimizer_live.parity_fn_from_verify(vfn, "myNode", {})
        self.assertEqual(pf("/b").status, PARITY_SKIP)


class TestOptimizeSurviving(unittest.TestCase):
    """The per-node compile-hook loop: on ACCEPT it overwrites the node's .cpp
    with the winner; on reject it leaves the original untouched; a per-node
    exception is isolated (never aborts the others / the build). Engine +
    adapters factory are injected so this needs no clang / Maya / LLM."""

    def _write(self, tmp, name, text):
        p = os.path.join(tmp, name + ".cpp")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def _run(self, tmp, nodes, engine):
        return optimizer_live.optimize_surviving(
            nodes, tmp, verify_fn=lambda b, r: {}, engine=engine,
            adapters_factory=lambda *a, **k: {})

    def test_accept_overwrites_cpp(self):
        from mpynode.native.ai.optimizer import OptimizeResult
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "mPyThing", "BASELINE")
            engine = lambda baseline, **kw: OptimizeResult(
                True, "WINNER", 100.0, 10.0, 10.0, 1, [], "accepted")
            self._run(tmp, [("mPyThing", cpp, {"suggested": {}})], engine)
            with open(cpp) as fh:
                self.assertEqual(fh.read(), "WINNER")

    def test_reject_leaves_cpp_untouched(self):
        from mpynode.native.ai.optimizer import OptimizeResult
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "mPyThing", "BASELINE")
            engine = lambda baseline, **kw: OptimizeResult(
                False, baseline, 100.0, 100.0, 1.0, 1, [], "no gain")
            self._run(tmp, [("mPyThing", cpp, {"suggested": {}})], engine)
            with open(cpp) as fh:
                self.assertEqual(fh.read(), "BASELINE")

    def test_per_node_exception_isolated(self):
        from mpynode.native.ai.optimizer import OptimizeResult

        def engine(baseline, **kw):
            if baseline == "BOOM":
                raise RuntimeError("kaboom")
            return OptimizeResult(True, "WON", 9.0, 1.0, 9.0, 1, [], "ok")

        with tempfile.TemporaryDirectory() as tmp:
            bad = self._write(tmp, "bad", "BOOM")
            good = self._write(tmp, "good", "OK")
            res = self._run(tmp, [("bad", bad, {"suggested": {}}),
                                  ("good", good, {"suggested": {}})], engine)
            with open(good) as fh:
                self.assertEqual(fh.read(), "WON")     # good node still optimized
            self.assertNotIn("bad", res)               # bad node isolated out


class TestCancelStopsTheOptimizeLoop(unittest.TestCase):
    """The engine wraps each round in ``except Exception`` so a flaky adapter
    cannot abort the run. A user Cancel went in through that same door: it was
    logged as "round N: error" and the loop started the next round. These drive
    the REAL make_adapters + REAL optimize_cpp + REAL optimize_surviving, with
    only the model call and the C++ build stubbed."""

    def _write(self, tmp, name, text):
        p = os.path.join(tmp, name + ".cpp")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def _factory(self, tmp, complete_fn, started):
        from mpynode.native.ai.optimizer import ParityVerdict

        def factory(spec, scratch, **kw):
            started.append(kw.get("node_type"))
            ad = optimizer_live.make_adapters(
                spec, scratch, maya="/x", complete_fn=complete_fn,
                node_type=kw.get("node_type"),
                parity_fn=lambda b: ParityVerdict(PARITY_PASS),
                benchmark_fn=lambda b: 10.0,
                run_step=lambda script, args, prefix, timeout: (None, False, ""))
            # The only piece that would want a real clang.
            ad["compile_fn"] = lambda cpp: (True, "", "bundle")
            return ad

        return factory

    def test_a_cancelled_model_call_stops_the_run_instead_of_erroring_a_round(self):
        from mpynode.native.ai.llm_client import PortCancelled

        def cancelled(system, user):
            raise PortCancelled()

        started, lines = [], []
        with tempfile.TemporaryDirectory() as tmp:
            first = self._write(tmp, "aNode", _BASELINE_CPP)
            second = self._write(tmp, "bNode", _BASELINE_CPP)
            res = optimizer_live.optimize_surviving(
                [("aNode", first, _SPEC), ("bNode", second, _SPEC)], tmp,
                verify_fn=lambda b, r: {}, rounds=3,
                adapters_factory=self._factory(tmp, cancelled, started),
                log_cb=lines.append)

        self.assertEqual(res, {}, "a cancelled node must not report a result")
        self.assertEqual(started, ["aNode"],
                         "the nodes after the cancel must never start")
        self.assertEqual([ln for ln in lines if "round 1: error" in ln], [],
                         "the cancel was recorded as a round error: %r" % lines)
        self.assertEqual([ln for ln in lines if "round 2/3" in ln], [],
                         "the loop went on to the next round: %r" % lines)
        self.assertTrue([ln for ln in lines if "cancelled during aNode" in ln],
                        "the cancel was never narrated: %r" % lines)

    def test_the_carrier_is_not_an_exception_so_the_engine_cannot_swallow_it(self):
        """The load-bearing detail: ``optimizer.optimize_cpp``'s per-round guard
        is ``except Exception``, and the pure engine must not learn about the
        LLM client to let a cancel past it."""
        self.assertTrue(issubclass(optimizer_live._OptimizeCancelled,
                                   BaseException))
        self.assertFalse(issubclass(optimizer_live._OptimizeCancelled,
                                    Exception))

    def test_an_already_set_event_skips_the_node_before_its_baseline_compile(self):
        """Only the model-calling adapters are cancel-guarded, so without the
        between-nodes check the next node still pays a full baseline compile +
        benchmark before anything notices."""
        started, lines = [], []

        def engine(baseline, **kw):
            raise AssertionError("the engine must not run after a cancel")

        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "aNode", _BASELINE_CPP)
            ev = threading.Event()
            ev.set()
            res = optimizer_live.optimize_surviving(
                [("aNode", cpp, _SPEC)], tmp, verify_fn=lambda b, r: {},
                cancel_event=ev, engine=engine, log_cb=lines.append,
                adapters_factory=self._factory(tmp, lambda s, u: "", started))

        self.assertEqual(res, {})
        self.assertEqual(started, [])
        self.assertTrue([ln for ln in lines if "cancelled before aNode" in ln],
                        "%r" % lines)


class TestOptimizeSurvivingChainsTheAdapterCallback(unittest.TestCase):
    """The engine takes ONE round_cb and there are now two consumers: the
    durable per-round .cpp writer and the adapters' entry-baseline update."""

    def _write(self, tmp, name, text):
        p = os.path.join(tmp, name + ".cpp")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def _factory(self, seen):
        def factory(spec, out_dir, **kw):
            return {"round_cb": lambda rec, cpp: seen.append(rec.outcome)}
        return factory

    def _engine(self, rec):
        from mpynode.native.ai.optimizer import OptimizeResult

        def engine(baseline, round_cb=None, **kw):
            round_cb(rec, "// text")
            return OptimizeResult(False, baseline, 1.0, 1.0, 1.0, 1, [], "x")
        return engine

    def test_both_the_adapter_hook_and_the_version_writer_run(self):
        from mpynode.native.ai.optimizer import RoundRecord
        from mpynode.native.compiler import bundler
        seen = []
        rec = RoundRecord(1, "accept", slug="hoist_invariant", ms=8.0)
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "kDTree", "BASE")
            optimizer_live.optimize_surviving(
                [("kDTree", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=self._engine(rec),
                adapters_factory=self._factory(seen))
            stage = os.path.join(bundler.stage_dir_for(tmp, "kDTree"),
                                 "3_optimized")
            self.assertEqual(sorted(os.listdir(stage)),
                             ["01_hoist_invariant.cpp"])
        self.assertEqual(seen, ["accept"])

    def test_the_adapter_hook_runs_before_the_version_writer(self):
        """_emit_round swallows the whole callback, and the version writer CAN
        raise (a non-str slug reaches _slugify). Ordering the hook second would
        put the baseline update back inside that blast radius."""
        from mpynode.native.ai.optimizer import RoundRecord
        seen = []
        rec = RoundRecord(1, "accept", slug=123, ms=8.0)   # writer will raise
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "kDTree", "BASE")
            optimizer_live.optimize_surviving(
                [("kDTree", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=self._engine(rec),
                adapters_factory=self._factory(seen))
        self.assertEqual(seen, ["accept"])


class TestANoChangeRoundLeavesNoDuplicateOnDisk(unittest.TestCase):
    """A no-change round produced no source of its own -- the text handed to
    the writer IS the incumbent. Kept as a .cpp it was a byte-identical
    duplicate filed under the slug the agent CLAIMED (01_simd_lanes.cpp), so
    anyone md5-ing 3_optimized/ saw work that never happened. Dropped outright
    it left an unexplained hole in the index, which reads as a lost file. It
    leaves a MARKER instead: the round is accounted for, and nothing there
    looks like source that was produced."""

    def _dir(self, tmp):
        from mpynode.native.compiler import bundler

        return os.path.join(bundler.stage_dir_for(tmp, "kDTree"), "3_optimized")

    def _no_change_round(self, tmp):
        from mpynode.native.ai.optimizer import RoundRecord

        write = optimizer_live.make_version_writer(tmp, "kDTree")
        self.assertTrue(write(RoundRecord(0, "baseline"), "BASE\n"))
        rec = RoundRecord(1, "no-change", slug="simd_lanes",
                          note="candidate is identical to the current best")
        return write, write(rec, "BASE\n")

    def test_the_claimed_slug_never_reaches_the_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._no_change_round(tmp)
            names = sorted(os.listdir(self._dir(tmp)))
            self.assertEqual([n for n in names if n.endswith(".cpp")],
                             ["00_baseline.cpp"])
            self.assertFalse([n for n in names if "simd_lanes" in n], names)

    def test_the_round_still_occupies_its_place_in_the_index(self):
        """00 then 02 reads as a file someone deleted. The marker says what
        actually happened, and is not a .cpp -- so no reader, and no md5 sweep,
        can mistake it for source the round produced."""
        with tempfile.TemporaryDirectory() as tmp:
            _w, path = self._no_change_round(tmp)
            names = sorted(os.listdir(self._dir(tmp)))
            filled = [n for n in names if n.startswith("01_")]
            self.assertEqual(len(filled), 1, names)
            self.assertFalse(filled[0].endswith(".cpp"), filled)
            self.assertEqual(path, os.path.join(self._dir(tmp), filled[0]))
            with open(path) as fh:
                self.assertIn("no-change", fh.read())

    def test_a_real_reject_is_still_kept(self):
        """The directory's whole reason to exist -- an attempt that measured
        SLOWER must survive."""
        from mpynode.native.ai.optimizer import RoundRecord

        with tempfile.TemporaryDirectory() as tmp:
            write = optimizer_live.make_version_writer(tmp, "kDTree")
            write(RoundRecord(0, "baseline"), "BASE\n")
            write(RoundRecord(1, "not-faster", slug="soa_split"), "SOA\n")
            self.assertEqual(sorted(os.listdir(self._dir(tmp))),
                             ["00_baseline.cpp", "01_soa_split.cpp"])


class TestOptimizeSurvivingLogRouting(unittest.TestCase):
    """The engine's high-level narration (baseline / ACCEPT / reject) and the
    noisy per-line streams (raw compiler output, AI chain-of-thought) must go to
    SEPARATE callbacks. The dialog hook only listens to the narration one; the
    flood the user saw came from make_adapters funnelling the compiler stream
    through the SAME callback the engine narrates on."""

    def _write(self, tmp, name, text):
        p = os.path.join(tmp, name + ".cpp")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def test_engine_and_adapter_log_cbs_are_distinct(self):
        from mpynode.native.ai.optimizer import OptimizeResult
        seen = {}

        def factory(spec, out_dir, **kw):
            seen["adapters_log_cb"] = kw.get("log_cb")
            return {}

        def engine(baseline, **kw):
            seen["engine_log_cb"] = kw.get("log_cb")
            return OptimizeResult(False, baseline, 1.0, 1.0, 1.0, 0, [], "x")

        eng_cb, comp_cb = (lambda m: None), (lambda m: None)
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "n", "BASE")
            optimizer_live.optimize_surviving(
                [("n", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=engine,
                adapters_factory=factory, log_cb=eng_cb, compile_log_cb=comp_cb)
        # The engine narrates on log_cb; the adapters (compiler/AI streams) get
        # the SEPARATE compile_log_cb -- never the engine's narration callback.
        self.assertIs(seen["engine_log_cb"], eng_cb)
        self.assertIs(seen["adapters_log_cb"], comp_cb)
        self.assertIsNot(seen["adapters_log_cb"], eng_cb)

    def test_compile_log_cb_defaults_off_so_streams_are_silenced(self):
        from mpynode.native.ai.optimizer import OptimizeResult
        seen = {}

        def factory(spec, out_dir, **kw):
            seen["adapters_log_cb"] = kw.get("log_cb")
            return {}

        def engine(baseline, **kw):
            seen["engine_log_cb"] = kw.get("log_cb")
            return OptimizeResult(False, baseline, 1.0, 1.0, 1.0, 0, [], "x")

        eng_cb = lambda m: None
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "n", "BASE")
            optimizer_live.optimize_surviving(
                [("n", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=engine,
                adapters_factory=factory, log_cb=eng_cb)  # no compile_log_cb
        # Engine still narrates; the noisy streams are dropped (None) by default
        # so a default dialog build never floods the log.
        self.assertIs(seen["engine_log_cb"], eng_cb)
        self.assertIsNone(seen["adapters_log_cb"])


class TestOptimizerRewriteTimeout(unittest.TestCase):
    """#56 root cause: the optimizer's full-file rewrite LLM call inherited the
    porter's 600s (MPYNODE_PORT_TIMEOUT) cap, so a large node (metaballs) timed
    out every round and the optimizer silently kept the original. The rewrite
    must get its own generous, separately-tunable budget."""

    def test_optimize_cli_timeout_default_is_generous(self):
        old = os.environ.pop("MPYNODE_OPT_TIMEOUT", None)
        try:
            self.assertEqual(optimizer_live._optimize_cli_timeout(), 2400.0)
        finally:
            if old is not None:
                os.environ["MPYNODE_OPT_TIMEOUT"] = old

    def test_optimize_cli_timeout_env_override(self):
        old = os.environ.get("MPYNODE_OPT_TIMEOUT")
        os.environ["MPYNODE_OPT_TIMEOUT"] = "1234"
        try:
            self.assertEqual(optimizer_live._optimize_cli_timeout(), 1234.0)
        finally:
            if old is None:
                os.environ.pop("MPYNODE_OPT_TIMEOUT", None)
            else:
                os.environ["MPYNODE_OPT_TIMEOUT"] = old

    def test_make_adapters_builds_complete_fn_with_optimizer_timeout(self):
        # When make_adapters builds the DEFAULT complete_fn (none injected), it
        # must hand make_cli_complete_fn the optimizer budget -- NOT the 600s
        # porter cap (which was None -> _cli_timeout() -> 600 before the fix).
        from mpynode.native.ai import llm_client
        seen = {}

        def fake_make(cancel_event=None, log_cb=None, timeout=None,
                      max_tokens=None):
            seen["timeout"] = timeout
            seen["max_tokens"] = max_tokens
            return lambda system, user: "```cpp\nX;\n```"

        old = os.environ.pop("MPYNODE_OPT_TIMEOUT", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with mock.patch.object(llm_client, "make_cli_complete_fn",
                                       fake_make):
                    optimizer_live.make_adapters(
                        _SPEC, tmp, maya="/x",
                        run_step=lambda script, args, prefix, timeout:
                            (None, False, ""))
            self.assertEqual(seen["timeout"], 2400.0)
            self.assertEqual(seen["max_tokens"], 64000)
        finally:
            if old is not None:
                os.environ["MPYNODE_OPT_TIMEOUT"] = old


class TestApiRequestHonoursTheOptimizerBudget(unittest.TestCase):
    """Without a tool-using CLI the optimizer asks for the WHOLE .cpp back, so
    the API request needs both a response ceiling big enough to hold it and a
    deadline long enough to generate it. The caller already supplies both;
    ``make_cli_complete_fn`` used to honour them for CLI providers and drop
    them on the floor for API ones."""

    def _capture(self, provider, fn_kw, sys_txt="sys", user_txt="user"):
        from mpynode.native.ai import llm_client
        seen = {}

        def fake_http(url, payload, headers, timeout=120.0, cancel_event=None):
            seen["url"], seen["payload"], seen["timeout"] = url, payload, timeout
            seen["cancel_event"] = cancel_event
            if provider == "gemini":
                return {"candidates": [{"content": {"parts": [{"text": "X;"}]}}]}
            return {"content": [{"type": "text", "text": "X;"}]}

        with mock.patch.object(llm_client._config, "get_provider",
                               lambda: provider), \
             mock.patch.object(llm_client._config, "get_model",
                               lambda p: "m"), \
             mock.patch.object(llm_client._config, "get_api_key",
                               lambda p: "k"), \
             mock.patch.object(llm_client, "_http_json", fake_http):
            llm_client.make_cli_complete_fn(**fn_kw)(sys_txt, user_txt)
        return seen

    def test_anthropic_request_uses_caller_max_tokens_and_timeout(self):
        seen = self._capture("anthropic",
                             {"timeout": 1234.0, "max_tokens": 64000})
        self.assertEqual(seen["payload"]["max_tokens"], 64000)
        self.assertEqual(seen["timeout"], 1234.0)

    def test_gemini_request_uses_caller_max_tokens(self):
        # A separate literal from the anthropic one -- easy to update only half.
        seen = self._capture("gemini", {"timeout": 1234.0, "max_tokens": 64000})
        self.assertEqual(
            seen["payload"]["generationConfig"]["maxOutputTokens"], 64000)

    def test_unbounded_timeout_is_passed_as_none(self):
        """socket.settimeout(inf) raises OverflowError, so the "optimize
        timeout disabled" sentinel must become None (= block forever), the same
        mapping _build_cli already does for subprocess.run."""
        seen = self._capture("anthropic",
                             {"timeout": float("inf"), "max_tokens": 64000})
        self.assertIsNone(seen["timeout"])

    def test_porter_path_is_unchanged(self):
        """The porter asks only for the marked compute region and shares this
        transport. A cap above a user-typed model's own limit is a 400 that is
        not retryable and there aborts the whole port, so stage 2 keeps the
        conservative shipped defaults."""
        from mpynode.native.ai import llm_client
        seen = {}

        def fake_http(url, payload, headers, timeout=120.0, cancel_event=None):
            seen["payload"], seen["timeout"] = payload, timeout
            seen["cancel_event"] = cancel_event
            return {"content": [{"type": "text", "text": "X;"}]}

        with mock.patch.object(llm_client._config, "get_provider",
                               lambda: "anthropic"), \
             mock.patch.object(llm_client._config, "get_model", lambda p: "m"), \
             mock.patch.object(llm_client._config, "get_api_key", lambda p: "k"), \
             mock.patch.object(llm_client, "_http_json", fake_http):
            llm_client._complete("sys", "user")
        self.assertEqual(seen["payload"]["max_tokens"], 4096)
        self.assertEqual(seen["timeout"], 120.0)

    def test_openai_is_refused_rather_than_posted_to_anthropic(self):
        """openai is in config.API_PROVIDERS but this transport has no openai
        branch -- it fell through to the anthropic payload, sending the user's
        OpenAI key to api.anthropic.com. Refuse instead."""
        from mpynode.native.ai import llm_client

        def boom(*a, **k):
            raise AssertionError("must not reach the network")

        with mock.patch.object(llm_client._config, "get_provider",
                               lambda: "openai"), \
             mock.patch.object(llm_client._config, "get_model", lambda p: "m"), \
             mock.patch.object(llm_client._config, "get_api_key", lambda p: "k"), \
             mock.patch.object(llm_client, "_http_json", boom):
            with self.assertRaises(RuntimeError) as ctx:
                llm_client._complete("sys", "user")
        self.assertIn("openai", str(ctx.exception).lower())


class TestApiCancelReachesTheRetryLoop(unittest.TestCase):
    """``config.request_with_retry`` has always polled a ``should_cancel`` hook
    -- before every attempt and every 0.2s of a 429/5xx backoff -- and the
    transport never passed one, so Cancel could not interrupt a rate-limit wait
    or land between retries. Passing it must NOT disturb the porter, which binds
    ``_complete`` bare: the request it emits has to stay byte-identical."""

    def _spy(self, call):
        """Run ``call(llm_client)`` with the network + retry helper spied.

        Captures the exact ``urllib`` Request (method / URL / body bytes /
        headers) and the kwargs the transport hands ``request_with_retry``.
        """
        from mpynode.native.ai import llm_client
        seen = {}

        class _Resp:
            def __enter__(_s):
                return _s

            def __exit__(_s, *a):
                return False

            def read(_s):
                return b'{"content": [{"type": "text", "text": "X;"}]}'

        def fake_urlopen(req, timeout=None, context=None):
            seen["method"] = req.get_method()
            seen["url"] = req.full_url
            seen["body"] = req.data
            seen["headers"] = dict(req.header_items())
            seen["timeout"] = timeout
            return _Resp()

        def fake_retry(do_request, **kw):
            seen["retry_kwargs"] = kw
            return do_request()

        with mock.patch.object(llm_client._config, "get_provider",
                               lambda: "anthropic"), \
             mock.patch.object(llm_client._config, "get_model", lambda p: "m"), \
             mock.patch.object(llm_client._config, "get_api_key", lambda p: "k"), \
             mock.patch.object(llm_client.urllib.request, "urlopen",
                               fake_urlopen), \
             mock.patch.object(llm_client._config, "request_with_retry",
                               fake_retry):
            call(llm_client)
        return seen

    def test_the_porter_request_is_byte_identical_and_passes_no_hook(self):
        """The porter and the OSL converter bind ``_complete`` bare, so their
        cancel_event stays None. Compared field by field against the optimizer's
        request rather than assumed: this is the one path where a silent change
        would alter shipped compiles."""
        ev = threading.Event()
        porter_seen = self._spy(lambda lc: lc._complete("sys", "user"))
        opt_seen = self._spy(
            lambda lc: lc.make_cli_complete_fn(cancel_event=ev)("sys", "user"))

        for field in ("method", "url", "body", "headers"):
            self.assertEqual(porter_seen[field], opt_seen[field],
                             "cancel plumbing changed the emitted %s" % field)
        self.assertEqual(porter_seen["method"], "POST")
        self.assertEqual(porter_seen["url"],
                         "https://api.anthropic.com/v1/messages")
        self.assertIsNone(porter_seen["retry_kwargs"]["should_cancel"],
                          "the porter must not acquire a cancel hook")
        self.assertEqual(opt_seen["retry_kwargs"]["should_cancel"], ev.is_set,
                         "the optimizer's event must reach the retry loop")

    def test_an_already_set_cancel_stops_before_the_request_is_sent(self):
        from mpynode.native.ai import llm_client
        ev = threading.Event()
        ev.set()

        def boom(*a, **k):
            raise AssertionError("must not reach the network")

        with mock.patch.object(llm_client._config, "get_provider",
                               lambda: "anthropic"), \
             mock.patch.object(llm_client._config, "get_model", lambda p: "m"), \
             mock.patch.object(llm_client._config, "get_api_key", lambda p: "k"), \
             mock.patch.object(llm_client.urllib.request, "urlopen", boom):
            with self.assertRaises(llm_client.PortCancelled):
                llm_client._complete("sys", "user", cancel_event=ev)

    def test_cancel_interrupts_a_rate_limit_backoff(self):
        """A 429 with ``Retry-After: 30`` used to mean 30 unresponsive seconds.
        The hook is polled every 0.2s of that wait, so Cancel lands mid-backoff
        -- and the CancelledError surfaces as the PortCancelled the callers
        already handle."""
        import urllib.error
        from mpynode.native.ai import llm_client
        ev = threading.Event()

        def rate_limited(req, timeout=None, context=None):
            threading.Timer(0.05, ev.set).start()
            raise urllib.error.HTTPError(
                req.full_url, 429, "Too Many Requests",
                {"Retry-After": "30"}, None)

        t0 = time.time()
        with mock.patch.object(llm_client._config, "get_provider",
                               lambda: "anthropic"), \
             mock.patch.object(llm_client._config, "get_model", lambda p: "m"), \
             mock.patch.object(llm_client._config, "get_api_key", lambda p: "k"), \
             mock.patch.object(llm_client.urllib.request, "urlopen",
                               rate_limited):
            with self.assertRaises(llm_client.PortCancelled):
                llm_client._complete("sys", "user", cancel_event=ev)
        self.assertLess(time.time() - t0, 10.0,
                        "the cancel waited out the 30s Retry-After")


class TestPreoptBackupAndRollback(unittest.TestCase):
    """#66: on ACCEPT the node's real .cpp is overwritten with the winner, but a
    backup of the deterministic original is written to ``<cpp>.preopt`` FIRST so
    the build can fall back to it if the accepted candidate later fails the FINAL
    (multi-node) assemble."""

    def _write(self, tmp, name, text):
        p = os.path.join(tmp, name + ".cpp")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def test_accept_writes_preopt_backup(self):
        from mpynode.native.ai.optimizer import OptimizeResult
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "mPyThing", "BASELINE")
            engine = lambda baseline, **kw: OptimizeResult(
                True, "WINNER", 100.0, 10.0, 10.0, 1, [], "accepted")
            optimizer_live.optimize_surviving(
                [("mPyThing", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=engine,
                adapters_factory=lambda *a, **k: {})
            self.assertTrue(os.path.exists(cpp + ".preopt"))
            with open(cpp + ".preopt") as fh:
                self.assertEqual(fh.read(), "BASELINE")   # original preserved
            with open(cpp) as fh:
                self.assertEqual(fh.read(), "WINNER")     # winner shipped

    def test_reject_writes_no_preopt(self):
        from mpynode.native.ai.optimizer import OptimizeResult
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "mPyThing", "BASELINE")
            engine = lambda baseline, **kw: OptimizeResult(
                False, baseline, 1.0, 1.0, 1.0, 0, [], "no gain")
            optimizer_live.optimize_surviving(
                [("mPyThing", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=engine,
                adapters_factory=lambda *a, **k: {})
            self.assertFalse(os.path.exists(cpp + ".preopt"))

    def test_rollback_restores_and_returns(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "n", "OPTIMIZED")
            with open(cpp + ".preopt", "w") as fh:
                fh.write("DETERMINISTIC")
            restored = optimizer_live.rollback_preopt([cpp])
            self.assertEqual(restored, [cpp])
            with open(cpp) as fh:
                self.assertEqual(fh.read(), "DETERMINISTIC")  # original back
            self.assertFalse(os.path.exists(cpp + ".preopt"))  # backup consumed

    def test_rollback_noop_when_no_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "n", "X")
            self.assertEqual(optimizer_live.rollback_preopt([cpp]), [])
            with open(cpp) as fh:
                self.assertEqual(fh.read(), "X")

    def test_discard_removes_preopt(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._write(tmp, "n", "SHIP")
            with open(cpp + ".preopt", "w") as fh:
                fh.write("ORIG")
            optimizer_live.discard_preopt([cpp])
            self.assertFalse(os.path.exists(cpp + ".preopt"))
            with open(cpp) as fh:
                self.assertEqual(fh.read(), "SHIP")       # shipped file untouched


class TestOptimizeTimeoutUnbounded(unittest.TestCase):
    """#65: the timeout is disable-able. An 'off'/'none'/'inf' sentinel in
    MPYNODE_OPT_TIMEOUT (set by the UI from the preference) means UNBOUNDED."""

    def _with_env(self, val):
        old = os.environ.get("MPYNODE_OPT_TIMEOUT")
        os.environ["MPYNODE_OPT_TIMEOUT"] = val
        try:
            return optimizer_live._optimize_cli_timeout()
        finally:
            if old is None:
                os.environ.pop("MPYNODE_OPT_TIMEOUT", None)
            else:
                os.environ["MPYNODE_OPT_TIMEOUT"] = old

    def test_off_sentinel_returns_inf(self):
        self.assertEqual(self._with_env("off"), float("inf"))

    def test_none_sentinel_returns_inf(self):
        self.assertEqual(self._with_env("none"), float("inf"))

    def test_numeric_value_is_finite(self):
        self.assertEqual(self._with_env("321"), 321.0)


class TestLLMClientUnboundedTimeout(unittest.TestCase):
    """#65: a float('inf') timeout means UNBOUNDED at the LLM client. On the
    blocking path that becomes subprocess.run(timeout=None) (block until exit);
    a None timeout still collapses to the shipped default (porter unchanged)."""

    class _FakeProc:
        stdout = "OUT"
        stderr = ""
        returncode = 0

    def _run_with(self, timeout):
        from mpynode.native.ai import llm_client
        seen = {}

        def fake_run(cmd, **kw):
            seen["timeout"] = kw.get("timeout")
            return self._FakeProc()

        with mock.patch.object(llm_client.subprocess, "run", fake_run), \
                mock.patch.object(llm_client, "_extract_cli_output",
                                  lambda *a, **k: "OUT"):
            out = llm_client._run_cli_proc(["x"], None, "bin", timeout=timeout)
        self.assertEqual(out, "OUT")
        return seen["timeout"]

    def test_inf_passes_none_to_subprocess_run(self):
        self.assertIsNone(self._run_with(float("inf")))

    def test_none_uses_shipped_default(self):
        from mpynode.native.ai import llm_client
        self.assertEqual(self._run_with(None), llm_client._cli_timeout())

    def test_finite_passes_through(self):
        self.assertEqual(self._run_with(123.0), 123.0)


class TestRunStepCancellable(unittest.TestCase):
    """Closing the compile window must KILL an in-flight AI-optimize child
    mayapy (benchmark/parity), not let it run to its own timeout in the
    background. The DEFAULT run_step (built by _make_run_step when the pipeline
    injects no runner) is therefore cancel-aware: it terminates the child as soon
    as cancel_event fires."""

    class _BlockingProc:
        """communicate() blocks until terminate()/kill() unblocks it -- models a
        long-running child mayapy so the poll loop must terminate it to proceed."""

        def __init__(self):
            self._done = threading.Event()
            self.returncode = None
            self.terminated = False

        def communicate(self, input=None):
            self._done.wait(5)
            return (b"", None)

        def terminate(self):
            self.terminated = True
            self.returncode = -15
            self._done.set()

        def kill(self):
            self.terminated = True
            self.returncode = -9
            self._done.set()

        def wait(self, timeout=None):
            self._done.wait(timeout)
            return self.returncode

        def poll(self):
            return self.returncode

    class _OKProc:
        returncode = 0

        def communicate(self, input=None):
            return (b'PFX:{"median_ms": 3.0}\n', None)

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def terminate(self):
            pass

        def kill(self):
            pass

    def test_cancelled_run_step_terminates_child(self):
        ev = threading.Event()
        ev.set()  # already cancelled -> first poll aborts immediately
        fake = self._BlockingProc()
        with tempfile.TemporaryDirectory() as tmp:
            run_step = optimizer_live._make_run_step(
                "/bin/mayapy", tmp, 1800, cancel_event=ev)
            with mock.patch.object(optimizer_live.subprocess, "Popen",
                                   return_value=fake):
                data, ok, tail = run_step("script.py", [], "PFX:")
        self.assertIsNone(data)
        self.assertFalse(ok)
        self.assertIn("cancel", tail.lower())
        self.assertTrue(fake.terminated)  # child actually killed

    def test_uncancelled_run_step_returns_parsed_output(self):
        # The cancel-aware path must preserve the (data, ok, tail) contract.
        ev = threading.Event()  # not set
        with tempfile.TemporaryDirectory() as tmp:
            run_step = optimizer_live._make_run_step(
                "/bin/mayapy", tmp, 1800, cancel_event=ev)
            with mock.patch.object(optimizer_live.subprocess, "Popen",
                                   return_value=self._OKProc()):
                data, ok, tail = run_step("script.py", [], "PFX:")
        self.assertEqual(data, {"median_ms": 3.0})
        self.assertTrue(ok)


class TestHeartbeatSubPhase(unittest.TestCase):
    """The liveness tick must name the sub-phase it is actually timing.

    A round is propose -> build -> parity -> benchmark; labelling all of it
    "AI working" produced ticks like "round 5/8 -- AI working 10m23s" minutes
    after the round's own "trying: ..." line proved the model call had returned,
    and past the budget it claimed to be timing.
    """

    def test_each_adapter_names_its_own_phase(self):
        hb = optimizer_live._Heartbeat(None, "kDTree")
        hb.set_round(2, 8)
        ad = {"optimize_fn": lambda c: c, "fix_fn": lambda c, e: c,
              "compile_fn": lambda c: (True, "", "/b"),
              "parity_fn": lambda b: None, "benchmark_fn": lambda b: 1.0}
        optimizer_live._wrap_phases(ad, hb)

        seen = []
        for key, args in (("optimize_fn", ("x",)), ("compile_fn", ("x",)),
                          ("parity_fn", ("/b",)), ("benchmark_fn", ("/b",)),
                          ("fix_fn", ("x", "err"))):
            ad[key](*args)
            seen.append(hb._phase[0])
        self.assertEqual(seen, ["round 2/8 -- AI working",
                                "round 2/8 -- building C++",
                                "round 2/8 -- checking parity",
                                "round 2/8 -- benchmarking",
                                "round 2/8 -- AI repairing the build"])

    def test_each_phase_restarts_the_clock(self):
        """The number is only honest as "how long has THIS been running"."""
        hb = optimizer_live._Heartbeat(None, "n")
        hb.set_round(1, 2)
        first = hb._phase[1]
        hb.set_phase("benchmarking")
        self.assertGreaterEqual(hb._phase[1], first)
        self.assertEqual(hb._phase[0], "round 1/2 -- benchmarking")

    def test_wrapping_preserves_the_adapter_contract(self):
        hb = optimizer_live._Heartbeat(None, "n")
        ad = {"benchmark_fn": lambda b: 12.5}
        optimizer_live._wrap_phases(ad, hb)
        self.assertEqual(ad["benchmark_fn"]("/bundle"), 12.5)

    def test_a_factory_that_supplied_no_adapters_is_not_invented_into_one(self):
        hb = optimizer_live._Heartbeat(None, "n")
        ad = {}
        optimizer_live._wrap_phases(ad, hb)
        self.assertEqual(ad, {})

    def test_past_the_last_round_the_label_stops_claiming_a_round(self):
        """`index > total` used to return, freezing the label on the final
        round for the whole post-loop tail -- and on "measuring baseline"
        forever for a rounds=0 run."""
        hb = optimizer_live._Heartbeat(None, "n")
        hb.set_round(3, 3)
        hb.set_round(4, 3)
        self.assertNotIn("round 3/3", hb._phase[0])
        self.assertEqual(hb._phase[0], "finishing up")

        hb0 = optimizer_live._Heartbeat(None, "n")
        hb0.set_round(1, 0)
        self.assertEqual(hb0._phase[0], "finishing up")


def _heartbeat_lines(want=2, interval=0.02):
    """Drive a real _Heartbeat through round 1/2 at a SQUEEZED interval and
    return the lines it emitted. Never the shipped 300s: the label and the reset
    are what is under test, not the wall clock."""
    seen = []
    hb = optimizer_live._Heartbeat(seen.append, "kDTree", interval=interval)
    with hb:
        hb.set_round(1, 2)
        deadline = time.time() + 5.0
        while len(seen) < want and time.time() < deadline:
            time.sleep(0.01)
    return seen


class TestHeartbeatTick(unittest.TestCase):
    """What the liveness line actually SAYS, and how often it says it."""

    def test_elapsed_reads_as_a_duration_not_a_four_digit_second_count(self):
        """One run's counter reached 5656 -- unreadable as a raw number."""
        self.assertEqual(
            [optimizer_live._fmt_elapsed(s) for s in (7, 59, 60, 252, 5656)],
            ["7s", "59s", "1m00s", "4m12s", "94m16s"])

    def test_a_tick_names_the_node_the_phase_and_how_long_that_phase_ran(self):
        seen = _heartbeat_lines()

        self.assertEqual(seen[0], "[kDTree] optimizing -- measuring baseline",
                         "the t=0 beat is what lights the AI-optimize "
                         "checkpoint; a 5-minute wait for it is too late")
        self.assertRegex(seen[1], r"^\[kDTree\] round 1/2 -- AI working \d+s$")

    def test_naming_a_round_restarts_the_clock(self):
        """Carried across rounds the number reported the node's age against the
        round's name (it reached 5656s, ~370 lines, on one run)."""
        hb = optimizer_live._Heartbeat(None, "n")
        hb.set_round(1, 3)
        first = hb._phase[1]
        time.sleep(0.01)
        hb.set_round(2, 3)

        self.assertEqual(hb._phase[0], "round 2/3 -- AI working")
        self.assertGreater(hb._phase[1], first)

    def test_the_default_interval_is_five_minutes(self):
        """Ticking is the only thing the user sees during a silent hour, so the
        cadence is a decision, not an implementation detail: shorter and the
        log is heartbeats, longer and a live run reads as hung."""
        import inspect

        interval = inspect.signature(
            optimizer_live._Heartbeat.__init__).parameters["interval"]
        self.assertEqual(interval.default, 300.0)


def _heartbeat_phase_ticks(phases, interval=0.02):
    """Drive a real _Heartbeat through each of ``phases`` (plus the post-loop
    "finishing up" label, reached the way the code reaches it -- ``set_round``
    past the last round) and return ``{phase: the tick it emitted}``. Squeezed
    interval; the wording is under test, not the wall clock."""
    seen = []
    ticks = {}
    hb = optimizer_live._Heartbeat(seen.append, "kDTree", interval=interval)

    def _wait_for(text):
        deadline = time.time() + 5.0
        while time.time() < deadline:
            for ln in seen:
                if text in ln:
                    return ln
            time.sleep(0.01)
        return None

    with hb:
        hb.set_round(1, 2)
        for phase in phases:
            hb.set_phase(phase)
            ticks[phase] = _wait_for(phase)
        hb.set_round(3, 2)
        ticks["finishing up"] = _wait_for("finishing up")
    return ticks


class TestSweepCompileOneDropsTheHeartbeat(unittest.TestCase):
    """``tools/sweep_compile_one.py`` records one line per progress event. The
    heartbeat carries no result and would drown that record, so the script drops
    it -- by matching wording that _Heartbeat owns, in another file. Pinned
    against lines the heartbeat REALLY emits, because a filter that matches
    nothing silently stops filtering (the hand-copied "-- still working" had
    already stopped matching, and none of the five sub-phases were listed)."""

    def _needles(self):
        """The wording the sweep's progress callback filters on. Only ``main()``
        touches Maya, so the module imports fine and the real predicate is used
        instead of a regex over its source."""
        import importlib.util

        path = os.path.join(optimizer_live._project_root(), "tools",
                            "sweep_compile_one.py")
        spec = importlib.util.spec_from_file_location("_sweep_one", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        needles = list(mod._heartbeat_needles())
        self.assertTrue(needles, "the heartbeat filter is gone entirely")
        return needles

    def test_every_phase_the_heartbeat_emits_is_dropped(self):
        """Enumerated from ``_ADAPTER_PHASES`` -- the table the filter derives
        from -- so a sixth sub-phase is covered the day it is added."""
        phases = [p for _key, p in optimizer_live._ADAPTER_PHASES]
        needles = self._needles()
        ticks = _heartbeat_phase_ticks(phases)

        self.assertEqual(sorted(ticks), sorted(phases + ["finishing up"]))
        for phase, tick in sorted(ticks.items()):
            self.assertIsNotNone(tick, "the heartbeat emitted no %r tick"
                                 % phase)
            self.assertTrue([n for n in needles if n in tick],
                            "the sweep would record heartbeat %r" % tick)

    def test_the_filter_matches_a_tick_the_heartbeat_really_emits(self):
        _baseline, tick = _heartbeat_lines()[:2]
        self.assertTrue([n for n in self._needles() if n in tick],
                        "the sweep filters wording nothing emits, so every "
                        "heartbeat now lands in the record: %r" % tick)

    def test_the_one_shot_baseline_line_is_kept(self):
        """It is not a heartbeat -- it says something happened."""
        baseline = _heartbeat_lines()[0]
        self.assertEqual([n for n in self._needles() if n in baseline], [],
                         "an over-broad filter also swallows the one optimize "
                         "line that reports a fact: %r" % baseline)


if __name__ == "__main__":
    unittest.main()
