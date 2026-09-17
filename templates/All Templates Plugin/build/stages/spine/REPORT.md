# spine -- compile report

**Source node:** `spine`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-08-26 01:21

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | not run |

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

## Files

```
build/stages/spine/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/spine/2_assisted.cpp       AI filled the unported region(s)
build/source/spine.cpp      SHIPPED
```
