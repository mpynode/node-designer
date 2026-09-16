"""NDOslEditor -- sister editor for a node's OSL render-target string (the
connectable ``osl`` plug).

Same editing chrome (line numbers, font zoom) as NDScriptEditor /
NDViewportEditor, but it pulls/pushes the OSL source via
``get_osl_expression`` / ``set_osl_expression`` (OslSourceMixin) instead of a
Python source tier.

The OSL tab is a RENDER TARGET, not an execution tier: unlike Compute /
Viewport (Python the node runs), the text here is renderer shader source
exposed as the node's connectable ``.osl`` output, wired into an Arnold
aiOslShader. It is C-like, NOT Python, so Python autocomplete is suppressed
(the inherited Python highlighter is left on as an approximate aid only).

Shown only for wrappers exposing ``set_osl_expression`` (v1: mPyFile). Lives
alongside the other sister editors inside NDScriptTabContent.
"""

from __future__ import annotations

from mpynode.ui.qt_wrapper import Signal
from mpynode.ui.widgets.editor_core import QtPythonEditor


def _make_destroy_canceller(holder):
    """Return a slot for the editor's ``destroyed`` signal that cancels an
    in-flight AI translation on teardown. It closes over a plain ``holder``
    dict -- never the (dying) QObject -- so it is safe to run as the widget is
    destroyed: it only sets the captured ``threading.Event``, which the
    transport polls to terminate the CLI subprocess promptly (instead of
    waiting out the ~600s CLI timeout when a tab is closed / the scene reset
    mid-translation). No-op when nothing is in flight."""

    def _cancel(*_args):
        ev = holder.get("ev")
        if ev is not None:
            ev.set()

    return _cancel


