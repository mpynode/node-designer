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

A generic `mPyNode` that multiplies two float inputs. We declare inputs `a`/`b` and output `c` through the wrapper, set a one-line Compute expression (inputs read as `self.a`/`self.b`, the output committed via `self.c =`), then drive the inputs and read back the computed result headless.

```python
import maya.cmds as mc
from mpynode import MPyNode

mc.file(new=True, force=True)

# Generic compute node: c = a * b.
node = MPyNode.create(name="multiply")
node.add_input_attr("a", "float")
node.add_input_attr("b", "float")
node.add_output_attr("c", "float")
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

`float`, `double`, `int`, `bool`, `angle` (doubleAngle, radians), `vector` (double3), `euler` (double3 of doubleAngle children, radians), `matrix` (4×4), `string`, `enum` (requires `enum_names`), `time` (auto-connects to `time1.outTime`), `python` (pickled object), `hex` (hex-encoded string), `mesh`, `nurbsCurve`, `nurbsSurface` — 16 types total. All support `is_array=True` for multi plugs.

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
