"""Node registry + wrapper factory + core mPyNode + plugin-load smoke + methods-tab completeness

Consolidated from: test_node_registry_completeness.py, test_factory_wrap.py, test_phase02.py, test_phase01.py, test_methods_tab_completeness.py.
"""

from __future__ import annotations

# ===================== from test_node_registry_completeness.py =====================
import unittest


class TestNodeRegistryCompleteness(unittest.TestCase):
    """Every wrapper class with a NATIVE_TYPE attr must be in the
    REGISTRY."""

    EXPECTED_TYPES = (
        # User-facing wrappers (mpynode.<name>).
        ("mpynode.wrappers._mpy_node", "MPyNode"),
        ("mpynode.wrappers.mpy_locator", "MPyLocator"),
        ("mpynode.wrappers.mpy_constraint", "MPyConstraint"),
        ("mpynode.wrappers.mpy_iksolver", "MPyIkSolver"),
        ("mpynode.wrappers.mpy_deformer", "MPyDeformer"),
        ("mpynode.wrappers.mpy_transform", "MPyTransform"),
        ("mpynode.wrappers.mpy_mesh", "MPyMesh"),
        ("mpynode.wrappers.mpy_skin_cluster", "MPySkinCluster"),
        ("mpynode.wrappers.mpy_blend_shape", "MPyBlendShape"),
    )

    # generator node types. These have no top-level wrapper module (the MPx
    # subclass IS the entry point), so the REGISTRY points the UI at the api2
    # module and the Scene tab can still enumerate them.
    PHASE_H_NATIVE_TYPES = ("mPyNurbsCurve", "mPyNurbsSurface")

    def test_all_wrapper_types_in_registry(self):
        from mpynode._node_registry import REGISTRY

        registered = set(REGISTRY.keys())
        # Each top-level wrapper exposes NATIVE_TYPE.
        for _mod_name, cls_name in self.EXPECTED_TYPES:
            # Reconstruct the native type from the wrapper convention:
            # MPyFoo -> mPyFoo (lowercase first 'M').
            native = "m" + cls_name[1:]
            self.assertIn(
                native, registered,
                f"native type {native!r} (from {cls_name!r}) missing "
                f"from REGISTRY -- Scene tab will silently skip "
                f"instances. Fix: add an entry in "
                f"mpynode/_node_registry.py::REGISTRY.",
            )

    def test_phase_h_generators_in_registry(self):
        from mpynode._node_registry import REGISTRY

        for native in self.PHASE_H_NATIVE_TYPES:
            self.assertIn(
                native, REGISTRY,
                f"generator type {native!r} missing from "
                f"REGISTRY. This was the bug that motivated this "
                f"test (proceduralCurve.ma showed empty Scene tab).",
            )

    def test_phase_h_wrappers_provide_designer_methods(self):
        """Deeper fix: each type's wrapper class
        must respond to the methods the Node Designer's panes
        call (get_name, get_compute_expression, get_init_expression,
        get_input_attr_map, get_output_attr_map). Without these the
        Attributes + Expression panes stay empty even when the
        Scene tab shows the node."""
        from mpynode._node_registry import REGISTRY

        REQUIRED_METHODS = (
            "get_name",
            "get_compute_expression",
            "get_init_expression",
            "get_input_attr_map",
            "get_output_attr_map",
        )
        for native in self.PHASE_H_NATIVE_TYPES:
            spec = REGISTRY[native]
            cls  = spec.get_wrapper_class()
            for method in REQUIRED_METHODS:
                self.assertTrue(
                    hasattr(cls, method),
                    f"{native} wrapper class {cls.__name__!r} from "
                    f"{spec.wrapper_module!r} missing required "
                    f"method {method!r}. Designer panes need this.",
                )

    def test_phase_h_wrappers_are_top_level(self):
        """The wrappers must be top-level
        (``mpynode.wrappers.mpy_nurbs_curve`` / ``mpynode.wrappers.mpy_nurbs_surface`` / ``mpynode.lattice``),
        NOT the api2 MPx subclasses (those don't take a name string
        in their constructor). This pins the fix at the
        REGISTRY-spec level so it can't drift back."""
        from mpynode._node_registry import REGISTRY

        EXPECTED = {
            "mPyNurbsCurve":   "mpynode.wrappers.mpy_nurbs_curve",
            "mPyNurbsSurface": "mpynode.wrappers.mpy_nurbs_surface",
        }
        for native, expected_module in EXPECTED.items():
            spec = REGISTRY[native]
            self.assertEqual(
                spec.wrapper_module, expected_module,
                f"{native} wrapper_module should be "
                f"{expected_module!r} (top-level user wrapper), "
                f"NOT {spec.wrapper_module!r}",
            )

    def test_total_count_matches_known_types(self):
        """Snapshot: 12 registered types (after removing mPyEmitter /
        mPyField / mPyObjectSet / mPyLattice, and consolidating
        mPyGeometryFilter into mPyDeformer).
        Update if we ever add another node type."""
        from mpynode._node_registry import REGISTRY

        self.assertEqual(
            len(REGISTRY), 12,
            f"REGISTRY size = {len(REGISTRY)}; expected 12. If a "
            f"new node type landed in a phase, update this test "
            f"AND make sure the new type has a wrapper test "
            f"covering it.",
        )


