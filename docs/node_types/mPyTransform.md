# mPyTransform

Expression-driven custom transform. Inherits from `MPxTransform` (API 1.0
only) paired with a custom `MPxTransformationMatrix` subclass. The expression
drives the node like a **single-joint IK solver**: it publishes a desired
**local** (parent-relative) `(4, 4)` matrix plus per-channel `apply_*` gates,
and the node rides that result on `offsetParentMatrix` (so descendants track it)
while the ordinary TRS channels stay live for un-gated channels. This lets
users implement custom matrix decomposition (quaternion blends, swing/twist,
RBF-driven offsets, aim constraints, etc.) at the transform level.

The contract mirrors `mPyIkSolver`'s gated local-matrix interface (with the
bind offset fixed to identity): un-gated channels fall back to the live TRS,
so a rotate-only expression reorients in place and leaves translate free.

To place the node in **world** space, keep the result local and convert:
read the parent's world from a **connected** matrix input and set
`self.local_matrix = worldDesired @ inv(parentWorld)`. The node never reads its
own DAG parent, so world-space is opt-in and free of the stale/cyclical trap an
imperative parent read would create.

---

## Plug-in

Registered via `MFnPlugin.registerTransform(...)` in `mpynode_api1.py`.
**This is the only mpynode native type that uses `registerTransform`
rather than `registerNode`**, because `MPxTransform` requires a paired
`MPxTransformationMatrix` class with its own `MTypeId`:

- `MPyTransform.NODE_ID = 0x00135717`
- `MPyTransformMatrix.NODE_ID = 0x00135718`

---

## Interface

The interface is **five per-channel INPUT attributes (reads) + four internal
write slots** (gated local-matrix).

### Input attributes (reads)

This node's own live channels are exposed as always-present **INPUT attributes** —
the inherited transform plugs, surfaced in the Node Designer's **Inputs** pane
(via the wrapper's `EXPOSED_INPUT_PLUGS`, so the default framework filter doesn't
hide them). The expression reads them as `self.<name>`; any change (manual OR a
connected/dirty plug) re-evaluates the node:

| `self.<name>` | Plug | Type | Notes |
|---|---|---|---|
| `translate` | `.translate` | `np.ndarray(3,)` | Live translate channel (tx, ty, tz), Maya internal linear unit (cm). |
| `rotate` | `.rotate` | `np.ndarray(3,)` | Live rotate channel (rx, ry, rz), in **radians**. |
| `scale` | `.scale` | `np.ndarray(3,)` | Live scale channel (sx, sy, sz). |
| `shear` | `.shear` | `np.ndarray(3,)` | Live shear channel (shearXY, shearXZ, shearYZ). |
| `rotate_order` | `.rotateOrder` | `int` | Rotate-order enum, `0..5` (`0 == xyz`). |

Read values are sourced fresh from the paired `MPxTransformationMatrix`
accessors each compute (not a plug read, which would be stale-by-one inside the
flush-free custom-output compute), so they track every evaluation and stay at
parity with the compiled node.

### Internal write slots

