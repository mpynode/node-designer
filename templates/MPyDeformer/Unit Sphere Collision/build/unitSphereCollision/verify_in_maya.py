"""Equivalence check: compiled native DEFORMER vs the original mPy deformer.
Run in Maya. Builds two identical spheres, applies the original mPy
deformer (expression copied from the source) to one and the compiled
deformer to the other, then compares object-space points over random
envelope/input samples.
"""
import os, random
import maya.cmds as cmds

BUNDLE      = os.path.join(os.path.dirname(__file__), 'unitSphereCollision.bundle')
NODE_TYPE   = 'unitSphereCollision'
SRC_TYPE    = 'mPyDeformer'
COMPUTE     = '# Unit-sphere collision deformer (accumulating "pusher" port). Every vertex\n# INSIDE the collider sphere is pushed onto its surface, and the pushed result\n# is kept in a persistent buffer (self.positions) so the deformation BAKES --\n# once the collider passes, the dent stays put (it does not spring back). The\n# collider is the UNIT sphere in the local space of the `pusher` matrix, so\n# wiring a sphere transform\'s worldMatrix into `pusher` makes its translate /\n# rotate / scale set the collider\'s centre, orientation and effective radius.\n#\n# self.positions is registered + seeded by the node\'s setup from the mesh\'s\n# initial points; if it is missing or stale (topology change) it is re-seeded\n# here from the current input. A deformer is not evaluated until a mesh is\n# connected, so nothing computes before then.\n#\n# WARNING: getPoints()/setPoints() are OBJECT space while `pusher` is a WORLD\n# matrix, so this is only correct when the deformed mesh has an identity\n# transform at the world origin (freeze its transform).\nmesh = self.outputGeometry[0]\npts = mesh.getPoints()                         # (N, 3) current input, object space\nif len(pts):\n    seed = np.hstack([np.asarray(pts, dtype=float), np.ones((len(pts), 1))])\n    try:\n        buf = np.asarray(self.positions, dtype=float)\n    except Exception:\n        buf = None\n    if buf is None or buf.ndim != 2 or buf.shape != (len(pts), 4):\n        buf = seed                             # first eval / topology change -> seed\n\n    P = buf.copy()\n    M = self.pusher                            # collider world matrix (MatrixView)\n    inv = M.inverse().asNumpy()                # api2 analytic inverse (EM-safe)\n    fwd = np.asarray(M, dtype=float)\n\n    local = P @ inv                            # accumulated buffer -> collider local\n    dist = np.linalg.norm(local[:, :3], axis=1)\n    inside = (dist > 0.0) & (dist < 1.0)       # guard dist==0 (no push direction)\n    local[inside, :3] = local[inside, :3] / dist[inside, None]   # onto surface\n    P = local @ fwd                            # back to object space (buffer accumulates)\n\n    self.positions = P                         # persist the baked buffer\n    env = self.envelope                 # blend the baked buffer against rest\n    mesh.setPoints(pts + env * (P[:, :3] - pts))\n'
INIT        = 'import numpy as np\n'
USER_INPUTS = {"pusher": "matrix"}
IS_SKIN     = False
TOL         = 1e-3


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
