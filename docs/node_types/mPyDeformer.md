# mPyDeformer

Expression-driven custom deformer built on `MPxDeformerNode` (API 1.0).
This is the **canonical** deformer of the family — the simplest one, and
the baseline its siblings (`mPySkinCluster`, `mPyBlendShape`) are described
against. You write a per-vertex Python expression; the node deforms whatever
geometry it is applied to — polygon meshes (`getPoints`/`setPoints`) and
NURBS curves/surfaces (`cvPositions`/`setCVPositions`).

---

## Expression contract (`self.X`)

The deform expression reaches everything through `self.X`. There is **no**
bridge-injected `self.points` / `self.normals` / `self.weights` /
`self.deformed` schema — that older design was removed. The live surface is:

| `self.X` | Type | Access | Notes |
|---|---|---|---|
| `self.outputGeometry[i]` | `MFnMeshHandle` | read/write | The writable output mesh, **eager-copied from the input** before the expression runs. `getPoints()` returns `(N, 3)` float64 numpy; mutate and call `setPoints(arr)`. The bridge commits it on compute exit. An empty expression is therefore an identity (output = input). |
| `self.input[i].inputGeometry` | `MFnMesh` | read | Read-only handle to the upstream source geometry. |
| `self.envelope` | `float` | read | Deformer envelope (`0.0` = no effect, `1.0` = full). Inherited from `MPxDeformerNode` — every deformer gets it for free. |
| user input attrs | per type | read | Anything added with `add_input_attr(...)` is readable as `self.<name>`. See [`_input_type_contract.md`](_input_type_contract.md). |
| user storage | any | read/write | `self.foo = ...` for arbitrary per-node Python state persisted across evaluations. |

The standard idiom:

```python
import numpy as np
mesh = self.outputGeometry[0]  # writable MFnMesh handle
rest = mesh.getPoints()        # (N, 3) float64 numpy
out  = rest.copy()
out[:, 1] += float(self.envelope) * np.sin(rest[:, 0])
mesh.setPoints(out)                # commit
```

> ⚠️ Writing `self.deformed = arr` (the old contract) does **not** deform
> anything — `deformed` is not a plug, so it is silently stored as a user
> variable and the mesh comes out unchanged. Always go through
> `self.outputGeometry[i]`.

---

## Base class & MTypeId

- Base class: `MPxDeformerNode` (API 1.0; `MPxDeformerNode` does not exist
  in API 2.0).
- MTypeId: `0x00135716`.

---

## Lineage

```
MPxNode
  └── MPxGeometryFilter
        └── MPxDeformerNode
              ├── MPxSkinCluster   → mPySkinCluster
              ├── mPyDeformer
              └── mPyBlendShape
```

---

## Plug-in

Registered in `plug-ins/mpynode_api1.py` (API 1.0):

```python
plugin.registerNode(
    MPyDeformer.NODE_NAME, MPyDeformer.NODE_ID,
    MPyDeformer.node_creator, MPyDeformer.node_initializer,
    MPxNode.kDeformerNode,
)
```

`node_initializer` adds only the framework/instrumentation plugs
(`_computeSource`, `_inputAttrs`, `_outputAttrs`, stored-var plugs,
`debug_mode`) via `helpers.build_internal_attrs`. The `input[]`,
`outputGeometry[]`, and `envelope` plugs are inherited from
`MPxDeformerNode`.

---

## Output plug

The inherited `outputGeometry[]` multi from `MPxGeometryFilter`. This is
Maya's standard deformer output — downstream mesh shapes consume it
through their `inMesh`.

---

## Re-evaluation

- **User-input changes** (a connected matrix moving, a slider drag, a
  direct `setAttr`) propagate to the output automatically: the node
  overrides `setDependentsDirty` to mark every `outputGeometry[*]` plug
  dirty when `_computeSource`, `envelope`, the stored-var plug, or any
  user input attr changes.
- **Frame changes**: a process-wide `timeChanged` callback
  (`register_time_change_callback` in `scripts/mpynode/_api1/mpy_deformer.py`)
  touches `envelope` on every `mPyDeformer` so the deform re-evaluates as
  the timeline scrubs (falling back to `dgdirty` when `envelope` is
  connected).

---

## Failure mode

- **Expression error** → the input mesh is returned unchanged (the eager
  copy was seeded from the input before exec). The error is written to
  `sys.stderr` and broadcast to the Node Designer Log tab via
  `mpynode._common.log_bus.log()`. A broken expression never crashes Maya;
  it just shows the rest pose.
