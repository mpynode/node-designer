"""Maya-FREE: the compile-time ``isinstance()`` fold in py_to_cpp.

``isinstance`` reaches the transpiler from exactly two places in the shipped
template corpus, both spelled against a ``getattr(self, '<name>', None)``
default::

    templates/MPyLocator/Widget Showcase   if not isinstance(presets, dict)
    templates/MPyLocator/Mesh Regions      if isinstance(_legacy, dict)

A ``None`` binding carries no C++ value at all, so its Python class IS a
compile-time fact and the call folds to ``false`` -- the existing dead-branch
handling then prunes the arm. Everything else must REJECT: a lowered value keeps
no record of the Python class it came from (dtype ``double`` covers a Python
float AND a ``np.float32`` element, and ``isinstance(np.float32(1.0), float)`` is
False while ``isinstance(np.float64(1.0), float)`` is True), so folding it would
silently disagree with the interpreted node.

The rejects are the load-bearing half of this module: they are what keeps a node
routing to the AI porter instead of being mis-lowered.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c
from mpynode.native.compiler.errors import UnsupportedSpec

_A = p2c.array_t("double", 1)


def _emit_fn(body):
    """Transpile ``def f(a)`` with a rank-1 double ``a``; return the C++ text."""
    res = p2c.transpile_function("def f(a):\n" + body, {"a": _A})
    return "\n".join(list(res.decl_lines) + list(res.body_lines))


def _emit_block(compute, const=None):
    """Transpile a compute block with one array input and one output writer."""
    res, _w, _h = p2c.transpile_compute_block(
        compute, {"self.a": _A},
        {"self.r": lambda v: ["out = %s;" % v.code]},
        const_source=const)
    return "\n".join(res.all_lines())


def _branch_on_none(cls_src):
    """`x = None` then branch on `isinstance(x, <cls_src>)`."""
    return ("    x = None\n"
            "    if isinstance(x, %s):\n"
            "        return a\n"
            "    return a * 2.0\n" % cls_src)


class TestFoldsOnAStaticallyNoneOperand(unittest.TestCase):
    """Every class in the decidable set answers False for None."""

    def test_dict_folds_false(self):
        # the widget_showcase / mesh_regions spelling
        self.assertIn("if (false) {", _emit_fn(_branch_on_none("dict")))

    def test_str_folds_false(self):
        self.assertIn("if (false) {", _emit_fn(_branch_on_none("str")))

    def test_tuple_of_classes_folds_false(self):
        self.assertIn("if (false) {", _emit_fn(_branch_on_none("(dict, list)")))

    def test_negated_call_takes_the_branch(self):
        """`if not isinstance(x, dict)` -- the widget_showcase shape. The fold
        has to survive the `not`, or the wrong arm is pruned."""
        out = _emit_fn("    x = None\n"
                       "    if not isinstance(x, dict):\n"
                       "        return a\n"
                       "    return a * 2.0\n")
        self.assertIn("(!(false))", out)

    def test_no_isinstance_call_survives_into_the_cpp(self):
        self.assertNotIn("isinstance", _emit_fn(_branch_on_none("dict")))

    def test_widget_showcase_idiom_folds(self):
        """The construct as it is actually authored: a getattr-defaulted
        optional stored var tested for dict-ness."""
        out = _emit_block("presets = getattr(self, 'presets', None)\n"
                          "if not isinstance(presets, dict):\n"
                          "    self.r = self.a\n"
                          "else:\n"
                          "    self.r = self.a * 2.0\n")
        self.assertIn("(!(false))", out)
        self.assertNotIn("isinstance", out)

    def test_ndarray_is_matched_by_ORIGIN_not_spelling(self):
        """`np.ndarray` is resolved through the canonical import resolver, so an
        aliased import reaches the same fold."""
        for alias in ("np", "onp"):
            out = _emit_block("x = getattr(self, 'missing', None)\n"
                              "if isinstance(x, %s.ndarray):\n"
                              "    self.r = self.a\n"
                              "else:\n"
                              "    self.r = self.a * 2.0\n" % alias,
                              const="import numpy as %s\n" % alias)
            self.assertIn("if (false) {", out)


class TestRejectsWhatItCannotDecide(unittest.TestCase):
    """Reject-or-lower, never mis-lower: each of these must keep the node on
    the AI-porter path rather than being guessed at."""

    def _reject(self, body, substring):
        with self.assertRaises(UnsupportedSpec) as cm:
            _emit_fn(body)
        self.assertIn(substring, str(cm.exception))

    def test_operand_that_is_a_real_value_rejects(self):
        """`a` lowers to nd::Array<double>; whether the interpreted node held a
        list, a tuple or an ndarray there is not recoverable."""
        self._reject("    if isinstance(a, np.ndarray):\n"
                     "        return a\n"
                     "    return a * 2.0\n",
                     "not statically None")

    def test_declared_input_read_through_getattr_rejects(self):
        """`getattr(self, 'a', None)` on a DECLARED input selects the attribute,
        not the default -- so the operand is a value, not None."""
        with self.assertRaises(UnsupportedSpec) as cm:
            _emit_block("x = getattr(self, 'a', None)\n"
                        "if isinstance(x, dict):\n"
                        "    self.r = self.a\n"
                        "else:\n"
                        "    self.r = self.a * 2.0\n")
        self.assertIn("not statically None", str(cm.exception))

    def test_object_rejects(self):
        """`object` is the spelling that would answer TRUE for None, so it is
        deliberately outside the decidable set."""
        self._reject(_branch_on_none("object"), "not a class this can decide")

    def test_type_none_rejects(self):
        """The other True-answering spelling."""
        self._reject(_branch_on_none("type(None)"),
                     "not a class this can decide")

    def test_a_shadowed_class_name_rejects(self):
        """A local named `dict` is the local, not the builtin -- folding on the
        spelling would be reading a name the program rebound."""
        self._reject("    dict = a\n" + _branch_on_none("dict"),
                     "not a class this can decide")

    def test_three_argument_call_rejects(self):
        self._reject(_branch_on_none("dict, 1"),
                     "only isinstance(<value>, <type>) is lowered")


if __name__ == "__main__":
    unittest.main()
