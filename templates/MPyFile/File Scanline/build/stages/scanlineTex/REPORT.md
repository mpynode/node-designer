# scanlineTex -- compile report

**Source node:** `scanlineTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 19:48

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **98.11x** over 3 round(s) -- 3 run of max 6, stopped: round 3 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# Scanline file texture: sample the image through the FRAMEWORK, then
# multiply by an animated horizontal scan band that scrolls with `frame`.
#
# The load is not this template's job -- self.read_texture() /
# self.sample_texture() give it `fileName` decoded out of `colorSpace`, the
# optional pre-filter and the wrap modes, the same as every other mPyFile.
# What this template is ABOUT is the band below.
#
# `bands` = number of bands across V, `speed` = scroll rate, `intensity` = how
# dark the troughs get (0 = flat, 1 = full black between).
buf = self.read_texture()
v = self.uvCoord[1]
r, g, b, a = self.sample_texture(buf, self.uvCoord[0], v)

vv = v - np.floor(v)
s = 0.5 + 0.5 * np.sin((vv * self.bands - self.frame * self.speed) * 2.0 * np.pi)
scan = (1.0 - self.intensity) + self.intensity * s

self.outColor = (r * scan, g * scan, b * scan)
self.outAlpha = a
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: VP2 bake of a 1024px source image; noise floor 15 ms; moved per tick: `bands (int)`, `borderColor (color)`, `frame (time)`, `intensity (float)`, `preFilter (bool)`, `preFilterRadius (float)`, `speed (float)`, `uvCoord (float2)`; outputs checked (2 plug(s)).

Baseline **578.680 ms** -> best **5.898 ms** (**98.11x**).

Rounds: **3** run of at most 6; the loop stopped because round 3 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 578.680 ms | -- | -- |
| 01 | `scalar_texel_row_scan` | replace the per-texel nd::Array chain with scalar math, resolve the texture once per bake, compute the sine band once per row (it depends only on v), and reuse the 16 MB bake buffer across bakes | 15.00x | 71.88x | 8.5 min | ACCEPTED |
| 02 | `persistent_bake_pool` | replace the per-bake std::thread spawn/join of 12 workers with a persistent per-override condvar pool and a dynamic 8-row chunk cursor; the bake itself was cheap, creating the threads was the cost | 1.50x | 98.11x | 13.1 min | ACCEPTED |
| 03 | `column_row_sampler_tables` | hoist the sampler's per-column (u, x0, tx) and per-row (y0, ty) work out of the 1M-texel bake loop as exact identities, so the corner-grid fast path is a gather, three double multiplies and a store | 1.10x | 6.028 ms | 18.3 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `scalar_texel_row_scan` -- predicted 15.00x, measured **71.88x**. the 1M-texel VP2 bake was paying ~8 heap allocations plus a string-compare memo lookup plus a sin() per texel for a result that is a pure function of the row; the remaining bake time was dominated by page-faulting a fresh 16 MB std::vector on the calling thread every bake
* `persistent_bake_pool` -- predicted 1.50x, measured **98.11x**. instrumented split on the Windows/MSVC box was bake 3-5 ms, acquireTexture ~1.7 ms, ogsRender ~3 ms; 1M texels on 12 threads should take well under 1 ms, so most of the bake number had to be thread creation + equal-block stragglers. Sleeping workers woken by generation counter, caller participating, rows claimed dynamically, should collapse it
* `column_row_sampler_tables` -- predicted 1.10x, **rejected: not faster**. the bake was ~0.7 ms of a 5.7 ms tick on 24 threads; each texel redid a double division, two clamp wraps, two float->int casts and the tx/ty tests that depend on x or y alone, so tabling them per bake should roughly halve the bake. The upload (MTextureManager::acquireTexture of a 16 MB RGBA32F texture, ~1.7 ms) and the ogsRender pipeline (~3 ms) are outside the node's arithmetic and set the floor

### Rejected rounds

* `column_row_sampler_tables` -- rejected: not faster. hoist the sampler's per-column (u, x0, tx) and per-row (y0, ty) work out of the 1M-texel bake loop as exact identities, so the corner-grid fast path is a gather, three double multiplies and a store

## Verification

* parity: **pass**  (maxerr 8.58306884765625e-06, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: fileName | authored @maya_test: 1/1 passed
* speed: compiled 0.018 ms vs interpreted 0.210 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/scanlineTex/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/scanlineTex/2_assisted.cpp       AI filled the unported region(s)
build/stages/scanlineTex/3_optimized/00_baseline.cpp
build/stages/scanlineTex/3_optimized/01_scalar_texel_row_scan.cpp
build/stages/scanlineTex/3_optimized/02_persistent_bake_pool.cpp
build/stages/scanlineTex/3_optimized/03_column_row_sampler_tables.cpp
build/source/scanlineTex.cpp      SHIPPED
```
