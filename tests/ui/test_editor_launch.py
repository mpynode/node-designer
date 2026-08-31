import os
import unittest
from mpynode.ui import editor_launch


class _Cap:
    def __init__(self):
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append((list(argv), kw))

        class _P:  # dummy Popen
            pass

        return _P()


class TestOpenInEditor(unittest.TestCase):
    def setUp(self):
        self._orig = editor_launch.subprocess.Popen
        self.cap = _Cap()
        editor_launch.subprocess.Popen = self.cap
        # Pretend every bare name resolves, so the result does not depend on
        # which editors the test machine has.
        self._orig_which = editor_launch.shutil.which
        editor_launch.shutil.which = lambda name, path=None: "/fake/bin/" + name
        # Pin a known template regardless of the user's prefs.
        import mpynode.ui.preferences as prefs
        self._orig_get = prefs.get_pref
        prefs.get_pref = lambda k, d=None: ("code --goto {file}:{line}"
                                            if k == "external_editor_command"
                                            else self._orig_get(k, d))

    def tearDown(self):
        editor_launch.subprocess.Popen = self._orig
        editor_launch.shutil.which = self._orig_which
        import mpynode.ui.preferences as prefs
        prefs.get_pref = self._orig_get

    def test_substitution_and_path_with_spaces_one_arg(self):
        ok, err = editor_launch.open_in_editor("/a b/c.py", 37)
        self.assertTrue(ok, err)
        argv = self.cap.calls[0][0]
        # '/a b/c.py' must stay in ONE argv element: substitution happens
        # AFTER shlex.split, so the file:line token stays glued. Splitting on
        # the space would give separate '/a' and 'b/c.py:37' tokens.
        self.assertIn("/a b/c.py:37", argv)
        self.assertIn("37", " ".join(argv))
        self.assertNotIn("{file}", " ".join(argv))

    def test_reveal_calls_popen(self):
        ok, err = editor_launch.reveal_in_file_manager("/a b/c.py")
        self.assertTrue(ok, err)
        self.assertTrue(self.cap.calls)

    def test_not_found_returns_helpful_error(self):
        # An unresolvable editor fails gracefully, pointing at the
        # Preferences override.
        editor_launch.shutil.which = lambda name, path=None: None
        ok, err = editor_launch.open_in_editor("/a b/c.py", 37)
        self.assertFalse(ok)
        self.assertIn("Preferences", err)
        self.assertFalse(self.cap.calls)  # never attempted to launch

    def test_absolute_command_used_directly(self):
        # An existing absolute template command is used as-is, skipping which;
        # point it at a path we know exists.
        import mpynode.ui.preferences as prefs
        real = editor_launch.__file__  # some file that definitely exists
        prefs.get_pref = lambda k, d=None: (
            "%s --goto {file}:{line}" % real
            if k == "external_editor_command" else self._orig_get(k, d))
        ok, err = editor_launch.open_in_editor("/a b/c.py", 5)
        self.assertTrue(ok, err)
        self.assertEqual(self.cap.calls[0][0][0], real)

    def test_augmented_path_includes_editor_bundles_on_mac(self):
        import sys
        if sys.platform != "darwin":
            self.skipTest("mac-only path augmentation")
        p = editor_launch._augmented_search_path()
        self.assertIn("Cursor.app", p)
        self.assertIn("/opt/homebrew/bin", p)

    def test_detect_default_editor_prefers_first_resolvable(self):
        # setUp patches which to resolve EVERY name, so detection returns the
        # FIRST entry in the preference order (cursor before code).
        cmd = editor_launch.detect_default_editor_command()
        self.assertEqual(cmd, "cursor --goto {file}:{line}")

    def test_detect_default_editor_falls_back_when_none_found(self):
        editor_launch.shutil.which = lambda name, path=None: None
        cmd = editor_launch.detect_default_editor_command()
        self.assertEqual(cmd, editor_launch._DEFAULT_EDITOR_COMMAND)

    def test_empty_pref_triggers_auto_detection(self):
        # An empty external_editor_command means "auto-detect": open_in_editor
        # must resolve a command via detect_default_editor_command() rather than
        # failing. Under the patched which, that's cursor.
        import mpynode.ui.preferences as prefs
        prefs.get_pref = lambda k, d=None: (
            "" if k == "external_editor_command" else self._orig_get(k, d))
        ok, err = editor_launch.open_in_editor("/x/y.py", 9)
        self.assertTrue(ok, err)
        argv = self.cap.calls[0][0]
        self.assertEqual(argv[0], "/fake/bin/cursor")
        self.assertIn("/x/y.py:9", argv)

    def test_reveal_label_nonempty(self):
        self.assertTrue(editor_launch.reveal_label())


if __name__ == "__main__":
    unittest.main()
