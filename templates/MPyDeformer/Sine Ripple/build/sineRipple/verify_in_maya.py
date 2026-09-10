"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run in Maya. Builds two identical spheres, applies the original mPy
deformer (expression copied from the source) to one and the compiled
deformer to the other, then compares object-space points over random
envelope/input samples.
"""
import os, random
import maya.cmds as cmds

BUNDLE = os.path.join(os.path.dirname(__file__), 'sineRipple.mll')
NODE_TYPE = 'sineRipple'
SRC_TYPE = 'mPyDeformer'
COMPUTE = "# Sine-ripple deformer: each vertex rides a travelling sine wave along its\n# surface normal. The wave's phase advances with distance from the mesh\n# centre and with time, so it animates as the timeline plays.\nmesh = self.outputGeometry[0]            # writable handle for this output mesh\npts = mesh.getPoints()                   # (N, 3) object-space points (numpy)\n\n# True per-vertex normals (object space). The output handle wraps an API-1\n# MFnMesh, so use the in-out MFloatVectorArray form.\nnrm = om.MFloatVectorArray()\nmesh.getVertexNormals(False, nrm, om.MSpace.kObject)\nnormals = np.array([[nrm[i].x, nrm[i].y, nrm[i].z]\n                    for i in range(nrm.length())], dtype=float)\n\namp = self.amplitude\nfreq = self.frequency\nspeed = self.speed\nenv = self.envelope               # built-in deformer envelope (0..1)\n\ncentre = pts.mean(axis=0)\ndist = np.linalg.norm(pts - centre, axis=1)\nphase = 2.0 * np.pi * freq * dist - speed * self.time\noffset = (amp * np.sin(phase))[:, None] * normals\n\nmesh.setPoints(pts + env * offset)\n"
INIT = 'import numpy as np\nimport maya.OpenMaya as om\n'
USER_INPUTS = {"amplitude": "float", "frequency": "float", "speed": "float", "time": "time"}
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
