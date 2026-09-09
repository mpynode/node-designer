# unitSphereCollision -- compile report

**Source node:** `unitSphereCollision`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-08 23:23

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **15.90x** over 2 round(s) -- re-measured: **10.23x** (outputs match) |

## The Python this was generated from

```python
# Unit-sphere collision deformer (accumulating "pusher" port). Every vertex
# INSIDE the collider sphere is pushed onto its surface, and the pushed result
# is kept in a persistent buffer (self.positions) so the deformation BAKES --
# once the collider passes, the dent stays put (it does not spring back). The
# collider is the UNIT sphere in the local space of the `pusher` matrix, so
# wiring a sphere transform's worldMatrix into `pusher` makes its translate /
# rotate / scale set the collider's centre, orientation and effective radius.
#
# self.positions is registered + seeded by the node's setup from the mesh's
# initial points; if it is missing or stale (topology change) it is re-seeded
# here from the current input. A deformer is not evaluated until a mesh is
# connected, so nothing computes before then.
#
# WARNING: getPoints()/setPoints() are OBJECT space while `pusher` is a WORLD
# matrix, so this is only correct when the deformed mesh has an identity
# transform at the world origin (freeze its transform).
mesh = self.outputGeometry[0]
pts = mesh.getPoints()                         # (N, 3) current input, object space
if len(pts):
    seed = np.hstack([np.asarray(pts, dtype=float), np.ones((len(pts), 1))])
    try:
        buf = np.asarray(self.positions, dtype=float)
    except Exception:
        buf = None
    if buf is None or buf.ndim != 2 or buf.shape != (len(pts), 4):
        buf = seed                             # first eval / topology change -> seed

    P = buf.copy()
    M = self.pusher                            # collider world matrix (MatrixView)
    inv = M.inverse().asNumpy()                # api2 analytic inverse (EM-safe)
    fwd = np.asarray(M, dtype=float)

    local = P @ inv                            # accumulated buffer -> collider local
    dist = np.linalg.norm(local[:, :3], axis=1)
    inside = (dist > 0.0) & (dist < 1.0)       # guard dist==0 (no push direction)
    local[inside, :3] = local[inside, :3] / dist[inside, None]   # onto surface
    P = local @ fwd                            # back to object space (buffer accumulates)

    self.positions = P                         # persist the baked buffer
    env = self.envelope                 # blend the baked buffer against rest
    mesh.setPoints(pts + env * (P[:, :3] - pts))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **26.243 ms** -> best **1.651 ms** (**15.90x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 300 / array length 10000: baseline 23.979 ms -> shipped 2.344 ms (**10.23x**); outputs match. The speedup above was taken before the gate existed; this is the number to quote. Moved per tick: `pusher (matrix)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 26.243 ms | -- | -- |
| 01 | `drop_dead_adjacency` | the deform() prologue built a full CSR vertex-adjacency table that the ported compute never reads; deleting it, then moving the per-vertex map onto raw in-place double* and a persistent pool, took 29.4 ms to 2.1 ms | 6.00x | 12.59x | 9.1 min | ACCEPTED |
| 02 | `raw_float_mesh_points` | Stop round-tripping 160k verts through MItGeometry's MPointArray. Fetch the output mesh from the datablock and read/write its own float[3n] point store in place, so the 5.1 MB allocation, the float->double widen and the double->float narrow all disappear. | 1.60x | 15.90x | 10.7 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `drop_dead_adjacency` -- predicted 6.00x, measured **12.59x**. this node is ELEMENTWISE, not query-shaped -- the ported math is ~40 flops over 159,602 verts and cannot be 26 ms on its own, so the cost has to be somewhere other than the arithmetic. It was: codegen scaffolding walked MItMeshVertex over every vertex calling getConnectedVertices + sort + unique into a heap-allocated inner std::vector per vertex, filled adjStart/adjNbr, and the ported region then never referenced either. With that gone the remaining cost is transport, not compute, so the next levers are per-access overhead (MPointArray::operator[] is an out-of-line call into the Maya dylib, ~6 per vertex) and whole-array temporaries, exactly as the ELEMENTWISE branch of the brief predicts.
* `raw_float_mesh_points` -- predicted 1.60x, measured **15.90x**. This node is ELEMENTWISE, not QUERY: one fixed 2x-matvec + sqrt per vertex, no inner scan, so there is no acceleration structure to build and the arithmetic is not the lever. The prior round had already hoisted the matrices, cached the accumulating buffer per-instance and threaded the map, which left the Maya-side bulk transfer as the largest thing still inside deform(). MItGeometry exposes only MPointArray for bulk access (I checked MItGeometry.h -- there is no MFloatPointArray overload), so allPositions()/setAllPositions() cost a 5.1 MB heap array plus a widen of 479k floats and a narrow back. MFnMesh::getRawPoints() hands back the mesh's actual float[3n] buffer; const_cast'ing it and writing in place performs exactly the same two casts the Maya calls perform internally, so the values are bit-identical while per-eval traffic drops from ~34 MB to ~14 MB. Guarded on the geometry really being a mesh with full membership (nv == iter.count()), with the original MPointArray path kept as the fallback, and closed with updateSurface() so the bbox/normal caches invalidate exactly as setPoints would.

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.001)
* authored @maya_test: 1/1 passed

## Files

```
build/stages/unitSphereCollision/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/unitSphereCollision/2_assisted.cpp       AI filled the unported region(s)
build/stages/unitSphereCollision/3_optimized/00_baseline.cpp
build/stages/unitSphereCollision/3_optimized/01_drop_dead_adjacency.cpp
build/stages/unitSphereCollision/3_optimized/02_raw_float_mesh_points.cpp
build/source/unitSphereCollision.cpp      SHIPPED
```
