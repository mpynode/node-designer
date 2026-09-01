"""Maya-FREE: the ndarray METHOD surface, and the absence of spelling gaps.

`arr.mean()` and `np.mean(arr)` are one operation written two ways. Wiring them
in two separate if-chains is how the gaps got in -- np.take and np.cumsum were
added free-only, .copy() method-only -- so both spellings now resolve through
ONE table (py_to_cpp._ARRAY_OPS) and the tests below pin that:

  * every "both" operation emits BYTE-IDENTICAL C++ either way. Not "both
    lowered" -- identical, which is the only claim that rules out drift;
  * every public ndarray method is accounted for, as an operation, an in-place
    statement, or an explicit reject WITH a reason. A method numpy has and this
    table does not is a failure here, not a surprise at compile time;
  * the measured numpy defaults are pinned, because a kernel that is right about
    the maths and wrong about the default axis is still a wrong answer.

Values are verified separately, against numpy itself, by
tests/compile/native/py_to_cpp_test.py -- a clean lowering proves nothing about results.
"""

from __future__ import annotations

import unittest

import numpy as np

from mpynode.native.compiler import py_to_cpp as p2c
from mpynode.native.compiler.errors import UnsupportedSpec


_ENV = {
    "self.a": p2c.array_t("double", 2),      # a matrix
    "self.v": p2c.array_t("double", 1),      # a vector
    "self.i": p2c.array_t("int64", 1),       # indices
    "self.m": p2c.array_t("bool", 1),        # a mask
}


def _emit(compute, env=None):
    res, _w, _h = p2c.transpile_compute_block(
        compute, dict(env or _ENV),
        {"self.r": lambda v: ["out = %s;" % v.code]})
    return "\n".join(res.all_lines())


def _expr(e):
    return _emit("self.r = %s\n" % e)


def _rank_of(expr, rank=1, dtype="double"):
    """The static rank the lattice assigns to `expr` (None when not known)."""
    res = p2c.transpile_function(
        "def f(a):\n    return %s\n" % expr, {"a": p2c.array_t(dtype, rank)})
    return res.returns[0].rank


# (op, method spelling, free spelling) for every operation numpy provides BOTH
# ways. The pair must emit identical C++.
_EQUIVALENT = [
    ("all",       "self.v.all()",                "np.all(self.v)"),
    ("any",       "self.v.any()",                "np.any(self.v)"),
    ("argmax",    "self.v.argmax()",             "np.argmax(self.v)"),
    ("argmin",    "self.v.argmin()",             "np.argmin(self.v)"),
    ("argsort",   "self.v.argsort()",            "np.argsort(self.v)"),
    ("choose",    "self.i.choose((self.v, self.v))",
                  "np.choose(self.i, (self.v, self.v))"),
    ("clip",      "self.v.clip(0.0, 1.0)",       "np.clip(self.v, 0.0, 1.0)"),
    ("conj",      "self.v.conj()",               "np.conj(self.v)"),
    ("conjugate", "self.v.conjugate()",          "np.conjugate(self.v)"),
    ("copy",      "self.v.copy()",               "np.copy(self.v)"),
    ("cumprod",   "self.v.cumprod()",            "np.cumprod(self.v)"),
    ("cumsum",    "self.v.cumsum()",             "np.cumsum(self.v)"),
    ("diagonal",  "self.a.diagonal()",           "np.diagonal(self.a)"),
    ("dot",       "self.v.dot(self.v)",          "np.dot(self.v, self.v)"),
    ("max",       "self.v.max()",                "np.max(self.v)"),
    ("mean",      "self.v.mean()",               "np.mean(self.v)"),
    ("min",       "self.v.min()",                "np.min(self.v)"),
    ("prod",      "self.v.prod()",               "np.prod(self.v)"),
    ("ptp",       "self.v.ptp()",                "np.ptp(self.v)"),
    ("ravel",     "self.a.ravel()",              "np.ravel(self.a)"),
    ("repeat",    "self.v.repeat(2)",            "np.repeat(self.v, 2)"),
    ("reshape",   "self.v.reshape((3, 1))",      "np.reshape(self.v, (3, 1))"),
    ("round",     "self.v.round(2)",             "np.round(self.v, 2)"),
    ("searchsorted", "self.v.searchsorted(self.v)",
                     "np.searchsorted(self.v, self.v)"),
    ("squeeze",   "self.a.squeeze()",            "np.squeeze(self.a)"),
    ("std",       "self.v.std()",                "np.std(self.v)"),
    ("sum",       "self.v.sum()",                "np.sum(self.v)"),
    ("swapaxes",  "self.a.swapaxes(0, 1)",       "np.swapaxes(self.a, 0, 1)"),
    ("take",      "self.v.take(self.i)",         "np.take(self.v, self.i)"),
    ("trace",     "self.a.trace()",              "np.trace(self.a)"),
    ("transpose", "self.a.transpose()",          "np.transpose(self.a)"),
    ("var",       "self.v.var()",                "np.var(self.v)"),
    # np.compress leads with the MASK, a.compress with the array -- different
    # argument order, and still required to reach the same lowering.
    ("compress",  "self.v.compress(self.m)",     "np.compress(self.m, self.v)"),
]


