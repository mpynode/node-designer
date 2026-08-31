"""mPyFile compiled-node surface: the VP2 override and the BASE attributes.

Two regressions this locks down, both of which shipped green:

1. ``emit_vp2_override.can_inject`` gated on the AI PORT markers. Once the
   transpiler learned to lower texture reads deterministically, every shipped
   mPyFile compute stopped having a PORT region -- so the injector silently
   no-op'd and each texture node shipped with NO ``MPxShadingNodeOverride``,
   rendering a flat colour in Viewport 2.0. The whole existing VP2 suite stayed
   green because it runs against a hand-written fixture that DOES carry markers.
   These tests drive the real templates through the real spec -> codegen path.

2. A compiled mPyFile only declared the attrs its SPEC captured, so the base
   plug-in surface (uvFilterSize, the sampler presets, outTransparency/outSize,
   the hidden _timeIn, the osl shader output) did not exist on the compiled node
   and ``convert to c++`` dropped every connection into them.
"""

from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init, ensure_plugins_loaded


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# Every shipped mPyFile template -> its node type. The flag is "stateless": Game
# Of Life is the one whose compute mutates persistent state, so it takes the
# hoisted-state path and has its own test below rather than joining these.
_TEMPLATES = [
    ("MPyFile/File Simple", "fileTexture", True),
    ("MPyFile/File Composite", "compositeTexture", True),
    ("MPyFile/File Scanline", "scanlineTex", True),
    ("MPyFile/Game Of Life Texture", "gameOfLifeTex", False),
]

_CREATE_RE = re.compile(r'\.create(?:Color|Point)?\(\s*"(\w+)"')
_AFFECTS_SRC_RE = re.compile(r"attributeAffects\((\w+),")


def _template_path(rel):
    from mpynode._common.util.template_gallery import _bundled_templates_root
    root = _bundled_templates_root()
    assert root, "bundled templates root not found"
    return os.path.join(root, *rel.split("/"), "template.mpn")


def _generate(rel):
    """(spec, generated cpp, cpp after VP2 injection) for one template."""
    from mpynode._common.io import mpn_io
    from mpynode.native.spec import mpn_spec_adapter
    from mpynode.native.compiler import node_scaffold
    from mpynode.native.compiler import emit_vp2_override as vp2
    payload = mpn_io.load_mpn(_template_path(rel), trusted=True)
    spec = mpn_spec_adapter.spec_from_mpn_payload(payload)
    cpp = node_scaffold.generate_cpp(spec, for_port=False)
    return spec, cpp, vp2.inject_vp2_override(cpp, spec)


def _ssot_plugs():
    """Every plug the interpreted mPyFile registers: the preset SSOT (parents +
    children) plus the two base plugs registered outside it."""
    from mpynode._common.interface import file_texture_interface as fti
    names, auto_color = [], set()
    for e in fti.FILE_TEXTURE_ATTRS:
        names.append(e["long"])
        names += [c["long"] for c in e.get("children", [])]
        if e["attr_type"] == "color":
            auto_color |= {c["long"] for c in e["children"]}
    return names + ["_timeIn", "osl"], auto_color


class TestVp2InjectionFiresOnShippedTemplates(unittest.TestCase):
    """The regression guard: a DETERMINISTICALLY-LOWERED texture must still get
    its override. Anchoring only on the PORT markers is what turned this off."""

    def test_stateless_textures_get_an_override(self):
        for rel, ty, want in _TEMPLATES:
            if not want:
                continue
            with self.subTest(template=rel):
                _spec, cpp, inj = _generate(rel)
                from mpynode.native.compiler import emit_vp2_override as vp2
                self.assertEqual(vp2.skip_reason(cpp), "",
                                 "%s must be injectable" % ty)
                self.assertIn("MPxShadingNodeOverride", inj)
                self.assertIn("registerShadingNodeOverrideCreator", inj)
                self.assertNotEqual(inj, cpp, "injection was a no-op")

    def test_lowered_compute_has_no_port_markers(self):
        """Proves the guard above is testing what it claims: these computes have
        no PORT region at all, so a marker-only gate WOULD refuse them."""
        from mpynode.native.compiler import emit_vp2_override as vp2
        for rel, ty, want in _TEMPLATES:
            if not want:
                continue
            with self.subTest(template=rel):
                _spec, cpp, _inj = _generate(rel)
                self.assertNotIn(vp2._PORT_BEGIN, cpp)
                self.assertIsNotNone(vp2._lowered_region(cpp),
                                     "%s should be a lowered compute" % ty)

    def test_bake_and_compute_share_one_texel_fn(self):
        """VP2 == compute by construction: exactly one nd_texel definition, and
        both compute() and the override's bake loop call it."""
        for rel, ty, want in _TEMPLATES:
            if not want:
                continue
            with self.subTest(template=rel):
                _spec, _cpp, inj = _generate(rel)
                self.assertEqual(inj.count("static void nd_texel("), 1)
                self.assertGreaterEqual(inj.count("nd_texel("), 3)

    def test_stateful_texture_gets_an_override_with_hoisted_state(self):
        """A compute that mutates persistent per-instance state USED to be
        refused here, on the grounds that the shared ``nd_texel`` is emitted
        ABOVE the node class and so cannot reach a member. That refusal was the
        bug: the texture CLASSIFICATION string is emitted by the same module, so
        declining also cost the node its classification, and Viewport 2.0 filled
        the whole surface with one flat ``outColor`` sample.

        The state is now hoisted out of the class and threaded into ``nd_texel``
        by reference -- exactly how ``_texCache``/``_texMutex`` were already
        passed -- so the stateful texture shades per-pixel like the others."""
        from mpynode.native.compiler import emit_vp2_override as vp2
        _spec, cpp, inj = _generate("MPyFile/Game Of Life Texture")
        self.assertIn("_NdState", cpp)
        self.assertEqual(vp2.skip_reason(cpp), "",
                         "the stateful texture must now be injectable")
        self.assertNotEqual(inj, cpp, "injection was a no-op")
        self.assertIn("MPxShadingNodeOverride", inj)
        self.assertIn("registerShadingNodeOverrideCreator", inj)
        # Still exactly ONE texel definition, taking the state by reference, and
        # the struct sits above it. That ordering IS the fix -- emit the struct
        # inside the class and this stops compiling.
        self.assertEqual(inj.count("static void nd_texel("), 1)
        self.assertIn("_NdState& _ndState", inj)
        self.assertLess(inj.index("struct _NdState"),
                        inj.index("static void nd_texel("))


