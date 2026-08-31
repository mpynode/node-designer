"""Profile + watch instrumentation tests.

Live tests (no Qt): the throttle helper, stats math, snapshot encode/
decode round-trip, watch filter, cProfile capture, _api1 migration
source-inspection, plug round-trips, multi-frame stats accumulation.

Inspect-only Qt tests: widget existence, glob filter helper exists,
designer wiring (addTab + _on_node_attr_changed branches +
refresh-for-node methods + setCurrentNode setPyNode calls).

Per the established discipline, no widget instantiation in
mayapy tests \u2014 we inspect class signatures and source for the Qt
hooks instead.
"""

from __future__ import annotations

import inspect
import unittest

import maya.cmds as mc

from._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Throttle helper (pure)
# ===========================================================================


class TestThrottlePolicy(unittest.TestCase):
    def test_count_zero_returns_false(self):
        from mpynode._common.instrumentation import should_write_snapshot

        self.assertFalse(should_write_snapshot(0))
        self.assertFalse(should_write_snapshot(-1))

    def test_count_one_always_writes(self):
        from mpynode._common.instrumentation import should_write_snapshot

        self.assertTrue(should_write_snapshot(1))
        self.assertTrue(should_write_snapshot(1, period=30))
        self.assertTrue(should_write_snapshot(1, period=10))

    def test_writes_every_nth_call(self):
        from mpynode._common.instrumentation import should_write_snapshot

        # period=30: 1 always, then 30, 60, 90,...
        self.assertTrue(should_write_snapshot(30, period=30))
        self.assertTrue(should_write_snapshot(60, period=30))
        self.assertTrue(should_write_snapshot(90, period=30))
        # In between: no write.
        self.assertFalse(should_write_snapshot(2, period=30))
        self.assertFalse(should_write_snapshot(15, period=30))
        self.assertFalse(should_write_snapshot(29, period=30))
        self.assertFalse(should_write_snapshot(31, period=30))
        self.assertFalse(should_write_snapshot(59, period=30))

    def test_custom_period(self):
        from mpynode._common.instrumentation import should_write_snapshot

        self.assertTrue(should_write_snapshot(5, period=5))
        self.assertTrue(should_write_snapshot(10, period=5))
        self.assertFalse(should_write_snapshot(7, period=5))

    def test_period_one_writes_every_call(self):
        from mpynode._common.instrumentation import should_write_snapshot

        for n in range(1, 20):
            self.assertTrue(should_write_snapshot(n, period=1))


# ===========================================================================
# Stats math (cumulative running mean)
# ===========================================================================


class TestStatsMath(unittest.TestCase):
    def _fresh_stats(self) -> dict:
        return {
            "last_us": 0.0,
            "avg_us": 0.0,
            "min_us": 0.0,
            "max_us": 0.0,
            "count": 0,
        }

    def test_first_sample_initializes_min_max_avg(self):
        from mpynode._common.instrumentation import update_stats

        stats = self._fresh_stats()
        update_stats(stats, 100.0)
        self.assertEqual(stats["count"], 1)
        self.assertAlmostEqual(stats["last_us"], 100.0)
        self.assertAlmostEqual(stats["avg_us"], 100.0)
        self.assertAlmostEqual(stats["min_us"], 100.0)
        self.assertAlmostEqual(stats["max_us"], 100.0)

    def test_subsequent_samples_running_mean(self):
        from mpynode._common.instrumentation import update_stats

        stats = self._fresh_stats()
        update_stats(stats, 100.0)
        update_stats(stats, 200.0)
        update_stats(stats, 300.0)
        self.assertEqual(stats["count"], 3)
        self.assertAlmostEqual(stats["avg_us"], 200.0)
        self.assertAlmostEqual(stats["min_us"], 100.0)
        self.assertAlmostEqual(stats["max_us"], 300.0)
        self.assertAlmostEqual(stats["last_us"], 300.0)

    def test_min_max_track_extremes(self):
        from mpynode._common.instrumentation import update_stats

        stats = self._fresh_stats()
        for sample in (50.0, 100.0, 25.0, 75.0, 200.0, 30.0):
            update_stats(stats, sample)
        self.assertEqual(stats["min_us"], 25.0)
        self.assertEqual(stats["max_us"], 200.0)
        self.assertEqual(stats["count"], 6)

    def test_running_mean_no_overflow_long_session(self):
        """1000 samples shouldn't drift due to floating point."""
        from mpynode._common.instrumentation import update_stats

        stats = self._fresh_stats()
        for _ in range(1000):
            update_stats(stats, 50.0)
        self.assertAlmostEqual(stats["avg_us"], 50.0, places=6)
        self.assertEqual(stats["count"], 1000)


# ===========================================================================
# Profile snapshot envelope round-trip
# ===========================================================================


class TestProfileSnapshotEnvelope(unittest.TestCase):
    def test_encode_decode_round_trip(self):
        from mpynode._common.instrumentation import (
            decode_profile_snapshot,
            encode_profile_snapshot,
        )

        stats = {
            "last_us": 12.5,
            "avg_us": 10.0,
            "min_us": 5.0,
            "max_us": 25.0,
            "count": 42,
        }
        text = encode_profile_snapshot(stats)
        decoded = decode_profile_snapshot(text)
        self.assertEqual(decoded["count"], 42)
        self.assertAlmostEqual(decoded["last_us"], 12.5)
        self.assertAlmostEqual(decoded["avg_us"], 10.0)
        self.assertAlmostEqual(decoded["min_us"], 5.0)
        self.assertAlmostEqual(decoded["max_us"], 25.0)
        self.assertNotIn("deep_table", decoded)

    def test_encode_includes_deep_table(self):
        from mpynode._common.instrumentation import (
            decode_profile_snapshot,
            encode_profile_snapshot,
        )

        stats = {"last_us": 0, "avg_us": 0, "min_us": 0, "max_us": 0, "count": 1}
        deep = [
            {
                "function": "foo (bar.py:10)",
                "calls": 5,
                "tottime_ms": 1.5,
                "cumtime_ms": 3.0,
                "percall_ms": 0.6,
            }
        ]
        text = encode_profile_snapshot(stats, deep)
        decoded = decode_profile_snapshot(text)
        self.assertIn("deep_table", decoded)
        self.assertEqual(len(decoded["deep_table"]), 1)
        self.assertEqual(decoded["deep_table"][0]["function"], "foo (bar.py:10)")

    def test_decode_empty_returns_none(self):
        from mpynode._common.instrumentation import decode_profile_snapshot

        self.assertIsNone(decode_profile_snapshot(""))
        self.assertIsNone(decode_profile_snapshot("not json"))


# ===========================================================================
# Watch vars envelope round-trip (handles non-JSON values)
# ===========================================================================


