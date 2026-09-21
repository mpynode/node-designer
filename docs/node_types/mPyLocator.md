# mPyLocator

Expression-driven custom locator built on `MPxLocatorNode` (API 2.0) plus a
bundled `MPxDrawOverride`. The transform behaves like any standard locator (it
lives in the DAG and can be parented); the unique part is the Compute
expression, which is **draw code**: it assigns `self.draw`, and the override
renders it into `MUIDrawManager` every frame.

---

## One surface, one transport

`self.draw` is the only draw surface. It flattens into an **ordered command
list** — one record per authored item — which both the Python override and the
compiled C++ node replay front-to-back:

```
Draw* objects ──to_commands()──▶ [{"slot": …, "buffer": {…}}, …] ──▶ MUIDrawManager / C++ Data POD
```

**Authoring order is draw order.** Whatever you write last draws on top. Items
are deliberately *not* merged per type: bucketing by slot would silently reorder
the drawing (every label always last, whatever you wrote), and it buys nothing —
Maya's draw manager takes one `setColor` plus one primitive call per element
either way, so a merged buffer costs exactly the same calls as separate ones.

```python
from mpynode._common.draw.draw_types import DrawCircle, DrawCurve, DrawText

self.draw = (DrawCircle(center=(0, 0, -1), radius=6.0, color=(1, .8, .2))
              + DrawCurve(pts, color=lcol)
              + DrawText("hip_ctrl", position=(0, 2, 0), screen_space=True))
```

A plain **list** is the same drawing, nested as deeply as you like — so a
drawing accumulated in a loop needs no `sum()`, and its items stay individually
addressable (swap two, drop one, reorder):

```python
rings     = [DrawCircle(radius=r) for r in radii]
self.draw = [background, rings, DrawText("hip_ctrl", position=(0, 2, 0))]
```

`None` entries are skipped rather than rejected, so an accumulator that appends
"nothing here this frame" does not have to filter itself.

> There are **no** per-type dict buffers. `self.lines` / `self.points` /
> `self.polygons` / `self.shapes` / `self.text` do not exist — keeping a second,
> order-losing transport beside `self.draw` is exactly what let the interpreted
> and compiled renderers disagree about draw order.

---

## Object surface (`self.draw`)

`self.draw = <DrawItem>` — the same *read an object from `self.X`, write an
object to `self.Y`* idiom as `self.outMesh = Mesh(...)`.

| Type | Buffer | Notes |
|---|---|---|
| `DrawSphere` `DrawBox` `DrawCone` `DrawCylinder` `DrawCircle` | `shapes` | Maya's native primitives. `center`, `radius`, `axis`, `filled`. Scalars broadcast, so one primitive is one call. |
| `DrawMesh` | `polygons` | Takes a `Mesh` **or** `points, counts, indices`. `outline`, `outline_width`, `outline_boundary_only`, `world_space`, `precise_hover`, `cull_backfaces`, `highlight_fill`, `highlight_wire`, plus the four fill modes below. |
| `DrawCurve` | `lines` | A **polyline** through `points`; does the `[:-1]`/`[1:]` segment split and trims per-vertex colours for you. `closed=True` adds the wrap segment. `world_space` as on `DrawMesh`. |
| `DrawLines` | `lines` | Explicit `starts` / `ends` pairs. `world_space` as on `DrawMesh`. |
| `DrawPoints` | `points` | `positions`, `size` (pixels). |
| `DrawText` | `text` | `text` (one string or a list), `position`, `size`. |
| `DrawGroup` | — | What `+` returns. |

### `DrawMesh` fill modes

The polygons buffer defines four mutually-exclusive fill keys with a
renderer-side precedence. Each has a `DrawMesh` keyword named after the key it
emits, so the mapping stays one-to-one with the dict form:

| Keyword | Emits | Meaning |
|---|---|---|
| `color=` | `face_colors` | flat per face (a single RGBA broadcasts) |
| `uniform_color=` | `colors` | one colour, via the renderer's single-`setColor` fast path |
| `vertex_colors=` | `vertex_colors` | smooth, one row per shared point |
| `face_vertex_colors=` | `face_vertex_colors` | face-varying, one row per corner |

Passing two on **one** patch raises, rather than letting the renderer warn and
pick by precedence. Two *different* patches may each use a different mode —
each is its own command, so each keeps its own style. A `DrawMesh` with no fill
at all keeps the historical default (flat white `face_colors`), so an uncoloured
patch still draws filled.

`highlight_fill` / `highlight_wire` default to `None`, meaning *inherit the
node-wide `auto_highlight`*; only an explicit `True`/`False` is written through,
which is how a template turns selection tinting off for one aspect while keeping
it on for the other.

**Composition is `+` only.** There is no `*` and no `-`: `DrawCircle(...) * 2`
could equally mean twice the radius, twice the brightness, or drawn twice, and
an ambiguous operator fails silently. Note `+` here means *group*, unlike
`Morph.__add__`, which merges overlapping data.

