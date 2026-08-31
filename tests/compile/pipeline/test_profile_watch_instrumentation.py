"""Profile + Watch instrumentation: scrub lifecycle, toggles-hidden, getter API, profile-widget units

Consolidated from: test_phase30_2.py, test_framework_toggles_hidden.py, test_phase29_1.py, test_phase29_3.py.
"""

from __future__ import annotations

# ===================== from test_phase30_2.py =====================
import inspect
import unittest

from tests._setup import standalone_init


def _setUpModule__phase30_2():
    standalone_init()


# ===========================================================================
# 1. scrub helper round-trip on real mPy nodes
# ===========================================================================


class TestDisableAllInstrumentationTogglesInScene(unittest.TestCase):
    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def test_helper_exists_and_is_callable(self):
        from mpynode._common import instrumentation

        self.assertTrue(
            hasattr(instrumentation, "disable_all_instrumentation_toggles_in_scene")
        )
        self.assertTrue(
            callable(instrumentation.disable_all_instrumentation_toggles_in_scene)
        )

    def test_scrub_disables_all_three_toggles(self):
        """Build 2 mPyNodes, turn on all three toggles on each, call
        the helper, verify every toggle is False."""
        import maya.cmds as mc
        from mpynode._common.instrumentation import (
            DEEP_PROFILE_ENABLED_ATTR_NAME,
            disable_all_instrumentation_toggles_in_scene,
            PROFILE_ENABLED_ATTR_NAME,
            WATCH_ENABLED_ATTR_NAME,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        nodes = []
        for i in range(2):
            n = MPyNode.create(name=f"scrubTest{i}")
            nodes.append(n.get_name())
            for attr in (
                PROFILE_ENABLED_ATTR_NAME,
                DEEP_PROFILE_ENABLED_ATTR_NAME,
                WATCH_ENABLED_ATTR_NAME,
            ):
                mc.setAttr(f"{n.get_name()}.{attr}", True)

        touched = disable_all_instrumentation_toggles_in_scene()
        # 2 nodes * 3 toggles = 6 attrs touched.
        self.assertEqual(touched, 6)

        for node in nodes:
            for attr in (
                PROFILE_ENABLED_ATTR_NAME,
                DEEP_PROFILE_ENABLED_ATTR_NAME,
                WATCH_ENABLED_ATTR_NAME,
            ):
                self.assertFalse(
                    mc.getAttr(f"{node}.{attr}"),
                    f"{node}.{attr} should be False after scrub",
                )

    def test_scrub_skips_already_off_attrs(self):
        """Helper only counts ATTRS THAT WERE ACTUALLY CHANGED -- if
        a toggle was already False, no setAttr call is issued, so
        the return count reflects only the work done."""
        import maya.cmds as mc
        from mpynode._common.instrumentation import (
            disable_all_instrumentation_toggles_in_scene,
            PROFILE_ENABLED_ATTR_NAME,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        # 1 node, all toggles default False.
        node = MPyNode.create(name="scrubAlreadyOff")
        # Enable just one of the three.
        mc.setAttr(f"{node.get_name()}.{PROFILE_ENABLED_ATTR_NAME}", True)
        touched = disable_all_instrumentation_toggles_in_scene()
        self.assertEqual(touched, 1)

    def test_scrub_covers_mpylocator_and_subclasses(self):
        """The helper should walk all mPy* native types, not just
        mPyNode. Test with mPyLocator (the subclass that
        was the user's primary use case)."""
        import maya.cmds as mc
        from mpynode._common.instrumentation import (
            disable_all_instrumentation_toggles_in_scene,
            PROFILE_ENABLED_ATTR_NAME,
        )
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="scrubLocator")
        mc.setAttr(f"{loc.get_name()}.{PROFILE_ENABLED_ATTR_NAME}", True)
        touched = disable_all_instrumentation_toggles_in_scene()
        self.assertEqual(touched, 1)
        self.assertFalse(mc.getAttr(f"{loc.get_name()}.{PROFILE_ENABLED_ATTR_NAME}"))


# ===========================================================================
# 2. Designer closeEvent calls the scrub (source-pin)
# ===========================================================================


class TestDesignerCloseEventScrubsToggles(unittest.TestCase):
    def test_closeEvent_calls_scrub_helper(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.closeEvent)
        self.assertIn(
            "disable_all_instrumentation_toggles_in_scene",
            src,
            "closeEvent must call the scrub helper to zero out "
            "background instrumentation work before tearing down",
        )

    def test_closeEvent_scrub_is_inside_try_except(self):
        """Never let a scrub error block Designer close."""
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.closeEvent)
        # Strip line-comments before checking.
        code = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
        self.assertIn("try:", code)
        self.assertIn("except", code)


