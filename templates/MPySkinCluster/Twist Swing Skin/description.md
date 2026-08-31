# Twist/Swing Skin (Two Weight Sets)

A real skinCluster that carries two independent sets of skin weights instead of one. `twistWeights` drives a dual-quaternion twist pass around each bone's own axis; `swingWeights` drives a linear-blend swing (bend) pass. A normal skinCluster gives you a single `weightList`, so you cannot paint a tight twist falloff and a soft bend falloff on the same joint -- here you can, and the node still compiles to pure C++.

`skinMode` picks what you are painting. `Paint LBS (Swing)` and `Paint DQS (Twist)` each load their set into `weightList`, so Paint Skin Weights and the Component Editor show it immediately, and your strokes bank straight back into that set. `Live Result`, the default, deforms from both sets at once. `twistAxis` chooses the bone-local twist axis. `self.sync_paint(mode)` carries that load-and-bank machinery; it is interactive-only, so the compiled node skips it and reads the two weight plugs directly.

**Create + Run demo** skins the bundled two-bone arm, seeding `twistWeights` from `DQS.json` (a rigid twist falloff) and `swingWeights` from `LBS.json` (a smooth bend falloff). The elbow twists first, over frames 0-30, then bends over frames 30-90, so you see each set on its own.

One caveat: the paint load and bank are deferred a frame for safety, so switching mode in the middle of a stroke can drop that stroke. Paint, pause, then switch.
