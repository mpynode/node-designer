# aimTransform -- compile report

**Source node:** `aimTransform`  ·  **Base:** `MPxTransform`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
m0 = self.matrix0.asNumpy()
m1 = self.matrix1.asNumpy()
p0 = m0[3, :3]
p1 = m1[3, :3]
fwd = p1 - p0
length = float(np.linalg.norm(fwd))
if length < 1e-9:
    fwd = np.array([1.0, 0.0, 0.0])
else:
    fwd = fwd / length
up = np.array([0.0, 1.0, 0.0])
if abs(float(np.dot(fwd, up))) > 0.999:
    up = np.array([0.0, 0.0, 1.0])
side = np.cross(fwd, up)
side = side / (float(np.linalg.norm(side)) + 1e-12)
up2 = np.cross(side, fwd)
M = np.eye(4)
M[0, :3] = fwd
M[1, :3] = up2
M[2, :3] = side
M[3, :3] = 0.5 * (p0 + p1)
P = self.parentWorld.asNumpy()
self.local_matrix = M @ np.linalg.inv(P)
self.apply_rotate = True
self.apply_translate = True
self.apply_scale = True
```

## Files

```
build/stages/aimTransform/1_transpiled.cpp     deterministic transpile (no AI)
build/source/aimTransform.cpp      SHIPPED
```
