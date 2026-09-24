"""Deterministic native lowering of the Spine template (``MPyNode/Spine``).

Spine builds and samples its own B-spline -- no Maya curve -- so its whole
compute (arc-length table, Hermite + Newton inversion, driver blends, the
per-sample frame and euler) must lower through Stage 1 to pure C++ with NO
AI-porter region. An edit that trips an unsupported construct (``atan2``, a
batched ``np.cross``, a tuple return, a non-literal range step...) would
otherwise fall back to a PORT region silently and cost an AI port at the next
build. This pins it, plus the three companion commands the compile carries.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_MPN = os.path.join(os.environ["MPYNODE_ROOT"], "templates", "MPyNode", "Spine",
                    "template.mpn")


class TestSpineLowering(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from mpynode._common.io.mpn_io import load_mpn
        from mpynode.native.compiler import node_scaffold
        from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload

        cls.spec = spec_from_mpn_payload(load_mpn(_MPN, trusted=False))
        cls.cpp  = node_scaffold.generate_cpp(cls.spec, for_port=True)

    def test_compute_lowers_deterministically(self):
        from mpynode.native.compiler import nd_lower, node_scaffold

        members = node_scaffold._members(self.spec)
        body = nd_lower.lower_compute(
            [m for m in members if m["kind"] == "inputs"],
            [m for m in members if m["kind"] == "outputs"],
            self.spec["compute"],
            nd_lower._combined_helper_source(self.spec),
            spec=self.spec)
        self.assertTrue(body, "Spine compute lowered to nothing")

    def test_no_port_region(self):
        self.assertNotIn("BEGIN PORTED COMPUTE", self.cpp,
                         "Spine fell back to an AI-port region")

    def test_no_maya_curve(self):
        self.assertNotIn("MFnNurbsCurve", self.cpp)
        self.assertNotIn("inputCurve", self.cpp)

    def test_companion_commands_registered(self):
        for cmd in ("spineBuildSystem", "spineResetRest", "spineSetDrivers"):
            self.assertIn('plugin.registerCommand("%s"' % cmd, self.cpp)


if __name__ == "__main__":
    unittest.main()
