"""Combine EVERY template node type -- and all their @maya_command companion
commands -- into ONE native plugin (.bundle).  First-ever exercise of the
bundler's multi-node + companion-command aggregation across the whole gallery.

Run inside mayapy with the same env compile_one.py uses:

    export MPYNODE_ROOT=$PWD MPYNODE_USE_STUDIO=1 \
           PYTHONPATH=$PWD/scripts MAYA_PLUG_IN_PATH=$PWD/plug-ins \
           QT_QPA_PLATFORM=offscreen
    "$MAYAPY" tools/harness/mega_plugin.py <out_dir> [plugin_name]

Best-effort (strict=False): unportable nodes (Phase-0 honest-drops, unsupported
attrs) drop out with a recorded reason; every portable node links into the one
bundle.  verify=False -- per-node parity is already established by the per-template
audit; here we prove they all CO-EXIST + LINK + register in a single plugin.
Writes mega_results.json next to the bundle.
"""
import os, sys, json, time

HARNESS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HARNESS))            # project root
AUDIT_ROOT = os.path.join(ROOT, "compiled_templates")       # audit output root

MODEL = os.environ.get("MPYNODE_PORT_MODEL", "claude-opus-4-8[1m]")
EFFORT = os.environ.get("MPYNODE_PORT_EFFORT", "high")

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(AUDIT_ROOT,
                                                             "_combined_plugin")
PLUGIN_NAME = sys.argv[2] if len(sys.argv) > 2 else "mPyMega"

# MPYNODE_MEGA_FROM_ARTIFACTS=1 links the per-template artifacts that already sit
# in compiled_templates/ instead of re-porting each .mpn. Those artifacts are the
# BEST code for every node: the optimizer promotes its accepted winner to
# build/<type>/<type>.cpp and leaves the ported baseline there when no candidate
# wins, so the gather needs no selection logic. The default path is unchanged --
# there is no cross-build cache for optimized .cpp (port_cache.put runs only on
# the port path), so re-porting can only ever produce the un-optimized code, and
# keeping both modes means the ported mega stays reproducible for comparison.
FROM_ARTIFACTS = os.environ.get("MPYNODE_MEGA_FROM_ARTIFACTS", "0") == "1"


def L(msg=""):
    print(msg, flush=True)


def _hr(t):
    L("=" * 78); L(t); L("=" * 78)


def _artifact_for(entry):
    """``(type_name, cpp_path)`` for a chosen template, or ``(None, None)``.

    Resolved from the template's own .mpn path
    (``templates/<Family>/<Template>/template.mpn`` ->
    ``compiled_templates/<Family>/<Template>/build/<type>/<type>.cpp``) rather
    than from ``native_type``, which carries the mPy BASE type (mPyFile) and not
    the compiled node type (fileTexture).

    The type comes from ``build/manifest.json``'s ``nodes[].type_name``, not from
    a listdir of ``build/``: a directory left behind by an earlier build is
    invisible to the manifest but not to a listdir. Mesh Regions has a stale
    ``build/meshRegions/`` beside the live ``build/meshRegionLocator/``, and
    ``entry["source"]`` is the source NODE NAME (``meshRegions``) -- matching the
    two picked the dead artifact and shipped a mega that could not read
    ``MPyLocator_Mesh_Regions.ma``.
    """
    tdir = os.path.dirname(entry.get("mpn") or "")
    if not tdir:
        return None, None
    build = os.path.join(ROOT, "compiled_templates",
                         os.path.basename(os.path.dirname(tdir)),
                         os.path.basename(tdir), "build")
    try:
        with open(os.path.join(build, "manifest.json")) as fh:
            declared = [n.get("type_name")
                        for n in (json.load(fh).get("nodes") or [])]
    except (OSError, ValueError):
        return None, None
    for ty in declared:
        p = os.path.join(build, ty or "", (ty or "") + ".cpp")
        if ty and os.path.isfile(p):
            return ty, p
    return None, None


