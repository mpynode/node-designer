# procrustesTags -- compile report

**Source node:** `procrustesTags`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 14:44

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **4.94x** over 3 round(s) -- 3 run of max 6, stopped: round 3 no-change -- nothing new to compound from |

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

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `mesh <- pSphereShape1.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 10.035 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **10.035 ms** -> best **2.031 ms** (**4.94x**).

Rounds: **3** run of at most 6; the loop stopped because round 3 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 10.035 ms | -- | -- |
| 01 | `gather_members_not_meshes` | Read only what the math touches: gather the cluster-member points straight from the two meshes' float stores instead of widening both 160k-vertex meshes to double, and pull only the first min(clusterRows, bindRows) bind matrices by logical index instead of marshalling all 20000. | 1.70x | 4.27x | 15.8 min | ACCEPTED |
| 02 | `fuse_kabsch_kernel` | replace the generic nd:: array chain (18 whole-array temporaries, reshape/slice/tile/einsum/svd/det/matmul) with one fused per-cluster Kabsch kernel that calls svd3_core directly and reproduces every accumulation in the same left-fold order | 1.02x | 4.94x | 21.1 min | ACCEPTED |
| 03 | `profile_upstream_bound_no_change` | timed every segment of compute() at the bench scene and found 94% of the tick is Maya evaluating the two non-cached upstream worldMesh[0] plugs inside data.inputValue(), 6% is the one unavoidable MFnMesh attach per mesh, and everything this file can reach is under 15 us combined -- so the round ships the baseline unchanged | 1.00x | -- | 15.1 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `gather_members_not_meshes` -- predicted 1.70x, measured **4.27x**. compute() spent O(V + B) on marshalling for an O(n*w) problem: two (V,3) float->double copies (V=159602) fed a vstack+take that reads n*w rows, and 20000 MMatrix handle reads fed a slice that keeps n rows. The harness seeds a string multi with ONE element, so n=1 here and everything except the two Maya mesh pulls is removable. The gather reproduces take(vstack(pts, zeros(1,3)), cl, 0) exactly: negative index wraps by V+1, index V reads the appended zero row, float->double widening is unchanged.
* `fuse_kabsch_kernel` -- predicted 1.02x, measured **4.94x**. profiling compute() with steady_clock showed ~1800 of ~2000 us are the two data.inputValue() pulls of upstream worldMesh[0] (a non-cached world-space attribute Maya re-copies on every pull -- getAttr -ca reports False, and a bare dgeval of the plug alone costs 0.45 ms), plus ~85 us of one-time lazy mesh finalisation that fires on the FIRST function-set attach to the freshly tweaked mesh (MItMeshVertex pays it instead of MFnMesh, so it is not avoidable while the vertex count is needed). Of the ~150 us the node itself owns, the nd:: chain was ~40 us of pure allocation and odometer overhead for a single 3x3 problem; a fused kernel with fixed-size stack arrays takes ~2.5 us and is bit-identical (same svd3_core, same left-fold sums over l ascending, same einsum operand order, same 3x3 det formula, same matmul l order).
* `profile_upstream_bound_no_change` -- predicted 1.00x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `profile_upstream_bound_no_change` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* verified with 1 geo/string input(s) left at default (unwired, could not be synthesized): clusterTags | authored @maya_test: 1/1 passed
* speed: compiled 0.257 ms vs interpreted 25.595 ms (best of 3, geo 40 / array 512)

## Files

```
build/stages/procrustesTags/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/procrustesTags/3_optimized/00_baseline.cpp
build/stages/procrustesTags/3_optimized/01_gather_members_not_meshes.cpp
build/stages/procrustesTags/3_optimized/02_fuse_kabsch_kernel.cpp
build/source/procrustesTags.cpp      SHIPPED
```
