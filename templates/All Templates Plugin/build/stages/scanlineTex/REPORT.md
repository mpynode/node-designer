# scanlineTex -- compile report

**Source node:** `scanlineTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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

## Files

```
build/stages/scanlineTex/1_transpiled.cpp     deterministic transpile (no AI)
build/source/scanlineTex.cpp      SHIPPED
```
