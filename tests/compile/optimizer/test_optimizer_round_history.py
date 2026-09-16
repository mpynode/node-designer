"""Arm C: what round N+1 is told about rounds 1..N.

Each optimize round is a FRESH ``claude -p`` process -- ``make_cli_agent_fn``
builds its argv per call with no ``--resume`` and no session id -- so a round
begins with no memory of the ones before it. The only continuity is the reused
workspace directory and the current-best .cpp. Concretely, a round that was
REJECTED leaves nothing behind: round N+1 starts from the same source round N
started from, with nothing saying that idea already lost, and can re-propose it.

The engine already RECORDS everything needed to fix that -- RoundRecord carries
slug / theme / hypothesis / predicted_speedup / risk / outcome / ms / speedup,
and ``write_rounds_json`` persists it -- but the ledger only ever travelled
outward, to the report. These tests drive it back IN.

The channel is an optional ``history_sink``: the mirror image of the existing
``round_meta_fn`` (which already carries data adapter -> engine). It must stay
optional, because ``optimize_fn`` is a ONE-argument contract and every existing
stub is a one-arg lambda -- a second positional argument would break them all.

Pure logic for the engine half -> no Maya. The prompt half touches only string
rendering.
"""

from __future__ import annotations

import unittest

from mpynode.native.ai.optimizer import (
    optimize_cpp, ParityVerdict, PARITY_PASS, PARITY_FAIL,
)


def _compile_ok(cpp):
    return (True, "", "b:" + cpp)


def _bench(ms_by_cpp):
    return lambda bundle: ms_by_cpp.get(bundle[2:])


def _parity(status):
    return lambda bundle: ParityVerdict(status)


class TestHistorySinkIsOptional(unittest.TestCase):
    """Arm A must stay byte-identical to what ships today."""

    def test_a_one_argument_optimize_fn_still_works(self):
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

    def test_no_sink_means_nothing_is_called(self):
        """Absent the sink the engine must not invent a channel of its own."""
        res = optimize_cpp(
            "BASE",
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0, "CAND": 40.0}),
            rounds       = 2,
            history_sink = None,
        )
        self.assertEqual(res.rounds, 2)


class TestHistorySinkReceivesTheLedger(unittest.TestCase):
    def _run(self, sink, rounds=3, **over):
        kw = dict(
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn = _compile_ok,
            parity_fn  = _parity(PARITY_PASS),
            # CAND never beats BASE -> every round is rejected, which is the
            # case the history actually has to fix.
            benchmark_fn = _bench({"BASE": 100.0, "CAND": 100.0}),
            rounds       = rounds,
            # Fixed count: these tests are about the sink, not the adaptive
            # stop rule, which would otherwise end an all-rejected run at 2.
            min_rounds   = rounds,
            history_sink = sink,
        )
        kw.update(over)
        return optimize_cpp("BASE", **kw)

    def test_it_is_called_once_per_round_before_the_proposal(self):
        seen  = []
        order = []

        def sink(history):
            order.append("sink")
            seen.append(list(history))

        def optimize_fn(cpp):
            order.append("propose")
            return "CAND"

        self._run(sink, rounds=3, optimize_fn=optimize_fn)

        self.assertEqual(len(seen), 3)
        # Before, not after: a proposal informed by history it has not been
        # handed yet is the bug this whole arm exists to remove.
        self.assertEqual(order, ["sink", "propose"] * 3)

    def test_round_one_gets_only_the_baseline(self):
        seen = []
        self._run(lambda h: seen.append(list(h)), rounds=2)

        self.assertEqual([r.index for r in seen[0]], [0])
        self.assertEqual(seen[0][0].outcome, "baseline")

    def test_later_rounds_see_every_resolved_round_before_them(self):
        seen = []
        self._run(lambda h: seen.append(list(h)), rounds=3)

        self.assertEqual([r.index for r in seen[1]], [0, 1])
        self.assertEqual([r.index for r in seen[2]], [0, 1, 2])
        self.assertEqual(seen[2][1].outcome,         "not-faster")

    def test_the_rejected_theme_survives_into_the_next_round(self):
        """The whole point: "structure-of-arrays was 2x slower" is only worth
        recording if the next attempt is told about it."""
        seen = []
        meta = {"slug": "soa", "theme": "structure-of-arrays",
                "hypothesis": "better cache locality",
                "predicted_speedup": 2.0, "risk": "layout churn"}
        self._run(lambda h: seen.append(list(h)), rounds=2,
                  round_meta_fn=lambda: meta)

        prior = seen[1][1]
        self.assertEqual(prior.theme,             "structure-of-arrays")
        self.assertEqual(prior.predicted_speedup, 2.0)
        self.assertEqual(prior.outcome,           "not-faster")
        self.assertAlmostEqual(prior.ms, 100.0)

    def test_a_failing_sink_never_costs_a_round(self):
        """Report material must not be able to fail an optimization, the same
        rule ``_fetch_meta`` and ``_emit_round`` already follow."""
        def sink(history):
            raise RuntimeError("sink exploded")

        res = self._run(sink, rounds=2,
                        benchmark_fn=_bench({"BASE": 100.0, "CAND": 10.0}))

        self.assertTrue(res.accepted)
        self.assertEqual(res.rounds, 2)

    def test_the_sink_cannot_mutate_the_engines_ledger(self):
        """It is handed history to READ. A sink that clears its argument must
        not blank the ledger that becomes rounds.json."""
        self_ = self

        def sink(history):
            try:
                history.clear()
            except AttributeError:
                self_.fail("history should be a concrete sequence")

        res = self._run(sink, rounds=2)
        self.assertEqual([r.index for r in res.ledger], [0, 1, 2])


