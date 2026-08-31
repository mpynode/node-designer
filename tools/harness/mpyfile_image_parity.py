"""mPyFile parity by IMAGE: bake every channel, render a 1:1 plane, diff.

The compute-parity gate samples ``outColor`` at a handful of uv points. That is
too coarse for a texture -- and it never touches the VP2 shading override at all,
so a compiled mPyFile could ship shading flat (or, once the optimizer is allowed
to rewrite these nodes, shading WRONG) and still pass.

This harness renders the node instead. For one template it produces four images
of the SAME node in the SAME scene with the SAME inputs -- interpreted, then
swapped to compiled -- and diffs them:

  dg_interp    outColor/outAlpha baked over an NxN uv grid, interpreted
  dg_compiled  the same grid, compiled
  vp2_interp   ogsRender of a 1:1 unit plane, interpreted
  vp2_compiled the same render, compiled

Two of the three comparisons are GATES:

  dg_interp    vs dg_compiled   COMPUTE parity. Exact -- same float math both
                                sides, so this is gated on MAX.
  vp2_compiled vs dg_compiled   the compiled override displays what the compiled
                                compute computes. This is the claim ``nd_texel``
                                exists to make true by construction (one
                                function, called by compute() AND the bake), and
                                it is the only check that catches an optimizer
                                round that kept every structural anchor but
                                changed the bake.

The third is REPORTED, NOT GATED, and the reason is worth stating: the two
overrides do not use the same strategy. The interpreted one uploads the raw
linearized image and lets the GPU sample it, so the compute's own modulation
(File Simple's brightness/contrast) never reaches its viewport. The compiled one
bakes the real compute per texel. They are therefore EXPECTED to differ wherever
the compute is not the identity -- the compiled viewport is the more faithful of
the two, so demanding equality here would gate on reproducing a known gap.

Same image = parity verified.

Usage:
  mayapy mpyfile_image_parity.py <bundle> <template.mpn> <type> <out_dir> [grid]
                                 [--asset PATH]
Prints IMG_PARITY_JSON:{...}; exit 0 iff every enabled comparison passes.
"""
import json
import os
import shutil
import sys

BUNDLE = sys.argv[1]
MPN = sys.argv[2]
CTYPE = sys.argv[3]
OUT = sys.argv[4]
_pos = [a for a in sys.argv[5:] if not a.startswith("--")]
GRID = int(_pos[0]) if _pos else 64

# A template.mpn carries no fileName (the artist picks one), so a deserialized
# node reads no image and every channel comes back as the magenta
# missing-texture sentinel -- which is UNIFORM, so every diff would pass while
# proving nothing. Drive a known asset instead.
#
# And it must be BAND-LIMITED. The obvious choice, _demos/data/test_grid.png, is
# a hard-edged grid at 1024x1024: point-sampling that on a 64x64 uv grid aliases
# so hard that the DG bake and a GPU render of the same texture disagree at
# mean 0.07 no matter how correct BOTH are. Measured on the smooth gradient the
# same pair agrees to 1/255. The asset is generated, not committed, so the gate
# has no binary fixture to drift.
_HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = ""
if "--asset" in sys.argv:
    ASSET = os.path.abspath(sys.argv[sys.argv.index("--asset") + 1])


def _binary_has_override(bundle):
    """Does the COMPILED plug-in actually carry a VP2 override?

    Read off the binary, not the .cpp: the two can disagree. The per-template
    ``build/<type>/<type>.bundle`` is the pre-injection STAGE artifact and has no
    override even though the .cpp beside it does -- checking the source would
    have called that node covered.
    """
    import subprocess
    try:
        out = subprocess.run(["nm", "-C", bundle], stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=60).stdout
        return b"Override" in out and b"MPxShadingNodeOverride" in out
    except Exception:
        try:
            with open(bundle, "rb") as fh:
                return b"MPxShadingNodeOverride" in fh.read()
        except Exception:
            return False


def _make_gradient(path, n=512):
    """A smooth sin gradient -- no frequency the uv grid cannot resolve."""
    import math
    from PIL import Image
    im = Image.new("RGB", (n, n))
    px = []
    for y in range(n):
        for x in range(n):
            u, v = x / (n - 1.0), 1.0 - y / (n - 1.0)
            px.append((
                int(round(255 * (0.5 + 0.5 * math.sin(2.0 * math.pi * u)))),
                int(round(255 * (0.5 + 0.5 * math.sin(2.0 * math.pi * v)))),
                int(round(255 * (0.5 + 0.5 * math.sin(math.pi * (u + v)))))))
    im.putdata(px)
    im.save(path)
    return path

