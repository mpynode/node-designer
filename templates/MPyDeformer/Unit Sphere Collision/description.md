# Unit Sphere Collision

A collision `mPyDeformer` with memory. Vertices caught inside the collider sphere are pushed out onto its surface, and the dent stays put instead of springing back once the collider moves on. Good for footprints and impact marks.

The collision is computed in the mesh's OBJECT space, so apply it to geometry with a frozen transform at the world origin.

## Inputs

* `pusher` -- the collider's world matrix. Anything scaled uniformly acts as a sphere of that radius; wire a transform's `worldMatrix` here.
* `envelope` -- the standard deformer blend back to the undented mesh.

## Outputs

* The dented mesh, written back through the deformer chain. Dents accumulate rather than reset, and survive a save and reopen.

## Commands

* `setup` -- pick the collider TRANSFORM first and the MESH second, then run. It wires the collider's `worldMatrix` into `pusher`, attaches the deformer, and seeds the buffer that lets baked dents persist. Offered as **Run setup on selection**.

## Create + Run demo

Builds a frozen plane and a collider sphere animated sinking through it -- press play to watch the dent form and stay.
