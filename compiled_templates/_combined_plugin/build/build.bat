@echo off
REM Generated combined build for native plugin 'mPyMega' (37 nodes).
REM Run from an 'x64 Native Tools Command Prompt for VS'.
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
set "OBJS="
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\mPyDnet.cpp" /Fo"%HERE%source\mPyDnet.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\mPyDnet.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\comboCorrectives.cpp" /Fo"%HERE%source\comboCorrectives.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\comboCorrectives.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\procrustesTags.cpp" /Fo"%HERE%source\procrustesTags.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\procrustesTags.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\nurbsWave.cpp" /Fo"%HERE%source\nurbsWave.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\nurbsWave.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\patchRelax.cpp" /Fo"%HERE%source\patchRelax.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\patchRelax.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\rbfWrapDeformer.cpp" /Fo"%HERE%source\rbfWrapDeformer.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\rbfWrapDeformer.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\sineRipple.cpp" /Fo"%HERE%source\sineRipple.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\sineRipple.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\unitSphereCollision.cpp" /Fo"%HERE%source\unitSphereCollision.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\unitSphereCollision.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\compositeTexture.cpp" /Fo"%HERE%source\compositeTexture.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\compositeTexture.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\scanlineTex.cpp" /Fo"%HERE%source\scanlineTex.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\scanlineTex.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\fileTexture.cpp" /Fo"%HERE%source\fileTexture.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\fileTexture.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\gameOfLifeTex.cpp" /Fo"%HERE%source\gameOfLifeTex.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\gameOfLifeTex.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\twoBoneIK.cpp" /Fo"%HERE%source\twoBoneIK.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\twoBoneIK.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\animatedSelection.cpp" /Fo"%HERE%source\animatedSelection.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\animatedSelection.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\animatedText.cpp" /Fo"%HERE%source\animatedText.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\animatedText.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\meshRegionLocator.cpp" /Fo"%HERE%source\meshRegionLocator.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\meshRegionLocator.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\widgetShowcase.cpp" /Fo"%HERE%source\widgetShowcase.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\widgetShowcase.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\diskMeshCache.cpp" /Fo"%HERE%source\diskMeshCache.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\diskMeshCache.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\gameOfLifeMesh.cpp" /Fo"%HERE%source\gameOfLifeMesh.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\gameOfLifeMesh.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\jsonMeshReader.cpp" /Fo"%HERE%source\jsonMeshReader.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\jsonMeshReader.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\meshMaze.cpp" /Fo"%HERE%source\meshMaze.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\meshMaze.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\metaballs.cpp" /Fo"%HERE%source\metaballs.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\metaballs.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\uvLayoutMesh.cpp" /Fo"%HERE%source\uvLayoutMesh.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\uvLayoutMesh.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\voxelizeMesh.cpp" /Fo"%HERE%source\voxelizeMesh.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\voxelizeMesh.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\bubbleSort.cpp" /Fo"%HERE%source\bubbleSort.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\bubbleSort.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\hexAttribute.cpp" /Fo"%HERE%source\hexAttribute.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\hexAttribute.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\ouch.cpp" /Fo"%HERE%source\ouch.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\ouch.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\rbfWrap.cpp" /Fo"%HERE%source\rbfWrap.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\rbfWrap.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\spine.cpp" /Fo"%HERE%source\spine.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\spine.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\spline.cpp" /Fo"%HERE%source\spline.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\spline.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\springChain.cpp" /Fo"%HERE%source\springChain.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\springChain.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\helixCurve.cpp" /Fo"%HERE%source\helixCurve.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\helixCurve.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\rippleSurf.cpp" /Fo"%HERE%source\rippleSurf.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\rippleSurf.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\dualQuaternionSkin.cpp" /Fo"%HERE%source\dualQuaternionSkin.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\dualQuaternionSkin.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\linearBlendSkin.cpp" /Fo"%HERE%source\linearBlendSkin.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\linearBlendSkin.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\twistSwingSkin.cpp" /Fo"%HERE%source\twistSwingSkin.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\twistSwingSkin.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /D MNoVersionString /D MNoPluginEntry /c "%HERE%source\aimTransform.cpp" /Fo"%HERE%source\aimTransform.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\aimTransform.obj""
cl /nologo /std:c++17 /O2 /fp:precise /EHsc /MD /bigobj /utf-8 /D NT_PLUGIN /D REQUIRE_IOSTREAM /D _BOOL /D WIN32 /D _WINDOWS /D _CRT_SECURE_NO_WARNINGS /c "%HERE%source\plugin_main.cpp" /Fo"%HERE%source\plugin_main.obj" /I "%MAYA%\include"
if errorlevel 1 exit /b 1
set "OBJS=%OBJS% "%HERE%source\plugin_main.obj""
cl /nologo /LD %OBJS% /link /LIBPATH:"%MAYA%\lib" OpenMaya.lib OpenMayaAnim.lib OpenMayaUI.lib OpenMayaRender.lib Foundation.lib Qt6Core.lib Qt6Gui.lib Qt6Widgets.lib /OUT:"%HERE%..\mPyMega.mll" /EXPORT:initializePlugin /EXPORT:uninitializePlugin
if errorlevel 1 exit /b 1
del %OBJS% 2>nul
echo Built: %HERE%..\mPyMega.mll
