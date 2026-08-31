"""Direct tests for the base ``MPyNode.build()`` classmethod.

These are characterization-style tests on already-built behavior: ``build()``
creates + populates a node (seeding the self-first ``setup`` onto
``_methodsSource``), and when ``setup=True`` snapshots the current selection
BEFORE create() then runs ``self.setup(selection=...)``, swallowing setup
errors (node left built-but-unwired).

Per the plan: do NOT add any one-undo assertion to a bare ``cls.build()`` call
-- ``build()`` is not itself wrapped in an undo chunk.
"""

import unittest

import maya.cmds as mc
from maya import cmds

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestBuild(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_build_creates_unwired_node_with_setup_seeded(self):
        from mpynode._node_registry import get_spec
        cls = get_spec("mPyDeformer").get_wrapper_class()
        node = cls.build()                                  # no setup
        self.assertTrue(node and mc.objExists(node.get_name()))
        src = node.get_methods_source()
        self.assertIn("def setup(self", src)               # seeded, self-first
        self.assertFalse(cmds.deformer(node.get_name(), q=True, g=True) or [])

    def test_build_setup_true_wires(self):
        from mpynode._node_registry import get_spec
        mesh = mc.polyCube()[0]
        mc.select(mesh)
        cls = get_spec("mPyDeformer").get_wrapper_class()
        node = cls.build(setup=True)                        # snapshot=mesh, then setup
        self.assertTrue(cmds.deformer(node.get_name(), q=True, g=True))

    def test_build_setup_true_snapshots_selection(self):
        from mpynode._node_registry import get_spec
        mesh = mc.polyCube()[0]
        mc.select(mesh)
        cls = get_spec("mPyDeformer").get_wrapper_class()
        node = cls.build(setup=True)
        self.assertIn(mc.listRelatives(mesh, shapes=True)[0],
                      cmds.deformer(node.get_name(), q=True, g=True) or [])

    def test_build_mpyfile_already_populated_seeds_without_double_seed(self):
        from mpynode._node_registry import get_spec
        cls = get_spec("mPyFile").get_wrapper_class()
        node = cls.build()
        src = node.get_methods_source() or ""
        self.assertEqual(src.count("def setup(self"), 1)   # exactly one setup


if __name__ == "__main__":
    unittest.main()
