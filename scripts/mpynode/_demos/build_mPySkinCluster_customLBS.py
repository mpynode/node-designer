"""Demo builder: mPySkinCluster custom linear-blend skin.

A subdivided cylinder skinned by a custom ``mPySkinCluster`` running real
linear-blend skinning in its Compute expression.

Rig: a 3-bone chain along Y -- ``skinBase`` (bottom), ``skinMid`` (middle),
``skinTip`` (top). Only the BOTTOM and MIDDLE joints are used as skin
influences (the tip is just part of the chain). Per-vertex weights blend
linearly by height:

    bottom vertices -> (1.0, 0.0)   (fully the base joint)
    middle vertices -> (0.5, 0.5)
    top vertices    -> (0.0, 1.0)   (fully the middle joint)

The weights live in the node's ``weightList[v].weights[j]`` plug -- the
exact same plug Maya's Component Editor (Smooth Skins tab) and Paint Skin
Weights tool read and write. Because mPySkinCluster is a genuine skinCluster
(registered under kSkinCluster), editing a weight there re-evaluates the
deform live. The Compute densifies those weights each frame and reads the
live joint matrices, so posing either influence deforms the mesh.

LBS convention (Maya row-vector matrices): the per-joint skinning matrix is
``bindPreMatrix @ jointWorldMatrix`` (identity at the bind pose, so the mesh
sits at rest until a joint moves).
"""
from __future__ import annotations

import maya.cmds as mc

from mpynode._demos.save_demo import save_demo


INIT_SOURCE = """\
import numpy as np
"""


COMPUTE_SOURCE = """\
# Real linear-blend skinning, driven by the live weightList plug -- the same
# plug Maya's Component Editor and Paint Skin Weights write to:
#   self.outputGeometry[0]         -> writable mesh handle (getPoints/setPoints)
#   self.weightList[v].weights[j]  -> per-vertex, per-influence weight (sparse)
#   self.matrix[j]                 -> (4,4) joint world matrix (live)
#   self.bindPreMatrix[j]          -> (4,4) bind-pose inverse matrix
mesh = self.outputGeometry[0]
rest = mesh.getPoints()                                   # (N, 3)
N = rest.shape[0]

# Densify the sparse per-influence weights straight from the weightList plug.
# (Demo clarity over speed: this is an O(N*J) Python read every evaluation --
# a production deformer would cache a dense (N, J) array and re-densify only
# when weightList changes.)
sparse = {}
n_inf = 0
for v, vplug in self.weightList:
    for j, w in vplug.weights:
        sparse[(int(v), int(j))] = float(w)
        if int(j) + 1 > n_inf:
            n_inf = int(j) + 1

if n_inf == 0:
    mesh.setPoints(rest)                                  # nothing painted yet
else:
    W = np.zeros((N, n_inf), dtype=np.float64)
    for (v, j), w in sparse.items():
        W[v, j] = w

    joint_mats = np.stack([self.matrix[j].asNumpy() for j in range(n_inf)])        # (J,4,4)
    bind_mats = np.stack([self.bindPreMatrix[j].asNumpy() for j in range(n_inf)])  # (J,4,4)

    # Per-joint skinning matrix: bindPre @ jointWorld (identity at the bind pose).
    M = bind_mats @ joint_mats                            # (J, 4, 4)

    pts_h = np.concatenate([rest, np.ones((N, 1))], axis=1)
    # deformed[v] = sum_j W[v, j] * (pts_h[v] @ M[j])   (Maya row-vector convention)
    deformed_h = np.einsum("vj,jkc,vk->vc", W, M, pts_h)

    out = rest + self.envelope * (deformed_h[:, :3] - rest)
    mesh.setPoints(out)
"""


def build():
    mc.file(new=True, force=True)
    for plugin in ("mpynode_api1", "mpynode_api2"):
        if not mc.pluginInfo(plugin, q=True, loaded=True):
            mc.loadPlugin(plugin)

    import numpy as np
    import maya.api.OpenMaya as om

    from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster

    # --- subdivided cylinder at the origin (object space == world) ----------
    cyl = mc.polyCylinder(
        name="skinnedCylinder", radius=1.0, height=6.0,
        subdivisionsX=16, subdivisionsY=12,
    )[0]
    cyl_shape = mc.listRelatives(cyl, shapes=True, fullPath=True)[0]

    # --- 3-bone chain along Y: base (-3) -> mid (0) -> tip (3) ---------------
    mc.select(clear=True)
    j_base = mc.joint(name="skinBase", position=(0.0, -3.0, 0.0))
    j_mid = mc.joint(name="skinMid", position=(0.0, 0.0, 0.0))
    j_tip = mc.joint(name="skinTip", position=(0.0, 3.0, 0.0))   # chain only
    mc.select(clear=True)

    # Rest vertex positions (object space).
    sel = om.MSelectionList()
    sel.add(cyl_shape)
    rest_pts = np.asarray(
        om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kObject)
    )[:, :3]
    n_verts = rest_pts.shape[0]

    # Height-linear weights: t = (y - ymin)/(ymax - ymin);
    #   w_base = 1 - t (influence 0), w_mid = t (influence 1).
    ymin, ymax = -3.0, 3.0
    t = np.clip((rest_pts[:, 1] - ymin) / (ymax - ymin), 0.0, 1.0)
    weights = np.zeros((n_verts, 2), dtype=np.float64)
    weights[:, 0] = 1.0 - t
    weights[:, 1] = t

    # --- custom skinCluster: influences = base + mid ONLY -------------------
    wrapper = MPySkinCluster.create(mesh=cyl, joints=[j_base, j_mid], name="customLBS")
    node = wrapper.get_name()

    # Populate weightList -- the source of truth Maya's Component Editor and
    # Paint Skin Weights read/write. Both influences per vertex (including
    # zeros) so both columns show in the Smooth Skins tab. Weights MUST be
    # written before the first deformer evaluation: a real kSkinCluster locks
    # in a 0.5/0.5 default on first eval and then resists setAttr. rest_pts is
    # read via OpenMaya (no eval) and nothing here queries the output, so the
    # ordering holds.
    for v in range(n_verts):
        wrapper.set_vertex_weight(v, 0, float(weights[v, 0]))
        wrapper.set_vertex_weight(v, 1, float(weights[v, 1]))

    wrapper.set_init_expression(INIT_SOURCE)
    wrapper.set_compute_expression(COMPUTE_SOURCE)

    # Pose the middle joint so the top half bends on load; the bottom stays
    # anchored to the base joint.
    mc.setAttr(j_mid + ".rotateZ", 60.0)

    save_demo("mPySkinCluster_customLBS")


if __name__ == "__main__":
    build()
