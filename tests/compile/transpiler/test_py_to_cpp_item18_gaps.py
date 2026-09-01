"""Maya-FREE: the four measured transpiler gaps closed under ITEM 18.

  * a guard ``raise`` -> the runtime's own throw;
  * ``is None`` / ``is not None`` folded at compile time;
  * ``np.meshgrid`` with ``indexing='ij'`` and with three inputs;
  * ``np.unique(a, return_index=True)``.

This module gates the LOWERING SHAPE and, more importantly, the rejects -- the
forms that must keep routing to the porter rather than being guessed at. The
byte-parity evidence (compile the C++, run it, compare against numpy) lives in
``tests/compile/native/py_to_cpp_test.py`` as the ``gap_raise_*`` / ``gap_none_*`` /
``gap_meshgrid_*`` / ``gap_unique_return_index_*`` fixtures, which is the only
place that has a compiler.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c
from mpynode.native.compiler.errors import UnsupportedSpec


def _fn(src, **types):
    return p2c.transpile_function(src, types)


def _emit_fn(src, **types):
    res = _fn(src, **types)
    return "\n".join(list(res.decl_lines) + list(res.body_lines))


class TestRaise(unittest.TestCase):
    def test_guard_raise_becomes_the_runtime_throw(self):
        out = _emit_fn("def f(a):\n"
                       "    if a.shape[0] < 1:\n"
                       "        raise ValueError('empty input')\n"
                       "    return a\n",
                       a=p2c.array_t("double", 1))
        self.assertIn('throw std::runtime_error("ValueError: empty input");',
                      out)

    def test_exception_type_is_kept_in_the_message(self):
        """The compiled node has no exception TYPE, so the only place the type
        can survive is the text -- losing it would erase the diagnostic."""
        out = _emit_fn("def f(a):\n    raise RuntimeError('bad')\n    return a\n",
                       a=p2c.array_t("double", 1))
        self.assertIn("RuntimeError: bad", out)

    def test_argument_less_exception_lowers_to_its_name(self):
        out = _emit_fn("def f(a):\n    raise ValueError\n    return a\n",
                       a=p2c.array_t("double", 1))
        self.assertIn('throw std::runtime_error("ValueError");', out)

    def test_bare_reraise_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n    raise\n", a=p2c.array_t("double", 1))
        self.assertIn("re-raise", str(cm.exception))

    def test_computed_message_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n    raise ValueError('n=%d' % 3)\n",
                a=p2c.array_t("double", 1))
        self.assertIn("literal string", str(cm.exception))

    def test_raise_from_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n    raise ValueError('x') from None\n",
                a=p2c.array_t("double", 1))
        self.assertIn("from", str(cm.exception))

    def test_raising_a_bound_value_rejects(self):
        """`raise a` with `a` an input is not the guard idiom -- an exception
        class is never a lowered value."""
        with self.assertRaises(UnsupportedSpec):
            _fn("def f(a):\n    raise a\n", a=p2c.array_t("double", 1))


class TestNoneIdentity(unittest.TestCase):
    def test_is_none_on_a_none_local_folds_true(self):
        out = _emit_fn("def f(a):\n"
                       "    src = None\n"
                       "    if src is None:\n"
                       "        return a\n"
                       "    return a * 2.0\n",
                       a=p2c.array_t("double", 1))
        self.assertIn("if (true) {", out)

    def test_is_none_on_a_value_folds_false(self):
        out = _emit_fn("def f(a):\n"
                       "    if a is None:\n"
                       "        return a\n"
                       "    return a * 2.0\n",
                       a=p2c.array_t("double", 1))
        self.assertIn("if (false) {", out)

    def test_is_not_none_is_the_complement(self):
        out = _emit_fn("def f(a):\n"
                       "    if a is not None:\n"
                       "        return a\n"
                       "    return a * 2.0\n",
                       a=p2c.array_t("double", 1))
        self.assertIn("if (true) {", out)

    def test_a_none_local_declares_no_cpp_variable(self):
        out = _emit_fn("def f(a):\n"
                       "    src = None\n"
                       "    return a\n",
                       a=p2c.array_t("double", 1))
        self.assertNotIn("src", out)

    def test_reading_a_none_local_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n    x = None\n    return a + x\n",
                a=p2c.array_t("double", 1))
        self.assertIn("no compiled value", str(cm.exception))

    def test_rebinding_none_to_a_value_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n    x = None\n    x = a\n    return x\n",
                a=p2c.array_t("double", 1))
        self.assertIn("bound to None", str(cm.exception))

    def test_rebinding_a_value_to_none_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n    x = a * 2.0\n    x = None\n    return a\n",
                a=p2c.array_t("double", 1))
        self.assertIn("reassigned to None", str(cm.exception))

    def test_equality_against_none_is_not_folded(self):
        """`== None` is an equality, not an identity test; folding it would be
        inventing a semantic numpy never gave us."""
        with self.assertRaises(UnsupportedSpec):
            _fn("def f(a):\n    x = None\n    if x == None:\n"
                "        return a\n    return a\n",
                a=p2c.array_t("double", 1))

    def test_optional_input_getattr_default_binds_none(self):
        """`getattr(self, '<absent>', None)` is the optional-input idiom; the
        default is the branch that is selected, so the local is None."""
        env = {"self.a": p2c.array_t("double", 1)}
        res, _w, _h = p2c.transpile_compute_block(
            "src = getattr(self, 'missing', None)\n"
            "if src is None:\n"
            "    self.r = self.a\n"
            "else:\n"
            "    self.r = self.a * 2.0\n",
            env, {"self.r": lambda v: ["out = %s;" % v.code]})
        self.assertIn("if (true) {", "\n".join(res.all_lines()))

    def test_declared_input_getattr_default_is_dead(self):
        env = {"self.a": p2c.array_t("double", 1)}
        res, _w, _h = p2c.transpile_compute_block(
            "src = getattr(self, 'a', None)\n"
            "if src is None:\n"
            "    self.r = self.a\n"
            "else:\n"
            "    self.r = self.a * 2.0\n",
            env, {"self.r": lambda v: ["out = %s;" % v.code]})
        self.assertIn("if (false) {", "\n".join(res.all_lines()))


class TestMeshgrid(unittest.TestCase):
    _XY = dict(x=p2c.array_t("double", 1), y=p2c.array_t("double", 1))
    _XYZ = dict(x=p2c.array_t("double", 1), y=p2c.array_t("double", 1),
                z=p2c.array_t("double", 1))

    def test_ij_swaps_both_the_arguments_and_the_grid(self):
        """'ij' is the transpose of 'xy', which for two inputs is exactly
        meshgrid_y(y, x) / meshgrid_x(y, x) -- no new runtime."""
        out = _emit_fn("def f(x, y):\n"
                       "    X, Y = np.meshgrid(x, y, indexing='ij')\n"
                       "    return X + Y\n", **self._XY)
        self.assertIn("nd::meshgrid_y(", out)
        self.assertIn("nd::meshgrid_x(", out)
        self.assertLess(out.index("nd::meshgrid_y("), out.index("nd::meshgrid_x("))

    def test_xy_is_unchanged(self):
        out = _emit_fn("def f(x, y):\n"
                       "    X, Y = np.meshgrid(x, y)\n"
                       "    return X + Y\n", **self._XY)
        self.assertLess(out.index("nd::meshgrid_x("), out.index("nd::meshgrid_y("))

    def test_three_inputs_ij_uses_axes_0_1_2(self):
        out = _emit_fn("def f(x, y, z):\n"
                       "    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')\n"
                       "    return X + Y + Z\n", **self._XYZ)
        self.assertEqual(3, out.count("nd::meshgrid3("))
        axes = [ln.split("nd::meshgrid3(")[1].split(",")[1].strip()
                for ln in out.splitlines() if "nd::meshgrid3(" in ln]
        self.assertEqual(["0", "1", "2"], axes)

    def test_three_inputs_xy_swaps_only_the_first_two_axes(self):
        out = _emit_fn("def f(x, y, z):\n"
                       "    X, Y, Z = np.meshgrid(x, y, z)\n"
                       "    return X + Y + Z\n", **self._XYZ)
        axes = [ln.split("nd::meshgrid3(")[1].split(",")[1].strip()
                for ln in out.splitlines() if "nd::meshgrid3(" in ln]
        self.assertEqual(["1", "0", "2"], axes)

    def test_four_inputs_reject(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(x, y, z, w):\n"
                "    A, B, C, D = np.meshgrid(x, y, z, w)\n"
                "    return A\n",
                w=p2c.array_t("double", 1), **self._XYZ)
        self.assertIn("2- and 3-input", str(cm.exception))

    def test_unpack_arity_must_match_the_input_count(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(x, y, z):\n"
                "    X, Y = np.meshgrid(x, y, z, indexing='ij')\n"
                "    return X\n", **self._XYZ)
        self.assertIn("one grid per input", str(cm.exception))

    def test_non_literal_indexing_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(x, y):\n    m = 'ij'\n"
                "    X, Y = np.meshgrid(x, y, indexing=m)\n"
                "    return X\n", **self._XY)
        self.assertIn("literal", str(cm.exception))

    def test_sparse_still_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(x, y):\n"
                "    X, Y = np.meshgrid(x, y, sparse=True)\n"
                "    return X\n", **self._XY)
        self.assertIn("sparse", str(cm.exception))


class TestUniqueReturnIndex(unittest.TestCase):
    _A = dict(a=p2c.array_t("double", 1))

    def test_return_index_lowers_to_one_stable_call(self):
        out = _emit_fn("def f(a):\n"
                       "    u, i = np.unique(a, return_index=True)\n"
                       "    return u\n", **self._A)
        self.assertEqual(1, out.count("nd::unique_index("))
        self.assertIn(".first;", out)
        self.assertIn(".second;", out)

    def test_the_index_array_is_int64(self):
        res = _fn("def f(a):\n"
                  "    u, i = np.unique(a, return_index=True)\n"
                  "    return i\n", **self._A)
        decls = "\n".join(res.decl_lines)
        self.assertIn("nd::Array<int64_t>", decls)

    def test_plain_unique_is_untouched(self):
        out = _emit_fn("def f(a):\n    return np.unique(a)\n", **self._A)
        self.assertIn("nd::unique(", out)
        self.assertNotIn("nd::unique_index(", out)

    def test_return_counts_still_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n"
                "    u, c = np.unique(a, return_counts=True)\n"
                "    return u\n", **self._A)
        self.assertIn("not lowered", str(cm.exception))

    def test_return_inverse_still_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n"
                "    u, v = np.unique(a, return_inverse=True)\n"
                "    return u\n", **self._A)
        self.assertIn("not lowered", str(cm.exception))

    def test_return_index_false_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n"
                "    u, i = np.unique(a, return_index=False)\n"
                "    return u\n", **self._A)
        self.assertIn("return_index=True", str(cm.exception))

    def test_three_way_unpack_rejects(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _fn("def f(a):\n"
                "    u, i, c = np.unique(a, return_index=True)\n"
                "    return u\n", **self._A)
        self.assertIn("values, indices", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
