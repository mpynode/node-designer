"""Every New-node create seeds the per-type setup source onto the node.

Design-final 4.2: EVERY built node carries its setup source on
``_methodsSource`` (seeded merge-not-replace) so the Methods tab shows it
and right-click "Run setup" works. Before the fix only the auto-setup path
(_SetupNodeCommand -> MPyNode.build) seeded; the plain "New" path
(build_new_node_command -> _ImportNodeCommand / _CreateNodeCommand) did not,
so a template/vanilla/headers-created node had an EMPTY Methods tab and
"Run setup" on it raised SetupError.

The regression guard proves general .mpn import (default seed_setup=False)
does NOT inject a setup that the payload didn't carry.
"""

import unittest

import maya.cmds as mc
from maya import cmds

from tests._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import (
    _ImportNodeCommand, _RunSetupCommand, build_new_node_command, run_undoable)
from mpynode._node_registry import get_spec, wrap_node
from mpynode._common.io.mpn_io import serialize_node


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestNewNodeSeedsSetup(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def _create(self, native_type, mode):
        cmd  = build_new_node_command(native_type, mode)
        name = run_undoable(cmd) or cmd.created_name
        return name

    def test_template_seed_only_seeds_setup_into_methods(self):
        # seed-only template create = _ImportNodeCommand(seed_setup=True);
        # mode="template" is retired. The seeded type-default setup is present.
        cls     = get_spec("mPyDeformer").get_wrapper_class()
        n       = cls.build()
        payload = serialize_node(n, include_persistent=False)
        mc.delete(n.get_name())
        cmd  = _ImportNodeCommand(payload, restore_persistent=False, seed_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        node = wrap_node(name, "mPyDeformer")
        self.assertIn("def setup(self", node.get_methods_source() or "")

    def test_vanilla_create_seeds_setup(self):
        name = self._create("mPyDeformer", "none")
        node = wrap_node(name, "mPyDeformer")
        self.assertIn("def setup(self", node.get_methods_source() or "")

    def test_headers_create_seeds_setup(self):
        name = self._create("mPyDeformer", "headers")
        node = wrap_node(name, "mPyDeformer")
        self.assertIn("def setup(self", node.get_methods_source() or "")

    def test_seeded_setup_has_exactly_one_def(self):
        # The template carries no methods_source, so exactly one setup appears
        # (no double-seed: deserialize applies none, seed_setup adds the type
        # default once).
        cls     = get_spec("mPyDeformer").get_wrapper_class()
        n       = cls.build()
        payload = serialize_node(n, include_persistent=False)
        mc.delete(n.get_name())
        cmd  = _ImportNodeCommand(payload, restore_persistent=False, seed_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        node = wrap_node(name, "mPyDeformer")
        src  = node.get_methods_source() or ""
        self.assertEqual(src.count("def setup(self"), 1)

    def test_template_mode_is_retired_returns_create_command(self):
        # mode="template" is retired -> treated like any other mode: bare seeded
        # create, never an _ImportNodeCommand from a bundled template. Compare by
        # class NAME (not isinstance) so a duplicate-module import of this package
        # under the test harness can't trigger a spurious class-identity mismatch.
        cmd = build_new_node_command("mPyDeformer", "template")
        self.assertEqual(type(cmd).__name__, "_CreateNodeCommand")

    def test_run_setup_works_on_plain_created_node(self):
        # SECONDARY latent bug: a plain (non-auto-setup) New node must carry a
        # seeded setup so "Run setup" against the selection wires it.
        mesh = mc.polyCube()[0]
        name = self._create("mPyDeformer", "none")
        mc.select(mesh)
        run_undoable(_RunSetupCommand(name, "mPyDeformer"))
        self.assertTrue(cmds.deformer(name, q=True, g=True))

    def test_general_import_does_not_inject_setup(self):
        # REGRESSION GUARD: the general-import call shape
        # (_ImportNodeCommand(payload), default seed_setup=False) must NOT
        # inject a setup the payload didn't already carry.
        from mpynode._common.io.mpn_io import serialize_node
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create()
        # bare mPyNode: no authored setup source, and mPyNode has no type
        # default setup either -> payload carries no setup.
        payload = serialize_node(n)
        self.assertNotIn("def setup(self", payload.get("methods_source") or "")

        cmd      = _ImportNodeCommand(payload)  # DEFAULT seed_setup=False
        name     = run_undoable(cmd) or cmd.created_name
        imported = wrap_node(name, "mPyNode")
        self.assertNotIn("def setup(self", imported.get_methods_source() or "")


if __name__ == "__main__":
    unittest.main()