class TestWatchVarsEnvelope(unittest.TestCase):
    def test_round_trip_simple_values(self):
        from mpynode._common.instrumentation import decode_watch_vars, encode_watch_vars

        vars_dict = {"a": 1, "b": "hello", "c": [1, 2, 3], "d": {"key": True}}
        text = encode_watch_vars(vars_dict)
        decoded = decode_watch_vars(text)
        self.assertEqual(decoded, vars_dict)

    def test_round_trip_numpy_arrays(self):
        import numpy as np
        from mpynode._common.instrumentation import decode_watch_vars, encode_watch_vars

        vars_dict = {"vec": np.array([1.0, 2.0, 3.0]), "mat": np.eye(3)}
        text = encode_watch_vars(vars_dict)
        decoded = decode_watch_vars(text)
        self.assertIn("vec", decoded)
        self.assertTrue(np.array_equal(decoded["vec"], vars_dict["vec"]))
        self.assertTrue(np.array_equal(decoded["mat"], vars_dict["mat"]))

    def test_unpicklable_value_falls_back_to_repr(self):
        from mpynode._common.instrumentation import decode_watch_vars, encode_watch_vars

        # Lambda is not picklable.
        vars_dict = {"f": lambda x: x, "y": 42}
        text = encode_watch_vars(vars_dict)
        decoded = decode_watch_vars(text)
        self.assertIn("f", decoded)
        self.assertEqual(decoded["y"], 42)
        self.assertIsInstance(decoded["f"], str)
        self.assertIn("lambda", decoded["f"])

    def test_decode_empty_returns_none(self):
        from mpynode._common.instrumentation import decode_watch_vars

        self.assertIsNone(decode_watch_vars(""))
        self.assertIsNone(decode_watch_vars("not json"))


# ===========================================================================
# filter_watch_vars (used by exec_with_profile_watch's snapshot writer)
# ===========================================================================


class TestFilterWatchVars(unittest.TestCase):
    def test_drops_modules_functions_classes_dunders(self):
        import math

        from mpynode._common.instrumentation import filter_watch_vars

        def fn():
            return 1

        class Cls:
            pass

        scope = {
            "x": 5,
            "y": "hello",
            "math": math,
            "fn": fn,
            "Cls": Cls,
            "_priv": 99,
            "__dunder": 100,
            "__builtins__": {},
        }
        out = filter_watch_vars(scope)
        self.assertEqual(out, {"x": 5, "y": "hello"})

    def test_glob_filter_target_star(self):
        from mpynode._common.instrumentation import filter_watch_vars

        scope = {
            "target_pos": [1, 2, 3],
            "target_rot": [0, 0, 0],
            "rest_pos": [0, 0, 0],
            "weight": 1.0,
        }
        out = filter_watch_vars(scope, glob_filter="target_*")
        self.assertEqual(set(out.keys()), {"target_pos", "target_rot"})

    def test_substring_filter_no_glob_metachar(self):
        from mpynode._common.instrumentation import filter_watch_vars

        scope = {"alpha_target": 1, "beta": 2, "target_x": 3}
        out = filter_watch_vars(scope, glob_filter="target")
        self.assertEqual(set(out.keys()), {"alpha_target", "target_x"})

    def test_empty_filter_keeps_all_user_vars(self):
        from mpynode._common.instrumentation import filter_watch_vars

        scope = {"a": 1, "b": 2}
        out = filter_watch_vars(scope, glob_filter="")
        self.assertEqual(out, scope)

    def test_does_not_mutate_input(self):
        from mpynode._common.instrumentation import filter_watch_vars

        scope = {"a": 1, "_b": 2}
        snapshot = dict(scope)
        filter_watch_vars(scope)
        self.assertEqual(scope, snapshot)


# ===========================================================================
# encode_cprofile_stats (round-trip via a known-slow expression)
# ===========================================================================


class TestCProfileCapture(unittest.TestCase):
    def test_capture_round_trip(self):
        import cProfile

        from mpynode._common.instrumentation import encode_cprofile_stats

        def slow_op():
            return sum(i * i for i in range(2000))

        prof = cProfile.Profile()
        prof.enable()
        slow_op()
        prof.disable()

        rows = encode_cprofile_stats(prof)
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertIn("function", row)
            self.assertIn("calls", row)
            self.assertIn("tottime_ms", row)
            self.assertIn("cumtime_ms", row)
            self.assertIn("percall_ms", row)
            self.assertIsInstance(row["calls"], int)
            self.assertIsInstance(row["tottime_ms"], float)

    def test_rows_sorted_by_cumtime_desc(self):
        import cProfile

        from mpynode._common.instrumentation import encode_cprofile_stats

        prof = cProfile.Profile()
        prof.enable()
        sum(i * i for i in range(1000))
        prof.disable()

        rows = encode_cprofile_stats(prof)
        if len(rows) > 1:
            cumtimes = [r["cumtime_ms"] for r in rows]
            self.assertEqual(cumtimes, sorted(cumtimes, reverse=True))


# ===========================================================================
# Live: per-instance stats accumulate across multi-frame compute
# ===========================================================================


class TestPerInstanceStats(unittest.TestCase):
    def test_get_or_create_stats_initializes_zeros(self):
        from mpynode._common.instrumentation import get_or_create_stats, reset_stats

        # Use a sentinel object as node_obj — the helper falls back to id().
        sentinel = object()
        try:
            stats = get_or_create_stats(sentinel)
            self.assertEqual(stats["count"], 0)
            self.assertEqual(stats["last_us"], 0.0)
            self.assertEqual(stats["avg_us"], 0.0)
            self.assertEqual(stats["min_us"], 0.0)
            self.assertEqual(stats["max_us"], 0.0)
        finally:
            reset_stats(sentinel)

    def test_repeated_get_returns_same_dict(self):
        from mpynode._common.instrumentation import get_or_create_stats, reset_stats

        sentinel = object()
        try:
            a = get_or_create_stats(sentinel)
            b = get_or_create_stats(sentinel)
            self.assertIs(a, b)
        finally:
            reset_stats(sentinel)

    def test_reset_clears(self):
        from mpynode._common.instrumentation import (
            get_or_create_stats,
            reset_stats,
            update_stats,
        )

        sentinel = object()
        stats = get_or_create_stats(sentinel)
        update_stats(stats, 50.0)
        update_stats(stats, 75.0)
        self.assertEqual(stats["count"], 2)
        reset_stats(sentinel)
        new_stats = get_or_create_stats(sentinel)
        self.assertEqual(new_stats["count"], 0)
        reset_stats(sentinel)


# ===========================================================================
# Live: end-to-end compute with profile + watch toggles
# ===========================================================================


