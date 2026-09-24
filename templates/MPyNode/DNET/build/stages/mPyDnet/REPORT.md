# mPyDnet -- compile report

**Source node:** `dnet`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-24 11:53

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **1.83x** over 2 round(s) -- 2 run of max 6, stopped: round 2 gained 1.10x, below the 1.15x needed to continue |

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

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `anchors[0] (float)`, `damping (float)`, `index0[0] (int)`, `index1[0] (int)`, `inverseMatrix (matrix)`, `iterations (int)`, `matrices[0] (matrix)`, `pull[0] (float)`, `push[0] (float)`, `tension[0] (float)`, `time (time)`, `tolerance (float)`; outputs checked (4 plug(s)); accepts re-timed against the incumbent on the smallest scene (geo density 40 / array length 512) and rejected if slower there.

Baseline **18.110 ms** -> best **9.909 ms** (**1.83x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 gained 1.10x, below the 1.15x needed to continue.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 18.110 ms | -- | -- |
| 01 | `raw_matrices_pooled_knot_map` | Replace the MMatrix vector with raw row-major doubles (input read, both blend products, row-3-only previous) and run the per-knot product+blend+inverse and the two solver phases as parallel maps on a persistent per-node pool, with per-link forces computed once instead of twice. | 2.50x | 1.83x | 29.9 min | ACCEPTED |
| 02 | `persistent_scratch_state` | Move the solver state from a static node registry into a per-instance member that also owns every per-tick scratch buffer, then trim the solve: one fused parallel region per Jacobi iteration instead of two, a threaded post-solve pass, and the serial adjacency rebuild overlapped with the per-knot matrix map. | 1.15x | 2.01x | 27.1 min | rejected: invalid candidate |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `raw_matrices_pooled_knot_map` -- predicted 2.50x, measured **1.83x**. Profile of one tick (16.6 ms, it~9): read 3.8, blend 1.65, solve 3.6, inverse 2.5, previous 0.65, finalize 3.9 ms. The node is ELEMENTWISE (N=L=20000, no scan), so the levers are per-access overhead and serial per-knot work: (1) the per-element std::vector<MMatrix> resize/copy on read and the exported MMatrix::operator*/get/ctor calls dominate read+blend+previous; MMatrix::operator* accumulates each entry left to right (verified bit-identical on 320k random entries, pairwise differed on 30%), so a raw product is exact, and only previous[:,3,:] is ever read so 4 doubles/knot suffice. (2) inv(matrices[k]) depends on nothing the solve produces, so it moves into the same per-knot map (column 3 of the inverse is never read, so its solve is skipped). (3) The solver's per-knot gather recomputed each link's sqrt/div for both endpoints; a per-link force pass + a per-knot gather/apply pass keeps the Jacobi split and the per-knot summation order. Maps write disjoint slots; the convergence max stays a serial loop in knot order.
* `persistent_scratch_state` -- predicted 1.15x, **rejected: invalid candidate**. Accepted by the optimizer at 2.01x, withheld in review: besides its parallel maps it runs the serial adjacency rebuild on the calling thread concurrently with the per-knot map -- outside the one threading shape the optimizer rules permit (a parallel map on the pool, the calling thread waiting).

### Rejected rounds

* `persistent_scratch_state` -- rejected: invalid candidate. Accepted by the optimizer at 2.01x, withheld in review: besides its parallel maps it runs the serial adjacency rebuild on the calling thread concurrently with the per-knot map -- outside the one threading shape the optimizer rules permit (a parallel map on the pool, the calling thread waiting).

## Verification

* parity: **pass**  (maxerr 1.8496648408472538e-05, tol 0.0001)
* compared on 23 of 30 input sets: on 7 the interpreted reference was non-idempotent (it carries state, and the harness evaluates it more often than the compiled node), so those cannot be lined up pointwise | authored @maya_test: 1/1 passed
* speed: compiled 67.105 ms vs interpreted 130.324 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/mPyDnet/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/mPyDnet/2_assisted.cpp       AI filled the unported region(s)
build/stages/mPyDnet/3_optimized/00_baseline.cpp
build/stages/mPyDnet/3_optimized/01_raw_matrices_pooled_knot_map.cpp
build/stages/mPyDnet/3_optimized/02_persistent_scratch_state.cpp
build/source/mPyDnet.cpp      SHIPPED
```
