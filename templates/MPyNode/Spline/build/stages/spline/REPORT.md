# spline -- compile report

**Source node:** `spline`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-25 10:32

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **3697.75x** over 2 round(s) |

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

Baseline **4.437 ms** -> best **0.001 ms** (**3697.75x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 4.437 ms | -- | -- |
| 01 | `span_limited_deboor` | a degree-d b-spline basis is nonzero on only d+1 control points, so compute the knot span once and let it prune the CV scan, the cv reads and the knot vector all at once | 15.00x | 3697.75x | 13.8 min | ACCEPTED |
| 02 | `bypass_output_builder` | the node was already at its algorithmic floor, so the round went to the output write: skip MArrayDataBuilder and the array swap when the samples multi already holds exactly the logical indices 0..n-1, and stop re-allocating the sample scratch every evaluation | 1.30x | 0.001 ms | 7.6 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `span_limited_deboor` -- predicted 15.00x, measured **3697.75x**. the lowered form is QUERY-shaped by accident: for every sample it scans all c control points and adds cv[k]*0.0 for all but d+1 of them. The knot span s (kv[s] <= u < kv[s+1]) is closed-form for an open uniform knot vector, so the scan collapses to k in [s-d, s]. Adding an exact 0.0 to a nonzero double is the identity, so restricting the loop in the same increasing-k order reproduces the accumulation bit for bit rather than merely within tolerance. Three consequences, each measured separately: (1) O(n*c) -> O(n*(d+1)) arithmetic; (2) the UNION of the per-sample spans is the only part of the cv multi the answer can depend on, and that union is a pure function of (i, n, c, degree) -- computable in a pre-pass with no cv reads at all -- so the 20000-element MArrayDataHandle walk shrinks to the window plus cv[c-1] for the endpoint override; (3) the c+degree+1 knot vector is just clamp(j-degree, 0, c-degree), so it never needs to be materialised.
* `bypass_output_builder` -- predicted 1.30x, **rejected: not faster**. an in-process profile (buffered std::chrono, dumped after the timed region) showed steady-state compute() at 210-290 ns against a ~1100 ns measured tick, so ~75-80% of what the benchmark times is Maya DG dispatch plus the Python asMDataHandle() call and is untouchable; of the ~250 ns that IS ours the four segments were near-equal at 1-2 clock ticks each (the clock quantizes at ~41.7 ns), and the only segment holding a heap allocation and a whole-array swap was the output write, so replacing the builder with in-place element handles was the one place left where a LEVEL of work could be removed rather than a constant shaved

### Rejected rounds

* `bypass_output_builder` -- rejected: not faster. the node was already at its algorithmic floor, so the round went to the output write: skip MArrayDataBuilder and the array swap when the samples multi already holds exactly the logical indices 0..n-1, and stop re-allocating the sample scratch every evaluation

## Verification

* parity: **pass**
* outputs produced no comparable components across the sweep -- pointwise parity skipped (vacuous) | authored @maya_test: 1/1 passed

## Files

```
build/stages/spline/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/spline/3_optimized/00_baseline.cpp
build/stages/spline/3_optimized/01_span_limited_deboor.cpp
build/stages/spline/3_optimized/02_bypass_output_builder.cpp
build/source/spline.cpp      SHIPPED
```
