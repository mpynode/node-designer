# mPyLocator

A viewport-drawn locator: an `MPxLocatorNode` (API 2.0) paired with an `MPxDrawOverride`. The Compute tab is drawing code. It assigns `self.draw`, and the override replays that drawing every frame through Maya's `MUIDrawManager`. It sits in the DAG like any locator, can be parented, selected and hovered, and the compiled C++ node replays the identical command list.

## Specific to this node

* Compute produces a drawing, not plug values. `self.draw` takes one item, a `+` chain, or a list nested as deeply as you like; `None` entries are skipped and `self.draw = None` draws nothing.
* Authoring order is draw order. Whatever you write last draws on top; items are never re-bucketed by type.
* User inputs work and feed the drawing. User outputs never compute: `MPxLocatorNode` does not dispatch `compute()` for runtime output plugs, so for output math chain a downstream `mPyNode`.
* Selection and hover are first-class: the drawing is tinted with Maya's selection colour when selected, and a cursor-ray tracker reports hover per locator.

## Draw types

All live in `mpynode._common.draw.draw_types` and a fresh Init tab imports them for you. Every item takes `color` and `space`; `space="screen"` gives constant pixel size and billboarded text.

* `DrawSphere`, `DrawBox`, `DrawCone`, `DrawCylinder`, `DrawCircle`: Maya's built-in primitives. `center`, `radius`, `axis`, `filled`; scalars broadcast, so one call can draw many. `DrawCircle` faces +Z by default.
* `DrawMesh(points, counts, indices)` or `DrawMesh(mesh)`: a polygon patch. Fill with `color` (flat per face), `uniform_color`, `vertex_colors` or `face_vertex_colors`; overlay edges with `outline`, `outline_width`, `outline_boundary_only`; plus `world_space`, `cull_backfaces`, `precise_hover`, `highlight_fill`, `highlight_wire`.
* `DrawCurve(points, closed=False)`: a polyline through the points, the segment split done for you.
* `DrawLines(starts, ends)`: explicit segment pairs.
* `DrawPoints(positions, size=4.0)`: point sprites, `size` in pixels.
* `DrawText(text, position, size)`: one string or a list of labels.
* `DrawGroup`: what `+` returns.

## In the Compute tab

* Reads: `self.time` (a `TimeFloat`; reading it opts the drawing into the timeline), `self.wallclock` (seconds since the epoch, a timeline-independent clock), `self.selected`, `self.is_lead`, `self.hovered`, `self.selection_color`.
* Writes: `self.draw`, plus the toggles `self.auto_highlight` (selection tint on or off), `self.auto_refresh` (a 30 fps redraw timer for animation without a time plug) and `self.precise_hover` (ray against the drawn triangles instead of the bounding box; also per patch through `DrawMesh(..., precise_hover=True)`).
* Every input you add, read as `self.<name>`.

## Creating one

* `MPyLocator.create(name)` creates the shape and Maya adds the parent transform; `get_transform()` returns it.
* `evaluate_draw_commands(time_value)` runs the expression headless and returns the ordered command list, handy for tests without a viewport.
* Five shipped templates: an animated selection gizmo, animated text, text written around a ring, tagged mesh regions and a widget showcase.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
