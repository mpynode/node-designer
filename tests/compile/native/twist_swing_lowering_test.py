"""Deterministic lowering of the TWIST/SWING skinCluster to pure C++.

``twist_swing`` is the first blessed ``Transpile`` free fn that calls its own
SIBLING module-level helpers (``_twist_matrix`` / ``_swing_matrix`` /
``dual_quaternion`` / ``linear_blend`` in ``skin_blend.py``). Those siblings must
resolve in the transpiler's helper pool (blessed_transpile.transpile_helper_sources
-> nd_lower._combined_helper_source), and the whole method must lower to pure C++
with NO AI porter (HARD RULE: a shipped default compiles deterministically or is
honest-rejected, never AI-ported).

These tests:
  * compile+run the lowered ``deform()`` for the ``self.twist_swing(...)`` method
    on rigid fixtures and prove it matches the ``skin_blend.twist_swing`` oracle;
  * prove the ``skinMode`` enum-branch template Compute (Linear / DualQuaternion /
    Twist-Swing) lowers deterministically (try_lower_deform is not None);
  * pin the helper-source registration that makes the sibling calls resolve.

Numeric byte-parity on a real bound arm across all three modes is separately
proven by tools/harness/skin_twist_swing_parity.py.
"""
import unittest

import numpy as np

from mpynode._common.methods import skin_blend
from mpynode.native.compiler import nd_lower, py_to_cpp
from mpynode.native.compiler.py_to_cpp import array_t, scalar_t
from mpynode.native.compiler.kernels import blessed_transpile

# Reuse the C++ compile+run harness and the rigid DQS fixtures (twist_swing
# needs rigid joints -- it extracts a rotation quaternion per influence).
from tests.compile.native.nd_lower_test import (
    _gen_skin_deform_cpp, _compile_run, _parse_probes, SKIN_DQS)

def _tsw_method(axis):
    """twist_swing deform method with an explicit literal twist axis (0=X/1=Y/2=Z)."""
    return (
        "mesh = self.outputGeometry[0]\n"
        "rest = mesh.getPoints()\n"
        "mesh.setPoints(rest + float(self.envelope) * (self.twist_swing("
        "rest, self.weightList, self.matrix, self.bindPreMatrix, %d) - rest))\n"
        % axis)


_SKIN_SPEC = {"mpy_type": "mPySkinCluster", "init": "import numpy as np\n"}

# The skinMode enum branch (all three algorithms in one Compute), stripped of the
# deform mesh I/O so it feeds transpile_compute_block directly (the real deform
# lowering rewrites mesh.getPoints/setPoints -- separately proven end-to-end by
# the compile + the 3-mode Maya parity harness).
_BRANCH_COMPUTE = (
    "mode = int(self.skinMode)\n"
    "if mode == 0:\n"
    "    deformed = self.linear_blend(rest, self.weightList, self.matrix, "
    "self.bindPreMatrix)\n"
    "elif mode == 1:\n"
    "    deformed = self.dual_quaternion(rest, self.weightList, self.matrix, "
    "self.bindPreMatrix)\n"
    "else:\n"
    "    deformed = self.twist_swing(rest, self.weightList, self.matrix, "
    "self.bindPreMatrix, int(self.twistAxis))\n"
    "self.result = deformed\n"
)
_BRANCH_SPEC = {"mpy_type": "mPySkinCluster", "compute": _BRANCH_COMPUTE}


def _tsw_oracle(rest, env_val, joint_mats, bind_mats, w_dense, twist_axis=0):
    rest_a = np.asarray(rest, dtype=np.float64).reshape(-1, 3)
    J = np.asarray(joint_mats, dtype=np.float64).reshape(-1, 4, 4)
    B = np.asarray(bind_mats, dtype=np.float64).reshape(-1, 4, 4)
    W = np.asarray(w_dense, dtype=np.float64)
    env = float(np.float32(env_val))   # deform() reads envelope as float32
    deformed = skin_blend.twist_swing(rest_a, W, J, B, twist_axis)
    return (rest_a + env * (deformed - rest_a)).ravel()


