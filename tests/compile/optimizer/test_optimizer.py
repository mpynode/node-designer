"""The AI-optimizer orchestration engine: a pure, gated loop that accepts a
rewritten .cpp ONLY if it compiles, still passes parity vs the interpreted
Python, AND is measurably faster -- else it keeps the original (honest reject).

All five side-effecting steps are injected, so this suite stubs them and drives
every gate branch with zero Maya / LLM / compiler. Pure logic -> no standalone.
"""

from __future__ import annotations

import unittest

from mpynode.native.ai.optimizer import (
    optimize_cpp, BenchmarkDiverged, ParityVerdict, PARITY_PASS, PARITY_FAIL,
    PARITY_SKIP,
)


def _compile_ok(cpp):
    return (True, "", "b:" + cpp)


def _bench(ms_by_cpp):
    """benchmark_fn keyed on the cpp encoded in the stub bundle path 'b:<cpp>'."""
    return lambda bundle: ms_by_cpp.get(bundle[2:])


def _parity(status):
    return lambda bundle: ParityVerdict(status)


def _bench_seq(*values):
    """Successive measurements, ignoring the bundle. The SAME source measuring
    differently on two runs is the jitter the identity gate exists for."""
    seq = iter(values)
    return lambda bundle: next(seq)


class TestOptimizeAcceptPath(unittest.TestCase):
    def test_accepts_faster_parity_passing_candidate(self):
        res = optimize_cpp(
            "BASE",
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0, "CAND": 40.0}),
            rounds       = 1,
        )
        self.assertTrue(res.accepted)
        self.assertEqual(res.best_cpp, "CAND")
        self.assertAlmostEqual(res.baseline_ms, 100.0)
        self.assertAlmostEqual(res.best_ms, 40.0)
        self.assertGreater(res.speedup, 2.0)


class TestOptimizeRejectPaths(unittest.TestCase):
    def _run(self, **over):
        kw = dict(
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0, "CAND": 40.0}),
            rounds       = 1,
        )
        kw.update(over)
        return optimize_cpp("BASE", **kw)

    def test_rejects_parity_fail(self):
        res = self._run(parity_fn=_parity(PARITY_FAIL))
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")

    def test_rejects_parity_skip_is_not_pass(self):
        # SKIP must never be treated as a pass -- can't prove correctness.
        res = self._run(parity_fn=_parity(PARITY_SKIP))
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")

    def test_rejects_not_measurably_faster(self):
        # 98 ms vs baseline 100 with min_speedup 1.05 -> needs < 95.24 ms.
        res = self._run(benchmark_fn=_bench({"BASE": 100.0, "CAND": 98.0}),
                        min_speedup=1.05)
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")

    def test_rejects_candidate_that_never_compiles_after_fix_loop(self):
        calls = {"fix": 0}

        def compile_fn(cpp):
            return (cpp == "BASE", "err", "b:" + cpp)  # only baseline compiles

        def fix_fn(cpp, errs):
            calls["fix"] += 1
            return "CANDFIX"  # still != BASE -> still won't compile

        res = self._run(compile_fn=compile_fn, fix_fn=fix_fn, max_fix_rounds=2)
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")
        self.assertEqual(calls["fix"], 2)  # fix-loop bounded by max_fix_rounds


class TestOptimizeFixLoop(unittest.TestCase):
    def test_fix_loop_then_accept(self):
        def compile_fn(cpp):
            return (cpp in ("BASE", "CANDFIX"), "err", "b:" + cpp)

        res = optimize_cpp(
            "BASE",
            optimize_fn=lambda cpp: "CAND",       # CAND won't compile
            fix_fn=lambda cpp, errs: "CANDFIX",   # the fix does
            compile_fn   = compile_fn,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0, "CANDFIX": 30.0}),
            rounds=1, max_fix_rounds=2,
        )
        self.assertTrue(res.accepted)
        self.assertEqual(res.best_cpp, "CANDFIX")