class TestEndToEndProfileWatch(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _make_node(self, name="prof_test"):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=name)
        n.add_input_attr("a", "float")
        n.add_output_attr("c", "float")
        # Expression has measurable but small work + creates locals to watch.
        n.set_compute_expression(
            "target_x = self.a * 2.0\n"
            "rest_x = self.a + 1.0\n"
            "tmp = sum(i for i in range(50))\n"
            "self.c = target_x + rest_x + tmp\n"
        )
        return n

    def test_node_has_phase25_plugs(self):
        n = self._make_node("plug_check")
        node_name = n.get_name()
        for attr in (
            "profile_enabled",
            "deep_profile_enabled",
            "watch_enabled",
            "_profileSnapshotData",
            "_watchVarsData",
        ):
            self.assertTrue(
                mc.attributeQuery(attr, node=node_name, exists=True),
                f"node {node_name!r} missing plug {attr!r}",
            )

    def test_default_toggles_are_off(self):
        n = self._make_node("default_off")
        self.assertFalse(n.is_profile_enabled())
        self.assertFalse(n.is_deep_profile_enabled())
        self.assertFalse(n.is_watch_enabled())

    def test_disabled_path_no_snapshot_written(self):
        n = self._make_node("disabled")
        mc.setAttr(n.get_name() + ".a", 1.0)
        mc.getAttr(n.get_name() + ".c")
        self.assertIsNone(n.get_profile_snapshot())
        self.assertIsNone(n.get_watch_vars())

    def test_profile_on_writes_snapshot_after_first_compute(self):
        n = self._make_node("prof_on")
        mc.setAttr(n.get_name() + ".profile_enabled", True)
        mc.setAttr(n.get_name() + ".a", 2.0)
        mc.getAttr(n.get_name() + ".c")
        snap = n.get_profile_snapshot()
        self.assertIsNotNone(snap, "expected snapshot after first compute")
        self.assertEqual(snap["count"], 1)
        self.assertGreater(snap["last_us"], 0.0)
        self.assertGreater(snap["avg_us"], 0.0)
        self.assertGreater(snap["max_us"], 0.0)

    def test_multi_frame_stats_accumulate(self):
        n = self._make_node("multi_frame")
        mc.setAttr(n.get_name() + ".profile_enabled", True)
        for i in range(35):
            mc.setAttr(n.get_name() + ".a", float(i))
            mc.getAttr(n.get_name() + ".c")
        snap = n.get_profile_snapshot()
        self.assertIsNotNone(snap)
        # Throttle policy writes at count=1 and count=30, so after 35 frames
        # the last persisted snapshot is count=30 (next write is count=60).
        self.assertEqual(snap["count"], 30)
        self.assertGreater(snap["max_us"], 0.0)
        self.assertGreaterEqual(snap["max_us"], snap["min_us"])

    def test_deep_profile_populates_deep_table(self):
        n = self._make_node("deep_on")
        mc.setAttr(n.get_name() + ".profile_enabled", True)
        mc.setAttr(n.get_name() + ".deep_profile_enabled", True)
        mc.setAttr(n.get_name() + ".a", 3.0)
        mc.getAttr(n.get_name() + ".c")
        snap = n.get_profile_snapshot()
        self.assertIsNotNone(snap)
        self.assertIn("deep_table", snap)
        self.assertGreater(len(snap["deep_table"]), 0)

    def test_watch_on_captures_user_locals_excludes_modules(self):
        n = self._make_node("watch_on")
        mc.setAttr(n.get_name() + ".watch_enabled", True)
        mc.setAttr(n.get_name() + ".a", 5.0)
        mc.getAttr(n.get_name() + ".c")
        watch = n.get_watch_vars()
        self.assertIsNotNone(watch)
        self.assertIn("target_x", watch)
        self.assertIn("rest_x", watch)
        self.assertIn("tmp", watch)
        # No module / function / class / dunder leakage.
        self.assertNotIn("np", watch)
        self.assertNotIn("math", watch)
        self.assertNotIn("__builtins__", watch)
        self.assertAlmostEqual(float(watch["target_x"]), 10.0)
        self.assertAlmostEqual(float(watch["rest_x"]), 6.0)

    def test_toggle_off_after_use_does_not_raise(self):
        n = self._make_node("off_again")
        mc.setAttr(n.get_name() + ".profile_enabled", True)
        mc.setAttr(n.get_name() + ".a", 1.0)
        mc.getAttr(n.get_name() + ".c")
        mc.setAttr(n.get_name() + ".profile_enabled", False)
        mc.setAttr(n.get_name() + ".a", 2.0)
        mc.getAttr(n.get_name() + ".c")
        # the previous snapshot stays (stale-but-present).
        snap = n.get_profile_snapshot()
        self.assertIsNotNone(snap)


# ===========================================================================
# Plug round-trip via the wrapper helpers
# ===========================================================================


class TestWrapperReadHelpers(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_helpers_return_none_when_no_data(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="empty_helpers")
        self.assertIsNone(n.get_profile_snapshot())
        self.assertIsNone(n.get_watch_vars())
        self.assertFalse(n.is_profile_enabled())
        self.assertFalse(n.is_deep_profile_enabled())
        self.assertFalse(n.is_watch_enabled())

    def test_helpers_reflect_toggle_state(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="toggle_helpers")
        mc.setAttr(n.get_name() + ".profile_enabled", True)
        mc.setAttr(n.get_name() + ".watch_enabled", True)
        self.assertTrue(n.is_profile_enabled())
        self.assertTrue(n.is_watch_enabled())
        self.assertFalse(n.is_deep_profile_enabled())

    def test_get_profile_snapshot_after_write(self):
        from mpynode._common.instrumentation import write_profile_snapshot
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="getter_check")

        import maya.api.OpenMaya as om

        sel = om.MSelectionList()
        sel.add(n.get_name())
        node_obj = sel.getDependNode(0)

        stats = {
            "last_us": 5.0,
            "avg_us": 4.0,
            "min_us": 1.0,
            "max_us": 8.0,
            "count": 7,
        }
        write_profile_snapshot(node_obj, stats)
        snap = n.get_profile_snapshot()
        self.assertIsNotNone(snap)
        self.assertEqual(snap["count"], 7)
        self.assertAlmostEqual(snap["last_us"], 5.0)


# ===========================================================================
# Live: the API 1 nodes also got the new plugs (checked via mPyIkSolver)
# ===========================================================================


class TestApi1NodesHavePhase25Plugs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _check_node(self, native_type: str):
        node_name = mc.createNode(native_type)
        for attr in (
            "profile_enabled",
            "deep_profile_enabled",
            "watch_enabled",
            "_profileSnapshotData",
            "_watchVarsData",
        ):
            self.assertTrue(
                mc.attributeQuery(attr, node=node_name, exists=True),
                f"{native_type}: missing plug {attr}",
            )

    def test_iksolver_node_has_phase25_plugs(self):
        self._check_node("mPyIkSolver")


# ===========================================================================
# _api1 migration: confirm exec_with_profile_watch is in the source
# of the 3 migrated functions (instead of raw exec()).
# ===========================================================================


class TestApi1MigrationSourceInspection(unittest.TestCase):
    def test_iksolver_helpers_uses_exec_with_profile_watch(self):
        from mpynode._api1 import helpers

        src = inspect.getsource(helpers.compute_ik_user_solve)
        self.assertIn("exec_with_profile_watch", src)
        # The old raw exec(code,...) call is gone.
        self.assertNotIn("exec(code, exec_globals, exec_locals)", src)


