# Spring Chain

An `mPyNode` spring-and-mass solver for secondary motion -- tails, ropes, antennae, jiggle. The first point chases the `driver`, each point after it chases the one in front, so motion ripples down the chain and settles on its own.

## Inputs

* `driver` -- the position the head of the chain chases. Wire a control's world position here.
* `time` -- drives the simulation. Connect it to scene time; the solver steps once per frame.
* `tension` -- how hard each point is pulled toward the one ahead. Higher is stiffer and snappier.
* `damping` -- how quickly motion bleeds off. Low values keep wobbling, high values settle fast.
* `mass` -- how heavy each point feels. Heavier lags further behind the driver.
* `gravity` -- a constant pull applied to every point. Zero it for a chain that should not sag.
* `minDistance` / `maxDistance` -- clamp how far a point may drift from the one ahead, which stops the chain stretching or collapsing.
* `resetBuffer` -- clears the stored simulation state. Use it after moving the rig, or if the chain has blown up.

## Outputs

* `driven` -- the solved positions, one entry per point in the chain. Connect each element to whatever that point should drive.

## Create + Run demo

Builds a keyframed driver locator and a 100-sphere chain wired to `driven`, with gravity zeroed and the tuning attributes on the driver's channel box.