class TestOptimizeMultiRound(unittest.TestCase):
    def test_rounds_compound_from_current_best(self):
        seen = []

        def optimize_fn(cpp):
            seen.append(cpp)               # record what each round proposes FROM
            return {"BASE": "CAND1", "CAND1": "CAND2"}[cpp]

        res = optimize_cpp(
            "BASE",
            optimize_fn=optimize_fn,
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0, "CAND1": 50.0, "CAND2": 20.0}),
            rounds       = 2,
        )
        self.assertTrue(res.accepted)
        self.assertEqual(res.best_cpp, "CAND2")     # compounded to the fastest
        self.assertAlmostEqual(res.best_ms, 20.0)
        self.assertAlmostEqual(res.speedup, 5.0)
        # round 2 proposed FROM the round-1 winner, not the baseline.
        self.assertEqual(seen, ["BASE", "CAND1"])


class TestOptimizeBaselineGuard(unittest.TestCase):
    def test_baseline_that_does_not_compile_is_a_safe_noop(self):
        def optimize_fn(cpp):
            raise AssertionError("optimize_fn must not run if baseline is bad")

        res = optimize_cpp(
            "BASE",
            optimize_fn=optimize_fn,
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = lambda cpp: (False, "boom", ""),
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = lambda b: 1.0,
            rounds       = 1,
        )
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")
        self.assertIn("baseline", res.reason.lower())


class TestOptimizeLedger(unittest.TestCase):
    def test_ledger_records_baseline_plus_each_round(self):
        res = optimize_cpp(
            "BASE",
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_FAIL),   # rejected -> honest reject
            benchmark_fn = _bench({"BASE": 100.0, "CAND": 10.0}),
            rounds=3, min_rounds=3,            # fixed count: every round runs
        )
        self.assertFalse(res.accepted)
        self.assertIs(res.best_cpp, "BASE")       # returns the ORIGINAL
        self.assertEqual(res.ledger[0].outcome, "baseline")
        self.assertEqual(len(res.ledger), 1 + 3)  # baseline + 3 rounds
        for rec in res.ledger[1:]:
            self.assertIn("parity", rec.outcome.lower())


class TestValidateFn(unittest.TestCase):
    """``validate_fn`` is the optional pre-check that keeps a truncated / prose
    answer from being compiled, written over the .cpp, or fed to the fix round.
    The engine stays content-agnostic: the C++ policy lives in
    optimizer_knowledge.implausible_reason and is injected here."""

    def _run(self, **over):
        kw = dict(
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0, "CAND": 40.0}),
            rounds       = 1,
        )
        kw.update(over)
        return optimize_cpp("BASE", **kw)

    def test_absent_validate_fn_keeps_the_old_behaviour(self):
        self.assertTrue(self._run().accepted)

    def test_rejected_candidate_is_never_compiled(self):
        seen = []

        def compile_fn(cpp):
            seen.append(cpp)
            return _compile_ok(cpp)

        res = self._run(compile_fn=compile_fn,
                        validate_fn=lambda cand, cur: "truncated")
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")
        self.assertEqual(seen, ["BASE"])          # baseline only; never the cand
        self.assertEqual(res.ledger[-1].outcome, "invalid-candidate")
        self.assertIn("truncated", res.ledger[-1].note)

    def test_a_rejected_fix_does_not_propagate(self):
        # The real failure: a corrupt fix became the input to the next fix, which
        # answered "I need the original source" -- and THAT was written to .cpp.
        compiled = []

        def compile_fn(cpp):
            compiled.append(cpp)
            return (cpp == "BASE", "err", "b:" + cpp)

        res = self._run(compile_fn=compile_fn,
                        fix_fn=lambda cpp, errs: "PROSE",
                        max_fix_rounds=2,
                        validate_fn=lambda cand, cur:
                            "not C++" if cand == "PROSE" else None)
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")
        self.assertNotIn("PROSE", compiled)       # corruption never compiled
        self.assertEqual(res.ledger[-1].outcome, "compile-failed")

    def test_validate_fn_sees_candidate_and_current(self):
        seen = []
        self._run(validate_fn=lambda cand, cur: seen.append((cand, cur)))
        self.assertEqual(seen, [("CAND", "BASE")])


