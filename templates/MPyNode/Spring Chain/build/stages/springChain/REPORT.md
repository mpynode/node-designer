# springChain -- compile report

**Source node:** `springChain`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-24 11:51

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- 1 region(s) still marked incomplete |
| 3 AI optimize | **2.87x** over 3 round(s) -- 3 run of max 6, stopped: round 3 no-change -- nothing new to compound from |

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

## Unfinished work in the generated C++

* **not translated:** the Python node restores self.position / self.velocity from the saved scene (mPyNode stored vars); this region can add no storable attribute and may do no file I/O, so the buffers are session-only and a reopened scene restarts the chain from zero (the vanilla seed below) instead of from its saved state.

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `damping (float)`, `driver (vector)`, `gravity (vector)`, `mass (float)`, `maxDistance (float)`, `minDistance (float)`, `tension (float)`, `time (time)`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on the smallest scene (geo density 40 / array length 512) and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 3.170 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **3.170 ms** -> best **1.105 ms** (**2.87x**).

Rounds: **3** run of at most 6; the loop stopped because round 3 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 3.170 ms | -- | -- |
| 01 | `inplace_output_write` | Write the 20000-element driven multi in place, fused into the serial spring loop, instead of building and swapping in a brand-new MArrayDataBuilder array every tick. | 2.00x | 2.87x | 25.4 min | ACCEPTED |
| 02 | `overlap_chain_with_setclean` | Run the inherently serial spring chain on a persistent per-node worker thread while the calling thread performs Maya's expensive attribute-level data.setClean(aDriven), then write the outputs in place chunk by chunk as the worker publishes them. | 1.50x | 4.11x | 21.6 min | rejected: invalid candidate |
| 03 | `caller_fused_until_worker_ready` | NO CHANGE SHIPPED: the caller integrated and wrote links itself until the chain worker woke, then handed it the rest; it measured slower and springChain.cpp was restored byte-identical to the entry file. | 1.18x | -- | 10.9 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `inplace_output_write` -- predicted 2.00x, measured **2.87x**. A phase profile of the original showed the finalize (20000 addElement + set3Double + outArr.set) at 2.1-2.9 ms of a ~3 ms tick, the latency-bound spring chain at 0.2-0.5 ms and the vector copy at ~40 us. The node is ELEMENTWISE (serial recurrence, no query, nothing cacheable: every input it reads moves), so the lever is per-access overhead: writing the existing elements in place removes a 20000-element allocate/free per tick, and emitting each element right after its spring lets the out-of-order core overlap the Maya calls with the chain's divide/sqrt latency. Accepted follow-ups, each A/B'd 3/3 with byte-identical fingerprints: layout checked once up front instead of elementIndex() per element; the min/max clamp if/elif turned into a select (the bench drives minDistance == maxDistance, so inside-vs-outside flips link to link and mispredicts, flushing the overlapped API work); spring rewritten on named scalars and the chain state carried in plain doubles across the opaque API calls. Also lifted the static NodeState registry to a per-instance member. Rejected: writing through asDouble3() instead of set3Double (slower 3/3), a bit-mask select (mixed), and writing through the existing array's own builder (addElement + set3Double, 2 calls instead of 3) -- slower 3/3, because addElement's index lookup costs more than next().
* `overlap_chain_with_setclean` -- predicted 1.50x, **rejected: invalid candidate**. Accepted by the optimizer at 4.11x, withheld in review: it runs the serial chain on a persistent worker thread while the compute thread calls data.setClean and writes the chunks the worker publishes -- a producer/consumer pipeline, outside the one threading shape the optimizer rules permit (a parallel map), and its setClean-before-write ordering was only checked in DG.
* `caller_fused_until_worker_ready` -- predicted 1.18x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `overlap_chain_with_setclean` -- rejected: invalid candidate. Accepted by the optimizer at 4.11x, withheld in review: it runs the serial chain on a persistent worker thread while the compute thread calls data.setClean and writes the chunks the worker publishes -- a producer/consumer pipeline, outside the one threading shape the optimizer rules permit (a parallel map), and its setClean-before-write ordering was only checked in DG.
* `caller_fused_until_worker_ready` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* compared on 16 of 30 input sets: on 14 the interpreted reference was non-idempotent (it carries state, and the harness evaluates it more often than the compiled node), so those cannot be lined up pointwise | authored @maya_test: 1/1 passed
* speed: compiled 0.045 ms vs interpreted 0.261 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/springChain/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/springChain/2_assisted.cpp       AI filled the unported region(s)
build/stages/springChain/3_optimized/00_baseline.cpp
build/stages/springChain/3_optimized/01_inplace_output_write.cpp
build/stages/springChain/3_optimized/02_overlap_chain_with_setclean.cpp
build/source/springChain.cpp      SHIPPED
```
