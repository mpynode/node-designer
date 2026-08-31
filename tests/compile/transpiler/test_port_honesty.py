"""Honesty moved from the compile GATE to the compiled OUTPUT.

Nothing that is valid Python is refused any more. What replaces the refusal is a
chain that has to hold end to end, and each link is pinned here:

  1. ``assess_portability`` reports a construct with no deterministic lowering
     as ``unported`` instead of a blocker (test_native_spec_extractor covers the
     detection itself; here we check it REACHES the porter).
  2. the porter's system prompt carries an escape hatch -- a marker to emit
     rather than an implementation to invent -- and its user prompt carries this
     node's specific gaps.
  3. the spliced body is scanned for that marker, and for the I/O the model was
     told never to emit. Both are findings, never gates.
  4. the compile bridge stops rendering an incomplete or unverified AI port as
     a clean build.

The scan is deliberately bounded by the PORT markers: codegen itself emits
``ifstream``/``fopen`` for sanctioned kernels (nd_io, the mPyFile texture cache,
the locator's file reader), and flagging those would make the check useless.
That boundary is the test that matters most here.
"""

from __future__ import annotations

import unittest

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


BEGIN = "// ===== BEGIN PORTED COMPUTE ====="
END = "// ===== END PORTED COMPUTE ====="


def _file(body, scaffold_extra=""):
    """A generated .cpp: scaffold, one PORT region, scaffold."""
    return ("#include <maya/MPxNode.h>\n"
            "%s\n"
            "MStatus X::compute() {\n"
            "    %s\n"
            "%s\n"
            "    %s\n"
            "    return MS::kSuccess;\n"
            "}\n" % (scaffold_extra, BEGIN, body, END))


# --------------------------------------------------------------------------- #
# 2. the escape hatch exists and is attached to every family
# --------------------------------------------------------------------------- #
class TestEscapeHatchInPrompt(unittest.TestCase):
    def test_marker_constant_is_distinctive(self):
        from mpynode.native.ai import prompt
        # Must not collide with ordinary C++ or with codegen's own markers.
        self.assertEqual("ND_PORT_INCOMPLETE", prompt.PORT_INCOMPLETE)

    def test_rule_names_the_marker_and_forbids_inventing(self):
        from mpynode.native.ai import prompt
        rule = prompt._UNPORTED_RULE
        self.assertIn(prompt.PORT_INCOMPLETE, rule)
        self.assertIn("ifstream", rule)
        self.assertIn("fopen", rule)

    def _system_for(self, base):
        from mpynode.native.ai import prompt
        spec = {"suggested": {"mpx_base": base, "node_type_name": "n"},
                "mpy_type": "mPyNode", "source_node": "n1",
                "compute": "self.out = 1.0", "init": "",
                "inputs": {}, "outputs": {"out": {"type": "float"}}}
        system, _user = prompt.build_prompt(spec, _file(""))
        return system

    def test_every_family_gets_the_rule(self):
        """It rides on the SYSTEM prompt, which is reused across the whole fix
        loop -- so round 2 cannot pressure the model into 'fixing' a marker away
        by inventing something that compiles."""
        from mpynode.native.ai import prompt
        from mpynode.native import compiler as codegen

        bases = ["MPxNode", codegen._TRANSFORM_BASE, codegen._LOCATOR_BASE,
                 codegen._IKSOLVER_BASE] + list(codegen._DEFORMER_BASES)
        for base in bases:
            self.assertIn(prompt.PORT_INCOMPLETE, self._system_for(base),
                          "base %r lost the escape hatch" % base)


