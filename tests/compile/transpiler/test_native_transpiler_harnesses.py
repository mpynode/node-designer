"""Gate the standalone numpy->C++ transpiler harnesses.

The native transpiler ships eleven self-contained oracle/driver harnesses that
compare the compiler against a numpy (or golden-file) ground truth, most of them
by compiling real C++ with clang++:

  * native/nd_runtime_test.py  -- nd:: runtime ops vs numpy (Array/reduce/dot...)
  * native/nd_rng_test.py      -- nd::MT19937 bit-identical to numpy RandomState
  * native/nd_intnan_test.py   -- integer //0, %0, INT64_MIN//-1 and NaN min/max
  * native/py_to_cpp_test.py   -- AST transpiler parity + reject-or-lower
  * native/nd_lower_test.py    -- codegen lowering (generic/geo/deform/xform +
                                  RNG fixtures) vs numpy, plus reject fixtures
  * native/metaballs_glue_parity.py        -- lowered metaballs glue vs numpy
  * native/sdf_dmc_parity.py               -- SDF dual-marching-cubes vs golden
  * native/native_side_effect_noop_test.py -- NativeSideEffect lowers to nothing
  * native/twist_swing_lowering_test.py    -- twist/swing skin C++ parity
  * native/twist_swing_dual_lowering_test.py -- two-weight-set compute LOWERS
  * native/twist_swing_dual_parity_test.py -- two-weight-set C++ byte-parity
    (the shipped proof for _demos/twist_swing_skin_source.py)

Each harness has its own success protocol (prints a summary + an "ALL PASS" /
"ALL BIT-EXACT" marker and exits 0; prints failures and exits 1). They were
Maya-FREE by design (their own MVector/MPoint shims) but need numpy, so they run
under the SAME interpreter as this gate (``sys.executable`` is mayapy here) --
which also gives us dual-numpy coverage for free (numpy 1.26.4 under Maya 2026,
2.2.6 under Maya 2024). Nothing in the unit suite referenced these
harnesses before, so their fixtures (including the bit-exact RNG lowering
fixtures) were NOT regression-protected by the gate. This wrapper closes that
gap: it subprocess-invokes each harness and fails the gate if any fixture drifts.

If no C++ compiler is on PATH the harnesses self-report "SKIP" and exit 0; this
wrapper turns that into a unittest skip so the gate stays green on clang-less
machines instead of silently passing a no-op.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from tests import _paths

_HERE = os.path.dirname(os.path.abspath(__file__))
_NATIVE_DIR = os.path.join(_paths.SCRIPTS, "mpynode", "native", "tests")

# Generous ceiling: the compile-heavy harnesses run ~20s each locally; a large
# multiple guards against a hung clang without letting a real hang wedge the gate.
_TIMEOUT_S = 600


def _have_cxx() -> bool:
    return bool(shutil.which("clang++") or shutil.which("g++"))


def _run_harness(test_case, filename, success_markers, needs_cxx=True):
    """Subprocess a native harness under this interpreter; assert success.

    success_markers: strings, ANY of which in stdout (with exit 0) means pass.
    needs_cxx: False for the pure-numpy / golden-file harnesses that never
    invoke a compiler, so they still gate on clang-less machines.
    """
    if needs_cxx and not _have_cxx():
        test_case.skipTest("no C++ compiler (clang++/g++) on PATH")

    path = os.path.join(_NATIVE_DIR, filename)
    if not os.path.isfile(path):
        test_case.fail("native harness missing: %s" % path)

    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        test_case.fail("%s timed out after %ds" % (filename, _TIMEOUT_S))

    out = (proc.stdout or "") + (proc.stderr or "")
    tail = out[-3000:]

    # A harness may self-skip (no compiler) even though we found one above (e.g.
    # a different PATH in the child); honour that as a skip, not a failure.
    if proc.returncode == 0 and "SKIP:" in out and not any(
            m in out for m in success_markers):
        test_case.skipTest("%s self-skipped: %s" % (filename, tail.strip()))

    test_case.assertEqual(
        proc.returncode, 0,
        "%s exited %d\n----- output tail -----\n%s"
        % (filename, proc.returncode, tail))
    test_case.assertTrue(
        any(m in out for m in success_markers),
        "%s exited 0 but printed no success marker %r\n"
        "----- output tail -----\n%s" % (filename, success_markers, tail))


class TestNativeTranspilerHarnesses(unittest.TestCase):
    def test_nd_runtime_parity(self):
        _run_harness(self, "nd_runtime_test.py", ("ALL PASS",))

    def test_nd_rng_bit_exact(self):
        _run_harness(self, "nd_rng_test.py", ("ALL BIT-EXACT",))

    # Integer //0, %0, INT64_MIN//-1 and NaN min/max. The gated fixtures use
    # only benign divisors (py_to_cpp_test floordiv_mod_array b=3,
    # nd_runtime_test floordiv_mod_neg b=+/-3), so without this line the guards
    # at nd_runtime.h:329-356 could be deleted with nothing going red.
    def test_nd_int_nan_edges(self):
        _run_harness(self, "nd_intnan_test.py", ("ALL PASS",))

    def test_py_to_cpp_parity(self):
        _run_harness(self, "py_to_cpp_test.py", ("ALL PASS",))

    def test_nd_lower_parity(self):
        _run_harness(self, "nd_lower_test.py", ("ALL PASS",))

    def test_metaballs_glue_parity(self):
        _run_harness(self, "metaballs_glue_parity.py",
                     ("METABALLS GLUE PARITY OK",), needs_cxx=False)

    def test_sdf_dmc_parity(self):
        _run_harness(self, "sdf_dmc_parity.py", ("PARITY OK",), needs_cxx=False)

    # The four below are unittest modules, so their success marker is the
    # unittest runner's own trailing "OK" line.
    def test_native_side_effect_noop(self):
        _run_harness(self, "native_side_effect_noop_test.py", ("\nOK",),
                     needs_cxx=False)

    def test_twist_swing_lowering(self):
        _run_harness(self, "twist_swing_lowering_test.py", ("\nOK",))

    def test_twist_swing_dual_lowering(self):
        _run_harness(self, "twist_swing_dual_lowering_test.py", ("\nOK",),
                     needs_cxx=False)

    def test_twist_swing_dual_parity(self):
        _run_harness(self, "twist_swing_dual_parity_test.py", ("\nOK",))


class TestHarnessCleansUpItsBinary(unittest.TestCase):
    """Every harness that builds INTO its own source directory must clean up.

    The removal used to be a trailing statement, reached only when the binary
    ran clean, so the one shape that matters -- a RED run -- stranded the
    executable in the source tree. It is a ``finally`` now; nothing else in the
    suite notices if that ``finally`` goes away, because every gated run is
    green and a green run cleans up either way. This drives the RED shape for
    all three in-tree builders. (py_to_cpp_test / nd_lower_test build into a
    tempdir, so they cannot strand anything and are not listed.)
    """

    # (harness module, .cpp it compiles, binary it drops next to itself)
    _IN_TREE_BUILDERS = (
        ("nd_runtime_test.py", "nd_runtime_test.cpp", "_nd_test.bin"),
        ("nd_rng_test.py", "nd_rng_test.cpp", "_nd_rng.bin"),
        ("nd_intnan_test.py", "nd_intnan_test.cpp", "_nd_intnan_test.bin"),
    )

    def test_a_failing_run_leaves_no_binary_behind(self):
        if not _have_cxx():
            self.skipTest("no C++ compiler (clang++/g++) on PATH")
        for mod, cpp, binary in self._IN_TREE_BUILDERS:
            with self.subTest(harness=mod):
                self._assert_red_run_is_clean(mod, cpp, binary)

    def _assert_red_run_is_clean(self, mod, cpp, binary):
        harness = os.path.join(_NATIVE_DIR, mod)
        if not os.path.isfile(harness):
            self.fail("native harness missing: %s" % harness)

        with tempfile.TemporaryDirectory() as tmp:
            # Repo-shaped: the harness derives HERE from its own location and
            # -I from HERE/../compiler, so it runs verbatim -- no patching.
            tests_dir = os.path.join(tmp, "tests")
            os.makedirs(tests_dir)
            os.makedirs(os.path.join(tmp, "compiler"))
            shutil.copy(harness, tests_dir)
            # Compiles clean, exits nonzero: the binary EXISTS when the harness
            # bails. A stub that failed to compile would leave nothing behind
            # no matter what, i.e. it would test nothing.
            with open(os.path.join(tests_dir, cpp), "w") as fh:
                fh.write("int main() { return 3; }\n")

            proc = subprocess.run(
                [sys.executable, os.path.join(tests_dir, mod)],
                capture_output=True, text=True, timeout=_TIMEOUT_S,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            self.assertEqual(proc.returncode, 1,
                             "stub harness should have gone RED\n" + out[-3000:])
            # Non-vacuity: this line is only printed after the compiled binary
            # was executed, so the file asserted on below really was created.
            self.assertIn("RUN FAILED", out,
                          "harness did not reach the run-failure path\n"
                          + out[-3000:])
            self.assertFalse(
                os.path.exists(os.path.join(tests_dir, binary)),
                "%s survived a RED run -- the cleanup in "
                "%s._compile_and_run is no longer a finally, so a failing run "
                "strands the executable in native/tests/" % (binary, mod[:-3]))


if __name__ == "__main__":
    unittest.main()
