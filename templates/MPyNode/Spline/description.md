# Spline

Evaluates a b-spline through control points. Put the positions in `cv`, set the degree, and evenly spaced points along the curve come back out. No Maya curve is created, so there is no shape to manage.

## Inputs

* `cv` -- the control point positions, in order. Wire a locator's translate into each element.
* `degree` -- the curve degree. 1 gives straight segments, 3 the usual smooth curve. Clamped if you have too few control points for the degree you ask for.

## Outputs

* `samples` -- evenly spaced positions along the curve. The number of samples follows how many elements you connect.

## Create + Run demo

Builds five zig-zagged locators feeding `cv` and 24 sample spheres along the curve -- drag a locator and the spheres follow.