Transforms and restyling are chainable methods returning **new** items, so a
drawing built once can be placed many times:

```python
ring      = DrawCircle(radius=1).colored(AMBER)
self.draw = ring + ring.translated(0, 2, 0).scaled(0.5)
```

`.colored(c)` · `.translated(x, y, z)` · `.scaled(f)` · `.in_space("screen")` ·
`DrawMesh.outlined(color, width, boundary_only)`

**Each item carries its own `space`.** A local-space circle and a screen-space
label coexist without either being reinterpreted, even when they are the same
type — one command per item means one `space` per item.

`DrawPrimitive.as_mesh(segments=16)` tessellates a primitive into a `DrawMesh`
when you want the styling only a mesh carries — `DrawSphere(radius=2).as_mesh()
.outlined(WHITE)`. It reproduces **what Maya draws**, so it keeps the same
conventions as the `MUIDrawManager` call behind each kind: a **cone**'s `center`
is its BASE and a **cylinder**'s is its MIDPOINT (both height `2 * radius`); a
**box** is the `up = axis` / `right = +X` frame with `radius` as the HALF extent
on each of the three; a **sphere** ignores `axis`. Colour and `space` carry over
(a per-primitive colour becomes per-face) and an array primitive becomes ONE
mesh of N shells; `filled` does not carry — a mesh picks its fill and outline
through `DrawMesh`'s own kwargs.

---

## Expression contract (`self.X`)

The expression's job is to assign `self.draw`. It also has read-only viewport
state and a few optional write-side framework toggles in scope.

### The drawing (write — `None` until assigned)

`self.draw` takes one `DrawItem`, several composed with `+`, or a (possibly
nested) list of them. `evaluateDrawItems` returns it as
`{"commands": [{"slot": …, "buffer": {…}}, …], "auto_highlight": …,
"auto_refresh": …, "precise_hover": …}`; each buffer's keys are:

| Slot | Buffer keys | Notes |
|---|---|---|
| `lines` | `starts`, `ends`, `colors`, `world_space` | Line segments (`(N,3)` arrays). |
| `points` | `positions`, `colors`, `sizes` | Screen-space point sprites. |
| `polygons` | `points`, `indices`, `counts` (+ fill/overlay options) | Filled polygons — see below. |
| `shapes` | `kinds`, `centers`, `radii`, `axes`, `colors`, `filled` | Maya built-ins: `sphere` / `box` / `cone` / `cylinder` / `circle`. |
| `text` | `positions`, `strings`, `colors`, `sizes` | Billboarded text labels. |

A `polygons` fill colour is **one of** (mutually exclusive): `colors` (uniform
RGB/RGBA), `face_colors` (`(F,3|4)`, flat per face), `vertex_colors`
(`(V,3|4)`, smooth per shared point), or `face_vertex_colors`
(`(sum(counts),3|4)`, face-varying). Extra options: `wireframe` overlays edges,
`wireframe_width` sets line width, `cull_backfaces` culls faces, and
`world_space=True` keeps the points in world space regardless of the locator
transform (useful when the geometry is pulled from a deformed mesh and the
locator drives the rig).

### Read-only viewport state

| `self.X` | Type | Notes |
|---|---|---|
| `self.time` | `TimeFloat` | Current frame (has `.fps` / `.asSeconds()`). |
| `self.selected` | `bool` | Viewport selection state (shape **or** its parent transform). |
| `self.is_lead` | `bool` | `True` iff this locator is the lead selection. |
| `self.hovered` | `bool` | `True` while the cursor is over this locator (from the cursor-ray `hover_tracker`). |
| `self.selection_color` | `(r, g, b, a)` tuple | Maya's themed wireframe/selection color. |

### Optional write-side toggles

