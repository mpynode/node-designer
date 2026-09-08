# Combo + In-Between Correctives

An aliased `mPyBlendShape` with the two corrective shapes every face rig needs. The `weight` multi is aliased to your target names, so the channel box shows `jawDrop` rather than `weight[0]`.

You declare correctives in the target NAME -- there is nothing else to set up:

* `jawDrop` -- a main target on its own weight.
* `jawDrop75` -- an in-between of `jawDrop`, peaking when the driver reaches 0.75.
* `cheekPuffL_jawDrop` -- a combo, which only comes in as both drivers rise.

In-betweens hand off to each other rather than all firing at once, so `jawDrop25`, `jawDrop50` and `jawDrop75` each peak on their own knot and fall away at their neighbours'. A lone in-between still covers the driver's whole travel.

Sculpt a corrective as the correction ITSELF -- what to add once its drivers are posed. Nothing is subtracted at bake time, so dialling `jawDrop75` to 1 on its own gives exactly the shape that was sculpted.

Correctives are additive: whatever you key on a corrective's own channel is kept, and the derived amount is added on top. So a combo can be animated by hand as well as driven.

## Inputs

* `weight` -- one entry per target, aliased to the target's name. This is what you animate.
* `applyCorrectives` -- switch the derived in-between amounts off without unhooking anything. Useful for seeing what that layer contributes.
* `applyCombos` -- the same switch for combos.
* `targetOffset` / `targetComponents` / `targetDeltas` -- the baked shape data. Written by the commands below; not for hand editing.
* `shapeSlot` / `interBase` / `interKnot` / `comboOffset` / `comboDriver` -- the decoded naming tables that say which target is a main, an in-between or a combo. Also written by the commands.
* `envelope` -- the standard deformer blend against the undeformed input.

## Outputs

* The deformed mesh, written back through the deformer chain, with mains, in-betweens and combos summed.

## Commands

* `add_targets` -- adds meshes as targets, each weight aliased after its mesh. Defaults to the current selection, which is the usual way to use it: pick the shapes, then run.
* `load_target_cmd` -- loads ONE shape from a file and adds it as a target. Handles `.ma`, `.mb`, `.obj`, `.fbx`, `.npz` and `.json`, and needs no mesh in the scene.
* `load_shapes_cmd` -- loads a whole shape cluster from a `.npz` or `.json`, one target per record, each aliased to its stored name. Reports how many names decoded as in-betweens or combos.

## Create + Run demo

Builds a real face: a 1306-vertex head with all 167 authored targets -- 52 mains, 31 in-betweens and 84 combos -- driven by 381 frames of performance capture on the 52 mains and nothing else. Press play, and every in-between and combo you see fire is derived on that frame rather than keyed. Scrub `jawDrop` to watch the 0.25, 0.50 and 0.75 corrections hand off one at a time, then raise `cheekPuffL` alongside it to fade the `cheekPuffL_jawDrop` combo in. The targets sit hidden in a grid behind the head.
