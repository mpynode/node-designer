"""The AI-optimizer knowledge SSOT: importable, 7-bit ASCII, and it carries the
load-bearing optimization + correctness rules that make the optimizer safe.

Pure-text module (no Maya import), so this test needs no standalone Maya.
"""

from __future__ import annotations

import unittest

from mpynode.native.ai import optimizer_knowledge as ok


class TestOptimizerKnowledge(unittest.TestCase):
    def test_guide_is_ascii(self):
        # The guide is injected into a prompt whose HARD rule is 7-bit ASCII; a
        # stray unicode dash here would leak into the model's C++ and fail clang.
        for name in ("OPTIMIZER_GUIDE", "CORRECTNESS", "FUSED_EXEMPLAR"):
            text = getattr(ok, name)
            text.encode("ascii")  # raises UnicodeEncodeError if any non-ASCII

    def test_guide_carries_the_load_bearing_rules(self):
        blob = ok.OPTIMIZER_GUIDE + ok.CORRECTNESS
        for needle in ("-ffp-contract=off", "-ffast-math", "x*x", "offset",
                       "strides", "static const", "topology", "ND_RESTRICT"):
            self.assertIn(needle, blob, "missing rule: %s" % needle)

    def test_correctness_reference_is_interpreted_numpy(self):
        # The gate must compare to the interpreted Python, not the old C++.
        self.assertIn("INTERPRETED numpy", ok.CORRECTNESS)

    def test_optimize_prompt_embeds_cpp_and_returns_pair(self):
        spec = {"compute": "self.out = self.a ** 2", "init": "import numpy as np"}
        system, user = ok.build_optimize_prompt("int MAGIC_CPP_TOKEN = 1;", spec,
                                                bench_hint="median 12.3 ms")
        self.assertTrue(system and user)
        self.assertIn("MAGIC_CPP_TOKEN", user)    # the source is embedded
        self.assertIn("self.a ** 2",     user)    # the parity reference too
        self.assertIn("12.3 ms",         user)    # the bench hint
        self.assertIn("COMPLETE",        system)  # whole-file output contract

    def test_fix_prompt_embeds_errors_and_cpp(self):
        system, user = ok.build_fix_prompt("int X = ;", "error: expected expression")
        self.assertTrue(system and user)
        self.assertIn("int X = ;", user)
        self.assertIn("expected expression", user)

    def test_prompts_are_ascii(self):
        for build in (
            lambda: ok.build_optimize_prompt("int x=1;", {"compute": "x"}),
            lambda: ok.build_fix_prompt("int x=1;", "err"),
        ):
            system, user = build()
            system.encode("ascii")
            user.encode("ascii")


# A stand-in for a generated plug-in: has the two Maya entry points and balances.
_BASE = (
    "#include <maya/MPxNode.h>\n"
    "class N : public MPxNode { public: MStatus compute(); };\n"
    "MStatus N::compute() { int a = 1; return MS::kSuccess; }\n"
    "MStatus initializePlugin(MObject o) { return MS::kSuccess; }\n"
    "MStatus uninitializePlugin(MObject o) { return MS::kSuccess; }\n"
)


