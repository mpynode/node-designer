"""Translation knowledge: how to reverse-engineer Python numerical code
(numpy / scipy / numba / PIL / cv2 / skimage) into deterministic C++ for a
native Maya plugin.

This module is the single source of truth the AI porter injects into the LLM
system prompt. Every C++ helper below was compiled with Apple clang 21 and
checked numerically against the Python original during research:
  * Bessel j0/j1 (A&S / Numerical-Recipes polynomial): max abs err ~5e-9 vs
    scipy.special.j0/j1 on [0, 40] -> port parity bounded at ~1e-6.
  * erf/erfc/tgamma/lgamma map to std::* and are EXACT vs scipy.special.
  * Dense partial-pivot LU (lu_solve) reproduces np.linalg.solve to ~1e-17.
  * Cox-de Boor basisFuns/findSpan + de Boor reproduce scipy B-spline bases to
    machine precision.

The guidance is split into sections so the porter can inject only what a given
node actually imports (see ``for_spec``). The whole thing is plain text +
copy-pasteable C++; it carries no Maya/Qt import so it loads anywhere.
"""

from __future__ import annotations

import re

# Single source of truth for "what counts as RNG": reuse spec_extractor's patterns
# so the parity-skip detector and the RANDOM translation trigger below can NEVER
# drift -- a node that skips parity must always get the <random> guidance.
# spec_extractor is pure (json/re only; lazy maya), so this import is cycle-free.
from mpynode.native.spec import spec_extractor as _spec_extractor


# ---------------------------------------------------------------------------
# Cross-compiler portability. Shared by BOTH prompt-building paths (the porter's
# build_prompt and the optimizer's build_optimize_prompt / agent task brief) so
# the rule exists in exactly one place.
#
# Why it is here at all: the only compile gate is a macOS clang run, and libc++
# leaks transitive includes where the MSVC STL does not -- so "std::mutex with
# no <mutex>" is rc=0 here and C2039 on Windows, invisible to every check we
# have. This is PROPHYLACTIC: 0 of the 42 shipped mega TUs actually has the
# defect, and the one optimizer round that added a mutex+atomic cache added both
# includes unprompted. It costs ~80 tokens against a prompt budget nd_runtime.h
# already dominates, which is why it is this short.
# ---------------------------------------------------------------------------

PORTABILITY_RULE = (
    "PORTABLE INCLUDES: this file is compiled by BOTH Apple clang (libc++) and "
    "MSVC cl.exe /std:c++17. libc++ satisfies many facilities through "
    "TRANSITIVE includes and the MSVC STL does not, so code that builds clean "
    "on macOS can fail to compile on Windows. INCLUDE EVERY HEADER YOU USE, "
    "even if it already builds: <mutex> for mutex/lock_guard/unique_lock/"
    "call_once, <atomic> for atomic and the memory_order constants, "
    "<condition_variable>, <thread>, <array> for std::array, <limits> for "
    "numeric_limits, <sstream>, <cstring>, <cstdint>. Restrict yourself to the "
    "C++17 standard library and the Maya SDK -- no platform-specific or "
    "third-party headers."
)


# ---------------------------------------------------------------------------
# Always-on core: numpy -> C++ and the determinism rules every port must obey.
# ---------------------------------------------------------------------------

CORE = """\
=== TRANSLATION GUIDE: Python numerical code -> deterministic C++ ===
General method: the Python is the SPEC. Reverse-engineer the INTENT, not the
byte layout. Vectorized array math becomes explicit C++ loops; the result must
be numerically identical (verified by an automated parity probe).

DETERMINISM (hard rules):
- Compute in `double`; cast to float ONLY at the Maya setter (h.setFloat((float)v)).
  Use a `double` output attr if you need full double precision end-to-end.
- RANDOMNESS IS SUPPORTED: numpy.random / random / secrets map to C++ <random>
  (see the RANDOM section + NdRng helper). It is NOT bit-identical to Python's
  PRNG and is not pointwise parity-checked -- but you MUST still make compute() a
  pure function of its inputs (seed the engine deterministically from inputs, no
  global/static engine, no time()/random_device), or the node flickers in the DG.
- NO file/scene/network/GUI/GPU. Everything comes from the in-scope locals.
- Same input -> same output, every run (RNG included: same inputs/seed -> same
  draws).

numpy -> C++ cheatsheet (compute element-wise in loops):
- Broadcasting: (N,1) op (1,M) -> nested loop over i in [0,N), j in [0,M).
- a @ b / np.dot / np.matmul -> explicit row*col sums (or MMatrix for 4x4).
- np.linspace(a,b,n): INCLUSIVE, step=(b-a)/(n-1), x_i=a+i*step (n>=2; n==1 -> a).
- np.arange(a,b,s): HALF-OPEN [a,b), count=ceil((b-a)/s).
- np.cumsum: INCLUSIVE running sum (out[i]=out[i-1]+x[i]).
- np.argmax/argmin: returns the FIRST max/min index on ties.
- np.clip(x,lo,hi) -> std::min(std::max(x,lo),hi).
- np.where(cond,a,b) -> ternary cond?a:b (element-wise).
- np.meshgrid(x,y) default indexing='xy' -> shape (len(y),len(x)); 'ij' -> (len(x),len(y)).
- np.tile repeats the whole array; np.repeat repeats each element in place -- different!
- np.unique(x,return_inverse=True): ASCENDING-sorted unique + an inverse remap;
  in C++ sort a copy, std::unique, then map original->index (std::map<int,int>).
- np.round / np.rint use BANKER'S rounding (round-half-to-EVEN), NOT std::round
  (which is half-away-from-zero). If the code rounds, replicate half-to-even:
    double r=std::floor(x+0.5); if(std::fabs(x+0.5-r)<1e-12 && std::fmod(r,2.0)!=0) r-=1.0;
- Python floor-division // and % follow the DIVISOR's sign (Python: -7 % 3 == 2).
  C++ / and % truncate toward zero. Replicate Python %:
    double pymod(double a,double b){ double m=std::fmod(a,b); if(m!=0 && (m<0)!=(b<0)) m+=b; return m; }
- Reductions (sum/mean/dot/norm) written as a serial Python loop are deterministic
  -> translate 1:1. (See NUMBA for prange/parallel reductions.)
- Bake Init-defined constants (control points, palettes, lookup tables) as C++
  literals / std::vector, reproducing their numpy expressions faithfully.

TYPE MAPPING (Python -> C++ for locals / helper signatures; pass big args const&):
- a single float / int           -> double (by value); a bool -> bool.
- a 3-component vector / point    -> MVector (const MVector& as a param).
- a list / 1-D array of numbers   -> std::vector<double> (const std::vector<double>&).
- a list of vectors / (N,3) array -> std::vector<MVector> (const std::vector<MVector>&).
- a 4x4 matrix                    -> MMatrix (const MMatrix&).
- a list-of-lists (jagged)        -> std::vector<std::vector<double>>.
  (Prefer MVector over MPoint for pure math -- MPoint isn't always in scope.)

PERFORMANCE (apply AFTER correctness; NEVER at the cost of determinism):
- Pass large args (std::vector, MVector, MMatrix, MString) by `const&`; return
  small results by value.
- reserve() a std::vector before a push_back loop of known length.
- Hoist loop-invariant computations out of inner loops; cache v.size() in a local.
- Reuse buffers instead of allocating inside the hot loop.
- DO NOT reorder floating-point reductions, parallelize, or enable -ffast-math /
  FMA -- keep the serial IEEE order the parity probe expects (the Jacobi /
  double-buffer rule above still holds)."""


