# mPyBlendShape

A scriptable blendShape: an `MPxDeformerNode` (API 1.0) that carries a flat stack of targets, aliased per-target weights that read like a stock blendShape in the Channel Box, and baked sparse delta tables the expression blends however it likes. In-betweens, combos and corrective rules live in your Init tab, in plain Python, instead of inside a resolver you cannot see.

## Specific to this node

* The deformer surface is the same as `mPyDeformer`: read, mutate and commit through `self.outputGeometry[i]`, with `envelope` inherited.
* Targets connect into `targetGeometry[j]` and each `weight[j]` is aliased to the target name, so `bs.browUp` is `bs.weight[0]` and animates like any blendShape channel.
* The compute reads baked deltas, not the target meshes. `rebuild()` derives compressed sparse row tables (`targetOffset`, `targetComponents`, `targetDeltas`) from what is connected, which is what makes the deform survive a deleted target and what lets it compile.
* Live targets stay live. With `liveTargets` on, a connected non-zero-weight target is read straight off its mesh, so sculpting a target moves the shape as you drag; the deform itself never writes a plug.
* Target names declare the rig: `browUp` is a main target, `browUp50` an in-between peaking at 0.5, `browUp_mouthOpen` a combo. `rebuild()` decodes them into the `interBase`, `interKnot`, `comboOffset` and `comboDriver` tables; how they are weighted is your code.
* Deliberately not an `MPxBlendShape`. That base never calls `deform()`, owns the `weight` name, and falls outside the C++ codegen.

## In the Compute tab

* Reads: `self.outputGeometry[i]`, `self.input[i].inputGeometry`, `self.envelope`, `self.weight[j]`, `self.targetGeometry[j]` (literal index only, and it blocks the compile), plus every input you add.
* Write: `self.outputGeometry[i].setPoints(arr)`.
* `self.morphs`, the target stack as one object and the surface the templates use:
  * `self.morphs.apply(base)` or `.apply(base, envelope)`: the whole deform in one call.
  * `self.morphs.weights` (raw channels) and `self.morphs.resolved` (after in-between and combo resolution), both `(T,)`.
  * `self.morphs.deltas(base)` or `.deltas(base, w)`: the offset field for the weights you built.
  * `self.morphs[i].weight`, `self.morphs["browUp"].weight`, `len(self.morphs)`. A name key is folded to a slot at compile time, so it must be a provable constant.
* At compile time the object is erased into the blessed methods `morph_apply`, `morph_weights`, `morph_deltas`, `blend_targets` and `morph_weight_at`, which transpile the same numpy kernel the interpreted node runs. No target name reaches the C++, so one bundle serves any rig.

## Creating one

* `MPyBlendShape.create(mesh, targets, name)` attaches the deformer and wires and aliases each target; `add_target(mesh, name)`, `rename_target`, `remove_target`, `set_weight` and `get_weight` edit the stack afterwards.
* `rebuild()` after any target change; `resync_targets()` freezes a live sculpt into the tables; `load_target` and `load_shapes` read targets from disk.
* Off the wrapper `bs.morphs` also carries names: `bs.morphs["browUp"]`, `.find("brow")`, `.names`, `.dense(nv)`, and `Morph` arithmetic that unions sparse index sets.
* The shipped template, Combo Correctives, ships the in-between hat and combo rules spelled out in its Init tab.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
