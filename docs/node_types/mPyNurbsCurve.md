# mPyNurbsCurve

Expression-driven NURBS-curve geometry generator. A plain dependency-graph
node (`MPxNode`, NOT a DAG shape) — the same architecture as `mPyMesh`. Maya's
canonical curve generators (`rebuildCurve`, `offsetCurve`, `circle`,
`curveFromMeshEdge`) are all DG nodes whose output-curve plug feeds a real
`nurbsCurve` shape's `create` plug. The user expression produces CV positions
(+ optional knots / degree / form); the bridge builds an `MFnNurbsCurve` and
exposes it via `outCurve`. To make the curve visible, connect
`mPyNurbsCurve.outCurve` to a `nurbsCurve` shape's `create` plug.

---

## Plug-in

Registered in `plug-ins/mpynode_api2.py`. Simple `registerNode` — no parent
class, no draw override.

```
plugin.registerNode(
    MPyNurbsCurve.NODE_NAME, MPyNurbsCurve.NODE_ID,
    MPyNurbsCurve.creator, MPyNurbsCurve.initializer,
)
```

MTypeId: `0x0013571D`.

---

## Expression contract (`self.X`)

| `self.X` | Type | Access | Notes |
|---|---|---|---|
| `self.time` | `TimeFloat` | read | Current frame. Time is **opt-in** — manually connect `time1.outTime` → `<node>._timeIn` (or `add_input_attr("t", "time")` and read `self.t`) to re-evaluate per frame; otherwise the curve is static. Carries the scene fps: `self.time.fps` / `self.time.asSeconds()`. |
| `self.cvs` | `np.ndarray(N, 3)` float64 | write | **REQUIRED** CV positions. Must be `(N, 3)`; needs at least `degree + 1` CVs or an empty curve ships. |
| `self.knots` | `np.ndarray(K,)` float64 or `None` | write | Optional knot vector; default uniform. If the count doesn't match Maya's rule (`N + degree − 1` open/closed, `N + 2·degree − 1` periodic) it is rebuilt uniform. |
| `self.degree` | `int` | write | One of `{1, 2, 3, 5, 7}`; default `3`. Anything else falls back to `3`. |
| `self.form` | `str` | write | `'open'` / `'closed'` / `'periodic'`; default `'open'`. |
| `self.rational` | `bool` | write | **Currently accepted but NOT applied** — the bridge harvests `self.rational` but `build_default_output` ignores it and `MFnNurbsCurve.create` is called non-rational. Setting it has no effect today. |
| `self.outCurve` | `MObject (kNurbsCurveData)` or `None` | write | Optional merged-compute path: assign a fully-built curve-data MObject (typically `build_default_output(self.cvs, self.knots, self.degree, self.form)`) and it is used verbatim, bypassing the auto-build. If the value isn't a valid `kNurbsCurveData`, the framework silently falls back to building from `cvs`/`knots`/`degree`/`form`. |

> ⚠️ The wrapper docstring's example assigns `self.points` — that slot is **not**
> harvested, so it produces an **empty curve**. The required output is
> `self.cvs`. (Verified in Maya 2024: `self.cvs` → 8 CVs; `self.points` → 0.)

`build_default_output(cvs, knots, degree, form)` is a **public** marshaller
auto-seeded into the Init tab's imports
(`from mpynode._api2.mpy_nurbs_curve import build_default_output`); cmd+click it
to read, copy, or extend the implementation for a custom marshaller.

---

## Output plug

