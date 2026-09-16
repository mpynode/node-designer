"""tools/harness/viewport_bench.py times viewport refresh against N copies of
a node inside a live Maya session -- the only place a locator's draw override
can be measured. Its pure helpers are pinned here without a session."""
from __future__ import annotations

import importlib.util
import os
import unittest

from tests import _paths

_TOOL = os.path.join(_paths.ROOT, "tools", "harness", "viewport_bench.py")


def _tool():
    spec = importlib.util.spec_from_file_location("viewport_bench", _TOOL)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPureHelpers(unittest.TestCase):
    def test_parse_copies(self):
        t = _tool()
        self.assertEqual(t.parse_copies("50, 1,10,10"), [1, 10, 50])
        self.assertEqual(t.parse_copies((100, 1)), [1, 100])
        with self.assertRaises(ValueError):
            t.parse_copies("0,-3")

    def test_grid_is_square_centred_and_spread(self):
        t   = _tool()
        pts = t.grid_positions(9, spacing=2.0)
        self.assertEqual(len(pts), 9)
        self.assertEqual(len(set(pts)), 9)                 # no two copies overlap
        xs = sorted({p[0] for p in pts}); zs = sorted({p[2] for p in pts})
        self.assertEqual(xs, [-2.0, 0.0, 2.0])
        self.assertEqual(zs, [-2.0, 0.0, 2.0])
        self.assertEqual(t.grid_positions(0), [])
        self.assertEqual(len(t.grid_positions(10)), 10)     # 4x4 grid, 10 used

    def test_table_has_one_row_per_measurement(self):
        t = _tool()
        md = t.format_table([{"variant": "interpreted", "copies": 10,
                              "ms_per_refresh": 42.5, "ms_per_copy": 4.25}])
        self.assertIn("| interpreted | 10 | 42.50 | 4.250 |", md)
        self.assertTrue(md.startswith("| variant | copies |"))

    def test_node_name_comes_from_the_wrapper_not_its_repr(self):
        # deserialize_node returns a wrapper whose str() is "<MPyLocator 'x'>";
        # the first release placed by that string and stopped at one locator.
        t = _tool()

        class _Wrapper:
            def get_name(self):
                return "transform2|animatedText"

            def __repr__(self):
                return "<MPyLocator 'animatedText'>"

        self.assertEqual(t._node_name_of(_Wrapper()), "transform2|animatedText")
        self.assertEqual(t._node_name_of("animatedText1"), "animatedText1")
        with self.assertRaises(TypeError):
            t._node_name_of(object())

    def test_refuses_batch(self):
        t = _tool()

        class _Cmds:
            @staticmethod
            def about(batch=False):
                return True

        with self.assertRaises(RuntimeError):
            t._refuse_in_batch(_Cmds)


if __name__ == "__main__":
    unittest.main()
