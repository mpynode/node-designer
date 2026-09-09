"""Median wall-clock benchmark of a COMPILED node under a fixed scene battery.

This is the missing piece the AI optimizer needs: an objective, repeatable speed
number so a rewritten .cpp can be proven *measurably faster* (not just "looks
faster"). It is deliberately node-agnostic -- it drives a scene expressed as a
flat list of setAttr "ops" (the same shape the parity harnesses use), warms the
DG, then times ``dgdirty(node); dgeval(node.plug)`` a number of times and reports
the MEDIAN (robust to GC / scheduler noise).

Usage (standalone mayapy, plug-ins + scripts on the path):
    mayapy benchmark_node.py <bundle> <node_type> [--out outMesh]
                             [--iters 9] [--warmup 3] [--scene scene.json]
                             [--mode compute|bake] [--bake-source 1024]

``--mode bake`` times an ogsRender of the node on a plane instead of one dgeval.
For a TEXTURE node the compute is a single texel (~0.003 ms, pure noise) while
the VP2 override bakes the whole buffer every frame -- so compute mode makes the
real cost invisible to the optimizer. See ``_bake_pull``.

*** BAKE MODE IS A DIAGNOSTIC, NOT AN OPTIMIZER OBJECTIVE. Measured 2026-08-28,
scanlineTex, 25 iters, spec-seeded so the content-key guard misses every frame:

    --bake-source  256 -> 7.40 ms and 4.51 ms on two identical runs
    --bake-source 1024 -> 10.88 ms and 8.24 ms

1024x1024 is SIXTEEN times the texels of 256x256 and cost 1.5x, while the spread
between two runs of the SAME config was larger than the difference between the
two configs. Timing also moved with --bake-render, which the bake grid does not
depend on. The node is not at fault: outSize tracks the asset exactly
(256/512/1024/2048). VP2 owns when updateShader is called and it is not once per
ogsRender, so the median is mostly renders that skipped the bake -- which no
amount of sampling fixes. Wiring this into optimizer_live._measure would hand the
optimizer a noise generator and it would accept random winners; that is strictly
worse than today's honest "noise-floor-speedup" refusal. Left in, OFF by default,
so the next attempt starts from this measurement instead of repeating it. ***

Baseline vs candidate are always measured with the SAME scene, so even a scene
that only exercises defaults yields a valid *relative* comparison; a
representative scene (built in for metaClay/metaballs, or supplied via --scene)
makes the number meaningful. Prints 'BENCH_JSON:{...}' as the last line.

Scene JSON schema (also the built-in shape):
    {"ops": [ {"plug": "resolution", "value": 16},
              {"plug": "shapeMatrix[0]", "kind": "matrix", "value": [16 floats]},
              {"plug": "halfExtents[0]", "kind": "double3", "value": [x, y, z]} ]}
``kind`` defaults to "scalar" (a bare setAttr); "matrix"/"double3" add the type.
"""
import argparse
import contextlib
import json
import os
import sys
import time

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as mc


# Set by the optimizer agent's generated ``bench.sh``, and by NOTHING else.
#
# Two paths reach this script. The ENGINE spawns it from
# ``optimizer_live._measure``, which already holds the cross-process benchmark
# flock around the whole child -- taking it again HERE would block on our own
# parent until the lock timeout, because an flock belongs to the open file
# description, not the process. The AGENT reaches it through
# ``bash ./bench.sh`` under the CLI, where no ancestor holds anything, and that
# path was measured running four benchmarks at once. So the caller that knows it
# holds nothing is the one that asks for the lock.
_LOCK_CHILD_ENV = "MPYNODE_BENCH_LOCK_CHILD"
_OFF = ("", "0", "off", "false", "no")


def _bench_lock(label):
    """The cross-process benchmark lock, or a no-op context manager.

    A no-op unless ``_LOCK_CHILD_ENV`` is set (so the engine path and every
    standalone/parity invocation are byte-for-byte unchanged and never touch the
    filesystem), and a no-op again if ``mpynode`` is not importable -- this
    script is run directly by ``run_all.py`` and by hand, and an optional lock
    must never be the reason a benchmark cannot run. A lock that IS requested
    and cannot be taken still raises: silently benchmarking unlocked is the
    failure this exists to prevent.
    """
    if (os.environ.get(_LOCK_CHILD_ENV) or "").strip().lower() in _OFF:
        return contextlib.nullcontext()
    try:
        from mpynode.native.ai import optimizer_live
    except Exception:
        return contextlib.nullcontext()
    return optimizer_live.bench_lock(label=label)