class TestNoSpellingGaps(unittest.TestCase):
    def test_every_pair_emits_identical_cpp(self):
        for name, m, f in _EQUIVALENT:
            with self.subTest(op=name):
                self.assertEqual(
                    _expr(m), _expr(f),
                    "%s: the method and free spellings lowered differently\n"
                    "  %s\n->%s\n\n  %s\n->%s"
                    % (name, m, _expr(m), f, _expr(f)))

    def test_keyword_arguments_reach_both_spellings(self):
        for m, f in [("self.a.sum(axis=1)", "np.sum(self.a, axis=1)"),
                     ("self.a.mean(axis=0, keepdims=True)",
                      "np.mean(self.a, axis=0, keepdims=True)"),
                     ("self.v.std(ddof=1)", "np.std(self.v, ddof=1)"),
                     ("self.a.cumsum(axis=1)", "np.cumsum(self.a, axis=1)"),
                     ("self.a.argmax(axis=0)", "np.argmax(self.a, axis=0)")]:
            with self.subTest(pair=m):
                self.assertEqual(_expr(m), _expr(f))

    def test_amax_amin_are_the_same_lowering_as_max_min(self):
        self.assertEqual(_expr("np.max(self.v)"), _expr("np.amax(self.v)"))
        self.assertEqual(_expr("np.min(self.v)"), _expr("np.amin(self.v)"))

    def test_flatten_and_ravel_share_one_lowering(self):
        self.assertEqual(_expr("self.a.ravel()"), _expr("self.a.flatten()"))

    def test_aliases_reach_the_method_surface_too(self):
        """Origin resolution and the method table compose: an aliased import
        still finds the same lowering."""
        base = _expr("np.prod(self.v)")
        for init, call in [("import numpy as onp\n", "onp.prod(self.v)"),
                           ("from numpy import prod\n", "prod(self.v)"),
                           ("from numpy import prod as P\n", "P(self.v)"),
                           ("from numpy import *\n", "prod(self.v)")]:
            with self.subTest(spelling=call):
                res, _w, _h = p2c.transpile_compute_block(
                    "self.r = %s\n" % call, dict(_ENV),
                    {"self.r": lambda v: ["out = %s;" % v.code]}, init)
                self.assertEqual(base, "\n".join(res.all_lines()))


