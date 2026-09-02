# Lowering `MatrixView` to C++ — design note

**Status: implemented at `PORTER_RECIPE_VERSION` 26.** Fifteen methods lower;
the design below is what shipped. Read `native/compiler/TRANSPILER.md` first.

What is NOT done, and must be before the tree is consistent: the checked-in
build artifacts have not been regenerated, so the stage-1 freshness gate is red
until `tools/build_compiled_templates.sh` runs. See "The rebuild debt" below —
that debt predates this change, and one rebuild settles both.

## The gap

`MatrixView` (`_common/plugs/promoted_types.py`) is what a `matrix` input hands
an expression. It wraps an api2 `MMatrix` plus a parallel
`MTransformationMatrix` and exposes **42 public methods**.

`py_to_cpp.py` used to lower exactly **one** of them — `asNumpy()`, and that as
an identity passthrough, because the receiver is already the materialised `nd`
(4,4). Every other method had no entry in `_ARRAY_OPS`, so a compute that called
one fell through to the stage-2 AI porter instead of transpiling
deterministically. Fifteen now lower.

The system prompt (`ui/llm/system_prompt.py`) used to tell the assistant to
stay on plain numpy math for a node headed to *Convert to C++*. That caveat is
gone, replaced by the setter/pivot exclusion. It did not have to be spotted by
hand: `test_only_asnumpy_is_lowered` was written to fail on the day the claim
stopped being true, and it did, which is what forced the prompt to be corrected
in the same change. It now reads in the opposite direction, as
`test_the_advertised_methods_actually_lower`.

## The 42 methods split three ways

| Tier | Methods | What it needs |
|---|---|---|
| **A** | `translation`, `transpose`, `inverse`, `getElement`, `asNumpy` | Nothing new. `translation()` is a row-3 slice, `inverse()` is `nd::inv` (any N). Dispatch wiring only |
| **C** | `rotation()`, `rotation(axes=N)`, `scale`, `shear`, `rotationOrder`, `isSingular`, `det3x3`, `det4x4`, `asRotateMatrix`, `asScaleMatrix`, `asMatrixInverse`, `adjoint`, `homogenize` | Maya's own semantics |

There is no Tier B. It was going to be a 4×4 arm for `nd::det`, and that
turned out to be both unnecessary and expensive: `MMatrix` ships `det4x4()`
and `det3x3()` natively, so Tier C gives bit-exact answers instead of
1.3e-13-close ones — and, decisively, it leaves `nd_runtime.h` untouched.
That header is inlined **verbatim** into every generated `.cpp` that lowers,
so extending `nd::det` changed the bytes of **24 of the 38** checked-in
stage-1 artifacts and would have forced a multi-hour rebuild of trees that
never touch a matrix. Measured: **0** shipped templates call any MatrixView
method, so routing them through Maya costs zero regenerated artifacts.
The lesson generalises — before touching `nd_runtime.h`, count what inlines it.

**Out of scope, and why.** The in-place setters (`setTranslation`,
`setRotation`, `setScale`, `setShear`, `reorderRotation`) mutate the receiver —
but a lowered compute materialises a matrix input into an `nd` **copy**, so
mutating it has no downstream meaning and the interpreted and compiled nodes
would quietly disagree. The eight pivot accessors carry `balance=` semantics
that should not be guessed at. Excluding both leaves **16 methods** covered,
of which **15 needed new `_ARRAY_OPS` entries** — `transpose` was already
handled correctly by the existing numpy array handler on a (4,4).

## Tier C does not need a reimplementation

The generated `.cpp` **is a Maya plug-in**, so it can call Maya and be bit-exact
by construction rather than to a tolerance. The pieces are already in place:

* `bundler.py` auto-includes `MMatrix`, `MEulerRotation`, `MQuaternion`,
  `MVector` on demand.
* `emit_iksolver.py` and `emit_locator.py` already include
  `maya/MTransformationMatrix.h`; 39 shipped generated sources include
  `maya/MMatrix.h`.
* `nd_lower.py :: _materialise_input` already converts `MMatrix src` to an `nd`
  (4,4) element-wise. The reverse is the same loop.

Reimplementing Maya's decomposition in `nd::` would instead be a standing
parity liability: negative-scale handling, shear extraction and rotate-order
reordering are not conventions worth re-deriving.

### Hard constraint: the bridge cannot live in `nd_runtime.h`

The eleven transpiler oracle harnesses under `tests/compile/native/` compile
that header with `-std=c++17 -I <repo>` and **no Maya include path** — they
carry their own `MVector`/`MPoint` shims (`TRANSPILER.md`). A single `maya/`
include in the runtime turns all eleven red.

The bridge therefore rides **on top of** the runtime, exactly the way
`kernels/nd_io_cpp.py` does: its own include guard so bundling several nodes
into one translation unit stays idempotent, emitted only when a spec needs it.

### Gate on the input table AND the method name

`nd_io_cpp.spec_uses_ndio` matches on SOURCE rather than transpiler state,
because the include list is decided before compute lowering. The Maya bridge
must do the same — but a bare method-name scan is far more collision-prone than
`ndio.read`: `.scale(` is a common spelling on unrelated objects, and a false
positive drags Maya headers into files that never touch a matrix.

