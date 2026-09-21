# patchRelax -- compile report

**Source node:** `patchRelax`  ·  **Base:** `MPxDeformerNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | not run |

## The Python this was generated from

```python
# Patch-based surface relaxation (de Goes et al., Pixar, SIGGRAPH '18 Talks).
# Every vertex flattens its 1-ring into a 2D "decal map", derives span-aware edge
# weights from it, fits the rest->posed rotation of that patch by SVD, and steps
# toward the rotated REST edge layout. Because the target carries the patch's own
# rotation, the silhouette survives -- unlike a Laplacian smooth, which shrinks.
#
# `ringNbrs` (flat row-major CCW 1-ring vertex ids, -1 padded) and `ringWidth`
# (the padded width) are DECLARED INPUTS that **Rebuild Rings** seeds. They are
# inputs rather than something the compute derives because (a) they depend only
# on TOPOLOGY, so rebuilding them per frame is pure waste, and (b) building them
# needs repeat/argsort/bincount, every one of which the transpiler rejects --
# seeding them is what lets the whole compute lower to PURE C++.
#
# A deformer is live the instant mc.deformer() creates it, so "no rest mesh yet"
# and "rings not built yet" are the NORMAL startup states, not exotic ones -- the
# gates below are the common path, not error handling.
#
# They are PURELY NUMERIC and nested rather than a try/except, for two reasons.
# nd_lower strips a top-level eager guard on the generic compute path but NOT on
# the deform path, so a try here would drop the node to the AI porter and break
# the pure-C++ rule. And the nesting is what makes that safe: an unconnected mesh
# input reads as None, but `ringWidth > 0` can only be true once Rebuild Rings
# has run, and that refuses to run without a rest mesh connected -- so the
# `self.restMesh` read is unreachable until a rest mesh exists. (Merely
# DISCONNECTING one later does not resurrect the None: Maya retains the last mesh
# in the datablock.) setPoints stays UNCONDITIONAL so the deformer keeps its
# single getPoints/setPoints shape; the gates only choose what gets written.
mesh = self.outputGeometry[0]
P    = mesh.getPoints()
N    = P.shape[0]
flat = np.asarray(self.ringNbrs, dtype=np.int64)
Kw   = int(self.ringWidth)

out  = P
if (Kw > 0) and (flat.shape[0] == N * Kw):
    rest = self.restMesh.points
    if rest.shape[0] == N:
        out = patch_relax(P, rest, flat.reshape(N, Kw), int(self.iterations),
                          self.alpha, self.surfaceBlend)
mesh.setPoints(P + self.envelope * (out - P))
```

## Files

```
build/stages/patchRelax/1_transpiled.cpp     deterministic transpile (no AI)
build/source/patchRelax.cpp      SHIPPED
```
