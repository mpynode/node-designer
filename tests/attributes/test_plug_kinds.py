"""The plug KIND behind ``quaternion``, ``matrix`` and ``float2``, and every
read and write path.

Since 2026-10:

* ``quaternion`` is Maya's numeric double4 (``-at double4`` with explicit
  X/Y/Z/W double children, W default 1) -- the kind of
  ``decomposeMatrix.outputQuat``. It used to be a generic compound of 4.
* ``matrix`` is ``-at matrix`` (kMatrixAttribute), which reads as identity with
  no init. It used to be a typed ``-dt matrix`` plug.
* ``float2`` is offered by the dialog and the assistant, so its output seed,
  its api1 write, its Watch shape and its Convert-to-C++ value copy are
  covered here too.

A compute-time matrix write must pick its call from the plug's actual kind:
``setMMatrix`` on ``-at matrix``, ``setMObject(MFnMatrixData)`` on ``-dt
matrix``. Either call on the other kind crashes Maya, so the scenes saved
before the change (typed matrix plugs, compound quaternions) are exercised in a
child mayapy: a wrong call there fails the test instead of killing the suite.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

import maya.cmds as mc

from tests._paths import ROOT, SCRIPTS
from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# A row-vector affine matrix with a translate row that is not trivially zero.
_M = [1.0, 0.0, 0.0, 0.0,
      0.0, 1.0, 0.0, 0.0,
      0.0, 0.0, 1.0, 0.0,
      7.5, 8.25, 9.125, 1.0]
_IDENTITY = [1.0, 0.0, 0.0, 0.0,
             0.0, 1.0, 0.0, 0.0,
             0.0, 0.0, 1.0, 0.0,
             0.0, 0.0, 0.0, 1.0]


def _quat(plug):
    """``getAttr`` of a double4 plug as a flat 4-list."""
    return list(mc.getAttr(plug)[0])


class _Base(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        if not mc.pluginInfo("matrixNodes", q=True, loaded=True):
            mc.loadPlugin("matrixNodes")

    def assertListAlmostEqual(self, got, exp, places=6):
        self.assertEqual(len(got), len(exp), (got, exp))
        for g, e in zip(got, exp):
            self.assertAlmostEqual(g, e, places=places, msg=(got, exp))


class TestQuaternionIsDouble4(_Base):

    def _node(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="quatKind")
        n.add_input_attr("qIn", "quaternion")
        n.add_output_attr("qOut", "quaternion")
        n.add_input_attr("qArr", "quaternion", is_array=True)
        n.add_output_attr("qArrOut", "quaternion", is_array=True)
        n.set_compute_expression("self.qOut = self.qIn\n"
                                 "self.qArrOut = self.qArr\n")
        return n.get_name()

    def test_plugs_are_double4_with_xyzw_children(self):
        nm = self._node()
        for plug in ("qIn", "qOut", "qArr", "qArrOut"):
            self.assertEqual(mc.attributeQuery(plug, node=nm, at=True), "double4")
            kids = mc.attributeQuery(plug, node=nm, listChildren=True)
            self.assertEqual(kids, [plug + ax for ax in "XYZW"])
            for kid in kids:
                self.assertEqual(
                    mc.attributeQuery(kid, node=nm, at=True), "double")

    def test_w_defaults_to_one(self):
        nm = self._node()
        self.assertListAlmostEqual(_quat(nm + ".qIn"), [0.0, 0.0, 0.0, 1.0])
        self.assertListAlmostEqual(_quat(nm + ".qOut"), [0.0, 0.0, 0.0, 1.0])
        # an element nothing has set reads as identity too
        mc.setAttr(nm + ".qArr[1]", 0.1, 0.2, 0.3, 0.4, type="double4")
        self.assertListAlmostEqual(_quat(nm + ".qArr[0]"), [0.0, 0.0, 0.0, 1.0])

    def test_decompose_matrix_quat_round_trips(self):
        # decomposeMatrix.outputQuat is a double4: in, through the compute, and
        # out into composeMatrix.inputQuat (also a double4).
        nm = self._node()
        dm = mc.createNode("decomposeMatrix")
        mc.setAttr(dm + ".inputMatrix",
                   0.36, 0.48, -0.8, 0, -0.8, 0.6, 0, 0, 0.48, 0.64, 0.6, 0,
                   1, 2, 3, 1, type="matrix")
        mc.connectAttr(dm + ".outputQuat", nm + ".qIn")
        mc.connectAttr(dm + ".outputQuat", nm + ".qArr[0]")
        mc.setAttr(nm + ".qArr[2]", 0.1, 0.2, 0.3, 0.4, type="double4")
        want = _quat(dm + ".outputQuat")
        self.assertListAlmostEqual(_quat(nm + ".qOut"),       want)
        self.assertListAlmostEqual(_quat(nm + ".qArrOut[0]"), want)
        self.assertListAlmostEqual(_quat(nm + ".qArrOut[1]"), [0.0, 0.0, 0.0, 1.0])
        self.assertListAlmostEqual(_quat(nm + ".qArrOut[2]"), [0.1, 0.2, 0.3, 0.4])
        cm = mc.createNode("composeMatrix")
        mc.connectAttr(nm + ".qOut", cm + ".inputQuat")
        self.assertListAlmostEqual(_quat(cm + ".inputQuat"), want)

    def test_compound_source_connects(self):
        # A generic compound of 4 (eulerToQuat.outputQuat's kind) drives a
        # double4 input.
        nm  = self._node()
        src = mc.createNode("network")
        mc.addAttr(src, ln="q", at="compound", nc=4)
        for ax in "XYZW":
            mc.addAttr(src, ln="q" + ax, at="double", p="q")
        mc.setAttr(src + ".qX", 0.5)
        mc.setAttr(src + ".qW", 0.5)
        mc.connectAttr(src + ".q", nm + ".qIn")
        self.assertListAlmostEqual(_quat(nm + ".qOut"), [0.5, 0.0, 0.0, 0.5])

    def test_saved_as_double4(self):
        nm   = self._node()
        tmp  = tempfile.mkdtemp(prefix="mpynode-quat-")
        path = os.path.join(tmp, "quat.ma")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.addCleanup(mc.file, new=True, force=True)
        mc.file(rename=path)
        mc.file(save=True, type="mayaAscii", force=True)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('-ln "qIn" -at "double4" -nc 4;', text)
        mc.file(new=True, force=True)
        mc.file(path, open=True, force=True)
        self.assertEqual(mc.attributeQuery("qIn", node=nm, at=True), "double4")


class TestMatrixIsAtMatrix(_Base):

    def _node(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="matKind")
        n.add_input_attr("mIn", "matrix")
        n.add_output_attr("mOut", "matrix")
        n.add_input_attr("mArr", "matrix", is_array=True)
        n.add_output_attr("mArrOut", "matrix", is_array=True)
        n.set_compute_expression(
            "import numpy as np\n"
            "self.mOut = np.asarray(self.mIn) * 2.0\n"
            "self.mArrOut = [np.asarray(m) for m in self.mArr]\n")
        return n.get_name()

    def test_plugs_are_at_matrix(self):
        nm = self._node()
        for plug in ("mIn", "mOut", "mArr", "mArrOut"):
            self.assertEqual(mc.attributeQuery(plug, node=nm, at=True), "matrix")

    def test_new_input_reads_identity_without_init(self):
        nm = self._node()
        self.assertListAlmostEqual(mc.getAttr(nm + ".mIn"), _IDENTITY)

    def test_input_read_and_output_write(self):
        # api2 helpers path: read_plug_value on the input, write_plug_value on
        # the output (setMMatrix), then a downstream offsetParentMatrix.
        nm = self._node()
        mc.setAttr(nm + ".mIn", *_M, type="matrix")
        self.assertListAlmostEqual(mc.getAttr(nm + ".mOut"), [2 * x for x in _M])
        loc = mc.spaceLocator()[0]
        mc.connectAttr(nm + ".mOut", loc + ".offsetParentMatrix")
        self.assertListAlmostEqual(mc.getAttr(loc + ".worldMatrix[0]"),
                                   [2 * x for x in _M])

    def test_array_output_write(self):
        # api2 helpers path: write_multi_plug_value, one setMMatrix per element.
        nm = self._node()
        mc.setAttr(nm + ".mArr[0]", *_M, type="matrix")
        mc.setAttr(nm + ".mArr[1]", *[3 * x for x in _M], type="matrix")
        self.assertListAlmostEqual(mc.getAttr(nm + ".mArrOut[0]"), _M)
        self.assertListAlmostEqual(mc.getAttr(nm + ".mArrOut[1]"), [3 * x for x in _M])


class TestApi1PlugWrite(_Base):
    """The api1 compute-time PlugProxy path (``plug_read`` / ``plug_write``):
    a deformer's user plugs, read and written while it deforms."""

    def test_matrix_and_quaternion_plugs(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(sx=1, sy=1)[0]
        d     = MPyDeformer.create_on(plane)
        dn    = d.get_name()
        d.add_input_attr("x", "double")
        d.add_input_attr("mIn", "matrix")
        d.add_output_attr("mOut", "matrix")
        d.add_output_attr("mArrOut", "matrix", is_array=True)
        d.add_output_attr("qOut", "quaternion")
        self.assertEqual(mc.attributeQuery("mIn", node=dn, at=True),  "matrix")
        self.assertEqual(mc.attributeQuery("mOut", node=dn, at=True), "matrix")
        self.assertEqual(mc.attributeQuery("qOut", node=dn, at=True), "double4")
        # The array output's buffer is pre-sized from its connected elements.
        for i in range(2):
            loc = mc.spaceLocator()[0]
            mc.connectAttr("%s.mArrOut[%d]" % (dn, i), loc + ".offsetParentMatrix")
        d.set_compute_expression(
            (d.get_compute_expression() or "")
            + "\nimport numpy as np\n"
            "m = np.array(np.asarray(self.mIn), dtype=float)\n"
            "m[3, 0] = float(self.x)\n"
            "self.mOut = m\n"
            "self.mArrOut[0] = m\n"
            "self.mArrOut[1] = m * 2.0\n"
            "self.qOut = [0.1, 0.2, 0.3, float(self.x)]\n")
        mc.setAttr(dn + ".mIn", *_M, type="matrix")
        mc.setAttr(dn + ".x", 3.5)
        shape = mc.listRelatives(plane, shapes=True)[0]
        mc.dgeval(shape + ".outMesh")
        want     = list(_M)
        want[12] = 3.5
        self.assertListAlmostEqual(mc.getAttr(dn + ".mOut"), want)
        self.assertListAlmostEqual(mc.getAttr(dn + ".mArrOut[0]"), want)
        self.assertListAlmostEqual(mc.getAttr(dn + ".mArrOut[1]"),
                                   [2 * x for x in want])
        self.assertListAlmostEqual(_quat(dn + ".qOut"), [0.1, 0.2, 0.3, 3.5])

    def test_numeric_compound_outputs(self):
        # float2, double3 and color outputs, scalar and array: one set<N><Type>
        # call each. An MFnNumericData pushed with setMObject read as garbage
        # (a float2's U came back 7.98e+33).
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(sx=1, sy=1)[0]
        d     = MPyDeformer.create_on(plane)
        dn    = d.get_name()
        for name, typ in (("uv", "float2"), ("v3", "double3"), ("c", "color")):
            d.add_output_attr(name, typ)
            d.add_output_attr(name + "Arr", typ, is_array=True)
        # Two consumers of uvArr, so its seeded buffer holds 2 elements and the
        # one the expression leaves alone is harvested as (0, 0).
        for i in range(2):
            p2d = mc.createNode("place2dTexture")
            mc.connectAttr("%s.uvArr[%d]" % (dn, i), p2d + ".uvCoord")
        d.set_compute_expression(
            (d.get_compute_expression() or "")
            + "\nself.uv = (0.125, 0.875)\n"
            "self.v3 = (1.5, 2.5, 3.5)\n"
            "self.c = (0.25, 0.5, 0.75)\n"
            "self.uvArr[0] = (0.375, 0.625)\n"
            "self.v3Arr = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]\n"
            "self.cArr = [(0.125, 0.25, 0.5)]\n")
        mc.dgeval(mc.listRelatives(plane, shapes=True)[0] + ".outMesh")
        for plug, want in (("uv", [0.125, 0.875]),
                           ("v3", [1.5, 2.5, 3.5]),
                           ("c", [0.25, 0.5, 0.75]),
                           ("uvArr[0]", [0.375, 0.625]),
                           ("uvArr[1]", [0.0, 0.0]),
                           ("v3Arr[1]", [4.0, 5.0, 6.0]),
                           ("cArr[0]", [0.125, 0.25, 0.5])):
            self.assertListAlmostEqual(list(mc.getAttr(dn + "." + plug)[0]), want)


class TestFloat2(_Base):
    """float2 is offered by the dialog and the assistant since 2026-10."""

    def test_partial_array_output_write_leaves_zeros(self):
        # The seed is an (N, 2) zero buffer: an element the expression leaves
        # alone writes (0, 0). A None seed used to write NaN.
        from mpynode.wrappers._mpy_node import MPyNode

        n  = MPyNode.create(name="f2Seed")
        nm = n.get_name()
        n.add_output_attr("uvOut", "float2")
        n.add_output_attr("uvArrOut", "float2", is_array=True)
        n.add_output_attr("seen", "string")
        for i in range(2):
            p2d = mc.createNode("place2dTexture")
            mc.connectAttr("%s.uvArrOut[%d]" % (nm, i), p2d + ".uvCoord")
        n.set_compute_expression(
            "import numpy as np\n"
            "self.seen = '%s %s' % (type(self.uvArrOut).__name__,\n"
            "                       np.shape(self.uvArrOut))\n"
            "self.uvArrOut[0] = (0.375, 0.625)\n")
        self.assertListAlmostEqual(list(mc.getAttr(nm + ".uvArrOut[0]")[0]),
                                   [0.375, 0.625])
        self.assertListAlmostEqual(list(mc.getAttr(nm + ".uvArrOut[1]")[0]),
                                   [0.0, 0.0])
        self.assertListAlmostEqual(list(mc.getAttr(nm + ".uvOut")[0]),
                                   [0.0, 0.0])
        self.assertEqual(mc.getAttr(nm + ".seen"), "ndarray (2, 2)")

    def test_watch_shapes_match_the_expression(self):
        # The Watch tab shows a float2 as the expression reads it: (2,), and
        # an array as (N, 2) with gaps at the default.
        import numpy as np

        from mpynode.ui.widgets.watch import (read_multi_plug_values,
                                              reshape_plug_value)
        from mpynode.wrappers._mpy_node import MPyNode

        n  = MPyNode.create(name="f2Watch")
        nm = n.get_name()
        n.add_input_attr("uv", "float2")
        n.add_input_attr("uvArr", "float2", is_array=True)
        n.add_input_attr("uvEmpty", "float2", is_array=True)
        mc.setAttr(nm + ".uv",       0.25,  0.75,  type="float2")
        mc.setAttr(nm + ".uvArr[0]", 0.125, 0.375, type="float2")
        mc.setAttr(nm + ".uvArr[2]", 0.5,   0.625, type="float2")
        one = reshape_plug_value(mc.getAttr(nm + ".uv"),
                                 {"attr_type": "float2"})
        self.assertEqual(np.shape(one), (2,))
        self.assertListAlmostEqual(list(one), [0.25, 0.75])
        arr = read_multi_plug_values(nm, "uvArr",
                                     {"attr_type": "float2", "is_array": True})
        self.assertIsInstance(arr, np.ndarray)
        self.assertEqual(arr.shape, (3, 2))
        self.assertListAlmostEqual(arr.ravel().tolist(),
                                   [0.125, 0.375, 0.0, 0.0, 0.5, 0.625])
        empty = read_multi_plug_values(nm, "uvEmpty",
                                       {"attr_type": "float2", "is_array": True})
        self.assertEqual(empty.shape, (0, 2))


class TestNodeSwapCopiesNewKinds(_Base):
    """Convert to C++ copies every value set by value. A double4 or float2
    array element reports neither "TdataCompound" nor a type the scalar copy
    knew, so its value used to be dropped."""

    def _node(self, name):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=name)
        n.add_input_attr("q", "quaternion")
        n.add_input_attr("qArr", "quaternion", is_array=True)
        n.add_input_attr("uv", "float2")
        n.add_input_attr("uvArr", "float2", is_array=True)
        return n.get_name()

    def test_values_set_by_value_are_copied(self):
        from mpynode._base.node_swap import copy_multi_values, copy_values

        src, dst = self._node("swapSrc"), self._node("swapDst")
        mc.setAttr(src + ".q",       0.1, 0.2, 0.3, 0.9, type="double4")
        mc.setAttr(src + ".qArr[0]", 0.6, 0.0, 0.0, 0.8, type="double4")
        mc.setAttr(src + ".qArr[2]", 0.0, 0.6, 0.0, 0.8, type="double4")
        mc.setAttr(src + ".uv",       0.25,  0.75,  type="float2")
        mc.setAttr(src + ".uvArr[0]", 0.125, 0.375, type="float2")
        mc.setAttr(src + ".uvArr[2]", 0.5,   0.625, type="float2")
        copy_values(src, dst)
        copy_multi_values(src, dst)
        for plug in ("q", "qArr[0]", "qArr[2]", "uv", "uvArr[0]", "uvArr[2]"):
            self.assertListAlmostEqual(list(mc.getAttr(dst + "." + plug)[0]),
                                       list(mc.getAttr(src + "." + plug)[0]))


