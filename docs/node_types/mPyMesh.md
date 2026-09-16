# mPyMesh

Expression-driven polygon geometry generator. A plain dependency-graph
node (`MPxNode`, NOT a DAG shape). Matches Maya's canonical pattern for
polygon geometry generators — `polyCube`, `polySplit`, `polyAppend`,
`polyBevel` are all DG nodes that output mesh data via an `outMesh`
plug. To make the geometry visible in the viewport, connect
`mPyMesh.outMesh` to a real Maya `mesh` shape's `inMesh` plug.

---

## Plug-in

Registered in `plug-ins/mpynode_api2.py`. Simple `registerNode` — no
parent class, no draw override.

```
plugin.registerNode(
    MPyMesh.NODE_NAME, MPyMesh.NODE_ID,
    MPyMesh.creator, MPyMesh.initializer,
)
```

MTypeId: `0x00135719`.

---

## Internal vars schema (7 entries)

| Name | Type | Access | Notes |
|---|---|---|---|
| `time` | `TimeFloat` | read | Current frame. Time is **opt-in** — manually connect `time1.outTime` → `<node>._timeIn` to make the expression re-evaluate per frame; otherwise the mesh is static. Carries the scene fps: `self.time.fps` / `self.time.asSeconds()`. |
| `points` | `np.ndarray(N, 3)` | write | REQUIRED per-vertex positions. |
| `counts` | `np.ndarray(F,)` int | write | REQUIRED vertex count per face (≥ 3). |
| `indices` | `np.ndarray(sum(counts),)` int | write | REQUIRED connectivity flat array. |
| `colors` | `np.ndarray(F, 3\|4)` or `(3\|4,)` or `None` | write | Optional color. A 2D array is applied **per-face** and must be shape `(F, 3\|4)` or it is silently dropped; a single `(3\|4,)` is a uniform color. |
| `normals` | `np.ndarray(N, 3)` or `None` | write | **Currently accepted but NOT applied** — the bridge harvests `self.normals` but never assigns it; Maya always computes smooth normals regardless. |
| `outMesh` | `MObject (kMeshData)` or `None` | write | Optional merged-compute path: write a fully-built mesh-data MObject (e.g. from `build_default_output(points, counts, indices, colors=...)`) and it is used verbatim, bypassing the `points`/`counts`/`indices` auto-build. |

---

## Output plug

`outMesh` — typed `kMesh`. The canonical Maya mesh output plug.
Connect to any downstream node that takes a mesh.

---

## Time invalidation

A process-wide `MEventMessage.timeChanged` callback dgdirty-s the `outMesh`
plug of every **time-driven** mPyMesh (one with an incoming `time`
connection) on every frame change; static meshes (no time connection) are
skipped. Even with
`attributeAffects(_timeIn, outMesh)` declared, Maya's mesh-data plug
caches across consecutive queries in mayapy. The callback's direct
dgdirty is the reliable trigger — same pattern as the transform node
mPyTransform.

---

## Failure mode

Any expression error → **ship an empty mesh**. The downstream mesh
shows nothing; the scene doesn't crash. Errors surface via `sys.stderr`
and `log_bus.log()` (UI Log panel).

Validation errors (degenerate face count, out-of-range index,
sum(counts) ≠ len(indices)) are also surfaced + ship empty mesh.

---

## No bounding box, no DAG presence

Unlike the prior `mPyShape` design (which inherited from
`MPxSurfaceShape`), mPyMesh is a plain DG node:

- No parent transform auto-created
- No `isBounded` / `boundingBox` overrides
- Doesn't show in the Outliner's DAG tree (only in Hypergraph / DG view)
- Smaller surface, simpler registration

The bounding box of the rendered geometry lives on the downstream
`mesh` shape — exactly where Maya users expect it.

---

## Example

This builds an `mPyMesh` generator whose compute expression emits a static 2x2 grid of quads via the required `self.points` / `self.counts` / `self.indices` writes, wires `outMesh` into a real Maya `mesh` shape, and asserts the resulting topology headless with `polyEvaluate`.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_mesh import MPyMesh

mc.file(new=True, force=True)

# Build the expression-driven polygon generator (a DG node, no transform).
gen  = MPyMesh.create(name="quadGen")
node = gen.get_name()

# Compute a static 2x2 grid of quads: 3x3 = 9 verts, 4 quad faces.
# REQUIRED writes are self.points / self.counts / self.indices; the
# bridge auto-builds the mesh-data from them onto outMesh.
gen.set_init_expression("import numpy as np\n")
gen.set_compute_expression(
    "import numpy as np\n"
    "ix, iz = np.meshgrid(np.arange(3), np.arange(3), indexing='ij')\n"
    "self.points = np.stack([ix.ravel(), np.zeros(9), iz.ravel()], axis=-1).astype(np.float64)\n"
    "quads = []\n"
    "for r in range(2):\n"
    "    for c in range(2):\n"
    "        a = r * 3 + c\n"
    "        quads += [a, a + 1, a + 4, a + 3]\n"
    "self.counts = np.full(4, 4, dtype=np.int32)\n"
    "self.indices = np.array(quads, dtype=np.int32)\n"
)

# Wire outMesh into a real Maya mesh shape so the result is queryable headless.
xform = mc.createNode("transform", name="quadXfm")
shape = mc.createNode("mesh", parent=xform, name="quadShape")
mc.connectAttr(node + ".outMesh", shape + ".inMesh", force=True)

