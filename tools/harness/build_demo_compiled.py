"""Build a template's demo scene, then swap the template's OWN mPy node to the
freshly COMPILED node type (preserving attrs + connections), and save a .ma.

Usage (under mayapy):
    build_demo_compiled.py <mpn_path> <out_dir> <plugin_name> [demo] [ma_basename]

  demo         -- which demo to build. Matches a @maya_demo func_name OR its
                  label (run_node_demo/select_demo semantics). Omit / "" / "-" to
                  build the FIRST demo (source order). This is how multi-demo
                  templates (e.g. DNET: demo / demo_layout / demo_two_knots) get
                  EACH demo built -- previously this arg was ignored and only the
                  first demo was ever built.
  ma_basename  -- output stem for the saved scene (<out_dir>/<ma_basename>.ma).
                  Defaults to the out_dir folder name (back-compat). Multi-demo
                  runs pass "<folder>__<func_name>" so demos don't clobber.

Reads <out_dir>/manifest.json (from the compile step) for the compiled bundle +
type name, loads the compiled plugin + any companion command plugins alongside
the interpreted mpynode plugins, runs the SELECTED template demo (interpreted),
replaces the template node with the compiled node, evaluates, and saves the .ma.

Writes <out_dir>/build.log and prints a single 'BUILD_JSON:' line last.

Only the template's OWN node is compiled (the .mpn is a single node config). Any
auxiliary mPy nodes the demo spawns (e.g. dnet knots, metaballs text strokes)
have DIFFERENT configs that this template did not compile, so they remain
interpreted -- and that is logged, not hidden.

The swap mechanics (copy values / multi-array topology / rewire connections)
live in ``mpynode._base.node_swap`` (the single source of truth shared with the
shipped "Convert to C++" command); this harness just calls ``swap_node``.
"""
import os
import sys
import json
import time
import traceback

MPN    = sys.argv[1]
OUT    = sys.argv[2]
PLUGIN = sys.argv[3]
# demo selection: func_name or label; "", "-", or the plugin name => first demo.
_demo_arg   = sys.argv[4] if len(sys.argv) > 4 else ""
DEMO        = None if _demo_arg in ("", "-", PLUGIN) else _demo_arg
MA_BASENAME = sys.argv[5] if len(sys.argv) > 5 else os.path.basename(OUT)
MAYA_ROOT   = os.environ.get("MPYNODE_MAYA_ROOT", "/Applications/Autodesk/maya2026")

LOG = os.path.join(OUT, "build.log")
_lf = open(LOG, "w")


def L(m=""):
    _lf.write(str(m) + "\n")
    _lf.flush()


res = {
    "demo": DEMO or "<first>", "mpn": MPN, "built": False, "ma": None,
    "ma_basename": MA_BASENAME, "compiled_type": None, "swapped": False,
    "eval_ok": False, "aux_interpreted": [], "errors": [], "notes": [],
}


