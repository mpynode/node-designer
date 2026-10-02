"""A compiled plug-in lands in a folder named after its Maya version.

``<out>/2025/<plugin>.mll`` -- never ``<out>/<plugin>_2025.mll``. Maya takes a
plug-in's NAME from its file name and records it in every scene that uses it
(``requires "mPyFoo"``), so a versioned file name would tie each scene to one
Maya release. The rule holds for every writer: the bundler (single- and
multi-node), a multi-version compile, ``bundle_prebuilt``, the bundle CLI and
the generated ``build.bat`` / ``build.sh``.

The year comes from the install's folder name (``Maya2025`` / ``maya2026``),
else from its devkit's ``MAYA_API_VERSION``. An older same-named plug-in left
one folder up by an earlier build is never deleted; one line says it is there.

The compile itself is faked (every command "writes" its outputs), so this runs
without a compiler; the script tests run the generated batch / bash blocks for
real where that shell exists.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from mpynode.native.compiler import bundler
from mpynode.native.toolchain import toolchain
from mpynode.native.toolchain import typeid_registry

from tests.compile.pipeline.test_native_bundle import _src, _write
from tests.compile.pipeline.test_native_toolchain import _touch_outputs, _uncollapsed_percent

# A version anywhere in a plug-in's file name is the bug this suite exists for.
_VERSIONED = re.compile(r"(19|20)\d\d")


def _maya_root(d, name, api=None):
    """A fake Maya install that passes the devkit check, optionally carrying an
    ``MTypes.h`` that defines ``MAYA_API_VERSION``."""
    root = os.path.join(d, name)
    inc  = os.path.join(root, "include", "maya")
    os.makedirs(inc, exist_ok=True)
    if api:
        with open(os.path.join(inc, "MTypes.h"), "w") as fh:
            fh.write("// MAYA_API_VERSION is built from major/minor/patch\n"
                     "#define MAYA_API_VERSION %s\n" % api)
    return root


@contextlib.contextmanager
def _fake_compiler(os_name="win32", compiler="cl"):
    """Every compile / link "succeeds" and writes the files it names. Yields the
    list of commands run."""
    real_current_os = toolchain.current_os
    runs            = []

    def fake_run(cmd, *, env=None, log_cb=None, cwd=None, timeout=None, **k):
        runs.append(list(cmd))
        _touch_outputs(cmd)
        return 0, ""

    with mock.patch.object(toolchain, "current_os",
                           lambda name=None: real_current_os(name) if name else os_name), \
         mock.patch.object(toolchain, "default_compiler", lambda *a: compiler), \
         mock.patch.object(toolchain, "build_env", lambda *a, **k: {"PATH": "x"}), \
         mock.patch.object(toolchain, "resolve_compiler", lambda c, *a, **k: c), \
         mock.patch.object(toolchain, "diagnose_toolset_mismatch", lambda *a, **k: None), \
         mock.patch.object(toolchain, "run_streaming", fake_run):
        yield runs


class TestMayaYear(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="maya_year_")
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_from_the_install_folder_name(self):
        for root, want in (("/Applications/Autodesk/maya2026", "2026"),
                           (r"C:\Program Files\Autodesk\Maya2025", "2025"),
                           ("C:\\Program Files\\Autodesk\\Maya2027\\", "2027"),
                           ("/usr/autodesk/MAYA2024/", "2024")):
            with self.subTest(root):
                self.assertEqual(toolchain.maya_year(root), want)

    def test_from_the_devkit_when_the_name_has_no_year(self):
        self.assertEqual(toolchain.maya_year(_maya_root(self.d, "mayaDev", "20250300")),
                         "2025")
        self.assertEqual(toolchain.maya_year(_maya_root(self.d, "dev (x86)", "20260100")),
                         "2026")

    def test_the_folder_name_is_read_first(self):
        self.assertEqual(toolchain.maya_year(_maya_root(self.d, "Maya2025", "20270000")),
                         "2025")

    def test_none_when_neither_says(self):
        self.assertIsNone(toolchain.maya_year(_maya_root(self.d, "MayaUSD")))
        self.assertIsNone(toolchain.maya_year(os.path.join(self.d, "missing")))
        self.assertIsNone(toolchain.maya_year(""))
        self.assertIsNone(toolchain.maya_year(None))

    def test_the_message_for_an_unknown_version_names_both_sources(self):
        msg = toolchain.maya_year_unknown_message("/x/mayaDev")
        self.assertIn("/x/mayaDev", msg)
        self.assertIn("MAYA_API_VERSION", msg)


class TestWhereThePluginGoes(unittest.TestCase):

    def test_the_year_folder_under_out(self):
        self.assertEqual(toolchain.plugin_dir_for("/out", "2025"),
                         os.path.join("/out", "2025"))

    def test_an_out_that_already_is_the_year_folder_takes_it(self):
        out = os.path.join("/out", "2025")
        self.assertEqual(toolchain.plugin_dir_for(out, "2025"),          out)
        self.assertEqual(toolchain.plugin_dir_for(out + os.sep, "2025"), out + os.sep)
        self.assertEqual(toolchain.plugin_dir_for(out, "2026"),          os.path.join(out, "2026"))

    def test_plugin_path_for(self):
        root = r"C:\Program Files\Autodesk\Maya2025"
        self.assertEqual(toolchain.plugin_path_for("/out", "plug", root, os_name="win32"),
                         os.path.join("/out", "2025", "plug.mll"))
        self.assertEqual(toolchain.plugin_path_for("/out", "plug", "/A/maya2026",
                                                   os_name="darwin"),
                         os.path.join("/out", "2026", "plug.bundle"))
        self.assertIsNone(toolchain.plugin_path_for("/out", "plug", "/A/mayaDev"))


class TestTheOutputFolderOfAPlugin(unittest.TestCase):
    """``out_dir_for_plugin``: from a built plug-in back to the folder holding
    its ``build/`` tree -- what the load check, the summary's source list, the
    geometry pre-arm and Open Folder read."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="year_back_")
        self.addCleanup(shutil.rmtree, self.d, True)

    def _tree(self, *build_rel):
        os.makedirs(os.path.join(self.d, *build_rel, "build"), exist_ok=True)

    def test_a_single_version_plugin_belongs_to_the_folder_above(self):
        self._tree()
        plugin = os.path.join(self.d, "2025", "plug.mll")
        self.assertEqual(toolchain.out_dir_for_plugin(plugin), self.d)

    def test_a_multi_version_plugin_belongs_to_its_own_folder(self):
        self._tree("2025")
        plugin = os.path.join(self.d, "2025", "plug.mll")
        self.assertEqual(toolchain.out_dir_for_plugin(plugin), os.path.join(self.d, "2025"))

    def test_a_year_folder_with_no_build_anywhere_still_maps_up(self):
        plugin = os.path.join(self.d, "2026", "plug.bundle")
        self.assertEqual(toolchain.out_dir_for_plugin(plugin), self.d)

    def test_a_plugin_outside_a_year_folder_is_its_own_folder(self):
        self._tree()
        for name in ("plug.mll", os.path.join("Maya2025", "plug.mll"),
                     os.path.join("v2025", "plug.mll")):
            with self.subTest(name):
                plugin = os.path.join(self.d, name)
                self.assertEqual(toolchain.out_dir_for_plugin(plugin),
                                 os.path.dirname(plugin))

    def test_it_inverts_plugin_path_for(self):
        self._tree()
        plugin = toolchain.plugin_path_for(self.d, "plug", "/A/maya2026", os_name="darwin")
        self.assertEqual(toolchain.out_dir_for_plugin(plugin), self.d)


