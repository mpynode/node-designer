"""Native toolchain + build-script generators

Consolidated from: test_toolchain.py, test_native_build_scripts.py.
"""

from __future__ import annotations

# ===================== from test_toolchain.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
import unittest.mock

from tests._setup import standalone_init


def _setUpModule__toolchain():
    standalone_init()


class TestPlatformConstants(unittest.TestCase):
    def test_plugin_ext_per_os(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.plugin_ext(os_name="darwin"), ".bundle")
        self.assertEqual(tc.plugin_ext(os_name="win32"), ".mll")
        self.assertEqual(tc.plugin_ext(os_name="linux"), ".so")

    def test_object_ext_per_os(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.object_ext(os_name="darwin"), ".o")
        self.assertEqual(tc.object_ext(os_name="linux"), ".o")
        self.assertEqual(tc.object_ext(os_name="win32"), ".obj")

    def test_maya_define_per_os(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.maya_define(os_name="darwin"), "OSMac_")
        self.assertEqual(tc.maya_define(os_name="win32"), "NT_PLUGIN")
        self.assertEqual(tc.maya_define(os_name="linux"), "LINUX")

    def test_maya_lib_dir_per_os(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.maya_lib_dir("/M", os_name="darwin"),
                         os.path.join("/M", "Maya.app", "Contents", "MacOS"))
        self.assertEqual(tc.maya_lib_dir("/M", os_name="linux"),
                         os.path.join("/M", "lib"))
        self.assertEqual(tc.maya_lib_dir(r"C:\M", os_name="win32"),
                         os.path.join(r"C:\M", "lib"))

    def test_maya_include_dir(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.maya_include_dir("/M"), os.path.join("/M", "include"))

    def test_default_compiler_per_os(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.default_compiler(os_name="darwin"), "clang++")
        self.assertEqual(tc.default_compiler(os_name="win32"), "cl")
        self.assertEqual(tc.default_compiler(os_name="linux"), "g++")

    def test_compiler_family(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.compiler_family("clang++"), "unix")
        self.assertEqual(tc.compiler_family("g++"), "unix")
        self.assertEqual(tc.compiler_family("cl"), "msvc")
        self.assertEqual(tc.compiler_family("cl.exe"), "msvc")
        self.assertEqual(tc.compiler_family(r"C:\VS\bin\HostX64\x64\cl.exe"),
                         "msvc")


