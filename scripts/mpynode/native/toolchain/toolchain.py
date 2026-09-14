"""Single source of truth for every platform/compiler decision in the native
compile pipeline.

Before this module the macOS clang recipe (``-std=c++17 -arch arm64 -bundle -D
OSMac_ ...``) was copy-pasted across ``porter.compile_cpp``, ``bundler`` and
``codegen.generate_build_sh``. Porting to Windows meant editing four places in
lock-step. Everything platform-specific now lives here:

  * plugin extension          ``.bundle`` / ``.mll`` / ``.so``
  * object extension          ``.o``      / ``.obj``
  * the Maya preprocessor define   ``OSMac_`` / ``NT_PLUGIN`` / ``LINUX``
  * the Maya lib directory    ``Maya.app/Contents/MacOS`` / ``lib``
  * the default compiler      ``clang++`` / ``cl`` / ``g++``
  * compile/link argv builders for the clang/gcc ("unix") and MSVC families
  * the MSVC build environment (captured from ``vcvarsall.bat``)
  * the ``mayapy`` executable path

DESIGN CONTRACT (pinned by ``_tests/test_toolchain.py``): on macOS the argv this
module builds is BYTE-FOR-BYTE the recipe the call sites used before the
refactor, so routing them through here is a no-op on the working platform. The
Windows (MSVC) path is new -- its argv shape is unit-asserted here, but it is
compiled/verified only on a Windows host (see ``docs/PORTING.md``).

Every OS-dependent function takes an explicit ``os_name`` (defaulting to the
running platform) so the whole matrix is testable from any host.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Platform identity
# ---------------------------------------------------------------------------


def current_os(os_name: Optional[str] = None) -> str:
    """Normalize a platform name to one of ``darwin`` / ``win32`` / ``linux``.

    ``os_name`` defaults to ``sys.platform``. Anything that is not macOS or
    Windows (``linux``, ``linux2``, the BSDs ...) collapses to ``linux`` so the
    unix/gcc path is the catch-all.
    """
    name = os_name if os_name is not None else sys.platform
    if name.startswith("darwin"):
        return "darwin"
    if name.startswith("win"):
        return "win32"
    return "linux"


def is_windows(os_name: Optional[str] = None) -> bool:
    return current_os(os_name) == "win32"


def is_macos(os_name: Optional[str] = None) -> bool:
    return current_os(os_name) == "darwin"


def is_linux(os_name: Optional[str] = None) -> bool:
    return current_os(os_name) == "linux"


# ---------------------------------------------------------------------------
# File-name conventions
# ---------------------------------------------------------------------------

_PLUGIN_EXT = {"darwin": ".bundle", "win32": ".mll", "linux": ".so"}
_OBJECT_EXT = {"darwin": ".o", "win32": ".obj", "linux": ".o"}
_MAYA_DEFINE = {"darwin": "OSMac_", "win32": "NT_PLUGIN", "linux": "LINUX"}
_DEFAULT_COMPILER = {"darwin": "clang++", "win32": "cl", "linux": "g++"}
_DEFAULT_MAYA = {
    "darwin": "/Applications/Autodesk/maya2026",
    "win32": r"C:\Program Files\Autodesk\Maya2026",
    "linux": "/usr/autodesk/maya2026",
}


def plugin_ext(os_name: Optional[str] = None) -> str:
    """Maya plugin file extension for the platform."""
    return _PLUGIN_EXT[current_os(os_name)]


def object_ext(os_name: Optional[str] = None) -> str:
    """Compiled object-file extension for the platform."""
    return _OBJECT_EXT[current_os(os_name)]


def maya_define(os_name: Optional[str] = None) -> str:
    """The platform preprocessor define Maya headers expect."""
    return _MAYA_DEFINE[current_os(os_name)]


def default_compiler(os_name: Optional[str] = None) -> str:
    """The conventional C++ compiler driver for the platform."""
    return _DEFAULT_COMPILER[current_os(os_name)]


def default_maya_dir(os_name: Optional[str] = None) -> str:
    """The conventional Maya install root for the platform."""
    return _DEFAULT_MAYA[current_os(os_name)]


def mac_arch() -> str:
    """The ``-arch`` value for a macOS build = this machine's architecture.

    Apple Silicon -> ``arm64`` (identical to the old hard-coded value), Intel ->
    ``x86_64`` (the old code hard-coded ``arm64``, which silently produced an
    un-loadable binary on Intel Macs -- this is the latent fix).
    """
    m = platform.machine()
    return "x86_64" if m in ("x86_64", "AMD64", "i386") else m  # arm64 stays arm64


# ---------------------------------------------------------------------------
# Maya directories
# ---------------------------------------------------------------------------


def maya_include_dir(maya: str) -> str:
    """Maya devkit include dir (same layout on every platform)."""
    return os.path.join(maya, "include")


def maya_lib_dir(maya: str, os_name: Optional[str] = None) -> str:
    """Directory holding the Maya import/link libraries.

    macOS keeps the dylibs inside the app bundle
    (``Maya.app/Contents/MacOS``); Windows and Linux use ``<maya>/lib``.
    """
    if is_macos(os_name):
        return os.path.join(maya, "Maya.app", "Contents", "MacOS")
    return os.path.join(maya, "lib")


def maya_frameworks_dir(maya: str, os_name: Optional[str] = None) -> str:
    """Directory that holds the Qt frameworks/libs a hover-capable locator links.

    macOS keeps the Qt frameworks inside the app bundle
    (``Maya.app/Contents/Frameworks`` -- ``QtCore.framework`` etc.); Linux ships
    the Qt ``.so`` in ``<maya>/lib`` (same as the Maya libs); Windows keeps the
    ``Qt6*.dll`` in ``<maya>/bin`` (import ``.lib`` in ``<maya>/lib``).
    """
    if is_macos(os_name):
        return os.path.join(maya, "Maya.app", "Contents", "Frameworks")
    if is_windows(os_name):
        return os.path.join(maya, "bin")
    return os.path.join(maya, "lib")


# Qt modules a self-contained hover locator needs: QtWidgets (QWidget), QtGui
# (QCursor), QtCore (transitively, QPoint).
_QT_MODULES = ["QtCore", "QtGui", "QtWidgets"]


# Escape hatch: point this at a directory that CONTAINS ``QtGui/QCursor`` when
# Maya's Qt headers live somewhere ``qt_include_dir`` cannot guess.
QT_INCLUDE_ENV = "MPYNODE_QT_INCLUDE"

# The header that proves a directory really is a Qt include root (it is exactly
# the one the hover locator's service includes).
_QT_INCLUDE_SENTINEL = ("QtGui", "QCursor")


def qt_user_cache_dir(inc: str, names, has_qt) -> Optional[str]:
    """The per-user extraction of the devkit's Qt header zip, made on demand.

    Windows only in practice: the devkit ships ``qt_<ver>-include.zip`` beside
    the Maya headers, and ``<maya>\\include`` is not writable without elevation
    (MEASURED 2026-09-14: 'Permission denied'), so the archive is extracted
    ONCE into ``%LOCALAPPDATA%\\mpynode\\qt_include\\<archive stem>`` -- the same
    folder the generated ``build.bat`` extracts into and searches, so both
    resolvers see one Qt. ``names`` is the listing of ``inc`` (already fetched by
    the caller), ``has_qt`` the sentinel test. Never raises: any failure --
    no ``LOCALAPPDATA``, an unreadable archive, a fake listing under test --
    reads as "not found", exactly as before this cache existed.
    """
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    for name in names:
        low = name.lower()
        if not (low.startswith("qt_") and low.endswith("-include.zip")):
            continue
        cache = os.path.join(base, "mpynode", "qt_include", name[:-4])
        if has_qt(cache):
            return cache
        try:
            import zipfile
            with zipfile.ZipFile(os.path.join(inc, name)) as zf:
                zf.extractall(cache)
        except Exception:
            continue
        if has_qt(cache):
            return cache
    return None


def qt_include_dir(maya: str, _isfile=None, _listdir=None) -> Optional[str]:
    """Directory to put on the header search path so ``#include <QtGui/QCursor>``
    resolves on Linux/Windows, or ``None`` if none can be found.

    ``<maya>/include`` does NOT carry the Qt headers out of the box: the devkit
    ships them as an UNEXTRACTED ``qt_<ver>-include.tar.gz`` beside the other
    include dirs, so nothing resolves until someone extracts it. Resolution
    order: the ``MPYNODE_QT_INCLUDE`` override, then ``<maya>/include`` itself
    and its ``qt``/``Qt`` subdirs, then any other immediate subdirectory of
    ``<maya>/include`` (an archive extracted under its own name). A candidate
    only counts when ``<cand>/QtGui/QCursor`` actually exists, so a wrong
    override is reported as unresolved instead of producing a C1083 later.
    ``_isfile`` / ``_listdir`` are injectable for tests.
    """
    isfile = _isfile or os.path.isfile
    listdir = _listdir or (lambda d: os.listdir(d) if os.path.isdir(d) else [])

    def _has_qt(d):
        return bool(d) and isfile(os.path.join(d, *_QT_INCLUDE_SENTINEL))

    env = os.environ.get(QT_INCLUDE_ENV)
    if env:
        return env if _has_qt(env) else None
    inc = maya_include_dir(maya)
    for cand in (inc, os.path.join(inc, "qt"), os.path.join(inc, "Qt")):
        if _has_qt(cand):
            return cand
    try:
        names = sorted(listdir(inc))
    except Exception:
        names = []
    for name in names:
        cand = os.path.join(inc, name)
        if _has_qt(cand):
            return cand
    # Last: the per-user extraction of the devkit's zip that the generated
    # build.bat also makes and searches (qt_resolver_bat) -- kept in step here so
    # a hand rebuild and the programmatic build cannot disagree about which Qt
    # they compiled against.
    cached = qt_user_cache_dir(inc, names, _has_qt)
    if cached:
        return cached
    return None


# MSVC-only flags Qt 6 REQUIRES of any TU that includes its headers. Kept in ONE
# place because there are four emitters: qt_compile_flags() (the programmatic
# build) and the three hand-runnable build.bat mirrors (build_scripts.
# generate_build_bat, bundler.make_build_bat, bundler.make_single_build_bat).
# The round-1 fix went into qt_compile_flags() alone and the .bat mirrors kept
# emitting a recipe that cannot compile. Both flags MEASURED on Windows
# 2026-08-14:
#   /Zc:__cplusplus -- MSVC leaves __cplusplus at 199711L even under /std:c++17,
#     and Qt's qcompilerdetection.h checks the MACRO rather than the switch, so
#     it hard-errors with C1189 without this.
#   /permissive-    -- Qt static_asserts on it directly:
#     qcompilerdetection.h(1242) C2338 "On MSVC you must pass the /permissive-
#     option to the compiler". Without it MSVC's non-conforming lookup also
#     instantiates std::is_convertible<...,QString> while QString is still only
#     forward-declared (qcontainerfwd.h) -- a second error, C2139. Maya's own
#     devkit headers are /permissive- clean in the same TU, so the "this could
#     break Maya's headers" risk did not materialise.
_QT_MSVC_FLAGS = ["/Zc:__cplusplus", "/permissive-"]


def qt_msvc_flags() -> List[str]:
    """The MSVC-only flags Qt 6 requires -- see :data:`_QT_MSVC_FLAGS`.

    Returns a fresh list so a caller may extend it without mutating the shared
    constant. MSVC-only by construction: no caller adds these off Windows.
    """
    return list(_QT_MSVC_FLAGS)


# MSVC 14.51 (VS 2026 18.6) removed stdext::checked_array_iterator, which Maya
# 2025's Qt 6.5.3 reaches unconditionally on MSVC (qcompilerdetection.h ->
# qvarlengtharray.h lines 379 and 890). MEASURED 2026-09-08: toolset 14.50
# still ships it (99 hits in its <iterator>), 14.51 has 0; animatedText.cpp
# died with C3861/C2065 'stdext' and compiled clean (0 warnings, same .obj) with
# this header force-included. It is self-gated on _MSC_VER >= 1951, so older
# toolsets are untouched. Same four-emitter rule as _QT_MSVC_FLAGS: the
# programmatic build force-includes the copy in this package by absolute path;
# the three .bat mirrors name it BARE (/FI resolves like #include "..."), so
# every shipped build carries a copy beside its sources and the script stays
# host-independent. ship_qt_msvc_compat_header() puts that copy in place.
QT_MSVC_COMPAT_HEADER = "nd_msvc_stdext_compat.h"


def qt_msvc_compat_header_path() -> str:
    """Absolute path of the ``stdext`` compat header shipped in this package."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        QT_MSVC_COMPAT_HEADER)


