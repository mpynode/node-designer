"""DG generator nodes: mPyMesh poly, mPyNurbsCurve, mPyNurbsSurface (merged-compute)

Consolidated from: test_phase31_1_poly.py, test_pass3_output_builder.py, test_phaseH_0_curve.py, test_phaseH_1_surface.py, test_phaseG_2_poly.py.
"""

from __future__ import annotations

# ===================== from test_phase31_1_poly.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase31_1_poly():
    standalone_init()


def _read_outmesh_counts(node):
    """Return (num_vertices, num_polygons) for a node's outMesh plug.
    Returns (0, 0) when the plug is null or the mesh is empty."""
    import maya.api.OpenMaya as om

    sel = om.MSelectionList()
    sel.add(node)
    mob      = sel.getDependNode(0)
    plug     = om.MFnDependencyNode(mob).findPlug("outMesh", True)
    mesh_obj = plug.asMObject()
    if mesh_obj.isNull():
        return (0, 0)
    try:
        mfn = om.MFnMesh(mesh_obj)
        return (mfn.numVertices, mfn.numPolygons)
    except Exception:
        return (0, 0)


def _read_outmesh(node):
    """Return an MFnMesh for a node's outMesh plug. Caller should
    use ``_read_outmesh_counts`` if the mesh may be empty."""
    import maya.api.OpenMaya as om

    sel = om.MSelectionList()
    sel.add(node)
    mob      = sel.getDependNode(0)
    plug     = om.MFnDependencyNode(mob).findPlug("outMesh", True)
    mesh_obj = plug.asMObject()
    if mesh_obj.isNull():
        mesh_obj = om.MFnMeshData().create()
    return om.MFnMesh(mesh_obj)


# ===========================================================================
# Plug-in registration
# ===========================================================================


