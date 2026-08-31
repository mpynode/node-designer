# twistSwingSkin -- compile report

**Source node:** `twistSwingSkin`  ·  **Base:** `MPxSkinCluster`  ·  **Generated:** 2026-08-25 10:56

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **1.93x** over 2 round(s) |

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

nj = self.matrix.shape[0]                        # influence count
nv = rest.shape[0]                               # vertex count
twist = np.asarray(self.twistWeights)            # flat (N*J,) weight-set plugs
swing = np.asarray(self.swingWeights)
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

Baseline **2.470 ms** -> best **1.282 ms** (**1.93x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 2.470 ms | -- | -- |
| 01 | `direct_fill_reused_buffers` | this node is ELEMENTWISE, not QUERY: at 159602 verts the arithmetic is nil and the whole cost is whole-array temporaries, so every per-evaluation malloc + value-init memset + redundant copy was replaced by a direct fill into a size-guarded per-instance scratch buffer | 1.35x | 1.63x | 12.9 min | ACCEPTED |
| 02 | `cache_weight_arrays` | cache the two 20000-element weight-set plug reads across evaluations, invalidated by setDependentsDirty + preEvaluation + an elementCount/first/last fingerprint | 1.15x | 1.93x | 10.9 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_weight_arrays` -- predicted 1.15x, measured **1.93x**. profiling showed the deform is pure per-access overhead, not arithmetic: of ~1.24 ms in-node, 0.34 ms is walking 2 x 20000 MArrayDataHandle elements at ~8.5 ns each. Maya re-runs deform() when ANY input goes dirty, and the benchmark's perturb function moves only swingWeights[0], so twistWeights is re-walked identically on every tick. Caching the derived flat buffer per plug should remove roughly half that pass.

## Verification

* parity: **pass**
* skinCluster needs a bound rig (wired joints + painted weights); generic point-compare skipped -- see tools/harness/skin_*_parity.py | authored @maya_test: 1/1 passed

## Files

```
build/stages/twistSwingSkin/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/twistSwingSkin/3_optimized/00_baseline.cpp
build/stages/twistSwingSkin/3_optimized/01_direct_fill_reused_buffers.cpp
build/stages/twistSwingSkin/3_optimized/02_cache_weight_arrays.cpp
build/source/twistSwingSkin.cpp      SHIPPED
```
