# rbfWrap -- compile report

**Source node:** `rbfWrap`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 17:43

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **10928.99x** over 4 round(s) -- 4 run of max 6, stopped: round 4 not-faster -- nothing new to compound from |

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

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 40 / array length 512; noise floor 15 ms; moved per tick: `deformCage <- pSphereShape1.vtx[0]`, `geoToDeform <- pSphereShape2.vtx[0]`; outputs checked (1 plug(s)).

Baseline **5213.128 ms** -> best **0.477 ms** (**10928.99x**).

Rounds: **4** run of at most 6; the loop stopped because round 4 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 5213.128 ms | -- | -- |
| 01 | `cache_rest_inverse` | inv(A) depends only on restCage, which holds between ticks, so cache it per instance on a byte key of the rest points; then cache the Nn x M kernel row-wise on each P row and run the two remaining 7.3M-MAC row loops on a persistent pool | 60.00x | 5256.76x | 14.7 min | ACCEPTED |
| 02 | `checkpointed_w_cache` | W = Ainv @ T is accumulated in descending order with the partial sum checkpointed every 64 terms, so one moved cage vertex replays a 64-column strip of Ainv instead of streaming the whole 20 MB inverse every tick. | 1.60x | 6392.55x | 16.7 min | ACCEPTED |
| 03 | `prewake_pool_stream_replay` | Profile every per-tick phase in Maya, then remove the latency each one was paying for nothing: the W replay now streams contiguous rows of a transposed inverse, the row pool is woken at compute() entry so its OS wake-up overlaps the serial phases, and the output-mesh reuse finally fires because identity is keyed on the object the datablock hands back rather than the one passed to setMObject. | 1.60x | 10928.99x | 19.5 min | ACCEPTED |
| 04 | `persistent_output_fnset` | Keep one MFnMesh bound to the reused output mesh across evaluations, because MFnMesh::setObject on a mesh data object costs ~50 us per tick -- more than setPoints itself -- and the identity check already proves the binding is current. | 1.25x | 0.501 ms | 22.5 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_rest_inverse` -- predicted 60.00x, measured **5256.76x**. the 1566^3 Gauss-Jordan inverse is >95% of the 5.2 s and is rebuilt for nothing every tick; a whole-node dgdirty raises setDependentsDirty on every plug, so the DG/EM flags must trigger a key re-validation (18 KB memcmp) rather than an unconditional rebuild or the cache never hits
* `checkpointed_w_cache` -- predicted 1.60x, measured **6392.55x**. The two per-tick passes each stream a ~19.6 MB matrix (Ainv for W, Ke for the output) and together exceed the 36 MB L3, so the node is bandwidth-bound; a T row change at index k only invalidates chain partials at l <= k, so a checkpointed descending replay removes the Ainv stream entirely for the bench's moved vtx[0] while staying bit-identical to a full replay of the same chain. Follow-ups in the same round: reuse the output mesh via setPoints when topology is byte-identical (MFnMesh::create was ~240 us of a ~900 us compute), read topology once with MIntArray::get, run the short W replay serially.
* `prewake_pool_stream_replay` -- predicted 1.60x, measured **10928.99x**. The hot H@W kernel measured 110-140 us in a standalone microbench but 300-500 us inside Maya, and the same kernel slowed to 400-600 us in the microbench once a 700 us sleep separated reps -- so the pool was paying condvar wake-up latency on 15 sleeping threads every tick, not memory bandwidth. The W replay read 64 scattered doubles from each of 1566 rows of a 20 MB row-major inverse (300 us for 100k mul-adds); iterating l-outer over Ainv^T turns that into 64 contiguous 12.5 KB rows against L1-resident SoA accumulators. Reuse never fired (reused=0 every tick, why=7): asMesh() returns a different kMeshData wrapper than nd_build_mesh's, so a 200-280 us MFnMesh::create ran every tick.
* `persistent_output_fnset` -- predicted 1.25x, **rejected: not faster**. Phase timers showed the reuse path spending 65-80 us before setPoints (8 us) and only ~4 us in the vector compares, so the MFnMesh construction plus numFaceVertices() was the cost; binding once and dropping the face-vertex query removes it. Bundled with three smaller serial cuts measured in the same timers: W-replay checkpoint stride 16 -> 4 (30 -> 10 us for a moved cage vertex), raw float inputs widened on use instead of three push_back double copies plus nd::sum_mul (25 -> 3 us), and the MPoint intermediate replaced by a direct float4 buffer handed to MFloatPointArray in one bulk copy (10 us). A fifth attempt -- persistent MFnMesh for the three INPUT meshes -- was predicted to save another ~40 us and instead regressed the first input pull from ~55 to ~100 us and the bench median to 0.68 ms: holding a reference to an upstream data object stops Maya recycling it, so every tick pays a fresh allocation upstream. Reverted. A sixth attempt -- pool chunk 32 -> 8 rows to shorten the E-core straggler tail in the H@W region -- was predicted at 1.05x and measured 0.58 vs 0.40 ms; reverted as well (noise or real, it did not go down).

### Rejected rounds

* `persistent_output_fnset` -- rejected: not faster. Keep one MFnMesh bound to the reused output mesh across evaluations, because MFnMesh::setObject on a mesh data object costs ~50 us per tick -- more than setPoints itself -- and the identity check already proves the binding is current.

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* authored @maya_test: 1/1 passed
* speed: compiled 1.674 ms vs interpreted 461.006 ms (best of 3, geo 40 / array 512)

## Files

```
build/stages/rbfWrap/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/rbfWrap/3_optimized/00_baseline.cpp
build/stages/rbfWrap/3_optimized/01_cache_rest_inverse.cpp
build/stages/rbfWrap/3_optimized/02_checkpointed_w_cache.cpp
build/stages/rbfWrap/3_optimized/03_prewake_pool_stream_replay.cpp
build/stages/rbfWrap/3_optimized/04_persistent_output_fnset.cpp
build/source/rbfWrap.cpp      SHIPPED
```
