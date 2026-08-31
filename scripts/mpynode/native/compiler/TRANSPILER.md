# Deterministic numpy → C++ transpiler

The native compile pipeline turns an mpynode's Python compute into a **pure-C++**
Maya `MPx*` plugin. This document describes the *deterministic* half of that
pipeline — the mechanical numpy-subset transpiler that lowers a compute body to
proven `nd::` runtime calls with **no embedded Python interpreter**.

## The HARD RULE

> A compiled node's compute must be **pure C++**, never Python under the hood — or
> the build is **rejected**.

The transpiler enforces this by construction: every Python construct is either
lowered to a proven `nd::` call **or** hard-rejected with a precise
`UnsupportedSpec`. There is no "best effort" path and no fallback interpreter. A
rejection is not a failure — `codegen` catches it and routes the node to the AI
porter, which **also** emits pure C++. So whichever path a node takes, the shipped
compute is pure C++. This is *translate-or-reject*.

## Pipeline

```
template.mpn / live node
  -> spec_extractor / mpn_spec_adapter   (node -> porter spec: inputs/outputs/compute/init/vars)
  -> codegen.generate_cpp                 (spec -> full MPx* C++ translation unit)
       |
       |  per family, BEFORE the AI-porter PORT region is emitted:
       +--> nd_lower.try_lower_*          (deterministic attempt)
       |        -> py_to_cpp.transpile_*  (numpy-subset AST -> nd:: C++)
       |        -> success: inline nd_runtime.h + deterministic body (NO port region)
       |        -> None (UnsupportedSpec): fall through to the AI porter
       |
  -> bundler.assemble                     (namespaced recompile -> .bundle/.mll)
```

`nd_runtime.h` is a header-only, dependency-free (no BLAS/LAPACK/Eigen) runtime
that mirrors numpy semantics bit-faithfully. On a deterministic lowering it is
**inlined** into the generated `.cpp` (see `codegen._nd_runtime_cpp`).

## Module map

| File | Role |
|------|------|
| `nd_runtime.h` | Header-only C++ runtime: `nd::Array<T>` (double/int64/bool), constructors, elementwise, reductions, matmul/broadcast, `diag`/`det`/`einsum`/`svd`, bit-exact `nd::MT19937`. |
| `py_to_cpp.py` | AST → C++ transpiler. `CppType` type/shape lattice, dtype promotion, per-op handlers. Rejects unsupported constructs. |
| `nd_lower.py` | Codegen integration: materialises `self.<attr>` inputs, drives `py_to_cpp.transpile_compute_block`, writes outputs. One `try_lower_*` per family. |
| `compiler/` (package; formerly `codegen.py`) | Emits the full MPx* translation unit; calls the `try_lower_*` short-circuits; inlines `nd_runtime.h`; applies the metadata banner. `node_scaffold.generate_cpp` is the dispatcher; the package `__init__` re-exports the complete former `codegen` surface. |
| `port_cache.py` | Content-addressed cache of the spliced `.cpp`. `PORTER_RECIPE_VERSION` force-invalidates after any change to generated C++ (incl. the inlined runtime). |
| `translation_knowledge.py` | Guidance handed to the AI porter for nodes that reject. |

## Supported op surface

### P0 — core (SP-1..SP-4)
Scalar arithmetic + control flow (for-range / while / if-elif-else / break /
continue / return / aug-assign); constructors (`zeros`/`ones`/`full`/`eye`/
`arange`/`linspace`/`array`/`*_like`/`expand_dims`); elementwise
(`+ - * / // % **`, unary neg, `maximum`/`minimum`/`clip`); ufuncs (`sin`…`sign`);
reductions (`sum`/`mean`/`max`/`min`, `linalg.norm`); linalg (`dot`/`cross`/
`matmul`/`@`); shape manip (`reshape`/`ravel`/`flatten`/`transpose`/`.T`/
`newaxis`/`astype`/`copy`); slicing + slice-assign;
`np.random.RandomState(seed).random(...)` via bit-exact `nd::MT19937`.

### P1 — masks, gather, structural (SP-5)
Boolean masks + array comparisons; `np.where`; fancy/gather indexing (integer-array
index + `np.take`); `nonzero` (tuple-unpacked); `concatenate`/`stack`/`hstack`/
`vstack`/`column_stack`; `tile`/`roll`; stencil neighbour reads; recursion-free
inline-INIT helper recovery (module-level `def`s become inline C++ lambdas);
persistent node-state locals.

### P2 — linalg on stacked 3×3 (SP-6)
`np.diag` (1-D ↔ 2-D); `np.linalg.det`; `np.einsum` with explicit
`'in,in->out'` subscripts (incl. diagonal + batched Procrustes/Kabsch forms);
`np.transpose(a, axes)`; and `np.linalg.svd` via **tuple-unpack**
`U, S, Vt = np.linalg.svd(a)`, mapped to a deterministic Jacobi `nd::svd` (no
BLAS/LAPACK). Batching over leading dims is supported for det/einsum/svd.

