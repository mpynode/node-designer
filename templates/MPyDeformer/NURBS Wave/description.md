# NURBS Wave Deformer

An `mPyDeformer` that pushes each CV along X by a sine of its height in Y, so a wave rolls across a NURBS surface as the timeline plays. The same node also deforms polygon meshes. Inputs: `amplitude`, `freq`, `time`, plus the built-in deformer `envelope`.

**Create + Run demo** builds a NURBS plane, attaches this deformer and sets a one-loop playback range -- press play to watch the wave travel. Compiles to pure C++.
