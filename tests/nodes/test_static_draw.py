"""Which mPyLocator drawings are static (``_common.draw.static_draw``).

A static drawing is built once per change instead of on every viewport
refresh, in the interpreted node and in the compiled one, so a wrong "static"
verdict leaves a gizmo frozen: these tests pin the reads that must keep a
drawing dynamic, the five shipped locator templates' verdicts, and the hover
flag the compiler derives from the same scan.
"""
from __future__ import annotations

import tests  # noqa: F401 -- first: keeps the run out of ~/.mpynode

import os
import unittest

from mpynode._common.draw.static_draw import analyse

_TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "templates", "MPyLocator")

DRAW = "self.draw = DrawCircle(radius=self.size)\n"


def _static(compute, **kwargs):
    kwargs.setdefault("inputs", ("size",))
    return analyse(compute, **kwargs)


class TestReadsThatKeepADrawingDynamic(unittest.TestCase):

    def test_inputs_only_is_static(self):
        a = _static(DRAW)
        self.assertTrue(a.static, a.reasons)
        self.assertEqual(a.draw_mode, "static")
        self.assertFalse(a.needs_hover)

    def test_each_context_read_is_dynamic(self):
        for name in ("time", "wallclock", "hovered", "selected", "is_lead", "selection_color"):
            a = _static("k = self.%s\n%s" % (name, DRAW))
            self.assertFalse(a.static, name)
            self.assertIn("reads self.%s" % name, a.reasons)

    def test_getattr_counts_as_a_read(self):
        a = _static('k = getattr(self, "hovered", False)\n' + DRAW)
        self.assertFalse(a.static)
        self.assertTrue(a.needs_hover)

    def test_auto_refresh_off_stays_static_and_needs_no_hover(self):
        a = _static("self.auto_refresh = False\n" + DRAW)
        self.assertTrue(a.static, a.reasons)
        self.assertFalse(a.needs_hover)
        a = _static("self.auto_refresh = None\n" + DRAW)
        self.assertTrue(a.static, a.reasons)

    def test_auto_refresh_on_is_dynamic_with_hover(self):
        for value in ("True", "0.5", "self.size > 1"):
            a = _static("self.auto_refresh = %s\n%s" % (value, DRAW))
            self.assertFalse(a.static, value)
            self.assertTrue(a.needs_hover, value)

    def test_a_tween_write_is_dynamic(self):
        a = _static('self.anim = getattr(self, "anim", 0.0) + 1.0\n' + DRAW, stored_vars=("anim",))
        self.assertFalse(a.static)
        self.assertTrue(any("writes self.anim" in r for r in a.reasons))

    def test_reading_a_stored_var_is_static(self):
        a = _static('t = self.table\nk = getattr(self, "presets", None)\n' + DRAW,
                    stored_vars=("table", "presets"))
        self.assertTrue(a.static, a.reasons)

    def test_an_unplaced_read_is_dynamic(self):
        a = _static("v = self.visibility\n" + DRAW)
        self.assertFalse(a.static)
        self.assertTrue(any("self.visibility" in r for r in a.reasons))

    def test_init_names_and_methods_are_placed(self):
        a = _static("k = self.TABLE\nm = self.helper(2)\n" + DRAW,
                    init="TABLE = [1, 2]\n", methods="def helper(self, x):\n    return x\n")
        self.assertTrue(a.static, a.reasons)

    def test_volatile_calls(self):
        for code in ("import time\nt = time.time()\n", "import random\nr = random.random()\n",
                     "import numpy as np\nr = np.random.rand(3)\n", "import maya.cmds as cmds\nn = cmds.ls()\n"):
            a = _static(code + DRAW)
            self.assertFalse(a.static, code)

    def test_volatile_calls_in_init_count_only_inside_functions(self):
        once = _static("k = self.T\n" + DRAW, init="import random\nrandom.seed(3)\nT = random.random()\n")
        self.assertTrue(once.static, once.reasons)
        every = _static("k = self.wobble()\n" + DRAW,
                        init="import time\ndef wobble():\n    return time.time()\n")
        self.assertFalse(every.static)

    def test_world_space_items_are_dynamic(self):
        self.assertFalse(_static("self.draw = DrawCurve(self.size, world_space=True)\n").static)
        self.assertTrue(_static("self.draw = DrawCurve(self.size, world_space=False)\n").static)

    def test_text_culling_and_screen_space_need_the_camera(self):
        for code in ('self.draw = DrawText("hi", size=self.size)\n',
                     "self.draw = DrawMesh(self.size, cull_backfaces=True)\n",
                     'self.draw = DrawPoints(self.size, space="screen")\n',
                     'self.draw = DrawCircle(radius=self.size).in_space("screen")\n'):
            a = _static(code)
            self.assertTrue(a.static, (code, a.reasons))
            self.assertTrue(a.view_dependent, code)
            self.assertEqual(a.draw_mode, "dynamic", code)
        a = _static("self.draw = DrawMesh(self.size, cull_backfaces=False)\n")
        self.assertFalse(a.view_dependent)
        self.assertEqual(a.draw_mode, "static")

    def test_a_source_that_does_not_parse_is_dynamic(self):
        a = _static("self.draw = (\n")
        self.assertFalse(a.static)
        self.assertFalse(a.parsed)

    def test_force_dynamic(self):
        a = _static(DRAW, force_dynamic=True)
        self.assertFalse(a.static)
        self.assertEqual(a.draw_mode, "dynamic")

    def test_comments_and_strings_do_not_count(self):
        a = _static("# self.hovered\nnote = 'self.time'\n" + DRAW)
        self.assertTrue(a.static, a.reasons)
        self.assertFalse(a.needs_hover)


class TestShippedLocatorTemplates(unittest.TestCase):
    """The verdicts the plan was written against (control_shapes/docs)."""

    EXPECTED = {
        # name:               (static, draw_mode, needs_hover)
        "Animated Selection": (False, "dynamic", True),
        "Animated Text":      (False, "dynamic", True),
        "Circular Text":      (True, "static", False),
        "Mesh Regions":       (False, "dynamic", True),
        "Widget Showcase":    (True, "dynamic", False),
    }

    def _analyse(self, name):
        from mpynode._common.io import mpn_io

        payload = mpn_io.load_mpn(os.path.join(_TEMPLATES, name, "template.mpn"), trusted=True)
        return analyse(
            payload.get("expression", ""),
            payload.get("init_source", ""),
            payload.get("methods_source", ""),
            inputs      = list(payload.get("input_attrs") or {}),
            stored_vars = list(payload.get("stored_vars") or {}),
        )

    def test_verdicts(self):
        for name, (static, mode, hover) in self.EXPECTED.items():
            with self.subTest(template=name):
                a = self._analyse(name)
                self.assertEqual(a.static, static, a.reasons)
                self.assertEqual(a.draw_mode, mode, a.view_reasons)
                self.assertEqual(a.needs_hover, hover)


if __name__ == "__main__":
    unittest.main()
