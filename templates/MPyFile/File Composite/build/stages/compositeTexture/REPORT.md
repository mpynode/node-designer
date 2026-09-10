# compositeTexture -- compile report

**Source node:** `compositeTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 15:33

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **138.44x** over 4 round(s) -- 4 run of max 6, stopped: round 4 no-change -- nothing new to compound from |

## The Python this was generated from

```python
# Composite texture -- Compute tier.
#
# AN ARBITRARY NUMBER OF LAYERS, bottom (`layers[0]`) to top, alpha-over at the
# sampled point. `layers` and `opacities` are ARRAY plugs, so the stack is as
# deep as you make it -- add an element, get a layer. Every layer is loaded by
# the SAME framework call the File Simple template uses -- self.read_texture
# (path) -- so all of them are decoded out of `colorSpace` and pre-filtered
# identically. Nothing here knows how to read a file; it only knows how to stack.
#
# The loop bound is the RUNTIME array length, and it stays that way when this
# node is compiled: `layers` lifts to a std::vector<std::string> and the C++ is
# the same `for` over `.size()`. Nothing about the layer count is baked in.
#
# AN UNSET SLOT DROPS OUT BY ITSELF. A blank or unresolvable path makes
# read_texture() return None, and every sample here passes
# `missing=(0.0, 0.0, 0.0, 0.0)` -- so that slot samples as fully transparent
# and contributes nothing, instead of the OPAQUE magenta "no image" sentinel
# that would cover the layers underneath. Drop the argument (or pass
# missing=None) to get the magenta back, which is still what you want while
# authoring: it makes a typo'd path impossible to miss.
#
# An `opacities` element is a real weight rather than an on/off switch -- 0 still
# removes a layer exactly, but you no longer have to zero a slot just because it
# has no file yet. A layer with NO matching opacity element defaults to 1.0: a
# path you bothered to set is on unless you say otherwise.
#
# The result is composited over black and comes out premultiplied, which is
# what an unlit surfaceShader wants.
cr, cg, cb, ca = self.composite_layers(
    self.layers, self.opacities, self.uvCoord[0], self.uvCoord[1],
    missing=(0.0, 0.0, 0.0, 0.0))

self.outColor = (cr, cg, cb)
self.outAlpha = ca
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `borderColor (color)`, `opacities[0] (float)`, `preFilterRadius (float)`, `uvCoord (float2)`; outputs checked (2 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 0.346 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **0.346 ms** -> best **0.003 ms** (**138.44x**).

Rounds: **4** run of at most 6; the loop stopped because round 4 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.346 ms | -- | -- |
| 01 | `lazy_opacity_read` | read only the opacity elements the layer stack can use (logical index < layers.size()) instead of walking all 20000 through the Maya array handle | 10.00x | 76.91x | 9.4 min | ACCEPTED |
| 02 | `alloc_free_texel` | composite the one sampled texel straight from the MString/float inputs instead of marshalling them through std::string vectors, nd::Array temporaries and nd::slice views | 1.40x | 111.65x | 16.2 min | ACCEPTED |
| 03 | `fuse_handles_lazy_reads` | Composite straight off the array handles -- no vector/MString marshalling -- and read uvCoord/wrapMode/borderColor only for a layer that actually loaded. | 1.15x | 138.44x | 13.0 min | ACCEPTED |
| 04 | `noise_floor_no_change` | compute() is ~0.1 us of a ~2.1 us pull; the rest is Maya plug evaluation + harness overhead, so no edit inside the file can move the number and the file is left byte-identical | 1.02x | -- | 10.3 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `lazy_opacity_read` -- predicted 10.00x, measured **76.91x**. the composite consumes ops[i] only for i < layers.size() (missing element -> 1.0, surplus ignored), so under the bench's one-layer stack the 20000-element MArrayDataHandle walk (elementIndex/inputValue/asFloat/next per element) is the entire cost; jumpToElement(i) for the handful of needed indices removes it and leaves compute() at Maya's dgdirty+pull floor
* `alloc_free_texel` -- predicted 1.40x, measured **111.65x**. the bench stack is one layer with no image and the memo hits every tick, so compute() is pure marshalling: a dozen heap round-trips (vector<string>, three shared_ptr-backed nd::Array, two slice views, an MString rebuilt from std::string) were ~1.4 us of a ~2.3 us compute(); an allocation-free loop with the identical float->double->float conversion order removes that level of work while every value stays byte-identical. Measured with an in-node steady_clock profile: texel 1400 ns -> 250 ns, compute() 2300 ns -> 1200 ns; harness 0.0036 -> 0.0027 ms. Note: the workspace build.sh/bench.sh are macOS-only (clang -bundle, lipo) and cannot run on this Windows host, so the numbers were taken by compiling the same file with the engine's own MSVC recipe (porter.compile_cpp, /O2 /fp:precise) and running the identical benchmark_node.py invocation against the .mll.
* `fuse_handles_lazy_reads` -- predicted 1.15x, measured **138.44x**. At one layer the compute is a few microseconds of Maya handle traffic, so the two vector allocations, the MString copy and the four input reads the sampler never consumes when no layer loads (two of them moved compound plugs) are most of what sits above the output-write floor; the over arithmetic itself is negligible.
* `noise_floor_no_change` -- predicted 1.02x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `noise_floor_no_change` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**  (maxerr 0.0001678466796875, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: layers | authored @maya_test: 1/1 passed
* speed: compiled 0.021 ms vs interpreted 1.521 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/compositeTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/compositeTexture/2_assisted.cpp       AI filled the unported region(s)
build/stages/compositeTexture/3_optimized/00_baseline.cpp
build/stages/compositeTexture/3_optimized/01_lazy_opacity_read.cpp
build/stages/compositeTexture/3_optimized/02_alloc_free_texel.cpp
build/stages/compositeTexture/3_optimized/03_fuse_handles_lazy_reads.cpp
build/source/compositeTexture.cpp      SHIPPED
```
