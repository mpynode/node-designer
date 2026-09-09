# widgetShowcase -- compile report

**Source node:** `widgetShowcase`  ·  **Base:** `MPxLocatorNode`  ·  **Generated:** 2026-09-08 23:24

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | ran, nothing accepted (baseline could not be benchmarked) |

## The Python this was generated from

```python
# Static rendering showcase -- no animation, so the cheapest possible
# locator (no auto_refresh). The `preset` enum selects which draw slots
# light up; a persistent `presets` dict (if present) overrides the shipped
# DEFAULT_PRESETS. Unassigned slots stay None and simply don't draw.
preset = self.preset.name()
presets = getattr(self, "presets", None)
if not isinstance(presets, dict):
    presets = DEFAULT_PRESETS
active = set(presets.get(preset, DEFAULT_PRESETS.get(preset, [])))

self.auto_highlight = False   # carry our own palette

# Each preset appends the drawables for its lane; `self.draw` takes the LIST
# straight and draws it in order. A drawable carries its own target buffer, so
# nothing here has to name a slot -- and an inactive preset simply contributes
# no object.
items = []

if "curves" in active:
    items.append(DrawLines(CURVE_STARTS, CURVE_ENDS, color=CURVE_COLORS))

if "points" in active:
    items.append(DrawPoints(POINT_POS, color=POINT_COLORS, size=POINT_SIZES))

if "polygons" in active:
    # outline_boundary_only=False draws EVERY edge (the cube's wire overlay),
    # not just the silhouette.
    items.append(DrawMesh(POLY_PTS, POLY_CNT, POLY_IDX,
                          color=POLY_FACE_COLORS, cull_backfaces=True,
                          outline=(0.04, 0.04, 0.06, 1.0), outline_width=2.0,
                          outline_boundary_only=False))

if "shapes" in active:
    items.append(
        DrawSphere(center=SHAPE_CENTERS[0], radius=0.8, axis=AXIS_Y,
                   color=SHAPE_COLORS[0], filled=True)
        + DrawBox(center=SHAPE_CENTERS[1], radius=0.8, axis=AXIS_Y,
                  color=SHAPE_COLORS[1], filled=True)
        + DrawCone(center=SHAPE_CENTERS[2], radius=0.8, axis=AXIS_Y,
                   color=SHAPE_COLORS[2], filled=True)
        + DrawCylinder(center=SHAPE_CENTERS[3], radius=0.8, axis=AXIS_Y,
                       color=SHAPE_COLORS[3], filled=True)
        + DrawCircle(center=SHAPE_CENTERS[4], radius=0.9, axis=AXIS_Y,
                     color=SHAPE_COLORS[4], filled=False))

if "text" in active:
    items.append(DrawText(TEXT_STRINGS, TEXT_POS, color=TEXT_COLORS, size=TEXT_SIZES))

self.draw = items
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **--** -> best **--** (**1.00x**).

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | -- | -- | -- |

## Verification

* parity: **pass**
* no scalar outputs to compare -- pointwise parity skipped (vacuous check) | authored @maya_test: 1/1 passed

## Files

```
build/stages/widgetShowcase/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/widgetShowcase/2_assisted.cpp       AI filled the unported region(s)
build/stages/widgetShowcase/3_optimized/00_baseline.cpp
build/source/widgetShowcase.cpp      SHIPPED
```
