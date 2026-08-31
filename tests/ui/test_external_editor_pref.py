import unittest


class TestExternalEditorPref(unittest.TestCase):
    def test_default_is_auto_detect(self):
        # Empty default == auto-detect an installed editor at launch time
        # (editor_launch.detect_default_editor_command), NOT a hardcoded `code`.
        from mpynode.ui import preferences
        val = preferences.DEFAULT_PREFS.get("external_editor_command")
        self.assertEqual(val, "")

    def test_detect_default_editor_command_has_placeholders(self):
        # Whatever auto-detect resolves to, it must be a template with the
        # {file}/{line} placeholders open_in_editor substitutes.
        from mpynode.ui import editor_launch
        cmd = editor_launch.detect_default_editor_command()
        self.assertIn("{file}", cmd)
        self.assertIn("{line}", cmd)

    def test_dialog_wires_external_editor(self):
        import inspect
        from mpynode.ui.dialogs import preferences as dlg
        src = inspect.getsource(dlg)
        self.assertIn("external_editor_command", src)
        self.assertIn("_external_editor_edit", src)
        self.assertIn("Auto-detect", src)

    def test_dialog_offers_auto_detect_preset(self):
        from mpynode.ui.dialogs.preferences import _EDITOR_PRESETS
        labels = [label for (label, _cmd) in _EDITOR_PRESETS]
        self.assertIn("Auto-detect", labels)
        # Auto-detect must carry an EMPTY template (empty == auto-detect).
        self.assertEqual(dict(_EDITOR_PRESETS)["Auto-detect"], "")


if __name__ == "__main__":
    unittest.main()
