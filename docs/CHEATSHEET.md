# MPyNode — Authoring Cheat Sheet

`self.X` is the whole runtime contract; the wrapper class is the whole scripting contract.

```python
from mpynode import MPyNode, MPyDeformer, MPyMesh, MPyLocator   # all 12 re-exported
import maya.cmds as mc
```

## 1. Create / wrap

| Node type | Wrapper | Create |
|---|---|---|
| `mPyNode`, `mPyConstraint`, `mPyLocator`, `mPyFile` | `MPyNode`, `MPyConstraint`, `MPyLocator`, `MPyFile` | `MPyX.create(name="myNode")` |
| `mPyMesh`, `mPyNurbsCurve`, `mPyNurbsSurface` | `MPyMesh`, `MPyNurbsCurve`, `MPyNurbsSurface` | `MPyX.create(name="myGeo")` |
| `mPyTransform` | `MPyTransform` | `MPyTransform.create(name="myXform")` |
| `mPyDeformer` | `MPyDeformer` | `MPyDeformer.create_on("pPlane1", name="myDef")` |
| `mPySkinCluster` | `MPySkinCluster` | `MPySkinCluster.create(mesh="body", joints=["j1","j2"])` |
| `mPyBlendShape` | `MPyBlendShape` | `MPyBlendShape.create(mesh="base", targets=["a","b"])` |
| `mPyIkSolver` | `MPyIkSolver` | `MPyIkSolver.find_solver()` — first solver in the scene, else `create()` |

```python
n = MPyNode.create(name="myNode")  # plug-in auto-loads; new node is selected
n = MPyNode("existingNode")        # wrap a node already in the scene
n.get_name()                              # -> Maya node name
MPyNode.create(name=None)                 # name DERIVED from the Class (camelCase)
MPyNode.create(skip_selection=True)       # do not disturb the active selection
MPyNode.build(name="myNode", setup=True)  # create + seed methods + run setup()
```

`create()` is the primitive (bare, unseeded); `build()` is the orchestrated path.

## 2. Adding attributes

```python
n.add_input_attr("amp", "float", min_value=0.0, max_value=10.0, default_value=1.0)
n.add_input_attr("mode", "enum", enum_names=["off", "add", "mult"])
n.add_input_attr("points", "vector", is_array=True)
n.add_input_attr("table", "double", is_array=True, packed=True)   # bulk data
n.add_output_attr("result", "vector")
n.add_output_attr("outs", "float", is_array=True)
```

### Every `attr_type` (19)

| `attr_type` | Maya plug | `self.X` reads as | `is_array=True` reads as |
|---|---|---|---|
| `float` | `at="float"` | `float` | `ndarray (n,)` float64 |
| `double` | `at="double"` | `float` | `ndarray (n,)` float64 |
| `int` | `at="long"` | `int` | `ndarray (n,)` int64 |
| `bool` | `at="bool"` | `bool` | `ndarray (n,)` bool |
| `angle` | `at="doubleAngle"` | `float` (RADIANS) | `ndarray (n,)` float64 |
| `time` | `at="time"` | `TimeFloat` = FRAME (`.fps`, `.asSeconds()`) | `ndarray (n,)` float64 |
| `vector` | `at="double3"` | `ndarray (3,)` float64 | `ndarray (n, 3)` |
| `euler` | `at="double3"` (doubleAngle kids) | `ndarray (3,)` RADIANS | `ndarray (n, 3)` |
| `color` | `at="float3"`, `usedAsColor` | `ndarray (3,)` R/G/B | `ndarray (n, 3)` |
| `quaternion` | `at="compound"` nc=4 | `ndarray (4,)` X/Y/Z/W | `ndarray (n, 4)` |
| `float2` | `at="float2"` | `ndarray (2,)` float64 (U/V) | — |
| `matrix` | `dt="matrix"` | `MatrixView`, numpy-transparent 4x4 | `MatrixArrayView` → `(n, 4, 4)` |
| `string` | `dt="string"` | `str` | `list[str]` |
| `enum` | `at="enum"` | `EnumInt` (int; `.name()` → label) | — |
| `hex` | `dt="string"` | `str` (hex-decoded text) | — |
| `python` | `dt="string"` | any unpickled object (trust-gated) | `list` |
| `mesh` | `dt="mesh"` | `MFnMesh` or `None` | `list` |
| `nurbsCurve` | `dt="nurbsCurve"` | `MFnNurbsCurve` or `None` | `list` |
| `nurbsSurface` | `dt="nurbsSurface"` | `MFnNurbsSurface` or `None` | `list` |