| `self.X` | Type | Default | Notes |
|---|---|---|---|
| `self.precise_hover` | `bool` | `False` | Opt the whole node into precise ray-vs-drawn-triangle hover instead of bounding-box hover. One patch at a time via `DrawMesh(..., precise_hover=True)`; the two compose. |
| `self.auto_highlight` | `bool` / `None` | `True` | Override the automatic selection tint (when selected, per-buffer colors take `selection_color`'s RGB and keep their own alpha, so translucent drawing stays translucent). |
| `self.auto_refresh` | truthy / `None` | `False` (off) | Opt into a redraw timer so time-driven animation advances without a time-input plug. The value is treated as a **boolean flag** — any truthy value enables a fixed **30 fps** (`1/30 s`) redraw; falsy/`None` disables it. The interval is not user-configurable. |

> ⚠️ The wrapper docstring describes `auto_refresh` as "redraw interval in
> seconds" and `selection_color` as `(r, g, b)`. The live bridge coerces
> `auto_refresh` to a `bool` (fixed-rate 30 fps timer via
> `mpynode._common.draw_refresh`) and reports `selection_color` as
> `(r, g, b, a)`. The behavior documented here matches the code.

User INPUT plugs added with `add_input_attr(...)` are readable as `self.<name>`
and feed the draw. The numpy buffer helpers live in `_common/draw_buffers.py`.

---

## Limitation — no DG user OUTPUTS

`MPxLocatorNode` (a DAG shape) does **not** dispatch `compute()` for
runtime-added output plugs — verified in Maya 2024 standalone *and* 2026 GUI (a
plain `mPyNode` computes; the locator never does). User **inputs** work (they
feed the draw); user **outputs** won't evaluate. For output math, drive a
downstream `mPyNode`. The same limitation applies to `mPyIkSolver`
(`MPxIkSolverNode`) — its result is the joint rotations written during
`doSolve`, not a DG output plug.

---

## Base class & MTypeId

- Base class: `MPxLocatorNode` (API 2.0).
- MTypeId: `0x00135702`.
- Draw classification: `drawdb/geometry/mpyLocator` (`DRAW_DB_CLASSIFICATION`);
  draw registrant id `mPyLocatorPlugin` (`DRAW_REGISTRANT_ID`).

---

## Plug-in

The node and its draw override are both registered in
`plug-ins/mpynode_api2.py`, tied together by the classification string:

```python
plugin2.registerNode(
    MPyLocator.NODE_NAME, MPyLocator.NODE_ID,
    MPyLocator.creator, MPyLocator.initializer,
    om2.MPxNode.kLocatorNode,
    MPyLocator.DRAW_DB_CLASSIFICATION,
)
omr2.MDrawRegistry.registerDrawOverrideCreator(
    MPyLocator.DRAW_DB_CLASSIFICATION,
    MPyLocator.DRAW_REGISTRANT_ID,
    MPyLocatorDrawOverride.creator,
)
```

---

## Re-evaluation

By default Maya only calls `prepareForDraw` when the node is dirty — which for a
vanilla locator means "on selection-state change." Camera tumble, hover, and
frame changes without a time-input plug do **not** re-run the expression. Set
`self.auto_refresh = True` to enable the opt-in 30 fps timer
(`mpynode._common.draw_refresh`), which fires `setGeometryDrawDirty` on every
tick so the expression re-runs and animation advances smoothly. The timer is
crash-safe (per-node + scene-event teardown on delete / file-new / file-open /
Maya-exit).

---

## Failure mode

A draw-expression error leaves the command list empty (nothing drawn) and is
logged; it never crashes the viewport.

---

## Example

This builds an `mPyLocator` whose Compute expression is draw code: a 3-axis
gizmo, read back headlessly with the wrapper's `evaluate_draw_commands()` (no
viewport) to assert the returned buffer's shape.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_locator import MPyLocator

mc.file(new=True, force=True)

# Build the locator shape (Maya auto-creates the parent transform).
loc = MPyLocator.create(name="myGizmo")

# The Compute expression is DRAW code: assign self.draw. Here a 3-axis gizmo --
# red X, green Y, blue Z.
loc.set_compute_expression('''
import numpy as np
from mpynode._common.draw.draw_types import DrawLines
self.draw = DrawLines(
    np.zeros((3, 3)),
    np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float),
    color=np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float),
)
''')

# Run the expression headlessly (no viewport) and read back the commands.
cmds = loc.evaluate_draw_commands()["commands"]
assert [c["slot"] for c in cmds] == ["lines"], cmds
assert cmds[0]["buffer"]["ends"].shape == (3, 3)
print("OK lines.ends =\n", cmds[0]["buffer"]["ends"])
```

---

## Wrapper constructors & helpers

| Method | Purpose |
|---|---|
| `MPyLocator(name)` | Wrap an existing `mPyLocator` shape by name. |
| `MPyLocator.create(name='mPyLocator#')` | `createNode` the locator shape (Maya auto-creates the parent transform). |
| `loc.get_transform()` | Return the parent transform. |
| `loc.evaluate_draw_commands(time_value=0.0)` | Run the expression and return this frame's ordered draw commands — handy for testing without a viewport. |

The wrapper is re-exported from the package root, so `from mpynode import
MPyLocator` also works. It mixes in `MethodsSourceMixin`, so the Methods code
tier (compiled `@maya_command` helpers) is available like other node types.

---

## See also

- Wrapper: `scripts/mpynode/wrappers/mpy_locator.py`
- Bridge (node + draw override): `scripts/mpynode/_api2/mpy_locator.py`
- Draw-buffer helpers: `scripts/mpynode/_common/draw_buffers.py`
- Auto-refresh timer: `scripts/mpynode/_common/draw_refresh.py`
- Plug-in registration: `plug-ins/mpynode_api2.py`
- Input typing: [`_input_type_contract.md`](_input_type_contract.md)
- Sibling specialty node: [`mPyConstraint.md`](mPyConstraint.md)