# ---------------------------------------------------------------------------
# numba (JIT) -- decorators are pure perf sugar; the body is plain numpy.
# ---------------------------------------------------------------------------

NUMBA = """\
=== numba (@njit/@jit/@guvectorize/@stencil, prange) ===
Strip ALL numba decorators and translate the body as ordinary C++ loops.
- @njit/@jit/@vectorize/@guvectorize/@stencil -> DELETE the decorator.
- numba.prange(n) -> plain `for (int i=0;i<n;++i)`.
- nb.typed.List -> std::vector; nb.typed.Dict -> std::unordered_map.
- numba.float64/int64 -> double / long long.
CRITICAL -- a prange loop is JACOBI (it reads the input array and writes a
SEPARATE output array; it cannot be order-dependent or it would race). Preserve
that double-buffering EXACTLY: read `src`, write `dst`, then swap. Do NOT update
in place (that is Gauss-Seidel and gives different numbers; verified divergent).
Build any adjacency in a canonical (sorted-unique) order so C++ and numpy iterate
identically.
TOLERANCE -- a value reduced across a prange (sum/dot/norm split per-thread then
combined) reorders float adds; expect ~1e-5 abs error, not bit-exact. fastmath=True
likewise changes low bits -- match with ordinary IEEE C++ + ~1e-5 tol (do NOT
enable -ffast-math; keep the plugin deterministic). Per-element prange loops ARE
bit-exact. numba.cuda/@cuda.jit/roc/objmode = hard blocker (GPU / Python callback)."""


# ---------------------------------------------------------------------------
# scipy.special -- erf family -> std::*; Bessel -> A&S polynomial helper.
# ---------------------------------------------------------------------------

SPECIAL = """\
=== scipy.special ===
- erf/erfc -> std::erf/std::erfc (EXACT vs scipy; verified bit-identical).
- gamma -> std::tgamma; gammaln/loggamma -> std::lgamma (EXACT).
- j0/j1 (Bessel) -> there is NO std::cyl_bessel_j on Apple clang 21. Use the
  provided bessj0/bessj1 (A&S 9.4 / Numerical Recipes polynomial). Max abs err
  ~5e-9 vs scipy on [0,40], so set the parity tolerance to ~1e-6 (NOT machine
  precision) and say WHY in RESULT.txt.
- yn/iv/kv/Ai etc.: flag as heavy (hand-rolled series/recurrence) -- attempt only
  if the node needs them."""

