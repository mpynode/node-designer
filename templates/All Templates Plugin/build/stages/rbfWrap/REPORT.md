# rbfWrap -- compile report

**Source node:** `rbfWrap`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# RBF thin-plate-spline WRAP: a smooth space warp defined by two control cages of
# identical topology -- `restCage` (rest positions) and `deformCage` (deformed
# positions) -- carries every point of `geoToDeform` from rest to deformed space
# and emits the result on `outGeo`. The warp is the classic thin-plate spline:
# kernel phi(r) = r^2 * log(r) (== 0.5 * d2 * log(d2), so no sqrt) plus an affine
# polynomial tail, so a rigid/affine cage motion is reproduced EXACTLY and a
# non-affine cage motion bends the geometry as smoothly as possible.
#
# The whole compute lowers to PURE C++ (byte-exact interp-vs-compiled): pairwise
# squared distances (matmul-identity form), the guarded r^2 log r kernel (via
# where/maximum -- no nan to clean up), the augmented (M+4) system built with
# zeros + slice-stores, Tikhonov-regularised and solved by nd::inv, then the
# evaluation matmul. A tiny 1e-8*I keeps the solve off nd::inv's singular
# fallback (and makes the empty-cage eager-eval a clean no-op, not a raise), and
# tightens interp(LAPACK)-vs-compiled(Gauss-Jordan) agreement. This is an mPyNode
# with THREE mesh INPUTS + one mesh OUTPUT (the #83 geo-I/O path) -- the only node
# shape that reads multiple meshes AND emits a mesh AND lowers deterministically.
rest = self.restCage.points
deform = self.deformCage.points
P = self.geoToDeform.points
counts = self.geoToDeform.counts
indices = self.geoToDeform.indices
M = rest.shape[0]
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
T[:M, :] = deform
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
self.outGeo = Mesh(points=warped, counts=counts, indices=indices)
```

## Files

```
build/stages/rbfWrap/1_transpiled.cpp     deterministic transpile (no AI)
build/source/rbfWrap.cpp      SHIPPED
```
