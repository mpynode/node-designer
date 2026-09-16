"""A string/hex ARRAY input lifts to the transpiler's ``strv`` carrier, so a
compute can loop over it -- the thing that lets File Composite take an ARBITRARY
number of layers instead of four numbered slots.

Before this, ``_materialise_input`` raised "input 'layers' type 'string' not
liftable" and any composite over an array of paths fell to the AI porter -- and
because ``read_texture``/``sample_texture`` are BLESSED, that is an honest
reject, not a port: the node simply would not compile.

The lift is ``std::vector<MString>`` (what emit_attr reads a string multi into)
-> ``std::vector<std::string>`` (what the ``strv`` kind carries), and indexing
goes through ``nd::strv_at``, which applies the SAME negative-index wrap as
``nd::at1`` so the two index paths cannot disagree.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init, ensure_plugins_loaded


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_LOOP_COMPUTE = """u = self.uvCoord[0]
v = self.uvCoord[1]
cr = 0.0
cg = 0.0
cb = 0.0
ca = 0.0
n_op = len(self.opacities)
for i in range(len(self.layers)):
    r, g, b, a_src = self.sample_texture(self.read_texture(self.layers[i]),
                                         u, v, missing=(0.0, 0.0, 0.0, 0.0))
    op = 1.0
    if i < n_op:
        op = float(self.opacities[i])
    a = a_src * op
    cr = r * a + cr * (1.0 - a)
    cg = g * a + cg * (1.0 - a)
    cb = b * a + cb * (1.0 - a)
    ca = a + ca * (1.0 - a)
