"""Variables-Internal panel: INTERNAL_API_SLOTS non-plug surface + live values

Consolidated from: test_pass1_variables_internal.py, test_pass2_live_internal_values.py.
"""

from __future__ import annotations

# ===================== from test_pass1_variables_internal.py =====================
import unittest

import maya.cmds as mc

from ._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


_API1_LOADED = False
_API2_LOADED = False


def _ensure_plugins__pass1_variables_internal():
    """Load both api1 + api2 plug-ins so all wrapper types are
    available. Safe to call repeatedly."""
    global _API1_LOADED, _API2_LOADED
    if not _API2_LOADED:
        if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
            mc.loadPlugin("mpynode_api2")
        _API2_LOADED = True
    if not _API1_LOADED:
        if not mc.pluginInfo("mpynode_api1", q=True, loaded=True):
            try:
                mc.loadPlugin("mpynode_api1")
            except Exception:
                pass
        _API1_LOADED = True


class TestAttributesAndInternalAreDisjoint(unittest.TestCase):
    """Invariant 1: Attributes-tab plug names and Variables-Internal
    slot names must not overlap."""

    def setUp(self):
        _ensure_plugins__pass1_variables_internal()
        mc.file(new=True, force=True)

    @staticmethod
    def _attribute_names(node_name):
        """Names that the Attributes tab would surface. Mirrors the
        Attributes-tab's data source: ``walk_plug_tree`` filtered to
        INPUT or OUTPUT direction (the Attributes tab buckets plugs
        by direction; INTERNAL-direction rows are the wrapper-class
        ``INTERNAL_API_SLOTS`` which the Attributes tab DOESN'T
        surface)."""
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree
        names = set()
        for row in walk_plug_tree(node_name):
            if row.direction not in ("INPUT", "OUTPUT"):
                continue
            # short_name (no compound prefix or array index) is the space
            # INTERNAL_API_SLOTS names live in.
            if row.short_name:
                names.add(row.short_name)
        return names

    @staticmethod
    def _internal_names(node_name):
        """Names that Variables-Internal surfaces (non-plug API slots
        from the wrapper's INTERNAL_API_SLOTS declaration)."""
        from mpynode.ui.widgets.variables import collect_internal_api_rows
        return set(r[0] for r in collect_internal_api_rows(node_name))

    def _assert_disjoint(self, node_name, label):
        attrs = self._attribute_names(node_name)
        internal = self._internal_names(node_name)
        overlap = attrs & internal
        self.assertEqual(
            overlap, set(),
            f"{label}: Attributes and Variables-Internal share {overlap!r} "
            f"-- invariant violated (Variables-Internal must be "
            f"non-plug API slots only)."
        )

    def test_mPyNode_disjoint(self):
        node = mc.createNode("mPyNode")
        self._assert_disjoint(node, "mPyNode")

    def test_mPyConstraint_disjoint(self):
        node = mc.createNode("mPyConstraint")
        self._assert_disjoint(node, "mPyConstraint")

    def test_mPyMesh_disjoint(self):
        node = mc.createNode("mPyMesh")
        self._assert_disjoint(node, "mPyMesh")

    def test_mPyNurbsCurve_disjoint(self):
        node = mc.createNode("mPyNurbsCurve")
        self._assert_disjoint(node, "mPyNurbsCurve")

    def test_mPyFile_disjoint(self):
        # mPyFile motivated this audit: its 16+ preset inputs in Attributes
        # used to appear duplicated in Variables-Internal.
        node = mc.shadingNode("mPyFile", asTexture=True, name="diffuseTexTest")
        self._assert_disjoint(node, "mPyFile")


