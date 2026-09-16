"""User-attribute ADD-ORDER preservation.

Maya appends dynamic attrs in creation order (Channel Box shows add-order), but
the Designer's JSON ``_inputAttrs`` / ``_outputAttrs`` map is stored with
``sort_keys=True`` (deterministic .ma diffs), and several consumers iterated it
alphabetically -- so a node authored ``width, height, density`` displayed and
exported as ``density, height, width``.

These tests pin the fix: an explicit per-attr ``order`` integer that every
surface honors -- the live accessor, the ``.mpn`` exporter/importer, the ``.py``
script generator -- with a fall-back to Maya's true creation order for legacy
maps saved before ``order`` existed.
"""
from __future__ import annotations

import ast
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# A deliberately NON-alphabetical author order; alphabetical would be
# density, frame, height, reset, width.
_AUTHOR_ORDER = ["width", "height", "density", "frame", "reset"]


def _make_node(name="ordNode#"):
    from mpynode.wrappers._mpy_node import MPyNode

    n = MPyNode.create(name=name)
    n.add_input_attr("width",   "int",   default_value=100)
    n.add_input_attr("height",  "int",   default_value=100)
    n.add_input_attr("density", "float", default_value=0.5)
    n.add_input_attr("frame", "time")
    n.add_input_attr("reset", "enum", enum_names=["False", "True"])
    return n


class TestLiveAccessorOrder(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_input_attr_map_preserves_add_order(self):
        n = _make_node()
        self.assertEqual(list(n.get_input_attr_map().keys()), _AUTHOR_ORDER)

    def test_output_attr_map_preserves_add_order(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n     = MPyNode.create(name="outOrd#")
        order = ["gamma", "alpha", "beta"]
        for nm in order:
            n.add_output_attr(nm, "float")
        self.assertEqual(list(n.get_output_attr_map().keys()), order)

    def test_rename_keeps_position(self):
        # Renaming the middle attr must NOT shove it to the end.
        n = _make_node()
        n.rename_input_attr("density", "fill")
        self.assertEqual(
            list(n.get_input_attr_map().keys()),
            ["width", "height", "fill", "frame", "reset"],
        )

    def test_legacy_map_without_order_uses_creation_order(self):
        # Simulate a node saved before ``order`` existed: strip the field from
        # the stored map. The accessor must fall back to Maya's true creation
        # order (the attrs were created in _AUTHOR_ORDER), NOT alphabetical.
        n   = _make_node()
        raw = n._read_input_map()
        for meta in raw.values():
            meta.pop("order", None)
        n._write_input_map(raw)
        # Sanity: the stored map now has no order anywhere.
        self.assertTrue(all("order" not in m for m in n._read_input_map().values()))
        self.assertEqual(list(n.get_input_attr_map().keys()), _AUTHOR_ORDER)


class TestMpnRoundTripOrder(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_serialize_then_deserialize_preserves_order(self):
        from mpynode._common.io.mpn_io import serialize_node, deserialize_node

        n       = _make_node()
        payload = serialize_node(n, include_persistent=False)
        # The payload's metas carry an explicit order field.
        ia = payload["input_attrs"]
        self.assertTrue(all("order" in m for m in ia.values()))
        self.assertEqual(
            sorted(ia, key=lambda k: ia[k]["order"]), _AUTHOR_ORDER
        )
        # And a freshly deserialized node displays the same order.
        mc.file(new=True, force=True)
        rebuilt = deserialize_node(payload, restore_persistent=False)
        self.assertEqual(
            list(rebuilt.get_input_attr_map().keys()), _AUTHOR_ORDER
        )


class TestPyExportOrder(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_generated_script_adds_in_author_order(self):
        from mpynode._common.io import py_export

        n     = _make_node()
        src   = py_export.generate_node_script(n, class_name="OrdRebuilt")
        tree  = ast.parse(src)
        added = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_input_attr"
                and node.args
            ):
                first = node.args[0]
                if isinstance(first, ast.Constant):
                    added.append(first.value)
        self.assertEqual(added, _AUTHOR_ORDER)


if __name__ == "__main__":
    unittest.main()
