"""What a compiled bundle embeds: the @maya_command defs and what they use.

``command_dispatch.command_payload_source`` trims the Methods source to the
command closure before it is embedded, so demos, tests and the helpers only
they use never ship; the bundle's prelude carries no test kit either. Demos and
tests keep running on the interpreted node, and verify reads the tests from
``spec["methods"]``, which stays whole.
"""

from __future__ import annotations

import ast
import copy
import sys
import types
import unittest

from mpynode._common.methods.maya_command import detect_commands, maya_command
from mpynode.native.compiler.kernels import command_dispatch as cd

SRC = '''from __future__ import annotations
"""Module docstring."""
from typing import Optional

import math

_SCALE = 2.0
_DEMO_ONLY = 9


def _helper(x: Optional[float] = None):
    return (x or 0.0) * _SCALE


def _shared():
    return math.pi


def _demo_positions():
    return [_DEMO_ONLY]


@maya_command(name="scaleIt")
def scale_it(self, value: float = 1.0):
    return _helper(value) + _shared()


@maya_demo(label="A demo")
def demo(self):
    import mpynode
    return _demo_positions(), _shared()


@maya_test(label="A test")
def test_it(self):
    assert_close(1.0, 1.0)
'''


def _names(text):
    return {n.name for n in ast.parse(text).body if hasattr(n, "name")}


class TestTrim(unittest.TestCase):

    def test_commands_and_what_they_use_are_kept(self):
        out = cd.command_payload_source(SRC)
        self.assertEqual(_names(out), {"_helper", "_shared", "scale_it"})
        for kept in ("_SCALE = 2.0", "import math", "from typing import Optional"):
            self.assertIn(kept, out)

    def test_demos_tests_and_their_helpers_are_dropped(self):
        out = cd.command_payload_source(SRC)
        for gone in ("def demo", "def test_it", "_demo_positions", "_DEMO_ONLY",
                     "import mpynode", "assert_close", "Module docstring"):
            self.assertNotIn(gone, out)

    def test_an_undecorated_reserved_demo_is_dropped(self):
        src = SRC.replace('@maya_demo(label="A demo")\n', "")
        self.assertNotIn("def demo", cd.command_payload_source(src))

    def test_the_future_import_is_kept_first(self):
        out = cd.command_payload_source(SRC)
        self.assertTrue(out.startswith("from __future__ import annotations\n"))

    def test_kept_statements_are_byte_exact(self):
        out = cd.command_payload_source(SRC)
        for name in ("_helper", "scale_it"):
            node = next(n for n in ast.parse(SRC).body
                        if getattr(n, "name", "") == name)
            start = min([d.lineno for d in node.decorator_list] + [node.lineno])
            text  = "".join(SRC.splitlines(keepends=True)[start - 1:node.end_lineno])
            self.assertIn(text, out)

    def test_the_commands_are_unchanged(self):
        def strip(cmds):
            return [{k: v for k, v in c.items() if k != "lineno"} for c in cmds]

        out = cd.command_payload_source(SRC)
        self.assertEqual(strip(detect_commands(out)), strip(detect_commands(SRC)))

    def test_it_runs_the_way_a_bundle_runs_it(self):
        """No inherited ``from __future__`` flags and only maya_command
        injected -- an annotation-only import that was dropped would raise
        NameError here, not on the host."""
        out = cd.command_payload_source(SRC.replace(
            "from __future__ import annotations\n", ""))
        ns = {"maya_command": maya_command}
        exec(compile(out, "<methods>", "exec", dont_inherit=True), ns)
        self.assertAlmostEqual(ns["scale_it"](None, 1.5), 3.0 + 3.141592653589793)

    def test_decorators_defaults_and_bases_are_followed(self):
        src = ("def _deco(fn):\n    return fn\n\n\n"
               "_DEFAULT = 3\n\n\n"
               "class _Base:\n    pass\n\n\n"
               "class _Thing(_Base):\n    pass\n\n\n"
               "@maya_command\n@_deco\n"
               "def poke(self, n=_DEFAULT):\n    return _Thing()\n")
        self.assertEqual(_names(cd.command_payload_source(src)),
                         {"_deco", "_Base", "_Thing", "poke"})
        self.assertIn("_DEFAULT = 3", cd.command_payload_source(src))

    def test_a_global_rebinding_keeps_its_module_binding(self):
        src = ("_COUNT = 0\n\n\n"
               "@maya_command\n"
               "def poke(self):\n    global _COUNT\n    _COUNT = 1\n")
        self.assertIn("_COUNT = 0", cd.command_payload_source(src))

    def test_a_statement_that_binds_nothing_is_kept(self):
        src = ("print('side effect')\n\n\n"
               "@maya_command\ndef poke(self):\n    return 1\n")
        self.assertIn("print('side effect')", cd.command_payload_source(src))

    def test_statements_sharing_a_line_stay_together(self):
        src = ("_A = 1; _B = 2\n\n\n"
               "@maya_command\ndef poke(self):\n    return _B\n")
        out = cd.command_payload_source(src)
        self.assertIn("_A = 1; _B = 2", out)
        ast.parse(out)

    def test_trimming_is_idempotent(self):
        out = cd.command_payload_source(SRC)
        self.assertEqual(cd.command_payload_source(out), out)

    def test_a_demo_edit_does_not_move_the_payload(self):
        edited = SRC.replace("return _demo_positions(), _shared()",
                             "return [1, 2, 3]\n    # and a longer demo")
        self.assertEqual(cd.command_payload_source(edited),
                         cd.command_payload_source(SRC))

    def test_a_command_edit_moves_the_payload(self):
        edited = SRC.replace("_helper(value) + _shared()", "_helper(value)")
        self.assertNotEqual(cd.command_payload_source(edited),
                            cd.command_payload_source(SRC))

    def test_a_dynamic_lookup_in_command_code_is_refused(self):
        src = ("@maya_command\ndef poke(self):\n"
               "    return globals()['_helper']()\n")
        with self.assertRaises(ValueError) as ctx:
            cd.command_payload_source(src)
        self.assertIn("globals()", str(ctx.exception))
        self.assertIn("L3", str(ctx.exception))

    def test_a_dynamic_lookup_in_a_demo_is_not_shipped_so_not_refused(self):
        src = SRC + "\n\n@maya_demo\ndef demo2(self):\n    return eval('1')\n"
        self.assertNotIn("eval", cd.command_payload_source(src))

    def test_unparsable_source_is_returned_as_is(self):
        self.assertEqual(cd.command_payload_source("def (:\n"), "def (:\n")