# ===========================================================================
# 3. Designer wires tabSaved -> _on_tab_saved (source-pin)
# ===========================================================================


class TestDesignerWiresTabSavedSignal(unittest.TestCase):
    def test_signal_is_connected(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow)
        self.assertIn(
            "self._script_tab_widget.tabSaved.connect",
            src,
            "Designer must subscribe to NDScriptTabWidget.tabSaved "
            "so Profile + Watch widgets refresh after Save (F5)",
        )
        self.assertIn("_on_tab_saved", src)

    def test_on_tab_saved_handler_exists(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "_on_tab_saved"))
        self.assertTrue(callable(NDMainWindow._on_tab_saved))

    def test_on_tab_saved_refreshes_both_widgets(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._on_tab_saved)
        self.assertIn("self._profile_widget.refresh()", src)
        self.assertIn("self._watch_widget.refresh()", src)

    def test_on_tab_saved_guards_against_node_mismatch(self):
        """The handler must only refresh widgets bound to the SAME
        node as the one whose save triggered the signal -- otherwise
        a save of node A would clobber Profile/Watch state for node B."""
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._on_tab_saved)
        self.assertIn(".get_name() == py_node.get_name()", src)


# ===================== from test_framework_toggles_hidden.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__framework_toggles_hidden():
    standalone_init()


TOGGLE_ATTRS = (
    "debug_mode",
    "profile_enabled",
    "deep_profile_enabled",
    "watch_enabled",
)


