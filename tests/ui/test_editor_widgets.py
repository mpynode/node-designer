"""Code-editor widgets: indent/comment, find bar, autocomplete, editor stack, refactor-rename, persistent-var, rename-var UI

Consolidated from: test_editor_indent_comment.py, test_editor_find.py, test_phaseM_1_autocomplete.py, test_phase17.py, test_refactor_rename.py, test_persistent_var.py, test_rename_var_ui.py.
"""

from __future__ import annotations

# ===================== from test_editor_indent_comment.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from mpynode.ui.widgets.editor_core import (
    INDENT_UNIT,
    indent_block,
    toggle_comment,
)


class TestIndentBlock(unittest.TestCase):
    def test_indent_single_line_no_selection(self):
        text = "x = 1\n"
        out, ns, ne = indent_block(text, 0, 0, add=True)
        self.assertEqual(out, "    x = 1\n")

    def test_indent_multi_line(self):
        text = "a = 1\nb = 2\nc = 3\n"
        # select from start of line 1 to somewhere in line 2.
        out, ns, ne = indent_block(text, 0, 8, add=True)
        self.assertEqual(out, "    a = 1\n    b = 2\nc = 3\n")

    def test_indent_skips_empty_lines(self):
        text = "a = 1\n\nb = 2\n"
        out, ns, ne = indent_block(text, 0, len(text), add=True)
        # blank middle line stays blank (no trailing whitespace).
        self.assertEqual(out, "    a = 1\n\n    b = 2\n")

    def test_unindent_removes_one_level(self):
        text = "    a = 1\n    b = 2\n"
        out, ns, ne = indent_block(text, 0, len(text), add=False)
        self.assertEqual(out, "a = 1\nb = 2\n")

    def test_unindent_partial_spaces(self):
        text = "  a = 1\n"  # only 2 leading spaces
        out, ns, ne = indent_block(text, 0, 0, add=False)
        self.assertEqual(out, "a = 1\n")

    def test_unindent_tab(self):
        text = "\ta = 1\n"
        out, ns, ne = indent_block(text, 0, 0, add=False)
        self.assertEqual(out, "a = 1\n")

    def test_unindent_noop_on_flush_line(self):
        text = "a = 1\n"
        out, ns, ne = indent_block(text, 0, 0, add=False)
        self.assertEqual(out, "a = 1\n")

    def test_selection_excludes_trailing_line_at_boundary(self):
        text = "a = 1\nb = 2\nc = 3\n"
        # selection ends exactly at the start of line 3 (offset 12).
        start = 0
        end = text.index("c = 3")
        out, ns, ne = indent_block(text, start, end, add=True)
        # only lines 1 + 2 indented; line 3 untouched.
        self.assertEqual(out, "    a = 1\n    b = 2\nc = 3\n")

    def test_roundtrip_indent_then_unindent(self):
        text = "def f():\n    return 1\n"
        i1, _, _ = indent_block(text, 0, len(text), add=True)
        back, _, _ = indent_block(i1, 0, len(i1), add=False)
        self.assertEqual(back, text)

    def test_indent_unit_is_four_spaces(self):
        self.assertEqual(INDENT_UNIT, "    ")


class TestToggleComment(unittest.TestCase):
    def test_comment_single_line(self):
        text = "x = 1\n"
        out, ns, ne = toggle_comment(text, 0, 0)
        self.assertEqual(out, "# x = 1\n")

    def test_uncomment_single_line(self):
        text = "# x = 1\n"
        out, ns, ne = toggle_comment(text, 0, 0)
        self.assertEqual(out, "x = 1\n")

    def test_comment_at_min_indent(self):
        text = "    a = 1\n    b = 2\n"
        out, ns, ne = toggle_comment(text, 0, len(text))
        # "# " inserted at the common indent (col 4), not col 0.
        self.assertEqual(out, "    # a = 1\n    # b = 2\n")

    def test_comment_mixed_indent_uses_minimum(self):
        text = "    a = 1\n        b = 2\n"
        out, ns, ne = toggle_comment(text, 0, len(text))
        # "# " goes at the MINIMUM common indent (col 4); the deeper line keeps
        # its extra indentation after the token.
        self.assertEqual(out, "    # a = 1\n    #     b = 2\n")

    def test_toggle_uncomments_only_when_all_commented(self):
        text = "# a = 1\nb = 2\n"
        # not all commented -> comment everything.
        out, ns, ne = toggle_comment(text, 0, len(text))
        self.assertEqual(out, "# # a = 1\n# b = 2\n")

    def test_uncomment_all_commented_block(self):
        text = "# a = 1\n# b = 2\n"
        out, ns, ne = toggle_comment(text, 0, len(text))
        self.assertEqual(out, "a = 1\nb = 2\n")

    def test_blank_lines_skipped(self):
        text = "a = 1\n\nb = 2\n"
        out, ns, ne = toggle_comment(text, 0, len(text))
        self.assertEqual(out, "# a = 1\n\n# b = 2\n")

    def test_uncomment_without_following_space(self):
        text = "#a = 1\n"
        out, ns, ne = toggle_comment(text, 0, 0)
        self.assertEqual(out, "a = 1\n")

    def test_comment_roundtrip(self):
        text = "    if x:\n        y = 1\n"
        c1, _, _ = toggle_comment(text, 0, len(text))
        back, _, _ = toggle_comment(c1, 0, len(c1))
        self.assertEqual(back, text)


_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
    from PySide6.QtCore import Qt as _Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
        from PySide2.QtCore import Qt as _Qt
        from PySide2.QtGui import QKeyEvent
        from PySide2.QtCore import QEvent
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["indent-test"])


def _qt():
    return _QAPP is not None


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestEditorIntegration(unittest.TestCase):
    def _editor(self, text):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        ed = QtPythonEditor()
        ed.setPlainText(text)
        return ed

    def _select(self, ed, start, end):
        try:
            from PySide6.QtGui import QTextCursor
        except Exception:
            from PySide2.QtGui import QTextCursor
        c = ed.textCursor()
        c.setPosition(start)
        c.setPosition(end, QTextCursor.KeepAnchor)
        ed.setTextCursor(c)

    def test_indent_method_indents_selection(self):
        ed = self._editor("a = 1\nb = 2\n")
        self._select(ed, 0, len("a = 1\nb"))
        ed._indent_selection(add=True)
        self.assertEqual(ed.toPlainText(), "    a = 1\n    b = 2\n")

    def test_unindent_method(self):
        ed = self._editor("    a = 1\n    b = 2\n")
        self._select(ed, 0, len(ed.toPlainText()))
        ed._indent_selection(add=False)
        self.assertEqual(ed.toPlainText(), "a = 1\nb = 2\n")

    def test_comment_method_toggles(self):
        ed = self._editor("a = 1\nb = 2\n")
        self._select(ed, 0, len(ed.toPlainText()))
        ed._toggle_comment_lines()
        self.assertEqual(ed.toPlainText(), "# a = 1\n# b = 2\n")
        # toggle again -> uncomment.
        self._select(ed, 0, len(ed.toPlainText()))
        ed._toggle_comment_lines()
        self.assertEqual(ed.toPlainText(), "a = 1\nb = 2\n")

    def test_indent_is_single_undo(self):
        ed = self._editor("a = 1\nb = 2\n")
        self._select(ed, 0, len(ed.toPlainText()))
        ed._indent_selection(add=True)
        self.assertEqual(ed.toPlainText(), "    a = 1\n    b = 2\n")
        ed.undo()
        self.assertEqual(ed.toPlainText(), "a = 1\nb = 2\n")

    def test_tab_key_indents_selection(self):
        ed = self._editor("a = 1\nb = 2\n")
        self._select(ed, 0, len("a = 1\nb"))
        ev = QKeyEvent(QEvent.KeyPress, _Qt.Key_Tab, _Qt.NoModifier)
        ed.keyPressEvent(ev)
        self.assertEqual(ed.toPlainText(), "    a = 1\n    b = 2\n")

    def test_backtab_key_unindents(self):
        ed = self._editor("    a = 1\n    b = 2\n")
        self._select(ed, 0, len(ed.toPlainText()))
        ev = QKeyEvent(QEvent.KeyPress, _Qt.Key_Backtab, _Qt.ShiftModifier)
        ed.keyPressEvent(ev)
        self.assertEqual(ed.toPlainText(), "a = 1\nb = 2\n")

    def test_tab_no_selection_does_not_block_indent(self):
        """A bare Tab with no selection must NOT block-indent the line
        (it falls through to Qt\'s default insert). We assert the line
        wasn\'t prefixed with the 4-space indent unit -- the default
        insert path can\'t be exercised reliably via a synthetic event
        offscreen, but the guard (no block indent) is what matters."""
        ed = self._editor("x = 1\n")
        c = ed.textCursor()
        # Caret mid-line (col 3): at col 0 a soft-tab insert and a block-indent
        # both prepend "    " and are indistinguishable. Mid-line, only a
        # wrongly block-indented line starts with INDENT_UNIT.
        c.setPosition(3)
        ed.setTextCursor(c)
        ev = QKeyEvent(QEvent.KeyPress, _Qt.Key_Tab, _Qt.NoModifier)
        ed.keyPressEvent(ev)
        self.assertFalse(
            ed.toPlainText().startswith(INDENT_UNIT),
            "no-selection Tab should not block-indent the line",
        )


