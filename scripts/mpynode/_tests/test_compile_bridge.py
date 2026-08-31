"""ui/llm/compile_bridge.py -- the pure, Qt-free, Maya-free packaging that turns a
CompileController result into a conversational hand-off for the AI assistant
(WS2 Phase 1 concierge). Pure data-in/data-out, so these tests need no Maya/Qt.
"""

from __future__ import annotations

import unittest


def _row(source_node, type_name, build_status, *, verify=None,
         build_reason="", blockers=None):
    spec = {"portability": {"blockers": list(blockers or [])}}
    return {
        "source_node": source_node,
        "type_name": type_name,
        "build_status": build_status,
        "build_reason": build_reason,
        "verify": verify or {"ran": False, "pass": None, "maxerr": None,
                             "tol": None, "reason": ""},
        "spec": spec,
    }


def _result(nodes, *, ok=True, errors=None, plugin_name="myPlugin"):
    return {
        "ok": ok,
        "bundle_path": "/tmp/out/myPlugin.bundle",
        "plugin_name": plugin_name,
        "nodes": nodes,
        "errors": list(errors or []),
        "strict": True,
    }


class TestBuildHandoff(unittest.TestCase):
    def test_failure_kind_picks_dropped_and_diverged_not_passing(self):
        from mpynode.ui.llm import compile_bridge

        rows = [
            _row("passNode1", "passNode", "compiled",
                 verify={"ran": True, "pass": True, "maxerr": 6e-8,
                         "tol": 1e-4, "reason": ""}),
            _row("dropNode1", "dropNode", "dropped",
                 build_reason="port: 'std::map' requires <map>",
                 blockers=["dict keyed by tuple in compute"]),
            _row("divNode1", "divNode", "compiled",
                 verify={"ran": True, "pass": False, "maxerr": 2.1e-3,
                         "tol": 1e-4, "reason": "outMesh mismatch"}),
        ]
        h = compile_bridge.build_handoff(_result(rows), {"out_dir": "/tmp/out"})
        self.assertEqual(h["kind"], "failure")
        picked = {r["type_name"] for r in h["rows"]}
        self.assertEqual(picked, {"dropNode", "divNode"})
        self.assertNotIn("passNode", picked)
        # primary = first picked row that has a source_node
        self.assertEqual(h["primary_source_node"], "dropNode1")
        self.assertEqual(h["plugin_name"], "myPlugin")
        self.assertEqual(h["out_dir"], "/tmp/out")

    def test_optimize_kind_picks_built_nodes(self):
        from mpynode.ui.llm import compile_bridge

        rows = [
            _row("a1", "a", "compiled",
                 verify={"ran": True, "pass": True, "maxerr": 0.0,
                         "tol": 1e-4, "reason": ""}),
            _row("b1", "b", "transformed"),
            _row("c1", "c", "dropped"),
        ]
        h = compile_bridge.build_handoff(_result(rows), {}, kind="optimize")
        self.assertEqual(h["kind"], "optimize")
        picked = {r["type_name"] for r in h["rows"]}
        self.assertEqual(picked, {"a", "b"})  # dropped is not "built"

    def test_diverged_row_carries_verify_and_blockers(self):
        from mpynode.ui.llm import compile_bridge

        rows = [_row("divNode1", "divNode", "compiled",
                     verify={"ran": True, "pass": False, "maxerr": 2.1e-3,
                             "tol": 1e-4, "reason": "outMesh mismatch"},
                     blockers=["uses a python dict"])]
        h = compile_bridge.build_handoff(_result(rows), {})
        r = h["rows"][0]
        self.assertEqual(r["verify"]["maxerr"], 2.1e-3)
        self.assertFalse(r["verify"]["pass"])
        self.assertIn("uses a python dict", r["blockers"])

    def test_empty_result_is_safe(self):
        from mpynode.ui.llm import compile_bridge

        h = compile_bridge.build_handoff({}, None)
        self.assertEqual(h["rows"], [])
        self.assertIsNone(h["primary_source_node"])

    def test_log_tail_passes_through(self):
        from mpynode.ui.llm import compile_bridge

        h = compile_bridge.build_handoff(_result([]), {}, log_tail=["a", "b"])
        self.assertEqual(h["log_tail"], ["a", "b"])


