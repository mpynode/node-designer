# procrustesTags -- compile report

**Source node:** `procrustesTags`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 20:36

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **4.98x** over 2 round(s) -- re-measured: unmeasurable under the gate |

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

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **2.874 ms** -> best **0.577 ms** (**4.98x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 12.437 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `mesh <- pSphereShape1.vtx[0]`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 2.874 ms | -- | -- |
| 01 | `gather_not_marshal` | this node is a GATHER, not a grid: stop materialising two 159k-vertex point tables and 20000 bind matrices when the cluster index block only ever names a handful of rows | 3.00x | 4.98x | 10.7 min | ACCEPTED |
| 02 | `profile_upstream_bound_no_win` | instrumented the whole compute and found 96% of it is Maya evaluating two upstream worldMesh[0] plugs inside data.inputValue(); nothing inside this file can reach that cost, and both attribute-level knobs that could have (setCached/setStorable) measured as noise, so the round ships the baseline unchanged | 2.00x | -- | 10.9 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `gather_not_marshal` -- predicted 3.00x, measured **4.98x**. compute() is pure input marshalling. np.take(vstack([pts, zeros(1,3)]), clusters, axis=0) reads exactly the rows in `clusters`, yet the lowered code built a full float->double table per mesh (push_back + a second copy in from_data), then copied each table AGAIN in vstack just to append one zero row -- four full passes over 3.8 MB apiece to fetch N*L rows. Likewise bindMatrices is clamped to bind[:min(cl.shape[0], bind.shape[0])], so with one clusterTags element exactly one of 20000 matrices survives, but all 20000 were read via inputValue()/asMatrix(). Fuse vstack+take into a direct gather off MFnMesh::getRawPoints (the (double)float cast is exact, so every gathered value is bit-identical), read only the bind prefix the clamp can reach, and get the array's logical length from the last physical element instead of walking all 20000.
* `profile_upstream_bound_no_win` -- predicted 2.00x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `profile_upstream_bound_no_win` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**
* outputs produced no comparable components across the sweep -- pointwise parity skipped (vacuous) | authored @maya_test: 1/1 passed

## Files

```
build/stages/procrustesTags/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/procrustesTags/3_optimized/00_baseline.cpp
build/stages/procrustesTags/3_optimized/01_gather_not_marshal.cpp
build/source/procrustesTags.cpp      SHIPPED
```
