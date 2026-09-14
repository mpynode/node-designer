# mPyMesh

A polygon generator: a plain `MPxNode` (API 2.0) that outputs mesh data on `outMesh`, the same pattern as `polyCube` and `polySplit`. It is a dependency-graph node, not a shape, so it has no transform of its own; connect `outMesh` to a `mesh` shape's `inMesh` to see the result. Procedural geometry, mesh readers and caches, cellular automata, isosurfaces and UV layouts all fit here.

## Specific to this node

* Three required writes make a mesh: `self.points` `(N, 3)`, `self.counts` `(F,)` with every face at least 3, and `self.indices`, the flat face-vertex stream whose length equals `sum(counts)`.
* Optional channels: `self.normals` and `self.colors`, each per vertex, or per face-vertex when the matching `normal_indices` / `color_indices` map is set. Colors may be RGB or RGBA.
* Typed output: `self.outMesh = Mesh(points=..., counts=..., indices=...)` from `mpynode._api2.geometry` bypasses the flat buffers, and any object exposing those three attributes is accepted. A finished `kMeshData` object is used as is.
* Validation fails soft: a bad face count, an out-of-range index or a mismatched stream logs the reason and ships an empty mesh instead of crashing.
* Time is opt-in: connect `time1.outTime` to `_timeIn` and the mesh re-evaluates every frame; static meshes evaluate once.

## In the Compute tab

* `self.time` as a `TimeFloat`, the seven write slots above, and every input you add.
* A `mesh` input arrives as a `Mesh` object: `.points`, `.counts`, `.indices`, `.normals`, `.uv_sets`, `.component_tags`, `.region(tag)`, `.from_faces` / `.from_vertices` / `.from_tag`, `.copy()`, and arithmetic (`+` unions two meshes, `-` removes overlapping faces, `+ morph` applies an offset field, `* 2.0` scales the points). Any `MFnMesh` method works on it directly.

## Creating one

* `MPyMesh.create(name)`, then `set_compute_expression(...)` and wire `outMesh` into a mesh shape.
* Seven shipped templates range from a Game of Life grid to metaballs, voxelization, a disk mesh cache and a UV layout.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
