#!/usr/bin/env bash
# Run MPyNode unit tests under mayapy 2026 with the standard env.
# Usage:  tools/run_tests.sh tests.nodes.test_draw_types [more modules...]
set -uo pipefail
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$TOOLS_DIR/.."

# Default to the macOS Maya 2026 install; override for another version or
# platform, e.g. MAYAPY=/usr/autodesk/maya2026/bin/mayapy tools/run_tests.sh
MAYAPY="${MAYAPY:-/Applications/Autodesk/maya2026/Maya.app/Contents/bin/mayapy}"
export MPYNODE_USE_STUDIO=1 QT_QPA_PLATFORM=offscreen
export MPYNODE_ROOT="$PWD"
# scipy/PIL live outside Maya on some setups. Point
# MPYNODE_EXTRA_PYTHONPATH at that site-packages dir if you need them.
# It lands on PYTHONPATH, which Python puts AHEAD of Maya's own
# site-packages, so that dir must NOT carry its own numpy: a second numpy
# shadows Maya's 1.26.4 and fails three ndarray tests outright (ptp and
# itemset were removed from ndarray in NumPy 2.0, to_device was added).
# $PWD itself is on the path so the suite imports as `tests.<area>.<module>`.
# Discovery would add it anyway, but naming ONE module on the command line does
# not go through discovery, and without this that form dies on `import tests`.
export PYTHONPATH="$PWD/scripts:$PWD${MPYNODE_EXTRA_PYTHONPATH:+:$MPYNODE_EXTRA_PYTHONPATH}"
export MAYA_PLUG_IN_PATH="$PWD/plug-ins"
# T38: headless has no way to show the trust prompt, so an untrusted scene
# fails closed -- Init AND Compute stop exec'ing. This is the suite's explicit
# opt-in for the repo's own fixtures (run_tests.bat:35 already sets it). Tests
# that exercise the DENY path pop it in setUp.
export MPYNODE_TRUST_PICKLE=1

# NOT `-m unittest`: after maya.standalone.initialize() mayapy's teardown forces
# exit 0, so failures were reported as success. tools/_unittest_exit.py runs the
# same TestProgram and exits with the real status.
#
# No args => discover, matching run_tests.bat:37-41. Forwarding "$@" bare made a
# bare `run_tests.sh` print "Ran 0 tests" / "OK" and exit 0 -- a false green that
# survives the `^OK( \(|$)` grep the suite is verified with.
if [ "$#" -eq 0 ]; then
    "$MAYAPY" "$TOOLS_DIR/_unittest_exit.py" discover -s tests -t . -p "test_*.py"
else
    "$MAYAPY" "$TOOLS_DIR/_unittest_exit.py" "$@"
fi
