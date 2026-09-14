# mPyIkSolver

A custom IK solver: an `MPxIkSolverNode` (API 1.0) whose `doSolve` runs your Python. Assign it to a standard `ikHandle` and the expression receives the joint chain, the handle, the pole vector and the twist, then publishes a desired matrix per joint. Look-at solvers, two-bone or N-bone chains with unusual math, springy or elastic behaviour, and procedural rigs where the stock solvers do not fit.

## Specific to this node

* One solver instance serves the scene. `MPyIkSolver.find_solver()` returns it, creating it if needed, and `mc.ikHandle(solver="mPyIkSolver")` requires that instance to exist first.
* The solve writes only each joint's `offsetParentMatrix`. The joints' own channels and `jointOrient` are never touched, so rotate-only solves reorient in place and preserve bone lengths.
* Per joint the dispatch is world over local over rest: a slot left `None` in both lists leaves that joint at its rest offset.
* There are no Euler outputs by design; a full matrix avoids the degrees versus radians trap. There are no DG user outputs either; the result is the solve itself.
* Only the first IK handle in the solver's group is processed.

## In the Compute tab

* `self.joints`: one dict per joint with `name`, `world_position`, `rotation`, `matrix` (local rest frame) and `world_matrix` (rest world frame); the two matrices are `MatrixView` objects, stable across solves.
* `self.end_effector`: the IK handle's world position, the goal. `self.pole_vector` and `self.twist` from the handle.
* `MatrixView` is available as a builder: `setRotation`, `setTranslation`, `setScale`, `rotateBy`, chainable and numpy-transparent, rotations in radians.
* Writes: `self.local_matrices[i]` or `self.world_matrices[i]` (4x4 or `None`, one slot per joint) and the gates `apply_rotate` (default `True`), `apply_translate` and `apply_scale` (default `False`), each a bool or a per-joint list.

## Creating one

* `MPyIkSolver.find_solver()` or `MPyIkSolver.create(name)`, then `set_compute_expression(...)`; `rebind()` re-attaches the solver to its handles after edits.
* The shipped template, Two Bone IK, solves a three-joint chain analytically and bends toward the pole vector.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
