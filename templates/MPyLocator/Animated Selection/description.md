# Animated Selection

A shaded cube (`mPyLocator`) that spins on the timeline and pops out under the mouse. Hover is a real ray-versus-triangle test, not a bounding box, and the pop runs off the wall clock, so it plays on any redraw.

`color_mode` sets the fill: `face` (flat per-face hues), `vertex` (a gradient across the corners), `face_vertex` (smooth inside a face, hard seams between) or `uniform` (one translucent colour). `show_wireframe` and `wire_width` add an edge overlay. `spinSpeed` (radians per frame), `popDuration` and `popAmount` tune the motion. Selecting the cube tints the fill only.

**Create + Run demo** sets a playback range and frames it.
