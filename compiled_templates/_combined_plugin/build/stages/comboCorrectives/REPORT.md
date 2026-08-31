# comboCorrectives -- compile report

**Source node:** `comboCorrectives`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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

mesh = self.outputGeometry[0]
base = mesh.getPoints()

w = resolve_morph_weights(self.weight, self.interBase, self.interKnot,
                          self.comboOffset, self.comboDriver,
                          self.applyCorrectives, self.applyCombos)

mesh.setPoints(base + self.envelope * self.morphs.deltas(base, w))
```

## Files

```
build/stages/comboCorrectives/1_transpiled.cpp     deterministic transpile (no AI)
build/source/comboCorrectives.cpp      SHIPPED
```
