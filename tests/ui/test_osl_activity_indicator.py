"""OSL Translate activity indicator: NDOslEditor progress/outcome/cancel signals
and the reusable NDOslActivityStrip widget.

These test the NEW wiring added so the OSL tab can show a spinner + timer + live
feed + Stop + persistent inline error while the AI-fallback translation runs on a
worker thread. They are Qt-guarded (skip when PySide is unavailable) and use fake
transports so no real LLM is called.
"""

from __future__ import annotations

import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication as _QApplication
except ImportError:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except ImportError:
        _QApplication = None

if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["osl-activity-test"])


class _FakeNode:
    """Minimal py_node stand-in for NDOslEditor (OSL get/set + name)."""

    def __init__(self, osl="PRIOR OSL"):
        self._osl = osl
        self.set_calls = []

    def get_osl_expression(self):
        return self._osl

    def set_osl_expression(self, text):
        self._osl = text
        self.set_calls.append(text)

    def get_name(self):
        return "fakeShader"

    def convert_compute_to_osl_ai(self, *a, **k):  # capability marker only
        return None


@unittest.skipIf(_QApplication is None, "Qt unavailable")
class TestOslEditorConvertSignals(unittest.TestCase):
    """The worker-body wiring: log lines -> convertProgress; success/failure/
    cancel -> the right terminal signal; prior .osl preserved on non-success."""

    def setUp(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor

        self.node = _FakeNode()
        self.editor = NDOslEditor(self.node)
        self.progress = []
        self.succeeded = []
        self.failed = []
        self.cancelled = []
        self.editor.convertProgress.connect(self.progress.append)
        self.editor.convertSucceeded.connect(lambda: self.succeeded.append(True))
        self.editor.convertFailed.connect(self.failed.append)
        self.editor.convertCancelled.connect(
            lambda: self.cancelled.append(True))

    def _patch(self, make_fn):
        """Patch the transport factory, the AI-convert core (passthrough that
        drives complete_fn), and the main-thread marshal (run inline). Returns a
        cleanup callable."""
        from mpynode.native.ai import porter
        from mpynode._common.osl import osl_ai_convert
        import maya.utils as mu

        _MISSING = object()
        orig_make = porter.make_cli_complete_fn
        orig_conv = osl_ai_convert.ai_convert_compute_to_osl
        # In real Maya GUI this exists; in headless mayapy it may be absent, so
        # save-or-mark-missing and run the marshaled finish inline.
        orig_marshal = getattr(mu, "executeInMainThreadWithResult", _MISSING)

        def _passthrough(compute, init, shader, complete_fn,
                         validate_fn=None, max_repair=1, log_cb=None):
            return complete_fn("system", "user")

        porter.make_cli_complete_fn = make_fn
        osl_ai_convert.ai_convert_compute_to_osl = _passthrough
        mu.executeInMainThreadWithResult = lambda fn: fn()

        def _cleanup():
            porter.make_cli_complete_fn = orig_make
            osl_ai_convert.ai_convert_compute_to_osl = orig_conv
            if orig_marshal is _MISSING:
                try:
                    delattr(mu, "executeInMainThreadWithResult")
                except Exception:
                    pass
            else:
                mu.executeInMainThreadWithResult = orig_marshal

        self.addCleanup(_cleanup)

    def test_progress_lines_emit_convertProgress_and_succeed(self):
        def make(cancel_event=None, log_cb=None):
            def complete_fn(system, user):
                for i in range(3):
                    if log_cb:
                        log_cb("line %d" % i)
                return "shader fakeShader() { }"
            return complete_fn

        self._patch(make)
        self.editor._run_ai_convert("compute", "init", "fakeShader")

        self.assertEqual(self.progress, ["line 0", "line 1", "line 2"])
        self.assertEqual(self.succeeded, [True])
        self.assertEqual(self.failed, [])
        self.assertEqual(self.node._osl, "shader fakeShader() { }")

    def test_failure_emits_convertFailed_and_preserves_osl(self):
        def make(cancel_event=None, log_cb=None):
            def complete_fn(system, user):
                raise RuntimeError("boom")
            return complete_fn

        self._patch(make)
        self.editor._run_ai_convert("compute", "init", "fakeShader")

        self.assertEqual(self.succeeded, [])
        self.assertEqual(len(self.failed), 1)
        self.assertIn("boom", self.failed[0])
        self.assertEqual(self.node._osl, "PRIOR OSL")  # untouched

    def test_cancel_emits_convertCancelled_not_failed(self):
        self.editor._cancel_event = threading.Event()
        self.editor._cancel_event.set()

        def make(cancel_event=None, log_cb=None):
            def complete_fn(system, user):
                raise RuntimeError("aborted mid-flight")
            return complete_fn

        self._patch(make)
        self.editor._run_ai_convert("compute", "init", "fakeShader")

        self.assertEqual(self.cancelled, [True])
        self.assertEqual(self.failed, [])
        self.assertEqual(self.succeeded, [])
        self.assertEqual(self.node._osl, "PRIOR OSL")  # untouched

    def test_cancel_method_sets_the_event(self):
        self.editor._cancel_event = threading.Event()
        self.assertFalse(self.editor._cancel_event.is_set())
        self.editor.cancel()
        self.assertTrue(self.editor._cancel_event.is_set())

    def test_destroy_canceller_sets_in_flight_event(self):
        # Teardown hook: destroying the editor mid-run sets the captured cancel
        # event so the CLI subprocess stops promptly (no 600s leak). The
        # canceller closes over a plain holder, never the QObject.
        from mpynode.ui.widgets.osl_editor import _make_destroy_canceller

        holder = {"ev": None}
        fn = _make_destroy_canceller(holder)
        fn()  # nothing in flight -> no-op, must not raise
        ev = threading.Event()
        holder["ev"] = ev
        fn()
        self.assertTrue(ev.is_set())

    def test_editor_initializes_cancel_holder(self):
        self.assertEqual(self.editor._cancel_holder, {"ev": None})

    def test_ai_convert_log_cb_is_wired_to_progress(self):
        # The AI core's attempt/rejection markers must reach the strip: the
        # editor has to pass its log_cb into ai_convert_compute_to_osl, not only
        # into the transport factory.
        from mpynode.native.ai import porter
        from mpynode._common.osl import osl_ai_convert
        import maya.utils as mu

        _MISSING = object()
        captured = {}
        orig_make = porter.make_cli_complete_fn
        orig_conv = osl_ai_convert.ai_convert_compute_to_osl
        orig_marshal = getattr(mu, "executeInMainThreadWithResult", _MISSING)

        def _cap(compute, init, shader, complete_fn,
                 validate_fn=None, max_repair=1, log_cb=None):
            captured["log_cb"] = log_cb
            if log_cb:
                log_cb("Attempt 1/2: generating OSL...")
            return complete_fn("s", "u")

        porter.make_cli_complete_fn = (
            lambda cancel_event=None, log_cb=None:
            (lambda system, user: "shader fakeShader() { }"))
        osl_ai_convert.ai_convert_compute_to_osl = _cap
        mu.executeInMainThreadWithResult = lambda fn: fn()

        def _cleanup():
            porter.make_cli_complete_fn = orig_make
            osl_ai_convert.ai_convert_compute_to_osl = orig_conv
            if orig_marshal is _MISSING:
                try:
                    delattr(mu, "executeInMainThreadWithResult")
                except Exception:
                    pass
            else:
                mu.executeInMainThreadWithResult = orig_marshal

        self.addCleanup(_cleanup)
        self.editor._run_ai_convert("compute", "init", "fakeShader")
        self.assertIsNotNone(captured.get("log_cb"))
        self.assertIn("Attempt 1/2: generating OSL...", self.progress)

    def test_convert_via_ai_populates_holder_for_teardown(self):
        # Starting a run must point the teardown holder at the run's cancel
        # event, so a later destroy cancels the RIGHT event.
        from mpynode.native.ai import porter
        from mpynode._common.osl.osl_convert import UnsupportedComputeError

        orig_check = porter.check_provider
        orig_thread = threading.Thread
        porter.check_provider = lambda: {"ok": True}

        class _NoRunThread:  # capture target, never actually run it
            def __init__(self, target=None, args=(), daemon=None):
                pass

            def start(self):
                pass

        threading.Thread = _NoRunThread

        def _cleanup():
            porter.check_provider = orig_check
            threading.Thread = orig_thread

        self.addCleanup(_cleanup)

        started = self.editor._convert_via_ai(UnsupportedComputeError("nope"))
        self.assertTrue(started)
        self.assertIsNotNone(self.editor._cancel_event)
        self.assertIs(self.editor._cancel_holder["ev"], self.editor._cancel_event)
        self.assertFalse(self.editor._cancel_event.is_set())


@unittest.skipIf(_QApplication is None, "Qt unavailable")
class TestOslActivityStrip(unittest.TestCase):
    """The reusable spinner+timer+log+Stop widget."""

    def _make(self):
        from mpynode.ui.widgets.osl_activity_strip import NDOslActivityStrip

        return NDOslActivityStrip()

    def test_start_then_finish_error_is_persistent(self):
        strip = self._make()
        strip.start()
        strip.add_log_line("compiling…")
        strip.finish_error("OSL compile failed")
        self.assertIn("OSL compile failed", strip.status_text())
        self.assertIn("compiling…", strip.log_text())

    def test_start_then_finish_ok(self):
        strip = self._make()
        strip.start()
        strip.finish_ok()
        # a successful finish is not an error state
        self.assertNotIn("✕", strip.status_text())

    def test_stop_button_emits_stopRequested(self):
        strip = self._make()
        got = []
        strip.stopRequested.connect(lambda: got.append(True))
        strip.start()
        strip.request_stop()
        self.assertEqual(got, [True])

    def test_stop_label_resets_on_next_run(self):
        # request_stop() relabels + disables the Stop button; a fresh run must
        # restore a clickable "Stop", not one still reading "Stopping…".
        strip = self._make()
        strip.start()
        strip.request_stop()
        self.assertEqual(strip._stop_btn.text(), "Stopping…")
        self.assertFalse(strip._stop_btn.isEnabled())
        strip.reset()
        strip.start()  # run 2
        self.assertEqual(strip._stop_btn.text(), "Stop")
        self.assertTrue(strip._stop_btn.isEnabled())

    def test_elapsed_resets_after_reset(self):
        # reset() must clear _t0 so a terminal call with NO preceding start()
        # reports 0:00, not a stale elapsed carried over from a prior run.
        strip = self._make()
        strip.start()
        strip._t0 = time.monotonic() - 500.0  # pretend the last run began long ago
        strip.reset()
        strip.finish_error("boom")  # no start() since reset()
        self.assertIn("after 0:00", strip.status_text())

    def test_finish_error_without_log_does_not_force_expand(self):
        # Synchronous failure path (no start(), empty log): don't reveal an
        # empty, uncollapsible log panel.
        strip = self._make()
        strip.reset()
        strip.finish_error("no AI provider configured")
        self.assertFalse(strip._log_toggle.isChecked())
        self.assertIn("no AI provider configured", strip.status_text())

    def test_finish_error_with_log_expands(self):
        # When there IS streamed detail, failure force-expands it (and the
        # toggle is available to collapse it again).
        strip = self._make()
        strip.start()
        strip.add_log_line("compiling…")
        strip.finish_error("compile failed")
        self.assertTrue(strip._log_toggle.isChecked())


@unittest.skipIf(_QApplication is None, "Qt unavailable")
class TestOslTabIntegration(unittest.TestCase):
    """End-to-end host wiring: the real NDScriptTabContent OSL tab embeds the
    strip and its convert signals drive it (busy -> start, progress -> log +
    curated stage, failed -> persistent inline error)."""

    @classmethod
    def setUpClass(cls):
        try:
            import maya.standalone

            maya.standalone.initialize("python")
            import maya.cmds as cmds

            for p in ("mpynode_api1", "mpynode_api2"):
                if not cmds.pluginInfo(p, q=True, loaded=True):
                    cmds.loadPlugin(p)
            cls.cmds = cmds
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest("maya unavailable: %s" % exc)

    def _make_tab(self):
        from mpynode import MPyNode
        from mpynode.ui.widgets.script_tab_content import NDScriptTabContent

        tr = self.cmds.createNode("mPyFile")
        return NDScriptTabContent(MPyNode(tr))

    def test_osl_tab_has_activity_strip(self):
        tab = self._make_tab()
        from mpynode.ui.widgets.osl_activity_strip import NDOslActivityStrip

        self.assertIsInstance(getattr(tab, "_osl_activity", None),
                              NDOslActivityStrip)

    def test_signals_drive_the_strip(self):
        tab = self._make_tab()
        ed = tab._osl_editor
        strip = tab._osl_activity

        ed.convertBusyChanged.emit(True)             # host -> strip.start()
        ed.convertProgress.emit("[tool] validating OSL compile")
        self.assertIn("validating OSL compile", strip.log_text())
        self.assertIn("Validating", strip.status_text())  # curated stage bump

        ed.convertFailed.emit("kaboom")              # persistent inline error
        self.assertIn("kaboom", strip.status_text())
        self.assertIn("✕", strip.status_text())

    def test_success_signal_clears_error(self):
        tab = self._make_tab()
        ed = tab._osl_editor
        strip = tab._osl_activity
        ed.convertBusyChanged.emit(True)
        ed.convertSucceeded.emit()
        self.assertNotIn("✕", strip.status_text())


class _CompositeNode:
    """A py_node stand-in shaped like compositeTexture: the deterministic arm
    can't handle it AND it is STRUCTURALLY IMPOSSIBLE in OSL (array texture
    input + non-colour typed outputs)."""

    def __init__(self):
        self._osl = "PRIOR OSL"

    def get_osl_expression(self):
        return self._osl

    def set_osl_expression(self, text):
        self._osl = text

    def get_name(self):
        return "compositeTex"

    def convert_compute_to_osl_ai(self, *a, **k):  # capability marker
        return None

    def get_compute_expression(self):
        return ("u, v = self.uvCoord\n"
                "self.outColor = (0.0, 0.0, 0.0)\n"
                "self.maxWidth = 0\nself.maxHeight = 0\n")

    def get_init_expression(self):
        return ""

    def get_input_attr_map(self):
        return {"filePaths": {"attr_type": "string", "is_array": True}}

    def get_output_attr_map(self):
        return {"maxWidth": {"attr_type": "int", "is_array": False}}


@unittest.skipIf(_QApplication is None, "Qt unavailable")
class TestOslEditorIntractabilityGate(unittest.TestCase):
    """The UI's fast veto: an OSL-impossible Compute must fail immediately with
    an actionable message -- NO worker thread, NO provider pre-flight, NO tokens
    (this is the compositeTexture 6-minute flail the gate eliminates). The
    editor worker calls the AI core DIRECTLY, so it needs its own gate (the
    registry-level gate never runs on this path)."""

    def test_intractable_compute_fails_fast_no_worker(self):
        from mpynode.ui.widgets.osl_editor import NDOslEditor
        from mpynode._common.osl.osl_convert import UnsupportedComputeError
        from mpynode.native.ai import porter

        node = _CompositeNode()
        editor = NDOslEditor(node)
        failed = []
        editor.convertFailed.connect(failed.append)

        check_calls = {"n": 0}
        orig_check = porter.check_provider
        orig_thread = threading.Thread

        def _spy_check():
            check_calls["n"] += 1
            return {"ok": True}

        class _NoRun:
            def __init__(self, *a, **k):
                pass

            def start(self):
                raise AssertionError("worker thread must NOT start")

        porter.check_provider = _spy_check
        threading.Thread = _NoRun
        try:
            started = editor._convert_via_ai(UnsupportedComputeError("nope"))
        finally:
            porter.check_provider = orig_check
            threading.Thread = orig_thread
            editor.deleteLater()

        self.assertFalse(started)
        self.assertFalse(editor._ai_busy)
        self.assertEqual(check_calls["n"], 0)   # short-circuits before pre-flight
        self.assertEqual(len(failed), 1)
        self.assertIn("filePaths", failed[0])   # actionable, names the culprit
        self.assertEqual(node._osl, "PRIOR OSL")  # prior osl untouched


if __name__ == "__main__":
    unittest.main()
