# Mesh Maze

Turns any mesh into a maze and outputs the maze's walls as an `mPyMesh`. The source mesh is the floor; the walls stand on its edges, extruded along the vertex normals, so a maze on a sphere wraps around it properly instead of shearing through it.

The mapping is simply:

| Maze | Mesh |
|---|---|
| Cell | Face |
| Door | An interior edge the maze walked through |
| Wall | Every other edge |

Because the doors never form a loop, every cell is reachable, there is exactly one path between any two cells, and `start` to `end` is always solvable. Mixed triangles and quads both work.

## Inputs

* `inMesh` -- the source mesh, used as the floor. Connect its `worldMesh`.
* `start` / `end` -- the face ids the maze runs between. A negative id counts back from the end, so the default `end = -1` is the last face. An out-of-range id is clamped rather than rejected.
* `seed` -- which maze you get. Same seed, same maze, every time.
* `solutionLength` -- how far the maze must wander before it is allowed to reach `end`, as a fraction of the face count. It stops the exit landing three cells from the entrance. It matters most when `start` and `end` are close together. Worth knowing: `end` only joins the maze through this gate, so at a low setting moving `end` can leave the layout unchanged.
* `wallHeight` / `wallThickness` -- the size of each wall slab, in world units. Absolute, so dial them to your mesh's scale.
* `drawSolution` -- draw the `start` to `end` path as tiles on the floor. Off by default.
* `solutionStep` -- how much of the path to show: `0` is the entrance tile alone and `n` is the whole path, where `n` is the number of steps reported on `solutionSteps`. Keyframe it from `0` to `n` and the path draws itself out one cell per unit; a value past the exit clamps there.
* `wallColor` / `solutionColor` -- vertex colours for the wall slabs (flat green) and the path tiles (yellow). `setup` turns `displayColors` on for the render mesh so they show.

## Outputs

* `outMesh` -- the wall geometry, plus the solution tiles when they are on. Slabs are not welded to each other. Each tile is its face's own polygon, inset half a wall thickness so it sits between the walls and floated a tenth of the wall height above the floor.
* `solutionSteps` -- the number of steps from `start` to `end` through the doors, which is what to key `solutionStep` up to. `0` when `end` cannot be reached, in which case no tiles are drawn.

## Commands

* `setup` -- select a mesh, then run: it wires that mesh in, builds the render mesh for the walls standing on it and switches its `displayColors` on. Offered as **Run setup on selection**.

Two things that look like bugs and are not. **Unreachable patches are left bare** -- if the mesh is in more than one connected piece, which unwelded vertices and T-junctions on imported geometry routinely cause, only the piece containing `start` gets a maze. Bad face ids and non-manifold edges degrade the same quiet way rather than erroring. And on a mesh with a hole or a handle, a torus say, you get a few detached closed wall loops floating in the maze. Triangles are dead-end magnets, so a tri-heavy mesh gives a stubbier maze than a quad one.

## Create + Run demo

Wraps a maze around the shipped head (`head.ma`, the Mesh Regions face, jaw-drop and all), switches the solution on and keys `solutionStep` one cell per frame from the entrance to the exit. Play the timeline and the yellow path draws itself through the maze while the jaw moves; drag `seed` and watch the maze rebuild.
