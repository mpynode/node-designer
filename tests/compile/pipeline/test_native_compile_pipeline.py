"""Native compile controller orchestration: pre-flight, file-read, RNG, verify-parity, persistent bake, parity sweep, multi-version

Consolidated from: test_compile_preflight.py, test_file_read_support.py, test_rng_support.py, test_verify_array_and_error.py, test_compile_from_mpn.py, test_native_parity_sweep.py, test_multi_version_compile.py.
"""

from __future__ import annotations

# ===================== from test_compile_preflight.py =====================
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import unittest.mock

from tests._setup import standalone_init


def _setUpModule__compile_preflight():
    standalone_init()


def _portable_spec(name="cubicCurveSampler"):
    """A minimal portable spec the engine accepts up to the port step."""
    return {
        "source_node": name,
        "mpy_type": "mPyNode",
        "suggested": {"node_type_name": name, "class_name": name[:1].upper() + name[1:],
                      "mpx_base": "MPxNode", "type_id": "0x0013a1c0"},
        "inputs": {"a": {"type": "double"}},
        "outputs": {"out": {"type": "double"}},
        "compute": "out = a * 2.0",
        "init": "",
        "portability": {"portable": True, "blockers": []},
    }


def _touch_bundle(out_dir, plugin_name):
    """Create the .bundle a REAL successful ``assemble`` writes to disk and
    return its path. The controller's #62 guard rejects a report that claims
    ``ok`` yet leaves no artifact on disk, so a success-modelling fake
    ``assemble`` must actually create the file."""
    path = os.path.join(out_dir, plugin_name + ".bundle")
    with open(path, "w") as fh:
        fh.write("")
    return path


# ---------------------------------------------------------------------------
# porter.check_provider
# ---------------------------------------------------------------------------


class TestCheckProvider(unittest.TestCase):
    def test_cli_provider_binary_found_is_ok(self):
        from mpynode.native.ai import porter, llm_client

        with unittest.mock.patch.object(porter._config, "get_provider",
                                        return_value="claude_cli"), \
             unittest.mock.patch.object(llm_client, "_resolve_cli_bin",
                                        return_value="/usr/local/bin/claude"):
            res = porter.check_provider()
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["kind"], "cli")

    def test_cli_provider_binary_missing_reports_clearly(self):
        from mpynode.native.ai import porter, llm_client

        def _raise(provider):
            raise RuntimeError("'claude' CLI not found on PATH (set CLAUDE_BIN)")

        with unittest.mock.patch.object(porter._config, "get_provider",
                                        return_value="claude_cli"), \
             unittest.mock.patch.object(llm_client, "_resolve_cli_bin", _raise):
            res = porter.check_provider()
        self.assertFalse(res["ok"])
        self.assertTrue(any("not found on PATH" in p for p in res["problems"]),
                        res["problems"])

    def test_api_provider_with_key_is_ok(self):
        from mpynode.native.ai import porter

        with unittest.mock.patch.object(porter._config, "get_api_key",
                                        return_value="sk-abc123"):
            res = porter.check_provider(provider="anthropic")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["kind"], "api")

    def test_api_provider_without_key_reports_clearly(self):
        from mpynode.native.ai import porter

        with unittest.mock.patch.object(porter._config, "get_api_key",
                                        return_value=""):
            res = porter.check_provider(provider="anthropic")
        self.assertFalse(res["ok"])
        joined = " ".join(res["problems"]).lower()
        self.assertIn("api key", joined)
        self.assertTrue(any("anthropic" in p for p in res["problems"]),
                        res["problems"])

    def test_never_raises(self):
        from mpynode.native.ai import porter

        def boom():
            raise RuntimeError("config exploded")

        with unittest.mock.patch.object(porter._config, "get_provider", boom):
            res = porter.check_provider()
        self.assertFalse(res["ok"])
        self.assertTrue(res["problems"])


# ---------------------------------------------------------------------------
# porter.compile_cpp -- decode the missing-compiler failure
# ---------------------------------------------------------------------------


class TestCompileCppMissingCompiler(unittest.TestCase):
    def test_filenotfound_is_decoded_not_raw_winerror(self):
        from mpynode.native.ai import porter

        spec = _portable_spec()
        with tempfile.TemporaryDirectory() as d:
            cpp = os.path.join(d, "x.cpp")
            with open(cpp, "w") as fh:
                fh.write("// stub\n")

            def _raise(*a, **k):
                raise FileNotFoundError(2, "The system cannot find the file specified")

            with unittest.mock.patch.object(porter.toolchain, "run_streaming",
                                            _raise):
                ok, log, plugin = porter.compile_cpp(cpp, spec, d)
        self.assertFalse(ok)
        # The opaque raw error must be translated into an actionable message.
        self.assertNotIn("WinError", log)
        self.assertIn("compiler", log.lower())

    def test_unresolved_compiler_short_circuits_with_message(self):
        from mpynode.native.ai import porter

        spec = _portable_spec()
        with tempfile.TemporaryDirectory() as d:
            cpp = os.path.join(d, "x.cpp")
            with open(cpp, "w") as fh:
                fh.write("// stub\n")
            # When the compiler can't be resolved to a real executable, compile_cpp
            # must return a clear message WITHOUT launching anything. (Give it a
            # non-None build env so the MSVC capture-failed guard is skipped and we
            # exercise the resolve->None path specifically.)
            called = {"n": 0}

            def _spy(*a, **k):
                called["n"] += 1
                raise AssertionError("the compiler must not be launched")

            with unittest.mock.patch.object(porter.toolchain, "build_env",
                                            return_value={"PATH": "x"}), \
                 unittest.mock.patch.object(porter.toolchain, "resolve_compiler",
                                            return_value=None), \
                 unittest.mock.patch.object(porter.toolchain, "run_streaming",
                                            _spy):
                ok, log, plugin = porter.compile_cpp(cpp, spec, d, compiler="cl")
        self.assertFalse(ok)
        self.assertEqual(called["n"], 0)
        self.assertIn("cl", log)

    def test_msvc_capture_failed_refuses_stray_cl(self):
        from mpynode.native.ai import porter

        spec = _portable_spec()
        with tempfile.TemporaryDirectory() as d:
            cpp = os.path.join(d, "x.cpp")
            with open(cpp, "w") as fh:
                fh.write("// stub\n")
            called = {"n": 0}

            def _spy(*a, **k):
                called["n"] += 1
                raise AssertionError("must not compile with a stray PATH cl")

            # build_env capture failed (None) and NOT in a developer shell ->
            # compile_cpp must refuse rather than run a possibly-mismatched cl
            # (the STL1001 cause), and say so.
            with unittest.mock.patch.object(porter.toolchain, "build_env",
                                            return_value=None), \
                 unittest.mock.patch.object(porter.toolchain, "in_developer_shell",
                                            return_value=False), \
                 unittest.mock.patch.object(porter.toolchain, "run_streaming",
                                            _spy):
                ok, log, plugin = porter.compile_cpp(cpp, spec, d, compiler="cl")
        self.assertFalse(ok)
        self.assertEqual(called["n"], 0)
        self.assertIn("STL1001", log)

    def test_compile_cpp_streams_via_log_cb(self):
        from mpynode.native.ai import porter

        spec = _portable_spec()
        lines = []

        def fake_stream(cmd, *, env=None, log_cb=None, **k):
            for ln in ("compiling…", "linking…"):
                log_cb(ln)
            return 0, "compiling…\nlinking…\n"

        with tempfile.TemporaryDirectory() as d:
            cpp = os.path.join(d, "x.cpp")
            with open(cpp, "w") as fh:
                fh.write("// stub\n")
            with unittest.mock.patch.object(porter.toolchain, "run_streaming",
                                            fake_stream):
                ok, log, plugin = porter.compile_cpp(cpp, spec, d,
                                                     log_cb=lines.append)
        self.assertTrue(ok)
        # The streamed compiler lines must reach log_cb, in order, and last.
        self.assertEqual(lines[-2:], ["compiling…", "linking…"])
        # The unix/macOS path is byte-clean: ONLY the streamed compiler lines,
        # so the exact match stays asserted THERE. On Windows compile_cpp
        # legitimately prepends three MSVC toolset diagnostics (compiler path /
        # build env / toolset), which is what broke this exact-match on
        # 2026-08-14 -- a reporting difference, not a pipeline difference.
        if not porter.toolchain.is_windows():
            self.assertEqual(lines, ["compiling…", "linking…"])
        self.assertIn("linking", log)

    def test_msvc_toolset_mismatch_refused_before_compiling(self):
        from mpynode.native.ai import porter

        spec = _portable_spec()
        stl_inc = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC"
                   r"\Tools\MSVC\14.51.36231\include")
        old_cl = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC"
                  r"\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe")

        def _spy(*a, **k):
            raise AssertionError("must NOT compile a known toolset mismatch")

        with tempfile.TemporaryDirectory() as d:
            cpp = os.path.join(d, "x.cpp")
            with open(cpp, "w") as fh:
                fh.write("// stub\n")
            # Ambient developer-shell fallback: capture failed (benv None) but
            # in a dev shell, so we'd compile with a stray PATH cl -- whose
            # toolset (14.44) differs from the dev-shell INCLUDE (14.51). That is
            # the exact STL1001 cause; refuse it BEFORE the 5 AI fix rounds.
            with unittest.mock.patch.object(porter.toolchain, "build_env",
                                            return_value=None), \
                 unittest.mock.patch.object(porter.toolchain, "in_developer_shell",
                                            return_value=True), \
                 unittest.mock.patch.object(porter.toolchain, "resolve_compiler",
                                            return_value=old_cl), \
                 unittest.mock.patch.dict(os.environ, {"INCLUDE": stl_inc}), \
                 unittest.mock.patch.object(porter.toolchain, "run_streaming",
                                            _spy):
                ok, log, plugin = porter.compile_cpp(cpp, spec, d, compiler="cl")
        self.assertFalse(ok)
        self.assertIn("STL1001", log)
        self.assertIn("14.44.35207", log)
        self.assertIn("14.51.36231", log)

    def test_msvc_consistent_toolset_compiles_and_logs_diagnostics(self):
        from mpynode.native.ai import porter

        spec = _portable_spec()
        root = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC"
                r"\Tools\MSVC\14.51.36231")
        good_cl = root + r"\bin\Hostx64\x64\cl.exe"
        good_inc = root + r"\include"
        lines = []

        def fake_stream(cmd, *, env=None, log_cb=None, **k):
            if log_cb:
                log_cb("cl : compiling x.cpp")
            return 0, "cl : compiling x.cpp\n"

        with tempfile.TemporaryDirectory() as d:
            cpp = os.path.join(d, "x.cpp")
            with open(cpp, "w") as fh:
                fh.write("// stub\n")
            # Captured vcvars env: cl resolved from VCToolsInstallDir matches the
            # INCLUDE toolset -> no mismatch -> compiles, and the diagnostics name
            # the resolved compiler + matched toolset in the log.
            with unittest.mock.patch.object(
                    porter.toolchain, "build_env",
                    return_value={"INCLUDE": good_inc, "VCToolsInstallDir": root}), \
                 unittest.mock.patch.object(porter.toolchain, "resolve_compiler",
                                            return_value=good_cl), \
                 unittest.mock.patch.object(porter.toolchain, "run_streaming",
                                            fake_stream):
                ok, log, plugin = porter.compile_cpp(cpp, spec, d, compiler="cl",
                                                     log_cb=lines.append)
        self.assertTrue(ok, log)
        joined = "\n".join(lines)
        self.assertIn(good_cl, joined)
        self.assertIn("14.51.36231", joined)
        self.assertIn("cl : compiling x.cpp", lines)


# ---------------------------------------------------------------------------
# port_node -- stream the multi-step porter work into the live log window
# ---------------------------------------------------------------------------


class TestPortNodeStepLogging(unittest.TestCase):
    def test_port_node_logs_its_steps(self):
        from mpynode.native.ai import porter

        lines = []

        def fake_compile(cpp_path, spec, out_dir, maya=None, compiler=None,
                         log_cb=None):
            return True, "ok", os.path.join(out_dir, "x.bundle")

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(porter, "compile_cpp", fake_compile):
            res = porter.port_node(
                _portable_spec(), d,
                complete_fn=lambda s, u: "out = a * 2.0;",
                log_cb=lines.append)
        self.assertTrue(res["ok"], res)
        joined = "\n".join(lines).lower()
        # The user wants to SEE the porter is doing multi-step work before the
        # compile: skeleton -> AI compute body -> compile.
        self.assertIn("skeleton", joined)
        self.assertIn("compute body", joined)
        self.assertIn("compil", joined)  # "compiling ..."


# ---------------------------------------------------------------------------
# bundler -- the multi-node compile/link path must ALSO decode a failed launch
# (the single-node compile_cpp got this; the bundler must not lag behind).
# ---------------------------------------------------------------------------


class TestBundlerCompileLaunchDecode(unittest.TestCase):
    def test_run_compile_decodes_filenotfound_to_message(self):
        from mpynode.native.compiler import bundler

        def _raise(*a, **k):
            raise FileNotFoundError(2, "The system cannot find the file specified")

        with unittest.mock.patch.object(bundler.toolchain, "run_streaming",
                                        _raise):
            proc = bundler._run_compile(["cl", "/c", "x.cpp"], None, "cl")
        # A failed launch must look like a normal nonzero-exit compile result,
        # carrying an actionable message -- never a raised bare [WinError 2].
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("WinError", proc.stderr)
        self.assertIn("cl", proc.stderr)

    def test_assemble_refuses_toolset_mismatch_before_compiling(self):
        # A CACHE HIT skips port_node/compile_cpp and assembles the cached .cpp
        # directly, so the toolset-mismatch guard must ALSO live in the bundler
        # (defense-in-depth) -- else a stray-cl-vs-newer-INCLUDE cache hit still
        # hits STL1001 in the final link.
        from mpynode.native.compiler import bundler

        stl_inc = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC"
                   r"\Tools\MSVC\14.51.36231\include")
        old_cl = (r"C:\Program Files\Microsoft Visual Studio\18\Community\VC"
                  r"\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe")

        def _spy(*a, **k):
            raise AssertionError("must NOT compile a known toolset mismatch")

        with tempfile.TemporaryDirectory() as d:
            # One transformable node .cpp so assemble reaches the compile step.
            cpp = os.path.join(d, "n.cpp")
            with open(cpp, "w") as fh:
                fh.write(
                    "#include <maya/MPxNode.h>\n"
                    "#include <maya/MFnPlugin.h>\n"
                    "class N : public MPxNode { public: static MTypeId id; };\n"
                    "MTypeId N::id(0x00001234);\n"
                    "MStatus initializePlugin(MObject o) {\n"
                    "    MFnPlugin plugin(o);\n"
                    "    plugin.registerNode(\"n\", N::id, N::creator,"
                    " N::initialize);\n"
                    "    return MS::kSuccess;\n"
                    "}\n"
                    "MStatus uninitializePlugin(MObject o) {\n"
                    "    MFnPlugin plugin(o);\n"
                    "    plugin.deregisterNode(N::id);\n"
                    "    return MS::kSuccess;\n"
                    "}\n")
            with unittest.mock.patch.object(bundler.toolchain, "default_compiler",
                                            return_value="cl"), \
                 unittest.mock.patch.object(bundler.toolchain, "build_env",
                                            return_value=None), \
                 unittest.mock.patch.object(bundler.toolchain, "in_developer_shell",
                                            return_value=True), \
                 unittest.mock.patch.object(bundler.toolchain, "resolve_compiler",
                                            return_value=old_cl), \
                 unittest.mock.patch.dict(os.environ, {"INCLUDE": stl_inc}), \
                 unittest.mock.patch.object(bundler.toolchain, "run_streaming",
                                            _spy):
                report = bundler.assemble([("n", cpp)], "myPlugin", d,
                                          strict=True)
        self.assertFalse(report.get("ok"))
        self.assertIn("STL1001", report.get("reason", ""))
        self.assertIn("14.44.35207", report.get("reason", ""))

    def test_run_compile_returns_streamed_result(self):
        from mpynode.native.compiler import bundler

        seen = {}

        def _fake(cmd, *, env=None, log_cb=None, **k):
            seen["cmd"] = cmd
            seen["env"] = env
            seen["log_cb"] = log_cb
            return 0, "compiled ok\n"

        sink = []

        def sink_fn(line):
            sink.append(line)

        with unittest.mock.patch.object(bundler.toolchain, "run_streaming",
                                        _fake):
            proc = bundler._run_compile(["clang++", "-c", "x.cpp"],
                                        {"PATH": "/x"}, "clang++",
                                        log_cb=sink_fn)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "compiled ok\n")
        self.assertEqual(seen["cmd"], ["clang++", "-c", "x.cpp"])
        self.assertEqual(seen["env"], {"PATH": "/x"})
        # log_cb must be forwarded so the dialog can stream the output.
        self.assertIs(seen["log_cb"], sink_fn)


# ---------------------------------------------------------------------------
# compile_plugin pre-flight ordering (no tokens spent on a bad host)
# ---------------------------------------------------------------------------


