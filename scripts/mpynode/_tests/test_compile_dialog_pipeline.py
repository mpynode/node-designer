"""The compile dialog's three-stage pipeline gate.

The single "AI-optimize C++ (slow)" checkbox conflated three separate decisions.
Split, each stage can be declined -- and the two implications between them are
made VISIBLE (checked + disabled) instead of being applied silently by the
engine:

* stage 3 needs stage 2, because there is nothing to speed up in a skeleton
  whose PORT regions are still empty;
* stage 3 needs the authored ``@maya_test``s, because for a node whose generic
  pointwise parity SKIPS they are the only gate the optimizer has -- which is
  exactly how a wrong candidate once shipped.

Constructing the real dialog needs Maya + Qt, so the gating logic is exercised
on a lightweight stand-in that reuses the dialog's own unbound methods.
"""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ._setup import standalone_init


def setUpModule():
    standalone_init()


class _Check:
    """Enough QCheckBox for the gate logic."""

    def __init__(self, checked=False):
        self._checked = checked
        self._enabled = True
        self.tip = ""

    def isChecked(self):
        return self._checked

    def setChecked(self, v):
        self._checked = bool(v)

    def isEnabled(self):
        return self._enabled

    def setEnabled(self, v):
        self._enabled = bool(v)

    def setToolTip(self, t):
        self.tip = t


class _Combo:
    def __init__(self, text="2"):
        self._text = text
        self._enabled = True

    def currentText(self):
        return self._text

    def setCurrentText(self, t):
        self._text = t

    def setEnabled(self, v):
        self._enabled = bool(v)

    def isEnabled(self):
        return self._enabled