Require **both**: the spec declares a `matrix` input (scalar or array), *and*
the source mentions one of the Tier C names. Only a matrix plug can produce a
`MatrixView`, so the input check is the discriminating half. A matrix input
using only `translation()` must NOT pull the bridge in — that method is Tier A.

### The rotate-order trap

`MatrixView` uses two different numberings in the same class. Mirror both
exactly; do not "correct" either, because matching the interpreted node beats
being self-consistent.

| Call | Numbering |
|---|---|
| `rotation(axes=N)` | **0-based** Maya rotate-order index — `0=xyz 1=yzx 2=zxy 3=xzy 4=yxz 5=zyx`, the same indices a `rotateOrder` enum plug uses |
| `rotationOrder()` | **1-based** `MTransformationMatrix::RotationOrder` — `kInvalid=0`, `kXYZ=1` |

In C++, spell the index-to-`MEulerRotation::RotationOrder` mapping out in a
`switch` rather than casting the integer. Note also that the Python calls
api2 `MTransformationMatrix.rotation()`, which returns an `MEulerRotation`;
the C++ method of that name returns an `MQuaternion`, and the euler equivalent
is `eulerRotation()`. `scale`/`shear` default to `MSpace::kTransform`, matching
the Python's `space=None`.

## The 4×4 determinant (Tier B), verified

Extend `nd::det` with an `r == 4` arm and leave the 1×1–3×3 arms
**byte-identical** — editing them would move generated output for nodes that
already lower `det`, producing freshness churn unrelated to the change.

Laplace on rows 0–1, via the six 2×2 minors of the top two rows paired with the
six of the bottom two. Fixed evaluation order, so it is bit-reproducible run to
run, which the stage-1 gate depends on:

```
s0 = E(0,0)*E(1,1) - E(1,0)*E(0,1)     c5 = E(2,2)*E(3,3) - E(3,2)*E(2,3)
s1 = E(0,0)*E(1,2) - E(1,0)*E(0,2)     c4 = E(2,1)*E(3,3) - E(3,1)*E(2,3)
s2 = E(0,0)*E(1,3) - E(1,0)*E(0,3)     c3 = E(2,1)*E(3,2) - E(3,1)*E(2,2)
s3 = E(0,1)*E(1,2) - E(1,1)*E(0,2)     c2 = E(2,0)*E(3,3) - E(3,0)*E(2,3)
s4 = E(0,1)*E(1,3) - E(1,1)*E(0,3)     c1 = E(2,0)*E(3,2) - E(3,0)*E(2,2)
s5 = E(0,2)*E(1,3) - E(1,2)*E(0,3)     c0 = E(2,0)*E(3,1) - E(3,0)*E(2,1)

det = s0*c5 - s1*c4 + s2*c3 + s3*c2 - s4*c1 + s5*c0
```

Measured against `np.linalg.det` over 2000 random 4×4 matrices in
`[-5, 5]`: **worst relative error 1.3e-13**, well inside the ~1e-12 the header
already documents for `nd::inv`. Identity, pure-translate and
`diag(2,3,4,1)` are exact.

## Cost — the code is not the expensive part

| Item | Cost |
|---|---|
| Transpiler change | Done: 15 `_ARRAY_OPS` entries, 15 `_op_*` handlers, the `_mv_recv` rank guard that rejects with `UnsupportedSpec` rather than emitting wrong code, and `kernels/nd_maya_cpp.py` |
| `PORTER_RECIPE_VERSION` bump | Done, `"25"` → `"26"`. **Mandatory**: an emitter-only change is invisible to the cache key, so without it every rebuild silently serves the old `.cpp`. `docs/ARCHITECTURE.md` said `"24"` and has been corrected |
| Regenerate the build trees | `tools/build_compiled_templates.sh` — hours, needs mayapy **and** an authenticated Claude CLI |
| Both freshness gates | re-run |
| Parity sweep | The shipped fixtures are macOS `.bundle`s; `tools\run_parity_sweep.bat` needs a local fixture rebuild first and remains unproven |

## The rebuild debt already exists

Measured on a **clean tree** with no local modifications:

```
manifests : 40      checked : 76
fresh     : 27      stale   : 49      error : 0      UNGATED : 0
```

Every one of the 49 differs **only at line 3** — the `// build: <hash12>`
determinism stamp — with byte-identical line counts (`4789 -> 4789`). That is
the signature of artifacts generated under an older `PORTER_RECIPE_VERSION`,
not of drifted codegen. It is also why
`tests/compile/freshness/test_stage1_codegen_freshness.py` currently fails
against its empty ratchet baseline.

The practical consequence: the rebuild this work needs is **not a tax the
change imposes** — the tree already owes it. One rebuild settles both.

Do not widen the baseline to paper over it. `--write-baseline` is the only
sanctioned widening and it exists to leave a reviewable diff, not to silence
the gate.

## Environment notes (this machine)

* `cl.exe` from Visual Studio 2022 Professional; devkits for Maya **2022** and
  **2025**. A compile can genuinely be verified here.
* When the rebuild runs, target **Maya 2025 only** — that is the version the
  Node Designer is actually being driven in, and it halves both wall time and
  LLM spend versus `compile_plugin_multi` across both installs.
