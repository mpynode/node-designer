# Input type contract per node

This document specifies the **types** of every variable available in a
node's user expression namespace. Use it as your reference when writing
expressions.

**Access is `self.X` only.** Every plug — user-added inputs and outputs
(`add_input_attr` / `add_output_attr`), preset inputs (mPyConstraint), the IK
context (mPyIkSolver), the locator draw context (mPyLocator), stored
variables, and pre-seeded outputs — is reachable **only** via `self.`, never
as a bare name. Read an input with `self.<name>`; commit an output with
`self.<name> = ...`. (Bare names defined in the **Init tab** — imports and
helpers — are still bare globals in the Expression; see below.)

Because attributes are accessed through `self`, attribute names must be valid
Python identifiers and must not be Python keywords. Names that shadow a
builtin (e.g. `min`, `type`) are fine — `self.min` is unambiguous.

**Numpy rule:** position / vector (double3) / euler / quaternion / color /
uv (float2) inputs and numeric array inputs come through as `numpy.ndarray`.
A matrix input comes through as a `MatrixView`, which is numpy-transparent
(`np.asarray(m)` → `(4, 4)`, `m @ x`, `m.shape`, indexing) and also offers
`.asNumpy()` / `.translation()` / `.rotation()` / `.scale()` /
`.asMatrix()`; a matrix array as a `MatrixArrayView` (`np.asarray` →
`(n, 4, 4)`). String / hex / pickle / geometry arrays are Python lists.
Scalars (`float`, `int`, `bool`, `str`) stay Python primitives.