class TestUnportedReachesThePrompt(unittest.TestCase):
    def _user_for(self, unported):
        from mpynode.native.ai import prompt
        spec = {"suggested": {"mpx_base": "MPxNode", "node_type_name": "n"},
                "mpy_type": "mPyNode", "source_node": "n1",
                "compute": "self.out = 1.0", "init": "",
                "inputs": {}, "outputs": {"out": {"type": "float"}},
                "portability": {"portable": True, "blockers": [],
                                "warnings": list(unported),
                                "unported": list(unported)}}
        _system, user = prompt.build_prompt(spec, _file(""))
        return user

    def test_gaps_are_listed_verbatim(self):
        user = self._user_for(["uses pandas (no deterministic C++ lowering)",
                               "pickle (a stack VM with import opcodes)"])
        self.assertIn("pandas", user)
        self.assertIn("pickle", user)
        self.assertIn("KNOWN GAPS", user)

    def test_no_gaps_leaves_the_prompt_unchanged(self):
        """A clean node's prompt must be byte-for-byte what it was, so the
        change cannot perturb ports that already work (or their cache)."""
        self.assertNotIn("KNOWN GAPS", self._user_for([]))

    def test_missing_portability_key_is_safe(self):
        from mpynode.native.ai import prompt
        spec = {"suggested": {"mpx_base": "MPxNode", "node_type_name": "n"},
                "mpy_type": "mPyNode", "source_node": "n1",
                "compute": "self.out = 1.0", "init": "",
                "inputs": {}, "outputs": {"out": {"type": "float"}}}
        _system, user = prompt.build_prompt(spec, _file(""))
        self.assertNotIn("KNOWN GAPS", user)


# --------------------------------------------------------------------------- #
# 3. the scan
# --------------------------------------------------------------------------- #
class TestScanPortedBody(unittest.TestCase):
    def _scan(self, cpp):
        from mpynode.native.ai import prompt
        return prompt.scan_ported_body(cpp)

    def test_marker_is_collected_with_its_reason(self):
        r = self._scan(_file(
            "    // ND_PORT_INCOMPLETE: pandas groupby has no C++ equivalent\n"
            "    h_out.setDouble(0.0);"))
        self.assertEqual(["pandas groupby has no C++ equivalent"],
                         r["incomplete"])
        self.assertTrue(r["ported"])

    def test_marker_without_a_reason_still_counts(self):
        r = self._scan(_file("    // ND_PORT_INCOMPLETE\n"
                             "    h_out.setDouble(0.0);"))
        self.assertEqual(["(no reason given)"], r["incomplete"])

    def test_clean_body_reports_nothing(self):
        r = self._scan(_file("    h_out.setDouble(in_a * 2.0);"))
        self.assertEqual([], r["incomplete"])
        self.assertEqual([], r["io"])
        self.assertTrue(r["ported"])

    def test_deterministic_file_has_no_ported_body(self):
        """No PORT markers -> nothing was AI-authored. This is what makes
        'verify did not run' mean something different on a lowered node."""
        r = self._scan("MStatus X::compute() { std::ifstream f(p); }\n")
        self.assertFalse(r["ported"])
        self.assertEqual([], r["io"])

    def test_invented_file_io_is_flagged(self):
        for line in ("    std::ifstream f(path);",
                     "    std::ofstream o(path);",
                     "    FILE* fp = fopen(path, \"r\");"):
            r = self._scan(_file(line))
            self.assertTrue(r["io"], line)

    def test_invented_process_and_network_are_flagged(self):
        self.assertTrue(self._scan(_file("    system(cmd);"))["io"])
        self.assertTrue(self._scan(_file("    int s = socket(1, 2, 3);"))["io"])

    def test_scene_access_via_mglobal_is_flagged(self):
        r = self._scan(_file("    MGlobal::executeCommand(\"polyCube\");"))
        self.assertTrue(any("MGlobal" in w for w in r["io"]), r["io"])

    def test_sanctioned_scaffold_io_is_NOT_flagged(self):
        """The single most important case. nd_io_cpp, file_texture_cpp and
        emit_locator legitimately emit exactly these calls -- but into the
        SCAFFOLD. Bounding the scan by the PORT markers is what separates
        codegen's I/O from the model's, with no allow-list to maintain."""
        cpp = _file("    h_out.setDouble(0.0);",
                    scaffold_extra=(
                        "static void nd_read(const char* p) {\n"
                        "    std::ifstream fh(p, std::ios::binary);\n"
                        "    FILE* f = fopen(p, \"rb\");\n"
                        "}\n"))
        r = self._scan(cpp)
        self.assertEqual([], r["io"])

    def test_marker_prose_mentioning_ifstream_is_not_a_finding(self):
        """The rule REQUIRES the model to explain itself. Flagging it for saying
        'this would need std::ifstream' would punish the exact behaviour asked
        for, and teach it to stop explaining."""
        r = self._scan(_file(
            "    // ND_PORT_INCOMPLETE: reading the cache would need "
            "std::ifstream, which is not allowed\n"
            "    h_out.setDouble(0.0);"))
        self.assertEqual([], r["io"])
        self.assertEqual(1, len(r["incomplete"]))

    def test_io_inside_a_string_literal_is_not_a_finding(self):
        r = self._scan(_file('    MString m("fopen(x) is forbidden");'))
        self.assertEqual([], r["io"])

    def test_block_comment_is_stripped(self):
        r = self._scan(_file("    /* std::ofstream would go here */\n"
                             "    h_out.setDouble(0.0);"))
        self.assertEqual([], r["io"])

    def test_multiple_port_regions_are_all_scanned(self):
        cpp = (_file("    // ND_PORT_INCOMPLETE: first\n")
               + _file("    std::ifstream f(p);"))
        r = self._scan(cpp)
        self.assertEqual(["first"], r["incomplete"])
        self.assertTrue(r["io"])

    def test_empty_and_none_are_safe(self):
        for bad in ("", None):
            r = self._scan(bad)
            self.assertEqual({"ported": False, "incomplete": [], "io": []}, r)


