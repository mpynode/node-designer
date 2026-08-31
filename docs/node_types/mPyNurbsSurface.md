# mPyNurbsSurface

Expression-driven NURBS-surface geometry generator. A plain dependency-graph
node (`MPxNode`, NOT a DAG shape) — mirrors `mPyMesh` / `mPyNurbsCurve`. Maya's
canonical surface generators (`loft`, `revolve`, `birail`) all output a
surface-data plug consumed by a downstream `nurbsSurface` shape's `create` plug.
The user expression produces a CV grid (+ optional knots / degree / form); the
bridge builds an `MFnNurbsSurface` and exposes it via `outSurface`. To make the
surface visible, connect `mPyNurbsSurface.outSurface` to a `nurbsSurface`
shape's `create` plug.

---

## Plug-in

Registered in `plug-ins/mpynode_api2.py`. Simple `registerNode` — no parent
class, no draw override.

```
plugin.registerNode(
    MPyNurbsSurface.NODE_NAME, MPyNurbsSurface.NODE_ID,
    MPyNurbsSurface.creator, MPyNurbsSurface.initializer,
)
```

MTypeId: `0x0013571E`.

---

## Expression contract (`self.X`)

| `self.X` | Type | Access | Notes |
|---|---|---|---|
| `self.time` | `TimeFloat` | read | Current frame. Time is **opt-in** — connect `time1.outTime` → `<node>._timeIn` (or `add_input_attr("t", "time")` and read `self.t`) to re-evaluate per frame; otherwise the surface is static. Carries the scene fps. |
| `self.cvs` | `np.ndarray(num_cvs_u, num_cvs_v, 3)` **or** `(num_cvs_u·num_cvs_v, 3)` | write | **REQUIRED** CV grid. Preferred form is the 3-D grid — the bridge derives `num_cvs_u`/`num_cvs_v` from its shape. The flat 2-D form requires `self.num_cvs_u` + `self.num_cvs_v` (row-major, matching `grid.reshape(u·v, 3)`). |
| `self.num_cvs_u` / `self.num_cvs_v` | `int` | write | CV counts per direction. **Required only for the flat `(N, 3)` form**; ignored when `cvs` is a 3-D grid. `num_cvs_u·num_cvs_v` must equal the row count. |
| `self.knots_u` / `self.knots_v` | `np.ndarray(K,)` float64 or `None` | write | Optional per-direction knot vectors; default uniform. Mismatched counts are rebuilt uniform. |
| `self.degree_u` / `self.degree_v` | `int` | write | One of `{1, 2, 3, 5, 7}`; default `3` each. Anything else falls back to `3`. |
| `self.form_u` / `self.form_v` | `str` | write | `'open'` / `'closed'` / `'periodic'` per direction; default `'open'`. |
| `self.outSurface` | `MObject (kNurbsSurfaceData)` or `None` | write | Optional merged-compute path: assign a fully-built surface-data MObject (typically `build_default_output(...)`) and it is used verbatim, bypassing the auto-build. If the value isn't a valid `kNurbsSurfaceData`, the framework falls back to building from the `cvs`/shape fields. |

> ⚠️ The wrapper docstring's example assigns `self.points` — that slot is **not**
> harvested, so it produces an **empty surface**. The required output is
> `self.cvs`. (Verified in Maya 2024: a `(4, 4, 3)` `self.cvs` grid → a 4×4 CV
> surface; `self.points` → 0×0.)

`build_default_output(cvs, num_cvs_u, num_cvs_v, knots_u, knots_v, degree_u,
degree_v, form_u, form_v)` is a **public** marshaller auto-seeded into the Init
tab's imports; it accepts either CV shape directly.

---

## Output plug

`outSurface` (short `os`) — typed `kNurbsSurface`, read-only/non-storable.
Connect to a `nurbsSurface` shape's `create` (or any node that takes a surface).
`attributeAffects` ties `_timeIn`, `_computeSource`, the stored-var plug, and the
input/output maps to `outSurface`.

---