# ===========================================================================
# Inspect-only Qt: widgets exist + have setPyNode / refresh / glob filter
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestProfileWidgetShape(unittest.TestCase):
    def test_widget_class_exists(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        self.assertTrue(callable(NDProfileWidget))

    def test_widget_has_setPyNode_and_refresh(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        for attr in ("setPyNode", "refresh"):
            self.assertTrue(
                callable(getattr(NDProfileWidget, attr, None)),
                f"NDProfileWidget should have {attr}",
            )

    def test_widget_has_controls_in_init_source(self):
        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.__init__)
        # The two Enable checkboxes became one Profile-mode combo
        # (Off / Profile / Deep) plus an "Evaluate Node" button.
        self.assertIn("self._mode_combo", src)
        self.assertIn("Reset Stats", src)
        self.assertIn("Evaluate Node", src)
        self.assertIn("self._unit_combo", src)

    def test_widget_init_creates_5_stat_rows(self):
        from mpynode.ui.widgets.profile import _STAT_KEYS

        # _STAT_LABELS (which baked the unit "us" into the text) became
        # _STAT_KEYS: labels are rebuilt per-refresh from the unit combo.
        self.assertEqual(
            set(_STAT_KEYS),
            {"last", "avg", "min", "max", "count"},
        )


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestWatchWidgetShape(unittest.TestCase):
    def test_widget_class_exists(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        self.assertTrue(callable(NDWatchWidget))

    def test_widget_has_setPyNode_refresh_setFilter(self):
        from mpynode.ui.widgets.watch import NDWatchWidget

        for attr in ("setPyNode", "refresh", "setFilter"):
            self.assertTrue(
                callable(getattr(NDWatchWidget, attr, None)),
                f"NDWatchWidget should have {attr}",
            )

    def test_apply_filter_glob(self):
        from mpynode.ui.widgets.watch import apply_filter

        scope = {"target_pos": 1, "target_rot": 2, "weight": 3}
        out = apply_filter(scope, "target_*")
        self.assertEqual(set(out.keys()), {"target_pos", "target_rot"})

    def test_apply_filter_substring(self):
        from mpynode.ui.widgets.watch import apply_filter

        scope = {"alpha_target": 1, "weight": 2, "target_x": 3}
        out = apply_filter(scope, "target")
        self.assertEqual(set(out.keys()), {"alpha_target", "target_x"})

    def test_apply_filter_empty_keeps_all(self):
        from mpynode.ui.widgets.watch import apply_filter

        scope = {"a": 1, "b": 2}
        self.assertEqual(apply_filter(scope, ""), scope)


# ===========================================================================
# Inspect-only Qt: designer wires both new tabs + dispatches both new plugs
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestDesignerWiring(unittest.TestCase):
    def test_build_ui_adds_profile_and_watch_tabs(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_ui)
        self.assertIn("NDProfileWidget", src)
        self.assertIn("NDWatchWidget", src)
        self.assertIn('"Profile"', src)
        self.assertIn('"Watch"', src)

    def test_set_current_node_pushes_to_both_widgets(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.setCurrentNode)
        self.assertIn("self._profile_widget.setPyNode", src)
        self.assertIn("self._watch_widget.setPyNode", src)

    def test_on_node_attr_changed_dispatches_both_plugs(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._on_node_attr_changed)
        self.assertIn("_profileSnapshotData", src)
        self.assertIn("_watchVarsData", src)
        self.assertIn("_refresh_profile_for_node", src)
        self.assertIn("_refresh_watch_for_node", src)

    def test_designer_has_refresh_methods(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        for name in ("_refresh_profile_for_node", "_refresh_watch_for_node"):
            self.assertTrue(
                hasattr(NDMainWindow, name),
                f"NDMainWindow should have {name}",
            )


# ===========================================================================
# \u2014 toggles non-storable + force-eval on toggle-on +
# editor compile-error popup.
# ===========================================================================


class TestHotfix8TogglesNonStorable(unittest.TestCase):
    """Profile / deep-profile / watch toggles AND their snapshot data
    plugs must NOT be saved to.ma. They always default off / empty on
    file open so a user can never ship a scene with the profiler
    accidentally left on."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _is_storable(self, node, attr):
        return bool(mc.attributeQuery(attr, node=node, storable=True))

    def test_profile_enabled_not_storable(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ns_prof")
        self.assertFalse(self._is_storable(n.get_name(), "profile_enabled"))

    def test_deep_profile_enabled_not_storable(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ns_deep")
        self.assertFalse(self._is_storable(n.get_name(), "deep_profile_enabled"))

    def test_watch_enabled_not_storable(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ns_watch")
        self.assertFalse(self._is_storable(n.get_name(), "watch_enabled"))

    def test_profile_snapshot_data_not_storable(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ns_psnap")
        self.assertFalse(self._is_storable(n.get_name(), "_profileSnapshotData"))

    def test_watch_vars_data_not_storable(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ns_wsnap")
        self.assertFalse(self._is_storable(n.get_name(), "_watchVarsData"))

    def test_save_reload_resets_toggles_to_off(self):
        """End-to-end: enable all 3 toggles, save scene, reopen \u2014
        toggles must be off, snapshots empty, expression preserved."""
        import os
        import tempfile

        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ns_e2e")
        n.add_input_attr("x", "float")
        n.add_output_attr("out", "float")
        n.set_compute_expression("y = x * 2.0\nout = y")
        mc.setAttr(n.get_name() + ".profile_enabled", True)
        mc.setAttr(n.get_name() + ".deep_profile_enabled", True)
        mc.setAttr(n.get_name() + ".watch_enabled", True)
        mc.setAttr(n.get_name() + ".x", 5)
        mc.getAttr(n.get_name() + ".out")  # trigger compute → populates snapshots

        ma_path = os.path.join(tempfile.mkdtemp(prefix="ns_e2e_"), "x.ma")
        try:
            mc.file(rename=ma_path)
            mc.file(save=True, type="mayaAscii", force=True)
            mc.file(new=True, force=True)
            mc.file(ma_path, open=True, force=True)

            self.assertFalse(mc.getAttr(n.get_name() + ".profile_enabled"))
            self.assertFalse(mc.getAttr(n.get_name() + ".deep_profile_enabled"))
            self.assertFalse(mc.getAttr(n.get_name() + ".watch_enabled"))
            self.assertIn(
                mc.getAttr(n.get_name() + "._profileSnapshotData") or "",
                ("", None),
            )
            self.assertIn(
                mc.getAttr(n.get_name() + "._watchVarsData") or "",
                ("", None),
            )
            # Expression must survive (storable=True is unchanged for it).
            self.assertEqual(
                mc.getAttr(n.get_name() + "._computeSource"),
                "y = x * 2.0\nout = y",
            )
        finally:
            try:
                os.remove(ma_path)
                os.rmdir(os.path.dirname(ma_path))
            except Exception:
                pass


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHotfix8WidgetForceEval(unittest.TestCase):
    """Toggling Enable Watch / Enable Profile must trigger force_one_eval
    so the snapshot panel populates without the user having to scrub
    the timeline manually."""

    def test_watch_toggled_handler_calls_force_one_eval(self):
        import inspect

        from mpynode.ui.widgets.watch import NDWatchWidget

        src = inspect.getsource(NDWatchWidget._on_watch_toggled)
        self.assertIn("force_one_eval", src)
        # Only when toggling ON (not OFF).
        self.assertIn("if checked", src)

    def test_mode_changed_handler_calls_force_one_eval(self):
        import inspect

        from mpynode.ui.widgets.profile import NDProfileWidget

        # The two toggle handlers merged into _on_mode_changed; turning
        # profiling ON must still force a one-shot compute.
        src = inspect.getsource(NDProfileWidget._on_mode_changed)
        self.assertIn("force_one_eval", src)
        self.assertIn("profile_on", src)

    def test_refresh_button_handler_calls_force_one_eval(self):
        import inspect

        from mpynode.ui.widgets.profile import NDProfileWidget

        # The "Evaluate Node" button forces a one-shot eval unconditionally.
        src = inspect.getsource(NDProfileWidget._on_refresh_clicked)
        self.assertIn("force_one_eval", src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHotfix8CompileErrorPopup(unittest.TestCase):
    """The editor's Save flow surfaces SyntaxErrors via a modal
    QMessageBox so users can't miss the broken expression."""

    def test_save_tab_sources_compile_check_and_popup(self):
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget._saveTab)
        self.assertIn("compile_expression", src)
        self.assertIn("QMessageBox", src)
        self.assertIn("Expression Compile Error", src)

    def test_save_tab_keeps_force_eval(self):
        """Make sure the toggles-non-storable change didn't accidentally
        drop the existing force_one_eval call after save (behavior)."""
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget._saveTab)
        self.assertIn("force_one_eval", src)


# ===========================================================================
# \u2014 toggles uncheck on file\u2192new + numpy formatter
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHotfix9TogglesUncheckOnNoNode(unittest.TestCase):
    """When py_node is set to None (file\u2192new clears _current_node), the
    profile + watch widgets must UNCHECK their toggles (not just disable
    them). Otherwise the user sees greyed-out checked boxes and assumes
    profiling is still on."""

    def test_profile_refresh_unchecks_when_no_node(self):
        import inspect

        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget.refresh)
        # In the ``self._py_node is None`` branch the mode combo must
        # reset to Off (was: two setChecked(False) calls).
        idx_none = src.find("self._py_node is None")
        self.assertGreater(idx_none, -1)
        cb_section = src[idx_none:]
        self.assertIn("self._mode_combo.setCurrentIndex(_MODE_OFF)", cb_section)

    def test_watch_refresh_unchecks_when_no_node(self):
        import inspect

        from mpynode.ui.widgets.watch import NDWatchWidget

        src = inspect.getsource(NDWatchWidget.refresh)
        idx_none = src.find("self._py_node is None")
        self.assertGreater(idx_none, -1)
        cb_section = src[idx_none:]
        self.assertIn("self._watch_cb.setChecked(False)", cb_section)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHotfix9NumpyFormatter(unittest.TestCase):
    """The watch widget's value formatter must preserve column-aligned
    multi-line numpy reprs so users can read matrices."""

    def test_format_value_preserves_4x4_matrix_alignment(self):
        import numpy as np
        from mpynode.ui.widgets.watch import _format_value

        m = np.eye(4)
        m[3, 0] = -5.33
        out = _format_value(m)
        self.assertIn("\n", out)
        rows = [ln for ln in out.split("\n") if "[" in ln or "]" in ln]
        self.assertGreaterEqual(len(rows), 4)
        # Sanity-check only: the numpy structure was not flattened to one line.
        self.assertNotIn("array([[1., 0., 0., 0.], [0.,", out.replace("\n", " "))

    def test_format_value_caps_long_arrays(self):
        import os
        import tempfile
        from unittest import mock

        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        # This verifies the CAP path, so it forces ``watch_threshold_inf`` off
        # in an ISOLATED tempdir prefs file (cache reset on enter AND exit) so
        # it never touches -- or leaks a stale cache into -- the real prefs.
        tmpdir = tempfile.mkdtemp(prefix="ndprefs_h9_")
        try:
            with mock.patch.object(preferences, "PREFS_DIR", tmpdir), \
                 mock.patch.object(preferences, "PREFS_PATH",
                                   os.path.join(tmpdir, "preferences.json")):
                preferences._reset_for_tests()
                preferences.set_pref("watch_threshold_inf", False)
                big = np.zeros((50, 4, 4))
                out = _format_value(big, max_lines=5)
                line_count = out.count("\n") + 1
                self.assertLessEqual(line_count, 6)  # 5 + the "X more lines" tail
        finally:
            preferences._reset_for_tests()
            try:
                for f in os.listdir(tmpdir):
                    os.remove(os.path.join(tmpdir, f))
                os.rmdir(tmpdir)
            except Exception:
                pass

    def test_format_value_handles_nonarray_unchanged(self):
        from mpynode.ui.widgets.watch import _format_value

        self.assertEqual(_format_value(42), "42")
        self.assertEqual(_format_value("hi"), "'hi'")
        self.assertIn("'a': 1", _format_value({"a": 1}))

    def test_watch_widget_caches_mono_font(self):
        """Mono font must be cached so populate_tree can apply it per item."""
        import inspect

        from mpynode.ui.widgets.watch import NDWatchWidget

        src = inspect.getsource(NDWatchWidget.__init__)
        self.assertIn("_mono_font", src)
        self.assertIn("Monospace", src)
        self.assertIn("setWordWrap(True)", src)
        self.assertIn("setUniformRowHeights(False)", src)

    def test_populate_tree_applies_mono_font(self):
        import inspect

        from mpynode.ui.widgets.watch import NDWatchWidget

        # Applied in the in-place child-sync helper: the tree is reconciled,
        # not cleared+rebuilt.
        src = inspect.getsource(NDWatchWidget._sync_group_children)
        self.assertIn("setFont(1, self._mono_font)", src)


