"""Stroke-font glyphs for the mPyMesh SDF "MPyNode" text.

Each glyph is a list of straight STROKES ``(x0, y0, x1, y1)`` in a local
letter frame: x in roughly ``[0, 1]``, baseline at ``y=0``, caps top at
``CAP``, lowercase x-height at ``XH``, descender at ``DESC``. A stroke
becomes one SDF box (centre, length, angle) extruded in Z; unioning the
boxes of a word yields a single watertight mesh via dual marching cubes.

``word_strokes(text)`` lays the glyphs out left-to-right (centred on the
origin) and returns a flat list of world boxes as dicts
``{cx, cy, length, thick, angle, depth}`` a caller turns into live
transforms + ``addBox`` calls.

This is a SHIPPED module (pure Python, ``math`` only -- no numpy, no Maya)
so it is importable at runtime by the Metaballs template's ``def demo`` as
well as at build time by ``mpynode._demos.sdf_text`` (which re-exports it,
so the glyph font is a single source of truth that can never drift).
"""
from __future__ import annotations

import math

CAP     = 1.40   # cap height
XH      = 0.95   # lowercase x-height
DESC    = -0.55  # descender bottom
THICK   = 0.22   # stroke thickness
DEPTH   = 0.50   # extrusion depth (Z)
ADVANCE = 1.35   # per-letter horizontal advance (cell 1.0 + gap 0.35)


# Glyphs only for the letters in "MPyNode".
GLYPHS = {
    "M": [
        (0.10, 0.00, 0.10, CAP),
        (0.90, 0.00, 0.90, CAP),
        (0.10, CAP, 0.50, 0.55),
        (0.90, CAP, 0.50, 0.55),
    ],
    "P": [
        (0.10, 0.00, 0.10, CAP),
        (0.10, CAP, 0.80, CAP),
        (0.80, CAP, 0.80, 0.72),
        (0.10, 0.72, 0.80, 0.72),
    ],
    "y": [
        (0.12, XH, 0.50, 0.28),
        (0.88, XH, 0.28, DESC),
    ],
    "N": [
        (0.10, 0.00, 0.10, CAP),
        (0.90, 0.00, 0.90, CAP),
        (0.10, CAP, 0.90, 0.00),
    ],
    "o": [
        (0.12, 0.00, 0.88, 0.00),
        (0.12, XH, 0.88, XH),
        (0.12, 0.00, 0.12, XH),
        (0.88, 0.00, 0.88, XH),
    ],
    "d": [
        (0.88, 0.00, 0.88, CAP),
        (0.12, 0.00, 0.12, XH),
        (0.12, XH, 0.88, XH),
        (0.12, 0.00, 0.88, 0.00),
    ],
    "e": [
        (0.12, 0.00, 0.12, XH),
        (0.12, XH, 0.88, XH),
        (0.12, 0.475, 0.88, 0.475),
        (0.12, 0.00, 0.88, 0.00),
        (0.88, 0.475, 0.88, XH),
    ],
}


def _stroke_box(x0, y0, x1, y1):
    """Turn a segment into a box: centre, length (extended by THICK so joins
    overlap), thickness, angle (deg about Z)."""
    cx     = (x0 + x1) * 0.5
    cy     = (y0 + y1) * 0.5
    dx     = x1 - x0
    dy     = y1 - y0
    length = math.hypot(dx, dy) + THICK
    angle  = math.degrees(math.atan2(dy, dx))
    return dict(cx=cx, cy=cy, length=length, thick=THICK, angle=angle,
                depth=DEPTH)


def word_strokes(text="MPyNode"):
    """Return the ordered list of world boxes for ``text`` (centred on X)."""
    letters = [c for c in text if c in GLYPHS]
    total_w = ADVANCE * (len(letters) - 1) + 1.0 if letters else 0.0
    x_off   = -total_w * 0.5
    boxes   = []
    for i, ch in enumerate(letters):
        ox = x_off + i * ADVANCE
        for (x0, y0, x1, y1) in GLYPHS[ch]:
            b = _stroke_box(x0, y0, x1, y1)
            b["cx"] += ox
            boxes.append(b)
    return boxes
