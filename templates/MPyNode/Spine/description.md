# Spine

Drives a chain of joints along a NURBS curve. Feed it the curve and one matrix per control, and it returns a position, rotation and scale for every sample point along that curve -- wire those to your riders and the chain follows the curve as the controls move it.

## Inputs

* `inputCurve` -- the curve the chain rides. Connect the curve shape's `worldSpace`.
* `controlMatrices` -- one entry per control, supplying the twist and scale basis at that point. Connect each control's `worldMatrix`.
* `samples` -- where along the curve each rider sits, 0 at the base to 1 at the tip. One element per rider.
* `curveAimAxis` / `curveUpAxis` -- which local axis of the riders points along the curve, and which points up.
* `curveInvertAimAxis` / `curveInvertUpAxis` -- flip either of those axes.
* `stretch` -- how much the chain lengthens with the curve. 0 keeps its original length and slides along, 1 stretches with it.
* `scale` -- an overall multiplier on the spacing along the curve.
* `shift` -- slides every rider along the curve together.
* `pivot` -- where the stretch is anchored, so the chain can stretch from the base, from the tip, or from anywhere between.
* `scaleMethod` -- how squash and stretch falls off across the chain: **Square Root**, **Linear** or **Cosine**.
* `defaultLength` -- the curve's rest length. `build_system` sets it to the curve's arc length when it builds the spine; set it again yourself after rebuilding or re-shaping the curve.

## Outputs

* `outputTranslate` -- one position per sample. Connect to each rider's translate.
* `outputRotate` -- one orientation per sample. Connect to each rider's rotate.
* `outputScale` -- one scale per sample. Connect to each rider's scale.

## Commands

* `build_system` -- builds an entire spine from a list of driving transforms: it creates the curve through their positions, live-drives its CVs, feeds their matrices in, and creates and connects the riders. Takes the rider count, the curve degree, and whether the riders are joints, locators, groups or cubes.
* `setup` -- the same thing from your selection. Pick at least two transforms, in order along the spine, then run. Offered as **Run setup on selection**.

## Create + Run demo

Builds a curve up Y, four control locators and a chain of 12 joints spread evenly along it -- move a control or edit the curve to reshape the chain.
