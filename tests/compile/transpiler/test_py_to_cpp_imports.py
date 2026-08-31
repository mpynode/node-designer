"""Maya-FREE: module dispatch resolves a name's ORIGIN, not its spelling.

Python binds a module -- or a name out of one -- in several shapes, and they all
reach the same function:

    import numpy as np             ->  np.sin(x)
    import numpy as onp            ->  onp.sin(x)
    import numpy.linalg as la      ->  la.norm(x)
    from numpy import sin as s     ->  s(x)
    from numpy.linalg import norm  ->  norm(x)
    from numpy import *            ->  sin(x)

Dispatching on the SPELLING gets all but the conventional `np.` wrong: it
rejects valid code, and -- worse -- it treats the NAME `np` as numpy even when
the source aliased something else to it, silently lowering `mylib.sin` to
`std::sin`. So every site resolves through `_parse_import_bindings` +
`canonical_dotted` and compares canonical origins.

The AMBIENT default is preserved on purpose: the Init header seeds `np`, and
computes rely on it, so a source with NO import behaves exactly as before. Only
an import that actually rebinds the name overrides it.
"""

from __future__ import annotations

import unittest

from mpynode.native.compiler import py_to_cpp as p2c
from mpynode.native.compiler.errors import UnsupportedSpec


def _emit(compute, init=""):
    res, _w, _h = p2c.transpile_compute_block(
        compute, {"self.a": p2c.array_t("double", 1)},
        {"self.r": lambda v: ["out = %s;" % v.code]}, init)
    return "\n".join(res.all_lines())


class TestParseImportBindings(unittest.TestCase):
    def _b(self, src):
        return p2c._parse_import_bindings(src)[0]

    def test_plain_import(self):
        self.assertEqual("numpy", self._b("import numpy\n")["numpy"])

    def test_aliased_import(self):
        self.assertEqual("numpy", self._b("import numpy as np")["np"])
        self.assertEqual("numpy", self._b("import numpy as onp")["onp"])

    def test_submodule_import_binds_the_ROOT_name(self):
        """`import numpy.linalg` binds `numpy`, NOT `numpy.linalg`."""
        b = self._b("import numpy.linalg\n")
        self.assertEqual("numpy", b["numpy"])
        self.assertNotIn("numpy.linalg", b)

    def test_aliased_submodule_import(self):
        self.assertEqual("numpy.linalg",
                         self._b("import numpy.linalg as la")["la"])

    def test_from_import(self):
        self.assertEqual("numpy.sin", self._b("from numpy import sin")["sin"])

    def test_from_import_as(self):
        self.assertEqual("numpy.sin",
                         self._b("from numpy import sin as s")["s"])

    def test_from_submodule_import(self):
        self.assertEqual("numpy.linalg.norm",
                         self._b("from numpy.linalg import norm")["norm"])

    def test_from_import_submodule_name(self):
        self.assertEqual("numpy.linalg",
                         self._b("from numpy import linalg as la")["la"])

    def test_star_import_is_reported_separately(self):
        _b, stars = p2c._parse_import_bindings("from numpy import *")
        self.assertEqual(["numpy"], stars)

    def test_duplicate_star_is_deduped(self):
        """The same source is handed in twice (helper AND const source); that
        must not read as a second, ambiguous star import."""
        _b, stars = p2c._parse_import_bindings(
            ["from numpy import *", "from numpy import *"])
        self.assertEqual(["numpy"], stars)

    def test_relative_import_has_no_resolvable_origin(self):
        self.assertEqual(p2c._SHADOWED_ORIGIN,
                         self._b("from . import norm")["norm"])

    def test_module_level_rebinding_wins(self):
        self.assertEqual(p2c._SHADOWED_ORIGIN,
                         self._b("import numpy as np\nnp = 5\n")["np"])

    def test_a_def_rebinds(self):
        self.assertEqual(p2c._SHADOWED_ORIGIN,
                         self._b("from numpy import sin\ndef sin(x): return x\n")
                         ["sin"])

    def test_attribute_assignment_does_not_rebind_the_base(self):
        """`self.x = 1` mutates self; it does not rebind the NAME self."""
        self.assertNotIn("self", self._b("import numpy as np\nself.x = 1\n"))

    def test_subscript_assignment_does_not_rebind_the_base(self):
        self.assertNotIn("a", self._b("import numpy as np\na[0] = 1\n"))