# ===================== from test_editor_find.py =====================
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
    _QAPP = _QApplication.instance() or _QApplication(["editor-find-test"])

import unittest


def _qt_available__editor_find():
    return _QAPP is not None


def _qtextcursor():
    try:
        from PySide6.QtGui import QTextCursor
    except Exception:
        from PySide2.QtGui import QTextCursor
    return QTextCursor


_SAMPLE = (
    "import numpy as np\n"
    "amplitude = 1.0\n"
    "result = amplitude * np.sin(amplitude)\n"
    "# Amplitude note\n"
)


@unittest.skipUnless(_qt_available__editor_find(), "Qt unavailable")
class TestEditorFind(unittest.TestCase):
    def _editor(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        ed = QtPythonEditor()
        ed.setPlainText(_SAMPLE)
        return ed

    def test_find_bar_lazy_then_opens(self):
        ed = self._editor()
        self.assertIsNone(ed._find_bar, "find bar should be lazy")
        ed.showFindBar()
        self.assertIsNotNone(ed._find_bar)
        self.assertFalse(ed._find_bar.isHidden(), "bar should be shown")

    def test_case_insensitive_match_count(self):
        ed = self._editor()
        total, _ = ed.find_match_stats("amplitude", case=False)
        self.assertEqual(total, 4)  # 3 lowercase + 1 "Amplitude"

    def test_case_sensitive_match_count(self):
        ed = self._editor()
        total, _ = ed.find_match_stats("amplitude", case=True)
        self.assertEqual(total, 3)  # excludes "Amplitude"

    def test_find_step_forward_selects_match(self):
        ed = self._editor()
        QTextCursor = _qtextcursor()
        cur = ed.textCursor()
        cur.movePosition(QTextCursor.Start)
        ed.setTextCursor(cur)
        self.assertTrue(ed.find_step("amplitude", backward=False, case=False))
        self.assertEqual(ed.textCursor().selectedText().lower(), "amplitude")

    def test_find_step_wraps_around(self):
        ed = self._editor()
        QTextCursor = _qtextcursor()
        cur = ed.textCursor()
        cur.movePosition(QTextCursor.End)
        ed.setTextCursor(cur)
        # 'import' only appears at the very top -> forward find from the
        # end must wrap around to find it.
        self.assertTrue(ed.find_step("import", backward=False, case=False))
        self.assertEqual(ed.textCursor().selectedText(), "import")

    def test_highlight_all_occurrences(self):
        ed = self._editor()
        from mpynode.ui.qt_wrapper import QColor

        ed.update_find_highlights("amplitude", QColor(255, 213, 79, 110), case=False)
        self.assertEqual(len(ed.extraSelections()), 4)

    def test_no_results(self):
        ed = self._editor()
        total, index = ed.find_match_stats("zzzznotfound", case=False)
        self.assertEqual(total, 0)
        self.assertEqual(index, 0)

    def test_close_clears_highlights(self):
        ed = self._editor()
        ed.showFindBar()
        from mpynode.ui.qt_wrapper import QColor

        ed.update_find_highlights("amplitude", QColor(255, 213, 79, 110), case=False)
        self.assertEqual(len(ed.extraSelections()), 4)
        ed._find_bar.close_bar()
        self.assertTrue(ed._find_bar.isHidden())
        self.assertEqual(len(ed.extraSelections()), 0)

    def test_current_index_tracks_selection(self):
        """find_match_stats reports the 1-based index of the match the
        cursor is currently sitting on."""
        ed = self._editor()
        QTextCursor = _qtextcursor()
        cur = ed.textCursor()
        cur.movePosition(QTextCursor.Start)
        ed.setTextCursor(cur)
        # Step to the first match, then the second.
        ed.find_step("amplitude", backward=False, case=False)
        _t1, i1 = ed.find_match_stats("amplitude", case=False)
        ed.find_step("amplitude", backward=False, case=False)
        _t2, i2 = ed.find_match_stats("amplitude", case=False)
        self.assertEqual(i1, 1)
        self.assertEqual(i2, 2)

    def test_all_three_editors_inherit_find(self):
        """Init / Compute / Viewport editors all expose the find API
        via the shared base class."""
        from mpynode.ui.widgets.editor_core import QtPythonEditor
        from mpynode.ui.widgets.init_editor import NDInitEditor
        from mpynode.ui.widgets.viewport_editor import NDViewportEditor
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        for cls in (NDScriptEditor, NDInitEditor, NDViewportEditor):
            self.assertTrue(issubclass(cls, QtPythonEditor))
            for method in ("showFindBar", "find_step", "find_match_stats",
                           "update_find_highlights", "clear_find_highlights"):
                self.assertTrue(
                    callable(getattr(cls, method, None)),
                    f"{cls.__name__} should inherit {method}",
                )


# ===================== from test_phaseM_1_autocomplete.py =====================
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
            _QAPP = _QApplication(["mayapy-phaseM-test"])
        except Exception:
            _QAPP = None

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__phaseM_1_autocomplete():
    standalone_init()


def _qapp_available():
    return _QAPP is not None


# ===========================================================================
# Vocabulary builder -- pure Python
# ===========================================================================


class TestVocabularyBuilder(unittest.TestCase):
    """Build_vocabulary returns a sorted list of Completion
    records pulling from walk_plug_tree + builtins + init helpers."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="ac_td")
        self.deformer.add_input_attr("amplitude", "vector")
        self.deformer.add_input_attr("driverMatrixA", "matrix")

    def test_no_node_returns_builtin_stub(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(None, scope="expression")
        texts = [c.text for c in vocab]
        self.assertIn("np", texts)
        self.assertIn("mc", texts)
        self.assertIn("self", texts)

    def test_expression_scope_includes_self_plugs(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="expression")
        texts = [c.text for c in vocab]
        self.assertIn("self.envelope", texts)
        self.assertIn("self.driverMatrixA", texts)
        self.assertIn("self.amplitude", texts)

    def test_expression_scope_includes_nested_compound_paths(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="expression")
        texts = [c.text for c in vocab]
        # input[0].inputGeometry is a deep nested plug; should be present.
        self.assertIn("self.input[0].inputGeometry", texts)

    def test_expression_scope_includes_promoted_methods(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="expression")
        texts = [c.text for c in vocab]
        # driverMatrixA reports kTypedAttribute, not kMatrixAttribute, so the
        # type-method table misses it. amplitude is a Double3 ->
        # kAttribute3Double -> asNumpy() is suggested.
        self.assertIn("self.amplitude.asNumpy()", texts)

    def test_expression_scope_includes_handle_methods_for_outputGeometry(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="expression")
        texts = [c.text for c in vocab]
        # outputGeometry array -> kMesh handle -> getPoints / setPoints.
        self.assertIn("self.outputGeometry[0].getPoints()", texts)
        self.assertIn("self.outputGeometry[0].setPoints(arr)", texts)

    def test_init_scope_excludes_plugs(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="init")
        texts = [c.text for c in vocab]
        # Init scope: no plug-tree completions.
        self.assertNotIn("self.envelope", texts)
        self.assertNotIn("self.driverMatrixA", texts)
        # But init helpers + python builtins still present.
        self.assertIn("mtm_to_numpy", texts)
        self.assertIn("np", texts)

    def test_vocabulary_sorted_and_deduped(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="expression")
        texts = [c.text for c in vocab]
        self.assertEqual(texts, sorted(texts))
        self.assertEqual(len(texts), len(set(texts)))


class TestStoredVarCompletions(unittest.TestCase):
    """If the node carries a non-empty _storedVarNames CSV, those vars
    surface as self.<name> completions."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="ac_sv_td")
        # Populate _storedVarNames directly.
        try:
            mc.setAttr(
                self.deformer.get_name() + "._storedVarNames",
                "alpha,beta,gamma_two",
                type="string",
            )
        except Exception as exc:
            self.skipTest(f"_storedVarNames plug not writable: {exc}")

    def test_storage_vars_surface(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="expression")
        texts = [c.text for c in vocab]
        for name in ("alpha", "beta", "gamma_two"):
            self.assertIn(f"self.{name}", texts,
                f"expected self.{name} from stored vars")


class TestInitBindingExtraction(unittest.TestCase):
    """Top-level defs / assignments in the Init source surface as
    completions via the cheap AST walk."""

    def setUp(self):
        ensure_plugins_loaded()
        mc.file(new=True, force=True)
        plane = mc.polyPlane(w=2.0, h=2.0, sx=2, sy=2)[0]
        from mpynode.wrappers.mpy_deformer import MPyDeformer

        self.deformer = MPyDeformer.create_on(plane, name="ac_init_td")
        self.deformer.set_init_expression(
            "import numpy as np\n"
            "def my_helper(x):\n"
            "    return x * 2\n"
            "MAX_ITER = 100\n"
            "class Buffer:\n"
            "    pass\n"
        )

    def test_init_bindings_extracted(self):
        from mpynode.ui.widgets.autocomplete import build_vocabulary

        vocab = build_vocabulary(self.deformer.get_name(), scope="expression")
        texts = [c.text for c in vocab]
        for name in ("my_helper", "MAX_ITER", "Buffer"):
            self.assertIn(name, texts,
                f"expected init binding {name!r} in vocab")


# ===========================================================================
# Editor integration (requires Qt)
# ===========================================================================


class TestEditorCompletionWiring(unittest.TestCase):
    """NDScriptEditor.refresh() must populate the inherited
    completion vocabulary. NDInitEditor.refresh() same for init
    scope."""

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

        self.deformer = MPyDeformer.create_on(plane, name="ac_ed_td")
        self.deformer.add_input_attr("driverMatrixA", "matrix")

    def test_script_editor_populates_completion_words(self):
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        editor = NDScriptEditor(self.deformer)
        words = editor.getCompletionWords()
        self.assertIn("self.envelope", words)
        self.assertIn("self.driverMatrixA", words)
        self.assertIn("np", words)

    def test_init_editor_populates_init_scope(self):
        from mpynode.ui.widgets.init_editor import NDInitEditor

        editor = NDInitEditor(self.deformer)
        words = editor.getCompletionWords()
        # Init scope: no plug completions.
        self.assertNotIn("self.envelope", words)
        # But init helpers + builtins present.
        self.assertIn("mtm_to_numpy", words)
        self.assertIn("np", words)

    def test_editor_has_completer_after_setCompletionWords(self):
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        editor = NDScriptEditor(self.deformer)
        self.assertIsNotNone(editor._completer,
            "QCompleter should be built after refresh() populates words")


class TestNewNodeHeaderModeGate(unittest.TestCase):
    """Header scoping contract.

    Headers are SEEDED into the plugs at Node-Designer *virgin create* in
    ``"headers"`` mode ONLY (via ``build_new_node_command``). The editors NEVER
    re-insert a header for a blank plug on open -- a deleted expression stays
    deleted after save + reload -- and the wrapper API ``create()`` path never
    seeds a header, so an imported / API-made node with a blank expression is
    left blank.
    """

    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()
        if not _qapp_available():
            raise unittest.SkipTest(
                "Qt unavailable in this mayapy build; widget tests skipped"
            )

    def setUp(self):
        from mpynode.ui import preferences

        mc.file(new=True, force=True)
        # This module has no prefs isolation, so restore the real pref.
        self._saved_mode = preferences.get_pref("new_node_mode", "headers")

    def tearDown(self):
        from mpynode.ui import preferences

        preferences.set_pref("new_node_mode", self._saved_mode)

    # -- helpers ------------------------------------------------------------
    def _blank_file_node(self):
        """A bare mPyFile (all five tiers) with every tier plug forced blank --
        the "user deleted the code" state. as_texture=False keeps it a plain DG
        node (no Arnold dependency); seed_defaults=False skips the presets."""
        from mpynode.wrappers.mpy_file import MPyFile

        w = MPyFile.create(name="hdrScope", as_texture=False,
                           seed_defaults=False)
        w.set_compute_expression("")
        w.set_init_expression("")
        w.set_viewport_expression("")
        w.set_osl_expression("")
        w.set_methods_source("")
        return w

    def _expression_editors_on(self, wrapper):
        from mpynode.ui.widgets.init_editor import NDInitEditor
        from mpynode.ui.widgets.script_editor import NDScriptEditor
        from mpynode.ui.widgets.viewport_editor import NDViewportEditor
        from mpynode.ui.widgets.osl_editor import NDOslEditor

        out = []
        for cls in (NDInitEditor, NDScriptEditor, NDViewportEditor, NDOslEditor):
            ed = cls(wrapper)
            ed.refresh()
            out.append((cls.__name__, ed))
        return out

    # -- display-time: a blank plug is NEVER repopulated on open ------------
    def test_editors_never_repopulate_blank_plug_headers_mode(self):
        """Even in 'headers' mode (where repopulation used to happen), opening an
        editor on a node whose plug was cleared shows a BLANK tab."""
        from mpynode.ui import preferences

        preferences.set_pref("new_node_mode", "headers")
        w = self._blank_file_node()
        for name, ed in self._expression_editors_on(w):
            self.assertEqual(
                ed.getText().strip(), "",
                f"{name}: a cleared plug must stay blank on open (no "
                f"display-time header repopulation)",
            )

    def test_compute_none_sentinel_shows_blank(self):
        """The api1 _computeSource default is the literal string 'None'. That
        sentinel still renders as an empty Compute tab (normalized), but NO
        header is added on top of it."""
        from mpynode.ui.widgets.script_editor import NDScriptEditor
        from mpynode.wrappers.mpy_locator import MPyLocator

        loc = MPyLocator.create(name="sentinelLoc")
        ed = NDScriptEditor(loc)
        ed.refresh()
        self.assertEqual(ed.getText().strip(), "")

    # -- creation: headers ARE seeded into the plugs (Designer 'headers') ---
    def _create_via_designer(self, native_type, mode):
        from mpynode._base.commands import build_new_node_command
        from mpynode._node_registry import wrap_node

        cmd = build_new_node_command(native_type, mode)
        name = cmd.doIt()
        self.assertTrue(name, "create command returned no node name")
        return wrap_node(name, native_type)

    def test_creation_headers_mode_seeds_all_expression_plugs(self):
        w = self._create_via_designer("mPyFile", "headers")
        # mPyFile is a registered STARTER type, so headers mode seeds working
        # starter code into Compute / Init / Viewport instead of a bare header.
        # The OSL tab has no starter and keeps the generic '//' header.
        for getter in ("get_compute_expression", "get_init_expression",
                       "get_viewport_expression"):
            text = (getattr(w, getter)() or "")
            self.assertTrue(
                text.lstrip().startswith("#") and text.strip(),
                f"{getter}: expected seeded '#' starter/header, got {text!r}")
        osl = (w.get_osl_expression() or "")
        self.assertTrue(
            osl.lstrip().startswith("//") and osl.strip(),
            f"get_osl_expression: expected a seeded '//' header, got {osl!r}")
        # Compute must carry the blessed-method starter, not a cross-wired
        # Init/Viewport one.
        self.assertIn("self.read_texture()", w.get_compute_expression())

    def test_creation_none_mode_leaves_plugs_blank(self):
        w = self._create_via_designer("mPyFile", "none")
        self.assertIn((w.get_compute_expression() or "").strip(), ("", "None"))
        for getter in ("get_init_expression", "get_viewport_expression",
                       "get_osl_expression"):
            self.assertEqual(
                (getattr(w, getter)() or "").strip(), "",
                f"{getter}: 'none' mode must leave the expression plug blank")
        # The Methods tier follows seed_setup, not header mode: mPyFile ships an
        # authored setup, so _methodsSource carries the BODY even in 'none'.
        methods = (w.get_methods_source() or "")
        self.assertIn("def setup", methods)
        self.assertFalse(
            methods.lstrip().startswith("#"),
            "'none' mode must not seed a Methods header")

    # -- API path: create() never seeds a header ---------------------------
    def test_api_create_never_seeds_headers(self):
        from mpynode.wrappers.mpy_file import MPyFile

        w = MPyFile.create(name="apiNoHdr", as_texture=False,
                           seed_defaults=False)
        self.assertIn((w.get_compute_expression() or "").strip(), ("", "None"))
        for getter in ("get_init_expression", "get_viewport_expression",
                       "get_osl_expression", "get_methods_source"):
            self.assertEqual(
                (getattr(w, getter)() or "").strip(), "",
                f"{getter}: API create must not seed a header")


class TestAutocompleteSourceShape(unittest.TestCase):
    """Source-grep pins: editor wires through the M.1 vocabulary
    pipeline, not an ad-hoc list."""

    def test_script_editor_uses_build_vocabulary(self):
        import inspect
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        src = inspect.getsource(NDScriptEditor.refreshCompletionVocabulary)
        self.assertIn("build_vocabulary", src)
        self.assertIn("expression", src)

    def test_init_editor_uses_build_vocabulary_init_scope(self):
        import inspect
        from mpynode.ui.widgets.init_editor import NDInitEditor

        src = inspect.getsource(NDInitEditor.refreshCompletionVocabulary)
        self.assertIn("build_vocabulary", src)
        self.assertIn("init", src)


# ===================== from test_phase17.py =====================
import unittest

from tests._setup import standalone_init


def _setUpModule__phase17():
    standalone_init()


def _qt_available__phase17() -> bool:
    try:
        from mpynode.ui.qt_wrapper import QWidget  # noqa: F401

        return True
    except ImportError:
        return False


# ===========================================================================
# QtPythonHighlighter (no widget instantiation)
# ===========================================================================


@unittest.skipUnless(_qt_available__phase17(), "Qt unavailable")
class TestHighlighterModuleShape(unittest.TestCase):
    def test_class_present(self):
        from mpynode.ui.widgets.highlighter import QtPythonHighlighter

        self.assertTrue(hasattr(QtPythonHighlighter, "highlightBlock"))
        self.assertTrue(hasattr(QtPythonHighlighter, "matchMultiline"))
        self.assertTrue(hasattr(QtPythonHighlighter, "rebuildRules"))

    def test_python3_keywords_present(self):
        from mpynode.ui.widgets.highlighter import QtPythonHighlighter

        for kw in (
            "def",
            "class",
            "if",
            "else",
            "import",
            "from",
            "return",
            "yield",
            "lambda",
            "with",
            "async",
            "await",
            "True",
            "False",
            "None",
        ):
            self.assertIn(kw, QtPythonHighlighter.KEYWORDS)

    def test_legacy_python2_keywords_dropped(self):
        """Trims the Python 2 ``print`` and ``exec`` keywords."""
        from mpynode.ui.widgets.highlighter import QtPythonHighlighter

        self.assertNotIn("print", QtPythonHighlighter.KEYWORDS)
        self.assertNotIn("exec", QtPythonHighlighter.KEYWORDS)

    def test_var_color_api_present(self):
        from mpynode.ui.widgets.highlighter import QtPythonHighlighter

        for method in (
            "setVarColorMap",
            "appendVarColor",
            "removeVarColor",
            "clearVarColors",
            "rebuildRules",
        ):
            self.assertTrue(
                hasattr(QtPythonHighlighter, method),
                f"highlighter should have {method!r}",
            )

    def test_format_text_helper(self):
        """FormatText is a classmethod that returns a QTextCharFormat \u2014
        verify via inspect since we can't instantiate without QApplication."""
        import inspect

        from mpynode.ui.widgets.highlighter import QtPythonHighlighter

        src = inspect.getsource(QtPythonHighlighter.formatText)
        self.assertIn("QColor", src)
        self.assertIn("QTextCharFormat", src)
        self.assertIn("setForeground", src)


# ===========================================================================
# QtPythonEditor (inspect-only)
# ===========================================================================


@unittest.skipUnless(_qt_available__phase17(), "Qt unavailable")
class TestEditorCoreModuleShape(unittest.TestCase):
    def test_class_present(self):
        from mpynode.ui.widgets.editor_core import QtLineNumberArea, QtPythonEditor

        for method in (
            "_initTextAttrs",
            "_apply_tab_stop",
            "_initEvents",
            "applyPrefsFont",
            "resizeEvent",
            "lineNumberAreaWidth",
            "updateLineNumberArea",
            "updateLineNumberAreaWidth",
            "lineNumberAreaPaintEvent",
            "wheelEvent",
            "highlightCurrentLine",
            "getHighlighter",
            "setFontSize",
            "getFontSize",
        ):
            self.assertTrue(
                hasattr(QtPythonEditor, method),
                f"QtPythonEditor should have {method!r}",
            )
        self.assertTrue(hasattr(QtLineNumberArea, "sizeHint"))
        self.assertTrue(hasattr(QtLineNumberArea, "paintEvent"))

    def test_uses_python_highlighter(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor
        from mpynode.ui.widgets.highlighter import QtPythonHighlighter

        self.assertIs(QtPythonEditor.HIGHLIGHTER_CLASS, QtPythonHighlighter)

    def test_default_constants(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor

        self.assertEqual(QtPythonEditor.TAB_STOP, 4)
        self.assertGreaterEqual(QtPythonEditor.DEFAULT_FONT_SIZE, 6)
        self.assertGreaterEqual(QtPythonEditor.MAX_FONT_SIZE, 24)
        self.assertLessEqual(QtPythonEditor.MIN_FONT_SIZE, 10)

    def test_wheel_event_overridden(self):
        """Fix: Ctrl+wheel zoom is via wheelEvent override
        (NOT the broken eventFilter approach from earlier revisions)."""
        import inspect

        from mpynode.ui.widgets.editor_core import QtPythonEditor

        src = inspect.getsource(QtPythonEditor.wheelEvent)
        self.assertIn("ControlModifier", src)
        self.assertIn("setFontSize", src)

    def test_prefs_fallback_is_graceful(self):
        """If mpynode.ui.preferences doesn't exist (pre-Phase-22), the
        editor should fall back to the default font without raising."""
        import inspect

        from mpynode.ui.widgets.editor_core import QtPythonEditor

        src = inspect.getsource(QtPythonEditor._initTextAttrs)
        self.assertIn("from mpynode.ui.preferences import editor_font", src)
        self.assertIn("except Exception", src)


# ===========================================================================
# NDScriptEditor (the user-facing editor used by NDScriptTabWidget)
# ===========================================================================


@unittest.skipUnless(_qt_available__phase17(), "Qt unavailable")
class TestNDScriptEditorShape(unittest.TestCase):
    def test_class_present(self):
        from mpynode.ui.widgets.editor_core import QtPythonEditor
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        # NDScriptEditor extends QtPythonEditor for line numbers + highlighting.
        self.assertTrue(issubclass(NDScriptEditor, QtPythonEditor))

    def test_public_api_matches_placeholder(self):
        """NDScriptEditor must expose the SAME public API as
        NDScriptEditorPlaceholder so NDScriptTabWidget doesn't change."""
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        for method in (
            "getMPyNode",
            "getText",
            "setText",
            "hasUnsavedChanges",
            "markSaved",
            "refresh",
        ):
            self.assertTrue(
                hasattr(NDScriptEditor, method),
                f"NDScriptEditor should have {method!r} (matches placeholder API)",
            )
        # Same dirtyStateChanged signal.
        self.assertTrue(hasattr(NDScriptEditor, "dirtyStateChanged"))


@unittest.skipUnless(_qt_available__phase17(), "Qt unavailable")
class TestScriptTabUsesRealEditor(unittest.TestCase):
    def test_addNewTab_uses_NDScriptEditor(self):
        """→ NDScriptTabWidget._addNewTab must
        instantiate the real editor (not placeholder).

        wrapped NDScriptEditor in NDScriptTabContent so the
        per-node tab can also host a sister JIT-source editor. The
        underlying expression editor is still NDScriptEditor —
        inspect NDScriptTabContent.__init__ to confirm."""
        import inspect

        from mpynode.ui.widgets.script_tab import NDScriptTabWidget
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        # tab content wraps the editors.
        tab_src = inspect.getsource(NDScriptTabWidget._addNewTab)
        self.assertIn("NDScriptTabContent(", tab_src)
        self.assertNotIn("NDScriptEditorPlaceholder(", tab_src)

        # And NDScriptTabContent itself instantiates NDScriptEditor.
        content_src = inspect.getsource(NDScriptTabContent.__init__)
        self.assertIn("NDScriptEditor(", content_src)

    def test_imports_NDScriptEditor(self):
        """NDScriptEditor is now imported via
        NDScriptTabContent rather than directly by NDScriptTabWidget,
        but the import chain still exists."""
        import inspect

        from mpynode.ui.widgets import script_tab_content as stc_module

        src = inspect.getsource(stc_module)
        self.assertIn(
            "from mpynode.ui.widgets.script_editor import NDScriptEditor",
            src,
        )


# ===========================================================================
# qt_wrapper additions
# ===========================================================================


@unittest.skipUnless(_qt_available__phase17(), "Qt unavailable")
class TestQtWrapperPhase17(unittest.TestCase):
    def test_added_imports(self):
        from mpynode.ui import qt_wrapper

        for name in (
            "QFont",
            "QFontMetrics",
            "QSyntaxHighlighter",
            "QTextCharFormat",
            "QTextFormat",
            "QRegularExpression",
        ):
            self.assertTrue(
                hasattr(qt_wrapper, name),
                f"qt_wrapper should expose {name!r} for editor",
            )


# ===================== from test_refactor_rename.py =====================
import unittest

from mpynode._common.util import refactor as rf


def _col_of(source, lineno, token):
    """0-based char column of the first ``token`` on 1-based ``lineno``."""
    line = source.splitlines()[lineno - 1]
    return line.index(token)


class TestWordAt(unittest.TestCase):
    def test_word_at_basic(self):
        src = "amplitude = 1.0\n"
        self.assertEqual(rf.word_at(src, 1, 3), "amplitude")

    def test_word_at_empty_on_operator(self):
        src = "a = b + c\n"
        # column on the '+' (index 6) -> no identifier
        self.assertEqual(rf.word_at(src, 1, 6), "")

    def test_word_at_out_of_range(self):
        self.assertEqual(rf.word_at("x = 1\n", 9, 0), "")


class TestIdentifier(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(rf.is_valid_identifier("amp2"))
        self.assertTrue(rf.is_valid_identifier("_x"))

    def test_invalid(self):
        self.assertFalse(rf.is_valid_identifier("2amp"))
        self.assertFalse(rf.is_valid_identifier("for"))   # keyword
        self.assertFalse(rf.is_valid_identifier("a b"))
        self.assertFalse(rf.is_valid_identifier(""))


class TestModuleScopeRename(unittest.TestCase):
    def test_simple_rename_all_occurrences(self):
        src = (
            "amplitude = 1.0\n"
            "result = amplitude * 2\n"
            "final = amplitude + result\n"
        )
        col = _col_of(src, 1, "amplitude")
        plan = rf.plan_rename_at(src, 1, col, "amp")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 3)
        self.assertIn("amp = 1.0", plan.new_source)
        self.assertIn("amp * 2", plan.new_source)
        self.assertIn("amp + result", plan.new_source)
        self.assertNotIn("amplitude", plan.new_source)
        self.assertTrue(plan.is_module_level)
        self.assertEqual(plan.scope_kind, "module")

    def test_rename_from_a_usage_site(self):
        """Cursor on a USE (not the def) still renames the binding."""
        src = "amplitude = 1.0\nresult = amplitude * 2\n"
        col = _col_of(src, 2, "amplitude")
        plan = rf.plan_rename_at(src, 2, col, "amp")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)

    def test_does_not_touch_substrings(self):
        src = "amp = 1\namplitude = 2\nx = amp + amplitude\n"
        col = _col_of(src, 1, "amp")
        plan = rf.plan_rename_at(src, 1, col, "gain")
        self.assertTrue(plan.ok, plan.reason)
        # only the 'amp' binding (2 occurrences), NOT 'amplitude'.
        self.assertEqual(plan.count, 2)
        self.assertIn("amplitude = 2", plan.new_source)
        self.assertIn("gain + amplitude", plan.new_source)


class TestScopeIsolation(unittest.TestCase):
    def test_function_local_not_module(self):
        src = (
            "x = 1\n"
            "def f():\n"
            "    x = 2\n"
            "    return x\n"
            "y = x\n"
        )
        # Rename the FUNCTION-LOCAL x (line 3) -> only lines 3 + 4.
        col = _col_of(src, 3, "x")
        plan = rf.plan_rename_at(src, 3, col, "z")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)
        self.assertEqual(plan.scope_kind, "function")
        self.assertFalse(plan.is_module_level)
        # Module-level x (lines 1, 5) untouched.
        self.assertIn("x = 1", plan.new_source)
        self.assertIn("y = x", plan.new_source)

    def test_module_var_not_function_local(self):
        src = (
            "x = 1\n"
            "def f():\n"
            "    x = 2\n"
            "    return x\n"
            "y = x\n"
        )
        # Rename the MODULE x (line 1) -> only lines 1 + 5.
        col = _col_of(src, 1, "x")
        plan = rf.plan_rename_at(src, 1, col, "z")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)
        self.assertIn("z = 1", plan.new_source)
        self.assertIn("y = z", plan.new_source)
        # function-local x kept.
        self.assertIn("    x = 2", plan.new_source)

    def test_function_param_rename(self):
        src = (
            "def f(amp, b):\n"
            "    return amp * b\n"
        )
        col = _col_of(src, 1, "amp")
        plan = rf.plan_rename_at(src, 1, col, "gain")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)  # param + use
        self.assertIn("def f(gain, b):", plan.new_source)
        self.assertIn("return gain * b", plan.new_source)

    def test_comprehension_target_isolated(self):
        src = (
            "items = [1, 2, 3]\n"
            "out = [x * 2 for x in items]\n"
            "x = 99\n"
        )
        # Rename comprehension target x (line 2) -> only within the comp.
        col = _col_of(src, 2, "x")
        plan = rf.plan_rename_at(src, 2, col, "v")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)  # 'x * 2' + 'for x'
        self.assertEqual(plan.scope_kind, "comprehension")
        self.assertIn("[v * 2 for v in items]", plan.new_source)
        self.assertIn("x = 99", plan.new_source)  # module x untouched


