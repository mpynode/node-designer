# RBF Wrap Deformer

A cage wrap, as an `mPyDeformer`. Build a low-resolution cage around your geometry and duplicate it: the untouched copy goes into `restCage`, the animated one into `deformCage`. Bend, twist or move the deform cage and everything wrapped inside follows smoothly. Good for driving dense geometry from a handful of easy-to-animate points.

A plain move, rotate or scale of the whole cage comes through exactly. Anything more elaborate bends the geometry with as little wrinkling as possible.

The warp runs in OBJECT space while the cages are read in WORLD space, so freeze the deformed mesh at the world origin.

## Inputs

* `restCage` -- the cage at rest, untouched. Measured against, never animated.
* `deformCage` -- the animated copy. Must have the same point count as `restCage`.
* `envelope` -- the standard deformer blend back to rest.

## Outputs

* The wrapped geometry, written back through the deformer chain. Until both cages carry points and agree on point count the node passes geometry through unchanged, so a half-wired wrap never collapses your mesh onto the origin.

## Create + Run demo

Wraps a sphere inside a lightly subdivided cube cage and flexes the cage with a keyed bend -- press play to watch the sphere follow.
