# procrustesTags -- compile report

**Source node:** `procrustesTags`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-24 10:20

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **4.02x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

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

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `mesh <- pSphereShape1.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on the smallest scene (geo density 40 / array length 512) and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 11.169 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **11.169 ms** -> best **2.776 ms** (**4.02x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 11.169 ms | -- | -- |
| 01 | `gather_member_rows` | Read only the cluster-member vertices straight from the raw float buffers, and only the bind matrices below min(ncl, nbind), instead of widening both 159k-vertex meshes and all 20k bind matrices into double arrays every tick. | 3.00x | 4.02x | 8.8 min | ACCEPTED |
| 02 | `skip_bind_walk` | Read only the first ncl bind matrices by logical index instead of walking all 20000 bindMatrices elements, and run the per-cluster Procrustes fit as one scalar pass instead of ~60 nd:: whole-array temporaries. | 1.08x | 2.863 ms | 19.5 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `gather_member_rows` -- predicted 3.00x, measured **4.02x**. The bench seeds one tag row (clusterTags[0]='bench') against 20000 bind matrices, so the procrustes math runs on one cluster; the time goes to converting 2 x 159,602 verts to double (plus two vstack copies) and copying 20000 MMatrix into a dense vector that the clamp then slices to one row. np.take over vstack([pts, zeros]) is reproduced exactly (negative index wraps by V+1, -1 and V land on the zero row), and nbind still comes from a full logical-index scan, so every value is bit-identical.
* `skip_bind_walk` -- predicted 1.08x, **rejected: not faster**. The node's own work is a small slice of the pull: in-compute timers put inputValue(mesh) and inputValue(meshOrig) at ~1 ms each (Maya copying a 160k-vert mesh across the connection) and data.setClean(aOutMatrix) at 0.75-2 ms (20000 connected outMatrix elements), all fixed by the plug contract. What the node controls: a 20000-element MArrayDataHandle walk that only exists to find nbind for min(ncl, nbind), with ncl = 1 here, and nd:: allocation overhead around a single 3x3 SVD. Since nbind >= last physical element's logical index + 1, when that already reaches ncl the walk can be skipped and rows < ncl fetched with jumpToElement, whatever the element order. Otherwise it falls back to the original walk.

### Rejected rounds

* `skip_bind_walk` -- rejected: not faster. Read only the first ncl bind matrices by logical index instead of walking all 20000 bindMatrices elements, and run the per-cluster Procrustes fit as one scalar pass instead of ~60 nd:: whole-array temporaries.

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* verified with 1 geo/string input(s) left at default (unwired, could not be synthesized): clusterTags | authored @maya_test: 1/1 passed
* speed: compiled 0.555 ms vs interpreted 49.695 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/procrustesTags/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/procrustesTags/3_optimized/00_baseline.cpp
build/stages/procrustesTags/3_optimized/01_gather_member_rows.cpp
build/stages/procrustesTags/3_optimized/02_skip_bind_walk.cpp
build/source/procrustesTags.cpp      SHIPPED
```