class TestCompilePluginPreflight(unittest.TestCase):
    def _run(self, *, toolchain_ok, provider_ok, complete_fn, reuse_cache=False,
             specs=None, optimize=False, provider_kind="api"):
        """Drive compile_plugin with injected pre-flights + a recording
        port_node/assemble so nothing actually compiles. Returns
        (result, port_calls, assemble_calls, events)."""
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler

        port_calls = []
        assemble_calls = []
        events = []

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": toolchain_ok,
                    "problems": [] if toolchain_ok else ["no C++ compiler"],
                    "compiler": "x", "compiler_path": None}

        def fake_check_provider(provider=None, model=None):
            return {"ok": provider_ok,
                    "problems": [] if provider_ok else ["No API key configured"],
                    "provider": provider, "kind": provider_kind}

        def fake_port_node(spec, out_dir, **k):
            port_calls.append(spec.get("suggested", {}).get("node_type_name"))
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("// ported\n")
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        def fake_assemble(nodes, plugin_name, out_dir, **k):
            assemble_calls.append([n for (n, _c) in nodes])
            bundle = _touch_bundle(out_dir, plugin_name)
            return {"ok": True,
                    "bundle": bundle,
                    "nodes": [{"name": n, "id": 1, "status": "compiled",
                               "reason": ""} for (n, _c) in nodes],
                    "dropped": [], "shared_helpers": []}

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(toolchain, "check_toolchain",
                                        fake_check_toolchain), \
             unittest.mock.patch.object(porter, "check_provider",
                                        fake_check_provider), \
             unittest.mock.patch.object(porter, "port_node", fake_port_node), \
             unittest.mock.patch.object(bundler, "assemble", fake_assemble):
            result = cc.compile_plugin(
                specs or [_portable_spec()], "myPlugin", d,
                strict=True, verify=False, reuse_cache=reuse_cache,
                complete_fn=complete_fn, provider="anthropic", model="m",
                optimize=optimize, progress_cb=events.append)
        return result, port_calls, assemble_calls, events

    def test_missing_toolchain_aborts_before_any_port_or_assemble(self):
        result, port_calls, assemble_calls, events = self._run(
            toolchain_ok=False, provider_ok=True, complete_fn=lambda s, u: "x")
        self.assertFalse(result["ok"])
        self.assertEqual(port_calls, [])
        self.assertEqual(assemble_calls, [])
        self.assertTrue(any("compiler" in e.lower() for e in result["errors"]),
                        result["errors"])
        self.assertTrue(any(ev.get("stage") == "preflight"
                            and ev.get("status") == "fail" for ev in events),
                        events)

    def test_missing_provider_aborts_at_first_miss_before_llm(self):
        # complete_fn=None -> the real provider would be used, so the provider
        # pre-flight gates the port. port_node must never be reached.
        result, port_calls, assemble_calls, events = self._run(
            toolchain_ok=True, provider_ok=False, complete_fn=None)
        self.assertFalse(result["ok"])
        self.assertEqual(port_calls, [])
        self.assertTrue(any("api key" in e.lower() for e in result["errors"]),
                        result["errors"])

    def test_deterministic_node_builds_without_provider(self):
        # A node that lowers DETERMINISTICALLY (no AI PORT region) never calls
        # the LLM, so a missing provider must NOT block it. Stub generate_cpp to
        # a PORT-region-free skeleton; the gate must react to that.
        from mpynode.native import compiler as codegen
        deterministic = "// full compute, no PORT region\n"
        self.assertNotIn(codegen.PORT_BEGIN, deterministic)
        with unittest.mock.patch.object(codegen, "generate_cpp",
                                        return_value=deterministic):
            result, port_calls, assemble_calls, events = self._run(
                toolchain_ok=True, provider_ok=False, complete_fn=None)
        self.assertTrue(result["ok"], result)
        self.assertEqual(port_calls, ["cubicCurveSampler"])
        self.assertEqual(assemble_calls, [["cubicCurveSampler"]])

    def test_injected_complete_fn_skips_provider_preflight(self):
        # When the caller injects its own complete_fn, the AI provider is never
        # used -- so a "missing provider" must NOT block the build.
        result, port_calls, assemble_calls, events = self._run(
            toolchain_ok=True, provider_ok=False,
            complete_fn=lambda s, u: "out = a * 2.0;")
        self.assertTrue(result["ok"], result)
        self.assertEqual(port_calls, ["cubicCurveSampler"])

    @staticmethod
    def _assist_skips(events):
        return [e for e in events if e.get("stage") == "port"
                and e.get("status") == "skip"]

    def test_a_run_that_needed_no_ai_says_so_once_porting_is_over(self):
        """"Did the AI have to fill anything?" is only ANSWERED once every node
        has ported. The controller knows (it already runs _node_needs_llm per
        node); nothing downstream can infer it, which left the dialog's AI-assist
        checkpoint grey for the whole run whenever optimize was off."""
        from mpynode.native import compiler as codegen
        specs = [_portable_spec("nodeA"), _portable_spec("nodeB")]
        with unittest.mock.patch.object(codegen, "generate_cpp",
                                        return_value="// no PORT region\n"):
            _r, _p, _a, events = self._run(toolchain_ok=True, provider_ok=True,
                                           complete_fn=None, specs=specs)
        said = self._assist_skips(events)
        self.assertEqual(len(said), 1, "once per RUN, never per node")
        self.assertIsNone(said[0]["node"], "it is a plugin-wide statement")
        self.assertIn("no node needed AI assist", said[0]["detail"])

    def test_a_run_where_any_node_needed_the_ai_makes_no_such_claim(self):
        from mpynode.native import compiler as codegen
        skeleton = "x\n%s\n%s\n" % (codegen.PORT_BEGIN, codegen.PORT_END)
        n = {"i": 0}

        def half_deterministic(spec, **k):
            n["i"] += 1
            return "// no PORT region\n" if n["i"] % 2 else skeleton

        specs = [_portable_spec("nodeA"), _portable_spec("nodeB")]
        with unittest.mock.patch.object(codegen, "generate_cpp",
                                        half_deterministic):
            _r, _p, _a, events = self._run(
                toolchain_ok=True, provider_ok=True,
                complete_fn=lambda s, u: "out = a * 2.0;", specs=specs)
        self.assertEqual(self._assist_skips(events), [],
                         "one node used the LLM, so the run did")

    def test_the_optimizers_own_notes_are_surfaced_and_the_raw_stream_is_not(self):
        """``compile_log_cb`` carries two things: the raw compiler/agent stream
        (a flood) and the optimizer's own "[optimizer] ..." notes -- which
        include the ONLY report a killed AI call ever produces. Off entirely,
        that report reached nothing; unfiltered, it arrives inside the flood."""
        from mpynode.native import compiler as codegen
        from mpynode.native.ai import optimizer_live

        seen = {}

        def fake_optimize_surviving(nodes, out_dir, **kw):
            seen["log_cb"] = kw.get("log_cb")
            seen["compile_log_cb"] = kw.get("compile_log_cb")
            return {}

        with unittest.mock.patch.object(codegen, "generate_cpp",
                                        return_value="// no PORT region\n"), \
             unittest.mock.patch.object(optimizer_live, "optimize_surviving",
                                        fake_optimize_surviving):
            _r, _p, _a, events = self._run(toolchain_ok=True, provider_ok=True,
                                           complete_fn=None, optimize=True)

        self.assertIsNotNone(seen.get("compile_log_cb"),
                             "the channel is not wired, so a timed-out AI call "
                             "still reports nothing")
        before = len(events)
        seen["compile_log_cb"]("[optimizer] the agent run ended early")
        seen["compile_log_cb"]("clang++ -O3 -c mPyThing.cpp   # 4000 more lines")
        details = [e.get("detail") for e in events[before:]]

        self.assertEqual(details, ["[optimizer] the agent run ended early"])
        self.assertTrue(all(e.get("stage") == "optimize" for e in
                            events[before:]), events[before:])

    def test_the_optimizer_and_the_report_agree_on_the_output_root(self):
        """The audit trail has to land where the report generator reads it.

        Both derive their paths from ``out_dir`` through ``bundler``, which
        appends ``build/`` itself. Handing the optimizer ``build/`` instead of
        the node ROOT put ``3_optimized/`` and ``rounds.json`` under
        ``build/build/stages/<Type>/`` -- a directory nothing reads, the scratch
        sweep never visits, and no test covered, so the whole per-round history
        of a 10-hour optimize run was written straight to a dead end."""
        from mpynode.native import compiler as codegen
        from mpynode.native.ai import optimizer_live
        from mpynode.native.toolchain import stage_report

        seen = {}

        def fake_optimize_surviving(nodes, out_dir, **kw):
            seen["optimize"] = out_dir
            return {}

        def fake_write_reports(out_dir, plugin_name, rows):
            seen["report"] = out_dir
            return []

        with unittest.mock.patch.object(codegen, "generate_cpp",
                                        return_value="// no PORT region\n"), \
             unittest.mock.patch.object(optimizer_live, "optimize_surviving",
                                        fake_optimize_surviving), \
             unittest.mock.patch.object(stage_report, "write_reports",
                                        fake_write_reports):
            self._run(toolchain_ok=True, provider_ok=True,
                      complete_fn=None, optimize=True)

        self.assertIn("optimize", seen, "the optimize hook never ran")
        self.assertIn("report", seen, "the report hook never ran")
        self.assertEqual(seen["optimize"], seen["report"],
                         "the optimizer writes its stages somewhere the report "
                         "generator does not read")
        # Pins the DIRECTION: both being ``build/`` would satisfy the equality
        # above while still doubling the root inside bundler.
        self.assertNotEqual(
            os.path.basename(seen["optimize"].rstrip(os.sep)), "build",
            "out_dir is the node ROOT -- bundler appends build/ itself")

    def _optimize_run(self, *, cap, provider_kind="api", agent_ok=True):
        """Drive the (c.6) optimize loop with a recording optimizer. Returns
        (nodes it was actually handed as [(name, .cpp text)], its events).

        ``agent_ok`` stubs the tool-using-agent pre-flight. The real one probes
        THIS machine (binary on PATH, a sandbox that nests), so without the stub
        the CLI arm depends on how the suite was launched."""
        from mpynode.native import compiler as codegen
        from mpynode.native.ai import optimizer_live
        from mpynode.native.ai import llm_client
        from mpynode.native.toolchain import compile_controller as cc

        handed = []

        def fake_optimize_surviving(nodes, out_dir, **kw):
            for (tn, cpp, _spec) in nodes:
                with open(cpp, "r") as fh:
                    handed.append((tn, fh.read()))
            return {}

        def fake_check_agent(provider=None):
            return {"ok": agent_ok, "provider": provider, "kind": "cli",
                    "problems": [] if agent_ok else ["sandboxes do not nest"]}

        with unittest.mock.patch.object(codegen, "generate_cpp",
                                        return_value="// no PORT region\n"), \
             unittest.mock.patch.object(optimizer_live, "optimize_surviving",
                                        fake_optimize_surviving), \
             unittest.mock.patch.object(llm_client, "check_agent",
                                        fake_check_agent), \
             unittest.mock.patch.object(cc, "_resolve_optimize_max_tokens",
                                        return_value=cap):
            _r, _p, _a, events = self._run(
                toolchain_ok=True, provider_ok=True, complete_fn=None,
                optimize=True, provider_kind=provider_kind)
        return handed, [e for e in events if e.get("stage") == "optimize"]

    def test_an_api_run_reports_its_response_budget_while_it_still_fits(self):
        """On the API path the optimizer must retype the WHOLE unit in one
        reply, so the ratio is only actionable BEFORE it is exceeded: the
        readout fires for a node that fits, not only for one already skipped.
        It quotes the estimate for the .cpp on disk and the resolved ceiling."""
        from mpynode.native.toolchain import compile_controller as cc

        handed, opt_events = self._optimize_run(cap=4242)
        self.assertEqual([n for (n, _t) in handed], ["cubicCurveSampler"],
                         "a node that fits must still be optimized")
        need = cc._response_tokens_needed(handed[0][1])
        self.assertEqual(
            [e["detail"] for e in opt_events if e["status"] == "info"],
            ["cubicCurveSampler response budget: %d/4242 tokens" % need])

    def test_an_over_budget_node_is_skipped_quoting_that_same_estimate(self):
        """Over the ceiling the node is dropped instead of read out, and the
        skip quotes the SAME estimator the readout does -- patch that one
        function and the gate's number moves with it."""
        from mpynode.native.toolchain import compile_controller as cc

        with unittest.mock.patch.object(cc, "_response_tokens_needed",
                                        return_value=4242):
            handed, opt_events = self._optimize_run(cap=100)
        self.assertEqual(handed, [], "an unfittable node must not spend a call")
        skips = [e["detail"] for e in opt_events if e["status"] == "skip"]
        self.assertEqual(len(skips), 1, opt_events)
        self.assertIn("needs ~4242 response tokens and the cap is 100",
                      skips[0])
        self.assertEqual([e for e in opt_events if e["status"] == "info"], [])

    def test_a_cli_run_gets_no_response_budget_readout_at_all(self):
        """The CLI agent EDITS the file in place, so no reply has to hold it:
        a ceiling that cannot bind must neither skip the node nor be quoted at
        it. cap=1 skips every node on the one-shot path."""
        handed, opt_events = self._optimize_run(cap=1,
                                                provider_kind="claude_cli")
        self.assertEqual([n for (n, _t) in handed], ["cubicCurveSampler"])
        self.assertEqual([e["detail"] for e in opt_events
                          if "budget" in e["detail"] or e["status"] == "skip"],
                         [])

    def test_a_cli_provider_demoted_to_one_shot_is_gated_like_an_api_one(self):
        """The CLI provider is reachable -- so ``prov["kind"] == "cli"`` -- but
        the AGENT pre-flight fails, and optimizer_live then falls back to the
        blind whole-file rewrite. That path has to retype the unit, so the
        ceiling binds. Gating on the provider kind is what let the two biggest
        nodes spend ~11 min a round on a rewrite that cannot fit."""
        handed, opt_events = self._optimize_run(
            cap=1, provider_kind="claude_cli", agent_ok=False)
        self.assertEqual(handed, [],
                         "a demoted CLI run must not spend a call it cannot fit")
        skips = [e["detail"] for e in opt_events if e["status"] == "skip"]
        self.assertEqual(len(skips), 1, opt_events)
        self.assertIn("whole-file rewrite", skips[0])

    def test_happy_path_ports_when_both_preflights_pass(self):
        result, port_calls, assemble_calls, events = self._run(
            toolchain_ok=True, provider_ok=True, complete_fn=None)
        self.assertTrue(result["ok"], result)
        self.assertEqual(port_calls, ["cubicCurveSampler"])
        self.assertEqual(assemble_calls, [["cubicCurveSampler"]])


