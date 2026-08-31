"""VP2 texture-display probe (baseline + fix gate).

ogsRender is confirmed working headlessly, but only for channels that are
visible WITHOUT scene lighting. We therefore drive an unlit ``surfaceShader``
(pure emissive: outColor = input) so a texture shows regardless of lights,
and any "flatness" is purely a VP2 texture-display property -- exactly the
thing under test.

  (A) CONTROL -- stock ``ramp`` -> surfaceShader.  ramp HAS a built-in VP2
      shading-node override, so VP2 must show a gradient (high variance).
      This proves the harness can distinguish textured vs flat in VP2.
  (B) SUBJECT -- compiled ``scanlineTex`` -> surfaceShader.  Without an
      emitted MPxShadingNodeOverride, VP2 shows a single flat colour (low
      variance) = the P0 bug.  After the codegen fix, VP2 must show the
      scanline pattern (high variance), matching the compute path.

Also samples ``scanlineTex.outColor`` to confirm the compute path is alive
(that path already renders correctly in software/Arnold).

Usage:  mayapy vp2_probe.py <scanline_bundle> <out_dir>
Prints  VP2_PROBE_JSON:{...}
exit 0 iff CONTROL is textured AND (subject textured  OR  --baseline given).
"""
import json
import os
import shutil
import sys

BUNDLE = sys.argv[1]
OUT = sys.argv[2]
BASELINE = "--baseline" in sys.argv  # expect the bug (subject flat) -> still ok
os.makedirs(OUT, exist_ok=True)

# A plane of side 10 in a 30-unit ortho 'top' frame fills ~11% of pixels; a
# textured fill of that area produces range/variance far above these floors,
# while a flat fill sits at ~0 range within the plane.
RANGE_TEXTURED = 8.0   # 0-255 luma range across the whole frame

res = {"ok": False, "control": {}, "subject": {}, "errors": [], "notes": [],
       "baseline_mode": BASELINE}

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
    px = list(im.getdata())
    lum = [0.299 * r + 0.587 * g + 0.114 * b for (r, g, b) in px]
    # Restrict the "textured?" judgement to NON-BLACK pixels (the plane), so a
    # flat-but-coloured plane on a black frame reads as flat, not textured.
    plane_lum = [v for v in lum if v > 0.5]
    n = len(lum)
    m = sum(lum) / n
    if plane_lum:
        pmn, pmx = min(plane_lum), max(plane_lum)
    else:
        pmn = pmx = 0.0
    return {"w": w, "h": h, "frame_range": max(lum) - min(lum),
            "plane_min": pmn, "plane_max": pmx,
            "plane_range": pmx - pmn, "nonblack_px": len(plane_lum),
            "textured": (pmx - pmn) > RANGE_TEXTURED}


def _plane_scene():
    mc.file(new=True, force=True)
    mc.directionalLight(name="key")
    # Default polyPlane lies in XZ (normal +Y) -> flat-on to ortho 'top' cam.
    return mc.polyPlane(name="texPlane", w=10, h=10, sx=1, sy=1)[0]


def _surface_shader(tag):
    sh = mc.shadingNode("surfaceShader", asShader=True, name=tag + "SS")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True,
                 name=tag + "SG")
    mc.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
    return sh, sg


def _ogs(out_base, w=256, h=256):
    mc.setAttr("defaultRenderGlobals.imageFormat", 32)  # PNG
    r = mc.ogsRender(camera="top", width=w, height=h)
    if isinstance(r, (list, tuple)):
        r = r[0] if r else None
    if r and os.path.isfile(r):
        dst = out_base + ".png"
        shutil.copy(r, dst)
        return dst
    return r


try:
    for p in ("mpynode_api1", "mpynode_api2"):
        try:
            if not mc.pluginInfo(p, q=True, loaded=True):
                mc.loadPlugin(p, quiet=True)
        except Exception as e:
            res["notes"].append("plugin %s: %s" % (p, e))

    # -------- (A) CONTROL: stock ramp via surfaceShader ----------------------
    try:
        plane = _plane_scene()
        sh, sg = _surface_shader("ctrl")
        ramp = mc.shadingNode("ramp", asTexture=True, name="ctrlRamp")
        mc.setAttr(ramp + ".type", 1)  # U ramp -> horizontal gradient
        mc.connectAttr(ramp + ".outColor", sh + ".outColor", force=True)
        mc.sets(plane, edit=True, forceElement=sg)
        mc.currentTime(1)
        p = _ogs(os.path.join(OUT, "control_vp2"))
        res["control"] = {"produced": p, "stats": _stats(p)}
    except Exception:
        import traceback
        res["control"]["error"] = traceback.format_exc()

    # -------- (B) SUBJECT: compiled scanlineTex via surfaceShader ------------
    try:
        from mpynode._base.plugins import load_or_reload_native_plugin
        lr = load_or_reload_native_plugin(BUNDLE)
        res["subject"]["loaded"] = bool(lr.get("loaded"))
        if not lr.get("loaded"):
            res["subject"]["load_error"] = lr.get("error")
        elif "scanlineTex" in (mc.allNodeTypes() or []):
            plane = _plane_scene()
            sh, sg = _surface_shader("sl")
            tex = mc.createNode("scanlineTex", name="sl")
            asset = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "..", "..", "scripts", "mpynode", "_demos", "data",
                "test_grid.png"))
            res["subject"]["asset_exists"] = os.path.isfile(asset)
            for cand in ("fileName", "fileTextureName"):
                if mc.attributeQuery(cand, node=tex, exists=True):
                    mc.setAttr(tex + "." + cand, asset, type="string")
                    res["subject"]["path_attr"] = cand
                    break
            mc.connectAttr(tex + ".outColor", sh + ".outColor", force=True)
            mc.sets(plane, edit=True, forceElement=sg)
            mc.currentTime(1)
            try:
                res["subject"]["outColor_sample"] = mc.getAttr(tex + ".outColor")
            except Exception as e:
                res["subject"]["outColor_err"] = str(e)
            p = _ogs(os.path.join(OUT, "subject_vp2"))
            res["subject"]["produced"] = p
            res["subject"]["stats"] = _stats(p)
        else:
            res["subject"]["registered"] = False
    except Exception:
        import traceback
        res["subject"]["error"] = traceback.format_exc()

    ctrl_ok = bool(res.get("control", {}).get("stats", {}).get("textured"))
    subj_tex = bool(res.get("subject", {}).get("stats", {}).get("textured"))
    res["control_textured"] = ctrl_ok
    res["subject_textured"] = subj_tex
    res["ok"] = ctrl_ok and (subj_tex or BASELINE)
except Exception:
    import traceback
    res["errors"].append(traceback.format_exc())
finally:
    print("VP2_PROBE_JSON:" + json.dumps(res, default=str))
    try:
        maya.standalone.uninitialize()
    except Exception:
        pass
    sys.exit(0 if res.get("ok") else 1)
