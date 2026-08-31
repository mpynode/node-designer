"""Single-process end-to-end verification of the rebuilt mPyMega bundle.

Proves the "take on drop" fix at RUNTIME (not just build-time):
  1. the mega bundle LOADS and every linked type REGISTERS;
  2. each of the 4 texture nodes renders a NON-FLAT texture in Viewport 2.0 from
     the MEGA bundle (the multi-node VP2-override path, previously unverified);
  3. no regression -- every non-texture linked type still CREATES without crash.

Usage: mayapy mega_verify.py <bundle> <results_json> <out_dir> <asset_png>
Prints MEGA_VERIFY_JSON:{...}; exit 0 iff all gates pass.
"""
import json
import os
import shutil
import sys

BUNDLE = sys.argv[1]
RESULTS = sys.argv[2]
OUT = sys.argv[3]
ASSET = sys.argv[4] if len(sys.argv) > 4 else None
os.makedirs(OUT, exist_ok=True)

TEXTURE_TYPES = {"fileTexture", "scanlineTex", "basicTexture", "gameOfLifeTex"}
# file-fed texture nodes want a fileName; synthetic (gameOfLifeTex) does not.
FILE_FED = {"fileTexture", "scanlineTex", "basicTexture"}

res = {"ok": False, "notes": [], "register": {}, "render": {}, "create": {}}

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as mc


def _stats(path):
    from PIL import Image
    if not path or not os.path.isfile(path):
        return {"exists": False}
    im = Image.open(path).convert("RGB")
    px = list(im.getdata())
    lum = [0.299 * r + 0.587 * g + 0.114 * b for (r, g, b) in px]
    plane = [v for v in lum if v > 0.5]
    pmn, pmx = (min(plane), max(plane)) if plane else (0.0, 0.0)
    return {"plane_min": round(pmn, 2), "plane_max": round(pmx, 2),
            "plane_range": round(pmx - pmn, 2), "nonblack_px": len(plane),
            "textured": (pmx - pmn) > 8.0}


def _render_texture(ntype):
    mc.file(new=True, force=True)
    mc.directionalLight(name="key")
    plane = mc.polyPlane(name="texPlane", w=10, h=10, sx=1, sy=1)[0]
    sh = mc.shadingNode("surfaceShader", asShader=True, name="ss")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name="ssSG")
    mc.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
    tex = mc.createNode(ntype, name="probeTex")
    if ntype in FILE_FED and ASSET and os.path.isfile(ASSET):
        for cand in ("fileName", "fileTextureName"):
            if mc.attributeQuery(cand, node=tex, exists=True):
                mc.setAttr(tex + "." + cand, ASSET, type="string")
                break
    mc.connectAttr(tex + ".outColor", sh + ".outColor", force=True)
    mc.sets(plane, edit=True, forceElement=sg)
    mc.currentTime(5)
    out = {}
    try:
        out["outColor"] = mc.getAttr(tex + ".outColor")
    except Exception as e:
        out["outColor_err"] = str(e)
    mc.setAttr("defaultRenderGlobals.imageFormat", 32)
    r = mc.ogsRender(camera="top", width=256, height=256)
    if isinstance(r, (list, tuple)):
        r = r[0] if r else None
    dst = os.path.join(OUT, ntype + "_vp2.png")
    if r and os.path.isfile(r):
        shutil.copy(r, dst)
    out["stats"] = _stats(dst)
    out["textured"] = bool(out["stats"].get("textured"))
    return out


try:
    linked = [e if isinstance(e, str) else (e.get("type_name") or e.get("name"))
              for e in json.load(open(RESULTS))["linked"]]
    res["linked_count"] = len(linked)

    for p in ("mpynode_api1", "mpynode_api2"):
        try:
            if not mc.pluginInfo(p, q=True, loaded=True):
                mc.loadPlugin(p, quiet=True)
        except Exception as e:
            res["notes"].append("plugin %s: %s" % (p, e))

    from mpynode._base.plugins import load_or_reload_native_plugin
    lr = load_or_reload_native_plugin(BUNDLE)
    res["loaded"] = bool(lr.get("loaded"))
    if not lr.get("loaded"):
        res["load_error"] = lr.get("error")
        raise RuntimeError("bundle did not load")

    known = set(mc.allNodeTypes() or [])
    for t in linked:
        res["register"][t] = (t in known)

    # (2) VP2 render for texture nodes from the MEGA bundle.
    for t in sorted(TEXTURE_TYPES):
        if t not in linked:
            res["render"][t] = {"skipped": "not linked"}
            continue
        try:
            res["render"][t] = _render_texture(t)
        except Exception:
            import traceback
            res["render"][t] = {"error": traceback.format_exc()}

    # (3) Regression: every non-texture linked type still CREATES.
    for t in sorted(set(linked) - TEXTURE_TYPES):
        mc.file(new=True, force=True)
        try:
            n = mc.createNode(t)
            res["create"][t] = bool(n)
        except Exception as e:
            res["create"][t] = "ERR: " + str(e)[:80]

    # ---- gates ----
    reg_ok = all(res["register"].values())
    tex_ok = all(res["render"].get(t, {}).get("textured")
                 for t in TEXTURE_TYPES if t in linked)
    create_ok = all(v is True for v in res["create"].values())
    res["gates"] = {"registered": reg_ok, "textures_render": tex_ok,
                    "no_create_regression": create_ok}
    res["ok"] = bool(res["loaded"] and reg_ok and tex_ok and create_ok)
except Exception:
    import traceback
    res["error"] = traceback.format_exc()
finally:
    print("MEGA_VERIFY_JSON:" + json.dumps(res, default=str))
    try:
        maya.standalone.uninitialize()
    except Exception:
        pass
    sys.exit(0 if res.get("ok") else 1)
