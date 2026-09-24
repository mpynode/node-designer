# bubbleSort -- compile report

**Source node:** `bubbleSort`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-24 11:04

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **2.82x** over 3 round(s) -- 3 run of max 6, stopped: round 3 no-change -- nothing new to compound from |

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

**Parity gate: authored `@maya_test` only.** The generic pointwise compare did not run for this node, so every accepted round below was judged by the authored test's own scene -- a behavioural check, not a numerical one. The bench-scene fingerprint (when recorded below) is the only value-level check these rounds had.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `maxVal (float)`, `minVal (float)`, `time (time)`; outputs skipped (node draws random numbers); accepts re-timed against the incumbent on the smallest scene (geo density 40 / array length 512) and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 1.895 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **1.895 ms** -> best **0.672 ms** (**2.82x**).

Rounds: **3** run of at most 6; the loop stopped because round 3 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 1.895 ms | -- | -- |
| 01 | `builder_addlast_asfloat` | fill the 20k-element sort[] builder with addLast().asFloat() in one fused lerp loop (no temp vector, no setFloat call, RNG built only on regen, state moved from a static registry to a per-instance member) | 1.10x | 1.57x | 17.6 min | ACCEPTED |
| 02 | `inplace_sort_write` | Write the 20k sort[] floats in place through the existing element handles (jumpToElement(i) proves the 0..n-1 layout, builder kept as fallback) instead of rebuilding the whole array with MArrayDataBuilder, and fuse a bit-identical inlined mt19937_64 draw into that write loop. | 2.00x | 2.82x | 20.8 min | ACCEPTED |
| 03 | `no_change_setclean_floor` | No candidate beat the entry file, so bubbleSort.cpp is left byte-identical: about 70% of compute() is Maya's mandatory data.setClean(aSort) on 20000 connected elements, and no change inside the node can shrink it. | 1.30x | -- | 20.3 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `builder_addlast_asfloat` -- predicted 1.10x, measured **1.57x**. compute() is not algorithmic here (bench drives reset=1: 20k RNG draws = 43 us); it is Maya per-element API cost -- the builder fill (~190 us) plus the mandatory data.setClean(aSort) over 20k connected elements (0.4-1.2 ms) -- so cutting API calls per element is the only controllable lever. Probe: fill loop 174-250 us -> 126-150 us, and setClean ran cheaper after asFloat writes. Tried and rejected: in-place outputValue() writes (loop 115 us but setClean 1.6-2.0 ms, total 2.27 ms), reusing _outArr.builder() (fill 450-900 us), swapping setClean/setAllClean order (no gain)
* `inplace_sort_write` -- predicted 2.00x, measured **2.82x**. The profile put data.setClean(aSort) at 500-1300 us and I read it as Maya tearing down the replaced 20k-element array, so writing in place would drop both the builder allocations and that teardown. Wrong half: a no-write diagnostic shows setClean is ~260-330 us whether we write or not, so it is Maya's per-plug bookkeeping for 20k connected elements. The measured win is all on our side of the call: builder fill 145 us -> 105 us in place, RNG 42 us -> 24 us, fusing the draw into the write saves another 12-20 us.
* `no_change_setclean_floor` -- predicted 1.30x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `no_change_setclean_floor` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**
* uses RNG via the AI porter (C++ <random>); not bit-identical to Python -- pointwise parity skipped | authored @maya_test: 1/1 passed

## Files

```
build/stages/bubbleSort/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/bubbleSort/2_assisted.cpp       AI filled the unported region(s)
build/stages/bubbleSort/3_optimized/00_baseline.cpp
build/stages/bubbleSort/3_optimized/01_builder_addlast_asfloat.cpp
build/stages/bubbleSort/3_optimized/02_inplace_sort_write.cpp
build/source/bubbleSort.cpp      SHIPPED
```
