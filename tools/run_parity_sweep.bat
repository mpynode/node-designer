@echo off
REM Pre-release gate: re-verify COMPILED native parity for all 12 basic mPyNode
REM types against their built .bundles (no rebuild, no porter, no LLM). Exits 0
REM only if all 12 pass -- wire this into CI / run before tagging a release.
REM
REM   tools\run_parity_sweep.bat
REM
REM Each type is verified in its own isolated mayapy subprocess. Override
REM MAYA_LOCATION to target a different Maya. Runtime ~6 min.
REM
REM The .bundle fixtures are NOT committed (.gitignore: *.bundle), so a fresh
REM clone has to build them first -- run_parity_sweep.py says so and exits
REM before spending six minutes proving it.
REM
REM See tools\parity_sweep\ for the runner and per-type parity_*.py checks.
setlocal
REM %~dp0 is tools\; MPYNODE_ROOT must be the REPO ROOT, its parent. %%~fI
REM resolves the "..\" away but drops the trailing separator, and HERE is
REM concatenated bare (%HERE%tools\...), so put the separator back.
for %%I in ("%~dp0..") do set "HERE=%%~fI\"
if "%MAYA_LOCATION%"=="" set "MAYA_LOCATION=C:\Program Files\Autodesk\Maya2026"
set "MAYAPY=%MAYA_LOCATION%\bin\mayapy.exe"
set "MPYNODE_ROOT=%HERE%"
set "QT_QPA_PLATFORM=offscreen"
REM T38: the fixtures are .ma scenes full of MPyNode Python, and headless can't
REM show the trust prompt -- without this opt-in the INTERPRETED side of every
REM comparison stops computing and the sweep reports a bogus FAIL. Inherited by
REM the per-type mayapy subprocesses. Mirrors run_parity_sweep.sh.
set "MPYNODE_TRUST_PICKLE=1"

REM Hand the runner's real status back across `endlocal` -- a bare `endlocal`
REM discards it, so the gate reported success no matter what the sweep found
REM (the defect run_tests.bat already carries the fix for).
"%MAYAPY%" "%HERE%tools\parity_sweep\run_parity_sweep.py"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
