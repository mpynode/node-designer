"""The agentic optimizer: hand an AI agent the .cpp plus a build+bench loop and
let it iterate on real files, instead of asking it to retype the whole file.

The agent itself is injected, so this suite drives every path with a stub -- no
LLM, no Maya, no compiler. Pure filesystem + logic.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from mpynode.native.ai import optimizer_agent as oa


_SPEC = {
    "suggested": {"node_type_name": "widgetNode", "class_name": "WidgetNode",
                  "mpx_base": "MPxNode", "type_id": "0x00012345"},
    "inputs": {}, "outputs": {},
    "compute": "self.out = self.a * 2",
    "init": "import numpy as np",
}

_CPP = "// original\nint main() { return 0; }\n"


class _Ws(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="optagent_")

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def _read(self, rel):
        with open(os.path.join(self.ws, rel)) as fh:
            return fh.read()


class TestBuildWorkspace(_Ws):
    def test_writes_cpp_build_bench_and_task(self):
        cpp_path, task = oa.build_workspace(_SPEC, self.ws, _CPP)
        self.assertEqual(cpp_path, os.path.join(self.ws, "widgetNode.cpp"))
        for f in ("widgetNode.cpp", "build.sh", "bench.sh", "TASK.md"):
            self.assertTrue(os.path.exists(os.path.join(self.ws, f)), f)
        self.assertEqual(self._read("widgetNode.cpp"), _CPP)
        self.assertTrue(task.strip())

    def test_build_and_bench_are_executable(self):
        oa.build_workspace(_SPEC, self.ws, _CPP)
        for f in ("build.sh", "bench.sh"):
            self.assertTrue(os.access(os.path.join(self.ws, f), os.X_OK), f)

    def test_bench_builds_before_measuring(self):
        # Measuring without rebuilding would time the PREVIOUS bundle -- the
        # agent would see "no change" for every edit it makes.
        oa.build_workspace(_SPEC, self.ws, _CPP)
        bench = self._read("bench.sh")
        self.assertLess(bench.index("build.sh"), bench.index("benchmark_node.py"))

    def test_bench_emits_a_single_parsable_number(self):
        oa.build_workspace(_SPEC, self.ws, _CPP)
        self.assertIn("MEDIAN_MS:", self._read("bench.sh"))

    def test_task_carries_the_python_parity_reference(self):
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP)
        self.assertIn("self.out = self.a * 2", task)
        self.assertIn("import numpy as np", task)

    def test_task_states_the_measured_baseline_when_known(self):
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP, baseline_ms=12.5)
        self.assertIn("12.500 ms", task)

    def test_task_states_the_invariants_that_get_it_rejected(self):
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP)
        for must in ("initializePlugin", "ONE self-contained translation unit",
                     "ffp-contract"):
            self.assertIn(must, task)

    def test_task_states_the_wall_clock_budget_when_bounded(self):
        # An agent that does not know it is on a clock gets killed mid-edit and
        # leaves a file that will not compile -- the gate then rejects it and
        # every measured win in that run is lost.
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP, budget_s=2400)
        self.assertIn("40 min", task)
        self.assertIn("killed", task)

    def test_task_says_unbounded_when_there_is_no_budget(self):
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP,
                                      budget_s=float("inf"))
        self.assertNotIn("killed", task)

    def test_task_states_the_workload_it_is_optimizing_for(self):
        # Without the sizes, the agent cannot tell an O(N*M) scan from a tree --
        # it has to go read the harness to find out, which costs cycles out of a
        # bounded budget and is what the scope section tells it not to do.
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP, bench_geo=200,
                                      bench_iters=9, bench_array=10000)
        self.assertIn("10000", task)
        self.assertIn("200", task)

    def test_task_names_the_absolute_path_of_the_file_to_edit(self):
        # The engine keeps its own scratch <name>.cpp in the PARENT directory.
        # Naming the target by bare name once cost a whole run: the agent
        # edited the sibling while bench.sh kept timing the untouched original.
        cpp_path, task = oa.build_workspace(_SPEC, self.ws, _CPP)
        self.assertIn(cpp_path, task)

    def test_task_permits_reading_the_harness_but_not_changing_it(self):
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP)
        low = task.lower()
        self.assertIn("read", low)
        self.assertIn("ONE file you may modify", task)

    def test_bench_surfaces_node_stdout_for_profiling(self):
        # The agent's first instinct on a plateau is to instrument the compute
        # and print timings. If bench.sh swallows stdout it burns cycles finding
        # that out, then cannot profile at all.
        oa.build_workspace(_SPEC, self.ws, _CPP)
        self.assertIn("NODE OUTPUT", self._read("bench.sh"))

    def test_task_allows_rewriting_the_inlined_runtime(self):
        # The hand-optimized reference won by replacing generic runtime helpers
        # with purpose-built ones; forbidding that would cap the achievable win.
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP)
        self.assertIn("nd_runtime.h", task)


class TestBenchShHonoursTheBenchmarkLock(_Ws):
    """The agent's own ``./bench.sh`` is the path the lock never reached.

    Measured 2026-08-13: with the agent live, max benchmark concurrency 4 and 36
    overlapping pairs -- every single one an ``_optagent/`` bundle, none a
    ``3_optimized/`` one. ``benchmark_node.py`` now takes the lock when told to;
    this is where it gets told, and it is told EXPLICITLY rather than by
    inheritance so an agent shell that scrubs the environment cannot silently
    turn the serialization back off.
    """

    _MARKER = "MPYNODE_BENCH_LOCK_CHILD"

    def _bench(self, lock):
        old = os.environ.get("MPYNODE_BENCH_LOCK")
        if lock is None:
            os.environ.pop("MPYNODE_BENCH_LOCK", None)
        else:
            os.environ["MPYNODE_BENCH_LOCK"] = lock
        try:
            oa.build_workspace(_SPEC, self.ws, _CPP)
            return self._read("bench.sh")
        finally:
            if old is None:
                os.environ.pop("MPYNODE_BENCH_LOCK", None)
            else:
                os.environ["MPYNODE_BENCH_LOCK"] = old

    def test_lock_on_exports_the_path_and_the_child_marker(self):
        bench = self._bench("/tmp/mpynode-test-bench.lock")
        self.assertIn("/tmp/mpynode-test-bench.lock", bench)
        self.assertIn(self._MARKER, bench)

    def test_the_marker_is_exported_before_the_benchmark_runs(self):
        bench = self._bench("/tmp/mpynode-test-bench.lock")
        self.assertLess(bench.index(self._MARKER),
                        bench.index("benchmark_node.py"),
                        "the marker is set after the child is launched")

    def test_lock_off_leaves_bench_sh_exactly_as_it_was(self):
        # Zero-cost default: unset means the generated script does not mention
        # the lock at all, so a single-process run is byte-identical.
        bench = self._bench(None)
        self.assertNotIn(self._MARKER, bench)
        self.assertNotIn("MPYNODE_BENCH_LOCK", bench)

    def test_the_engine_path_never_sets_the_marker(self):
        """The deadlock guard, pinned.

        ``optimizer_live._measure`` holds that same flock across the whole
        benchmark child. An flock belongs to the open file description, so a
        child that took it again would wait on its own parent until
        ``MPYNODE_BENCH_LOCK_TIMEOUT`` and then fail the measurement. The
        engine's child env is ``dict(os.environ)`` plus overrides, so the marker
        must never appear in it.
        """
        from mpynode.native.ai import optimizer_live

        old = os.environ.pop(self._MARKER, None)
        try:
            env = optimizer_live._base_env(self.ws)
        finally:
            if old is not None:
                os.environ[self._MARKER] = old
        self.assertNotIn(self._MARKER, env)

    def test_a_marker_already_in_the_parent_env_is_not_passed_down(self):
        """``_base_env`` starts from ``dict(os.environ)``, so anything the
        PARENT exported is inherited. Only a human can put the marker there
        (bench.sh's export propagates DOWN, not up), but the consequence is the
        deadlock above -- the engine's child waiting on its own parent's flock
        until the timeout -- so the child env is scrubbed, not trusted."""
        from mpynode.native.ai import optimizer_live

        old = os.environ.get(self._MARKER)
        os.environ[self._MARKER] = "1"
        try:
            env = optimizer_live._base_env(self.ws)
        finally:
            if old is None:
                os.environ.pop(self._MARKER, None)
            else:
                os.environ[self._MARKER] = old
        self.assertNotIn(self._MARKER, env)


class TestTheAgentProcessCarriesTheLockItself(_Ws):
    """``bench.sh`` is not the only way to reach ``benchmark_node.py``.

    Its absolute path is written into ``bench.sh`` in plain text, and TASK.md
    invites the agent to read the harness, so an agent that runs the benchmark
    by hand -- to add a flag, or to see the raw output -- gets a child with none
    of bench.sh's exports and benchmarks UNSERIALISED. Putting the same two
    variables in the AGENT's own environment closes that: every descendant it
    spawns inherits them, whichever way it measures.

    The engine is unaffected -- it never runs inside this window (the round is
    agent, THEN compile+measure, on one thread) and ``_base_env`` scrubs the
    marker regardless.
    """

    _MARKER = "MPYNODE_BENCH_LOCK_CHILD"
    _LOCK = "MPYNODE_BENCH_LOCK"

    def _run_agent(self, lock):
        """Run a stub agent with the lock env as given; return what it saw."""
        seen = {}

        def agent(prompt):
            seen[self._MARKER] = os.environ.get(self._MARKER)
            seen[self._LOCK] = os.environ.get(self._LOCK)
            return ""

        old = {k: os.environ.get(k) for k in (self._LOCK, self._MARKER)}
        os.environ.pop(self._MARKER, None)
        if lock is None:
            os.environ.pop(self._LOCK, None)
        else:
            os.environ[self._LOCK] = lock
        try:
            oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return seen

    def test_the_agent_runs_with_the_marker_and_the_lockfile_set(self):
        lock = os.path.join(self.ws, "bench.lock")
        seen = self._run_agent(lock)
        self.assertEqual(seen[self._MARKER], "1")
        self.assertEqual(seen[self._LOCK], lock)

    def test_the_window_closes_when_the_agent_returns(self):
        # The engine's own benchmark child follows in the same process. Leaving
        # the marker set would put it back in the deadlock this guards.
        lock = os.path.join(self.ws, "bench.lock")
        self._run_agent(lock)
        self.assertIsNone(os.environ.get(self._MARKER))

    def test_it_closes_even_when_the_agent_raises(self):
        lock = os.path.join(self.ws, "bench.lock")
        old = os.environ.get(self._LOCK)
        os.environ[self._LOCK] = lock
        try:
            def boom(prompt):
                raise RuntimeError("killed")

            oa.optimize_with_agent(_SPEC, self.ws, _CPP, boom)
        finally:
            if old is None:
                os.environ.pop(self._LOCK, None)
            else:
                os.environ[self._LOCK] = old
        self.assertIsNone(os.environ.get(self._MARKER))

    def test_lock_off_leaves_the_agents_environment_alone(self):
        # Zero-cost default, matching bench.sh: with the lock off the agent
        # runs in exactly the environment it runs in today.
        seen = self._run_agent(None)
        self.assertIsNone(seen[self._MARKER])


class TestOptimizeWithAgent(_Ws):
    def test_returns_the_agents_edit(self):
        def agent(prompt):
            with open(os.path.join(self.ws, "widgetNode.cpp"), "w") as fh:
                fh.write("// FASTER\n")
            return "done"

        out = oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent)
        self.assertEqual(out, "// FASTER\n")

    def test_untouched_file_returns_the_original(self):
        out = oa.optimize_with_agent(_SPEC, self.ws, _CPP, lambda p: "nothing")
        self.assertEqual(out, _CPP)

    def test_emptied_file_falls_back_to_the_original(self):
        def agent(prompt):
            open(os.path.join(self.ws, "widgetNode.cpp"), "w").close()
            return ""

        self.assertEqual(oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent),
                         _CPP)

    def test_cancel_propagates(self):
        # Cancel is the user saying stop. Nothing should be gated or kept.
        from mpynode.native.ai.llm_client import PortCancelled

        def agent(prompt):
            with open(os.path.join(self.ws, "widgetNode.cpp"), "w") as fh:
                fh.write("// half-finished\n")
            raise PortCancelled()

        with self.assertRaises(PortCancelled):
            oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent)

    def test_timeout_keeps_work_the_agent_already_finished(self):
        # The agent's work IS the file on disk, not its reply. A wall-clock kill
        # that lands after it finished editing must not throw that away -- the
        # external compile+parity+benchmark gate is what decides if it is good.
        import subprocess

        def agent(prompt):
            with open(os.path.join(self.ws, "widgetNode.cpp"), "w") as fh:
                fh.write("// FASTER\n")
            raise subprocess.TimeoutExpired(["claude"], 2400)

        out = oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent)
        self.assertEqual(out, "// FASTER\n")

    def test_failure_before_any_edit_returns_the_original(self):
        def agent(prompt):
            raise RuntimeError("boom")

        self.assertEqual(oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent),
                         _CPP)

    def test_tampering_still_discards_even_when_the_agent_timed_out(self):
        # A timeout must not become a way to smuggle a rewritten ruler past the
        # guard that would otherwise catch it.
        import subprocess

        def agent(prompt):
            with open(os.path.join(self.ws, "bench.sh"), "a") as fh:
                fh.write("\necho 'MEDIAN_MS: 0.001'\n")
            with open(os.path.join(self.ws, "widgetNode.cpp"), "w") as fh:
                fh.write("// allegedly faster\n")
            raise subprocess.TimeoutExpired(["claude"], 2400)

        self.assertEqual(oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent),
                         _CPP)

    def test_tampering_with_bench_discards_the_candidate(self):
        # The agent has a shell, so "make the number go down" is also
        # satisfiable by editing the thing that prints the number.
        def agent(prompt):
            with open(os.path.join(self.ws, "bench.sh"), "a") as fh:
                fh.write("\necho 'MEDIAN_MS: 0.001'\n")
            with open(os.path.join(self.ws, "widgetNode.cpp"), "w") as fh:
                fh.write("// allegedly faster\n")
            return "done"

        self.assertEqual(oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent),
                         _CPP)

    def test_tampering_with_build_flags_discards_the_candidate(self):
        def agent(prompt):
            with open(os.path.join(self.ws, "build.sh"), "a") as fh:
                fh.write("\n# -ffast-math\n")
            with open(os.path.join(self.ws, "widgetNode.cpp"), "w") as fh:
                fh.write("// allegedly faster\n")
            return "done"

        self.assertEqual(oa.optimize_with_agent(_SPEC, self.ws, _CPP, agent),
                         _CPP)

    def test_task_tells_the_agent_the_harness_is_checksummed(self):
        _p, task = oa.build_workspace(_SPEC, self.ws, _CPP)
        self.assertIn("checksummed", task)
        self.assertIn("ONE file you may modify", task)

    def test_agent_receives_the_task_text(self):
        seen = {}
        oa.optimize_with_agent(_SPEC, self.ws, _CPP,
                               lambda p: seen.setdefault("p", p))
        self.assertIn("Optimize", seen["p"])
        self.assertIn("./bench.sh", seen["p"])


class TestUltracodeDirective(unittest.TestCase):
    """ultracode must say something TRUE about the optimizer agent.

    The porter and the optimizer are opposite kinds of job: the porter is a
    blindfolded text task whose deliverable is its reply; the optimizer is a
    tool-using agent whose deliverable is the edited file and whose reply is
    discarded. They cannot share one directive.
    """

    def setUp(self):
        self._saved = os.environ.get("MPYNODE_PORT_ULTRACODE")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MPYNODE_PORT_ULTRACODE", None)
        else:
            os.environ["MPYNODE_PORT_ULTRACODE"] = self._saved

    def _argv(self, ultracode):
        from mpynode.native.ai import llm_client
        if ultracode:
            os.environ["MPYNODE_PORT_ULTRACODE"] = "1"
        else:
            os.environ.pop("MPYNODE_PORT_ULTRACODE", None)
        seen = {}

        def fake_run(cmd, stdin_text, binp, **kw):
            seen["cmd"] = list(cmd)
            seen["prompt"] = stdin_text
            return "ok"

        orig = llm_client._run_cli_proc
        llm_client._run_cli_proc = fake_run
        try:
            llm_client.make_cli_agent_fn("/tmp/ultracode_test_ws")("DO IT")
        finally:
            llm_client._run_cli_proc = orig
        return seen

    def _directive(self, cmd):
        return (cmd[cmd.index("--append-system-prompt") + 1]
                if "--append-system-prompt" in cmd else "")

    def test_off_adds_no_system_prompt(self):
        self.assertNotIn("--append-system-prompt", self._argv(False)["cmd"])

    def test_on_still_carries_the_ultracode_keyword(self):
        # The literal keyword in the prompt BODY is what triggers the behaviour.
        self.assertTrue(self._argv(True)["prompt"].startswith("ultracode"))

    def test_on_does_not_deny_the_tools_it_was_just_granted(self):
        seen = self._argv(True)
        cmd, txt = seen["cmd"], self._directive(seen["cmd"])
        allow = cmd[cmd.index("--allowedTools") + 1]
        self.assertIn("Bash", allow)
        self.assertNotIn("NO file, shell", txt)

    def test_on_does_not_demand_the_reply_be_the_deliverable(self):
        # The optimizer's work is the FILE. Telling it the final message is the
        # answer steers it straight back into one-shot retyping.
        txt = self._directive(self._argv(True)["cmd"])
        self.assertNotIn("FINAL message MUST be ONLY", txt)
        self.assertNotIn("PORT markers", txt)

    def test_on_describes_optimizing_not_porting(self):
        txt = self._directive(self._argv(True)["cmd"])
        self.assertNotIn("porting ONE Maya node", txt)
        self.assertIn("faster", txt.lower())


if __name__ == "__main__":
    unittest.main()
