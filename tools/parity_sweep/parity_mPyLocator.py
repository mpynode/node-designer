import os, sys, json, math, subprocess

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.environ.get("MPYNODE_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("MAYA_PLUG_IN_PATH", os.path.join(ROOT, "plug-ins"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import maya.standalone; maya.standalone.initialize()
import maya.cmds as cmds
import maya.api.OpenMaya as om
for p in ("mpynode_api1", "mpynode_api2"):
    if not cmds.pluginInfo(p, q=True, loaded=True):
        cmds.loadPlugin(p, quiet=True)

NB     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyLocator")
SCENE  = os.path.join(NB, "mPyLocator_spinGizmo_original.ma")
PROBE  = os.path.join(NB, "spinGizmo_probe")
FRAMES = [0, 6, 12, 18, 24, 30, 36, 42]
TOL    = 1e-4
MAYA   = "/Applications/Autodesk/maya2026"


def fail(reason):
    print("PARITY_RESULT " + json.dumps({
        "pass": False, "reason": reason, "maxerr": None,
        "num_samples": 0, "components_compared": 0,
    }))
    sys.exit(0)


# ---- 1) run the existing probe (rebuild ONLY via fixed clang if it won't run) --
def run_probe():
    env                        = dict(os.environ)
    env["DYLD_LIBRARY_PATH"]   = os.path.join(MAYA, "Maya.app/Contents/MacOS")
    env["DYLD_FRAMEWORK_PATH"] = os.path.join(MAYA, "Maya.app/Contents/Frameworks")
    cp = subprocess.run([PROBE] + [str(f) for f in FRAMES],
                        env=env, capture_output=True, text=True)
    if cp.returncode != 0:
        return None, cp.stderr
    return cp.stdout, None


out, err = run_probe()
if out is None:
    # fixed clang of the existing .cpp -- NOT an LLM rebuild
    bp = os.path.join(NB, "build_probe.sh")
    r  = subprocess.run(["bash", bp], capture_output=True, text=True)
    if r.returncode != 0:
        fail("probe won't run and build_probe.sh failed: " + (r.stderr or "")[:500])
    out, err = run_probe()
    if out is None:
        fail("probe still won't run after rebuild: " + (err or "")[:500])

try:
    probe = json.loads(out)
except Exception as e:
    fail("probe JSON parse failed: %r ; raw=%r" % (e, out[:300]))

probe_by_t = {round(float(d["time"]), 6): d for d in probe}

# ---- 2) build the REAL python reference node from the original scene ----------
cmds.file(SCENE, open=True, force=True, ignoreVersion=True)
locs = cmds.ls(type="mPyLocator") or []
if not locs:
    fail("no mPyLocator found in original scene")
loc_name = None
for l in locs:
    if l == "spinGizmo" or l.endswith("|spinGizmo") or "spinGizmo" in l:
        loc_name = l
        break
if loc_name is None:
    loc_name = locs[0]
if not cmds.objExists(loc_name):
    fail("python ref node does not exist: %r" % loc_name)

sel = om.MSelectionList(); sel.add(loc_name)
node_obj = sel.getDependNode(0)
fn       = om.MFnDependencyNode(node_obj)
mpx      = fn.userNode()
if mpx is None:
    fail("could not get MPx user node for %r (python ref unavailable)" % loc_name)


def to_list(v):
    """Normalize any numeric buffer (numpy/list/scalar) to a flat list of floats."""
    if v is None:
        return None
    try:
        import numpy as np
        if isinstance(v, np.ndarray):
            return [float(x) for x in v.ravel().tolist()]
    except Exception:
        pass
    if isinstance(v, (list, tuple)):
        flat = []
        for x in v:
            sub = to_list(x)
            if sub is None:
                continue
            flat.extend(sub)
        return flat
    try:
        return [float(v)]
    except Exception:
        return None


# Map probe JSON field -> (python buffer slot, key within that slot)
# Numeric fields only (strings/text compared separately, exactly).
NUMERIC_MAP = [
    ("lineStart",   "lines",  "starts"),
    ("lineEnd",     "lines",  "ends"),
    ("lineColor",   "lines",  "colors"),
    ("pointPos",    "points", "positions"),
    ("pointColor",  "points", "colors"),
    ("pointSize",   "points", "sizes"),
    ("textPos",     "text",   "positions"),
    ("textColor",   "text",   "colors"),
    ("textSize",    "text",   "sizes"),
    ("shapeCenter", "shapes", "centers"),
    ("shapeRadius", "shapes", "radii"),
    ("shapeAxis",   "shapes", "axes"),
    ("shapeColor",  "shapes", "colors"),
    ("shapeFilled", "shapes", "filled"),
]
SHAPE_KIND_MAP = {"sphere": 0, "circle": 1}

maxerr         = 0.0
ncomp          = 0
nsamp          = 0
mismatch_str   = []

for f in FRAMES:
    key = round(float(f), 6)
    pj  = probe_by_t.get(key)
    if pj is None:
        fail("probe missing frame %s" % f)
    bufs = mpx.evaluateDrawItems(float(f))
    nsamp += 1

    # numeric fields
    for jfield, slot, subkey in NUMERIC_MAP:
        pvals  = [float(x) for x in to_list(pj[jfield]) or []]
        slot_d = bufs.get(slot)
        yvals  = []
        if slot_d is not None and slot_d.get(subkey) is not None:
            yvals = to_list(slot_d.get(subkey)) or []
        # compare element-wise (must match length)
        if len(pvals) != len(yvals):
            fail("length mismatch frame=%s field=%s probe=%d py=%d (probe=%r py=%r)"
                 % (f, jfield, len(pvals), len(yvals), pvals, yvals))
        for a, b in zip(pvals, yvals):
            e = abs(a - b)
            if e > maxerr:
                maxerr = e
            ncomp += 1

    # shapeKind: probe int code vs python kind string -> code
    pkind  = [int(round(x)) for x in (to_list(pj["shapeKind"]) or [])]
    shapes = bufs.get("shapes")
    ykinds = []
    if shapes is not None and shapes.get("kinds") is not None:
        ykinds = [SHAPE_KIND_MAP.get(str(k), -99) for k in shapes["kinds"]]
    if len(pkind) != len(ykinds):
        fail("shapeKind length mismatch frame=%s probe=%d py=%d" % (f, len(pkind), len(ykinds)))
    for a, b in zip(pkind, ykinds):
        e = abs(float(a) - float(b))
        if e > maxerr:
            maxerr = e
        ncomp += 1

    # text strings: exact match (non-numeric, but a real output component)
    ptext = [str(s) for s in (pj.get("textStr") or [])]
    txt   = bufs.get("text")
    ytext = []
    if txt is not None and txt.get("strings") is not None:
        ytext = [str(s) for s in txt["strings"]]
    if ptext != ytext:
        mismatch_str.append("frame=%s textStr probe=%r py=%r" % (f, ptext, ytext))
    else:
        ncomp += len(ptext)  # count matched string components

if mismatch_str:
    print("PARITY_RESULT " + json.dumps({
        "pass": False, "reason": "text string mismatch: " + "; ".join(mismatch_str),
        "maxerr": maxerr, "num_samples": nsamp, "components_compared": ncomp,
    }))
    sys.exit(0)

passed = (ncomp > 0) and (maxerr <= TOL)
print("PARITY_RESULT " + json.dumps({
    "pass": bool(passed),
    "reason": "ok" if passed else ("maxerr %g > tol %g" % (maxerr, TOL)),
    "maxerr": maxerr,
    "num_samples": nsamp,
    "components_compared": ncomp,
    "loc_name": loc_name,
}))
