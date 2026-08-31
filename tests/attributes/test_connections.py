"""Connect/disconnect commands, multi-attr index routing, callbacks, connect-attr dialog, panel refresh, multi-contract, mpy-constraint

Consolidated from: test_disconnect_all_multi.py, test_output_multi_connect_index.py, test_output_multi_write_index.py, test_connection_callback.py, test_phase18_6.py, test_attr_panel_refresh_on_connect.py, test_phase18_5.py, test_phase06.py.
"""

from __future__ import annotations

# ===================== from test_disconnect_all_multi.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__disconnect_all_multi():
    standalone_init()


class TestDisconnectAllMulti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def _n_out(self, plug):
        return len(
            mc.listConnections(plug, source=False, destination=True, plugs=True) or []
        )

    def _n_in(self, plug):
        return len(
            mc.listConnections(plug, source=True, destination=False, plugs=True) or []
        )

    def test_disconnect_all_multi_output(self):
        """A multi OUTPUT wired at offset element indices [5,6,7] must be
        fully disconnected."""
        from mpynode._base.commands import _DisconnectAllCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        node = MPyNode.create(name="emit")
        node.add_output_attr("pts", "vector", is_array=True)
        node.set_compute_expression(
            "self.pts = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]\n"
        )
        plug = node.get_name() + ".pts"
        dsts = [mc.createNode("transform", name="d%d" % i) for i in range(3)]
        for k, idx in enumerate((5, 6, 7)):
            mc.connectAttr("%s[%d]" % (plug, idx), dsts[k] + ".translate", force=True)
        self.assertEqual(self._n_out(plug), 3)
        run_undoable(_DisconnectAllCommand(plug, "output"))
        self.assertEqual(self._n_out(plug), 0)

    def test_disconnect_all_multi_input(self):
        """A multi INPUT wired from N drivers must be fully disconnected."""
        from mpynode._base.commands import _DisconnectAllCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        node = MPyNode.create(name="recv")
        # A "collector" multi input. All multis are indexMatters=True (Maya
        # default); nextAvailable picks the next free index, so N drivers
        # give N elements.
        node.add_input_attr("inv", "vector", is_array=True)
        plug = node.get_name() + ".inv"
        srcs = [mc.createNode("transform", name="s%d" % i) for i in range(3)]
        for i, s in enumerate(srcs):
            mc.connectAttr(s + ".translate", "%s[%d]" % (plug, i), force=True)
        self.assertEqual(self._n_in(plug), 3)
        run_undoable(_DisconnectAllCommand(plug, "input"))
        self.assertEqual(self._n_in(plug), 0)

    def test_disconnect_all_scalar_still_works(self):
        """Regression guard: scalar disconnect (the path that already
        worked) must keep working."""
        from mpynode._base.commands import _DisconnectAllCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        node = MPyNode.create(name="scal")
        node.add_input_attr("k", "float")
        plug = node.get_name() + ".k"
        src = mc.createNode("transform", name="drv")
        mc.connectAttr(src + ".translateX", plug, force=True)
        self.assertEqual(self._n_in(plug), 1)
        run_undoable(_DisconnectAllCommand(plug, "input"))
        self.assertEqual(self._n_in(plug), 0)


# ===================== from test_output_multi_connect_index.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__output_multi_connect_index():
    standalone_init()


# 5 deterministic non-zero points, written unconditionally (no ``evaluate``
# gate) -- mirrors pointNoise, whose ungated compute cached elements before
# the cubes were wired.
_COMPUTE = (
    "self.points = [[float(i + 1), float(i + 1) * 2.0, float(i + 1) * 3.0] "
    "for i in range(5)]\n"
)


class TestOutputMultiConnectIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="noiseEmitter")
        self.node.add_output_attr("points", "vector", is_array=True)
        self.node.set_compute_expression(_COMPUTE)
        self.plug = self.node.get_name() + ".points"
        # One eval caches 5 elements at logical [0..4] -- the buggy state.
        mc.getAttr("%s[0]" % self.plug)

    def test_eval_caches_elements_at_logical_zero(self):
        """Sanity: compute populates logical indices [0..4]."""
        idx = sorted(mc.getAttr(self.plug, multiIndices=True) or [])
        self.assertEqual(idx, [0, 1, 2, 3, 4])

    def test_old_next_available_skips_the_cached_data(self):
        """Documents the BUGGY behavior: ``_next_available_multi_index``
        returns max(existing data index)+1 == 5, i.e. it would wire past
        the data region."""
        from mpynode.ui.dialogs.connect_attr import _next_available_multi_index

        self.assertEqual(_next_available_multi_index(self.plug), 5)

    def test_next_available_source_index_starts_at_zero(self):
        """THE FIX: an output with cached data but no outgoing source
        connections is wired starting at index 0."""
        from mpynode.ui.dialogs.connect_attr import _next_available_source_index

        self.assertEqual(_next_available_source_index(self.plug), 0)

    def test_output_pairs_drive_from_data_indices(self):
        """``compute_output_connection_pairs`` maps each destination to a
        data-bearing source element starting at 0."""
        from mpynode.ui.dialogs.connect_attr import compute_output_connection_pairs

        t1 = mc.createNode("transform", name="dst1")
        t2 = mc.createNode("transform", name="dst2")
        t3 = mc.createNode("transform", name="dst3")
        dests = [t1 + ".translate", t2 + ".translate", t3 + ".translate"]
        pairs = compute_output_connection_pairs(self.plug, True, dests)
        self.assertEqual(
            pairs,
            [
                ("%s[0]" % self.plug, t1 + ".translate"),
                ("%s[1]" % self.plug, t2 + ".translate"),
                ("%s[2]" % self.plug, t3 + ".translate"),
            ],
        )

    def test_end_to_end_transforms_receive_computed_values(self):
        """The user-visible bug: wiring then evaluating must move the
        transforms off their (0,0,0) default."""
        from mpynode.ui.dialogs.connect_attr import compute_output_connection_pairs

        t1 = mc.createNode("transform", name="cube1")
        t2 = mc.createNode("transform", name="cube2")
        dests = [t1 + ".translate", t2 + ".translate"]
        pairs = compute_output_connection_pairs(self.plug, True, dests)
        for src, dst in pairs:
            mc.connectAttr(src, dst, force=True)
        # Re-pull so the freshly-connected elements are computed.
        mc.dgdirty(self.node.get_name())
        self.assertEqual(list(mc.getAttr(t1 + ".translate")[0]), [1.0, 2.0, 3.0])
        self.assertEqual(list(mc.getAttr(t2 + ".translate")[0]), [2.0, 4.0, 6.0])

    def test_incremental_connect_continues_after_existing_sources(self):
        """A second wiring operation continues past already-wired source
        indices (so distinct destinations get distinct data elements)."""
        from mpynode.ui.dialogs.connect_attr import (
            _next_available_source_index,
            compute_output_connection_pairs,
        )

        t1 = mc.createNode("transform", name="firstA")
        t2 = mc.createNode("transform", name="firstB")
        pairs = compute_output_connection_pairs(
            self.plug, True, [t1 + ".translate", t2 + ".translate"]
        )
        for src, dst in pairs:
            mc.connectAttr(src, dst, force=True)
        # [0] and [1] now drive something -> next source index is 2.
        self.assertEqual(_next_available_source_index(self.plug), 2)


# ===================== from test_output_multi_write_index.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__output_multi_write_index():
    standalone_init()


# Three non-zero points, assigned as a full REPLACEMENT (mirrors pointNoise),
# so the pre-sized buffer is discarded and the written sequence is len 3.
_COMPUTE_3 = (
    "self.points = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]\n"
)


class TestOutputMultiWriteIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def _make_node(self, name, compute=_COMPUTE_3):
        from mpynode.wrappers._mpy_node import MPyNode

        node = MPyNode.create(name=name)
        node.add_output_attr("points", "vector", is_array=True)
        node.set_compute_expression(compute)
        return node, node.get_name() + ".points"

    def test_offset_connected_output_drives_consumers(self):
        """THE BUG: output wired at logical [5,6,7] (offset past cached
        data). Each consumer must receive its value, not (0,0,0)."""
        mc.file(new=True, force=True)
        node, plug = self._make_node("offsetEmitter")
        t1 = mc.createNode("transform", name="c1")
        t2 = mc.createNode("transform", name="c2")
        t3 = mc.createNode("transform", name="c3")
        mc.connectAttr("%s[5]" % plug, t1 + ".translate", force=True)
        mc.connectAttr("%s[6]" % plug, t2 + ".translate", force=True)
        mc.connectAttr("%s[7]" % plug, t3 + ".translate", force=True)
        mc.dgdirty(node.get_name())
        self.assertEqual(list(mc.getAttr(t1 + ".translate")[0]), [1.0, 2.0, 3.0])
        self.assertEqual(list(mc.getAttr(t2 + ".translate")[0]), [4.0, 5.0, 6.0])
        self.assertEqual(list(mc.getAttr(t3 + ".translate")[0]), [7.0, 8.0, 9.0])

    def test_contiguous_from_zero_unchanged(self):
        """No regression: an output wired contiguously from 0 still drives
        its consumers (the spherePointDistributor case)."""
        mc.file(new=True, force=True)
        node, plug = self._make_node("zeroEmitter")
        t1 = mc.createNode("transform", name="z1")
        t2 = mc.createNode("transform", name="z2")
        t3 = mc.createNode("transform", name="z3")
        mc.connectAttr("%s[0]" % plug, t1 + ".translate", force=True)
        mc.connectAttr("%s[1]" % plug, t2 + ".translate", force=True)
        mc.connectAttr("%s[2]" % plug, t3 + ".translate", force=True)
        mc.dgdirty(node.get_name())
        self.assertEqual(list(mc.getAttr(t1 + ".translate")[0]), [1.0, 2.0, 3.0])
        self.assertEqual(list(mc.getAttr(t2 + ".translate")[0]), [4.0, 5.0, 6.0])
        self.assertEqual(list(mc.getAttr(t3 + ".translate")[0]), [7.0, 8.0, 9.0])

    def test_unconnected_output_writes_positionally(self):
        """Watch-only / pre-wire eval: no outgoing connections -> write to
        positional [0..len-1] so Watch can read the values."""
        mc.file(new=True, force=True)
        node, plug = self._make_node("watchEmitter")
        mc.getAttr("%s[0]" % plug)  # force one eval
        idx = sorted(mc.getAttr(plug, multiIndices=True) or [])
        self.assertEqual(idx, [0, 1, 2])
        self.assertEqual(list(mc.getAttr("%s[0]" % plug)[0]), [1.0, 2.0, 3.0])
        self.assertEqual(list(mc.getAttr("%s[2]" % plug)[0]), [7.0, 8.0, 9.0])

    def test_fewer_values_than_connections_drives_leading_consumers(self):
        """The python-scene case: 2 computed values but 3 offset
        connections [5,6,7]. value k -> source k; the trailing connection
        with no value is left at its default (one extra cube unavoidably
        undriven), the others move."""
        mc.file(new=True, force=True)
        compute = "self.points = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]\n"
        node, plug = self._make_node("fewerEmitter", compute=compute)
        t1 = mc.createNode("transform", name="f1")
        mc.connectAttr("%s[5]" % plug, t1 + ".translate", force=True)
        t2 = mc.createNode("transform", name="f2")
        mc.connectAttr("%s[6]" % plug, t2 + ".translate", force=True)
        t3 = mc.createNode("transform", name="f3")
        mc.connectAttr("%s[7]" % plug, t3 + ".translate", force=True)
        mc.dgdirty(node.get_name())
        self.assertEqual(list(mc.getAttr(t1 + ".translate")[0]), [1.0, 2.0, 3.0])
        self.assertEqual(list(mc.getAttr(t2 + ".translate")[0]), [4.0, 5.0, 6.0])
        # third connection has no value -> stays at default
        self.assertEqual(list(mc.getAttr(t3 + ".translate")[0]), [0.0, 0.0, 0.0])

    def test_count_mismatch_falls_back_to_positional(self):
        """If the written count != number of outgoing connections (e.g. an
        in-place pre-sized buffer write), fall back to positional so a
        connection inside [0..len-1] is still covered."""
        mc.file(new=True, force=True)
        # 8 values, but only 3 connections at [5,6,7]: positional [0..7]
        # covers logical 5,6,7 -> consumers get value rows 5,6,7.
        compute = (
            "self.points = [[float(i), float(i) * 10.0, float(i) * 100.0] "
            "for i in range(8)]\n"
        )
        node, plug = self._make_node("mismatchEmitter", compute=compute)
        t1 = mc.createNode("transform", name="m1")
        mc.connectAttr("%s[5]" % plug, t1 + ".translate", force=True)
        t2 = mc.createNode("transform", name="m2")
        mc.connectAttr("%s[6]" % plug, t2 + ".translate", force=True)
        t3 = mc.createNode("transform", name="m3")
        mc.connectAttr("%s[7]" % plug, t3 + ".translate", force=True)
        mc.dgdirty(node.get_name())
        # value row 5 == [5, 50, 500] lands at logical element [5] -> t1
        self.assertEqual(list(mc.getAttr(t1 + ".translate")[0]), [5.0, 50.0, 500.0])
        self.assertEqual(list(mc.getAttr(t2 + ".translate")[0]), [6.0, 60.0, 600.0])
        self.assertEqual(list(mc.getAttr(t3 + ".translate")[0]), [7.0, 70.0, 700.0])


# ===================== from test_connection_callback.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__connection_callback():
    standalone_init()


class TestConnectionCallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def test_fires_on_connect_and_disconnect(self):
        from mpynode._base.node_callbacks import (
            install_node_connection_callback,
            remove_callback,
        )

        mc.file(new=True, force=True)
        mc.createNode("transform", name="watched")
        mc.createNode("transform", name="driver")
        fired = []
        cb = install_node_connection_callback(
            "watched", lambda plug: fired.append(plug.name())
        )
        try:
            mc.connectAttr("driver.translateX", "watched.translateX", force=True)
            after_connect = len(fired)
            mc.disconnectAttr("driver.translateX", "watched.translateX")
            after_disconnect = len(fired)
        finally:
            remove_callback(cb)
        self.assertGreaterEqual(after_connect, 1)
        self.assertGreater(after_disconnect, after_connect)

    def test_ignores_plain_setattr(self):
        from mpynode._base.node_callbacks import (
            install_node_connection_callback,
            remove_callback,
        )

        mc.file(new=True, force=True)
        mc.createNode("transform", name="w2")
        fired = []
        cb = install_node_connection_callback(
            "w2", lambda plug: fired.append(plug.name())
        )
        try:
            mc.setAttr("w2.translateY", 5.0)  # plain value set, no connection
        finally:
            remove_callback(cb)
        self.assertEqual(fired, [])


# ===================== from test_phase18_6.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase18_6():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Filter helper (pure function). EXACT match against the attribute name unless
# a wildcard metachar is present; glob (*? [) matches the full ``node.attr``.
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestFilterMatches(unittest.TestCase):
    def test_empty_filter_matches_all(self):
        from mpynode.ui.dialogs.connect_attr import _filter_matches

        for s in ("pCube1.translate", "pCube1.translateX", "pCube1.visibility"):
            self.assertTrue(_filter_matches(s, ""))

    def test_no_wildcard_requires_exact_attr_name_match(self):
        """typing without wildcard requires EXACT match
        against the attribute name (last segment after ``.``)."""
        from mpynode.ui.dialogs.connect_attr import _filter_matches

        # Exact match \u2014 succeeds.
        self.assertTrue(_filter_matches("pCube1.translate", "translate"))
        self.assertTrue(_filter_matches("pCube2.translate", "translate"))
        # Substring match \u2014 fails (no wildcard, must be exact).
        self.assertFalse(_filter_matches("pCube1.translateX", "translate"))
        self.assertFalse(_filter_matches("pCube1.translateX", "trans"))
        # Node-name partial \u2014 fails (must match attr name, not node).
        self.assertFalse(_filter_matches("pCube1.translate", "pCube"))
        self.assertFalse(_filter_matches("pCube1.translate", "cube"))

    def test_no_wildcard_exact_match_is_case_insensitive(self):
        from mpynode.ui.dialogs.connect_attr import _filter_matches

        self.assertTrue(_filter_matches("pCube1.Translate", "translate"))
        self.assertTrue(_filter_matches("pCube1.translate", "TRANSLATE"))
        # Still must be exact (different attr).
        self.assertFalse(_filter_matches("pCube1.TranslateX", "translate"))

    def test_glob_metachar_activates_fnmatch(self):
        """When the filter contains ``*? [`` we switch to fnmatch
        against the FULL ``node.attr`` string."""
        from mpynode.ui.dialogs.connect_attr import _filter_matches

        self.assertTrue(_filter_matches("pCube1.translate", "*translate"))
        self.assertTrue(_filter_matches("pCube1.translateX", "*translate*"))
        self.assertTrue(_filter_matches("pCube1.translate", "pcube1.*"))
        self.assertTrue(_filter_matches("pCube1.translateX", "pcube?.t*"))
        self.assertFalse(_filter_matches("pCube1.translate", "*sphere*"))
        # ``*term*`` mimics the OLD substring behaviour.
        self.assertTrue(_filter_matches("pCube1.translateX", "*trans*"))

    def test_pivot_substring_no_longer_matches_without_wildcard(self):
        """sanity check: typing ``pivot`` without a wildcard
        no longer matches ``rotatePivotTranslate`` even if pivots are
        unhidden. User must use ``*pivot*`` for substring matching."""
        from mpynode.ui.dialogs.connect_attr import _filter_matches

        self.assertFalse(_filter_matches("pCube1.rotatePivotTranslate", "pivot"))
        self.assertTrue(_filter_matches("pCube1.rotatePivotTranslate", "*pivot*"))


