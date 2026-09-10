# animatedSelection -- compile report

**Source node:** `animatedSelection`  ·  **Base:** `MPxLocatorNode`  ·  **Generated:** 2026-09-10 14:36

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) -- 0 run of max 6, stopped: baseline could not be benchmarked |

## The Python this was generated from

```python
# Polygon-shading showcase cube: spins on the WALL CLOCK (self.wallclock --
# seconds since the epoch, never the timeline), "pops" on mouse HOVER (an
# elastic tween on the same clock), and recolours via the `color_mode`
# enum. Selection tints the FILL only (highlight_fill) while the wireframe
# keeps its own colour (highlight_wire=False) -- per-aspect highlighting.
# Animation state lives in getattr-defaulted vars, so it needs no seeding.
hovered = bool(self.hovered)
now = float(self.wallclock)
duration = max(self.popDuration, 1e-3)
amount = self.popAmount

prev = bool(getattr(self, "prev_hovered", False))
anim_start = float(getattr(self, "anim_start_t", 0.0))
anim_from = float(getattr(self, "anim_from", 0.0))
anim_to = float(getattr(self, "anim_to", 0.0))

elapsed = (now - anim_start) / duration
elapsed = 0.0 if elapsed < 0.0 else (1.0 if elapsed > 1.0 else elapsed)
current_pop = anim_from + (anim_to - anim_from) * elastic_in_out(elapsed)

if hovered != prev:
    self.anim_start_t = now
    self.anim_from = current_pop
    self.anim_to = 1.0 if hovered else 0.0
    self.prev_hovered = hovered
    elapsed = 0.0

scale = 1.0 + amount * current_pop

# Spin on the wall clock at the user-tunable spinSpeed (radians per second).
ang = self.wallclock * self.spinSpeed
spun = ((cube_pts * scale) @ rot_y(ang).T) @ rot_x(ang * 0.6).T

# The four fill modes are named after the buffer key each one drives, so the
# enum maps straight onto a DrawMesh keyword. They are mutually exclusive --
# passing two raises instead of silently letting the renderer pick by
# precedence.
mode = self.color_mode.name()
if mode == "face":
    fill = {"color": FACE_HUES}                       # flat, per face
elif mode == "vertex":
    fill = {"vertex_colors": VERTEX_COLORS}           # smooth, per point
elif mode == "face_vertex":
    fill = {"face_vertex_colors": FACE_VERTEX_COLORS}  # per corner
else:  # "uniform"
    fill = {"uniform_color": (0.45, 0.85, 1.0, 0.6)}  # one setColor call

# highlight_fill/highlight_wire are per-ASPECT: selection tints the fill but
# leaves the wireframe its own colour. outline_boundary_only=False keeps every
# cube edge, matching the wire overlay this demo is showing off.
cube = DrawMesh(spun, cube_cnt, cube_idx,
                cull_backfaces=True, precise_hover=True,
                highlight_fill=True, highlight_wire=False, **fill)

if self.show_wireframe:
    cube = cube.outlined((0.04, 0.04, 0.06, 1.0), width=self.wire_width, boundary_only=False)

self.draw = cube
self.auto_highlight = False      # we drive highlighting ourselves
# Keep repainting while the pop tween runs AND while the cube spins: on the wall
# clock nothing else ever redraws it between interactions (a still cube with
# spinSpeed 0 rests once its tween settles).
self.auto_refresh = bool(elapsed < 1.0) or float(self.spinSpeed) != 0.0
```

## Optimization

Parity gate: not exercised -- no candidate reached the parity check (the baseline was unmeasurable or no round compiled).

Bench scene: geo density 40 / array length 512; noise floor 15 ms.

Baseline **--** -> best **--** (**1.00x**).

Rounds: **0** run of at most 6; the loop stopped because baseline could not be benchmarked.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | -- | -- | -- |

## Verification

* parity: **pass**
* no scalar outputs to compare -- pointwise parity skipped (vacuous check) | authored @maya_test: 1/1 passed

## Files

```
build/stages/animatedSelection/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/animatedSelection/2_assisted.cpp       AI filled the unported region(s)
build/stages/animatedSelection/3_optimized/00_baseline.cpp
build/source/animatedSelection.cpp      SHIPPED
```
