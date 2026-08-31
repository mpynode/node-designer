# sineRippleDefault -- compile report

**Source node:** `sineRippleDefault`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-08-19 11:58

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **7.72x** over 2 round(s) |

## The Python this was generated from

```python
# Sine-ripple deformer: each vertex rides a travelling sine wave along its
# surface normal. The wave's phase advances with distance from the mesh
# centre and with time, so it animates as the timeline plays.
mesh = self.outputGeometry[0]            # writable handle for this output mesh
pts = mesh.getPoints()                   # (N, 3) object-space points (numpy)

# True per-vertex normals (object space). The output handle wraps an API-1
# MFnMesh, so use the in-out MFloatVectorArray form.
nrm = om.MFloatVectorArray()
mesh.getVertexNormals(False, nrm, om.MSpace.kObject)
normals = np.array([[nrm[i].x, nrm[i].y, nrm[i].z]
                    for i in range(nrm.length())], dtype=float)

amp = self.amplitude
freq = self.frequency
speed = self.speed
env = self.envelope               # built-in deformer envelope (0..1)

centre = pts.mean(axis=0)
dist = np.linalg.norm(pts - centre, axis=1)
phase = 2.0 * np.pi * freq * dist - speed * self.time
offset = (amp * np.sin(phase))[:, None] * normals

mesh.setPoints(pts + env * offset)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Baseline **12.997 ms** -> best **1.683 ms** (**7.72x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 12.997 ms | -- | -- |
| 01 | `cache_normals_fuse_thread` | This is an elementwise deformer, so the answer was three layers: collapse the eleven nd:: whole-array temporaries into one fused per-vertex pass, cache the per-vertex normals across evaluations behind a content hash of the input mesh's raw point buffer, and run the surviving per-vertex map on a persistent worker pool. | 3.00x | 5.46x | 12.0 min | ACCEPTED |
| 02 | `raw_mesh_buffers` | profile first, then delete both MPointArray staging copies: read positions from the input mesh's raw float buffer and write the deformed result straight into the output mesh's raw float buffer, so allPositions() and setAllPositions() disappear entirely | 1.35x | 7.72x | 11.9 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_normals_fuse_thread` -- predicted 3.00x, measured **5.46x**. The lowered nd:: chain allocates and streams ~10 arrays of 3N doubles (1.3 MB each at N=159602) to do arithmetic that fits in registers, so it is memory-bound rather than FLOP-bound and a single fused loop should win outright. After fusing, profiling should show whether the residual cost is arithmetic or a Maya API call -- and it turned out to be MFnMesh::getVertexNormals at 2.3 ms of a 3.9 ms deform, which depends only on the input mesh while the benchmark animates the scalars, making it the textbook derived-state cache.
* `raw_mesh_buffers` -- predicted 1.35x, measured **7.72x**. the node arrived already caching normals, centre and a thread pool, so the arithmetic was no longer the cost; an instrumented build showed deform() was only 0.73 ms of the 2.21 ms tick and that 0.51 ms of that 0.73 was pure marshalling -- allPositions() widening 159602 float triples into a 5.1 MB MPointArray and setAllPositions() narrowing them back. Both ends already had a raw float buffer in hand (the fingerprint block calls getRawPoints on the input mesh), and float->double widening is exact, so routing around the staging array is bit-identical rather than merely close.

## Verification

* parity: **pass**
* verify could not run: Unable to create/find dependency node. | authored @maya_test: 1/1 passed

## Files

```
build/stages/sineRippleDefault/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/sineRippleDefault/3_optimized/00_baseline.cpp
build/stages/sineRippleDefault/3_optimized/01_cache_normals_fuse_thread.cpp
build/stages/sineRippleDefault/3_optimized/02_raw_mesh_buffers.cpp
build/source/sineRippleDefault.cpp      SHIPPED
```
