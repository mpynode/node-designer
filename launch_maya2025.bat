@echo off
REM Launch Maya 2025 (GUI) wired to use the mpynode code in THIS repo (Windows).
REM
REM   launch_maya2025.bat
REM
REM Mirrors launch_maya2025.sh. What it does:
REM   * Prepends this repo's scripts\ to PYTHONPATH        -> import mpynode = THIS copy
REM   * Prepends this repo's plug-ins\ to MAYA_PLUG_IN_PATH -> plugins load from here
REM   * Sets MPYNODE_USE_STUDIO=1 so the Maya-prefs userSetup.py skips its own
REM     (stale) path setup and doesn't fight us.

setlocal
set "HERE=%~dp0"
set "MPYNODE_USE_STUDIO=1"
set "PYTHONPATH=%HERE%scripts;%PYTHONPATH%"
set "MAYA_PLUG_IN_PATH=%HERE%plug-ins;%MAYA_PLUG_IN_PATH%"

if "%MAYA_LOCATION%"=="" set "MAYA_LOCATION=C:\Program Files\Autodesk\Maya2025"
set "MAYA_BIN=%MAYA_LOCATION%\bin\maya.exe"

echo [launch_maya2025] mpynode scripts : %HERE%scripts
echo [launch_maya2025] plug-ins        : %HERE%plug-ins
echo [launch_maya2025] launching: %MAYA_BIN%

"%MAYA_BIN%" %*
endlocal