class TestFailedRoundsAreInTheHistoryToo(unittest.TestCase):
    def test_a_parity_failure_is_reported_to_the_next_round(self):
        seen = []
        optimize_cpp(
            "BASE",
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = _compile_ok,
            parity_fn    = _parity(PARITY_FAIL),
            benchmark_fn = _bench({"BASE": 100.0, "CAND": 10.0}),
            rounds       = 2,
            history_sink = lambda h: seen.append(list(h)),
        )
        self.assertEqual(seen[1][1].outcome, "parity-fail")

    def test_a_compile_failure_is_reported_to_the_next_round(self):
        seen = []
        optimize_cpp(
            "BASE",
            optimize_fn=lambda cpp: "CAND",
            fix_fn=lambda cpp, errs: cpp,
            compile_fn   = lambda cpp: (cpp == "BASE", "boom", "b:" + cpp),
            parity_fn    = _parity(PARITY_PASS),
            benchmark_fn = _bench({"BASE": 100.0}),
            rounds       = 2,
            history_sink = lambda h: seen.append(list(h)),
        )
        self.assertEqual(seen[1][1].outcome, "compile-failed")


class TestHistoryIsOffByDefault(unittest.TestCase):
    """Arms A and C run from the SAME binary. If the live adapters wired the
    sink unconditionally, arm A would silently get history too and the whole
    experiment would compare a thing against itself. Same env-var shape as
    ``MPYNODE_OPT_ROUNDS`` / ``MPYNODE_OPT_TIMEOUT``."""

    ENV = "MPYNODE_OPT_HISTORY"

    def setUp(self):
        import os
        self._saved = os.environ.get(self.ENV)

    def tearDown(self):
        import os
        if self._saved is None:
            os.environ.pop(self.ENV, None)
        else:
            os.environ[self.ENV] = self._saved

    def test_default_is_off(self):
        import os
        from mpynode.native.ai import optimizer_live
        os.environ.pop(self.ENV, None)
        self.assertFalse(optimizer_live._history_enabled())

    def test_env_turns_it_on(self):
        import os
        from mpynode.native.ai import optimizer_live
        for raw in ("1", "true", "yes", "on"):
            os.environ[self.ENV] = raw
            self.assertTrue(optimizer_live._history_enabled(),
                            "%r should enable history" % raw)

    def test_explicit_off_stays_off(self):
        import os
        from mpynode.native.ai import optimizer_live
        for raw in ("0", "", "off", "no"):
            os.environ[self.ENV] = raw
            self.assertFalse(optimizer_live._history_enabled(),
                             "%r should leave history off" % raw)


