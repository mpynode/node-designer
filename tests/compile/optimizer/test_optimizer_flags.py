"""The optimizer recompile MUST pass -ffp-contract=off (fused mul+add would
otherwise FMA-contract and drift ~1 ULP, breaking parity). The opt-in flag on
compile_to_plugin_cmd adds -O3 -ffp-contract=off on unix, leaves MSVC unchanged,
and is default-OFF so every existing caller's argv is byte-identical.

Pure argv-builder assertions -> no standalone Maya needed.
"""

from __future__ import annotations

import unittest
from unittest import mock

from mpynode.native.toolchain import toolchain
from mpynode.native.ai import porter


def _unix(**over):
    kw = dict(compiler="clang++", src="a.cpp", out_plugin="out.bundle",
              include_dir="/i", lib_dir="/l", libs=["OpenMaya"],
              os_name="darwin", arch="arm64")
    kw.update(over)
    return toolchain.compile_to_plugin_cmd(**kw)


class TestOptimizeFlag(unittest.TestCase):
    def test_optimize_adds_ffp_contract_off_and_o3_on_unix(self):
        cmd = _unix(optimize=True)
        self.assertIn("-ffp-contract=off", cmd)
        self.assertIn("-O3", cmd)
        self.assertNotIn("-O2", cmd)
        self.assertNotIn("-ffast-math", cmd)  # never, under any flag

    def test_default_is_o3_ffp_contract_off_unix(self):
        # QW2: -O3 -ffp-contract=off is now the DEFAULT on unix. contract=off is
        # MANDATORY for byte-parity (clang defaults to contract=on -> FMA -> ~1
        # ULP drift). The default now matches the optimize=True recipe.
        cmd = _unix()
        self.assertIn("-O3", cmd)
        self.assertIn("-ffp-contract=off", cmd)
        self.assertNotIn("-O2", cmd)
        self.assertNotIn("-ffast-math", cmd)

    def test_msvc_unchanged_by_optimize(self):
        base = toolchain.compile_to_plugin_cmd(
            "cl", "a.cpp", "out.mll", include_dir="/i", lib_dir="/l",
            libs=["OpenMaya"], os_name="windows", optimize=False)
        opt = toolchain.compile_to_plugin_cmd(
            "cl", "a.cpp", "out.mll", include_dir="/i", lib_dir="/l",
            libs=["OpenMaya"], os_name="windows", optimize=True)
        self.assertEqual(base, opt)  # MSVC parity path is unverified -> untouched
        self.assertNotIn("-ffp-contract=off", opt)


class TestPorterForwardsOptimize(unittest.TestCase):
    """porter.compile_cpp must forward the optimize flag into the argv builder so
    the optimizer's recompile actually gets -ffp-contract=off. Patch only the
    boundary calls (compiler resolution + argv build + subprocess) so no real
    compiler runs -- we assert the flag reaches compile_to_plugin_cmd."""

    _SPEC = {"suggested": {"node_type_name": "mPyTest", "mpx_base": "MPxNode"}}

    def _capture_optimize(self, **compile_kw):
        seen = {}

        def fake_cmd(*a, **k):
            seen["optimize"] = k.get("optimize")
            return ["clang++"]

        with mock.patch.object(toolchain, "resolve_compiler",
                               lambda *a, **k: "clang++"), \
             mock.patch.object(toolchain, "build_env", lambda *a, **k: None), \
             mock.patch.object(toolchain, "run_streaming",
                               lambda cmd, **k: (0, "ok")), \
             mock.patch.object(toolchain, "compile_to_plugin_cmd", fake_cmd):
            porter.compile_cpp("x.cpp", self._SPEC, "/tmp/out",
                               compiler="clang++", **compile_kw)
        return seen["optimize"]

    def test_forwards_optimize_true(self):
        self.assertTrue(self._capture_optimize(optimize=True))

    def test_defaults_optimize_false(self):
        self.assertFalse(self._capture_optimize())


if __name__ == "__main__":
    unittest.main()
