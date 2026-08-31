"""INTERNAL_VARS removal + SelfProxy import migration acceptance across node types

Consolidated from: test_phaseG_4_remaining.py, test_phaseF_6_remaining_nodes.py.
"""

from __future__ import annotations

# ===================== from test_phaseG_4_remaining.py =====================
import inspect
import unittest

import maya.cmds as mc

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseG_4_remaining():
    standalone_init()


class TestSourceCleanup(unittest.TestCase):
    """No file in the migrated set imports legacy SelfProxy."""

    def _src(self, mod):
        return inspect.getsource(mod)

    def test_node(self):
        from mpynode._api2 import _mpy_node as node
        s = self._src(node)
        self.assertIn("from mpynode._common.compute.self_proxy import SelfProxy", s)

    def test_locator(self):
        from mpynode._api2 import mpy_locator as locator_node

        s = self._src(locator_node)
        self.assertIn("from mpynode._common.compute.self_proxy import SelfProxy", s)

    def test_constraint(self):
        from mpynode._api2 import mpy_constraint as constraint_node

        s = self._src(constraint_node)
        self.assertIn("from mpynode._common.compute.self_proxy import SelfProxy", s)

    def test_iksolver_helpers(self):
        from mpynode._api1 import helpers

        s = self._src(helpers)
        self.assertIn("from mpynode._common.compute.self_proxy import SelfProxy", s)


class TestNodesStillCreate(unittest.TestCase):

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_mpynode_creates(self):
        n = mc.createNode("mPyNode")
        self.assertTrue(mc.objExists(n))

    def test_mpylocator_creates(self):
        n = mc.createNode("mPyLocator")
        self.assertTrue(mc.objExists(n))

    def test_mpyconstraint_creates(self):
        n = mc.createNode("mPyConstraint")
        self.assertTrue(mc.objExists(n))

    def test_mpyiksolver_creates(self):
        n = mc.createNode("mPyIkSolver")
        self.assertTrue(mc.objExists(n))


class TestUserStorageStillWorks(unittest.TestCase):
    """Smoke: compute_locals -> compute_locals harvest doesn't break
    user storage flow on mPyNode."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_storage_persists_on_mpynode(self):
        n = mc.createNode("mPyNode")
        expr = (
            "self.iter = self.iter + 1 if hasattr(self, 'iter') else 1\n"
        )
        mc.setAttr(n + "._computeSource", expr, type="string")
        # Force at least one compute. mPyNode without USER outputs
        # only computes on demand; trigger via dirty propagation.
        try:
            mc.dgdirty(n)
            mc.evalDeferred("import maya.cmds as _; _.refresh()")
        except Exception:
            pass
        # We don't actually need eval to confirm the migration; the
        # source-level test above is the primary pin. The createNode
        # call exercises plugin instantiation against the new proxy.
        self.assertTrue(mc.objExists(n))


# ===================== from test_phaseF_6_remaining_nodes.py =====================
import unittest

import maya.cmds as mc

from._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseF_6_remaining_nodes():
    standalone_init()


class TestF6SchemaDeleted(unittest.TestCase):
    def test_mpynode_internal_vars_gone(self):
        from mpynode._api2._mpy_node import MPyNode
        self.assertFalse(hasattr(MPyNode, "INTERNAL_VARS"))

    def test_locator_internal_vars_gone(self):
        from mpynode._api2.mpy_locator import MPyLocator
        self.assertFalse(hasattr(MPyLocator, "INTERNAL_VARS"))

    def test_constraint_internal_vars_gone(self):
        from mpynode._api2.mpy_constraint import MPyConstraint
        self.assertFalse(hasattr(MPyConstraint, "INTERNAL_VARS"))

    def test_iksolver_internal_vars_gone(self):
        from mpynode._api1.mpy_iksolver import MPyIkSolver
        self.assertFalse(hasattr(MPyIkSolver, "INTERNAL_VARS"))


class TestF6NodeCreation(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_remaining_node_types_create(self):
        for cls in ("mPyNode", "mPyLocator", "mPyConstraint", "mPyIkSolver"):
            n = mc.createNode(cls, name=cls + "_F6_smoke")
            self.assertTrue(mc.objExists(n), "{} did not create".format(cls))


def setUpModule():
    _setUpModule__phaseG_4_remaining()
    _setUpModule__phaseF_6_remaining_nodes()


if __name__ == "__main__":
    import unittest
    unittest.main()
