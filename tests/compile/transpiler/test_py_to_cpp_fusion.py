"""Maya-FREE: Phase-2 deterministic ELEMENTWISE FUSION in the numpy->C++ transpiler.

A per-assignment tree of elementwise ops (a + b*c, maximum, sqrt, ...) used to
emit one allocating `nd::` temp + one loop PER op. Fusion collapses the whole
elementwise RHS tree into ONE scalar C++ loop that reads each array leaf per
element and writes a flat output buffer -- byte-identical to the nested `nd::`
result. A runtime guard (leaves same-shape; rank>=2 leaves contiguous) selects
the fused fast path; otherwise the original nested `nd::` expression runs as a
fallback, so fusion can never change results.

These are string-level assertions that the fused loop + guard + fallback were
emitted (and that non-fusable cases fall back); numeric byte-parity is proven by
the compile-and-compare harnesses (test_native_transpiler_harnesses /
metaclay_parity)."""

from __future__ import annotations

import unittest

from mpynode.native.compiler.py_to_cpp import (
    transpile_compute_block, transpile_function, scalar_t, array_t)


def _transpile(compute, env):
    writers = {"self.out": lambda val: ["OUT = %s;" % val.code]}
    res, _written, _helpers = transpile_compute_block(compute, dict(env), writers)
    return "\n".join(res.all_lines())


def _transpile_fn(src, arg_types):
    res = transpile_function(src, arg_types)
    return "\n".join(res.all_lines())


class TestFusionFires(unittest.TestCase):
    def test_rank2_arith_tree_fuses_with_guard_and_fallback(self):
        # t = a + b*c  (all rank-2 arrays) -> ONE fused scalar loop guarded on
        # contiguity, with the nested nd:: expression kept as a fallback.
        cpp = _transpile(
            "t = a + b * c\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 2),
             "c": array_t("double", 2)})
        self.assertIn("for (",           cpp)  # a scalar loop was emitted
        self.assertIn("is_contiguous()", cpp)  # runtime guard (rank>=2)
        self.assertIn("::alloc(",        cpp)  # fused output allocation
        self.assertIn("nd::add(",        cpp)  # nd:: fallback retained

    def test_rank1_leaf_uses_strided_read(self):
        # rank-1 leaves may be strided views (e.g. col of an (N,3)); the fused
        # loop must read them via offset + i*strides[0].
        cpp = _transpile(
            "t = a - b\nself.out = t\n",
            {"a": array_t("double", 1), "b": array_t("double", 1)})
        self.assertIn("for (",       cpp)
        self.assertIn(".strides[0]", cpp)  # strided rank-1 read
        self.assertIn("nd::sub(",    cpp)  # fallback retained