Set these from the expression (shown in the Designer's **API** pane); the
node handles everything else:

| Name | Type | Access | Notes |
|---|---|---|---|
| `local_matrix` | `np.ndarray(4, 4)` or `None` | write | Desired **local** (parent-relative) matrix. Default `None`. For world placement set it to `worldDesired @ inv(parentWorld)`. |
| `apply_rotate` | `bool` | write | Gate: take rotation from the matrix. Default `True`. |
| `apply_translate` | `bool` | write | Gate: take translate from the matrix. Default `True`. |
| `apply_scale` | `bool` | write | Gate: take scale from the matrix. Default `True`. |

> **Why reading the live channels is cycle-safe.** The T/R/S/shear/rotateOrder
> channels never depend on the `offsetParentMatrix` this node authors — so
> reading them while writing opm is a fan-in (both feed `worldMatrix`), not a
> loop. The node deliberately exposes only these local channels: reading its own
> *world*/`parentMatrix` would feed the output back. World placement therefore
> uses a **connected** parent-world matrix INPUT (a DG-tracked fan-in), never an
> imperative read of the DAG parent.

**Dispatch rules:**

- `local_matrix` `None` → nothing applied (plain Maya transform). This is
  **checked first**, so a vanilla node is inert regardless of the gates —
  the gates default `True` purely so that *assigning a matrix* drives every
  channel without also opening gates by hand.
- All three `apply_*` `False` → nothing applied.
- `local_matrix` not `None` and ≥1 gate open → drive from the local matrix.
- Un-gated channels (a gate set `False`) come from the live TRS (bind offset ≡
  identity), so e.g. `apply_rotate=False` (with a matrix set) keeps the live
  rotation while translate/scale come from the matrix.

> The legacy `world_matrix` write slot (and the older `time`, `parent_matrix`,
> and `output_matrix` slots) were **removed**. Read this node's own live pose
> off `self.translate` / `rotate` / `scale` / `shear` / `rotate_order` (above);
> read **external / world driver** values — including a parent world for world
> placement — through matrix INPUT attrs (see the aim template's `matrix0` /
> `matrix1` / `parentWorld`).

---

## Matrix layout

Maya `MMatrix` is **row-major** with translation in the **last row** (row
3, columns 0..2). To shift the transform up by Y=2 in local space:

```python
import numpy as np
m = np.eye(4)
m[3, 1] = 2.0
self.local_matrix = m         # gates default True -> all channels driven
# set e.g. self.apply_rotate = False to keep the live rotation
```

---

## Architecture: flush-free `offsetParentMatrix` (R1-double)

The result rides `offsetParentMatrix`, never `asMatrix()`:

- `MPyTransformMatrix.asMatrix()` returns the **plain TRS** — the expression
  no longer runs there.
- `MPyTransformMatrix._run_expression()` (the C++ scaffold's `desiredLocal()`)
  runs the expression, applies the gated dispatch, and returns the desired
  **local** matrix `D`.
- The transform's `compute()` authors `opm = inv(L) @ D` (where `L` =
  `asMatrix()`) into a hidden `_outLocalFlat` `double[16]` output. A stock
  `fourByFourMatrix` relay (auto-wired per node) rebuilds that into a matrix
  and feeds `offsetParentMatrix`. Result: `world = L @ opm @ parent = D @ parent`,
  so descendants inherit the expression result.

A `double[]` array carrier is used because a matrix output from
`MPxTransform.compute()` segfaults in Maya 2026 (same reason as the
interpreted node's flat carrier).

The node **never** reads its own DAG parent (neither `MDagPath::pop()` +
`inclusiveMatrix` nor `parentMatrix`): an imperative parent read is not
DG-tracked, so a later parent move leaves the authored `opm` stale, and
`parentMatrix` already folds in this node's own `offsetParentMatrix`, feeding
the output back on itself. World placement is instead done in the expression —
`self.local_matrix = worldDesired @ inv(parentWorld)` off a **connected**
parent-world matrix input, which is a proper DG fan-in and re-solves whenever
the parent moves.

---

## Failure mode

Any expression error → the node authors an identity `opm` and behaves as a
normal Maya transform (children stay in place, viewport doesn't break). The
error surfaces via:
- `sys.stderr`
- `log_bus.log()` (UI Log panel)

---

## Example

This example builds an expression-driven custom transform that lifts itself
+2 in Y by publishing a **local** matrix with only the translate gate open,
parents a child locator under it, and reads the child's `worldMatrix` back to
prove the offset propagated. (The transform is a root, so its local frame *is*
its world frame; for a parented node, convert with
`self.local_matrix = worldDesired @ inv(parentWorld)`.)

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_transform import MPyTransform

mc.file(new=True, force=True)

# Custom transform: publish a local matrix offset +2 in Y with only the
# translate gate open (gates default True, so rotate/scale are closed
# explicitly to leave them on the live TRS).
t = MPyTransform.create(name="liftingTransform")
node = t.get_name()

# Parent a child so the offset shows up in a real worldMatrix read.
child = mc.spaceLocator(name="rider")[0]
mc.parent(child, node)

t.set_compute_expression(
    "import numpy as np\n"
    "# Maya MMatrix is row-major: translation lives in row 3, cols 0..2.\n"
    "m = np.eye(4)\n"
    "m[3, 1] = 2.0\n"
    "self.local_matrix = m\n"        # desired LOCAL (parent-relative) frame
    "self.apply_translate = True\n"  # gate translate...
    "self.apply_rotate = False\n"    # ...and keep rotate/scale live
    "self.apply_scale = False\n"
)

# Force evaluation by reading the child's worldMatrix (element 13 == ty).
world_y = mc.getAttr(child + ".worldMatrix[0]")[13]
assert abs(world_y - 2.0) < 1e-4, world_y
print("child world Y =", round(world_y, 4))  # -> child world Y = 2.0
```

---

## See also

- Demo: `scripts/mpynode/_demos/build_mPyTransform_bobbing.py`
- Wrapper: `scripts/mpynode/wrappers/mpy_transform.py`
- Bridge: `scripts/mpynode/_api1/mpy_transform.py`
- Plugin registration: `plug-ins/mpynode_api1.py`
