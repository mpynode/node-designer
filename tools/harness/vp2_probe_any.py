"""Generic VP2 texture probe: load a bundle, create its texture node, wire it to
an unlit surfaceShader on a top-framed polyPlane, ogsRender, report whether the
plane shows a NON-FLAT texture (plane_range > 8 luma).

Usage:  mayapy vp2_probe_any.py <bundle> <node_type> <out_dir> [asset_png]
Prints  VP2_ANY_JSON:{...}  ; exit 0 iff textured.
"""
import json
import os
import shutil
import sys

BUNDLE = sys.argv[1]
NODE_TYPE = sys.argv[2]
OUT = sys.argv[3]
ASSET = sys.argv[4] if len(sys.argv) > 4 else None
os.makedirs(OUT, exist_ok=True)
res = {"ok": False, "node_type": NODE_TYPE, "notes": []}

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as mc


def _stats(path):
    from PIL import Image
    if not path or not os.path.isfile(path):
        return {"exists": False}
    im = Image.open(path).convert("RGB")
    px = list(im.getdata())
    lum = [0.299*r + 0.587*g + 0.114*b for (r, g, b) in px]
    plane = [v for v in lum if v > 0.5]
    pmn, pmx = (min(plane), max(plane)) if plane else (0.0, 0.0)
    return {"plane_min": pmn, "plane_max": pmx, "plane_range": pmx - pmn,
            "nonblack_px": len(plane), "textured": (pmx - pmn) > 8.0}


try:
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
    elif NODE_TYPE not in (mc.allNodeTypes() or []):
        res["registered"] = False
    else:
        mc.file(new=True, force=True)
        mc.directionalLight(name="key")
        plane = mc.polyPlane(name="texPlane", w=10, h=10, sx=1, sy=1)[0]
        sh = mc.shadingNode("surfaceShader", asShader=True, name="ss")
        sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name="ssSG")
        mc.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
        tex = mc.createNode(NODE_TYPE, name="probeTex")
        if ASSET and os.path.isfile(ASSET):
            for cand in ("fileName", "fileTextureName"):
                if mc.attributeQuery(cand, node=tex, exists=True):
                    mc.setAttr(tex + "." + cand, ASSET, type="string")
                    res["path_attr"] = cand
                    break
        mc.connectAttr(tex + ".outColor", sh + ".outColor", force=True)
        mc.sets(plane, edit=True, forceElement=sg)
        mc.currentTime(5)
        try:
            res["outColor_sample"] = mc.getAttr(tex + ".outColor")
        except Exception as e:
            res["outColor_err"] = str(e)
        mc.setAttr("defaultRenderGlobals.imageFormat", 32)
        r = mc.ogsRender(camera="top", width=256, height=256)
        if isinstance(r, (list, tuple)):
            r = r[0] if r else None
        dst = os.path.join(OUT, NODE_TYPE + "_vp2.png")
        if r and os.path.isfile(r):
            shutil.copy(r, dst)
        res["stats"] = _stats(dst)
        res["ok"] = bool(res["stats"].get("textured"))
except Exception:
    import traceback
    res["error"] = traceback.format_exc()
finally:
    print("VP2_ANY_JSON:" + json.dumps(res, default=str))
    try:
        maya.standalone.uninitialize()
    except Exception:
        pass
    sys.exit(0 if res.get("ok") else 1)
