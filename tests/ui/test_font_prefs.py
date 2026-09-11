"""The UI font: the resolver, the wiring helper, and the transcript.

Two fonts: ``editor`` (its own family + size, untouched here) and ``ui`` --
one family + size for every non-editor surface, which the historical areas
``panel`` and ``assistant`` alias. The interesting cases are not "does setFont
work" but the three places a naive implementation silently does nothing:

  * a per-item font (Variables/Watch value columns) overrides the view font, so
    it needs the size applied too;
  * inline HTML ``font-size`` in the assistant transcript becomes a char format
    that outranks both ``setFont`` and ``document().setDefaultFont()``;
  * text already inserted keeps its char formats, so a live change has to touch
    the existing document, not just the next message.
"""

from __future__ import annotations

import types
import unittest

from tests._setup import standalone_init

# A QApplication at IMPORT time, as the other UI modules do: constructing a
# QWidget under mayapy without one segfaults.
_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApp
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApp
    except Exception:
        _QApp = None
if _QApp is not None:
    _QAPP = _QApp.instance() or _QApp(["nd-font-test"])


def setUpModule():
    standalone_init()


class TestResolveFontSize(unittest.TestCase):
    """The clamp and the fallbacks live in one place so every widget in an
    area agrees on the number (same rationale as resolve_optimize_max_tokens)."""

    def setUp(self):
        from mpynode.ui import preferences

        self.P = preferences
        preferences._reset_for_tests()
        self.addCleanup(preferences._reset_for_tests)

    def test_every_area_has_a_key(self):
        self.assertEqual(sorted(self.P.FONT_AREA_KEYS),
                         ["assistant", "editor", "panel", "ui"])
        for key in self.P.FONT_AREA_KEYS.values():
            self.assertIn(key, self.P.DEFAULT_PREFS, key)
        # panel and assistant are the two halves of the ONE UI font.
        self.assertEqual(self.P.FONT_AREA_KEYS["panel"], "ui_font_size")
        self.assertEqual(self.P.FONT_AREA_KEYS["assistant"], "ui_font_size")

    def test_bounds_are_accepted(self):
        for size in (self.P.FONT_SIZE_MIN, 14, self.P.UI_FONT_SIZE_MAX):
            self.P.set_pref("ui_font_size", size)
            self.assertEqual(self.P.resolve_font_size("panel"), size)
        # The editor keeps the wide range.
        self.P.set_pref("editor_font_size", self.P.FONT_SIZE_MAX)
        self.assertEqual(self.P.resolve_font_size("editor"), self.P.FONT_SIZE_MAX)

    def test_out_of_range_falls_back_to_the_default(self):
        default = self.P.DEFAULT_PREFS["ui_font_size"]
        for size in (0, self.P.FONT_SIZE_MIN - 1, self.P.UI_FONT_SIZE_MAX + 1,
                     self.P.FONT_SIZE_MAX, 9999):
            self.P.set_pref("ui_font_size", size)
            self.assertEqual(self.P.resolve_font_size("panel"), default, size)

    def test_garbage_falls_back_rather_than_raising(self):
        # This runs during widget construction; an exception would take the
        # whole panel down.
        default = self.P.DEFAULT_PREFS["ui_font_size"]
        for junk in ("not a number", None, [], {}):
            self.P.set_pref("ui_font_size", junk)
            self.assertEqual(self.P.resolve_font_size("panel"), default, junk)

    def test_a_numeric_string_is_accepted(self):
        # The dialog stores an int, but a hand-edited preferences.json is a
        # supported way in.
        self.P.set_pref("ui_font_size", "18")
        self.assertEqual(self.P.resolve_font_size("panel"), 18)

    def test_unknown_area_raises(self):
        with self.assertRaises(KeyError):
            self.P.resolve_font_size("sidebar")

    def test_the_editor_is_independent_and_the_ui_is_one(self):
        self.P.set_pref("editor_font_size", 20)
        self.P.set_pref("ui_font_size", 8)
        self.assertEqual(
            [self.P.resolve_font_size(a) for a in ("editor", "ui", "assistant", "panel")],
            [20, 8, 8, 8])

    def test_the_retired_per_area_sizes_change_nothing(self):
        # A preferences.json from before the merge still carries these. They
        # are exactly the values that ran away (15 / 20 while icons stayed
        # 16 px), so they must not be read.
        default = self.P.DEFAULT_PREFS["ui_font_size"]
        # set_pref persists to the test home's file and _reset_for_tests
        # re-reads it, so pin the UI size before planting the stale keys.
        self.P.set_pref("ui_font_size",        default)
        self.P.set_pref("panel_font_size",     15)
        self.P.set_pref("assistant_font_size", 20)
        self.assertEqual(self.P.resolve_font_size("panel"), default)
        self.assertEqual(self.P.resolve_font_size("assistant"), default)

    def test_the_family_is_maya_unless_installed(self):
        from mpynode.ui.qt_wrapper import QFont

        self.P.set_pref("ui_font_family", "")
        self.assertEqual(self.P.resolve_ui_font_family(), "")
        self.assertEqual(self.P.area_font("panel").family(), QFont().family())
        self.P.set_pref("ui_font_family", "No Such Family 1234")
        installed = self.P.installed_font_families()
        if not installed:
            # No font database under this platform plug-in: a saved family
            # is passed through unchecked (Qt substitutes), which is all that
            # can be asserted here.
            self.assertEqual(self.P.resolve_ui_font_family(), "No Such Family 1234")
            return
        self.assertEqual(self.P.resolve_ui_font_family(), "")
        self.P.set_pref("ui_font_family", installed[0])
        self.assertEqual(self.P.resolve_ui_font_family(), installed[0])
        self.assertEqual(self.P.area_font("assistant").family(), installed[0])