class TestRefusals(unittest.TestCase):
    def test_collision_refused(self):
        src = "a = 1\nb = 2\nc = a + b\n"
        col = _col_of(src, 1, "a")
        plan = rf.plan_rename_at(src, 1, col, "b")
        self.assertFalse(plan.ok)
        self.assertIn("already exists", plan.reason)
        self.assertIsNone(plan.new_source)

    def test_invalid_new_name_refused(self):
        src = "a = 1\n"
        col = _col_of(src, 1, "a")
        plan = rf.plan_rename_at(src, 1, col, "2bad")
        self.assertFalse(plan.ok)
        self.assertIn("not a valid", plan.reason)

    def test_keyword_new_name_refused(self):
        src = "a = 1\n"
        col = _col_of(src, 1, "a")
        plan = rf.plan_rename_at(src, 1, col, "class")
        self.assertFalse(plan.ok)

    def test_blocked_name_refused(self):
        src = "x = np.sin(1.0)\n"
        col = _col_of(src, 1, "np")
        plan = rf.plan_rename_at(src, 1, col, "numpy", blocked_names={"np"})
        self.assertFalse(plan.ok)
        self.assertIn("framework", plan.reason)

    def test_syntax_error_refused(self):
        src = "a = = 1\n"
        plan = rf.plan_rename_at(src, 1, 0, "b")
        self.assertFalse(plan.ok)
        self.assertIn("syntax error", plan.reason)

    def test_cursor_on_attribute_refused(self):
        """self.amplitude -- the 'amplitude' attribute is NOT a local
        variable, so the local renamer declines it."""
        src = "self.amplitude = 1.0\n"
        col = _col_of(src, 1, "amplitude")
        plan = rf.plan_rename_at(src, 1, col, "amp")
        self.assertFalse(plan.ok)

    def test_global_decl_refused(self):
        src = (
            "g = 0\n"
            "def f():\n"
            "    global g\n"
            "    g = 1\n"
        )
        col = _col_of(src, 1, "g")
        plan = rf.plan_rename_at(src, 1, col, "h")
        self.assertFalse(plan.ok)
        self.assertIn("global/nonlocal", plan.reason)