class TestImplausibleReason(unittest.TestCase):
    """The guard that stopped truncated / prose answers reaching the .cpp."""

    def test_a_real_rewrite_is_accepted(self):
        self.assertIsNone(ok.implausible_reason(
            _BASE.replace("int a = 1;", "int a = 2;"), _BASE))

    def test_unchanged_source_is_accepted(self):
        # "return the file UNCHANGED" is an explicit, legal answer.
        self.assertIsNone(ok.implausible_reason(_BASE, _BASE))

    def test_empty_is_rejected(self):
        self.assertIn("empty", ok.implausible_reason("   ", _BASE))

    def test_prose_only_answer_is_rejected(self):
        # Verbatim shape of the answer that landed on disk as a 564-byte .cpp.
        prose = ("**The problem is clear:** the previous response was truncated "
                 "mid-output. To proceed I need the original C++ source.")
        self.assertIn("not C++", ok.implausible_reason(prose, _BASE))

    def test_truncated_midway_is_rejected(self):
        # Cut inside compute(): braces no longer balance.
        cut = _BASE[:_BASE.index("return MS::kSuccess; }")]
        self.assertIn("truncated", ok.implausible_reason(cut, _BASE))

    def test_answer_missing_an_entry_point_is_rejected(self):
        gone = _BASE.replace(
            "MStatus uninitializePlugin(MObject o) { return MS::kSuccess; }", "")
        self.assertIn("uninitializePlugin", ok.implausible_reason(gone, _BASE))

    def test_anchor_absent_from_baseline_is_not_required(self):
        # Calibrated to the baseline: a source without the anchors cannot be
        # false-flagged for lacking them.
        base = "int f() { int a = 1; return a; }\n"
        self.assertIsNone(ok.implausible_reason(
            "int f() { int a = 2; return a; }\n", base))

    def test_unbalanced_baseline_disables_the_brace_check(self):
        # A baseline with a brace in a string literal must not make every
        # candidate look truncated.
        base = 'const char* s = "{"; int f() { return 0; }\n'
        cand = 'const char* s = "{"; int f() { return 1; }\n'
        self.assertIsNone(ok.implausible_reason(cand, base))


# A generated .cpp ships as SOURCE the user compiles on their own machine
# (build.sh / build.bat), so it must build with Apple clang AND MSVC. The
# optimizer's own compile gate is clang on the host, which accepts every
# clang-only construct below -- so without this check a macOS-only rewrite would
# validate, compile, benchmark faster and ship.
_PBASE = (
    "#include <maya/MPxNode.h>\n"
    "#include <cmath>\n"
    "MStatus initializePlugin(MObject o) { return MS::kSuccess; }\n"
    "MStatus uninitializePlugin(MObject o) { return MS::kSuccess; }\n"
    "double f(double x) {\n"
    "    return std::cos(x);\n"
    "}\n"
)


def _body(repl):
    """_PBASE with the function body replaced. The directive lands on its OWN
    line -- a preprocessor directive must be the first token on a line, so
    splicing it after ``{`` would be invalid C++ and would test nothing."""
    return _PBASE.replace("    return std::cos(x);\n", repl)


