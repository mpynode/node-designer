@echo off
REM Combine compiled MPyNode node sources into one Maya plug-in.
REM
REM   tools\bundle.bat NAME INPUT... [--maya 2025] [options]
REM   tools\bundle.bat --check INPUT...
REM   tools\bundle.bat --refresh DIR
REM   tools\bundle.bat --help
REM
REM Finds a mayapy (MPYNODE_MAYAPY, then MAYA_LOCATION, then the newest Maya
REM under "C:\Program Files\Autodesk" that has a devkit) and runs
REM mpynode.native.bundle under it with this repo's scripts first on
REM PYTHONPATH. By default the bundle targets the Maya that mayapy belongs
REM to; pass --maya to build for another installed version.
setlocal
for %%I in ("%~dp0..") do set "HERE=%%~fI\"

set "MAYAPY=%MPYNODE_MAYAPY%"
if "%MAYAPY%"=="" if not "%MAYA_LOCATION%"=="" set "MAYAPY=%MAYA_LOCATION%\bin\mayapy.exe"
if "%MAYAPY%"=="" (
  for /d %%D in ("C:\Program Files\Autodesk\Maya*") do (
    if exist "%%~fD\include\maya" if exist "%%~fD\bin\mayapy.exe" set "MAYAPY=%%~fD\bin\mayapy.exe"
  )
)
if not exist "%MAYAPY%" (
  echo bundle.bat: no mayapy found. Set MPYNODE_MAYAPY or MAYA_LOCATION, or 1>&2
  echo   install a Maya with its devkit under "C:\Program Files\Autodesk". 1>&2
  exit /b 3
)

set "PYTHONPATH=%HERE%scripts;%PYTHONPATH%"
REM Never let a crashed child leave Autodesk's error-report window behind.
set "MAYA_DISABLE_CER=1"
REM Pinned so generated C++ is byte-stable across processes.
set "PYTHONHASHSEED=0"

"%MAYAPY%" -m mpynode.native.bundle %*
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
