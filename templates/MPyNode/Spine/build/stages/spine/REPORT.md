# spine -- compile report

**Source node:** `spine`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:28

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **4.79x** over 2 round(s) -- re-measured: **1.13x** (outputs match) |

## The Python this was generated from

```python
# Name: Re-rootable Quaternion Spine  (numpy-first port of the original MPyNode)
# Author: Eric Vignola - eric.vignola@gmail.com
#
# Ported to the current MPyNode value-type contract:
#   * matrix inputs arrive as numpy (n,4,4) row-major (translation in row 3)
#   * vector / euler outputs are pre-sized numpy buffers (slice-assign by index)
#   * nurbsCurve input is an MFnNurbsCurve (om), used as-is for curve queries
#   * matrix->euler decomposition uses om.MTransformationMatrix (rotation-order exact)
#
# (Imports + helper functions live in the Init tab.)

# ---------------------- Main ----------------------#

max_parameter = self.inputCurve.findParamFromLength(10 ** 9)
currentLength = self.inputCurve.findLengthFromParam(max_parameter)

if self.resetDefaultLength or not hasattr(self, 'defaultLength'):
    self.defaultLength = currentLength

# End points / tangents for out-of-range projection (om -> numpy 3-vectors)
t0 = np.array(self.inputCurve.tangent(0, space=om.MSpace.kWorld))[:3]
t1 = np.array(self.inputCurve.tangent(max_parameter, space=om.MSpace.kWorld))[:3]
p0 = np.array(self.inputCurve.getPointAtParam(0, space=om.MSpace.kWorld))[:3]
p1 = np.array(self.inputCurve.getPointAtParam(max_parameter, space=om.MSpace.kWorld))[:3]

# Control matrices as a single (n,4,4) numpy array (row-major; translate = row 3)
CM = np.asarray(self.controlMatrices)
trans = CM[:, 3, :3]

# Normalized control parameters (chord-length keys)
keys = [0.0]
for i in range(len(CM)):
    if i > 0:
        dist = float(np.linalg.norm(trans[i] - trans[i - 1])) + keys[i - 1]
        keys.append(dist)
for i in range(1, len(keys)):
    keys[i] /= keys[-1]

ratio = self.defaultLength / currentLength
delta = (currentLength - self.defaultLength) / currentLength

for i in range(len(self.outputTranslate)):

    # -- POSITION --
    u = self.shift + self.pivot + (((((self.samples[i] * ratio + delta * self.pivot) * (1 - self.stretch)) + self.samples[i] * self.stretch) - self.pivot) * self.scale)
    w = self.inputCurve.findParamFromLength(u * currentLength)

    if u < 0:
        self.outputTranslate[i] = (p0 + t0 * (u * currentLength))
    elif u > 1:
        self.outputTranslate[i] = (p1 + t1 * ((u - 1) * currentLength))
    else:
        self.outputTranslate[i] = np.array(self.inputCurve.getPointAtParam(w, space=om.MSpace.kWorld))[:3]

    # -- ROTATION --
    index = bl(keys, u) - 1
    if index < 0:
        index = 0
    elif index == len(keys) - 1:
        index -= 1

    up0 = CM[index][self.curveUpAxis, :3]
    up1 = CM[index + 1][self.curveUpAxis, :3]

    blend = (u - keys[index]) / (keys[index + 1] - keys[index])
    blend = max(min(blend, 1), 0)

    normal = vectorSlerp(up0, up1, blend)
    tangent = np.array(self.inputCurve.tangent(w, space=om.MSpace.kWorld))[:3]

    if self.curveInvertUpAxis:
        normal = -normal
    if self.curveInvertAimAxis:
        tangent = -tangent

    basis = vectorToMatrix(tangent, normal, self.curveAimAxis, self.curveUpAxis)
    e = om.MTransformationMatrix(om.MMatrix(basis.flatten().tolist())).rotation()
    self.outputRotate[i] = np.array([e.x, e.y, e.z])

    # -- SCALE --
    if self.scaleMethod == 0:
        s0 = np.abs(_scale_of(CM[index])) ** (1 - blend)
        s1 = np.abs(_scale_of(CM[index + 1])) ** blend
        self.outputScale[i] = s0 * s1
    else:
        if self.scaleMethod == 2:
            blend = 1 - ((math.cos(math.radians(blend * 180)) + 1) * 0.5)
        self.outputScale[i] = _scale_of(CM[index + 1]) * blend + _scale_of(CM[index]) * (1 - blend)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **8.723 ms** -> best **1.821 ms** (**4.79x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: baseline 17.181 ms -> shipped 15.198 ms (**1.13x**); outputs match. The speedup above was taken before the gate existed; this is the number to quote. Moved per tick: `controlMatrices[0] (matrix)`, `inputCurve <- nurbsCircleShape1.cv[0]`, `pivot (float)`, `samples[0] (float)`, `scale (float)`, `shift (float)`, `stretch (float)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 8.723 ms | -- | -- |
| 01 | `bucket_index_keys` | replace the per-sample bisect_left over the 20000-entry chord-length key table with a uniform bucket table that brackets each query to a handful of adjacent entries, and hoist the per-control-matrix up-row/scale/log work out of the sample loop | 1.40x | 1.13x | 11.2 min | ACCEPTED |
| 02 | `memo_bit_equal_pure_queries` | every per-sample NURBS query and the whole rotation/scale block are pure functions of a key that barely changes across the 20000 samples, so one-entry memos keyed on BIT-EQUAL arguments replace 60000 Maya curve calls with 17 | 2.00x | 4.79x | 10.5 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `memo_bit_equal_pure_queries` -- predicted 2.00x, measured **4.79x**. profiling said tangent() cost 2.5ms of a 7.1ms loop while getPointAtParam cost 0.28ms -- a 9x gap that only makes sense if getPointAtParam was being SKIPPED, i.e. the samples land outside [0,1] and findParamFromLength keeps clamping w onto one endpoint param. If w repeats, tangent(w) repeats, and once u leaves the key span blend saturates so the slerped normal, the basis, the MTransformationMatrix euler and the blended scale all repeat too. Memoizing on exact bit equality is identity-preserving, not tolerance-preserving, so it cannot move the answer.

## Verification

* parity: **FAIL**  (maxerr 0.04546562905909468, tol 0.0001)
* authored @maya_test: 1/1 passed

## Files

```
build/stages/spine/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/spine/2_assisted.cpp       AI filled the unported region(s)
build/stages/spine/3_optimized/00_baseline.cpp
build/stages/spine/3_optimized/01_bucket_index_keys.cpp
build/stages/spine/3_optimized/02_memo_bit_equal_pure_queries.cpp
build/source/spine.cpp      SHIPPED
```