# --------------------------------------------------------------------------- #
# 4. the bridge: incomplete / unverified stop reading as a clean build
# --------------------------------------------------------------------------- #
def _row(**kw):
    row = {
        "source_node": "n1", "type_name": "myNode", "build_status": "compiled",
        "build_reason": "", "ported": False, "incomplete": [], "invented_io": [],
        "verify": {"ran": True, "pass": True, "maxerr": 1e-9, "tol": 1e-6,
                   "reason": ""},
        "spec": {"portability": {"blockers": [], "unported": []}},
    }
    row.update(kw)
    return row


class TestScanRunsBeforeVp2Injection(unittest.TestCase):
    """The scan must be taken BEFORE the VP2 override transform.

    ``emit_vp2_override.inject_vp2_override`` replaces the whole PORT region with
    a marker-stripped ``nd_texel`` call, so an mPyFile's finalized .cpp has no
    port markers at all. Scanning after it reports nothing for the entire texture
    family -- not just their honest declarations but an invented ifstream too,
    which is the case the scan exists for. Caught in a real mega build:
    fileTexture and gameOfLifeTex both shipped genuine PORT_INCOMPLETE notes that
    the manifest missed."""

    def test_vp2_injection_consumes_the_whole_port_region(self):
        """Pin the premise. If injection ever stops replacing the region, the
        ordering constraint below becomes free rather than load-bearing -- and
        this test says so at that moment instead of leaving a stale comment.

        The region is now located through helpers rather than inline: injection
        handles a deterministically-lowered compute as well as an AI-ported one,
        so ``_PORT_BEGIN`` lives in ``_port_region``. The premise is unchanged --
        whichever shape matched, the WHOLE region is captured by value into
        ``port_full`` and replaced -- so the assertions follow it to its new
        home instead of being dropped."""
        import inspect
        from mpynode.native.compiler import emit_vp2_override

        src = inspect.getsource(emit_vp2_override.inject_vp2_override)
        self.assertIn("port_full", src,
                      "injection no longer captures the PORT region by value")
        self.assertIn("_port_region", src,
                      "injection no longer locates the PORT region")
        region_src = inspect.getsource(emit_vp2_override._port_region)
        self.assertIn("_PORT_BEGIN", region_src)
        self.assertIn("_PORT_END", region_src)

    def test_controller_scans_before_it_injects(self):
        """Source-order check: the honesty scan block must precede the VP2
        block. A unit test cannot easily drive a whole compile, and the bug is
        purely one of ORDER."""
        import inspect
        from mpynode.native.toolchain import compile_controller

        src = inspect.getsource(compile_controller)
        scan_at = src.find("honesty[tn] = _prompt.scan_ported_body")
        vp2_at = src.find("emit_vp2_override.inject_vp2_override")
        self.assertNotEqual(-1, scan_at, "the honesty scan block is gone")
        self.assertNotEqual(-1, vp2_at, "the VP2 injection block is gone")
        self.assertLess(scan_at, vp2_at,
                        "the scan must run BEFORE VP2 injection strips the "
                        "PORT markers, or every mPyFile reports clean")

    def test_rows_consume_the_prescan_not_a_fresh_read(self):
        """Row construction must use the stashed result. Re-reading the .cpp
        there would put us back after the transform."""
        import inspect
        from mpynode.native.toolchain import compile_controller

        src = inspect.getsource(compile_controller)
        self.assertIn('scan = honesty.get(tn)', src)


