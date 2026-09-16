"""A compile that asks for AI and gets none must SAY SO, per node and per run.

The failure this locks down was measured, not imagined. A 43-template batch
reported ok=43 / fail=0 in 77 minutes with no agent session having started:
the Claude CLI died ~2s into every round (``sandbox_apply: Operation not
permitted`` -- sandboxes do not nest), ``optimize_with_agent`` swallowed that
and returned the UNCHANGED source, the gate rebuilt and re-measured the same
file, and benchmark noise recorded ``accept, 1.15x`` against a candidate whose
md5 equalled the baseline's.

Three things have to hold, and each is asserted here:
  1. the swallowed failure is still RECORDED (``candidates == 0`` + an error),
  2. the run-level result is NOT ok when nothing was delivered,
  3. an honest "no improvement found" is NOT mistaken for that.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from tests._setup import standalone_init
from tests.compile.pipeline.test_native_compile_pipeline import (_portable_spec,
                                                         _touch_bundle)
from mpynode.native.ai import optimizer_live


def _setUpModule__ai_unavailable_status():
    standalone_init()


setUpModule = _setUpModule__ai_unavailable_status


_SPEC = {"suggested": {"node_type_name": "mPyThing", "mpx_base": "MPxNode"},
         "compute": "self.out = self.a ** 2", "init": ""}
_BASELINE_CPP = "void f(){ return; }"


class _Env:
    def __init__(self, **kw):
        self._kw  = kw
        self._old = {}

    def __enter__(self):
        for k, v in self._kw.items():
            self._old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestASwallowedAgentFailureIsStillRecorded(unittest.TestCase):
    def test_an_agent_that_dies_at_startup_leaves_candidates_zero(self):
        from mpynode.native.ai.llm_client import AgentUnavailable

        def dead_agent(prompt):
            raise AgentUnavailable("sandbox_apply: Operation not permitted")

        status, notes = {}, []
        with tempfile.TemporaryDirectory() as tmp:
            ad = optimizer_live.make_adapters(
                _SPEC, tmp, maya="/x", agent_fn=dead_agent,
                status_out=status, log_cb=notes.append,
                run_step=lambda s, a, p, t: (None, False, ""))
            # optimize_with_agent swallows the failure and hands the UNCHANGED
            # source back -- exactly as it does in production.
            out = ad["optimize_fn"](_BASELINE_CPP)

        self.assertEqual(out, _BASELINE_CPP)
        self.assertEqual(status["rounds"], 1)
        self.assertEqual(status["candidates"], 0,
                         "an unchanged file is not a candidate")
        self.assertTrue(status["errors"], "the failure vanished again")
        self.assertIn("sandbox_apply", status["errors"][0])
        self.assertTrue(any("no candidate" in n for n in notes), notes)

    def test_a_real_edit_counts_as_a_candidate_and_records_no_error(self):
        status = {}
        with tempfile.TemporaryDirectory() as tmp:
            ws = os.path.join(tmp, "_optagent")

            def working_agent(prompt):
                # The real agent's deliverable is the file on disk, not its
                # reply; optimize_with_agent reads the workspace copy back.
                with open(os.path.join(ws, "mPyThing.cpp"), "w") as fh:
                    fh.write("void f(){ return; } // faster")
                return "done"

            ad = optimizer_live.make_adapters(
                _SPEC, tmp, maya="/x", agent_fn=working_agent,
                agent_ws=ws, status_out=status,
                run_step=lambda s, a, p, t: (None, False, ""))
            out = ad["optimize_fn"](_BASELINE_CPP)

        self.assertNotEqual(out, _BASELINE_CPP)
        self.assertEqual(status["candidates"], 1)
        self.assertEqual(status["errors"], [])

    def test_a_failing_one_shot_rewrite_is_recorded_too(self):
        def broken(system, user):
            raise RuntimeError("claude exited 71")

        status = {}
        with tempfile.TemporaryDirectory() as tmp:
            ad = optimizer_live.make_adapters(
                _SPEC, tmp, maya="/x", complete_fn=broken, status_out=status,
                run_step=lambda s, a, p, t: (None, False, ""))
            with self.assertRaises(RuntimeError):
                ad["optimize_fn"](_BASELINE_CPP)

        self.assertEqual(status["candidates"], 0)
        self.assertIn("claude exited 71", status["errors"][0])

    def test_a_cancel_is_not_recorded_as_an_ai_failure(self):
        """Cancel is the USER stopping the run, not the provider failing. Filing
        it as a failure would make every cancelled build report ok=False."""
        from mpynode.native.ai.llm_client import PortCancelled

        def cancelled(system, user):
            raise PortCancelled()

        status = {}
        with tempfile.TemporaryDirectory() as tmp:
            ad = optimizer_live.make_adapters(
                _SPEC, tmp, maya="/x", complete_fn=cancelled,
                status_out=status,
                run_step=lambda s, a, p, t: (None, False, ""))
            # _cancel_guard re-raises a cancel as _OptimizeCancelled, which
            # derives from BaseException so the engine's per-round guard cannot
            # swallow it.
            with self.assertRaises(optimizer_live._OptimizeCancelled):
                ad["optimize_fn"](_BASELINE_CPP)

        self.assertEqual(status["errors"], [])


class TestOptimizeSurvivingReportsPerNode(unittest.TestCase):
    def test_status_is_filled_for_a_node_that_errored_out_entirely(self):
        """A node missing from the RESULTS is precisely the node whose story the
        caller cannot otherwise tell."""
        status = {}
        with tempfile.TemporaryDirectory() as tmp:
            cpp = os.path.join(tmp, "kDTree.cpp")
            with open(cpp, "w") as fh:
                fh.write("BASELINE")

            def boom(baseline, **kw):
                raise RuntimeError("engine exploded")

            res = optimizer_live.optimize_surviving(
                [("kDTree", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=boom,
                adapters_factory=lambda *a, **k: {}, status_out=status)

        self.assertEqual(res, {})
        self.assertIn("kDTree", status)
        self.assertIn("engine exploded", status["kDTree"]["errors"][0])


class TestTheRunLevelVerdict(unittest.TestCase):
    """compile_plugin must not return ok when it was asked to optimize with AI
    and no AI ever delivered anything -- and must not abort the batch either."""

    def _run(self, *, provider_ok=True, status=None, results=None,
             optimize=True):
        from mpynode.native import compiler as codegen
        from mpynode.native.ai import optimizer_live as ol
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain

        events = []

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_check_provider(provider=None, model=None):
            return {"ok": provider_ok,
                    "problems": [] if provider_ok else ["No API key configured"],
                    "provider": provider, "kind": "api"}

        def fake_port_node(spec, out_dir, **k):
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("// ported\n")
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        def fake_assemble(nodes, plugin_name, out_dir, **k):
            return {"ok": True, "bundle": _touch_bundle(out_dir, plugin_name),
                    "nodes": [{"name": n, "id": 1, "status": "compiled",
                               "reason": ""} for (n, _c) in nodes],
                    "dropped": [], "shared_helpers": []}

        def fake_optimize_surviving(nodes, out_dir, **kw):
            self._opt_kw = dict(kw)
            out          = kw.get("status_out")
            if out is not None:
                out.update(status or {})
            return results or {}

        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(toolchain, "check_toolchain",
                               fake_check_toolchain), \
             mock.patch.object(porter, "check_provider", fake_check_provider), \
             mock.patch.object(porter, "port_node", fake_port_node), \
             mock.patch.object(codegen, "generate_cpp",
                               return_value="// no PORT region\n"), \
             mock.patch.object(ol, "optimize_surviving",
                               fake_optimize_surviving), \
             mock.patch.object(bundler, "assemble", fake_assemble):
            result = cc.compile_plugin(
                [_portable_spec()], "myPlugin", d, strict=True, verify=False,
                reuse_cache=False, complete_fn=None, provider="anthropic",
                model="m", optimize=optimize, progress_cb=events.append)
        return result, events

    def test_the_runs_provider_is_handed_to_the_optimizer(self):
        """The gate above already asks ``check_agent(provider)``. The round has
        to ask the same one, and it can only do that if the run's provider
        reaches it -- otherwise it re-derives one from prefs."""
        self._opt_kw = None
        self._run()

        self.assertIsNotNone(self._opt_kw, "the optimizer was never called")
        self.assertEqual(self._opt_kw.get("provider"), "anthropic")

    def test_no_candidate_anywhere_is_not_ok(self):
        result, events = self._run(status={
            "cubicCurveSampler": {
                "rounds": 2, "candidates": 0,
                "errors": ["round 1 produced no candidate -- "
                           "AgentUnavailable: sandbox_apply"]}})

        self.assertFalse(result["ok"],
                         "a run that optimized nothing reported success")
        self.assertTrue(result["bundle_path"],
                        "the deterministic bundle is still real and must be "
                        "reported, so the runner can keep the artifact")
        self.assertTrue(any("no candidate" in e for e in result["errors"]),
                        result["errors"])
        self.assertIn("__status__", result["optimize"])
        self.assertIn("ai_optimize_failed", result,
                      "a caller must be able to tell 'the AI never ran' from "
                      "'the build is broken' without matching error strings")
        self.assertTrue(any(e.get("stage") == "optimize"
                            and e.get("status") == "fail" for e in events),
                        "the runner gets no per-node event to record")

    def test_it_does_not_raise_so_a_batch_can_carry_on(self):
        # The whole point of a status over an exception: node 7 of 43 failing
        # must not take the other 36 with it.
        result, _events = self._run(status={
            "cubicCurveSampler": {"rounds": 1, "candidates": 0,
                                  "errors": ["boom"]}})
        self.assertIsInstance(result, dict)
        self.assertFalse(result["ok"])

    def test_an_honest_no_improvement_found_is_still_ok(self):
        """Zero candidates with NO recorded error is the AI saying "already
        optimal". Failing that would punish a correct answer."""
        result, _events = self._run(status={
            "cubicCurveSampler": {"rounds": 2, "candidates": 0, "errors": []}})
        self.assertTrue(result["ok"], result["errors"])

    def test_a_delivered_candidate_keeps_the_run_ok_even_if_rejected(self):
        result, _events = self._run(status={
            "cubicCurveSampler": {"rounds": 2, "candidates": 2,
                                  "errors": ["round 2 produced no candidate "
                                             "-- timeout"]}})
        self.assertTrue(result["ok"], result["errors"])

    def test_an_unreachable_provider_fails_the_run_instead_of_skipping_it(self):
        result, events = self._run(provider_ok=False)
        self.assertFalse(result["ok"])
        self.assertIn("__status__", result["optimize"])
        self.assertTrue(any("not reachable" in e for e in result["errors"]),
                        result["errors"])

    def test_a_build_with_optimize_off_is_untouched(self):
        result, _events = self._run(optimize=False)
        self.assertTrue(result["ok"], result["errors"])
        self.assertNotIn("optimize", result)