# ===========================================================================
# Pivot / limit detection helper
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestPivotLimitDetection(unittest.TestCase):
    def test_detects_rotate_pivot_family(self):
        from mpynode.ui.dialogs.connect_attr import _is_pivot_or_limit

        for n in (
            "rotatePivot",
            "rotatePivotX",
            "rotatePivotTranslate",
            "rotatePivotTranslateX",
        ):
            self.assertTrue(_is_pivot_or_limit(n), n)

    def test_detects_scale_pivot_family(self):
        from mpynode.ui.dialogs.connect_attr import _is_pivot_or_limit

        for n in (
            "scalePivot",
            "scalePivotX",
            "scalePivotTranslate",
            "scalePivotTranslateZ",
        ):
            self.assertTrue(_is_pivot_or_limit(n), n)

    def test_detects_limit_family(self):
        from mpynode.ui.dialogs.connect_attr import _is_pivot_or_limit

        for n in (
            "minRotXLimit",
            "maxRotZLimit",
            "minTransLimitEnable",
            "minScaleLimit",
        ):
            self.assertTrue(_is_pivot_or_limit(n), n)

    def test_keeps_legitimate_attrs(self):
        from mpynode.ui.dialogs.connect_attr import _is_pivot_or_limit

        for n in ("translate", "translateX", "rotate", "scaleY", "visibility"):
            self.assertFalse(_is_pivot_or_limit(n), n)


# ===========================================================================
# Candidate-attr enumeration (settable-always + hide_pivots flag)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestListCandidatePlugs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_default_includes_compound_parents(self):
        """The keyable-only default was hiding compound
        parents like ``translate``. The new settable-only path includes
        them."""
        from mpynode.ui.dialogs.connect_attr import _list_candidate_plugs

        cube = mc.polyCube(name="cmpd")[0]
        mc.select(cube, replace=True)
        rows = _list_candidate_plugs()  # hide_pivots=True (default)
        attr_names = {r[1] for r in rows}

        # compound parents AND their children.
        self.assertIn("translate", attr_names)
        self.assertIn("rotate", attr_names)
        self.assertIn("scale", attr_names)
        self.assertIn("translateX", attr_names)
        self.assertIn("rotateY", attr_names)
        self.assertIn("scaleZ", attr_names)
        self.assertIn("visibility", attr_names)

    def test_default_hides_pivots(self):
        """Hide_pivots default ON strips the pivot/limit noise."""
        from mpynode.ui.dialogs.connect_attr import _list_candidate_plugs

        cube = mc.polyCube(name="hidep")[0]
        mc.select(cube, replace=True)
        rows = _list_candidate_plugs()  # hide_pivots=True (default)
        attr_names = {r[1] for r in rows}

        # pivot families and limits filtered out.
        self.assertNotIn("rotatePivotTranslate", attr_names)
        self.assertNotIn("scalePivotTranslate", attr_names)
        self.assertNotIn("rotatePivotTranslateX", attr_names)
        self.assertNotIn("minRotXLimit", attr_names)
        self.assertNotIn("maxScaleLimit", attr_names)

    def test_hide_pivots_off_includes_pivots(self):
        """``hide_pivots=False`` shows the full settable surface."""
        from mpynode.ui.dialogs.connect_attr import _list_candidate_plugs

        cube = mc.polyCube(name="showp")[0]
        mc.select(cube, replace=True)
        rows = _list_candidate_plugs(hide_pivots=False)
        attr_names = {r[1] for r in rows}

        self.assertIn("rotatePivotTranslate", attr_names)
        self.assertIn("scalePivotTranslate", attr_names)
        self.assertIn("translate", attr_names)
        self.assertIn("translateX", attr_names)


# ===========================================================================
# Sort logic (pure functions, no Qt instantiation)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestSortRows(unittest.TestCase):
    def _rows(self):
        # Mixed types and node-name numbering to exercise natural sort.
        return [
            ("pCube10", "translate", "double3"),
            ("pCube2", "rotate", "double3"),
            ("pCube1", "visibility", "bool"),
            ("pCube1", "translateX", "doubleLinear"),
            ("pSphere1", "worldMatrix", "matrix"),
            ("pCube1", "label", "string"),
        ]

    def test_selection_mode_preserves_order(self):
        from mpynode.ui.dialogs.connect_attr import _sort_rows

        rows = self._rows()
        out = _sort_rows(rows, "selection")
        self.assertEqual(out, rows)

    def test_natural_asc_handles_numeric_node_names(self):
        from mpynode.ui.dialogs.connect_attr import _sort_rows

        out = _sort_rows(self._rows(), "natural_asc")
        nodes = [r[0] for r in out]
        # pCube1 < pCube2 < pCube10 < pSphere1 (natsort respects the
        # numeric component, which string sort would get wrong).
        self.assertEqual(
            nodes, ["pCube1", "pCube1", "pCube1", "pCube2", "pCube10", "pSphere1"]
        )

    def test_natural_desc_reverses(self):
        from mpynode.ui.dialogs.connect_attr import _sort_rows

        out = _sort_rows(self._rows(), "natural_desc")
        nodes = [r[0] for r in out]
        self.assertEqual(nodes[0], "pSphere1")

    def test_type_alpha_groups_same_types(self):
        from mpynode.ui.dialogs.connect_attr import _sort_rows

        out = _sort_rows(self._rows(), "type_alpha_asc")
        types = [r[2] for r in out]
        # Adjacent rows should share a type when grouped alpha-asc.
        # bool < double3 < doubleLinear < matrix < string
        self.assertEqual(
            types,
            ["bool", "double3", "double3", "doubleLinear", "matrix", "string"],
        )

    def test_type_category_puts_compounds_first(self):
        from mpynode.ui.dialogs.connect_attr import _sort_rows

        out = _sort_rows(self._rows(), "type_category")
        types = [r[2] for r in out]
        # double3 (cat 0) before matrix (cat 1) before doubleLinear (cat 3)
        # before bool (cat 4) before string (cat 6).
        self.assertEqual(types[0], "double3")
        self.assertEqual(types[1], "double3")
        self.assertEqual(types[2], "matrix")
        self.assertEqual(types[3], "doubleLinear")
        self.assertEqual(types[4], "bool")
        self.assertEqual(types[5], "string")


# ===========================================================================
# Type-category bucketing helper
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestTypeCategoryKey(unittest.TestCase):
    def test_compound_vectors_first(self):
        from mpynode.ui.dialogs.connect_attr import _type_category_key

        self.assertLess(_type_category_key("double3"), _type_category_key("matrix"))
        self.assertLess(_type_category_key("double3"), _type_category_key("double"))
        self.assertLess(_type_category_key("float3"), _type_category_key("string"))

    def test_matrices_after_vectors(self):
        from mpynode.ui.dialogs.connect_attr import _type_category_key

        self.assertLess(
            _type_category_key("matrix"), _type_category_key("doubleLinear")
        )

    def test_unknown_type_goes_last(self):
        from mpynode.ui.dialogs.connect_attr import _type_category_key

        self.assertGreater(
            _type_category_key("weirdCustomType"),
            _type_category_key("string"),
        )


# ===========================================================================
# Dialog UI shape (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestConnectDialogPhase18_6(unittest.TestCase):
    def test_hide_pivots_checkbox_present(self):
        """replaces ``Show all attrs`` checkbox."""
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        src = inspect.getsource(_BaseConnectDialog._build_ui)
        self.assertIn("_hide_pivots_check", src)
        self.assertIn("Hide pivots & limits", src)

    def test_populate_tree_uses_hide_pivots_flag(self):
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        src = inspect.getsource(_BaseConnectDialog._populate_tree)
        self.assertIn("_hide_pivots_check.isChecked()", src)
        self.assertIn("hide_pivots=", src)

    def test_populate_tree_presizes_node_attr_column(self):
        """Col 0 (Node.Attr) is auto-sized to its widest entry on populate."""
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        src = inspect.getsource(_BaseConnectDialog._populate_tree)
        self.assertIn("resizeColumnToContents(0)", src)

    def test_filter_uses_full_node_attr_match(self):
        """Filter matches against the full node.attr string."""
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        src = inspect.getsource(_BaseConnectDialog._apply_filter)
        # Pulls full node.attr from UserRole + 1 + uses _filter_matches.
        self.assertIn("UserRole + 1", src)
        self.assertIn("_filter_matches", src)

    def test_header_click_sort_wired(self):
        """Clickable column headers cycle through sort modes."""
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        self.assertTrue(
            callable(getattr(_BaseConnectDialog, "_on_header_clicked", None))
        )
        # Build must ALSO enable clickable sections: setSortingEnabled(False)
        # defaults sectionsClickable to False, so the live UI fires nothing.
        src = inspect.getsource(_BaseConnectDialog._build_ui)
        self.assertIn("sectionClicked", src)
        self.assertIn("_on_header_clicked", src)
        self.assertIn(
            "setSectionsClickable(True)",
            src,
            "header().setSectionsClickable(True) is REQUIRED whenever "
            "setSortingEnabled(False) \u2014 otherwise sectionClicked never "
            "fires in live Qt (the click is swallowed). Caught in interactive "
            "Maya during review.",
        )

    def test_header_click_cycles_sort_mode(self):
        """End-to-end: clicking column 1 cycles type-sort modes; clicking
        column 0 resets to selection mode. Uses real QApplication."""
        try:
            from mpynode.ui.qt_wrapper import QApplication  # noqa: F401
        except ImportError:
            self.skipTest("QApplication unavailable")
        # Build offscreen QApp.
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PySide2.QtWidgets import QApplication
        import sys

        app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841

        from mpynode.ui.dialogs.connect_attr import (
            _BaseConnectDialog,
            _NODE_SORT_MODES,
            _TYPE_SORT_MODES,
        )

        dlg = _BaseConnectDialog(
            parent=None, target_plug="m.in", target_is_multi=False, title="t"
        )
        # sectionsClickable must be True or live clicks are swallowed.
        self.assertTrue(dlg._tree.header().sectionsClickable())

        # Initial mode comes from prefs (default 'selection' on col 0).
        self.assertEqual(dlg._sort_col, 0)
        # Click col 1 -> first type mode.
        dlg._tree.header().sectionClicked.emit(1)
        self.assertEqual(dlg._sort_col, 1)
        self.assertEqual(dlg._sort_mode, _TYPE_SORT_MODES[0])
        # Click col 1 again -> second type mode.
        dlg._tree.header().sectionClicked.emit(1)
        self.assertEqual(dlg._sort_mode, _TYPE_SORT_MODES[1])
        # Third click -> third mode.
        dlg._tree.header().sectionClicked.emit(1)
        self.assertEqual(dlg._sort_mode, _TYPE_SORT_MODES[2])
        # Fourth click wraps back.
        dlg._tree.header().sectionClicked.emit(1)
        self.assertEqual(dlg._sort_mode, _TYPE_SORT_MODES[0])
        # Click col 0 -> resets to col 0's first mode.
        dlg._tree.header().sectionClicked.emit(0)
        self.assertEqual(dlg._sort_col, 0)
        self.assertEqual(dlg._sort_mode, _NODE_SORT_MODES[0])
        dlg.deleteLater()


