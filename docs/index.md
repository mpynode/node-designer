# mpynode API — Comprehensive Usage Guide

The complete API for building expression-driven Maya nodes via the
`mpynode` plug-ins. Covers all 12 node types, the shared
`add_input_attr` / `set_compute_expression` / `connectAttr` workflow, the
auto-dirty propagation system, stored variables, the Profile / Watch
/ Log instrumentation, plug-in auto-loading, and worked recipes.

For a focused walkthrough on building a deformer (the "5 steps", a worked
example, and the whole deformer family), see
[`node_types/mPyDeformer.md`](node_types/mPyDeformer.md).
Per-node design notes live under [`node_types/`](node_types/).

---

## Contents

1. [Quick start](#quick-start)
2. [Core concepts](#core-concepts)
3. [Node type cheat sheet](#node-type-cheat-sheet)
4. [Creating nodes — full API per type](#creating-nodes--full-api-per-type)
5. [Adding user attributes (`add_input_attr` / `add_output_attr`)](#adding-user-attributes-addinputattr--addoutputattr)
6. [Writing expressions (the `self.X` namespace)](#writing-expressions-the-selfx-namespace)
7. [Stored variables (persisted state)](#stored-variables-persisted-state)
8. [Auto-dirty propagation](#auto-dirty-propagation)
9. [Instrumentation — Log, Watch, Profile](#instrumentation--log-watch-profile)
10. [Plug-in loading + scene save/load](#plug-in-loading--scene-saveload)
11. [Failure mode](#failure-mode)
12. [Worked recipes](#worked-recipes)
13. [Troubleshooting / FAQ](#troubleshooting--faq)

---

## Quick start

Every wrapper is re-exported from the package root, so `from mpynode import
MPyX` works for all 12 types.

```python
from mpynode import MPyDeformer
import maya.cmds as mc

plane = mc.polyPlane(name="target", w=8, h=8, sx=40, sy=40)[0]

d = MPyDeformer.create_on(plane, name="myDeformer")
d.add_input_attr("matrix",  "matrix")
d.add_input_attr("falloff", "double")
d.set_compute_expression("""
import numpy as np
mesh = self.outputGeometry[0]          # writable MFnMesh handle
rest = mesh.getPoints()                # (N, 3) float64 numpy
pos  = np.asarray(self.matrix)[3, :3]  # matrix input is a (4, 4) MatrixView
dist = np.linalg.norm(rest - pos[None, :], axis=1)
fall = np.maximum(0.0, 1.0 - dist / max(float(self.falloff), 1e-6))
amp  = fall * 0.4 * np.sin(dist * 4.0)
out  = rest.copy()
out[:, 1] += amp * float(self.envelope)
mesh.setPoints(out)                    # commit
""")

loc = mc.spaceLocator(name="ctrl")[0]
mc.connectAttr(loc + ".worldMatrix[0]", d.get_name() + ".matrix", force=True)
mc.setAttr(d.get_name() + ".falloff", 4.0)
mc.setAttr(d.get_name() + ".envelope", 1.0)
```

Drag `ctrl` → ripples follow. Slide `falloff` → radius changes.
No keyframes or timeline ticks needed (the auto-dirty system
propagates connection-driven changes automatically).

---

## Core concepts

There are exactly three ideas to internalize:

### 1. Every node is a class with one expression slot

Each of the 12 node types is a Maya custom node whose `compute()`
runs a single Python expression you set via `set_compute_expression()`. The
expression has access to a curated `self.X` namespace (per node
type) plus any user-defined input attrs, read as `self.<name>`.

### 2. User attrs are declared dynamically

You don't sub-class the node — you just call `add_input_attr(name,
type)` / `add_output_attr(name, type)` on the wrapper. Maya gets new
plugs, the expression namespace gets new variables. Same node class,
different I/O per instance.

### 3. The wrapper is just a thin Python facade

Every wrapper (`MPyDeformer`, `MPyTransform`, …) inherits the single
base class `MPyNode`, which gives it:

* A `create` / `create_on` factory that loads the plug-in and
  instantiates the Maya node.
* A `set_compute_expression` / `get_compute_expression` pair.
* User-attr management (`add_input_attr` / `add_output_attr` / …).
* Per-instance Python storage (`add_variable` / `get_variables` / …).
* Profile + watch hooks (perf + value inspection).

Once a node exists, you can poke it via standard `cmds.setAttr` /
`cmds.connectAttr` like any other Maya node.

---

## Node type cheat sheet

Every wrapper is importable from the package root (`from mpynode import
MPyX`) and also from its module (`from mpynode.wrappers.mpy_x import MPyX`).

| Node | When to use | Wrapper | Plug-in |
|---|---|---|---|
| [`mPyNode`](node_types/mPyNode.md) | Generic compute — define inputs, write Python, declare outputs | `mpynode.MPyNode` | api2 |
| [`mPyLocator`](node_types/mPyLocator.md) | Custom viewport locator with `MPxDrawOverride` (lines, points, polygons, shapes, text) | `mpynode.MPyLocator` | api2 |
| [`mPyConstraint`](node_types/mPyConstraint.md) | Constraint-style node with target / rest preset inputs + user output math | `mpynode.MPyConstraint` | api2 |
| [`mPyFile`](node_types/mPyFile.md) | Expression-driven file-texture shading node (Hypershade / VP2) | `mpynode.MPyFile` | api2 |
| [`mPyMesh`](node_types/mPyMesh.md) | DG polygon generator — output mesh wired into a `mesh` shape | `mpynode.MPyMesh` | api2 |
| [`mPyNurbsCurve`](node_types/mPyNurbsCurve.md) | DG NURBS-curve generator | `mpynode.MPyNurbsCurve` | api2 |
| [`mPyNurbsSurface`](node_types/mPyNurbsSurface.md) | DG NURBS-surface generator | `mpynode.MPyNurbsSurface` | api2 |
| [`mPyIkSolver`](node_types/mPyIkSolver.md) | Custom IK solver — write your own joint chain solve | `mpynode.MPyIkSolver` | api1 |
| [`mPyTransform`](node_types/mPyTransform.md) | Custom transform with expression-driven local matrix | `mpynode.MPyTransform` | api1 |
| [`mPyDeformer`](node_types/mPyDeformer.md) | Expression-driven deformer (`MPxDeformerNode`) — handles polygon meshes and NURBS curves/surfaces | `mpynode.MPyDeformer` | api1 |
| [`mPySkinCluster`](node_types/mPySkinCluster.md) | Custom skinCluster — write your own LBS / DQ / heat-diffuse / etc. | `mpynode.MPySkinCluster` | api1 |
| [`mPyBlendShape`](node_types/mPyBlendShape.md) | Expression-driven deformer with a blendShape lineage — envelope-driven, with an aliased `weight[]` multi (`bs.browUp` *is* `bs.weight[0]`) and baked CSR delta tables, surfaced to the compute as one `self.morphs` object | `mpynode.MPyBlendShape` | api1 |

---

## Creating nodes — full API per type

Every wrapper has a `create` / `create_on` classmethod that
auto-loads the plug-in if needed. The returned object is the
wrapper. You can also wrap an existing node by name: `MPyDeformer("foo")`.

### Bare DG-style nodes (`mPyNode` family)

```python
from mpynode import MPyNode, MPyConstraint, MPyIkSolver

n  = MPyNode.create(name="myCompute")
c  = MPyConstraint.create(name="myConstraint")
ik = MPyIkSolver.find_solver()   # IK solver is a singleton instance, not create()
```

### Viewport-drawn locator

The draw expression assigns `self.draw` — one drawable, several composed with
`+`, or a (possibly nested) list of them. Authoring order is draw order.

```python
from mpynode import MPyLocator
loc = MPyLocator.create(name="myLocator")
loc.set_compute_expression("""
from mpynode._common.draw.draw_types import DrawLines
# A yellow line from origin to (1, 0, 0).
self.draw = DrawLines((0, 0, 0), (1, 0, 0), color=(1, 1, 0))
""")
```

### Time-driven transform

```python
from mpynode import MPyTransform
import maya.cmds as mc

t = MPyTransform.create(name="myBobber")
# Add a time input and wire time1.outTime so the matrix re-evaluates each frame.
t.add_input_attr("time", "double")
mc.connectAttr("time1.outTime", t.get_name() + ".time", force=True)
t.set_compute_expression("""
import numpy as np
y = np.sin(self.time * 0.3) * 2.0
m = np.eye(4)
m[3, 1] = y                     # translation lives in the last row (Maya is row-major)
self.local_matrix = m          # desired LOCAL (parent-relative) frame; gates default True
self.apply_rotate = False       # keep the live rotate/scale, drive translate only
self.apply_scale = False
""")
```

### DG polygon generator

```python
from mpynode import MPyMesh
p = MPyMesh.create(name="myProcGeom")
# Wire p.outMesh -> a real mesh shape's inMesh to render in the viewport.
p.set_compute_expression("""
import numpy as np
# A simple square (4 verts, 1 quad).
self.points  = np.array([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], dtype=float)
self.counts  = np.array([4], dtype=int)        # vertex count per face
self.indices = np.array([0, 1, 2, 3], dtype=int)  # flat connectivity
""")
```

### Deformer family (3 types)

```python
import maya.cmds as mc

# Expression-driven deformer (MPxDeformerNode) -- handles polygon meshes AND
# NURBS curves/surfaces (mesh: getPoints/setPoints; NURBS: cvPositions/setCVPositions).
from mpynode import MPyDeformer
d = MPyDeformer.create_on(mesh="myMesh", name="myDef")

# Custom skinCluster (joints wired by the helper, not mc.skinCluster)
from mpynode import MPySkinCluster
sc = MPySkinCluster.create(mesh="myMesh", joints=["j1", "j2"], name="mySkin")

# Custom blendShape-lineage deformer (envelope-driven + multi-target)
from mpynode import MPyBlendShape
bs = MPyBlendShape.create(mesh="myBase", targets=["targetA", "targetB"], name="myBlend")
```

### Wrapping existing nodes

Every wrapper supports `Wrapper(existing_node_name)`:

```python
d = MPyDeformer("mPySimpleDeformer")  # wraps the node already in the scene
d.set_compute_expression("""
mesh = self.outputGeometry[0]
mesh.setPoints(mesh.getPoints() * 2.0)
""")
```

---

## Adding user attributes (`add_input_attr` / `add_output_attr`)

`MPyNode` provides the same attr methods to every wrapper:

```python
d.add_input_attr(name, attr_type, is_array=False,
               enum_names=None, auto_connect_time=True)
d.add_output_attr(name, attr_type, is_array=False, enum_names=None)
d.delete_input_attr(name)
d.delete_output_attr(name)
d.rename_input_attr(old, new)
d.rename_output_attr(old, new)
d.get_input_attr_map()      # {name: {"attr_type": <stored name>, ...}, ...}
d.get_output_attr_map()
d.list_valid_input_types()  # the 21 stored attr_type names
```

### Supported `attr_type` values

21 types total, declared once in `_common/attr_types.py`. All support
`is_array=True` for multi plugs. Each type has two names: the one the Add
Attribute dropdown shows, and the stored one, Maya's where that alone
describes the plug. `attr_type` takes either (see
[Two names per type](#two-names-per-type)).

The table is in the dropdown's order and groups. **Dropdown** and
**Description** are the dropdown's two columns, word for word; **Stored** is
what files, scene attr maps and the get-APIs carry.

| Dropdown | Description | Stored | Maya plug | Python value the expression sees |
|---|---|---|---|---|
| **Numbers** | | | | |
| `"float64"` | double (64-bit) | `"double"` | `double` (the dialog's default; Maya's own "Float") | `float` |
| `"int"` | long | `"long"` | `long` | `int` |
| `"bool"` | bool (on / off) | `"bool"` | `bool` | `bool` |
| `"angle"` | doubleAngle (radians) | `"doubleAngle"` | `doubleAngle` | `float` (radians) |
| `"distance"` | doubleLinear (cm) | `"doubleLinear"` | `doubleLinear` (a distance, like `translateX`) | `float` (cm) |
| `"float32"` | float (32-bit) | `"float"` | `float` (32-bit) | `float` |
| **Vectors, compounds, matrix** | | | | |
| `"position"` | double3 of doubleLinear (cm) | `"position"` | `double3` of `doubleLinear`, like `translate` | `np.ndarray(3,)` float64 (cm) |
| `"vector"` | double3 (no unit) | `"double3"` | `double3` of `double` | `np.ndarray(3,)` float64 (no unit) |
| `"euler"` | double3 of doubleAngle (radians) | `"euler"` | `double3` of `doubleAngle`, like `rotate` | `np.ndarray(3,)` float64 (radians) |
| `"quaternion"` | double4 (X/Y/Z/W) | `"quaternion"` | `double4`, children X/Y/Z/W | `np.ndarray(4,)` float64 (X/Y/Z/W; W defaults to 1, so `[0, 0, 0, 1]` until set) |
| `"matrix"` | matrix (4x4 doubles) | `"matrix"` | `matrix` (`-at`) | `MatrixView` — numpy-transparent → `(4, 4)`; `np.asarray(m)`, `m @ x`, `.asNumpy()` / `.translation()` / …; identity until set |
| `"color"` | float3 (colour) | `"color"` | `float3`, `usedAsColor` | `np.ndarray(3,)` float64 (R/G/B; binds to shader color plugs) |
| `"uv"` | float2 (U/V) | `"float2"` | `float2`, children U/V | `np.ndarray(2,)` float64 (U/V) |
| **Text and data** | | | | |
| `"string"` | string (text) | `"string"` | `string` | `str` |
| `"enum"` | enum (named choices, default False/True) | `"enum"` | `enum` | `int` (`EnumInt`; `.name()` gives the field label) |
| `"hex"` | string (stored as UTF-8 hex) | `"hex"` | `string` | `str` (hex-decoded text) |
| `"pickle"` | string (pickled data, C++ unsupported) | `"pickle"` | `string` | arbitrary unpickled object (trust-gated; `None` in an untrusted scene) |
| **Geometry** | | | | |
| `"mesh"` | mesh (code gets a Mesh object) | `"mesh"` | the typed geometry plug | `Mesh`, which passes any `MFnMesh` method through (or `None` if unconnected) |
| `"nurbsCurve"` | nurbsCurve (code gets a NurbsCurve object) | `"nurbsCurve"` | the typed geometry plug | `NurbsCurve`, which passes any `MFnNurbsCurve` method through (or `None` if unconnected) |
| `"nurbsSurface"` | nurbsSurface (code gets a NurbsSurface object) | `"nurbsSurface"` | the typed geometry plug | `NurbsSurface`, which passes any `MFnNurbsSurface` method through (or `None` if unconnected) |
| **Time** | | | | |
| `"time"` | time (frames) | `"time"` | `time` | `float` (the current frame, in the UI time unit) |

`is_array=True` produces a Maya multi-plug:
* Numeric / 3-vector / color / uv / quaternion multis arrive as a stacked
  `np.ndarray` (position / vector / euler / color multi → `(n, 3)`; uv
  multi → `(n, 2)`; quaternion multi → `(n, 4)`).
* A matrix multi arrives as a `MatrixArrayView`, numpy-transparent
  (`np.asarray` → `(n, 4, 4)`).
* String / hex / pickle / geometry multis arrive as a `list`.

See [`node_types/_input_type_contract.md`](node_types/_input_type_contract.md)
for the complete attr-type → value contract, including the two places it
bends: mPyFile's Compute reads `uv` (`float2`) as a list and `hex` / `pickle`
undecoded, and the API 1.0 nodes write `hex` / `pickle` / `time` (and, on
mPyTransform / mPyIkSolver, `angle` / `euler`) outputs differently.

### The Add Attribute dialog

The Type dropdown lists all 21 in the five groups above, with a separator line
between groups that cannot be picked. Open, it is drawn as two columns, the
dropdown name and its description, the description at one x for every row;
closed, it shows the pick on one line, `<name> - <description>`. It
pre-selects `float64` (`float64 - double (64-bit)`) until you pick another
type, then remembers the last pick for the session. Whatever you pick, the
node gets the stored name: picking `vector` adds a `double3`.
The Min / Max / Default fields of a `distance` / `angle` are labelled `(cm)` /
`(radians)`. The Attributes list names each attribute the dropdown's way
(`pos: vector`), with `stored as double3` in the row's tooltip.

### Which type to pick

* `float64` (`double`) for a number. `float32` (`float`) only to match a
  32-bit plug; it reads as a Python `float` either way.
* `position` for anything wired to or from `translate`, or any point, when
  the value is in cm; `distance` (`doubleLinear`) for one translate channel.
  A value computed from a unitless input (e.g. mPyConstraint's presets) stays
  `vector` (`double3`).
* `euler` for `rotate`; `angle` (`doubleAngle`) for one rotate channel.
* `vector` for a unitless 3-vector: a direction, a scale.

The unit types use Maya's internal units whatever the scene's UI units:
`angle` / `euler` in radians, `distance` / `position` in centimetres. The
expression reads and writes those units. `min_value` / `max_value` /
`default_value` on an `angle` / `distance` are typed in them too, and the Add
Attribute dialog labels its Min / Max / Default fields for those two
`(radians)` / `(cm)`; `euler` and `position` take none. At linear unit m, a
`translate` of 1.5 reads 150.0 through a `position`, with no `unitConversion`
node between them. A `vector` wired from the same `translate` in that scene
gets a `unitConversion` node and reads 1.5; one wired while the scene was
still cm has none and keeps reading 150.0.

### Two names per type

Every type stores ONE name: Maya's attribute type where that alone describes
the plug, our own word where Maya tells the plug apart only by its child type
or a flag, or has no type for it (`position`, `euler`, `quaternion`, `color`,
`hex`, `pickle`). The dropdown's name, where it differs, is an alias, and so
are Maya's `double4` and `float3` for `quaternion` and `color`. Every input
point takes an alias and translates it to the stored name before anything is
created: `add_input_attr` / `add_output_attr`, an `.mpn` being restored, the
assistant's tools and a compile spec.

| Alias | Stored |
|---|---|
| `float64` | `double` |
| `int` | `long` |
| `angle` | `doubleAngle` |
| `distance` | `doubleLinear` |
| `float32` | `float` |
| `vector` | `double3` |
| `uv` | `float2` |
| `double4` | `quaternion` |
| `float3` | `color` |

```python
d.add_input_attr("aim", "vector")  # the dropdown's name
d.add_input_attr("up", "double3")  # the stored name: the same plug type

d.get_input_attr_map()["aim"]["attr_type"]  # -> "double3"
```

**Stored name everywhere it is saved or reported:** `.mpn` files, the `.py`
bake, scene attr maps (`_inputAttrs` / `_outputAttrs`),
`get_input_attr_map()` / `get_output_attr_map()`, `list_valid_input_types()`
and error messages. **Dropdown name where an artist reads it:** the Add
Attribute dialog, the Attributes list and the assistant's chat line
(`add_input pos (vector)`).

**`python` is now `pickle`**, both its stored and its dropdown name. New code
or an `.mpn` that names `python` is rejected with a hint,
`attr_type 'python' was renamed: use 'pickle'`, and compiling one reports it
as a blocker. A scene that stored `python` keeps computing: its map is
translated on read.

**Old scenes.** Scenes that stored `int` / `vector` / `angle` (the stored
names before the 2026-10-02 rename) load again. Their maps keep the old names
through a re-save, until an attribute edit on that side rewrites its map
(inputs and outputs separately); that is harmless, because every reader
translates. v1 scenes map their names through the same table on upgrade.

### How the expression sees them

User input attrs are read as `self.<name>` in the expression. (Attribute
names must be valid, non-keyword Python identifiers, since they are accessed
through `self`.)

```python
d.add_input_attr("amplitude", "float64")  # or "double"
d.add_input_attr("center", "matrix")
d.set_compute_expression("""
import numpy as np
ctr = np.asarray(self.center)[3, :3]   # matrix input -> (4, 4)
mesh = self.outputGeometry[0]
out = mesh.getPoints()
out[:, 1] += self.amplitude
mesh.setPoints(out)
""")
```

User output attrs are written back via `self.<output_name>`:

```python
n.add_output_attr("outTotal", "double")
n.set_compute_expression("self.outTotal = sum(self.inputs)")
```

---

## Writing expressions (the `self.X` namespace)

Each node type exposes a curated `self.X` namespace, plus any
user-declared inputs / outputs.

### Common to all node types

| `self.X` | Notes |
|---|---|
| User input attrs | Bare names in namespace (also readable via `self.<name>`) |
| User output attrs | Written via `self.<output_name>` |
| `self.<stored_var>` | Persisted Python objects (see Stored Variables) |
| `__builtins__` | Python builtins only — **no modules auto-imported**; `import numpy as np` yourself (or define it in the Init tab) |

### Per-node internal vars

| Node | Internal `self.X` slots |
|---|---|
| `mPyNode` | (user-defined inputs/outputs only) |
| `mPyLocator` | read: `self.time`, `self.selected`, `self.is_lead`, `self.hovered`, `self.selection_color`; write: `self.draw` (a `DrawItem`, a nested list of them, or `None`) + toggles `self.auto_highlight` / `self.auto_refresh` / `self.precise_hover` |
| `mPyConstraint` | read presets: `self.targetTranslate`, `self.targetRotate`, `self.targetWeight`, `self.restTranslate`, `self.restRotate` (all `(3,)` / float); outputs are user-added |
| `mPyIkSolver` | read: `self.joints` (list of dict incl. `matrix`/`world_matrix` MatrixViews), `self.end_effector`, `self.pole_vector`, `self.twist`, `MatrixView`; write: `self.local_matrices` (list[4×4 or None], LOCAL) and `self.world_matrices` (WORLD), both applied via `offsetParentMatrix` (dispatch WORLD > LOCAL > rest) + gates `self.apply_rotate` / `self.apply_translate` / `self.apply_scale` (scalar or per-joint list) |
| `mPyTransform` | read: `self.translate`, `self.rotate` (**radians**), `self.scale`, `self.shear`, `self.rotate_order` (0..5), plus any matrix INPUT attrs you add (`self.<name>.asNumpy()`); write: `self.local_matrix` (4×4 or None, LOCAL/parent-relative — for world set `worldDesired @ inv(parentWorld)` off a connected parent input) applied via `offsetParentMatrix` + gates `self.apply_rotate` / `self.apply_translate` / `self.apply_scale` (default True) |
| `mPyMesh` | write: `self.points (N, 3)`, `self.counts (F,)`, `self.indices`, optional `self.colors` / `self.normals` (normals accepted but not applied) / `self.outMesh`; read: `self.time` (opt-in, connect `time1.outTime` → `_timeIn`) |
| `mPyDeformer` | read/write: `self.outputGeometry[i]` (mesh `getPoints`/`setPoints`, NURBS `cvPositions`/`setCVPositions`); read: `self.input[i].inputGeometry`, `self.envelope` |
| `mPySkinCluster` | deformer slots + `self.matrix[j].asNumpy()` (joint world), `self.bindPreMatrix[j].asNumpy()` (bind inverse), `self.weightList[i].weights` (sparse) |
| `mPyBlendShape` | deformer slots (`self.outputGeometry[i]`, `self.input[i].inputGeometry`, `self.envelope`) + `self.morphs` (read, `MorphStack` — the target stack as an object, erased at compile time). Underneath it: `self.weight[j]` (read, float, aliased to the target name), the baked `targetOffset` / `targetComponents` / `targetDeltas` tables, and `shapeSlot` (the compute's NAME keys, folded to slots at compile time). `self.targetGeometry[j]` (read, `MFnMesh`) exists for authoring, but reading it at a runtime index blocks the native compile |

> ⚠️ The deformer family has **no** `self.points` / `self.normals` /
> `self.weights` / `self.deformed` schema — that older design was removed.
> Writing `self.deformed = arr` silently stores a user variable and the
> mesh comes out unchanged. Always read/write through
> `self.outputGeometry[i]`.

See [`node_types/`](node_types/) for per-type schema details.

### Setting / getting expressions

```python
wrapper.set_compute_expression(source: str) -> None
wrapper.get_compute_expression() -> str
```

Both delegate to the node's `_computeSource` string plug. Save / load
with the scene as standard `.ma` / `.mb`.

---

## Stored variables (persisted state)

`MPyNode` provides per-instance Python storage (node "variables"). Set /
get via `self.X` in the expression — values persist between ticks and
across file save/load.

```python
# In an expression:
self.last_count = self.last_count + 1     # write -> persisted (seed it first with add_variable)
```

Behind the scenes, stored vars serialize to a string plug so they
round-trip through `.ma`. Picklable types only (`int`, `float`, `str`,
`list`, `dict`, `np.ndarray`, nested combinations thereof).

External API on the wrapper:

```python
wrapper.add_variable(name: str, value=None, persistent: bool = True) -> None
wrapper.set_variable(name: str, value, persistent: bool | None = None) -> None
wrapper.get_variables() -> dict
wrapper.remove_variable(name: str) -> None
wrapper.clear_variables() -> None
```

`add_variable` DECLARES a variable and is persistent by default —
declaring is the deliberate act. `set_variable` only UPDATES a value, so
its `persistent=None` default leaves the variable's Persistent/Temporary
status exactly as it was; a variable it creates from scratch is
Temporary. Writing a value never changes a variable's lifetime unless
you pass `persistent=True` / `False` explicitly (or call
`set_variable_persistent`).

---

## Auto-dirty propagation

Maya's `attributeAffects` is class-init-time only — it cannot be
declared dynamically for attrs added at runtime via `add_input_attr`.
This means without intervention, a connected upstream source (e.g.
a locator's `worldMatrix` flowing into your `matrix` user input)
wouldn't trigger a re-evaluation when the source moves.

The `mpynode._common.auto_dirty` module bridges this gap using
Maya DG callbacks (no scriptJobs):

* `MNodeMessage.addAttributeChangedCallback` on the destination —
  catches direct `setAttr` to your user inputs.
* `MNodeMessage.addNodeDirtyPlugCallback` on each source — catches
  upstream-driven changes.
* `MDGMessage.addConnectionCallback` — installs the source-side
  callback whenever a new connection is made.

These are installed automatically by `add_input_attr` and by each
plug-in's `initializePlugin`. Zero user configuration required.

Result: every user input change — direct or connection-driven —
triggers re-evaluation immediately in interactive Maya. No
keyframes, no timeline tick, no manual envelope touch.

---

## Instrumentation — Log, Watch, Profile

The Node Designer UI's bottom tabs (in order: **Log**, **Watch**,
**Profile**) all hook into the same Python primitives that you can
use programmatically.

### Log

```python
from mpynode._common.log_bus import log
log("hello from my expression", level="info")  # also visible in UI Log tab
```

Used internally by expression failure handling — any uncaught
exception in `set_compute_expression` is logged here.

### Watch

```python
# In an expression, mark a value for the Watch tab:
self.watch("intermediate_distance", dist)
```

The Watch tab shows live values from currently-selected node's last
expression run.

### Profile

The Profile tab shows per-node `cProfile` output for the last
expression run, sorted by cumulative time. Activate via the per-node
`debug_mode` plug or via the UI panel.

---

## Plug-in loading + scene save/load

### Auto-loading

Every `create` / `create_on` calls `mpynode._common.plugin_loader.ensure_loaded`
which loads the right plug-in (`mpynode_api1.py` or `mpynode_api2.py`)
on demand. You don't need to `mc.loadPlugin` manually.

If the plug-in isn't on `MAYA_PLUG_IN_PATH`, you get a clear error
message instead of cryptic `"Unable to create/find dependency node"`.

### Scene save/load

Custom mpynode nodes round-trip through `.ma` / `.mb` like any
other Maya node. Specifically preserved:

* `_computeSource` plug (the user's Python source).
* `_inputAttrs` / `_outputAttrs` JSON (user attr declarations).
* The stored-vars JSON plug (stored variables).
* All standard Maya plugs (envelope, weight maps, connections, etc.).

After file open, the auto-dirty handlers re-attach automatically via
the per-type `MDGMessage.addNodeAddedCallback` (or scene-open sweep
fallback).

---

## Failure mode

**Any uncaught exception in the expression is caught.** The node
returns the rest pose / identity output, and the error is logged to
both `sys.stderr` AND the UI Log tab.

This means a broken expression NEVER crashes Maya — you just see
the rest mesh / identity output, fix the expression, and try again.

```python
d.set_compute_expression("this is not python !!")
# Plane shows rest pose, [mPyDeformer expression error] message in Log tab.
d.set_compute_expression("""
mesh = self.outputGeometry[0]
mesh.setPoints(mesh.getPoints() * 2.0)
""")
# Plane is now scaled 2x. No restart needed.
```

---

## Worked recipes

### Recipe: Lookat constraint

`mPyConstraint` exposes 5 preset inputs via `self.X` (`targetTranslate`,
`targetRotate`, `targetWeight`, `restTranslate`, `restRotate`) and lets
you add your own outputs.

```python
from mpynode import MPyConstraint
import maya.cmds as mc

src  = mc.spaceLocator(name="aimTarget")[0]
rest = mc.spaceLocator(name="aimFrom")[0]
dst  = mc.polyCube(name="aimedCube")[0]

c = MPyConstraint.create(name="myLookAt")
c.add_output_attr("aim_matrix", "matrix")
c.set_compute_expression("""
import numpy as np
my_pos     = self.restTranslate          # preset inputs are self.X (3,)
target_pos = self.targetTranslate

fwd = target_pos - my_pos
fwd = fwd / max(np.linalg.norm(fwd), 1e-9)
up  = np.array([0.0, 1.0, 0.0])
right = np.cross(up, fwd); right = right / max(np.linalg.norm(right), 1e-9)
up    = np.cross(fwd, right)

# Row-major: basis vectors in rows 0..2, translation in row 3.
self.aim_matrix = np.array([
    [right[0], right[1], right[2], 0.0],
    [up[0],    up[1],    up[2],    0.0],
    [fwd[0],   fwd[1],   fwd[2],   0.0],
    [my_pos[0],my_pos[1],my_pos[2],1.0],
], dtype=float)
""")

mc.connectAttr(src  + ".translate", c.get_name() + ".targetTranslate")
mc.connectAttr(rest + ".translate", c.get_name() + ".restTranslate")
mc.connectAttr(c.get_name() + ".aim_matrix", dst + ".offsetParentMatrix", force=True)
```

### Recipe: Procedural skinCluster (LBS)

mPySkinCluster is a genuine skinCluster (registered under
`MPxNode.kSkinCluster`), so Maya's Component Editor "Smooth Skins" tab and
Paint Skin Weights edit its `weightList[v].weights[j]` plug directly — that
plug is the live source of truth. Joints reach the expression through the plug
tree (`self.matrix[j]` / `self.bindPreMatrix[j]`); densify the weights from
the live `self.weightList` plug rather than carrying a separate copy.

```python
from mpynode import MPySkinCluster
import numpy as np, maya.cmds as mc

cyl = mc.polyCylinder(h=4, sx=20, sy=10, axis=(1, 0, 0))[0]
j1  = mc.joint(name="j1")
mc.select(clear=True)
j2 = mc.joint(name="j2", p=(2, 0, 0))

sc = MPySkinCluster.create(mesh=cyl, joints=[j1, j2], name="mySkin")
# Seed the weightList plug (then refine with Paint Skin Weights / Component Editor).
nverts = mc.polyEvaluate(cyl, vertex=True)
for v in range(nverts):
    sc.set_vertex_weight(v, 0, 0.5)
    sc.set_vertex_weight(v, 1, 0.5)

sc.set_compute_expression("""
import numpy as np
mesh = self.outputGeometry[0]
rest = mesh.getPoints()                                       # (N, 3)
N = rest.shape[0]

# Densify the per-influence weights straight from the live weightList plug.
sparse = {}
n_inf = 0
for v, vp in self.weightList:
    for j, w in vp.weights:
        sparse[(int(v), int(j))] = float(w)
        n_inf = max(n_inf, int(j) + 1)
W = np.zeros((N, n_inf), dtype=np.float64)
for (v, j), w in sparse.items():
    W[v, j] = w

joint_mats = np.stack([self.matrix[j].asNumpy() for j in range(n_inf)])         # (J, 4, 4)
bind_mats  = np.stack([self.bindPreMatrix[j].asNumpy() for j in range(n_inf)])  # (J, 4, 4)

M = bind_mats @ joint_mats                                    # (J, 4, 4)
pts_h = np.concatenate([rest, np.ones((N, 1))], axis=1)
deformed_h = np.einsum("vj,jkc,vk->vc", W, M, pts_h)          # Maya row-vector convention
out = rest + float(self.envelope) * (deformed_h[:, :3] - rest)
mesh.setPoints(out)
""")
```

### Recipe: blendShape (envelope + multi-target)

Envelope-only squash:

```python
from mpynode import MPyBlendShape
import maya.cmds as mc

base = mc.polySphere(name="base")[0]
bs   = MPyBlendShape.create(mesh=base, name="myBlend")
bs.set_compute_expression("""
import numpy as np
mesh = self.outputGeometry[0]
rest = mesh.getPoints()
env  = float(self.envelope)
out  = rest.copy()
out[:, 0] *= 1.0 + 0.5 * env   # squash on X/Z, stretch on Y
out[:, 1] *= 1.0 - 0.5 * env
out[:, 2] *= 1.0 + 0.5 * env
mesh.setPoints(out)
""")
mc.setAttr(bs.get_name() + ".envelope", 1.0)
```

Multi-target morph — `out = base + envelope · Σⱼ wⱼ · deltaⱼ`. Each weight is
ALIASED to its target name, so the node drives like a stock blendShape. The
compute reads BAKED sparse deltas, not the live target meshes: that is what Maya
itself stores, and it is the only form that compiles (`nd_lower` rewrites a
mesh-multi element read only at a *literal* index).

You do not touch those tables. `self.morphs` is the whole target stack as one
object — a view over the baked data, with in-betweens and combos already
resolved — so the compute is three lines:

```python
from mpynode import MPyBlendShape

bs = MPyBlendShape.create(mesh=base, name="myMorph")
bs.ensure_delta_attrs()
bs.set_compute_expression("""
mesh = self.outputGeometry[0]
base = mesh.getPoints()

w = self.morphs.weights
mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))
""")
bs.add_target(targetA, "browUp")
bs.add_target(targetB, "mouthOpen")
bs.rebuild()                                # bake deltas + decode names

mc.setAttr(bs.get_name() + ".browUp", 1.0)  # by ALIAS, like Maya
mc.setAttr(bs.get_name() + ".mouthOpen", 0.5)

bs.morphs["browUp"]                     # authoring-side: by name, or .find("brow")
```

Name keys work **inside the compute** too — `self.morphs["browUp"].weight`, or a
constant tuple you loop over. They cannot be looked up live (aliases return empty
on the worker thread `deform()` runs on), so the compiler folds each name to an
integer **slot** and `rebuild()` writes the per-rig `weight[]` index into
`shapeSlot[]`. The key must be a provable constant; a variable a branch
reassigns honest-rejects rather than silently folding to the wrong shape.

`self.morphs` is **erased at compile time** — each member rewrites to a blessed
method that transpiles the same numpy kernel the interpreted node runs, and no
target name reaches the generated C++, so one bundle still serves any rig. See
[`mPyBlendShape.md`](node_types/mPyBlendShape.md) for the recognised surface and
what honest-rejects.

### Recipe: Time-driven transform

```python
from mpynode import MPyTransform
import maya.cmds as mc

t = MPyTransform.create(name="myBobber")
t.add_input_attr("time", "double")
mc.connectAttr("time1.outTime", t.get_name() + ".time", force=True)  # time is opt-in
t.set_compute_expression("""
import numpy as np
y = 1.5 + np.sin(self.time * 0.3) * 2.0
m = np.eye(4)
m[3, 1] = y           # translateY lives in the last row
self.local_matrix = m       # desired LOCAL frame; gates default True
self.apply_rotate = False    # translate only -> keep live rotate/scale
self.apply_scale = False
""")
# Press Play -> the node's translate Y bobs.
```

### Recipe: Generic compute (mPyNode)

```python
from mpynode import MPyNode

n = MPyNode.create(name="myCalc")
n.add_input_attr("a", "double")
n.add_input_attr("b", "double")
n.add_output_attr("sum", "double")
n.add_output_attr("product", "double")
n.set_compute_expression("""
self.sum = self.a + self.b   # read inputs as self.<name>; commit via self.<output>
self.product = self.a * self.b
""")
# Wire mc.setAttr / mc.connectAttr on n.get_name() + ".a" / ".b" / ".sum" / ".product"
```

### Recipe: Custom locator drawing

```python
from mpynode import MPyLocator

loc = MPyLocator.create(name="myCustomGizmo")
loc.set_compute_expression("""
import numpy as np
from mpynode._common.draw.draw_types import DrawMesh, DrawText

# Star polygon centered at origin + a label. The label is written LAST, so it
# draws on top -- authoring order is draw order.
n_points = 5
outer_r, inner_r = 1.0, 0.5
verts = []
for i in range(n_points * 2):
    angle = i * np.pi / n_points
    r = outer_r if i % 2 == 0 else inner_r
    verts.append((r * np.cos(angle), 0.0, r * np.sin(angle)))

self.draw = [
    DrawMesh(np.array(verts, dtype=float),
             np.array([len(verts)], dtype=int),
             np.arange(len(verts), dtype=int),
             uniform_color=(0.0, 1.0, 0.5, 1.0)),      # uniform fill
    DrawText("hello", position=(0.0, 1.2, 0.0), color=(1.0, 1.0, 1.0)),
]
""")
```

---

## Troubleshooting / FAQ

### "Unable to create/find dependency node"

The plug-in isn't loaded. Every `create` / `create_on` should
auto-load it via `_common.plugin_loader.ensure_loaded`. If you see
this error, check:

* Is `MAYA_PLUG_IN_PATH` set? The userSetup.py 
  directory handles this automatically.
* Are you constructing a wrapper from an existing-node name
  (`MPyDeformer("foo")`) without the plug-in loaded? Use `create`
  / `create_on` instead — they auto-load.

### Moving a locator (connected to my user input) doesn't update my deformer

The auto-dirty system installs DG callbacks on the SOURCE side that
bridge to your destination. If you STILL see this, the most likely
cause is the plug-in didn't fully initialize (check the Output Window
for `[auto_dirty]` errors at plug-in load).

### My expression errors silently

Look in the **Log** tab (the leftmost bottom tab). All
expression exceptions are caught + logged there (also to
`sys.stderr` for mayapy / batch contexts).

### How do I see what's in `self.X` at runtime?

In the expression:

```python
self.watch("my_intermediate", value)
```

Then check the **Watch** tab in the UI. Or just `print(value)` —
the output goes to `sys.stdout` and the Log tab.

### How do I profile slow expressions?

Toggle `debug_mode` to `2` (cProfile) on the node, then trigger
re-evaluation. The **Profile** tab shows per-line cumulative time
sorted descending.

```python
mc.setAttr(d.get_name() + ".debug_mode", 2)
```

### Can I save a Python object in stored vars?

Anything picklable. Numpy arrays, dicts, lists, primitives, nested
combinations — all fine. Non-picklable types (e.g. open file
handles, Maya MObjects) raise on save.

Geometry wrappers (`Mesh`, `NurbsCurve`, `NurbsSurface`, `UVSet`) and every
`Draw*` item are picklable too.

### Can I move a mesh or a drawing outside Maya?

Yes — both pickle and JSON.

```python
import json, pickle

mesh = self.inMesh                 # attached: live DATA + MFnMesh
blob = pickle.dumps(mesh)          # -> a DETACHED value mesh (arrays only)
text = json.dumps(mesh.to_json())  # -> plain JSON: no numpy, no Maya types
```

Reading back:

```python
from mpynode._api2.geometry import geometry_from_json
from mpynode._common.draw.draw_types import draw_from_json

mesh         = pickle.loads(blob)          # or geometry_from_json(text)
self.outMesh = mesh                        # still assignable to an output plug
self.draw    = draw_from_json(saved_text)  # a whole drawing, in authoring order
```

An **attached** wrapper holds a live geometry DATA `MObject` and an `MFn*`
function set, neither of which can be serialized. Both formats therefore
materialize every channel first and hand back a **detached** value object —
exactly what `copy()` returns, and still valid to assign to an output. Points,
counts, indices, normals, colors, component tags and UV sets all survive; the
`.fn` link does not.

JSON is the portable form: the payload is text with a `"type"` tag, so a plain
Python process with no Maya can read it.

### Does this work with referencing / file save?

Yes. All custom plugs (`_computeSource`, `_inputAttrs`, `_outputAttrs`,
and the stored-vars plug) are standard string attrs that round-trip
through `.ma` / `.mb`. After file open, auto-dirty handlers
re-attach automatically.

### What if I want to disable auto-dirty for a specific node?

You don't normally need to. The auto-dirty handlers only fire when
a user input attr changes value — they impose no overhead during
normal evaluation. If you have an edge case, contact the
maintainers.

### Where are the per-node design docs?

Under [`node_types/`](node_types/) — one markdown per node type
with the schema, plug list, MTypeId, and design notes.

---

## See also

* [`node_types/mPyDeformer.md`](node_types/mPyDeformer.md) — the
  deformer-family walkthrough (5 steps + worked example + family table),
  [`node_types/mPySkinCluster.md`](node_types/mPySkinCluster.md),
  [`node_types/mPyBlendShape.md`](node_types/mPyBlendShape.md),
  [`node_types/mPyTransform.md`](node_types/mPyTransform.md),
  [`node_types/mPyMesh.md`](node_types/mPyMesh.md),
  [`node_types/mPyFile.md`](node_types/mPyFile.md),
  [`node_types/mPyIkSolver.md`](node_types/mPyIkSolver.md),
  [`node_types/mPyNode.md`](node_types/mPyNode.md),
  [`node_types/mPyConstraint.md`](node_types/mPyConstraint.md),
  [`node_types/mPyLocator.md`](node_types/mPyLocator.md),
  [`node_types/mPyNurbsCurve.md`](node_types/mPyNurbsCurve.md),
  [`node_types/mPyNurbsSurface.md`](node_types/mPyNurbsSurface.md)
  — per-type design notes.
* [`node_types/_input_type_contract.md`](node_types/_input_type_contract.md)
  — the full attr-type → Python value contract.
* `scripts/mpynode/_demos/build_templates.py` — the canonical
  template regenerator (browse the bundled results via **New from
  Template** in the Node Designer).
