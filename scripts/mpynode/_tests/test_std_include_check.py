"""The MSVC include-isolation defect class, and the three things that close it.

THE DEFECT. libc++ (Apple clang) leaks transitive includes generously; the MSVC
STL does not. A TU that says ``std::mutex`` while including only ``<vector>`` is
rc=0 on macOS and C2039 on Windows. Every gate in this pipeline is a macOS
clang run, so nothing here can see it.

WHAT IS PINNED:
  1. ``tools/check_std_includes.py`` catches all five calibration defects
     (mutex/sstream/fstream/array/limits) -- clang's own flags catch 2 of 5 --
     and stays SILENT on the seven ``pair``/``make_pair``/``move`` hits a prior
     verification pass refuted. A checker that cries wolf gets switched off, so
     the false-hit assertion matters as much as the recall one.
  2. The known-clean corpus (the 42 mega TUs) reports ZERO findings, which is
     the calibration the table was tuned against.
  3. ``PORTABILITY_RULE`` exists in ONE place and reaches BOTH the porter and
     the optimizer system prompts.
  4. The porter repairs a missing include rather than rejecting the port, and
     ``scan_ported_body`` keeps its three-key shape when there is nothing to
     say (a caller compares it against that dict literal).

Pure text + a path-loaded module; no Maya needed beyond the suite's standard
init.
"""

from __future__ import annotations

import importlib.util
import os
import unittest

from ._setup import standalone_init


def setUpModule():
    standalone_init()


_REPO = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", ".."))
_TOOL = os.path.join(_REPO, "tools", "check_std_includes.py")
_MEGA_SRC = os.path.join(_REPO, "compiled_templates", "_combined_plugin",
                         "build", "source")
_COMPILER_DIR = os.path.join(_REPO, "scripts", "mpynode", "native", "compiler")


