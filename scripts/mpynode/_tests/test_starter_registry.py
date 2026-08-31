"""Per-type tier-starter registry + its wiring into the virgin-create seeder.

The registry supplies runnable default code for registered types (mPyFile,
mPySkinCluster); the empty-tier seeder consults it BEFORE the generic header, so
a Designer plain-left-click ("headers" mode) seeds working code for those types
while every other type keeps its header-only behavior and populated tiers are
never overwritten.
"""
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init
from mpynode._defaults import starter_registry as sr
from mpynode._defaults.starter_registry import (
    TIER_COMPUTE, TIER_INIT, TIER_VIEWPORT, TIER_OSL, starter_source)


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestStarterRegistryLookup(unittest.TestCase):
    def test_mpyfile_compute_is_blessed_passthrough(self):
        src = starter_source("mPyFile", TIER_COMPUTE)
        self.assertIsNotNone(src)
        self.assertIn("self.read_texture()", src)
        self.assertIn("self.sample_texture(", src)

    def test_mpyfile_has_init_and_viewport(self):
        self.assertIsNotNone(starter_source("mPyFile", TIER_INIT))
        self.assertIsNotNone(starter_source("mPyFile", TIER_VIEWPORT))

    def test_mpyskincluster_compute_is_lbs(self):
        # The LBS default is the blessed one-liner self.linear_blend(rest,
        # weights, joint, bind) with the node's plugs passed EXPLICITLY (SSOT
        # skin_blend.py), mirroring mPyFile's self.read_texture() passthrough.
        src = starter_source("mPySkinCluster", TIER_COMPUTE)
        self.assertIsNotNone(src)
        self.assertIn(
            "self.linear_blend(rest, self.weightList, self.matrix, "
            "self.bindPreMatrix)", src)

    def test_mpyskincluster_init_imports_numpy(self):
        src = starter_source("mPySkinCluster", TIER_INIT)
        self.assertIsNotNone(src)
        self.assertIn("import numpy as np", src)

    def test_mpyskincluster_has_no_viewport_or_osl_starter(self):
        self.assertIsNone(starter_source("mPySkinCluster", TIER_VIEWPORT))
        self.assertIsNone(starter_source("mPySkinCluster", TIER_OSL))

    def test_unknown_type_returns_none(self):
        self.assertIsNone(starter_source("mPyNode", TIER_COMPUTE))
        self.assertIsNone(starter_source("nonexistentType", TIER_COMPUTE))

    def test_unknown_tier_returns_none(self):
        self.assertIsNone(starter_source("mPyFile", "bogus_tier"))

    def test_registered_types(self):
        types = sr.registered_types()
        self.assertIn("mPyFile", types)
        self.assertIn("mPySkinCluster", types)

    def test_registry_is_single_source_of_truth_for_mpyfile(self):
        # The registry points at the same constant the wrapper create() seeds.
        from mpynode._defaults.file_defaults import DEFAULT_COMPUTE_SOURCE
        self.assertEqual(starter_source("mPyFile", TIER_COMPUTE),
                         DEFAULT_COMPUTE_SOURCE)


class TestSeederUsesStarter(unittest.TestCase):
    """Full Designer plain-create path (build_new_node_command, headers mode)."""

    def setUp(self):
        mc.file(new=True, force=True)

    def _create(self, native_type):
        from mpynode._base.commands import build_new_node_command, run_undoable
        cmd = build_new_node_command(native_type, "headers")
        return run_undoable(cmd) or cmd.created_name

    def test_skincluster_seeds_lbs_compute_and_numpy_init(self):
        from mpynode._node_registry import wrap_node
        name = self._create("mPySkinCluster")
        node = wrap_node(name, "mPySkinCluster")
        compute = node.get_compute_expression() or ""
        self.assertIn(
            "self.linear_blend(rest, self.weightList, self.matrix, "
            "self.bindPreMatrix)", compute)
        self.assertIn("import numpy as np", node.get_init_expression() or "")

    def test_mpyfile_seeds_blessed_compute(self):
        # Closes the plain-left-click gap: virgin create finally seeds working
        # file-texture code without relying on MPyFile.create().
        from mpynode._node_registry import wrap_node
        name = self._create("mPyFile")
        node = wrap_node(name, "mPyFile")
        self.assertIn("self.read_texture()", node.get_compute_expression() or "")

    def test_unregistered_type_gets_generic_header_not_starter(self):
        from mpynode._node_registry import wrap_node
        from mpynode._common.lifecycle.compute_header import make_compute_header
        name = self._create("mPyNode")
        node = wrap_node(name, "mPyNode")
        compute = node.get_compute_expression() or ""
        # No starter leaked into a non-registered type; it got the header verbatim.
        self.assertNotIn("self.weightList", compute)
        self.assertNotIn("self.read_texture()", compute)
        self.assertEqual(compute, make_compute_header("mPyNode"))

    def test_populated_tier_is_not_overwritten(self):
        # The empty-tier guard survives: a tier already carrying user text is
        # left untouched when the seeder runs.
        from mpynode._base.commands import _seed_headers
        from mpynode._node_registry import wrap_node
        name = mc.createNode("mPySkinCluster")
        node = wrap_node(name, "mPySkinCluster")
        custom = "# my custom code\nmesh = self.outputGeometry[0]\n"
        node.set_compute_expression(custom)
        _seed_headers(name, "mPySkinCluster")
        self.assertEqual(wrap_node(name, "mPySkinCluster").get_compute_expression(),
                         custom)


if __name__ == "__main__":
    unittest.main()
