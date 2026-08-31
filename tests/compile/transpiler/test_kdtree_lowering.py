"""cKDTree lowering: the chained temporary, and the a[idx] gather beside it.

Both of these were rejections, and together they are why a real closest-point
node reached the AI porter instead of ``nd::KDTree``. The porter then wrote, in
the generated C++:

    // A kd-tree and a brute-force scan return the same nearest point /
    // distance, so the tree is replaced by an explicit O(N*M) scan.

-- a complexity-class downgrade, measured at 2.5x-29x slower than the kernel
that was already available (``tools/kdtree_lowering_bench.cpp``).

These assertions are about ROUTING, not arithmetic: that the two spellings reach
``nd::kdtree`` / ``nd::take`` at all. The numbers are pinned as real parity
against scipy and numpy in ``native/tests/py_to_cpp_test.py``, and the tie rule
against brute force in ``tools/kdtree_kernel_check.cpp``.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler.py_to_cpp import (UnsupportedSpec, array_t,
                                               transpile_function)

_HEAD = ("def f(p, q):\n"
         "    import numpy as np\n"
         "    from scipy.spatial import cKDTree\n")

# (M, 3) points and (N, 3) queries -- the closest-point node's two arrays.
_ARGS = {"p": array_t("double", 2), "q": array_t("double", 2)}


def _lower(body):
    """-> the generated C++ for ``body``, or raise UnsupportedSpec."""
    res = transpile_function(_HEAD + body, _ARGS)
    return "\n".join(list(res.decl_lines) + list(res.body_lines))


class TestChainedKdtree(unittest.TestCase):
    """`cKDTree(p).query(q)` -- the spelling scipy's own docs use."""

    def test_chained_query_emits_a_real_tree(self):
        cpp = _lower("    d, i = cKDTree(p).query(q, k=1)\n"
                     "    return d\n")
        self.assertIn("nd::kdtree(", cpp)
        self.assertIn("nd::kd_query1(", cpp)

    def test_chained_and_bound_emit_the_same_kernel_calls(self):
        chained = _lower("    d, i = cKDTree(p).query(q, k=1)\n"
                         "    return d\n")
        bound = _lower("    t = cKDTree(p)\n"
                       "    d, i = t.query(q, k=1)\n"
                       "    return d\n")
        for call in ("nd::kdtree(", "nd::kd_query1("):
            self.assertEqual(chained.count(call), bound.count(call),
                             "chained/bound disagree on %s" % call)

    def test_chained_builds_the_tree_exactly_once(self):
        """The receiver must be materialised once, not re-evaluated per use."""
        cpp = _lower("    d, i = cKDTree(p).query(q, k=1)\n"
                     "    return d\n")
        self.assertEqual(cpp.count("nd::kdtree("), 1)

    def test_chained_query_ball_point_lowers(self):
        cpp = _lower("    s, it = cKDTree(p).query_ball_point(q, 3.0)\n"
                     "    return s\n")
        self.assertIn("nd::kd_query_ball_point(", cpp)

    def test_chained_query_pairs_lowers(self):
        cpp = _lower("    pr = cKDTree(p).query_pairs(3.0, "
                     "output_type='ndarray')\n"
                     "    return pr\n")
        self.assertIn("nd::kd_query_pairs(", cpp)

    def test_a_tree_still_cannot_escape_into_an_arbitrary_position(self):
        """Built and queried is the whole surface -- it has no value semantics."""
        with self.assertRaises(UnsupportedSpec) as cm:
            _lower("    return np.sum(cKDTree(p))\n")
        self.assertIn("cKDTree", str(cm.exception))


class TestGatherIndexing(unittest.TestCase):
    """`a[idx]` with an integer ARRAY -- fancy indexing on axis 0."""

    def test_rows_gather_lowers_to_take(self):
        cpp = _lower("    i = np.zeros(3).astype(np.int64)\n"
                     "    return p[i]\n")
        self.assertIn("nd::take(", cpp)

    def test_query_result_gathers_the_winning_rows(self):
        """The whole closest-point idiom in one statement."""
        cpp = _lower("    d, i = cKDTree(p).query(q, k=1)\n"
                     "    return p[i]\n")
        self.assertIn("nd::kdtree(", cpp)
        self.assertIn("nd::take(", cpp)

    def test_scalar_index_still_takes_the_slice_path(self):
        """A plain integer index must NOT become a gather."""
        cpp = _lower("    return p[2]\n")
        self.assertNotIn("nd::take(", cpp)
        self.assertIn("nd::slice(", cpp)

    def test_slice_still_takes_the_slice_path(self):
        cpp = _lower("    return p[1:4]\n")
        self.assertNotIn("nd::take(", cpp)
        self.assertIn("nd::slice(", cpp)

    def test_non_int64_index_is_converted_not_reinterpreted(self):
        cpp = _lower("    i = np.zeros(3).astype(np.int32)\n"
                     "    return p[i]\n")
        self.assertIn("nd::astype<int64_t>(", cpp)

    def test_boolean_mask_is_rejected_by_name(self):
        """A mask SELECTS a runtime-sized subset -- not a gather."""
        with self.assertRaises(UnsupportedSpec) as cm:
            _lower("    m = p[:, 0] > 0.0\n"
                   "    return p[m]\n")
        self.assertIn("mask", str(cm.exception))

    def test_mixed_tuple_fancy_index_is_still_rejected(self):
        """a[idx, 1] follows broadcasting rules this does not implement."""
        with self.assertRaises(UnsupportedSpec):
            _lower("    i = np.zeros(3).astype(np.int64)\n"
                   "    return p[i, 1]\n")


if __name__ == "__main__":
    unittest.main()
