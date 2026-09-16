"""Maya-FREE: Item 6 -- read-only nd::Array helper params passed by const&.

A helper param whose nd::Array is only READ in the body is emitted as
``const nd::Array<T>&`` instead of by value (``nd::Array<T>``), avoiding a
per-call copy of the shape/stride vectors + a shared_ptr refcount bump. This is
a pure calling-convention change: the values read are identical, so the compiled
output is byte-for-byte unchanged. A param that is WRITTEN (reassigned,
element-stored, or used as a loop target) MUST stay BY VALUE -- a const& would be
a compile error on reassignment / silent aliasing on an in-place store. Return
types are never const& (a returned Array is a value)."""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c


def _emit(helper_src, compute, env):
    _res, _w, helper_lines = p2c.transpile_compute_block(
        compute, dict(env), {"self.r": lambda v: ["out = %s;" % v.code]},
        helper_source=helper_src)
    return "\n".join(helper_lines)


def _A(dt="double", r=1):
    return p2c.CppType("array", dt, r)


def _S(dt="double"):
    return p2c.CppType("scalar", dt, 0)


class TestConstRefReadOnlyParams(unittest.TestCase):
    def test_nonrecursive_readonly_array_param_is_const_ref(self):
        # kv is only READ (kv + 1.0) -> const nd::Array<double>& param; the array
        # RETURN must stay by value (nd::Array<double>, never const&).
        text = _emit("def _f(kv):\n    return kv + 1.0\n",
                     "self.r = _f(self.kv)\n", {"self.kv": _A()})
        self.assertIn("const nd::Array<double>& kv", text)
        self.assertNotIn("nd::Array<double> kv", text)  # not by value
        self.assertIn("-> nd::Array<double>", text)     # return by value
        self.assertNotIn("-> const nd::Array<double>&", text)

    def test_recursive_readonly_array_param_is_const_ref_in_sig_and_params(self):
        # Recursive scalar helper reading a read-only array param -> the
        # std::function carries const nd::Array<double>& in BOTH the type list
        # and the lambda param (float() coerces the at1 read to a scalar return).
        helper = ("def _sum(k, kv):\n"
                  "    if k < 0:\n"
                  "        return 0.0\n"
                  "    return float(kv[k]) + _sum(k - 1, kv)\n")
        text = _emit(helper, "self.r = _sum(self.k, self.kv)\n",
                     {"self.k": _S("int64"), "self.kv": _A()})
        self.assertIn("std::function<", text)
        self.assertIn("const nd::Array<double>&)", text)    # sigtypes tail
        self.assertIn("const nd::Array<double>& kv", text)  # lambda param


class TestWrittenParamStaysByValue(unittest.TestCase):
    def test_reassigned_array_param_stays_by_value(self):
        # kv is REASSIGNED -> written -> must stay by value; the read-only
        # analysis must exclude it (const& would not compile on reassignment).
        text = _emit("def _g(kv):\n    kv = kv + 1.0\n    return kv + 2.0\n",
                     "self.r = _g(self.kv)\n", {"self.kv": _A()})
        self.assertIn("nd::Array<double> kv", text)             # by value
        self.assertNotIn("const nd::Array<double>& kv", text)


if __name__ == "__main__":
    unittest.main()
