# voxelizeMesh -- compile report

**Source node:** `voxelizeMesh`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 15:56

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- 1 region(s) still marked incomplete |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) -- 0 run of max 6, stopped: baseline could not be benchmarked |

## The Python this was generated from

```python
# Rebuild the incoming mesh as a voxel SHELL, by CLOSEST POINT rather than by
# binning the source geometry -- so the result never depends on how finely the
# source happens to be tessellated.
#
#   1. Take the source bounding box and lay a WORLD-anchored lattice over it:
#      cell `i` spans [i*voxelSize, (i+1)*voxelSize), so a cube CORNER sits
#      exactly on the origin. The lattice is fixed in world space, so voxels do
#      not swim when the mesh moves or deforms.
#   2. Build the dense 3D point cloud of every cell CENTRE in that box and ask
#      the mesh for the closest surface point to each one.
#   3. Snap every returned sample to the cell that contains it and drop the
#      duplicates, keeping the sample CLOSEST to its own grid point. Those cells
#      are the voxels; each winner also supplies its cube's colour.
#
# The grid is O(K^3) while the shell is O(K^2), so most queries are "wasted" --
# but they are not: an interior grid point regularly claims a cell that no
# nearer point reaches, and pruning the query set to a band around the surface
# was measured to silently lose cells. MMeshIntersector runs ~170k queries/s,
# which keeps the dense sweep well inside interactive range.
#
# Colour is taken at the WINNING sample and falls down a chain: `textureFile`
# sampled at the exact closest point's UV, else the source's vertex colours,
# else `defaultColor`. A blank or unreadable path just drops to the next link --
# it is never an error.
import numpy as np
import maya.api.OpenMaya as om
from mpynode._api2.geometry import Mesh

src = getattr(self, "inMesh", None)
pts = None if src is None else getattr(src, "points", None)
pts = None if pts is None else np.asarray(pts, dtype=np.float64)
nfaces = 0 if src is None else int(np.asarray(src.counts).size)

if pts is None or pts.shape[0] == 0 or nfaces == 0:
    # No input, an empty one, or a point cloud with no surface to project onto
    # -> an empty but VALID mesh, never a raise.
    self.outMesh = Mesh()
else:
    vsize = max(1e-6, float(self.voxelSize))
    grid = _vox_grid(pts.min(axis=0), pts.max(axis=0), vsize)
    n = int(grid.shape[0])

    # Brake on the GRID, before a single query runs -- the sweep is cubic in
    # 1/voxelSize, so halving it costs 8x. Checking here aborts instantly
    # instead of after a long stall.
    cap = int(self.maxVoxels)
    if cap > 0 and n > cap:
        raise ValueError(
            "voxelize: %d grid points at voxelSize=%g exceeds maxVoxels=%d. "
            "Raise voxelSize (or maxVoxels) -- the sweep is cubic in "
            "1/voxelSize." % (n, vsize, cap))

    samples, faces, tris, bary = _vox_closest(src.to_mobject(), grid)
    cells, win = _vox_winners(samples, grid, vsize)
    m = int(cells.shape[0])
    centers = (cells.astype(np.float64) + 0.5) * vsize

    # The hit triangle + weights let ANY per-vertex attribute be read exactly at
    # the winning closest point. Only the winners are interpolated, not all n.
    corner, w = _vox_corner_weights(src, faces[win], tris[win], bary[win])

    # --- one colour per cube: texture -> vertex colour -> defaultColor -----
    col = None
    tex = _vox_read_image(self.textureFile)
    if tex is not None:
        uvv = _vox_vertex_uvs(src, pts.shape[0])
        if uvv is not None:
            col = _vox_sample_texture(tex, (uvv[corner] * w[:, :, None]).sum(1))
    if col is None:
        vcol = getattr(src, "colors", None)
        vcol = None if vcol is None else np.asarray(vcol, dtype=np.float64)
        if vcol is not None and vcol.shape[0] == pts.shape[0]:
            col = (vcol[corner] * w[:, :, None]).sum(1)[:, :3]
    if col is None:
        base_col = np.asarray(self.defaultColor, dtype=np.float64).reshape(1, -1)
        col = np.repeat(base_col[:, :3], m, axis=0)

    points, counts, indices = _vox_cubes(centers, 0.5 * vsize)
    # Per-vertex colours (no color_indices): 8 verts per cube all share its
    # colour, which is 1/3 the MColor churn of the per-face-vertex form.
    self.outMesh = Mesh(points=points, counts=counts, indices=indices,
                        colors=np.repeat(col, 8, axis=0))
```

## Unfinished work in the generated C++

* **not translated:** _vox_resolve_path resolves a RELATIVE textureFile by

## Optimization

Parity gate: not exercised -- no candidate reached the parity check (the baseline was unmeasurable or no round compiled).

Bench scene: geo density 40 / array length 512; noise floor 15 ms.

Baseline **--** -> best **--** (**1.00x**).

Rounds: **0** run of at most 6; the loop stopped because baseline could not be benchmarked.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | -- | -- | -- |

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/voxelizeMesh/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/voxelizeMesh/2_assisted.cpp       AI filled the unported region(s)
build/stages/voxelizeMesh/3_optimized/00_baseline.cpp
build/source/voxelizeMesh.cpp      SHIPPED
```
