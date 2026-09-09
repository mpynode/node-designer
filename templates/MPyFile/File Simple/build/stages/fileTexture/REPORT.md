# fileTexture -- compile report

**Source node:** `fileTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:38

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **1.75x** over 2 round(s) -- re-measured: unmeasurable under the gate |

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

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.004 ms** -> best **0.002 ms** (**1.75x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.004 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `borderColor (color)`, `brightness (float)`, `contrast (float)`, `preFilter (bool)`, `preFilterRadius (float)`, `uvCoord (float2)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.004 ms | -- | -- |
| 01 | `drop_nd_array_temporaries` | fileTexture is ELEMENTWISE with N=1 -- one texel per compute() -- so the only thing that costs anything is per-evaluation overhead: the generated code built and tore down heap-allocated nd::Array temporaries to move four doubles around, and re-resolved the same texture pointer twice a tick. | 1.80x | 1.75x | 20.1 min | ACCEPTED |
| 02 | `fingerprint_revalidate_texres` | dgdirty marks every plug dirty each tick, so the already-cached texture resolution was torn down and re-resolved on every single evaluation; compare a content fingerprint of the five keying inputs instead and revalidate the pointer in place, and delete the two dead priming writes to the output handles | 1.05x | 0.002 ms | 15.2 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `fingerprint_revalidate_texres` -- predicted 1.05x, **rejected: not faster**. This node is ELEMENTWISE and degenerate: compute() does ONE bilinear texel, so the arithmetic is nothing and the entire measurement is per-access overhead -- opaque Maya accessor calls plus the DG plug machinery. Instrumenting confirmed exactly one compute() per tick, for outAlpha only (outColor is served clean off the same pass), so there is no redundant-invocation win to be had. That leaves the count of Maya calls inside the one compute as the only lever. The existing _texResValid cache never actually hits: the benchmark's dgdirty(node) dirties fileName along with everything else, setDependentsDirty fires invalidateTexRes(), and every tick therefore takes the rebuild branch -- five extra data.inputValue() reads, an MString deep-compare, a nearbyintf, and a scan of the eight-row thread_local memo with its std::string::compare. The dirty flag only says 'might have changed'; an item-2 content fingerprint says 'did change', and on this node the answer is always no. Predicted the fingerprint would remove roughly the memo scan and leave the five reads, so a modest single-digit-percent win.

### Rejected rounds

* `fingerprint_revalidate_texres` -- rejected: not faster. dgdirty marks every plug dirty each tick, so the already-cached texture resolution was torn down and re-resolved on every single evaluation; compare a content fingerprint of the five keying inputs instead and revalidate the pointer in place, and delete the two dead priming writes to the output handles

## Verification

* parity: **pass**  (maxerr 2.980232238769531e-07, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: fileName | authored @maya_test: 1/1 passed
* speed: compiled 0.017 ms vs interpreted 0.187 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/fileTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/fileTexture/2_assisted.cpp       AI filled the unported region(s)
build/stages/fileTexture/3_optimized/00_baseline.cpp
build/stages/fileTexture/3_optimized/01_drop_nd_array_temporaries.cpp
build/stages/fileTexture/3_optimized/02_fingerprint_revalidate_texres.cpp
build/source/fileTexture.cpp      SHIPPED
```
