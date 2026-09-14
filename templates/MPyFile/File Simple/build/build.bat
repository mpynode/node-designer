@echo off
setlocal
REM Rebuild native plugin 'MPyFile_File_Simple' from its single source 'source\fileTexture.cpp'.
REM Edit source\fileTexture.cpp, then run build.bat from any cmd.exe -- it sets up MSVC itself.
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
set "HERE=%~dp0"
REM Link in a local temp folder, then copy the plug-in into place: the
REM MSVC linker memory-maps its outputs, and on a cloud-synced folder
REM (Google Drive, OneDrive) that write hangs forever. A copy is fine.
set "LINKTMP=%TEMP%\mpynode_link_%RANDOM%_%RANDOM%"
if exist "%LINKTMP%" rd /s /q "%LINKTMP%"
mkdir "%LINKTMP%"
cl /nologo /LD /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /I "%MAYA%\include" "%HERE%source\fileTexture.cpp" /Fo"%HERE%fileTexture.obj" /link /LIBPATH:"%MAYA%\lib" OpenMaya.lib OpenMayaAnim.lib OpenMayaUI.lib OpenMayaRender.lib Foundation.lib /IMPLIB:"%LINKTMP%\MPyFile_File_Simple.lib" /OUT:"%LINKTMP%\MPyFile_File_Simple.mll" /EXPORT:initializePlugin /EXPORT:uninitializePlugin
if errorlevel 1 exit /b 1
copy /Y "%LINKTMP%\MPyFile_File_Simple.mll" "%HERE%..\MPyFile_File_Simple.mll" >nul
if errorlevel 1 exit /b 1
rd /s /q "%LINKTMP%" 2>nul
del "%HERE%fileTexture.obj" 2>nul
echo Built: %HERE%..\MPyFile_File_Simple.mll
exit /b 0