def _identity_matrix(tx=0.0, ty=0.0, tz=0.0, sx=1.0, sy=1.0, sz=1.0):
    # row-major 4x4 as Maya's setAttr(...,type="matrix") expects (translate in
    # the last row) -- mirrors metaballs_parity._mat so the scene is comparable.
    return [sx, 0.0, 0.0, 0.0,
            0.0, sy, 0.0, 0.0,
            0.0, 0.0, sz, 0.0,
            tx, ty, tz, 1.0]


def _metaclay_scene(res):
    """A representative metaClay/metaballs workload: cube + smooth sphere -
    cylinder (all three CSG ops), matching the proven csg_all parity scene, at a
    caller-chosen grid resolution so the compute is heavy enough to time."""
    mats = [_identity_matrix(0, 0, 0),
            _identity_matrix(0.6, 0.3, 0),
            _identity_matrix(0, 0, 0)]
    stype = [1, 0, 2]          # box, sphere, cylinder
    add = [1, 1, 0]            # union, union, subtract
    smooth = [0.0, 0.4, 0.0]
    rad = [1.0, 0.7, 0.4]
    hgt = [1.0, 1.0, 2.4]
    ax = [1, 1, 0]
    half = [[0.8, 0.8, 0.8], [0.5, 0.5, 0.5], [0.5, 0.5, 0.5]]
    ops = []
    for i, m in enumerate(mats):
        ops.append({"plug": "shapeMatrix[%d]" % i, "kind": "matrix", "value": m})
    for i in range(len(stype)):
        ops.append({"plug": "shapeType[%d]" % i, "value": stype[i]})
        ops.append({"plug": "additive[%d]" % i, "value": add[i]})
        ops.append({"plug": "smoothing[%d]" % i, "value": smooth[i]})
        ops.append({"plug": "radius[%d]" % i, "value": rad[i]})
        ops.append({"plug": "height[%d]" % i, "value": hgt[i]})
        ops.append({"plug": "axis[%d]" % i, "value": ax[i]})
        ops.append({"plug": "halfExtents[%d]" % i, "kind": "double3",
                    "value": half[i]})
    ops.append({"plug": "resolution", "value": int(res)})
    ops.append({"plug": "isoValue", "value": 0.1})
    return ops


# Built-in scenes so the harness runs out of the box on the driving example.
_BUILTIN = {
    "metaClay": lambda res: _metaclay_scene(res),
    "metaballs": lambda res: _metaclay_scene(res),
}


def _builtin_scene_key(node_type):
    """The ``_BUILTIN`` key for ``node_type``, or None.

    Exact match first, then the LONGEST key the type STARTS WITH. A compiled
    type name is the template's name plus a suffix (``metaballs`` ->
    ``metaballsSw`` / ``metaballsCmp``), and the old exact-only lookup therefore
    dropped the representative scene for every renamed type -- silently. For an
    SDF generator the fallback (generic spec-seeding) yields an EMPTY
    isosurface, so the harness timed a compute that produced nothing and a
    candidate that merely early-outs looked ~95x faster.

    Longest-first so a future ``meta`` / ``metaballs`` pair resolves to the more
    specific key rather than whichever hashed first.
    """
    if node_type in _BUILTIN:
        return node_type
    low = (node_type or "").lower()
    cands = [k for k in _BUILTIN if low.startswith(k.lower())]
    return max(cands, key=len) if cands else None