class TestMacRegressionExact(unittest.TestCase):
    """The toolchain argv on macOS == the exact recipe the sites use today."""

    def test_compile_to_plugin_matches_porter_compile_cpp(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.compile_to_plugin_cmd(
            "clang++", "foo.cpp", "/out/foo.bundle",
            include_dir="/M/include",
            lib_dir="/M/Maya.app/Contents/MacOS",
            libs=["OpenMaya", "Foundation"],
            os_name="darwin", arch="arm64")
        self.assertEqual(got, [
            "clang++", "-std=c++17", "-O3", "-ffp-contract=off",
            "-arch", "arm64", "-bundle",
            "-D", "OSMac_", "-D", "REQUIRE_IOSTREAM", "-D", "_BOOL",
            "-Wno-nontrivial-memcall",
            "-I", "/M/include",
            "-L", "/M/Maya.app/Contents/MacOS",
            "-lOpenMaya", "-lFoundation",
            "-o", "/out/foo.bundle", "foo.cpp",
        ])

    def test_compile_object_matches_bundler_fragment(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.compile_object_cmd(
            "clang++", "/x/frag.cpp", "/x/frag.o",
            include_dir="/M/include", frag=True,
            os_name="darwin", arch="arm64")
        self.assertEqual(got, [
            "clang++", "-std=c++17", "-O3", "-ffp-contract=off", "-arch", "arm64",
            "-D", "OSMac_", "-D", "REQUIRE_IOSTREAM", "-D", "_BOOL",
            "-Wno-nontrivial-memcall",
            "-D", "MNoVersionString", "-D", "MNoPluginEntry",
            "-I/M/include", "-c", "/x/frag.cpp", "-o", "/x/frag.o",
        ])

    def test_compile_object_non_fragment_omits_suppress_defines(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.compile_object_cmd(
            "clang++", "/x/plugin_main.cpp", "/x/plugin_main.o",
            include_dir="/M/include", frag=False,
            os_name="darwin", arch="arm64")
        self.assertNotIn("MNoVersionString", got)
        self.assertIn("-I/M/include", got)


class TestMsvcContract(unittest.TestCase):
    def test_compile_to_plugin_msvc(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.compile_to_plugin_cmd(
            "cl", r"C:\src\foo.cpp", r"C:\out\foo.mll",
            include_dir=r"C:\M\include",
            lib_dir=r"C:\M\lib",
            libs=["OpenMaya", "Foundation"],
            os_name="win32")
        # DLL build, NT_PLUGIN, C++17, the source, the .mll output.
        self.assertEqual(got[0], "cl")
        self.assertIn("/LD", got)
        self.assertIn("/std:c++17", got)
        self.assertIn("NT_PLUGIN", got)
        self.assertNotIn("OSMac_", got)
        self.assertNotIn("-arch", got)
        self.assertIn(r"C:\src\foo.cpp", got)
        # include via /I, the maya include dir present
        self.assertIn(r"C:\M\include", got)
        # link section: libpath + named .lib tokens + exports + .mll out
        self.assertIn("/link", got)
        self.assertTrue(any(a.startswith("/LIBPATH:") and r"C:\M\lib" in a
                            for a in got), got)
        self.assertIn("OpenMaya.lib", got)
        self.assertIn("Foundation.lib", got)
        self.assertTrue(any("initializePlugin" in a for a in got), got)
        self.assertTrue(any("uninitializePlugin" in a for a in got), got)
        self.assertTrue(any(a.endswith("foo.mll") for a in got), got)

    def test_compile_object_msvc(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.compile_object_cmd(
            "cl", r"C:\x\frag.cpp", r"C:\x\frag.obj",
            include_dir=r"C:\M\include", frag=True, os_name="win32")
        self.assertEqual(got[0], "cl")
        self.assertIn("/c", got)
        self.assertIn("NT_PLUGIN", got)
        self.assertIn("MNoVersionString", got)
        self.assertIn(r"C:\x\frag.cpp", got)
        self.assertTrue(any(a.startswith("/Fo") and "frag.obj" in a
                            for a in got), got)

    def test_link_plugin_msvc(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.link_plugin_cmd(
            "cl", [r"C:\x\a.obj", r"C:\x\b.obj"], r"C:\out\plug.mll",
            lib_dir=r"C:\M\lib", libs=["OpenMaya"], os_name="win32")
        self.assertEqual(got[0], "cl")
        self.assertIn("/LD", got)
        self.assertIn(r"C:\x\a.obj", got)
        self.assertIn(r"C:\x\b.obj", got)
        self.assertIn("/link", got)
        self.assertIn("OpenMaya.lib", got)
        self.assertTrue(any(a.startswith("/LIBPATH:") for a in got), got)
        self.assertTrue(any("initializePlugin" in a for a in got), got)


class TestMsvcFpPrecise(unittest.TestCase):
    """Item 1: every MSVC COMPILE command must carry an EXPLICIT /fp:precise
    (and /O2), never /fp:fast. This is the MSVC parity lever: the clang path
    already pins -ffp-contract=off, but the MSVC path used to rely on the
    compiler's IMPLICIT /fp:precise default, which an inherited env flag or a
    future default change to /fp:fast would silently override -- FMA-contracting
    / reassociating a*b + c chains and diverging bit-for-bit from the numpy
    reference. The pure link command compiles nothing, so it needs no /fp flag."""

    def _compile_cmds(self):
        from mpynode.native.toolchain import toolchain as tc
        return {
            "compile_to_plugin": tc.compile_to_plugin_cmd(
                "cl", r"C:\s\f.cpp", r"C:\o\f.mll",
                include_dir=r"C:\M\inc", lib_dir=r"C:\M\lib",
                libs=["OpenMaya"], os_name="win32"),
            "compile_object": tc.compile_object_cmd(
                "cl", r"C:\s\f.cpp", r"C:\o\f.obj",
                include_dir=r"C:\M\inc", frag=True, os_name="win32"),
        }

    def _all_cmds(self):
        from mpynode.native.toolchain import toolchain as tc
        cmds = self._compile_cmds()
        cmds["link_plugin"] = tc.link_plugin_cmd(
            "cl", [r"C:\o\a.obj"], r"C:\o\p.mll",
            lib_dir=r"C:\M\lib", libs=["OpenMaya"], os_name="win32")
        return cmds

    def test_msvc_compile_commands_have_fp_precise_and_o2(self):
        for name, cmd in self._compile_cmds().items():
            self.assertIn("/fp:precise", cmd, "%s missing /fp:precise" % name)
            self.assertIn("/O2", cmd, "%s missing /O2" % name)

    def test_no_msvc_command_has_parity_breaking_flags(self):
        for name, cmd in self._all_cmds().items():
            joined = " ".join(cmd)
            self.assertNotIn("/fp:fast", joined, "%s has /fp:fast" % name)
            self.assertNotIn("/fp:contract", joined, "%s has /fp:contract" % name)
            self.assertNotIn("/arch:", joined, "%s has /arch:" % name)

    def test_msvc_compile_commands_are_utf8_and_silence_crt_secure(self):
        # 24 generated TUs carry non-ASCII comment bytes (cl reads them as the
        # ANSI codepage without /utf-8 -> C4819 and, for a stray lead byte, a
        # hard parse error); the embedded-image stage calls getenv (C4996).
        for name, cmd in self._compile_cmds().items():
            self.assertIn("/utf-8", cmd, "%s missing /utf-8" % name)
            self.assertIn("_CRT_SECURE_NO_WARNINGS", cmd,
                          "%s missing _CRT_SECURE_NO_WARNINGS" % name)


class TestQtLinkage(unittest.TestCase):
    """Qt frameworks linkage for hover-capable locator plugins (needs_qt). A
    self-contained C++ hover service uses QCursor/QWidget, so those TUs must
    compile against Maya's Qt headers and link the Qt frameworks + an rpath so
    they resolve in GUI Maya AND batch mayapy. macOS is the verified path
    (frameworks); Linux/Windows are best-effort. The qt=False default keeps every
    existing argv BYTE-IDENTICAL (the regression anchor)."""

    def test_maya_frameworks_dir_per_os(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(
            tc.maya_frameworks_dir("/M", os_name="darwin"),
            os.path.join("/M", "Maya.app", "Contents", "Frameworks"))
        # Linux Qt .so live in the lib dir.
        self.assertEqual(tc.maya_frameworks_dir("/M", os_name="linux"),
                         os.path.join("/M", "lib"))

    def test_qt_link_flags_darwin(self):
        from mpynode.native.toolchain import toolchain as tc

        fw = os.path.join("/M", "Maya.app", "Contents", "Frameworks")
        got = tc.qt_link_flags("/M", os_name="darwin")
        for f in ("QtCore", "QtGui", "QtWidgets"):
            self.assertIn("-framework", got)
            self.assertIn(f, got)
        self.assertIn("-F", got)
        self.assertIn(fw, got)
        # an rpath to the frameworks dir so Qt resolves in batch mayapy too
        self.assertIn("-Wl,-rpath," + fw, got)

    def test_qt_compile_flags_darwin_has_framework_search(self):
        from mpynode.native.toolchain import toolchain as tc

        fw = os.path.join("/M", "Maya.app", "Contents", "Frameworks")
        got = tc.qt_compile_flags("/M", os_name="darwin")
        self.assertIn("-F", got)
        self.assertIn(fw, got)

    def test_compile_to_plugin_qt_false_is_byte_identical(self):
        from mpynode.native.toolchain import toolchain as tc

        # The whole-cmd anchor: qt defaults False -> unchanged from today.
        got = tc.compile_to_plugin_cmd(
            "clang++", "foo.cpp", "/out/foo.bundle",
            include_dir="/M/include",
            lib_dir="/M/Maya.app/Contents/MacOS",
            libs=["OpenMaya", "Foundation"],
            os_name="darwin", arch="arm64")
        self.assertEqual(got, [
            "clang++", "-std=c++17", "-O3", "-ffp-contract=off",
            "-arch", "arm64", "-bundle",
            "-D", "OSMac_", "-D", "REQUIRE_IOSTREAM", "-D", "_BOOL",
            "-Wno-nontrivial-memcall",
            "-I", "/M/include",
            "-L", "/M/Maya.app/Contents/MacOS",
            "-lOpenMaya", "-lFoundation",
            "-o", "/out/foo.bundle", "foo.cpp",
        ])

    def test_compile_to_plugin_qt_true_appends_qt_darwin(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.compile_to_plugin_cmd(
            "clang++", "foo.cpp", "/out/foo.bundle",
            include_dir="/M/include",
            lib_dir="/M/Maya.app/Contents/MacOS",
            libs=["OpenMaya", "Foundation"],
            os_name="darwin", arch="arm64", qt=True, maya="/M")
        fw = os.path.join("/M", "Maya.app", "Contents", "Frameworks")
        self.assertIn("-framework", got)
        self.assertIn("QtGui", got)
        self.assertIn("-Wl,-rpath," + fw, got)
        # the .cpp and output are still present (well-formed compile+link)
        self.assertIn("foo.cpp", got)
        self.assertTrue(any(a.endswith("foo.bundle") for a in got))

    def test_compile_object_qt_true_adds_framework_search_darwin(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.compile_object_cmd(
            "clang++", "/x/frag.cpp", "/x/frag.o",
            include_dir="/M/include", frag=True,
            os_name="darwin", arch="arm64", qt=True, maya="/M")
        fw = os.path.join("/M", "Maya.app", "Contents", "Frameworks")
        self.assertIn("-F", got)
        self.assertIn(fw, got)
        # still a fragment object compile
        self.assertIn("-c", got)
        self.assertIn("/x/frag.cpp", got)

    def test_link_plugin_qt_true_adds_frameworks_and_rpath_darwin(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.link_plugin_cmd(
            "clang++", ["/x/a.o", "/x/b.o"], "/out/plug.bundle",
            lib_dir="/M/Maya.app/Contents/MacOS", libs=["OpenMaya"],
            os_name="darwin", arch="arm64", qt=True, maya="/M")
        fw = os.path.join("/M", "Maya.app", "Contents", "Frameworks")
        self.assertIn("QtWidgets", got)
        self.assertIn("-Wl,-rpath," + fw, got)

    def test_compile_object_qt_false_unchanged(self):
        from mpynode.native.toolchain import toolchain as tc

        # qt=False default -> the existing fragment anchor, no Qt tokens.
        got = tc.compile_object_cmd(
            "clang++", "/x/frag.cpp", "/x/frag.o",
            include_dir="/M/include", frag=True,
            os_name="darwin", arch="arm64")
        self.assertNotIn("-framework", got)
        self.assertNotIn("QtGui", got)


class TestQtIncludeResolution(unittest.TestCase):
    """Windows/Linux must RESOLVE a Qt include dir -- the old docstring claimed
    ``<maya>/include`` already carries the Qt headers, which is FALSE: the devkit
    ships them as an unextracted archive (Windows: ``qt_<ver>_vc14-include.zip``,
    confirmed on Maya 2026; macOS/Linux: ``qt_<ver>-include.tar.gz``), so
    ``#include <QtGui/QCursor>`` fails with C1083 and aborts the whole serial
    build. macOS resolves via the framework search path and must NOT move."""

    def test_darwin_flags_are_exactly_the_framework_search(self):
        from mpynode.native.toolchain import toolchain as tc

        # The macOS anchor: byte-for-byte the pre-existing two tokens.
        self.assertEqual(tc.qt_compile_flags("/M", os_name="darwin"),
                         ["-F", os.path.join("/M", "Maya.app", "Contents",
                                             "Frameworks")])

    def test_include_dir_honours_env_override(self):
        from mpynode.native.toolchain import toolchain as tc

        good = os.path.join("/qt", "include")
        with unittest.mock.patch.dict(os.environ,
                                      {tc.QT_INCLUDE_ENV: good}):
            got = tc.qt_include_dir(
                "/M",
                _isfile=lambda p: p == os.path.join(good, "QtGui", "QCursor"))
        self.assertEqual(got, good)

    def test_include_dir_rejects_a_bogus_env_override(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.dict(os.environ,
                                      {tc.QT_INCLUDE_ENV: "/nope"}):
            self.assertIsNone(tc.qt_include_dir("/M",
                                                _isfile=lambda p: False,
                                                _listdir=lambda d: []))

    def test_include_dir_finds_headers_extracted_into_maya_include(self):
        from mpynode.native.toolchain import toolchain as tc

        inc = os.path.join("/M", "include")
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(tc.QT_INCLUDE_ENV, None)
            got = tc.qt_include_dir(
                "/M",
                _isfile=lambda p: p == os.path.join(inc, "QtGui", "QCursor"),
                _listdir=lambda d: [])
        self.assertEqual(got, inc)

    def test_include_dir_finds_an_extracted_subdirectory(self):
        from mpynode.native.toolchain import toolchain as tc

        inc = os.path.join("/M", "include")
        sub = os.path.join(inc, "qt_6.5.3-include")
        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(tc.QT_INCLUDE_ENV, None)
            got = tc.qt_include_dir(
                "/M",
                _isfile=lambda p: p == os.path.join(sub, "QtGui", "QCursor"),
                _listdir=lambda d: ["maya", "tbb", "qt_6.5.3-include"])
        self.assertEqual(got, sub)

    def test_include_dir_none_when_nothing_is_extracted(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(tc.QT_INCLUDE_ENV, None)
            self.assertIsNone(tc.qt_include_dir(
                "/M", _isfile=lambda p: False,
                _listdir=lambda d: ["maya", "qt_6.5.3-include.tar.gz"]))

    def test_windows_emits_slash_I_for_the_resolved_dir(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=r"C:\M\include\qt"):
            self.assertEqual(tc.qt_compile_flags(r"C:\M", os_name="win32"),
                             ["/Zc:__cplusplus", "/permissive-",
                              "/I", r"C:\M\include\qt",
                              "/FI", tc.qt_msvc_compat_header_path()])

    def test_windows_qt_flags_carry_Zc_cplusplus(self):
        """Qt's qcompilerdetection.h reads __cplusplus, which MSVC leaves at
        199711L under /std:c++17 unless /Zc:__cplusplus is passed. Windows
        2026-08-14 hit exactly that as C1189, so assert the flag directly and
        not merely as part of a list that could be reordered away."""
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=r"C:\M\include\qt"):
            self.assertIn("/Zc:__cplusplus",
                          tc.qt_compile_flags(r"C:\M", os_name="win32"))
        # macOS and Linux must be untouched by the MSVC-only workaround.
        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value="/M/include/qt"):
            self.assertNotIn("/Zc:__cplusplus",
                             tc.qt_compile_flags("/M", os_name="linux"))
        self.assertNotIn("/Zc:__cplusplus",
                         tc.qt_compile_flags("/M", os_name="darwin"))

    def test_windows_qt_flags_carry_permissive(self):
        """Qt 6 static_asserts on /permissive- (qcompilerdetection.h(1242),
        C2338 'On MSVC you must pass the /permissive- option to the
        compiler'). Windows 2026-08-14 hit it as the next error after
        /Zc:__cplusplus was added, so assert the flag directly rather than as
        part of a list that could be reordered away."""
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=r"C:\M\include\qt"):
            self.assertIn("/permissive-",
                          tc.qt_compile_flags(r"C:\M", os_name="win32"))
        # macOS and Linux must be untouched by the MSVC-only requirement.
        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value="/M/include/qt"):
            self.assertNotIn("/permissive-",
                             tc.qt_compile_flags("/M", os_name="linux"))
        self.assertNotIn("/permissive-",
                         tc.qt_compile_flags("/M", os_name="darwin"))

    def test_linux_emits_dash_I_for_the_resolved_dir(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value="/M/include/qt"):
            self.assertEqual(tc.qt_compile_flags("/M", os_name="linux"),
                             ["-I", "/M/include/qt"])

    def test_windows_compile_object_carries_the_qt_include(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=r"C:\qt"):
            got = tc.compile_object_cmd(
                "cl", r"C:\x\frag.cpp", r"C:\x\frag.obj",
                include_dir=r"C:\M\include", frag=True, os_name="win32",
                qt=True, maya=r"C:\M")
        self.assertIn(r"C:\qt", got)
        self.assertEqual(got.count("/I"), 2)  # maya devkit + qt

    def test_problem_is_none_on_macos_and_when_resolved(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertIsNone(tc.qt_include_problem("/M", os_name="darwin"))
        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=r"C:\qt"):
            self.assertIsNone(tc.qt_include_problem(r"C:\M", os_name="win32"))

    def test_an_unresolved_linux_qt_is_not_refused(self):
        # The gate is a WINDOWS remedy: cl dies at C1083 partway through a
        # serial build. Linux was never gated, and a box carrying Qt on a
        # default include path (or via CPLUS_INCLUDE_PATH) compiles without
        # anything this resolver can see -- so refusing there would break a
        # build that used to work, and would quote an MSVC error code at a
        # g++ user. It still gets the -I when the dir DOES resolve.
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=None):
            self.assertIsNone(tc.qt_include_problem("/M", os_name="linux"))
            self.assertIsNotNone(tc.qt_include_problem(r"C:\M",
                                                       os_name="win32"))

    def test_problem_message_names_the_env_var_and_what_to_point_it_at(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=None):
            msg = tc.qt_include_problem(r"C:\M", os_name="win32")
        self.assertIsNotNone(msg)
        self.assertIn("MPYNODE_QT_INCLUDE", msg)
        self.assertIn("QtGui/QCursor", msg)
        # says WHY they're missing. qt_include_problem() is Windows-only, and
        # the 2026-08-14 Maya 2026 run confirmed the real artifact there is
        # 'qt_6.5.3_vc14-include.zip' -- not the .tar.gz the message used to
        # name, which sent the reader looking for a file that is not present.
        self.assertIn(".zip", msg)

    def test_c1083_on_a_qt_header_gets_an_actionable_hint(self):
        from mpynode.native.toolchain import toolchain as tc

        hint = tc.diagnose_compiler_log(
            "hover.cpp(69): fatal error C1083: Cannot open include file: "
            "'QtGui/QCursor': No such file or directory")
        self.assertIsNotNone(hint)
        self.assertIn("MPYNODE_QT_INCLUDE", hint)


class TestMayapy(unittest.TestCase):
    def test_mayapy_path_prefers_existing(self):
        from mpynode.native.toolchain import toolchain as tc

        # Non-existent dir -> falls back to the first (macOS-layout) candidate,
        # same contract as the old _mayapy_for. os_name is PINNED because the
        # assertion is about the macOS layout specifically: unpinned, this read
        # the host platform and failed on Windows, where the fallback shape is
        # bin\mayapy.exe -- exactly what the next test asserts.
        p = tc.mayapy_path("/no/such/maya", os_name="darwin")
        self.assertTrue(p.endswith(os.path.join("Maya.app", "Contents", "bin",
                                                 "mayapy")))

    def test_not_found_fallback_uses_the_platform_shape(self):
        from mpynode.native.toolchain import toolchain as tc

        # The fallback path only ever appears in a diagnostic, so it must be the
        # shape the user would actually look for on THEIR platform -- the macOS
        # Maya.app/... shape is meaningless on Windows.
        self.assertEqual(tc.mayapy_path(r"C:\M", os_name="win32"),
                         os.path.join(r"C:\M", "bin", "mayapy.exe"))
        self.assertEqual(tc.mayapy_path("/M", os_name="linux"),
                         os.path.join("/M", "bin", "mayapy"))
        self.assertEqual(
            tc.mayapy_path("/M", os_name="darwin"),
            os.path.join("/M", "Maya.app", "Contents", "bin", "mayapy"))


class TestPreferredMayaDir(unittest.TestCase):
    """The in-process default must be an install that EXISTS.

    ``default_maya_dir`` is a pinned constant (maya2026). MEASURED on Windows
    2026-08-31: on a box with Maya 2022 + 2025 and no 2026, every non-UI caller
    compiled against a nonexistent devkit and ``bundler.assemble`` dropped EVERY
    node -- reported only as "dropped", with no reason naming the cause. The
    generated build scripts never had this bug because they resolve at run time.
    """

    def test_prefers_the_newest_install_that_exists(self):
        from mpynode.native.toolchain import toolchain as tc

        fake = [{"label": "Maya2022", "version": "2022", "root": "/A/Maya2022",
                 "mayapy": "x"},
                {"label": "Maya2025", "version": "2025", "root": "/A/Maya2025",
                 "mayapy": "x"}]
        with unittest.mock.patch.object(tc, "discover_maya_installs",
                                        return_value=fake):
            self.assertEqual(tc.preferred_maya_dir("win32"), "/A/Maya2025")

    def test_falls_back_to_the_conventional_constant(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "discover_maya_installs",
                                        return_value=[]):
            for os_name in ("win32", "darwin", "linux"):
                self.assertEqual(tc.preferred_maya_dir(os_name),
                                 tc.default_maya_dir(os_name))

    def test_the_engine_defaults_use_it(self):
        """All four modules that carry a _MAYA_DEFAULT must resolve, not pin."""
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain import compile_controller, verify
        from mpynode.native.ai import porter
        from mpynode.native.toolchain import toolchain as tc

        want = tc.preferred_maya_dir()
        for mod in (bundler, compile_controller, verify, porter):
            self.assertEqual(mod._MAYA_DEFAULT, want,
                             "%s pins its Maya default" % mod.__name__)


class TestVcvarsParsing(unittest.TestCase):
    def test_parse_set_output(self):
        from mpynode.native.toolchain import toolchain as tc

        sample = (
            "PATH=C:\\Windows;C:\\VS\\bin\r\n"
            "INCLUDE=C:\\VS\\include;C:\\SDK\\include\r\n"
            "LIB=C:\\VS\\lib\r\n"
            "WeirdNoEquals\r\n"          # ignored
            "EMPTY=\r\n"
        )
        env = tc._parse_set_output(sample)
        self.assertEqual(env["INCLUDE"], "C:\\VS\\include;C:\\SDK\\include")
        self.assertEqual(env["LIB"], "C:\\VS\\lib")
        self.assertEqual(env["EMPTY"], "")
        self.assertNotIn("WeirdNoEquals", env)

    def test_build_env_is_none_for_unix(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertIsNone(tc.build_env("clang++"))
        self.assertIsNone(tc.build_env("g++"))


def _strip_ambient_msvc_toolset(test_case):
    """Drop the ambient ``VCToolsInstallDir`` for the duration of one test.

    ``resolve_compiler`` deliberately falls back to the AMBIENT
    ``VCToolsInstallDir`` when the captured build env has none -- its documented
    "developer-shell fallback", which is what stops a stray older cl.exe on PATH
    from being used against newer active headers. The Windows suite is run from
    a VS2022 x64 Native Tools prompt, where that variable IS set, so these tests
    resolved the REAL cl.exe and returned before ever consulting their injected
    ``_which``: five failures that never reached the code they were written for
    (measured 2026-08-14). A no-op off Windows, where it is never set.

    NOT applied to TestMsvcClFromToolset, which asserts that fallback on purpose.
    """
    patcher = unittest.mock.patch.dict(os.environ)
    patcher.start()
    test_case.addCleanup(patcher.stop)
    os.environ.pop("VCToolsInstallDir", None)


class TestResolveCompiler(unittest.TestCase):
    def setUp(self):
        _strip_ambient_msvc_toolset(self)

    """Resolving the compiler to a full path. The Windows fix: ``cl.exe`` lives
    ONLY on the vcvars-captured PATH, and Windows ``subprocess`` does NOT search
    a passed-in ``env``'s PATH to locate the executable, so we must resolve the
    full path ourselves from that captured PATH and pass it as argv[0]."""

    def test_unix_compiler_is_passed_through_unchanged(self):
        from mpynode.native.toolchain import toolchain as tc

        # Unix family must be byte-for-byte unchanged: returned verbatim, never
        # rewritten to a full path (the working macOS path must not move).
        self.assertEqual(tc.resolve_compiler("clang++"), "clang++")
        self.assertEqual(tc.resolve_compiler("g++", {"PATH": "/whatever"}),
                         "g++")

    def test_msvc_resolves_from_build_env_path(self):
        from mpynode.native.toolchain import toolchain as tc

        seen = {}

        def fake_which(name, path=None):
            seen["name"] = name
            seen["path"] = path
            return r"C:\VS\bin\HostX64\x64\cl.exe"

        got = tc.resolve_compiler("cl", {"PATH": r"C:\VS\bin\HostX64\x64"},
                                  _which=fake_which)
        self.assertEqual(got, r"C:\VS\bin\HostX64\x64\cl.exe")
        # MUST search the captured vcvars PATH, not the ambient one.
        self.assertEqual(seen["path"], r"C:\VS\bin\HostX64\x64")
        self.assertEqual(seen["name"], "cl")

    def test_msvc_returns_none_when_not_found(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.resolve_compiler("cl", {"PATH": r"C:\nope"},
                                  _which=lambda n, path=None: None)
        self.assertIsNone(got)

    def test_msvc_with_no_build_env_searches_none_path(self):
        from mpynode.native.toolchain import toolchain as tc

        seen = {}

        def fake_which(name, path=None):
            seen["path"] = path
            return None

        self.assertIsNone(tc.resolve_compiler("cl", None, _which=fake_which))
        self.assertIsNone(seen["path"])


class TestMsvcClFromToolset(unittest.TestCase):
    """Resolve cl.exe DIRECTLY from the captured vcvars VCToolsInstallDir so the
    compiler ALWAYS matches the toolset whose INCLUDE/LIB the same vcvars run set
    -- the real STL1001 fix (a PATH-resolved cl can be a stray OLDER one ahead of
    the toolset bin, mismatched against the newer headers)."""

    _ROOT = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools"
             r"\MSVC\14.51.36231")

    def test_builds_hostx64_x64_cl_path(self):
        from mpynode.native.toolchain import toolchain as tc

        got = tc.msvc_cl_from_toolset({"VCToolsInstallDir": self._ROOT + "\\"},
                                      _isfile=lambda p: True)
        self.assertEqual(
            got, self._ROOT + r"\bin\Hostx64\x64\cl.exe")

    def test_none_when_no_vctoolsinstalldir_or_no_env(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertIsNone(tc.msvc_cl_from_toolset({}, _isfile=lambda p: True))
        self.assertIsNone(tc.msvc_cl_from_toolset(None, _isfile=lambda p: True))

    def test_none_when_file_missing(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertIsNone(
            tc.msvc_cl_from_toolset({"VCToolsInstallDir": self._ROOT},
                                    _isfile=lambda p: False))

    def test_resolve_compiler_prefers_toolset_exact_over_path(self):
        from mpynode.native.toolchain import toolchain as tc

        # When VCToolsInstallDir is present, resolve_compiler returns the
        # toolset-exact cl and must NOT fall back to a (possibly stray) PATH cl.
        def boom_which(name, path=None):
            raise AssertionError("must not PATH-resolve when toolset cl exists")

        got = tc.resolve_compiler(
            "cl",
            {"VCToolsInstallDir": self._ROOT, "PATH": r"C:\stray"},
            _which=boom_which, _isfile=lambda p: True)
        self.assertEqual(got, self._ROOT + r"\bin\Hostx64\x64\cl.exe")

    def test_resolve_compiler_falls_back_to_path_when_toolset_cl_missing(self):
        from mpynode.native.toolchain import toolchain as tc

        # VCToolsInstallDir set but the file isn't there -> fall back to PATH
        # resolution (preserves the prior behavior). Clear any ambient
        # VCToolsInstallDir so the ambient-toolset fallback doesn't intercept.
        seen = {}

        def fake_which(name, path=None):
            seen["path"] = path
            return r"C:\fallback\cl.exe"

        with unittest.mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VCToolsInstallDir", None)
            got = tc.resolve_compiler(
                "cl", {"VCToolsInstallDir": self._ROOT, "PATH": r"C:\vs\bin"},
                _which=fake_which, _isfile=lambda p: False)
        self.assertEqual(got, r"C:\fallback\cl.exe")
        self.assertEqual(seen["path"], r"C:\vs\bin")

    def test_resolve_compiler_uses_ambient_vctoolsinstalldir_in_dev_shell(self):
        from mpynode.native.toolchain import toolchain as tc

        # THE DEVELOPER-SHELL FIX: capture failed but an x64 Native Tools
        # prompt is active, so cl MUST come from that ambient toolset -- a
        # stray PATH cl could be older and cause STL1001.
        def boom_which(name, path=None):
            raise AssertionError("must not PATH-resolve a stray cl in a dev shell")

        with unittest.mock.patch.dict(os.environ,
                                      {"VCToolsInstallDir": self._ROOT + "\\"}):
            got = tc.resolve_compiler("cl", None, _which=boom_which,
                                      _isfile=lambda p: True)
        self.assertEqual(got, self._ROOT + r"\bin\Hostx64\x64\cl.exe")


class TestCompilerMissingMessage(unittest.TestCase):
    def test_msvc_message_points_at_visual_studio(self):
        from mpynode.native.toolchain import toolchain as tc

        msg = tc.compiler_missing_message("cl", os_name="win32")
        self.assertIn("cl", msg)
        low = msg.lower()
        self.assertTrue("visual studio" in low or "build tools" in low, msg)

    def test_unix_message_points_at_clt(self):
        from mpynode.native.toolchain import toolchain as tc

        msg = tc.compiler_missing_message("clang++", os_name="darwin")
        self.assertIn("clang++", msg)
        self.assertTrue("xcode" in msg.lower() or "command line" in msg.lower(),
                        msg)


class TestCheckToolchain(unittest.TestCase):
    def setUp(self):
        _strip_ambient_msvc_toolset(self)

    """The pre-flight: can this host actually compile? Never raises; returns
    ``{ok, problems, compiler, compiler_path}``. Fully injectable so the whole
    platform matrix is testable from macOS."""

    def test_mac_all_present_is_ok(self):
        from mpynode.native.toolchain import toolchain as tc

        res = tc.check_toolchain(
            "/Applications/Autodesk/maya2026", os_name="darwin",
            _isdir=lambda p: True,
            _which=lambda n, path=None: "/usr/bin/clang++")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["problems"], [])

    def test_mac_missing_maya_headers_reports_maya(self):
        from mpynode.native.toolchain import toolchain as tc

        res = tc.check_toolchain(
            "/no/such/maya", os_name="darwin",
            _isdir=lambda p: False,
            _which=lambda n, path=None: "/usr/bin/clang++")
        self.assertFalse(res["ok"])
        self.assertTrue(any("maya" in p.lower() for p in res["problems"]),
                        res["problems"])

    def test_mac_missing_compiler_reports_compiler(self):
        from mpynode.native.toolchain import toolchain as tc

        res = tc.check_toolchain(
            "/M", os_name="darwin",
            _isdir=lambda p: True,
            _which=lambda n, path=None: None)
        self.assertFalse(res["ok"])
        self.assertTrue(any("clang++" in p for p in res["problems"]),
                        res["problems"])

    def test_win_missing_visual_studio_reports_it(self):
        from mpynode.native.toolchain import toolchain as tc

        res = tc.check_toolchain(
            r"C:\Program Files\Autodesk\Maya2026", os_name="win32",
            _isdir=lambda p: True,
            _find_vcvarsall=lambda: None)
        self.assertFalse(res["ok"])
        joined = " ".join(res["problems"]).lower()
        self.assertTrue("visual studio" in joined or "build tools" in joined,
                        res["problems"])

    def test_win_vs_found_but_cl_unresolved_reports_compiler(self):
        from mpynode.native.toolchain import toolchain as tc

        res = tc.check_toolchain(
            r"C:\M", os_name="win32",
            _isdir=lambda p: True,
            _find_vcvarsall=lambda: r"C:\VS\vcvarsall.bat",
            _capture_vcvars=lambda: {"PATH": r"C:\VS\bin"},
            _which=lambda n, path=None: None)
        self.assertFalse(res["ok"])
        self.assertTrue(any("cl" in p for p in res["problems"]), res["problems"])

    def test_win_all_present_is_ok_with_resolved_cl(self):
        from mpynode.native.toolchain import toolchain as tc

        res = tc.check_toolchain(
            r"C:\M", os_name="win32",
            _isdir=lambda p: True,
            _find_vcvarsall=lambda: r"C:\VS\vcvarsall.bat",
            _capture_vcvars=lambda: {"PATH": r"C:\VS\bin"},
            _which=lambda n, path=None: r"C:\VS\bin\cl.exe")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["compiler_path"], r"C:\VS\bin\cl.exe")

    def test_never_raises_on_probe_explosion(self):
        from mpynode.native.toolchain import toolchain as tc

        def boom(*a, **k):
            raise RuntimeError("probe blew up")

        # Even if a probe raises, check_toolchain degrades to a problem string.
        res = tc.check_toolchain("/M", os_name="darwin", _isdir=boom)
        self.assertFalse(res["ok"])
        self.assertTrue(res["problems"])


class TestFindVcvarsallPrerelease(unittest.TestCase):
    """vswhere must also find a VS *preview* (e.g. the '18'/2026 preview whose
    14.51 toolset it hides by default) -- else vcvars capture fails and the build
    falls back to a stray PATH cl, causing the STL1001 toolset mismatch."""

    def test_retries_with_prerelease_when_stable_empty(self):
        import unittest.mock as mock

        from mpynode.native.toolchain import toolchain as tc

        calls = []

        def fake_runner(args):
            calls.append(list(args))
            return "C:\\VS18\n" if "-prerelease" in args else "\n"

        with mock.patch.object(tc, "find_vswhere", return_value="C:\\vswhere.exe"):
            got = tc.find_vcvarsall(_runner=fake_runner, _isfile=lambda p: True)
        self.assertEqual(
            got, os.path.join("C:\\VS18", "VC", "Auxiliary", "Build",
                              "vcvarsall.bat"))
        self.assertEqual(len(calls), 2, calls)
        self.assertNotIn("-prerelease", calls[0])
        self.assertIn("-prerelease", calls[1])

    def test_stable_found_does_not_retry(self):
        import unittest.mock as mock

        from mpynode.native.toolchain import toolchain as tc

        calls = []

        def fake_runner(args):
            calls.append(list(args))
            return "C:\\VS17\n"

        with mock.patch.object(tc, "find_vswhere", return_value="C:\\vswhere.exe"):
            got = tc.find_vcvarsall(_runner=fake_runner, _isfile=lambda p: True)
        self.assertTrue(got.endswith("vcvarsall.bat"))
        self.assertEqual(len(calls), 1, calls)
        self.assertNotIn("-prerelease", calls[0])

    def test_none_when_no_vswhere(self):
        import unittest.mock as mock

        from mpynode.native.toolchain import toolchain as tc

        with mock.patch.object(tc, "find_vswhere", return_value=None):
            self.assertIsNone(tc.find_vcvarsall(_runner=lambda a: "X"))


class TestDeveloperShell(unittest.TestCase):
    def test_detects_active_msvc_toolset_env(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertTrue(tc.in_developer_shell({"VCToolsInstallDir": "C:\\x"}))
        self.assertTrue(tc.in_developer_shell({"VCINSTALLDIR": "C:\\x"}))
        self.assertFalse(tc.in_developer_shell({}))


class TestVcvarsUnavailableMessage(unittest.TestCase):
    def test_message_is_actionable_and_names_the_failure(self):
        from mpynode.native.toolchain import toolchain as tc

        m = tc.vcvars_unavailable_message("cl")
        self.assertIn("STL1001", m)  # names the mismatch it is preventing
        low = m.lower()
        self.assertTrue("visual studio" in low or "native tools" in low, m)


class TestDiagnoseCompilerLog(unittest.TestCase):
    def test_detects_stl1001(self):
        from mpynode.native.toolchain import toolchain as tc

        hint = tc.diagnose_compiler_log(
            "yvals_core.h(921): error C2338: static_assert failed: 'error "
            "STL1001: Unexpected compiler version, expected MSVC Compiler "
            "19.50 or newer.'")
        self.assertIsNotNone(hint)
        self.assertIn("cl.exe", hint)

    def test_none_for_unknown_or_empty(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertIsNone(tc.diagnose_compiler_log("error C2065: undeclared"))
        self.assertIsNone(tc.diagnose_compiler_log(""))
        self.assertIsNone(tc.diagnose_compiler_log(None))


class TestToolsetConsistency(unittest.TestCase):
    """Parse + compare MSVC toolset versions so the doctor can pinpoint an
    STL1001 (compiler-older-than-headers) BEFORE the cryptic compile error."""

    _CL = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools"
           r"\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe")
    _CL_NEW = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools"
               r"\MSVC\14.51.36231\bin\Hostx64\x64\cl.exe")
    _INC_NEW = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools"
                r"\MSVC\14.51.36231\include;"
                r"C:\Program Files (x86)\Windows Kits\10\include\10.0.22621.0\ucrt")

    def test_toolset_from_path(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.msvc_toolset_from_path(self._CL), "14.44.35207")
        self.assertEqual(tc.msvc_toolset_from_path(self._CL_NEW), "14.51.36231")

    def test_toolset_from_path_case_insensitive_and_none(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(
            tc.msvc_toolset_from_path(self._CL.replace("MSVC", "msvc")),
            "14.44.35207")
        self.assertIsNone(tc.msvc_toolset_from_path(r"C:\bin\cl.exe"))
        self.assertIsNone(tc.msvc_toolset_from_path(None))
        self.assertIsNone(tc.msvc_toolset_from_path(""))

    def test_toolset_from_path_ignores_stray_non_vs_msvc_folder(self):
        from mpynode.native.toolchain import toolchain as tc

        # A folder merely NAMED MSVC (not the Visual Studio VC\Tools\MSVC tree)
        # must NOT be mistaken for a toolset -- it would yield a bogus version
        # and a false toolset-mismatch alarm.
        self.assertIsNone(
            tc.msvc_toolset_from_path(r"C:\MyTools\MSVC\1.0\bin\cl.exe"))

    def test_toolsets_from_include(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertEqual(tc.msvc_toolsets_from_include(self._INC_NEW),
                         ["14.51.36231"])
        # Order preserved + deduped across multiple toolset entries (realistic
        # VC\Tools\MSVC paths).
        base = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools"
        two = (base + r"\MSVC\14.44.35207\include;"
               + base + r"\MSVC\14.51.36231\include;"
               + base + r"\MSVC\14.44.35207\atlmfc\include")
        self.assertEqual(tc.msvc_toolsets_from_include(two),
                         ["14.44.35207", "14.51.36231"])
        # A folder merely named MSVC outside the VC\Tools tree is ignored.
        self.assertEqual(
            tc.msvc_toolsets_from_include(r"C:\MyTools\MSVC\1.0\include"), [])
        self.assertEqual(tc.msvc_toolsets_from_include(""), [])
        self.assertEqual(tc.msvc_toolsets_from_include(None), [])

    def test_mismatch_detected_when_cl_older_than_headers(self):
        from mpynode.native.toolchain import toolchain as tc

        # The classic STL1001 setup: a stray OLD cl on PATH, NEW headers on
        # INCLUDE.
        hint = tc.diagnose_toolset_mismatch(self._CL, self._INC_NEW)
        self.assertIsNotNone(hint)
        self.assertIn("14.44.35207", hint)
        self.assertIn("14.51.36231", hint)
        self.assertIn("STL1001", hint)

    def test_no_mismatch_when_consistent(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertIsNone(tc.diagnose_toolset_mismatch(self._CL_NEW,
                                                       self._INC_NEW))

    def test_no_verdict_when_unknown(self):
        from mpynode.native.toolchain import toolchain as tc

        # Can't parse a toolset from a bare cl, or no MSVC headers on INCLUDE ->
        # no false alarm.
        self.assertIsNone(tc.diagnose_toolset_mismatch(r"C:\bin\cl.exe",
                                                       self._INC_NEW))
        self.assertIsNone(tc.diagnose_toolset_mismatch(self._CL, ""))
        self.assertIsNone(tc.diagnose_toolset_mismatch(None, None))


class TestRunStreaming(unittest.TestCase):
    def test_streams_each_line_and_accumulates_full_text(self):
        from mpynode.native.toolchain import toolchain as tc

        seen = []

        class _Proc:
            stdout = ["compiling a\n", "compiling b\n", "done\n"]

            def wait(self):
                return 0

        rc, text = tc.run_streaming(["cl", "x.cpp"], env={"PATH": "/x"},
                                    log_cb=seen.append,
                                    _popen=lambda *a, **k: _Proc())
        self.assertEqual(rc, 0)
        self.assertEqual(text, "compiling a\ncompiling b\ndone\n")
        # streamed line-by-line, newline stripped
        self.assertEqual(seen, ["compiling a", "compiling b", "done"])

    def test_returns_nonzero_rc_and_works_without_log_cb(self):
        from mpynode.native.toolchain import toolchain as tc

        class _Proc:
            stdout = iter(["error C2338\n"])

            def wait(self):
                return 2

        rc, text = tc.run_streaming(["cl"], _popen=lambda *a, **k: _Proc())
        self.assertEqual(rc, 2)
        self.assertEqual(text, "error C2338\n")

    def test_a_failing_log_cb_never_breaks_the_run(self):
        from mpynode.native.toolchain import toolchain as tc

        def boom(_line):
            raise RuntimeError("ui callback blew up")

        class _Proc:
            stdout = ["line\n"]

            def wait(self):
                return 0

        rc, text = tc.run_streaming(["cl"], log_cb=boom,
                                    _popen=lambda *a, **k: _Proc())
        self.assertEqual(rc, 0)
        self.assertEqual(text, "line\n")


def _fallback_cand(name, d="/usr/local/bin"):
    """The candidate path ``find_executable`` actually builds for a fallback dir.

    Production does ``os.path.join(os.path.expanduser(d), name)``, so on Windows
    the separator is a BACKSLASH (``/usr/local/bin\\claude``). Tests that
    hardcoded the POSIX spelling never matched their own mock there -- measured
    2026-08-14, three failures that had nothing to do with the code under test.
    """
    return os.path.join(os.path.expanduser(d), name)


class TestCliLaunchHelpers(unittest.TestCase):
    def test_resolve_executable_unknown_returns_name(self):
        from mpynode.native.toolchain import toolchain as tc

        name = "definitely_not_a_real_binary_xyz_42"
        self.assertEqual(tc.resolve_executable(name), name)

    def test_cli_subprocess_kwargs_utf8_everywhere(self):
        from mpynode.native.toolchain import toolchain as tc

        for osn in ("darwin", "win32", "linux"):
            kw = tc.cli_subprocess_kwargs(os_name=osn)
            self.assertEqual(kw["encoding"], "utf-8")
            self.assertEqual(kw["errors"], "replace")

    def test_cli_subprocess_kwargs_no_window_only_on_windows(self):
        from mpynode.native.toolchain import toolchain as tc

        self.assertIn("creationflags", tc.cli_subprocess_kwargs(os_name="win32"))
        self.assertNotIn("creationflags",
                         tc.cli_subprocess_kwargs(os_name="darwin"))
        self.assertNotIn("creationflags",
                         tc.cli_subprocess_kwargs(os_name="linux"))

    def test_find_executable_uses_which_when_on_path(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc.shutil, "which",
                                        return_value="/opt/x/claude"):
            self.assertEqual(tc.find_executable("claude"), "/opt/x/claude")

    def test_find_executable_falls_back_to_common_dirs_off_path(self):
        # A Finder-launched macOS app inherits the minimal launchd PATH, so
        # which() misses /usr/local/bin and a terminal-visible `claude` is
        # invisible. find_executable must still find it in the common dirs.
        from mpynode.native.toolchain import toolchain as tc

        cand = _fallback_cand("claude")
        # isfile is mocked too: production requires isfile AND access, so with
        # only access mocked this passed on macOS purely because a real
        # /usr/local/bin/claude happened to exist on the box.
        with unittest.mock.patch.object(tc.shutil, "which", return_value=None), \
                unittest.mock.patch.object(
                    tc.os, "access", side_effect=lambda p, m: p == cand), \
                unittest.mock.patch.object(
                    tc.os.path, "isfile", side_effect=lambda p: p == cand):
            self.assertEqual(tc.find_executable("claude"), cand)

    def test_find_executable_absent_returns_none(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc.shutil, "which", return_value=None), \
                unittest.mock.patch.object(tc.os, "access", return_value=False):
            self.assertIsNone(tc.find_executable("nope_xyz_42"))

    def test_find_executable_absolute_checks_executable_bit(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(
                tc.os, "access",
                side_effect=lambda p, m: p == "/abs/claude"), \
                unittest.mock.patch.object(
                    tc.os.path, "isfile",
                    side_effect=lambda p: p == "/abs/claude"):
            self.assertEqual(tc.find_executable("/abs/claude"), "/abs/claude")
            self.assertIsNone(tc.find_executable("/abs/missing"))

    def test_resolve_executable_uses_fallback_dirs(self):
        # resolve_executable must delegate to find_executable so the interactive
        # assistant's _run() resolves a claude that is off the process PATH.
        from mpynode.native.toolchain import toolchain as tc

        cand = _fallback_cand("claude")
        with unittest.mock.patch.object(tc.shutil, "which", return_value=None), \
                unittest.mock.patch.object(
                    tc.os, "access", side_effect=lambda p, m: p == cand), \
                unittest.mock.patch.object(
                    tc.os.path, "isfile", side_effect=lambda p: p == cand):
            self.assertEqual(tc.resolve_executable("claude"), cand)

    def test_find_executable_rejects_absolute_directory(self):
        # os.access(dir, X_OK) is True for any searchable directory; shutil.which
        # excluded dirs. A CLAUDE_BIN pointing at an install DIR must not resolve.
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc.os, "access", return_value=True), \
                unittest.mock.patch.object(tc.os.path, "isfile",
                                           return_value=False):
            self.assertIsNone(tc.find_executable("/opt/homebrew/bin"))

    def test_find_executable_rejects_fallback_directory(self):
        # A directory literally named claude/gemini/codex inside a fallback dir
        # (or an empty override that joins to the dir itself) must not resolve.
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc.shutil, "which", return_value=None), \
                unittest.mock.patch.object(tc.os, "access", return_value=True), \
                unittest.mock.patch.object(tc.os.path, "isfile",
                                           return_value=False):
            self.assertIsNone(tc.find_executable("claude"))
            self.assertIsNone(tc.find_executable(""))

    def test_find_executable_still_returns_real_file(self):
        # Regression guard for the isfile fix: a genuine file is still resolved.
        from mpynode.native.toolchain import toolchain as tc

        cand = _fallback_cand("claude")
        with unittest.mock.patch.object(tc.shutil, "which", return_value=None), \
                unittest.mock.patch.object(
                    tc.os, "access", side_effect=lambda p, m: p == cand), \
                unittest.mock.patch.object(
                    tc.os.path, "isfile", side_effect=lambda p: p == cand):
            self.assertEqual(tc.find_executable("claude"), cand)


# ===================== from test_native_build_scripts.py =====================
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__native_build_scripts():
    standalone_init()


_SPEC = {"suggested": {"node_type_name": "fooNode", "class_name": "FooNode",
                       "mpx_base": "MPxNode"}}

# A hover-capable locator spec -> the build must link Maya's Qt frameworks.
_HOVER_SPEC = {"suggested": {"node_type_name": "gizmoCube",
                            "class_name": "GizmoCube",
                            "mpx_base": "MPxLocatorNode"},
              "needs_hover": True}

# `for /d %%D in (...) do (... %%~fD ...)` is how a batch FILE spells a loop
# variable, and the Maya-version resolver (toolchain.maya_resolver_bat) is built
# on one. That is the ONLY legitimate `%%` in a generated .bat, so strip exactly
# those tokens before asserting: what remains is a Python %-format slip that
# leaked an uncollapsed escape into the output, which is what these guards are
# for. Paired with test_bat_resolver_emits_a_real_for_loop below, so stripping
# can never hide a resolver that stopped being emitted.
_BAT_FOR_VAR_RE = re.compile(r"%%(?:~f)?D\b")


def _uncollapsed_percent(body):
    """True if the .bat carries a `%%` that is NOT a for-loop variable."""
    return "%%" in _BAT_FOR_VAR_RE.sub("", body)


class TestCodegenBuildScripts(unittest.TestCase):
    def test_dispatcher_picks_sh_on_unix(self):
        from mpynode.native import compiler as codegen

        name, body = codegen.generate_build_script(_SPEC, maya="/M",
                                                   os_name="darwin")
        self.assertEqual(name, "build.sh")
        self.assertIn("clang++", body)
        self.assertIn("fooNode.bundle", body)

    def test_dispatcher_picks_bat_on_windows(self):
        from mpynode.native import compiler as codegen

        name, body = codegen.generate_build_script(_SPEC, maya=r"C:\M",
                                                   os_name="win32")
        self.assertEqual(name, "build.bat")
        self.assertIn("cl /nologo", body)
        self.assertIn("NT_PLUGIN", body)
        self.assertIn("/OUT:", body)
        self.assertIn("fooNode.mll", body)
        self.assertIn("initializePlugin", body)

    def test_build_sh_recipe_unchanged(self):
        from mpynode.native import compiler as codegen

        body = codegen.generate_build_sh(_SPEC, maya="/M")
        self.assertIn("clang++ -std=c++17 -O3 -ffp-contract=off -arch arm64 "
                      "-bundle", body)
        self.assertIn('-o "$HERE/fooNode.bundle" "$HERE/fooNode.cpp"', body)
        self.assertIn("-lOpenMaya", body)

    def test_generated_scripts_disable_fp_contraction(self):
        """The emitted rebuild scripts must match the toolchain's parity flags.

        A hand-rebuild that contracts `a*b + c` into an FMA rounds once where
        numpy rounds twice, so the rebuilt plugin silently stops being
        bit-identical. -O2-without-contract was the old default and did exactly
        that; guard both platforms against the regression.
        """
        from mpynode.native import compiler as codegen

        sh = codegen.generate_build_sh(_SPEC, maya="/M")
        self.assertIn("-ffp-contract=off", sh)
        self.assertNotIn("-ffast-math", sh)
        self.assertNotIn("-Ofast", sh)

        bat = codegen.generate_build_bat(_SPEC, maya=r"C:\M")
        self.assertIn("/fp:precise", bat)
        self.assertNotIn("/fp:fast", bat)

    def test_build_bat_mirrors_the_msvc_charset_and_crt_flags(self):
        from mpynode.native import compiler as codegen

        body = codegen.generate_build_bat(_SPEC, maya=r"C:\M")
        self.assertIn("/utf-8", body)
        self.assertIn("_CRT_SECURE_NO_WARNINGS", body)
        self.assertFalse(_uncollapsed_percent(body))

    def test_build_bat_has_no_uncollapsed_percent(self):
        from mpynode.native import compiler as codegen

        body = codegen.generate_build_bat(_SPEC, maya=r"C:\M")
        self.assertFalse(_uncollapsed_percent(body))
        self.assertIn("%MAYA%", body)        # single-% variable refs survive
        self.assertIn("%~dp0", body)

    def test_bat_resolver_emits_a_real_for_loop(self):
        """The for-loop tokens _uncollapsed_percent() strips must actually be
        there. Without this, a resolver that stopped being emitted would make
        every `%%` guard above pass on a script that cannot find Maya."""
        from mpynode.native import compiler as codegen

        body = codegen.generate_build_bat(_SPEC, maya=r"C:\M")
        self.assertIn("for /d %%D in (", body)
        self.assertIn("%%~fD", body)
        self.assertIn('set "_V=%~1"', body)   # the version argument itself

    def test_build_sh_no_qt_without_needs_hover(self):
        from mpynode.native import compiler as codegen

        body = codegen.generate_build_sh(_SPEC, maya="/M")
        self.assertNotIn("-framework", body)
        self.assertNotIn("QtGui", body)

    def test_build_sh_adds_qt_when_needs_hover(self):
        from mpynode.native import compiler as codegen

        body = codegen.generate_build_sh(_HOVER_SPEC, maya="/M")
        self.assertIn("-framework QtGui", body)
        self.assertIn("Frameworks", body)
        self.assertIn("-Wl,-rpath,", body)
        # still a well-formed locator build
        self.assertIn("gizmoCube.bundle", body)

    def test_build_bat_adds_qt_when_needs_hover(self):
        from mpynode.native import compiler as codegen

        body = codegen.generate_build_bat(_HOVER_SPEC, maya=r"C:\M")
        self.assertFalse(_uncollapsed_percent(body))
        self.assertIn("Qt6Gui.lib", body)

    def _hover_bats(self):
        """The three hand-runnable .bat mirrors, for a hover-capable node."""
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import bundler

        return (
            ("porter", codegen.generate_build_bat(_HOVER_SPEC, maya=r"C:\M")),
            ("multi", bundler.make_build_bat("myBundle", ["frag_a.cpp"],
                                             needs_qt=True)),
            ("single", bundler.make_single_build_bat("myBundle", "foo.cpp",
                                                     ["OpenMaya"],
                                                     needs_qt=True)),
        )

    def test_every_windows_bat_carries_the_qt_msvc_flags(self):
        """All THREE hand-runnable .bat mirrors must emit the MSVC-only flags
        Qt 6 requires. Round 1 put /Zc:__cplusplus into qt_compile_flags() only,
        so a hover node's SHIPPED build.bat still died at C1189 (then C2338)
        while the programmatic build succeeded. Windows 2026-08-14."""
        from mpynode.native.toolchain import toolchain as tc

        want = tc.qt_msvc_flags()
        self.assertIn("/Zc:__cplusplus", want)
        self.assertIn("/permissive-", want)

        for label, body in self._hover_bats():
            for flag in want:
                self.assertIn(flag, body,
                              "%s build.bat is missing %s" % (label, flag))
            # The header search path is resolved BY THE SCRIPT, so the recipe
            # references the variable the resolver sets -- never a baked path.
            self.assertIn('/I "%QTINC%"', body, label)
            self.assertIn('set "QTINC=', body, label)
            # MSVC 14.51 dropped stdext::checked_array_iterator; the shim is
            # named BARE so the script stays host-independent (copy ships
            # beside the sources).
            self.assertIn("/FI " + tc.QT_MSVC_COMPAT_HEADER, body, label)
            self.assertFalse(_uncollapsed_percent(body), label)

    def test_bat_qt_recipe_does_not_depend_on_the_generating_host(self):
        """ROUND 3. The .bat is a cross-platform artifact: it is GENERATED on
        macOS and RUN on Windows. Rounds 1 and 2 baked in the host-resolved
        qt_include_dir, which is None on macOS, so every hover node shipped a
        build.bat with no Qt include path and no MSVC Qt flags -- and the test
        that used to sit here asserted exactly that as correct ("must keep
        today's exact bytes"). It died on Windows at 'C1083: Cannot open include
        file: QtCore/QPoint', 14 translation units in. MEASURED 2026-08-31,
        Maya 2025 + VS 2022.

        A macOS host must now emit BYTE-IDENTICAL Windows scripts."""
        from mpynode.native.toolchain import toolchain as tc

        on_windows = self._hover_bats()
        # A macOS host: nothing about the Windows Qt layout is knowable there.
        with unittest.mock.patch.object(tc, "is_windows", return_value=False), \
             unittest.mock.patch.object(tc, "is_macos", return_value=True), \
             unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=None):
            on_macos = self._hover_bats()

        for (label, win), (_, mac) in zip(on_windows, on_macos):
            self.assertEqual(win, mac,
                             "%s build.bat differs by generating host" % label)
            for flag in tc.qt_msvc_flags():
                self.assertIn(flag, mac, label)
            self.assertIn('/I "%QTINC%"', mac, label)

    def test_no_qt_recipe_when_the_node_has_no_hover(self):
        """The resolver and its flags are scoped to hover nodes: a plain build
        must not gain a Qt probe it would then fail on."""
        from mpynode.native.compiler import bundler

        for body in (bundler.make_build_bat("plain", ["frag_a.cpp"]),
                     bundler.make_single_build_bat("plain", "foo.cpp",
                                                   ["OpenMaya"])):
            self.assertNotIn("QTINC", body)
            self.assertNotIn("/permissive-", body)
            self.assertNotIn("/Zc:__cplusplus", body)
            self.assertNotIn("/FI", body)

    def test_qt_resolver_bat_probes_and_fails_loudly(self):
        """The resolver must actually PROBE (not just set a variable) and must
        name the unextracted archive when it finds nothing -- that message is
        the whole reason a user can act on the failure."""
        from mpynode.native.toolchain import toolchain as tc

        body = "\r\n".join(tc.qt_resolver_bat())
        # Same sentinel the Python resolver uses, with WINDOWS separators: a
        # macOS os.path.join here would emit 'QtGui/QCursor'.
        self.assertIn(r"QtGui\QCursor", body)
        self.assertNotIn("QtGui/QCursor", body)
        self.assertIn(tc.QT_INCLUDE_ENV, body)
        self.assertIn("for /d %%D in (", body)      # the subdirectory sweep
        self.assertIn("%%~fD", body)
        self.assertIn("exit /b 1", body)
        self.assertIn("-include.zip", body)         # names the archive
        self.assertFalse(_uncollapsed_percent(body))

    def test_bat_diagnostics_reach_stderr(self):
        """`1^>^&2` inside a parenthesised if-block is LITERAL TEXT: cmd prints
        'msg 1>&2' to STDOUT and nothing reaches stderr. MEASURED against the
        shipped build.bat on Windows 2026-08-31 -- every resolver diagnostic in
        the project was going to the wrong stream with a visible '1>&2' suffix.
        Plain `1>&2` redirects correctly."""
        from mpynode.native.toolchain import toolchain as tc

        bodies = ["\r\n".join(tc.maya_resolver_bat("win32")),
                  "\r\n".join(tc.qt_resolver_bat())]
        bodies += [b for _, b in self._hover_bats()]
        for body in bodies:
            self.assertNotIn("1^>^&2", body)
            self.assertIn("1>&2", body)
            # ^ is not an escape inside double quotes either.
            self.assertNotIn('"^<', body)

    def test_load_test_extension_follows_platform(self):
        from mpynode.native.toolchain import toolchain
        from mpynode.native import compiler as codegen

        body = codegen.generate_load_test(_SPEC)
        self.assertIn("fooNode" + toolchain.plugin_ext(), body)
        # extension-agnostic load: derives the plugin name from the path.
        self.assertIn("os.path.basename(BUNDLE)", body)


class TestBundlerBuildScripts(unittest.TestCase):
    def test_make_build_sh_unchanged(self):
        from mpynode.native.compiler import bundler

        body = bundler.make_build_sh("myBundle", ["frag_a.cpp", "frag_b.cpp"])
        self.assertIn("clang++ -std=c++17 -arch arm64 -bundle", body)
        self.assertIn("myBundle.bundle", body)
        self.assertIn("plugin_main.cpp", body)

    def test_make_build_sh_no_qt_by_default(self):
        from mpynode.native.compiler import bundler

        body = bundler.make_build_sh("myBundle", ["frag_a.cpp"])
        self.assertNotIn("-framework", body)
        self.assertNotIn("QtGui", body)

    def test_make_build_sh_adds_qt_when_needs_qt(self):
        from mpynode.native.compiler import bundler

        body = bundler.make_build_sh("myBundle", ["frag_a.cpp"], needs_qt=True)
        self.assertIn("-framework QtGui", body)
        self.assertIn("-Wl,-rpath,", body)

    def test_make_build_bat_no_uncollapsed_percent(self):
        from mpynode.native.compiler import bundler

        body = bundler.make_build_bat("myBundle", ["frag_a.cpp", "frag_b.cpp"])
        self.assertFalse(_uncollapsed_percent(body))

    def test_make_build_bat_echo_names_the_file_it_actually_wrote(self):
        from mpynode.native.compiler import bundler

        # The link writes %HERE%..\<name>.mll (the bundle lives one level up,
        # beside build/); the echo used to claim %HERE%<name>.mll.
        body = bundler.make_build_bat("myBundle", ["frag_a.cpp"])
        self.assertIn('/OUT:"%HERE%..\\myBundle.mll"', body)
        self.assertIn("echo Built: %HERE%..\\myBundle.mll", body)

    def test_make_build_bat_mirrors_the_msvc_charset_and_crt_flags(self):
        from mpynode.native.compiler import bundler

        body = bundler.make_build_bat("myBundle", ["frag_a.cpp"])
        self.assertIn("/utf-8", body)
        self.assertIn("_CRT_SECURE_NO_WARNINGS", body)

    def test_make_single_build_bat_mirrors_the_charset_and_crt_flags(self):
        from mpynode.native.compiler import bundler

        body = bundler.make_single_build_bat("myBundle", "foo.cpp",
                                             ["OpenMaya"])
        self.assertIn("/utf-8", body)
        self.assertIn("_CRT_SECURE_NO_WARNINGS", body)

    def test_make_build_bat_cleanup_cannot_fail_the_build(self):
        """A successful build must exit 0 even if the object sweep hiccups.

        `del %OBJS% 2>nul` returns errorlevel 1 when a file is already gone, and
        `echo` does not reset it, so the script exited 1 after linking fine.
        MEASURED on Windows 2026-09-01: mPyMega.mll was on disk at 2.7 MB and
        the wrapper still printed BUILD FAILED and skipped the install copy.
        build.sh is immune -- a shell script's status is its last command."""
        from mpynode.native.compiler import bundler

        body = bundler.make_build_bat("myBundle", ["frag_a.cpp"])
        lines = [l for l in body.splitlines() if l.strip()]
        self.assertIn("del %OBJS%", body, "the cleanup sweep went missing")
        self.assertEqual(
            lines[-1].strip(), "exit /b 0",
            "build.bat must end by forcing success; otherwise `del`'s "
            "errorlevel decides whether a good build looks failed")
        # The echo must still be the last thing the user SEES.
        self.assertTrue(lines[-2].startswith("echo Built:"), lines[-2])

    def test_make_build_bat_resolves_qt_in_the_script(self):
        """``needs_qt`` alone must produce a COMPLETE Windows recipe.

        This test used to assert the opposite -- that a script generated without
        a host-resolved ``qt_include`` (i.e. every script this macOS-developed
        project ships) correctly carried no Qt include path. That is precisely
        the defect: it died on Windows at C1083. There is no ``qt_include``
        parameter any more; the script resolves %QTINC% itself."""
        from mpynode.native.compiler import bundler

        got = bundler.make_build_bat("myBundle", ["frag_a.cpp"], needs_qt=True)
        self.assertIn('set "QTINC=', got)          # the resolver is present
        self.assertIn('/I "%QTINC%"', got)         # ...and actually used
        self.assertIn("/Zc:__cplusplus", got)
        self.assertIn("/permissive-", got)
        self.assertFalse(_uncollapsed_percent(got))
        # No absolute host path may be baked in.
        self.assertNotIn(r"C:\M\include\qt", got)

    def test_make_build_bat_links_all_objs(self):
        from mpynode.native.compiler import bundler

        body = bundler.make_build_bat("myBundle", ["frag_a.cpp", "frag_b.cpp"])
        self.assertIn("frag_a.obj", body)
        self.assertIn("frag_b.obj", body)
        self.assertIn("plugin_main.obj", body)
        self.assertIn("/OUT:", body)
        self.assertIn("myBundle.mll", body)
        self.assertIn("OpenMaya.lib", body)
        self.assertIn("initializePlugin", body)
        # accumulates objects into %OBJS% then links them
        self.assertIn('set "OBJS=', body)


class TestAssembleQtGate(unittest.TestCase):
    """A hover bundle whose Qt headers cannot be located must fail LOUDLY at
    GENERATION time. Otherwise the build emits a build.bat whose first hover TU
    dies at C1083 and, because the .bat is a serial ``if errorlevel 1 exit /b 1``
    chain, the whole 41-node plugin never links -- with no actionable message."""

    def test_refuses_when_qt_headers_are_unresolvable(self):
        import tempfile

        from mpynode.native.compiler import bundler
        from mpynode.native.compiler.errors import UnsupportedSpec

        msg = "cannot find Qt; set MPYNODE_QT_INCLUDE"
        with tempfile.TemporaryDirectory() as td, \
                unittest.mock.patch.object(bundler.toolchain,
                                           "qt_include_problem",
                                           return_value=msg):
            with self.assertRaises(UnsupportedSpec) as ctx:
                bundler.assemble([("fooNode", os.path.join(td, "foo.cpp"))],
                                 "myBundle", os.path.join(td, "out"),
                                 needs_qt=True, compile_now=False)
        self.assertIn("MPYNODE_QT_INCLUDE", str(ctx.exception))

    def test_a_non_hover_bundle_is_never_gated(self):
        import tempfile

        from mpynode.native.compiler import bundler

        with tempfile.TemporaryDirectory() as td, \
                unittest.mock.patch.object(bundler.toolchain,
                                           "qt_include_problem",
                                           return_value="boom"):
            # needs_qt=False -> the gate must not even be consulted; a missing
            # source is reported in the usual way, never raised.
            rep = bundler.assemble([("fooNode", os.path.join(td, "foo.cpp"))],
                                   "myBundle", os.path.join(td, "out"),
                                   needs_qt=False, compile_now=False)
        self.assertFalse(rep["ok"])


class TestRepoTestRunnerParity(unittest.TestCase):
    """``tools/run_tests.bat`` is the Windows mirror of ``tools/run_tests.sh``.

    It cannot be executed here, so the properties that make it a real gate are
    pinned as text. Every mayapy invocation must go through
    ``tools/_unittest_exit.py``: after ``maya.standalone.initialize()`` mayapy's
    teardown forces exit 0, so a plain ``-m unittest`` run reports failures as
    success -- and the batch file must then hand that status back to the caller
    across ``endlocal``. The environment must not drift from the shell runner
    either, since a test module that reads ``MPYNODE_ROOT`` raises at import.
    """

    @classmethod
    def setUpClass(cls):
        root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
        with open(os.path.join(root, "tools", "run_tests.bat")) as fh:
            cls.bat = fh.read()
        with open(os.path.join(root, "tools", "run_tests.sh")) as fh:
            cls.sh = fh.read()

    def _invocations(self):
        return [ln.strip() for ln in self.bat.splitlines()
                if "%MAYAPY%" in ln
                and not ln.strip().upper().startswith("REM")]

    def test_every_mayapy_call_routes_through_the_exit_shim(self):
        calls = self._invocations()
        self.assertTrue(calls, "run_tests.bat never invokes %MAYAPY%")
        for call in calls:
            self.assertIn("_unittest_exit.py", call,
                          "bypasses the exit shim: %s" % call)
            self.assertNotIn("-m unittest", call,
                             "mayapy -m unittest always exits 0: %s" % call)

    def test_the_real_status_survives_endlocal(self):
        self.assertIn("%ERRORLEVEL%", self.bat)
        self.assertIn("exit /b", self.bat)

    def test_environment_matches_the_shell_runner(self):
        for setting in ("MPYNODE_USE_STUDIO=1", "MPYNODE_ROOT="):
            self.assertIn(setting, self.sh)
            self.assertIn(setting, self.bat,
                          "run_tests.bat drifted from run_tests.sh on %s"
                          % setting)

    def test_both_runners_anchor_on_the_repo_root_not_on_tools(self):
        """Both live in tools/ but every path they set is repo-root-relative.

        The .sh derives it (``cd "$TOOLS_DIR/.."``); the .bat has to resolve
        ``%~dp0..`` the same way. A bare ``HERE=%~dp0`` silently points
        PYTHONPATH / MAYA_PLUG_IN_PATH / MPYNODE_ROOT at tools\\ -- every path
        still *looks* well-formed, so the failure is an import error deep in
        setUpModule rather than anything naming the runner.
        """
        self.assertIn('cd "$TOOLS_DIR/.."', self.sh)
        self.assertIn('"%~dp0.."', self.bat,
                      "run_tests.bat does not walk up out of tools\\")
        self.assertNotIn('set "HERE=%~dp0"', self.bat,
                         "HERE is the tools dir, not the repo root")


class TestParitySweepLaunchers(unittest.TestCase):
    """The compiled-parity gate's two launchers, pinned the same way.

    ``run_parity_sweep.bat`` ended its run with a bare ``endlocal``, which
    discards the runner's status -- so the gate reported success no matter what
    the sweep found, exactly the defect ``run_tests.bat`` already carries the
    fix for. Both launchers also live in tools/ and must anchor one level up.
    """

    @classmethod
    def setUpClass(cls):
        root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
        with open(os.path.join(root, "tools", "run_parity_sweep.bat")) as fh:
            cls.bat = fh.read()
        with open(os.path.join(root, "tools", "run_parity_sweep.sh")) as fh:
            cls.sh = fh.read()

    def test_the_real_status_survives_endlocal(self):
        self.assertIn("%ERRORLEVEL%", self.bat)
        self.assertIn("exit /b", self.bat,
                      "a bare `endlocal` drops the sweep's exit status, so the "
                      "gate always looks green")

    def test_both_anchor_on_the_repo_root(self):
        self.assertIn('"$TOOLS_DIR/.."', self.sh)
        self.assertIn('"%~dp0.."', self.bat)

    def test_the_runner_refuses_to_start_without_fixtures(self):
        """The .bundle fixtures are gitignored, so a fresh clone has none. The
        sweep must say that and exit, not emit twelve '????' rows."""
        root = os.environ.get("MPYNODE_ROOT") or os.getcwd()
        path = os.path.join(root, "tools", "parity_sweep",
                            "run_parity_sweep.py")
        with open(path) as fh:
            src = fh.read()
        self.assertIn("_missing_bundles", src)
        self.assertIn("build_compiled_templates.sh", src,
                      "the bail-out must name the command that fixes it")


def setUpModule():
    _setUpModule__toolchain()
    _setUpModule__native_build_scripts()


class QtMsvcStdextCompatTests(unittest.TestCase):
    """MSVC 14.51 (VS 2026 18.6) removed stdext::checked_array_iterator; Maya
    2025's Qt 6.5.3 reaches it from qvarlengtharray.h(379, 890) on every MSVC.
    MEASURED 2026-09-08: animatedText.cpp died with C3861/C2065 'stdext' and
    compiled clean once nd_msvc_stdext_compat.h was force-included (/FI)."""

    def test_header_exists_and_is_self_gated(self):
        from mpynode.native.toolchain import toolchain as tc

        path = tc.qt_msvc_compat_header_path()
        self.assertTrue(os.path.isfile(path), path)
        self.assertEqual(os.path.basename(path), tc.QT_MSVC_COMPAT_HEADER)
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        # 14.50 still ships the class (99 hits in its <iterator>); 14.51 has 0.
        # A 1950 gate would redefine it on 14.50.
        self.assertIn("_MSC_VER >= 1951", body)
        self.assertIn("make_checked_array_iterator", body)
        self.assertIn("make_unchecked_array_iterator", body)
        self.assertIn("#pragma once", body)

    def test_windows_qt_compile_flags_force_include_the_header(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=r"C:\M\include\qt"):
            flags = tc.qt_compile_flags(r"C:\M", os_name="win32")
        i = flags.index("/FI")
        self.assertEqual(flags[i + 1], tc.qt_msvc_compat_header_path())
        # macOS / Linux use Qt's own (x) fallback for the macro: not their bug.
        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value="/M/include/qt"):
            self.assertNotIn("/FI", tc.qt_compile_flags("/M", os_name="linux"))
        self.assertNotIn("/FI", tc.qt_compile_flags("/M", os_name="darwin"))

    def test_compile_cmds_carry_FI_only_for_qt_builds(self):
        from mpynode.native.toolchain import toolchain as tc

        with unittest.mock.patch.object(tc, "qt_include_dir",
                                        return_value=r"C:\qt"):
            obj_qt = tc.compile_object_cmd(
                "cl", r"C:\x\frag.cpp", r"C:\x\frag.obj",
                include_dir=r"C:\M\include", frag=True, os_name="win32",
                qt=True, maya=r"C:\M")
            plugin_qt = tc.compile_to_plugin_cmd(
                "cl", r"C:\x\n.cpp", r"C:\x\n.mll",
                include_dir=r"C:\M\include", lib_dir=r"C:\M\lib",
                libs=["OpenMaya"], os_name="win32", qt=True, maya=r"C:\M")
        plain = tc.compile_object_cmd(
            "cl", r"C:\x\frag.cpp", r"C:\x\frag.obj",
            include_dir=r"C:\M\include", frag=True, os_name="win32")
        for cmd in (obj_qt, plugin_qt):
            self.assertIn("/FI", cmd)
            self.assertTrue(cmd[cmd.index("/FI") + 1].endswith(
                tc.QT_MSVC_COMPAT_HEADER), cmd)
        self.assertNotIn("/FI", plain)

    def test_ship_copies_bytes_for_qt_and_removes_otherwise(self):
        from mpynode.native.toolchain import toolchain as tc

        with tempfile.TemporaryDirectory() as d:
            dst = tc.ship_qt_msvc_compat_header(d, True)
            self.assertEqual(dst, os.path.join(d, tc.QT_MSVC_COMPAT_HEADER))
            with open(dst, "rb") as a, \
                 open(tc.qt_msvc_compat_header_path(), "rb") as b:
                self.assertEqual(a.read(), b.read())
            self.assertIsNone(tc.ship_qt_msvc_compat_header(d, False))
            self.assertFalse(os.path.exists(dst))


class BatLocalScopeTests(unittest.TestCase):
    """Every generated .bat opens with setlocal. MEASURED 2026-09-08: without
    it the inner build\\build.bat overwrote the calling wrapper's HERE through
    `call`, so templates/All Templates Plugin/build.bat linked mPyMega.mll and
    then failed its install copy (exit 1, nothing in plugin\\). `exit /b N`
    still returns N -- it ends the local scope on the way out."""

    def test_every_bat_opens_with_setlocal(self):
        from mpynode.native import compiler as codegen
        from mpynode.native.compiler import bundler

        bodies = (
            ("porter", codegen.generate_build_bat(_HOVER_SPEC, maya=r"C:\M")),
            ("multi", bundler.make_build_bat("b", ["frag_a.cpp"])),
            ("single", bundler.make_single_build_bat("b", "foo.cpp",
                                                     ["OpenMaya"])),
        )
        for label, body in bodies:
            lines = body.split("\r\n")
            self.assertEqual(lines[0], "@echo off", label)
            self.assertEqual(lines[1], "setlocal", label)
            self.assertFalse(_uncollapsed_percent(body), label)


if __name__ == "__main__":
    import unittest
    unittest.main()
