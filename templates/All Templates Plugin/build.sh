#!/usr/bin/env bash
# Build mPyMega for the scenes beside this script.
#
# Usage:  ./build.sh [maya-version]      e.g. ./build.sh 2026
# With no argument the newest installed Maya is used; MAYA=<path> overrides.
#
# No binary ships with this repo: a Maya plug-in is compiled against one Maya
# version's devkit and will not load in another. This compiles the committed
# C++ under build/ beside this script (37 node types + 32 bundled commands,
# namespaced per node and linked through one generated plugin_main.cpp). The
# result lands beside this script in a folder named after the Maya version --
# 2026/mPyMega.bundle -- which is the folder MAYA_PLUG_IN_PATH points at.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$HERE/build/build.sh" ]; then
    echo "build.sh: no combined build tree at $HERE/build" >&2
    exit 1
fi

# The inner script owns Maya-version resolution (argument > MAYA > newest
# install with a devkit), the version folder and its own diagnostics -- forward
# the argument rather than second-guessing it here. One resolver, one place to
# fix.
#
# The name stays exactly mPyMega.bundle: the version lives in the folder, never
# in the file name. Maya derives a plug-in's NAME from its filename, and every
# scene here carries `requires ... "mPyMega"`. A version-stamped copy loads fine
# but registers as "mPyMega.2026", and then all 40 scenes open with unknown
# nodes -- with nothing failing at build time.
bash "$HERE/build/build.sh" "$@"

# Builds before the version folders installed a copy into plugin/. It is left
# in place -- a MAYA_PLUG_IN_PATH may still name it -- but two mPyMega on the
# path load whichever Maya meets first, so say so.
if [ -e "$HERE/plugin/mPyMega.bundle" ]; then
    echo "build.sh: note: an older plugin/mPyMega.bundle is left in place; Maya loads whichever mPyMega comes first on the plug-in path" >&2
fi
