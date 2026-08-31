"""CompileDialog wiring for the scene-safety + progress-bar fixes.

Three behaviors, tested with a duck-typed ``self`` (constructing the real
QDialog under headless mayapy is unreliable):

  1. ``_on_compile`` must drive the parity verify through ``subprocess_verify_fn``
     (scene-safe) and NOT ``main_thread_verify_fn`` (which wiped the live scene).
  2. ``_offer_load`` must load through ``load_or_reload_native_plugin`` (unload
     stale -> load new; never file(new)), surfacing reload vs. error.
  3. The progress bar is GONE: ``_set_busy`` / ``_on_progress_main`` /
     ``_on_finished`` must not reference ``self._progress_bar`` anymore.
"""
from __future__ import annotations

import inspect
import os
import shutil
import tempfile
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest import mock

from tests._setup import standalone_init


def setUpModule():
    standalone_init()


def _real_bundle(testcase):
    """Create a real ``.bundle`` on disk (cleaned up when the test ends) so
    ``_on_finished``'s #59 existence gate treats the build as a genuine success.
    Passing a path that does not exist now (correctly) routes to the failure
    branch, so success-modelling tests must point at a file that exists."""
    d = tempfile.mkdtemp(prefix="ndwiring_bundle_")
    testcase.addCleanup(shutil.rmtree, d, True)
    path = os.path.join(d, "myPlug.bundle")
    with open(path, "w") as fh:
        fh.write("")
    return path


class _W:
    """Minimal fake widget recording the last call."""

    def __init__(self):
        self.enabled = None
        self.visible = None
        self.text = None
        self.value = None

    def setEnabled(self, v):
        self.enabled = v

    def setVisible(self, v):
        self.visible = v

    def setText(self, t):
        self.text = t

    def setValue(self, v):
        self.value = v

    def isChecked(self):
        return True


class _LogW:
    """Fake QPlainTextEdit: records appended lines + visibility + clears."""

    def __init__(self):
        self.lines = []
        self.visible = None
        self.cleared = 0

    def appendPlainText(self, t):
        self.lines.append(t)

    def clear(self):
        self.cleared += 1
        self.lines = []

    def setVisible(self, v):
        self.visible = v

    def isVisible(self):
        return bool(self.visible)


class _FakeSelf:
    """Duck-typed CompileDialog with only what the tested methods touch."""

    def __init__(self):
        self._busy = False
        self._compile_btn = _W()
        self._cancel_btn = _W()
        self._name_edit = _W()
        self._out_edit = _W()
        self._browse_btn = _W()
        self._strict_check = _W()
        # Off-by-default "Run authored node tests" option (locked by _set_busy
        # like the other options; read by _on_compile).
        self._run_tests_check = _W()
        # The three-stage pipeline group. Stage 1 (transpile) always runs and
        # has no widget; stage 2 defaults ON so today's unconditional porting is
        # unchanged, and stage 3 is opt-in and implies stage 2.
        self._optimize_check = _W()
        self._assist_check = _W()
        self._rounds_combo = _W()
        self._keep_intermediates_check = _W()
        self._clean_scratch_check = _W()
        self._sync_pipeline_gates = lambda *a: None
        # Post-run shortcuts to the pipeline's own output (shown by _on_finished
        # only when there is something to open).
        self._report_btn = _W()
        self._folder_btn = _W()
        self._last_report_path = None
        # Live checkpoint strip (its own logic is covered in
        # test_compile_dialog_pipeline; here it just must not be missing).
        self._rail_apply = lambda *a: None
        self._rail_reset = lambda *a: None
        # Per-row optimizer verdict (covered in test_compile_dialog_pipeline).
        self._stamp_optimize_results = lambda *a: None
        # Mirror the real _set_busy's widgets (checkbox-list model): the bundle
        # is now driven by per-row checkboxes + these bulk buttons, not the old
        # Add/Remove pair.
        self._select_all_btn = _W()
        self._select_none_btn = _W()
        self._refresh_btn = _W()
        # External-.mpn feature widgets (locked by _set_busy alongside the rest).
        self._add_mpn_btn = _W()
        self._ignore_persistent_check = _W()
        self._table = _W()
        self._status_label = _W()
        self._row_by_type = {}
        self._bundle_path = None
        self._set_busy_calls = []
        self._offer_load_calls = []
        # Spinner + log surface (recording stubs). The real implementations are
        # exercised separately in TestCompileDialogSpinnerLog; here they just
        # record so _set_busy/_on_progress_main wiring can be asserted.
        self._log_view = _LogW()
        self._log_toggle_btn = _W()
        self._status_msg = ""
        self._status_msgs = []
        self._spin_started = 0
        self._spin_stopped = 0
        self._appended_logs = []
        self._clear_log_calls = 0
        self._show_log_calls = []
        # Elapsed-timer origin (set by the real _set_busy(True); None when idle).
        self._run_start = None
        # Multi-version target checkboxes (locked by _set_busy; empty here).
        self._maya_checks = {}
        # _on_progress_main mirrors high-level events to the log via this pure
        # staticmethod -- bind the REAL one (the fake stands in for a real
        # CompileDialog, which has it).
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as _CD

        self._narration_line = _CD._narration_line
        # _on_finished gates the load offer through this pure staticmethod.
        self._should_offer_load = _CD._should_offer_load
        # Maya root a single build targeted (None = legacy/running Maya).
        self._build_target_root = None
        # WS2 "Fix with AI" concierge surface (recording stubs).
        self._ai_btn = _W()
        self._last_ai_result = None
        self._last_ai_out_dir = None
        self._update_ai_button_calls = []
        # NOTE: deliberately NO _progress_bar -- touching it must raise.

    def _update_ai_button(self, result, out_dir):
        self._update_ai_button_calls.append((result, out_dir))

    def _set_busy(self, busy):
        self._set_busy_calls.append(busy)
        self._busy = busy

    def _set_cell(self, row, col, text):
        pass

    def _offer_load(self, bundle_path, companion_paths=None):
        self._offer_load_calls.append(bundle_path)

    # --- spinner + log recording stubs --------------------------------
    def _start_spinner(self):
        self._spin_started += 1

    def _stop_spinner(self):
        self._spin_stopped += 1

    def _set_status_msg(self, msg):
        self._status_msg = msg or ""
        self._status_msgs.append(self._status_msg)
        self._status_label.setText(self._status_msg)

    def _append_log(self, line):
        self._appended_logs.append(line)

    def _clear_log(self):
        self._clear_log_calls += 1

    def _show_log(self, show):
        self._show_log_calls.append(bool(show))

    @staticmethod
    def _cell_text(stage, status, detail):
        return "%s %s" % (stage, status)


