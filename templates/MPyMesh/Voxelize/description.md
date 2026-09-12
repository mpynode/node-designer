# Voxelize

Rebuilds a mesh as a hollow voxel shell (an `mPyMesh`), one cube per occupied cell. Use it for a chunky, blocky version of a model that stays live. The cubes are not welded.

Occupancy is found by closest point rather than by binning the source geometry, so the result does not depend on how finely the source happens to be tessellated -- a two-triangle wall voxelizes as solidly as a dense mesh. The lattice is anchored in world space, so the voxels do not swim when the source moves or deforms.

Each voxel takes its colour from the first of these that is available:

1. `textureFile`, sampled at the surface point under that voxel.
2. the source mesh's vertex colours, if the path is blank or the file cannot be read.
3. `defaultColor`, if there are no vertex colours either.

## Inputs

* `inMesh` -- the source mesh. Connect its `worldMesh`.
* `voxelSize` -- the cell size, in world units. This is the main dial. Halving it costs roughly eight times as much.
* `maxVoxels` -- a safety brake, checked before any work is done, so an over-fine setting aborts immediately with the real count rather than stalling Maya. Set it to 0 to disable.
* `textureFile` -- an image to colour the voxels from. Takes an absolute path, or one relative to the template search root, which is what `setup` seeds. Clear it to fall through to vertex colours.
* `defaultColor` -- the colour used when there is no texture and no vertex colour.

## Outputs

* The generated voxel shell -- one cube per occupied cell, each carrying its resolved colour.

## Commands

* `setup` -- select a mesh, then run: it wires that mesh in, builds the render mesh, seeds `textureFile` with the shipped test grid, and switches `displayColors` on so the colours actually draw. Offered as **Run setup on selection**.

## Create + Run demo

Voxelizes the shipped head (`head.ma`, the Mesh Regions face, jaw-drop and all). Scrub the timeline and the shell re-voxelizes the moving jaw; drag `voxelSize` and watch it rebuild live.
