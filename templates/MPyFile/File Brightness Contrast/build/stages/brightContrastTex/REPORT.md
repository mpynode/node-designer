# brightContrastTex -- compile report

**Source node:** `brightContrastTex`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:38

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# File texture with a brightness / contrast filter. Reads the image at
# `fileName`, samples it (nearest-neighbour) at the incoming `uvCoord`,
# applies brightness then contrast (pivoted at mid-grey), and writes
# `outColor` / `outAlpha`.
img = _read_image(self.fileName)
u, v = self.uvCoord

if img is None:
    self.outColor = (1.0, 0.0, 1.0)          # magenta = no/!readable file
    self.outAlpha = 1.0
else:
    h, w = img.shape[0], img.shape[1]
    uu = u - np.floor(u)                      # wrap into [0,1)
    vv = v - np.floor(v)
    # Map u/v uniformly across all w/h texels (same cell mapping on both
    # axes). v is flipped because Maya's V runs bottom-up while the image
    # buffer is top-down (see _read_image) -- matching a standard file node.
    px = min(w - 1, int(uu * w))
    py = min(h - 1, int((1.0 - vv) * h))
    r, g, b, a = (float(c) for c in img[py, px])

    bright = self.brightness
    contrast = self.contrast
    out = []
    for ch in (r, g, b):
        ch = ch * bright
        ch = (ch - 0.5) * contrast + 0.5
        out.append(max(0.0, min(1.0, ch)))
    self.outColor = (out[0], out[1], out[2])
    self.outAlpha = a
```

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0058823529411764705)
* 1 string input(s) driven with generated fixtures: fileName | authored @maya_test: 1/1 passed
* speed: compiled 0.017 ms vs interpreted 0.261 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/brightContrastTex/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/brightContrastTex/2_assisted.cpp       AI filled the unported region(s)
build/source/brightContrastTex.cpp      SHIPPED
```
