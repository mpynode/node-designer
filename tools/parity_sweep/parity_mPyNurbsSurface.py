import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(ROOT, "plug-ins"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import maya.standalone
maya.standalone.initialize()
import maya.cmds as cmds
import maya.api.OpenMaya as om

for p in ("mpynode_api1", "mpynode_api2"):
    if not cmds.pluginInfo(p, q=True, loaded=True):
        cmds.loadPlugin(p, quiet=True)

BUILD   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyNurbsSurface")
ORIG_MA = os.path.join(BUILD, "mPyNurbsSurface_waveSurf_original.ma")
BUNDLE  = os.path.join(BUILD, "waveSurf.bundle")
TOL     = 1e-4

# --- open original scene (provides python ref node 'waveSurfSrc') ---
cmds.file(ORIG_MA, open=True, force=True)
assert cmds.objExists("waveSurfSrc"), "original python ref node missing"
print("PYREF_TYPE", cmds.nodeType("waveSurfSrc"))

# --- load compiled bundle + create compiled node ---
if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
    cmds.loadPlugin(BUNDLE)
comp = cmds.createNode("waveSurf")
print("COMP_NODE", comp)


def read_cvs(node):
    sel = om.MSelectionList()
    sel.add(node)
    obj      = sel.getDependNode(0)
    fn       = om.MFnDependencyNode(obj)
    plug     = fn.findPlug("outSurface", True)
    surf_obj = plug.asMObject()  # forces eval
    sfn      = om.MFnNurbsSurface(surf_obj)
    pts      = sfn.cvPositions(om.MSpace.kObject)
    out      = []
    for i in range(len(pts)):
        out.append((pts[i].x, pts[i].y, pts[i].z))
    return out


phases = [0.0, 0.25, 0.5, 1.0, 1.5708, 2.0, 3.14159, 5.5]
maxerr = 0.0
ncomp  = 0
nsamp  = 0
fail   = False

for ph in phases:
    cmds.setAttr("waveSurfSrc.phase", ph)
    cmds.setAttr(comp + ".phase", ph)
    try:
        ref = read_cvs("waveSurfSrc")
        got = read_cvs(comp)
    except Exception as e:
        print("READ_ERROR", ph, repr(e))
        fail = True
        break
    if len(ref) == 0 or len(got) == 0:
        print("EMPTY_CVS", ph, "ref=", len(ref), "got=", len(got))
        fail = True
        break
    if len(ref) != len(got):
        print("CVCOUNT_MISMATCH", ph, "ref=", len(ref), "got=", len(got))
        fail = True
        break
    nsamp += 1
    for (rx, ry, rz), (gx, gy, gz) in zip(ref, got):
        for a, b in ((rx, gx), (ry, gy), (rz, gz)):
            e = abs(float(a) - float(b))
            if e > maxerr:
                maxerr = e
            ncomp += 1

print("RESULT samples=%d components=%d maxerr=%.6e tol=%.6e" % (nsamp, ncomp, maxerr, TOL))
ok = (not fail) and ncomp > 0 and maxerr <= TOL
print("PARITY", "PASS" if ok else "FAIL")