# ===========================================================================
# \u2014 numpy column alignment + new prefs
# ===========================================================================


class TestHotfix10NumpyAlignmentAndPrefs(unittest.TestCase):
    """Two fixes:
      1. Pass ``prefix='array('`` to ``np.array2string`` so subsequent
         rows are indented to line up under the first ``[`` (the wrap
         with ``'array(' +... + ')'`` confused numpy's auto-indent).
      2. Two new prefs (``watch_suppress_scientific``,
         ``watch_threshold_inf``) drive the formatter.

    Pref-mutating tests use the tempdir isolation pattern from
    test_phase22 so we never clobber the user's real
    ~/.mpynode/preferences.json.
    """

    def setUp(self):
        # Tempdir isolation for the prefs file (mirrors test_phase22).
        import tempfile
        from unittest import mock

        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_h10_")
        self._patches = [
            mock.patch.object(preferences, "PREFS_DIR", self._tmpdir),
            mock.patch.object(
                preferences,
                "PREFS_PATH",
                __import__("os").path.join(self._tmpdir, "preferences.json"),
            ),
        ]
        for p in self._patches:
            p.start()
        preferences._reset_for_tests()

    def tearDown(self):
        import os

        from mpynode.ui import preferences

        for p in self._patches:
            p.stop()
        preferences._reset_for_tests()
        try:
            for f in os.listdir(self._tmpdir):
                os.remove(os.path.join(self._tmpdir, f))
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def test_format_value_passes_prefix_to_array2string(self):
        """Source inspection: the formatter sets prefix='array('."""
        import inspect

        from mpynode.ui.widgets import watch as _w

        src = inspect.getsource(_w._format_value)
        self.assertIn('"prefix": "array("', src)

    def test_format_value_aligns_4x4_rows_under_first_bracket(self):
        """All matrix rows should start at the same column (just after
        ``array(``) so the columns line up visually."""
        import numpy as np
        from mpynode.ui.widgets.watch import _format_value

        m = np.eye(4)
        m[3, 0] = -5.3349
        out = _format_value(m)
        lines = out.split("\n")
        first_line = lines[0]
        first_bracket_col = first_line.index("[[")
        # Each later row starts with ``[`` one column inside the outer ``[``.
        inner_col = first_bracket_col + 1
        for ln in lines[1:]:
            if "[" not in ln:
                continue
            self.assertEqual(
                ln.find("["),
                inner_col,
                f"row {ln!r} not aligned at col {inner_col} of first row "
                f"{first_line!r}",
            )

    def test_default_prefs_for_watch_panel(self):
        """Suppress=True default ON; threshold_inf default OFF."""
        from mpynode.ui import preferences

        self.assertTrue(preferences.get_pref("watch_suppress_scientific"))
        self.assertFalse(preferences.get_pref("watch_threshold_inf"))

    def test_format_value_respects_suppress_pref(self):
        """Suppress=False yields scientific notation for tiny floats."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_suppress_scientific", False)
        preferences.set_pref("watch_threshold_inf", False)
        small = np.array([1e-9, 2.5e3, 1.0])
        out = _format_value(small)
        self.assertIn("e-", out.lower())

    def test_format_value_suppress_pref_default_hides_scientific(self):
        """Default (suppress=True) renders the same array without ``e``."""
        import numpy as np
        from mpynode.ui.widgets.watch import _format_value

        small = np.array([1e-9, 2.5e3, 1.0])
        out = _format_value(small)
        self.assertNotIn("e-", out.lower())
        self.assertNotIn("e+", out.lower())

    def test_format_value_threshold_inf_pref_disables_truncation(self):
        """Threshold_inf=True \u2192 numpy renders all elements (no '...')."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", True)
        big = np.arange(500, dtype=float)
        out = _format_value(big, max_lines=200, max_chars_per_line=10000)
        self.assertNotIn("...", out)
        self.assertIn("499.", out)

    def test_preferences_dialog_exposes_new_keys(self):
        """The Preferences dialog persists the two new keys."""
        try:
            from mpynode.ui.qt_wrapper import QWidget  # noqa: F401
        except ImportError:
            self.skipTest("Qt unavailable")
        import inspect

        from mpynode.ui.dialogs.preferences import NDPreferencesDialog

        src = inspect.getsource(NDPreferencesDialog._on_save_clicked)
        self.assertIn("watch_suppress_scientific", src)
        self.assertIn("watch_threshold_inf", src)

    # -- summarized-array change tag (Watch "stale W" bug) --------------
    # numpy summarizes arrays over ``threshold`` (200) elements to their
    # first/last 3 rows, so a change confined to the elided middle left the
    # displayed string byte-identical and the Watch tab looked frozen.
    # _format_value appends a content-sensitive tag on the summarizing path.

    def test_format_value_summarized_reflects_hidden_change(self):
        """A change in a numpy-ELIDED middle row must change the display."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", False)  # summarizing path
        a = np.zeros((300, 2))
        a[:, 1] = 1.0  # 600 elems > 200 -> numpy summarizes (first/last 3 rows)
        b = a.copy()
        b[150] = [0.5, 0.5]  # change ONLY a hidden interior row
        # the summarized bodies are identical; only the tag differs.
        self.assertNotEqual(_format_value(a), _format_value(b))

    def test_format_value_tag_distinguishes_when_stats_collide(self):
        """The tag must catch changes even when shape/min/max/mean/sum are
        all unchanged (skin weights are row-normalized, so a permutation of
        interior values keeps every summary statistic identical)."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", False)
        a = np.zeros((300, 2))
        a[:, 1] = 1.0
        b = a.copy()
        # Permute two hidden interior rows: same multiset -> same min/max/mean/
        # sum. Only a full-buffer digest distinguishes them.
        a[100] = [0.2, 0.8]
        a[101] = [0.8, 0.2]
        b[100] = [0.8, 0.2]
        b[101] = [0.2, 0.8]
        self.assertEqual(float(a.min()), float(b.min()))
        self.assertEqual(float(a.max()), float(b.max()))
        self.assertEqual(float(a.mean()), float(b.mean()))
        self.assertNotEqual(_format_value(a), _format_value(b))

    def test_format_value_no_tag_when_not_summarized(self):
        """Small (un-summarized) arrays are byte-for-byte unchanged: no tag,
        no 'shape='/'#' suffix (protects the exact-equality contracts)."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", False)
        small = np.arange(12).reshape(3, 4).astype(float)  # 12 <= 200
        out = _format_value(small)
        self.assertNotIn("shape=", out)
        self.assertNotIn("#", out)

    def test_format_value_tag_boundary_strictly_over_threshold(self):
        """numpy elides iff size > threshold(200); the tag follows exactly."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", False)
        self.assertNotIn("shape=", _format_value(np.zeros(200)))  # 200: shown
        self.assertIn("shape=", _format_value(np.zeros(201)))  # 201: elided

    def test_format_value_no_tag_when_threshold_inf(self):
        """The full-array (threshold_inf) path stays unchanged: no tag."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", True)
        out = _format_value(np.arange(500.0), max_lines=10**6,
                            max_chars_per_line=10**6)
        self.assertNotIn("shape=", out)
        self.assertNotIn("#", out)

    def test_format_value_tag_preserves_line_cap(self):
        """The tag is a same-line suffix, so it never adds a line (protects
        test_format_value_caps_long_arrays)."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", False)
        big = np.zeros((50, 4, 4))  # 800 elems, repr exceeds max_lines
        out = _format_value(big, max_lines=5)
        self.assertLessEqual(out.count("\n") + 1, 6)
        # ...and the tag survived the cap (appended to the last line).
        self.assertIn("shape=", out)

    def test_format_value_tag_never_raises(self):
        """The tag helper must never raise on the 80 ms poll: object arrays,
        all-NaN, inf, and 0-d arrays all format without throwing."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", False)
        # object dtype > 200 elems: numeric-only gate skips the tag, no raise.
        obj = np.array([object()] * 300, dtype=object)
        self.assertIsInstance(_format_value(obj), str)
        # all-NaN and inf-bearing numeric arrays: no raise, still a string.
        self.assertIsInstance(_format_value(np.full(300, np.nan)), str)
        inf_arr = np.zeros(300)
        inf_arr[7] = np.inf
        self.assertIsInstance(_format_value(inf_arr), str)
        self.assertIsInstance(_format_value(np.array(5.0)), str)  # 0-d


# ===========================================================================
# \u2014 threshold_inf disables widget cap, toggle-off
# clears values, Profile/Watch in collapsible bottom panel.
# ===========================================================================


class TestHotfix11ThresholdDisablesWidgetCap(unittest.TestCase):
    """When ``watch_threshold_inf=True`` is on, the widget-side
    max_lines / max_chars caps must also be bypassed (not just numpy's
    own threshold)."""

    def setUp(self):
        import tempfile
        from unittest import mock

        from mpynode.ui import preferences

        self._tmpdir = tempfile.mkdtemp(prefix="ndprefs_h11_")
        self._patches = [
            mock.patch.object(preferences, "PREFS_DIR", self._tmpdir),
            mock.patch.object(
                preferences,
                "PREFS_PATH",
                __import__("os").path.join(self._tmpdir, "preferences.json"),
            ),
        ]
        for p in self._patches:
            p.start()
        preferences._reset_for_tests()

    def tearDown(self):
        import os

        from mpynode.ui import preferences

        for p in self._patches:
            p.stop()
        preferences._reset_for_tests()
        try:
            for f in os.listdir(self._tmpdir):
                os.remove(os.path.join(self._tmpdir, f))
            os.rmdir(self._tmpdir)
        except Exception:
            pass

    def test_threshold_inf_bypasses_widget_max_lines(self):
        """50x4x4 array should render in full when threshold_inf=True
        even though the caller passed max_lines=12 (the default)."""
        import numpy as np
        from mpynode.ui import preferences
        from mpynode.ui.widgets.watch import _format_value

        preferences.set_pref("watch_threshold_inf", True)
        big = np.zeros((50, 4, 4))
        out = _format_value(big)
        self.assertNotIn("more lines", out)
        self.assertGreater(out.count("\n"), 100)   # 50 outer x ~4 lines


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHotfix11ToggleOffClearsValues(unittest.TestCase):
    """Toggling Watch / Profile OFF must clear the snapshot plug AND
    the widget's display so stale values don't linger."""

    def test_watch_toggled_off_clears_plug_and_tree(self):
        import inspect

        from mpynode.ui.widgets.watch import NDWatchWidget

        # OFF branch clears the snapshot plug then delegates to refresh()
        # (which empties the panel). Check both halves.
        src = inspect.getsource(NDWatchWidget._on_watch_toggled)
        self.assertIn("else:", src)
        self.assertIn("_watchVarsData", src)
        self.assertIn('type="string"', src)
        self.assertIn("self.refresh()", src)
        refreshed = inspect.getsource(NDWatchWidget.refresh)
        self.assertIn("self._cached_vars = {}", refreshed)
        self.assertIn("self._populate_tree()", refreshed)

    def test_profile_toggled_off_clears_plug_and_stats(self):
        import inspect

        from mpynode.ui.widgets.profile import NDProfileWidget

        src = inspect.getsource(NDProfileWidget._on_mode_changed)
        self.assertIn("else:", src)
        self.assertIn("_profileSnapshotData", src)
        self.assertIn('type="string"', src)
        # Stats should reset to em-dash.
        self.assertIn("\\u2014", src.encode("unicode_escape").decode())


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHotfix11CollapsibleBottomPanel(unittest.TestCase):
    """Profile + Watch live in a collapsible bottom QSplitter under
    the script editor (was: in the LEFT panel tab widget)."""

    def test_build_ui_uses_vertical_split_for_right_side(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_ui)
        # A vertical QSplitter wraps the script editor + tools.
        self.assertIn("QSplitter(Qt.Vertical", src)
        self.assertIn("self._tools_tab_widget", src)
        # Editor goes top, tools go bottom.
        editor_idx = src.find("addWidget(self._script_tab_widget)")
        tools_idx = src.find("addWidget(self._tools_tab_widget)")
        self.assertGreater(editor_idx, -1)
        self.assertGreater(tools_idx, -1)
        self.assertLess(editor_idx, tools_idx)

    def test_profile_and_watch_added_to_tools_widget_not_panel(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_ui)
        # Profile + Watch go on the tools widget, NOT the panel tabs (the old
        # code used self._panel_tab_widget.addTab for both).
        self.assertIn(
            'self._tools_tab_widget.addTab(self._profile_widget, "Profile")',
            src,
        )
        self.assertIn(
            'self._tools_tab_widget.addTab(self._watch_widget, "Watch")',
            src,
        )
        self.assertNotIn(
            "self._panel_tab_widget.addTab(self._profile_widget",
            src,
        )
        self.assertNotIn(
            "self._panel_tab_widget.addTab(self._watch_widget",
            src,
        )

    def test_right_split_collapsible_settings(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_ui)
        # NEITHER pane fully collapses (was setCollapsible(1, True)); the
        # bottom tools panel keeps a floor so the tab bar stays visible.
        self.assertIn("right_split.setCollapsible(0, False)", src)
        self.assertIn("right_split.setCollapsible(1, False)", src)
        # The floor is derived from the live tall bar, not the stale hard-coded
        # 30 which clipped the (1.5x taller) labels.
        self.assertIn("self._tools_tab_widget.setMinimumHeight(", src)
        self.assertIn("self._tools_tab_bar.sizeHint().height()", src)
        # Default sizes leave most room to editor.
        self.assertIn("right_split.setSizes(", src)


# ===========================================================================
# \u2014 watch refresh on save + connect type compat
# ===========================================================================


class TestHotfix12SaveResetsStats(unittest.TestCase):
    """After save, profile/watch stats are reset so the next compute
    writes a fresh snapshot regardless of throttle. Otherwise the
    panels can show stale values until the user scrubs the timeline."""

    def test_save_tab_calls_reset_stats(self):
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget._saveTab)
        self.assertIn("instrumentation", src)
        self.assertIn("reset_stats", src)
        # reset_stats must precede the force_one_eval CALL so the next compute
        # writes at count=1. rfind skips an earlier docstring mention of it.
        reset_idx = src.find("reset_stats(node_obj)")
        force_idx = src.rfind("force_one_eval(py_node)")
        self.assertGreater(reset_idx, -1)
        self.assertGreater(force_idx, -1)
        self.assertLess(reset_idx, force_idx)


class TestHotfix12TypeCompatibility(unittest.TestCase):
    """Type compatibility helper: only show plugs that can DG-connect
    to the target attr's type."""

    def test_scalars_interconvert(self):
        from mpynode.ui.dialogs.connect_attr import _type_compatible

        for t1 in (
            "float",
            "double",
            "long",
            "bool",
            "doubleLinear",
            "doubleAngle",
            "time",
            "enum",
        ):
            for t2 in ("float", "double", "long", "bool"):
                self.assertTrue(
                    _type_compatible(t1, t2),
                    f"{t1} should be compatible with {t2}",
                )

    def test_vector3_compounds_match_each_other(self):
        from mpynode.ui.dialogs.connect_attr import _type_compatible

        self.assertTrue(_type_compatible("float3", "double3"))
        self.assertTrue(_type_compatible("double3", "float3"))
        self.assertTrue(_type_compatible("float3", "float3"))

    def test_vector3_and_scalar_do_not_match(self):
        """Critical: a float input must NOT show compound translate as
        a candidate (per user's bug report)."""
        from mpynode.ui.dialogs.connect_attr import _type_compatible

        self.assertFalse(_type_compatible("float", "float3"))
        self.assertFalse(_type_compatible("double", "double3"))
        self.assertFalse(_type_compatible("float3", "float"))

    def test_matrix_only_matches_matrix(self):
        from mpynode.ui.dialogs.connect_attr import _type_compatible

        self.assertTrue(_type_compatible("matrix", "matrix"))
        self.assertFalse(_type_compatible("matrix", "float3"))
        self.assertFalse(_type_compatible("matrix", "float"))
        self.assertFalse(_type_compatible("matrix", "double3"))

    def test_typed_data_strict(self):
        from mpynode.ui.dialogs.connect_attr import _type_compatible

        self.assertTrue(_type_compatible("mesh", "mesh"))
        self.assertFalse(_type_compatible("mesh", "nurbsCurve"))
        self.assertFalse(_type_compatible("mesh", "nurbsSurface"))
        self.assertFalse(_type_compatible("mesh", "string"))

    def test_unknown_type_is_permissive(self):
        """When at least one type is uncategorized we don't filter the
        plug out \u2014 better to show too much than hide a candidate the
        user actually wants."""
        from mpynode.ui.dialogs.connect_attr import _type_compatible

        self.assertTrue(_type_compatible("", "float"))
        self.assertTrue(_type_compatible("float", ""))
        self.assertTrue(_type_compatible("weirdtype", "float"))
        self.assertTrue(_type_compatible("float", "weirdtype"))


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHotfix12ConnectDialogCompatToggle(unittest.TestCase):
    """The connect dialog has a new ``Filter by compatible type``
    checkbox driven by a pref (default ON)."""

    def test_default_pref_is_true(self):
        import tempfile
        from unittest import mock

        from mpynode.ui import preferences

        tmpdir = tempfile.mkdtemp(prefix="ndprefs_h12_")
        try:
            with (
                mock.patch.object(preferences, "PREFS_DIR", tmpdir),
                mock.patch.object(
                    preferences,
                    "PREFS_PATH",
                    __import__("os").path.join(tmpdir, "preferences.json"),
                ),
            ):
                preferences._reset_for_tests()
                self.assertTrue(
                    preferences.get_pref("connect_dialog_filter_by_type_default")
                )
        finally:
            import os

            # CRITICAL: the ``with`` loaded the cache from the tmp prefs (bare
            # defaults) and PREFS_PATH is now the REAL one, so drop that stale
            # cache -- else a later non-isolated ``set_pref`` flushes bare
            # defaults over the user's real preferences.json.
            preferences._reset_for_tests()
            try:
                for f in os.listdir(tmpdir):
                    os.remove(os.path.join(tmpdir, f))
                os.rmdir(tmpdir)
            except Exception:
                pass

    def test_dialog_source_has_compat_check(self):
        import inspect

        from mpynode.ui.dialogs import connect_attr as _ca

        src = inspect.getsource(_ca._BaseConnectDialog._build_ui)
        self.assertIn("self._compat_check", src)
        self.assertIn("connect_dialog_filter_by_type_default", src)
        self.assertIn("Filter by compatible type", src)

    def test_populate_tree_filters_by_compat(self):
        import inspect

        from mpynode.ui.dialogs import connect_attr as _ca

        src = inspect.getsource(_ca._BaseConnectDialog._populate_tree)
        self.assertIn("_resolve_target_attr_type", src)
        self.assertIn("_type_compatible", src)
        self.assertIn("self._compat_check", src)


