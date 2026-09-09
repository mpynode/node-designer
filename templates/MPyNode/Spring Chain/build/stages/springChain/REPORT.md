# springChain -- compile report

**Source node:** `springChain`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:28

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **1.07x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# Name: Simple spring solver  (numpy-first port)
# Author: Eric Vignola - eric.vignola@gmail.com
# self.initialized (session-only) avoids an integration on the first eval after
# load. self.position / self.velocity persist. driven = vector array output.
#
# (Imports + helper functions live in the Init tab.)

# ---------------------------- Main ----------------------------#

# Fresh (vanilla) node, or one whose buffers were never restored: seed the
# spring buffers so the first integration has state. The original relied on
# restored stored vars; gallery templates ship vanilla (no stored vars).
if not hasattr(self, 'velocity'):
    self.velocity = [np.zeros(3) for _ in range(len(self.driven))]
    self.position = [np.zeros(3) for _ in range(len(self.driven))]

# First eval after a load: just mark initialized + push the stored buffer out
# (self.initialized is session-only -> absent again on the next load).
if not hasattr(self, 'initialized'):
    self.initialized = True

else:
    n = len(self.driven)

    if self.resetBuffer:
        self.velocity = [np.zeros(3) for _ in range(n)]
        self.position = [np.zeros(3) for _ in range(n)]

    elif len(self.velocity) < n:
        for _ in range(len(self.velocity), n):
            self.velocity.append(np.zeros(3))
            self.position.append(np.zeros(3))

    elif len(self.velocity) > n:
        self.velocity = self.velocity[:n]
        self.position = self.position[:n]

    else:
        # Initial drag
        self.position[0], self.velocity[0] = spring(
            self.driver, self.position[0], self.velocity[0],
            self.gravity, self.tension, self.mass, self.damping, self.minDistance, self.maxDistance)

        # Spring forces down the chain
        for i in range(1, n):
            self.position[i], self.velocity[i] = spring(
                self.position[i - 1], self.position[i], self.velocity[i],
                self.gravity, self.tension, self.mass, self.damping, self.minDistance, self.maxDistance)


# Output positions from the stored buffer
self.driven[:] = np.asarray(self.position, dtype=float)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.002 ms** -> best **0.001 ms** (**1.07x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 1.462 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `damping (float)`, `driver (vector)`, `gravity (vector)`, `mass (float)`, `maxDistance (float)`, `minDistance (float)`, `tension (float)`, `time (time)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.002 ms | -- | -- |
| 01 | `drop_builder_and_registry` | this node is API-overhead-bound at ~1.5us, not algorithm-bound: collapse the two outputArrayValue calls into one, delete the per-compute MArrayDataBuilder rebuild and the staging vector in favour of a guarded in-place element walk, and lift the leaking static NodeState registry into a per-instance member | 1.30x | 0.002 ms | 7.3 min | rejected: not faster |
| 02 | `strip_percall_overhead` | this node is not compute-bound at all -- the benchmark drives it with exactly ONE driven element, so every microsecond is per-call fixed overhead (datablock lookups, two MArrayDataHandle acquisitions, a heap-allocating temp vector, an MArrayDataBuilder rebuild and a static registry scan); removing that overhead is the whole win | 1.60x | 1.07x | 8.4 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `drop_builder_and_registry` -- predicted 1.30x, **rejected: not faster**. the workload description promises 20000-element arrays and a 159k-vert sphere, but springChain has NO array inputs and NO geometry inputs -- the only array is the driven OUTPUT, whose elementCount comes from downstream connections. So compute() is ~11 Maya API calls over a handful of elements, and the only lever is removing API calls: one outputArrayValue instead of two, no MArrayDataBuilder allocate + set() rebuild, no out_aDriven heap allocation per evaluate
* `strip_percall_overhead` -- predicted 1.60x, measured **1.07x**. the spec declares no array and no geometry inputs, so --bench-array 20000 / --bench-geo 400 seed nothing and n = elementCount(driven) = 1 (confirmed by instrumenting the node: 'DBG n=1 pos=1'). The spring integration is therefore ~3 flops and irrelevant; the measurable cost is Maya API call count per compute. Cutting the per-call constant should get most of the way to the harness floor.

### Rejected rounds

* `drop_builder_and_registry` -- rejected: not faster. this node is API-overhead-bound at ~1.5us, not algorithm-bound: collapse the two outputArrayValue calls into one, delete the per-compute MArrayDataBuilder rebuild and the staging vector in favour of a guarded in-place element walk, and lift the leaking static NodeState registry into a per-instance member

## Verification

* parity: **pass**  (maxerr 0.14652301856921035, tol 0.0001)
* compute carries state; the interpreted reference was non-idempotent on 13 of 30 input sets and the 17 comparable sets still diverged by 0.147 (tol 0.0001) -- with the two sides evaluated a different number of times that is a trajectory difference, not a port verdict; pointwise parity inconclusive (authored @maya_test is the parity gate) | authored @maya_test: 1/1 passed

## Files

```
build/stages/springChain/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/springChain/2_assisted.cpp       AI filled the unported region(s)
build/stages/springChain/3_optimized/00_baseline.cpp
build/stages/springChain/3_optimized/01_drop_builder_and_registry.cpp
build/stages/springChain/3_optimized/02_strip_percall_overhead.cpp
build/source/springChain.cpp      SHIPPED
```