# ===========================================================================
# Node menu actions (Select Node + Add Attribute)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestNodeMenuActions(unittest.TestCase):
    def test_select_node_method_present(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "selectCurrentNodeInScene"))
        self.assertTrue(callable(NDMainWindow.selectCurrentNodeInScene))

    def test_add_attribute_method_present(self):
        from mpynode.ui.mpynode_designer import NDMainWindow

        self.assertTrue(hasattr(NDMainWindow, "showAddAttributeDialog"))
        self.assertTrue(callable(NDMainWindow.showAddAttributeDialog))

    def test_select_node_uses_cmds_select(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.selectCurrentNodeInScene)
        self.assertIn("mc.select", src)
        self.assertIn("self._current_node", src)

    def test_add_attribute_opens_NDAddAttrDialog(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.showAddAttributeDialog)
        self.assertIn("NDAddAttrDialog", src)
        self.assertIn("self._current_node", src)
        # Persistent (cached on _menu_add_attr_dlg)
        self.assertIn("_menu_add_attr_dlg", src)

    def test_setCurrentNode_tracks_current_node(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.setCurrentNode)
        self.assertIn("self._current_node = py_node", src)

    def test_menu_bar_wires_both_actions(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._build_menu_bar)
        self.assertIn("Select Node in Scene", src)
        self.assertIn("Add Attribute", src)
        self.assertIn("selectCurrentNodeInScene", src)
        self.assertIn("showAddAttributeDialog", src)

    def test_init_creates_current_node_and_dlg_cache(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow.__init__)
        self.assertIn("self._current_node = None", src)
        self.assertIn("self._menu_add_attr_dlg = None", src)


# ===================== from test_attr_panel_refresh_on_connect.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__attr_panel_refresh_on_connect():
    standalone_init()


class _FakeItem:
    def __init__(self, name, is_array=False):
        self._name = name
        self.attr_name = name
        self.attr_meta = {"is_array": is_array}

    def getCurrentName(self):
        return self._name


class _RefreshRecorder:
    """Minimal duck-typed stand-in for the attr tree."""

    def __init__(self, category, py_node, item):
        self.ATTR_CATEGORY = category
        self._py_node = py_node
        self._item = item
        self.refresh_calls = 0

    def _selected_user_items(self):
        return [self._item]

    def refresh(self):
        self.refresh_calls += 1