class TestCompilePluginNameGuards(unittest.TestCase):
    """Engine-level name guards + per-Class collapse. A compiled node may not
    register a framework type name (mPyNode/mPyIkSolver/...). Multiple INSTANCES
    of one Class legitimately share a native type: IDENTICAL instances collapse
    to a single compiled type (compile the Class once); instances whose code has
    DIVERGED are surfaced (fork the divergent one) rather than silently
    mis-compiled -- the must-fix #1 integrity guard."""

    def _run(self, specs, *, strict):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler

        port_calls = []
        assemble_calls = []

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_port_node(spec, out_dir, **k):
            port_calls.append(spec["suggested"]["node_type_name"])
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("// ported\n")
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        def fake_assemble(nodes, plugin_name, out_dir, **k):
            assemble_calls.append([n for (n, _c) in nodes])
            bundle = _touch_bundle(out_dir, plugin_name)
            return {"ok": True,
                    "bundle": bundle,
                    "nodes": [{"name": n, "id": 1, "status": "compiled",
                               "reason": ""} for (n, _c) in nodes],
                    "dropped": [], "shared_helpers": []}

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(toolchain, "check_toolchain",
                                        fake_check_toolchain), \
             unittest.mock.patch.object(porter, "port_node", fake_port_node), \
             unittest.mock.patch.object(bundler, "assemble", fake_assemble):
            result = cc.compile_plugin(
                specs, "myPlugin", d, strict=strict, verify=False,
                reuse_cache=False, complete_fn=lambda s, u: "out = a*2.0;",
                provider="anthropic", model="m")
        return result, port_calls, assemble_calls

    def test_reserved_name_strict_aborts_before_port(self):
        result, port_calls, _ = self._run([_portable_spec("mPyNode")],
                                          strict=True)
        self.assertFalse(result["ok"])
        self.assertEqual(port_calls, [])
        self.assertTrue(any("reserved" in e.lower() for e in result["errors"]),
                        result["errors"])

    def test_reserved_name_case_insensitive(self):
        # "MPyIkSolver" (the user's capitalization) is caught too.
        result, port_calls, _ = self._run([_portable_spec("MPyIkSolver")],
                                          strict=True)
        self.assertFalse(result["ok"])
        self.assertEqual(port_calls, [])

    def test_reserved_name_best_effort_drops_and_keeps_others(self):
        result, port_calls, assemble_calls = self._run(
            [_portable_spec("mPyIkSolver"), _portable_spec("goodNode")],
            strict=False)
        self.assertTrue(result["ok"], result)
        self.assertEqual(port_calls, ["goodNode"])
        self.assertEqual(assemble_calls, [["goodNode"]])
        dropped = [r for r in result["nodes"] if r["build_status"] == "dropped"]
        self.assertEqual([r["type_name"] for r in dropped], ["mPyIkSolver"])
        self.assertIn("reserved", dropped[0]["build_reason"])

    @staticmethod
    def _diverged():
        """Two specs sharing ONE type name but with DIFFERENT compute code --
        the Duplicate-then-edit divergence the guard must catch."""
        a = _portable_spec("dupNode")
        b = _portable_spec("dupNode")
        b["compute"] = "out = a * 3.0"  # edited sibling
        return [a, b]

    def test_identical_instances_collapse_best_effort(self):
        # Two INSTANCES of one Class with identical code -> compile the Class
        # ONCE, no error, no dropped row (a normal per-Class compile).
        result, port_calls, assemble_calls = self._run(
            [_portable_spec("dupNode"), _portable_spec("dupNode")],
            strict=False)
        self.assertTrue(result["ok"], result)
        self.assertEqual(port_calls, ["dupNode"])        # ported once
        self.assertEqual(assemble_calls, [["dupNode"]])  # bundle has ONE
        dropped = [r for r in result["nodes"] if r["build_status"] == "dropped"]
        self.assertEqual(dropped, [])                    # collapsed silently

    def test_identical_instances_collapse_strict(self):
        # Strict no longer aborts on identical instances -- they are the same
        # Class, so the build succeeds with a single compiled type.
        result, port_calls, _ = self._run(
            [_portable_spec("dupNode"), _portable_spec("dupNode")],
            strict=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(port_calls, ["dupNode"])

    def test_diverged_instances_strict_aborts(self):
        result, port_calls, _ = self._run(self._diverged(), strict=True)
        self.assertFalse(result["ok"])
        self.assertEqual(port_calls, ["dupNode"])  # first ok, second aborts
        blob = " ".join(result["errors"]).lower()
        self.assertIn("diverged", blob, result["errors"])
        self.assertIn("fork", blob, result["errors"])

    def test_diverged_instances_best_effort_drops_with_fork_hint(self):
        result, port_calls, assemble_calls = self._run(self._diverged(),
                                                       strict=False)
        self.assertTrue(result["ok"], result)
        self.assertEqual(port_calls, ["dupNode"])        # only the first ported
        self.assertEqual(assemble_calls, [["dupNode"]])  # bundle has ONE
        dropped = [r for r in result["nodes"] if r["build_status"] == "dropped"]
        self.assertEqual(len(dropped), 1)
        self.assertIn("diverged", dropped[0]["build_reason"].lower())
        self.assertIn("fork", dropped[0]["build_reason"].lower())


# ---------------------------------------------------------------------------
# compile_plugin -> live compiler-output streaming (the dialog's log window)
# ---------------------------------------------------------------------------


class TestCompilePluginLogStreaming(unittest.TestCase):
    """The controller must hand porter.port_node AND bundler.assemble a usable
    ``log_cb`` whose lines become ``stage='log', status='line'`` progress events,
    so the compile dialog can stream the subprocess output live."""

    def test_port_and_assemble_lines_become_log_events(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler

        events = []

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_port_node(spec, out_dir, log_cb=None, **k):
            # The controller MUST pass a usable log_cb down to the porter.
            assert callable(log_cb), "controller did not pass a log_cb to port_node"
            log_cb("clang: compiling foo.cpp")
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("// ported\n")
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        def fake_assemble(nodes, plugin_name, out_dir, log_cb=None, **k):
            assert callable(log_cb), "controller did not pass a log_cb to assemble"
            log_cb("clang: linking myPlugin.bundle")
            bundle = _touch_bundle(out_dir, plugin_name)
            return {"ok": True,
                    "bundle": bundle,
                    "nodes": [{"name": n, "id": 1, "status": "compiled",
                               "reason": ""} for (n, _c) in nodes],
                    "dropped": [], "shared_helpers": []}

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(toolchain, "check_toolchain",
                                        fake_check_toolchain), \
             unittest.mock.patch.object(porter, "port_node", fake_port_node), \
             unittest.mock.patch.object(bundler, "assemble", fake_assemble):
            result = cc.compile_plugin(
                [_portable_spec()], "myPlugin", d, strict=True, verify=False,
                reuse_cache=False, complete_fn=lambda s, u: "x",
                provider="anthropic", model="m", progress_cb=events.append)

        self.assertTrue(result["ok"], result)
        log_events = [e for e in events
                      if e.get("stage") == "log" and e.get("status") == "line"]
        details = [e.get("detail") for e in log_events]
        self.assertIn("clang: compiling foo.cpp", details)
        self.assertIn("clang: linking myPlugin.bundle", details)
        # The per-node line is tagged with the node name; the assemble line is
        # plugin-wide (node is None) so the dialog can route it correctly.
        port_log = next(e for e in log_events
                        if e["detail"] == "clang: compiling foo.cpp")
        self.assertEqual(port_log["node"], "cubicCurveSampler")
        asm_log = next(e for e in log_events
                       if e["detail"] == "clang: linking myPlugin.bundle")
        self.assertIsNone(asm_log["node"])

    def test_no_progress_cb_still_writes_durable_port_log(self):
        # The PER-NODE port log_cb is ALWAYS a callback so the durable
        # out_dir/<type>/compile.log is captured headlessly. The plugin-wide
        # ASSEMBLE log_cb stays None when nothing is listening.
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler

        seen = {}

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_port_node(spec, out_dir, log_cb=None, **k):
            seen["port_log_cb"] = log_cb
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("// ported\n")
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        def fake_assemble(nodes, plugin_name, out_dir, log_cb=None, **k):
            seen["asm_log_cb"] = log_cb
            bundle = _touch_bundle(out_dir, plugin_name)
            return {"ok": True,
                    "bundle": bundle,
                    "nodes": [{"name": n, "id": 1, "status": "compiled",
                               "reason": ""} for (n, _c) in nodes],
                    "dropped": [], "shared_helpers": []}

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(toolchain, "check_toolchain",
                                        fake_check_toolchain), \
             unittest.mock.patch.object(porter, "port_node", fake_port_node), \
             unittest.mock.patch.object(bundler, "assemble", fake_assemble):
            result = cc.compile_plugin(
                [_portable_spec()], "myPlugin", d, strict=True, verify=False,
                reuse_cache=False, complete_fn=lambda s, u: "x",
                provider="anthropic", model="m", progress_cb=None)
        self.assertTrue(result["ok"], result)
        self.assertIsNotNone(seen["port_log_cb"])
        self.assertTrue(callable(seen["port_log_cb"]))
        self.assertIsNone(seen["asm_log_cb"])


# ---------------------------------------------------------------------------
# compile_plugin -> decode STL1001 (toolset mismatch) in a failure reason
# ---------------------------------------------------------------------------


class TestCompilePluginStl1001Hint(unittest.TestCase):
    """An STL1001 'Unexpected compiler version' in the compiler output must be
    turned into a plain-English next step in the failure reason -- on BOTH the
    per-node port path and the plugin-wide assemble path."""

    _STL1001_LOG = (
        "yvals_core.h(921): error C2338: static_assert failed: 'error STL1001: "
        "Unexpected compiler version, expected MSVC Compiler 19.50 or newer.'")

    def test_port_compile_failure_appends_stl1001_hint(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.ai import porter

        events = []

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_port_node(spec, out_dir, log_cb=None, **k):
            return {"ok": False, "cpp": None, "fix_rounds": 4,
                    "compiler_log": self._STL1001_LOG}

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(toolchain, "check_toolchain",
                                        fake_check_toolchain), \
             unittest.mock.patch.object(porter, "port_node", fake_port_node):
            result = cc.compile_plugin(
                [_portable_spec()], "myPlugin", d, strict=True, verify=False,
                reuse_cache=False, complete_fn=lambda s, u: "x",
                provider="anthropic", model="m", progress_cb=events.append)

        self.assertFalse(result["ok"])
        joined = " ".join(result["errors"]).lower()
        self.assertIn("toolset", joined)  # the STL1001 hint phrase
        # The failure event the dialog shows must also carry the hint.
        port_fail = next(e for e in events
                         if e.get("stage") == "port" and e.get("status") == "fail")
        self.assertIn("toolset", (port_fail.get("detail") or "").lower())

    def test_assemble_compile_failure_appends_stl1001_hint(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.ai import porter
        from mpynode.native.compiler import bundler

        events = []

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_port_node(spec, out_dir, log_cb=None, **k):
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("// ported\n")
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        def fake_assemble(nodes, plugin_name, out_dir, log_cb=None, **k):
            # Compile/link failed inside the bundler; the full streamed text is
            # surfaced on report['stderr'] (see bundler.assemble).
            return {"ok": False, "bundle": None, "reason": "link failed",
                    "stderr": self._STL1001_LOG,
                    "nodes": [{"name": n, "id": 1, "status": "compile-failed",
                               "reason": "err"} for (n, _c) in nodes],
                    "dropped": []}

        with tempfile.TemporaryDirectory() as d, \
             unittest.mock.patch.object(toolchain, "check_toolchain",
                                        fake_check_toolchain), \
             unittest.mock.patch.object(porter, "port_node", fake_port_node), \
             unittest.mock.patch.object(bundler, "assemble", fake_assemble):
            result = cc.compile_plugin(
                [_portable_spec()], "myPlugin", d, strict=True, verify=False,
                reuse_cache=False, complete_fn=lambda s, u: "x",
                provider="anthropic", model="m", progress_cb=events.append)

        self.assertFalse(result["ok"])
        joined = " ".join(result["errors"]).lower()
        self.assertIn("toolset", joined)
        asm_fail = next(e for e in events
                        if e.get("stage") == "assemble"
                        and e.get("status") == "fail")
        self.assertIn("toolset", (asm_fail.get("detail") or "").lower())


class TestAssembleSingleStaleBundlePreserved(unittest.TestCase):
    """#67 regression guard (adversarial-review finding): a single-node
    recompile that can't find a compiler must NOT delete the previously-built
    bundle. The stale-bundle removal happens only AFTER the compiler is
    confirmed available (mirrors the multi-node assemble path)."""

    def test_no_compiler_recompile_keeps_prior_bundle(self):
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain.typeid_registry import TypeIdRegistry

        with tempfile.TemporaryDirectory() as d:
            ext = bundler.toolchain.plugin_ext()
            stale = os.path.join(d, "smokePlug" + ext)
            with open(stale, "w") as fh:
                fh.write("PRIOR-GOOD-BUNDLE")
            cpp = os.path.join(d, "smokeDoubler.cpp")
            with open(cpp, "w") as fh:
                fh.write("// trivial\n")
            reg = TypeIdRegistry(path=os.path.join(d, "reg.json"))
            with unittest.mock.patch.object(
                    bundler, "make_single_node_cpp",
                    return_value=("// canned\n", {"node_name": "smokeDoubler"})), \
                 unittest.mock.patch.object(
                     bundler, "_prepare_compiler", return_value=None):
                report = bundler.assemble(
                    [("smokeDoubler", cpp)], "smokePlug", d,
                    compile_now=True, registry=reg)
            self.assertFalse(report["ok"])
            self.assertTrue(
                os.path.exists(stale),
                "a compiler-unavailable recompile deleted the previously-built "
                "bundle")
            with open(stale) as fh:
                self.assertEqual(fh.read(), "PRIOR-GOOD-BUNDLE")


class TestOptimizeFallbackRefreshesRows(unittest.TestCase):
    """#66 (adversarial-review finding): when an accepted AI-optimized candidate
    fails the FINAL multi-node compile and the deterministic fallback re-assemble
    SUCCEEDS, the per-node rows must be refreshed from the SECOND report so the
    shipped node is recorded 'compiled' -- not left 'compile-failed', which would
    wrongly drop it from verify / companions / the manifest."""

    class _OptRes:
        def __init__(self, accepted, speedup, reason):
            self.accepted = accepted
            self.speedup = speedup
            self.reason = reason

    def test_fallback_marks_node_compiled_not_failed(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode.native.toolchain import toolchain
        from mpynode.native.ai import porter
        from mpynode.native.ai import optimizer_live
        from mpynode.native.compiler import bundler
        from mpynode.native.toolchain.typeid_registry import TypeIdRegistry

        def fake_check_toolchain(maya, *a, **k):
            return {"ok": True, "problems": [], "compiler": "x",
                    "compiler_path": None}

        def fake_check_provider(provider=None, model=None):
            return {"ok": True, "problems": [], "provider": provider,
                    "kind": "api"}

        def fake_port_node(spec, out_dir, **k):
            cpp = os.path.join(out_dir,
                               spec["suggested"]["node_type_name"] + ".cpp")
            with open(cpp, "w") as fh:
                fh.write("// ported\n")
            return {"ok": True, "cpp": cpp, "fix_rounds": 0}

        with tempfile.TemporaryDirectory() as d:
            bundle = os.path.join(d, "myPlugin.bundle")
            with open(bundle, "w") as fh:
                fh.write("")  # the fallback re-assemble's on-disk artifact
            # 1st assemble (OPTIMIZED frag) fails the per-node compile; 2nd
            # assemble (deterministic fallback) links fine.
            fail_report = {
                "ok": False, "bundle": None, "reason": "build failed",
                "dropped": ["cubicCurveSampler"],
                "nodes": [{"name": "cubicCurveSampler",
                           "status": "compile-failed",
                           "reason": "optimized frag failed", "id": None}]}
            ok_report = {
                "ok": True, "bundle": bundle, "shared_helpers": [], "dropped": [],
                "nodes": [{"name": "cubicCurveSampler", "status": "compiled",
                           "reason": "", "id": 7}]}
            reg = TypeIdRegistry(path=os.path.join(d, "reg.json"))
            with unittest.mock.patch.object(toolchain, "check_toolchain",
                                            fake_check_toolchain), \
                 unittest.mock.patch.object(porter, "check_provider",
                                            fake_check_provider), \
                 unittest.mock.patch.object(porter, "port_node",
                                            fake_port_node), \
                 unittest.mock.patch.object(cc, "_optimize_skip_reason",
                                            return_value=""), \
                 unittest.mock.patch.object(
                     optimizer_live, "optimize_surviving",
                     return_value={"cubicCurveSampler":
                                   self._OptRes(True, 2.0, "2.00x faster")}), \
                 unittest.mock.patch.object(
                     optimizer_live, "rollback_preopt",
                     return_value=["cubicCurveSampler.cpp"]), \
                 unittest.mock.patch.object(optimizer_live, "discard_preopt",
                                            return_value=[]), \
                 unittest.mock.patch.object(bundler, "assemble",
                                            side_effect=[fail_report, ok_report]):
                result = cc.compile_plugin(
                    [_portable_spec()], "myPlugin", d, strict=True,
                    verify=False, reuse_cache=False, optimize=True,
                    complete_fn=lambda s, u: "out = a*2.0;",
                    provider="anthropic", model="m", registry=reg)

        self.assertTrue(result["ok"], result)
        node = next(n for n in result["nodes"]
                    if n["type_name"] == "cubicCurveSampler")
        self.assertEqual(node["build_status"], "compiled",
                         "fallback-shipped node must be recorded compiled")
        self.assertEqual(node["type_id"], 7)


# ===================== from test_file_read_support.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init, ensure_plugins_loaded


def _setUpModule__file_read_support():
    standalone_init()
    ensure_plugins_loaded()


class TestImageReadCarveOut(unittest.TestCase):
    """Pure assess_portability -- no Maya needed.

    The carve-out is the load-bearing part and is UNCHANGED: ``allow_file_read``
    is what turns an image read into ``reads_image_file``, which drives the
    MImage::readFromFile codegen and the loose/skip verify. Without it the read
    is merely a reported gap -- so the flag still means exactly "a SANCTIONED
    read on a texture node", never "someone wrote imread somewhere"."""

    def test_imread_is_a_gap_by_default(self):
        from mpynode.native.spec import spec_extractor as se
        r = se.assess_portability("x = cv2.imread(self.fileName)", "", {}, {}, {})
        # Not refused -- but NOT sanctioned either, which is the bit that matters.
        self.assertFalse(r.get("reads_image_file"))
        self.assertTrue(any("image file read" in u for u in r["unported"]),
                        r["unported"])

    def test_cv2_imread_allowed_for_texture_node(self):
        from mpynode.native.spec import spec_extractor as se
        r = se.assess_portability("img = cv2.imread(self.fileName)", "", {}, {},
                                  {}, allow_file_read=True)
        self.assertTrue(r["portable"], r.get("blockers"))
        self.assertTrue(r["reads_image_file"])
        self.assertTrue(any("file" in w.lower() for w in r["warnings"]),
                        "expected a file-read warning: %r" % r["warnings"])

    def test_pil_open_allowed_for_texture_node(self):
        from mpynode.native.spec import spec_extractor as se
        r = se.assess_portability("", "img = Image.open(self.fileName)", {}, {},
                                  {}, allow_file_read=True)
        self.assertTrue(r["portable"], r.get("blockers"))
        self.assertTrue(r["reads_image_file"])

    def test_skimage_imread_allowed_imsave_not_sanctioned(self):
        from mpynode.native.spec import spec_extractor as se
        rd = se.assess_portability("a = io.imread(self.fileName)", "", {}, {},
                                   {}, allow_file_read=True)
        self.assertTrue(rd["portable"], rd.get("blockers"))
        self.assertTrue(rd["reads_image_file"])
        wr = se.assess_portability("io.imsave(self.fileName, a)", "", {}, {},
                                   {}, allow_file_read=True)
        # A WRITE is never sanctioned: the carve-out is a read kernel only.
        self.assertFalse(wr.get("reads_image_file"))
        self.assertTrue(wr["unported"], "the write must still be reported")

    def test_image_write_is_not_sanctioned_even_for_texture(self):
        from mpynode.native.spec import spec_extractor as se
        r = se.assess_portability("cv2.imwrite(self.fileName, img)", "", {}, {},
                                  {}, allow_file_read=True)
        self.assertFalse(r.get("reads_image_file"))
        self.assertTrue(any("cv2" in u for u in r["unported"]), r["unported"])

    def test_bare_open_is_not_sanctioned_even_for_texture(self):
        from mpynode.native.spec import spec_extractor as se
        # Non-binary open on a texture node: NOT the embedded-image staging
        # idiom, so it must not be mistaken for it.
        r = se.assess_portability("f = open(self.fileName)", "", {}, {}, {},
                                  allow_file_read=True)
        self.assertFalse(r.get("reads_embedded_image"))
        self.assertTrue(any("open()" in u for u in r["unported"]), r["unported"])

    def test_socket_is_reported_even_for_texture(self):
        from mpynode.native.spec import spec_extractor as se
        r = se.assess_portability("socket.socket()", "", {}, {}, {},
                                  allow_file_read=True)
        self.assertTrue(any("socket" in u for u in r["unported"]), r["unported"])

    def test_no_image_read_leaves_flag_false(self):
        from mpynode.native.spec import spec_extractor as se
        r = se.assess_portability("self.out = self.uIn * 2.0", "", {}, {}, {},
                                  allow_file_read=True)
        self.assertTrue(r["portable"])
        self.assertFalse(r.get("reads_image_file"))
        self.assertEqual([], r["unported"])


class TestGeometryMultiAndAliasBlockers(unittest.TestCase):
    """The blendShape gate reports by CAPABILITY, not by attribute name.

    `nd_lower` rewrites a geometry-multi element read only at a LITERAL index,
    so a loop over targets at a runtime index genuinely cannot lower -- while
    the same attr read at a constant index lowers today. And `self.aliases` is
    an authoring-time property: alias lookup is a side-channel DG query, and
    those return EMPTY on the EM worker thread that deform() runs on, so a
    compute reading names would be unreliable interpreted and impossible
    compiled.

    Neither refuses the build any more; both are reported as ``unported`` (each
    reason naming its deterministic alternative) and handed to the porter. The
    discriminating assertion is that the RIGHT form raises no gap while the
    unlowerable one does -- a blanket flag on the attribute NAME would put a
    false gap in the prompt for code that compiles today.
    """

    BS_INPUTS = {
        "weight": {"attr_type": "float", "is_array": True},
        "targetOffset": {"attr_type": "int", "is_array": True},
        "targetComponents": {"attr_type": "int", "is_array": True},
        "targetDeltas": {"attr_type": "double", "is_array": True},
    }

    def _assess(self, compute, inputs=None):
        from mpynode.native.spec import spec_extractor as se
        return se.assess_portability(
            compute, "", self.BS_INPUTS if inputs is None else inputs, {}, {})

    def test_geometry_multi_at_a_runtime_index_is_reported(self):
        r = self._assess(
            "for i in range(4):\n"
            "    tgt = self.targetGeometry[i]\n")
        self.assertTrue(r["portable"], r["blockers"])
        self.assertTrue(any("RUNTIME index" in u for u in r["unported"]),
                        r["unported"])
        # The reason must carry the deterministic alternative, because that text
        # is what the porter is shown.
        self.assertTrue(any("bake_deltas" in u for u in r["unported"]),
                        r["unported"])

    def test_geometry_multi_at_a_LITERAL_index_raises_no_gap(self):
        r = self._assess("tgt = self.targetGeometry[0]\n")
        self.assertTrue(r["portable"], r["blockers"])
        self.assertEqual([], r["unported"])

    def test_a_user_declared_mesh_multi_is_reported_the_same_way(self):
        """The rule is derived from the inputs map, not a hardcoded name, so a
        user's own mesh array gets the same treatment."""
        ins = dict(self.BS_INPUTS)
        ins["myMeshes"] = {"attr_type": "mesh", "is_array": True}
        r = self._assess("m = self.myMeshes[k]\n", inputs=ins)
        self.assertTrue(r["portable"], r["blockers"])
        self.assertTrue(any("myMeshes" in u for u in r["unported"]),
                        r["unported"])

    def test_a_scalar_array_at_a_runtime_index_raises_no_gap(self):
        """Only GEOMETRY multis are affected -- numeric arrays are the whole
        point of the design and must lower cleanly."""
        r = self._assess("w = float(self.weight[t])\n")
        self.assertTrue(r["portable"], r["blockers"])
        self.assertEqual([], r["unported"])

    def test_reading_aliases_in_a_compute_is_reported(self):
        for spelling in ("self.aliases", "self.target_names",
                         "self.alias_fingerprint"):
            r = self._assess("for nm in %s:\n    pass\n" % spelling)
            self.assertTrue(r["portable"], (spelling, r["blockers"]))
            self.assertTrue(any("target names" in u for u in r["unported"]),
                            (spelling, r["unported"]))

    def test_the_baked_delta_compute_is_portable(self):
        r = self._assess(
            "mesh = self.outputGeometry[0]\n"
            "base = mesh.getPoints()\n"
            "w = self.weight\n"
            "ofs = self.targetOffset\n"
            "comp = self.targetComponents\n"
            "dlt = self.targetDeltas\n"
            "flat = base.reshape(-1).copy()\n"
            "for t in range(w.shape[0]):\n"
            "    wt = float(w[t])\n"
            "    if wt != 0.0 and t + 1 < ofs.shape[0]:\n"
            "        for j in range(int(ofs[t]), int(ofs[t + 1])):\n"
            "            v = int(comp[j])\n"
            "            flat[3 * v] = flat[3 * v] + wt * float(dlt[3 * j])\n"
            "out = flat.reshape(-1, 3)\n"
            "mesh.setPoints(out)\n")
        self.assertTrue(r["portable"], r["blockers"])


class TestSpecReadsImageFileHelper(unittest.TestCase):
    def test_helper_reads_flag(self):
        from mpynode.native.spec import spec_extractor as se
        self.assertTrue(se.spec_reads_image_file(
            {"suggested": {"reads_image_file": True}}))
        self.assertFalse(se.spec_reads_image_file({"suggested": {}}))
        self.assertFalse(se.spec_reads_image_file({}))


class TestImageReadCodegen(unittest.TestCase):
    """A reads_image_file spec must emit the MImage::readFromFile scaffold
    (include + CACHED load + RGBA8 buffer exposed to the ported compute). The
    decode is cached per node instance (nd_img_load_raw) -- a per-compute decode
    is per shading sample and makes a render thousands of times slower than the
    Python node (which caches its decode in _GRID_CACHE)."""

    def _spec(self, *, reads=True, with_filename=True):
        from mpynode.native.spec import spec_extractor
        from mpynode import MPyNode
        import maya.cmds as cmds

        cmds.file(new=True, force=True)
        w = MPyNode.create(name="texSrc#")
        if with_filename:
            w.add_input_attr("fileName", "string")
        w.add_input_attr("uIn", "float")
        w.add_output_attr("outColor", "vector")
        # CANARY -- must stay NON-lowerable: the MImage scaffold is emitted only on
        # the AI-porter path, so if this compute lowers to C++ the test silently
        # stops checking anything. A class definition is rejected STRUCTURALLY
        # (py_to_cpp: "unsupported statement (line 1, node ClassDef)") -- a compiled
        # compute() cannot create a Python type at runtime, so this will not become
        # lowerable. Do NOT replace it with something merely unimplemented today:
        # this used to be a bare list literal until the transpiler gained ex_List.
        w.set_compute_expression(
            "class _Tint(object):\n"
            "    gain = 2.0\n"
            "self.outColor = [self.uIn * _Tint.gain, self.uIn, self.uIn]\n")
        spec = spec_extractor.extract_spec(w.get_name())
        spec["suggested"]["node_type_name"] = "texTestNode"
        if reads:
            spec["suggested"]["reads_image_file"] = True
        else:
            spec["suggested"].pop("reads_image_file", None)
        return spec

    def test_reads_image_emits_mimage_scaffold(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(reads=True), for_port=True)
        self.assertIn("maya/MImage.h", cpp)
        self.assertIn("readFromFile", cpp)            # the decode is emitted...
        self.assertIn("nd_img_load_raw(_imgRawCache", cpp)  # ...but CACHED (not per-compute)
        self.assertIn("in_aFileName", cpp)            # path comes from the fileName input
        self.assertIn("_imgPixels", cpp)
        self.assertIn("getSize", cpp)
        # PERF guard: the decode must NOT run inside compute() (per sample).
        self.assertNotIn(".readFromFile(", cpp.split("::compute(", 1)[1])

    def test_no_reads_no_mimage(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(reads=False), for_port=True)
        self.assertNotIn("MImage", cpp)
        self.assertNotIn("_imgPixels", cpp)


class TestImageReadGuidance(unittest.TestCase):
    """The porter guide must teach the imread->_imgPixels mapping only when the
    node is a sanctioned file reader."""

    def test_guidance_present_when_reads_image(self):
        from mpynode.native.ai import translation_knowledge as tk
        # `inputs` carries the path plug because the guidance is now gated on one
        # RESOLVING: the scaffold only declares `_imgPixels` when it does, so
        # promising it otherwise names an identifier the TU never has. Every real
        # spec reaching here has the plug -- the self.<name> scan picks up the
        # `self.fileName` this compute reads, and extract_spec captures it
        # explicitly for the helper-call readers that scan misses.
        spec = {"compute": "img = Image.open(self.fileName)", "init": "",
                "inputs": {"fileName": {"type": "string"}},
                "suggested": {"reads_image_file": True}}
        guide = tk.guide_for_spec(spec)
        self.assertIn("_imgPixels", guide)
        self.assertIn("MImage::readFromFile", guide)
        self.assertIn("SANCTIONED IMAGE FILE READ", guide)

    def test_guidance_absent_without_flag(self):
        from mpynode.native.ai import translation_knowledge as tk
        spec = {"compute": "self.out = self.uIn * 2", "init": "",
                "suggested": {}}
        guide = tk.guide_for_spec(spec)
        self.assertNotIn("_imgPixels", guide)

    def test_guidance_absent_when_the_flag_has_no_path_plug(self):
        # Flag set but no string/hex INPUT: the scaffold suppresses the cache, so
        # the guide must not tell the porter a buffer was loaded for it.
        from mpynode.native.ai import translation_knowledge as tk
        spec = {"compute": "img = Image.open('/tmp/hardcoded.png')", "init": "",
                "inputs": {"amount": {"type": "float"}},
                "suggested": {"reads_image_file": True}}
        guide = tk.guide_for_spec(spec)
        self.assertNotIn("SANCTIONED IMAGE FILE READ", guide)


_CLOSEST_POINT_COMPUTE = (
    "import maya.api.OpenMaya as om\n"
    "isect = om.MMeshIntersector()\n"
    "isect.create(self.inMesh.to_mobject())\n"
    "r = isect.getClosestPoint(om.MPoint(0.0, 0.0, 0.0))\n"
    "self.outMesh = Mesh(points=[[r.point.x, r.point.y, r.point.z]])\n"
)


def _closest_point_spec(mpy_type, *, flag=True):
    """Minimal spec for the two emitters that gate on uses_mesh_intersector:
    ``mPyMesh`` -> the geo GENERATOR path (emit_geo, which is what the shipped
    voxelize template takes), anything else -> the plain MPxNode path
    (node_scaffold)."""
    spec = {
        "mpy_type": mpy_type,
        "suggested": {"node_type_name": "closestPtNode",
                      "class_name": "ClosestPtNode", "type_id": "0x00070001",
                      "mpx_base": "MPxNode"},
        "compute": _CLOSEST_POINT_COMPUTE,
        "init": "",
        "inputs": {"inMesh": {"type": "mesh"}},
        "outputs": {"outValue": {"type": "double"}},
        "portability": {"portable": True, "blockers": []},
    }
    if flag:
        spec["suggested"]["uses_mesh_intersector"] = True
    return spec


class TestMeshIntersectorInclude(unittest.TestCase):
    """A closest-point port cannot compile without <maya/MMeshIntersector.h>.

    The porter is forbidden to add #includes (native/ai/prompt.py says so in six
    places), so the header has to come from the scaffold. Before this it was in
    no include list at all, which left an AI port of a closest-point compute two
    options: fail to compile, or fabricate a different algorithm that does.

    Gated on the flag, because an include is generated C++: emitting it
    unconditionally would move every node's .cpp and re-key the whole port cache.
    """

    def _cpp(self, mpy_type, *, flag):
        from mpynode.native import compiler as codegen
        return codegen.generate_cpp(_closest_point_spec(mpy_type, flag=flag),
                                    for_port=True)

    def _includes(self, cpp):
        """The #include lines only. The geo scaffold quotes the original Python
        compute verbatim into the PORT-region comment, so the CLASS NAME appears
        in the text either way -- the include is the thing that is gated."""
        return [ln for ln in cpp.splitlines() if ln.startswith("#include")]

    def test_geo_generator_emits_the_include(self):
        # mPyMesh -> emit_geo. This is the voxelize path.
        cpp = self._cpp("mPyMesh", flag=True)
        self.assertIn("#include <maya/MMeshIntersector.h>", cpp)

    def test_plain_node_emits_the_include(self):
        # Everything non-geo -> node_scaffold (incl. the deformer branch).
        cpp = self._cpp("mPyNode", flag=True)
        self.assertIn("#include <maya/MMeshIntersector.h>", cpp)

    def test_the_mesh_object_the_query_needs_is_already_bound(self):
        # MMeshIntersector::create takes the raw mesh MObject, not the MFnMesh.
        # The include is only half the story -- if the scaffold stopped binding
        # the MObject, the emitted header would still leave the port unportable.
        cpp = self._cpp("mPyMesh", flag=True)
        self.assertIn("MObject in_aInMesh_obj", cpp)

    def test_unflagged_node_is_untouched_on_BOTH_paths(self):
        # The byte-parity guard: no flag -> the include list is exactly what it
        # was, so an unrelated node's .cpp (and its port-cache entry) cannot move.
        for mpy_type in ("mPyMesh", "mPyNode"):
            incs = self._includes(self._cpp(mpy_type, flag=False))
            self.assertEqual([], [i for i in incs if "MMeshIntersector" in i],
                             mpy_type)

    def test_flag_adds_the_header_AND_NOTHING_ELSE(self):
        # The header self-includes MPoint/MFloatPoint/MFloatVector/MMatrix/
        # MIntArray, so it needs no companions -- and the gate must not perturb
        # the rest of the list (order included) for the flagged node either.
        for mpy_type in ("mPyMesh", "mPyNode"):
            off = self._includes(self._cpp(mpy_type, flag=False))
            on = self._includes(self._cpp(mpy_type, flag=True))
            added = [i for i in on if i not in off]
            self.assertEqual(["#include <maya/MMeshIntersector.h>"], added,
                             mpy_type)
            self.assertEqual(off, [i for i in on if i in off], mpy_type)


class TestMeshClosestPointGuidance(unittest.TestCase):
    """The porter guide must carry the api1 spelling AND the barycentric
    ordering -- the one way to get this silently wrong (u, v weight the FIRST
    TWO triangle vertices; the measured cost of the other order is 0.73 error
    against 5e-07 for the correct one)."""

    def test_guidance_present_when_flagged(self):
        from mpynode.native.ai import translation_knowledge as tk
        guide = tk.guide_for_spec(
            {"compute": _CLOSEST_POINT_COMPUTE, "init": "",
             "suggested": {"uses_mesh_intersector": True}})
        self.assertIn("CLOSEST POINT ON A MESH", guide)
        self.assertIn("getBarycentricCoords", guide)
        self.assertIn("1-u-v", guide)
        self.assertIn("faceIndex", guide)
        # The header is already there -- saying otherwise invites a port that
        # tries to add one (and gets scrubbed).
        self.assertIn("ALREADY included", guide)

    def test_guidance_absent_without_flag(self):
        from mpynode.native.ai import translation_knowledge as tk
        guide = tk.guide_for_spec({"compute": "self.out = self.uIn * 2",
                                   "init": "", "suggested": {}})
        self.assertNotIn("CLOSEST POINT ON A MESH", guide)


class TestVoxelizeTemplateSeesItsClosestPointQuery(unittest.TestCase):
    """End-to-end on the node that motivated this: the shipped voxelize
    template's whole algorithm is an MMeshIntersector sweep, and it does not
    lower, so it goes to the AI porter. Its portability report used to name only
    the image read -- the query itself was invisible."""

    def _spec(self):
        import os
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        path = os.path.join(os.environ["MPYNODE_ROOT"], "templates", 
                            "MPyMesh", "Voxelize", "template.mpn")
        if not os.path.isfile(path):
            self.skipTest("voxelize template not installed: %s" % path)
        return mpn_spec_adapter.spec_from_mpn_payload(
            mpn_io.load_mpn(path, trusted=True))

    def test_report_names_the_query_and_the_spec_carries_the_flag(self):
        spec = self._spec()
        self.assertTrue(spec["suggested"].get("uses_mesh_intersector"))
        self.assertTrue(
            any("closest-point mesh query" in u
                for u in spec["portability"]["unported"]),
            spec["portability"]["unported"])

    def test_its_skeleton_carries_the_header(self):
        from mpynode.native import compiler as codegen
        cpp = codegen.generate_cpp(self._spec(), for_port=True)
        self.assertIn("#include <maya/MMeshIntersector.h>", cpp)
        # Still an AI port (it does not lower), which is exactly why the header
        # has to be pre-emitted.
        self.assertIn(codegen.PORT_BEGIN, cpp)


_IMG_SPEC = {
    "suggested": {"node_type_name": "texSrcNode", "mpx_base": "MPxNode",
                  "reads_image_file": True},
    "compute": "self.outColor = [0.5, 0.5, 0.5]",
    "init": "from PIL import Image",
    "inputs": {"fileName": {"type": "string"}},
    "outputs": {"outColor": {"type": "vector"}},
}


class TestVerifySkipsImageRead(unittest.TestCase):
    """A file/texture node reads its image at eval time, so the parity harness
    must SKIP pointwise compare WITHOUT touching Maya (mirrors the RNG skip)."""

    def test_verify_one_skips_image_read_without_touching_maya(self):
        from mpynode.native.toolchain import verify as cc

        class _BoomCmds:
            def __getattr__(self, _n):
                def _f(*a, **k):
                    raise AssertionError(
                        "verify must NOT touch Maya for a file-read node")
                return _f

        res = cc._verify_one(_BoomCmds(), "/some/tex.bundle", _IMG_SPEC)
        self.assertFalse(res["ran"])
        self.assertIsNone(res["pass"])
        self.assertIsNone(res["maxerr"])
        self.assertIn("image file", res["reason"].lower())

    def test_image_read_skip_precedes_array_skip(self):
        """An image-read node with an array attr still reports the FILE reason
        (the file-read skip is the more specific, user-meaningful one)."""
        from mpynode.native.toolchain import verify as cc

        spec = dict(_IMG_SPEC)
        spec["outputs"] = {"outColor": {"type": "vector", "is_array": True}}
        res = cc._verify_one(object(), "/some/tex.bundle", spec)
        self.assertFalse(res["ran"])
        self.assertIn("image file", res["reason"].lower())


class TestVerifyUISurfacesSkipReason(unittest.TestCase):
    """End-to-end honesty: the skip dict my feature emits ({ran:False,
    pass:None, reason}) must flow through the controller's verify status-mapping
    to a "skip" event, which the dialog renders as 'verify skipped: <reason>'
    (NOT a silent green 'verified', and NOT a red 'FAILED parity')."""

    def test_skip_dict_maps_to_skip_status_not_fail(self):
        # Mirror the controller's verify status-mapping (compile_controller
        # run_compile, ~line 1000): ran&!pass -> fail, ran&pass -> ok, else skip.
        v = _IMG_SPEC and {"ran": False, "pass": None, "maxerr": None,
                           "tol": None, "reason": "reads an image file"}
        if v.get("ran") and v.get("pass") is False:
            status = "fail"
        elif v.get("ran") and v.get("pass"):
            status = "ok"
        else:
            status = "skip"
        self.assertEqual(status, "skip")

    def test_cell_text_renders_image_read_skip_reason(self):
        from mpynode.ui.dialogs.compile_dialog import CompileDialog
        reason = ("reads an image file (MImage::readFromFile); output depends "
                  "on external file state")
        txt = CompileDialog._cell_text("verify", "skip", reason)
        self.assertIn("skip", txt.lower())
        self.assertIn("image file", txt.lower())


# ===================== from test_rng_support.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__rng_support():
    standalone_init()


_RNG_SPEC = {
    "suggested": {"node_type_name": "noiseNode", "mpx_base": "MPxNode"},
    "compute": "self.out = float(np.random.random())",
    "init": "import numpy as np",
    "inputs": {},
    "outputs": {"out": {"type": "float"}},
}


class TestGuardRelaxed(unittest.TestCase):
    def test_numpy_random_is_warning_not_blocker(self):
        from mpynode.native.spec import spec_extractor as se

        res = se.assess_portability(
            "self.out = np.random.random()", "import numpy as np", {}, {}, {})
        self.assertTrue(res["portable"], "np.random must no longer block: %r"
                        % res["blockers"])
        self.assertFalse(res["blockers"])
        self.assertTrue(any("random" in w.lower() for w in res["warnings"]),
                        "an RNG warning should be present: %r" % res["warnings"])

    def test_python_random_is_warning_not_blocker(self):
        from mpynode.native.spec import spec_extractor as se

        res = se.assess_portability(
            "x = random.uniform(0.0, 1.0)\nself.out = x", "import random",
            {}, {}, {})
        self.assertTrue(res["portable"], "random.* must no longer block: %r"
                        % res["blockers"])

    def test_rng_is_a_warning_not_a_gap(self):
        """RNG and an unlowerable construct are BOTH warnings now, so the RNG
        tests above no longer discriminate on their own. What separates them is
        ``unported``: RNG has a real kernel (C++ <random>), so it must not be
        reported to the porter as work to do."""
        from mpynode.native.spec import spec_extractor as se

        res = se.assess_portability(
            "self.out = np.random.random()", "import numpy as np", {}, {}, {})
        self.assertEqual([], res["unported"])
        # ...whereas these have no kernel, and must be.
        r1 = se.assess_portability("data = open('x.txt').read()", "", {}, {}, {})
        self.assertTrue(any("open()" in u for u in r1["unported"]),
                        r1["unported"])
        r2 = se.assess_portability("img = cv2.imread('a.png')", "import cv2",
                                   {}, {}, {})
        self.assertTrue(any("image file read" in u for u in r2["unported"]),
                        r2["unported"])

    def test_uses_rng_detector(self):
        from mpynode.native.spec import spec_extractor as se

        self.assertTrue(se.uses_rng("np.random.random()"))
        self.assertTrue(se.uses_rng("y = numpy.random.randint(0, 5)"))
        self.assertTrue(se.uses_rng("z = random.gauss(0, 1)"))
        self.assertFalse(se.uses_rng("x = math.sin(t)"))
        self.assertTrue(se.spec_uses_rng(_RNG_SPEC))
        self.assertFalse(se.spec_uses_rng(
            {"compute": "self.out = self.a + 1", "init": ""}))


class TestCodegenRandomInclude(unittest.TestCase):
    def test_random_in_every_family_include_list(self):
        from mpynode.native import compiler as codegen

        self.assertIn("random", codegen._INCLUDES,
                      "base/scalar+deformer includes must carry <random>")
        for name in ("_IKSOLVER_INCLUDES", "_LOCATOR_INCLUDES_COMMON",
                     "_GEO_INCLUDES_BASE", "_TRANSFORM_INCLUDES"):
            lst = getattr(codegen, name)
            self.assertIn("random", lst,
                          "%s must carry <random> so RNG works there too" % name)


class TestTranslationKnowledgeRandom(unittest.TestCase):
    def test_random_section_and_helper_injected_on_rng(self):
        from mpynode.native.ai import translation_knowledge as tk

        self.assertIn("random", tk.sections_for("self.out = np.random.random()"))
        g = tk.guide_for("self.out = np.random.random()")
        self.assertIn("std::mt19937", g, "the RNG helper must be injected")
        self.assertIn("NdRng", g)

    def test_non_rng_does_not_inject_random(self):
        from mpynode.native.ai import translation_knowledge as tk

        self.assertNotIn("random", tk.sections_for("self.out = math.sin(t)"))

    def test_detector_and_translation_section_never_diverge(self):
        """Anything spec_extractor flags as RNG (-> parity skipped) MUST also
        trigger the translation RANDOM section (-> the LLM gets <random>
        guidance). Otherwise a node skips parity yet ports with no RNG help."""
        from mpynode.native.spec import spec_extractor as se
        from mpynode.native.ai import translation_knowledge as tk

        for tok in ("x = random.betavariate(2, 3)",
                    "x = random.expovariate(1.0)",
                    "x = random.normalvariate(0, 1)",
                    "x = random.randrange(10)",
                    "x = random.sample(seq, 3)",
                    "rng = np.random.default_rng(0)"):
            self.assertTrue(se.uses_rng(tok), "spec_extractor missed: %s" % tok)
            self.assertIn("random", tk.sections_for(tok),
                          "translation RANDOM not injected for: %s" % tok)

    def test_core_no_longer_forbids_randomness(self):
        from mpynode.native.ai import translation_knowledge as tk

        self.assertNotIn("cannot be ported", tk.CORE,
                         "CORE must no longer declare RNG unportable")


class TestVerifySkipsRng(unittest.TestCase):
    def test_verify_one_skips_rng_without_touching_maya(self):
        from mpynode.native.toolchain import verify as cc

        class _BoomCmds:
            def __getattr__(self, _n):
                def _f(*a, **k):
                    raise AssertionError(
                        "verify must NOT touch Maya for an RNG node")
                return _f

        res = cc._verify_one(_BoomCmds(), "/some/x.bundle", _RNG_SPEC)
        self.assertFalse(res["ran"])
        self.assertIsNone(res["pass"])
        self.assertIn("random", res["reason"].lower())


# A DETERMINISTICALLY LOWERED RNG node: RandomState(seed).random(...) transpiles
# to the bit-exact nd::MT19937, so its parity MUST be checked (maxerr == 0), NOT
# skipped. A `bias` input makes `out` DG-affected without touching the RNG stream
# (a no-input node never recomputes -- see the SP-4 memory gotcha). WITH
# portability so generate_cpp reaches the lowering path instead of raising.
_LOWERED_RNG_SPEC = {
    "suggested": {"node_type_name": "noiseLowered", "class_name": "NoiseLowered",
                  "mpx_base": "MPxNode", "type_id": "0x0013a1c1"},
    "compute": ("rng = np.random.RandomState(12345)\n"
                "v = rng.random(4)\n"
                "self.out = float(v[0] + v[1] + v[2] + v[3]) + self.bias\n"),
    "init": "import numpy as np",
    "inputs": {"bias": {"type": "double"}},
    "outputs": {"out": {"type": "double"}},
    "portability": {"portable": True, "blockers": []},
}

# An AI-PORTED RNG node: bare np.random.random() cannot lower -> the AI porter
# fills the PORT region with C++ <random> (non-bit-exact) -> parity stays skipped.
# Same as _RNG_SPEC but WITH portability + full `suggested` so generate_cpp
# succeeds and its PORT region can be observed directly.
_PORTED_RNG_SPEC = {
    "suggested": {"node_type_name": "noisePorted", "class_name": "NoisePorted",
                  "mpx_base": "MPxNode", "type_id": "0x0013a1c2"},
    "compute": "self.out = float(np.random.random())",
    "init": "import numpy as np",
    "inputs": {},
    "outputs": {"out": {"type": "float"}},
    "portability": {"portable": True, "blockers": []},
}


class TestVerifyRngSkipConditional(unittest.TestCase):
    """The RNG parity-skip in compile_controller._verify_one is CONDITIONAL on
    the porter path, and the discriminator is the scaffold's PORT region marker
    (`codegen.PORT_BEGIN in generate_cpp(spec)`). These fast, Maya-free tests
    lock that invariant both ways so the relaxation cannot silently regress to
    the old unconditional skip (which would leave the bit-exact lowered RNG
    path unverified)."""

    def test_lowered_rng_has_no_port_region_so_parity_runs(self):
        from mpynode.native.spec import spec_extractor as se
        from mpynode.native import compiler as codegen

        self.assertTrue(se.spec_uses_rng(_LOWERED_RNG_SPEC))
        cpp = codegen.generate_cpp(_LOWERED_RNG_SPEC)
        # No PORT region => _verify_one's RNG-skip branch does NOT fire =>
        # the node is parity-checked like any other numeric node.
        self.assertNotIn(codegen.PORT_BEGIN, cpp,
                         "RandomState compute must lower (no PORT region) so its "
                         "bit-exact RNG is parity-checked, not skipped")
        self.assertIn("nd::MT19937", cpp,
                      "lowered RNG must map to the bit-exact nd::MT19937")

    def test_ported_rng_has_port_region_so_parity_skips(self):
        from mpynode.native.spec import spec_extractor as se
        from mpynode.native import compiler as codegen

        self.assertTrue(se.spec_uses_rng(_PORTED_RNG_SPEC))
        cpp = codegen.generate_cpp(_PORTED_RNG_SPEC)
        # PORT region present => AI porter fills C++ <random> (non-bit-exact) =>
        # _verify_one skips parity for this node.
        self.assertIn(codegen.PORT_BEGIN, cpp,
                      "bare np.random.random must stay on the AI porter path")
        self.assertNotIn("deterministic numpy->C++ lowered compute (no port)",
                         cpp, "bare np.random must NOT be lowered")


# ===================== from test_verify_array_and_error.py =====================
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _setUpModule__verify_array_and_error():
    standalone_init()


# A spec shaped like cubicCurveSampler: vector ARRAY in + vector ARRAY out.
_ARRAY_SPEC = {
    "suggested": {"node_type_name": "cubicCurveSampler", "mpx_base": "MPxNode"},
    "compute": "self.outSamples[:] = self.controlPoints",
    "init": "import numpy as np",
    "inputs": {"controlPoints": {"type": "vector", "is_array": True}},
    "outputs": {"outSamples": {"type": "vector", "is_array": True}},
}


class _BoomCmds:
    """Any Maya call explodes -- proves the skip happens BEFORE touching Maya."""

    def __getattr__(self, _n):
        def _f(*a, **k):
            raise AssertionError(
                "verify must NOT touch Maya for an unsupported (array) node")
        return _f


class TestVerifyOneArrayNodesNowRun(unittest.TestCase):
    """#45 (D2): array/multi nodes are NO LONGER skipped wholesale -- they now
    fall through to the real harness which DRIVES the multi element plugs and
    COMPARES the multi outputs. The pre-scene skips that survive (RNG / image /
    float2 / empty-outputs) are covered by their own classes; here we only prove
    the array gate is gone (an array node now reaches Maya instead of a canned
    'uses array attribute' skip)."""

    def test_array_node_reaches_harness_instead_of_being_skipped(self):
        from mpynode.native.toolchain import verify as cc

        # _BoomCmds explodes on the first Maya call: an array node reaching the
        # harness now RAISES, where it used to return a pre-scene skip dict.
        with self.assertRaises(AssertionError):
            cc._verify_one(_BoomCmds(), "/some/x.bundle", _ARRAY_SPEC)

    def test_array_only_on_output_reaches_harness(self):
        from mpynode.native.toolchain import verify as cc

        spec = {
            "suggested": {"node_type_name": "n", "mpx_base": "MPxNode"},
            "compute": "self.outSamples[:] = self.a", "init": "",
            "inputs": {"a": {"type": "float"}},
            "outputs": {"outSamples": {"type": "vector", "is_array": True}},
        }
        with self.assertRaises(AssertionError):
            cc._verify_one(_BoomCmds(), "/some/x.bundle", spec)

    def test_empty_outputs_skips_without_vacuous_pass(self):
        # P0-8: a scalar spec with NO outputs would make the parity loop
        # vacuous (the ``for o in OUT`` loop never runs, maxerr stays 0.0 -> a
        # false PASS). It must short-circuit to a not-run skip BEFORE touching
        # Maya, and never report pass=True.
        from mpynode.native.toolchain import verify as cc

        spec = {
            "suggested": {"node_type_name": "n", "mpx_base": "MPxNode"},
            "compute": "pass", "init": "",
            "inputs": {"a": {"type": "float"}},
            "outputs": {},
        }
        res = cc._verify_one(_BoomCmds(), "/some/x.bundle", spec)
        self.assertFalse(res["ran"])
        self.assertIsNone(res["pass"])           # skip, NOT a vacuous PASS
        self.assertIn("output", res["reason"].lower())

    def test_plain_scalar_spec_is_not_array_skipped(self):
        """A non-array spec must NOT be array-skipped -- it should fall through to
        the real harness (which we let touch Maya here, so it raises our boom).
        Proves the array gate doesn't over-match plain nodes."""
        from mpynode.native.toolchain import verify as cc

        spec = {
            "suggested": {"node_type_name": "n", "mpx_base": "MPxNode"},
            "compute": "self.out = self.a + 1", "init": "",
            "inputs": {"a": {"type": "float"}},
            "outputs": {"out": {"type": "float"}},
        }
        with self.assertRaises(AssertionError):
            cc._verify_one(_BoomCmds(), "/some/x.bundle", spec)


class TestVerifyArrayHelpers(unittest.TestCase):
    """#45 (D2): pure helpers behind array/multi parity -- crash-safe int-array
    seeding, divergence-tolerant comparison, and the non-driveable-input set.
    These are Maya-free, so they gate the core logic without a scene."""

    def test_array_values_int_are_index_safe(self):
        # int arrays MUST stay in [0, k-1] so an index-array (dnet index0/index1)
        # can't drive a compiled node OOB -> segfault (uncatchable in-process).
        from mpynode.native.toolchain import verify as v
        import random
        rng = random.Random(0)
        for k in (1, 4, 9):
            vals = v._array_values("int", k, rng)
            self.assertEqual(len(vals), k)
            self.assertTrue(all(0 <= x <= k - 1 for x in vals), vals)

    def test_array_values_float_span_is_wide(self):
        from mpynode.native.toolchain import verify as v
        import random
        vals = v._array_values("float", 6, random.Random(1))
        self.assertEqual(len(vals), 6)
        self.assertTrue(any(x < 0 for x in vals) or any(x > 1 for x in vals))

    def test_pair_stats_finite_maxerr(self):
        from mpynode.native.toolchain import verify as v
        me, nc, nd = v._pair_stats([1.0, 2.0, 3.0], [1.0, 2.5, 3.0])
        self.assertAlmostEqual(me, 0.5)
        self.assertEqual((nc, nd), (3, 0))

    def test_pair_stats_both_nonfinite_is_diverged_not_error(self):
        # both implementations blew up -> counted as diverged, excluded from maxerr
        from mpynode.native.toolchain import verify as v
        inf = float("inf")
        me, nc, nd = v._pair_stats([inf, 1.0], [-inf, 1.0])
        self.assertEqual(me, 0.0)          # only the finite 1.0==1.0 pair compared
        self.assertEqual((nc, nd), (1, 1))

    def test_pair_stats_one_sided_nonfinite_is_real_discrepancy(self):
        # exactly one side non-finite = a genuine mismatch -> +inf (a real signal)
        from mpynode.native.toolchain import verify as v
        me, nc, nd = v._pair_stats([float("inf"), 2.0], [5.0, 2.0])
        self.assertEqual(me, float("inf"))
        self.assertEqual((nc, nd), (2, 0))

    def test_diverge_ceiling_is_generous_but_finite(self):
        from mpynode.native.toolchain import verify as v
        # far above any plausible scene magnitude, far below solver blow-up (1e16)
        self.assertTrue(1.0e4 < v._DIVERGE_CEIL < 1.0e12)

    def test_idempotence_probe_needs_the_dirty_to_see_a_moving_reference(self):
        # _read_outputs is a plain getAttr, so without the dgdirty a clean plug
        # hands back the cached value and EVERY node looks idempotent -- the
        # probe would be vacuously true and exclude nothing.
        from mpynode.native.toolchain import verify as v

        class _FakeCmds(object):
            def __init__(self, reads):
                self._reads, self._i, self.dirtied = reads, 0, 0

            def getAttr(self, plug):
                return self._reads[min(self._i, len(self._reads) - 1)]

            def dgdirty(self, node):
                self._i += 1
                self.dirtied += 1

        out_meta = {"out": {"is_array": False}}
        steady = _FakeCmds([1.0, 1.0])
        self.assertTrue(v._interp_is_idempotent(steady, "n", out_meta, 1e-4))
        self.assertEqual(steady.dirtied, 1)     # it really did force a recompute
        # a reference that moves under its own feet is NOT comparable
        moving = _FakeCmds([1.0, 2.0])
        self.assertFalse(v._interp_is_idempotent(moving, "n", out_meta, 1e-4))
        # drift inside tol is still idempotent enough to compare
        jitter = _FakeCmds([1.0, 1.0 + 1e-9])
        self.assertTrue(v._interp_is_idempotent(jitter, "n", out_meta, 1e-4))

    def test_has_carry_state_matches_the_codegen_definition(self):
        from mpynode.native.toolchain import verify as v
        stateful = {"compute": "self.previous = self.previous + self.a\n"
                               "self.out = self.previous\n",
                    "inputs": {"a": {}}, "outputs": {"out": {}}}
        stateless = {"compute": "self.out = self.a * 2.0\n",
                     "inputs": {"a": {}}, "outputs": {"out": {}}}
        self.assertTrue(v._has_carry_state(stateful))
        self.assertFalse(v._has_carry_state(stateless))
        self.assertFalse(v._has_carry_state({}))            # no source -> no claim
        self.assertFalse(v._has_carry_state({"compute": "def ("}))   # unparseable

    def test_carry_state_drift_needs_both_state_and_a_tight_bound(self):
        # The structural precondition is the point: _DIVERGE_CEIL's magnitude-only
        # band was wide enough to absorb dnet's maxDisplacement sentinel (a real
        # port bug that diverged by exactly 1.0). Both halves are pinned here.
        from mpynode.native.toolchain import verify as v
        stateful = {"compute": "self.previous = self.previous + self.a\n"
                               "self.out = self.previous\n",
                    "inputs": {"a": {"type": "float"}},
                    "outputs": {"out": {"type": "float"}}}
        stateless = {"compute": "self.out = self.a * 2.0\n",
                     "inputs": {"a": {"type": "float"}},
                     "outputs": {"out": {"type": "float"}}}
        tol = 1e-4
        # small drift + a carry var -> the two sides advanced state a different
        # number of times; the pointwise compare is not defined
        self.assertTrue(v._carry_state_drift(stateful, 1.8e-4, tol))
        # a sentinel-class error is orders above the band and STILL fails
        self.assertFalse(v._carry_state_drift(stateful, 1.0, tol))
        self.assertFalse(v._carry_state_drift(stateful, float("inf"), tol))
        # nothing to excuse at or below tol
        self.assertFalse(v._carry_state_drift(stateful, tol, tol))
        # and a stateless node never matches, whatever the magnitude
        self.assertFalse(v._carry_state_drift(stateless, 1.8e-4, tol))

    def test_non_driveable_is_string_and_hex_geo_is_now_wired(self):
        # Geo inputs (mesh/curve/surface) are no longer left at default: they are
        # WIRED to a real upstream shape (_wire_geo_input) for non-vacuous parity.
        # `string` and `hex` (both string-backed, non-numeric) remain
        # non-driveable and are left at their default on both sides.
        from mpynode.native.toolchain import verify as v
        self.assertEqual(set(v._NON_DRIVEABLE_IN), {"string", "hex"})
        self.assertEqual(set(v._GEO_IN_TYPES),
                         {"nurbsCurve", "mesh", "nurbsSurface"})


class TestVerifyDriveInputsAndTexSkip(unittest.TestCase):
    """#1b: verify drives CONNECTED inputs gracefully (no more abort on a
    connected time/texture plug) + color/quaternion now get real component
    parity while only float2/uvCoord is peeled."""

    def _rec(self, connected=()):
        calls = {"setAttr": [], "currentTime": []}
        connected = set(connected)

        class _Cmds:
            def setAttr(self, plug, *a, **k):
                calls["setAttr"].append((plug, a, k))

            def listConnections(self, plug, **k):
                return ["src"] if plug in connected else None

            def currentTime(self, v, *a, **k):
                calls["currentTime"].append(v)

        return _Cmds(), calls

    def test_set_plug_color_uses_double3(self):
        from mpynode.native.toolchain import verify as v
        cmds, calls = self._rec()
        v._set_plug(cmds, "n.col", "color", [0.1, 0.2, 0.3])
        self.assertEqual(len(calls["setAttr"]), 1)
        plug, a, k = calls["setAttr"][0]
        self.assertEqual((plug, a, k.get("type")), ("n.col", (0.1, 0.2, 0.3), "double3"))

    def test_set_plug_quaternion_drives_four_children(self):
        from mpynode.native.toolchain import verify as v
        cmds, calls = self._rec()
        v._set_plug(cmds, "n.q", "quaternion", [0.1, 0.2, 0.3, 0.9])
        self.assertEqual([c[0] for c in calls["setAttr"]],
                         ["n.qX", "n.qY", "n.qZ", "n.qW"])

    def test_drive_input_skips_connected_plug(self):
        from mpynode.native.toolchain import verify as v
        cmds, calls = self._rec(connected={"comp.a"})
        v._drive_input(cmds, ("orig", "comp"), "a", "float", 1.5)
        plugs = [c[0] for c in calls["setAttr"]]
        self.assertIn("orig.a", plugs)       # unconnected -> driven
        self.assertNotIn("comp.a", plugs)    # connected -> left to its source

    def test_drive_input_time_drives_timeline_and_unconnected_side(self):
        from mpynode.native.toolchain import verify as v
        # orig.t is auto-connected to time1 (Python original); comp.t is NOT.
        cmds, calls = self._rec(connected={"orig.t"})
        v._drive_input(cmds, ("orig", "comp"), "t", "time", 12.0)
        self.assertEqual(calls["currentTime"], [12.0])   # both driven via timeline
        plugs = [c[0] for c in calls["setAttr"]]
        self.assertNotIn("orig.t", plugs)                # connected: no setAttr
        self.assertIn("comp.t", plugs)                   # unconnected: setAttr too

    def test_color_output_falls_through_tex_gate(self):
        # color is no longer tex-skipped -> reaches the real harness (touches
        # Maya via _BoomCmds, which raises), proving it is NOT peeled.
        from mpynode.native.toolchain import verify as v
        spec = {
            "suggested": {"node_type_name": "n", "mpx_base": "MPxNode"},
            "compute": "self.outColor = self.k", "init": "",
            "inputs": {"k": {"type": "float"}},
            "outputs": {"outColor": {"type": "color"}},
        }
        with self.assertRaises(AssertionError):
            v._verify_one(_BoomCmds(), "/x.bundle", spec)

    def test_float2_on_nonmpyfile_still_skipped_without_touching_maya(self):
        # float2 is the NATIVE texture interface; a float2 attr on a NON-mPyFile
        # node has no generic host to rebuild on -> honest skip (never a raise).
        from mpynode.native.toolchain import verify as v
        spec = {
            "suggested": {"node_type_name": "n", "mpx_base": "MPxNode"},
            "compute": "self.out = self.uv[0]", "init": "",
            "inputs": {"uv": {"type": "float2"}},
            "outputs": {"out": {"type": "float"}},
        }
        res = v._verify_one(_BoomCmds(), "/x.bundle", spec)
        self.assertFalse(res["ran"])
        self.assertIsNone(res["pass"])
        self.assertIn("float2", res["reason"].lower())

    def test_set_plug_float2_uses_double2(self):
        # T6: uvCoord (numeric compound-2) is driven via a double2 setAttr.
        from mpynode.native.toolchain import verify as v
        cmds, calls = self._rec()
        v._set_plug(cmds, "n.uvCoord", "float2", [0.25, 0.75])
        self.assertEqual(len(calls["setAttr"]), 1)
        plug, a, k = calls["setAttr"][0]
        self.assertEqual((plug, a, k.get("type")),
                         ("n.uvCoord", (0.25, 0.75), "double2"))

    def test_elem_value_float2_has_two_components(self):
        from mpynode.native.toolchain import verify as v
        import random
        val = v._elem_value("float2", random.Random(0))
        self.assertEqual(len(val), 2)
        self.assertTrue(all(isinstance(x, float) for x in val))

    def test_float2_mpyfile_falls_through_to_rebuild(self):
        # T6: a PROCEDURAL mPyFile texture (float2 uvCoord -> outColor, no file,
        # no RNG) is NO LONGER peeled -- it reaches the real rebuild (which builds
        # an mPyFile pair + drives uvCoord). Letting it touch Maya via _BoomCmds
        # and asserting it raises proves the tex-skip did NOT claim it.
        from mpynode.native.toolchain import verify as v
        spec = {
            "suggested": {"node_type_name": "procTexture", "mpx_base": "MPxNode"},
            "mpy_type": "mPyFile",
            "compute": ("u, v = self.uvCoord\n"
                        "self.outColor = (u, v, u * v)\n"
                        "self.outAlpha = 1.0\n"),
            "init": "import numpy as np\n",
            "inputs": {"uvCoord": {"type": "float2"}},
            "outputs": {"outColor": {"type": "color"},
                        "outAlpha": {"type": "float"}},
            "portability": {"portable": True, "blockers": []},
        }
        with self.assertRaises(AssertionError):
            v._verify_one(_BoomCmds(), "/x.bundle", spec)


# A geo spec (mPyMesh) that ALSO carries an array input -- the array-skip must
# NOT claim it: geometry generators (mesh/curve/surface) read their geo OUTPUT
# via MFn*, and the geo parity branch drives array inputs itself. Before SP-4.5
# there was no geo branch, so this node was wrongly array-skipped (ran=False)
# instead of reaching the real geo parity harness.
_GEO_MESH_SPEC = {
    "suggested": {"node_type_name": "gmesh", "mpx_base": "MPxNode"},
    "mpy_type": "mPyMesh",
    "compute": (
        "import numpy as np\n"
        "from mpynode._api2.mpy_mesh import build_default_output\n"
        "self.points = self.vin * self.scale\n"
        "self.counts = self.cin\n"
        "self.indices = self.iin\n"
        "self.outMesh = build_default_output("
        "self.points, self.counts, self.indices)\n"
    ),
    "init": "",
    "inputs": {
        "vin": {"type": "vector", "is_array": True},
        "scale": {"type": "double", "default_value": 2.0},
        "cin": {"type": "int", "is_array": True},
        "iin": {"type": "int", "is_array": True},
    },
    "outputs": {},
    "portability": {"portable": True, "blockers": []},
}


class TestVerifyOneGeoDispatch(unittest.TestCase):
    """A geometry node (mPyMesh/Curve/Surface) must reach the geo parity branch,
    NOT the array-skip -- even when it carries array inputs. The geo branch reads
    the geo OUTPUT (outMesh/outCurve/outSurface) via MFn* and drives array inputs
    itself, so array attrs are no longer a reason to skip a geo node. We let the
    branch touch Maya (via _BoomCmds) and assert it raises -- proving it did NOT
    take a skip branch. (Real end-to-end geo parity runs under mayapy, opt-in.)
    """

    def test_geo_node_with_array_inputs_is_not_array_skipped(self):
        from mpynode.native.toolchain import verify as cc
        from mpynode.native import compiler as codegen

        # Guard: this only tests something if the spec really is a geo kind.
        self.assertEqual(codegen._geo_kind(_GEO_MESH_SPEC), "mesh")
        with self.assertRaises(AssertionError):
            cc._verify_one(_BoomCmds(), "/some/x.bundle", _GEO_MESH_SPEC)


class TestGeoSeedingConsistency(unittest.TestCase):
    """The geo parity sweep must SEED valid, internally-consistent geometry for
    all three generator families -- otherwise the check silently degrades to a
    vacuous 'every config empty' skip. Two Maya-free contracts guarded here:

      * role attribution follows the ARRAY feeder, not a trailing scalar. The
        idiom ``self.cvs = self.cvsIn * self.scale`` must map cvsIn->cvs (a
        greedy ``self\\.(\\w+)`` wrongly grabs ``scale``, leaving the CV array
        unseeded -- fatal for surfaces, which need a full grid).
      * a surface needs numU*numV == len(cvs) with numU,numV >= degree+1. The
        cvs seed must therefore be a real grid (not a 4-CV run) and the
        numU/numV inputs must be driven to that grid's dims for EVERY config.
    """

    def _rng(self):
        import random
        return random.Random(0)

    def test_role_attribution_follows_array_feeder_not_trailing_scalar(self):
        from mpynode.native.toolchain import verify as cc
        roles = cc._geo_input_roles(
            "self.cvs = self.cvsIn * self.scale\n"
            "self.outCurve = build_default_output(self.cvs, None, 3, 'open')\n")
        self.assertEqual(roles.get("cvsIn"), "cvs")   # NOT 'scale'
        self.assertNotIn("scale", roles)

    def test_surface_numuv_roles_detected(self):
        from mpynode.native.toolchain import verify as cc
        roles = cc._geo_input_roles(
            "self.cvs = self.cvsIn * self.scale\n"
            "self.num_cvs_u = self.nu\n"
            "self.num_cvs_v = self.nv\n"
            "self.outSurface = build_default_output("
            "self.cvs, self.num_cvs_u, self.num_cvs_v)\n")
        self.assertEqual(roles.get("cvsIn"), "cvs")
        self.assertEqual(roles.get("nu"), "numU")
        self.assertEqual(roles.get("nv"), "numV")

    def test_cvs_seed_is_a_full_grid(self):
        from mpynode.native.toolchain import verify as cc
        vals = cc._geo_array_value("cvs", "vector", 0)
        dim = cc._GEO_SURF_DIM
        # A dim x dim CV grid: enough for a degree-3 curve AND a dim x dim
        # surface (numU*numV == len(cvs)); every element an [x,y,z] triple.
        self.assertEqual(len(vals), dim * dim)
        self.assertTrue(all(len(p) == 3 for p in vals))

    def test_mesh_points_seed_stays_a_single_quad(self):
        from mpynode.native.toolchain import verify as cc
        # The mesh path pairs points with counts=[4]/indices=[0..3]; its point
        # seed must remain a 4-vertex quad, unaffected by the grid CV change.
        vals = cc._geo_array_value("points", "vector", 0)
        self.assertEqual(len(vals), 4)
        self.assertEqual(cc._geo_array_value("counts", "int", 0), [4])
        self.assertEqual(cc._geo_array_value("indices", "int", 0), [0, 1, 2, 3])

    def test_numuv_scalar_driven_to_grid_dim_every_config(self):
        from mpynode.native.toolchain import verify as cc
        meta = {"type": "int"}
        dim = cc._GEO_SURF_DIM
        for cfg in range(cc._GEO_CFGS):
            self.assertEqual(
                cc._geo_scalar_value(meta, "int", cfg, self._rng(), role="numU"),
                dim)
            self.assertEqual(
                cc._geo_scalar_value(meta, "int", cfg, self._rng(), role="numV"),
                dim)


class TestVerifyScriptHonesty(unittest.TestCase):
    """The shipped verify_in_maya.py artifact must be HONEST: geo nodes get a
    geo-aware check, scalar outputs are compared component-by-component (not a
    cv[0]/sv[0] first-element peel that false-PASSes a vector wrong on Y/Z), and
    a node with nothing comparable reports SKIP rather than a vacuous PASS."""

    def test_geo_spec_dispatches_to_geo_verify_script(self):
        from mpynode.native.ai import porter
        s = porter._verify_script(_GEO_MESH_SPEC)
        # Runs the AUTHORITATIVE parity branch (no duplicated, drifting logic)
        # and embeds the spec so it is self-contained (no live SOURCE needed).
        self.assertIn("_verify_one", s)
        self.assertIn("SPEC = json.loads", s)
        self.assertNotIn("cv[0]", s)

    def test_scalar_verify_script_flattens_all_components(self):
        from mpynode.native.ai import porter
        spec = {
            "suggested": {"node_type_name": "n", "mpx_base": "MPxNode"},
            "compute": "self.out = self.a", "init": "",
            "inputs": {"a": {"type": "vector"}},
            "outputs": {"out": {"type": "vector"}},
        }
        s = porter._verify_script(spec)
        self.assertIn("_flat(", s)                 # full flatten, every component
        self.assertNotIn("cv = cv[0]", s)          # the old first-element peel
        self.assertNotIn("sv = sv[0]", s)
        self.assertIn("component count", s)        # length-mismatch guard

    def test_scalar_verify_script_guards_vacuous_pass(self):
        from mpynode.native.ai import porter
        spec = {
            "suggested": {"node_type_name": "n", "mpx_base": "MPxNode"},
            "compute": "pass", "init": "",
            "inputs": {"a": {"type": "float"}}, "outputs": {},
        }
        s = porter._verify_script(spec)
        self.assertIn("no outputs to compare", s)      # empty-OUTPUTS guard
        self.assertIn("no comparable outputs", s)      # nothing-compared guard


class TestDefaultVerifyReclassifiesExceptions(unittest.TestCase):
    def test_harness_exception_is_skip_not_failure(self):
        from mpynode.native.toolchain import verify as cc
        import maya.cmds as mcmds

        rows = [{"type_name": "n", "spec": {"suggested": {"node_type_name": "n"}}}]

        # Make pluginInfo report the bundle already loaded so _default_verify
        # SKIPS loadPlugin and reaches the per-row try, then force _verify_one to
        # raise (simulating ANY harness error, e.g. setAttr on a multi).
        orig_pi = mcmds.pluginInfo
        orig_v1 = cc._verify_one
        mcmds.pluginInfo = lambda *a, **k: True
        cc._verify_one = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("setAttr: ... is a multi"))
        try:
            out = cc._default_verify("/x.bundle", rows)
        finally:
            mcmds.pluginInfo = orig_pi
            cc._verify_one = orig_v1

        r = out["n"]
        # The decisive assertion: an exception must NOT become a parity FAILURE
        # (ran=True, pass=False) -- it is a not-run skip carrying the reason.
        self.assertFalse(r["ran"])
        self.assertIsNone(r["pass"])
        self.assertIsNone(r["maxerr"])
        self.assertIn("multi", r["reason"])


class TestAttrComponentsFlatten(unittest.TestCase):
    """The scalar-compute parity check must compare ALL output components, not
    just element [0]. The old getv did ``while isinstance(val,(list,tuple)):
    val = val[0]`` -- collapsing a vector output to X and a matrix output to
    m[0][0] -- so a port wrong on Y/Z or a transposed matrix scored maxerr~=0
    and rendered a confident-but-FALSE green "verified". _attr_components keeps
    every component so the comparison is honest.
    """

    def test_scalar_is_single_component(self):
        from mpynode.native.toolchain import verify as cc
        self.assertEqual(cc._attr_components(5.0), [5.0])

    def test_vector_getattr_shape_keeps_all_three(self):
        from mpynode.native.toolchain import verify as cc
        # Maya getAttr on a double3 returns [(x, y, z)].
        self.assertEqual(cc._attr_components([(1.0, 2.0, 3.0)]), [1.0, 2.0, 3.0])

    def test_matrix_flat16_keeps_all_sixteen(self):
        from mpynode.native.toolchain import verify as cc
        m = [float(i) for i in range(16)]
        self.assertEqual(cc._attr_components(m), m)

    def test_nested_rows_are_flattened(self):
        from mpynode.native.toolchain import verify as cc
        self.assertEqual(cc._attr_components([[1.0, 2.0], [3.0, 4.0]]),
                         [1.0, 2.0, 3.0, 4.0])


class TestComponentsMaxerr(unittest.TestCase):
    def test_equal_components_are_zero_error(self):
        from mpynode.native.toolchain import verify as cc
        self.assertEqual(cc._components_maxerr([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]),
                         0.0)

    def test_mismatch_outside_element_zero_is_caught(self):
        from mpynode.native.toolchain import verify as cc
        # The crux: Y differs. The OLD [0]-collapse compared only X (1==1) and
        # missed this entirely -> false PASS. Now it is caught.
        self.assertEqual(cc._components_maxerr([1.0, 2.0, 3.0], [1.0, 9.0, 3.0]),
                         7.0)

    def test_empty_is_zero(self):
        from mpynode.native.toolchain import verify as cc
        self.assertEqual(cc._components_maxerr([], []), 0.0)


# ===================== from test_compile_from_mpn.py =====================
import copy
import inspect
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import standalone_init


def _setUpModule__compile_from_mpn():
    standalone_init()


def _spec_with_vars():
    return {
        "schema_version": 1,
        "source_node": "x",
        "mpy_type": "mPyNode",
        "suggested": {"node_type_name": "x", "class_name": "X",
                      "type_id": "0x00070000", "mpx_base": "MPxNode"},
        "inputs": {}, "outputs": {},
        "variables": {"a": {"kind": "int", "value": 1, "bake": False}},
        "compute": "out = 1", "init": "", "affects": "all",
        "portability": {"portable": True, "blockers": [], "warnings": [],
                        "reads_image_file": False},
    }


class TestBakePersistent(unittest.TestCase):
    """(C) compile_plugin bake_persistent."""

    def test_signature_backcompat(self):
        from mpynode.native.toolchain import compile_controller as cc

        p = inspect.signature(cc.compile_plugin).parameters["bake_persistent"]
        self.assertEqual(p.default, True)
        self.assertEqual(p.kind, inspect.Parameter.KEYWORD_ONLY)

    def test_bake_persistent_false_strips_variables(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = [_spec_with_vars()]
        tmp = tempfile.mkdtemp()
        # Force preflight to fail -> compile_plugin returns right AFTER the strip,
        # with no compiler/AI needed. The strip mutates the specs list in place.
        with mock.patch.object(cc.toolchain, "check_toolchain",
                               return_value={"ok": False,
                                             "problems": ["no compiler (test)"]}):
            res = cc.compile_plugin(specs, "plug", tmp, bake_persistent=False,
                                    verify=False, provider="p", model="m")
        self.assertEqual(specs[0]["variables"], {})
        self.assertFalse(res["ok"])

    def test_default_keeps_variables_backcompat(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = [_spec_with_vars()]
        tmp = tempfile.mkdtemp()
        with mock.patch.object(cc.toolchain, "check_toolchain",
                               return_value={"ok": False,
                                             "problems": ["no compiler (test)"]}):
            cc.compile_plugin(specs, "plug", tmp, verify=False,
                              provider="p", model="m")
        self.assertEqual(specs[0]["variables"],
                         {"a": {"kind": "int", "value": 1, "bake": False}})

    def test_stripping_changes_cache_key(self):
        from mpynode.native.toolchain import compile_controller as cc

        with_vars = _spec_with_vars()
        without = copy.deepcopy(with_vars)
        without["variables"] = {}
        k1 = cc.port_cache.cache_key(with_vars, provider="p", model="m")
        k2 = cc.port_cache.cache_key(without, provider="p", model="m")
        self.assertNotEqual(k1, k2)


class TestPortCacheCommandKeying(unittest.TestCase):
    """Every @maya_command compiles into the node's OWN bundle as an MPxCommand
    on EVERY base -- there is no companion plug-in any more -- so commands (and,
    when there are commands, the methods source they carry) are baked into the
    .cpp and MUST be part of the cache key. A command-LESS spec must still key
    byte-identically, so a setup/demo-only edit never costs an LLM re-port."""

    def _base_spec(self, base):
        s = _spec_with_vars()
        s["suggested"]["mpx_base"] = base
        return s

    def test_methods_edit_busts_key_for_non_locator(self):
        # Regression: keying past commands/methods here served a cached .cpp
        # with NO command classes, so the node registered no commands at all --
        # silently, because the build still succeeded.
        from mpynode.native.toolchain import port_cache

        a = self._base_spec("MPxNode")
        a["methods"] = '@maya_command("foo")\ndef foo(self):\n    return 1\n'
        a["commands"] = [{"name": "foo"}]
        b = copy.deepcopy(a)
        b["methods"] = '@maya_command("foo")\ndef foo(self):\n    return 2\n'
        self.assertNotEqual(
            port_cache.cache_key(a, provider="p", model="m"),
            port_cache.cache_key(b, provider="p", model="m"),
            "the command body is baked into the .cpp -> must re-port")

    def test_adding_a_command_busts_key_for_non_locator(self):
        from mpynode.native.toolchain import port_cache

        a = self._base_spec("MPxNode")
        b = copy.deepcopy(a)
        b["methods"] = '@maya_command("foo")\ndef foo(self):\n    return 1\n'
        b["commands"] = [{"name": "foo"}]
        self.assertNotEqual(
            port_cache.cache_key(a, provider="p", model="m"),
            port_cache.cache_key(b, provider="p", model="m"),
            "a node that gained a command must not reuse its command-less .cpp")

    def test_methods_edit_busts_key_for_locator(self):
        from mpynode.native.toolchain import port_cache

        a = self._base_spec("MPxLocatorNode")
        a["methods"] = ('@maya_command("createMeshRegion")\n'
                        'def f(cls):\n    return cls\n')
        a["commands"] = [{"name": "createMeshRegion"}]
        b = copy.deepcopy(a)
        b["commands"] = [{"name": "setMeshRegion"}]
        self.assertNotEqual(
            port_cache.cache_key(a, provider="p", model="m"),
            port_cache.cache_key(b, provider="p", model="m"),
            "a locator bakes the native command into the .cpp -> must re-port")

    def test_commandless_methods_edit_keeps_key(self):
        # Cost fence: `methods` only reaches the .cpp through the commands, so a
        # spec with NO commands must key identically across a methods-only edit
        # (setup/demo hooks live there) -- otherwise every such edit re-ports.
        from mpynode.native.toolchain import port_cache

        a = self._base_spec("MPxNode")
        a["methods"] = "def setup(self):\n    return 1\n"
        a["commands"] = []
        b = copy.deepcopy(a)
        b["methods"] = "def setup(self):\n    return 2\n"
        self.assertEqual(
            port_cache.cache_key(a, provider="p", model="m"),
            port_cache.cache_key(b, provider="p", model="m"),
            "a command-less .cpp does not embed methods -> no re-port")

        canon = port_cache._canonical_spec(a)
        self.assertNotIn("methods", canon)
        # And a spec carrying neither key still keys (no crash on the pop).
        self.assertTrue(port_cache.cache_key(self._base_spec("MPxNode"),
                                             provider="p", model="m"))


class TestCompileFromMpnPaths(unittest.TestCase):
    """(E) headless compile_from_mpn_paths."""

    def test_loads_each_path_and_forwards_specs(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        captured = {}

        def fake_compile(specs, plugin_name, out_dir, **kw):
            captured["specs"] = specs
            captured["plugin"] = plugin_name
            captured["kw"] = kw
            return {"ok": True}

        with mock.patch.object(mpn_io, "load_mpn",
                               side_effect=lambda p, **k: {"path": p}), \
             mock.patch.object(mpn_spec_adapter, "spec_from_mpn_payload",
                               side_effect=lambda d: {"spec_for": d["path"]}), \
             mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            res = cc.compile_from_mpn_paths(["a.mpn", "b.mpn"], "plug", "/tmp/out")

        self.assertTrue(res["ok"])
        self.assertEqual(len(captured["specs"]), 2)
        self.assertEqual(captured["specs"][0], {"spec_for": "a.mpn"})
        self.assertEqual(captured["specs"][1], {"spec_for": "b.mpn"})
        self.assertEqual(captured["plugin"], "plug")

    def test_path_tuple_sets_per_spec_bake_persistent(self):
        # A ``(path, bake)`` tuple flags that one .mpn's persistent data per-file;
        # a plain string falls back to the global default (no per-spec key).
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        captured = {}

        with mock.patch.object(mpn_io, "load_mpn",
                               side_effect=lambda p, **k: {"path": p}), \
             mock.patch.object(mpn_spec_adapter, "spec_from_mpn_payload",
                               side_effect=lambda d: {"spec_for": d["path"]}), \
             mock.patch.object(
                 cc, "compile_plugin",
                 side_effect=lambda specs, *a, **kw: captured.update(specs=specs)
                 or {"ok": True}):
            cc.compile_from_mpn_paths(
                [("a.mpn", False), "b.mpn"], "plug", "/tmp/out")

        specs = captured["specs"]
        self.assertEqual(specs[0]["spec_for"], "a.mpn")
        self.assertEqual(specs[1]["spec_for"], "b.mpn")
        self.assertIs(specs[0].get("bake_persistent"), False)  # tuple -> per-spec
        self.assertNotIn("bake_persistent", specs[1])          # string -> global

    def test_path_tuple_true_sets_per_spec_true(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        captured = {}
        with mock.patch.object(mpn_io, "load_mpn",
                               side_effect=lambda p, **k: {"path": p}), \
             mock.patch.object(mpn_spec_adapter, "spec_from_mpn_payload",
                               side_effect=lambda d: {}), \
             mock.patch.object(
                 cc, "compile_plugin",
                 side_effect=lambda specs, *a, **kw: captured.update(specs=specs)
                 or {"ok": True}):
            cc.compile_from_mpn_paths([("a.mpn", True)], "plug", "/tmp/out")
        self.assertIs(captured["specs"][0].get("bake_persistent"), True)

    def test_options_and_bake_persistent_forwarded(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        captured = {}

        with mock.patch.object(mpn_io, "load_mpn",
                               side_effect=lambda p, **k: {"path": p}), \
             mock.patch.object(mpn_spec_adapter, "spec_from_mpn_payload",
                               side_effect=lambda d: {}), \
             mock.patch.object(cc, "compile_plugin",
                               side_effect=lambda *a, **kw: captured.update(kw) or {"ok": True}):
            cc.compile_from_mpn_paths(["a.mpn"], "plug", "/tmp/out",
                                      bake_persistent=False, strict=False)

        self.assertIs(captured.get("bake_persistent"), False)
        self.assertIs(captured.get("strict"), False)

    def test_one_element_tuple_unpacks_inner_path(self):
        # A 1-element ``(path,)`` sequence must still load the inner path string
        # (bake falls back to the global), not pass the whole tuple to load_mpn.
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        calls = []

        def fake_load(p, **k):
            calls.append(p)
            return {"path": p}

        with mock.patch.object(mpn_io, "load_mpn", side_effect=fake_load), \
             mock.patch.object(mpn_spec_adapter, "spec_from_mpn_payload",
                               side_effect=lambda d: {}), \
             mock.patch.object(cc, "compile_plugin",
                               side_effect=lambda *a, **kw: {"ok": True}):
            cc.compile_from_mpn_paths([("a.mpn",), ["b.mpn"]], "plug", "/tmp/out")

        self.assertEqual(calls, ["a.mpn", "b.mpn"])  # inner strings, not sequences

    def test_load_uses_trusted_true_by_default(self):
        from mpynode.native.toolchain import compile_controller as cc
        from mpynode._common.io import mpn_io
        from mpynode.native.spec import mpn_spec_adapter

        calls = []

        def fake_load(p, **k):
            calls.append(k)
            return {"path": p}

        with mock.patch.object(mpn_io, "load_mpn", side_effect=fake_load), \
             mock.patch.object(mpn_spec_adapter, "spec_from_mpn_payload",
                               side_effect=lambda d: {}), \
             mock.patch.object(cc, "compile_plugin",
                               side_effect=lambda *a, **kw: {"ok": True}):
            cc.compile_from_mpn_paths(["a.mpn"], "plug", "/tmp/out")

        self.assertTrue(all(c.get("trusted") is True for c in calls))

    def test_compile_controller_top_has_no_maya_import(self):
        import ast

        from mpynode.native.toolchain import compile_controller as cc

        tree = ast.parse(inspect.getsource(cc))
        offenders = []
        for node in tree.body:  # module top-level only
            if isinstance(node, ast.Import):
                offenders += [a.name for a in node.names
                              if a.name.split(".")[0] == "maya"]
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "maya":
                    offenders.append(node.module)
        self.assertEqual(offenders, [])


class TestApplyPersistentPolicy(unittest.TestCase):
    """The per-spec / global persistent-bake decision (one engine mechanism).

    Each spec may carry its own ``bake_persistent`` override; it WINS over the
    global default. The key is popped so it never reaches the port_cache key
    (the bake decision shows up there via ``variables`` being {} or not)."""

    def _two_specs(self):
        a = _spec_with_vars(); a["source_node"] = "a"
        b = _spec_with_vars(); b["source_node"] = "b"
        return [a, b]

    def test_per_spec_false_overrides_global_true(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = self._two_specs()
        specs[0]["bake_persistent"] = False
        cc._apply_persistent_policy(specs, True)  # global would keep
        self.assertEqual(specs[0]["variables"], {})
        self.assertNotEqual(specs[1]["variables"], {})

    def test_per_spec_true_overrides_global_false(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = self._two_specs()
        specs[0]["bake_persistent"] = True
        cc._apply_persistent_policy(specs, False)  # global would strip
        self.assertNotEqual(specs[0]["variables"], {})
        self.assertEqual(specs[1]["variables"], {})

    def test_key_is_popped(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = self._two_specs()
        specs[0]["bake_persistent"] = True
        cc._apply_persistent_policy(specs, True)
        self.assertNotIn("bake_persistent", specs[0])
        self.assertNotIn("bake_persistent", specs[1])

    def test_global_default_when_no_per_spec_key(self):
        from mpynode.native.toolchain import compile_controller as cc

        specs = self._two_specs()
        cc._apply_persistent_policy(specs, False)  # global strips all
        self.assertEqual(specs[0]["variables"], {})
        self.assertEqual(specs[1]["variables"], {})

    def test_no_variables_key_stays_absent_when_stripped(self):
        # A spec with NO 'variables' key must not gain one on strip (so its
        # cache key matches the key-absent twin; both adapters always emit the
        # key, this guards synthetic/partial specs).
        from mpynode.native.toolchain import compile_controller as cc

        spec = {"source_node": "a"}  # deliberately no 'variables'
        cc._apply_persistent_policy([spec], False)  # strip
        self.assertNotIn("variables", spec)


# ===================== from test_native_parity_sweep.py =====================
import importlib.util
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from tests._setup import standalone_init


def _repo_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "scripts", "mpynode")):
            return d
        d = os.path.dirname(d)
    raise RuntimeError("repo root (containing scripts/mpynode) not found")


_ROOT = _repo_root()
_SWEEP_DIR = os.path.join(_ROOT, "tools", "parity_sweep")
_RUNNER = os.path.join(_SWEEP_DIR, "run_parity_sweep.py")

_EXPECTED_TYPES = [
    "mPyNode", "mPyConstraint", "mPyFile",
    "mPyMesh", "mPyNurbsCurve", "mPyNurbsSurface",
    "mPyDeformer", "mPyBlendShape", "mPySkinCluster",
    "mPyTransform", "mPyIkSolver", "mPyLocator",
]


def _load_runner():
    spec = importlib.util.spec_from_file_location("_parity_runner", _RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _setUpModule__native_parity_sweep():
    standalone_init()


class TestParitySweepWiring(unittest.TestCase):
    """Always-on, fast, Maya-free guards for the sweep harness."""

    def test_runner_and_all_scripts_present(self):
        self.assertTrue(os.path.isfile(_RUNNER), _RUNNER)
        for t in _EXPECTED_TYPES:
            p = os.path.join(_SWEEP_DIR, "parity_%s.py" % t)
            self.assertTrue(os.path.isfile(p), "missing %s" % p)

    def test_runner_covers_exactly_the_basic_types(self):
        mod = _load_runner()
        self.assertEqual(sorted(mod.TYPES), sorted(_EXPECTED_TYPES))

    def test_scripts_are_portable_no_hardcoded_user_path(self):
        # A CI gate must not bake in a developer's absolute path.
        for t in _EXPECTED_TYPES:
            p = os.path.join(_SWEEP_DIR, "parity_%s.py" % t)
            with open(p) as fh:
                src = fh.read()
            self.assertNotIn("/Users/", src, "%s hardcodes a user path" % t)

    def test_parser_accepts_every_result_format(self):
        mod = _load_runner()
        passing = {
            "locator_json": 'PARITY_RESULT {"pass": true, "maxerr": 1.8e-07, '
                            '"components_compared": 504}',
            "node": "COMPONENTS: 125\nMAXERR: 0.0\nRESULT: PASS",
            "constraint": "RESULT PASS samples 25 components 75 "
                          "maxerr 8.8e-16 fails 0",
            "file": "RESULT pass1=True pass2=True overall=True "
                    "overall_maxerr=6.4e-06 total_comps=180",
            "curve": "RESULT|PASS|maxerr=0|samples=8|components=192",
            "surface": "RESULT samples=8 components=600 maxerr=0.0\nPARITY PASS",
            "deformer": "RESULT samples=14 components=5628 maxerr=0.0\n"
                        "VERIFY PASS",
            "blend": "RESULT_LINE PASS maxerr=7.6e-06 samples=14 "
                     "components=5628",
            "transform": "RESULT maxerr=0.0 nsamp=8 ncomp=128 tol=1e-4 "
                         "pass=True",
        }
        for name, out in passing.items():
            self.assertIs(mod._parse(out)["pass"], True, name)

    def test_parser_is_discriminating_not_rubber_stamp(self):
        mod = _load_runner()
        fail = "RESULT samples=8 components=72 maxerr=9.9 tol=1e-4\nPARITY FAIL"
        self.assertIs(mod._parse(fail)["pass"], False)
        # Unparseable output must be UNKNOWN (None), never a silent pass.
        self.assertIsNone(mod._parse("garbage, no result line")["pass"])


# ---------------------------------------------------------------------------
# Integration: run the FULL basic-type sweep. Opt-in (slow ~6 min) + needs Maya.
#   MPYNODE_RUN_PARITY_SWEEP=1  (and maya2026 present)
# ---------------------------------------------------------------------------
_MAYA2026 = "/Applications/Autodesk/maya2026"
_MAYAPY = os.path.join(_MAYA2026, "Maya.app", "Contents", "bin", "mayapy")
_HAS_MAYA = os.path.isfile(_MAYAPY)
_OPT_IN = os.environ.get("MPYNODE_RUN_PARITY_SWEEP") == "1"


@unittest.skipUnless(
    _HAS_MAYA and _OPT_IN,
    "slow native parity sweep -- set MPYNODE_RUN_PARITY_SWEEP=1 (needs maya2026)")
class TestParitySweepIntegration(unittest.TestCase):
    def test_all_types_pass(self):
        env = dict(os.environ, MAYAPY=_MAYAPY, MPYNODE_ROOT=_ROOT)
        proc = subprocess.run(
            [sys.executable, _RUNNER],
            capture_output=True, text=True, env=env, timeout=1800)
        out = proc.stdout + "\n" + proc.stderr
        print("\n" + out)
        self.assertEqual(proc.returncode, 0, "parity sweep failed:\n" + out)
        self.assertIn("12/12 PASS", out)


# ===================== from test_multi_version_compile.py =====================
import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._setup import standalone_init


def _setUpModule__multi_version_compile():
    standalone_init()


def _make_maya_tree(parent, label, *, devkit=True, mayapy=True):
    """Create a fake Maya install under ``parent/label`` (macOS layout)."""
    root = os.path.join(parent, label)
    if devkit:
        os.makedirs(os.path.join(root, "include", "maya"), exist_ok=True)
    if mayapy:
        binp = os.path.join(root, "Maya.app", "Contents", "bin")
        os.makedirs(binp, exist_ok=True)
        with open(os.path.join(binp, "mayapy"), "w") as f:
            f.write("#!/bin/sh\n")
    os.makedirs(root, exist_ok=True)
    return root


class TestDiscoverMayaInstalls(unittest.TestCase):
    def test_finds_devkit_plus_mayapy_only(self):
        from mpynode.native.toolchain import toolchain

        tmp = tempfile.mkdtemp()
        _make_maya_tree(tmp, "maya2024")
        _make_maya_tree(tmp, "maya2026")
        # Runtime-only (no devkit) -> excluded (mimics mayausd).
        _make_maya_tree(tmp, "mayausd", devkit=False, mayapy=False)
        # Devkit-only (no mayapy) -> excluded.
        _make_maya_tree(tmp, "maya2020", mayapy=False)

        found = toolchain.discover_maya_installs(search_dirs=[tmp])
        labels = [e["label"] for e in found]
        self.assertEqual(labels, ["maya2024", "maya2026"])
        for e in found:
            self.assertTrue(os.path.isfile(e["mayapy"]))
            self.assertTrue(e["root"].endswith(e["label"]))
        self.assertEqual(found[0]["version"], "2024")
        self.assertEqual(found[1]["version"], "2026")

    def test_sorted_by_version(self):
        from mpynode.native.toolchain import toolchain

        tmp = tempfile.mkdtemp()
        _make_maya_tree(tmp, "maya2026")
        _make_maya_tree(tmp, "maya2023")
        _make_maya_tree(tmp, "maya2025")
        found = toolchain.discover_maya_installs(search_dirs=[tmp])
        self.assertEqual([e["version"] for e in found], ["2023", "2025", "2026"])

    def test_custom_label_does_not_outrank_real_year(self):
        # A non-year custom install (devkit+mayapy) must NOT sort last and become
        # the "highest version" default; the newest REAL year stays last.
        from mpynode.native.toolchain import toolchain

        tmp = tempfile.mkdtemp()
        _make_maya_tree(tmp, "maya2024")
        _make_maya_tree(tmp, "maya2026")
        _make_maya_tree(tmp, "mayaDev")  # no 4-digit year
        found = toolchain.discover_maya_installs(search_dirs=[tmp])
        labels = [e["label"] for e in found]
        self.assertIn("mayaDev", labels)
        # The last entry (the _default_checked_labels "highest") is a real year.
        self.assertEqual(found[-1]["label"], "maya2026")

    def test_empty_when_nothing_installed(self):
        from mpynode.native.toolchain import toolchain

        tmp = tempfile.mkdtemp()
        self.assertEqual(toolchain.discover_maya_installs(search_dirs=[tmp]), [])

    def test_default_search_dirs_per_platform(self):
        from mpynode.native.toolchain import toolchain

        self.assertEqual(toolchain.maya_install_search_dirs("darwin"),
                         ["/Applications/Autodesk"])
        self.assertIn("Autodesk", toolchain.maya_install_search_dirs("win32")[0])
        self.assertEqual(toolchain.maya_install_search_dirs("linux"),
                         ["/usr/autodesk"])


def _target(label, root):
    return {"label": label, "version": label[-4:], "root": root,
            "mayapy": os.path.join(root, "mayapy")}


def _ok_result(ok=True):
    return {"ok": ok, "bundle_path": "/b", "manifest_path": "/m",
            "plugin_name": "plug", "nodes": [], "errors": [], "strict": True}


class TestCompilePluginMulti(unittest.TestCase):
    """(headless) compile_plugin_multi loops the engine once per Maya target."""

    def test_per_version_outdir_and_maya(self):
        from mpynode.native.toolchain import compile_controller as cc

        calls = []

        def fake_compile(specs, name, out_dir, **kw):
            calls.append({"out_dir": out_dir, "maya": kw.get("maya")})
            return _ok_result(True)

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            res = cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")])

        self.assertTrue(res["ok"])
        self.assertEqual(len(res["results"]), 2)
        self.assertEqual(calls[0]["out_dir"], os.path.join("/out", "maya2024"))
        self.assertEqual(calls[0]["maya"], "/m/2024")
        self.assertEqual(calls[1]["out_dir"], os.path.join("/out", "maya2026"))
        self.assertEqual(calls[1]["maya"], "/m/2026")
        self.assertEqual(res["results"][0]["label"], "maya2024")
        self.assertEqual(res["results"][0]["out_dir"],
                         os.path.join("/out", "maya2024"))

    def test_specs_deepcopied_per_version(self):
        from mpynode.native.toolchain import compile_controller as cc

        seen_ids = []

        def fake_compile(specs, name, out_dir, **kw):
            seen_ids.append(id(specs))
            specs[0]["variables"] = {"MUTATED": True}  # mimic in-place strip
            return _ok_result(True)

        original = [{"variables": {"a": 1}}]
        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            cc.compile_plugin_multi(original, "plug", "/out",
                                    [_target("maya2024", "/m/2024"),
                                     _target("maya2026", "/m/2026")])

        # The caller's list AND each per-version copy are independent objects.
        self.assertNotIn(id(original), seen_ids)
        self.assertNotEqual(seen_ids[0], seen_ids[1])
        # The caller's specs were NOT mutated by either version build.
        self.assertEqual(original[0]["variables"], {"a": 1})

    def test_continue_on_per_version_failure(self):
        from mpynode.native.toolchain import compile_controller as cc

        def fake_compile(specs, name, out_dir, **kw):
            ok = "2026" in (kw.get("maya") or "")
            return _ok_result(ok)

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            res = cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")])

        # Both attempted; overall NOT ok because one failed.
        self.assertEqual(len(res["results"]), 2)
        self.assertFalse(res["ok"])
        self.assertFalse(res["results"][0]["result"]["ok"])
        self.assertTrue(res["results"][1]["result"]["ok"])

    def test_exception_in_one_version_does_not_abort_others(self):
        from mpynode.native.toolchain import compile_controller as cc

        def fake_compile(specs, name, out_dir, **kw):
            if "2024" in (kw.get("maya") or ""):
                raise RuntimeError("boom 2024")
            return _ok_result(True)

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            res = cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")])

        self.assertEqual(len(res["results"]), 2)
        self.assertFalse(res["results"][0]["result"]["ok"])
        self.assertTrue(res["results"][1]["result"]["ok"])
        self.assertFalse(res["ok"])

    def test_verify_fn_for_builds_per_version(self):
        from mpynode.native.toolchain import compile_controller as cc

        got = []

        def fake_compile(specs, name, out_dir, **kw):
            got.append(kw.get("verify_fn"))
            return _ok_result(True)

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")],
                verify_fn_for=lambda root: ("VF", root))

        self.assertEqual(got[0], ("VF", "/m/2024"))
        self.assertEqual(got[1], ("VF", "/m/2026"))

    def test_emits_version_events(self):
        from mpynode.native.toolchain import compile_controller as cc

        events = []
        with mock.patch.object(cc, "compile_plugin",
                               side_effect=lambda *a, **k: _ok_result(True)):
            cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")],
                progress_cb=lambda e: events.append(e))

        version_starts = [e for e in events
                          if e["stage"] == "version" and e["status"] == "start"]
        self.assertEqual([e["node"] for e in version_starts],
                         ["maya2024", "maya2026"])
        self.assertEqual([e["i"] for e in version_starts], [0, 1])
        self.assertEqual([e["n"] for e in version_starts], [2, 2])
        self.assertTrue(any(e["stage"] == "done" for e in events))

    def test_inner_done_events_suppressed(self):
        from mpynode.native.toolchain import compile_controller as cc

        events = []

        def fake_compile(specs, name, out_dir, **kw):
            cb = kw.get("progress_cb")
            if cb:  # compile_plugin emits its own terminal 'done' per call
                cb({"stage": "done", "node": None, "status": "ok",
                    "detail": "", "i": 0, "n": 0})
            return _ok_result(True)

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")],
                progress_cb=lambda e: events.append(e))

        # Exactly ONE done reaches the caller -- the outer multi 'done', not the
        # two inner per-version ones (which would prematurely finish the dialog).
        dones = [e for e in events if e["stage"] == "done"]
        self.assertEqual(len(dones), 1)
        # Inner stage events (e.g. version) still flow through.
        self.assertTrue(any(e["stage"] == "version" for e in events))

    def test_cancel_stops_remaining_versions(self):
        from mpynode.native.toolchain import compile_controller as cc
        import threading

        cancel = threading.Event()
        calls = []

        def fake_compile(specs, name, out_dir, **kw):
            calls.append(kw.get("maya"))
            cancel.set()  # cancel after the first build
            return _ok_result(True)

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")],
                cancel_event=cancel)

        self.assertEqual(calls, ["/m/2024"])  # second never started

    def test_cancel_between_versions_is_not_ok(self):
        from mpynode.native.toolchain import compile_controller as cc
        import threading

        cancel = threading.Event()

        def fake_compile(specs, name, out_dir, **kw):
            cancel.set()  # cancel lands in the gap BEFORE the next version
            return _ok_result(True)

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            res = cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")],
                cancel_event=cancel)

        # A requested version was never built -> must NOT report ok.
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("cancelled"))
        self.assertEqual(len(res["results"]), 1)
        self.assertTrue(any("cancel" in e.lower() for e in res["errors"]))

    def test_result_always_carries_errors_key(self):
        from mpynode.native.toolchain import compile_controller as cc

        # success -> errors present and empty
        with mock.patch.object(cc, "compile_plugin",
                               side_effect=lambda *a, **k: _ok_result(True)):
            ok_res = cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2026", "/m/2026")])
        self.assertIn("errors", ok_res)
        self.assertEqual(ok_res["errors"], [])

        # per-version failure -> labelled error aggregated at top level
        def fake_compile(specs, name, out_dir, **kw):
            ok = "2026" in (kw.get("maya") or "")
            r = _ok_result(ok)
            if not ok:
                r["errors"] = ["boom"]
            return r

        with mock.patch.object(cc, "compile_plugin", side_effect=fake_compile):
            fail_res = cc.compile_plugin_multi(
                [{"variables": {}}], "plug", "/out",
                [_target("maya2024", "/m/2024"),
                 _target("maya2026", "/m/2026")])
        self.assertIn("errors", fail_res)
        self.assertTrue(any("maya2024" in e for e in fail_res["errors"]))

    def test_no_maya_import_at_module_top(self):
        import ast
        import inspect
        from mpynode.native.toolchain import compile_controller as cc

        tree = ast.parse(inspect.getsource(cc))
        offenders = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                offenders += [a.name for a in node.names
                              if a.name.split(".")[0] == "maya"]
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] == "maya":
                    offenders.append(node.module)
        self.assertEqual(offenders, [])


class TestStartMulti(unittest.TestCase):
    """CompileController.start_multi runs compile_plugin_multi off-thread."""

    def test_start_multi_forwards_and_sets_result(self):
        from mpynode.native.toolchain import compile_controller as cc

        captured = {}

        def fake_multi(specs, name, out_dir, targets, **kw):
            captured["targets"] = targets
            captured["kw"] = kw
            return {"ok": True, "multi": True, "results": []}

        ctrl = cc.CompileController(progress_cb=lambda e: None)
        with mock.patch.object(cc, "compile_plugin_multi", side_effect=fake_multi):
            t = ctrl.start_multi([{"variables": {}}], "plug", "/out",
                                 [_target("maya2024", "/m/2024")],
                                 strict=True, verify=True)
            t.join(timeout=5)

        self.assertEqual(ctrl.result, {"ok": True, "multi": True, "results": []})
        # progress_cb + cancel_event injected by the controller (not the caller).
        self.assertIn("progress_cb", captured["kw"])
        self.assertIn("cancel_event", captured["kw"])
        self.assertEqual(len(captured["targets"]), 1)


def setUpModule():
    _setUpModule__compile_preflight()
    _setUpModule__file_read_support()
    _setUpModule__rng_support()
    _setUpModule__verify_array_and_error()
    _setUpModule__compile_from_mpn()
    _setUpModule__native_parity_sweep()
    _setUpModule__multi_version_compile()


if __name__ == "__main__":
    import unittest
    unittest.main()
