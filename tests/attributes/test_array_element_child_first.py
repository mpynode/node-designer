"""A child of an array element that does not exist yet computes when it is
read first, as on the compiled node.

Measured 2026-10-15 with round 3's array-element probe (the compiled finals
and the All Templates Plugin, DG and parallel evaluation): on a new De Boor
Spline, ``samples[3].samplesX`` read first read 0.0 where the compiled node
read 6.0, the last CV. DNET ``positions`` and Spine ``outputTranslate`` /
``outputScale`` did the same: 4 of 12 child reads. A child read past the
computed elements (``samples[1]``, then ``samples[6].samplesX``) read 0 too.
The interpreted node never ran compute and reported the plug clean.

Cause: the element such a read creates starts with clean children.
``dirty_affects.declare_user_affects`` dirtied the array output, its existing
elements and their children, and an element created later is none of these.
Reading the element itself (``samples[3]``) computed. The compiled node's
``attributeAffects`` reach the children of every element.

The fix: ``declare_user_affects`` also appends each child of a compound array
output at the array level (``arr[-1].arrX``), which dirties the children of
an element created later. The compute of every API 2.0 family already
resolves a child to its element. Computes per frame are unchanged: 1 per
frame for a keyed input under DG and parallel evaluation, before and after.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

import maya.api.OpenMaya as om
import maya.cmds as mc

from tests import _paths
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_FAMILIES = ("mPyNode", "mPyConstraint", "mPyFile", "mPyMesh",
             "mPyNurbsCurve", "mPyNurbsSurface")
# arr[i] = (10 a + i, a, n): n is the element count compute sized arr to
_EXPR = ("n = len(self.arr)\n"
         "self.arr = [(self.a * 10.0 + i, self.a, float(n)) for i in range(n)]\n"
         "self.fl = [self.a + i for i in range(len(self.fl))]\n")
_MODES = ("off", "parallel")


def _family_node(node_type, a=0.5):
    import mpynode

    node = mc.createNode(node_type, name="n_" + node_type, skipSelect=True)
    w    = mpynode.wrap_node(node)
    w.add_input_attr("a", "double")
    w.add_output_attr("arr", "double3", is_array=True)
    w.add_output_attr("fl", "double", is_array=True)
    w.set_compute_expression(_EXPR)
    mc.setAttr(node + ".a", a)
    return node


def _template_node(rel):
    from mpynode._common.io import mpn_io

    path    = os.path.join(_paths.ROOT, "templates", rel, "template.mpn")
    payload = mpn_io.load_mpn(path, trusted=True)
    return mpn_io.deserialize_node(payload, skip_selection=True).get_name()


def _mtx(tx, ty, tz):
    return [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, tx, ty, tz, 1.0]


def _spline():
    n = _template_node("MPyNode/De Boor Spline")
    for k, v in enumerate([(0, 0, 0), (1, 2, 0), (3, -1, 1), (4, 0, 2),
                           (6, 1, 0)]):
        mc.setAttr("%s.cv[%d]" % (n, k), *v)
    return n


def _dnet():
    n = _template_node("MPyNode/DNET")
    for k, x in enumerate((0.0, 1.0, 2.5, 3.0, 4.0)):
        mc.setAttr("%s.matrices[%d]" % (n, k), _mtx(x, 0.2 * k, 0.0),
                   type="matrix")
    mc.setAttr(n + ".anchors[0]", 1.0)
    mc.setAttr(n + ".anchors[4]", 1.0)
    return n


def _spine():
    n = _template_node("MPyNode/Spine")
    for k, (x, y) in enumerate(((0.0, 0.0), (2.0, 1.0), (4.0, 0.0),
                                (6.0, 1.5))):
        mc.setAttr("%s.controlMatrices[%d]" % (n, k), _mtx(x, y, 0.0),
                   type="matrix")
    for k, s in enumerate((0.0, 0.2, 0.45, 0.7, 1.0)):
        mc.setAttr("%s.samples[%d]" % (n, k), s)
    mc.setAttr(n + ".computeWeights", 1)
    return n


class _Case(unittest.TestCase):

    def setUp(self):
        mc.file(new=True, force=True)
        self._em = mc.evaluationManager(query=True, mode=True)[0]
        self.addCleanup(mc.evaluationManager, mode=self._em)
        self.addCleanup(mc.file, new=True, force=True)

    def _fresh(self, mode):
        mc.file(new=True, force=True)
        mc.evaluationManager(mode=mode)


class TestAffects(_Case):

    def _affected(self, node):
        from mpynode._api2._mpy_node import MPyNode as ApiNode
        from mpynode._common.plugs import dirty_affects

        mobj     = om.MSelectionList().add(node).getDependNode(0)
        affected = om.MPlugArray()
        dirty_affects.invalidate_all()
        dirty_affects.declare_user_affects(
            mobj, om.MFnDependencyNode(mobj).findPlug("a", False), affected,
            ApiNode._input_attrs_attr, ApiNode._output_attrs_attr)
        return [affected[i].partialName(useLongNames=True)
                for i in range(len(affected))]

    def test_a_compound_array_dirties_its_children_at_the_array_level(self):
        node  = _family_node("mPyNode")
        names = self._affected(node)
        for want in ("arr[-1].arrX", "arr[-1].arrY", "arr[-1].arrZ"):
            self.assertEqual(names.count(want), 1, names)

    def test_existing_elements_keep_their_own_entries(self):
        node = _family_node("mPyNode")
        mc.getAttr(node + ".arr[1]")
        mc.getAttr(node + ".fl[1]")
        names = self._affected(node)
        for want in ("arr", "arr[0]", "arr[1]", "arr[1].arrY", "fl", "fl[0]",
                     "fl[1]"):
            self.assertIn(want, names)

    def test_a_scalar_array_gets_no_array_level_entry(self):
        node  = _family_node("mPyNode")
        names = self._affected(node)
        self.assertEqual([x for x in names if x.startswith("fl")], ["fl"])


class TestEveryFamily(_Case):
    """Hand-built node per API 2.0 family, DG and parallel evaluation."""

    def _run(self, check):
        for mode in _MODES:
            for node_type in _FAMILIES:
                self._fresh(mode)
                node = _family_node(node_type)
                with self.subTest(family=node_type, mode=mode):
                    check(node)

    def test_a_child_read_first_computes(self):
        def check(node):
            self.assertAlmostEqual(mc.getAttr(node + ".arr[3].arrX"), 8.0)
            self.assertAlmostEqual(mc.getAttr(node + ".arr[3].arrZ"), 4.0)
            self.assertEqual(mc.getAttr(node + ".arr[3]"), [(8.0, 0.5, 4.0)])
        self._run(check)

    def test_another_child_read_first_computes(self):
        def check(node):
            self.assertAlmostEqual(mc.getAttr(node + ".arr[2].arrY"), 0.5)
            self.assertAlmostEqual(mc.getAttr(node + ".arr[0].arrZ"), 3.0)
        self._run(check)

    def test_a_child_read_past_the_computed_elements_computes(self):
        def check(node):
            self.assertEqual(mc.getAttr(node + ".arr[1]"), [(6.0, 0.5, 2.0)])
            self.assertAlmostEqual(mc.getAttr(node + ".arr[5].arrX"), 10.0)
            self.assertAlmostEqual(mc.getAttr(node + ".arr[5].arrZ"), 6.0)
        self._run(check)

    def test_a_child_read_after_an_input_change_computes(self):
        def check(node):
            mc.getAttr(node + ".arr[1]")
            mc.setAttr(node + ".a", 2.0)
            self.assertAlmostEqual(mc.getAttr(node + ".arr[4].arrY"), 2.0)
            self.assertAlmostEqual(mc.getAttr(node + ".arr[0].arrX"), 20.0)
        self._run(check)

    def test_a_connected_child_reads_its_value(self):
        def check(node):
            sink = mc.createNode("transform", skipSelect=True)
            mc.connectAttr(node + ".arr[3].arrX", sink + ".translateX")
            self.assertAlmostEqual(mc.getAttr(sink + ".translateX"), 8.0)
            mc.setAttr(node + ".a", 1.5)
            self.assertAlmostEqual(mc.getAttr(sink + ".translateX"), 18.0)
        self._run(check)


class TestAfterReopen(_Case):

    def test_a_child_read_first_after_open_computes(self):
        from mpynode._common.lifecycle import scene_state

        # The opens below start the 10 s post-open grace window. Put the old
        # stamp back, so later tests in this process do not start inside it,
        # where should_defer_transient() is True and a compute error naming
        # a missing plug, even a misspelt one, is not reported.
        self.addCleanup(setattr, scene_state, "_last_open_monotonic",
                        scene_state._last_open_monotonic)
        folder = tempfile.mkdtemp(prefix="child_first_")
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, "child_first.ma").replace("\\", "/")
        for node_type in _FAMILIES:
            mc.file(new=True, force=True)
            node = _family_node(node_type, a=1.0)
            mc.file(rename=path)
            mc.file(save=True, type="mayaAscii", force=True)
            mc.file(new=True, force=True)
            mc.file(path, open=True, force=True)
            with self.subTest(family=node_type):
                self.assertAlmostEqual(mc.getAttr(node + ".arr[2].arrX"), 12.0)
                self.assertAlmostEqual(mc.getAttr(node + ".arr[2].arrZ"), 3.0)


class TestTemplates(_Case):
    """The shipped templates with a compound array output: a child read
    first on one node equals the same child read after its element on a
    twin."""

    CASES = (("De Boor Spline", _spline, "samples", "X", 6.0),
             ("De Boor Spline", _spline, "samples", "Y", 1.0),
             ("DNET", _dnet, "positions", "X", None),
             ("DNET", _dnet, "positions", "Y", None),
             ("Spine", _spine, "outputTranslate", "X", None),
             ("Spine", _spine, "outputTranslate", "Y", None),
             ("Spine", _spine, "outputScale", "X", 1.0),
             ("Spine", _spine, "outputRotate", "Z", None))

    def test_a_child_read_first_matches_the_element_read(self):
        for mode in _MODES:
            for label, make, attr, axis, value in self.CASES:
                self._fresh(mode)
                first = make()
                twin  = make()
                child = "%s[3].%s%s" % (attr, attr, axis)
                got   = mc.getAttr(first + "." + child)
                mc.getAttr("%s.%s[3]" % (twin, attr))
                want = mc.getAttr(twin + "." + child)
                with self.subTest(template=label, plug=child, mode=mode):
                    self.assertNotAlmostEqual(want, 0.0)
                    self.assertAlmostEqual(got, want, places=6)
                    if value is not None:
                        self.assertAlmostEqual(got, value, places=6)


if __name__ == "__main__":
    unittest.main()
