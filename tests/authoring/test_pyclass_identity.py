"""Logical class identity (``_pyClass``): plug accessors, import-on-wrap,
scoped ``ls()``, auto-stamp on create, and ``.mpn`` round-trip.

Spec: docs/superpowers/specs/2026-07-05-pyclass-logical-node-identity-design.md
"""

from __future__ import annotations

import ast
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


# A real, importable MPyNode subclass used by the import-on-wrap / ls / stamp
# tests. Its dotted path is stable: this test module is always importable.
from mpynode.wrappers._mpy_node import MPyNode  # noqa: E402


class _PyClassSub(MPyNode):
    """Test-only logical subclass of MPyNode (native type stays mPyNode)."""


_SUB_PATH = "tests.authoring.test_pyclass_identity._PyClassSub"


# Logical subclasses of every SUBTYPE wrapper -- the auto-stamp on create()
# must fire for these exactly as it does for a bare-MPyNode subclass, no matter
# which subtype ``create()`` override built the node (W3/W4 faithfulness).
from mpynode import (  # noqa: E402
    MPyBlendShape,
    MPyDeformer,
    MPyFile,
    MPyIkSolver,
    MPyLocator,
    MPyMesh,
    MPyNurbsCurve,
    MPyNurbsSurface,
    MPySkinCluster,
    MPyTransform,
)


class _MeshSub(MPyMesh):
    pass


class _LocSub(MPyLocator):
    pass


class _XformSub(MPyTransform):
    pass


class _DeformSub(MPyDeformer):
    pass


class _IkSub(MPyIkSolver):
    pass


class _FileSub(MPyFile):
    pass


class _CurveSub(MPyNurbsCurve):
    pass


class _SurfSub(MPyNurbsSurface):
    pass


class _BlendSub(MPyBlendShape):
    pass


class _SkinSub(MPySkinCluster):
    pass


def _dotted(cls):
    return cls.__module__ + "." + cls.__qualname__


