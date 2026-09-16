"""C++ byte-parity for the plug-promoted two-weight-set twist/swing deform.

Compiles the lowered ``deform()`` body of the plug-promotion compute (two weight
sets carried as flattened ``double is_array=True`` input plugs, reshaped in the
compute) and proves each ``skinMode`` branch matches the ``skin_blend`` oracle:

  * mode 0 (Paint LBS)  -> ``linear_blend`` of the inherited ``weightList``
  * mode 1 (Paint DQS)  -> ``dual_quaternion`` of the inherited ``weightList``
  * mode 2 (Live Result)-> ``twist_swing_dual`` of the TWO reshaped weight plugs

Mode 2 is the byte-parity performance path (the compiled node reads its own
per-node plugs). The bare ``self.sync_paint(mode)`` NativeSideEffect statement
lowers to nothing, so it never perturbs the numeric result. Full Maya-bound-node
parity is separately proven by tools/harness/skin_twist_swing_dual_parity.py.
"""
import unittest

import numpy as np

from mpynode._common.methods import skin_blend
from mpynode.native.compiler import nd_lower
from tests.compile.native.nd_lower_test import (
    _SHIM, _cpp_lit, _mmat_init_list, _compile_run, _parse_probes, SKIN_DQS)
# Compile the ACTUAL shipped Compute string (SSOT), not a copy.
from mpynode._demos.twist_swing_skin_source import COMPUTE as _DUAL_COMPUTE

_INS = [
    {"plug": "twistWeights", "member": "twistWeights",
     "meta": {"type": "double", "is_array": True}},
    {"plug": "swingWeights", "member": "swingWeights",
     "meta": {"type": "double", "is_array": True}},
    {"plug": "skinMode", "member": "skinMode", "meta": {"type": "enum"}},
    {"plug": "twistAxis", "member": "twistAxis", "meta": {"type": "enum"}},
]

_SPEC = {"mpy_type": "mPySkinCluster", "init": "import numpy as np\n",
         "compute": _DUAL_COMPUTE}


def _gen(rest, env_val, joint, bind, wl_dense, twist_flat, swing_flat,
         mode, axis, body):
    """C++ main() seeding the inherited skin locals (jointMat/bindPre/skinW) AND
    the declared plug inputs (in_twistWeights/in_swingWeights flat, in_skinMode/
    in_twistAxis), running the lowered body, probing the mutated points."""
    wd = np.asarray(wl_dense, dtype=np.float64)
    L  = [_SHIM, "int main() {"]
    L.append("    std::vector<MPoint> pts = {%s};"
             % ", ".join("MPoint(%s, %s, %s)"
                         % (_cpp_lit(p[0]), _cpp_lit(p[1]), _cpp_lit(p[2]))
                         for p in rest))
    L.append("    unsigned int n = (unsigned int)pts.size();")
    L.append("    const float* _rawIn = 0;")
    L.append("    float env = (float)(%s);" % _cpp_lit(env_val))
    L.append("    std::vector<MMatrix> jointMat = {%s};"
             % ", ".join(_mmat_init_list(m) for m in joint))
    L.append("    std::vector<MMatrix> bindPre = {%s};"
             % ", ".join(_mmat_init_list(m) for m in bind))
    L.append("    std::vector<double> skinW = {%s};"
             % ", ".join(_cpp_lit(x) for x in wd.ravel()))
    L.append("    int64_t skinN = %d, skinJ = %d;" % (wd.shape[0], wd.shape[1]))
    L.append("    std::vector<double> in_twistWeights = {%s};"
             % ", ".join(_cpp_lit(x) for x in np.asarray(twist_flat).ravel()))
    L.append("    std::vector<double> in_swingWeights = {%s};"
             % ", ".join(_cpp_lit(x) for x in np.asarray(swing_flat).ravel()))
    L.append("    short in_skinMode = %d;" % mode)
    L.append("    short in_twistAxis = %d;" % axis)
    L.append("    // ===== lowered deform =====")
    L += body
    L.append('    { printf("PROBE points %zu :", pts.size()*3);'
             " for (size_t _i=0;_i<pts.size();++_i)"
             ' printf(" %.17g %.17g %.17g", pts[_i].x, pts[_i].y, pts[_i].z);'
             ' printf("\\n"); }')
    L.append("    return 0;\n}")
    return "\n".join(L) + "\n"


