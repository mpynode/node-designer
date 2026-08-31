"""Maya-FREE: the string surface -- str(), .strip(), a str ternary, and the
string-ARRAY kind produced by list(<str>).

The transpiler's ``str`` kind is a ``std::string`` carrier. This adds the
minimum needed to turn a runtime string into a countable sequence of labels:

  * ``str(s)`` on a string is the IDENTITY. ``str()`` of a NUMBER is rejected --
    Python's repr (``str(3.0) == "3.0"``, ``str(3) == "3"``) has no exact C++
    equivalent, and a near-miss would draw the wrong text.
  * ``s.strip()`` strips the exact set of code points ``str.isspace()`` accepts,
    not just ASCII blanks, so a stripped-empty test cannot disagree with Python.
  * ``list(s)`` splits by CODE POINT (Python), NOT by byte -- a UTF-8
    ``std::string`` would otherwise report a 2-byte 'é' as two labels.

The ``strv`` kind is a ``std::vector<std::string>``: it supports ``len()``,
positional indexing (``v[i]`` -> one ``str``) and being handed to a consumer
(DrawText). Every numeric use REJECTS rather than reaching a numeric coercion
that has no std::string case. Indexing is what lets a string ARRAY input drive a
loop -- the File Composite template walks ``self.layers[i]`` -- so a slice or a
tuple index rejects rather than lowering a near-miss.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c
from mpynode.native.compiler.errors import UnsupportedSpec


def _emit(compute, env=None):
    env = dict(env or {"self.s": p2c.str_t()})
    res, _w, _h = p2c.transpile_compute_block(
        compute, env, {"self.r": lambda v: ["out = %s;" % v.code]})
    return "\n".join(res.all_lines())


def _rejects(test, compute, env=None):
    with test.assertRaises(UnsupportedSpec):
        _emit(compute, env)


class TestStrBuiltin(unittest.TestCase):
    def test_str_of_a_string_is_the_identity(self):
        out = _emit("t = str(self.s)\nself.r = len(list(t))\n")
        self.assertIn("std::string", out)
        self.assertNotIn("to_string", out)

    def test_str_of_a_number_rejects(self):
        """Python's number->text formatting has no exact C++ equivalent."""
        _rejects(self, "t = str(1.5)\nself.r = len(list(t))\n")

    def test_str_of_an_array_rejects(self):
        _rejects(self, "t = str(self.a)\nself.r = len(list(t))\n",
                 {"self.a": p2c.array_t("double", 1)})


class TestStrip(unittest.TestCase):
    def test_strip_lowers_to_the_runtime_helper(self):
        out = _emit("t = self.s.strip()\nself.r = len(list(t))\n")
        self.assertIn("nd::str_strip(", out)

    def test_strip_takes_no_arguments(self):
        """str.strip(chars) strips a SET, not a prefix -- not lowered."""
        _rejects(self, 't = self.s.strip("x")\nself.r = len(list(t))\n')

    def test_strip_of_a_number_rejects(self):
        _rejects(self, "t = (1.0).strip()\nself.r = 1.0\n")


class TestStringTernary(unittest.TestCase):
    def test_both_branches_string_selects(self):
        out = _emit('t = self.s if self.s else "fallback"\n'
                    "self.r = len(list(t))\n")
        self.assertIn("?", out)
        self.assertIn("fallback", out)

    def test_mixed_string_and_number_rejects(self):
        _rejects(self, "t = self.s if self.s else 1.0\nself.r = len(list(t))\n")


class TestListOfString(unittest.TestCase):
    def test_list_of_a_string_splits_by_code_point(self):
        out = _emit("t = list(self.s)\nself.r = len(t)\n")
        self.assertIn("nd::str_chars(", out)

    def test_a_string_array_local_is_a_vector_of_string(self):
        out = _emit("t = list(self.s)\nself.r = len(t)\n")
        self.assertIn("std::vector<std::string> ", out)

    def test_len_counts_the_elements(self):
        out = _emit("t = list(self.s)\nself.r = len(t)\n")
        self.assertIn(".size()", out)

    def test_list_of_a_number_rejects(self):
        _rejects(self, "t = list(1.0)\nself.r = 1.0\n")

    def test_list_of_an_array_rejects(self):
        """np arrays already ARE the sequence; list() of one has no meaning here."""
        _rejects(self, "t = list(self.a)\nself.r = 1.0\n",
                 {"self.a": p2c.array_t("double", 1)})


class TestStringArrayIndexing(unittest.TestCase):
    """``v[i]`` yields ONE std::string, via the same negative-index wrap nd::at1
    uses. This is what lets a string-array INPUT drive a loop."""

    # len() takes a strv, not a bare str, so an indexed element is re-split with
    # list(...) to give the numeric sink something countable.
    def test_index_lowers_to_strv_at(self):
        out = _emit("t = list(self.s)\nself.r = len(list(t[0]))\n")
        self.assertIn("nd::strv_at(", out)

    def test_indexed_element_is_a_string(self):
        """It must land in the `str` kind -- a numeric use of it still rejects,
        which is the proof it did not silently become a number."""
        _rejects(self, "t = list(self.s)\nself.r = t[0] + 1.0\n")

    def test_a_runtime_index_lowers(self):
        out = _emit("t = list(self.s)\ni = len(t) - 1\n"
                    "self.r = len(list(t[i]))\n")
        self.assertIn("nd::strv_at(", out)

    def test_slice_rejects(self):
        """A slice needs a runtime-sized sub-vector this kind cannot carry."""
        _rejects(self, "t = list(self.s)\nu = t[0:2]\nself.r = len(u)\n")

    def test_tuple_index_rejects(self):
        _rejects(self, "t = list(self.s)\nself.r = len(list(t[0, 1]))\n")

    def test_string_key_rejects(self):
        """A name key has no runtime form -- reject where the message says so."""
        _rejects(self, "t = list(self.s)\nself.r = len(list(t[self.s]))\n")


class TestStringArrayIsInert(unittest.TestCase):
    """Every numeric use must REJECT, not reach a coercion with no string case."""

    def test_arithmetic_rejects(self):
        _rejects(self, "t = list(self.s)\nself.r = t + 1.0\n")

    def test_comparison_rejects(self):
        _rejects(self, "t = list(self.s)\nself.r = 1.0 if t == t else 2.0\n")

    def test_invert_rejects(self):
        _rejects(self, "t = list(self.s)\nself.r = ~t\n")

    def test_pow_squared_rejects(self):
        _rejects(self, "t = list(self.s)\nself.r = t ** 2\n")

    def test_used_as_a_number_rejects(self):
        _rejects(self, "t = list(self.s)\nself.r = float(t)\n")

    def test_persistent_state_rejects(self):
        with self.assertRaises(UnsupportedSpec):
            p2c.transpile_compute_block(
                "self.keep = list(self.s)\nself.r = 1.0\n",
                {"self.s": p2c.str_t()},
                {"self.r": lambda v: ["out = %s;" % v.code]},
                state_vars={"keep"})


if __name__ == "__main__":
    unittest.main()
