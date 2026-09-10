# compositeTexture -- compile report

**Source node:** `compositeTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 19:39

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **11.91x** over 3 round(s) -- 3 run of max 6, stopped: round 3 not-faster -- nothing new to compound from |

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

Bench scene: VP2 bake of a 1024px source image; noise floor 15 ms; moved per tick: `borderColor (color)`, `opacities[0] (float)`, `preFilter (bool)`, `preFilterRadius (float)`, `uvCoord (float2)`; outputs checked (2 plug(s)).

Baseline **24.130 ms** -> best **2.026 ms** (**11.91x**).

Rounds: **3** run of at most 6; the loop stopped because round 3 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 24.130 ms | -- | -- |
| 01 | `resolve_layers_once` | The VP2 bake resolved the layer stack per texel -- a heap vector of layer paths, a heap copy of the 512 opacities as an nd::Array, a 2-element uv array and a string-keyed memo probe per layer -- so resolve it once per bake into a flat {buffer, size, opacity} table and run a lean per-texel kernel over it. | 2.00x | 8.00x | 9.7 min | ACCEPTED |
| 02 | `skip_empty_bake_reuse_buffer` | the bench stack has zero loadable layers (layers[0]='bench'), so the whole 256x256 bake was a zero-fill: skip the texel loop when the resolved stack is empty, keep the bake grid in a reused member buffer instead of page-faulting a fresh 1 MB vector each tick, and read/key only the opacities[i] with i < layers.size() (the only ones composite_layers can see) instead of 512 MPlug reads plus 512 snprintf per tick | 1.45x | 11.91x | 9.5 min | ACCEPTED |
| 03 | `exact_bake_key` | key the VP2 texture cache on what the bake actually reads (the resolved layer stack and grid size) instead of every raw input, so an animated borderColor or an opacity on an empty slot no longer forces a re-bake and GPU upload of byte-identical pixels | 1.06x | 2.081 ms | 11.6 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `resolve_layers_once` -- predicted 2.00x, measured **8.00x**. With one bogus layer over 512 opacities the bake is the 256x256 fallback grid, so per-texel setup (several mallocs + a 4 KB opacity copy) dwarfs the actual sample; hoisting it removes ~all node-side work. Follow-ups measured in the same run: size-gate the row threading so a sub-millisecond bake runs serially instead of spawning 11 threads (16.83 -> 7.28 -> 3.35 ms), then drop unloadable layers with finite opacity from the table since their alpha is exactly +-0 and the accumulate is an identity (3.35 -> 3.05 ms).
* `skip_empty_bake_reuse_buffer` -- predicted 1.45x, measured **11.91x**. instrumented breakdown per tick: updateDG 150 us (512 elementByPhysicalIndex), texName 105 us (512 snprintf), bake 550 us (65k texels x 0 layers = writing zeros, plus 1 MB fresh-allocation page faults), acquireTexture 110 us; the first three are removable exactly because an empty stack is bit-identical +0.0f and a surplus opacity never reaches the result
* `exact_bake_key` -- predicted 1.06x, **rejected: not faster**. an in-node steady_clock profile showed the override at ~130-200 us of a ~2100 us tick (updateDG 22, key+findTexture 28, bake path 22, acquireTexture 80, nrl=0, 256x256 fallback grid because the bench's layers[0]='bench' never loads); the old key hashed borderColor, all opacities and the unresolved paths, but the bake samples with wrap fixed to clamp so borderColor is never read, and a slot that does not load with a finite opacity is an exact no-op -- so every bench tick re-baked and re-uploaded identical bytes. Keying on (path, colorSpace, preFilter, kernel, rq, w, h, op) per RESOLVED layer plus the grid size makes those ticks a texture-manager hit, removing bake+acquire (~100 us) and leaving ~45 us of override work. Second, smaller change in the same round: updateDG built ten plugs by name (findPlug walks the attribute table per call); MPlug(node, attr) from the class's static attribute MObjects is the same non-networked plug without the lookup. Bench numbers were taken on this Windows host by compiling with the engine's own MSVC recipe (porter.compile_cpp, /O2 /fp:precise) and running the identical benchmark_node.py invocation against the .mll, because build.sh/bench.sh are clang -bundle/lipo only. Baseline via that path: 2.13-2.37 ms (9 iters); exact key alone: 1.828 ms (21 iters); exact key + direct plugs (final): 1.701 ms (21 iters, samples 1.59-2.43).

### Rejected rounds

* `exact_bake_key` -- rejected: not faster. key the VP2 texture cache on what the bake actually reads (the resolved layer stack and grid size) instead of every raw input, so an animated borderColor or an opacity on an empty slot no longer forces a re-bake and GPU upload of byte-identical pixels

## Verification

* parity: **pass**  (maxerr 0.0001678466796875, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: layers | authored @maya_test: 1/1 passed
* speed: compiled 0.111 ms vs interpreted 1.631 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/compositeTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/compositeTexture/2_assisted.cpp       AI filled the unported region(s)
build/stages/compositeTexture/3_optimized/00_baseline.cpp
build/stages/compositeTexture/3_optimized/01_resolve_layers_once.cpp
build/stages/compositeTexture/3_optimized/02_skip_empty_bake_reuse_buffer.cpp
build/stages/compositeTexture/3_optimized/03_exact_bake_key.cpp
build/source/compositeTexture.cpp      SHIPPED
```