# ---- scenes saved before 2026-10, in a child mayapy ------------------------

_CHILD = textwrap.dedent(r'''
    import json, os, sys
    out_path = sys.argv[1]
    res = {}

    def save():
        with open(out_path, "w") as fh:
            json.dump(res, fh)

    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc
    for p in ("mpynode_api1", "mpynode_api2"):
        mc.loadPlugin(p)
    from mpynode.wrappers._mpy_node import MPyNode

    def legacy_matrix(n, name, is_array):
        # What add_output_attr made before 2026-10: a typed -dt matrix plug.
        kw = {"multi": True} if is_array else {}
        mc.addAttr(n.get_name(), ln=name, sn=name, dt="matrix", keyable=False,
                   writable=False, readable=True, cachedInternally=True, **kw)
        mp = n._read_output_map()
        mp[name] = {"attr_type": "matrix", "is_array": is_array, "order": len(mp)}
        n._write_output_map(mp)

    def legacy_matrix_input(n, name, is_array):
        # What add_input_attr made before 2026-10: a typed -dt matrix plug.
        kw = {"multi": True} if is_array else {}
        mc.addAttr(n.get_name(), ln=name, sn=name, dt="matrix", **kw)
        mp = n._read_input_map()
        mp[name] = {"attr_type": "matrix", "is_array": is_array, "order": len(mp)}
        n._write_input_map(mp)

    M = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0,
         7.5, 8.25, 9.125, 1.0]
    DUMP = ("import json\n"
            "import numpy as np\n"
            "d = {}\n"
            "for a in NAMES:\n"
            "    d[a] = np.asarray(getattr(self, a), dtype=float).tolist()\n"
            "self.seen = json.dumps(d)\n")

    def legacy_quat(n, name, is_array, output):
        # What add_*_attr made before 2026-10: a generic compound of 4.
        nm = n.get_name()
        kw = {"writable": False} if output else {}
        mc.addAttr(nm, ln=name, at="compound", nc=4, multi=is_array, **kw)
        for ax in "XYZW":
            mc.addAttr(nm, ln=name + ax, at="double", p=name,
                       dv=(1.0 if ax == "W" else 0.0), **kw)
        if output:
            mp = n._read_output_map()
        else:
            mp = n._read_input_map()
        mp[name] = {"attr_type": "quaternion", "is_array": is_array,
                    "order": len(mp)}
        (n._write_output_map if output else n._write_input_map)(mp)

    # api2 MPyNode: typed matrix outputs, scalar + array.
    n = MPyNode.create(name="legacyMat")
    n.add_input_attr("x", "double")
    legacy_matrix(n, "mOut", False)
    legacy_matrix(n, "mArrOut", True)
    n.set_compute_expression(
        "import numpy as np\n"
        "m = np.eye(4); m[3, 0] = self.x\n"
        "self.mOut = m\n"
        "self.mArrOut = [m, m * 2.0]\n")
    res["api2_kind"] = mc.attributeQuery("mOut", node="legacyMat", at=True)
    save()
    mc.setAttr("legacyMat.x", 4.5)
    res["api2_out"] = mc.getAttr("legacyMat.mOut")
    res["api2_arr1"] = mc.getAttr("legacyMat.mArrOut[1]")
    save()

    # api2 MPyNode: compound quaternion input + outputs, scalar + array.
    q = MPyNode.create(name="legacyQuat")
    legacy_quat(q, "qIn", False, False)
    legacy_quat(q, "qOut", False, True)
    legacy_quat(q, "qArrOut", True, True)
    q.set_compute_expression("self.qOut = self.qIn * 2.0\n"
                             "self.qArrOut = [self.qIn, self.qIn * 3.0]\n")
    mc.setAttr("legacyQuat.qInX", 0.25)
    res["quat_kind"] = mc.attributeQuery("qOut", node="legacyQuat", at=True)
    res["quat_out"] = list(mc.getAttr("legacyQuat.qOut")[0])
    res["quat_arr1"] = list(mc.getAttr("legacyQuat.qArrOut[1]")[0])
    save()

    # api2 MPyNode: typed matrix INPUTS through the plug reader -- connected,
    # set, unset, and an array with a gap.
    r = MPyNode.create(name="legacyMatIn")
    rn = r.get_name()
    r.add_output_attr("seen", "string")
    for name, is_array in (("lmIn", False), ("lmSet", False),
                           ("lmUnset", False), ("lmArr", True)):
        legacy_matrix_input(r, name, is_array)
    loc = mc.spaceLocator()[0]
    mc.setAttr(loc + ".translate", 1.0, 2.0, 3.0)
    mc.connectAttr(loc + ".worldMatrix[0]", rn + ".lmIn")
    mc.setAttr(rn + ".lmSet", *M, type="matrix")
    mc.setAttr(rn + ".lmArr[1]", *M, type="matrix")
    r.set_compute_expression(
        "NAMES = ('lmIn', 'lmSet', 'lmUnset', 'lmArr')\n" + DUMP)
    res["api2_read"] = json.loads(mc.getAttr(rn + ".seen"))
    save()

    # api1 deformer: typed matrix outputs, scalar and array (the array goes
    # through the seeded buffer and its harvest).
    from mpynode.wrappers.mpy_deformer import MPyDeformer
    plane = mc.polyPlane(sx=1, sy=1)[0]
    d = MPyDeformer.create_on(plane)
    dn = d.get_name()
    d.add_input_attr("x", "double")
    legacy_matrix(d, "mOut", False)
    legacy_matrix(d, "mArrOut", True)
    for i in range(2):
        loc = mc.spaceLocator()[0]
        mc.connectAttr("%s.mArrOut[%d]" % (dn, i), loc + ".offsetParentMatrix")
    d.set_compute_expression(
        (d.get_compute_expression() or "")
        + "\nimport numpy as np\n"
        "m = np.eye(4); m[3, 1] = float(self.x)\n"
        "self.mOut = m\n"
        "self.mArrOut[0] = m\n"
        "self.mArrOut[1] = m * 2.0\n")
    mc.setAttr(dn + ".x", 6.0)
    mc.dgeval(mc.listRelatives(plane, shapes=True)[0] + ".outMesh")
    res["api1_out"] = mc.getAttr(dn + ".mOut")
    res["api1_arr1"] = mc.getAttr(dn + ".mArrOut[1]")
    save()

    # mPyFile: typed matrix inputs through the thread-safe DATABLOCK reader,
    # where asMatrix() on a typed handle read garbage memory.
    from mpynode.wrappers.mpy_file import MPyFile
    f = MPyFile.create(name="legacyFile", seed_defaults=False, as_texture=False)
    fn = f.get_name()
    f.add_output_attr("seen", "string")
    for name, is_array in (("lmSet", False), ("lmUnset", False),
                           ("lmArr", True)):
        legacy_matrix_input(f, name, is_array)
    mc.setAttr(fn + ".lmSet", *M, type="matrix")
    mc.setAttr(fn + ".lmArr[1]", *M, type="matrix")
    f.set_compute_expression(
        "NAMES = ('lmSet', 'lmUnset', 'lmArr')\n" + DUMP
        + "self.outColor = (0.5, 0.5, 0.5)\n")
    mc.getAttr(fn + ".outColor")
    res["file_read"] = json.loads(mc.getAttr(fn + ".seen"))
    res["done"] = True
    save()

    # A clean shutdown: a bare exit after loading the plug-ins crashes in Maya's
    # teardown and writes a recovery scene to %TEMP%.
    mc.file(new=True, force=True)
    maya.standalone.uninitialize()
    os._exit(0)
''')


