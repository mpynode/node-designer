"""The declarative mPyFile interface SSOT (``_common/interface/file_texture_interface``).

Guards the refactor that retires the side-effecting transient ``createNode("mPyFile")``
interface capture: one declarative table now feeds BOTH the api2 node registration AND the
native porter. The porter projection MUST stay byte-identical to the old pinned
``_MPYFILE_PRESET_META`` (else every mPyFile-derived node re-ports), and the table MUST
match what a live mPyFile actually registers (the drift guard, now by construction).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from mpynode._common.interface import file_texture_interface as iface


class TestPorterProjection(unittest.TestCase):
    """The projection reproduces the porter's raw-meta table byte-identically (Maya-free)."""

    def test_matches_static_table(self):
        from mpynode.native.spec import spec_extractor as se
        derived = iface.build_porter_meta_table()
        self.assertEqual(
            derived, se._MPYFILE_PRESET_META,
            "porter projection drifted from _MPYFILE_PRESET_META -> port_cache churn")

    def test_projection_shape_minimal(self):
        # Non-enum presets carry ONLY {attr_type,_writable,_readable} -- no
        # default/min/max leaking in, so their normalized specs (and therefore
        # their port_cache keys) stay byte-identical. Enums additionally carry
        # enum_names + default_value: codegen BAKES the default field index into
        # eAttr.create, so it genuinely changes the generated C++ and a key miss
        # there is the port_cache contract working, not churn.
        # float2 additionally carries `children`, for the same reason: codegen
        # otherwise synthesizes <plug>X/<plug>Y, and uvCoord's children are
        # uCoord/vCoord -- without it a compiled mPyFile has no uCoord plug at
        # all, so the key miss there is likewise the contract working.
        allowed        = {"attr_type", "_writable", "_readable"}
        allowed_enum   = allowed | {"enum_names", "default_value"}
        allowed_float2 = allowed | {"children"}
        extra          = {"enum": allowed_enum, "float2": allowed_float2}
        for nm, meta in iface.build_porter_meta_table().items():
            ok = extra.get(meta["attr_type"], allowed)
            self.assertTrue(set(meta).issubset(ok),
                            "%s meta has extra keys: %s" % (nm, set(meta) - ok))

    def test_enum_defaults_are_projected(self):
        # The SSOT default field index must reach the porter -- without it a
        # compiled mPyFile registers filterMode=Point / mipmapMode=None.
        t = iface.build_porter_meta_table()
        self.assertEqual(t["filterMode"]["default_value"], iface.kFilterAnisotropic)
        self.assertEqual(t["mipmapMode"]["default_value"], iface.kMipmapAuto)
        self.assertEqual(t["preFilterKernel"]["default_value"],
                         iface.kPreFilterGaussian)
        self.assertEqual(t["wrapModeU"]["default_value"],  iface.kWrapWrap)
        self.assertEqual(t["wrapModeV"]["default_value"],  iface.kWrapWrap)
        self.assertEqual(t["colorSpace"]["default_value"], 0)

    def test_every_enum_default_matches_its_declared_entry(self):
        t = iface.build_porter_meta_table()
        for e in iface.FILE_TEXTURE_ATTRS:
            if e["attr_type"] != "enum":
                continue
            self.assertEqual(t[e["long"]]["default_value"], e["default"],
                             "%s default drifted from the SSOT" % e["long"])

    def test_codegen_bakes_the_ssot_enum_default(self):
        """End-to-end through the real normalizer + emitter: the third
        ``eAttr.create`` argument IS the default field index."""
        from mpynode.native.compiler import emit_attr
        from mpynode.native.spec import spec_extractor as se

        table = iface.build_porter_meta_table()
        for nm, expected in (("filterMode", 2), ("mipmapMode", 1),
                             ("preFilterKernel", 3), ("colorSpace", 0)):
            raw = dict(table[nm])
            raw.pop("_writable")
            raw.pop("_readable")
            line = emit_attr._create_lines(
                {"plug": nm, "member": "aX", "kind": "inputs",
                 "meta": se.normalize_attr(raw)})[0]
            self.assertIn('eAttr.create("%s", "%s", %d);' % (nm, nm, expected),
                          line, "wrong baked default for %s: %s" % (nm, line))

    def test_directions_route_correctly(self):
        t = iface.build_porter_meta_table()
        self.assertFalse(t["outColor"]["_writable"])  # output
        self.assertFalse(t["outAlpha"]["_writable"])
        self.assertTrue(t["uvCoord"]["_writable"])    # input
        self.assertTrue(t["fileName"]["_writable"])
        self.assertTrue(t["borderColor"]["_writable"])
        self.assertTrue(all(m["_readable"] for m in t.values()))