class TestMPyFileVariablesInternalSurfacesBridgeHandles(unittest.TestCase):
    """Invariant 4: mPyFile's Viewport/Viewport tab injects non-plug
    bridge handles (self.shader etc.) which MUST be discoverable in
    Variables-Internal -- no black box. Invariant 3: a GENUINELY
    plug-only node (mPyNode) stays empty."""

    def setUp(self):
        _ensure_plugins__pass1_variables_internal()
        mc.file(new=True, force=True)

    def test_mPyFile(self):
        node = mc.shadingNode("mPyFile", asTexture=True, name="diffuseTexTest")
        from mpynode.ui.widgets.variables import collect_internal_api_rows
        rows = collect_internal_api_rows(node)
        names = set(r[0] for r in rows)
        # The Viewport exec namespace binds these non-plug handles onto
        # self.<x>, so Variables-Internal is the ONLY place to surface them.
        expected = {"time", "shader", "texture_manager", "state_manager",
                    "mappings"}
        self.assertTrue(
            expected.issubset(names),
            "mPyFile must surface its non-plug bridge handles "
            f"{expected!r} in Variables-Internal (no black box); got {names!r}."
        )

    def test_mPyNode(self):
        node = mc.createNode("mPyNode")
        from mpynode.ui.widgets.variables import collect_internal_api_rows
        rows = collect_internal_api_rows(node)
        self.assertEqual(
            rows, [],
            "mPyNode has no INTERNAL_API_SLOTS declaration -- "
            "Variables-Internal should be empty."
        )


class TestMPyIkSolverDeclaresInternalApiSlots(unittest.TestCase):
    """Invariant 2: mPyIkSolver -- the canonical motivating case --
    must declare its non-plug API state via INTERNAL_API_SLOTS."""

    def test_class_attr(self):
        # Read directly from the wrapper class so this test doesn't
        # need the api1 plug-in loaded or a real IK chain in the scene.
        try:
            from mpynode.wrappers.mpy_iksolver import MPyIkSolver
        except ImportError:
            self.skipTest("mpynode.wrappers.mpy_iksolver not importable in this build")
        # ``INTERNAL_API_SLOTS`` accepts plain strings or ``(name, dir, hint)``
        # tuples; normalize to names before comparing.
        raw = getattr(MPyIkSolver, "INTERNAL_API_SLOTS", ())
        slots = set()
        for entry in raw:
            if isinstance(entry, str):
                slots.add(entry)
            elif isinstance(entry, tuple) and entry:
                slots.add(entry[0])
        # Canonical IK input set the wrapper marshals into the user namespace;
        # output-buffer slots may be added later.
        required = {"joints", "end_effector", "pole_vector", "twist"}
        self.assertTrue(
            required.issubset(slots),
            f"mPyIkSolver.INTERNAL_API_SLOTS must include the IK inputs "
            f"{required!r}; got {slots!r}."
        )


# ===================== from test_pass2_live_internal_values.py =====================
import unittest

import maya.cmds as mc


_API2_LOADED = False


def _ensure_plugins__pass2_live_internal_values():
    global _API2_LOADED
    if not _API2_LOADED:
        if not mc.pluginInfo("mpynode_api2", q=True, loaded=True):
            mc.loadPlugin("mpynode_api2")
        _API2_LOADED = True


# ---------------------------------------------------------------------------
# Invariant 2: _format_slot_value rendering
# ---------------------------------------------------------------------------


class TestFormatSlotValue(unittest.TestCase):
    def setUp(self):
        from mpynode.ui.widgets.variables import _format_slot_value
        self.fmt = _format_slot_value

    def test_none(self):
        self.assertEqual(self.fmt(None), "None")

    def test_numpy_array_shape_only(self):
        import numpy as np
        arr = np.zeros((48, 3), dtype=np.float64)
        out = self.fmt(arr)
        # Shape + dtype only -- NO element dump (a 48x3 array would
        # blow out the tree-row column).
        self.assertIn("ndarray", out)
        self.assertIn("(48, 3)", out)
        self.assertIn("float64", out)
        self.assertNotIn(
            "0.0", out,
            "numpy element values should not appear -- shape/dtype only",
        )

    def test_numpy_array_empty(self):
        import numpy as np
        arr = np.array([], dtype=np.int32)
        out = self.fmt(arr)
        self.assertIn("ndarray", out)
        self.assertIn("int32", out)

    def test_list_short(self):
        out = self.fmt([1, 2, 3])
        self.assertTrue(out.startswith("list[3]:"), f"got {out!r}")
        self.assertNotIn("...", out)

    def test_list_long_truncated(self):
        out = self.fmt(list(range(50)))
        self.assertTrue(out.startswith("list[50]:"), f"got {out!r}")
        self.assertIn(",...", out)

    def test_tuple(self):
        out = self.fmt(("a", "b"))
        self.assertTrue(out.startswith("tuple[2]:"), f"got {out!r}")

    def test_empty_list(self):
        self.assertEqual(self.fmt([]), "list[0]")

    def test_long_string_truncated(self):
        s = "x" * 200
        out = self.fmt(s)
        self.assertLessEqual(len(out), 80)
        self.assertTrue(out.endswith("..."))

    def test_short_string(self):
        out = self.fmt("hello")
        self.assertEqual(out, "'hello'")

    def test_mmatrix_compact(self):
        import maya.api.OpenMaya as om
        m = om.MMatrix()
        out = self.fmt(m)
        self.assertTrue(out.startswith("MMatrix("), f"got {out!r}")
        # Identity matrix's first row starts with 1.
        self.assertIn("1", out)

    def test_mvector_compact(self):
        import maya.api.OpenMaya as om
        v = om.MVector(1.0, 2.0, 3.0)
        out = self.fmt(v)
        self.assertEqual(out, "MVector(1, 2, 3)")


