# Helix Curve Generator

An `mPyNurbsCurve` that builds a helix: a coil of `radius`, rising `height` over `turns` revolutions. The result is a 120-CV degree-3 curve, and a `t` time input wired to the timeline spins it. Nothing appears until you wire `outCurve` into a real `nurbsCurve` shape's `create` plug.

**Create + Run demo** builds the render curve, dials in a wide coil and sets a one-loop playback range -- press play to watch it turn. Compiles to pure C++.
