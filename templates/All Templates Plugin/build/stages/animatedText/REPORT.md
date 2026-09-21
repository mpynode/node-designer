# animatedText -- compile report

**Source node:** `animatedText`  ·  **Base:** `MPxLocatorNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Animated rainbow text gizmo. The motion is driven by the timeline position
# (mod `loopFrames`) PLUS a gentle wall-clock drift, so it keeps flowing whether
# you scrub / play the timeline OR leave it idle -- the locator has no
# time-input plug, so a still timeline alone would freeze it (this is how the
# original text gizmo kept moving). auto_refresh keeps it repainting so the
# wall-clock term stays live.
self.auto_refresh = True

raw   = getattr(self, "displayText", "")
msg   = raw if (raw and str(raw).strip()) else "MPyNode!"
chars = list(str(msg))
n     = len(chars)
idx   = np.arange(n, dtype=np.float64)

loop  = max(self.loopFrames, 1)
frame = float(getattr(self, "time", 0.0))
# timeline position (0..1 per loop) plus a slow wall-clock drift so the gizmo
# animates even when the timeline is idle (matches the original text gizmo).
cyc     = (frame % loop) / loop + _wall.time() * 0.15
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

## Files

```
build/stages/animatedText/1_transpiled.cpp     deterministic transpile (no AI)
build/source/animatedText.cpp      SHIPPED
```
