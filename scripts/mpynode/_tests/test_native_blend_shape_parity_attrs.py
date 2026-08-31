"""Native codegen: the two plugs that broke Python<->C++ plug parity on a
compiled mPyBlendShape.

A compiled node is supposed to carry every user-facing plug its interpreted twin
has. A converted blendShape carried neither of these, and both failed quietly:

  * ``targetGeometry`` -- mPyBlendShape's OWN framework plug. ``MPxSkinCluster``
    hands a compiled skinCluster ``matrix``/``bindPreMatrix`` for free, but
    ``MPxDeformerNode`` has no ``targetGeometry``, so the compiled node had
    nowhere to land the target meshes and Convert to C++ dropped all 167 target
    connections.

  * ``weight`` keyability -- array inputs are created non-keyable so numeric
    multis stay out of the channel box, and ``MPyNode.KEYABLE_ARRAY_INPUTS``
    opts the few exceptions back in. Codegen never consulted that SSOT, so a
    compiled blendShape's aliased weights were invisible in the channel box.
    Worse, Maya does not write a non-keyable multi's default-valued elements,
    so a save/reload silently LOST them (measured: 167 -> 42).

Both are creation-time properties -- neither ``addAttr -e -keyable`` nor
``setAttr`` on the plug can repair them afterwards -- so they have to be right
in the emitted C++.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _float_array():
    """A float multi input, with the codegen hints normalize_attr adds."""
    from mpynode.native.spec.spec_extractor import normalize_attr
    return normalize_attr({"attr_type": "float", "is_array": True})


def _last_keyable(cpp, plug):
    """The keyability the emitted C++ actually leaves ``plug`` with: the LAST
    setKeyable between its create() and the next one. Maya honours the final
    call, and the emitter deliberately writes several."""
    import re

    body = cpp.split('create("%s", "%s"' % (plug, plug))[1]
    body = re.split(r"= [a-z]Attr\.create\(", body)[0]
    calls = re.findall(r"Attr\.setKeyable\((true|false)\);", body)
    assert calls, "no setKeyable emitted for %r" % plug
    return calls[-1]


def _bs_spec(**over):
    spec = {
        "schema_version": 1,
        "source_node": "bsProbe",
        "mpy_type": "mPyBlendShape",
        "suggested": {"node_type_name": "bsProbe", "class_name": "BsProbe",
                      "mpx_base": "MPxDeformerNode", "type_id": "0x00131a01"},
        "inputs": {"weight": _float_array()},
        "outputs": {},
        "portability": {"portable": True, "blockers": [], "warnings": [],
                        "notes": []},
        "compute": "pass\n",
    }
    spec.update(over)
    return spec


class TestKeyableArrayInputsSsot(unittest.TestCase):
    """Codegen reads the interpreted side's registry rather than re-deciding."""

    def test_blend_shape_exempts_weight(self):
        from mpynode.native.compiler.emit_attr import keyable_array_inputs
        self.assertEqual(set(keyable_array_inputs("mPyBlendShape")), {"weight"})

    def test_other_types_exempt_nothing(self):
        from mpynode.native.compiler.emit_attr import keyable_array_inputs
        for t in ("mPyNode", "mPySkinCluster", "mPyDeformer", "mPyLocator"):
            self.assertEqual(set(keyable_array_inputs(t)), set(),
                             "%s must keep the never-keyable rule" % t)

    def test_an_unknown_type_is_not_an_error(self):
        from mpynode.native.compiler.emit_attr import keyable_array_inputs
        self.assertEqual(set(keyable_array_inputs("notARealType")), set())

    def test_the_registry_matches_the_wrapper_class(self):
        """If the wrapper's exemption list moves, codegen must move with it."""
        from mpynode.native.compiler.emit_attr import keyable_array_inputs
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
        self.assertEqual(set(keyable_array_inputs("mPyBlendShape")),
                         set(MPyBlendShape.KEYABLE_ARRAY_INPUTS))


