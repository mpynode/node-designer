"""Build a template's demo scene against the MEGA plugin.

Same contract as ``build_demo_compiled.py`` -- run the template's demo
interpreted, then swap the template's OWN mPy node to the COMPILED node type
(preserving attrs + connections) and save a .ma -- with ONE difference: the
compiled type comes from the single MEGA bundle (every template node type linked
together) instead of a per-template bundle.

Usage (under mayapy):
    build_demo_mega.py <mpn> <out_dir> <mega_bundle> <compiled_type>
                       [demo] [ma_basename]

  demo         -- @maya_demo func_name or its label; "" / "-" builds the FIRST
                  demo in source order (run_node_demo/select_demo semantics).
  ma_basename  -- output stem; defaults to the out_dir folder name. Multi-demo
                  templates pass "<folder>__<func_name>" so demos don't clobber.

Writes <out_dir>/build.log and prints a single 'BUILD_JSON:' line last.

Only the template's OWN node is swapped. Auxiliary mPy nodes a demo spawns have
DIFFERENT configs that no template compiled, so they stay interpreted -- logged,
not hidden. The swap mechanics live in ``mpynode._base.node_swap`` (shared with
the shipped "Convert to C++" command); this harness just calls ``swap_node``.
"""
import os
import sys
import json
import time
import traceback

MPN = sys.argv[1]
OUT = sys.argv[2]
BUNDLE = sys.argv[3]
COMPILED_TYPE = sys.argv[4]
_demo_arg = sys.argv[5] if len(sys.argv) > 5 else ""
DEMO = None if _demo_arg in ("", "-") else _demo_arg
MA_BASENAME = sys.argv[6] if len(sys.argv) > 6 else os.path.basename(OUT)
MAYA_ROOT = os.environ.get("MPYNODE_MAYA_ROOT", "/Applications/Autodesk/maya2026")

os.makedirs(OUT, exist_ok=True)
LOG = os.path.join(OUT, "build.log")
_lf = open(LOG, "w")


def L(m=""):
    _lf.write(str(m) + "\n")
    _lf.flush()


res = {
    "demo": DEMO or "<first>", "mpn": MPN, "built": False, "ma": None,
    "ma_basename": MA_BASENAME, "compiled_type": COMPILED_TYPE,
    "swapped": False, "eval_ok": False, "aux_interpreted": [],
    "errors": [], "notes": [], "via": "mega",
}


try:
    L("=" * 78)
    L("BUILD MEGA DEMO  ::  %s" % (DEMO or "<first>"))
    L("=" * 78)
    L("time (start) : %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    L("mega bundle  : %s" % BUNDLE)
    L("compiled type: %s" % COMPILED_TYPE)
    if not (BUNDLE and os.path.exists(BUNDLE)):
        raise RuntimeError("mega bundle not found: %s" % BUNDLE)

    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc

    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p, quiet=True)

    from mpynode._base.plugins import load_or_reload_native_plugin
    from mpynode._base import node_swap
    lr = load_or_reload_native_plugin(BUNDLE)
    L("load mega    : %s" % lr)
    if not lr.get("loaded"):
        raise RuntimeError("mega bundle failed to load: %s" % lr.get("error"))

    registered = mc.pluginInfo(BUNDLE, q=True, dependNode=True) or []
    L("registered   : %d type(s)" % len(registered))
    if COMPILED_TYPE not in registered:
        raise RuntimeError("type %r not registered by the mega bundle (has %s)"
                           % (COMPILED_TYPE, registered[:8]))

    # Companion @maya_command plugins that ship beside the mega bundle.
    companions = []
    mega_dir = os.path.dirname(BUNDLE)
    for fn in sorted(os.listdir(mega_dir)):
        if fn.endswith("_commands.py") or (fn.endswith(".py")
                                           and "command" in fn.lower()):
            cp = os.path.join(mega_dir, fn)
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

    payload = mpn_io.load_mpn(MPN, trusted=True)
    native_type = payload.get("native_type")
    L("native type  : %s" % native_type)

    tnode = deserialize_node(payload, restore_persistent=False)
    tname = tnode.get_name()
    L("template node: %s (%s)" % (tname, native_type))

    # long=True on BOTH sides: tname_full below is a long name, so short-name
    # sets never cancelled it and the template's OWN node -- the one that gets
    # swapped -- was reported as "left interpreted" on every template whose node
    # survives its demo. The note already shortens with a.split("|")[-1].
    before = set(mc.ls(type=native_type, long=True) or [])

    L(">>> running interpreted demo: %s" % (DEMO or "<first>"))
    try:
        run_node_demo(tnode, DEMO)
        L("    demo ran OK")
    except Exception as exc:
        res["errors"].append("demo run: %r" % exc)
        L("    demo run FAILED: %r" % exc)
        L(traceback.format_exc())

    after = set(mc.ls(type=native_type, long=True) or [])
    tname_full = None
    for n in (mc.ls(tname, long=True) or []):
        tname_full = n
        break
    if tname_full is None:
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

    L(">>> swapping %s -> mega compiled type %s" % (tname_full, COMPILED_TYPE))
    comp, _dropped = node_swap.swap_node(tname_full, COMPILED_TYPE)
    res["swapped"] = True
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
        try:
            mc.currentTime(mc.currentTime(q=True))
            mc.refresh(force=True)
        except Exception:
            pass
        res["eval_ok"] = True
        L("    evaluated compiled node (out_ok=%s)" % out_ok)
    except Exception as exc:
        res["errors"].append("eval: %r" % exc)
        L("    eval FAILED: %r" % exc)

    # A demo asset can import nodes this mayapy has no plug-in for -- Mesh
    # Regions' head.ma creates 7 mtoa render-settings nodes but carries no
    # `requires mtoa`, so Maya keeps them as `unknown` and then refuses to write
    # the scene AT ALL ("unknown data ... preventing Maya from changing the file
    # format"). They are leaf render settings no demo reads, so drop them --
    # recorded in notes, never silent.
    unknown = []
    for _ut in ("unknown", "unknownDag", "unknownTransform"):
        unknown += (mc.ls(type=_ut) or [])
    if unknown:
        gone, kept = [], []
        for n in unknown:
            try:
                mc.lockNode(n, lock=False)   # defaultArnoldRenderOptions is -shared
            except Exception:
                pass
            try:
                mc.delete(n)
                gone.append(n)
            except Exception as exc:
                kept.append("%s (%r)" % (n, exc))
        if gone:
            res["notes"].append(
                "%d unknown node(s) removed before save -- no plug-in in this "
                "mayapy provides them: %s" % (len(gone), ", ".join(gone)))
            L("unknown removed (%d): %s" % (len(gone), gone))
        if kept:
            res["notes"].append("unknown node(s) that could NOT be removed: %s"
                                % "; ".join(kept))
            L("unknown NOT removed: %s" % kept)

    # ---- Save the .ma (plugins loaded so 'requires' stamps correctly). ----
    ma = os.path.join(OUT, MA_BASENAME.replace(" ", "_").replace("/", "_") + ".ma")
    try:
        mc.file(rename=ma)
        mc.file(save=True, type="mayaAscii", force=True)
        res["ma"] = ma
        res["built"] = True
        L(">>> saved scene: %s" % ma)
    except Exception as exc:
        res["errors"].append("save: %r" % exc)
        L(">>> save FAILED: %r" % exc)
        L(traceback.format_exc())

    L("time (end)   : %s" % time.strftime("%Y-%m-%d %H:%M:%S"))

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
