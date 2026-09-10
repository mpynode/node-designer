# spline -- compile report

**Source node:** `spline`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 16:59

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **8507.12x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# Name: Spline Node  (numpy-first port)
# Author: Eric Vignola - eric.vignola@gmail.com
# A De Boor b-spline evaluator (arbitrary degree). cv = input vector array,
# samples = output vector array. Node-aware of #inputs / #outputs.
#
# (Imports + helper functions live in the Init tab.)

# -------------------------- Main --------------------------#
c = len(self.cv)
degree = min(self.degree, c - 1)

# Open knot vector (float array via numpy so the same source lowers to
# deterministic C++; values match the original [0]*d + range + [c-d]*d list).
n = len(self.samples)
kv = np.concatenate([np.zeros(degree, dtype=np.float64),
                     np.arange(c - degree + 1, dtype=np.float64),
                     np.full(degree, float(c - degree), dtype=np.float64)])

for i in range(n):
    u = float(i) / (n - 1) * float(kv[-1])
    acc = np.zeros(3)
    for k in range(c):
        w = DeBoor(u, k, degree, kv)
        acc = acc + self.cv[k] * w
    self.samples[i] = acc

if len(self.cv) > 0 and len(self.samples) > 0:
    self.samples[-1] = self.cv[-1]
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 40 / array length 512; noise floor 15 ms; moved per tick: `cv[0] (vector)`; outputs checked (1 plug(s)).

Baseline **91.026 ms** -> best **0.011 ms** (**8507.12x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 91.026 ms | -- | -- |
| 01 | `local_support_basis` | evaluate only the d+1 basis functions whose support contains u -- the other c-d-1 are exactly +-0.0 and cannot change the accumulator -- with the same Cox-de Boor recursion, so the O(n*c*2^d) std::function sum becomes O(n*(d+1)*2^d) and is bit-identical | 300.00x | 8507.12x | 15.5 min | ACCEPTED |
| 02 | `write_through_asdouble3_ref` | store each output sample through the double3& that MDataHandle::asDouble3() exposes instead of calling set3Double, and fuse the sample evaluation into that write loop so a tick allocates nothing and never round-trips an n*3 temporary | 1.05x | 0.009 ms | 15.2 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `local_support_basis` -- predicted 300.00x, measured **8507.12x**. the node is QUERY-shaped (every sample scans every control point) but the scanned function has compact support: a degree-d B-spline basis is exactly zero unless one of its d+1 degree-0 leaves contains u, and adding +-0.0 to an accumulator that is never -0.0 is a no-op under round-to-nearest. Locating the knot span by binary search (confirmed with the reference's exact leaf test) and evaluating just k in [span-d, span] removes a LEVEL of work (512 -> 4 basis evaluations per sample) instead of making each evaluation cheaper. Dropping the std::function recursion and the per-(i,k) nd::Array allocation of the accumulator is a constant-factor bonus. Non-finite cv or n == 1 (u = 0/0 = NaN) fall back to the full-range reference loop so NaN/inf propagation stays identical.
* `write_through_asdouble3_ref` -- predicted 1.05x, **rejected: not faster**. incumbent under 2 ms: 1.15x required, measured 1.13x

### Rejected rounds

* `write_through_asdouble3_ref` -- rejected: not faster. incumbent under 2 ms: 1.15x required, measured 1.13x

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* on 13 of 30 input sets the interpreted reference raised mid-compute (an input the node rejects, e.g. a negative degree) and left stale outputs; those sets were excluded | authored @maya_test: 1/1 passed
* speed: compiled 0.089 ms vs interpreted 31.659 ms (best of 3, geo 40 / array 512)

## Files

```
build/stages/spline/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/spline/3_optimized/00_baseline.cpp
build/stages/spline/3_optimized/01_local_support_basis.cpp
build/stages/spline/3_optimized/02_write_through_asdouble3_ref.cpp
build/source/spline.cpp      SHIPPED
```
