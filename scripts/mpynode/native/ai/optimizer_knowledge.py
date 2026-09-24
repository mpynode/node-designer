"""Optimizer knowledge: how to make a generated MPyNode C++ compute FASTER
without changing its numerical result.

This is the single source of truth the AI C++ optimizer injects into the LLM
system prompt. Every rule below was distilled from a verified case study: an
external agent hand-optimized the metaClay / mPyMesh node (an SDF-metaball ->
dual-marching-cubes mesh generator) to 134-365x end-to-end while keeping the
mesh topology byte-identical and vertex drift under 2e-14 -- i.e. inside the
project's 1e-4 scalar / 1e-3 geometric parity tolerance.

Like ``translation_knowledge`` this module is plain text + copy-pasteable C++ and
carries no Maya/Qt import, so it loads anywhere (headless, tests, in Maya). The
optimizer is ALWAYS gated: any rewrite ships only if it recompiles, still matches
the interpreted Python across many randomized scenes, AND is measurably faster --
otherwise the original C++ is kept unchanged (honest reject).
"""

from __future__ import annotations

import re

# Cross-compiler include hygiene, shared verbatim with the porter's system
# prompt. Defined in translation_knowledge so the rule has exactly one home;
# that module is the same plain-text/no-Maya shape as this one.
from .translation_knowledge import PORTABILITY_RULE


# ---------------------------------------------------------------------------
# The generalizable optimization catalog.
# ---------------------------------------------------------------------------