# ---------------------------------------------------------------------------
# Task 1: _pyClass plug accessors + module helpers
# ---------------------------------------------------------------------------
class TestPyClassAccessors(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_unset_returns_none(self):
        n = MPyNode.create(name="pcaccessor1")
        self.assertIsNone(n.get_py_class())

    def test_set_then_get(self):
        n = MPyNode.create(name="pcaccessor2")
        n.set_py_class("some.module.Thing")
        self.assertEqual(n.get_py_class(), "some.module.Thing")

    def test_set_persists_as_hidden_string_plug(self):
        n = MPyNode.create(name="pcaccessor3")
        n.set_py_class("a.B")
        self.assertTrue(
            mc.attributeQuery("class_path", node=n.get_name(), exists=True))
        self.assertEqual(
            mc.getAttr(n.get_name() + ".class_path", type=True), "string")

    def test_clear_reverts_to_none(self):
        n = MPyNode.create(name="pcaccessor4")
        n.set_py_class("a.B")
        n.clear_py_class()
        self.assertIsNone(n.get_py_class())

    def test_set_empty_is_none(self):
        n = MPyNode.create(name="pcaccessor5")
        n.set_py_class("a.B")
        n.set_py_class("")
        self.assertIsNone(n.get_py_class())

    def test_module_helper_read_py_class(self):
        from mpynode.wrappers._mpy_node import _read_py_class

        n = MPyNode.create(name="pcaccessor6")
        self.assertIsNone(_read_py_class(n.get_name()))
        n.set_py_class("x.Y")
        self.assertEqual(_read_py_class(n.get_name()), "x.Y")

    def test_module_helper_import_py_class(self):
        from mpynode.wrappers._mpy_node import _import_py_class

        self.assertIsNone(_import_py_class("nonexistent_pkg_zzz.Nope"))
        self.assertIsNone(_import_py_class("mpynode.Nope_not_a_symbol"))
        self.assertIs(_import_py_class(_SUB_PATH), _PyClassSub)


# ---------------------------------------------------------------------------
# Task 2: import-on-wrap (__new__)
# ---------------------------------------------------------------------------
class TestImportOnWrap(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_generic_base_construction_upgrades(self):
        n = MPyNode.create(name="iow1")
        n.set_py_class(_SUB_PATH)
        self.assertIs(type(MPyNode(n.get_name())), _PyClassSub)

    def test_wrap_node_upgrades(self):
        from mpynode._node_registry import wrap_node

        n = MPyNode.create(name="iow2")
        n.set_py_class(_SUB_PATH)
        wrapped = wrap_node(n.get_name(), "mPyNode")
        self.assertIs(type(wrapped), _PyClassSub)

    def test_unimportable_falls_back_to_root(self):
        n = MPyNode.create(name="iow3")
        n.set_py_class("no_such_pkg_zzz.Nope")
        w = MPyNode(n.get_name())
        self.assertIs(type(w), MPyNode)
        # Plug string preserved for display / ls fallback.
        self.assertEqual(w.get_py_class(), "no_such_pkg_zzz.Nope")

    def test_untagged_wraps_as_root(self):
        n = MPyNode.create(name="iow4")
        self.assertIs(type(MPyNode(n.get_name())), MPyNode)


# ---------------------------------------------------------------------------
# Task 3: base ls() classmethod (scoped by native type + logical class)
# ---------------------------------------------------------------------------
class TestLs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_base_ls_returns_all_native_type(self):
        from mpynode import MPyLocator

        a = MPyNode.create(name="lsBare1")
        b = MPyNode.create(name="lsSub1")
        b.set_py_class(_SUB_PATH)
        loc = MPyLocator.create(name="lsLoc1")
        names = set(w.get_name() for w in MPyNode.ls())
        self.assertIn(a.get_name(), names)
        self.assertIn(b.get_name(), names)
        self.assertNotIn(loc.get_name(), names)

    def test_subclass_ls_filters_to_subclass(self):
        a = MPyNode.create(name="lsBare2")
        b = MPyNode.create(name="lsSub2")
        b.set_py_class(_SUB_PATH)
        got = _PyClassSub.ls()
        self.assertTrue(got)
        self.assertTrue(all(isinstance(w, _PyClassSub) for w in got))
        names = set(w.get_name() for w in got)
        self.assertIn(b.get_name(), names)
        self.assertNotIn(a.get_name(), names)

    def test_locator_ls_disjoint_from_mpynode(self):
        from mpynode import MPyLocator

        n = MPyNode.create(name="lsBare3")
        MPyLocator.create(name="lsLoc3")
        loc_names = set(w.get_name() for w in MPyLocator.ls())
        node_names = set(w.get_name() for w in MPyNode.ls())
        self.assertFalse(loc_names & node_names)
        self.assertIn(n.get_name(), node_names)


# ---------------------------------------------------------------------------
# Task 4: auto-stamp _pyClass on create()/build()
# ---------------------------------------------------------------------------
class TestAutoStamp(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_subclass_create_stamps_py_class(self):
        n = _PyClassSub.create(name="stamp1")
        self.assertEqual(n.get_py_class(), _SUB_PATH)

    def test_subclass_build_stamps_py_class(self):
        n = _PyClassSub.build(name="stamp2")
        self.assertEqual(n.get_py_class(), _SUB_PATH)

    def test_base_create_does_not_stamp(self):
        n = MPyNode.create(name="stamp3")
        self.assertIsNone(n.get_py_class())

    def test_root_wrapper_create_does_not_stamp(self):
        from mpynode import MPyLocator

        n = MPyLocator.create(name="stamp4")
        self.assertIsNone(n.get_py_class())

    def test_subtype_subclass_create_stamps_py_class(self):
        """W3/W4: a user subclass of a SUBTYPE wrapper (mesh, locator,
        transform, deformer, ...) must stamp ``_pyClass`` on ``create()``
        exactly like a bare-MPyNode subclass. Every subtype ``create()``
        override must inherit/apply the base stamp -- none may bypass it."""
        cases = [
            (_MeshSub, {"name": "msMesh"}),
            (_LocSub, {"name": "msLoc"}),
            (_XformSub, {"name": "msXform"}),
            (_DeformSub, {"name": "msDef"}),
            (_IkSub, {"name": "msIk"}),
            (_FileSub, {"name": "msFile"}),
            (_CurveSub, {"name": "msCurve"}),
            (_SurfSub, {"name": "msSurf"}),
            (_BlendSub, {"name": "msBlend"}),
            (_SkinSub, {"name": "msSkin"}),
        ]
        for sub_cls, kw in cases:
            n = sub_cls.create(**kw)
            self.assertEqual(
                n.get_py_class(),
                _dotted(sub_cls),
                f"{sub_cls.__name__}.create() did not stamp _pyClass",
            )

    def test_subtype_subclass_build_stamps_py_class(self):
        """``build()`` funnels through the subtype ``create()`` override, so
        the stamp must survive that path too."""
        n = _MeshSub.build(name="msMeshBuild")
        self.assertEqual(n.get_py_class(), _dotted(_MeshSub))

    def test_deformer_subclass_create_on_stamps_py_class(self):
        """The deformer's second constructor (``create_on``) must also stamp."""
        sph = mc.polySphere(constructionHistory=False)[0]
        n = _DeformSub.create_on(sph, name="msDefOn")
        self.assertEqual(n.get_py_class(), _dotted(_DeformSub))

    def test_subtype_root_wrapper_create_does_not_stamp(self):
        """A ROOT subtype wrapper (not a user subclass) must stay unstamped."""
        for root_cls, kw in (
            (MPyMesh, {"name": "rootMesh"}),
            (MPyTransform, {"name": "rootXform"}),
            (MPyFile, {"name": "rootFile"}),
        ):
            n = root_cls.create(**kw)
            self.assertIsNone(
                n.get_py_class(),
                f"{root_cls.__name__}.create() wrongly stamped _pyClass",
            )


# ---------------------------------------------------------------------------
# Task 5: .mpn round-trip of py_class
# ---------------------------------------------------------------------------
class TestMpnRoundTrip(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_serialize_captures_py_class(self):
        from mpynode._common.io.mpn_io import serialize_node

        n = MPyNode.create(name="mpn1")
        n.set_py_class(_SUB_PATH)
        payload = serialize_node(n)
        self.assertEqual(payload.get("class_path"), _SUB_PATH)

    def test_serialize_omits_when_unset(self):
        from mpynode._common.io.mpn_io import serialize_node

        n = MPyNode.create(name="mpn2")
        payload = serialize_node(n)
        self.assertNotIn("class_path", payload)
        self.assertNotIn("py_class", payload)

    def test_deserialize_restores_and_upgrades(self):
        from mpynode._common.io.mpn_io import deserialize_node, serialize_node

        src = MPyNode.create(name="mpn3")
        src.set_py_class(_SUB_PATH)
        payload = serialize_node(src)
        mc.delete(src.get_name())
        new = deserialize_node(payload, name="mpn3restored")
        self.assertEqual(new.get_py_class(), _SUB_PATH)
        # Re-wrapping the restored node upgrades it to the logical subclass.
        self.assertIs(type(MPyNode(new.get_name())), _PyClassSub)


# ---------------------------------------------------------------------------
# Task 6: display_label() helper (lowercase-first, uniform for built-ins + subs)
# ---------------------------------------------------------------------------
class TestDisplayLabel(unittest.TestCase):
    def test_root_wrapper_names(self):
        from mpynode._node_registry import display_label

        self.assertEqual(display_label("MPyFile"), "mPyFile")
        self.assertEqual(display_label("MPySkinCluster"), "mPySkinCluster")

    def test_user_subclass_name(self):
        from mpynode._node_registry import display_label

        self.assertEqual(display_label("BlackWhiteFile"), "blackWhiteFile")

    def test_empty_string(self):
        from mpynode._node_registry import display_label

        self.assertEqual(display_label(""), "")

    def test_already_lower(self):
        from mpynode._node_registry import display_label

        self.assertEqual(display_label("mPyNode"), "mPyNode")


# ---------------------------------------------------------------------------
# Task 7: bake names the class from identity; base = root wrapper; no ls
# ---------------------------------------------------------------------------
class TestBakeIdentity(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _gen(self, py_node, **kw):
        from mpynode._common.io import py_export

        return py_export.generate_node_script(py_node, **kw)

    def test_explicit_class_name_and_root_base(self):
        n = MPyNode.create(name="bakeWeirdName")
        src = self._gen(n, class_name="BlackWhiteThing")
        self.assertIn("from mpynode import MPyNode", src)
        self.assertIn("class BlackWhiteThing(MPyNode):", src)

    def test_no_ls_emitted(self):
        n = MPyNode.create(name="bakeNoLs")
        src = self._gen(n, class_name="NoLsThing")
        self.assertNotIn("def ls(", src)

    def test_node_name_never_becomes_class_name(self):
        n = MPyNode.create(name="uglyNodeName")
        src = self._gen(n, class_name="CleanName")
        tree = ast.parse(src)
        classdefs = [c.name for c in ast.walk(tree)
                     if isinstance(c, ast.ClassDef)]
        self.assertEqual(classdefs, ["CleanName"])
        self.assertNotIn("UglyNodeName", src)

    def test_subclass_instance_bakes_root_base_and_identity_name(self):
        # A logical subclass node: base is the ROOT wrapper (importable) and the
        # class name comes from the stamped identity, not the live subclass repr.
        n = _PyClassSub.create(name="bakeSub")  # auto-stamps _pyClass
        src = self._gen(n)  # no class_name -> derive from _pyClass short name
        self.assertIn("from mpynode import MPyNode", src)
        self.assertIn("class _PyClassSub(MPyNode):", src)
        self.assertNotIn("from mpynode import _PyClassSub", src)

    def test_baked_source_byte_compiles(self):
        n = MPyNode.create(name="bakeCompile")
        n.add_output_attr("out", "float")
        src = self._gen(n, class_name="CompileThing")
        compile(src, "<baked>", "exec")


# ---------------------------------------------------------------------------
# Task 9: bake class-name resolution (pure) -- tagged reuses identity, untagged
# prompts; a valid entered name also STAMPS the node; cancel aborts.
# ---------------------------------------------------------------------------
class TestBakeNameResolution(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_is_valid_class_name(self):
        from mpynode._common.io.py_export import is_valid_class_name

        self.assertTrue(is_valid_class_name("Foo"))
        self.assertTrue(is_valid_class_name("BlackWhiteFile"))
        self.assertTrue(is_valid_class_name("foo"))  # valid ident (lc = warn only)
        self.assertFalse(is_valid_class_name(""))
        self.assertFalse(is_valid_class_name("3Foo"))
        self.assertFalse(is_valid_class_name("Foo Bar"))
        self.assertFalse(is_valid_class_name("class"))  # keyword
        self.assertFalse(is_valid_class_name(None))

    def test_resolve_reuses_tag_without_prompting(self):
        from mpynode._common.io.py_export import resolve_bake_class_name

        n = MPyNode.create(name="bakeResolveTagged")
        n.set_py_class("__main__.BlackWhiteFile")
        calls = []

        def _prompt():
            calls.append(1)
            return "ShouldNotBeUsed"

        name = resolve_bake_class_name(n, _prompt)
        self.assertEqual(name, "BlackWhiteFile")
        self.assertEqual(calls, [])  # tagged -> never prompts

    def test_resolve_untagged_prompts_and_stamps(self):
        from mpynode._common.io.py_export import resolve_bake_class_name

        n = MPyNode.create(name="uglyBakeName")
        name = resolve_bake_class_name(n, lambda: "CleanName")
        self.assertEqual(name, "CleanName")
        # A valid entered name stamps the node (importable in-memory class) so
        # future bakes reuse it.
        self.assertEqual(n.get_py_class(), "mpynode_user.CleanName")

    def test_resolve_cancel_aborts_and_does_not_stamp(self):
        from mpynode._common.io.py_export import resolve_bake_class_name

        n = MPyNode.create(name="bakeCancel")
        self.assertIsNone(resolve_bake_class_name(n, lambda: None))
        self.assertIsNone(n.get_py_class())

    def test_resolve_never_uses_node_name(self):
        from mpynode._common.io.py_export import resolve_bake_class_name

        n = MPyNode.create(name="uglyNodeName2")
        # Untagged + prompt cancelled -> abort, NOT a fallback to the node name.
        self.assertIsNone(resolve_bake_class_name(n, lambda: None))


if __name__ == "__main__":
    unittest.main()