# ---------------------------------------------------------------------------
# Invariant 1: collect_internal_api_rows reads live values
# ---------------------------------------------------------------------------


class TestCollectInternalApiRowsLiveValues(unittest.TestCase):
    """Live-value upgrade -- placeholder ``<api>`` is gone; rows now
    carry the actual ``repr`` (or formatted summary) of the wrapper's
    slot value."""

    def setUp(self):
        _ensure_plugins__pass2_live_internal_values()
        mc.file(new=True, force=True)

    def test_no_api_placeholder_for_any_slot(self):
        """Regression: the legacy placeholder ``"<api>"`` must not
        leak into any row for any wrapper. Values may be diagnostics
        (``<error:...>`` / ``<wrapper unavailable>``) but NEVER the
        stale literal ``<api>``."""
        from mpynode.ui.widgets.variables import collect_internal_api_rows

        for node_type in ("mPyNode", "mPyFile", "mPyLocator"):
            try:
                if node_type == "mPyFile":
                    node = mc.shadingNode(node_type, asTexture=True)
                else:
                    node = mc.createNode(node_type)
            except Exception:
                continue
            rows = collect_internal_api_rows(node)
            for slot, _dir, val in rows:
                self.assertNotEqual(
                    val, "<api>",
                    f"{node_type}.{slot}: live-value rendering must replace the "
                    f"<api> placeholder with a live value",
                )

    def test_empty_for_plug_only_node(self):
        """A GENUINELY plug-only node (mPyNode -- no INTERNAL_API_SLOTS)
        yields an empty rows list (placeholder rendering is the
        Variables widget's job, not the collector's)."""
        from mpynode.ui.widgets.variables import collect_internal_api_rows

        node = mc.createNode("mPyNode")
        self.assertEqual(collect_internal_api_rows(node), [])

    def test_mpyfile_surfaces_bridge_handles(self):
        """mPyFile is NOT plug-only: its Viewport/Viewport tab injects
        non-plug bridge handles (shader / time / mappings /
        texture_manager / state_manager). They have no live value
        outside a render tick (the wrapper has no matching property), so
        they surface as diagnostic rows -- but they MUST surface (no
        black box), never an empty list."""
        from mpynode.ui.widgets.variables import collect_internal_api_rows

        node = mc.shadingNode("mPyFile", asTexture=True)
        names = {r[0] for r in collect_internal_api_rows(node)}
        self.assertTrue(
            {"shader", "time", "mappings", "texture_manager",
             "state_manager"}.issubset(names),
            f"mPyFile must surface its bridge handles; got {names!r}",
        )

    def test_diagnostic_on_missing_property(self):
        """If a wrapper declares a slot in ``INTERNAL_API_SLOTS`` but
        doesn't expose a matching attribute, the row surfaces its type-hint
        schema (or an empty value cell) rather than raising into the caller
        -- the getattr-AttributeError is the expected I/O contract, not an
        error, so no ``<error:...>`` / ``(write-only)`` / ``no wrapper
        property`` tag is emitted (direction lives in the 'Dir' column).

        mPyLocator is currently in this state: it declares
        ``selected``, ``is_lead``, ``selection_color`` slots but
        the wrapper class has no matching properties. The live-value path's
        contract is that this surfaces cleanly, not as a crash."""
        from mpynode.ui.widgets.variables import collect_internal_api_rows

        node = mc.createNode("mPyLocator")
        rows = collect_internal_api_rows(node)
        if not rows:
            self.skipTest("mPyLocator INTERNAL_API_SLOTS not declared")
        for slot, _dir, val in rows:
            # type-hint schema OR empty -- but the call must not have
            # thrown an exception into the caller.
            self.assertIsInstance(
                val, str,
                f"{slot}: value must be a string, got {type(val).__name__}",
            )