OPTIMIZER_GUIDE = """\
=== C++ OPTIMIZER GUIDE: make a generated MPyNode compute faster, same result ===
You are given a COMPLETE, already-correct C++ source for a native Maya plugin
node (it compiles and matches the interpreted Python). Rewrite it to run FASTER
while producing the SAME numbers. The file inlines an ~1600-line numpy-faithful
runtime header (`nd::` / `nd_runtime.h`); the compute helpers and the
`compute()`/`deform()`/`draw` body come AFTER it. Optimize the HOT compute code;
leave the runtime header and cold run-once glue alone.

WHERE THE TIME GOES -- SETTLE THE COMPLEXITY CLASS BEFORE ANYTHING ELSE:
0. WHAT SHAPE IS THIS NODE? Read the compute and count its loops against the
   input sizes. There are two shapes and they have different answers.
   * ELEMENTWISE / GRID -- O(output), a fixed amount of arithmetic per element.
     Here the arithmetic really is NOT the bottleneck: items 1-4 and catalog
     A-H below are the whole answer (that is the metaClay 100x).
   * QUERY -- an inner loop over a whole SECOND collection per output element
     (nearest point, nearest neighbour, containment, intersection, any "for
     each x, scan all y"). Cost is O(N x M) and NO amount of raw-pointer
     access, fusion or strength reduction changes that exponent. The lever is
     an ACCELERATION STRUCTURE over the scanned collection -- a BVH, a k-d
     tree, a uniform or hash grid, a sorted array plus binary search -- built
     ONCE and reused across queries -- and if the collection it indexes is not
     what animates, it wants to survive across evaluations too, as per-node
     derived state keyed on the inputs that built it (never the final output;
     a per-node member is not the global/static state CORRECTNESS bans).
     Measured on the voxelize node: replacing a linear closest-point scan with
     a binned-SAH BVH took one evaluation from 714 s to 0.125 s, and the
     sixteen rounds of constant-factor work that followed it each moved the
     total by single- or double-digit percent. If the node is query-shaped,
     spend the round on the structure, not on A-H.
   The PORTER is separately forbidden to replace a named structure with a scan
   (prompt._COMPLEXITY_RULE). Your job is the mirror image: a scan that reached
   you is either one the Python genuinely had or one the port introduced, and
   either way it is yours to accelerate -- so long as the result is identical.
Once the class is settled, the remaining cost is the `nd::` runtime's per-access
overhead in hot loops and per-op whole-array temporaries:
  1. Per-element scalar access. `nd::slice(a, {nd::Sl::at(i), ...}).item()` and
     `nd::assign(nd::slice(a, {...}), v)` each build a std::vector<Sl> and a fresh
     Array view (shared_ptr refcount + shape/strides vectors) PER ACCESS. Over an
     O(N^2)/O(N^3) grid this is hundreds of millions of heap allocations. This is
     the single biggest, most general lever.
  2. Whole-array temporaries + no fusion. A vectorized chain (e.g. sqrt/add/power/
     maximum over the whole grid, once per shape) allocates a full Array per op
     and sweeps memory once per op. Fusing the chain into ONE scalar loop kills
     all the intermediates and the repeated sweeps -- this delivered the bulk of
     the metaClay 100x+.
  3. Per-call constant tables. `nd::from_data({...})` for a call-invariant literal
     table re-allocates + copies it every compute(). Hoist to `static const`.
  4. libm pow for squares. `x**2` lowers to `std::pow(x, 2.0)` -- 1-2 orders of
     magnitude slower than a multiply, and on Apple libm ~1 ULP off numpy.

OPTIMIZATION CATALOG (apply the ones that fit; each is worth doing):
A. RAW-POINTER SCALAR ACCESS (huge, general). In hot loops, replace
   nd::slice(...).item() reads and nd::assign(nd::slice(...)) writes with direct
   buffer indexing. Fetch the pointer + offset + strides ONCE before the loop:
     const double* ND_RESTRICT p = a.data->data(); long o = a.offset;
     long s0 = a.strides[0], s1 = a.strides[1];   // ... for each axis used
   then read `p[o + i*s0 + j*s1]`. CRITICAL: honor the array's REAL offset +
   strides (an INPUT may be a non-contiguous view). Only linear-index (`buf[i*W+j]`)
   a buffer YOU just allocated C-order yourself. Keep the nd:: bit-packed path for
   `bool` arrays.
B. LOOP FUSION (huge, general). Collapse a multi-pass whole-grid nd:: elementwise
   chain into a SINGLE loop over scalar locals, computing each output element in
   one pass with no intermediate whole-array temporaries. Preserve the exact
   per-element evaluation and the visit ORDER (C-order / row-major, matching the
   nd:: odometer).
C. LOOP-INVARIANT HOIST / SCALAR-REPLACEMENT (large). Precompute per-entity
   constants ONCE into a small POD struct (a `struct SC { double sc0, rad, ...; };`
   vector), out of the innermost loop, instead of recomputing them as array ops
   inside it. Hoist index/offset arithmetic out of inner loops.
D. STATIC CONST TABLES (large, mechanical). A call-invariant literal table built
   via nd::from_data({...}) every call -> a function-scope `static const T NAME[] =
   {...};` (in .rodata, built once). Flatten a 2-D (R,C) table to 1-D indexed
   `NAME[r*C + c]`. Only for genuinely constant data (no closure over inputs).
E. STRENGTH REDUCTION (medium, mechanical, also a faithfulness FIX). `x**2` ->
   `x*x`; `x**3` -> `x*x*x`; `x**0.5` -> `std::sqrt(x)`; `x**-1` -> `1.0/x`. numpy's
   power ufunc special-cases these; std::pow(x,2.0) on Apple libm is ~1 ULP off,
   so x*x is BOTH faster AND more numpy-faithful. Only for integer/exact
   exponents; a runtime or non-integer exponent stays std::pow.
F. SCRATCH BUFFERS. Internal working grids created with nd::zeros/full then
   integer-indexed -> `std::vector<T>` with explicit C-order linear index (or a
   stack array for small fixed sizes). Small loop-local nd temporaries -> stack
   locals.
G. reserve() before push_back loops of known length; pass big args by `const&`;
   add ND_RESTRICT to raw pointers so -O2/-O3 auto-vectorizes.
H. GUARD + VERBATIM FALLBACK (safety + acceptance). When a fused / raw-pointer fast
   path assumes a memory layout, guard it and keep the ORIGINAL nd:: expression,
   verbatim, in the else branch:
     if (a.is_contiguous() /* + offset==0 if you linear-index */) { fast path }
     else { <the original nd:: expression, unchanged> }
   This keeps a non-contiguous INPUT view correct AND degrades a subtle
   stride/offset bug to the byte-identical original instead of a parity failure --
   worst case the fast path is skipped and the original runs. It is the single
   biggest safety + acceptance lever.
I. PER-ROW DERIVED STATE (large when one input animates piecemeal). A cached
   matrix whose row i depends only on row i of ONE input (a kernel/basis matrix
   over points, a per-vertex table) is not all-or-nothing: on a key miss compare
   that input ROW-WISE against the key that built the cache and rebuild only the
   rows that differ. One moved vertex then costs one row, not Nn x M; every kept
   row is the bit-identical output of unchanged inputs. Measured: rbfWrap
   7.5 ms -> 2.1 ms at 1562 x 1562 with one vertex moving per tick.
J. FUSE A BUILD INTO ITS CONSUMER when the built array is streamed exactly once
   and NOT reused across evaluations (a kernel matrix consumed by one matmul):
   compute each row in registers and consume it at once -- no materialised
   array, no second pass. Size-dependent: at 8k x 8k this beat storing the
   matrix; at 1.5k x 1.5k the per-row cache (I) wins 2x. Measure both.
K. OUTPUT MESH REUSE (Maya side). When the output topology is unchanged
   (byte-equal counts/indices), `MFnMesh::setPoints` on the mesh object already
   in the output handle instead of `MFnMeshData::create` + `MFnMesh::create`
   every tick. Guard on exact topology equality AND on MObject identity; rebuild
   from scratch on any mismatch. ~200 us of a 750 us tick at 1.5k vertices.

THREADING (one permitted shape, everything else is banned by CORRECTNESS): a
parallel MAP -- deterministic per-element write into a PRE-SIZED container, each
element a pure function of its index and read-only inputs, ZERO Maya API in the
worker, on a persistent per-node pool joined before compute() returns. This is
usually the LARGEST single win available: 10.2x-11.7x measured on the REFERENCE
machine (a 12P+4E Apple M4) for a per-vertex deformer sweep at N=10k-40k,
bit-identical to serial. That machine is not necessarily the one you are on:
size the pool from std::thread::hardware_concurrency() at runtime and never
assume a core count or a P/E-core split. Two measured facts change how you
apply it:
  * The chunk cursor MUST be a member of the pool, NEVER file-scope. Maya's EM
    evaluates independent nodes concurrently, so two instances of the same
    compiled node can be inside one region at once and each rewinds the other's
    cursor -- 30 of 30 trials dropped vertices, worst case 50% left unwritten.
    No single-instance test can see this.
  * That same EM concurrency caps the payoff: with 4-8 deformers evaluating at
    once the incremental gain falls to 1.5x-3.6x. Thread it anyway, but size the
    work against that number, not the single-node one.
Prefer a dynamic chunk cursor to an equal-block partition (+34-45%). Do NOT ship a
busy-spin pool -- it wins in isolation and collapses under load. Size gate: do not
open a parallel region for a pass whose serial cost is under ~50 us -- a condvar
region costs ~4.8 us at 2 threads, ~18.3 us at 8 and ~42.7 us at 16, i.e. it grows
with thread count (measured on the idle reference Apple M4; treat as a FLOOR under
contention, since the region nests inside Maya's own EM pool).

SCOPE: rewrite only the hot loops / the compute helpers. Do NOT edit the
nd_runtime.h header, the attribute registration, or the Maya marshalling. Leave
O(output)-once cold glue (final array assembly, boundary marshalling) on the
nd:: runtime -- converting it adds risk for no measurable gain. Do NOT blindly
raw-pointer every array: bulk one-shot whole-range writes stay on the nd:: path;
only scalarize the element-by-element HOT loops.

CONSERVATISM (this optimizer is gated -- align with the gate): the input is
already transpiler-optimized. Change ONLY the hot sections you can make faster
while staying within parity tolerance; leave every other line byte-for-byte
unchanged. A smaller correct speedup is ACCEPTED; a divergent rewrite is REJECTED
and wastes the whole round. When unsure a change stays in tolerance, do NOT make
it."""


