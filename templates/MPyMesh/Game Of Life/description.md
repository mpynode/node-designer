# Game Of Life

Conway's Game of Life as one procedural mesh (an `mPyMesh`). Every live cell becomes a cube built straight into the output, so a board of any size shows up as geometry with nothing to wire by hand.

The board does not wrap, so gliders die at the edge rather than reappearing on the far side. Touching cubes are not welded -- the overlapping faces are intentional, and keep it fast.

## Inputs

* `boardX` / `boardY` -- the board size in cells.
* `frame` -- steps the simulation, already wired to the timeline.
* `resetBoard` -- set it to **True** to reseed a fresh random board.
* `randomSamples` -- how many cells start alive when reseeding.
* `cellSize` -- each cube's edge length. The default 0.9 leaves a visible gap between neighbours; 1.0 makes them touch.

## Outputs

* The generated mesh -- one cube per live cell, rebuilt each frame.

## Create + Run demo

Builds the render mesh, seeds a lively 20x20 board and frames it. Play the timeline to watch it evolve.
