# Linear Blend Skin

A real skinCluster (`mPySkinCluster`) that does classic linear blend skinning in Python: every vertex lands on a weighted average of the joints influencing it. Good for seeing how skinning works under the hood, or as a base for your own deformer.

Maya sees a genuine skinCluster, so Paint Skin Weights, the Component Editor and `cmds.skinPercent` read and write its `weightList` plug live. Compiles to pure C++ -- a native skinCluster that deforms the same way.

**Create + Run demo** imports the bundled two-bone arm, moves the weights off its stock skinCluster onto this one, and bends the elbow so the arm starts posed.
