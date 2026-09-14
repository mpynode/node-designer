@echo off
setlocal
REM Rebuild native plugin 'MPyLocator_Mesh_Regions' from its single source 'source\meshRegionLocator.cpp'.
REM Edit source\meshRegionLocator.cpp, then run build.bat from any cmd.exe -- it sets up MSVC itself.
REM
REM Usage:  build.bat [maya-version]      e.g. build.bat 2026
REM With no argument the newest installed Maya is used; set MAYA to
REM override discovery.
REM --- MSVC: set up the compiler environment unless this is already a
REM     developer prompt (vcvarsall / VsDevCmd export VSCMD_ARG_TGT_ARCH).
set "_VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "_VSINST="
if not "%VSCMD_ARG_TGT_ARCH%"=="" goto :msvc_ready
if not exist "%_VSWHERE%" goto :msvc_check
for /f "usebackq delims=" %%D in (`"%_VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "_VSINST=%%D"
if "%_VSINST%"=="" for /f "usebackq delims=" %%D in (`"%_VSWHERE%" -prerelease -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "_VSINST=%%D"
set "PATH=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer;%PATH%"
if exist "%_VSINST%\VC\Auxiliary\Build\vcvarsall.bat" call "%_VSINST%\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul
:msvc_check
where cl >nul 2>nul
if errorlevel 1 (
  echo build.bat: no MSVC compiler ^(cl^) found. Install Visual Studio with the 1>&2
  echo   "Desktop development with C++" workload, or run this from an 1>&2
  echo   'x64 Native Tools Command Prompt for VS'. 1>&2
  exit /b 1
)
if "%INCLUDE%"=="" (
  echo build.bat: 'cl' is on PATH but the MSVC environment is not set up 1>&2
  echo   ^(INCLUDE is empty^) -- that cl is probably a stray older toolchain. 1>&2
  echo   Run this from an 'x64 Native Tools Command Prompt for VS'. 1>&2
  exit /b 1
)
:msvc_ready
set "_V=%~1"
if not "%_V%"=="" set "MAYA="
if "%MAYA%"=="" (
  for /d %%D in ("C:\Program Files\Autodesk\Maya%_V%*") do (
    if exist "%%~fD\include\maya" set "MAYA=%%~fD"
  )
)
if not exist "%MAYA%\include\maya" (
  echo build.bat: no Maya %_V% with a devkit under "C:\Program Files\Autodesk" 1>&2
  echo   pass a version:  build.bat 2026 1>&2
  echo   or set MAYA:     set "MAYA=C:\path\to\maya" 1>&2
  exit /b 1
)
set "QTINC=%MPYNODE_QT_INCLUDE%"
if not "%QTINC%"=="" if not exist "%QTINC%\QtGui\QCursor" (
  echo build.bat: MPYNODE_QT_INCLUDE is set to "%QTINC%" but that has no QtGui\QCursor 1>&2
  echo   point it at the directory that CONTAINS QtGui\, or unset it 1>&2
  exit /b 1
)
if "%QTINC%"=="" if exist "%MAYA%\include\QtGui\QCursor" set "QTINC=%MAYA%\include"
if "%QTINC%"=="" if exist "%MAYA%\include\qt\QtGui\QCursor" set "QTINC=%MAYA%\include\qt"
if "%QTINC%"=="" if exist "%MAYA%\include\Qt\QtGui\QCursor" set "QTINC=%MAYA%\include\Qt"
if "%QTINC%"=="" (
  for /d %%D in ("%MAYA%\include\*") do (
    if exist "%%~fD\QtGui\QCursor" set "QTINC=%%~fD"
  )
)
set "_QTZIP="
set "_QTCACHE="
if "%QTINC%"=="" (
  for %%D in ("%MAYA%\include\qt_*-include.zip") do set "_QTZIP=%%~fD"
)
if "%QTINC%"=="" if not "%_QTZIP%"=="" (
  for %%D in ("%_QTZIP%") do set "_QTCACHE=%LOCALAPPDATA%\mpynode\qt_include\%%~nD"
)
if "%QTINC%"=="" if not "%_QTCACHE%"=="" (
  if not exist "%_QTCACHE%\QtGui\QCursor" (
    echo build.bat: extracting the devkit Qt headers once into "%_QTCACHE%" ...
    if not exist "%_QTCACHE%" mkdir "%_QTCACHE%"
    if exist "%SystemRoot%\System32\tar.exe" (
      "%SystemRoot%\System32\tar.exe" -xf "%_QTZIP%" -C "%_QTCACHE%"
    ) else (
      powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%_QTZIP%' -DestinationPath '%_QTCACHE%' -Force"
    )
  )
  if exist "%_QTCACHE%\QtGui\QCursor" set "QTINC=%_QTCACHE%"
)
if "%QTINC%"=="" (
  echo build.bat: this plugin has a hover locator, whose C++ includes the Maya 1>&2
  echo   Qt headers -- but none were found under "%MAYA%\include". 1>&2
  echo   The devkit ships them as an UNEXTRACTED archive, e.g. 1>&2
  echo     "%MAYA%\include\qt_6.5.3_vc14-include.zip" 1>&2
  echo   which this script extracts by itself into 1>&2
  echo     "%LOCALAPPDATA%\mpynode\qt_include\<archive name>" 1>&2
  echo   so either that archive is missing or the extraction failed. 1>&2
  echo   Fix: extract it anywhere so "<dir>\QtGui\QCursor" exists, then 1>&2
  echo     set MPYNODE_QT_INCLUDE=^<dir^> 1>&2
  exit /b 1
)
set "HERE=%~dp0"
REM Link in a local temp folder, then copy the plug-in into place: the
REM MSVC linker memory-maps its outputs, and on a cloud-synced folder
REM (Google Drive, OneDrive) that write hangs forever. A copy is fine.
set "LINKTMP=%TEMP%\mpynode_link_%RANDOM%_%RANDOM%"
if exist "%LINKTMP%" rd /s /q "%LINKTMP%"
mkdir "%LINKTMP%"
cl /nologo /LD /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /I "%MAYA%\include" /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h "%HERE%source\meshRegionLocator.cpp" /Fo"%HERE%meshRegionLocator.obj" /link /LIBPATH:"%MAYA%\lib" OpenMaya.lib OpenMayaAnim.lib OpenMayaUI.lib OpenMayaRender.lib Foundation.lib Qt6Core.lib Qt6Gui.lib Qt6Widgets.lib /IMPLIB:"%LINKTMP%\MPyLocator_Mesh_Regions.lib" /OUT:"%LINKTMP%\MPyLocator_Mesh_Regions.mll" /EXPORT:initializePlugin /EXPORT:uninitializePlugin
if errorlevel 1 exit /b 1
copy /Y "%LINKTMP%\MPyLocator_Mesh_Regions.mll" "%HERE%..\MPyLocator_Mesh_Regions.mll" >nul
if errorlevel 1 exit /b 1
rd /s /q "%LINKTMP%" 2>nul
del "%HERE%meshRegionLocator.obj" 2>nul
echo Built: %HERE%..\MPyLocator_Mesh_Regions.mll
exit /b 0