class TestFrameworkTogglesHidden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)

    def _assert_attr_hidden(self, node_name, attr):
        """Three invariants per toggle."""
        full = "{}.{}".format(node_name, attr)
        # 1. The attr exists at all (sanity).
        self.assertTrue(
            mc.attributeQuery(attr, node=node_name, exists=True),
            "{} should expose {!r}".format(node_name, attr),
        )
        # 2. Not in the channel box (visible).
        self.assertFalse(
            mc.getAttr(full, channelBox=True),
            "{} should NOT be in the channel box".format(full),
        )
        # 3. Not keyable.
        self.assertFalse(
            mc.getAttr(full, keyable=True),
            "{} should NOT be keyable".format(full),
        )
        # 4. Hidden from the AE.
        self.assertTrue(
            mc.attributeQuery(attr, node=node_name, hidden=True),
            "{} should be hidden from the Attribute Editor".format(full),
        )

    # One test per node type so the failure message points at the offending
    # wrapper. Each is independent + cheap (a single ``create()`` call).

    def test_mPyNode_toggles_hidden(self):
        from mpynode.wrappers._mpy_node import MPyNode
        n = MPyNode.create(name="tog_test_node")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyLocator_toggles_hidden(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        n = MPyLocator.create(name="tog_test_loc")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyConstraint_toggles_hidden(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint
        n = MPyConstraint.create(name="tog_test_con")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyFile_toggles_hidden(self):
        from mpynode.wrappers.mpy_file import MPyFile
        n = MPyFile.create(name="tog_test_file")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyMesh_toggles_hidden(self):
        from mpynode.wrappers.mpy_mesh import MPyMesh
        n = MPyMesh.create(name="tog_test_poly")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyNurbsCurve_toggles_hidden(self):
        from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve
        n = MPyNurbsCurve.create(name="tog_test_curve")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyNurbsSurface_toggles_hidden(self):
        from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface
        n = MPyNurbsSurface.create(name="tog_test_surf")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyIkSolver_toggles_hidden(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver
        n = MPyIkSolver.create(name="tog_test_iks")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyDeformer_toggles_hidden(self):
        import maya.cmds as mc_
        plane = mc_.polyPlane(w=2, h=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer
        n = MPyDeformer.create_on(plane, name="tog_test_def")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyTransform_toggles_hidden(self):
        from mpynode.wrappers.mpy_transform import MPyTransform
        n = MPyTransform.create(name="tog_test_xfm")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyDeformer_nurbs_toggles_hidden(self):
        import maya.cmds as mc_
        nurbs = mc_.nurbsPlane(w=2, lr=1)[0]
        # mc.deformer is Maya's standard deformer-attach path; the
        # wrapper exposes the resulting node via the framework name.
        node_name = mc_.deformer(
            nurbs, type="mPyDeformer", name="tog_test_df_nurbs"
        )[0]
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(node_name, a)

    def test_mPySkinCluster_toggles_hidden(self):
        import maya.cmds as mc_
        sphere = mc_.polySphere(r=1)[0]
        joint = mc_.joint(p=(0, 0, 0))
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        n = MPySkinCluster.create(mesh=sphere, joints=[joint], name="tog_test_skin")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)

    def test_mPyBlendShape_toggles_hidden(self):
        import maya.cmds as mc_
        base = mc_.polySphere(r=1)[0]
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape
        n = MPyBlendShape.create(mesh=base, name="tog_test_bs")
        for a in TOGGLE_ATTRS:
            self._assert_attr_hidden(n.get_name(), a)


# ===================== from test_phase29_1.py =====================
import unittest

from tests._setup import standalone_init


def _setUpModule__phase29_1():
    standalone_init()


# ===========================================================================
# 1. Base wrapper shape
# ===========================================================================


class TestProfileWatchApiBase(unittest.TestCase):
    def test_mpynode_exposes_profile_watch_api(self):
        from mpynode.wrappers._mpy_node import MPyNode

        for method in (
            "is_profile_enabled",
            "is_deep_profile_enabled",
            "is_watch_enabled",
            "get_profile_snapshot",
            "get_watch_vars",
        ):
            self.assertTrue(
                hasattr(MPyNode, method),
                f"MPyNode missing {method!r}",
            )

    def test_base_module_is_qt_free(self):
        """The base wrapper sits on the producer side -- must not pull Qt."""
        import inspect

        from mpynode.wrappers import _mpy_node as node
        src = inspect.getsource(node)
        self.assertNotIn("PySide", src)
        self.assertNotIn("qt_wrapper", src)


# ===========================================================================
# 2. Every specialty wrapper has the API
# ===========================================================================


class TestAllWrappersHaveProfileWatchApi(unittest.TestCase):
    """Pre-Phase-29.1, only MPyNode had these methods. The Profile +
    Watch widgets fell back to '(not supported for this node type)'
    for any other wrapper. Verify all 7 wrapper types now expose it."""

    def _check_methods(self, cls):
        for method in (
            "is_profile_enabled",
            "is_deep_profile_enabled",
            "is_watch_enabled",
            "get_profile_snapshot",
            "get_watch_vars",
        ):
            self.assertTrue(
                hasattr(cls, method),
                f"{cls.__name__} should expose {method!r}",
            )

    def test_iksolver_has_profile_watch_api(self):
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        self._check_methods(MPyIkSolver)

    def test_locator_has_profile_watch_api(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        self._check_methods(MPyLocator)

    def test_deformer_has_profile_watch_api(self):
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self._check_methods(MPyDeformer)

    def test_constraint_inherits_via_mpynode(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        self._check_methods(MPyConstraint)

    def test_mpynode_still_works(self):
        from mpynode.wrappers._mpy_node import MPyNode

        self._check_methods(MPyNode)


# ===========================================================================
# 3. Round-trip on a real Maya node
# ===========================================================================


class TestProfileWatchRoundTrip(unittest.TestCase):
    """Toggle the plug via mc.setAttr (same path the Profile + Watch
    widgets use) and verify the wrapper reads it back. Confirms the
    mixin's transient-MPyNode delegation works end-to-end on a
    specialty wrapper class."""

    def setUp(self):
        import maya.cmds as mc

        mc.file(new=True, force=True)

    def test_locator_round_trip_is_profile_enabled(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="profileGizmo")
        # Default plug value = False.
        self.assertFalse(loc.is_profile_enabled())
        # Toggle via setAttr (matches widget's path).
        mc.setAttr(loc.get_name() + ".profile_enabled", True)
        self.assertTrue(loc.is_profile_enabled())

    def test_locator_round_trip_is_watch_enabled(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="watchGizmo")
        self.assertFalse(loc.is_watch_enabled())
        mc.setAttr(loc.get_name() + ".watch_enabled", True)
        self.assertTrue(loc.is_watch_enabled())

    def test_iksolver_round_trip_is_deep_profile_enabled(self):
        import maya.cmds as mc
        from mpynode.wrappers.mpy_iksolver import MPyIkSolver

        # Need a real IK solver to test against. Use the standard
        # creator that constructs an mPyIkSolver dep node.
        solver = MPyIkSolver.find_solver()
        self.assertFalse(solver.is_deep_profile_enabled())
        mc.setAttr(solver.get_name() + ".deep_profile_enabled", True)
        self.assertTrue(solver.is_deep_profile_enabled())

    def test_locator_get_profile_snapshot_returns_none_before_eval(self):
        """Fresh locator with no compute history returns None (or {}).
        Verifies the snapshot reader path doesn't crash."""
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="snapshotGizmo")
        snap = loc.get_profile_snapshot()
        # Either None or empty dict is fine; the contract is no crash.
        self.assertTrue(snap is None or isinstance(snap, dict))

    def test_locator_get_watch_vars_returns_none_before_eval(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="watchVarsGizmo")
        watch = loc.get_watch_vars()
        self.assertTrue(watch is None or isinstance(watch, dict))


# ===================== from test_phase29_3.py =====================
import inspect
import unittest

from tests._setup import standalone_init


def _setUpModule__phase29_3():
    standalone_init()


# ===========================================================================
# 1. Module-level table
# ===========================================================================


class TestUnitsTable(unittest.TestCase):
    def test_four_units_defined(self):
        from mpynode.ui.widgets.profile import _TIME_UNITS

        labels = [u[0] for u in _TIME_UNITS]
        self.assertEqual(labels, ["ns", "\u00b5s", "ms", "s"])

    def test_unit_map_includes_each_unit(self):
        from mpynode.ui.widgets.profile import _TIME_UNIT_MAP, _TIME_UNITS

        for label, mult, prec in _TIME_UNITS:
            self.assertIn(label, _TIME_UNIT_MAP)
            self.assertEqual(_TIME_UNIT_MAP[label], (mult, prec))

    def test_default_unit_is_microseconds(self):
        from mpynode.ui.widgets.profile import _DEFAULT_UNIT

        self.assertEqual(_DEFAULT_UNIT, "\u00b5s")


# ===========================================================================
# 2. Conversion math
# ===========================================================================


class TestConvert(unittest.TestCase):
    def test_us_to_ms(self):
        from mpynode.ui.widgets.profile import _convert, _SNAP_BASE_TO_SECONDS

        # 1500 us = 1.5 ms
        result = _convert(1500.0, _SNAP_BASE_TO_SECONDS, "ms")
        self.assertAlmostEqual(result, 1.5, places=5)

    def test_us_to_s(self):
        from mpynode.ui.widgets.profile import _convert, _SNAP_BASE_TO_SECONDS

        # 1,000,000 us = 1 s
        result = _convert(1_000_000.0, _SNAP_BASE_TO_SECONDS, "s")
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_us_to_us(self):
        from mpynode.ui.widgets.profile import _convert, _SNAP_BASE_TO_SECONDS

        result = _convert(42.0, _SNAP_BASE_TO_SECONDS, "\u00b5s")
        self.assertAlmostEqual(result, 42.0, places=5)

    def test_us_to_ns(self):
        from mpynode.ui.widgets.profile import _convert, _SNAP_BASE_TO_SECONDS

        # 1 us = 1000 ns
        result = _convert(1.0, _SNAP_BASE_TO_SECONDS, "ns")
        self.assertAlmostEqual(result, 1000.0, places=5)

    def test_ms_to_s(self):
        from mpynode.ui.widgets.profile import _convert, _DEEP_BASE_TO_SECONDS

        # 2500 ms = 2.5 s
        result = _convert(2500.0, _DEEP_BASE_TO_SECONDS, "s")
        self.assertAlmostEqual(result, 2.5, places=5)

    def test_ms_to_ns(self):
        from mpynode.ui.widgets.profile import _convert, _DEEP_BASE_TO_SECONDS

        # 1 ms = 1,000,000 ns
        result = _convert(1.0, _DEEP_BASE_TO_SECONDS, "ns")
        self.assertAlmostEqual(result, 1_000_000.0, places=5)


# ===========================================================================
# 3. Formatting
# ===========================================================================


class TestFormat(unittest.TestCase):
    def test_ns_integer(self):
        from mpynode.ui.widgets.profile import _fmt

        self.assertEqual(_fmt(1234.7, "ns"), "1235")

    def test_us_two_decimals(self):
        from mpynode.ui.widgets.profile import _fmt

        self.assertEqual(_fmt(1.236, "\u00b5s"), "1.24")

    def test_ms_three_decimals(self):
        from mpynode.ui.widgets.profile import _fmt

        self.assertEqual(_fmt(0.1234, "ms"), "0.123")

    def test_s_six_decimals(self):
        from mpynode.ui.widgets.profile import _fmt

        self.assertEqual(_fmt(0.0001234, "s"), "0.000123")


# ===========================================================================
# 4. Widget surface (source-pin)
# ===========================================================================


class TestProfileWidgetUnitDropdown(unittest.TestCase):
    def test_all_qt_symbols_bound_at_module_load(self):
        """Regression guard: an early version of the unit-
        dropdown edit dropped QLabel + QHBoxLayout from the import
        list (they're indispensable for the widget). Headless tests
        don't catch this because they skipUnless Qt-available. Pin
        the full import list explicitly.

        QCheckBox was removed when the two Enable-Profile checkboxes
        were replaced by a single Profile-mode QComboBox.
        """
        import mpynode.ui.widgets.profile as profile_module

        for symbol in (
            "QLabel",
            "QHBoxLayout",
            "QComboBox",
            "QPushButton",
            "Qt",
            "QTreeWidget",
            "QTreeWidgetItem",
            "QVBoxLayout",
            "QWidget",
        ):
            self.assertTrue(
                hasattr(profile_module, symbol),
                f"profile.py missing required Qt import: {symbol}",
            )
        # QCheckBox must NOT be reintroduced -- profiling is driven by
        # the Profile-mode combo now, not checkboxes.
        self.assertFalse(
            hasattr(profile_module, "QCheckBox"),
            "profile.py should no longer import QCheckBox (the Enable "
            "checkboxes were replaced by the Profile-mode combo).",
        )

    def test_widget_has_unit_combo(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.__init__)
        self.assertIn("self._unit_combo", src)
        self.assertIn("QComboBox", src)

    def test_widget_has_unit_changed_handler(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        self.assertTrue(hasattr(NDProfileWidget, "_on_unit_changed"))

    def test_unit_changed_wired_to_combo(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.__init__)
        self.assertIn(
            "self._unit_combo.currentTextChanged.connect(self._on_unit_changed)",
            src,
        )

    def test_unit_changed_handler_triggers_refresh(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget._on_unit_changed)
        self.assertIn("self.refresh()", src)

    def test_default_unit_is_microseconds(self):
        from mpynode.ui.widgets.profile import _DEFAULT_UNIT, NDProfileWidget

        src = inspect.getsource(NDProfileWidget.__init__)
        # Init stores _DEFAULT_UNIT into self._unit.
        self.assertIn("self._unit: str = _DEFAULT_UNIT", src)
        self.assertEqual(_DEFAULT_UNIT, "\u00b5s")


# ===========================================================================
# 5. Refresh uses unit-aware labels + conversions
# ===========================================================================


class TestRefreshUsesUnit(unittest.TestCase):
    def test_refresh_rebuilds_stat_labels_with_unit(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.refresh)
        # The 4 timing labels are rebuilt each refresh using the
        # current unit string.
        self.assertIn('f"Last ({unit}):"', src)
        self.assertIn('f"Avg ({unit}):"', src)
        self.assertIn('f"Min ({unit}):"', src)
        self.assertIn('f"Max ({unit}):"', src)

    def test_refresh_rebuilds_tree_headers_with_unit(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.refresh)
        self.assertIn('f"Cumulative ({unit})"', src)
        self.assertIn('f"Total ({unit})"', src)
        self.assertIn('f"Per-call ({unit})"', src)

    def test_refresh_converts_snapshot_values(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.refresh)
        # The snapshot values are converted via _convert with the
        # microsecond-base divisor.
        self.assertIn("_convert(", src)
        self.assertIn("_SNAP_BASE_TO_SECONDS", src)
        self.assertIn("_DEEP_BASE_TO_SECONDS", src)


# ===========================================================================
# 6. Sort key is canonical seconds (preserves order across switches)
# ===========================================================================


class TestSortKeyIsCanonical(unittest.TestCase):
    def test_set_float_col_accepts_sort_seconds(self):
        from mpynode.ui.widgets.profile import _set_float_col

        sig = inspect.signature(_set_float_col)
        self.assertIn("sort_seconds", sig.parameters)
        self.assertIn("unit", sig.parameters)

    def test_set_float_col_stores_seconds_in_user_role(self):
        from mpynode.ui.widgets.profile import _set_float_col

        src = inspect.getsource(_set_float_col)
        # Stores sort_seconds (or value) into UserRole.
        self.assertIn("sort_seconds if sort_seconds is not None else value", src)

    def test_sortable_item_class_exists(self):
        """Regression guard: the cProfile tree was sorting
        lexicographically (e.g. cumulative col returned [84, 666, 541,
        3959, 250, 208, 208, 1501, 13625, 12125] in ns) because
        QTreeWidget compares display text by default, not the
        canonical-seconds value we stored in Qt.UserRole. Fix:
        _SortableTreeWidgetItem subclass overrides __lt__ to consult
        UserRole when present."""
        from mpynode.ui.widgets.profile import _SortableTreeWidgetItem

        # Verify the override is defined on the subclass (not just
        # inherited from QTreeWidgetItem).
        self.assertIn("__lt__", _SortableTreeWidgetItem.__dict__)

    def test_sortable_item_lt_consults_user_role(self):
        from mpynode.ui.widgets.profile import _SortableTreeWidgetItem

        src = inspect.getsource(_SortableTreeWidgetItem.__lt__)
        # Reads Qt.UserRole from both items and compares as floats.
        self.assertIn("self.data(col, Qt.UserRole)", src)
        self.assertIn("other.data(col, Qt.UserRole)", src)
        self.assertIn("float(a) < float(b)", src)

    def test_sortable_item_lt_does_not_call_super(self):
        """Regression guard: ``super().__lt__()`` re-enters
        through PySide's virtual-function dispatch and infinite-recurses
        when the cProfile tree is sorted (user-reported RecursionError
        when Enable Deep Profile is on). __lt__ must implement the text
        fallback DIRECTLY via self.text(col) < other.text(col)."""
        from mpynode.ui.widgets.profile import _SortableTreeWidgetItem

        src = inspect.getsource(_SortableTreeWidgetItem.__lt__)
        # Strip Python line-comments before checking -- the method's
        # own warning-comment mentions the forbidden pattern by name.
        code_only = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
        self.assertNotIn(
            "super().__lt__",
            code_only,
            "_SortableTreeWidgetItem.__lt__ must not call super().__lt__ "
            "-- causes infinite recursion via PySide virtual dispatch",
        )
        # And it MUST use the direct-text comparison fallback.
        self.assertIn("self.text(col) < other.text(col)", src)

    def test_refresh_uses_sortable_item_class(self):
        """Pin that refresh() instantiates _SortableTreeWidgetItem, not
        the default QTreeWidgetItem (which would re-trigger the bug)."""
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.refresh)
        self.assertIn("_SortableTreeWidgetItem(self._tree)", src)
        # ...and NOT "QTreeWidgetItem(self._tree)", the previous buggy per-row
        # pattern (headers may still use a plain QTreeWidgetItem).
        self.assertNotIn("QTreeWidgetItem(self._tree)", src)


class TestSortableItemNumericOrder(unittest.TestCase):
    """Pure-Python (no Qt instance needed) test of the __lt__ comparator
    using mock objects. Reproduces the exact regression from the user's
    screenshots: in lex-sort, [208, 250, 1501, 666] would come out as
    [1501, 208, 250, 666]. With UserRole-based numeric sort, the order
    must be [208, 250, 666, 1501]."""

    def test_numeric_sort_preserved_across_magnitude_ranges(self):
        """Reproduce the exact bug: small + large numbers mixed."""
        import sys

        # Bypass needing a live QTreeWidget by mocking the sort interface.
        class _MockItem:
            """Subset of _SortableTreeWidgetItem.__lt__ behavior we need."""

            def __init__(self, sort_value, display_text):
                self.sort_value = sort_value
                self.display_text = display_text

            def __lt__(self, other):
                # Mirror _SortableTreeWidgetItem.__lt__: consult sort key.
                if self.sort_value is not None and other.sort_value is not None:
                    return float(self.sort_value) < float(other.sort_value)
                return self.display_text < other.display_text

        # Bug repro from a real "Cumulative (ns)" column: the pre-fix lex sort
        # ordered these '208' < '250' < '1501', which is wrong.
        values = [84, 666, 541, 3959, 3334, 2542, 250, 208, 208, 1501, 13625, 12125]
        items = [_MockItem(v, str(v)) for v in values]
        items.sort()
        result = [item.sort_value for item in items]
        self.assertEqual(result, sorted(values))
        # Specifically: 250 should NOT come BEFORE 1501 (which is what
        # the buggy lex sort would do because '1' < '2').
        idx_250 = result.index(250)
        idx_1501 = result.index(1501)
        self.assertLess(
            idx_250,
            idx_1501,
            "250 must sort before 1501 numerically (1501 > 250)",
        )


def setUpModule():
    _setUpModule__phase30_2()
    _setUpModule__framework_toggles_hidden()
    _setUpModule__phase29_1()
    _setUpModule__phase29_3()


# ===========================================================================
# API dataclasses show as a LABEL, never as a pickled payload
# ===========================================================================


class TestLabelOnlyWatchValues(unittest.TestCase):
    """Mesh / NurbsCurve / Morph / Draw* collapse to their repr in the snapshot.

    The snapshot is pickled to a plug EVERY compute. Before this, a 20k-point
    Mesh was pickled in full (~680 KB) purely so the size estimate could decide
    it was too big, then thrown away for a "<too large>" string that did not say
    which mesh it was. Collapsing up front is both cheaper and more informative.
    """

    def test_a_big_mesh_collapses_to_its_repr_without_pickling(self):
        import numpy as np
        from mpynode._api2.geometry import Mesh
        from mpynode._common.instrumentation.watch import cap_watch_value

        big = Mesh(points=np.zeros((20000, 3)),
                   counts=np.full(5000, 4, dtype=np.int32),
                   indices=np.zeros(20000, dtype=np.int32))
        out = cap_watch_value(big)
        self.assertIsInstance(out, str)
        self.assertEqual(out, repr(big))
        self.assertNotIn("too large", out)

    def test_draw_items_collapse_too(self):
        from mpynode._common.draw.draw_types import DrawCircle
        from mpynode._common.instrumentation.watch import cap_watch_value

        out = cap_watch_value(DrawCircle(center=(0, 0, 0), radius=2.0))
        self.assertIsInstance(out, str)
        self.assertIn("DrawCircle", out)

    def test_ordinary_values_are_untouched(self):
        # The substitution must be narrow: an ndarray is exactly the thing a
        # user DOES want to inspect element-by-element.
        import numpy as np
        from mpynode._common.instrumentation.watch import cap_watch_value

        arr = np.arange(10)
        self.assertIs(cap_watch_value(arr), arr)
        self.assertEqual(cap_watch_value("hello"), "hello")
        self.assertEqual(cap_watch_value(3), 3)
        self.assertIsNone(cap_watch_value(None))

    def test_the_label_remembers_what_it_replaced(self):
        # The Value column shows the repr, but the Type column must still say
        # "Mesh" -- a collapsed stand-in that reported "str" would be a
        # regression over showing the object itself.
        import numpy as np
        from mpynode._api2.geometry import Mesh
        from mpynode._common.instrumentation.watch import (
            WatchLabel,
            cap_watch_value,
        )

        out = cap_watch_value(Mesh(points=np.zeros((3, 3)),
                                   counts=np.array([3], dtype=np.int32),
                                   indices=np.arange(3, dtype=np.int32)))
        self.assertIsInstance(out, WatchLabel)
        self.assertEqual(out.type_name, "Mesh")

    def test_the_label_survives_the_pickle_round_trip(self):
        # The snapshot is pickled to _watchVarsData and unpickled in the UI. A
        # str subclass with extra state does NOT round-trip by default, so the
        # type name would arrive missing and the Type column would read "str".
        import pickle

        from mpynode._common.instrumentation.watch import WatchLabel

        back = pickle.loads(pickle.dumps(WatchLabel('Mesh("pCubeShape1")',
                                                    "Mesh")))
        self.assertIsInstance(back, WatchLabel)
        self.assertEqual(back, 'Mesh("pCubeShape1")')
        self.assertEqual(back.type_name, "Mesh")


# ===========================================================================
# the FRAMEWORK surface rides in the watch snapshot
# ===========================================================================


class TestFrameworkVarsCapture(unittest.TestCase):
    """``self.X`` wrapper slots reach the Watch tab.

    ``self`` is deliberately excluded from Locals (it is the SelfProxy, not a
    user value), so the slots hanging off it -- a locator's draw, a mesh's
    points/counts/indices -- had no way to be seen. They are already in memory
    on the proxy at the snapshot point, so collecting them costs no evaluation.
    """

    def test_collect_framework_vars_reads_the_proxy(self):
        from mpynode._common.instrumentation.watch import collect_framework_vars

        class FakeProxy:
            def get_compute_locals(self):
                return {"points": [1, 2, 3], "time": 4.0, "_hidden": "no"}

        out = collect_framework_vars({"self": FakeProxy()})
        self.assertEqual(out.get("time"), 4.0)
        self.assertEqual(out.get("points"), [1, 2, 3])
        # same hygiene as Locals: private names never surface
        self.assertNotIn("_hidden", out)

    def test_a_proxy_without_compute_locals_is_not_an_error(self):
        from mpynode._common.instrumentation.watch import collect_framework_vars

        self.assertEqual(collect_framework_vars({}), {})
        self.assertEqual(collect_framework_vars({"self": object()}), {})

    def test_a_raising_proxy_degrades_to_empty(self):
        from mpynode._common.instrumentation.watch import collect_framework_vars

        class Exploding:
            def get_compute_locals(self):
                raise RuntimeError("boom")

        # Instrumentation must never take a compute down with it.
        self.assertEqual(collect_framework_vars({"self": Exploding()}), {})

    def test_the_reserved_key_cannot_collide_with_a_user_variable(self):
        from mpynode._common.instrumentation.watch import (
            WATCH_FRAMEWORK_KEY, filter_watch_vars)

        # filter_watch_vars drops every leading-underscore name, so a user
        # cannot land a variable on the key the framework surface travels under.
        self.assertTrue(WATCH_FRAMEWORK_KEY.startswith("_"))
        self.assertEqual(
            filter_watch_vars({WATCH_FRAMEWORK_KEY: "spoofed"}), {})


if __name__ == "__main__":
    import unittest
    unittest.main()
