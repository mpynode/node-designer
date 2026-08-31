"""Compile ONE template to C++ for the model x ultracode sweep, and report.

One invocation = one cell of the Task-3 matrix. Everything that varies between
cells (model, effort, ultracode, round count, agent budget) is supplied through
the environment by the runner, so this script stays a constant:

    MPYNODE_PREFS           per-run preferences.json carrying the model+effort
    MPYNODE_PORT_ULTRACODE  1 / unset
    MPYNODE_OPT_ROUNDS      optimize rounds (1 for the sweep)
    MPYNODE_OPT_TIMEOUT     per-round agent wall clock

It compiles and writes the spec next to the bundle; MEASUREMENT is deliberately
left to a separate `benchmark_node.py` process, because a bundle must be timed in
a fresh Maya (a plug-in cannot be reloaded in-process, so timing it here would
silently re-measure whatever verify already loaded).

    mayapy tools/sweep_compile_one.py --template <t.mpn> --out <dir>
           [--optimize] [--json-out <f.json>]
"""
import argparse
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def L(m=""):
    print(m, flush=True)


def _heartbeat_needles():
    """Wording that marks a liveness tick from ``optimizer_live._Heartbeat``.

    Derived from the heartbeat's own sub-phase table so a new phase cannot start
    landing in the record unnoticed -- the hand-copied pair that used to live
    here had already drifted ("-- still working" matched nothing the code emits,
    and none of the five sub-phases were filtered at all). The two phases below
    are named literally because no adapter owns them: ``_Heartbeat`` emits them
    itself. Its one-shot "optimizing -- measuring baseline" opener is NOT a
    needle -- that line reports a fact and is kept.
    """
    from mpynode.native.ai import optimizer_live as ol

    return tuple(["-- " + phase for _key, phase in ol._ADAPTER_PHASES]
                 + ["baseline -- measuring", "finishing up"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--optimize", action="store_true")
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--type-name", default=None)
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc
    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p)

    from mpynode._common.io import mpn_io
    from mpynode.native.spec.mpn_spec_adapter import spec_from_mpn_payload
    from mpynode.native.toolchain import compile_controller as cc

    out_dir = args.out
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    payload = mpn_io.load_mpn(args.template, trusted=True)
    spec = spec_from_mpn_payload(payload)
    if args.type_name:
        spec.setdefault("suggested", {})["node_type_name"] = args.type_name
    tname = spec.get("suggested", {}).get("node_type_name")

    rec = {
        "template": args.template,
        "type_name": tname,
        "optimize": bool(args.optimize),
        "model": os.environ.get("_SWEEP_MODEL", ""),
        "ultracode": os.environ.get("MPYNODE_PORT_ULTRACODE", "") or "off",
        "rounds": os.environ.get("MPYNODE_OPT_ROUNDS", ""),
        "budget_s": os.environ.get("MPYNODE_OPT_TIMEOUT", ""),
        "needs_llm": None, "ok": False, "bundle": None,
        "optimize_summary": {}, "wall_s": None, "events": [],
    }

    try:
        rec["needs_llm"] = bool(cc._node_needs_llm(spec))
    except Exception as exc:
        rec["needs_llm"] = "error: %s" % exc

    # Heartbeats would drown the record; they carry no result. See
    # _heartbeat_needles for why the list is derived rather than written out.
    needles = _heartbeat_needles()

    def cb(ev):
        if ev.get("stage") in ("optimize", "verify", "port", "assemble"):
            line = "[%s %s] %s" % (ev.get("stage"), ev.get("status"),
                                   (ev.get("detail") or "")[:200])
            if not any(n in line for n in needles):
                rec["events"].append(line)
                L("   " + line)

    t0 = time.time()
    try:
        res = cc.compile_plugin([spec], (tname or "sweep") + "Cmp", out_dir,
                                strict=False, verify=True, reuse_cache=True,
                                optimize=bool(args.optimize), progress_cb=cb)
        rec["ok"] = bool(res.get("ok"))
        rec["bundle"] = res.get("bundle_path")
        rec["optimize_summary"] = res.get("optimize") or {}
    except Exception as exc:
        import traceback
        rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        rec["traceback"] = traceback.format_exc()[-2000:]
    rec["wall_s"] = round(time.time() - t0, 1)

    # The benchmark process needs the spec to seed every input and pull every
    # output; write it beside the bundle so the runner can point at it.
    try:
        with open(os.path.join(out_dir, "_sweep_spec.json"), "w") as fh:
            json.dump(spec, fh)
    except Exception:
        pass

    if args.json_out:
        with open(args.json_out, "w") as fh:
            json.dump(rec, fh, indent=2)
    L("")
    L("SWEEP_JSON:" + json.dumps(rec))
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
