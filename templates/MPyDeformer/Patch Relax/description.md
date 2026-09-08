# Patch Relax

An `mPyDeformer` that spreads bunched and pinched polygons back into an even layout -- **without the shrinking a Laplacian smooth causes**. Use it to clean up after a skin, wrap or squash.

Each vertex flattens its ring of neighbours into a flat map and steps toward the rest layout, rotated to match the current pose. Carrying each patch's own rotation is what saves the silhouette.

**Patch-based surface relaxation**, de Goes et al., Pixar, *SIGGRAPH '18 Talks* ([doi:10.1145/3214745.3214768](https://doi.org/10.1145/3214745.3214768)).

## Inputs

* `restMesh` -- the undistorted reference. Supplies both the rest edge layout and the topology.
* `iterations` -- how many relax passes to run (default 20). More passes give a more even result and cost more time.
* `alpha` -- how strongly the rest layout is enforced. 0 is a no-op.
* `surfaceBlend` -- 0 relaxes through space, 1 slides along the surface. Leave it at 0; at 1 the mesh does not move at all.
* `ringNbrs` / `ringWidth` -- the neighbour table, filled in by `rebuild_rings`. Until it is seeded the node passes the geometry through unchanged.
* `envelope` -- the standard deformer blend against the un-relaxed input.

## Outputs

* The deformed mesh, written back through the deformer chain. Border vertices are pinned and stay where they are.

## Commands

* `rebuild_rings` -- reads the connected `restMesh` and fills in `ringNbrs` / `ringWidth`. Run it once after wiring a rest mesh, and again only if that mesh's topology changes -- moving vertices needs no rebuild.
* `setup` -- wires the node onto the mesh it deforms and makes it live. Offered as **Run setup on selection**, and also what the Create command runs.

## Create + Run demo

Squashes and twists a sphere so its polygons bunch up, then relaxes them back -- press play, and toggle `envelope` to compare the bunched input against the relaxed result.