# Force evaluation by querying the downstream geometry.
verts = mc.polyEvaluate(shape, vertex=True)
faces = mc.polyEvaluate(shape, face=True)
assert verts == 9, "expected 9 vertices, got %r" % verts
assert faces == 4, "expected 4 quad faces, got %r" % faces
print("mPyMesh OK: vertices=%d faces=%d" % (verts, faces))
```

See `scripts/mpynode/_demos/build_mPyMesh_ribbon.py` for the
full demo.

---

## Mesh arithmetic and sub-mesh extraction

`Mesh` supports operators modelled on `MeshData` in
`rl/math/geometry/mesh.py`. `__add__` is `copy()` + `__iadd__`, so the merge
logic exists once and the pure form never mutates its operands.

| Expression | Meaning |
|---|---|
| `mesh + other_mesh` | **union** — appends faces, rebasing the other side's `indices` past our vertex count. Not a boolean. |
| `mesh - other_mesh` | **overlap removal** — drops the faces whose corners all coincide with a vertex of the other mesh. Not a boolean either; the inverse of the union. |
| `mesh + morph` | applies a sparse offset field: anything with `.indices` / `.offsets` (duck-typed, so `geometry.py` never imports `morph.py`) |
| `mesh + (0, 1, 0)` | offsets every point |
| `mesh * 2.0` | scales the point field |
| `mesh - morph` / `- vector` | the mirrors of `+` |
| `sum([m1, m2, m3])` | works — `__radd__` returns a copy on the `0` seed |

`mesh - other_mesh` is the reference's tolerance-based overlap removal
(`MeshData.difference`), not a boolean subtract. It matches our vertices against
the other mesh's within `tolerance` (default `1e-6`), then keeps the complement
through `from_vertices(matched, contained=True, exclude=True)`: a face survives
unless **every** one of its corners coincides — a partial match keeps the face.
Points are then compacted and `indices` renumbered, so derived channels,
component tags and UV sets are dropped. With no coincident vertex at all the
mesh comes back untouched, channels included. `(a + b) - b` gives back `a`
whenever `a` and `b` share no coincident vertices.

The vertex match is a uniform spatial hash whose grid step *is* the tolerance,
so a partner can only be in the same cell or one of the 26 touching it. The
27-cell scan is exact, not an approximation — the point is to get the kd-tree's
answer without making a core wrapper depend on the optional `scipy`.

The morph branch uses `np.add.at`, not `points[idx] += offsets` — fancy-index
in-place assignment keeps only the LAST write when indices repeat, which would
silently under-apply a target.

> **`Mesh + Morph` has no compiled path today — interpreted only.**
> An earlier draft of this page showed
> `self.outMesh = self.inMesh.copy() + self.morphs["smile"] * 0.5` as the
> mPyBlendShape blend. That is wrong twice over: mPyBlendShape is a *deformer*
> that reaches its geometry as `self.outputGeometry[0]` with
> `getPoints()`/`setPoints()` — it has no `inMesh`/`outMesh` — and
> `nd_lower._desugar_morphs` lowers only `weights`, `resolved`, `deltas()`,
> `apply()`, `[i|name].weight` and `len()`. There is no lowering for
> `Morph * scalar` or `Mesh + Morph`, so a compute written that way is pinned to
> interpreted.
>
> The canonical, compilable blend is what the shipped template uses:
>
> ```python
> mesh = self.outputGeometry[0]
> base = mesh.getPoints()
> mesh.setPoints(self.morphs.apply(base, self.envelope))
> ```
>
> The `Mesh + Morph` operators work and are unit-tested, but nothing ships using
> them; see §11.6 of
> `docs/design/2026-08-02-geometry-dunders-and-draw-types-spec.md`.

### Sub-meshes

| Call | Returns |
|---|---|
| `mesh.from_faces(faces, exclude=False)` | a new detached Mesh of those faces, points compacted and `indices` renumbered |
| `mesh.from_vertices(verts, contained=True)` | faces touching those verts (`contained` requires EVERY corner) |
| `mesh.from_tag(tag)` | dispatches on the tag's own component type |
| `mesh.contains_vertices(verts, contained=True)` | just the face indices |

Use `from_tag`, **not** `from_faces(region(tag))`: `region()` returns POINTS for
a vertex tag and INDICES for a face tag, so feeding it to `from_faces` works for
one and silently produces garbage for the other. `from_tag` raises `KeyError`
listing the available tags when the name is absent.

```python
self.draw = DrawMesh(mesh.from_tag("left_cheek"), color=rgba, outline=WHITE)
```

`NurbsCurve` has one operator — `curve + other` concatenates CVs into one longer
curve, dropping `knots` so a uniform vector is rebuilt, and rejecting a degree
or `periodic` mismatch rather than silently re-fitting. `NurbsSurface` has none:
concatenating CVs has no meaning that preserves a `(u,v)` grid.

---

## history

Originally built as **mPyMesh** (MPxSurfaceShape + MPxDrawOverride).
Pivoted twice:

1. **mPyMesh → mPyShape**: dropped the draw override (couldn't produce
   visible geometry without a 2000-LOC apiMeshShape-style
   implementation; the connect-to-real-mesh pattern is the canonical
   Maya path anyway). Dropped selection-state slots (meaningless
   without self-rendering).

2. **mPyShape → mPyMesh**: dropped MPxSurfaceShape (no need to be a
   DAG shape if we're not rendering). Switched to plain MPxNode —
   matches `polyCube`, `polySplit`, `polyAppend`, `polyBevel` exactly.

Final result: a tight DG geometry generator, ~670 LOC for the bridge,
~80 LOC for the wrapper. The schema (12 → 7 entries), draw-override
file (~200 LOC), and DAG-only attrs all melted away.

---

## See also

- Demo: `scripts/mpynode/_demos/build_mPyMesh_ribbon.py`
- Wrapper: `scripts/mpynode/wrappers/mpy_mesh.py`
- Bridge: `scripts/mpynode/_api2/mpy_mesh.py`
- Plugin registration: `plug-ins/mpynode_api2.py`