def _bundle(src):
    """Run the trimmed copy the way a bundle does: only maya_command injected,
    no inherited __future__ flags."""
    ns = {"maya_command": maya_command}
    exec(compile(cd.command_payload_source(src), "<methods>", "exec",
                 dont_inherit=True), ns)
    return ns


class TestCodeThatRunsAtLoad(unittest.TestCase):
    """What a module-level statement DOES cannot be traced by name, so any
    statement that runs code while the namespace is built ships."""

    def test_a_loop_that_fills_a_table_ships(self):
        src = ("_T = {}\nfor _k in range(3):\n    _T[_k] = _k * 2\n\n\n"
               "@maya_command\ndef poke(self):\n    return _T[2]\n")
        self.assertEqual(_bundle(src)["poke"](None), 4)

    def test_a_registering_decorator_ships(self):
        src = ("_H = {}\n\n\ndef handler(k):\n    def deco(fn):\n"
               "        _H[k] = fn\n        return fn\n    return deco\n\n\n"
               "@handler('a')\ndef _do_a(x):\n    return 2 * x\n\n\n"
               "@maya_command\ndef poke(self):\n    return _H['a'](1)\n")
        self.assertEqual(_bundle(src)["poke"](None), 2)

    def test_a_bare_comprehension_ships(self):
        src = ("_T = {}\n[_T.setdefault(k, k * 2) for k in (1, 2, 3)]\n\n\n"
               "@maya_command\ndef poke(self):\n    return len(_T)\n")
        self.assertEqual(_bundle(src)["poke"](None), 3)

    def test_a_star_import_ships(self):
        src = ("from math import *\n\n\n"
               "@maya_command\ndef poke(self):\n    return sqrt(4.0)\n")
        self.assertEqual(_bundle(src)["poke"](None), 2.0)

    def test_a_plain_import_or_constant_nobody_reads_is_dropped(self):
        src = ("import json\n_UNUSED = (1, 2)\n\n\n"
               "@maya_command\ndef poke(self):\n    return 1\n")
        out = cd.command_payload_source(src)
        self.assertNotIn("json", out)
        self.assertNotIn("_UNUSED", out)


