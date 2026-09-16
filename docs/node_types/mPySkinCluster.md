# mPySkinCluster

Expression-driven custom skinCluster built on `MPxSkinCluster` (API 1.0
only). The highest-level deformer in the family — it is a **genuine
skinCluster by type** (registered under `MPxNode.kSkinCluster`), so it
carries the standard skinCluster plugs (per-joint world matrices, bind-pose
inverses, sparse weights) and Maya's native skinning tools recognise it. You
write your own skinning formula (linear-blend, dual-quaternion, custom) in
Python.

---

## Works with Maya's native skinning tools

Because it registers under `MPxNode.kSkinCluster`, Maya treats it as a real
skinCluster:

- **Component Editor → "Smooth Skins" tab** shows and edits the per-influence
  weights.
- **Paint Skin Weights** (`artAttrSkinPaintCtx`) enumerates the influences and
  paints onto the mesh.
- `cmds.skinPercent` (set and query), `cmds.skinCluster -q -inf`, and
  `MFnSkinCluster` (`influenceObjects()`, etc.) all work.

These tools read and write the `weightList[v].weights[j]` plug, which is the
**live source of truth**: editing a weight there re-evaluates the deform
immediately (the C++ base class propagates `weightList → outputGeometry`
dirtiness natively).

> ⚠️ **Known caveat:** `MFnSkinCluster.getWeights()` returns zeros for a
> *Python* `MPxSkinCluster` subclass even when the `weightList` plug is
> correctly populated (the C++ weight cache is divorced from the plug for a
> Python subclass). The plug-reading tools above (Component Editor, Paint,
> `skinPercent`) are unaffected. If your own code needs the weights, read the
> `weightList[v].weights[j]` plug (or use `skinPercent`), not `getWeights()`.

---

## Expression contract (`self.X`)

There is **no** bridge-injected `self.points` / `self.joint_matrices` /
`self.bind_matrices` / `self.weights` / `self.deformed` schema — that older
design (with automatic weight densification) was removed. The joints,
weights, and bind matrices reach the expression **through the plug tree**:

| `self.X` | Type | Access | Notes |
|---|---|---|---|
| `self.outputGeometry[i]` | `MFnMeshHandle` | read/write | Writable output mesh, eager-copied from input. `getPoints()` → `(N, 3)` numpy; `setPoints(arr)` commits. |
| `self.input[i].inputGeometry` | `MFnMesh` | read | Read-only upstream source. |
| `self.envelope` | `float` | read | Inherited envelope. |
| `self.matrix[j]` | `MatrixView` | read | Joint *world* matrix. `self.matrix[j].asNumpy()` → `(4, 4)` float64. |
| `self.bindPreMatrix[j]` | `MatrixView` | read | Joint bind-pose inverse. `self.bindPreMatrix[j].asNumpy()` → `(4, 4)` float64. |
| `self.weightList[i].weights` | sparse | read | Per-vertex sparse weight read — Maya's standard `weightList[v].weights[j]` storage (the plug the Component Editor / Paint Skin Weights edit). Iterate it to densify (`for v, vp in self.weightList: for j, w in vp.weights: ...`); see the demo. |
| user input attrs / storage | per type | read/write | `add_input_attr(...)` names + `self.foo` Python state. |

> ⚠️ The old `self.deformed = ...` write does nothing — commit through
> `self.outputGeometry[i].setPoints(...)`.

---

## Plug-in

Registered in `plug-ins/mpynode_api1.py` (API 1.0 only):

```python
plugin.registerNode(
    MPySkinCluster.NODE_NAME, MPySkinCluster.NODE_ID,
    MPySkinCluster.node_creator, MPySkinCluster.node_initializer,
    MPxNode.kSkinCluster if hasattr(MPxNode, "kSkinCluster")
    else MPxNode.kDeformerNode,   # defensive fallback only
)
```

MTypeId: `0x0013571B`.

