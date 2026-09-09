# scanlineTex -- compile report

**Source node:** `scanlineTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:38

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **1.95x** over 2 round(s) -- re-measured: unmeasurable under the gate |

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

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.004 ms** -> best **0.002 ms** (**1.95x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.007 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `bands (int)`, `borderColor (color)`, `frame (time)`, `intensity (float)`, `preFilter (bool)`, `preFilterRadius (float)`, `speed (float)`, `uvCoord (float2)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.004 ms | -- | -- |
| 01 | `scalarize_0d_arrays` | this texture node computes ONE texel per compute(), but the ported band math ran through nd::Array temporaries that were all 0-d -- roughly ten heap allocations to hold one double each; replacing them with plain double arithmetic (same std::sin/std::floor, same order, same type) cut the measured tick nearly in half | 3.00x | 1.78x | 16.6 min | ACCEPTED |
| 02 | `pod_tls_texmemo` | drop the std::string out of the thread_local texture memo so the row array is trivially destructible and clang can address it as a plain TLS offset instead of a guarded wrapper call, and stop deep-copying the MString path into nd_texel on every texel | 1.15x | 1.95x | 12.1 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `scalarize_0d_arrays` -- predicted 3.00x, measured **1.78x**. the node is ELEMENTWISE with N=1, so there is no algorithm to improve and no acceleration structure to build -- per-access overhead is the entire cost. At 4.2 us a tick, a shared_ptr<vector<double>> allocation per nd:: op is the dominant term, not the sin() or the bilinear sample.
* `pod_tls_texmemo` -- predicted 1.15x, measured **1.95x**. this node is ELEMENTWISE with an output of exactly ONE texel per compute -- no array inputs, no geometry inputs -- so there is no O(N) pass and no scan to accelerate. The only per-evaluation costs inside the file are the 13 data.inputValue() reads, the texture-memo probe and one bilinear tap. The memo was the one place doing real avoidable work: NdTexMemo held a std::string, which makes `static thread_local NdTexMemo memo[8]` non-trivially-destructible, forcing a __cxa_thread_atexit registration and an initialisation-guard check behind a TLS wrapper call on EVERY access -- overhead sitting in front of a probe whose entire purpose is to be cheaper than the std::map lookup it guards. Making the row POD (fixed char buffer) makes the block constant-initialised and the access a direct offset. Separately, nd_texel took `MString in_aFileName` BY VALUE, a malloc+strcpy+free per texel -- the exact copy the callsite comment two frames up says it had already eliminated at the datablock end.

## Verification

* parity: **pass**  (maxerr 8.58306884765625e-06, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: fileName | authored @maya_test: 1/1 passed
* speed: compiled 0.018 ms vs interpreted 0.232 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/scanlineTex/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/scanlineTex/2_assisted.cpp       AI filled the unported region(s)
build/stages/scanlineTex/3_optimized/00_baseline.cpp
build/stages/scanlineTex/3_optimized/01_scalarize_0d_arrays.cpp
build/stages/scanlineTex/3_optimized/02_pod_tls_texmemo.cpp
build/source/scanlineTex.cpp      SHIPPED
```