## Time invalidation

A process-wide `MEventMessage.timeChanged` callback (`register_time_change_callback`
in `scripts/mpynode/_api2/mpy_nurbs_surface.py`) dgdirty-s the `outSurface` plug
of every **time-driven** mPyNurbsSurface (one with an incoming `time` connection)
on each frame change; static surfaces are skipped — same mayapy typed-data-plug
caching workaround as `mPyMesh` / `mPyNurbsCurve`.

---

## Failure mode

Any expression error → **ship an empty surface** (no crash). Validation failures
(CVs not `(U, V, 3)` / `(N, 3)`, `num_cvs_u·num_cvs_v` ≠ rows, fewer than
`degree + 1` CVs in a direction, bad degree, knot-count mismatch) are surfaced
via `sys.stderr` and `log_bus.log()` and ship an empty / corrected surface.

---

## No DAG presence

Like `mPyMesh`, this is a plain DG node: no parent transform is auto-created, no
bounding box, and it shows only in the Hypergraph / DG view. The rendered
surface's bounding box lives on the downstream `nurbsSurface` shape.

---

## Example

A headless mayapy example that builds an `mPyNurbsSurface` generator whose compute writes a `(5, 5, 3)` CV grid into `self.cvs`, wires its `outSurface` into a real `nurbsSurface` shape, then forces evaluation and asserts the resulting surface has the expected span counts.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_nurbs_surface import MPyNurbsSurface

mc.file(new=True, force=True)

# Build the expression-driven NURBS-surface generator (a DG node).
surf = MPyNurbsSurface.create(name="sineSurfGen")

# The compute MUST write self.cvs (a (Nu, Nv, 3) CV grid). The wrapper
# docstring's self.points is NOT harvested and yields an empty surface.
surf.set_compute_expression('''
import numpy as np
u = np.linspace(0.0, 4.0, 5)
v = np.linspace(0.0, 4.0, 5)
U, V = np.meshgrid(u, v, indexing="ij")
Y = 0.5 * np.sin(U * 1.5) * np.cos(V * 1.5)
self.cvs = np.stack([U, Y, V], axis=-1)   # (5, 5, 3) grid
self.degree_u = 3
self.degree_v = 3
''')

# Wire outSurface into a real nurbsSurface shape so Maya evaluates it.
xform = mc.createNode("transform", name="sineSurf")
shape = mc.createNode("nurbsSurface", name="sineSurfShape", parent=xform)
mc.connectAttr(surf.get_name() + ".outSurface", shape + ".create", force=True)

# Force evaluation and assert the surface materialized headless.
mc.dgeval(shape + ".create")
spans_u = mc.getAttr(shape + ".spansU")
spans_v = mc.getAttr(shape + ".spansV")
# 5 CVs at degree 3 (open) -> 5 - 3 = 2 spans per direction.
assert (spans_u, spans_v) == (2, 2), (spans_u, spans_v)
print("OK mPyNurbsSurface -> nurbsSurface: spansU=%d spansV=%d" % (spans_u, spans_v))
```

---

## Wrapper constructors

| Method | Purpose |
|---|---|
| `MPyNurbsSurface(name)` | Wrap an existing `mPyNurbsSurface` node by name. |
| `MPyNurbsSurface.create(name='mPyNurbsSurface#')` | Create a bare DG node (`ensure_loaded` + `createNode`). Time is **opt-in** — a fresh surface is not wired to `time1`. |

The wrapper is re-exported from the package root, so `from mpynode import
MPyNurbsSurface` also works. Expression/attr/variable authoring uses the shared
`MPyNode` API.

---

## See also

- Wrapper: `scripts/mpynode/wrappers/mpy_nurbs_surface.py`
- Bridge: `scripts/mpynode/_api2/mpy_nurbs_surface.py`
- Plug-in registration: `plug-ins/mpynode_api2.py`
- Sibling generators: [`mPyMesh.md`](mPyMesh.md), [`mPyNurbsCurve.md`](mPyNurbsCurve.md)
