"""The compile pipeline is three GATED stages, and each leaves a durable artifact.

    1  transpile   always runs, never calls an LLM, always produces a .cpp
    2  AI assist   opt-out; fills the PORT region the transpiler left empty
    3  AI optimize  opt-in; iterative speed passes

Two properties are pinned here.

**Stage 1 is a deliverable, not an intermediate.** ``codegen.generate_cpp`` is
already 100% deterministic -- when it cannot lower a compute it emits an EMPTY
``PORT_BEGIN``/``PORT_END`` region carrying the Python as comments. That text is
exactly the "baseline .cpp with comments ready for the next AI agent" a user
should be able to ask for, and it used to be thrown away. It is now written to
``build/stages/<Type>/1_transpiled.cpp`` on every path, including a port-cache
hit.

**``ai_assist=False`` must not be silently upgraded.** A node needing the porter
stops at stage 1 with ``needs_assist``; it is not compiled and not bundled, and
crucially the LLM is never called. A node that lowers deterministically is
untouched by the flag -- that is the whole point of the split.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import unittest.mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


def _spec(compute, name="stagedProbe"):
    """Minimal portable spec (shape copied from test_native_compile_pipeline)."""
    return {
        "source_node": name,
        "mpy_type":    "mPyNode",
        "suggested": {"node_type_name": name,
                      "class_name": name[:1].upper() + name[1:],
                      "mpx_base": "MPxNode", "type_id": "0x0013a1c0"},
        "inputs":      {"a": {"type": "double"}},
        "outputs":     {"out": {"type": "double"}},
        "compute":     compute,
        "init":        "",
        "portability": {"portable": True, "blockers": []},
    }


# `self.`-form lowers deterministically; the bare form does not (self-only
# contract), which makes it the cheapest spec that reaches the AI porter.
DETERMINISTIC = "self.out = self.a * 2.0"
NEEDS_PORTER  = "out = a * 2.0"


class TestStagesLayout(unittest.TestCase):
    def test_stage_dir_is_under_build_stages(self):
        from mpynode.native.compiler import bundler

        self.assertEqual(
            bundler.stage_dir_for("/tmp/out", "kDTree"),
            os.path.join("/tmp/out", "build", "stages", "kDTree"))
        self.assertEqual(bundler.stages_dir_for("/tmp/out"),
                         os.path.join("/tmp/out", "build", "stages"))

    def test_stages_are_not_swept_by_clean_stale_intermediates(self):
        """stages/ holds the only durable record of how the .cpp was reached.

        _clean_stale_intermediates globs build/ and build/source/ for *.o and
        frag_*.cpp; it must never reach into build/stages/."""
        from mpynode.native.compiler import bundler

        out   = tempfile.mkdtemp(prefix="mpynode-stages-")
        stage = bundler.stage_dir_for(out, "kDTree")
        os.makedirs(os.path.join(stage, "3_optimized"), exist_ok=True)
        keep = [os.path.join(stage, "1_transpiled.cpp"),
                os.path.join(stage, "3_optimized", "00_baseline.cpp"),
                os.path.join(stage, "3_optimized", "01_hoist.o")]
        for p in keep:
            with open(p, "w") as fh:
                fh.write("// x")

        bundler._clean_stale_intermediates(out, keep=[])

        for p in keep:
            self.assertTrue(os.path.isfile(p),
                            "cleanup deleted a durable stage artifact: %s" % p)


class TestStageOneIsAlwaysPersisted(unittest.TestCase):
    def _run(self, compute, **kw):
        from mpynode.native.ai import porter

        seen = {}

        def stage_cb(stage, text):
            seen[stage] = text

        out = tempfile.mkdtemp(prefix="mpynode-stage1-")
        res = porter.port_node(_spec(compute), out, stage_cb=stage_cb, **kw)
        return res, seen

    def test_deterministic_node_emits_stage_one_without_a_port_region(self):
        from mpynode.native.ai import porter

        with unittest.mock.patch.object(
                porter, "compile_cpp", return_value=(True, "", "/tmp/x.bundle")):
            _res, seen = self._run(DETERMINISTIC)

        self.assertIn("1_transpiled", seen)
        self.assertNotIn(porter.codegen.PORT_BEGIN, seen["1_transpiled"])
        self.assertNotIn("2_assisted", seen,
                         "no AI ran, so there is no assisted stage")

    def test_porter_bound_node_emits_stage_one_with_the_empty_port_region(self):
        from mpynode.native.ai import porter

        _res, seen = self._run(NEEDS_PORTER, ai_assist=False)

        self.assertIn("1_transpiled", seen)
        self.assertIn(porter.codegen.PORT_BEGIN, seen["1_transpiled"])

    def test_assisted_stage_is_written_when_the_ai_runs(self):
        from mpynode.native.ai import porter

        with unittest.mock.patch.object(
                porter, "compile_cpp", return_value=(True, "", "/tmp/x.bundle")):
            _res, seen = self._run(
                NEEDS_PORTER, complete_fn=lambda s, u: "out_h.setDouble(0.0);")

        self.assertIn("1_transpiled",          seen)
        self.assertIn("2_assisted",            seen)
        self.assertIn("out_h.setDouble(0.0);", seen["2_assisted"])


class TestAiAssistGate(unittest.TestCase):
    def test_assist_off_stops_at_stage_one_and_never_calls_the_llm(self):
        from mpynode.native.ai import porter

        calls = []

        def complete_fn(system, user):
            calls.append(1)
            return "// should never be reached"

        out = tempfile.mkdtemp(prefix="mpynode-noassist-")
        res = porter.port_node(_spec(NEEDS_PORTER), out,
                               complete_fn=complete_fn, ai_assist=False)

        self.assertEqual(calls, [], "ai_assist=False still called the LLM")
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("needs_assist"))
        self.assertGreaterEqual(res.get("port_regions", 0), 1)
        self.assertIsNone(res.get("bundle"))
        # The baseline .cpp must still exist on disk -- it is the deliverable.
        self.assertTrue(os.path.isfile(res["cpp"]))

    def test_assist_off_does_not_disturb_a_deterministic_node(self):
        from mpynode.native.ai import porter

        with unittest.mock.patch.object(
                porter, "compile_cpp",
                return_value=(True, "", "/tmp/x.bundle")) as cc:
            out = tempfile.mkdtemp(prefix="mpynode-detassist-")
            res = porter.port_node(_spec(DETERMINISTIC), out, ai_assist=False)

        self.assertTrue(cc.called, "a deterministic node must still compile")
        self.assertTrue(res["ok"])
        self.assertFalse(res.get("needs_assist"))

    def test_assist_defaults_on_so_current_behaviour_is_unchanged(self):
        import inspect

        from mpynode.native.ai import porter

        sig = inspect.signature(porter.port_node)
        self.assertIs(sig.parameters["ai_assist"].default, True)


class TestControllerWiring(unittest.TestCase):
    """compile_plugin must honour the gate and always leave stage 1 on disk."""

    def _harness(self):
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import toolchain

        def fake_check_toolchain(maya=None):
            return {"ok": True, "problems": [], "compiler": "clang++"}

        def fake_check_provider(provider=None, model=None):
            return {"ok": True, "problems": [], "provider": "anthropic",
                    "kind": "api"}

        def fake_assemble(nodes, plugin_name, out_dir, **k):
            path = os.path.join(out_dir, plugin_name + ".bundle")
            with open(path, "w") as fh:
                fh.write("")
            return {"ok": True, "bundle": path,
                    "nodes": [{"name": n, "id": 1, "status": "compiled",
                               "reason": ""} for (n, _c) in nodes],
                    "dropped": [], "shared_helpers": []}

        return (unittest.mock.patch.object(toolchain, "check_toolchain",
                                           fake_check_toolchain),
                unittest.mock.patch.object(porter, "check_provider",
                                           fake_check_provider),
                unittest.mock.patch.object(bundler, "assemble", fake_assemble))

    def test_compile_plugin_defaults_to_assist_on(self):
        import inspect

        from mpynode.native.toolchain import compile_controller as cc

        sig = inspect.signature(cc.compile_plugin)
        self.assertIs(sig.parameters["ai_assist"].default, True)

    def test_assist_off_drops_the_node_but_leaves_the_baseline_cpp(self):
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import compile_controller as cc

        tc, pv, asm = self._harness()
        with tempfile.TemporaryDirectory() as d, tc, pv, asm:
            res = cc.compile_plugin(
                [_spec(NEEDS_PORTER)], "myPlugin", d, strict=False,
                verify=False, reuse_cache=False, provider="anthropic",
                model="m", ai_assist=False)

            stage = os.path.join(bundler.stage_dir_for(d, "stagedProbe"),
                                 "1_transpiled.cpp")
            self.assertTrue(os.path.isfile(stage),
                            "the deterministic baseline .cpp is the whole "
                            "deliverable of an assist-off run")
            with open(stage) as fh:
                self.assertIn("BEGIN PORTED COMPUTE", fh.read())

        row = [r for r in res["nodes"]
               if r.get("type_name") == "stagedProbe"][0]
        self.assertIn("assist", row.get("build_reason", "").lower())

    def test_assist_off_does_not_need_a_reachable_ai_provider(self):
        """The point of the gate is users with no AI budget. An unreachable
        provider must not abort a build that will never call one."""
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import toolchain
        from mpynode.native.toolchain import compile_controller as cc

        def dead_provider(provider=None, model=None):
            return {"ok": False, "problems": ["No API key configured"],
                    "provider": "anthropic", "kind": "api"}

        def fake_check_toolchain(maya=None):
            return {"ok": True, "problems": [], "compiler": "clang++"}

        def fake_assemble(nodes, plugin_name, out_dir, **k):
            path = os.path.join(out_dir, plugin_name + ".bundle")
            with open(path, "w") as fh:
                fh.write("")
            return {"ok": True, "bundle": path, "nodes": [], "dropped": [],
                    "shared_helpers": []}

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(toolchain, "check_toolchain",
                                        fake_check_toolchain), \
             unittest.mock.patch.object(porter, "check_provider",
                                        dead_provider), \
             unittest.mock.patch.object(bundler, "assemble", fake_assemble):
            res = cc.compile_plugin(
                [_spec(NEEDS_PORTER)], "myPlugin", d, strict=False,
                verify=False, reuse_cache=False, provider="anthropic",
                model="m", ai_assist=False)

            self.assertTrue(
                os.path.isfile(os.path.join(
                    bundler.stage_dir_for(d, "stagedProbe"),
                    "1_transpiled.cpp")))

        self.assertFalse(any("provider" in e.lower() for e in res["errors"]),
                         res["errors"])

    def test_assist_off_ignores_the_port_cache_for_llm_bound_nodes(self):
        """A cache hit would ship AI-authored C++ inside a run whose whole
        contract is 'no AI touched this'."""
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import port_cache

        looked_up = []

        def spy_get_path(key):
            looked_up.append(key)
            return None

        tc, pv, asm = self._harness()
        with tempfile.TemporaryDirectory() as d, tc, pv, asm, \
             unittest.mock.patch.object(port_cache, "get_path", spy_get_path):
            cc.compile_plugin(
                [_spec(NEEDS_PORTER)], "myPlugin", d, strict=False,
                verify=False, reuse_cache=True, provider="anthropic",
                model="m", ai_assist=False)

        self.assertEqual(looked_up, [],
                         "assist-off consulted the port cache")

    def test_cache_hit_still_writes_the_transpiled_stage(self):
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import port_cache

        cached = tempfile.NamedTemporaryFile(
            suffix=".cpp", delete=False, mode="w")
        cached.write("// cached port\n")
        cached.close()

        tc, pv, asm = self._harness()
        with tempfile.TemporaryDirectory() as d, tc, pv, asm, \
             unittest.mock.patch.object(port_cache, "get_path",
                                        lambda key: cached.name):
            cc.compile_plugin(
                [_spec(NEEDS_PORTER)], "myPlugin", d, strict=False,
                verify=False, reuse_cache=True, provider="anthropic",
                model="m")

            self.assertTrue(
                os.path.isfile(os.path.join(
                    bundler.stage_dir_for(d, "stagedProbe"),
                    "1_transpiled.cpp")),
                "a cache hit must not leave a hole in the stage history")

            assisted = os.path.join(bundler.stage_dir_for(d, "stagedProbe"),
                                    "2_assisted.cpp")
            self.assertTrue(os.path.isfile(assisted),
                            "cached C++ for an LLM-bound node IS the assisted "
                            "stage; omitting it reads as 'the AI never ran'")
            with open(assisted) as fh:
                self.assertIn("cached port", fh.read())

    def test_a_cache_hit_does_not_narrate_an_ai_call_it_did_not_make(self):
        """The stage artifact must still be recorded (the cached body IS
        AI-written), but "AI filled the compute regions" is an event of some
        EARLIER run -- printed here, just above "reusing cached C++ (no AI
        call)", it contradicts the very next line."""
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import port_cache

        cached = tempfile.NamedTemporaryFile(
            suffix=".cpp", delete=False, mode="w")
        cached.write("// cached port\n")
        cached.close()

        events = []
        tc, pv, asm = self._harness()
        with tempfile.TemporaryDirectory() as d, tc, pv, asm, \
             unittest.mock.patch.object(port_cache, "get_path",
                                        lambda key: cached.name):
            cc.compile_plugin(
                [_spec(NEEDS_PORTER)], "myPlugin", d, strict=False,
                verify=False, reuse_cache=True, provider="anthropic",
                model="m", progress_cb=events.append)

        seq = [(e.get("stage"), e.get("status"), e.get("detail"))
               for e in events if e.get("stage") in ("stage", "cache")]
        kinds = [d for (s, _st, d) in seq if s == "stage"]
        self.assertIn("1_transpiled", kinds)
        self.assertNotIn("2_assisted", kinds,
                         "the plain assisted event narrates an AI call")
        self.assertIn("2_assisted_cached", kinds)

        # ...and it lands AFTER the cache-hit line it used to precede.
        order = [i for i, (s, st, dt) in enumerate(seq)
                 if (s == "cache" and st == "hit") or dt == "2_assisted_cached"]
        self.assertEqual(len(order), 2)
        cache_at = [i for i, (s, st, _d) in enumerate(seq)
                    if s == "cache" and st == "hit"][0]
        assisted_at = [i for i, (_s, _st, dt) in enumerate(seq)
                       if dt == "2_assisted_cached"][0]
        self.assertLess(cache_at, assisted_at)

    def test_an_unwritable_stage_dir_does_not_claim_the_stage_landed(self):
        """``_write_stage`` swallows its own OSError and returns None. Gating on
        the read alone ticks 'AI assist done' and writes 'AI-assisted (cached)'
        into the row for a file that is not on disk -- the exact
        MPYNODE_HOME-is-unwritable case."""
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import port_cache

        cached = tempfile.NamedTemporaryFile(
            suffix=".cpp", delete=False, mode="w")
        cached.write("// cached port\n")
        cached.close()

        events = []
        tc, pv, asm = self._harness()
        with tempfile.TemporaryDirectory() as d, tc, pv, asm, \
             unittest.mock.patch.object(port_cache, "get_path",
                                        lambda key: cached.name), \
             unittest.mock.patch.object(cc, "_write_stage",
                                        lambda *a, **k: None):
            cc.compile_plugin(
                [_spec(NEEDS_PORTER)], "myPlugin", d, strict=False,
                verify=False, reuse_cache=True, provider="anthropic",
                model="m", progress_cb=events.append)

        kinds = [e.get("detail") for e in events if e.get("stage") == "stage"]
        self.assertNotIn("2_assisted_cached", kinds)

    def test_the_cached_assist_event_still_lights_the_rail(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        self.assertIn("2_assisted_cached", CompileDialog._STAGE_CELL)
        self.assertIsNone(CompileDialog._narration_line(
            "stage", "ok", "kDTree", "2_assisted_cached"),
            "the cache-hit line already said it; a second line is noise")

    def test_a_deterministic_node_gets_no_assisted_stage_from_the_cache(self):
        """The cached .cpp for a node the transpiler fully lowers was never
        touched by an AI, and the stage history must not imply it was."""
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import port_cache

        cached = tempfile.NamedTemporaryFile(
            suffix=".cpp", delete=False, mode="w")
        cached.write("// cached deterministic\n")
        cached.close()

        tc, pv, asm = self._harness()
        with tempfile.TemporaryDirectory() as d, tc, pv, asm, \
             unittest.mock.patch.object(port_cache, "get_path",
                                        lambda key: cached.name):
            cc.compile_plugin(
                [_spec(DETERMINISTIC)], "myPlugin", d, strict=False,
                verify=False, reuse_cache=True, provider="anthropic",
                model="m")

            self.assertFalse(os.path.isfile(os.path.join(
                bundler.stage_dir_for(d, "stagedProbe"), "2_assisted.cpp")))

    def test_optimize_forces_assist_on(self):
        """Optimising a source with unfilled PORT regions is meaningless."""
        from mpynode.native.toolchain import compile_controller as cc

        self.assertTrue(cc._resolve_ai_assist(ai_assist=False, optimize=True))
        self.assertTrue(cc._resolve_ai_assist(ai_assist=True, optimize=False))
        self.assertFalse(cc._resolve_ai_assist(ai_assist=False,
                                               optimize=False))


class TestOptimizerRoundMetadata(unittest.TestCase):
    """Every optimize round must say what it tried, and leave the source behind.

    The external agent run this mimics named each revision for its THEME
    (``v01_branchpeel``, ``v05_kdtree``, ``v07_cache``), which is simultaneously
    the filename, the live progress line and the report heading. Today the
    agent's account of its own work is discarded (``agent_fn(task)``'s return
    value is unused) and only the last candidate survives on disk, so a rejected
    round -- the most instructive kind -- leaves no trace at all.
    """

    def _engine(self, **kw):
        from mpynode.native.ai import optimizer

        return optimizer

    def _adapters(self, metas, times):
        """Adapters whose Nth round proposes source N and gets faster each time."""
        from mpynode.native.ai.optimizer import ParityVerdict, PARITY_PASS

        state = {"i": 0}

        def optimize_fn(cpp):
            state["i"] += 1
            return "// candidate %d\n%s" % (state["i"], cpp)

        def round_meta_fn():
            return metas[state["i"] - 1]

        def fix_fn(cpp, errors):
            return cpp

        def compile_fn(cpp):
            return True, "", "/tmp/fake.bundle"

        def parity_fn(bundle):
            return ParityVerdict(PARITY_PASS)

        def benchmark_fn(bundle):
            return times[min(state["i"], len(times) - 1)]

        return dict(optimize_fn=optimize_fn, fix_fn=fix_fn,
                    compile_fn=compile_fn, parity_fn=parity_fn,
                    benchmark_fn=benchmark_fn, round_meta_fn=round_meta_fn)

    def test_round_record_carries_the_agent_theme(self):
        optimizer = self._engine()

        metas = [{"slug": "hoist_invariant",
                  "theme":             "peel the p==0 test out of the argmin",
                  "hypothesis":        "the invariant disjunct blocks NEON packing",
                  "predicted_speedup": 2.0,
                  "risk": "none -- pure loop restructure"}]
        ad  = self._adapters(metas, times=[100.0, 50.0])

        res = optimizer.optimize_cpp("// baseline", rounds=1, **ad)

        self.assertTrue(res.accepted)
        rec = [r for r in res.ledger if r.index == 1][0]
        self.assertEqual(rec.slug, "hoist_invariant")
        self.assertEqual(rec.theme, "peel the p==0 test out of the argmin")
        self.assertEqual(rec.predicted_speedup, 2.0)
        self.assertIsNotNone(rec.duration_s)

    def test_every_round_is_handed_to_round_cb_including_rejects(self):
        optimizer = self._engine()

        metas = [{"slug": "good_one", "theme": "t1", "predicted_speedup": 2.0},
                 {"slug": "no_win", "theme": "t2", "predicted_speedup": 3.0}]
        # round 1: 100 -> 50 (accept). round 2: 50 -> 49.9 (not faster enough).
        ad   = self._adapters(metas, times=[100.0, 50.0, 49.9])

        seen = []

        def round_cb(record, cpp_text):
            seen.append((record.index, record.outcome, record.slug, cpp_text))

        res = optimizer.optimize_cpp("// baseline", rounds=2,
                                     round_cb=round_cb, **ad)

        idx = [s[0] for s in seen]
        self.assertEqual(idx, [0, 1, 2], "baseline + both rounds must be seen")
        self.assertEqual(seen[0][1], "baseline")
        self.assertEqual(seen[1][1], "accept")
        self.assertEqual(seen[2][1], "not-faster")
        self.assertEqual(seen[2][2], "no_win",
                         "a rejected round still has a theme worth recording")
        self.assertIn("// baseline", seen[0][3])
        self.assertTrue(res.accepted)

    def test_a_missing_or_broken_meta_fn_never_breaks_a_round(self):
        """The metadata is a report nicety; it must not gate optimization."""
        optimizer = self._engine()

        ad                  = self._adapters([{}], times=[100.0, 50.0])
        ad["round_meta_fn"] = lambda: (_ for _ in ()).throw(RuntimeError("x"))

        res = optimizer.optimize_cpp("// baseline", rounds=1, **ad)

        self.assertTrue(res.accepted)
        rec = [r for r in res.ledger if r.index == 1][0]
        self.assertIsNone(rec.slug)

    def test_the_round_narrates_its_intent_before_it_is_judged(self):
        """"What is it doing right now" is the question the log cannot answer
        today: the only per-round lines are outcomes, printed after the fact."""
        optimizer = self._engine()

        metas = [{"slug": "simd_argmin", "theme": "vectorise the argmin",
                  "predicted_speedup": 3.0, "risk": "medium"}]
        ad    = self._adapters(metas, times=[100.0, 50.0])
        lines = []

        optimizer.optimize_cpp("// baseline", rounds=1, label="kDTree",
                               log_cb=lines.append, **ad)

        intent = [l for l in lines if "vectorise the argmin" in l]
        self.assertEqual(len(intent), 1, lines)
        self.assertIn("round 1/1", intent[0])
        self.assertIn("3.00x",     intent[0])
        self.assertIn("medium",    intent[0])
        self.assertIn("[kDTree]",  intent[0])
        # And it must land BEFORE the measurement it predicts.
        self.assertLess(lines.index(intent[0]),
                        [i for i, l in enumerate(lines) if "ACCEPT" in l][0])

    def test_a_round_says_it_began_before_the_call_that_can_last_minutes(self):
        """The intent line cannot announce the round: its theme comes OUT of the
        optimizer, so it does not exist until the blocking propose call returns
        -- which can be tens of minutes. Without a line at the top of the round
        the first sign the round exists is its outcome."""
        optimizer = self._engine()

        ad = self._adapters([{"slug": "s", "theme": "vectorise the argmin"}],
                            times=[100.0, 50.0])
        propose          = ad["optimize_fn"]
        lines            = []
        seen_when_called = []

        def optimize_fn(cpp):
            seen_when_called.extend(lines)
            return propose(cpp)

        ad["optimize_fn"] = optimize_fn
        optimizer.optimize_cpp("// baseline", rounds=1, label="kDTree",
                               log_cb=lines.append, **ad)

        self.assertIn("[kDTree] round 1/1 starting", seen_when_called,
                      lines)

    def test_a_themeless_round_still_announces_that_it_started(self):
        """The one line that must not depend on the optimizer narrating itself
        -- a silent round is exactly the case it exists for."""
        optimizer = self._engine()

        ad    = self._adapters([{}], times=[100.0, 50.0])
        lines = []

        optimizer.optimize_cpp("// baseline", rounds=1, log_cb=lines.append,
                               **ad)

        self.assertIn("round 1/1 starting", lines)

    def test_a_themeless_round_says_nothing_rather_than_something_hollow(self):
        optimizer = self._engine()

        ad    = self._adapters([{}], times=[100.0, 50.0])
        lines = []

        optimizer.optimize_cpp("// baseline", rounds=1, log_cb=lines.append,
                               **ad)

        self.assertEqual([l for l in lines if "trying" in l], [])

    def test_a_compiled_round_remembers_where_its_binary_was_built(self):
        """Needed to keep the per-round bundle; a transient scratch path, so it
        must NOT reach the durable ledger."""
        optimizer = self._engine()

        ad  = self._adapters([{"slug": "s1"}], times=[100.0, 50.0])
        res = optimizer.optimize_cpp("// baseline", rounds=1, **ad)

        rec = [r for r in res.ledger if r.index == 1][0]
        self.assertEqual(rec.bundle, "/tmp/fake.bundle")

    def test_the_scratch_bundle_path_is_not_written_to_rounds_json(self):
        import json

        from mpynode.native.ai import optimizer, optimizer_live
        from mpynode.native.compiler import bundler

        ad  = self._adapters([{"slug": "s1"}], times=[100.0, 50.0])
        res = optimizer.optimize_cpp("// baseline", rounds=1, **ad)

        out = tempfile.mkdtemp(prefix="mpynode-ledger-")
        optimizer_live.write_rounds_json(out, "kDTree", res)
        with open(os.path.join(bundler.stage_dir_for(out, "kDTree"),
                               "rounds.json")) as fh:
            blob = fh.read()
        self.assertNotIn("fake.bundle", blob)
        json.loads(blob)


class TestKeepIntermediates(unittest.TestCase):
    """"Keep intermediates" keeps the per-round BINARY, not just its source.

    The reference run this mimics kept a loadable .bundle per revision, which is
    what lets someone try round 3 in Maya instead of reading round 3. Off by
    default (~90 KB each); the .cpp, the ledger and the reports are always kept.
    """

    def _round(self, index, slug, bundle):
        from mpynode.native.ai.optimizer import RoundRecord

        return RoundRecord(index, "accept", slug=slug, bundle=bundle)

    def _fake_bundle(self, root, name):
        d = os.path.join(root, name)
        os.makedirs(os.path.join(d, "Contents"), exist_ok=True)
        with open(os.path.join(d, "Contents", "binary"), "w") as fh:
            fh.write("MACHO")
        return d

    def test_the_bundle_is_kept_beside_its_source(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.compiler import bundler

        out     = tempfile.mkdtemp(prefix="mpynode-keepint-")
        scratch = tempfile.mkdtemp(prefix="mpynode-keepint-scr-")
        w       = optimizer_live.make_version_writer(out, "kDTree", keep_bundles=True)

        w(self._round(1, "simd_argmin",
                      self._fake_bundle(scratch, "kDTree.bundle")), "// v1")

        d = os.path.join(bundler.stage_dir_for(out, "kDTree"), "3_optimized")
        self.assertEqual(sorted(os.listdir(d)),
                         ["01_simd_argmin.bundle", "01_simd_argmin.cpp"])
        self.assertTrue(os.path.isfile(os.path.join(
            d, "01_simd_argmin.bundle", "Contents", "binary")))

    def test_off_by_default_only_the_source_is_kept(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.compiler import bundler

        out     = tempfile.mkdtemp(prefix="mpynode-keepoff-")
        scratch = tempfile.mkdtemp(prefix="mpynode-keepoff-scr-")
        w       = optimizer_live.make_version_writer(out, "kDTree")

        w(self._round(1, "simd_argmin",
                      self._fake_bundle(scratch, "kDTree.bundle")), "// v1")

        d = os.path.join(bundler.stage_dir_for(out, "kDTree"), "3_optimized")
        self.assertEqual(os.listdir(d), ["01_simd_argmin.cpp"])

    def test_a_round_with_no_binary_still_keeps_its_source(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.compiler import bundler

        out  = tempfile.mkdtemp(prefix="mpynode-keepnone-")
        w    = optimizer_live.make_version_writer(out, "kDTree", keep_bundles=True)

        path = w(self._round(2, "did_not_build", None), "// v2")

        d = os.path.join(bundler.stage_dir_for(out, "kDTree"), "3_optimized")
        self.assertEqual(os.listdir(d), ["02_did_not_build.cpp"])
        self.assertTrue(path)

    def test_the_choice_is_threaded_from_the_dialog_to_the_writer(self):
        import inspect

        from mpynode.native.ai import optimizer_live
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.ui.dialogs import compile_dialog

        self.assertIn("keep_intermediates",
                      inspect.signature(cc.compile_plugin).parameters)
        self.assertIn("keep_intermediates",
                      inspect.signature(optimizer_live.optimize_surviving)
                      .parameters)
        self.assertIn("keep_bundles",
                      inspect.signature(optimizer_live.make_version_writer)
                      .parameters)
        self.assertEqual(
            inspect.getsource(compile_dialog).count(
                "keep_intermediates=keep_intermediates"), 2,
            "both the single and multi-version paths must pass it")


class TestOptimizerVersionsOnDisk(unittest.TestCase):
    def test_versions_are_written_with_index_and_slug(self):
        from mpynode.native.ai import optimizer_live

        out = tempfile.mkdtemp(prefix="mpynode-versions-")
        w   = optimizer_live.make_version_writer(out, "kDTree")

        from mpynode.native.ai.optimizer import RoundRecord

        w(RoundRecord(0, "baseline"), "// base")
        w(RoundRecord(1, "accept", slug="hoist_invariant"), "// v1")
        w(RoundRecord(2, "parity-fail", slug="soa_split"), "// v2")

        from mpynode.native.compiler import bundler

        d = os.path.join(bundler.stage_dir_for(out, "kDTree"), "3_optimized")
        self.assertEqual(sorted(os.listdir(d)),
                         ["00_baseline.cpp", "01_hoist_invariant.cpp",
                          "02_soa_split.cpp"])

    def test_slugs_are_sanitised_into_filenames(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.ai.optimizer import RoundRecord
        from mpynode.native.compiler import bundler

        out = tempfile.mkdtemp(prefix="mpynode-slugs-")
        w   = optimizer_live.make_version_writer(out, "kDTree")
        w(RoundRecord(1, "accept", slug="NEON argmin / 2 accumulators!"), "// x")
        w(RoundRecord(2, "accept", slug=None), "// y")

        d     = os.path.join(bundler.stage_dir_for(out, "kDTree"), "3_optimized")
        names = sorted(os.listdir(d))
        self.assertEqual(len(names), 2)
        self.assertTrue(names[0].startswith("01_"), names)
        self.assertNotIn("/", names[0])
        self.assertNotIn(" ", names[0])
        # No slug -> fall back to the outcome so the file still says something.
        self.assertEqual(names[1], "02_accept.cpp")


class TestOptimizeSurvivingWritesTheHistory(unittest.TestCase):
    def _node(self, tmp, name, text):
        from mpynode.native.compiler import bundler

        src = bundler.source_dir_for(tmp)
        os.makedirs(src, exist_ok=True)
        p = os.path.join(src, name + ".cpp")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def test_versions_and_rounds_json_land_under_stages(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.ai.optimizer import OptimizeResult, RoundRecord
        from mpynode.native.compiler import bundler

        ledger = [
            RoundRecord(0, "baseline", compiled=True, ms=100.0),
            RoundRecord(1, "accept", compiled=True, parity="pass", ms=50.0,
                        speedup=2.0, slug="hoist_invariant",
                        theme="peel the invariant test out of the argmin",
                        predicted_speedup=2.0, duration_s=41.2),
            RoundRecord(2, "not-faster", compiled=True, parity="pass", ms=49.9,
                        slug="soa_split", theme="three double streams",
                        predicted_speedup=3.0, duration_s=55.0),
        ]

        def engine(baseline, round_cb=None, **kw):
            # Mirror the real engine: hand every resolved round to round_cb.
            for rec in ledger:
                round_cb(rec, "// source for round %d" % rec.index)
            return OptimizeResult(True, "WINNER", 100.0, 50.0, 2.0, 2, ledger,
                                  "accepted (2.00x)")

        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._node(tmp, "kDTree", "BASELINE")
            optimizer_live.optimize_surviving(
                [("kDTree", cpp, {"suggested": {}})], tmp,
                verify_fn=lambda b, r: {}, engine=engine,
                adapters_factory=lambda *a, **k: {})

            stage    = bundler.stage_dir_for(tmp, "kDTree")
            versions = sorted(os.listdir(os.path.join(stage, "3_optimized")))
            self.assertEqual(versions, ["00_baseline.cpp",
                                        "01_hoist_invariant.cpp",
                                        "02_soa_split.cpp"])

            import json as _json
            with open(os.path.join(stage, "rounds.json")) as fh:
                doc = _json.load(fh)

        self.assertTrue(doc["accepted"])
        self.assertEqual(doc["speedup"], 2.0)
        self.assertEqual(len(doc["ledger"]), 3)
        self.assertEqual(doc["ledger"][1]["slug"], "hoist_invariant")
        self.assertEqual(doc["ledger"][2]["predicted_speedup"], 3.0)
        self.assertTrue(doc["parity_gate"],
                        "the report must state WHICH gate judged these rounds")

    def test_parity_gate_records_that_there_was_no_gate(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.ai.optimizer import OptimizeResult
        from mpynode.native.compiler import bundler

        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._node(tmp, "kDTree", "BASELINE")
            optimizer_live.optimize_surviving(
                [("kDTree", cpp, {"suggested": {}})], tmp,
                verify_fn=None,
                engine=lambda baseline, **kw: OptimizeResult(
                    False, baseline, 1.0, 1.0, 1.0, 0, [], "no gain"),
                adapters_factory=lambda *a, **k: {})

            import json as _json
            with open(os.path.join(bundler.stage_dir_for(tmp, "kDTree"),
                                   "rounds.json")) as fh:
                doc = _json.load(fh)

        self.assertEqual(doc["parity_gate"], "none")


class TestScratchLandsWhereTheSweepLooks(unittest.TestCase):
    """``out_dir`` is the node ROOT, so the scratch has to be derived, not joined.

    ``_clean_working_subdirs`` removes ``build/_optscratch/``. The round
    physically runs there, and it is a whole build tree plus an agent workspace
    per optimized node -- built off the root instead, it lands one level up and
    nothing ever cleans it. This is the other half of the stages fix: both paths
    come from the same argument, so moving one moves the other.
    """

    def test_the_scratch_lands_under_build_not_the_root(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.ai.optimizer import OptimizeResult
        from mpynode.native.compiler import bundler

        seen = {}

        def adapters_factory(spec, scratch, *a, **k):
            seen["scratch"] = scratch
            return {}

        with tempfile.TemporaryDirectory() as tmp:
            src = bundler.source_dir_for(tmp)
            os.makedirs(src, exist_ok=True)
            cpp = os.path.join(src, "kDTree.cpp")
            with open(cpp, "w") as fh:
                fh.write("BASELINE")

            optimizer_live.optimize_surviving(
                [("kDTree", cpp, {"suggested": {}})], tmp,
                verify_fn=None,
                engine=lambda baseline, **kw: OptimizeResult(
                    False, baseline, 1.0, 1.0, 1.0, 0, [], "no gain"),
                adapters_factory=adapters_factory)

            self.assertEqual(
                seen.get("scratch"),
                os.path.join(bundler.build_dir_for(tmp),
                             optimizer_live.OPT_SCRATCH_DIRNAME, "kDTree"))
            self.assertTrue(os.path.isdir(seen["scratch"]))


class TestAgentRoundMetadata(unittest.TestCase):
    def test_round_json_is_parsed_and_coerced(self):
        from mpynode.native.ai import optimizer_agent

        ws = tempfile.mkdtemp(prefix="mpynode-roundmeta-")
        with open(os.path.join(ws, optimizer_agent.ROUND_JSON), "w") as fh:
            fh.write('{"slug": "simd_argmin", "theme": "vectorise", '
                     '"predicted_speedup": "2.5", "junk": 1}')

        meta = optimizer_agent.read_round_meta(ws)

        self.assertEqual(meta["slug"], "simd_argmin")
        self.assertEqual(meta["predicted_speedup"], 2.5)
        self.assertNotIn("junk", meta)

    def test_malformed_round_json_is_not_fatal(self):
        from mpynode.native.ai import optimizer_agent

        ws = tempfile.mkdtemp(prefix="mpynode-roundbad-")
        self.assertEqual(optimizer_agent.read_round_meta(ws), {})
        with open(os.path.join(ws, optimizer_agent.ROUND_JSON), "w") as fh:
            fh.write("{ truncated")
        self.assertEqual(optimizer_agent.read_round_meta(ws), {})
        with open(os.path.join(ws, optimizer_agent.ROUND_JSON), "w") as fh:
            fh.write('{"slug": "x", "predicted_speedup": "fast"}')
        self.assertEqual(optimizer_agent.read_round_meta(ws), {"slug": "x"})

    def test_stale_round_json_is_cleared_when_the_workspace_is_rebuilt(self):
        """The workspace is reused per round; a leftover file would mislabel
        this round's candidate with the previous round's theme."""
        from mpynode.native.ai import optimizer_agent

        ws = tempfile.mkdtemp(prefix="mpynode-roundstale-")
        with open(os.path.join(ws, optimizer_agent.ROUND_JSON), "w") as fh:
            fh.write('{"slug": "previous_round"}')

        optimizer_agent.build_workspace(
            _spec(DETERMINISTIC), ws, "// cpp",
            maya="/Applications/Autodesk/maya2026/Maya.app/Contents")

        self.assertEqual(optimizer_agent.read_round_meta(ws), {})

    def test_the_task_asks_for_the_round_file(self):
        from mpynode.native.ai import optimizer_agent

        ws = tempfile.mkdtemp(prefix="mpynode-roundtask-")
        _cpp, task = optimizer_agent.build_workspace(
            _spec(DETERMINISTIC), ws, "// cpp",
            maya="/Applications/Autodesk/maya2026/Maya.app/Contents")

        self.assertIn("ROUND.json", task)
        self.assertIn("predicted_speedup", task)
        self.assertIn("slug", task)


class TestScratchCleanup(unittest.TestCase):
    """What survives a compile is the source and the story, never the lint.

    ``_clean_working_subdirs`` already swept ``build/<Type>/``; the optimizer's
    working tree (``build/_optscratch/<Type>`` -- a whole build dir plus the
    agent workspace, per optimized node) was never cleaned by anyone. It is now
    swept by the same rule, under the same flag, and with the same exception:
    a DROPPED node keeps its evidence.
    """

    def _tree(self, rows):
        """A realistic out_dir; returns (out_dir, build_dir)."""
        from mpynode.native.compiler import bundler
        from mpynode.native.ai import optimizer_live

        out   = tempfile.mkdtemp(prefix="mpynode-clean-")
        build = bundler.build_dir_for(out)
        for sub in (bundler.source_dir_for(out),
                    bundler.stage_dir_for(out, "probeA")):
            os.makedirs(sub, exist_ok=True)
        with open(os.path.join(bundler.source_dir_for(out), "probeA.cpp"),
                  "w") as fh:
            fh.write("// shipped")
        with open(os.path.join(bundler.stage_dir_for(out, "probeA"),
                               "1_transpiled.cpp"), "w") as fh:
            fh.write("// stage 1")
        for r in rows:
            tn = r["type_name"]
            for d in (os.path.join(build, tn),
                      os.path.join(build, optimizer_live.OPT_SCRATCH_DIRNAME,
                                   tn)):
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, "junk.o"), "w") as fh:
                    fh.write("lint")
        return out, build

    def test_a_built_nodes_optimizer_scratch_is_swept(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.toolchain import compile_controller as cc

        rows = [{"type_name": "probeA", "build_status": "compiled"}]
        out, build = self._tree(rows)

        cc._clean_working_subdirs(out, rows)

        self.assertFalse(os.path.isdir(os.path.join(build, "probeA")))
        self.assertFalse(os.path.isdir(
            os.path.join(build, optimizer_live.OPT_SCRATCH_DIRNAME, "probeA")))
        self.assertFalse(os.path.isdir(
            os.path.join(build, optimizer_live.OPT_SCRATCH_DIRNAME)),
            "an emptied scratch root should not be left behind")

    def test_the_source_and_the_story_always_survive(self):
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import compile_controller as cc

        rows = [{"type_name": "probeA", "build_status": "compiled"}]
        out, _build = self._tree(rows)

        cc._clean_working_subdirs(out, rows)

        self.assertTrue(os.path.exists(
            os.path.join(bundler.source_dir_for(out), "probeA.cpp")))
        self.assertTrue(os.path.exists(
            os.path.join(bundler.stage_dir_for(out, "probeA"),
                         "1_transpiled.cpp")))

    def test_a_dropped_nodes_evidence_is_spared(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.toolchain import compile_controller as cc

        rows = [{"type_name": "probeA", "build_status": "dropped"}]
        out, build = self._tree(rows)

        cc._clean_working_subdirs(out, rows)

        self.assertTrue(os.path.isdir(os.path.join(build, "probeA")))
        self.assertTrue(os.path.isdir(
            os.path.join(build, optimizer_live.OPT_SCRATCH_DIRNAME, "probeA")),
            "the scratch is where a failed optimize left its logs")

    def test_clean_scratch_false_keeps_everything(self):
        from mpynode.native.ai import optimizer_live
        from mpynode.native.toolchain import compile_controller as cc

        rows = [{"type_name": "probeA", "build_status": "compiled"}]
        out, build = self._tree(rows)

        cc._clean_working_subdirs(out, rows, clean_scratch=False)

        self.assertTrue(os.path.isdir(os.path.join(build, "probeA")))
        self.assertTrue(os.path.isdir(
            os.path.join(build, optimizer_live.OPT_SCRATCH_DIRNAME, "probeA")))

    def test_the_scratch_name_has_one_definition(self):
        """The dirname is written by the optimizer and read by the cleaner; two
        literals in two files drift, and the drift is silent (nothing cleaned)."""
        import inspect

        from mpynode.native.ai import optimizer_live
        from mpynode.native.toolchain import compile_controller as cc

        self.assertEqual(optimizer_live.OPT_SCRATCH_DIRNAME, "_optscratch")
        self.assertNotIn('"_optscratch"', inspect.getsource(cc))

    def test_the_flag_reaches_the_cleaner_from_compile_plugin(self):
        import inspect

        from mpynode.native.toolchain import compile_controller as cc

        sig = inspect.signature(cc.compile_plugin)
        self.assertIn("clean_scratch", sig.parameters)
        self.assertIs(sig.parameters["clean_scratch"].default, True)
        self.assertIn("_clean_working_subdirs(out_dir, rows, clean_scratch)",
                      inspect.getsource(cc.compile_plugin))


if __name__ == "__main__":
    unittest.main()