class TestWatchColumnWidth(unittest.TestCase):
    """The Value column gets a wider STATIC default; there is no dynamic
    per-update resizing (which crashed Maya during real-time watch)."""

    def test_value_column_wider_default(self):
        import inspect
        from mpynode.ui.widgets.watch import NDWatchWidget

        src = inspect.getsource(NDWatchWidget.__init__)
        self.assertIn("setColumnWidth(1, 320)", src)

    def test_no_dynamic_autosize(self):
        import inspect
        from mpynode.ui.widgets.watch import NDWatchWidget

        cls_src = inspect.getsource(NDWatchWidget)
        self.assertNotIn("_autosize_columns", cls_src)
        self.assertNotIn("_compute_column_widths", cls_src)
        self.assertNotIn("def resizeEvent", cls_src)


class TestPrefsIsolationRegression(unittest.TestCase):
    """Regression: no pref-mutating test in this module may persist to the
    real ~/.mpynode/preferences.json.

    The leak: an inline ``PREFS_PATH`` patch reset the cache INSIDE the
    ``with`` block but not after it, so on exit a stale, tmp-loaded,
    defaults-only cache stayed bound to the restored (real) path. A later
    ordinary ``set_pref`` then flushed those bare defaults over the real file,
    silently wiping user settings (e.g. the AI provider). This runs the
    formerly-leaking class under a SANDBOX 'real' prefs file (never the user's)
    and asserts a seeded sentinel survives a subsequent write.
    """

    def test_inline_pref_patch_does_not_clobber_real_prefs(self):
        import json
        import os
        import tempfile
        from unittest import mock

        from mpynode.ui import preferences

        sandbox = tempfile.mkdtemp(prefix="nd_realprefs_")
        sandbox_path = os.path.join(sandbox, "preferences.json")
        try:
            with mock.patch.object(preferences, "PREFS_DIR", sandbox), \
                 mock.patch.object(preferences, "PREFS_PATH", sandbox_path):
                preferences._reset_for_tests()
                preferences.set_pref("SENTINEL_REAL_PREF", "keep")

                # Run the class whose inline PREFS_PATH patch used to leak a
                # stale cache; its writes hit the sandbox.
                suite = unittest.TestLoader().loadTestsFromName(
                    "%s.TestHotfix12ConnectDialogCompatToggle" % __name__)
                with open(os.devnull, "w") as devnull:
                    unittest.TextTestRunner(stream=devnull, verbosity=0).run(
                        suite)

                # The flush: an ordinary write. A leaked stale cache would
                # persist bare defaults here, dropping the sentinel.
                preferences.set_pref("probe_after", True)
                with open(sandbox_path) as fh:
                    data = json.load(fh)
            self.assertEqual(
                data.get("SENTINEL_REAL_PREF"), "keep",
                "an inline PREFS_PATH patch leaked a stale cache; a later "
                "set_pref clobbered the (sandbox stand-in for the) real prefs "
                "file")
        finally:
            preferences._reset_for_tests()
            try:
                for f in os.listdir(sandbox):
                    os.remove(os.path.join(sandbox, f))
                os.rmdir(sandbox)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
