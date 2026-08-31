#!/usr/bin/env bash
# Generated combined build for native plugin 'mPyMega' (37 nodes).
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
CXX=(clang++ -std=c++17 -O3 -ffp-contract=off -arch arm64 -D OSMac_ -D REQUIRE_IOSTREAM -D _BOOL -Wno-nontrivial-memcall -I"$MAYA/include" -F"$MAYA/Maya.app/Contents/Frameworks")
OBJS=()
# Node fragments suppress the plugin-version symbols (-D MNoVersionString -D MNoPluginEntry);
# only plugin_main.cpp emits them (exactly one per plugin).
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/mPyDnet.cpp" -o "$HERE/source/mPyDnet.o"
OBJS+=("$HERE/source/mPyDnet.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/comboCorrectives.cpp" -o "$HERE/source/comboCorrectives.o"
OBJS+=("$HERE/source/comboCorrectives.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/procrustesTags.cpp" -o "$HERE/source/procrustesTags.o"
OBJS+=("$HERE/source/procrustesTags.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/nurbsWave.cpp" -o "$HERE/source/nurbsWave.o"
OBJS+=("$HERE/source/nurbsWave.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/patchRelax.cpp" -o "$HERE/source/patchRelax.o"
OBJS+=("$HERE/source/patchRelax.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/rbfWrapDeformer.cpp" -o "$HERE/source/rbfWrapDeformer.o"
OBJS+=("$HERE/source/rbfWrapDeformer.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/sineRipple.cpp" -o "$HERE/source/sineRipple.o"
OBJS+=("$HERE/source/sineRipple.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/unitSphereCollision.cpp" -o "$HERE/source/unitSphereCollision.o"
OBJS+=("$HERE/source/unitSphereCollision.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/compositeTexture.cpp" -o "$HERE/source/compositeTexture.o"
OBJS+=("$HERE/source/compositeTexture.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/scanlineTex.cpp" -o "$HERE/source/scanlineTex.o"
OBJS+=("$HERE/source/scanlineTex.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/fileTexture.cpp" -o "$HERE/source/fileTexture.o"
OBJS+=("$HERE/source/fileTexture.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/gameOfLifeTex.cpp" -o "$HERE/source/gameOfLifeTex.o"
OBJS+=("$HERE/source/gameOfLifeTex.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/twoBoneIK.cpp" -o "$HERE/source/twoBoneIK.o"
OBJS+=("$HERE/source/twoBoneIK.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/animatedSelection.cpp" -o "$HERE/source/animatedSelection.o"
OBJS+=("$HERE/source/animatedSelection.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/animatedText.cpp" -o "$HERE/source/animatedText.o"
OBJS+=("$HERE/source/animatedText.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/meshRegionLocator.cpp" -o "$HERE/source/meshRegionLocator.o"
OBJS+=("$HERE/source/meshRegionLocator.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/widgetShowcase.cpp" -o "$HERE/source/widgetShowcase.o"
OBJS+=("$HERE/source/widgetShowcase.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/diskMeshCache.cpp" -o "$HERE/source/diskMeshCache.o"
OBJS+=("$HERE/source/diskMeshCache.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/gameOfLifeMesh.cpp" -o "$HERE/source/gameOfLifeMesh.o"
OBJS+=("$HERE/source/gameOfLifeMesh.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/jsonMeshReader.cpp" -o "$HERE/source/jsonMeshReader.o"
OBJS+=("$HERE/source/jsonMeshReader.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/meshMaze.cpp" -o "$HERE/source/meshMaze.o"
OBJS+=("$HERE/source/meshMaze.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/metaballs.cpp" -o "$HERE/source/metaballs.o"
OBJS+=("$HERE/source/metaballs.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/uvLayoutMesh.cpp" -o "$HERE/source/uvLayoutMesh.o"
OBJS+=("$HERE/source/uvLayoutMesh.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/voxelizeMesh.cpp" -o "$HERE/source/voxelizeMesh.o"
OBJS+=("$HERE/source/voxelizeMesh.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/bubbleSort.cpp" -o "$HERE/source/bubbleSort.o"
OBJS+=("$HERE/source/bubbleSort.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/hexAttribute.cpp" -o "$HERE/source/hexAttribute.o"
OBJS+=("$HERE/source/hexAttribute.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/ouch.cpp" -o "$HERE/source/ouch.o"
OBJS+=("$HERE/source/ouch.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/rbfWrap.cpp" -o "$HERE/source/rbfWrap.o"
OBJS+=("$HERE/source/rbfWrap.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/spine.cpp" -o "$HERE/source/spine.o"
OBJS+=("$HERE/source/spine.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/spline.cpp" -o "$HERE/source/spline.o"
OBJS+=("$HERE/source/spline.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/springChain.cpp" -o "$HERE/source/springChain.o"
OBJS+=("$HERE/source/springChain.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/helixCurve.cpp" -o "$HERE/source/helixCurve.o"
OBJS+=("$HERE/source/helixCurve.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/rippleSurf.cpp" -o "$HERE/source/rippleSurf.o"
OBJS+=("$HERE/source/rippleSurf.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/dualQuaternionSkin.cpp" -o "$HERE/source/dualQuaternionSkin.o"
OBJS+=("$HERE/source/dualQuaternionSkin.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/linearBlendSkin.cpp" -o "$HERE/source/linearBlendSkin.o"
OBJS+=("$HERE/source/linearBlendSkin.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/twistSwingSkin.cpp" -o "$HERE/source/twistSwingSkin.o"
OBJS+=("$HERE/source/twistSwingSkin.o")
"${CXX[@]}" -D MNoVersionString -D MNoPluginEntry -c "$HERE/source/aimTransform.cpp" -o "$HERE/source/aimTransform.o"
OBJS+=("$HERE/source/aimTransform.o")
"${CXX[@]}" -c "$HERE/source/plugin_main.cpp" -o "$HERE/source/plugin_main.o"
OBJS+=("$HERE/source/plugin_main.o")
clang++ -std=c++17 -arch arm64 -bundle -L"$MAYA/Maya.app/Contents/MacOS" -lOpenMaya -lOpenMayaAnim -lOpenMayaUI -lOpenMayaRender -lFoundation "${OBJS[@]}" -framework QtCore -framework QtGui -framework QtWidgets -F"$MAYA/Maya.app/Contents/Frameworks" -Wl,-rpath,"$MAYA/Maya.app/Contents/Frameworks" -o "$HERE/../mPyMega.bundle"
rm -f "${OBJS[@]}"
echo "Built: $HERE/../mPyMega.bundle"
lipo -info "$HERE/../mPyMega.bundle"