class TestCanonicalDotted(unittest.TestCase):
    def test_head_is_resolved_and_the_tail_kept(self):
        self.assertEqual("numpy.linalg.norm",
                         p2c.canonical_dotted("la.norm", {"la": "numpy.linalg"}))

    def test_bare_name_resolves_whole(self):
        self.assertEqual("numpy.sin",
                         p2c.canonical_dotted("s", {"s": "numpy.sin"}))

    def test_unbound_head_passes_through(self):
        self.assertEqual("foo.bar", p2c.canonical_dotted("foo.bar", {}))

    def test_single_star_resolves_unbound_names(self):
        self.assertEqual("numpy.sin",
                         p2c.canonical_dotted("sin", {}, ["numpy"]))

    def test_two_stars_are_ambiguous_and_resolve_nothing(self):
        self.assertEqual("sin",
                         p2c.canonical_dotted("sin", {}, ["numpy", "mylib"]))

    def test_shadowed_stays_shadowed(self):
        self.assertEqual(p2c._SHADOWED_ORIGIN,
                         p2c.canonical_dotted("np.sin",
                                              {"np": p2c._SHADOWED_ORIGIN}))


class TestEveryShapeReachesOneLowering(unittest.TestCase):
    """The claim is not "it lowered" -- it is "it lowered to the SAME thing"."""

    def _same(self, variants):
        outs = [_emit(compute, init) for init, compute in variants]
        self.assertEqual(1, len(set(outs)),
                         "spellings produced different C++:\n\n%s"
                         % "\n---\n".join(sorted(set(outs))))
        return outs[0]

    def test_numpy_function_spellings(self):
        out = self._same([
            ("import numpy as np\n", "self.r = np.sin(self.a)\n"),
            ("import numpy\n", "self.r = numpy.sin(self.a)\n"),
            ("import numpy as onp\n", "self.r = onp.sin(self.a)\n"),
            ("from numpy import sin\n", "self.r = sin(self.a)\n"),
            ("from numpy import sin as s\n", "self.r = s(self.a)\n"),
            ("from numpy import *\n", "self.r = sin(self.a)\n"),
            ("", "self.r = np.sin(self.a)\n"),          # ambient, unchanged
        ])
        self.assertIn("nd::sin(", out)

    def test_numpy_submodule_spellings(self):
        out = self._same([
            ("import numpy as np\n", "self.r = np.linalg.norm(self.a)\n"),
            ("import numpy.linalg as la\n", "self.r = la.norm(self.a)\n"),
            ("from numpy import linalg as la\n", "self.r = la.norm(self.a)\n"),
            ("from numpy.linalg import norm\n", "self.r = norm(self.a)\n"),
            ("from numpy.linalg import norm as f\n", "self.r = f(self.a)\n"),
        ])
        self.assertIn("norm", out)

    def test_math_function_spellings(self):
        self._same([
            ("import math\n", "self.r = math.cos(1.0)\n"),
            ("import math as m\n", "self.r = m.cos(1.0)\n"),
            ("from math import cos\n", "self.r = cos(1.0)\n"),
            ("from math import cos as c\n", "self.r = c(1.0)\n"),
        ])

    def test_named_constant_spellings(self):
        out = self._same([
            ("import math\n", "self.r = math.pi\n"),
            ("import math as m\n", "self.r = m.pi\n"),
            ("from math import pi\n", "self.r = pi\n"),
            ("from math import pi as P\n", "self.r = P\n"),
            ("import numpy as np\n", "self.r = np.pi\n"),
        ])
        self.assertIn("3.14159", out)

    def test_dtype_spellings(self):
        self._same([
            ("import numpy as np\n",
             "self.r = np.array([1.0], dtype=np.float64)\n"),
            ("import numpy\n",
             "self.r = numpy.array([1.0], dtype=numpy.float64)\n"),
            ("import numpy as np\nfrom numpy import float64\n",
             "self.r = np.array([1.0], dtype=float64)\n"),
        ])


