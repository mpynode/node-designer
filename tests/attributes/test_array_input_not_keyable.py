"""Array INPUTs must not be keyable.

Scalar-numeric multi inputs (float / int / bool) created keyable leak into the
channel box; compound (vector/euler) and dt-typed arrays never display there.
An array input should be absent from BOTH channel-box sections (keyable and
non-keyable "displayable") yet still exist -- so it stays editable in the
Attribute Editor. Single (non-array) inputs are unchanged: keyable, in the CB.
"""

from __future__ import annotations

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestArrayInputNotKeyable(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _make(self, name):
        from mpynode.wrappers._mpy_node import MPyNode

        return MPyNode.create(name=name)

    def _assert_not_in_channel_box(self, node, attr):
        self.assertTrue(
            mc.attributeQuery(attr, node=node, exists=True),
            "%s.%s should still exist (Attribute-Editor visible)" % (node, attr),
        )
        self.assertFalse(
            mc.attributeQuery(attr, node=node, keyable=True),
            "%s.%s must not be keyable (channel-box leak)" % (node, attr),
        )
        self.assertNotIn(attr, mc.listAttr(node, keyable=True) or [])
        self.assertNotIn(attr, mc.listAttr(node, channelBox=True) or [])

    def test_float_array_input_not_keyable(self):
        n = self._make("fa")
        n.add_input_attr("w", "float", is_array=True)
        self._assert_not_in_channel_box(n.get_name(), "w")

    def test_int_array_input_not_keyable(self):
        n = self._make("ia")
        n.add_input_attr("w", "int", is_array=True)
        self._assert_not_in_channel_box(n.get_name(), "w")

    def test_bool_array_input_not_keyable(self):
        n = self._make("ba")
        n.add_input_attr("w", "bool", is_array=True)
        self._assert_not_in_channel_box(n.get_name(), "w")

    def test_single_float_input_stays_keyable(self):
        n = self._make("sf")
        n.add_input_attr("g", "float")
        node = n.get_name()
        self.assertTrue(mc.attributeQuery("g", node=node, keyable=True))
        self.assertIn("g", mc.listAttr(node, keyable=True) or [])


if __name__ == "__main__":
    unittest.main()
