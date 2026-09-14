# mPyTransform

An expression-driven transform: an `MPxTransform` paired with its own `MPxTransformationMatrix` (API 1.0, registered with `registerTransform`). The expression reads the node's own channels and any inputs you add, and publishes a desired local matrix; the node applies it, and children ride along. Aim setups, matrix-driven placement, custom decompositions and rig helpers at the transform level.

## Specific to this node

* The result travels through `offsetParentMatrix`. A stock `fourByFourMatrix` relay is auto-wired per node, so the world matrix and every descendant update natively in DG, Evaluation Manager and Cached Playback with no manual flush.
* Once `self.local_matrix` is set, the driven channels are cancelled: `translate`, `rotate` and `scale` still change in the Channel Box and remain readable as inputs, but the node stays where the expression puts it. Close a gate (`self.apply_rotate = False`) to leave that channel live.
* The node never reads its own DAG parent. For world placement, connect the parent's `worldMatrix` to a matrix input and set `self.local_matrix = wanted @ inv(parent)`, which stays cycle-free and DG-tracked.
* Matrices are row-major with translation in row 3, matching Maya's `MMatrix`.
* Time is opt-in: connect `time1.outTime` to `_timeIn`, or add a `time` input.
* An expression error leaves the node a plain transform.

## In the Compute tab

* Reads: `self.translate`, `self.rotate` (radians), `self.scale`, `self.shear` (each `(3,)` numpy) and `self.rotate_order` (0 to 5), plus every input you add, typically `matrix` inputs read with `.asNumpy()`.
* Writes: `self.local_matrix` (4x4 or `None`) and the gates `self.apply_rotate`, `self.apply_translate`, `self.apply_scale`, all default `True`.

## Creating one

* `MPyTransform.create(name)`, then `add_input_attr(...)` and `set_compute_expression(...)`; parent anything under it.
* The shipped template, Aim Between Matrices, parks the node at the midpoint of two matrices and aims along their segment.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
