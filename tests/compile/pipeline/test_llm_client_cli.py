"""What ``llm_client`` actually hands the local CLI: argv and child ENV.

Two separate contracts live here.

``--permission-mode`` (T57). The tool-using optimizer agent states it explicitly;
the porter's one-shot argv did not, so the two paths relied on different
defaults for the same binary. An A/B probe produced IDENTICAL correct C++ either
way, so this is unapplied hardening -- which is exactly why it needs a test: the
only way it can hurt is by drifting away from the optimizer's value or leaking
onto a non-Claude CLI.

The response CEILING (T79). ``make_cli_complete_fn`` takes ``max_tokens`` and,
for a CLI provider, dropped it: the caller's configured "Max response tokens"
never reached the child, so the one-shot optimizer rewrite was silently capped by
the CLI's own default. Measured on the 2026-08-13 arm-1 run: eight rounds over
four nodes all stopped between ~29k and ~38k estimated output tokens -- a stop
point that tracks the CEILING, not the 172KB-458KB inputs -- and every one was
rejected as truncated.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mpynode.native.ai import llm_client


class TestPermissionModeOnThePorterArgv(unittest.TestCase):
    def test_claude_cli_argv_states_a_permission_mode(self):
        cmd, _ = llm_client._build_cli("claude_cli", "claude", "opus", "max",
                                       "P")
        self.assertIn("--permission-mode", cmd)

    def test_it_is_the_same_mode_the_optimizer_agent_uses(self):
        """One value, said once. Two literals drift, and a porter running under
        a different permission mode than the agent is a difference nobody
        declared."""
        cmd, _ = llm_client._build_cli("claude_cli", "claude", "opus", "max",
                                       "P")
        porter_mode = cmd[cmd.index("--permission-mode") + 1]

        seen = {}

        def fake_run(cmd, stdin_text, binp, **kw):
            seen["cmd"] = list(cmd)
            return "ok"

        with mock.patch.object(llm_client, "_resolve_cli_bin",
                               lambda p: "claude"), \
                mock.patch.object(llm_client._config, "get_model",
                                  lambda p: "opus"), \
                mock.patch.object(llm_client._config, "get_effort",
                                  lambda p: "max"), \
                mock.patch.object(llm_client, "_run_cli_proc", fake_run):
            llm_client.make_cli_agent_fn("/tmp")("P")
        agent_cmd  = seen["cmd"]
        agent_mode = agent_cmd[agent_cmd.index("--permission-mode") + 1]
        self.assertEqual(porter_mode, agent_mode)

    def test_non_claude_clis_never_get_the_flag(self):
        # It is a Claude Code concept; gemini/codex would reject an unknown flag
        # and take the whole port down with it.
        for provider, binp in (("gemini_cli", "gemini"), ("codex_cli", "codex")):
            cmd, _ = llm_client._build_cli(provider, binp, "m", "max", "P")
            self.assertNotIn("--permission-mode", cmd, provider)

    def test_the_prompt_still_goes_on_stdin_unchanged(self):
        # The flag must be additive: same stdin, same deny list, same prompt.
        cmd, stdin = llm_client._build_cli("claude_cli", "claude", "opus",
                                           "max", "P")
        self.assertEqual(stdin, "P")
        self.assertEqual(cmd[cmd.index("--disallowedTools") + 1],
                         llm_client._CLI_DENY)


class TestTheResponseCeilingReachesTheCli(unittest.TestCase):
    """``max_tokens`` is the OPTIMIZER's ceiling for a whole-file rewrite. It
    reached the anthropic/gemini payloads and was dropped for CLI providers,
    where the CLI's own (lower, undocumented) default decided instead."""

    def _capture(self, provider, **fn_kw):
        seen = {}

        def fake_run(cmd, stdin_text, binp, **kw):
            seen["cmd"] = list(cmd)
            seen["kw"]  = dict(kw)
            return "X;"

        with mock.patch.object(llm_client._config, "get_provider",
                               lambda: provider), \
                mock.patch.object(llm_client._config, "get_model",
                                  lambda p: "m"), \
                mock.patch.object(llm_client._config, "get_effort",
                                  lambda p: "max"), \
                mock.patch.object(llm_client, "_resolve_cli_bin",
                                  lambda p: "bin"), \
                mock.patch.object(llm_client, "_run_cli_proc", fake_run):
            llm_client.make_cli_complete_fn(**fn_kw)("sys", "user")
        return seen

    def test_claude_cli_child_is_given_the_configured_ceiling(self):
        seen = self._capture("claude_cli", timeout=2400.0, max_tokens=64000)
        env  = seen["kw"].get("env")
        self.assertIsNotNone(
            env, "the CLI child got no env, so the ceiling was dropped")
        self.assertEqual(env.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS"), "64000")

    def test_the_rest_of_the_child_env_is_inherited_not_replaced(self):
        # Handing the CLI a 1-entry env would strip PATH/HOME and break it.
        import os

        seen = self._capture("claude_cli", max_tokens=64000)
        env  = seen["kw"]["env"]
        for k in os.environ:
            self.assertIn(k, env, "child env dropped %s" % k)

    def test_the_porter_call_shape_leaves_the_env_alone(self):
        """The porter binds ``make_cli_complete_fn(cancel_event=ev)`` -- no
        ceiling. It must keep inheriting os.environ untouched, or this hardening
        has changed a working port."""
        seen = self._capture("claude_cli", timeout=600.0)
        self.assertIsNone(seen["kw"].get("env"))

    def test_a_non_claude_cli_does_not_get_a_claude_env_var(self):
        seen = self._capture("gemini_cli", max_tokens=64000)
        self.assertIsNone(seen["kw"].get("env"))


class TestTheLoudRejectionSurvivesTheHigherCeiling(unittest.TestCase):
    """Raising the ceiling must not be mistaken for trusting the answer.

    Not a new behaviour -- a pin. A bigger budget makes a truncated reply LESS
    likely and never impossible (dualQuaternionSkin needs ~131k output tokens
    and no ceiling reaches that), so the validator has to keep rejecting the
    exact shape the 2026-08-13 run produced: a faithful prefix of the baseline
    that stops partway and continues in markdown.
    """

    def _arm1_shaped_candidate(self):
        # The measured shape: 99% of the candidate's lines appear verbatim in
        # the baseline, it stops at ~40% of the file, it never reaches
        # initializePlugin, and it tails off mid-sentence in prose.
        base = ("#include <maya/MPxNode.h>\n"
                + "".join("void f%d() { int x = %d; }\n" % (i, i)
                          for i in range(100))
                + "MStatus initializePlugin(MObject o) { return MS::kSuccess; }\n"
                  "MStatus uninitializePlugin(MObject o) { return MS::kSuccess; }\n")
        cand = ("#include <maya/MPxNode.h>\n"
                + "".join("void f%d() { int x = %d; }\n" % (i, i)
                          for i in range(40))
                + "void f40() { int x = 40;\n"
                  "## What changes and why\n"
                  "Find (in the deform loop, the line right after the two input-mar")
        return cand, base

    def test_a_truncated_prefix_answer_is_still_rejected(self):
        from mpynode.native.ai import optimizer_knowledge

        cand, base = self._arm1_shaped_candidate()
        why = optimizer_knowledge.implausible_reason(cand, base)
        self.assertTrue(why, "a truncated whole-file rewrite was accepted")

    def test_an_empty_answer_is_still_rejected(self):
        from mpynode.native.ai import optimizer_knowledge

        _c, base = self._arm1_shaped_candidate()
        self.assertTrue(optimizer_knowledge.implausible_reason("   \n", base))

    def test_a_complete_answer_is_still_accepted(self):
        # The other half of the pin: the validator must not have been tightened
        # into refusing a genuine whole-file reply either.
        from mpynode.native.ai import optimizer_knowledge

        _c, base = self._arm1_shaped_candidate()
        good = base.replace("int x = 3;", "int x = 3; /* faster */")
        self.assertIsNone(optimizer_knowledge.implausible_reason(good, base))


class TestRunCliProcForwardsTheEnv(unittest.TestCase):
    """An ``env`` the runner accepts and never passes on is worse than no env at
    all: the caller sees the ceiling applied and the child never saw it."""

    def test_blocking_path_passes_env_to_the_subprocess(self):
        seen = {}

        class _P:
            stdout, stderr, returncode = "out", "", 0

        def fake_run(cmd, **kw):
            seen.update(kw)
            return _P()

        with mock.patch.object(llm_client.subprocess, "run", fake_run):
            llm_client._run_cli_proc(["x"], None, "bin",
                                     env={"CLAUDE_CODE_MAX_OUTPUT_TOKENS": "7"})
        self.assertEqual(seen["env"]["CLAUDE_CODE_MAX_OUTPUT_TOKENS"], "7")

    def test_env_none_is_still_passed_as_none_so_the_child_inherits(self):
        seen = {}

        class _P:
            stdout, stderr, returncode = "out", "", 0

        def fake_run(cmd, **kw):
            seen.update(kw)
            return _P()

        with mock.patch.object(llm_client.subprocess, "run", fake_run):
            llm_client._run_cli_proc(["x"], None, "bin")
        self.assertIsNone(seen.get("env"))


class TestGeminiPorterArgvFitsAndIsTrusted(unittest.TestCase):
    """The compile porter spawns the Gemini CLI itself, and hit both walls the
    interactive assistant did.

    The prompt used to ride in argv, so a real port -- system prompt + the
    node's compute + the cheat sheet -- was tens of KB and Windows refused the
    spawn before the CLI started: ``[WinError 206] The filename or extension is
    too long``. And the CLI will not run in a folder that was never trusted
    interactively (exit 55), which Maya's working directory never is.
    """

    _BIG = "x" * 60000

    def test_the_prompt_is_not_in_argv(self):
        cmd, stdin = llm_client._build_cli("gemini_cli", "gemini", "auto",
                                           "off", self._BIG)
        self.assertNotIn(self._BIG, cmd)
        self.assertTrue(stdin.startswith("x"))
        self.assertEqual(len(stdin), len(self._BIG) + 1)

    def test_argv_stays_far_below_the_windows_limit(self):
        cmd, _ = llm_client._build_cli("gemini_cli", "gemini", "auto", "off",
                                       self._BIG)
        self.assertLess(sum(len(a) + 1 for a in cmd), 1024)

    def test_the_workspace_is_trusted_but_not_auto_approving(self):
        # --skip-trust is what lets it start; -y is deliberately absent, because
        # the porter wants C++ text back and nothing else (the Claude branch
        # denies every editing tool for the same reason).
        cmd, _ = llm_client._build_cli("gemini_cli", "gemini", "auto", "off", "P")
        self.assertIn("--skip-trust", cmd)
        self.assertNotIn("-y", cmd)

    def test_only_gemini_gets_a_scratch_working_directory(self):
        # What --skip-trust trusts should be a temp dir, not the user's project.
        import os

        got = llm_client._cli_cwd("gemini_cli")
        self.assertTrue(os.path.isdir(got))
        self.assertNotEqual(os.path.normcase(got), os.path.normcase(os.getcwd()))
        self.assertEqual(llm_client._cli_cwd("gemini_cli"), got)  # reused
        self.assertIsNone(llm_client._cli_cwd("claude_cli"))
        self.assertIsNone(llm_client._cli_cwd("codex_cli"))

    def test_the_claude_path_is_untouched(self):
        # Same argv, same stdin, same deny list as before this fix.
        cmd, stdin = llm_client._build_cli("claude_cli", "claude", "opus",
                                           "max", self._BIG, stream_json=True)
        self.assertEqual(stdin, self._BIG)
        self.assertNotIn("--skip-trust", cmd)
        self.assertLess(sum(len(a) + 1 for a in cmd), 2048)


if __name__ == "__main__":
    unittest.main()
