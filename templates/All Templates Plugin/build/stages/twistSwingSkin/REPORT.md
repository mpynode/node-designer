# twistSwingSkin -- compile report

**Source node:** `twistSwingSkin`  ·  **Base:** `MPxSkinCluster`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# ----------------------------------------------------------------------
# mPySkinCluster -- twist/swing with TWO weight sets on ONE node, painted
# interactively via the skinMode enum, COMPILABLE to pure C++.
#
# self.twistWeights / self.swingWeights are declared (double, is_array) INPUT
# plugs holding the two dense weight sets FLATTENED row-major to length N*J:
# twistWeights drives the DUAL-QUATERNION twist, swingWeights the LINEAR-BLEND
# swing (bend). Being plugs, they serialize PER NODE (each character keeps its
# own weights) and the compiled deform reads them directly -- so this node
# compiles to byte-parity (the two sets are never shared across instances).
#
# skinMode is a PAINT-MODE selector:
#   0 Paint LBS (Swing) -> preview the live weightList with linear_blend; paint it
#                          and sync_paint banks the edits into swingWeights.
#   1 Paint DQS (Twist) -> preview the live weightList with dual_quaternion; paint
#                          it and sync_paint banks the edits into twistWeights.
#   2 Live Result       -> deform from BOTH weight-set plugs (twist + swing).
# twistAxis picks the bone-local twist axis (0 X default / 1 Y / 2 Z).
#
# self.sync_paint(mode) holds ALL the interactive machinery (load the active set
# into weightList on a mode switch so Paint Skin Weights shows it; bank painted
# weightList back into the active set plug on a settled eval). It is a blessed
# NativeSideEffect method: interpreted-only, and a bare call lowers to NOTHING in
# the compiled node (which runs headless -- no paint session -- and reads the two
# weight plugs directly, so omitting the scratchpad staging is faithful).
# ----------------------------------------------------------------------

mesh = self.outputGeometry[0]
rest = mesh.getPoints()                         # (N, 3) object-space rest points

mode = int(self.skinMode)

# interactive paint load/bank/latch (a no-op in the compiled node).
self.sync_paint(mode)

nj        = self.matrix.shape[0]           # influence count
nv        = rest.shape[0]                  # vertex count
twist     = np.asarray(self.twistWeights)  # flat (N*J,) weight-set plugs
swing     = np.asarray(self.swingWeights)
have_sets = twist.size == nv * nj and swing.size == nv * nj

if mode == 0:                                    # Paint LBS: preview live weightList
    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)
elif mode == 1:                                  # Paint DQS: preview live weightList
    deformed = self.dual_quaternion(rest, self.weightList, self.matrix, self.bindPreMatrix)
elif have_sets:                                  # Live Result: both weight-set plugs
    deformed = self.twist_swing_dual(rest, twist.reshape(nv, nj), swing.reshape(nv, nj), self.matrix, self.bindPreMatrix, int(self.twistAxis))
else:                                            # not seeded yet -> plain LBS fallback
    deformed = self.linear_blend(rest, self.weightList, self.matrix, self.bindPreMatrix)

# envelope=0 rest, 1 fully skinned (partial-effect composition explicit here).
mesh.setPoints(rest + float(self.envelope) * (deformed - rest))
```

## Files

```
build/stages/twistSwingSkin/1_transpiled.cpp     deterministic transpile (no AI)
build/source/twistSwingSkin.cpp      SHIPPED
```