`outCurve` (short `oc`) — typed `kNurbsCurve`, read-only/non-storable. The
canonical Maya curve-data output. Connect to any downstream node that takes a
curve (a `nurbsCurve` shape's `create`, `rebuildCurve.inputCurve`, etc.).
`attributeAffects` ties `_timeIn`, `_computeSource`, the stored-var plug, and
the input/output maps to `outCurve`.

---

## Time invalidation

A process-wide `MEventMessage.timeChanged` callback (`register_time_change_callback`
in `scripts/mpynode/_api2/mpy_nurbs_curve.py`) dgdirty-s the `outCurve` plug of
every **time-driven** mPyNurbsCurve (one with an incoming `time` connection) on
each frame change; static curves (no time connection) are skipped. This is the
reliable trigger because Maya caches typed-data plugs across consecutive queries
in mayapy — same pattern as `mPyMesh`.

---

## Failure mode

Any expression error → **ship an empty curve** (no crash). Validation failures
(CVs not `(N, 3)`, fewer than `degree + 1` CVs, bad degree, knot-count mismatch)
are surfaced via `sys.stderr` and `log_bus.log()` (UI Log panel) and also ship
an empty / corrected curve.

---

## No DAG presence

Like `mPyMesh`, this is a plain DG node: no parent transform is auto-created, it
has no bounding box, and it shows only in the Hypergraph / DG view (not the
Outliner DAG tree). The bounding box of the rendered geometry lives on the
downstream `nurbsCurve` shape — exactly where Maya users expect it.

---

## Example

Build a procedural sine-wave NURBS curve generator and wire its `outCurve` into a real `nurbsCurve` shape so Maya renders it. The compute writes the required `self.cvs` (N, 3) array and marshals it through `build_default_output`; querying the downstream shape proves the curve was built headless.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_nurbs_curve import MPyNurbsCurve

mc.file(new=True, force=True)

# Create the generator (a plain DG node -- NOT a DAG shape).
gen = MPyNurbsCurve.create(name="sineCurveGen")

# Author the compute: write self.cvs (REQUIRED, (N,3)) then marshal to
# kNurbsCurveData via the framework's build_default_output. NOTE the real
# slot is self.cvs -- self.points is NOT harvested (ships an empty curve).
gen.set_init_expression(
    "import numpy as np\n"
    "from mpynode._api2.mpy_nurbs_curve import build_default_output\n"
)
gen.set_compute_expression(
    "import numpy as np\n"
    "u = np.linspace(0.0, 1.0, 8)\n"
    "self.cvs = np.stack([u * 4.0, np.sin(u * 6.28) * 0.5, np.zeros_like(u)], axis=1)\n"
    "self.degree = 3\n"
    "self.outCurve = build_default_output(self.cvs, self.knots, self.degree, self.form)\n"
)

# Wire outCurve into a real nurbsCurve shape's create plug so Maya builds it.
xform = mc.createNode("transform", name="sineCurveRender")
shape = mc.createNode("nurbsCurve", name="sineCurveRenderShape", parent=xform)
mc.connectAttr(gen.get_name() + ".outCurve", shape + ".create", force=True)

# Force evaluation and read back a concrete result (headless, no viewport).
mc.dgeval(gen.get_name() + ".outCurve")
spans = mc.getAttr(shape + ".spans")
cv_count = spans + mc.getAttr(shape + ".degree")  # open curve: spans + degree CVs
assert cv_count == 8, "expected 8 CVs, got %r" % cv_count
print("mPyNurbsCurve OK -- built nurbsCurve with %d CVs (degree %d)"
      % (cv_count, mc.getAttr(shape + ".degree")))
```

---

## Wrapper constructors

| Method | Purpose |
|---|---|
| `MPyNurbsCurve(name)` | Wrap an existing `mPyNurbsCurve` node by name. |
| `MPyNurbsCurve.create(name='mPyNurbsCurve#')` | Create a bare DG node (`ensure_loaded` + `createNode`). Time is **opt-in** — a fresh curve is not wired to `time1`. |

The wrapper is re-exported from the package root, so `from mpynode import
MPyNurbsCurve` also works. Expression/attr/variable authoring uses the shared
`MPyNode` API.

---

## See also

- Wrapper: `scripts/mpynode/wrappers/mpy_nurbs_curve.py`
- Bridge: `scripts/mpynode/_api2/mpy_nurbs_curve.py`
- Plug-in registration: `plug-ins/mpynode_api2.py`
- Sibling generators: [`mPyMesh.md`](mPyMesh.md), [`mPyNurbsSurface.md`](mPyNurbsSurface.md)
