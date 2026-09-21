# diskMeshCache -- compile report

**Source node:** `diskMeshCache`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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

frames  = ndio.read(self.cachePath, "points")
counts  = ndio.read(self.cachePath, "counts", dtype=np.int64)
indices = ndio.read(self.cachePath, "indices", dtype=np.int64)

n = frames.shape[0]

if n < 1:
    pts = np.zeros((0, 3))
else:
    i   = int(self.frame) % n
    pts = frames[i] * self.scale

self.outMesh = Mesh(points=pts, counts=counts, indices=indices)
```

## Files

```
build/stages/diskMeshCache/1_transpiled.cpp     deterministic transpile (no AI)
build/source/diskMeshCache.cpp      SHIPPED
```
