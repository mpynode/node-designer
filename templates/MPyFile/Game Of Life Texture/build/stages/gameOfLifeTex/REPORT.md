# gameOfLifeTex -- compile report

**Source node:** `gameOfLifeTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 15:56

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **1.25x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

## The Python this was generated from

```python
# Conway's Game of Life as a procedural texture. A bounded numpy board (no
# wrap) advances one step per frame and is sampled per-UV: white = alive,
# black = dead. Drive `frame` (auto-wired to the timeline) to animate; set
# `reset` True to reseed `density` random cells; `width`/`height` set the grid.
# Spelled to LOWER to C++ (it must: nd::MT19937 reproduces numpy's RandomState
# stream bit-for-bit, so the compiled node seeds the SAME board -- an AI port
# would substitute a different generator and diverge). That means: the advance is
# inline rather than `_gol_advance(self)` (the node object cannot be passed into a
# helper), the first-run seed is hasattr-guarded (persistent state must be written
# before it is read), uvCoord is indexed rather than tuple-unpacked, and the
# sampled cell is float()-ed (an indexed element is a rank-0 array, not a scalar).
hh = max(1, int(self.height))
ww = max(1, int(self.width))
fr = float(self.frame)
dens = float(self.density)
reset_on = int(self.reset) == 1
if not hasattr(self, "board"):
    self.board = _gol_seed(hh, ww, dens, seed=int(fr) if reset_on else 0)
    self.lastFrame = fr
    self.bakedFrame = -1.0
board = self.board
shape_bad = (int(board.shape[0]) != hh or int(board.shape[1]) != ww)
if shape_bad or fr != self.lastFrame:
    if reset_on or shape_bad:
        # While reset is held, vary the seed by frame so the random startup is
        # live (density edits are visible); else seed deterministically.
        board = _gol_seed(hh, ww, dens, seed=int(fr) if reset_on else 0)
    else:
        board = _gol_step(board)
    self.board = board
    self.lastFrame = fr
# Bake the frame for the OSL/Arnold tier, which samples the file (Game of Life is
# stateful, so a shader cannot evaluate it from (u, v, t)). The third argument
# writes a FRAME-STAMPED name (bakePath "x.png" -> "x.0007.png"): Arnold's texture
# system caches by filename and never re-stats, so re-baking one fixed path leaves
# a render showing whichever frame it read first. The result is ASSIGNED (a blessed
# call left as a bare statement is dropped from the emitted C++), and bakedFrame
# advances only on SUCCESS so an unwritable path is retried rather than marked done.
if self.bakePath != "" and fr != self.bakedFrame:
    baked = self.write_texture(self.bakePath, _gol_rgba(board), fr)
    if baked:
        self.bakedFrame = fr
h, w = int(board.shape[0]), int(board.shape[1])
u = self.uvCoord[0]
v = self.uvCoord[1]
uu = u - np.floor(u)
vv = v - np.floor(v)
cx = min(w - 1, int(uu * w))
cy = min(h - 1, int((1.0 - vv) * h))
alive = 1.0 if float(board[cy, cx]) > 0.5 else 0.0
self.outColor = (alive, alive, alive)
self.outAlpha = 1.0
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `density (float)`, `frame (time)`, `height (int)`, `uvCoord (float2)`, `width (int)`; outputs skipped (node draws random numbers); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 0.008 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **0.008 ms** -> best **0.006 ms** (**1.25x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.008 ms | -- | -- |
| 01 | `scalar_texel` | Replace the nd::Array temporaries on the per-texel path with scalar math and a fused seed/step kernel, so one texel costs a floor, two multiplies and a table lookup instead of ~70 heap allocations. | 1.50x | 1.25x | 19.6 min | ACCEPTED |
| 02 | `cache_rng_stream` | cache the RandomState(seed) draw stream per instance so a reseed costs one compare per cell instead of a 624-word MT19937 init and twist, and rewrite the board in place instead of reallocating it | 1.50x | 0.006 ms | 12.7 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `cache_rng_stream` -- predicted 1.50x, **rejected: not faster**. incumbent under the noise floor: second measurement 0.006 ms did not confirm 0.004 ms

### Rejected rounds

* `cache_rng_stream` -- rejected: not faster. incumbent under the noise floor: second measurement 0.006 ms did not confirm 0.004 ms

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0058823529411764705)
* verified with 1 geo/string input(s) left at default (unwired, could not be synthesized): bakePath | authored @maya_test: 1/1 passed
* speed: compiled 0.030 ms vs interpreted 0.469 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/gameOfLifeTex/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/gameOfLifeTex/2_assisted.cpp       AI filled the unported region(s)
build/stages/gameOfLifeTex/3_optimized/00_baseline.cpp
build/stages/gameOfLifeTex/3_optimized/01_scalar_texel.cpp
build/stages/gameOfLifeTex/3_optimized/02_cache_rng_stream.cpp
build/source/gameOfLifeTex.cpp      SHIPPED
```
