# rbfWrapDeformer -- compile report

**Source node:** `rbfWrapDeformer`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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
mesh          = self.outputGeometry[0]
rest          = self.restCage.points
deform        = self.deformCage.points
P             = mesh.getPoints()
M             = rest.shape[0]
Md            = deform.shape[0]
Mm            = min(M, Md)
Nn            = P.shape[0]
rc            = (rest * rest).sum(1)
d2            = rc[:, None] + rc[None, :] - 2.0 * (rest @ rest.T)
d2            = np.maximum(d2, 0.0)
K             = np.where(d2 > 1e-12, 0.5 * d2 * np.log(np.maximum(d2, 1e-12)), 0.0)
A             = np.zeros((M + 4, M + 4))
A[:M, :M]     = K
A[:M, M]      = 1.0
A[:M, M + 1:] = rest
A[M, :M]      = 1.0
A[M + 1:, :M] = rest.T
A             = A + 1e-8 * np.eye(M + 4)
T             = np.zeros((M + 4, 3))
T[:Mm, :]     = deform[:Mm, :]
W             = np.linalg.inv(A) @ T
pc            = (P * P).sum(1)
e2            = pc[:, None] + rc[None, :] - 2.0 * (P @ rest.T)
e2            = np.maximum(e2, 0.0)
Ke            = np.where(e2 > 1e-12, 0.5 * e2 * np.log(np.maximum(e2, 1e-12)), 0.0)
H             = np.zeros((Nn, M + 4))
H[:, :M]      = Ke
H[:, M]       = 1.0
H[:, M + 1:]  = P
warped        = H @ W
hasCage       = 1.0 if (M > 0 and M == Md) else 0.0
mesh.setPoints(P + (self.envelope * hasCage) * (warped - P))
```

## Files

```
build/stages/rbfWrapDeformer/1_transpiled.cpp     deterministic transpile (no AI)
build/source/rbfWrapDeformer.cpp      SHIPPED
```
