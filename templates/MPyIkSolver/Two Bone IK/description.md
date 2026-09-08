# Two-Bone Analytic IK

An `mPyIkSolver` for a three-joint chain -- root, mid, tip -- driven by a standard Maya `ikHandle`. It solves the knee angle directly rather than iterating, so there is nothing to tune and no settling.

It reads each joint's rest frame, so `jointOrient` is left alone, and bends toward the pole vector. With no pole vector connected it falls back to the knee direction the chain was built in.

## Inputs

There are no attributes to set on the node. It reads the standard IK setup instead:

* the `ikHandle` it is assigned to -- its position is the goal.
* the three joints of the chain, including their rest orientation.
* the pole vector constraint, if there is one, which decides which way the knee points.

## Outputs

* The solved joint rotations, written back to the chain through the IK system, exactly as a built-in solver would.

## Create + Run demo

Builds a three-joint leg driven by an `ikHandle`, plus a draggable goal locator -- move the goal to pose the leg.
