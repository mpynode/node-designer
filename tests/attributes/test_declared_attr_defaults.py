"""A DECLARED ``bool`` default must reach the attribute -- and mean the SAME
thing interpreted and compiled.

Maya writes a multi element to the .ma only when its value differs from the
attribute default (an all-default multi is written not at all; a sparse one
loses every default-valued element). So a stream whose SEMANTIC default -- the
value its compute overlays for an absent element -- disagrees with the declared
attribute default silently reverts on reload. Metaballs' ``axis`` was fixed that
way (declared 1, matching ``_dense_over(self.axis, np.ones(n))``); ``additive``
carries the same defect with ``bool``.

``add_input_attr`` used to accept ``default_value`` only for
float/double/int/angle (+enum), so a bool default was dropped BEFORE it reached
either backend, and both ends hardcoded false. Honouring it needs all three
links: the ``cmds.addAttr`` call, the recorded meta (-> spec -> codegen), and the
two C++ emitters -- ``emit_attr._create_lines`` (the attribute default itself)
and ``_array_gap_default_cpp`` (the dense-array gap fill, whose interpreted twin
``_api2.helpers.array_gap_default`` reads ``MFnNumericAttribute.default``).
"""
from __future__ import annotations

import os
import shutil
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _node(name, **kw):
    """A fresh mPyNode carrying one bool multi input ``b``."""
    import maya.cmds as mc
    import mpynode

    mc.file(new=True, force=True)
    n = mc.createNode("mPyNode", name=name)
    w = mpynode.wrap_node(n)
    w.add_input_attr("b", "bool", is_array=True, **kw)
    w.set_compute_expression("pass\n")
    return n, w


def _member(spec, plug):
    from mpynode.native.compiler import emit_attr

    for m in emit_attr._members(spec):
        if m["plug"] == plug:
            return m
    raise AssertionError("no member for %r" % plug)


def _spec_of(node):
    from mpynode.native.spec import spec_extractor

    return spec_extractor.extract_spec(node)


class TestBoolDefaultDeclaration(unittest.TestCase):
    """The declaration has to survive ``add_input_attr`` -- it is the first of
    the three links, and the one that was missing."""

    def test_declared_bool_default_reaches_the_live_attr(self):
        import maya.cmds as mc

        n, _ = _node("boolDvLive", default_value=True)
        self.assertEqual(mc.attributeQuery("b", node=n, listDefault=True),
                         [1.0])

    def test_declared_bool_default_is_recorded_in_the_spec(self):
        n, w = _node("boolDvSpec", default_value=True)
        self.assertTrue(w.get_input_attr_map()["b"].get("default_value"))
        self.assertTrue(_spec_of(n)["inputs"]["b"].get("default_value"))

    def test_undeclared_bool_default_stays_false(self):
        """No declaration -> nothing recorded, so every existing node keeps a
        byte-identical spec (and port-cache key)."""
        import maya.cmds as mc

        n, w = _node("boolNoDv")
        self.assertEqual(mc.attributeQuery("b", node=n, listDefault=True),
                         [0.0])
        self.assertNotIn("default_value", w.get_input_attr_map()["b"])
        self.assertNotIn("default_value", _spec_of(n)["inputs"]["b"])


