# scanlineTex -- compile report

**Source node:** `scanlineTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 15:23

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **2.91x** over 2 round(s) -- 2 run of max 6, stopped: round 2 no-change -- nothing new to compound from |

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

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `bands (int)`, `borderColor (color)`, `frame (time)`, `intensity (float)`, `preFilter (bool)`, `preFilterRadius (float)`, `speed (float)`, `uvCoord (float2)`; outputs checked (2 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 0.009 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **0.009 ms** -> best **0.003 ms** (**2.91x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 no-change -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.009 ms | -- | -- |
| 01 | `scalar_texel` | the ported texel body built about a dozen heap-allocating nd::Array<double> temporaries to do scalar arithmetic on one pixel; the same expression on plain doubles, in the same operation order, removes every allocation from compute() | 1.80x | 2.91x | 16.2 min | ACCEPTED |
| 02 | `single_attribute_plug_gate` | resolve plug.attribute() once and compare MObjects instead of four MPlug-vs-MObject comparisons at the top of compute(); measured as noise, reverted, file left identical to the entry version | 1.04x | -- | 9.3 min | rejected: no change to the source |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `scalar_texel` -- predicted 1.80x, measured **2.91x**. at 6 us per evaluation the node is pure per-call overhead: ~24 malloc/free pairs from nd::from_data/slice/sub/floor/mul/add/sin dominate, then two MString copies and a second texture-cache probe for outSize; nd::sin and nd::floor are std::sin/std::floor on double so a scalar rewrite is bit-identical under /fp:precise and -ffp-contract=off
* `single_attribute_plug_gate` -- predicted 1.04x, **rejected: no change to the source**. candidate is identical to the current best

### Rejected rounds

* `single_attribute_plug_gate` -- rejected: no change to the source. candidate is identical to the current best

## Verification

* parity: **pass**  (maxerr 8.58306884765625e-06, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: fileName | authored @maya_test: 1/1 passed
* speed: compiled 0.017 ms vs interpreted 0.212 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/scanlineTex/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/scanlineTex/2_assisted.cpp       AI filled the unported region(s)
build/stages/scanlineTex/3_optimized/00_baseline.cpp
build/stages/scanlineTex/3_optimized/01_scalar_texel.cpp
build/source/scanlineTex.cpp      SHIPPED
```
