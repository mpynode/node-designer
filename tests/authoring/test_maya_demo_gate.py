"""Static detection coverage for the @maya_demo marker + detect_demos.

Maya-free (ast/warnings only), mirrors test_maya_command_gate. detect_demos must
behave like detect_commands but keyed on the maya_demo marker + a `label=` kwarg.
"""
import unittest
import warnings

from mpynode._common.methods.maya_command import maya_demo, detect_demos


class TestMayaDemoMarker(unittest.TestCase):
    def test_bare_marker_records_metadata_and_returns_fn(self):
        @maya_demo
        def d(self):
            return 1
        self.assertEqual(d.__maya_demo__, {"label": None})
        self.assertTrue(callable(d))

    def test_parameterized_marker_records_label(self):
        @maya_demo(label="Igloo (SDF)")
        def d(self):
            return 1
        self.assertEqual(d.__maya_demo__, {"label": "Igloo (SDF)"})


class TestDetectDemos(unittest.TestCase):
    def test_empty_and_syntax_error_yield_empty(self):
        for bad in (None, "", "   ", "def (:\n"):
            self.assertEqual(detect_demos(bad), [])

    def test_decorated_instance_demo(self):
        src = "@maya_demo\ndef show(self):\n    return 1\n"
        got = detect_demos(src)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["func_name"], "show")
        self.assertTrue(got[0]["is_instance"])
        self.assertFalse(got[0]["is_factory"])
        self.assertEqual(got[0]["label"], "Show")

    def test_decorated_factory_demo_classmethod(self):
        src = "@maya_demo(label='Build It')\n@classmethod\ndef make(cls):\n    return 1\n"
        got = detect_demos(src)
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["is_factory"])
        self.assertEqual(got[0]["label"], "Build It")

    def test_cls_first_without_decorator_is_factory(self):
        src = "@maya_demo\ndef make(cls):\n    return 1\n"
        self.assertTrue(detect_demos(src)[0]["is_factory"])

    def test_multiple_demos_in_source_order(self):
        src = ("@maya_demo(label='A')\ndef a(self):\n    return 1\n"
               "@maya_demo(label='B')\ndef b(self):\n    return 2\n")
        got = detect_demos(src)
        self.assertEqual([g["func_name"] for g in got], ["a", "b"])
        self.assertEqual([g["label"] for g in got], ["A", "B"])

    def test_demo_named_demo_gets_run_demo_label(self):
        src = "@maya_demo\ndef demo(self):\n    return 1\n"
        self.assertEqual(detect_demos(src)[0]["label"], "Run demo")

    def test_undecorated_defs_ignored(self):
        src = "def plain(self):\n    return 1\n"
        self.assertEqual(detect_demos(src), [])

    def test_non_literal_label_warns_and_falls_back(self):
        src = "PFX='x'\n@maya_demo(label=PFX)\ndef show(self):\n    return 1\n"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            got = detect_demos(src)
        self.assertEqual(got[0]["label"], "Show")
        self.assertTrue(any("not a string literal" in str(x.message) for x in w))

    def test_async_marked_demo_warns_and_dropped(self):
        src = "@maya_demo\nasync def show(self):\n    return 1\n"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            got = detect_demos(src)
        self.assertEqual(got, [])
        self.assertTrue(any("async" in str(x.message) for x in w))

    def test_aliased_marker_warns(self):
        src = ("from mpynode._common.methods.maya_command import maya_demo as md\n"
               "@md\ndef show(self):\n    return 1\n")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            got = detect_demos(src)
        self.assertEqual(got, [])
        self.assertTrue(any("aliased" in str(x.message) for x in w))


class TestDetectCommandsUnaffected(unittest.TestCase):
    def test_detect_commands_still_finds_maya_command(self):
        from mpynode._common.methods.maya_command import detect_commands
        src = "@maya_command(name='doIt')\ndef run(self):\n    return 1\n"
        got = detect_commands(src)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["name"], "doIt")


if __name__ == "__main__":
    unittest.main()