class TestDynamicWarnings(unittest.TestCase):
    def test_getattr_string_ref_warned(self):
        src = (
            "amplitude = 1.0\n"
            "v = getattr(self, 'amplitude')\n"
        )
        col = _col_of(src, 1, "amplitude")
        plan = rf.plan_rename_at(src, 1, col, "amp")
        self.assertTrue(plan.ok, plan.reason)
        # The code binding renamed; the string ref flagged, not touched.
        self.assertTrue(any("getattr" in w for w in plan.warnings))
        self.assertIn("'amplitude'", plan.new_source)  # string literal kept

    def test_eval_warned(self):
        src = "amplitude = 1.0\nv = eval('amplitude + 1')\n"
        col = _col_of(src, 1, "amplitude")
        plan = rf.plan_rename_at(src, 1, col, "amp")
        self.assertTrue(plan.ok, plan.reason)
        self.assertTrue(any("eval" in w for w in plan.warnings))


class TestFreeNamePath(unittest.TestCase):
    """Cross-tab propagation: rename only module-scope (free) refs."""

    def test_free_rename_in_sibling(self):
        # Sibling Compute tab that READS an Init-defined 'amplitude'.
        src = "result = amplitude * np.sin(amplitude)\n"
        plan = rf.plan_rename_free_name(src, "amplitude", "amp")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)
        self.assertIn("amp * np.sin(amp)", plan.new_source)

    def test_free_rename_skips_local_shadow(self):
        # Sibling where 'amplitude' is shadowed by a function local.
        src = (
            "result = amplitude + 1\n"
            "def helper(amplitude):\n"
            "    return amplitude * 2\n"
        )
        plan = rf.plan_rename_free_name(src, "amplitude", "amp")
        self.assertTrue(plan.ok, plan.reason)
        # Only the module-scope free ref on line 1.
        self.assertEqual(plan.count, 1)
        self.assertIn("amp + 1", plan.new_source)
        self.assertIn("def helper(amplitude):", plan.new_source)
        self.assertIn("return amplitude * 2", plan.new_source)

    def test_free_rename_no_occurrences(self):
        src = "result = something_else\n"
        plan = rf.plan_rename_free_name(src, "amplitude", "amp")
        self.assertFalse(plan.ok)


