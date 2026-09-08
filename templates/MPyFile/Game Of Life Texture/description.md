# Game Of Life Texture

Conway's Game of Life running as a live texture (an `mPyFile`). It steps a grid of cells once per frame and paints it onto whatever surface you assign -- white for alive, black for dead. It draws in the swatch, in the viewport, and in an Arnold render.

The grid does not wrap: a cell at the edge has no neighbours past it, so gliders die at the border rather than reappearing on the far side.

## Inputs

* `width` / `height` -- the grid size (default 100 x 100).
* `density` -- the fraction of cells that start alive, 0 to 1 (default 0.5).
* `reset` -- set it to **True** to reseed the board from `density`.
* `frame` -- steps the simulation, auto-wired to the timeline.
* `bakePath` -- where the Arnold bake sequence is written. Leave it alone unless you need the files somewhere specific.
* `uvCoord` -- the sample position, wired for you by the shading network.

## Outputs

* `outColor` and `outAlpha` -- the current board as a texture. Connect them anywhere a file node would go.

Two things to know when rendering in Arnold. Scrubbing leaves one small PNG per visited frame beside `bakePath`, and changing `width`, `density` or `reset` while the frame is HELD will not change an Arnold render until the frame moves -- the viewport and swatch update immediately either way. A headless batch may need a per-frame `dgeval` so each frame bakes before Arnold samples it.

## Create + Run demo

Builds a polyPlane, a lambert shader and the Arnold render path when MtoA is present, all wired to this node.
