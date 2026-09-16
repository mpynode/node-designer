"""LLM assistant tools must seed the per-type setup source on creation.

The AI/LLM assistant tools (create_node / define_node) create nodes via the
TOOL dispatch path. Previously they called the RAW primitive cls.create(),
which returns a bare, inert, UNSEEDED node -- so AI-created nodes never carried
their per-type ``def setup(self)`` on ``_methodsSource`` (unlike the UI command
path which goes through MPyNode.build()).

The fix routes both tools through cls.build() (WITHOUT setup=True): build()
ALWAYS seeds the methods source (merge-not-replace) but only runs setup(self)
when setup=True. So AI nodes get the seeded setup source but setup(self) is
NOT run (an AI agent must not run scene-mutating setup against whatever is
ambiently selected).

These tests drive the PUBLIC tool entry (T.dispatch) -- the same way real
code invokes the tools -- and were RED before the fix because create() does
not seed.
"""

import unittest

import maya.cmds as mc
from maya import cmds

from tests._setup import ensure_plugins_loaded, standalone_init
from mpynode._common import node_setups
from mpynode._node_registry import wrap_node


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestLLMToolsSeedSetup(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.ui.llm import tools as T
        self.T = T

    def _create_node(self, node_type, name=None):
        ctx  = self.T.ToolContext()
        args = {"node_type": node_type}
        if name:
            args["name"] = name
        res = self.T.dispatch("create_node", args, ctx)
        self.assertNotIn("error", res, "create_node errored: %r" % res)
        return res["created"]

    def _define_node(self, node_type):
        ctx = self.T.ToolContext()
        res = self.T.dispatch("define_node", {"node_type": node_type}, ctx)
        self.assertNotIn("error", res, "define_node errored: %r" % res)
        # define_node returns the node name under "node" (or in its schema).
        node = res.get("node") or res.get("created")
        if not node:
            node = ctx.working_node
        return node

    def test_create_node_seeds_setup_for_setup_type(self):
        name = self._create_node("mPyDeformer")
        node = wrap_node(name, "mPyDeformer")
        self.assertIn("def setup(self", node.get_methods_source() or "")

    def test_create_node_no_setup_injected_for_plain_type(self):
        # mPyNode has no authored type-default setup -> nothing injected.
        name = self._create_node("mPyNode")
        node = wrap_node(name, "mPyNode")
        self.assertIsNone(
            node_setups.find_setup(node.get_methods_source() or ""))

    def test_create_node_does_not_run_setup(self):
        # Seed-only: setup(self) must NOT run, so the new deformer is NOT wired
        # to the selected mesh.
        mesh = mc.polyCube()[0]
        mc.select(mesh)
        name = self._create_node("mPyDeformer")
        try:
            wired = cmds.deformer(name, q=True, g=True)
        except Exception:
            wired = None
        self.assertFalse(wired, "setup(self) ran -- node wired to mesh: %r" % wired)

    def test_define_node_seeds_setup(self):
        name = self._define_node("mPyDeformer")
        node = wrap_node(name, "mPyDeformer")
        self.assertIn("def setup(self", node.get_methods_source() or "")


if __name__ == "__main__":
    unittest.main()
