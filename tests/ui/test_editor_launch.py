import tests  # noqa: F401 -- first: keeps the run out of ~/.mpynode

import os
import shlex
import shutil
import sys
import unittest
from unittest import mock

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
        self._orig                     = editor_launch.subprocess.Popen
        self.cap                       = _Cap()
        editor_launch.subprocess.Popen = self.cap
        # Pretend every bare name resolves, so the result does not depend on
        # which editors the test machine has.
        self._orig_which           = editor_launch.shutil.which
        editor_launch.shutil.which = lambda name, path=None: "/fake/bin/" + name
        # Pin a known template regardless of the user's prefs.
        import mpynode.ui.preferences as prefs
        self._orig_get = prefs.get_pref
        prefs.get_pref = lambda k, d=None: ("code --goto {file}:{line}"
                                            if k == "external_editor_command"
                                            else self._orig_get(k, d))

    def tearDown(self):
        editor_launch.subprocess.Popen = self._orig
        editor_launch.shutil.which     = self._orig_which
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
        # A REAL path: reveal now refuses a nonexistent one rather than
        # launching a file manager that lands somewhere arbitrary.
        ok, err = editor_launch.reveal_in_file_manager(editor_launch.__file__)
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
        # point it at a path we know exists. Quoted, because the repo's folder
        # may have a space in it.
        import mpynode.ui.preferences as prefs
        real = editor_launch.__file__  # some file that definitely exists
        prefs.get_pref = lambda k, d=None: (
            '"%s" --goto {file}:{line}' % real
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
        cmd                        = editor_launch.detect_default_editor_command()
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


class TestAnAbsoluteCommandLaunchesTheExactExecutable(unittest.TestCase):
    """An absolute editor command reaches Popen as the exact executable.

    Windows splits the command non-POSIX (a POSIX split takes each backslash
    for an escape), and that split keeps the quotes around a quoted token. A
    path with a space has to be quoted, so it came back as
    '"C:\\...\\my editor.exe"': not an absolute path, never found. Unquoted,
    it splits at the space. Nothing resolves on the search path here, so only
    the absolute path itself can launch.
    """

    def setUp(self):
        import tempfile

        import mpynode.ui.preferences as prefs
        # Imported now, under the real os.name, before a test patches it.
        from mpynode.native.toolchain import toolchain  # noqa: F401

        base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, base, True)
        self.spaced   = self._exe(base, "with space", "my editor.exe")
        self.plain    = self._exe(base, "nospace", "editor.exe")
        self.calls    = []
        self.template = None

        def fake_popen(argv, *a, **kw):
            self.calls.append(list(argv))

            class P:
                pass
            return P()

        orig_get = prefs.get_pref

        def get_pref(k, d=None):
            if k == "external_editor_command":
                return self.template
            return orig_get(k, d)

        for owner, name, value in (
                (editor_launch.subprocess, "Popen", fake_popen),
                (editor_launch.shutil, "which", lambda name, path=None: None),
                (prefs, "get_pref", get_pref)):
            self.addCleanup(setattr, owner, name, getattr(owner, name))
            setattr(owner, name, value)

    @staticmethod
    def _exe(base, folder, name):
        os.makedirs(os.path.join(base, folder))
        path = os.path.join(base, folder, name)
        with open(path, "w") as fh:
            fh.write("")
        return path

    def _launch(self, template, path="/a b/c.py", line=5):
        self.template = template
        del self.calls[:]
        ok, err = editor_launch.open_in_editor(path, line)
        self.assertTrue(ok, err)
        self.assertEqual(len(self.calls), 1)
        return self.calls[0]

    def test_a_quoted_path_with_a_space_is_launched_as_is(self):
        for quote in ('"', "'"):
            with self.subTest(quote=quote):
                argv = self._launch(
                    "%s%s%s --goto {file}:{line}" % (quote, self.spaced, quote))
                self.assertEqual(argv, [self.spaced, "--goto", "/a b/c.py:5"])

    def test_a_path_without_a_space_quoted_or_not(self):
        if " " in self.plain:
            self.skipTest("the temp folder has a space: %s" % self.plain)
        for template in ("%s --goto {file}:{line}",
                         '"%s" --goto {file}:{line}'):
            with self.subTest(template=template):
                argv = self._launch(template % self.plain)
                self.assertEqual(argv, [self.plain, "--goto", "/a b/c.py:5"])

    def test_a_command_with_arguments(self):
        # A quoted argument loses its quotes too, the {file}:{line} one
        # included: the editor gets the path, not a path wrapped in quotes.
        data = os.path.join(os.path.dirname(self.spaced), "user data")
        argv = self._launch(
            '"%s" --new-window --goto "{file}:{line}" --user-data-dir "%s"'
            % (self.spaced, data), path="/x y/z.py", line=12)
        self.assertEqual(argv, [self.spaced, "--new-window", "--goto",
                                "/x y/z.py:12", "--user-data-dir", data])
        argv = self._launch('"%s" --line {line} {file}' % self.spaced,
                            path="/x y/z.py", line=12)
        self.assertEqual(argv, [self.spaced, "--line", "12", "/x y/z.py"])

    def test_the_windows_split_on_any_host(self):
        # os.name picks the split. These paths have no backslash, so on a Mac
        # or Linux host the Windows split reads them too.
        with mock.patch.object(os, "name", "nt"):
            argv = self._launch(
                '"%s" --goto "{file}:{line}"' % self.spaced)
        self.assertEqual(argv, [self.spaced, "--goto", "/a b/c.py:5"])

    def test_a_missing_quoted_path_is_named_without_its_quotes(self):
        gone          = os.path.join(os.path.dirname(self.spaced), "gone.exe")
        self.template = '"%s" --goto {file}:{line}' % gone
        ok, err = editor_launch.open_in_editor("/a b/c.py", 5)
        self.assertFalse(ok)
        self.assertIn("could not find %r" % gone, err)
        self.assertEqual(self.calls, [])

    def test_an_unquoted_path_with_a_space_says_to_put_quotes_around_it(self):
        # Unquoted, the split cuts the path at its first space, and the error
        # named only the first word ("could not find '...\\with'"). It now
        # says to put quotes around a path that has a space, with an example
        # (a Windows one on Windows); quoted as it says, the path launches.
        # The word is named as written, each backslash single on Windows, as
        # in the example: not its repr.
        first         = self.spaced.split(" ")[0]
        self.template = "%s --goto {file}:{line}" % self.spaced
        ok, err = editor_launch.open_in_editor("/a b/c.py", 5)
        self.assertFalse(ok)
        self.assertEqual(self.calls, [])
        self.assertEqual(
            err,
            "could not find '%s'. In Preferences > Editor > Open-in-editor "
            "command, put quotes around a path that has a space, e.g. %s"
            % (first, editor_launch._quoted_path_example()))
        argv = self._launch('"%s" --goto {file}:{line}' % self.spaced)
        self.assertEqual(argv, [self.spaced, "--goto", "/a b/c.py:5"])

    def test_the_example_is_a_windows_one_on_windows(self):
        # The Windows split on any host: the error gives a Windows path, and
        # that split reads the example's quoted path as one executable.
        with mock.patch.object(os, "name", "nt"):
            self.template = "%s --goto {file}:{line}" % self.spaced
            ok, err = editor_launch.open_in_editor("/a b/c.py", 5)
            example = editor_launch._quoted_path_example()
        self.assertFalse(ok)
        self.assertEqual(example, '"C:\\Program Files\\Microsoft VS Code\\bin'
                                  '\\code.cmd" --goto {file}:{line}')
        self.assertTrue(err.endswith("a path that has a space, e.g. " + example),
                        err)
        words = [editor_launch._unquote(w)
                 for w in shlex.split(example, posix=False)]
        self.assertEqual(words, ["C:\\Program Files\\Microsoft VS Code\\bin"
                                 "\\code.cmd", "--goto", "{file}:{line}"])
        # Elsewhere the example is a macOS one, read whole by the POSIX split.
        with mock.patch.object(os, "name", "posix"):
            example = editor_launch._quoted_path_example()
        self.assertEqual(shlex.split(example),
                         ["/Applications/Visual Studio Code.app/Contents/"
                          "Resources/app/bin/code", "--goto", "{file}:{line}"])

    def test_only_a_path_cut_at_its_space_gets_that_advice(self):
        # A quoted path was not cut: named without its quotes, no advice. A
        # lone unquoted path has nothing after it, so no space was cut. A
        # bare name gets the search-path advice, as before.
        lone = os.path.join(os.path.dirname(self.plain), "gone.exe")
        if " " in lone:
            self.skipTest("the temp folder has a space: %s" % lone)
        quoted = os.path.join(os.path.dirname(self.spaced), "gone.exe")
        for template, named in (
                ('"%s" --goto {file}:{line}' % quoted, quoted),
                (lone, lone),
                ("noSuchEditor --goto {file}:{line}", "noSuchEditor")):
            with self.subTest(template=template):
                self.template = template
                ok, err = editor_launch.open_in_editor("/a b/c.py", 5)
                self.assertFalse(ok)
                self.assertTrue(err.startswith("could not find %r. " % named),
                                err)
                self.assertNotIn("quotes", err)
                self.assertIn("GUI Maya may not see your shell PATH", err)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()


