"""Attributes/Variables-Internal/Storage panels rendering the plug tree

Consolidated from: test_phaseM_0_attributes_widget.py, test_phaseO_0_storage_tree.py, test_phaseG_6_variables_widget.py.
"""

from __future__ import annotations

# ===================== from test_phaseM_0_attributes_widget.py =====================
import os

# Qt MUST come before standalone init -- see module docstring.
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
            _QAPP = _QApplication(["mayapy-phaseM-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseM_0_attributes_widget():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


# ===========================================================================
# Treeify -- Qt-free
# ===========================================================================


class TestAllowlistWithAncestors(unittest.TestCase):
    """``_allowlist_with_ancestors`` keeps allowlisted rows AND the structural
    ancestor rows they need to nest, so an allowlisted deep plug (e.g.
    inputGeometry) does not orphan to the tree root when its intermediate
    element/compound rows aren't themselves allowlisted."""

    @staticmethod
    def _row(plug_path, parent_path, short_name, ua=False):
        from types import SimpleNamespace

        return SimpleNamespace(plug_path=plug_path, parent_path=parent_path,
                               short_name=short_name, is_user_added=ua)

    def test_deep_allowlisted_leaf_readds_its_ancestors(self):
        from mpynode.ui.widgets.attributes import _allowlist_with_ancestors

        rows = [
            self._row("input", "", "input"),
            self._row("input[0]", "input", "input[0]"),
            self._row("input[0].inputGeometry", "input[0]", "inputGeometry"),
        ]
        # Only the deep leaf is allowlisted; both ancestors are NOT.
        kept = _allowlist_with_ancestors(rows, {"inputGeometry"})
        paths = [r.plug_path for r in kept]
        # All three survive, in the original depth-first order.
        self.assertEqual(
            paths, ["input", "input[0]", "input[0].inputGeometry"])

    def test_non_allowlisted_row_without_kept_descendant_is_dropped(self):
        from mpynode.ui.widgets.attributes import _allowlist_with_ancestors

        rows = [
            self._row("caching", "", "caching"),   # not allowlisted, no kids
            self._row("envelope", "", "envelope"),  # allowlisted
        ]
        kept = [r.plug_path for r in _allowlist_with_ancestors(rows, {"envelope"})]
        self.assertEqual(kept, ["envelope"])

    def test_user_added_deep_row_readds_ancestors(self):
        from mpynode.ui.widgets.attributes import _allowlist_with_ancestors

        rows = [
            self._row("weightList", "", "weightList"),
            self._row("weightList[0]", "weightList", "weightList[0]"),
            self._row("weightList[0].weights", "weightList[0]", "weights",
                      ua=True),
        ]
        kept = [r.plug_path for r in _allowlist_with_ancestors(rows, set())]
        self.assertEqual(
            kept, ["weightList", "weightList[0]", "weightList[0].weights"])


class TestTreeify(unittest.TestCase):
    """The L.0/M.0 ``treeify`` helper groups flat walker rows into a
    nested TreeNode list ready for QTreeWidgetItem construction."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="treeifytd")
        self.deformer.add_input_attr("amplitude", "vector")

    def test_treeify_returns_nested_tree(self):
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree, treeify

        rows = walk_plug_tree(self.deformer.get_name())
        tops = treeify(rows)
        self.assertGreater(len(tops), 0)
        # All top-level entries have parent_path == ""
        for t in tops:
            self.assertEqual(t.row.parent_path, "")

    def test_amplitude_compound_has_3_children(self):
        """Amplitude (user-added Double3) should treeify with 3
        children (amplitudeX/Y/Z)."""
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree, treeify

        rows = walk_plug_tree(self.deformer.get_name())
        tops = treeify(rows)
        amp_node = None
        for t in tops:
            if t.row.short_name == "amplitude":
                amp_node = t
                break
        self.assertIsNotNone(amp_node, "amplitude top-level node missing")
        child_names = sorted(c.row.short_name for c in amp_node.children)
        self.assertEqual(child_names, ["amplitudeX", "amplitudeY", "amplitudeZ"])

    def test_input_compound_multi_treeifies(self):
        """Input[0].inputGeometry should appear as input -> [0] ->
        inputGeometry in the tree."""
        from mpynode.ui.widgets.plug_tree_walker import walk_plug_tree, treeify

        rows = walk_plug_tree(self.deformer.get_name())
        tops = treeify(rows)

        def _find(node_list, short_name):
            for n in node_list:
                if n.row.short_name == short_name:
                    return n
            return None

        input_node = _find(tops, "input")
        self.assertIsNotNone(input_node)
        # The element row "input[0]" should be a child of "input".
        element_rows = [c for c in input_node.children if "[0]" in c.row.plug_path]
        self.assertGreater(len(element_rows), 0,
            "expected at least one input[i] element under the input multi")


# ===========================================================================
# Attributes widget (requires Qt)
# ===========================================================================


class TestAttributesWidgetWalker(unittest.TestCase):
    """The NDInputAttrTree / NDOutputAttrTree widgets now walk the
    live plug tree via _buildLockedTreeFromWalker. Inherited base-
    class plugs + user-added attrs both appear; compound children
    nest under their parent QTreeWidgetItem."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest(
                "Qt unavailable in this mayapy build; widget tests skipped"
            )

    def setUp(self):
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="attrtestdef")
        self.deformer.add_input_attr("amplitude", "vector")
        self.deformer.add_input_attr("driverMatrixA", "matrix")

    def _make_input_tree(self):
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        t = NDInputAttrTree()
        t.setNode(self.deformer)
        return t

    def _make_output_tree(self):
        from mpynode.ui.widgets.attributes import NDOutputAttrTree

        t = NDOutputAttrTree()
        t.setNode(self.deformer)
        return t

    def _flatten_tree(self, widget):
        from mpynode.ui.widgets.attributes import (
            NDLockedAttrTreeItem, NDUserAttrTreeItem,
        )

        out = []

        def _recurse(item, depth):
            kind = "USER" if isinstance(item, NDUserAttrTreeItem) else "INH"
            out.append((depth, kind, item.text(0)))
            for i in range(item.childCount()):
                _recurse(item.child(i), depth + 1)

        for i in range(widget.topLevelItemCount()):
            _recurse(widget.topLevelItem(i), 0)
        return out

    def test_input_tree_has_inherited_envelope(self):
        tree = self._make_input_tree()
        rows = self._flatten_tree(tree)
        labels = [r[2] for r in rows if r[1] == "INH"]
        self.assertTrue(
            any("envelope" in lbl for lbl in labels),
            f"expected inherited 'envelope' row; got labels: {labels}",
        )

    def test_input_tree_has_user_added_attrs(self):
        tree = self._make_input_tree()
        rows = self._flatten_tree(tree)
        user_labels = [r[2] for r in rows if r[1] == "USER"]
        names = [lbl.split(": ")[0].split("[", 1)[0] for lbl in user_labels]
        self.assertIn("driverMatrixA", names)
        self.assertIn("driverMatrixB", names) if False else None  # only A added
        self.assertIn("amplitude", names)

    def test_input_tree_nests_input_compound_multi(self):
        """Input[].something should appear as nested rows -- depth 0
        for 'input', depth 1 for '[0]', depth 2 for the children."""
        tree = self._make_input_tree()
        rows = self._flatten_tree(tree)
        depths_by_label = {r[2]: r[0] for r in rows}
        # Find input parent depth.
        input_depth = None
        for d, _kind, lbl in rows:
            if lbl.startswith("input["):
                input_depth = d
                break
        self.assertIsNotNone(input_depth, "input[] row missing")
        # Find inputGeometry child depth.
        ig_depth = None
        for d, _kind, lbl in rows:
            if lbl.startswith("inputGeometry"):
                ig_depth = d
                break
        self.assertIsNotNone(ig_depth, "inputGeometry row missing")
        self.assertGreater(ig_depth, input_depth,
            "inputGeometry should be DEEPER in the tree than input")

    def test_output_tree_has_outputGeometry(self):
        tree = self._make_output_tree()
        rows = self._flatten_tree(tree)
        labels = [r[2] for r in rows]
        self.assertTrue(
            any("outputGeometry" in lbl for lbl in labels),
            f"expected 'outputGeometry' row in OUTPUT tree; got labels: {labels}",
        )

    def test_no_orphaned_user_added_children(self):
        """Children of user-added compounds (e.g. amplitudeX under
        amplitude) must NOT appear as top-level inherited rows. They
        are owned by the user-added flat row."""
        tree = self._make_input_tree()
        rows = self._flatten_tree(tree)
        # At depth 0 with INH kind, none of the labels should start
        # with 'amplitudeX' / 'amplitudeY' / 'amplitudeZ'.
        for depth, kind, lbl in rows:
            if depth == 0 and kind == "INH":
                first_token = lbl.split(":", 1)[0].strip()
                self.assertNotIn(
                    first_token, ("amplitudeX", "amplitudeY", "amplitudeZ"),
                    "user-added compound child must not orphan as inherited row",
                )

    def test_user_added_items_remain_editable(self):
        from mpynode.ui.widgets.attributes import NDUserAttrTreeItem
        from mpynode.ui.qt_wrapper import Qt

        tree = self._make_input_tree()
        # Find the driverMatrixA user item.
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDUserAttrTreeItem) and it.attr_name == "driverMatrixA":
                self.assertTrue(it.flags() & Qt.ItemIsEditable,
                    "user-added rows must remain editable (inline rename)")
                return
        self.fail("driverMatrixA user-added row missing from tree")

    def test_inherited_items_are_locked(self):
        from mpynode.ui.widgets.attributes import NDLockedAttrTreeItem
        from mpynode.ui.qt_wrapper import Qt

        tree = self._make_input_tree()
        found_locked = False
        for i in range(tree.topLevelItemCount()):
            it = tree.topLevelItem(i)
            if isinstance(it, NDLockedAttrTreeItem):
                # Edit ops must NOT be enabled for inherited rows.
                self.assertFalse(
                    bool(it.flags() & Qt.ItemIsEditable),
                    "inherited rows must NOT be editable",
                )
                self.assertFalse(
                    bool(it.flags() & Qt.ItemIsSelectable),
                    "inherited rows must NOT be selectable (per LOCKED_FLAGS)",
                )
                found_locked = True
        self.assertTrue(found_locked,
            "expected at least one NDLockedAttrTreeItem (inherited row)")


