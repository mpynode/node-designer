"""Phase 2 -- the AI porter: spec -> compiled, verified native plugin.

Pipeline: codegen emits a port-mode skeleton (attributes + registration final;
a marked region for the compute body). The LLM translates the Python compute
into C++ that fills that region. We splice it in, compile with the proven
clang++ recipe, and on failure feed the compiler errors back to the model
(bounded fix loop). Finally we emit a ``verify_in_maya.py`` that checks the
compiled node matches the original mPyNode numerically.

Qt-free: depends only on ``native.codegen`` + ``ui.llm.config`` (config has no
Qt import) + stdlib, so the porter runs headless or inside Maya. The LLM call
is a plain one-shot completion (no tools), reusing config for provider / key /
model / TLS / retry. ``complete_fn`` is injectable for testing.

This module is the HUB: the prompts, followed-helper machinery, provider
transport, and verify-script emitters live in the sibling modules
(``prompt`` / ``helpers`` / ``llm_client`` / ``verify_scripts``); the names
they export are re-imported here so external callers keep reaching them as
``porter.<name>``.
"""

from __future__ import annotations

import os

from mpynode.native import compiler as codegen
from mpynode.native.toolchain import toolchain
from mpynode.native.ai import translation_knowledge
from . import prompt, llm_client, helpers, verify_scripts
# names used verbatim by the kept function bodies:
from .prompt import build_prompt, splice_body
from .llm_client import _complete, make_cli_complete_fn, PortCancelled
from .helpers import (
    _shareable_helper_units, _translate_helper, _marked_block,
    _inject_helper_blocks, _HelperProtoError, reset_helper_memo,
)
from .verify_scripts import _verify_script

# Back-compat surface: external callers reach these as porter.<name>.
from .llm_client import check_provider  # noqa: F401
from .prompt import _strip_fences  # noqa: F401

# Complete facade: this module was monolithic and callers (tests especially) reach
# its former internals by name, so re-export EVERY name the split siblings define
# (public and private) and porter stays a perfect drop-in. setdefault preserves
# the hub's own imports above and the functions below; a curated subset would be
# omission-prone (~50 private helpers).
for _mod in (prompt, helpers, llm_client, verify_scripts):
    for _name in dir(_mod):
        if not _name.startswith("__"):
            globals().setdefault(_name, getattr(_mod, _name))
del _mod, _name

_MAYA_DEFAULT = toolchain.preferred_maya_dir()


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------


