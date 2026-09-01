// nd_runtime_test.cpp — standalone P0 op-surface exerciser for nd_runtime.h.
//
// This binary computes each op with nd:: and prints, per case, the INPUT arrays
// and the OUTPUT array in a parseable text protocol. A companion numpy oracle
// (nd_runtime_test.py, run under mayapy) reconstructs the inputs from the IN
// lines, recomputes the same op with numpy, and asserts parity. Inputs flow
// C++ -> oracle, so there is a single source of truth (no fixture drift).
//
// Build:
//   clang++ -std=c++17 -O2 nd_runtime_test.cpp -o /tmp/nd_test
// Protocol (one block per case):
//   CASE <name>
//   IN  <name> <f64|i64|bool> <ndim> <d0..> : <flat C-order values>
//   OUT <ret>  <f64|i64|bool> <ndim> <d0..> : <flat C-order values>
//   END

#include "nd_runtime.h"
#include <cstdio>
#include <cstring>

using namespace nd;

template <class T> const char* dtype_tag();
template <> const char* dtype_tag<double>()  { return "f64"; }
template <> const char* dtype_tag<int64_t>() { return "i64"; }
template <> const char* dtype_tag<bool>()    { return "bool"; }

template <class T>
void emit(const char* kind, const char* name, const Array<T>& a) {
    Array<T> c = a.copy();
    std::printf("%s %s %s %lld", kind, name, dtype_tag<T>(), (long long)a.ndim());
    for (int64_t d : a.shape) std::printf(" %lld", (long long)d);
    std::printf(" :");
    int64_t n = c.size();
    for (int64_t i = 0; i < n; ++i) {
        if (std::is_floating_point<T>::value)
            std::printf(" %.17g", (double)(*c.data)[(size_t)i]);
        else
            std::printf(" %lld", (long long)(*c.data)[(size_t)i]);
    }
    std::printf("\n");
}

void caseName(const char* n) { std::printf("CASE %s\n", n); }
void endCase() { std::printf("END\n"); }

// ----------------------------------------- matmul2d accumulation-order gate
// matmul2d dispatches to several kernels (the compile-time matmul2d_fixed
// sizes, the i-l-j streaming path, the generic fallback). All of them MUST
// return the byte-identical result of summing over l in ASCENDING order into a
// T accumulator, because the repo's parity gates compare bytes. The numpy
// oracle above cannot police that -- np.matmul goes through BLAS, which blocks
// and reassociates -- so the reference here is a literal ascending-l loop and
// the comparison is memcmp, not a tolerance.
//
// This only means anything under -ffp-contract=off (the shipping recipe, see
// toolchain.py). With contraction ON the compiler picks FMA per call site, and
// the runtime changes bytes between -O1 and -O2 with no source edit at all.
struct MMRng {
    uint64_t s;
    explicit MMRng(uint64_t seed) : s(seed) {}
    uint64_t next() {
        uint64_t z = (s += 0x9E3779B97F4A7C15ULL);
        z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
        z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
        return z ^ (z >> 31);
    }
};

// Deliberately wide exponent spread: summing 2^-16 and 2^15 terms is what makes
// the order observable. Equal-magnitude operands would hide a reassociation.
template <class T> T mm_rand(MMRng& r);
template <> double mm_rand<double>(MMRng& r) {
    uint64_t u = r.next();
    double m = (double)(u >> 11) * (1.0 / 9007199254740992.0);
    return (m - 0.5) * std::ldexp(1.0, (int)(u & 31) - 16);
}
template <> int64_t mm_rand<int64_t>(MMRng& r) { return (int64_t)(r.next() % 2001) - 1000; }
template <> bool mm_rand<bool>(MMRng& r) { return (r.next() & 1) != 0; }

template <class T>
Array<T> mm_make(const Shape& sh, MMRng& r) {
    Array<T> a = Array<T>::alloc(sh);
    int64_t n = prod(sh);
    for (int64_t i = 0; i < n; ++i) (*a.data)[(size_t)i] = mm_rand<T>(r);
    return a;
}

template <class T>
Array<T> mm_ref(const Array<T>& a, const Array<T>& b) {
    int64_t m = a.shape[0], k = a.shape[1], n = b.shape[1];
    Array<T> out = zeros<T>({m, n});
    for (int64_t i = 0; i < m; ++i)
        for (int64_t j = 0; j < n; ++j) {
            T acc = (T)0;
            for (int64_t l = 0; l < k; ++l)
                acc += (*a.data)[(size_t)(a.offset + i*a.strides[0] + l*a.strides[1])]
                     * (*b.data)[(size_t)(b.offset + l*b.strides[0] + j*b.strides[1])];
            (*out.data)[(size_t)(i*n + j)] = acc;
        }
    return out;
}

