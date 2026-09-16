"""CompileDialog per-node green-light + the "Compile with AI" label (WS2 T22).

Revision 2 of the unified-compile design gives the user AGENCY per node: a
compile that built but diverged / shipped incomplete / could not be verified is
not a failure, it is a choice. "Green-light" accepts that node's C++ as-is;
leaving it un-green-lit means "keep iterating", and only those nodes ride into
the "Fix with AI" hand-off.

Also covers R2.5's default-action relabel: the Compile button reads "Compile
with AI" while the AI-assist stage is armed (the default), and honestly falls
back to plain "Compile" when the user declines AI assist.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import ensure_plugins_loaded, standalone_init

_QAPP = None
try:
    from PySide6.QtWidgets import QApplication as _QApplication
except Exception:
    try:
        from PySide2.QtWidgets import QApplication as _QApplication
    except Exception:
        _QApplication = None
if _QApplication is not None:
    _QAPP = _QApplication.instance() or _QApplication(["compile-greenlight-test"])


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


def _verify(ran=False, ok=None, maxerr=None, tol=None, reason=""):
    return {"ran": ran, "pass": ok, "maxerr": maxerr, "tol": tol,
            "reason": reason}


def _row(type_name, build_status="compiled", verify=None, ported=False,
         incomplete=None, build_reason=""):
    return {
        "source_node":  type_name + "1",
        "type_name":    type_name,
        "build_status": build_status,
        "build_reason": build_reason,
        "ported":       ported,
        "incomplete":   list(incomplete or []),
        "invented_io":  [],
        "verify":       verify or _verify(),
        "spec":         {"portability": {"blockers": []}},
    }


def _result(nodes, ok=True):
    return {
        "ok":          ok,
        "plugin_name": "myPlugin",
        "bundle_path": "/tmp/out/myPlugin.bundle" if ok else None,
        "nodes":       nodes,
        "errors":      [],
    }


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestCompileWithAILabel(unittest.TestCase):
    """R2.5 Q2: "Compile with AI" is the DEFAULT action -- but the label must
    never claim AI when the user has switched the AI-assist stage off."""

    def _dialog(self):
        import maya.cmds as mc
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        mc.file(new=True, force=True)
        return CompileDialog()

    def test_default_label_says_compile_with_ai(self):
        dlg = self._dialog()
        try:
            self.assertTrue(dlg._assist_check.isChecked())
            self.assertEqual(dlg._compile_btn.text(), "Compile with AI")
        finally:
            dlg.deleteLater()

    def test_label_drops_ai_when_assist_declined(self):
        dlg = self._dialog()
        try:
            dlg._assist_check.setChecked(False)
            self.assertEqual(dlg._compile_btn.text(), "Compile")
            dlg._assist_check.setChecked(True)
            self.assertEqual(dlg._compile_btn.text(), "Compile with AI")
        finally:
            dlg.deleteLater()

    def test_optimize_forces_label_back_to_ai(self):
        """AI optimize implies AI assist (_sync_pipeline_gates), so the label
        must follow the RESOLVED gate, not the raw checkbox."""
        dlg = self._dialog()
        try:
            dlg._assist_check.setChecked(False)
            self.assertEqual(dlg._compile_btn.text(), "Compile")
            dlg._optimize_check.setChecked(True)
            self.assertTrue(dlg._pipeline_options()["ai_assist"])
            self.assertEqual(dlg._compile_btn.text(), "Compile with AI")
        finally:
            dlg.deleteLater()


@unittest.skipUnless(_QAPP is not None, "Qt unavailable")
class TestPerNodeGreenLight(unittest.TestCase):
    def _dialog(self):
        import maya.cmds as mc
        from mpynode.ui.dialogs.compile_dialog import CompileDialog

        mc.file(new=True, force=True)
        return CompileDialog()

    def _diverged(self, name="alpha"):
        return _row(name, "compiled",
                    verify=_verify(ran=True, ok=False, maxerr=1e-2, tol=1e-6))

    def _dropped(self, name="beta"):
        return _row(name, "dropped", build_reason="port failed")

    def test_no_greenlight_rows_on_a_clean_result(self):
        dlg = self._dialog()
        try:
            dlg.show()
            clean = _row("gamma", "compiled",
                         verify=_verify(ran=True, ok=True, maxerr=0.0, tol=1e-6))
            dlg._update_ai_button(_result([clean]), "/tmp/out")
            self.assertEqual(dlg._greenlight_buttons(), {})
            self.assertFalse(dlg._greenlight_box.isVisible())
        finally:
            dlg.deleteLater()

    def test_one_button_per_flagged_node(self):
        dlg = self._dialog()
        try:
            dlg._update_ai_button(
                _result([self._diverged(), self._dropped()]), "/tmp/out")
            btns = dlg._greenlight_buttons()
            self.assertEqual(sorted(btns), ["alpha1", "beta1"])
            for btn in btns.values():
                self.assertTrue(btn.isCheckable())
                self.assertFalse(btn.isChecked())
        finally:
            dlg.deleteLater()

    def test_greenlit_node_drops_out_of_the_handoff(self):
        dlg = self._dialog()
        try:
            dlg._update_ai_button(
                _result([self._diverged(), self._dropped()]), "/tmp/out")
            seen = []
            dlg.handoffToAssistant.connect(seen.append)
            dlg._greenlight_buttons()["alpha1"].setChecked(True)
            dlg._on_fix_with_ai()
            self.assertEqual(len(seen), 1)
            names = [r.get("source_node") for r in seen[0]["rows"]]
            self.assertEqual(names, ["beta1"])
        finally:
            dlg.deleteLater()

    def test_greenlighting_everything_hides_the_ai_button(self):
        dlg = self._dialog()
        try:
            dlg.show()
            dlg._update_ai_button(
                _result([self._diverged(), self._dropped()]), "/tmp/out")
            self.assertTrue(dlg._ai_btn.isVisible())
            for btn in dlg._greenlight_buttons().values():
                btn.setChecked(True)
            self.assertFalse(dlg._ai_btn.isVisible())
            # ...and un-green-lighting one brings the ask back.
            dlg._greenlight_buttons()["beta1"].setChecked(False)
            self.assertTrue(dlg._ai_btn.isVisible())
        finally:
            dlg.deleteLater()

    def test_greenlight_is_not_offered_for_a_verified_node(self):
        """A node that PASSED verify has nothing to consent to -- offering a
        green-light there would imply its parity was in doubt."""
        dlg = self._dialog()
        try:
            passing = _row("gamma", "compiled",
                           verify=_verify(ran=True, ok=True, maxerr=0.0,
                                          tol=1e-6))
            dlg._update_ai_button(
                _result([passing, self._diverged()]), "/tmp/out")
            self.assertEqual(sorted(dlg._greenlight_buttons()), ["alpha1"])
        finally:
            dlg.deleteLater()

    def test_new_run_clears_previous_greenlights(self):
        dlg = self._dialog()
        try:
            dlg.show()
            dlg._update_ai_button(_result([self._diverged()]), "/tmp/out")
            dlg._greenlight_buttons()["alpha1"].setChecked(True)
            self.assertFalse(dlg._ai_btn.isVisible())
            # A fresh run must not carry the last run's consent forward.
            dlg._reset_greenlights()
            dlg._update_ai_button(_result([self._diverged()]), "/tmp/out")
            self.assertTrue(dlg._ai_btn.isVisible())
            self.assertFalse(dlg._greenlight_buttons()["alpha1"].isChecked())
        finally:
            dlg.deleteLater()

    def test_each_row_names_its_own_reason(self):
        """Naming node A while describing node B's failure is the exact bug
        ``compile_bridge._shape_and_row`` exists to prevent; the per-node strip
        must not reintroduce it."""
        try:
            from PySide6.QtWidgets import QLabel
        except Exception:
            from PySide2.QtWidgets import QLabel

        dlg = self._dialog()
        try:
            dlg._update_ai_button(
                _result([self._diverged(), self._dropped()]), "/tmp/out")
            texts  = [w.text() for w in dlg._greenlight_box.findChildren(QLabel)]
            joined = "\n".join(texts)
            self.assertIn("alpha1 -- built, but its output DIVERGED", joined)
            self.assertIn("beta1 -- did not build", joined)
        finally:
            dlg.deleteLater()

    def test_compile_run_resets_greenlights(self):
        """The reset must be wired into the run start, not just available."""
        import inspect

        from mpynode.ui.dialogs import compile_dialog as cd

        src = inspect.getsource(cd.CompileDialog._on_compile)
        self.assertIn("_reset_greenlights()", src)


if __name__ == "__main__":
    unittest.main()