class TestRewriteIntegrity(unittest.TestCase):
    def test_result_always_parses(self):
        import ast as _ast

        src = (
            "import numpy as np\n"
            "amplitude = 1.0\n"
            "data = [amplitude * i for i in range(3)]\n"
            "def scale(amplitude, k):\n"
            "    return amplitude * k\n"
            "out = scale(amplitude, 2) + sum(data)\n"
        )
        col = _col_of(src, 2, "amplitude")
        plan = rf.plan_rename_at(src, 2, col, "gain")
        self.assertTrue(plan.ok, plan.reason)
        _ast.parse(plan.new_source)  # must not raise
        # module amplitude: lines 2, 3 (elt, NOT the comp target i) and 6. The
        # function param on lines 4-5 is a different binding, untouched.
        self.assertIn("def scale(amplitude, k):", plan.new_source)
        self.assertIn("return amplitude * k", plan.new_source)
        self.assertIn("gain = 1.0", plan.new_source)
        self.assertIn("scale(gain, 2)", plan.new_source)



class TestClassifyAt(unittest.TestCase):
    def test_self_attr(self):
        src = "self.amplitude = 1.0\n"
        col = _col_of(src, 1, "amplitude")
        kind, name = rf.classify_at(src, 1, col)
        self.assertEqual((kind, name), ("self_attr", "amplitude"))

    def test_plain_name(self):
        src = "amplitude = 1.0\n"
        col = _col_of(src, 1, "amplitude")
        kind, name = rf.classify_at(src, 1, col)
        self.assertEqual((kind, name), ("name", "amplitude"))

    def test_non_self_attribute_is_other(self):
        src = "obj.amplitude = 1.0\n"
        col = _col_of(src, 1, "amplitude")
        kind, name = rf.classify_at(src, 1, col)
        self.assertEqual(kind, "other")

    def test_none_on_operator(self):
        src = "a = b + c\n"
        kind, name = rf.classify_at(src, 1, 6)
        self.assertEqual(kind, "none")

    def test_myself_not_confused_with_self(self):
        """A name like 'myself.x' must NOT be classed as self.x."""
        src = "myself = obj\nv = myself.amplitude\n"
        col = _col_of(src, 2, "amplitude")
        kind, name = rf.classify_at(src, 2, col)
        self.assertEqual(kind, "other")  # attribute of myself, not self

    def test_a_decorator_is_not_a_local(self):
        """``@maya_command(...)`` parses to Call(func=Name('maya_command')),
        so it used to classify as a plain local -- which put "Rename" and
        "Promote to Persistent Variable" on a framework decorator's menu."""
        src = ("@maya_command(name='doThing')\n"
               "def do_thing(self, count=1):\n"
               "    total = count + 1\n"
               "    return total\n")
        col = _col_of(src, 1, "maya_command")
        self.assertEqual(rf.classify_at(src, 1, col),
                         ("other", "maya_command"))

    def test_a_bare_decorator_is_not_a_local_either(self):
        src = "@maya_test\ndef test_it(self):\n    return True\n"
        col = _col_of(src, 1, "maya_test")
        self.assertEqual(rf.classify_at(src, 1, col), ("other", "maya_test"))

    def test_a_local_inside_the_decorated_body_still_classifies(self):
        # The guard must not swallow the whole decorated statement.
        src = ("@maya_command(name='doThing')\n"
               "def do_thing(self, count=1):\n"
               "    total = count + 1\n"
               "    return total\n")
        col = _col_of(src, 3, "total")
        self.assertEqual(rf.classify_at(src, 3, col), ("name", "total"))

    def test_a_class_decorator_is_covered_too(self):
        src = "@registered\nclass Thing(object):\n    pass\n"
        col = _col_of(src, 1, "registered")
        self.assertEqual(rf.classify_at(src, 1, col), ("other", "registered"))