# ===================== from test_factory_wrap.py =====================
import unittest

import maya.cmds as mc


class TestFactoryWrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for p in ("mpynode_api1", "mpynode_api2"):
            if not mc.pluginInfo(p, q=True, loaded=True):
                mc.loadPlugin(p)

    def setUp(self):
        mc.file(new=True, force=True)

    def test_dispatch_to_specific_subclass(self):
        from mpynode import MPyNode
        from mpynode.wrappers.mpy_constraint import MPyConstraint
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        from mpynode.wrappers.mpy_transform import MPyTransform

        cases = {
            "mPySkinCluster": MPySkinCluster,
            "mPyConstraint":  MPyConstraint,
            "mPyTransform":   MPyTransform,
        }
        for ntype, wcls in cases.items():
            node = mc.createNode(ntype)
            w    = MPyNode(node)
            self.assertIs(type(w), wcls, "%s -> %s" % (ntype, type(w).__name__))
            self.assertIsInstance(w, MPyNode)
            self.assertEqual(w.get_name(), node)

    def test_bare_mpynode_stays_base(self):
        from mpynode import MPyNode

        node = mc.createNode("mPyNode")
        self.assertIs(type(MPyNode(node)), MPyNode)

    def test_module_and_classmethod_wrap_alias(self):
        import mpynode
        from mpynode import MPyNode
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster

        node = mc.createNode("mPySkinCluster")
        self.assertIsInstance(mpynode.wrap_node(node), MPySkinCluster)
        self.assertIsInstance(MPyNode.wrap(node), MPySkinCluster)

    def test_direct_subclass_construction_unaffected(self):
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster

        node = mc.createNode("mPySkinCluster")
        self.assertIs(type(MPySkinCluster(node)), MPySkinCluster)

    def test_nonexistent(self):
        import mpynode
        from mpynode import MPyNode

        with self.assertRaises(ValueError):
            MPyNode("doesNotExist__xyz")
        self.assertIsNone(mpynode.wrap_node("doesNotExist__xyz"))

    def test_bare_constructor_gives_build_guidance(self):
        """``MPyNode()`` with no node name must fail with a message that points
        at the proper creation entry point (``build``), not the cryptic
        'missing 1 required positional argument' TypeError. Motivated by a user
        exporting a node and trying ``new = TimesTwo()`` to run it."""
        from mpynode import MPyNode

        with self.assertRaisesRegex(TypeError, r"\.build\("):
            MPyNode()

    def test_nonexistent_name_gives_build_guidance(self):
        """Wrapping a name that doesn't exist still raises ValueError, but the
        message now also explains how to CREATE (build) vs WRAP (existing name /
        wrap)."""
        from mpynode import MPyNode

        # still a ValueError, still mentions the missing node ...
        with self.assertRaisesRegex(ValueError, r"does not exist"):
            MPyNode("doesNotExist__abc")
        # ... and now also carries the build/wrap guidance.
        with self.assertRaisesRegex(ValueError, r"\.build\("):
            MPyNode("doesNotExist__abc")

    def test_construction_guidance_names_the_subclass(self):
        """The guidance names the ACTUAL wrapper class, so a subclass says
        ``MPyLocator.build()`` -- not ``MPyNode.build()``."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        with self.assertRaisesRegex(TypeError, r"MPyLocator\.build\("):
            MPyLocator()


# ===================== from test_phase02.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase02():
    standalone_init()


class TestMPyNodeBasics(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_node_type_registered(self):
        self.assertIn("mPyNode", mc.allNodeTypes() or [])

    def test_create_returns_wrapper(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="basicNode")
        self.assertEqual(n.get_name(), "basicNode")
        self.assertTrue(mc.objExists("basicNode"))
        self.assertEqual(mc.nodeType("basicNode"), "mPyNode")

    def test_internal_attrs_present(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="attrCheckNode")
        for plug in ("_computeSource", "_inputAttrs", "_outputAttrs",
                     "_storedVarNames", "_storedVarsData", "debug_mode"):
            self.assertTrue(
                mc.attributeQuery(plug, node=n.get_name(), exists=True),
                f"internal plug {plug!r} should exist on mPyNode",
            )


class TestMPyNodeAddAttrs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_add_input_attr_float(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="addIn")
        n.add_input_attr("a", "float")
        self.assertTrue(mc.attributeQuery("a", node=n.get_name(), exists=True))
        # Recorded in JSON map
        self.assertIn("a", n.get_input_attr_map())
        self.assertEqual(n.get_input_attr_map()["a"]["attr_type"], "float")

    def test_add_output_attr_float(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="addOut")
        n.add_output_attr("c", "float")
        self.assertTrue(mc.attributeQuery("c", node=n.get_name(), exists=True))
        self.assertIn("c", n.get_output_attr_map())

    def test_add_vector_creates_xyz_children(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="addVec")
        n.add_input_attr("v", "vector")
        for child in ("v", "vX", "vY", "vZ"):
            self.assertTrue(
                mc.attributeQuery(child, node=n.get_name(), exists=True),
                f"vector child {child!r} should exist",
            )

    def test_delete_input_attr(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="delIn")
        n.add_input_attr("temp", "float")
        self.assertIn("temp", n.get_input_attr_map())
        n.delete_input_attr("temp")
        self.assertNotIn("temp", n.get_input_attr_map())
        self.assertFalse(mc.attributeQuery("temp", node=n.get_name(), exists=True))


class TestMPyNodeExpression(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_set_get_expression(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="expr")
        n.set_compute_expression("c = a * b")
        self.assertEqual(n.get_compute_expression(), "c = a * b")

    def test_compute_simple_multiply_via_visible_cube(self):
        """End-to-end: create mPyNode with c = a * b, drive a VISIBLE
        cube's translateX from c, set a + b, query cube's translateX.

        The cube is visible (default after createPolyCube) so Maya is
        forced to evaluate the chain. Without the cube the output plug
        could be re-read without ever firing compute.
        """
        from mpynode.wrappers._mpy_node import MPyNode

        # Build the expression node.
        n = MPyNode.create(name="multNode")
        n.add_input_attr("a", "float")
        n.add_input_attr("b", "float")
        n.add_output_attr("c", "float")
        n.set_compute_expression("self.c = self.a * self.b")

        # Build the visible cube driven by the node's output.
        cube = mc.polyCube(name="drivenCube")[0]
        # The cube's transform's translateX is what we'll observe.
        mc.connectAttr(n.get_name() + ".c", cube + ".translateX", force=True)

        # Drive the inputs.
        mc.setAttr(n.get_name() + ".a", 3.0)
        mc.setAttr(n.get_name() + ".b", 4.0)

        # Force evaluation by querying the cube's world position.
        # cmds.xform will dgeval the chain.
        ws = mc.xform(cube, q=True, ws=True, t=True)

        # Cube's world translateX should equal a*b = 12.
        self.assertAlmostEqual(ws[0], 12.0, places=4,
                               msg=f"cube ws X = {ws[0]}; expected 12.0 from a*b")
        # And the underlying plug
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".c"), 12.0, places=4)

    def test_compute_re_evaluates_on_input_change(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="reeval")
        n.add_input_attr("x", "float")
        n.add_output_attr("y", "float")
        n.set_compute_expression("self.y = self.x + 100")

        cube = mc.polyCube(name="reevalCube")[0]
        mc.connectAttr(n.get_name() + ".y", cube + ".translateY", force=True)

        mc.setAttr(n.get_name() + ".x", 1.0)
        ws_y_first = mc.xform(cube, q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(ws_y_first, 101.0, places=4)

        mc.setAttr(n.get_name() + ".x", 50.0)
        ws_y_second = mc.xform(cube, q=True, ws=True, t=True)[1]
        self.assertAlmostEqual(ws_y_second, 150.0, places=4)

    def test_compute_with_vector_output(self):
        """Vector output drives cube translate (3 components)."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="vecNode")
        n.add_input_attr("scale", "float")
        n.add_output_attr("pos", "vector")
        n.set_compute_expression("self.pos = [self.scale, self.scale * 2, self.scale * 3]")

        cube = mc.polyCube(name="vecCube")[0]
        mc.connectAttr(n.get_name() + ".pos", cube + ".translate", force=True)

        mc.setAttr(n.get_name() + ".scale", 5.0)
        ws = mc.xform(cube, q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[0], 5.0,  places=4)
        self.assertAlmostEqual(ws[1], 10.0, places=4)
        self.assertAlmostEqual(ws[2], 15.0, places=4)