def _load_tool():
    spec = importlib.util.spec_from_file_location("check_std_includes_t", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BEGIN = "// ===== BEGIN PORTED COMPUTE ====="
END = "// ===== END PORTED COMPUTE ====="

# The AI translation unit's real include set (compiler/emit_attr.py:_INCLUDES).
# Everything the model can reach beyond this is a Windows-only compile error.
_AI_TU_HEAD = ("#include <cmath>\n"
               "#include <algorithm>\n"
               "#include <vector>\n"
               "#include <random>\n"
               "#include <cstdint>\n"
               "#include <maya/MPxNode.h>\n")


def _ported(body):
    """A generated .cpp with the AI include set and one PORT region."""
    return (_AI_TU_HEAD
            + "MStatus X::compute() {\n"
            + BEGIN + "\n"
            + "    " + body + "\n"
            + END + "\n"
            + "    return MS::kSuccess;\n}\n")


# --------------------------------------------------------------------------- #
# 1. the checker: recall and false hits
# --------------------------------------------------------------------------- #
class TestChecker(unittest.TestCase):
    def setUp(self):
        self.chk = _load_tool()

    _BASE = ("#include <vector>\n"
             "#include <cmath>\n"
             "#include <string>\n"
             "#include <map>\n")

    # (header the facility needs, a statement that uses it)
    CALIBRATION = [
        ("mutex", "std::mutex g; std::lock_guard<std::mutex> lk(g);"),
        ("sstream", "std::ostringstream oss; oss << 1;"),
        ("fstream", "std::ifstream fh(\"p\");"),
        ("array", "std::array<double,3> a{};"),
        ("limits", "double d = std::numeric_limits<double>::max();"),
    ]

    def test_all_five_calibration_defects_are_caught(self):
        for header, stmt in self.CALIBRATION:
            txt = self._BASE + "void g() { %s }\n" % stmt
            found = self.chk.check_text(txt)
            self.assertIn(header, self.chk.missing_headers(found),
                          "missed std defect needing <%s>: %s" % (header, stmt))

    def test_the_defect_disappears_once_the_header_is_there(self):
        for header, stmt in self.CALIBRATION:
            txt = ("#include <%s>\n" % header) + self._BASE + \
                "void g() { %s }\n" % stmt
            self.assertEqual([], self.chk.missing_headers(
                self.chk.check_text(txt)), header)

    def test_pair_move_make_pair_do_not_cry_wolf(self):
        # The seven refuted hits: <map>/<string>/<vector> make these complete on
        # every implementation. Reporting them again would burn the checker's
        # credibility on known-good code.
        txt = self._BASE + (
            "void h() { std::map<int,int> m;"
            " m.insert(std::make_pair(1,2));"
            " std::pair<int,int> p(1,2);"
            " std::string s = std::move(std::string(\"a\"));"
            " std::size_t n = s.size(); (void)p; (void)n; }\n")
        self.assertEqual([], self.chk.check_text(txt))

    def test_unmapped_names_are_never_a_failure(self):
        txt = self._BASE + "void h() { std::totally_not_a_real_facility x; }\n"
        self.assertEqual([], self.chk.check_text(txt))

    def test_comments_and_string_literals_are_not_code(self):
        txt = self._BASE + (
            "void h() { const char* s = \"std::mutex\"; (void)s; }\n"
            "// std::ofstream in a comment\n"
            "/* std::array<int,2> in a block comment */\n")
        self.assertEqual([], self.chk.check_text(txt))

    def test_order_is_reported_when_the_header_lands_after_first_use(self):
        txt = "void h() { std::array<int,2> a{}; (void)a; }\n#include <array>\n"
        found = self.chk.check_text(txt)
        self.assertEqual(["order"], [f.kind for f in found])
        # ORDER is not a missing header, so it must not be auto-added.
        self.assertEqual([], self.chk.missing_headers(found))

    def test_cli_self_test_passes(self):
        self.assertEqual(0, self.chk.main(["check_std_includes.py",
                                           "--self-test"]))


# --------------------------------------------------------------------------- #
# 2. the calibration corpus: the shipped TUs must be silent
# --------------------------------------------------------------------------- #
class TestKnownCleanCorpus(unittest.TestCase):
    def test_mega_corpus_reports_zero_findings(self):
        if not os.path.isdir(_MEGA_SRC):
            self.skipTest("mega build/source not present")
        chk = _load_tool()
        files = [f for f in sorted(os.listdir(_MEGA_SRC)) if f.endswith(".cpp")]
        self.assertTrue(files, "no TUs to calibrate against")
        bad = {}
        for fn in files:
            found = chk.check_file(os.path.join(_MEGA_SRC, fn),
                                   search_dirs=[_COMPILER_DIR])
            if found:
                bad[fn] = [chk.format_finding(f) for f in found]
        self.assertEqual({}, bad)


# --------------------------------------------------------------------------- #
# 3. region scoping + the porter's repair
# --------------------------------------------------------------------------- #
class TestPortedRegion(unittest.TestCase):
    def test_region_resolves_against_the_whole_files_includes(self):
        # std::sqrt is covered by the scaffold's <cmath>; the region must not be
        # blamed for a header it does not carry itself.
        chk = _load_tool()
        cpp = _ported("h_out.setDouble(std::sqrt(in_a));")
        body = "h_out.setDouble(std::sqrt(in_a));"
        self.assertEqual([], chk.check_region(body, cpp))

    def test_missing_std_includes_finds_what_libcxx_hid(self):
        from mpynode.native.ai import prompt
        cpp = _ported("static std::mutex m; std::lock_guard<std::mutex> lk(m);")
        self.assertEqual(["mutex"], prompt.missing_std_includes(cpp))

    def test_missing_std_includes_is_quiet_on_a_clean_body(self):
        from mpynode.native.ai import prompt
        self.assertEqual(
            [], prompt.missing_std_includes(
                _ported("h_out.setDouble(std::sqrt(in_a) * 2.0);")))

    def test_codegen_own_code_outside_the_markers_is_not_a_port_finding(self):
        # The scan is bounded by the markers for the same reason the I/O scan is:
        # codegen emits sanctioned facilities of its own.
        from mpynode.native.ai import prompt
        cpp = (_AI_TU_HEAD
               + "static std::mutex g_codegenLock;\n"
               + "MStatus X::compute() {\n" + BEGIN + "\n"
               + "    h_out.setDouble(1.0);\n" + END + "\n}\n")
        self.assertEqual([], prompt.missing_std_includes(cpp))

    def test_add_std_includes_repairs_the_file(self):
        from mpynode.native.ai import prompt
        cpp = _ported("static std::mutex m; std::lock_guard<std::mutex> lk(m);")
        fixed = prompt.add_std_includes(cpp, ["mutex"])
        self.assertIn("#include <mutex>", fixed)
        # placed in the include block, above the compute that uses it
        self.assertLess(fixed.index("#include <mutex>"), fixed.index("compute"))
        # and the repair is complete: nothing left to report
        self.assertEqual([], prompt.missing_std_includes(fixed))
        # nothing else moved
        self.assertEqual(len(cpp.splitlines()) + 1, len(fixed.splitlines()))

    def test_add_std_includes_is_a_noop_with_nothing_to_add(self):
        from mpynode.native.ai import prompt
        cpp = _ported("h_out.setDouble(1.0);")
        self.assertEqual(cpp, prompt.add_std_includes(cpp, []))


# --------------------------------------------------------------------------- #
# 4. the report surface keeps its shape
# --------------------------------------------------------------------------- #
class TestScanShape(unittest.TestCase):
    def test_includes_key_appears_only_when_there_is_something_to_say(self):
        from mpynode.native.ai import prompt
        clean = prompt.scan_ported_body(_ported("h_out.setDouble(1.0);"))
        self.assertNotIn("includes", clean)
        dirty = prompt.scan_ported_body(
            _ported("static std::mutex m; (void)m;"))
        self.assertEqual(["mutex"], dirty["includes"])

    def test_empty_and_none_keep_the_three_key_shape(self):
        # compile_controller and test_port_honesty both compare against this
        # exact literal; a fourth key would break them.
        from mpynode.native.ai import prompt
        for bad in ("", None):
            self.assertEqual({"ported": False, "incomplete": [], "io": []},
                             prompt.scan_ported_body(bad))

    def test_a_missing_include_is_never_a_gate(self):
        # The standing directive: valid work is never rejected at the output
        # boundary. The finding rides alongside a normal, shipped result.
        from mpynode.native.ai import prompt
        r = prompt.scan_ported_body(_ported("static std::mutex m; (void)m;"))
        self.assertTrue(r["ported"])
        self.assertEqual([], r["io"])
        self.assertEqual([], r["incomplete"])


# --------------------------------------------------------------------------- #
# 5. the prompt rule: one home, both consumers
# --------------------------------------------------------------------------- #
class TestPortabilityRule(unittest.TestCase):
    def test_rule_is_ascii_and_names_both_compilers(self):
        from mpynode.native.ai import translation_knowledge as tk
        tk.PORTABILITY_RULE.encode("ascii")
        low = tk.PORTABILITY_RULE.lower()
        for needle in ("msvc", "clang", "libc++", "transitive", "c++17"):
            self.assertIn(needle, low, "rule does not mention %s" % needle)

    def test_rule_is_short(self):
        # Prompt real estate is scarce: nd_runtime.h alone is ~60k of the 64k
        # response budget. A rule that grows without bound crowds out the node.
        from mpynode.native.ai import translation_knowledge as tk
        self.assertLess(len(tk.PORTABILITY_RULE), 900)

    def test_it_reaches_the_porter_system_prompt(self):
        from mpynode.native.ai import prompt, translation_knowledge as tk
        spec = {"suggested": {"mpx_base": "MPxNode", "node_type_name": "n"},
                "mpy_type": "mPyNode", "source_node": "n1",
                "compute": "self.out = 1.0", "init": "",
                "inputs": {}, "outputs": {"out": {"type": "float"}}}
        system, _user = prompt.build_prompt(spec, _ported("h_out.setDouble(1);"))
        self.assertIn(tk.PORTABILITY_RULE, system)

    def test_it_reaches_both_optimizer_system_prompts(self):
        from mpynode.native.ai import (optimizer_knowledge as ok,
                                       translation_knowledge as tk)
        system, _u = ok.build_optimize_prompt("int x=1;", {"compute": "x"})
        self.assertIn(tk.PORTABILITY_RULE, system)
        system, _u = ok.build_fix_prompt("int x=;", "error")
        self.assertIn(tk.PORTABILITY_RULE, system)

    def test_it_reaches_the_agent_task_brief(self):
        from mpynode.native.ai import (optimizer_agent as oa,
                                       translation_knowledge as tk)
        self.assertIn("{portability}", oa._TASK_MD)
        self.assertIs(oa.PORTABILITY_RULE, tk.PORTABILITY_RULE)

    def test_the_text_lives_in_exactly_one_place(self):
        # "Do not duplicate the text in two places" -- the failure mode is two
        # copies drifting apart, which a grep for a distinctive phrase catches.
        import mpynode.native.ai as ai_pkg

        needle = "libc++ satisfies many facilities through"
        ai_dir = os.path.dirname(ai_pkg.__file__)
        homes = []
        for fn in sorted(os.listdir(ai_dir)):
            if not fn.endswith(".py"):
                continue
            # These sources are UTF-8; Windows text mode defaults to cp1252 and
            # dies on the first byte outside it (0x9d, measured 2026-08-14).
            with open(os.path.join(ai_dir, fn), encoding="utf-8") as fh:
                if needle in fh.read():
                    homes.append(fn)
        self.assertEqual(["translation_knowledge.py"], homes)


if __name__ == "__main__":
    unittest.main()