def ship_qt_msvc_compat_header(dst_dir: str, needs_qt: bool) -> Optional[str]:
    """Copy the compat header beside the sources in ``dst_dir`` when the build
    needs Qt; remove a stale copy when it does not.

    Returns the copy's path, or ``None`` when nothing is shipped. Byte copy on
    purpose: ``tools/regen_build_scripts.py --check`` compares the shipped copy
    byte-for-byte, and a text-mode round trip on a Windows host would rewrite
    the line endings.
    """
    dst = os.path.join(dst_dir, QT_MSVC_COMPAT_HEADER)
    if not needs_qt:
        if os.path.isfile(dst):
            os.remove(dst)
        return None
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copyfile(qt_msvc_compat_header_path(), dst)
    return dst


def qt_compile_flags(maya: str, os_name: Optional[str] = None) -> List[str]:
    """Flags to COMPILE a translation unit that ``#include``s Maya's Qt headers.

    macOS: a framework header search path (``-F<Frameworks>``) so
    ``#include <QtGui/QCursor>`` resolves. Linux/Windows: a header search path
    for the RESOLVED Qt include dir (:func:`qt_include_dir`) -- ``/I`` for MSVC,
    ``-I`` for gcc. Empty when it cannot be resolved; callers gate on
    :func:`qt_include_problem` BEFORE generating a build so that case fails
    loudly instead of at C1083 (best-effort; only macOS is build-verified).
    """
    if is_macos(os_name):
        return ["-F", maya_frameworks_dir(maya, os_name)]
    inc = qt_include_dir(maya)
    if not inc:
        return []
    if is_windows(os_name):
        # Scoped to qt_compile_flags (needs_qt builds only), so nothing without
        # a hover locator changes.
        return qt_msvc_flags() + ["/I", inc,
                                  "/FI", qt_msvc_compat_header_path()]
    return ["-I", inc]


def qt_include_problem(maya: str,
                       os_name: Optional[str] = None) -> Optional[str]:
    """An actionable message when a hover-capable node CANNOT be compiled here
    because Maya's Qt headers are unreachable, else ``None``.

    WINDOWS ONLY. ``None`` on macOS (the frameworks are always inside the app
    bundle) and ``None`` on Linux, which was never gated: g++ also reads
    ``CPLUS_INCLUDE_PATH`` and the distro's own include roots, so a box with Qt
    installed system-wide compiles fine with nothing this resolver can see, and
    refusing there would break a build that used to work (and quote an MSVC
    error code at a g++ user). Linux still gets the ``-I`` from
    :func:`qt_compile_flags` whenever the dir DOES resolve. Also ``None``
    whenever :func:`qt_include_dir` resolves, so the working platform is
    untouched.
    """
    if not is_windows(os_name):
        return None
    if qt_include_dir(maya):
        return None
    return (
        "This plugin contains a hover-capable locator, whose C++ hover service "
        "includes <QtCore/QPoint>, <QtGui/QCursor> and <QtWidgets/QWidget> -- "
        "but Maya's Qt headers could not be found. Looked for 'QtGui/QCursor' "
        "under %r (and its 'qt'/'Qt' subdirectories). The Maya devkit ships "
        "these headers as an UNEXTRACTED archive -- on Windows a .zip, e.g. "
        "'<maya>/include/qt_6.5.3_vc14-include.zip' (confirmed on Maya 2026) -- "
        "so they are on no include "
        "path until it is extracted. Fix: extract that archive so "
        "'<dir>/QtGui/QCursor' exists, then set %s to <dir> (extracting it "
        "directly into %r also works). Refusing to generate a build that would "
        "die at 'C1083: Cannot open include file' partway through."
        % (maya_include_dir(maya), QT_INCLUDE_ENV, maya_include_dir(maya))
    )


def qt_resolver_bat(_os_name: Optional[str] = None) -> List[str]:
    """Batch lines that set ``%QTINC%`` to Maya's Qt include root at RUN time.

    The Windows counterpart to :func:`qt_include_dir`, and the reason the three
    hand-runnable ``build.bat`` mirrors no longer depend on the host that
    GENERATED them. Baking a host-RESOLVED path into the script could only ever
    work when the generating machine was also the running machine, and this
    project is developed on macOS: ``qt_include_dir`` returns ``None`` there, so
    every hover node shipped a build.bat carrying neither the include path nor
    the MSVC flags, and died on Windows at ``C1083: Cannot open include file:
    'QtCore/QPoint'`` -- MEASURED on Windows 2026-08-31 against Maya 2025 + VS
    2022. Resolving at run time is what :func:`maya_resolver_bat` already does
    for ``%MAYA%``; this is the same trick for the header search path.

    Resolution order mirrors :func:`qt_include_dir` EXACTLY, so a hand rebuild
    and the programmatic build cannot disagree about which Qt they compiled
    against: the ``MPYNODE_QT_INCLUDE`` override, then ``%MAYA%\\include`` and
    its ``qt``/``Qt`` subdirs, then any other immediate subdirectory (an archive
    extracted under its own name). ``QtGui\\QCursor`` is the sentinel there and
    here -- exactly the header the hover service includes. A SET-but-wrong
    override is a hard stop rather than a silent fall-through, also matching the
    Python resolver: a typo must not read as "Maya has no Qt headers".

    Emits ``%%D``/``%%~fD`` as its loop variable for the same reason
    :func:`maya_resolver_bat` does -- ``for /d`` assigns inside the loop and is
    read only after it, so no delayed expansion is needed.
    """
    # NOT os.path.join: this writes a WINDOWS script, and joining on a macOS
    # host would emit 'QtGui/QCursor'. The separator has to be literal.
    sentinel = "\\".join(_QT_INCLUDE_SENTINEL)
    inc = "%MAYA%\\include"
    return [
        'set "QTINC=%{0}%"'.format(QT_INCLUDE_ENV),
        # Hard stop on a bad override, before the cheap probes below can mask it.
        'if not "%QTINC%"=="" if not exist "%QTINC%\\{0}" ('.format(sentinel),
        '  echo build.bat: {0} is set to "%QTINC%" but that has no {1} 1>&2'
        .format(QT_INCLUDE_ENV, sentinel),
        '  echo   point it at the directory that CONTAINS QtGui\\, or unset it '
        '1>&2',
        '  exit /b 1',
        ')',
        'if "%QTINC%"=="" if exist "{0}\\{1}" set "QTINC={0}"'
        .format(inc, sentinel),
        'if "%QTINC%"=="" if exist "{0}\\qt\\{1}" set "QTINC={0}\\qt"'
        .format(inc, sentinel),
        'if "%QTINC%"=="" if exist "{0}\\Qt\\{1}" set "QTINC={0}\\Qt"'
        .format(inc, sentinel),
        'if "%QTINC%"=="" (',
        '  for /d %%D in ("{0}\\*") do ('.format(inc),
        '    if exist "%%~fD\\{0}" set "QTINC=%%~fD"'.format(sentinel),
        '  )',
        ')',
        # The devkit ships the Qt headers as an unextracted zip beside the Maya
        # headers, and <maya>\include is not writable without elevation, so the
        # in-place extraction the old message suggested could never work for a
        # normal user (MEASURED 2026-09-14: 'Permission denied'). Extract ONCE
        # into a per-user cache instead and search there. Windows' own tar
        # (System32, bsdtar since Windows 10 1803) reads zips; the tar Git puts
        # on PATH is GNU tar and does NOT, hence the explicit path. PowerShell's
        # Expand-Archive is the fallback. %%D is the loop variable here too,
        # read only after its loop (see the docstring).
        'set "_QTZIP="',
        'set "_QTCACHE="',
        'if "%QTINC%"=="" (',
        '  for %%D in ("{0}\\qt_*-include.zip") do set "_QTZIP=%%~fD"'.format(inc),
        ')',
        'if "%QTINC%"=="" if not "%_QTZIP%"=="" (',
        '  for %%D in ("%_QTZIP%") do set "_QTCACHE=%LOCALAPPDATA%\\mpynode\\qt_include\\%%~nD"',
        ')',
        'if "%QTINC%"=="" if not "%_QTCACHE%"=="" (',
        '  if not exist "%_QTCACHE%\\{0}" ('.format(sentinel),
        '    echo build.bat: extracting the devkit Qt headers once into "%_QTCACHE%" ...',
        '    if not exist "%_QTCACHE%" mkdir "%_QTCACHE%"',
        '    if exist "%SystemRoot%\\System32\\tar.exe" (',
        '      "%SystemRoot%\\System32\\tar.exe" -xf "%_QTZIP%" -C "%_QTCACHE%"',
        '    ) else (',
        '      powershell -NoProfile -ExecutionPolicy Bypass -Command '
        '"Expand-Archive -LiteralPath \'%_QTZIP%\' -DestinationPath \'%_QTCACHE%\' -Force"',
        '    )',
        '  )',
        '  if exist "%_QTCACHE%\\{0}" set "QTINC=%_QTCACHE%"'.format(sentinel),
        ')',
        'if "%QTINC%"=="" (',
        '  echo build.bat: this plugin has a hover locator, whose C++ includes '
        'the Maya 1>&2',
        '  echo   Qt headers -- but none were found under "{0}". 1>&2'
        .format(inc),
        '  echo   The devkit ships them as an UNEXTRACTED archive, e.g. 1>&2',
        '  echo     "{0}\\qt_6.5.3_vc14-include.zip" 1>&2'.format(inc),
        '  echo   which this script extracts by itself into 1>&2',
        '  echo     "%LOCALAPPDATA%\\mpynode\\qt_include\\<archive name>" 1>&2',
        '  echo   so either that archive is missing or the extraction failed. 1>&2',
        '  echo   Fix: extract it anywhere so "<dir>\\{0}" exists, then 1>&2'
        .format(sentinel),
        '  echo     set {0}=^<dir^> 1>&2'.format(QT_INCLUDE_ENV),
        '  exit /b 1',
        ')',
    ]


