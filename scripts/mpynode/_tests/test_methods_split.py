"""Pure headless tests for ``methods_split`` (no ``_setup`` / Maya / Qt).

Runnable both under mayapy (via the gate's ``unittest discover``) and under a
plain ``python3`` interpreter, because ``methods_split`` and its one dependency
(``py_export._classify_funcdef``) import only ``ast`` + stdlib.
"""
import unittest

from mpynode._common.methods.methods_split import (
    split_methods_source,
    join_methods_source,
)

# Canonical layout: module preamble (import, constant, free function) FIRST,
# then the class-bound methods -- so join(split(x)) is byte-identical.
METHODS = (
    "import numpy as np\n"
    "GAIN = 2.0\n"
    "\n"
    "def helper(x):\n"
    "    return x * GAIN\n"
    "\n"
    "def doThing(self, x):\n"
    "    return helper(x)\n"
    "\n"
    "@classmethod\n"
    "def make(cls):\n"
    "    return cls()\n"
)


class TestSplit(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(split_methods_source(""), ("", ""))
        self.assertEqual(split_methods_source("   \n"), ("", ""))

    def test_routes_methods_and_functions(self):
        fns, meth = split_methods_source(METHODS)
        self.assertIn("def helper", fns)
        self.assertIn("import numpy", fns)
        self.assertIn("GAIN = 2.0", fns)
        self.assertNotIn("def doThing", fns)
        self.assertIn("def doThing", meth)
        self.assertIn("@classmethod", meth)
        self.assertIn("def make", meth)
        self.assertNotIn("def helper", meth)

    def test_roundtrip_canonical(self):
        fns, meth = split_methods_source(METHODS)
        self.assertEqual(join_methods_source(fns, meth), METHODS)

    def test_roundtrip_all_methods(self):
        src = "def doThing(self):\n    return 1\n"
        fns, meth = split_methods_source(src)
        self.assertEqual(fns, "")
        self.assertEqual(join_methods_source(fns, meth), src)

    def test_roundtrip_all_functions(self):
        src = "import os\nX = 1\ndef f(x):\n    return x\n"
        fns, meth = split_methods_source(src)
        self.assertEqual(meth, "")
        self.assertEqual(join_methods_source(fns, meth), src)

    def test_helper_class_and_async_to_functions(self):
        src = (
            "class Helper:\n    pass\n"
            "async def a():\n    return 1\n"
            "def m(self):\n    return 2\n"
        )
        fns, meth = split_methods_source(src)
        self.assertIn("class Helper", fns)
        self.assertIn("async def a", fns)
        self.assertIn("def m(self)", meth)
        self.assertNotIn("class Helper", meth)

    def test_static_and_cls_first_go_to_methods(self):
        src = (
            "@staticmethod\n"
            "def s():\n    return 1\n"
            "def c(cls):\n    return 2\n"
            "def free(x):\n    return x\n"
        )
        fns, meth = split_methods_source(src)
        self.assertIn("@staticmethod", meth)
        self.assertIn("def s()", meth)
        self.assertIn("def c(cls)", meth)
        self.assertIn("def free(x)", fns)
        self.assertNotIn("def free(x)", meth)

    def test_decorator_rides_with_def(self):
        # @maya_command on a self-first def -> stays glued to the method chunk.
        src = (
            "@maya_command\n"
            "def cmd(self):\n    return 1\n"
        )
        fns, meth = split_methods_source(src)
        self.assertEqual(fns, "")
        self.assertIn("@maya_command", meth)
        self.assertEqual(join_methods_source(fns, meth), src)

    def test_syntax_error_degrades_to_methods(self):
        bad = "def f(:\n  pass\n"
        fns, meth = split_methods_source(bad)
        self.assertEqual(fns, "")
        self.assertEqual(meth, bad)
        self.assertEqual(join_methods_source(fns, meth), bad)

    def test_comment_only_routes_to_methods(self):
        # A statement-less source (pure comments / blanks -- e.g. the seeded
        # new-node Methods header) has no funcdefs to classify. It routes to the
        # PRIMARY Methods view, not Functions, and round-trips byte-identically.
        src = (
            "# ------------------------------------------------------------\n"
            "# mPyLocator -- Methods: companion commands + helper functions.\n"
            "#\n"
            "# @maya_command example ...\n"
        )
        fns, meth = split_methods_source(src)
        self.assertEqual(fns, "")
        self.assertEqual(meth, src)
        self.assertEqual(join_methods_source(fns, meth), src)

    def test_join_order_and_short_circuit(self):
        self.assertEqual(join_methods_source("", "M\n"), "M\n")
        self.assertEqual(join_methods_source("F\n", ""), "F\n")
        self.assertEqual(join_methods_source("F", "M\n"), "F\nM\n")

    def test_classify_contract(self):
        # Pin the _classify_funcdef behavior split relies on.
        import ast

        from mpynode._common.io.py_export import _classify_funcdef

        def kind(s):
            return _classify_funcdef(ast.parse(s).body[0])[0]

        self.assertEqual(kind("def f(self): pass"), "class")
        self.assertEqual(kind("def f(cls): pass"), "class")
        self.assertEqual(kind("@staticmethod\ndef f(): pass"), "class")
        self.assertEqual(kind("@classmethod\ndef f(cls): pass"), "class")
        self.assertEqual(kind("def f(x): pass"), "module")
        self.assertEqual(kind("def f(): pass"), "module")


if __name__ == "__main__":
    unittest.main()
