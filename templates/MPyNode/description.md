# mPyNode

The general-purpose node. A plain `MPxNode` (API 2.0) whose `compute()` runs the Python stored on the node itself: declare inputs and outputs at runtime, read them as `self.<input>`, assign `self.<output>`, and Maya's dependency graph carries the result. It is the base every other mPy type inherits from, and the right pick for matrix and vector math, custom interpolation, procedural logic, and anything you would otherwise write as an `expression` but want as a real node.

## Specific to this node

* No preset plugs. Every input and output is one you add, so the node's interface is exactly what you declare.
* Any input may feed any output, so a change to any input dirties every output. The framework declares that dependency for you, so it holds under the Evaluation Manager too.
* Outputs are pre-seeded on `self` before the expression runs: scalars at their default, matrices at identity, array outputs as a pre-sized `(N, ...)` buffer you can slice-assign in place.
* Geometry flows through a plain node too. A `mesh`, `nurbsCurve` or `nurbsSurface` attribute reads as a `Mesh`, `NurbsCurve` or `NurbsSurface` object and accepts one on output, single or array.

## In the Compute tab

* `self.<input>` for each declared input. Scalars are Python primitives, vectors and arrays are numpy, a matrix is a numpy-transparent `MatrixView` with `.asNumpy()`, `.translation()`, `.rotation()` and the rest of the `MTransformationMatrix` surface.
* `self.<output> = value` is the only write that reaches a plug. Any other `self.x = ...` becomes a stored variable.
* No module is injected. Import `numpy`, `math` or `maya.cmds` in the expression or in Init.
* A `time` input auto-connects to `time1.outTime` and reads as a `TimeFloat` with `.fps` and `.asSeconds()`.

## Creating one

* `MPyNode.create(name)` for a bare node, `MPyNode.build(name, setup=True)` to also seed and run its `setup()`, `MPyNode("existing")` or `wrap_node("existing")` to wrap a node already in the scene.
* `add_input_attr(name, attr_type, ...)` and `add_output_attr(name, attr_type, ...)`, then `set_compute_expression(source)`.
* Eight shipped templates, from a bubble sort and a spring chain to a spline solver and the DNET rig.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
