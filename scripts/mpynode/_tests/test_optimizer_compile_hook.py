"""The opt-in compile-step hook: compile_plugin grows an ``optimize`` param that
defaults False, so every existing caller's build is byte-for-byte unchanged (the
rest of the suite proves that by staying green). When on, the (c.6) seam runs the
gated optimizer per surviving node; when off, that seam is never entered.
"""

from __future__ import annotations

import inspect
import os
import tempfile
import unittest
import unittest.mock

from mpynode.native.toolchain import compile_controller


class TestOptimizeSkipReason(unittest.TestCase):
    """The isolated per-node optimizer must REFUSE nodes where a compute-parity-
    only gate cannot protect a transform it does not exercise:
      * any node whose .cpp carries a shared followed-import helper block, which
        assemble dedups across nodes (first-wins) -- optimizing one copy in
        isolation could ship an unvalidated / mismatched helper body or break the
        link. A plain node with no such structure is optimizable.

    mPyFile is NO LONGER blanket-refused. (c.5) splices the VP2 override BEFORE
    the optimizer runs, so the candidate the model edits already contains it, and
    ``optimizer_knowledge._PLUGIN_ANCHORS`` fails any candidate that dropped the
    override tokens -- a targeted guard in place of a whole-family refusal.
    """

    def _cpp(self, tmp, text):
        p = os.path.join(tmp, "n.cpp")
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def test_mpyfile_is_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, "int x=1;")
            r = compile_controller._optimize_skip_reason(cpp, {"mpy_type": "mPyFile"})
            self.assertFalse(
                r, "mPyFile is optimizable: the override is spliced before the "
                   "optimizer and guarded by _PLUGIN_ANCHORS (got %r)" % r)

    def test_the_vp2_override_tokens_are_anchored(self):
        """The refusal was replaced by an anchor, not by nothing."""
        from mpynode.native.ai import optimizer_knowledge
        for tok in ("MPxShadingNodeOverride", "nd_texel",
                    "registerShadingNodeOverrideCreator"):
            self.assertIn(tok, optimizer_knowledge._PLUGIN_ANCHORS)

    def test_shared_helper_marker_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(
                tmp, "// === MPYNODE SHARED HELPER BEGIN name=nd_foo proto=... ===\n"
                     "double nd_foo(double){return 0;}\n"
                     "// === MPYNODE SHARED HELPER END name=nd_foo ===\n")
            r = compile_controller._optimize_skip_reason(cpp, {"mpy_type": "mPyMesh"})
            self.assertTrue(r)
            self.assertIn("shared", r.lower())

    def test_plain_mesh_node_is_optimizable(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, "int compute(){return 42;}")
            r = compile_controller._optimize_skip_reason(cpp, {"mpy_type": "mPyMesh"})
            self.assertEqual(r, "")

    def test_oversized_tu_skipped_on_the_one_shot_path(self):
        """Without a tool-using agent the optimizer must return the WHOLE unit
        in one reply. Spending that call when it provably cannot fit produces a
        truncation the gate rejects, i.e. a wasted round that reads to the user
        exactly like "your code is already fast"."""
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, "double x=1.0;\n" * 24000)   # ~300 KB
            r = compile_controller._optimize_skip_reason(
                cpp, {"mpy_type": "mPyMesh"}, one_shot=True)
            self.assertTrue(r)
            self.assertIn("response tokens", r)
            self.assertIn("64000", r)

    def test_oversized_tu_not_skipped_on_the_agent_path(self):
        """The agent EDITS the file in place, so no reply has to hold it --
        the ceiling that motivates this gate does not exist there."""
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, "double x=1.0;\n" * 24000)
            r = compile_controller._optimize_skip_reason(
                cpp, {"mpy_type": "mPyMesh"}, one_shot=False)
            self.assertEqual(r, "")

    def test_response_tokens_needed_is_shared_by_gate_and_readout(self):
        """The skip gate and the per-node readout must quote the SAME number --
        a readout that disagrees with the gate is worse than none."""
        text = "double x=1.0;\n" * 24000
        n = compile_controller._response_tokens_needed(text)
        self.assertEqual(n, int(len(text) / 3.5 * 1.25))
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, text)
            r = compile_controller._optimize_skip_reason(
                cpp, {"mpy_type": "mPyMesh"}, one_shot=True)
        self.assertIn(str(n), r)

    def test_small_tu_not_skipped_on_api_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, "int compute(){return 42;}")
            r = compile_controller._optimize_skip_reason(
                cpp, {"mpy_type": "mPyMesh"}, one_shot=True)
            self.assertEqual(r, "")

    def test_the_gate_is_the_path_not_the_provider_kind(self):
        """A ``claude_cli`` provider DEMOTED to the one-shot path (no sandbox,
        binary gone) cannot edit the file in place either, so the ceiling binds
        it exactly as it binds an API provider. Gating on the provider KIND let
        sineRipple (~99k tokens) and dualQuaternionSkin (~131k) burn ~11 min per
        round before an honest reject."""
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, "double x=1.0;\n" * 24000)
            r = compile_controller._optimize_skip_reason(
                cpp, {"mpy_type": "mPyMesh"}, one_shot=True)
            self.assertTrue(r)
            self.assertIn("response tokens", r)

    def test_the_skip_says_the_file_is_too_large_to_rewrite_whole(self):
        """"...or use a CLI provider" is backwards advice for a CLI provider
        that WAS demoted. Say what is actually true of the file."""
        with tempfile.TemporaryDirectory() as tmp:
            cpp = self._cpp(tmp, "double x=1.0;\n" * 24000)
            r = compile_controller._optimize_skip_reason(
                cpp, {"mpy_type": "mPyMesh"}, one_shot=True)
            self.assertIn("whole-file rewrite", r)
            self.assertNotIn("use a CLI provider", r)


