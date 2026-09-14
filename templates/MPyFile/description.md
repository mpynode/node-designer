# mPyFile

A scriptable file texture: an `MPxNode` paired with an `MPxShadingNodeOverride` (API 2.0). It recreates the stock `file` node with every line of the image pipeline exposed as editable Python: colour-space conversion, pre-filtering, sampling, and the Viewport 2.0 upload. Plug it into a shader `color` channel and it shades in the viewport, the Hypershade swatch and the software renderer.

## Specific to this node

* Four code tabs instead of two. Init holds the pipeline math (about 550 lines by default), Compute samples `self.outColor` and `self.outAlpha` for the dependency-graph path, Viewport builds the GPU texture and sampler state for `updateShader`, and OSL is a connectable render-target string, authored by hand or translated from Compute.
* Created as a texture. `create()` goes through `shadingNode -asTexture`, so Maya adds the `place2dTexture` upstream like any 2D texture; `as_texture=False` makes a bare node.
* A preset plug surface identical to the reference `customFileTexture`: `fileName`, `uvCoord`, `uvFilterSize`, `colorSpace` (25 entries, stable indices), `preFilter` / `preFilterKernel` / `preFilterRadius`, `filterMode`, `maxAnisotropy`, `mipmapMode`, `mipLODBias`, `minLOD` / `maxLOD`, `wrapModeU` / `wrapModeV`, `borderColor`, and the outputs `outColor` and `outAlpha`.
* `self.time` is always live: the wrapper wires `time1.outTime` on creation, so image sequences index by frame with no setup.
* The default Init ships the gamut matrices, transfer functions, blur kernels, `_linearize`, `_prefilter`, `_load_linear_pixels`, `_sample` and `_upload_linear_texture`; edit any of them and both the Compute and Viewport paths pick the change up.
* PIL is optional. Without it the pipeline returns the same magenta fallback the stock node uses.

## In the Compute tab

* Reads: every preset above as `self.<name>` (`self.uvCoord` unpacks to `u, v`; enums read as ints), `self.time` as a `TimeFloat`, plus every input you add.
* Writes: `self.outColor` as an `(r, g, b)` triple and `self.outAlpha` as a float.
* Blessed texture methods, cached per path and settings:
  * `read_texture(path=None)`: load, linearize and pre-filter an image into an `(H, W, 4)` float32 buffer.
  * `sample_texture(buf, u, v, missing=None)`: wrap-aware bilinear lookup returning `(r, g, b, a)`.
  * `composite_layers(layers, opacities, u, v, missing=None)`: alpha-over a stack of image paths at one UV, bottom to top.
  * `write_texture(path, rgba, frame=None)`: write an RGBA buffer to disk as an 8-bit PNG.
* The Viewport tab reads the same presets and the Init namespace, and hands its texture and sampler to the stock `mayaFileTexture` fragment; no custom GLSL or HLSL anywhere.

## Creating one

* `MPyFile.create(name, seed_defaults=True, as_texture=True)`; `set_file_name(path)` and `get_file_name()` mirror the stock node; `reseed_defaults()` restores the shipped sources after an experiment.
* Five shipped templates: File Simple, File Scanline, File Brightness Contrast, File Composite and a Game Of Life Texture.

## Common to all node types

* **Three code tiers.** Init runs once per file open and its names are bare globals in Compute; Compute runs on every dependency-graph pull; Methods is an isolated namespace for `@maya_command`, `@maya_demo` and `@maya_test` defs.
* **Runtime attributes.** `add_input_attr` / `add_output_attr` with 19 wire types, any of them an array, plus `sparse`, `packed`, `enum_names`, min / max / default values. Dirty propagation for these is synthesised for you.
* **Stored variables.** A bare `self.x = ...` in Init or Compute becomes a variable; persistent ones save with the scene, temporary ones live for the session.
* **Instrumentation.** The Log, Watch and Profile tabs read the `watch_enabled`, `profile_enabled` and `deep_profile_enabled` plugs.
* **Round trips.** Export the node as `.mpn` (everything, variable values included), bake it to a `.py` class, or fill in the Metadata tab (authors, version) the gallery shows.
* **Compile to C++.** Convert to a native plug-in: the deterministic transpiler lowers what it can, an AI assist fills only what it could not, and a throwaway mayapy verifies parity against the Python node.
