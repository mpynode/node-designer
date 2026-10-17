"""Compile OUTPUT-FOLDER layout: a clean, self-explanatory folder.

The importable ``<plugin>.bundle`` sits in a folder named after its Maya version
(``<out>/2025/``); ALL source, build scripts, README and the manifest live under
``build/`` -- with the C++ source (``<node>.cpp`` / ``plugin_main.cpp`` /
``shared_helpers.cpp``) nested one level deeper in ``build/source/``. The build
scripts therefore read their inputs from ``$HERE/source/`` and write the rebuilt
bundle back up to ``$PLUGIN_DIR`` (``$HERE/../<year>``), so a hand rebuild
lands the bundle exactly where the programmatic build did.

These assert the bundler's file placement with ``compile_now=False`` (no compiler
needed): the source/scripts are written regardless of whether the link runs.
"""
from __future__ import annotations

import tests  # noqa: F401 -- first: keeps the run out of ~/.mpynode

import os
import shutil
import tempfile
import unittest

from mpynode.native.compiler import bundler
from mpynode.native.toolchain import toolchain
from mpynode.native.toolchain import typeid_registry

# Reuse the minimal, valid single-node .cpp fixture (registerNode +
# initializePlugin/uninitializePlugin + MTypeId) the dedup suite already ships.
from tests.compile.transpiler.test_native_helper_dedup import _node_src


def _reg(d):
    return typeid_registry.TypeIdRegistry(path=os.path.join(d, "reg.json"))


def _broken_node_src(node_name, cls, tid):
    """A node that TRANSFORMS fine (has registerNode + init/uninit) but does NOT
    compile (garbage in the compute body) -- to exercise the best-effort drop."""
    return (
        "#include <maya/MPxNode.h>\n"
        "#include <maya/MFnPlugin.h>\n"
        "class %s : public MPxNode {\n"
        "public:\n"
        "    static void* creator() { return new %s(); }\n"
        "    static MStatus initialize() { return MS::kSuccess; }\n"
        "    MStatus compute(const MPlug& plug, MDataBlock& data) override {\n"
        "        this is definitely not valid c++ @@@ ;\n"
        "        return MS::kSuccess;\n"
        "    }\n"
        "    static MTypeId id;\n"
        "};\n"
        "MTypeId %s::id(%s);\n"
        "MStatus initializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj, \"x\", \"1.0\", \"Any\");\n"
        "    return plugin.registerNode(\"%s\", %s::id, %s::creator, "
        "%s::initialize);\n"
        "}\n"
        "MStatus uninitializePlugin(MObject obj) {\n"
        "    MFnPlugin plugin(obj);\n"
        "    return plugin.deregisterNode(%s::id);\n"
        "}\n"
        % (cls, cls, cls, tid, node_name, cls, cls, cls, cls))