class TestFusionInc2(unittest.TestCase):
    def test_div_fuses(self):
        cpp = _transpile(
            "t = a / b\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 2)})
        self.assertIn("::alloc(",    cpp)
        self.assertIn("/",           cpp)
        self.assertIn("nd::divide(", cpp)          # fallback retained

    def test_maximum_fuses_with_nan_safe_elem(self):
        # The per-element form is nd::maximum_elem, NOT a bare `a > b ? a : b`.
        # np.maximum propagates NaN from either operand and the ternary does not
        # (it returns the non-NaN operand when the LEFT one is NaN), so spelling
        # it inline here would make this fast path disagree with the nd:: arm of
        # its own guard -- breaking this file's "fusion can never change results".
        # maximum_elem IS that ternary plus the isnan guard, and is the same
        # definition nd::maximum uses, so the two arms cannot drift.
        cpp = _transpile(
            "import numpy as np\nt = np.maximum(a, b)\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 2)})
        self.assertIn("::alloc(",          cpp)
        self.assertIn("nd::maximum_elem<", cpp)  # scalar max in the loop
        self.assertIn("nd::maximum(",      cpp)  # fallback retained

    def test_negate_fuses(self):
        cpp = _transpile(
            "t = -a + b\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 2)})
        self.assertIn("::alloc(",    cpp)
        self.assertIn("nd::add(",    cpp)  # fallback retained
        self.assertIn("nd::negate(", cpp)  # fallback retained

    def test_sqrt_ufunc_fuses(self):
        cpp = _transpile(
            "import numpy as np\nt = np.sqrt(a) + b\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 2)})
        self.assertIn("::alloc(",   cpp)
        self.assertIn("std::sqrt(", cpp)  # scalar ufunc in the loop
        self.assertIn("nd::sqrt(",  cpp)  # fallback retained


class TestFusionInc3Sinks(unittest.TestCase):
    def test_return_of_tree_fuses(self):
        cpp = _transpile_fn(
            "def f(a, b, c):\n    return a + b * c\n",
            {"a": array_t("double", 2), "b": array_t("double", 2),
             "c": array_t("double", 2)})
        self.assertIn("for (",    cpp)  # fused loop
        self.assertIn("::alloc(", cpp)
        self.assertIn("nd::add(", cpp)  # fallback retained
        self.assertIn("return ",  cpp)  # returns the temp

    def test_direct_output_write_of_tree_fuses(self):
        # self.out = <tree> with no intermediate local -> fuse into a temp, then
        # the output writer consumes the temp.
        cpp = _transpile(
            "self.out = a + b * c\n",
            {"a": array_t("double", 2), "b": array_t("double", 2),
             "c": array_t("double", 2)})
        self.assertIn("for (",    cpp)
        self.assertIn("::alloc(", cpp)
        self.assertIn("nd::add(", cpp)  # fallback retained
        self.assertIn("OUT = ",   cpp)  # writer still fires


class TestFusionAliasing(unittest.TestCase):
    def test_self_referential_assign_binds_leaf_by_value(self):
        # `a = a / d` -- the fused output IS an input leaf. Binding the leaf by
        # REFERENCE would alias the reallocated output (reads zeros). The leaf
        # must be captured BY VALUE (shares the old buffer via shared_ptr).
        cpp = _transpile(
            "d = a * 1.0\nt = a / d\na = a - t\nself.out = a\n",
            {"a": array_t("double", 1)})
        # no by-reference array bind may appear in a fused block
        self.assertNotIn("const nd::Array<double>& __L", cpp)
        self.assertIn("const nd::Array<double> __L0", cpp)   # by value


class TestFusionBoolScalarLeaf(unittest.TestCase):
    def test_bool_arith_scalar_leaf_not_lossily_hoisted(self):
        # (p>0)+(q>0) is dtype-LABELED bool but its VALUE can be 2 (bool+bool
        # promotes to int in C++), so hoisting it into `const bool __s0`
        # truncates 2 -> 1 and diverges from the int64 nd:: fallback.
        cpp = _transpile(
            "self.out = a + ((p > 0) + (q > 0))\n",
            {"a": array_t("int64", 1),
             "p": scalar_t("int64"), "q": scalar_t("int64")})
        self.assertNotIn("const bool", cpp)   # no lossy bool hoist


class TestFusionInc2Matmul(unittest.TestCase):
    def test_matmul_plus_rowvec_fuses_as_producer(self):
        # points[:, :3] @ M[:3, :3] + M[3, :3] must fuse into ONE loop: the
        # matmul becomes an inline acc-loop producer (NOT a materialized
        # `__L0 = nd::matmul(...)` leaf), the (3,) row vector a per-column
        # broadcast read, and the nd:: expression stays as the fallback.
        cpp = _transpile_fn(
            "def f(p, m):\n    return p[:, :3] @ m[:3, :3] + m[3, :3]\n",
            {"p": array_t("double", 2), "m": array_t("double", 2)})
        self.assertIn("__i / __N", cpp)              # row index (producer mode)
        self.assertIn("__i % __N", cpp)              # column index (producer mode)
        self.assertIn("__mm0",     cpp)              # matmul accumulator
        self.assertIn("__l <",     cpp)              # inline contraction loop
        self.assertNotIn("__L0 = nd::matmul(", cpp)  # NOT materialized as a leaf
        self.assertIn("nd::matmul(", cpp)            # fallback retained
        self.assertIn("nd::add(", cpp)               # fallback retained

    def test_rank2_plus_rowvec_broadcast_fuses(self):
        # (m,N) + (N,) -- a row broadcast with no matmul. The (N,) operand must
        # become a per-column read (indexed by __jj), not a flat same-shape leaf.
        cpp = _transpile(
            "t = a + c\nself.out = t\n",
            {"a": array_t("double", 2), "c": array_t("double", 1)})
        self.assertIn("__i % __N", cpp)  # column index for the broadcast
        self.assertIn("nd::add(", cpp)   # fallback retained

    def test_bare_matmul_does_not_producer_fuse(self):
        # A bare 2-D @ 2-D with no elementwise consumer stays on the Inc1 nd::
        # matmul fast path -- no producer loop (a lone matmul gains nothing from
        # a scalar loop and would lose Inc1's unrolled fast path).
        cpp = _transpile_fn(
            "def f(a, b):\n    return a @ b\n",
            {"a": array_t("double", 2), "b": array_t("double", 2)})
        self.assertNotIn("__i / __N", cpp)  # no producer loop
        self.assertNotIn("__mm0", cpp)
        self.assertIn("nd::matmul(", cpp)   # plain Inc1 path


class TestFusionGates(unittest.TestCase):
    def test_bool_result_does_not_fuse(self):
        # comparisons produce Array<bool> (bit-packed, no data()) -> must NOT
        # fuse in v1; stays on the nd:: path.
        cpp = _transpile(
            "t = a < b\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 2)})
        self.assertNotIn("::alloc(", cpp)  # no fused fast path
        self.assertIn("nd::cmp_lt(", cpp)  # plain nd:: path

    def test_unknown_rank_does_not_fuse(self):
        # rank None -> cannot size the loop -> fall back to nd::.
        cpp = _transpile(
            "t = a + b\nself.out = t\n",
            {"a": array_t("double", None), "b": array_t("double", None)})
        self.assertNotIn("::alloc(", cpp)
        self.assertIn("nd::add(", cpp)

    def test_trailing_newaxis_leaf_does_not_fuse(self):
        # `b[:, None]` lowers to nd::newaxis(view, 1), which writes a stride of
        # 0 at the LAST axis -- and nd::c_strides always leaves its last entry
        # at 1, so Array::is_contiguous() is false for EVERY shape (the empty
        # ones included). The guard term the fused block would add for that leaf
        # can therefore never hold, so the loop it guards is unreachable: emit
        # the plain nd:: expression (the arm that already runs) and nothing else.
        cpp = _transpile(
            "t = a * b[:, None]\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 1)})
        self.assertNotIn("is_contiguous()", cpp)  # no always-false guard
        self.assertNotIn("::alloc(", cpp)         # no unreachable loop
        self.assertIn("nd::newaxis(", cpp)        # the view itself is intact
        self.assertIn("nd::mul(", cpp)            # plain nd:: path

    def test_leading_newaxis_leaf_still_fuses(self):
        # Narrowness fence for the gate above: `b[None, :]` puts the 0 stride on
        # a NON-last axis, where c_strides CAN also be 0 (a zero-length dim), so
        # that guard is not provably false and the block is NOT dead code. It
        # must keep fusing -- the gate suppresses unreachable blocks only, it is
        # not a blanket "any newaxis leaf disables fusion".
        cpp = _transpile(
            "t = a * b[None, :]\nself.out = t\n",
            {"a": array_t("double", 2), "b": array_t("double", 1)})
        self.assertIn("is_contiguous()", cpp)
        self.assertIn("::alloc(",        cpp)
        self.assertIn("nd::mul(",        cpp)             # fallback retained


if __name__ == "__main__":
    unittest.main()
