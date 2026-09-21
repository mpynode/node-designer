# mPyDnet -- compile report

**Source node:** `dnet`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | not run |

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
N        = matrices.shape[0]

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
    L      = min(index0.shape[0], index1.shape[0])
    if L == 0 and N >= 2:
        index0 = np.arange(N - 1, dtype=np.int32)
        index1 = np.arange(1, N, dtype=np.int32)
        L      = N - 1
    else:
        index0 = index0[:L]
        index1 = index1[:L]

    def _dense(v, neutral):
        a = np.asarray(v, dtype=np.float64).ravel()
        if a.shape[0] >= L:
            return a[:L]
        out              = np.full(L, neutral, dtype=np.float64)
        out[:a.shape[0]] = a
        return out

    restLengths = _dense(self.restLengths, 1.0)  # rest length per link
    tension     = _dense(self.tension,     0.0)  # per-link contraction (0 = none)
    push        = _dense(self.push,        1.0)  # per-link compression resistance
    pull        = _dense(self.pull,        1.0)  # per-link stretch resistance

    self.node.evaluate(matrices, anchors, restLengths,
                       inverseMatrix=self.inverseMatrix, index0=index0, index1=index1,
                       tensions=tension, push=push, pull=pull,
                       reset      = self.resetBuffer,
                       iterations = self.iterations,
                       tolerance  = self.tolerance,
                       damping=self.damping)

    self.positions     = self.node.local_positions
    self.lengths       = self.node.lengths
    self.maxIterations = self.node.iterations
    self.maxForce      = self.node.max_force

    # Store previous state
    self.previous = self.node.previous
```

## Files

```
build/stages/mPyDnet/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/mPyDnet/2_assisted.cpp       AI filled the unported region(s)
build/source/mPyDnet.cpp      SHIPPED
```
