# mPyConstraint

Expression-driven custom constraint built on `MPxNode` (API 2.0). It behaves
like a scriptable `pointConstraint` / `parentConstraint`: five preset
constraint-style **input** plugs feed the expression, which writes arbitrary
**user output** plugs back into the DG. Unlike the locator and IK solver, it is
a plain dependency node, so it has full DG user-output support.

---

## Why `MPxNode` and not `MPxConstraint`

`MPxConstraint` hijacks `compute()` for its inherited plugs, which forces a
reactive-callback pattern just to write *user* outputs. `mPyConstraint` instead
subclasses `MPyNode` (an `MPxNode`) and adds constraint-style preset inputs. The
end-user behavior is the same — a distinct, channel-box-friendly "constraint"
node — but the plumbing is the standard `compute()` path with no callback
workaround.

---

## Expression contract (`self.X`)

| `self.X` | Type | Access | Notes |
|---|---|---|---|
| `self.targetTranslate` | `(3,) float64` numpy | read | Preset vector input (`double3`). |
| `self.targetRotate` | `(3,) float64` numpy | read | Preset vector input (`double3`). Plain doubles, **not** an angle attr — a connection from a transform's `.rotate` delivers Maya's internal angular unit (radians); use `np.degrees(...)` if you want degrees. |
| `self.targetWeight` | `float` | read | Preset scalar input, default `1.0`. |
| `self.restTranslate` | `(3,) float64` numpy | read | Preset vector input (`double3`). |
| `self.restRotate` | `(3,) float64` numpy | read | Preset vector input (`double3`); same angular-unit caveat as `targetRotate`. |
| user input attrs | per type | read | Anything added with `add_input_attr(...)` is readable as `self.<name>`. See [`_input_type_contract.md`](_input_type_contract.md). |
| user output attrs | per type | write | Anything added with `add_output_attr(...)`; assign `self.out = ...` to drive it. |
| user storage | any | read/write | `self.foo = ...` for arbitrary per-node Python state persisted across evaluations. |

The five preset inputs are **always available** via `self.X` (no
`add_input_attr` needed) and are **read-only**. They are read plug-side through
`PlugProxy.asNumpy()` — the same path `self.X` uses — **not** via `cmds.getAttr`
(a DG-re-entry anti-pattern that was removed) and not via `data_block.inputValue`.
Because the preset plugs are created by the node initializer (not in the user's
`_inputAttrs` JSON), they are reached as `self.targetTranslate` etc. — the same
`self.<name>` access used for user-added inputs and outputs.

---

## Base class & MTypeId

- Base class: `MPyNode` → `MPxNode` (API 2.0).
- MTypeId: `0x00135703`.

---

## Lineage

```
MPxNode
  └── MPyNode            (API 2.0 base — full input/output support)
        └── mPyConstraint  (+ 5 preset constraint-style inputs)
```

---

## Plug-in

Registered in `plug-ins/mpynode_api2.py` as a plain dependency node (no
classification, no draw override):

```python
plugin2.registerNode(
    MPyConstraint.NODE_NAME, MPyConstraint.NODE_ID,
    MPyConstraint.creator, MPyConstraint.initializer,
)
```

`initializer` builds the standard framework/instrumentation plugs
(`_computeSource`, the inputs/outputs maps, stored-var plugs, `debug_mode`,
profile/watch plugs) via `helpers.build_internal_attrs`, then adds the five
preset inputs with `MFnNumericAttribute` (`createPoint` for the four vectors,
`create(..., kFloat, 1.0)` for `targetWeight`). All five are `storable`,
`keyable`, and `connectable`.

---

## Re-evaluation

The node overrides `setDependentsDirty` so that a change to **any** preset input
(or its `X`/`Y`/`Z` child) marks **all** user output plugs dirty — the output
re-evaluates when the driver moves. Changes to user-added inputs fall through to
the parent `MPyNode` dirty logic.

---

## Failure mode

- **During file read** → `compute()` defers (`MFileIO.isReadingFile()` guard) so
  the Evaluation Manager can't pull an output before the node's dynamic attrs are
  restored. It recomputes normally once the scene is whole.
- **Expression error** → the offending output is left unwritten; the error is
  written to `sys.stderr` and broadcast to the Node Designer Log tab via
  `mpynode._common.log_bus.log()`. A broken expression never crashes Maya.

---

## Example

Point-constrain one cube to another: the constraint reads its preset `targetTranslate` input and writes it back out through a user-added `constrained_pos` vector output, which drives the driven cube's `translate`. After moving the source, forcing evaluation shows the driven cube following exactly.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_constraint import MPyConstraint

mc.file(new=True, force=True)

# Source and driven cubes.
src = mc.polyCube(name="srcCube")[0]
dst = mc.polyCube(name="drivenCube")[0]

# Build the constraint, add a vector output, and write targetTranslate to it.
c = MPyConstraint.create(name="myConstraint")
node = c.get_name()
c.add_output_attr("constrained_pos", "vector")
c.set_compute_expression("self.constrained_pos = self.targetTranslate")

# Wire: src.translate -> constraint -> dst.translate.
mc.connectAttr(src + ".translate", node + ".targetTranslate", force=True)
mc.connectAttr(node + ".constrained_pos", dst + ".translate", force=True)

# Drive the source and force evaluation; the driven cube must follow.
mc.setAttr(src + ".translate", 4.0, -2.0, 7.0)
mc.dgeval(node + ".constrained_pos")
driven = mc.getAttr(dst + ".translate")[0]

assert abs(driven[0] - 4.0) < 1e-6 and abs(driven[1] + 2.0) < 1e-6 and abs(driven[2] - 7.0) < 1e-6, driven
print("OK driven.translate =", driven)
```

---

## Wrapper constructors & helpers

| Method | Purpose |
|---|---|
| `MPyConstraint(name)` | Wrap an existing `mPyConstraint` node by name. |
| `MPyConstraint.create(name='mPyConstraint#')` | Create a bare constraint node. |
| `c.list_preset_inputs()` | Return the five preset input plug names (`MPyConstraint.PRESET_INPUTS`). |

The wrapper is re-exported from the package root, so `from mpynode import
MPyConstraint` also works. Output/expression authoring uses the shared
`MPyNode` API (`add_output_attr`, `add_input_attr`, `set_compute_expression`,
`add_variable`, …).

---

## See also

- Wrapper: `scripts/mpynode/wrappers/mpy_constraint.py`
- Bridge: `scripts/mpynode/_api2/mpy_constraint.py`
- Plug-in registration: `plug-ins/mpynode_api2.py`
- Input typing: [`_input_type_contract.md`](_input_type_contract.md)
- Sibling specialty node: [`mPyLocator.md`](mPyLocator.md)
