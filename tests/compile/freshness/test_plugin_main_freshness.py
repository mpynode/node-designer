"""Every committed ``build/source/plugin_main.cpp`` must equal what
``bundler.make_plugin_main`` emits for the fragments beside it.

``plugin_main.cpp`` is codegen, like the build scripts
``test_build_script_freshness`` gates, and it had no gate: the entry point
grew a session pre-check and rollback (a failed mPyMega load used to leave
orphan node types behind, and ``createNode`` on one crashed Maya), and without
this the shipped All Templates Plugin would have kept the old one with nothing
going red. ``tools/regen_plugin_main.py`` does the deriving; this is the gate
over its result.

WHY NO BASELINE. The tree is fully fresh as of the change that added the tool,
so this is an equality, not a ratchet: any drift fails with a one-line fix
(re-run the tool).
"""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest

from tests import _paths

_ROOT = _paths.ROOT
_TOOL = os.path.join(_ROOT, "tools", "regen_plugin_main.py")
_MEGA = "templates/All Templates Plugin/build/source/plugin_main.cpp"

_RESULT = None


def setUpModule():
    global _RESULT
    spec = importlib.util.spec_from_file_location("regen_plugin_main", _TOOL)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = os.path.join(tempfile.mkdtemp(prefix="pm_fresh_"), "result.json")
    rc  = mod.main(["--json", out])
    with open(out, encoding="utf-8") as fh:
        _RESULT = json.load(fh)
    _RESULT["rc"] = rc


class TestPluginMainFreshness(unittest.TestCase):

    def test_the_tool_read_every_fragment(self):
        self.assertEqual(_RESULT["broken"], [],
                         "fragments the regenerator could not parse -- fix "
                         "bundler.fragment_info rather than tolerating the hole")

    def test_the_mega_entry_point_is_covered(self):
        # Floor, not an equality: a path rename must not turn this into a
        # no-op that passes on an empty measurement.
        self.assertIn(_MEGA, _RESULT["fresh"] + _RESULT["stale"])

    def test_every_committed_entry_point_matches_todays_generator(self):
        self.assertEqual(
            _RESULT["stale"], [],
            "stale plugin_main.cpp -- regenerate with:\n"
            "  mayapy tools/regen_plugin_main.py")
        self.assertEqual(_RESULT["rc"], 0)


if __name__ == "__main__":
    unittest.main()
