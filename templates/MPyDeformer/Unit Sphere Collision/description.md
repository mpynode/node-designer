# Unit Sphere Collision

A collision `mPyDeformer` with memory. Vertices caught inside the collider sphere get pushed onto its surface, and the dent bakes in instead of springing back once the collider moves on. Good for footprints and impact marks.

Run setup from the Scene tab with the collider TRANSFORM picked first, the MESH second: it wires the collider's `worldMatrix` into `pusher`, attaches the deformer, and seeds a buffer so baked dents survive save and reopen. The deformer `envelope` blends back to the undented mesh.

**Create + Run demo** builds a frozen plane and a collider sphere animated sinking through it -- press play to watch the dent form and bake.

**Note:** the collision is computed in the mesh's OBJECT space, so apply it to a plane with a frozen / identity transform at the world origin.
