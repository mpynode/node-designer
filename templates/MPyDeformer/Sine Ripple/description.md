# Sine Ripple Deformer

An `mPyDeformer` that pushes each vertex along its normal with a sine wave, so ripples spread from the mesh centre and travel as `time` advances -- good for water, flags, and any rolling wobble. Inputs: `amplitude`, `frequency`, `speed`, `time`, plus the built-in `envelope`.

**Create + Run demo** builds a subdivided plane, attaches the deformer and sets a one-loop playback range -- press play to watch the ripple travel.
