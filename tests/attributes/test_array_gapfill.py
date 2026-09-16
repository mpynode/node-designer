"""Gap-filled (logical-index) array INPUT reads + the per-input ``sparse`` opt-out.

A NON-sparse array input now reads as a DENSE numpy array of length
``max_logical+1``, with unconnected/unset gaps filled by the attribute default
(matrices -> identity, quaternions -> [0,0,0,1], numeric -> the addAttr ``dv``).
A ``sparse=True`` array keeps the legacy compact (connected-only) read.

Replaces the removed ``index_matters`` feature: every multi is now Maya-default
``indexMatters=True`` (logical indices preserved), and how the expression SEES
the array is chosen by the read-layer ``sparse`` flag instead.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.api.OpenMaya as om
import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _read(node, names):
    """Read selected user inputs exactly as compute() does."""
    from mpynode._api2 import helpers

    sel = om.MSelectionList()
    sel.add(node.get_name())
    obj = sel.getDependNode(0)
    attr_map = {
        k: v for k, v in node.get_input_attr_map().items() if k in names
    }
    return helpers.read_user_inputs_dict(obj, attr_map)


class TestGapFillRead(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.MPyNode = MPyNode

    def test_float_gaps_fill_default_zero(self):
        n = self.MPyNode.create(name="gf_f")
        n.add_input_attr("d", "float", is_array=True)
        mc.setAttr(n.get_name() + ".d[3]", 11.0)
        mc.setAttr(n.get_name() + ".d[8]", 22.0)
        out = _read(n, ["d"])["d"]
        self.assertEqual(len(out), 9)
        self.assertEqual(out[3],   11.0)
        self.assertEqual(out[8],   22.0)
        self.assertEqual(out[0],   0.0)
        self.assertEqual(out[5],   0.0)

    def test_float_gaps_fill_custom_dv(self):
        n = self.MPyNode.create(name="gf_dv")
        n.add_input_attr("d", "float", is_array=True, default_value=5.0)
        mc.setAttr(n.get_name() + ".d[2]", 99.0)
        out = _read(n, ["d"])["d"]
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0],   5.0)
        self.assertEqual(out[1],   5.0)
        self.assertEqual(out[2],   99.0)

    def test_int_gaps_fill_dv(self):
        n = self.MPyNode.create(name="gf_i")
        n.add_input_attr("k", "int", is_array=True, default_value=7)
        mc.setAttr(n.get_name() + ".k[4]", 3)
        out = _read(n, ["k"])["k"]
        self.assertEqual(len(out),      5)
        self.assertEqual(list(out[:4]), [7, 7, 7, 7])
        self.assertEqual(out[4],        3)

    def test_sparse_keeps_compact(self):
        n = self.MPyNode.create(name="gf_sp")
        n.add_input_attr("d", "float", is_array=True, sparse=True)
        mc.setAttr(n.get_name() + ".d[3]", 11.0)
        mc.setAttr(n.get_name() + ".d[8]", 22.0)
        out = _read(n, ["d"])["d"]
        self.assertEqual(len(out), 2)
        self.assertEqual(sorted(out.tolist()), [11.0, 22.0])

    def test_empty_array_is_length_zero(self):
        n = self.MPyNode.create(name="gf_e")
        n.add_input_attr("d", "float", is_array=True)
        out = _read(n, ["d"])["d"]
        self.assertEqual(len(out), 0)

    def test_contiguous_unchanged(self):
        n = self.MPyNode.create(name="gf_c")
        n.add_input_attr("d", "float", is_array=True)
        for i in range(3):
            mc.setAttr("%s.d[%d]" % (n.get_name(), i), float(i + 1))
        out = _read(n, ["d"])["d"]
        self.assertEqual(out.tolist(), [1.0, 2.0, 3.0])

    def test_vector_gaps_fill_zeros(self):
        n = self.MPyNode.create(name="gf_v")
        n.add_input_attr("v", "vector", is_array=True)
        mc.setAttr(n.get_name() + ".v[2]", 1.0, 2.0, 3.0, type="double3")
        out = _read(n, ["v"])["v"]
        self.assertEqual(out.shape,       (3, 3))
        self.assertEqual(out[0].tolist(), [0.0, 0.0, 0.0])
        self.assertEqual(out[2].tolist(), [1.0, 2.0, 3.0])

    def test_matrix_gaps_fill_identity(self):
        n = self.MPyNode.create(name="gf_m")
        n.add_input_attr("m", "matrix", is_array=True)
        vals = [2.0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 1]
        mc.setAttr(n.get_name() + ".m[2]", *vals, type="matrix")
        out = np.asarray(_read(n, ["m"])["m"])
        self.assertEqual(out.shape, (3, 4, 4))
        self.assertTrue(np.allclose(out[0], np.eye(4)))
        self.assertTrue(np.allclose(out[1], np.eye(4)))
        self.assertAlmostEqual(out[2][0][0], 2.0)

    def test_quaternion_gaps_fill_identity_quat(self):
        n = self.MPyNode.create(name="gf_q")
        n.add_input_attr("q", "quaternion", is_array=True)
        for ax, val in zip("XYZW", (0.1, 0.2, 0.3, 0.4)):
            mc.setAttr("%s.q[1].q%s" % (n.get_name(), ax), val)
        out = _read(n, ["q"])["q"]
        self.assertEqual(out.shape, (2, 4))
        self.assertTrue(np.allclose(out[0], [0.0, 0.0, 0.0, 1.0]))
        self.assertTrue(np.allclose(out[1], [0.1, 0.2, 0.3, 0.4]))
