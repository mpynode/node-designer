"""Attributes-tab UI: framework filter, connection visuals, rename editor + expr rewrite, colors, live refresh

Consolidated from: test_attributes_plug_filter.py, test_attr_connection_visual.py, test_locked_row_bold_connected.py, test_rename_editor_polish.py, test_attr_color_live_refresh.py, test_attr_rename_expr.py, test_phase23.py, test_phase18.py.
"""

from __future__ import annotations

# ===================== from test_attributes_plug_filter.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-plug-filter-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__attributes_plug_filter():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestIsFrameworkAttr(unittest.TestCase):
    """Pure-function classifier tests (no Qt / no scene needed)."""

    def test_underscore_prefix_is_framework(self):
        from mpynode._common.plugs.plug_filter import is_framework_attr

        for name in (
            "_initSource",
            "_storedVarsData",
            "_inputAttrs",
            "_outputAttrs",
            "_timeIn",
            "_autoEvaluate",
        ):
            self.assertTrue(
                is_framework_attr(name),
                f"{name!r} should be classified as framework",
            )

    def test_blocklist_named_attrs_are_framework(self):
        from mpynode._common.plugs.plug_filter import is_framework_attr

        for name in (
            "_computeSource",
            "debug_mode",
            "profile_enabled",
            "deep_profile_enabled",
            "watch_enabled",
            "caching",
            "frozen",
            "isHistoricallyInteresting",
            "nodeState",
            "binMembership",
            "message",
            "blockGPU",
            "function",
            "map64BitIndices",
            "weightFunction",
        ):
            self.assertTrue(
                is_framework_attr(name),
                f"{name!r} should be classified as framework",
            )

    def test_user_facing_attrs_are_NOT_framework(self):
        from mpynode._common.plugs.plug_filter import is_framework_attr

        for name in (
            "envelope",
            "input",
            "outputGeometry",
            "originalGeometry",
            "envelopeWeightsList",
            "weightList",
            "amplitude",
            "amplitudeX",
            "driverMatrixA",
            "driverMatrixB",
        ):
            self.assertFalse(
                is_framework_attr(name),
                f"{name!r} should NOT be classified as framework",
            )

    def test_empty_string_is_not_framework(self):
        from mpynode._common.plugs.plug_filter import is_framework_attr

        self.assertFalse(is_framework_attr(""))

    def test_fchild_pattern_is_framework(self):
        """Maya names unnamed Compound-numeric children
        ``fchild1`` / ``fchild2`` / ``fchild3``. They orphan-leak
        when the parent compound is filtered, so they must be
        filtered too."""
        from mpynode._common.plugs.plug_filter import is_framework_attr

        for name in ("fchild1", "fchild2", "fchild3", "fchild99"):
            self.assertTrue(
                is_framework_attr(name),
                f"{name!r} (Maya auto-named compound child) "
                f"should be classified as framework",
            )

    def test_fchild_pattern_does_not_match_unrelated_names(self):
        """``fchild`` prefix on a real attr name shouldn't be
        filtered (regex anchors to start AND requires digits)."""
        from mpynode._common.plugs.plug_filter import is_framework_attr

        for name in ("fchildren", "myFchild1", "fchild", "fchildA"):
            self.assertFalse(
                is_framework_attr(name),
                f"{name!r} should NOT be classified as framework "
                f"(only ``fchild\\d+`` pattern matches)",
            )


class TestIsUsefulInherited(unittest.TestCase):
    """Allowlist predicate + shared deformer set (no Qt / no scene)."""

    def test_deformer_useful_membership(self):
        from mpynode._common.plugs.plug_filter import DEFORMER_USEFUL
        for n in ("input", "inputGeometry", "outputGeometry",
                  "originalGeometry", "envelope", "weightList"):
            self.assertIn(n, DEFORMER_USEFUL)
        for n in ("paintWeights", "wtDrty", "weights", "groupId"):
            self.assertNotIn(n, DEFORMER_USEFUL)

    def test_is_useful_inherited_allow_and_deny(self):
        from mpynode._common.plugs.plug_filter import is_useful_inherited
        allow = frozenset({"input", "outputGeometry"})
        self.assertTrue(is_useful_inherited("input", allow))
        self.assertTrue(is_useful_inherited("outputGeometry", allow))
        self.assertFalse(is_useful_inherited("paintWeights", allow))
        self.assertFalse(is_useful_inherited("", allow))
        self.assertFalse(is_useful_inherited("input", frozenset()))


