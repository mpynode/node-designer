"""Self-only namespace contract (Bug 1).

A node's expression reaches inputs and outputs ONLY through ``self``. Bare
names are no longer injected for inputs, and bare assignments are no longer
harvested as outputs -- one convention, no dual surface. Python-keyword
attribute names are rejected at creation (``self.in`` is a SyntaxError);
builtin-shadowing names (``min``, ``type``) remain legal because ``self.min``
is unambiguous.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _make_node():
    from mpynode import MPyNode

    n = MPyNode.create(name="selfOnlyTest")
    n.add_input_attr("a", "float")
    n.add_output_attr("c", "float")
    return n


class TestSelfOnlyContract(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_self_input_self_output_commits(self):
        n = _make_node()
        n.set_compute_expression("self.c = self.a * 2")
        mc.setAttr(n.get_name() + ".a", 5.0)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".c"), 10.0, places=5)

    def test_bare_input_does_not_resolve(self):
        n = _make_node()
        # 'a' as a bare name must NOT resolve -> expression errors -> c unwritten.
        n.set_compute_expression("self.c = a * 2")
        mc.setAttr(n.get_name() + ".a", 5.0)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".c"), 0.0, places=5)

    def test_bare_output_not_committed(self):
        n = _make_node()
        # bare 'c =' must NOT be harvested -> output stays at default.
        n.set_compute_expression("c = self.a * 2")
        mc.setAttr(n.get_name() + ".a", 5.0)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".c"), 0.0, places=5)

    def test_keyword_input_name_rejected(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="kwInTest")
        with self.assertRaises(ValueError):
            n.add_input_attr("in", "float")

    def test_keyword_output_name_rejected(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="kwOutTest")
        with self.assertRaises(ValueError):
            n.add_output_attr("class", "float")

    def test_non_identifier_name_rejected(self):
        from mpynode import MPyNode

        n = MPyNode.create(name="badNameTest")
        with self.assertRaises(ValueError):
            n.add_input_attr("has space", "float")

    def test_builtin_shadowing_name_allowed(self):
        from mpynode import MPyNode

        # 'min' shadows a builtin but is safe under self-only (self.min).
        n = MPyNode.create(name="builtinNameTest")
        n.add_input_attr("min", "float")
        n.add_output_attr("c", "float")
        n.set_compute_expression("self.c = self.min + 1")
        mc.setAttr(n.get_name() + ".min", 4.0)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".c"), 5.0, places=5)


if __name__ == "__main__":
    unittest.main()
