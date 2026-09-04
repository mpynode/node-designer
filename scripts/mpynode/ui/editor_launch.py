"""Launch an external editor at file:line, and reveal files in the OS file
manager. Detached / fire-and-forget (subprocess.Popen), never blocking."""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys


def reveal_label() -> str:
    if sys.platform == "darwin":
        return "Reveal in Finder"
    if os.name == "nt":
        return "Reveal in Explorer"
    return "Reveal in File Manager"


# macOS app-bundle CLI locations. GUI Maya launched from the Dock inherits a
# MINIMAL PATH (no /usr/local/bin, no Homebrew, no editor bundles), so
# `shutil.which("code")` fails even when the editor is installed.
_MAC_EDITOR_APP_BINS = (
    "/Applications/Visual Studio Code.app/Contents/Resources/app/bin",
    "/Applications/VSCodium.app/Contents/Resources/app/bin",
    "/Applications/Cursor.app/Contents/Resources/app/bin",
    "/Applications/Sublime Text.app/Contents/SharedSupport/bin",
    "/Applications/PyCharm.app/Contents/MacOS",
    "/Applications/PyCharm CE.app/Contents/MacOS",
)


def _augmented_search_path() -> str:
    """A PATH for locating editor CLIs that doesn't depend on Maya's inherited
    (often minimal) environment PATH."""
    parts = [p for p in (os.environ.get("PATH") or "").split(os.pathsep) if p]
    if sys.platform == "darwin":
        parts += ["/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]
        for d in _MAC_EDITOR_APP_BINS:
            parts.append(d)
            # Also the user-local ~/Applications copy of each bundle.
            parts.append(os.path.expanduser("~" + d))
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return os.pathsep.join(out)


def _resolve_editor_exe(name):
    """Absolute path to the editor executable, or None if it can't be found.
    An absolute template command is honored as-is (if it exists); a bare name
    is resolved against the augmented search path (see above)."""
    if os.path.isabs(name):
        return name if os.path.exists(name) else None
    return shutil.which(name, path=_augmented_search_path())


# (cli_name, command_template) in PREFERENCE order; first name that resolves
# against the augmented path wins. `cursor` precedes `code` because Cursor ships
# BOTH a native `cursor` and a VS Code-compat `code` shim -- prefer the native.
_DETECTABLE_EDITORS = (
    ("cursor", "cursor --goto {file}:{line}"),
    ("code", "code --goto {file}:{line}"),
    ("codium", "codium --goto {file}:{line}"),
    ("subl", "subl {file}:{line}"),
    ("pycharm", "pycharm --line {line} {file}"),
)

# Last-resort default. `code` still resolves to any VS Code-family bundle
# (incl. Cursor) via the augmented path, so this degrades gracefully.
_DEFAULT_EDITOR_COMMAND = "code --goto {file}:{line}"


def detect_default_editor_command():
    """Best-guess open-in-editor command for whatever editor is installed.

    Probes the known editor CLIs (see ``_DETECTABLE_EDITORS``) against the
    augmented search path and returns the first that resolves; falls back to the
    VS Code ``code`` command when none are found. Cheap (path lookups only) and
    never raises -- safe to call on demand (never at import). This is what an
    EMPTY ``external_editor_command`` pref resolves to, so a fresh install opens
    the user's actual editor without any configuration."""
    for name, template in _DETECTABLE_EDITORS:
        try:
            if _resolve_editor_exe(name):
                return template
        except Exception:
            continue
    return _DEFAULT_EDITOR_COMMAND


def open_in_editor(path, line):
    """Launch the external editor (external_editor_command pref) at path:line.
    Returns (ok, error_message_or_None). Never raises."""
    from mpynode.ui import preferences
    from mpynode.native.toolchain import toolchain

    # An empty pref means "auto-detect": pick whatever editor is installed.
    template = preferences.get_pref("external_editor_command") \
        or detect_default_editor_command()
    try:
        parts = shlex.split(template, posix=(os.name != "nt"))
    except ValueError as exc:
        return False, "bad external_editor_command: %s" % exc
    if not parts:
        return False, "external_editor_command is empty"
    argv = [p.replace("{file}", str(path)).replace("{line}", str(int(line)))
            for p in parts]
    exe = _resolve_editor_exe(argv[0])
    if exe is None:
        return False, (
            "could not find %r. GUI Maya may not see your shell PATH -- set an "
            "ABSOLUTE command in Preferences > Editor > Open-in-editor command, "
            "e.g. /Applications/Cursor.app/Contents/Resources/app/bin/code "
            "--goto {file}:{line}" % argv[0])
    argv[0] = exe
    try:
        subprocess.Popen(argv, **toolchain.no_window_kwargs())
    except (OSError, ValueError) as exc:
        return False, "could not launch %r: %s" % (argv[0], exc)
    return True, None


def reveal_in_file_manager(path):
    """Reveal `path` in the OS file manager. Returns (ok, err). Never raises.

    Accepts a file OR a directory. That distinction is the whole point on
    Windows: ``explorer /select,`` names a child to highlight, so handing it a
    DIRECTORY does not open that directory -- Explorer cannot act on the
    argument and silently falls back to its default location, which for most
    people is Documents. It reports nothing, and ``explorer.exe`` exits 1 even
    on success, so there is no return code to check either. The result was a
    reveal that looked like it worked and went somewhere else entirely.

    Two of the three callers hand this a directory: the template gallery
    always passes ``TemplateEntry.folder``, and the compile dialog passes its
    AI output dir when there is no report file. So a directory gets
    ``explorer <dir>`` (open it) and only a file gets ``/select,``.

    ``normpath`` first because a trailing separator or a forward slash
    produces exactly the same silent fallback, and a missing path is refused
    outright rather than launched -- that is the third route to a wrong
    window, and the compile dialog already surfaces ``err`` in a message box.
    """
    from mpynode.native.toolchain import toolchain
    kw = toolchain.no_window_kwargs()
    target = os.path.normpath(str(path))
    if not os.path.exists(target):
        return False, "no such path: %s" % target
    try:
        if sys.platform == "darwin":
            # `open -R` already handles both a file and a directory.
            subprocess.Popen(["open", "-R", target], **kw)
        elif os.name == "nt":
            if os.path.isdir(target):
                subprocess.Popen(["explorer", target], **kw)
            else:
                subprocess.Popen(["explorer", "/select," + target], **kw)
        else:
            folder = target if os.path.isdir(target) else os.path.dirname(target)
            subprocess.Popen(["xdg-open", folder or "."], **kw)
    except (OSError, ValueError) as exc:
        return False, str(exc)
    return True, None
