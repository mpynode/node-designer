# Patch Relax

An `mPyDeformer` that spreads bunched and pinched polygons back into an even layout -- **without the shrinking a Laplacian smooth causes**. Use it to clean up after a skin, wrap or squash.

Each vertex flattens its ring of neighbours into a 2D *decal map* and steps toward the rest layout, rotated to match the current pose. Carrying each patch's own rotation is what saves the silhouette.

**Patch-based surface relaxation**, de Goes et al., Pixar, *SIGGRAPH '18 Talks* ([doi:10.1145/3214745.3214768](https://doi.org/10.1145/3214745.3214768)).

## Inputs

* `restMesh` -- the undistorted reference. Supplies both the rest edge layout and the topology.
* `iterations` -- Jacobi sweeps (default 20). Each sweep reads the previous one's positions and writes a fresh buffer, so the result never depends on vertex order.
* `alpha` -- how strongly the rest layout is enforced; 0 is a no-op.
* `surfaceBlend` -- 0 relaxes through space, 1 slides along the surface. **Defaults to 0**, see the note below.
* `ringNbrs` / `ringWidth` -- the CCW 1-ring adjacency, seeded by **Rebuild Rings**.
* `envelope` -- the standard deformer blend against the un-relaxed input.

## Rebuild Rings

Run the **Rebuild Rings** command once after wiring a rest mesh, and again only if its TOPOLOGY changes -- moving vertices needs no rebuild. The rings are an input rather than something the compute derives for two reasons: they depend only on connectivity, so rebuilding them every frame is waste; and building them needs `repeat`/`argsort`/`bincount`, which the transpiler rejects. Seeding them is what lets the whole compute lower to pure C++. Until they are seeded the node is a pass-through, not a collapse.

Border vertices are **pinned**. The decal map normalizes a ring's angles to 2*pi, which only means anything on a closed ring; applying it to an open fan drags the border inward.

## Note on `surfaceBlend`

The reference builds the surface target as `step * (vp2 - alpha * Rvh2)`, where `Rvh2` is `vh2` scaled by `|vp2|/|vh2|` and rotated by `arg(vp2) - arg(vh2)`. That construction *is* `vp2` by definition, so the target collapses to `step * (1 - alpha) * vp2` and the surface branch does nothing at `alpha = 1`. On a bunched torus, through-space leaves 59% of the input edge error after 20 sweeps, `surfaceBlend = 0.8` leaves 87%, and `surfaceBlend = 1.0` leaves 100% -- the mesh does not move. This is faithful to the reference, which is why the default here is 0.

**Create + Run demo** squashes and twists a sphere so its polygons bunch up, then relaxes them back -- press play, and toggle `envelope` to compare the bunched input against the relaxed result.
