# Helix Curve Generator

An `mPyNurbsCurve` that builds a helix -- a coil of a given radius, rising over a number of turns. The result is a 120-CV degree-3 curve, and the time input spins it as the timeline plays.

Nothing appears until you wire the node's curve output into a real `nurbsCurve` shape's `create` plug. The Create command does that for you.

## Inputs

* `radius` -- how wide the coil is.
* `height` -- how far it rises from bottom to top.
* `turns` -- how many revolutions it makes over that height. Fractional turns are fine.
* `t` -- spins the coil. Connect it to scene time.

## Outputs

* The generated NURBS curve. Connect it into a curve shape's `create` plug.

## Create + Run demo

Builds the render curve, dials in a wide coil and sets a one-loop playback range -- press play to watch it turn.
