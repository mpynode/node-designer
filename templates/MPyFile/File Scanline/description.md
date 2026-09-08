# File Scanline

A file texture (`mPyFile`) with an animated scan band rolling over it -- an old-CRT look. It draws in the swatch, in the viewport, and in an Arnold render.

If `fileName` is blank or missing, the node falls back to whatever is baked into its `embeddedImage` variable. The demo bakes the bundled `test_grid.png` into it for you.

## Inputs

* `bands` -- how many scan bands fit vertically (default 12).
* `speed` -- how fast they scroll (default 0.1). Negative scrolls the other way.
* `intensity` -- how dark the troughs get, 0 to 1 (default 0.6). 0 hides the effect.
* `frame` -- drives the scroll, auto-wired to the timeline.
* `fileName` -- the image on disk. Leave it blank to use the baked fallback.
* `uvCoord` -- the sample position, wired for you by the shading network.

## Outputs

* `outColor` and `outAlpha` -- the texture with the bands applied. Connect them anywhere a file node would go.

## Create + Run demo

Builds a plane and an unlit surfaceShader, sets a 1-120 playback range so the bands scroll on play, and wires the Arnold path when MtoA is present.
