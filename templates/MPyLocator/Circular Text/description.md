# Circular Text

A word written around a ring (`mPyLocator`), laid out in the ring's own polar frame: every letter is an angle around the circle and a distance from its centre, so the text belongs to the ring instead of being pasted onto it. By default it lies flat and reads from above, tops toward the centre, and each letter tapers inward like lettering on a dial.

Type into `displayText`; blank shows `MPyNode`. `radius`, `letterHeight` and `tracking` set the size and spacing, and a string longer than the circle wraps once around it. `tilt` stands the letters up (0 flat, 90 upright) and `roll` turns the word around the ring; neither is clamped, so both can be keyed round and round. `aimAxis` and `upAxis`, each with an invert, choose where the word sits and what it circles, and a negative `radius` puts it on the far side.

`textStyle` draws filled Consolas glyphs or a thinner stroke font. `ringStyle` either lofts a shaded ribbon between the baseline and the cap that fades out toward the word, or draws those two edges as thin arcs. Either way the gap is measured from the word's own arc, so nothing is ever drawn behind the letters however long the text gets. `color` and `alpha` set the fill; selecting the gizmo tints it without losing that transparency.

**Create + Run demo** writes `MPyNode` flat on a radius-10 ring and frames it.