class TestNoChangeCandidate(unittest.TestCase):
    """An ``optimize_fn`` that hands back its input is the optimizer doing
    NOTHING. Allowed through, the round re-compiles and re-benchmarks IDENTICAL
    bytes and timing jitter alone decides the verdict -- a 1.15x "accept" was
    recorded that way against a file byte-identical to its own baseline."""

    SRC = "int f(int n) {\n    return n + 1;\n}\n"

    def _run(self, optimize_fn, *, rounds=1, benchmark_fn=None, **over):
        kw = dict(
            optimize_fn=optimize_fn,
            fix_fn=lambda cpp, errs: cpp,
            compile_fn = _compile_ok,
            parity_fn  = _parity(PARITY_PASS),
            # Re-measuring the same source comes back 10x faster: pure jitter,
            # far past min_speedup. No round may turn that into a win.
            benchmark_fn = benchmark_fn or _bench_seq(100.0, 10.0, 10.0, 10.0),
            rounds       = rounds,
        )
        kw.update(over)
        return optimize_cpp(self.SRC, **kw)

    def test_an_identical_candidate_is_never_accepted(self):
        res = self._run(lambda cpp: cpp)
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, self.SRC)
        self.assertEqual(res.ledger[-1].outcome, "no-change")

    def test_it_is_rejected_before_compile_parity_and_benchmark(self):
        compiled, parity, benched = [], [], []

        def compile_fn(cpp):
            compiled.append(cpp)
            return _compile_ok(cpp)

        def parity_fn(bundle):
            parity.append(bundle)
            return ParityVerdict(PARITY_PASS)

        def benchmark_fn(bundle):
            benched.append(bundle)
            return 100.0 if len(benched) == 1 else 1.0

        res = self._run(lambda cpp: cpp, compile_fn=compile_fn,
                        parity_fn=parity_fn, benchmark_fn=benchmark_fn)

        self.assertFalse(res.accepted)
        self.assertEqual(compiled,     [self.SRC])   # the baseline, nothing after it
        self.assertEqual(parity,       [])
        self.assertEqual(len(benched), 1)

    def test_the_round_is_recorded_with_no_measurement_to_misread(self):
        """What ``write_rounds_json`` serialises verbatim. The old failure read
        as a win precisely because the row carried an ms and a speedup."""
        res = self._run(lambda cpp: cpp)
        rec = res.ledger[-1]
        self.assertEqual(rec.outcome, "no-change")
        self.assertIsNone(rec.ms)
        self.assertIsNone(rec.speedup)
        self.assertNotIn("accept", [r.outcome for r in res.ledger])

    def test_leading_or_trailing_whitespace_alone_is_not_an_edit(self):
        """The one-shot path returns ``prompt._extract_body(...)``, which
        strips, so a model echoing the file back differs from the on-disk
        baseline by a trailing newline. Exact ``==`` would miss it."""
        for cand in (self.SRC + "\n", "\n\n" + self.SRC, self.SRC.rstrip("\n")):
            res = self._run(lambda cpp, c=cand: c)
            self.assertEqual(res.ledger[-1].outcome, "no-change", repr(cand))
            self.assertFalse(res.accepted)

    def test_a_whitespace_change_inside_the_file_is_still_a_real_candidate(self):
        """The normalisation boundary, drawn deliberately at the WHOLE file:
        only its outer edges are ignored. A trailing space added to a LINE is
        still gated as an edit -- spending one round measuring a cosmetic
        change is cheaper than discarding a real optimization."""
        cand = self.SRC.replace("    return n + 1;", "    return n + 1;  ")
        res  = self._run(lambda cpp: cand, benchmark_fn=_bench_seq(100.0, 10.0))
        self.assertTrue(res.accepted)
        self.assertEqual(res.best_cpp, cand)
        self.assertEqual(res.ledger[-1].outcome, "accept")

    def test_a_no_change_round_costs_a_round_but_does_not_abort_the_run(self):
        """Deliberate: a no-change round is NOT proof of a broken optimizer.
        TASK.md tells the agent to revert any edit that did not measure faster,
        so one that tries five things and keeps none returns the file unchanged
        -- an honest round. Aborting there would abandon exactly the hard nodes
        that are worth another attempt. Within ``min_rounds`` the adaptive loop
        therefore never stops on it (here the whole run is guaranteed)."""
        step = {"i": 0}

        def optimize_fn(cpp):
            step["i"] += 1
            return cpp if step["i"] < 3 else "FASTER"

        res = self._run(optimize_fn, rounds=3, min_rounds=3,
                        benchmark_fn=_bench_seq(100.0, 25.0))

        self.assertTrue(res.accepted)
        self.assertEqual(res.best_cpp, "FASTER")
        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "no-change", "no-change", "accept"])


