# Voxelize

Rebuilds a mesh as a hollow **voxel shell** (an `mPyMesh`) on `outMesh`, one cube per occupied cell. Use it for a chunky, blocky version of a model that stays live. The cubes are **not** welded.

Occupancy is found by **closest point**, not by binning the source geometry, so the result does not depend on how finely the source happens to be tessellated -- a two-triangle wall voxelizes as solidly as a dense mesh:

1. Lay a **world-anchored** lattice over the source bounding box. Cell `i` spans `[i*voxelSize, (i+1)*voxelSize)`, so a cube **corner** sits exactly on the origin. Because the lattice is fixed in world space and not tied to the mesh's own minimum, the voxels do not swim when the source moves or deforms.
2. Build the dense 3D cloud of every cell **centre** in that box and ask the mesh for the closest surface point to each.
3. Snap each returned sample to the cell containing it and drop the duplicates, keeping the sample **closest to its own grid point**. Those cells are the voxels, and each winner supplies its cube's colour.

Colour resolves down a chain, and each link is a *fallback*, never an error:

1. **`textureFile`** sampled bilinearly at the UV of the exact closest point. The image is read with Maya's own `MImage` (no PIL) and linearized from sRGB, so voxels shade at the same brightness a standard `file` node would give.
2. The source mesh's **vertex colours**, when the path is blank or the file cannot be read.
3. **`defaultColor`**, when there are no vertex colours either.

`textureFile` takes an absolute path, or one **relative to a template search root** -- which is what `setup` seeds it with (`MPyFile/File Simple/test_grid.png`, the grid the MPyFile examples use), so the shipped example paints no matter where mpynode's templates are installed. Clear the field to fall through to the rest of the chain. `setup` also switches **`displayColors`** on for the render mesh it builds, since a new mesh does not draw its colour set until you do.

Attributes are interpolated with the hit triangle's barycentric weights, so the lookup sits on the true closest point rather than on a nearby sample. UVs are collapsed to one per vertex first, so on a UV seam one of the several is kept -- invisible at voxel resolution.

`maxVoxels` is a safety brake, and it is checked on the **grid** before a single query runs. The sweep is cubic in `1/voxelSize`, so halving `voxelSize` costs eight times as much; the brake aborts immediately with the real count rather than stalling Maya. Set it to 0 to disable.

**Create + Run demo** voxelizes a sphere so you can drag `voxelSize` and watch the shell rebuild live.