class TestFormatReportBlock(unittest.TestCase):
    def test_report_has_fences_nodes_verify_and_guidance(self):
        from mpynode.ui.llm import compile_bridge

        rows = [
            _row("dropNode1", "dropNode", "dropped",
                 build_reason="port: 'std::map' requires <map>",
                 blockers=["dict keyed by tuple in compute"]),
            _row("divNode1", "divNode", "compiled",
                 verify={"ran": True, "pass": False, "maxerr": 2.1e-3,
                         "tol": 1e-4, "reason": "outMesh mismatch"}),
        ]
        h = compile_bridge.build_handoff(_result(rows), {})
        text = compile_bridge.format_report_block(h)
        self.assertIn("[Compile report]", text)
        self.assertIn("[/Compile report]", text)
        self.assertIn("dropNode", text)
        self.assertIn("divNode", text)
        self.assertIn("2.1e-03", text.replace("2.1e-3", "2.1e-03"))  # maxerr shown
        self.assertIn("dict keyed by tuple in compute", text)   # blocker shown
        # reframe guidance: enable, don't hard-block; C++ ok; green-light/editable
        low = text.lower()
        self.assertTrue("green-light" in low or "green light" in low
                        or "hand-edit" in low or "editable" in low)

    def test_optimize_report_mentions_performance(self):
        from mpynode.ui.llm import compile_bridge

        rows = [_row("a1", "a", "compiled",
                     verify={"ran": True, "pass": True, "maxerr": 0.0,
                             "tol": 1e-4, "reason": ""})]
        h = compile_bridge.build_handoff(_result(rows), {}, kind="optimize")
        text = compile_bridge.format_report_block(h)
        self.assertIn("[Compile report]", text)
        self.assertIn("a", text)


class TestClassify(unittest.TestCase):
    def test_buckets_built_dropped_diverged_verified(self):
        from mpynode.ui.llm import compile_bridge

        rows = [
            _row("ok1", "ok", "compiled",
                 verify={"ran": True, "pass": True, "maxerr": 6e-8,
                         "tol": 1e-4, "reason": ""}),
            _row("div1", "div", "compiled",
                 verify={"ran": True, "pass": False, "maxerr": 2e-3,
                         "tol": 1e-4, "reason": "x"}),
            _row("drop1", "drop", "dropped"),
            _row("nv1", "nv", "compiled"),  # built, verify did not run
        ]
        c = compile_bridge.classify(_result(rows))
        self.assertEqual(c["n_total"], 4)
        self.assertEqual({r["type_name"] for r in c["built"]},
                         {"ok", "div", "nv"})
        self.assertEqual({r["type_name"] for r in c["dropped"]}, {"drop"})
        self.assertEqual({r["type_name"] for r in c["diverged"]}, {"div"})
        self.assertEqual({r["type_name"] for r in c["verified_ok"]}, {"ok"})
        self.assertTrue(c["needs_ai"])

    def test_all_clean_needs_no_ai(self):
        from mpynode.ui.llm import compile_bridge

        rows = [_row("ok1", "ok", "compiled",
                     verify={"ran": True, "pass": True, "maxerr": 0.0,
                             "tol": 1e-4, "reason": ""})]
        self.assertFalse(compile_bridge.needs_ai(_result(rows)))

    def test_empty_is_safe(self):
        from mpynode.ui.llm import compile_bridge

        c = compile_bridge.classify({})
        self.assertEqual(c["n_total"], 0)
        self.assertFalse(c["needs_ai"])


class TestVerifySummaryLines(unittest.TestCase):
    def test_one_line_per_node_with_verify(self):
        from mpynode.ui.llm import compile_bridge

        rows = [
            _row("ok1", "ok", "compiled",
                 verify={"ran": True, "pass": True, "maxerr": 6e-8,
                         "tol": 1e-4, "reason": ""}),
            _row("div1", "div", "compiled",
                 verify={"ran": True, "pass": False, "maxerr": 2e-3,
                         "tol": 1e-4, "reason": "outMesh mismatch"}),
            _row("nv1", "nv", "compiled",
                 verify={"ran": False, "pass": None, "maxerr": None,
                         "tol": None, "reason": "string input"}),
        ]
        lines = compile_bridge.verify_summary_lines(_result(rows))
        self.assertEqual(len(lines), 3)
        self.assertIn("PASS", lines[0])
        self.assertIn("FAIL", lines[1])
        self.assertIn("outMesh mismatch", lines[1])
        self.assertIn("did not run", lines[2])
        self.assertIn("string input", lines[2])


