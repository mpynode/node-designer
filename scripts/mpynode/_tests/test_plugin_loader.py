"""Tests for ``mpynode._common.lifecycle.plugin_loader`` auto-load behaviour.

The README / API docs promise every wrapper's ``create`` / ``create_on``
auto-loads the plug-in that registers the node type, so copy-paste
examples work without a manual ``mc.loadPlugin``. That promise only holds
if every registered node type has an entry in
``plugin_loader._NODE_TYPE_TO_PLUGIN`` -- a missing entry makes
``ensure_loaded`` raise ``RuntimeError`` for that type.
"""
import unittest

from mpynode import _node_registry
from mpynode._common.lifecycle import plugin_loader


class TestPluginLoaderCoverage(unittest.TestCase):
    """Every registry node type must be auto-loadable."""

    def test_every_registry_type_has_a_plugin_mapping(self):
        registry_types = set(_node_registry.all_native_types())
        mapped_types = set(plugin_loader._NODE_TYPE_TO_PLUGIN)
        missing = sorted(registry_types - mapped_types)
        self.assertEqual(
            missing, [],
            "node types in the registry with no auto-load mapping "
            "(create() will raise RuntimeError in a fresh session): %s"
            % missing,
        )

    def test_mapped_plugins_are_known_filenames(self):
        # Guard against typos: every mapped plug-in is one of the two
        # real plug-in files.
        valid = {"mpynode_api1.py", "mpynode_api2.py"}
        for node_type, plugin in plugin_loader._NODE_TYPE_TO_PLUGIN.items():
            self.assertIn(
                plugin, valid,
                "%r maps to unexpected plug-in %r" % (node_type, plugin),
            )


class TestRegistryMatchesRegisteredNodeTypes(unittest.TestCase):
    """P1-2: the wrapper registry and the actually-registered Maya node types
    must agree once the plug-ins load -- catches drift in either direction (a
    registry entry with no registered node, or a registered ``mPy`` node type
    missing from the registry)."""

    def test_registry_equals_registered_mpy_types(self):
        import maya.cmds as mc

        from ._setup import ensure_plugins_loaded, standalone_init

        standalone_init()
        ensure_plugins_loaded()
        registry = set(_node_registry.all_native_types())
        # Ask the two plug-ins what THEY registered instead of scanning every
        # node type for an "mPy" prefix. A loaded compiled bundle contributes
        # types of its own and a template is free to be named mPy-anything
        # (the dnet template's compiled type is literally "mPyDnet") -- those
        # are not wrapper types and must not read as registry drift.
        registered = set()
        for plug in ("mpynode_api1", "mpynode_api2"):
            registered.update(
                t for t in (mc.pluginInfo(plug, q=True, dependNode=True) or [])
                if t.startswith("mPy")
            )
        self.assertEqual(
            registry, registered,
            "registry vs registered node-type drift: only-in-registry=%s "
            "only-registered=%s"
            % (sorted(registry - registered), sorted(registered - registry)),
        )


if __name__ == "__main__":
    unittest.main()
