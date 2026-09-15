#!/usr/bin/env bash
# Launch Maya 2025 (GUI) wired to use the mpynode code in THIS repo (macOS / Linux).
#
#   ./launch_maya2025.sh
#
# Mirrors launch_maya2025.bat. What it does:
#   * Prepends this repo's scripts/ to PYTHONPATH          -> import mpynode = THIS copy
#   * Prepends this repo's plug-ins/ to MAYA_PLUG_IN_PATH  -> plug-ins load from here
#   * Sets MPYNODE_USE_STUDIO=1 so a Maya-prefs userSetup.py skips its own
#     (stale) path setup and doesn't fight us.
#
# Pass no scene file: it would open during startup, before the plug-in is
# registered. Set MAYA_LOCATION to point at another Maya install.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MPYNODE_USE_STUDIO=1
export PYTHONPATH="$HERE/scripts${PYTHONPATH:+:$PYTHONPATH}"
export MAYA_PLUG_IN_PATH="$HERE/plug-ins${MAYA_PLUG_IN_PATH:+:$MAYA_PLUG_IN_PATH}"

if [ -z "$MAYA_LOCATION" ]; then
  if [ -d "/Applications/Autodesk/maya2025/Maya.app/Contents" ]; then
    MAYA_LOCATION="/Applications/Autodesk/maya2025/Maya.app/Contents"
  else
    MAYA_LOCATION="/usr/autodesk/maya2025"
  fi
fi
export MAYA_LOCATION
MAYA_BIN="$MAYA_LOCATION/bin/maya"

echo "[launch_maya2025] mpynode scripts : $HERE/scripts"
echo "[launch_maya2025] plug-ins        : $HERE/plug-ins"
echo "[launch_maya2025] launching: $MAYA_BIN"

exec "$MAYA_BIN" "$@"