class TestMPyNodeRecipe(unittest.TestCase):
    def test_mpynode_recipe_registered(self):
        from mpynode._common.util.recipes import get_recipe

        recipe = get_recipe("mPyNode")
        self.assertIsNotNone(recipe)
        # mPyNode has no inherited or synthetic plugs in the recipe
        # (all user inputs/outputs are dynamic).
        self.assertEqual(len(recipe.inputs), 0)
        self.assertEqual(len(recipe.outputs), 0)


# ===================== from test_phase01.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase01():
    standalone_init()


class TestPluginsLoad(unittest.TestCase):
    def test_api1_plugin_loads(self):
        ensure_plugins_loaded()
        self.assertTrue(mc.pluginInfo("mpynode_api1", q=True, loaded=True))

    def test_api2_plugin_loads(self):
        ensure_plugins_loaded()
        self.assertTrue(mc.pluginInfo("mpynode_api2", q=True, loaded=True))

    def test_api2_plugin_uses_new_api(self):
        """Verify the API 2 plugin file actually has the maya_useNewAPI marker."""
        ensure_plugins_loaded()
        path = mc.pluginInfo("mpynode_api2", q=True, path=True)
        with open(path) as f:
            src = f.read()
        self.assertIn(
            "def maya_useNewAPI()",
            src,
            "mpynode_api2.py must declare maya_useNewAPI for Maya to use API 2",
        )

    def test_api1_plugin_does_not_use_new_api(self):
        """API 1 plugin must NOT have the maya_useNewAPI marker."""
        ensure_plugins_loaded()
        path = mc.pluginInfo("mpynode_api1", q=True, path=True)
        with open(path) as f:
            src = f.read()
        self.assertNotIn(
            "def maya_useNewAPI()",
            src,
            "mpynode_api1.py must NOT declare maya_useNewAPI (it's API 1.0)",
        )


