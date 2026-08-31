# Game Of Life Texture

Conway's Game of Life running as a live texture (an `mPyFile`). It steps a grid of cells once per frame and paints it onto whatever surface you assign -- white for alive, black for dead.

`width` and `height` set the grid (default 100x100). `frame` is auto-wired to the timeline, so it animates on play. `density` (0-1, default 0.5) is the fraction of cells that start alive; set `reset` to **True** to reseed the board.

The grid does not wrap: a cell at the edge has no neighbours past it, so gliders die at the border instead of reappearing on the far side.

It draws in the swatch, the viewport and an Arnold render (via OSL). Because the simulation carries state, Arnold samples a PNG the node re-bakes each frame.

**Create + Run demo** builds a polyPlane, a lambert shader and (when MtoA is present) the Arnold OSL render path, all wired to this node.

**Note:** the bake rides the normal viewport / swatch evaluation, so the frame you are looking at renders correctly in Arnold. A headless batch may need a per-frame `dgeval` so each frame bakes before Arnold samples it.

**Note:** the bake is a numbered SEQUENCE beside `bakePath` (`x.png` -> `x.0007.png`), because Arnold's texture cache is keyed on the filename and never re-checks the file -- one overwritten path would render the first frame forever. Two consequences: scrubbing leaves one small PNG per visited frame in your temp directory, and editing `width`, `density` or `reset` while the frame is HELD will not change an Arnold render until the frame moves (the viewport and swatch update immediately).
