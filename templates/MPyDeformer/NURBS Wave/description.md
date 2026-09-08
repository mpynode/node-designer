# NURBS Wave Deformer

An `mPyDeformer` that pushes each point along X by a sine of its height in Y, so a wave rolls up a NURBS surface as the timeline plays. It deforms polygon meshes just as well.

## Inputs

* `amplitude` -- how far the wave pushes each point. 0 is a no-op.
* `freq` -- how many wave crests fit across the surface. Higher is tighter.
* `time` -- drives the travel. Connect it to scene time.
* `envelope` -- the standard deformer blend against the undeformed input.

## Outputs

* The deformed surface or mesh, written back through the deformer chain.

## Create + Run demo

Builds a NURBS plane, attaches the deformer and sets a one-loop playback range -- press play to watch the wave travel.
