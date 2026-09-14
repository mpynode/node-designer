# mPyConstraint

A scriptable constraint: an `MPxNode` (API 2.0) carrying five preset, constraint-style inputs, with the solve written by you and published through outputs you declare. It is deliberately not an `MPxConstraint`, which hijacks `compute()` for its own plugs; here the plumbing is the ordinary compute path, and the node still reads as a constraint in the Channel Box.

## Specific to this node

* Five preset inputs, always present: `targetTranslate`, `targetRotate`, `targetWeight` (default `1.0`), `restTranslate`, `restRotate`. The vectors read as `(3,)` numpy, the weight as a float.
* `targetRotate` and `restRotate` are plain doubles. Connected from a transform's `.rotate` they carry Maya's internal angular unit, radians; convert with `np.degrees` if you need degrees.
* Any change to a preset, or to one of its X, Y, Z children, dirties every user output, so the driven side updates as soon as the driver moves. User-added inputs follow the regular `mPyNode` rules.
* You add the outputs. A typical setup wires a driver into the presets, computes the constrained value in Compute, and connects a vector output into the driven transform.
* During a file read the compute defers until the scene is whole, so the Evaluation Manager cannot pull an output before the node's attributes are restored.

## In the Compute tab

* `self.targetTranslate`, `self.targetRotate`, `self.targetWeight`, `self.restTranslate`, `self.restRotate`, plus every input you add.
* `self.<output> = value` for each declared output.
* A `mesh` input arrives as a `Mesh` object with its component tags, which is what the shipped Procrustes Tags template rivets to.

## Creating one

* `MPyConstraint.create(name)`, then `add_output_attr(...)` and `set_compute_expression(...)`.
* `list_preset_inputs()` returns the five preset plug names.
* The shipped template, Procrustes Tags, rivets a transform to tagged regions of a deforming mesh.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