class TestBoolDefaultCodegen(unittest.TestCase):
    """Both C++ emitters must read the declaration instead of hardcoding
    ``false`` -- and agree with the interpreted gap-fill oracle."""

    def _gap_oracle(self, node, attr):
        """``_api2.helpers.array_gap_default`` -- what the INTERPRETED read fills
        an absent element with."""
        import maya.api.OpenMaya as om
        from mpynode._api2 import helpers

        sel = om.MSelectionList()
        sel.add(node)
        fn = om.MFnDependencyNode(sel.getDependNode(0))
        return helpers.array_gap_default(fn.attribute(attr), "bool")

    def test_create_line_honours_the_declared_default(self):
        from mpynode.native.compiler import emit_attr

        n, _ = _node("boolDvCreate", default_value=True)
        lines = emit_attr._create_lines(_member(_spec_of(n), "b"))
        self.assertIn(
            '    aB = nAttr.create("b", "b", MFnNumericData::kBoolean, true);',
            lines)

    def test_create_line_without_a_declaration_stays_false(self):
        from mpynode.native.compiler import emit_attr

        n, _ = _node("boolNoDvCreate")
        lines = emit_attr._create_lines(_member(_spec_of(n), "b"))
        self.assertIn(
            '    aB = nAttr.create("b", "b", MFnNumericData::kBoolean, false);',
            lines)

    def test_gap_default_honours_the_declared_default(self):
        from mpynode.native.compiler import emit_attr

        n, _ = _node("boolDvGap", default_value=True)
        meta = _spec_of(n)["inputs"]["b"]
        self.assertEqual(emit_attr._array_gap_default_cpp(meta), "true")
        self.assertEqual(self._gap_oracle(n, "b"), True,
                         "interpreted oracle changed -- reconcile the C++ gap")

    def test_gap_default_without_a_declaration_stays_false(self):
        from mpynode.native.compiler import emit_attr

        n, _ = _node("boolNoDvGap")
        meta = _spec_of(n)["inputs"]["b"]
        self.assertEqual(emit_attr._array_gap_default_cpp(meta), "false")
        self.assertEqual(self._gap_oracle(n, "b"), False)


# --------------------------------------------------------------------------- #
# Runtime compiled-vs-interpreted proof: a GAP in a bool multi must read the
# declared default on BOTH backends. SKIP (never fail) without a compiler.

_PASSTHROUGH = "self.outFlags = self.flags\n"
_RT_NAME     = "boolDvRt"
_RT_TYPE_ID  = "0x00070574"


def _running_maya_root():
    import sys
    from mpynode.native.toolchain import toolchain

    seeds = [os.environ.get("MAYA_LOCATION") or "",
             os.path.dirname(os.path.abspath(sys.executable))]
    for seed in seeds:
        cur = seed
        while cur and cur != os.path.dirname(cur):
            if os.path.isdir(os.path.join(toolchain.maya_include_dir(cur), "maya")):
                return cur
            cur = os.path.dirname(cur)
    return None


def _have_toolchain():
    return bool((shutil.which("clang++") or shutil.which("g++"))
                and _running_maya_root())


class TestBoolGapRuntimeParity(unittest.TestCase):
    """flags[0]=False, flags[2]=False leaves logical index 1 ABSENT. With
    ``default_value=True`` both backends must read it as True."""

    _tmp    = None
    _bundle = None
    _spec   = None

    @classmethod
    def _build_source(cls):
        import maya.cmds as mc
        import mpynode

        mc.file(new=True, force=True)
        n = mc.createNode("mPyNode", name="boolDvSrc")
        w = mpynode.wrap_node(n)
        w.add_input_attr("flags", "bool", is_array=True, default_value=True)
        w.add_output_attr("outFlags", "bool", is_array=True)
        w.set_compute_expression(_PASSTHROUGH)
        return n, w

    @classmethod
    def setUpClass(cls):
        if not _have_toolchain():
            return
        import maya.cmds as mc
        from mpynode.native.spec import spec_extractor
        from mpynode.native.toolchain import compile_controller as cc

        n, _ = cls._build_source()
        spec                                = spec_extractor.extract_spec(n)
        spec["suggested"]["node_type_name"] = _RT_NAME
        spec["suggested"]["class_name"]     = "BoolDvRt"
        spec["suggested"]["type_id"]        = _RT_TYPE_ID
        cls._spec                           = spec

        cls._tmp = tempfile.mkdtemp()
        res = cc.compile_plugin([spec], _RT_NAME, cls._tmp, strict=True,
                                verify=False, reuse_cache=False)
        if not res["ok"]:
            raise AssertionError("build failed: %s" % res.get("errors"))
        cls._bundle = res["bundle_path"]
        mc.file(new=True, force=True)
        mc.loadPlugin(cls._bundle)

    @classmethod
    def tearDownClass(cls):
        if not cls._bundle:
            return
        import maya.cmds as mc
        try:
            mc.file(new=True, force=True)
            mc.unloadPlugin(os.path.basename(cls._bundle))
        except Exception:
            pass
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        if not self._bundle:
            self.skipTest("no C++ compiler or Maya devkit for the running mayapy")

    @staticmethod
    def _drive(node):
        import maya.cmds as mc

        mc.setAttr(node + ".flags[0]", False)
        mc.setAttr(node + ".flags[2]", False)
        mc.dgeval(node + ".outFlags")
        return [mc.getAttr("%s.outFlags[%d]" % (node, i)) for i in range(3)]

    def test_compiled_gap_matches_interpreted(self):
        import maya.cmds as mc

        n, _ = self._build_source()
        interpreted = self._drive(n)

        mc.file(new=True, force=True)
        compiled = self._drive(mc.createNode(_RT_NAME))

        self.assertEqual(interpreted, [False, True, False],
                         "interpreted gap did not read the declared default")
        self.assertEqual(compiled, interpreted,
                         "compiled gap fill diverged from the interpreted read")