### The ndarray METHOD surface (SP-6)
`a.f(...)` and `np.f(a, ...)` are one operation written two ways, so both
spellings resolve through a single table (`py_to_cpp._ARRAY_OPS`) and cannot
drift apart — two if-chains is how `np.take`/`np.cumsum` ended up free-only and
`.copy()` method-only. Covered: `all`/`any`, `argmax`/`argmin`/`argsort`/`sort`,
`prod`/`cumprod`/`cumsum`, `std`/`var` (ddof), `ptp`, `round`, `squeeze`/
`swapaxes`/`diagonal`/`trace`, `repeat`/`compress`/`choose`/`searchsorted`/
`take`, `conj`, `byteswap`, `resize`, and the in-place statement forms
`sort`/`fill`/`put`/`itemset`/`setflags` (plus the free `np.put`). A method
numpy has and the table does not is a **test failure**
(`_tests/test_py_to_cpp_array_methods.py`), not a surprise at compile time.

Measured numpy behaviours the kernels reproduce, each of which the obvious C++
spelling gets wrong: `round` is half-to-**even** (`std::round` differs on 3 of
`[0.5,1.5,2.5,-0.5,-1.5]`) and with `decimals` reproduces numpy's
scale/rint/unscale (`round(1.2345,3) == 1.234`); `std`/`var` default to
**ddof=0**; `argmax`/`argmin` take the FIRST tie and a **NaN wins both**; NaN
sorts LAST; `sort`/`argsort` default to **axis=-1** while `cumsum`/`argmax`
default to **flatten**; `a.sort()` mutates in place (an aliased name must see
it) where `np.sort` copies; `a.resize()` zero-fills where `np.resize` repeats.

### Guards, `None`, and the last meshgrid/unique forms (ITEM 18)

`raise <Exception>('<literal>')` lowers to
`throw std::runtime_error("<Exception>: <literal>")` — **the runtime's own error
channel**, the same one `nd::reshape`/`nd::matmul` already use for a malformed
input. Both sides then do the same thing: stop, write no output. Only the literal
form lowers; a computed message (f-string, `%`-format) and a bare re-raise reject,
because losing the diagnostic text would be worse than porting the node.

`None` is not a value — it binds a **name**. `x = None`, and the
`getattr(self, '<absent>', None)` optional-input idiom, mark the local as None and
declare no C++ variable; only `x is None` / `x is not None` can read it, and both
fold to a compile-time `true`/`false` (a value that transpiles at all can never
*be* None). `== None` is deliberately **not** folded — it is an equality, not an
identity test. Rebinding in either direction (None → value, value → None) rejects:
one C++ variable cannot be two things. The dead branch is still transpiled, so a
node whose unreachable arm is unlowerable still rejects — conservative, never wrong.

`np.meshgrid` now covers `indexing='ij'` and the 3-input form. `'ij'` is the
transpose of `'xy'`, which for two inputs is exactly *swap the arguments and swap
which grid you ask for* (no new runtime); three inputs use `nd::meshgrid3`, which
takes the output shape plus the source axis per output, so `'ij'` is axes
`(0,1,2)` over `(nx,ny,nz)` and `'xy'` is axes `(1,0,2)` over `(ny,nx,nz)` —
numpy swaps only the first two.

`u, i = np.unique(a, return_index=True)` lowers to `nd::unique_index`. The index
contract is the whole point: numpy switches to a **stable** sort as soon as
indices are asked for, so the index reported for a repeated value is the
*smallest* original (flattened, C-order) one; `std::stable_sort` over a
permutation reproduces that exactly where the plain `std::sort` in `nd::unique`
would not. `return_inverse` / `return_counts` still reject.

### Rejected → AI porter (still pure C++)
`np.linalg.solve`; deferred `argwhere`; any
non-numeric I/O (matrix/string/hex/quaternion/float2/color, matrix arrays, raw
mesh/nurbs handles). `np.linalg.svd` **without** tuple-unpack and `np.einsum`
**without** an explicit `->` are rejected with a message pointing at the required
form.

Rejected ndarray methods, each for a stated reason rather than a gap
(`py_to_cpp._ARRAY_OP_REJECTS` carries the argument): `partition`/
`argpartition` (numpy leaves the order of non-kth elements **unspecified**, so
compiled and interpreted would disagree on the same input — a parity
impossibility); `view` (aliases its base, and returning a copy would silently
drop the write-through); `newbyteorder` (non-native byte order changes the
values); `tolist` (returns a Python list, where `+` concatenates — lowering it
to the array would silently turn `a.tolist() + b.tolist()` into elementwise
addition); `tobytes`/`tostring`, `dump`/`dumps`, `getfield`/`setfield`.

## Families (`nd_lower.try_lower_*`)

