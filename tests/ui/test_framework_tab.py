"""Framework tab (left, read-only) coverage: the GROUPS and their row content.

``NDFrameworkWidget`` renders read-only groups for the active node:

  * **Methods** -- the wrapper's blessed ``INTERNAL_API_METHODS`` (each row
    carries its ``MethodSpec`` via ``data(0, Qt.UserRole)`` so the right-click
    menu can jump to the transpiled source).
  * **Properties** -- the non-plug ``INTERNAL_API_SLOTS`` (via
    ``variables.collect_internal_api_rows``, skipping the appended METHOD rows,
    which the Methods group already shows).
  * **Authoring Methods** (+ the wrapper's ``@property`` surface) -- the
    scene-mutating wrapper API, curated per wrapper via ``AUTHORING_API``.

Which of those exist depends on the SCRIPT TIER the editor is on, because
``self`` is not one object: the expression tiers get a SelfProxy, the API tab
gets the wrapper. Tests that want the authoring surface must therefore say
``w.setActiveTier("API")`` -- the default (unset) tier renders the Compute
panel. The tier->groups matrix itself lives in
``test_framework_panel_tiers``; this module covers what is INSIDE each group.

A skinCluster wrapper is the canonical blessed-method fixture: it declares NO
INTERNAL_API_SLOTS (every self.X is a plug) yet surfaces the
linear_blend / dual_quaternion / twist_swing skin methods. The skinCluster is
built exactly like test_variables_method_rows.TestSlotlessMethodRows._skin:
two joints + a poly plane -> MPySkinCluster.create(plane, joints=[...]).
"""

from __future__ import annotations

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
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-frameworktab-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _qapp_available():
    return _QAPP is not None


def _top_item_by_label(tree, label):
    """Return the top-level QTreeWidgetItem whose col-0 text == ``label``."""
    for i in range(tree.topLevelItemCount()):
        it = tree.topLevelItem(i)
        if it.text(0) == label:
            return it
    return None