class TestAttrPanelRefreshOnConnect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def test_disconnect_selected_refreshes_and_disconnects(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        node = MPyNode.create(name="dn")
        node.add_input_attr("k", "float")
        plug = node.get_name() + ".k"
        src = mc.createNode("transform", name="drv")
        mc.connectAttr(src + ".translateX", plug, force=True)
        self.assertTrue(mc.isConnected(src + ".translateX", plug))

        fake = _RefreshRecorder("input", node, _FakeItem("k"))
        NDInputAttrTree._disconnect_selected(fake)

        self.assertFalse(mc.isConnected(src + ".translateX", plug))
        self.assertEqual(fake.refresh_calls, 1)

    def test_show_connect_dlg_refreshes_after_connect(self):
        from mpynode.ui.widgets import attributes as A
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        node = MPyNode.create(name="cn")
        node.add_input_attr("k", "float")
        plug = node.get_name() + ".k"
        src = mc.createNode("transform", name="drv2")
        src_plug = src + ".translateX"

        class _FakeDlg:
            def __init__(self, parent, target_plug, target_is_multi=False):
                pass

            def exec_(self):
                return True

            def getChosenPlugs(self):
                return [src_plug]

            def getExtraFlag(self):
                return True

        fake = _RefreshRecorder("input", node, _FakeItem("k"))
        orig = A.NDConnectInputAttrDialog
        A.NDConnectInputAttrDialog = _FakeDlg
        try:
            A.NDInputAttrTree._show_connect_dlg(fake)
        finally:
            A.NDConnectInputAttrDialog = orig

        self.assertTrue(mc.isConnected(src_plug, plug))
        self.assertEqual(fake.refresh_calls, 1)


# ===================== from test_phase18_5.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase18_5():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Multi-attr type contract
# ===========================================================================


class TestMultiAttrTypeContract(unittest.TestCase):
    """Multi numerical inputs return numpy 1D arrays.
    Multi vector / euler inputs return numpy (n, 3) ndarrays.
    Multi matrix inputs return a numpy-transparent MatrixArrayView
    (``np.asarray(M)`` -> (n, 4, 4); ``M.shape`` -> (n, 4, 4)).
    Multi string / python / geometry inputs stay as Python list.

    vector / euler / matrix multis used to return
    ``list[np.ndarray]``. Now they return a single stacked ndarray for
    better numpy ergonomics (``vec_in[:, 0]`` for all X coords,
    ``vec_in.shape``, etc.). Iteration still yields per-row
    sub-arrays so most existing user expressions keep working unchanged.
    """

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _probe_input_type(self, attr_name: str, attr_type: str) -> str:
        """Add an array input + capture its type via a string output expression."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=f"probe_{attr_name}")
        n.add_input_attr(attr_name, attr_type, is_array=True)
        n.add_output_attr("type_name", "string")
        n.set_compute_expression(f"self.type_name = type(self.{attr_name}).__name__")
        n.set_compute_expression(f"self.type_name = type(self.{attr_name}).__name__")
        # Reading the output is enough: compute fires on the first read.
        return mc.getAttr(n.get_name() + ".type_name") or ""

    def _probe_input_shape(self, attr_name: str, attr_type: str) -> str:
        """Same probe pattern but reads.shape (or len for non-arrays)."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name=f"shape_{attr_name}")
        n.add_input_attr(attr_name, attr_type, is_array=True)
        n.add_output_attr("shape_str", "string")
        n.set_compute_expression(f"self.shape_str = str(self.{attr_name}.shape)")
        return mc.getAttr(n.get_name() + ".shape_str") or ""

    def test_multi_float_returns_ndarray(self):
        result = self._probe_input_type("vals", "float")
        self.assertEqual(result, "ndarray")

    def test_multi_int_returns_ndarray(self):
        result = self._probe_input_type("counts", "int")
        self.assertEqual(result, "ndarray")

    def test_multi_bool_returns_ndarray(self):
        result = self._probe_input_type("flags", "bool")
        self.assertEqual(result, "ndarray")

    def test_multi_vector_returns_ndarray(self):
        """was list, now stacked ndarray (n, 3)."""
        result = self._probe_input_type("vecs", "vector")
        self.assertEqual(result, "ndarray")

    def test_multi_vector_empty_shape_is_n_3(self):
        """Empty multi vector still has the (0, 3) shape so user code
        that does ``.shape[1]`` doesn't blow up on empty input."""
        result = self._probe_input_shape("vecs", "vector")
        # Empty multi \u2192 numElements()==0 \u2192 np.zeros((0, 3))
        self.assertEqual(result, "(0, 3)")

    def test_multi_matrix_returns_matrix_array_view(self):
        """was list, then stacked ndarray; now a numpy-transparent
        MatrixArrayView (``np.asarray(M)`` -> (n,4,4), ``M[i]`` -> single
        view, ``M.translation()`` -> (n,3))."""
        result = self._probe_input_type("mats", "matrix")
        self.assertEqual(result, "MatrixArrayView")

    def test_multi_matrix_empty_shape_is_n_4_4(self):
        result = self._probe_input_shape("mats", "matrix")
        self.assertEqual(result, "(0, 4, 4)")

    def test_multi_string_returns_list(self):
        result = self._probe_input_type("names", "string")
        self.assertEqual(result, "list")

    def test_multi_float_dtype(self):
        """Verify the dtype, not just the type."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="dtype1")
        n.add_input_attr("xs", "float", is_array=True)
        n.add_output_attr("dt", "string")
        n.set_compute_expression("self.dt = str(self.xs.dtype)")
        result = mc.getAttr(n.get_name() + ".dt") or ""
        self.assertEqual(result, "float64")

    def test_multi_vector_populated_shape(self):
        """3 connected vector sources \u2192 input shape (3, 3)."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="vshape")
        n.add_input_attr("vs", "vector", is_array=True)
        n.add_output_attr("shape_str", "string")
        n.set_compute_expression("self.shape_str = str(self.vs.shape)")

        # Connect 3 cube.translate to the multi.
        cubes = [mc.polyCube(name=f"vc_{i}")[0] for i in range(3)]
        for i, c in enumerate(cubes):
            mc.connectAttr(f"{c}.translate", f"{n.get_name()}.vs[{i}]")
        # Touch one of them to make sure the output is dirty.
        mc.setAttr(f"{cubes[0]}.translateX", 1.0)
        result = mc.getAttr(n.get_name() + ".shape_str") or ""
        self.assertEqual(result, "(3, 3)")

    def test_multi_matrix_populated_shape(self):
        """2 matrix elements \u2192 input shape (2, 4, 4)."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="mshape")
        n.add_input_attr("ms", "matrix", is_array=True)
        n.add_output_attr("shape_str", "string")
        n.set_compute_expression("self.shape_str = str(self.ms.shape)")

        m_id = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        for i in range(2):
            mc.setAttr(f"{n.get_name()}.ms[{i}]", *m_id, type="matrix")
        # Touch to dirty.
        mc.setAttr(f"{n.get_name()}.ms[0]", *m_id, type="matrix")
        result = mc.getAttr(n.get_name() + ".shape_str") or ""
        self.assertEqual(result, "(2, 4, 4)")


# ===========================================================================
# Multi-attr connect helper
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestComputeConnectionPairs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_scalar_target_takes_first_source_only(self):
        from mpynode.ui.dialogs.connect_attr import compute_connection_pairs

        pairs = compute_connection_pairs(
            "node.input",
            target_is_multi=False,
            source_plugs=["a.x", "b.x", "c.x"],
        )
        self.assertEqual(pairs, [("a.x", "node.input")])

    def test_multi_target_distributes_to_indices(self):
        """Empty multi target \u2192 sources fill [0], [1], [2],..."""
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.dialogs.connect_attr import compute_connection_pairs

        n = MPyNode.create(name="multi1")
        n.add_input_attr("input", "vector", is_array=True)
        target = f"{n.get_name()}.input"

        pairs = compute_connection_pairs(
            target,
            target_is_multi=True,
            source_plugs=["a.translate", "b.translate", "c.translate"],
        )
        self.assertEqual(
            pairs,
            [
                ("a.translate", f"{target}[0]"),
                ("b.translate", f"{target}[1]"),
                ("c.translate", f"{target}[2]"),
            ],
        )

    def test_multi_target_starts_at_next_available(self):
        """Pre-existing connections at [0], [1] \u2192 new sources start at [2]."""
        from mpynode._base.commands import _ConnectAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.dialogs.connect_attr import compute_connection_pairs

        n = MPyNode.create(name="multi2")
        n.add_input_attr("input", "vector", is_array=True)
        target = f"{n.get_name()}.input"

        # Pre-populate indices [0] and [1]
        c1 = mc.polyCube(name="src1")[0]
        c2 = mc.polyCube(name="src2")[0]
        run_undoable(_ConnectAttrCommand(f"{c1}.translate", f"{target}[0]"))
        run_undoable(_ConnectAttrCommand(f"{c2}.translate", f"{target}[1]"))

        # Two new sources -> should start at [2].
        c3 = mc.polyCube(name="src3")[0]
        c4 = mc.polyCube(name="src4")[0]
        pairs = compute_connection_pairs(
            target,
            target_is_multi=True,
            source_plugs=[f"{c3}.translate", f"{c4}.translate"],
        )
        self.assertEqual(
            pairs,
            [
                (f"{c3}.translate", f"{target}[2]"),
                (f"{c4}.translate", f"{target}[3]"),
            ],
        )

    def test_user_workflow_multi_translate_connection(self):
        """Reproduces the bug: connecting translate from
        multiple cubes to a multi vector input."""
        from mpynode._base.commands import _ConnectAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode
        from mpynode.ui.dialogs.connect_attr import compute_connection_pairs

        n = MPyNode.create(name="bugfix")
        n.add_input_attr("input", "vector", is_array=True)
        target = f"{n.get_name()}.input"

        cubes = [mc.polyCube(name=f"bug_{i}")[0] for i in range(3)]
        sources = [f"{c}.translate" for c in cubes]

        pairs = compute_connection_pairs(
            target, target_is_multi=True, source_plugs=sources
        )
        # must not raise "Incompatible multi-attribute parent levels".
        for src, dst in pairs:
            run_undoable(_ConnectAttrCommand(src, dst))

        for i, c in enumerate(cubes):
            conns = mc.listConnections(f"{target}[{i}]", source=True, plugs=True) or []
            self.assertIn(f"{c}.translate", conns)


# ===========================================================================
# AddAttr dialog persistence + dual-direction
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestAddAttrDialogShape(unittest.TestCase):
    def test_dialog_is_not_modal(self):
        """Dialog stays open between Adds. Non-modal."""
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog.__init__)
        self.assertIn("setModal(False)", src)

    def test_has_direction_radios_and_done_button(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        build_src = inspect.getsource(NDAddAttrDialog._build_ui)
        self.assertIn("_input_radio", build_src)
        self.assertIn("_output_radio", build_src)
        self.assertIn('"Done"', build_src)
        # Add button stays open + clears + refocuses
        add_src = inspect.getsource(NDAddAttrDialog._on_add_clicked)
        self.assertIn("self._name_edit.clear()", add_src)
        self.assertIn("self._name_edit.setFocus()", add_src)

    def test_signature_takes_py_node_plus_callback(self):
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        sig = inspect.signature(NDAddAttrDialog.__init__)
        params = list(sig.parameters.keys())
        # parent, py_node, initial_direction, on_attr_added
        self.assertIn("py_node", params)
        self.assertIn("initial_direction", params)
        self.assertIn("on_attr_added", params)

    def test_stack_built_before_populate_type_combo(self):
        """Regression: _populate_type_combo calls _on_type_changed which
        needs _stack to exist. Build order matters."""
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        build_src = inspect.getsource(NDAddAttrDialog._build_ui)
        stack_idx = build_src.find("self._stack = QStackedLayout")
        populate_idx = build_src.find("self._populate_type_combo()")
        self.assertGreater(
            stack_idx,
            -1,
            "_build_ui must create self._stack",
        )
        self.assertGreater(
            populate_idx,
            -1,
            "_build_ui must call _populate_type_combo",
        )
        self.assertLess(
            stack_idx,
            populate_idx,
            "self._stack must be created BEFORE _populate_type_combo() "
            "is called (otherwise _on_type_changed crashes during init)",
        )

    def test_on_type_changed_guards_against_missing_stack(self):
        """Defensive: _on_type_changed should be safe to call even if
        _stack hasn't been built yet."""
        import inspect

        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog

        src = inspect.getsource(NDAddAttrDialog._on_type_changed)
        self.assertIn('hasattr(self, "_stack")', src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestConnectDialogShape(unittest.TestCase):
    def test_extended_selection(self):
        import inspect

        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        build_src = inspect.getsource(_BaseConnectDialog._build_ui)
        self.assertIn("ExtendedSelection", build_src)

    def test_get_chosen_plugs_returns_list(self):
        from mpynode.ui.dialogs.connect_attr import _BaseConnectDialog

        # Method renamed to plural form.
        self.assertTrue(hasattr(_BaseConnectDialog, "getChosenPlugs"))

    def test_target_is_multi_kwarg(self):
        import inspect

        from mpynode.ui.dialogs.connect_attr import (
            NDConnectInputAttrDialog,
            NDConnectOutputAttrDialog,
        )

        for cls in (NDConnectInputAttrDialog, NDConnectOutputAttrDialog):
            sig = inspect.signature(cls.__init__)
            self.assertIn("target_is_multi", sig.parameters.keys())


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestAttributesWidgetMultiHandling(unittest.TestCase):
    def test_show_connect_dlg_passes_target_is_multi(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._show_connect_dlg)
        self.assertIn("target_is_multi", src)
        self.assertIn("compute_connection_pairs", src)


# ===================== from test_phase06.py =====================
import os
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase06():
    standalone_init()


class TestMPyConstraintBasics(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_node_type_registered(self):
        self.assertIn("mPyConstraint", mc.allNodeTypes() or [])

    def test_create(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        c = MPyConstraint.create(name="myConstraint")
        self.assertTrue(mc.objExists("myConstraint"))
        self.assertEqual(mc.nodeType("myConstraint"), "mPyConstraint")

    def test_preset_inputs_present(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        c = MPyConstraint.create(name="presetCheck")
        for plug in (
            "targetTranslate",
            "targetRotate",
            "targetWeight",
            "restTranslate",
            "restRotate",
        ):
            self.assertTrue(
                mc.attributeQuery(plug, node=c.get_name(), exists=True),
                f"preset constraint plug {plug!r} should exist",
            )

    def test_internal_attrs_present(self):
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        c = MPyConstraint.create(name="internalCheck")
        for plug in ("_computeSource", "_inputAttrs", "_outputAttrs"):
            self.assertTrue(mc.attributeQuery(plug, node=c.get_name(), exists=True))


class TestMPyConstraintExpression(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_drives_cube_via_targetTranslate(self):
        """End-to-end: source cube -> constraint -> driven cube.
        Move source, driven follows."""
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        source = mc.polyCube(name="src")[0]
        driven = mc.polyCube(name="dst")[0]

        c = MPyConstraint.create(name="ptCstr")
        c.add_output_attr("out", "vector")
        c.set_compute_expression("self.out = list(self.targetTranslate)")

        mc.connectAttr(source + ".translate", c.get_name() + ".targetTranslate", force=True)
        mc.connectAttr(c.get_name() + ".out", driven + ".translate", force=True)

        # Move source to (5, 7, 9), driven should follow.
        mc.setAttr(source + ".translate", 5.0, 7.0, 9.0, type="double3")
        ws = mc.xform(driven, q=True, ws=True, t=True)
        self.assertAlmostEqual(
            ws[0], 5.0, places=4, msg=f"driven X = {ws[0]}; expected 5.0"
        )
        self.assertAlmostEqual(ws[1], 7.0, places=4)
        self.assertAlmostEqual(ws[2], 9.0, places=4)

        # Move source again.
        mc.setAttr(source + ".translate", -2.0, 1.5, 0.5, type="double3")
        ws = mc.xform(driven, q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[0], -2.0, places=4)
        self.assertAlmostEqual(ws[1], 1.5, places=4)
        self.assertAlmostEqual(ws[2], 0.5, places=4)

    def test_weighted_constraint_blends_to_rest(self):
        """Target_weight=0 should output restTranslate; weight=1
        should output targetTranslate. Verify with visible cube."""
        from mpynode.wrappers.mpy_constraint import MPyConstraint

        source = mc.polyCube(name="srcW")[0]
        driven = mc.polyCube(name="dstW")[0]

        c = MPyConstraint.create(name="weightedCstr")
        c.add_output_attr("out", "vector")
        c.set_compute_expression(
            "self.out = ["
            "    self.targetTranslate[0] * self.targetWeight + self.restTranslate[0] * (1 - self.targetWeight),"
            "    self.targetTranslate[1] * self.targetWeight + self.restTranslate[1] * (1 - self.targetWeight),"
            "    self.targetTranslate[2] * self.targetWeight + self.restTranslate[2] * (1 - self.targetWeight),"
            "]"
        )

        mc.connectAttr(source + ".translate", c.get_name() + ".targetTranslate", force=True)
        mc.connectAttr(c.get_name() + ".out", driven + ".translate", force=True)

        mc.setAttr(source + ".translate", 10.0, 0.0, 0.0, type="double3")
        mc.setAttr(c.get_name() + ".restTranslate", 0.0, 0.0, 0.0, type="double3")

        # weight=1 \u2192 driven matches source
        mc.setAttr(c.get_name() + ".targetWeight", 1.0)
        ws = mc.xform(driven, q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[0], 10.0, places=3)

        # weight=0 \u2192 driven matches rest (origin)
        mc.setAttr(c.get_name() + ".targetWeight", 0.0)
        ws = mc.xform(driven, q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[0], 0.0, places=3)

        # weight=0.5 \u2192 driven at half
        mc.setAttr(c.get_name() + ".targetWeight", 0.5)
        ws = mc.xform(driven, q=True, ws=True, t=True)
        self.assertAlmostEqual(ws[0], 5.0, places=3)


class TestMPyConstraintRecipe(unittest.TestCase):
    def test_recipe_registered(self):
        from mpynode._common.util.recipes import get_recipe

        recipe = get_recipe("mPyConstraint")
        self.assertIsNotNone(recipe)
        names_in = {e.name for e in recipe.inputs}
        for n in (
            "targetTranslate",
            "targetRotate",
            "targetWeight",
            "restTranslate",
            "restRotate",
        ):
            self.assertIn(n, names_in)
        # All 5 are real plugs (no synthetics)
        for entry in recipe.inputs:
            self.assertTrue(entry.source_plug, f"{entry.name} should be a real plug")


# ===================== multi-target auto-index + clobber policy =====================
# Connecting an mPy output INTO a multi (array) target attr, plus the unified
# "start at 0 (clobber) vs append" index policy for a MULTI mPy attr.
import os
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__multi_target_connect():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestParseIndexRange(unittest.TestCase):
    """Pure range parser for the target-array index field."""

    def test_blank_or_all_is_full_existing_count(self):
        from mpynode.ui.dialogs.connect_attr import parse_index_range

        self.assertEqual(parse_index_range("", 4), [0, 1, 2, 3])
        self.assertEqual(parse_index_range("all", 3), [0, 1, 2])
        self.assertEqual(parse_index_range("   ", 2), [0, 1])

    def test_colon_range_is_end_exclusive(self):
        from mpynode.ui.dialogs.connect_attr import parse_index_range

        self.assertEqual(parse_index_range("0:14", 0), list(range(14)))
        self.assertEqual(parse_index_range("2:5", 0), [2, 3, 4])

    def test_open_ended_colon_uses_default(self):
        from mpynode.ui.dialogs.connect_attr import parse_index_range

        self.assertEqual(parse_index_range("0:", 5), [0, 1, 2, 3, 4])

    def test_comma_list_and_combo_dedupe(self):
        from mpynode.ui.dialogs.connect_attr import parse_index_range

        self.assertEqual(parse_index_range("0,2,5", 0), [0, 2, 5])
        self.assertEqual(parse_index_range("0:3,2,7", 0), [0, 1, 2, 7])

    def test_bad_tokens_and_negatives_dropped(self):
        from mpynode.ui.dialogs.connect_attr import parse_index_range

        self.assertEqual(parse_index_range("x,3,y:z", 0), [3])
        self.assertEqual(parse_index_range("-1,2", 0), [2])


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestResolveMultiTarget(unittest.TestCase):
    """Detect an un-indexed multi ancestor on a candidate DESTINATION plug."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_polycolorpervertex_vertexcolor_is_multi_target(self):
        from mpynode.ui.dialogs.connect_attr import resolve_multi_target

        pcv = mc.createNode("polyColorPerVertex")
        info = resolve_multi_target(pcv + ".vertexColor.vertexColorRGB")
        self.assertTrue(info["is_multi_target"])
        self.assertFalse(info["nested"])
        self.assertEqual(
            info["template"], pcv + ".vertexColor[{idx}].vertexColorRGB"
        )

    def test_plain_compound_is_not_a_multi_target(self):
        from mpynode.ui.dialogs.connect_attr import resolve_multi_target

        t = mc.createNode("transform")
        info = resolve_multi_target(t + ".translate")
        self.assertFalse(info["is_multi_target"])
        self.assertIsNone(info["template"])

    def test_nested_double_multi_is_flagged_unsupported(self):
        from mpynode.ui.dialogs.connect_attr import resolve_multi_target

        pcv = mc.createNode("polyColorPerVertex")
        info = resolve_multi_target(
            pcv + ".vertexColor.vertexFaceColor.vertexFaceColorRGB"
        )
        self.assertTrue(info["is_multi_target"])
        self.assertTrue(info["nested"])
        self.assertIsNone(info["template"])

    def test_existing_count_reflects_wired_elements(self):
        """plusMinusAverage.input3D is itself a multi; count = wired elems."""
        from mpynode.ui.dialogs.connect_attr import resolve_multi_target

        pma = mc.createNode("plusMinusAverage")
        locs = [mc.spaceLocator()[0] for _ in range(3)]
        for i, l in enumerate(locs):
            mc.connectAttr(l + ".translate", "%s.input3D[%d]" % (pma, i), force=True)
        info = resolve_multi_target(pma + ".input3D")
        self.assertTrue(info["is_multi_target"])
        self.assertEqual(info["existing_count"], 3)
        self.assertEqual(info["template"], pma + ".input3D[{idx}]")


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestExpandDestPlugs(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_scalar_plug_passes_through(self):
        from mpynode.ui.dialogs.connect_attr import expand_dest_plugs

        t = mc.createNode("transform")
        out, warns = expand_dest_plugs([t + ".translate"])
        self.assertEqual(out, [t + ".translate"])
        self.assertEqual(warns, [])

    def test_multi_target_expands_over_range(self):
        from mpynode.ui.dialogs.connect_attr import expand_dest_plugs

        pcv = mc.createNode("polyColorPerVertex")
        out, warns = expand_dest_plugs([pcv + ".vertexColor.vertexColorRGB"], "0:3")
        self.assertEqual(
            out,
            [pcv + ".vertexColor[%d].vertexColorRGB" % i for i in range(3)],
        )
        self.assertEqual(warns, [])

    def test_empty_multi_blank_range_seeds_index_zero(self):
        from mpynode.ui.dialogs.connect_attr import expand_dest_plugs

        pcv = mc.createNode("polyColorPerVertex")  # vertexColor has 0 elems
        out, warns = expand_dest_plugs([pcv + ".vertexColor.vertexColorRGB"], "")
        self.assertEqual(out, [pcv + ".vertexColor[0].vertexColorRGB"])

    def test_nested_target_warns_and_is_skipped(self):
        from mpynode.ui.dialogs.connect_attr import expand_dest_plugs

        pcv = mc.createNode("polyColorPerVertex")
        out, warns = expand_dest_plugs(
            [pcv + ".vertexColor.vertexFaceColor.vertexFaceColorRGB"], "0:2"
        )
        self.assertEqual(out, [])
        self.assertEqual(len(warns), 1)

    def test_blank_range_drives_existing_sparse_indices(self):
        """Blank / 'all' must drive the multi's ACTUAL logical indices (which
        may be sparse), not range(count)."""
        from mpynode.ui.dialogs.connect_attr import expand_dest_plugs

        pma = mc.createNode("plusMinusAverage")
        locs = [mc.spaceLocator()[0] for _ in range(3)]
        for l, i in zip(locs, (0, 3, 7)):
            mc.connectAttr(l + ".translate", "%s.input3D[%d]" % (pma, i), force=True)
        out, warns = expand_dest_plugs([pma + ".input3D"], "")
        self.assertEqual(out, ["%s.input3D[%d]" % (pma, i) for i in (0, 3, 7)])
        self.assertEqual(warns, [])

    def test_malformed_range_warns_and_skips(self):
        """A non-blank range that resolves to nothing must warn + skip, never
        silently seed [0] on a populated multi."""
        from mpynode.ui.dialogs.connect_attr import expand_dest_plugs

        pcv = mc.createNode("polyColorPerVertex")
        for bad in ("10:5", "2:2", "foo"):
            out, warns = expand_dest_plugs(
                [pcv + ".vertexColor.vertexColorRGB"], bad
            )
            self.assertEqual(out, [], bad)
            self.assertEqual(len(warns), 1, bad)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestExpandSourcePlugs(unittest.TestCase):
    """T7: the INPUT dialog auto-indexes a SOURCE that lives under an un-indexed
    multi ancestor (driver.worldMatrix, a multi output element) -- the same
    [idx]-insertion the OUTPUT dialog does for multi TARGETS. The resolution is
    direction-agnostic, exposed via source-named aliases."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_source_aliases_are_the_direction_agnostic_functions(self):
        from mpynode.ui.dialogs.connect_attr import (
            expand_dest_plugs,
            expand_source_plugs,
            resolve_multi_source,
            resolve_multi_target,
        )
        self.assertIs(expand_source_plugs, expand_dest_plugs)
        self.assertIs(resolve_multi_source, resolve_multi_target)

    def test_scalar_source_passes_through(self):
        from mpynode.ui.dialogs.connect_attr import expand_source_plugs

        t = mc.createNode("transform")
        out, warns = expand_source_plugs([t + ".translateX"])
        self.assertEqual(out, [t + ".translateX"])
        self.assertEqual(warns, [])

    def test_multi_source_expands_over_range(self):
        from mpynode.ui.dialogs.connect_attr import expand_source_plugs

        # worldMatrix is a multi (array) output on a transform.
        t = mc.createNode("transform")
        out, warns = expand_source_plugs([t + ".worldMatrix"], "0:2")
        self.assertEqual(out, [t + ".worldMatrix[%d]" % i for i in range(2)])
        self.assertEqual(warns, [])

    def test_input_show_connect_dlg_expands_sources(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._show_connect_dlg)
        # input branch expands multi sources before building pairs.
        self.assertIn("expand_source_plugs", src)
        self.assertIn("compute_connection_pairs", src)

    def test_input_dialog_builds_a_source_range_field(self):
        import inspect

        from mpynode.ui.dialogs.connect_attr import NDConnectInputAttrDialog

        src = inspect.getsource(NDConnectInputAttrDialog._build_extra_widgets)
        # source-array index range, mirroring the output dialog's target range.
        self.assertIn("_build_range_field", src)
        self.assertIn("Source array indices", src)


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestClobberVsAppendPairs(unittest.TestCase):
    """The ``clobber`` flag on the pair computers = start at index 0."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_output_clobber_starts_at_zero_append_continues(self):
        from mpynode._base.commands import _ConnectAttrCommand, run_undoable
        from mpynode.ui.dialogs.connect_attr import compute_output_connection_pairs
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ob")
        n.add_output_attr("pts", "vector", is_array=True)
        n.set_compute_expression(
            "self.pts=[[float(i)]*3 for i in range(len(self.pts))]\n"
        )
        plug = n.get_name() + ".pts"
        ds = [mc.createNode("transform", name="ob%d" % i) for i in range(3)]
        for i, d in enumerate(ds):
            run_undoable(_ConnectAttrCommand("%s[%d]" % (plug, i), d + ".translate"))
        newd = mc.createNode("transform", name="obNew")
        append = compute_output_connection_pairs(
            plug, True, [newd + ".translate"], clobber=False
        )
        self.assertEqual(append, [("%s[3]" % plug, newd + ".translate")])
        clob = compute_output_connection_pairs(
            plug, True, [newd + ".translate"], clobber=True
        )
        self.assertEqual(clob, [("%s[0]" % plug, newd + ".translate")])

    def test_input_clobber_starts_at_zero_append_continues(self):
        from mpynode._base.commands import _ConnectAttrCommand, run_undoable
        from mpynode.ui.dialogs.connect_attr import compute_connection_pairs
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ib")
        n.add_input_attr("inv", "vector", is_array=True)
        plug = n.get_name() + ".inv"
        srcs = [mc.createNode("transform", name="ib%d" % i) for i in range(2)]
        for i, s in enumerate(srcs):
            run_undoable(_ConnectAttrCommand(s + ".translate", "%s[%d]" % (plug, i)))
        newn = mc.createNode("transform", name="ibNew")
        append = compute_connection_pairs(
            plug, True, [newn + ".translate"], clobber=False
        )
        self.assertEqual(append, [(newn + ".translate", "%s[2]" % plug)])
        clob = compute_connection_pairs(
            plug, True, [newn + ".translate"], clobber=True
        )
        self.assertEqual(clob, [(newn + ".translate", "%s[0]" % plug)])


class TestClobberMultiConnectCommand(unittest.TestCase):
    """Clobber trims the array (Maya won't shrink on plain disconnect) and
    rewires from 0; undo restores the prior elements + connections."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def _idx(self, plug):
        return sorted(mc.getAttr(plug, multiIndices=True) or [])

    def test_output_clobber_resizes_and_undo_restores(self):
        from mpynode._base.commands import (
            _ClobberMultiConnectCommand,
            _ConnectAttrCommand,
            run_undoable,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name="cl")
        n.add_output_attr("pts", "vector", is_array=True)
        # Self-sizing (len-based) compute: the array follows the connection
        # count, like the real point-emitter nodes.
        n.set_compute_expression(
            "self.pts=[[float(i)+1.0]*3 for i in range(len(self.pts))]\n"
        )
        plug = n.get_name() + ".pts"
        dsts = [mc.createNode("transform", name="cl%d" % i) for i in range(6)]
        for i, d in enumerate(dsts):
            run_undoable(_ConnectAttrCommand("%s[%d]" % (plug, i), d + ".translate"))
        mc.getAttr("%s[0]" % plug)
        self.assertEqual(self._idx(plug), [0, 1, 2, 3, 4, 5])

        new = [mc.createNode("transform", name="clN%d" % i) for i in range(3)]
        pairs = [("%s[%d]" % (plug, i), new[i] + ".translate") for i in range(3)]
        run_undoable(_ClobberMultiConnectCommand(plug, pairs))
        mc.dgdirty(n.get_name())
        mc.getAttr("%s[0]" % plug)
        # Array resized to the new selection; old connections gone.
        self.assertEqual(self._idx(plug), [0, 1, 2])
        for i in range(3):
            self.assertIn(
                new[i] + ".translate",
                mc.listConnections("%s[%d]" % (plug, i), s=False, d=True, p=True) or [],
            )

        # Single undo restores the 6-element array + original wiring.
        mc.undo()
        self.assertEqual(self._idx(plug), [0, 1, 2, 3, 4, 5])
        for i, d in enumerate(dsts):
            self.assertIn(
                d + ".translate",
                mc.listConnections("%s[%d]" % (plug, i), s=False, d=True, p=True) or [],
            )

    def test_input_clobber_resizes_array(self):
        from mpynode._base.commands import (
            _ClobberMultiConnectCommand,
            _ConnectAttrCommand,
            run_undoable,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        m = MPyNode.create(name="recvc")
        m.add_input_attr("inv", "vector", is_array=True)
        ip = m.get_name() + ".inv"
        srcs = [mc.createNode("transform", name="rc%d" % i) for i in range(6)]
        for i, s in enumerate(srcs):
            run_undoable(_ConnectAttrCommand(s + ".translate", "%s[%d]" % (ip, i)))
        self.assertEqual(self._idx(ip), [0, 1, 2, 3, 4, 5])

        new = [mc.createNode("transform", name="rcN%d" % i) for i in range(3)]
        pairs = [(new[i] + ".translate", "%s[%d]" % (ip, i)) for i in range(3)]
        run_undoable(_ClobberMultiConnectCommand(ip, pairs))
        self.assertEqual(self._idx(ip), [0, 1, 2])
        for i in range(3):
            self.assertIn(
                new[i] + ".translate",
                mc.listConnections("%s[%d]" % (ip, i), s=True, d=False, p=True) or [],
            )


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestMultiTargetEndToEnd(unittest.TestCase):
    """The user's broken scene: an mPy color / color-array output driving a
    polyColorPerVertex multi target must connect without 'Incompatible
    multi-attribute parent levels'."""

    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def _make_pcv(self, name):
        cube = mc.polyCube(name=name)[0]
        mc.polyColorPerVertex(cube, rgb=(0.0, 0.0, 0.0))  # populate vertexColor
        return mc.ls(type="polyColorPerVertex")[0]

    def test_scalar_color_fans_across_vertexcolor(self):
        from mpynode.ui.dialogs.connect_attr import (
            compute_output_connection_pairs,
            expand_dest_plugs,
            resolve_multi_target,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        pcv = self._make_pcv("m1")
        info = resolve_multi_target(pcv + ".vertexColor.vertexColorRGB")
        count = info["existing_count"]
        self.assertGreater(count, 0)

        node = MPyNode.create(name="colorDrv")
        node.add_output_attr("color", "color")
        node.set_compute_expression("self.color=[1.0,0.0,0.0]\n")

        dests, warns = expand_dest_plugs(
            [pcv + ".vertexColor.vertexColorRGB"], "0:%d" % count
        )
        self.assertEqual(warns, [])
        self.assertEqual(len(dests), count)
        pairs = compute_output_connection_pairs(
            node.get_name() + ".color", False, dests
        )
        for src, dst in pairs:
            mc.connectAttr(src, dst, force=True)  # must not raise
        for i in range(count):
            self.assertIn(
                node.get_name() + ".color",
                mc.listConnections(
                    "%s.vertexColor[%d].vertexColorRGB" % (pcv, i),
                    s=True, d=False, p=True,
                ) or [],
            )

    def test_color_array_maps_element_wise(self):
        from mpynode.ui.dialogs.connect_attr import (
            compute_output_connection_pairs,
            expand_dest_plugs,
            resolve_multi_target,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        pcv = self._make_pcv("m2")
        info = resolve_multi_target(pcv + ".vertexColor.vertexColorRGB")
        count = info["existing_count"]

        node = MPyNode.create(name="colorArrDrv")
        node.add_output_attr("colorArray", "color", is_array=True)
        node.set_compute_expression(
            "for i in range(len(self.colorArray)):\n"
            "    self.colorArray[i]=[0.0,0.0,1.0]\n"
        )
        dests, _ = expand_dest_plugs(
            [pcv + ".vertexColor.vertexColorRGB"], "0:%d" % count
        )
        pairs = compute_output_connection_pairs(
            node.get_name() + ".colorArray", True, dests, clobber=True
        )
        self.assertEqual(
            pairs[0],
            (
                node.get_name() + ".colorArray[0]",
                pcv + ".vertexColor[0].vertexColorRGB",
            ),
        )
        for src, dst in pairs:
            mc.connectAttr(src, dst, force=True)  # must not raise


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestConnectDialogClobberCheckbox(unittest.TestCase):
    """The input Force checkbox was grayed out for multi targets, leaving no
    way to start at index 0. It is now a live clobber toggle."""

    def test_input_build_no_longer_disables_multi_checkbox(self):
        import inspect

        from mpynode.ui.dialogs.connect_attr import NDConnectInputAttrDialog

        src = inspect.getsource(NDConnectInputAttrDialog._build_extra_widgets)
        # clobber toggle exists, defaults ON, old grey-out gone.
        self.assertIn("_clobber_check", src)
        self.assertIn("setChecked(True)", src)  # default = clobber (Issue 2b)
        self.assertNotIn("setEnabled(False)", src)

    def test_output_build_has_range_field(self):
        import inspect

        from mpynode.ui.dialogs.connect_attr import (
            NDConnectOutputAttrDialog,
            _BaseConnectDialog,
        )

        # The range field comes from the SHARED base builder (so the input
        # dialog gets one too); output invokes it with a target label.
        build_src = inspect.getsource(
            NDConnectOutputAttrDialog._build_extra_widgets
        )
        self.assertIn("_build_range_field", build_src)
        self.assertIn("Target array indices", build_src)
        # The shared builder is what creates the _range_edit widget.
        self.assertIn("_range_edit", inspect.getsource(
            _BaseConnectDialog._build_range_field))
        # Stale-prefill guard: refresh the auto value on a selection change
        # without stomping a hand-typed range.
        sel_src = inspect.getsource(
            NDConnectOutputAttrDialog._on_range_selection_changed
        )
        self.assertIn("_range_autofill", sel_src)
        self.assertIn("user_edited", sel_src)

    def test_multi_input_dialog_checkbox_is_enabled_live(self):
        # A real widget needs a widget-capable QApplication, which headless
        # mayapy lacks -- so this SKIPS in the gate and runs only in an
        # interactive Maya. The inspect test above covers it headless.
        try:
            from mpynode.ui.qt_wrapper import QApplication  # noqa: F401
        except ImportError:
            self.skipTest("QApplication unavailable (headless)")
        if QApplication.instance() is None:
            self.skipTest("no live QApplication")
        from mpynode.ui.dialogs.connect_attr import NDConnectInputAttrDialog

        dlg = NDConnectInputAttrDialog(
            parent=None, target_plug="m.inv", target_is_multi=True
        )
        self.assertTrue(dlg._clobber_check.isEnabled())
        self.assertTrue(dlg._clobber_check.isChecked())  # default = clobber
        self.assertTrue(dlg.getClobber())
        dlg.deleteLater()


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestShowConnectDlgWiring(unittest.TestCase):
    def test_output_handler_expands_and_honors_clobber(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDOutputAttrTree

        src = inspect.getsource(NDOutputAttrTree._show_connect_dlg)
        self.assertIn("expand_dest_plugs", src)
        self.assertIn("getClobber", src)
        self.assertIn("_ClobberMultiConnectCommand", src)

    def test_output_clobber_end_to_end_via_show_connect_dlg(self):
        """Behavioral: driving _show_connect_dlg on an OUTPUT array with a
        multi-target destination + clobber wires colorArray[i] ->
        vertexColor[i].vertexColorRGB and refreshes."""
        from mpynode.ui.widgets import attributes as A
        from mpynode.wrappers._mpy_node import MPyNode

        mc.file(new=True, force=True)
        ensure_plugins_loaded()
        cube = mc.polyCube(name="scMesh")[0]
        mc.polyColorPerVertex(cube, rgb=(0.0, 0.0, 0.0))  # 8 vertexColor elems
        pcv = mc.ls(type="polyColorPerVertex")[0]

        node = MPyNode.create(name="scDrv")
        node.add_output_attr("colorArray", "color", is_array=True)
        node.set_compute_expression(
            "for i in range(len(self.colorArray)):\n"
            "    self.colorArray[i]=[1.0,0.0,0.0]\n"
        )
        target_leaf = pcv + ".vertexColor.vertexColorRGB"

        class _FakeDlg:
            def __init__(self, parent, target_plug, target_is_multi=False):
                pass

            def exec_(self):
                return True

            def getChosenPlugs(self):
                return [target_leaf]

            def getExtraFlag(self):
                return True

            def getClobber(self):
                return True

            def getRangeText(self):
                return "0:8"

        recorder = _RefreshRecorder(
            "output", node, _FakeItem("colorArray", is_array=True)
        )
        orig = A.NDConnectOutputAttrDialog
        A.NDConnectOutputAttrDialog = _FakeDlg
        try:
            A.NDOutputAttrTree._show_connect_dlg(recorder)
        finally:
            A.NDConnectOutputAttrDialog = orig

        for i in range(8):
            conns = (
                mc.listConnections(
                    "%s.vertexColor[%d].vertexColorRGB" % (pcv, i),
                    s=True, d=False, p=True,
                )
                or []
            )
            self.assertIn("%s.colorArray[%d]" % (node.get_name(), i), conns)
        self.assertEqual(recorder.refresh_calls, 1)


def setUpModule():
    _setUpModule__disconnect_all_multi()
    _setUpModule__output_multi_connect_index()
    _setUpModule__output_multi_write_index()
    _setUpModule__connection_callback()
    _setUpModule__phase18_6()
    _setUpModule__attr_panel_refresh_on_connect()
    _setUpModule__phase18_5()
    _setUpModule__phase06()
    _setUpModule__multi_target_connect()


if __name__ == "__main__":
    import unittest
    unittest.main()
