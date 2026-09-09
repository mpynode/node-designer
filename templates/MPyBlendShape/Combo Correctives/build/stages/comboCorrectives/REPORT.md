# comboCorrectives -- compile report

**Source node:** `comboCorrectives`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-09-08 23:23

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **258.02x** over 2 round(s) -- re-measured: **183.26x** (outputs match) |

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
# off to pin the deform to the baked tables. Compiled nodes are baked-only.

mesh = self.outputGeometry[0]
base = mesh.getPoints()

w = resolve_morph_weights(self.weight, self.interBase, self.interKnot,
                          self.comboOffset, self.comboDriver,
                          self.applyCorrectives, self.applyCombos)

mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **73.665 ms** -> best **0.285 ms** (**258.02x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 90 / array length 2000: baseline 139.993 ms -> shipped 0.764 ms (**183.26x**); outputs match. The speedup above was taken before the gate existed; this is the number to quote. Moved per tick: `applyCombos (bool)`, `weight[0] (float)`, `input[0].inputGeometry <- pSphereShape1Orig.vtx[0]`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 73.665 ms | -- | -- |
| 01 | `raw_scatter_deltas` | the delta accumulator was heap-allocating three nd::Array temporaries per vertex-component; a raw-pointer scatter plus a per-main sorted knot index for the in-between rescan took the node from 73.7 ms to 0.35 ms | 15.00x | 227.50x | 14.3 min | ACCEPTED |
| 02 | `compact_slot_scatter_cache` | cache the targetOffset/targetComponents-derived scatter topology per instance, accumulate into a compact 576-slot buffer instead of a 24k-double per-vertex array, and touch only the vertices a delta row actually names | 1.35x | 258.02x | 12.2 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `raw_scatter_deltas` -- predicted 15.00x, measured **227.50x**. accumulate_deltas spelled every += as nd::add(nd::slice(out,{Sl::at(b)}), s).item(), which builds a shared_ptr-backed Array view AND an allocated result Array for each of the three components of each of ~178k (target, component) pairs -- roughly a million allocations per evaluation, so the arithmetic is invisible next to malloc. Replacing it with out[b] = out[b] + wt*dlt[d] keeps the exact operand order and the exact double add, so it is bit-identical. Secondarily, inbetween_hat rescans all 2000 ibase entries for every one of 2000 targets (4M iterations); its lo/hi are an order-independent max/min over the knots sharing a main, so a per-main sorted knot list plus lower_bound/upper_bound selects the identical doubles in O(log n).
* `compact_slot_scatter_cache` -- predicted 1.35x, measured **258.02x**. in-file profiling showed the baked scatter was 0.147 ms of a 0.275 ms compute; only 576 of 8012 vertices are ever written, so the 192 KB zero-init, the 24k-double rest-point snapshot and the 8012-vertex rewrite are all pure overhead, and the clamped per-target [lo,hi) plus the per-row vertex id are derived state that never moves while the weights animate

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.001)
* authored @maya_test: 2/2 passed

## Files

```
build/stages/comboCorrectives/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/comboCorrectives/3_optimized/00_baseline.cpp
build/stages/comboCorrectives/3_optimized/01_raw_scatter_deltas.cpp
build/stages/comboCorrectives/3_optimized/02_compact_slot_scatter_cache.cpp
build/source/comboCorrectives.cpp      SHIPPED
```
