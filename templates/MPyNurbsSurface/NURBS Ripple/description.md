# Ripple Surface Generator

An `mPyNurbsSurface` that builds a rippling surface -- an 8x8 CV grid over a square, lifted in Y by a wave. The time input rolls the wave across it as the timeline plays.

Nothing appears until you wire the node's surface output into a real `nurbsSurface` shape's `create` plug. The Create command does that for you.

## Inputs

* `size` -- how wide the square patch is.
* `amplitude` -- how far the wave lifts the surface. 0 gives a flat plane.
* `freq` -- how many wave crests fit across the patch. Higher is tighter.
* `t` -- rolls the wave. Connect it to scene time.

## Outputs

* The generated NURBS surface. Connect it into a surface shape's `create` plug.

## Create + Run demo

Builds the render surface, dials up a visible ripple and sets a one-loop playback range.