class TestOlderPluginNote(unittest.TestCase):

    def test_none_when_nothing_sits_one_folder_up(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(toolchain.older_plugin_note(os.path.join(d, "2025", "p.mll")))

    def test_names_the_older_copy_and_leaves_it(self):
        with tempfile.TemporaryDirectory() as d:
            old = os.path.join(d, "p.mll")
            with open(old, "wb") as fh:
                fh.write(b"OLD")
            note = toolchain.older_plugin_note(os.path.join(d, "2025", "p.mll"))
            self.assertIn("older p.mll", note)
            self.assertIn(old, note)
            self.assertIn("whichever comes first on the plug-in path", note)
            self.assertNotIn("\n", note)
            with open(old, "rb") as fh:
                self.assertEqual(fh.read(), b"OLD")


class TestTheBundlerWritesTheYearFolder(unittest.TestCase):
    """``bundler.assemble`` -- the one writer every compile path goes through."""

    _PLATFORMS = (("win32", "cl", ".mll"), ("darwin", "clang++", ".bundle"))

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="year_folder_")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.maya = _maya_root(self.d, "Maya2025")

    def _nodes(self, n):
        return [(("n%dNode" % i),
                 _write(self.d, "in/n%dNode.cpp" % i,
                        _src("n%dNode" % i, "N%dNode" % i, "0x0008100%d" % i)))
                for i in range(n)]

    def _assemble(self, n, out, maya=None, **kw):
        reg = typeid_registry.TypeIdRegistry(path=os.path.join(self.d, "reg.json"))
        return bundler.assemble(self._nodes(n), "plug", out, strict=True, registry=reg,
                                maya=maya or self.maya, **kw)

    def test_single_and_multi_node_land_in_the_year_folder(self):
        for os_name, compiler, ext in self._PLATFORMS:
            for n in (1, 2):
                with self.subTest(os_name=os_name, nodes=n):
                    out = os.path.join(self.d, "out_%s_%d" % (os_name, n))
                    with _fake_compiler(os_name, compiler):
                        report = self._assemble(n, out)
                    self.assertTrue(report["ok"], report)
                    self.assertEqual(report["bundle"], os.path.join(out, "2025", "plug" + ext))
                    self.assertTrue(os.path.isfile(report["bundle"]))
                    self.assertEqual(sorted(os.listdir(out)), ["2025", "build"])
                    self.assertEqual(os.listdir(os.path.join(out, "2025")), ["plug" + ext])
                    self.assertIsNone(_VERSIONED.search(os.path.basename(report["bundle"])))

    def test_a_multi_version_tree_takes_the_plugin_beside_its_build(self):
        # compile_plugin_multi hands the bundler <out>/<year>: the plug-in goes
        # straight in, beside that version's build/ -- not <out>/2027/2027/.
        maya = _maya_root(self.d, "Maya2027")
        out  = os.path.join(self.d, "multi", "2027")
        with _fake_compiler():
            report = self._assemble(2, out, maya=maya)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["bundle"], os.path.join(out, "plug.mll"))
        self.assertEqual(sorted(os.listdir(out)), ["build", "plug.mll"])

    def test_a_devkit_with_no_version_is_refused_before_anything_compiles(self):
        maya = _maya_root(self.d, "mayaDev")
        for n in (1, 2):
            with self.subTest(nodes=n):
                out = os.path.join(self.d, "unknown_%d" % n)
                with _fake_compiler() as runs:
                    report = self._assemble(n, out, maya=maya)
                self.assertFalse(report["ok"])
                self.assertIn("cannot tell which Maya version", report["reason"])
                self.assertEqual(runs, [])
                self.assertEqual(os.listdir(out), ["build"])

    def test_the_version_comes_from_the_devkit_when_the_folder_has_none(self):
        maya = _maya_root(self.d, "mayaDev", "20260100")
        out  = os.path.join(self.d, "custom")
        with _fake_compiler():
            report = self._assemble(1, out, maya=maya)
        self.assertEqual(report["bundle"], os.path.join(out, "2026", "plug.mll"))

    def test_an_older_plugin_one_folder_up_is_noted_once_and_kept(self):
        out = os.path.join(self.d, "noted")
        os.makedirs(out)
        old = os.path.join(out, "plug.mll")
        with open(old, "wb") as fh:
            fh.write(b"OLD")
        for n in (1, 2):
            with self.subTest(nodes=n):
                lines = []
                with _fake_compiler():
                    report = self._assemble(n, out, log_cb=lines.append)
                self.assertTrue(report["ok"], report)
                notes = [ln for ln in lines if "older plug.mll" in ln]
                self.assertEqual(len(notes), 1, lines)
                self.assertEqual(report["older_plugin_note"], notes[0])
                with open(old, "rb") as fh:
                    self.assertEqual(fh.read(), b"OLD")
                self.assertTrue(os.path.isfile(os.path.join(out, "2025", "plug.mll")))

    def test_without_a_log_the_note_goes_to_stderr(self):
        out = os.path.join(self.d, "stderr")
        os.makedirs(out)
        open(os.path.join(out, "plug.mll"), "wb").close()
        err = io.StringIO()
        with _fake_compiler(), mock.patch.object(sys, "stderr", err):
            self._assemble(1, out)
        self.assertEqual(err.getvalue().count("older plug.mll"), 1, err.getvalue())

    def test_no_note_without_an_older_plugin(self):
        lines = []
        with _fake_compiler():
            report = self._assemble(1, os.path.join(self.d, "clean"), log_cb=lines.append)
        self.assertNotIn("older_plugin_note", report)
        self.assertEqual(lines, [])


