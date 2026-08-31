@echo off
REM Rebuild native plugin 'MPyNode_Spine' from its single source 'source\spine.cpp'.
REM Edit source\spine.cpp, then run build.bat from an 'x64 Native Tools Command Prompt for VS'.
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
  echo build.bat: no Maya %_V% with a devkit under "C:\Program Files\Autodesk" 1^>^&2
  echo   pass a version:  build.bat 2026 1^>^&2
  echo   or set MAYA:     set "MAYA=C:\path\to\maya" 1^>^&2
  exit /b 1
)
set "HERE=%~dp0"
cl /nologo /LD /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /I "%MAYA%\include" "%HERE%source\spine.cpp" /link /LIBPATH:"%MAYA%\lib" OpenMaya.lib OpenMayaAnim.lib OpenMayaUI.lib OpenMayaRender.lib Foundation.lib /OUT:"%HERE%..\MPyNode_Spine.mll" /EXPORT:initializePlugin /EXPORT:uninitializePlugin
if errorlevel 1 exit /b 1
echo Built: %HERE%..\MPyNode_Spine.mll