class TestCommonImports(unittest.TestCase):
    """The _common/ package modules must be importable with no Maya
    dependency at module-import time."""

    def test_serialization_imports(self):
        from mpynode._common.io import serialization

        self.assertTrue(hasattr(serialization, "encode_attr_map"))
        self.assertTrue(hasattr(serialization, "decode_attr_map"))

    def test_expression_imports(self):
        from mpynode._common.compute import expression

        self.assertTrue(hasattr(expression, "compile_expression"))
        self.assertTrue(hasattr(expression, "exec_with_profile_watch"))

    def test_recipes_imports(self):
        from mpynode._common.util import recipes

        self.assertTrue(hasattr(recipes, "HydrationRecipe"))
        self.assertTrue(hasattr(recipes, "get_recipe"))
        # Lookup of an unregistered type returns None.
        self.assertIsNone(recipes.get_recipe("definitely_not_a_real_type"))

    def test_callbacks_imports(self):
        from mpynode._common.lifecycle import callbacks

        self.assertTrue(hasattr(callbacks, "CALLBACK_MANAGER"))


class TestSerializationRoundTrip(unittest.TestCase):
    def test_attr_map_round_trip(self):
        from mpynode._common.io.serialization import decode_attr_map, encode_attr_map

        data = {
            "myFloat":  {"attr_type": "float", "is_array": False},
            "myVecArr": {"attr_type": "vector", "is_array": True},
        }
        encoded = encode_attr_map(data)
        self.assertEqual(decode_attr_map(encoded), data)

    def test_attr_map_empty(self):
        from mpynode._common.io.serialization import decode_attr_map

        self.assertEqual(decode_attr_map(""), {})
        self.assertEqual(decode_attr_map("None"), {})

    def test_attr_map_invalid_json_raises(self):
        from mpynode._common.io.serialization import decode_attr_map, InvalidAttrMapError

        with self.assertRaises(InvalidAttrMapError):
            decode_attr_map("not json {")

    def test_attr_map_invalid_shape_raises(self):
        from mpynode._common.io.serialization import decode_attr_map, InvalidAttrMapError

        # Top-level list is not allowed.
        with self.assertRaises(InvalidAttrMapError):
            decode_attr_map("[1, 2, 3]")
        # Entry missing attr_type is not allowed.
        with self.assertRaises(InvalidAttrMapError):
            decode_attr_map('{"foo": {"is_array": false}}')

    def test_stored_vars_round_trip(self):
        from mpynode._common.io.serialization import decode_stored_vars, encode_stored_vars

        vars_dict = {"counter": 5, "history": [1, 2, 3], "name": "test"}
        encoded   = encode_stored_vars(vars_dict)
        self.assertEqual(decode_stored_vars(encoded), vars_dict)