| Family | Entry | Notes |
|--------|-------|-------|
| generic compute | `try_lower_compute` | scalar / 1-D array / vector / (N,3) vec-array I/O. |
| geometry (mesh/curve/surface) | `try_lower_geo_compute` | fills the typed geo buffer; the flagship GoL mPyMesh lowers here. |
| deformer | `try_lower_deform` | `getPoints`/`setPoints` in-place mutate idiom. |
| transform | `try_lower_transform` | `asMatrix()` frame math. |
| locator / iksolver | (assessed, SP-4d) | draw/solve idioms stay on the AI-porter path; no deterministic template yet. |

Supported I/O (numeric only): scalar (`float/double/int/bool/enum/angle/time`),
1-D array → `(N,)`, vector/euler → `(3,)`, vector-array → `(N,3)`. Anything else
rejects with zero regression.

## Extending the transpiler

To add a new op deterministically (rather than leaving it on the porter path):

1. **Runtime** — add a numpy-faithful kernel to `nd_runtime.h`. Keep it
   dependency-free and deterministic (fixed accumulation order — no BLAS, no
   `-ffast-math` reliance). For linear algebra, prefer closed-form / Jacobi over
   anything needing an external solver.
2. **Transpiler** — wire a handler in `py_to_cpp._call_numpy` (or the method /
   ufunc dispatch), threading the `CppType` result (kind/dtype/rank) so downstream
   type inference stays correct. Remove the op from the `deferred` table.
3. **Fixtures** — add a parity fixture to `py_to_cpp_test.py` (`_F(name, src,
   **inputs)`); the oracle is the same source under numpy, compared with
   `np.allclose`. Add a matching **reject** fixture for any form you intentionally
   do *not* support.
4. **Block path** — if the op should be reachable from the geo/deform families,
   confirm it via `nd_lower_test.py` (it exercises `transpile_compute_block`, the
   production entry, not just the single-function harness).
5. **Cache** — bump `port_cache.PORTER_RECIPE_VERSION` so pre-existing cache
   entries (which inline the *old* runtime) miss cleanly and regenerate.

### Verifying a kernel is genuinely under test (red-green)

For kernels validated by convention-independent quantities (e.g. SVD, where
Jacobi ≠ LAPACK bit-for-bit but singular values / reconstruction / the unique
Kabsch rotation *are* stable), prove the test is non-vacuous: temporarily corrupt
the kernel in `nd_runtime.h`, confirm the relevant fixtures go RED, then revert
and confirm GREEN. A test that stays green under a corrupted kernel is not
testing it.

## Harnesses

All four are Maya-free (their own `MVector`/`MPoint` shims) but need numpy, so run
them under a `mayapy` interpreter. They compile real C++ with `clang++ -std=c++17
-O2 -I <native>` and compare against a numpy oracle.

```
MPYNODE_ROOT=$PWD PYTHONPATH=$PWD/scripts QT_QPA_PLATFORM=offscreen \
  <mayapy> scripts/mpynode/native/<harness>.py
```

| Harness | Proves | Success marker |
|---------|--------|----------------|
| `nd_runtime_test.py` | `nd::` ops vs numpy | `ALL PASS` |
| `nd_rng_test.py` | `nd::MT19937` bit-identical to numpy `RandomState` | `ALL BIT-EXACT` |
| `py_to_cpp_test.py` | AST transpiler parity + reject-or-lower | `ALL PASS` |
| `nd_lower_test.py` | family lowering (generic/geo/deform/xform + RNG) vs numpy + rejects | `ALL PASS` |

They are gate-protected by `_tests/test_native_transpiler_harnesses.py` (subprocess
under the gate's `mayapy`), so new fixtures ride along automatically. The flagship
`_tests/test_native_gol_e2e.py` additionally compiles the full GoL mPyMesh
translation unit against the running mayapy's Maya devkit headers (SKIPs — never
fails — with no compiler/devkit).

## Cache versioning

`port_cache` content-addresses the spliced `.cpp` by the spec (minus a small
deny-list) + provider + model + `PORTER_RECIPE_VERSION`. Because a
deterministically-lowered `.cpp` **inlines** `nd_runtime.h`, any change to the
runtime, codegen skeleton, or porter guidance that alters generated C++ for an
unchanged spec **must** bump `PORTER_RECIPE_VERSION` — otherwise a stale cache HIT
serves a `.cpp` with an outdated inlined runtime. History: v2 (locator mesh-input),
v3 (metadata banner), v4 (SP-4..SP-6 runtime growth: P1 masks/gather/structural,
P2 linalg diag/det/einsum/svd, batched matmul/broadcast), v5 (`unported`
escape-hatch prompt), v6 (complexity rule), v7 (ITEM-18 gap-fill: `raise` /
`is None` / meshgrid `'ij'`+3-input / `unique(return_index=True)`, plus
`nd::meshgrid3` + `nd::unique_index` in the inlined runtime).