class TestTheAgentPromptRendersTheHistory(unittest.TestCase):
    """``build_workspace`` writes TASK.md. The history block follows the exact
    shape of the existing ``{budget_block}``: conditional, absent when empty."""

    def _record(self, **kw):
        from mpynode.native.ai.optimizer import RoundRecord
        return RoundRecord(**kw)

    def test_no_history_renders_no_block(self):
        from mpynode.native.ai import optimizer_agent
        self.assertEqual(optimizer_agent.render_history_block([]), "")
        self.assertEqual(optimizer_agent.render_history_block(None), "")

    def test_the_baseline_alone_renders_no_block(self):
        """Round 1 has a ledger -- the baseline -- but nothing was TRIED yet."""
        from mpynode.native.ai import optimizer_agent
        base = self._record(index=0, outcome="baseline", ms=33.9)
        self.assertEqual(optimizer_agent.render_history_block([base]), "")

    def test_a_rejected_round_is_named_with_its_measurement(self):
        from mpynode.native.ai import optimizer_agent
        rows = [
            self._record(index=0, outcome="baseline", ms=33.9),
            self._record(index=1, outcome="not-faster", theme="structure-of-arrays",
                         hypothesis="better cache locality", predicted_speedup=2.0,
                         ms=41.2),
        ]
        block = optimizer_agent.render_history_block(rows)

        self.assertIn("structure-of-arrays", block)
        self.assertIn("41.2", block)
        self.assertIn("2.0", block)          # what it predicted
        self.assertIn("not-faster", block)

    def test_an_accepted_round_is_marked_as_already_in_the_file(self):
        """Re-proposing a change that is already applied wastes a round."""
        from mpynode.native.ai import optimizer_agent
        rows = [
            self._record(index=0, outcome="baseline", ms=100.0),
            self._record(index=1, outcome="accept", theme="hoist invariant",
                         ms=50.0, speedup=2.0),
        ]
        block = optimizer_agent.render_history_block(rows)

        self.assertIn("hoist invariant", block)
        low = block.lower()
        self.assertTrue("already" in low or "in the file" in low or
                        "applied" in low,
                        "an accepted round must read as already applied")

    def test_an_unnamed_round_still_appears(self):
        """A round whose narrator said nothing is still evidence -- dropping it
        would tell the next round that fewer things were tried than were."""
        from mpynode.native.ai import optimizer_agent
        rows = [
            self._record(index=0, outcome="baseline", ms=100.0),
            self._record(index=1, outcome="compile-failed"),
        ]
        block = optimizer_agent.render_history_block(rows)

        self.assertIn("compile-failed", block)

    def test_the_block_reaches_TASK_md(self):
        from mpynode.native.ai import optimizer_agent
        rows = [
            self._record(index=0, outcome="baseline", ms=100.0),
            self._record(index=1, outcome="not-faster", theme="simd argmin",
                         ms=120.0),
        ]
        self.assertIn("{history_block}", optimizer_agent._TASK_MD)
        # And the renderer's output is what fills it.
        self.assertIn("simd argmin",
                      optimizer_agent.render_history_block(rows))


