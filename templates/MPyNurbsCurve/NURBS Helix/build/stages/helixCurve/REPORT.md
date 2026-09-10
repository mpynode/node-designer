# helixCurve -- compile report

**Source node:** `helixCurve`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 17:32

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **5.41x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# Procedural HELIX generator. Builds the (N, 3) CV positions and hands them to
# the NurbsCurve constructor: a coil of `radius`, total rise `height`, `turns`
# full revolutions. `t` (a time input auto-wired to the timeline) slowly spins
# the coil so it animates on playback. NurbsCurve marshals the CVs ->
# kNurbsCurveData; the native compile reproduces that build step, so this lowers
# to pure C++.
import numpy as np
n = 120
u = np.linspace(0.0, 1.0, n)
ang = u * self.turns * 2.0 * np.pi + self.t * 0.05
x = self.radius * np.cos(ang)
z = self.radius * np.sin(ang)
y = (u - 0.5) * self.height
cvs = np.stack([x, y, z], axis=1)
self.outCurve = NurbsCurve(points=cvs, degree=3)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `height (float)`, `radius (float)`, `t (time)`, `turns (float)`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 0.018 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **0.018 ms** -> best **0.003 ms** (**5.41x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.018 ms | -- | -- |
| 01 | `refill_curve_in_place` | the helix is 120 CVs with fixed topology, so refill the previous tick's kNurbsCurveData with setCVs+updateCurve instead of creating a fresh curve object every evaluation, and fuse the numpy chain into one allocation-free loop over constant u / knot tables built once in the constructor | 1.60x | 5.41x | 10.5 min | ACCEPTED |
| 02 | `raw_cv_cursor_bind_fnset` | Fill the reused CV buffer through a contiguity-proven raw MPoint pointer and keep the output curve's function set bound across evaluations, so one tick makes about ten Maya calls instead of about 135. | 1.30x | 0.004 ms | 22.0 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `refill_curve_in_place` -- predicted 1.60x, measured **5.41x**. at 120 points the arithmetic is negligible; the 18 us is dominated by MFnNurbsCurveData::create + MFnNurbsCurve::create (allocation, knot validation, internal curve build) and by ~10 shared_ptr<vector> temporaries plus a 122-append MDoubleArray knot rebuild per tick. Fusing the chain removes the temporaries (measured 0.0174 -> 0.0116 ms); writing CVs into the existing output data object removes the curve rebuild (measured 0.0116 -> 0.0033 ms). Every CV is recomputed every tick; only the container is reused, guarded on numCVs/degree/form/numKnots and falling back to create().
* `raw_cv_cursor_bind_fnset` -- predicted 1.30x, **rejected: not faster**. At 120 CVs the compute is ~1.9 us of call overhead, not arithmetic: 120 out-of-line MPointArray::set calls (~300 ns) plus a six-call hasFn/ctor/numCVs/degree/form/numKnots re-validation of the same data object every tick (~350 ns) are a third of it, while the exact sincos loop (~300 ns) and setCVs+updateCurve (~450 ns) are the floor the public API allows. Removing whole calls, not cheapening the math, is the lever; every input moves to a fresh value each tick so no input-keyed cache can hit.

### Rejected rounds

* `raw_cv_cursor_bind_fnset` -- rejected: not faster. Fill the reused CV buffer through a contiguity-proven raw MPoint pointer and keep the output curve's function set bound across evaluations, so one tick makes about ten Maya calls instead of about 135.

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/helixCurve/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/helixCurve/3_optimized/00_baseline.cpp
build/stages/helixCurve/3_optimized/01_refill_curve_in_place.cpp
build/stages/helixCurve/3_optimized/02_raw_cv_cursor_bind_fnset.cpp
build/source/helixCurve.cpp      SHIPPED
```
