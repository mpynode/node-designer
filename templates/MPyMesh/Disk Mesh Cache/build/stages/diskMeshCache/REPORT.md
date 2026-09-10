# diskMeshCache -- compile report

**Source node:** `diskMeshCache`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 15:24

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) -- 0 run of max 6, stopped: baseline could not be benchmarked |

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
build/stages/diskMeshCache/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/diskMeshCache/3_optimized/00_baseline.cpp
build/source/diskMeshCache.cpp      SHIPPED
```
