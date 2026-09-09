# twoBoneIK -- compile report

**Source node:** `twoBoneIK`  ·  **Base:** `MPxIkSolverNode`  ·  **Generated:** 2026-09-08 23:24

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | ran, nothing accepted (no candidate beat the baseline) |

## The Python this was generated from

```python
# 2-bone analytic IK (law of cosines) producing per-joint WORLD matrices.
# Runs during the IK solve when this node is the solver on an ikHandle driving a
# 3-joint chain (root -> mid -> tip). The solve is jointOrient-agnostic: it reads
# each joint's rest (bind) world frame and rotates it so the bone aims correctly,
# then the bridge applies the result via offsetParentMatrix (rotate-only by
# default) -- the joints' own channels and jointOrient are left untouched.
#
# NOTE: this minimal solver's bend plane comes from the pole vector if present,
# else the rest knee direction (stable, avoids knee-pop). Add a dedicated pole
# input + reference axis for production rigs.
import math
import numpy as np

joints = self.joints
if len(joints) >= 3:
    p0 = np.asarray(joints[0]["world_position"], float)   # root (hip)
    p1 = np.asarray(joints[1]["world_position"], float)   # mid  (knee)
    p2 = np.asarray(joints[2]["world_position"], float)   # tip  (ankle)
    W0 = np.asarray(joints[0]["world_matrix"], float).reshape(4, 4)
    W1 = np.asarray(joints[1]["world_matrix"], float).reshape(4, 4)
    B1 = float(np.linalg.norm(p1 - p0))       # upper bone length (rigid)
    B2 = float(np.linalg.norm(p2 - p1))       # lower bone length (rigid)

    target = np.asarray(self.end_effector, float)
    goal_vec = target - p0
    reach = float(np.linalg.norm(goal_vec))
    if reach > 1e-9 and B1 > 1e-9 and B2 > 1e-9:
        goal_dir = goal_vec / reach
        # clamp reachable distance (law-of-cosines domain)
        d = min(max(reach, abs(B1 - B2) + 1e-4), B1 + B2 - 1e-4)
        goal_pt = p0 + d * goal_dir

        pole = np.asarray(self.pole_vector, float)
        ref = (pole - p0) if float(np.linalg.norm(pole)) > 1e-6 else (p1 - p0)
        bend_n = np.cross(goal_dir, ref)
        if float(np.linalg.norm(bend_n)) < 1e-6:
            bend_n = np.cross(goal_dir, np.array([0.0, 0.0, 1.0]))
        if float(np.linalg.norm(bend_n)) < 1e-6:
            bend_n = np.cross(goal_dir, np.array([1.0, 0.0, 0.0]))
        bend_n = bend_n / np.linalg.norm(bend_n)

        cos_a = (B1 * B1 + d * d - B2 * B2) / (2.0 * B1 * d)
        alpha = math.acos(max(-1.0, min(1.0, cos_a)))

        def rot3(axis, ang):
            # column-vector Rodrigues rotation (R @ v) about a unit axis.
            x, y, z = axis[0], axis[1], axis[2]
            c = math.cos(ang)
            s = math.sin(ang)
            k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
            return np.eye(3) + s * k + (1.0 - c) * (k @ k)

        upper_dir = rot3(bend_n, alpha) @ goal_dir
        upper_dir = upper_dir / np.linalg.norm(upper_dir)
        knee_pt = p0 + B1 * upper_dir
        lower_dir = goal_pt - knee_pt
        lower_dir = lower_dir / np.linalg.norm(lower_dir)

        def aim(w_rest, rest_dir, new_dir):
            # World matrix that re-aims a joint's bind frame so its bone points
            # from rest_dir to new_dir. Returns w_rest @ delta, where delta's
            # rotation is the transpose of the (column) rotation mapping
            # rest_dir->new_dir (row-vector Maya). Only rotation is used
            # downstream (translate is gated off), so the delta translation is 0.
            a = rest_dir / np.linalg.norm(rest_dir)
            b = new_dir / np.linalg.norm(new_dir)
            v = np.cross(a, b)
            s = float(np.linalg.norm(v))
            c = float(np.dot(a, b))
            if s < 1e-9:
                rct = np.eye(3)
            else:
                rct = rot3(v / s, -math.acos(max(-1.0, min(1.0, c))))
            delta = np.eye(4)
            delta[:3, :3] = rct
            return w_rest @ delta

        self.world_matrices[0] = aim(W0, p1 - p0, upper_dir)   # root aims upper bone
        self.world_matrices[1] = aim(W1, p2 - p1, lower_dir)   # mid  aims lower bone
        # tip (joint 2) is left as None -> it follows the chain.
        self.apply_rotate = True       # reorient the joints...
        self.apply_translate = False   # ...keep their rest translate (bone lengths)
        self.apply_scale = False
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.006 ms** -> best **0.006 ms** (**1.00x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.006 ms | -- | -- |
| 01 | `scalar_solve_cached_attrs` | lower the 3-joint IK solve from nd::Array temporaries to plain doubles and replace the ten per-solve string findPlug() lookups with cached attribute MObjects | 1.60x | -- | 9.2 min | rejected: parity fail |
| 02 | `scalar_lower_solve` | Hand-lower the nd::Array solve to stack scalars and cache the attribute handles -- then discover by ablation that doSolve() is entirely below the benchmark's noise floor, because the timed region is a Python cmds.getAttr and not the solve. | 1.60x | -- | 11.3 min | rejected: parity fail |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `scalar_solve_cached_attrs` -- predicted 1.60x, **rejected: parity fail**. authored @maya_test FAILED: test_two_bone_ik: knee barely bends (rotateX=0.00)
* `scalar_lower_solve` -- predicted 1.60x, **rejected: parity fail**. authored @maya_test FAILED: test_two_bone_ik: knee barely bends (rotateX=0.00)

### Rejected rounds

* `scalar_solve_cached_attrs` -- rejected: parity fail. authored @maya_test FAILED: test_two_bone_ik: knee barely bends (rotateX=0.00)
* `scalar_lower_solve` -- rejected: parity fail. authored @maya_test FAILED: test_two_bone_ik: knee barely bends (rotateX=0.00)

## Verification

* parity: **FAIL**  (maxerr 2.6645352591003757e-15, tol 0.001)
* authored @maya_test FAILED: test_two_bone_ik: knee barely bends (rotateX=0.00)

## Files

```
build/stages/twoBoneIK/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/twoBoneIK/3_optimized/00_baseline.cpp
build/stages/twoBoneIK/3_optimized/01_scalar_solve_cached_attrs.cpp
build/stages/twoBoneIK/3_optimized/02_scalar_lower_solve.cpp
build/source/twoBoneIK.cpp      SHIPPED
```