class TestBridgeAttention(unittest.TestCase):
    def _wants(self, row):
        from mpynode.ui.llm import compile_bridge
        return compile_bridge._wants_attention(row)

    def test_clean_verified_build_is_quiet(self):
        self.assertFalse(self._wants(_row()))

    def test_incomplete_marker_wants_attention(self):
        self.assertTrue(self._wants(_row(incomplete=["pandas groupby"])))

    def test_invented_io_wants_attention(self):
        self.assertTrue(self._wants(_row(invented_io=["C++ file stream"])))

    def test_unverified_AI_PORT_wants_attention(self):
        """'it compiled' is the only gate an LLM-authored body passed."""
        self.assertTrue(self._wants(_row(
            ported=True,
            verify={"ran": False, "pass": None, "maxerr": None, "tol": None,
                    "reason": "uses RNG via the AI porter"})))

    def test_unverified_DETERMINISTIC_node_stays_quiet(self):
        """The 13 legitimate verify skips (RNG, image read, float2, an unbound
        skinCluster...) must not start screaming on a transpiled node: there the
        transpiler IS the guarantee, so a skip is routine."""
        self.assertFalse(self._wants(_row(
            ported=False,
            verify={"ran": False, "pass": None, "maxerr": None, "tol": None,
                    "reason": "no scalar outputs to compare"})))

    def test_dropped_still_wants_attention(self):
        self.assertTrue(self._wants(_row(build_status="dropped")))

    def test_diverged_still_wants_attention(self):
        self.assertTrue(self._wants(_row(
            verify={"ran": True, "pass": False, "maxerr": 1.0, "tol": 1e-6,
                    "reason": ""})))


class TestBridgeSummary(unittest.TestCase):
    def _lines(self, rows):
        from mpynode.ui.llm import compile_bridge
        return compile_bridge.verify_summary_lines({"nodes": rows})

    def test_incomplete_is_stated_on_the_status_line(self):
        lines = self._lines([_row(incomplete=["pandas groupby"])])
        self.assertIn("INCOMPLETE", lines[0])
        self.assertTrue(any("pandas groupby" in ln for ln in lines))

    def test_build_status_itself_is_untouched(self):
        """`build_status` gates verify, companions and scratch cleanup upstream
        (`in ("compiled", "transformed")`). Folding incompleteness INTO it would
        skip verify on exactly the nodes that most need it, so the honesty is a
        separate field and only the rendered label changes."""
        row = _row(incomplete=["x"])
        self._lines([row])
        self.assertEqual("compiled", row["build_status"])

    def test_invented_io_is_called_out(self):
        lines = self._lines([_row(invented_io=["C++ file stream"])])
        self.assertTrue(any("instructed not to emit" in ln for ln in lines),
                        lines)

    def test_unverified_ai_port_is_called_out(self):
        lines = self._lines([_row(
            ported=True,
            verify={"ran": False, "pass": None, "maxerr": None, "tol": None,
                    "reason": ""})])
        self.assertTrue(any("NOT verified" in ln for ln in lines), lines)

    def test_clean_row_gets_exactly_one_line(self):
        self.assertEqual(1, len(self._lines([_row()])))


class TestBridgeClassify(unittest.TestCase):
    def _c(self, rows):
        from mpynode.ui.llm import compile_bridge
        return compile_bridge.classify({"nodes": rows})

    def test_incomplete_bucket_and_needs_ai(self):
        c = self._c([_row(incomplete=["x"])])
        self.assertEqual(1, len(c["incomplete"]))
        self.assertTrue(c["needs_ai"])

    def test_unchecked_bucket_and_needs_ai(self):
        c = self._c([_row(ported=True,
                          verify={"ran": False, "pass": None, "maxerr": None,
                                  "tol": None, "reason": ""})])
        self.assertEqual(1, len(c["unchecked"]))
        self.assertTrue(c["needs_ai"])

    def test_clean_build_needs_no_ai(self):
        c = self._c([_row()])
        self.assertFalse(c["needs_ai"])
        self.assertEqual(1, len(c["verified_ok"]))


if __name__ == "__main__":
    unittest.main()
