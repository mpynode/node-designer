# patchRelax -- compile report

**Source node:** `patchRelax`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-08 23:23

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **3.16x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# Patch-based surface relaxation (de Goes et al., Pixar, SIGGRAPH '18 Talks).
# Every vertex flattens its 1-ring into a 2D "decal map", derives span-aware edge
# weights from it, fits the rest->posed rotation of that patch by SVD, and steps
# toward the rotated REST edge layout. Because the target carries the patch's own
# rotation, the silhouette survives -- unlike a Laplacian smooth, which shrinks.
#
# `ringNbrs` (flat row-major CCW 1-ring vertex ids, -1 padded) and `ringWidth`
# (the padded width) are DECLARED INPUTS that **Rebuild Rings** seeds. They are
# inputs rather than something the compute derives because (a) they depend only
# on TOPOLOGY, so rebuilding them per frame is pure waste, and (b) building them
# needs repeat/argsort/bincount, every one of which the transpiler rejects --
# seeding them is what lets the whole compute lower to PURE C++.
#
# A deformer is live the instant mc.deformer() creates it, so "no rest mesh yet"
# and "rings not built yet" are the NORMAL startup states, not exotic ones -- the
# gates below are the common path, not error handling.
#
# They are PURELY NUMERIC and nested rather than a try/except, for two reasons.
# nd_lower strips a top-level eager guard on the generic compute path but NOT on
# the deform path, so a try here would drop the node to the AI porter and break
# the pure-C++ rule. And the nesting is what makes that safe: an unconnected mesh
# input reads as None, but `ringWidth > 0` can only be true once Rebuild Rings
# has run, and that refuses to run without a rest mesh connected -- so the
# `self.restMesh` read is unreachable until a rest mesh exists. (Merely
# DISCONNECTING one later does not resurrect the None: Maya retains the last mesh
# in the datablock.) setPoints stays UNCONDITIONAL so the deformer keeps its
# single getPoints/setPoints shape; the gates only choose what gets written.
mesh = self.outputGeometry[0]
P = mesh.getPoints()
N = P.shape[0]
flat = np.asarray(self.ringNbrs, dtype=np.int64)
Kw = int(self.ringWidth)

out = P
if (Kw > 0) and (flat.shape[0] == N * Kw):
    rest = self.restMesh.points
    if rest.shape[0] == N:
        out = patch_relax(P, rest, flat.reshape(N, Kw), int(self.iterations),
                          self.alpha, self.surfaceBlend)
mesh.setPoints(P + self.envelope * (out - P))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **4.778 ms** -> best **1.514 ms** (**3.16x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 14.114 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `alpha (double)`, `iterations (int)`, `ringNbrs[0] (int)`, `ringWidth (int)`, `surfaceBlend (double)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 4.778 ms | -- | -- |
| 01 | `fuse_marshalling` | at bench scale the ring gate is CLOSED, so patch_relax never runs and the node is pure ELEMENTWISE marshalling -- so delete every whole-array temporary between Maya's MPointArray and the nd::Array, and make each input lazy exactly where the Python makes it lazy | 1.30x | 2.09x | 14.7 min | ACCEPTED |
| 02 | `inplace_mesh_floats` | profile first, then delete the MItGeometry double round-trip: deform the output mesh's own float point buffer in place instead of marshalling 159k MPoints out through allPositions and back through setAllPositions | 1.35x | 3.16x | 11.9 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `fuse_marshalling` -- predicted 1.30x, measured **2.09x**. ringNbrs is 20000 elements while the mesh is 159602 verts, so `flat.shape[0] == N * Kw` can never hold and `out` is always literally `P`; the entire 4.78 ms is therefore MArrayDataHandle walking + three full-size double buffers (nd::from_data allocs a zero-init vector and then copies a second one onto it) + MPointArray::operator[] called 320k times across the DSO boundary, none of which is arithmetic
* `inplace_mesh_floats` -- predicted 1.35x, measured **3.16x**. the node is ELEMENTWISE, not QUERY -- the patch_relax gate (flat.shape[0] == N*Kw, 20000 vs 159602) can never open under the bench scene, so nothing algorithmic is running and the whole cost is per-access overhead. An in-deform profile showed 0.62 ms of the 2.10 ms median inside deform() and 0.51 ms of THAT in allPositions (0.35) + setAllPositions (0.16), which build and consume a 5.1 MB MPointArray of doubles that the mesh stores as floats anyway. Reaching the output geometry through block.outputArrayValue(outputGeom) and writing its raw float buffer directly removes both marshalling passes without changing a single arithmetic operation: the blend is still evaluated in double on values that were float-exact to begin with, exactly as MPoint delivered them.

## Verification

* parity: **pass**
* compute reshapes an array input by a scalar-int stride/width -- its array inputs are cross-coupled (element counts must be mutually consistent), which the generic per-input random drive cannot synthesize; pointwise parity skipped (authored @maya_test is the parity gate) | authored @maya_test: 1/1 passed

## Files

```
build/stages/patchRelax/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/patchRelax/3_optimized/00_baseline.cpp
build/stages/patchRelax/3_optimized/01_fuse_marshalling.cpp
build/stages/patchRelax/3_optimized/02_inplace_mesh_floats.cpp
build/source/patchRelax.cpp      SHIPPED
```
