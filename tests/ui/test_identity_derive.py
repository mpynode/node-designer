import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


class TestPascalValidator(unittest.TestCase):
    def test_accepts_pascal(self):
        from mpynode._common.io.py_export import is_pascal_class_name
        self.assertTrue(is_pascal_class_name("Procrustes"))
        self.assertTrue(is_pascal_class_name("BlackWhiteFile"))

    def test_rejects_lower_first(self):
        from mpynode._common.io.py_export import is_pascal_class_name
        self.assertFalse(is_pascal_class_name("procrustes"))

    def test_rejects_non_identifier_and_keyword(self):
        from mpynode._common.io.py_export import is_pascal_class_name
        self.assertFalse(is_pascal_class_name("9x"))
        self.assertFalse(is_pascal_class_name("has space"))
        self.assertFalse(is_pascal_class_name("class"))  # keyword (also lower)
        self.assertFalse(is_pascal_class_name(""))
        self.assertFalse(is_pascal_class_name(None))


class TestBakeStamp(unittest.TestCase):
    def test_prompt_stamps_mpynode_user_not_main(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io.py_export import resolve_bake_class_name
        n = MPyNode.create(name="bakeStamp#")
        got = resolve_bake_class_name(n, prompt_fn=lambda: "Widget")
        self.assertEqual(got, "Widget")
        self.assertEqual(n.get_py_class(), "mpynode_user.Widget")

    def test_existing_class_not_reprompted(self):
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io.py_export import resolve_bake_class_name
        n = MPyNode.create(name="bakeStamp2#")
        n.set_py_class("mpynode_user.Already")

        def _boom():
            raise AssertionError("should not prompt")

        self.assertEqual(resolve_bake_class_name(n, _boom), "Already")


class TestDeriveIdentity(unittest.TestCase):
    def test_class_name_preserves_pascal(self):
        from mpynode.native.spec.identity import derive_class_identity
        s = derive_class_identity("mpynode_user.Procrustes", "mPyNode")
        self.assertEqual(s["class_name"], "Procrustes")
        self.assertEqual(s["node_type_name"], "procrustes")

    def test_override_wins_and_class_name_unchanged(self):
        from mpynode.native.spec.identity import derive_class_identity
        s = derive_class_identity("mpynode_user.Procrustes", "mPyNode",
                                  node_type_name_override="procrustesSolver")
        self.assertEqual(s["node_type_name"], "procrustesSolver")
        self.assertEqual(s["class_name"], "Procrustes")

    def test_includes_mpx_base_and_type_id(self):
        from mpynode.native.spec.identity import derive_class_identity
        s = derive_class_identity("mpynode_user.Foo", "mPyNode")
        self.assertIn("mpx_base", s)
        self.assertIn("type_id", s)

    def test_bare_class_path(self):
        from mpynode.native.spec.identity import derive_class_identity
        s = derive_class_identity("Widget", "mPyNode")
        self.assertEqual(s["class_name"], "Widget")

    def test_transitional_instance_name_upper_first(self):
        # A class-less transitional path passes an instance name; class_name
        # must upper-first (byte-identical to the old derivation).
        from mpynode.native.spec.identity import derive_class_identity
        s = derive_class_identity("equiv_node", "mPyNode")
        self.assertEqual(s["class_name"], "Equiv_node")
        self.assertEqual(s["node_type_name"], "equiv_node")


class TestSpecParity(unittest.TestCase):
    def setUp(self):
        ensure_plugins_loaded()

    def test_live_and_mpn_suggested_identical(self):
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode._common.io.mpn_io import serialize_node
        from mpynode.native.spec import spec_extractor, mpn_spec_adapter

        mc.file(new=True, force=True)
        n = MPyNode.create(name="parityNode#")
        n.set_py_class("mpynode_user.ParityClass")
        n.set_compute_expression("out = x")

        live = spec_extractor.extract_spec(n.get_name())
        payload = serialize_node(n)
        frommpn = mpn_spec_adapter.spec_from_mpn_payload(payload)
        self.assertEqual(live["suggested"]["node_type_name"], "parityClass")
        self.assertEqual(live["suggested"], frommpn["suggested"])

    def test_two_instances_one_class_same_type(self):
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.native.spec import spec_extractor

        mc.file(new=True, force=True)
        a = MPyNode.create(name="alpha#"); a.set_py_class("mpynode_user.Shared")
        b = MPyNode.create(name="beta#");  b.set_py_class("mpynode_user.Shared")
        sa = spec_extractor.extract_spec(a.get_name())
        sb = spec_extractor.extract_spec(b.get_name())
        self.assertEqual(sa["suggested"]["node_type_name"],
                         sb["suggested"]["node_type_name"])
        self.assertEqual(sa["suggested"]["node_type_name"], "shared")


class TestPorterApplyTypeName(unittest.TestCase):
    def test_override_sets_name_and_class_not_type_id(self):
        from mpynode.native.ai import porter
        spec = {"suggested": {"node_type_name": "orig", "class_name": "Orig",
                              "type_id": "0x00070001", "mpx_base": "MPxNode"}}
        porter.apply_type_name(spec, "myThing")
        self.assertEqual(spec["suggested"]["node_type_name"], "myThing")
        self.assertEqual(spec["suggested"]["class_name"], "MyThing")
        self.assertEqual(spec["suggested"]["type_id"], "0x00070001")  # preserved

    def test_falsy_is_noop(self):
        from mpynode.native.ai import porter
        spec = {"suggested": {"node_type_name": "orig", "class_name": "Orig"}}
        porter.apply_type_name(spec, "")
        self.assertEqual(spec["suggested"]["node_type_name"], "orig")
