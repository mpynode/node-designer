# metaballs -- compile report

**Source node:** `metaballs`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
mats = np.asarray(self.shapeMatrix, dtype=np.float64)
n = mats.shape[0]
shape_type = _dense_over(self.shapeType, np.zeros(n, dtype=np.int64))
additive = _dense_over(self.additive, np.ones(n, dtype=np.int64))
smoothing = _dense_over(self.smoothing, np.zeros(n, dtype=np.float64))
radius = _dense_over(self.radius, np.where(shape_type == 2, 0.5, 1.0))
height = _dense_over(self.height, np.ones(n, dtype=np.float64))
axis = _dense_over(self.axis, np.ones(n, dtype=np.int64))
half = _dense_over(self.halfExtents, np.full((n, 3), 0.5))
packed = _mesh_packed(mats, shape_type, additive, smoothing, radius, height,
                      axis, half, int(self.resolution), float(self.isoValue))
V = int(packed[0])
F = int(packed[1])
points = packed[2:2 + 3 * V].reshape(V, 3)
indices = packed[2 + 3 * V:2 + 3 * V + 4 * F].astype(np.int32)
counts = np.full(F, 4, dtype=np.int32)
self.outMesh = Mesh(points=points, counts=counts, indices=indices)
```

## Files

```
build/stages/metaballs/1_transpiled.cpp     deterministic transpile (no AI)
build/source/metaballs.cpp      SHIPPED
```
