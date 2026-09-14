# mPyNurbsCurve

A NURBS-curve generator: a plain `MPxNode` (API 2.0) that outputs curve data on `outCurve`, like Maya's own `circle` and `rebuildCurve` nodes. Connect `outCurve` to a `nurbsCurve` shape's `create` plug to render it. Helices, procedural paths, guide curves and anything built from CV positions.

## Specific to this node

* Write `self.cvs` `(N, 3)`, optionally `self.degree` (1, 2, 3, 5 or 7, default 3), `self.form` (`open`, `closed` or `periodic`) and `self.knots`. Knots default to a uniform vector, and a vector of the wrong length is rebuilt uniform.
* Typed output: `self.outCurve = NurbsCurve(points=..., degree=3, periodic=False, kv=None)` from `mpynode._api2.geometry`; a duck-typed object with `.points` works too.
* Periodic curves follow Maya's storage: supply CVs that already wrap (the last `degree` CVs repeat the first ones) and the knot count is `numCVs + degree - 1`.
* A curve with fewer than `degree + 1` CVs, or invalid data, ships an empty curve and logs why.
* Time is opt-in through `_timeIn` or a `time` input.

## In the Compute tab

* `self.time`, the write slots above, and every input you add.
* A `nurbsCurve` input arrives as a `NurbsCurve` object: `.points` (alias `.cvs`), `.degree`, `.form`, `.periodic`, `.knots`, `.component_tags`, `.region(tag)`, `.copy()`, and `+` to concatenate two curves of the same degree and form into one.
* Any `MFnNurbsCurve` method still works on the input object, `curve.length()` for example.

## Creating one

* `MPyNurbsCurve.create(name)`, then `set_compute_expression(...)` and wire `outCurve` into a curve shape.
* The shipped template, NURBS Helix, builds a parametric helix.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
