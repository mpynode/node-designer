# sineRipple -- compile report

**Source node:** `sineRipple`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-08 23:23

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **5.82x** over 2 round(s) -- re-measured: **2.98x** (outputs match) |

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

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **9.759 ms** -> best **1.676 ms** (**5.82x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 300 / array length 10000: baseline 15.765 ms -> shipped 5.291 ms (**2.98x**); outputs match. The speedup above was taken before the gate existed; this is the number to quote. Moved per tick: `amplitude (float)`, `frequency (float)`, `speed (float)`, `time (time)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 9.759 ms | -- | -- |
| 01 | `cache_normals_skip_geo_pull` | fuse the six whole-array nd:: temporaries into one per-vertex pass, then key a per-node vertex-normal cache on a bitwise fingerprint of the input points so a cache hit never calls outputArrayValue(input) at all | 3.00x | 3.71x | 13.2 min | ACCEPTED |
| 02 | `raw_points_inplace` | deform in place on the output mesh's own packed float array from getRawPoints, instead of round-tripping every vertex through a 5.1 MB MPointArray of doubles via MItGeometry::allPositions/setAllPositions | 1.30x | 5.82x | 13.2 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `raw_points_inplace` -- predicted 1.30x, measured **5.82x**. instrumenting deform() showed 890 us of the 2.38 ms compute was mine and 535 us of that was the two MPointArray conversions alone -- allPositions 355 us, setAllPositions 180 us -- so removing both copies should take deform to ~350 us; the transform is bit-exact because the existing path was already float->double->compute->float and getRawPoints just removes the two intermediate double buffers

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.001)
* authored @maya_test: 1/1 passed

## Files

```
build/stages/sineRipple/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/sineRipple/3_optimized/00_baseline.cpp
build/stages/sineRipple/3_optimized/01_cache_normals_skip_geo_pull.cpp
build/stages/sineRipple/3_optimized/02_raw_points_inplace.cpp
build/source/sineRipple.cpp      SHIPPED
```