def link_via_temp_bat(plugin_name: str, dest: str) -> Tuple[List[str], str, List[str]]:
    """Batch lines to link a plug-in in a LOCAL temp folder and copy the result
    to ``dest`` (a batch expression such as ``%HERE%..\\foo.mll``).

    Returns ``(before, out_args, after)``: ``before`` makes the temp folder,
    ``out_args`` is the ``/IMPLIB:... /OUT:...`` pair to splice into the link
    line, ``after`` checks the link status, copies the plug-in into place and
    removes the folder -- import library and export file with it, since nothing
    ever loads a Maya plug-in's import library.

    Why not link in place: the MSVC linker memory-maps its outputs, and on a
    cloud-synced folder (a Google Drive stream, OneDrive) that write never
    completes -- the linker sits on a zero-byte output forever and cannot even
    be killed. MEASURED 2026-09-14, twice, on a Drive-hosted checkout, while the
    same link finished in under a second on C:. A plain copy is fine on such a
    folder, and the object files, which cl writes normally, always were. Shared
    by the three hand-runnable build.bat mirrors so they cannot drift.
    """
    before = [
        "REM Link in a local temp folder, then copy the plug-in into place: the",
        "REM MSVC linker memory-maps its outputs, and on a cloud-synced folder",
        "REM (Google Drive, OneDrive) that write hangs forever. A copy is fine.",
        'set "LINKTMP=%TEMP%\\mpynode_link_%RANDOM%_%RANDOM%"',
        'if exist "%LINKTMP%" rd /s /q "%LINKTMP%"',
        'mkdir "%LINKTMP%"',
    ]
    out_args = ('/IMPLIB:"%LINKTMP%\\{0}.lib" /OUT:"%LINKTMP%\\{0}.mll"'
                .format(plugin_name))
    after = [
        "if errorlevel 1 exit /b 1",
        'copy /Y "%LINKTMP%\\{0}.mll" "{1}" >nul'.format(plugin_name, dest),
        "if errorlevel 1 exit /b 1",
        'rd /s /q "%LINKTMP%" 2>nul',
    ]
    return before, out_args, after


def qt_link_flags(maya: str, os_name: Optional[str] = None) -> List[str]:
    """Flags to LINK a plugin against Maya's Qt + an rpath so it resolves at load.

    macOS: ``-F<Frameworks> -framework QtCore -framework QtGui -framework
    QtWidgets`` plus ``-Wl,-rpath,<Frameworks>`` (Qt binds via ``@rpath``; the
    rpath lets the bundle resolve Qt in batch ``mayapy`` too, not just GUI Maya
    where Qt is already loaded). Linux: ``-L<lib> -lQt6{Core,Gui,Widgets}`` +
    rpath. Windows: the ``Qt6*.lib`` import libs via ``/LIBPATH`` (no rpath).
    Only macOS is build-verified; Linux/Windows are best-effort.
    """
    fw = maya_frameworks_dir(maya, os_name)
    if is_macos(os_name):
        out = ["-F", fw]
        for m in _QT_MODULES:
            out += ["-framework", m]
        out.append("-Wl,-rpath," + fw)
        return out
    if is_windows(os_name):
        out = ["/LIBPATH:" + os.path.join(maya, "lib")]
        out += ["Qt6%s.lib" % m[2:] for m in _QT_MODULES]  # Qt6Core.lib ...
        return out
    # linux
    out = ["-L", fw]
    out += ["-lQt6%s" % m[2:] for m in _QT_MODULES]
    out.append("-Wl,-rpath," + fw)
    return out