class TestAdaptiveRounds(unittest.TestCase):
    """``rounds`` is a MAXIMUM. The loop always runs ``min_rounds``, then goes
    on only while the last round was accepted with a gain of at least
    ``continue_gain``; the first reject past the floor ends it. Measured need:
    20 of 29 shipped nodes accepted both of a fixed 2 rounds (the second worth a
    median 1.58x), so the count -- not the node -- was ending the work."""

    def _run(self, plan, *, ms, **over):
        """``plan`` maps the incumbent source to the next candidate; ``ms`` maps
        a source to its measured time (a parity-fail candidate never reaches
        the benchmark)."""
        kw = dict(
            optimize_fn=lambda cpp: plan[cpp],
            fix_fn=lambda cpp, errs: cpp,
            compile_fn=_compile_ok,
            parity_fn=lambda b: ParityVerdict(
                PARITY_FAIL if b[2:].startswith("BAD") else PARITY_PASS),
            benchmark_fn = _bench(ms),
            rounds       = 6,
        )
        kw.update(over)
        return optimize_cpp("BASE", **kw)

    def test_stops_after_the_first_reject_past_min_rounds(self):
        res = self._run({"BASE": "C1", "C1": "BAD2", "BAD2": "C3"},
                        ms={"BASE": 100.0, "C1": 50.0, "C3": 10.0})
        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "accept", "parity-fail"])
        self.assertEqual(res.rounds,     2)               # rounds RUN, not the cap
        self.assertEqual(res.max_rounds, 6)
        self.assertEqual(res.best_cpp,   "C1")
        self.assertIn("round 2 parity-fail", res.stop_reason)

    def test_min_rounds_always_run_even_after_a_reject(self):
        # Round 1 is a no-change (rejected); the floor of 2 still grants round 2,
        # which wins, and the loop then continues on merit.
        plan = {"BASE": "BASE", "C2": "C3", "C3": "C4"}
        step = {"n": 0}

        def optimize_fn(cpp):
            step["n"] += 1
            return "C2" if step["n"] == 2 else plan[cpp]

        res = self._run({}, ms={"BASE": 100.0, "C2": 50.0, "C3": 25.0,
                                "C4": 24.0},
                        optimize_fn=optimize_fn)
        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "no-change", "accept", "accept",
                          "not-faster"])
        self.assertEqual(res.rounds, 4)
        self.assertIn("round 4 not-faster", res.stop_reason)

    def test_continues_while_gains_hold_and_stops_on_a_small_one(self):
        res = self._run({"BASE": "C1", "C1": "C2", "C2": "C3", "C3": "C4"},
                        ms={"BASE": 100.0, "C1": 50.0, "C2": 25.0, "C3": 23.0,
                            "C4": 1.0})
        # 100 -> 50 (2x) -> 25 (2x) -> 23 (1.09x: accepted, but below 1.15x, so
        # no round 4 even though C4 would have been 23x).
        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "accept", "accept", "accept"])
        self.assertEqual(res.best_cpp, "C3")
        self.assertAlmostEqual(res.best_ms, 23.0)
        self.assertEqual(res.rounds, 3)
        self.assertIn("1.09x", res.stop_reason)
        self.assertIn("1.15x", res.stop_reason)

    def test_the_cap_still_holds(self):
        res = self._run({"BASE": "C1", "C1": "C2", "C2": "C3", "C3": "C4"},
                        ms={"BASE": 100.0, "C1": 50.0, "C2": 25.0, "C3": 12.0,
                            "C4": 6.0}, rounds=3)
        self.assertEqual(res.rounds,      3)
        self.assertEqual(res.best_cpp,    "C3")
        self.assertEqual(res.stop_reason, "max rounds (3) reached")

    def test_zero_rounds_measures_the_baseline_only(self):
        res = self._run({"BASE": "C1"}, ms={"BASE": 100.0, "C1": 1.0}, rounds=0)
        self.assertFalse(res.accepted)
        self.assertEqual(res.rounds,      0)
        self.assertEqual(res.max_rounds,  0)
        self.assertEqual(len(res.ledger), 1)

    def test_a_fixed_count_is_still_available(self):
        # min_rounds == rounds reproduces the old behaviour exactly: every round
        # runs whatever happened before it.
        res = self._run({"BASE": "BAD1", "BAD1": "BAD2", "BAD2": "BAD3"},
                        ms={"BASE": 100.0}, rounds=3, min_rounds=3)
        self.assertEqual(len(res.ledger), 4)
        self.assertEqual(res.rounds, 3)

    def test_stop_reason_is_recorded_when_the_baseline_fails(self):
        res = optimize_cpp(
            "BASE", optimize_fn=lambda cpp: "C", fix_fn=lambda c, e: c,
            compile_fn=lambda cpp: (False, "boom", ""),
            parity_fn=_parity(PARITY_PASS), benchmark_fn=lambda b: 1.0,
            rounds=6)
        self.assertEqual(res.max_rounds, 6)
        self.assertIn("did not compile", res.stop_reason)


