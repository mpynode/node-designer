# Composite Stack

An `mPyFile` that stacks any number of images into one texture, so you can build a background plus as many decals as you like without authoring a new image.

Add an element to `layers` and you get a layer -- there is no fixed slot count.

Every layer goes through this node's own `colorSpace` and pre-filter settings, so the whole stack is filtered consistently.

## Inputs

* `layers` -- an array of image paths, composited bottom (`layers[0]`) to top with alpha-over. A layer whose file is missing or unreadable drops out of the stack as fully transparent rather than covering everything beneath it.
* `opacities` -- a matching array of weights. 0 removes a layer exactly. A layer with no matching element defaults to full opacity.
* `uvCoord` -- the sample position, wired for you by the shading network.

## Outputs

* `outColor` and `outAlpha` -- the composited stack over black, which is what an unlit shader wants. Connect them anywhere a file node would go.

If the surface renders as nothing at all, check that `layers` actually has elements -- an empty array is an empty stack, and comes out fully transparent rather than black. Note that a typo'd path fails the same quiet way, so it is worth checking paths before hunting elsewhere.

## Create + Run demo

Builds a plane and an unlit shader, then loads the four images shipped beside this template -- `grid_bg.png`, `red_square.png`, `green_circle.png`, `blue_triangle.png` -- into the first four elements at full opacity. Four is just what the demo loads; append a fifth and it composites.
