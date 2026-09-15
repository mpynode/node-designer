# meshMaze -- compile report

**Source node:** `meshMaze`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-14 17:51

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **33.81x** over 5 round(s) -- 5 run of max 6, stopped: round 5 no-change -- nothing new to compound from |

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
    self.solutionSteps = 0
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
    visited, door, sol_len, parent = _maze_carve(
        n_faces, adj_start, deg, adj_dst, adj_eid, int(ei.shape[0]),
        start, end, want, int(self.seed))

    # The solution is free: the doors are a tree rooted at `start`, so walking
    # `parent` back from `end` IS the one path between them. `solutionSteps`
    # reports its length -- 0 when `end` was never reached -- so `solutionStep`
    # can be keyed exactly from the entrance (0) to the exit (n).
    path = _maze_solution(parent, visited, start, end)
    n_steps = max(int(path.shape[0]) - 1, 0)
    self.solutionSteps = n_steps

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

    h = float(self.wallHeight)
    half = 0.5 * float(self.wallThickness)
    wp = np.zeros((0, 3), dtype=np.float64)
    wc = np.zeros(0, dtype=np.int64)
    wi = np.zeros(0, dtype=np.int64)
    if int(wall.shape[0]) > 0:
        k = uniq[wall]
        va = k // np.int64(n_verts)
        vb = k - va * np.int64(n_verts)
        wp, wc, wi = _maze_walls(pts, nrm, va, vb, h, half)

    # The solution tiles: path faces 0..`solutionStep` (clamped at the exit),
    # each inset half a wall thickness so it lies BETWEEN the slabs and floated
    # a tenth of the wall height so it does not z-fight the floor. Switched
    # off, or no path at all, draws nothing -- never an error.
    tp = np.zeros((0, 3), dtype=np.float64)
    tc = np.zeros(0, dtype=np.int64)
    ti = np.zeros(0, dtype=np.int64)
    if bool(self.drawSolution) and int(path.shape[0]) > 0:
        upto = min(max(int(self.solutionStep), 0), n_steps) + 1
        tp, tc, ti = _maze_tiles(pts, nrm, counts, indices, path[:upto],
                                 0.1 * h, half)

    if int(wc.shape[0]) + int(tc.shape[0]) == 0:
        self.outMesh = Mesh()
    else:
        # One vertex colour per point: walls in `wallColor`, tiles in
        # `solutionColor`. The render mesh shows them once displayColors is on,
        # which `setup` does.
        wall_col = np.asarray(self.wallColor, dtype=np.float64)[:3]
        path_col = np.asarray(self.solutionColor, dtype=np.float64)[:3]
        col = np.concatenate([
            np.zeros((int(wp.shape[0]), 3), dtype=np.float64) + wall_col[None, :],
            np.zeros((int(tp.shape[0]), 3), dtype=np.float64) + path_col[None, :]],
            axis=0)
        self.outMesh = Mesh(points=np.concatenate([wp, tp], axis=0),
                            counts=np.concatenate([wc, tc]),
                            indices=np.concatenate([wi, ti + np.int64(wp.shape[0])]),
                            colors=col)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 90 / array length 2000; noise floor 15 ms; moved per tick: `drawSolution (bool)`, `end (int)`, `inMesh <- pSphereShape1.vtx[0]`, `seed (int)`, `solutionColor (color)`, `solutionLength (double)`, `start (int)`, `wallColor (color)`, `wallHeight (double)`, `wallThickness (double)`; outputs checked (2 plug(s)); accepts re-timed against the incumbent on the smallest scene (geo density 40 / array length 512) and rejected if slower there.

Baseline **80.339 ms** -> best **2.376 ms** (**33.81x**).

Rounds: **5** run of at most 6; the loop stopped because round 5 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 80.339 ms | -- | -- |
| 01 | `bulk_color_set` | replace the per-vertex setVertexColors call on the 64k-vertex wall mesh with one data-mesh color set filled by bulk setColors + assignColors, and rewrite the output mesh in place when its topology repeats | 2.50x | 2.66x | 20.8 min | ACCEPTED |
| 02 | `topology_template_mesh` | Keep a per-instance mesh of each recurring output topology (walls + tile face sizes) with its colour set already assigned, rewrite only its points and colours each tick and hand it to the datablock, instead of MFnMesh::create plus assignColors on a 64k-vertex soup every evaluation. | 3.00x | 13.69x | 30.3 min | ACCEPTED |
| 03 | `palette_threads_overlap_carve` | Cut the per-tick Maya marshalling and hide the serial carve: a 2-entry colour palette replaces 64k per-vertex colours, the wall slabs become a parallel map written straight into a persistent MFloatPointArray, and the randomized DFS runs on a dedicated worker while the main thread is inside MFnMesh::getVertexNormals. | 1.80x | 29.26x | 32.5 min | ACCEPTED |
| 04 | `--` | -- | -- | 33.81x | 9.0 min | ACCEPTED |
| 05 | `--` | -- | -- | -- | 3 s | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `topology_template_mesh` -- predicted 3.00x, measured **13.69x**. Profiling showed ~23 of 31 ms was MFnMesh::create (16 ms), colour-set creation/assignment (5 ms) and releasing the previous mesh (2 ms); the maze itself (edges, dual, DFS, slab geometry) was ~4 ms. The output topology is a pure function of the wall count and the tile face sizes, and the bench alternates drawSolution so it flips between exactly two topologies, which is why the porter's single-slot in-place reuse never fired. MDataHandle::setMObject was verified to COPY the data (mutating the object after the set leaves the datablock's copy untouched, and the object outlives its replacement), so a node-owned template can be rewritten and re-set every tick. Secondary: cache the whole _maze_edges/_maze_dual/CSR derivation keyed on a full byte compare of (n_verts, counts, indices), which hold while a vertex moves; read points via getRawPoints; emit points straight into a persistent MFloatPoint buffer (same (float) cast Maya applies to an MPoint).
* `palette_threads_overlap_carve` -- predicted 1.80x, measured **29.26x**. Profiling showed half the 5.9 ms tick was Maya-side output marshalling (setPoints 1.2 ms, setColors 0.8 ms, datablock copy 0.66 ms) and a further 0.6 ms Maya normal recompute; setPoints and the copy are API floors, but setColors only exists because 64k identical colours were re-sent -- the parity reader compares face-vertex colours, so a 2-colour palette with per-face-vertex assignment fixed at template build is indistinguishable and ~free per tick. Of our own 1.6 ms, the wall-slab loop (0.64 ms, 6 divisions + 2 sqrt per wall) is an embarrassingly parallel per-row map, and the carve (0.45 ms) + wall listing (0.13 ms) depend only on topology and scalars, so they can run on one worker concurrently with the normals call, which is a Maya API call on the calling thread that the carve never reads. MFloatPointArray storage is contiguous (element addresses checked every tick), so the kernel writes into it directly and the 1 MB copy disappears.

### Rejected rounds

* `?` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* authored @maya_test: 1/1 passed
* speed: compiled 4.039 ms vs interpreted 79.812 ms (best of 3, geo 40 / array 512)

## Files

```
build/stages/meshMaze/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/meshMaze/2_assisted.cpp       AI filled the unported region(s)
build/stages/meshMaze/3_optimized/00_baseline.cpp
build/stages/meshMaze/3_optimized/01_bulk_color_set.cpp
build/stages/meshMaze/3_optimized/02_topology_template_mesh.cpp
build/stages/meshMaze/3_optimized/03_palette_threads_overlap_carve.cpp
build/stages/meshMaze/3_optimized/04_accept.cpp
build/source/meshMaze.cpp      SHIPPED
```
