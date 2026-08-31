# RBF Wrap

A wrap deformer driven by a cage. Hand it two copies of one cage -- `restCage` at rest, `deformCage` posed -- plus the geometry to carry on `geoToDeform`, and the warped result comes out on `outGeo`.

The two cages define a thin-plate spline (an RBF), the smoothest warp from one to the other: move, rotate or scale the whole cage and the geometry follows exactly; push a few points and it bends smoothly between them. The cages must share topology; `geoToDeform` need not, so a light cage drives a dense mesh.

**Create + Run demo** wraps the shipped two-bone arm mesh in a lightly-subdivided cube cage and flexes it with a keyed bend -- press play to watch the arm follow. Compiles to pure C++.
