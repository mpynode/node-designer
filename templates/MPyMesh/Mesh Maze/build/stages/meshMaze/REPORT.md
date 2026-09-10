# meshMaze -- compile report

**Source node:** `meshMaze`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 18:02

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **34.37x** over 4 round(s) -- 4 run of max 6, stopped: round 4 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# Build a maze on the incoming mesh and output its WALLS as geometry.
#
#   1. Key every face-vertex edge as one int64 and group them. Two incident
#      faces -> an interior edge, and an arc of the DUAL graph. One -> a
#      boundary edge. Three or more -> non-manifold, kept out of the dual.
#   2. Randomized DFS over the dual from `start`, refusing to carve into `end`
#      until the stack is `solutionLength` of the mesh deep. The edges it walks
#      through are the DOORS, and they form a spanning tree of whatever the DFS
#      could reach -- so every reached face is connected to every other by
#      exactly one path, and start -> end is solvable by construction.
#   3. Every other edge that touches a reached face becomes a wall: a slab
#      standing on the edge, extruded along the two ends' VERTEX NORMALS.
#
# Faces the DFS could NOT reach are left completely bare. That is the whole
# difference from the textbook algorithm, which re-seeds until the maze covers
# the mesh and raises when it cannot: unwelded verts, bowties and T-junctions
# fragment the dual on real geometry, and a bare patch is a far better answer
# than a red node. Bad `start` / `end` indices, degenerate faces and
# non-manifold edges degrade the same way. Nothing here ever raises.
import numpy as np
from mpynode._api2.geometry import Mesh

src = getattr(self, "inMesh", None)
pts = None if src is None else getattr(src, "points", None)
pts = None if pts is None else np.asarray(pts, dtype=np.float64)
counts = None if src is None else getattr(src, "counts", None)
counts = None if counts is None else np.asarray(counts, dtype=np.int64)
indices = None if src is None else getattr(src, "indices", None)
indices = None if indices is None else np.asarray(indices, dtype=np.int64)

if (pts is None or counts is None or indices is None
        or pts.shape[0] == 0 or counts.shape[0] == 0
        or int(counts.sum()) != int(indices.shape[0])):
    # No input, an empty one, or a point cloud with no faces to use as cells
    # -> an empty but VALID mesh, never a raise.
    self.outMesh = Mesh()
else:
    n_verts = int(pts.shape[0])
    n_faces = int(counts.shape[0])

    # Vertex normals are what the walls stand up along. A value mesh may carry
    # none; fall back to +Y so the node still emits geometry.
    nrm = getattr(src, "normals", None)
    nrm = None if nrm is None else np.asarray(nrm, dtype=np.float64)
    if nrm is None or int(nrm.shape[0]) != n_verts:
        nrm = np.zeros((n_verts, 3), dtype=np.float64)
        nrm[:, 1] = 1.0

    # A NEGATIVE index counts back from the end, so the documented
    # `end = -1` -> LAST face is just the general rule with no special case.
    # Anything still out of range is CLAMPED: a typo in a face id has to
    # degrade to a maze somewhere else on the mesh, never to a red node.
    start = int(self.start)
    end = int(self.end)
    if start < 0:
        start = n_faces + start
    if end < 0:
        end = n_faces + end
    start = min(max(start, 0), n_faces - 1)
    end = min(max(end, 0), n_faces - 1)

    key, fv_face = _maze_edges(counts, indices, n_verts)
    uniq, inv, ei, adj_start, deg, adj_dst, adj_eid = _maze_dual(
        key, fv_face, n_faces)

    # The gate is a FRACTION of the face count rather than an absolute cell
    # count, so the same setting means the same thing after a subdivide.
    #
    # `sol_len` -- the achieved solution length -- goes nowhere: the node has
    # no output for it and the walls do not depend on it. It is returned
    # because the build gate and the authored test assert on it.
    want = int(float(self.solutionLength) * float(n_faces))
    visited, door, sol_len = _maze_carve(
        n_faces, adj_start, deg, adj_dst, adj_eid, int(ei.shape[0]),
        start, end, want, int(self.seed))

    # An edge is LIVE when any face it touches was reached. Doors are carved
    # out of the live set; everything else in it -- the interior edges the tree
    # passed over, every boundary edge, and any non-manifold edge that never
    # entered the dual -- is a wall. An edge touching only unreached faces is
    # in neither, which is exactly what leaves an unreachable patch bare.
    live = np.zeros(int(uniq.shape[0]), dtype=np.bool_)
    live[inv[visited[fv_face]]] = True
    is_door = np.zeros(int(uniq.shape[0]), dtype=np.bool_)
    is_door[ei[door]] = True
    wall = np.nonzero(live & ~is_door)[0]

    if int(wall.shape[0]) == 0:
        self.outMesh = Mesh()
    else:
        k = uniq[wall]
        va = k // np.int64(n_verts)
        vb = k - va * np.int64(n_verts)
        wp, wc, wi = _maze_walls(pts, nrm, va, vb,
                                 float(self.wallHeight),
                                 0.5 * float(self.wallThickness))
        self.outMesh = Mesh(points=wp, counts=wc, indices=wi)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 140 / array length 5000; noise floor 15 ms; moved per tick: `end (int)`, `inMesh <- pSphereShape1.vtx[0]`, `seed (int)`, `solutionLength (double)`, `start (int)`, `wallHeight (double)`, `wallThickness (double)`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there.

