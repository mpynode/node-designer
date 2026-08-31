# Two-Bone Analytic IK

Law-of-cosines solver for a 3-joint chain (root -> mid -> tip) driven by an `ikHandle`. It reads each joint's rest frame, so jointOrient is left alone, and bends toward the pole vector, falling back to the rest knee direction.

**Create + Run demo** builds a 3-joint leg driven by an ikHandle, plus a draggable goal locator -- move the goal to pose the leg.
