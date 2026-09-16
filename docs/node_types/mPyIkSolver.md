# mPyIkSolver

**Plugin:** `mpynode_api1` · **Inherits:** `MPxIkSolverNode` (API 1.0 only) · **Type ID:** `0x00135713`

Custom IK solver. Write your own joint solve in Python.

---

## Use cases

- Look-at / aim solvers
- Custom 2-bone or N-bone IK with non-standard math (e.g., elastic, springy)
- Procedural rigging where the standard ikRP/ikSC solvers don't fit

---

## Contract at a glance

The solver writes **only** each joint's `offsetParentMatrix` — the joints' own
translate/rotate/scale channels and `jointOrient` are never touched. Your
expression drives joints through two per-joint matrix outputs (each a list of
`None`, one slot per joint):

- `self.local_matrices[i]` — desired **LOCAL** (parent-relative) matrix
- `self.world_matrices[i]` — desired **WORLD** (absolute) matrix

Per joint the dispatch is **WORLD > LOCAL > follow-rest** (a slot left `None` in
both lists leaves the joint at its rest offset). Three channel gates —
`apply_rotate` (default `True`), `apply_translate` (default `False`),
`apply_scale` (default `False`) — select which components of the desired matrix
drive the joint; ungated components come from the joint's rest pose (so
rotate-only reorients in place, preserving bone lengths). Each gate is a scalar
bool (broadcast to the chain) **or** a per-joint list of bools.

There are no Euler-angle outputs — a full matrix sidesteps the degrees/radians
mismatch that the old `joint_rotations` contract suffered.

## Example

Build a 3-joint chain plus an `ikHandle` pinned to a custom `mPyIkSolver`, then
set a compute expression that bends the knee. This uses the **local** path via
the `MatrixView` helper (injected into the namespace) so you never touch raw
matrix math. Moving the handle and forcing a solve runs `doSolve` headless; we
assert the knee's `offsetParentMatrix` was driven while its `rotate` channel
stayed zero.

```python
import maya.cmds as mc
from mpynode.wrappers.mpy_iksolver import MPyIkSolver

mc.file(new=True, force=True)

# Build a 3-joint vertical chain: hip -> knee -> ankle (10 units fully extended).
mc.select(clear=True)
hip   = mc.joint(name="hipJ",   position=(0, 5, 0))
knee  = mc.joint(name="kneeJ",  position=(0, 0, 0))
ankle = mc.joint(name="ankleJ", position=(0, -5, 0))

# Create the custom solver INSTANCE, then set its solve expression.
solver = MPyIkSolver.create()
solver.set_compute_expression('''
import math
import numpy as np
B1 = 5.0  # hip -> knee length
B2 = 5.0  # knee -> ankle length
hip_wp = self.joints[0]["world_position"]
d = float(np.linalg.norm(self.end_effector - hip_wp))  # end_effector = handle pos
# Knee bend via law of cosines.
if d >= B1 + B2:
    bend = 0.0
elif d <= abs(B1 - B2):
    bend = math.pi
else:
    c = (B1 ** 2 + B2 ** 2 - d ** 2) / (2.0 * B1 * B2)
    bend = math.pi - math.acos(max(-1.0, min(1.0, c)))
# Desired knee LOCAL matrix: rotate its rest (parent-relative) frame about X.
m = self.joints[1]["matrix"]      # a MatrixView (local/parent-relative frame)
m.rotateBy([-bend, 0.0, 0.0])     # RADIANS, in place, chainable
self.local_matrices[1] = m
self.apply_rotate = True          # rotate-only (default) -> bone lengths preserved
''')

# IK handle pinned to our solver.
handle = mc.ikHandle(startJoint=hip, endEffector=ankle,
                     solver=solver.get_name(), name="legHandle")[0]

# Pull the handle inside reach so the knee must bend, then force a solve headless.
mc.setAttr(handle + ".translate", 0, -2, 4)
mc.dgeval("ankleJ.worldMatrix[0]")   # triggers MPxIkSolverNode.doSolve()

import numpy as np
off = np.array(mc.getAttr("kneeJ.offsetParentMatrix")).reshape(4, 4)
assert not np.allclose(off, np.eye(4)), "knee offsetParentMatrix not driven"
assert abs(mc.getAttr("kneeJ.rotateX")) < 1e-5, "joint's own rotate should stay 0"
print("OK knee driven via offsetParentMatrix; kneeJ.rotateX = %.6f (untouched)"
      % mc.getAttr("kneeJ.rotateX"))
```

