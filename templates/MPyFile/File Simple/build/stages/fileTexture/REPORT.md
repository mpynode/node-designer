# fileTexture -- compile report

**Source node:** `fileTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 15:46

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **1.57x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# File texture with a brightness / contrast filter.
#
# self.read_texture()    load `fileName`, decode it out of `colorSpace`, apply
#                        the optional pre-filter. Returns a float32 HxWx4
#                        SCENE-LINEAR buffer (cached), or None when the file is
#                        missing / unreadable -- but first it falls back to the
#                        node's baked `embeddedImage` bytes, so a node with no
#                        file on disk still renders.
# self.sample_texture()  wrap-aware BILINEAR lookup into that buffer ->
#                        (r, g, b, a). Returns magenta when the buffer is None,
#                        so a missing file never raises.
#
# Both are framework methods shared by every mPyFile -- the same pair the
# built-in default uses -- so this template stays about the GRADE, not about
# how to read a PNG.
buf = self.read_texture()
r, g, b, a = self.sample_texture(buf, self.uvCoord[0], self.uvCoord[1])

# brightness scales about black, contrast about mid-grey, then clamp.
bright = self.brightness
contrast = self.contrast
r = min(1.0, max(0.0, (r * bright - 0.5) * contrast + 0.5))
g = min(1.0, max(0.0, (g * bright - 0.5) * contrast + 0.5))
b = min(1.0, max(0.0, (b * bright - 0.5) * contrast + 0.5))

self.outColor = (r, g, b)
self.outAlpha = a
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `borderColor (color)`, `brightness (float)`, `contrast (float)`, `preFilter (bool)`, `preFilterRadius (float)`, `uvCoord (float2)`; outputs checked (2 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 0.004 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **0.004 ms** -> best **0.002 ms** (**1.57x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.004 ms | -- | -- |
| 01 | `scalar_texel_lazy_inputs` | a one-texel node is all per-access overhead: drop the nd::Array temporaries the port used to carry five numbers, and read only the inputs the current branch can see | 1.60x | 1.57x | 14.0 min | ACCEPTED |
| 02 | `inline_no_image_texel` | the benchmark leaves fileName empty, so compute() is sixteen Maya API calls around three double multiplies; resolve the plug attribute once and grade the magenta sentinel inline instead of through the 20-argument nd_texel call | 1.05x | 0.002 ms | 11.6 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `inline_no_image_texel` -- predicted 1.05x, **rejected: not faster**. at 1.9 us per tick the timed region is MPlug.asMDataHandle overhead plus datablock reads/writes, so the only removable work is the four MPlug::operator!=(MObject) attribute resolutions (now one MPlug::attribute() and four MObject compares) and the nd_texel call frame with its dead nd_tex_sample dispatch on a null image

### Rejected rounds

* `inline_no_image_texel` -- rejected: not faster. the benchmark leaves fileName empty, so compute() is sixteen Maya API calls around three double multiplies; resolve the plug attribute once and grade the magenta sentinel inline instead of through the 20-argument nd_texel call

## Verification

* parity: **pass**  (maxerr 2.980232238769531e-07, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: fileName | authored @maya_test: 1/1 passed
* speed: compiled 0.016 ms vs interpreted 0.184 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/fileTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/fileTexture/2_assisted.cpp       AI filled the unported region(s)
build/stages/fileTexture/3_optimized/00_baseline.cpp
build/stages/fileTexture/3_optimized/01_scalar_texel_lazy_inputs.cpp
build/stages/fileTexture/3_optimized/02_inline_no_image_texel.cpp
build/source/fileTexture.cpp      SHIPPED
```