class TestTheLiveWiringActuallyCarriesIt(unittest.TestCase):
    """The chain the unit tests above each cover ONE link of:

        engine -> history_sink -> _agent_state -> optimize_with_agent(history=)

    If any link is missing, arm C is silently identical to arm A and the whole
    experiment compares a thing against itself -- a failure that would look
    exactly like "history does not help". Stubs only; no AI, no compiler.
    """

    def setUp(self):
        import os
        from mpynode.native.ai import llm_client, optimizer_agent
        from mpynode.ui.llm import config as cfg
        self._saved_env     = os.environ.get("MPYNODE_OPT_HISTORY")
        self._agent_mod     = optimizer_agent
        self._llm           = llm_client
        self._cfg           = cfg
        self._orig_owa      = optimizer_agent.optimize_with_agent
        self._orig_mkagent  = llm_client.make_cli_agent_fn
        self._orig_provider = cfg.get_provider
        self._orig_check    = llm_client.check_agent
        # A provider with a tool-using headless mode, and an agent that does
        # nothing -- the round's OUTPUT is irrelevant here, only what it is TOLD.
        cfg.get_provider             = lambda: "claude_cli"
        llm_client.make_cli_agent_fn = lambda ws, **kw: (lambda prompt: "")
        # ...and a host whose sandbox the agent can install. The real pre-flight
        # probes THIS machine, so without the stub the arm under test depends on
        # how the suite was launched (nested sandbox -> demoted to one-shot ->
        # optimize_with_agent never called -> both arms empty).
        llm_client.check_agent = lambda provider=None: {
            "ok": True, "problems": [], "provider": "claude_cli", "kind": "cli"}

    def tearDown(self):
        import os
        self._agent_mod.optimize_with_agent = self._orig_owa
        self._llm.make_cli_agent_fn         = self._orig_mkagent
        self._cfg.get_provider              = self._orig_provider
        self._llm.check_agent               = self._orig_check
        if self._saved_env is None:
            os.environ.pop("MPYNODE_OPT_HISTORY", None)
        else:
            os.environ["MPYNODE_OPT_HISTORY"] = self._saved_env

    def _drive(self, tmp):
        """Two rounds through the LIVE adapters; return each round's history."""
        from mpynode.native.ai import optimizer_live, optimizer_agent
        from mpynode.native.ai.optimizer import optimize_cpp

        seen = []

        def fake_owa(spec, ws_dir, cpp_text, agent_fn, **kw):
            seen.append(list(kw.get("history") or []))
            return cpp_text            # never improves -> both rounds rejected

        optimizer_agent.optimize_with_agent = fake_owa

        spec = {"suggested": {"node_type_name": "kdProbe"},
                "compute": "pass", "init": ""}
        ad = optimizer_live.make_adapters(
            spec, tmp, node_type="kdProbe",
            parity_fn=lambda b: ParityVerdict(PARITY_PASS),
            benchmark_fn=lambda b: 100.0)
        # compile_fn would invoke a real compiler; the engine only needs a bundle.
        ad["compile_fn"] = _compile_ok
        optimize_cpp("BASE", rounds=2, **ad)
        return seen, ad

    def test_with_history_on_round_two_is_told_about_round_one(self):
        import os
        import tempfile
        os.environ["MPYNODE_OPT_HISTORY"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            seen, ad = self._drive(tmp)

        self.assertIn("history_sink", ad,
                      "the gate is on, so the engine must be given the sink")
        self.assertEqual(len(seen), 2)
        self.assertEqual([r.index for r in seen[0]], [0])
        self.assertEqual([r.index for r in seen[1]], [0, 1],
                         "round 2 must be told what round 1 did")

    def test_with_history_off_round_two_is_told_nothing(self):
        import os
        import tempfile
        os.environ.pop("MPYNODE_OPT_HISTORY", None)
        with tempfile.TemporaryDirectory() as tmp:
            seen, ad = self._drive(tmp)

        self.assertNotIn("history_sink", ad)
        self.assertEqual([list(h) for h in seen], [[], []],
                         "arm A must be byte-identical to what ships today")


class TestTheOneShotFallbackGetsItToo(unittest.TestCase):
    """The sink is registered with NO provider gate, so on gemini/codex (no
    headless tool mode) with ``MPYNODE_OPT_HISTORY=1`` the ledger was collected
    every round and read by nobody -- the one path where re-proposing a losing
    idea costs a whole blind rewrite.

    The renderer is the agent's; there is exactly one, so the two paths can
    never describe the same ledger differently.
    """

    ENV = "MPYNODE_OPT_HISTORY"

    def setUp(self):
        import os
        self._saved = os.environ.get(self.ENV)

    def tearDown(self):
        import os
        if self._saved is None:
            os.environ.pop(self.ENV, None)
        else:
            os.environ[self.ENV] = self._saved

    _CPP = "int main(){ return 0; }\n"

    def _drive(self, tmp):
        """Two rounds through the LIVE adapters on the one-shot text path.

        An injected ``complete_fn`` IS the one-shot path -- ``make_adapters``
        refuses to promote an injected text function to a live agent. Returns
        (each round's user turn, each round's ledger as the engine offered it).
        """
        from mpynode.native.ai import optimizer_live

        prompts = []
        ledgers = []

        def complete_fn(system, user):
            prompts.append(user)
            return self._CPP       # never improves -> both rounds resolve

        spec = {"suggested": {"node_type_name": "kdProbe"},
                "compute": "pass", "init": ""}
        ad = optimizer_live.make_adapters(
            spec, tmp, node_type="kdProbe", complete_fn=complete_fn,
            parity_fn=lambda b: ParityVerdict(PARITY_PASS),
            benchmark_fn=lambda b: 100.0)
        ad["compile_fn"] = _compile_ok
        sink             = ad.get("history_sink")
        if sink is not None:
            def spy(ledger):
                ledgers.append(list(ledger or []))
                sink(ledger)

            ad["history_sink"] = spy
        optimize_cpp(self._CPP, rounds=2, **ad)
        return prompts, ledgers

    def test_with_history_on_the_second_prompt_names_the_first_round(self):
        import os
        import tempfile
        from mpynode.native.ai import optimizer_agent
        os.environ[self.ENV] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            prompts, ledgers = self._drive(tmp)

        self.assertEqual(len(prompts), 2)
        self.assertNotIn("earlier rounds", prompts[0],
                         "round 1 has tried nothing yet")
        self.assertIn("earlier rounds", prompts[1])
        self.assertIn("round 1", prompts[1])
        # ...and it is the AGENT's renderer over the engine's OWN ledger, not a
        # second description of it that can drift from the first.
        self.assertEqual(len(ledgers), 2)
        self.assertIn(optimizer_agent.render_history_block(ledgers[1]),
                      prompts[1])

    def test_with_history_off_the_prompt_is_unchanged(self):
        """The default is OFF and settled by measurement (restarts 23.03x vs
        restarts+history 22.69x). This closes a plumbing gap; it must not move
        the default."""
        import os
        import tempfile
        os.environ.pop(self.ENV, None)
        with tempfile.TemporaryDirectory() as tmp:
            prompts, ledgers = self._drive(tmp)

        self.assertEqual(ledgers, [], "the sink must not even be registered")
        self.assertEqual(len(prompts), 2)
        self.assertEqual(prompts[0], prompts[1])
        self.assertNotIn("earlier rounds", prompts[1])


if __name__ == "__main__":
    unittest.main()
