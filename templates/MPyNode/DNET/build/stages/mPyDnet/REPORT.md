# mPyDnet -- compile report

**Source node:** `dnet`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 20:44

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **3.77x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# DNET spring-network relaxation -- the source dnet .mpn's Compute
# expression (bugs/dnet_code.mpn), built on the VERBATIM numba Solver in the Init
# tab. The only addition over the .mpn's one-liner is reading the per-link inputs
# DENSELY: the .mpn's evaluate() fills a neutral default only for a *None* arg, but
# in an mPyNode a demo / create_link network wires the topology
# (index0 / index1 / restLengths) and tension yet leaves push / pull unset (empty
# multis) -- a raw pass would let the kernels index past a short array and silently
# ship an unrelaxed (all-zero) solve. So we pad each per-link array to the link
# count (the same "compute reads dense" contract the numpy-free port used); for a
# network whose arrays are already full (the .mpn's own scenes) this is a no-op and
# the Solver sees exactly what it did there.

import numpy as np

# `previous` is the solver carry-over state. In the source .mpn it is a persistent
# stored var (returns None until first solved); as a vanilla template it starts as
# session scratch, so seed it to None on first touch -- Solver(None) cold-starts
# (snaps free knots to their live goals). Promote `previous` to persistent (Data
# column) to carry the solved state across scene save / load like the .mpn.
if not hasattr(self, 'previous'):
    self.previous = None

# Init the node
if not hasattr(self, 'node'):
    self.node = Solver(self.previous)

matrices = np.asarray(self.matrices, dtype=np.float64).reshape(-1, 4, 4)
N = matrices.shape[0]

if self.evaluate and N > 0:
    # anchors dense to the knot count (unset knots read 0 == free).
    anchors = np.asarray(self.anchors, dtype=np.float64).ravel()
    if anchors.shape[0] < N:
        anchors = np.concatenate([anchors, np.zeros(N - anchors.shape[0])])
    else:
        anchors = anchors[:N]

    # Topology: paired link indices. Fall back to an open chain when no links are
    # wired so a bare (no-demo) node still relaxes into a line.
    index0 = np.asarray(self.index0, dtype=np.int32).ravel()
    index1 = np.asarray(self.index1, dtype=np.int32).ravel()
    L = min(index0.shape[0], index1.shape[0])
    if L == 0 and N >= 2:
        index0 = np.arange(N - 1, dtype=np.int32)
        index1 = np.arange(1, N, dtype=np.int32)
        L = N - 1
    else:
        index0 = index0[:L]
        index1 = index1[:L]

    def _dense(v, neutral):
        a = np.asarray(v, dtype=np.float64).ravel()
        if a.shape[0] >= L:
            return a[:L]
        out = np.full(L, neutral, dtype=np.float64)
        out[:a.shape[0]] = a
        return out

    restLengths = _dense(self.restLengths, 1.0)   # rest length per link
    tension = _dense(self.tension, 0.0)           # per-link contraction (0 = none)
    push = _dense(self.push, 1.0)                 # per-link compression resistance
    pull = _dense(self.pull, 1.0)                 # per-link stretch resistance

    self.node.evaluate(matrices, anchors, restLengths,
                       inverseMatrix=self.inverseMatrix, index0=index0, index1=index1,
                       tensions=tension, push=push, pull=pull,
                       reset=self.resetBuffer,
                       iterations=self.iterations,
                       tolerance=self.tolerance,
                       damping=self.damping)

    self.positions     = self.node.local_positions
    self.lengths       = self.node.lengths
    self.maxIterations = self.node.iterations
    self.maxForce      = self.node.max_force

    # Store previous state
    self.previous = self.node.previous
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **5.963 ms** -> best **1.580 ms** (**3.77x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 12.944 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `anchors[0] (float)`, `damping (float)`, `index0[0] (int)`, `index1[0] (int)`, `inverseMatrix (matrix)`, `iterations (int)`, `matrices[0] (matrix)`, `pull[0] (float)`, `push[0] (float)`, `tension[0] (float)`, `time (time)`, `tolerance (float)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 5.963 ms | -- | -- |
| 01 | `adjugate_inverse` | Profiled compute() into five sections and removed whole levels of work from the three fattest: replace 20000 general MMatrix::inverse() calls with a direct adjugate that only forms the three columns actually read, build only row 3 of the prev*inverseMatrix product instead of the full 4x4, and walk the spring links once scattering the +/- force to both endpoints instead of recomputing every link twice from each endpoint's adjacency slot. | 1.50x | 1.76x | 9.8 min | ACCEPTED |
| 02 | `cache_clean_array_inputs` | snapshot every array input in per-instance state and re-walk only the multis that actually went dirty, then inline the matrices*inverseMatrix product and collapse the solver's three redundant 480 KB streams into one fused pass | 2.20x | 3.77x | 11.7 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_clean_array_inputs` -- predicted 2.20x, measured **3.77x**. profiling said the compute was 40% MArrayDataHandle traversal (1330 us for 6 multis x 20000 elements) and only ONE array input moves between ticks, so invalidating on setDependentsDirty + preEvaluation + an element-count backstop should retire five sixths of that read cost outright; the residual solve time is per-element overhead and whole-array temporaries, not arithmetic, so inlining MMatrix::operator* and deleting positionsPrev/displacements/the per-iteration F fill should take the rest

## Verification

* parity: **pass**  (maxerr 1.3969838619232178e-09, tol 0.0001)
* compared on 23 of 30 input sets: on 7 the interpreted reference was non-idempotent (it carries state and re-runs its compute 2-3x per dgdirty where the compiled node runs once), so those cannot be lined up pointwise | authored @maya_test: 1/1 passed
* speed: compiled 4.067 ms vs interpreted 30.663 ms (best of 3, geo 40 / array 512)

## Files

```
build/stages/mPyDnet/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/mPyDnet/2_assisted.cpp       AI filled the unported region(s)
build/stages/mPyDnet/3_optimized/00_baseline.cpp
build/stages/mPyDnet/3_optimized/01_adjugate_inverse.cpp
build/stages/mPyDnet/3_optimized/02_cache_clean_array_inputs.cpp
build/source/mPyDnet.cpp      SHIPPED
```