class TestWireAreaFont(unittest.TestCase):
    """apply-now + re-apply-on-change, and above all: react to YOUR key only."""

    def setUp(self):
        from mpynode.ui import preferences

        self.P = preferences
        preferences._reset_for_tests()
        self.addCleanup(preferences._reset_for_tests)

    def _widget(self):
        from mpynode.ui.qt_wrapper import QWidget

        w = QWidget()
        self.addCleanup(w.deleteLater)
        return w

    def test_font_is_applied_at_wire_time(self):
        from mpynode.ui.widgets.font_prefs import wire_area_font

        self.P.set_pref("ui_font_size", 19)
        w = self._widget()
        wire_area_font(w, "panel")
        self.assertEqual(w.font().pointSize(), 19)

    def test_font_follows_a_later_change(self):
        from mpynode.ui.widgets.font_prefs import wire_area_font

        w = self._widget()
        wire_area_font(w, "panel")
        self.P.set_pref("ui_font_size", 22)
        self.assertEqual(w.font().pointSize(), 22)

    def test_the_family_follows_a_later_change(self):
        from mpynode.ui.widgets.font_prefs import wire_area_font

        installed = self.P.installed_font_families()
        if not installed:
            self.skipTest("no font database under this platform plug-in")
        w = self._widget()
        wire_area_font(w, "assistant")
        self.P.set_pref("ui_font_family", installed[-1])
        self.assertEqual(w.font().family(), installed[-1])

    def test_another_areas_key_is_ignored(self):
        # The whole point of splitting the areas: raising the editor font must
        # not reflow the panels.
        from mpynode.ui.widgets.font_prefs import wire_area_font

        self.P.set_pref("ui_font_size", 11)
        w = self._widget()
        wire_area_font(w, "panel")
        self.P.set_pref("editor_font_size", 30)
        self.P.set_pref("editor_font_family", "Courier New")
        self.assertEqual(w.font().pointSize(), 11)

    def test_rel_scales_below_its_area(self):
        from mpynode.ui.widgets.font_prefs import wire_area_font

        self.P.set_pref("ui_font_size", 20)
        w = self._widget()
        wire_area_font(w, "assistant", rel=0.85)
        self.assertEqual(w.font().pointSize(), 17)

    def test_rel_is_floored(self):
        # A subordinate caption must never become illegible.
        from mpynode.ui.widgets.font_prefs import wire_area_font

        self.P.set_pref("ui_font_size", self.P.FONT_SIZE_MIN)
        w = self._widget()
        wire_area_font(w, "assistant", rel=0.5)
        self.assertEqual(w.font().pointSize(), self.P.FONT_SIZE_MIN)

    def test_on_change_callback_fires(self):
        from mpynode.ui.widgets.font_prefs import wire_area_font

        seen = []
        w    = self._widget()
        wire_area_font(w, "panel", on_change=lambda: seen.append(1))
        self.P.set_pref("ui_font_size", 15)
        self.assertEqual(len(seen), 1)
        self.P.set_pref("editor_font_size", 15)
        self.assertEqual(len(seen), 1, "fired on another area's key")