class TestTheControllerWritesTheYearFolder(unittest.TestCase):

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="year_ctl_")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.m25 = _maya_root(self.d, "Maya2025")
        self.m27 = _maya_root(self.d, "Maya2027")
        self.a   = _write(self.d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        self.b   = _write(self.d, "in/bNode.cpp", _src("bNode", "BNode", "0x00081001"))

    def test_a_single_version_compile_reports_the_year_folder(self):
        from mpynode.native.toolchain import compile_controller as cc

        out = os.path.join(self.d, "single")
        with _fake_compiler(), \
             mock.patch.object(toolchain, "check_toolchain", return_value={"ok": True}):
            res = cc.compile_plugin([], "duo", out, verify=False, maya=self.m25,
                                    ai_assist=False, prebuilt=[self.a, self.b])
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["bundle_path"], os.path.join(out, "2025", "duo.mll"))
        self.assertTrue(os.path.isfile(os.path.join(out, "build", "manifest.json")))
        self.assertEqual(toolchain.out_dir_for_plugin(res["bundle_path"]), out)

    def test_compile_plugin_multi_names_each_folder_by_year(self):
        from mpynode.native.toolchain import compile_controller as cc

        calls = []

        def fake_compile(specs, name, out_dir, **kw):
            calls.append(out_dir)
            return {"ok": True, "bundle_path": None, "manifest_path": None,
                    "plugin_name": name, "nodes": [], "errors": [], "strict": True}

        targets = [{"label": "Maya2025", "version": "2025", "root": self.m25},
                   {"label": "Maya2027", "version": "2027", "root": self.m27}]
        out = os.path.join(self.d, "multi")
        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            res = cc.compile_plugin_multi([{"variables": {}}], "duo", out, targets)
        self.assertTrue(res["ok"], res)
        self.assertEqual(calls, [os.path.join(out, "2025"), os.path.join(out, "2027")])

    def test_bundle_prebuilt_one_target(self):
        from mpynode.native.toolchain import compile_controller as cc

        out = os.path.join(self.d, "prebuilt_one")
        with _fake_compiler():
            res = cc.bundle_prebuilt([self.a, self.b], "duo", out, maya=self.m25)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["bundle_path"], os.path.join(out, "2025", "duo.mll"))
        self.assertEqual(sorted(os.listdir(out)), ["2025", "build"])
        self.assertEqual(toolchain.out_dir_for_plugin(res["bundle_path"]), out)

    def test_bundle_prebuilt_two_targets(self):
        from mpynode.native.toolchain import compile_controller as cc

        out = os.path.join(self.d, "prebuilt_two")
        targets = [{"label": "Maya2025", "version": "2025", "root": self.m25},
                   {"label": "Maya2027", "version": "2027", "root": self.m27}]
        with _fake_compiler():
            res = cc.bundle_prebuilt([self.a, self.b], "duo", out, targets=targets)
        self.assertTrue(res["ok"], res)
        self.assertEqual(sorted(os.listdir(out)), ["2025", "2027"])
        for r, year in zip(res["results"], ("2025", "2027")):
            self.assertEqual(r["out_dir"], os.path.join(out, year))
            self.assertEqual(r["result"]["bundle_path"], os.path.join(out, year, "duo.mll"))
            self.assertEqual(sorted(os.listdir(r["out_dir"])), ["build", "duo.mll"])
            self.assertEqual(toolchain.out_dir_for_plugin(r["result"]["bundle_path"]),
                             r["out_dir"])