def mayapy_path(maya: str, os_name: Optional[str] = None) -> str:
    """Resolve the ``mayapy`` executable from a Maya install dir.

    Tries the macOS, Linux and Windows layouts in turn and returns the first
    that exists. When NONE exists the return value only ever ends up in a
    "mayapy not found at ..." diagnostic, so it falls back to the candidate for
    the RUNNING platform -- quoting the macOS ``Maya.app/Contents/bin`` shape at
    a Windows user sends them looking for a path that never exists there. On
    macOS the result is unchanged. Folded here from the old
    ``compile_controller._mayapy_for`` so there is one resolver.
    """
    cands = [
        os.path.join(maya, "Maya.app", "Contents", "bin", "mayapy"),  # macOS
        os.path.join(maya, "bin", "mayapy"),                          # linux
        os.path.join(maya, "bin", "mayapy.exe"),                      # windows
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    if is_windows(os_name):
        return cands[2]
    if is_linux(os_name):
        return cands[1]
    return cands[0]


# ---------------------------------------------------------------------------
# Installed-version discovery (for multi-version compile)
# ---------------------------------------------------------------------------

_MAYA_SEARCH_DIRS = {
    "darwin": ["/Applications/Autodesk"],
    "win32": [r"C:\Program Files\Autodesk"],
    "linux": ["/usr/autodesk"],
}


def maya_install_search_dirs(os_name: Optional[str] = None) -> List[str]:
    """Parent directories that hold per-version Maya installs on this platform
    (e.g. ``/Applications/Autodesk`` -> ``maya2024``/``maya2026``/...)."""
    return list(_MAYA_SEARCH_DIRS[current_os(os_name)])


def _maya_version_label(label: str) -> str:
    """The 4-digit year out of an install dir name (``maya2026`` -> ``2026``);
    falls back to the whole label if there is no year (custom dir name)."""
    import re

    m = re.search(r"(\d{4})", label)
    return m.group(1) if m else label


def discover_maya_installs(os_name: Optional[str] = None,
                           search_dirs: Optional[List[str]] = None) -> List[dict]:
    """Installed Maya versions usable as native-build targets.

    A target qualifies only if its install root has BOTH a devkit
    (``include/maya``, needed to COMPILE) AND a real ``mayapy`` (needed to
    parity-VERIFY in the matching runtime). This filters out runtime-only
    installs (e.g. ``mayausd``) and devkit-only trees. Returns an ordered (by
    version) list of ``{"label", "version", "root", "mayapy"}``.

    ``search_dirs`` overrides the platform default (used by tests); otherwise
    the platform's Autodesk parent dir(s) are globbed for ``[Mm]aya*``.
    """
    import glob

    dirs = search_dirs if search_dirs is not None else maya_install_search_dirs(os_name)
    found = {}
    for parent in dirs:
        for d in glob.glob(os.path.join(parent, "[Mm]aya*")):
            if not os.path.isdir(d):
                continue
            # devkit headers present? (Maya.app aside, the devkit lives in
            # <root>/include/maya regardless of platform)
            if not os.path.isdir(os.path.join(maya_include_dir(d), "maya")):
                continue
            mp = mayapy_path(d)
            if not os.path.isfile(mp):
                continue
            label = os.path.basename(d.rstrip("/\\"))
            found[os.path.abspath(d)] = {
                "label": label,
                "version": _maya_version_label(label),
                "root": d,
                "mayapy": mp,
            }
    # Sort so year installs order NUMERICALLY and come LAST, with custom-named
    # installs before them -- ``[-1]`` is then always the newest real Maya, never
    # a lexical fluke like "mayaDev".
    return sorted(
        found.values(),
        key=lambda e: ((1, int(e["version"])) if e["version"].isdigit()
                       else (0, e["version"])))


def preferred_maya_dir(os_name: Optional[str] = None) -> str:
    """The Maya root a build should target when the caller names none.

    :func:`default_maya_dir` is the platform's CONVENTIONAL path and nothing
    more -- a constant pinned at one version, so on a machine without that exact
    version it points at nothing. The generated build scripts never had this
    problem: :func:`maya_resolver_bat` / :func:`maya_resolver_sh` discover an
    install at RUN time. The in-process path took the bare constant, and
    MEASURED on Windows 2026-08-31 that meant ``bundler.assemble`` dropped EVERY
    node on a box whose Maya installs are 2022 and 2025 while the pinned default
    ``C:\\Program Files\\Autodesk\\Maya2026`` does not exist -- reported only as
    "dropped", with no reason naming the missing devkit.

    Prefers the newest install :func:`discover_maya_installs` can actually see
    (it sorts year versions numerically and LAST), and falls back to the
    conventional constant, so behaviour on a machine that HAS the pinned version
    is unchanged. Callers that know better still win: the compile dialog resolves
    the RUNNING Maya from ``MAYA_LOCATION`` and passes it explicitly.
    """
    installs = discover_maya_installs(os_name)
    if installs:
        return installs[-1]["root"]
    return default_maya_dir(os_name)


# ---------------------------------------------------------------------------
# Shell mirrors of discover_maya_installs(), emitted INTO the build scripts
# ---------------------------------------------------------------------------
#
# A generated build script must run with NOTHING but a compiler and a Maya
# install -- no python3, no mpynode on sys.path -- so the version lookup is
# spelled in shell rather than shelling back through this module. The search
# roots still come from _MAYA_SEARCH_DIRS above, so there is one place to edit
# when a platform's layout changes.
#
# Precedence, identical in both dialects:
#   1. a version argument     ./build.sh 2026
#   2. $MAYA / %MAYA%         (how bundler.assemble drives these scripts)
#   3. the newest install carrying a devkit
# The argument outranks the environment deliberately: otherwise a stale
# exported MAYA would silently win over an explicit `./build.sh 2024`.


def build_provenance(maya, comment: str = "#") -> List[str]:
    """One comment line naming the Maya install an artifact was built against.

    Records the version LABEL (``maya2026``), never the absolute path, so a
    shipped script carries no machine-specific paths. Empty when unknown.

    Splits on BOTH separators: a Windows root is routinely formatted on a macOS
    host (the .bat is a cross-platform artifact), and ``os.path.basename`` there
    does not treat ``\\`` as one -- it would emit the whole path.
    """
    if not maya:
        return []
    label = str(maya).rstrip("/\\").replace("\\", "/").rsplit("/", 1)[-1]
    return ["%s Built against: %s" % (comment, label)] if label else []


def maya_resolver_sh(os_name: Optional[str] = None) -> List[str]:
    """Bash lines that set ``$MAYA`` from an optional ``$1`` version."""
    out = [
        '_v="${1:-}"',
        'if [ -n "$_v" ] || [ -z "${MAYA:-}" ]; then',
        '  _found=""',
    ]
    for parent in maya_install_search_dirs(os_name):
        # Year-named installs first so the LAST match is the newest real Maya,
        # mirroring the sort in discover_maya_installs(). A bash glob expands
        # sorted, and an unmatched glob stays literal -- the -d test rejects it.
        out += [
            '  for _d in "%s"/[Mm]aya"$_v"[0-9][0-9][0-9][0-9]*; do' % parent,
            '    [ -d "$_d/include/maya" ] && _found="$_d"',
            '  done',
            '  if [ -z "$_found" ]; then',
            '    for _d in "%s"/[Mm]aya"$_v"*; do' % parent,
            '      [ -d "$_d/include/maya" ] && _found="$_d"',
            '    done',
            '  fi',
        ]
    out += [
        '  MAYA="$_found"',
        'fi',
        'if [ ! -d "${MAYA:-}/include/maya" ]; then',
        '  echo "build.sh: no Maya ${_v:-install} with a devkit under '
        '%s" >&2' % " ".join(maya_install_search_dirs(os_name)),
        '  echo "  pass a version:  ./build.sh 2026" >&2',
        '  echo "  or set MAYA:     MAYA=/path/to/maya ./build.sh" >&2',
        '  exit 1',
        'fi',
    ]
    return out


def maya_resolver_bat(os_name: Optional[str] = None) -> List[str]:
    """Batch lines that set ``%MAYA%`` from an optional ``%1`` version.

    ``for /d`` assigns inside the loop and is read only AFTER it, so this needs
    no delayed expansion. The glob is case-insensitive on Windows, so a single
    ``Maya*`` pattern covers ``maya2026`` too.
    """
    out = [
        'set "_V=%~1"',
        'if not "%_V%"=="" set "MAYA="',
        'if "%MAYA%"=="" (',
    ]
    for parent in maya_install_search_dirs(os_name or "win32"):
        out += [
            '  for /d %%%%D in ("%s\\Maya%%_V%%*") do (' % parent,
            '    if exist "%%~fD\\include\\maya" set "MAYA=%%~fD"',
            '  )',
        ]
    out += [
        ')',
        'if not exist "%MAYA%\\include\\maya" (',
        '  echo build.bat: no Maya %%_V%% with a devkit under '
        '"%s" 1>&2' % " ".join(maya_install_search_dirs(os_name or "win32")),
        '  echo   pass a version:  build.bat 2026 1>&2',
        '  echo   or set MAYA:     set "MAYA=C:\\path\\to\\maya" 1>&2',
        '  exit /b 1',
        ')',
    ]
    return out


def msvc_resolver_bat() -> List[str]:
    """Batch lines that make ``cl`` the MSVC toolset the build expects.

    The scripts used to assume an *x64 Native Tools Command Prompt* -- REM'd at
    the top, documented in README.txt, and ignored: run from a plain
    ``cmd.exe`` they failed with whatever ``cl`` happened to be on PATH. On one
    machine that was Visual Studio 2015, which predates ``/std:c++17``,
    ``/permissive-`` and ``/Zc:__cplusplus`` (three ``D9002`` warnings) and,
    with no ``INCLUDE`` set, could not find ``<cmath>``. Nothing in that
    output says "wrong prompt".

    So do in batch what :func:`capture_vcvars_env` does in Python: ask
    ``vswhere`` for the latest install with the C++ tools (the same arguments
    as :func:`find_vcvarsall`, ``-prerelease`` retried second) and ``call
    vcvarsall.bat x64``. That PREPENDS the right ``cl`` to PATH, so a stray
    older one stops winning. Skipped entirely when ``VSCMD_ARG_TGT_ARCH`` is
    already set -- vcvarsall / VsDevCmd export it -- so a developer prompt is
    used exactly as it is rather than having vcvarsall run twice.

    Every generated script opens with ``setlocal``, so what vcvarsall exports
    (PATH, INCLUDE, LIB) and the script's own variables (HERE, OBJS, MAYA,
    QTINC, _VSINST) die with it. MEASURED 2026-09-08: without that, the inner
    ``build\\build.bat`` overwrote the calling wrapper's ``HERE`` through
    ``call``, so ``templates/All Templates Plugin/build.bat`` linked
    mPyMega.mll and then failed its install copy with exit 1.

    Two guards follow, each with the fix in its message: no ``cl`` at all, and
    the case above -- a ``cl`` on PATH but an empty ``INCLUDE``.

    Batch hazards designed around: ``%ProgramFiles(x86)%`` contains ``)``,
    which terminates an ``if (...)`` block, so this is flat with ``goto``
    labels rather than nested; and the loop variable is ``%%D``, the only form
    the percent-collapse test tolerates -- legal here because the two ``for``
    loops are sequential, never nested.
    """
    vswhere = "%ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer\\vswhere.exe"
    query = ("-latest -products * -requires "
             "Microsoft.VisualStudio.Component.VC.Tools.x86.x64 "
             "-property installationPath")
    vcvars = "%_VSINST%\\VC\\Auxiliary\\Build\\vcvarsall.bat"
    return [
        "REM --- MSVC: set up the compiler environment unless this is already a",
        "REM     developer prompt (vcvarsall / VsDevCmd export VSCMD_ARG_TGT_ARCH).",
        'set "_VSWHERE=' + vswhere + '"',
        'set "_VSINST="',
        'if not "%VSCMD_ARG_TGT_ARCH%"=="" goto :msvc_ready',
        'if not exist "%_VSWHERE%" goto :msvc_check',
        'for /f "usebackq delims=" %%D in (`"%_VSWHERE%" ' + query
        + '`) do set "_VSINST=%%D"',
        'if "%_VSINST%"=="" for /f "usebackq delims=" %%D in (`"%_VSWHERE%" '
        '-prerelease ' + query + '`) do set "_VSINST=%%D"',
        # vcvarsall -> VsDevCmd shells `vswhere.exe` by BARE name and prints
        # "'vswhere.exe' is not recognized" to stderr when the Installer dir is
        # not on PATH. Harmless, but every plain-cmd user would see it and read
        # it as a failure -- so put that dir on PATH first.
        'set "PATH=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer;%PATH%"',
        'if exist "' + vcvars + '" call "' + vcvars + '" x64 >nul',
        ":msvc_check",
        "where cl >nul 2>nul",
        "if errorlevel 1 (",
        "  echo build.bat: no MSVC compiler ^(cl^) found. Install Visual Studio "
        "with the 1>&2",
        '  echo   "Desktop development with C++" workload, or run this from an 1>&2',
        "  echo   'x64 Native Tools Command Prompt for VS'. 1>&2",
        "  exit /b 1",
        ")",
        'if "%INCLUDE%"=="" (',
        "  echo build.bat: 'cl' is on PATH but the MSVC environment is not set "
        "up 1>&2",
        "  echo   ^(INCLUDE is empty^) -- that cl is probably a stray older "
        "toolchain. 1>&2",
        "  echo   Run this from an 'x64 Native Tools Command Prompt for VS'. 1>&2",
        "  exit /b 1",
        ")",
        ":msvc_ready",
    ]


# ---------------------------------------------------------------------------
# Compiler family
# ---------------------------------------------------------------------------


def compiler_family(compiler: str) -> str:
    """Classify a compiler driver as ``"msvc"`` or ``"unix"`` (clang/gcc).

    Robust to both path separators regardless of the host OS, so a Windows
    ``cl.exe`` full path classifies correctly even when this runs on macOS.
    """
    base = compiler.replace("\\", "/").rsplit("/", 1)[-1].lower()
    stem = base[:-4] if base.endswith(".exe") else base
    if stem == "cl" or stem.endswith("clang-cl"):
        return "msvc"
    return "unix"


# ---------------------------------------------------------------------------
# argv builders
# ---------------------------------------------------------------------------
#
# Two recipe families. The "unix" builders reproduce the historical macOS clang
# argv EXACTLY (the regression anchor); they also cover Linux/gcc. The "msvc"
# builders target ``cl.exe`` for Windows.

# Defines shared by every Maya TU (mac order preserved: define -> value pairs).
_COMMON_DEFINES = ["REQUIRE_IOSTREAM", "_BOOL"]
# Suppress the duplicated plugin-version symbols in node *fragments* (only
# plugin_main.cpp emits them) -- see bundler._FRAG_DEFINES.
_FRAG_SUPPRESS_DEFINES = ["MNoVersionString", "MNoPluginEntry"]


def _unix_base_defines(os_name: str) -> List[str]:
    """``-D NAME`` token pairs every unix-family Maya TU needs (mac/linux)."""
    return ["-D", maya_define(os_name), "-D", "REQUIRE_IOSTREAM", "-D", "_BOOL"]


_UNIX_FRAG_DEFINES = ["-D", "MNoVersionString", "-D", "MNoPluginEntry"]


def _msvc_defines(os_name: str, frag: bool) -> List[str]:
    """``/D NAME`` token pairs for an MSVC compile.

    ``_CRT_SECURE_NO_WARNINGS`` silences C4996 on the plain-C calls the emitters
    use (the embedded-image stage has three ``getenv`` sites); it changes no
    generated code, only the diagnostic.
    """
    out = ["/D", maya_define(os_name), "/D", "REQUIRE_IOSTREAM", "/D", "_BOOL",
           "/D", "WIN32", "/D", "_WINDOWS",
           "/D", "_CRT_SECURE_NO_WARNINGS"]
    if frag:
        out += ["/D", "MNoVersionString", "/D", "MNoPluginEntry"]
    return out


# Common MSVC compile flags: no logo, C++17, /O2, EXPLICIT /fp:precise,
# exceptions, multithreaded-DLL CRT (must match Maya's), big-object support,
# and /utf-8. /utf-8 is needed because 24 of the generated TUs carry non-ASCII
# comment bytes: without it cl reads the source in the machine's ANSI codepage
# (C4819, and a hard parse error when a lead byte swallows the next char).
# /fp:precise is the MSVC parity lever (the analogue of clang's
# -ffp-contract=off): it forbids FMA contraction + reassociation of `a*b + c` so
# each rounds like numpy. It is normally the default, but pinning it EXPLICITLY
# guards against an inherited env flag or a future flip to /fp:fast, which
# reassociates and would silently break byte-parity.
_MSVC_CXXFLAGS = ["/nologo", "/std:c++17", "/O2", "/fp:precise",
                  "/EHsc", "/MD", "/bigobj", "/utf-8"]


def msvc_link_byproducts(out_plugin: str, one_shot: bool = False) -> List[str]:
    """Files an MSVC link leaves behind that nothing ever loads.

    LINK writes an import library and an export file for any DLL that exports
    symbols -- ours export initializePlugin/uninitializePlugin. ``cl`` picks
    their name itself, ``/implib:<first .obj>.lib``, RELATIVE TO THE CWD: a
    mega build left ``mPyDnet.lib`` + ``mPyDnet.exp`` beside the template, the
    programmatic build left the same pair in Maya's working directory, and one
    suite run left 29 such files at the repo root (MEASURED 2026-09-08). The
    one-shot ``cl /LD src.cpp`` also drops ``src.obj`` in the CWD.

    :func:`compile_to_plugin_cmd` and :func:`link_plugin_cmd` now pin
    ``/IMPLIB:<plugin base>.lib`` (LINK names the .exp after the .lib) and the
    one-shot form pins ``/Fo<plugin base>.obj``; this lists exactly those paths
    so a caller can remove them after the link. The three ``build.bat``
    emitters do the same in batch with a trailing ``del``.
    """
    base = os.path.splitext(out_plugin)[0]
    out = [base + ".lib", base + ".exp"]
    if one_shot:
        out.append(base + ".obj")
    return out


def remove_msvc_link_byproducts(out_plugin: str,
                                one_shot: bool = False) -> List[str]:
    """Delete :func:`msvc_link_byproducts`; returns the paths actually removed.

    Safe everywhere: off MSVC nothing exists to remove, and after a failed link
    whatever LINK got to write goes too. Best effort -- a locked file is left
    behind rather than turning a successful build into a failure.
    """
    removed = []
    for p in msvc_link_byproducts(out_plugin, one_shot):
        try:
            os.remove(p)
        except OSError:
            continue
        removed.append(p)
    return removed


def compile_to_plugin_cmd(compiler: str, src: str, out_plugin: str, *,
                          include_dir: str, lib_dir: str, libs: List[str],
                          os_name: Optional[str] = None,
                          arch: Optional[str] = None,
                          qt: bool = False,
                          optimize: bool = False,
                          maya: Optional[str] = None) -> List[str]:
    """One-shot *compile + link* of a single ``.cpp`` into a Maya plugin.

    This is the single-node ``porter.compile_cpp`` recipe. On macOS with
    ``compiler='clang++'`` the returned argv is identical to the old hard-coded
    list. ``qt=True`` (with ``maya``) additionally compiles+links Maya's Qt
    frameworks (a self-contained hover locator includes QCursor/QWidget) -- the
    framework search + ``-framework Qt*`` + rpath cover both the compile and the
    link in this one-shot. ``qt`` defaults False so every existing caller's argv
    is byte-for-byte unchanged.

    ``optimize=True`` is the AI-optimizer recompile recipe on unix: ``-O3`` plus
    ``-ffp-contract=off``. The latter is REQUIRED -- once the optimizer fuses a
    ``mul`` and an ``add`` into one expression, the default ``-ffp-contract=on``
    would contract them into an FMA and drift ~1 ULP, breaking parity. It never
    adds ``-ffast-math`` (that reassociates and would break parity outright).
    MSVC is left untouched (its parity path is unverified). Defaults False so
    every existing caller's argv is byte-for-byte unchanged.
    """
    osn = current_os(os_name)
    if compiler_family(compiler) == "msvc":
        cmd = [compiler] + list(_MSVC_CXXFLAGS) + ["/LD"]
        cmd += _msvc_defines(osn, frag=False)
        if qt and maya:
            cmd += qt_compile_flags(maya, osn)
        # /Fo and /IMPLIB: see msvc_link_byproducts(). Without them `cl /LD`
        # drops <src>.obj in the CWD and hands LINK `/implib:<src>.lib` (which
        # also decides the .exp name) -- CWD again. Both now land beside the
        # plugin, where remove_msvc_link_byproducts() finds them.
        base = os.path.splitext(out_plugin)[0]
        cmd += ["/I", include_dir, src, "/Fo" + base + ".obj",
                "/link", "/LIBPATH:" + lib_dir]
        cmd += [l + ".lib" for l in libs]
        if qt and maya:
            cmd += qt_link_flags(maya, osn)
        cmd += ["/IMPLIB:" + base + ".lib", "/OUT:" + out_plugin,
                "/EXPORT:initializePlugin", "/EXPORT:uninitializePlugin"]
        return cmd
    # unix family (clang on macOS / gcc on linux). -ffp-contract=off is MANDATORY
    # for byte-parity: clang defaults to =on and would fuse `a*b + c` into one FMA
    # (one rounding instead of two), drifting ~1 ULP from numpy. -O3 over -O2 is
    # measured faster and stays IEEE-correct while contraction is off and
    # -ffast-math is unused. `optimize` is kept for API compatibility but no
    # longer downgrades these base flags -- the old default (-O2 WITHOUT
    # contract=off) produced non-bit-parity binaries.
    cmd = [compiler, "-std=c++17", "-O3", "-ffp-contract=off"]
    if osn == "darwin":
        if arch:
            cmd += ["-arch", arch]
        cmd += ["-bundle"]
    else:  # linux shared object
        cmd += ["-shared", "-fPIC"]
    cmd += _unix_base_defines(osn)
    cmd += ["-Wno-nontrivial-memcall",
            "-I", include_dir,
            "-L", lib_dir]
    cmd += ["-l" + l for l in libs]
    if qt and maya:
        # The -F in qt_link_flags also makes the Qt headers resolve for the
        # compile half of this one-shot, so it covers both.
        cmd += qt_link_flags(maya, osn)
    cmd += ["-o", out_plugin, src]
    return cmd


def compile_object_cmd(compiler: str, src: str, obj: str, *,
                       include_dir: str, frag: bool = True,
                       os_name: Optional[str] = None,
                       arch: Optional[str] = None,
                       qt: bool = False,
                       maya: Optional[str] = None) -> List[str]:
    """Compile one ``.cpp`` to an object file (``-c`` / ``/c``).

    Used by the multi-node bundler. ``frag=True`` adds the plugin-version
    suppression defines (node fragments); ``plugin_main.cpp`` is compiled with
    ``frag=False`` so it carries the single copy of those symbols. ``qt=True``
    (with ``maya``) adds the Qt header search path so a hover-locator fragment's
    ``#include <QtGui/QCursor>`` resolves. ``qt`` defaults False -> byte-identical.

    On macOS with ``compiler='clang++'`` and ``qt=False`` the argv matches the
    old bundler fragment recipe exactly, including the single-token ``-I<dir>``.
    """
    osn = current_os(os_name)
    if compiler_family(compiler) == "msvc":
        cmd = [compiler] + list(_MSVC_CXXFLAGS) + ["/c"]
        cmd += _msvc_defines(osn, frag)
        if qt and maya:
            cmd += qt_compile_flags(maya, osn)
        cmd += ["/I", include_dir, src, "/Fo" + obj]
        return cmd
    # unix family: -std=c++17 -O3 -ffp-contract=off (MANDATORY for byte parity)
    # THEN -arch, the base + frag-suppress defines, -Wno-nontrivial-memcall, then
    # the single-token -I<dir>.
    cmd = [compiler, "-std=c++17", "-O3", "-ffp-contract=off"]
    if osn == "darwin" and arch:
        cmd += ["-arch", arch]
    cmd += _unix_base_defines(osn)
    cmd += ["-Wno-nontrivial-memcall"]
    if frag:
        cmd += _UNIX_FRAG_DEFINES
    if qt and maya:
        cmd += qt_compile_flags(maya, osn)
    cmd += ["-I" + include_dir, "-c", src, "-o", obj]
    return cmd


def link_plugin_cmd(compiler: str, objs: List[str], out_plugin: str, *,
                    lib_dir: str, libs: List[str],
                    os_name: Optional[str] = None,
                    arch: Optional[str] = None,
                    qt: bool = False,
                    maya: Optional[str] = None) -> List[str]:
    """Link object files into the final Maya plugin (multi-node bundler).

    ``qt=True`` (with ``maya``) links Maya's Qt frameworks + an rpath so a bundle
    containing a hover locator resolves Qt at load. ``qt`` defaults False so the
    existing argv is byte-for-byte unchanged.
    """
    osn = current_os(os_name)
    if compiler_family(compiler) == "msvc":
        cmd = [compiler, "/nologo", "/LD"] + list(objs)
        cmd += ["/link", "/LIBPATH:" + lib_dir]
        cmd += [l + ".lib" for l in libs]
        if qt and maya:
            cmd += qt_link_flags(maya, osn)
        # /IMPLIB: cl would otherwise name it after the FIRST object
        # (mPyDnet.lib) and LINK writes it, plus the .exp, into the CWD. See
        # msvc_link_byproducts().
        cmd += ["/IMPLIB:" + os.path.splitext(out_plugin)[0] + ".lib",
                "/OUT:" + out_plugin,
                "/EXPORT:initializePlugin", "/EXPORT:uninitializePlugin"]
        return cmd
    cmd = [compiler, "-std=c++17"]
    if osn == "darwin":
        if arch:
            cmd += ["-arch", arch]
        cmd += ["-bundle"]
    else:
        cmd += ["-shared", "-fPIC"]
    cmd += ["-L", lib_dir]
    cmd += ["-l" + l for l in libs]
    if qt and maya:
        cmd += qt_link_flags(maya, osn)
    cmd += list(objs) + ["-o", out_plugin]
    return cmd


# ---------------------------------------------------------------------------
# Build environment (MSVC / vcvars)
# ---------------------------------------------------------------------------


def _parse_set_output(text: str) -> Dict[str, str]:
    """Parse the output of ``cmd /c set`` (``KEY=VALUE`` per line) into a dict.

    Lines without ``=`` are ignored; the first ``=`` splits key from value so
    values may themselves contain ``=``.
    """
    env: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key:
            env[key] = val.rstrip("\r")
    return env


def find_vswhere() -> Optional[str]:
    """Locate ``vswhere.exe`` (ships in a fixed location with VS 2017+)."""
    pf86 = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
    if not pf86:
        return None
    cand = os.path.join(pf86, "Microsoft Visual Studio", "Installer",
                        "vswhere.exe")
    return cand if os.path.isfile(cand) else None


def find_vcvarsall(_runner=None, _isfile=None) -> Optional[str]:
    """Find ``vcvarsall.bat`` via vswhere (latest install with the C++ tools).

    Tries a STABLE install first, then retries WITH ``-prerelease`` so a Visual
    Studio *preview* (e.g. the "18"/2026 preview, whose 14.51 toolset vswhere
    hides by default) is also found. If the preview is the only/usable install,
    skipping ``-prerelease`` makes capture fail -> the build falls back to a
    stray PATH ``cl.exe`` while INCLUDE points at the newest toolset -> the
    STL1001 "Unexpected compiler version" mismatch. ``_runner(cmd) -> str`` and
    ``_isfile`` are injectable for testing.
    """
    vswhere = find_vswhere()
    if not vswhere:
        return None
    runner = _runner or (lambda c: subprocess.check_output(c, text=True))
    isfile = _isfile or os.path.isfile
    base = [
        vswhere, "-latest", "-products", "*",
        "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
        "-property", "installationPath",
    ]
    for args in (base, base + ["-prerelease"]):
        try:
            install = runner(args).strip()
        except Exception:
            install = ""
        if not install:
            continue
        cand = os.path.join(install, "VC", "Auxiliary", "Build",
                            "vcvarsall.bat")
        if isfile(cand):
            return cand
    return None


_VCVARS_ENV_CACHE: Dict[str, Dict[str, str]] = {}


def vs_installer_on_path(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """A copy of ``env`` (default ``os.environ``) with the Visual Studio
    Installer directory prepended to PATH.

    ``vcvarsall.bat`` hands off to ``VsDevCmd.bat``, which shells ``vswhere.exe``
    by BARE name. From a process whose PATH lacks
    ``%ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer`` -- mayapy, Maya,
    a plain cmd -- every capture printed "'vswhere.exe' is not recognized as an
    internal or external command" to stderr. Harmless (vcvarsall falls back to
    its own install root) but it reads like a failure in the script editor.
    The generated ``build.bat`` prepends the same directory before it calls
    vcvarsall (:func:`msvc_resolver_bat`); this is the Python-side twin.
    Returns an unchanged copy when vswhere cannot be located, and never adds
    the directory twice.
    """
    out = dict(os.environ if env is None else env)
    vswhere = find_vswhere()
    if vswhere:
        inst = os.path.dirname(vswhere)
        path = out.get("PATH", "")
        if inst.lower() not in [p.lower() for p in path.split(os.pathsep)]:
            out["PATH"] = inst + (os.pathsep + path if path else "")
    return out


def capture_vcvars_env(arch: str = "x64", vcvarsall: Optional[str] = None,
                       _runner=None) -> Optional[Dict[str, str]]:
    """Capture the environment ``vcvarsall.bat <arch>`` sets, as a dict.

    Runs ``cmd /c "<vcvarsall> <arch> && set"`` and parses the trailing ``set``
    dump. Cached per ``arch``. ``_runner(cmd) -> str`` is injectable for tests.
    Returns ``None`` if VS can't be located.
    """
    if arch in _VCVARS_ENV_CACHE:
        return _VCVARS_ENV_CACHE[arch]
    bat = vcvarsall or find_vcvarsall()
    if not bat:
        return None
    # Pass the whole "<vcvarsall> <arch> && set" as a STRING under shell=True.
    # A list ["cmd","/c", "...&&..."] would get re-quoted by list2cmdline and
    # break the && chaining; the string form is the proven pattern (cf.
    # setuptools' _get_vc_env). ``_runner`` is injected in tests.
    cmd = '"%s" %s && set' % (bat, arch)
    runner = _runner or (lambda c: subprocess.check_output(
        c, shell=True, text=True, env=vs_installer_on_path()))
    try:
        out = runner(cmd)
    except Exception:
        return None
    env = _parse_set_output(out)
    if not env:
        return None
    merged = dict(os.environ)
    merged.update(env)
    _VCVARS_ENV_CACHE[arch] = merged
    return merged


def build_env(compiler: str, arch: str = "x64",
              _runner=None) -> Optional[Dict[str, str]]:
    """Environment dict to run ``compiler`` under, or ``None`` to inherit.

    Unix compilers inherit the ambient environment (``None``). MSVC needs the
    ``vcvars`` environment (INCLUDE/LIB/PATH for the toolset); this returns that
    captured dict so ``cl.exe`` resolves headers and import libs.
    """
    if compiler_family(compiler) != "msvc":
        return None
    return capture_vcvars_env(arch=arch, _runner=_runner)


def in_developer_shell(env: Optional[Dict[str, str]] = None) -> bool:
    """True if the ambient environment already has an MSVC toolset activated.

    A "Developer Command Prompt" / "x64 Native Tools Command Prompt for VS" sets
    ``VCToolsInstallDir`` (and ``VCINSTALLDIR``). When that is the case it is
    legitimate to compile with the ambient ``cl`` (its INCLUDE/LIB are already
    consistent), even if our own ``vcvarsall`` capture failed -- so the
    "refuse a stray PATH cl" guard must not fire here.
    """
    e = os.environ if env is None else env
    return bool(e.get("VCToolsInstallDir") or e.get("VCINSTALLDIR"))


def vcvars_unavailable_message(compiler: str) -> str:
    """Message for "MSVC is installed-ish but its build environment could not be
    captured, so we refuse to compile with a stray system-PATH compiler."""
    return (
        "The Visual Studio C++ build environment could not be captured "
        "(vcvarsall.bat was not found or failed to run). Refusing to compile "
        "with a %r found on the system PATH, because it may not match the "
        "installed MSVC headers -- a mismatched compiler causes "
        "'STL1001: Unexpected compiler version'. Fix: install or repair Visual "
        "Studio with the 'Desktop development with C++' workload, or launch Maya "
        "from the 'x64 Native Tools Command Prompt for VS'. Download: "
        "https://visualstudio.microsoft.com/downloads/" % compiler
    )


# Known compiler-error patterns -> a plain-English hint appended to the failure.
_COMPILER_LOG_HINTS = (
    ("STL1001",
     "The C++ compiler (cl.exe) being used is OLDER than the installed MSVC STL "
     "headers -- they are from different toolset versions. This usually means a "
     "stray, older cl.exe is on your system PATH. Remove it so the build uses "
     "the matching Visual Studio toolset (run the win_compile_doctor to confirm "
     "which cl.exe is being used), or install/repair the MSVC C++ toolset so the "
     "compiler and headers match."),
    ("QtGui/QCursor",
     "This node's hover service includes Maya's Qt headers, and the compiler "
     "could not find them. Maya's devkit ships them as an UNEXTRACTED archive "
     "(Windows: '<maya>/include/qt_6.5.3_vc14-include.zip'; macOS/Linux: a "
     "'qt_*-include.tar.gz'). Extract it so "
     "'<dir>/QtGui/QCursor' exists, then set MPYNODE_QT_INCLUDE to <dir> and "
     "recompile."),
    # The next two are the cl-vs-WINDOWS-SDK mismatch, which is NOT what
    # diagnose_toolset_mismatch/STL1001 detect: that compares cl's MSVC toolset
    # against the MSVC STL headers on INCLUDE and says nothing about the Windows
    # Kits UCRT. MEASURED on Windows 2026-08-31: a VS 2015 x64 Native Tools
    # prompt (cl 19.00) paired with Windows SDK 10.0.28000.0 -- its own
    # vcvarsall picks the NEWEST installed SDK -- produced both of these and
    # matched no hint at all, so the failure dialog stayed cryptic.
    ("D9002",
     "The C++ compiler (cl.exe) is too OLD for this build: it does not "
     "recognise '/std:c++17', a switch that arrived in Visual Studio 2017 "
     "15.3, so it silently fell back to C++14 and the sources will not "
     "compile. You are almost certainly in an old 'x64 Native Tools Command "
     "Prompt' (e.g. VS 2015). Launch the one for VS 2019 or newer -- Maya 2025 "
     "and 2026 are built with VS 2022 -- or remove the stray old cl.exe from "
     "PATH."),
    ("_mm_loadu_si64",
     "The C++ compiler (cl.exe) is OLDER than the installed Windows SDK. The "
     "UCRT's own <wchar.h> uses the '_mm_loadu_si64' intrinsic, which MSVC only "
     "gained in Visual Studio 2019 16.7, so the C runtime headers cannot be "
     "parsed at all and the error points into wchar.h rather than at your code. "
     "Note vcvarsall selects the NEWEST installed SDK, so an old prompt plus a "
     "current SDK always lands here. Launch the 'x64 Native Tools Command "
     "Prompt' for VS 2019 or newer (VS 2022 for Maya 2025/2026)."),
    ("C2337",
     "A variable in the generated C++ collides with a Windows SAL annotation "
     "macro. sal.h defines ~423 object-like macros whose names start with a "
     "double underscore -- '__out', '__in', '__inout' and friends -- so "
     "'MPoint* __out = ...' preprocesses to 'MPoint* [SA_annotation] = ...', "
     "which MSVC reports as C2337 'attribute not found' plus a bogus C4467 "
     "'ATL attributes are deprecated'. clang has no sal.h, so this compiles "
     "cleanly on macOS. Rename the variable (the transpiler's other "
     "double-underscore temporaries -- __i, __L0, __s0 -- do not collide)."),
)


def diagnose_compiler_log(log: Optional[str]) -> Optional[str]:
    """Return an actionable hint for a known compiler-error pattern in ``log``,
    else ``None``. Lets the pipeline turn a cryptic error (e.g. STL1001) into a
    plain-English next step in the failure dialog."""
    if not log:
        return None
    for token, hint in _COMPILER_LOG_HINTS:
        if token in log:
            return hint
    return None


# MSVC lays its toolset out as ``...\VC\Tools\MSVC\<version>\...``: cl.exe under
# ``<version>\bin``, STL headers under ``<version>\include``. STL1001 fires when
# those versions differ (compiler older than headers), so these helpers compare
# them and name the mismatch instead of a cryptic ``static_assert``. Anchored on
# the full ``VC\Tools\MSVC\<ver>`` structure (not a bare ``\MSVC\``) so an
# unrelated folder named MSVC cannot raise a false alarm.
_MSVC_TOOLSET_RE = re.compile(
    r"[\\/]Tools[\\/]MSVC[\\/]([0-9][0-9.]*)[\\/]", re.IGNORECASE)
_MSVC_INCLUDE_RE = re.compile(
    r"[\\/]Tools[\\/]MSVC[\\/]([0-9][0-9.]*)[\\/][^;]*include", re.IGNORECASE)


def msvc_toolset_from_path(path: Optional[str]) -> Optional[str]:
    """The MSVC toolset version (e.g. ``14.44.35207``) embedded in a cl.exe
    path, or ``None`` if the path isn't under a ``...\\MSVC\\<ver>\\...`` tree."""
    if not path:
        return None
    m = _MSVC_TOOLSET_RE.search(str(path))
    return m.group(1) if m else None


def msvc_toolsets_from_include(include: Optional[str]) -> list:
    """The MSVC toolset versions referenced by ``...\\MSVC\\<ver>\\...include``
    entries in an ``INCLUDE`` string, in first-seen order, deduped. ``[]`` if
    none (e.g. a Windows-Kits-only INCLUDE, or empty/None)."""
    if not include:
        return []
    out = []
    for m in _MSVC_INCLUDE_RE.finditer(str(include)):
        ver = m.group(1)
        if ver not in out:
            out.append(ver)
    return out


def diagnose_toolset_mismatch(cl_path: Optional[str],
                              include: Optional[str]) -> Optional[str]:
    """Hint if the cl.exe that will run is from a DIFFERENT MSVC toolset than the
    C++ headers on ``INCLUDE`` -- the exact STL1001 condition -- else ``None``.

    Returns ``None`` when it can't tell (no toolset parseable from the cl path,
    or no MSVC headers on INCLUDE) so it never raises a false alarm. When the
    compiler's toolset IS among the INCLUDE toolsets they are consistent and the
    result is ``None``.
    """
    cl_ver = msvc_toolset_from_path(cl_path)
    inc_vers = msvc_toolsets_from_include(include)
    if not cl_ver or not inc_vers:
        return None
    if cl_ver in inc_vers:
        return None
    return (
        "MSVC toolset MISMATCH: the cl.exe that will run is toolset %s, but the "
        "C++ headers on INCLUDE are from toolset(s) %s. A compiler older than "
        "its STL headers fails with 'STL1001: Unexpected compiler version'. "
        "This usually means a stray, older cl.exe is ahead on your PATH. Remove "
        "it (or launch from the matching 'x64 Native Tools Command Prompt for "
        "VS') so the compiler and headers come from the SAME toolset."
        % (cl_ver, ", ".join(inc_vers)))


# ---------------------------------------------------------------------------
# Subprocess no-window flag (Windows console-app hygiene)
# ---------------------------------------------------------------------------


def no_window_kwargs(os_name: Optional[str] = None) -> Dict[str, object]:
    """``subprocess`` kwargs that suppress a flashing console window on Windows.

    Returns ``{"creationflags": CREATE_NO_WINDOW}`` on Windows, ``{}`` elsewhere
    (the attribute does not exist on non-Windows ``subprocess``).
    """
    if is_windows(os_name):
        flag = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": flag}
    return {}


# Common dirs a CLI provider installs into that are ABSENT from the minimal
# launchd PATH a macOS app inherits from the Dock (/usr/bin:/bin:/usr/sbin:/sbin).
# shutil.which sees only the process PATH, so a `claude` that works in a terminal
# is invisible to a dock-launched Maya -- probe these too.
_CLI_FALLBACK_DIRS = (
    "~/.claude/local",    # Claude Code native installer
    "~/.local/bin",       # pipx / user-local installs
    "/usr/local/bin",     # npm-global (Intel) / manual
    "/opt/homebrew/bin",  # Homebrew (Apple silicon)
    "~/.npm-global/bin",  # npm prefix override
)


def find_executable(name: str) -> Optional[str]:
    """Full path to ``name``, or ``None`` if it cannot be located.

    Beyond ``shutil.which`` (process PATH only) this also probes the common CLI
    install dirs in ``_CLI_FALLBACK_DIRS`` -- a macOS app launched from the Dock
    inherits the minimal launchd PATH (no /usr/local/bin, Homebrew, ~/.local/bin
    or the Claude Code installer dir), so a terminal-visible `claude`/`gemini`/
    `codex` is invisible to which(). An absolute ``name`` is returned iff it is
    executable. Never runs a shell -- pure PATH + filesystem probes.
    """
    if os.path.isabs(name):
        # isfile (not just X_OK): os.access(dir, X_OK) is True for any searchable
        # directory, but shutil.which excluded dirs -- so a *_BIN pointing at an
        # install DIR (or a dir named like the tool) must NOT resolve.
        return name if (os.path.isfile(name) and os.access(name, os.X_OK)) \
            else None
    hit = shutil.which(name)
    if hit:
        return hit
    for d in _CLI_FALLBACK_DIRS:
        cand = os.path.join(os.path.expanduser(d), name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def resolve_executable(name: str) -> str:
    """Full path to an executable, resolving ``.cmd``/``.exe`` shims on Windows.

    Returns the resolved full path (see ``find_executable``), or ``name``
    unchanged if it cannot be located. CreateProcess on Windows cannot launch an
    npm-style ``.cmd`` launcher (e.g. ``claude.cmd``, ``gemini.cmd``) by bare
    name; passing the resolved full path lets ``subprocess`` exec it without
    ``shell=True``. Off-PATH CLI install dirs are probed too (``find_executable``).
    """
    return find_executable(name) or name


def cli_subprocess_kwargs(os_name: Optional[str] = None) -> Dict[str, object]:
    """``subprocess`` kwargs for launching a child CLI portably.

    Forces UTF-8 text pipes (the Windows console default is cp1252, which mangles
    LLM/tool JSON output) and adds the no-console-window flag on Windows. Use in
    place of ``text=True`` when spawning CLI providers.
    """
    kw: Dict[str, object] = {"encoding": "utf-8", "errors": "replace"}
    kw.update(no_window_kwargs(os_name))
    return kw


def run_streaming(cmd, *, env=None, log_cb=None, os_name=None, _popen=None):
    """Run ``cmd``, streaming combined stdout+stderr LINE BY LINE to ``log_cb``
    while ALSO accumulating the full text. Returns ``(returncode, full_text)``.

    stderr is merged into stdout (``stderr=STDOUT``) so there is ONE pipe to
    drain -- no concurrent-reader deadlock -- and the live log reads in natural
    order. ``log_cb(line)`` (newline stripped) is best-effort: a raising callback
    never breaks the build. The accumulated ``full_text`` reproduces what
    ``subprocess.run(capture_output=True)`` returned before (so callers'
    ``compiler_log`` / ``report['stderr']`` are preserved). UTF-8 with
    ``errors='replace'`` (the Windows console default cp1252 mangles output).

    Raises ``FileNotFoundError`` if the executable can't be launched (callers
    decode that into an actionable message). ``_popen`` is injectable for tests.
    """
    popen = _popen or subprocess.Popen
    proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                 env=env, text=True, encoding="utf-8", errors="replace",
                 **no_window_kwargs(os_name))
    chunks = []
    out = getattr(proc, "stdout", None)
    if out is not None:
        for line in out:
            chunks.append(line)
            if log_cb is not None:
                try:
                    log_cb(line.rstrip("\r\n"))
                except Exception:
                    # A misbehaving UI callback must never break the build.
                    pass
        try:
            out.close()
        except Exception:
            pass
    rc = proc.wait()
    return rc, "".join(chunks)


# ---------------------------------------------------------------------------
# Compiler resolution + toolchain pre-flight
# ---------------------------------------------------------------------------


def msvc_cl_from_toolset(build_env_dict: Optional[Dict[str, str]],
                         arch: str = "x64", host: Optional[str] = None,
                         _isfile=None) -> Optional[str]:
    """Full path to ``cl.exe`` DERIVED from the captured vcvars
    ``VCToolsInstallDir``, or ``None``.

    THE STL1001 FIX. ``vcvarsall.bat`` exports ``VCToolsInstallDir`` =
    ``...\\VC\\Tools\\MSVC\\<ver>\\`` -- the EXACT toolset whose ``INCLUDE``/``LIB``
    that same run set. The compiler for it is at
    ``<VCToolsInstallDir>\\bin\\Host<host>\\<arch>\\cl.exe``. Resolving cl this way
    GUARANTEES the compiler matches the headers, so it can never hit
    "STL1001: Unexpected compiler version" -- unlike resolving cl off ``PATH``,
    where a stray OLDER cl ahead of the toolset bin would be picked while
    ``INCLUDE`` still points at the newer toolset.

    ``host`` defaults to ``arch`` (an x64 host building x64 -> ``Hostx64\\x64``).
    Windows-only path (built with ``\\`` regardless of the running OS, since it is
    never used off Windows); ``_isfile`` injectable for tests.
    """
    if not build_env_dict:
        return None
    root = build_env_dict.get("VCToolsInstallDir")
    if not root:
        return None
    isfile = _isfile or os.path.isfile
    host = host or arch
    cand = "%s\\bin\\Host%s\\%s\\cl.exe" % (root.rstrip("\\/"), host, arch)
    return cand if isfile(cand) else None


def resolve_compiler(compiler: str, build_env_dict: Optional[Dict[str, str]] = None,
                     os_name: Optional[str] = None, _which=None,
                     _isfile=None) -> Optional[str]:
    """Full path to the compiler executable, or ``None`` if it cannot be found.

    THE WINDOWS FIX. ``cl.exe`` is on the PATH only *inside* the environment
    ``vcvarsall.bat`` captures (``build_env``); it is never on the ambient PATH.
    And on Windows ``subprocess`` does NOT use a passed-in ``env``'s PATH to
    locate the executable -- it searches the *calling* process's PATH. So
    launching ``["cl", ...]`` by bare name fails with ``[WinError 2] The system
    cannot find the file specified`` EVEN when Visual Studio is correctly
    installed. The fix is to resolve the full path ourselves and pass it as
    argv[0].

    For MSVC we PREFER the toolset-exact cl from the captured
    ``VCToolsInstallDir`` (:func:`msvc_cl_from_toolset`) so the compiler always
    matches the ``INCLUDE`` the same vcvars run set -- this is what prevents the
    STL1001 toolset mismatch. If capture failed but an x64 Native Tools prompt is
    active, we next derive cl from the AMBIENT ``VCToolsInstallDir`` (so it still
    matches the active ``INCLUDE`` rather than a stray older ``cl`` ahead on
    ``PATH``). Only if neither is available do we fall back to resolving ``cl``
    off ``PATH``.

    Unix compilers (clang on macOS, gcc on Linux) are returned VERBATIM: they
    resolve fine from the ambient PATH and the historical argv must not move on
    the working platform, so this is a deliberate no-op for them.
    ``_which`` / ``_isfile`` are injectable for tests.
    """
    if compiler_family(compiler) != "msvc":
        return compiler
    # 1) toolset-exact cl from the captured vcvars env (the normal path).
    exact = msvc_cl_from_toolset(build_env_dict, _isfile=_isfile)
    if exact:
        return exact
    # 2) developer-shell fallback: capture failed but a toolset is active in the
    #    ambient env -- derive cl from the AMBIENT VCToolsInstallDir so it matches
    #    the ambient INCLUDE. This is what stops a stray older cl.exe on PATH
    #    (which a non-standard path would let diagnose_toolset_mismatch miss) from
    #    being used against newer active headers -> STL1001.
    exact = msvc_cl_from_toolset(os.environ, _isfile=_isfile)
    if exact:
        return exact
    # 3) last resort: resolve cl off the captured PATH.
    which = _which or shutil.which
    path = (build_env_dict or {}).get("PATH")
    return which(compiler, path=path)


def compiler_missing_message(compiler: str, os_name: Optional[str] = None) -> str:
    """A human, actionable message for "the C++ compiler could not be launched"."""
    if compiler_family(compiler) == "msvc":
        return (
            "C++ compiler %r could not be found. Install Visual Studio with the "
            "'Desktop development with C++' workload (or the standalone 'Build "
            "Tools for Visual Studio'), which provides cl.exe and vcvarsall.bat, "
            "then retry. Download: "
            "https://visualstudio.microsoft.com/downloads/" % compiler
        )
    osn = current_os(os_name)
    if osn == "darwin":
        return (
            "C++ compiler %r not found. Install the Xcode Command Line Tools "
            "with `xcode-select --install`, then retry." % compiler
        )
    return (
        "C++ compiler %r not found. Install a C++ toolchain (e.g. g++ via your "
        "package manager) so it is on PATH, then retry." % compiler
    )


def check_toolchain(maya: str, compiler: Optional[str] = None,
                    os_name: Optional[str] = None, *,
                    _isdir=None, _which=None, _find_vcvarsall=None,
                    _capture_vcvars=None) -> Dict[str, object]:
    """Pre-flight: can this host actually compile a Maya plugin RIGHT NOW?

    Verifies, WITHOUT compiling anything (and without spending a single LLM
    token), that the four things a build needs are reachable: the Maya devkit
    headers, the Maya link libraries, the C++ compiler, and -- on Windows -- the
    Visual Studio build environment that puts ``cl.exe`` on a PATH.

    Returns ``{"ok": bool, "problems": [str, ...], "compiler": str,
    "compiler_path": str|None}``. NEVER raises -- a probe that explodes is
    reported as a problem string, not an exception, so a caller can always show
    the result. Every system probe is injectable so the whole platform matrix is
    testable from any host.
    """
    osn = current_os(os_name)
    compiler = compiler or default_compiler(os_name)
    isdir = _isdir or os.path.isdir
    problems: List[str] = []
    compiler_path: Optional[str] = None

    # --- Maya devkit (headers + libs) -------------------------------------
    try:
        inc = maya_include_dir(maya)
        if not isdir(inc):
            problems.append(
                "Maya devkit headers not found at %r. Point the compile at a "
                "Maya install that includes the devkit headers (so the generated "
                "C++ can #include <maya/...>)." % inc)
        lib = maya_lib_dir(maya, os_name)
        if not isdir(lib):
            problems.append(
                "Maya link libraries not found at %r. The plugin cannot link "
                "against Maya without them." % lib)
    except Exception as exc:  # pragma: no cover - defensive
        problems.append("Could not check the Maya devkit: %s" % exc)

    # --- compiler / build environment -------------------------------------
    try:
        if compiler_family(compiler) == "msvc":
            find = _find_vcvarsall or find_vcvarsall
            vcvars = find()
            if not vcvars:
                problems.append(
                    "Visual Studio C++ build tools not found (no vcvarsall.bat). "
                    "Install Visual Studio with the 'Desktop development with "
                    "C++' workload, or the standalone 'Build Tools for Visual "
                    "Studio'. Download: "
                    "https://visualstudio.microsoft.com/downloads/")
            else:
                cap = _capture_vcvars or (lambda: capture_vcvars_env())
                benv = cap()
                if not benv:
                    problems.append(
                        "Found vcvarsall.bat at %r but could not capture its "
                        "environment (the C++ toolset may be only partially "
                        "installed)." % vcvars)
                else:
                    compiler_path = resolve_compiler(
                        compiler, benv, os_name, _which=_which)
                    if not compiler_path:
                        problems.append(
                            "%s vcvarsall.bat was found at %r, but %r is still "
                            "not on its toolset PATH -- the C++ toolset may be "
                            "incompletely installed."
                            % (compiler_missing_message(compiler, os_name),
                               vcvars, compiler))
        else:
            which = _which or shutil.which
            compiler_path = which(compiler)
            if not compiler_path:
                problems.append(compiler_missing_message(compiler, os_name))
    except Exception as exc:  # pragma: no cover - defensive
        problems.append("Could not check the C++ compiler: %s" % exc)

    return {
        "ok": not problems,
        "problems": problems,
        "compiler": compiler,
        "compiler_path": compiler_path,
    }
