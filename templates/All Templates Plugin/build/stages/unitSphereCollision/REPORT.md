# unitSphereCollision -- compile report

**Source node:** `unitSphereCollision`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Unit-sphere collision deformer (accumulating "pusher" port). Every vertex
# INSIDE the collider sphere is pushed onto its surface, and the pushed result
# is kept in a persistent buffer (self.positions) so the deformation BAKES --
# once the collider passes, the dent stays put (it does not spring back). The
# collider is the UNIT sphere in the local space of the `pusher` matrix, so
# wiring a sphere transform's worldMatrix into `pusher` makes its translate /
# rotate / scale set the collider's centre, orientation and effective radius.
#
# self.positions is registered + seeded by the node's setup from the mesh's
# initial points; if it is missing or stale (topology change) it is re-seeded
# here from the current input. A deformer is not evaluated until a mesh is
# connected, so nothing computes before then.
#
# WARNING: getPoints()/setPoints() are OBJECT space while `pusher` is a WORLD
# matrix, so this is only correct when the deformed mesh has an identity
# transform at the world origin (freeze its transform).
mesh = self.outputGeometry[0]
pts  = mesh.getPoints()                         # (N, 3) current input, object space
if len(pts):
    seed = np.hstack([np.asarray(pts, dtype=float), np.ones((len(pts), 1))])
    try:
        buf = np.asarray(self.positions, dtype=float)
    except Exception:
        buf = None
    if buf is None or buf.ndim != 2 or buf.shape != (len(pts), 4):
        buf = seed                             # first eval / topology change -> seed

    P   = buf.copy()
    M   = self.pusher            # collider world matrix (MatrixView)
    inv = M.inverse().asNumpy()  # api2 analytic inverse (EM-safe)
    fwd = np.asarray(M, dtype=float)

    local             = P @ inv                                 # accumulated buffer -> collider local
    dist              = np.linalg.norm(local[:, :3], axis=1)
    inside            = (dist > 0.0) & (dist < 1.0)             # guard dist==0 (no push direction)
    local[inside, :3] = local[inside, :3] / dist[inside, None]  # onto surface
    P                 = local @ fwd                             # back to object space (buffer accumulates)

    self.positions = P              # persist the baked buffer
    env            = self.envelope  # blend the baked buffer against rest
    mesh.setPoints(pts + env * (P[:, :3] - pts))
```

## Files

```
build/stages/unitSphereCollision/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/unitSphereCollision/2_assisted.cpp       AI filled the unported region(s)
build/source/unitSphereCollision.cpp      SHIPPED
```
