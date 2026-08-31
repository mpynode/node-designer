# File Simple

A file texture (`mPyFile`) that can carry its own picture. It samples `fileName` at `uvCoord`, applies `brightness` then `contrast` around mid-grey, and writes `outColor`/`outAlpha` like a stock file node. It draws in the swatch, the viewport and an Arnold render (via OSL).

Bake an image into the `embeddedImage` variable and the node falls back to it whenever `fileName` is blank or missing, so the texture travels with the scene.

**Create + Run demo** builds a sphere and an unlit surfaceShader, points `fileName` at the shipped `test_grid.png` and bakes it into the fallback, and (when MtoA is present) wires the Arnold OSL render path.
