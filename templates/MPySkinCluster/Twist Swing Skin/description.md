# Twist / Swing Skin

A real skinCluster that carries two independent sets of skin weights instead of one. A normal skinCluster gives you a single weight list, so you cannot paint a tight twist falloff and a soft bend falloff on the same joint. Here you can.

One set drives a dual-quaternion twist around each bone's own axis, the other a linear-blend swing, or bend. Paint them separately and the node deforms from both.

## Inputs

* `twistWeights` -- the twist set, one weight per vertex per influence. Drives the rotation around the bone.
* `swingWeights` -- the swing set. Drives the bend.
* `skinMode` -- which set you are painting. **Paint LBS (Swing)** and **Paint DQS (Twist)** each load their set into the paintable weights, so Paint Skin Weights and the Component Editor show it immediately and your strokes bank back into that set. **Live Result**, the default, deforms from both sets at once.
* `twistAxis` -- which bone-local axis the twist happens around.
* `envelope` -- the standard deformer blend back to the unskinned mesh.

## Outputs

* The skinned mesh, written back through the deformer chain, with the twist and swing passes combined.

One caveat when painting: the load and bank are deferred a frame for safety, so switching `skinMode` in the middle of a stroke can drop that stroke. Paint, pause, then switch.

## Create + Run demo

Skins the bundled two-bone arm, seeding `twistWeights` with a rigid twist falloff and `swingWeights` with a smooth bend falloff. The elbow twists first over frames 0 to 30, then bends over frames 30 to 90, so you see each set on its own.
