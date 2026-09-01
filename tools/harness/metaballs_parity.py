"""End-to-end parity: the DETERMINISTICALLY-compiled metaballs node vs the pure
-Python reference (sdf_dmc.mesh_from_shapes) on identical inputs.

The generic geo-verify sweep can't coherently seed metaballs' parallel SDF
shape-stream arrays (shapeMatrix/shapeType/radius/...), so this dedicated check
drives the compiled node directly with a few fully-specified scenes and compares
the produced mesh (every point component within tol + EXACT face topology) to
``mesh_from_shapes`` computed in-process. Because the interpreted node ==
``mesh_from_shapes`` is already proven byte-for-byte (tests/compile/native/
metaballs_glue_parity.py), compiled == reference closes the loop compiled ==
interpreted.

Usage (under mayapy, with the plug-ins + scripts on the path):
    mayapy metaballs_parity.py <bundle_path>

Prints 'PARITY_JSON:{...}' as the last line; exit 0 iff every scene matches.
"""
import json
import os
import sys

import numpy as np

BUNDLE = sys.argv[1]

_PT_ATOL = 1e-4          # compiled float path vs numpy; topology must be EXACT

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as mc
import maya.api.OpenMaya as om2

from mpynode._common.nodes.mesh import sdf_dmc

result = {"ok": False, "bundle": BUNDLE, "scenes": [], "errors": []}


def _mat(tx=0.0, ty=0.0, tz=0.0, sx=1.0, sy=1.0, sz=1.0):
    m = np.eye(4, dtype=np.float64)
    m[0, 0] = sx; m[1, 1] = sy; m[2, 2] = sz
    m[3, :3] = (tx, ty, tz)
    return m


def _scenes():
    d64 = np.float64
    S = []
    # single sphere
    S.append(("sphere", dict(
        mats=np.stack([_mat()]),
        stype=np.array([0], np.int64), add=np.array([1], np.int64),
        smooth=np.array([0.0], d64), rad=np.array([1.0], d64),
        hgt=np.array([1.0], d64), ax=np.array([1], np.int64),
        half=np.array([[0.5, 0.5, 0.5]], d64), res=8, iso=0.0)))
    # two-sphere hard union
    S.append(("union", dict(
        mats=np.stack([_mat(-0.4, 0, 0), _mat(0.4, 0, 0)]),
        stype=np.array([0, 0], np.int64), add=np.array([1, 1], np.int64),
        smooth=np.array([0.0, 0.0], d64), rad=np.array([1.0, 1.0], d64),
        hgt=np.array([1.0, 1.0], d64), ax=np.array([1, 1], np.int64),
        half=np.array([[0.5, 0.5, 0.5]] * 2, d64), res=8, iso=0.0)))
    # cube + smooth sphere - cylinder (all three CSG ops, axis 0 cylinder)
    S.append(("csg_all", dict(
        mats=np.stack([_mat(0, 0, 0), _mat(0.6, 0.3, 0), _mat(0, 0, 0)]),
        stype=np.array([1, 0, 2], np.int64), add=np.array([1, 1, 0], np.int64),
        smooth=np.array([0.0, 0.4, 0.0], d64), rad=np.array([1.0, 0.7, 0.4], d64),
        hgt=np.array([1.0, 1.0, 2.4], d64), ax=np.array([1, 1, 0], np.int64),
        half=np.array([[0.8, 0.8, 0.8], [0.5, 0.5, 0.5], [0.5, 0.5, 0.5]], d64),
        res=9, iso=0.1)))
    return S