class TestSharedLines(unittest.TestCase):

    def test_a_shared_line_brings_what_its_other_statements_read(self):
        src = ("_SEED = 7\n_A = _SEED; _B = 2\n\n\n"
               "@maya_command\ndef poke(self):\n    return _B\n")
        self.assertEqual(_bundle(src)["poke"](None), 2)

    def test_the_mpynode_gate_sees_a_shared_line(self):
        from mpynode.native.compiler.errors import UnsupportedSpec

        src = ("import mpynode; _SCALE = 2.0\n\n\n"
               "@maya_command\ndef poke(self):\n    return _SCALE\n")
        self.assertTrue(cd.payload_mpynode_imports(src))
        with self.assertRaises(UnsupportedSpec):
            cd.emit_dispatch_commands(detect_commands(src), "pokeType", src)


class TestLineBreaks(unittest.TestCase):

    def test_characters_str_splitlines_breaks_on_do_not_shift_the_cut(self):
        for odd in ("\x0c", " ", "\x85"):
            src = ("@maya_command\ndef poke(self):\n    return _helper(4.0)\n\n\n"
                   "def _helper(v):\n    return v * 2  # note %s here\n" % odd)
            self.assertEqual(_bundle(src)["poke"](None), 8.0, repr(odd))


class TestNoFalseRefusals(unittest.TestCase):
    """Code that cannot read module names by name is not refused."""

    def _ok(self, body):
        src = "import json\nimport math\n\n\n@maya_command\ndef poke(self, n=2):\n" + body
        self.assertIn("poke", _bundle(src))
        cd.python_module_source("pokeType", src, detect_commands(src))

    def test_a_local_named_like_a_test_helper(self):
        self._ok("    max_abs_diff = 0.5 * n\n    return max_abs_diff\n")

    def test_a_parameter_named_like_a_test_helper(self):
        src = "@maya_command\ndef poke(self, assert_true=False):\n    return assert_true\n"
        cd.python_module_source("pokeType", src, detect_commands(src))

    def test_vars_of_an_object_locals_in_a_def_and_import_calls(self):
        self._ok("    a = sorted(vars(math))\n    b = locals()\n"
                 "    c = __import__('json')\n    return a, b, c\n")

    def test_eval_with_its_own_globals(self):
        self._ok("    return eval('n + 1', {'__builtins__': {}}, {'n': n})\n")

    def test_a_local_named_like_a_demo_does_not_ship_the_demo(self):
        src = ("@maya_command\ndef poke(self):\n    demo = 3\n    return demo\n\n\n"
               "@maya_demo\ndef demo(self):\n    import mpynode\n")
        self.assertNotIn("import mpynode", cd.command_payload_source(src))
        cd.python_module_source("pokeType", src, detect_commands(src))

    def test_still_refused(self):
        for body in ("    return globals()['x']\n", "    return eval('x')\n"):
            src = "@maya_command\ndef poke(self):\n" + body
            with self.assertRaises(ValueError, msg=body):
                cd.command_payload_source(src)
        with self.assertRaises(ValueError):
            cd.command_payload_source("_S = locals()\n\n\n"
                                      "@maya_command\ndef poke(self):\n    return 1\n")


