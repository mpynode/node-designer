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

BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "mPyIkSolver")
ORIG_SCENE = os.path.join(BUILD, "mPyIkSolver_twoBone_original.ma")
PLUGIN_SCENE = os.path.join(BUILD, "mPyIkSolver_twoBoneSolver_plugin.ma")
BUNDLE = os.path.join(BUILD, "twoBoneSolver.bundle")

# 8 goal positions (handle translate). Spread so the leg must bend to varying degrees.
GOALS = [
    (3.0, 0.0, 2.0),
    (2.0, 3.0, 1.0),
    (-2.0, 4.0, 3.0),
    (4.0, -1.0, -2.0),
    (0.0, 6.0, 0.0),
    (-3.0, 2.0, -4.0),
    (5.0, 0.0, 5.0),
    (1.0, -3.0, 4.0),
]

JOINT_NAMES = ["hip", "knee", "ankle"]


def _solve_and_read(scene_path):
    """Open scene, drive handle through 8 goals, return list of dicts {jointname: (x,y,z) world}."""
    cmds.file(scene_path, open=True, force=True)
    # discover
    handles = cmds.ls(type="ikHandle")
    joints = cmds.ls(type="joint")
    print("DISCOVER scene=%s handles=%s joints=%s" % (os.path.basename(scene_path), handles, joints))
    if not handles:
        raise RuntimeError("no ikHandle found in %s" % scene_path)
    handle = handles[0]
    records = []
    for g in GOALS:
        cmds.setAttr(handle + ".t", g[0], g[1], g[2], type="double3")
        # force a solve: dgdirty + refresh, then read joint world positions (xform forces eval)
        cmds.dgdirty(handle)
        try:
            cmds.refresh(force=True)
        except Exception:
            pass
        rec = {}
        for j in JOINT_NAMES:
            if not cmds.objExists(j):
                raise RuntimeError("joint %s missing in %s" % (j, scene_path))
            pos = cmds.xform(j, q=True, ws=True, t=True)
            rec[j] = tuple(pos)
        records.append(rec)
    return records


def main():
    # (1) Python solver scene
    orig_records = _solve_and_read(ORIG_SCENE)
    print("ORIG records collected:", len(orig_records))

    # (2) new scene, load compiled bundle, open plugin scene
    cmds.file(new=True, force=True)
    bundle_base = os.path.basename(BUNDLE)
    if not cmds.pluginInfo(bundle_base, q=True, loaded=True):
        cmds.loadPlugin(BUNDLE)
    print("Loaded bundle? ", cmds.pluginInfo(bundle_base, q=True, loaded=True))
    print("twoBoneSolver registered nodeTypes:", "twoBoneSolver" in (cmds.pluginInfo(bundle_base, q=True, dependNode=True) or []))

    plugin_records = _solve_and_read(PLUGIN_SCENE)
    print("PLUGIN records collected:", len(plugin_records))

    # (3) compare element-wise
    maxerr = 0.0
    n_components = 0
    n_samples = 0
    worst = None
    for i, (o, p) in enumerate(zip(orig_records, plugin_records)):
        n_samples += 1
        for j in JOINT_NAMES:
            ov = o[j]
            pv = p[j]
            for k in range(3):
                d = abs(float(ov[k]) - float(pv[k]))
                n_components += 1
                if d > maxerr:
                    maxerr = d
                    worst = (i, j, k, ov[k], pv[k])

    print("RESULT samples=%d components=%d maxerr=%.6e worst=%s" % (n_samples, n_components, maxerr, worst))
    # also dump a couple sample positions for audit
    for i in (0, 4, 7):
        print("SAMPLE goal=%s orig.ankle=%s plugin.ankle=%s" % (GOALS[i], orig_records[i]["ankle"], plugin_records[i]["ankle"]))
    TOL = 1e-4
    print("PARITY", "PASS" if (n_components > 0 and maxerr <= TOL) else "FAIL")


if __name__ == "__main__":
    main()