class TestMetaballsDeclaredDefaults(unittest.TestCase):
    """The metaballs per-shape streams whose attribute default can be made to
    agree with the compute's ``_dense_over`` overlay must declare it -- in the
    GENERATOR and in the shipped (generated) template."""

    #: stream -> declared default, mirroring COMPUTE_SOURCE's overlay.
    EXPECTED = {"shapeType": None,      # overlays 0 == the bare default
                "smoothing": None,  # overlays 0.0 == the bare default
                "additive":  True,  # overlays np.ones
                "height":    1.0,   # overlays np.ones
                "axis": 1}              # overlays np.ones  (T89)

    def test_generator_declares_the_overlay_defaults(self):
        from mpynode._demos import build_mPyMesh_sdf_dmc as gen

        got = {n: dv for n, _t, dv in gen._ARRAY_INPUTS}
        for name, want in self.EXPECTED.items():
            self.assertEqual(got[name], want,
                             "%s: declared default must match the overlay"
                             % name)

    def test_shipped_template_carries_them(self):
        """template.mpn is GENERATED from the builder -- if it drifts, a
        deserialized node silently gets the old defaults back."""
        import json

        root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
        path = os.path.join(root, "templates", "MPyMesh",
                            "Metaballs", "template.mpn")
        with open(path) as fh:
            payload = json.load(fh)
        attrs = (payload.get("data") or payload)["input_attrs"]
        for name, want in self.EXPECTED.items():
            self.assertEqual(attrs[name].get("default_value"), want,
                             "%s: template.mpn out of sync with the generator"
                             % name)


class TestAnimatedSelectionDeclaredDefault(unittest.TestCase):
    """``show_wireframe`` is the animated_selection locator's edge overlay, and
    its generator has declared ``True`` since the template was authored -- the
    declaration was simply dropped before bool defaults were honoured. The
    shipped template has to carry it too: the demo's ``demo()`` hook never sets
    the plug, so the attribute default IS what the node looks like on create.
    """

    def _generator_default(self):
        """The ``default_value`` the builder declares for ``show_wireframe``.

        Parsed rather than imported -- build_templates initializes
        maya.standalone at module scope."""
        import ast

        root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
        path = os.path.join(root, "scripts", "mpynode", "_demos",
                            "build_templates.py")
        with open(path) as fh:
            tree = ast.parse(fh.read())
        for call in ast.walk(tree):
            if (isinstance(call, ast.Call)
                    and getattr(call.func, "attr", None) == "add_input_attr"
                    and call.args
                    and getattr(call.args[0], "value", None) == "show_wireframe"):
                for kw in call.keywords:
                    if kw.arg == "default_value":
                        return ast.literal_eval(kw.value)
                return None
        raise AssertionError("build_templates declares no show_wireframe input")

    def test_generator_declares_the_overlay_on(self):
        self.assertIs(self._generator_default(), True)

    def test_shipped_template_carries_it(self):
        """template.mpn is GENERATED -- while it disagrees, the next rebuild
        silently flips the shipped demo's wireframe on."""
        import json

        root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
        path = os.path.join(root, "templates", "MPyLocator",
                            "Animated Selection", "template.mpn")
        with open(path) as fh:
            payload = json.load(fh)
        attrs = (payload.get("data") or payload)["input_attrs"]
        self.assertIs(attrs["show_wireframe"].get("default_value"),
                      self._generator_default(),
                      "template.mpn out of sync with the generator")


if __name__ == "__main__":
    unittest.main()
