"""SelfProxy engine: no-legacy, compute-locals, dropped-locals inventory, output-scratch, api2 bridge

Consolidated from: test_phaseG_7_no_legacy_selfproxy.py, test_phaseG_0_compute_locals.py, test_phaseJ_0_dropped_compute_locals.py, test_self_proxy_output_scratch.py, test_phaseP_api2_dynamic_attr_bridge.py.
"""

from __future__ import annotations

# ===================== from test_phaseG_7_no_legacy_selfproxy.py =====================
import inspect
import os
import unittest
from tests import _paths


def _scripts_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return _paths.SCRIPTS


_SOURCE_SUBTREES = (
    "_api1",
    "_api2",
    "_common",
    "ui",
)


def _walk_source_py():
    scripts = _scripts_root()
    for sub in _SOURCE_SUBTREES:
        root = os.path.join(scripts, "mpynode", sub)
        for dp, _dn, fn in os.walk(root):
            for f in fn:
                if f.endswith(".py"):
                    yield os.path.join(dp, f)


class TestSelfProxyClassShape(unittest.TestCase):

    def test_only_one_class_named_self_proxy(self):
        from mpynode._common.compute import self_proxy

        src = inspect.getsource(self_proxy)
        self.assertNotIn("validate_internal_vars_schema", src)
        self.assertIn("class SelfProxy(object):", src)
        self.assertNotIn("class PlugSelfProxy", src)

    def test_constructor_accepts_compute_locals(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        sig    = inspect.signature(SelfProxy.__init__)
        params = list(sig.parameters)
        self.assertEqual(params[1], "mobject")
        self.assertIn("compute_locals", params)

    def test_get_compute_locals_present(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        self.assertTrue(hasattr(SelfProxy, "get_compute_locals"))
        self.assertTrue(hasattr(SelfProxy, "mark_compute_local_writable"))


class TestNoLegacyReferences(unittest.TestCase):

    def test_no_plug_selfproxy_construct_in_source(self):
        for path in _walk_source_py():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            self.assertNotIn(
                "PlugSelfProxy(",
                src,
                f"{path} still constructs PlugSelfProxy(...)",
            )
            self.assertNotIn(
                "import PlugSelfProxy",
                src,
                f"{path} still imports PlugSelfProxy",
            )

    def test_no_legacy_internal_schema_kwarg_in_source(self):
        for path in _walk_source_py():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            self.assertNotIn(
                "internal_schema=",
                src,
                f"{path} still uses legacy internal_schema= kwarg",
            )

    def test_no_legacy_validator_in_source(self):
        for path in _walk_source_py():
            with open(path, encoding="utf-8") as f:
                src = f.read()
            self.assertNotIn(
                "validate_internal_vars_schema",
                src,
                f"{path} still references validate_internal_vars_schema",
            )


# ===================== from test_phaseG_0_compute_locals.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseG_0_compute_locals():
    standalone_init()


def _new_node():
    """Make a throwaway mPyNode for plug-tree tests; return the
    MObject the proxy needs."""
    ensure_plugins_loaded()
    n   = mc.createNode("mPyNode")
    sel = om.MSelectionList()
    sel.add(n)
    obj = om.MObject()
    sel.getDependNode(0, obj)
    return n, obj


class TestComputeLocalsRead(unittest.TestCase):

    def test_pre_populated_value_readable(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        _, obj = _new_node()
        sp = SelfProxy(
            obj,
            compute_locals={"output_matrix": np.eye(4) * 2},
        )
        self.assertTrue(np.allclose(sp.output_matrix, np.eye(4) * 2))

    def test_compute_local_beats_init_binding(self):
        """Tier order: plug -> compute_locals -> init bindings -> stored.
        If both a compute_local and an init_binding define X, the
        compute_local wins (closer to the user expression)."""
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        _, obj = _new_node()
        sp = SelfProxy(
            obj,
            init_bindings  = {"X": "from_init"},
            compute_locals = {"X": "from_compute_local"},
        )
        self.assertEqual(sp.X, "from_compute_local")


class TestComputeLocalsWrite(unittest.TestCase):

    def test_assign_pre_populated_routes_to_locals(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        _, obj = _new_node()
        sp = SelfProxy(
            obj, compute_locals={"output_matrix": np.zeros((4, 4))}
        )
        # User expression-style write:
        sp.output_matrix = np.eye(4) * 3.5
        out              = sp.get_compute_locals()
        self.assertIn("output_matrix", out)
        self.assertTrue(np.allclose(out["output_matrix"], np.eye(4) * 3.5))

    def test_mutate_in_place_visible_in_harvest(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        _, obj = _new_node()
        arr                    = np.zeros((4, 4))
        sp                     = SelfProxy(obj, compute_locals={"output_matrix": arr})
        sp.output_matrix[0, 0] = 9.0
        self.assertEqual(sp.get_compute_locals()["output_matrix"][0, 0], 9.0)

    def test_unknown_name_falls_through_to_storage(self):
        """Tier-4 legacy behaviour: if X is not a plug and not a
        compute_local, ``self.X = v`` lands in user storage."""
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        _, obj = _new_node()
        sp               = SelfProxy(obj, compute_locals={})
        sp.brand_new_var = 42
        self.assertEqual(sp.get_user_storage().get("brand_new_var"), 42)
        self.assertNotIn("brand_new_var", sp.get_compute_locals())

    def test_mark_writable_then_assign_routes_to_locals(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        _, obj = _new_node()
        sp = SelfProxy(obj, compute_locals={})
        sp.mark_compute_local_writable("emit_count")
        sp.emit_count = 7
        self.assertEqual(sp.get_compute_locals().get("emit_count"), 7)
        self.assertNotIn("emit_count", sp.get_user_storage())


class TestHarvestSnapshot(unittest.TestCase):

    def test_get_compute_locals_returns_snapshot(self):
        """Mutating the returned dict must NOT affect the proxy."""
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        _, obj = _new_node()
        sp          = SelfProxy(obj, compute_locals={"foo": 1})
        snap        = sp.get_compute_locals()
        snap["foo"] = 999
        snap["new"] = "added"
        self.assertEqual(sp.get_compute_locals().get("foo"), 1)
        self.assertNotIn("new", sp.get_compute_locals())


class TestPlugTakesPrecedenceForRealPlug(unittest.TestCase):
    """If a name is a real plug AND in compute_locals, writes go to
    compute_locals (the legacy SelfProxy semantics: schema slot wins
    over plug). Reads also prefer plug -- the existing tier-1 read."""

    def test_writes_to_local_key_dont_set_real_plug(self):
        from mpynode._common.compute.self_proxy import SelfProxy

        mc.file(new=True, force=True)
        n, obj = _new_node()
        # ``message`` is a real plug on every node. We register it as
        # a compute_local so writes route there.
        sp         = SelfProxy(obj, compute_locals={"message": "scratch"})
        sp.message = "overwritten"
        self.assertEqual(sp.get_compute_locals()["message"], "overwritten")


# ===================== from test_phaseJ_0_dropped_compute_locals.py =====================
import os
import unittest


def _scripts_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return _paths.SCRIPTS


def _read(rel_path):
    full = os.path.join(_scripts_root(), "mpynode", rel_path)
    with open(full, encoding="utf-8") as f:
        return f.read()


class TestTransformKeepInventory(unittest.TestCase):
    """The GATED LOCAL-MATRIX compute_locals inventory: the four write slots
    (local_matrix / apply_rotate / apply_translate / apply_scale) plus the five
    per-channel READS this node's own live channels are seeded from (translate /
    rotate [radians] / scale / shear / rotate_order). The legacy ``world_matrix``
    write slot (WORLD placement is now a connected-parent expression) and the
    ``time`` / ``parent_matrix`` read slots + ``output_matrix`` write slot stay
    removed."""

    SRC = "_api1/mpy_transform.py"
    KEEP_KEYS = (
        '"translate":',
        '"rotate":',
        '"scale":',
        '"shear":',
        '"rotate_order":',
        '"local_matrix":',
        '"apply_rotate":',
        '"apply_translate":',
        '"apply_scale":',
    )
    # These legacy slots must NOT reappear as seeded compute_locals.
    GONE_KEYS = (
        '"time":',
        '"parent_matrix":',
        '"output_matrix":',
        '"world_matrix":',
    )

    def test_all_keep_keys_present(self):
        src = _read(self.SRC)
        for key in self.KEEP_KEYS:
            self.assertIn(
                key,
                src,
                f"{self.SRC} must keep compute_locals key {key!r}",
            )

    def test_legacy_keys_removed(self):
        src = _read(self.SRC)
        for key in self.GONE_KEYS:
            self.assertNotIn(
                key,
                src,
                f"{self.SRC} must NOT seed removed compute_locals key {key!r}",
            )


class TestConstraintKeepInventory(unittest.TestCase):
    """All 5 preset constraint inputs stay as KEEP-callback
    convenience numpy reads (per the J.0 design lock revision).

    updated the SHAPE of the reads (cmds.getAttr -> PlugProxy
    + CompoundPlugProxy.asNumpy()) but the SLOTS the user sees via
    self.X still exist. This test greps for the slot KEYS and the
    compute_locals plumbing -- not the specific
    ``preset_internals["X"] = cmds.getAttr(...)`` syntax which is gone.

    The EM rivet-to-origin fix folded ``preset_internals`` into a
    ``merged_locals`` dict (USER inputs seeded first, presets +
    output-defaults layered on top) that becomes ``compute_locals``, so
    the pin now tracks ``merged_locals.update(preset_internals)`` +
    ``compute_locals=merged_locals`` rather than the old direct pass."""

    SRC = "_api2/mpy_constraint.py"
    KEEP_FRAGMENTS = (
        '"targetTranslate"',
        '"targetRotate"',
        '"targetWeight"',
        '"restTranslate"',
        '"restRotate"',
        "merged_locals.update(preset_internals)",
        "compute_locals=merged_locals",
    )

    def test_preset_internals_kept(self):
        src = _read(self.SRC)
        for frag in self.KEEP_FRAGMENTS:
            self.assertIn(
                frag,
                src,
                f"{self.SRC} must keep preset_internals fragment {frag!r}",
            )


class TestGeneratorTimeFrameKept(unittest.TestCase):
    """``time`` stays as a KEEP-callback compute_local (now a
    ``TimeFloat`` carrying the scene fps) on poly/curve/surface/locator."""

    NODES = (
        "_api2/mpy_mesh.py",
        "_api2/mpy_nurbs_curve.py",
        "_api2/mpy_nurbs_surface.py",
        "_api2/mpy_locator.py",
    )

    def test_time_compute_local_kept(self):
        for src_path in self.NODES:
            src = _read(src_path)
            self.assertIn(
                '"time":',
                src,
                f"{src_path} should keep the 'time' KEEP-callback slot",
            )


class TestKeepFamilyUnchanged(unittest.TestCase):
    """iksolver keeps ALL its compute_locals (callback-sourced data; not
    redundant with plugs)."""

    def test_iksolver_keeps_joints(self):
        src = _read("_api1/helpers.py")
        self.assertIn('"joints":', src)


# ===================== from test_self_proxy_output_scratch.py =====================
import unittest

import maya.cmds as mc
import maya.OpenMaya as om

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__self_proxy_output_scratch():
    standalone_init()
    ensure_plugins_loaded()


def _node_with_string_attr(attr_name, value):
    """Create a node with a MANAGED string input attr set to ``value``; return
    (name, api1 MObject) for the SelfProxy.

    The attr goes in through ``add_input_attr`` rather than a bare
    ``cmds.addAttr``: plug governance only surfaces attributes the node
    manages, so an addAttr'd plug is deliberately invisible to ``self.<name>``.
    These tests are about read/write PRECEDENCE between a real plug and an
    output-scratch slot, which needs the plug to be a real managed one."""
    from mpynode import MPyNode

    nd = MPyNode.create()
    nd.add_input_attr(attr_name, "string")
    n = nd.get_name()
    mc.setAttr(n + "." + attr_name, value, type="string")
    sel = om.MSelectionList()
    sel.add(n)
    obj = om.MObject()
    sel.getDependNode(0, obj)
    return n, obj


class TestOutputScratchReadPrecedence(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)

    def test_real_plug_wins_on_read_for_scratch_name(self):
        """The keystone: ``text`` is a write-only output-scratch slot AND a
        real input plug. Reading ``self.text`` must return the PLUG value."""
        from mpynode._common.compute.self_proxy import SelfProxy

        n, obj = _node_with_string_attr("text", "WORLD")
        sp = SelfProxy(
            obj,
            compute_locals      = {"text": None},  # draw-buffer scratch slot
            output_scratch_keys = {"text"},        # declared write-only output
        )
        self.assertEqual(sp.text, "WORLD")

    def test_write_to_scratch_name_lands_in_locals_not_plug(self):
        """Write asymmetry: ``self.text = {...}`` feeds the scratch slot
        (harvested for drawing); the real input plug is untouched."""
        from mpynode._common.compute.self_proxy import SelfProxy

        n, obj = _node_with_string_attr("text", "WORLD")
        sp = SelfProxy(
            obj,
            compute_locals      = {"text": None},
            output_scratch_keys = {"text"},
        )
        sp.text = {"strings": ["A", "B"]}
        self.assertEqual(sp.get_compute_locals()["text"], {"strings": ["A", "B"]})
        # The user's input plug must NOT have been clobbered.
        self.assertEqual(mc.getAttr(n + ".text"), "WORLD")

    def test_scratch_name_without_plug_returns_scratch_value(self):
        """No regression: a scratch name with NO backing plug still reads its
        scratch value (None until the user assigns it)."""
        from mpynode._common.compute.self_proxy import SelfProxy

        n   = mc.createNode("mPyNode")
        sel = om.MSelectionList()
        sel.add(n)
        obj = om.MObject()
        sel.getDependNode(0, obj)
        sp = SelfProxy(
            obj,
            compute_locals      = {"lines": None},
            output_scratch_keys = {"lines"},
        )
        self.assertIsNone(sp.lines)
        sp.lines = {"starts": [1]}
        self.assertEqual(sp.get_compute_locals()["lines"], {"starts": [1]})

    def test_non_scratch_compute_local_still_wins_on_read(self):
        """mPyFile regression guard: a compute_local NOT in output_scratch_keys
        still wins on read even when a real plug of the same name exists -- so
        ``self.<input>`` resolves with NO plug read on the worker thread."""
        from mpynode._common.compute.self_proxy import SelfProxy

        n, obj = _node_with_string_attr("gain", "PLUGVAL")
        sp = SelfProxy(
            obj,
            compute_locals={"gain": "LOCALVAL"},   # NOT an output-scratch key
        )
        self.assertEqual(sp.gain, "LOCALVAL")

    def test_default_no_scratch_keys_is_backwards_compatible(self):
        """With no output_scratch_keys (the default), a compute_local shadows a
        plug on read -- the long-standing Tier-1 behavior."""
        from mpynode._common.compute.self_proxy import SelfProxy

        n, obj = _node_with_string_attr("text", "WORLD")
        sp = SelfProxy(obj, compute_locals={"text": None})
        self.assertIsNone(sp.text)


class TestLocatorDrawInputCollision(unittest.TestCase):
    """End-to-end repro through a real mPyLocator: a user INPUT whose name
    collides with an output-scratch slot must stay readable via ``self.X``.

    The locator's scratch slots are ``draw`` / ``auto_highlight`` /
    ``auto_refresh`` / ``precise_hover``; a same-named input has no other way in,
    so a scratch slot shadowing it on READ is a silent data loss."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_draw_input_readable_despite_the_draw_scratch_slot(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="rtCollide")
        loc.add_input_attr("draw", "string")
        mc.setAttr(loc.get_name() + ".draw", "WORLD", type="string")
        # Read the input via self.draw, stash it where we can observe it.
        loc.set_compute_expression(
            "from mpynode._common.draw.draw_types import DrawText\n"
            "self.draw = DrawText(self.draw)\n")
        cmds = loc.evaluate_draw_commands()["commands"]
        self.assertEqual(
            cmds[0]["buffer"]["strings"], ["WORLD"],
            "self.draw read the output scratch (None) instead of the user's "
            "'draw' input plug",
        )

    def test_input_read_and_drawing_write_coexist(self):
        """The textGizmo pattern: read the same-named input early, then write
        the drawing to that slot later -- both must work."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="rtBoth")
        loc.add_input_attr("draw", "string")
        mc.setAttr(loc.get_name() + ".draw", "HELLO", type="string")
        loc.set_compute_expression(
            "from mpynode._common.draw.draw_types import DrawText\n"
            "msg = self.draw\n"
            "self.draw = DrawText(list(msg), [(i, 0, 0) for i in range(len(msg))])\n"
        )
        cmds = loc.evaluate_draw_commands()["commands"]
        self.assertEqual(cmds[0]["buffer"]["strings"], list("HELLO"))


class TestGeometryGeneratorScratchKeys(unittest.TestCase):
    """mPyMesh / mPyNurbsCurve / mPyNurbsSurface seed FIXED framework
    output-buffer names into compute_locals (points / cvs / outMesh / ...), the
    same bug class as the locator. They must declare those as output-scratch so
    a user input of the same name is readable. Spy on SelfProxy construction to
    confirm the wiring; the read/write mechanism itself is pinned by
    TestOutputScratchReadPrecedence above.
    """

    def setUp(self):
        mc.file(new=True, force=True)

    def _capture_scratch_keys(self, create_fn, output_plug):
        # These node modules import SelfProxy LOCALLY inside compute(), so patch
        # the shared source module -- the local ``from ... import SelfProxy``
        # resolves the attribute at call time and picks up the spy.
        import mpynode._common.compute.self_proxy as SP

        captured = {}
        orig     = SP.SelfProxy

        def _spy(*args, **kwargs):
            captured["osk"] = set(kwargs.get("output_scratch_keys") or ())
            captured["cl"]  = set((kwargs.get("compute_locals") or {}).keys())
            return orig(*args, **kwargs)

        SP.SelfProxy = _spy
        try:
            name = create_fn()
            mc.getAttr(name + "." + output_plug)  # triggers compute()
        finally:
            SP.SelfProxy = orig
        self.assertIn("osk", captured, "compute() never built a SelfProxy")
        return captured

    def test_mesh_declares_output_scratch_keys(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        def _make():
            loc = MPyMesh.create(name="oskMesh")
            loc.set_compute_expression("self.points = None\n")
            return loc.get_name()

        cap = self._capture_scratch_keys(_make, "outMesh")
        osk, cl = cap["osk"], cap["cl"]
        self.assertTrue(osk, "mPyMesh passed no output_scratch_keys")
        self.assertTrue(osk <= cl, "scratch keys must be real compute_locals: %r" % osk)
        for k in ("points", "colors", "normals", "outMesh"):
            self.assertIn(k, osk)
        self.assertNotIn("time", osk, "context 'time' must not be output-scratch")

    def test_nurbs_curve_declares_output_scratch_keys(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve

        def _make():
            loc = MPyNurbsCurve.create(name="oskCurve")
            loc.set_compute_expression("self.cvs = None\n")
            return loc.get_name()

        cap = self._capture_scratch_keys(_make, "outCurve")
        osk, cl = cap["osk"], cap["cl"]
        self.assertTrue(osk <= cl, "scratch keys must be real compute_locals: %r" % osk)
        for k in ("cvs", "knots", "outCurve"):
            self.assertIn(k, osk)
        self.assertNotIn("time", osk)
        # Only PURE None-seeded output buffers are scratch. Non-None
        # build-param DEFAULTS must NOT be -- marking them creates a read!=build
        # split (self.degree reads an input while the curve builds at default).
        for k in ("degree", "form", "rational"):
            self.assertNotIn(
                k, osk,
                "build-param default %r must not be output-scratch" % k)

    def test_nurbs_surface_declares_output_scratch_keys(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface

        def _make():
            loc = MPyNurbsSurface.create(name="oskSurf")
            loc.set_compute_expression("self.cvs = None\n")
            return loc.get_name()

        cap = self._capture_scratch_keys(_make, "outSurface")
        osk, cl = cap["osk"], cap["cl"]
        self.assertTrue(osk <= cl, "scratch keys must be real compute_locals: %r" % osk)
        for k in ("cvs", "num_cvs_u", "num_cvs_v", "knots_u", "knots_v", "outSurface"):
            self.assertIn(k, osk)
        self.assertNotIn("time", osk)
        # Non-None build-param defaults must NOT be scratch (see curve test).
        for k in ("degree_u", "degree_v", "form_u", "form_v"):
            self.assertNotIn(
                k, osk,
                "build-param default %r must not be output-scratch" % k)


class TestIkSolverScratchKeys(unittest.TestCase):
    """The IK solve helper (compute_ik_user_solve) seeds two in-place-mutated
    matrix output buffers (local_matrices / world_matrices) into
    compute_locals. Both are implausible input names, so there are no
    None-seeded pure write targets -- output_scratch_keys is EMPTY, and the
    buffers are left unmarked so ``self.local_matrices[i] = ...`` (and the
    world variant) keep mutating the seeded lists. The decoded reads
    (joints/end_effector/pole_vector/twist) must NOT be scratch.
    """

    def test_ik_helper_seeds_matrix_buffers_no_scratch(self):
        import inspect

        from mpynode._api1 import helpers

        src = inspect.getsource(helpers.compute_ik_user_solve)
        self.assertIn(
            "output_scratch_keys", src,
            "compute_ik_user_solve must pass output_scratch_keys to SelfProxy")
        # Both matrix output buffers are seeded as compute_locals.
        self.assertIn('"local_matrices"', src)
        self.assertIn('"world_matrices"', src)
        # No None-seeded scratch targets remain -- the scratch set is empty.
        self.assertIn("output_scratch_keys=set()", src)


class TestMeshInputCollisionEndToEnd(unittest.TestCase):
    """End-to-end: a vector input named ``colors`` (collides with the mesh
    ``colors`` draw buffer) must be readable via ``self.colors`` in compute."""

    def setUp(self):
        mc.file(new=True, force=True)

    def test_colors_input_readable_despite_buffer_slot(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        loc = MPyMesh.create(name="meshCollide")
        loc.add_input_attr("colors", "vector")
        mc.setAttr(loc.get_name() + ".colors", 0.25, 0.5, 0.75, type="double3")
        # Read the input via self.colors, persist it as a stored var so we can
        # observe it after compute commits.
        loc.set_compute_expression(
            "self.seen_colors = [round(float(c), 3) for c in self.colors]\n"
        )
        mc.getAttr(loc.get_name() + ".outMesh")  # trigger compute + var commit
        self.assertEqual(
            loc.get_variables().get("seen_colors"), [0.25, 0.5, 0.75]
        )


# ===================== from test_phaseP_api2_dynamic_attr_bridge.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseP_api2_dynamic_attr_bridge():
    standalone_init()


class TestApi2DynamicAttrBridge(unittest.TestCase):
    """Each api2 wrapper must let the user expression read a
    user-added dynamic attribute via ``self.X``."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def _run_compute_with_offset_read(self, wrapper, native_type, force_attr):
        """Add a dynamic ``offset`` input, set it to 5.0, write an
        expression that reads ``self.offset``, force compute by
        pulling ``force_attr``, and assert no errors leaked."""
        wrapper.add_input_attr("offset", "float")
        mc.setAttr(wrapper.get_name() + ".offset", 5.0)
        wrapper.set_compute_expression(
            "import numpy as np\n"
            "captured_offset = float(self.offset)\n"
            "self.last_offset = captured_offset\n"
        )
        # Force compute; it must not raise SelfProxy's
        # "AttributeError: 'self' has no plug...".
        try:
            mc.getAttr(wrapper.get_name() + "." + force_attr)
        except Exception as exc:
            # cmds.getAttr may legitimately fail on a complex output plug; the
            # symptom we're after is the AttributeError inside the expression.
            pass
        # The storage write happened iff the expression succeeded. Stored vars
        # live in the deferred in-memory store during a session (the
        # ``_storedVarsData`` plug is cleared on load and only repopulated on
        # save/export), so read through the API.
        try:
            from mpynode._common.storedvars.stored_vars_api import get_variables

            stored = get_variables(wrapper.get_name())
        except Exception:
            stored = {}
        self.assertEqual(
            stored.get("last_offset"), 5.0,
            f"{native_type} expression failed to read self.offset "
            f"(stored.last_offset = {stored.get('last_offset')!r}). "
            f"SelfProxy api1/api2 MObject bridge is broken.",
        )

    def test_mPyMesh_reads_user_attr(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh
        p = MPyMesh.create(name="bridgePoly")
        self._run_compute_with_offset_read(p, "mPyMesh", "outMesh")

    def test_mPyNurbsCurve_reads_user_attr(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
        c = MPyNurbsCurve.create(name="bridgeCurve")
        self._run_compute_with_offset_read(c, "mPyNurbsCurve", "outCurve")

    def test_mPyNurbsSurface_reads_user_attr(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface
        s = MPyNurbsSurface.create(name="bridgeSurf")
        self._run_compute_with_offset_read(s, "mPyNurbsSurface", "outSurface")


class TestApi1MObjectPassThrough(unittest.TestCase):
    """``_ensure_api1_mobject`` must not regress api1 callers
    (mPyDeformer / mPyTransform / etc.)."""

    def test_api1_mobject_passes_through_unchanged(self):
        import maya.OpenMaya as om1
        from mpynode._common.compute.self_proxy import _ensure_api1_mobject

        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        node = mc.createNode("transform", name="api1Test")
        sel = om1.MSelectionList(); sel.add(node)
        mob1 = om1.MObject(); sel.getDependNode(0, mob1)
        result = _ensure_api1_mobject(mob1)
        self.assertIs(result, mob1,
            "api1 MObject must pass through unchanged (no re-resolve)")

    def test_api2_mobject_bridges_to_api1(self):
        import maya.OpenMaya as om1
        import maya.api.OpenMaya as om2
        from mpynode._common.compute.self_proxy import _ensure_api1_mobject

        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        node = mc.createNode("transform", name="api2Test")
        sel2 = om2.MSelectionList(); sel2.add(node)
        mob2   = sel2.getDependNode(0)
        result = _ensure_api1_mobject(mob2)
        self.assertIsInstance(result, om1.MObject,
            "api2 MObject must be bridged to an api1 MObject")
        # And it must resolve to the same node.
        self.assertEqual(
            om1.MFnDependencyNode(result).name(), node,
            "bridged MObject should refer to the same Maya node",
        )


def setUpModule():
    _setUpModule__phaseG_0_compute_locals()
    _setUpModule__self_proxy_output_scratch()
    _setUpModule__phaseP_api2_dynamic_attr_bridge()


if __name__ == "__main__":
    import unittest
    unittest.main()