HELPER_BESSEL = r"""// scipy.special.j0/j1 (A&S 9.4 / Numerical Recipes). Max abs err ~5e-9 on [0,40].
static double bessj0(double x) {
    double ax = std::fabs(x), y, p1, p2;
    if (ax < 8.0) {
        y = x * x;
        p1 = 57568490574.0 + y*(-13362590354.0 + y*(651619640.7
             + y*(-11214424.18 + y*(77392.33017 + y*(-184.9052456)))));
        p2 = 57568490411.0 + y*(1029532985.0 + y*(9494680.718
             + y*(59272.64853 + y*(267.8532712 + y*1.0))));
        return p1 / p2;
    }
    double z = 8.0 / ax, yy = z * z, xx = ax - 0.785398164;
    p1 = 1.0 + yy*(-0.1098628627e-2 + yy*(0.2734510407e-4
         + yy*(-0.2073370639e-5 + yy*0.2093887211e-6)));
    p2 = -0.1562499995e-1 + yy*(0.1430488765e-3 + yy*(-0.6911147651e-5
         + yy*(0.7621095161e-6 + yy*(-0.934935152e-7))));
    return std::sqrt(0.636619772 / ax) *
           (std::cos(xx) * p1 - z * std::sin(xx) * p2);
}
static double bessj1(double x) {
    double ax = std::fabs(x), y, p1, p2, ans;
    if (ax < 8.0) {
        y = x * x;
        p1 = x*(72362614232.0 + y*(-7895059235.0 + y*(242396853.1
             + y*(-2972611.439 + y*(15704.48260 + y*(-30.16036606))))));
        p2 = 144725228442.0 + y*(2300535178.0 + y*(18583304.74
             + y*(99447.43394 + y*(376.9991397 + y*1.0))));
        return p1 / p2;
    }
    double z = 8.0 / ax, yy = z * z, xx = ax - 2.356194491;
    p1 = 1.0 + yy*(0.183105e-2 + yy*(-0.3516396496e-4
         + yy*(0.2457520174e-5 + yy*(-0.240337019e-6))));
    p2 = 0.04687499995 + yy*(-0.2002690873e-3 + yy*(0.8449199096e-5
         + yy*(-0.88228987e-6 + yy*0.105787412e-6)));
    ans = std::sqrt(0.636619772 / ax) *
          (std::cos(xx) * p1 - z * std::sin(xx) * p2);
    return (x < 0.0) ? -ans : ans;
}"""


# ---------------------------------------------------------------------------
# numpy.linalg / scipy.linalg -- dense direct solvers.
# ---------------------------------------------------------------------------

LINALG = """\
=== numpy.linalg / scipy.linalg (dense) ===
- np.linalg.solve(A,b) -> the provided lu_solve(A,b,n) (partial-pivot Doolittle
  LU == LAPACK getrf/getrs; reproduces np.linalg.solve to ~1e-17). Build A
  ROW-MAJOR (A[i*n+j]). For multiple RHS, solve each column.
- np.linalg.inv -> lu_solve against the identity columns.
- np.linalg.det -> product of LU diagonal * pivot-sign.
- np.linalg.lstsq / np.linalg.qr -> Householder QR then back-substitute.
- np.linalg.cholesky -> standard Cholesky (SPD only).
- symmetric eig (np.linalg.eigh small) -> cyclic Jacobi.
- SVD / non-symmetric eig: flag as HEAVY (no compact exact port) -- attempt only
  if essential, and relax tolerance."""

HELPER_LU = r"""// np.linalg.solve: partial-pivot dense LU (== LAPACK getrf/getrs, ~1e-17).
// Solves A x = b in place; A is row-major n*n, b length n. false if singular.
static bool lu_solve(std::vector<double>& A, std::vector<double>& b, int n) {
    for (int k = 0; k < n; ++k) {
        int p = k; double mx = std::fabs(A[k*n+k]);
        for (int i = k+1; i < n; ++i) { double v = std::fabs(A[i*n+k]); if (v > mx) { mx = v; p = i; } }
        if (mx == 0.0) return false;
        if (p != k) { for (int j = 0; j < n; ++j) std::swap(A[k*n+j], A[p*n+j]); std::swap(b[k], b[p]); }
        double akk = A[k*n+k];
        for (int i = k+1; i < n; ++i) {
            double m = A[i*n+k] / akk; A[i*n+k] = m;
            for (int j = k+1; j < n; ++j) A[i*n+j] -= m * A[k*n+j];
        }
    }
    for (int i = 1; i < n; ++i) for (int j = 0; j < i; ++j) b[i] -= A[i*n+j] * b[j];
    for (int i = n-1; i >= 0; --i) { for (int j = i+1; j < n; ++j) b[i] -= A[i*n+j] * b[j]; b[i] /= A[i*n+i]; }
    return true;
}"""


# ---------------------------------------------------------------------------
# scipy.interpolate -- B-splines via Cox-de Boor / de Boor.
# ---------------------------------------------------------------------------

INTERP = """\
=== scipy.interpolate (B-splines) ===
- A B-spline basis is Cox-de Boor recursion. Use the provided findSpan +
  basisFuns (Piegl-Tiller A2.2/A2.3): for parameter u, span i=findSpan(...),
  basisFuns gives the (degree+1) nonzero basis values N[0..p] for control points
  i-p..i. Reproduces scipy bases to machine precision.
- Evaluating a curve C(u)=sum N_k * P_k -> deBoor (provided) or basisFuns dot CVs.
- scipy.interpolate.BSpline(t,c,k): t=knots, c=coeffs, k=degree -> deBoor(k,t,c,u)
  per coefficient component.
- make_interp_spline: clamped/not-a-knot knot vector + a banded collocation solve
  (use lu_solve). The KNOT construction must match scipy exactly.
- splrep/splev with smoothing s>0 is iterative FITPACK (DIERCKX) and is NOT
  bit-reproducible -- either bake the fitted coeffs as constants, or accept a
  tolerance and document it."""