class TestRevealTargetsAFolderCorrectly(unittest.TestCase):
    """``explorer /select,`` names a CHILD to highlight.

    Handing it a directory therefore does not open that directory: Explorer
    cannot act on the argument and silently falls back to its default
    location, which for most people is Documents. It reports nothing, and
    ``explorer.exe`` exits 1 even on success, so there is no return code to
    check -- the reveal looked like it worked and went somewhere else.

    Two of the three callers hand this a directory: the template gallery
    always passes ``TemplateEntry.folder``, and the compile dialog passes its
    AI output dir whenever there is no report file. Confirmed by running all
    three candidate commands and watching which window appeared.
    """

    def setUp(self):
        import tempfile

        from mpynode.ui import editor_launch
        self.editor_launch = editor_launch
        self.calls         = []

        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.file = os.path.join(self.dir, "thing.mpn")
        with open(self.file, "w") as fh:
            fh.write("x")

        real_popen = editor_launch.subprocess.Popen

        def fake(argv, *a, **kw):
            self.calls.append(list(argv))

            class P:
                pass
            return P()

        editor_launch.subprocess.Popen = fake
        self.addCleanup(setattr, editor_launch.subprocess, "Popen", real_popen)

    def _reveal(self, path, platform="win32", name="nt"):
        with mock.patch.object(sys, "platform", platform), \
                mock.patch.object(os, "name", name):
            return self.editor_launch.reveal_in_file_manager(path)

    # -- Windows -----------------------------------------------------------

    def test_a_directory_is_opened_not_selected(self):
        ok, err = self._reveal(self.dir)
        self.assertTrue(ok, err)
        self.assertEqual(self.calls, [["explorer", self.dir]])

    def test_a_file_is_still_selected(self):
        # The working case must keep working: /select, highlights the file
        # inside its folder, which is what "reveal" should mean.
        ok, err = self._reveal(self.file)
        self.assertTrue(ok, err)
        self.assertEqual(self.calls, [["explorer", "/select," + self.file]])

    def test_a_trailing_separator_does_not_break_it(self):
        # Same silent fallback as the directory case, and just as invisible.
        ok, err = self._reveal(self.dir + os.sep)
        self.assertTrue(ok, err)
        self.assertEqual(self.calls, [["explorer", self.dir]])

    def test_forward_slashes_are_normalised(self):
        # Explorer cannot parse a forward-slash path either -- and paths reach
        # this function from env vars and config as often as from os.path.
        ok, err = self._reveal(self.dir.replace("\\", "/"))
        self.assertTrue(ok, err)
        self.assertEqual(self.calls, [["explorer", os.path.normpath(self.dir)]])

    # -- the guard ---------------------------------------------------------

    def test_a_missing_path_is_refused_rather_than_launched(self):
        # The third route to a wrong window. compile_dialog already shows
        # `err` in a message box, so refusing is strictly more informative
        # than opening Documents and returning success.
        ok, err = self._reveal(os.path.join(self.dir, "nope", "gone.txt"))
        self.assertFalse(ok)
        self.assertIn("no such path", err)
        self.assertEqual(self.calls, [])

    # -- the other platforms are unchanged ---------------------------------

    def test_macos_uses_open_dash_r_for_both_kinds(self):
        # `open -R` already handles a file and a directory alike.
        self._reveal(self.dir, platform="darwin", name="posix")
        self._reveal(self.file, platform="darwin", name="posix")
        self.assertEqual(self.calls,
                         [["open", "-R", self.dir], ["open", "-R", self.file]])

    def test_linux_opens_the_containing_folder(self):
        self._reveal(self.file, platform="linux", name="posix")
        self.assertEqual(self.calls, [["xdg-open", self.dir]])

    def test_linux_opens_a_directory_target_directly(self):
        # Previously this took os.path.dirname of a directory, landing one
        # level too high.
        self._reveal(self.dir, platform="linux", name="posix")
        self.assertEqual(self.calls, [["xdg-open", self.dir]])
