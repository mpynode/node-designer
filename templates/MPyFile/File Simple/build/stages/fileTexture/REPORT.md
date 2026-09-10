# fileTexture -- compile report

**Source node:** `fileTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 19:36

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **26.48x** over 2 round(s) -- 2 run of max 6, stopped: round 2 gained 1.08x, below the 1.15x needed to continue |

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

Bench scene: VP2 bake of a 1024px source image; noise floor 15 ms; moved per tick: `borderColor (color)`, `brightness (float)`, `contrast (float)`, `preFilter (bool)`, `preFilterRadius (float)`, `uvCoord (float2)`; outputs checked (2 plug(s)).

Baseline **127.935 ms** -> best **4.831 ms** (**26.48x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 gained 1.08x, below the 1.15x needed to continue.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 127.935 ms | -- | -- |
| 01 | `fused_bake_row_pool` | the VP2 bake paid an MString copy, two nd::Array heap temporaries and a memo probe per texel, then spawned 11 threads and zero-filled 16 MB every tick; resolve the buffer once, bake rows against a column table on a persistent pool into a reused buffer | 6.00x | 24.52x | 14.9 min | ACCEPTED |
| 02 | `pipeline_bake_upload` | keep one persistent GPU texture per override and upload each baked band with MTexture::update(region) while the pool bakes the next band, so the 16 MB copy overlaps the bake instead of following it | 1.10x | 26.48x | 12.2 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `fused_bake_row_pool` -- predicted 6.00x, measured **24.52x**. at 1024x1024 the arithmetic is nothing -- per-texel allocation and per-bake thread creation are the whole cost, so hoisting everything that depends only on u or only on v, and keeping threads and the output buffer alive across bakes, leaves only the 16 MB GPU upload and the render
* `pipeline_bake_upload` -- predicted 1.10x, measured **26.48x**. profiling the override showed bake ~0.5 ms, acquireTexture ~2.0 ms and ~2.9 ms of ogsRender overhead we cannot touch; swapping acquireTexture for an in-place update() alone was neutral (the cost is the 16 MB copy, not the allocation), so the remaining lever is to hide the bake under the upload by splitting the grid into 4 row bands and uploading band k-1 on the calling thread while workers bake band k

## Verification

* parity: **pass**  (maxerr 2.980232238769531e-07, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: fileName | authored @maya_test: 1/1 passed
* speed: compiled 0.017 ms vs interpreted 0.186 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/fileTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/fileTexture/2_assisted.cpp       AI filled the unported region(s)
build/stages/fileTexture/3_optimized/00_baseline.cpp
build/stages/fileTexture/3_optimized/01_fused_bake_row_pool.cpp
build/stages/fileTexture/3_optimized/02_pipeline_bake_upload.cpp
build/source/fileTexture.cpp      SHIPPED
```
