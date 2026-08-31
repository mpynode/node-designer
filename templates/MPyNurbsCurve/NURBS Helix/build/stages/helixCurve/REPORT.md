# helixCurve -- compile report

**Source node:** `helixCurve`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-25 10:44

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **9.50x** over 2 round(s) |

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

Baseline **0.015 ms** -> best **0.002 ms** (**9.50x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.015 ms | -- | -- |
| 01 | `reuse_curve_data_inplace` | the node is a fixed 120-CV generator whose topology never changes, so stop rebuilding the nurbsCurve data object every tick -- fuse the five nd::Array passes into one allocation-free loop and push the new CVs into the data object already on the output plug | 2.50x | 5.63x | 11.0 min | ACCEPTED |
| 02 | `cache_turns_circle_bind_fnset` | split the helix angle into a turns-only unit-circle table cached across evaluations and a one-sincos time rotation, then stop re-establishing the output curve's identity with a fresh MFnNurbsCurve every tick | 2.00x | 9.50x | 13.2 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `reuse_curve_data_inplace` -- predicted 2.50x, measured **5.63x**. at n=120 the arithmetic is irrelevant; the whole 12.4us is per-allocation and per-Maya-call overhead. Six nd::Array allocs plus a 360-double stack plus two growing Maya arrays plus a full MFnNurbsCurve::create per evaluation are all avoidable, because CV count, degree, form and the entire knot vector are compile-time constants for this node and only the CV positions move.
* `cache_turns_circle_bind_fnset` -- predicted 2.00x, measured **9.50x**. at 120 CVs the node is not arithmetic-bound but call-bound: 120 __sincos plus 120 out-of-line MPointArray::operator[] plus a per-tick hasFn/MFnNurbsCurve-construct/numCVs/degree/form re-validation are the whole body, so removing whole CALLS -- not making the math cheaper -- is the lever

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/helixCurve/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/helixCurve/3_optimized/00_baseline.cpp
build/stages/helixCurve/3_optimized/01_reuse_curve_data_inplace.cpp
build/stages/helixCurve/3_optimized/02_cache_turns_circle_bind_fnset.cpp
build/source/helixCurve.cpp      SHIPPED
```