class TestTheAgentPreflight(unittest.TestCase):
    """``check_provider`` says ok for a claude_cli on PATH -- and the agent still
    cannot start, because it is granted Bash and the CLI's own OS sandbox cannot
    nest. That gap is what let the batch through, so the agent gets its own
    pre-flight (and NOT a stricter check_provider, which the porter shares and
    which never shells out)."""

    def test_a_sandbox_that_cannot_nest_is_reported_with_the_remedy(self):
        from mpynode.native.ai import llm_client

        with _Env(MPYNODE_OPT_AGENT_NO_SANDBOX=None), \
             mock.patch.object(llm_client, "check_provider",
                               return_value={"ok": True, "problems": [],
                                             "provider": "claude_cli",
                                             "kind": "cli"}), \
             mock.patch.object(llm_client, "_sandbox_nests",
                               return_value=False):
            chk = llm_client.check_agent()

        self.assertFalse(chk["ok"])
        self.assertTrue(any("MPYNODE_OPT_AGENT_NO_SANDBOX" in p
                            for p in chk["problems"]), chk)

    def test_the_escape_hatch_makes_it_pass(self):
        from mpynode.native.ai import llm_client

        with _Env(MPYNODE_OPT_AGENT_NO_SANDBOX="1"), \
             mock.patch.object(llm_client, "check_provider",
                               return_value={"ok": True, "problems": [],
                                             "provider": "claude_cli",
                                             "kind": "cli"}), \
             mock.patch.object(llm_client, "_sandbox_nests",
                               return_value=False):
            self.assertTrue(llm_client.check_agent()["ok"])

    def test_an_unknown_probe_result_never_blocks(self):
        # An inference must not be the thing that stops a run that would work.
        from mpynode.native.ai import llm_client

        with _Env(MPYNODE_OPT_AGENT_NO_SANDBOX=None), \
             mock.patch.object(llm_client, "check_provider",
                               return_value={"ok": True, "problems": [],
                                             "provider": "claude_cli",
                                             "kind": "cli"}), \
             mock.patch.object(llm_client, "_sandbox_nests",
                               return_value=None):
            self.assertTrue(llm_client.check_agent()["ok"])

    def test_a_non_claude_provider_has_no_agent_mode(self):
        from mpynode.native.ai import llm_client

        with mock.patch.object(llm_client, "check_provider",
                               return_value={"ok": True, "problems": [],
                                             "provider": "anthropic",
                                             "kind": "api"}):
            chk = llm_client.check_agent()
        self.assertFalse(chk["ok"])
        self.assertTrue(any("tool-using" in p for p in chk["problems"]), chk)

    def test_the_porters_own_check_provider_is_NOT_made_stricter(self):
        """The one-shot text path never shells out, so a nested sandbox must not
        block a port."""
        import inspect

        from mpynode.native.ai import llm_client

        src = inspect.getsource(llm_client.check_provider)
        self.assertNotIn("_sandbox_nests", src)

    def test_the_optimizer_demotes_to_one_shot_and_says_why(self):
        from mpynode.native.ai import llm_client

        status, notes = {}, []
        # make_adapters resolves the one-shot complete_fn at BUILD time, so the
        # stand-in has to be in place before it, not before the round.
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(llm_client, "check_agent",
                               return_value={"ok": False, "provider":
                                             "claude_cli", "kind": "cli",
                                             "problems": ["sandbox_apply"]}), \
             mock.patch.object(
                 llm_client, "make_cli_complete_fn",
                 return_value=lambda s, u: "```cpp\nvoid g(){}\n```"):
            ad = optimizer_live.make_adapters(
                _SPEC, tmp, maya="/x", status_out=status, log_cb=notes.append,
                complete_fn=None,
                run_step=lambda s, a, p, t: (None, False, ""))
            ad["optimize_fn"](_BASELINE_CPP)

        self.assertIn("no agent", status["path"])
        self.assertIn("sandbox_apply", status["path"])
        self.assertTrue(any("one-shot" in n for n in notes), notes)