class TestSubResolutionConfirmation(unittest.TestCase):
    """Below ``resolution_ms`` the incumbent sits inside the harness's own
    jitter (~8% at 0.4 ms): ``min_speedup`` alone would accept noise. There a
    candidate must clear ``confirm_gain`` on TWO independent measurements, and
    the slower of the two is what the ledger keeps."""

    def _run(self, seq, **over):
        calls = {"n": 0}

        def benchmark_fn(bundle):
            calls["n"] += 1
            return seq[calls["n"] - 1]

        kw = dict(
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = benchmark_fn,
            rounds       = 1,
        )
        kw.update(over)
        return optimize_cpp("BASE", **kw), calls["n"]

    def test_a_gain_inside_the_noise_band_is_not_faster(self):
        # 1.0 -> 0.90 ms is 1.11x: past min_speedup, short of confirm_gain.
        res, n = self._run([1.0, 0.90])
        self.assertFalse(res.accepted)
        self.assertEqual(res.ledger[-1].outcome, "not-faster")
        self.assertIn("required", res.ledger[-1].note)
        self.assertEqual(n, 2)                          # no second measurement

    def test_an_unconfirmed_gain_is_not_faster(self):
        # 0.80 clears 1.15x; the re-measure (0.95) does not.
        res, n = self._run([1.0, 0.80, 0.95])
        self.assertFalse(res.accepted)
        self.assertEqual(res.ledger[-1].outcome, "not-faster")
        self.assertIn("did not confirm", res.ledger[-1].note)
        self.assertAlmostEqual(res.ledger[-1].ms, 0.95)
        self.assertEqual(n, 3)

    def test_a_confirmed_gain_is_accepted_at_the_slower_of_the_two(self):
        res, n = self._run([1.0, 0.80, 0.82])
        self.assertTrue(res.accepted)
        self.assertEqual(res.ledger[-1].outcome, "accept")
        self.assertAlmostEqual(res.ledger[-1].ms, 0.82)
        self.assertAlmostEqual(res.best_ms, 0.82)
        self.assertIn("confirmed twice", res.ledger[-1].note)
        self.assertEqual(n, 3)

    def test_an_unmeasurable_re_measure_is_not_faster(self):
        res, n = self._run([1.0, 0.80, None])
        self.assertFalse(res.accepted)
        self.assertEqual(res.ledger[-1].outcome, "not-faster")
        self.assertIn("unmeasurable", res.ledger[-1].note)

    def test_above_the_resolution_floor_one_measurement_suffices(self):
        # 100 -> 94 ms is 1.064x: past min_speedup, and no confirmation asked.
        res, n = self._run([100.0, 94.0])
        self.assertTrue(res.accepted)
        self.assertEqual(res.ledger[-1].note, "")
        self.assertEqual(n, 2)

    def test_the_floor_is_a_parameter(self):
        res, n = self._run([1.0, 0.90], resolution_ms=0.5)
        self.assertTrue(res.accepted)                   # 1.0 ms is "big" here
        self.assertEqual(n, 2)

    def test_resolution_fn_widens_the_band_per_node(self):
        # A node under the noise floor: the adapter answers inf, so a 100 ms
        # incumbent is inside the band and a 1.11x gain is not enough...
        res, n = self._run([100.0, 90.0], resolution_fn=lambda: float("inf"))
        self.assertFalse(res.accepted)
        self.assertIn("under the noise floor", res.ledger[-1].note)
        # ...while 1.25x confirmed twice is.
        res, n = self._run([100.0, 80.0, 82.0], resolution_fn=lambda: float("inf"))
        self.assertTrue(res.accepted)
        self.assertAlmostEqual(res.best_ms, 82.0)
        self.assertEqual(n, 3)

    def test_resolution_fn_none_keeps_resolution_ms(self):
        res, n = self._run([100.0, 94.0], resolution_fn=lambda: None)
        self.assertTrue(res.accepted)
        self.assertEqual(n, 2)