class TestTheLoadCheckReadsTheManifest(unittest.TestCase):
    """#63 after a real single-version build: the load check must find
    ``<out>/build/manifest.json`` from ``<out>/2025/<plugin>`` and check the
    types it names, not pass with nothing checked."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="year_load_")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.m25 = _maya_root(self.d, "Maya2025")
        self.a   = _write(self.d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081000"))

    def test_bundle_prebuilt_then_validate(self):
        from mpynode._base import plugins
        from mpynode.native.toolchain import compile_controller as cc

        out = os.path.join(self.d, "out")
        with _fake_compiler():
            res = cc.bundle_prebuilt([self.a], "solo", out, maya=self.m25)
        self.assertTrue(res["ok"], res)

        class _Registered:
            def pluginInfo(self, base, query=False, dependNode=False, **kw):
                return []  # loaded, but registered nothing

        with mock.patch.object(plugins, "cmds", _Registered()):
            got = plugins.validate_registered_types(res["bundle_path"])
        self.assertEqual(got["expected"], ["aNode"])
        self.assertFalse(got["ok"])


class TestTheCliWritesTheYearFolder(unittest.TestCase):

    def setUp(self):
        from mpynode.native import bundle

        self.cli = bundle
        self.d   = tempfile.mkdtemp(prefix="year_cli_")
        self.addCleanup(shutil.rmtree, self.d, True)
        self.maya = _maya_root(self.d, "Maya2025")
        self.a    = _write(self.d, "in/aNode.cpp", _src("aNode", "ANode", "0x00081000"))
        self.b    = _write(self.d, "in/bNode.cpp", _src("bNode", "BNode", "0x00081001"))

    def _run(self, *argv):
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with _fake_compiler(), redirect_stdout(buf):
            rc = self.cli.main(list(argv))
        return rc, buf.getvalue()

    def test_out_year_name(self):
        out = os.path.join(self.d, "out")
        rc, txt = self._run("duo", self.a, self.b, "--maya", self.maya, "--out", out,
                            "--no-load-check")
        self.assertEqual(rc, 0, txt)
        plug = os.path.join(out, "2025", "duo.mll")
        self.assertTrue(os.path.isfile(plug))
        self.assertIn("built    : %s" % plug, txt)
        self.assertEqual(sorted(os.listdir(out)), ["2025", "build"])

        # A rebuild with an older duo.mll at the top (where builds used to put
        # it) says so and leaves it alone.
        old = os.path.join(out, "duo.mll")
        with open(old, "wb") as fh:
            fh.write(b"OLD")
        rc, txt = self._run("--refresh", out, "--maya", self.maya, "--no-load-check")
        self.assertEqual(rc, 0, txt)
        self.assertEqual(txt.count("older duo.mll"), 1, txt)
        with open(old, "rb") as fh:
            self.assertEqual(fh.read(), b"OLD")


class TestTheGeneratedScriptsCarryTheYearLogic(unittest.TestCase):

    def _bats(self):
        return (("multi", bundler.make_build_bat("plug", ["a.cpp", "b.cpp"])),
                ("single", bundler.make_single_build_bat("plug", "a.cpp", ["OpenMaya"])))

    def _shs(self):
        return (("multi", bundler.make_build_sh("plug", ["a.cpp", "b.cpp"])),
                ("single", bundler.make_single_build_sh("plug", "a.cpp", ["OpenMaya"])))

    def test_build_bat(self):
        for label, body in self._bats():
            with self.subTest(label):
                self.assertIn('if /i "%_MN:~0,4%"=="maya" set "_YEAR=%_MN:~4,4%"', body)
                self.assertIn("MAYA_API_VERSION", body)
                self.assertIn('set "PLUGIN_DIR=%HERE%..\\%_YEAR%"', body)
                self.assertIn('if not exist "%PLUGIN_DIR%" mkdir "%PLUGIN_DIR%"', body)
                self.assertIn('if exist "%PLUGIN_DIR%\\..\\plug.mll" echo build.bat: note:',
                              body)
                self.assertIn('copy /Y "%LINKTMP%\\plug.mll" "%PLUGIN_DIR%\\plug.mll"', body)
                self.assertNotIn("%HERE%..\\plug.mll", body)
                self.assertFalse(_uncollapsed_percent(body))
                # settled before the first compile, so an unknown version fails fast
                self.assertLess(body.index('set "PLUGIN_DIR='), body.index("cl /nologo"))

    def test_build_sh(self):
        for label, body in self._shs():
            with self.subTest(label):
                self.assertIn('YEAR="${_mn:4:4}"', body)
                self.assertIn("MAYA_API_VERSION", body)
                self.assertIn('PLUGIN_DIR="$HERE/../$YEAR"', body)
                self.assertIn('mkdir -p "$PLUGIN_DIR"', body)
                self.assertIn('if [ -e "$PLUGIN_DIR/../plug.bundle" ]; then', body)
                self.assertIn('-o "$PLUGIN_DIR/plug.bundle"', body)
                self.assertNotIn("$HERE/../plug.bundle", body)
                self.assertLess(body.index('PLUGIN_DIR="'), body.index("clang++ "))

    def test_no_script_names_a_versioned_file(self):
        for label, body in self._bats() + self._shs():
            with self.subTest(label):
                for name in re.findall(r"plug[\w.]*\.(?:mll|bundle)", body):
                    self.assertIn(name, ("plug.mll", "plug.bundle"))

    def test_readme_says_where_the_plugin_lands(self):
        text = bundler.make_readme("plug", ["a.cpp"], single=True, bundle_name="plug.mll")
        self.assertIn("../<year>/plug.mll", text)
        self.assertIn("e.g. ../2026/plug.mll", text)


class _ScriptRunner:
    """Run the generated year block against fake installs, for real."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="year_script_")
        self.addCleanup(shutil.rmtree, self.d, True)

    def _cases(self):
        named  = _maya_root(self.d, "Maya2025")
        custom = _maya_root(self.d, "dev (x86)", "20260100")
        blank  = _maya_root(self.d, "mayaDev")
        return (
            ("named", named, ("t1", "build"), ("t1", "2025")),
            ("devkit", custom, ("t2", "build"), ("t2", "2026")),
            ("in-year", named, ("t3", "2025", "build"), ("t3", "2025")),
            ("unknown", blank, ("t4", "build"), None),
        )

    def test_the_block(self):
        for label, maya, here, want in self._cases():
            with self.subTest(label):
                here = os.path.join(self.d, *here)
                os.makedirs(here, exist_ok=True)
                rc, got, err = self._run(maya, here)
                if want is None:
                    self.assertEqual(rc, 1, err)
                    self.assertIn("cannot tell which Maya version", err)
                    continue
                self.assertEqual(rc, 0, err)
                self.assertEqual(os.path.normcase(os.path.realpath(got)),
                                 os.path.normcase(os.path.realpath(
                                     os.path.join(self.d, *want))))
                self.assertTrue(os.path.isdir(got))
                self.assertNotIn("note:", err)

    def test_the_note(self):
        maya = _maya_root(self.d, "Maya2025")
        here = os.path.join(self.d, "noted", "build")
        os.makedirs(here)
        old = os.path.join(self.d, "noted", "plug" + self.EXT)
        with open(old, "wb") as fh:
            fh.write(b"OLD")
        rc, _got, err = self._run(maya, here)
        self.assertEqual(rc, 0, err)
        self.assertEqual(err.count("note: an older plug%s" % self.EXT), 1, err)
        with open(old, "rb") as fh:
            self.assertEqual(fh.read(), b"OLD")


