# sineRipple -- compile report

**Source node:** `sineRipple`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-09 15:23

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **5.55x** over 3 round(s) -- 3 run of max 6, stopped: round 3 gained 1.12x, below the 1.15x needed to continue |

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

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `amplitude (float)`, `frequency (float)`, `speed (float)`, `time (time)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there.

Baseline **19.408 ms** -> best **3.495 ms** (**5.55x**).

Rounds: **3** run of at most 6; the loop stopped because round 3 gained 1.12x, below the 1.15x needed to continue.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 19.408 ms | -- | -- |
| 01 | `fuse_ripple_loop` | collapse the ten whole-array nd:: temporaries (mean, sub, norm, phase, sin, mul, newaxis, mul, add, copy) into one per-vertex loop that reads the mesh's raw floats and writes them back in place | 1.80x | 2.00x | 13.6 min | ACCEPTED |
| 02 | `own_normals_cached_topo` | replace MFnMesh::getVertexNormals (4.3 of 8.8 ms) with Maya's own normal algorithm computed in-node over a cached topology, threaded and fused into the ripple loop | 2.90x | 4.96x | 15.0 min | ACCEPTED |
| 03 | `overlap_mean_with_faces` | launch the face-normal region on the workers only, and do the caller's serial work (the row-order centre sum and the sampled Maya-API topology check) underneath it instead of before it | 1.07x | 5.55x | 18.3 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `own_normals_cached_topo` -- predicted 2.90x, measured **4.96x**. profiling showed getVertexNormals at 4.3 ms plus a 0.7 ms MFloatVectorArray copy while the whole ripple loop was 0.74 ms; a diagnostic round matched Maya's normals to 1.3e-7 (float rounding) with: float32 Newell face normal, normalised, summed UNWEIGHTED per vertex in face order, normalised -- area- and angle-weighted variants were 0.1-0.3 off, so this is the exact algorithm. Topology (CSR faces + vertex->face adjacency) is cached per instance and keyed on numVertices/numPolygons/numFaceVertices/numEdges plus 256 evenly spaced faces' vertex lists re-read each tick via getPolygonVertices; the face pass and the fused vertex-normal+ripple pass run on a persistent per-node condvar pool with a member chunk cursor (MPYNODE_THREADS env cap), the mean stays a serial reduction.
* `overlap_mean_with_faces` -- predicted 1.07x, measured **5.55x**. deform() was 0.95 ms of a 3.5 ms tick, of which ~0.6 ms was the calling thread running the serial mean and the 256-face topology check while 23 pool threads sat idle; the face pass only needs the cached topology, so a cheap counts-only key lets it start first and the caller joins at finish(). Same arithmetic, same fold order, bit-identical.

## Verification

* parity: **pass**
* verify could not run: Unable to create/find dependency node. | authored @maya_test: 1/1 passed

## Files

```
build/stages/sineRipple/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/sineRipple/3_optimized/00_baseline.cpp
build/stages/sineRipple/3_optimized/01_fuse_ripple_loop.cpp
build/stages/sineRipple/3_optimized/02_own_normals_cached_topo.cpp
build/stages/sineRipple/3_optimized/03_overlap_mean_with_faces.cpp
build/source/sineRipple.cpp      SHIPPED
```
