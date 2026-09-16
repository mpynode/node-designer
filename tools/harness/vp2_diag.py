"""Isolate: can this headless mayapy render a NON-black VP2 image at all?

Solid-red lambert on a polyPlane. Try ogsRender(top), ogsRender(persp),
and playblast(persp). Report per-method variance/range so we can see which
capture path (if any) produces a non-black frame.
"""
import json
import os
import shutil
import sys

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
res = {"methods": {}, "notes": []}

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as mc


def _stats(path):
    try:
        from PIL import Image
    except Exception as e:
        return {"err": "PIL %s" % e}
    if not path or not os.path.isfile(path):
        return {"file": path, "exists": False}
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px  = list(im.getdata())
    lum = [0.299 * r + 0.587 * g + 0.114 * b for (r, g, b) in px]
    n   = len(lum)
    m   = sum(lum) / n if n else 0
    var = sum((v - m) ** 2 for v in lum) / n if n else 0
    # also count non-black pixels
    nonblack = sum(1 for (r, g, b) in px if (r + g + b) > 0)
    return {"w": w, "h": h, "min": min(lum), "max": max(lum), "var": var,
            "mean": m, "nonblack_px": nonblack, "total_px": n}


mc.file(new=True, force=True)
mc.directionalLight(name="key")
plane = mc.polyPlane(name="p", w=10, h=10, sx=1, sy=1)[0]
sh    = mc.shadingNode("lambert", asShader=True, name="redL")
mc.setAttr(sh + ".color", 1, 0, 0, type="double3")
mc.setAttr(sh + ".incandescence", 1, 0, 0, type="double3")  # unlit-visible
sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True, name="redSG")
mc.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
mc.sets(plane, edit=True, forceElement=sg)
mc.currentTime(1)

# Camera introspection
for cam in ("top", "persp"):
    try:
        shape = mc.listRelatives(cam, shapes=True)[0]
        info  = {"t": mc.getAttr(cam + ".translate")[0]}
        if mc.attributeQuery("orthographicWidth", node=shape, exists=True):
            info["orthoWidth"] = mc.getAttr(shape + ".orthographicWidth")
            info["ortho"]      = mc.getAttr(shape + ".orthographic")
        res.setdefault("cameras", {})[cam] = info
    except Exception as e:
        res["notes"].append("cam %s: %s" % (cam, e))


def _ogs(cam, tag):
    try:
        mc.setAttr("defaultRenderGlobals.imageFormat", 32)
        r = mc.ogsRender(camera=cam, width=128, height=128)
        if isinstance(r, (list, tuple)):
            r = r[0] if r else None
        if r and os.path.isfile(r):
            dst = os.path.join(OUT, tag + ".png")
            shutil.copy(r, dst)
            return _stats(dst)
        return {"produced": r, "exists": bool(r and os.path.isfile(r))}
    except Exception:
        import traceback
        return {"error": traceback.format_exc()}


res["methods"]["ogs_top"]   = _ogs("top", "ogs_top")
res["methods"]["ogs_persp"] = _ogs("persp", "ogs_persp")

try:
    dst = os.path.join(OUT, "pb_persp")
    out = mc.playblast(camera="persp", format="image", compression="png",
                       frame=[1], widthHeight=[128, 128], viewer=False,
                       percent=100, filename=dst, forceOverwrite=True)
    cand = out if out and os.path.isfile(out) else dst + ".0001.png"
    res["methods"]["pb_persp"] = _stats(cand) if os.path.isfile(cand) else \
        {"produced": out, "exists": False}
except Exception:
    import traceback
    res["methods"]["pb_persp"] = {"error": traceback.format_exc()}

print("VP2_DIAG_JSON:" + json.dumps(res, default=str))
try:
    maya.standalone.uninitialize()
except Exception:
    pass