class TestFileBaseAttributeSurface(unittest.TestCase):
    """Every compiled mPyFile carries the interpreted node's whole plug surface."""

    def test_every_base_plug_is_created(self):
        want, auto_color = _ssot_plugs()
        for rel, ty, _v in _TEMPLATES:
            with self.subTest(template=rel):
                _spec, cpp, _inj = _generate(rel)
                have = set(_CREATE_RE.findall(cpp)) | auto_color
                missing = [w for w in want if w not in have]
                self.assertEqual(missing, [], "%s is missing base plugs" % ty)

    def test_non_fragment_plugs_never_drive_the_affects_graph(self):
        """uvFilterSize / _timeIn / osl on the SOURCE side make Maya 2026's VP2
        fragment compiler reject the texture binding (white viewport, black
        swatch). The interpreted node excludes them; so must the compiled one."""
        for rel, ty, _v in _TEMPLATES:
            with self.subTest(template=rel):
                _spec, cpp, _inj = _generate(rel)
                srcs = set(_AFFECTS_SRC_RE.findall(cpp))
                for banned in ("aUvFilterSize", "a_timeIn", "aOsl"):
                    self.assertNotIn(banned, srcs,
                                     "%s: %s must not affect an output"
                                     % (ty, banned))

    def test_derived_outputs_are_written_and_reachable(self):
        """outTransparency / outSize are DERIVED, never authored by the compute
        -- so the tail must write them AND the plug guard must accept a pull on
        them, or a shader reading only .transparency gets a stale value."""
        for rel, ty, _v in _TEMPLATES:
            with self.subTest(template=rel):
                _spec, cpp, _inj = _generate(rel)
                self.assertIn("aOutTransparency", cpp)
                self.assertIn("_hOT.set3Float(_ndT, _ndT, _ndT);", cpp)
                self.assertIn("_hOS.set2Float(_ndW, _ndH);", cpp)
                guard = cpp.split("compute(const MPlug& plug", 1)[1]
                guard = guard.split("return MS::kUnknownParameter;", 1)[0]
                self.assertIn("plug != aOutTransparency", guard)
                self.assertIn("plug != aOutSize", guard)

    def test_transparency_is_one_minus_alpha_clamped(self):
        _spec, cpp, _inj = _generate("MPyFile/File Simple")
        self.assertIn("float _ndA = h_aOutAlpha.asFloat();", cpp)
        self.assertIn("const float _ndT = 1.0f - _ndA;", cpp)

    def test_enum_defaults_come_from_the_ssot(self):
        """filterMode -> Anisotropic (2), mipmapMode -> Auto (1). A dropped
        default silently registers Point / None instead."""
        _spec, cpp, _inj = _generate("MPyFile/File Simple")
        self.assertIn('eAttr.create("filterMode", "filterMode", 2)', cpp)
        self.assertIn('eAttr.create("mipmapMode", "mipmapMode", 1)', cpp)

    def test_base_surface_is_mpyfile_only(self):
        """The gate is mpy_type -- no other node type grows plugs."""
        from mpynode.native.compiler.kernels import file_texture_cpp
        for mt in ("mPyNode", "mPyMesh", "mPyLocator", "mPyDeformer", None):
            self.assertEqual(
                file_texture_cpp.base_attr_members({"mpy_type": mt}, []), [])


class TestOptimizerKeepsTheVp2Surface(unittest.TestCase):
    """The optimizer is allowed to rewrite an mPyFile now. Compute parity covers
    nd_texel (compute calls it), but NOT the override surface -- a candidate that
    deleted it would still pass parity and ship shading flat."""

    def _baseline(self):
        _spec, _cpp, inj = _generate("MPyFile/File Simple")
        return inj

    def test_untouched_candidate_is_accepted(self):
        from mpynode.native.ai import optimizer_knowledge as ok
        base = self._baseline()
        self.assertIsNone(ok.implausible_reason(base, base))

    def test_dropping_the_override_is_rejected(self):
        from mpynode.native.ai import optimizer_knowledge as ok
        base = self._baseline()
        for tok in ("MPxShadingNodeOverride", "registerShadingNodeOverrideCreator",
                    "outputForConnection", "nd_texel", "updateShader"):
            with self.subTest(token=tok):
                why = ok.implausible_reason(base.replace(tok, "_gone_"), base)
                self.assertIsNotNone(why, "%s may not be dropped silently" % tok)
                self.assertIn(tok, why)

    def test_anchor_check_is_baseline_calibrated(self):
        """A node with no override contains none of the tokens, so it can never
        be false-flagged by them."""
        from mpynode.native.ai import optimizer_knowledge as ok
        plain = ("MStatus initializePlugin(MObject o) { return MS::kSuccess; }\n"
                 "MStatus uninitializePlugin(MObject o) { return MS::kSuccess; }\n")
        self.assertIsNone(ok.implausible_reason(plain, plain))


if __name__ == "__main__":
    unittest.main()