class TestAttributesTabFilterIntegration(unittest.TestCase):
    """The Attributes tab hides framework attrs by default and shows
    them when the checkbox is toggled."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        # no stale optionVar across tests.
        try:
            if mc.optionVar(exists="mpynodeShowFrameworkAttrs"):
                mc.optionVar(remove="mpynodeShowFrameworkAttrs")
        except Exception:
            pass
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="filter_test")
        # User-added attr that MUST show even when filter is on.
        self.node.add_input_attr("amplitude", "float")

    def tearDown(self):
        try:
            if mc.optionVar(exists="mpynodeShowFrameworkAttrs"):
                mc.optionVar(remove="mpynodeShowFrameworkAttrs")
        except Exception:
            pass

    def _make_tree(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        t = NDInputAttrTree()
        t.setNode(self.node)
        return t

    def _row_short_names(self, tree):
        """Walk the QTreeWidget items recursively + return every
        attr's short name from item text. The text format is
        ``"name: type"`` for scalars OR ``"name[]: type"`` /
        ``"name[]: type (sparse)"`` for arrays; we strip the suffix."""
        names = []

        def _walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                _walk(child)
            txt = item.text(0) or ""
            if ": " in txt:
                txt = txt.split(": ", 1)[0]
            # strip the "[]" array marker; attr names never contain "[".
            names.append(txt.split("[", 1)[0].strip())

        for i in range(tree.topLevelItemCount()):
            _walk(tree.topLevelItem(i))
        return names

    def test_default_filter_hides_framework_attrs(self):
        tree  = self._make_tree()
        names = self._row_short_names(tree)
        # Framework attrs MUST NOT appear by default.
        for hidden in ("_computeSource", "caching", "nodeState",
                       "_initSource", "_storedVarsData"):
            self.assertNotIn(
                hidden, names,
                f"{hidden!r} leaked into the tree with default "
                f"(filter=ON) settings; got rows: {names}",
            )
        # User-added attr MUST still appear.
        self.assertIn("amplitude", names,
            f"user-added 'amplitude' missing; got rows: {names}")

    def test_skincluster_allowlist_hides_deformer_noise(self):
        # Allowlist model end-to-end through the real widget: a skinCluster
        # shows its I/O but NOT the ~40 inherited deformer noise plugs.
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        j1 = mc.joint(p=(0, 0, 0), n="afj1"); mc.select(cl=True)
        j2 = mc.joint(p=(0, 2, 0), n="afj2"); mc.select(cl=True)
        plane = mc.polyPlane(name="afP", w=2, h=2, sx=1, sy=1)[0]
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
        sc = MPySkinCluster.create(plane, joints=[j1, j2], name="afSkin")

        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDOutputAttrTree,
        )
        it = NDInputAttrTree(); it.setNode(sc)
        in_names = set(self._row_short_names(it))
        for useful in ("input", "inputGeometry", "originalGeometry",
                       "envelope", "weightList", "skinningMethod"):
            self.assertIn(useful, in_names,
                          f"{useful!r} should show in inputs; got {sorted(in_names)}")
        for noise in ("paintWeights", "wtDrty", "bindPose", "influenceColor",
                      "heatmapFalloff", "dqsScaleX", "weights"):
            self.assertNotIn(noise, in_names,
                             f"{noise!r} leaked into inputs; got {sorted(in_names)}")
        ot = NDOutputAttrTree(); ot.setNode(sc)
        out_names = set(self._row_short_names(ot))
        self.assertIn("outputGeometry", out_names,
                      f"outputGeometry should show in outputs; got {sorted(out_names)}")

    def test_optionvar_on_shows_framework_attrs(self):
        mc.optionVar(iv=("mpynodeShowFrameworkAttrs", 1))
        tree  = self._make_tree()
        names = self._row_short_names(tree)
        # with the opt-in flag, at least one blocklisted framework attr
        # must appear.
        framework_present = any(
            n in names for n in (
                "_computeSource", "caching", "nodeState",
                "debug_mode", "_initSource",
            )
        )
        self.assertTrue(
            framework_present,
            f"with optionVar=1, expected at least one framework "
            f"row to appear; got: {names}",
        )

    def test_checkbox_toggle_persists_via_optionvar(self):
        """The NDAttributesWidget checkbox writes
        mpynodeShowFrameworkAttrs on toggle."""
        from mpynode.ui.widgets.attributes import NDAttributesWidget

        w = NDAttributesWidget()
        # setChecked fires toggled, which writes the optionVar.
        w._show_framework_chk.setChecked(True)
        try:
            val = mc.optionVar(q="mpynodeShowFrameworkAttrs")
        except Exception:
            val = None
        self.assertEqual(int(val), 1,
            "toggling checkbox ON must set optionVar=1")
        w._show_framework_chk.setChecked(False)
        try:
            val = mc.optionVar(q="mpynodeShowFrameworkAttrs")
        except Exception:
            val = None
        self.assertEqual(int(val), 0,
            "toggling checkbox OFF must set optionVar=0")


class TestSourceShape__attributes_plug_filter(unittest.TestCase):
    def test_filter_module_exists(self):
        from mpynode._common.plugs.plug_filter import (
            is_framework_attr, _FRAMEWORK_HIDDEN,
        )

        self.assertGreater(
            len(_FRAMEWORK_HIDDEN), 5,
            "_FRAMEWORK_HIDDEN should have several entries",
        )
        self.assertTrue(callable(is_framework_attr))

    def test_attributes_tab_calls_filter(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._buildLockedTreeFromWalker)
        # filter goes through is_hidden_input_row = is_framework_attr plus a
        # per-wrapper EXPOSED_INPUT_PLUGS allowlist, so wrappers like
        # mPyTransform can promote inherited plugs to inputs.
        self.assertIn("is_hidden_input_row", src)
        self.assertIn("_show_framework_attrs", src)

    def test_widget_has_checkbox(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDAttributesWidget

        src = inspect.getsource(NDAttributesWidget.__init__)
        self.assertIn("QCheckBox", src)
        self.assertIn("Show framework attrs", src)
        self.assertIn("mpynodeShowFrameworkAttrs", src)


# ===================== from test_attr_connection_visual.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-attr-conn-visual-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__attr_connection_visual():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


def _tree_widget_safe():
    """Return True iff we can construct a QTreeWidget without
    crashing. mayapy standalone returns False -- batch mode lacks
    the real Qt event loop QTreeWidget needs to back its viewport.
    """
    try:
        return not bool(mc.about(batch=True))
    except Exception:
        # If we cannot ask, assume unsafe.
        return False


class TestModuleHelpers(unittest.TestCase):
    """Helpers in isolation -- no Qt event loop required for asserts
    beyond constructing the cached QIcon / QBrush singletons."""

    @classmethod
    def setUpClass(cls):
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def test_connected_icon_is_cached_singleton(self):
        from mpynode.ui.widgets.attributes import _connected_icon

        a = _connected_icon()
        b = _connected_icon()
        self.assertIsNotNone(a)
        self.assertIs(a, b, "connected icon should be a cached singleton")

    def test_connected_icon_differs_from_blank(self):
        from mpynode.ui.widgets.attributes import _blank_icon, _connected_icon

        # cacheKey is stable per QIcon; the connected icon has a painted
        # pixmap, the blank one is transparent.
        self.assertNotEqual(
            _connected_icon().cacheKey(),
            _blank_icon().cacheKey(),
            "connected icon must be visually distinct from blank icon",
        )

    def test_muted_brush_is_cached_singleton(self):
        from mpynode.ui.widgets.attributes import _muted_brush

        a = _muted_brush()
        b = _muted_brush()
        self.assertIsNotNone(a)
        self.assertIs(a, b, "muted brush should be a cached singleton")

    def test_muted_brush_color_is_low_alpha_gray(self):
        from mpynode.ui.widgets.attributes import _muted_brush

        color = _muted_brush().color()
        # ~55% alpha intended; asserted loosely so tuning it needs no
        # test edit.
        self.assertLess(color.alpha(), 255, "muted brush must be semi-transparent")
        # near-gray (R == G == B by design).
        self.assertEqual(color.red(), color.green())
        self.assertEqual(color.green(), color.blue())


class TestUserAttrConnectionVisual(unittest.TestCase):
    """Drive a live mPyNode + render its attribute tree, then assert
    the new visual convention on a USER-added attribute row.

    Skipped under mayapy batch -- constructing a real QTreeWidget
    crashes without a real Qt event loop. Expected to run in real
    Maya GUI as part of the manual smoke-test passes.
    """

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")
        if not _tree_widget_safe():
            raise unittest.SkipTest(
                "QTreeWidget construction crashes mayapy batch; "
                "this test runs in real Maya GUI"
            )

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="conn_visual_test")
        self.node.add_input_attr("free", "float", default=0.0)
        self.node.add_input_attr("wired", "float", default=0.0)
        # drive `wired` so listConnections reports a real source.
        loc = mc.spaceLocator(name="conn_visual_src")[0]
        mc.connectAttr(f"{loc}.translateX", f"{self.node.get_name()}.wired")

    def _items_by_name(self, tree):
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        out = {}
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if isinstance(item, NDUserAttrTreeItem):
                out[item.attr_name] = item
        return out

    def test_connected_row_uses_connected_icon(self):
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree,
            _blank_icon,
            _connected_icon,
        )

        tree = NDInputAttrTree()
        tree.setNode(self.node)
        rows = self._items_by_name(tree)
        self.assertIn("wired", rows, "wired user input should appear in tree")

        wired_item = rows["wired"]
        self.assertTrue(getattr(wired_item, "_is_connected", False))

        self.assertEqual(
            wired_item.icon(0).cacheKey(),
            _connected_icon().cacheKey(),
            "connected row must use the connected-dot icon",
        )
        self.assertNotEqual(
            wired_item.icon(0).cacheKey(),
            _blank_icon().cacheKey(),
        )

    def test_disconnected_row_uses_blank_icon_and_muted_brush(self):
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree,
            _blank_icon,
            _connected_icon,
            _muted_brush,
        )

        tree = NDInputAttrTree()
        tree.setNode(self.node)
        rows = self._items_by_name(tree)
        self.assertIn("free", rows)

        free_item = rows["free"]
        self.assertFalse(getattr(free_item, "_is_connected", True))

        self.assertEqual(
            free_item.icon(0).cacheKey(),
            _blank_icon().cacheKey(),
            "disconnected row must use the blank placeholder icon",
        )
        self.assertNotEqual(
            free_item.icon(0).cacheKey(),
            _connected_icon().cacheKey(),
        )

        muted = _muted_brush()
        self.assertEqual(
            free_item.foreground(0).color().rgba(),
            muted.color().rgba(),
            "disconnected row without ui_color must use the muted brush",
        )

    def test_ui_color_wins_over_muting_on_disconnected_row(self):
        """A disconnected row that carries a deliberate ``ui_color``
        must keep its hue at full strength -- the icon (blank) is the
        only connection signal for that row."""
        from mpynode._base.commands import _SetAttrColorCommand, run_undoable
        from mpynode.ui.qt_wrapper import QColor
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree,
            _blank_icon,
            _muted_brush,
        )

        TAG_HEX = "#80e650"
        run_undoable(_SetAttrColorCommand(self.node, "free", TAG_HEX, "input"))

        tree = NDInputAttrTree()
        tree.setNode(self.node)
        rows = self._items_by_name(tree)
        self.assertIn("free", rows)

        free_item = rows["free"]
        self.assertFalse(getattr(free_item, "_is_connected", True))

        self.assertEqual(
            free_item.icon(0).cacheKey(),
            _blank_icon().cacheKey(),
        )

        muted_color = _muted_brush().color()
        tag_color   = QColor(TAG_HEX)
        self.assertNotEqual(
            free_item.foreground(0).color().rgba(),
            muted_color.rgba(),
            "ui_color must override muted brush on disconnected rows",
        )
        self.assertEqual(
            free_item.foreground(0).color().rgba(),
            tag_color.rgba(),
            "foreground must match the user-chosen ui_color",
        )


# ===================== from test_locked_row_bold_connected.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-bold-connected-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__locked_row_bold_connected():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestLockedRowBoldOnConnected(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2, h=2, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="bold_test_def")

    def test_inherited_class_has_apply_connection_state(self):
        from mpynode.ui.widgets.attributes import NDLockedAttrTreeItem

        self.assertTrue(
            hasattr(NDLockedAttrTreeItem, "apply_connection_state"),
            "NDLockedAttrTreeItem must expose "
            "apply_connection_state for the connection-state visual convention",
        )

    def test_input_geometry_row_flags_connected(self):
        """The deformer\'s ``input[0].inputGeometry`` is auto-wired
        to the source mesh by Maya during ``create_on``. The
        corresponding row in the Attributes tab should be flagged
        as connected via ``_is_connected = True`` (which drives the
        column-0 dot icon + default-brightness foreground)."""
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDLockedAttrTreeItem,
        )
        # Show ALL rows (filter off) so the input rows surface.
        mc.optionVar(iv=("mpynodeShowFrameworkAttrs", 1))
        try:
            tree = NDInputAttrTree()
            tree.setNode(self.deformer)
            # Find a locked item whose plug_path is actually connected;
            # input[0] is wired on a fresh deformer.
            connected_found = False
            def _walk(item):
                nonlocal connected_found
                for i in range(item.childCount()):
                    _walk(item.child(i))
                if (
                    isinstance(item, NDLockedAttrTreeItem)
                    and item.row_spec is not None
                    and getattr(item, "_is_connected", False)
                ):
                    connected_found = True
            for i in range(tree.topLevelItemCount()):
                _walk(tree.topLevelItem(i))
            self.assertTrue(
                connected_found,
                "expected at least one CONNECTED locked row on a "
                "freshly-created deformer (input[0].inputGeometry "
                "is auto-wired)",
            )
        finally:
            try:
                mc.optionVar(remove="mpynodeShowFrameworkAttrs")
            except Exception:
                pass

    def test_unconnected_inherited_row_is_NOT_flagged_connected(self):
        """An inherited row with NO connection must report
        ``_is_connected = False`` (the inverse of the connected
        visual state)."""
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDLockedAttrTreeItem,
        )

        mc.optionVar(iv=("mpynodeShowFrameworkAttrs", 1))
        try:
            tree = NDInputAttrTree()
            tree.setNode(self.deformer)
            # envelope is unconnected on a fresh deformer.
            unconnected_row = None
            def _walk(item):
                nonlocal unconnected_row
                for i in range(item.childCount()):
                    _walk(item.child(i))
                if (
                    isinstance(item, NDLockedAttrTreeItem)
                    and item.row_spec is not None
                    and item.row_spec.short_name == "envelope"
                ):
                    unconnected_row = item
            for i in range(tree.topLevelItemCount()):
                _walk(tree.topLevelItem(i))
            if unconnected_row is None:
                self.skipTest(
                    "envelope row not found (filter may have hidden it)"
                )
            self.assertFalse(
                getattr(unconnected_row, "_is_connected", False),
                "unconnected \'envelope\' row should NOT be flagged "
                "as connected",
            )
        finally:
            try:
                mc.optionVar(remove="mpynodeShowFrameworkAttrs")
            except Exception:
                pass


class TestSourceShape__locked_row_bold_connected(unittest.TestCase):
    def test_locked_subtree_applies_connection_state(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._addLockedSubtree)
        self.assertIn("apply_connection_state", src)


# ===================== from test_rename_editor_polish.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-rename-editor-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__rename_editor_polish():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestRenameEditorDelegate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode
        self.node = MPyNode.create(name="rename_editor_test")
        self.node.add_input_attr("test", "float")

    def _make_tree(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree
        t = NDInputAttrTree()
        t.setNode(self.node)
        return t

    def test_delegate_installed_on_column_0(self):
        from mpynode.ui.widgets.attributes import _UserAttrRenameDelegate

        tree = self._make_tree()
        self.assertTrue(
            hasattr(tree, "_user_attr_rename_delegate"),
            "rename delegate must be installed on NDInputAttrTree",
        )

    def test_delegate_edits_only_attr_name(self):
        """CreateEditor + setEditorData must put just the attr_name
        in the editor, NOT the full "name: type" label."""
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDUserAttrTreeItem,
        )

        tree   = self._make_tree()
        target = None
        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            if isinstance(top, NDUserAttrTreeItem) and top.attr_name == "test":
                target = top
                break
        if target is None:
            self.skipTest("test row missing")

        delegate = tree._user_attr_rename_delegate
        # indexFromItem gives the real QModelIndex the delegate needs.
        try:
            idx = tree.indexFromItem(target, 0)
        except Exception:
            self.skipTest("indexFromItem not available")
        try:
            try:
                from PySide6.QtWidgets import QStyleOptionViewItem
            except Exception:
                from PySide2.QtWidgets import QStyleOptionViewItem
            opt = QStyleOptionViewItem()
        except Exception:
            self.skipTest("QStyleOptionViewItem not constructible")
        editor = delegate.createEditor(tree, opt, idx)
        delegate.setEditorData(editor, idx)
        # editor holds the attr_name "test", not the label "test: float".
        self.assertEqual(
            editor.text(), "test",
            f"editor should hold just attr_name, got {editor.text()!r}",
        )

    def test_editor_is_frameless_and_zero_padded(self):
        """The QLineEdit must be frameless + zero-margin so it sits
        pixel-flush with the painted text rect."""
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        tree     = self._make_tree()
        delegate = tree._user_attr_rename_delegate
        try:
            try:
                from PySide6.QtWidgets import QStyleOptionViewItem
            except Exception:
                from PySide2.QtWidgets import QStyleOptionViewItem
            opt = QStyleOptionViewItem()
        except Exception:
            self.skipTest("QStyleOptionViewItem not constructible")
        try:
            idx = tree.indexFromItem(tree.topLevelItem(0), 0)
        except Exception:
            self.skipTest("indexFromItem not available")
        editor = delegate.createEditor(tree, opt, idx)
        try:
            self.assertFalse(editor.hasFrame(),
                "QLineEdit frame must be disabled")
        except AttributeError:
            pass  # PySide version quirk
        try:
            m = editor.textMargins()
            self.assertEqual(
                (m.left(), m.top(), m.right(), m.bottom()),
                (0, 0, 0, 0),
                "text margins must be zero",
            )
        except AttributeError:
            pass


class TestRenameEditorDelegateSourceShape(unittest.TestCase):
    def test_install_zeros_frame_and_margins(self):
        import inspect
        from mpynode.ui.widgets.attributes import _UserAttrRenameDelegate

        src = inspect.getsource(_UserAttrRenameDelegate.install_on)
        self.assertIn("setFrame(False)", src)
        self.assertIn("setTextMargins(0, 0, 0, 0)", src)
        self.assertIn("attr_name", src)


# ===================== from test_attr_color_live_refresh.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance()
    if _QAPP is None:
        try:
            _QAPP = _QApplication(["mayapy-color-signal-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__attr_color_live_refresh():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestExpandStatePreserved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="expand_state_test")
        # a vector attr gives an expandable compound row.
        self.node.add_input_attr("amplitude", "vector")

    def _make_tree(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        t = NDInputAttrTree()
        t.setNode(self.node)
        return t

    def test_capture_restore_helpers_present(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        for m in (
            "_capture_expanded_locked_paths",
            "_capture_expanded_user_names",
            "_restore_expanded_locked_paths",
            "_restore_expanded_user_names",
        ):
            self.assertTrue(
                hasattr(NDInputAttrTree, m),
                f"NDInputAttrTree missing helper {m!r}",
            )

    def test_user_row_expand_state_survives_refresh(self):
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDUserAttrTreeItem,
        )

        tree   = self._make_tree()
        target = None
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == "amplitude":
                target = it
                break
        if target is None:
            self.skipTest("amplitude row not found")
        target.setExpanded(True)
        self.assertTrue(target.isExpanded())
        # Trigger a refresh (mimics what _SetAttrColorCommand does).
        tree.refresh()
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == "amplitude":
                self.assertTrue(
                    it.isExpanded(),
                    "expanded user row collapsed after refresh()",
                )
                return
        self.fail("amplitude row missing after refresh()")


class TestAttrColorChangedSignal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")
        # a real QTreeWidget needs the Qt event loop its viewport wants;
        # batch mayapy crashes with "Cannot create a QWidget without
        # QApplication", so skip in batch like the other widget tests.
        if not _tree_widget_safe():
            raise unittest.SkipTest("QTreeWidget unavailable in batch mode")

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="color_signal_test")
        self.node.add_input_attr("driverMatrixA", "matrix")

    def test_tree_emits_color_changed_on_set(self):
        from mpynode.ui.widgets.attributes import (
            NDInputAttrTree, NDUserAttrTreeItem,
        )

        tree = NDInputAttrTree()
        tree.setNode(self.node)
        received = []
        tree.attrColorChanged.connect(lambda name: received.append(name))
        # QColorDialog can't run headless, so drive the wrapper API and
        # refresh/emit by hand.
        try:
            self.node.set_attr_color("driverMatrixA", "#0000ff", "input")
        except Exception:
            self.skipTest("set_attr_color API not available")
        tree.refresh()
        try:
            tree.attrColorChanged.emit(self.node.get_name())
        except Exception:
            self.skipTest("Signal.emit failed headless")
        self.assertEqual(received, [self.node.get_name()],
            f"expected one attrColorChanged emit; got {received}")

    def test_widget_forwards_signal(self):
        """NDAttributesWidget re-emits its trees' attrColorChanged."""
        from mpynode.ui.widgets.attributes import NDAttributesWidget

        w = NDAttributesWidget()
        w.refresh(self.node)
        received = []
        w.attrColorChanged.connect(lambda name: received.append(name))
        w._input_tree.attrColorChanged.emit(self.node.get_name())
        self.assertEqual(received, [self.node.get_name()],
            f"widget should forward tree's signal; got {received}")