template <class T>
bool mm_same_bits(const Array<T>& x, const Array<T>& y) {
    if (x.shape != y.shape) return false;
    int64_t n = x.size();
    for (int64_t i = 0; i < n; ++i) {
        T u = (T)(*x.data)[(size_t)i], v = (T)(*y.data)[(size_t)i];
        if (std::memcmp(&u, &v, sizeof(T)) != 0) return false;
    }
    return true;
}

// Layout variants: 0 both contiguous, 1 a transposed, 2 b transposed, 3 both,
// 4 a row-strided view, 5 b column-strided view, 6 offset + strided both.
template <class T>
void mm_build(int v, int64_t m, int64_t k, int64_t n, MMRng& r,
              Array<T>& a, Array<T>& b) {
    switch (v) {
        case 0: a = mm_make<T>({m, k}, r);            b = mm_make<T>({k, n}, r); break;
        case 1: a = transpose(mm_make<T>({k, m}, r)); b = mm_make<T>({k, n}, r); break;
        case 2: a = mm_make<T>({m, k}, r);            b = transpose(mm_make<T>({n, k}, r)); break;
        case 3: a = transpose(mm_make<T>({k, m}, r)); b = transpose(mm_make<T>({n, k}, r)); break;
        case 4: a = slice(mm_make<T>({m*2, k}, r), {Sl::stepped(2), Sl::full()});
                b = mm_make<T>({k, n}, r); break;
        case 5: a = mm_make<T>({m, k}, r);
                b = slice(mm_make<T>({k, n*2}, r), {Sl::full(), Sl::stepped(2)}); break;
        default: a = slice(mm_make<T>({m*2 + 1, k + 2}, r),
                           {Sl::range(1, 1 + m*2, 2), Sl::range(2, 2 + k)});
                 b = slice(mm_make<T>({k + 1, n*2 + 3}, r),
                           {Sl::range(1, 1 + k), Sl::range(3, 3 + n*2, 2)}); break;
    }
}

// (m,k,n) chosen to cover every dispatch arm: the matmul2d_fixed sizes, the
// n>=16 streaming gate, and a generic fallback whose leading dim lands on and
// off any blocking boundary (m = 1..3 tail-only, 4..8, and not a multiple).
static const int64_t kMMShapes[][3] = {
    {1,1,1}, {2,2,2}, {3,3,3}, {4,4,4}, {4,4,3}, {5,3,1}, {5,4,1}, {7,5,1},
    {7,5,2}, {3,7,2}, {4,9,5}, {6,11,13}, {8,17,15}, {9,16,16}, {5,32,17},
    {10,6,12}, {13,3,4}, {2,8,8}, {8,1,8}, {1,64,33}, {11,5,3}, {6,2,7},
    {17,9,4}, {3,12,6}, {2,5,40}, {0,3,3}, {3,0,4}, {3,4,0}, {5,1,1}, {1,5,1},
};

template <class T>
int mm_check(const char* dt, int& cases) {
    int bad = 0;
    const int nsh = (int)(sizeof(kMMShapes) / sizeof(kMMShapes[0]));
    for (int c = 0; c < nsh; ++c) {
        int64_t m = kMMShapes[c][0], k = kMMShapes[c][1], n = kMMShapes[c][2];
        for (int v = 0; v < 7; ++v) {
            if (v >= 4 && (m == 0 || k == 0 || n == 0)) continue;  // no 0-len views
            MMRng r(0xC0FFEEULL + 7919ULL*(uint64_t)c + 104729ULL*(uint64_t)v);
            Array<T> a, b;
            mm_build<T>(v, m, k, n, r, a, b);
            ++cases;
            if (!mm_same_bits(matmul2d(a, b), mm_ref(a, b))) {
                ++bad;
                if (bad <= 8)
                    std::printf("MATMUL2D BITEXACT case %s (%lld,%lld,%lld) layout %d "
                                "DIFFERS from the ascending-l reference\n",
                                dt, (long long)m, (long long)k, (long long)n, v);
            }
        }
    }
    return bad;
}

// ------------------------------------ batched matmul accumulation-order gate
// nd::matmul's BATCHED arm (ndim > 2) is a separate kernel from matmul2d: its
// own broadcast-strided batch walk, and its own k loop with the row/column
// bases hoisted out of it. The MATMUL2D block above never reaches it, and the
// matmul_batched numpy case is (2,2,2)@(2,2,3) over small integers -- a
// reversed sum of two exactly representable terms is bit-identical, so that
// case would pass against a deliberately reassociated kernel.
//
// The reference below is the same literal ascending-l sum with NOTHING hoisted
// out of the l loop, over operands whose magnitudes span ~17 decades so that
// reordering the k terms moves the mantissa. Compared with memcmp, not
// tolerance -- same reasoning as the matmul2d gate: numpy cannot be the oracle
// because np.matmul goes through BLAS, which blocks and reassociates.
static const double kBmmMags[8] = {1e9, 1e-9, -1e8, 3.25, -1e-7, 7.5e6, -2.5e-8, 1.0};

