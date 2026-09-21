# compositeTexture -- compile report

**Source node:** `compositeTexture`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

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
u = self.uvCoord[0]
v = self.uvCoord[1]

# Accumulate over transparent black, bottom layer first.
cr   = 0.0
cg   = 0.0
cb   = 0.0
ca   = 0.0
n_op = len(self.opacities)
for i in range(len(self.layers)):
    r, g, b, a_src = self.sample_texture(self.read_texture(self.layers[i]),
                                         u, v, missing=(0.0, 0.0, 0.0, 0.0))
    op = 1.0
    if i < n_op:
        op = float(self.opacities[i])
    a  = a_src * op
    cr = r * a + cr * (1.0 - a)
    cg = g * a + cg * (1.0 - a)
    cb = b * a + cb * (1.0 - a)
    ca = a + ca * (1.0 - a)

self.outColor = (cr, cg, cb)
self.outAlpha = ca
```

## Files

```
build/stages/compositeTexture/1_transpiled.cpp     deterministic transpile (no AI)
build/source/compositeTexture.cpp      SHIPPED
```
