// nd_intnan_test.cpp -- degenerate-divisor / NaN parity fixtures for nd_runtime.h
//
// Companion to nd_intnan_test.py, which recomputes every case with numpy and
// asserts parity. Two distinct hazards are pinned here:
//
//   1. INTEGER // and % with a 0 or -1 divisor. numpy yields 0 (and INT64_MIN
//      for INT64_MIN // -1) with only a RuntimeWarning; a raw `ia / ib` raises
//      SIGFPE, which is a SIGNAL, not a C++ exception -- it walks straight
//      through the node's catch(std::exception) and kills the host. If the
//      guards regress, this binary dies on the signal and the driver reports
//      "RUN FAILED" rather than a value mismatch.
//   2. np.minimum / np.maximum (and the np.min / np.max reductions built on
//      them) PROPAGATE NaN from either operand.
//
// Both the collapsed and the strided ew_binary branches, and both the packed
// fast path and the general strided path of reduce(), are exercised so the two
// implementations of each op cannot drift apart.
//
// Protocol (one line per output):
//     RES <case> <name> <i64|f64> <n> : v0 v1 ...
// Values are printed with %lld / %.17g; "nan" and "inf" round-trip through
// Python float().

#include "nd_runtime.h"

#include <cstdio>
#include <limits>
#include <string>
#include <vector>

static void emit_i(const char* cs, const char* nm, const nd::Array<int64_t>& a) {
    nd::Array<int64_t> c = a.copy();
    std::printf("RES %s %s i64 %lld :", cs, nm, (long long)c.size());
    for (int64_t i = 0; i < c.size(); ++i)
        std::printf(" %lld", (long long)(*c.data)[(size_t)i]);
    std::printf("\n");
}

static void emit_f(const char* cs, const char* nm, const nd::Array<double>& a) {
    nd::Array<double> c = a.copy();
    std::printf("RES %s %s f64 %lld :", cs, nm, (long long)c.size());
    for (int64_t i = 0; i < c.size(); ++i)
        std::printf(" %.17g", (*c.data)[(size_t)i]);
    std::printf("\n");
}

static void emit_i_scalars(const char* cs, const char* nm,
                           const std::vector<int64_t>& v) {
    std::printf("RES %s %s i64 %lld :", cs, nm, (long long)v.size());
    for (size_t i = 0; i < v.size(); ++i) std::printf(" %lld", (long long)v[i]);
    std::printf("\n");
}

static void emit_f_scalars(const char* cs, const char* nm,
                           const std::vector<double>& v) {
    std::printf("RES %s %s f64 %lld :", cs, nm, (long long)v.size());
    for (size_t i = 0; i < v.size(); ++i) std::printf(" %.17g", v[i]);
    std::printf("\n");
}