template <class T> T bmm_rand(MMRng& r, int64_t i);
template <> double bmm_rand<double>(MMRng& r, int64_t i) {
    double u = (double)(r.next() % 2000001) / 1000000.0 - 1.0;   // [-1,1]
    return u * kBmmMags[(size_t)(i % 8)];
}
template <> float bmm_rand<float>(MMRng& r, int64_t i) {
    return (float)bmm_rand<double>(r, i);
}
template <> int64_t bmm_rand<int64_t>(MMRng& r, int64_t i) {
    (void)i; return (int64_t)(r.next() % 2001) - 1000;
}
template <> bool bmm_rand<bool>(MMRng& r, int64_t i) {
    (void)i; return (r.next() & 1) != 0;
}

template <class T>
Array<T> bmm_make(const Shape& sh, MMRng& r) {
    Array<T> a = Array<T>::alloc(sh);
    int64_t n = prod(sh);
    for (int64_t i = 0; i < n; ++i) (*a.data)[(size_t)i] = bmm_rand<T>(r, i);
    return a;
}

// Batch offsets are derived the same way the runtime derives them (there is
// only one correct broadcast); what this reference does NOT copy is the index
// hoist -- every A/B address is recomputed in full inside the l loop, and l
// runs ascending.
template <class T>
Array<T> bmm_ref(const Array<T>& a, const Array<T>& b) {
    int64_t na = a.ndim(), nb = b.ndim();
    Shape abatch(a.shape.begin(), a.shape.end() - 2);
    Shape bbatch(b.shape.begin(), b.shape.end() - 2);
    Shape batch = broadcast_shapes(abatch, bbatch);
    int64_t m = a.shape[na-2], k = a.shape[na-1], n = b.shape[nb-1];
    Shape osh = batch; osh.push_back(m); osh.push_back(n);
    Array<T> out = zeros<T>(osh);
    Shape ash = batch; ash.push_back(a.shape[na-2]); ash.push_back(a.shape[na-1]);
    Shape bsh = batch; bsh.push_back(b.shape[nb-2]); bsh.push_back(b.shape[nb-1]);
    Shape sa = bcast_strides(a, ash);
    Shape sb = bcast_strides(b, bsh);
    Shape bidx(batch.size(), 0);
    int64_t nbatch = prod(batch);
    for (int64_t bi = 0; bi < nbatch; ++bi) {
        int64_t oa = a.offset, ob = b.offset;
        for (size_t d = 0; d < batch.size(); ++d) { oa += bidx[d]*sa[d]; ob += bidx[d]*sb[d]; }
        for (int64_t i = 0; i < m; ++i)
            for (int64_t j = 0; j < n; ++j) {
                T acc = (T)0;
                for (int64_t l = 0; l < k; ++l)
                    acc += (*a.data)[(size_t)(oa + i*a.strides[na-2] + l*a.strides[na-1])]
                         * (*b.data)[(size_t)(ob + l*b.strides[nb-2] + j*b.strides[nb-1])];
                (*out.data)[(size_t)(bi*m*n + i*n + j)] = acc;
            }
        incr(bidx, batch);
    }
    return out;
}

template <class T>
int bmm_check(const char* tag, const Array<T>& a, const Array<T>& b, int& cases) {
    ++cases;
    if (mm_same_bits(matmul(a, b), bmm_ref(a, b))) return 0;
    std::printf("MATMUL BATCHED BITEXACT case %s DIFFERS from the ascending-l "
                "reference\n", tag);
    return 1;
}