class TestSurfaceIsAccountedFor(unittest.TestCase):
    """Zero exceptions: every public ndarray method is covered by one of the
    three tables. This is the guard that turns a future gap into a test failure
    instead of a surprise. (It reads numpy at runtime, so a numpy upgrade that
    adds a method fails HERE, which is the intent.)"""

    def test_no_public_ndarray_method_is_unaccounted_for(self):
        covered = (set(p2c._ARRAY_OPS)
                   | set(p2c._ARRAY_STMT_OPS)
                   | set(p2c._ARRAY_OP_REJECTS)
                   | {n for n, _s in p2c._ARRAY_OPS_BY_SPELLING})
        public = {n for n in dir(np.ndarray)
                  if not n.startswith("_") and callable(getattr(np.ndarray, n))}
        self.assertEqual(set(), public - covered,
                         "ndarray methods with no table entry at all")

    def test_every_reject_carries_a_reason(self):
        for name, reason in p2c._ARRAY_OP_REJECTS.items():
            with self.subTest(op=name):
                self.assertTrue(len(reason) > 30,
                                "%s: a reject needs an argument, not a label"
                                % name)

    def test_rejects_say_why_in_both_spellings(self):
        for name in ("partition", "view", "tolist", "tobytes"):
            for src in ("self.r = self.v.%s()\n" % name,
                        "self.r = np.%s(self.v)\n" % name):
                with self.subTest(src=src):
                    with self.assertRaises(UnsupportedSpec) as cm:
                        _emit(src)
                    self.assertIn(p2c._ARRAY_OP_REJECTS[name][:24], str(cm.exception))

    def test_a_method_only_name_says_so_when_spelled_free(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _emit("self.r = np.flatten(self.a)\n")
        self.assertIn("a.flatten(...)", str(cm.exception))

    def test_an_inplace_method_used_as_a_value_says_so(self):
        with self.assertRaises(UnsupportedSpec) as cm:
            _emit("self.r = self.v.sort()\n")
        self.assertIn("returns None", str(cm.exception))


class TestMeasuredDefaultsArePinned(unittest.TestCase):
    """The defaults differ between operations that look alike -- sort defaults
    to the LAST axis, cumsum flattens. Each was measured against numpy."""

    def test_sort_defaults_to_the_last_axis_not_flatten(self):
        self.assertIn("-1, false)", _expr("np.sort(self.a)"))

    def test_sort_axis_none_is_the_opt_in_flatten(self):
        self.assertIn("true", _expr("np.sort(self.a, axis=None)"))

    def test_cumsum_defaults_to_flatten(self):
        self.assertIn("true", _expr("np.cumsum(self.a)"))

    def test_argmax_defaults_to_flatten(self):
        out = _expr("np.argmax(self.a)")
        self.assertIn("nd::argmax(", out)
        self.assertIn("{}", out)          # no axis -> reduce over all of them

    def test_argmax_rejects_a_tuple_of_axes(self):
        with self.assertRaises(UnsupportedSpec):
            _emit("self.r = np.argmax(self.a, axis=(0, 1))\n")

    def test_var_ddof_defaults_to_zero(self):
        self.assertTrue(_expr("np.var(self.v)").rstrip().endswith("0);"),
                        _expr("np.var(self.v)"))

    def test_ddof_must_be_a_keyword(self):
        # numpy's positional order is (axis, dtype, out, ddof), so a second
        # positional argument is `dtype`, not ddof -- reading it as ddof would
        # be a silent wrong answer.
        with self.assertRaises(UnsupportedSpec) as cm:
            _emit("self.r = np.std(self.v, 0, 1)\n")
        self.assertIn("ddof", str(cm.exception))

    def test_std_maps_to_stddev_not_std(self):
        # nd::std would shadow the std:: namespace inside namespace nd.
        self.assertIn("nd::stddev(", _expr("np.std(self.v)"))

    def test_repeat_without_axis_flattens_to_rank_1(self):
        out = _expr("self.v.repeat(2)")
        self.assertIn("nd::repeat(", out)
        self.assertEqual(1, _rank_of("a.repeat(2)"))

    def test_transpose_normalises_a_negative_axis(self):
        # nd::transpose indexes axes[i] directly, so -1 would read out of
        # bounds. `-1` is UnaryOp(USub, Constant(1)), NOT Constant(-1), so an
        # isinstance(Constant) test misses every negative literal.
        self.assertIn("{1, 0}", _expr("self.a.transpose(-1, -2)"))

    def test_squeeze_without_an_axis_has_no_static_rank(self):
        # Which axes vanish depends on the RUNTIME shape, so there is no static
        # rank to report; naming an axis restores one.
        self.assertIsNone(_rank_of("a.squeeze()", rank=3))
        self.assertEqual(2, _rank_of("a.squeeze(0)", rank=3))


class TestStatementMethods(unittest.TestCase):
    def test_sort_in_place_uses_the_in_place_kernel(self):
        out = _emit("b = self.a.copy()\nb.sort()\nself.r = b\n")
        self.assertIn("nd::sort_inplace(", out)

    def test_fill_and_put_and_itemset_mutate_through_the_buffer(self):
        out = _emit("b = self.v.copy()\n"
                    "b.fill(1.0)\n"
                    "b.put(self.i, self.v)\n"
                    "b.itemset(0, 2.0)\n"
                    "self.r = b\n")
        self.assertIn("nd::fill_inplace(", out)
        self.assertEqual(2, out.count("nd::put_inplace("))

    def test_np_put_is_the_same_lowering_as_the_method(self):
        m = _emit("b = self.v.copy()\nb.put(self.i, self.v)\nself.r = b\n")
        f = _emit("b = self.v.copy()\nnp.put(b, self.i, self.v)\nself.r = b\n")
        self.assertEqual(m, f)

    def test_setflags_is_a_no_op_not_a_reject(self):
        out = _emit("b = self.v.copy()\nb.setflags(write=False)\nself.r = b\n")
        self.assertNotIn("setflags", out)

    def test_resize_method_zero_fills_free_function_repeats(self):
        m = _emit("b = self.v.copy()\nb.resize(6)\nself.r = b\n")
        self.assertIn("nd::resize_zero(", m)
        self.assertIn("nd::resize_repeat(", _expr("np.resize(self.v, 6)"))

    def test_an_in_place_method_needs_a_local_receiver(self):
        # `(a + b).sort()` sorts a temporary -- dead code in Python too.
        with self.assertRaises(UnsupportedSpec) as cm:
            _emit("(self.v + self.v).sort()\nself.r = self.v\n")
        self.assertIn("local array variable", str(cm.exception))

    def test_sort_axis_none_is_rejected_for_the_in_place_form(self):
        with self.assertRaises(UnsupportedSpec):
            _emit("b = self.v.copy()\nb.sort(axis=None)\nself.r = b\n")


class TestNonzeroBothSpellings(unittest.TestCase):
    def test_method_and_free_unpack_identically(self):
        m = _emit("ys, xs = self.a.nonzero()\nself.r = ys + xs\n")
        f = _emit("ys, xs = np.nonzero(self.a)\nself.r = ys + xs\n")
        self.assertEqual(m, f)

    def test_both_spellings_point_at_the_unpack_form(self):
        for src in ("self.r = self.a.nonzero()\n",
                    "self.r = np.nonzero(self.a)\n"):
            with self.subTest(src=src):
                with self.assertRaises(UnsupportedSpec) as cm:
                    _emit(src)
                self.assertIn("tuple-unpacked", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
