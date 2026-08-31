# Spline

Evaluates a b-spline through control points, De Boor style. Put the positions in the `cv` vector array, set `degree`, and evenly spaced points come back in `samples`. The count follows the output array size; no Maya curve is created.

**Create + Run demo** builds five zig-zagged locators feeding `cv` and 24 sample spheres along the curve -- drag a locator and the spheres follow.
