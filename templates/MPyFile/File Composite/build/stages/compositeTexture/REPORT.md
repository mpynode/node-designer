# compositeTexture -- compile report

**Source node:** `compositeTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 20:40

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **95.23x** over 2 round(s) -- re-measured: unmeasurable under the gate |

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

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.209 ms** -> best **0.002 ms** (**95.23x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.345 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `borderColor (color)`, `opacities[0] (float)`, `preFilterRadius (float)`, `uvCoord (float2)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.209 ms | -- | -- |
| 01 | `dense_multi_read_no_temps` | this node is not query-shaped and barely touches its layer stack -- the entire measured cost is reading one 20000-element float multi and copying it three times, so prove the multi is dense to drop 20000 elementIndex() calls and collapse the three whole-array temporaries into one | 1.45x | 1.59x | 19.9 min | ACCEPTED |
| 02 | `bound_opacity_read_to_layers` | the compositor only ever indexes ops[i] for i < layer count, so reading the whole opacities multi is dead work -- bound the read at the layer count and address those few logical indices directly instead of walking the array | 20.00x | 95.23x | 12.4 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `bound_opacity_read_to_layers` -- predicted 20.00x, measured **95.23x**. this node is ELEMENTWISE with a degenerate output of ONE texel: nd_tex_composite_layers loops `for i < nPaths` and reads `(i < nOps) ? ops[i] : 1.0`, and the bench drives layers with 1 element and opacities with 20000. So 19999 of the 20000 MArrayDataHandle inputValue()/next() pairs feed a value no expression can observe. Removing them should leave only Maya's dirty/pull overhead and a single bilinear sample; I predicted the read was essentially the entire 0.132 ms.

## Verification

* parity: **pass**
* reads an image file (MImage::readFromFile); output depends on external file state -- pointwise parity skipped (build verified to compile + load) | authored @maya_test: 1/1 passed

## Files

```
build/stages/compositeTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/compositeTexture/2_assisted.cpp       AI filled the unported region(s)
build/stages/compositeTexture/3_optimized/00_baseline.cpp
build/stages/compositeTexture/3_optimized/01_dense_multi_read_no_temps.cpp
build/stages/compositeTexture/3_optimized/02_bound_opacity_read_to_layers.cpp
build/source/compositeTexture.cpp      SHIPPED
```
