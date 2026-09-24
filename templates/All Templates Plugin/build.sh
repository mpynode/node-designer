#!/usr/bin/env bash
# Build mPyMega and install it into plugin/, ready for the scenes beside it.
#
# Usage:  ./build.sh [maya-version]      e.g. ./build.sh 2026
# With no argument the newest installed Maya is used; MAYA=<path> overrides.
#
# No binary ships with this repo: a Maya plug-in is compiled against one Maya
# version's devkit and will not load in another. This compiles the committed
# C++ under build/ beside this script (37 node types + 32 bundled commands,
# namespaced per node and linked through one generated plugin_main.cpp) and
# drops the result next to the demo scenes.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$HERE/build/build.sh" ]; then
    echo "build.sh: no combined build tree at $HERE/build" >&2
    exit 1
fi

# The inner script owns Maya-version resolution (argument > MAYA > newest
# install with a devkit) and its own diagnostics -- forward the argument rather
# than second-guessing it here. One resolver, one place to fix.
bash "$HERE/build/build.sh" "$@"

# plugin/ holds only ignored build products, so it does NOT exist in a fresh
# clone -- git does not track empty directories.
mkdir -p "$HERE/plugin"

# The name must stay exactly mPyMega.bundle. Maya derives a plug-in's NAME from
# its filename, and every scene here carries `requires ... "mPyMega"`. A
# version-stamped copy loads fine but registers as "mPyMega.2026", and then all
# 40 scenes open with unknown nodes -- with nothing failing at build time.
cp "$HERE/mPyMega.bundle" "$HERE/plugin/mPyMega.bundle"
echo "Installed: $HERE/plugin/mPyMega.bundle"