For a full 2-bone aim solve (hip reorients toward the goal, knee bends, tip
reaches exactly) see `templates/MPyIkSolver/Two Bone IK/template.mpn` — it
drives `self.world_matrices` with world frames and is the porter-friendly
expression shipped with the compiled `twoBoneIK` demo.

---

## Expression namespace

All IK context is reached via `self.` (the exec namespace injects
`__builtins__`, `self`, a `node` proxy, and `MatrixView` — never bare `joints` /
`end_effector` / ...):

| Variable | Type | Notes |
|---|---|---|
| `self.joints` | list of dict | One dict per joint in the chain. Keys: `name`, `world_position` (numpy 3,), `rotation` (numpy 3,, Euler degrees), `matrix` (**MatrixView**, local/parent-relative rest frame), `world_matrix` (**MatrixView**, rest **world** frame — both include the captured bind offset and are stable across solves; row-vector Maya) |
| `self.end_effector` | numpy (3,) | World-space position of the IK HANDLE (NOT the effector) |
| `self.pole_vector` | numpy (3,) | From the IK handle's `poleVector` attr |
| `self.twist` | float | From the IK handle's `twist` attr |
| `MatrixView` | class | Matrix builder: `setRotation`/`setTranslation`/`setScale`/`rotateBy`/… (rotations in **radians**, chainable in place, numpy-transparent). Build a result without raw matrix math. |
| `self.local_matrices` | list[4×4 or `None`] | OUTPUT: per-joint desired **LOCAL** (parent-relative) matrix (one `None` slot per joint). Applied via `offsetParentMatrix`, gated, leaving the joint's own channels **and jointOrient** untouched. |
| `self.world_matrices` | list[4×4 or `None`] | OUTPUT: per-joint desired **WORLD** (absolute) matrix. Same application as `local_matrices`. Per-joint dispatch is **WORLD > LOCAL > rest**. |
| `self.apply_rotate` | bool **or** list[bool] | Gate: take rotation from the matrix (default `True`). Scalar broadcasts to the chain; a per-joint list gates individual joints (ragged → default-filled). |
| `self.apply_translate` | bool **or** list[bool] | Gate: take translate (default `False`) — ungated channels come from the joint's rest pose, so rotate-only reorients in place (bone lengths preserved). |
| `self.apply_scale` | bool **or** list[bool] | Gate: take scale (default `False`). |

> **Local vs world.** Drive `world_matrices` when your solve produces an
> absolute frame (aim/goal solves — the world path also threads each joint's
> parent world). Drive `local_matrices` when it produces a parent-relative frame
> (a local bend); the local path needs no parent-world term. Setting **both** on
> the same joint is a conflict — world wins and a warning is logged.

Only `__builtins__`, `node`, and `MatrixView` are injected automatically. Import
`math` / `numpy as np` yourself (inline, as the quickstart does, or in the
Init tab); `cmds` is not auto-provided.

---

## How the bridge works

