# rippleSurf -- compile report

**Source node:** `rippleSurf`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 17:58

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **1.98x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# Procedural RIPPLE SURFACE generator. Builds an 8x8 CV grid over a `size`-wide
# square in the XZ plane and lifts each CV in Y by a radial-ish sin/cos ripple of
# `amplitude` and `freq`. `t` (a time input auto-wired to the timeline) advances
# the ripple phase so it animates on playback. Hands the flat (nu*nv, 3) CV form
# to the NurbsSurface constructor with num_u/num_v (row-major). LOWERS to pure
# C++ (emit_geo).
import numpy as np
nu = 8
nv = 8
u = np.linspace(0.0, self.size, nu)
v = np.linspace(0.0, self.size, nv)
# Broadcast into (nu, nv) grids, then flatten row-major (k = i*nv + j).
Uf = (u[:, None] + np.zeros((nu, nv))).reshape(nu * nv)
Vf = (np.zeros((nu, nv)) + v[None, :]).reshape(nu * nv)
phase = self.t * 0.1
Yf = self.amplitude * np.sin(Uf * self.freq + phase) * np.cos(Vf * self.freq + phase)
cvs = np.stack([Uf, Yf, Vf], axis=1)
self.outSurface = NurbsSurface(points=cvs, num_u=nu, num_v=nv,
                               degree_u=3, degree_v=3)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `amplitude (float)`, `freq (float)`, `size (float)`, `t (time)`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 0.022 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **0.022 ms** -> best **0.011 ms** (**1.98x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.022 ms | -- | -- |
| 01 | `fuse_grid_cache_knots` | Replace the ~12 nd::Array temporaries of the numpy chain with one direct 8x8 loop writing a reused MPointArray, and build the two constant open-uniform knot vectors once in the constructor instead of every tick. | 1.60x | 1.98x | 12.6 min | ACCEPTED |
| 02 | `reuse_output_surface_rejected` | Refilling the surface already on outSurface with setCVs+updateSurface instead of creating a fresh MFnNurbsSurfaceData each tick was measured 3.7x SLOWER, so the create path is kept unchanged. | 1.30x | 0.013 ms | 12.7 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `reuse_output_surface_rejected` -- predicted 1.30x, **rejected: not faster**. The node is ELEMENTWISE at 64 CVs (8x8 grid, 16 sin/cos calls), so the math is well under 1 us of an ~8 us tick and every input (amplitude, freq, size, t) moves between ticks, leaving nothing to cache; the only lever was the Maya-side cost of MFnNurbsSurfaceData::create + MFnNurbsSurface::create + freeing the previous pair every tick, which in-place setCVs on the constant-topology surface should remove.

### Rejected rounds

* `reuse_output_surface_rejected` -- rejected: not faster. Refilling the surface already on outSurface with setCVs+updateSurface instead of creating a fresh MFnNurbsSurfaceData each tick was measured 3.7x SLOWER, so the create path is kept unchanged.

## Verification

* parity: **pass**
* verify could not run: 'NoneType' object has no attribute 'add_input_attr' | authored @maya_test: 1/1 passed

## Files

```
build/stages/rippleSurf/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/rippleSurf/3_optimized/00_baseline.cpp
build/stages/rippleSurf/3_optimized/01_fuse_grid_cache_knots.cpp
build/stages/rippleSurf/3_optimized/02_reuse_output_surface_rejected.cpp
build/source/rippleSurf.cpp      SHIPPED
```
