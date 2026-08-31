# Dual Quaternion Skin

A real skinCluster (`mPySkinCluster`) that does dual quaternion skinning. Instead of averaging joint matrices, it blends each joint's rotation and translation as a dual quaternion, so a bent elbow or twisted wrist keeps its volume rather than collapsing into the classic "candy wrapper" pinch.

It reads the same live `weightList` plug as the Linear Blend Skin template, so Paint Skin Weights, the Component Editor and `cmds.skinPercent` all drive it, and one set of weights works in either. Compiles to pure C++ -- a native skinCluster that deforms the same way.

**Create + Run demo** imports the bundled two-bone arm, moves the weights off its stock skinCluster onto this one, and bends the elbow so the arm starts posed. Compare the bent volume against the Linear Blend Skin template.
