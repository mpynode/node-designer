# gameOfLifeMesh -- compile report

**Source node:** `gameOfLifeMesh`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:24

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) |

## The Python this was generated from

```python
# Conway's Game of Life as a single procedural mesh: build ONE cube per LIVE
# cell straight into ``self.outMesh``. The board is a bounded numpy array (no
# wrap) recomputed from a fixed seed each eval -- no cross-eval state, so the
# timeline scrubs both ways. Advance with `frame` (auto-wired to time1);
# `resetBoard` reseeds `randomSamples` cells each frame. Adjacent cubes are NOT
# welded (overlapping faces/verts are intentional); `cellSize` (< 1) leaves a
# visible gap between neighbouring cells.
import numpy as np
from mpynode._api2.geometry import Mesh

bx = max(1, self.boardX)
by = max(1, self.boardY)
board = _gol_board(by, bx, self.randomSamples, self.frame, self.resetBoard)

half = 0.5 * max(1e-6, self.cellSize)
ys, xs = np.nonzero(board)              # row (y) + col (x) of each live cell
m = int(xs.shape[0])

if m == 0:
    # An all-dead board -> an empty (but valid) mesh: no points, no faces.
    points = np.zeros((0, 3), dtype=np.float64)
    counts = np.zeros(0, dtype=np.int32)
    indices = np.zeros(0, dtype=np.int32)
else:
    # Cube centre = grid cell coordinate (x, y, 0), one unit apart.
    centers = np.column_stack([
        xs.astype(np.float64),
        ys.astype(np.float64),
        np.zeros(m, dtype=np.float64)])
    # 8 corners of a unit cube, scaled to half the cell size.
    corners = np.array([
        [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
        [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
    ], dtype=np.float64) * half
    # (m, 8, 3) -> (8m, 3): every cube's 8 corners in world space.
    points = (centers[:, None, :] + corners[None, :, :]).reshape(-1, 3)
    # 6 outward-facing quad faces per cube; offset each cube's indices by 8*i.
    # Every quad is wound CCW as seen from OUTSIDE so its normal points away
    # from the cube centre (-Z, +Z, -Y, +Y, -X, +X respectively).
    faces = np.array([
        [0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4],
        [3, 7, 6, 2], [0, 4, 7, 3], [1, 2, 6, 5],
    ], dtype=np.int32)
    base = (8 * np.arange(m, dtype=np.int32))[:, None, None]
    indices = (base + faces[None, :, :]).reshape(-1)
    counts = np.full(6 * m, 4, dtype=np.int32)

self.outMesh = Mesh(points=points, counts=counts, indices=indices)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **--** -> best **--** (**1.00x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | -- | -- | -- |

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* authored @maya_test: 1/1 passed
* speed: compiled 0.044 ms vs interpreted 0.293 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/gameOfLifeMesh/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/gameOfLifeMesh/3_optimized/00_baseline.cpp
build/source/gameOfLifeMesh.cpp      SHIPPED
```
