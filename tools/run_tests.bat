@echo off
REM Run the mpynode unit suite under mayapy on Windows.
REM
REM   tools\run_tests.bat                                  (whole suite)
REM   tools\run_tests.bat tests.nodes.test_draw_types      (one module)
REM
REM Mirrors run_tests.sh -- same env, same runner, same exit status. The
REM optional MPYNODE_EXTRA_PYTHONPATH entry (numpy / scipy / PIL) that
REM run_tests.sh honours has no equivalent here, and is the one deliberate
REM difference. Override MAYA_LOCATION to target a different Maya.
REM
REM NOT `-m unittest`: after maya.standalone.initialize() mayapy's teardown
REM forces exit 0, so failures were reported as success. _unittest_exit.py runs
REM the same TestProgram and exits with the real status, which the tail of this
REM script hands back to the caller across `endlocal`.

setlocal
REM %~dp0 is tools\; every path below is anchored on the REPO ROOT, its parent.
REM %%~fI resolves the "..\" away but drops the trailing separator, and HERE is
REM concatenated bare (%HERE%scripts), so put the separator back.
for %%I in ("%~dp0..") do set "HERE=%%~fI\"
cd /d "%HERE%"
if "%MAYA_LOCATION%"=="" set "MAYA_LOCATION=C:\Program Files\Autodesk\Maya2026"
set "MAYAPY=%MAYA_LOCATION%\bin\mayapy.exe"

set "MPYNODE_USE_STUDIO=1"
set "MPYNODE_ROOT=%HERE%"
REM The repo root is on the path too, so the suite imports as
REM `tests.<area>.<module>`. HERE carries a trailing separator, which a path
REM entry does not want, so trim it. Discovery would add the root by itself,
REM but naming ONE module on the command line bypasses discovery entirely.
set "PYTHONPATH=%HERE%scripts;%HERE:~0,-1%"
set "MAYA_PLUG_IN_PATH=%HERE%plug-ins"
set "QT_QPA_PLATFORM=offscreen"
set "MPYNODE_TRUST_PICKLE=1"

if "%~1"=="" (
    "%MAYAPY%" "%HERE%tools\_unittest_exit.py" discover -s tests -t . -p "test_*.py"
) else (
    "%MAYAPY%" "%HERE%tools\_unittest_exit.py" %*
)
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
