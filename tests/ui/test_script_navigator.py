"""NDScriptNavigator -- the Script area's right-hand column, as ONE table.

Beyond "it lists things", four claims are worth pinning:

* it says what the node CANNOT do. A tab strip can only show tiers that exist;
  an absent tier is simply an absent tab. The navigator greys it and names the
  missing setter, which is the whole reason it earns its pixels.
* it does NOT inherit the Methods outline's known defect. Sourcing rows from the
  bake's region map instead of ``outline_model.build_outline`` means a
  module-level ``class SetupError`` shows up -- build_outline walks
  ``ast.FunctionDef`` only and drops it.
* the Symbol column GROWS with the pane. Qt's default is
  ``stretchLastSection=True``, which pins Symbol at the 100px
  ``defaultSectionSize`` and hands every new pixel to the last column: widening
  the pane 180 -> 460 moved Line 100 -> 358 and left the names truncated.
* selection is ONE key with two renderers. Raising a tab lights the row, and
  clicking the row raises the tab -- the return leg that was missing.
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
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-nav-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


METHODS = (
    "import math\n\n\n"
    "MAX_TRIES = 5\n\n\n"
    "class SetupError(Exception):\n    pass\n\n\n"
    "def helper(x):\n    return x\n\n\n"
    "@maya_demo\ndef demo(self):\n    return 1\n\n\n"
    "@maya_test\ndef test_thing(self):\n    return True\n\n\n"
    "def setup(self):\n    return 1\n"
)


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestScriptNavigator(unittest.TestCase):
    def _locator(self, methods=METHODS, var=True):
        from mpynode.wrappers.mpy_locator import MPyLocator

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="navLoc")
        if methods:
            loc.set_methods_source(methods)
        if var:
            loc.add_variable("board", persistent=True)
        return loc

    def _nav(self, py_node):
        from mpynode.ui.widgets.script_navigator import NDScriptNavigator

        return NDScriptNavigator(py_node)

    def _names(self, nav, section):
        return [n for n, _m, _d in nav.rowsUnder(section)]

    # -- structure ------------------------------------------------------

    def test_sections_in_document_order(self):
        nav = self._nav(self._locator())
        try:
            titles = nav.sectionTitles()
            # EXPRESSIONS then CLASS: the two you reach for get the top of the
            # pane. MODULE SCOPE is reference, and sits below.
            self.assertEqual(titles[0], "EXPRESSIONS")
            self.assertTrue(titles[1].startswith("CLASS · "), titles)
            self.assertLess(titles.index("EXPRESSIONS"),
                            titles.index("MODULE SCOPE"))
            self.assertLess(titles.index(titles[1]), titles.index("MODULE SCOPE"))
            self.assertIn("MODULE SCOPE", titles)
            self.assertIn("VARIABLES", titles)
        finally:
            nav.deleteLater()

    def test_the_document_section_is_gone_and_its_count_moved_up(self):
        # It was a category holding one row, and the row named the FILE that
        # every other row is already a part of. The user called it noise. The
        # line count survives, in the pane's title bar where it describes the
        # pane rather than pretending to be somewhere you can go.
        nav = self._nav(self._locator())
        try:
            self.assertNotIn("DOCUMENT", nav.sectionTitles())
            self.assertEqual(nav._title_label.text(), "Outline")
            self.assertTrue(nav._total_label.text().endswith(" lines"),
                            nav._total_label.text())
            self.assertGreater(int(nav._total_label.text().split()[0]), 0)
        finally:
            nav.deleteLater()

    def test_a_node_with_nothing_baked_shows_no_count(self):
        # refresh() bails before it can measure anything; a stale number left
        # over the empty tree would be a lie about what is on screen.
        nav = self._nav(self._locator())
        try:
            self.assertTrue(nav._total_label.text())
            nav.setPyNode(None)
            self.assertEqual(nav._total_label.text(), "")
        finally:
            nav.deleteLater()

    def test_section_rows_are_painted_without_a_focus_square(self):
        # A section refuses SELECTION but Qt still puts a CURRENT index on it,
        # and the style outlined that -- a little square in the empty Kind cell
        # beside EXPRESSIONS that meant nothing and no click could clear.
        from mpynode.ui.qt_wrapper import (
            QStyle, QStyledItemDelegate, QStyleOptionViewItem,
        )

        nav = self._nav(self._locator())
        try:
            delegate = nav._tree.itemDelegate()
            self.assertIsNotNone(delegate)
            seen = []
            opt = QStyleOptionViewItem()
            opt.state = QStyle.State_Enabled | QStyle.State_HasFocus
            # Column 1 of a section row: the empty Kind cell the square
            # appeared in.
            index = nav._tree.model().index(0, 1)

            def _spy(_self, _painter, option, _idx):
                seen.append(bool(option.state & QStyle.State_HasFocus))
                seen.append(bool(option.state & QStyle.State_Enabled))

            original = QStyledItemDelegate.paint
            try:
                QStyledItemDelegate.paint = _spy
                delegate.paint(None, opt, index)
            finally:
                QStyledItemDelegate.paint = original
            # Focus gone, and ONLY focus: clearing Enabled too would grey the
            # whole pane.
            self.assertEqual(seen, [False, True])
            # The option handed IN is untouched -- the view reuses one object
            # across cells, so mutating it would leak into the next row.
            self.assertTrue(bool(opt.state & QStyle.State_HasFocus))
        finally:
            nav.deleteLater()

    def test_absent_tiers_are_shown_greyed_and_named(self):
        nav = self._nav(self._locator())
        try:
            rows = dict((n, (m, d)) for n, m, d in nav.rowsUnder("EXPRESSIONS"))
            self.assertEqual(
                sorted(rows), ["Compute", "Init", "OSL", "Viewport"])
            self.assertFalse(rows["Init"][1])
            self.assertFalse(rows["Compute"][1])
            self.assertTrue(rows["Viewport"][1], "Viewport should be greyed")
            self.assertEqual(rows["OSL"][0], "not on this type")
        finally:
            nav.deleteLater()

    def test_all_four_tiers_live_on_mpyfile(self):
        from mpynode.wrappers.mpy_file import MPyFile

        mc.file(new=True, force=True)
        node = MPyFile.create(name="navFile")
        nav = self._nav(node)
        try:
            rows = dict((n, d) for n, _m, d in nav.rowsUnder("EXPRESSIONS"))
            for tier in ("Init", "Compute", "Viewport", "OSL"):
                self.assertFalse(rows[tier], "%s should be live" % tier)
        finally:
            nav.deleteLater()

    def test_module_level_class_and_constant_are_listed(self):
        # outline_model.build_outline walks ast.FunctionDef only, so a
        # module-level class never appears there. Sourcing from the bake's
        # region map does not have that hole.
        nav = self._nav(self._locator())
        try:
            names = self._names(nav, "MODULE SCOPE")
            self.assertIn("SetupError", names)
            self.assertIn("MAX_TRIES", names)
            self.assertIn("helper", names)
            self.assertIn("imports", names)
        finally:
            nav.deleteLater()

    def test_no_module_scope_section_on_a_plain_node(self):
        # A node whose Methods source has no module-scope code gets no
        # section at all. It used to show "(no module scope) 0 segments",
        # which named a concept the node does not use.
        nav = self._nav(self._locator(methods=""))
        try:
            self.assertNotIn("MODULE SCOPE", nav.sectionTitles())
            self.assertNotIn("MODULE", nav.sectionTitles())
        finally:
            nav.deleteLater()

    def test_module_scope_section_explains_itself(self):
        nav = self._nav(self._locator())
        try:
            titles = nav.sectionTitles()
            self.assertIn("MODULE SCOPE", titles)
            top = [nav._tree.topLevelItem(i)
                   for i in range(nav._tree.topLevelItemCount())
                   if nav._tree.topLevelItem(i).text(0) == "MODULE SCOPE"][0]
            self.assertIn("Methods", top.toolTip(0))
            self.assertIn("module scope", top.toolTip(0))
        finally:
            nav.deleteLater()

    def test_module_rows_name_the_symbol_not_the_whole_source_line(self):
        # The crushed-column symptom had two halves; this is the other one.
        # The row used to carry "class SetupError(Exception):" verbatim, which
        # elides to "class Set..." in any realistic width.
        nav = self._nav(self._locator())
        try:
            self.assertNotIn(
                "class SetupError(Exception):", self._names(nav, "MODULE SCOPE"))
        finally:
            nav.deleteLater()

    def test_members_split_into_role_sections(self):
        nav = self._nav(self._locator())
        try:
            self.assertIn("setup", self._names(nav, "SETUP"))
            self.assertIn("demo", self._names(nav, "DEMOS"))
            self.assertIn("test_thing", self._names(nav, "TESTS"))
        finally:
            nav.deleteLater()

    def test_class_section_carries_the_managed_skeleton(self):
        nav = self._nav(self._locator())
        try:
            title = [t for t in nav.sectionTitles()
                     if t.startswith("CLASS · ")][0]
            names = self._names(nav, title)
            self.assertTrue(any(n.startswith("class ") for n in names), names)
            self.assertIn("build()", names)
            self.assertIn("Variables", names)
        finally:
            nav.deleteLater()

    def test_persistent_variables_listed_by_name_only(self):
        nav = self._nav(self._locator())
        try:
            self.assertEqual(self._names(nav, "VARIABLES"), ["board"])
        finally:
            nav.deleteLater()

    def test_no_variables_says_so_rather_than_going_blank(self):
        nav = self._nav(self._locator(var=False))
        try:
            rows = nav.rowsUnder("VARIABLES")
            self.assertEqual(len(rows), 1)
            self.assertIn("none declared", rows[0][0])
            self.assertTrue(rows[0][2], "the placeholder should be disabled")
        finally:
            nav.deleteLater()

    def test_rows_resolve_to_a_region_with_a_baked_line(self):
        from mpynode._common.io import py_export

        node = self._locator()
        nav = self._nav(node)
        try:
            src = py_export.generate_node_script(node).split("\n")
            for key in nav.keysUnder("MODULE SCOPE"):
                region = nav.regionForKey(key)
                self.assertIsNotNone(region, key)
                name = key.split(".", 1)[1]
                if name == "imports":
                    continue  # a category label, not a symbol in the source
                blob = "\n".join(src[region["start"]:region["start"] + 3])
                self.assertIn(name, blob)
        finally:
            nav.deleteLater()

    def test_member_rows_carry_the_methods_source_line(self):
        # Stage 2 splices edits back by this number; a wrong one writes into
        # the wrong def.
        node = self._locator()
        nav = self._nav(node)
        msrc = (node.get_methods_source() or "").split("\n")
        try:
            for key in nav.keysUnder("SETUP") + nav.keysUnder("TESTS"):
                region = nav.regionForKey(key)
                line = region.get("src_line")
                self.assertTrue(line, key)
                window = "\n".join(msrc[line - 1:line + 2])
                self.assertIn(key.split(".", 1)[1], window)
        finally:
            nav.deleteLater()

    def test_reuses_a_supplied_region_map(self):
        from mpynode._common.io.py_export import (
            generate_node_script_with_regions,
        )

        node = self._locator()
        _src, regions = generate_node_script_with_regions(node)
        nav = self._nav(node)
        try:
            nav.refresh(regions)
            self.assertIn("setup", self._names(nav, "SETUP"))
            # an empty map must not invent rows
            nav.refresh([])
            self.assertEqual(nav.rowsUnder("SETUP"), [])
        finally:
            nav.deleteLater()

    def test_no_node_renders_nothing_and_does_not_raise(self):
        from mpynode.ui.widgets.script_navigator import NDScriptNavigator

        nav = NDScriptNavigator()
        try:
            nav.refresh()
            self.assertEqual(nav.sectionTitles(), [])
        finally:
            nav.deleteLater()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestBlessedSection(unittest.TestCase):
    """The framework's authoring surface, offered for copy/insert.

    command_templates_for_type alone is not enough: only mPyBlendShape ships
    any, so a palette driven by it is empty on 11 of 12 node types.
    """

    def _nav(self, wrapper="MPyLocator", name="blessLoc"):
        import mpynode
        from mpynode.ui.widgets.script_navigator import NDScriptNavigator

        mc.file(new=True, force=True)
        node = getattr(mpynode, wrapper).create(name=name)
        return NDScriptNavigator(node)

    def test_framework_decorators_offered_on_a_plain_node(self):
        nav = self._nav()
        try:
            names = [n for n, _m, _d in nav.rowsUnder("BLESSED")]
            for want in ("@maya_command", "@maya_demo", "@maya_test"):
                self.assertIn(want, names)
        finally:
            nav.deleteLater()

    def test_offers_are_inert_rows(self):
        # An OFFER is not code in the buffer: nothing to jump to, nothing to
        # run. A stray left-click must not mutate the source.
        nav = self._nav()
        try:
            rows = nav.rowsUnder("BLESSED")
            self.assertTrue(rows)
            for _name, _meta, disabled in rows:
                self.assertTrue(disabled)
            self.assertEqual(
                [k for k in nav.keysUnder("BLESSED") if k], [])
        finally:
            nav.deleteLater()

    def test_per_type_offers_still_appear(self):
        # mPyBlendShape is the one type with plain-command templates; the
        # framework skeletons must not have displaced them.
        try:
            nav = self._nav("MPyBlendShape", "blessBs")
        except Exception as exc:  # noqa: BLE001
            self.skipTest("MPyBlendShape unavailable: %s" % exc)
        try:
            names = [n for n, _m, _d in nav.rowsUnder("BLESSED")]
            self.assertIn("@maya_command", names)
            self.assertTrue(
                any("load_target" in n for n in names),
                "per-type offers missing: %r" % names)
        finally:
            nav.deleteLater()

    def test_every_skeleton_is_valid_python(self):
        # These get pasted into the user's buffer. A skeleton that does not
        # parse is worse than no palette at all.
        import ast

        from mpynode._common.node_setups import framework_templates

        templates = framework_templates()
        self.assertTrue(templates)
        for t in templates:
            src = t.source
            if src.lstrip().startswith("@"):
                # a bare decorator needs its import to compile standalone
                src = ("def maya_command(*a, **k):\n    return lambda f: f\n"
                       "maya_demo = maya_test = maya_command\n") + src
            try:
                ast.parse(src)
            except SyntaxError as exc:
                self.fail("%s does not parse: %s" % (t.name, exc))


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestNavigatorColumns(unittest.TestCase):
    """The measured crush: Symbol pinned at 100px while Line ate the slack."""

    def _nav(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_navigator import NDScriptNavigator

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="navCols")
        loc.set_methods_source(METHODS)
        return NDScriptNavigator(loc)

    def test_header_is_visible_so_the_dividers_can_be_dragged(self):
        nav = self._nav()
        try:
            self.assertFalse(nav._tree.isHeaderHidden())
            self.assertFalse(nav._tree.header().stretchLastSection())
        finally:
            nav.deleteLater()

    def test_symbol_column_grows_with_the_pane(self):
        nav = self._nav()
        try:
            widths = []
            for w in (180, 300, 460):
                nav.resize(w, 600)
                nav.show()
                _QAPP.processEvents()
                widths.append(nav._tree.columnWidth(0))
            self.assertLess(widths[0], widths[1], widths)
            self.assertLess(widths[1], widths[2], widths)
        finally:
            nav.deleteLater()

    def test_a_user_drag_wins_over_auto_fit(self):
        # Auto-fit exists because Interactive columns do not track the
        # viewport. It must not then fight someone who sizes it by hand.
        nav = self._nav()
        try:
            nav.resize(300, 600)
            nav.show()
            _QAPP.processEvents()
            nav._tree.header().sectionResized.emit(0, 100, 140)
            nav._tree.setColumnWidth(0, 140)
            nav.resize(460, 600)
            _QAPP.processEvents()
            self.assertEqual(nav._tree.columnWidth(0), 140)
        finally:
            nav.deleteLater()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestNavigatorInTheScriptTab(unittest.TestCase):
    def setUp(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        self._saved_tier = NDScriptTabContent.__dict__.get("_shared_tier")

    def tearDown(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        NDScriptTabContent._shared_tier = self._saved_tier

    def _build(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="navTab")
        loc.set_methods_source(METHODS)
        return loc, NDScriptTabContent(loc)

    def _tab(self, w):
        return w._inner_tabs.tabText(w._inner_tabs.currentIndex())

    def test_navigator_sits_beside_the_strip_and_may_be_railed(self):
        loc, w = self._build()
        try:
            self.assertIsNotNone(w._navigator)
            self.assertIs(w._nav_split.widget(0), w._inner_tabs)
            self.assertIs(w._nav_split.widget(1), w._navigator)
            self.assertFalse(w._nav_split.isCollapsible(0))
            self.assertTrue(w._nav_split.isCollapsible(1))
        finally:
            w.deleteLater()

    def test_navigator_row_raises_the_tab(self):
        loc, w = self._build()
        try:
            w._navigator.selectRequested.emit("tier.init")
            self.assertEqual(self._tab(w), "Init")
            w._navigator.selectRequested.emit("api")
            self.assertEqual(self._tab(w), "API")
        finally:
            w.deleteLater()

    def test_raising_a_tab_lights_the_row(self):
        # The user's item 2: this leg did not exist. Selecting Compute in the
        # strip left the table pointing wherever it had been.
        loc, w = self._build()
        try:
            w.select("tier.init")
            self.assertEqual(w._navigator.currentKey(), "tier.init")
            w._inner_tabs.setCurrentIndex(w._index_for_tier("Compute"))
            self.assertEqual(w._navigator.currentKey(), "tier.compute")
            # The API tab no longer HAS a row -- DOCUMENT is gone -- so the
            # strip clears the highlight instead of leaving it on the tier you
            # just left, which would point at the wrong place.
            w._inner_tabs.setCurrentIndex(w._index_for_tier("API"))
            self.assertIsNone(w._navigator.currentKey())
        finally:
            w.deleteLater()

    def test_osl_key_finds_the_uppercase_tab(self):
        # "osl".capitalize() is "Osl"; the tab is "OSL".
        from mpynode.wrappers.mpy_file import MPyFile
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        node = MPyFile.create(name="navOsl")
        w = NDScriptTabContent(node)
        try:
            self.assertTrue(w.select("tier.osl"))
            self.assertEqual(self._tab(w), "OSL")
            self.assertEqual(w._navigator.currentKey(), "tier.osl")
        finally:
            w.deleteLater()

    def test_symbol_row_opens_the_api_view_at_that_line(self):
        loc, w = self._build()
        try:
            keys = w._navigator.keysUnder("MODULE SCOPE")
            self.assertTrue(keys)
            region = w._navigator.regionForKey(keys[-1])
            w._navigator.selectRequested.emit(keys[-1])
            self.assertEqual(self._tab(w), "API")
            self.assertEqual(
                w._api_view.textCursor().block().blockNumber(),
                region["start"])
        finally:
            w.deleteLater()

    def test_variable_row_relays_the_reveal_request(self):
        loc, w = self._build()
        seen = []
        w.revealVariableRequested.connect(seen.append)
        try:
            w._navigator.variableActivated.emit("board")
            self.assertEqual(seen, ["board"])
        finally:
            w.deleteLater()

    # -- single = locate, double / Enter = go edit (2026-09) -----------------

    def _build_with_var(self):
        loc, w = self._build()
        loc.add_variable("board", persistent=True)
        w.refreshIdentityViews()          # re-bake the API view + the Outline
        return loc, w

    def test_single_click_locates_in_the_api_view_and_keeps_the_tab(self):
        loc, w = self._build()
        loc.set_init_expression("import math\n")
        w.refreshIdentityViews()
        try:
            w._inner_tabs.setCurrentIndex(w._index_for_tier("Compute"))
            rail = w._navigator.regionForKey("tier.init")
            self.assertIsNotNone(rail)
            self.assertTrue(w.locate("tier.init"))
            self.assertEqual(self._tab(w), "API")
            self.assertEqual(w._api_view.textCursor().block().blockNumber(),
                             rail["start"])
            self.assertEqual(w._navigator.currentKey(), "tier.init")
            # The row's click emits locateRequested, never selectRequested.
            located, opened = [], []
            w._navigator.locateRequested.connect(located.append)
            w._navigator.selectRequested.connect(opened.append)
            w._navigator._on_item_clicked(
                w._navigator._item_for_key("tier.init"), 0)
            self.assertEqual((located, opened), (["tier.init"], []))
            self.assertEqual(self._tab(w), "API")
        finally:
            w.deleteLater()

    def test_an_empty_tier_has_no_line_so_its_click_opens_the_tab(self):
        # The one exception to single = locate: nothing in the bake to show.
        loc, w = self._build()
        try:
            self.assertIsNone(w._navigator.regionForKey("tier.init"))
            self.assertTrue(w.locate("tier.init"))
            self.assertEqual(self._tab(w), "Init")
        finally:
            w.deleteLater()

    def test_activation_opens_the_authoring_tab(self):
        loc, w = self._build_with_var()
        try:
            w._navigator._on_item_activated(
                w._navigator._item_for_key("tier.init"), 0)
            self.assertEqual(self._tab(w), "Init")
            seen = []
            w.revealVariableRequested.connect(seen.append)
            w._navigator._on_item_activated(
                w._navigator._item_for_key("var.board"), 0)
            self.assertEqual(seen, ["board"])
            attrs = []
            w.revealAttributesRequested.connect(attrs.append)
            self.assertTrue(w.select("class.attrs_in"))
            self.assertEqual(attrs, ["Inputs"])
        finally:
            w.deleteLater()

    def test_a_variable_row_resolves_to_its_own_line(self):
        loc, w = self._build_with_var()
        try:
            region = w._navigator.regionForKey("var.board")
            self.assertIsNotNone(region, "the variable row carries no line")
            line = w._api_view.source().split("\n")[region["start"]]
            self.assertIn("'board'", line)
            self.assertTrue(w.locate("var.board"))
            self.assertEqual(self._tab(w), "API")
            self.assertEqual(w._api_view.textCursor().block().blockNumber(),
                             region["start"])
        finally:
            w.deleteLater()

    def test_a_click_on_a_generated_line_opens_a_railed_outline(self):
        loc, w = self._build()
        w.resize(1000, 600)
        w.show()
        _QAPP.processEvents()
        try:
            total = sum(w._nav_split.sizes())
            w._nav_split.setSizes([total, 0])
            self.assertEqual(w._nav_split.sizes()[1], 0)
            decl = [r for r in w._api_view.regions()
                    if r["kind"] == "class_decl"][0]
            w._api_view.regionActivated.emit(decl)
            self.assertGreater(w._nav_split.sizes()[1], 0)
            self.assertEqual(w._navigator.currentKey(), "class.decl")
        finally:
            w.deleteLater()

    def test_blessed_insert_appends_to_the_methods_source(self):
        loc, w = self._build()
        try:
            before = loc.get_methods_source() or ""
            w._navigator.insertTemplateRequested.emit(
                "def blessed(self):\n    pass\n")
            after = loc.get_methods_source() or ""
            self.assertIn("def blessed(self):", after)
            # nothing the user already had may be displaced
            for kept in ("class SetupError", "def helper", "def setup"):
                self.assertIn(kept, after, before)
            # and the new def is visible where it will be edited
            self.assertEqual(
                w._inner_tabs.tabText(w._inner_tabs.currentIndex()), "API")
            self.assertIn("def blessed(self):", w._api_view.toPlainText())
        finally:
            w.deleteLater()

    def test_blessed_insert_reaches_a_node_with_no_methods_yet(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="navEmpty")
        loc.set_methods_source("")
        w = NDScriptTabContent(loc)
        try:
            w._navigator.insertTemplateRequested.emit(
                "def blessed(self):\n    pass\n")
            self.assertIn("def blessed(self):", loc.get_methods_source() or "")
        finally:
            w.deleteLater()

    def test_navigator_and_api_view_agree(self):
        loc, w = self._build()
        try:
            for key in w._navigator.keysUnder("MODULE SCOPE"):
                region = w._navigator.regionForKey(key)
                found = w._api_view.regionAt(region["start"])
                self.assertIsNotNone(found, key)
        finally:
            w.deleteLater()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestKeyForRegion(unittest.TestCase):
    """The inverse lookup that lets a click in the code light up a row."""

    def setUp(self):
        # _shared_tier is a MUTABLE CLASS attribute -- select() writes it for
        # every node in the session. _pair() selects API, so without this a
        # later test asserting the class default reads "API".
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        self._saved_tier = NDScriptTabContent.__dict__.get("_shared_tier")

    def tearDown(self):
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        NDScriptTabContent._shared_tier = self._saved_tier

    def _pair(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="navKey")
        loc.add_input_attr("maxVal", "float")
        loc.add_output_attr("sort", "float", is_array=True)
        loc.add_variable("board", persistent=True)
        loc.set_methods_source(METHODS)
        tab = NDScriptTabContent(loc)
        tab.resize(940, 640)
        tab.show()
        tab.select("api")
        _QAPP.processEvents()
        return tab

    def test_every_class_row_resolves_both_ways(self):
        tab = self._pair()
        try:
            nav, api = tab._navigator, tab._api_view
            for kind, key in (("class_decl", "class.decl"),
                              ("build_signature", "class.build"),
                              ("attrs_in", "class.attrs_in"),
                              ("attrs_out", "class.attrs_out"),
                              ("vars", "class.vars")):
                found = [r for r in api.regions() if r["kind"] == kind]
                self.assertTrue(found, "no %s region" % kind)
                self.assertEqual(nav.keyForRegion(found[0]), key)
                back = nav.regionForKey(key)
                self.assertEqual(back["start"], found[0]["start"])
        finally:
            tab.deleteLater()

    def test_the_stored_payload_is_a_copy_so_identity_cannot_be_used(self):
        # setData round-trips a dict through QVariant and hands back an
        # equal-valued COPY -- "stored is region" is False even for the very
        # dict that was put there. keyForRegion matches on (kind, start, end).
        tab = self._pair()
        try:
            nav, api = tab._navigator, tab._api_view
            region = [r for r in api.regions()
                      if r["kind"] == "attrs_in"][0]
            self.assertIsNot(nav.regionForKey("class.attrs_in"), region)
            self.assertEqual(nav.keyForRegion(region), "class.attrs_in")
        finally:
            tab.deleteLater()

    def test_an_unknown_region_resolves_to_nothing(self):
        tab = self._pair()
        try:
            nav = tab._navigator
            self.assertIsNone(nav.keyForRegion(None))
            self.assertIsNone(nav.keyForRegion({"kind": "gap"}))
            self.assertIsNone(
                nav.keyForRegion({"kind": "attrs_in", "start": 9999,
                                  "end": 9999}))
        finally:
            tab.deleteLater()

    def test_clicking_a_managed_region_selects_without_moving_the_caret(self):
        tab = self._pair()
        try:
            nav, api = tab._navigator, tab._api_view
            before = api.textCursor().blockNumber()
            target = [r for r in api.regions()
                      if r["kind"] == "attrs_out"][0]
            tab._on_region_activated(target)
            _QAPP.processEvents()
            self.assertEqual(nav.currentKey(), "class.attrs_out")
            self.assertEqual(api.textCursor().blockNumber(), before,
                             "highlight only -- you are already looking at it")
        finally:
            tab.deleteLater()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestNavigatorRhythm(unittest.TestCase):
    """Sections have to read as separators, and no row may stand out of step.

    The managed badge used to be the U+1F512 lock EMOJI. An emoji resolves to
    the colour-emoji font, which is taller than the UI font, so the rows
    carrying one -- and only those -- grew. It is invisible in a headless run,
    where there is no emoji font to fall back to, which is exactly why the row
    height is pinned rather than left to whatever the glyph asks for.
    """

    def _nav(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_navigator import NDScriptNavigator

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="navRhythm")
        loc.set_methods_source(METHODS)
        loc.add_variable("board", persistent=True)
        nav = NDScriptNavigator(loc)
        nav.resize(240, 600)
        nav.show()
        _QAPP.processEvents()
        return nav

    def test_the_managed_badge_is_not_an_emoji(self):
        from mpynode.ui.widgets import script_navigator as sn

        self.assertNotEqual(sn._LOCK, "\U0001f512")
        self.assertEqual(len(sn._LOCK), 1)
        self.assertLess(ord(sn._LOCK), 0x1F000,
                        "outside the emoji planes, so it uses the UI font")

    def test_sections_stand_off_from_their_rows(self):
        nav = self._nav()
        try:
            tree = nav._tree
            section = tree.topLevelItem(0)
            self.assertGreater(
                tree.visualItemRect(section).height(),
                tree.visualItemRect(section.child(0)).height())
        finally:
            nav.deleteLater()

    def test_every_row_is_the_same_height(self):
        nav = self._nav()
        try:
            tree = nav._tree
            heights = set()
            locked = 0
            for i in range(tree.topLevelItemCount()):
                top = tree.topLevelItem(i)
                for j in range(top.childCount()):
                    child = top.child(j)
                    heights.add(tree.visualItemRect(child).height())
                    from mpynode.ui.widgets import script_navigator as sn

                    if sn._LOCK in child.text(1):
                        locked += 1
            self.assertEqual(len(heights), 1, heights)
            self.assertGreater(locked, 0, "expected some managed rows")
        finally:
            nav.deleteLater()

    def test_line_counts_are_spelled_out_and_agree_on_number(self):
        from mpynode.ui.widgets.script_navigator import _lines

        self.assertEqual(_lines(1), "1 line")
        self.assertEqual(_lines(0), "0 lines")
        self.assertEqual(_lines(132), "132 lines")

    def test_no_row_still_says_ln(self):
        nav = self._nav()
        try:
            tree = nav._tree
            for i in range(tree.topLevelItemCount()):
                top = tree.topLevelItem(i)
                for j in range(top.childCount()):
                    detail = top.child(j).text(2)
                    self.assertFalse(detail.endswith(" ln"), detail)
        finally:
            nav.deleteLater()


if __name__ == "__main__":
    unittest.main()
