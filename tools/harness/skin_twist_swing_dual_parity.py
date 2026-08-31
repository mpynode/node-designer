"""Stage-2 in-scene parity for the two-weight-set TWIST/SWING skinCluster.

The compiled ``twistSwingSkin`` carries the two painted weight sets as declared
``double is_array`` INPUT plugs (``twistWeights`` / ``swingWeights``, flattened
N*J) plus a ``skinMode`` enum and a ``twistAxis`` enum, and branches on them in
the pure-C++ ``deform()``. This harness proves the compiled node -- built by the
REAL codegen (attr declarations + plug materialisation + MPxSkinCluster
registration), not the hand-written C++-level fixture -- reproduces the
INTERPRETED node on a real bound arm skin:

  * PRIMARY: skinMode=2 (Live Result) reads the two per-node weight plugs and
    matches ``skin_blend.twist_swing_dual`` across twist+bend poses and all three
    twist axes. This is the byte-parity performance path.
  * paint previews: skinMode 0/1 read the live ``weightList``; asserted on an
    UNPAINTED node (weightList pre-set to the active set, so the interpreted
    node's sync_paint load is a no-op and the compiled no-op agrees).

The generic deformer verify (native/toolchain/verify.py) SKIPS skinClusters, so
this does the real thing: identical arm weights + identical weight-set plugs on
both nodes, compared at multiple poses.

Run under mayapy (same env as compile_one.py)::

    mayapy skin_twist_swing_dual_parity.py [out_dir] [compiled_type]
"""
import os
import sys
import glob

HARNESS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HARNESS))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as mc
import numpy as np

for _p in ("mpynode_api1", "mpynode_api2"):
    if not mc.pluginInfo(_p, q=True, loaded=True):
        mc.loadPlugin(_p, quiet=True)

OUT = (sys.argv[1] if len(sys.argv) > 1
       else os.path.join(ROOT, "templates", "MPySkinCluster",
                         "Twist Swing Skin"))
COMPILED_TYPE = sys.argv[2] if len(sys.argv) > 2 else "twistSwingSkin"

import mpynode
from mpynode._base.plugins import load_or_reload_native_plugin
from mpynode._common.methods import skin_blend
from mpynode._demos.twist_swing_skin_source import COMPUTE, INIT, METHODS
from tests.nodes.test_skin_cluster_lbs_arm_parity import (
    _arm_path, _extract_stock_skin, _mesh_pts)

for _b in glob.glob(os.path.join(OUT, "*.bundle")):
    load_or_reload_native_plugin(_b)
print("loaded compiled bundle(s) from", OUT)


def _seed_plug(node, plug, W):
    flat = np.asarray(W, dtype=np.float64).ravel()
    for i in range(flat.size):
        mc.setAttr("%s.%s[%d]" % (node, plug, i), float(flat[i]))


def build_and_capture(sc_type, interpreted, skin_mode, twist_axis,
                      twist_w, swing_w, weight_list, poses):
    """Bind ``sc_type`` to the arm with the given weights + weight-set plugs, set
    the mode/axis, drive the elbow through ``poses`` (rx, ry), return points/pose.

    Both node types get the SAME weightList + twistWeights + swingWeights. The
    interpreted node additionally gets the four declared attrs + the shipped
    Compute (a compiled node already has them baked in by codegen)."""
    mc.file(new=True, force=True)
    new = mc.file(_arm_path(), i=True, ignoreVersion=True,
                  returnNewNodes=True) or []
    sc = (mc.ls(new, type="skinCluster") or [None])[0]
    joints = mc.ls(new, type="joint", long=True) or []
    meshes = [m for m in (mc.ls(new, type="mesh", long=True) or [])
              if not mc.getAttr(m + ".intermediateObject")]
    mesh_shape = meshes[0]
    mesh_xform = mc.listRelatives(mesh_shape, parent=True, fullPath=True)[0]
    elbow = (next((j for j in joints
                   if j.rsplit("|", 1)[-1] == "loarm_r_JNT"), None)
             or next((j for j in joints if "loarm" in j), None))

    infl, _W, bind = _extract_stock_skin(sc, mesh_shape)
    nv = weight_list.shape[0]

    for ax in ("rotateX", "rotateY", "rotateZ"):
        for s in (mc.listConnections(elbow + "." + ax, s=True, d=False,
                                     plugs=True) or []):
            mc.disconnectAttr(s, elbow + "." + ax)
        mc.setAttr(elbow + "." + ax, lock=False)

    mc.skinCluster(sc, e=True, unbind=True)   # mesh -> exact rest

    node = mc.deformer(mesh_xform, type=sc_type)[0]
    for i, jnt in enumerate(infl):
        mc.connectAttr(jnt + ".worldMatrix[0]", "%s.matrix[%d]" % (node, i),
                       force=True)
        if i in bind:
            mc.setAttr("%s.bindPreMatrix[%d]" % (node, i), bind[i],
                       type="matrix")
    ninf = len(infl)
    for v in range(nv):
        for c in range(ninf):
            mc.setAttr("%s.weightList[%d].weights[%d]" % (node, v, c),
                       float(weight_list[v][c]))

    if interpreted:
        w = mpynode.wrap(node)
        w.add_input_attr("twistWeights", "double", is_array=True)
        w.add_input_attr("swingWeights", "double", is_array=True)
        w.add_input_attr("skinMode", "enum",
                         enum_names=["Paint LBS (Swing)", "Paint DQS (Twist)",
                                     "Live Result"], default_value=2)
        w.add_input_attr("twistAxis", "enum",
                         enum_names=["X", "Y", "Z"], default_value=0)
        w.set_init_expression(INIT)
        w.set_compute_expression(COMPUTE)
        w.set_methods_source(METHODS)

    _seed_plug(node, "twistWeights", twist_w)
    _seed_plug(node, "swingWeights", swing_w)
    mc.setAttr("%s.skinMode" % node, int(skin_mode))
    mc.setAttr("%s.twistAxis" % node, int(twist_axis))

    caps = []
    for rx, ry in poses:
        mc.setAttr(elbow + ".rotate", 0, 0, 0)
        mc.setAttr(elbow + ".rotateX", float(rx))    # twist about the bone
        mc.setAttr(elbow + ".rotateY", float(ry))    # bend (arm hinges on Y)
        mc.dgeval(mesh_shape + ".outMesh")
        caps.append(_mesh_pts(mesh_shape))
    return caps


