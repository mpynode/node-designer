"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run in Maya. Builds two identical spheres, applies the original mPy
deformer (expression copied from the source) to one and the compiled
deformer to the other, then compares object-space points over random
envelope/input samples.
"""
import os, math, random
import maya.cmds as cmds

BUNDLE      = os.path.join(os.path.dirname(__file__), 'patchRelax.mll')
NODE_TYPE   = 'patchRelax'
SRC_TYPE    = 'mPyDeformer'
COMPUTE     = '# Patch-based surface relaxation (de Goes et al., Pixar, SIGGRAPH \'18 Talks).\n# Every vertex flattens its 1-ring into a 2D "decal map", derives span-aware edge\n# weights from it, fits the rest->posed rotation of that patch by SVD, and steps\n# toward the rotated REST edge layout. Because the target carries the patch\'s own\n# rotation, the silhouette survives -- unlike a Laplacian smooth, which shrinks.\n#\n# `ringNbrs` (flat row-major CCW 1-ring vertex ids, -1 padded) and `ringWidth`\n# (the padded width) are DECLARED INPUTS that **Rebuild Rings** seeds. They are\n# inputs rather than something the compute derives because (a) they depend only\n# on TOPOLOGY, so rebuilding them per frame is pure waste, and (b) building them\n# needs repeat/argsort/bincount, every one of which the transpiler rejects --\n# seeding them is what lets the whole compute lower to PURE C++.\n#\n# A deformer is live the instant mc.deformer() creates it, so "no rest mesh yet"\n# and "rings not built yet" are the NORMAL startup states, not exotic ones -- the\n# gates below are the common path, not error handling.\n#\n# They are PURELY NUMERIC and nested rather than a try/except, for two reasons.\n# nd_lower strips a top-level eager guard on the generic compute path but NOT on\n# the deform path, so a try here would drop the node to the AI porter and break\n# the pure-C++ rule. And the nesting is what makes that safe: an unconnected mesh\n# input reads as None, but `ringWidth > 0` can only be true once Rebuild Rings\n# has run, and that refuses to run without a rest mesh connected -- so the\n# `self.restMesh` read is unreachable until a rest mesh exists. (Merely\n# DISCONNECTING one later does not resurrect the None: Maya retains the last mesh\n# in the datablock.) setPoints stays UNCONDITIONAL so the deformer keeps its\n# single getPoints/setPoints shape; the gates only choose what gets written.\nmesh = self.outputGeometry[0]\nP = mesh.getPoints()\nN = P.shape[0]\nflat = np.asarray(self.ringNbrs, dtype=np.int64)\nKw = int(self.ringWidth)\n\nout = P\nif (Kw > 0) and (flat.shape[0] == N * Kw):\n    rest = self.restMesh.points\n    if rest.shape[0] == N:\n        out = patch_relax(P, rest, flat.reshape(N, Kw), int(self.iterations),\n                          self.alpha, self.surfaceBlend)\nmesh.setPoints(P + self.envelope * (out - P))\n'
INIT        = 'import numpy as np\nfrom mpynode._common.nodes.mesh.patch_relax import patch_relax\n'
USER_INPUTS = {"restMesh": "mesh", "ringNbrs": "long", "ringWidth": "long", "iterations": "long", "alpha": "double", "surfaceBlend": "double"}
IS_SKIN     = False
TOL         = 1e-3


# Every pick lands inside its attr's range: see _fit.
_RANGED           = ("double", "float", "long", "short", "doubleAngle", "doubleLinear")
_RANGED_COMPOUNDS = ("double3", "euler", "position", "color", "float2")
_BOUNDS = (("minExists", "minimum", max),
           ("maxExists", "maximum", min),
           ("softMinExists", "softMin", max),
           ("softMaxExists", "softMax", min))


def _range(nodes, attr):
    # The tightest hard bound any node declares, narrowed by a soft range
    # unless the soft range contradicts it. Either end may be None.
    b = [None, None, None, None]
    for nd in nodes:
        for i, (has, get, pick) in enumerate(_BOUNDS):
            try:
                if not cmds.attributeQuery(attr, node=nd, **{has: True}):
                    continue
                v = float(cmds.attributeQuery(attr, node=nd, **{get: True})[0])
            except Exception:
                continue
            b[i] = v if b[i] is None else pick(b[i], v)
    lo = b[0] if b[2] is None else (b[2] if b[0] is None else max(b[0], b[2]))
    hi = b[1] if b[3] is None else (b[3] if b[1] is None else min(b[1], b[3]))
    if lo is not None and hi is not None and lo > hi:
        return b[0], b[1]
    return lo, hi


def _fold(v, lo, hi):
    # A value inside comes back untouched; one outside is reflected off the
    # bound it crossed, so out-of-range picks spread over the range.
    if (lo is None or v >= lo) and (hi is None or v <= hi):
        return v
    if lo is not None and hi is not None:
        if hi <= lo:
            return lo
        span = hi - lo
        r    = (v - lo) % (2 * span)
        return lo + (r if r <= span else 2 * span - r)
    if lo is not None:
        return 2 * lo - v
    return 2 * hi - v


def _fit(nodes, attr, t, v):
    # v inside attr's range on every node that has attr; a numeric compound
    # is fitted one child at a time.
    nodes = [n for n in nodes if n and cmds.objExists(n + "." + attr)]
    if t in _RANGED_COMPOUNDS and isinstance(v, (list, tuple)):
        kids = []
        for nd in nodes:
            kids = cmds.attributeQuery(attr, node=nd, listChildren=True) or []
            if kids:
                break
        if len(kids) != len(v):
            return v
        return [_fold(x, *_range(nodes, k)) for x, k in zip(v, kids)]
    if t not in _RANGED or isinstance(v, bool):
        return v
    if not isinstance(v, (int, float)):
        return v
    lo, hi = _range(nodes, attr)
    if t in ("long", "short"):
        lo = None if lo is None else math.ceil(lo)
        hi = None if hi is None else math.floor(hi)
        return int(round(_fold(v, lo, hi)))
    return _fold(v, lo, hi)


def _sample(t):
    if t == "bool": return random.choice([0, 1])
    if t == "long": return random.randint(-3, 3)
    if t == "enum": return random.randint(0, 1)
    if t in ("double3", "euler", "position"):
        return [random.uniform(-2, 2) for _ in range(3)]
    return random.uniform(-2, 2)


def _set(node, attr, t, v):
    if t in ("double3", "euler", "position"):
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def _pts(mesh):
    return cmds.xform(mesh + ".vtx[*]", q=True, os=True, t=True)


def _apply(deformer_type, configure):
    tr = cmds.polySphere(r=1, sx=12, sy=12, ch=False)[0]
    d  = cmds.deformer(tr, type=deformer_type)[0]
    if configure:
        configure(d)
    return tr, d


def run(samples=12):
    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    if IS_SKIN:
        print("NOTE: skinCluster parity needs a bound influence set "
              "(matrix[]/bindPreMatrix[]/weights). Without joints both nodes "
              "are identity; wire a rig for a meaningful comparison.")

    import mpynode

    def cfg(node):
        w = mpynode.wrap_node(node)
        for nm, t in USER_INPUTS.items():
            try:
                w.add_input_attr(nm, t)
            except Exception:
                pass
        if INIT.strip():
            w.set_init_expression(INIT)
        w.set_compute_expression(COMPUTE)

    src_tr, src_d = _apply(SRC_TYPE, cfg)
    cmp_tr, cmp_d = _apply(NODE_TYPE, None)

    fails = 0
    for _ in range(samples):
        env = random.uniform(0.0, 1.0)
        cmds.setAttr(src_d + ".envelope", env)
        cmds.setAttr(cmp_d + ".envelope", env)
        for a, t in USER_INPUTS.items():
            v = _fit((src_d, cmp_d), a, t, _sample(t))
            if cmds.objExists(src_d + "." + a):
                _set(src_d, a, t, v)
            if cmds.objExists(cmp_d + "." + a):
                _set(cmp_d, a, t, v)
        a_pts = _pts(src_tr)
        b_pts = _pts(cmp_tr)
        if len(a_pts) != len(b_pts):
            print("VERTEX COUNT MISMATCH", len(a_pts), len(b_pts))
            fails += 1
            continue
        for i in range(len(a_pts)):
            if abs(a_pts[i] - b_pts[i]) > TOL:
                print("MISMATCH coord", i, a_pts[i], "!=", b_pts[i])
                fails += 1
                break
    print("VERIFY", "PASS" if not fails else ("FAIL " + str(fails)))
    return fails == 0


if __name__ == "__main__":
    run()
