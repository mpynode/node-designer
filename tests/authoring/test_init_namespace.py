"""Init source/namespace: _initSource plug, rename, self-parity, init-proxy, init-helpers, scene-open registry, completeness

Consolidated from: test_phaseA_init_rename.py, test_init_self_parity.py, test_phaseB_init_proxy.py, test_phaseJ_2_init_helpers.py, test_scene_open_type_filter.py, test_init_tab_completeness.py.
"""

from __future__ import annotations

# ===================== from test_phaseA_init_rename.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseA_init_rename():
    standalone_init()


# ===========================================================================
# Wrapper API surface
# ===========================================================================


class TestInitSourceMixinAPI(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_set_and_get_init_source_roundtrip(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)

        src   = "import numpy as np\nMY_TABLE = np.array([1, 2, 3])\n"
        self.assertTrue(d.set_init_expression(src))
        self.assertEqual(d.get_init_expression(), src)

    def test_set_init_source_creates_initSource_attr(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)

        self.assertFalse(mc.attributeQuery("_initSource", node=d.get_name(), exists=True))
        d.set_init_expression("X = 1")
        self.assertTrue(mc.attributeQuery("_initSource", node=d.get_name(), exists=True))

    def test_has_init_source(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        self.assertFalse(d.has_init_expression())
        d.set_init_expression("X = 42")
        self.assertTrue(d.has_init_expression())

    def test_clear_init_source(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        d.set_init_expression("Y = 7")
        self.assertTrue(d.has_init_expression())
        d.clear_init_expression()
        self.assertFalse(d.has_init_expression())
        # the attr is emptied, not removed, so the editor can re-save
        # without addAttr churn.
        self.assertEqual(d.get_init_expression(), "")

    def test_empty_init_source_clears_namespace(self):
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        d.set_init_expression("A = 1")
        self.assertTrue(d.has_init_expression())
        d.set_init_expression("")  # explicit empty
        self.assertFalse(d.has_init_expression())
        uuid = init_registry._node_uuid_from_name(d.get_name())
        self.assertNotIn(uuid, init_registry._NODE_INIT_NS)

    def test_bad_init_source_returns_false_no_stale(self):
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        ok    = d.set_init_expression("this is not valid python!!")
        self.assertFalse(ok)
        uuid = init_registry._node_uuid_from_name(d.get_name())
        self.assertNotIn(uuid, init_registry._NODE_INIT_NS)


# ===========================================================================
# init_registry low-level helpers
# ===========================================================================


class TestInitRegistryHelpers(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import init_registry

        init_registry.clear_all_init_ns()

    def test_init_ns_count_increments(self):
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.assertEqual(init_registry.init_ns_count(), 0)
        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d1    = MPyDeformer.create_on(plane)
        d1.set_init_expression("X = 1")
        self.assertEqual(init_registry.init_ns_count(), 1)

        d2 = MPyDeformer.create_on(plane)
        d2.set_init_expression("Y = 2")
        self.assertEqual(init_registry.init_ns_count(), 2)

    def test_clear_all_init_ns_wipes_everything(self):
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        for _ in range(3):
            MPyDeformer.create_on(plane).set_init_expression("Q = 1")
        self.assertEqual(init_registry.init_ns_count(), 3)
        init_registry.clear_all_init_ns()
        self.assertEqual(init_registry.init_ns_count(), 0)

    def test_get_init_namespace_for_mobject(self):
        import maya.OpenMaya as om
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        d.set_init_expression("CONST = 12345")

        sel = om.MSelectionList()
        sel.add(d.get_name())
        mobj = om.MObject()
        sel.getDependNode(0, mobj)

        ns = init_registry.get_init_namespace_for_mobject(mobj)
        self.assertIsNotNone(ns)
        self.assertEqual(ns.get("CONST"), 12345)


# ===========================================================================
# Auto-generated header
# ===========================================================================


class TestMakeInitHeader(unittest.TestCase):
    def test_header_includes_node_type_name(self):
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("mPyDeformer")
        self.assertIn("mPyDeformer", hdr)

    def test_header_lists_read_and_write_bindings_for_deformer(self):
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("mPyDeformer")
        for binding in (
            "self.outputGeometry[i]",
            "self.input[i].inputGeometry",
            "self.envelope",
            "setPoints",
        ):
            self.assertIn(binding, hdr)
        # The 5 internal-vars schema was deleted with the generic-compute
        # migration; the header must not advertise it anywhere -- including
        # the trailing generic example.
        for removed in ("self.points", "self.normals", "self.weights",
                        "self.deformed"):
            self.assertNotIn(
                removed, hdr,
                "mPyDeformer header still advertises removed name %s" % removed)

    def test_blendshape_header_advertises_plug_tree_not_removed_schema(self):
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("mPyBlendShape")
        for binding in ("self.outputGeometry[i]", "self.input[i].inputGeometry",
                        "self.targetGeometry[j]", "self.weight[j]",
                        "self.envelope"):
            self.assertIn(binding, hdr,
                          "mPyBlendShape header missing %s" % binding)
        for removed in ("self.points", "self.deformed", "self.targets",
                        "self.target_weights", "self.geom_index",
                        "self.time_value", "self.world_matrix"):
            self.assertNotIn(
                removed, hdr,
                "mPyBlendShape header still advertises removed name %s" % removed)

    def test_transform_header_does_not_advertise_axed_world_matrix(self):
        """``world_matrix`` was axed from mPyTransform (WORLD placement is a
        connected-parent expression); the five live channels are the reads."""
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("mPyTransform")
        for binding in ("self.local_matrix", "self.apply_rotate",
                        "self.translate", "self.rotate", "self.scale",
                        "self.shear", "self.rotate_order"):
            self.assertIn(binding, hdr,
                          "mPyTransform header missing %s" % binding)
        self.assertNotIn(
            "self.world_matrix", hdr,
            "mPyTransform header still advertises the axed world_matrix slot")

    def test_skincluster_header_advertises_plug_tree_not_removed_schema(self):
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("mPySkinCluster")
        # Check only the type-specific bindings section.
        start    = hdr.index("Available in your Expression tab")
        bindings = hdr[start:hdr.index("Compute-time plug writes")]
        for binding in ("self.weightList", "self.outputGeometry", "self.matrix",
                        "self.bindPreMatrix"):
            self.assertIn(binding, bindings, "mPySkinCluster header missing %s" % binding)
        # The old auto-densify schema was removed -- it must not be advertised.
        for removed in ("self.joint_matrices", "self.bind_matrices",
                        "self.deformed", "self.points"):
            self.assertNotIn(
                removed, bindings,
                "mPySkinCluster header still advertises removed name %s" % removed)

    def test_header_for_all_tracked_types(self):
        from mpynode._common.lifecycle import _BRIDGE_BINDINGS, make_init_header

        # every type with a bindings entry produces a non-empty, multi-line,
        # comment-styled header.
        for node_type in _BRIDGE_BINDINGS.keys():
            hdr = make_init_header(node_type)
            self.assertTrue(
                hdr.strip().startswith("#"), f"{node_type}: header doesn't start with #"
            )
            self.assertGreater(
                len(hdr.splitlines()), 10, f"{node_type}: header too short"
            )
            self.assertIn(node_type, hdr)

    def test_locator_header_lists_the_draw_surface(self):
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("mPyLocator")
        for binding in ("self.draw", "self.time", "self.hovered",
                        "self.selection_color", "self.auto_highlight",
                        "self.auto_refresh", "self.precise_hover"):
            self.assertIn(binding, hdr, "mPyLocator header missing %s" % binding)

    def test_locator_header_seeds_a_REAL_draw_import(self):
        """Commented-out examples are not discoverable by autocomplete -- the
        locator header must seed an import that actually runs."""
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("mPyLocator")
        code = [ln for ln in hdr.splitlines()
                if ln.strip() and not ln.lstrip().startswith("#")]
        self.assertTrue(code, "mPyLocator header seeds no executable line")
        ns = {}
        exec(compile(hdr, "<init_header>", "exec"), ns)
        for cls in ("DrawCircle", "DrawMesh", "DrawPoints", "DrawText"):
            self.assertIn(cls, ns, "%s not bound by the seeded import" % cls)

    def test_only_the_locator_header_seeds_code(self):
        """Every other type's header stays pure comment."""
        from mpynode._common.lifecycle import _BRIDGE_BINDINGS, make_init_header

        for node_type in _BRIDGE_BINDINGS:
            if node_type == "mPyLocator":
                continue
            hdr = make_init_header(node_type)
            code = [ln for ln in hdr.splitlines()
                    if ln.strip() and not ln.lstrip().startswith("#")]
            self.assertEqual([], code, "%s header gained code" % node_type)

    def test_header_for_unknown_type_still_returns_something(self):
        from mpynode._common.lifecycle import make_init_header

        hdr = make_init_header("noSuchNodeType")
        self.assertIsInstance(hdr, str)
        self.assertGreater(len(hdr), 0)

    def test_e4_section_present_for_wired_node_types(self):
        """The make_init_header should advertise the new
        compute-time `node.X` write surface for every node type that
        was wired for E4."""
        from mpynode._common.lifecycle import make_init_header

        e4_supported = (
            "mPyDeformer", "mPySkinCluster",
            "mPyBlendShape",
        )
        for node_type in e4_supported:
            hdr = make_init_header(node_type)
            self.assertIn(
                "Compute-time plug writes", hdr,
                f"{node_type}: header missing compute-time plug writes section",
            )
            self.assertIn(
                "node.envelope", hdr,
                f"{node_type}: header missing node.X numeric write example",
            )

    def test_e4_section_lists_outputGeometry_only_for_deformer_family(self):
        """The deformer-family fast path uses `node.outputGeometry[i]`;
        non-deformer node types don't have that surface."""
        from mpynode._common.lifecycle import make_init_header

        deformer_family = (
            "mPyDeformer", "mPySkinCluster",
            "mPyBlendShape",
        )
        for node_type in deformer_family:
            hdr = make_init_header(node_type)
            self.assertIn(
                "node.outputGeometry", hdr,
                f"{node_type}: header missing outputGeometry write example",
            )
        for node_type in ("mPyTransform", "mPyMesh"):
            hdr = make_init_header(node_type)
            self.assertNotIn(
                "node.outputGeometry", hdr,
                f"{node_type}: should NOT advertise outputGeometry"
                " (no geom_iter at compute time)",
            )

    def test_e4_section_absent_for_node_types_not_wired(self):
        """Transform / poly / mPyNode etc. aren't wired for the
        compute-time write surface; the header should NOT advertise it
        for them."""
        from mpynode._common.lifecycle import make_init_header

        for node_type in ("mPyTransform", "mPyMesh"):
            hdr = make_init_header(node_type)
            self.assertNotIn(
                "Compute-time plug writes", hdr,
                f"{node_type}: header should not advertise compute-time writes (not wired)",
            )


# ===========================================================================
# Auto-generated Compute header
# ===========================================================================


class TestMakeComputeHeader(unittest.TestCase):
    def test_header_is_commented_and_names_type(self):
        from mpynode._common.lifecycle.compute_header import make_compute_header

        hdr = make_compute_header("mPyDeformer")
        self.assertIsInstance(hdr, str)
        self.assertTrue(hdr.strip().startswith("#"))
        self.assertIn("mPyDeformer", hdr)

    def test_header_describes_the_compute_tab(self):
        from mpynode._common.lifecycle.compute_header import make_compute_header

        hdr = make_compute_header("mPyDeformer")
        self.assertIn("Compute", hdr)

    def test_header_for_unknown_type_still_returns_something(self):
        from mpynode._common.lifecycle.compute_header import make_compute_header

        hdr = make_compute_header("noSuchNodeType")
        self.assertIsInstance(hdr, str)
        self.assertGreater(len(hdr), 0)

    def test_header_does_not_claim_numpy_always_available(self):
        # np is NOT auto-injected: build_exec_namespace adds only
        # __builtins__, so the header must tell you to import it.
        from mpynode._common.lifecycle.compute_header import make_compute_header

        hdr = make_compute_header("mPyDeformer")
        self.assertNotIn("always", hdr.lower())
        self.assertIn("import numpy", hdr.lower())


# ===========================================================================
# Backward-compat: legacy _jitSource attribute migration
# ===========================================================================


class TestLegacyJitSourceMigration(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import init_registry

        init_registry.clear_all_init_ns()

    def test_on_scene_opened_migrates_legacy_jitSource(self):
        """Old.ma files that wrote ``_jitSource`` should still load
        their init code when ``_initSource`` doesn't exist."""
        from mpynode._common.lifecycle import scene_callbacks
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)

        # A phase-05-era .ma has only the legacy _jitSource attr.
        mc.addAttr(d.get_name(), longName="_jitSource", dataType="string")
        mc.setAttr(
            d.get_name() + "._jitSource",
            "MIGRATED_VALUE = 999",
            type="string",
        )

        # Trigger the kAfterOpen scanner directly (no real file open).
        scene_callbacks._on_scene_opened(None)

        self.assertTrue(d.has_init_expression())
        # get_init_expression falls back to the legacy attr when
        # _initSource is absent.
        self.assertEqual(d.get_init_expression(), "MIGRATED_VALUE = 999")

    def test_initSource_preferred_over_legacy_jitSource(self):
        """If BOTH attrs exist, ``_initSource`` wins."""
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)

        d.set_init_expression("NEW_VALUE = 100")  # adds _initSource
        mc.addAttr(d.get_name(), longName="_jitSource", dataType="string")
        mc.setAttr(d.get_name() + "._jitSource", "OLD_VALUE = 1", type="string")

        # get_init_expression must prefer _initSource:
        self.assertIn("NEW_VALUE", d.get_init_expression())
        self.assertNotIn("OLD_VALUE", d.get_init_expression())


# ===========================================================================
# Editor / file rename smoke checks
# ===========================================================================


class TestRenameSmoke(unittest.TestCase):
    def test_init_editor_module_exists(self):
        # jit_source_editor.py -> init_editor.py, NDJitSourceEditor ->
        # NDInitEditor.
        from mpynode.ui.widgets import init_editor

        self.assertTrue(hasattr(init_editor, "NDInitEditor"))

    def test_old_jit_source_editor_module_gone(self):
        try:
            from mpynode.ui.widgets import jit_source_editor  # noqa: F401
        except ImportError:
            return  # expected
        self.fail("old jit_source_editor module still importable rename")

    def test_init_registry_module_exists(self):
        from mpynode._common.lifecycle import init_registry

        self.assertTrue(hasattr(init_registry, "InitSourceMixin"))
        self.assertTrue(hasattr(init_registry, "register_init_source"))

    def test_jit_registry_module_gone(self):
        try:
            from mpynode._common import jit_registry  # noqa: F401
        except ImportError:
            return
        self.fail("old jit_registry module still importable rename")


# ===================== from test_init_self_parity.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__init_self_parity():
    standalone_init()


class TestInitSelfParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="init_parity_test")
        self.name = self.node.get_name()

    def _stored(self):
        from mpynode._common.storedvars.stored_vars_api import get_variables

        return get_variables(self.name)

    def _init_bindings(self):
        from mpynode._common.lifecycle import init_registry as ir
        import maya.api.OpenMaya as om

        sel = om.MSelectionList()
        sel.add(self.name)
        mobj = sel.getDependNode(0)
        return ir.get_init_bindings_for_mobject(mobj) or {}

    # -- reads ---------------------------------------------------------

    def test_init_reads_plug_via_self(self):
        self.node.add_input_attr("amplitude", "float")
        mc.setAttr(self.name + ".amplitude", 2.5)
        self.node.set_init_expression("self.seen = self.amplitude\n")
        self.assertAlmostEqual(self._stored().get("seen"), 2.5, places=4)

    def test_init_reads_stored_var_via_self(self):
        from mpynode._common.storedvars.stored_vars_api import set_variable

        set_variable(self.name, "values", [1, 2, 3])
        self.node.set_init_expression("self.copy = self.values\n")
        self.assertEqual(self._stored().get("copy"), [1, 2, 3])

    def test_init_read_back_of_own_write(self):
        self.node.set_init_expression("self.a = 5\nself.b = self.a * 2\n")
        s = self._stored()
        self.assertEqual(s.get("a"), 5)
        self.assertEqual(s.get("b"), 10)

    # -- writes persist (parity with Compute, no registration) ---------

    def test_init_write_persists_any_name(self):
        # No add_variable / registration -- still persists.
        self.node.set_init_expression("self.cache = {'k': 1}\n")
        self.assertEqual(self._stored().get("cache"), {"k": 1})

    def test_init_write_list_persists(self):
        self.node.set_init_expression("self.values = [10, 20, 30]\n")
        self.assertEqual(self._stored().get("values"), [10, 20, 30])

    # -- the staleness fix: writes go to storage, NOT bindings ---------

    def test_init_writes_go_to_storage_not_bindings(self):
        """Init writes must land in stored-var data, not the legacy
        init-bindings tier -- otherwise a later Compute write to the
        same name would be shadowed by a stale Tier-3 binding."""
        self.node.set_init_expression("self.counter = 100\n")
        self.assertEqual(self._stored().get("counter"), 100)
        self.assertNotIn("counter", self._init_bindings())

    def test_compute_update_not_shadowed_by_init_seed(self):
        """Init seeds a stored var; Compute overwrites it. Reading the
        var back in Compute must see the Compute value, not the stale
        init seed."""
        self.node.add_output_attr("outVal", "float")
        self.node.set_init_expression("self.counter = 1.0\n")
        self.node.set_compute_expression(
            "self.counter = 42.0\n"
            "self.outVal = self.counter\n"
        )
        val = mc.getAttr(self.name + ".outVal")
        self.assertAlmostEqual(val, 42.0, places=4)
        self.assertAlmostEqual(self._stored().get("counter"), 42.0, places=4)

    # -- plug-name writes are skipped ----------------------------------

    def test_init_write_to_plug_name_is_skipped(self):
        self.node.add_input_attr("gainPlug", "float")
        mc.setAttr(self.name + ".gainPlug", 7.0)
        self.node.set_init_expression("self.gainPlug = 999.0\n")
        self.assertAlmostEqual(mc.getAttr(self.name + ".gainPlug"), 7.0, places=4)
        self.assertNotIn("gainPlug", self._stored())

    # -- idempotent pattern --------------------------------------------

    def test_idempotent_pattern(self):
        from mpynode._common.storedvars.stored_vars_api import add_variable, set_variable

        # Initialize the stored var to None so `self.values` resolves.
        add_variable(self.name, "values", None)
        src = (
            "if self.values is None:\n"
            "    self.values = [1, 1, 1]\n"
        )
        self.node.set_init_expression(src)
        self.assertEqual(self._stored().get("values"), [1, 1, 1])
        set_variable(self.name, "values", [9, 9, 9])
        # re-running Init must not overwrite an edited value.
        self.node.set_init_expression(src)
        self.assertEqual(self._stored().get("values"), [9, 9, 9])

    # -- compute reads what init wrote ---------------------------------

    def test_compute_reads_init_written_value(self):
        self.node.add_output_attr("outVal", "float")
        self.node.set_init_expression("self.gain = 4.0\n")
        self.node.set_compute_expression("self.outVal = self.gain\n")
        self.assertAlmostEqual(mc.getAttr(self.name + ".outVal"), 4.0, places=4)


# ===================== from test_phaseB_init_proxy.py =====================
import base64
import json
import pickle
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseB_init_proxy():
    standalone_init()


def _decode_stored(raw: str) -> dict:
    """Round-trip helper: decode the stored-vars blob (codec-aware --
    the blob is now pickle+compress+base64, so go through the canonical
    decoder rather than unpickling the bytes directly)."""
    from mpynode._common.io.serialization import decode_stored_vars

    return decode_stored_vars(raw or "")


# ===========================================================================
# InitProxy unit-ish tests (operate on the registry directly)
# ===========================================================================


class TestInitProxyBindings(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        from mpynode._common.lifecycle import init_registry

        init_registry.clear_all_init_ns()

    def test_self_X_writes_persist_to_stored_vars(self):
        from mpynode._common.storedvars.stored_vars_api import get_variables
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        ok    = d.set_init_expression("self.A = 1\nself.B = [2, 3]\nself.C = 'hi'")
        self.assertTrue(ok)

        stored = get_variables(d.get_name())
        self.assertEqual(stored.get("A"), 1)
        self.assertEqual(stored.get("B"), [2, 3])
        self.assertEqual(stored.get("C"), "hi")

    def test_init_can_read_back_its_own_writes(self):
        """InitProxy.__getattr__ returns values previously stored via
        InitProxy.__setattr__ within the same init exec."""
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        ok = d.set_init_expression(
            "self.X = 100\nself.Y = self.X + 50\n"  # read back
        )
        self.assertTrue(ok)
        from mpynode._common.storedvars.stored_vars_api import get_variables

        self.assertEqual(get_variables(d.get_name()).get("Y"), 150)

    def test_re_init_keeps_persisted_stored_vars(self):
        """Stored vars persist across re-inits by design: a re-run that
        doesn't mention ``A`` leaves its persisted value intact (unlike
        the old session-only bindings, which were wiped each run)."""
        from mpynode._common.storedvars.stored_vars_api import get_variables
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        d.set_init_expression("self.A = 1")
        d.set_init_expression("self.B = 2")  # NO `A` this time

        stored = get_variables(d.get_name())
        self.assertEqual(stored.get("A"), 1)  # persists
        self.assertEqual(stored.get("B"), 2)

    def test_bad_init_does_not_leak_partial_bindings(self):
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        ok = d.set_init_expression(
            "self.A = 1\n"
            "raise RuntimeError('boom')\n"  # bombs AFTER writing A
            "self.B = 2\n"
        )
        self.assertFalse(ok)
        # the flush only runs on success, so the partial write to A must
        # not reach stored vars.
        from mpynode._common.storedvars.stored_vars_api import get_variables

        self.assertNotIn("A", get_variables(d.get_name()))
        # namespace + bindings registry entry are wiped on failure.
        uuid = init_registry._node_uuid_from_name(d.get_name())
        self.assertNotIn(uuid, init_registry._INIT_BINDINGS)

    def test_clear_init_source_drops_bindings(self):
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        d.set_init_expression("self.A = 1")
        uuid = init_registry._node_uuid_from_name(d.get_name())
        self.assertIn(uuid, init_registry._INIT_BINDINGS)

        d.clear_init_expression()
        self.assertNotIn(uuid, init_registry._INIT_BINDINGS)

    def test_clear_all_init_ns_wipes_bindings_too(self):
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        for _ in range(3):
            MPyDeformer.create_on(plane).set_init_expression("self.X = 1")

        self.assertGreater(len(init_registry._INIT_BINDINGS), 0)
        init_registry.clear_all_init_ns()
        self.assertEqual(len(init_registry._INIT_BINDINGS), 0)

    def test_get_init_bindings_for_mobject(self):
        import maya.OpenMaya as om
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)
        d.set_init_expression("self.VAL = 42")

        sel = om.MSelectionList()
        sel.add(d.get_name())
        mobj = om.MObject()
        sel.getDependNode(0, mobj)

        # Init writes now persist to stored vars, not the bindings tier.
        from mpynode._common.storedvars.stored_vars_api import get_variables

        self.assertEqual(get_variables(d.get_name()).get("VAL"), 42)
        # the bindings tier is present but empty; self.X writes no longer
        # land there.
        bindings = init_registry.get_init_bindings_for_mobject(mobj)
        self.assertFalse(bindings)  # {} or None

    def test_get_init_bindings_returns_none_for_unbound_node(self):
        import maya.OpenMaya as om
        from mpynode._common.lifecycle import init_registry
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        plane = mc.polyPlane(name="p", sx=4, sy=4)[0]
        d     = MPyDeformer.create_on(plane)  # no init source

        sel   = om.MSelectionList()
        sel.add(d.get_name())
        mobj = om.MObject()
        sel.getDependNode(0, mobj)

        self.assertIsNone(init_registry.get_init_bindings_for_mobject(mobj))


# ===================== from test_phaseJ_2_init_helpers.py =====================
import unittest

import maya.cmds as mc
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseJ_2_init_helpers():
    standalone_init()


class TestModuleSurface(unittest.TestCase):
    def test_public_symbols_present(self):
        from mpynode._common.lifecycle import init_helpers as ih

        # Check the documented surface (PHASE_J_DESIGN.md Section 3.6).
        for name in (
            "MatrixView",
            "mtm_to_numpy",
            "mtm_translation_numpy",
            "mtm_rotation_numpy",
            "mtm_scale_numpy",
            "mfnmesh_to_numpy_points",
            "mfncurve_to_numpy_cvs",
            "mfnsurface_to_numpy_cvs",
            "mfnlattice_to_numpy_points",
            "joint_chain_walk",
        ):
            self.assertTrue(
                hasattr(ih, name),
                f"init_helpers must export {name!r}",
            )

    def test_re_exports_promoted_type(self):
        from mpynode._common.lifecycle import init_helpers as ih
        from mpynode._common.plugs import promoted_types as pt

        self.assertIs(ih.MatrixView, pt.MatrixView)


class TestMatrixHelpers(unittest.TestCase):
    def test_mtm_to_numpy_identity(self):
        from mpynode._common.lifecycle import init_helpers as ih

        out = ih.mtm_to_numpy(None)
        np.testing.assert_array_almost_equal(out, np.eye(4))

    def test_mtm_to_numpy_from_view(self):
        from mpynode._common.plugs.promoted_types import MatrixView
        from mpynode._common.lifecycle import init_helpers as ih
        import maya.OpenMaya as om

        mm = om.MMatrix()
        om.MScriptUtil.createMatrixFromList(
            [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 8, 9, 1], mm
        )
        v   = MatrixView(mm)
        arr = ih.mtm_to_numpy(v)
        self.assertEqual(arr.shape, (4, 4))
        self.assertAlmostEqual(arr[3, 0], 7.0, places=4)
        self.assertAlmostEqual(arr[3, 1], 8.0, places=4)
        self.assertAlmostEqual(arr[3, 2], 9.0, places=4)

    def test_translation_extractor(self):
        from mpynode._common.plugs.promoted_types import MatrixView
        from mpynode._common.lifecycle import init_helpers as ih
        import maya.OpenMaya as om

        mm = om.MMatrix()
        om.MScriptUtil.createMatrixFromList(
            [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 7, 8, 9, 1], mm
        )
        t = ih.mtm_translation_numpy(mm)
        self.assertEqual(t.shape, (3,))
        np.testing.assert_array_almost_equal(t, [7.0, 8.0, 9.0])


class TestMeshHelper(unittest.TestCase):
    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_mfnmesh_to_numpy_points_from_polyplane(self):
        from mpynode._common.lifecycle import init_helpers as ih
        import maya.OpenMaya as om

        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        shape = mc.listRelatives(plane, shapes=True)[0]
        sel   = om.MSelectionList()
        sel.add(shape)
        dag = om.MDagPath()
        sel.getDagPath(0, dag)
        fn  = om.MFnMesh(dag)

        pts = ih.mfnmesh_to_numpy_points(fn)
        self.assertEqual(pts.ndim, 2)
        self.assertEqual(pts.shape[1], 3)
        self.assertGreater(pts.shape[0], 0)


class TestLatticeHelperSoftSkip(unittest.TestCase):
    def test_lattice_helper_returns_None_when_data_missing(self):
        """When MFnLatticeData isn't available in the Python API
        (Maya 2024), the helper returns None for ``None`` input
        without crashing. The full path is exercised by
        test_phaseH_2_lattice.py when HAS_LATTICE_DATA is True."""
        from mpynode._common.lifecycle import init_helpers as ih

        out = ih.mfnlattice_to_numpy_points(None)
        self.assertIsNone(out)


class TestJointChainWalk(unittest.TestCase):
    def test_returns_empty_list_on_garbage_input(self):
        from mpynode._common.lifecycle import init_helpers as ih

        out = ih.joint_chain_walk(None)
        self.assertEqual(out, [])


# ===================== from test_scene_open_type_filter.py =====================
import unittest


class TestSceneOpenPreFiltersTypes(unittest.TestCase):
    def test_filter_uses_allnodetypes(self):
        import inspect
        from mpynode._common.lifecycle import scene_callbacks

        src = inspect.getsource(scene_callbacks._on_scene_opened)
        self.assertIn("allNodeTypes", src,
            "_on_scene_opened must pre-filter via cmds.allNodeTypes() "
            "to suppress Unknown-object-type warnings")
        self.assertIn("known_types", src)

    def test_filter_skips_unknown_types_silently(self):
        """If we monkey-patch the tracked list to include a fake
        type Maya doesn't know about, _on_scene_opened must NOT
        try to ls() that type."""
        from mpynode._common.lifecycle import init_registry, scene_callbacks

        # _register_init_sources_for_tracked read the tracked-types tuple by
        # value at module load, so patch the scene_callbacks binding, which
        # is the name the handler sees.
        original      = scene_callbacks._INIT_TRACKED_NODE_TYPES
        original_ns   = init_registry._NODE_INIT_NS.copy()
        original_bind = init_registry._INIT_BINDINGS.copy()
        try:
            scene_callbacks._INIT_TRACKED_NODE_TYPES = (
                "definitely_not_a_real_maya_node_type",
            )
            # ls() on the bogus type would only warn, and warnings are hard
            # to capture here, so just check the handler doesn't raise.
            scene_callbacks._on_scene_opened(None)
        finally:
            scene_callbacks._INIT_TRACKED_NODE_TYPES = original
            init_registry._NODE_INIT_NS.clear()
            init_registry._NODE_INIT_NS.update(original_ns)
            init_registry._INIT_BINDINGS.clear()
            init_registry._INIT_BINDINGS.update(original_bind)


# ===================== from test_init_tab_completeness.py =====================
import unittest


REQUIRED_INIT_METHODS = (
    "set_init_expression",
    "get_init_expression",
    "clear_init_expression",
)


class TestInitSourceMixinOnAllWrappers(unittest.TestCase):
    def test_every_wrapper_has_init_source_methods(self):
        from mpynode._node_registry import REGISTRY

        missing = []
        for native_type, spec in REGISTRY.items():
            try:
                cls = spec.get_wrapper_class()
            except Exception as exc:
                self.fail(
                    f"failed to load wrapper for {native_type!r}: {exc}"
                )
            for method in REQUIRED_INIT_METHODS:
                if not hasattr(cls, method):
                    missing.append(
                        f"{native_type} ({cls.__module__}.{cls.__name__})"
                        f" missing {method!r}"
                    )
        if missing:
            self.fail(
                "Init-tab gating in the Node Designer requires every "
                "wrapper to expose the InitSourceMixin surface. "
                "Missing:\n  " + "\n  ".join(missing)
            )

    def test_every_registry_type_in_init_tracked_list(self):
        """The scene-open auto-load + scene-change cleanup walks
        every type in ``_INIT_TRACKED_NODE_TYPES``. It must cover
        every type in REGISTRY (otherwise a node with a persisted
        ``_initSource`` plug would be silently skipped on.ma open
        for the untracked type)."""
        from mpynode._node_registry import REGISTRY
        from mpynode._common.lifecycle.init_registry import _INIT_TRACKED_NODE_TYPES

        registered = set(REGISTRY.keys())
        tracked    = set(_INIT_TRACKED_NODE_TYPES)
        missing    = registered - tracked
        self.assertFalse(
            missing,
            f"REGISTRY types not in _INIT_TRACKED_NODE_TYPES: "
            f"{sorted(missing)}. Scene-open auto-load skips these.",
        )


# ===========================================================================
# T38 -- Init exec is gated on the per-scene trust flag
# ===========================================================================


class TestInitExecTrustGate(unittest.TestCase):
    """``register_init_source`` must NOT exec file-supplied Init code when
    the per-scene pickle-trust flag says the scene is untrusted."""

    PROBE = "_t38_init_exec_probe"

    def setUp(self):
        import os
        import sys
        import types

        from mpynode._common.io import trust
        from mpynode._common.lifecycle import init_registry

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        init_registry.clear_all_init_ns()

        self.trust        = trust
        self.ir           = init_registry
        self._prior_trust = trust.pickle_trusted()
        self._prior_env   = os.environ.pop("MPYNODE_TRUST_PICKLE", None)
        self.addCleanup(self._restore)

        probe                   = types.ModuleType(self.PROBE)
        probe.ran               = False
        sys.modules[self.PROBE] = probe
        self.probe              = probe

        plane = mc.polyPlane(name="t38_p", sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.node = MPyDeformer.create_on(plane).get_name()
        self.src = "import {p}\n{p}.ran = True\nT38_VALUE = 7\n".format(
            p=self.PROBE
        )

    def _restore(self):
        import os
        import sys

        sys.modules.pop(self.PROBE, None)
        if self._prior_env is None:
            os.environ.pop("MPYNODE_TRUST_PICKLE", None)
        else:
            os.environ["MPYNODE_TRUST_PICKLE"] = self._prior_env
        self.trust.note_file_opened(self._prior_trust)

    def _uuid(self):
        return self.ir._node_uuid_from_name(self.node)

    def test_untrusted_scene_halts_init_exec(self):
        self.trust.note_file_opened(False)
        ok = self.ir.register_init_source(self.node, self.src)
        self.assertFalse(ok)
        self.assertFalse(self.probe.ran, "Init code ran on an untrusted scene")
        uuid = self._uuid()
        self.assertNotIn(uuid, self.ir._NODE_INIT_NS)
        self.assertNotIn(uuid, self.ir._INIT_BINDINGS)

    def test_trusted_scene_runs_init_exec(self):
        self.trust.note_file_opened(True)
        ok = self.ir.register_init_source(self.node, self.src)
        self.assertTrue(ok)
        self.assertTrue(self.probe.ran)
        self.assertIn(self._uuid(), self.ir._NODE_INIT_NS)

    def test_env_opt_in_allows_exec_while_flag_is_false(self):
        """Headless/batch opt-in: the EXISTING ``MPYNODE_TRUST_PICKLE`` env
        re-enables exec even while the per-scene flag reads False (which is
        also the forced-closed state for the whole open transition)."""
        import os

        self.trust.note_file_opened(False)
        os.environ["MPYNODE_TRUST_PICKLE"] = "1"
        ok                                 = self.ir.register_init_source(self.node, self.src)
        self.assertTrue(ok)
        self.assertTrue(self.probe.ran)

    def test_explicit_trusted_true_bypasses_flag(self):
        self.trust.note_file_opened(False)
        ok = self.ir.register_init_source(self.node, self.src, trusted=True)
        self.assertTrue(ok)
        self.assertTrue(self.probe.ran)

    def test_explicit_trusted_false_overrides_a_trusted_scene(self):
        self.trust.note_file_opened(True)
        ok = self.ir.register_init_source(self.node, self.src, trusted=False)
        self.assertFalse(ok)
        self.assertFalse(self.probe.ran)

    def test_set_init_expression_is_authoring_and_still_runs(self):
        """The wrapper setter carries source the caller supplied in-process
        (UI editor / demo builder / test), not source read out of an
        untrusted file -- it must keep working on an untrusted scene."""
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.trust.note_file_opened(False)
        w = MPyDeformer(self.node)
        self.assertTrue(w.set_init_expression(self.src))
        self.assertTrue(self.probe.ran)

    def test_scene_open_sweep_is_gated(self):
        """The real file-open path (``_register_init_sources_for_tracked``,
        driven by kAfterOpen) must report the node as failed and register
        nothing when the scene is untrusted."""
        from mpynode._common.lifecycle import scene_callbacks
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        MPyDeformer(self.node).set_init_expression(self.src)
        self.ir.clear_all_init_ns()
        self.probe.ran = False

        self.trust.note_file_opened(False)
        loaded, failed, _migrated = (
            scene_callbacks._register_init_sources_for_tracked(only_new=False)
        )
        self.assertEqual(loaded, 0)
        self.assertGreaterEqual(failed, 1)
        self.assertFalse(self.probe.ran)
        self.assertEqual(self.ir.init_ns_count(), 0)

    def test_denied_init_writes_no_stored_vars(self):
        """A halted Init must not leave the node half-initialised: no
        stored-var write-back, no bindings entry."""
        from mpynode._common.storedvars.stored_vars_api import get_variables

        self.trust.note_file_opened(False)
        ok = self.ir.register_init_source(
            self.node, "self.t38_half = 123\n"
        )
        self.assertFalse(ok)
        self.assertNotIn("t38_half", dict(get_variables(self.node) or {}))
        self.assertNotIn(self._uuid(), self.ir._INIT_BINDINGS)

    def test_empty_source_still_clears_on_untrusted_scene(self):
        """Clearing is not exec -- it must not be blocked by the gate."""
        self.trust.note_file_opened(True)
        self.assertTrue(self.ir.register_init_source(self.node, self.src))
        self.trust.note_file_opened(False)
        self.assertTrue(self.ir.register_init_source(self.node, ""))
        self.assertNotIn(self._uuid(), self.ir._NODE_INIT_NS)


# ===========================================================================
# T38 (a) -- Compute exec is gated on the SAME per-scene trust flag
# ===========================================================================


class TestComputeExecTrustGate(unittest.TestCase):
    """``exec_with_profile_watch`` must NOT exec a node's compute code when
    the scene is untrusted. A node-bound call carries code read out of the
    node's ``_computeSource`` plug (i.e. out of the file); a node-less call
    carries code the caller supplied in-process and stays ungated."""

    PROBE = "_t38_compute_exec_probe"

    def setUp(self):
        import os
        import sys
        import types

        import maya.OpenMaya as om1

        from mpynode._common.compute import expression as expr
        from mpynode._common.io import trust

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

        self.trust        = trust
        self.expr         = expr
        self._prior_trust = trust.pickle_trusted()
        self._prior_env   = os.environ.pop("MPYNODE_TRUST_PICKLE", None)
        self.addCleanup(self._restore)

        probe                   = types.ModuleType(self.PROBE)
        probe.ran               = False
        sys.modules[self.PROBE] = probe
        self.probe              = probe
        self.code = compile(
            "import {p}\n{p}.ran = True\n".format(p=self.PROBE),
            "<t38-compute>",
            "exec",
        )

        plane = mc.polyPlane(name="t38_c", sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.node = MPyDeformer.create_on(plane).get_name()
        sel       = om1.MSelectionList()
        sel.add(self.node)
        self.mobj = om1.MObject()
        sel.getDependNode(0, self.mobj)

    def _restore(self):
        import os
        import sys

        sys.modules.pop(self.PROBE, None)
        if self._prior_env is None:
            os.environ.pop("MPYNODE_TRUST_PICKLE", None)
        else:
            os.environ["MPYNODE_TRUST_PICKLE"] = self._prior_env
        self.trust.note_file_opened(self._prior_trust)

    def test_untrusted_scene_halts_compute_exec(self):
        self.trust.note_file_opened(False)
        ok = self.expr.exec_with_profile_watch(
            self.code, {}, node_obj=self.mobj
        )
        self.assertFalse(ok)
        self.assertFalse(self.probe.ran, "compute ran on an untrusted scene")

    def test_refusal_leaves_the_namespace_untouched(self):
        """The gate must bail BEFORE the Init-namespace merge and the
        ``node`` PlugProxy injection, so a refused node is never left
        half-wired."""
        self.trust.note_file_opened(False)
        ns = {}
        self.expr.exec_with_profile_watch(self.code, ns, node_obj=self.mobj)
        self.assertEqual(ns, {})

    def test_trusted_scene_runs_compute_exec(self):
        self.trust.note_file_opened(True)
        ok = self.expr.exec_with_profile_watch(
            self.code, {}, node_obj=self.mobj
        )
        self.assertTrue(ok)
        self.assertTrue(self.probe.ran)

    def test_env_opt_in_allows_compute_exec(self):
        """Headless/batch opt-in -- the SAME ``MPYNODE_TRUST_PICKLE`` the Init
        gate uses, not a second mechanism."""
        import os

        self.trust.note_file_opened(False)
        os.environ["MPYNODE_TRUST_PICKLE"] = "1"
        ok = self.expr.exec_with_profile_watch(
            self.code, {}, node_obj=self.mobj
        )
        self.assertTrue(ok)
        self.assertTrue(self.probe.ran)

    def test_nodeless_caller_is_not_gated(self):
        """No ``node_obj`` == the code did not come out of a scene file."""
        self.trust.note_file_opened(False)
        ok = self.expr.exec_with_profile_watch(self.code, {})
        self.assertTrue(ok)
        self.assertTrue(self.probe.ran)

    def _build_e2e_node(self, name):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=name)
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = 42.0\n")
        return n.get_name()

    def test_real_compute_path_is_gated_end_to_end(self):
        """Through the shipped api2 compute, not just the exec helper. Two
        nodes rather than one dirtied twice, so the assertion can't ride on
        dirty-propagation subtleties."""
        self.trust.note_file_opened(False)
        denied = self._build_e2e_node("t38_e2e_denied")
        self.assertEqual(mc.getAttr(denied + ".out"), 0.0)

        self.trust.note_file_opened(True)
        allowed = self._build_e2e_node("t38_e2e_allowed")
        self.assertAlmostEqual(mc.getAttr(allowed + ".out"), 42.0, places=5)


# ===========================================================================
# T38 (b) -- the open-time scan must count node Python, not just pickle
# ===========================================================================


class TestSceneTrustScanSeesNodePython(unittest.TestCase):
    """Without this, a PICKLE-FREE scene resolves trusted with no prompt and
    its Init/Compute Python runs on open."""

    def setUp(self):
        from mpynode._common.lifecycle import trust_prompt

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        self.tp = trust_prompt

        plane   = mc.polyPlane(name="t38_s", sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.w    = MPyDeformer.create_on(plane)
        self.node = self.w.get_name()

    def test_code_free_pickle_free_scene_needs_no_trust(self):
        self.assertFalse(self.tp._scene_has_pickle_blobs(mc))

    def test_init_source_alone_needs_trust(self):
        self.w.set_init_expression("T38_SCAN = 1\n")
        self.assertTrue(self.tp._scene_has_pickle_blobs(mc))

    def test_compute_source_alone_needs_trust(self):
        self.w.set_compute_expression("T38_SCAN = 1\n")
        self.assertTrue(self.tp._scene_has_pickle_blobs(mc))

    def test_legacy_jit_source_alone_needs_trust(self):
        """The open sweep still migrates AND EXECS a legacy ``_jitSource``
        (``scene_callbacks._register_init_sources_for_tracked``), so an old
        ``.ma`` that only has that attr must still be asked about."""
        mc.addAttr(self.node, longName="_jitSource", dataType="string")
        mc.setAttr(self.node + "._jitSource", "T38_SCAN = 1\n", type="string")
        self.assertTrue(self.tp._scene_has_pickle_blobs(mc))

    def test_unset_api1_computeSource_default_needs_no_trust(self):
        """api1 creates ``_computeSource`` holding the literal ``"None"``; a
        brand-new node has nothing to exec and must not trigger a prompt."""
        mc.setAttr(self.node + "._computeSource", "None", type="string")
        self.assertFalse(self.tp._scene_has_pickle_blobs(mc))

    def test_whitespace_only_source_needs_no_trust(self):
        mc.setAttr(self.node + "._computeSource", "  \n\t", type="string")
        self.assertFalse(self.tp._scene_has_pickle_blobs(mc))

    def test_viewport_source_alone_needs_trust(self):
        """``_viewportSource`` is a STORABLE string plug read straight out of
        the file and exec'd through ``exec_with_profile_watch`` on every VP2
        shader update (``_api2/mpy_file.py``). Scanning only Init/Compute let a
        pickle-free ``.ma`` whose payload lives there resolve TRUSTED with no
        prompt -- and the exec gate then waved it through."""
        mc.file(new=True, force=True)
        f = mc.createNode("mPyFile")
        for attr in ("_computeSource", "_initSource"):
            if mc.attributeQuery(attr, node=f, exists=True):
                mc.setAttr("%s.%s" % (f, attr), "", type="string")
        mc.setAttr(f + "._viewportSource", "", type="string")
        self.assertFalse(self.tp._scene_has_pickle_blobs(mc))
        mc.setAttr(f + "._viewportSource", "T38_SCAN = 1\n", type="string")
        self.assertTrue(self.tp._scene_has_pickle_blobs(mc))


class TestPickleFreeSceneOpenIsGated(unittest.TestCase):
    """HEADLINE for T38: opening a pickle-free ``.ma`` whose mPy node carries
    Init code must not silently run it. Headless can't prompt -> deny."""

    PROBE = "_t38_open_probe"

    def setUp(self):
        import os
        import shutil
        import sys
        import tempfile
        import types

        from mpynode._common.io import trust

        mc.file(new=True, force=True)
        ensure_plugins_loaded()

        self.trust        = trust
        self._prior_trust = trust.pickle_trusted()
        self._prior_env   = os.environ.pop("MPYNODE_TRUST_PICKLE", None)

        probe                   = types.ModuleType(self.PROBE)
        probe.ran               = False
        sys.modules[self.PROBE] = probe
        self.probe              = probe

        plane = mc.polyPlane(name="t38_o", sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        w = MPyDeformer.create_on(plane)
        w.set_init_expression(
            "import {p}\n{p}.ran = True\n".format(p=self.PROBE)
        )

        # A fresh dir so the persistent "Always" store can't pre-trust it.
        self.tmpdir = tempfile.mkdtemp(prefix="t38_open_")
        self.path   = os.path.join(self.tmpdir, "t38_open.ma")
        mc.file(rename=self.path)
        mc.file(save=True, type="mayaAscii", force=True)
        mc.file(new=True, force=True)
        probe.ran = False  # only the OPEN may flip this

        self.addCleanup(self._restore)
        self.addCleanup(shutil.rmtree, self.tmpdir, True)

    def _restore(self):
        import os
        import sys

        mc.file(new=True, force=True)
        sys.modules.pop(self.PROBE, None)
        if self._prior_env is None:
            os.environ.pop("MPYNODE_TRUST_PICKLE", None)
        else:
            os.environ["MPYNODE_TRUST_PICKLE"] = self._prior_env
        self.trust.note_file_opened(self._prior_trust)

    def test_open_does_not_run_init_without_trust(self):
        mc.file(self.path, open=True, force=True)
        self.assertFalse(
            self.trust.pickle_trusted(),
            "a pickle-free scene carrying node Python resolved TRUSTED",
        )
        self.assertFalse(self.probe.ran, "Init ran on open with no prompt")

    def test_env_opt_in_restores_the_open(self):
        import os

        os.environ["MPYNODE_TRUST_PICKLE"] = "1"
        mc.file(self.path, open=True, force=True)
        self.assertTrue(self.probe.ran)


# ===========================================================================
# T38 (c) -- the prompt text
# ===========================================================================


class _FakeButton:
    def __init__(self, label):
        self.label = label


class _FakeMessageBox:
    """Enough QMessageBox for ``_make_trust_prompt`` to run headless. The real
    prompt only ever appears in the GUI, so this is the only way the shipped
    wording + button wiring get exercised at all."""

    Warning     = object()
    YesRole     = object()
    AcceptRole  = object()
    NoRole      = object()

    click_label = "Don't Trust"
    last        = None

    def __init__(self):
        self.title       = ""
        self.text        = ""
        self.informative = ""
        self.buttons     = []
        type(self).last = self

    def setIcon(self, _icon):
        pass

    def setWindowTitle(self, t):
        self.title = t

    def setText(self, t):
        self.text = t

    def setInformativeText(self, t):
        self.informative = t

    def addButton(self, label, _role):
        b = _FakeButton(label)
        self.buttons.append(b)
        return b

    def exec_(self):
        pass

    def clickedButton(self):
        for b in self.buttons:
            if b.label == type(self).click_label:
                return b
        return None


class TestTrustPromptTextMatchesTheGate(unittest.TestCase):
    """The prompt used to promise that Init/Compute Python runs on open
    "regardless of this choice". With the gate in, that is false."""

    def setUp(self):
        from mpynode.ui import qt_wrapper

        self.qt                     = qt_wrapper
        self._prior_box             = qt_wrapper.QMessageBox
        qt_wrapper.QMessageBox      = _FakeMessageBox
        _FakeMessageBox.last        = None
        _FakeMessageBox.click_label = "Don't Trust"
        self.addCleanup(self._restore)

    def _restore(self):
        self.qt.QMessageBox         = self._prior_box
        _FakeMessageBox.last        = None
        _FakeMessageBox.click_label = "Don't Trust"

    def _run(self, subject, path="/tmp/x.ma", allow_always=True):
        from mpynode._common.lifecycle import trust_prompt

        decision = trust_prompt.make_trust_prompt(
            allow_always=allow_always, subject=subject
        )(path)
        return decision, _FakeMessageBox.last

    def test_scene_prompt_says_the_code_will_not_run(self):
        decision, box = self._run("scene")
        self.assertEqual(decision, "no")
        self.assertNotIn("already runs", box.informative)
        self.assertNotIn("does NOT sandbox", box.informative)
        self.assertIn("will not run", box.informative)
        self.assertIn("will not load", box.informative)

    def test_mpn_prompt_does_not_overclaim(self):
        """``load_mpn`` gates ONLY the pickle decode -- a template's
        Init/Compute is applied through the authoring setters -- so the
        template prompt must NOT promise an exec block it doesn't deliver."""
        decision, box = self._run(".mpn template")
        self.assertEqual(decision, "no")
        self.assertNotIn("will not run", box.informative)

    def test_buttons_still_resolve(self):
        _FakeMessageBox.click_label = "Trust"
        self.assertEqual(self._run("scene")[0], "yes")
        _FakeMessageBox.click_label = "Always Trust This Folder"
        self.assertEqual(self._run("scene")[0], "always_folder")

    def test_unsaved_scene_offers_no_always_button(self):
        _FakeMessageBox.click_label = "Always Trust This Folder"
        decision, box = self._run("scene", path=None)
        self.assertEqual(decision, "no")
        self.assertNotIn(
            "Always Trust This Folder", [b.label for b in box.buttons]
        )


def setUpModule():
    _setUpModule__phaseA_init_rename()
    _setUpModule__init_self_parity()
    _setUpModule__phaseB_init_proxy()
    _setUpModule__phaseJ_2_init_helpers()


if __name__ == "__main__":
    import unittest
    unittest.main()
