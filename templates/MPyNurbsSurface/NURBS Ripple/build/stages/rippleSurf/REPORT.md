# rippleSurf -- compile report

**Source node:** `rippleSurf`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:29

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **2.14x** over 2 round(s) -- re-measured: unmeasurable under the gate |

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

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.012 ms** -> best **0.006 ms** (**2.14x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.017 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `amplitude (float)`, `freq (float)`, `size (float)`, `t (time)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.012 ms | -- | -- |
| 01 | `separable_ripple_grid` | the 8x8 ripple is a separable outer product, so the nd::Array pipeline and 112 of its 128 transcendentals are pure bookkeeping -- compute S[i]*C[j] straight into a reused MPointArray | 2.00x | 2.14x | 9.1 min | ACCEPTED |
| 02 | `reuse_out_data_container` | reclaim the kNurbsSurfaceData container already parked in the output handle and build into it, instead of allocating a fresh one plus a setMObject round trip every evaluation | 1.15x | 0.007 ms | 13.4 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `reuse_out_data_container` -- predicted 1.15x, **rejected: not faster**. this node is ELEMENTWISE and tiny -- 64 CVs, 16 transcendentals -- so no arithmetic change can matter; at ~5.7 us/eval the only per-evaluation costs left are Maya API calls, and the two unconditional ones are MFnNurbsSurfaceData::create (a heap allocation) and MDataHandle::setMObject. Both disappear once the container is reused, since MFnNurbsSurface::create fully overwrites the geometry inside it.

### Rejected rounds

* `reuse_out_data_container` -- rejected: not faster. reclaim the kNurbsSurfaceData container already parked in the output handle and build into it, instead of allocating a fresh one plus a setMObject round trip every evaluation

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* authored @maya_test: 1/1 passed
* speed: compiled 0.021 ms vs interpreted 0.218 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/rippleSurf/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/rippleSurf/3_optimized/00_baseline.cpp
build/stages/rippleSurf/3_optimized/01_separable_ripple_grid.cpp
build/stages/rippleSurf/3_optimized/02_reuse_out_data_container.cpp
build/source/rippleSurf.cpp      SHIPPED
```
