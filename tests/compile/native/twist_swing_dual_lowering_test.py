"""The plug-promoted two-weight-set twist/swing compute LOWERS to pure C++.

This is the crux of the plug-promotion design: the two painted weight sets are
declared ``double is_array=True`` input plugs (flattened ``N*J``), the compute
reshapes each to ``(N, J)`` and calls the blessed ``twist_swing_dual`` transpile
method, and the interactive paint machinery is a bare ``self.sync_paint(mode)``
NativeSideEffect statement that lowers to nothing. If this lowers, the compiled
node reads its own per-node weight plugs (per-instance + persistent) and the
deform is a pure function of them -- the byte-parity path.
"""
import unittest

from mpynode.native.compiler import nd_lower
# Verify the ACTUAL shipped Compute string (SSOT), not a copy, so the template and
# the compiler can never drift.
from mpynode._demos.twist_swing_skin_source import COMPUTE as _DUAL_COMPUTE

_INS = [
    {"plug": "twistWeights", "member": "twistWeights",
     "meta": {"type": "double", "is_array": True}},
    {"plug": "swingWeights", "member": "swingWeights",
     "meta": {"type": "double", "is_array": True}},
    {"plug": "skinMode", "member": "skinMode", "meta": {"type": "enum"}},
    {"plug": "twistAxis", "member": "twistAxis", "meta": {"type": "enum"}},
]


class TestTwistSwingDualLowering(unittest.TestCase):
    def test_dual_plug_compute_lowers(self):
        spec = {"mpy_type": "mPySkinCluster", "init": "import numpy as np\n",
                "compute": _DUAL_COMPUTE}
        body = nd_lower.lower_deform(_INS, spec, "MPxSkinCluster")
        self.assertTrue(body)
        j = "\n".join(body)
        # the interactive paint call lowers to nothing.
        self.assertNotIn("sync_paint", j)
        # the two weight-set plugs materialise as 1-D arrays.
        self.assertIn("in_twistWeights", j)
        self.assertIn("in_swingWeights", j)
        # the blessed twist_swing_dual math lowers to its transpiled helper.
        self.assertIn("twist_swing_dual", j)


if __name__ == "__main__":
    unittest.main()