class TestDeformerBaseFrameworkAttrs(unittest.TestCase):
    def test_blend_shape_gets_target_geometry(self):
        from mpynode.native.compiler.emit_deformer import base_attr_members
        got = base_attr_members(_bs_spec(), [])
        self.assertEqual([m["plug"] for m in got],
                         ["targetGeometry", "liveTargets"])
        m = got[0]
        self.assertEqual(m["kind"], "inputs")
        self.assertTrue(m["meta"]["is_array"])
        self.assertEqual(m["meta"]["type"], "mesh")
        self.assertTrue(m["affects"], "it must drive outputGeom")

    def test_blend_shape_gets_the_live_gate_defaulted_ON(self):
        """The compiled default has to match the interpreted one.

        _api1 creates liveTargets with a True default, so a compiled node
        defaulting to false would silently stop following its target meshes on
        Convert to C++ -- the exact behaviour difference this plug exists to
        make explicit.
        """
        from mpynode.native.compiler.emit_deformer import base_attr_members
        m = [x for x in base_attr_members(_bs_spec(), [])
             if x["plug"] == "liveTargets"][0]
        self.assertEqual(m["kind"], "inputs")
        self.assertEqual(m["meta"]["type"], "bool")
        self.assertIs(m["meta"]["default_value"], True)
        self.assertTrue(m["affects"], "it must drive outputGeom")

    def test_other_types_get_nothing(self):
        from mpynode.native.compiler.emit_deformer import base_attr_members
        for t in ("mPySkinCluster", "mPyDeformer", "mPyNode"):
            self.assertEqual(base_attr_members(_bs_spec(mpy_type=t), []), [])

    def test_a_spec_that_already_declares_it_wins(self):
        """The user/spec attr is emitted anyway -- never declare it twice."""
        from mpynode.native.compiler.emit_deformer import base_attr_members
        spec = _bs_spec()
        spec["inputs"]["targetGeometry"] = {"type": "mesh", "is_array": True}
        spec["inputs"]["liveTargets"] = {"type": "bool"}
        self.assertEqual(base_attr_members(spec, []), [])

    def test_each_framework_plug_is_skipped_independently(self):
        """Declaring one must not suppress the other."""
        from mpynode.native.compiler.emit_deformer import base_attr_members
        spec = _bs_spec()
        spec["inputs"]["targetGeometry"] = {"type": "mesh", "is_array": True}
        self.assertEqual([m["plug"] for m in base_attr_members(spec, [])],
                         ["liveTargets"])

    def test_the_member_name_cannot_collide(self):
        from mpynode.native.compiler.emit_deformer import base_attr_members
        got = base_attr_members(_bs_spec(), [{"member": "aTargetGeometry"}])
        self.assertNotEqual(got[0]["member"], "aTargetGeometry")


class TestEmittedCpp(unittest.TestCase):
    """End to end: what actually lands in the generated C++."""

    @classmethod
    def setUpClass(cls):
        from mpynode.native.compiler import node_scaffold
        cls.cpp = node_scaffold.generate_cpp(_bs_spec(), for_port=True)

    def test_target_geometry_is_declared_added_and_affects_output(self):
        self.assertIn(
            'tAttr.create("targetGeometry", "targetGeometry", MFnData::kMesh)',
            self.cpp)
        self.assertIn("addAttribute(aTargetGeometry);", self.cpp)
        self.assertIn(
            "attributeAffects(aTargetGeometry, MPxGeometryFilter::outputGeom);",
            self.cpp)

    def test_target_geometry_is_not_storable(self):
        """Matches the interpreted declaration: the meshes are a live authoring
        link and the deform reads the BAKED tables, so writing 167 meshes into
        every scene that touches one is not the point."""
        block = self.cpp.split('tAttr.create("targetGeometry"')[1][:400]
        self.assertIn("tAttr.setStorable(false);", block)

    def test_target_geometry_is_an_array(self):
        block = self.cpp.split('tAttr.create("targetGeometry"')[1][:400]
        self.assertIn("tAttr.setArray(true);", block)

    def test_weight_ends_up_keyable(self):
        """Only the LAST setKeyable counts. Every numeric attr gets a default
        setKeyable(true), the array branch overrides it to false, and the
        exemption has to land after BOTH."""
        self.assertEqual(_last_keyable(self.cpp, "weight"), "true")

    def test_a_non_exempt_array_stays_non_keyable(self):
        from mpynode.native.compiler import node_scaffold
        spec = _bs_spec()
        spec["inputs"]["interKnot"] = _float_array()
        cpp = node_scaffold.generate_cpp(spec, for_port=True)
        self.assertEqual(_last_keyable(cpp, "interKnot"), "false")
        self.assertEqual(_last_keyable(cpp, "weight"), "true",
                         "the exemption must still apply alongside it")


if __name__ == "__main__":
    unittest.main()