def compile_cpp(cpp_path: str, spec: dict, out_dir: str,
                maya: str = _MAYA_DEFAULT, compiler: str = None,
                log_cb=None, optimize: bool = False) -> tuple:
    """Compile one .cpp to a native Maya plugin. Returns (ok, log, plugin_path).

    The compile/link recipe and the plugin extension are chosen per platform by
    ``native.toolchain`` (macOS: clang -> ``.bundle``; Windows: cl -> ``.mll``).
    ``compiler`` defaults to the platform compiler. ``log_cb(line)`` (optional)
    receives each line of compiler output as it streams, for a live log view;
    the full text is still returned in ``log`` (so the fix-loop is unchanged).
    ``optimize=True`` is the AI-optimizer recompile recipe (-O3 -ffp-contract=off
    on unix); it defaults False so the porter's own compiles are unchanged.
    """
    compiler = compiler or toolchain.default_compiler()
    name     = spec["suggested"]["node_type_name"]
    plugin   = os.path.join(out_dir, name + toolchain.plugin_ext())
    is_msvc  = toolchain.compiler_family(compiler) == "msvc"
    benv     = toolchain.build_env(compiler)
    # MSVC: with no captured vcvars env, do NOT fall back to a stray cl.exe on
    # PATH -- it may be an older toolset than the installed headers ("STL1001:
    # Unexpected compiler version"). Allow the ambient compiler only inside an
    # x64 Native Tools prompt, where the toolset is already consistent.
    if is_msvc and benv is None and not toolchain.in_developer_shell():
        return False, toolchain.vcvars_unavailable_message(compiler), plugin
    # Resolve the compiler to a full path before launching. cl.exe is on the PATH
    # only inside the captured vcvars env, which Windows subprocess won't search,
    # so a bare "cl" raises the opaque "[WinError 2]" even with Visual Studio
    # installed. resolve_compiler returns the full path (preferring the
    # toolset-exact one from VCToolsInstallDir); unix compilers pass through
    # unchanged, so macOS/Linux argv is byte-for-byte identical.
    exe = toolchain.resolve_compiler(compiler, benv)
    if exe is None:
        return False, toolchain.compiler_missing_message(compiler), plugin
    # MSVC toolset-consistency PRE-FLIGHT: refuse BEFORE compiling if cl is from a
    # DIFFERENT toolset than the INCLUDE headers -- the STL1001 cause, which the AI
    # fix-loop can NEVER fix (a toolchain mismatch, not a code error), so every fix
    # round would burn on the same error. Cannot trigger with a captured vcvars
    # env; this catches the ambient developer-shell fallback.
    if is_msvc:
        include  = (benv or os.environ).get("INCLUDE")
        mismatch = toolchain.diagnose_toolset_mismatch(exe, include)
        if mismatch:
            return False, mismatch, plugin
        # Stream toolchain diagnostics so the live log shows EXACTLY which cl +
        # toolset is being used (the evidence needed to debug an STL1001).
        if log_cb is not None:
            try:
                log_cb("compiler: %s" % exe)
                log_cb("MSVC build env: %s" % (
                    "captured from vcvars" if benv is not None
                    else "ambient (developer shell)"))
                cl_ts = toolchain.msvc_toolset_from_path(exe) or "?"
                inc_ts = ", ".join(
                    toolchain.msvc_toolsets_from_include(include)) or "?"
                log_cb("toolset: cl=%s  headers=%s" % (cl_ts, inc_ts))
            except Exception:
                pass
    cmd = toolchain.compile_to_plugin_cmd(
        exe, cpp_path, plugin,
        include_dir = toolchain.maya_include_dir(maya),
        lib_dir     = toolchain.maya_lib_dir(maya),
        libs        = codegen._libs_for(spec),
        arch        = toolchain.mac_arch(),
        # A hover-capable locator links Maya's Qt frameworks (its self-contained
        # C++ hover service includes QCursor/QWidget). Off for every other node.
        qt       = bool(spec.get("needs_hover")),
        optimize = optimize,
        maya     = maya,
    )
    try:
        rc, log = toolchain.run_streaming(cmd, env=benv, log_cb=log_cb)
    except FileNotFoundError:
        # The compiler executable could not be launched at all -- translate the
        # opaque OS "file not found" into an actionable message instead of
        # bubbling a bare [WinError 2] up to the user.
        return False, toolchain.compiler_missing_message(compiler), plugin
    toolchain.remove_msvc_link_byproducts(plugin, one_shot=True)
    return rc == 0, log, plugin


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def apply_type_name(spec: dict, type_name: str) -> dict:
    """Override the generated node *type* name (and derived class name).

    Lets the plugin's node type differ from the scene node name -- e.g. scene
    node ``bubbleSort`` -> plugin type ``bubbleSorter``. The name is sanitized
    to a valid Maya/C++ identifier. ``type_name`` falsy/None is a no-op (keeps
    the scene-derived name). Mutates and returns ``spec``.
    """
    if not type_name or not str(type_name).strip():
        return spec
    from mpynode.native.spec import spec_extractor

    # Name-only override: rewrite node_type_name + class_name, PRESERVE type_id
    # (the suggested id is registry-reallocated at assemble; recomputing it here
    # would perturb any reader before then). Deliberately does NOT use
    # identity.derive_class_identity (which lower-firsts the type name) -- this
    # override sets node_type_name to the sanitized name verbatim.
    ident                 = spec_extractor._sanitize_ident(type_name)
    sug                   = spec.setdefault("suggested", {})
    sug["node_type_name"] = ident
    sug["class_name"]     = ident[:1].upper() + ident[1:]
    return spec