HELPER_BSPLINE = r"""// B-spline (Cox-de Boor). findSpan/basisFuns: Piegl-Tiller "The NURBS Book".
static int findSpan(int n, int p, double u, const std::vector<double>& U) {
    if (u >= U[n + 1]) return n;          // clamp to last span
    if (u <= U[p])     return p;          // clamp to first span
    int low = p, high = n + 1, mid = (low + high) / 2;
    while (u < U[mid] || u >= U[mid + 1]) {
        if (u < U[mid]) high = mid; else low = mid;
        mid = (low + high) / 2;
    }
    return mid;
}
// Nonzero basis funcs N[0..p] at span i for parameter u (degree p, knots U).
static void basisFuns(int i, double u, int p, const std::vector<double>& U,
                      std::vector<double>& N) {
    N.assign(p + 1, 0.0);
    std::vector<double> left(p + 1, 0.0), right(p + 1, 0.0);
    N[0] = 1.0;
    for (int j = 1; j <= p; ++j) {
        left[j]  = u - U[i + 1 - j];
        right[j] = U[i + j] - u;
        double saved = 0.0;
        for (int r = 0; r < j; ++r) {
            double tmp = N[r] / (right[r + 1] + left[j - r]);
            N[r] = saved + right[r + 1] * tmp;
            saved = left[j - r] * tmp;
        }
        N[j] = saved;
    }
}
// de Boor: evaluate a scalar B-spline (knots t, coeffs c, degree k) at u.
static double deBoor(int k, const std::vector<double>& t,
                     const std::vector<double>& c, double u) {
    int mu = findSpan((int)c.size() - 1, k, u, t);
    std::vector<double> d(k + 1);
    for (int j = 0; j <= k; ++j) d[j] = c[j + mu - k];
    for (int r = 1; r <= k; ++r)
        for (int j = k; j >= r; --j) {
            double a = (u - t[j + mu - k]) / (t[j + 1 + mu - r] - t[j + mu - k]);
            d[j] = (1.0 - a) * d[j - 1] + a * d[j];
        }
    return d[k];
}"""


# ---------------------------------------------------------------------------
# Imaging libraries -- math subset is portable, I/O is not.
# ---------------------------------------------------------------------------

IMAGING = """\
=== PIL / cv2 / skimage (pixels arrive via a Maya float-array/texture input) ===
PORTABLE (translate to loops): per-pixel point ops, blend/composite, convolution
(Kernel/BLUR/SHARPEN/filter2D/GaussianBlur/Sobel/Scharr), resize (nearest/
bilinear), rotate/warp (inverse-map + sample), threshold, color conversion,
morphology (erosion/dilation = min/max over a structuring element).
NON-PORTABLE (hard blocker): imread/imwrite/imshow/open/save/show, VideoCapture/
Writer, dnn/cuda/ml/CascadeClassifier, ImageDraw/ImageFont/ImageGrab, skimage.io.
COPY CONVENTIONS FROM THE SAME LIBRARY THE PYTHON USED (they differ!):
- Channel order: cv2 = BGR; PIL/skimage = RGB.
- Gray/luma: cv2 = 0.299R+0.587G+0.114B (BGR input); skimage = 0.2125R+0.7154G+
  0.0721B (RGB, float[0,1]).
- Data range: cv2/PIL uint8 [0,255]; skimage float [0,1].
- Border: PIL replicate/clamp; cv2 default BORDER_REFLECT_101 (gfedcb|abcdefgh);
  skimage gaussian default mode='nearest' (clamp), radius=ceil(truncate*sigma).
- Resize maps output->source CENTER-aligned: src=(o+0.5)*(slen/dlen)-0.5, clamp,
  bilinear between floor/ceil. In the float domain this matches PIL/cv2 exactly;
  uint8 differs by <=1 LSB -> keep work in double, round only at the end.
- cv2.getGaussianKernel with explicit sigma>0: w[i]=exp(-(i-c)^2/(2 sig^2)),
  c=(ksize-1)/2, normalize sum 1 (matches cv2 to ~5e-17). sigma<=0 uses an
  internal table -> compute the explicit sigma=0.3*((ksize-1)*0.5-1)+0.8 instead."""


# ---------------------------------------------------------------------------
# numpy.random / random / secrets -> C++ <random> (supported, non-bit-exact).
# ---------------------------------------------------------------------------

RANDOM = """\
=== numpy.random / random / secrets -> C++ <random> (SUPPORTED, NOT bit-exact) ===
RNG is allowed. Map the calls to the provided NdRng helper (std::mt19937_64 +
<random> distributions). The output is NOT bit-identical to Python's PRNG -- that
is expected and accepted; RNG nodes are NOT pointwise parity-checked.

DETERMINISM IS STILL MANDATORY (this is a Maya DG node -- compute() runs
constantly and MUST be a pure function of its inputs, or the node flickers and
breaks DG caching):
- Create the engine LOCALLY at the TOP of compute() and seed it DETERMINISTICALLY
  from the node's inputs. NEVER use a global/static engine, std::random_device,
  time(), or a default-constructed engine.
- Seed source: if the node has an integer `seed`-like input, use it; mix in any
  time/frame input so animation varies per frame yet each frame is reproducible:
      NdRng rng((uint64_t)in_seed ^ nd_mix_seed((uint64_t)std::llround(in_time*1000.0)));
  If there is NO seed/time input, seed from a fixed constant (e.g. NdRng rng(0)) ->
  the noise is stable (same every evaluation).
- Draw values in the SAME ORDER the Python does (which draw lands where matters),
  even though the values themselves differ from Python.

Call mapping:
- np.random.random()/rand()/random.random()        -> rng.random()            // [0,1)
- np.random.uniform(lo,hi)/random.uniform(lo,hi)    -> rng.uniform(lo,hi)
- np.random.randint(lo,hi)/np.random.integers(lo,hi)-> rng.randint(lo,hi)      // [lo,hi)
- random.randint(a,b)  (INCLUSIVE!)                 -> rng.randint(a, b+1)
- np.random.normal(mu,s)/randn()/random.gauss(mu,s) -> rng.normal(mu,s)        // randn: mu=0,s=1
- np.random.seed(x)/default_rng(x)/random.seed(x)   -> fold x into the seed: NdRng rng((uint64_t)x)
- np.random.random(n) / array fills                 -> loop i in [0,n): a[i]=rng.random() (one draw/elem)
- np.random.choice(seq)                             -> seq[rng.randint(0,(long long)seq.size())]
<random> is already included by the generated file -- do NOT add another #include."""