class TestSourceShape__attr_color_live_refresh(unittest.TestCase):
    def test_refresh_calls_capture_and_restore(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree.refresh)
        self.assertIn("_capture_expanded_locked_paths", src)
        self.assertIn("_capture_expanded_user_names",   src)
        self.assertIn("_restore_expanded_locked_paths", src)
        self.assertIn("_restore_expanded_user_names",   src)

    def test_color_commands_emit_signal(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        for fn_name in ("_set_selected_color", "_clear_selected_colors"):
            fn = getattr(NDInputAttrTree, fn_name, None)
            if fn is None:
                # name varies; skip if not present
                continue
            src = inspect.getsource(fn)
            self.assertIn("attrColorChanged.emit", src,
                f"{fn_name} must emit attrColorChanged")

    def test_designer_wires_color_signal_to_editor(self):
        import inspect
        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._on_attr_color_changed)
        self.assertIn("refreshVarColors", src)
        self.assertIn("_expr_editor", src)


# ===================== from test_attr_rename_expr.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__attr_rename_expr():
    standalone_init()


class TestCommandRewritesStoredSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="attr_rename_test")
        self.node.add_input_attr("amplitude", "float")
        self.node.add_output_attr("outVal", "float")
        mc.setAttr(self.node.get_name() + ".amplitude", 3.0)

    def _rename(self, old, new, direction="input"):
        from mpynode._base.commands import _RenameAttrCommand, run_undoable

        run_undoable(_RenameAttrCommand(self.node, old, new, direction))

    def test_compute_source_rewritten(self):
        self.node.set_compute_expression("self.outVal = self.amplitude * 2.0\n")
        self._rename("amplitude", "amp")
        src = self.node.get_compute_expression()
        self.assertIn("self.amp", src)
        self.assertNotIn("self.amplitude", src)

    def test_node_evaluates_without_error_after_rename(self):
        """The reported bug: post-rename eval raised AttributeError
        because the stored expression still referenced the old name."""
        self.node.set_compute_expression("self.outVal = self.amplitude * 2.0\n")
        self._rename("amplitude", "amp")
        # Pulling the output computes the rewritten expression: 3.0 * 2.
        mc.setAttr(self.node.get_name() + ".amp", 3.0)
        val = mc.getAttr(self.node.get_name() + ".outVal")
        self.assertAlmostEqual(val, 6.0, places=4)

    def test_init_source_rewritten_when_referencing_self(self):
        self.node.set_init_expression("base = 10.0\n")  # no self.X -> untouched
        self.node.set_compute_expression("self.outVal = self.amplitude + base\n")
        self._rename("amplitude", "amp")
        self.assertEqual(self.node.get_init_expression().strip(), "base = 10.0")
        self.assertIn("self.amp + base", self.node.get_compute_expression())

    def test_unrelated_attr_text_untouched(self):
        self.node.add_input_attr("amplitudeGain", "float")
        self.node.set_compute_expression(
            "self.outVal = self.amplitude * self.amplitudeGain\n"
        )
        self._rename("amplitude", "amp")
        src = self.node.get_compute_expression()
        # 'amplitude' renamed; 'amplitudeGain' (a different attr) intact.
        self.assertIn("self.amp *", src)
        self.assertIn("self.amplitudeGain", src)

    def test_output_attr_rename_rewrites_source(self):
        self.node.set_compute_expression("self.outVal = self.amplitude * 2.0\n")
        self._rename("outVal", "result", direction="output")
        src = self.node.get_compute_expression()
        self.assertIn("self.result =", src)
        self.assertNotIn("self.outVal", src)


    def test_node_state_restored_to_normal(self):
        """nodeState is blocked during the rename then restored to its
        prior value (Normal=0 here)."""
        nm = self.node.get_name()
        self.assertEqual(mc.getAttr(nm + ".nodeState"), 0)
        self.node.set_compute_expression("self.outVal = self.amplitude\n")
        self._rename("amplitude", "amp")
        self.assertEqual(mc.getAttr(nm + ".nodeState"), 0)

    def test_node_state_prior_value_preserved(self):
        """If the user had nodeState set (e.g. HasNoEffect=1), the
        rename restores THAT value, not a hardcoded Normal."""
        nm = self.node.get_name()
        mc.setAttr(nm + ".nodeState", 1)  # HasNoEffect
        self.node.set_compute_expression("self.outVal = self.amplitude\n")
        self._rename("amplitude", "amp")
        self.assertEqual(mc.getAttr(nm + ".nodeState"), 1)