def _weights_for_arm():
    """Two DISTINCT dense weight sets sized to the arm skin (twist = stock,
    swing = a renormalised roll of it), plus the stock weightList."""
    mc.file(new=True, force=True)
    new = mc.file(_arm_path(), i=True, ignoreVersion=True,
                  returnNewNodes=True) or []
    sc = (mc.ls(new, type="skinCluster") or [None])[0]
    mesh_shape = [m for m in (mc.ls(new, type="mesh", long=True) or [])
                  if not mc.getAttr(m + ".intermediateObject")][0]
    _infl, W, _bind = _extract_stock_skin(sc, mesh_shape)
    twist_w = np.asarray(W, dtype=np.float64)
    swing_w = np.roll(twist_w, 1, axis=1)
    swing_w = swing_w / np.clip(swing_w.sum(axis=1, keepdims=True), 1e-9, None)
    return twist_w, swing_w


def main():
    tol = 1e-4
    twist_w, swing_w = _weights_for_arm()
    poses = [(0.0, 0.0), (60.0, 0.0), (60.0, 45.0)]   # rest, twist, twist+bend
    all_ok = True

    # PRIMARY gate: Live Result (mode 2), all three twist axes.
    for axis in (0, 1, 2):
        interp = build_and_capture("mPySkinCluster", True, 2, axis,
                                   twist_w, swing_w, twist_w, poses)
        comp = build_and_capture(COMPILED_TYPE, False, 2, axis,
                                 twist_w, swing_w, twist_w, poses)
        moved = float(np.abs(interp[-1] - interp[0]).max())
        diffs = [float(np.abs(a - b).max()) for a, b in zip(interp, comp)]
        ok = moved > 1.0 and all(d <= tol for d in diffs)
        all_ok = all_ok and ok
        print("Live (mode 2) axis %d: deform=%.4f  maxdiff=%s  -> %s"
              % (axis, moved, " ".join("%.2e" % d for d in diffs),
                 "PASS" if ok else "FAIL"))

    # paint previews (mode 0/1) on an UNPAINTED node: weightList == the active set,
    # so the interpreted sync_paint load is a no-op and matches the compiled no-op.
    for mode, active, label in ((0, swing_w, "Paint LBS"),
                                (1, twist_w, "Paint DQS")):
        interp = build_and_capture("mPySkinCluster", True, mode, 0,
                                   twist_w, swing_w, active, poses)
        comp = build_and_capture(COMPILED_TYPE, False, mode, 0,
                                 twist_w, swing_w, active, poses)
        moved = float(np.abs(interp[-1] - interp[0]).max())
        diffs = [float(np.abs(a - b).max()) for a, b in zip(interp, comp)]
        ok = moved > 1.0 and all(d <= tol for d in diffs)
        all_ok = all_ok and ok
        print("%s (mode %d): deform=%.4f  maxdiff=%s  -> %s"
              % (label, mode, moved, " ".join("%.2e" % d for d in diffs),
                 "PASS" if ok else "FAIL"))

    print("PARITY (dual twist/swing): %s (tol=%.0e)"
          % ("PASS" if all_ok else "FAIL", tol))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
