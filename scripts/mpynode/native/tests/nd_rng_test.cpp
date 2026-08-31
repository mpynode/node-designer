// nd_rng_test.cpp — standalone bit-exactness exerciser for nd::MT19937.
//
// Prints, per case, a sequence of doubles drawn from nd::MT19937 in the exact
// order/shape numpy's legacy RandomState would produce. A companion numpy
// oracle (nd_rng_test.py, run under mayapy) recomputes each sequence with
// numpy.random.RandomState and asserts BIT-IDENTICAL equality (==, not
// allclose) — the 53-bit draws are power-of-two rationals, so both sides yield
// the same IEEE double and %.17g round-trips it exactly.
//
// Build:
//   clang++ -std=c++17 -O2 nd_rng_test.cpp -o /tmp/nd_rng
// Protocol (one line per case):
//   SEQ  <name> <count> : <flat C-order values>          (scalar-seed / array-seed / shape-fill)
//   SHAPE <name> <seed> <ndim> <d0..> : <flat C-order values>

#include "nd_runtime.h"
#include <cstdio>
#include <vector>

using namespace nd;

static void emit_seq(const char* name, const std::vector<double>& v) {
    std::printf("SEQ %s %zu :", name, v.size());
    for (double x : v) std::printf(" %.17g", x);
    std::printf("\n");
}

int main() {
    // Scalar-int seeds (RandomState(seed) -> mt19937_seed). These are the paths
    // real nodes use: seed = 0, 1, int(frame), int(seed)&0x7fffffff, etc.
    const uint32_t seeds[] = {0u, 1u, 42u, 12345u, 987654321u, 2147483647u};
    for (uint32_t s : seeds) {
        MT19937 r; r.seed(s);
        std::vector<double> v;
        for (int i = 0; i < 16; ++i) v.push_back(r.next_double());
        char nm[64];
        std::snprintf(nm, sizeof(nm), "seed_%u", (unsigned)s);
        emit_seq(nm, v);
    }

    // C-order shape fill (RandomState(seed).random((r,c)) ravelled C-order).
    {
        MT19937 r; r.seed(7);
        Array<double> a = r.random({3, 4});
        std::vector<double> v(a.data->begin(), a.data->end());
        std::printf("SHAPE fill7 7 2 3 4 :");
        for (double x : v) std::printf(" %.17g", x);
        std::printf("\n");
    }
    {
        MT19937 r; r.seed(101);
        Array<double> a = r.random({2, 2, 3});
        std::vector<double> v(a.data->begin(), a.data->end());
        std::printf("SHAPE fill101 101 3 2 2 3 :");
        for (double x : v) std::printf(" %.17g", x);
        std::printf("\n");
    }

    // Array-seed path (RandomState(np.array([...])) -> init_by_array).
    {
        MT19937 r; r.init_by_array({1u, 2u, 3u, 4u});
        std::vector<double> v;
        for (int i = 0; i < 12; ++i) v.push_back(r.next_double());
        emit_seq("initarr_1_2_3_4", v);
    }
    // Multi-element only: numpy squeezes a 1-element array seed to a scalar and
    // takes the mt19937_seed path, so init_by_array is only reachable with >=2
    // distinct elements.
    {
        MT19937 r; r.init_by_array({7u, 13u});
        std::vector<double> v;
        for (int i = 0; i < 12; ++i) v.push_back(r.next_double());
        emit_seq("initarr_7_13", v);
    }

    return 0;
}
