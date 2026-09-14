# mPySkinCluster

A scriptable skinCluster: an `MPxSkinCluster` (API 1.0) registered under `kSkinCluster`, so Maya treats it as a genuine skinCluster. The Component Editor, Paint Skin Weights and `skinPercent` all read and write its weights, and the skinning formula itself is Python in the Compute tab. Linear blend, dual quaternion, twist and swing, or a blend you invent, on a node Maya's own tools recognise.

## Specific to this node

* Real skinCluster lineage. `hasFn(kSkinClusterFilter)` is true, `mc.skinCluster -q -inf` lists the influences, and the standard `matrix[]`, `bindPreMatrix[]` and `weightList[]` plugs are provided by the base class.
* `weightList[v].weights[j]` is the live source of truth. Painting or editing a weight re-evaluates the deform natively, so the paint tools and the expression stay in step.
* The deformer surface is the same as `mPyDeformer`: read, mutate and commit through `self.outputGeometry[i]`, with `envelope` inherited.
* One caveat: `MFnSkinCluster.getWeights()` returns zeros for a Python subclass. Read the plug, or use `skinPercent`, when your own code needs the weights.
* The `mc.skinCluster` bind command cannot create a custom skinCluster, so the wrapper does the joint wiring and bind-pose seeding itself.
* An expression error leaves the mesh unchanged. A commit whose vertex count does not match is skipped with a warning.

## In the Compute tab

* Reads: `self.outputGeometry[i]`, `self.input[i].inputGeometry`, `self.envelope`, `self.matrix[j]` (joint world matrix, a `MatrixView`), `self.bindPreMatrix[j]` (bind-pose inverse), `self.weightList[i].weights` (sparse per-vertex weights; the blessed methods take it as is), plus every input you add.
* Write: `self.outputGeometry[i].setPoints(arr)`.
* Blessed skinning methods, each returning `(N, 3)` points with the envelope left to you:
  * `linear_blend(rest, weights, joint, bind)`: classic linear blend skinning.
  * `dual_quaternion(rest, weights, joint, bind)`: volume-preserving under bends.
  * `twist_swing(rest, weights, joint, bind, twist_axis)`: dual quaternion for the twist about a bone-local axis (0 = X, 1 = Y, 2 = Z), linear blend for the swing.
  * `twist_swing_dual(rest, twist_weights, swing_weights, joint, bind, twist_axis)`: the same with separately painted twist and swing weight sets.
  * `update_weights(weights)`: push a dense `(N, J)` array into `weightList` so the paint tools show it. `sync_paint(mode)`: load a weight set into the paint scratchpad and bank the painted result back. Both are interactive-only side effects and lower to nothing in a compiled node.
* All of these transpile, so a skin written this way compiles to C++ unchanged.

## Creating one

* `MPySkinCluster.create(mesh, joints, name)` attaches the deformer, connects each joint `worldMatrix[0]` into `matrix[i]` and seeds `bindPreMatrix[i]` from the current pose.
* `set_vertex_weight(vertex, joint, weight)` writes one `weightList` entry; `skinPercent` and the paint tools take over from there.
* Three shipped templates: Linear Blend Skin, Dual Quaternion Skin and Twist Swing Skin.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
