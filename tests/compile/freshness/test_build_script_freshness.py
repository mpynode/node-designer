# tests/compile/freshness/test_build_script_freshness.py
"""Every committed build.sh / build.bat must equal what the generators emit.

The build scripts are codegen, exactly like ``1_transpiled.cpp``, and they had
no gate: a change to ``bundler.make_*_build_*`` or
``build_scripts.generate_build_*`` left 120 checked-in scripts describing the
previous recipe, and nothing went red. This is the same ratchet
``test_stage1_codegen_freshness`` puts over stage-1 artifacts, applied to the
scripts. ``tools/regen_build_scripts.py`` does the deriving; this module is the
gate over its result.

WHY NO BASELINE. Unlike stage-1, the tree is fully fresh as of the version-
argument change, so this gate starts green and stays an equality, not a
ratchet. Any drift is a hard failure with a one-line fix (re-run the tool).

WHY ORPHANS ARE PINNED. One script has no manifest row behind it -- a scratch
dir left by a node rename -- so nothing can regenerate it. Tolerating "some
unowned scripts" would let a future rename quietly park more stale codegen in
the tree, so the set is pinned by exact path: a new orphan fails here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from tests import _paths

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = _paths.ROOT
_TOOL = os.path.join(_ROOT, "tools", "regen_build_scripts.py")

# Measured 2026-08-29: 40 build trees, 119 regenerable scripts. Floors, not
# equalities -- a path rename or a manifest-shape change must not turn this
# suite into a no-op that passes on an empty measurement.
_MIN_TREES = 35
_MIN_SCRIPTS = 110

# The one script no manifest row accounts for: `meshRegions/` is the scratch dir
# of a node that was renamed to `meshRegionLocator`, and the plugin links only
# the latter (see the tree's own build.sh).
_KNOWN_ORPHANS = [
    "compiled_templates/MPyLocator/Mesh Regions/build/meshRegions/build.sh",
]

_RESULT = None


def _mayapy():
    """The interpreter for the child -- mayapy, never the Maya GUI binary.

    Under the headless runner ``sys.executable`` IS mayapy. Inside a GUI session
    it is ``Maya`` itself, and handing that a script path opens a whole second
    Maya, so look for mayapy beside it and in the sibling ``bin/`` first.
    """
    here = os.path.dirname(sys.executable)
    for cand in (os.path.join(here, "mayapy"),
                 os.path.join(os.path.dirname(here), "bin", "mayapy")):
        if os.path.isfile(cand):
            return cand
    return sys.executable


def _measure():
    out = os.path.join(tempfile.mkdtemp(prefix="mpynode-buildsh-"),
                       "freshness.json")
    proc = subprocess.run([_mayapy(), _TOOL, "--json", out],
                          capture_output=True, text=True)
    if proc.returncode != 0 or not os.path.isfile(out):
        raise AssertionError(
            "tools/regen_build_scripts.py failed (rc=%d):\n%s\n%s"
            % (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:]))
    with open(out) as fh:
        return json.load(fh)


def setUpModule():
    global _RESULT
    _RESULT = _measure()
    sys.stderr.write(
        "[build-script freshness] %d trees / %d fresh / %d stale / "
        "%d not-regenerable / %d orphan\n"
        % (_RESULT["trees"], len(_RESULT["fresh"]), len(_RESULT["stale"]),
           _RESULT["not_regenerable"], len(_RESULT["orphans"])))


class TestBuildScriptMeasurementIsReal(unittest.TestCase):
    """Guards the gate itself -- everything below is vacuous without these."""

    def test_enough_scripts_were_actually_compared(self):
        self.assertGreaterEqual(
            _RESULT["trees"], _MIN_TREES,
            "found %d build trees; the walk in regen_build_scripts.py stopped "
            "seeing them" % _RESULT["trees"])
        n = len(_RESULT["fresh"]) + len(_RESULT["stale"])
        self.assertGreaterEqual(
            n, _MIN_SCRIPTS,
            "compared %d build scripts; the rest of this suite would pass on "
            "an empty measurement" % n)

    def test_no_tree_silently_dropped_out_of_the_comparison(self):
        self.assertEqual(
            _RESULT["not_regenerable"], 0,
            "%d build trees produced no comparison at all. A tree that cannot "
            "be regenerated is ungated -- fix the derivation in "
            "tools/regen_build_scripts.py rather than tolerating the hole."
            % _RESULT["not_regenerable"])


class TestCommittedBuildScriptsAreFresh(unittest.TestCase):

    def test_every_committed_script_matches_todays_generator(self):
        stale = _RESULT["stale"]
        self.assertEqual(
            stale, [],
            "%d committed build script(s) no longer match the generators:\n"
            "  %s\n\nRefresh them with:\n"
            "  mayapy tools/regen_build_scripts.py"
            % (len(stale), "\n  ".join(stale[:20])))

    def test_the_unowned_script_set_has_not_grown(self):
        self.assertEqual(
            sorted(_RESULT["orphans"]), sorted(_KNOWN_ORPHANS),
            "the set of build scripts with no manifest row behind them "
            "changed. A new one means codegen is being parked in the tree "
            "where nothing can refresh it -- delete the stale scratch dir, or "
            "add it to _KNOWN_ORPHANS with a reason.")


if __name__ == "__main__":
    unittest.main()