Registering under `MPxNode.kSkinCluster` is what gives the node genuine
skinCluster lineage (so the native skin tools recognise it). The C++
`MPxSkinCluster` base auto-provides `matrix[]`, `bindPreMatrix[]` and
`weightList`. `node_initializer` *also* declares `matrix[]` / `bindPreMatrix[]`
manually (the duplicate-name error is expected and swallowed) — this is dead
weight on the normal path but required for the defensive `kDeformerNode`
fallback, where a plain deformer base does not provide those plugs.

---

## Lineage

```
geometryFilter
  └── skinCluster
        └── THskinCluster
              └── mPySkinCluster   (apiType kPluginSkinCluster)
```

(`hasFn(MFn.kSkinClusterFilter)` is `True` — the type check every native skin
tool performs.)

---

## Wrapper helper

`MPySkinCluster.create(mesh, joints=[...], name=...)` attaches the deformer
via `mc.deformer`, connects each joint's `worldMatrix[0]` into `matrix[i]`,
and seeds `bindPreMatrix[i]` from each joint's `worldInverseMatrix[0]` at the
current (bind) pose:

```python
from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster
sc = MPySkinCluster.create(mesh=cylinder, joints=[j1, j2], name="mySkin")
sc.set_vertex_weight(vertex_index=0, joint_index=0, weight=1.0)  # weightList[0].weights[0]
```

`mc.skinCluster`'s *bind* command is hard-coded to the native skinCluster type
and can't create a custom `MPxSkinCluster`, so the helper does the joint plug
wiring directly. After that, the node is a real skinCluster, so `skinPercent`,
the Component Editor and Paint Skin Weights all work on it — populate the
initial weights via `set_vertex_weight`, a `setAttr` loop, or `skinPercent`,
then refine them with Maya's tools.

---

## Output plug

The inherited `outputGeometry[]` multi from `MPxGeometryFilter`.

---

## Failure mode

Expression error → input mesh unchanged (error to `sys.stderr` + Log tab).
Vertex-count mismatch on commit → output drops back to input with an stderr
warning.

---

## Example

