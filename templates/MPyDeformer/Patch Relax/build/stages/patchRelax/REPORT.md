# patchRelax -- compile report

**Source node:** `patchRelax`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-09 14:19

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **3.21x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

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

**Parity gate: authored `@maya_test` only.** The generic pointwise compare did not run for this node, so every accepted round below was judged by the authored test's own scene -- a behavioural check, not a numerical one. The bench-scene fingerprint (when recorded below) is the only value-level check these rounds had.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `alpha (double)`, `iterations (int)`, `ringNbrs[0] (int)`, `ringWidth (int)`, `surfaceBlend (double)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 7.790 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **7.790 ms** -> best **2.430 ms** (**3.21x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 7.790 ms | -- | -- |
| 01 | `lazy_gate_inputs` | pull the rest mesh and read the 20k ring values only inside the size gate that consumes them, and probe the ring array's length in O(1) instead of walking 20k element handles | 2.00x | 3.21x | 13.2 min | ACCEPTED |
| 02 | `float_passthrough` | the bench never passes the ring-size gate (20000 ring ids vs 159602*Kw), so the timed path is the envelope pass-through; evaluate it in float, where this exact expression is bit-identical to the double form, and skip building the 20k-element ring handle when ringWidth <= 0 | 1.12x | 2.416 ms | 13.9 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `lazy_gate_inputs` -- predicted 2.00x, measured **3.21x**. at 159,602 verts and 20,000 ring elements the gate `len(flat) == N*Kw` can never pass, so every timed tick paid for a 20k MDataHandle walk, a 160k-vertex rest-mesh input pull (measured ~0.9-1.6 ms by itself), and three (N,3) double temporaries whose result is just P; the source reads restMesh and the ring values only inside the gate, so deferring them is a pure reordering with identical output. Measured on this Windows box: 8.06 -> 3.55 ms (ring probe + no double temporaries) -> 2.52 ms (rest-mesh pull deferred). A 4-wide unroll of the remaining float write-back loop measured slower (2.97 ms) and was reverted; the ~2.3 ms left is Maya's own deformer input->output mesh copy.
* `float_passthrough` -- predicted 1.12x, **rejected: not faster**. the deform body is dominated by the P + env*(P-P) loop widening 480k floats to double and narrowing back; (p-p) is exactly +-0/NaN, env*0 is exactly +-0/NaN, and p + (+-0) is exactly p in either precision, so float loses no bits and runs 4 lanes per op with no cvt; the ring array handle is only observable once Kw > 0, so reading ringWidth first and short-circuiting is the Python's own `and` semantics

### Rejected rounds

* `float_passthrough` -- rejected: not faster. the bench never passes the ring-size gate (20000 ring ids vs 159602*Kw), so the timed path is the envelope pass-through; evaluate it in float, where this exact expression is bit-identical to the double form, and skip building the 20k-element ring handle when ringWidth <= 0

## Verification

* parity: **pass**
* compute reshapes an array input by a scalar-int stride/width -- its array inputs are cross-coupled (element counts must be mutually consistent), which the generic per-input random drive cannot synthesize; pointwise parity skipped (authored @maya_test is the parity gate) | authored @maya_test: 1/1 passed

## Files

```
build/stages/patchRelax/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/patchRelax/3_optimized/00_baseline.cpp
build/stages/patchRelax/3_optimized/01_lazy_gate_inputs.cpp
build/stages/patchRelax/3_optimized/02_float_passthrough.cpp
build/source/patchRelax.cpp      SHIPPED
```
