"""Compile ONE template .mpn into a native plugin, as a Node Designer user would
with model=claude-opus-4-8[1m], a reliable reasoning effort, ultracode optional.

Usage (under mayapy):
    mayapy compile_one.py <mpn_path> <out_dir> <plugin_name> [demo_label]

Writes <out_dir>/compile.log (full pipeline narrative + timing) and prints a
single JSON summary line prefixed with 'RESULT_JSON:' as the LAST stdout line.

This is the Part-2 compile workhorse: one fresh mayapy process per template so
each build is isolated (a crash in one never poisons another).
"""
import os
import sys
import json
import time
import traceback

MPN_PATH = sys.argv[1]
OUT_DIR = sys.argv[2]
PLUGIN_NAME = sys.argv[3]
DEMO_LABEL = sys.argv[4] if len(sys.argv) > 4 else PLUGIN_NAME

MODEL = os.environ.get("MPYNODE_PORT_MODEL", "claude-opus-4-8[1m]")
# Porter effort default = 'high' (overridable via MPYNODE_PORT_EFFORT).
#
# T8 finding (2026-07-16): 'max' is a NET REGRESSION for a HARD port. A single
# effort=max porter call on procrustes_single TIMED OUT (>900s; orchestrate=on
# hit even the 1800s ceiling in ONE round) -> the node DROPS. The SAME node ports
# CLEANLY at effort=high in ~180s. Deterministically-LOWERED nodes never invoke
# the porter at all, so effort is irrelevant to them; effort only affects the
# minority that reach the AI porter, where 'high' reliably completes within the
# default 600s MPYNODE_PORT_TIMEOUT (see llm_client._cli_timeout). Every shipped
# AI-ported artifact was in fact built at 'high', so this makes the harness
# default match actual practice + stop under-reporting portability. 'max' remains
# available as an explicit escalation (MPYNODE_PORT_EFFORT=max, ideally paired
# with a larger MPYNODE_PORT_TIMEOUT) when a node fails to port at 'high'.
EFFORT = os.environ.get("MPYNODE_PORT_EFFORT", "high")
MAYA_ROOT = os.environ.get("MPYNODE_MAYA_ROOT", "/Applications/Autodesk/maya2026")

os.makedirs(OUT_DIR, exist_ok=True)
LOG_PATH = os.path.join(OUT_DIR, "compile.log")
_logf = open(LOG_PATH, "w")


def L(msg=""):
    _logf.write(str(msg) + "\n")
    _logf.flush()


def _hr(title):
    L("\n" + "=" * 78)
    L(title)
    L("=" * 78)


summary = {
    "demo": DEMO_LABEL,
    "mpn": MPN_PATH,
    "plugin": PLUGIN_NAME,
    "out_dir": OUT_DIR,
    "ok": False,
    "bundle_path": None,
    "manifest_path": None,
    "companions": [],
    "nodes": [],
    "ai_ported": False,
    "errors": [],
    "seconds": None,
}