class TestTimingNote(unittest.TestCase):
    """A slow-but-correct port is a PASSING row, and both existing channels drop
    detail on passing rows (`_verify_line` throws `reason` away once ok is True).
    So the timing note has to survive as its OWN line."""

    def test_passing_row_still_shows_its_timing_warning(self):
        from mpynode.ui.llm import compile_bridge

        warn = ("TIMING: compiled is 22.7x SLOWER than the interpreted Python "
                "(124.7 ms vs 5.5 ms)")
        rows = [_row("slow1", "slow", "compiled",
                     verify={"ran": True, "pass": True, "maxerr": 1e-9,
                             "tol": 1e-4, "reason": "",
                             "timing": {"measured": True, "py_ms": 5.5,
                                        "cpp_ms": 124.7, "n": 3,
                                        "truncated": False,
                                        "verdict": "much-slower",
                                        "warning": warn,
                                        "scene": "geo 140/array 5000"}})]
        lines = compile_bridge.verify_summary_lines(_result(rows))
        self.assertEqual(len(lines), 2, lines)
        self.assertIn("PASS", lines[0])          # still a pass -- unchanged
        self.assertEqual("    ! %s" % warn, lines[1])
        self.assertTrue(lines[1].startswith("    ! TIMING:"), lines[1])

    def test_ok_verdict_adds_no_line(self):
        from mpynode.ui.llm import compile_bridge

        rows = [_row("fast1", "fast", "compiled",
                     verify={"ran": True, "pass": True, "maxerr": 1e-9,
                             "tol": 1e-4, "reason": "",
                             "timing": {"measured": True, "py_ms": 5.5,
                                        "cpp_ms": 0.9, "n": 3,
                                        "truncated": False, "verdict": "ok",
                                        "scene": "geo 140/array 5000"}})]
        lines = compile_bridge.verify_summary_lines(_result(rows))
        self.assertEqual(len(lines), 1, lines)
        self.assertNotIn("!", lines[0])

    def test_a_row_with_no_timing_at_all_is_safe(self):
        from mpynode.ui.llm import compile_bridge

        rows = [_row("old1", "old", "compiled",
                     verify={"ran": True, "pass": True, "maxerr": 0.0,
                             "tol": 1e-4, "reason": ""})]
        self.assertEqual(len(compile_bridge.verify_summary_lines(
            _result(rows))), 1)

    def test_timing_survives_into_the_assistant_handoff(self):
        from mpynode.ui.llm import compile_bridge

        timing = {"measured": True, "py_ms": 5.5, "cpp_ms": 124.7, "n": 3,
                  "truncated": False, "verdict": "much-slower",
                  "warning": "TIMING: 22.7x slower",
                  "scene": "geo 140/array 5000"}
        rows = [_row("slow1", "slow", "compiled",
                     verify={"ran": True, "pass": True, "maxerr": 1e-9,
                             "tol": 1e-4, "reason": "", "timing": timing})]
        # A passing row only reaches the hand-off via the optimize flow, which
        # is precisely the flow that needs the measurement.
        h = compile_bridge.build_handoff(_result(rows), {}, kind="optimize")
        self.assertEqual(h["rows"][0]["verify"]["timing"], timing)

    def test_missing_timing_summarises_to_an_empty_dict(self):
        from mpynode.ui.llm import compile_bridge

        h = compile_bridge.build_handoff(
            _result([_row("n1", "n", "compiled")]), {}, kind="optimize")
        self.assertEqual(h["rows"][0]["verify"]["timing"], {})


class TestOslHandoff(unittest.TestCase):
    def test_build_osl_handoff_carries_reason_node_suggestions(self):
        from mpynode.ui.llm import compile_bridge

        h = compile_bridge.build_osl_handoff(
            "OSL has no runtime array-of-textures input",
            node_name="compositeTex",
            suggestions=["hard-code N single string inputs (inputPath0..N)",
                         "generate N inputs from the current path count"])
        self.assertEqual(h["kind"], "osl")
        self.assertEqual(h["primary_source_node"], "compositeTex")
        self.assertIn("runtime array", h["reason"])
        self.assertEqual(len(h["suggestions"]), 2)

    def test_osl_handoff_has_default_suggestion(self):
        from mpynode.ui.llm import compile_bridge

        h = compile_bridge.build_osl_handoff("some reason")
        self.assertTrue(h["suggestions"], "should provide a default hint")

    def test_osl_report_and_prompt_mention_osl_and_reason(self):
        from mpynode.ui.llm import compile_bridge

        h = compile_bridge.build_osl_handoff(
            "string-array input unsupported", node_name="compositeTex",
            suggestions=["hard-code inputPath0..N"])
        report = compile_bridge.format_report_block(h)
        self.assertIn("[Compile report]", report)
        self.assertIn("string-array input unsupported", report)
        self.assertIn("hard-code inputPath0..N", report)
        low = report.lower()
        self.assertIn("osl", low)
        prompt = compile_bridge.starter_prompt(h)
        self.assertTrue(prompt.strip())
        self.assertIn("compositeTex", prompt)


class TestStarterPrompt(unittest.TestCase):
    def test_failure_and_optimize_differ_and_nonempty(self):
        from mpynode.ui.llm import compile_bridge

        fail = compile_bridge.build_handoff(
            _result([_row("n1", "n", "dropped")]), {})
        opt = compile_bridge.build_handoff(
            _result([_row("n1", "n", "compiled")]), {}, kind="optimize")
        fp = compile_bridge.starter_prompt(fail)
        op = compile_bridge.starter_prompt(opt)
        self.assertTrue(fp.strip())
        self.assertTrue(op.strip())
        self.assertNotEqual(fp, op)


if __name__ == "__main__":
    unittest.main()
