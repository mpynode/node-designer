# animatedText -- compile report

**Source node:** `animatedText`  ·  **Base:** `MPxLocatorNode`  ·  **Generated:** 2026-09-10 14:37

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) -- 0 run of max 6, stopped: baseline could not be benchmarked |

## The Python this was generated from

```python
# Animated rainbow text gizmo, driven by the WALL CLOCK only. self.wallclock is
# seconds since the epoch (time.time()) and is identical in the compiled node,
# so the motion is the same at idle, while scrubbing and in every playback
# mode: frame rate and scene time units never change its speed. Timeline
# animation is opt-in -- an expression gets it by reading self.time (or a
# time plug); this one deliberately does not. `loopDuration` is wall-clock
# seconds per loop: 1 = one loop per second, 2 = two seconds per loop,
# -1 = one loop per second in reverse, 0 = frozen. auto_refresh keeps the
# gizmo repainting between the redraws Maya would otherwise never issue.
self.auto_refresh = True

raw     = getattr(self, "displayText", "")
msg     = raw if (raw and str(raw).strip()) else "MPyNode!"
chars   = list(str(msg))
n       = len(chars)
idx     = np.arange(n, dtype=np.float64)

dur     = float(self.loopDuration)
speed   = (1.0 / dur) if dur != 0.0 else 0.0  # loops per wall-clock second
cyc     = self.wallclock * speed              # loop position; its fraction is the phase
phase   = TWO_PI * cyc

spacing = self.spacing
wave    = self.waveHeight

# layout along X with a slow one-per-loop horizontal sway
xs        = (idx - (n - 1) / 2.0) * spacing + 1.2 * np.sin(phase)
ys        = wave * np.sin(idx * 0.7 - 2.0 * phase)     # 2 travelling waves / loop
zs        = 0.5 * np.cos(idx * 0.5 - 1.0 * phase)
positions = np.stack([xs, ys, zs], axis=1).astype(np.float32)

# scrolling rainbow (hue cycles once per loop + per-glyph offset)
rgb    = hue2rgb(idx / max(n, 1) + cyc)
colors = np.concatenate([rgb, np.ones((n, 1))], axis=1).astype(np.float32)
if bool(getattr(self, "selected", False)):
    colors[:] = (1.0, 1.0, 1.0, 1.0)          # flash white while selected

# Text is drawn in the default LOCAL space, so `size` is an OBJECT-space
# glyph height (world units, ~half the 1.3 letter spacing) -- NOT pixels.
# The locator auto-scales the bitmap font from the object's on-screen size,
# so the letters shrink as you zoom the camera out (and grow with the
# transform scale) instead of overlapping. Switch to constant pixels by
# passing screen_space=True to DrawText.
sizes = (0.55 + 0.22 * np.sin(idx * 0.8 - 3.0 * phase)).astype(np.float32)

# twinkling sparkle points above each glyph
sp = positions.copy()
sp[:, 1] += 1.7 + 0.35 * np.sin(idx * 1.3 + 2.0 * phase)
psize = (5.0 + 6.0 * np.abs(np.sin(idx * 0.9 + 2.0 * phase))).astype(np.float32)

# flowing sine ribbon under the text. DrawCurve takes the POLYLINE and does the
# pts[:-1] / pts[1:] segment split itself -- including trimming the per-vertex
# colours to the segment count, which is easy to forget by hand and silently
# rejects the whole buffer when the lengths disagree.
m    = 64
lx   = np.linspace(xs.min() - 1.0, xs.max() + 1.0, m)
ly   = 0.7 * np.sin(lx * 0.8 + 1.0 * phase) - 2.4
pts  = np.stack([lx, ly, np.zeros(m)], axis=1).astype(np.float32)
lrgb = hue2rgb(lx * 0.04 + cyc)
lcol = np.concatenate([lrgb, np.ones((m, 1))], axis=1).astype(np.float32)

# pulsing circle halo behind the message
R = 6.0 + 0.6 * np.sin(phase)

# ONE drawing, composed with `+`. Each drawable knows which buffer it belongs to,
# so there are no parallel arrays to keep in sync and no "kinds"/"filled" lists
# to line up by hand.
self.draw = (DrawText(chars, positions, color=colors, size=sizes)
             + DrawPoints(sp, color=colors, size=psize)
             + DrawCurve(pts, color=lcol)
             + DrawCircle(center=(0.0, 0.0, -1.0), radius=R,
                          color=hue2rgb(np.array([cyc]))))
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
build/stages/animatedText/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/animatedText/3_optimized/00_baseline.cpp
build/source/animatedText.cpp      SHIPPED
```