Baseline **30.521 ms** -> best **0.888 ms** (**34.37x**).

Rounds: **4** run of at most 6; the loop stopped because round 4 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 30.521 ms | -- | -- |
| 01 | `reuse_out_mesh_setpoints` | the slab soup's topology is a pure function of the wall count, so on a repeat count the datablock's own output mesh is updated in place with float setPoints instead of being rebuilt by MFnMesh::create; the topology-derived dual graph is cached per instance on a byte compare of counts+connectivity, vertex normals come from the one bulk float call the Python reference makes, and positions are read off the mesh's raw float store | 4.00x | 9.68x | 24.2 min | ACCEPTED |
| 02 | `raw_store_output` | on the reused output mesh, write the wall soup straight into the mesh's own float store (getRawPoints) and signal with updateSurface instead of staging xyzw and calling setPoints, which was 1.7 of 3.9 ms; then thread the flat wall map on a persistent per-node pool and read the carve's adjacency through raw pointers so the visited/door byte stores stop forcing vector-pointer reloads | 1.90x | 15.85x | 24.8 min | ACCEPTED |
| 03 | `own_vertex_normals` | Replace MFnMesh::getVertexNormals (700 us, 37% of the tick) with the node's own float32 Newell face normals averaged per vertex on the persistent pool, measured to match Maya within 1.8e-7; then interleave the dual-graph adjacency into (dst, eid) pairs so the serial DFS carve touches one cache line per step. | 1.60x | 34.37x | 22.2 min | ACCEPTED |
| 04 | `incremental_normals` | recompute vertex normals only for the faces a moved vertex touches, keep the MFnMesh bound to the reused output mesh across ticks, and take the adj_start hop out of the carve's dependent-load chain | 1.25x | 1.123 ms | 22.9 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `reuse_out_mesh_setpoints` -- predicted 4.00x, measured **9.68x**. profiling showed MFnMesh::create + tearing down the previous 155k-point mesh was ~23 of 30 ms; every other phase (normals 1.9, dual 1.3, walls 1.9, carve 0.6) was small by comparison, so the win had to come from not re-creating the mesh each tick. setPoints(MPointArray) still cost 12 ms because it narrows per point; MFloatPointArray built from one raw float[4] soup dropped it to ~2.6 ms. Only a vertex position moves between ticks, so the dual graph is a full-key cache hit.
* `raw_store_output` -- predicted 1.90x, measured **15.85x**. setPoints spends its time on per-point accessor calls and internal bookkeeping, not on the 2.5 MB copy, so a direct write into the store plus one updateSurface removes almost all of it (measured: 1700 us -> 30 us); the wall soup is a pure per-wall map so an 8-lane condvar pool takes it from ~430 us to ~90 us; the carve DFS indexes std::vectors while storing unsigned char flags, and char stores may alias the vectors' data pointers, so hoisting raw pointers should cut ~10-20% of its 450 us (measured: ~240 us off the median); the fused live/door/wall-list pass and the LCG mask were expected to be small and were neutral
* `own_vertex_normals` -- predicted 1.60x, measured **34.37x**. Per-phase timers showed normals 700 us, carve 500 us, wall list 155 us, soup 180 us, input 160 us. Maya's vertex normal is the float32 mean of normalized Newell face normals (unnormalized/area-weighted was 1e-2 off, double precision 5e-5 off, float32 normalized 1.8e-7 off with 20% bit-identical), so two parallel maps over faces then vertices reproduce it inside the 1e-4 parity tolerance. The carve is latency-bound on dependent L2 loads across adj_start, adj_dst and adj_eid, so pairs plus pair-valued candidates cut two dependent loads per step. When every face is reached, the frontier sweep is a no-op and every edge is live, so both are skipped exactly; the candidate collect and wall pass go branchless to kill mispredicts on the random walk.
* `incremental_normals` -- predicted 1.25x, **rejected: not faster**. phase timers put the 0.82 ms at: input fetch 235 us (of which MFnMesh::setObject ~45), normals 60-90, carve ~340, soup ~80. One moved vertex dirties ~4 faces / ~9 vertices, so a bit-compare of positions against a snapshot (~15 us) replaces two 19k-element parallel maps; the output mesh is ours and identity-checked, so its function set can stay bound (saves the ~45 us bind); the DFS is latency-bound on adj_start[cur] -> adj[base+k] -> visited[dst], so a fixed-stride adjacency computes base arithmetically and a magic-multiply modulo replaces the mispredicting switch on the candidate count

### Rejected rounds

* `incremental_normals` -- rejected: not faster. recompute vertex normals only for the faces a moved vertex touches, keep the MFnMesh bound to the reused output mesh across ticks, and take the adj_start hop out of the carve's dependent-load chain

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/meshMaze/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/meshMaze/2_assisted.cpp       AI filled the unported region(s)
build/stages/meshMaze/3_optimized/00_baseline.cpp
build/stages/meshMaze/3_optimized/01_reuse_out_mesh_setpoints.cpp
build/stages/meshMaze/3_optimized/02_raw_store_output.cpp
build/stages/meshMaze/3_optimized/03_own_vertex_normals.cpp
build/stages/meshMaze/3_optimized/04_incremental_normals.cpp
build/source/meshMaze.cpp      SHIPPED
```