- **Topology change clamp** → if the output handle's vertex count no longer
  matches the input's, `commit_deformer_output()` skips the commit (output
  drops back to the input unchanged) and logs an stderr warning.

---

## Example

Creating a deformer is five steps: make a mesh, create the deformer **on**
it (`create_on`), add any user inputs (`add_input_attr`), write the
per-vertex Compute expression, then wire/drive the inputs. A self-contained
sine-wave deformer follows: `create_on` attaches an `mPyDeformer` to a
polyPlane, the compute expression pushes each vertex along Y through the
writable `self.outputGeometry[0]` handle scaled by `self.envelope`, then we
query the deformed vertices and assert one moved.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_deformer import MPyDeformer

mc.file(new=True, force=True)

# Build a flat polyPlane and attach the deformer in one call.
plane = mc.polyPlane(name="targetPlane", sx=20, sy=20, w=4, h=4)[0]
d     = MPyDeformer.create_on(plane, name="myDeformer")

# Deform contract: read/mutate/commit through self.outputGeometry[0].
d.set_init_expression("import numpy as np")
d.set_compute_expression(
    "mesh = self.outputGeometry[0]\n"
    "rest = mesh.getPoints()\n"
    "out  = rest.copy()\n"
    "out[:, 1] += float(self.envelope) * 0.5 * np.sin(rest[:, 0] * 4.0)\n"
    "mesh.setPoints(out)\n"
)
mc.setAttr(d.get_name() + ".envelope", 1.0)

# Force evaluation: querying the deformed plane's vertex positions pulls
# outputGeometry through the deformer's deform() in headless mayapy.
verts = mc.xform(plane + ".vtx[*]", q=True, ws=True, t=True)
ys    = verts[1::3]
peak  = max(abs(y) for y in ys)
assert peak > 0.05, "deformer did not move any vertex (peak Y=%r)" % peak
print("PASS deformed peak |Y| = %.4f" % peak)
```

To drive the deformation live, add a user input and connect it — e.g.
`d.add_input_attr("center", "matrix")` then
`mc.connectAttr(locator + ".worldMatrix[0]", d.get_name() + ".center")`.
When any user input changes (a connected matrix moving, a slider drag, a
direct `setAttr`) the deformer re-evaluates automatically — no keyframes or
timeline tick required.

See `scripts/mpynode/_demos/build_mPyDeformer_sphereWave.py` for the full
locator-driven wave demo (per-vertex normal push with an exponential
distance falloff).

---

## Wrapper constructors

| Method | Purpose |
|---|---|
| `MPyDeformer(name)` | Wrap an existing `mPyDeformer` node by name. |
| `MPyDeformer.create(name='mPyDeformer#')` | Create a bare node (not attached to any mesh). |
| `MPyDeformer.create_on(mesh, name='mPyDeformer#')` | Create + attach in one shot — equivalent to `mc.deformer(mesh, type='mPyDeformer')` plus wrapping. |

---

## The deformer family

`mPyDeformer` is the baseline; its three siblings share the same
`self.outputGeometry[i]` / `self.input[i].inputGeometry` / `self.envelope`
contract and the same `add_input_attr` / `set_compute_expression` /
`connectAttr` workflow. Only the base class and a few extra plugs differ:

| Node | Extra surface | Wrapper |
|---|---|---|
| `mPyDeformer` | — (the baseline; also accepts NURBS curve/surface via `cvPositions()` / `setCVPositions()`) | `mpynode.wrappers.mpy_deformer` |
| `mPySkinCluster` | `self.matrix[j]` / `self.bindPreMatrix[j]` (4×4 joint matrices) + sparse `self.weightList[i].weights` | `mpynode.wrappers.mpy_skin_cluster` |
| `mPyBlendShape` | multi-target morphing — aliased `self.weight[j]` (float) + baked CSR delta tables, built via `create(mesh=…)` + `add_target(mesh, name)` + `rebuild()` | `mpynode.wrappers.mpy_blend_shape` |

---

## See also

- Gallery templates: **New from Template → MPyDeformer**
  (`sine_ripple`, `unit_sphere_collision`, `nurbs_wave`)
- Wrapper: `scripts/mpynode/wrappers/mpy_deformer.py`
- Bridge: `scripts/mpynode/_api1/mpy_deformer.py`
- Plug-in registration: `plug-ins/mpynode_api1.py`
- Auto-dirty (why user-input changes re-evaluate with no timeline tick):
  `scripts/mpynode/_common/auto_dirty.py`
- Sibling deformers: [`mPySkinCluster.md`](mPySkinCluster.md),
  [`mPyBlendShape.md`](mPyBlendShape.md)