# ---------------------------------------------------------------------------
# Invariant 3: _wrapper_instance_for plumbing
# ---------------------------------------------------------------------------


class TestWrapperInstanceFor(unittest.TestCase):
    """Will rely on the wrapper-instance constructor to read
    slot values from inside compute helpers, demos, etc. The live-value path just
    verifies the plumbing returns a usable instance for every
    api2-registered type."""

    def setUp(self):
        _ensure_plugins__pass2_live_internal_values()
        mc.file(new=True, force=True)

    def test_returns_instance_for_known_type(self):
        from mpynode.ui.widgets.plug_tree_walker import _wrapper_instance_for

        node = mc.createNode("mPyNode")
        wrapper = _wrapper_instance_for(node)
        self.assertIsNotNone(
            wrapper, "_wrapper_instance_for(mPyNode) must return a wrapper")
        self.assertEqual(
            wrapper.get_name(), node,
            "wrapper should wrap the same Maya node")

    def test_returns_none_for_unknown_type(self):
        from mpynode.ui.widgets.plug_tree_walker import _wrapper_instance_for

        # A vanilla Maya node type with no mpynode wrapper.
        node = mc.createNode("transform")
        self.assertIsNone(
            _wrapper_instance_for(node),
            "_wrapper_instance_for(transform) must return None")

    def test_returns_none_for_nonexistent_node(self):
        from mpynode.ui.widgets.plug_tree_walker import _wrapper_instance_for
        self.assertIsNone(_wrapper_instance_for("definitely_not_a_node"))


# ---------------------------------------------------------------------------
# Invariant 4: dead-code cleanup
# ---------------------------------------------------------------------------


