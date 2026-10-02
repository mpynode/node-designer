# twistSwingSkin -- compile report

**Source node:** `twistSwingSkin`  ·  **Base:** `MPxSkinCluster`  ·  **Generated:** 2026-09-09 18:24

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **5.01x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# ----------------------------------------------------------------------
# mPySkinCluster -- twist/swing with TWO weight sets on ONE node, painted
# interactively via the skinMode enum, COMPILABLE to pure C++.
#
# self.twistWeights / self.swingWeights are declared (double, is_array) INPUT
# plugs holding the two dense weight sets FLATTENED row-major to length N*J:
# twistWeights drives the DUAL-QUATERNION twist, swingWeights the LINEAR-BLEND
# swing (bend). Being plugs, they serialize PER NODE (each character keeps its
# own weights) and the compiled deform reads them directly -- so this node
# compiles to byte-parity (the two sets are never shared across instances).
#
# skinMode is a PAINT-MODE selector:
#   0 Paint LBS (Swing) -> preview the live weightList with linear_blend; paint it
#                          and sync_paint banks the edits into swingWeights.
#   1 Paint DQS (Twist) -> preview the live weightList with dual_quaternion; paint
#                          it and sync_paint banks the edits into twistWeights.
#   2 Live Result       -> deform from BOTH weight-set plugs (twist + swing).
# twistAxis picks the bone-local twist axis (0 X default / 1 Y / 2 Z).
#
# self.sync_paint(mode) holds ALL the interactive machinery (load the active set
# into weightList on a mode switch so Paint Skin Weights shows it; bank painted
# weightList back into the active set plug on a settled eval). It is a blessed
# NativeSideEffect method: interpreted-only, and a bare call lowers to NOTHING in
# the compiled node (which runs headless -- no paint session -- and reads the two
# weight plugs directly, so omitting the scratchpad staging is faithful).
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

mode = int(self.skinMode)

# interactive paint load/bank/latch (a no-op in the compiled node).
self.sync_paint(mode)

nj        = self.matrix.shape[0]           # influence count
nv        = rest.shape[0]                  # vertex count
twist     = np.asarray(self.twistWeights)  # flat (N*J,) weight-set plugs
swing     = np.asarray(self.swingWeights)
have_sets = twist.size == nv * nj and swing.size == nv * nj

if mode == 0:                                    # Paint LBS: preview live weightList
    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)
elif mode == 1:                                  # Paint DQS: preview live weightList
    deformed = self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)
elif have_sets:                                  # Live Result: both weight-set plugs
    deformed = self.twist_swing_dual(rest, twist.reshape(nv, nj), swing.reshape(nv, nj), self.matrix, self.bindPreMatrix, int(self.twistAxis))
else:                                            # not seeded yet -> plain LBS fallback
    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)

# envelope=0 rest, 1 fully skinned (partial-effect composition explicit here).
mesh.setPoints(rest + float(self.envelope) * (deformed - rest))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `swingWeights[0] (double)`, `twistWeights[0] (double)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 4.645 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **4.645 ms** -> best **0.927 ms** (**5.01x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 4.645 ms | -- | -- |
| 01 | `defer_weight_reads_reuse_ptsbuf` | read the two 20000-element weight-set plugs only on the branch that consumes them, fuse linear_blend into one strided loop with no (N,4) concat, and keep the 3n-double rest-point store as a per-instance buffer instead of faulting in a fresh 4 MB block every tick | 2.50x | 5.01x | 13.4 min | ACCEPTED |
| 02 | `lazy_rest_float_source` | stop widening the 160k rest points to a 3.8 MB double copy every tick; the linear-blend kernel and the envelope blend read the mesh's own float store, and the double copy is built only for the nd-heavy dual-quaternion and generic-broadcast paths | 1.15x | 0.929 ms | 12.7 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `defer_weight_reads_reuse_ptsbuf` -- predicted 2.50x, measured **5.01x**. the bench wires no joints (J=0) so every tick is: 40000 MArrayDataHandle element reads whose values are never used, an N*3 push_back widening, an (N,4) homogeneous concat, then a shape-mismatch throw; none of that is numeric work, so removing the reads and the two big allocations should take the node to Maya's own mesh-copy floor
* `lazy_rest_float_source` -- predicted 1.15x, **rejected: not faster**. incumbent under the noise floor: second measurement 0.929 ms did not confirm 0.757 ms

### Rejected rounds

* `lazy_rest_float_source` -- rejected: not faster. incumbent under the noise floor: second measurement 0.929 ms did not confirm 0.757 ms

## Verification

* parity: **pass**
* verify could not run: Unable to create/find dependency node. | authored @maya_test: 1/1 passed

## Files

```
build/stages/twistSwingSkin/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/twistSwingSkin/3_optimized/00_baseline.cpp
build/stages/twistSwingSkin/3_optimized/01_defer_weight_reads_reuse_ptsbuf.cpp
build/stages/twistSwingSkin/3_optimized/02_lazy_rest_float_source.cpp
build/source/twistSwingSkin.cpp      SHIPPED
```
