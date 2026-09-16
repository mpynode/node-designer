"""Maya-FREE: Item 3 -- specialize a compile-time-literal np.einsum into a
per-subscript scalar contraction loop, byte-identical to nd::einsum.

nd::einsum (nd_runtime.h) re-parses the subscript string and drives generic
odometers via std::vector on EVERY call. For the corpus's fixed subscripts we
instead emit a specialized nest: output labels loop outermost in C-contiguous
order, sum labels (first-seen order) innermost; per output element `acc=(T)0`,
then over the sum odometer `prodv=(T)1`, `prodv*=at{rank}(op_t, ...)` in operand
order, `acc+=prodv`; the result is stored C-contiguous. This mirrors nd::einsum's
accumulation order EXACTLY (same loop nesting, same operand order, same real
offset+stride reads via at1..at4), so every produced bit is unchanged.

Anything the specialized path does not model -- a repeated label within a term
(diagonal), a term of rank > 4, or an empty output-label set -- FALLS BACK to the
proven nd::einsum runtime call, so those stay byte-exact too.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c


def _emit(compute, env):
    res, _w, _h = p2c.transpile_compute_block(
        compute, dict(env), {"self.r": lambda v: ["out = %s;" % v.code]})
    return "\n".join(res.all_lines())


def _A(dt="double", r=1):
    return p2c.CppType("array", dt, r)


class TestEinsumSpecialized(unittest.TestCase):
    def test_matmul_batch_nij_njk_specialized(self):
        # "nij,njk->nik": out labels n,i,k (C-order loops), sum label j inner.
        text = _emit('self.r = np.einsum("nij,njk->nik", self.a, self.b)\n',
                     {"self.a": _A(r=3), "self.b": _A(r=3)})
        self.assertNotIn("nd::einsum(", text)        # specialized, not runtime
        self.assertEqual(text.count("nd::at3("), 2)  # one read per rank-3 operand
        self.assertIn("_acc += ", text)              # per-output accumulator
        self.assertIn("_prod *= ", text)             # per-term product

    def test_matvec_batch_nij_nj_specialized(self):
        # "nij,nj->ni": op1 is rank-2 -> at2 reads; op0 rank-3 -> at3.
        text = _emit('self.r = np.einsum("nij,nj->ni", self.a, self.b)\n',
                     {"self.a": _A(r=3), "self.b": _A(r=2)})
        self.assertNotIn("nd::einsum(", text)
        self.assertIn("nd::at3(", text)
        self.assertIn("nd::at2(", text)

    def test_three_operand_nij_njk_nkl_specialized(self):
        # "nij,njk,nkl->nil": 3 operands, sum labels j,k (j outer, k inner).
        text = _emit(
            'self.r = np.einsum("nij,njk,nkl->nil", self.a, self.b, self.c)\n',
            {"self.a": _A(r=3), "self.b": _A(r=3), "self.c": _A(r=3)})
        self.assertNotIn("nd::einsum(", text)
        self.assertEqual(text.count("nd::at3("), 3)    # one read per operand

    def test_diagonal_falls_back_to_runtime(self):
        # "ii->i" repeats a label within a term (diagonal) -> not modeled by the
        # specialized nest -> the proven nd::einsum runtime call is preserved.
        text = _emit('self.r = np.einsum("ii->i", self.a)\n', {"self.a": _A(r=2)})
        self.assertIn("nd::einsum(", text)


if __name__ == "__main__":
    unittest.main()
