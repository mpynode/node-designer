# UV Layout

An `mPyMesh` that shows a mesh's UV layout as flat geometry in the 3D view. Each UV becomes a point at (u, v, 0) and the face connectivity comes across with it, so you can see stretching, overlaps and seams on real geometry rather than in the UV editor.

## Inputs

* `inMesh` -- the source mesh. Connect its `worldMesh`.
* `uvSetName` -- which UV set to show. Blank picks the first set, usually `map1`.

## Outputs

* The generated flat mesh, one face per source face, laid out in UV space.

## Commands

* `setup` -- select a mesh, then run: it wires that mesh in and builds the UV render mesh for you. Offered as **Run setup on selection**.

## Create + Run demo

Builds the layout mesh for a sample model so you can see the seams as geometry.
