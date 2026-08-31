# Game Of Life

Conway's Game of Life as one procedural mesh (an `mPyMesh`). Every **live** cell becomes a cube built straight into `outMesh`, so a board of any size shows up as geometry with nothing to wire by hand. The board is `boardX` by `boardY` cells and steps forward once per frame. It does not wrap, so gliders die at the edge instead of reappearing on the far side.

Drive `frame` (already wired to the timeline) to animate. Set `resetBoard` to **True** to reseed a fresh random board each frame; `randomSamples` is how many cells start alive. `cellSize` is each cube's edge length -- the default 0.9 leaves a visible gap between neighbours.

Touching cubes are **not** welded -- overlapping faces are intentional, kept for speed and simplicity.

**Create + Run demo** builds the render mesh, seeds a lively 20x20 board and frames it. Play the timeline to watch it evolve.
