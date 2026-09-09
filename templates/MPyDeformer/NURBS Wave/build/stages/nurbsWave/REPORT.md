# nurbsWave -- compile report

**Source node:** `nurbsWave`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-08 20:37

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **6.03x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# NURBS wave deformer: push each CV along X (the default nurbsPlane's normal --
# that plane lies in YZ with X=0) by a travelling sine of its Y coordinate, so a
# clear wave ripples across the surface. Reads CVs via the NURBS idiom
# cvPositions()/setCVPositions() (mPyDeformer also accepts mesh
# getPoints/setPoints). `time` (auto-wired to the timeline) animates the wave;
# `envelope` (0..1) blends it against rest.
import numpy as np
h = self.outputGeometry[0]
rest = h.cvPositions()                 # (N, 3) object-space CVs (numpy)
env = float(self.envelope)
out = rest.copy()
out[:, 0] = out[:, 0] + env * self.amplitude * np.sin(rest[:, 1] * self.freq + self.time * 0.1)
h.setCVPositions(out)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **4.219 ms** -> best **0.700 ms** (**6.03x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 13.724 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `amplitude (float)`, `freq (float)`, `time (time)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 4.219 ms | -- | -- |
| 01 | `raw_points_inplace` | Fuse the nd expression tree into one loop, then stop round-tripping 160k verts through an MPointArray at all -- deform the output mesh's own float point buffer in place, with a persistent per-node pool mapping over disjoint vertex ranges. | 3.00x | 2.52x | 10.9 min | ACCEPTED |
| 02 | `skip_deformer_mesh_copy` | override compute() so the wave is written straight into the datablock's existing output mesh buffer, instead of letting MPxGeometryFilter deep-copy the 160k-vert input mesh into the output and then hand us an MItGeometry over it | 2.00x | 6.03x | 11.0 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `skip_deformer_mesh_copy` -- predicted 2.00x, measured **6.03x**. the arithmetic was already a rounding error in the total: a no-op deform() still measured 1.418 ms of a 1.569 ms tick, and aliasing the input mesh to the output with no copy at all measured 0.521 ms, so ~0.90 ms per evaluation is Maya's input->output mesh copy plus iterator construction and NOT the sine; the output data object the datablock already holds has the identical topology every tick, so reusing that shell and streaming src->dst with the wave fused into the same pass removes a whole level of work rather than making the existing work cheaper

## Verification

* parity: **pass**
* NURBS CV-idiom deformer (cvPositions/setCVPositions); generic drive uses a polygon sphere, so pointwise parity is skipped -- authored @maya_test drives a real NURBS surface | authored @maya_test: 1/1 passed

## Files

```
build/stages/nurbsWave/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/nurbsWave/3_optimized/00_baseline.cpp
build/stages/nurbsWave/3_optimized/01_raw_points_inplace.cpp
build/stages/nurbsWave/3_optimized/02_skip_deformer_mesh_copy.cpp
build/source/nurbsWave.cpp      SHIPPED
```