# ---------------------------------------------------------------------------
# Correctness rules -- the hard gate the optimizer must never violate.
# ---------------------------------------------------------------------------

CORRECTNESS = """\
=== CORRECTNESS RULES (the optimizer is gated; a violation is rejected) ===
- The parity reference is the INTERPRETED numpy node, NOT the previous compiled
  plugin. Match numpy's result; do not merely reproduce the old C++ bits.
- Preserve floating-point EVALUATION and ACCUMULATION order exactly. Associate
  sums left-to-right as numpy does ((a+b)+c); reproduce matmul/reduction as
  acc=0; acc+=...  (this preserves -0.0 corners and per-op rounding). NEVER
  tree-reduce, reassociate, or reorder reductions.
- Keep divisions as divisions: do NOT rewrite a/b as a*(1.0/b) unless the source
  did. Only strength-reduce integer/exact powers (rule E).
- Preserve C-order (row-major) traversal order in any fused/rewritten loop, so
  the visit order matches the nd:: odometer.
- Raw-buffer access must honor the array's real offset+strides for INPUT views;
  linear-index only buffers you allocated C-order yourself. Getting this wrong is
  a SILENT parity break, not a crash.
- Static-const hoisting is valid ONLY for compile-time-constant literals with no
  closure over runtime inputs.
- The recompile MUST use -ffp-contract=off (once a mul and add fuse into one
  expression, FMA contraction rounds once instead of twice, drifts ~1 ULP, and
  can flip a >= comparison -- for geometry that changes topology). NEVER
  -ffast-math / -Ofast / /fp:fast. -O3 is fine only paired with -ffp-contract=off.
- Geometry: vertex/face COUNT and CONNECTIVITY (the flat index list) must be
  IDENTICAL; positions may differ only within tolerance (1e-4). Any topology diff
  is a hard fail.
- Output strictly 7-bit ASCII in code AND comments (no smart quotes, em/en dash,
  Unicode minus, arrows, ellipsis, non-breaking space); clang cannot lex non-ASCII
  outside a string literal.
- Determinism is preserved: compute() stays a pure function of its inputs -- no
  new global/static mutable state (a function-static `static const` read-only
  table is fine), no time()/random_device, no I/O.
- THREADING is the concrete case the accumulation-order and determinism rules
  above were written for, so it inherits both: no <thread>-based parallel
  REDUCTION (the parity gate is tolerance-based at 1e-3/1e-4, so a reassociated
  sum drifts ~1 ULP and PASSES while breaking byte-parity -- the gate cannot
  police this); no parallel append to a shared output whose order depends on
  completion order; no Maya API from a worker thread; no per-evaluate thread
  creation; the thread count must never affect the ANSWER. The one permitted
  shape (a parallel MAP) and its size gate are in the guide above.
- Scalarize np.maximum/np.minimum as the runtime's asymmetric ternary
  (a<b)?a:b / (a>b)?a:b in the ORIGINAL operand order -- never std::min/std::max/
  std::fmin/std::fmax (opposite NaN rule; they also differ on -0.0). A Min/Max
  reduction inits its accumulator to +INFINITY/-INFINITY and keeps the accumulator
  as the FIRST ternary operand.
- Preserve numpy negative-index wrap: when you replace slice().item()/atN() with a
  raw p[offset + i*stride] read, keep the `if (i < 0) i += shape[axis];` wrap
  wherever the index CAN be negative; drop it ONLY when the index is provably in
  [0, shape) (e.g. a 0..N for-loop).
- Skip a branch-dead computation only when PROVABLE (inside where(x>c, ...max(x,c)
  ...) the taken branch has max(x,c)==x, so log(x) may be computed directly). When
  fusing away a concat/stack, accumulate the column/row blocks in their original
  order.
- NEVER NARROW, NOR LOOSEN, A COMPARISON THAT RESOLVES A TIE. A test that only
  RANKS candidates looks like it has slack; at an exact tie the winner is decided
  by the last bit. Recomputing a double box/point distance in float changed which
  of two exactly-equidistant triangles won -- every value stayed inside tolerance
  and the ANSWER changed. So: any comparison that selects an index, a winner, or
  a branch keeps the source's TYPE, its DIRECTION, and its STRICTNESS (`<` vs
  `<=`, `>` vs `>=`). The inlined nd:: k-d tree is the worked example and states
  its own rule at the top of its section in this file -- read it before touching
  that code rather than re-deriving it. The -ffp-contract=off rule above is the
  same failure through a different door: both are a last-bit change that survives
  every tolerance check and flips a discrete choice.
- KEEP EVERY data.setClean(<attr>) the finalize has, reached on every path that
  returns MS::kSuccess. setAllClean() on an array handle cleans only its
  ELEMENTS; without the attribute-level call Maya's Evaluation Manager re-runs
  compute once per connected output array. Parity cannot see it, so a candidate
  that drops one is rejected before it is compiled."""


