"""NDApiView -- the Script tab's read-only baked-.py surface.

The load-bearing claims are all mechanical, so they are all tested here:

* the buffer is EXACTLY what the bake emits (no synthesized document);
* expression bodies are really hidden, via QTextBlock.setVisible, which
  QPlainTextDocumentLayout honours;
* line numbers stay TRUE baked numbers across a fold, because blockNumber()
  survives folding and the shipped gutter skips invisible blocks;
* re-loading re-applies the fold -- setPlainText silently clears every
  visibility flag, so a view that folds once and reloads shows everything;
* looking at the tab never mutates the node (the bake's class-name resolver
  prompts AND stamps _pyClass; this view must not go near it).
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
    _QAPP = _QApplication.instance() or _QApplication(["mayapy-apiview-test"])

# Straight from the binding: qt_wrapper re-exports QRect and QSize but not
# QPoint, and widening the shared shim for a test is the wrong direction.
try:
    from PySide6.QtCore import QPoint as _QPoint
except Exception:
    try:
        from PySide2.QtCore import QPoint as _QPoint
    except Exception:
        _QPoint = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _qapp_available():
    return _QAPP is not None


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestApiView(unittest.TestCase):
    def _node(self, name="apiView"):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name=name)
        n.add_input_attr("inFloat", "float")
        n.add_output_attr("outFloat", "float")
        n.set_init_expression(
            "\n".join("a%d = %d" % (i, i) for i in range(20)) + "\n")
        n.set_compute_expression("self.outFloat = self.inFloat\n")
        return n

    def _view(self, py_node):
        from mpynode.ui.widgets.api_view import NDApiView

        return NDApiView(py_node)

    def test_buffer_is_exactly_the_bake(self):
        from mpynode._common.io import py_export

        n = self._node()
        v = self._view(n)
        try:
            self.assertEqual(v.toPlainText(),
                             py_export.generate_node_script(n))
        finally:
            v.deleteLater()

    def test_expression_bodies_are_hidden(self):
        n = self._node()
        v = self._view(n)
        try:
            self.assertGreater(v.hiddenLineCount(), 15,
                               "the 20-line init body should be folded away")
            doc  = v.document()
            init = [r for r in v.regions() if r["kind"] == "expr_init"][0]
            # the rail line stays visible -- it carries the managed call AND
            # the user's first body line, which the exporter puts on one line
            self.assertTrue(
                doc.findBlockByNumber(init["start"]).isVisible())
            for ln in range(init["start"] + 1, init["end"] + 1):
                self.assertFalse(doc.findBlockByNumber(ln).isVisible(),
                                 "line %d should be folded" % ln)
        finally:
            v.deleteLater()

    def test_line_numbers_stay_true_baked_numbers(self):
        # blockNumber() is preserved across a fold, so the gutter runs
        # non-contiguously rather than renumbering. This is what lets the view
        # claim its line numbers are the bake's line numbers.
        n = self._node()
        v = self._view(n)
        try:
            doc = v.document()
            visible = [i for i in range(doc.blockCount())
                       if doc.findBlockByNumber(i).isVisible()]
            src_lines = v.source().split("\n")
            for i in visible:
                self.assertEqual(doc.findBlockByNumber(i).text(),
                                 src_lines[i])
            # and they really are non-contiguous
            gaps = [b - a for a, b in zip(visible, visible[1:]) if b - a > 1]
            self.assertTrue(gaps, "expected a numbering gap across the fold")
        finally:
            v.deleteLater()

    def test_refresh_reapplies_the_fold(self):
        # setPlainText clears every block's visibility flag.
        n = self._node()
        v = self._view(n)
        try:
            first = v.hiddenLineCount()
            self.assertGreater(first, 0)
            v.refresh()
            self.assertEqual(v.hiddenLineCount(), first)
        finally:
            v.deleteLater()

    def test_starts_clean_and_refuses_drops(self):
        # No longer whole-widget read-only: the Methods regions are edited here.
        # A drop can insert at one place and delete at another, which is two
        # guarded ranges, so drops stay off.
        n = self._node()
        v = self._view(n)
        try:
            self.assertFalse(v.hasUnsavedChanges())
            self.assertFalse(v.acceptDrops())
        finally:
            v.deleteLater()

    def test_opening_the_view_does_not_stamp_py_class(self):
        # resolve_bake_class_name() prompts and calls set_py_class(); the view
        # must call the generator directly instead.
        n      = self._node()
        before = n.get_py_class()
        v      = self._view(n)
        try:
            v.refresh()
            self.assertEqual(n.get_py_class(), before)
        finally:
            v.deleteLater()

    def test_edit_guard_refuses_generated_spans(self):
        # setReadOnly is whole-widget, so the managed spans are protected by
        # refusing the keystroke. A leak here corrupts the bake contract.
        n        = self._node()
        v        = self._view(n)
        refusals = []
        v.editRefused.connect(refusals.append)
        try:
            before = v.toPlainText()
            for kind in ("class_decl", "build_signature", "return"):
                hits = [r for r in v.regions() if r["kind"] == kind]
                if not hits:
                    continue
                self._caret_on(v, hits[0]["start"])
                self._type(v, "Z")
                self.assertEqual(v.toPlainText(), before,
                                 "%s accepted a keystroke" % kind)
            self.assertTrue(refusals, "no refusal was reported")
            self.assertFalse(v.hasUnsavedChanges())
        finally:
            v.deleteLater()

    def test_edit_inside_a_member_splices_back_alone(self):
        n = self._node()
        n.set_methods_source(
            "def helper(x):\n    return x * 2\n\n\n"
            "def setup(self):\n    return 1\n")
        v = self._view(n)
        try:
            member = [r for r in v.regions()
                      if r["kind"] == "method_member"][0]
            self._caret_on(v, member["end"], end_of_line=True)
            self._type(v, "  # edited")
            self.assertTrue(v.hasUnsavedChanges())
            v.markSaved()
            saved = n.get_methods_source()
            self.assertIn("# edited", saved)
            self.assertIn("return x * 2", saved, "helper() was disturbed")
            self.assertFalse(v.hasUnsavedChanges())
        finally:
            v.deleteLater()

    def test_a_def_the_bake_skips_survives_a_save(self):
        # `build` is reserved: the exporter refuses it and emits a warning
        # comment with NO editable region. Because write-back is a per-region
        # splice and not a re-parse of the baked text, the def stays put.
        n = self._node()
        n.set_methods_source(
            "def build(self):\n    return 'skipped'\n\n\n"
            "def setup(self):\n    return 1\n")
        v = self._view(n)
        try:
            member = [r for r in v.regions()
                      if r["kind"] == "method_member"][0]
            self._caret_on(v, member["end"], end_of_line=True)
            self._type(v, "  # ok")
            v.markSaved()
            saved = n.get_methods_source()
            self.assertIn("return 'skipped'", saved)
            self.assertIn("# ok", saved)
        finally:
            v.deleteLater()

    def test_unedited_save_is_a_no_op(self):
        n = self._node()
        n.set_methods_source("def setup(self):\n    return 1\n")
        before = n.get_methods_source()
        v      = self._view(n)
        try:
            self.assertFalse(v.hasUnsavedChanges())
            v.markSaved()
            self.assertEqual(n.get_methods_source(), before)
        finally:
            v.deleteLater()

    def test_refresh_does_not_discard_unsaved_edits(self):
        # refresh() re-bakes from the node. Running it over a dirty buffer
        # would silently throw away whatever was typed.
        n = self._node()
        n.set_methods_source("def setup(self):\n    return 1\n")
        v = self._view(n)
        try:
            member = [r for r in v.regions()
                      if r["kind"] == "method_member"][0]
            self._caret_on(v, member["end"], end_of_line=True)
            self._type(v, "  # keep me")
            v.refresh()
            self.assertIn("# keep me", v.toPlainText())
            self.assertTrue(v.hasUnsavedChanges())
        finally:
            v.deleteLater()

    def test_synthesized_classmethod_is_not_written_back(self):
        # A cls-first def gains an @classmethod in the bake that has no
        # counterpart in the source; splicing it back would add one per save.
        n = self._node()
        n.set_methods_source("def setup(cls):\n    return 1\n")
        v = self._view(n)
        try:
            self.assertIn("@classmethod", v.toPlainText())
            member = [r for r in v.regions()
                      if r["kind"] == "method_member"][0]
            self.assertTrue(member.get("synth_classmethod"))
            self._caret_on(v, member["end"], end_of_line=True)
            self._type(v, "  # x")
            v.markSaved()
            saved = n.get_methods_source()
            self.assertNotIn("@classmethod", saved)
            self.assertIn("# x", saved)
        finally:
            v.deleteLater()

    @staticmethod
    def _caret_on(view, line, end_of_line=False):
        block  = view.document().findBlockByNumber(int(line))
        cursor = view.textCursor()
        cursor.setPosition(
            block.position() + (len(block.text()) if end_of_line else 0))
        view.setTextCursor(cursor)

    @staticmethod
    def _type(view, text):
        try:
            from PySide6.QtGui import QKeyEvent
            from PySide6.QtCore import QEvent, Qt as _Qt
        except Exception:
            from PySide2.QtGui import QKeyEvent
            from PySide2.QtCore import QEvent, Qt as _Qt
        for ch in text:
            view.keyPressEvent(QKeyEvent(
                QEvent.KeyPress, _Qt.Key_A, _Qt.NoModifier, ch))

    def test_any_line_of_an_expression_resolves_to_its_tier(self):
        n = self._node()
        v = self._view(n)
        try:
            init = [r for r in v.regions() if r["kind"] == "expr_init"][0]
            self.assertEqual(init["label"], "Init")
            # the region is the hit target, so any of its lines routes
            self.assertIsNotNone(v.regionAt(init["start"]))
            self.assertEqual(v.regionAt(init["start"])["label"], "Init")
        finally:
            v.deleteLater()

    def test_caret_never_rests_in_a_folded_line(self):
        from mpynode.ui.qt_wrapper import QTextCursor

        n = self._node()
        v = self._view(n)
        try:
            init        = [r for r in v.regions() if r["kind"] == "expr_init"][0]
            hidden_line = init["start"] + 1
            cur         = v.textCursor()
            cur.setPosition(
                v.document().findBlockByNumber(hidden_line).position())
            v.setTextCursor(cur)
            self.assertTrue(v.textCursor().block().isVisible(),
                            "caret was left inside a folded block")
            del QTextCursor
        finally:
            v.deleteLater()

    def test_escaped_expression_collapses_onto_its_call_line(self):
        # A carriage return forces the repr'd accumulator form: ``exp = ...``
        # lines, then ``node.set_compute_expression(exp)``. It used to stay
        # fully visible for want of a rail; now the CALL line is the rail and
        # the accumulator lines hide under it.
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name="apiEsc")
        n.set_compute_expression("a = 1\r\nb = 2\n")
        v = self._view(n)
        try:
            comp = [r for r in v.regions() if r["kind"] == "expr_compute"][0]
            self.assertFalse(comp["inline"])
            doc  = v.document()
            rail = v._rail_of(comp)
            self.assertEqual(rail, comp["end"])
            for ln in range(comp["start"], comp["end"] + 1):
                self.assertEqual(doc.findBlockByNumber(ln).isVisible(),
                                 ln == rail, ln)
            self.assertIs(v._placeholders.get(rail), comp)
            self.assertEqual(v._placeholder_label(comp), "‹ 2 lines ›")
        finally:
            v.deleteLater()

    def test_variable_name_parsed_off_a_declaration(self):
        from mpynode.ui.widgets.api_view import _var_name_on

        self.assertEqual(
            _var_name_on("        node.add_variable('board', persistent=True)"),
            "board")
        self.assertEqual(
            _var_name_on('        node.add_variable("b2", persistent=True)'),
            "b2")
        self.assertIsNone(_var_name_on("        node = cls.create(name=name)"))

    def test_survives_a_node_with_no_expressions(self):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name="apiBare")
        v = self._view(n)
        try:
            self.assertIn("class ", v.toPlainText())
            # Expression bodies are the only thing that folds, and this node
            # has none -- nothing generated is hidden on arrival any more.
            self.assertEqual(v.hiddenLineCount(), 0)
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestManagedMarkAndScrolling(unittest.TestCase):
    """The managed mark moved off the text and into the gutter + a wash.

    The old right-edge diamond was drawn at a VIEWPORT-fixed x. Qt scrolls a
    QPlainTextEdit horizontally by blitting and repainting only the newly
    exposed strip, so every diamond got copied sideways and nothing erased the
    copy -- markers smeared into trails across the line.
    """

    def _node(self, name="apiMark"):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name=name)
        n.set_init_expression(
            "\n".join("a%d = %d" % (i, i) for i in range(20)) + "\n")
        n.set_methods_source(
            "def helper(x):\n"
            + "".join("    y%d = x + %d\n" % (i, i) for i in range(40))
            + "    return x\n")
        return n

    def _view(self, py_node):
        from mpynode.ui.widgets.api_view import NDApiView

        v = NDApiView(py_node)
        v.resize(700, 500)
        return v

    def test_no_diamond_is_drawn_anywhere(self):
        import inspect

        from mpynode.ui.widgets import api_view

        self.assertNotIn("◆", inspect.getsource(api_view))

    def test_horizontal_scroll_is_wired_to_a_full_repaint(self):
        n = self._node()
        v = self._view(n)
        try:
            # disconnect() raises if the connection was never made, which is
            # the whole claim: without it the blit leaves stale pixels behind.
            v.horizontalScrollBar().valueChanged.disconnect(
                v._repaint_viewport)
        except (RuntimeError, TypeError) as exc:  # pragma: no cover
            self.fail("hscroll not bound to a repaint: %s" % exc)
        finally:
            v.deleteLater()

    def test_one_rule_decides_generated_for_gutter_and_wash(self):
        # The bar and the tint are two halves of one signal; they read the
        # same predicate so they cannot drift apart.
        n = self._node()
        v = self._view(n)
        try:
            decl = [r for r in v.regions() if r["kind"] == "class_decl"][0]
            self.assertTrue(v._marks_generated(decl, decl["start"]))
            mine = [r for r in v.regions() if v._is_editable(r)]
            self.assertTrue(mine, "expected an editable member region")
            self.assertFalse(v._marks_generated(mine[0], mine[0]["start"]))
        finally:
            v.deleteLater()

    def test_the_gutter_claims_room_for_the_bar(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        n     = self._node()
        v     = self._view(n)
        plain = QtPythonEditor()
        try:
            self.assertGreater(v.lineNumberAreaWidth(),
                               plain.lineNumberAreaWidth())
        finally:
            v.deleteLater()
            plain.deleteLater()

    def test_the_file_opens_on_code_not_on_a_generated_preamble(self):
        # It used to open on 16 lines of export documentation, folded, above
        # the imports. The top of the file belongs to whoever writes it.
        n = self._node()
        v = self._view(n)
        try:
            text = v.toPlainText()
            self.assertNotIn("Baked by the MPyNode Node Designer", text)
            first = next(ln for ln in text.split("\n") if ln.strip())
            self.assertTrue(first.startswith("from mpynode import"), first)
        finally:
            v.deleteLater()

    def test_refresh_keeps_your_place(self):
        # refresh() runs on EVERY return to the tab and calls setPlainText,
        # which sends the caret and the scrollbar home. The tier editors keep
        # their place for free because they are buffers, not projections.
        n = self._node()
        v = self._view(n)
        v.show()
        try:
            doc = v.document()
            target = max(i for i in range(doc.blockCount())
                         if doc.findBlockByNumber(i).isVisible())
            self.assertTrue(v.goToLine(target))
            caret = v.textCursor().blockNumber()
            self.assertEqual(caret, target)
            v.refresh()
            self.assertEqual(v.textCursor().blockNumber(), caret)
        finally:
            v.deleteLater()

    def test_a_restored_caret_never_lands_in_a_fold(self):
        n = self._node()
        v = self._view(n)
        try:
            rail   = [r for r in v.regions() if r["kind"] == "expr_init"][0]
            hidden = rail["start"] + 1
            v._restore_position((hidden, 0, 0, 0))
            self.assertTrue(v.textCursor().block().isVisible())
        finally:
            v.deleteLater()

    def test_restore_clamps_to_a_shorter_document(self):
        n = self._node()
        v = self._view(n)
        try:
            v._restore_position((10 ** 6, 10 ** 6, 10 ** 6, 10 ** 6))
            self.assertLess(v.textCursor().blockNumber(),
                            v.document().blockCount())
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestContextMenuIsGuardedToo(unittest.TestCase):
    """``keyPressEvent`` is not the only way to mutate a document.

    Qt's standard menu wires Cut / Delete straight to the C++ slots, so they
    never reach the keystroke guard and a Python override of ``cut()`` is not
    called either -- the menu has to be rebuilt, not patched.
    """

    def _node(self, name="apiMenu"):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name=name)
        n.set_methods_source(
            "@maya_command(name='doThing')\n"
            "def do_thing(self, count=1):\n"
            "    total = count + 1\n"
            "    return total\n")
        return n

    def _view(self, py_node):
        from mpynode.ui.widgets.api_view import NDApiView

        v = NDApiView(py_node)
        v.resize(700, 500)
        v.show()
        return v

    class _Ev:
        def __init__(self, pt):
            self._pt = pt

        def pos(self):
            return self._pt

    def _point_on(self, view, block_no, col=2):
        from mpynode.ui.qt_wrapper import QTextCursor

        block  = view.document().findBlockByNumber(block_no)
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + min(col, len(block.text())))
        point = view.cursorRect(cursor).center()
        # Prove the coordinate really lands where we meant, rather than
        # silently hit-testing onto a scrolled-away neighbour.
        self.assertEqual(
            view.cursorForPosition(point).block().blockNumber(), block_no)
        return point

    def test_generated_lines_get_the_read_only_menu(self):
        n = self._node()
        v = self._view(n)
        try:
            decl = [r for r in v.regions() if r["kind"] == "class_decl"][0]
            self.assertFalse(
                v._menu_may_mutate(self._Ev(self._point_on(v, decl["start"]))))
        finally:
            v.deleteLater()

    def test_your_own_code_keeps_the_full_menu(self):
        n = self._node()
        v = self._view(n)
        try:
            mine = [r for r in v.regions()
                    if v._is_editable(r) and r["kind"] != "module_zone"][0]
            body = mine["start"] + 2
            self.assertTrue(
                v._menu_may_mutate(self._Ev(self._point_on(v, body, 6))))
        finally:
            v.deleteLater()

    def test_a_selection_reaching_into_generated_text_locks_the_menu(self):
        from mpynode.ui.qt_wrapper import QTextCursor

        n = self._node()
        v = self._view(n)
        try:
            mine   = [r for r in v.regions() if v._is_editable(r)][0]
            point  = self._point_on(v, mine["start"] + 2, 6)
            decl   = [r for r in v.regions() if r["kind"] == "class_decl"][0]
            block  = v.document().findBlockByNumber(decl["start"])
            cursor = v.textCursor()
            cursor.setPosition(block.position())
            cursor.setPosition(block.position() + len(block.text()),
                               QTextCursor.KeepAnchor)
            v.setTextCursor(cursor)
            self.assertTrue(v.textCursor().hasSelection())
            self.assertFalse(v._menu_may_mutate(self._Ev(point)))
        finally:
            v.deleteLater()

    def test_load_from_file_is_offered_normally_but_not_here(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        n     = self._node()
        v     = self._view(n)
        plain = QtPythonEditor()
        try:
            self.assertTrue(plain._offers_file_load())
            self.assertFalse(v._offers_file_load())
        finally:
            v.deleteLater()
            plain.deleteLater()

    def test_a_dismissed_menu_does_not_open_the_file_dialog(self):
        # load_act is None when the action is suppressed, and a dismissed menu
        # returns None too -- so the dispatch has to test "is not None" first.
        import inspect

        from mpynode.ui.widgets.editor_core import QtPythonEditor

        src = inspect.getsource(QtPythonEditor.contextMenuEvent)
        self.assertIn("load_act is not None and chosen is load_act", src)

    def test_an_external_setplaintext_resyncs_the_regions(self):
        # Rename and Promote both apply their rewrite through
        # rename_var._set_editor_text -> setPlainText. Without a resync that
        # unfolds the document and collapses every maintained cursor, and the
        # next save splices the wrong slices back into the Methods source.
        n = self._node()
        v = self._view(n)
        try:
            cursors  = len(v._region_cursors)
            folded   = v.hiddenLineCount()
            baseline = v._methods_from_document()
            v.setPlainText(v.toPlainText())
            self.assertEqual(len(v._region_cursors),     cursors)
            self.assertEqual(v.hiddenLineCount(),        folded)
            self.assertEqual(v._methods_from_document(), baseline)
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestManagedBlocksAreSolid(unittest.TestCase):
    """A blank line between two generated regions belonged to NO region.

    That is the worst of both worlds: unmarked, so it read as yours, and
    outside every region cursor, so typing there was silently refused. It also
    chopped ``build()`` into stripes instead of one managed block.
    """

    def _node(self, name="apiSolid"):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name=name)
        n.add_input_attr("maxVal", "float", default_value=100.0)
        n.add_input_attr("minVal", "float", default_value=1.0)
        n.add_output_attr("sort", "float", is_array=True)
        n.add_variable("board", persistent=True)
        n.set_init_expression("# Init tab\na = 1\nb = 2\n")
        n.set_methods_source("def helper(x):\n    return x\n")
        return n

    def _view(self, py_node):
        from mpynode.ui.widgets.api_view import NDApiView

        v = NDApiView(py_node)
        v.resize(900, 620)
        return v

    def test_no_line_between_regions_belongs_to_nothing(self):
        n = self._node()
        v = self._view(n)
        try:
            claimed = sorted(v._block_region)
            holes = [i for i in range(min(claimed), max(claimed) + 1)
                     if v.regionAt(i) is None]
            self.assertEqual(holes, [], "unclaimed interior lines")
        finally:
            v.deleteLater()

    def test_every_gap_reads_as_managed_and_stays_locked(self):
        n = self._node()
        v = self._view(n)
        try:
            gaps = [i for i in sorted(v._block_region)
                    if v.regionAt(i).get("kind") == "gap"]
            self.assertTrue(gaps, "expected blank separators in the bake")
            for i in gaps:
                region = v.regionAt(i)
                self.assertTrue(v._marks_generated(region, i),
                                "gap %d should paint as managed" % (i + 1))
                self.assertFalse(v._is_editable(region))
        finally:
            v.deleteLater()

    def test_the_blank_line_inside_build_is_no_longer_a_trap(self):
        # The reported bug: a blank line between the inputs and outputs blocks
        # looked editable and refused every keystroke.
        n = self._node()
        v = self._view(n)
        try:
            src    = v.source().split("\n")
            first  = next(i for i, t in enumerate(src) if "--- inputs ---" in t)
            last   = next(i for i, t in enumerate(src) if "--- outputs ---" in t)
            blanks = [i for i in range(first, last) if not src[i].strip()]
            self.assertTrue(blanks, "expected a separator inside build()")
            for i in blanks:
                region = v.regionAt(i)
                self.assertIsNotNone(region)
                self.assertTrue(v._marks_generated(region, i))
                pos = v.document().findBlockByNumber(i).position()
                self.assertFalse(v._allows(pos, pos),
                                 "still locked, and now it looks locked")
        finally:
            v.deleteLater()

    def test_blank_lines_inside_your_own_function_stay_yours(self):
        # A gap INSIDE an editable region is within its span and must never be
        # swept up by the gap fill.
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name="apiOwnGap")
        n.set_methods_source("def helper(x):\n    a = 1\n\n    return a\n")
        v = self._view(n)
        try:
            member = [r for r in v.regions() if v._is_editable(r)][0]
            for i in range(member["start"], member["end"] + 1):
                self.assertIsNot(v.regionAt(i).get("kind"), "gap")
                self.assertTrue(v._is_editable(v.regionAt(i)))
        finally:
            v.deleteLater()

    def test_trailing_blanks_past_the_last_region_are_left_alone(self):
        # Claiming them would paint a managed band under empty space.
        n = self._node()
        v = self._view(n)
        try:
            last = max(v._block_region)
            for i in range(last + 1, v.document().blockCount()):
                self.assertIsNone(v.regionAt(i))
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestOneSignalNotTwo(unittest.TestCase):
    """The per-tier zone bands are gone, and the wash follows the palette."""

    def _view(self):
        from mpynode import MPyNode
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        n = MPyNode.create(name="apiOneSig")
        n.set_init_expression("# Init tab\na = 1\nb = 2\nc = 3\n")
        v = NDApiView(n)
        v.resize(900, 620)
        return v

    def test_zone_colours_are_gone(self):
        from mpynode.ui.widgets import api_view

        self.assertFalse(hasattr(api_view, "_ZONE_COLORS"))

    def test_the_wash_is_derived_from_the_palette_not_hard_coded(self):
        # The editor is dark in Maya and light in a headless render. A fixed
        # grey vanishes against one of them; blending toward the palette's
        # text colour reads as grey on both.
        from mpynode.ui.qt_wrapper import QPalette
        from mpynode.ui.widgets.api_view import _TINT_ALPHA

        v = self._view()
        try:
            wash = v._wash(_TINT_ALPHA)
            text = v.palette().color(QPalette.Text)
            self.assertEqual(
                (wash.red(), wash.green(), wash.blue()),
                (text.red(), text.green(), text.blue()))
            self.assertEqual(wash.alpha(), _TINT_ALPHA)
        finally:
            v.deleteLater()

    def test_the_placeholder_sits_where_the_body_was(self):
        # Drawn from open_col and left-aligned there. Right-aligned at the
        # viewport edge it landed ON TOP of the code whenever the rail line
        # was long enough to reach.
        import inspect

        from mpynode.ui.widgets.api_view import NDApiView

        src = inspect.getsource(NDApiView._paint_placeholder)
        self.assertIn("open_col", src)
        self.assertIn("AlignLeft", src)

    def test_every_expression_rail_carries_a_placeholder(self):
        # Drawn, not clicked: the rail routes to the tier like the rest of
        # the line, and "Go to" lives in the context menu.
        v = self._view()
        try:
            rails = [r for r in v.regions()
                     if r.get("body_col") and r["kind"].startswith("expr_")]
            self.assertTrue(rails)
            for r in rails:
                self.assertIs(v._placeholders.get(v._rail_of(r)), r)
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestTheEditGuardBoundary(unittest.TestCase):
    """Insertion and removal need DIFFERENT rules at a region's first char.

    Measured: with a maintained cursor on 865..960, inserting at 865 moves it
    to 866..961 and leaves the new character OUTSIDE, so the write-back drops
    it. Removal has no such ambiguity -- taking text off the front just
    shrinks the selection.

    Applying the insert rule to both made the first character of every region
    immortal: you could backspace a class away letter by letter and be left
    with a lone ``c`` that nothing could delete, i.e. a syntax error the editor
    would not let you repair.
    """

    METHODS = (
        "class SetupError(Exception):\n"
        '    """Cannot support setup."""\n'
        "\n\n"
        "def _has_shape(node, shape_types):\n"
        "    return False\n"
    )

    def _view(self, name="apiGuard"):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        node = MPyLocator.create(name=name)
        node.set_methods_source(self.METHODS)
        view = NDApiView(node)
        view.resize(1000, 700)
        return node, view

    def _span(self, view, region):
        doc   = view.document()
        first = doc.findBlockByNumber(region["start"])
        last  = doc.findBlockByNumber(view._claim_end(region))
        return first.position(), last.position() + len(last.text())

    def _first_editable(self, view):
        return sorted((r for r in view.regions() if view._is_editable(r)),
                      key=lambda r: r["start"])[0]

    def test_a_whole_region_can_be_selected_and_deleted(self):
        _node, v = self._view()
        try:
            lo, hi = self._span(v, self._first_editable(v))
            self.assertTrue(v._allows(lo, hi, removing=True))
        finally:
            v.deleteLater()

    def test_the_first_character_can_be_removed(self):
        _node, v = self._view()
        try:
            lo, _hi = self._span(v, self._first_editable(v))
            self.assertTrue(v._allows(lo, lo + 1, removing=True))
        finally:
            v.deleteLater()

    def test_inserting_at_the_anchor_is_still_refused(self):
        # The load-bearing half: relaxing this would lose the character.
        _node, v = self._view()
        try:
            lo, _hi = self._span(v, self._first_editable(v))
            self.assertFalse(v._allows(lo, lo))
            self.assertTrue(v._allows(lo + 1, lo + 1))
        finally:
            v.deleteLater()

    def test_a_removal_may_not_reach_outside_the_region(self):
        _node, v = self._view()
        try:
            lo, hi = self._span(v, self._first_editable(v))
            self.assertFalse(v._allows(lo - 1, lo + 1, removing=True))
            self.assertFalse(v._allows(lo, hi + 5, removing=True))
        finally:
            v.deleteLater()

    def test_deleting_a_class_reaches_the_methods_source_and_still_parses(self):
        import ast

        from mpynode.ui.qt_wrapper import QTextCursor

        node, v = self._view()
        v.show()
        try:
            region = self._first_editable(v)
            lo, hi = self._span(v, region)
            cursor = v.textCursor()
            cursor.setPosition(lo)
            cursor.setPosition(hi, QTextCursor.KeepAnchor)
            v.setTextCursor(cursor)
            self.assertTrue(v._allows(lo, hi, removing=True))
            cursor.removeSelectedText()
            v._after_edit()
            v.markSaved()
            source = node.get_methods_source()
            self.assertNotIn("class SetupError", source)
            self.assertIn("_has_shape", source, "the neighbour must survive")
            ast.parse(source)
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestGapsFollowTheirNeighbour(unittest.TestCase):
    """A blank line between two of YOUR functions is yours, not the bake's."""

    METHODS = (
        "def one(x):\n    return x\n"
        "\n\n"
        "def two(x):\n    return x\n"
    )

    def _view(self, name="apiGaps"):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        node = MPyLocator.create(name=name)
        node.set_methods_source(self.METHODS)
        view = NDApiView(node)
        view.resize(1000, 700)
        return node, view

    def test_no_gap_between_two_editable_regions_reads_as_managed(self):
        _node, v = self._view()
        try:
            regions   = sorted(v.regions(), key=lambda r: r["start"])
            offenders = []
            for a, b in zip(regions, regions[1:]):
                if not (v._is_editable(a) and v._is_editable(b)):
                    continue
                for line in range(a["end"] + 1, b["start"]):
                    if v._marks_generated(v.regionAt(line), line):
                        offenders.append(line + 1)
            self.assertEqual(offenders, [])
        finally:
            v.deleteLater()

    def test_you_can_type_in_the_gap_after_your_own_function(self):
        _node, v = self._view()
        try:
            first = sorted((r for r in v.regions() if v._is_editable(r)),
                           key=lambda r: r["start"])[0]
            gap = first["end"] + 1
            self.assertFalse(v.source().split("\n")[gap].strip(),
                             "expected a blank separator")
            pos = v.document().findBlockByNumber(gap).position()
            self.assertTrue(v._allows(pos, pos))
        finally:
            v.deleteLater()

    def test_a_gap_after_generated_code_stays_locked(self):
        # Directionality is the rule: a gap joins the region ABOVE it. After
        # the hoisted imports there is nothing of yours to attach to, so it
        # stays the bake's. (The gap before ``class`` is a different case --
        # it follows YOUR last function, so it is yours.)
        _node, v = self._view()
        try:
            imports = [r for r in v.regions() if r["kind"] == "imports"][0]
            after   = imports["end"] + 1
            region  = v.regionAt(after)
            self.assertIsNotNone(region)
            self.assertFalse(v.source().split("\n")[after].strip())
            self.assertTrue(v._marks_generated(region, after))
            self.assertFalse(v._is_editable(region))
        finally:
            v.deleteLater()

    def test_the_gap_before_the_class_belongs_to_your_last_function(self):
        _node, v = self._view()
        try:
            decl   = [r for r in v.regions() if r["kind"] == "class_decl"][0]
            before = decl["start"] - 1
            region = v.regionAt(before)
            self.assertIsNotNone(region)
            self.assertTrue(v._is_editable(region),
                            "module scope: you must be able to add a def here")
        finally:
            v.deleteLater()

    def test_saving_repeatedly_does_not_grow_blank_lines(self):
        # _claim_end pulls blank lines the BAKE added into the region, and the
        # Methods source never held them. Without the trailing strip on
        # write-back the file gains a blank line on every single save.
        node, v = self._view()
        try:
            before = node.get_methods_source()
            for _ in range(4):
                v.markSaved()
                v.refresh(force=True)
            self.assertEqual(node.get_methods_source(), before)
        finally:
            v.deleteLater()

    def test_the_strip_helper_leaves_interior_blanks_alone(self):
        from mpynode.ui.widgets.api_view import _strip_trailing_blanks

        self.assertEqual(_strip_trailing_blanks("a\n\nb\n\n\n"), "a\n\nb")
        self.assertEqual(_strip_trailing_blanks("a"),            "a")
        self.assertEqual(_strip_trailing_blanks("\n\n"),         "")


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestBodiesNeverOpenHere(unittest.TestCase):
    """Every expression tier is ONE line here, always.

    ``node.set_init_expression(‹ 4 lines ›)``: the body is authored in its own
    tab, so this view hides it entirely -- including the first body line, which
    the exporter puts on the call line, and including one-line bodies, which
    used to have nothing below the rail to fold and so showed in full, looking
    editable. Nothing expands; right-click > Go to <tier> is the way in. The
    count is the body's own line count, not the number of hidden blocks, which
    under-counted a two-line compute as ``‹ 1 lines ›``.
    """

    def _view(self, name="apiFold", init="# Init\na = 1\nb = 2\nc = 3\n",
              compute=None):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        node = MPyLocator.create(name=name)
        node.set_init_expression(init)
        if compute is not None:
            node.set_compute_expression(compute)
        view = NDApiView(node)
        view.resize(1000, 700)
        view.show()
        # Offscreen, repaint() on an unmapped widget is a no-op, so the paint
        # pass that records the marker rects never runs without this.
        _QAPP.processEvents()
        return node, view

    def _repaint(self, view):
        view.repaint()
        _QAPP.processEvents()

    def _rail(self, view, kind="expr_init"):
        return [r for r in view.regions() if r["kind"] == kind][0]

    # -- what is hidden ---------------------------------------------------

    def test_only_expression_bodies_are_hidden_on_arrival(self):
        _node, v = self._view()
        try:
            doc = v.document()
            hidden = {i for i in range(doc.blockCount())
                      if not doc.findBlockByNumber(i).isVisible()}
            self.assertTrue(hidden, "the init body should be hidden")
            covered = set()
            for r in v._placeholder_regions():
                covered.update(ln for ln in range(r["start"], r["end"] + 1)
                               if ln != v._rail_of(r))
            self.assertEqual(hidden, covered,
                             "something other than an expression body hid")
        finally:
            v.deleteLater()

    def test_the_users_own_header_is_never_hidden(self):
        # It is THEIR text at the top of THEIR file. Hiding it would repeat
        # the preamble mistake with the one block that is not generated.
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        node = MPyLocator.create(name="apiOwnHdr")
        node.set_methods_source("# Mine.\n# Two lines of it.\n\ndef f(self):\n    return 1\n")
        v = NDApiView(node)
        v.resize(1000, 700)
        try:
            header = [r for r in v.regions() if r["kind"] == "header"][0]
            doc    = v.document()
            for ln in range(header["start"], header["end"] + 1):
                self.assertTrue(doc.findBlockByNumber(ln).isVisible(), ln)
            self.assertNotIn(header["start"], v._placeholders)
        finally:
            v.deleteLater()

    def test_a_one_line_body_is_a_placeholder_too(self):
        _node, v = self._view(init="import numpy as np")
        try:
            init = self._rail(v)
            self.assertEqual(init["start"], init["end"])
            self.assertIs(v._placeholders.get(v._rail_of(init)), init)
            self.assertEqual(v._placeholder_label(init), "‹ 1 line ›")
            self._repaint(v)
            self.assertIn(init["start"], v._marker_rects)
        finally:
            v.deleteLater()

    def test_the_count_is_the_bodys_line_count(self):
        _node, v = self._view(
            init="\n".join("a%d = %d" % (i, i) for i in range(20)) + "\n",
            compute="pts = self.inPosition\nself.out = pts")
        try:
            self.assertEqual(v._placeholder_label(self._rail(v)),
                             "‹ 20 lines ›")
            self.assertEqual(v._placeholder_label(self._rail(v, "expr_compute")),
                             "‹ 2 lines ›")
        finally:
            v.deleteLater()

    def test_the_hidden_bodies_survive_the_rebake(self):
        # refresh() runs on every return to the tab, and setPlainText clears
        # every visibility flag.
        _node, v = self._view()
        try:
            before = v.hiddenLineCount()
            self.assertGreater(before, 0)
            v.refresh(force=True)
            self.assertEqual(v.hiddenLineCount(), before)
        finally:
            v.deleteLater()

    def test_the_rail_keeps_its_managed_mark_after_lines_are_added_above(self):
        # Return on a blank line above the class pushes every rail down. The
        # mark used to compare against the BAKE's line number and so fell off
        # the moved rail: the call text lost its wash while the placeholder
        # stayed (the averagePosition_broken.mpn report).
        try:
            from PySide6.QtGui import QKeyEvent
            from PySide6.QtCore import QEvent
        except Exception:
            from PySide2.QtGui import QKeyEvent
            from PySide2.QtCore import QEvent
        from mpynode.ui.qt_wrapper import Qt as _Qt

        _node, v = self._view()
        try:
            rail = self._rail(v)
            before = v._rail_of(rail)
            self.assertTrue(v._marks_generated(rail, before))
            doc = v.document()
            blank = [i for i in range(rail["start"])
                     if not doc.findBlockByNumber(i).text().strip()][0]
            cur = v.textCursor()
            cur.setPosition(doc.findBlockByNumber(blank).position())
            v.setTextCursor(cur)
            for _ in range(3):
                v.keyPressEvent(QKeyEvent(QEvent.KeyPress, _Qt.Key_Return,
                                          _Qt.NoModifier, "\r"))
            live = [b for b, r in v._placeholders.items() if r is rail][0]
            self.assertEqual(live, before + 3)
            self.assertTrue(v._marks_generated(rail, live))
            self.assertFalse(v._marks_generated(rail, before))
        finally:
            v.deleteLater()

    # -- nothing opens ----------------------------------------------------

    def test_nothing_expands(self):
        import inspect

        from mpynode.ui.widgets.api_view import NDApiView

        _node, v = self._view()
        try:
            self.assertFalse(hasattr(v, "toggleFoldAt"))
            src = inspect.getsource(NDApiView.contextMenuEvent)
            self.assertNotIn("Expand Body", src)
            self.assertNotIn("Collapse Body", src)
        finally:
            v.deleteLater()

    def test_go_to_names_the_tab_that_authors_the_line(self):
        _node, v = self._view(compute="x = 1\n")
        try:
            seen = []
            v.tierActivated.connect(seen.append)
            text, fire = v._go_to_target(self._rail(v), "")
            self.assertEqual(text, "Go to Init")
            fire()
            self.assertEqual(seen, ["Init"])
            text, _fire = v._go_to_target(self._rail(v, "expr_compute"), "")
            self.assertEqual(text, "Go to Compute")
            decl = [r for r in v.regions() if r["kind"] == "class_decl"][0]
            self.assertIsNone(v._go_to_target(decl, ""))
        finally:
            v.deleteLater()

    # -- the placeholder --------------------------------------------------

    def test_the_placeholder_covers_the_opening_delimiter_too(self):
        # It starts at open_col -- where the call's argument begins -- NOT at
        # body_col, which is three columns further right, past the opening
        # delimiter. Anchored at body_col the reader was left looking at a
        # bare triple quote and the first character of a body the count says
        # is not being shown.
        _node, v = self._view()
        try:
            self._repaint(v)
            rail = self._rail(v)
            rect = v._marker_rects.get(rail["start"])
            self.assertIsNotNone(rect, "no placeholder was drawn on the rail")
            metrics = v.fontMetrics()
            try:
                char_w = metrics.horizontalAdvance("9")
            except AttributeError:
                char_w = metrics.width("9")
            # The gap between the two IS the delimiter, and it is what the
            # placeholder swallows.
            self.assertEqual(rail["body_col"] - rail["open_col"], 3)
            open_at = (int(v.contentOffset().x())
                       + int(rail["open_col"] * char_w))
            self.assertEqual(rect[0], open_at)
        finally:
            v.deleteLater()

    def test_the_rail_shows_no_quotes_at_all(self):
        # The rail used to open on a triple-SINGLE quote and close on a
        # triple-DOUBLE one, because the closer was hardcoded while the opener
        # is whichever of the two the exporter picked to dodge a collision in
        # the body. Covering the whole argument means neither delimiter is
        # drawn, so the two can no longer disagree.
        _node, v = self._view()
        try:
            self._repaint(v)
            rail    = self._rail(v)
            drawn   = v.document().findBlockByNumber(rail["start"]).text()
            visible = drawn[:rail["open_col"]]
            self.assertNotIn("'", visible)
            self.assertNotIn('"', visible)
            self.assertTrue(visible.rstrip().endswith("("), visible)
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestGoToReachesTheTab(unittest.TestCase):
    def test_tier_activation_switches_the_strip(self):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        mc.file(new=True, force=True)
        loc = MPyLocator.create(name="apiGoTo")
        loc.set_init_expression("a = 1\n")
        w = NDScriptTabContent(loc)
        try:
            tabs   = w._inner_tabs
            labels = [tabs.tabText(i) for i in range(tabs.count())]
            tabs.setCurrentIndex(labels.index("API"))
            w._api_view.tierActivated.emit("Init")
            self.assertEqual(tabs.tabText(tabs.currentIndex()), "Init")
            w._api_view.tierActivated.emit("Compute")
            self.assertEqual(tabs.tabText(tabs.currentIndex()), "Compute")
        finally:
            w.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestPersistentValuesAreManagedPlaceholders(unittest.TestCase):
    """The API view shows the node as it IS: a persistent variable holding a
    value renders as ``node.set_variable('board', ‹ list · 3 items ›,
    persistent=True)`` -- managed, never expandable, the data never on screen
    -- and a None value as the plain declaration. Right-click: Go to Variables
    · name."""

    def _node(self):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name="apiVals")
        n.add_input_attr("a", "float")
        n.add_output_attr("out", "float")
        n.set_compute_expression("self.out = self.a")
        n.add_variable("board", persistent=True)
        n.set_variable("board", [1, 2, 3])
        n.add_variable("empty", persistent=True)
        return n

    def _view(self, n):
        from mpynode.ui.widgets.api_view import NDApiView

        v = NDApiView(n)
        v.resize(1000, 700)
        v.show()
        _QAPP.processEvents()
        return v

    def test_a_held_value_is_a_set_variable_placeholder(self):
        v = self._view(self._node())
        try:
            self.assertIn("node.set_variable('board', [1, 2, 3], persistent=True)",
                          v.source())
            self.assertIn("node.add_variable('empty', persistent=True)", v.source())
            vars_r = [r for r in v.regions() if r["kind"] == "vars"][0]
            (entry,) = vars_r["values"]
            line_no = vars_r["start"] + entry["offset"]
            self.assertIs(v._value_placeholders.get(line_no), entry)
            v.repaint()
            _QAPP.processEvents()
            self.assertIn(line_no, v._marker_rects, "no placeholder painted")
            # Managed: refuses edits, no expand.
            self.assertFalse(v._is_editable(vars_r))
            self.assertFalse(hasattr(v, "toggleFoldAt"))
        finally:
            v.deleteLater()

    def test_go_to_and_click_name_the_variable_on_a_value_line(self):
        from mpynode.ui.widgets.api_view import _var_name_on

        v = self._view(self._node())
        try:
            vars_r = [r for r in v.regions() if r["kind"] == "vars"][0]
            (entry,) = vars_r["values"]
            text = v.document().findBlockByNumber(
                vars_r["start"] + entry["offset"]).text()
            self.assertEqual(_var_name_on(text), "board")
            seen = []
            v.variableActivated.connect(seen.append)
            label, fire = v._go_to_target(vars_r, text)
            self.assertEqual(label, "Go to Variables · board")
            fire()
            self.assertEqual(seen, ["board"])
        finally:
            v.deleteLater()

    def test_a_blob_value_brings_a_generated_helper(self):
        import numpy as np

        from mpynode.ui.widgets.api_view import _GENERATED_KINDS

        n = self._node()
        n.set_variable("board", np.arange(3.0))
        v = self._view(n)
        try:
            helper = [r for r in v.regions() if r["kind"] == "helpers"][0]
            self.assertIn("helpers", _GENERATED_KINDS)
            self.assertFalse(v._is_editable(helper))
            for ln in range(helper["start"], helper["end"] + 1):
                self.assertTrue(v._marks_generated(helper, ln))
            (entry,) = [r for r in v.regions() if r["kind"] == "vars"][0]["values"]
            self.assertEqual(entry["summary"], "ndarray (3,) float64 · 24 B")
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestTheModuleZoneIsYours(unittest.TestCase):
    """The blank lines between the imports and ``class`` on a node with no
    module-scope code yet. Return could open them and nothing could be typed
    into them -- "a gap holds no text in the node's data model". Now they are
    the module zone: what is typed there is inserted into the Methods source
    after its imports and re-bakes as module_segment regions, so the space is
    editable the way everything else that is yours is.
    """

    def _view(self, name="apiZone", methods=None):
        from mpynode.wrappers.mpy_locator import MPyLocator
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        node = MPyLocator.create(name=name)
        node.set_init_expression("import math\n")
        if methods is not None:
            node.set_methods_source(methods)
        view = NDApiView(node)
        view.resize(1000, 700)
        return node, view

    def _zone(self, view):
        hits = [r for r in view.regions() if r["kind"] == "module_zone"]
        return hits[0] if hits else None

    def _caret(self, view, block_no, col=0):
        block  = view.document().findBlockByNumber(block_no)
        cursor = view.textCursor()
        cursor.setPosition(block.position() + col)
        view.setTextCursor(cursor)

    def _type(self, view, text):
        # Through keyPressEvent, the way a user types: that is the path that
        # runs the edit guard and re-indexes the regions after each key.
        try:
            from PySide6.QtGui import QKeyEvent
            from PySide6.QtCore import QEvent
        except ImportError:
            from PySide2.QtGui import QKeyEvent
            from PySide2.QtCore import QEvent
        from mpynode.ui.qt_wrapper import Qt

        for ch in text:
            if ch == "\n":
                view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return,
                                             Qt.NoModifier, "\r"))
            else:
                view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_A,
                                             Qt.NoModifier, ch))

    def test_the_zone_sits_between_the_imports_and_the_class(self):
        _node, v = self._view()
        try:
            zone = self._zone(v)
            self.assertIsNotNone(zone, "no module zone on a plain node")
            imports = [r for r in v.regions() if r["kind"] == "imports"][0]
            decl    = [r for r in v.regions() if r["kind"] == "class_decl"][0]
            self.assertEqual(zone["start"], imports["end"] + 1)
            self.assertEqual(zone["end"], decl["start"] - 1)
            lines = v.source().split("\n")
            for ln in range(zone["start"], zone["end"] + 1):
                self.assertEqual(lines[ln].strip(), "")
            self.assertEqual(zone["src_line"], 1)     # empty Methods source
            self.assertEqual(zone["src_lines"], 0)
        finally:
            v.deleteLater()

    def test_the_zone_is_editable_and_unwashed(self):
        _node, v = self._view()
        try:
            zone = self._zone(v)
            self.assertTrue(v._is_editable(zone))
            for ln in range(zone["start"], zone["end"] + 1):
                self.assertFalse(v._marks_generated(zone, ln), ln)
                self.assertIs(v.regionAt(ln), zone)
            pos = v.document().findBlockByNumber(zone["start"]).position()
            self.assertTrue(v._allows(pos, pos), "typing at the zone's first char")
            # The gaps INSIDE build() are still the bake's.
            header = [r for r in v.regions() if r["kind"] == "expr_header"][0]
            gap_pos = v.document().findBlockByNumber(header["start"] - 1).position()
            self.assertFalse(v._allows(gap_pos, gap_pos))
        finally:
            v.deleteLater()

    def test_an_untouched_zone_is_not_dirty_and_saves_nothing(self):
        node, v = self._view()
        try:
            self.assertFalse(v.hasUnsavedChanges())
            self.assertEqual(v._methods_from_document(), node.get_methods_source() or "")
            self.assertNotIn("class_decl", v._spacing_from_document())
        finally:
            v.deleteLater()

    def test_code_typed_in_the_zone_lands_after_the_imports_and_rebakes(self):
        node, v = self._view()
        try:
            zone = self._zone(v)
            self._caret(v, zone["start"])
            self._type(v, "CONST = 3")
            self.assertTrue(v.hasUnsavedChanges())
            v.markSaved()
            src = node.get_methods_source() or ""
            self.assertTrue(src.startswith("CONST = 3"), src)
            self.assertEqual(src.count("CONST = 3"), 1)
            # Saving re-bakes, so the view is clean and describes the node --
            # NOT dirty because the insertion would be applied a second time.
            self.assertFalse(v.hasUnsavedChanges())
            kinds = [r["kind"] for r in v.regions()]
            self.assertIn("module_segment", kinds)
            self.assertNotIn("module_zone", kinds, "code above the class now owns the gap")
            seg = [r for r in v.regions() if r["kind"] == "module_segment"][0]
            self.assertEqual(seg["label"], "CONST")
            self.assertIn("CONST = 3", v.source().split("\n")[seg["start"]])
            # The user's own function stays editable after the round trip.
            self.assertTrue(v._is_editable(seg))
        finally:
            v.deleteLater()

    def test_the_insertion_follows_existing_imports_and_header(self):
        # A Methods source that has imports and a header but no other module
        # code: the zone exists, and typed code goes BELOW the imports.
        methods = '"""Header."""\nimport os\n\n\ndef setup(self):\n    return 1\n'
        node, v = self._view(name="apiZoneImports", methods=methods)
        try:
            zone = self._zone(v)
            self.assertIsNotNone(zone)
            self.assertEqual(zone["src_line"], 3)   # after the docstring + import
            self._caret(v, zone["start"])
            self._type(v, "LIMIT = 4")
            v.markSaved()
            self.assertFalse(v.hasUnsavedChanges())
            lines = (node.get_methods_source() or "").split("\n")
            self.assertEqual(lines[:4], ['"""Header."""', "import os", "LIMIT = 4", ""])
            self.assertIn("def setup(self):", lines)
        finally:
            v.deleteLater()

    def test_blank_lines_typed_in_the_zone_are_not_code_and_not_spacing(self):
        node, v = self._view()
        try:
            zone = self._zone(v)
            self._caret(v, zone["start"])
            self._type(v, "\n\n")
            self.assertFalse(v.hasUnsavedChanges(),
                             "blank lines in the zone are neither code nor a stored count")
            self.assertNotIn("class_decl", v._spacing_from_document())
        finally:
            v.deleteLater()

    def test_a_node_with_module_code_gets_no_zone(self):
        _node, v = self._view(name="apiZoneNone",
                              methods="def helper(x):\n    return x\n")
        try:
            self.assertIsNone(self._zone(v))
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestAClickGoesWhereTheThingIsAuthored(unittest.TestCase):
    """A generated block is a read-only rendering of something the user edits
    somewhere else. Clicking it LOCATES it: the view reports the region and
    the host lights the Outline row (opening the pane if it was railed away).
    Nothing navigates on a left click; the right-click Go to does (2026-09:
    single = locate, double / right-click = go edit).

    The regression this pins: the fold marker used to swallow the click, so
    ``‹ 80 lines ›`` -- the one part of the rail a user would aim at to reach
    their Compute code -- was the only part that refused to.
    """

    def _view(self, name="apiJump"):
        from mpynode import MPyNode
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        node = MPyNode.create(name=name)
        node.add_input_attr("inFloat", "float")
        node.add_output_attr("outFloat", "float")
        node.set_init_expression("import math\nseed = 1\nscale = 2\n")
        node.set_compute_expression(
            "\n".join("row_%02d = %d" % (i, i) for i in range(30)) + "\n")
        view = NDApiView(node)
        view.resize(1200, 800)
        view.show()
        _QAPP.processEvents()
        view.repaint()
        _QAPP.processEvents()
        return node, view

    def _click(self, view, point):
        from mpynode.ui.qt_wrapper import Qt
        try:
            from PySide6.QtGui import QMouseEvent
            from PySide6.QtCore import QEvent, QPointF
        except Exception:
            from PySide2.QtGui import QMouseEvent
            from PySide2.QtCore import QEvent, QPointF
        view.mousePressEvent(QMouseEvent(
            QEvent.MouseButtonPress, QPointF(point),
            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        _QAPP.processEvents()

    def _mid_of(self, view, line):
        block = view.document().findBlockByNumber(line)
        geo = view.blockBoundingGeometry(block).translated(
            view.contentOffset())
        return _QPoint(8, int(geo.top() + geo.height() / 2))

    def test_clicking_the_fold_marker_reports_the_tier_and_stays_put(self):
        # It used to raise the Compute tab. Retracted: the tier is already on
        # screen under the marker, so the jump cost the reader their place. It
        # reports the region -- the host highlights -- and nothing moves.
        _node, v = self._view()
        seen = []
        v.regionActivated.connect(seen.append)
        try:
            rail = [r for r in v.regions()
                    if r["kind"] == "expr_compute"][0]["start"]
            rect = v._marker_rects.get(rail)
            self.assertIsNotNone(rect, "no marker to aim at")
            hidden = v.hiddenLineCount()
            x0, x1, y0, y1 = rect
            self._click(v, _QPoint(int((x0 + x1) / 2), int((y0 + y1) / 2)))
            self.assertEqual([r["label"] for r in seen], ["Compute"])
            self.assertEqual(v.hiddenLineCount(), hidden,
                             "the click must not also expand the body")
        finally:
            v.deleteLater()

    def test_clicking_the_call_text_reports_the_same_way(self):
        # Both halves of the rail mean the same thing, so they must agree.
        _node, v = self._view()
        seen = []
        v.regionActivated.connect(seen.append)
        try:
            rail = [r for r in v.regions()
                    if r["kind"] == "expr_init"][0]["start"]
            self._click(v, self._mid_of(v, rail))
            self.assertEqual([r["label"] for r in seen], ["Init"])
        finally:
            v.deleteLater()

    def test_a_left_click_never_emits_the_tier_signal(self):
        # The signal exists again for the right-click "Go to <tier>" menu
        # (2026-09), but a LEFT click on a rail still only highlights: the
        # teleport that cost the reader their place stays retracted.
        _node, v = self._view()
        seen = []
        v.tierActivated.connect(seen.append)
        try:
            rail = [r for r in v.regions()
                    if r["kind"] == "expr_compute"][0]["start"]
            self._click(v, self._mid_of(v, rail))
            self.assertEqual(seen, [])
        finally:
            v.deleteLater()

    def test_a_left_click_locates_variables_and_attributes_too(self):
        # They used to open their tabs on a click while an expression did not;
        # now every generated line answers the same way -- the region, for the
        # host to highlight -- and the right-click Go to is the way there.
        _node, v = self._view()
        _node.set_variable("board", [1, 2, 3], persistent=True)
        v.refresh(force=True)
        _QAPP.processEvents()
        regions, vars_seen, attrs_seen = [], [], []
        v.regionActivated.connect(regions.append)
        v.variableActivated.connect(vars_seen.append)
        v.attributesActivated.connect(attrs_seen.append)
        try:
            vars_r = [r for r in v.regions() if r["kind"] == "vars"][0]
            attrs = [r for r in v.regions() if r["kind"] == "attrs_in"][0]
            self._click(v, self._mid_of(v, vars_r["start"] + 1))
            self._click(v, self._mid_of(v, attrs["start"] + 1))
            self.assertEqual([r["kind"] for r in regions], ["vars", "attrs_in"])
            self.assertEqual(vars_seen, [])
            self.assertEqual(attrs_seen, [])
        finally:
            v.deleteLater()

    def test_go_to_still_reaches_variables_and_attributes(self):
        _node, v = self._view()
        _node.set_variable("board", [1, 2, 3], persistent=True)
        v.refresh(force=True)
        _QAPP.processEvents()
        vars_seen, attrs_seen = [], []
        v.variableActivated.connect(vars_seen.append)
        v.attributesActivated.connect(attrs_seen.append)
        try:
            vars_r = [r for r in v.regions() if r["kind"] == "vars"][0]
            line = v.document().findBlockByNumber(vars_r["start"] + 1).text()
            text, fire = v._go_to_target(vars_r, line)
            self.assertEqual(text, "Go to Variables · board")
            fire()
            attrs = [r for r in v.regions() if r["kind"] == "attrs_in"][0]
            text, fire = v._go_to_target(attrs, "")
            self.assertEqual(text, "Go to Inputs")
            fire()
            self.assertEqual(vars_seen, ["board"])
            self.assertEqual(attrs_seen, ["Inputs"])
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestYouCanMakeRoomAroundAManagedBlock(unittest.TestCase):
    """Return opens a line above a managed block; Backspace closes it again.

    The rule the user asked for, and the reason it needs both halves: a fold,
    a gap or a boundary that can be collapsed but not restored is a one-way
    door. Return with the caret at the head of ANY block pushes it down;
    Backspace in the blank run above it pulls it back up until the two blocks
    touch.

    WHERE THE RESULT LIVES depends on the boundary, and that is not a detail:
    the top of the file is Methods lines 1..N (real text, spliced back), while
    a gap inside ``build()`` has no text to hold, so only the COUNT is stored
    -- on the node, because the view re-bakes its buffer on every visit and
    spacing kept in the widget would not survive a tab switch.
    """

    def _view(self, name="apiRoom"):
        from mpynode import MPyNode
        from mpynode.ui.widgets.api_view import NDApiView

        mc.file(new=True, force=True)
        node = MPyNode.create(name=name)
        node.add_input_attr("inFloat", "float")
        node.add_output_attr("outFloat", "float")
        node.set_compute_expression("self.outFloat = self.inFloat\n")
        view = NDApiView(node)
        view.resize(900, 600)
        return node, view

    def _key(self, view, key, text=""):
        from mpynode.ui.qt_wrapper import Qt
        try:
            from PySide6.QtGui import QKeyEvent
            from PySide6.QtCore import QEvent
        except ImportError:            # pragma: no cover
            from PySide2.QtGui import QKeyEvent
            from PySide2.QtCore import QEvent
        view.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text))

    @property
    def _Qt(self):
        from mpynode.ui.qt_wrapper import Qt

        return Qt

    def _caret(self, view, block_no, col=0):
        block  = view.document().findBlockByNumber(block_no)
        cursor = view.textCursor()
        cursor.setPosition(block.position() + col)
        view.setTextCursor(cursor)

    def _line_of(self, view, needle):
        for i, text in enumerate(view.toPlainText().split("\n")):
            if needle in text:
                return i
        raise AssertionError("no line holding %r" % needle)

    # -- the top of the file ------------------------------------------------

    def test_return_on_line_one_pushes_the_file_down(self):
        _node, v = self._view()
        try:
            self.assertTrue(v.toPlainText().startswith("from mpynode import"))
            self._caret(v, 0)
            self._key(v, self._Qt.Key_Return, "\n")
            lines = v.toPlainText().split("\n")
            self.assertEqual(lines[0], "")
            self.assertTrue(lines[1].startswith("from mpynode import"))
            # ...and the caret is in the room, not below it. Qt leaves it at
            # the head of the block that moved; the next keystroke would go to
            # the wrong line and be refused.
            self.assertEqual(v.textCursor().blockNumber(), 0)
        finally:
            v.deleteLater()

    def test_typing_before_the_imports_is_still_refused(self):
        # Only a NEWLINE is safe at that exact spot -- a character would land
        # on the generated line itself.
        _node, v = self._view()
        refused = []
        v.editRefused.connect(refused.append)
        try:
            self._caret(v, 0)
            self._key(v, self._Qt.Key_A, "a")
            self.assertTrue(refused)
            self.assertTrue(
                v.toPlainText().startswith("from mpynode import"))
        finally:
            v.deleteLater()

    def test_the_room_you_made_is_yours_to_write_in(self):
        node, v = self._view()
        try:
            self._caret(v, 0)
            self._key(v, self._Qt.Key_Return, "\n")
            for ch in "# mine":
                self._key(v, self._Qt.Key_A, ch)
            self.assertEqual(v.toPlainText().split("\n")[0], "# mine")
            v.markSaved()
            self.assertIn("# mine", node.get_methods_source() or "")
            v.refresh()
            self.assertEqual(v.toPlainText().split("\n")[0], "# mine")
        finally:
            v.deleteLater()

    def test_deleting_the_header_puts_the_code_back_on_line_one(self):
        node, v = self._view()
        try:
            node.set_methods_source("# gone soon\n\ndef helper(x):\n"
                                    "    return x\n")
            # force: writing the plug from outside makes this view's baseline
            # stale, which reads as "dirty", which makes refresh a no-op.
            v.refresh(force=True)
            self.assertEqual(v.toPlainText().split("\n")[0], "# gone soon")
            from mpynode.ui.qt_wrapper import QTextCursor

            limit  = v._top_limit()
            cursor = v.textCursor()
            cursor.setPosition(0)
            cursor.setPosition(limit, QTextCursor.KeepAnchor)
            v.setTextCursor(cursor)
            self._key(v, self._Qt.Key_Delete)
            self.assertTrue(
                v.toPlainText().startswith("from mpynode import"))
            v.markSaved()
            v.refresh()
            self.assertTrue(
                v.toPlainText().startswith("from mpynode import"))
        finally:
            v.deleteLater()

    # -- a boundary inside build() -----------------------------------------

    def test_return_opens_a_line_above_a_managed_block(self):
        _node, v = self._view()
        try:
            at = self._line_of(v, "# --- outputs ---")
            self.assertEqual(v.toPlainText().split("\n")[at - 1], "")
            self._caret(v, at)
            self._key(v, self._Qt.Key_Return, "\n")
            at    = self._line_of(v, "# --- outputs ---")
            lines = v.toPlainText().split("\n")
            self.assertEqual([lines[at - 2], lines[at - 1]], ["", ""])
            self.assertEqual(v._spacing_from_document().get("attrs_out"), 2)
        finally:
            v.deleteLater()

    def test_backspace_closes_it_until_the_blocks_touch(self):
        _node, v = self._view()
        try:
            for _ in range(4):
                at = self._line_of(v, "# --- outputs ---")
                self._caret(v, at)
                self._key(v, self._Qt.Key_Backspace)
            at    = self._line_of(v, "# --- outputs ---")
            above = v.toPlainText().split("\n")[at - 1]
            self.assertIn("add_input_attr", above,
                          "the two blocks should be touching")
            self.assertEqual(v._spacing_from_document().get("attrs_out"), 0)
        finally:
            v.deleteLater()

    def test_backspace_stops_at_zero_and_never_eats_the_block_above(self):
        _node, v = self._view()
        try:
            for _ in range(12):        # far more than the gap ever held
                at = self._line_of(v, "# --- outputs ---")
                self._caret(v, at)
                self._key(v, self._Qt.Key_Backspace)
            text = v.toPlainText()
            self.assertIn("node.add_input_attr('inFloat', 'float')", text)
            self.assertIn("# --- inputs ---", text)
        finally:
            v.deleteLater()

    def test_a_gap_takes_a_newline_but_not_a_character(self):
        # A gap holds no text in the node's data model, so a character typed
        # there would promise a round trip that does not exist.
        _node, v = self._view()
        refused = []
        v.editRefused.connect(refused.append)
        try:
            at = self._line_of(v, "# --- outputs ---")
            self._caret(v, at - 1)
            self._key(v, self._Qt.Key_X, "x")
            self.assertTrue(refused)
            self.assertNotIn("x\n        # --- outputs ---", v.toPlainText())
        finally:
            v.deleteLater()

    # -- persistence --------------------------------------------------------

    def test_the_spacing_is_stored_on_the_node_and_survives_a_refresh(self):
        node, v = self._view()
        try:
            at = self._line_of(v, "# --- outputs ---")
            self._caret(v, at)
            self._key(v, self._Qt.Key_Return, "\n")
            self.assertTrue(v.hasUnsavedChanges())
            v.markSaved()
            self.assertEqual(node.get_api_gap_spacing(), {"attrs_out": 2})
            v.refresh()
            at    = self._line_of(v, "# --- outputs ---")
            lines = v.toPlainText().split("\n")
            self.assertEqual([lines[at - 2], lines[at - 1]], ["", ""])
            self.assertFalse(v.hasUnsavedChanges())
        finally:
            v.deleteLater()

    def test_an_untouched_node_stores_nothing(self):
        # The map is SPARSE on purpose: an empty one bakes byte-for-byte what
        # the exporter baked before any of this existed.
        node, v = self._view()
        try:
            self.assertEqual(v._spacing_from_document(), {})
            v.markSaved()
            self.assertEqual(node.get_api_gap_spacing(), {})
        finally:
            v.deleteLater()


