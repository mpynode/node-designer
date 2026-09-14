# mPyDeformer

The canonical deformer: an `MPxDeformerNode` (API 1.0) whose `deform()` runs your Python on a writable copy of the input geometry. Polygon meshes, NURBS curves, NURBS surfaces and lattices all pass through it, and `envelope` comes for free from Maya's deformer base. `mPySkinCluster` and `mPyBlendShape` share this surface and add their own.

## Specific to this node

* Read, mutate, commit. `self.outputGeometry[i]` is a writable handle eager-copied from the input before the expression runs; whatever you `setPoints` on it is committed when compute ends. An empty expression is therefore an identity deformer.
* The handle is numpy-friendly: `getPoints()` returns `(N, 3)` float64, `setPoints(arr)` writes it back, and `.points`, `.counts`, `.indices`, `.region(tag)` and `.copy()` mirror the geometry wrapper's read surface. NURBS use `cvPositions()` and `setCVPositions()`.
* `self.input[i].inputGeometry` is the read-only upstream source and `self.envelope` the inherited envelope.
* `node.X = value` writes go through the datablock during compute: `node.outputGeometry[0] = arr` commits a mesh in one shot, `node.envelope = 0.5` sets a plug.
* Safe failure. An expression error returns the input unchanged; a commit whose vertex count no longer matches the input is skipped with a warning. A broken expression never crashes Maya, it shows the rest pose.
* Re-evaluates when a user input changes, when a connected driver moves, and on every frame.

## In the Compute tab

* `self.outputGeometry[i]`, `self.input[i].inputGeometry`, `self.envelope`, plus every input you add: a `matrix` input for a driver, a `mesh` input for a collider, scalars for falloff and amplitude.
* Component tags on the incoming geometry are readable through the handle's `region(tag)`.

## Creating one

* `MPyDeformer.create_on(mesh, name)` creates and attaches in one call, the equivalent of `mc.deformer(mesh, type="mPyDeformer")`. `MPyDeformer.create(name)` makes an unattached node.
* Five shipped templates cover a sine ripple, a NURBS wave, patch relaxation, an RBF wrap and unit-sphere collision.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