def _drive(node, s):
    mats = s["mats"]
    for i in range(mats.shape[0]):
        flat = [float(x) for x in mats[i].reshape(-1)]
        mc.setAttr("%s.shapeMatrix[%d]" % (node, i), *flat, type="matrix")
    for i, v in enumerate(s["stype"]):
        mc.setAttr("%s.shapeType[%d]" % (node, i), int(v))
    for i, v in enumerate(s["add"]):
        mc.setAttr("%s.additive[%d]" % (node, i), int(v))
    for i, v in enumerate(s["smooth"]):
        mc.setAttr("%s.smoothing[%d]" % (node, i), float(v))
    for i, v in enumerate(s["rad"]):
        mc.setAttr("%s.radius[%d]" % (node, i), float(v))
    for i, v in enumerate(s["hgt"]):
        mc.setAttr("%s.height[%d]" % (node, i), float(v))
    for i, v in enumerate(s["ax"]):
        mc.setAttr("%s.axis[%d]" % (node, i), int(v))
    for i, v in enumerate(s["half"]):
        mc.setAttr("%s.halfExtents[%d]" % (node, i),
                   float(v[0]), float(v[1]), float(v[2]), type="double3")
    mc.setAttr("%s.resolution" % node, int(s["res"]))
    mc.setAttr("%s.isoValue" % node, float(s["iso"]))


def _read_mesh(node):
    sel = om2.MSelectionList(); sel.add(node)
    mob = sel.getDependNode(0)
    plug = om2.MFnDependencyNode(mob).findPlug("outMesh", True)
    data = plug.asMObject()
    if data.isNull():
        return None, None, None
    mfn = om2.MFnMesh(data)
    if mfn.numVertices == 0:
        return np.zeros((0, 3)), np.zeros(0, np.int64), np.zeros(0, np.int64)
    pts = np.array([[p.x, p.y, p.z] for p in mfn.getPoints(om2.MSpace.kObject)])
    counts, connects = mfn.getVertices()
    return pts, np.asarray(counts, np.int64), np.asarray(connects, np.int64)


try:
    for p in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(p, q=True, loaded=True):
            mc.loadPlugin(p, quiet=True)
    mc.loadPlugin(BUNDLE, quiet=True)

    all_ok = True
    for name, s in _scenes():
        rec = {"scene": name, "ok": False}
        node = mc.createNode("metaballs")
        _drive(node, s)
        mc.dgeval(node + ".outMesh")
        cp, cc, ci = _read_mesh(node)

        rp, rc, ri = sdf_dmc.mesh_from_shapes(
            s["mats"], s["stype"], s["add"], s["smooth"], s["rad"], s["hgt"],
            s["ax"], s["half"], s["res"], s["iso"])
        rp = np.asarray(rp, np.float64)
        rc = np.asarray(rc, np.int64)
        ri = np.asarray(ri, np.int64)

        rec["compiled_verts"] = int(cp.shape[0]) if cp is not None else 0
        rec["ref_verts"] = int(rp.shape[0])
        rec["compiled_faces"] = int(cc.shape[0]) if cc is not None else 0
        rec["ref_faces"] = int(rc.shape[0])

        if cp is None:
            rec["reason"] = "compiled produced no geometry"
        elif cp.shape != rp.shape:
            rec["reason"] = "points shape %s != ref %s" % (cp.shape, rp.shape)
        elif not np.array_equal(cc, rc):
            rec["reason"] = "counts differ"
        elif not np.array_equal(ci, ri):
            rec["reason"] = "indices differ"
        else:
            maxerr = float(np.max(np.abs(cp - rp))) if cp.size else 0.0
            rec["maxerr"] = maxerr
            if maxerr <= _PT_ATOL:
                rec["ok"] = True
            else:
                rec["reason"] = "points maxerr %.3e > tol %.1e" % (maxerr, _PT_ATOL)
        all_ok = all_ok and rec["ok"]
        result["scenes"].append(rec)
    result["ok"] = all_ok
except Exception as exc:
    import traceback
    result["errors"].append(traceback.format_exc())
finally:
    print("PARITY_JSON:" + json.dumps(result))
    try:
        maya.standalone.uninitialize()
    except Exception:
        pass
    sys.exit(0 if result.get("ok") else 1)