@unittest.skipUnless(sys.platform.startswith("win"), "cmd.exe only")
class TestTheBatchBlockRuns(_ScriptRunner, unittest.TestCase):
    EXT = ".mll"

    def _run(self, maya, here):
        bat = os.path.join(self.d, "probe.bat")
        lines = (["@echo off", "setlocal", 'set "MAYA=%s"' % maya,
                  'set "HERE=%s"' % (here + os.sep)]
                 + toolchain.plugin_dir_bat("plug.mll")
                 + ["echo PLUGIN_DIR=%PLUGIN_DIR%", "exit /b 0"])
        with open(bat, "w", newline="") as fh:
            fh.write("\r\n".join(lines) + "\r\n")
        p = subprocess.run(["cmd", "/c", bat], capture_output=True, text=True)
        got = [ln[len("PLUGIN_DIR="):] for ln in p.stdout.splitlines()
               if ln.startswith("PLUGIN_DIR=")]
        return p.returncode, (got[0] if got else None), p.stderr


def _bash():
    if sys.platform.startswith("win"):
        for cand in (r"C:\Program Files\Git\bin\bash.exe",
                     r"C:\Program Files (x86)\Git\bin\bash.exe"):
            if os.path.isfile(cand):
                return cand
        return None
    return shutil.which("bash")