def _child_col0_texts(top_item):
    return [top_item.child(i).text(0) for i in range(top_item.childCount())]


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestFrameworkTab(unittest.TestCase):
    def setUp(self):
        mc.file(new=True, force=True)
        self._widgets = []

    def tearDown(self):
        for w in self._widgets:
            try:
                w.deleteLater()
            except Exception:
                pass

    # -- fixtures ------------------------------------------------------------

    def _widget(self):
        from mpynode.ui.widgets.framework_tab import NDFrameworkWidget

        w = NDFrameworkWidget()
        self._widgets.append(w)
        return w

    def _skin(self, name):
        from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster

        j1 = mc.joint(p=(0, 0, 0), n="ftj1")
        mc.select(clear=True)
        j2 = mc.joint(p=(0, 2, 0), n="ftj2")
        mc.select(clear=True)
        plane = mc.polyPlane(name="ftP", w=4, h=4, sx=2, sy=2)[0]
        return MPySkinCluster.create(plane, joints=[j1, j2], name=name)

    def _plain(self, name):
        from mpynode.wrappers._mpy_node import MPyNode

        return MPyNode.create(name=name)

    # -- tests ---------------------------------------------------------------

    def test_methods_group_lists_blessed(self):
        w = self._widget()
        w.setPyNode(self._skin("ftSkin#"))
        methods = _top_item_by_label(w._tree, "Methods")
        self.assertIsNotNone(methods, "Methods group missing")
        names = _child_col0_texts(methods)
        for meth in ("linear_blend", "dual_quaternion", "twist_swing"):
            self.assertIn(meth, names, "%s missing from Methods group" % meth)

    def _blend(self, name):
        from mpynode.wrappers.mpy_blend_shape import MPyBlendShape

        base = mc.polySphere(r=1.0, sx=6, sy=6, name="ftBsBase#")[0]
        return MPyBlendShape.create(mesh=base, name=name)

    def test_blend_shape_methods_group_is_not_empty(self):
        """Regression: mPyBlendShape registered its blessed methods in
        method_registry but never mirrored them onto the CLASS, and the tab
        reads the class attr -- so the group rendered "(none)"."""
        w = self._widget()
        w.setPyNode(self._blend("ftBs#"))
        methods = _top_item_by_label(w._tree, "Methods")
        self.assertIsNotNone(methods)
        names = _child_col0_texts(methods)
        self.assertNotIn("(none)", names)
        for meth in ("morph_weights", "morph_deltas", "blend_targets"):
            self.assertIn(meth, names)

    def test_authoring_methods_group_names_the_scene_mutating_api(self):
        """self.load_target and friends are what a Setup or a command body
        calls, but they cannot join INTERNAL_API_METHODS (that tuple is the
        plug-validated compute-time surface) -- so they need their own group,
        on the one tab whose `self` is the wrapper."""
        w = self._widget()
        w.setPyNode(self._blend("ftBsAuth#"))
        w.setActiveTier("API")
        group = _top_item_by_label(w._tree, "Authoring Methods")
        self.assertIsNotNone(group, "Authoring Methods group missing")
        names = _child_col0_texts(group)
        for meth in ("load_target", "load_shapes", "add_target", "rebuild",
                     "set_weight", "remove_target"):
            self.assertIn(meth, names)
        # The blessed ones stay in their own group, not duplicated here.
        for meth in ("morph_weights", "blend_targets"):
            self.assertNotIn(meth, names)

    def test_authoring_rows_carry_a_signature_without_self(self):
        w = self._widget()
        w.setPyNode(self._blend("ftBsSig#"))
        w.setActiveTier("API")
        group = _top_item_by_label(w._tree, "Authoring Methods")
        row = next(group.child(i) for i in range(group.childCount())
                   if group.child(i).text(0) == "load_target")
        self.assertIn("path", row.text(1))
        self.assertNotIn("self", row.text(1))

    def test_authoring_rows_carry_no_spec_so_the_jump_menu_stays_inert(self):
        """_on_menu bails when data(0, Qt.UserRole) is None. Only blessed rows
        have a resolvable transpiled source, so authoring rows must not pretend
        to."""
        from mpynode.ui.qt_wrapper import Qt

        w = self._widget()
        w.setPyNode(self._blend("ftBsMenu#"))
        w.setActiveTier("API")
        group = _top_item_by_label(w._tree, "Authoring Methods")
        for i in range(group.childCount()):
            self.assertIsNone(group.child(i).data(0, Qt.UserRole))

    def test_properties_group_picks_up_a_property_missing_from_the_slots(self):
        """INTERNAL_API_SLOTS is hand-maintained and drifts -- MPyBlendShape
        lists four of its five properties. target_names is the stray.

        A wrapper ``@property`` resolves on the WRAPPER, so the group that
        catches the stray is the API tab's, not the expression tiers'."""
        w = self._widget()
        w.setPyNode(self._blend("ftBsProp#"))
        w.setActiveTier("API")
        group = _top_item_by_label(w._tree, "Properties")
        self.assertIsNotNone(group)
        names = _child_col0_texts(group)
        self.assertIn("target_names", names)
        self.assertIn("morphs", names)   # ...without dropping the listed ones

    def _locator(self, name):
        from mpynode.wrappers.mpy_locator import MPyLocator

        return MPyLocator.create(name=name)

    def test_draw_types_group_on_a_locator(self):
        """A locator's whole visual surface is self.draw = Draw*(...), so the
        tab has to name those types somewhere."""
        w = self._widget()
        w.setPyNode(self._locator("ftLoc#"))
        group = _top_item_by_label(w._tree, "Draw types")
        self.assertIsNotNone(group, "Draw types group missing on mPyLocator")
        names = _child_col0_texts(group)
        for cls in ("DrawCircle", "DrawMesh", "DrawPoints", "DrawLines",
                    "DrawCurve", "DrawText"):
            self.assertIn(cls, names, "%s missing from Draw types" % cls)

    def test_draw_types_rows_carry_a_signature(self):
        w = self._widget()
        w.setPyNode(self._locator("ftLocSig#"))
        group = _top_item_by_label(w._tree, "Draw types")
        row = next(group.child(i) for i in range(group.childCount())
                   if group.child(i).text(0) == "DrawCircle")
        self.assertIn("center", row.text(1))
        self.assertNotIn("self", row.text(1))

    def test_draw_types_group_absent_on_other_types(self):
        w = self._widget()
        w.setPyNode(self._plain("ftPlainDraw#"))
        self.assertIsNone(_top_item_by_label(w._tree, "Draw types"))

    def test_setpynode_rebinds(self):
        w = self._widget()
        a = self._plain("ftPlainA#")
        b = self._plain("ftPlainB#")
        w.setPyNode(a)
        w.setPyNode(b)
        self.assertIs(w.getMPyNode(), b)
        # refresh must have run without error; tree has content (>=1 top item).
        self.assertGreaterEqual(w._tree.topLevelItemCount(), 1)

    def test_menu_resolves_source_for_blessed(self):
        from mpynode.ui.qt_wrapper import Qt
        from mpynode._common.methods.blessed_source import resolve_method_source

        w = self._widget()
        w.setPyNode(self._skin("ftSkin2#"))
        methods = _top_item_by_label(w._tree, "Methods")
        self.assertIsNotNone(methods)
        target = None
        for i in range(methods.childCount()):
            child = methods.child(i)
            if child.text(0) == "dual_quaternion":
                target = child
                break
        self.assertIsNotNone(target, "dual_quaternion row missing")
        spec = target.data(0, Qt.UserRole)
        self.assertIsNotNone(spec, "MethodSpec not stored on the row")
        resolved = resolve_method_source(spec)
        self.assertIsNotNone(resolved, "blessed source did not resolve")
        path, line = resolved
        self.assertTrue(
            path.endswith("skin_blend.py"),
            "expected skin_blend.py, got %r" % (path,),
        )
        self.assertIsInstance(line, int)

    def test_no_node_placeholder(self):
        w = self._widget()
        # No setPyNode: refresh() must show a placeholder, not crash.
        w.refresh()
        self.assertGreaterEqual(w._tree.topLevelItemCount(), 1)
        top0 = w._tree.topLevelItem(0)
        self.assertIn("no active node", top0.text(0))


if __name__ == "__main__":
    unittest.main()
