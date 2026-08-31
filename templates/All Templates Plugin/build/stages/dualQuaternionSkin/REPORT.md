# dualQuaternionSkin -- compile report

**Source node:** `dualQuaternionSkin`  ·  **Base:** `MPxSkinCluster`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# ----------------------------------------------------------------------
# mPySkinCluster -- default Compute source: dual quaternion skinning (DQS)
#
# The skinning math is the blessed API method self.dual_quaternion(rest,
# weights, joint, bind). Every operand is passed EXPLICITLY -- the method reads
# nothing off self -- so the plug dependencies are visible right here. They are
# the same plugs Maya's Component Editor / Paint Skin Weights / skinPercent edit:
#   self.weightList     -> dense (N, J) per-vertex, per-influence weights
#   self.matrix         -> (J, 4, 4) live joint WORLD matrices
#   self.bindPreMatrix  -> (J, 4, 4) joint bind-pose inverse matrices
# It blends each influence's rigid transform as a unit dual quaternion, so a bent
# joint keeps its volume (no LBS "candy-wrapper" collapse), and returns the
# deformed object-space points (N, 3); the envelope + write stay here so
# partial-effect composition is explicit.
#
# self.outputGeometry[0] is the writable mesh handle (object-space rest points).
# A deformer cannot change topology -- setPoints must keep the same N.
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

# Dual quaternion skinning of the rest points (envelope=0 rest, 1 fully skinned).
mesh.setPoints(rest + float(self.envelope) * (
    self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)
    - rest))
```

## Files

```
build/stages/dualQuaternionSkin/1_transpiled.cpp     deterministic transpile (no AI)
build/source/dualQuaternionSkin.cpp      SHIPPED
```
