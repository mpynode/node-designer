# RBF Wrap

A cage-driven wrap that outputs a mesh rather than acting as a deformer. Hand it two copies of one cage -- `restCage` at rest, `deformCage` posed -- plus the geometry to carry, and the warped result comes out as a mesh you can connect on.

Move, rotate or scale the whole cage and the geometry follows exactly; push a few points and it bends smoothly between them. Use this when you want the warp as a mesh output, and the **RBF Wrap Deformer** template when you want it in a deformer chain.

## Inputs

* `restCage` -- the cage at rest. Measured against, never animated.
* `deformCage` -- the posed copy. Must share topology with `restCage`.
* `geoToDeform` -- the geometry to carry. Needs no relation to the cage topology, so a light cage can drive a dense mesh.

## Outputs

* `outGeo` -- the warped geometry. Connect it into a mesh shape's `inMesh`.

## Commands

* `setup` -- wires the whole thing from your selection: pick the REST cage, the DEFORM cage and the GEOMETRY to warp, in that order. It also creates the result mesh the output is written to. Offered as **Run setup on selection**.

## Create + Run demo

Wraps the shipped two-bone arm mesh in a lightly subdivided cube cage and flexes it with a keyed bend -- press play to watch the arm follow.
