# nurbsWave -- compile report

**Source node:** `nurbsWave`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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

## Files

```
build/stages/nurbsWave/1_transpiled.cpp     deterministic transpile (no AI)
build/source/nurbsWave.cpp      SHIPPED
```