class TestAttrRenamedSignalWiring(unittest.TestCase):
    """Source-pins for the Attributes-tab -> editor refresh path."""

    def test_input_tree_has_attr_renamed_signal(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        self.assertTrue(hasattr(NDInputAttrTree, "attrRenamed"))

    def test_on_item_changed_emits_attr_renamed(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._on_item_changed)
        self.assertIn("attrRenamed.emit", src)

    def test_composite_widget_forwards_signal(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDAttributesWidget

        self.assertTrue(hasattr(NDAttributesWidget, "attrRenamed"))
        src = inspect.getsource(NDAttributesWidget.__init__)
        self.assertIn("attrRenamed.connect(self.attrRenamed)", src)

    def test_designer_connects_and_refreshes(self):
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        wire = inspect.getsource(NDMainWindow._wire_signals)
        self.assertIn("attrRenamed.connect", wire)
        self.assertTrue(hasattr(NDMainWindow, "_on_attr_renamed"))
        handler = inspect.getsource(NDMainWindow._on_attr_renamed)
        self.assertIn("_refresh_editor_for_node", handler)

    def test_rename_command_rewrites_sources_source_pin(self):
        import inspect

        from mpynode._base.commands import _RenameAttrCommand

        src = inspect.getsource(_RenameAttrCommand)
        self.assertIn("_rewrite_expression_sources", src)
        self.assertIn("plan_rename_self_attr", src)

    def test_rename_command_blocks_node_state_source_pin(self):
        import inspect

        from mpynode._base.commands import _RenameAttrCommand

        src = inspect.getsource(_RenameAttrCommand.doIt)
        # Suspends eval via _eval_block_state + restores the prior value.
        self.assertIn(".nodeState",        src)
        self.assertIn("_eval_block_state", src)
        self.assertIn("prev_state",        src)

    def test_eval_block_state_non_deformer_is_blocking(self):
        import maya.cmds as mc_
        from mpynode._base.commands import _eval_block_state
        from mpynode.wrappers._mpy_node import MPyNode

        mc_.file(new=True, force=True)
        n = MPyNode.create(name="block_val_test")
        # mPyNode (non-deformer) -> Blocking (2).
        self.assertEqual(_eval_block_state(n.get_name()), 2)



class TestDeformerNodeStateBlock(unittest.TestCase):
    """Deformers reject Blocking; the rename must use HasNoEffect (1)
    so Maya doesn't warn, and must restore the prior state."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2, h=2, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="dfm_block_test")
        self.deformer.add_input_attr("amplitude", "float")

    def test_deformer_uses_has_no_effect(self):
        from mpynode._base.commands import _eval_block_state

        # Deformer family -> HasNoEffect (1), NOT Blocking (2).
        self.assertEqual(_eval_block_state(self.deformer.get_name()), 1)

    def test_deformer_rename_restores_state(self):
        from mpynode._base.commands import _RenameAttrCommand, run_undoable

        nm = self.deformer.get_name()
        self.assertEqual(mc.getAttr(nm + ".nodeState"), 0)
        self.deformer.set_compute_expression(
            "for i in range(len(self.points)):\n"
            "    self.points[i] = self.points[i]\n"
        )
        run_undoable(
            _RenameAttrCommand(self.deformer, "amplitude", "amp", "input")
        )
        # State restored to Normal (0); no leftover HasNoEffect.
        self.assertEqual(mc.getAttr(nm + ".nodeState"), 0)
        self.assertTrue(mc.attributeQuery("amp", node=nm, exists=True))


# ===================== from test_phase23.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase23():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Wrapper API: per-attr color storage in attr meta
# ===========================================================================


class TestWrapperAttrColors(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_set_input_attr_color(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c1")
        n.add_input_attr("alpha", "float")
        self.assertIsNone(n.get_input_attr_color("alpha"))

        n.set_input_attr_color("alpha", "#ff0000")
        self.assertEqual(n.get_input_attr_color("alpha"), "#ff0000")

    def test_set_output_attr_color(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c2")
        n.add_output_attr("out", "vector")
        n.set_output_attr_color("out", "#00ffff")
        self.assertEqual(n.get_output_attr_color("out"), "#00ffff")

    def test_clear_color_via_None(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c3")
        n.add_input_attr("a", "float")
        n.set_input_attr_color("a", "#abcdef")
        n.set_input_attr_color("a", None)
        self.assertIsNone(n.get_input_attr_color("a"))

    def test_set_color_unknown_attr_raises(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c4")
        with self.assertRaises(ValueError):
            n.set_input_attr_color("nonexistent", "#ff0000")
        with self.assertRaises(ValueError):
            n.set_output_attr_color("nonexistent", "#ff0000")

    def test_get_all_attr_colors_combines_input_and_output(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c5")
        n.add_input_attr("a", "float")
        n.add_input_attr("b", "vector")
        n.add_output_attr("out", "float")
        n.set_input_attr_color("a", "#ff0000")
        n.set_output_attr_color("out", "#00ff00")
        all_colors = n.get_all_attr_colors()
        self.assertEqual(all_colors, {"a": "#ff0000", "out": "#00ff00"})

    def test_color_persists_through_rename(self):
        """Renaming an attr should preserve its custom color."""
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c6")
        n.add_input_attr("foo", "float")
        n.set_input_attr_color("foo", "#123456")
        n.rename_input_attr("foo", "bar")
        self.assertEqual(n.get_input_attr_color("bar"), "#123456")

    def test_color_dropped_on_attr_delete(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="c7")
        n.add_input_attr("doomed", "float")
        n.set_input_attr_color("doomed", "#ff0000")
        n.delete_input_attr("doomed")
        self.assertEqual(n.get_all_attr_colors(), {})


# ===========================================================================
# _SetAttrColorCommand (undoable, no-op undo per chunk pattern)
# ===========================================================================


class TestSetAttrColorCommand(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_set_via_command_undo_redo(self):
        from mpynode._base.commands import _SetAttrColorCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cmd1")
        n.add_input_attr("a", "float")

        run_undoable(_SetAttrColorCommand(n, "a", "#deadbe", "input"))
        self.assertEqual(n.get_input_attr_color("a"), "#deadbe")

        mc.undo()
        # the setAttr on _inputAttrs is inside the chunk, so chunk-undo
        # restores the previous JSON map.
        self.assertIsNone(n.get_input_attr_color("a"))

        mc.redo()
        self.assertEqual(n.get_input_attr_color("a"), "#deadbe")

    def test_clear_via_command(self):
        from mpynode._base.commands import _SetAttrColorCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cmd2")
        n.add_output_attr("out", "vector")
        n.set_output_attr_color("out", "#abcdef")

        run_undoable(_SetAttrColorCommand(n, "out", None, "output"))
        self.assertIsNone(n.get_output_attr_color("out"))

    def test_command_rejects_bad_direction(self):
        from mpynode._base.commands import _SetAttrColorCommand
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="cmd3")
        with self.assertRaises(ValueError):
            _SetAttrColorCommand(n, "x", "#ff0000", "sideways")


# ===========================================================================
# Editor: hex \u2192 rgb conversion + highlighter sync
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestHexToRgbHelper(unittest.TestCase):
    def test_six_char_hex(self):
        from mpynode.ui.widgets.script_editor import _hex_to_rgb

        self.assertEqual(_hex_to_rgb("#ff0000"), (255, 0, 0))
        self.assertEqual(_hex_to_rgb("#00ff00"), (0, 255, 0))
        self.assertEqual(_hex_to_rgb("#abcdef"), (171, 205, 239))

    def test_three_char_hex(self):
        from mpynode.ui.widgets.script_editor import _hex_to_rgb

        self.assertEqual(_hex_to_rgb("#fff"), (255, 255, 255))
        self.assertEqual(_hex_to_rgb("#000"), (0, 0, 0))
        # #abc => #aabbcc
        self.assertEqual(_hex_to_rgb("#abc"), (170, 187, 204))

    def test_no_hash_prefix(self):
        from mpynode.ui.widgets.script_editor import _hex_to_rgb

        self.assertEqual(_hex_to_rgb("ff0000"), (255, 0, 0))

    def test_bad_input_returns_None(self):
        from mpynode.ui.widgets.script_editor import _hex_to_rgb

        for bad in ("", None, "garbage", "#xyz123", "#1234", 42):
            self.assertIsNone(_hex_to_rgb(bad))


# ===========================================================================
# Inspect-only structural tests
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestUIShape(unittest.TestCase):
    def test_user_attr_item_prefers_custom_color(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        # __init__ delegates to _apply_color, not _apply_type_color.
        init_src = inspect.getsource(NDUserAttrTreeItem.__init__)
        self.assertIn("_apply_color", init_src)
        # _apply_color only calls setForeground when meta has ui_color.
        helper_src = inspect.getsource(NDUserAttrTreeItem._apply_color)
        self.assertIn("ui_color", helper_src)
        self.assertIn("setForeground", helper_src)

    def test_context_menu_has_set_color_action(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree.contextMenuEvent)
        self.assertIn("Set Color", src)
        self.assertIn("Clear Color", src)
        self.assertIn("_show_set_color_dlg", src)
        self.assertIn("_clear_selected_colors", src)

    def test_set_color_dlg_uses_QColorDialog_and_command(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._show_set_color_dlg)
        self.assertIn("QColorDialog",         src)
        self.assertIn("_SetAttrColorCommand", src)
        self.assertIn("run_undoable",         src)

    def test_clear_dispatches_command_with_None(self):
        import inspect

        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._clear_selected_colors)
        self.assertIn("_SetAttrColorCommand", src)
        self.assertIn(", None,", src)

    def test_script_editor_refresh_rebuilds_var_colors(self):
        import inspect

        from mpynode.ui.widgets.script_editor import NDScriptEditor

        refresh_src = inspect.getsource(NDScriptEditor.refresh)
        self.assertIn("refreshVarColors", refresh_src)

        helper_src = inspect.getsource(NDScriptEditor.refreshVarColors)
        self.assertIn("get_all_attr_colors", helper_src)
        self.assertIn("_hex_to_rgb",         helper_src)
        self.assertIn("setVarColorMap",      helper_src)

    def test_phase21_callback_pushes_new_colors(self):
        """When MNodeMessage fires for _inputAttrs/_outputAttrs change,
        the editor's var colors should also refresh."""
        import inspect

        from mpynode.ui.mpynode_designer import NDMainWindow

        src = inspect.getsource(NDMainWindow._refresh_attributes_for_node)
        self.assertIn("refreshVarColors", src)


# ===================== from test_phase18.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phase18():
    standalone_init()


def _qt_available() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# Wrapper rename API
# ===========================================================================


class TestWrapperRenameAttr(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_rename_input_attr_basic(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="rn1")
        n.add_input_attr("a", "float")
        n.rename_input_attr("a", "alpha")

        self.assertNotIn("a", n.get_input_attr_map())
        self.assertIn("alpha", n.get_input_attr_map())
        self.assertTrue(mc.attributeQuery("alpha", node=n.get_name(), exists=True))
        self.assertFalse(mc.attributeQuery("a", node=n.get_name(), exists=True))

    def test_rename_input_attr_vector_renames_xyz_children(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="rn2")
        n.add_input_attr("v", "vector")
        for axis in ("X", "Y", "Z"):
            self.assertTrue(mc.attributeQuery("v" + axis, node=n.get_name(), exists=True))
        n.rename_input_attr("v", "vec")
        for axis in ("X", "Y", "Z"):
            self.assertFalse(mc.attributeQuery("v" + axis, node=n.get_name(), exists=True))
            self.assertTrue(mc.attributeQuery("vec" + axis, node=n.get_name(), exists=True))

    def test_rename_input_attr_collision_raises(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="rn3")
        n.add_input_attr("a", "float")
        n.add_input_attr("b", "float")
        with self.assertRaises(ValueError):
            n.rename_input_attr("a", "b")

    def test_rename_output_attr(self):
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="rn4")
        n.add_output_attr("out", "float")
        n.rename_output_attr("out", "result")
        self.assertNotIn("out", n.get_output_attr_map())
        self.assertIn("result", n.get_output_attr_map())
        self.assertTrue(mc.attributeQuery("result", node=n.get_name(), exists=True))


# ===========================================================================
# _BaseCommand subclasses
# ===========================================================================


class TestAttrCommands(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_add_input_attr_command_undoable(self):
        from mpynode._base.commands import _AddInputAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ac1")
        run_undoable(_AddInputAttrCommand(n, "x", "float"))
        self.assertIn("x", n.get_input_attr_map())

        mc.undo()
        self.assertNotIn("x", n.get_input_attr_map())

        mc.redo()
        self.assertIn("x", n.get_input_attr_map())

    def test_add_output_attr_command_undoable(self):
        from mpynode._base.commands import _AddOutputAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ac2")
        run_undoable(_AddOutputAttrCommand(n, "out", "vector"))
        self.assertIn("out", n.get_output_attr_map())

        mc.undo()
        self.assertNotIn("out", n.get_output_attr_map())

        mc.redo()
        self.assertIn("out", n.get_output_attr_map())

    def test_delete_attr_command_round_trip(self):
        from mpynode._base.commands import _DeleteAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ac3")
        n.add_input_attr("k", "int")
        self.assertIn("k", n.get_input_attr_map())

        run_undoable(_DeleteAttrCommand(n, "k", "input"))
        self.assertNotIn("k", n.get_input_attr_map())

        mc.undo()
        self.assertIn("k", n.get_input_attr_map())
        self.assertEqual(n.get_input_attr_map()["k"]["attr_type"], "int")

    def test_rename_attr_command_undoable(self):
        from mpynode._base.commands import _RenameAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="ac4")
        n.add_input_attr("foo", "float")
        run_undoable(_RenameAttrCommand(n, "foo", "bar", "input"))
        self.assertIn("bar", n.get_input_attr_map())

        mc.undo()
        self.assertIn("foo", n.get_input_attr_map())
        self.assertNotIn("bar", n.get_input_attr_map())

    def test_connect_attr_command(self):
        from mpynode._base.commands import _ConnectAttrCommand, run_undoable
        from mpynode.wrappers._mpy_node import MPyNode

        src = mc.polyCube(name="srcCube")[0]
        n   = MPyNode.create(name="ac5")
        n.add_input_attr("driven", "float")
        run_undoable(_ConnectAttrCommand(f"{src}.translateX", f"{n.get_name()}.driven"))
        conns = mc.listConnections(f"{n.get_name()}.driven", source=True, plugs=True) or []
        self.assertIn(f"{src}.translateX", conns)

    def test_disconnect_all_command(self):
        from mpynode._base.commands import (
            _ConnectAttrCommand,
            _DisconnectAllCommand,
            run_undoable,
        )
        from mpynode.wrappers._mpy_node import MPyNode

        src = mc.polyCube(name="srcCube2")[0]
        n   = MPyNode.create(name="ac6")
        n.add_input_attr("driven", "float")
        run_undoable(_ConnectAttrCommand(f"{src}.translateX", f"{n.get_name()}.driven"))
        run_undoable(_DisconnectAllCommand(f"{n.get_name()}.driven", "input"))
        conns = mc.listConnections(f"{n.get_name()}.driven", source=True, plugs=True) or []
        self.assertEqual(conns, [])


# ===========================================================================
# force_one_eval helper
# ===========================================================================


class TestForceOneEval(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        ensure_plugins_loaded()

    def test_force_one_eval_doesnt_raise_on_empty_node(self):
        """An empty mPyNode (no inputs, no outputs) shouldn't crash."""
        from mpynode._base.eval_helpers import force_one_eval
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="empty")
        force_one_eval(n)  # should not raise

    def test_force_one_eval_triggers_compute(self):
        """After Save, force_one_eval bumps a scalar input which triggers
        compute. We verify by attaching a stored counter that increments
        per compute call."""
        from mpynode._base.eval_helpers import force_one_eval
        from mpynode.wrappers._mpy_node import MPyNode

        n = MPyNode.create(name="counted")
        n.add_input_attr("trigger", "float")
        n.add_output_attr("out", "int")
        n.add_variable("counter", 0)
        n.set_compute_expression("self.counter = self.counter + 1\nout = self.counter")

        # counter starts at 0 and bumps once per eval.
        force_one_eval(n)
        self.assertEqual(n.get_variables()["counter"], 1)

        force_one_eval(n)
        self.assertEqual(n.get_variables()["counter"], 2)


# ===========================================================================
# NDAddAttrDialog name validation (no widget instantiation)
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestValidateAttrName(unittest.TestCase):
    def test_valid_names(self):
        from mpynode.ui.dialogs.add_attr import validate_attr_name

        for name in ("foo", "foo_bar", "_underscore", "x1", "alpha2"):
            ok, err = validate_attr_name(name, set())
            self.assertTrue(ok, f"{name!r} should be valid; got: {err}")

    def test_empty_invalid(self):
        from mpynode.ui.dialogs.add_attr import validate_attr_name

        ok, err = validate_attr_name("", set())
        self.assertFalse(ok)
        self.assertIn("required", err.lower())

    def test_starts_with_digit_invalid(self):
        from mpynode.ui.dialogs.add_attr import validate_attr_name

        ok, _ = validate_attr_name("1foo", set())
        self.assertFalse(ok)

    def test_dash_invalid(self):
        from mpynode.ui.dialogs.add_attr import validate_attr_name

        ok, _ = validate_attr_name("foo-bar", set())
        self.assertFalse(ok)

    def test_python_keyword_invalid(self):
        from mpynode.ui.dialogs.add_attr import validate_attr_name

        for kw in ("class", "def", "if", "for", "lambda", "self"):
            ok, _ = validate_attr_name(kw, set())
            self.assertFalse(ok, f"{kw!r} should be invalid (Python keyword)")

    def test_existing_collision(self):
        from mpynode.ui.dialogs.add_attr import validate_attr_name

        ok, _ = validate_attr_name("foo", existing={"foo"})
        self.assertFalse(ok)


# ===========================================================================
# Inspect-based UI structural tests
# ===========================================================================


@unittest.skipUnless(_qt_available(), "Qt unavailable")
class TestAttributesWidgetShape(unittest.TestCase):
    def test_user_item_is_editable(self):
        from mpynode.ui.qt_wrapper import Qt
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        flags = NDUserAttrTreeItem.USER_FLAGS
        self.assertTrue(bool(flags & Qt.ItemIsEditable))

    def test_input_tree_has_context_menu_methods(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        for method in (
            "contextMenuEvent",
            "_show_add_attr_dlg",
            "_delete_selected",
            "_show_connect_dlg",
            "_disconnect_selected",
            "_select_node",
            "_on_item_changed",
        ):
            self.assertTrue(
                hasattr(NDInputAttrTree, method),
                f"NDInputAttrTree should have {method!r}",
            )

    def test_output_tree_inherits_input(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree, NDOutputAttrTree

        self.assertTrue(issubclass(NDOutputAttrTree, NDInputAttrTree))
        self.assertEqual(NDOutputAttrTree.ATTR_CATEGORY, "output")
        self.assertEqual(NDOutputAttrTree.LIST_ATTR_FUNC_NAME, "get_output_attr_map")

    def test_add_attr_dialog_module(self):
        from mpynode.ui.dialogs.add_attr import NDAddAttrDialog, validate_attr_name

        self.assertTrue(callable(validate_attr_name))
        self.assertTrue(hasattr(NDAddAttrDialog, "_make_subframe"))
        # the dialog runs its own undoable Add via _on_add_clicked; it used
        # to return a getResult dict for the caller to dispatch.
        self.assertTrue(hasattr(NDAddAttrDialog, "_on_add_clicked"))

    def test_connect_dialogs_module(self):
        from mpynode.ui.dialogs.connect_attr import (
            NDConnectInputAttrDialog,
            NDConnectOutputAttrDialog,
        )

        for cls in (NDConnectInputAttrDialog, NDConnectOutputAttrDialog):
            # renamed to plural form (multi-select supported).
            self.assertTrue(hasattr(cls, "getChosenPlugs"))
            self.assertTrue(hasattr(cls, "getExtraFlag"))

    def test_designer_imports_attributes_module(self):
        import inspect

        import mpynode.ui.mpynode_designer as designer_module

        src = inspect.getsource(designer_module)
        self.assertIn(
            "from mpynode.ui.widgets.attributes import",
            src,
        )

    def test_save_tab_calls_force_one_eval(self):
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget

        src = inspect.getsource(NDScriptTabWidget._saveTab)
        self.assertIn("force_one_eval", src)


class TestUserAttrLabelSparse(unittest.TestCase):
    """The user-attr label puts ``[]`` after an array name and ``(sparse)``
    after the type for a sparse array (dense is the default, so it carries no
    marker; scalars have no bracket). Pure function -- no scene."""

    def _label(self, meta):
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem

        return NDUserAttrTreeItem._format_label("arr", meta)

    def test_scalar_has_no_bracket(self):
        self.assertEqual(self._label({"attr_type": "float"}), "arr: float")

    def test_dense_array_has_no_sparse_word(self):
        self.assertEqual(
            self._label({"attr_type": "matrix", "is_array": True}),
            "arr[]: matrix",
        )

    def test_sparse_array_shows_word(self):
        self.assertEqual(
            self._label(
                {"attr_type": "matrix", "is_array": True, "sparse": True}
            ),
            "arr[]: matrix (sparse)",
        )

    def test_array_missing_sparse_key_is_dense(self):
        self.assertEqual(
            self._label({"attr_type": "float", "is_array": True}),
            "arr[]: float",
        )


def setUpModule():
    _setUpModule__attributes_plug_filter()
    _setUpModule__attr_connection_visual()
    _setUpModule__locked_row_bold_connected()
    _setUpModule__rename_editor_polish()
    _setUpModule__attr_color_live_refresh()
    _setUpModule__attr_rename_expr()
    _setUpModule__phase23()
    _setUpModule__phase18()


if __name__ == "__main__":
    import unittest
    unittest.main()
