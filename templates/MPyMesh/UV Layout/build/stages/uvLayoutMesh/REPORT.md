# uvLayoutMesh -- compile report

**Source node:** `uvLayoutMesh`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-25 10:07

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **11.60x** over 2 round(s) |

## The Python this was generated from

```python
# Output the input mesh's UV layout as a flat 2D mesh: each UV coordinate becomes
# an (u, v, 0) point and the mesh's per-face UV connectivity becomes the output
# faces. Plug a mesh into `inMesh` and the generated mesh in the 3D view IS its
# UV layout -- handy for inspecting/visualising UVs as geometry. Choose a UV set
# by name with `uvSetName` (blank = the first/default set, e.g. "map1"); a mesh
# with no UVs (or an unconnected input) yields an empty (but valid) mesh.
import numpy as np
from mpynode._api2.geometry import Mesh

src = getattr(self, "inMesh", None)
sets = src.uv_sets if src is not None else []
if not sets:
    self.outMesh = Mesh()
else:
    want = (getattr(self, "uvSetName", "") or "").strip()
    chosen = sets[0]
    if want:
        for s in sets:
            if s.name == want:
                chosen = s
                break
    # Mesh() gracefully accepts a UVSet -> builds the 2D UV layout (u, v, 0.0).
    self.outMesh = Mesh(chosen)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Baseline **19.008 ms** -> best **1.638 ms** (**11.60x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 19.008 ms | -- | -- |
| 01 | `bulk_uv_read` | replace the per-id getUV loop with one getUVs call, then stop round-tripping Maya's UV face lists through three redundant int buffers before handing them back to create() | 2.00x | 1.55x | 11.3 min | ACCEPTED |
| 02 | `cache_topology_template` | MFnMesh::create was 90% of compute, so cache the built mesh as a topology TEMPLATE keyed on an exact content hash of (counts, indices, nPoints) and produce each evaluation's output with MFnMesh::copy plus freshly-read points instead of a fresh create | 4.00x | 11.60x | 13.4 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_topology_template` -- predicted 4.00x, measured **11.60x**. profiling showed create() at 10-12 ms of a 12.5 ms compute while every other pass summed to 1.2 ms; no constant-factor work on the reads could matter, and copy() of an already-built poly structure is a deep memcpy rather than a topology derivation, so it should be an order of magnitude cheaper

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/uvLayoutMesh/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/uvLayoutMesh/2_assisted.cpp       AI filled the unported region(s)
build/stages/uvLayoutMesh/3_optimized/00_baseline.cpp
build/stages/uvLayoutMesh/3_optimized/01_bulk_uv_read.cpp
build/stages/uvLayoutMesh/3_optimized/02_cache_topology_template.cpp
build/source/uvLayoutMesh.cpp      SHIPPED
```