os.makedirs(OUT, exist_ok=True)

# PIL/numpy may ship outside Maya; point MPYNODE_EXTRA_PYTHONPATH at that
# site-packages dir. APPEND -- prepending shadows Maya's own numpy.
for _sp in os.environ.get("MPYNODE_EXTRA_PYTHONPATH", "").split(os.pathsep):
    if _sp and os.path.isdir(_sp) and _sp not in sys.path:
        sys.path.append(_sp)

# Tolerances, and WHICH statistic each is gated on.
#
# Gating a resampled image comparison on MAX is wrong, and measurably so: the
# test asset is a high-frequency grid, so a point-sampled DG texel either lands
# on a black line or misses it while the box-averaged render pixel returns grey.
# That produces a near-1.0 max on a pair that is structurally identical. Mean and
# p99 are what actually distinguish "same look" from "wrong look".
#
#   compute parity   DG vs DG -- same float math both sides, so MAX, and tight.
#   viewport parity  render vs render -- same resolution, same GPU path.
#   vp2 vs compute   render vs DG -- inherently phase-shifted, so both sides are
#                    box-downsampled to kill sampling phase before comparing.
TOL_DG_MAX = 1.5 / 255.0
TOL_CROSS_MEAN, TOL_CROSS_P99 = 10.0 / 255.0, 32.0 / 255.0

res = {"ok": False, "type": CTYPE, "grid": GRID, "images": {}, "compare": {},
       "errors": [], "notes": []}

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as mc


def _png(path, rows, w, h):
    """Write an RGBA float grid (row-major, top row = v=1) as a 16-bit PNG."""
    from PIL import Image
    im = Image.new("RGBA", (w, h))
    px = []
    for row in rows:
        for (r, g, b, a) in row:
            px.append(tuple(
                max(0, min(255, int(round(c * 255.0)))) for c in (r, g, b, a)))
    im.putdata(px)
    im.save(path)
    return path


def _load_rgb(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    return im.size, list(im.getdata())


def _diff(a_path, b_path, *, max_tol=None, mean_tol=None, p99_tol=None,
          downsample=0):
    """Per-channel max / mean / p99 absolute difference, 0-1.

    ``downsample`` box-averages BOTH images to NxN first, which removes
    sampling-phase differences between a point-sampled DG bake and a GPU render
    while still catching a genuinely wrong look. Every supplied tolerance must
    hold; the statistics not gated on are still reported.
    """
    from PIL import Image
    if not (a_path and b_path and os.path.isfile(a_path)
            and os.path.isfile(b_path)):
        return {"ok": False, "reason": "missing image"}
    ia = Image.open(a_path).convert("RGB")
    ib = Image.open(b_path).convert("RGB")
    if downsample:
        ia = ia.resize((downsample, downsample), Image.BOX)
        ib = ib.resize((downsample, downsample), Image.BOX)
    elif ia.size != ib.size:
        return {"ok": False, "reason": "size %s vs %s" % (ia.size, ib.size)}
    pa, pb = list(ia.getdata()), list(ib.getdata())
    ds = []
    for x, y in zip(pa, pb):
        ds.extend(abs(c - d) for c, d in zip(x, y))
    ds.sort()
    n = len(ds)
    mx = ds[-1] / 255.0
    mean = (sum(ds) / 255.0) / max(1, n)
    p99 = ds[min(n - 1, int(0.99 * n))] / 255.0
    out = {"max": round(mx, 5), "mean": round(mean, 6), "p99": round(p99, 5),
           "px": ia.size[0] * ia.size[1],
           "gated_on": [k for k, v in (("max", max_tol), ("mean", mean_tol),
                                       ("p99", p99_tol)) if v is not None]}
    ok = True
    for stat, val, tol in (("max", mx, max_tol), ("mean", mean, mean_tol),
                           ("p99", p99, p99_tol)):
        if tol is None:
            continue
        out["tol_" + stat] = round(tol, 5)
        if val > tol:
            ok = False
            out.setdefault("failed", []).append(stat)
    out["ok"] = ok
    return out


def _bake_dg(node, path):
    """Sample outColor/outAlpha over a GRIDxGRID uv grid straight off the DG."""
    rows = []
    for j in range(GRID):
        # Row 0 is v=1 so the baked image is oriented like the rendered plane.
        v = 1.0 - (j + 0.5) / GRID
        row = []
        for i in range(GRID):
            u = (i + 0.5) / GRID
            mc.setAttr(node + ".uvCoord", u, v, type="double2")
            c = mc.getAttr(node + ".outColor")[0]
            try:
                a = mc.getAttr(node + ".outAlpha")
            except Exception:
                a = 1.0
            row.append((c[0], c[1], c[2], a))
        rows.append(row)
    return _png(path, rows, GRID, GRID)


def _plane_scene():
    """A 1:1 unit plane filling an orthographic frame exactly.

    orthographicWidth == the plane's width, so one rendered pixel maps to one
    fixed fraction of uv -- the render and the DG bake address the same space.
    """
    mc.polyPlane(name="texPlane", w=10, h=10, sx=1, sy=1)
    mc.setAttr("top.orthographicWidth", 10)
    mc.setAttr("topShape.orthographic", 1)
    return "texPlane"


def _surface_shader(tag):
    """Unlit emissive: outColor passes through, so the image IS the texture and
    no light rig can perturb the comparison."""
    sh = mc.shadingNode("surfaceShader", asShader=True, name=tag + "SS")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True,
                 name=tag + "SG")
    mc.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
    return sh, sg


