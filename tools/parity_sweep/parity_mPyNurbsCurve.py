import os, sys, math
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

BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyNurbsCurve")
ORIG_MA   = os.path.join(BUILD_DIR, "mPyNurbsCurve_sineCurve_original.ma")
BUNDLE    = os.path.join(BUILD_DIR, "sineCurve.bundle")
NODE_TYPE = "sineCurve"
SOURCE    = "sineCurveSrc"
TOL       = 1e-4

PHASES = [0.0, 0.5, 1.0, 1.5, 2.0, 3.14159265, 4.5, 6.0]


def fail(reason):
    print("RESULT|FAIL|maxerr=None|samples=0|components=0|reason=%s" % reason)
    sys.exit(0)


# --- open original scene (brings in python sineCurveSrc node) ---
try:
    cmds.file(ORIG_MA, open=True, force=True)
except Exception as e:
    fail("could not open original .ma: %s" % e)

if not cmds.objExists(SOURCE):
    fail("python reference node %s not found after open" % SOURCE)
python_ref_built = True

# --- load the existing compiled bundle ---
try:
    if not cmds.pluginInfo(os.path.basename(BUNDLE), q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
except Exception as e:
    fail("could not load bundle: %s" % e)
builds_loads = True

# --- create the compiled native node ---
try:
    comp = cmds.createNode(NODE_TYPE)
except Exception as e:
    fail("could not createNode %s: %s" % (NODE_TYPE, e))

if not cmds.objExists(comp):
    fail("compiled node %s does not exist after createNode" % comp)


def cv_positions(node):
    """Force-eval outCurve, return list of (x,y,z) in object space via API."""
    sel = om.MSelectionList()
    sel.add(node)
    dep  = om.MFnDependencyNode(sel.getDependNode(0))
    plug = dep.findPlug("outCurve", False)
    mobj = plug.asMObject()  # forces evaluation of the nurbsCurve data
    fn   = om.MFnNurbsCurve(mobj)
    pts  = fn.cvPositions(om.MSpace.kObject)
    return [(p.x, p.y, p.z) for p in pts]


maxerr          = 0.0
components      = 0
num_samples     = 0
mismatch_detail = ""

for phase in PHASES:
    cmds.setAttr(comp + ".phase", phase)
    cmds.setAttr(SOURCE + ".phase", phase)
    try:
        comp_cvs = cv_positions(comp)
        src_cvs  = cv_positions(SOURCE)
    except Exception as e:
        fail("error reading curve at phase=%s: %s" % (phase, e))

    if len(comp_cvs) != len(src_cvs):
        fail("CV count mismatch at phase=%s: comp=%d src=%d"
             % (phase, len(comp_cvs), len(src_cvs)))
    if len(comp_cvs) == 0:
        fail("zero CVs at phase=%s" % phase)

    num_samples += 1
    for ci, (cpt, spt) in enumerate(zip(comp_cvs, src_cvs)):
        for axis in range(3):
            err = abs(cpt[axis] - spt[axis])
            components += 1
            if err > maxerr:
                maxerr = err
                mismatch_detail = ("phase=%s cv=%d axis=%d comp=%.10f src=%.10f"
                                   % (phase, ci, axis, cpt[axis], spt[axis]))

parity_pass = (components > 0 and maxerr <= TOL)
print("RESULT|%s|maxerr=%.12g|samples=%d|components=%d|worst=%s|python_ref=%s|builds=%s"
      % ("PASS" if parity_pass else "FAIL", maxerr, num_samples, components,
         mismatch_detail, python_ref_built, builds_loads))