class TestSchemaInvariants(unittest.TestCase):
    """Structural invariants the consumers rely on (Maya-free)."""

    def test_filename_declared_first(self):
        # Swatch generator hint: fileName must be the first declared attr.
        self.assertEqual(iface.FILE_TEXTURE_ATTRS[0]["long"], "fileName")

    def test_compounds_have_children(self):
        for e in iface.FILE_TEXTURE_ATTRS:
            if e["attr_type"] == "float2":
                self.assertEqual(len(e["children"]), 2, e["long"])
            if e["attr_type"] == "color":
                self.assertEqual(len(e["children"]), 3, e["long"])
                self.assertTrue(e["flags"].get("used_as_color"), e["long"])

    def test_no_colon_in_enum_labels(self):
        for e in iface.FILE_TEXTURE_ATTRS:
            if e["attr_type"] == "enum":
                for label in iface.enum_labels(e):
                    self.assertNotIn(":", label, "%s: %r" % (e["long"], label))

    def test_colorspace_is_25(self):
        self.assertEqual(len(iface.COLOR_SPACE_NAMES), 25)

    def test_affects_excludes_uvfiltersize(self):
        aff = iface.affects_input_names()
        self.assertIn("uvCoord", aff)
        self.assertIn("fileName", aff)
        self.assertNotIn("uvFilterSize", aff)   # deliberately excluded (VP2 fragment trap)


class TestInlineEnumMirrorsMatchSSOT(unittest.TestCase):
    """The k* enum ints are a frozen 0/1/2/3 contract mirroring Maya's stock file
    node. mpy_file.py imports them from the SSOT (real dedup), but two mirrors must
    stay INLINE and cannot import the package:
      * _defaults/file_defaults.py -- exec'd node source (editable in the Init tab,
        preserved by one-way .py bake/export -> must be self-contained).
    This guard fails loudly if an inline mirror drifts from the SSOT. (Maya-free.)"""

    _K_NAMES = (
        "kFilterPoint", "kFilterLinear", "kFilterAnisotropic",
        "kMipmapNone", "kMipmapAuto",
        "kWrapWrap", "kWrapClamp", "kWrapMirror", "kWrapBorder",
        "kPreFilterBox", "kPreFilterQuadratic", "kPreFilterQuartic",
        "kPreFilterGaussian",
    )

    def _parse_inline_k(self, source):
        """Extract ``kName = <int>`` assignments from a source string (regex, so it
        works on the exec'd raw-string node source without importing Maya)."""
        import re
        found = {}
        for name in self._K_NAMES:
            m = re.search(r"^\s*%s\s*=\s*(\d+)\s*$" % re.escape(name),
                          source, re.MULTILINE)
            if m:
                found[name] = int(m.group(1))
        return found

    def test_file_defaults_inline_k_matches_ssot(self):
        from mpynode._defaults import file_defaults as fd
        inline = self._parse_inline_k(fd.DEFAULT_INIT_SOURCE)
        for name in self._K_NAMES:
            self.assertIn(name, inline,
                          "file_defaults Init source is missing inline %r" % name)
            self.assertEqual(inline[name], getattr(iface, name),
                             "file_defaults inline %r=%r drifted from SSOT %r"
                             % (name, inline[name], getattr(iface, name)))


class TestConformsToLiveNode(unittest.TestCase):
    """Drift guard, now by construction: the declarative table must match what a real
    mPyFile registers -- both the porter projection (raw-meta) AND the attr flags/enums."""

    @classmethod
    def setUpClass(cls):
        from tests._setup import standalone_init, ensure_plugins_loaded
        standalone_init()
        ensure_plugins_loaded()

    def test_projection_matches_live_introspection(self):
        import maya.cmds as mc
        from mpynode.native.spec import spec_extractor as se
        node = mc.createNode("mPyFile")
        try:
            table = iface.build_porter_meta_table()
            for nm, meta in table.items():
                live = se._preset_attr_meta(node, nm, mc)
                self.assertIsNotNone(live, "no live meta for %r" % nm)
                self.assertEqual(meta, live,
                                 "declarative table drifted from live for %r" % nm)
        finally:
            mc.delete(node)

    def test_live_flags_and_enums_match_table(self):
        import maya.cmds as mc
        node = mc.createNode("mPyFile")
        try:
            for e in iface.FILE_TEXTURE_ATTRS:
                nm = e["long"]
                def q(**kw):
                    return mc.attributeQuery(nm, node=node, **kw)
                # enum fields (order + labels)
                if e["attr_type"] == "enum":
                    le          = q(listEnum=True)
                    live_labels = le[0].split(":") if le and le[0] else []
                    self.assertEqual(live_labels, iface.enum_labels(e),
                                     "enum labels differ for %r" % nm)
                # writable/readable direction
                self.assertEqual(bool(q(writable=True)), e["direction"] == "input",
                                 "writable differs for %r" % nm)
        finally:
            mc.delete(node)


if __name__ == "__main__":
    unittest.main()