class TestDeadCodeRemoved(unittest.TestCase):
    def test_use_plug_tree_render_attr_gone(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget
        self.assertFalse(hasattr(NDVariablesWidget, "_USE_PLUG_TREE_RENDER"))

    def test_collect_plug_tree_method_gone(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget
        self.assertFalse(hasattr(NDVariablesWidget, "_collect_plug_tree"))

    def test_add_plug_tree_node_method_gone(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget
        self.assertFalse(hasattr(NDVariablesWidget, "_add_plug_tree_node"))

    def test_collect_plug_rows_method_gone(self):
        from mpynode.ui.widgets.variables import NDVariablesWidget
        self.assertFalse(hasattr(NDVariablesWidget, "_collect_plug_rows"))


# ---------------------------------------------------------------------------
# Invariant 5: helper relocation + back-compat
# ---------------------------------------------------------------------------


class TestHelperRelocation(unittest.TestCase):
    def test_canonical_path_is_plug_tree_walker(self):
        """``collect_plug_rows`` / ``collect_plug_tree`` /
        ``read_plug_value_text`` / ``PLUG_BROWSER_BLACKLIST`` now
        canonically live in plug_tree_walker -- the module that
        actually walks the plug tree."""
        from mpynode.ui.widgets import plug_tree_walker
        for name in (
            "collect_plug_rows", "collect_plug_tree",
            "read_plug_value_text", "PLUG_BROWSER_BLACKLIST",
        ):
            self.assertTrue(
                hasattr(plug_tree_walker, name),
                f"{name} should be defined in plug_tree_walker",
            )

    def test_back_compat_reexport_from_variables(self):
        """Existing call sites import these names from
        ``ui.widgets.variables``. The re-export must point at the
        SAME object (not a copy) so identity comparisons hold."""
        from mpynode.ui.widgets import variables, plug_tree_walker
        for name in (
            "collect_plug_rows", "collect_plug_tree",
            "read_plug_value_text", "PLUG_BROWSER_BLACKLIST",
        ):
            self.assertIs(
                getattr(variables, name),
                getattr(plug_tree_walker, name),
                f"{name}: re-export must be same object",
            )


# ---------------------------------------------------------------------------
# Invariant 6: the Variables-Internal "Dir" column reflects each slot's
# real read/write direction (was a static "API" label).
# ---------------------------------------------------------------------------


class TestDirColumnLabel(unittest.TestCase):
    """The 'Dir' column shows READ / WRITE per slot (from INTERNAL_API_SLOTS'
    direction). Legacy slots that declare no direction fall back to 'API'.
    The direction is a SEPARATE tuple field, no longer a prefix baked into
    the value text."""

    def setUp(self):
        _ensure_plugins__pass1_variables_internal()
        mc.file(new=True, force=True)

    def test_dir_label_mapping(self):
        # Ask 1: the Dir column shows the direction as a plain word
        # (READ / WRITE / READWRITE / METHOD).
        from mpynode.ui.widgets.variables import _dir_label
        self.assertEqual(_dir_label("read"), "READ")
        self.assertEqual(_dir_label("write"), "WRITE")
        self.assertEqual(_dir_label("readwrite"), "READWRITE")
        # Legacy flat-string slots (no declared direction) -> neutral blank.
        self.assertEqual(_dir_label(""), "")
        self.assertEqual(_dir_label(None), "")

    def test_transform_rows_carry_direction_not_in_value(self):
        node = mc.createNode("mPyTransform")
        from mpynode.ui.widgets.variables import collect_internal_api_rows
        rows = collect_internal_api_rows(node)
        by_name = {r[0]: r for r in rows}
        self.assertIn("local_matrix", by_name)
        # 3-tuple: (name, direction, value_text)
        _n, direction, value_text = by_name["local_matrix"]
        self.assertEqual(direction, "write")
        # direction is NOT duplicated as a prefix inside the value text.
        self.assertNotIn("WRITE |", value_text)
        self.assertNotIn("READ |", value_text)
        # the redundant "(write-only)" placeholder is gone -- the Dir column
        # already conveys WRITE; only the type-hint schema remains.
        self.assertNotIn("(write-only)", value_text)


class TestSectionHeaderLabels(unittest.TestCase):
    """Ask 1: the non-plug API-state section is labelled 'Properties'
    (Internal -> API -> Properties); the Dir column carries R / W / RW / M
    badges instead of the READ/WRITE words."""

    def test_internal_section_labelled_properties(self):
        from mpynode.ui.widgets.variables import SECTION_INTERNAL
        self.assertEqual(SECTION_INTERNAL, "Properties")


class TestValueTooltip(unittest.TestCase):
    """Long API value/description text overflows the Value column and
    truncates; a word-wrapped rich-text tooltip surfaces the full content on
    hover (Qt-free unit test of the wrap/escape helper)."""

    def test_wrap_tooltip_empty(self):
        from mpynode.ui.widgets.variables import _wrap_tooltip
        self.assertEqual(_wrap_tooltip(""), "")
        self.assertEqual(_wrap_tooltip(None), "")

    def test_wrap_tooltip_is_rich_text(self):
        from mpynode.ui.widgets.variables import _wrap_tooltip
        out = _wrap_tooltip("desired LOCAL matrix via offsetParentMatrix")
        # rich text so Qt word-wraps long single-line descriptions
        self.assertTrue(out.startswith("<qt>"))
        self.assertTrue(out.endswith("</qt>"))
        self.assertIn("offsetParentMatrix", out)

    def test_wrap_tooltip_escapes_html_metachars(self):
        from mpynode.ui.widgets.variables import _wrap_tooltip
        out = _wrap_tooltip("world @ inv(parent) <connected> & more")
        # '<connected>' must NOT survive as a literal tag (Qt would eat it)
        self.assertIn("&lt;connected&gt;", out)
        self.assertNotIn("<connected>", out)
        self.assertIn("&amp;", out)


if __name__ == "__main__":
    import unittest
    unittest.main()
