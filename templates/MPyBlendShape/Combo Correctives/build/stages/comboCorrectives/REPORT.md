# comboCorrectives -- compile report

**Source node:** `comboCorrectives`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-09 14:36

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **414.56x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# Corrective blendShape: in-betweens and combos, resolved from tables.
#
# The naming convention lives in the ALIASES, and it is decoded ONCE, in Python,
# by MPyBlendShape.rebuild() -- never here:
#
#     browUp                a main target, driven by its own weight
#     browUp50              an IN-BETWEEN of browUp, peaking at 0.50
#     browUp_mouthOpen      a COMBO, active when both drivers are up
#
# Names cannot be read in a compute at all. Alias lookup is a side-channel DG
# query, and those return EMPTY on the Evaluation-Manager worker thread that
# deform() runs on -- so it would be unreliable interpreted and impossible
# compiled. What crosses into the compute is pure number:
#
#     interBase[t]    the main target an in-between corrects, else -1
#     interKnot[t]    where it peaks (0.5 for browUp50)
#     comboOffset[t] .. comboOffset[t+1]   slice of comboDriver for target t
#     comboDriver[j]  a driver target index
#
# Every target stores its RAW `sculpt - base` offsets. A corrective is sculpted
# as the correction ITSELF -- what to add once its drivers are already posed --
# so there is nothing to subtract at bake time. That is also why dialling one by
# hand shows exactly the shape it was sculpted as.
#
# The rules live in the INIT tab as three ordinary functions --
# `inbetween_hat`, `combo_blend`, `resolve_morph_weights` -- so the
# maths is right there to read and change. There is no shared weight resolver
# behind them: whatever maths a rig wants lives in ITS Init and Compute, in
# the open. Init transpiles with the Compute, so an edited rule compiles too.
#
# Correctives are ADDITIVE here: a corrective keeps whatever is keyed on its own
# channel and the driven amount is added on top. `applyCorrectives` and
# `applyCombos` switch the driven half off without unhooking anything, so you can
# key the drivers and watch each contribution on its own.

# Construction history is automatic: `self.morphs.deltas` reads a target's
# offsets straight off its CONNECTED mesh, so sculpting one reaches the deform
# as you drag. A target with no connection falls back to its baked deltas, which
# is what makes deleting a target leave the shape driving. Switch `liveTargets`
# off to pin the deform to the baked tables. Compiled nodes follow their targets
# too -- they read every CONNECTED one, where interpreted skips the slots that
# resolve to zero weight, so the result matches and only the cost differs.

mesh = self.outputGeometry[0]
base = mesh.getPoints()

w = resolve_morph_weights(self.weight, self.interBase, self.interKnot,
                          self.comboOffset, self.comboDriver,
                          self.applyCorrectives, self.applyCombos)

mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 90 / array length 2000; noise floor 15 ms; moved per tick: `applyCombos (bool)`, `weight[0] (float)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`; outputs checked (1 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there.

Baseline **144.060 ms** -> best **0.347 ms** (**414.56x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 144.060 ms | -- | -- |
| 01 | `raw_pointer_scatter` | the delta scatter built three nd::Array temporaries per component per row (slice + add + item), so lower the whole deform to raw pointers with the same expression and visit order; then cache the two table-derived structures (per-vertex gather index, per-target combo products) across ticks | 10.00x | 414.56x | 19.3 min | ACCEPTED |
| 02 | `thread_fused_gather` | fuse the per-vertex baked-delta gather into the output write and run that one map on a persistent per-node pool; the gather table holds ~170k (target,row) entries at the bench size because random slices overlap, so it was ~100 us of a ~235 us deform, not the 666 entries the row count suggests | 1.45x | 0.312 ms | 25.0 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `raw_pointer_scatter` -- predicted 10.00x, measured **414.56x**. at 2000 targets x 2000 rows the node is ELEMENTWISE over the tables, not over the mesh: ~670k scatter iterations each paying two heap allocations dwarf the 8k-vertex mesh work, so removing the allocations should take the node from 144 ms to the low tens of ms; what remains is the serial combo product chain (~670k dependent multiplies) and the random-write scatter, both derived from tables that HOLD between ticks except for the drivers whose weight moved
* `thread_fused_gather` -- predicted 1.45x, **rejected: not faster**. incumbent under 2 ms: second measurement 0.312 ms did not confirm 0.292 ms

### Rejected rounds

* `thread_fused_gather` -- rejected: not faster. incumbent under 2 ms: second measurement 0.312 ms did not confirm 0.292 ms

## Verification

* parity: **pass**
* verify could not run: Unable to create/find dependency node. | authored @maya_test: 2/2 passed

## Files

```
build/stages/comboCorrectives/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/comboCorrectives/3_optimized/00_baseline.cpp
build/stages/comboCorrectives/3_optimized/01_raw_pointer_scatter.cpp
build/stages/comboCorrectives/3_optimized/02_thread_fused_gather.cpp
build/source/comboCorrectives.cpp      SHIPPED
```
