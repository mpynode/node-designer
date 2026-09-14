# voxelizeMesh -- compile report

**Source node:** `voxelizeMesh`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-14 08:19

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **4.21x** over 2 round(s) -- 2 run of max 8, stopped: round 2 no-change -- nothing new to compound from |

## The Python this was generated from

```python
# Rebuild the incoming mesh as a voxel SHELL by RASTERISING its triangles into
# a WORLD-anchored lattice (cell i spans [i*voxelSize, (i+1)*voxelSize), so a
# cube corner sits exactly on the origin and the voxels never swim).
#
#   1. Fan-triangulate the faces (pure index arithmetic, no Maya call).
#   2. For every triangle enumerate the lattice cells its bounding box touches
#      (a ragged expansion, cumsum + searchsorted) -- the CANDIDATE pairs.
#   3. Keep a pair iff the triangle really overlaps the cell's cube: the exact
#      separating-axis test (Akenine-Moller), plane axis first, then the nine
#      edge axes. The kept cells are EXACTLY the cells the surface passes
#      through -- the conservative / 26-separating shell, independent of how
#      finely the source is tessellated (a two-triangle wall voxelises solidly).
#   4. One deterministic winner per cell: the pair whose closest point on its
#      triangle is nearest the cell centre (ties -> lowest pair index). The
#      winner's barycentrics put the colour lookup at that surface point.
#
# Work is O(candidate pairs) ~ triangles x (edge / voxelSize + 1)^3, never the
# K^3 grid. maxVoxels brakes on min(grid cells, candidate pairs) -- an upper
# bound on the voxel count that is never larger than the old grid count -- in
# O(triangles), BEFORE any pair is materialised.
#
# Colour is taken at the winner's closest point and falls down a chain:
# `textureFile` sampled at that point's UV, else the source's vertex colours,
# else `defaultColor`. A blank or unreadable path drops to the next link.

# Interpreted-only prologue: a never-connected inMesh is None and an
# unattached Mesh() has None arrays. (The C++ port is handed empty arrays for
# a null mesh, so it has no `is None` test to make.)
src = self.inMesh
pts = np.zeros((0, 3), dtype=np.float64)
cnt = np.zeros(0, dtype=np.int64)
idx = np.zeros(0, dtype=np.int64)
if src is not None and src.points is not None and src.counts is not None and src.indices is not None:
    pts = np.asarray(src.points, dtype=np.float64)
    cnt = np.asarray(src.counts, dtype=np.int64)
    idx = np.asarray(src.indices, dtype=np.int64)
vs = max(1e-6, float(self.voxelSize))
cap = int(self.maxVoxels)
h = 0.5 * vs

# --- O(T): triangles, per-triangle cell ranges, brake ----------------------
tv = _vox_tris(cnt, idx)                                  # (T,3) vertex ids
T = int(tv.shape[0])
bounds = _vox_tri_bounds(pts, tv, vs)                     # (T,6) lo | hi cells
span_t = bounds[:, 3:6] - bounds[:, 0:3] + 1
per_tri = span_t[:, 0] * span_t[:, 1] * span_t[:, 2]     # cells per triangle
M = int(per_tri.sum())                                    # candidate pairs
base = np.zeros(3, dtype=np.int64)
span = np.ones(3, dtype=np.int64)
ngrid = 0
tol = 1e-9 * vs
if T > 0:
    base = bounds[:, 0:3].min(axis=0)
    span = bounds[:, 3:6].max(axis=0) - base + 1
    ngrid = int(span[0] * span[1] * span[2])              # the old K^3 count
    ext = float(np.maximum(base + span, 0 - base).max()) * vs
    tol = 1e-9 * vs + 1e-13 * ext                         # robust touching
# Brake BEFORE the expansion: every voxel is one grid cell and at least one
# candidate pair, so min(ngrid, M) bounds the count; it is never above the
# old grid count, so no scene that computed before aborts now.
bound = min(ngrid, M)
if cap > 0 and bound > cap:
    raise ValueError("voxelize: voxel bound exceeds maxVoxels -- raise voxelSize or maxVoxels")

# --- O(M): exact overlap, plane axis first ---------------------------------
cand = _vox_candidates(bounds, per_tri)                   # (M,4) tri,ix,iy,iz
k1, = np.nonzero(_vox_plane_keep(pts, tv, cand, vs, tol))
cand = np.take(cand, k1, axis=0)
k2, = np.nonzero(_vox_edge_keep(pts, tv, cand, vs, tol))
cand = np.take(cand, k2, axis=0)                          # (P,4) overlapping
tri = cand[:, 0]
cell = cand[:, 1:4]
ctr = (cell.astype(np.float64) + 0.5) * vs

# --- winner per cell + surface point ---------------------------------------
tt = tv[tri]                                              # (P,3) corner ids
a = pts[tt[:, 0]]
b = pts[tt[:, 1]]
c = pts[tt[:, 2]]
w = _vox_bary_closest(ctr, a, b, c)                       # (P,3) weights
q = a * w[:, 0:1] + b * w[:, 1:2] + c * w[:, 2:3]         # closest points
dq = q - ctr
dist2 = (dq * dq).sum(axis=1)
win = _vox_pick(cell, dist2, base, span)                  # (S,) pair index
cells = cell[win]
corner = tt[win]
wgt = w[win]
m = int(cells.shape[0])
centers = (cells.astype(np.float64) + 0.5) * vs

# --- one colour per cube: texture -> vertex colour -> defaultColor ---------
# (interpreted chain: uv_sets / colors / image reads are not lowerable, so the
# C++ port carries this block as ported code, exactly as it does today)
col = np.zeros((m, 3)) + np.asarray(self.defaultColor, dtype=np.float64)[:3]
got = False
tex = _vox_read_image(self.textureFile)
if tex is not None and src is not None:
    uvv = _vox_vertex_uvs(src, pts.shape[0])
    if uvv is not None:
        col = _vox_sample_texture(tex, (uvv[corner] * wgt[:, :, None]).sum(1))
        got = True
if not got and src is not None:
    vcol = getattr(src, "colors", None)
    if vcol is not None:
        vcol = np.asarray(vcol, dtype=np.float64)
        if vcol.shape[0] == pts.shape[0]:
            col = (vcol[corner] * wgt[:, :, None]).sum(1)[:, :3]

# --- cubes -----------------------------------------------------------------
points = _vox_cube_points(centers, h)
counts = np.full(6 * m, 4, dtype=np.int64)
indices = _vox_cube_indices(m)
self.outMesh = Mesh(points=points, counts=counts, indices=indices,
                    colors=np.repeat(col, 8, axis=0))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 40 / array length 512; noise floor 15 ms; moved per tick: `defaultColor (color)`, `inMesh <- pSphereShape1.vtx[0]`; outputs checked (1 plug(s)).

Baseline **46.463 ms** -> best **11.049 ms** (**4.21x**).

Rounds: **2** run of at most 8; the loop stopped because round 2 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 46.463 ms | -- | -- |
| 01 | `direct_colorset_write` | the node was bound by Maya mesh-output calls, not voxel math: write the colour set directly in setVertexColors' exact layout instead of calling setVertexColors (48.1 -> 24.9 ms), rewrite points + colours IN PLACE into the node's own output mesh when its topology is byte-identical instead of MFnMesh::create each tick (-> 12.1 ms), and replace the O(P log P) winner sort with a dense one-pass best-per-cell pick plus reused scratch buffers (-> 10.0 ms) | 1.80x | 4.21x | 22.0 min | ACCEPTED |
| 02 | `float4_output_and_row_sat_cache` | write cube corners and face-vertex colours straight into float4 buffers keyed on the cube count (no MPoint/MColor/topology vectors, no topology byte-compare), cache each triangle's SAT survivors across evaluations so only the triangles touching the moved vertex are re-tested (overwritten in place when their survivor count holds), and reuse one MColorArray for the in-place colour upload | 2.20x | -- | 20.5 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `direct_colorset_write` -- predicted 1.80x, measured **4.21x**. a section profile at the bench size (T=3120 tris, M=32.6k candidate pairs, P=19.2k overlaps, m=4780 cubes -> 38k verts, 115k face-vertices) showed all geometry math ~5 ms while setVertexColors took ~30 ms and MFnMesh::create ~8.5 ms. setVertexColors stores ONE colour per face-vertex (numColors = 24m, RGBA, unclamped, colorSet1 current), so createColorSetWithNameDataMesh + setColors(face-vertex table) + assignColors(0..n-1) reproduces it in two bulk calls. Between ticks only defaultColor and vtx[0] move, the voxel count (hence counts/indices) does not change, so the previous output data object (checked by MObject identity, byte-compared counts/indices, and O(1) vertex/face/face-vertex/colour counts) can be updated with setPoints + setColors. The winner pick is a per-cell argmin with lowest-index tie-break; a strict-< pass in pair order over a dense key array gives exactly the stable sort's first-per-key, in ascending key order
* `float4_output_and_row_sat_cache` -- predicted 2.20x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `float4_output_and_row_sat_cache` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/voxelizeMesh/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/voxelizeMesh/2_assisted.cpp       AI filled the unported region(s)
build/stages/voxelizeMesh/3_optimized/00_baseline.cpp
build/stages/voxelizeMesh/3_optimized/01_direct_colorset_write.cpp
build/source/voxelizeMesh.cpp      SHIPPED
```
