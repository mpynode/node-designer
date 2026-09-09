# hexAttribute -- compile report

**Source node:** `hexAttribute`  ·  **Base:** `MPxNode`  ·  **Generated:** 2026-09-08 23:28

| stage | outcome |
|---|---|
| 1 Transpile | emitted, with region(s) the transpiler could not lower |
| 2 AI assist | ran -- no unresolved regions |
| 3 AI optimize | **13.67x** over 2 round(s) -- re-measured: unmeasurable under the gate |

## The Python this was generated from

```python
# Name: Text Mesh Generator  (numpy-first port)
# Author: Eric Vignola - eric.vignola@gmail.com
# The `output` attribute is typed `hex`: assign plain text and the attr
# auto-encodes it to the space-separated UTF-8 hex a Maya `type` node
# consumes as mesh text -- no manual unicode -> hex step needed.

# Convert XYZ input (a numpy 3-vector) to rounded strings.
self.output = 'DRAG ME AROUND!\n'
self.output += 'X: %s\n' % round(float(self.inPosition[0]), self.decimals)
self.output += 'Y: %s\n' % round(float(self.inPosition[1]), self.decimals)
self.output += 'Z: %s\n' % round(float(self.inPosition[2]), self.decimals)
```

## Optimization

Parity gate: `authored+pointwise`. Every accepted round was re-checked against the interpreted Python before it was allowed to win. Where a node's generic pointwise parity SKIPS -- a deformer writes through the native `outputGeometry`, which the scalar harness cannot read -- the authored `@maya_test` is the ONLY gate, so treat those rows as behavioural checks rather than numerical ones.

Bench scene: not recorded (ledger predates the scene record; no noise-floor gate, no per-tick perturbation check and no output fingerprint applied to these rounds).

Baseline **0.021 ms** -> best **0.002 ms** (**13.67x**).

**Re-measured 2026-09-08** under the gated harness (noise floor, animated-input perturbation, output fingerprint), geo density 400 / array length 20000: **unmeasurable** -- baseline 0.025 ms is below the 15 ms noise floor even at the largest bench scene (geo=400 array=20000); nothing this small can be optimized against measurably. The speedup above was taken before the gate existed and cannot be reproduced under it. Moved per tick: `decimals (int)`, `inPosition (vector)`.

| # | change | theme | predicted | measured | time | outcome |
|---|---|---|---|---|---|---|
| 00 | `--` | -- | -- | 0.021 ms | -- | -- |
| 01 | `limb_decimal_expansion` | the node is three Python float-to-string conversions, and all of its time went into expanding a double's exact decimal one base-10 digit at a time -- carry it in base-1e9 limbs instead, then stop re-parsing candidates that are already known to round-trip | 3.50x | 10.25x | 16.4 min | ACCEPTED |
| 02 | `dyadic_round_no_bignum` | Python's round()/repr() were driving a base-1e9 exact-decimal expansion six times per compute; both collapse to one 64x64->128 multiply plus a shift-with-sticky, because x*10^nd is the dyadic rational (m*5^nd)*2^(e+nd) and every decimal the node emits is short enough for Clinger's exactly-representable window. | 2.50x | 13.67x | 14.1 min | ACCEPTED |

### Predicted vs measured

The rounds where the guess and the stopwatch disagreed. These are the transferable part -- a prediction that missed says more about the machine than one that landed.

* `limb_decimal_expansion` -- predicted 3.50x, measured **10.25x**. This is an ELEMENTWISE node with an output of three numbers, not a QUERY node, so there is no acceleration structure to build: the entire 20.1 us is fixed per-call arithmetic. nd_exact() reconstructs the exact decimal expansion of a double via `reps` passes of a schoolbook multiply over a growing base-10 digit vector -- O(reps^2) with reps ~= 52 for a typical mantissa, and it is called SIX times per compute (once inside nd_py_round and once inside nd_py_repr, per component). Carrying the same exact integer in base-1e9 limbs and multiplying by 5^12 / 2^29 per pass does identical arithmetic with ~100x fewer inner operations. The second cost is nd_py_repr's shortest-round-trip search, which scans p = 1, 2, 3, ... and does a std::stod plus several substr/append allocations per step, so it pays ~8 parses per component. But nd_py_round has ALREADY produced a decimal D with a known digit count and has ALREADY handed D to strtod -- so D's digit count is an upper bound on the shortest length, and D's own round-trip result is known by construction. Probe there instead of at p = 1.
* `dyadic_round_no_bignum` -- predicted 2.50x, measured **13.67x**. This node is ELEMENTWISE and tiny (3 doubles in, one ~180-char hex string out), so there is no acceleration structure to build and no array to thread -- the whole cost is inside nd_exact() and strtod(). nd_exact() builds all ~55 exact decimal digits of a double as a bignum and is called 6x per compute (once per coordinate in round(), once more in repr()); strtod() is called ~6x to re-parse the decimals just produced. Replacing the bignum with exact 128-bit integer arithmetic and strtod with a single correctly-rounded multiply/divide should remove ~3/4 of the compute.

## Verification

* parity: **pass**  (maxerr 0.0, tol 0.0001)
* authored @maya_test: 1/1 passed
* speed: compiled 0.015 ms vs interpreted 0.141 ms (best of 3, geo 140 / array 5000)

## Files

```
build/stages/hexAttribute/1_transpiled.cpp     deterministic transpile (no AI)
build/stages/hexAttribute/2_assisted.cpp       AI filled the unported region(s)
build/stages/hexAttribute/3_optimized/00_baseline.cpp
build/stages/hexAttribute/3_optimized/01_limb_decimal_expansion.cpp
build/stages/hexAttribute/3_optimized/02_dyadic_round_no_bignum.cpp
build/source/hexAttribute.cpp      SHIPPED
```
