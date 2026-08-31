# Ripple Surface Generator

An `mPyNurbsSurface` that builds a rippling surface: an 8x8 CV grid over a `size`-wide square, lifted in Y by a sin/cos wave of `amplitude` and `freq`. A `t` time input wired to the timeline rolls the wave across it. Nothing appears until you wire `outSurface` into a real `nurbsSurface` shape's `create` plug.

**Create + Run demo** builds the render surface, dials up a visible ripple and sets a one-loop playback range. Compiles to pure C++.