class TestPlanRenameSelfAttr(unittest.TestCase):
    def test_rewrites_all_self_accesses(self):
        src = (
            "self.amplitude = 1.0\n"
            "v = self.amplitude * 2\n"
            "w = self.other + self.amplitude\n"
        )
        plan = rf.plan_rename_self_attr(src, "amplitude", "amp")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 3)
        self.assertIn("self.amp = 1.0", plan.new_source)
        self.assertIn("self.amp * 2", plan.new_source)
        self.assertIn("self.other + self.amp", plan.new_source)

    def test_leaves_non_self_attr_alone(self):
        src = "x = obj.amplitude + self.amplitude\n"
        plan = rf.plan_rename_self_attr(src, "amplitude", "amp")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 1)
        self.assertIn("obj.amplitude", plan.new_source)
        self.assertIn("self.amp", plan.new_source)

    def test_zero_in_sibling_without_attr(self):
        src = "x = 1 + 2\n"
        plan = rf.plan_rename_self_attr(src, "amplitude", "amp")
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 0)
        self.assertEqual(plan.new_source, src)

    def test_invalid_new_attr_refused(self):
        src = "self.amplitude = 1.0\n"
        plan = rf.plan_rename_self_attr(src, "amplitude", "2bad")
        self.assertFalse(plan.ok)


