"""Pulling a compound output's CHILD first gets the computed value (bug 7).

Two holes on the interpreted node, both needed for ``getAttr node.outY`` to be
right when nothing has read ``node.out`` yet:

  * dirtying: ``declare_user_affects`` appended the output PARENT, which leaves
    its children clean -- so an input edit never reached ``outY``, which kept
    serving the previous value (a fresh node: the default);
  * compute: the request names the child, whose name is not in the output map,
    so compute returned early.

Measured before the fix: ``probe.colR`` read 0.0 on a fresh node and the
pre-edit value after an input edit, while ``probe.col`` was right.
"""
from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


class _DG(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        self._em = mc.evaluationManager(query=True, mode=True)[0]
        mc.evaluationManager(mode="off")

    def tearDown(self):
        mc.evaluationManager(mode=self._em)


class TestMPyNode(_DG):

    def _node(self):
        from mpynode import MPyNode

        w = MPyNode.create(name="kidPull")
        w.add_input_attr("k", "float", default_value=0.25)
        w.add_output_attr("col", "color")
        w.add_output_attr("vec", "double3")
        w.add_output_attr("arr", "double3", is_array=True)
        w.set_compute_expression(
            "self.col = (self.k, 2 * self.k, 3 * self.k)\n"
            "self.vec = (self.k, -self.k, 4.0)\n"
            "self.arr = [(self.k, 1.0, 2.0), (3.0, self.k, 5.0)]\n")
        return w.get_name()

    def test_fresh_node_child_first(self):
        n = self._node()
        self.assertAlmostEqual(mc.getAttr(n + ".colR"), 0.25, places=6)

    def test_child_first_after_an_input_edit(self):
        n = self._node()
        mc.getAttr(n + ".col")  # computed once at k=0.25
        mc.setAttr(n + ".k", 0.5)
        self.assertAlmostEqual(mc.getAttr(n + ".colG"), 1.0, places=6)
        mc.setAttr(n + ".k", 0.75)
        self.assertAlmostEqual(mc.getAttr(n + ".vecY"), -0.75, places=6)
        mc.setAttr(n + ".k", 1.5)
        self.assertAlmostEqual(mc.getAttr(n + ".arr[1].arrY"), 1.5, places=6)

    def test_affects_reach_the_children(self):
        import maya.api.OpenMaya as om
        from mpynode._api2._mpy_node import MPyNode as ApiNode
        from mpynode._common.plugs import dirty_affects

        n = self._node()
        mc.getAttr(n + ".arr[1]")  # make the elements exist
        dirty_affects.invalidate_all()
        sel = om.MSelectionList()
        sel.add(n)
        mobj     = sel.getDependNode(0)
        affected = om.MPlugArray()
        dirty_affects.declare_user_affects(
            mobj, om.MFnDependencyNode(mobj).findPlug("k", False), affected,
            ApiNode._input_attrs_attr, ApiNode._output_attrs_attr)
        names = {affected[i].partialName(useLongNames=True)
                 for i in range(len(affected))}
        for want in ("col", "colR", "colG", "colB", "vec", "vecX", "arr[1]",
                     "arr[1].arrY"):
            self.assertIn(want, names)


class TestMPyMesh(_DG):

    def test_user_compound_output_child_first(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        w = MPyMesh.create(name="kidMesh")
        w.add_input_attr("k", "float", default_value=0.5)
        w.add_output_attr("centre", "double3")
        w.set_compute_expression(
            "import numpy as np\n"
            "self.points = np.zeros((3, 3)) + self.k\n"
            "self.counts = np.array([3])\n"
            "self.indices = np.array([0, 1, 2])\n"
            "self.centre = (self.k, 2 * self.k, 0.0)\n")
        n = w.get_name()
        mc.getAttr(n + ".centre")
        mc.setAttr(n + ".k", 2.0)
        self.assertAlmostEqual(mc.getAttr(n + ".centreY"), 4.0, places=6)


if __name__ == "__main__":
    unittest.main()