`—` = not specified in `docs/node_types/_input_type_contract.md`. The Add-Attribute
dialog offers 17 of these; `double` and `float2` are API-only.

### `add_input_attr` kwargs

| kwarg | Effect |
|---|---|
| `is_array=True` | Multi plug. Not keyable by default (AE only); a wrapper opts one back in via `KEYABLE_ARRAY_INPUTS` — `mPyBlendShape.weight` does. |
| `enum_names=[...]` | Required for `enum`; falls back to `['False','True']`. |
| `min_value` / `max_value` / `default_value` | Scalar numerics; `default_value` also for `enum` (start index) and `bool`. |
| `sparse=True` | Compact, connected-only read. Default `False` = DENSE read of length `max_logical+1`, gaps filled with the default, so `self.X[i]` == logical index `i`. |
| `packed=True` | `double`/`int` arrays only: ONE typed-array plug. 655,928 values = 41.5 min as a multi vs 0.017 s packed. Excludes `sparse` and per-element connections; cannot be toggled later. |
| `auto_connect_time=False` | Suppress the automatic `time1.outTime` connect on scalar `time` inputs. |

Names: valid Python identifier, no dashes, no leading digit, not a keyword, not
`self`, not already used in that direction, not framework-reserved. Shadowing a
builtin (`min`, `type`) is fine via the API — the Add-Attribute DIALOG rejects it.

```python
n.delete_input_attr("amp"); n.rename_input_attr("amp", "gain")
n.get_input_attr_map(); n.set_input_attr_sparse("points", True)
n.set_input_attr_color("gain", "#ff8800")  # tints the row in Node Designer
n.reorder_input_attrs(["gain", "points"])  # addAttribute order == Channel Box order
```

## 3. Init vs Compute

| | Init | Compute |
|---|---|---|
| Runs | ONCE per file lifecycle (`kAfterOpen`, and on `set_init_expression`) | every DG pull |
| Put here | imports, `@njit` kernels, lookup tables, helper defs | the per-evaluation math |
| Names defined here | become BARE globals in Compute / Viewport | locals; `x = ...` does not persist |
| `self` | `InitProxy` — `self.X = v` PERSISTS to stored vars | `SelfProxy` — plugs + stored vars |
| Measured | kernel defined in Init: 0.31 s/eval | njit inlined in the expression: 0.61 s/eval |

```python
# --- Init tab ---
import numpy as np
from numba import njit

@njit(fastmath=True)
def ripple(pts, amp):
    out = pts.copy()
    out[:, 1] += amp * np.sin(out[:, 0] * 4.0)
    return out
```

```python
# --- Compute tab --- (no import, no self. on Init names)
self.result = ripple(np.asarray(self.points), float(self.amp))
```

### The tiers

| Tab | When it runs | Shown if the wrapper has | Setter |
|---|---|---|---|
| Init | once per file open | always | `set_init_expression(src)` |
| Compute | per DG evaluation | always | `set_compute_expression(src)` |
| Viewport | per VP2 shader update (mPyFile) | `set_viewport_expression` | `set_viewport_expression(src)` |
| OSL | never — renderer SOURCE on a connectable `.osl` output | `set_osl_expression` | `set_osl_expression(src)` |
| API | not a tier — the `.py` bake view; Methods are edited here | always | `set_methods_source(src)` |

## 4. Reading / writing in Compute

- **`self.X` only** — inputs, outputs, presets, draw context, stored vars. Never bare names.
- **No modules are auto-injected.** `import numpy as np` in the expression or in Init.
- Only assignments to declared OUTPUT plugs propagate; any other `self.X = ...` becomes a stored variable.
- Scalars stay Python primitives; vectors and arrays arrive as numpy. Matrices are ROW-major (translation is row 3).

