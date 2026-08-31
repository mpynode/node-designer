# File Scanline

A file texture (`mPyFile`) with an animated scan band rolling over it -- an old-CRT look. `bands` sets how many fit across V (default 12), `speed` the scroll rate (default 0.1), `intensity` how dark the troughs get, 0-1 (default 0.6), and `frame` is auto-wired to the timeline.

If `fileName` is blank or missing, the node falls back to whatever is baked into the `embeddedImage` variable -- the demo bakes the bundled `test_grid.png` into it for you.

It draws in the swatch, the viewport and an Arnold render (via OSL).

**Create + Run demo** builds a plane and an unlit surfaceShader, sets a 1-120 playback range so the bands scroll on play, and wires the Arnold OSL path (when MtoA is present) with `tIn` driven by time.
