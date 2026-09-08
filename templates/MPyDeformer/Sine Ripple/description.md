# Sine Ripple Deformer

An `mPyDeformer` that pushes each vertex along its normal with a sine wave, so ripples spread out from the mesh centre and travel as time advances. Good for water, flags, and any rolling wobble.

## Inputs

* `amplitude` -- how far each vertex is pushed. 0 is a no-op.
* `frequency` -- how many ripples fit between the centre and the edge. Higher is tighter.
* `speed` -- how fast the ripples travel outward.
* `time` -- drives the travel. Connect it to scene time.
* `envelope` -- the standard deformer blend against the undeformed input.

## Outputs

* The deformed mesh, written back through the deformer chain.

## Create + Run demo

Builds a subdivided plane, attaches the deformer and sets a one-loop playback range -- press play to watch the ripple travel.
