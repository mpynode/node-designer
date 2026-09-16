import os, sys, random

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

PROC_BUNDLE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyFile", "proceduralTex.bundle")
PROC_ORIG_MA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyFile", "mPyFile_proceduralTex_original.ma")
FULL_BUNDLE  = os.path.join(ROOT, "plug-ins", "fullFileNode.bundle")
PNG          = os.path.join(ROOT, "scripts", "mpynode", "_demos", "data", "test_grid.png")

# accumulators
results = {}


# ---------------------------------------------------------------------------
# CHECK 1 -- procedural basic-type artifact parity
# ---------------------------------------------------------------------------
def check_procedural():
    # open the original scene (python mPyFile 'proceduralTex')
    cmds.file(PROC_ORIG_MA, open=True, force=True)
    # ensure the python wrapper node exists
    assert cmds.objExists("proceduralTex"), "python proceduralTex node missing after open"
    py_node = "proceduralTex"

    # load the native bundle and create compiled node
    bn = os.path.basename(PROC_BUNDLE)
    if not cmds.pluginInfo(bn, q=True, loaded=True):
        cmds.loadPlugin(PROC_BUNDLE)
    nat = cmds.createNode("proceduralTex")
    assert cmds.objExists(nat), "native proceduralTex node not created"
    assert nat != py_node, "name collision (%s)" % nat

    inputs     = {"uIn": "float", "vIn": "float", "kScale": "float"}
    out_scalar = ["outVal"]
    out_vec    = ["outRGB"]

    random.seed(1234)
    maxerr = 0.0
    comps  = 0
    nsamp  = 25
    for _ in range(nsamp):
        for a in inputs:
            v = random.uniform(-5, 5)
            cmds.setAttr(py_node + "." + a, v)
            cmds.setAttr(nat + "." + a, v)
        # scalar outputs
        for o in out_scalar:
            pv     = cmds.getAttr(py_node + "." + o)
            cv     = cmds.getAttr(nat + "." + o)
            pv     = pv[0] if isinstance(pv, (list, tuple)) else pv
            cv     = cv[0] if isinstance(cv, (list, tuple)) else cv
            e      = abs(float(pv) - float(cv))
            maxerr = max(maxerr, e)
            comps += 1
        # vector outputs (3 comps)
        for o in out_vec:
            pv = cmds.getAttr(py_node + "." + o)  # [(x,y,z)]
            cv = cmds.getAttr(nat + "." + o)
            pv = pv[0] if isinstance(pv[0], (list, tuple)) else pv
            cv = cv[0] if isinstance(cv[0], (list, tuple)) else cv
            for i in range(3):
                e      = abs(float(pv[i]) - float(cv[i]))
                maxerr = max(maxerr, e)
                comps += 1
    return {"maxerr": maxerr, "comps": comps, "samples": nsamp, "tol": 1e-4}


# ---------------------------------------------------------------------------
# CHECK 2 -- full file-read parity (native fullFileNode vs python MPyFile)
# ---------------------------------------------------------------------------
def check_fullfile():
    cmds.file(new=True, force=True)
    # reload api plugins after file-new
    for p in ("mpynode_api1", "mpynode_api2"):
        if not cmds.pluginInfo(p, q=True, loaded=True):
            cmds.loadPlugin(p, quiet=True)

    # native node
    bn = os.path.basename(FULL_BUNDLE)
    if not cmds.pluginInfo(bn, q=True, loaded=True):
        cmds.loadPlugin(FULL_BUNDLE)
    nat = cmds.createNode("fullFileNode")
    assert cmds.objExists(nat), "native fullFileNode not created"
    cmds.setAttr(nat + ".fileName", PNG, type="string")

    # python reference
    from mpynode.wrappers.mpy_file import MPyFile
    pyf     = MPyFile.create(name="pyf#", seed_defaults=True, as_texture=True)
    py_node = pyf.get_name()
    assert cmds.objExists(py_node), "python MPyFile node not created"
    cmds.setAttr(py_node + ".fileName", PNG, type="string")

    assert nat != py_node

    random.seed(987)
    maxerr     = 0.0
    comps      = 0
    ncases     = 20
    mismatches = []
    for _ in range(ncases):
        cs = random.randint(0, 24)
        u  = random.uniform(-0.2, 1.2)
        v  = random.uniform(-0.2, 1.2)
        wu = random.randint(0, 3)
        wv = random.randint(0, 3)

        for n in (nat, py_node):
            cmds.setAttr(n + ".colorSpace", cs)
            cmds.setAttr(n + ".uvCoord", u, v, type="double2")
            cmds.setAttr(n + ".wrapModeU", wu)
            cmds.setAttr(n + ".wrapModeV", wv)

        pc = cmds.getAttr(py_node + ".outColor")
        nc = cmds.getAttr(nat + ".outColor")
        pc = pc[0] if isinstance(pc[0], (list, tuple)) else pc
        nc = nc[0] if isinstance(nc[0], (list, tuple)) else nc
        pa = cmds.getAttr(py_node + ".outAlpha")
        na = cmds.getAttr(nat + ".outAlpha")
        pa = pa[0] if isinstance(pa, (list, tuple)) else pa
        na = na[0] if isinstance(na, (list, tuple)) else na

        case_err = 0.0
        for i in range(3):
            e        = abs(float(pc[i]) - float(nc[i]))
            maxerr   = max(maxerr, e)
            case_err = max(case_err, e)
            comps += 1
        e        = abs(float(pa) - float(na))
        maxerr   = max(maxerr, e)
        case_err = max(case_err, e)
        comps += 1

        if case_err > 1e-3:
            mismatches.append((cs, round(u, 3), round(v, 3), wu, wv,
                               [round(float(x), 5) for x in pc], round(float(pa), 5),
                               [round(float(x), 5) for x in nc], round(float(na), 5),
                               round(case_err, 6)))

    return {"maxerr": maxerr, "comps": comps, "samples": ncases, "tol": 1e-3,
            "mismatches": mismatches}


r1 = check_procedural()
print("CHECK1 procedural maxerr=%.3e comps=%d samples=%d tol=%.1e" % (
    r1["maxerr"], r1["comps"], r1["samples"], r1["tol"]))
r2 = check_fullfile()
print("CHECK2 fullfile maxerr=%.3e comps=%d samples=%d tol=%.1e" % (
    r2["maxerr"], r2["comps"], r2["samples"], r2["tol"]))
for m in r2["mismatches"][:8]:
    print("  MISMATCH cs=%d uv=(%s,%s) wrap=(%d,%d) py=%s/%s nat=%s/%s err=%s" % m)

overall_max   = max(r1["maxerr"], r2["maxerr"])
total_comps   = r1["comps"] + r2["comps"]
total_samples = r1["samples"] + r2["samples"]
pass1         = r1["maxerr"] <= r1["tol"]
pass2         = r2["maxerr"] <= r2["tol"]
overall       = pass1 and pass2
print("RESULT pass1=%s pass2=%s overall=%s overall_maxerr=%.3e total_comps=%d total_samples=%d" % (
    pass1, pass2, overall, overall_max, total_comps, total_samples))