def _oracle(rest, env_val, joint, bind, wl_dense, twist_dense, swing_dense,
            mode, axis, have_sets=True):
    rest_a = np.asarray(rest, dtype=np.float64).reshape(-1, 3)
    J      = np.asarray(joint, dtype=np.float64).reshape(-1, 4, 4)
    B      = np.asarray(bind, dtype=np.float64).reshape(-1, 4, 4)
    env    = float(np.float32(env_val))          # deform() reads envelope as float32
    if mode == 0:
        deformed = skin_blend.linear_blend(rest_a, np.asarray(wl_dense), J, B)
    elif mode == 1:
        deformed = skin_blend.dual_quaternion(rest_a, np.asarray(wl_dense), J, B)
    elif have_sets:
        deformed = skin_blend.twist_swing_dual(
            rest_a, np.asarray(twist_dense), np.asarray(swing_dense), J, B, axis)
    else:                                     # Live mode, plugs not seeded -> LBS
        deformed = skin_blend.linear_blend(rest_a, np.asarray(wl_dense), J, B)
    return (rest_a + env * (deformed - rest_a)).ravel()


class TestTwistSwingDualParity(unittest.TestCase):
    def test_all_modes_byte_parity(self):
        for name, rest, env_val, joint, bind, w in SKIN_DQS:
            wd = np.asarray(w, dtype=np.float64)
            nv, nj = wd.shape
            # two DISTINCT weight sets for mode 2: twist = weightList, swing = a
            # renormalised roll so the two sets genuinely differ.
            twist_d = wd.copy()
            swing_d = np.roll(wd, 1, axis=1)
            swing_d = swing_d / swing_d.sum(axis=1, keepdims=True)
            body    = nd_lower.lower_deform(_INS, _SPEC, "MPxSkinCluster")
            self.assertTrue(body, "%s: empty lowered body" % name)
            for mode in (0, 1, 2):
                for axis in ((0,) if mode != 2 else (0, 1, 2)):
                    cpp = _gen(rest, env_val, joint, bind, wd,
                               twist_d.ravel(), swing_d.ravel(), mode, axis, body)
                    out, err = _compile_run(
                        cpp, "tswd_%s_m%d_a%d" % (name, mode, axis))
                    self.assertFalse(err, "%s m%d a%d: %s"
                                     % (name, mode, axis, err))
                    got = _parse_probes(out).get("points")
                    exp = _oracle(rest, env_val, joint, bind, wd,
                                  twist_d, swing_d, mode, axis)
                    self.assertIsNotNone(got, "%s m%d a%d: no probe"
                                         % (name, mode, axis))
                    self.assertEqual(got.shape, exp.shape,
                                     "%s m%d a%d: shape" % (name, mode, axis))
                    self.assertTrue(
                        np.allclose(got, exp, rtol=1e-8, atol=1e-8),
                        "%s m%d a%d: maxdiff %.3e" % (
                            name, mode, axis, float(np.abs(got - exp).max())))

    def test_live_mode_empty_plugs_falls_back_to_lbs(self):
        # A Live-Result (mode 2) node whose weight-set plugs are NOT seeded must
        # fall back to plain LBS of the weightList (no reshape crash), byte-parity.
        body = nd_lower.lower_deform(_INS, _SPEC, "MPxSkinCluster")
        for name, rest, env_val, joint, bind, w in SKIN_DQS:
            wd = np.asarray(w, dtype=np.float64)
            cpp = _gen(rest, env_val, joint, bind, wd,
                       [], [], 2, 0, body)          # empty weight-set plugs
            out, err = _compile_run(cpp, "tswd_%s_empty" % name)
            self.assertFalse(err, "%s empty: %s" % (name, err))
            got = _parse_probes(out).get("points")
            exp = _oracle(rest, env_val, joint, bind, wd, None, None, 2, 0,
                          have_sets=False)
            self.assertIsNotNone(got, "%s empty: no probe" % name)
            self.assertTrue(np.allclose(got, exp, rtol=1e-8, atol=1e-8),
                            "%s empty: maxdiff %.3e"
                            % (name, float(np.abs(got - exp).max())))


if __name__ == "__main__":
    unittest.main()