# Repo root: .../scripts/mpynode/_tests/<this file>
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# The two nodes that MOTIVATED the up-front gate, with the character count of
# the finalized .cpp each one actually produces. At 3.5 chars/token x 1.25 that
# is ~129k and ~164k response tokens against a 64000 cap -- a whole-file rewrite
# of either is impossible, not merely capped, and all 8 arm-1 rounds spent ~11
# min apiece proving it. The size is recorded here so the pin holds even in a
# tree with no built artifacts; the artifact leg below uses the real bytes.
_REAL_OVERSIZED = (
    ("sineRipple", "mPyDeformer", 361375,
     "compiled_templates/MPyDeformer/Sine Ripple/build/source/"
     "sineRipple.cpp"),
    ("dualQuaternionSkin", "mPySkinCluster", 458420,
     "compiled_templates/MPySkinCluster/Dual Quaternion Skin/build/"
     "source/dualQuaternionSkin.cpp"),
)


class TestTheTwoTemplatesThatMotivatedTheGate(unittest.TestCase):
    """``T79``/``T83`` confirm. These two MOTIVATED the gate; prove it refuses
    BOTH, up front, with a diagnostic reason -- not after a round.

    It does NOT apply to only two. MEASURED over every built TU in this tree:
    **27 of 46 exceed the 64000 cap**, because ``nd_runtime.h`` is textually
    inlined and costs 60268 response tokens on its own, leaving ~3700 of
    headroom. The nodes that fit are the trivial ones. So on the ONE-SHOT path
    the whole-file optimizer is refused for most of the tree -- correctly (they
    genuinely cannot be rewritten in one reply), but the scope is the tree, not
    a pair."""

    def test_a_tu_of_each_recorded_size_is_refused_up_front(self):
        cap = compile_controller._resolve_optimize_max_tokens()
        for name, mpy_type, size, _rel in _REAL_OVERSIZED:
            with self.subTest(node=name):
                with tempfile.TemporaryDirectory() as tmp:
                    p = os.path.join(tmp, name + ".cpp")
                    with open(p, "w") as fh:
                        fh.write("x" * size)
                    need = compile_controller._response_tokens_needed("x" * size)
                    self.assertGreater(need, cap)
                    r = compile_controller._optimize_skip_reason(
                        p, {"mpy_type": mpy_type}, one_shot=True)
                    self.assertIn("whole-file rewrite", r)
                    self.assertIn(str(need), r)
                    self.assertIn(str(cap), r)

    def test_the_shipped_cpp_of_both_is_refused_up_front(self):
        """The same claim against the REAL artifacts, so a codegen change that
        shrinks (or grows) them cannot quietly invalidate the numbers above."""
        present = [(n, t, os.path.join(_ROOT, rel))
                   for (n, t, _s, rel) in _REAL_OVERSIZED
                   if os.path.exists(os.path.join(_ROOT, rel))]
        if not present:
            self.skipTest("no built compiled_templates artifacts in this tree")
        cap = compile_controller._resolve_optimize_max_tokens()
        for name, mpy_type, path in present:
            with self.subTest(node=name):
                with open(path, "r") as fh:
                    text = fh.read()
                # Not the shared-helper branch: it returns FIRST, so a hit there
                # would mask whether the budget branch works at all.
                self.assertNotIn(compile_controller._SHARED_HELPER_MARKER, text)
                self.assertGreater(
                    compile_controller._response_tokens_needed(text), cap)
                r = compile_controller._optimize_skip_reason(
                    path, {"mpy_type": mpy_type}, one_shot=True)
                self.assertIn("whole-file rewrite", r)


