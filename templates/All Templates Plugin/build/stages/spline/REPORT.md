# spline -- compile report

**Source node:** `spline`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Name: Spline Node  (numpy-first port)
# Author: Eric Vignola - eric.vignola@gmail.com
# A De Boor b-spline evaluator (arbitrary degree). cv = input vector array,
# samples = output vector array. Node-aware of #inputs / #outputs.
#
# (Imports + helper functions live in the Init tab.)

# -------------------------- Main --------------------------#
c      = len(self.cv)
degree = min(self.degree, c - 1)

# Open knot vector (float array via numpy so the same source lowers to
# deterministic C++; values match the original [0]*d + range + [c-d]*d list).
n = len(self.samples)
kv = np.concatenate([np.zeros(degree, dtype=np.float64),
                     np.arange(c - degree + 1, dtype=np.float64),
                     np.full(degree, float(c - degree), dtype=np.float64)])

for i in range(n):
    u   = float(i) / (n - 1) * float(kv[-1])
    acc = np.zeros(3)
    for k in range(c):
        w   = DeBoor(u, k, degree, kv)
        acc = acc + self.cv[k] * w
    self.samples[i] = acc

if len(self.cv) > 0 and len(self.samples) > 0:
    self.samples[-1] = self.cv[-1]
```

## Files

```
build/stages/spline/1_transpiled.cpp     deterministic transpile (no AI)
build/source/spline.cpp      SHIPPED
```
