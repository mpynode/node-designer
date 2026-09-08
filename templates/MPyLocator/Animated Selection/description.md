# Animated Selection

A shaded cube (`mPyLocator`) that spins on the timeline and pops out under the mouse. Hover is a real ray-versus-triangle test rather than a bounding box, and the pop runs off the wall clock, so it plays on any redraw. Selecting the cube tints the fill only.

## Inputs

* `color_mode` -- how the cube is filled. `face` gives flat per-face hues, `vertex` a gradient across the corners, `face_vertex` smooth inside each face with hard seams between, `uniform` one translucent colour.
* `show_wireframe` -- adds an edge overlay on top of the fill.
* `wire_width` -- how thick that overlay is.
* `spinSpeed` -- rotation per frame. 0 stops it.
* `popDuration` -- how long the hover pop takes.
* `popAmount` -- how far the cube pops out when hovered.

## Outputs

* The viewport drawing. Nothing is connected onward -- this is a gizmo, not a value.

## Create + Run demo

Sets a playback range and frames it.