def _geo_emptiness(plug, om):
    """Is this output plug positively EMPTY geometry?

    ``True`` = it is geometry and it is empty, ``False`` = it holds real
    geometry, ``None`` = not geometry at all (a numeric / array output, which
    must stay unaffected by the emptiness gate).

    An empty geo data object is NOT null: ``MFn*`` may CONSTRUCT on it and then
    raise "Object does not exist" on the first attribute access.

    Dispatch is on the data's ``apiType``, NOT on "did some MFn* constructor
    succeed": an ``MFn*`` will happily construct on NUMERIC data and then fail
    the count access, which made this probe report every kdtree array output as
    empty geometry and refuse a perfectly good benchmark.
    """
    try:
        data = plug.asMObject()
    except Exception:
        return None
    if data.isNull():
        return None
    kinds = {om.MFn.kMeshData: (om.MFnMesh, "numVertices"),
             om.MFn.kNurbsCurveData: (om.MFnNurbsCurve, "numCVs"),
             om.MFn.kNurbsSurfaceData: (om.MFnNurbsSurface, "numCVsInU")}
    try:
        entry = kinds.get(data.apiType())
    except Exception:
        return None
    if entry is None:
        return None                  # not geometry -- leave this node alone
    fn, count = entry
    try:
        return int(getattr(fn(data), count)) == 0
    except Exception:
        return True                  # constructed-but-inaccessible == empty


_FP_CAP = 400000   # floats per plug; 40k verts x 3 is 120k


def _flatten_values(v, out=None, cap=_FP_CAP):
    """Nested tuples/lists of numbers -> one flat float list (bools as 0/1).
    Anything else (a string, None) is skipped; the caller keeps text apart."""
    out = [] if out is None else out
    if isinstance(v, bool):
        out.append(float(v))
    elif isinstance(v, (int, float)):
        out.append(float(v))
    elif isinstance(v, (list, tuple)):
        for x in v:
            if len(out) >= cap:
                break
            _flatten_values(x, out, cap)
    return out


def _typed_data_values(plug, om):
    """``(kind, count, values)`` for a plug holding TYPED data (geometry, a
    numeric array, a matrix, a string) read through the API -- ``getAttr``
    cannot read those -- or ``None`` when the plug holds plain numerics."""
    try:
        data = plug.asMObject()
    except Exception:
        return None
    if data.isNull():
        return None
    t = data.apiType()
    try:
        if t == om.MFn.kMeshData:
            pts = om.MFnMesh(data).getPoints()
            return "mesh", len(pts), _flatten_values([(p.x, p.y, p.z) for p in pts])
        if t == om.MFn.kNurbsCurveData:
            pts = om.MFnNurbsCurve(data).cvPositions()
            return "nurbsCurve", len(pts), _flatten_values([(p.x, p.y, p.z) for p in pts])
        if t == om.MFn.kNurbsSurfaceData:
            pts = om.MFnNurbsSurface(data).cvPositions()
            return "nurbsSurface", len(pts), _flatten_values([(p.x, p.y, p.z) for p in pts])
        if t == om.MFn.kDoubleArrayData:
            a = list(om.MFnDoubleArrayData(data).array())
            return "doubleArray", len(a), _flatten_values(a)
        if t == om.MFn.kIntArrayData:
            a = list(om.MFnIntArrayData(data).array())
            return "intArray", len(a), _flatten_values(a)
        if t in (om.MFn.kVectorArrayData, om.MFn.kPointArrayData):
            fn = (om.MFnVectorArrayData if t == om.MFn.kVectorArrayData
                  else om.MFnPointArrayData)
            a = fn(data).array()
            return "vectorArray", len(a), _flatten_values([(p.x, p.y, p.z) for p in a])
        if t == om.MFn.kMatrixData:
            m = om.MFnMatrixData(data).matrix()
            return "matrix", 1, [m.getElement(i, j) for i in range(4) for j in range(4)]
        if t == om.MFn.kStringData:
            return "string", 1, om.MFnStringData(data).string()
    except Exception:
        return None
    return None