class TestPortabilityGate(unittest.TestCase):
    """A candidate may not INTRODUCE code only one toolchain accepts."""

    def test_clean_rewrite_is_accepted(self):
        self.assertIsNone(ok.implausible_reason(
            _body("    return std::cos(x) + 0.0;\n"), _PBASE))

    def test_attribute_is_rejected(self):
        cand = _PBASE.replace("double f(",
                              "__attribute__((always_inline)) double f(")
        self.assertIn("__attribute__", ok.implausible_reason(cand, _PBASE))

    def test_builtin_is_rejected(self):
        cand = _body("    if (__builtin_expect(x > 0, 1)) return std::cos(x);\n"
                     "    return 0.0;\n")
        self.assertIn("__builtin_", ok.implausible_reason(cand, _PBASE))

    def test_platform_header_is_rejected(self):
        cand = _PBASE.replace("#include <cmath>\n",
                              "#include <cmath>\n#include <arm_neon.h>\n")
        self.assertIn("platform-specific header",
                      ok.implausible_reason(cand, _PBASE))

    def test_int128_in_real_code_is_rejected(self):
        cand = _body("    __int128 w = 1; (void)w;\n    return std::cos(x);\n")
        self.assertIn("__int128", ok.implausible_reason(cand, _PBASE))

    def test_int128_named_only_in_a_comment_is_accepted(self):
        # hexAttribute's ONLY __int128 is a comment explaining that the
        # optimizer avoided it because MSVC has no such type, and wrote a
        # portable 64x64->128 multiply instead. Rejecting that would kill a
        # candidate for doing exactly the right thing.
        cand = _PBASE.replace(
            "double f(",
            "// no __int128 here: MSVC has no such type\ndouble f(")
        self.assertIsNone(ok.implausible_reason(cand, _PBASE))

    def test_token_only_in_a_string_literal_is_accepted(self):
        cand = _body('    const char* s = "__int128"; (void)s;\n'
                     "    return std::cos(x);\n")
        self.assertIsNone(ok.implausible_reason(cand, _PBASE))

    def test_platform_branch_without_a_fallback_is_rejected(self):
        cand = _body("#if defined(__APPLE__)\n"
                     "    return __sincos_helper(x);\n"
                     "#endif\n"
                     "    return std::cos(x);\n")
        self.assertIn("no #else", ok.implausible_reason(cand, _PBASE))

    def test_platform_branch_with_a_fallback_is_accepted(self):
        # helixCurve's real shape: an Apple __sincos fast path is fine PRECISELY
        # because MSVC still gets std::cos/std::sin from the #else.
        cand = _body("#if defined(__APPLE__)\n"
                     "    return __sincos_helper(x);\n"
                     "#else\n"
                     "    return std::cos(x);\n"
                     "#endif\n")
        self.assertIsNone(ok.implausible_reason(cand, _PBASE))

    def test_pragma_only_conditional_is_accepted(self):
        # py_to_cpp's fp-contract fusion guard is pragma-only: there is no code
        # for the other toolchain to miss, and MSVC defaults to /fp:precise.
        cand = _body("#if defined(__clang__)\n"
                     "#pragma clang fp contract(off)\n"
                     "#endif\n"
                     "    return std::cos(x);\n")
        self.assertIsNone(ok.implausible_reason(cand, _PBASE))

    def test_construct_already_in_the_baseline_is_kept(self):
        # Baseline-calibrated, like every other check: ND_RESTRICT's guarded
        # __restrict__ is in every generated baseline and must never flag.
        base = _PBASE.replace("double f(",
                              "__attribute__((always_inline)) double f(")
        cand = base.replace("std::cos(x)", "std::cos(x) + 0.0")
        self.assertIsNone(ok.implausible_reason(cand, base))

    # -- Windows SAL macro names used as identifiers -----------------------
    # helixCurve's promoted optimizer winner declared `MPoint* __out = &_cv[0];`
    # for a contiguous-write fast path. sal.h makes __out a MACRO, so MSVC saw
    # `MPoint* [SA_annotation] = ...` -> C2059, then C2337 on every `__out[__i]`.
    # clang has no sal.h, so it passed the optimizer's compile gate, benchmarked
    # faster and shipped. MEASURED on Windows 2026-08-31.

    def test_sal_out_identifier_is_rejected(self):
        cand = _body("    MPoint* __out = &p[0];\n"
                     "    __out[0].x = x;\n"
                     "    return std::cos(x);\n")
        reason = ok.implausible_reason(cand, _PBASE)
        self.assertIsNotNone(reason, "a SAL macro name must be rejected")
        self.assertIn("SAL", reason)

    def test_other_sal_directional_names_are_rejected(self):
        for name in ("__in", "__inout", "__out_opt", "__deref_out",
                     "__range", "__bound", "__success", "__reserved"):
            cand = _body("    double %s = x;\n    return %s;\n" % (name, name))
            self.assertIsNotNone(ok.implausible_reason(cand, _PBASE),
                                 "%s must be rejected" % name)

    def test_the_transpilers_own_double_underscore_temps_are_accepted(self):
        """The rule may NOT be "no __ prefix": __-prefixed temporaries are the
        transpiler's convention (__i appears 12590 times across the templates).
        Measured against the installed SDK, exactly ONE of the project's 100
        distinct __ identifiers collides with sal.h -- __out."""
        cand = _body("    double __L0 = x, __s0 = 0.0;\n"
                     "    for (int __i = 0; __i < 4; ++__i) __s0 += __L0;\n"
                     "    double __o = __s0, __n = 1.0, __a = __o / __n;\n"
                     "    return __a + std::cos(x);\n")
        self.assertIsNone(ok.implausible_reason(cand, _PBASE))

    def test_sal_name_only_in_a_comment_is_accepted(self):
        cand = _PBASE.replace(
            "double f(", "// renamed off __out: sal.h defines it\ndouble f(")
        self.assertIsNone(ok.implausible_reason(cand, _PBASE))


if __name__ == "__main__":
    unittest.main()
