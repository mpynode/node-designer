# jsonMeshReader -- compile report

**Source node:** `jsonMeshReader`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-25 09:40

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) |

## The Python this was generated from

```python
# Stream a mesh off disk, ONE JSON FILE PER FRAME -- and compile.
#
# `path` is a filename template: ndio.frame_path replaces the first run of '#'
# with the zero-padded frame, so ".../mesh.####.json" at frame 7 reads
# ".../mesh.0007.json". That substitution is the one string operation a
# compiled compute cannot express on its own -- there is no str(), no %, and no
# f-string in the lowerable surface -- so it lives in the kernel next to the
# reader, and both halves produce byte-identical filenames.
#
# Because every frame is its OWN file, the TOPOLOGY may change from frame to
# frame. That is what this buys over a single packed cache array, which needs
# constant topology by construction.
#
# ndio.read caches the parsed file on path + mtime + size in BOTH
# implementations, so re-evaluating a frame already in hand does no file IO. A
# missing or malformed file yields EMPTY arrays instead of raising, which is why
# the guard below is the only error handling this node needs.
import numpy as np

from mpynode import ndio
from mpynode._api2.geometry import Mesh

resolved = ndio.frame_path(self.path, self.frame)

pts = ndio.read(resolved, "points")
counts = ndio.read(resolved, "counts", dtype=np.int64)
indices = ndio.read(resolved, "indices", dtype=np.int64)

# Accepts points as [[x,y,z], ...] or a flat [x,y,z,x,y,z, ...]; an absent file
# gives an empty array, which must not go through reshape(-1, 3).
if pts.shape[0] < 1:
    points = np.zeros((0, 3))
else:
    points = pts.reshape(-1, 3)

self.outMesh = Mesh(points=points, counts=counts, indices=indices)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Baseline **--** -> best **--** (**1.00x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | -- | -- | -- |

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/jsonMeshReader/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/jsonMeshReader/3_optimized/00_baseline.cpp
build/source/jsonMeshReader.cpp      SHIPPED
```
