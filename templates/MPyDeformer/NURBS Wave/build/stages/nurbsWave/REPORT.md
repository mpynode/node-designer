# nurbsWave -- compile report

**Source node:** `nurbsWave`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-09 15:20

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **9.98x** over 4 round(s) -- 4 run of max 6, stopped: round 4 not-faster -- nothing new to compound from |

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

**Parity gate: authored `@maya_test` only.** The generic pointwise compare did not run for this node, so every accepted round below was judged by the authored test's own scene -- a behavioural check, not a numerical one. The bench-scene fingerprint (when recorded below) is the only value-level check these rounds had.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `amplitude (float)`, `freq (float)`, `time (time)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 8.312 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **8.312 ms** -> best **0.833 ms** (**9.98x**).

Rounds: **4** run of at most 6; the loop stopped because round 4 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 8.312 ms | -- | -- |
| 01 | `fuse_raw_sine_loop` | replace the whole-array nd:: temporaries (harvest to double, copy, slice, mul, add, sin, mul, add, assign, write-back) with one fused pass over the mesh's own float store that touches only x, then run that pass on a persistent 2-lane per-node pool | 3.00x | 2.53x | 25.2 min | ACCEPTED |
| 02 | `direct_compute_path` | answer outputGeometry[i] in compute() itself -- copy the input handle, deform the copy's raw float store, setClean -- so Maya's internal deformer pass (its MItGeometry build and bookkeeping) never runs for a full-membership mesh | 1.40x | 3.09x | 21.8 min | ACCEPTED |
| 03 | `single_input_pull` | pull input[i].inputGeometry once through a child-plug inputValue instead of inputArrayValue + element inputValue, which evaluated the shape's uncached worldMesh twice; then re-tune the kernel pool from 2 to 4 lanes now that the fixed overhead is halved | 2.60x | 9.98x | 23.3 min | ACCEPTED |
| 04 | `inline_fdlibm_sin` | replace the libm sin call in the per-vertex kernel with an inlined fdlibm-style Cody-Waite reduction + polynomial that rounds to the same float, so the loop body has no call and no data-dependent branch | 1.04x | 0.987 ms | 18.4 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `direct_compute_path` -- predicted 1.40x, measured **3.09x**. instrumenting the tick showed deform() itself is only ~0.4 ms of ~2.6 ms: the kernel cannot move the number, but Maya calls compute() BEFORE its internal copy+iterator+deform() pass and that pass is ~1 ms of overhead at 160k verts (an MItGeometry over the handle alone measured 1-2.3 ms); returning kSuccess from compute() after producing the output ourselves removes that level of work while hOut.copy() keeps the same data flow and the same float store the kernel already wrote
* `single_input_pull` -- predicted 2.60x, measured **9.98x**. in-compute timers put ~1.0 ms of a 1.35 ms tick in the two input-handle calls; a mayapy probe showed MPxGeometryFilter::inputGeom and the shape's worldMesh are both isCached=false (worldMesh: ~0.55 ms per pull at 160k verts, outMesh: 1 us), so each handle call re-evaluated the world mesh and block.inputValue(childPlug) asks for it exactly once; with the sin kernel then the largest remaining term (~0.3 ms at 2 lanes) more lanes should pay
* `inline_fdlibm_sin` -- predicted 1.04x, **rejected: not faster**. phase timers put the tick at pull=0.5-0.6 ms (Maya re-evaluating the uncached worldMesh[0], 65-70%), copy=0.003 (COW), membership=0.04, kernel=0.11-0.23 on 4 lanes; the kernel is the only part this file owns that is big enough to move, and a standalone check showed the inlined sin 20% faster than MSVC std::sin (0.46 vs 0.59 ms serial at 160k) with 0 float mismatches over 4 x 160k arguments

### Rejected rounds

* `inline_fdlibm_sin` -- rejected: not faster. replace the libm sin call in the per-vertex kernel with an inlined fdlibm-style Cody-Waite reduction + polynomial that rounds to the same float, so the loop body has no call and no data-dependent branch

## Verification

* parity: **pass**
* NURBS CV-idiom deformer (cvPositions/setCVPositions); generic drive uses a polygon sphere, so pointwise parity is skipped -- authored @maya_test drives a real NURBS surface | authored @maya_test: 1/1 passed

## Files

```
build/stages/nurbsWave/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/nurbsWave/3_optimized/00_baseline.cpp
build/stages/nurbsWave/3_optimized/01_fuse_raw_sine_loop.cpp
build/stages/nurbsWave/3_optimized/02_direct_compute_path.cpp
build/stages/nurbsWave/3_optimized/03_single_input_pull.cpp
build/stages/nurbsWave/3_optimized/04_inline_fdlibm_sin.cpp
build/source/nurbsWave.cpp      SHIPPED
```
