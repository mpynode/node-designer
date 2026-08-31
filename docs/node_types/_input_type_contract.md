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

**Numpy rule:** vector / euler / array inputs come through as
`numpy.ndarray`. A matrix input comes through as a `MatrixView`, which is
numpy-transparent (`np.asarray(m)` → `(4, 4)`, `m @ x`, `m.shape`,
indexing) and also offers `.asNumpy()` / `.translation()` / `.rotation()` /
`.scale()` / `.asMatrix()`. Scalars (`float`, `int`, `bool`, `str`) stay
Python primitives.

## Modules in the namespace

**No modules are auto-injected.** Only Python `__builtins__` (`len`,
`range`, `dict`, …) is guaranteed. To use `math` / `numpy` / `maya.cmds`
you must `import` them in the expression itself, **or** import them / define
helpers in the **Init tab** — names defined in Init become bare globals in
the Expression (the per-node Init namespace is merged in first).

## Per-node injected variables

### mPyNode

User-added inputs only. Each is read as `self.<name>`:

| Attr type | Value type |
|---|---|
| `float` / `double` | `float` |
| `int` | `int` |
| `bool` | `bool` |
| `angle` | `float` (radians) |
| `vector` | `numpy.ndarray (3,)` float64 |
| `euler` | `numpy.ndarray (3,)` float64 (radians) |
| `color` | `numpy.ndarray (3,)` float64 (R/G/B; `usedAsColor`) |
| `quaternion` | `numpy.ndarray (4,)` float64 (X/Y/Z/W; default identity `[0, 0, 0, 1]`) |
| `matrix` | `MatrixView` (numpy-transparent → `(4, 4)`; `.asNumpy()` / `.translation()` / …) |
| `string` | `str` |
| `enum` | `int` (an `EnumInt`; `.name()` gives the field label) |
| `time` | `float` (a `TimeFloat`, current FRAME; `.fps` / `.asSeconds()`) |
| `python` | arbitrary unpickled object (trust-gated; `None` in an untrusted scene) |
| `hex` | `str` (hex-decoded text) |
| `mesh` / `nurbsCurve` / `nurbsSurface` | `MFnMesh` / `MFnNurbsCurve` / `MFnNurbsSurface` (or `None` if unconnected) |

**Array inputs (`is_array=True`):**

| Element type | Array value |
|---|---|
| numeric scalar (`float`/`double`/`int`/`bool`/`angle`/`time`) | `numpy.ndarray (n,)` of the matching dtype (float64 / int64 / bool) |
| `vector` / `euler` / `color` | `numpy.ndarray (n, 3)` float64 |
| `quaternion` | `numpy.ndarray (n, 4)` float64 |
| `matrix` | `MatrixArrayView` (`np.asarray` → `(n, 4, 4)`) |
| `string` / `python` / `mesh` / `nurbsCurve` / `nurbsSurface` | Python `list` |

Stored variables are accessible via `self.<name>` (e.g. `self.cached_table`),
like every other plug. Their type is whatever the user assigned, preserved
across compute calls via base64-pickle. (Names defined in the Init tab, by
contrast, DO become bare globals.)

### mPyConstraint

Same as mPyNode for user-added inputs (read as `self.<name>`), **plus** 5
preset inputs reachable via `self.X`:

| Name | Type | Source |
|---|---|---|
| `self.targetTranslate` | `numpy.ndarray (3,)` | preset plug |
| `self.targetRotate` | `numpy.ndarray (3,)` | preset plug — raw double3; units follow the connected source (a `transform.rotate` connection delivers radians, not degrees) |
| `self.targetWeight` | `float` | preset plug |
| `self.restTranslate` | `numpy.ndarray (3,)` | preset plug |
| `self.restRotate` | `numpy.ndarray (3,)` | preset plug — raw double3 (see `targetRotate`) |

```python
# Weighted blend between target and rest — numpy makes this a one-liner.
constrained_pos = self.targetTranslate * self.targetWeight \
                  + self.restTranslate * (1 - self.targetWeight)
```

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
| `float` / `double` | numeric | `float()` on the plug |
| `int` | numeric | `int()` |
| `bool` | bool/numeric | `bool()` |
| `vector` / `euler` | `[x, y, z]` (list, tuple, OR numpy `(3,)`) | `np.asarray(..., dtype=float64).flatten()` → double3 plug |
| `color` | `[r, g, b]` (list, tuple, OR numpy `(3,)`) | `set3Float` on the float3 (R/G/B) plug |
| `quaternion` | `[x, y, z, w]` (list, tuple, OR numpy `(4,)`) | per-child `setDouble` on the 4-double compound |
| `matrix` | `MMatrix` / `MTransformationMatrix` / flat-16 / `(4, 4)` / `(3, 3)` | `_coerce_to_4x4_numpy()` → matrix plug |
| `string` / `hex` | str | type-specific encoder |
| `vector` array | list/array of `(3,)` items | array of double3 plugs |

Only **vector/euler** outputs use the
`np.asarray(..., dtype=float64).flatten()` path; scalars use
`float()`/`int()`/`bool()`, matrices use `_coerce_to_4x4_numpy()`, and
string/hex/python/time use their own type-specific encoders.

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