class TestCompileOutputLayout(unittest.TestCase):
    def _write_node(self, d, node, cls, tid):
        p = os.path.join(d, node + ".cpp")
        with open(p, "w") as fh:
            fh.write(_node_src(node, cls, tid, with_block=False))
        return p

    def _assemble(self, nodes, plugin, d):
        out = os.path.join(d, "out")
        report = bundler.assemble(nodes, plugin, out, strict=True,
                                  registry=_reg(d), compile_now=False)
        self.assertTrue(report.get("ok"), report)
        return out

    # ---- single-node -----------------------------------------------------
    def test_single_node_clean_top_level(self):
        d   = tempfile.mkdtemp(prefix="layout_single_")
        p   = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        out = self._assemble([("fooNode", p)], "solo", d)

        # Source is nested in build/source; scripts + README sit in build/.
        self.assertTrue(os.path.isfile(
            os.path.join(out, "build", "source", "fooNode.cpp")))
        for f in ("build.sh", "build.bat", "README.txt"):
            self.assertTrue(os.path.isfile(os.path.join(out, "build", f)), f)

        # Nothing spills to the top level (no bundle: compile_now=False).
        self.assertFalse(os.path.exists(os.path.join(out, "fooNode.cpp")))
        self.assertFalse(os.path.exists(os.path.join(out, "build.sh")))
        self.assertEqual(set(os.listdir(out)), {"build"})

    def test_single_build_sh_paths(self):
        d   = tempfile.mkdtemp(prefix="layout_ssh_")
        p   = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        out = self._assemble([("fooNode", p)], "solo", d)
        with open(os.path.join(out, "build", "build.sh")) as fh:
            sh = fh.read()
        self.assertIn("$HERE/source/fooNode.cpp",     sh)  # input from source/
        self.assertIn('-o "$PLUGIN_DIR/solo.bundle"', sh)  # bundle to the version folder
        self.assertIn('PLUGIN_DIR="$HERE/../$YEAR"',  sh)

    # ---- multi-node ------------------------------------------------------
    def test_multi_node_clean_top_level(self):
        d   = tempfile.mkdtemp(prefix="layout_multi_")
        p1  = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        p2  = self._write_node(d, "barNode", "BarNode", "0x00081001")
        out = self._assemble([("fooNode", p1), ("barNode", p2)], "duo", d)

        src = os.path.join(out, "build", "source")
        for f in ("fooNode.cpp", "barNode.cpp", "plugin_main.cpp"):
            self.assertTrue(os.path.isfile(os.path.join(src, f)), f)
        for f in ("build.sh", "build.bat", "README.txt"):
            self.assertTrue(os.path.isfile(os.path.join(out, "build", f)), f)
        self.assertEqual(set(os.listdir(out)), {"build"})

    def test_multi_build_sh_paths(self):
        d   = tempfile.mkdtemp(prefix="layout_msh_")
        p1  = self._write_node(d, "fooNode", "FooNode", "0x00081000")
        p2  = self._write_node(d, "barNode", "BarNode", "0x00081001")
        out = self._assemble([("fooNode", p1), ("barNode", p2)], "duo", d)
        with open(os.path.join(out, "build", "build.sh")) as fh:
            sh = fh.read()
        self.assertIn("$HERE/source/", sh)                # inputs from source/
        self.assertIn('-o "$PLUGIN_DIR/duo.bundle"', sh)  # bundle to the version folder
        self.assertIn('PLUGIN_DIR="$HERE/../$YEAR"', sh)

    # ---- a DROPPED node must not orphan its fragment in source/ ----------
    def test_dropped_node_fragment_not_left_in_source(self):
        # Real-compiler integration: a best-effort multi-node build where one
        # node won't compile. The dropped node's fragment must NOT linger in
        # source/ -- source/ is exactly the bundle's source.
        d    = tempfile.mkdtemp(prefix="layout_drop_")
        good = self._write_node(d, "goodNode", "GoodNode", "0x00081000")
        bad  = os.path.join(d, "badNode.cpp")
        with open(bad, "w") as fh:
            fh.write(_broken_node_src("badNode", "BadNode", "0x00081001"))
        out = os.path.join(d, "out")
        report = bundler.assemble(
            [("goodNode", good), ("badNode", bad)], "duo", out,
            strict=False, registry=_reg(d), compile_now=True)
        # Skip when this host has no C++ toolchain: then even the good node never
        # reaches the compile step (badNode wouldn't be in 'dropped').
        if not report.get("ok") and "badNode" not in (report.get("dropped") or []):
            self.skipTest("no compiler on this host: %s" % report.get("reason"))
        self.assertIn("badNode", report.get("dropped") or [])
        src = bundler.source_dir_for(out)
        self.assertTrue(os.path.isfile(os.path.join(src, "goodNode.cpp")))
        self.assertFalse(os.path.exists(os.path.join(src, "badNode.cpp")),
                         "dropped node's fragment must be removed from source/")
        # The good node still linked into the bundle, in its version folder.
        self.assertTrue(report.get("ok"))
        # Platform extension, not a hardcoded ".bundle": the artifact is
        # duo.mll on Windows and duo.so on Linux, so this asserted a file that
        # could never exist there (measured 2026-08-14).
        year = toolchain.maya_year(bundler._MAYA_DEFAULT)
        self.assertTrue(os.path.isfile(
            os.path.join(out, year, "duo" + toolchain.plugin_ext())))

    # ---- layout helpers are the single source of truth -------------------
    def test_layout_helpers(self):
        self.assertEqual(bundler.build_dir_for("/x/out"),
                         os.path.join("/x/out", "build"))
        self.assertEqual(bundler.source_dir_for("/x/out"),
                         os.path.join("/x/out", "build", "source"))