This builds a 2-joint chain skinning a cylinder with a custom `mPySkinCluster`
that runs linear-blend skinning in its Compute expression. It populates the
`weightList` plug (the live source of truth Maya's skin tools edit), then the
Compute densifies those weights straight from `self.weightList`, reads the
live joint matrices (`self.matrix[j]` / `self.bindPreMatrix[j]`), and commits
through `self.outputGeometry[0].setPoints(...)`. Rotating the mid joint bends
the cylinder; the assert proves a top vertex moved off its rest position
headlessly.

```python
import numpy as np
import maya.cmds as mc
import maya.api.OpenMaya as om
from mpynode.wrappers.mpy_skin_cluster import MPySkinCluster

mc.file(new=True, force=True)

# Cylinder at the origin (object space == world) + a 2-joint chain along Y.
cyl = mc.polyCylinder(name="skinnedCyl", radius=1.0, height=6.0,
                      subdivisionsX=12, subdivisionsY=10)[0]
cyl_shape = mc.listRelatives(cyl, shapes=True, fullPath=True)[0]
mc.select(clear=True)
j_base = mc.joint(name="jBase", position=(0.0, -3.0, 0.0))
j_mid  = mc.joint(name="jMid", position=(0.0, 0.0, 0.0))
mc.select(clear=True)

# Rest positions -> height-linear (N, 2) weights (col 0 = base, col 1 = mid).
sel = om.MSelectionList(); sel.add(cyl_shape)
rest    = np.asarray(om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kObject))[:, :3]
t       = np.clip((rest[:, 1] + 3.0) / 6.0, 0.0, 1.0)
weights = np.zeros((rest.shape[0], 2), dtype=np.float64)
weights[:, 0], weights[:, 1] = 1.0 - t, t

# create() attaches the deformer, wires worldMatrix -> matrix[i], seeds bindPreMatrix.
sc = MPySkinCluster.create(mesh=cyl, joints=[j_base, j_mid], name="myLBS")

# Populate the weightList plug -- both influences per vertex (incl. zeros) so
# both columns show up in the Component Editor / Paint Skin Weights.
for v in range(rest.shape[0]):
    sc.set_vertex_weight(v, 0, float(weights[v, 0]))
    sc.set_vertex_weight(v, 1, float(weights[v, 1]))

sc.set_init_expression("import numpy as np\n")
sc.set_compute_expression(
    "import numpy as np\n"
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "N = rest.shape[0]\n"
    "sparse = {}\n"
    "n_inf = 0\n"
    "for v, vp in self.weightList:\n"
    "    for j, w in vp.weights:\n"
    "        sparse[(int(v), int(j))] = float(w)\n"
    "        n_inf = max(n_inf, int(j) + 1)\n"
    "W = np.zeros((N, n_inf), dtype=np.float64)\n"
    "for (v, j), w in sparse.items():\n"
    "    W[v, j] = w\n"
    "joint_mats = np.stack([self.matrix[j].asNumpy() for j in range(n_inf)])\n"
    "bind_mats = np.stack([self.bindPreMatrix[j].asNumpy() for j in range(n_inf)])\n"
    "M = bind_mats @ joint_mats\n"
    "pts_h = np.concatenate([rest, np.ones((N, 1))], axis=1)\n"
    "out = np.einsum('vj,jkc,vk->vc', W, M, pts_h)[:, :3]\n"
    "mesh.setPoints(rest + float(self.envelope) * (out - rest))\n"
)

# Pose the mid joint -> the top half (weighted to jMid) bends. Force eval + read back.
mc.setAttr(j_mid + ".rotateZ", 60.0)
mc.getAttr(cyl_shape + ".outMesh")  # pull the deformer
top   = int(np.argmax(rest[:, 1]))    # a vertex fully weighted to the rotated joint
moved = np.asarray(om.MFnMesh(sel.getDagPath(0)).getPoints(om.MSpace.kObject))[:, :3]
delta = float(np.linalg.norm(moved[top] - rest[top]))
assert delta > 0.1, "top vertex should move when jMid rotates, got delta=%f" % delta
print("OK mPySkinCluster deformed: top vertex moved %.4f units from rest" % delta)
```

See `scripts/mpynode/_demos/build_mPySkinCluster_customLBS.py` for the shipped
weightList-driven LBS demo. `build_mPySkinCluster_blend.py` blends between a
smooth and a rigid weight map; `build_mPySkinCluster_custom.py` is a simpler
procedural envelope-driven bend (no joint-matrix math).

---

## Differences vs the other deformers

| Aspect | mPyDeformer | mPySkinCluster |
|---|---|---|
| Base class | `MPxDeformerNode` | `MPxSkinCluster` (a real skinCluster) |
| Native skin tools | — | ✅ Component Editor / Paint Skin Weights / skinPercent |
| Joint matrices | — | ✅ `self.matrix[j]` / `self.bindPreMatrix[j]` |
| Weights | — | sparse `self.weightList[i].weights` (live, editable) |
| Geometry access | `self.outputGeometry[i]` | `self.outputGeometry[i]` |
| MTypeId | `0x00135716` | `0x0013571B` |

---

## See also

- Demo: `scripts/mpynode/_demos/build_mPySkinCluster_customLBS.py`
- Wrapper: `scripts/mpynode/wrappers/mpy_skin_cluster.py`
- Bridge: `scripts/mpynode/_api1/mpy_skin_cluster.py`
- Plug-in registration: `plug-ins/mpynode_api1.py`
- Sibling deformers: [`mPyDeformer.md`](mPyDeformer.md),
  [`mPyBlendShape.md`](mPyBlendShape.md)