# A trimmed, worked few-shot exemplar: the metaClay per-shape struct-of-scalars
# precompute + single fused loop, distilled to the transferable shape.
FUSED_EXEMPLAR = """\
=== WORKED EXEMPLAR (the shape to aim for) ===
BEFORE (per shape: build ~8 whole-grid nd::Array temporaries + a matmul + libm
pow, then combine -- one memory sweep per op):
    // grid_points = stack(meshgrid(...));   local = matmul(grid_points, inv);
    // d = nd::sqrt(nd::add(nd::power(X,2), nd::power(Y,2))) ... per element, whole grid

AFTER (hoist per-shape constants once, then ONE fused scalar loop; x*x, raw
buffers, ND_RESTRICT, preserved acc order):
    struct SC { double r00,r01,r02, r10,r11,r12, r20,r21,r22, tx,ty,tz, rad; };
    std::vector<SC> S; S.reserve(nShapes);
    for (int s = 0; s < nShapes; ++s) { /* decompose once into S[s] */ }
    auto SQ = [](double v){ return v*v; };            // NOT std::pow(v,2.0)
    double* ND_RESTRICT out = field.data();
    for (int i = 0; i < nx; ++i)
      for (int j = 0; j < ny; ++j)
        for (int k = 0; k < nz; ++k) {
          double gx = /* world x of cell i,j,k */, gy = /*...*/, gz = /*...*/;
          double best = LARGE;
          for (int s = 0; s < nShapes; ++s) {
            const SC& c = S[s];
            double acc0 = 0.0; acc0 += c.r00*gx; acc0 += c.r10*gy; acc0 += c.r20*gz; // preserve order
            double X = acc0 - c.tx;   /* Y, Z similarly */
            double d = std::sqrt(SQ(X) + SQ(Y) + SQ(Z)) - c.rad;
            best = combine(best, d);  // same combine + order as the Python
          }
          out[(i*ny + j)*nz + k] = best;   // C-order index into a buffer we own
        }
Note: the whole marching-cubes cold assembly around this can STAY on nd:: --
only the O(grid) hot sampler was fused."""