# ===================== from test_persistent_var.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from mpynode._common.util import refactor as rf


def _col(source, lineno, token):
    return source.splitlines()[lineno - 1].index(token)


class TestPromoteEngine(unittest.TestCase):
    def test_promote_simple_local(self):
        src = "var2 = [5, 6, 7, 8]\nx = var2[0]\n"
        plan = rf.plan_promote_local(src, 1, _col(src, 1, "var2"))
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)
        self.assertIn("self.var2 = [5, 6, 7, 8]", plan.new_source)
        self.assertIn("x = self.var2[0]", plan.new_source)

    def test_promote_from_usage_site(self):
        src = "amp = 1.0\ny = amp * 2\n"
        plan = rf.plan_promote_local(src, 2, _col(src, 2, "amp"))
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)
        self.assertIn("self.amp = 1.0", plan.new_source)
        self.assertIn("y = self.amp * 2", plan.new_source)

    def test_promote_refuses_function_local(self):
        src = "def f():\n    inner = 1\n    return inner\n"
        plan = rf.plan_promote_local(src, 2, _col(src, 2, "inner"))
        self.assertFalse(plan.ok)
        self.assertIn("top-level", plan.reason)

    def test_promote_refuses_blocked_name(self):
        src = "amplitude = 1.0\n"
        plan = rf.plan_promote_local(
            src, 1, _col(src, 1, "amplitude"),
            blocked_names={"amplitude"},
        )
        self.assertFalse(plan.ok)

    def test_promote_only_touches_target_binding(self):
        src = "a = 1\nb = 2\nc = a + b\n"
        plan = rf.plan_promote_local(src, 1, _col(src, 1, "a"))
        self.assertTrue(plan.ok, plan.reason)
        self.assertEqual(plan.count, 2)  # 'a =' + 'a + b'
        self.assertIn("self.a = 1", plan.new_source)
        self.assertIn("b = 2", plan.new_source)
        self.assertIn("c = self.a + b", plan.new_source)

    def test_promote_result_parses(self):
        import ast as _ast

        src = "vals = [i * 2 for i in range(3)]\ntotal = sum(vals)\n"
        plan = rf.plan_promote_local(src, 1, _col(src, 1, "vals"))
        self.assertTrue(plan.ok, plan.reason)
        _ast.parse(plan.new_source)
        # comp target `i` untouched; module local `vals` -> self.vals.
        self.assertIn("self.vals = [i * 2 for i in range(3)]", plan.new_source)
        self.assertIn("total = sum(self.vals)", plan.new_source)

    def test_promote_no_identifier(self):
        src = "a = 1 + 2\n"
        plan = rf.plan_promote_local(src, 1, 6)  # on '+'
        self.assertFalse(plan.ok)


_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["persist-var-test"])

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__persistent_var():
    standalone_init()