class _Dlg:
    """A stand-in carrying only the widgets the gate logic touches."""

    def __init__(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        self._assist_check = _Check(True)
        self._optimize_check = _Check(False)
        self._run_tests_check = _Check(False)
        self._rounds_combo = _Combo("2")
        self._keep_intermediates_check = _Check(False)
        self._clean_scratch_check = _Check(True)
        self._sync = CompileDialog._sync_pipeline_gates.__get__(self)
        self._opts = CompileDialog._pipeline_options.__get__(self)
        # The gate also renames the Compile button ("Compile with AI" only while
        # stage 2 is armed). No button on the stand-in -> the real method's
        # not-yet-built guard runs, same as during _build_ui.
        self._sync_compile_button_label = (
            CompileDialog._sync_compile_button_label.__get__(self))


class TestGateImplications(unittest.TestCase):
    def setUp(self):
        self.d = _Dlg()

    def test_defaults_preserve_todays_behaviour(self):
        """Porting is unconditional today; assist defaulting off would silently
        stop shipping nodes that currently build."""
        self.d._sync()
        o = self.d._opts()
        self.assertTrue(o["ai_assist"])
        self.assertFalse(o["optimize"])
        self.assertFalse(o["keep_intermediates"])
        self.assertTrue(o["clean_scratch"])

    def test_optimize_forces_assist_and_authored_tests_visibly(self):
        self.d._optimize_check.setChecked(True)
        self.d._sync()

        for check in (self.d._assist_check, self.d._run_tests_check):
            self.assertTrue(check.isChecked())
            self.assertFalse(check.isEnabled(),
                             "a forced choice must be shown as forced")
        self.assertIn("only gate", self.d._run_tests_check.tip.lower())

    def test_turning_optimize_off_restores_what_the_user_had(self):
        self.d._assist_check.setChecked(False)
        self.d._run_tests_check.setChecked(False)
        self.d._sync()

        self.d._optimize_check.setChecked(True)
        self.d._sync()
        self.assertTrue(self.d._assist_check.isChecked())

        self.d._optimize_check.setChecked(False)
        self.d._sync()
        self.assertFalse(self.d._assist_check.isChecked(),
                         "the user's own choice must come back")
        self.assertFalse(self.d._run_tests_check.isChecked())
        self.assertTrue(self.d._assist_check.isEnabled())

    def test_repeated_syncs_do_not_lose_the_remembered_state(self):
        self.d._assist_check.setChecked(False)
        self.d._sync()
        self.d._optimize_check.setChecked(True)
        self.d._sync()
        self.d._sync()
        self.d._sync()
        self.d._optimize_check.setChecked(False)
        self.d._sync()
        self.assertFalse(self.d._assist_check.isChecked())

    def test_assist_off_alone_is_honoured(self):
        self.d._assist_check.setChecked(False)
        self.d._sync()
        self.assertFalse(self.d._opts()["ai_assist"])

    def test_options_resolve_the_implication_even_if_sync_never_ran(self):
        """_pipeline_options is the single source the engine reads."""
        self.d._assist_check.setChecked(False)
        self.d._optimize_check.setChecked(True)
        o = self.d._opts()
        self.assertTrue(o["ai_assist"])
        self.assertTrue(o["run_tests"])


class _Label:
    """Enough QLabel for the rail."""

    def __init__(self):
        self.text = ""
        self.style = ""
        self.tip = ""
        self.visible = None

    def setText(self, t):
        self.text = t

    def setStyleSheet(self, s):
        self.style = s

    def setToolTip(self, t):
        self.tip = t

    def setVisible(self, v):
        self.visible = bool(v)


class _RailDlg:
    """A stand-in carrying only what the rail logic touches."""

    def __init__(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        for const in ("_RAIL_STEPS", "_RAIL_GLYPH", "_RAIL_RANK",
                      "_RAIL_COLOR"):
            setattr(self, const, getattr(CompileDialog, const))
        self._rail_labels = {k: _Label() for k, _t in self._RAIL_STEPS}
        self._rail_state = {}
        self._rail_detail = _Label()
        for name in ("_rail_reset", "_rail_set", "_rail_apply", "_rail_render"):
            setattr(self, name, getattr(CompileDialog, name).__get__(self))

    def state(self, key):
        return self._rail_state.get(key)


class TestPipelineRail(unittest.TestCase):
    """The five checkpoints the user watches, and the one rule that matters:
    the rail may never claim more than the run actually did."""

    def setUp(self):
        self.d = _RailDlg()
        self.d._rail_reset({"ai_assist": True, "optimize": True})

    def test_a_declined_stage_starts_and_stays_off(self):
        d = _RailDlg()
        d._rail_reset({"ai_assist": False, "optimize": False})

        self.assertEqual(d.state("assist"), "off")
        self.assertEqual(d.state("optimize"), "off")
        # An event must not be able to light a stage the user turned off.
        d._rail_apply("stage", "ok", "2_assisted")
        d._rail_apply("optimize", "ok", "kDTree 4.7x")
        self.assertEqual(d.state("assist"), "off")
        self.assertEqual(d.state("optimize"), "off")

    def test_the_stage_artifacts_light_their_checkpoints(self):
        self.d._rail_apply("stage", "ok", "1_transpiled")
        self.assertEqual(self.d.state("transpile"), "done")
        self.assertEqual(self.d.state("assist"), "pending")

        self.d._rail_apply("stage", "ok", "2_assisted")
        self.assertEqual(self.d.state("assist"), "done")

    def test_progress_is_monotonic_so_a_second_node_cannot_unlight_it(self):
        self.d._rail_apply("stage", "ok", "1_transpiled")
        self.d._rail_apply("port", "start", "porting")
        self.assertEqual(self.d.state("transpile"), "done",
                         "node B starting must not un-tick node A's work")

    def test_a_skipped_verify_outranks_a_verified_one(self):
        """Weakest outcome wins: a run where one node's parity was SKIPPED has
        not been fully checked, and a green tick would say it had."""
        self.d._rail_apply("verify", "ok", "")
        self.assertEqual(self.d.state("verify"), "done")
        self.d._rail_apply("verify", "skip", "array attrs")
        self.assertEqual(self.d.state("verify"), "skip")
        # ...and a later pass cannot scrub it.
        self.d._rail_apply("verify", "ok", "")
        self.assertEqual(self.d.state("verify"), "skip")

    def test_a_failure_is_sticky(self):
        self.d._rail_apply("assemble", "fail", "link error")
        self.d._rail_apply("assemble", "ok", "")
        self.assertEqual(self.d.state("bundle"), "fail")

    def test_a_port_failure_lands_on_the_stage_that_owned_it(self):
        d = _RailDlg()
        d._rail_reset({"ai_assist": True, "optimize": False})
        d._rail_apply("port", "fail", "clang error")
        self.assertEqual(d.state("transpile"), "fail",
                         "nothing had been transpiled yet, so it failed there")

        d = _RailDlg()
        d._rail_reset({"ai_assist": True, "optimize": False})
        d._rail_apply("stage", "ok", "1_transpiled")
        d._rail_apply("port", "fail", "clang error")
        self.assertEqual(d.state("transpile"), "done")
        self.assertEqual(d.state("assist"), "fail")

    def test_a_deterministic_port_does_not_claim_the_ai_helped(self):
        """A node the transpiler fully lowers reaches "port ok" without an LLM
        ever being called. Ticking "AI assist" there is a false credit -- and
        the 2_assisted artifact is the signal that actually distinguishes them."""
        self.d._rail_apply("port", "ok", "")

        self.assertEqual(self.d.state("transpile"), "done")
        self.assertEqual(self.d.state("assist"), "pending")

        self.d._rail_apply("stage", "ok", "2_assisted")
        self.assertEqual(self.d.state("assist"), "done")

    def test_assist_is_retired_when_the_run_says_no_node_needed_it(self):
        """With AI optimize OFF there is no optimize event, so the chip used to
        sit on "pending" -- indistinguishable from "not yet" -- until the
        terminal sweep. The controller STATES it once porting is over."""
        d = _RailDlg()
        d._rail_reset({"ai_assist": True, "optimize": False})
        d._rail_apply("stage", "ok", "1_transpiled")
        d._rail_apply("port", "ok", "")
        self.assertEqual(d.state("assist"), "pending")

        d._rail_apply("port", "skip", "no node needed AI assist")
        self.assertEqual(d.state("assist"), "skip")

    def test_the_first_optimize_event_also_retires_a_pending_assist(self):
        """Optimize starts only once EVERY node has ported, so an assist chip
        still "pending" here is final -- not "not yet". Leaving it grey until
        the terminal sweep can be an hour of optimizing away."""
        self.d._rail_apply("stage", "ok", "1_transpiled")
        self.d._rail_apply("port", "ok", "")
        self.assertEqual(self.d.state("assist"), "pending")

        self.d._rail_apply("optimize", "info", "[kDTree] baseline 12.400 ms")
        self.assertEqual(self.d.state("assist"), "skip")

    def test_optimizing_cannot_scrub_an_assist_that_really_ran(self):
        """skip OUTRANKS done, so an unguarded set at the optimize event would
        turn a genuine AI-filled body into "did not run"."""
        self.d._rail_apply("stage", "ok", "2_assisted")
        self.d._rail_apply("optimize", "info", "[kDTree] baseline 12.400 ms")
        self.assertEqual(self.d.state("assist"), "done")

    def test_that_claim_cannot_scrub_an_assist_that_really_ran(self):
        """skip OUTRANKS done, so an unguarded set would turn a genuine tick
        into "did not run"."""
        self.d._rail_apply("stage", "ok", "2_assisted")
        self.d._rail_apply("port", "skip", "no node needed AI assist")
        self.assertEqual(self.d.state("assist"), "done")

    def test_that_claim_touches_neither_a_declined_nor_a_failed_assist(self):
        d = _RailDlg()
        d._rail_reset({"ai_assist": False, "optimize": False})
        d._rail_apply("port", "skip", "no node needed AI assist")
        self.assertEqual(d.state("assist"), "off")

        d = _RailDlg()
        d._rail_reset({"ai_assist": True, "optimize": False})
        d._rail_apply("stage", "ok", "1_transpiled")
        d._rail_apply("port", "fail", "clang error")
        d._rail_apply("port", "skip", "no node needed AI assist")
        self.assertEqual(d.state("assist"), "fail")

    def test_a_stage_nothing_reached_ends_as_did_not_run_not_pending(self):
        """At the end, "pending" is unreadable: it looks like the run stopped
        early. Nothing reached it, and that is what it should say."""
        self.d._rail_apply("stage", "ok", "1_transpiled")
        self.d._rail_apply("assemble", "ok", "")
        self.d._rail_apply("done", "ok", "")

        self.assertEqual(self.d.state("transpile"), "done")
        self.assertEqual(self.d.state("bundle"), "done")
        self.assertEqual(self.d.state("assist"), "skip")
        self.assertEqual(self.d.state("verify"), "skip")

    def test_finishing_does_not_disturb_a_declined_stage(self):
        d = _RailDlg()
        d._rail_reset({"ai_assist": True, "optimize": False})
        d._rail_apply("done", "ok", "")
        self.assertEqual(d.state("optimize"), "off")

    def test_the_optimizer_narration_becomes_the_detail_line(self):
        """The user asked to SEE what the AI is trying, not just that it is
        trying. The engine's round-intent line is that sentence."""
        self.d._rail_apply(
            "optimize", "info",
            "[kDTree] round 2/4 trying: vectorise the argmin (predicted 3.00x)")

        self.assertEqual(self.d.state("optimize"), "run")
        self.assertIn("vectorise the argmin", self.d._rail_detail.text)
        self.assertIn("round 2/4", self.d._rail_detail.text)

    def test_an_empty_optimize_event_does_not_blank_the_last_thing_said(self):
        self.d._rail_apply("optimize", "info", "[kDTree] baseline 12.400 ms")
        self.d._rail_apply("optimize", "info", "")
        self.assertIn("baseline", self.d._rail_detail.text)

    def test_every_checkpoint_renders_its_name_and_a_glyph(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        for key, title in CompileDialog._RAIL_STEPS:
            lbl = self.d._rail_labels[key]
            self.assertIn(title, lbl.text)
            self.assertTrue(lbl.text.strip(), key)

    def test_a_done_checkpoint_is_green_and_a_failed_one_is_not(self):
        self.d._rail_apply("assemble", "ok", "")
        done_style = self.d._rail_labels["bundle"].style
        self.d._rail_apply("verify", "fail", "maxerr 1e-2")
        fail_style = self.d._rail_labels["verify"].style
        self.assertTrue(done_style)
        self.assertNotEqual(done_style, fail_style)

    def test_an_unknown_event_is_ignored_rather_than_guessed_at(self):
        before = dict(self.d._rail_state)
        self.d._rail_apply("typeid", "warn", "clash")
        self.assertEqual(self.d._rail_state, before)


class TestPerNodeSpeedup(unittest.TestCase):
    """How much faster THIS node got belongs on THIS node's row.

    The optimizer's per-node result already comes back on ``result['optimize']``
    but only ever reached the log, where it scrolls away -- so the table said
    "verified" for a node that got 4.7x and for one the optimizer rejected.
    """

    def _dlg(self, rows=("kDTree",)):
        # A fake table, not a QTableWidget: a real one needs a QApplication,
        # which these headless runs do not have. QTableWidgetItem is a plain
        # value type and constructs fine.
        from mpynode.ui.qt_wrapper import QTableWidgetItem
        from mpynode.ui.dialogs.compile_dialog import CompileDialog, _COL_STATUS

        class _Table:
            def __init__(self):
                self.items = {}

            def item(self, r, c):
                return self.items.get((r, c))

            def setItem(self, r, c, it):
                self.items[(r, c)] = it

        class _D:
            pass

        d = _D()
        d._table = _Table()
        d._row_by_type = {}
        for i, name in enumerate(rows):
            d._row_by_type[name] = i
            d._table.setItem(i, _COL_STATUS, QTableWidgetItem("verified"))
        d._set_cell = CompileDialog._set_cell.__get__(d)
        d._stamp_optimize_results = (
            CompileDialog._stamp_optimize_results.__get__(d))
        return d

    def _status(self, d, row=0):
        from mpynode.ui.dialogs.compile_dialog import _COL_STATUS

        item = d._table.item(row, _COL_STATUS)
        return item.text() if item is not None else ""

    def test_an_accepted_speedup_lands_on_the_row(self):
        d = self._dlg()
        d._stamp_optimize_results({"optimize": {
            "kDTree": {"accepted": True, "speedup": 4.68, "reason": ""}}})

        self.assertIn("verified", self._status(d))
        self.assertIn("4.7", self._status(d))

    def test_a_rejected_optimize_says_so_rather_than_nothing(self):
        """Silence reads as 'not optimized'; the truth is 'tried, kept the
        original' and that is the more useful thing to know."""
        d = self._dlg()
        d._stamp_optimize_results({"optimize": {
            "kDTree": {"accepted": False, "speedup": 1.0,
                       "reason": "no candidate beat the baseline"}}})

        self.assertIn("verified", self._status(d))
        self.assertIn("kept original", self._status(d).lower())

    def test_a_node_the_optimizer_never_touched_is_left_alone(self):
        d = self._dlg(rows=("kDTree", "patchRelax"))
        d._stamp_optimize_results({"optimize": {
            "kDTree": {"accepted": True, "speedup": 2.0}}})

        self.assertEqual(self._status(d, 1), "verified")

    def test_no_optimize_section_is_a_no_op(self):
        d = self._dlg()
        d._stamp_optimize_results({})
        self.assertEqual(self._status(d), "verified")

    def test_stamping_twice_does_not_double_the_suffix(self):
        d = self._dlg()
        rec = {"optimize": {"kDTree": {"accepted": True, "speedup": 4.68}}}
        d._stamp_optimize_results(rec)
        d._stamp_optimize_results(rec)
        self.assertEqual(self._status(d).count("4.7"), 1)

    def test_it_runs_on_a_failed_build_too(self):
        import inspect

        from mpynode.ui.dialogs import compile_dialog

        fin = inspect.getsource(compile_dialog).split(
            "def _on_finished(", 1)[1].split("\n    def ", 1)[0]
        # Anchored on the built/failed branch itself, not on its exact
        # condition: that condition has since grown the AI-optimize-failed case
        # ("(ok or ai_failed) and bundle_exists"), and an anchor that stops
        # matching makes this assertion pass over the WHOLE method -- vacuously.
        self.assertIn("and bundle_exists:", fin, "the anchor stopped matching")
        head = fin.split("and bundle_exists:", 1)[0]
        self.assertIn("_stamp_optimize_results(result)", head,
                      "a rejected/failed run is when the numbers matter most")


class TestStageEventPresentation(unittest.TestCase):
    """The new per-artifact ``stage`` event goes through the SAME formatters as
    every other event, so an unhandled one falls through to the generic
    "<stage> <status>" and writes literal "stage ok" into the node's row."""

    def test_the_row_says_what_landed_not_that_something_landed(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        t1 = CompileDialog._cell_text("stage", "ok", "1_transpiled")
        t2 = CompileDialog._cell_text("stage", "ok", "2_assisted")

        self.assertNotIn("stage ok", (t1, t2))
        self.assertIn("transpil", t1.lower())
        self.assertIn("assist", t2.lower())

    def test_an_unrecognised_stage_id_does_not_write_gibberish(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        self.assertEqual(CompileDialog._cell_text("stage", "ok", "4_future"),
                         None,
                         "no cell update beats a wrong one")

    def test_a_none_cell_text_leaves_the_row_alone(self):
        import inspect

        from mpynode.ui.dialogs import compile_dialog

        main = inspect.getsource(compile_dialog).split(
            "def _on_progress_main", 1)[1].split("\n    @", 1)[0]
        self.assertIn("if cell is not None", main)

    def test_the_transpile_step_narrates_itself(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        line = CompileDialog._narration_line("stage", "ok", "kDTree",
                                             "1_transpiled")
        self.assertIsNotNone(line)
        self.assertIn("kDTree", line)
        self.assertIsNone(
            CompileDialog._narration_line("stage", "ok", "kDTree", "9_nope"))


class TestRailWiring(unittest.TestCase):
    def _source(self):
        import inspect

        from mpynode.ui.dialogs import compile_dialog

        return inspect.getsource(compile_dialog)

    def test_progress_events_reach_the_rail(self):
        src = self._source()
        main = src.split("def _on_progress_main", 1)[1].split("\n    @", 1)[0]
        self.assertIn("_rail_apply(", main)

    def test_a_run_starts_from_a_clean_rail(self):
        """Left over from the previous compile, a green tick is a lie about
        this one."""
        src = self._source()
        compile_fn = src.split("def _on_compile", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("_rail_reset(pipe)", compile_fn)


class TestPipelineGroupPresentation(unittest.TestCase):
    """Stage 1 is a stage, and should look like one.

    It was the only row without a checkbox, so the group read as "two optional
    things" rather than "three stages, the first of which is not negotiable".
    It gets a box that is checked and cannot be turned off -- and it must stay
    the same colour as the others, which rules out setEnabled(False) (Qt greys a
    disabled checkbox's label).
    """

    def _source(self):
        import inspect

        from mpynode.ui.dialogs import compile_dialog

        return inspect.getsource(compile_dialog._build_pipeline_ui) \
            if hasattr(compile_dialog, "_build_pipeline_ui") \
            else inspect.getsource(compile_dialog.CompileDialog._build_pipeline_ui)

    def test_stage_one_has_a_checkbox_that_is_on(self):
        src = self._source()
        self.assertIn('QCheckBox("1  Transpile"', src)
        self.assertIn("_transpile_check.setChecked(True)", src)

    def test_stage_one_is_locked_without_being_greyed_out(self):
        src = self._source()
        self.assertNotIn("_transpile_check.setEnabled(False)", src,
                         "disabling greys the label; the user asked for it to "
                         "read the same white as the other two")
        self.assertIn("_transpile_check.setFocusPolicy", src)

    def test_stage_one_keeps_its_tooltip_reachable(self):
        """Qt delivers tooltips through the mouse-event path, so a widget marked
        transparent to mouse events can never show one -- and stage 1 is the box
        a user is most likely to interrogate, being the only one they cannot
        click."""
        src = self._source()
        self.assertIn("_transpile_check.setToolTip", src)
        self.assertNotIn("WA_TransparentForMouseEvents", src)

    def test_stage_one_cannot_end_up_unchecked(self):
        src = self._source()
        self.assertIn("_transpile_check.toggled.connect", src,
                      "without a revert, a click (or Space) turns stage 1 off")

    def test_stage_one_is_not_re_enabled_by_the_busy_toggle(self):
        """_set_busy re-enables every option widget when a run finishes. A box
        that was never disabled must not be swept up in that."""
        import inspect

        from mpynode.ui.dialogs import compile_dialog

        busy = inspect.getsource(compile_dialog).split(
            "def _set_busy", 1)[1].split("\n    def ", 1)[0]
        self.assertNotIn("_transpile_check", busy)

    def test_the_rows_are_laid_out_on_a_grid_so_they_form_columns(self):
        """Hand-tuned addSpacing() cannot align three checkbox labels of
        different widths; a grid sizes the column to the widest."""
        src = self._source()
        self.assertIn("QGridLayout", src)
        self.assertNotIn("addSpacing(18)", src)

    def test_stage_one_is_not_offered_as_a_pipeline_choice(self):
        """It is always on, so it must not appear in the dict the engine reads
        -- a key nothing consumes is a promise the UI cannot keep."""
        d = _Dlg()
        self.assertNotIn("transpile", d._opts())


class TestRoundsSelection(unittest.TestCase):
    def test_rounds_are_read_from_the_combo(self):
        d = _Dlg()
        d._rounds_combo.setCurrentText("6")
        self.assertEqual(d._opts()["optimize_rounds"], 6)

    def test_a_junk_rounds_value_falls_back_to_the_engine_default(self):
        d = _Dlg()
        d._rounds_combo.setCurrentText("lots")
        self.assertEqual(d._opts()["optimize_rounds"], 2)


class TestDialogWiring(unittest.TestCase):
    def _source(self):
        import inspect

        from mpynode.ui.dialogs import compile_dialog

        return inspect.getsource(compile_dialog)

    def test_the_gate_reaches_the_engine(self):
        src = self._source()
        self.assertTrue("ai_assist=ai_assist" in src,
                        "the dialog never passes ai_assist to the controller")
        self.assertEqual(src.count("ai_assist=ai_assist"), 2,
                         "both the single and multi-version paths must pass it")

    def test_the_cleanup_choice_reaches_the_engine(self):
        """Off must mean off: the engine deletes the working dirs, so a dialog
        that reads the checkbox but never sends it is silently a no-op."""
        src = self._source()
        self.assertEqual(src.count("clean_scratch=clean_scratch"), 2,
                         "both the single and multi-version paths must pass it")

    def test_the_old_single_optimize_checkbox_is_gone(self):
        """The conflated control, not the words -- the docstring explaining the
        replacement legitimately still names it."""
        src = self._source()
        self.assertFalse('QCheckBox("AI-optimize C++ (slow)"' in src,
                         "the conflated checkbox should have been replaced by "
                         "the three-stage pipeline group")
        self.assertTrue('QCheckBox("3  AI optimize"' in src)
        self.assertTrue('QCheckBox("2  AI assist"' in src)

    def test_busy_toggling_reasserts_the_gates(self):
        """_set_busy re-enables every widget; without a re-sync, finishing a run
        hands back an editable 'AI assist' box while optimize is still on."""
        src = self._source()
        busy = src.split("def _set_busy", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("_sync_pipeline_gates()", busy)


if __name__ == "__main__":
    unittest.main()
