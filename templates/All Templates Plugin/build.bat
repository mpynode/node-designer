@echo off
REM Build mPyMega and install it into plugin\, ready for the scenes beside it.
REM
REM Usage:  build.bat [maya-version]      e.g. build.bat 2026
REM With no argument the newest installed Maya is used; set MAYA to override.
REM Runs from any cmd.exe: MSVC is located via vswhere and vcvarsall x64 is
REM called for you. An 'x64 Native Tools Command Prompt' is used as-is.
REM
REM No binary ships with this repo: a Maya plug-in is compiled against one Maya
REM version's devkit and will not load in another. This compiles the committed
REM C++ under build\ beside this script (37 node types + 32 bundled commands,
REM namespaced per node and linked through one generated plugin_main.cpp) and
REM drops the result next to the demo scenes.
setlocal

set "HERE=%~dp0"

if not exist "%HERE%build\build.bat" (
  echo build.bat: no combined build tree at "%HERE%build" 1>&2
  exit /b 1
)

REM The inner script owns Maya-version resolution (argument, then MAYA, then the
REM newest install with a devkit) and its own diagnostics -- forward the
REM argument rather than second-guessing it here. One resolver, one place to fix.
call "%HERE%build\build.bat" %1
if errorlevel 1 exit /b 1

REM plugin\ holds only ignored build products, so it does NOT exist in a fresh
REM clone -- git does not track empty directories.
if not exist "%HERE%plugin" mkdir "%HERE%plugin"

REM The name must stay exactly mPyMega.mll. Maya derives a plug-in's NAME from
REM its filename, and every scene here carries `requires ... "mPyMega"`. A
REM version-stamped copy loads fine but registers as "mPyMega.2026", and then
REM all 39 scenes open with unknown nodes -- with nothing failing at build time.
copy /Y "%HERE%mPyMega.mll" "%HERE%plugin\mPyMega.mll" >nul
if errorlevel 1 exit /b 1
echo Installed: %HERE%plugin\mPyMega.mll

endlocal
