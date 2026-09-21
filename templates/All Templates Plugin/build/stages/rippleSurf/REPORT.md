# rippleSurf -- compile report

**Source node:** `rippleSurf`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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
u  = np.linspace(0.0, self.size, nu)
v  = np.linspace(0.0, self.size, nv)
# Broadcast into (nu, nv) grids, then flatten row-major (k = i*nv + j).
Uf    = (u[:, None] + np.zeros((nu, nv))).reshape(nu * nv)
Vf    = (np.zeros((nu, nv)) + v[None, :]).reshape(nu * nv)
phase = self.t * 0.1
Yf    = self.amplitude * np.sin(Uf * self.freq + phase) * np.cos(Vf * self.freq + phase)
cvs   = np.stack([Uf, Yf, Vf], axis=1)
self.outSurface = NurbsSurface(points=cvs, num_u=nu, num_v=nv,
                               degree_u=3, degree_v=3)
```

## Files

```
build/stages/rippleSurf/1_transpiled.cpp     deterministic transpile (no AI)
build/source/rippleSurf.cpp      SHIPPED
```
