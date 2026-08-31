# Composite Stack (compositeTexture)

An `mPyFile` that stacks an ARBITRARY number of images into one texture, so you
can build a background plus as many decals as you like without authoring a new
image.

`layers` is an ARRAY of image paths, composited bottom (`layers[0]`) to top with
alpha-over at the sampled point, and `opacities` is a matching array of weights.
Add an element, get a layer -- there is no fixed slot count, and the compiled
node loops over the runtime array length exactly as the interpreted one does.

A layer with no file (or an unreadable one) drops out of the stack on its own:
every sample passes `missing=(0.0, 0.0, 0.0, 0.0)`, so an empty layer is fully
transparent rather than the opaque magenta "no image" colour that would cover
everything beneath it. An `opacities` element is a plain weight on top of that
-- 0 still removes a layer exactly. A layer with no matching opacity element
defaults to 1.0.

Drop the `missing=` argument to get the magenta sentinel back. That is often
what you want while authoring, because it makes a typo'd path impossible to
miss; transparent failure is quiet by design.

If the node renders as nothing at all, check that `layers` actually has
elements: an empty array is an empty stack, and the surface comes out fully
transparent rather than black.

Every layer is loaded by the same framework call the File Simple template
uses, `self.read_texture(path)`, so all of them go through this node's
`colorSpace`, `preFilter`, `preFilterKernel` and `preFilterRadius`. That is
also why this template compiles: the loads lower straight to
`nd_tex_load_linear`, with no hand-written C++ loader, and the string array
lifts to a `std::vector<std::string>`.

The stack is sampled at `uvCoord` and comes out `outColor` / `outAlpha`,
composited over black (premultiplied), which is what an unlit shader wants.

**Create + Run demo** builds a plane and an unlit shader, then loads the four
images shipped beside this template -- `grid_bg.png`, `red_square.png`,
`green_circle.png`, `blue_triangle.png` -- into the first four array elements at
full opacity. Four is just what the demo loads; append a fifth and it composites.
