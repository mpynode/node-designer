# rbfWrapDeformer -- compile report

**Source node:** `rbfWrapDeformer`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-09 14:57

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **6616.12x** over 2 round(s) -- 2 run of max 6, stopped: round 2 no-change -- nothing new to compound from |

## The Python this was generated from

```python
# RBF thin-plate-spline WRAP, as a DEFORMER. Two control cages of identical
# topology -- `restCage` (rest positions) and `deformCage` (deformed positions) --
# define a smooth space warp that carries every point of the deformed geometry
# from rest to deformed space. The warp is the classic thin-plate spline: kernel
# phi(r) = r^2 * log(r) (== 0.5 * d2 * log(d2), so no sqrt) plus an affine
# polynomial tail, so a rigid/affine cage motion is reproduced EXACTLY and a
# non-affine cage motion bends the geometry as smoothly as possible.
#
# Unlike the mPyNode rbf_wrap (three mesh INPUTS + a mesh OUTPUT), the geometry to
# deform is the deformer's own `outputGeometry` -- so this node stacks in a normal
# deformation chain and honours `envelope` (0 = rest, 1 = fully warped).
#
# A deformer is LIVE the moment mc.deformer() creates it, so the never-connected
# and mismatched cage states are normal, not exotic. `hasCage` is a purely NUMERIC
# no-op gate (no try/except -- that would drop the node to the AI porter): the
# warp is only applied when both cages carry points AND agree on point count.
# `Mm` clamps the deform-cage copy so a half-wired node never shape-mismatches.
# (Note: DISCONNECTING a cage does not reach this gate -- Maya retains the last
# mesh in the datablock, so the compute keeps seeing the old point count.)
#
# The whole compute lowers to PURE C++: pairwise squared distances (matmul-identity
# form), the guarded r^2 log r kernel (via where/maximum -- no nan to clean up),
# the augmented (M+4) system built with zeros + slice-stores, Tikhonov-regularised
# and solved by nd::inv, then the evaluation matmul. A tiny 1e-8*I keeps the solve
# off nd::inv's singular fallback and tightens interp(LAPACK)-vs-compiled
# (Gauss-Jordan) agreement.
#
# WARNING: getPoints()/setPoints() are OBJECT space while the cages are read in
# WORLD space (worldMesh), so this is only correct when the deformed mesh has an
# identity transform at the world origin (freeze its transform).
mesh = self.outputGeometry[0]
rest = self.restCage.points
deform = self.deformCage.points
P = mesh.getPoints()
M = rest.shape[0]
Md = deform.shape[0]
Mm = min(M, Md)
Nn = P.shape[0]
rc = (rest * rest).sum(1)
d2 = rc[:, None] + rc[None, :] - 2.0 * (rest @ rest.T)
d2 = np.maximum(d2, 0.0)
K = np.where(d2 > 1e-12, 0.5 * d2 * np.log(np.maximum(d2, 1e-12)), 0.0)
A = np.zeros((M + 4, M + 4))
A[:M, :M] = K
A[:M, M] = 1.0
A[:M, M + 1:] = rest
A[M, :M] = 1.0
A[M + 1:, :M] = rest.T
A = A + 1e-8 * np.eye(M + 4)
T = np.zeros((M + 4, 3))
T[:Mm, :] = deform[:Mm, :]
W = np.linalg.inv(A) @ T
pc = (P * P).sum(1)
e2 = pc[:, None] + rc[None, :] - 2.0 * (P @ rest.T)
e2 = np.maximum(e2, 0.0)
Ke = np.where(e2 > 1e-12, 0.5 * e2 * np.log(np.maximum(e2, 1e-12)), 0.0)
H = np.zeros((Nn, M + 4))
H[:, :M] = Ke
H[:, M] = 1.0
H[:, M + 1:] = P
warped = H @ W
hasCage = 1.0 if (M > 0 and M == Md) else 0.0
mesh.setPoints(P + (self.envelope * hasCage) * (warped - P))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 40 / array length 512; noise floor 15 ms; moved per tick: `deformCage <- pSphereShape2.vtx[0]`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`; outputs checked (1 plug(s)).

Baseline **4921.733 ms** -> best **0.744 ms** (**6616.12x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 4921.733 ms | -- | -- |
| 01 | `cache_inverse_thread_rows` | cache the (M+4)x(M+4) Gauss-Jordan inverse on the rest cage's bytes, cache the evaluation matrix H row-by-row on each point's bytes, and run the two remaining per-row matmuls (Ainv@T, H@W) as a deterministic parallel map on a persistent per-node pool | 500.00x | 6616.12x | 15.1 min | ACCEPTED |
| 02 | `merge_pool_regions` | fold the two per-tick worker wake-ups (W = Ainv@T, then out = H@W) into one pool job with an in-region completion barrier; measured slower on both barrier flavours, so the file is left at the round's entry state | 1.10x | -- | 21.4 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_inverse_thread_rows` -- predicted 500.00x, measured **6616.12x**. the whole 4.9 s is the O(M^3) nd::inv of a 1566x1566 system that depends only on restCage, which HOLDS between ticks; deformCage and one input vertex move, so per tick only W = Ainv@T (7.4 MFLOP), one H row (1562 logs) and warped = H@W (7.3 MFLOP) need recomputing; every accumulation keeps nd::matmul/sum_mul's order (acc starts at 0, ascending terms, a*b operand order), so the result is bit-identical to the unoptimised lowering
* `merge_pool_regions` -- predicted 1.10x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `merge_pool_regions` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**
* verify could not run: Unable to create/find dependency node. | authored @maya_test: 1/1 passed

## Files

```
build/stages/rbfWrapDeformer/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/rbfWrapDeformer/3_optimized/00_baseline.cpp
build/stages/rbfWrapDeformer/3_optimized/01_cache_inverse_thread_rows.cpp
build/source/rbfWrapDeformer.cpp      SHIPPED
```
