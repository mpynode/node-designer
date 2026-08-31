# Mesh Maze

Turns any mesh into a **maze**, and outputs the maze's **walls** as an `mPyMesh` on `outMesh`. The source mesh is the floor; the walls stand on its edges, extruded along the **vertex normals**, so a maze on a sphere wraps around it properly instead of shearing through it.

The whole thing is one idea: **a maze on a mesh is a spanning tree of that mesh's dual graph.**

| Maze | Mesh |
|---|---|
| Cell | Face |
| Door | Interior edge the tree walked through |
| Wall | Every other edge |

Because the doors form a *tree*, three things come for free: every cell is reachable, there is exactly **one** path between any two cells, and `start` -> `end` is always solvable -- no validation pass needed. None of it depends on face valence, so mixed triangles and quads just work.

- `start` / `end` -- the **face ids** the maze runs between. A negative id counts back from the end, so the default **`end = -1` is the last face**. An id that is still out of range is clamped rather than rejected.
- `seed` -- which maze you get. Same seed, same maze, every time.
- `solutionLength` -- how deep the carve must be before it is allowed to reach `end`, as a fraction of the face count. It is what stops a maze from parking the exit three cells from the entrance. It matters most when `start` and `end` are **close together**; when they are already far apart the maze is long anyway and the setting does little. Worth knowing: `end` reaches the maze *only* through this gate, so at a low setting the gate never fires and moving `end` can leave the layout completely unchanged.
- `wallHeight` / `wallThickness` -- the size of each wall slab, in world units. They are absolute, so dial them to your mesh's scale.

**Unreachable patches are left bare.** If the mesh's dual graph is in more than one piece -- which is what unwelded vertices, bowties and T-junctions produce, and they are near-universal on imported geometry -- only the piece containing `start` gets a maze. The rest gets no walls at all, which reads at a glance as *that region is not connected* rather than failing. Bad face ids, degenerate faces and non-manifold edges degrade the same way: this node does not error out.

A couple of honest limits. Wall slabs are **not welded** to each other. On a mesh with holes or a handle (a torus, say) you get a few detached closed wall loops floating in the maze -- still a perfect maze, and the count of them is fixed by the surface's topology, not by the algorithm. And triangles are dead-end magnets, so a tri-heavy mesh gives a stubbier maze than a quad one.

**Create + Run demo** wraps a maze around a poly sphere. Drag `seed` and watch it rebuild.
