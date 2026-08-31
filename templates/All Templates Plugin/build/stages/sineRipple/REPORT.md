# sineRipple -- compile report

**Source node:** `sineRipple`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Sine-ripple deformer: each vertex rides a travelling sine wave along its
# surface normal. The wave's phase advances with distance from the mesh
# centre and with time, so it animates as the timeline plays.
mesh = self.outputGeometry[0]            # writable handle for this output mesh
pts = mesh.getPoints()                   # (N, 3) object-space points (numpy)

# True per-vertex normals (object space). The output handle wraps an API-1
# MFnMesh, so use the in-out MFloatVectorArray form.
nrm = om.MFloatVectorArray()
mesh.getVertexNormals(False, nrm, om.MSpace.kObject)
normals = np.array([[nrm[i].x, nrm[i].y, nrm[i].z]
                    for i in range(nrm.length())], dtype=float)

amp = self.amplitude
freq = self.frequency
speed = self.speed
env = self.envelope               # built-in deformer envelope (0..1)

centre = pts.mean(axis=0)
dist = np.linalg.norm(pts - centre, axis=1)
phase = 2.0 * np.pi * freq * dist - speed * self.time
offset = (amp * np.sin(phase))[:, None] * normals

mesh.setPoints(pts + env * offset)
```

## Files

```
build/stages/sineRipple/1_transpiled.cpp     deterministic transpile (no AI)
build/source/sineRipple.cpp      SHIPPED
```
