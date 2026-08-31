"""Flagship acceptance: the Game of Life mPyMesh template compiles to a pure-C++
native plugin end-to-end.

This is priority ONE of the transpiler work ("figure out how to compile the game
of life mpymesh example"). It exercises the REAL production path -- NOT the
Maya-free nd_lower harness -- so it proves the whole chain that ships:

    templates/MPyMesh/Game Of Life/template.mpn
      -> mpn_io.load_mpn                 (real .mpn payload)
      -> mpn_spec_adapter                (payload -> porter spec)
      -> codegen.generate_cpp            (spec -> full MPxNode C++)
      -> clang++ -c against Maya devkit  (the translation unit typechecks)

Two invariants beyond "it compiles" are locked here because they are the whole
point of the HARD RULE (compiled compute must be PURE C++, never Python):

  * the compute LOWERS DETERMINISTICALLY -- no AI-porter PORT region -- so there
    is no embedded interpreter/fallback, and
  * the three recursion-free INIT helpers (``_gol_seed`` / ``_gol_step`` /
    ``_gol_board``) are transpiled to inline C++ lambdas (SP-5 part b), and the
    ``np.random.RandomState`` seed maps to the bit-exact ``nd::MT19937`` so the
    native board is byte-identical to the Python node's board.

The compile test SKIPs (never fails) on a host with no C++ compiler or no Maya
devkit headers, so the suite stays green off the build machine; the dual-Maya
gate host has both, so it runs there.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ._setup import standalone_init


def setUpModule():
    standalone_init()


_REL = "MPyMesh/Game Of Life"


def _gol_spec():
    """Load the shipped GoL mesh template.mpn and adapt it to a porter spec."""
    from mpynode._common.io import mpn_io
    from mpynode.native.spec import mpn_spec_adapter

    path = os.path.join(os.environ["MPYNODE_ROOT"], "templates",
                        *_REL.split("/"), "template.mpn")
    payload = mpn_io.load_mpn(path, trusted=True)
    return mpn_spec_adapter.spec_from_mpn_payload(payload)


def _running_maya_root():
    """The install root of the mayapy running this test (the dir that holds
    ``include/maya``). Climb from MAYA_LOCATION / sys.executable until the devkit
    headers are found; None if this build has no devkit."""
    import sys
    from mpynode.native.toolchain import toolchain

    seeds = [os.environ.get("MAYA_LOCATION") or "",
             os.path.dirname(os.path.abspath(sys.executable))]
    for seed in seeds:
        cur = seed
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(toolchain.maya_include_dir(cur), "maya")):
                return cur
            cur = os.path.dirname(cur)
    return None


class TestGolMeshLowersToPureCpp(unittest.TestCase):
    """Maya-free structural invariants (no compiler needed): the flagship node
    classifies as a geo mesh, fully lowers to deterministic C++, and carries the
    inline init helpers + bit-exact RNG."""

    def setUp(self):
        self.spec = _gol_spec()

    def test_template_is_a_mesh_generator(self):
        from mpynode.native import compiler as codegen

        self.assertEqual(self.spec.get("mpy_type"), "mPyMesh")
        self.assertEqual(codegen._geo_kind(self.spec), "mesh")
        self.assertTrue(self.spec.get("portability", {}).get("portable"),
                        self.spec.get("portability"))

    def test_compute_lowers_fully_no_ai_port(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import nd_lower

        in_members = [m for m in codegen._members(self.spec)
                      if m["kind"] == "inputs"]
        lowered = nd_lower.try_lower_geo_compute(in_members, "mesh", self.spec)
        self.assertIsNotNone(
            lowered, "GoL mesh compute must lower deterministically (pure C++); "
                     "None means it fell back to the AI porter")
        self.assertTrue(lowered)

    def test_generated_cpp_has_no_port_region(self):
        # The HARD RULE: a shipped native compute is PURE C++ with no AI PORT
        # region (no embedded interpreter/fallback).
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self.spec, for_port=True)
        self.assertNotIn(codegen.PORT_BEGIN, cpp)

    def test_init_helpers_become_inline_lambdas(self):
        # SP-5 part (b): the recursion-free init defs are monomorphized to inline
        # C++ lambdas emitted before the compute body.
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self.spec, for_port=True)
        for helper in ("_gol_seed", "_gol_step", "_gol_board"):
            self.assertIn("auto _h_%s" % helper, cpp,
                          "init helper %r must be a transpiled lambda" % helper)

    def test_randomstate_maps_to_bit_exact_mt19937(self):
        # RandomState(seed) lowers to nd::MT19937 (bit-exact numpy legacy RNG),
        # so the native board matches the Python board -- parity is CHECKED, not
        # skipped (unlike a bare np.random.random on the AI-porter path).
        from mpynode.native import compiler as codegen

        cpp = codegen.generate_cpp(self.spec, for_port=True)
        self.assertIn("nd::MT19937", cpp)


class TestGolMeshCompilesNative(unittest.TestCase):
    """The real payoff: the full generated translation unit compiles against the
    running mayapy's Maya devkit headers. SKIP (not fail) with no compiler/devkit
    so the suite stays green off the build host."""

    def test_generated_plugin_compiles_clean(self):
        from mpynode.native.toolchain import toolchain
        from mpynode.native import compiler as codegen

        cxx = shutil.which("clang++") or shutil.which("g++")
        if not cxx:
            self.skipTest("no C++ compiler on PATH")
        maya = _running_maya_root()
        if not maya:
            self.skipTest("no Maya devkit headers for the running mayapy")

        spec = _gol_spec()
        cpp = codegen.generate_cpp(spec, for_port=True)
        inc = toolchain.maya_include_dir(maya)
        native_dir = os.path.join(os.environ["MPYNODE_ROOT"], "scripts",
                                  "mpynode", "native")

        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, spec["suggested"]["node_type_name"] + ".cpp")
            with open(src, "w") as fh:
                fh.write(cpp)
            obj = os.path.join(d, "gol.o")
            cmd = [cxx, "-std=c++17", "-O2", "-c", src, "-o", obj,
                   "-I", inc, "-I", native_dir]
            md = toolchain.maya_define()
            if md:
                cmd += ["-D" + md]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0,
                             "GoL native compile failed:\n" + proc.stderr[-4000:])
            self.assertTrue(os.path.isfile(obj) and os.path.getsize(obj) > 0)


if __name__ == "__main__":
    unittest.main()
