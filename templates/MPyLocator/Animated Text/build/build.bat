@echo off
REM Rebuild native plugin 'MPyLocator_Animated_Text' from its single source 'source\animatedText.cpp'.
REM Edit source\animatedText.cpp, then run build.bat from any cmd.exe -- it sets up MSVC itself.
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
if "%QTINC%"=="" (
  echo build.bat: this plugin has a hover locator, whose C++ includes the Maya 1>&2
  echo   Qt headers -- but none were found under "%MAYA%\include". 1>&2
  echo   The devkit ships them as an UNEXTRACTED archive, e.g. 1>&2
  echo     "%MAYA%\include\qt_6.5.3_vc14-include.zip" 1>&2
  echo   so they are on no include path until it is extracted. 1>&2
  echo   Fix: extract it so "<dir>\QtGui\QCursor" exists, then either 1>&2
  echo     tar -xf "%MAYA%\include\qt_*-include.zip" -C "%MAYA%\include"   ^(in place^), 1>&2
  echo   or extract anywhere and set MPYNODE_QT_INCLUDE=^<dir^>. 1>&2
  exit /b 1
)
set "HERE=%~dp0"
cl /nologo /LD /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /I "%MAYA%\include" /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h "%HERE%source\animatedText.cpp" /link /LIBPATH:"%MAYA%\lib" OpenMaya.lib OpenMayaAnim.lib OpenMayaUI.lib OpenMayaRender.lib Foundation.lib Qt6Core.lib Qt6Gui.lib Qt6Widgets.lib /OUT:"%HERE%..\MPyLocator_Animated_Text.mll" /EXPORT:initializePlugin /EXPORT:uninitializePlugin
if errorlevel 1 exit /b 1
echo Built: %HERE%..\MPyLocator_Animated_Text.mll