HELPER_RANDOM = r"""// numpy.random / random -> deterministic C++ <random>. Seed LOCALLY each
// compute() from the node's inputs (NdRng rng(seed);) so the node is a pure
// function of its inputs. NOT bit-identical to Python's PRNG (not parity-checked).
static inline uint64_t nd_mix_seed(uint64_t s) {
    // SplitMix64 finalizer: spreads a small/zero seed into well-distributed bits.
    s += 0x9E3779B97F4A7C15ULL;
    s = (s ^ (s >> 30)) * 0xBF58476D1CE4E5B9ULL;
    s = (s ^ (s >> 27)) * 0x94D049BB133111EBULL;
    return s ^ (s >> 31);
}
struct NdRng {
    std::mt19937_64 eng;
    explicit NdRng(uint64_t seed) : eng(nd_mix_seed(seed)) {}
    double random() {                       // np.random.random() / random.random() -> [0,1)
        return std::uniform_real_distribution<double>(0.0, 1.0)(eng);
    }
    double uniform(double lo, double hi) {  // np.random.uniform / random.uniform
        return std::uniform_real_distribution<double>(lo, hi)(eng);
    }
    long long randint(long long lo, long long hi_exclusive) {  // [lo, hi_exclusive)
        if (hi_exclusive <= lo) return lo;
        return std::uniform_int_distribution<long long>(lo, hi_exclusive - 1)(eng);
    }
    double normal(double mu, double sigma) {  // np.random.normal / randn / random.gauss
        return std::normal_distribution<double>(mu, sigma)(eng);
    }
};"""


# Section + helper registry, keyed by the import/usage signature in the source.
_SECTIONS = [
    ("numba", NUMBA, ["", r"\bnumba\b", r"@njit", r"@jit\b", r"\bprange\b",
                      r"@guvectorize", r"@vectorize", r"@stencil", r"\bnb\."]),
    ("special", SPECIAL, [r"scipy\.special", r"\bspecial\.", r"\b(?:j0|j1|erf|erfc|gammaln)\b"]),
    ("interp", INTERP, [r"scipy\.interpolate", r"\binterpolate\b", r"\bBSpline\b",
                        r"make_interp_spline", r"\bsplrep\b", r"\bsplev\b", r"\bsplprep\b"]),
    ("linalg", LINALG, [r"np\.linalg", r"numpy\.linalg", r"scipy\.linalg",
                        r"\blinalg\.", r"\.solve\(", r"\blstsq\b", r"\bcholesky\b"]),
    ("imaging", IMAGING, [r"\bcv2\b", r"\bPIL\b", r"\bImage\b", r"\bImageFilter\b",
                          r"\bskimage\b", r"\bImageOps\b"]),
    # RNG triggers are the EXACT patterns spec_extractor uses to detect RNG (and
    # skip parity), so the two can never diverge -- anything that skips parity
    # also gets the RANDOM section + NdRng helper.
    ("random", RANDOM, [p.pattern for p in _spec_extractor._RNG_PATTERNS]),
]

_HELPERS = {
    "special": HELPER_BESSEL,
    "linalg": HELPER_LU,
    "interp": HELPER_BSPLINE,
    "random": HELPER_RANDOM,
}


def sections_for(source: str) -> list:
    """Return the section keys whose signatures appear in ``source``."""
    src = source or ""
    keys = []
    for key, _text, pats in _SECTIONS:
        for p in pats:
            if p == "":
                continue
            if re.search(p, src):
                keys.append(key)
                break
    return keys


def guide_for(source: str, include_helpers: bool = True) -> str:
    """Build the translation guide for a compute+init source string.

    Always includes CORE; appends the section text (and verified C++ helper
    bodies) for every library signature detected in ``source``.
    """
    parts = [CORE]
    keys = sections_for(source)
    text_by_key = {k: t for k, t, _ in _SECTIONS}
    for key in keys:
        parts.append(text_by_key[key])
    if include_helpers:
        helper_blocks = []
        for key in keys:
            if key in _HELPERS:
                helper_blocks.append(_HELPERS[key])
        if helper_blocks:
            parts.append(
                "=== VERIFIED C++ HELPERS (paste any you use, inside the PORT "
                "region or just above it) ===\n" + "\n\n".join(helper_blocks))
    return "\n\n".join(parts)


