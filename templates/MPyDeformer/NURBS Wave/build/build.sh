#!/usr/bin/env bash
# Rebuild native plugin 'MPyDeformer_NURBS_Wave' from its single source 'source/nurbsWave.cpp'.
# Edit source/nurbsWave.cpp, then run ./build.sh to produce MPyDeformer_NURBS_Wave.bundle (one level
# up, in a folder named after the Maya version: ../2026/).
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
# The plug-in lands in a folder named after the Maya version, never with the
# version in its file name: Maya records the file name in every scene that
# uses it. The year comes from the install's folder name (Maya2026), else from
# its devkit's MAYA_API_VERSION. A build folder already inside its version
# folder (a multi-version compile's out/2026/build) writes beside itself.
_mn="$(basename "$MAYA")"
YEAR=""
case "$_mn" in
  [Mm][Aa][Yy][Aa][0-9][0-9][0-9][0-9]*) YEAR="${_mn:4:4}" ;;
esac
if [ -z "$YEAR" ]; then
  YEAR="$(sed -n 's/^#define[[:space:]]\{1,\}MAYA_API_VERSION[[:space:]]\{1,\}\([0-9]\{4\}\).*/\1/p' "$MAYA/include/maya/MTypes.h" 2>/dev/null | head -n 1 || true)"
fi
if [ -z "$YEAR" ]; then
  echo "build.sh: cannot tell which Maya version $MAYA is: no year in its folder name and no MAYA_API_VERSION in include/maya/MTypes.h" >&2
  exit 1
fi
if [ "$(basename "$(cd "$HERE/.." && pwd)")" = "$YEAR" ]; then
  PLUGIN_DIR="$HERE/.."
else
  PLUGIN_DIR="$HERE/../$YEAR"
fi
mkdir -p "$PLUGIN_DIR"
if [ -e "$PLUGIN_DIR/../MPyDeformer_NURBS_Wave.bundle" ]; then
  echo "build.sh: note: an older MPyDeformer_NURBS_Wave.bundle sits one folder up and is left in place; Maya loads whichever comes first on the plug-in path" >&2
fi
clang++ -std=c++17 -O3 -ffp-contract=off -arch arm64 -bundle \
  -D OSMac_ -D REQUIRE_IOSTREAM -D _BOOL \
  -Wno-nontrivial-memcall \
  -I"$MAYA/include" \
  -L"$MAYA/Maya.app/Contents/MacOS" \
  -lOpenMaya -lOpenMayaAnim -lOpenMayaUI -lOpenMayaRender -lFoundation \
  -o "$PLUGIN_DIR/MPyDeformer_NURBS_Wave.bundle" "$HERE/source/nurbsWave.cpp"
echo "Built: $PLUGIN_DIR/MPyDeformer_NURBS_Wave.bundle"
lipo -info "$PLUGIN_DIR/MPyDeformer_NURBS_Wave.bundle"