try:
    _hr("NODE DESIGNER NATIVE COMPILE  ::  %s" % DEMO_LABEL)
    L("template .mpn : %s" % MPN_PATH)
    L("output folder : %s" % OUT_DIR)
    L("plugin name   : %s" % PLUGIN_NAME)
    L("time (start)  : %s" % time.strftime("%Y-%m-%d %H:%M:%S"))

    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc
    for p in ("mpynode_api1", "mpynode_api2"):
        try:
            if not mc.pluginInfo(p, q=True, loaded=True):
                mc.loadPlugin(p, quiet=True)
        except Exception as exc:
            L("WARN could not load %s: %r" % (p, exc))

    # ---- Configure the compile exactly as a user would in the AI settings ----
    _hr("AI SETTINGS (as a Node Designer user)")
    from mpynode.ui.llm import config as _cfg
    _cfg.set_provider("claude_cli")
    _cfg.set_model("claude_cli", MODEL)
    _cfg.set_effort("claude_cli", EFFORT)
    try:
        _cfg.set_multiagent("claude_cli", True)  # ultracode requested
    except Exception as exc:
        L("note: set_multiagent unavailable: %r" % exc)
    # Porter "ultracode" (Task fan-out) is OPT-IN and default OFF: an e2e showed it
    # is impractically slow for a hard port (procrustes_single timed out at 1800s
    # in one round). The high-value "ultracode-quality" bits -- max reasoning +
    # real chain-of-thought capture (stream-json) + the prose/ASCII output guard --
    # are ALWAYS on for claude_cli regardless. Set MPYNODE_PORT_ULTRACODE=1 to
    # experiment with the multi-agent fan-out.
    os.environ.setdefault("MPYNODE_PORT_ULTRACODE", "0")
    _orch = os.environ.get("MPYNODE_PORT_ULTRACODE", "0").strip().lower() \
        not in ("", "0", "false", "no", "off")
    L("provider   : claude_cli")
    L("model      : %s" % MODEL)
    L("effort     : %s (max reasoning)" % EFFORT)
    L("ultracode  : max effort + real CoT capture (stream-json) + prose/ASCII "
      "output guard are ALWAYS on (#5). Multi-agent Task fan-out: %s (opt-in; slow "
      "-- see MPYNODE_PORT_ULTRACODE)." % ("ON" if _orch else "OFF"))
    L("CLAUDE_BIN : %s" % os.environ.get("CLAUDE_BIN", "(claude on PATH)"))

    # ---- Live pipeline stream --------------------------------------------
    _hr("COMPILE PIPELINE STREAM  (deterministic lowering -> codegen -> "
        "assemble -> verify; AI porter only if a compute cannot be lowered)")
    events = []
    # Reliable porter markers (native/ai/porter.py): the deterministic path logs
    # "deterministic compute (verified helpers)"; the AI path logs "requesting AI
    # compute body" and "compile failed; AI fix round N/M".
    AI_MARK = "requesting ai compute body"
    DET_MARK = "deterministic compute (verified helpers)"
    FIX_MARK = "ai fix round"
    seen = {"ai": False, "det": False, "fix": 0}

    def progress_cb(ev):
        try:
            events.append(ev)
            stage = ev.get("stage")
            status = ev.get("status")
            node = ev.get("node")
            detail = ev.get("detail", "")
            if stage == "log":
                L("    | %s" % detail)
            else:
                idx = ev.get("i")
                n = ev.get("n")
                pos = ("[%s/%s] " % (idx, n)) if n else ""
                L(">>> %s%s : %s%s%s" % (
                    pos, stage, status,
                    (" (" + str(node) + ")") if node else "",
                    (" -- " + str(detail)) if detail else ""))
            low = str(detail).lower()
            if AI_MARK in low:
                seen["ai"] = True
            if DET_MARK in low:
                seen["det"] = True
            if FIX_MARK in low:
                seen["fix"] += 1
        except Exception:
            pass

    from mpynode.native.toolchain import compile_controller as cc
    from mpynode.native.toolchain import verify as _verify_mod

    # The `verify=True` param used to SHADOW the imported `verify` module (default
    # parity raised "'bool' object has no attribute '_default_verify'"); that was
    # FIXED (compile_controller aliases `import verify as _verify_mod`). We still
    # pass the documented verify_fn hook explicitly so the audit pins the exact
    # MAYA_ROOT used for the in-process parity check.
    def _verify_fn(bundle_path, rows):
        return _verify_mod._default_verify(bundle_path, rows, maya=MAYA_ROOT)

    t0 = time.time()
    result = cc.compile_from_mpn_paths(
        [MPN_PATH],
        PLUGIN_NAME,
        OUT_DIR,
        trusted=True,
        provider="claude_cli",
        model=MODEL,
        maya=MAYA_ROOT,
        strict=True,
        verify=True,
        verify_fn=_verify_fn,
        progress_cb=progress_cb,
        reuse_cache=False,   # audit: force a real build, no cached .cpp reuse
        bake_persistent=True,
    )
    dt = time.time() - t0
    summary["seconds"] = round(dt, 1)
    summary["ai_ported"] = bool(seen["ai"])
    summary["deterministic"] = bool(seen["det"])
    summary["ai_fix_rounds"] = seen["fix"]

    # ---- Per-node result -------------------------------------------------
    _hr("PER-NODE RESULT")
    summary["ok"] = bool(result.get("ok"))
    summary["bundle_path"] = result.get("bundle_path")
    summary["manifest_path"] = result.get("manifest_path")
    for comp in (result.get("companions") or []):
        cp = comp.get("path") if isinstance(comp, dict) else comp
        if cp:
            summary["companions"].append(cp)
    for row in (result.get("nodes") or []):
        tn = row.get("type_name")
        bs = row.get("build_status")
        v = row.get("verify") or {}
        fr = row.get("fix_rounds")
        node_rec = {
            "type_name": tn,
            "build_status": bs,
            "verify_ran": v.get("ran"),
            "verify_pass": v.get("pass"),
            "verify_maxerr": v.get("maxerr"),
            "verify_tol": v.get("tol"),
            "verify_reason": v.get("reason"),
            "fix_rounds": fr,
        }
        summary["nodes"].append(node_rec)
        L("node          : %s" % tn)
        L("  build_status: %s" % bs)
        L("  verify      : ran=%s pass=%s maxerr=%s tol=%s reason=%s"
          % (v.get("ran"), v.get("pass"), v.get("maxerr"),
             v.get("tol"), v.get("reason")))
        if fr is not None:
            L("  fix_rounds  : %s (compiler-error feedback loops to the AI)" % fr)
        # Dump every other key on the row (compiler_log, cache, id, ...)
        for k, val in row.items():
            if k in ("type_name", "build_status", "verify", "fix_rounds"):
                continue
            sval = str(val)
            if len(sval) > 4000:
                sval = sval[:4000] + " ...[truncated]"
            L("  %-11s : %s" % (k, sval))

    for e in (result.get("errors") or []):
        summary["errors"].append(str(e))
        L("ERROR: %s" % e)

    # ---- How the C++ was produced (the 'internal discussion') ------------
    _hr("HOW THE C++ WAS GENERATED")
    if summary["ai_ported"]:
        L("This node required the AI PORTER: its numpy compute could not be")
        L("deterministically lowered, so the compiler asked Claude (opus 4.8")
        L("1M ctx, effort=max, ultracode) to translate the compute body to C++,")
        L("then ran a bounded compile/fix loop feeding compiler errors back to")
        L("the model. As of #5 the porter streams --output-format stream-json, so")
        L("the model's chain-of-thought (thinking) + tool/sub-agent activity is")
        L("captured inline above (the '| [thinking] ...' lines) and in the durable")
        L("per-node compile.log; only the final C++ answer is spliced into the .cpp.")
    else:
        L("This node was lowered DETERMINISTICALLY (nd_lower -> pure C++). No LLM")
        L("was invoked: the numpy compute mapped 1:1 onto typed C++ via the")
        L("transpiler (array/vector/matrix ops -> nd::runtime), so the 'internal")
        L("discussion' is the deterministic lowering + codegen recorded above,")
        L("and the output is bit-faithful to the Python interpretation by")
        L("construction (confirmed by the parity verify).")

    # ---- Emit the generated C++ into the log for the record --------------
    for row in (result.get("nodes") or []):
        tn = row.get("type_name")
        # Clean assembled source lives under build/source/ (the per-node scratch
        # build/<type>/ is removed after a successful build).
        cpp = os.path.join(OUT_DIR, "build", "source", tn + ".cpp")
        if os.path.isfile(cpp):
            _hr("GENERATED C++  ::  %s.cpp" % tn)
            with open(cpp) as f:
                _logf.write(f.read())
            _logf.write("\n")
            _logf.flush()

    _hr("TIMING")
    mins = int(dt // 60)
    secs = int(dt % 60)
    if summary["ok"]:
        L("Compiled in %d:%02d (%.1fs)" % (mins, secs, dt))
    else:
        L("Compile FAILED after %d:%02d (%.1fs)" % (mins, secs, dt))
    L("time (end)    : %s" % time.strftime("%Y-%m-%d %H:%M:%S"))

except Exception as exc:
    summary["errors"].append("HARNESS EXCEPTION: %r" % exc)
    L("\n!!! HARNESS EXCEPTION !!!")
    L(traceback.format_exc())
finally:
    _logf.close()
    print("RESULT_JSON:" + json.dumps(summary))
    try:
        import maya.standalone
        maya.standalone.uninitialize()
    except Exception:
        pass
    sys.exit(0 if summary.get("ok") else 1)