IMAGE_FILE_READ = """\
=== SANCTIONED IMAGE FILE READ (this is a texture/file node) ===
The image file IS already read for you -- the generated scaffold loaded the
node's path input via MImage::readFromFile into:
  const unsigned char* _imgPixels;  // RGBA, 8-bit, row-major; NULL if read failed
  unsigned int _imgW, _imgH;        // image dimensions (0 if read failed)
  bool _imgOK;                      // false if path empty/missing/unsupported
Pixel (x,y) channel c (0=R,1=G,2=B,3=A): _imgPixels[(y*_imgW + x)*4 + c], 0..255.
When the Python compute obtains its image through a HELPER call instead of a
direct read -- e.g. `img = _resolve_image(self)` or `img = _composite_image(self)`
(a multi-file path array is pre-composited into ONE buffer for you) -- map that
helper's result to _imgPixels: `img is None` -> `!_imgOK`, `img.shape[1]` -> _imgW,
`img.shape[0]` -> _imgH, `img[py, px]` channel c -> _imgPixels[(py*_imgW+px)*4+c].
Do NOT port the helper body. Do NOT call imread / Image.open / cv2.imread in C++
-- map those Python calls to _imgPixels. The output depends on external file
state, so this node is NOT
pointwise parity-checked (loose/skipped); still keep compute() a pure function of
(inputs + file) with no other I/O.
CHANNEL ORDER: _imgPixels is RGBA. If the Python used cv2 (imread returns BGR),
read B=_imgPixels[..+2], G=..+1, R=..+0 to match its convention; PIL/skimage are
already RGB. Normalize to the range the Python math expects (uint8 [0,255] for
cv2/PIL; divide by 255.0 for skimage's float [0,1]).
ALWAYS handle _imgOK == false: output a stable fallback (e.g. the magenta the
Python node uses, or zeros) so a missing file never crashes compute()."""


TEXTURE_INTERFACE_ATTRS = """\
=== TEXTURE INTERFACE ATTRS (float2 uvCoord / color outColor) ===
A float2 input (e.g. uvCoord) is read as a 2-float array: in_<name>[0] is U,
in_<name>[1] is V -- e.g. `double u = in_aUvCoord[0], v = in_aUvCoord[1];`.
A color input (e.g. borderColor) is a 3-float array: in_<name>[0/1/2] = R/G/B.
WRITE a color OUTPUT with set3Float on its handle (NOT set3Double):
  h_<name>.set3Float((float)r, (float)g, (float)b);   // r,g,b 0..1 linear
A float2 OUTPUT uses set2Float((float)u, (float)v). color/float2 handles take the
float setters; only plain `vector` outputs use set3Double."""


NURBS_CURVE_INPUT = """\
=== NURBS CURVE INPUT (self.<curve> is an MFnNurbsCurve) ===
The scaffold already read each nurbsCurve INPUT into a ready-to-use MFnNurbsCurve
local named in_<member> (built from the input plug's kNurbsCurve MObject; the raw
MObject is in_<member>_obj). Do NOT construct the curve yourself. Map
self.<curve>.<method>(...) to in_<curve>.<method>(...) using these C++ (api1)
signatures -- they DIFFER from the Python api2 forms you see in the source:
  * param from arc length:  double u = in_crv.findParamFromLength(len);
  * arc length from param:   double L = in_crv.findLengthFromParam(param);
  * point at param:          MPoint p; in_crv.getPointAtParam(param, p, MSpace::kWorld);
                             // p is an OUT-param (NOT a return); p.x/p.y/p.z are doubles.
  * tangent at param:        MVector t = in_crv.tangent(param, MSpace::kWorld);  // returns MVector
Map om.MSpace.kWorld -> MSpace::kWorld (use kObject only if the Python used kObject).
np.array(<api point/vector>)[:3] just means take .x/.y/.z as a 3-vector.
If the curve can be empty/unconnected and the Python guarded it, guard with
`if (!in_crv_obj.isNull() && in_crv_obj.hasFn(MFn::kNurbsCurve)) { ... }` and emit
a stable fallback otherwise -- a query on a null curve must not crash compute().

=== MATRIX -> EULER (om.MTransformationMatrix(...).rotation()) ===
To decompose a 4x4 basis matrix to an Euler rotation (Maya default XYZ order):
  double mm[4][4] = {{a,b,c,d},{e,f,g,h},{i,j,k,l},{m,n,o,p}};  // 16 row-major values
  MMatrix M(mm);
  MEulerRotation er = MTransformationMatrix(M).eulerRotation();  // RADIANS, XYZ order
  // er.x, er.y, er.z match om.MTransformationMatrix(om.MMatrix(vals)).rotation().x/.y/.z
Build mm from the same row-major values the numpy code flattens (row 3 = translate,
upper-left 3x3 = rotation*scale). Write euler array OUTPUTS in RADIANS:
  out_<name>[i] = MVector(er.x, er.y, er.z);"""