def _fingerprint_outputs(mc, om, node, pulls):
    """``{attr: {"kind", "count", "values" | "text"}}`` for every output the
    benchmark pulls -- geometry through the API, plain numerics through getAttr,
    every element of a multi. Read ONCE after warm-up, outside the timed region.
    A plug that cannot be read is recorded as ``opaque`` rather than skipped, so
    two fingerprints always cover the same plugs."""
    fp = {}
    for attr, is_arr in pulls:
        base = "%s.%s" % (node, attr)
        entry = {"kind": "opaque", "count": 0, "values": []}
        try:
            idx = None
            try:
                idx = mc.getAttr(base, mi=True)
            except Exception:
                idx = None
            names = (["%s[%d]" % (base, int(i)) for i in idx] if idx
                     else [base if not is_arr else base + "[0]"])
            kind, count, values, text = None, 0, [], []
            for name in names:
                typed = None
                try:
                    sel = om.MSelectionList()
                    sel.add(name)
                    typed = _typed_data_values(sel.getPlug(0), om)
                except Exception:
                    typed = None
                if typed is not None:
                    k, n, vals = typed
                    kind = kind or k
                    count += n
                    if k == "string":
                        text.append(vals)
                    else:
                        values.extend(vals[:max(0, _FP_CAP - len(values))])
                    continue
                val = mc.getAttr(name)
                if isinstance(val, str):
                    kind = kind or "string"
                    count += 1
                    text.append(val)
                else:
                    kind = kind or "numeric"
                    count += 1
                    _flatten_values(val, values)
            entry = {"kind": kind or "opaque", "count": count,
                     "values": values[:_FP_CAP]}
            if text:
                entry["text"] = text
            if len(values) > _FP_CAP:
                entry["truncated"] = True
        except Exception:
            pass
        fp[attr] = entry
    return fp


def _apply_ops(node, ops):
    for op in ops:
        plug = "%s.%s" % (node, op["plug"])
        val = op["value"]
        kind = op.get("kind", "scalar")
        if kind == "matrix":
            mc.setAttr(plug, *val, type="matrix")
        elif kind == "double3":
            mc.setAttr(plug, float(val[0]), float(val[1]), float(val[2]),
                       type="double3")
        elif isinstance(val, (list, tuple)):
            mc.setAttr(plug, *val)
        else:
            mc.setAttr(plug, val)


def _bake_asset(path, n):
    """An n x n gradient PNG for the node to read.

    THIS is what sets the bake workload: the VP2 override sizes its grid from the
    SOURCE image (uncapped, deliberately -- a cap would hand VP2 a different-sized
    texture than the interpreted tier uploads). Without a real file the node reads
    nothing, falls back to a synthetic 256x256 grid, and the benchmark measures a
    16x-too-small bake.
    """
    import numpy as np
    import maya.api.OpenMaya as om
    ramp = np.linspace(0, 255, n).astype(np.uint8)
    a = np.empty((n, n, 4), np.uint8)
    a[..., 0] = ramp[None, :]
    a[..., 1] = ramp[:, None]
    a[..., 2] = 128
    a[..., 3] = 255
    img = om.MImage()
    img.create(n, n, 4, om.MImage.kByte)
    img.setPixels(bytes(a.tobytes()), n, n)
    img.writeToFile(path, "png")
    return path