class TestExpressionCompile(unittest.TestCase):
    def test_compile_empty_returns_noop_code(self):
        from mpynode._common.compute.expression import compile_expression

        code = compile_expression("")
        self.assertIsNotNone(code)
        # Should exec without error.
        exec(code, {}, {})

    def test_compile_valid(self):
        from mpynode._common.compute.expression import compile_expression

        code = compile_expression("x = 1 + 2")
        ns: dict = {}
        exec(code, {}, ns)
        self.assertEqual(ns["x"], 3)

    def test_compile_syntax_error_raises(self):
        from mpynode._common.compute.expression import compile_expression

        with self.assertRaises(SyntaxError):
            compile_expression("def bad(:")

    def test_safe_compile_returns_none_on_syntax_error(self):
        """Safe_compile_expression catches the
        SyntaxError, surfaces a user-facing message, and returns None
        so the caller can keep its previous compiled code."""
        from mpynode._common.compute.expression import safe_compile_expression

        # User's bug.ma typo: ``M[:-,3,:3]`` (the ``:-`` is invalid).
        result = safe_compile_expression(
            "p = M[:-,3,:3].mean(axis=0)",
            node_name="bug_repro",
        )
        self.assertIsNone(result)

    def test_safe_compile_returns_code_on_valid_syntax(self):
        """Valid expressions compile + execute identically to the
        legacy ``compile_expression`` path."""
        from mpynode._common.compute.expression import safe_compile_expression

        code = safe_compile_expression("y = 5 * 3", node_name="ok")
        self.assertIsNotNone(code)
        ns: dict = {}
        exec(code, {}, ns)
        self.assertEqual(ns["y"], 15)

    def test_safe_compile_writes_to_stderr_on_syntax_error(self):
        """The SyntaxError message must reach stderr so headless mayapy
        + log capture see it (Maya's MGlobal.displayWarning is also
        called when the API is available)."""
        import io
        import sys

        from mpynode._common.compute.expression import safe_compile_expression

        old_stderr = sys.stderr
        buf        = io.StringIO()
        sys.stderr = buf
        try:
            safe_compile_expression("p = M[:-,3,:3].mean(axis=0)", node_name="logged")
        finally:
            sys.stderr = old_stderr
        msg = buf.getvalue()
        self.assertIn("logged", msg)
        self.assertIn("invalid syntax", msg.lower())
        # Caret pointer should be present.
        self.assertIn("^", msg)

    def test_setInternalValue_keeps_old_code_on_syntax_error(self):
        """End-to-end: pushing a syntax-broken
        expression to a node leaves the previous expression compiled
        and computing. Without the fix the node would silently stop
        producing values (the user's bug.ma symptom)."""
        import maya.cmds as mc
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

        n = MPyNode.create(name="last_known_good")
        n.add_input_attr("a", "float")
        n.add_output_attr("c", "float")
        n.set_compute_expression("self.c = self.a * 3")

        mc.setAttr(n.get_name() + ".a", 4)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".c"), 12.0)

        # Push a syntax-broken expression. setInternalValue should
        # surface the warning AND keep the previous _expr_code.
        n.set_compute_expression("c = M[:-,3,:3].mean(axis=0)")

        # Compute should still produce a*3 (last-known-good).
        mc.setAttr(n.get_name() + ".a", 5)
        self.assertAlmostEqual(mc.getAttr(n.get_name() + ".c"), 15.0)

    def test_exec_with_profile_watch_success(self):
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("y = 10 * 2")
        # single namespace dict (was exec_globals + exec_locals).
        ns: dict = {}
        ok = exec_with_profile_watch(code, ns)
        self.assertTrue(ok)
        self.assertEqual(ns["y"], 20)

    def test_exec_with_profile_watch_failure_calls_on_error(self):
        from mpynode._common.compute.expression import (
            compile_expression,
            exec_with_profile_watch,
        )

        code = compile_expression("raise ValueError('boom')")
        captured: list[str] = []
        # single namespace dict.
        ok = exec_with_profile_watch(
            code, {}, on_error=lambda msg: captured.append(msg)
        )
        self.assertFalse(ok)
        self.assertEqual(len(captured), 1)
        self.assertIn("boom", captured[0])