def _assemble_from_artifacts(chosen, out_dir, plugin_name, maya_root):
    """Link the existing per-template artifacts into one plugin.

    Returns a dict shaped like ``compile_controller.compile_from_mpn_paths``'s
    result so the reporting below is shared between both modes.
    """
    from mpynode.native.compiler import bundler

    nodes, missing = [], []
    for c in chosen:
        ty, cpp = _artifact_for(c)
        if not cpp:
            missing.append(c)
            L("   MISSING ARTIFACT %-22s (%s)"
              % (c.get("source") or "?", c["folder"]))
            continue
        nodes.append((ty, cpp))
    L("   linking %d artifact(s); %d without one" % (len(nodes), len(missing)))

    rep = bundler.assemble(nodes, plugin_name, out_dir, strict=False,
                           maya=maya_root, compile_now=True,
                           log_cb=lambda ev: None)
    drop = set(rep.get("dropped") or [])
    rows = []
    for n in rep.get("nodes") or []:
        name = n.get("name")
        ok_row = n.get("status") == "compiled" and name not in drop
        rows.append({
            "type_name": name,
            "base": "",
            "type_id": n.get("id"),
            "build_status": "compiled" if ok_row else "dropped",
            "build_reason": "" if ok_row else (n.get("reason") or n.get("status")),
        })
    for c in missing:
        rows.append({
            "type_name": c.get("native_type") or c["folder"],
            "base": "", "type_id": None, "build_status": "dropped",
            "build_reason": "no per-template artifact in compiled_templates/ -- "
                            "compile that template first",
        })
    return {
        "ok": bool(rep.get("ok")) and not missing,
        "bundle_path": rep.get("bundle"),
        "manifest_path": None,
        "nodes": rows,
        "errors": [],
        "companions": [],
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    _hr("MEGA-PLUGIN BUILD: combine every template node type into one plugin")

    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as mc
    for p in ("mpynode_api1.py", "mpynode_api2.py"):
        try:
            if not mc.pluginInfo(p, q=True, loaded=True):
                mc.loadPlugin(p)
        except Exception:
            try: mc.loadPlugin(p)
            except Exception as e: L("WARN loadPlugin %s: %s" % (p, e))

    # Porter config (only used for a cache MISS; most nodes hit the warm cache).
    try:
        from mpynode.ui.llm import config as _cfg
        _cfg.set_provider("claude_cli")
        _cfg.set_model("claude_cli", MODEL)
        _cfg.set_effort("claude_cli", EFFORT)
    except Exception as e:
        L("WARN llm config: %s" % e)
    os.environ.setdefault("MPYNODE_PORT_ULTRACODE", "0")

    # ---- collect UNIQUE template .mpn paths (dedup by source_name) ----------
    from demo_specs import load_templates
    templates = load_templates(HARNESS, ROOT)
    seen, paths, chosen = set(), [], []
    for t in templates:
        # Dual-read: templates.json now carries ``node_name`` (old key
        # ``source_name``); tolerate either, then the folder as a last resort.
        src = t.get("node_name") or t.get("source_name") or t["folder"]
        if src in seen:
            L("dedup: skip %-42s (dupe of source %s)" % (t["folder"], src))
            continue
        mpn = os.path.join(ROOT, t["mpn"])
        if not os.path.exists(mpn):
            L("MISSING: %s" % mpn); continue
        seen.add(src)
        paths.append(mpn)
        chosen.append({"folder": t["folder"], "source": src,
                       "native_type": t.get("native_type"), "mpn": mpn})
    L("")
    L("combining %d unique template node(s):" % len(paths))
    for c in chosen:
        L("   %-24s %-20s (%s)" % (c["source"], c["native_type"], c["folder"]))
    L("")

    MAYA_ROOT = os.environ.get("MPYNODE_MAYA_ROOT",
                               "/Applications/Autodesk/maya2026")

    def progress_cb(ev):
        st = ev.get("stage"); status = ev.get("status")
        node = ev.get("node") or "-"
        detail = ev.get("detail") or ""
        if status in ("fail", "drop", "miss", "ok", "hit", "start") and \
           st in ("portability", "port", "assemble", "cache", "verify",
                  "preflight"):
            if st == "cache" and status == "hit":
                return  # quiet the many cache hits
            L("   [%s] %-22s %-6s %s" % (st, node, status, detail[:90]))

    from mpynode.native.toolchain import compile_controller as cc

    t0 = time.time()
    if FROM_ARTIFACTS:
        _hr("assemble from per-template ARTIFACTS -> ONE bundle (best code)")
        result = _assemble_from_artifacts(chosen, OUT_DIR, PLUGIN_NAME, MAYA_ROOT)
    else:
        _hr("compile_from_mpn_paths -> ONE bundle (strict=False, verify=False)")
        result = cc.compile_from_mpn_paths(
            [(p,) for p in paths],
            PLUGIN_NAME,
            OUT_DIR,
            provider="claude_cli",
            model=MODEL,
            strict=False,       # best-effort: drop unportable, link the rest
            verify=False,       # per-node parity already proven; prove co-link here
            reuse_cache=True,   # warm cache from the per-template audit -> fast
            progress_cb=progress_cb,
            maya=MAYA_ROOT,
        )
    dt = time.time() - t0

    _hr("RESULT")
    L("ok            : %s" % result.get("ok"))
    L("bundle_path   : %s" % result.get("bundle_path"))
    L("manifest_path : %s" % result.get("manifest_path"))
    L("seconds       : %.1f" % dt)
    rows = result.get("nodes") or []
    built = [r for r in rows if r.get("build_status") == "compiled"]
    dropped = [r for r in rows if r.get("build_status") != "compiled"]
    L("nodes linked  : %d / %d" % (len(built), len(rows)))
    L("")
    L("LINKED:")
    for r in built:
        L("   %-24s %-14s id=%s" % (r.get("type_name"),
          r.get("base"), r.get("type_id")))
    if dropped:
        L("")
        L("DROPPED (best-effort):")
        for r in dropped:
            L("   %-24s %s" % (r.get("type_name"),
              (r.get("build_reason") or "")[:100]))
    if result.get("errors"):
        L("")
        L("ERRORS:")
        for e in result["errors"]:
            L("   - %s" % str(e)[:160])

    # companions (Python-side @maya_command companion plugins, if any)
    comps = result.get("companions") or []
    if comps:
        L("")
        L("COMPANIONS: %s" % comps)

    out = {
        "ok": bool(result.get("ok")),
        "bundle_path": result.get("bundle_path"),
        "seconds": dt,
        "n_input": len(paths),
        "n_linked": len(built),
        "linked": [r.get("type_name") for r in built],
        "dropped": [{"type_name": r.get("type_name"),
                     "reason": r.get("build_reason")} for r in dropped],
        "errors": result.get("errors"),
        "companions": comps,
    }
    # The build report is an artifact, not something loaded -- keep it under
    # build/ beside the manifest (top level holds only the bundle + companions).
    build_dir = os.path.join(OUT_DIR, "build")
    os.makedirs(build_dir, exist_ok=True)
    with open(os.path.join(build_dir, "mega_results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    # Sweep a stale top-level copy a pre-reorg run left behind.
    _stale = os.path.join(OUT_DIR, "mega_results.json")
    if os.path.exists(_stale):
        try:
            os.remove(_stale)
        except OSError:
            pass
    L("")
    L("wrote %s" % os.path.join(build_dir, "mega_results.json"))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
