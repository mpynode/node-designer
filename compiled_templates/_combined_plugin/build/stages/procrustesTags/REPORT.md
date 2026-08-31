# procrustesTags -- compile report

**Source node:** `procrustesTags`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Vectorized Procrustes attachment. Cluster ids resolve LIVE from this node's
# component-tag names off the input mesh DATA each evaluation; bind offsets come
# from self.bindMatrices. Mesh inputs are reached via self.X (self-only contract);
# self.mesh follows the worldMesh[0] connection to the DEFORMED upstream output.
# Every input is read defensively: during EAGER evaluation (mid-wiring, before
# the demo seeds bind vars / authors the tags, or while a mesh input is
# momentarily unconnected) any read can be unavailable -- no-op until the node
# is fully configured so a partial state never raises.
_ok = True
try:
    rest = self.meshOrig.points
    deformed = self.mesh.points
    # Tags are authored on the deforming `mesh` (visible twistTubeShape); resolve
    # membership LIVE off its data so tag edits take effect immediately.
    cl = np.asarray(self.mesh.tag_clusters(self.clusterTags), dtype=np.int64)
    bind = np.asarray(self.bindMatrices, dtype=np.float64).reshape(-1, 4, 4)
    # cluster count (live from clusterTags) and bind count (the per-ring offset
    # INPUT) can diverge the instant a user adds/removes a tag NAME from the
    # multi-string input. procrustes_clusters broadcasts bind row-for-row against
    # clusters, so a mismatch would raise -- clamp both to the common length so a
    # tag edit is a clean partial update rather than a crash.
    _n = min(cl.shape[0], bind.shape[0])
    cl = cl[:_n]
    bind = bind[:_n]
except Exception:
    _ok = False
if _ok and cl.shape[0] and rest.shape[0] and deformed.shape[0]:
    self.outMatrix = procrustes_clusters(rest, deformed, cl, bind)
```

## Files

```
build/stages/procrustesTags/1_transpiled.cpp     deterministic transpile (no AI)
build/source/procrustesTags.cpp      SHIPPED
```
