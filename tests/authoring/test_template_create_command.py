"""_TemplateCreateCommand: the gallery "Create + Run setup" path (Design #2 §2).

Two paths:
  * seed-only / unwired = _ImportNodeCommand(payload, restore_persistent=False,
    seed_setup=True) (unchanged import path).
  * Create + Run setup = _TemplateCreateCommand(payload, native_type,
    run_setup=True): snapshot selection BEFORE create, import the template
    (applying its methods_source if present), seed the type default only if
    the template carried none, then run the node's own setup against
    [selection minus self]. The §6.1 rework: setup runs AFTER the payload is
    applied, so a template's own setup wins over the type default.
"""

import unittest

import maya.cmds as mc
from maya import cmds

from tests._setup import ensure_plugins_loaded, standalone_init
from mpynode._base.commands import (
    _ImportNodeCommand, _TemplateCreateCommand, run_undoable)
from mpynode._common.io.mpn_io import serialize_node
from mpynode._node_registry import get_spec, wrap_node


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _deformer_template_payload():
    """A definitions-only mPyDeformer payload (no methods_source), like a
    bundled template: build a bare node, serialize without persistent data."""
    cls     = get_spec("mPyDeformer").get_wrapper_class()
    n       = cls.build()                       # bare, unwired
    payload = serialize_node(n, include_persistent=False)
    mc.delete(n.get_name())              # source node gone; payload is standalone
    return payload


class TestTemplateCreateCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_create_seed_only_is_not_wired(self):
        payload = _deformer_template_payload()
        mesh    = mc.polyCube()[0]
        mc.select(mesh)
        # seed-only path = _ImportNodeCommand(seed_setup=True), NOT _TemplateCreateCommand
        cmd  = _ImportNodeCommand(payload, restore_persistent=False, seed_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        node = wrap_node(name, "mPyDeformer")
        self.assertIn("def setup(self", node.get_methods_source() or "")
        # NOT wired into the mesh's deformation chain
        self.assertFalse(cmds.deformer(name, q=True, g=True) or [])

    def test_create_and_run_setup_wires(self):
        payload = _deformer_template_payload()
        mesh    = mc.polyCube()[0]
        mc.select(mesh)
        cmd  = _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        self.assertTrue(cmds.deformer(name, q=True, g=True))

    def test_snapshot_excludes_self(self):
        payload = _deformer_template_payload()
        mesh    = mc.polyCube()[0]
        cmd     = _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True)
        name    = run_undoable(cmd) or cmd.created_name
        # node never wired to itself (authored setup excludes self; the created
        # node was not in the snapshot anyway since it didn't exist pre-create)
        geo = cmds.deformer(name, q=True, g=True) or []
        self.assertNotIn(name, geo)

    def test_undo_removes_node_and_wiring(self):
        payload = _deformer_template_payload()
        mesh    = mc.polyCube()[0]
        mc.select(mesh)
        cmd  = _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        self.assertTrue(mc.objExists(name))
        mc.undo()
        self.assertFalse(mc.objExists(name))

    def test_setup_failure_recorded_in_tier_failures(self):
        # P0-6: when the template's setup raises, the failure must be RECORDED
        # on the command (not only written to stderr) so the gallery UI can
        # surface it. The node is still created (built-but-unwired).
        payload = _deformer_template_payload()
        payload["methods_source"] = (
            "def setup(self, selection=None):\n"
            "    raise RuntimeError('boom-setup')\n")
        cmd  = _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        self.assertTrue(mc.objExists(name))            # node still created
        self.assertIn("setup", cmd.tier_failures)
        self.assertIn("boom-setup", cmd.tier_failures["setup"])

    def test_template_setup_wins_over_type_default(self):
        # §6.1 order: a template that ships its OWN methods_source setup must
        # run the TEMPLATE setup, not the type default. Inject a sentinel setup
        # that tags the node, and assert the tag is present (template ran) AND
        # _seed_setup_source did NOT replace it (merge-not-replace).
        payload = _deformer_template_payload()
        payload["methods_source"] = (
            "def setup(self, selection=None):\n"
            "    self.add_variable('TEMPLATE_RAN', True, persistent=True)\n")
        cmd  = _TemplateCreateCommand(payload, "mPyDeformer", run_setup=True)
        name = run_undoable(cmd) or cmd.created_name
        node = wrap_node(name, "mPyDeformer")
        # the template's custom setup survived (type default did NOT overwrite it)
        self.assertIn("TEMPLATE_RAN", node.get_methods_source() or "")
        self.assertEqual(node.get_variables().get("TEMPLATE_RAN"), True)


if __name__ == "__main__":
    unittest.main()