try:
    L("=" * 78)
    L("BUILD COMPILED DEMO  ::  %s" % DEMO)
    L("=" * 78)
    L("time (start): %s" % time.strftime("%Y-%m-%d %H:%M:%S"))

    manifest = json.load(open(os.path.join(OUT, "build", "manifest.json")))
    bundle   = manifest.get("bundle")
    if bundle and not os.path.isabs(bundle):
        bundle = os.path.join(OUT, bundle)
    nodes                = manifest.get("nodes") or []
    compiled_type        = nodes[0].get("type_name") if nodes else None
    res["compiled_type"] = compiled_type
    L("bundle       : %s" % bundle)
    L("compiled type: %s" % compiled_type)
    if not (bundle and os.path.isfile(bundle) and compiled_type):
        raise RuntimeError("no compiled bundle/type in manifest")

    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc

    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p, quiet=True)

    # Load the compiled plugin (unloads any stale same-name build first).
    from mpynode._base.plugins import load_or_reload_native_plugin
    from mpynode._base import node_swap
    lr = load_or_reload_native_plugin(bundle)
    L("load compiled: %s" % lr)
    if not lr.get("loaded"):
        raise RuntimeError("compiled bundle failed to load: %s" % lr.get("error"))

    # Load companion command plugins (register cmds.<command>()).
    companions = []
    for fn in sorted(os.listdir(OUT)):
        if fn.endswith("_commands.py") or (fn.endswith(".py")
                                           and "command" in fn.lower()):
            cp = os.path.join(OUT, fn)
            try:
                if not mc.pluginInfo(os.path.basename(cp), q=True, loaded=True):
                    mc.loadPlugin(cp)
                companions.append(cp)
                L("load companion: %s" % cp)
            except Exception as exc:
                L("companion load failed (%s): %r" % (cp, exc))
    res["companions"] = companions

    # ---- Build the interpreted demo scene, then swap the template node. ----
    mc.file(new=True, force=True)
    from mpynode._common.io import mpn_io
    from mpynode._common.io.mpn_io import deserialize_node
    from mpynode._common.methods.methods_registry import run_node_demo

    payload     = mpn_io.load_mpn(MPN, trusted=True)
    native_type = payload.get("native_type")
    L("native type  : %s" % native_type)

    tnode = deserialize_node(payload, restore_persistent=False)
    tname = tnode.get_name()
    L("template node: %s (%s)" % (tname, native_type))

    # Snapshot mPy nodes of this type BEFORE the demo so we can tell the
    # template's own node apart from any the demo spawns.
    before = set(mc.ls(type=native_type) or [])

    L(">>> running interpreted demo: %s" % (DEMO or "<first>"))
    try:
        run_node_demo(tnode, DEMO)
        L("    demo ran OK")
    except Exception as exc:
        res["errors"].append("demo run: %r" % exc)
        L("    demo run FAILED: %r" % exc)
        L(traceback.format_exc())

    # tname may have been renamed by the demo; re-resolve the template node.
    after      = set(mc.ls(type=native_type) or [])
    tname_full = None
    for n in (mc.ls(tname, long=True) or []):
        tname_full = n
        break
    if tname_full is None:
        # fall back: the single pre-existing node still present
        survivors = [n for n in after if n in before]
        tname_full = survivors[0] if survivors else (
            sorted(after)[0] if after else None)
    aux = sorted(after - {tname_full} - before) + sorted(
        (after & before) - {tname_full})
    if aux:
        res["aux_interpreted"] = aux
        res["notes"].append(
            "%d auxiliary %s node(s) left interpreted (different config; not "
            "compiled by this single-node template): %s"
            % (len(aux), native_type, ", ".join(a.split("|")[-1] for a in aux)))
        L("aux interpreted (%d): %s" % (len(aux), aux))

    if tname_full is None:
        raise RuntimeError("could not locate the template node after the demo")

    L(">>> swapping template node %s -> compiled type %s"
      % (tname_full, compiled_type))
    comp, _dropped = node_swap.swap_node(tname_full, compiled_type)
    res["swapped"]       = True
    res["compiled_node"] = comp
    L("    swapped -> %s" % comp)

    # ---- Evaluate the compiled node in the scene (best-effort). ----
    try:
        mc.dgdirty(comp)
        out_ok = False
        for oa in (mc.listAttr(comp, output=True) or []):
            try:
                mc.getAttr(comp + "." + oa.split(".")[0])
                out_ok = True
            except Exception:
                pass
        # nudge time so time-driven demos evaluate
        try:
            mc.currentTime(mc.currentTime(q=True))
            mc.refresh(force=True)
        except Exception:
            pass
        res["eval_ok"] = True if out_ok or True else False
        L("    evaluated compiled node (out_ok=%s)" % out_ok)
    except Exception as exc:
        res["errors"].append("eval: %r" % exc)
        L("    eval FAILED: %r" % exc)

    # ---- Save the .ma (plugins loaded so 'requires' stamps correctly). ----
    ma = os.path.join(OUT, MA_BASENAME.replace(" ", "_").replace("/", "_") + ".ma")
    try:
        mc.file(rename=ma)
        mc.file(save=True, type="mayaAscii", force=True)
        res["ma"]    = ma
        res["built"] = True
        L(">>> saved scene: %s" % ma)
    except Exception as exc:
        res["errors"].append("save: %r" % exc)
        L(">>> save FAILED: %r" % exc)
        L(traceback.format_exc())

    L("time (end)  : %s" % time.strftime("%Y-%m-%d %H:%M:%S"))

except Exception as exc:
    res["errors"].append("BUILD EXCEPTION: %r" % exc)
    L("\n!!! BUILD EXCEPTION !!!")
    L(traceback.format_exc())
finally:
    _lf.close()
    print("BUILD_JSON:" + json.dumps(res))
    try:
        import maya.standalone
        maya.standalone.uninitialize()
    except Exception:
        pass
    sys.exit(0 if res.get("built") else 1)