self.outColor = (cr, cg, cb)
self.outAlpha = ca
"""


def _images():
    """The four images shipped beside the File Composite template."""
    root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
    d    = os.path.join(root, "templates", "MPyFile", "File Composite")
    names = ("grid_bg.png", "red_square.png", "green_circle.png",
             "blue_triangle.png")
    return [os.path.join(d, n) for n in names
            if os.path.isfile(os.path.join(d, n))]


class TestStringArrayLift(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        self.mc   = mc
        self.imgs = _images()
        if len(self.imgs) < 2:
            self.skipTest("shipped File Composite images not present")
        mc.file(new=True, force=True)

    def _node(self, paths, ops=None, compute=_LOOP_COMPUTE):
        from mpynode.wrappers.mpy_file import MPyFile

        w = MPyFile.create(name="strArr#", seed_defaults=False, as_texture=True)
        w.add_input_attr("layers", "string", is_array=True)
        w.add_input_attr("opacities", "float", is_array=True)
        w.set_compute_expression(compute)
        n = w.get_name()
        for i, p in enumerate(paths):
            self.mc.setAttr("%s.layers[%d]" % (n, i), p, type="string")
            self.mc.setAttr("%s.opacities[%d]" % (n, i),
                            1.0 if ops is None else ops[i])
        return n

    def _spec(self, node):
        from mpynode.native.spec import spec_extractor

        return spec_extractor.extract_spec(node)

    def _cpp(self, node):
        from mpynode.native import compiler as codegen

        return codegen.generate_cpp(self._spec(node), for_port=True)

    # -- the lift itself ----------------------------------------------------
    def test_string_array_input_is_liftable(self):
        from mpynode.native.compiler import nd_lower

        meta = {"type": "string", "is_array": True}
        self.assertTrue(nd_lower._is_string_array(meta))
        self.assertFalse(nd_lower._is_string_scalar(meta))
        lines, typ = nd_lower._materialise_input(
            {"plug": "layers", "member": "aLayers", "meta": meta}, "dst")
        self.assertEqual(typ.kind, "strv")
        body = "\n".join(lines)
        self.assertIn("std::vector<std::string> dst;", body)
        self.assertIn(".asChar()", body)

    def test_hex_array_rides_the_same_lift(self):
        """emit_attr already decodes a hex element, so it is a string here."""
        from mpynode.native.compiler import nd_lower

        _lines, typ = nd_lower._materialise_input(
            {"plug": "h", "member": "aH", "meta": {"type": "hex",
                                                   "is_array": True}}, "d")
        self.assertEqual(typ.kind, "strv")

    def test_scalar_string_still_lifts_to_a_plain_string(self):
        """The scalar path must be untouched by the array addition."""
        from mpynode.native.compiler import nd_lower

        lines, typ = nd_lower._materialise_input(
            {"plug": "fileName", "member": "aFileName",
             "meta": {"type": "string", "is_array": False}}, "d")
        self.assertEqual(typ.kind, "str")
        self.assertIn("std::string d = in_aFileName.asChar();",
                      "\n".join(lines).strip())

    # -- end to end ---------------------------------------------------------
    def test_the_loop_lowers_deterministically(self):
        cpp = self._cpp(self._node(self.imgs))
        self.assertIn("std::vector<std::string> ndin_self_layers", cpp)
        self.assertIn("nd::strv_at(ndin_self_layers", cpp)
        # The loop bound is the RUNTIME array length, not a baked layer count.
        self.assertIn("ndin_self_layers.size()", cpp)
        # Deterministic: a blessed compute that reached the AI porter would be
        # an honest reject instead, so this also proves it did not.
        self.assertNotIn("ND_PORT", cpp)

    def test_the_missing_substitute_is_baked_into_the_loop(self):
        """missing=(0,0,0,0) becomes a compile-time constant beside the sample.
        The temp counter is not fixed, so match the shape, not the name."""
        import re

        cpp = self._cpp(self._node(self.imgs))
        self.assertTrue(
            re.search(r"float sm_\d+_ms\[4\] = \{ 0\.0f, 0\.0f, 0\.0f, 0\.0f \};",
                      cpp),
            "no zeroed missing-substitute array in the emitted sample")
        # The magenta default must NOT appear for this template.
        self.assertNotIn("_ms[4] = { 1.0f, 0.0f, 1.0f, 1.0f };", cpp)

    def test_interpreted_composites_every_element(self):
        """Four layers stack; the sampled texels are not one flat colour."""
        n    = self._node(self.imgs)
        seen = set()
        for u, v in ((0.0625, 0.0625), (0.1875, 0.4375),
                     (0.5625, 0.5625), (0.5625, 0.1875)):
            self.mc.setAttr(n + ".uCoord", u)
            self.mc.setAttr(n + ".vCoord", v)
            self.mc.dgdirty(n)
            seen.add(tuple(round(c, 4)
                           for c in self.mc.getAttr(n + ".outColor")[0]))
        self.assertGreater(len(seen), 1)

    def test_the_stack_length_is_runtime_not_four(self):
        """Six elements composite as six -- a fixed-slot node could not."""
        six = [self.imgs[0]] * 5 + [self.imgs[1]]
        n   = self._node(six, ops=[1.0] * 5 + [0.0])
        self.mc.setAttr(n + ".uCoord", 0.1875)
        self.mc.setAttr(n + ".vCoord", 0.4375)
        self.mc.dgdirty(n)
        without = list(self.mc.getAttr(n + ".outColor")[0])
        self.mc.setAttr(n + ".opacities[5]", 1.0)
        self.mc.dgdirty(n)
        with_top = list(self.mc.getAttr(n + ".outColor")[0])
        self.assertEqual(
            len(self.mc.getAttr(n + ".layers", multiIndices=True) or []), 6)
        self.assertGreater(max(abs(a - b) for a, b in zip(without, with_top)),
                           1e-4)

    def test_an_empty_array_is_transparent_not_magenta(self):
        n = self._node([])
        self.mc.dgdirty(n)
        self.assertEqual(
            tuple(round(c, 4) for c in self.mc.getAttr(n + ".outColor")[0]),
            (0.0, 0.0, 0.0))
        self.assertAlmostEqual(self.mc.getAttr(n + ".outAlpha"), 0.0, delta=1e-5)

    def test_a_broken_layer_under_a_good_one_changes_nothing(self):
        good = self._node([self.imgs[1]])
        self.mc.setAttr(good + ".uCoord", 0.1875)
        self.mc.setAttr(good + ".vCoord", 0.4375)
        self.mc.dgdirty(good)
        alone = list(self.mc.getAttr(good + ".outColor")[0])

        both  = self._node(["", self.imgs[1]])
        self.mc.setAttr(both + ".uCoord", 0.1875)
        self.mc.setAttr(both + ".vCoord", 0.4375)
        self.mc.dgdirty(both)
        stacked = list(self.mc.getAttr(both + ".outColor")[0])
        for a, b in zip(alone, stacked):
            self.assertAlmostEqual(a, b, delta=1e-6)

    def test_a_layer_with_no_opacity_element_defaults_to_one(self):
        """`opacities` shorter than `layers` must not read past its end."""
        n = self._node([self.imgs[1]])
        self.mc.removeMultiInstance(n + ".opacities[0]", b=True)
        self.mc.setAttr(n + ".uCoord", 0.1875)
        self.mc.setAttr(n + ".vCoord", 0.4375)
        self.mc.dgdirty(n)
        self.assertAlmostEqual(self.mc.getAttr(n + ".outAlpha"), 1.0,
                               delta=1e-5)


if __name__ == "__main__":
    unittest.main()
