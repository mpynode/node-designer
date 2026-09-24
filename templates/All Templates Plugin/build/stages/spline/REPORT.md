# spline -- compile report

**Source node:** `spline`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-24 09:51

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **6143.89x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

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

Baseline **94.001 ms** -> best **0.015 ms** (**6143.89x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 94.001 ms | -- | -- |
| 01 | `cache_sparse_basis` | Cache the De Boor basis weights per instance as a sparse table (at most degree+1 per sample), keyed on cv count, effective degree and sample count, so a tick that only moves cvs costs O(n*(d+1)) instead of O(n*c*2^(d+1)) recursive std::function calls; then write the output array in place instead of rebuilding it with MArrayDataBuilder. | 200.00x | 6143.89x | 7.9 min | ACCEPTED |
| 02 | `direct_handle_io` | cut per-element Maya data-handle calls: prove the cv and samples arrays dense once instead of calling elementIndex per element, write outputs through the asDouble3 reference instead of set3Double, and evaluate each sample straight into its output handle instead of staging a 12 KB buffer | 1.25x | 0.020 ms | 17.8 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_sparse_basis` -- predicted 200.00x, measured **6143.89x**. The weights depend only on (c, degree, n), and all three hold between ticks; only cv VALUES move. Outside the support [jmin-d, jmax] every weight is exactly +-0, and acc is never -0, so skipping those terms is bit-exact when cvs are finite. Non-finite cvs, n<2 and negative degree fall back to the original lowered loop, kept unchanged.
* `direct_handle_io` -- predicted 1.25x, **rejected: not faster**. the sparse basis cache already made the math ~1 us, so compute is bound by ~3.5k OpenMaya calls on 512 cvs + 512 samples (profiled: read 4.8 us, basis eval 1.3 us, write+finalize 7.8 us); dropping one call per element on each side and the staging pass removes a level of per-element work while the arithmetic (same operand order, same +-0 behaviour) is untouched

### Rejected rounds

* `direct_handle_io` -- rejected: not faster. cut per-element Maya data-handle calls: prove the cv and samples arrays dense once instead of calling elementIndex per element, write outputs through the asDouble3 reference instead of set3Double, and evaluate each sample straight into its output handle instead of staging a 12 KB buffer

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* on 13 of 30 input sets the interpreted reference raised mid-compute (an input the node rejects, e.g. a negative degree) and left stale outputs; those sets were excluded | authored @maya_test: 1/1 passed
* speed: compiled 0.136 ms vs interpreted 103.268 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/spline/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/spline/3_optimized/00_baseline.cpp
build/stages/spline/3_optimized/01_cache_sparse_basis.cpp
build/stages/spline/3_optimized/02_direct_handle_io.cpp
build/source/spline.cpp      SHIPPED
```
