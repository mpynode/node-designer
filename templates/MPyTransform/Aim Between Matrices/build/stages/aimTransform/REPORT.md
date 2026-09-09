# aimTransform -- compile report

**Source node:** `aimTransform`  ·  **Base:** `MPxTransform`  ·  **Generated:** 2026-09-08 23:29

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **4.10x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
m0 = self.matrix0.asNumpy()
m1 = self.matrix1.asNumpy()
p0 = m0[3, :3]
p1 = m1[3, :3]
fwd = p1 - p0
length = float(np.linalg.norm(fwd))
if length < 1e-9:
    fwd = np.array([1.0, 0.0, 0.0])
else:
    fwd = fwd / length
up = np.array([0.0, 1.0, 0.0])
if abs(float(np.dot(fwd, up))) > 0.999:
    up = np.array([0.0, 0.0, 1.0])
side = np.cross(fwd, up)
side = side / (float(np.linalg.norm(side)) + 1e-12)
up2 = np.cross(side, fwd)
M = np.eye(4)
M[0, :3] = fwd
M[1, :3] = up2
M[2, :3] = side
M[3, :3] = 0.5 * (p0 + p1)
P = self.parentWorld.asNumpy()
self.local_matrix = M @ np.linalg.inv(P)
self.apply_rotate = True
self.apply_translate = True
self.apply_scale = True
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.008 ms** -> best **0.002 ms** (**4.10x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.013 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `matrix0 (matrix)`, `matrix1 (matrix)`, `parentWorld (matrix)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.008 ms | -- | -- |
| 01 | `scalarise_and_feed_datablock` | this node is 4x4 scalar math wearing an ndarray costume: replace the nd:: lowering with stack scalars, stop re-reading the three matrix inputs through MPlug when compute() already holds them, and cache inverse(L) on the exact bits of L | 3.00x | 3.73x | 11.0 min | ACCEPTED |
| 02 | `inplace_array_write` | write the 16 output-array elements in place instead of rebuilding them through an MArrayDataBuilder every tick; the node turned out to be entirely harness-bound, so the change is unmeasurable rather than a win | 1.25x | 4.10x | 10.6 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `inplace_array_write` -- predicted 1.25x, measured **4.10x**. This node is ELEMENTWISE and tiny -- the whole numerical job is 4x4 scalar math on three matrix inputs, and the polySphere/20000-element inputs the bench drives are never read by compute(). A previous porter had already collapsed the nd::Array lowering to stack scalars and cached inverse(L). That left exactly one repeated Maya-API cost in the hot path: MArrayDataBuilder + 16 x addElement() (each an index search/insert) + arrH.set() commit, rebuilding an output array whose shape is a fixed 0..15 and never changes. Replacing it with jumpToArrayElement(0) + next() over the existing elements, guarded by elementCount()==16 and a per-element elementIndex() check with a full builder fallback, removes the builder allocation and the 16 searches without touching a single written value.

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* authored @maya_test: 1/1 passed
* speed: compiled 0.018 ms vs interpreted 0.064 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/aimTransform/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/aimTransform/3_optimized/00_baseline.cpp
build/stages/aimTransform/3_optimized/01_scalarise_and_feed_datablock.cpp
build/stages/aimTransform/3_optimized/02_inplace_array_write.cpp
build/source/aimTransform.cpp      SHIPPED
```
