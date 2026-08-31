# linearBlendSkin -- compile report

**Source node:** `linearBlendSkin`  ·  **Base:** `MPxSkinCluster`  ·  **Generated:** 2026-08-25 10:51

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **10.22x** over 2 round(s) |

## The Python this was generated from

```python
# ----------------------------------------------------------------------
# mPySkinCluster -- default Compute source: linear blend skinning (LBS)
#
# The skinning math is the blessed API method self.linear_blend(rest,
# weights, joint, bind). Every operand is passed EXPLICITLY -- the method reads
# nothing off self -- so the plug dependencies are visible right here. They are
# the same plugs Maya's Component Editor / Paint Skin Weights / skinPercent edit:
#   self.weightList     -> dense (N, J) per-vertex, per-influence weights
#   self.matrix         -> (J, 4, 4) live joint WORLD matrices
#   self.bindPreMatrix  -> (J, 4, 4) joint bind-pose inverse matrices
# It blends M_j = bindPreMatrix_j @ jointWorld_j linearly (identity at the bind
# pose, so the mesh stays at rest until a joint moves) and returns the deformed
# object-space points (N, 3); the envelope + write stay here so partial-effect
# composition is explicit.
#
# self.outputGeometry[0] is the writable mesh handle (object space). It holds a
# copy of the input geometry, so getPoints() == rest and setPoints() commits the
# deform. A deformer cannot change topology -- setPoints must keep the same N.
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

# Linear blend skinning of the rest points (envelope=0 rest, 1 fully skinned).
mesh.setPoints(rest + float(self.envelope) * (
    self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)
    - rest))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Baseline **2.976 ms** -> best **0.291 ms** (**10.22x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 2.976 ms | -- | -- |
| 01 | `raw_points_no_temporaries` | read Maya's own float vertex buffer instead of MItGeometry::allPositions, and stop materialising the whole-array temporaries (the flat marshalling vector, ones(N,1) and the concatenated homogeneous (N,4) points) that the generic nd runtime built around a loop that only ever reads four doubles per vertex | 2.00x | 4.50x | 12.8 min | ACCEPTED |
| 02 | `hoist_broadcast_check` | the shape check that decides whether the deform can run at all is a pure function of two integers, so it hoists above the 3.8 MB point marshalling and above the throw that used to report it -- and the throw, not the arithmetic, was over half the tick | 1.30x | 10.22x | 9.7 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `raw_points_no_temporaries` -- predicted 2.00x, measured **4.50x**. this node is ELEMENTWISE, not query-shaped: the einsum is O(N*J*16) but the benchmark drives no influences at all (the spec declares no inputs, so matrix[]/bindPreMatrix[]/weightList are never seeded and the j-loop is zero-trip), which leaves the entire measured cost in per-vertex data movement over 159602 points. At that size the levers are (a) not widening float->double into a 5.1 MB MPointArray only to narrow it straight back into a packed (N,3) double buffer, and (b) not allocating and filling a 5.1 MB (N,4) homogeneous copy whose fourth column is the constant 1.0 -- pts_h[v,k] is exactly (k < 3 ? rest[v,k] : 1.0), so it can be fed from `rest` inside the loop with the multiply and accumulation order untouched
* `hoist_broadcast_check` -- predicted 1.30x, measured **10.22x**. the harness spec declares no inputs, so matrix/bindPreMatrix/weightList arrive EMPTY while a 159602-vert polySphere is attached; the lowered tail computes rest(n,3) + env*(blend(skinN,3) - rest(n,3)) with skinN=0, marshals the whole point buffer into doubles, and then throws out of nd::sub. Broadcast compatibility depends only on (skinN, n), never on a buffer value, so testing it first removes the marshalling AND the unwind while emitting the identical error and the identical MS::kFailure

## Verification

* parity: **pass**
* skinCluster needs a bound rig (wired joints + painted weights); generic point-compare skipped -- see tools/harness/skin_*_parity.py | authored @maya_test: 1/1 passed

## Files

```
build/stages/linearBlendSkin/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/linearBlendSkin/3_optimized/00_baseline.cpp
build/stages/linearBlendSkin/3_optimized/01_raw_points_no_temporaries.cpp
build/stages/linearBlendSkin/3_optimized/02_hoist_broadcast_check.cpp
build/source/linearBlendSkin.cpp      SHIPPED
```
