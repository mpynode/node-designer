# Linear Blend Skin

A real skinCluster (`mPySkinCluster`) doing classic linear blend skinning: every vertex lands on a weighted average of the joints influencing it. Useful for seeing how skinning behaves, or as a starting point for your own deformer.

Maya sees a genuine skinCluster, so Paint Skin Weights, the Component Editor and `cmds.skinPercent` all read and write its weights live -- nothing about your normal weighting workflow changes.

## Inputs

There are no extra attributes to set. It reads the standard skinCluster setup:

* the `weightList` weights, paintable exactly as on any skinCluster.
* the influence joints and their bind poses.
* `envelope` -- the standard deformer blend back to the unskinned mesh.

## Outputs

* The skinned mesh, written back through the deformer chain.

## Create + Run demo

Imports the bundled two-bone arm, moves the weights off its stock skinCluster onto this one, and bends the elbow so the arm starts posed.