def _ogs(out_base, w, h):
    mc.setAttr("defaultRenderGlobals.imageFormat", 32)  # PNG
    r = mc.ogsRender(camera="top", width=w, height=h)
    if isinstance(r, (list, tuple)):
        r = r[0] if r else None
    if r and os.path.isfile(r):
        dst = out_base + ".png"
        shutil.copy(r, dst)
        return dst
    return None


try:
    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p, quiet=True)
    from mpynode._base.plugins import load_or_reload_native_plugin
    from mpynode._base import node_swap
    lr = load_or_reload_native_plugin(BUNDLE)
    res["bundle_loaded"] = bool(lr.get("loaded"))
    if not lr.get("loaded"):
        raise RuntimeError("bundle load failed: %s" % lr.get("error"))

    mc.file(new=True, force=True)
    # A view transform would be applied to the RENDER but not to the DG values,
    # so the two would never line up. Off makes them the same space.
    try:
        mc.colorManagementPrefs(e=True, cmEnabled=False)
    except Exception as exc:
        res["notes"].append("colorManagementPrefs: %s" % exc)

    from mpynode._common.io import mpn_io
    from mpynode._common.io.mpn_io import deserialize_node
    tnode = deserialize_node(mpn_io.load_mpn(MPN, trusted=True),
                             restore_persistent=False)
    name = tnode.get_name()
    res["interpreted_node"] = name
    res["interpreted_type"] = mc.nodeType(name)

    if not ASSET:
        ASSET = _make_gradient(os.path.join(OUT, "_parity_gradient.png"))
    res["asset"] = ASSET
    res["asset_exists"] = os.path.isfile(ASSET)
    for cand in ("fileName", "fileTextureName"):
        if mc.attributeQuery(cand, node=name, exists=True):
            mc.setAttr(name + "." + cand, ASSET, type="string")
            res["asset_attr"] = cand
            break
    else:
        res["notes"].append("no fileName-ish plug -- node drives itself")

    # A multi-file node (File Composite) reads its paths from a string ARRAY,
    # not fileName -- leave it empty and the node outputs one uniform colour,
    # which passes every diff while proving nothing. Drive it too.
    for a in (mc.listAttr(name, multi=False) or []):
        if a.startswith("_") or "." in a:
            continue
        try:
            if not mc.attributeQuery(a, node=name, multi=True):
                continue
            # Neither getAttr(type=True) nor attributeQuery(dataType=True) works
            # here -- the first throws on an array parent with no elements (the
            # state a freshly deserialized composite is in) and the second throws
            # outright on these plugs. `typed` is as far as introspection gets;
            # the setAttr below is the real test.
            if mc.attributeQuery(a, node=name, attributeType=True) != "typed":
                continue
        except Exception:
            continue
        paths = [ASSET] + [_make_gradient(
            os.path.join(OUT, "_parity_layer%d.png" % k), 256 + 64 * k)
            for k in range(1, 3)]
        ok_n = 0
        for k, pth in enumerate(paths):
            try:
                mc.setAttr("%s.%s[%d]" % (name, a, k), pth, type="string")
                ok_n += 1
            except Exception as exc:
                res["notes"].append("layer set %s[%d]: %s" % (a, k, exc))
        if not ok_n:
            continue  # a typed multi that is not a string array
        res["array_asset_attr"] = a
        res["array_asset_count"] = ok_n
        break

    plane = _plane_scene()
    sh, sg = _surface_shader("par")
    mc.connectAttr(name + ".outColor", sh + ".outColor", force=True)
    mc.sets(plane, edit=True, forceElement=sg)
    mc.currentTime(1)

    res["images"]["vp2_interp"] = _ogs(os.path.join(OUT, "vp2_interp"),
                                       GRID * 2, GRID * 2)
    res["images"]["dg_interp"] = _bake_dg(name, os.path.join(OUT, "dg_interp.png"))

    comp, dropped = node_swap.swap_node(name, CTYPE)
    res["compiled_node"] = comp
    res["dropped_connections"] = dropped
    mc.currentTime(1)
    mc.dgdirty(comp)

    res["images"]["vp2_compiled"] = _ogs(os.path.join(OUT, "vp2_compiled"),
                                         GRID * 2, GRID * 2)
    res["images"]["dg_compiled"] = _bake_dg(comp,
                                            os.path.join(OUT, "dg_compiled.png"))

    im = res["images"]
    half = max(8, GRID // 2)
    res["compare"]["compute_parity"] = _diff(
        im["dg_interp"], im["dg_compiled"], max_tol=TOL_DG_MAX)
    # The construction claim: the override bakes through the same nd_texel the
    # compute calls, so the rendered plane must match the DG bake. Only when the
    # binary HAS an override -- a stateful compute (Game Of Life) is refused one
    # by design, and gating a node that legitimately shades flat would be a
    # guaranteed red. Recorded either way; never silently dropped.
    res["has_vp2_override"] = _binary_has_override(BUNDLE)
    if res["has_vp2_override"]:
        res["compare"]["vp2_matches_compute"] = _diff(
            im["dg_compiled"], im["vp2_compiled"],
            mean_tol=TOL_CROSS_MEAN, p99_tol=TOL_CROSS_P99, downsample=half)
    else:
        res["notes"].append("binary carries NO MPxShadingNodeOverride -- "
                            "viewport comparison skipped (expected for a "
                            "stateful compute); compute parity still gated")
    # Reported only -- see the module docstring for why this is not a gate.
    res["compare_info"] = {"vp2_interp_vs_vp2_compiled": _diff(
        im["vp2_interp"], im["vp2_compiled"], downsample=half)}

    # A UNIFORM pair passes every diff above while proving nothing -- and that is
    # not hypothetical: with no fileName the node returns the magenta
    # missing-texture sentinel for every texel. The signal test must therefore be
    # SPATIAL (does the image vary across pixels?), never per-channel: magenta is
    # (255, 0, 255), so a channel-range test scores it a perfect 255.
    _sz, _px = _load_rgb(im["dg_compiled"])
    _lum = [0.299 * r + 0.587 * g + 0.114 * b for (r, g, b) in _px]
    _rng = max(_lum) - min(_lum)
    res["compiled_dg_spatial_range"] = round(_rng, 2)
    res["compiled_dg_unique_colors"] = len(set(_px))
    res["is_magenta_sentinel"] = all(p == (255, 0, 255) for p in _px)
    # >= 2 colours, not > 4: Game Of Life is a black/white automaton, so two
    # colours over a real spatial pattern is genuine signal, not a flat frame.
    res["has_signal"] = _rng > 8.0 and len(set(_px)) >= 2
    if res["is_magenta_sentinel"]:
        res["notes"].append("compiled DG bake is the MAGENTA missing-texture "
                            "sentinel -- the node read no image at all")
    elif not res["has_signal"]:
        res["notes"].append("compiled DG bake is nearly uniform (spatial range "
                            "%.1f/255, %d colours) -- a passing diff proves "
                            "nothing" % (_rng, len(set(_px))))

    res["ok"] = (bool(res["has_signal"]) and not dropped
                 and all(c.get("ok") for c in res["compare"].values()))
except Exception:
    import traceback
    res["errors"].append(traceback.format_exc())
finally:
    print("IMG_PARITY_JSON:" + json.dumps(res, default=str))
    try:
        maya.standalone.uninitialize()
    except Exception:
        pass
    sys.exit(0 if res.get("ok") else 1)