**Two names per type.** Each attr type has the name the Add Attribute
dropdown shows and a stored name, Maya's where that alone describes the plug;
they differ for `float64` / `double`, `int` / `long`, `angle` /
`doubleAngle`, `distance` / `doubleLinear`, `float32` / `float`, `vector` /
`double3` and `uv` / `float2`. `add_input_attr` / `add_output_attr` take
either (Maya's `double4` / `float3` too, for `quaternion` / `color`) and store
the stored name, which is what files, scene attr maps, `get_input_attr_map()`
and errors report. Both lines below make the same kind of plug, and both read
as numpy `(3,)`:

```python
n.add_input_attr("aim", "vector")  # the dropdown's name
n.add_input_attr("up", "double3")  # the stored name
```

The pickled-object type is `pickle`; the old name `python` is rejected in new
code and `.mpn` files, while a scene that stored it keeps computing. The
tables below name a type the dropdown's way first, with the stored name in
brackets where it differs.

## Modules in the namespace

**No modules are auto-injected.** Only Python `__builtins__` (`len`,
`range`, `dict`, …) is guaranteed. To use `math` / `numpy` / `maya.cmds`
you must `import` them in the expression itself, **or** import them / define
helpers in the **Init tab** — names defined in Init become bare globals in
the Expression (the per-node Init namespace is merged in first).

## Per-node injected variables

### mPyNode

User-added inputs only. Each is read as `self.<name>`. In the dropdown's
order and groups; **Dropdown** and **Description** are the dropdown's two
columns, word for word:

| Dropdown | Description | Stored | Value type |
|---|---|---|---|
| **Numbers** | | | |
| `float64` | double (64-bit) | `double` | `float` |
| `int` | long | `long` | `int` |
| `bool` | bool (on / off) | `bool` | `bool` |
| `angle` | doubleAngle (radians) | `doubleAngle` | `float` (radians) |
| `distance` | doubleLinear (cm) | `doubleLinear` | `float` (cm) |
| `float32` | float (32-bit) | `float` | `float` |
| **Vectors, compounds, matrix** | | | |
| `position` | double3 of doubleLinear (cm) | `position` | `numpy.ndarray (3,)` float64 (cm) |
| `vector` | double3 (no unit) | `double3` | `numpy.ndarray (3,)` float64 (no unit) |
| `euler` | double3 of doubleAngle (radians) | `euler` | `numpy.ndarray (3,)` float64 (radians) |
| `quaternion` | double4 (X/Y/Z/W) | `quaternion` | `numpy.ndarray (4,)` float64 (X/Y/Z/W; W defaults to 1, so `[0, 0, 0, 1]` until set) |
| `matrix` | matrix (4x4 doubles) | `matrix` | `MatrixView` (numpy-transparent → `(4, 4)`; `.asNumpy()` / `.translation()` / …; identity until set) |
| `color` | float3 (colour) | `color` | `numpy.ndarray (3,)` float64 (R/G/B; `usedAsColor`) |
| `uv` | float2 (U/V) | `float2` | `numpy.ndarray (2,)` float64 (U/V) |
| **Text and data** | | | |
| `string` | string (text) | `string` | `str` |
| `enum` | enum (named choices, default False/True) | `enum` | `int` (an `EnumInt`; `.name()` gives the field label) |
| `hex` | string (stored as UTF-8 hex) | `hex` | `str` (hex-decoded text) |
| `pickle` | string (pickled data, C++ unsupported) | `pickle` | arbitrary unpickled object (trust-gated; `None` in an untrusted scene) |
| **Geometry** | | | |
| `mesh` | mesh (code gets a Mesh object) | `mesh` | `Mesh`, which passes any `MFnMesh` method through (or `None` if unconnected) |
| `nurbsCurve` | nurbsCurve (code gets a NurbsCurve object) | `nurbsCurve` | `NurbsCurve`, which passes any `MFnNurbsCurve` method through (or `None` if unconnected) |
| `nurbsSurface` | nurbsSurface (code gets a NurbsSurface object) | `nurbsSurface` | `NurbsSurface`, which passes any `MFnNurbsSurface` method through (or `None` if unconnected) |
| **Time** | | | |
| `time` | time (frames) | `time` | `float` (the current frame, in the UI time unit) |

The unit types read Maya's internal units whatever the scene's UI units:
radians for `angle` (`doubleAngle`) / `euler`, centimetres for `distance`
(`doubleLinear`) / `position` (at linear unit m, a `translate` of 1.5 reads
150.0 through a `position`). A `vector` (`double3`) has no unit: wired from
`translate` in a non-cm scene, Maya puts a `unitConversion` node in front of
it and it reads UI units.

**Array inputs (`is_array=True`):**

| Element type | Array value |
|---|---|
| numeric scalar (`float64` (`double`) / `int` (`long`) / `bool` / `angle` (`doubleAngle`) / `distance` (`doubleLinear`) / `float32` (`float`) / `enum` / `time`) | `numpy.ndarray (n,)` of the matching dtype (float64 / int64 / bool) |
| `position` / `vector` (`double3`) / `euler` / `color` | `numpy.ndarray (n, 3)` float64 |
| `quaternion` | `numpy.ndarray (n, 4)` float64 |
| `matrix` | `MatrixArrayView` (`np.asarray` → `(n, 4, 4)`) |
| `uv` (`float2`) | `numpy.ndarray (n, 2)` float64 |
| `string` / `hex` / `pickle` / `mesh` / `nurbsCurve` / `nurbsSurface` | Python `list` |

Stored variables are accessible via `self.<name>` (e.g. `self.cached_table`),
like every other plug. Their type is whatever the user assigned, preserved
across compute calls via base64-pickle. (Names defined in the Init tab, by
contrast, DO become bare globals.)

### mPyConstraint

Same as mPyNode for user-added inputs (read as `self.<name>`), **plus** 5
preset inputs reachable via `self.X`:

| Name | Type | Source |
|---|---|---|
| `self.targetTranslate` | `numpy.ndarray (3,)` | preset plug — a raw Maya `float3`, no unit; a `transform.translate` connection made in a non-cm scene goes through a `unitConversion` node and delivers the UI linear unit |
| `self.targetRotate` | `numpy.ndarray (3,)` | preset plug — a raw Maya `float3`, no unit; a `transform.rotate` connection goes through a `unitConversion` node and delivers the UI angle unit (degrees by default), not radians |
| `self.targetWeight` | `float` | preset plug (a `float`, default `1.0`) |
| `self.restTranslate` | `numpy.ndarray (3,)` | preset plug — a raw Maya `float3` (see `targetTranslate`) |
| `self.restRotate` | `numpy.ndarray (3,)` | preset plug — a raw Maya `float3` (see `targetRotate`) |

The presets are 32-bit plugs; they still read as float64 arrays.

```python
# Weighted blend between target and rest — numpy makes this a one-liner.
constrained_pos = self.targetTranslate * self.targetWeight \
                  + self.restTranslate * (1 - self.targetWeight)
```

### mPyFile

User-added inputs follow the mPyNode tables, except in the **Compute** tab.
Compute reads them off the datablock (safe on the Hypershade swatch / Arnold
worker thread), and three types arrive differently there:

| Attr type | In mPyFile's Compute |
|---|---|
| `uv` (`float2`) | Python `list` `[u, v]`; an array is a list of `[u, v]` lists |
| `hex` | the stored hex string (`"48 69"`), not decoded |
| `pickle` | the stored base64 string, not unpickled |

### mPyIkSolver

Synthetic context populated by the bridge from the connected `ikHandle`,
reachable **only via `self.X`** (the exec namespace holds only
`__builtins__`, `self`, and a `node` proxy):

| Name | Type | Notes |
|---|---|---|
| `self.joints` | `list[dict]` | One dict per joint in the chain |
| `self.joints[i]["name"]` | `str` | Joint's DAG name |
| `self.joints[i]["world_position"]` | `numpy.ndarray (3,)` | Joint's world position |
| `self.joints[i]["rotation"]` | `numpy.ndarray (3,)` | Joint's local rotation (Euler degrees) |
| `self.joints[i]["matrix"]` | `MatrixView (4, 4)` | Joint's local (parent-relative) rest frame (row-vector) |
| `self.joints[i]["world_matrix"]` | `MatrixView (4, 4)` | Joint's rest **world** frame (incl. bind offset; row-vector) |
| `self.end_effector` | `numpy.ndarray (3,)` | IK handle's world position (the puppet target) |
| `self.pole_vector` | `numpy.ndarray (3,)` | from `handle.poleVector` |
| `self.twist` | `float` | from `handle.twist` |
| `MatrixView` | class | Matrix builder (setRotation/…, radians, chainable) injected into the namespace |
| `self.local_matrices` (output) | `list[4×4 or None]` | Per-joint desired **LOCAL** (parent-relative) matrix; applied via `offsetParentMatrix` (channel-gated). `None` slots follow rest |
| `self.world_matrices` (output) | `list[4×4 or None]` | Per-joint desired **WORLD** (absolute) matrix; per-joint dispatch WORLD > LOCAL > rest |
| `self.apply_rotate` / `self.apply_translate` / `self.apply_scale` (output) | `bool` or `list[bool]` | Channel gates (default `True`/`False`/`False`); scalar broadcasts, list is per-joint |

### mPyLocator

Per-frame draw context (the draw is per-frame, not DG-data-driven),
reachable via `self.X`:

| Name | Type | Notes |
|---|---|---|
| `self.time` | `float` | Current Maya **frame** (a `TimeFloat`; `.fps` / `.asSeconds()`) |
| `self.selected` / `self.is_lead` | `bool` | Viewport selection state |
| `self.hovered` | `bool` | Cursor-over-locator state |
| `self.selection_color` | tuple `(r, g, b, a)` | Active selection colour |
| `self.draw` (output) | `DrawItem`, a (nested) list of them, or `None` | The whole drawing, in authoring order; assign to render |
| `self.auto_highlight` (output) | `bool` | Override the automatic selection tint (default `True`) |
| `self.auto_refresh` (output) | `bool` | Truthy enables a fixed 30 fps redraw timer so animations advance between DG changes (default `False`) |
| `self.precise_hover` (output) | `bool` | Opt into precise ray-vs-triangle hover instead of bounding-box (default `False`) |

User-added INPUT plugs follow the mPyNode table. Note: `mPyLocator` does NOT
support DG user OUTPUTS (MPxLocatorNode doesn't dispatch `compute()` for
runtime-added outputs — see [`mPyLocator.md`](mPyLocator.md)).

## Output types

How an output write is coerced depends on the output's type:

| Output type | What you assign | How it's written |
|---|---|---|
| `float64` (`double`) / `float32` (`float`) | numeric | `float()` → `setDouble` / `setFloat` |
| `int` (`long`) / `enum` | numeric | `int()` → `setInt` |
| `bool` | bool/numeric | `bool()` → `setBool` |
| `angle` (`doubleAngle`) / `distance` (`doubleLinear`) | numeric, in radians / cm | `float()` → `setDouble` |
| `position` / `vector` (`double3`) / `euler` | `[x, y, z]` (list, tuple, OR numpy `(3,)`); radians for `euler`, cm for `position` | `set3Double` on the double3 plug |
| `quaternion` | `[x, y, z, w]` (list, tuple, OR numpy `(4,)`) | `set4Double` on the numeric double4 |
| `matrix` | `MMatrix` / `MTransformationMatrix` / flat-16 / `(4, 4)` / `(3, 3)` | `_coerce_to_4x4_numpy()` → `setMMatrix` on the `-at matrix` plug |
| `color` | `[r, g, b]` (list, tuple, OR numpy `(3,)`) | `set3Float` on the float3 (R/G/B) plug |
| `uv` (`float2`) | `[u, v]` (list, tuple, OR numpy `(2,)`) | `set2Float` on the float2 (U/V) plug |
| `string` / `hex` / `pickle` | str / str / any picklable | `setString` of the text / its UTF-8 hex / its pickle in base64 |
| `mesh` / `nurbsCurve` / `nurbsSurface` | a `Mesh` / `NurbsCurve` / `NurbsSurface`, an arrays bucket, or an `MFn*Data` MObject | `setMObject` |
| `time` | a frame | `setMTime` in the UI time unit |
| `vector` (`double3`) array | list/array of `(3,)` items | array of double3 plugs |

The numeric compounds (`position` / `vector` / `euler` / `quaternion` /
`color` / `uv`) flatten what you assign with
`np.asarray(..., dtype=float64).flatten()` and zero-pad a short value before
the one `set<N><Type>` call; scalars use `float()`/`int()`/`bool()`, matrices
use `_coerce_to_4x4_numpy()`, and string/hex/pickle/time use their own
type-specific encoders.

A scene saved before 2026-10 can carry a typed `-dt matrix` plug or a generic
4-child compound quaternion. Both still read; their writes take
`setMObject(MFnMatrixData)` and per-child `setDouble`, picked from the plug's
real kind (the wrong matrix call crashes Maya). Its attr maps can also name
`int` / `vector` / `angle` (the stored names before the 2026-10-02 rename) or
`python`: every reader translates them to `long` / `double3` / `doubleAngle` /
`pickle`, so the node computes as before. A re-save keeps the old names in the
map until an attribute edit on that side rewrites it (inputs and outputs
separately).

These are the writes on the API 2.0 nodes (mPyNode, mPyConstraint, mPyFile,
mPyMesh, mPyNurbsCurve, mPyNurbsSurface). The API 1.0 nodes pick the call
from the plug's kind, not the attr type, so a `hex` or `pickle` output gets
plain `str(value)`, with no hex encoding and no pickle. Beyond that:

* mPyDeformer, mPyBlendShape and mPySkinCluster write through the datablock.
  A `time` output is taken as SECONDS there: `10.0` at 30 fps lands as frame
  300.
* mPyTransform and mPyIkSolver write through `setAttr`. A `time` output is a
  frame in the UI time unit, and a `distance` (`doubleLinear`) / `position`
  value is converted from cm. An `angle` (`doubleAngle`) / `euler` value is
  NOT converted from radians: it lands in the UI angle unit, so `math.pi / 2`
  reads back as 1.5708°, not 90°.

## Why this matters

Originally, `targetTranslate` in mPyConstraint was a Python list. Users
wrote things like:

```python
# OLD (lists — manual zip/loop required)
constrained_pos = [
    self.targetTranslate[0] * self.targetWeight + self.restTranslate[0] * (1 - self.targetWeight),
    self.targetTranslate[1] * self.targetWeight + self.restTranslate[1] * (1 - self.targetWeight),
    self.targetTranslate[2] * self.targetWeight + self.restTranslate[2] * (1 - self.targetWeight),
]
```

After the standardization:

```python
# NEW (numpy — vector math is built in)
constrained_pos = self.targetTranslate * self.targetWeight + self.restTranslate * (1 - self.targetWeight)
```

Every node's vector inputs follow the same numpy contract now.

## Design rationale: numpy for vectors, Python for scalars

- **Vectors and arrays** benefit massively from numpy: element-wise ops,
  broadcasting, dot/cross products, slicing.
- **Scalars** gain nothing from numpy. `np.float64` is heavier than Python
  `float` and sometimes surprises users (e.g., `repr` shows
  `np.float64(1.5)` instead of `1.5`). Python primitives mix cleanly with
  numpy when needed.
- **Strings and bools** never make sense as numpy.

This split mirrors how scientific Python codebases typically work:
numpy/pandas/torch stay numeric; metadata stays Python.