class TestMPyMeshBasics(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_node_type_registered(self):
        self.assertIn("mPyMesh", mc.allNodeTypes() or [])

    def test_create_via_wrapper(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="myPolyGen")
        self.assertTrue(mc.objExists(p.get_name()))
        self.assertEqual(mc.nodeType(p.get_name()), "mPyMesh")

    def test_node_is_dg_not_dag(self):
        """MPyMesh is a plain DG node -- no parent transform after
        createNode. This is the architectural pivot from mPyShape."""
        n         = mc.createNode("mPyMesh", name="p1")
        inherited = mc.nodeType(n, inherited=True) or []
        self.assertNotIn("dagNode",      inherited)
        self.assertNotIn("shape",        inherited)
        self.assertNotIn("surfaceShape", inherited)
        # no parent transform was auto-created; listRelatives on a DG node
        # returns None or fails.
        parents = (
            mc.listRelatives(n, parent=True)
            if mc.objectType(n, isAType="dagNode")
            else None
        )
        self.assertIsNone(parents)

    def test_internal_attrs_present(self):
        n = mc.createNode("mPyMesh", name="p1")
        for plug in (
            "_computeSource",
            "_inputAttrs",
            "_outputAttrs",
            "_storedVarNames",
            "_storedVarsData",
            "debug_mode",
            "profile_enabled",
            "deep_profile_enabled",
            "watch_enabled",
            "_timeIn",
            "outMesh",
        ):
            self.assertTrue(
                mc.attributeQuery(plug, node=n, exists=True),
                f"plug {plug!r} missing on mPyMesh",
            )


# ===========================================================================
# Schema
# ===========================================================================


class TestMPyMeshCompute(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_empty_expression_produces_empty_mesh(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="p1")
        nv, nf = _read_outmesh_counts(p.get_name())
        self.assertEqual(nv, 0)
        self.assertEqual(nf, 0)

    def test_single_triangle_expression(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="p1")
        p.set_compute_expression(
            "import numpy as np\n"
            "self.points = np.array([[0,0,0],[1,0,0],[0,1,0]], dtype=np.float64)\n"
            "self.counts = np.array([3], dtype=np.int32)\n"
            "self.indices = np.array([0,1,2], dtype=np.int32)"
        )
        mfn = _read_outmesh(p.get_name())
        self.assertEqual(mfn.numVertices, 3)
        self.assertEqual(mfn.numPolygons, 1)

    def test_quad_expression(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="p1")
        p.set_compute_expression(
            "import numpy as np\n"
            "self.points = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]], dtype=np.float64)\n"
            "self.counts = np.array([4], dtype=np.int32)\n"
            "self.indices = np.array([0,1,2,3], dtype=np.int32)"
        )
        mfn = _read_outmesh(p.get_name())
        self.assertEqual(mfn.numVertices, 4)
        self.assertEqual(mfn.numPolygons, 1)

    def test_time_driven_mesh_reevals_per_frame(self):
        """Regression for the time-change callback: outMesh must re-eval
        on every timeline change."""
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="p1")
        # Time is opt-in: wire the scene clock so this mesh re-evaluates.
        mc.connectAttr("time1.outTime", p.get_name() + "._timeIn", force=True)
        p.set_compute_expression(
            "import numpy as np\n"
            "y = float(self.time) * 0.1\n"
            "self.points = np.array([[0,y,0],[1,y,0],[0,y+1,0]], dtype=np.float64)\n"
            "self.counts = np.array([3], dtype=np.int32)\n"
            "self.indices = np.array([0,1,2], dtype=np.int32)"
        )
        for f in (1, 10, 30, 50):
            mc.currentTime(f, edit=True)
            mfn = _read_outmesh(p.get_name())
            p0  = mfn.getPoint(0)
            self.assertAlmostEqual(
                p0.y,
                f * 0.1,
                places = 3,
                msg    = f"mesh stale at frame {f}",
            )

    def test_expression_error_fallback_empty_mesh(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="p1")
        p.set_compute_expression("this is not python at all!!!")
        nv, nf = _read_outmesh_counts(p.get_name())
        self.assertEqual(nv, 0)
        self.assertEqual(nf, 0)


# ===========================================================================
# Connect to a real mesh shape (the canonical rendering pattern)
# ===========================================================================


class TestOutMeshConnect(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_outMesh_connects_to_real_mesh_shape(self):
        """The canonical Maya pattern: mPyMesh.outMesh -> mesh.inMesh."""
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="p1")
        p.set_compute_expression(
            "import numpy as np\n"
            "self.points = np.array("
            "[[0,0,0],[1,0,0],[2,0,0],[3,0,0]], dtype=np.float64)\n"
            "self.counts = np.array([4], dtype=np.int32)\n"
            "self.indices = np.array([0,1,2,3], dtype=np.int32)"
        )
        downstream_xform = mc.polyCube(name="downstreamMesh")[0]
        downstream_shape = mc.listRelatives(downstream_xform, shapes=True)[0]
        mc.connectAttr(p.get_name() + ".outMesh", downstream_shape + ".inMesh", force=True)
        self.assertTrue(
            mc.isConnected(p.get_name() + ".outMesh", downstream_shape + ".inMesh")
        )


# ===========================================================================
# Demo
# ===========================================================================


# ===========================================================================
# Wrapper
# ===========================================================================


class TestMPyMeshWrapper(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_create_does_not_auto_connect_time(self):
        """Time is OPT-IN: a fresh mPyMesh is static (not wired to
        time1). The user opts in by connecting time1 (or adding a time
        input) when the expression needs the frame."""
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="p1")
        self.assertFalse(mc.isConnected("time1.outTime", p.get_name() + "._timeIn"))
        # Opting back in still works.
        mc.connectAttr("time1.outTime", p.get_name() + "._timeIn", force=True)
        self.assertTrue(mc.isConnected("time1.outTime", p.get_name() + "._timeIn"))

    def test_native_type_constant(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        self.assertEqual(MPyMesh.NATIVE_TYPE, "mPyMesh")

    def test_set_get_expression_roundtrip(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p   = MPyMesh.create(name="p1")
        src = "self.points = None"
        p.set_compute_expression(src)
        self.assertEqual(p.get_compute_expression(), src)


# ===================== from test_pass3_output_builder.py =====================
import unittest

import maya.cmds as mc


_API2_LOADED = False


def _ensure_plugins():
    global _API2_LOADED
    if not _API2_LOADED:
        if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
            mc.loadPlugin("mpynode_api2")
        _API2_LOADED = True


def _connect_render_shape(curve_node):
    xform = mc.createNode("transform", name=f"{curve_node}_xform")
    shape = mc.createNode(
        "nurbsCurve", name=f"{curve_node}_shape", parent=xform,
    )
    mc.connectAttr(curve_node + ".outCurve", shape + ".create", force=True)
    return xform, shape


# ---------------------------------------------------------------------------
# 1. build_default_output is a public framework function.
# ---------------------------------------------------------------------------


class TestFrameworkMarshallerIsPublic(unittest.TestCase):
    """The marshaller is importable, public, and reachable via the
    legacy underscore alias."""

    def test_public_name_importable(self):
        from mpynode._api2.mpy_nurbs_curve import build_default_output
        self.assertTrue(callable(build_default_output))
        self.assertEqual(build_default_output.__name__, "build_default_output")

    def test_back_compat_alias_same_object(self):
        from mpynode._api2.mpy_nurbs_curve import (
            build_default_output, _build_curve_data_object,
        )
        self.assertIs(
            _build_curve_data_object, build_default_output,
            "Legacy underscore name must be a same-object alias",
        )


# ---------------------------------------------------------------------------
# 2 + 3 + 4. Merged-compute behavior.
# ---------------------------------------------------------------------------


class TestMergedComputeWritesOutCurve(unittest.TestCase):
    """The merged-compute model: user code's
    ``self.outCurve = build_default_output(...)`` write inside the
    Compute expression must round-trip through compute_locals into
    the outCurve plug, without ever going through the unsafe
    plug-tree write path."""

    def setUp(self):
        _ensure_plugins()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyNurbsCurve", name="mergedTest")
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
        self.wrapper = MPyNurbsCurve(self.node)
        self.wrapper.set_init_expression(
            "import numpy as np\n"
            "from mpynode._api2.mpy_nurbs_curve import build_default_output\n"
        )
        self.xform, self.shape = _connect_render_shape(self.node)

    def test_self_outcurve_write_propagates_to_plug(self):
        """User writes ``self.outCurve = build_default_output(...)``
        in Compute; the curve must render correctly downstream."""
        self.wrapper.set_compute_expression(
            "import numpy as np\n"
            "u = np.linspace(0, 1, 8)\n"
            "self.cvs = np.stack(\n"
            "    [u * 4.0, np.sin(u * 6.28) * 0.5, np.zeros_like(u)],\n"
            "    axis=1,\n"
            ")\n"
            "self.degree = 3\n"
            "self.outCurve = build_default_output(\n"
            "    self.cvs, self.knots, self.degree, self.form,\n"
            ")\n"
        )
        mc.dgdirty(self.node + ".outCurve")
        spans = mc.getAttr(self.shape + ".spans")
        self.assertEqual(spans, 5, "8 cvs - degree 3 = 5 spans")
        cv7 = mc.pointPosition(f"{self.xform}|{self.shape}.cv[7]")
        self.assertAlmostEqual(cv7[0], 4.0, places=3)

    def test_no_outcurve_write_falls_back_to_framework_default(self):
        """User writes only cvs / degree / form -- no
        ``self.outCurve =...`` line. compute() must auto-marshall
        via the framework default. Same curve as the explicit case."""
        self.wrapper.set_compute_expression(
            "import numpy as np\n"
            "u = np.linspace(0, 1, 8)\n"
            "self.cvs = np.stack(\n"
            "    [u * 4.0, np.sin(u * 6.28) * 0.5, np.zeros_like(u)],\n"
            "    axis=1,\n"
            ")\n"
            "self.degree = 3\n"
        )
        mc.dgdirty(self.node + ".outCurve")
        cv7 = mc.pointPosition(f"{self.xform}|{self.shape}.cv[7]")
        self.assertAlmostEqual(
            cv7[0], 4.0, places=3,
            msg="No-outCurve-write path must produce the default curve",
        )

    def test_invalid_outcurve_write_falls_back_to_framework_default(self):
        """User writes ``self.outCurve = 'oops'`` -- not a valid
        kNurbsCurveData MObject. compute() must detect this and fall
        back to the framework default (NOT crash trying to push the
        string into ``setMObject``)."""
        self.wrapper.set_compute_expression(
            "import numpy as np\n"
            "u = np.linspace(0, 1, 8)\n"
            "self.cvs = np.stack(\n"
            "    [u * 4.0, np.sin(u * 6.28) * 0.5, np.zeros_like(u)],\n"
            "    axis=1,\n"
            ")\n"
            "self.degree = 3\n"
            "self.outCurve = 'this is not a curve'\n"
        )
        mc.dgdirty(self.node + ".outCurve")
        cv7 = mc.pointPosition(f"{self.xform}|{self.shape}.cv[7]")
        self.assertAlmostEqual(
            cv7[0], 4.0, places=3,
            msg="Invalid outCurve write must trigger framework fallback",
        )

    def test_outcurve_in_compute_locals_seed(self):
        """The framework must pre-populate ``outCurve: None`` in the
        SelfProxy's compute_locals seed. Without this, the user's
        ``self.outCurve =...`` would fall through to the plug-tree
        write path -- which crashes on the api1/api2 mismatch.
        Source-grep is sufficient (the runtime behavior is covered
        by the three tests above)."""
        import inspect
        from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve as MPxCurve
        src = inspect.getsource(MPxCurve._run_expression)
        self.assertIn(
            '"outCurve": None', src,
            "outCurve must be seeded in compute_locals so writes "
            "take SelfProxy's Tier-1 locals path, not the plug-tree "
            "write path (which is the manual-paste crash mechanism).",
        )


class TestOutputBuilderConceptRemoved(unittest.TestCase):
    """The Output Builder tab / plug / mixin / editor were
    consolidated into Compute. Lock in the deletion -- regressions
    would put the bug back."""

    def setUp(self):
        _ensure_plugins()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyNurbsCurve", name="conceptRemovedTest")
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
        self.wrapper = MPyNurbsCurve(self.node)

    def test_output_builder_source_plug_gone(self):
        self.assertFalse(
            mc.attributeQuery(
                "_outputBuilderSource", node=self.node, exists=True
            ),
            "Output Builder source plug must be removed (merged-compute)",
        )

    def test_output_builder_enabled_plug_gone(self):
        self.assertFalse(
            mc.attributeQuery(
                "_outputBuilderEnabled", node=self.node, exists=True
            ),
            "Output Builder enabled plug must be removed",
        )

    def test_wrapper_has_no_output_builder_api(self):
        for name in (
            "set_output_builder_source", "get_output_builder_source",
            "has_output_builder_source", "clear_output_builder_source",
            "set_output_builder_enabled", "is_output_builder_enabled",
            "ensure_default_sources",
        ):
            self.assertFalse(
                hasattr(self.wrapper, name),
                f"merged-compute: wrapper.{name} should be gone",
            )

    def test_output_builder_files_deleted(self):
        """The Output Builder editor + registry modules should be
        deleted -- a stale import would silently bring the concept
        back."""
        try:
            import mpynode.ui.widgets.output_builder_editor  # noqa: F401
            self.fail("output_builder_editor module should be deleted")
        except ImportError:
            pass  # expected
        try:
            import mpynode._common.output_builder_registry  # noqa: F401
            self.fail("output_builder_registry module should be deleted")
        except ImportError:
            pass  # expected


# ---------------------------------------------------------------------------
# 5. INTERNAL_API_SLOTS schema rendering.
# ---------------------------------------------------------------------------


class TestSchemaNormalizer(unittest.TestCase):
    """Schema normalizer accepts both flat-string and tuple forms.
    Unchanged by the merged-compute refactor."""

    def setUp(self):
        from mpynode.ui.widgets.plug_tree_walker import (
            _normalize_internal_api_slot_specs,
        )
        self.norm = _normalize_internal_api_slot_specs

    def test_legacy_flat_strings(self):
        self.assertEqual(
            self.norm(("a", "b")),
            [("a", "", ""), ("b", "", "")],
        )

    def test_new_extended_form(self):
        self.assertEqual(
            self.norm((("a", "read", "h1"), ("b", "write", "h2"))),
            [("a", "read", "h1"), ("b", "write", "h2")],
        )

    def test_mixed_form(self):
        self.assertEqual(
            self.norm(("a", ("b", "write", "h"))),
            [("a", "", ""), ("b", "write", "h")],
        )

    def test_partial_tuple(self):
        self.assertEqual(
            self.norm((("a", "read"),)),
            [("a", "read", "")],
        )

    def test_empty(self):
        self.assertEqual(self.norm(()), [])
        self.assertEqual(self.norm(None), [])


class TestMPyNurbsCurveExtendedSchema(unittest.TestCase):
    """MPyNurbsCurve declares the I/O contract via the extended schema."""

    def setUp(self):
        _ensure_plugins()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyNurbsCurve", name="schemaTest")

    def test_seven_slots_with_read_write(self):
        from mpynode.ui.widgets.plug_tree_walker import (
            _internal_api_slot_specs_for,
        )
        specs = _internal_api_slot_specs_for(self.node)
        self.assertEqual(len(specs), 5)
        names = [s[0] for s in specs]
        # 'rational' is seeded but inert, so it lives in
        # RESERVED_COMPUTE_LOCALS and is not a UI row.
        self.assertEqual(
            names,
            ["time", "cvs", "knots", "degree", "form"],
        )
        dirs = {s[0]: s[1] for s in specs}
        self.assertEqual(dirs["time"],   "read")
        self.assertEqual(dirs["cvs"],    "write")
        self.assertEqual(dirs["degree"], "write")

    def test_pass1_names_only_view_still_works(self):
        from mpynode.ui.widgets.plug_tree_walker import (
            _internal_api_slots_for,
        )
        slots = _internal_api_slots_for(self.node)
        self.assertEqual(
            slots,
            frozenset({"time", "cvs", "knots", "degree", "form"}),
        )

    def test_variables_internal_rows_show_direction_and_type_hint(self):
        from mpynode.ui.widgets.variables import collect_internal_api_rows
        rows = collect_internal_api_rows(self.node)
        self.assertEqual(len(rows), 5)
        # rows are (name, direction, value_text): direction is its own field
        # in the Dir column, not a "READ |"/"WRITE |" prefix on the value.
        by_name = {r[0]: r for r in rows}
        _n, time_dir, time_val = by_name["time"]
        self.assertEqual(time_dir, "read")
        self.assertIn("current frame", time_val)
        self.assertNotIn("READ", time_val)
        # read slots drop the "no wrapper property" placeholder; the value
        # column carries the type-hint schema only.
        self.assertNotIn("no wrapper property", time_val)
        _n, cvs_dir, cvs_val = by_name["cvs"]
        self.assertEqual(cvs_dir, "write")
        # write slots drop "(write-only)"; the Dir column already says WRITE.
        self.assertNotIn("(write-only)", cvs_val)
        self.assertIn("np.ndarray(N, 3)", cvs_val)
        self.assertNotIn("WRITE", cvs_val)


# ---------------------------------------------------------------------------
# 6. offset input attribute propagation (canonical user-input demo).
# ---------------------------------------------------------------------------


class TestOffsetAttrPropagates(unittest.TestCase):
    """The ``offset`` input attribute must propagate to outCurve.
    Each setAttr+pull cycle must produce mathematically-correct CV
    positions and must not crash."""

    def setUp(self):
        _ensure_plugins()
        mc.file(new=True, force=True)
        self.node = mc.createNode("mPyNurbsCurve", name="offsetTest")
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
        self.wrapper = MPyNurbsCurve(self.node)
        self.wrapper.add_input_attr("offset", "double")
        # merged-compute pattern: import in Init, write outCurve in Compute.
        self.wrapper.set_init_expression(
            "import numpy as np\n"
            "from mpynode._api2.mpy_nurbs_curve import build_default_output\n"
        )
        self.wrapper.set_compute_expression(
            "n = 8\n"
            "u = np.arange(n, dtype=np.float64) + self.offset\n"
            "self.cvs = np.stack(\n"
            "    [np.cos(u), np.zeros(n), np.sin(u)], axis=1,\n"
            ")\n"
            "self.degree = 3\n"
            "self.outCurve = build_default_output(\n"
            "    self.cvs, self.knots, self.degree, self.form,\n"
            ")\n"
        )
        self.xform, self.shape = _connect_render_shape(self.node)

    def test_offset_zero_baseline(self):
        mc.setAttr(self.node + ".offset", 0.0)
        mc.dgdirty(self.node + ".outCurve")
        cv0 = mc.pointPosition(f"{self.xform}|{self.shape}.cv[0]")
        self.assertAlmostEqual(cv0[0], 1.0, places=3)
        self.assertAlmostEqual(cv0[2], 0.0, places=3)

    def test_offset_quarter_turn(self):
        import math
        mc.setAttr(self.node + ".offset", math.pi / 2)
        mc.dgdirty(self.node + ".outCurve")
        cv0 = mc.pointPosition(f"{self.xform}|{self.shape}.cv[0]")
        self.assertAlmostEqual(cv0[0], 0.0, places=3)
        self.assertAlmostEqual(cv0[2], 1.0, places=3)

    def test_offset_half_turn_inverts(self):
        import math
        mc.setAttr(self.node + ".offset", math.pi)
        mc.dgdirty(self.node + ".outCurve")
        cv0 = mc.pointPosition(f"{self.xform}|{self.shape}.cv[0]")
        self.assertAlmostEqual(cv0[0], -1.0, places=3)
        self.assertAlmostEqual(cv0[2], 0.0, places=3)

    def test_hammer_offset_changes_dont_crash(self):
        """100 setAttr-offset / read cycles must not crash and must
        produce mathematically-correct CV positions every iteration.
        This is the post-fix regression for the original
        offset-change crash."""
        import math
        for i in range(100):
            offset = i * 0.05
            mc.setAttr(self.node + ".offset", offset)
            cv0        = mc.pointPosition(f"{self.xform}|{self.shape}.cv[0]")
            expected_x = math.cos(0.0 + offset)
            self.assertAlmostEqual(
                cv0[0], expected_x, places=3,
                msg=(
                    f"iteration {i}: offset={offset:.3f} "
                    f"expected cos={expected_x:.3f}, got cv[0].x={cv0[0]:.3f}"
                ),
            )


# ---------------------------------------------------------------------------
# 7. Thread-safety fixes from the offset-crash investigation.
# ---------------------------------------------------------------------------


class TestPhaseQCurveThreadSafety(unittest.TestCase):
    """Locks in the three thread-safety fixes from the offset-crash
    investigation. mayapy can't reproduce the Maya 2026 EM-parallel
    crash directly, but we CAN verify the code-path shape: api1
    MObject cache, data_block plumbing, cmds.* main-thread guard."""

    def test_compute_reads_time_from_datablock_not_cmds(self):
        import ast as _ast
        import inspect
        import textwrap
        from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve as MPxCurve

        compute_src  = textwrap.dedent(inspect.getsource(MPxCurve.compute))
        tree         = _ast.parse(compute_src)
        called_attrs = []
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Call):
                f = node.func
                if isinstance(f, _ast.Attribute):
                    called_attrs.append(f.attr)
        self.assertNotIn(
            "currentTime", called_attrs,
            "compute() must NOT call cmds.currentTime (worker-thread-unsafe)",
        )
        self.assertIn(
            "data_block.inputValue(MPyNurbsCurve._time_in_attr)", compute_src,
            "compute() must read time via data_block.inputValue (EM-safe)",
        )

    def test_run_expression_storage_writeback_uses_deferred_store(self):
        # tier-2: stored-var write-back goes to the thread-safe in-memory
        # store, not cmds.setAttr, so no main-thread gate is needed. The
        # store flushes to the plug on scene save/export.
        import inspect
        from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve as MPxCurve
        src = inspect.getsource(MPxCurve._run_expression)
        self.assertIn("_svstore.set_for_compute(node_obj, new_stored)", src,
            "_run_expression must write stored vars through the deferred store")
        self.assertNotIn("cmds.setAttr", src,
            "_run_expression must NOT setAttr the stored-vars plug in compute")

    def test_setDependentsDirty_caches_api1_mobject(self):
        import inspect
        from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve as MPxCurve
        self.assertTrue(
            "setDependentsDirty" in MPxCurve.__dict__,
            "MPyNurbsCurve must override setDependentsDirty for api1-cache",
        )
        src = inspect.getsource(MPxCurve.setDependentsDirty)
        self.assertIn("_api1_mobject",  src)
        self.assertIn("MSelectionList", src)
        self.assertIn("maya.OpenMaya",  src)

    def test_self_proxy_receives_data_block(self):
        """``_run_expression`` must thread data_block down to
        SelfProxy so PlugProxy uses ``data_block.inputValue(plug)``
        instead of unsafe MPlug reads."""
        import inspect
        from mpynode._api2.mpy_nurbs_curve import MPyNurbsCurve as MPxCurve
        src = inspect.getsource(MPxCurve._run_expression)
        self.assertIn(
            "datablock=data_block", src,
            "_run_expression must pass data_block to SelfProxy",
        )


# ===================== from test_phaseH_0_curve.py =====================
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseH_0_curve():
    standalone_init()
    ensure_plugins_loaded()


class _CurveBase(unittest.TestCase):

    def setUp(self):
        from maya import cmds

        cmds.file(new=True, force=True)
        self.node = cmds.createNode("mPyNurbsCurve")

    def _set_expr(self, expr):
        from maya import cmds

        cmds.setAttr(self.node + "._computeSource", expr, type="string")

    def _read_curve(self):
        """Return a dict with degree/num_cvs/first_cv read from
        ``outCurve``. Holds the plug reference internally so the
        underlying MObject stays alive until the dict is built.
        """
        import maya.api.OpenMaya as om

        sel = om.MSelectionList()
        sel.add(self.node)
        node_obj = sel.getDependNode(0)
        fn       = om.MFnDependencyNode(node_obj)
        # Stash on self so the plug + obj live until the test ends.
        self._plug     = fn.findPlug("outCurve", True)
        self._data_obj = self._plug.asMObject()
        if self._data_obj.isNull():
            return None
        try:
            mfn     = om.MFnNurbsCurve(self._data_obj)
            num_cvs = int(mfn.numCVs)
            degree  = int(mfn.degree)
            form    = int(mfn.form)
            cv0_y   = float(mfn.cvPosition(0).y) if num_cvs > 0 else 0.0
        except RuntimeError:
            # MFnNurbsCurve.numCVs raises "Object does not exist" on an empty
            # MFnNurbsCurveData (the ship-empty failure mode); report the
            # structural equivalent.
            return {"num_cvs": 0, "degree": 0, "form": 0, "cv0_y": 0.0}
        return {
            "num_cvs": num_cvs,
            "degree":  degree,
            "form":    form,
            "cv0_y":   cv0_y,
        }


class TestCurveBasicSpiral(_CurveBase):

    def test_static_spiral_has_expected_cvs(self):
        self._set_expr(
            "import numpy as np\n"
            "n = 24\n"
            "t = np.linspace(0, 4 * np.pi, n)\n"
            "x = np.cos(t)\n"
            "y = np.linspace(0, 4, n)\n"
            "z = np.sin(t)\n"
            "self.cvs = np.stack([x, y, z], axis=1)\n"
        )
        info = self._read_curve()
        self.assertIsNotNone(info, "mPyNurbsCurve must produce a non-null curve")
        self.assertEqual(info["num_cvs"], 24,
            "spiral expression must yield 24 CVs")

    def test_default_degree_is_3(self):
        self._set_expr(
            "import numpy as np\n"
            "self.cvs = np.array([\n"
            "    [0, 0, 0], [1, 1, 0], [2, 0, 0], [3, -1, 0], [4, 0, 0]\n"
            "], dtype=float)\n"
        )
        info = self._read_curve()
        self.assertIsNotNone(info)
        self.assertEqual(info["degree"], 3,
            "default curve degree must be 3")

    def test_user_specified_degree_1(self):
        self._set_expr(
            "import numpy as np\n"
            "self.cvs = np.array([\n"
            "    [0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]\n"
            "], dtype=float)\n"
            "self.degree = 1\n"
        )
        info = self._read_curve()
        self.assertIsNotNone(info)
        self.assertEqual(info["degree"], 1,
            "user-specified degree=1 must round-trip")


class TestCurveTime(_CurveBase):
    """Time is OPT-IN. A curve only re-evaluates on frame change when it
    has an incoming time connection; static curves are skipped so they
    don't pay a per-frame recompute they don't need."""

    _TIME_EXPR = (
        "import numpy as np\n"
        "t = self.time\n"
        "n = 8\n"
        "u = np.linspace(0, 1, n)\n"
        "self.cvs = np.stack([u, np.full(n, t), np.zeros(n)], axis=1)\n"
    )

    def test_frame_change_recomputes_when_time_connected(self):
        from maya import cmds

        self._set_expr(self._TIME_EXPR)
        # opt in by wiring the scene clock; the gated timeChanged callback
        # then dirties this instance.
        cmds.connectAttr("time1.outTime", self.node + "._timeIn", force=True)
        cmds.currentTime(0)
        info0 = self._read_curve()
        self.assertIsNotNone(info0)
        y0 = info0["cv0_y"]
        cmds.currentTime(10)
        info1 = self._read_curve()
        self.assertIsNotNone(info1)
        y1 = info1["cv0_y"]
        self.assertAlmostEqual(y1 - y0, 10.0, places=4,
            msg="time-connected curve must re-evaluate on frame change")

    def test_static_curve_is_skipped_on_frame_change(self):
        from maya import cmds

        # same expression with NO time connection is static: the gated
        # callback must not dirty it, so the cached plug survives the
        # frame change.
        self._set_expr(self._TIME_EXPR)
        cmds.currentTime(0)
        info0 = self._read_curve()
        self.assertIsNotNone(info0)
        y0 = info0["cv0_y"]
        cmds.currentTime(10)
        info1 = self._read_curve()
        self.assertIsNotNone(info1)
        y1 = info1["cv0_y"]
        self.assertAlmostEqual(y1, y0, places=4,
            msg="static (time-less) curve must not re-evaluate on frame change")


class TestCurveFailureMode(_CurveBase):

    def test_expression_error_yields_empty_curve(self):
        self._set_expr("raise ValueError('boom')")
        info = self._read_curve()
        # on error we ship empty MFnNurbsCurveData, so the mfn reports 0 CVs.
        if info is None:
            return
        self.assertEqual(info["num_cvs"], 0,
            "expression error must result in empty curve, not crash")


class TestCurveSourceShape(unittest.TestCase):

    def test_curve_node_module_present(self):
        from mpynode._api2 import mpy_nurbs_curve as curve_node
        self.assertTrue(hasattr(curve_node, "MPyNurbsCurve"))
        self.assertTrue(hasattr(curve_node, "register_time_change_callback"))
        self.assertEqual(curve_node.MPyNurbsCurve.NODE_NAME, "mPyNurbsCurve")

    def test_curve_uses_self_proxy_compute_locals(self):
        """The new node must follow the ``SelfProxy +
        compute_locals`` contract -- no legacy schema-based plumbing."""
        import inspect

        from mpynode._api2 import mpy_nurbs_curve as curve_node
        src = inspect.getsource(curve_node)
        self.assertIn("from mpynode._common.compute.self_proxy import SelfProxy", src)
        self.assertIn("compute_locals=", src)
        self.assertNotIn("internal_schema=", src)


# ===================== from test_phaseH_1_surface.py =====================
import unittest

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseH_1_surface():
    standalone_init()
    ensure_plugins_loaded()


class _SurfaceBase(unittest.TestCase):

    def setUp(self):
        from maya import cmds

        cmds.file(new=True, force=True)
        self.node = cmds.createNode("mPyNurbsSurface")

    def _set_expr(self, expr):
        from maya import cmds

        cmds.setAttr(self.node + "._computeSource", expr, type="string")

    def _read_surface(self):
        """Return dict with num_cvs_u/v/degree, holding plug ref."""
        import maya.api.OpenMaya as om

        sel = om.MSelectionList()
        sel.add(self.node)
        node_obj       = sel.getDependNode(0)
        fn             = om.MFnDependencyNode(node_obj)
        self._plug     = fn.findPlug("outSurface", True)
        self._data_obj = self._plug.asMObject()
        if self._data_obj.isNull():
            return None
        try:
            mfn = om.MFnNurbsSurface(self._data_obj)
            return {
                "num_cvs_u": int(mfn.numCVsInU),
                "num_cvs_v": int(mfn.numCVsInV),
                "degree_u":  int(mfn.degreeInU),
                "degree_v":  int(mfn.degreeInV),
                "cv0_y":     float(mfn.cvPosition(0, 0).y),
            }
        except RuntimeError:
            return {"num_cvs_u": 0, "num_cvs_v": 0, "degree_u": 0, "degree_v": 0, "cv0_y": 0.0}


class TestSurfaceBasic(_SurfaceBase):

    def test_grid_surface_has_expected_cvs(self):
        self._set_expr(
            "import numpy as np\n"
            "u, v = 6, 4\n"
            "xs = np.linspace(0, 1, u)\n"
            "ys = np.linspace(0, 1, v)\n"
            "cvs = np.empty((u, v, 3))\n"
            "for i in range(u):\n"
            "    for j in range(v):\n"
            "        cvs[i, j] = (xs[i], 0.0, ys[j])\n"
            "self.cvs = cvs\n"
        )
        info = self._read_surface()
        self.assertIsNotNone(info)
        self.assertEqual(info["num_cvs_u"], 6)
        self.assertEqual(info["num_cvs_v"], 4)
        self.assertEqual(info["degree_u"],  3)
        self.assertEqual(info["degree_v"],  3)

    def test_flat_cvs_with_explicit_dims(self):
        self._set_expr(
            "import numpy as np\n"
            "u, v = 5, 5\n"
            "self.num_cvs_u = u\n"
            "self.num_cvs_v = v\n"
            "self.cvs = np.zeros((u * v, 3))\n"
        )
        info = self._read_surface()
        self.assertIsNotNone(info)
        self.assertEqual(info["num_cvs_u"], 5)
        self.assertEqual(info["num_cvs_v"], 5)


class TestSurfaceTime(_SurfaceBase):

    def test_frame_change_recomputes(self):
        from maya import cmds

        # Time is opt-in: wire the scene clock so this surface re-evaluates.
        cmds.connectAttr("time1.outTime", self.node + "._timeIn", force=True)
        self._set_expr(
            "import numpy as np\n"
            "u, v = 4, 4\n"
            "t = self.time\n"
            "cvs = np.zeros((u, v, 3))\n"
            "for i in range(u):\n"
            "    for j in range(v):\n"
            "        cvs[i, j] = (i, t, j)\n"
            "self.cvs = cvs\n"
        )
        cmds.currentTime(0)
        i0 = self._read_surface()
        self.assertIsNotNone(i0)
        cmds.currentTime(7)
        i1 = self._read_surface()
        self.assertIsNotNone(i1)
        self.assertAlmostEqual(i1["cv0_y"] - i0["cv0_y"], 7.0, places=4)


class TestSurfaceFailureMode(_SurfaceBase):

    def test_expression_error_yields_empty_surface(self):
        self._set_expr("raise RuntimeError('boom')")
        info = self._read_surface()
        if info is None:
            return
        self.assertEqual(info["num_cvs_u"], 0)


class TestSurfaceSourceShape(unittest.TestCase):

    def test_surface_node_module_present(self):
        from mpynode._api2 import mpy_nurbs_surface as surface_node

        self.assertTrue(hasattr(surface_node, "MPyNurbsSurface"))
        self.assertEqual(surface_node.MPyNurbsSurface.NODE_NAME, "mPyNurbsSurface")
        self.assertTrue(hasattr(surface_node, "_build_surface_data_object"))

    def test_surface_uses_self_proxy_compute_locals(self):
        import inspect

        from mpynode._api2 import mpy_nurbs_surface as surface_node

        src = inspect.getsource(surface_node)
        self.assertIn("from mpynode._common.compute.self_proxy import SelfProxy", src)
        self.assertIn("compute_locals=", src)
        self.assertNotIn("internal_schema=", src)


# ===================== from test_phaseG_2_poly.py =====================
import inspect
import unittest

import maya.cmds as mc
import maya.OpenMaya as om
import numpy as np

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseG_2_poly():
    standalone_init()


class TestSourceCleanup(unittest.TestCase):

    def test_selfproxy_import_present(self):
        from mpynode._api2 import mpy_mesh as poly_node
        src = inspect.getsource(poly_node)
        self.assertIn(
            "from mpynode._common.compute.self_proxy import SelfProxy", src
        )

    def test_uses_compute_locals_kwarg(self):
        from mpynode._api2 import mpy_mesh as poly_node
        self.assertIn("compute_locals=", inspect.getsource(poly_node))


class TestPolyExpressionRoundTrip(unittest.TestCase):

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_triangle_round_trip(self):
        """User expression writes 3 points + 1 face -> outMesh has 3 verts."""
        n          = mc.createNode("mPyMesh")
        mesh_xform = mc.createNode("transform")
        mesh_shape = mc.createNode("mesh", parent=mesh_xform)
        mc.connectAttr(n + ".outMesh", mesh_shape + ".inMesh")
        expr = (
            "import numpy as np\n"
            "self.points = np.array("
            "[[0.0,0.0,0.0],[1.0,0.0,0.0],[0.5,1.0,0.0]],"
            " dtype=np.float64)\n"
            "self.counts = np.array([3], dtype=np.int32)\n"
            "self.indices = np.array([0,1,2], dtype=np.int32)\n"
        )
        mc.setAttr(n + "._computeSource", expr, type="string")
        nv = mc.polyEvaluate(mesh_xform, vertex=True)
        self.assertEqual(nv, 3)

    def test_time_value_visible(self):
        """``self.time`` is populated when time is connected (opt-in)."""
        n          = mc.createNode("mPyMesh")
        mesh_xform = mc.createNode("transform")
        mesh_shape = mc.createNode("mesh", parent=mesh_xform)
        mc.connectAttr(n + ".outMesh", mesh_shape + ".inMesh")
        # Time is opt-in: wire the scene clock so self.time advances and
        # the gated callback re-evaluates this mesh.
        mc.connectAttr("time1.outTime", n + "._timeIn", force=True)
        mc.currentTime(7)
        expr = (
            "import numpy as np\n"
            "y = float(self.time)\n"
            "self.points = np.array("
            "[[0.0,y,0.0],[1.0,y,0.0],[0.5,y+1.0,0.0]],"
            " dtype=np.float64)\n"
            "self.counts = np.array([3], dtype=np.int32)\n"
            "self.indices = np.array([0,1,2], dtype=np.int32)\n"
        )
        mc.setAttr(n + "._computeSource", expr, type="string")
        mc.currentTime(7)
        bbox = mc.exactWorldBoundingBox(mesh_xform)
        self.assertAlmostEqual(bbox[1], 7.0, places=4)


class TestGeometryUserOutputs(unittest.TestCase):
    """P0-7: mPyMesh / mPyNurbsCurve / mPyNurbsSurface must honor user-added
    OUTPUT attrs (compute + write them), not accept-then-ignore. Mirrors the
    write_user_outputs contract already shipped on mPyFile."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_mesh_user_output_written(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        p = MPyMesh.create(name="meshUO")
        p.add_input_attr("drv", "float")
        p.add_output_attr("outLen", "float")
        p.set_compute_expression("self.outLen = self.drv * 2.0\n")
        nm = p.get_name()
        mc.setAttr(nm + ".drv", 3.5)
        self.assertAlmostEqual(mc.getAttr(nm + ".outLen"), 7.0, places=4)

    def test_curve_user_output_written(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve

        c = MPyNurbsCurve.create(name="curveUO")
        c.add_input_attr("drv", "float")
        c.add_output_attr("outLen", "float")
        c.set_compute_expression("self.outLen = self.drv + 1.0\n")
        nm = c.get_name()
        mc.setAttr(nm + ".drv", 4.0)
        self.assertAlmostEqual(mc.getAttr(nm + ".outLen"), 5.0, places=4)

    def test_surface_user_output_written(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface

        s = MPyNurbsSurface.create(name="surfUO")
        s.add_input_attr("drv", "float")
        s.add_output_attr("outLen", "float")
        s.set_compute_expression("self.outLen = self.drv - 1.0\n")
        nm = s.get_name()
        mc.setAttr(nm + ".drv", 4.0)
        self.assertAlmostEqual(mc.getAttr(nm + ".outLen"), 3.0, places=4)


class TestGeometryVectorArrayInputDense(unittest.TestCase):
    """A vector ARRAY input read via ``self.<name>`` inside a geometry
    node's Compute expression must be a DENSE numpy ``(n, 3)`` array --
    the same contract mPyNode / mPyLocator / mPyConstraint already honor.

    Before the fix, mPyNurbsCurve / mPyMesh / mPyNurbsSurface never seeded
    user inputs into ``compute_locals``, so ``self.points`` fell through to
    the live plug proxy (``PlugListProxy``). ``np.asarray(self.points)``
    then saw a ragged sequence of ``(index, value)`` tuples and raised
    ``ValueError: setting an array element with a sequence ... inhomogeneous
    shape ... (n, 2)``.
    """

    _PTS = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
    ]

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _probe_dense(self, wrapper, input_name):
        """Add a vector-array input + numeric probe outputs, seed 6
        elements, run ``np.asarray(self.<input>)`` and report back what
        the expression saw. Returns the node name."""
        wrapper.add_input_attr(input_name, "vector", is_array=True)
        wrapper.add_output_attr("outIsNdarray", "float")
        wrapper.add_output_attr("outRows",      "float")
        wrapper.add_output_attr("outCols",      "float")
        nm = wrapper.get_name()
        for i, (x, y, z) in enumerate(self._PTS):
            mc.setAttr(f"{nm}.{input_name}[{i}]", x, y, z, type="double3")
        wrapper.set_compute_expression(
            "import numpy as np\n"
            # Record the type BEFORE asarray: the buggy path raises inside
            # asarray, aborting the expression, so outIsNdarray stays at its
            # 0.0 default. Either way the assertion below is RED before the
            # fix.
            f"self.outIsNdarray = 1.0 if isinstance(self.{input_name}, np.ndarray) else 0.0\n"
            f"points = np.asarray(self.{input_name})\n"
            "self.outRows = float(points.shape[0])\n"
            "self.outCols = float(points.shape[1] if points.ndim == 2 else -1.0)\n"
        )
        return nm

    def _assert_dense(self, nm):
        self.assertAlmostEqual(
            mc.getAttr(nm + ".outIsNdarray"), 1.0, places=4,
            msg="self.<vector-array-input> must be a numpy.ndarray",
        )
        self.assertAlmostEqual(
            mc.getAttr(nm + ".outRows"), 6.0, places=4,
            msg="dense read must expose all 6 logical elements",
        )
        self.assertAlmostEqual(
            mc.getAttr(nm + ".outCols"), 3.0, places=4,
            msg="a vector array must read as (n, 3), not ragged",
        )

    def test_curve_input_named_points_is_dense(self):
        """The literal repro: an mPyNurbsCurve with a vector-array input
        named ``points``. ``points`` is NOT a
        reserved curve build-param name, so it must seed to dense numpy."""
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve

        nm = self._probe_dense(MPyNurbsCurve.create(name="curvePoints"), "points")
        self._assert_dense(nm)

    def test_curve_vector_array_input_is_dense(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve

        nm = self._probe_dense(MPyNurbsCurve.create(name="curveArr"), "pts")
        self._assert_dense(nm)

    def test_mesh_vector_array_input_is_dense(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh

        nm = self._probe_dense(MPyMesh.create(name="meshArr"), "pts")
        self._assert_dense(nm)

    def test_surface_vector_array_input_is_dense(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface

        nm = self._probe_dense(MPyNurbsSurface.create(name="surfArr"), "pts")
        self._assert_dense(nm)


def setUpModule():
    _setUpModule__phase31_1_poly()
    _setUpModule__phaseH_0_curve()
    _setUpModule__phaseH_1_surface()
    _setUpModule__phaseG_2_poly()


if __name__ == "__main__":
    import unittest
    unittest.main()
