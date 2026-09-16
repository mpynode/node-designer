"""mPySkinCluster shipped default sources (Init + linear-blend-skinning Compute).

Pure-string / parse-level checks -- no Maya needed. The runtime deform behavior
is proven by the demo test (_demos/build_mPySkinCluster_customLBS.py); here we
pin the shape of the starter code the Designer seeds.
"""
import unittest

from mpynode._defaults import skin_cluster_defaults as scd


class TestSkinClusterInitDefault(unittest.TestCase):
    def test_init_imports_numpy(self):
        # np is NOT auto-injected into Compute; the Init namespace is merged into
        # Compute globals, so the import must ship in Init.
        self.assertIn("import numpy as np", scd.DEFAULT_INIT_SOURCE)

    def test_init_compiles(self):
        compile(scd.DEFAULT_INIT_SOURCE, "<skin_init>", "exec")


class TestSkinClusterComputeDefault(unittest.TestCase):
    def test_compute_is_seeded(self):
        self.assertTrue(scd.DEFAULT_COMPUTE_SOURCE.strip())

    def test_compute_reads_the_live_plug_tree(self):
        src = scd.DEFAULT_COMPUTE_SOURCE
        for name in ("self.outputGeometry[0]", "self.weightList",
                     "self.matrix", "self.bindPreMatrix", "self.envelope"):
            self.assertIn(name, src)

    def test_compute_calls_blessed_lbs_method(self):
        src = scd.DEFAULT_COMPUTE_SOURCE
        # The LBS math is the SSOT blessed method (skin_blend.py); the default
        # CALLS it with the node's plugs passed EXPLICITLY (no inline math /
        # einsum here -- that lives in the free fn the method delegates to), then
        # commits via setPoints.
        self.assertIn(
            "self.linear_blend(rest, self.weightList, self.matrix, "
            "self.bindPreMatrix)", src)
        self.assertIn(".setPoints(", src)
        # The plug reads are visible at the call site, not hidden in the method.
        self.assertNotIn("np.einsum", src)

    def test_compute_uses_no_python_densify_loop(self):
        # The old sparse dict/loop densify did NOT lower; the vectorized rewrite
        # must not reintroduce it (guards the compiled path).
        src = scd.DEFAULT_COMPUTE_SOURCE
        self.assertNotIn("np.zeros", src)
        self.assertNotIn("np.stack", src)
        self.assertNotIn("for ",     src)

    def test_compute_compiles_with_no_toplevel_return(self):
        # exec-mode compile raises SyntaxError on a top-level `return`; a clean
        # compile proves the empty-weights early-out uses if/else, not `return`.
        compile(scd.DEFAULT_COMPUTE_SOURCE, "<skin_compute>", "exec")
        self.assertNotIn("\nreturn", "\n" + scd.DEFAULT_COMPUTE_SOURCE)


if __name__ == "__main__":
    unittest.main()