def _bake_pull(node, args, result):
    """Wire the node onto a top-framed plane and return a timed render closure.

    Same plane + unlit-surfaceShader + ogsRender rig the five VP2 harnesses in
    this directory already use (mpyfile_image_parity, vp2_probe, vp2_probe_any,
    vp2_diag, mega_verify). It is copied rather than imported because every one
    of them parses sys.argv at import and so cannot be imported as a library.

    The render is deliberately TINY. Bake cost tracks the SOURCE resolution, not
    the render resolution, so a small frame keeps ogsRender's own draw + PNG
    writeback out of the measurement while the full-size bake still runs. That
    asymmetry is also the non-vacuity test: the timing must scale with
    --bake-source and stay flat against --bake-render.
    """
    asset = os.path.join(os.path.dirname(os.path.abspath(args.bundle)),
                         "_bench_bake_%d.png" % args.bake_source)
    try:
        _bake_asset(asset, args.bake_source)
        result["bake_asset"] = asset
    except Exception as exc:
        result["errors"].append("bake asset: %r" % (exc,))
        asset = None

    # The node must actually READ it, or the grid falls back to 256x256.
    for cand in ("fileName", "fileTextureName"):
        if asset and mc.attributeQuery(cand, node=node, exists=True):
            mc.setAttr("%s.%s" % (node, cand), asset, type="string")
            result["bake_asset_attr"] = cand
            break

    mc.polyPlane(name="benchPlane", w=10, h=10, sx=1, sy=1)
    mc.setAttr("top.orthographicWidth", 10)
    mc.setAttr("topShape.orthographic", 1)
    sh = mc.shadingNode("surfaceShader", asShader=True, name="benchSS")
    sg = mc.sets(renderable=True, noSurfaceShader=True, empty=True,
                 name="benchSG")
    mc.connectAttr(sh + ".outColor", sg + ".surfaceShader", force=True)
    mc.connectAttr(node + ".outColor", sh + ".outColor", force=True)
    mc.sets("benchPlane", edit=True, forceElement=sg)
    mc.setAttr("defaultRenderGlobals.imageFormat", 32)  # PNG

    px = args.bake_render

    def _pull():
        mc.ogsRender(camera="top", width=px, height=px)

    return _pull


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("node_type")
    ap.add_argument("--out", default=None)
    ap.add_argument("--iters", type=int, default=9)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--res", type=int, default=16)
    ap.add_argument("--scene", default=None)
    # The spec drives UNIVERSAL seeding: every supported input plug (single and
    # array) gets a value and every supported output plug gets pulled. Without
    # it a node whose inputs are a mesh + a big array benchmarks an EMPTY
    # compute, and the optimizer can never accept anything.
    ap.add_argument("--spec", default=None)
    ap.add_argument("--bench-array", type=int, default=512)
    ap.add_argument("--bench-geo", type=int, default=40)
    # Every pulled output's values after warm-up, as JSON, so the optimizer can
    # refuse a candidate that computed something ELSE on the same scene.
    ap.add_argument("--fingerprint-out", default=None)
    # A node with nothing to perturb between ticks would be timed on cache hits
    # (rbfWrap: "6103x"); the harness refuses unless told otherwise.
    ap.add_argument("--allow-unperturbed", action="store_true")
    # BAKE mode. `compute` times one dgeval; for a TEXTURE node that is a single
    # texel, which is why every mPyFile template benchmarks at ~0.003 ms and every
    # optimizer round comes back "noise-floor-speedup" -- the objective cannot see
    # the VP2 bake, where a 1024x1024 node actually spends ~10 ms/frame. Bake mode
    # times an ogsRender of the node on a plane instead, i.e. what the viewport
    # does. See --bake-source for why the render is deliberately tiny.
    ap.add_argument("--mode", choices=("compute", "bake"), default="compute")
    ap.add_argument("--bake-render", type=int, default=64)
    ap.add_argument("--bake-source", type=int, default=1024)
    args = ap.parse_args()

    result = {"ok": False, "bundle": args.bundle, "node_type": args.node_type,
              "plug": args.out, "median_ms": None, "iters": args.iters,
              "samples_ms": [], "scene": None, "errors": [],
              "driven": [], "skipped": [], "pulled": []}
    try:
        for p in ("mpynode_api1", "mpynode_api2"):
            if not mc.pluginInfo(p, q=True, loaded=True):
                mc.loadPlugin(p, quiet=True)
        mc.loadPlugin(args.bundle, quiet=True)

        scene_label = None
        if args.scene:
            with open(args.scene) as fh:
                ops = json.load(fh).get("ops", [])
            scene_label = os.path.basename(args.scene)
        else:
            _bkey = _builtin_scene_key(args.node_type)
            if _bkey:
                ops = _BUILTIN[_bkey](args.res)
                scene_label = "builtin:%s@res%d" % (_bkey, args.res)
            else:
                ops = []
        result["scene"] = scene_label or ("defaults (no scene for %s)"
                                          % args.node_type)

        # A deformer must be ATTACHED to geometry or it computes nothing; a
        # compute node just gets created. The spec decides which.
        if args.spec:
            from mpynode.native.toolchain import verify as _verify0
            with open(args.spec) as _fh0:
                _spec0 = json.load(_fh0)
            node = _verify0.bench_make_node(mc, _spec0, args.node_type,
                                            density=args.bench_geo)
        else:
            node = mc.createNode(args.node_type)

        # Universal seeding + pull list, from the spec. The type knowledge is
        # shared with the parity harness (verify.seed_bench_scene) so a plug
        # type can never be driveable there and silently un-driveable here.
        pulls = []
        if args.spec:
            from mpynode.native.toolchain import verify as _verify
            with open(args.spec) as fh:
                spec = json.load(fh)
            rep = _verify.seed_bench_scene(mc, node, spec,
                                           k_array=args.bench_array,
                                           geo_density=args.bench_geo)
            result["driven"] = ["%s:%s(%s)" % r for r in rep["driven"]]
            result["skipped"] = ["%s:%s(%s)" % r for r in rep["skipped"]]
            result["sized_outputs"] = ["%s[%d]->%s" % o
                                       for o in rep.get("outputs", [])]
            result["scene"] = ("spec-seeded: %d driven, %d array, %d output "
                               "multi(s) sized, %d skipped"
                               % (len(rep["driven"]), rep["arrays"],
                                  len(rep.get("outputs", [])),
                                  len(rep["skipped"])))
            pulls = _verify.bench_pull_plugs(spec)

        # The representative scene is applied LAST so it WINS. seed_bench_scene
        # pads every multi out to k_array elements with generic values; applied
        # before it, a builtin scene's shapeType/radius/halfExtents were
        # overwritten and its 3 real shapes were buried under hundreds of junk
        # ones (which is what inflated the metaballs AABB to a 405^3 lattice).
        # Trailing elements the scene does not own are removed for the multis it
        # DOES drive, so the node sees exactly the intended workload.
        if ops:
            if args.spec:
                _owned = {}
                for op in ops:
                    plug = op.get("plug", "")
                    if "[" in plug and plug.endswith("]"):
                        base, _, idx = plug[:-1].partition("[")
                        try:
                            _owned[base] = max(_owned.get(base, -1), int(idx))
                        except ValueError:
                            continue
                for base, last in _owned.items():
                    try:
                        idxs = mc.getAttr("%s.%s" % (node, base),
                                          multiIndices=True) or []
                    except Exception:
                        continue
                    for i in idxs:
                        if int(i) > last:
                            try:
                                mc.removeMultiInstance(
                                    "%s.%s[%d]" % (node, base, int(i)), b=True)
                            except Exception:
                                pass
            _apply_ops(node, ops)
            if scene_label:
                result["scene"] = scene_label

        if args.out:                      # explicit override wins
            pulls = [(args.out, None)]
        if not pulls:
            # No spec and no --out: fall back to the historical default so
            # existing callers keep working.
            pulls = [("outMesh", None)]

        # An ARRAY output must be pulled as `attr[0]`: dgeval on the multi ROOT
        # does not force a recompute in Maya 2026, which silently times a node
        # that never ran. Resolve each plug's real form ONCE, here, and fail
        # loudly if none of them is pullable.
        #
        # Resolve and pull through MPlug.asMDataHandle, NOT getAttr: getAttr
        # cannot read typed data ("The data is not a numeric or string value")
        # so a getAttr-gated resolve silently drops exactly the geometry outputs
        # -- outMesh, outputGeometry -- that carry the work. asMDataHandle reads
        # every type, is silent, and forces evaluation just the same (verified:
        # metaballs 1682 ms @ res 6 -> 7422 ms @ res 10, matching res^3).
        import maya.api.OpenMaya as om

        def _resolve(plug_name):
            sel = om.MSelectionList()
            sel.add(plug_name)
            return sel.getPlug(0)

        resolved, plugs = [], []
        for attr, is_arr in pulls:
            for cand in (["%s.%s[0]" % (node, attr)] if is_arr else
                         ["%s.%s" % (node, attr),
                          "%s.%s[0]" % (node, attr)]):
                try:
                    plugs.append(_resolve(cand))
                    resolved.append(cand)
                    break
                except Exception:
                    continue

        # IK solvers have no output plug at all -- doSolve() runs when an
        # ikHandle evaluates -- so rig a chain and pull its tip instead.
        ik_pull = None
        if not resolved and args.spec:
            ik_pull, _handle = _verify.bench_ik_rig(mc, node)
            if ik_pull is not None:
                resolved = ["<ikHandle rig: tip worldMatrix>"]

        result["pulled"] = resolved
        if not resolved:
            raise RuntimeError(
                "no pullable output plug on %s (tried %s) -- the benchmark "
                "cannot measure this node" % (args.node_type,
                                              [p[0] for p in pulls]))
        result["plug"] = ", ".join(resolved)

        if ik_pull is not None:
            _pull = ik_pull
        else:
            def _pull():
                for p in plugs:
                    h = p.asMDataHandle()
                    try:
                        p.destructHandle(h)
                    except Exception:
                        pass

        # BAKE mode replaces ONLY the timed action. Everything above -- spec
        # seeding, the representative scene, the output-plug resolve -- still
        # runs, so the node is set up identically and a bake number is directly
        # comparable to the compute number taken on the same scene.
        result["mode"] = args.mode
        if args.mode == "bake":
            _pull = _bake_pull(node, args, result)
            result["plug"] = ("ogsRender %dpx, bake source %dpx"
                              % (args.bake_render, args.bake_source))

        # dgdirty re-marks the plugs but leaves their VALUES identical, so a
        # compute that memoizes on input content answers every tick from cache
        # and the benchmark times a cache hit. Move one scalar between ticks --
        # OUTSIDE the timed region, so only the compute is measured.
        _perturb = None
        if args.spec:
            try:
                _perturb = _verify.bench_perturb_fn(mc, node, spec)
            except Exception:
                _perturb = None
        result["perturbed"] = _perturb is not None
        result["moved"] = list(getattr(_perturb, "moved", None) or [])
        if args.spec and _perturb is None and not args.allow_unperturbed:
            result["unperturbed"] = True
            raise RuntimeError(
                "nothing to perturb on %s between ticks -- every timed tick "
                "would re-read identical inputs, so a candidate that caches its "
                "last answer measures as a cache hit (rbfWrap: 2103 ms -> 0.34 "
                "ms, '6103x'). Refusing to report a timing; pass "
                "--allow-unperturbed to override." % args.node_type)

        # Everything from here to the last sample is full-rate compute, so it is
        # ONE lock window: warmup left outside it would run during another
        # process's timed region, which corrupts that measurement just as badly
        # as an overlapping sample loop does.
        samples = []
        with _bench_lock(args.node_type):
            # Warm up: force the compute so codegen/first-touch costs don't
            # pollute the timed samples.
            for _ in range(max(0, args.warmup)):
                if _perturb:
                    _perturb()
                mc.dgdirty(node)
                _pull()

            # An EMPTY output means this is timing a compute that produces
            # nothing. The number is meaningless AND the parity gate that would
            # catch a wrong candidate skips for the same reason -- which is
            # exactly how a metaballs candidate with an inverted shape dispatch
            # was accepted at "95x". Refuse to report a timing instead. Flagged
            # separately from a crash so the optimizer's ladder can GROW the
            # scene rather than give up.
            _empt = [_geo_emptiness(p, om) for p in plugs]
            _known = [e for e in _empt if e is not None]
            if _known and all(_known):
                result["empty_output"] = True
                raise RuntimeError(
                    "every geometry output of %s is EMPTY under this scene "
                    "(%s) -- refusing to report a timing for a compute that "
                    "produces nothing. Supply a representative --scene, or "
                    "grow --bench-geo / --res until the output is non-empty."
                    % (args.node_type, result["scene"]))

            # What the node COMPUTED on this scene, after warm-up: the
            # optimizer holds every candidate to the baseline's values.
            if args.fingerprint_out and ik_pull is None:
                fp = _fingerprint_outputs(mc, om, node, pulls)
                with open(args.fingerprint_out, "w") as fh:
                    json.dump(fp, fh)
                result["fingerprint"] = {"path": args.fingerprint_out,
                                         "plugs": sorted(fp)}

            for _ in range(max(1, args.iters)):
                if _perturb:
                    _perturb()
                mc.dgdirty(node)
                t0 = time.perf_counter()
                _pull()
                t1 = time.perf_counter()
                samples.append((t1 - t0) * 1000.0)

        result["samples_ms"] = [round(x, 4) for x in samples]
        result["median_ms"] = round(_median(samples), 4)
        result["ok"] = result["median_ms"] is not None
    except Exception:
        import traceback
        result["errors"].append(traceback.format_exc())
    finally:
        print("BENCH_JSON:" + json.dumps(result))
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
