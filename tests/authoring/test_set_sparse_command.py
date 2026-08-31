"""_SetSparseCommand: toggle a user input ARRAY's ``sparse`` read flag.

Pure metadata edit -- rewrites the ``_inputAttrs`` JSON; the Maya plug is
untouched, so connections / element values are preserved. The ``mc.setAttr``
that persists the map rides Maya's undo chunk, so ``undoIt``/``redoIt`` are
no-ops (same contract as ``_SetAttrColorCommand``). Input arrays only.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestSetSparseCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode.wrappers._mpy_node import MPyNode

        self.MPyNode = MPyNode

    def test_toggle_sets_meta(self):
        from mpynode._base.commands import _SetSparseCommand, run_undoable

        n = self.MPyNode.create(name="sp1")
        n.add_input_attr("d", "float", is_array=True)
        self.assertFalse(n.get_input_attr_map()["d"].get("sparse", False))
        run_undoable(_SetSparseCommand(n, "d", True))
        self.assertTrue(n.get_input_attr_map()["d"]["sparse"])
        run_undoable(_SetSparseCommand(n, "d", False))
        # Toggling off drops the key (deviation-only invariant).
        self.assertFalse(n.get_input_attr_map()["d"].get("sparse", False))

    def test_toggle_preserves_connections_and_values(self):
        from mpynode._base.commands import _SetSparseCommand, run_undoable

        n = self.MPyNode.create(name="sp2")
        n.add_input_attr("d", "float", is_array=True)
        mc.setAttr(n.get_name() + ".d[2]", 9.0)
        src = mc.createNode("transform", name="drv")
        mc.connectAttr(src + ".translateX", n.get_name() + ".d[5]", force=True)
        run_undoable(_SetSparseCommand(n, "d", True))
        # Plug untouched: element [2] value + [5] connection survive.
        self.assertEqual(mc.getAttr(n.get_name() + ".d[2]"), 9.0)
        self.assertTrue(
            mc.isConnected(src + ".translateX", n.get_name() + ".d[5]")
        )

    def test_undo_restores_previous_flag(self):
        from mpynode._base.commands import _SetSparseCommand, run_undoable

        n = self.MPyNode.create(name="sp3")
        n.add_input_attr("d", "float", is_array=True)
        run_undoable(_SetSparseCommand(n, "d", True))
        self.assertTrue(n.get_input_attr_map()["d"]["sparse"])
        mc.undo()
        self.assertFalse(n.get_input_attr_map()["d"].get("sparse", False))

    def test_non_array_rejected(self):
        from mpynode._base.commands import _SetSparseCommand, run_undoable

        n = self.MPyNode.create(name="sp4")
        n.add_input_attr("s", "float")  # scalar
        with self.assertRaises(Exception):
            run_undoable(_SetSparseCommand(n, "s", True))

    def test_mpn_roundtrip(self):
        from mpynode._common.io import mpn_io

        n = self.MPyNode.create(name="sp5")
        n.add_input_attr("d", "float", is_array=True, sparse=True)
        n.add_input_attr("e", "float", is_array=True)  # non-sparse
        payload = mpn_io.serialize_node(n)

        n2 = self.MPyNode.create(name="sp5b")
        mpn_io.apply_payload_to_node(n2, payload)
        self.assertTrue(n2.get_input_attr_map()["d"]["sparse"])
        self.assertFalse(n2.get_input_attr_map()["e"].get("sparse", False))
