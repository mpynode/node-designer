#!/usr/bin/env bash
# Generated build for native node 'meshRegions'.
set -euo pipefail
MAYA="${MAYA:-/Applications/Autodesk/maya2026}"
HERE="$(cd "$(dirname "$0")" && pwd)"
clang++ -std=c++17 -O3 -ffp-contract=off -arch arm64 -bundle \
  -D OSMac_ -D REQUIRE_IOSTREAM -D _BOOL \
  -Wno-nontrivial-memcall \
  -I"$MAYA/include" \
  -L"$MAYA/Maya.app/Contents/MacOS" \
  -lOpenMaya -lFoundation -lOpenMayaAnim -lOpenMayaUI -lOpenMayaRender \
  -F"$MAYA/Maya.app/Contents/Frameworks" \
  -framework QtCore -framework QtGui -framework QtWidgets \
  -Wl,-rpath,"$MAYA/Maya.app/Contents/Frameworks" \
  -o "$HERE/meshRegions.bundle" "$HERE/meshRegions.cpp"
echo "Built: $HERE/meshRegions.bundle"
lipo -info "$HERE/meshRegions.bundle"
