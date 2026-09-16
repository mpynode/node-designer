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

HERE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyConstraint")
ORIG_MA   = os.path.join(HERE, "mPyConstraint_pointBlend_original.ma")
BUNDLE    = os.path.join(HERE, "pointBlendConstraint.bundle")
NODE_TYPE = "pointBlendConstraint"
TOL       = 1e-4

INPUTS = {"blend": "float", "offset": "vector", "targetA": "vector", "targetB": "vector"}
OUT    = "outPos"


def _sample(t):
    if t == "vector":
        return [random.uniform(-5, 5) for _ in range(3)]
    return random.uniform(0.0, 1.0)  # blend constrained 0..1


def _set(node, attr, t, v):
    if t == "vector":
        cmds.setAttr(node + "." + attr, v[0], v[1], v[2], type="double3")
    else:
        cmds.setAttr(node + "." + attr, v)


def _read_vec(node, attr):
    val = cmds.getAttr(node + "." + attr)  # forces eval
    # getAttr on double3 returns [(x,y,z)]
    if isinstance(val, (list, tuple)):
        flat = val
        while isinstance(flat, (list, tuple)) and len(flat) == 1 and isinstance(flat[0], (list, tuple)):
            flat = flat[0]
        return [float(c) for c in flat]
    return [float(val)]


def main():
    # 1) Load the original python mPyConstraint node from the .ma
    cmds.file(ORIG_MA, open=True, force=True)
    PYREF = "pointBlendConstraint"
    if not cmds.objExists(PYREF):
        print("RESULT no_python_ref node_missing")
        return
    py_type = cmds.nodeType(PYREF)
    print("PYREF", PYREF, "type", py_type)
    py_built = (py_type == "mPyConstraint")

    # 2) Load the compiled bundle and create the native node
    plug = os.path.basename(BUNDLE)
    if not cmds.pluginInfo(plug, q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    comp      = cmds.createNode(NODE_TYPE)
    comp_type = cmds.nodeType(comp)
    print("COMP", comp, "type", comp_type)
    comp_built = cmds.objExists(comp)

    if not (py_built and comp_built):
        print("RESULT setup_fail py_built", py_built, "comp_built", comp_built)
        return

    random.seed(42)
    n_samples      = 25
    comps_compared = 0
    maxerr         = 0.0
    fails          = 0
    for s in range(n_samples):
        for a, t in INPUTS.items():
            v = _sample(t)
            _set(comp, a, t, v)
            _set(PYREF, a, t, v)
        cv = _read_vec(comp, OUT)
        sv = _read_vec(PYREF, OUT)
        if len(cv) != len(sv):
            print("LEN_MISMATCH", cv, sv)
            fails += 1
            continue
        for c, p in zip(cv, sv):
            e = abs(c - p)
            comps_compared += 1
            if e > maxerr:
                maxerr = e
            if e > TOL:
                fails += 1
                print("MISMATCH sample", s, c, "!=", p, "err", e)

    status = "PASS" if (fails == 0 and comps_compared > 0) else "FAIL"
    print("RESULT", status, "samples", n_samples, "components", comps_compared,
          "maxerr", repr(maxerr), "fails", fails)


if __name__ == "__main__":
    main()
