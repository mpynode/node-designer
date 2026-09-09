# bubbleSort -- compile report

**Source node:** `bubbleSort`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:28

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **1.15x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# Name: Bubble Sort!  (port)
# Author: Eric Vignola - eric.vignola@gmail.com
#
# One bubble-sort pass per evaluation over n normalized random floats, where
# n = len(self.sort) = the number of connected outputs. Each output is lerped
# LIVE between minVal and maxVal, so dragging min/max rescales every output
# instantly (no re-sort). self.data / self.sorted are session-only.
#
# reset enum:  0 = False (sort one pass per eval, then hold sorted)
#              1 = True  (held reshuffle: regenerate every eval, never sorts)
#              2 = Auto  (sort, then auto-regenerate on completion -> loops
#                         forever with fresh patterns)
#
# (Imports live in the Init tab.)

n = len(self.sort)
reset = self.reset

# (re)generate normalized [0, 1] data: first eval, output-count change,
# True (held reshuffle), or Auto once the previous pass finished sorting.
regen = (not hasattr(self, 'data')) or len(self.data) != n
if reset == 1:
    regen = True
if reset == 2 and getattr(self, 'sorted', False):
    regen = True

if regen:
    self.data = [random.random() for _ in range(n)]
    self.sorted = False

# one bubble pass (skipped while held in True so it keeps reshuffling)
if reset != 1 and not self.sorted:
    self.sorted = True
    for i in range(n - 1):
        if self.data[i] > self.data[i + 1]:
            self.sorted = False
            self.data[i], self.data[i + 1] = self.data[i + 1], self.data[i]

self.text = 'SORTED!!!' if self.sorted else 'UNSORTED!!!'

# lerp each (partially) sorted float between the LIVE min/max
lo, hi = self.minVal, self.maxVal
self.sort = [lo + t * (hi - lo) for t in self.data]
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.002 ms** -> best **0.002 ms** (**1.15x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.333 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `maxVal (float)`, `minVal (float)`, `time (time)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.002 ms | -- | -- |
| 01 | `splitmix64_rng` | the node re-seeds a 312-word Mersenne Twister every evaluation to draw a single double; replace it with splitmix64 and strip the per-eval allocations around it | 2.00x | 1.15x | 7.5 min | ACCEPTED |
| 02 | `walk_array_no_builder` | replace the MArrayDataBuilder round-trip on the sort output with an in-place walk of the already-existing elements; it lost, so the round ships the pristine file unchanged | 1.30x | -- | 14.1 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `splitmix64_rng` -- predicted 2.00x, measured **1.15x**. this is an ELEMENTWISE node at n=1, not a QUERY node -- the harness seeds reset=1 ('held reshuffle') and only sort[0] exists, so regen fires on every tick and the entire per-eval cost is std::mt19937_64 state init plus a first-draw twist (~624 word-ops) plus a handful of Maya-side allocations. There is no scan to accelerate and no cross-eval structure worth caching, so the lever is deleting fixed overhead, not changing an exponent.
* `walk_array_no_builder` -- predicted 1.30x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `walk_array_no_builder` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**
* uses RNG via the AI porter (C++ <random>); not bit-identical to Python -- pointwise parity skipped | authored @maya_test: 1/1 passed

## Files

```
build/stages/bubbleSort/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/bubbleSort/2_assisted.cpp       AI filled the unported region(s)
build/stages/bubbleSort/3_optimized/00_baseline.cpp
build/stages/bubbleSort/3_optimized/01_splitmix64_rng.cpp
build/source/bubbleSort.cpp      SHIPPED
```