MESH_CLOSEST_POINT = """\
=== CLOSEST POINT ON A MESH (om.MMeshIntersector / getClosestPoint) ===
The C++ API is the SAME class with the same methods, so port this 1:1 -- do NOT
substitute a brute-force scan over vertices or triangles, and do NOT invent an
approximation. <maya/MMeshIntersector.h> is ALREADY included in the scaffold
(you may not add includes; it is there for you).
Python (api2)                          C++ (api1)
  isect = om.MMeshIntersector()          MMeshIntersector isect;
  isect.create(meshObj)                  isect.create(in_<mesh>_obj);
  r = isect.getClosestPoint(om.MPoint(x,y,z))
                                         MPointOnMesh r;
                                         isect.getClosestPoint(MPoint(x,y,z), r);
  r.point        -> x/y/z                MFloatPoint p = r.getPoint();   // p.x/p.y/p.z
  r.normal                               MFloatVector n = r.getNormal();
  r.face                                 int f = r.faceIndex();
  r.triangle                             int t = r.triangleIndex();
  r.barycentricCoords -> (u, v, w)       float u, v; r.getBarycentricCoords(u, v);
create() takes the mesh MObject the scaffold already read from the input plug
(in_<mesh>_obj), NOT the MFnMesh. It is a HEAVY octree build: create it ONCE
before the query loop, never inside it. getClosestPoint is const + threadsafe.
BARYCENTRIC ORDERING (the one silent way to get this wrong): the pair (u, v)
weights the FIRST TWO vertices of the hit TRIANGLE and the third weight is
1-u-v -- so `w = {u, v, 1-u-v}` against the triangle's vertices in order. Any
other assignment still produces plausible-looking output while every
interpolated value is wrong (measured 0.73 error vs 5e-07 for the correct
order). Get the hit triangle's vertex ids from MFnMesh::getTriangles(triCounts,
triVerts): triVerts is flat, 3 ids per triangle, and triangle t of face f starts
at (prefix-sum of triCounts up to f) + t.
Both sides store these as float32 internally, so a faithful port is EXACT, not
merely close -- a parity failure here means the port diverged, not rounding.
COST -- NOT A STYLE CHOICE, AND THE ONE MISTAKE THIS PIPELINE HAS ALREADY MADE.
MFnMesh::getClosestPoint(point, outPoint, space, &faceId) returns the same
answer, but its trailing MMeshIsectAccelParams* argument DEFAULTS TO NULL and
without it the call is an unaccelerated walk of the polygon list, so a sweep
costs O(queries x faces). MMeshIntersector builds its spatial structure ONCE in
create(), so each query is sublinear in the face count. If the Python used
MMeshIntersector you MUST emit MMeshIntersector. Substituting
MFnMesh::getClosestPoint there is a WRONG port that compiles, is deterministic,
matches every value and passes every gate downstream -- this guide is the only
place it can be caught. Measured: a voxelize port that made that substitution
took 714 SECONDS for ONE evaluation on a 40k-vertex sphere at voxelSize 0.025;
the same sweep over a spatial structure took 0.125 s. The template's own note
measures MMeshIntersector at ~170k queries/s, ~13x MFnMesh.getClosestPoint for
the identical answer. Use MFnMesh::getClosestPoint ONLY when the Python used
MFnMesh.getClosestPoint, and then port it as written -- do not add an
accelerator the Python did not ask for."""


PERSISTENT_STATE = """\
=== PERSISTENT PER-INSTANCE STATE (self.<x> that survives between evals) ===
This compute reads AND writes one or more self.<x> that are NOT declared inputs
or outputs. Those are PERSISTENT PER-INSTANCE STATE: a value the Python node
latches on one evaluate() and reads back on a LATER one (a latched rest length,
a solver carry-over, a simulation buffer, a `previous` frame). MPxNode::compute()
is otherwise STATELESS -- a plain local is reborn every call -- so you MUST give
each such variable a home that survives across compute() calls, keyed on the node
instance. DO NOT flatten it (re-deriving it every eval from the current inputs):
that silently breaks the feature (e.g. a spine whose `defaultLength` is re-latched
every frame has ratio==1 forever, so its `stretch` becomes a no-op).

THE SHAPE THIS WANTS, WHICH YOU CANNOT WRITE. The deterministic numpy->C++
lowering solves exactly this problem with PER-INSTANCE CLASS MEMBERS -- created
and destroyed with the node, at an address stable for its whole life, guarded by
their own mutex:

    // class body
    struct _NdState { bool x_isset = false; double x {}; };
    _NdState _ndState;
    std::mutex _ndStateMutex;
    // first lines of the body
    std::lock_guard<std::mutex> _ndStateLock(_ndStateMutex);
    _NdState& st = _ndState;

You write ONLY the code between the PORT markers, inside compute(): you may not
add a class member and you may not add an #include. So write the closest thing
that fits in the region -- a function-static registry keyed by (const void*)this,
found-or-created at the top of compute(). Store POINTERS, never records:

    struct NodeState {
        const void* key;
        bool  initialized = false;   // state seeded yet? (hasattr(self,'x'))
        double x {};                 // one member per persistent self.<x>
        std::vector<MVector> buf;
    };
    static std::vector<NodeState*> s_states;   // POINTERS: the vector reallocates,
                                               // the states it points at never move
    NodeState* st = nullptr;
    for (NodeState* s : s_states)
        if (s->key == (const void*)this) { st = s; break; }
    if (!st) { st = new NodeState(); st->key = (const void*)this; s_states.push_back(st); }

NEVER `static std::vector<NodeState> s_states;` with `st = &s_states.back();` (or
`&s_states[i]`). A vector of RECORDS reallocates on push_back, and every pointer
into it dangles the moment it does -- Maya's parallel EM evaluates nodes
concurrently, so another instance's compute() can reallocate the vector while you
are holding a pointer into it. That is live undefined behaviour, and it is the one
way this guidance has actually been got wrong. Pointers fix THAT much: only the
pointer array moves, never a state.

Pointers do NOT make the registry thread-safe, and nothing you can write in here
will. The lock the class-member shape above uses needs <mutex>, which the port
skeleton does not include and you cannot add, so s_states is UNSYNCHRONISED by
construction: the range-for read can run against another thread's push_back the
first time two instances of this node evaluate together. Emit it EXACTLY as
written anyway, and do NOT improvise around the hole -- a `volatile`, a
reserve(), a second static flag, a thread_local registry (which would hand the
same node a DIFFERENT state per thread and silently lose the carry) all make it
look settled without adding a happens-before edge.

That is why this registry is a CONSTRAINED FALLBACK, not the shape anyone wants:
it is what fits inside the PORT region, it is never evicted (so it cannot free a
destroyed node's record either), and closing both holes means lifting it to the
class-member shape at the top of this section. The optimizer pass CAN edit the
class body and is told to do exactly that -- but only mechanically, so keep EVERY
state access going through `st->`, found-or-created in ONE block at the top of
compute(), and key on nothing but `this`. (You are here only because your compute
could not be lowered deterministically; a node that lowers gets the member
directly and never sees a registry.)

Then:
  * self.<x>          -> st->x               (read/write the member)
  * hasattr(self,'x') -> st->initialized     (false until you first set it)
  * `if reset or not hasattr(self,'x'): self.x = <expr>`  ->
        if (in_reset || !st->initialized) { st->x = <expr>; st->initialized = true; }
Seed the state EXACTLY as the Python first-run branch does (only on the first eval
or when a reset input is set), and read it UNMODIFIED on later evals -- never
overwrite it every call. This node's parity is checked over MANY evals with
changing inputs, so a flattened state WILL be caught and the build REJECTED.

The member TYPE follows the value: a scalar self.<x> -> a POD member (double/int/
bool); an array/buffer -> a std::vector<...> (or nd::Array). If a persistent
self.<x> holds a PYTHON OBJECT -- a helper-CLASS INSTANCE or the return of a
function (e.g. `self.solver = Solver(self.previous)`, `self.buf = make_state()`) --
you CANNOT store the object or a pointer to it. Instead identify the actual
per-instance DATA that object carries across evals (its fields, or the arg it was
seeded from -- frequently ANOTHER persistent self.<y> such as a `previous` frame or
a solved buffer) and make THAT the NodeState member(s); reconstruct the object's
per-eval computation inline in compute() from those members. A common shape is a
solver cached on self (`self.node = Solver(self.previous)`) whose REAL state is the
`self.previous` buffer it reads and rewrites each eval -- carry `previous`, drop the
cached instance. Never store a Python-object pointer in NodeState."""