_ASCII_RULE = (
    "ASCII ONLY -- CRITICAL: emit strictly 7-bit ASCII C++. NEVER use smart/curly "
    "quotes, em/en dashes, the Unicode minus, math symbols, arrows, ellipsis or "
    "non-breaking spaces -- clang cannot lex these outside a string literal. Use "
    "plain ASCII \" ' - * / <= >= != and -> in code AND comments."
)

_OUTPUT_CONTRACT = (
    "OUTPUT CONTRACT: return the COMPLETE optimized .cpp file and NOTHING else -- "
    "no prose, no explanation, no markdown outside a single ```cpp fenced block "
    "(or the bare file). It must be a full, compilable translation unit: keep the "
    "inlined nd_runtime header, every #include, the attribute registration, and "
    "the Maya entry points intact; change only the compute code. If you cannot "
    "make it faster while keeping the result identical, return the file UNCHANGED."
)


def _spec_context(spec: dict) -> str:
    """Compact reference block: the node's Python compute + init, for the model to
    check its rewrite against (the parity reference is this numpy, not the C++)."""
    spec    = spec or {}
    compute = (spec.get("compute") or "").strip()
    init    = (spec.get("init") or "").strip()
    parts   = []
    if compute:
        parts.append("Original Python compute (the parity reference -- match "
                     "THIS numpy result):\n```python\n%s\n```" % compute)
    if init:
        parts.append("Original Init (helpers/imports), for reference:\n"
                     "```python\n%s\n```" % init)
    return "\n\n".join(parts)


# Entry points every generated Maya plug-in has. Used only as a "did the model
# return a whole translation unit" signal, and only when the BASELINE has them.
_PLUGIN_ANCHORS = (
    "initializePlugin", "uninitializePlugin",
    # VP2 shading override (emit_vp2_override, spliced at (c.5) BEFORE the
    # optimizer runs). The compute-parity gate evaluates outColor through the DG
    # only, so it cannot see a candidate that deleted the Viewport 2.0 surface --
    # the node would still pass parity and ship shading flat. Baseline-calibrated
    # like every anchor here: a node without an override contains none of these
    # tokens, so nothing else is affected.
    "MPxShadingNodeOverride", "registerShadingNodeOverrideCreator",
    "deregisterShadingNodeOverrideCreator", "fragmentName",
    "getCustomMappings", "outputForConnection", "updateDG", "updateShader",
    "nd_texel", "addEventCallback",
)