def port_node(spec: dict, out_dir: str, complete_fn=None,
              max_fix_rounds: int = 4, maya: str = _MAYA_DEFAULT,
              type_name: str = None, log_cb=None, ai_assist: bool = True,
              stage_cb=None) -> dict:
    """Generate -> AI compute -> compile -> fix-loop. Returns a result dict.

    ``complete_fn(system, user) -> str`` defaults to the real LLM; inject a
    fake in tests. Raises ``codegen.UnsupportedSpec`` if out of phase-1 scope.
    ``type_name`` overrides the generated node type name; None keeps the
    scene-derived name. ``log_cb(line)`` (optional) streams each line of compiler
    output for a live log view (forwarded to every ``compile_cpp`` call).

    ``ai_assist=False`` stops a node that NEEDS the porter at the deterministic
    stage: the skeleton (with its empty PORT region and the Python carried as
    comments) is written and returned with ``needs_assist=True``, and the LLM is
    never called. A node that lowers deterministically ignores the flag and
    compiles exactly as before -- keeping "no AI ran" a true statement about the
    build rather than a request that gets silently upgraded.

    ``stage_cb(stage, text)`` (optional) receives each durable pipeline artifact
    -- ``"1_transpiled"`` always, ``"2_assisted"`` only when the AI actually
    authored a body. The callback owns where it lands; the porter stays ignorant
    of the output-folder layout.
    """
    complete_fn = complete_fn or _complete
    apply_type_name(spec, type_name)
    os.makedirs(out_dir, exist_ok=True)
    name     = spec["suggested"]["node_type_name"]
    cpp_path = os.path.join(out_dir, name + ".cpp")

    # Stream the porter's multi-step work into the live log window so the user
    # sees progress BEFORE the (long) compile -- never raises on a bad callback.
    def _log(msg):
        if log_cb is not None:
            try:
                log_cb(msg)
            except Exception:
                pass

    def _stage(stage, text):
        """Hand a durable pipeline artifact to the caller (never raises)."""
        if stage_cb is None:
            return
        try:
            stage_cb(stage, text)
        except Exception:
            pass

    def _splice(skel, ai_body):
        """Splice the AI body in, then add any std header the body needs.

        The only compile gate here is macOS clang, and libc++ satisfies far more
        std facilities transitively than the MSVC STL does -- so a body using
        std::mutex or std::array with no include for it compiles clean and fails
        C2039 on Windows, where nothing in this pipeline can see it. Adding a
        standard header to a TU that already compiled cannot break it, so the
        repair is applied rather than reported: a missing include is never a
        reason to throw away a good port. Used by all four splice sites,
        including the fix-loop, since `skel` is re-spliced from scratch each
        round and the previous round's additions are not carried over."""
        out  = splice_body(skel, ai_body)
        need = prompt.missing_std_includes(out)
        if need:
            out = prompt.add_std_includes(out, need)
            _log("[%s] added missing include(s) for MSVC: %s"
                 % (name, " ".join("<%s>" % h for h in need)))
        return out

    _log("[%s] generating C++ skeleton..." % name)
    inline_skeleton = codegen.generate_cpp(spec, for_port=True)  # validates scope
    skeleton        = inline_skeleton

    # Stage 1 is a DELIVERABLE. Emit it before anything can fail downstream, on
    # every path -- deterministic or not, assisted or not. For a node the
    # transpiler could not lower this is the "baseline .cpp with the gaps marked"
    # that a user without an AI budget can still take away and finish by hand.
    _stage("1_transpiled", inline_skeleton)

    # Deterministic node: codegen emitted the FULL compute (verified helpers, no
    # AI PORT region) -- e.g. a full-parity mPyFile. Compile as-is: no LLM call,
    # no fix-loop. Still emit the build + verify helpers and return the same shape.
    if codegen.PORT_BEGIN not in inline_skeleton:
        _log("[%s] deterministic compute (verified helpers); compiling..." % name)
        with open(cpp_path, "w", encoding="utf-8") as f:
            f.write(inline_skeleton)
        ok, log, bundle = compile_cpp(cpp_path, spec, out_dir, maya=maya,
                                      log_cb=log_cb)
        build_name, build_src = codegen.generate_build_script(spec, maya=maya)
        build_path = os.path.join(out_dir, build_name)
        with open(build_path, "w", encoding="utf-8") as f:
            f.write(build_src)
        if not toolchain.is_windows():
            os.chmod(build_path, 0o755)
        # The Windows script force-includes this by bare name: keep it beside
        # the .cpp (toolchain.QT_MSVC_COMPAT_HEADER).
        toolchain.ship_qt_msvc_compat_header(out_dir, bool(spec.get("needs_hover")))
        verify_path = os.path.join(out_dir, "verify_in_maya.py")
        with open(verify_path, "w", encoding="utf-8") as f:
            f.write(_verify_script(spec))
        return {
            "ok": ok, "node": name, "cpp": cpp_path,
            "bundle": bundle if ok else None, "fix_rounds": 0,
            "compiler_log": log, "verify_script": verify_path,
        }

    # Past here the node HAS a PORT region, i.e. finishing it requires the AI.
    # With assist declined, stop: write the deterministic skeleton as the node's
    # .cpp and report what is missing. Deliberately BEFORE the shared-helper
    # translation below, which is itself an LLM call.
    if not ai_assist:
        n_regions = inline_skeleton.count(codegen.PORT_BEGIN)
        _log("[%s] AI assist off; stopping at the deterministic stage "
             "(%d region(s) unported)" % (name, n_regions))
        with open(cpp_path, "w", encoding="utf-8") as f:
            f.write(inline_skeleton)
        return {
            "ok": False, "node": name, "cpp": cpp_path, "bundle": None,
            "fix_rounds": 0, "compiler_log": "", "verify_script": None,
            "needs_assist": True, "port_regions": n_regions,
        }

    # Shared followed-import helpers: translate each once into a named C++ free
    # function, emit it as a marked file-scope block (the bundler hoists the unique
    # set into one shared_helpers.cpp), and tell the port to CALL them. Scalar
    # helpers carry a fixed proto; non-scalar ones let the LLM choose a typed proto
    # (accumulated into `known` so a later helper may call an earlier one). No
    # shareable helpers -> shared_protos None -> the inline path, byte-for-byte. A
    # translation with no usable signature drops the node to the inline path.
    shared_units  = _shareable_helper_units(spec)
    shared_protos = None
    if shared_units:
        _log("[%s] translating %d shared helper(s)..."
             % (name, len(shared_units)))
        try:
            known   = [u["proto"] for u in shared_units if u.get("proto")]
            results = []
            for u in shared_units:
                r = _translate_helper(u, complete_fn, known)
                results.append(r)
                if r["proto"] and r["proto"] not in known:
                    known.append(r["proto"])
            blocks = [_marked_block(r["name"], r["proto"], r["code"])
                      for r in results]
            skeleton = _inject_helper_blocks(inline_skeleton, blocks)
            shared_protos = [("%s.%s" % (u["module"], u["sym"]), r["proto"])
                             for (u, r) in zip(shared_units, results)]
        except _HelperProtoError:
            skeleton      = inline_skeleton
            shared_protos = None

    system, user = build_prompt(spec, skeleton, shared_protos=shared_protos)

    _log("[%s] requesting AI compute body..." % name)
    body = complete_fn(system, user)
    cpp  = _splice(skeleton, body)
    with open(cpp_path, "w", encoding="utf-8") as f:
        f.write(cpp)

    _log("[%s] compiling (initial)..." % name)
    ok, log, bundle = compile_cpp(cpp_path, spec, out_dir, maya=maya,
                                       log_cb=log_cb)
    rounds = 0
    while not ok and rounds < max_fix_rounds:
        rounds += 1
        _log("[%s] compile failed; AI fix round %d/%d..."
             % (name, rounds, max_fix_rounds))
        fix_user = (
            "The C++ below did not compile. Fix ONLY the compute body (the code "
            "between the PORT markers) and output the corrected body statements "
            "only (no fences, no signature).\n\n"
            "Compiler errors:\n%s\n\nCurrent file:\n```cpp\n%s\n```\n"
            % (log[-4000:], cpp)
        )
        body = complete_fn(system, fix_user)
        cpp  = _splice(skeleton, body)
        with open(cpp_path, "w", encoding="utf-8") as f:
            f.write(cpp)
        ok, log, bundle = compile_cpp(cpp_path, spec, out_dir, maya=maya,
                                       log_cb=log_cb)

    # Safety net: a node that USED shared helpers and STILL did not compile after
    # the fix-loop retries ONCE on the robust INLINE path (helper source ported
    # inside compute). Reuses the exact inline machinery and writes the SAME
    # cpp_path, so the bundled .cpp carries NO marked block and the bundler treats
    # it as a plain node. Gated on `shared_protos is not None`, so no-helper and
    # inline-only ports never enter here.
    if (not ok) and (shared_protos is not None):
        system, user = build_prompt(spec, inline_skeleton, shared_protos=None)
        body = complete_fn(system, user)
        cpp  = _splice(inline_skeleton, body)
        with open(cpp_path, "w", encoding="utf-8") as f:
            f.write(cpp)
        ok, log, bundle = compile_cpp(cpp_path, spec, out_dir, maya=maya,
                                       log_cb=log_cb)
        rounds2 = 0
        while not ok and rounds2 < max_fix_rounds:
            rounds2 += 1
            fix_user = (
                "The C++ below did not compile. Fix ONLY the compute body (the "
                "code between the PORT markers) and output the corrected body "
                "statements only (no fences, no signature).\n\n"
                "Compiler errors:\n%s\n\nCurrent file:\n```cpp\n%s\n```\n"
                % (log[-4000:], cpp)
            )
            body = complete_fn(system, fix_user)
            cpp  = _splice(inline_skeleton, body)
            with open(cpp_path, "w", encoding="utf-8") as f:
                f.write(cpp)
            ok, log, bundle = compile_cpp(cpp_path, spec, out_dir, maya=maya,
                                       log_cb=log_cb)
        rounds += rounds2

    # Stage 2, emitted AFTER the fix-loop and the inline retry so it is the
    # source that actually reached the compiler -- not the model's first answer.
    _stage("2_assisted", cpp)

    # Always emit the build + verify helpers (platform-appropriate build
    # script: build.sh on macOS/Linux, build.bat on Windows).
    build_name, build_src = codegen.generate_build_script(spec, maya=maya)
    build_path = os.path.join(out_dir, build_name)
    with open(build_path, "w", encoding="utf-8") as f:
        f.write(build_src)
    if not toolchain.is_windows():
        os.chmod(build_path, 0o755)
    # The Windows script force-includes this by bare name: keep it beside
    # the .cpp (toolchain.QT_MSVC_COMPAT_HEADER).
    toolchain.ship_qt_msvc_compat_header(out_dir, bool(spec.get("needs_hover")))
    verify_path = os.path.join(out_dir, "verify_in_maya.py")
    with open(verify_path, "w", encoding="utf-8") as f:
        f.write(_verify_script(spec))

    return {
        "ok":            ok,
        "node":          name,
        "cpp":           cpp_path,
        "bundle":        bundle if ok else None,
        "fix_rounds":    rounds,
        "compiler_log":  log,
        "verify_script": verify_path,
    }


def port_from_node(node: str, out_dir: str, complete_fn=None,
                   max_fix_rounds: int = 4, maya: str = _MAYA_DEFAULT,
                   type_name: str = None) -> dict:
    """In-Maya convenience: extract a live mPyNode's spec, then port it.

    ``type_name`` overrides the generated node type name (defaults to the scene
    node's sanitized name when None) -- e.g. node 'bubbleSort' -> 'bubbleSorter'.
    """
    from mpynode.native.spec import spec_extractor

    spec = spec_extractor.extract_spec(node)
    return port_node(spec, out_dir, complete_fn=complete_fn,
                     max_fix_rounds=max_fix_rounds, maya=maya,
                     type_name=type_name)
