# File Simple

A file texture (`mPyFile`) that can carry its own picture. It samples the image, applies brightness then contrast around mid-grey, and outputs colour and alpha exactly like a stock Maya file node. It draws in the swatch, in the viewport, and in an Arnold render.

Bake an image into the node's `embeddedImage` variable and it falls back to that whenever `fileName` is blank or the path is missing, so the texture travels with the scene.

## Inputs

* `brightness` -- lifts or lowers the whole image. Applied before contrast.
* `contrast` -- pushes values away from mid-grey. 1 leaves the image alone.
* `fileName` -- the image on disk, as on any file node. Leave it blank to use the baked fallback.
* `uvCoord` -- the sample position, wired for you by the shading network.

## Outputs

* `outColor` and `outAlpha` -- the sampled, adjusted texture. Connect them anywhere a file node would go.

## Create + Run demo

Builds a sphere and an unlit surfaceShader, points `fileName` at the shipped `test_grid.png` and bakes it into the fallback, and wires the Arnold render path when MtoA is present.
