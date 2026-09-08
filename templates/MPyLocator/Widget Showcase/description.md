# Widget Showcase

A reference `mPyLocator` that draws one of everything the locator renderer supports: **lines** (a three-axis gizmo and a diamond), **points** (a rainbow grid), **polygons** (a per-face-coloured cube with a wireframe overlay), **shapes** (sphere, box, cone, cylinder, circle) and **text** labels.

Use it to see what is available before writing your own gizmo. Nothing animates, which makes it the cheapest locator to leave in a scene.

## Inputs

* `preset` -- which group draws. `everything` (the default) shows all five side by side, or pick a single one. Behind it is a `presets` variable holding which groups each preset turns on, so you can edit the combinations.

## Outputs

* The viewport drawing. Nothing is connected onward -- this is a gizmo, not a value.

## Create + Run demo

Bakes the preset variable and frames it.
