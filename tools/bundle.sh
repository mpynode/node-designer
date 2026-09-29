#!/usr/bin/env bash
# Combine compiled MPyNode node sources into one Maya plug-in.
#
#   tools/bundle.sh NAME INPUT... [--maya 2026] [options]
#   tools/bundle.sh --check INPUT...
#   tools/bundle.sh --refresh DIR
#   tools/bundle.sh --help
#
# Finds a mayapy (MPYNODE_MAYAPY, then MAYA_LOCATION, then the newest Maya
# under /Applications/Autodesk or /usr/autodesk that has a devkit) and runs
# mpynode.native.bundle under it with this repo's scripts first on PYTHONPATH.
# By default the bundle targets the Maya that mayapy belongs to; pass --maya
# to build for another installed version.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"

MAYAPY="${MPYNODE_MAYAPY:-}"
if [ -z "$MAYAPY" ] && [ -n "${MAYA_LOCATION:-}" ]; then
  # macOS MAYA_LOCATION is <root>/Maya.app/Contents; Linux is the root.
  for c in "$MAYA_LOCATION/bin/mayapy" "$MAYA_LOCATION/Maya.app/Contents/bin/mayapy"; do
    [ -x "$c" ] && MAYAPY="$c" && break
  done
fi
if [ -z "$MAYAPY" ]; then
  for d in /Applications/Autodesk/maya* /usr/autodesk/maya*; do
    [ -d "$d/include/maya" ] || continue
    for c in "$d/Maya.app/Contents/bin/mayapy" "$d/bin/mayapy"; do
      [ -x "$c" ] && MAYAPY="$c"
    done
  done
fi
if [ ! -x "${MAYAPY:-}" ]; then
  echo "bundle.sh: no mayapy found. Set MPYNODE_MAYAPY or MAYA_LOCATION, or install a Maya with its devkit." >&2
  exit 3
fi

export PYTHONPATH="$HERE/scripts${PYTHONPATH:+:$PYTHONPATH}"
# Never let a crashed child leave Autodesk's error-report window behind.
export MAYA_DISABLE_CER=1
# Pinned so generated C++ is byte-stable across processes.
export PYTHONHASHSEED=0

exec "$MAYAPY" -m mpynode.native.bundle "$@"
