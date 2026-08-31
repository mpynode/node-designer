"""Maya-FREE: the deterministic RAW-POINTER scalar element-access recipe in the
numpy->C++ transpiler.

A fully-integer-indexed scalar read ``a[i, j, k]`` used to lower to
``nd::slice(a, {nd::Sl::at(i), ...}).item()`` -- a fresh view object (vector +
shared_ptr refcount) allocated PER access. In an O(N^3) grid loop (dual marching
cubes) that is hundreds of millions of tiny heap allocations and is the single
biggest, most general cost in every generated node (NOT the arithmetic).

The recipe lowers such accesses to ``nd::atN(a, i, j, k)`` (read) / ``nd::atN_ref
(a, i, j, k) = v`` (write) -- raw buffer indexing that honors the array's real
offset+strides, evaluates the base once, and allocates nothing. It is
bit-identical to slice(...).item() (same offset+strides math). It applies ONLY to
a FULL all-integer index (rank drops to a scalar), rank 1-4, and NOT to ``bool``
arrays (std::vector<bool> is bit-packed -- keep the nd:: path there).

A scalar read only reaches the raw form when consumed in a SCALAR context -- an
integer index, or a ``float()`` / ``int()`` cast -- exactly the consumers the DMC
compute uses (``float(scalar_field[i+ox, j+oy, k+oz])``, ``int(cfg_grid[i,j,k])``,
``grid[i,j,k] = value``). These are string-level assertions (the recipe fired);
numeric bit-parity is proven by the compile-and-compare harnesses (py_to_cpp_test
/ nd_lower_test / sdf_dmc_parity / metaballs_parity)."""

from __future__ import annotations

import unittest

from mpynode.native.compiler.py_to_cpp import (
    transpile_compute_block, scalar_t, array_t)


def _transpile(compute, env):
    writers = {"self.out": lambda val: ["OUT = %s;" % val.code]}
    res, _written, _helpers = transpile_compute_block(compute, dict(env), writers)
    return "\n".join(res.all_lines())


class TestRawScalarRead(unittest.TestCase):
    def test_full_integer_index_read_uses_raw_access(self):
        # float(a[i, 0, 0]) forces the read into a scalar context.
        compute = (
            "acc = 0.0\n"
            "for i in range(n):\n"
            "    acc = acc + float(a[i, 0, 0])\n"
            "self.out = acc\n"
        )
        env = {"n": scalar_t("int64"), "a": array_t("double", 3)}
        cpp = _transpile(compute, env)
        self.assertIn("nd::at3(", cpp)              # raw access fired
        self.assertNotIn(".item()", cpp)            # no per-element view alloc
        self.assertNotIn("nd::slice(", cpp)

    def test_two_d_read_uses_at2(self):
        compute = (
            "acc = 0.0\n"
            "for i in range(n):\n"
            "    acc = acc + float(a[i, 0])\n"
            "self.out = acc\n"
        )
        env = {"n": scalar_t("int64"), "a": array_t("double", 2)}
        cpp = _transpile(compute, env)
        self.assertIn("nd::at2(", cpp)
        self.assertNotIn(".item()", cpp)

    def test_int_cast_read_uses_raw(self):
        # int(a[i, 0]) -- the dominant DMC read (config/offset/edge tables) --
        # takes the raw path too.
        compute = (
            "acc = 0\n"
            "for i in range(n):\n"
            "    acc = acc + int(a[i, 0])\n"
            "self.out = acc\n"
        )
        env = {"n": scalar_t("int64"), "a": array_t("int64", 2)}
        cpp = _transpile(compute, env)
        self.assertIn("nd::at2(", cpp)
        self.assertNotIn(".item()", cpp)

    def test_int_index_used_as_index_uses_raw(self):
        # a scalar read consumed as an INTEGER INDEX (a[b[i,0], 0]) also takes
        # the raw path, on both the inner index read and the outer read.
        compute = (
            "acc = 0.0\n"
            "for i in range(n):\n"
            "    acc = acc + float(a[b[i, 0], 0])\n"
            "self.out = acc\n"
        )
        env = {"n": scalar_t("int64"),
               "b": array_t("int64", 2), "a": array_t("double", 2)}
        cpp = _transpile(compute, env)
        self.assertIn("nd::at2(", cpp)
        self.assertNotIn(".item()", cpp)


class TestRawScalarWrite(unittest.TestCase):
    def test_full_integer_index_write_uses_ref(self):
        compute = (
            "for i in range(n):\n"
            "    b[i, 0] = a[i, 0]\n"
            "self.out = b[0, 0]\n"
        )
        env = {"n": scalar_t("int64"),
               "a": array_t("double", 2), "b": array_t("double", 2)}
        cpp = _transpile(compute, env)
        self.assertIn("nd::at2_ref(", cpp)          # raw ref-write fired
        self.assertNotIn("nd::assign(", cpp)


class TestRawAccessGates(unittest.TestCase):
    def test_bool_array_keeps_nd_slice(self):
        # std::vector<bool> is bit-packed -> operator[] returns a proxy, not a
        # reference; the raw recipe must NOT touch bool arrays.
        compute = (
            "acc = 0\n"
            "for i in range(n):\n"
            "    acc = acc + int(flags[i, 0])\n"
            "self.out = acc\n"
        )
        env = {"n": scalar_t("int64"), "flags": array_t("bool", 2)}
        cpp = _transpile(compute, env)
        self.assertNotIn("nd::at2(", cpp)           # NOT the raw path for bool
        self.assertIn("nd::slice(", cpp)            # still the nd:: view path

    def test_partial_index_stays_a_view(self):
        # a[i] on a 2-D array is a rank-1 VIEW (not a scalar) -> must stay a
        # slice, never a raw scalar access.
        compute = (
            "row = a[i]\n"
            "self.out = row[0]\n"
        )
        env = {"i": scalar_t("int64"), "a": array_t("double", 2)}
        cpp = _transpile(compute, env)
        self.assertIn("nd::slice(", cpp)            # the partial view survives


if __name__ == "__main__":
    unittest.main()