class TestWindowsBuildScriptFpFlags(unittest.TestCase):
    """Item 1: the generated Windows rebuild scripts must carry the SAME parity
    flags as the in-process compile (_MSVC_CXXFLAGS): /O2 AND an explicit
    /fp:precise, never /fp:fast. A user who hand-runs build.bat must reproduce a
    binary numerically identical to the shipped one; a script missing /O2 (slower)
    or /fp:precise (implicit-default drift) would silently diverge."""

    def test_combined_build_bat_has_o2_and_fp_precise(self):
        bat = bundler.make_build_bat("duo", ["fooNode.cpp", "barNode.cpp"])
        self.assertIn("/O2", bat)
        self.assertIn("/fp:precise", bat)
        self.assertNotIn("/fp:fast", bat)

    def test_single_build_bat_has_o2_and_fp_precise(self):
        bat = bundler.make_single_build_bat("solo", "fooNode.cpp", ["OpenMaya"])
        self.assertIn("/O2", bat)
        self.assertIn("/fp:precise", bat)
        self.assertNotIn("/fp:fast", bat)


class TestBuildScriptsMatchTheirRegenerator(unittest.TestCase):
    """A compile writes its build scripts in the committed form that
    tools/regen_build_scripts.py regenerates -- on a Windows host too, which is
    where the per-node build.bat used to come out as \\r\\r\\n and both .bat files
    carried a "REM Built against" line no committed build.bat has. Either one
    failed test_build_script_freshness after every Windows compile."""

    _MAYA = "C:/Program Files/Autodesk/Maya2025"

    def _with_host(self, windows):
        real                 = toolchain.is_windows
        toolchain.is_windows = lambda os_name=None: windows
        self.addCleanup(setattr, toolchain, "is_windows", real)

    def _read(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def test_tree_build_bat_never_records_provenance(self):
        for windows in (True, False):
            with self.subTest(windows_host=windows):
                self._with_host(windows)
                d = tempfile.mkdtemp(prefix="layout_prov_")
                self.addCleanup(shutil.rmtree, d, True)
                p = os.path.join(d, "fooNode.cpp")
                with open(p, "w") as fh:
                    fh.write(_node_src("fooNode", "FooNode", "0x00081000", with_block=False))
                report = bundler.assemble([("fooNode", p)], "solo", os.path.join(d, "out"),
                                          strict=True, registry=_reg(d), maya=self._MAYA,
                                          compile_now=False)
                self.assertTrue(report.get("ok"), report)
                bat = self._read(os.path.join(d, "out", "build", "build.bat"))
                sh  = self._read(os.path.join(d, "out", "build", "build.sh"))
                self.assertNotIn(b"Built against", bat)
                self.assertNotIn(b"\r\r\n", bat)
                self.assertEqual(b"Built against: Maya2025" in sh, not windows)

    def test_node_build_script_is_the_generator_output_verbatim(self):
        from mpynode.native.ai import porter
        from mpynode.native.compiler import build_scripts

        spec = {"suggested": {"node_type_name": "fooNode", "mpx_base": "MPxNode"}}
        for windows, name in ((True, "build.bat"), (False, "build.sh")):
            with self.subTest(windows_host=windows):
                self._with_host(windows)
                d = tempfile.mkdtemp(prefix="layout_node_")
                self.addCleanup(shutil.rmtree, d, True)
                path = porter._write_build_script(spec, d)
                self.assertEqual(os.path.basename(path), name)
                want = build_scripts.generate_build_script(spec)[1].encode("utf-8")
                self.assertEqual(self._read(path), want)
                self.assertNotIn(b"Built against", want)


class TestVerifyScriptIsWrittenLF(unittest.TestCase):
    """port_node writes verify_in_maya.py as tools/regen_verify_scripts.py
    writes a shipped one: the generator's text byte for byte, so LF. A
    text-mode write made it CRLF on Windows, so every Windows build left a
    script that differed on every line from the one the repository ships.

    Both write sites run, the deterministic branch (no PORT region) and the
    AI branch, with a stub compile_cpp and the rest real. On Windows the real
    text layer writes the file. On any other host a text-mode write is made
    to translate line endings as it does on Windows, so a text-mode write of
    the script fails this test there too."""

    # A shipped spec that lowers with no PORT region.
    _DETERMINISTIC = ("templates", "MPyNode", "De Boor Spline", "build",
                      "manifest.json")

    @staticmethod
    def _windows_text_mode():
        """Off Windows, text-mode writes turn "\\n" into "\\r\\n"."""
        import builtins
        import contextlib
        from unittest import mock

        if os.name == "nt":
            return contextlib.nullcontext()
        real = builtins.open

        def _open(file, mode="r", buffering=-1, encoding=None, errors=None,
                  newline=None, *args, **kwargs):
            if "b" not in mode and newline is None and set(mode) & set("wax+"):
                newline = "\r\n"
            return real(file, mode, buffering, encoding, errors, newline,
                        *args, **kwargs)

        return mock.patch.object(builtins, "open", _open)

    def _port(self, spec, complete_fn):
        """Run port_node on ``spec``; return the verify script's bytes."""
        from unittest import mock

        from mpynode.native.ai import porter

        def fake_compile(cpp_path, spec, out_dir, **kwargs):
            plugin = os.path.join(out_dir, "x" + toolchain.plugin_ext())
            return True, "", plugin

        d = tempfile.mkdtemp(prefix="layout_verify_")
        self.addCleanup(shutil.rmtree, d, True)
        with mock.patch.object(porter, "compile_cpp", fake_compile), \
                self._windows_text_mode():
            res = porter.port_node(spec, d, complete_fn=complete_fn)
        self.assertTrue(res["ok"], res)
        path = os.path.join(d, "verify_in_maya.py")
        self.assertEqual(res["verify_script"], path)
        with open(path, "rb") as fh:
            return fh.read()

    def _assert_generator_text(self, spec, data):
        from mpynode.native.ai import verify_scripts

        self.assertEqual(data.count(b"\r"), 0, "verify_in_maya.py has CRs")
        want = verify_scripts._verify_script(spec).encode("utf-8")
        self.assertEqual(data.splitlines(True), want.splitlines(True))

    def test_deterministic_branch_writes_lf(self):
        import copy
        import json

        from mpynode.native import compiler as codegen
        from tests import _paths

        path = os.path.join(_paths.ROOT, *self._DETERMINISTIC)
        with open(path, encoding="utf-8") as fh:
            spec = json.load(fh)["nodes"][0]["spec"]
        skeleton = codegen.generate_cpp(copy.deepcopy(spec), for_port=True)
        self.assertFalse(codegen.PORT_BEGIN in skeleton,
                         "this spec now has a PORT region: pick another")
        asked = []
        data  = self._port(spec, lambda system, user: asked.append(user))
        self.assertEqual(asked, [])
        self._assert_generator_text(spec, data)

    def test_ai_branch_writes_lf(self):
        from tests.compile.pipeline.test_native_compile_pipeline import (
            _portable_spec)

        asked = []

        def complete_fn(system, user):
            asked.append(user)
            return "out = a * 2.0;"

        spec = _portable_spec()
        data = self._port(spec, complete_fn)
        self.assertEqual(len(asked), 1)
        self._assert_generator_text(spec, data)


class TestACompileWritesLF(unittest.TestCase):
    """Every text file a compile writes is LF, as the repository stores it;
    build.bat alone is CRLF, on purpose. On Windows the pipeline wrote the
    final and source .cpp, the stage files, both REPORT.md, manifest.json,
    compile.log, the optimizer's rounds and the port cache in text mode, so
    each came out CRLF and differed on every line from the LF copy the
    repository ships.

    A Windows compile on any host: Windows is the host OS (build.bat, cl),
    the porter's compile_cpp is a stub, the bundler's compiles and link are
    faked, and the optimizer's engine accepts one round. compile_plugin
    builds three nodes, one lowered whole, one with an AI body and an
    mPyFile with its viewport override, then each again on its own from the
    port cache. A two-node assemble adds a shared helper unit. On Windows
    the real text layer writes the files; elsewhere a text-mode write is
    made to translate as on Windows, as in TestVerifyScriptIsWrittenLF."""

    # A failure names every file with a wrong line ending.
    maxDiff = None

    _FILE_SIMPLE = ("templates", "MPyFile", "File Simple", "build",
                    "manifest.json")

    @staticmethod
    def _spec(name, compute, type_id):
        return {
            "source_node": name,
            "mpy_type":    "mPyNode",
            "suggested": {"node_type_name": name,
                          "class_name": name[:1].upper() + name[1:],
                          "mpx_base": "MPxNode", "type_id": type_id},
            "inputs":      {"a": {"type": "double"}},
            "outputs":     {"out": {"type": "double"}},
            "compute":     compute,
            "init":        "",
            "portability": {"portable": True, "blockers": []},
        }

    def _specs(self):
        """A node lowered whole, one the AI ports, and File Simple's
        mPyFile (lowered whole, then given its viewport override)."""
        import json

        from tests import _paths

        with open(os.path.join(_paths.ROOT, *self._FILE_SIMPLE),
                  encoding="utf-8") as fh:
            texture = json.load(fh)["nodes"][0]["spec"]
        return [self._spec("lfWhole", "self.out = self.a * 2.0", "0x0013a1d0"),
                self._spec("lfPorted", "out = a * 2.0", "0x0013a1d1"),
                texture]

    @staticmethod
    def _windows():
        """The patches for a Windows compile on any host, as one context."""
        import contextlib
        from unittest import mock

        from mpynode.native.ai import optimizer, optimizer_live, porter
        from mpynode.native.ai.optimizer import OptimizeResult, RoundRecord
        from tests.compile.pipeline.test_native_toolchain import _touch_outputs

        real_os = toolchain.current_os

        def fake_compile(cpp_path, spec, out_dir, **kwargs):
            if kwargs.get("log_cb") is not None:
                kwargs["log_cb"]("cl /c %s" % os.path.basename(cpp_path))
            return True, "", os.path.join(out_dir, "x" + toolchain.plugin_ext())

        def fake_run(cmd, **kwargs):
            _touch_outputs(cmd)
            return 0, ""

        def engine(baseline, round_cb=None, **kwargs):
            best = baseline + "// round 1\n"
            ledger = [RoundRecord(0, "baseline", compiled=True, ms=2.0),
                      RoundRecord(1, "accept", compiled=True, parity="pass",
                                  ms=1.0, speedup=2.0, slug="hoist"),
                      RoundRecord(2, "no-change", compiled=True, slug="noop")]
            for rec, text in zip(ledger, (baseline, best, best)):
                round_cb(rec, text)
            return OptimizeResult(True, best, 2.0, 1.0, 2.0, 2, ledger,
                                  "accepted (2.00x)")

        provider = {"ok": True, "problems": [], "provider": "anthropic",
                    "kind": "api"}
        patches = [
            (toolchain, "current_os",
             lambda name=None: real_os(name) if name else "win32"),
            (toolchain, "check_toolchain",
             lambda *a, **k: {"ok": True, "problems": [], "compiler": "cl"}),
            (toolchain, "default_compiler", lambda *a: "cl"),
            (toolchain, "build_env", lambda *a, **k: {"PATH": "x"}),
            (toolchain, "resolve_compiler", lambda c, *a, **k: c),
            (toolchain, "diagnose_toolset_mismatch", lambda *a, **k: None),
            (toolchain, "run_streaming", fake_run),
            (porter, "compile_cpp", fake_compile),
            (porter, "check_provider", lambda *a, **k: dict(provider)),
            (optimizer_live, "benchmark_harness_problem", lambda: None),
            (optimizer_live, "make_adapters", lambda *a, **k: {}),
            (optimizer, "optimize_cpp", engine),
        ]
        stack = contextlib.ExitStack()
        for target, name, value in patches:
            stack.enter_context(mock.patch.object(target, name, value))
        stack.enter_context(TestVerifyScriptIsWrittenLF._windows_text_mode())
        return stack

    @staticmethod
    def _scan(roots):
        """Every text file under ``roots`` (``{label: folder}``), and the
        ones whose line endings are wrong: a CR anywhere but build.bat, and
        anything but CRLF in build.bat."""
        seen, bad = set(), {}
        for label, root in roots.items():
            for folder, _dirs, files in os.walk(root):
                for name in files:
                    path = os.path.join(folder, name)
                    with open(path, "rb") as fh:
                        data = fh.read()
                    try:
                        data.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    if b"\0" in data:
                        continue
                    rel = "%s/%s" % (label, os.path.relpath(path, root)
                                     .replace(os.sep, "/"))
                    seen.add(rel)
                    if name != "build.bat":
                        if b"\r" in data:
                            bad[rel] = "%d CR" % data.count(b"\r")
                    elif (not data or b"\r\r" in data
                          or data.count(b"\r\n") != data.count(b"\n")):
                        bad[rel] = "not CRLF"
        return seen, bad

    def test_a_windows_compile_writes_every_text_file_lf(self):
        import copy
        from unittest import mock

        from mpynode.native.toolchain import compile_controller as cc

        d = tempfile.mkdtemp(prefix="layout_lf_")
        self.addCleanup(shutil.rmtree, d, True)
        cache = os.path.join(d, "port_cache")
        roots = {"cache": cache}
        specs = self._specs()

        def compile_(label, nodes):
            out = roots[label] = os.path.join(d, label)
            res = cc.compile_plugin(
                copy.deepcopy(nodes), "lfPlugin", out, strict=True,
                verify=False, verify_fn=lambda *a, **k: {},
                provider="anthropic", model="m", optimize=True,
                clean_scratch=False,
                complete_fn=lambda system, user: "out = a * 2.0;")
            self.assertTrue(res["ok"], res.get("errors"))
            self.assertEqual({r["build_status"] for r in res["nodes"]},
                             {"compiled"})

        with mock.patch.dict(os.environ, {"MPYNODE_PORT_CACHE": cache}), \
                self._windows():
            compile_("all", specs)
            for spec in specs:
                compile_(spec["suggested"]["node_type_name"], [spec])
        seen, bad = self._scan(roots)

        # Each kind of file a compile writes is there to be checked.
        want = {"all/build/" + f for f in (
            "build.bat", "build.sh", "README.txt", "manifest.json",
            "source/plugin_main.cpp", "stages/lfPorted/2_assisted.cpp")}
        want |= {"all/REPORT.md"}
        for t in ("lfWhole", "lfPorted", "fileTexture"):
            want |= {"all/build/" + f % {"t": t} for f in (
                "%(t)s/%(t)s.cpp", "%(t)s/build.bat", "%(t)s/compile.log",
                "%(t)s/verify_in_maya.py", "source/%(t)s.cpp",
                "stages/%(t)s/1_transpiled.cpp", "stages/%(t)s/REPORT.md")}
            want |= {"%s/build/source/%s.cpp" % (t, t),
                     "%s/build/stages/%s/1_transpiled.cpp" % (t, t)}
        for t in ("lfWhole", "lfPorted"):
            want |= {"all/build/stages/%s/%s" % (t, f) for f in (
                "3_optimized/00_baseline.cpp", "3_optimized/01_hoist.cpp",
                "3_optimized/02_no_change.txt", "rounds.json")}
        want |= {"lfPorted/build/stages/lfPorted/2_assisted.cpp"}
        self.assertEqual(sorted(want - seen), [])
        self.assertEqual(len([r for r in seen if r.startswith("cache/")]), 6)
        self.assertEqual(bad, {})

    def test_a_shared_helper_unit_is_written_lf(self):
        d = tempfile.mkdtemp(prefix="layout_lf_shared_")
        self.addCleanup(shutil.rmtree, d, True)
        nodes = []
        for i in range(2):
            p = os.path.join(d, "n%dNode.cpp" % i)
            with open(p, "w", newline="", encoding="utf-8") as fh:
                fh.write(_node_src("n%dNode" % i, "N%dNode" % i,
                                   "0x0008100%d" % i, with_block=True))
            nodes.append(("n%dNode" % i, p))
        out = os.path.join(d, "out")
        with self._windows():
            report = bundler.assemble(nodes, "plug", out, strict=True,
                                      registry=_reg(d))
        self.assertTrue(report.get("ok"), report)
        seen, bad = self._scan({"out": out})
        self.assertIn("out/build/source/" + bundler.SHARED_HELPERS_FILE, seen)
        self.assertEqual(bad, {})


class TestCleanWorkingSubdirs(unittest.TestCase):
    """The controller's post-build scratch sweep: drop a built node's
    build/<type>/, keep a dropped node's for debugging, and MIGRATE away any
    pre-reorg top-level out_dir/<type>/ for every node -- never the bundle."""

    def test_sweep_migrates_toplevel_keeps_dropped_buildsubdir(self):
        from mpynode.native.toolchain import compile_controller as cc

        d = tempfile.mkdtemp(prefix="cleanws_")
        # pre-reorg top-level scratch for a built + a dropped node (migration)
        for tn in ("fooBuilt", "barDropped"):
            os.makedirs(os.path.join(d, tn))
        # new-layout scratch under build/ for both
        os.makedirs(os.path.join(d, "build", "fooBuilt"))
        os.makedirs(os.path.join(d, "build", "barDropped"))
        # the importable artifacts must survive
        open(os.path.join(d, "P.bundle"), "w").close()
        open(os.path.join(d, "foo_commands.py"), "w").close()

        rows = [{"type_name": "fooBuilt", "build_status": "compiled"},
                {"type_name": "barDropped", "build_status": "dropped"}]
        cc._clean_working_subdirs(d, rows)

        # top-level scratch swept for BOTH (migration).
        self.assertFalse(os.path.exists(os.path.join(d, "fooBuilt")))
        self.assertFalse(os.path.exists(os.path.join(d, "barDropped")))
        # build/<type>: built removed, dropped kept.
        self.assertFalse(os.path.exists(os.path.join(d, "build", "fooBuilt")))
        self.assertTrue(os.path.exists(os.path.join(d, "build", "barDropped")))
        # bundle + companion untouched.
        self.assertTrue(os.path.exists(os.path.join(d, "P.bundle")))
        self.assertTrue(os.path.exists(os.path.join(d, "foo_commands.py")))


class TestBuildsInATempFolder(unittest.TestCase):
    """Every compile and link runs in-process in ONE local temp folder, on
    Windows AND macOS, and only the finished plug-in reaches out_dir. The
    build.sh / build.bat beside the sources are for a user compiling by hand:
    the pipeline never runs them (macOS used to run build.sh)."""

    _PLATFORMS = (("win32", "cl"), ("darwin", "clang++"))

    def _assemble(self, os_name, compiler, n_nodes, with_block=False):
        from unittest import mock

        from tests.compile.pipeline.test_native_toolchain import _touch_outputs

        real_current_os = toolchain.current_os
        runs            = []

        def fake_run(cmd, *, env=None, log_cb=None, cwd=None, timeout=None, **k):
            runs.append({"cmd": list(cmd), "cwd": cwd, "timeout": timeout})
            _touch_outputs(cmd)
            return 0, ""

        d = tempfile.mkdtemp(prefix="tmpbuild_")
        self.addCleanup(shutil.rmtree, d, True)
        nodes = []
        for i in range(n_nodes):
            p = os.path.join(d, "n%dNode.cpp" % i)
            with open(p, "w") as fh:
                fh.write(_node_src("n%dNode" % i, "N%dNode" % i,
                                   "0x0008100%d" % i, with_block=with_block))
            nodes.append(("n%dNode" % i, p))
        out = os.path.join(d, "out")
        with mock.patch.object(
                toolchain, "current_os",
                lambda name=None: real_current_os(name) if name else os_name), \
             mock.patch.object(toolchain, "default_compiler", lambda *a: compiler), \
             mock.patch.object(toolchain, "build_env", lambda *a, **k: {"PATH": "x"}), \
             mock.patch.object(toolchain, "resolve_compiler", lambda c, *a, **k: c), \
             mock.patch.object(toolchain, "diagnose_toolset_mismatch",
                               lambda *a, **k: None), \
             mock.patch.object(toolchain, "run_streaming", fake_run):
            report = bundler.assemble(nodes, "plug", out, strict=True,
                                      registry=_reg(d))
            ext = toolchain.plugin_ext()
        return report, runs, out, ext

    def _check(self, report, runs, out, ext):
        self.assertTrue(report.get("ok"), report)
        year = toolchain.maya_year(bundler._MAYA_DEFAULT)
        self.assertEqual(report["bundle"], os.path.join(out, year, "plug" + ext))
        self.assertTrue(os.path.isfile(report["bundle"]))
        self.assertFalse([r for r in runs
                          if os.path.basename(r["cmd"][0]) == "bash"],
                         "the pipeline must not run build.sh")
        tmps = {r["cwd"] for r in runs}
        self.assertEqual(len(tmps), 1, "one temp folder per build")
        tmp = tmps.pop()
        for r in runs:
            self.assertEqual(r["timeout"], toolchain.build_timeout())
            for tok in r["cmd"]:
                if tok.endswith(".cpp"):
                    self.assertTrue(tok.startswith(tmp), tok)
        self.assertFalse(os.path.exists(tmp), "the temp folder must be gone")
        # Sources and scripts only -- no object, import library or export file.
        src = bundler.source_dir_for(out)
        self.assertTrue(all(f.endswith((".cpp", ".h")) for f in os.listdir(src)),
                        os.listdir(src))
        for f in ("build.sh", "build.bat", "README.txt"):
            self.assertTrue(os.path.isfile(os.path.join(out, "build", f)), f)
        self.assertEqual(sorted(os.listdir(out)), sorted(["build", year]))
        self.assertEqual(os.listdir(os.path.join(out, year)), ["plug" + ext])

    def test_single_node(self):
        for os_name, compiler in self._PLATFORMS:
            with self.subTest(os_name):
                report, runs, out, ext = self._assemble(os_name, compiler, 1)
                self._check(report, runs, out, ext)
                self.assertEqual(len(runs), 1, "one compile+link call")

    def test_multi_node(self):
        for os_name, compiler in self._PLATFORMS:
            with self.subTest(os_name):
                report, runs, out, ext = self._assemble(os_name, compiler, 2)
                self._check(report, runs, out, ext)
                # 2 fragments + plugin_main compiled, then ONE link -- the
                # fragment objects are the link inputs, not compiled twice.
                self.assertEqual(len(runs), 4)

    def test_multi_node_with_a_shared_helper_unit(self):
        for os_name, compiler in self._PLATFORMS:
            with self.subTest(os_name):
                report, runs, out, ext = self._assemble(os_name, compiler, 2,
                                                        with_block=True)
                self._check(report, runs, out, ext)
                self.assertTrue(os.path.isfile(os.path.join(
                    bundler.source_dir_for(out), bundler.SHARED_HELPERS_FILE)))
                self.assertEqual(len(runs), 5)


if __name__ == "__main__":
    unittest.main()