class TestAttributesWidgetSourceShape(unittest.TestCase):
    """Source-grep pin: NDInputAttrTree must use walk_plug_tree,
    not the legacy build_locked_rows / get_recipe path."""

    def test_buildLockedTreeFromWalker_uses_walker(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDInputAttrTree

        src = inspect.getsource(NDInputAttrTree._buildLockedTreeFromWalker)
        self.assertIn("walk_plug_tree", src)
        self.assertIn("treeify", src)

    def test_locked_item_accepts_row_spec(self):
        import inspect
        from mpynode.ui.widgets.attributes import NDLockedAttrTreeItem

        sig = inspect.signature(NDLockedAttrTreeItem.__init__)
        self.assertIn("row_spec", sig.parameters)


# ===================== from test_phaseO_0_storage_tree.py =====================
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
            _QAPP = _QApplication(["mayapy-phaseO0-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseO_0_storage_tree():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


class TestStorageTreeRender(unittest.TestCase):
    """The Internal section renders nested compound children when
    _USE_PLUG_TREE_RENDER is True (default)."""

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest("Qt unavailable")

    def setUp(self):
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="o0_td")
        self.deformer.add_input_attr("amplitude", "vector")

    def _flag_set(self):
        """Build the widget + run refresh; return the populated
        QTreeWidget for inspection."""
        # Ensure env var isn't disabling the tree path.
        os.environ.pop("MPYNODE_FLAT_STORAGE", None)
        from mpynode.ui.widgets.variables import NDVariablesWidget

        w = NDVariablesWidget()
        w._py_node = self.deformer
        # Populate through whichever refresh entry point the widget exposes.
        if hasattr(w, "refresh"):
            try:
                w.refresh()
            except Exception:
                pass
        elif hasattr(w, "rebuild"):
            try:
                w.rebuild()
            except Exception:
                pass
        return w

    def test_dead_class_attr_removed(self):
        """``_USE_PLUG_TREE_RENDER`` toggled the (now-removed)
        plug-tree mini-browser branch. After the audit removed both
        the branch and the dead attribute, the
        class must no longer carry it."""
        from mpynode.ui.widgets.variables import NDVariablesWidget

        self.assertFalse(hasattr(NDVariablesWidget, "_USE_PLUG_TREE_RENDER"),
            "_USE_PLUG_TREE_RENDER should be deleted (its branch is gone)")

    def test_dead_helpers_removed(self):
        """The per-instance plug-tree helpers
        (``_collect_plug_tree`` / ``_add_plug_tree_node`` /
        ``_collect_plug_rows``) were thin wrappers around the
        module-level helpers, used only by the Pass-1-removed
        plug-tree mini-browser. They should be gone."""
        from mpynode.ui.widgets.variables import NDVariablesWidget

        for name in ("_collect_plug_tree", "_add_plug_tree_node", "_collect_plug_rows"):
            self.assertFalse(
                hasattr(NDVariablesWidget, name),
                f"NDVariablesWidget.{name} should be deleted",
            )

    def test_env_var_forces_flat(self):
        """(design-intent audit) The Variables tab no longer renders a
        Properties/Internal section: ``_populate_internal_section`` was
        DELETED. That plug-tree surface is now exclusively the Attributes
        tab's responsibility, so the Variables widget no longer walks the
        plug tree here at all -- which also makes the legacy
        ``MPYNODE_FLAT_STORAGE`` tree/flat toggle moot.

        Re-purposed assertion: confirm the method is GONE (so the widget
        cannot walk the plug tree via it) and that the obsolete env-var
        toggle is no longer referenced by the module.
        """
        import inspect
        from mpynode.ui.widgets import variables
        from mpynode.ui.widgets.variables import NDVariablesWidget

        # The plug-tree-walking Internal section renderer is gone entirely.
        self.assertFalse(
            hasattr(NDVariablesWidget, "_populate_internal_section"),
            "_populate_internal_section should be deleted; the Variables tab "
            "no longer renders the Properties/Internal plug-tree section",
        )
        # With no tree/flat renderer left, the env-var toggle that used to
        # switch between them is obsolete and must no longer appear.
        self.assertNotIn(
            "MPYNODE_FLAT_STORAGE", inspect.getsource(variables),
            "env var is obsolete; the Variables tab has no tree/flat toggle "
            "anymore",
        )


class TestPlugTreeHelperRelocated(unittest.TestCase):
    """Invariants for the module-level plug-tree helpers
    (relocated to plug_tree_walker.py)."""

    def test_back_compat_reexport_from_variables(self):
        """``collect_plug_rows`` + ``collect_plug_tree`` used to live
        in ``ui.widgets.variables`` and are imported from there by
        many existing call sites + tests. The audit relocated them to
        ``plug_tree_walker`` -- the old import path MUST keep
        working via back-compat re-export."""
        from mpynode.ui.widgets import variables, plug_tree_walker

        for name in ("collect_plug_rows", "collect_plug_tree",
                     "read_plug_value_text", "PLUG_BROWSER_BLACKLIST"):
            self.assertTrue(hasattr(variables, name),
                f"back-compat: {name} must still be importable from "
                f"mpynode.ui.widgets.variables")
            self.assertTrue(hasattr(plug_tree_walker, name),
                f"canonical: {name} must live in plug_tree_walker")
            # Same object, not a copy.
            self.assertIs(getattr(variables, name),
                          getattr(plug_tree_walker, name),
                          f"{name}: back-compat re-export must be the "
                          f"SAME object as the canonical definition")


# ===================== from test_phaseG_6_variables_widget.py =====================
import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseG_6_variables_widget():
    standalone_init()


class TestCollectPlugRows(unittest.TestCase):

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)

    def test_blacklist_filters_bookkeeping_plugs(self):
        from mpynode.ui.widgets.variables import collect_plug_rows

        n = mc.createNode("mPyNode")
        rows = collect_plug_rows(n)
        names = [r[0] for r in rows]
        for hidden in (
            "_computeSource",
            "_initSource",
            "_storedVarsList",
            "_storedVarsData",
            "_inputAttrs",
            "_outputAttrs",
        ):
            self.assertNotIn(hidden, names)

    def test_surfaces_native_message_plug(self):
        from mpynode.ui.widgets.variables import collect_plug_rows

        n = mc.createNode("mPyNode")
        rows = collect_plug_rows(n)
        names = [r[0] for r in rows]
        self.assertIn("message", names)

    def test_direction_tagged_in_or_out(self):
        from mpynode.ui.widgets.variables import collect_plug_rows

        n = mc.createNode("mPyNode")
        rows = collect_plug_rows(n)
        for plug_name, direction, value_text in rows:
            self.assertIn(direction, ("IN", "OUT"))
            self.assertIsInstance(value_text, str)

    def test_connected_input_marked_with_arrow(self):
        from mpynode.ui.widgets.variables import collect_plug_rows

        # nodeState is on every node -- writable and accepts connections.
        src = mc.createNode("transform")
        n = mc.createNode("mPyNode")
        # Once connected, the row's value_text must start with "<-".
        mc.connectAttr(src + ".nodeState", n + ".nodeState", force=True)
        rows = collect_plug_rows(n)
        for plug_name, direction, value_text in rows:
            if plug_name == "nodeState":
                self.assertEqual(direction, "IN")
                self.assertTrue(
                    value_text.startswith("<-"),
                    f"connected nodeState value_text={value_text!r} should "
                    "start with '<-'",
                )
                return
        self.fail("nodeState plug row missing")

    def test_helper_handles_unknown_node_gracefully(self):
        from mpynode.ui.widgets.variables import collect_plug_rows

        rows = collect_plug_rows("nosuchnode_xyz")
        self.assertEqual(rows, [])


class TestSourceCleanup(unittest.TestCase):
    """Source-level pin -- the placeholder text from F.7
    is replaced by the live plug-tree implementation."""

    def test_no_old_placeholder_text(self):
        from mpynode.ui.widgets import variables

        import inspect

        src = inspect.getsource(variables)
        self.assertNotIn(
            "(no internal-var snapshot for this node type)",
            src,
            "F.7 placeholder text must be removed in G.6",
        )

    def test_module_helpers_present(self):
        from mpynode.ui.widgets import variables

        self.assertTrue(hasattr(variables, "collect_plug_rows"))
        self.assertTrue(hasattr(variables, "read_plug_value_text"))
        self.assertTrue(hasattr(variables, "PLUG_BROWSER_BLACKLIST"))


class TestApiRowValueTooltip(unittest.TestCase):
    """A long API row value/description gets a word-wrapped rich-text tooltip
    on every column so hovering surfaces the full (otherwise-truncated) text."""

    def setUp(self):
        if not _qapp_available():
            self.skipTest("no QApplication available")

    def test_ndplugrowitem_sets_wrapped_tooltip_on_all_columns(self):
        from mpynode.ui.widgets.variables import NDPlugRowItem
        try:
            from PySide6.QtWidgets import QTreeWidget
        except ImportError:
            from PySide2.QtWidgets import QTreeWidget

        tree = QTreeWidget()
        long_text = (
            "4x4 or None -- desired LOCAL (parent-relative) matrix; applied "
            "via offsetParentMatrix. For WORLD placement set local_matrix = "
            "world @ inv(parent), reading the parent from a connected input"
        )
        item = NDPlugRowItem(
            tree, plug_name="local_matrix", direction="WRITE",
            value_text=long_text,
        )
        for col in range(3):
            tip = item.toolTip(col)
            self.assertTrue(
                tip.startswith("<qt>"),
                f"col {col}: tooltip must be rich-text so Qt wraps it; got {tip!r}",
            )
            self.assertIn("offsetParentMatrix", tip)

    def test_empty_value_sets_no_tooltip(self):
        from mpynode.ui.widgets.variables import NDPlugRowItem
        try:
            from PySide6.QtWidgets import QTreeWidget
        except ImportError:
            from PySide2.QtWidgets import QTreeWidget

        tree = QTreeWidget()
        item = NDPlugRowItem(
            tree, plug_name="foo", direction="WRITE", value_text="",
        )
        # No value -> no tooltip (empty string), not "<qt></qt>".
        self.assertEqual(item.toolTip(2), "")


def setUpModule():
    _setUpModule__phaseM_0_attributes_widget()
    _setUpModule__phaseO_0_storage_tree()
    _setUpModule__phaseG_6_variables_widget()


if __name__ == "__main__":
    import unittest
    unittest.main()
