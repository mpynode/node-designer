@echo off
REM Generated combined build for native plugin 'mPyMega' (37 nodes).
REM Runs from any cmd.exe: MSVC is located via vswhere and vcvarsall x64
REM is called for you. An 'x64 Native Tools Command Prompt' is used as-is.
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
set "OBJS="
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\mPyDnet.cpp" /Fo"%HERE%source\mPyDnet.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\mPyDnet.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\comboCorrectives.cpp" /Fo"%HERE%source\comboCorrectives.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\comboCorrectives.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\procrustesTags.cpp" /Fo"%HERE%source\procrustesTags.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\procrustesTags.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\nurbsWave.cpp" /Fo"%HERE%source\nurbsWave.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\nurbsWave.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\patchRelax.cpp" /Fo"%HERE%source\patchRelax.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\patchRelax.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\rbfWrapDeformer.cpp" /Fo"%HERE%source\rbfWrapDeformer.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\rbfWrapDeformer.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\sineRipple.cpp" /Fo"%HERE%source\sineRipple.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\sineRipple.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\unitSphereCollision.cpp" /Fo"%HERE%source\unitSphereCollision.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\unitSphereCollision.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\compositeTexture.cpp" /Fo"%HERE%source\compositeTexture.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\compositeTexture.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\scanlineTex.cpp" /Fo"%HERE%source\scanlineTex.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\scanlineTex.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\fileTexture.cpp" /Fo"%HERE%source\fileTexture.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\fileTexture.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\gameOfLifeTex.cpp" /Fo"%HERE%source\gameOfLifeTex.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\gameOfLifeTex.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\twoBoneIK.cpp" /Fo"%HERE%source\twoBoneIK.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\twoBoneIK.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\animatedSelection.cpp" /Fo"%HERE%source\animatedSelection.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\animatedSelection.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\animatedText.cpp" /Fo"%HERE%source\animatedText.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\animatedText.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\meshRegionLocator.cpp" /Fo"%HERE%source\meshRegionLocator.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\meshRegionLocator.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\widgetShowcase.cpp" /Fo"%HERE%source\widgetShowcase.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\widgetShowcase.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\diskMeshCache.cpp" /Fo"%HERE%source\diskMeshCache.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\diskMeshCache.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\gameOfLifeMesh.cpp" /Fo"%HERE%source\gameOfLifeMesh.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\gameOfLifeMesh.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\jsonMeshReader.cpp" /Fo"%HERE%source\jsonMeshReader.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\jsonMeshReader.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\meshMaze.cpp" /Fo"%HERE%source\meshMaze.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\meshMaze.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\metaballs.cpp" /Fo"%HERE%source\metaballs.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\metaballs.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\uvLayoutMesh.cpp" /Fo"%HERE%source\uvLayoutMesh.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\uvLayoutMesh.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\voxelizeMesh.cpp" /Fo"%HERE%source\voxelizeMesh.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\voxelizeMesh.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\bubbleSort.cpp" /Fo"%HERE%source\bubbleSort.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\bubbleSort.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\hexAttribute.cpp" /Fo"%HERE%source\hexAttribute.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\hexAttribute.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\ouch.cpp" /Fo"%HERE%source\ouch.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\ouch.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\rbfWrap.cpp" /Fo"%HERE%source\rbfWrap.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\rbfWrap.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\spine.cpp" /Fo"%HERE%source\spine.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\spine.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\spline.cpp" /Fo"%HERE%source\spline.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\spline.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\springChain.cpp" /Fo"%HERE%source\springChain.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\springChain.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\helixCurve.cpp" /Fo"%HERE%source\helixCurve.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\helixCurve.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\rippleSurf.cpp" /Fo"%HERE%source\rippleSurf.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\rippleSurf.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\dualQuaternionSkin.cpp" /Fo"%HERE%source\dualQuaternionSkin.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\dualQuaternionSkin.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\linearBlendSkin.cpp" /Fo"%HERE%source\linearBlendSkin.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\linearBlendSkin.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\twistSwingSkin.cpp" /Fo"%HERE%source\twistSwingSkin.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\twistSwingSkin.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\aimTransform.cpp" /Fo"%HERE%source\aimTransform.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\aimTransform.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /Zc:__cplusplus /permissive- /I "%QTINC%" /FI nd_msvc_stdext_compat.h /c "%HERE%source\plugin_main.cpp" /Fo"%HERE%source\plugin_main.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\plugin_main.obj""
cl /nologo /LD %OBJS% /link /LIBPATH:"%MAYA%\lib" OpenMaya.lib OpenMayaAnim.lib OpenMayaUI.lib OpenMayaRender.lib Foundation.lib Qt6Core.lib Qt6Gui.lib Qt6Widgets.lib /OUT:"%HERE%..\mPyMega.mll" /EXPORT:initializePlugin /EXPORT:uninitializePlugin
if errorlevel 1 exit /b 1
del %OBJS% 2>nul
echo Built: %HERE%..\mPyMega.mll
exit /b 0