class TestRecipeRegistry(unittest.TestCase):
    def test_register_and_lookup(self):
        from mpynode._common.util.recipes import (
            get_recipe,
            HydrationInputEntry,
            HydrationRecipe,
            register_recipe,
        )

        r = HydrationRecipe(
            native_type="testNode",
            inputs=[
                HydrationInputEntry(
                    name        = "real",
                    source_plug = "real",
                    kind        = "float",
                ),
                HydrationInputEntry(
                    name        = "synthetic",
                    source_plug = "",  # synthetic marker
                    kind        = "vector",
                ),
            ],
        )
        register_recipe(r)
        try:
            looked = get_recipe("testNode")
            self.assertIsNotNone(looked)
            self.assertEqual(len(looked.inputs), 2)
            real_inputs = [e for e in looked.inputs if e.source_plug]
            self.assertEqual(len(real_inputs), 1)
            self.assertEqual(real_inputs[0].name, "real")
        finally:
            from mpynode._common.util.recipes import HYDRATION_RECIPES

            HYDRATION_RECIPES.pop("testNode", None)

    def test_lookup_missing_returns_none(self):
        from mpynode._common.util.recipes import get_recipe

        self.assertIsNone(get_recipe("does_not_exist_node_type"))


class TestCallbackManager(unittest.TestCase):
    def test_register_and_remove_all(self):
        from mpynode._common.lifecycle.callbacks import CallbackManager

        mgr = CallbackManager()
        deregistered: list[int] = []

        def fake_dereg(cb_id):
            deregistered.append(cb_id)

        mgr.register(101, fake_dereg)
        mgr.register(102, fake_dereg)
        mgr.register(103, fake_dereg)

        n = mgr.remove_all()
        self.assertEqual(n, 3)
        self.assertEqual(sorted(deregistered), [101, 102, 103])

    def test_unregister_single(self):
        from mpynode._common.lifecycle.callbacks import CallbackManager

        mgr = CallbackManager()
        deregistered: list[int] = []

        def fake_dereg(cb_id):
            deregistered.append(cb_id)

        t1 = mgr.register(201, fake_dereg)
        t2 = mgr.register(202, fake_dereg)

        self.assertTrue(mgr.unregister(t1))
        self.assertEqual(deregistered, [201])

        # remove_all should now only remove the remaining one.
        n = mgr.remove_all()
        self.assertEqual(n, 1)
        self.assertEqual(deregistered, [201, 202])


# ===================== from test_methods_tab_completeness.py =====================
import unittest


REQUIRED_METHODS = (
    "set_methods_source",
    "get_methods_source",
    "clear_methods_source",
    "has_methods_source",
    "list_commands",
    "call_command",
)


class TestMethodsSourceMixinOnAllWrappers(unittest.TestCase):
    def test_every_wrapper_has_methods_source_surface(self):
        from mpynode._node_registry import REGISTRY

        missing = []
        for native_type, spec in REGISTRY.items():
            try:
                cls = spec.get_wrapper_class()
            except Exception as exc:  # noqa: BLE001
                self.fail(
                    f"failed to load wrapper for {native_type!r}: {exc}"
                )
            for method in REQUIRED_METHODS:
                if not hasattr(cls, method):
                    missing.append(
                        f"{native_type} ({cls.__module__}.{cls.__name__})"
                        f" missing {method!r}"
                    )
        if missing:
            self.fail(
                "Methods-tab gating in the Node Designer requires every wrapper "
                "to expose the MethodsSourceMixin surface so the tab shows for "
                "every node type. Missing:\n  " + "\n  ".join(missing)
            )


def setUpModule():
    _setUpModule__phase02()
    _setUpModule__phase01()


if __name__ == "__main__":
    import unittest
    unittest.main()
