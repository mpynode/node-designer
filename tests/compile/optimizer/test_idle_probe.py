"""tools/harness/idle_probe.py measures a scene's idle load (redraws/s, main-
thread CPU %) with N locators present, inside a live Maya session -- the
measurement that found the 30 fps idle-refresh timer holding the main thread at
98% and drove the CPU-metered throttle. Its Maya-free helpers are pinned here
without a session."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

from tests import _paths

_TOOL = os.path.join(_paths.ROOT, "tools", "harness", "idle_probe.py")


def _tool():
    spec = importlib.util.spec_from_file_location("idle_probe", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestClocks(unittest.TestCase):
    def test_thread_cpu_clock_is_real_on_windows(self):
        t = _tool()
        a = t.main_thread_cpu_s()
        if sys.platform != "win32":
            self.assertIsNone(a)
            return
        self.assertIsInstance(a, float)
        sum(i * i for i in range(300_000))                 # burn a little CPU
        self.assertGreaterEqual(t.main_thread_cpu_s(), a)

    def test_process_cpu_clock(self):
        t = _tool()
        self.assertIsInstance(t.process_cpu_s(), float)


class TestTable(unittest.TestCase):
    def test_one_row_per_window_with_dashes_for_unmeasured(self):
        t = _tool()
        md = t.format_table([
            {"config": "cpp", "copies": 10, "sweep": False, "wall_s": 10.0, "redraws": 200,
             "redraws_per_s": 20.0, "ms_per_redraw": 1.5, "main_cpu_pct": 23.0, "proc_cpu_pct": 31.0},
            {"config": "cpp", "copies": 0, "sweep": True, "wall_s": 10.0, "redraws": 0,
             "redraws_per_s": 0.0, "ms_per_redraw": None, "main_cpu_pct": None, "proc_cpu_pct": 1.0},
        ])
        lines = md.splitlines()
        self.assertTrue(lines[0].startswith("| config | copies | sweep |"))
        self.assertIn("| cpp | 10 | no | 10.0 | 200 | 20.0 | 1.50 | 23 | 31 |", lines)
        self.assertIn("| cpp | 0 | yes | 10.0 | 0 | 0.0 | - | - | 1 |", lines)


class TestConfigs(unittest.TestCase):
    """Every config is a dict the Probe drives the same way: label, scene(cmds),
    make(cmds, n), copies, sweep, grid."""

    KEYS = {"label", "scene", "make", "copies", "sweep", "grid"}

    def test_compiled_config_shape(self):
        t = _tool()
        c = t.compiled_config("cpp", "animatedText", plugin="x.mll", copies=(0, 5))
        self.assertEqual(set(c), self.KEYS)
        self.assertEqual((c["label"], c["copies"], c["sweep"], c["grid"]), ("cpp", [0, 5], False, True))
        self.assertTrue(callable(c["scene"]) and callable(c["make"]))

    def test_interpreted_and_mesh_regions_configs(self):
        t = _tool()
        i = t.interpreted_config("py", "t.mpn", patch=t.static_patch)
        m = t.mesh_regions_config("mr", "t.mpn", "head.ma", sweep=True)
        cm = t.compiled_mesh_regions_config("cmr", "meshRegionLocator", "x.mll", "head.ma")
        for c in (i, m, cm):
            self.assertEqual(set(c), self.KEYS)
        self.assertEqual(i["copies"], [0, 10, 100])
        self.assertTrue(i["grid"], "free-standing gizmos are spread on a grid")
        self.assertFalse(m["grid"], "region gizmos sit on the head, not on a grid")
        self.assertTrue(m["sweep"])
        self.assertFalse(cm["grid"])

    def test_static_patch_turns_the_idle_refresh_request_off(self):
        t = _tool()
        expr = "self.auto_refresh = True\nself.draw = None\n"
        self.assertIn("self.auto_refresh = False", t.static_patch(expr))
        self.assertNotIn("self.auto_refresh = True", t.static_patch(expr))
        self.assertEqual(t.static_patch("x = 1\n"), "x = 1\n")

    def test_model_panel_lookup_reports_a_missing_viewport(self):
        t = _tool()

        class _Cmds:
            @staticmethod
            def playblast(**_kw):
                return ""

            @staticmethod
            def getPanel(**_kw):
                return []

        with self.assertRaises(RuntimeError):
            t._model_panel(_Cmds)


if __name__ == "__main__":
    unittest.main()
