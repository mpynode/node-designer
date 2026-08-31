# RBF Wrap Deformer

A cage wrap, as an `mPyDeformer`. Build a low-resolution cage around your geometry and duplicate it: the untouched copy goes into `restCage`, the animated one into `deformCage`. Bend, twist or move the deform cage and everything wrapped inside follows smoothly. Good for driving dense geometry from a handful of easy-to-animate points.

The warp is a thin-plate spline -- the smoothest shape you can pull through a set of points. A plain move, rotate or scale of the whole cage comes through exactly; anything more elaborate bends the geometry with as little wrinkling as possible.

Being a deformer, the result is the node's own `outputGeometry`, so there is no mesh output to wire, and the `envelope` blends the warp back to rest. Until both cages carry points and agree on point count, `hasCage` keeps the node a pass-through, so a new or half-wired wrap never collapses your geometry onto the origin.

The warp runs in OBJECT space while the cages are read in WORLD space, so freeze the deformed mesh at the world origin.

**Create + Run demo** wraps a sphere inside a lightly subdivided cube cage and flexes the cage with a keyed bend -- press play to watch the sphere follow the cage. Compiles to pure C++.