class TestTwistSwingDeterministicLowering(unittest.TestCase):
    def test_method_lowers_and_matches_oracle(self):
        # Compile + run the lowered twist_swing for ALL THREE twist axes
        # (X/Y/Z) and prove each matches its interpreted oracle -- the
        # scalar-coefficient axis selection lowers to pure C++ with byte-parity.
        for axis in (0, 1, 2):
            spec = dict(_SKIN_SPEC, compute=_tsw_method(axis))
            for name, rest, env_val, joint, bind, w in SKIN_DQS:
                body = nd_lower.lower_deform([], spec, "MPxSkinCluster")
                self.assertTrue(body, "axis %d %s: empty lowered body"
                                % (axis, name))
                cpp = _gen_skin_deform_cpp(rest, env_val, joint, bind, w, body)
                out, err = _compile_run(cpp, "tsw_a%d_%s" % (axis, name))
                self.assertFalse(err, "axis %d %s: %s" % (axis, name, err))
                got = _parse_probes(out).get("points")
                exp = _tsw_oracle(rest, env_val, joint, bind, w, axis)
                self.assertIsNotNone(got, "axis %d %s: no points probe"
                                     % (axis, name))
                self.assertEqual(got.shape, exp.shape,
                                 "axis %d %s: shape" % (axis, name))
                self.assertTrue(np.allclose(got, exp, rtol=1e-8, atol=1e-8),
                                "axis %d %s: maxdiff %.3e"
                                % (axis, name, float(np.abs(got - exp).max())))

    def test_mode_branch_transpiles_all_three(self):
        # The skinMode enum branch lowers deterministically through the REAL
        # shipped machinery (make_transpile_lowerings + transpile_helper_sources):
        # an if/elif/else that emits all three blessed methods as C++ helpers.
        blessed, blessed_unpack = blessed_transpile.make_transpile_lowerings(
            _BRANCH_SPEC)
        self.assertEqual(set(blessed),
                         {"linear_blend", "dual_quaternion", "twist_swing"})
        srcs = blessed_transpile.transpile_helper_sources(_BRANCH_SPEC)
        env = {"rest": array_t("double", 2),
               "self.weightList": array_t("double", 2),
               "self.matrix": array_t("double", 3),
               "self.bindPreMatrix": array_t("double", 3),
               "self.skinMode": scalar_t("int64"),
               "self.twistAxis": scalar_t("int64")}
        writers = {"self.result": lambda v: ["(void)(%s);" % v.code]}
        res, written, helper_lines = py_to_cpp.transpile_compute_block(
            _BRANCH_COMPUTE, dict(env), writers, srcs,
            blessed=blessed, blessed_unpack=blessed_unpack)
        body = "\n".join(res.body_lines)
        hl = "\n".join(helper_lines)
        self.assertIn("if (", body)
        self.assertIn("} else {", body)
        for h in ("_h_twist_swing", "_h_linear_blend", "_h_dual_quaternion"):
            self.assertIn(h, hl, "helper %r not emitted" % h)

    def test_helper_sources_register_sibling_defs(self):
        srcs = blessed_transpile.transpile_helper_sources(_BRANCH_SPEC)
        self.assertTrue(srcs, "no helper sources for a twist/swing spec")
        joined = "\n".join(srcs)
        for fn in ("def twist_swing", "def _twist_matrix", "def _swing_matrix",
                   "def dual_quaternion", "def linear_blend"):
            self.assertIn(fn, joined, "missing sibling %r in helper pool" % fn)

    def test_nonblessed_type_gets_no_helper_sources(self):
        # A non-blessed type (or a compute calling no blessed method) contributes
        # nothing -- every other node's helper pool is unchanged.
        self.assertEqual(
            blessed_transpile.transpile_helper_sources(
                {"mpy_type": "mPyNode", "compute": "self.x = 1\n"}), [])


if __name__ == "__main__":
    unittest.main()