class TestTranscriptScaling(unittest.TestCase):
    """The eleven authored ``font-size:Npx`` literals are kept as relative
    intent and converted in the insertion funnels. Exercised against the real
    method on a stand-in receiver, so no panel (and no Maya node) is needed."""

    def setUp(self):
        from mpynode.ui import preferences
        from mpynode.ui.widgets import assistant_panel

        self.P = preferences
        self.A = assistant_panel.NDAssistantPanel
        preferences._reset_for_tests()
        self.addCleanup(preferences._reset_for_tests)

    def _scale(self, html, pt):
        fake = types.SimpleNamespace(
            _AUTHORED_BASE_PX = self.A._AUTHORED_BASE_PX,
            _SIZE_PX_RE       = self.A._SIZE_PX_RE,
            _asst_pt          = lambda: pt,
        )
        return self.A._scale_html(fake, html)

    def test_px_literals_become_pt(self):
        out = self._scale('<div style="font-size:11px;">x</div>', 10)
        self.assertIn("font-size:9pt", out)
        self.assertNotIn("px", out)

    def test_the_size_tracks_the_preference(self):
        small = self._scale('<i style="font-size:11px;">x</i>', 10)
        large = self._scale('<i style="font-size:11px;">x</i>', 20)
        self.assertIn("font-size:9pt", small)
        self.assertIn("font-size:18pt", large)

    def test_the_visual_hierarchy_survives(self):
        # 11px (tool lines) must stay above 10px (timings) above 7px (spacer).
        out   = self._scale("a font-size:11px b font-size:10px c font-size:7px", 20)
        sizes = [int(s) for s in __import__("re").findall(r"font-size:(\d+)pt", out)]
        self.assertEqual(sizes, sorted(sizes, reverse=True), out)
        self.assertEqual(len(set(sizes)), 3, "tiers collapsed together")

    def test_small_settings_are_floored(self):
        out = self._scale("a font-size:7px b font-size:11px", 6)
        for size in __import__("re").findall(r"font-size:(\d+)pt", out):
            self.assertGreaterEqual(int(size), self.P.FONT_SIZE_MIN)

    def test_html_without_a_size_is_untouched(self):
        html = '<b>You</b><br>hello &amp; goodbye'
        self.assertEqual(self._scale(html, 14), html)

    def test_the_helpers_exist_on_the_panel(self):
        for name in ("_asst_pt", "_scale_html", "_rescale_existing",
                     "_on_assistant_font"):
            self.assertTrue(hasattr(self.A, name), name)


class TestRescaleExisting(unittest.TestCase):
    """Text already inserted keeps its char formats, so a live change has to
    rewrite the existing document. Done proportionally off toHtml(), which
    round-trips streamed bubbles too -- a recorded-history replay would lose
    anything the streaming path inserted by cursor.

    Exercised against a REAL QTextEdit: the toHtml()/setHtml() round-trip is
    the part that could plausibly mangle content, and a mock would not show it.
    """

    def setUp(self):
        from mpynode.ui import preferences
        from mpynode.ui.widgets import assistant_panel

        self.P = preferences
        self.A = assistant_panel.NDAssistantPanel
        preferences._reset_for_tests()
        self.addCleanup(preferences._reset_for_tests)
        preferences.set_pref("ui_font_size", 10)

    def _fake(self):
        from mpynode.ui.qt_wrapper import QTextEdit

        A = self.A

        class _Fake:
            _AUTHORED_BASE_PX = A._AUTHORED_BASE_PX
            _SIZE_PX_RE       = A._SIZE_PX_RE
            _SIZE_PT_RE       = A._SIZE_PT_RE
            _asst_pt          = A._asst_pt
            _scale_html       = A._scale_html
            _rescale_existing = A._rescale_existing

        f              = _Fake()
        f._transcript  = QTextEdit()
        f._asst_anchor = None
        self.addCleanup(f._transcript.deleteLater)
        # What the panel really appends: a bubble, a tool line, a timing line.
        for html in ('<b>You</b><br>build me a node',
                     '<div style="color:#7aa;font-size:11px;">apply mPyNode</div>',
                     '<div style="color:#666;font-size:10px;">done in 1m 06s</div>'):
            f._transcript.append(f._scale_html(html))
        return f

    def _sizes(self, f):
        import re

        html = f._transcript.toHtml()
        return sorted({int(round(float(x)))
                       for x in re.findall(r"font-size:([0-9.]+)pt", html)})

    def test_explicit_sizes_scale_proportionally(self):
        # Assert the AUTHORED tiers, not the whole size set: toHtml() also
        # emits the document's default font size, which comes from the widget
        # font rather than from any authored markup. In the real panel that
        # font is wired to the same preference, so it is already correct and
        # must not be double-scaled; here the stand-in leaves it at the Qt
        # default, which is why it shows up as an extra size.
        f      = self._fake()
        before = self._sizes(f)
        self.assertTrue(before, "no explicit pt sizes survived the append")
        # 11px and 10px against a 12px authoring base, at 10pt -> 9pt and 8pt.
        authored = [9, 8]
        for pt in authored:
            self.assertIn(pt, before, before)
        self.assertTrue(f._rescale_existing(2.0))
        after = self._sizes(f)
        for pt in authored:
            self.assertIn(pt * 2, after, after)
        self.assertGreater(max(after), max(before))

    def test_the_text_survives_the_round_trip(self):
        f = self._fake()
        f._rescale_existing(2.0)
        text = f._transcript.toPlainText()
        self.assertIn("build me a node", text)
        self.assertIn("apply mPyNode",   text)
        self.assertIn("done in 1m 06s",  text)

    def test_it_declines_mid_stream(self):
        # A live assistant bubble is being rewritten by cursor; replacing the
        # whole document under it would strand the anchor.
        f              = self._fake()
        f._asst_anchor = 5
        self.assertFalse(f._rescale_existing(2.0))

    def test_it_declines_a_no_op_ratio(self):
        f = self._fake()
        self.assertFalse(f._rescale_existing(1.0))
        self.assertFalse(f._rescale_existing(0))