class TestOriginNotSpelling(unittest.TestCase):
    """A name is numpy because of where it CAME FROM, not what it is called."""

    def test_a_foreign_module_aliased_to_np_is_not_numpy(self):
        with self.assertRaises(UnsupportedSpec):
            _emit("self.r = np.sin(self.a)\n", "import mylib as np\n")

    def test_a_foreign_module_aliased_to_numpy_is_not_numpy(self):
        with self.assertRaises(UnsupportedSpec):
            _emit("self.r = numpy.sin(self.a)\n", "import mylib as numpy\n")

    def test_a_local_named_np_shadows_the_module(self):
        """A bound VALUE wins over any module of the same name."""
        with self.assertRaises(UnsupportedSpec):
            _emit("np = self.a\nself.r = np.sin(self.a)\n",
                  "import numpy as np\n")

    def test_a_star_import_from_an_unknown_module_is_not_numpy(self):
        with self.assertRaises(UnsupportedSpec):
            _emit("self.r = sin(self.a)\n", "from mylib import *\n")

    def test_ambient_np_still_works_with_no_import(self):
        self.assertIn("nd::sin(", _emit("self.r = np.sin(self.a)\n"))


class TestStarImportDoesNotSwallowEverything(unittest.TestCase):
    """`from numpy import *` binds unbound BARE names -- not `self`, and not the
    builtins numpy does not export.

    The star resolver used to claim every unbound head, so `self.v.copy()`
    resolved to `numpy.self.v.copy` and every method call on an input was
    rejected the moment a star import appeared. A compute block's env is keyed by
    the FULL dotted name ("self.v"), so the head "self" is never in env and the
    ordinary shadowing guard could not catch it.
    """

    def _star(self, compute):
        return _emit(compute, "from numpy import *\n")

    def test_method_call_on_an_input_survives_a_star_import(self):
        for call in ("self.a.copy()", "self.a.sum()", "self.a.ravel()",
                     "self.a.astype(np.int64)"):
            with self.subTest(call=call):
                self.assertEqual(_emit("self.r = %s\n" % call),
                                 self._star("self.r = %s\n" % call))

    def test_shape_read_survives_a_star_import(self):
        src = "n = self.a.shape[0]\nself.r = np.full((2,), float(n))\n"
        self.assertEqual(_emit(src), self._star(src))

    def test_builtins_numpy_does_not_export_stay_builtins(self):
        # numpy exports abs/min/max/round/sum/any/all but NOT these.
        for call in ("float(1.5)", "int(1.5)", "bool(1.5)"):
            with self.subTest(call=call):
                self.assertEqual(_emit("self.r = np.full((2,), %s)\n" % call),
                                 self._star("self.r = np.full((2,), %s)\n" % call))

    def test_len_stays_a_builtin_under_a_star_import(self):
        src = "self.r = np.full((2,), float(len(self.a)))\n"
        self.assertEqual(_emit(src), self._star(src))

    def test_a_name_numpy_DOES_export_still_resolves_to_numpy(self):
        # np.abs exists, so after a star import `abs(x)` really is np.abs --
        # the fix must not over-correct and grab it back as the builtin.
        self.assertIn("nd::fabs(", self._star("self.r = abs(self.a)\n"))

    def test_an_explicit_import_still_beats_the_builtin_shortcut(self):
        # `from numpy import float64 as float` genuinely rebinds the name, so it
        # must NOT be silently treated as the builtin float().
        with self.assertRaises(UnsupportedSpec):
            _emit("self.r = np.full((2,), float(1.5))\n",
                  "from numpy import float64 as float\n")

    def test_a_star_import_cannot_resolve_a_DOTTED_name(self):
        # `from numpy import *` binds names, never dotted paths.
        self.assertEqual("x.y.z", p2c.canonical_dotted("x.y.z", {}, ["numpy"]))
        self.assertEqual("numpy.sin", p2c.canonical_dotted("sin", {}, ["numpy"]))

    def test_a_bound_submodule_still_resolves_its_tail(self):
        # The dotted restriction applies only to the STAR fallback; an explicit
        # binding must still carry its tail.
        self.assertEqual("numpy.linalg.norm",
                         p2c.canonical_dotted("la.norm", {"la": "numpy.linalg"},
                                              ["numpy"]))


if __name__ == "__main__":
    unittest.main()
