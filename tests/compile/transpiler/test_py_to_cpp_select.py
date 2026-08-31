"""Maya-FREE: np.select(condlist, choicelist, default) -> nested np.where.

numpy takes the FIRST true condition, so the equivalent nesting is built from
the BACK: ``where(c0, v0, where(c1, v1, ... default))``. The lowering rewrites
to ``np.where`` AST nodes rather than emitting ``nd::`` directly, so it inherits
where's dtype promotion, rank inference and elementwise fusion unchanged instead
of duplicating them.

The list lengths must be known at COMPILE time -- the nesting depth is the list
length -- so a non-literal condlist/choicelist rejects.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c
from mpynode.native.compiler.errors import UnsupportedSpec


def _emit(compute, env=None):
    env = dict(env or {"self.a": p2c.array_t("double", 1)})
    res, _w, _h = p2c.transpile_compute_block(
        compute, env, {"self.r": lambda v: ["out = %s;" % v.code]})
    return "\n".join(res.all_lines())


class TestNpSelect(unittest.TestCase):
    def test_two_way_select_nests_two_wheres(self):
        out = _emit("self.r = np.select([self.a > 1.0, self.a > 0.0],\n"
                    "                   [1.0, 2.0], default=3.0)\n")
        self.assertEqual(2, out.count("nd::where("))

    def test_first_true_condition_wins(self):
        """The FIRST condition must be the OUTERMOST where, else a value later
        in the list would win where numpy takes the earlier one."""
        out = _emit("self.r = np.select([self.a > 1.0, self.a > 0.0],\n"
                    "                   [7.0, 9.0], default=3.0)\n")
        outer = out.index("7")
        inner = out.index("9")
        self.assertLess(outer, inner)

    def test_default_is_the_innermost_value(self):
        out = _emit("self.r = np.select([self.a > 1.0], [7.0], default=5.0)\n")
        self.assertIn("5", out[out.index("7"):])

    def test_default_defaults_to_zero(self):
        """numpy's default= is 0 when omitted."""
        out = _emit("self.r = np.select([self.a > 1.0], [7.0])\n")
        self.assertEqual(1, out.count("nd::where("))

    def test_positional_default_is_accepted(self):
        out = _emit("self.r = np.select([self.a > 1.0], [7.0], 5.0)\n")
        self.assertIn("5", out)

    def test_array_choices_lower(self):
        out = _emit("self.r = np.select([self.a > 1.0, self.a > 0.0],\n"
                    "                   [self.a, self.a * 2.0], default=0.0)\n")
        self.assertEqual(2, out.count("nd::where("))

    def test_length_mismatch_rejects(self):
        with self.assertRaises(UnsupportedSpec):
            _emit("self.r = np.select([self.a > 1.0], [1.0, 2.0])\n")

    def test_empty_condlist_rejects(self):
        with self.assertRaises(UnsupportedSpec):
            _emit("self.r = np.select([], [])\n")

    def test_non_literal_condlist_rejects(self):
        """The nesting depth IS the list length; an opaque sequence has none."""
        with self.assertRaises(UnsupportedSpec):
            _emit("conds = self.a\nself.r = np.select(conds, [1.0])\n")


if __name__ == "__main__":
    unittest.main()
