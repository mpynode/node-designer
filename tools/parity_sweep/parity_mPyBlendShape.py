import os, sys, random
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(ROOT, "plug-ins"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
for p in ("mpynode_api1", "mpynode_api2"):
    if not cmds.pluginInfo(p, q=True, loaded=True):
        cmds.loadPlugin(p, quiet=True)

random.seed(1234)

NATIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyBlendShape")
BUNDLE = os.path.join(NATIVE_DIR, "customSquash.bundle")
NODE_TYPE = "customSquash"
SRC_TYPE = "mPyBlendShape"
COMPUTE = ('mesh = self.outputGeometry[0]\n'
           'rest = mesh.getPoints()\n'
           'env = float(self.envelope)\n'
           's = float(self.squash)\n'
           'if s < 1e-4:\n'
           '    s = 1e-4\n'
           'inv = 1.0 / (s ** 0.5)\n'
           'out = rest.copy()\n'
           'out[:, 0] = rest[:, 0] * inv\n'
           'out[:, 1] = rest[:, 1] * s\n'
           'out[:, 2] = rest[:, 2] * inv\n'
           'out = rest + env * (out - rest)\n'
           'mesh.setPoints(out)\n')
INIT = 'import numpy as np\n'
USER_INPUTS = {"squash": "float"}
TOL = 1e-4
SAMPLES = 14


def fail(reason):
    print("RESULT_LINE", "FAIL", "maxerr=None", "samples=0",
          "components=0", "reason=" + reason)
    maya.standalone.uninitialize()
    sys.exit(0)


# Load compiled bundle
if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
    cmds.loadPlugin(BUNDLE)
if NODE_TYPE not in cmds.pluginInfo(os.path.basename(BUNDLE), q=True, dependNode=True):
    fail("native node type %s not registered by bundle" % NODE_TYPE)

import mpynode


def _apply(deformer_type, configure):
    tr = cmds.polySphere(r=1, sx=12, sy=12, ch=False)[0]
    d = cmds.deformer(tr, type=deformer_type)[0]
    if configure:
        configure(d)
    return tr, d


def cfg(node):
    w = mpynode.wrap(node)
    for nm, t in USER_INPUTS.items():
        try:
            w.add_input_attr(nm, t)
        except Exception as e:
            print("WARN add_input_attr", nm, e)
    if INIT.strip():
        w.set_init_expression(INIT)
    w.set_compute_expression(COMPUTE)


def _pts(mesh):
    return cmds.xform(mesh + ".vtx[*]", q=True, os=True, t=True)


# Build the real Python reference node
try:
    src_tr, src_d = _apply(SRC_TYPE, cfg)
except Exception as e:
    fail("could not build python reference deformer: %r" % e)

# Build the compiled native node
try:
    cmp_tr, cmp_d = _apply(NODE_TYPE, None)
except Exception as e:
    fail("could not build native deformer: %r" % e)

if not cmds.objExists(src_d) or not cmds.objExists(cmp_d):
    fail("deformer node(s) missing after creation")

# Confirm the python ref squash attr exists (it is a user-added attr)
have_src_squash = cmds.objExists(src_d + ".squash")
have_cmp_squash = cmds.objExists(cmp_d + ".squash")
print("ATTR src.squash=%s cmp.squash=%s" % (have_src_squash, have_cmp_squash))

maxerr = 0.0
components = 0
nsamp = 0
mismatch = 0

for k in range(SAMPLES):
    env = random.uniform(0.0, 1.0)
    sval = random.uniform(-2.0, 2.0)
    cmds.setAttr(src_d + ".envelope", env)
    cmds.setAttr(cmp_d + ".envelope", env)
    if have_src_squash:
        cmds.setAttr(src_d + ".squash", sval)
    if have_cmp_squash:
        cmds.setAttr(cmp_d + ".squash", sval)

    a_pts = _pts(src_tr)
    b_pts = _pts(cmp_tr)
    if len(a_pts) != len(b_pts) or len(a_pts) == 0:
        print("VERTEX/COORD COUNT MISMATCH", len(a_pts), len(b_pts))
        mismatch += 1
        continue
    nsamp += 1
    for i in range(len(a_pts)):
        e = abs(a_pts[i] - b_pts[i])
        components += 1
        if e > maxerr:
            maxerr = e

print("ATTR_SAMPLE last env=%.5f squash=%.5f" % (env, sval))
print("FIRST_COORDS src=%s cmp=%s" % (_pts(src_tr)[:3], _pts(cmp_tr)[:3]))

ok = (components > 0 and mismatch == 0 and maxerr <= TOL)
print("RESULT_LINE", "PASS" if ok else "FAIL",
      "maxerr=%.6e" % maxerr,
      "samples=%d" % nsamp,
      "components=%d" % components,
      "tol=%.1e" % TOL)

maya.standalone.uninitialize()