class TestWiringIsPresent(unittest.TestCase):
    """Source-level: every area named in the plan is actually wired. A missing
    call is invisible at runtime -- the widget just keeps the inherited font --
    so assert the call sites rather than trusting they were all done."""

    WIRED = {
        "assistant_panel.py": 4,  # transcript, input, and two small labels
        "attributes.py":      1,  # covers NDOutputAttrTree by inheritance
        "framework_tab.py":   1,
        "logger.py":          1,
        "profile.py":         1,
        "scene_tree.py":      1,
        "variables.py":       1,
        "watch.py":           1,
    }

    def test_each_module_wires_its_widget(self):
        import io
        import os

        from tests import _paths

        base = os.path.join(_paths.ROOT, "scripts", "mpynode", "ui", "widgets")
        for mod, at_least in sorted(self.WIRED.items()):
            src = io.open(os.path.join(base, mod), encoding="utf-8").read()
            # The import line is `... import wire_area_font` with no
            # paren, so every match with one is a real call site.
            calls = src.count("wire_area_font(")
            self.assertGreaterEqual(
                calls, at_least,
                "%s wires %d widget(s), expected at least %d"
                % (mod, calls, at_least))

    def test_the_tab_bars_follow_the_ui_font(self):
        # The Init | Compute | API bar and the Workspace | Templates bar are
        # siblings of the wired views, not children, so each is wired itself.
        # The editors under the script bar are NOT: they own their font.
        import io
        import os

        from tests import _paths

        src = io.open(os.path.join(_paths.ROOT, "scripts", "mpynode", "ui",
                                   "mpynode_designer.py"),
                      encoding="utf-8").read()
        self.assertIn('wire_area_font(self._script_tab_widget.tabBar(), "panel")', src)
        self.assertIn('wire_area_font(self._mode_tab_bar, "panel")', src)
        self.assertNotIn('wire_area_font(self._script_tab_widget, "panel")', src)

    def test_the_editors_are_left_alone(self):
        # editor_core owns a family pref and a Ctrl+wheel zoom this helper has
        # no concept of; rewiring a working path would only add risk.
        import io
        import os

        from tests import _paths

        src = io.open(os.path.join(_paths.ROOT, "scripts", "mpynode", "ui",
                                   "widgets", "editor_core.py"),
                      encoding="utf-8").read()
        self.assertNotIn("wire_area_font", src)
        self.assertIn("editor_font", src)

    def test_no_stylesheet_pins_a_font_size_in_the_assistant(self):
        # A stylesheet font-size beats setFont(), so any left behind would pin
        # its widget while the rest of the panel scaled.
        import io
        import os
        import re

        from tests import _paths

        src = io.open(os.path.join(_paths.ROOT, "scripts", "mpynode", "ui",
                                   "widgets", "assistant_panel.py"),
                      encoding="utf-8").read()
        offenders = re.findall(r'setStyleSheet\([^)]*font-size[^)]*\)', src)
        self.assertEqual(offenders, [], offenders)