int main() {
    // ---- elementwise + broadcasting ----
    {
        caseName("add_broadcast");
        auto a = from_data<double>({1,2,3,4,5,6}, {2,3});
        auto b = from_data<double>({10,20,30}, {3});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","out", add(a,b)); endCase();
    }
    {
        caseName("sub_mul");
        auto a = from_data<double>({1,2,3,4}, {2,2});
        auto b = from_data<double>({4,3,2,1}, {2,2});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","out", mul(sub(a,b), 2.0)); endCase();
    }
    {
        caseName("truediv_int_promote");
        auto a = from_data<int64_t>({1,2,3,7}, {4});
        emit("IN","a",a);
        emit("OUT","out", divide(a, (int64_t)2)); endCase();  // -> float64
    }
    {
        caseName("floordiv_mod_neg");
        auto a = from_data<int64_t>({-7,7,-7,7}, {4});
        auto b = from_data<int64_t>({3,3,-3,-3}, {4});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","fd", floordiv(a,b));
        emit("OUT","md", mod(a,b)); endCase();
    }
    {
        caseName("power_float");
        auto a = from_data<double>({2,3,4}, {3});
        auto b = from_data<double>({0.5,2,0.5}, {3});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","out", power(a,b)); endCase();
    }
    {
        caseName("negate");
        auto a = from_data<double>({1,-2,3}, {3});
        emit("IN","a",a);
        emit("OUT","out", negate(a)); endCase();
    }
    {
        caseName("newaxis_outer");   // a[:,None] * b  -> (3,3)
        auto a = from_data<double>({1,2,3}, {3});
        auto b = from_data<double>({10,20,30}, {3});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","out", mul(newaxis(a,1), b)); endCase();
    }
    {
        caseName("maximum_minimum");
        auto a = from_data<double>({1,5,3}, {3});
        auto b = from_data<double>({4,2,3}, {3});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","mx", maximum(a,b));
        emit("OUT","mn", minimum(a,b)); endCase();
    }
    // ---- reductions ----
    {
        caseName("sum_axes");
        auto a = from_data<double>({1,2,3,4,5,6}, {2,3});
        emit("IN","a",a);
        emit("OUT","s0", sum(a, {0}));
        emit("OUT","s1", sum(a, {1}));
        emit("OUT","sall", sum(a, {}));
        emit("OUT","s1k", sum(a, {1}, true)); endCase();
    }
    {
        caseName("sum_multiaxis_3d");
        auto a = arange<double>(0,24,1);
        a = reshape(a, {2,3,4});
        emit("IN","a",a);
        emit("OUT","s12", sum(a, {1,2}));
        emit("OUT","s02", sum(a, {0,2})); endCase();
    }
    {
        // sum_mul must equal sum(mul(a,b)) both where its fused path fires (a
        // trailing, packed reduced axis) and where it must fall back: a
        // NON-trailing axis, and a BROADCAST product whose operands do not even
        // share a shape. A fallback that silently dropped the broadcast would
        // pass any test that only ever fed it equal shapes.
        // numpy RAISES LinAlgError here, so there is no numpy expression to
        // compare against -- the oracle hardcodes the contract instead. A
        // singular system must yield ZEROS, never NaN/inf: a compute that
        // emitted NaN would poison the DAG's world-matrix cache.
        caseName("solve_singular_yields_zeros");
        auto s = from_data<double>({1,2, 2,4}, {2,2});   // rank 1 -> singular
        auto r = from_data<double>({1,1}, {2});
        emit("IN","s",s); emit("IN","r",r);
        emit("OUT","x", solve(s, r)); endCase();
    }
    {
        caseName("sum_mul_fused_and_fallback");
        auto a = arange<double>(0,24,1);  a = reshape(a, {2,3,4});
        auto b = arange<double>(3,27,1);  b = reshape(b, {2,3,4});
        auto c = arange<double>(1,7,1);   c = reshape(c, {2,3,1});
        emit("IN","a",a); emit("IN","b",b); emit("IN","c",c);
        emit("OUT","last",  sum_mul(a, b, {2}));        // fires
        emit("OUT","lastk", sum_mul(a, b, {2}, true));  // fires, keepdims
        emit("OUT","all",   sum_mul(a, b, {}));         // fires (reduce-all)
        emit("OUT","mid",   sum_mul(a, b, {1}));        // falls back
        emit("OUT","first", sum_mul(a, b, {0}));        // falls back
        emit("OUT","bcast", sum_mul(c, b, {2}));        // falls back (broadcast)
        endCase();
    }
    {
        // Prefix sums are NOT reassociable, so the scan order is part of the
        // contract, not an implementation detail. Values chosen so a reordered
        // accumulation would actually show up: 1e16 next to 1.0 means adding
        // the big term first ABSORBS the small ones.
        caseName("cumsum_2d");
        auto a = from_data<double>({1,2,3, 4,5,6}, {2,3});
        emit("IN","a",a);
        emit("OUT","c0", cumsum(a, 0, false));
        emit("OUT","c1", cumsum(a, 1, false));
        emit("OUT","cn1", cumsum(a, -1, false));   // negative axis
        emit("OUT","cflat", cumsum(a, 0, true)); endCase();
    }
    {
        caseName("cumsum_rounding_order");
        auto a = from_data<double>({1e16, 1.0, 1.0, -1e16}, {4});
        emit("IN","a",a);
        emit("OUT","c", cumsum(a, 0, false)); endCase();
    }
    {
        // A transposed view is non-contiguous with a non-trivial stride pair;
        // the scan must follow strides, not raw buffer order.
        caseName("cumsum_strided");
        auto r = arange<double>(0,12,1);
        r = reshape(r, {3,4});
        auto t = transpose(r);
        emit("IN","t",t);
        emit("OUT","c0", cumsum(t, 0, false));
        emit("OUT","cflat", cumsum(t, 0, true)); endCase();
    }
    {
        caseName("cumsum_3d_int");
        auto a = arange<int64_t>(0,24,1);
        a = reshape(a, {2,3,4});
        emit("IN","a",a);
        emit("OUT","c1", cumsum(a, 1, false));
        emit("OUT","c2", cumsum(a, 2, false));
        emit("OUT","cflat", cumsum(a, 0, true)); endCase();
    }
    {
        caseName("mean_norm");
        auto a = from_data<double>({3,4, 6,8, 0,0}, {3,2});
        emit("IN","a",a);
        emit("OUT","m0", mean(a, {0}));
        emit("OUT","n1", norm(a, {1})); endCase();
    }
    {
        caseName("minmax_reduce");
        auto a = from_data<double>({3,1,4,1,5,9}, {2,3});
        emit("IN","a",a);
        emit("OUT","mx1", reduce_max(a, {1}));
        emit("OUT","mn0", reduce_min(a, {0})); endCase();
    }
    // ---- linalg ----
    {
        caseName("matmul_2d");
        auto a = from_data<double>({1,2,3,4,5,6}, {2,3});
        auto b = from_data<double>({7,8, 9,10, 11,12}, {3,2});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","out", matmul(a,b)); endCase();
    }
    {
        caseName("matmul_2d_1d");
        auto a = from_data<double>({1,2,3,4,5,6}, {2,3});
        auto v = from_data<double>({1,0,-1}, {3});
        emit("IN","a",a); emit("IN","v",v);
        emit("OUT","mv", matmul(a,v));
        emit("OUT","d", scalar<double>(dot1d(v, v))); endCase();  // v.v
    }
    {
        caseName("matmul_batched");
        auto a = arange<double>(0,8,1);  a = reshape(a, {2,2,2});
        auto b = arange<double>(8,20,1); b = reshape(b, {2,2,3});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","out", matmul(a,b)); endCase();
    }
    {
        caseName("cross_transpose");
        auto a = from_data<double>({1,0,0}, {3});
        auto b = from_data<double>({0,1,0}, {3});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","c", cross(a,b));
        auto m = from_data<double>({1,2,3,4,5,6}, {2,3});
        emit("IN","m",m);
        emit("OUT","mt", transpose(m)); endCase();
    }
    // ---- shape manip ----
    {
        caseName("reshape_infer_ravel");
        auto a = arange<double>(0,12,1);
        auto r = reshape(a, {3,-1});
        emit("IN","a",a);
        emit("OUT","r", r);
        emit("OUT","rav", ravel(transpose(r)));  // non-contiguous ravel = C-order copy
        endCase();
    }
    {
        caseName("astype_trunc");
        auto a = from_data<double>({-2.7, 2.7, -0.9, 3.99}, {4});
        emit("IN","a",a);
        emit("OUT","i", astype<int64_t>(a));
        auto b = from_data<int64_t>({1,2,3}, {3});
        emit("IN","b",b);
        emit("OUT","f", astype<double>(b)); endCase();
    }
    // ---- slicing ----
    {
        caseName("slice_1d");
        auto a = arange<double>(0,10,1);
        emit("IN","a",a);
        emit("OUT","mid", slice(a, {Sl::range(2,7)}));      // a[2:7]
        emit("OUT","step2", slice(a, {Sl::stepped(2)}));    // a[::2]
        emit("OUT","rev", slice(a, {Sl::rev()}));           // a[::-1]
        emit("OUT","head", slice(a, {Sl::to(-2)}));         // a[:-2]
        emit("OUT","tail", slice(a, {Sl::from(3)}));        // a[3:]
        endCase();
    }
    {
        caseName("slice_2d_block_index");
        auto m = arange<double>(0,12,1); m = reshape(m, {3,4});
        emit("IN","m",m);
        emit("OUT","block", slice(m, {Sl::full(), Sl::range(1,3)})); // m[:,1:3]
        emit("OUT","row1", slice(m, {Sl::at(1), Sl::full()}));       // m[1,:]
        emit("OUT","lastcol", slice(m, {Sl::full(), Sl::at(-1)}));   // m[:,-1]
        endCase();
    }
    {
        caseName("slice_assign");
        auto z = zeros<double>({4,4});
        auto blk = slice(z, {Sl::range(1,3), Sl::range(1,3)});
        assign(blk, from_data<double>({5,6,7,8}, {2,2}));
        emit("OUT","z", z); endCase();
    }
    // ---- constructors ----
    {
        caseName("constructors");
        emit("OUT","z", zeros<double>({2,2}));
        emit("OUT","o", ones<double>({3}));
        emit("OUT","f", full<double>({2,2}, 7.0));
        emit("OUT","e", eye(3));
        emit("OUT","ar", arange<double>(2,11,3));
        emit("OUT","ls", linspace(0,1,5));
        emit("OUT","lsne", linspace(0,1,5,false));
        endCase();
    }
    // ---- ufuncs ----
    {
        caseName("ufuncs");
        auto a = from_data<double>({0, 1.5707963267948966, -3.14159, 4.0, -2.5}, {5});
        emit("IN","a",a);
        emit("OUT","sin", sin(a));
        emit("OUT","sqrt", sqrt(from_data<double>({0,1,4,9},{4})));
        emit("OUT","floor", floor(a));
        emit("OUT","sign", sign(a));
        emit("OUT","fabs", fabs(a));
        emit("OUT","exp", exp(from_data<double>({0,1,2},{3})));
        endCase();
    }
    // ---- comparison -> bool (P1) ----
    {
        caseName("compare_ops");
        auto a = from_data<double>({1,2,3,2,1}, {5});
        auto b = from_data<double>({2,2,2,2,2}, {5});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","eq", cmp_eq(a,b));
        emit("OUT","lt", cmp_lt(a,b));
        emit("OUT","ge", cmp_ge(a,b));
        emit("OUT","ne_s", cmp_ne(a, 2.0));   // scalar rhs
        endCase();
    }
    {
        caseName("compare_broadcast");
        auto m = from_data<double>({1,2,3,4,5,6}, {2,3});
        auto r = from_data<double>({2,2,2}, {3});
        emit("IN","m",m); emit("IN","r",r);
        emit("OUT","gt", cmp_gt(m,r));
        endCase();
    }
    // ---- bitwise / logical (P1) ----
    {
        caseName("bitwise_int");
        auto a = from_data<int64_t>({6,5,3,12}, {4});
        auto b = from_data<int64_t>({3,1,7,10}, {4});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","band", bit_and(a,b));
        emit("OUT","bor",  bit_or(a,b));
        emit("OUT","bxor", bit_xor(a,b));
        emit("OUT","inv",  invert(a));
        endCase();
    }
    {
        caseName("bitwise_bool");
        auto a = from_data<bool>({true,true,false,false}, {4});
        auto b = from_data<bool>({true,false,true,false}, {4});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","band", bit_and(a,b));
        emit("OUT","bor",  bit_or(a,b));
        emit("OUT","inv",  invert(a));
        endCase();
    }
    {
        caseName("logical_ops");
        auto a = from_data<int64_t>({0,3,0,5}, {4});
        auto b = from_data<int64_t>({1,0,0,2}, {4});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","land", logical_and(a,b));
        emit("OUT","lor",  logical_or(a,b));
        emit("OUT","lnot", logical_not(a));
        endCase();
    }
    // ---- where (select) ----
    {
        caseName("where_op");
        auto cond = from_data<bool>({true,false,true,false,true}, {5});
        auto a = from_data<double>({10,20,30,40,50}, {5});
        auto b = from_data<double>({1,2,3,4,5}, {5});
        emit("IN","cond",cond); emit("IN","a",a); emit("IN","b",b);
        emit("OUT","w", where(cond,a,b));
        emit("OUT","ws", where(cond, 0.0, b));   // scalar-a
        endCase();
    }
    // ---- nonzero (C-order: rows outer, cols inner) ----
    {
        caseName("nonzero_2d");
        auto m = from_data<int64_t>({0,1,0, 1,0,1}, {2,3});
        emit("IN","m",m);
        auto nz = nonzero(m);
        emit("OUT","ys", nz[0]);
        emit("OUT","xs", nz[1]);
        endCase();
    }
    // ---- concatenate / stack ----
    {
        caseName("concat_stack");
        auto a = from_data<double>({1,2,3,4}, {2,2});
        auto b = from_data<double>({5,6,7,8}, {2,2});
        emit("IN","a",a); emit("IN","b",b);
        emit("OUT","c0", concatenate<double>({a,b}, 0));
        emit("OUT","c1", concatenate<double>({a,b}, 1));
        emit("OUT","s0", stack<double>({a,b}, 0));
        emit("OUT","s1", stack<double>({a,b}, 1));
        endCase();
    }
    // ---- concatenate view-layout coverage ----
    // concatenate() BLOCK-COPIES any operand whose elements are flat in C-order
    // (concat_src_is_flat) and falls back to the odometer otherwise. The
    // concat_stack case above is contiguous-only, so it exercises neither the
    // offset form, nor a genuinely strided operand, nor a 3-D axis where the
    // copied block is shape[axis]*inner rather than shape[axis].
    {
        caseName("concat_views");
        auto base = from_data<double>({1,2,3,4,5,6,7,8,9,10,11,12}, {4,3});
        auto offv = slice(base, {Sl::mk(true,1,true,4,1), Sl::full()});   // (3,3) offset 3, flat
        auto strv = slice(base, {Sl::full(), Sl::mk(true,0,true,3,2)});   // (4,2) strides {3,2}, NOT flat
        auto other3 = from_data<double>({100,200,300,400,500,600,700,800,900}, {3,3});
        auto other2 = from_data<double>({-1,-2,-3,-4,-5,-6,-7,-8}, {4,2});
        emit("IN","offv",offv); emit("IN","strv",strv);
        emit("IN","other3",other3); emit("IN","other2",other2);
        emit("OUT","cf",   concatenate<double>({offv, other3}, 1));   // flat operand, offset != 0
        emit("OUT","cs",   concatenate<double>({strv, other2}, 1));   // strided operand -> fallback
        emit("OUT","cmix", concatenate<double>({strv, other2}, 0));
        auto c3 = from_data<double>({1,2,3,4,5,6,7,8,9,10,11,12}, {2,3,2});
        auto d3 = from_data<double>({21,22,23,24}, {2,1,2});
        emit("IN","c3",c3); emit("IN","d3",d3);
        emit("OUT","c3d",  concatenate<double>({c3, d3}, 1));         // (2,4,2), inner = 2
        auto p = from_data<double>({1,2,3,4,5}, {5});
        auto q = from_data<double>({6,7,8,9,10}, {5});
        auto r = from_data<double>({11,12,13,14,15}, {5});
        emit("IN","p",p); emit("IN","q",q); emit("IN","r",r);
        emit("OUT","st1", stack<double>({p,q,r}, 1));                 // newaxis stride-0 operands
        emit("OUT","st0", stack<double>({p,q,r}, 0));
        endCase();
    }
    // ---- column_stack / tile ----
    {
        caseName("colstack_tile");
        auto x = from_data<double>({1,2,3}, {3});
        auto y = from_data<double>({4,5,6}, {3});
        auto z = from_data<double>({7,8,9}, {3});
        emit("IN","x",x); emit("IN","y",y); emit("IN","z",z);
        emit("OUT","cs", column_stack<double>({x,y,z}));   // (3,3)
        auto t1 = from_data<double>({1,2}, {2});
        emit("IN","t1",t1);
        emit("OUT","tl", tile(t1, Shape{3}));              // (6,)
        auto t2 = from_data<double>({1,2,3,4}, {2,2});
        emit("IN","t2",t2);
        emit("OUT","tl2", tile(t2, Shape{2,1}));           // (4,2)
        endCase();
    }
    // ---- take / roll ----
    {
        caseName("take_roll");
        auto a = from_data<double>({10,11,12,13,14}, {5});
        auto idx = from_data<int64_t>({0,2,4,4,1}, {5});
        emit("IN","a",a); emit("IN","idx",idx);
        emit("OUT","tk", take(a, idx));
        emit("OUT","rl", roll(a, (int64_t)2));
        auto m = from_data<double>({0,1,2,3,4,5}, {2,3});
        emit("IN","m",m);
        emit("OUT","tkax", take(m, from_data<int64_t>({2,0},{2}), (int64_t)1)); // cols 2,0
        emit("OUT","rlax", roll(m, (int64_t)1, (int64_t)0));                    // rows down 1
        endCase();
    }
    // ---- matmul2d accumulation-order gate (bytes, not tolerance) ----
    {
        int cases = 0, bad = 0;
        bad += mm_check<double>("f64", cases);
        bad += mm_check<int64_t>("i64", cases);
        bad += mm_check<bool>("bool", cases);
        if (bad) {
            std::printf("MATMUL2D BITEXACT FAIL cases=%d bad=%d\n", cases, bad);
            return 1;
        }
        std::printf("MATMUL2D BITEXACT OK cases=%d\n", cases);
    }
    // ---- batched matmul accumulation-order gate (bytes, not tolerance) ----
    {
        int cases = 0, bad = 0;
        MMRng r(0x5EEDB47CULL);
        {   // patchRelax's real shape
            auto A = bmm_make<double>({97,3,3}, r); auto B = bmm_make<double>({97,3,1}, r);
            bad += bmm_check("f64 (97,3,3)@(97,3,1)", A, B, cases);
        }
        {   // 4x4 rigid-transform batch
            auto A = bmm_make<double>({53,4,4}, r); auto B = bmm_make<double>({53,4,4}, r);
            bad += bmm_check("f64 (53,4,4)@(53,4,4)", A, B, cases);
        }
        {   // long k -- the accumulation-order canary
            auto A = bmm_make<double>({7,5,64}, r); auto B = bmm_make<double>({7,64,6}, r);
            bad += bmm_check("f64 (7,5,64)@(7,64,6)", A, B, cases);
        }
        {   // TRANSPOSED left operand (non-contiguous, positive strides)
            auto A = transpose(bmm_make<double>({11,6,4}, r), {0,2,1});
            auto B = bmm_make<double>({11,6,5}, r);
            bad += bmm_check("f64 transposed-left", A, B, cases);
        }
        {   // TRANSPOSED right operand
            auto A = bmm_make<double>({9,4,7}, r);
            auto B = transpose(bmm_make<double>({9,3,7}, r), {0,2,1});
            bad += bmm_check("f64 transposed-right", A, B, cases);
        }
        {   // newaxis -> stride-0 broadcast batch on the LEFT
            auto A = newaxis(bmm_make<double>({3,3}, r), 0);
            auto B = bmm_make<double>({8,3,2}, r);
            bad += bmm_check("f64 bcast-left", A, B, cases);
        }
        {   // newaxis -> stride-0 broadcast batch on the RIGHT
            auto A = bmm_make<double>({8,2,5}, r);
            auto B = newaxis(bmm_make<double>({5,4}, r), 0);
            bad += bmm_check("f64 bcast-right", A, B, cases);
        }
        {   // multi-dim batch, broadcast on one axis each side
            auto A = bmm_make<double>({4,1,3,3}, r); auto B = bmm_make<double>({1,5,3,3}, r);
            bad += bmm_check("f64 (4,1,3,3)@(1,5,3,3)", A, B, cases);
        }
        {   // NONZERO-OFFSET sliced views on both sides
            auto A = slice(bmm_make<double>({12,8,8}, r),
                           {Sl::range(2,10), Sl::range(1,6), Sl::range(3,7)});
            auto B = slice(bmm_make<double>({12,8,8}, r),
                           {Sl::range(2,10), Sl::range(3,7), Sl::range(0,5)});
            bad += bmm_check("f64 offset-slices", A, B, cases);
        }
        {   // STEP-2 sliced views (stride multiples)
            auto A = slice(bmm_make<double>({6,10,10}, r),
                           {Sl::full(), Sl::range(0,10,2), Sl::range(1,9,2)});
            auto B = slice(bmm_make<double>({6,10,10}, r),
                           {Sl::full(), Sl::range(1,9,2), Sl::range(0,10,2)});
            bad += bmm_check("f64 step2-slices", A, B, cases);
        }
        {   // REVERSED (negative-stride) views
            auto A = slice(bmm_make<double>({5,6,6}, r), {Sl::full(), Sl::full(), Sl::rev()});
            auto B = slice(bmm_make<double>({5,6,6}, r), {Sl::full(), Sl::rev(), Sl::full()});
            bad += bmm_check("f64 reversed-views", A, B, cases);
        }
        {   // degenerate m=1 / n=1 / k=1
            auto A = bmm_make<double>({4,1,5}, r); auto B = bmm_make<double>({4,5,1}, r);
            bad += bmm_check("f64 (4,1,5)@(4,5,1)", A, B, cases);
            auto C = bmm_make<double>({4,6,1}, r); auto D = bmm_make<double>({4,1,7}, r);
            bad += bmm_check("f64 (4,6,1)@(4,1,7)", C, D, cases);
        }
        {   // EMPTY BATCH
            auto A = bmm_make<double>({0,3,3}, r); auto B = bmm_make<double>({0,3,1}, r);
            bad += bmm_check("f64 empty-batch", A, B, cases);
        }
        {   // EMPTY k -- the l loop never runs; result must be all zeros
            auto A = bmm_make<double>({2,3,0}, r); auto B = bmm_make<double>({2,0,4}, r);
            bad += bmm_check("f64 empty-k", A, B, cases);
        }
        {   // integer arm
            auto A = bmm_make<int64_t>({7,3,4}, r); auto B = bmm_make<int64_t>({7,4,3}, r);
            bad += bmm_check("i64 (7,3,4)@(7,4,3)", A, B, cases);
        }
        {   // fp32 arm -- narrower mantissa, so it is the most order-sensitive
            auto A = bmm_make<float>({13,4,6}, r); auto B = bmm_make<float>({13,6,4}, r);
            bad += bmm_check("f32 (13,4,6)@(13,6,4)", A, B, cases);
        }
        {   // bool -- the instantiation that has no vector<bool>::data()
            auto A = bmm_make<bool>({3,2,2}, r); auto B = bmm_make<bool>({3,2,2}, r);
            bad += bmm_check("bool (3,2,2)@(3,2,2)", A, B, cases);
        }
        if (bad) {
            std::printf("MATMUL BATCHED BITEXACT FAIL cases=%d bad=%d\n", cases, bad);
            return 1;
        }
        std::printf("MATMUL BATCHED BITEXACT OK cases=%d\n", cases);
    }
    return 0;
}
