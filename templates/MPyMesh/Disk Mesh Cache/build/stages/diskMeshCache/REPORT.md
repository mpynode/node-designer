# diskMeshCache -- compile report

**Source node:** `diskMeshCache`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:24

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) |

## The Python this was generated from

```python
# Play a cached deforming mesh straight off disk.
#
# ONE file holds the whole take: `points` is (FRAMES, VERTS, 3), and `counts` /
# `indices` describe the constant topology. Each evaluation reads the three
# named arrays and slices out the current frame.
#
# "Reads" is the interesting word. `ndio.read` caches the parsed file on
# path + mtime + size, in BOTH implementations -- the Python one you are
# running now and the C++ kernel the compiled node uses. So the first
# evaluation touches the disk and every later one does not, however far you
# scrub. Rewrite the file under the same name and the key changes, so the new
# contents are picked up rather than served stale.
#
# A missing or malformed file yields EMPTY arrays rather than an exception,
# which is why the `n < 1` guard below is the only error handling needed: the
# node shows no geometry instead of going into an error state.
import numpy as np

from mpynode import ndio
from mpynode._api2.geometry import Mesh

frames = ndio.read(self.cachePath, "points")
counts = ndio.read(self.cachePath, "counts", dtype=np.int64)
indices = ndio.read(self.cachePath, "indices", dtype=np.int64)

n = frames.shape[0]

if n < 1:
    pts = np.zeros((0, 3))
else:
    i = int(self.frame) % n
    pts = frames[i] * self.scale

self.outMesh = Mesh(points=pts, counts=counts, indices=indices)
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
* speed: compiled 0.122 ms vs interpreted 0.306 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/diskMeshCache/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/diskMeshCache/3_optimized/00_baseline.cpp
build/source/diskMeshCache.cpp      SHIPPED
```
