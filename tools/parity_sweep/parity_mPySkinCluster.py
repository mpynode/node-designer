import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(ROOT, "plug-ins"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds
for p in ("mpynode_api1", "mpynode_api2"):
    if not cmds.pluginInfo(p, q=True, loaded=True):
        cmds.loadPlugin(p, quiet=True)

import maya.api.OpenMaya as om

NATIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPySkinCluster", "customLBS.bundle")
TOL = 1e-4

COMPUTE = ('mesh = self.outputGeometry[0]\nrest = mesh.getPoints()\nN = rest.shape[0]\nJ = 2\n'
           'env = float(self.envelope)\n'
           'M = [np.asarray(self.bindPreMatrix[j]) @ np.asarray(self.matrix[j]) for j in range(J)]\n'
           'out = rest.copy()\n'
           'for i in range(N):\n'
           '    wl = self.weightList[i].weights\n'
           '    px, py, pz = rest[i, 0], rest[i, 1], rest[i, 2]\n'
           '    ax = 0.0\n    ay = 0.0\n    az = 0.0\n'
           '    for j in range(J):\n'
           '        w = wl[j]\n        m = M[j]\n'
           '        tx = px * m[0, 0] + py * m[1, 0] + pz * m[2, 0] + m[3, 0]\n'
           '        ty = px * m[0, 1] + py * m[1, 1] + pz * m[2, 1] + m[3, 1]\n'
           '        tz = px * m[0, 2] + py * m[1, 2] + pz * m[2, 2] + m[3, 2]\n'
           '        ax += w * tx\n        ay += w * ty\n        az += w * tz\n'
           '    out[i, 0] = px + env * (ax - px)\n'
           '    out[i, 1] = py + env * (ay - py)\n'
           '    out[i, 2] = pz + env * (az - pz)\n'
           'mesh.setPoints(out)\n')
INIT = "import numpy as np\n"


def _orig_shape_points(mesh_xform):
    """Read object-space points from the INTERMEDIATE (orig/input) shape of a
    deformed mesh via OpenMaya. Does NOT trigger a deformer eval."""
    shapes = cmds.listRelatives(mesh_xform, shapes=True, fullPath=True) or []
    orig = None
    for s in shapes:
        if cmds.getAttr(s + ".intermediateObject"):
            orig = s
            break
    if orig is None:
        # no intermediate yet; fall back to the only shape
        orig = shapes[0]
    sel = om.MSelectionList()
    sel.add(orig)
    dag = sel.getDagPath(0)
    fn = om.MFnMesh(dag)
    pa = fn.getPoints(om.MSpace.kObject)
    return [(pa[k].x, pa[k].y, pa[k].z) for k in range(len(pa))]


def build_rig(prefix, deformer_type, configure=None):
    """Build a cylinder + 2-joint chain, bind with given deformer, set
    height-linear native weightList weights. Returns (mesh_xform, deformer)."""
    # poly cylinder: height 10, 12 sides, 10 subdivs height
    cyl = cmds.polyCylinder(h=10, sx=12, sy=10, name=prefix + "_cyl")[0]
    cmds.delete(cyl, ch=True)

    # 2-joint chain: base at origin, mid up +Y (height 5 = half the cylinder)
    cmds.select(clear=True)
    jb = cmds.joint(name=prefix + "_jb", p=(0, -5, 0))
    jm = cmds.joint(name=prefix + "_jm", p=(0, 0, 0))  # mid at cylinder center
    cmds.select(clear=True)

    # create the deformer (skinCluster-family) on the mesh
    d = cmds.deformer(cyl, type=deformer_type)[0]

    if configure:
        configure(d)

    # wire joint world matrices into matrix[0]/matrix[1]
    cmds.connectAttr(jb + ".worldMatrix[0]", d + ".matrix[0]", force=True)
    cmds.connectAttr(jm + ".worldMatrix[0]", d + ".matrix[1]", force=True)

    # bindPreMatrix = inverse of joint world at bind time
    jbm = cmds.getAttr(jb + ".worldInverseMatrix[0]")
    jmm = cmds.getAttr(jm + ".worldInverseMatrix[0]")
    cmds.setAttr(d + ".bindPreMatrix[0]", *jbm, type="matrix")
    cmds.setAttr(d + ".bindPreMatrix[1]", *jmm, type="matrix")

    # disable normalization BEFORE setting weights
    try:
        cmds.setAttr(d + ".normalizeWeights", 0)
    except Exception:
        pass

    # set IDENTICAL height-linear native weightList weights per vertex,
    # BEFORE first eval. base joint at y=-5, mid at y=0 (top at +5).
    # CRITICAL: read rest positions from the INTERMEDIATE (orig) input shape,
    # NOT the deformed output (cyl.vtx[*]) -- querying the output would force a
    # deformer eval here, and a real kSkinCluster locks in a 0.5/0.5 weight
    # default on first eval and then resists setAttr. Read the orig shape via
    # OpenMaya so no deformer eval is triggered before weights are set.
    rest_pts = _orig_shape_points(cyl)
    nverts = len(rest_pts)
    for i in range(nverts):
        y = rest_pts[i][1]
        # map y in [-5,5] to t in [0,1]; w_mid = t, w_base = 1-t
        t = (y + 5.0) / 10.0
        t = max(0.0, min(1.0, t))
        w_base = 1.0 - t
        w_mid = t
        cmds.setAttr(d + ".weightList[%d].weights[0]" % i, w_base)
        cmds.setAttr(d + ".weightList[%d].weights[1]" % i, w_mid)

    return cyl, d, jb, jm


def get_os_points(mesh_xform):
    """Read object-space points of the deformed output via OpenMaya (forces eval)."""
    shapes = cmds.listRelatives(mesh_xform, shapes=True, noIntermediate=True, fullPath=True)
    shape = shapes[0]
    sel = om.MSelectionList()
    sel.add(shape)
    dag = sel.getDagPath(0)
    fn = om.MFnMesh(dag)
    pa = fn.getPoints(om.MSpace.kObject)
    out = []
    for k in range(len(pa)):
        out.append((pa[k].x, pa[k].y, pa[k].z))
    return out


def main():
    cmds.file(new=True, force=True)

    if not cmds.pluginInfo(os.path.basename(NATIVE), q=True, loaded=True):
        cmds.loadPlugin(NATIVE)

    print("PY mPySkinCluster registered:", "mPySkinCluster" in (cmds.pluginInfo("mpynode_api2", q=True, dependNode=True) or []) or cmds.objExists)
    python_ref_built = False

    import mpynode

    def cfg(node):
        w = mpynode.wrap(node)
        if INIT.strip():
            w.set_init_expression(INIT)
        w.set_compute_expression(COMPUTE)

    # Rig 1: PYTHON mPySkinCluster
    try:
        py_cyl, py_d, py_jb, py_jm = build_rig("py", "mPySkinCluster", cfg)
        python_ref_built = True
        print("PYTHON RIG BUILT deformer=", py_d)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("RESULT builds_loads=%s python_ref_built=False components=0 maxerr=None pass=False reason=python_bind_failed:%s" % (True, e))
        return

    # Rig 2: COMPILED customLBS
    cmp_cyl, cmp_d, cmp_jb, cmp_jm = build_rig("cmp", "customLBS", None)
    print("COMPILED RIG BUILT deformer=", cmp_d)

    # ensure envelope = 1 on both
    cmds.setAttr(py_d + ".envelope", 1.0)
    cmds.setAttr(cmp_d + ".envelope", 1.0)

    angles = [0.0, 15.0, 30.0, 45.0, 60.0, 90.0, -30.0, -60.0]
    maxerr = 0.0
    total_components = 0
    nsamples = 0

    for ang in angles:
        cmds.setAttr(py_jm + ".rotateZ", ang)
        cmds.setAttr(cmp_jm + ".rotateZ", ang)
        a = get_os_points(py_cyl)
        b = get_os_points(cmp_cyl)
        if len(a) != len(b):
            print("VERTEX COUNT MISMATCH", len(a), len(b))
            print("RESULT builds_loads=True python_ref_built=True components=0 maxerr=None pass=False reason=vtx_count_mismatch")
            return
        nsamples += 1
        for i in range(len(a)):
            for c in range(3):
                e = abs(a[i][c] - b[i][c])
                if e > maxerr:
                    maxerr = e
                total_components += 1

    # sanity: confirm the rig actually deforms (not identity) at 45 deg
    cmds.setAttr(py_jm + ".rotateZ", 45.0)
    cmds.setAttr(cmp_jm + ".rotateZ", 45.0)
    p0 = get_os_points(py_cyl)
    cmds.setAttr(py_jm + ".rotateZ", 0.0)
    p_rest = get_os_points(py_cyl)
    disp = max(abs(p0[i][c] - p_rest[i][c]) for i in range(len(p0)) for c in range(3))
    print("DEFORM SANITY max displacement (45deg vs rest):", disp)

    passed = (maxerr <= TOL) and (total_components > 0) and (disp > 1e-3)
    print("RESULT builds_loads=True python_ref_built=True components=%d samples=%d maxerr=%.12g tol=%g deform_disp=%.6g pass=%s"
          % (total_components, nsamples, maxerr, TOL, disp, passed))


if __name__ == "__main__":
    main()