class TestOversizedNodeNeverReachesTheOptimizer(unittest.TestCase):
    """The gate is only worth anything if the node never enters
    ``optimize_surviving`` -- that call is the ~11-minute round. Drive the real
    (c.6) seam with a DEMOTED ``claude_cli`` (the `T83` scenario: the CLI is
    reachable, so ``check_provider`` says ok, but the agent pre-flight fails)
    and a .cpp the size sineRipple really is."""

    def _spec(self, name="sineRipple"):
        return {
            "source_node": name,
            "mpy_type": "mPyDeformer",
            "suggested": {"node_type_name": name, "class_name": "SineRipple",
                          "mpx_base": "MPxNode", "type_id": "0x0013a1c1"},
            "inputs": {"a": {"type": "double"}},
            "outputs": {"out": {"type": "double"}},
            "compute": "out = a * 2.0",
            "init": "",
            "portability": {"portable": True, "blockers": []},
        }

    def test_the_oversized_node_is_never_handed_to_optimize_surviving(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.toolchain.typeid_registry import TypeIdRegistry
        from mpynode.native.ai import llm_client, optimizer_live, porter
        from mpynode.native.compiler import bundler

        size = _REAL_OVERSIZED[0][2]

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_check_provider(provider=None, model=None):
            return {"ok": True, "problems": [], "provider": "claude_cli",
                    "kind": "cli"}

        def fake_check_agent(provider=None):
            return {"ok": False, "kind": "cli", "provider": provider,
                    "problems": ["sandboxes do not nest"]}

        def fake_port_node(spec, out_dir, **k):
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("x" * size)
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        handed = []

        def spy_optimize_surviving(nodes, *a, **k):
            handed.append(list(nodes))
            return {}

        events = []

        with tempfile.TemporaryDirectory() as d:
            bundle = os.path.join(d, "myPlugin.bundle")
            with open(bundle, "w") as fh:
                fh.write("")
            ok_report = {"ok": True, "bundle": bundle, "shared_helpers": [],
                         "dropped": [],
                         "nodes": [{"name": "sineRipple", "status": "compiled",
                                    "reason": "", "id": 7}]}
            reg = TypeIdRegistry(path=os.path.join(d, "reg.json"))
            with unittest.mock.patch.object(toolchain, "check_toolchain",
                                            fake_check_toolchain), \
                 unittest.mock.patch.object(porter, "check_provider",
                                            fake_check_provider), \
                 unittest.mock.patch.object(porter, "port_node",
                                            fake_port_node), \
                 unittest.mock.patch.object(llm_client, "check_agent",
                                            fake_check_agent), \
                 unittest.mock.patch.object(optimizer_live, "optimize_surviving",
                                            spy_optimize_surviving), \
                 unittest.mock.patch.object(optimizer_live, "rollback_preopt",
                                            return_value=[]), \
                 unittest.mock.patch.object(optimizer_live, "discard_preopt",
                                            return_value=[]), \
                 unittest.mock.patch.object(bundler, "assemble",
                                            return_value=ok_report):
                result = cc.compile_plugin(
                    [self._spec()], "myPlugin", d, strict=True, verify=False,
                    reuse_cache=False, optimize=True,
                    complete_fn=lambda s, u: "out = a*2.0;",
                    provider="claude_cli", model="m", registry=reg,
                    progress_cb=events.append)

        self.assertEqual(handed, [[]],
                         "the oversized node was handed to the optimizer -- "
                         "that is the ~11-minute round the gate exists to skip")
        summary = (result.get("optimize") or {}).get("sineRipple") or {}
        self.assertFalse(summary.get("accepted"))
        self.assertIn("whole-file rewrite", summary.get("reason", ""))
        # ...and the user is TOLD, up front, on the optimize stage.
        skips = [e for e in events
                 if e.get("stage") == "optimize" and e.get("status") == "skip"]
        self.assertTrue(skips, events[-5:])
        self.assertIn("whole-file rewrite", skips[0].get("detail", ""))
        # A run whose only node was skipped must NOT read as "the AI died".
        self.assertNotIn("__status__", result.get("optimize") or {})


class TestWhichOptimizerPathTheRunWillTake(unittest.TestCase):
    """The controller has to answer "will this run have to retype the file?"
    BEFORE it hands the node over. ``prov["kind"]`` cannot answer it: the
    demotion to one-shot happens later, inside ``optimizer_live._make_agent``,
    on the ``llm_client.check_agent`` pre-flight. So ask the same pre-flight.
    """

    def _agent(self, ok, problems=()):
        from mpynode.native.ai import llm_client

        return unittest.mock.patch.object(
            llm_client, "check_agent",
            lambda provider=None: {"ok": ok, "problems": list(problems),
                                   "provider": provider, "kind": "cli"})

    def test_an_api_provider_never_has_an_agent(self):
        with self._agent(True):
            self.assertTrue(
                compile_controller._optimizer_is_one_shot("anthropic", "api"))

    def test_a_cli_provider_with_a_working_agent_is_not_one_shot(self):
        with self._agent(True):
            self.assertFalse(
                compile_controller._optimizer_is_one_shot("claude_cli", "cli"))

    def test_a_demoted_cli_provider_is_one_shot(self):
        with self._agent(False, ["sandboxes do not nest"]):
            self.assertTrue(
                compile_controller._optimizer_is_one_shot("claude_cli", "cli"))

    def test_an_unaskable_preflight_reads_as_one_shot(self):
        """This module must stay importable headless, and the conservative
        answer to "can it edit in place?" is no."""
        from mpynode.native.ai import llm_client

        def _boom(provider=None):
            raise RuntimeError("no llm_client here")

        with unittest.mock.patch.object(llm_client, "check_agent", _boom):
            self.assertTrue(
                compile_controller._optimizer_is_one_shot("claude_cli", "cli"))


class TestCompileHookOptIn(unittest.TestCase):
    def test_compile_plugin_has_optimize_param_default_false(self):
        sig = inspect.signature(compile_controller.compile_plugin)
        self.assertIn("optimize", sig.parameters)
        self.assertIs(sig.parameters["optimize"].default, False)

    def test_hook_guarded_by_optimize_flag(self):
        # The (c.6) call into the optimizer must be reachable ONLY under the flag,
        # so a default build cannot spawn it. Assert the source guards the call.
        src = inspect.getsource(compile_controller.compile_plugin)
        self.assertIn("optimize_surviving", src)          # the hook is wired
        self.assertIn("if optimize", src)                 # ...behind the flag
        self.assertIn("_optimize_skip_reason", src)       # ...and filters unsafe nodes

    def test_optimizer_verify_does_not_disable_authored_tests(self):
        # A node whose pointwise parity SKIPS (a deformer declares no outputs)
        # has NO gate left, so the optimizer rejects every candidate.
        # verify._merge_authored_test turns that skip into a real pass/fail via
        # the node's @maya_test, but only when the verify_fn was built with
        # authored tests ON -- so the optimizer must not override it to False.
        src = inspect.getsource(compile_controller.compile_plugin)
        blk = src[src.index("(c.6)"):]
        blk = blk[:blk.index("(d) assemble")]
        self.assertIn("subprocess_verify_fn", blk)
        self.assertNotIn("run_authored_tests=False", blk)

    def test_optimizer_narration_uses_dedicated_stage_not_port_ok(self):
        # The optimizer narration must NOT ride the ("port","ok") event -- the
        # formatter collapses every one of those to a fixed "AI port compiled
        # OK." line (the reported flood). The block emits "optimize" instead.
        src = inspect.getsource(compile_controller.compile_plugin)
        blk = src[src.index("(c.6)"):]
        blk = blk[:blk.index("(d) assemble")]
        self.assertIn('"optimize"', blk)                  # dedicated stage
        # The old per-message port/ok flood pattern is gone from the block.
        self.assertNotIn('"AI-optimize: %s" % m', blk)


if __name__ == "__main__":
    unittest.main()
