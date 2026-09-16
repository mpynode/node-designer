import os, sys, random, math
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(ROOT, "plug-ins"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
for p in ("mpynode_api1", "mpynode_api2"):
    if not cmds.pluginInfo(p, q=True, loaded=True):
        cmds.loadPlugin(p, quiet=True)

# ---- constants read from fixtures/mPyDeformer/verify_in_maya.py ----
BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyDeformer")
BUNDLE    = os.path.join(BUILD_DIR, "sineWaveY.bundle")
NODE_TYPE = "sineWaveY"
SRC_TYPE  = "mPyDeformer"
COMPUTE = ('mesh = self.outputGeometry[0]\nrest = mesh.getPoints()\n'
           'env = float(self.envelope)\namp = float(self.amplitude)\n'
           'freq = float(self.frequency)\nphase = float(self.phase)\n'
           'out = rest.copy()\n'
           'out[:, 1] = rest[:, 1] + env * amp * np.sin(freq * rest[:, 0] + phase)\n'
           'mesh.setPoints(out)\n')
INIT        = "import numpy as np\n"
USER_INPUTS = {"amplitude": "float", "frequency": "float", "phase": "float"}
TOL         = 1e-3

# ---- load the EXISTING compiled bundle (do NOT rebuild) ----
bname = os.path.basename(BUNDLE)
if not cmds.pluginInfo(bname, q=True, loaded=True):
    cmds.loadPlugin(BUNDLE)
assert NODE_TYPE in (cmds.pluginInfo(bname, q=True, dependNode=True) or []), \
    "compiled deformer type not registered by bundle"

import mpynode


def sample_val(t):
    if t == "bool": return random.choice([0, 1])
    if t == "int": return random.randint(-3, 3)
    if t == "vector": return [random.uniform(-2, 2) for _ in range(3)]
    return random.uniform(-2, 2)


def set_val(node, attr, t, v):
    if t == "vector":
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def pts(mesh):
    return cmds.xform(mesh + ".vtx[*]", q=True, os=True, t=True)


# ---- build FRESH Python reference deformer on identical sphere ----
src_tr = cmds.polySphere(r=1, sx=12, sy=12, ch=False)[0]
src_d  = cmds.deformer(src_tr, type=SRC_TYPE)[0]
w      = mpynode.wrap(src_d)
for nm, t in USER_INPUTS.items():
    try:
        w.add_input_attr(nm, t)
    except Exception as e:
        print("add_input_attr warn", nm, e)
if INIT.strip():
    w.set_init_expression(INIT)
w.set_compute_expression(COMPUTE)

# ---- build compiled deformer on identical sphere ----
cmp_tr = cmds.polySphere(r=1, sx=12, sy=12, ch=False)[0]
cmp_d  = cmds.deformer(cmp_tr, type=NODE_TYPE)[0]

print("SRC_DEFORMER", src_d, "CMP_DEFORMER", cmp_d)
print("SRC_INPUTS_PRESENT",
      [a for a in USER_INPUTS if cmds.objExists(src_d + "." + a)])
print("CMP_INPUTS_PRESENT",
      [a for a in USER_INPUTS if cmds.objExists(cmp_d + "." + a)])

random.seed(20260617)
maxerr     = 0.0
components = 0
samples    = 14
fails      = 0
for s in range(samples):
    env = random.uniform(0.0, 1.0)
    cmds.setAttr(src_d + ".envelope", env)
    cmds.setAttr(cmp_d + ".envelope", env)
    chosen = {}
    for a, t in USER_INPUTS.items():
        v         = sample_val(t)
        chosen[a] = v
        if cmds.objExists(src_d + "." + a):
            set_val(src_d, a, t, v)
        if cmds.objExists(cmp_d + "." + a):
            set_val(cmp_d, a, t, v)
    a_pts = pts(src_tr)
    b_pts = pts(cmp_tr)
    if len(a_pts) != len(b_pts):
        print("VERTEX COUNT MISMATCH", len(a_pts), len(b_pts))
        fails += 1
        continue
    serr = 0.0
    for i in range(len(a_pts)):
        e = abs(a_pts[i] - b_pts[i])
        if e > serr:
            serr = e
        if e > maxerr:
            maxerr = e
        components += 1
    if serr > TOL:
        fails += 1
        print("SAMPLE", s, "env=%.4f" % env, chosen, "serr=%.3e" % serr)

print("RESULT samples=%d components=%d maxerr=%.6e tol=%.1e fails=%d" % (
    samples, components, maxerr, TOL, fails))
print("VERIFY", "PASS" if (fails == 0 and components > 0 and maxerr <= TOL)
      else "FAIL")