def _mayapy():
    """mayapy, never the Maya GUI binary (see test_stage1_codegen_freshness)."""
    here = os.path.dirname(sys.executable)
    for cand in (os.path.join(here, "mayapy"), os.path.join(here, "mayapy.exe"),
                 os.path.join(os.path.dirname(here), "bin", "mayapy"),
                 os.path.join(os.path.dirname(here), "bin", "mayapy.exe")):
        if os.path.isfile(cand):
            return cand
    return sys.executable


class TestLegacyKindsInAChild(unittest.TestCase):
    """Scenes saved before 2026-10 keep their typed matrix and compound
    quaternion plugs; every compute write must still pick the right call, and
    every reader (the plug reader and mPyFile's datablock reader) must read
    them."""

    @classmethod
    def setUpClass(cls):
        tmp      = tempfile.mkdtemp(prefix="mpynode-legacy-kinds-")
        cls.tmp  = tmp
        script   = os.path.join(tmp, "child.py")
        out_path = os.path.join(tmp, "result.json")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(_CHILD)
        env                     = dict(os.environ)
        env["MAYA_DISABLE_CER"] = "1"
        env["MPYNODE_ROOT"]     = ROOT
        env["PYTHONPATH"] = os.pathsep.join(
            [SCRIPTS, ROOT] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
        env["MAYA_PLUG_IN_PATH"] = os.pathsep.join(
            [os.path.join(ROOT, "plug-ins")]
            + [p for p in env.get("MAYA_PLUG_IN_PATH", "").split(os.pathsep) if p])
        proc = subprocess.run([_mayapy(), script, out_path], env=env,
                              capture_output=True, text=True, timeout=600)
        cls.returncode = proc.returncode
        cls.tail       = (proc.stdout + proc.stderr)[-3000:]
        cls.res        = {}
        if os.path.isfile(out_path):
            with open(out_path, encoding="utf-8") as fh:
                cls.res = json.load(fh)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _need(self, key):
        if key not in self.res:
            self.fail("the child mayapy stopped before %r (exit %s); a wrong "
                      "matrix call crashes Maya. Child output:\n%s"
                      % (key, self.returncode, self.tail))
        return self.res[key]

    def test_child_finished(self):
        self.assertTrue(self._need("done"))
        self.assertEqual(self.returncode, 0, self.tail)

    def test_api2_typed_matrix_outputs_write(self):
        self.assertEqual(self._need("api2_kind"), "typed")
        want     = list(_IDENTITY)
        want[12] = 4.5
        for g, e in zip(self._need("api2_out"), want):
            self.assertAlmostEqual(g, e)
        for g, e in zip(self._need("api2_arr1"), [2 * x for x in want]):
            self.assertAlmostEqual(g, e)

    def test_api2_compound_quaternion_writes(self):
        self.assertEqual(self._need("quat_kind"), "compound")
        for g, e in zip(self._need("quat_out"), [0.5, 0.0, 0.0, 2.0]):
            self.assertAlmostEqual(g, e)
        for g, e in zip(self._need("quat_arr1"), [0.75, 0.0, 0.0, 3.0]):
            self.assertAlmostEqual(g, e)

    def test_api1_typed_matrix_output_writes(self):
        want     = list(_IDENTITY)
        want[13] = 6.0
        for g, e in zip(self._need("api1_out"), want):
            self.assertAlmostEqual(g, e)
        for g, e in zip(self._need("api1_arr1"), [2 * x for x in want]):
            self.assertAlmostEqual(g, e)

    def _assert_matrix(self, got, flat16):
        self.assertEqual(len(got), 4, got)
        flat = [x for row in got for x in row]
        for g, e in zip(flat, flat16):
            self.assertAlmostEqual(g, e, msg=(got, flat16))

    def test_api2_typed_matrix_inputs_read(self):
        got              = self._need("api2_read")
        connected        = list(_IDENTITY)
        connected[12:15] = [1.0, 2.0, 3.0]
        self._assert_matrix(got["lmIn"],    connected)
        self._assert_matrix(got["lmSet"],   _M)
        self._assert_matrix(got["lmUnset"], _IDENTITY)
        self.assertEqual(len(got["lmArr"]), 2)
        self._assert_matrix(got["lmArr"][0], _IDENTITY)
        self._assert_matrix(got["lmArr"][1], _M)

    def test_file_datablock_reads_typed_matrix_inputs(self):
        got = self._need("file_read")
        self._assert_matrix(got["lmSet"], _M)
        self._assert_matrix(got["lmUnset"], _IDENTITY)
        self.assertEqual(len(got["lmArr"]), 2)
        self._assert_matrix(got["lmArr"][0], _IDENTITY)
        self._assert_matrix(got["lmArr"][1], _M)


if __name__ == "__main__":
    unittest.main()