def _qt():
    return _QAPP is not None


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestPersistUIFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="persist_ui_test")
        self.node.add_input_attr("amplitude", "float")
        self.node.add_output_attr("outVal", "float")

    def _editor(self, text):
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        ed = NDScriptEditor(self.node)
        ed.setPlainText(text)
        return ed

    def _stored(self):
        from mpynode._common.storedvars.stored_vars_api import get_variables

        return get_variables(self.node.get_name())

    # -- classify -------------------------------------------------------

    def test_classify_make_for_fresh_self_attr(self):
        from mpynode.ui.widgets.rename_var import classify_persistable

        ed = self._editor("self.foo = 5\n")
        col = ed.toPlainText().index("foo")
        self.assertEqual(classify_persistable(ed, 1, col), ("make", "foo"))

    def test_classify_no_make_for_plug(self):
        from mpynode.ui.widgets.rename_var import classify_persistable

        ed = self._editor("self.amplitude = 5\n")
        col = ed.toPlainText().index("amplitude")
        self.assertEqual(classify_persistable(ed, 1, col), (None, ""))

    def test_classify_promote_for_local(self):
        from mpynode.ui.widgets.rename_var import classify_persistable

        ed = self._editor("var2 = [1, 2, 3]\n")
        col = ed.toPlainText().index("var2")
        self.assertEqual(classify_persistable(ed, 1, col), ("promote", "var2"))

    def test_classify_no_promote_collides_with_plug(self):
        from mpynode.ui.widgets.rename_var import classify_persistable

        ed = self._editor("amplitude = 9.0\n")  # collides with the plug
        col = ed.toPlainText().index("amplitude")
        self.assertEqual(classify_persistable(ed, 1, col), (None, ""))

    # -- actions --------------------------------------------------------

    def test_make_persistent_registers_seeded_none(self):
        from mpynode.ui.widgets.rename_var import make_persistent_variable

        ed = self._editor("self.foo = 5\n")
        make_persistent_variable(ed, "foo")
        stored = self._stored()
        self.assertIn("foo", stored)
        self.assertIsNone(stored["foo"])  # seeded None

    def test_promote_rewrites_editor_and_registers(self):
        from mpynode.ui.widgets.rename_var import promote_to_persistent_variable

        ed = self._editor("var2 = [5, 6, 7, 8]\nself.outVal = var2[0]\n")
        col = ed.toPlainText().index("var2")
        promote_to_persistent_variable(ed, 1, col)
        # Editor rewritten.
        self.assertIn("self.var2 = [5, 6, 7, 8]", ed.toPlainText())
        self.assertIn("self.outVal = self.var2[0]", ed.toPlainText())
        # Registered (seeded None) in storage.
        self.assertIn("var2", self._stored())

    def test_make_persistent_then_eval_populates(self):
        """After making self.foo persistent, evaluating the node writes
        the real value to storage (auto-persist)."""
        from mpynode.ui.widgets.rename_var import make_persistent_variable

        ed = self._editor("self.foo = 7.0\nself.outVal = self.foo\n")
        # Persist the expression to the node first.
        self.node.set_compute_expression(ed.toPlainText())
        make_persistent_variable(ed, "foo")
        self.assertIsNone(self._stored().get("foo"))  # seeded None
        # Evaluate -> compute writes foo = 7.0 to storage.
        mc.getAttr(self.node.get_name() + ".outVal")
        self.assertAlmostEqual(self._stored().get("foo"), 7.0, places=4)


# ===================== from test_rename_var_ui.py =====================
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
    _QAPP = _QApplication.instance() or _QApplication(["rename-ui-test"])

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def _setUpModule__rename_var_ui():
    standalone_init()


def _qt():
    return _QAPP is not None


@unittest.skipUnless(_qt(), "Qt unavailable")
class TestRenameVarPlumbing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_plugins_loaded()

    def setUp(self):
        mc.file(new=True, force=True)
        from mpynode.wrappers._mpy_node import MPyNode

        self.node = MPyNode.create(name="rename_ui_test")
        self.node.add_input_attr("amplitude", "float")
        self.node.add_output_attr("outVal", "float")

    def _editor(self, text):
        from mpynode.ui.widgets.script_editor import NDScriptEditor

        ed = NDScriptEditor(self.node)
        ed.setPlainText(text)
        return ed

    # -- local variable rename -----------------------------------------

    def test_local_rename_applies(self):
        from mpynode.ui.widgets import rename_var

        ed = self._editor(
            "gain = 2.0\n"
            "self.outVal = self.amplitude * gain\n"
        )
        # 'gain' is at line 1, col 0.
        captured = {}

        def fake_dialog(parent, old, header, plan_fn):
            ok, summary, warnings, apply_fn = plan_fn("scale")
            captured["ok"] = ok
            captured["apply"] = apply_fn

            class _Stub:
                def show(self_): pass
                def raise_(self_): pass
            return _Stub()

        orig = rename_var.NDRenameVariableDialog
        rename_var.NDRenameVariableDialog = fake_dialog
        try:
            rename_var.run_rename(ed, 1, 0)
        finally:
            rename_var.NDRenameVariableDialog = orig

        self.assertTrue(captured.get("ok"))
        captured["apply"]()
        self.assertIn("scale = 2.0", ed.toPlainText())
        self.assertIn("self.amplitude * scale", ed.toPlainText())
        self.assertNotIn("gain", ed.toPlainText())

    def test_blocked_framework_name_refused(self):
        from mpynode.ui.widgets import rename_var

        ed = self._editor("import numpy as np\nself.outVal = np.pi\n")
        # 'np' on line 1.
        col = "import numpy as ".__len__()
        results = {}

        def fake_dialog(parent, old, header, plan_fn):
            results["plan"] = plan_fn("npy")

            class _Stub:
                def show(self_): pass
                def raise_(self_): pass
            return _Stub()

        orig = rename_var.NDRenameVariableDialog
        rename_var.NDRenameVariableDialog = fake_dialog
        try:
            # 'np' is module-scope but framework-blocklisted -> refused.
            usage_col = "self.outVal = ".__len__()
            rename_var.run_rename(ed, 2, usage_col)
        finally:
            rename_var.NDRenameVariableDialog = orig

        ok = results["plan"][0]
        self.assertFalse(ok)
        self.assertIn("framework", results["plan"][1])

    # -- self.<attr> rename --------------------------------------------

    def test_self_input_attr_rename_applies(self):
        from mpynode.ui.widgets import rename_var

        ed = self._editor("self.outVal = self.amplitude * 2.0\n")
        captured = {}

        def fake_dialog(parent, old, header, plan_fn):
            ok, summary, warnings, apply_fn = plan_fn("amp")
            captured["ok"] = ok
            captured["summary"] = summary
            captured["apply"] = apply_fn

            class _Stub:
                def show(self_): pass
                def raise_(self_): pass
            return _Stub()

        orig = rename_var.NDRenameVariableDialog
        rename_var.NDRenameVariableDialog = fake_dialog
        try:
            # click on 'amplitude' (the attr token) in self.amplitude.
            col = ed.toPlainText().index("amplitude")
            rename_var.run_rename(ed, 1, col)
        finally:
            rename_var.NDRenameVariableDialog = orig

        self.assertTrue(captured.get("ok"), captured.get("summary"))
        captured["apply"]()
        # DG attribute renamed.
        self.assertTrue(mc.attributeQuery("amp", node=self.node.get_name(),
                                          exists=True))
        self.assertFalse(mc.attributeQuery("amplitude", node=self.node.get_name(),
                                            exists=True))
        # Text reference rewritten.
        self.assertIn("self.amp * 2.0", ed.toPlainText())

    def test_self_attr_collision_refused(self):
        from mpynode.ui.widgets import rename_var

        ed = self._editor("self.outVal = self.amplitude\n")
        results = {}

        def fake_dialog(parent, old, header, plan_fn):
            # Try to rename amplitude -> outVal (already an output attr).
            results["plan"] = plan_fn("outVal")

            class _Stub:
                def show(self_): pass
                def raise_(self_): pass
            return _Stub()

        orig = rename_var.NDRenameVariableDialog
        rename_var.NDRenameVariableDialog = fake_dialog
        try:
            col = ed.toPlainText().index("amplitude")
            rename_var.run_rename(ed, 1, col)
        finally:
            rename_var.NDRenameVariableDialog = orig

        self.assertFalse(results["plan"][0])
        self.assertIn("already exists", results["plan"][1])

    def test_non_renameable_token_is_silent(self):
        from mpynode.ui.widgets import rename_var

        ed = self._editor("x = 1 + 2\n")
        # Column on '+' -> classify returns 'none' -> no dialog, no raise.
        rename_var.run_rename(ed, 1, 6)  # should not raise


def setUpModule():
    _setUpModule__phaseM_1_autocomplete()
    _setUpModule__phase17()
    _setUpModule__persistent_var()
    _setUpModule__rename_var_ui()


if __name__ == "__main__":
    import unittest
    unittest.main()
