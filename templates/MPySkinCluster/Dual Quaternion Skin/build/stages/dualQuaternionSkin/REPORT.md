# dualQuaternionSkin -- compile report

**Source node:** `dualQuaternionSkin`  ·  **Base:** `MPxSkinCluster`  ·  **Generated:** 2026-09-08 23:29

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **2.75x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# ----------------------------------------------------------------------
# mPySkinCluster -- default Compute source: dual quaternion skinning (DQS)
#
# The skinning math is the blessed API method self.dual_quaternion(rest,
# weights, joint, bind). Every operand is passed EXPLICITLY -- the method reads
# nothing off self -- so the plug dependencies are visible right here. They are
# the same plugs Maya's Component Editor / Paint Skin Weights / skinPercent edit:
#   self.weightList     -> dense (N, J) per-vertex, per-influence weights
#   self.matrix         -> (J, 4, 4) live joint WORLD matrices
#   self.bindPreMatrix  -> (J, 4, 4) joint bind-pose inverse matrices
# It blends each influence's rigid transform as a unit dual quaternion, so a bent
# joint keeps its volume (no LBS "candy-wrapper" collapse), and returns the
# deformed object-space points (N, 3); the envelope + write stay here so
# partial-effect composition is explicit.
#
# self.outputGeometry[0] is the writable mesh handle (object-space rest points).
# A deformer cannot change topology -- setPoints must keep the same N.
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

# Dual quaternion skinning of the rest points (envelope=0 rest, 1 fully skinned).
mesh.setPoints(rest + float(self.envelope) * (
    self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)
    - rest))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **1.787 ms** -> best **0.651 ms** (**2.75x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 5.959 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 1.787 ms | -- | -- |
| 01 | `reuse_point_buffers` | the node is elementwise, not query-shaped, so the win was deleting whole-array temporaries: adopt the marshalling vector instead of copying it, reuse the MPointArray and the point buffer across evaluations, and stop heap-allocating an empty buffer for every one of the ~90 nd::Array locals | 1.60x | 1.73x | 10.7 min | ACCEPTED |
| 02 | `raw_points_read` | read the rest points straight off MFnMesh::getRawPoints() and widen float->double in one pass, instead of materialising a 159k-element MPointArray with MItGeometry::allPositions() and then re-reading it | 1.50x | 2.75x | 10.1 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `raw_points_read` -- predicted 1.50x, measured **2.75x**. this node is ELEMENTWISE, not query-shaped, and at the benchmark's sizes the arithmetic is nil -- every array input is empty (the spec declares no inputs, so matrix/bindPreMatrix/weightList arrive with 0 elements) while the mesh is 159,602 verts. So the whole cost is per-vertex marshalling: allPositions() writes 5.1 MB of (x,y,z,1) doubles that we immediately re-read into a (N,3) double buffer. Taking the mesh's float positions directly off the already-computed outputGeom handle removes one full 5.1 MB materialisation and turns the marshal into a single 1.9 MB read / 3.8 MB write widening loop.

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.001)
* authored @maya_test: 1/1 passed

## Files

```
build/stages/dualQuaternionSkin/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/dualQuaternionSkin/3_optimized/00_baseline.cpp
build/stages/dualQuaternionSkin/3_optimized/01_reuse_point_buffers.cpp
build/stages/dualQuaternionSkin/3_optimized/02_raw_points_read.cpp
build/source/dualQuaternionSkin.cpp      SHIPPED
```
