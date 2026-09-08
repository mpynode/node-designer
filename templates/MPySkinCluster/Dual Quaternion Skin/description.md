# Dual Quaternion Skin

A real skinCluster (`mPySkinCluster`) doing dual quaternion skinning. Instead of averaging joint matrices, it blends each joint's rotation and translation together, so a bent elbow or twisted wrist keeps its volume rather than collapsing into the classic candy-wrapper pinch.

It reads the same weights as the **Linear Blend Skin** template, so Paint Skin Weights, the Component Editor and `cmds.skinPercent` all drive it, and one set of weights works in either.

## Inputs

There are no extra attributes to set. It reads the standard skinCluster setup:

* the `weightList` weights, paintable exactly as on any skinCluster.
* the influence joints and their bind poses.
* `envelope` -- the standard deformer blend back to the unskinned mesh.

## Outputs

* The skinned mesh, written back through the deformer chain.

## Create + Run demo

Imports the bundled two-bone arm, moves the weights off its stock skinCluster onto this one, and bends the elbow so the arm starts posed. Compare the bent volume against the Linear Blend Skin template.