1. `MPyIkSolver.doSolve()` is called by Maya's IK system when the connected `ikHandle` is dirty.
2. We delegate to `_api1.helpers.compute_ik_doSolve(self)`:
   - Walk the IK handle group → get the first IK handle's `MFnIkHandle`
   - Get start joint + effector via `getStartJoint()` / `getEffector()`
   - Walk the joint chain via `_walk_joint_chain` (fix: don't break early on effector siblings)
   - **Capture bind offsets** (pre-writeback): the first time (or after a re-bind) each joint's current `offsetParentMatrix` is captured, positionally along the chain, into the storable `_jointBindOffsets` plug — then locked. This is the neutral the solver restores unset joints to and mixes ungated channels from.
   - For each joint, thread its **rest** `matrix` (local) and `world_matrix` (`local @ bindOffset @ parentWorld`, from the root's true DAG-parent world) as MatrixViews; also read `world_position` + `rotation`.
   - Build `end_effector` from the HANDLE's world position; `pole_vector` + `twist` from the handle's plugs.
3. Run the user expression with the above context.
4. Apply the result via `_apply_joint_solve`, walking root→tip and threading each joint's parent world. Per joint:
   - **world** slot set → gate-mix the desired world matrix against the rest world, `offset = inv(local) @ w_mixed @ inv(parent_world)`;
   - else **local** slot set → gate-mix against the rest parent-relative, `offset = inv(local) @ l_mixed` (parent-world cancels);
   - else → restore the captured **bind offset** (the joint returns to rest; the write is idempotent).
   Only `offsetParentMatrix` is ever written.
5. Write a JSON snapshot to `_solverContextSnapshot` plug (for the Solver Context UI panel).

> **Why parent world comes from the DAG parent, not `parentInverseMatrix`:** a node's `.parentMatrix` / `.parentInverseMatrix` **include that node's own `offsetParentMatrix`**. Seeding a reference from them picks up the *previous* solve's offset and drifts across solves. `_root_parent_world` reads the root's DAG-parent `worldMatrix` (identity under world) and the solve threads parent world root→tip, giving a stable reference and one-shot convergence.

> **Re-bind.** `MPyIkSolver.rebind()` (or `_api1.helpers.rebind_ik_solver(name)`) clears `_jointBindOffsets` so the next solve re-captures the joints' current offsets as the new neutral — i.e. "set current pose as rest". Use it after intentionally changing the rest pose.

---

## Critical Phase fixes baked in

- `end_effector` is the IK HANDLE's world position, not the effector's. The effector is the chain's slave tip; reading from it would mean "where the chain currently ends" instead of "where the user wants it to end."
- `_walk_joint_chain` doesn't break when a SIBLING of the next joint is the effector. Without this, 3+ joint chains drop the last joint.

---

## Shipping demo: `two_bone_ik` (world path)

`templates/MPyIkSolver/Two Bone IK/template.mpn` is the reference template. It
runs a jointOrient-agnostic 2-bone aim solve entirely through
`world_matrices`: the hip reorients toward the goal, the knee bends via the
law of cosines, and the tip reaches the goal exactly — with the joints' own
`rotate` channels left at rest and `jointOrient` preserved (only
`offsetParentMatrix` is driven). Bone lengths are read from the rest-pose joint
positions (not hardcoded).

It compiles to the native `twoBoneIK` MPx plugin. The compiled solver reaches the
goal within `1e-3` and matches the interpreted `mPyIkSolver` to `~1e-15` across a
target sweep (see `templates/MPyIkSolver/Two Bone IK/`):

| Artifact | What it is |
|---|---|
| `basics_rigging_two_bone_ik.ma` | headless demo scene bound to the compiled `twoBoneIK` |
| `two_bone_ik_verify.ma` | interactive scene — open it and drag the `ikGoal` locator; the leg tracks it via the compiled `offsetParentMatrix` IK |

---

## Caveats

- `mc.ikHandle solver="mPyIkSolver"` requires the solver INSTANCE to exist first (not just the type). The wrapper's `find_solver()` ensures this.
- Only the FIRST IK handle in the solver's handle group is processed (multi-handle support is straightforward but deferred).

---

## See also

- `_api1/mpy_iksolver.py` — MPxIkSolverNode subclass
- `_api1/helpers.py` — `compute_ik_doSolve`, `_walk_joint_chain`, `compute_ik_user_solve`
- `_common/snapshot.py` — `_solverContextSnapshot` write/read
- `wrappers/mpy_iksolver.py` — user-facing wrapper
