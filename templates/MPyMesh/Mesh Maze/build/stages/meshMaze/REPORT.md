# meshMaze -- compile report

**Source node:** `meshMaze`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 20:42

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **2.28x** over 2 round(s) -- re-measured: **1.49x** (outputs match) |

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

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **18.386 ms** -> best **8.080 ms** (**2.28x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 140 / array length 5000: baseline 38.798 ms -> shipped 26.102 ms (**1.49x**); outputs match. The speedup above was taken before the gate existed; this is the number to quote. Moved per tick: `end (int)`, `inMesh <- pSphereShape1.vtx[0]`, `seed (int)`, `solutionLength (double)`, `start (int)`, `wallHeight (double)`, `wallThickness (double)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 18.386 ms | -- | -- |
| 01 | `cache_mesh_topology` | everything the maze derives from inMesh -- points, vertex normals, the deduplicated edge list, the inverse map and the CSR dual graph -- is cached on a per-instance fingerprint, so a tick that only moves a scalar carves and extrudes without rebuilding the graph; the output arrays are also handed to Maya through bulk MPointArray/MIntArray constructors instead of per-element append() | 2.40x | 2.02x | 14.8 min | ACCEPTED |
| 02 | `skip_same_point_check` | the node is 85% MFnMesh::create, so the round went into create's own cost -- turning off its same-point-twice scan and filling MFloatPointArray/MIntArray in place instead of staging through std::vector | 1.15x | 2.28x | 12.2 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `skip_same_point_check` -- predicted 1.15x, measured **2.28x**. profiling first would show the maze itself is noise; a 19.5k-slab unwelded soup (155,688 verts / 116,766 quads / 467,064 connects) is marshalling-bound, and create's per-polygon duplicate-index validation is pure waste when every quad is vbase+0..7 by construction

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/meshMaze/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/meshMaze/2_assisted.cpp       AI filled the unported region(s)
build/stages/meshMaze/3_optimized/00_baseline.cpp
build/stages/meshMaze/3_optimized/01_cache_mesh_topology.cpp
build/stages/meshMaze/3_optimized/02_skip_same_point_check.cpp
build/source/meshMaze.cpp      SHIPPED
```
