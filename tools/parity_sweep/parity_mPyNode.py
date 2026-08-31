import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(ROOT, "plug-ins"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
for p in ("mpynode_api1", "mpynode_api2"):
    if not cmds.pluginInfo(p, q=True, loaded=True):
        cmds.loadPlugin(p, quiet=True)

import random

BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyNode")
ORIG_MA = os.path.join(BUILD, "mPyNode_mathNode_original.ma")
BUNDLE = os.path.join(BUILD, "mathNode.bundle")

# --- 1) Open the original scene (python mPyNode 'mathNode') ---
cmds.file(ORIG_MA, open=True, force=True)
assert cmds.objExists("mathNode"), "python mathNode not found after open"
py_node = "mathNode"
print("PY_NODE_TYPE:", cmds.nodeType(py_node))

# --- 2) Load the native bundle and create the compiled node ---
if not cmds.pluginInfo(BUNDLE, q=True, loaded=True):
    cmds.loadPlugin(BUNDLE, quiet=True)
comp = cmds.createNode("mathNode")  # returns a UNIQUE name (collision with python node name)
print("COMP_NODE:", comp, "TYPE:", cmds.nodeType(comp))
assert cmds.objExists(comp)
assert comp != py_node, "expected unique compiled node name"

random.seed(20260617)

def set_inputs(node, a, b, k, vx, vy, vz):
    cmds.setAttr(node + ".a", a)
    cmds.setAttr(node + ".b", b)
    cmds.setAttr(node + ".k", k)
    cmds.setAttr(node + ".v", vx, vy, vz, type="double3")

def read_outputs(node):
    total = cmds.getAttr(node + ".total")
    vlen = cmds.getAttr(node + ".vlen")
    vsum = cmds.getAttr(node + ".vsum")[0]  # (x,y,z)
    return float(total), float(vlen), float(vsum[0]), float(vsum[1]), float(vsum[2])

N = 25
maxerr = 0.0
components = 0
worst = None
for i in range(N):
    a = random.uniform(-10, 10)
    b = random.uniform(-10, 10)
    k = random.uniform(-10, 10)
    vx = random.uniform(-10, 10)
    vy = random.uniform(-10, 10)
    vz = random.uniform(-10, 10)

    set_inputs(py_node, a, b, k, vx, vy, vz)
    set_inputs(comp, a, b, k, vx, vy, vz)

    po = read_outputs(py_node)
    co = read_outputs(comp)

    for pj, cj in zip(po, co):
        e = abs(pj - cj)
        components += 1
        if e > maxerr:
            maxerr = e
            worst = (i, pj, cj)

print("SAMPLES:", N)
print("COMPONENTS:", components)
print("MAXERR:", repr(maxerr))
print("WORST:", worst)
TOL = 1e-4
PASS = (components > 0) and (maxerr <= TOL)
print("RESULT:", "PASS" if PASS else "FAIL")