class NDOslEditor(QtPythonEditor):
    """Per-tab editor bound to a node's ``osl`` string attr."""

    dirtyStateChanged = Signal(bool)
    # Brackets the worker-thread AI fallback, so the host can disable /
    # relabel the Translate button while it's in flight.
    convertBusyChanged = Signal(bool)
    # One streamed chain-of-thought / tool line at a time from the transport's
    # log_cb. Feeds the OSL-tab activity strip.
    convertProgress = Signal(str)
    # Terminal outcomes -- exactly ONE fires per run. Failures carry the
    # message inline; there is no modal dialog.
    convertSucceeded = Signal()
    convertFailed    = Signal(str)
    convertCancelled = Signal()
    # On a HARD OSL limit, a compile_bridge hand-off dict the host can route to
    # the assistant. Emitted ALONGSIDE convertFailed, so hosts that don't wire
    # this still see the message.
    handoffToAssistant = Signal(object)

    def __init__(self, py_node, parent=None):
        super().__init__(parent)
        self._py_node = py_node
        self._last_saved_text: str = ""
        self._suppress_change_signal = False
        self._ai_busy                = False  # guards against re-entrant AI fallback runs
        # Set per AI-fallback run so a Stop button can cancel it (the transport
        # polls this and raises PortCancelled). None when no run is in flight.
        self._cancel_event = None
        # Mirrors the cancel event for the destroy hook: a closure can't read
        # self after teardown, so it reads this holder. Cancel lives on
        # ``destroyed`` (fired by deleteLater, the route every tab teardown
        # takes) rather than closeEvent, which would NOT catch it.
        self._cancel_holder = {"ev": None}
        self.destroyed.connect(_make_destroy_canceller(self._cancel_holder))
        # OSL is not Python: no plug/builtins vocabulary to offer.
        self.setCompletionWords([])
        self.refresh()
        self.textChanged.connect(self._on_text_changed)

    def getMPyNode(self):
        return self._py_node

    def getText(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self._suppress_change_signal = True
        try:
            self.setPlainText(text)
        finally:
            self._suppress_change_signal = False

    def hasUnsavedChanges(self) -> bool:
        return self.getText() != self._last_saved_text

    def markSaved(self) -> None:
        """Persist the OSL source to the node's ``osl`` plug + reset baseline."""
        text = self.getText()
        try:
            self._py_node.set_osl_expression(text)
        except Exception as exc:
            import sys

            sys.stderr.write(
                f"[NDOslEditor] set_osl_expression failed: {exc}\n"
            )
            return
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    def refresh(self) -> None:
        """Re-pull from the node's ``osl`` attr + reset baseline.

        A blank attr renders as a BLANK tab -- the editor never re-inserts a
        header for an empty plug. Headers are seeded into the plug ONCE, at
        Node-Designer virgin create in "headers" mode (build_new_node_command);
        a cleared expression therefore stays cleared across save + reload.
        """
        try:
            text = self._py_node.get_osl_expression() or ""
        except Exception:
            text = ""
        self.setText(text)
        self._last_saved_text = text
        self.dirtyStateChanged.emit(False)

    def refreshCompletionVocabulary(self) -> None:
        # OSL is not Python; keep completion empty (parity with the tab API).
        self.setCompletionWords([])

    def convertFromCompute(self) -> bool:
        """Translate the node's Compute look-math into this OSL tab.

        Hybrid: tries the DETERMINISTIC transpiler first (fast, exact, no
        tokens). If the look-math is outside its v1 grammar
        (``UnsupportedComputeError`` -- e.g. the full colour-management
        pipeline), it AUTO-FALLS-BACK to a one-shot AI translation
        (:meth:`_convert_via_ai`), run off the main thread. Returns True on a
        successful synchronous (deterministic) conversion, or True when the AI
        fallback was successfully STARTED (it finishes asynchronously)."""
        node = self._py_node
        conv = getattr(node, "convert_compute_to_osl", None)
        if not callable(conv):
            return False
        from mpynode._common.osl.osl_convert import UnsupportedComputeError

        try:
            osl = conv()
        except UnsupportedComputeError as det_exc:
            # Deterministic grammar can't express this -> AI fallback (auto).
            return self._convert_via_ai(det_exc)
        except Exception as exc:
            self._emit_failure(exc)
            return False
        # Already persisted to .osl; sync the view + baseline so the tab is
        # clean, with no spurious unsaved-changes marker.
        self.setText(osl)
        self._last_saved_text = osl
        self.dirtyStateChanged.emit(False)
        return True

    def cancel(self) -> None:
        """Request cancellation of an in-flight AI translation. Sets the per-run
        cancel event; the transport polls it and raises PortCancelled, which the
        finish path reports as a cancel (prior .osl untouched). No-op when idle."""
        ev = self._cancel_event
        if ev is not None:
            ev.set()

    # ------------------------------------------------------------------
    # AI fallback (one-shot translate + compile-validate + 1 self-repair)
    # ------------------------------------------------------------------
    def _convert_via_ai(self, det_exc) -> bool:
        """Start the AI translation fallback. Gathers the node tiers + pre-flights
        the provider on the (current) main thread, then runs the blocking LLM
        translation on a worker thread so Maya doesn't freeze. Returns True if
        the worker was started, False if it could not run (no capability / no
        provider / already busy) -- in which case the user sees a message."""
        node = self._py_node
        if not callable(getattr(node, "convert_compute_to_osl_ai", None)):
            self._emit_failure(det_exc)
            return False
        if self._ai_busy:
            return False

        # Gather the node's tiers + shader name on the MAIN thread (Maya reads).
        try:
            from mpynode._common.osl.osl_registry import _osl_identifier

            getc    = getattr(node, "get_compute_expression", None)
            geti    = getattr(node, "get_init_expression", None)
            compute = (getc() or "") if callable(getc) else ""
            init    = (geti() or "") if callable(geti) else ""
            name = getattr(node, "_name", "") or (
                node.get_name() if hasattr(node, "get_name") else "")
            shader = _osl_identifier(name)
        except Exception as exc:
            self._emit_failure(exc)
            return False

        # Some computes are STRUCTURALLY impossible in OSL (a runtime array of
        # textures, non-colour typed outputs). The worker calls the AI core
        # directly, bypassing the registry gate, so refuse HERE -- before any
        # pre-flight / worker / tokens -- with an actionable message instead of
        # a multi-minute flail that produces no OSL. The assessment itself must
        # never block a translatable node.
        try:
            from mpynode._common.osl.osl_convert import assess_osl_tractability

            gim       = getattr(node, "get_input_attr_map", None)
            gom       = getattr(node, "get_output_attr_map", None)
            in_attrs  = gim() if callable(gim) else None
            out_attrs = gom() if callable(gom) else None
            tractable, reason = assess_osl_tractability(
                compute, init, input_attrs=in_attrs, output_attrs=out_attrs)
        except Exception:
            tractable, reason = True, ""
        if not tractable:
            # Offer the assistant a hand-off (the host decides how to surface
            # it), then still show the inline message for hosts that don't
            # wire it.
            try:
                from mpynode.ui.llm import compile_bridge

                self.handoffToAssistant.emit(
                    compile_bridge.build_osl_handoff(
                        reason, node_name=name, compute=compute))
            except Exception:
                pass
            self._emit_failure(self._intractable_message(reason))
            return False

        # Pre-flight the provider WITHOUT spending tokens. None available ->
        # show the deterministic hint plus the concrete provider problem.
        try:
            from mpynode.native.ai import porter

            chk = porter.check_provider()
        except Exception as exc:
            chk = {"ok": False, "problems": [str(exc)]}
        if not chk.get("ok"):
            self._emit_failure(self._no_provider_message(det_exc, chk))
            return False

        import threading

        self._ai_busy             = True
        self._cancel_event        = threading.Event()
        self._cancel_holder["ev"] = self._cancel_event  # arm the teardown hook
        self.convertBusyChanged.emit(True)

        threading.Thread(
            target = self._run_ai_convert,
            args   = (compute, init, shader),
            daemon = True,
        ).start()
        return True

    def _run_ai_convert(self, compute, init, shader) -> None:
        """Worker thread: run the blocking AI translation + compile-validation,
        then marshal the result back to the main thread to persist + refresh."""
        osl = None
        err = None
        try:
            from mpynode._common.osl.osl_ai_convert import ai_convert_compute_to_osl
            from mpynode.native.ai import porter

            # Safe from this worker thread: a Qt signal is delivered to the
            # GUI thread via a queued connection.
            def _log_cb(line):
                self.convertProgress.emit(str(line))

            complete_fn = porter.make_cli_complete_fn(
                cancel_event=self._cancel_event, log_cb=_log_cb)
            osl = ai_convert_compute_to_osl(
                compute, init, shader, complete_fn,
                validate_fn = self._validate_osl_main_thread,
                log_cb      = _log_cb,
            )
        except Exception as exc:
            err = exc
        # Marshal the finish onto the MAIN thread. The import is guarded
        # SEPARATELY from the marshal: only an absent maya.utils (headless /
        # tests, with no Qt loop or scene to corrupt) may finish inline. A
        # genuine marshal failure -- e.g. the tab was torn down during a slow
        # LLM call -- must NOT re-run _finish_ai_convert, which touches Qt
        # widgets and writes the scene. Just log and clear the busy latch so
        # the Translate button isn't left stuck.
        try:
            import maya.utils as mu
        except Exception:
            self._finish_ai_convert(osl, err)
            return
        try:
            mu.executeInMainThreadWithResult(
                lambda: self._finish_ai_convert(osl, err)
            )
        except Exception as exc:
            import sys

            sys.stderr.write(
                "[NDOslEditor] AI-convert finish marshal failed: %s\n" % exc
            )
            self._ai_busy = False

    def _validate_osl_main_thread(self, osl):
        """compile-validate ``osl`` via Arnold ON THE MAIN THREAD (OSLSceneModel
        is a Maya/Arnold API call). Called from the worker thread by the AI core;
        marshals via maya.utils. Returns ``(ok, error)`` -- ``(True, "")`` when it
        can't validate (no MtoA) so translation isn't blocked."""
        try:
            import maya.utils as mu
            from mpynode._common.osl.osl_targets import validate_osl_via_arnold

            return mu.executeInMainThreadWithResult(
                lambda: validate_osl_via_arnold(osl)
            )
        except Exception:
            return True, ""

    def _finish_ai_convert(self, osl, err) -> None:
        """Main thread: persist the translated OSL + refresh the tab, or report a
        cancel / failure. Exactly ONE terminal signal fires (succeeded / cancelled
        / failed). The prior ``.osl`` is left untouched on cancel or failure."""
        cancelled = (self._cancel_event is not None
                     and self._cancel_event.is_set())
        self._ai_busy             = False
        self._cancel_event        = None
        self._cancel_holder["ev"] = None  # disarm the teardown hook
        self.convertBusyChanged.emit(False)

        if cancelled:
            # Stop was pressed: whatever error unwound (the transport wraps
            # PortCancelled) is a cancel, not a failure.
            self.convertCancelled.emit()
            return
        if osl:
            try:
                self._py_node.set_osl_expression(osl)
            except Exception as exc:
                self._emit_failure(exc)
                return
            self.setText(osl)
            self._last_saved_text = osl
            self.dirtyStateChanged.emit(False)
            self.convertSucceeded.emit()
        else:
            self._emit_failure(
                err or Exception("AI translation did not produce OSL.")
            )

    def _intractable_message(self, reason) -> str:
        """Actionable message for a Compute that CANNOT be translated to OSL
        (refused before any AI round). Unlike the deterministic ``det_exc``
        hint, this does NOT suggest "use the AI assistant" -- the AI can't do it
        either -- but explains why and points at the hand-authoring path."""
        return (
            "This node's Compute cannot be translated to OSL.\n\n"
            + str(reason).strip()
            + "\n\nAn OSL shader produces a single colour from scalar / string "
            "/ colour parameters, so this look has no OSL equivalent. Author "
            "the .osl by hand if you need it in a renderer."
        )

    def _no_provider_message(self, det_exc, chk) -> str:
        problems = "; ".join(
            chk.get("problems") or ["no AI provider is configured"]
        )
        return (
            str(det_exc)
            + "\n\nThe AI fallback could not run: "
            + problems
            + "\n\nConfigure a provider in the Node Designer's AI Assistant "
            "settings, then try again."
        )

    def _emit_failure(self, exc) -> None:
        """Report a translation failure via the inline convertFailed signal (the
        host shows a persistent inline error -- no modal). Also logs to stderr so
        a headless run with no connected host still records the reason."""
        msg = str(exc) or "Could not translate the Compute look-math to OSL."
        self.convertFailed.emit(msg)
        import sys

        sys.stderr.write("[NDOslEditor] convert failed: %s\n" % msg)

    def _on_text_changed(self) -> None:
        if self._suppress_change_signal:
            return
        self.dirtyStateChanged.emit(self.hasUnsavedChanges())
