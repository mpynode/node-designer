#!/usr/bin/env bash
# Rebuild native plugin 'MPyLocator_Widget_Showcase' from its single source 'source/widgetShowcase.cpp'.
# Edit source/widgetShowcase.cpp, then run ./build.sh to produce MPyLocator_Widget_Showcase.bundle (one level up).
#
# Usage:  ./build.sh [maya-version]      e.g. ./build.sh 2026
# With no argument the newest installed Maya is used; MAYA=<path>
# overrides discovery.
set -euo pipefail
_v="${1:-}"
if [ -n "$_v" ] || [ -z "${MAYA:-}" ]; then
  _found=""
  for _d in "/Applications/Autodesk"/[Mm]aya"$_v"[0-9][0-9][0-9][0-9]*; do
    [ -d "$_d/include/maya" ] && _found="$_d"
  done
  if [ -z "$_found" ]; then
    for _d in "/Applications/Autodesk"/[Mm]aya"$_v"*; do
      [ -d "$_d/include/maya" ] && _found="$_d"
    done
  fi
  MAYA="$_found"
fi
if [ ! -d "${MAYA:-}/include/maya" ]; then
  echo "build.sh: no Maya ${_v:-install} with a devkit under /Applications/Autodesk" >&2
  echo "  pass a version:  ./build.sh 2026" >&2
  echo "  or set MAYA:     MAYA=/path/to/maya ./build.sh" >&2
  exit 1
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
clang++ -std=c++17 -O3 -ffp-contract=off -arch arm64 -bundle \
  -D OSMac_ -D REQUIRE_IOSTREAM -D _BOOL \
  -Wno-nontrivial-memcall \
  -I"$MAYA/include" \
  -L"$MAYA/Maya.app/Contents/MacOS" \
  -lOpenMaya -lOpenMayaAnim -lOpenMayaUI -lOpenMayaRender -lFoundation \
  -o "$HERE/../MPyLocator_Widget_Showcase.bundle" "$HERE/source/widgetShowcase.cpp"
echo "Built: $HERE/../MPyLocator_Widget_Showcase.bundle"
lipo -info "$HERE/../MPyLocator_Widget_Showcase.bundle"
