"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run in Maya. Builds two identical spheres, applies the original mPy
deformer (expression copied from the source) to one and the compiled
deformer to the other, then compares object-space points over random
envelope/input samples.
"""
import os, random
import maya.cmds as cmds

BUNDLE = os.path.join(os.path.dirname(__file__), 'twistSwingSkin.bundle')
NODE_TYPE = 'twistSwingSkin'
SRC_TYPE = 'mPySkinCluster'
COMPUTE = '# ----------------------------------------------------------------------\n# mPySkinCluster -- twist/swing with TWO weight sets on ONE node, painted\n# interactively via the skinMode enum, COMPILABLE to pure C++.\n#\n# self.twistWeights / self.swingWeights are declared (double, is_array) INPUT\n# plugs holding the two dense weight sets FLATTENED row-major to length N*J:\n# twistWeights drives the DUAL-QUATERNION twist, swingWeights the LINEAR-BLEND\n# swing (bend). Being plugs, they serialize PER NODE (each character keeps its\n# own weights) and the compiled deform reads them directly -- so this node\n# compiles to byte-parity (the two sets are never shared across instances).\n#\n# skinMode is a PAINT-MODE selector:\n#   0 Paint LBS (Swing) -> preview the live weightList with linear_blend; paint it\n#                          and sync_paint banks the edits into swingWeights.\n#   1 Paint DQS (Twist) -> preview the live weightList with dual_quaternion; paint\n#                          it and sync_paint banks the edits into twistWeights.\n#   2 Live Result       -> deform from BOTH weight-set plugs (twist + swing).\n# twistAxis picks the bone-local twist axis (0 X default / 1 Y / 2 Z).\n#\n# self.sync_paint(mode) holds ALL the interactive machinery (load the active set\n# into weightList on a mode switch so Paint Skin Weights shows it; bank painted\n# weightList back into the active set plug on a settled eval). It is a blessed\n# NativeSideEffect method: interpreted-only, and a bare call lowers to NOTHING in\n# the compiled node (which runs headless -- no paint session -- and reads the two\n# weight plugs directly, so omitting the scratchpad staging is faithful).\n# ----------------------------------------------------------------------\n\nmesh = self.outputGeometry[0]\nrest = mesh.getPoints()                         # (N, 3) object-space rest points\n\nmode = int(self.skinMode)\n\n# interactive paint load/bank/latch (a no-op in the compiled node).\nself.sync_paint(mode)\n\nnj = self.matrix.shape[0]                        # influence count\nnv = rest.shape[0]                               # vertex count\ntwist = np.asarray(self.twistWeights)            # flat (N*J,) weight-set plugs\nswing = np.asarray(self.swingWeights)\nhave_sets = twist.size == nv * nj and swing.size == nv * nj\n\nif mode == 0:                                    # Paint LBS: preview live weightList\n    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)\nelif mode == 1:                                  # Paint DQS: preview live weightList\n    deformed = self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)\nelif have_sets:                                  # Live Result: both weight-set plugs\n    deformed = self.twist_swing_dual(rest, twist.reshape(nv, nj), swing.reshape(nv, nj), self.matrix, self.bindPreMatrix, int(self.twistAxis))\nelse:                                            # not seeded yet -> plain LBS fallback\n    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)\n\n# envelope=0 rest, 1 fully skinned (partial-effect composition explicit here).\nmesh.setPoints(rest + float(self.envelope) * (deformed - rest))\n'
INIT = 'import numpy as np\n'
USER_INPUTS = {"twistWeights": "double", "swingWeights": "double", "skinMode": "enum", "twistAxis": "enum"}
IS_SKIN = True
TOL = 1e-3


def _sample(t):
    if t == "bool": return random.choice([0, 1])
    if t == "int": return random.randint(-3, 3)
    if t == "enum": return random.randint(0, 1)
    if t in ("vector", "euler"): return [random.uniform(-2, 2) for _ in range(3)]
    return random.uniform(-2, 2)


def _set(node, attr, t, v):
    if t in ("vector", "euler"):
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def _pts(mesh):
    return cmds.xform(mesh + ".vtx[*]", q=True, os=True, t=True)


def _apply(deformer_type, configure):
    tr = cmds.polySphere(r=1, sx=12, sy=12, ch=False)[0]
    d = cmds.deformer(tr, type=deformer_type)[0]
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
            v = _sample(t)
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
