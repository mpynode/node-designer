# fileTexture -- compile report

**Source node:** `fileTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# File texture with a brightness / contrast filter.
#
# self.read_texture()    load `fileName`, decode it out of `colorSpace`, apply
#                        the optional pre-filter. Returns a float32 HxWx4
#                        SCENE-LINEAR buffer (cached), or None when the file is
#                        missing / unreadable -- but first it falls back to the
#                        node's baked `embeddedImage` bytes, so a node with no
#                        file on disk still renders.
# self.sample_texture()  wrap-aware BILINEAR lookup into that buffer ->
#                        (r, g, b, a). Returns magenta when the buffer is None,
#                        so a missing file never raises.
#
# Both are framework methods shared by every mPyFile -- the same pair the
# built-in default uses -- so this template stays about the GRADE, not about
# how to read a PNG.
buf = self.read_texture()
r, g, b, a = self.sample_texture(buf, self.uvCoord[0], self.uvCoord[1])

# brightness scales about black, contrast about mid-grey, then clamp.
bright   = self.brightness
contrast = self.contrast
r        = min(1.0, max(0.0, (r * bright - 0.5) * contrast + 0.5))
g        = min(1.0, max(0.0, (g * bright - 0.5) * contrast + 0.5))
b        = min(1.0, max(0.0, (b * bright - 0.5) * contrast + 0.5))

self.outColor = (r, g, b)
self.outAlpha = a
```

## Files

```
build/stages/fileTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/source/fileTexture.cpp      SHIPPED
```