class TestTheGateAndTheRunAskAboutOneProvider(unittest.TestCase):
    """``check_agent`` was probed twice with DIFFERENT inputs: the controller
    passed the run's resolved ``provider``, ``optimizer_live`` passed nothing
    and so resolved PREFS. With an override in play the budget gate answered
    for one provider while the round executed under another, both ways:

      * override ``claude_cli`` / prefs an API provider -- the gate says
        "agent, no response ceiling" and skips nothing, then the run demotes to
        the one-shot whole-file rewrite it never budgeted for: a big node is
        retyped, truncated, rejected, and the round is spent.
      * override an API provider / prefs ``claude_cli`` -- the gate says
        "one-shot" and can SKIP a large node on the response budget, while the
        run would have used the agent, which edits in place and has no ceiling.

    One source of truth: the explicitly-passed provider wins (it is the more
    specific signal, and it is what the porter, the cache key and the gate
    already use), ``None`` falls back to prefs -- which is exactly what
    ``check_provider`` already does, so a run with NO override is unchanged.
    """

    def _check_agent(self, asked, prefs):
        """``check_agent`` with the REAL resolution rule, recording its input."""
        from mpynode.native.ai import llm_client

        def _chk(provider=None):
            asked.append(provider)
            prov = provider or prefs
            ok   = (prov == "claude_cli")
            return {"ok": ok, "provider": prov,
                    "kind":     "cli" if prov.endswith("_cli") else "api",
                    "problems": [] if ok else
                    ["%r has no headless tool-using mode" % prov]}

        return mock.patch.object(llm_client, "check_agent", _chk)

    def _gate_one_shot(self, provider, kind, prefs, asked):
        from mpynode.native.toolchain import compile_controller as cc

        with self._check_agent(asked, prefs):
            return cc._optimizer_is_one_shot(provider, kind)

    def _path_taken(self, provider, prefs, asked):
        """Which path a REAL ``make_adapters`` round takes for ``provider``."""
        from mpynode.native.ai import llm_client

        status = {}
        with tempfile.TemporaryDirectory() as tmp, \
             self._check_agent(asked, prefs), \
             mock.patch.object(llm_client, "make_cli_agent_fn",
                               return_value=lambda prompt: "did nothing"), \
             mock.patch.object(
                 llm_client, "make_cli_complete_fn",
                 return_value=lambda s, u: "```cpp\nvoid g(){}\n```"):
            ad = optimizer_live.make_adapters(
                _SPEC, tmp, maya="/x", status_out=status, complete_fn=None,
                provider=provider,
                run_step=lambda s, a, p, t: (None, False, ""))
            ad["optimize_fn"](_BASELINE_CPP)
        return status["path"]

    def test_an_override_to_a_cli_provider_governs_both(self):
        gate_asked, run_asked = [], []
        one_shot = self._gate_one_shot("claude_cli", "cli", "anthropic",
                                       gate_asked)
        path = self._path_taken("claude_cli", "anthropic", run_asked)

        self.assertFalse(one_shot, "the gate did not see the agent path")
        self.assertEqual(path, "agent",
                         "the gate budgeted for the agent and the run demoted "
                         "to a one-shot rewrite: %r" % path)
        self.assertEqual(gate_asked, run_asked, "two probes, two questions")

    def test_an_override_to_an_api_provider_governs_both(self):
        gate_asked, run_asked = [], []
        # kind == "api" short-circuits the gate, so it never probes at all.
        one_shot = self._gate_one_shot("anthropic", "api", "claude_cli",
                                       gate_asked)
        path = self._path_taken("anthropic", "claude_cli", run_asked)

        self.assertTrue(one_shot)
        self.assertIn("one-shot", path,
                      "the gate budgeted for a whole-file rewrite and the run "
                      "used the agent: %r" % path)
        self.assertEqual(run_asked, ["anthropic"],
                         "the round asked prefs, not the run's provider")

    def test_the_resolved_prefs_value_and_None_are_the_same_question(self):
        """What the no-override path -- every normal run -- rests on.
        ``compile_plugin`` resolves the provider from prefs itself, so passing
        that value on asks EXACTLY the question ``None`` already asked:
        ``check_provider`` resolves ``None`` from the same prefs."""
        from mpynode.native.ai import llm_client
        from mpynode.ui.llm import config as _cfg

        with mock.patch.object(_cfg, "get_provider",
                               return_value="claude_cli"), \
             mock.patch.object(llm_client, "_resolve_cli_bin",
                               return_value="/bin/claude"), \
             mock.patch.object(llm_client, "_sandbox_nests",
                               return_value=True):
            self.assertEqual(llm_client.check_agent(None),
                             llm_client.check_agent("claude_cli"))

    def test_with_no_override_both_sides_still_resolve_prefs(self):
        gate_asked, run_asked = [], []
        one_shot = self._gate_one_shot(None, "cli", "claude_cli", gate_asked)
        path     = self._path_taken(None, "claude_cli", run_asked)

        self.assertFalse(one_shot)
        self.assertEqual(path,       "agent")
        self.assertEqual(gate_asked, [None])
        self.assertEqual(run_asked,  [None])


class TestAgentUnavailableIsTyped(unittest.TestCase):
    def test_the_sandbox_failure_is_raised_as_AgentUnavailable(self):
        from mpynode.native.ai import llm_client

        with mock.patch.object(llm_client, "_resolve_cli_bin",
                               return_value="/bin/claude"), \
             mock.patch.object(
                 llm_client, "_run_cli_proc",
                 side_effect=RuntimeError(
                     "/bin/claude exited 71: sandbox-exec: sandbox_apply: "
                     "Operation not permitted")):
            agent = llm_client.make_cli_agent_fn("/tmp")
            with self.assertRaises(llm_client.AgentUnavailable) as cm:
                agent("do it")
        self.assertIn("MPYNODE_OPT_AGENT_NO_SANDBOX", str(cm.exception))

    def test_it_is_still_a_RuntimeError_so_existing_handlers_are_unchanged(self):
        from mpynode.native.ai.llm_client import AgentUnavailable

        self.assertTrue(issubclass(AgentUnavailable, RuntimeError))


if __name__ == "__main__":
    unittest.main()
