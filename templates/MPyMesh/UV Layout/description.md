# UV Layout (mesh -> UVs as a mesh)

An `mPyMesh` that shows a mesh's UV layout as flat geometry in the 3D view. Each UV becomes an (u, v, 0) point and the per-face UV connectivity becomes the faces, so you can see stretching, overlaps and seams on real geometry.

- `inMesh` -- the source mesh (connect its `worldMesh`).
- `uvSetName` -- which UV set to show. Blank picks the first set, usually `map1`.

Select a mesh, then Run setup -- it wires the mesh in and builds the UV render mesh for you.
