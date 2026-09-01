@echo off
REM Rebuild native plugin 'MPyLocator_Mesh_Regions' from its single source 'source\meshRegionLocator.cpp'.
REM Edit source\meshRegionLocator.cpp, then run build.bat from an 'x64 Native Tools Command Prompt for VS'.
REM
REM Usage:  build.bat [maya-version]      e.g. build.bat 2026
REM With no argument the newest installed Maya is used; set MAYA to
REM override discovery.
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
cl /nologo /LD /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /I "%MAYA%\include" /Zc:__cplusplus /permissive- /I "%QTINC%" "%HERE%source\meshRegionLocator.cpp" /link /LIBPATH:"%MAYA%\lib" OpenMaya.lib OpenMayaAnim.lib OpenMayaUI.lib OpenMayaRender.lib Foundation.lib Qt6Core.lib Qt6Gui.lib Qt6Widgets.lib /OUT:"%HERE%..\MPyLocator_Mesh_Regions.mll" /EXPORT:initializePlugin /EXPORT:uninitializePlugin
if errorlevel 1 exit /b 1
echo Built: %HERE%..\MPyLocator_Mesh_Regions.mll
