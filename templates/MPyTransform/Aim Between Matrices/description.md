# Aim Between Two Matrices

An `mPyTransform` that parks itself halfway between two things and points at one of them. Feed it two matrices and it sits at their midpoint with its X axis aiming from the first toward the second, with the roll kept from flipping when the aim goes near-vertical.

The frame carries no scale, so anything parented under it rides cleanly along the segment between the two inputs -- stretchy limb segments, or connector geometry between two controls.

The solve is published through `offsetParentMatrix` and ignores the node's own translate, rotate and scale channels, so a channel like `translateX` stays free to use as a plain handle for something else.

## Inputs

* `matrix0` -- the start. Wire any transform's `worldMatrix` here: a locator, a joint, another transform.
* `matrix1` -- the end. The aim points from `matrix0` toward this.
* `parentWorld` -- optional. Left alone, the node lands exactly where the aim puts it in world space. To aim under a moving parent, connect that parent's `worldMatrix[0]`; the node re-solves when the parent moves and never reads its own DAG parent, so there is no cycle.

## Outputs

* The transform's own position and orientation, published through `offsetParentMatrix`. Parent anything under it and it rides the segment.

## Commands

* `setup` -- aims this transform between two selected objects: pick START then END. An optional third pick drives `parentWorld`. Offered as **Run setup on selection**.

## Create + Run demo

Drops two locators, wires them in, and parents a cube so the aim is visible. Move either locator to watch the transform re-aim and its child follow.
