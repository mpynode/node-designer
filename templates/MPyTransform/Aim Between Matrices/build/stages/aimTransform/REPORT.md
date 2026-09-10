# aimTransform -- compile report

**Source node:** `aimTransform`  ·  **Base:** `MPxTransform`  ·  **Generated:** 2026-09-09 18:44

| stage | outcome |
|---|---|
| 1 Transpile | deterministic C++, no AI |
| 2 AI assist | not run (nothing to fill) |
| 3 AI optimize | **3.17x** over 3 round(s) -- 3 run of max 6, stopped: round 3 not-faster -- nothing new to compound from |

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

Bench scene: geo density 400 / array length 20000; noise floor 15 ms; moved per tick: `matrix0 (matrix)`, `matrix1 (matrix)`, `parentWorld (matrix)`; outputs checked (2 plug(s)); accepts re-timed against the incumbent on geo 40 / array 512 and rejected if slower there; baseline under the noise floor at the largest scene, so every accept had to clear 1.15x on two independent timings. baseline 0.013 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); measured anyway -- every accept must clear 1.15x on two independent timings.

Baseline **0.013 ms** -> best **0.004 ms** (**3.17x**).

Rounds: **3** run of at most 6; the loop stopped because round 3 not-faster -- nothing new to compound from.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.013 ms | -- | -- |
| 01 | `fused_scalar_kernel` | Replace the nd:: array chain (30-odd heap allocations per evaluate) and three findPlug/getValue/MFnMatrixData round trips with one fused scalar kernel that reads the three matrices straight from the datablock handles compute() already pulls; then write the 16 output elements in place instead of through a rebuilt MArrayDataBuilder. | 3.00x | 1.74x | 18.0 min | ACCEPTED |
| 02 | `lean_output_walk` | walk the 16 output elements with next() and check the logical index only at the two ends, so each element costs 3 Maya API calls instead of 4 | 1.10x | 3.17x | 10.2 min | ACCEPTED |
| 03 | `trim_preamble_gate_all` | test the plug before the RTTI cast so the base-class `matrix` pull skips it, and specialise the all-gates-open mix so the three unused base-row normalisations are never computed | 1.04x | 0.004 ms | 13.2 min | rejected: not faster |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `fused_scalar_kernel` -- predicted 3.00x, measured **1.74x**. This node is ELEMENTWISE with a fixed 4x4 output; the arithmetic is ~200 ns, so the 12 us tick is all per-access overhead: MFnDependencyNode + 3x findPlug by name + 3x MPlug::getValue DG pulls in desiredLocal(), then ~30 shared_ptr/vector allocations for slice/norm/cross/eye/assign/inv/matmul temporaries. Keeping every operation in the same order on registers (sub, acc=acc+x*x norm, dot1d acc+=, cross formula, Gauss-Jordan inv with the 1e-12 pivot guard, matmul2d_fixed acc+=) is bit-identical under -ffp-contract=off / /fp:precise, so the kernel can be a plain function with zero allocations.
* `lean_output_walk` -- predicted 1.10x, measured **3.17x**. compute() is ~85 Maya API calls and no real arithmetic (three 4x4 reads, one 4x4 inverse, sixteen scalar writes); the 16-element write loop is 64 of those calls, so trimming 14 redundant elementIndex() checks (16 sorted distinct indices with first==0 and last==15 are exactly 0..15) should be the largest removable share. Every input moves every tick, so no derived state survives between evaluations and caching cannot apply.
* `trim_preamble_gate_all` -- predicted 1.04x, **rejected: not faster**. incumbent under the noise floor: 1.15x required, measured 1.14x

### Rejected rounds

* `trim_preamble_gate_all` -- rejected: not faster. incumbent under the noise floor: 1.15x required, measured 1.14x

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* authored @maya_test: 1/1 passed
* speed: compiled 0.015 ms vs interpreted 0.054 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/aimTransform/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/aimTransform/3_optimized/00_baseline.cpp
build/stages/aimTransform/3_optimized/01_fused_scalar_kernel.cpp
build/stages/aimTransform/3_optimized/02_lean_output_walk.cpp
build/stages/aimTransform/3_optimized/03_trim_preamble_gate_all.cpp
build/source/aimTransform.cpp      SHIPPED
```
