# metaballs -- compile report

**Source node:** `metaballs`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 20:43

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **4.17x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
mats = np.asarray(self.shapeMatrix, dtype=np.float64)
n = mats.shape[0]
shape_type = _dense_over(self.shapeType, np.zeros(n, dtype=np.int64))
additive = _dense_over(self.additive, np.ones(n, dtype=np.int64))
smoothing = _dense_over(self.smoothing, np.zeros(n, dtype=np.float64))
radius = _dense_over(self.radius, np.where(shape_type == 2, 0.5, 1.0))
height = _dense_over(self.height, np.ones(n, dtype=np.float64))
axis = _dense_over(self.axis, np.ones(n, dtype=np.int64))
half = _dense_over(self.halfExtents, np.full((n, 3), 0.5))
packed = _mesh_packed(mats, shape_type, additive, smoothing, radius, height,
                      axis, half, int(self.resolution), float(self.isoValue))
V = int(packed[0])
F = int(packed[1])
points = packed[2:2 + 3 * V].reshape(V, 3)
indices = packed[2 + 3 * V:2 + 3 * V + 4 * F].astype(np.int32)
counts = np.full(F, 4, dtype=np.int32)
self.outMesh = Mesh(points=points, counts=counts, indices=indices)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **2.309 ms** -> best **0.554 ms** (**4.17x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 1.591 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `halfExtents[0] (vector)`, `height[0] (double)`, `isoValue (double)`, `radius[0] (double)`, `resolution (int)`, `shapeMatrix[0] (matrix)`, `smoothing[0] (double)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 2.309 ms | -- | -- |
| 01 | `fuse_field_raw_dmc_thread` | This node is grid-shaped at a much smaller size than the brief implies -- the harness's builtin metaClay scene overrides the generic seeding, so it is 3 shapes on a 48x35x31 lattice, not 20000 shapes -- so the win is removing whole-array temporaries and strided nd:: accessors, then threading the one pass that clears the 50us floor. | 3.00x | 3.36x | 11.6 min | ACCEPTED |
| 02 | `direct_mesh_writeback` | the dual-marching-cubes core now writes MPoint/int output buffers in place and the Maya arrays are built with bulk constructors, deleting a packed-float64 round-trip and ~36k per-element append() API calls | 1.20x | 4.17x | 11.0 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `direct_mesh_writeback` -- predicted 1.20x, measured **4.17x**. this node is GRID-shaped, not QUERY-shaped -- 3 shapes over a ~48x35x31 lattice -- and a previous round had already fused the SDF field evaluation and raw-pointered the DMC traversal, so the arithmetic was no longer the cost. What was left was pure marshalling: DMC wrote _pts/_idx, copied them into a packed float64 array, and compute() then sliced/reshaped/astype'd that array back apart into points/counts/indices, touching every vertex and index five times; the result was then handed to Maya one element at a time through MPointArray::append / MIntArray::append. Removing the round-trip and appending in bulk should cost nothing numerically because int32 -> double -> int64 -> int is exact over these ranges and MPoint(x,y,z) is the same triple either way.

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/metaballs/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/metaballs/3_optimized/00_baseline.cpp
build/stages/metaballs/3_optimized/01_fuse_field_raw_dmc_thread.cpp
build/stages/metaballs/3_optimized/02_direct_mesh_writeback.cpp
build/source/metaballs.cpp      SHIPPED
```