def _posix(path):
    """A path Git Bash on Windows understands (``/c/...``); unchanged elsewhere."""
    if not sys.platform.startswith("win"):
        return path
    p = path.replace("\\", "/")
    return "/" + p[0].lower() + p[2:] if p[1:2] == ":" else p


def _native(path):
    if not sys.platform.startswith("win") or not path.startswith("/"):
        return path
    return path[1].upper() + ":" + path[2:]


@unittest.skipUnless(_bash(), "no bash (Git Bash on Windows)")
class TestTheBashBlockRuns(_ScriptRunner, unittest.TestCase):
    EXT = ".bundle"

    def _run(self, maya, here):
        sh = os.path.join(self.d, "probe.sh")
        lines = (["set -euo pipefail", 'MAYA="%s"' % _posix(maya),
                  'HERE="%s"' % _posix(here)]
                 + toolchain.plugin_dir_sh("plug.bundle")
                 + ['echo "PLUGIN_DIR=$PLUGIN_DIR"'])
        with open(sh, "w", newline="") as fh:
            fh.write("\n".join(lines) + "\n")
        p = subprocess.run([_bash(), _posix(sh)], capture_output=True, text=True)
        got = [ln[len("PLUGIN_DIR="):] for ln in p.stdout.splitlines()
               if ln.startswith("PLUGIN_DIR=")]
        return p.returncode, (_native(got[0]) if got else None), p.stderr


if __name__ == "__main__":
    unittest.main()
