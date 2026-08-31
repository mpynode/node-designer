import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestMpnKeys(unittest.TestCase):
    def _make(self):
        from mpynode.wrappers._mpy_node import MPyNode
        n = MPyNode.create(name="keyRename#")
        n.set_py_class("mpynode_user.KeyThing")
        return n

    def test_serialize_uses_new_keys(self):
        from mpynode._common.io.mpn_io import serialize_node
        p = serialize_node(self._make())
        self.assertIn("node_name", p)
        self.assertNotIn("source_name", p)
        self.assertEqual(p.get("class_path"), "mpynode_user.KeyThing")
        self.assertNotIn("py_class", p)

    def test_deserialize_reads_new_keys(self):
        from mpynode._common.io.mpn_io import serialize_node, deserialize_node
        p = serialize_node(self._make())
        n2 = deserialize_node(p, name="keyRenameRestore#")
        self.assertEqual(n2.get_py_class(), "mpynode_user.KeyThing")

    def test_deserialize_ignores_old_keys(self):
        # No back-compat: the dual-read shim is gone, so a legacy payload that
        # carries ONLY the OLD keys no longer restores identity -- ``py_class``
        # (old) is ignored, so no logical class is stamped.
        from mpynode._common.io.mpn_io import deserialize_node
        legacy = {
            "native_type": "mPyNode",
            "source_name": "legacyNode",
            "py_class": "mpynode_user.Legacy",
            "expression": "", "input_attrs": {}, "output_attrs": {},
            "stored_vars": {},
        }
        n = deserialize_node(legacy)
        self.assertNotEqual(n.get_py_class(), "mpynode_user.Legacy")

    def test_source_name_node_name_ignores_old_key(self):
        # The node-name derivation reads ONLY the new ``node_name`` key; a legacy
        # payload carrying only ``source_name`` no longer derives a name (falls
        # through to Maya's default type-based name). Guards the removed
        # ``or ...source_name`` fallback in _source_name_node_name.
        from mpynode._common.io.mpn_io import _source_name_node_name
        self.assertIsNone(_source_name_node_name({"source_name": "legacyNode"}))
        self.assertEqual(_source_name_node_name({"node_name": "keepName"}),
                         "keepName")

    def test_spec_adapter_ignores_old_keys(self):
        # The .mpn -> spec adapter reads ONLY the new keys: an old-key-only
        # payload yields an empty source_node and derives identity from "" (NOT
        # from the legacy ``py_class``). Guards the two removed fallbacks in
        # spec_from_mpn_payload.
        from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload
        from mpynode.native.spec.identity import derive_class_identity
        spec = spec_from_mpn_payload({
            "native_type": "mPyNode",
            "source_name": "foo",
            "py_class": "mpynode_user.Legacy",
            "expression": "", "input_attrs": {}, "output_attrs": {},
            "stored_vars": {},
        })
        self.assertEqual(spec["source_node"], "")
        self.assertEqual(spec["suggested"], derive_class_identity("", "mPyNode"))
