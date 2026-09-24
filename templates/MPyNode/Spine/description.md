# Spine

Drives a chain of riders along a B-spline that the node builds itself from one matrix per control. It returns a position, rotation and scale for every sample along the curve -- wire those to your riders and the chain follows the controls. No Maya curve takes part in the evaluation.

## Inputs

* `controlMatrices` -- one entry per control, in order along the spine. Each control's position is a curve CV, its axes can drive the twist and its scale can drive the scale. Connect each control's `worldMatrix`.
* `samples` -- where each rider sits, by arc length: 0 at the base to 1 at the tip. One element per rider.
* `degree` -- the curve degree, held to one less than the control count (at most 7).
* `periodic` -- a closed curve (3 controls or more). Sample 0 always registers on the first control (the point of the curve that control pulls on most), and riders loop round the seam.
* `curveAimAxis` / `curveUpAxis` -- which local axis of the riders points along the curve, and which points up.
* `curveInvertAimAxis` / `curveInvertUpAxis` -- flip either of those axes.
* `stretch` -- how much the chain lengthens with the curve. 0 keeps its rest length and slides along, 1 stretches with it.
* `scale` -- an overall multiplier on the spacing along the curve.
* `shift` -- slides every rider along the curve together.
* `pivot` -- where the stretch is anchored, so the chain can stretch from the base, from the tip, or from anywhere between.
* `defaultLength` / `restKeys` -- the rest pose: the curve's rest length and each control's rest position along it. `spineBuildSystem` captures both; run `spineResetRest` after re-posing the controls on purpose.
* `translateProjection` -- riders pushed past the ends of an open curve: **Clamped** holds the end point, **Infinite** carries on along the end direction.
* `controlUpAxes` -- per control, which of its axes is its up vector: 0 the riders' up axis, 1-3 +X/+Y/+Z, 4-6 -X/-Y/-Z.
* `rotateMode` / `scaleMode` -- which controls drive the twist and the scale:
  * **All** -- every control.
  * **Flagged** -- the controls set in `rotateFlags` / `scaleFlags`. Riders between two flagged controls blend between them.
  * **None** -- identity rotation / unit scale.
  * **Matrix** -- the single `rotateMatrix` / `scaleMatrix` drives every rider; the controls are ignored.
* `rotateFlags` / `scaleFlags` -- one bool per control, for **Flagged**.
* `rotateMatrix` / `scaleMatrix` -- one outside matrix, for **Matrix**.
* `rotateProjection` / `scaleProjection` -- how riders blend between drivers, and past the first and last one:
  * **Frozen** -- by each rider's rest position, so shift and stretch leave the blend alone; carries on past the end drivers.
  * **Infinite** -- by each rider's live position; carries on past the end drivers.
  * **Clamped** -- by the live position, holding the first and last driver.
  On a closed curve the blend runs across the seam.
* `scaleMethod` -- how scale blends between drivers: **Square Root**, **Linear** or **Cosine**.
* `computeWeights` -- also output the basis weights.

## Outputs

* `outputTranslate` -- one position per sample. Connect to each rider's translate.
* `outputRotate` -- one orientation per sample. Connect to each rider's rotate.
* `outputScale` -- one scale per sample. Connect to each rider's scale.
* `currentLength` -- the curve's live arc length.
* `controlKeys` -- each control's live position along the spine, 0 to 1 by chord length.
* `restValid` -- the rest data matches the controls; when it does not, **Frozen** uses the live keys.
* `outputWeights` -- with `computeWeights` on, one row of control weights per sample (samples x controls, row by row). A row times the control positions gives that sample's `outputTranslate`.

## Commands

* `spineBuildSystem` -- builds an entire spine from a list of driving transforms: feeds their matrices in, sets the drivers and projections, creates and connects the riders, adds a templated display curve and captures the rest pose. Drivers are `all`, `none`, `ends`, `first` or `last`, a list of the controls, or one outside transform.
* `spineSetDrivers` -- changes the twist and scale drivers of a built spine by control name.
* `spineResetRest` -- captures the current pose as the rest pose.
* `setup` -- `spineBuildSystem` from your selection. Pick at least two transforms, in order along the spine, then run. Offered as **Run setup on selection**.

## Create + Run demo

* **Spine From Four Controls** -- four control locators up Y and 12 cubes spread evenly along the spine. Move a control to reshape it.
* **Spine: Twist Ends, Squash Middle** -- five controls; only the two ends drive the twist (the top one is turned 90 degrees) and the ends plus the middle drive the scale, so the cubes twist smoothly and bulge in the middle.
* **Spine: Closed Loop** -- six controls on a circle driving a closed spine, 24 cubes round it, the first one registered on the first control.