class TestAcceptCheck(unittest.TestCase):
    """``accept_check_fn`` is the last gate on a candidate about to be
    accepted: the live binding re-times it against the incumbent on the
    smallest bench scene. A reason rejects the round as ``regressed``; a
    divergence there is ``bench-diverged``; ``None`` lets the accept through."""

    def _run(self, check, **over):
        kw = dict(
            optimize_fn=lambda cpp: {"BASE": "C1", "C1": "C2"}[cpp],
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0, "C1": 50.0, "C2": 20.0}),
            rounds=1, accept_check_fn=check,
        )
        kw.update(over)
        return optimize_cpp("BASE", **kw)

    def test_a_reason_rejects_the_round_as_regressed(self):
        seen = []

        def check(cand, best):
            seen.append((cand, best))
            return "slower on the small scene: 3.0 ms vs 1.0 ms"

        res = self._run(check)
        self.assertFalse(res.accepted)
        self.assertEqual(res.best_cpp, "BASE")
        self.assertEqual(res.ledger[-1].outcome, "regressed")
        self.assertIn("small scene", res.ledger[-1].note)
        self.assertAlmostEqual(res.ledger[-1].ms, 50.0)  # its frozen-scene time
        self.assertEqual(seen, [("b:C1", "b:BASE")])     # candidate, incumbent

    def test_none_lets_the_accept_through(self):
        res = self._run(lambda cand, best: None)
        self.assertTrue(res.accepted)
        self.assertEqual(res.best_cpp, "C1")

    def test_it_is_not_asked_about_a_candidate_that_was_not_faster(self):
        seen = []
        res = self._run(lambda c, b: seen.append((c, b)),
                        benchmark_fn=_bench({"BASE": 100.0, "C1": 99.0}))
        self.assertFalse(res.accepted)
        self.assertEqual(seen, [])

    def test_a_divergence_there_is_bench_diverged(self):
        def check(cand, best):
            raise BenchmarkDiverged("on the small scene: out maxerr 1")

        res = self._run(check)
        self.assertFalse(res.accepted)
        self.assertEqual(res.ledger[-1].outcome, "bench-diverged")
        self.assertIn("small scene", res.ledger[-1].note)

    def test_the_incumbent_advances_with_each_accept(self):
        seen = []
        res  = self._run(lambda c, b: seen.append((c, b)), rounds=2)
        self.assertEqual(res.best_cpp, "C2")
        self.assertEqual(seen, [("b:C1", "b:BASE"), ("b:C2", "b:C1")])

    def test_a_regressed_round_ends_the_adaptive_loop(self):
        res = self._run(lambda c, b: "slower", rounds=6)
        self.assertEqual([r.outcome for r in res.ledger],
                         ["baseline", "regressed", "regressed"])
        self.assertIn("round 2 regressed", res.stop_reason)


if __name__ == "__main__":
    unittest.main()
