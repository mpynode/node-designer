# gameOfLifeTex -- compile report

**Source node:** `gameOfLifeTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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
# stateful, so a shader cannot evaluate it from (u, v, t)). The result is ASSIGNED:
# a blessed call left as a bare statement is dropped from the emitted C++.
if self.bakePath != "" and fr != self.bakedFrame:
    baked = self.write_texture(self.bakePath, _gol_rgba(board))
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

## Files

```
build/stages/gameOfLifeTex/1_transpiled.cpp     deterministic transpile (no AI)
build/source/gameOfLifeTex.cpp      SHIPPED
```
