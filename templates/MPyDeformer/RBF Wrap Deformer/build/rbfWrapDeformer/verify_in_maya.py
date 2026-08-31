"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run in Maya. Builds two identical spheres, applies the original mPy
deformer (expression copied from the source) to one and the compiled
deformer to the other, then compares object-space points over random
envelope/input samples.
"""
import os, random
import maya.cmds as cmds

BUNDLE = os.path.join(os.path.dirname(__file__), 'rbfWrapDeformer.bundle')
NODE_TYPE = 'rbfWrapDeformer'
SRC_TYPE = 'mPyDeformer'
COMPUTE = "# RBF thin-plate-spline WRAP, as a DEFORMER. Two control cages of identical\n# topology -- `restCage` (rest positions) and `deformCage` (deformed positions) --\n# define a smooth space warp that carries every point of the deformed geometry\n# from rest to deformed space. The warp is the classic thin-plate spline: kernel\n# phi(r) = r^2 * log(r) (== 0.5 * d2 * log(d2), so no sqrt) plus an affine\n# polynomial tail, so a rigid/affine cage motion is reproduced EXACTLY and a\n# non-affine cage motion bends the geometry as smoothly as possible.\n#\n# Unlike the mPyNode rbf_wrap (three mesh INPUTS + a mesh OUTPUT), the geometry to\n# deform is the deformer's own `outputGeometry` -- so this node stacks in a normal\n# deformation chain and honours `envelope` (0 = rest, 1 = fully warped).\n#\n# A deformer is LIVE the moment mc.deformer() creates it, so the never-connected\n# and mismatched cage states are normal, not exotic. `hasCage` is a purely NUMERIC\n# no-op gate (no try/except -- that would drop the node to the AI porter): the\n# warp is only applied when both cages carry points AND agree on point count.\n# `Mm` clamps the deform-cage copy so a half-wired node never shape-mismatches.\n# (Note: DISCONNECTING a cage does not reach this gate -- Maya retains the last\n# mesh in the datablock, so the compute keeps seeing the old point count.)\n#\n# The whole compute lowers to PURE C++: pairwise squared distances (matmul-identity\n# form), the guarded r^2 log r kernel (via where/maximum -- no nan to clean up),\n# the augmented (M+4) system built with zeros + slice-stores, Tikhonov-regularised\n# and solved by nd::inv, then the evaluation matmul. A tiny 1e-8*I keeps the solve\n# off nd::inv's singular fallback and tightens interp(LAPACK)-vs-compiled\n# (Gauss-Jordan) agreement.\n#\n# WARNING: getPoints()/setPoints() are OBJECT space while the cages are read in\n# WORLD space (worldMesh), so this is only correct when the deformed mesh has an\n# identity transform at the world origin (freeze its transform).\nmesh = self.outputGeometry[0]\nrest = self.restCage.points\ndeform = self.deformCage.points\nP = mesh.getPoints()\nM = rest.shape[0]\nMd = deform.shape[0]\nMm = min(M, Md)\nNn = P.shape[0]\nrc = (rest * rest).sum(1)\nd2 = rc[:, None] + rc[None, :] - 2.0 * (rest @ rest.T)\nd2 = np.maximum(d2, 0.0)\nK = np.where(d2 > 1e-12, 0.5 * d2 * np.log(np.maximum(d2, 1e-12)), 0.0)\nA = np.zeros((M + 4, M + 4))\nA[:M, :M] = K\nA[:M, M] = 1.0\nA[:M, M + 1:] = rest\nA[M, :M] = 1.0\nA[M + 1:, :M] = rest.T\nA = A + 1e-8 * np.eye(M + 4)\nT = np.zeros((M + 4, 3))\nT[:Mm, :] = deform[:Mm, :]\nW = np.linalg.inv(A) @ T\npc = (P * P).sum(1)\ne2 = pc[:, None] + rc[None, :] - 2.0 * (P @ rest.T)\ne2 = np.maximum(e2, 0.0)\nKe = np.where(e2 > 1e-12, 0.5 * e2 * np.log(np.maximum(e2, 1e-12)), 0.0)\nH = np.zeros((Nn, M + 4))\nH[:, :M] = Ke\nH[:, M] = 1.0\nH[:, M + 1:] = P\nwarped = H @ W\nhasCage = 1.0 if (M > 0 and M == Md) else 0.0\nmesh.setPoints(P + (self.envelope * hasCage) * (warped - P))\n"
INIT = 'import numpy as np\n'
USER_INPUTS = {"restCage": "mesh", "deformCage": "mesh"}
IS_SKIN = False
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
