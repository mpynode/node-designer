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

## Outputs

* The generated wall geometry. Slabs are not welded to each other.

## Commands

* `setup` -- select a mesh, then run: it wires that mesh in and builds the render mesh for the walls standing on it. Offered as **Run setup on selection**.

Two things that look like bugs and are not. **Unreachable patches are left bare** -- if the mesh is in more than one connected piece, which unwelded vertices and T-junctions on imported geometry routinely cause, only the piece containing `start` gets a maze. Bad face ids and non-manifold edges degrade the same quiet way rather than erroring. And on a mesh with a hole or a handle, a torus say, you get a few detached closed wall loops floating in the maze. Triangles are dead-end magnets, so a tri-heavy mesh gives a stubbier maze than a quad one.

## Create + Run demo

Wraps a maze around the shipped head (`head.ma`, the Mesh Regions face, jaw-drop and all). Scrub the timeline and the maze rebuilds on the moving jaw; drag `seed` and watch it rebuild.