class TestCompileDialogVerifyWiring(unittest.TestCase):
    def test_on_compile_uses_subprocess_verify_not_main_thread(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn(
            "subprocess_verify_fn", src,
            "_on_compile must use the scene-safe subprocess verify")
        self.assertNotIn(
            "main_thread_verify_fn", src,
            "_on_compile must NOT use main_thread_verify_fn (it wipes the scene)")

    def test_on_compile_threads_live_maya_version(self):
        """The build + verify must use the RUNNING Maya, not a hardcoded 2026."""
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn("_resolve_maya_dir", src,
                      "_on_compile must resolve the live Maya install dir")
        self.assertIn("maya", src)


class TestResolveMayaDir(unittest.TestCase):
    def _set_loc(self, value):
        old = os.environ.get("MAYA_LOCATION")
        if value is None:
            os.environ.pop("MAYA_LOCATION", None)
        else:
            os.environ["MAYA_LOCATION"] = value

        def _restore():
            if old is None:
                os.environ.pop("MAYA_LOCATION", None)
            else:
                os.environ["MAYA_LOCATION"] = old

        self.addCleanup(_restore)

    def test_strips_macos_app_bundle_suffix(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self._set_loc("/Applications/Autodesk/maya2024/Maya.app/Contents")
        self.assertEqual(cd._resolve_maya_dir(),
                         "/Applications/Autodesk/maya2024")

    def test_strips_macos_app_bundle_suffix_with_trailing_slash(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # A trailing slash on MAYA_LOCATION must not defeat the suffix strip
        # (else the install root is wrong and the pre-flight probes the wrong
        # Maya, falsely flagging missing devkit headers).
        self._set_loc("/Applications/Autodesk/maya2024/Maya.app/Contents/")
        self.assertEqual(cd._resolve_maya_dir(),
                         "/Applications/Autodesk/maya2024")

    def test_linux_style_passthrough(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self._set_loc("/usr/autodesk/maya2026")
        self.assertEqual(cd._resolve_maya_dir(), "/usr/autodesk/maya2026")

    def test_none_when_unset(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self._set_loc(None)
        self.assertIsNone(cd._resolve_maya_dir())


class TestCellTextPreflight(unittest.TestCase):
    def test_preflight_fail_renders_blocked(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        txt = CompileDialog._cell_text("preflight", "fail", "no compiler")
        # A node-targeted pre-flight block must read clearly, not "preflight fail".
        self.assertIn("blocked", txt.lower())
        self.assertIn("no compiler", txt)


class TestCellTextVerify(unittest.TestCase):
    """A verify that couldn't run is "compiled (verify skipped: <why>)" -- NOT a
    red "FAILED parity". Only a genuine numeric mismatch is a parity failure.
    """

    def test_skip_surfaces_the_reason_and_is_not_a_failure(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        reason = "uses array/multi attribute(s) controlPoints, outSamples"
        txt = CompileDialog._cell_text("verify", "skip", reason)
        # Must read as compiled/skipped, never as a parity FAILURE.
        self.assertNotIn("FAILED", txt)
        self.assertIn("skipped", txt.lower())
        # The reason is surfaced so the user knows WHY it wasn't checked.
        self.assertIn("controlPoints", txt)

    def test_skip_without_reason_still_reads_clean(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        txt = CompileDialog._cell_text("verify", "skip", "")
        self.assertNotIn("FAILED", txt)
        self.assertIn("skipped", txt.lower())

    def test_genuine_parity_mismatch_still_reads_failed(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        txt = CompileDialog._cell_text("verify", "fail", "maxerr=0.5")
        self.assertIn("FAILED parity", txt)
        self.assertIn("0.5", txt)


class TestCompileDialogOfferLoad(unittest.TestCase):
    def _run_offer_load(self, fake, answer_yes, helper_result=None,
                        helper_raises=False):
        from mpynode._base import plugins
        from mpynode.ui.dialogs import compile_dialog as cd

        orig_q = cd.QMessageBox.question
        orig_warn = cd.QMessageBox.warning
        orig_crit = cd.QMessageBox.critical
        orig_helper = plugins.load_or_reload_native_plugin
        warned = {}
        crit = {}

        cd.QMessageBox.question = staticmethod(
            lambda *a, **k: cd.QMessageBox.Yes if answer_yes
            else cd.QMessageBox.No)
        cd.QMessageBox.warning = staticmethod(
            lambda *a, **k: warned.update(msg=a[-1] if a else None))
        cd.QMessageBox.critical = staticmethod(
            lambda *a, **k: crit.update(msg=a[-1] if a else None))

        def _helper(path):
            if helper_raises:
                raise RuntimeError("boom")
            return helper_result

        plugins.load_or_reload_native_plugin = _helper
        try:
            cd.CompileDialog._offer_load(fake, "/out/myPlug.bundle")
        finally:
            cd.QMessageBox.question = orig_q
            cd.QMessageBox.warning = orig_warn
            cd.QMessageBox.critical = orig_crit
            plugins.load_or_reload_native_plugin = orig_helper
        return warned, crit

    def test_offer_load_reloaded(self):
        fake = _FakeSelf()
        self._run_offer_load(
            fake, answer_yes=True,
            helper_result={"base": "myPlug.bundle", "loaded": True,
                           "reloaded": True, "error": None})
        self.assertIn("Reloaded myPlug.bundle", fake._status_label.text)

    def test_offer_load_loaded_fresh(self):
        fake = _FakeSelf()
        self._run_offer_load(
            fake, answer_yes=True,
            helper_result={"base": "myPlug.bundle", "loaded": True,
                           "reloaded": False, "error": None})
        self.assertIn("Loaded myPlug.bundle", fake._status_label.text)

    def test_offer_load_no_means_no_load(self):
        from mpynode._base import plugins

        fake = _FakeSelf()
        called = {"n": 0}
        orig = plugins.load_or_reload_native_plugin
        plugins.load_or_reload_native_plugin = lambda p: called.__setitem__(
            "n", called["n"] + 1)
        try:
            self._run_offer_load(fake, answer_yes=False, helper_result=None)
        finally:
            plugins.load_or_reload_native_plugin = orig
        # On 'No' the helper must never be called.
        self.assertEqual(called["n"], 0)

    def test_offer_load_no_is_not_silent(self):
        """Declining the load must SAY the compiled type is not registered.

        A silent return here reads as an unqualified success while leaving the
        Scene tab's "Convert Node to C++" greyed out with no stated cause --
        the reported patchRelax symptom.
        """
        from mpynode._base import plugins

        fake = _FakeSelf()
        called = {"n": 0}
        orig = plugins.load_or_reload_native_plugin
        plugins.load_or_reload_native_plugin = lambda p: called.__setitem__(
            "n", called["n"] + 1)
        try:
            self._run_offer_load(fake, answer_yes=False, helper_result=None)
        finally:
            plugins.load_or_reload_native_plugin = orig
        # Still never loads -- the consent behaviour is unchanged...
        self.assertEqual(called["n"], 0)
        # ...but it is no longer silent: name the bundle and the consequence.
        joined = "\n".join(fake._appended_logs)
        self.assertIn("myPlug.bundle", joined)
        self.assertIn("Convert Node to C++", joined)

    def test_offer_load_unload_error_surfaced(self):
        fake = _FakeSelf()
        warned, _crit = self._run_offer_load(
            fake, answer_yes=True,
            helper_result={"base": "myPlug.bundle", "loaded": False,
                           "reloaded": False,
                           "error": "has nodes in use in the scene"})
        self.assertTrue(warned.get("msg"), "an unload error must be surfaced")
        self.assertIn("nodes in use", warned["msg"])


class TestCompileDialogNoProgressBar(unittest.TestCase):
    def test_set_busy_does_not_touch_progress_bar(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        # Must not AttributeError on a missing _progress_bar.
        cd.CompileDialog._set_busy(fake, True)
        cd.CompileDialog._set_busy(fake, False)
        self.assertFalse(fake._busy)

    def test_on_progress_main_does_not_touch_progress_bar(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        # A per-node event with n and i set used to drive the bar; the status now
        # flows through _set_status_msg (which the spinner renders), not a raw
        # setText -- so assert the status message was recorded.
        event = {"stage": "port", "node": "foo", "status": "start",
                 "detail": "", "i": 1, "n": 1}
        cd.CompileDialog._on_progress_main(fake, event)  # must not raise
        self.assertTrue(fake._status_msgs)
        self.assertIn("foo", fake._status_msgs[-1])

    def test_on_finished_success_offers_load_without_progress_bar(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        bpath = _real_bundle(self)

        class _Ctrl:
            result = {"ok": True, "bundle_path": bpath,
                      "errors": [], "nodes": [{"build_status": "compiled"}]}

        fake._controller = _Ctrl()
        cd.CompileDialog._on_finished(fake)  # must not touch _progress_bar
        self.assertEqual(fake._offer_load_calls, [bpath])
        self.assertEqual(fake._set_busy_calls, [False])


# ---------------------------------------------------------------------------
# Spinner + collapsible log window (the "something is happening" feedback)
# ---------------------------------------------------------------------------


class _SpinLogFake:
    """Fuller duck-typed self that binds the REAL spinner/log methods, so the
    actual rendering / streaming logic is exercised end-to-end (no Qt window
    needed). ``_spin_timer`` is None -> the methods skip the QTimer start/stop
    and just render synchronously."""

    _METHODS = ("_render_status", "_set_status_msg", "_tick_spinner",
                "_start_spinner", "_stop_spinner", "_append_log", "_clear_log",
                "_show_log", "_toggle_log")

    def __init__(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        self._status_label = _W()
        self._status_msg = ""
        self._spin_running = False
        self._spin_i = 0
        self._spin_timer = None
        self._log_view = _LogW()
        self._log_toggle_btn = _W()
        self._log_shown = False
        # Elapsed-timer origin; None -> the spinner shows no timer (default).
        self._run_start = None
        for m in self._METHODS:
            setattr(self, m, types.MethodType(getattr(C, m), self))


class TestCompileDialogSpinnerLog(unittest.TestCase):
    # ---- wiring (recording stubs on _FakeSelf) ----------------------------

    def test_set_busy_true_starts_spinner_clears_and_opens_log(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        cd.CompileDialog._set_busy(fake, True)
        self.assertEqual(fake._spin_started, 1)
        # Auto-open the log window on compile + start it empty.
        self.assertEqual(fake._clear_log_calls, 1)
        self.assertEqual(fake._show_log_calls[-1], True)

    def test_set_busy_false_stops_spinner(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        cd.CompileDialog._set_busy(fake, False)
        self.assertEqual(fake._spin_stopped, 1)

    def test_log_event_appends_to_log_not_status(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        event = {"stage": "log", "node": "foo", "status": "line",
                 "detail": "clang: compiling foo.cpp", "i": 1, "n": 1}
        cd.CompileDialog._on_progress_main(fake, event)
        # The line goes to the log pane...
        self.assertEqual(fake._appended_logs, ["clang: compiling foo.cpp"])
        # ...and must NOT be written to the status line/spinner.
        self.assertNotIn("clang: compiling foo.cpp", fake._status_msgs)

    def test_non_log_event_updates_status_msg(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        event = {"stage": "assemble", "node": None, "status": "start",
                 "detail": "linking 2 node(s)", "i": 0, "n": 2}
        cd.CompileDialog._on_progress_main(fake, event)
        self.assertEqual(fake._status_msgs[-1], "linking 2 node(s)")
        # High-level narration (a human line, NOT the raw streamed compiler
        # output) is now mirrored to the log so it reads as a build story.
        self.assertEqual(fake._appended_logs, ["Linking native plugin..."])

    # ---- real spinner rendering -------------------------------------------

    def test_tick_spinner_prepends_a_braille_frame(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _SpinLogFake()
        fake._status_msg = "Porting"
        fake._spin_running = True
        fake._spin_i = 0
        fake._tick_spinner()
        text = fake._status_label.text
        self.assertIn("Porting", text)
        self.assertIn(text[0], cd._SPIN_FRAMES)

    def test_tick_spinner_advances_frame(self):
        fake = _SpinLogFake()
        fake._status_msg = "x"
        fake._spin_running = True
        fake._spin_i = 0
        fake._tick_spinner()
        first = fake._status_label.text[0]
        fake._tick_spinner()
        second = fake._status_label.text[0]
        self.assertNotEqual(first, second)

    def test_render_status_has_no_frame_when_not_spinning(self):
        fake = _SpinLogFake()
        fake._spin_running = False
        fake._set_status_msg("Built ok")
        self.assertEqual(fake._status_label.text, "Built ok")

    def test_start_then_stop_spinner_leaves_plain_message(self):
        fake = _SpinLogFake()
        fake._set_status_msg("Compiling 3 node(s)…")
        fake._start_spinner()
        # While spinning the label carries a frame prefix.
        self.assertTrue(fake._status_label.text.endswith("Compiling 3 node(s)…"))
        self.assertNotEqual(fake._status_label.text, "Compiling 3 node(s)…")
        fake._stop_spinner()
        # Stopped: just the message, no frame.
        self.assertEqual(fake._status_label.text, "Compiling 3 node(s)…")

    # ---- real log pane behaviour ------------------------------------------

    def test_append_log_writes_to_log_view(self):
        fake = _SpinLogFake()
        fake._append_log("clang: linking")
        self.assertEqual(fake._log_view.lines, ["clang: linking"])

    def test_clear_log_clears_the_view(self):
        fake = _SpinLogFake()
        fake._append_log("old line")
        fake._clear_log()
        self.assertEqual(fake._log_view.lines, [])
        self.assertEqual(fake._log_view.cleared, 1)

    def test_show_log_toggles_visibility_and_arrow(self):
        fake = _SpinLogFake()
        fake._show_log(True)
        self.assertTrue(fake._log_view.isVisible())
        self.assertIn("▾", fake._log_toggle_btn.text)  # expanded marker
        fake._show_log(False)
        self.assertFalse(fake._log_view.isVisible())
        self.assertIn("▸", fake._log_toggle_btn.text)  # collapsed marker

    def test_toggle_log_flips_state(self):
        fake = _SpinLogFake()
        fake._log_shown = False
        fake._toggle_log()
        self.assertTrue(fake._log_shown)
        self.assertTrue(fake._log_view.isVisible())
        fake._toggle_log()
        self.assertFalse(fake._log_shown)
        self.assertFalse(fake._log_view.isVisible())

    def test_render_status_guards_none_label(self):
        # A pending QTimer tick can fire after the dialog is torn down; a None
        # _status_label must NOT raise (the spinner runs on the GUI thread but
        # the widget may already be gone on close).
        fake = _SpinLogFake()
        fake._status_label = None
        fake._spin_running = True
        fake._status_msg = "Porting"
        fake._render_status()  # must not raise
        fake._tick_spinner()   # must not raise either

    def test_close_event_stops_the_spinner(self):
        # Closing the dialog mid-compile must halt the QTimer (else it keeps
        # ticking on a hidden/torn-down reused dialog). Source-level assertion
        # (constructing+closing a real QDialog under headless mayapy is flaky).
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog.closeEvent)
        self.assertIn("_stop_spinner", src)


class TestCompileLogWrapping(unittest.TestCase):
    """A log line longer than the pane restarted at column 0, so the remainder
    of "  [AI-optimize] round 2/4 trying: ..." read as a new, prefix-less entry.
    The wrap keeps a wrapped block reading as ONE entry -- without reflowing
    ordinary output or breaking a path in half."""

    _LONG = ("  [AI-optimize] round 2/4 trying: vectorise the argmin over the "
             "neighbour list (predicted 3.00x, risk: medium)")

    def test_a_line_inside_the_width_comes_back_byte_identical(self):
        from mpynode.ui.dialogs.compile_dialog import _wrap_log_line

        line = "  [AI-optimize] round 2/4 trying: vectorise"
        self.assertEqual(_wrap_log_line(line), line)

    def test_an_over_long_line_is_wrapped_at_the_pane_width(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self.assertGreater(len(self._LONG), cd._LOG_WRAP_COLS)
        parts = cd._wrap_log_line(self._LONG).split("\n")

        self.assertGreater(len(parts), 1)
        for p in parts:
            self.assertLessEqual(len(p), cd._LOG_WRAP_COLS, p)

    def test_a_continuation_is_indented_one_step_past_its_own_header(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        parts = cd._wrap_log_line(self._LONG).split("\n")
        head = self._LONG[:len(self._LONG) - len(self._LONG.lstrip(" "))]

        self.assertTrue(parts[0].startswith(head))
        for p in parts[1:]:
            self.assertTrue(p.startswith(head + cd._LOG_WRAP_INDENT),
                            "a continuation restarting at the header's own "
                            "column reads as a new entry: %r" % p)

    def test_one_over_long_token_is_never_split(self):
        """A path or an identifier must stay copy-pasteable."""
        from mpynode.ui.dialogs.compile_dialog import _wrap_log_line

        token = "/very/long/path/" + ("x" * 120)
        self.assertIn(token, _wrap_log_line("  " + token))

    def test_every_line_reaches_the_pane_through_the_wrap(self):
        """One point, not one per emitter -- the wrap is only worth anything if
        _append_log applies it."""
        fake = _SpinLogFake()
        fake._append_log(self._LONG)

        self.assertIn("\n", fake._log_view.lines[0],
                      "the raw over-long line went straight to the pane")


class TestCompileDialogLogBuildUI(unittest.TestCase):
    """The log pane + toggle must actually be built and wired (source-level, so
    no real QDialog construction is needed under headless mayapy)."""

    def test_build_ui_creates_log_view_and_toggle(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("_log_view", src)
        self.assertIn("QPlainTextEdit", src)
        self.assertIn("_log_toggle_btn", src)

    def test_log_starts_hidden_collapsed(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        # Collapsible: idle dialog hides the log pane (auto-opens on compile).
        self.assertIn("setVisible(False)", src.replace(" ", ""))

    def test_toggle_is_wired(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._wire_signals)
        self.assertIn("_toggle_log", src)

    def test_spin_timer_wired_to_tick(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("QTimer", src)
        self.assertIn("_tick_spinner", src)


class TestCheckboxColumnTightFit(unittest.TestCase):
    """The per-row checkbox column (col 0) must hug its checkbox on every
    platform. On Windows the header's style-derived default minimumSectionSize
    (~36-37px) is much larger than a checkbox cell's content (~18-22px), so the
    ResizeToContents column is clamped UP -- leaving an empty, focus-selectable
    strip between the checkbox and the Node column (cosmetic; macOS's smaller
    default hides it). ``_build_ui`` lowers the per-header floor MONOTONICALLY so
    col 0 can finally shrink to its content on Windows the way it already does
    on macOS -- and, being a one-directional lower, never widens macOS.
    """

    def test_cap_constant_is_below_a_checkbox_indicator(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Must sit BELOW a real checkbox's content width (~16-22px) so the cap
        # never itself clamps col 0 wide; and be positive.
        self.assertGreater(cd._CHECKBOX_COL_MIN_PX, 0)
        self.assertLessEqual(cd._CHECKBOX_COL_MIN_PX, 16)

    def test_min_section_size_only_ever_lowers(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        cap = cd._CHECKBOX_COL_MIN_PX
        # Windows-like large default -> lowered to the cap.
        self.assertEqual(cd._checkbox_min_section_size(36), cap)
        # macOS-like small default -> left untouched (no regression).
        self.assertEqual(cd._checkbox_min_section_size(8), 8)
        # Exactly at the cap -> unchanged (idempotent).
        self.assertEqual(cd._checkbox_min_section_size(cap), cap)

    def test_build_ui_lowers_header_minimum_section_size(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("setMinimumSectionSize", src)
        self.assertIn("_checkbox_min_section_size", src)


class TestCompileDialogFinishSummary(unittest.TestCase):
    """On finish the compile log gets a clear 'done + elapsed + generated files'
    block set off by a separator rule; while compiling the spinner shows a small
    elapsed timer next to the animated frame."""

    # ---- _format_elapsed (pure) -------------------------------------------
    def test_format_elapsed_basic(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self.assertEqual(cd._format_elapsed(0), "0:00")
        self.assertEqual(cd._format_elapsed(7), "0:07")
        self.assertEqual(cd._format_elapsed(83), "1:23")
        self.assertEqual(cd._format_elapsed(725), "12:05")

    def test_format_elapsed_none_or_negative_is_blank(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self.assertEqual(cd._format_elapsed(None), "")
        self.assertEqual(cd._format_elapsed(-3), "")

    # ---- _summary_lines (pure) --------------------------------------------
    def test_summary_success_has_done_time_files_and_rule(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        lines = cd._summary_lines(
            True, "0:12", "myPlug", "/out/myPlug.bundle",
            "/out/myPlug.manifest.json", ["/out/aNode.cpp"],
            ["aNode (compiled)"], [])
        blob = "\n".join(lines)
        self.assertIn("0:12", blob)               # how long it took
        self.assertIn("Compiled", blob)           # clear "done"
        self.assertIn("/out/myPlug.bundle", blob)  # generated file + location
        self.assertIn("/out/myPlug.manifest.json", blob)
        self.assertIn("/out/aNode.cpp", blob)
        self.assertIn("aNode (compiled)", blob)
        self.assertIn(cd._SUMMARY_RULE, lines)     # clean separator

    def test_summary_failure_shows_time_and_errors(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        lines = cd._summary_lines(
            False, "0:05", "myPlug", None, None, [], [],
            ["assemble: boom", "dropped: aNode"])
        blob = "\n".join(lines)
        self.assertIn("0:05", blob)
        self.assertIn("failed", blob.lower())
        self.assertIn("boom", blob)
        self.assertIn("dropped: aNode", blob)
        self.assertIn(cd._SUMMARY_RULE, lines)

    def test_summary_success_without_time_omits_in_clause(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        lines = cd._summary_lines(
            True, "", "myPlug", "/out/p.bundle", None, [], [], [])
        blob = "\n".join(lines)
        self.assertIn("Compiled", blob)
        self.assertNotIn("Compiled in ", blob)  # no dangling empty time

    def test_summary_success_renders_warnings(self):
        # A build that dropped a node or a command set is still ok=True -- those
        # non-fatal errors must be VISIBLE in the success summary.
        from mpynode.ui.dialogs import compile_dialog as cd

        lines = cd._summary_lines(
            True, "0:03", "myPlug", "/out/p.bundle", None, [], [], [],
            warning_lines=["companion: dup clash", "dropped: badNode"])
        blob = "\n".join(lines)
        self.assertIn("Compiled", blob)
        self.assertIn("companion: dup clash", blob)
        self.assertIn("dropped: badNode", blob)
        self.assertIn("Warning", blob)  # rendered under a distinct label

    def test_on_finished_success_surfaces_companion_errors(self):
        # When the bundle links but a companion command set fails to ship
        # (ok=True with a "companion:" error), the user must SEE it: in the
        # summary AND a modal. The success path used to pass [] for errors.
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        fake._run_start = None
        bpath = _real_bundle(self)

        class _Ctrl:
            result = {"ok": True, "bundle_path": bpath,
                      "manifest_path": None, "plugin_name": "myPlug",
                      "errors": ["companion: command name 'dup' is defined on "
                                 "both 'A' and 'B'"],
                      "nodes": [{"type_name": "A", "build_status": "compiled"}]}

        fake._controller = _Ctrl()
        warned = {}
        orig_warn = cd.QMessageBox.warning
        cd.QMessageBox.warning = staticmethod(
            lambda *a, **k: warned.update(msg=a[-1] if a else ""))
        try:
            cd.CompileDialog._on_finished(fake)
        finally:
            cd.QMessageBox.warning = orig_warn
        blob = "\n".join(fake._appended_logs)
        self.assertIn("dup", blob)            # surfaced in the summary
        self.assertTrue(warned.get("msg"))    # and a modal popped
        self.assertIn("dup", warned["msg"])
        # The build still succeeded -> it still offered to load the bundle.
        self.assertEqual(fake._offer_load_calls, [bpath])

    def test_on_finished_ai_optimize_failure_still_offers_the_linked_bundle(self):
        """``ok=False`` can mean ONLY that the AI optimize step delivered
        nothing -- the bundle LINKED. Presenting that as a flat "Compile
        failed" hid a real, loadable artifact sitting on disk, so the run takes
        the built branch with the AI failure carried as the warning it is."""
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        fake._run_start = None
        bpath = _real_bundle(self)
        why = ("AI optimize was requested but produced no candidate for any of "
               "the 2 node(s) attempted (1 blocked: nodeA). First failure: "
               "AgentUnavailable: sandbox_apply")

        class _Ctrl:
            result = {"ok": False, "bundle_path": bpath,
                      "manifest_path": None, "plugin_name": "myPlug",
                      "ai_optimize_failed": why, "errors": [why],
                      "nodes": [{"type_name": "A", "build_status": "compiled"}]}

        fake._controller = _Ctrl()
        warned = {}
        orig_warn = cd.QMessageBox.warning
        cd.QMessageBox.warning = staticmethod(
            lambda *a, **k: warned.update(title=a[1] if len(a) > 1 else "",
                                          msg=a[-1] if a else ""))
        try:
            cd.CompileDialog._on_finished(fake)
        finally:
            cd.QMessageBox.warning = orig_warn

        blob = "\n".join(fake._appended_logs)
        self.assertNotIn("Compile failed", blob)
        # Told BOTH halves: the AI step failed, and the plugin is loadable.
        self.assertIn("AI optimize FAILED", blob)
        self.assertIn("sandbox_apply", blob)
        self.assertIn("can be loaded", blob)
        self.assertEqual(fake._offer_load_calls, [bpath],
                         "a linked bundle was withheld over an AI failure")
        self.assertNotIn("Compile failed", fake._status_msg)
        self.assertIn("AI optimize FAILED", fake._status_msg)
        self.assertTrue(warned.get("msg"))
        self.assertIn("AI optimize", warned["title"])

    def _multi_result(self, sub, root="/tmp/nd_fake_maya"):
        """A multi-version controller result carrying one version's sub-result."""
        return {"ok": bool(sub.get("ok")), "multi": True,
                "plugin_name": "myPlug", "errors": [],
                "results": [{"label": "maya2026", "root": root,
                             "out_dir": "/tmp/nd_fake_out", "result": sub}]}

    def _run_multi(self, fake, result, root="/tmp/nd_fake_maya"):
        """Drive the REAL _on_finished through the multi branch, with the
        running Maya resolving to ``root`` so the load offer is reachable."""
        from mpynode.ui.dialogs import compile_dialog as cd

        class _Ctrl:
            pass

        _Ctrl.result = result
        fake._controller = _Ctrl()
        # Bind the REAL multi handler so _on_finished's dispatch is covered too.
        fake._on_finished_multi = (
            lambda *a: cd.CompileDialog._on_finished_multi(fake, *a))
        orig_warn = cd.QMessageBox.warning
        orig_resolve = cd._resolve_maya_dir
        warned = {}
        cd.QMessageBox.warning = staticmethod(
            lambda *a, **k: warned.update(title=a[1] if len(a) > 1 else "",
                                          msg=a[-1] if a else ""))
        cd._resolve_maya_dir = staticmethod(lambda *a, **k: root)
        try:
            cd.CompileDialog._on_finished(fake)
        finally:
            cd.QMessageBox.warning = orig_warn
            cd._resolve_maya_dir = orig_resolve
        return warned

    def test_on_finished_multi_ai_failure_still_offers_the_linked_bundle(self):
        """Same defect as the single-build path, on the per-VERSION path: a
        sub-result can carry ``ok=False`` for the sole reason that AI optimize
        delivered nothing, while that version's bundle LINKED and is on disk
        (``compile_plugin_multi`` forwards ``optimize`` to each per-version
        ``compile_plugin``). Reporting it as a flat FAILED hid a loadable
        artifact and never offered it."""
        fake = _FakeSelf()
        fake._run_start = None
        bpath = _real_bundle(self)
        why = ("AI optimize was requested but produced no candidate for any of "
               "the 2 node(s) attempted (1 blocked: nodeA)")
        sub = {"ok": False, "bundle_path": bpath, "manifest_path": None,
               "plugin_name": "myPlug", "ai_optimize_failed": why,
               "errors": [why], "nodes": []}

        warned = self._run_multi(fake, self._multi_result(sub))

        blob = "\n".join(fake._appended_logs)
        self.assertIn("Built 1/1 Maya version(s)", blob,
                      "the linked version was counted as a failure")
        # It is being OFFERED to load, so it must not also be named in a
        # "these versions failed to build" modal.
        self.assertNotIn("Compile Failed", warned.get("title") or "")
        self.assertIn(bpath, blob, "the linked bundle's path was never shown")
        self.assertIn("AI optimize FAILED", blob)
        self.assertEqual(fake._offer_load_calls, [bpath],
                         "a linked bundle was withheld over an AI failure")

    def test_on_finished_multi_a_real_failure_is_still_a_failure(self):
        """The special case must not swallow a version that actually broke: no
        ``ai_optimize_failed`` key means that version stays FAILED, is never
        offered, and still raises the modal."""
        fake = _FakeSelf()
        fake._run_start = None
        bpath = _real_bundle(self)
        sub = {"ok": False, "bundle_path": bpath, "manifest_path": None,
               "plugin_name": "myPlug", "errors": ["link error: undefined"],
               "nodes": []}

        warned = self._run_multi(fake, self._multi_result(sub))

        blob = "\n".join(fake._appended_logs)
        self.assertIn("Built 0/1 Maya version(s)", blob)
        self.assertIn("FAILED", blob)
        self.assertEqual(fake._offer_load_calls, [])
        self.assertIn("maya2026", warned.get("msg") or "")

    def test_on_finished_a_real_failure_is_still_a_failure(self):
        """The special case must not swallow a build that actually broke: no
        ``ai_optimize_failed`` key means the failure branch, unchanged."""
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        fake._run_start = None
        bpath = _real_bundle(self)

        class _Ctrl:
            result = {"ok": False, "bundle_path": bpath,
                      "manifest_path": None, "plugin_name": "myPlug",
                      "errors": ["link error: undefined symbol"],
                      "nodes": [{"type_name": "A", "build_status": "dropped"}]}

        fake._controller = _Ctrl()
        orig_warn = cd.QMessageBox.warning
        cd.QMessageBox.warning = staticmethod(lambda *a, **k: None)
        try:
            cd.CompileDialog._on_finished(fake)
        finally:
            cd.QMessageBox.warning = orig_warn

        self.assertIn("Compile failed", "\n".join(fake._appended_logs))
        self.assertEqual(fake._offer_load_calls, [])

    # ---- _generated_sources (filesystem) ----------------------------------
    def test_generated_sources_lists_existing_cpp_only(self):
        import tempfile

        from mpynode.ui.dialogs import compile_dialog as cd

        d = tempfile.mkdtemp()
        # Assembled sources live under build/source/ now.
        src_dir = os.path.join(d, "build", "source")
        os.makedirs(src_dir)
        for nm in ("aNode.cpp", "bNode.cpp"):
            with open(os.path.join(src_dir, nm), "w") as fh:
                fh.write("// x\n")
        rows = [{"type_name": "aNode"}, {"type_name": "bNode"},
                {"type_name": "missing"}, {"build_status": "compiled"}]
        got = cd._generated_sources(d, rows)
        self.assertEqual(got, [os.path.join(src_dir, "aNode.cpp"),
                               os.path.join(src_dir, "bNode.cpp")])

    # ---- elapsed timer next to the spinner (real _render_status) ----------
    def test_render_status_shows_elapsed_next_to_frame_while_spinning(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _SpinLogFake()
        fake._run_start = 100.0
        fake._spin_running = True
        fake._spin_i = 0
        fake._status_msg = "Porting"
        orig_now = cd._now
        cd._now = lambda: 107.0
        try:
            fake._render_status()
        finally:
            cd._now = orig_now
        text = fake._status_label.text
        self.assertIn("0:07", text)               # the little timer
        self.assertIn("Porting", text)            # the message
        self.assertIn(text[0], cd._SPIN_FRAMES)   # still the animated icon

    def test_render_status_no_timer_when_no_run_start(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _SpinLogFake()
        fake._run_start = None
        fake._spin_running = True
        fake._spin_i = 0
        fake._status_msg = "x"
        fake._render_status()
        self.assertTrue(fake._status_label.text.endswith("x"))
        self.assertNotIn(":", fake._status_label.text)  # no time component

    # ---- _set_busy records the run start ----------------------------------
    def test_set_busy_true_records_run_start(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        orig_now = cd._now
        cd._now = lambda: 555.0
        try:
            cd.CompileDialog._set_busy(fake, True)
        finally:
            cd._now = orig_now
        self.assertEqual(fake._run_start, 555.0)

    # ---- _on_finished appends the summary block to the log ----------------
    def test_on_finished_appends_summary_block_to_log(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        fake._run_start = None
        bpath = _real_bundle(self)

        class _Ctrl:
            result = {"ok": True, "bundle_path": bpath,
                      "manifest_path": "/out/myPlug.manifest.json",
                      "plugin_name": "myPlug", "errors": [],
                      "nodes": [{"type_name": "aNode",
                                 "build_status": "compiled"}]}

        fake._controller = _Ctrl()
        cd.CompileDialog._on_finished(fake)
        blob = "\n".join(fake._appended_logs)
        self.assertIn("Compiled", blob)
        self.assertIn(bpath, blob)
        self.assertIn("aNode", blob)
        # And it still offered to load the built bundle.
        self.assertEqual(fake._offer_load_calls, [bpath])


class _TextW:
    """Fake QLineEdit returning a fixed text() string."""

    def __init__(self, t=""):
        self._t = t

    def text(self):
        return self._t

    def setText(self, t):
        self._t = t


class _AddMpnFake:
    """Duck-typed self for _on_add_mpn (binds the real _unique_row_name)."""

    def __init__(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        self._busy = False
        self._out_edit = _TextW("/tmp")
        self._file_rows = {}
        self._checked = set()
        self._scene_nodes = []
        self._refresh_calls = 0
        self._unique_row_name = types.MethodType(C._unique_row_name, self)

    def _refresh_table(self):
        self._refresh_calls += 1


class TestCompileDialogExternalMpn(unittest.TestCase):
    """(F) Add external .mpn files to the compile list (no scene node) + the
    'Ignore persistent data' compile toggle."""

    # ---- source-level wiring (matches the file's _on_compile idiom) -------
    def test_build_ui_has_add_mpn_button_and_ignore_checkbox(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("Add .mpn files", src)
        self.assertIn("_add_mpn_btn", src)
        self.assertIn("Ignore persistent data", src)
        self.assertIn("_ignore_persistent_check", src)

    def test_wire_signals_connects_add_mpn(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._wire_signals)
        self.assertIn("_on_add_mpn", src)

    def test_on_compile_branches_on_file_rows(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        # File rows go through the pure adapter; scene rows still use extract_spec.
        self.assertIn("_file_rows", src)
        self.assertIn("spec_from_mpn_payload", src)
        self.assertIn("extract_spec", src)

    def test_on_compile_threads_bake_persistent(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        # The global "Ignore persistent data" toggle is read via the helper and
        # threaded into the engine's bake_persistent default.
        self.assertIn("_global_ignore_persistent", src)
        self.assertIn("bake_persistent", src)

    def test_refresh_table_merges_file_rows(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._refresh_table)
        self.assertIn("_file_rows", src)

    # ---- behavioral ------------------------------------------------------
    def test_set_busy_locks_add_mpn_and_ignore(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        cd.CompileDialog._set_busy(fake, True)
        self.assertIs(fake._add_mpn_btn.enabled, False)
        self.assertIs(fake._ignore_persistent_check.enabled, False)
        cd.CompileDialog._set_busy(fake, False)
        self.assertIs(fake._add_mpn_btn.enabled, True)
        self.assertIs(fake._ignore_persistent_check.enabled, True)

    def test_on_add_mpn_registers_file_row_and_checks_it(self):
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode._common.io import mpn_io

        fake = _AddMpnFake()
        orig_dlg = cd.QFileDialog.getOpenFileNames
        cd.QFileDialog.getOpenFileNames = staticmethod(
            lambda *a, **k: (["/x/libNode.mpn"], ""))
        try:
            with mock.patch.object(
                    mpn_io, "load_mpn",
                    return_value={"native_type": "mPyNode",
                                  "source_name": "libNode"}):
                cd.CompileDialog._on_add_mpn(fake)
        finally:
            cd.QFileDialog.getOpenFileNames = orig_dlg

        self.assertIn("libNode", fake._file_rows)
        self.assertEqual(fake._file_rows["libNode"][0], "/x/libNode.mpn")
        self.assertIn("libNode", fake._checked)
        self.assertEqual(fake._refresh_calls, 1)

    def test_unique_row_name_disambiguates(self):
        fake = _AddMpnFake()
        fake._scene_nodes = [("foo", "mPyNode")]
        self.assertEqual(fake._unique_row_name("bar"), "bar")
        self.assertEqual(fake._unique_row_name("foo"), "foo (2)")

    def test_on_add_mpn_skips_duplicate_node_identity(self):
        # Two different .mpn files that define the SAME node (identity = sanitized
        # node_type_name, what the bundle keys on) -> only ONE row is added; the
        # duplicate is skipped (this also covers re-adding the SAME file twice).
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        fake = _AddMpnFake()
        orig_dlg = cd.QFileDialog.getOpenFileNames
        cd.QFileDialog.getOpenFileNames = staticmethod(
            lambda *a, **k: (["/x/foo.mpn", "/y/foo.mpn"], ""))
        try:
            with mock.patch.object(
                    mpn_io, "load_mpn",
                    side_effect=lambda p, **k: {"native_type": "mPyNode",
                                                "source_name": "foo"}), \
                 mock.patch.object(
                    mpn_spec_adapter, "spec_from_mpn_payload",
                    side_effect=lambda d: {"suggested": {
                        "node_type_name": d["source_name"]}, "variables": {}}), \
                 mock.patch.object(cd, "QMessageBox"):
                cd.CompileDialog._on_add_mpn(fake)
        finally:
            cd.QFileDialog.getOpenFileNames = orig_dlg

        self.assertEqual(len(fake._file_rows), 1)
        self.assertIn("foo", fake._file_rows)

    def test_on_add_mpn_skips_adapter_failure(self):
        # A .mpn that LOADS but fails to ADAPT (corrupted/hand-edited) must be
        # warned + skipped, NOT added as an auto-checked row that later aborts
        # the whole compile (review finding #6).
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        fake = _AddMpnFake()
        orig_dlg = cd.QFileDialog.getOpenFileNames
        cd.QFileDialog.getOpenFileNames = staticmethod(
            lambda *a, **k: (["/x/bad.mpn"], ""))
        try:
            with mock.patch.object(
                    mpn_io, "load_mpn",
                    side_effect=lambda p, **k: {"native_type": "mPyNode",
                                                "source_name": "bad"}), \
                 mock.patch.object(mpn_spec_adapter, "spec_from_mpn_payload",
                                   side_effect=ValueError("corrupt")), \
                 mock.patch.object(cd, "QMessageBox"):
                cd.CompileDialog._on_add_mpn(fake)
        finally:
            cd.QFileDialog.getOpenFileNames = orig_dlg

        self.assertEqual(fake._file_rows, {})     # not added
        self.assertEqual(fake._checked, set())    # not checked
        self.assertEqual(fake._refresh_calls, 0)  # nothing added -> no refresh

    def test_on_add_mpn_caches_has_persistent_on_row(self):
        # The row tuple carries (path, native_type, has_persistent, node_type) so
        # the Persistent column can show the at-a-glance indicator without re-
        # reading the file. A payload with stored_vars -> has_persistent True.
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        fake = _AddMpnFake()
        orig_dlg = cd.QFileDialog.getOpenFileNames
        cd.QFileDialog.getOpenFileNames = staticmethod(
            lambda *a, **k: (["/x/foo.mpn"], ""))
        try:
            with mock.patch.object(
                    mpn_io, "load_mpn",
                    side_effect=lambda p, **k: {
                        "native_type": "mPyNode", "source_name": "foo",
                        "stored_vars": {"a": 1}}), \
                 mock.patch.object(
                    mpn_spec_adapter, "spec_from_mpn_payload",
                    side_effect=lambda d: {"suggested": {
                        "node_type_name": "foo"}, "variables": {"a": {}}}):
                cd.CompileDialog._on_add_mpn(fake)
        finally:
            cd.QFileDialog.getOpenFileNames = orig_dlg

        val = fake._file_rows["foo"]
        self.assertEqual(val[0], "/x/foo.mpn")
        self.assertIs(val[2], True)        # has_persistent
        self.assertEqual(val[3], "foo")    # node_type identity

    def test_on_add_mpn_reads_new_node_name_key(self):
        # New-key .mpn payloads carry ``node_name`` (the old key was
        # ``source_name``); the row must take its display name from node_name,
        # not fall back to the file stem.
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        fake = _AddMpnFake()
        orig_dlg = cd.QFileDialog.getOpenFileNames
        cd.QFileDialog.getOpenFileNames = staticmethod(
            lambda *a, **k: (["/x/whatever.mpn"], ""))
        try:
            with mock.patch.object(
                    mpn_io, "load_mpn",
                    side_effect=lambda p, **k: {
                        "native_type": "mPyNode", "node_name": "wheelNode"}), \
                 mock.patch.object(
                    mpn_spec_adapter, "spec_from_mpn_payload",
                    side_effect=lambda d: {"suggested": {
                        "node_type_name": "wheel"}, "variables": {}}):
                cd.CompileDialog._on_add_mpn(fake)
        finally:
            cd.QFileDialog.getOpenFileNames = orig_dlg

        # Keyed by the node_name (NOT "whatever", the file stem).
        self.assertIn("wheelNode", fake._file_rows)

    # ---- review fix HIGH: never bypass the pickle-trust gate in the UI ----
    def test_on_add_mpn_uses_trust_prompt_not_forced_trusted(self):
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode._common.io import mpn_io

        fake = _AddMpnFake()
        captured = {}

        def cap_load(p, **k):
            captured.update(k)
            return {"native_type": "mPyNode", "source_name": "libNode"}

        orig_dlg = cd.QFileDialog.getOpenFileNames
        cd.QFileDialog.getOpenFileNames = staticmethod(
            lambda *a, **k: (["/x/libNode.mpn"], ""))
        try:
            with mock.patch.object(mpn_io, "load_mpn", side_effect=cap_load):
                cd.CompileDialog._on_add_mpn(fake)
        finally:
            cd.QFileDialog.getOpenFileNames = orig_dlg

        # A .mpn can carry pickled stored vars -> the UI must gate the decode
        # behind the trust prompt, NOT force trusted=True (RCE bypass).
        self.assertIsNot(captured.get("trusted"), True)
        self.assertTrue(callable(captured.get("prompt_fn")))

    def test_on_compile_does_not_force_trusted_true(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertNotIn("trusted=True", src)
        self.assertIn("_mpn_trust_prompt", src)

    # ---- review fix MEDIUM: file row vs later-created same-named scene node -
    def test_disambiguate_file_rows_renames_scene_collision(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        rows = {"foo": ("/x/foo.mpn", "mPyNode")}
        new_rows, new_checked, _persist = C._disambiguate_file_rows(
            rows, {"foo"}, set(), {"foo"})
        self.assertNotIn("foo", new_rows)
        self.assertIn("foo (2)", new_rows)
        self.assertEqual(new_rows["foo (2)"], ("/x/foo.mpn", "mPyNode"))
        self.assertIn("foo (2)", new_checked)
        self.assertNotIn("foo", new_checked)

    def test_disambiguate_file_rows_no_collision_unchanged(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        rows = {"bar": ("/x/bar.mpn", "mPyNode")}
        new_rows, new_checked, new_persist = C._disambiguate_file_rows(
            rows, {"bar"}, {"bar"}, {"foo"})
        self.assertEqual(new_rows, rows)
        self.assertEqual(new_checked, {"bar"})
        self.assertEqual(new_persist, {"bar"})

    def test_disambiguate_file_rows_remaps_persistent_unchecked(self):
        # A per-node persistent UNCHECK must follow the row across a rename so it
        # never attaches to an unrelated node that later takes the freed name
        # (the silent data-loss class the review flagged).
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        rows = {"foo": ("/x/foo.mpn", "mPyNode")}
        _r, _c, new_persist = C._disambiguate_file_rows(
            rows, {"foo"}, {"foo"}, {"foo"})  # scene 'foo' collides -> rename
        self.assertIn("foo (2)", new_persist)
        self.assertNotIn("foo", new_persist)

    def test_refresh_table_redisambiguates_file_rows(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._refresh_table)
        self.assertIn("_disambiguate_file_rows", src)

    # ---- review fix LOW: file rows must not leak across scene opens -------
    def test_refresh_nodes_resets_file_rows(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        class _F:
            pass

        fake = _F()
        fake._busy = False
        fake._checked = {"a"}
        fake._row_by_type = {"t": 0}
        fake._file_rows = {"x": ("/x.mpn", "mPyNode")}
        fake._refresh_table = lambda: None
        C.refresh_nodes(fake)
        self.assertEqual(fake._file_rows, {})
        self.assertEqual(fake._checked, set())


class TestMultiVersionCompileDialog(unittest.TestCase):
    """Multi-version target selection + the per-version / high-level log
    narration in the Compile dialog."""

    # ---- pure helpers ----------------------------------------------------
    def test_narration_line_mapping(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        # Raw compiler/porter lines are appended verbatim elsewhere -> no mirror.
        self.assertIsNone(C._narration_line("log", "line", "n", "x"))
        self.assertIn("maya2024", C._narration_line(
            "version", "start", "maya2024", "Compiling maya2024 (1/2)", 0, 2))
        # cache miss narrates the "generating / sending to AI" story the user
        # asked for; cache hit says it reused the cache (no AI).
        self.assertIn("sending to AI",
                      C._narration_line("cache", "miss", "nodeX", ""))
        self.assertIn("cache", C._narration_line(
            "cache", "hit", "nodeX", "").lower())
        self.assertIn("Linking",
                      C._narration_line("assemble", "start", None, ""))
        self.assertIn("Parity",
                      C._narration_line("verify", "start", None, ""))

    def test_optimize_stage_surfaces_detail_not_fixed_string(self):
        # The AI-optimizer narration used to be emitted as ("port","ok"), which
        # the formatter collapses to one opaque line for EVERY message -> a log
        # flood. It now gets its own "optimize" stage whose line surfaces the
        # detail (baseline ms, speedup, kept-original reason, skip reason).
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        info = C._narration_line("optimize", "info",
                                 None, "metaClay baseline 117.4 ms")
        self.assertIsNotNone(info)
        self.assertIn("117.4", info)
        self.assertNotIn("AI port compiled OK", info)

        ok = C._narration_line("optimize", "ok", None, "metaClay: 2.30x faster")
        self.assertIn("2.30x", ok)

        skip = C._narration_line("optimize", "skip", None,
                                 "mPyFile skipped: VP2 override")
        self.assertIn("VP2", skip)

        # An empty detail says nothing (no blank line spam).
        self.assertIsNone(C._narration_line("optimize", "info", None, ""))

    def test_default_checked_labels(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        installs = [{"label": "maya2024", "root": "/m/2024"},
                    {"label": "maya2026", "root": "/m/2026"}]
        # Running Maya pre-checked.
        self.assertEqual(C._default_checked_labels(installs, "/m/2026"),
                         ["maya2026"])
        # Running not among installs -> highest version (installs are sorted).
        self.assertEqual(C._default_checked_labels(installs, "/nope"),
                         ["maya2026"])
        self.assertEqual(C._default_checked_labels([], "/m/2026"), [])

    def test_checked_targets(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        class _CB:
            def __init__(self, c):
                self._c = c

            def isChecked(self):
                return self._c

        class _F:
            pass

        fake = _F()
        fake._maya_targets = [{"label": "maya2024", "root": "/m/2024"},
                              {"label": "maya2026", "root": "/m/2026"}]
        fake._maya_checks = {"maya2024": _CB(False), "maya2026": _CB(True)}
        got = C._checked_targets(fake)
        self.assertEqual([t["label"] for t in got], ["maya2026"])

    # ---- source-level wiring --------------------------------------------
    def test_build_ui_discovers_versions(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("discover_maya_installs", src)
        self.assertIn("Maya versions", src)
        self.assertIn("_maya_checks", src)

    def test_build_ui_version_list_scrollable_with_select_all(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Many installed versions must not widen / overflow the dialog: the
        # version list is a height-capped scroll area with Select All / None.
        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("QScrollArea", src)
        self.assertIn("_ver_all_btn", src)
        self.assertIn("_set_all_versions", src)

    def test_on_compile_branches_multi_vs_single(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn("_checked_targets", src)
        self.assertIn("start_multi", src)
        self.assertIn("verify_fn_for", src)
        self.assertIn("subprocess_verify_fn", src)

    def test_on_progress_narrates_and_handles_version(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_progress_main)
        self.assertIn("_narration_line", src)
        self.assertIn("version", src)

    def test_on_finished_handles_multi(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_finished)
        self.assertIn("multi", src)

    # ---- behavioral ------------------------------------------------------
    def test_set_busy_locks_version_checks(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        cb = _W()
        fake._maya_checks = {"maya2026": cb}
        cd.CompileDialog._set_busy(fake, True)
        self.assertIs(cb.enabled, False)
        cd.CompileDialog._set_busy(fake, False)
        self.assertIs(cb.enabled, True)

    def test_set_all_versions_toggles(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        class _CBSet:
            def __init__(self, c):
                self.c = c

            def setChecked(self, v):
                self.c = bool(v)

            def isChecked(self):
                return self.c

        fake = _FakeSelf()
        a, b = _CBSet(False), _CBSet(True)
        fake._maya_checks = {"maya2024": a, "maya2026": b}
        cd.CompileDialog._set_all_versions(fake, True)
        self.assertTrue(a.isChecked() and b.isChecked())
        cd.CompileDialog._set_all_versions(fake, False)
        self.assertFalse(a.isChecked() or b.isChecked())

    def test_set_busy_locks_version_buttons(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        fake._ver_all_btn = _W()
        fake._ver_none_btn = _W()
        cd.CompileDialog._set_busy(fake, True)
        self.assertIs(fake._ver_all_btn.enabled, False)
        self.assertIs(fake._ver_none_btn.enabled, False)
        cd.CompileDialog._set_busy(fake, False)
        self.assertIs(fake._ver_all_btn.enabled, True)
        self.assertIs(fake._ver_none_btn.enabled, True)

    def test_should_offer_load_guards_abi_mismatch(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        # No specific target (legacy) -> offer.
        self.assertTrue(C._should_offer_load(None, "/m/2026"))
        # Built for the running Maya -> offer.
        self.assertTrue(C._should_offer_load("/m/2026", "/m/2026"))
        # Built for a DIFFERENT Maya than the running one -> do NOT offer.
        self.assertFalse(C._should_offer_load("/m/2024", "/m/2026"))
        # Running Maya unknown -> can't compare, offer.
        self.assertTrue(C._should_offer_load("/m/2024", None))

    def test_on_compile_records_build_target_root(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn("_build_target_root", src)

    def test_on_finished_guards_load_offer(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_finished)
        self.assertIn("_should_offer_load", src)

    def test_on_progress_version_appends_narration_to_log(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        cd.CompileDialog._on_progress_main(
            fake, {"stage": "version", "node": "maya2024", "status": "start",
                   "detail": "Compiling maya2024 (1/2)", "i": 0, "n": 2})
        self.assertTrue(any("maya2024" in s for s in fake._appended_logs))


class TestCompileDialogSourceColumn(unittest.TestCase):
    """A 'Source' column telling whether each row is a scene node or an external
    .mpn template."""

    def test_source_column_constants(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # 7-column layout: Compile · Node Name · Class · Source · Data ·
        # Node Type · Status. Source sits between Class and Data; Node Type is the
        # derived compiled type (col 5); Status is last (col 6).
        self.assertEqual(cd._COL_CLASS, 2)
        self.assertEqual(cd._COL_SOURCE, 3)
        self.assertEqual(cd._COL_PERSIST, 4)
        self.assertEqual(cd._COL_TYPE, 5)
        self.assertEqual(cd._COL_STATUS, 6)
        # Distinct indices, no collision (all seven columns).
        self.assertEqual(
            len({cd._COL_CHECK, cd._COL_NODE, cd._COL_CLASS, cd._COL_TYPE,
                 cd._COL_SOURCE, cd._COL_PERSIST, cd._COL_STATUS}), 7)

    def test_build_ui_declares_source_column(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Headers + count live in the module SSOT (_COL_HEADERS / _COL_COUNT) so
        # the indices and titles can never drift; _build_ui consumes both.
        self.assertEqual(cd._COL_HEADERS[cd._COL_SOURCE], "Source")
        self.assertEqual(cd._COL_COUNT, 7)
        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("_COL_SOURCE", src)
        self.assertIn("_COL_COUNT", src)
        self.assertIn("_COL_HEADERS", src)

    def test_source_label_scene_vs_external(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        class _F:
            pass

        fake = _F()
        fake._file_rows = {"ext": ("/x/ext.mpn", "mPyNode")}
        self.assertEqual(C._source_label(fake, "ext"), "External .mpn")
        self.assertEqual(C._source_label(fake, "sceneNode"), "Scene")

    def test_render_row_writes_source_cell(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._render_row)
        self.assertIn("_COL_SOURCE", src)
        self.assertIn("_source_label", src)


class _ItemChangedFake:
    """Duck-typed self for _on_check_toggled (both columns)."""

    def __init__(self):
        self._checked = set()
        self._persistent_unchecked = set()
        self.rendered_persist = []

    def _apply_row_style(self, row, checked):
        pass

    def _render_persistent_cell(self, row, name):
        self.rendered_persist.append((row, name))


class TestPersistentColumn(unittest.TestCase):
    """Per-node Persistent-data column: pure decision helpers + the wiring that
    stamps each spec's per-node bake choice and tracks explicit unchecks."""

    # ---- pure decision helpers (no Qt) -----------------------------------
    def test_persist_cell_state_data_default_checked(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        # (has_persistent, global_ignore, user_unticked) -> (enabled, checked)
        self.assertEqual(C._persist_cell_state(True, False, False), (True, True))

    def test_persist_cell_state_data_user_unticked(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        self.assertEqual(C._persist_cell_state(True, False, True), (True, False))

    def test_persist_cell_state_no_data_disabled_unchecked(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        self.assertEqual(C._persist_cell_state(False, False, False),
                         (False, False))

    def test_persist_cell_state_global_ignore_greys_all(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        # Even a data node is disabled + unchecked when global-ignore is on.
        self.assertEqual(C._persist_cell_state(True, True, False), (False, False))

    def test_persist_cell_state_excluded_row_disabled(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        # Not in the bundle -> disabled (won't compile), but still shows the
        # has-data indicator (checked) so the column reads at a glance.
        self.assertEqual(
            C._persist_cell_state(True, False, False, in_bundle=False),
            (False, True))
        self.assertEqual(
            C._persist_cell_state(False, False, False, in_bundle=False),
            (False, False))

    def test_bake_choice_default_bakes(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        self.assertIs(C._bake_choice_for("foo", False, set()), True)

    def test_bake_choice_explicit_uncheck_strips(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        self.assertIs(C._bake_choice_for("foo", False, {"foo"}), False)

    def test_bake_choice_global_ignore_leaves_unset(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog as C

        # None -> leave the per-spec key unset so the global False strips ALL.
        self.assertIsNone(C._bake_choice_for("foo", True, set()))
        self.assertIsNone(C._bake_choice_for("foo", True, {"foo"}))

    # ---- source-level wiring ---------------------------------------------
    def test_build_ui_declares_persistent_column(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self.assertEqual(cd._COL_PERSIST, 4)
        self.assertEqual(cd._COL_STATUS, 6)
        # The persistent-bake column header is terse: "Data" (the global
        # "Ignore persistent data" checkbox supplies the full context).
        self.assertEqual(cd._COL_HEADERS[cd._COL_PERSIST], "Data")
        self.assertEqual(cd._COL_COUNT, 7)
        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("_COL_PERSIST", src)

    def test_render_row_renders_persistent_cell(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._render_row)
        self.assertIn("_render_persistent_cell", src)

    def test_render_persistent_cell_gates_on_bundle(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # The persist box of a row excluded from the bundle is greyed out.
        src = inspect.getsource(cd.CompileDialog._render_persistent_cell)
        self.assertIn("_checked", src)

    # ---- header titles + centered checkboxes (UX polish) -----------------
    def test_build_ui_titles_check_and_persistent_columns(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Full 7-column header list (indices pinned in the _COL_* test above).
        # The persistent-bake column is the terse "Data"; "Node Type" is the
        # derived compiled type.
        self.assertEqual(
            cd._COL_HEADERS,
            ["Compile", "Node Name", "Class", "Source", "Data", "Node Type",
             "Status"])
        self.assertEqual(cd._COL_HEADERS[cd._COL_CHECK], "Compile")
        self.assertEqual(cd._COL_HEADERS[cd._COL_PERSIST], "Data")
        self.assertEqual(cd._COL_HEADERS[cd._COL_TYPE], "Node Type")

    def test_render_persistent_cell_uses_centered_widget(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # The persist checkbox is a centered cell WIDGET, not a checkable item
        # (a checkable item pins its indicator to the cell's leading edge and
        # leaves a selectable empty gap -- the bug the user reported).
        src = inspect.getsource(cd.CompileDialog._render_persistent_cell)
        self.assertIn("_make_check_cell", src)
        self.assertIn("setCellWidget", src)
        self.assertNotIn("QTableWidgetItem", src)

    def test_render_row_uses_centered_check_widget(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Col 0's checkbox is a centered cell widget too.
        src = inspect.getsource(cd.CompileDialog._render_row)
        self.assertIn("_make_check_cell", src)
        self.assertIn("setCellWidget", src)
        self.assertNotIn("QTableWidgetItem", src)

    def test_make_check_cell_source_centers_and_sets_before_connect(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # The cell hosts a QCheckBox centered by a zero-margin QHBoxLayout and
        # routes toggles to _on_check_toggled. checked/enabled are set BEFORE
        # connect, so (re)building a cell never fires the handler.
        src = inspect.getsource(cd.CompileDialog._make_check_cell)
        self.assertIn("QHBoxLayout", src)
        self.assertIn("AlignCenter", src)
        self.assertIn("QCheckBox", src)
        self.assertIn("_on_check_toggled", src)
        self.assertLess(src.index("setChecked"), src.index("toggled.connect"),
                        "state must be set before connecting the signal")

    def test_make_check_cell_builds_centered_checkbox(self):
        # Behavioral: needs a real GUI QApplication. Headless mayapy installs a
        # QCoreApplication (no widgets), so skip; runs inside the Maya GUI.
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode.ui.qt_wrapper import Qt, QWidget, QCheckBox, QHBoxLayout
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:  # PySide2 (Maya 2024)
            from PySide2.QtWidgets import QApplication

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            self.skipTest("no GUI QApplication (headless mayapy)")

        class _F:
            pass

        fake = _F()
        fake._table = QWidget()
        fired = []
        fake._on_check_toggled = (
            lambda col, name, row, checked: fired.append(
                (col, name, row, checked)))

        w = cd.CompileDialog._make_check_cell(
            fake, "nodeA", cd._COL_PERSIST, 3, checked=True, enabled=True)
        self.assertIsInstance(w, QWidget)
        self.assertIsInstance(w.layout(), QHBoxLayout)
        boxes = w.findChildren(QCheckBox)
        self.assertEqual(len(boxes), 1)
        cb = boxes[0]
        self.assertTrue(cb.isChecked())
        self.assertTrue(cb.isEnabled())
        # GEOMETRY: laid out at a known width, the checkbox is horizontally
        # centered (its center ~ half the cell width) -- the real fix, vs. a
        # left-pinned checkable-item indicator.
        w.resize(90, 24)
        w.layout().activate()
        center_x = cb.x() + cb.width() / 2.0
        self.assertAlmostEqual(center_x, 45.0, delta=2.0)
        # Building it did NOT fire the handler (state set before connect)...
        self.assertEqual(fired, [])
        # ...but a user toggle does, with the col/name/row it was built for.
        cb.setChecked(False)
        self.assertEqual(fired[-1], (cd._COL_PERSIST, "nodeA", 3, False))

    def test_check_toggle_rerenders_persist(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Toggling bundle inclusion re-renders the persist cell so its greyed
        # state tracks bundle membership live.
        src = inspect.getsource(cd.CompileDialog._on_check_toggled)
        self.assertIn("_render_persistent_cell", src)

    def test_on_compile_stamps_per_spec_bake(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn("_persistent_unchecked", src)
        self.assertIn("bake_persistent", src)
        self.assertIn("_bake_choice_for", src)

    def test_wire_signals_connects_ignore_toggle(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._wire_signals)
        self.assertIn("_ignore_persistent_check", src)
        self.assertIn("toggled", src)

    # ---- behavioral: the persist column toggle tracks explicit unchecks ---
    def test_check_toggle_persist_col_tracks_unchecks(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _ItemChangedFake()
        cd.CompileDialog._on_check_toggled(
            fake, cd._COL_PERSIST, "n", 0, False)
        self.assertIn("n", fake._persistent_unchecked)
        # Re-checking removes it (back to the bake default).
        cd.CompileDialog._on_check_toggled(
            fake, cd._COL_PERSIST, "n", 0, True)
        self.assertNotIn("n", fake._persistent_unchecked)
        # Invariant 4 (other direction): toggling the Data column must NEVER
        # touch the bundle set.
        self.assertEqual(fake._checked, set())
        # The include column (col 0) must NOT touch the persistent set, and it
        # re-renders that row's persist cell.
        cd.CompileDialog._on_check_toggled(
            fake, cd._COL_CHECK, "n", 0, True)
        self.assertIn("n", fake._checked)
        self.assertNotIn("n", fake._persistent_unchecked)
        self.assertIn((0, "n"), fake.rendered_persist)

    # ---- review-hardening: lock the refactor's load-bearing details -------
    def test_refresh_persistent_column_reads_names_from_node_cell(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # The global "Ignore persistent data" re-grey path: col 0 is a widget
        # now, so _refresh_persistent_column must read each row's NAME from the
        # Node cell (col 1), not col 0. Lock that data dependency.
        class _Item:
            def __init__(self, text):
                self._t = text

            def text(self):
                return self._t

        class _Tbl:
            def __init__(self, names):
                self._names = names

            def rowCount(self):
                return len(self._names)

            def item(self, row, col):
                # Only the Node column carries an item; col 0 (a widget) is None.
                if col == cd._COL_NODE:
                    n = self._names[row]
                    return _Item(n) if n is not None else None
                return None

        class _F:
            pass

        fake = _F()
        fake._table = _Tbl(["alpha", None, "gamma"])
        forwarded = []
        fake._render_persistent_cell = (
            lambda row, name: forwarded.append((row, name)))
        cd.CompileDialog._refresh_persistent_column(fake)
        # Names came from col 1; the row with a None Node item is skipped.
        self.assertEqual(forwarded, [(0, "alpha"), (2, "gamma")])

    def test_old_itemchanged_model_is_gone(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # A cheap regression fence: the per-cell set-before-connect model must
        # not have a table-level itemChanged connection, a global suppress flag,
        # or the old handler creep back in next to the cell widgets.
        wire = inspect.getsource(cd.CompileDialog._wire_signals)
        self.assertNotIn("itemChanged.connect", wire)
        full = inspect.getsource(cd.CompileDialog)
        self.assertNotIn("_suppress_check", full)
        self.assertNotIn("_on_table_item_changed", full)

    def test_render_persistent_cell_installs_widget_no_item(self):
        # Behavioral (GUI-guarded): a data node yields an enabled+checked
        # centered checkbox, global-ignore yields a disabled+unchecked one, and
        # the cell holds NO QTableWidgetItem (the empty-selectable-gap fix).
        from mpynode.ui.dialogs import compile_dialog as cd
        from mpynode.ui.qt_wrapper import QWidget, QCheckBox, QTableWidget
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PySide2.QtWidgets import QApplication

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            self.skipTest("no GUI QApplication (headless mayapy)")

        class _F:
            pass

        fake = _F()
        fake._table = QTableWidget(1, 6)
        fake._checked = {"n"}
        fake._persistent_unchecked = set()
        fake._on_check_toggled = lambda *a: None
        fake._persist_cell_state = cd.CompileDialog._persist_cell_state
        fake._make_check_cell = cd.CompileDialog._make_check_cell.__get__(
            fake, cd.CompileDialog)
        # _render_persistent_cell now re-applies the checked-row highlight to the
        # freshly-built Data widget -- bind the real tinter so that path runs.
        fake._checked_row_color = cd.CompileDialog._checked_row_color.__get__(
            fake, cd.CompileDialog)
        fake._tint_cell_widget = cd.CompileDialog._tint_cell_widget.__get__(
            fake, cd.CompileDialog)
        fake._global_ignore_persistent = lambda: False

        # Data node, not globally ignored -> enabled + checked.
        fake._node_has_persistent = lambda name: True
        cd.CompileDialog._render_persistent_cell(fake, 0, "n")
        w = fake._table.cellWidget(0, cd._COL_PERSIST)
        self.assertIsInstance(w, QWidget)
        self.assertIsNone(fake._table.item(0, cd._COL_PERSIST))
        cb = w.findChildren(QCheckBox)[0]
        self.assertTrue(cb.isChecked())
        self.assertTrue(cb.isEnabled())

        # Global ignore on -> greyed (disabled + unchecked), still a widget.
        fake._global_ignore_persistent = lambda: True
        cd.CompileDialog._render_persistent_cell(fake, 0, "n")
        cb2 = fake._table.cellWidget(0, cd._COL_PERSIST).findChildren(
            QCheckBox)[0]
        self.assertFalse(cb2.isChecked())
        self.assertFalse(cb2.isEnabled())


class TestCompanionReportAndLoad(unittest.TestCase):
    """Step 5 (report native-vs-companion) + step 4 (load the companion beside
    the bundle) wiring in the compile dialog."""

    def test_companion_command_lines_from_result(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        result = {"companions": [
            {"type_name": "addNode1", "path": "/o/addNode1_commands.py",
             "commands": [{"name": "mk", "func_name": "mk", "kind": "factory"},
                          {"name": "op", "func_name": "op",
                           "kind": "instance"}]}]}
        lines = cd._companion_command_lines(result)
        blob = "\n".join(lines)
        self.assertIn("mk", blob)
        self.assertIn("factory", blob)
        self.assertIn("op", blob)
        self.assertIn("companion", blob.lower())

    def test_companion_command_lines_empty_when_none(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        self.assertEqual(cd._companion_command_lines({}), [])

    def test_summary_lines_renders_command_lines(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        lines = cd._summary_lines(
            True, "0:01", "p", "/o/p.bundle", None, [], [], [],
            command_lines=["mk (factory) -> companion"])
        self.assertIn("mk (factory) -> companion", "\n".join(lines))

    def test_summary_lines_without_command_lines_unchanged(self):
        # Default (no command_lines) must not add anything (backward compat).
        from mpynode.ui.dialogs import compile_dialog as cd

        a = cd._summary_lines(True, "0:01", "p", "/o/p.bundle", None, [],
                              ["n (compiled)"], [])
        b = cd._summary_lines(True, "0:01", "p", "/o/p.bundle", None, [],
                              ["n (compiled)"], [], command_lines=[])
        self.assertEqual(a, b)

    def test_offer_load_also_loads_companions_after_bundle(self):
        from mpynode._base import plugins
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        calls = []
        orig_q = cd.QMessageBox.question
        orig_helper = plugins.load_or_reload_native_plugin
        cd.QMessageBox.question = staticmethod(lambda *a, **k: cd.QMessageBox.Yes)

        def _helper(path):
            calls.append(path)
            return {"base": os.path.basename(path), "loaded": True,
                    "reloaded": False, "error": None}

        plugins.load_or_reload_native_plugin = _helper
        try:
            cd.CompileDialog._offer_load(
                fake, "/out/myPlug.bundle", ["/out/addNode1_commands.py"])
        finally:
            cd.QMessageBox.question = orig_q
            plugins.load_or_reload_native_plugin = orig_helper

        self.assertIn("/out/myPlug.bundle", calls)
        self.assertIn("/out/addNode1_commands.py", calls)
        self.assertLess(calls.index("/out/myPlug.bundle"),
                        calls.index("/out/addNode1_commands.py"),
                        "the bundle must load BEFORE its companion")


class TestCompileDialogRunTestsAndHighlight(unittest.TestCase):
    """The 'Run authored node tests' option (off by default, opt-in) + the
    checked-row highlight + option tooltips."""

    def test_build_ui_adds_run_tests_checkbox_off_by_default(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("_run_tests_check", src)
        self.assertIn("Run authored node tests", src)
        self.assertIn("self._run_tests_check.setChecked(False)", src)

    def test_build_ui_gives_strict_and_run_tests_tooltips(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_ui)
        self.assertIn("self._strict_check.setToolTip", src)
        self.assertIn("self._run_tests_check.setToolTip", src)

    def test_set_busy_locks_run_tests_check(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        cd.CompileDialog._set_busy(fake, True)
        self.assertIs(fake._run_tests_check.enabled, False)
        cd.CompileDialog._set_busy(fake, False)
        self.assertIs(fake._run_tests_check.enabled, True)

    def test_on_compile_threads_run_authored_tests(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        # Read through _pipeline_options now (which also forces them on when the
        # optimizer runs), not straight off the checkbox.
        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn("_pipeline_options", src)
        self.assertIn("run_authored_tests", src)
        opts = inspect.getsource(cd.CompileDialog._pipeline_options)
        self.assertIn("_run_tests_check", opts)

    def test_pipeline_group_adds_optimize_checkbox_off_by_default(self):
        """The stage checkboxes moved from _build_ui into the pipeline group."""
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._build_pipeline_ui)
        self.assertIn("_optimize_check", src)
        self.assertIn("AI optimize", src)
        self.assertIn("self._optimize_check.setChecked(False)", src)
        # ...and stage 2 defaults ON, so unconditional porting is unchanged.
        self.assertIn("self._assist_check.setChecked(True)", src)
        self.assertIn("_build_pipeline_ui()",
                      inspect.getsource(cd.CompileDialog._build_ui))

    def test_set_busy_locks_optimize_check(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        cd.CompileDialog._set_busy(fake, True)
        self.assertIs(fake._optimize_check.enabled, False)
        cd.CompileDialog._set_busy(fake, False)
        self.assertIs(fake._optimize_check.enabled, True)

    def test_on_compile_threads_optimize(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn("optimize=optimize", src)
        self.assertIn("_pipeline_options", src)
        opts = inspect.getsource(cd.CompileDialog._pipeline_options)
        self.assertIn("_optimize_check", opts)

    def test_apply_row_style_highlights_checked_rows(self):
        """A CHECKED row: text items get a non-default background + normal (not
        dim) foreground, and BOTH checkbox cell widgets are tinted. UNCHECKED:
        dim foreground and the widgets untinted."""
        from mpynode.ui.dialogs import compile_dialog as cd

        class _Item:
            def __init__(self):
                self.fg = "unset"
                self.bg = "unset"

            def setForeground(self, b):
                self.fg = b

            def setBackground(self, b):
                self.bg = b

        class _Tbl:
            def __init__(self):
                self._items = {(0, c): _Item() for c in range(6)}
                self._widgets = {(0, cd._COL_CHECK): object(),
                                 (0, cd._COL_PERSIST): object()}

            def item(self, r, c):
                return self._items.get((r, c))

            def cellWidget(self, r, c):
                return self._widgets.get((r, c))

            def palette(self):
                raise RuntimeError("no palette -> fallback color")

        class _F:
            pass

        fake = _F()
        fake._table = _Tbl()
        tint_calls = []
        fake._tint_cell_widget = (
            lambda w, checked: tint_calls.append((w, checked)))
        fake._checked_row_color = cd.CompileDialog._checked_row_color.__get__(
            fake, cd.CompileDialog)

        # Checked -> both widget cells tinted True; text items got a background.
        cd.CompileDialog._apply_row_style(fake, 0, True)
        self.assertEqual(len(tint_calls), 2)
        self.assertTrue(all(checked for (_w, checked) in tint_calls))
        node_item = fake._table.item(0, cd._COL_NODE)
        self.assertIsNot(node_item.bg, "unset")
        fg_checked = node_item.fg

        # Unchecked -> both widget cells un-tinted; foreground is the dim brush.
        tint_calls.clear()
        cd.CompileDialog._apply_row_style(fake, 0, False)
        self.assertEqual(len(tint_calls), 2)
        self.assertFalse(any(checked for (_w, checked) in tint_calls))
        self.assertIs(fake._table.item(0, cd._COL_NODE).fg, cd._DIM_BRUSH)
        self.assertIsNot(fg_checked, cd._DIM_BRUSH)

    def test_checked_row_color_falls_back_when_no_palette(self):
        from mpynode.ui.dialogs import compile_dialog as cd

        class _Tbl:
            def palette(self):
                raise RuntimeError("no palette")

        class _F:
            pass

        fake = _F()
        fake._table = _Tbl()
        col = cd.CompileDialog._checked_row_color(fake)
        self.assertEqual(col, cd._CHECKED_ROW_FALLBACK)
        # Cached after first computation.
        self.assertIs(cd.CompileDialog._checked_row_color(fake),
                      fake._checked_row_color_cache)


class TestOnFinishedMultiVerifyCrashGate(unittest.TestCase):
    """#61: the verify-crashed load gate must apply in the MULTI-version path
    too -- a multi build whose running-version bundle links fine but whose
    sandbox parity verify CRASHED must NOT be offered for load (loading it into
    the live session could crash Maya the same way)."""

    _RUNNING = "/Applications/Autodesk/maya2026/Maya.app/Contents"

    def _drive(self, verify_row):
        from mpynode.ui.dialogs import compile_dialog as cd

        fake = _FakeSelf()
        bpath = _real_bundle(self)
        sub = {"ok": True, "bundle_path": bpath, "companions": [],
               "nodes": [{"type_name": "A", "build_status": "compiled",
                          "verify": verify_row}]}
        result = {"ok": True, "results": [
            {"result": sub, "label": "2026", "root": self._RUNNING}]}
        warned = {}
        orig_warn = cd.QMessageBox.warning
        orig_resolve = cd._resolve_maya_dir
        cd.QMessageBox.warning = staticmethod(
            lambda *a, **k: warned.update(msg=a[-1] if a else ""))
        cd._resolve_maya_dir = staticmethod(lambda: self._RUNNING)
        try:
            cd.CompileDialog._on_finished_multi(fake, result, "0:05")
        finally:
            cd.QMessageBox.warning = orig_warn
            cd._resolve_maya_dir = orig_resolve
        return fake, warned, bpath

    def test_skips_load_when_running_version_verify_crashed(self):
        fake, warned, _bpath = self._drive(
            {"ran": False, "pass": None, "maxerr": None, "tol": None,
             "reason": "the verify process may have crashed"})
        self.assertEqual(fake._offer_load_calls, [],
                         "must NOT offer to load a verify-crashed bundle")
        self.assertTrue(warned.get("msg"))

    def test_offers_load_when_verify_clean(self):
        fake, warned, bpath = self._drive(
            {"ran": True, "pass": True, "maxerr": 1e-9, "tol": 1e-4,
             "reason": ""})
        self.assertEqual(fake._offer_load_calls, [bpath],
                         "a clean multi build must still offer to load")


if __name__ == "__main__":
    unittest.main()