int main() {
    const int64_t IMIN = std::numeric_limits<int64_t>::min();
    const double NAN_ = std::numeric_limits<double>::quiet_NaN();
    const double INF_ = std::numeric_limits<double>::infinity();

    // ---- 1. integer // and % with degenerate divisors (array path) ----------
    // Every (numerator, divisor) pairing that can trap or overflow, plus the
    // ordinary negative-operand cases so the existing round-toward--inf
    // behaviour is re-pinned alongside the new guards.
    {
        std::vector<int64_t> na{ 7, -7,  0,  5, -5,  IMIN, IMIN, IMIN,  9, -9, IMIN };
        std::vector<int64_t> nb{ 0,  0,  0, -1, -1,  -1,   0,    1,     4,  4, 3 };
        nd::Array<int64_t> a = nd::from_data<int64_t>(na, {(int64_t)na.size()});
        nd::Array<int64_t> b = nd::from_data<int64_t>(nb, {(int64_t)nb.size()});
        emit_i("int_degenerate", "fd", nd::floordiv(a, b));
        emit_i("int_degenerate", "md", nd::mod(a, b));
    }

    // ---- 2. the SCALAR path (py_to_cpp _scalar_binop emits apply_binop) -----
    {
        std::vector<int64_t> fd, md;
        const int64_t xs[6] = { 7, -7, 0, IMIN, IMIN, -13 };
        const int64_t ys[6] = { 0,  0, 0, -1,   0,    -1 };
        for (int i = 0; i < 6; ++i) {
            fd.push_back(nd::apply_binop<int64_t>(nd::BinOp::FloorDiv, xs[i], ys[i]));
            md.push_back(nd::apply_binop<int64_t>(nd::BinOp::Mod, xs[i], ys[i]));
        }
        emit_i_scalars("int_scalar", "fd", fd);
        emit_i_scalars("int_scalar", "md", md);
    }

    // ---- 3. FLOAT // and % by zero already match numpy -- pin them ---------
    {
        std::vector<double> fa{ 5.0, -5.0, 0.0, -0.0 };
        std::vector<double> fb{ 0.0,  0.0, 0.0,  0.0 };
        nd::Array<double> a = nd::from_data<double>(fa, {4});
        nd::Array<double> b = nd::from_data<double>(fb, {4});
        emit_f("float_divzero", "fd", nd::floordiv(a, b));
        emit_f("float_divzero", "md", nd::mod(a, b));
    }

    // ---- 4. minimum/maximum NaN propagation, COLLAPSED ew_binary branch ----
    // Both operands are contiguous over the output shape, so ew_binary takes
    // its single flat span. NaN appears on the left, on the right, on both, and
    // nowhere; +-inf and signed zero ride along as controls.
    {
        std::vector<double> xa{ NAN_,   1.0, NAN_,  2.0, -0.0,  INF_, -INF_,  3.0 };
        std::vector<double> xb{  1.0, NAN_, NAN_,  7.0,  0.0,   1.0,   1.0, NAN_ };
        nd::Array<double> a = nd::from_data<double>(xa, {8});
        nd::Array<double> b = nd::from_data<double>(xb, {8});
        emit_f("minmax_flat", "mx", nd::maximum(a, b));
        emit_f("minmax_flat", "mn", nd::minimum(a, b));
    }

    // ---- 5. minimum/maximum NaN, STRIDED (broadcast) ew_binary branch ------
    // (3,1) against (3,2): a.shape != osh, so the collapse test fails and the
    // outer-walk path runs instead. Must agree with case 4 element for element.
    {
        nd::Array<double> col = nd::from_data<double>({NAN_, 2.0, -1.0}, {3, 1});
        nd::Array<double> m = nd::from_data<double>(
            {1.0, NAN_, NAN_, 5.0, 4.0, NAN_}, {3, 2});
        emit_f("minmax_bcast", "mx", nd::maximum(col, m));
        emit_f("minmax_bcast", "mn", nd::minimum(col, m));
    }

    // ---- 6. np.max / np.min reductions over NaN ----------------------------
    // axis=1 is the TRAILING packed axis -> reduce()'s fast path; axis=0 is not
    // trailing -> the general strided path. Both must propagate.
    {
        nd::Array<double> m = nd::from_data<double>(
            {1.0, NAN_, 3.0,
             4.0,  5.0, 6.0,
             NAN_, 8.0, 9.0}, {3, 3});
        emit_f("reduce_nan", "mx1", nd::reduce_max(m, {1}));
        emit_f("reduce_nan", "mn1", nd::reduce_min(m, {1}));
        emit_f("reduce_nan", "mx0", nd::reduce_max(m, {0}));
        emit_f("reduce_nan", "mn0", nd::reduce_min(m, {0}));
        emit_f("reduce_nan", "mxall", nd::reduce_max(m));
        emit_f("reduce_nan", "mnall", nd::reduce_min(m));
    }

    // ---- 7. integer max/min are unaffected by the NaN guard ----------------
    {
        nd::Array<int64_t> a = nd::from_data<int64_t>({3, -4, 0, IMIN}, {4});
        nd::Array<int64_t> b = nd::from_data<int64_t>({1, 5, 0, 7}, {4});
        emit_i("int_minmax", "mx", nd::maximum(a, b));
        emit_i("int_minmax", "mn", nd::minimum(a, b));
        emit_i("int_minmax", "rmx", nd::reduce_max(a));
        emit_i("int_minmax", "rmn", nd::reduce_min(a));
    }

    // ---- 8. scalar apply_binop Min/Max (the fused-loop / reduce operand) ---
    {
        std::vector<double> mx, mn;
        const double ls[4] = { NAN_, 1.0, NAN_, 2.0 };
        const double rs[4] = { 1.0, NAN_, NAN_, 7.0 };
        for (int i = 0; i < 4; ++i) {
            mx.push_back(nd::apply_binop<double>(nd::BinOp::Max, ls[i], rs[i]));
            mn.push_back(nd::apply_binop<double>(nd::BinOp::Min, ls[i], rs[i]));
        }
        emit_f_scalars("minmax_scalar", "mx", mx);
        emit_f_scalars("minmax_scalar", "mn", mn);
    }

    std::printf("DONE\n");
    return 0;
}