```python
# --- Compute tab: mPyNode with inputs a/b/amp/offset, outputs sum/product ---
import numpy as np
self.sum     = float(self.a) + float(self.b)
self.product = np.asarray(self.offset) * float(self.amp)
```

| Output type | Assign | Written as |
|---|---|---|
| `float` / `double` / `int` / `bool` | numeric | `float()` / `int()` / `bool()` |
| `vector` / `euler` | `[x,y,z]`, tuple, or `(3,)` ndarray | `np.asarray(..., float64).flatten()` → double3 |
| `color` | `[r,g,b]` | `set3Float` on the float3 |
| `quaternion` | `[x,y,z,w]` | per-child `setDouble` |
| `matrix` | `MMatrix`, `MTransformationMatrix`, flat-16, `(4,4)`, `(3,3)` | coerced to 4x4 |
| `string` / `hex` | `str` | type-specific encoder |
| `vector` array | list of `(3,)` items | array of double3 plugs |

## 5. Stored variables

**Persistent** = saved with the scene (pickle + zlib + base64). **Temporary** =
session-only, re-initialised on next file load. A bare `self.x = ...` write in
Compute or Init lands in this store.

```python
n.add_variable("counter", 0)                   # declare PERSISTENT
n.set_variable("counter", 5)                   # value only -- KEEPS its status
n.set_variable("scratch", 5)                   # NEW var -> TEMPORARY
n.set_variable("scratch", 5, persistent=True)  # ...or promote as you write
n.get_variables(); n.get_variable_names(); n.is_variable_persistent("counter")
n.set_variable_persistent("counter", False)  # demote to TEMPORARY
n.rename_variable("counter", "ticks"); n.remove_variable("ticks")
```

```python
# --- Compute tab: seed-once idiom ---
import numpy as np
if not hasattr(self, "seed"):
    self.seed = np.random.rand(10)     # temporary until promoted
self.out = float(self.seed.mean())
```

Picklable values only (primitives, `list`, `dict`, `ndarray`, geometry wrappers,
`Draw*` items). `.mpn` carries the VALUES; the `.py` bake carries only the names.

## 6. Per-type `self.X` surface

| Node | Read | Write |
|---|---|---|
| `mPyDeformer` | `self.outputGeometry[i]` (writable `MFnMesh`), `self.input[i].inputGeometry`, `self.envelope` | `self.outputGeometry[i].setPoints(arr)` |
| `mPySkinCluster` | deformer slots + `self.matrix[j].asNumpy()`, `self.bindPreMatrix[j].asNumpy()`, `self.weightList[i].weights` | as deformer |
| `mPyBlendShape` | deformer slots + `self.morphs`, `self.weight[j]` (aliased to target name), `self.targetGeometry[j]` | as deformer |
| `mPyMesh` | `self.time` | `self.points (N,3)`, `self.counts (F,)`, `self.indices`, opt. `self.colors` (+ `color_indices`), `self.normals` (needs `normal_indices` — bare per-vertex is silently dropped), or `self.outMesh` |
| `mPyNurbsCurve` | `self.time` | `self.cvs (N,3)`, `self.degree`, `self.form`, `self.knots`, or `self.outCurve` |
| `mPyNurbsSurface` | `self.time` | `self.cvs (u,v,3)`, `self.num_cvs_u/v`, `self.degree_u/v`, `self.form_u/v`, or `self.outSurface` |
| `mPyTransform` | `self.translate`, `self.rotate` (RADIANS), `self.scale`, `self.shear`, `self.rotate_order` | `self.local_matrix` (LOCAL 4x4) + gates `self.apply_translate` / `apply_rotate` / `apply_scale` |
| `mPyLocator` | `self.time`, `self.selected`, `self.is_lead`, `self.hovered`, `self.selection_color` | `self.draw` + `self.auto_highlight` / `auto_refresh` / `precise_hover` |
| `mPyConstraint` | `self.targetTranslate`, `self.targetRotate`, `self.targetWeight`, `self.restTranslate`, `self.restRotate` | user-added outputs |
| `mPyIkSolver` | `self.joints` (list of dict), `self.end_effector`, `self.pole_vector`, `self.twist`, `MatrixView` | `self.local_matrices`, `self.world_matrices`, gates |
| `mPyFile` | `self.fileName`, `self.uvCoord`, `self.colorSpace`, filter / wrap / LOD plugs | `self.outColor`, `self.outAlpha` |