def _code_only(src: str) -> str:
    """``src`` with C++ comments and string/char literals blanked to spaces
    (newlines preserved), leaving only real code.

    The portability scan MUST run on code only. hexAttribute's single
    ``__int128`` sits in a COMMENT explaining why the optimizer AVOIDED it and
    wrote a portable 64x64->128 multiply instead -- flagging that would reject a
    candidate for doing exactly the right thing. Raw strings are skipped whole:
    no generated node emits one today, but an embedded-source node could, and a
    desynced scanner produces false rejects.
    """
    out = []
    i, n = 0, len(src or "")
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j   = src.find("*/", i + 2)
            end = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:end]))
            i = end
            continue
        if c == "R" and i + 1 < n and src[i + 1] == '"':
            j = src.find("(", i + 2)
            if j > 0:
                closer = ")" + src[i + 2:j] + '"'
                k      = src.find(closer, j + 1)
                end    = n if k < 0 else k + len(closer)
                out.append("".join(ch if ch == "\n" else " "
                                   for ch in src[i:end]))
                i = end
                continue
        if c == '"' or c == "'":
            q = c
            out.append(" ")
            i += 1
            while i < n and src[i] != q and src[i] != "\n":
                out.append(" ")
                if src[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    i += 2
                else:
                    i += 1
            if i < n and src[i] == q:
                out.append(" ")
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


# A datablock setClean the optimizer may not drop. ``setAllClean()`` on an array
# handle cleans its ELEMENTS only; ``data.setClean(aX)`` cleans the attribute,
# and without it the Evaluation Manager re-runs compute once per connected array
# output (measured 2026-09-23: Spine 3 runs a frame -> 1, DNET 2 -> 1 and its
# solver drift gone). Neither parity nor the bench can see a dropped call -- the
# values are identical and the bench pulls a single element -- so it is gated
# here. Any receiver counts (``data.``, ``block.``, ``->``): candidates rename
# the datablock. A handle's no-argument ``setClean()`` is not matched.
_SETCLEAN_RE = re.compile(r"(?:\.|->)\s*setClean\s*\(\s*([A-Za-z_][\w:]*)\s*\)")


def setclean_targets(src: str) -> set:
    """The attributes / plugs ``src`` marks clean through a datablock
    ``setClean(<name>)`` call, comments and string literals excluded."""
    return set(_SETCLEAN_RE.findall(_code_only(src or "")))


# Constructs MSVC (cl.exe /std:c++17) rejects outright. PORTABILITY_RULE already
# TELLS the model the file is compiled by both Apple clang and MSVC, and it has
# been obeying that -- but nothing MEASURED it: the optimizer's own compile gate
# is clang on the host, which accepts every one of these happily, so a macOS-only
# rewrite could pass validation, compile, benchmark faster and ship.
_NONPORTABLE = (
    (re.compile(r"__attribute__\s*\("), "__attribute__"),
    (re.compile(r"\b__builtin_\w+"), "__builtin_*"),
    (re.compile(r"\btypeof\s*\("), "typeof"),
    (re.compile(r"\b__int128\b"), "__int128"),
    (re.compile(r"\balloca\s*\("), "alloca"),
    (re.compile(r"\bposix_memalign\s*\("), "posix_memalign"),
    (re.compile(r"#\s*pragma\s+omp\b"), "OpenMP pragma"),
    (re.compile(r"#\s*include\s*<\s*(?:arm_neon|immintrin|xmmintrin|emmintrin|"
                r"pmmintrin|smmintrin|avxintrin|unistd|dlfcn)\.?h?\s*>|"
                r"#\s*include\s*<\s*(?:Accelerate|simd)/[^>]*>"),
     "platform-specific header"),
    # Windows SAL. sal.h defines ~423 OBJECT-LIKE macros whose names begin with
    # a double underscore -- __out, __in, __inout, __range and friends -- so one
    # used as a variable name is not a style question but a preprocessor
    # collision: `MPoint* __out = &_cv[0];` becomes `MPoint* [SA_annotation] =
    # ...`, which MSVC reports as C2059 then C2337 "attribute not found" on
    # every later use, plus a bogus C4467 "ATL attributes are deprecated". clang
    # has no sal.h at all, so it compiled clean on the host, benchmarked faster
    # and SHIPPED -- exactly the hole this table exists to close.
    #
    # This cannot be a blanket "no __ prefix" rule: __-prefixed temporaries are
    # the transpiler's own convention (__i appears 12590 times, __L0 12530), so
    # it names the SAL families only. MEASURED against the installed SDK on
    # Windows 2026-08-31: of the project's 100 distinct __ identifiers exactly
    # ONE collided -- __out, in helixCurve. Re-derive the authoritative set with
    #   grep -hoE '^#define (__[A-Za-z_]\w*)' "<WindowsSdkDir>/shared/sal.h"
    (re.compile(r"\b__(?:in|out|inout)(?:_\w+)?\b"
                r"|\b__deref_\w+\b"
                r"|\b__(?:field|post|pre)_\w+\b"
                r"|\b__(?:[ebx]?count\w*|cap\w*)\b"
                r"|\b__(?:range|bound|inner_range|inner_bound|assume_bound)\b"
                r"|\b__(?:reserved|success|failure|on_failure|override)\b"
                r"|\b__(?:transfer|typefix|callback|allocator|deallocate)\b"
                r"|\b__(?:nonvolatile|volatile|specstrings)\b"),
     "a Windows SAL macro name (sal.h) used as an identifier"),
)

_PLATFORM_IF_RE = re.compile(
    r"^[ \t]*#[ \t]*if(?:def)?[ \t]+[^\n]*?"
    r"(?:__APPLE__|__MACH__|_WIN32|_WIN64|_MSC_VER|__linux__|__GNUC__|__clang__)",
    re.M)


def _unguarded_platform_blocks(code: str) -> int:
    """How many platform conditionals wrap real CODE with no ``#else``/``#elif``.

    Such a block gives one toolchain nothing at all. A block containing only
    ``#pragma`` lines is NOT one of these: py_to_cpp's fp-contract fusion guard
    is exactly that shape and needs no fallback (MSVC defaults to /fp:precise),
    and helixCurve's ``__APPLE__`` sincos fast path is legitimate precisely
    because it DOES carry an ``#else`` with plain std::cos/std::sin.
    """
    lines = code.splitlines()
    bad   = 0
    for m in _PLATFORM_IF_RE.finditer(code):
        start = code.count("\n", 0, m.start())
        depth, has_else, has_code = 0, False, False
        for i in range(start, len(lines)):
            s = lines[i].strip()
            if re.match(r"#\s*if", s):
                depth += 1
                continue
            if re.match(r"#\s*endif", s):
                depth -= 1
                if depth == 0:
                    break
                continue
            if depth == 1 and re.match(r"#\s*el(?:se|if)", s):
                has_else = True
                continue
            if s and not re.match(r"#\s*pragma\b", s):
                has_code = True
        if has_code and not has_else:
            bad += 1
    return bad


def implausible_reason(cand, baseline):
    """Why ``cand`` cannot be a valid replacement for ``baseline`` -- or None.

    A whole-file rewrite of a 3400-line source comes back truncated mid-function,
    or as PROSE describing a patch ("replace everything from X through its
    closing brace"). Both used to be written straight to the .cpp; the prose then
    became the input to the fix round, which understandably answered "I need the
    original source", and that answer was written to the .cpp too.

    Checks are calibrated against the baseline rather than hardcoded, so a node
    whose source legitimately lacks a token cannot be false-flagged. That holds
    for the clean bookkeeping too: a candidate may not drop a datablock
    ``setClean(<attr>)`` its baseline had (:func:`setclean_targets`). Injected
    into ``optimizer.optimize_cpp`` as ``validate_fn`` -- the engine itself stays
    content-agnostic so it remains testable with opaque stubs.
    """
    if not cand or not cand.strip():
        return "empty response"
    if "{" not in cand:                     # prose has no C++ shape at all
        return "not C++ (no braces)"
    # Truncation shows up as a brace imbalance. Only trust this when the baseline
    # itself balances -- braces inside string literals would skew both equally.
    if baseline.count("{") == baseline.count("}"):
        opens, closes = cand.count("{"), cand.count("}")
        if opens != closes:
            return "unbalanced braces (%d '{' vs %d '}') -- truncated" % (
                opens, closes)
    for tok in _PLUGIN_ANCHORS:
        if tok in baseline and tok not in cand:
            return "missing %s -- not a complete translation unit" % tok
    if len(cand) < 0.25 * len(baseline):
        return "only %d%% the size of the baseline -- truncated" % (
            100.0 * len(cand) / max(1, len(baseline)))
    # PORTABILITY. The generated .cpp ships as source a user compiles on their
    # own machine (build.sh / build.bat), so a candidate may not INTRODUCE code
    # only one toolchain accepts. Baseline-calibrated like every check above:
    # ND_RESTRICT's guarded __restrict__ is in every baseline and so can never
    # false-flag, and a node that already carries a construct keeps it.
    cand_code, base_code = _code_only(cand), _code_only(baseline)
    for rx, label in _NONPORTABLE:
        extra = len(rx.findall(cand_code)) - len(rx.findall(base_code))
        if extra > 0:
            return ("introduces %s (%d new) -- the .cpp must also compile with "
                    "MSVC cl.exe /std:c++17" % (label, extra))
    extra = (_unguarded_platform_blocks(cand_code)
             - _unguarded_platform_blocks(base_code))
    if extra > 0:
        return ("introduces %d platform conditional(s) with no #else -- one "
                "toolchain would get no code at all" % extra)
    lost = sorted(set(_SETCLEAN_RE.findall(base_code))
                  - set(_SETCLEAN_RE.findall(cand_code)))
    if lost:
        return ("drops data.setClean(%s) -- every output the baseline marks clean "
                "must stay marked clean, or the Evaluation Manager re-runs compute "
                "once per output array" % ", ".join(lost))
    return None


def build_optimize_prompt(cpp: str, spec: dict, bench_hint: str = None) -> tuple:
    """Return (system, user) prompts asking the model to optimize ``cpp``.

    FALLBACK PATH ONLY. The real optimizer is ``optimizer_agent``, which gives a
    tool-using agent the file plus a build+bench loop and lets it iterate; this
    one-shot "return the whole file as text" shape is what remains for providers
    with no headless tool mode (gemini/codex). It cannot measure anything, so it
    is a guess -- and on a large node the answer tends to truncate.

    ``cpp`` is the complete, already-correct C++ source. ``spec`` supplies the
    Python compute/init as the parity reference. ``bench_hint`` (optional) is a
    human note about where the time goes (e.g. current median ms / grid size)."""
    system = "\n\n".join([OPTIMIZER_GUIDE, CORRECTNESS, FUSED_EXEMPLAR,
                          _ASCII_RULE, PORTABILITY_RULE, _OUTPUT_CONTRACT])
    ctx  = _spec_context(spec)
    hint = ("\nProfiling hint: %s\n" % bench_hint) if bench_hint else ""
    user = (
        "Optimize this native Maya node for speed WITHOUT changing its numerical "
        "result (parity is re-verified against the interpreted Python across many "
        "randomized scenes, and the result is benchmarked -- a slower or divergent "
        "rewrite is rejected).\n\n"
        "%s%s\n\n"
        "Current C++ source (return the COMPLETE optimized file):\n"
        "```cpp\n%s\n```\n" % (ctx, hint, cpp)
    )
    return system, user


def build_fix_prompt(cpp: str, errors: str) -> tuple:
    """Return (system, user) prompts asking the model to repair a non-compiling
    optimized candidate, preserving the optimization intent and the same result.

    Still one-shot even on the agent path: repairing a compile error is a small
    bounded edit, not an optimization search."""
    system = "\n\n".join([OPTIMIZER_GUIDE, CORRECTNESS, _ASCII_RULE,
                          PORTABILITY_RULE, _OUTPUT_CONTRACT])
    user = (
        "The optimized C++ below did not compile. Fix ONLY what is needed to make "
        "it compile, keeping the optimization and the identical numerical result. "
        "Return the COMPLETE corrected .cpp file.\n\n"
        "Compiler errors:\n%s\n\nCurrent file:\n```cpp\n%s\n```\n"
        % ((errors or "")[-4000:], cpp)
    )
    return system, user
