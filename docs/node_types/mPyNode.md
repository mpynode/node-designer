# mPyNode

**Plugin:** `mpynode_api2` · **Inherits:** `MPxNode` (API 2.0) · **Type ID:** `0x00135700`

Generic compute node. Define your own inputs + outputs + write Python.

---

## Use cases

- Math nodes (matrix multiply, vector blend, custom interpolation)
- Driven keys with arbitrary logic
- Anything you'd build with `expression` but want as a real DG node

---

## Example

A generic `mPyNode` that multiplies two double inputs. We declare inputs `a`/`b` and output `c` through the wrapper, set a one-line Compute expression (inputs read as `self.a`/`self.b`, the output committed via `self.c =`), then drive the inputs and read back the computed result headless.

```python
import maya.cmds as mc
from mpynode import MPyNode

mc.file(new=True, force=True)

# Generic compute node: c = a * b.
node = MPyNode.create(name="multiply")
node.add_input_attr("a", "double")
node.add_input_attr("b", "double")
node.add_output_attr("c", "double")
# Inputs read as self.a / self.b; the output is committed via self.c.
node.set_compute_expression("self.c = self.a * self.b")

name = node.get_name()
mc.setAttr(name + ".a", 7.0)
mc.setAttr(name + ".b", 3.0)

# Force evaluation by querying the output plug.
result = mc.getAttr(name + ".c")
assert abs(result - 21.0) < 1e-6, "expected 21.0, got %r" % result
print("mPyNode computed c =", result)
```

---

## Supported attribute types

21 types, in the Add Attribute dropdown's order and groups. **Dropdown** and **Description** are what the dropdown shows; **Stored** is the name the node, its files and `get_input_attr_map()` carry. All support `is_array=True` for multi plugs.

| Dropdown | Description | Stored | Notes |
|---|---|---|---|
| **Numbers** | | | |
| `float64` | double (64-bit) | `double` | the dialog's default; Maya's own "Float" |
| `int` | long | `long` | |
| `bool` | bool (on / off) | `bool` | |
| `angle` | doubleAngle (radians) | `doubleAngle` | radians |
| `distance` | doubleLinear (cm) | `doubleLinear` | a distance, like `translateX`; cm |
| `float32` | float (32-bit) | `float` | only to match a 32-bit plug |
| **Vectors, compounds, matrix** | | | |
| `position` | double3 of doubleLinear (cm) | `position` | doubleLinear children, like `translate`; cm |
| `vector` | double3 (no unit) | `double3` | a direction or scale |
| `euler` | double3 of doubleAngle (radians) | `euler` | doubleAngle children, like `rotate`; radians |
| `quaternion` | double4 (X/Y/Z/W) | `quaternion` | W defaults to 1 |
| `matrix` | matrix (4x4 doubles) | `matrix` | `-at matrix`; identity until set |
| `color` | float3 (colour) | `color` | `usedAsColor` |
| `uv` | float2 (U/V) | `float2` | |
| **Text and data** | | | |
| `string` | string (text) | `string` | |
| `enum` | enum (named choices, default False/True) | `enum` | requires `enum_names` |
| `hex` | string (stored as UTF-8 hex) | `hex` | write plain text, read decoded |
| `pickle` | string (pickled data, C++ unsupported) | `pickle` | any picklable object; trust-gated |
| **Geometry** | | | |
| `mesh` | mesh (code gets a Mesh object) | `mesh` | |
| `nurbsCurve` | nurbsCurve (code gets a NurbsCurve object) | `nurbsCurve` | |
| `nurbsSurface` | nurbsSurface (code gets a NurbsSurface object) | `nurbsSurface` | |
| **Time** | | | |
| `time` | time (frames) | `time` | auto-connects to `time1.outTime` |

`add_input_attr` / `add_output_attr` take either name (and Maya's `double4` / `float3` for `quaternion` / `color`) and translate it before anything is created, so these two lines make the same kind of plug:

```python
node.add_input_attr("aim", "vector")  # the dropdown's name, stored as double3
node.add_input_attr("up", "double3")  # the stored name
```

Files, scene attr maps, `get_input_attr_map()` and errors report the stored name; the dialog, the Attributes list and the assistant's chat line show the dropdown's. The unit types read and write Maya's internal units (radians, cm) whatever the scene's UI units.

`python` is renamed `pickle`: new code and `.mpn` files that name `python` are rejected with the hint, while a scene that stored it keeps computing. Scenes that stored `int` / `vector` / `angle` (the stored names before the 2026-10-02 rename) load again; their attr maps keep the old names through a re-save, which is harmless because every reader translates them. v1 scenes map their names on upgrade. The full value contract is in [`_input_type_contract.md`](_input_type_contract.md).

---

## Expression namespace

- All declared INPUT attrs are read as `self.<name>` (e.g. `self.a`, `self.b`). Attr names must be valid, non-keyword Python identifiers (builtin-shadowing names like `min`/`type` are fine — `self.min` is unambiguous).
- All declared OUTPUT attrs are pre-seeded on `self.<name>` (e.g. `self.c == 0.0`, matrices = identity, arrays = a pre-sized buffer). Commit an output via `self.c = ...`.
- All STORED VARS via `self.<name>` (see "Stored variables").
- Only Python `__builtins__` are auto-injected. **No modules are auto-imported** — `import math` / `import numpy as np` / `import maya.cmds as cmds` yourself in the expression (or define them in the Init tab, where they become bare globals).

---

## Stored variables

```python
n.add_variable("counter", 0)
n.set_compute_expression("self.counter = self.counter + 1")
```

Each compute reads `self.counter` from the stored vars, executes, and writes the mutated value back. Persists across compute calls AND across `.ma` save/load.

---

## Implementation notes

- `setDependentsDirty(plug, affected_plugs)` — when ANY user input or the expression attr changes, mark all USER outputs dirty. Required because USER outputs are added dynamically (per-instance), so static `attributeAffects` can't be declared in `nodeInitializer`.
- `setInternalValue(plug, data_handle)` — when the `_computeSource` (expression) plug changes, recompile `_expr_code` immediately (via `type(self)._expression_attr` so subclasses like mPyConstraint inherit correctly). It also invalidates the cached `setDependentsDirty` affects schema when the `_inputAttrs` / `_outputAttrs` plugs change, so dynamically added/removed user attrs are picked up.
- Vector inputs: child plug dirty events strip XYZ suffix to map back to parent name in the input map.

---

## See also

- `_api2/_mpy_node.py` — the MPxNode subclass
- `wrappers/_mpy_node.py` — user-facing wrapper