The deformer family has **no** `self.points` / `self.deformed` schema — `self.deformed = arr` silently stores a variable and the mesh is unchanged.

```python
# --- Compute tab: mPyDeformer (input "matrix" + "falloff") ---
import numpy as np
mesh = self.outputGeometry[0]          # writable MFnMesh handle
rest = mesh.getPoints()                # (N, 3) float64
pos  = np.asarray(self.matrix)[3, :3]  # matrix input -> (4, 4) MatrixView
dist = np.linalg.norm(rest - pos[None, :], axis=1)
fall = np.maximum(0.0, 1.0 - dist / max(float(self.falloff), 1e-6))
out  = rest.copy()
out[:, 1] += fall * 0.4 * np.sin(dist * 4.0) * float(self.envelope)
mesh.setPoints(out)                    # commit
```

NURBS geometry inside a deformer uses `cvPositions()` / `setCVPositions()`.

```python
# --- Compute tab: mPyMesh (typed output) ---
import numpy as np
from mpynode._api2.geometry import Mesh
self.outMesh = Mesh(points=np.array([(0,0,0), (1,0,0), (1,0,1), (0,0,1)], float),
                    counts=np.array([4], int),
                    indices=np.array([0, 1, 2, 3], int))
```

Wire `myGeo.outMesh -> someMeshShape.inMesh` to render it (curve/surface:
`outCurve` / `outSurface` -> the shape's `create`).

```python
# --- Compute tab: mPyLocator (draw types are seeded into a fresh Init) ---
from mpynode._common.draw.draw_types import DrawCircle, DrawText
self.draw = [DrawCircle(center=(0, 0, 0), radius=2), DrawText("hi")]
```

`self.draw` takes one item, a `+` chain, or a (nested) list — authoring order is
draw order, last on top; `None` draws nothing. Types: `DrawCircle`, `DrawSphere`,
`DrawBox`, `DrawCone`, `DrawCylinder`, `DrawPoints`, `DrawLines`, `DrawCurve`,
`DrawMesh`, `DrawText`. `mPyLocator` takes user INPUTS but has no DG user outputs.

## 7. Methods — `@maya_command` / `@maya_demo` / `@maya_test`

The three decorators and the assert helpers are PRE-INJECTED into the Methods
namespace — and NOTHING else is, so `maya.cmds` and every module you use you import
yourself, inside the def. The `.py` bake re-synthesizes only the DECORATOR imports.

| Decorator | Meaning | Compiled result |
|---|---|---|
| `@maya_command(name=..., undoable=...)` | companion command | a real `MPxCommand` registered with the node (`mc.<name>` / MEL) |
| `@maya_command(creates=True)` on `def setup(self, ...)` | CREATE command (the `skinCluster` shape: creates the node AND wires it) | the command snapshots the selection, creates the node, passes it in as `self` |
| `@maya_demo(label=...)` | runnable demo that fabricates its own scene | shipped demo scene |
| `@maya_test(label=..., digits=N)` | test — PASS = returns, FAIL = raises | the SAME test validates interpreted and compiled |

```python
# --- Methods, edited in the API tab ---
@maya_command(name="setMeshRegion", undoable=True)
def set_region_ids(self, indices=None):
    self.set_variable("region_ids", indices, persistent=True)

@maya_test(label="output doubles the input", digits=3)
def test_double(self):
    from maya import cmds as mc
    mc.setAttr(self.get_name() + ".inValue", 2.0)
    assert_close(mc.getAttr(self.get_name() + ".outValue"), 4.0)
```

Helpers: `assert_true`, `assert_equal`, `assert_close`, `max_abs_diff`,
`TestFailure`. `digits` (default 4) is decimal-place tolerance — a C++ compile can
differ in the last ulps. `creates=True` is ignored (with a warning) on a `cls`-first,
`@classmethod` or `@staticmethod` def; static detection only honours LITERAL kwargs.

```python
n.set_methods_source(src); n.get_methods_source()
n.run_setup(); n.run_demo(); n.run_test("test_double"); n.run_tests()
```

**Trap:** `self` is TWO objects. Expression tiers get a `SelfProxy`;
Methods / setup / demo / command bodies get the real WRAPPER. Disjoint surfaces —
a wrapper method called from Compute raises `AttributeError`.

## 8. Node Designer — tabs and keys

```python
from mpynode.ui.mpynode_designer import show_designer
show_designer()
```

Mode tabs `Workspace` (default) / `Templates`. Workspace is a 3-pane splitter:
left `Scene | Attributes | Variables | Framework`, centre the script strip
`Init | Compute | [Viewport] | [OSL] | API` over `Log | Watch | Profile`, right
the AI Assistant.

| Menu path | Does |
|---|---|
| `Node ▸ New Node ▸ <type>` | stays open — create several in a row (right-click a type for create modes) |
| `Node ▸ Add Attribute…` | persistent dialog: `Add` clears + refocuses, `Done` closes |
| `Node ▸ Duplicate` / `Duplicate + Inputs` | the latter re-creates input connections |
| `Node ▸ Save Node` (F5) / `Save All` | commit editor buffers to the node |
| `Node ▸ Compile to Native Plugin…` | the compile dialog |
| Scene-tree right-click | `Info…` (metadata) · `Run setup` · `Run demo` |
| Templates gallery | `Create` · `Create + Run demo` |

| Key | Action |
|---|---|
| `F5` | Save Node |
| `Ctrl/Cmd+F` | Find |
| `F3` / `Shift+F3` (`Cmd+G` / `Cmd+Shift+G`) | Find Next / Previous |
| `Ctrl+/` | Toggle comment |
| `Ctrl` + wheel | Font zoom |

```python
mc.setAttr(n.get_name() + ".watch_enabled", 1)
n.get_watch_vars()                                     # locals from the last compute (Watch tab)
mc.setAttr(n.get_name() + ".profile_enabled", 1)
mc.setAttr(n.get_name() + ".deep_profile_enabled", 1)  # cProfile drill-down
n.get_profile_snapshot()                               # {last_us, avg_us, min_us, max_us, count, ...}

from mpynode._common.util.log_bus import log
log("hello from my node", level="info")     # shows in the Log tab
```

## 9. `.mpn` vs `.py` bake

| | `.mpn` — `File ▸ Export Current Node as .mpn…` | `.py` — `File ▸ Bake Node to .py File…` |
|---|---|---|
| Direction | ROUND-TRIP | ONE-WAY |
| Sources | Init + Compute + Viewport + OSL + Methods | same, but Methods become REAL Python defs |
| Attributes | full maps incl. authored order + `ui_color` | re-declared via `add_*_attr` calls |
| Stored vars | the VALUES | names only — `add_variable(name, persistent=...)` |
| Metadata | Node Info block + `class_path` | `#` banner (pref `metadata_bake_header`) |
| Connections | NOT carried — it is a node template | not carried |
| Re-import | repopulates every tab | does NOT repopulate the Methods surface |

```python
from mpynode._common.io.mpn_io import (serialize_node, save_mpn,
                                       load_mpn, deserialize_node)
save_mpn(serialize_node(n), "myNode.mpn")            # zlib; compression="lzma" for max
payload, failures = load_mpn("myNode.mpn", return_failures=True)
new_node = deserialize_node(payload, name="reborn")

from mpynode._common.io.py_export import generate_node_script
src = generate_node_script(n)                        # exactly what the API tab shows
```

Baked shape: a subclass of the root wrapper with a generated `build()` calling
`cls.create(...)` (or `cls.create_on(mesh, ...)` for the deformer family), then
`# --- inputs ---`, `# --- outputs ---`, `# --- expressions ---`. Only `build()`
is regenerated; `ls` / `wrap` / `create` are inherited.

## 10. Compiling to a native plug-in

`Node ▸ Compile to Native Plugin…` — check the scene nodes to bundle, name the
plug-in, pick target Maya versions (one checkbox per install found with a
devkit). It ports, compiles and parity-verifies in a throwaway `mayapy`, so the
live scene is never touched.

```python
from mpynode.native.spec import spec_extractor
from mpynode.native.toolchain import compile_controller

specs = [spec_extractor.extract_spec(name) for name in ("nodeA", "nodeB")]
out = compile_controller.compile_plugin(specs, "myPlugin", "out",
                                        strict=True, verify=True,
                                        reuse_cache=True, optimize=False)
out["ok"], out["bundle_path"], out["manifest_path"]

from mpynode.native.ai import porter
res = porter.port_from_node("myNode", "out")   # one node -> one plug-in
```

| Stage | File | Meaning |
|---|---|---|
| 1 | `build/stages/<Type>/1_transpiled.cpp` | deterministic transpile, NO AI. Always written; a hand-finishable baseline. |
| 2 | `build/stages/<Type>/2_assisted.cpp` | only if a `PORT` region survived AND assist is on. Absent = it lowered deterministically. |
| 3 | `build/stages/<Type>/3_optimized/NN_*.cpp` | opt-in optimizer, one file per round, rejects kept. |
| ship | `build/source/<Type>.cpp` | what actually links. `build/manifest.json` is the receipt. `build/<Type>/` is per-node SCRATCH, swept on success. |

- `strict=True` aborts on a BLOCKED node; `strict=False` drops it and bundles the rest.
- The compute is pure C++ on BOTH paths — there is no interpreter fallback.
- A gap the AI cannot honestly fill is marked `ND_PORT_INCOMPLETE`, never invented.
- Ported `.cpp` is cached by SPEC hash, so an emitter-only change is invisible to it — bump `PORTER_RECIPE_VERSION` and rebuild rather than editing the freshness test.
- Network / file / `maya.cmds` / GUI use is reported as **unported** — a warning plus AI-porter context, NOT a gate. The only BLOCKERS are `python` and `message` attr types.
- Needs a C++ toolchain; a fully deterministic or fully cached build needs no AI provider.

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Unable to create/find dependency node` | Plug-in not loaded. `create` / `create_on` auto-load; wrapping by name does not. Check `MAYA_PLUG_IN_PATH` contains `plug-ins/`. |
| Expression seems to do nothing | Check the **Log** tab — every expression exception is caught and logged there (and to `stderr` in batch). |
| `NameError: np is not defined` | No modules are auto-injected. Import in the expression or define it in Init. |
| `AttributeError` on a name the Framework tab lists | That tab is TIER-SCOPED. Expression tiers get `SelfProxy`; Methods / setup / demo get the wrapper. |
| Output never updates when an upstream node moves | Auto-dirty callbacks failed to install — check the Output Window for `[auto_dirty]` errors at plug-in load. |
| Mesh comes out undeformed | You wrote `self.deformed` / `self.points`. Deformers commit ONLY via `self.outputGeometry[i].setPoints(arr)`. |
| A value vanishes between evals | It was a bare local or a temporary var. `n.set_variable_persistent(name, True)`. |
| `python` input reads `None` | Untrusted scene — pickle is trust-gated. Headless: `MPYNODE_TRUST_PICKLE=1`. |
| `self.X[i]` doesn't line up with the plug index | The input is `sparse=True`; the default dense read pads gaps with the attribute default. |
| Writing a big table takes minutes | A numeric multi is one `setAttr` per element. Re-add the attribute with `packed=True`. |
| Locator user OUTPUT never computes | `MPxLocatorNode` doesn't dispatch `compute()` for runtime outputs — chain a downstream `mPyNode`. |
| Compile "succeeded" but behaviour is stale | Port-cache hit served an old `.cpp`. Bump `PORTER_RECIPE_VERSION` and rebuild. |
| Stored var won't save | Non-picklable value (open handle, `MObject`). Keep stored data plain. |

Reference: `docs/index.md` (API guide), `docs/node_types/` (per-type schemas),
`docs/node_types/_input_type_contract.md` (authoritative `self.X` types),
`templates/<WrapperClass>/<Name>/template.mpn` (37 examples, e.g. `MPyNode/Bubble Sort/`),
`tools/run_tests.sh` (the test suite).