@unittest.skipUnless(_qapp_available(), "Qt unavailable")
class TestTheMetadataBannerAndTheHeaderZone(unittest.TestCase):
    """The Node Info banner sits ABOVE the user's header zone.

    That distinction is load-bearing, and getting it wrong DESTROYED DATA. The
    zone is positional -- everything between ``_top_start`` and the first
    generated line -- and the save reads it off the document, not off a region,
    so that a header the user has only just begun still lands. When the banner
    shipped without ``_ABOVE_TOP_ZONE`` it became the first generated region,
    the limit went to 0, the zone vanished, and the save spliced an EMPTY
    header over Methods lines 1..N: every node with metadata lost its header
    the first time it was saved from this view.

    The suite did not catch it because nothing built a node with metadata AND a
    header AND then saved. These tests are that missing case.
    """

    META = {"authors": ["Ada L"], "copyright": "(c) 2026 Studio"}
    SRC  = '"""My own header."""\n\n\ndef helper():\n    return 1\n'

    def _node(self, meta, src=None, name="apiBanner"):
        from mpynode import MPyNode

        mc.file(new=True, force=True)
        n = MPyNode.create(name=name)
        if src is not None:
            n.set_methods_source(src)
        if meta is not None:
            n.set_metadata(meta)
        return n

    def _view(self, node):
        from mpynode.ui.widgets.api_view import NDApiView

        v = NDApiView(node)
        v.resize(900, 620)
        return v

    def test_a_save_does_not_eat_the_users_header(self):
        v = self._view(self._node(self.META, self.SRC))
        try:
            rebuilt = v._methods_from_document()
            self.assertIsNotNone(rebuilt)
            self.assertIn('"""My own header."""', rebuilt)
            self.assertIn("def helper():", rebuilt)
        finally:
            v.deleteLater()

    def test_the_banner_is_never_written_back_as_methods_source(self):
        # The mirror image of the same bug: a zone starting at 0 would swallow
        # the banner and save it as if the user had typed it.
        v = self._view(self._node(self.META, self.SRC))
        try:
            rebuilt = v._methods_from_document() or ""
            self.assertNotIn("Generated by Node Designer", rebuilt)
            self.assertNotIn("copyright:", rebuilt)
        finally:
            v.deleteLater()

    def test_the_zone_is_identical_with_and_without_a_banner(self):
        plain = self._view(self._node(None, self.SRC, "apiPlain"))
        try:
            expected = plain._top_text()
        finally:
            plain.deleteLater()
        v = self._view(self._node(self.META, self.SRC, "apiMeta"))
        try:
            self.assertEqual(v._top_text(), expected)
            self.assertEqual(v._top_start() > 0, True)  # past the banner
        finally:
            v.deleteLater()

    def test_return_opens_room_between_the_banner_and_the_imports(self):
        """With no header of your own there is nowhere to type -- the banner
        butts against the imports. Return at the top of the generated block has
        to open a line, exactly as it does on a node with no banner."""
        v = self._view(self._node(self.META, None, "apiRoom"))
        try:
            limit = v._top_limit()
            self.assertTrue(v._allows(limit, limit, False, True))
        finally:
            v.deleteLater()

    def test_the_banner_itself_still_refuses_every_keystroke(self):
        v = self._view(self._node(self.META, self.SRC, "apiRefuse"))
        try:
            # Position 2 is inside the first bar line of the banner.
            self.assertFalse(v._allows(2, 2, False, False))
            self.assertFalse(v._allows(2, 3, True, False))
        finally:
            v.deleteLater()

    def test_typing_in_the_opened_room_reaches_the_methods_source(self):
        from mpynode.ui.qt_wrapper import QTextCursor

        v = self._view(self._node(self.META, None, "apiType"))
        try:
            cur = QTextCursor(v.document())
            cur.setPosition(v._top_limit())
            cur.insertText("\n")
            v._after_edit()
            cur.setPosition(v._top_start())
            cur.insertText("# my own note")
            v._after_edit()
            self.assertIn("# my own note", v._methods_from_document() or "")
        finally:
            v.deleteLater()


if __name__ == "__main__":
    unittest.main()
