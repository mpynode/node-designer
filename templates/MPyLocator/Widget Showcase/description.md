# Widget Showcase

A reference `mPyLocator` that draws one of everything the locator renderer supports: **lines** (a 3-axis gizmo and a diamond), **points** (a rainbow grid), **polygons** (a per-face-coloured cube with a wireframe overlay), **shapes** (sphere, box, cone, cylinder, circle) and **text** labels.

The `preset` enum picks what draws: `everything` (the default) shows all five side by side, or pick a single slot. Behind it is a persistent `presets` dict variable, so you can edit which slots each preset turns on.

Nothing animates -- the cheapest locator to leave in a scene. **Create + Run demo** bakes the preset dict and frames it.