def _persistent_state_names(spec: dict):
    """self.<x> that are written-whole AND read but NOT declared IO -- persistent
    per-instance state (mirrors nd_lower._persistent_state_vars)."""
    import ast

    src = "%s\n%s" % (spec.get("compute") or "", spec.get("init") or "")
    declared = set(spec.get("inputs") or {}) | set(spec.get("outputs") or {})
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    written, read = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            targets = n.targets
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
            targets = [n.target]
        else:
            targets = ()
        for t in targets:
            if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == "self" and t.attr not in declared):
                written.add(t.attr)
        if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load)
                and isinstance(n.value, ast.Name) and n.value.id == "self"
                and n.attr not in declared):
            read.add(n.attr)
    return written & read


def _spec_has_attr_types(spec: dict, types) -> bool:
    for kind in ("inputs", "outputs"):
        for m in (spec.get(kind) or {}).values():
            if isinstance(m, dict) and m.get("type") in types:
                return True
    return False


def guide_for_spec(spec: dict, include_helpers: bool = True) -> str:
    """Convenience: build the guide from a porter spec's compute + init.

    For a sanctioned texture/file node (``reads_image_file``) the image-file-read
    guidance is appended so the AI maps imread/Image.open to the pre-loaded
    ``_imgPixels`` buffer instead of treating it as an unportable blocker. When
    the spec carries the texture-interface types (float2 uvCoord / color
    outColor, e.g. captured mPyFile presets) the read/write conventions for those
    are appended too. A node flagged ``uses_mesh_intersector`` gets the
    closest-point mapping (the same flag emits <maya/MMeshIntersector.h> into the
    scaffold, which the porter itself may not add)."""
    src = "%s\n%s" % (spec.get("compute") or "", spec.get("init") or "")
    guide = guide_for(src, include_helpers=include_helpers)
    # The scaffold only declares the buffer when a path INPUT resolves (see
    # node_scaffold's `_path_in is None` suppression); promising `_imgPixels`
    # here anyway would name an identifier the TU never declares, and the port
    # would not compile. `_pick_path_input` returns None exactly when there is no
    # string/hex INPUT -- an output cannot be a path source -- so that is the test.
    _has_path_input = any(
        isinstance(m, dict) and m.get("type") in ("string", "hex")
        for m in (spec.get("inputs") or {}).values())
    if (spec.get("suggested") or {}).get("reads_image_file") and _has_path_input:
        guide = guide + "\n\n" + IMAGE_FILE_READ
    if _spec_has_attr_types(spec, ("float2", "color")):
        guide = guide + "\n\n" + TEXTURE_INTERFACE_ATTRS
    if _spec_has_attr_types(spec, ("nurbsCurve",)):
        guide = guide + "\n\n" + NURBS_CURVE_INPUT
    # Closest-point mesh query: the C++ class is identical, so the port is 1:1 --
    # but only if the porter is told the api1 spelling and the barycentric
    # ordering. Same flag that emits <maya/MMeshIntersector.h>.
    if (spec.get("suggested") or {}).get("uses_mesh_intersector"):
        guide = guide + "\n\n" + MESH_CLOSEST_POINT
    # Persistent per-instance state (spine defaultLength, dnet previous, ...): the
    # porter must emit a this-keyed registry instead of flattening the state.
    if _persistent_state_names(spec):
        guide = guide + "\n\n" + PERSISTENT_STATE
    return guide
