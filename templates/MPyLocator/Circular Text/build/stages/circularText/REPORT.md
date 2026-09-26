# circularText -- compile report

**Source node:** `circularText`  ·  **Base:** `MPxLocatorNode`  ·  **Generated:** 2026-09-26 00:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) -- 0 run of max 6, stopped: baseline could not be benchmarked |

## The Python this was generated from

```python
# A word written around the locator's ring, built in the ring's own polar frame:
# every glyph point is an ANGLE around the circle plus a DISTANCE from its
# centre, so the letters belong to the ring instead of being pasted onto it.
#
# The frame is yours to choose: `upAxis` is what the letters circle around,
# `aimAxis` is where the middle of the word sits, and either can be inverted.
# `roll` then spins the whole word around the up axis, `tilt` rolls each letter
# about the ring tangent (0 flat for the top-down read, 90 upright), and a
# NEGATIVE `radius` puts the ring on the far side of the aim axis and reverses
# the reading direction -- the quickest fix when text comes out mirrored in your
# view. None of those is clamped: wind them as far as you like.
#
# Flat letters taper on their own. A glyph spans a fixed slice of angle, so the
# arc it covers shrinks as it nears the centre: the inner edge of a letter is
# narrower than its outer edge and the word fans out radially. Standing the
# letters upright removes the taper, because an upright letter spans no radius.
text = getattr(self, "displayText", "")
text = str(text) if (text is not None and str(text) != "") else "MPyNode"

radius = float(self.radius)
if abs(radius) < 1e-4:
    radius = 1e-4 if radius >= 0.0 else -1e-4
height = max(float(self.letterHeight), 1e-6)
tilt   = np.radians(float(self.tilt))
ct     = float(np.cos(tilt))     # how much of a letter's height goes OUTWARD
st     = float(np.sin(tilt))     # ...and how much of it goes UP
rgb    = np.asarray(self.color, dtype=np.float64).reshape(-1)[:3]
alpha  = min(max(float(self.alpha), 0.0), 1.0)
color  = (float(rgb[0]), float(rgb[1]), float(rgb[2]), alpha)
style  = self.textStyle.name()
shade  = self.ringStyle.name() == "shaded"

aim, tangent, up = ring_frame(self.aimAxis.name(),
                              self.invertAim.name() == "True",
                              self.upAxis.name(),
                              self.invertUp.name() == "True")

offsets, total = letter_offsets(len(text), max(float(self.tracking), 0.0))
# Spacing squeezes so a string longer than the circle wraps round it exactly
# once instead of running past its own start. The letters keep their size.
span = total * height
fit  = min(1.0, (TWO_PI * abs(radius)) / span) if span > 0.0 else 1.0
roll = np.radians(float(self.roll))

# The band the letters occupy: the baseline ring and the cap ring, which rolls
# inward or upward with the letters. `shaded` lofts a ribbon between the two,
# `lines` draws them as a pair of faint arcs. Either way the drawing stops
# short of the word; only how it fades into that gap differs.
#
# The gap is measured from the word's OWN arc, so the shading gets out of the
# way by itself: a longer string, taller letters or looser tracking each widen
# it, and nothing is ever drawn behind the text.
items = []
pitch = total / max(len(text), 1)
gap   = min((0.5 * total + 0.5 * pitch) * fit * height / abs(radius), np.pi)
arc   = TWO_PI - 2.0 * gap
if arc > 1e-3:                  # a word that wraps the ring leaves no room
    steps = max(int(96.0 * arc / TWO_PI) + 2, 8)
    u     = np.linspace(0.0, 1.0, steps)
    theta = roll + gap + arc * u
    one   = np.ones(steps, dtype=np.float64)
    outer = place(theta, one * radius, one * 0.0, aim, tangent, up)
    inner = place(theta, one * (radius - ct * height), one * (st * height),
                  aim, tangent, up)
    if shade:
        # A cosine bump: clear at both ends, where the letters begin, and
        # full alpha on the far side of the ring. A ribbon carries enough
        # ink for a fade that long to read as a fade.
        fade = alpha * (0.5 - 0.5 * np.cos(TWO_PI * u))
        vcol = np.empty((2 * steps, 4), dtype=np.float64)
        vcol[:, :3]     = color[:3]
        vcol[:steps, 3] = fade
        vcol[steps:, 3] = fade
        bcnt, bidx = band_faces(steps)
        items.append(DrawMesh(np.concatenate([outer, inner]), bcnt, bidx,
                              vertex_colors=vcol, cull_backfaces=False))
    else:
        # The arcs take the same gap -- neither style crosses a letter -- but
        # NOT the same fade. A line an eyelash wide has far less ink than the
        # ribbon, so a ramp that long reads as faint everywhere rather than as
        # a fade. These hold full colour and fade over a short run-in at each
        # end instead, capped in ANGLE so a longer arc does not stretch the
        # run-in out with it.
        ramp  = min(0.12 * arc, 0.35)          # radians of fade at each end
        t     = np.clip(np.minimum(u, 1.0 - u) * arc / ramp, 0.0, 1.0)
        gfade = alpha * t * t * (3.0 - 2.0 * t)          # smoothstep
        gcol  = np.empty((steps, 4), dtype=np.float64)
        gcol[:, :3] = (color[0] * 0.35, color[1] * 0.35, color[2] * 0.35)
        gcol[:, 3]  = gfade
        items.append(DrawCurve(outer, color=gcol))
        items.append(DrawCurve(inner, color=gcol))


def to_world(gx, gy):
    # gx is the distance along the baseline (cap heights, already offset by the
    # letter's own position), gy the height up the glyph: x becomes an angle, y
    # becomes height, and the tilt splits that height outward versus upward.
    # Letter height runs INWARD: tops sit on the inner edge of the band and
    # bottoms on the outer one, so the word reads from outside the ring looking
    # in. It also aims the taper the way a circle wants it -- the tops are
    # nearer the centre, so they span less arc than the bottoms.
    h = gy * height
    return place((gx * height) / radius + roll, radius - ct * h, st * h,
                 aim, tangent, up)


# Outline glyphs for every character the font has; strokes (the tofu box) for
# anything else, so nothing typed silently vanishes.
want_fill = style == "filled"
pts, idx, counts, fill_at = [], [], [], 0
sk0, sk1 = [], []
for i, ch in enumerate(text):
    at = offsets[i] * fit
    g  = POLY.get(ch.upper()) if want_fill else None
    if g is not None:
        gp, gi = g
        pts.append(gp + np.array([at, 0.0]))
        idx.append(gi + fill_at)
        counts.append(np.full(gi.shape[0] // 3, 3, dtype=np.int64))
        fill_at += gp.shape[0]
        continue
    for (x0, y0, x1, y1) in glyph(ch):
        sk0.append((at + (x0 - 0.5) * ADVANCE, y0))
        sk1.append((at + (x1 - 0.5) * ADVANCE, y1))

if pts:
    flat = np.concatenate(pts, axis=0)
    face = to_world(flat[:, 0], flat[:, 1])
    cnt  = np.concatenate(counts)
    ids  = np.concatenate(idx)
    # The letters are their own buffer, so they keep the single-colour fast
    # path whatever the band beneath them is doing.
    items.append(DrawMesh(face, cnt, ids, uniform_color=color,
                          cull_backfaces=False))

if sk0:
    p0 = np.array(sk0, dtype=np.float64)
    p1 = np.array(sk1, dtype=np.float64)
    items.append(DrawLines(to_world(p0[:, 0], p0[:, 1]),
                           to_world(p1[:, 0], p1[:, 1]), color=color))

self.draw         = items
self.auto_refresh = False
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
build/stages/circularText/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/circularText/2_assisted.cpp       AI filled the unported region(s)
build/stages/circularText/3_optimized/00_baseline.cpp
build/source/circularText.cpp      SHIPPED
```
