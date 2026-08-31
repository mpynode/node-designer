# Aim Between Two Matrices

An `mPyTransform` that parks itself halfway between two things and points at
one of them. Feed it two matrices and it sits at their midpoint with its X axis
aiming from `matrix0` toward `matrix1`; a world up vector (switching to +Z when
the aim goes near-vertical) keeps the roll from flipping. The frame carries no
scale, so anything parented under it rides cleanly along the segment between
the two inputs -- stretchy limb segments, connector geometry between two
controls. Wire any `worldMatrix` (a locator, a joint, another transform) into
`matrix0` and `matrix1`.

World placement is opt-in. `parentWorld` defaults to identity, so the node
lands exactly where the aim puts it in world space. To aim under a moving
parent, connect that parent's `worldMatrix[0]` into `parentWorld` -- the node
re-solves when the parent moves, and never reads its own DAG parent, so there
is no cycle.

The solve is published through `offsetParentMatrix` and ignores the node's own
translate / rotate / scale channels, so a channel like `translateX` stays free
to use as a plain handle for something else.

**Create + Run demo** drops two locators, wires them into `matrix0` /
`matrix1`, and parents a cube so the aim is visible. Move either locator to
watch the transform re-aim and its child follow.
