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

NB      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyTransform")
ORIG_MA = os.path.join(NB, "mPyTransform_bobXform_original.ma")
BUNDLE  = os.path.join(NB, "bobXform.bundle")
TOL     = 1e-4

# 1) Build/load the PYTHON reference: open original scene -> python mPyTransform 'bobXform'
cmds.file(ORIG_MA, open=True, force=True)
# Find the python reference node (mPyTransform type).
py_nodes = cmds.ls(type="mPyTransform") or []
assert py_nodes, "no python mPyTransform node found in original scene"
PY = py_nodes[0]
print("PYREF_NODE", PY, "type", cmds.nodeType(PY))

# 2) Load the compiled bundle and create a real native node (unique name).
if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
    cmds.loadPlugin(BUNDLE)
COMP = cmds.createNode("bobXform")
print("COMP_NODE", COMP, "type", cmds.nodeType(COMP))
assert cmds.objExists(COMP)
assert cmds.objExists(PY)

# 3) Sweep translateX over 8 values; compare all 16 elements of .worldMatrix
#    AND of .offsetParentMatrix.
# NOT .matrix: under the FLUSH-FREE mPyTransform re-arch asMatrix() returns the
# plain TRS on BOTH sides, so a .matrix probe agrees no matter what the
# expression computes (a vacuous pass). The expression's desired LOCAL matrix D
# rides _outLocalFlat -> fourByFourMatrix -> offsetParentMatrix, so for these
# root (unparented) nodes worldMatrix IS D, and reading it exercises the whole
# relay chain end to end.
#
# .offsetParentMatrix is the OTHER free plug: it is the relay's own terminus,
# the plug the node actually authors, where worldMatrix is Maya's downstream
# composition of it. Probing only the composed plug leaves the authored one
# unchecked, so both are compared -- purely additive, the worldMatrix
# comparison below is untouched.
sweep      = [-4.0, -3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0]
maxerr     = 0.0
ncomp      = 0
nsamp      = 0
maxbob     = 0.0
maxbob_opm = 0.0
for tx in sweep:
    cmds.setAttr(PY + ".translateX", tx)
    cmds.setAttr(COMP + ".translateX", tx)
    pm = cmds.getAttr(PY + ".worldMatrix[0]")   # forces eval; flat list of 16
    cm = cmds.getAttr(COMP + ".worldMatrix[0]")
    assert len(pm) == 16 and len(cm) == 16, ("matrix len", len(pm), len(cm))
    nsamp += 1
    for i in range(16):
        e = abs(float(pm[i]) - float(cm[i]))
        ncomp += 1
        if e > maxerr:
            maxerr = e
    # sanity: confirm the bob actually happened in element [3][1] (index 13)
    maxbob = max(maxbob, abs(float(pm[13])), abs(float(cm[13])))

    po = cmds.getAttr(PY + ".offsetParentMatrix")
    co = cmds.getAttr(COMP + ".offsetParentMatrix")
    assert len(po) == 16 and len(co) == 16, ("opm len", len(po), len(co))
    for i in range(16):
        e = abs(float(po[i]) - float(co[i]))
        ncomp += 1
        if e > maxerr:
            maxerr = e
    maxbob_opm = max(maxbob_opm, abs(float(po[13])), abs(float(co[13])))
    print("tx=%.1f py[13]=%.6f cm[13]=%.6f opm py[13]=%.6f cm[13]=%.6f"
          % (tx, pm[13], cm[13], po[13], co[13]))

# NON-VACUITY GUARD: two sides agreeing only means something if the expression
# actually moved the node. A flat 0 bob on both sides means the compute never
# ran -- which is exactly how a fixture written against a stale contract read as
# a PASS. Fail loudly instead of rubber-stamping.
assert maxbob > 1e-3, ("vacuous parity: no bob observed on either side", maxbob)
assert maxbob_opm > 1e-3, ("vacuous parity: offsetParentMatrix never authored",
                           maxbob_opm)

print("RESULT maxerr=%.6e nsamp=%d ncomp=%d tol=%.1e pass=%s"
      % (maxerr, nsamp, ncomp, TOL, maxerr <= TOL))
