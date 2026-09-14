# mPyNurbsSurface

A NURBS-surface generator: a plain `MPxNode` (API 2.0) that outputs surface data on `outSurface`, the shape `loft` and `revolve` produce. Connect `outSurface` to a `nurbsSurface` shape's `create` plug to render it. Ribbons, procedural patches and anything described by a grid of CVs.

## Specific to this node

* Write `self.cvs` as a `(nu, nv, 3)` grid, U-major, and the bridge derives the counts; a flat `(nu*nv, 3)` array needs `self.num_cvs_u` and `self.num_cvs_v`.
* Per direction: `self.degree_u` / `self.degree_v` (1, 2, 3, 5 or 7, default 3), `self.form_u` / `self.form_v` (`open`, `closed` or `periodic`) and optional `self.knots_u` / `self.knots_v`, rebuilt uniform when absent or mis-sized.
* Typed output: `self.outSurface = NurbsSurface(points=grid, degree_u=3, degree_v=3, periodic_u=False, periodic_v=False)` from `mpynode._api2.geometry`, or any object exposing `.points`.
* Fewer than `degree + 1` CVs in either direction ships an empty surface and logs why.
* Time is opt-in through `_timeIn` or a `time` input.

## In the Compute tab

* `self.time`, the write slots above, and every input you add.
* A `nurbsSurface` input arrives as a `NurbsSurface` object: `.points` as a `(nu, nv, 3)` grid, `.num_u`, `.num_v`, `.degree_u`, `.degree_v`, `.form_u`, `.form_v`, `.knots_u`, `.knots_v`, `.component_tags` with `(u, v)` CV indices, `.region(tag)` and `.copy()`. `MFnNurbsSurface` methods work on it directly.

## Creating one

* `MPyNurbsSurface.create(name)`, then `set_compute_expression(...)` and wire `outSurface` into a surface shape.
* The shipped template, NURBS Ripple, animates a wave across a patch.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