class TestGeneratedModule(unittest.TestCase):

    def _module(self, src):
        cmds = detect_commands(src)
        return cd.python_module_source("payloadType", src, cmds)

    def _exec(self, module_src):
        """Exec the generated dispatch module with maya stubbed."""
        maya      = types.ModuleType("maya")
        maya.cmds = types.ModuleType("maya.cmds")
        saved     = {k: sys.modules.get(k) for k in ("maya", "maya.cmds")}
        sys.modules.update({"maya": maya, "maya.cmds": maya.cmds})
        try:
            ns = {"__name__": "mpynode_cmd_payloadType"}
            exec(compile(module_src, "<bundle>", "exec", dont_inherit=True), ns)
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
        return ns

    def test_the_module_embeds_the_trimmed_source(self):
        ns = self._exec(self._module(SRC))
        self.assertEqual(ns["_METHODS_SRC"], cd.command_payload_source(SRC))

    def test_every_command_binds_in_the_bundle_namespace(self):
        ns     = self._exec(self._module(SRC))
        bundle = ns["build_methods_namespace"](ns["_METHODS_SRC"])
        for func in set(ns["_FUNCS"].values()):
            self.assertTrue(callable(bundle.get(func)), func)

    def test_the_prelude_carries_no_test_kit(self):
        tree  = ast.parse(self._module(SRC))
        names = {n.name for n in tree.body if hasattr(n, "name")}
        names |= {t.id for n in tree.body if isinstance(n, ast.Assign)
                  for t in n.targets if isinstance(t, ast.Name)}
        self.assertEqual(names & cd._test_kit_names(), set())

    def test_command_code_reading_the_test_kit_is_refused(self):
        src = ("@maya_command\ndef poke(self):\n"
               "    assert_close(1.0, 1.0)\n")
        with self.assertRaises(ValueError) as ctx:
            self._module(src)
        self.assertIn("assert_close", str(ctx.exception))

    def test_the_emit_fails_by_node_name(self):
        from mpynode.native.compiler.errors import UnsupportedSpec

        src = ("@maya_command\ndef poke(self):\n"
               "    return eval('1')\n")
        with self.assertRaises(UnsupportedSpec) as ctx:
            cd.emit_dispatch_commands(detect_commands(src), "evalType", src)
        self.assertIn("evalType", str(ctx.exception))


class TestCacheKey(unittest.TestCase):

    def _spec(self, methods):
        return {"compute": "x = 1", "inputs": {}, "outputs": {},
                "methods": methods, "commands": detect_commands(methods)}

    def _key(self, spec):
        from mpynode.native.toolchain import port_cache

        return port_cache.cache_key(spec, provider="p", model="m")

    def test_a_demo_edit_keeps_the_key(self):
        edited = SRC.replace("return _demo_positions(), _shared()", "return 0")
        self.assertEqual(self._key(self._spec(SRC)), self._key(self._spec(edited)))

    def test_a_demo_edit_above_a_command_keeps_the_key(self):
        """It moves the command's line number, which codegen never reads."""
        edited = SRC.replace("def _demo_positions():\n",
                             "def _demo_positions():\n    # one more line\n")
        self.assertNotEqual(detect_commands(edited)[0]["lineno"],
                            detect_commands(SRC)[0]["lineno"])
        self.assertEqual(self._key(self._spec(SRC)), self._key(self._spec(edited)))

    def test_a_command_edit_moves_the_key(self):
        edited = SRC.replace("_helper(value) + _shared()", "_helper(value)")
        self.assertNotEqual(self._key(self._spec(SRC)),
                            self._key(self._spec(edited)))

    def test_the_spec_keeps_its_whole_methods(self):
        """verify reads the @maya_test bodies from spec["methods"]."""
        spec   = self._spec(SRC)
        before = copy.deepcopy(spec)
        self._key(spec)
        cd.dispatch_for_spec(spec, "payloadType")
        self.assertEqual(spec, before)


if __name__ == "__main__":
    unittest.main()
