@echo off
REM Build mPyMega for the scenes beside this script.
REM
REM Usage:  build.bat [maya-version]      e.g. build.bat 2026
REM With no argument the newest installed Maya is used; set MAYA to override.
REM Runs from any cmd.exe: MSVC is located via vswhere and vcvarsall x64 is
REM called for you. An 'x64 Native Tools Command Prompt' is used as-is.
REM
REM No binary ships with this repo: a Maya plug-in is compiled against one Maya
REM version's devkit and will not load in another. This compiles the committed
REM C++ under build\ beside this script (37 node types + 32 bundled commands,
REM namespaced per node and linked through one generated plugin_main.cpp). The
REM result lands beside this script in a folder named after the Maya version --
REM 2026\mPyMega.mll -- which is the folder MAYA_PLUG_IN_PATH points at.
setlocal

set "HERE=%~dp0"

if not exist "%HERE%build\build.bat" (
  echo build.bat: no combined build tree at "%HERE%build" 1>&2
  exit /b 1
)

REM The inner script owns Maya-version resolution (argument, then MAYA, then the
REM newest install with a devkit), the version folder and its own diagnostics --
REM forward the argument rather than second-guessing it here. One resolver, one
REM place to fix.
REM
REM The name stays exactly mPyMega.mll: the version lives in the folder, never in
REM the file name. Maya derives a plug-in's NAME from its filename, and every
REM scene here carries `requires ... "mPyMega"`. A version-stamped copy loads fine
REM but registers as "mPyMega.2026", and then all 40 scenes open with unknown
REM nodes -- with nothing failing at build time.
call "%HERE%build\build.bat" %1
if errorlevel 1 exit /b 1

REM Builds before the version folders installed a copy into plugin\. It is left
REM in place -- a MAYA_PLUG_IN_PATH may still name it -- but two mPyMega on the
REM path load whichever Maya meets first, so say so.
if exist "%HERE%plugin\mPyMega.mll" echo build.bat: note: an older plugin\mPyMega.mll is left in place; Maya loads whichever mPyMega comes first on the plug-in path 1>&2

endlocal
