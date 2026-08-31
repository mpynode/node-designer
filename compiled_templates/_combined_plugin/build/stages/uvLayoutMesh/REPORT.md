# uvLayoutMesh -- compile report

**Source node:** `uvLayoutMesh`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | not run |

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

## Files

```
build/stages/uvLayoutMesh/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/uvLayoutMesh/2_assisted.cpp       AI filled the unported region(s)
build/source/uvLayoutMesh.cpp      SHIPPED
```
