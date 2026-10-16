"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run in Maya. Builds two identical spheres, applies the original mPy
deformer (expression copied from the source) to one and the compiled
deformer to the other, then compares object-space points over random
envelope/input samples.
"""
import os, math, random
import maya.cmds as cmds

BUNDLE      = os.path.join(os.path.dirname(__file__), 'twistSwingSkin.mll')
NODE_TYPE   = 'twistSwingSkin'
SRC_TYPE    = 'mPySkinCluster'
COMPUTE     = '# ----------------------------------------------------------------------\n# mPySkinCluster -- twist/swing with TWO weight sets on ONE node, painted\n# interactively via the skinMode enum, COMPILABLE to pure C++.\n#\n# self.twistWeights / self.swingWeights are declared (double, is_array) INPUT\n# plugs holding the two dense weight sets FLATTENED row-major to length N*J:\n# twistWeights drives the DUAL-QUATERNION twist, swingWeights the LINEAR-BLEND\n# swing (bend). Being plugs, they serialize PER NODE (each character keeps its\n# own weights) and the compiled deform reads them directly -- so this node\n# compiles to byte-parity (the two sets are never shared across instances).\n#\n# skinMode is a PAINT-MODE selector:\n#   0 Paint LBS (Swing) -> preview the live weightList with linear_blend; paint it\n#                          and sync_paint banks the edits into swingWeights.\n#   1 Paint DQS (Twist) -> preview the live weightList with dual_quaternion; paint\n#                          it and sync_paint banks the edits into twistWeights.\n#   2 Live Result       -> deform from BOTH weight-set plugs (twist + swing).\n# twistAxis picks the bone-local twist axis (0 X default / 1 Y / 2 Z).\n#\n# self.sync_paint(mode) holds ALL the interactive machinery (load the active set\n# into weightList on a mode switch so Paint Skin Weights shows it; bank painted\n# weightList back into the active set plug on a settled eval). It is a blessed\n# NativeSideEffect method: interpreted-only, and a bare call lowers to NOTHING in\n# the compiled node (which runs headless -- no paint session -- and reads the two\n# weight plugs directly, so omitting the scratchpad staging is faithful).\n# ----------------------------------------------------------------------\n\nmesh = self.outputGeometry[0]\nrest = mesh.getPoints()                         # (N, 3) object-space rest points\n\nmode = int(self.skinMode)\n\n# interactive paint load/bank/latch (a no-op in the compiled node).\nself.sync_paint(mode)\n\nnj = self.matrix.shape[0]                        # influence count\nnv = rest.shape[0]                               # vertex count\ntwist = np.asarray(self.twistWeights)            # flat (N*J,) weight-set plugs\nswing = np.asarray(self.swingWeights)\nhave_sets = twist.size == nv * nj and swing.size == nv * nj\n\nif mode == 0:                                    # Paint LBS: preview live weightList\n    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)\nelif mode == 1:                                  # Paint DQS: preview live weightList\n    deformed = self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)\nelif have_sets:                                  # Live Result: both weight-set plugs\n    deformed = self.twist_swing_dual(rest, twist.reshape(nv, nj), swing.reshape(nv, nj), self.matrix, self.bindPreMatrix, int(self.twistAxis))\nelse:                                            # not seeded yet -> plain LBS fallback\n    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)\n\n# envelope=0 rest, 1 fully skinned (partial-effect composition explicit here).\nmesh.setPoints(rest + float(self.envelope) * (deformed - rest))\n'
INIT        = 'import numpy as np\n'
USER_INPUTS = {"twistWeights": "double", "swingWeights": "double", "skinMode": "enum", "twistAxis": "enum"}
IS_SKIN     = True
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
