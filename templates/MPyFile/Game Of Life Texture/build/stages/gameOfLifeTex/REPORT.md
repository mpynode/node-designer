# gameOfLifeTex -- compile report

**Source node:** `gameOfLifeTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-09 19:27

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **2.56x** over 2 round(s) -- 2 run of max 6, stopped: round 2 not-faster -- nothing new to compound from |

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

Bench scene: VP2 bake of a 4096px source image; noise floor 15 ms; moved per tick: `density (float)`, `frame (time)`, `height (int)`, `uvCoord (float2)`, `width (int)`; outputs skipped (node draws random numbers); accepts re-timed against the incumbent on the smallest scene (VP2 bake of a 1024px source image) and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 4.711 ms is below the 15 ms noise floor even at the largest bench scene (geo=bake array=4096); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **4.711 ms** -> best **1.838 ms** (**2.56x**).

Rounds: **2** run of at most 6; the loop stopped because round 2 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 4.711 ms | -- | -- |
| 01 | `direct_board_bake` | the VP2 bake sampled the board through the generic per-texel port (mutex, std::string, ~10 nd::Array temporaries per texel) and spawned min(12, h) threads per frame; it now reads the board buffer directly, serially, with the same float-narrowed uv -> floor -> truncate -> min-clamp -> >0.5 math | 1.50x | 2.56x | 7.6 min | ACCEPTED |
| 02 | `flat_board_no_nd_temporaries` | the bench grid is k x k with k in the tens, so the frame cost is fixed overhead: store the board as a flat byte vector and seed/step/sample it directly, with one mutex acquisition, cached fragment parameter names and sampler state, and MPlug(attr) reads instead of six findPlug name lookups | 1.06x | 1.845 ms | 10.5 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `direct_board_bake` -- predicted 1.50x, measured **2.56x**. the harness drives width = height = k (2..12), so the grid is under 150 cells and the per-frame cost was thread creation/join plus per-texel allocation overhead, not arithmetic; removing both takes the node side of the bake to the noise floor and leaves only ogsRender's fixed cost
* `flat_board_no_nd_temporaries` -- predicted 1.06x, **rejected: not faster**. nd_texel's prime call built a std::string, ~10 nd::Array temporaries (bit-packed vector<bool> via shared_ptr) and locked the mutex twice per frame; updateShader re-scanned shader.parameterList and re-acquired a sampler state every frame; removing all of it should shave ~0.1 ms off a ~1.9 ms ogsRender tick whose remainder is Maya's own render cost

### Rejected rounds

* `flat_board_no_nd_temporaries` -- rejected: not faster. the bench grid is k x k with k in the tens, so the frame cost is fixed overhead: store the board as a flat byte vector and seed/step/sample it directly, with one mutex acquisition, cached fragment parameter names and sampler state, and MPlug(attr) reads instead of six findPlug name lookups

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0058823529411764705)
* verified with 1 geo/string input(s) left at default (unwired, could not be synthesized): bakePath | authored @maya_test: 1/1 passed
* speed: compiled 0.025 ms vs interpreted 0.316 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/gameOfLifeTex/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/gameOfLifeTex/2_assisted.cpp       AI filled the unported region(s)
build/stages/gameOfLifeTex/3_optimized/00_baseline.cpp
build/stages/gameOfLifeTex/3_optimized/01_direct_board_bake.cpp
build/stages/gameOfLifeTex/3_optimized/02_flat_board_no_nd_temporaries.cpp
build/source/gameOfLifeTex.cpp      SHIPPED
```
