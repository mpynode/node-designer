"""@maya_test -- node validation / parity decorator (Feature C, Phase 1).

Covers the pure layers (static detection, discovery, outline, assert helpers --
no Maya) and the Maya-dependent runner (run a node's @maya_test bound to the
instance; PASS returns normally, FAIL raises).
"""

from __future__ import annotations

import os
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

import maya.cmds as mc

from tests._setup import ensure_plugins_loaded, standalone_init


def setUpModule():
    standalone_init()
    ensure_plugins_loaded()


# ---------------------------------------------------------------------------
# Pure: detect_tests (static AST)
# ---------------------------------------------------------------------------
class TestDetectTests(unittest.TestCase):
    def test_bare_and_parameterized(self):
        from mpynode._common.methods.maya_command import detect_tests

        src = (
            "@maya_test\n"
            "def test_a(self):\n"
            "    pass\n"
            "\n"
            "@maya_test(label='UV move', digits=3)\n"
            "def test_b(self):\n"
            "    pass\n"
        )
        tests = detect_tests(src)
        self.assertEqual(len(tests), 2)
        a, b = tests
        self.assertEqual(a["func_name"], "test_a")
        self.assertEqual(a["label"], "Test A")   # humanized
        self.assertIsNone(a["digits"])
        self.assertTrue(a["is_instance"])
        self.assertEqual(b["func_name"], "test_b")
        self.assertEqual(b["label"], "UV move")
        self.assertEqual(b["digits"], 3)

    def test_positional_label(self):
        from mpynode._common.methods.maya_command import detect_tests

        tests = detect_tests(
            "@maya_test('the label')\ndef test_x(self):\n    pass\n")
        self.assertEqual(tests[0]["label"], "the label")

    def test_non_literal_digits_warns_and_falls_back(self):
        from mpynode._common.methods.maya_command import detect_tests

        src = ("D = 3\n"
               "@maya_test(digits=D)\n"
               "def test_x(self):\n    pass\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            tests = detect_tests(src)
        self.assertIsNone(tests[0]["digits"])
        self.assertTrue(any("digits" in str(x.message) for x in w))

    def test_bool_is_not_int_digits(self):
        # bool is an int subclass; digits=True must NOT be read as 1.
        from mpynode._common.methods.maya_command import detect_tests

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            tests = detect_tests(
                "@maya_test(digits=True)\ndef test_x(self):\n    pass\n")
        self.assertIsNone(tests[0]["digits"])

    def test_async_warns(self):
        from mpynode._common.methods.maya_command import detect_tests

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            tests = detect_tests(
                "@maya_test\nasync def test_x(self):\n    pass\n")
        self.assertEqual(tests, [])
        self.assertTrue(any("async" in str(x.message) for x in w))

    def test_syntax_error_is_empty(self):
        from mpynode._common.methods.maya_command import detect_tests

        self.assertEqual(detect_tests("def (:\n"), [])

    def test_marker_is_side_effect_free(self):
        from mpynode._common.methods.maya_command import maya_test

        @maya_test(label="L", digits=2)
        def f(self):
            return 42

        self.assertEqual(f.__maya_test__, {"label": "L", "digits": 2})
        self.assertEqual(f(None), 42)  # unchanged at runtime

        @maya_test
        def g(self):
            return 7

        self.assertEqual(g.__maya_test__, {"label": None, "digits": None})
        self.assertEqual(g(None), 7)


# ---------------------------------------------------------------------------
# Pure: find_tests / select_test / has_test_source
# ---------------------------------------------------------------------------
class TestFindTests(unittest.TestCase):
    _SRC = (
        "@maya_test(label='first')\n"
        "def test_one(self):\n    pass\n"
        "\n"
        "@maya_test\n"
        "def test_two(self):\n    pass\n"
    )

    def test_find_and_labels(self):
        from mpynode._common import node_setups

        specs = node_setups.find_tests(self._SRC)
        self.assertEqual([s.func_name for s in specs], ["test_one", "test_two"])
        self.assertEqual(node_setups.test_labels(self._SRC),
                         ["first", "Test Two"])
        self.assertTrue(node_setups.has_test_source(self._SRC))
        self.assertFalse(node_setups.has_test_source("def plain():\n    pass\n"))

    def test_select(self):
        from mpynode._common import node_setups

        specs = node_setups.find_tests(self._SRC)
        self.assertEqual(node_setups.select_test(specs).func_name, "test_one")
        self.assertEqual(
            node_setups.select_test(specs, "test_two").func_name, "test_two")
        self.assertEqual(
            node_setups.select_test(specs, "first").func_name, "test_one")
        self.assertIsNone(node_setups.select_test(specs, "nope"))
        self.assertIsNone(node_setups.select_test([]))


# ---------------------------------------------------------------------------
# Pure: outline "Test" group
# ---------------------------------------------------------------------------
class TestOutlineGroup(unittest.TestCase):
    def test_test_group_present_and_labeled(self):
        from mpynode._common.methods.outline_model import (
            OUTLINE_GROUPS, GROUP_LABELS, build_outline)

        self.assertIn("Test", OUTLINE_GROUPS)
        self.assertEqual(GROUP_LABELS["Test"], "Tests")
        # Every group has a label (coverage invariant the UI relies on).
        for g in OUTLINE_GROUPS:
            self.assertIn(g, GROUP_LABELS)

    def test_test_def_lands_in_test_group_not_instance(self):
        from mpynode._common.methods.outline_model import build_outline

        items = build_outline(
            "@maya_test(label='Lbl')\ndef test_x(self):\n    pass\n")
        test_items = [it for it in items if it.kind == "Test"]
        self.assertEqual(len(test_items), 1)
        it = test_items[0]
        self.assertEqual(it.name, "Lbl")
        self.assertTrue(it.runnable)
        self.assertEqual(it.run_kind, "test")
        self.assertEqual(it.command_name, "test_x")
        # not double-counted as an Instance method
        self.assertFalse([i for i in items if i.kind == "Instance"])


# ---------------------------------------------------------------------------
# Pure: assert helpers + tolerance scoping
# ---------------------------------------------------------------------------
class TestAssertHelpers(unittest.TestCase):
    def test_assert_close_scalar_and_seq(self):
        from mpynode._common.methods import test_helpers as th

        th.assert_close(1.00001, 1.0, digits=3)          # within
        th.assert_close([1.0, 2.0], [1.0004, 2.0004], digits=3)
        with self.assertRaises(th.TestFailure):
            th.assert_close(1.01, 1.0, digits=3)         # outside
        with self.assertRaises(th.TestFailure):
            th.assert_close([1.0, 2.0], [1.0], digits=3)  # length mismatch

    def test_assert_equal_and_true(self):
        from mpynode._common.methods import test_helpers as th

        th.assert_equal(6, 6)
        th.assert_true(1 < 2)
        with self.assertRaises(th.TestFailure):
            th.assert_equal(6, 7)
        with self.assertRaises(th.TestFailure):
            th.assert_true(False)

    def test_default_digits_scope(self):
        from mpynode._common.methods import test_helpers as th

        self.assertEqual(th.default_digits(), 4)          # fallback
        prev = th.set_default_digits(2)
        try:
            th.assert_close(1.004, 1.0)                    # ok at 2 digits
            with self.assertRaises(th.TestFailure):
                th.assert_close(1.02, 1.0)
        finally:
            th.set_default_digits(prev)
        self.assertEqual(th.default_digits(), 4)           # restored

    def test_namespace_injects_markers_and_helpers(self):
        from mpynode._common.methods.methods_registry import (
            build_methods_namespace)

        ns = build_methods_namespace("X = 1\n")
        for name in ("maya_command", "maya_demo", "maya_test",
                     "assert_close", "assert_equal", "assert_true"):
            self.assertIn(name, ns)


# ---------------------------------------------------------------------------
# Maya: run_node_test / run_tests on a live node
# ---------------------------------------------------------------------------
class TestRunNodeTest(unittest.TestCase):
    def _loc(self):
        from mpynode.wrappers.mpy_locator import MPyLocator

        mc.file(new=True, force=True)
        return MPyLocator.create(name="testHost")

    def test_pass_and_fail(self):
        loc = self._loc()
        loc.set_methods_source(
            "@maya_test(label='passes')\n"
            "def test_ok(self):\n"
            "    assert_close(2.0, 2.00001, digits=3)\n"
            "\n"
            "@maya_test(digits=3)\n"
            "def test_bad(self):\n"
            "    assert_close(2.0, 3.0)\n"
        )
        ok = loc.run_test("test_ok")
        self.assertTrue(ok["passed"], ok)
        self.assertEqual(ok["label"], "passes")

        bad = loc.run_test("test_bad")
        self.assertFalse(bad["passed"])
        self.assertIn("decimal places", bad["error"])

    def test_run_all_and_list(self):
        loc = self._loc()
        loc.set_methods_source(
            "@maya_test\n"
            "def test_a(self):\n    assert_true(True)\n"
            "\n"
            "@maya_test\n"
            "def test_b(self):\n    assert_true(False)\n"
        )
        results = loc.run_tests()
        self.assertEqual([r["name"] for r in results], ["test_a", "test_b"])
        self.assertTrue(results[0]["passed"])
        self.assertFalse(results[1]["passed"])
        self.assertEqual(len(loc.list_tests()), 2)

    def test_decorator_digits_scopes_assert_close(self):
        # A bare assert_close inside a @maya_test(digits=2) uses 2 places.
        loc = self._loc()
        loc.set_methods_source(
            "@maya_test(digits=2)\n"
            "def test_loose(self):\n"
            "    assert_close(1.0, 1.004)\n"   # ok at 2, would fail at 4
        )
        self.assertTrue(loc.run_test()["passed"])

    def test_missing_test_raises_setuperror(self):
        from mpynode._common.methods import setup_helpers as node_setup

        loc = self._loc()
        loc.set_methods_source("def plain(self):\n    return 1\n")
        with self.assertRaises(node_setup.SetupError):
            loc.run_test()

    def test_exception_in_test_is_a_fail_not_a_raise(self):
        loc = self._loc()
        loc.set_methods_source(
            "@maya_test\n"
            "def test_boom(self):\n    raise ValueError('kaboom')\n"
        )
        res = loc.run_test()
        self.assertFalse(res["passed"])
        self.assertIn("kaboom", res["error"])

    def test_run_test_command_stashes_result_and_returns_verdict(self):
        from mpynode._base.commands import run_undoable, _RunTestCommand

        loc = self._loc()
        loc.set_methods_source(
            "@maya_test(label='ok')\n"
            "def test_ok(self):\n    assert_true(True)\n"
            "\n"
            "@maya_test(label='no')\n"
            "def test_no(self):\n    assert_true(False)\n"
        )
        cmd = _RunTestCommand(loc.get_name(), loc.NATIVE_TYPE, "test_ok")
        verdict = run_undoable(cmd)
        self.assertEqual(verdict, "PASS")
        self.assertTrue(cmd.test_result["passed"])

        cmd2 = _RunTestCommand(loc.get_name(), loc.NATIVE_TYPE, "test_no")
        self.assertEqual(run_undoable(cmd2), "FAIL")
        self.assertFalse(cmd2.test_result["passed"])

    def test_run_test_on_node_name_with_explicit_source(self):
        # the parity-harness entry: run a @maya_test from explicit source
        # against a bare node NAME, with no _methodsSource plug.
        from mpynode._common.methods import methods_registry

        loc = self._loc()
        src = (
            "@maya_test\n"
            "def test_named(self):\n"
            "    assert_true(self.get_name() == '%s')\n" % loc.get_name()
        )
        res = methods_registry.run_test_on_node_name(loc.get_name(), src)
        self.assertTrue(res["passed"], res)
        self.assertEqual(res["name"], "test_named")


class TestMergeAuthoredTest(unittest.TestCase):
    """Pure verify-harness merge logic (no Maya)."""

    def test_merge_semantics(self):
        from mpynode.native.toolchain.verify import _merge_authored_test

        good = {"ran": True, "passed": True, "count": 2, "passes": 2,
                "reason": ""}
        bad = {"ran": True, "passed": False, "count": 2, "passes": 1,
               "reason": "t2: boom"}

        # generic SKIP + authored PASS -> becomes a real pass
        m = _merge_authored_test(
            {"ran": False, "pass": None, "maxerr": None, "tol": None,
             "reason": ""}, good)
        self.assertTrue(m["ran"])
        self.assertTrue(m["pass"])
        self.assertEqual(m["authored_test"], good)

        # generic PASS + authored PASS -> stays pass
        m = _merge_authored_test(
            {"ran": True, "pass": True, "maxerr": 0.0, "tol": 1e-4,
             "reason": ""}, good)
        self.assertTrue(m["pass"])

        # generic PASS + authored FAIL -> flips to fail, reason carries it
        m = _merge_authored_test(
            {"ran": True, "pass": True, "maxerr": 0.0, "tol": 1e-4,
             "reason": ""}, bad)
        self.assertFalse(m["pass"])
        self.assertIn("authored @maya_test FAILED", m["reason"])

        # generic FAIL + authored PASS -> stays fail (both must pass)
        m = _merge_authored_test(
            {"ran": True, "pass": False, "maxerr": 9.9, "tol": 1e-4,
             "reason": "topo"}, good)
        self.assertFalse(m["pass"])


if __name__ == "__main__":
    unittest.main()
