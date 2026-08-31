# Spine

Drives a joint chain along a NURBS curve. Feed it an `inputCurve` and a `controlMatrices` array, one per control, returning `outputTranslate`, `outputRotate` and `outputScale` arrays -- one per entry in `samples`, 0 to 1 along it. `stretch`, `scale`, `shift`, `pivot` and `scaleMethod` tune the falloff.

**Create + Run demo** builds a curve up Y, four control locators and a chain of 12 joints -- move a control or edit the curve to reshape it.
