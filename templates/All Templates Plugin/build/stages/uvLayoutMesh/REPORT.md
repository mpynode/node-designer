# uvLayoutMesh -- compile report

**Source node:** `uvLayoutMesh`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 16:13

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **9.26x** over 2 round(s) -- 2 run of max 6, stopped: round 2 gained 1.15x, below the 1.15x needed to continue |

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

src  = getattr(self, "inMesh", None)
sets = src.uv_sets if src is not None else []
if not sets:
    self.outMesh = Mesh()
else:
    want   = (getattr(self, "uvSetName", "") or "").strip()
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

Bench scene: geo density 300 / array length 10000; noise floor 15 ms; moved per tick: `inMesh <- pSphereShape1.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there.

Baseline **21.335 ms** -> best **2.304 ms** (**9.26x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 gained 1.15x, below the 1.15x needed to continue.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 21.335 ms | -- | -- |
| 01 | `bulk_uvs_inplace_output` | read the UV set with the two bulk MFnMesh calls instead of ~90k per-UV getUV calls, and when the output handle still holds a mesh built from byte-identical UV counts/indices rewrite only its (u, v, 0) positions in place instead of an MFnMesh::create of ~90k vertices | 5.00x | 8.08x | 13.0 min | ACCEPTED |
| 02 | `raw_uv_and_int_views` | read the UV set through MFnMesh::getRawUVs and view the getAssignedUVs MIntArrays in place, so the per-tick cost is one memcmp cache key plus the two Maya calls instead of four bulk copies | 1.40x | 9.26x | 13.5 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `bulk_uvs_inplace_output` -- predicted 5.00x, measured **8.08x**. the node is O(N) marshalling, not a query: 90k out-of-line getUV(k, &setName) calls and a full 90k-vertex/90k-face MFnMesh::create dominate, while a moved vertex changes neither the UVs nor the UV topology, so the create is skippable every tick once the topology compares equal; UVs are float32 already, so an MFloatPointArray / raw float store write is bit-identical to the double->float narrowing create performs
* `raw_uv_and_int_views` -- predicted 1.40x, measured **9.26x**. a stage timer showed the node's own work was almost all marshalling: getUVs + two MFloatArray::get copies (~300-600 us), two MIntArray::get copies (~300 us) and filter/guard/compare loops (~150 us) around two Maya calls (input pull ~750 us, getAssignedUVs ~700 us) that cannot be avoided soundly; getRawUVs is a pointer into the mesh's (u, v) store (verified byte-equal to getUVs on 90,599 UVs), and MIntArray::operator[] returns a real int& so &arr[0] (contiguity confirmed against &arr[n-1], get() fallback otherwise) is a zero-copy view; keying the derived topology on a memcmp of the RAW counts/ids lets a hit skip the filter and guard loops entirely

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/uvLayoutMesh/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/uvLayoutMesh/2_assisted.cpp       AI filled the unported region(s)
build/stages/uvLayoutMesh/3_optimized/00_baseline.cpp
build/stages/uvLayoutMesh/3_optimized/01_bulk_uvs_inplace_output.cpp
build/stages/uvLayoutMesh/3_optimized/02_raw_uv_and_int_views.cpp
build/source/uvLayoutMesh.cpp      SHIPPED
```
