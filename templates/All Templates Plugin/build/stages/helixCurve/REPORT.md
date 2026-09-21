# helixCurve -- compile report

**Source node:** `helixCurve`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Procedural HELIX generator. Builds the (N, 3) CV positions and hands them to
# the NurbsCurve constructor: a coil of `radius`, total rise `height`, `turns`
# full revolutions. `t` (a time input auto-wired to the timeline) slowly spins
# the coil so it animates on playback. NurbsCurve marshals the CVs ->
# kNurbsCurveData; the native compile reproduces that build step, so this lowers
# to pure C++.
import numpy as np
n             = 120
u             = np.linspace(0.0, 1.0, n)
ang           = u * self.turns * 2.0 * np.pi + self.t * 0.05
x             = self.radius * np.cos(ang)
z             = self.radius * np.sin(ang)
y             = (u - 0.5) * self.height
cvs           = np.stack([x, y, z], axis=1)
self.outCurve = NurbsCurve(points=cvs, degree=3)
```

## Files

```
build/stages/helixCurve/1_transpiled.cpp     deterministic transpile (no AI)
build/source/helixCurve.cpp      SHIPPED
```
